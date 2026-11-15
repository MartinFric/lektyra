"""Live sessions (ADR-013, ADR-016): streams heard in real time, several at once, with voices known as they speak.

The same ingest as everywhere (ADR-007) reads the source at live speed and cuts pieces in quiet moments, shorter
than for archives so words arrive sooner. Alongside it:

- **voices now**: every second the last 2 s, if it is speech, is fingerprinted and given to a session speaker
  (`OnlineSpeakers`); a few seconds of speech are enough to say who is speaking;
- **numbers and names**: every few seconds the session writes the files diarization writes (`diarization.json`,
  `speakers.npy`, `embeddings.npz`) and lists its speakers in the database, so each gets a voice number or a name
  exactly as an archive video does (ADR-012), and Martin can name a voice while it speaks;
- **words per piece**: each finished piece goes to speech-to-text in the background (ElevenLabs, ~$0.22 an hour);
- **claims every minute** (K29): once a minute's words are in, the claims loop reads it (spike-plan §8, the same
  loop as `lektyra claims`, ~$1.85 an hour); when the stream ends, one last pass covers the rest.

When the stream ends (or Stop is pressed) the event is an ordinary video: transcript, speakers, names.

Several sessions run side by side (a scheduled TA3 run while STVR is on): each has its own threads and voice model;
their voice updates take turns behind the review's lock, so two sessions never found the same voice twice.
"""

import json
import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

import numpy as np
from pydantic import BaseModel, SecretStr

from lektyra.adapters.media.loopback import LoopbackSource, output_devices
from lektyra.adapters.store.postgres import Store
from lektyra.app.claims import run_claims, run_end_pass
from lektyra.app.ingest import run_ingest
from lektyra.app.review import Review
from lektyra.app.transcribe import model_dir, transcribe_piece
from lektyra.atomic import swap
from lektyra.domain.audio import SAMPLE_RATE, Curve, Samples, ms_to_samples
from lektyra.domain.chunking import CutRule, Piece
from lektyra.domain.claims import MINUTE_MS
from lektyra.domain.diarization import UNCLEAR, Matrix, normalise
from lektyra.domain.diarization import turns as make_turns
from lektyra.domain.live_voices import JOIN, OnlineSpeakers, WindowPlanner
from lektyra.errors import LektyraError
from lektyra.ports import SourceInfo
from lektyra.settings import Settings

log = logging.getLogger("lektyra.live")

LIVE_RULE: Final = CutRule(window_start_ms=20_000, decide_at_ms=30_000, hard_max_ms=40_000)  # words sooner
STT_MODEL: Final = "elevenlabs/scribe-v2"
STT_LANGUAGE: Final = "sk"
LIST_FROM: Final = 8  # windows (~8 s of speech) before a live speaker is listed, numbered and can be named
SAVE_EVERY_MS: Final = 5_000
NOW_MS: Final = 2_500  # a speaker heard this recently is "speaking now"
TAIL_MS: Final = 4_000
RECENT_TURNS: Final = 80
STT_ATTEMPTS: Final = 3
STT_RETRY_S: Final = 3.0
CLAIMS_EVERY_S: Final = 15.0  # how often the claims loop looks for a minute whose words are in
STREAM_PREFIXES: Final = ("https://", "http://", "ta3:", "stvr:", "pc:sound")
UPLOAD_PREFIX: Final = "upload:"  # a video uploaded to lektyra's MinIO, played as live
MAX_SESSIONS: Final = 4  # at once; each one fingerprints a window every second
KEEP_ENDED: Final = 12  # ended sessions still shown, newest first
MEDIA_TYPES: Final = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
}

LiveStatus = Literal["loading", "running", "stopping", "finished", "failed"]
Embed = Callable[[list[Samples]], Matrix]
MakeEmbedder = Callable[[], tuple[Embed, str]]


class LiveSpeaker(BaseModel):
    label: str
    windows: int
    talk_s: float
    last_ms: int
    listed: bool  # heard long enough to have a voice number and to be named


class LiveTurn(BaseModel):
    start_ms: int
    end_ms: int
    label: str


