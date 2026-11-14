"""The local Postgres + pgvector store (ADR-004, ADR-005, ADR-009). Rows are parsed into typed records here.

Embeddings travel as pgvector text literals; nothing biometric is logged.
"""

import re
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from pydantic import BaseModel

from lektyra.domain.matching import K, Neighbour
from lektyra.errors import LektyraError

MIGRATION: Final = re.compile(r"^(\d{4})_.+\.sql$")
Row = dict[str, Any]
SpeakerStatus = Literal["auto", "suggested", "unknown", "confirmed", "new"]
FlagKind = Literal["words", "speaker", "name_number", "other"]
PersonKind = Literal["politician", "host", "journalist", "expert", "official", "other"]
ROBOT: Final = "lektyra"  # the actor of what matching does on its own
VOICE_LOCK: Final = 4_851_302  # advisory lock key: who may write voices right now (ADR-012)


class PersonFields(BaseModel):
    """What Martin says about a person. `external_ref` links to knowledge kept elsewhere (Wikidata id or URL)."""

    name: str
    kind: PersonKind = "other"
    function: str | None = None
    party: str | None = None
    public_figure: bool = True
    note: str | None = None
    external_ref: str | None = None


class PhotoSource(BaseModel):
    """Where a picture came from (ADR-015). All empty: a file Martin uploaded."""

    source_url: str | None = None
    license: str | None = None
    author: str | None = None


class PhotoInfo(PhotoSource):
    version: str  # the picture's URL carries it, so a new picture is a new URL


class PhotoRow(BaseModel):
    object_key: str
    content_type: str
    version: str


class PersonRow(BaseModel):
    id: int
    key: str
    number: int
    name: str
    anonymous: bool
    kind: PersonKind
    external_ref: str | None
    function: str | None
    party: str | None
    public_figure: bool
    note: str | None
    samples: int
    events: int
    photo: PhotoInfo | None = None


class SpeakerRow(BaseModel):
    id: int
    event_id: str
    label: str
    talk_s: float
    share: float
    person_id: int | None
    person_name: str | None
    person_number: int | None
    person_anonymous: bool | None
    status: SpeakerStatus
    score: float | None
    no_profile: bool


class EventRow(BaseModel):
    id: str
    title: str
    source_url: str
    is_live: bool
    audio_ms: int
    started_at: datetime
    speakers: int
    named: int


class RatingRow(BaseModel):
    variant: str
    accuracy: int | None
    names_numbers: int | None
    note: str
    rated_at: datetime


class FlagRow(BaseModel):
    id: int
    variant: str
    at_ms: int
    kind: FlagKind
    note: str


class VoiceRow(BaseModel):
    event_id: str
    event_title: str
    label: str
    talk_s: float
    person_id: int | None
    person_name: str | None
    person_anonymous: bool | None
    status: SpeakerStatus
    embedding: list[float]


