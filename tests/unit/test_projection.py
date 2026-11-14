"""The voice map: groups stay apart on the page. Synthetic vectors only."""

import numpy as np

from lektyra.domain.projection import project_2d


def test_two_voices_land_in_two_separate_places() -> None:
    rng = np.random.default_rng(3)
    a, b = rng.normal(0, 1, 32), rng.normal(0, 1, 32)
    points = np.stack([a + rng.normal(0, 0.05, 32) for _ in range(5)] + [b + rng.normal(0, 0.05, 32) for _ in range(5)])
    flat = project_2d(points.astype(np.float32))
    assert flat.shape == (10, 2)
    assert float(np.abs(flat).max()) <= 1.0
    gap = float(np.linalg.norm(flat[:5].mean(axis=0) - flat[5:].mean(axis=0)))
    spread = float(max(np.linalg.norm(flat[:5] - flat[:5].mean(axis=0), axis=1).max(), 1e-6))
    assert gap > 5 * spread


def test_one_or_no_voice_sits_in_the_middle() -> None:
    assert project_2d(np.zeros((0, 4), dtype=np.float32)).shape == (0, 2)
    assert project_2d(np.ones((1, 4), dtype=np.float32)).tolist() == [[0.0, 0.0]]
