"""Diarization on synthetic embeddings and curves (no real voices: ADR-005)."""

import numpy as np

from lektyra.domain.audio import FRAME_MS
from lektyra.domain.diarization import (
    Turn,
    assign,
    centroids,
    cluster,
    group,
    similarity,
    speech_regions,
    turns,
    windows,
)


def voices(rng: np.random.Generator, centres: np.ndarray, which: list[int], noise: float) -> np.ndarray:
    return (centres[which] + rng.normal(0, noise, size=(len(which), centres.shape[1]))).astype(np.float32)


def test_three_voices_come_out_as_three_speakers_largest_first() -> None:
    rng = np.random.default_rng(3)
    centres = rng.normal(0, 1, size=(3, 192))
    which = [0] * 60 + [1] * 30 + [2] * 10
    labels = cluster(voices(rng, centres, which, noise=0.35), threshold=0.6)
    assert len(set(labels.tolist())) == 3
    assert (labels[:60] == 0).all() and (labels[60:90] == 1).all() and (labels[90:] == 2).all()


def test_a_strict_threshold_never_merges_two_voices() -> None:
    rng = np.random.default_rng(5)
    centres = rng.normal(0, 1, size=(2, 192))
    labels = cluster(voices(rng, centres, [0] * 20 + [1] * 20, noise=0.3), threshold=0.3)
    assert len(set(labels[:20].tolist()) & set(labels[20:].tolist())) == 0


def test_speech_regions_bridge_short_gaps_and_drop_blips() -> None:
    prob = np.zeros(200, dtype=np.float32)
    prob[10:40] = 0.9  # 960 ms
    prob[45:80] = 0.9  # 5 frames gap = 160 ms: bridged
    prob[120:125] = 0.9  # 160 ms blip: dropped
    assert speech_regions(prob) == [(10 * FRAME_MS, 80 * FRAME_MS)]


def test_windows_cover_a_region_to_its_end() -> None:
    wins = windows([(0, 4_500)])
    assert wins[0] == (0, 2_000, 0)
    assert wins[-1][1] == 4_500


def test_groups_never_mix_regions() -> None:
    wins = [(0, 2000, 0), (1000, 3000, 0), (5000, 7000, 1), (6000, 8000, 1)]
    _, members = group(np.ones((4, 8), dtype=np.float32), wins, size=3)
    assert members == [[0, 1], [2, 3]]


def test_short_runs_are_absorbed_and_neighbours_merge() -> None:
    wins = [(k * 1000, k * 1000 + 2000, 0) for k in range(10)]
    labels = np.array([0, 0, 0, 0, 1, 0, 0, 0, 0, 0], dtype=np.int64)  # a 1 s blip of speaker 1
    assert turns(wins, labels) == [Turn(0, 11_000, 0)]


def test_the_same_voice_in_two_events_is_most_similar() -> None:
    rng = np.random.default_rng(9)
    centres = rng.normal(0, 1, size=(3, 192))
    a = centroids(voices(rng, centres, [0, 0, 1, 1], 0.3), np.array([0, 0, 1, 1]))
    b = centroids(voices(rng, centres, [1, 1, 2, 2], 0.3), np.array([0, 0, 1, 1]))
    s = similarity(a, b)
    assert int(np.argmax(s[1])) == 0  # a's speaker 1 is b's speaker 0 (the same centre)
    assert assign(a, b).shape == (2,)


def test_a_tiny_cluster_becomes_unclear_not_a_speaker() -> None:
    from lektyra.domain.diarization import UNCLEAR, drop_minor

    labels = np.array([0] * 300 + [1] * 200 + [2] * 2, dtype=np.int64)  # two voices and a 2-point blip
    out = drop_minor(labels)
    assert set(out[:500].tolist()) == {0, 1}
    assert (out[500:] == UNCLEAR).all()


def test_a_window_like_no_speaker_is_unclear() -> None:
    from lektyra.domain.diarization import UNCLEAR

    centres = np.eye(3, dtype=np.float32)[:2]  # speakers along x and y
    windows_ = np.array([[1, 0.1, 0], [0, 0, 1]], dtype=np.float32)  # near x; along z (nobody)
    assert assign(windows_, centres).tolist() == [0, UNCLEAR]
