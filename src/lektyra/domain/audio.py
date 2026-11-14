"""The audio format every source is turned into (ADR-007) and per-frame measurements.

16 kHz, mono, signed 16-bit little-endian PCM. A frame is 512 samples = 32 ms: the window Silero VAD scores, so
speech probability and energy line up frame by frame.
"""

from typing import Final

import numpy as np
import numpy.typing as npt

SAMPLE_RATE: Final = 16_000
SAMPLE_BYTES: Final = 2
FRAME_SAMPLES: Final = 512
FRAME_MS: Final = FRAME_SAMPLES * 1000 // SAMPLE_RATE  # 32
FRAME_BYTES: Final = FRAME_SAMPLES * SAMPLE_BYTES
BYTES_PER_MS: Final = SAMPLE_RATE * SAMPLE_BYTES // 1000  # 32

# Below this, a frame is digital silence: -96 dBFS is the floor of 16-bit audio.
SILENCE_FLOOR_DB: Final = -96.0

Samples = npt.NDArray[np.int16]
Curve = npt.NDArray[np.float32]


def samples_from_bytes(pcm: bytes) -> Samples:
    """Little-endian s16 PCM bytes → samples. A trailing odd byte is not a sample and is dropped."""
    usable = len(pcm) - len(pcm) % SAMPLE_BYTES
    return np.frombuffer(pcm[:usable], dtype="<i2").astype(np.int16)


def frame_energy_db(samples: Samples) -> Curve:
    """RMS energy of each whole 512-sample frame, in dBFS (0 = full scale, -96 = digital silence).

    A trailing partial frame is ignored; the caller keeps it until the next samples complete it.
    """
    whole = len(samples) // FRAME_SAMPLES
    if whole == 0:
        return np.zeros(0, dtype=np.float32)
    frames = samples[: whole * FRAME_SAMPLES].astype(np.float64).reshape(whole, FRAME_SAMPLES) / 32768.0
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(rms)
    return np.maximum(db, SILENCE_FLOOR_DB).astype(np.float32)


def ms_to_samples(ms: int) -> int:
    return ms * SAMPLE_RATE // 1000


def frames_to_ms(frames: int) -> int:
    return frames * FRAME_MS