class LiveDevices(BaseModel):
    devices: list[str]
    default: str | None


class LiveState(BaseModel):
    id: str
    status: LiveStatus
    message: str
    source: str
    title: str | None
    event_id: str | None
    is_live: bool | None
    duration_s: float | None
    media: bool  # a local file the UI can play next to the session
    started_at: datetime
    position_ms: int
    current: str | None
    speakers: list[LiveSpeaker]
    turns: list[LiveTurn]
    pieces: int
    transcribe: bool
    transcribed: int
    stt_errors: int
    variant: str | None
    cost_usd: float
    claims: int = 0  # open claims so far
    claims_minutes: int = 0  # minutes the claims loop has read
    claims_error: str | None = None


def label_of(speaker: int) -> str:
    return "?" if speaker == UNCLEAR else f"S{speaker + 1}"


def ecapa(settings: Settings) -> MakeEmbedder:
    def make() -> tuple[Embed, str]:
        from lektyra.adapters.embed.speechbrain_ecapa import EcapaEmbedder

        embedder = EcapaEmbedder(settings.data_dir / "models")
        return embedder.embed, EcapaEmbedder.name

    return make


class LiveSession:
    def __init__(
        self, *, settings: Settings, store: Store, review: Review, source: str, title: str | None,
        media_path: Path | None, transcribe: bool, api_key: SecretStr | None, make_embedder: MakeEmbedder,
        shown_source: str | None = None,
    ) -> None:  # fmt: skip
        self.id = uuid.uuid4().hex[:12]
        self._shown_source = shown_source or source  # what Martin picked (upload:…), not the cache path
        self._settings = settings
        self._store = store
        self._review = review
        self._source = source
        self._title = title
        self.media_path = media_path
        self._transcribe = transcribe
        self._api_key = api_key
        self._make_embedder = make_embedder
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._status: LiveStatus = "loading"
        self._message = "Loading the voice model…"
        self._started = datetime.now().astimezone()
        self._info: SourceInfo | None = None
        self._event_dir: Path | None = None
        self._embed: Embed | None = None
        self._model = ""
        self._planner = WindowPlanner()
        self._tracker = OnlineSpeakers()
        self._wins: list[tuple[int, int, int]] = []
        self._embs: list[np.ndarray] = []
        self._region = 0
        self._tail: Samples = np.zeros(0, dtype=np.int16)
        self._position = 0
        self._saved_at = 0
        self._turns: list[LiveTurn] = []
        self._talk: dict[int, float] = {}
        self._pieces = 0
        self._transcribed = 0
        self._stt_errors = 0
        self._cost = 0.0
        self._queue: queue.Queue[Piece | None] = queue.Queue()
        self._words_ms = 0  # the words are in up to here (pieces are transcribed in order)
        self._words_done = threading.Event()
        self._claims = 0
        self._claims_minutes = 0
        self._claims_error: str | None = None

    # control ----------------------------------------------------------------------------------------------------
    def start(self) -> None:
        threading.Thread(target=self._run, name=f"lektyra-live-{self.id}", daemon=True).start()

    def stop(self) -> None:
        with self._lock:
            if self._status in ("loading", "running"):
                self._status = "stopping"
                self._message = "Stopping: the last piece is being written…"
        self._stop.set()

    @property
    def active(self) -> bool:
        return self._status in ("loading", "running", "stopping")

    # the thread -------------------------------------------------------------------------------------------------
    def _run(self) -> None:
        worker: threading.Thread | None = None
        claims: threading.Thread | None = None
        try:
            self._embed, self._model = self._make_embedder()
            if self._transcribe:
                worker = threading.Thread(target=self._stt_loop, name=f"lektyra-stt-{self.id}", daemon=True)
                worker.start()
                claims = threading.Thread(target=self._claims_loop, name=f"lektyra-claims-{self.id}", daemon=True)
                claims.start()
            with self._lock:
                if self._status == "loading":
                    self._message = "Opening the source…"
            run_ingest(
                self._source,
                title=self._title,
                realtime=True,
                max_minutes=None,
                settings=self._settings,
                on_start=self._started_at,
                on_audio=self._audio,
                on_piece=self._piece,
                should_stop=self._stop.is_set,
                rule=LIVE_RULE,
                source=LoopbackSource() if self._source.startswith("pc:sound") else None,
            )
            self._save()
            if worker:
                with self._lock:
                    self._message = "Writing the last words…"
                self._queue.put(None)
                worker.join()
            self._words_done.set()
            if claims:
                with self._lock:
                    self._message = "Writing the last claims…"
                claims.join()
            with self._lock:
                self._status = "finished"
                self._message = "Finished. The video is in Videos with its speakers and transcript."
        except Exception as error:  # the session must end in a state the UI can show, whatever failed
            log.error("live session failed", exc_info=error)
            self._words_done.set()
            if worker:
                self._queue.put(None)
            with self._lock:
                self._status = "failed"
                self._message = (
                    f"The session stopped: {str(error).splitlines()[0][:300] if str(error) else type(error).__name__}"
                )

    def _started_at(self, event_dir: Path, info: SourceInfo) -> None:
        with self._lock:
            self._event_dir = event_dir
            self._info = info
            if self._status == "loading":
                self._status = "running"
                self._message = "Listening."
        self._store.upsert_event(event_dir.name, info.title, info.url, info.source_id, info.is_live, self._started, 0)

    def _audio(self, samples: Samples, probs: Curve, at_ms: int) -> None:
        embed = self._embed
        if embed is None:
            return
        keep = ms_to_samples(TAIL_MS)
        tail = np.concatenate([self._tail, samples])[-keep:]
        end_ms = at_ms + len(samples) * 1000 // SAMPLE_RATE
        due = self._planner.feed(probs)
        clips: list[tuple[int, int, Samples]] = []
        for a, b in due:
            first = len(tail) - ms_to_samples(end_ms - a)
            last = len(tail) - ms_to_samples(end_ms - b)
            if first >= 0 and last <= len(tail):
                clips.append((a, b, tail[first:last]))
        vectors = embed([c for _, _, c in clips]) if clips else np.zeros((0, 0), dtype=np.float32)
        with self._lock:
            self._tail = tail
            self._position = end_ms
            for (a, b, _), v in zip(clips, vectors, strict=True):
                if self._wins and a > self._wins[-1][1]:
                    self._region += 1
                self._wins.append((a, b, self._region))
                self._embs.append(np.asarray(v, dtype=np.float32))
                self._tracker.add(np.asarray(v, dtype=np.float32))
        if end_ms - self._saved_at >= SAVE_EVERY_MS:
            try:
                self._save()
            except OSError as err:  # a save that fails is written again by the next one: never end the session
                log.warning("voices not saved this time (%s); the next save writes them", err)

    def _piece(self, piece: Piece) -> None:
        with self._lock:
            self._pieces += 1
        if self._transcribe:
            self._queue.put(piece)

    def _stt_loop(self) -> None:
        while (piece := self._queue.get()) is not None:
            event_dir, key = self._event_dir, self._api_key
            if event_dir is None or key is None:
                continue
            done = False
            for attempt in range(STT_ATTEMPTS):  # a piece that fails is tried again before its minute moves on
                try:
                    record = transcribe_piece(event_dir, STT_MODEL, piece, api_key=key, language=STT_LANGUAGE)
                    if record.error is None:
                        with self._lock:
                            self._transcribed += 1
                            self._cost += record.cost_usd or 0.0
                        done = True
                        break
                    log.warning("speech-to-text failed for piece %s: %s", piece.index, record.error)
                except Exception as error:  # one failed piece must not stop the words of the next ones
                    log.warning("speech-to-text failed for piece %s: %s", piece.index, type(error).__name__)
                if attempt + 1 < STT_ATTEMPTS:
                    time.sleep(STT_RETRY_S * (attempt + 1))
            if not done:
                with self._lock:
                    self._stt_errors += 1  # a hole in the words; the state shows how many
            with self._lock:
                self._words_ms = max(self._words_ms, piece.end_ms)

    def _claims_loop(self) -> None:
        """Claims for every minute whose words are in, then one last pass when the words are done. A failure never
        stops the session: it shows in the state and the next round tries again."""
        while not self._words_done.wait(CLAIMS_EVERY_S):
            with self._lock:
                due = self._words_ms // MINUTE_MS
            if due > self._claims_minutes:
                self._claims_up_to(due)
        if self._event_dir is not None and self._words_ms > 0:
            self._claims_up_to(None)
            self._end_pass()

    def _roles(self) -> dict[str, str]:
        """The voice labels lektyra recognises now, as the claims loop should read them: "Braňo Kráľ (host)"."""
        event_dir = self._event_dir
        if event_dir is None:
            return {}
        return speaker_roles(self._store, event_dir.name)

    def _end_pass(self) -> None:
        """The whole-picture pass once the show is over: what live missed, links, duplicates (~$0.15 an hour)."""
        event_dir, key = self._event_dir, self._api_key
        if event_dir is None or key is None:
            return
        with self._lock:
            if self._status != "failed":  # a failure's message stays: the scheduler quotes it (review, point 7)
                self._message = "Reviewing all claims once more…"
        try:
            run_end_pass(
                event_dir, api_key=key, llm=self._settings.claims_model, engine=STT_MODEL, language=STT_LANGUAGE,
                roles=self._roles(),
            )  # fmt: skip
        except Exception as error:  # the live ledger stays; the end pass can be run by hand (lektyra end-pass)
            log.warning("end pass failed: %s", error)

    def _claims_up_to(self, minute: int | None) -> None:
        event_dir, key = self._event_dir, self._api_key
        if event_dir is None or key is None:
            return
        try:
            result = run_claims(
                event_dir, api_key=key, llm=self._settings.claims_model, engine=STT_MODEL, language=STT_LANGUAGE,
                until_minute=minute, roles=self._roles(),
            )  # fmt: skip
            with self._lock:
                self._claims = sum(1 for c in result.ledger.claims if c.status == "open")
                self._claims_minutes = minute if minute is not None else result.ledger.minute
                self._claims_error = None
        except Exception as error:  # the session goes on; the next round tries again
            log.warning("claims failed: %s", error)
            with self._lock:
                self._claims_error = str(error).splitlines()[0][:200] if str(error) else type(error).__name__

    # what the review sees ---------------------------------------------------------------------------------------
    def _save(self) -> None:
        """Write what diarization writes, list the speakers heard long enough, and let matching number or name
        them (ADR-012). Files are replaced whole, so a reader never sees half of one."""
        event_dir = self._event_dir
        if event_dir is None:
            return
        with self._lock:
            self._saved_at = self._position
            wins = list(self._wins)
            embs = list(self._embs)
            labels = np.asarray(self._tracker.labels, dtype=np.int64)
            count = self._tracker.count
            centres = [self._tracker.centroid(i) for i in range(count)]
            sizes = [self._tracker.windows_of(i) for i in range(count)]
            position = self._position
        if not wins or count == 0:
            return
        listed = {i for i in range(count) if sizes[i] >= LIST_FROM}
        shown = np.asarray([s if s in listed else UNCLEAR for s in labels.tolist()], dtype=np.int64)
        found = make_turns(wins, shown)
        talk: dict[int, float] = {}
        for t in found:
            talk[t.speaker] = talk.get(t.speaker, 0.0) + (t.end_ms - t.start_ms) / 1000
        total = sum(talk.values()) or 1.0
        speakers = [
            {"label": label_of(i), "talk_s": round(talk.get(i, 0.0), 1), "share": round(talk.get(i, 0.0) / total, 3),
             "turns": sum(1 for t in found if t.speaker == i)}
            for i in sorted(listed)
        ]  # fmt: skip
        diarization = {
            "embedder": self._model,
            "threshold": JOIN,
            "windows": len(wins),
            "live": True,
            "speakers": speakers,
            "unclear_s": round(talk.get(UNCLEAR, 0.0), 1),
            "turns": [{"start_ms": t.start_ms, "end_ms": t.end_ms, "speaker": label_of(t.speaker)} for t in found],
        }
        matrix: Matrix = normalise(np.stack(embs).astype(np.float32))
        _replace_json(event_dir / "diarization.json", diarization)
        _replace_npy(event_dir / "speakers.npy", np.stack(centres).astype(np.float32))
        _replace_npz(event_dir / "embeddings.npz", np.asarray(wins, dtype=np.int64), matrix)
        with self._lock:
            self._turns = [LiveTurn(start_ms=t.start_ms, end_ms=t.end_ms, label=label_of(t.speaker)) for t in found]
            self._talk = talk
        with self._review.exclusive():
            self._store.upsert_event(
                event_dir.name,
                self._info.title if self._info else event_dir.name,
                self._info.url if self._info else self._source,
                self._info.source_id if self._info else None,
                self._info.is_live if self._info else False,
                self._started,
                position,
            )
            for s in speakers:
                index = int(str(s["label"])[1:]) - 1
                self._store.upsert_speaker(
                    event_dir.name, str(s["label"]), centres[index].tolist(), self._model,
                    float(str(s["talk_s"])), float(str(s["share"])),
                )  # fmt: skip
            self._review.refresh_guesses()

    def snapshot(self) -> LiveState:
        with self._lock:
            labels = self._tracker.labels
            last_heard: dict[int, int] = {}
            for (_, b, _), s in zip(self._wins, labels, strict=False):
                if s != UNCLEAR:
                    last_heard[s] = b
            current: str | None = None
            if self._wins and labels and labels[-1] != UNCLEAR and self._wins[-1][1] >= self._position - NOW_MS:
                current = label_of(labels[-1])
            speakers = [
                LiveSpeaker(
                    label=label_of(i),
                    windows=self._tracker.windows_of(i),
                    talk_s=round(self._talk.get(i, float(self._tracker.windows_of(i))), 1),
                    last_ms=last_heard.get(i, 0),
                    listed=self._tracker.windows_of(i) >= LIST_FROM,
                )
                for i in range(self._tracker.count)
            ]
            info = self._info
            return LiveState(
                id=self.id,
                status=self._status,
                message=self._message,
                source=self._shown_source,
                title=info.title if info else self._title,
                event_id=self._event_dir.name if self._event_dir else None,
                is_live=info.is_live if info else None,
                duration_s=info.duration_s if info else None,
                media=self.media_path is not None,
                started_at=self._started,
                position_ms=self._position,
                current=current,
                speakers=speakers,
                turns=self._turns[-RECENT_TURNS:],
                pieces=self._pieces,
                transcribe=self._transcribe,
                transcribed=self._transcribed,
                stt_errors=self._stt_errors,
                variant=model_dir(STT_MODEL, STT_LANGUAGE) if self._transcribe and self._transcribed else None,
                cost_usd=round(self._cost, 4),
                claims=self._claims,
                claims_minutes=self._claims_minutes,
                claims_error=self._claims_error,
            )


