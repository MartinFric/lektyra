"""Ingest: any source → PCM stream → speech probability + energy → cuts → FLAC pieces (ADR-006, ADR-007).

The same loop serves a live stream and a stored video. Pieces are written the moment they are cut, and the manifest
is rewritten after each one, so a live run shows progress and survives a crash.

- **Ctrl+C** ends a run cleanly: the audio heard so far becomes the last piece.
- **A live stream that drops** is opened again (fresh address and token, backing off) up to `MAX_RECONNECTS` times.
  Each gap is recorded in the manifest; the stream time continues where the audio left off.
- **A stored video that ends early** is marked `complete: false` with how much was heard.
- **What ffmpeg and yt-dlp say** goes to `ffmpeg.log` in the event folder, not to the console.
"""

import contextlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from lektyra.adapters.media.ffmpeg_ytdlp import FfmpegYtdlpSource, FlacWriter
from lektyra.adapters.media.stvr import StvrResolver
from lektyra.adapters.media.ta3 import Ta3Resolver
from lektyra.adapters.vad.silero_onnx import SileroVad, ensure_model
from lektyra.domain.audio import (
    BYTES_PER_MS,
    FRAME_BYTES,
    FRAME_MS,
    Curve,
    Samples,
    frame_energy_db,
    samples_from_bytes,
)
from lektyra.domain.chunking import DEFAULT_RULE, CutPlanner, CutRule, Piece, PieceEnd, piece_after
from lektyra.domain.naming import event_id
from lektyra.ports import MediaSource, PcmSink, SourceInfo, SpeechDetector
from lektyra.settings import Settings

READ_FRAMES: Final = 31  # read ~1 s at a time
MAX_RECONNECTS: Final = 20
BACKOFF_S: Final = (2.0, 4.0, 8.0, 15.0, 30.0)
COMPLETE_TOLERANCE_MS: Final = 2_000  # a stored video counts as complete within 2 s of its stated length
# What ffmpeg says when an HLS server answers after the last segment (TA3 every time): harmless once the audio is
# complete, so it is not counted as a problem then.
BENIGN_WHEN_COMPLETE: Final = re.compile(r"Error during demuxing: I/O error")

StopReason = Literal["end", "max", "interrupted", "dropped"]


class Gap(BaseModel):
    """A live stream dropped at stream time `at_ms` and came back after `wall_s` seconds (attempt `attempt`)."""

    model_config = ConfigDict(frozen=True)

    at_ms: int
    wall_s: float
    attempt: int


class SavedSource(BaseModel):
    """The source as saved: everything but `media_url`, which may carry a token (ADR-005)."""

    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    is_live: bool
    duration_s: float | None = None
    resolved_by: str
    source_id: str | None = None

    @classmethod
    def of(cls, info: SourceInfo) -> "SavedSource":
        return cls(
            url=info.url,
            title=info.title,
            is_live=info.is_live,
            duration_s=info.duration_s,
            resolved_by=info.resolved_by,
            source_id=info.source_id,
        )


class Manifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: str
    started_at: datetime
    source: SavedSource
    rule: CutRule
    audio_ms: int
    finished: bool
    stopped: StopReason | None = None
    complete: bool | None = None  # stored videos only: was all of it heard?
    gaps: list[Gap] = []
    pieces: list[Piece]


@dataclass(frozen=True)
class IngestResult:
    event_dir: Path
    audio_s: float
    pieces: list[Piece]
    stopped: StopReason
    complete: bool | None
    gaps: list[Gap]
    log_lines: int


class _PieceCutter:
    """Holds the audio since (last cut - overlap) and writes a piece when the planner cuts."""

    def __init__(self, sink: Callable[[Path], PcmSink], pieces_dir: Path, rule: CutRule) -> None:
        self._sink = sink
        self._dir = pieces_dir
        self._rule = rule
        self._buffer = bytearray()
        self._buffer_start_ms = 0
        self._last_cut_ms = 0
        self.pieces: list[Piece] = []

    def append(self, pcm: bytes) -> None:
        self._buffer += pcm

    def cut(self, at_ms: int, kind: PieceEnd, quiet_ms: int) -> Piece:
        piece = piece_after(self._last_cut_ms, len(self.pieces), at_ms, kind, quiet_ms, self._rule.overlap_ms)
        a = (piece.start_ms - self._buffer_start_ms) * BYTES_PER_MS
        b = (piece.end_ms - self._buffer_start_ms) * BYTES_PER_MS
        with self._sink(self._dir / f"{piece.index:04d}.flac") as out:
            out.write(bytes(self._buffer[a:b]))
        self.pieces.append(piece)
        self._last_cut_ms = at_ms
        keep_from_ms = max(0, at_ms - self._rule.overlap_ms)
        del self._buffer[: (keep_from_ms - self._buffer_start_ms) * BYTES_PER_MS]
        self._buffer_start_ms = keep_from_ms
        return piece

    @property
    def last_cut_ms(self) -> int:
        return self._last_cut_ms


def default_source(settings: Settings) -> FfmpegYtdlpSource:
    return FfmpegYtdlpSource(
        settings.ffmpeg, settings.ffprobe, settings.ytdlp, resolvers=[Ta3Resolver(settings.ffprobe), StvrResolver()]
    )


