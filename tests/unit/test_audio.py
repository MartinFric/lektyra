import numpy as np

from lektyra.domain.audio import (
    FRAME_MS,
    FRAME_SAMPLES,
    SILENCE_FLOOR_DB,
    frame_energy_db,
    samples_from_bytes,
)


def test_a_frame_is_32_ms() -> None:
    assert FRAME_MS == 32


def test_silence_is_the_floor() -> None:
    db = frame_energy_db(np.zeros(FRAME_SAMPLES * 3, dtype=np.int16))
    assert db.tolist() == [SILENCE_FLOOR_DB] * 3


def test_full_scale_square_wave_is_about_zero_db() -> None:
    square = np.tile(np.array([32767, -32767], dtype=np.int16), FRAME_SAMPLES // 2)
    db = frame_energy_db(square)
    assert db.size == 1
    assert -0.01 < float(db[0]) <= 0.0


def test_a_trailing_partial_frame_waits_for_more_samples() -> None:
    db = frame_energy_db(np.ones(FRAME_SAMPLES + 100, dtype=np.int16))
    assert db.size == 1


def test_bytes_are_little_endian_and_an_odd_byte_is_dropped() -> None:
    samples = samples_from_bytes(b"\x01\x00\xff\x7f\x00")
    assert samples.tolist() == [1, 32767]
