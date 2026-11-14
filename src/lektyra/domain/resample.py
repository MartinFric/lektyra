"""48 kHz stereo float → 16 kHz mono int16, block by block, as a sound card delivers it. Pure.

The PC's sound output (ADR-007, K28) comes at 48 kHz; lektyra works at 16 kHz mono (ADR-006). Taking every third
sample would fold everything above 8 kHz back into the speech band, so the signal is low-pass filtered first
(a windowed-sinc FIR) and then decimated. The filter keeps its history between blocks, so cutting the stream into
blocks of any size gives exactly the same result as one long block.
"""

from dataclasses import dataclass, field
from typing import Final

import numpy as np
import numpy.typing as npt

from lektyra.domain.audio import SAMPLE_RATE, Samples

CAPTURE_RATE: Final = 48_000
FACTOR: Final = CAPTURE_RATE // SAMPLE_RATE  # 3
CUTOFF_HZ: Final = 7_000  # under 16 kHz's Nyquist (8 kHz) with room for the filter's slope
TAPS: Final = 95

Signal = npt.NDArray[np.float32]


def lowpass(taps: int = TAPS, cutoff_hz: float = CUTOFF_HZ, rate: int = CAPTURE_RATE) -> Signal:
    """A windowed-sinc low-pass filter (Hamming window), unit gain at 0 Hz."""
    n = np.arange(taps, dtype=np.float64) - (taps - 1) / 2
    ideal = np.sinc(2 * cutoff_hz / rate * n) * (2 * cutoff_hz / rate)
    shaped = ideal * np.hamming(taps)
    out: Signal = (shaped / shaped.sum()).astype(np.float32)
    return out


@dataclass
class Decimator:
    """Feed it the sound card's blocks (frames × channels, float in [-1, 1]); get 16 kHz mono int16 back."""

    factor: int = FACTOR
    taps: Signal = field(default_factory=lowpass)
    _history: Signal = field(default_factory=lambda: np.zeros(TAPS - 1, dtype=np.float32))
    _position: int = 0  # input samples consumed so far

    def feed(self, frames: npt.NDArray[np.float32]) -> Samples:
        mono = frames.mean(axis=1) if frames.ndim == 2 else frames
        x = np.concatenate([self._history, mono.astype(np.float32)])
        filtered = np.convolve(x, self.taps, mode="valid")  # one value per new input sample
        first = (-self._position) % self.factor  # keep every `factor`-th sample of the whole stream
        kept = filtered[first :: self.factor]
        self._position += len(mono)
        self._history = x[len(x) - (len(self.taps) - 1) :]
        out: Samples = np.clip(np.round(kept * 32767.0), -32768, 32767).astype(np.int16)
        return out