def run_ingest(
    url: str,
    *,
    title: str | None,
    realtime: bool,
    max_minutes: float | None,
    settings: Settings,
    on_piece: Callable[[Piece], None] = lambda _piece: None,
    on_gap: Callable[[Gap], None] = lambda _gap: None,
    on_start: Callable[[Path, SourceInfo], None] = lambda _dir, _info: None,
    on_audio: Callable[[Samples, Curve, int], None] = lambda _samples, _probs, _at_ms: None,
    should_stop: Callable[[], bool] = lambda: False,
    rule: CutRule = DEFAULT_RULE,
    now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
    source: MediaSource | None = None,
    detector: SpeechDetector | None = None,
    sink: Callable[[Path], PcmSink] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> IngestResult:
    media = source or default_source(settings)
    make_sink: Callable[[Path], PcmSink] = sink or (lambda path: FlacWriter(settings.ffmpeg, path))
    info = media.resolve(url)
    if title:
        info = info.model_copy(update={"title": title})
    started = now()
    name = event_id(info.title, started)
    event_dir = settings.data_dir / "events" / name
    pieces_dir = event_dir / "pieces"
    pieces_dir.mkdir(parents=True, exist_ok=True)

    vad = detector or SileroVad(ensure_model(settings.data_dir / "models"))
    vad.reset()
    planner = CutPlanner(rule)
    cutter = _PieceCutter(make_sink, pieces_dir, rule)
    max_frames = None if max_minutes is None else int(max_minutes * 60_000) // FRAME_MS
    heard_frames = 0
    pending = bytearray()
    gaps: list[Gap] = []
    stopped: StopReason | None = None
    complete: bool | None = None

    def save(finished: bool) -> None:
        manifest = Manifest(
            event=name,
            started_at=started,
            source=SavedSource.of(info),
            rule=rule,
            audio_ms=heard_frames * FRAME_MS,
            finished=finished,
            stopped=stopped,
            complete=complete,
            gaps=gaps,
            pieces=cutter.pieces,
        )
        tmp = event_dir / "manifest.json.part"
        tmp.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(event_dir / "manifest.json")

    log_path = event_dir / "ffmpeg.log"
    save(finished=False)
    on_start(event_dir, info)
    with log_path.open("ab") as log, make_sink(event_dir / "audio.flac") as full:
        try:
            attempt = 0
            while stopped is None:
                with media.open(info, realtime=realtime, log=log) as stream:
                    for chunk in stream.chunks(FRAME_BYTES * READ_FRAMES):
                        pending += chunk
                        whole = len(pending) - len(pending) % FRAME_BYTES
                        if whole == 0:
                            continue
                        block = bytes(pending[:whole])
                        del pending[:whole]
                        full.write(block)
                        cutter.append(block)
                        samples = samples_from_bytes(block)
                        probs = vad.probabilities(samples)
                        on_audio(samples, probs, heard_frames * FRAME_MS)
                        for cut in planner.feed(probs, frame_energy_db(samples)):
                            on_piece(cutter.cut(cut.at_ms, cut.kind, cut.quiet_ms))
                            save(finished=False)
                        heard_frames += len(block) // FRAME_BYTES
                        attempt = 0  # audio flows again: the next drop starts the backoff afresh
                        if max_frames is not None and heard_frames >= max_frames:
                            stopped = "max"
                            break
                        if should_stop():
                            stopped = "interrupted"
                            break
                if stopped is not None:
                    break
                if not info.is_live:
                    stopped = "end"
                    break
                attempt += 1
                if attempt > MAX_RECONNECTS:
                    stopped = "dropped"
                    break
                pending.clear()  # a partial frame from before the drop does not belong to what comes next
                lost_from = time.monotonic()
                sleep(BACKOFF_S[min(attempt - 1, len(BACKOFF_S) - 1)])
                with contextlib.suppress(RuntimeError):  # keep the old address if resolving fails right now
                    info = media.resolve(info.url).model_copy(update={"title": info.title})
                gap = Gap(at_ms=heard_frames * FRAME_MS, wall_s=round(time.monotonic() - lost_from, 1), attempt=attempt)
                gaps.append(gap)
                on_gap(gap)
                save(finished=False)
        except KeyboardInterrupt:
            stopped = "interrupted"
        end_ms = heard_frames * FRAME_MS
        if end_ms > cutter.last_cut_ms:
            on_piece(cutter.cut(end_ms, "end", 0))
    if not info.is_live and info.duration_s is not None and stopped == "end":
        complete = end_ms >= info.duration_s * 1000 - COMPLETE_TOLERANCE_MS
    save(finished=True)
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines() if log_path.exists() else []
    if complete:
        lines = [line for line in lines if not BENIGN_WHEN_COMPLETE.search(line)]
    log_lines = len(lines)
    return IngestResult(
        event_dir=event_dir,
        audio_s=end_ms / 1000,
        pieces=cutter.pieces,
        stopped=stopped,
        complete=complete,
        gaps=gaps,
        log_lines=log_lines,
    )


def load_manifest(event_dir: Path) -> Manifest:
    return Manifest.model_validate_json((event_dir / "manifest.json").read_text(encoding="utf-8"))
