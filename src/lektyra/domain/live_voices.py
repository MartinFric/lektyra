"""Who is speaking, while it is being said: 2 s window fingerprints → session speakers, one window at a time. Pure.

The offline diarization (ADR-008) sees the whole video before it clusters; a live stream cannot wait. Here each
window joins the session speaker it sounds most like, if it is close enough. A window close to nobody waits as
pending; when the last `found` pending windows sound like one another, they become a new speaker. Stragglers stay
unclear rather than being forced onto someone (ADR-004: a wrong name is worse than unknown).
"""

from dataclasses import dataclass, field
from typing import Final

import numpy as np
import numpy.typing as npt

from lektyra.domain.audio import FRAME_MS, Curve
from lektyra.domain.diarization import HOP_MS, UNCLEAR, WINDOW_MS

JOIN: Final = 0.40  # a window this close to a speaker's centroid is that speaker (calibrated, ADR-013)
FOUND: Final = 5  # unexplained windows that agree with each other found a new speaker (~5 s of speech)
KEEP_PENDING: Final = 6
SPEECH_SHARE: Final = 0.6  # a window is fingerprinted when at least this share of its frames is speech

Vector = npt.NDArray[np.float32]


def _unit(v: Vector) -> Vector:
    n = float(np.linalg.norm(v))
    out: Vector = (v / n).astype(np.float32) if n > 0 else v.astype(np.float32)
    return out


@dataclass
class WindowPlanner:
    """Which 2 s windows to fingerprint as audio arrives: every `hop_ms`, the last `window_ms`, if enough of it is
    speech. Speech probabilities come in 32 ms frames from the start of the stream."""

    window_ms: int = WINDOW_MS
    hop_ms: int = HOP_MS
    speech_share: float = SPEECH_SHARE
    threshold: float = 0.5
    _probs: list[float] = field(default_factory=list)
    _offset: int = 0  # frames dropped from the front of _probs
    _next_end: int = WINDOW_MS

    def feed(self, probs: Curve) -> list[tuple[int, int]]:
        """Windows (start_ms, end_ms) that are due now and worth a fingerprint."""
        self._probs.extend(float(p) for p in probs)
        heard_ms = (self._offset + len(self._probs)) * FRAME_MS
        due: list[tuple[int, int]] = []
        while self._next_end <= heard_ms:
            start = self._next_end - self.window_ms
            a, b = start // FRAME_MS - self._offset, self._next_end // FRAME_MS - self._offset
            frames = self._probs[max(a, 0) : b]
            if frames and sum(p >= self.threshold for p in frames) / len(frames) >= self.speech_share:
                due.append((start, self._next_end))
            self._next_end += self.hop_ms
        keep_from = max(0, (self._next_end - self.window_ms) // FRAME_MS - self._offset)
        del self._probs[:keep_from]
        self._offset += keep_from
        return due


@dataclass
class _Speaker:
    total: Vector
    count: int = 0

    @property
    def centroid(self) -> Vector:
        return _unit(self.total)

    def add(self, v: Vector) -> None:
        self.total = (self.total + v).astype(np.float32)
        self.count += 1


@dataclass
class OnlineSpeakers:
    join: float = JOIN
    found: int = FOUND
    keep_pending: int = KEEP_PENDING
    labels: list[int] = field(default_factory=list)  # per window, in order; UNCLEAR until it belongs to someone
    _speakers: list[_Speaker] = field(default_factory=list)
    _pending: list[tuple[int, Vector]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self._speakers)

    def centroid(self, speaker: int) -> Vector:
        return self._speakers[speaker].centroid

    def windows_of(self, speaker: int) -> int:
        return self._speakers[speaker].count

    def add(self, embedding: Vector) -> int:
        """The window's speaker (0-based), or UNCLEAR while it is not clear yet."""
        v = _unit(np.asarray(embedding, dtype=np.float32))
        index = len(self.labels)
        self.labels.append(UNCLEAR)
        if self._speakers:
            sims = [float(s.centroid @ v) for s in self._speakers]
            best = int(np.argmax(sims))
            if sims[best] >= self.join:
                self._speakers[best].add(v)
                self.labels[index] = best
                return best
        self._pending.append((index, v))
        newest = self._pending[-self.found :]
        if len(newest) == self.found:
            mean = _unit(np.sum([w for _, w in newest], axis=0).astype(np.float32))
            if all(float(w @ mean) >= self.join for _, w in newest):
                speaker = len(self._speakers)
                self._speakers.append(_Speaker(total=np.zeros_like(v)))
                for i, w in newest:
                    self._speakers[speaker].add(w)
                    self.labels[i] = speaker
                self._pending = self._pending[: -self.found]
                return speaker
        if len(self._pending) > self.keep_pending:
            self._pending.pop(0)
        return UNCLEAR
