"""The review service behind the local UI (ADR-009): videos and their speakers, persons, naming, transcripts,
ratings and flags. Files under data/events/ stay the source of the audio, words and diarization; the database holds
what Martin decides (names, ratings, flags) and the voice samples his names produce (ADR-004, ADR-005).

Naming a speaker is the one write with consequences: the speaker's clean windows become samples of that person, and
every speaker Martin has not named is matched again, so one name can suggest the same voice everywhere else.
"""

import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

import numpy as np
from pydantic import BaseModel

from lektyra.adapters.store.postgres import (
    FlagKind,
    FlagRow,
    PersonFields,
    PersonKind,
    RatingRow,
    SpeakerRow,
    SpeakerStatus,
    Store,
)
from lektyra.app.ingest import load_manifest
from lektyra.app.report import speaker_utterances
from lektyra.app.transcribe import variant_of
from lektyra.domain.diarization import Matrix, assign, normalise
from lektyra.domain.matching import CHUNK, Status, decide, profile_samples, ranked
from lektyra.domain.projection import project_2d
from lektyra.errors import LektyraError

EVENT_ID: Final = re.compile(r"^[\w.@-]+$")
ANSWER: Final = re.compile(r"^\d{4}\.json$")
SPEAKER_LABEL: Final = re.compile(r"^S(\d+)$")
CANDIDATES: Final = 3
NEAREST: Final = 3


# --- what the UI reads -------------------------------------------------------------------------------------------
class Variant(BaseModel):
    id: str  # folder name under raw/, e.g. elevenlabs__scribe-v2@sk
    engine: str  # elevenlabs/scribe-v2
    language: str | None
    covered: int  # pieces with an answer
    pieces: int


class EventSummary(BaseModel):
    id: str
    title: str
    source_url: str
    is_live: bool
    audio_ms: int
    started_at: datetime
    speakers: int
    named: int
    transcripts: int  # variants that cover every piece


class Document(BaseModel):
    name: str
    size: int


class EventDetail(EventSummary):
    complete: bool | None
    has_audio: bool
    variants: list[Variant]
    documents: list[Document]


class Candidate(BaseModel):
    person_id: int
    name: str
    score: float
    status: Status
    votes: int


class Speaker(BaseModel):
    label: str
    talk_s: float
    share: float
    person_id: int | None
    person_name: str | None
    person_number: int | None
    person_anonymous: bool | None
    status: SpeakerStatus
    score: float | None
    candidates: list[Candidate]
    rejected: list[int]
    no_profile: bool


class Person(BaseModel):
    id: int
    key: str  # never changes: what knowledge kept elsewhere points at
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


class Paragraph(BaseModel):
    start_ms: int
    end_ms: int
    label: str  # S1…N or "?"
    text: str


class SpeakerTurn(BaseModel):
    start_ms: int
    end_ms: int
    label: str


class Transcript(BaseModel):
    variant: str
    paragraphs: list[Paragraph]
    turns: list[SpeakerTurn]
    words: int
    unknown_words: int


class Rating(BaseModel):
    variant: str
    accuracy: int | None
    names_numbers: int | None
    note: str
    rated_at: datetime


class Flag(BaseModel):
    id: int
    variant: str
    at_ms: int
    kind: FlagKind
    note: str


class NearVoice(BaseModel):
    event_id: str
    label: str
    similarity: float


class VoicePoint(BaseModel):
    event_id: str
    event_title: str
    label: str
    talk_s: float
    person_id: int | None
    person_name: str | None
    person_anonymous: bool | None
    status: SpeakerStatus
    x: float
    y: float
    nearest: list[NearVoice]


class SyncResult(BaseModel):
    events: int
    speakers: int


# --- files the service reads -------------------------------------------------------------------------------------
class _SpeakerFile(BaseModel):
    label: str
    talk_s: float
    share: float


class _TurnFile(BaseModel):
    start_ms: int
    end_ms: int
    speaker: str


class _DiarizationFile(BaseModel):
    embedder: str
    speakers: list[_SpeakerFile]
    turns: list[_TurnFile]


def _speaker_index(label: str) -> int:
    m = SPEAKER_LABEL.match(label)
    if not m:
        raise LektyraError("invalid", f"{label!r} is not a speaker label (S1, S2, …).")
    return int(m.group(1)) - 1