def _replace_json(path: Path, value: object) -> None:
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(value, indent=1), encoding="utf-8")
    swap(tmp, path)


def _replace_npy(path: Path, value: Matrix) -> None:
    tmp = path.with_name(path.stem + ".part.npy")
    np.save(tmp, value)
    swap(tmp, path)


def _replace_npz(path: Path, windows: np.ndarray, emb: Matrix) -> None:
    tmp = path.with_name(path.stem + ".part.npz")
    np.savez(tmp, windows=windows, emb=emb)
    swap(tmp, path)


SOURCES_HINT: Final = (
    "Pick a live channel (ta3:live, stvr:1, stvr:2), a YouTube or Facebook address, PC sound or an uploaded video."
)


def check_source(source: str) -> None:
    """Only what a session can open: a live channel, an address, PC sound or an upload; never a path on this PC."""
    if not (source.startswith(STREAM_PREFIXES) or source.startswith(UPLOAD_PREFIX)):
        raise LektyraError("invalid", SOURCES_HINT)
    if source.startswith("stvr:") and source not in ("stvr:1", "stvr:2"):
        raise LektyraError("invalid", "STVR live is stvr:1 (Jednotka) or stvr:2 (Dvojka).")


def speaker_roles(store: Store, event_id: str) -> dict[str, str]:
    """Who each named speaker of a video is, with what they are on air (K60): {"S1": "Braňo Kráľ (host)"}."""
    persons = {p.id: p for p in store.persons()}
    roles: dict[str, str] = {}
    for s in store.speakers(event_id):
        person = persons.get(s.person_id) if s.person_id is not None else None
        known = person is not None and (not person.anonymous or person.kind in ("host", "audience"))
        if person is not None and known and s.status in ("confirmed", "auto", "new"):
            roles[s.label] = f"{person.name} ({person.kind})"
    return roles