def vector(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


def _person(row: Row) -> PersonRow:
    photo = (
        PhotoInfo(
            version=row["photo_version"],
            source_url=row["photo_source_url"],
            license=row["photo_license"],
            author=row["photo_author"],
        )
        if row["photo_version"]
        else None
    )
    return PersonRow.model_validate({**row, "photo": photo})


def parse_vector(text: object) -> list[float]:
    return [float(x) for x in str(text).strip("[]").split(",") if x]


def with_database(url: str, name: str) -> str:
    """The same server and user, another database (the manual-testing one, ADR-009)."""
    return make_conninfo(url, dbname=name)


def database_name(url: str) -> str:
    return str(conninfo_to_dict(url).get("dbname", ""))


def ensure_database(url: str, reset: bool) -> bool:
    """Create the URL's database when missing; with `reset`, drop it first. Returns True when it was (re)created."""
    name = database_name(url)
    with psycopg.connect(make_conninfo(url, dbname="postgres"), autocommit=True, connect_timeout=5) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None
        if exists and reset:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        if not exists or reset:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            return True
    return False


class Store:
    """One connection, reused and reopened when it breaks (a database restart). Transactions on it take turns:
    a local single-user tool needs no pool, but a new connection per query cost ~40 ms each on Windows."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._conn: psycopg.Connection[Row] | None = None
        self._lock = threading.RLock()

    def _connection(self) -> psycopg.Connection[Row]:
        if self._conn is None or self._conn.closed or self._conn.broken:
            self._conn = psycopg.connect(self._url, row_factory=dict_row, connect_timeout=5, autocommit=True)
        return self._conn

    @contextmanager
    def _tx(self) -> Iterator[psycopg.Cursor[Row]]:
        with self._lock:
            conn = self._connection()
            with conn.transaction(), conn.cursor() as cur:
                yield cur

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        """Voices are written by one process at a time, so two `lektyra ui` running live sessions side by side never
        found the same voice twice. A session-level advisory lock on this store's connection; Postgres frees it by
        itself if the connection or the process dies."""
        with self._tx() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (VOICE_LOCK,))
        try:
            yield
        finally:
            with self._tx() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (VOICE_LOCK,))

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def ping(self) -> None:
        with self._tx() as cur:
            cur.execute("SELECT 1")

    # migrations -------------------------------------------------------------------------------------------------
    def migrate(self, folder: Path) -> list[int]:
        """Apply every numbered migration newer than the database's version. Each file records its own version."""
        with self._tx() as cur:
            cur.execute("SELECT to_regclass('schema_version') IS NOT NULL AS ready")
            ready = cur.fetchone()
            current = 0
            if ready and ready["ready"]:
                cur.execute("SELECT coalesce(max(version), 0) AS v FROM schema_version")
                row = cur.fetchone()
                current = int(row["v"]) if row else 0
        applied: list[int] = []
        for path in sorted(folder.glob("*.sql")):
            m = MIGRATION.match(path.name)
            if not m or int(m.group(1)) <= current:
                continue
            with self._tx() as cur:
                cur.execute(path.read_text(encoding="utf-8").encode("utf-8"))
            applied.append(int(m.group(1)))
        return applied

    # events and speakers ----------------------------------------------------------------------------------------
    def upsert_event(
        self, event_id: str, title: str, source_url: str, source_id: str | None, is_live: bool,
        started_at: datetime, audio_ms: int,
    ) -> None:  # fmt: skip
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO event (id, source_url, source_id, title, is_live, started_at, audio_ms)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, audio_ms = EXCLUDED.audio_ms""",
                (event_id, source_url, source_id, title, is_live, started_at, audio_ms),
            )

    def upsert_speaker(
        self, event_id: str, label: str, centroid: Sequence[float], model: str, talk_s: float, share: float
    ) -> None:
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO event_speaker (event_id, label, embedding, embedding_model, talk_s, share)
                   VALUES (%s, %s, %s::vector, %s, %s, %s)
                   ON CONFLICT ON CONSTRAINT event_speaker_unique DO UPDATE
                   SET embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model,
                       talk_s = EXCLUDED.talk_s, share = EXCLUDED.share""",
                (event_id, label, vector(centroid), model, talk_s, share),
            )

    def events(self) -> list[EventRow]:
        with self._tx() as cur:
            cur.execute(
                """SELECT e.id, e.title, e.source_url, e.is_live, e.audio_ms, e.started_at,
                          count(s.id) AS speakers, count(s.id) FILTER (WHERE s.status = 'confirmed') AS named
                   FROM event e LEFT JOIN event_speaker s ON s.event_id = e.id
                   GROUP BY e.id ORDER BY e.started_at DESC"""
            )
            return [EventRow.model_validate(r) for r in cur.fetchall()]

    def event(self, event_id: str) -> EventRow:
        found = [e for e in self.events() if e.id == event_id]
        if not found:
            raise LektyraError("not_found", f"No video {event_id!r}.")
        return found[0]

    def speakers(self, event_id: str | None = None) -> list[SpeakerRow]:
        """One video's speakers, or all of them in the order they were heard (oldest video first): the order in
        which unnamed voices get their numbers."""
        with self._tx() as cur:
            cur.execute(
                """SELECT s.id, s.event_id, s.label, coalesce(s.talk_s, 0) AS talk_s, coalesce(s.share, 0) AS share,
                          s.person_id, p.name AS person_name, p.number AS person_number,
                          p.anonymous AS person_anonymous, s.status, s.score, s.no_profile
                   FROM event_speaker s JOIN event e ON e.id = s.event_id LEFT JOIN person p ON p.id = s.person_id
                   WHERE %s::text IS NULL OR s.event_id = %s
                   ORDER BY e.started_at, s.event_id, s.share DESC NULLS LAST, s.label""",
                (event_id, event_id),
            )
            return [SpeakerRow.model_validate(r) for r in cur.fetchall()]

    def speaker(self, event_id: str, label: str) -> SpeakerRow:
        found = [s for s in self.speakers(event_id) if s.label == label]
        if not found:
            raise LektyraError("not_found", f"No speaker {label} in this video.")
        return found[0]

    def _centroid(self, speaker_id: int) -> tuple[list[float], str]:
        with self._tx() as cur:
            cur.execute("SELECT embedding::text AS e, embedding_model FROM event_speaker WHERE id = %s", (speaker_id,))
            row = cur.fetchone()
        if row is None or row["e"] is None:
            raise LektyraError("not_found", "This speaker has no voice fingerprint yet.")
        return parse_vector(row["e"]), str(row["embedding_model"])

    def voices(self) -> list[VoiceRow]:
        with self._tx() as cur:
            cur.execute(
                """SELECT s.event_id, e.title AS event_title, s.label, coalesce(s.talk_s, 0) AS talk_s,
                          s.person_id, p.name AS person_name, p.anonymous AS person_anonymous, s.status,
                          s.embedding::text AS e
                   FROM event_speaker s JOIN event e ON e.id = s.event_id LEFT JOIN person p ON p.id = s.person_id
                   WHERE s.embedding IS NOT NULL ORDER BY e.started_at, s.label"""
            )
            rows = cur.fetchall()
        return [VoiceRow.model_validate({**r, "embedding": parse_vector(r["e"])}) for r in rows]

    # persons ----------------------------------------------------------------------------------------------------
    def persons(self) -> list[PersonRow]:
        with self._tx() as cur:
            cur.execute(
                """SELECT p.id, p.key::text AS key, p.number, p.name, p.anonymous, p.kind, p.external_ref,
                          p.function, p.party, p.public_figure, p.note,
                          (SELECT count(*) FROM voice_sample v WHERE v.person_id = p.id) AS samples,
                          (SELECT count(DISTINCT s.event_id) FROM event_speaker s WHERE s.person_id = p.id) AS events,
                          ph.version AS photo_version, ph.source_url AS photo_source_url,
                          ph.license AS photo_license, ph.author AS photo_author
                   FROM person p LEFT JOIN person_photo ph ON ph.person_id = p.id
                   ORDER BY p.anonymous, CASE WHEN p.anonymous THEN p.number END, p.name"""
            )
            return [_person(r) for r in cur.fetchall()]

    def person(self, person_id: int) -> PersonRow:
        found = [p for p in self.persons() if p.id == person_id]
        if not found:
            raise LektyraError("not_found", f"No person with id {person_id}.")
        return found[0]

    def save_person(self, person_id: int | None, fields: PersonFields, actor: str) -> int:
        f = fields
        name = f.name
        try:
            with self._tx() as cur:
                if person_id is None:
                    cur.execute(
                        """INSERT INTO person (name, kind, function, party, public_figure, note, external_ref)
                           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                        (f.name, f.kind, f.function, f.party, f.public_figure, f.note, f.external_ref),
                    )
                else:
                    # An unnamed voice stays unnamed only while it keeps its "Voice N" name.
                    cur.execute(
                        """UPDATE person SET name = %s, kind = %s, function = %s, party = %s, public_figure = %s,
                                  note = %s, external_ref = %s, anonymous = anonymous AND name = %s
                           WHERE id = %s RETURNING id""",
                        (
                            f.name,
                            f.kind,
                            f.function,
                            f.party,
                            f.public_figure,
                            f.note,
                            f.external_ref,
                            f.name,
                            person_id,
                        ),
                    )
                row = cur.fetchone()
                if row is None:
                    raise LektyraError("not_found", f"No person with id {person_id}.")
                new_id = int(row["id"])
                cur.execute(
                    "INSERT INTO audit_log (actor, action, subject, detail) VALUES (%s, 'person', %s, '{}')",
                    (actor, str(new_id)),
                )
                return new_id
        except psycopg.errors.UniqueViolation as err:
            raise LektyraError("conflict", f"Someone called {name!r} is already in the list.") from err

    def forget_person(self, person_id: int, actor: str) -> None:
        """Delete the person and every voice sample. Their speakers become unknown and never grow a new profile:
        forgetting sticks (ADR-005)."""
        with self._tx() as cur:
            cur.execute(
                """UPDATE event_speaker SET person_id = NULL, status = 'unknown', score = NULL, no_profile = true
                   WHERE person_id = %s""",
                (person_id,),
            )
            cur.execute("DELETE FROM person WHERE id = %s RETURNING id", (person_id,))
            if cur.fetchone() is None:
                raise LektyraError("not_found", f"No person with id {person_id}.")
            cur.execute(
                "INSERT INTO audit_log (actor, action, subject, detail) VALUES (%s, 'forget', %s, '{}')",
                (actor, str(person_id)),
            )

    # pictures (ADR-015) -----------------------------------------------------------------------------------------
    def photo(self, person_id: int) -> PhotoRow:
        with self._tx() as cur:
            cur.execute("SELECT object_key, content_type, version FROM person_photo WHERE person_id = %s", (person_id,))
            row = cur.fetchone()
        if row is None:
            raise LektyraError("not_found", "This person has no picture.")
        return PhotoRow.model_validate(row)

    def photo_keys(self) -> set[str]:
        """Every object a person points at: anything else in the bucket is left over and may go."""
        with self._tx() as cur:
            cur.execute("SELECT object_key FROM person_photo")
            return {str(r["object_key"]) for r in cur.fetchall()}

    def save_photo(
        self,
        person_id: int,
        object_key: str,
        size: tuple[int, int],
        version: str,
        content_type: str,
        source: PhotoSource,
        actor: str,
    ) -> None:
        """One picture per person: a new one replaces the old row. The audit says where it came from."""
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO person_photo (person_id, object_key, content_type, width, height, version, source_url,
                                             license, author, added_by)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (person_id) DO UPDATE SET object_key = EXCLUDED.object_key,
                       content_type = EXCLUDED.content_type,
                       width = EXCLUDED.width, height = EXCLUDED.height, version = EXCLUDED.version,
                       source_url = EXCLUDED.source_url, license = EXCLUDED.license, author = EXCLUDED.author,
                       added_by = EXCLUDED.added_by, added_at = now()""",
                (
                    person_id,
                    object_key,
                    content_type,
                    size[0],
                    size[1],
                    version,
                    source.source_url,
                    source.license,
                    source.author,
                    actor,
                ),
            )
            cur.execute(
                """INSERT INTO audit_log (actor, action, subject, detail)
                   VALUES (%s, 'photo', %s, jsonb_build_object('source', %s::text, 'license', %s::text))""",
                (actor, str(person_id), source.source_url or "upload", source.license),
            )

    def delete_photo(self, person_id: int, actor: str) -> None:
        with self._tx() as cur:
            cur.execute("DELETE FROM person_photo WHERE person_id = %s RETURNING person_id", (person_id,))
            if cur.fetchone() is None:
                raise LektyraError("not_found", "This person has no picture.")
            cur.execute(
                """INSERT INTO audit_log (actor, action, subject, detail)
                   VALUES (%s, 'photo', %s, '{"removed": true}')""",
                (actor, str(person_id)),
            )

    # naming and profiles ----------------------------------------------------------------------------------------
    def assign(
        self, speaker: SpeakerRow, person_id: int, samples: Sequence[Sequence[float]], model: str, actor: str
    ) -> None:
        """Name a speaker: the row points at the person, and this speaker's samples replace any it gave before."""
        self.person(person_id)
        with self._tx() as cur:
            cur.execute("DELETE FROM voice_sample WHERE event_speaker_id = %s", (speaker.id,))
            cur.execute(
                "DELETE FROM voice_rejection WHERE event_speaker_id = %s AND person_id = %s", (speaker.id, person_id)
            )
            cur.execute(
                "UPDATE event_speaker SET person_id = %s, status = 'confirmed', score = NULL WHERE id = %s",
                (person_id, speaker.id),
            )
            for vec in samples:
                cur.execute(
                    """INSERT INTO voice_sample (person_id, event_id, event_speaker_id, start_ms, end_ms, embedding,
                                                 embedding_model, provenance, quality, weight, confirmed_by)
                       VALUES (%s, %s, %s, 0, 0, %s::vector, %s, 'human_confirmed', 1, 1, %s)""",
                    (person_id, speaker.event_id, speaker.id, vector(vec), model, actor),
                )
            cur.execute(
                """INSERT INTO audit_log (actor, action, subject, detail)
                   VALUES (%s, 'name', %s, jsonb_build_object('person_id', %s::bigint, 'samples', %s::int))""",
                (actor, f"{speaker.event_id}/{speaker.label}", person_id, len(samples)),
            )

    def create_voice(self, speaker: SpeakerRow, samples: Sequence[Sequence[float]], model: str) -> int:
        """A voice nobody has heard before gets the next number and this speaker's samples (ADR-012)."""
        with self._tx() as cur:
            cur.execute("SELECT nextval('voice_number_seq') AS n")
            row = cur.fetchone()
            if row is None:
                raise LektyraError("internal", "No voice number was given.")
            number = int(row["n"])
            cur.execute(
                """INSERT INTO person (number, name, anonymous, public_figure) VALUES (%s, %s, true, true)
                   RETURNING id""",
                (number, f"Voice {number}"),
            )
            created = cur.fetchone()
            if created is None:
                raise LektyraError("internal", "The voice was not saved.")
            voice_id = int(created["id"])
            cur.execute("DELETE FROM voice_sample WHERE event_speaker_id = %s", (speaker.id,))
            for vec in samples:
                cur.execute(
                    """INSERT INTO voice_sample (person_id, event_id, event_speaker_id, start_ms, end_ms, embedding,
                                                 embedding_model, provenance, quality, weight)
                       VALUES (%s, %s, %s, 0, 0, %s::vector, %s, 'auto', 1, 1)""",
                    (voice_id, speaker.event_id, speaker.id, vector(vec), model),
                )
            cur.execute(
                "UPDATE event_speaker SET person_id = %s, status = 'new', score = NULL WHERE id = %s",
                (voice_id, speaker.id),
            )
            cur.execute(
                """INSERT INTO audit_log (actor, action, subject, detail)
                   VALUES (%s, 'voice', %s, jsonb_build_object('number', %s::int))""",
                (ROBOT, f"{speaker.event_id}/{speaker.label}", number),
            )
            return voice_id

    def merge(self, source_id: int, target_id: int, actor: str) -> None:
        """`source` and `target` are one person: samples, speakers and refusals move to `target`, which keeps the
        older (lower) number; `source` is gone."""
        if source_id == target_id:
            return
        source = self.person(source_id)
        self.person(target_id)
        with self._tx() as cur:
            cur.execute("UPDATE voice_sample SET person_id = %s WHERE person_id = %s", (target_id, source_id))
            cur.execute("UPDATE event_speaker SET person_id = %s WHERE person_id = %s", (target_id, source_id))
            cur.execute(
                """INSERT INTO voice_rejection (event_speaker_id, person_id, created_by, created_at)
                   SELECT event_speaker_id, %s, created_by, created_at FROM voice_rejection WHERE person_id = %s
                   ON CONFLICT DO NOTHING""",
                (target_id, source_id),
            )
            cur.execute(  # a picture follows the person, unless the target has its own
                """UPDATE person_photo SET person_id = %s
                   WHERE person_id = %s AND NOT EXISTS (SELECT 1 FROM person_photo WHERE person_id = %s)""",
                (target_id, source_id, target_id),
            )
            cur.execute("DELETE FROM person WHERE id = %s", (source_id,))
            cur.execute("UPDATE person SET number = least(number, %s) WHERE id = %s", (source.number, target_id))
            cur.execute(
                """INSERT INTO audit_log (actor, action, subject, detail)
                   VALUES (%s, 'merge', %s, jsonb_build_object('into', %s::bigint))""",
                (actor, str(source_id), target_id),
            )

    def unassign(self, speaker: SpeakerRow, actor: str) -> None:
        with self._tx() as cur:
            cur.execute("DELETE FROM voice_sample WHERE event_speaker_id = %s", (speaker.id,))
            cur.execute(
                "UPDATE event_speaker SET person_id = NULL, status = 'unknown', score = NULL WHERE id = %s",
                (speaker.id,),
            )
            cur.execute(
                "INSERT INTO audit_log (actor, action, subject, detail) VALUES (%s, 'unname', %s, '{}')",
                (actor, f"{speaker.event_id}/{speaker.label}"),
            )

    def reject(self, speaker: SpeakerRow, person_id: int, actor: str) -> None:
        self.person(person_id)
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO voice_rejection (event_speaker_id, person_id, created_by) VALUES (%s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (speaker.id, person_id, actor),
            )
            cur.execute(
                """INSERT INTO audit_log (actor, action, subject, detail)
                   VALUES (%s, 'reject', %s, jsonb_build_object('person_id', %s::bigint))""",
                (actor, f"{speaker.event_id}/{speaker.label}", person_id),
            )

    def set_guess(self, speaker_id: int, person_id: int | None, score: float | None, status: SpeakerStatus) -> None:
        """What matching thinks of a speaker Martin has not named. Martin's names and the speaker an unnamed voice
        was founded on are never touched."""
        with self._tx() as cur:
            cur.execute(
                """UPDATE event_speaker SET person_id = %s, score = %s, status = %s
                   WHERE id = %s AND status NOT IN ('confirmed', 'new')""",
                (person_id, score, status, speaker_id),
            )

    def neighbours(self, speaker: SpeakerRow, per_person: int = K) -> list[Neighbour]:
        """Each person's `per_person` samples closest to this speaker's voice, from other videos only, without
        persons Martin rejected for this speaker."""
        centroid, model = self._centroid(speaker.id)
        return self.nearest(centroid, model, speaker.event_id, speaker.id, per_person)

    def nearest(
        self, voice: Sequence[float], model: str, other_than_event: str, speaker_id: int | None = None,
        per_person: int = K,
    ) -> list[Neighbour]:  # fmt: skip
        """The closest samples to any voice vector (a live speaker has no row yet). Exact scan: a few thousand
        samples need no index."""
        with self._tx() as cur:
            cur.execute(
                """SELECT person_id, similarity FROM (
                     SELECT v.person_id, 1 - (v.embedding <=> %s::vector) AS similarity,
                            row_number() OVER (PARTITION BY v.person_id ORDER BY v.embedding <=> %s::vector) AS rn
                     FROM voice_sample v
                     WHERE v.embedding_model = %s AND v.event_id <> %s
                       AND v.person_id NOT IN (SELECT person_id FROM voice_rejection WHERE event_speaker_id = %s)
                   ) ranked WHERE rn <= %s ORDER BY similarity DESC""",
                (vector(voice), vector(voice), model, other_than_event, speaker_id or -1, per_person),
            )
            return [Neighbour(int(r["person_id"]), float(r["similarity"])) for r in cur.fetchall()]

    def rejected(self, speaker_id: int) -> list[int]:
        with self._tx() as cur:
            cur.execute("SELECT person_id FROM voice_rejection WHERE event_speaker_id = %s", (speaker_id,))
            return [int(r["person_id"]) for r in cur.fetchall()]

    # ratings and flags ------------------------------------------------------------------------------------------
    def ratings(self, event_id: str) -> list[RatingRow]:
        with self._tx() as cur:
            cur.execute(
                "SELECT variant, accuracy, names_numbers, note, rated_at FROM transcript_rating WHERE event_id = %s",
                (event_id,),
            )
            return [RatingRow.model_validate(r) for r in cur.fetchall()]

    def rate(
        self, event_id: str, variant: str, accuracy: int | None, names_numbers: int | None, note: str, actor: str
    ) -> None:
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO transcript_rating (event_id, variant, accuracy, names_numbers, note, rated_by)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (event_id, variant) DO UPDATE SET accuracy = EXCLUDED.accuracy,
                     names_numbers = EXCLUDED.names_numbers, note = EXCLUDED.note, rated_by = EXCLUDED.rated_by,
                     rated_at = now()""",
                (event_id, variant, accuracy, names_numbers, note, actor),
            )
            cur.execute(
                "INSERT INTO audit_log (actor, action, subject, detail) VALUES (%s, 'rate', %s, '{}')",
                (actor, f"{event_id}/{variant}"),
            )

    def flags(self, event_id: str, variant: str) -> list[FlagRow]:
        with self._tx() as cur:
            cur.execute(
                """SELECT id, variant, at_ms, kind, note FROM transcript_flag
                   WHERE event_id = %s AND variant = %s ORDER BY at_ms""",
                (event_id, variant),
            )
            return [FlagRow.model_validate(r) for r in cur.fetchall()]

    def add_flag(self, event_id: str, variant: str, at_ms: int, kind: FlagKind, note: str, actor: str) -> FlagRow:
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO transcript_flag (event_id, variant, at_ms, kind, note, created_by)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, variant, at_ms, kind, note""",
                (event_id, variant, at_ms, kind, note, actor),
            )
            row = cur.fetchone()
            if row is None:
                raise LektyraError("internal", "The flag was not saved.")
            return FlagRow.model_validate(row)

    def delete_flag(self, event_id: str, flag_id: int) -> None:
        with self._tx() as cur:
            cur.execute("DELETE FROM transcript_flag WHERE id = %s AND event_id = %s RETURNING id", (flag_id, event_id))
            if cur.fetchone() is None:
                raise LektyraError("not_found", f"No flag with id {flag_id}.")