@dataclass(frozen=True)
class _VoiceFiles:
    """One event's window fingerprints and speaker centroids, as diarization (or a live session) saved them."""

    windows: Matrix
    centres: Matrix
    model: str

    def samples(self, label: str, min_windows: int = 1) -> Matrix | None:
        index = _speaker_index(label)
        if index >= len(self.centres):
            return None
        labels = assign(self.windows, self.centres)
        return profile_samples(self.windows, labels, index, self.centres[index], min_windows=min_windows)


class Review:
    def __init__(self, store: Store, events_dir: Path, actor: str) -> None:
        self._store = store
        self._events = events_dir
        self._actor = actor
        # Naming, re-matching and a live session's updates take turns: two of them founding a voice for the same
        # speaker at once would leave an orphan.
        self.lock = threading.RLock()

    # files ------------------------------------------------------------------------------------------------------
    def _dir(self, event_id: str) -> Path:
        path = self._events / event_id
        if not EVENT_ID.match(event_id) or not (path / "manifest.json").is_file():
            raise LektyraError("not_found", f"No video {event_id!r}. It may have been renamed or deleted.")
        return path

    @staticmethod
    def _diarization(event_dir: Path) -> _DiarizationFile | None:
        path = event_dir / "diarization.json"
        return _DiarizationFile.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None

    @staticmethod
    def _variants(event_dir: Path, pieces: int) -> list[Variant]:
        raw = event_dir / "raw"
        found: list[Variant] = []
        for folder in sorted(raw.iterdir()) if raw.is_dir() else []:
            if not folder.is_dir():
                continue
            model, language = variant_of(folder.name)
            covered = sum(1 for f in folder.iterdir() if ANSWER.match(f.name))
            found.append(Variant(id=folder.name, engine=model, language=language, covered=covered, pieces=pieces))
        return sorted(found, key=lambda v: (v.covered < v.pieces, -v.covered, v.id))

    # sync -------------------------------------------------------------------------------------------------------
    def sync(self) -> SyncResult:
        """Bring every event folder into the database (videos, speakers, fingerprints); keep Martin's names."""
        events = speakers = 0
        for event_dir in sorted(self._events.iterdir()) if self._events.is_dir() else []:
            if not (event_dir / "manifest.json").is_file() or not EVENT_ID.match(event_dir.name):
                continue
            manifest = load_manifest(event_dir)
            src = manifest.source
            self._store.upsert_event(
                event_dir.name, src.title, src.url, src.source_id, src.is_live, manifest.started_at, manifest.audio_ms
            )
            events += 1
            diarization = self._diarization(event_dir)
            centres_file = event_dir / "speakers.npy"
            if diarization is None or not centres_file.exists():
                continue
            centres: Matrix = np.asarray(np.load(centres_file), dtype=np.float32)
            for s in diarization.speakers:
                index = _speaker_index(s.label)
                if index >= len(centres):
                    continue
                self._store.upsert_speaker(
                    event_dir.name, s.label, centres[index].tolist(), diarization.embedder, s.talk_s, s.share
                )
                speakers += 1
        self.refresh_guesses()
        return SyncResult(events=events, speakers=speakers)

    def refresh_guesses(self) -> None:
        """Give every speaker a voice, oldest video first (ADR-012). A speaker that sounds like a known voice (named
        or not, ≥ ACCEPT) joins it; any other founds the next numbered voice from its own samples. Martin's names,
        founders and forgotten speakers are left alone."""
        with self.lock:
            self._refresh_guesses()

    def _refresh_guesses(self) -> None:
        files: dict[str, _VoiceFiles | None] = {}
        for s in self._store.speakers():
            if s.status in ("confirmed", "new") or s.no_profile:
                continue
            d = decide(self._store.neighbours(s))
            if d.status == "auto" and d.person_id is not None:
                self._store.set_guess(s.id, d.person_id, d.score, "auto")
                continue
            if s.event_id not in files:
                files[s.event_id] = self._voice_files(self._events / s.event_id)
            found = files[s.event_id]
            samples = found.samples(s.label, min_windows=CHUNK) if found else None
            if samples is None or len(samples) == 0:
                self._store.set_guess(s.id, None, None, "unknown")  # too little clean speech to found a voice
            else:
                self._store.create_voice(s, samples.tolist(), found.model if found else "")

    def _voice_files(self, event_dir: Path) -> "_VoiceFiles | None":
        diarization = self._diarization(event_dir)
        if diarization is None or not (event_dir / "embeddings.npz").is_file():
            return None
        saved = np.load(event_dir / "embeddings.npz")
        windows: Matrix = normalise(np.asarray(saved["emb"], dtype=np.float32))
        centres: Matrix = np.asarray(np.load(event_dir / "speakers.npy"), dtype=np.float32)
        return _VoiceFiles(windows=windows, centres=centres, model=diarization.embedder)

    # videos -----------------------------------------------------------------------------------------------------
    def events(self) -> list[EventSummary]:
        out: list[EventSummary] = []
        for e in self._store.events():
            path = self._events / e.id
            full = 0
            if (path / "manifest.json").is_file():
                pieces = len(load_manifest(path).pieces)
                full = sum(1 for v in self._variants(path, pieces) if v.covered >= pieces)
            out.append(EventSummary(**e.model_dump(), transcripts=full))
        return out

    def event(self, event_id: str) -> EventDetail:
        path = self._dir(event_id)
        row = self._store.event(event_id)
        manifest = load_manifest(path)
        variants = self._variants(path, len(manifest.pieces))
        return EventDetail(
            **row.model_dump(),
            transcripts=sum(1 for v in variants if v.covered >= v.pieces),
            complete=manifest.complete,
            has_audio=(path / "audio.flac").is_file(),
            variants=variants,
            documents=self.documents(event_id),
        )

    def audio(self, event_id: str) -> Path:
        path = self._dir(event_id) / "audio.flac"
        if not path.is_file():
            raise LektyraError("not_found", "This video has no audio file yet.")
        return path

    def documents(self, event_id: str) -> list[Document]:
        path = self._dir(event_id)
        return [Document(name=f.name, size=f.stat().st_size) for f in sorted(path.glob("*.md"))]

    def document(self, event_id: str, name: str) -> str:
        if name not in {d.name for d in self.documents(event_id)}:
            raise LektyraError("not_found", f"No document {name!r} for this video.")
        return (self._dir(event_id) / name).read_text(encoding="utf-8")

    # speakers ---------------------------------------------------------------------------------------------------
    def speakers(self, event_id: str) -> list[Speaker]:
        self._dir(event_id)
        names = {p.id: p.name for p in self._store.persons()}
        out: list[Speaker] = []
        for s in self._store.speakers(event_id):
            candidates = [
                Candidate(person_id=d.person_id, name=names[d.person_id], score=d.score, status=d.status, votes=d.votes)
                for d in ranked(self._store.neighbours(s))[:CANDIDATES]
                if d.person_id is not None and d.person_id in names
            ]
            out.append(
                Speaker(
                    label=s.label,
                    talk_s=s.talk_s,
                    share=s.share,
                    person_id=s.person_id,
                    person_name=s.person_name,
                    person_number=s.person_number,
                    person_anonymous=s.person_anonymous,
                    status=s.status,
                    score=s.score,
                    candidates=candidates,
                    rejected=self._store.rejected(s.id),
                    no_profile=s.no_profile,
                )
            )
        return out

    def _speaker(self, event_id: str, label: str) -> SpeakerRow:
        self._dir(event_id)
        return self._store.speaker(event_id, label)

    def name_speaker(self, event_id: str, label: str, person_id: int) -> None:
        """Martin says who a speaker is (ADR-004, ADR-012). If the speaker belonged to an unnamed voice, that whole
        voice is this person: it merges into them, so every video it was heard in gets the name. The speaker's clean
        windows become confirmed samples, then everyone unnamed is matched again."""
        with self.lock:
            speaker = self._speaker(event_id, label)
            found = self._voice_files(self._dir(event_id))
            if found is None:
                raise LektyraError("not_found", "This video has no speakers yet: run `lektyra diarize` first.")
            samples = found.samples(label)
            if samples is None:
                raise LektyraError("not_found", f"No fingerprint for {label} in this video.")
            if len(samples) == 0:
                raise LektyraError("conflict", f"{label} has no clean stretch long enough to learn the voice from.")
            if speaker.person_id is not None and speaker.person_id != person_id and speaker.person_anonymous:
                self._store.merge(speaker.person_id, person_id, self._actor)
            self._store.assign(speaker, person_id, samples.tolist(), found.model, self._actor)
            self._refresh_guesses()

    def unname_speaker(self, event_id: str, label: str) -> None:
        with self.lock:
            self._store.unassign(self._speaker(event_id, label), self._actor)
            self._refresh_guesses()

    def reject(self, event_id: str, label: str, person_id: int) -> None:
        """ "Not this person": the candidate never comes back for this speaker."""
        with self.lock:
            speaker = self._speaker(event_id, label)
            if speaker.status == "confirmed" and speaker.person_id == person_id:
                raise LektyraError("conflict", "This speaker is named as that person. Remove the name first.")
            self._store.reject(speaker, person_id, self._actor)
            self._refresh_guesses()

    # persons ----------------------------------------------------------------------------------------------------
    def persons(self) -> list[Person]:
        return [Person(**p.model_dump()) for p in self._store.persons()]

    def save_person(self, person_id: int | None, fields: PersonFields) -> Person:
        new_id = self._store.save_person(person_id, fields, self._actor)
        return Person(**self._store.person(new_id).model_dump())

    def forget_person(self, person_id: int) -> None:
        with self.lock:
            self._store.forget_person(person_id, self._actor)
            self._refresh_guesses()

    # transcripts ------------------------------------------------------------------------------------------------
    def _variant(self, event_id: str, variant: str) -> Path:
        path = self._dir(event_id)
        if variant not in {v.id for v in self._variants(path, len(load_manifest(path).pieces))}:
            raise LektyraError("not_found", f"No transcript {variant!r} for this video.")
        return path

    def transcript(self, event_id: str, variant: str) -> Transcript:
        path = self._variant(event_id, variant)
        diarization = self._diarization(path)
        if diarization is None:
            raise LektyraError("not_found", "This video has no speakers yet: run `lektyra diarize` first.")
        model, language = variant_of(variant)
        items, words, unknown = speaker_utterances(path, model, language, names={})
        return Transcript(
            variant=variant,
            paragraphs=[Paragraph(start_ms=u.start_ms, end_ms=u.end_ms, label=u.label, text=u.text) for u in items],
            turns=[SpeakerTurn(start_ms=t.start_ms, end_ms=t.end_ms, label=t.speaker) for t in diarization.turns],
            words=words,
            unknown_words=unknown,
        )

    def ratings(self, event_id: str) -> list[Rating]:
        self._dir(event_id)
        return [_rating(r) for r in self._store.ratings(event_id)]

    def rate(self, event_id: str, variant: str, accuracy: int | None, names_numbers: int | None, note: str) -> Rating:
        self._variant(event_id, variant)
        self._store.rate(event_id, variant, accuracy, names_numbers, note, self._actor)
        return next(r for r in self.ratings(event_id) if r.variant == variant)

    def flags(self, event_id: str, variant: str) -> list[Flag]:
        self._variant(event_id, variant)
        return [_flag(f) for f in self._store.flags(event_id, variant)]

    def add_flag(self, event_id: str, variant: str, at_ms: int, kind: FlagKind, note: str) -> Flag:
        self._variant(event_id, variant)
        return _flag(self._store.add_flag(event_id, variant, at_ms, kind, note, self._actor))

    def delete_flag(self, event_id: str, flag_id: int) -> None:
        self._dir(event_id)
        self._store.delete_flag(event_id, flag_id)

    # the voice map ----------------------------------------------------------------------------------------------
    def voices(self) -> list[VoicePoint]:
        rows = self._store.voices()
        if not rows:
            return []
        unit = normalise(np.asarray([r.embedding for r in rows], dtype=np.float32))
        flat = project_2d(unit)
        sims = unit @ unit.T
        out: list[VoicePoint] = []
        for i, r in enumerate(rows):
            order = [j for j in np.argsort(-sims[i]).tolist() if j != i][:NEAREST]
            out.append(
                VoicePoint(
                    event_id=r.event_id,
                    event_title=r.event_title,
                    label=r.label,
                    talk_s=r.talk_s,
                    person_id=r.person_id,
                    person_name=r.person_name,
                    person_anonymous=r.person_anonymous,
                    status=r.status,
                    x=round(float(flat[i, 0]), 4),
                    y=round(float(flat[i, 1]), 4),
                    nearest=[
                        NearVoice(
                            event_id=rows[j].event_id, label=rows[j].label, similarity=round(float(sims[i, j]), 3)
                        )
                        for j in order
                    ],
                )
            )
        return out


def _rating(r: RatingRow) -> Rating:
    return Rating(**r.model_dump())


def _flag(f: FlagRow) -> Flag:
    return Flag(id=f.id, variant=f.variant, at_ms=f.at_ms, kind=f.kind, note=f.note)