def media_type(path: Path) -> str:
    return MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


ResolveUpload = Callable[[str], Path]


class LiveManager:
    """The live sessions of this UI server: up to MAX_SESSIONS at once, each with an id."""

    def __init__(
        self,
        settings: Settings,
        store: Store,
        review: Review,
        make_embedder: MakeEmbedder,
        resolve_upload: ResolveUpload | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._review = review
        self._make_embedder = make_embedder
        self._resolve_upload = resolve_upload
        self._sessions: dict[str, LiveSession] = {}
        self._lock = threading.Lock()

    def devices(self) -> LiveDevices:
        """The PC's sound outputs a session can listen to (`pc:sound:<name>`, K28)."""
        names, default = output_devices()
        return LiveDevices(devices=names, default=default)

    def start(self, source: str, title: str | None, transcribe: bool) -> LiveState:
        check_source(source)
        media: Path | None = None
        target = source
        if source.startswith(UPLOAD_PREFIX):
            if self._resolve_upload is None:
                raise LektyraError("unavailable", "Uploaded videos are not available in this server.")
            media = self._resolve_upload(source.removeprefix(UPLOAD_PREFIX))  # a local copy, fetched if needed
            target = str(media)
        key = self._settings.openrouter_api_key
        if transcribe and key is None:
            raise LektyraError("invalid", "No OpenRouter key in ~/.secrets/lektyra.env: start without transcription.")
        with self._lock:
            running = [s for s in self._sessions.values() if s.active]
            if len(running) >= MAX_SESSIONS:
                raise LektyraError("conflict", f"{MAX_SESSIONS} sessions are running already. Stop one first.")
            if source.startswith("pc:sound") and any(s.snapshot().source.startswith("pc:sound") for s in running):
                raise LektyraError("conflict", "PC sound is being listened to already: one session per sound output.")
            session = LiveSession(
                settings=self._settings, store=self._store, review=self._review, source=target, title=title,
                media_path=media, transcribe=transcribe, api_key=key, make_embedder=self._make_embedder,
                shown_source=source,
            )  # fmt: skip
            self._sessions[session.id] = session
            ended = [s for s in self._sessions.values() if not s.active]
            for old in ended[: max(0, len(ended) - KEEP_ENDED)]:
                del self._sessions[old.id]
        session.start()
        return session.snapshot()

    def _session(self, session_id: str) -> LiveSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise LektyraError("not_found", "No such live session. lektyra may have been restarted.")
        return session

    def stop(self, session_id: str) -> LiveState:
        session = self._session(session_id)
        if not session.active:
            raise LektyraError("conflict", "This session is not running.")
        session.stop()
        return session.snapshot()

    def state(self, session_id: str) -> LiveState | None:
        session = self._sessions.get(session_id)
        return session.snapshot() if session else None

    def sessions(self) -> list[LiveState]:
        """Running sessions first, then ended ones; newest first within each."""
        states = [s.snapshot() for s in list(self._sessions.values())]
        return sorted(
            states, key=lambda s: (s.status not in ("loading", "running", "stopping"), -s.started_at.timestamp())
        )

    def uses(self, source: str) -> bool:
        """Is a running session reading this source (an upload about to be deleted)?"""
        return any(s.active and s.snapshot().source == source for s in list(self._sessions.values()))

    def media(self, session_id: str) -> tuple[Path, str]:
        session = self._session(session_id)
        if session.media_path is None:
            raise LektyraError("not_found", "This session has no local file to play.")
        return session.media_path, media_type(session.media_path)
