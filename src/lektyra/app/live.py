"""A live session (ADR-013): one stream at a time, heard in real time, with voices known as they speak.

The same ingest as everywhere (ADR-007) reads the source at live speed and cuts pieces in quiet moments, shorter
than for archives so words arrive sooner. Alongside it:

- **voices now**: every second the last 2 s, if it is speech, is fingerprinted and given to a session speaker
  (`OnlineSpeakers`); a few seconds of speech are enough to say who is speaking;
- **numbers and names**: every few seconds the session writes the files diarization writes (`diarization.json`,
  `speakers.npy`, `embeddings.npz`) and lists its speakers in the database, so each gets a voice number or a name
  exactly as an archive video does (ADR-012), and Martin can name a voice while it speaks;
- **words per piece**: each finished piece goes to speech-to-text in the background (ElevenLabs, ~$0.22 an hour).

When the stream ends (or Stop is pressed) the event is an ordinary video: transcript, speakers, names.
"""

import json
import logging
import queue
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

import numpy as np
from pydantic import BaseModel, SecretStr

from lektyra.adapters.store.postgres import Store
from lektyra.app.ingest import run_ingest
from lektyra.app.review import Review
from lektyra.app.transcribe import model_dir, transcribe_piece
from lektyra.domain.audio import SAMPLE_RATE, Curve, Samples, ms_to_samples
from lektyra.domain.chunking import CutRule, Piece
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
STREAM_PREFIXES: Final = ("https://", "http://", "ta3:", "stvr:")
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


class LiveSource(BaseModel):
    name: str
    size: int
    kind: Literal["video", "audio"]


class LiveState(BaseModel):
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
    ) -> None:  # fmt: skip
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

    # control ----------------------------------------------------------------------------------------------------
    def start(self) -> None:
        threading.Thread(target=self._run, name="lektyra-live", daemon=True).start()

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
        try:
            self._embed, self._model = self._make_embedder()
            if self._transcribe:
                worker = threading.Thread(target=self._stt_loop, name="lektyra-live-stt", daemon=True)
                worker.start()
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
            )
            self._save()
            if worker:
                with self._lock:
                    self._message = "Writing the last words…"
                self._queue.put(None)
                worker.join()
            with self._lock:
                self._status = "finished"
                self._message = "Finished. The video is in Videos with its speakers and transcript."
        except Exception as error:  # the session must end in a state the UI can show, whatever failed
            log.error("live session failed", exc_info=error)
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
            self._save()

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
            try:
                record = transcribe_piece(event_dir, STT_MODEL, piece, api_key=key, language=STT_LANGUAGE)
                with self._lock:
                    if record.error is None:
                        self._transcribed += 1
                        self._cost += record.cost_usd or 0.0
                    else:
                        self._stt_errors += 1
            except Exception as error:  # one failed piece must not stop the words of the next ones
                log.warning("speech-to-text failed for piece %s: %s", piece.index, type(error).__name__)
                with self._lock:
                    self._stt_errors += 1

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
        with self._review.lock:
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
                status=self._status,
                message=self._message,
                source=self._source,
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
            )


def _replace_json(path: Path, value: object) -> None:
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(value, indent=1), encoding="utf-8")
    tmp.replace(path)


def _replace_npy(path: Path, value: Matrix) -> None:
    tmp = path.with_name(path.stem + ".part.npy")
    np.save(tmp, value)
    tmp.replace(path)


def _replace_npz(path: Path, windows: np.ndarray, emb: Matrix) -> None:
    tmp = path.with_name(path.stem + ".part.npz")
    np.savez(tmp, windows=windows, emb=emb)
    tmp.replace(path)


def _playable(path: Path) -> bool:
    """A finished media file; downloads in progress (`.part`) are not offered."""
    return path.is_file() and path.suffix.lower() in MEDIA_TYPES and ".part" not in path.name


def _kind(path: Path) -> Literal["video", "audio"]:
    return "video" if path.suffix.lower() in (".mp4", ".webm") else "audio"


class LiveManager:
    """One live session at a time, owned by the UI server."""

    def __init__(self, settings: Settings, store: Store, review: Review, make_embedder: MakeEmbedder) -> None:
        self._settings = settings
        self._store = store
        self._review = review
        self._make_embedder = make_embedder
        self._session: LiveSession | None = None
        self._lock = threading.Lock()

    @property
    def videos_dir(self) -> Path:
        return self._settings.data_dir / "videos"

    def sources(self) -> list[LiveSource]:
        """Files in data/videos/ the UI can play next to a session (`lektyra fetch` puts them there)."""
        folder = self.videos_dir
        files = [f for f in folder.iterdir() if _playable(f)] if folder.is_dir() else []
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return [LiveSource(name=f.name, size=f.stat().st_size, kind=_kind(f)) for f in files]

    def start(self, source: str, title: str | None, transcribe: bool) -> LiveState:
        with self._lock:
            if self._session is not None and self._session.active:
                raise LektyraError("conflict", "A live session is already running. Stop it first.")
            media: Path | None = None
            names = {s.name for s in self.sources()}
            if source in names:
                media = self.videos_dir / source
                target = str(media)
            elif source.startswith(STREAM_PREFIXES):
                target = source
            else:
                raise LektyraError(
                    "invalid", "Pick a file from data/videos or give a stream address (ta3:live, stvr:1, https://…)."
                )
            key = self._settings.openrouter_api_key
            if transcribe and key is None:
                raise LektyraError(
                    "invalid", "No OpenRouter key in ~/.secrets/lektyra.env: start without transcription."
                )
            session = LiveSession(
                settings=self._settings, store=self._store, review=self._review, source=target, title=title,
                media_path=media, transcribe=transcribe, api_key=key, make_embedder=self._make_embedder,
            )  # fmt: skip
            self._session = session
            session.start()
            return session.snapshot()

    def stop(self) -> LiveState:
        session = self._session
        if session is None or not session.active:
            raise LektyraError("conflict", "No live session is running.")
        session.stop()
        return session.snapshot()

    def state(self) -> LiveState | None:
        return self._session.snapshot() if self._session else None

    def media(self) -> tuple[Path, str]:
        session = self._session
        if session is None or session.media_path is None:
            raise LektyraError("not_found", "This session has no local file to play.")
        return session.media_path, MEDIA_TYPES.get(session.media_path.suffix.lower(), "application/octet-stream")
