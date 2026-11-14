"""48 kHz stereo → 16 kHz mono (K28): speech passes, what would alias is filtered, blocks do not matter."""

import numpy as np

from lektyra.domain.resample import CAPTURE_RATE, Decimator


def _tone(hz: float, seconds: float, amplitude: float = 0.5) -> np.ndarray:
    t = np.arange(int(CAPTURE_RATE * seconds)) / CAPTURE_RATE
    mono = (amplitude * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    return np.stack([mono, mono], axis=1)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))


def test_a_speech_band_tone_passes_at_a_third_of_the_rate() -> None:
    out = Decimator().feed(_tone(1_000, 1.0))
    assert len(out) == 16_000
    expected = 0.5 / np.sqrt(2) * 32767
    assert abs(_rms(out[200:]) - expected) / expected < 0.03


def test_a_tone_above_8_khz_is_filtered_instead_of_folding_into_speech() -> None:
    passed = _rms(Decimator().feed(_tone(1_000, 1.0))[200:])
    folded = _rms(Decimator().feed(_tone(10_000, 1.0))[200:])  # without a filter it would come back at 6 kHz
    assert folded < 0.02 * passed


def test_blocks_of_any_size_give_the_same_stream() -> None:
    tone = _tone(440, 0.5) + _tone(3_000, 0.5, 0.2)
    whole = Decimator().feed(tone)
    d = Decimator()
    parts, at = [], 0
    for size in (1000, 777, 2223, 5, 9001, 3):
        parts.append(d.feed(tone[at : at + size]))
        at += size
    parts.append(d.feed(tone[at:]))
    assert np.array_equal(np.concatenate(parts), whole)


def test_stereo_is_mixed_to_mono() -> None:
    left = _tone(1_000, 0.2)[:, 0]
    opposite = np.stack([left, -left], axis=1)  # the channels cancel
    assert int(np.abs(Decimator().feed(opposite)).max()) == 0
