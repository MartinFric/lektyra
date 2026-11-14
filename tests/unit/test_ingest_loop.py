"""The ingest loop with fakes: live reconnects, completeness, Ctrl+C-free stops (ADR-007). No ffmpeg, no network."""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import IO, ClassVar, Self

import numpy as np

from lektyra.app.ingest import MAX_RECONNECTS, IngestResult, load_manifest, run_ingest
from lektyra.domain.audio import FRAME_SAMPLES, SAMPLE_RATE, Curve, Samples
from lektyra.ports import SourceInfo
from lektyra.settings import Settings


def speech_with_pauses(seconds: int, pause_every_s: int = 13) -> bytes:
    """Noise at speech level with a 400 ms silence every `pause_every_s` seconds."""
    rng = np.random.default_rng(1)
    samples = rng.normal(0, 3000, size=seconds * SAMPLE_RATE).astype(np.int16)
    for t in range(pause_every_s, seconds, pause_every_s):
        samples[t * SAMPLE_RATE : t * SAMPLE_RATE + SAMPLE_RATE * 2 // 5] = 0
    return samples.astype("<i2").tobytes()


class FakeStream:
    def __init__(self, pcm: bytes) -> None:
        self._pcm = pcm

    def chunks(self, chunk_bytes: int) -> Iterator[bytes]:
        for i in range(0, len(self._pcm), chunk_bytes):
            yield self._pcm[i : i + chunk_bytes]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None) -> None:
        return None


class FakeSource:
    """Each open plays `seconds_per_open` seconds, then the stream 'drops'."""

    def __init__(self, live: bool, seconds_per_open: int, duration_s: float | None = None) -> None:
        self.live = live
        self.seconds = seconds_per_open
        self.duration_s = duration_s
        self.opens = 0
        self.resolves = 0

    def resolve(self, url: str) -> SourceInfo:
        self.resolves += 1
        return SourceInfo(
            url=url,
            title="fake",
            is_live=self.live,
            duration_s=self.duration_s,
            media_url=f"fake://{self.resolves}",
            resolved_by="direct",
        )

    def open(self, info: SourceInfo, *, realtime: bool, log: IO[bytes] | None = None) -> FakeStream:
        self.opens += 1
        return FakeStream(speech_with_pauses(self.seconds))


class EnergyDetector:
    """Speech where there is energy: enough for the planner to find the pauses."""

    def reset(self) -> None:
        return None

    def probabilities(self, samples: Samples) -> Curve:
        whole = len(samples) // FRAME_SAMPLES
        frames = samples[: whole * FRAME_SAMPLES].astype(np.float64).reshape(whole, FRAME_SAMPLES)
        rms = np.sqrt(np.mean(frames * frames, axis=1))
        return np.where(rms > 100, 0.9, 0.05).astype(np.float32)


class MemorySink:
    written: ClassVar[dict[str, int]] = {}

    def __init__(self, path: Path) -> None:
        self._path = path
        MemorySink.written[path.name] = 0

    def write(self, pcm: bytes) -> None:
        MemorySink.written[self._path.name] += len(pcm)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None) -> None:
        return None


def run(tmp_path: Path, source: FakeSource, max_minutes: float | None) -> tuple[IngestResult, list[float]]:
    sleeps: list[float] = []
    result = run_ingest(
        "fake:stream",
        title=None,
        realtime=False,
        max_minutes=max_minutes,
        settings=Settings(data_dir=tmp_path),
        now=lambda: datetime(2026, 11, 14, 12, 0, 0),
        source=source,
        detector=EnergyDetector(),
        sink=MemorySink,
        sleep=sleeps.append,
    )
    return result, sleeps


def test_a_live_stream_that_drops_is_reopened_and_the_gaps_recorded(tmp_path: Path) -> None:
    source = FakeSource(live=True, seconds_per_open=40)
    (result, sleeps) = run(tmp_path, source, max_minutes=3)
    assert source.opens >= 5  # 3 min of audio from 40 s streams
    assert len(result.gaps) == source.opens - 1
    assert result.stopped == "max"
    assert all(s > 0 for s in sleeps)
    manifest = load_manifest(result.event_dir)
    assert manifest.finished and len(manifest.gaps) == len(result.gaps)
    # The planner carries on across drops: pieces still 45–90 s, the last one ending the run.
    lengths = [p.end_ms - p.own_start_ms for p in manifest.pieces[:-1]]
    assert lengths and all(45_000 <= n <= 90_000 for n in lengths)


def test_a_live_stream_that_never_comes_back_stops_after_the_reconnect_budget(tmp_path: Path) -> None:
    source = FakeSource(live=True, seconds_per_open=0)
    (result, _) = run(tmp_path, source, max_minutes=None)
    assert result.stopped == "dropped"
    assert source.opens == MAX_RECONNECTS + 1


def test_a_stored_video_that_ends_early_is_marked_incomplete(tmp_path: Path) -> None:
    (result, _) = run(tmp_path, FakeSource(live=False, seconds_per_open=60, duration_s=120.0), max_minutes=None)
    assert result.stopped == "end"
    assert result.complete is False


def test_a_stored_video_heard_to_its_end_is_complete(tmp_path: Path) -> None:
    (result, _) = run(tmp_path, FakeSource(live=False, seconds_per_open=100, duration_s=100.0), max_minutes=None)
    assert result.complete is True
    assert result.gaps == []
