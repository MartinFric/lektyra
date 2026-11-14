"""ADR-004: decisions from the nearest samples; profile samples from clean windows. Synthetic vectors only."""

import numpy as np

from lektyra.domain.matching import Neighbour, decide, profile_samples, ranked


def test_no_samples_means_unknown() -> None:
    assert decide([]).status == "unknown"


def test_a_clear_majority_of_close_samples_is_named() -> None:
    d = decide([Neighbour(1, 0.86), Neighbour(1, 0.83), Neighbour(1, 0.81), Neighbour(2, 0.40), Neighbour(1, 0.79)])
    assert (d.person_id, d.status, d.votes) == (1, "auto", 4)
    assert 0.80 < d.score < 0.83


def test_a_middling_match_is_only_suggested() -> None:
    d = decide([Neighbour(3, 0.62), Neighbour(3, 0.60), Neighbour(4, 0.30)])
    assert (d.person_id, d.status) == (3, "suggested")


def test_a_weak_best_match_stays_unknown_but_names_the_candidate() -> None:
    d = decide([Neighbour(5, 0.47), Neighbour(6, 0.31)])
    assert d.status == "unknown"
    assert d.person_id == 5


def test_votes_are_summed_so_one_lucky_sample_does_not_win() -> None:
    d = decide([Neighbour(1, 0.90), Neighbour(2, 0.70), Neighbour(2, 0.69), Neighbour(2, 0.68)])
    assert d.person_id == 2


def test_samples_come_only_from_clean_windows_of_that_speaker() -> None:
    rng = np.random.default_rng(1)
    voice = rng.normal(0, 1, 16).astype(np.float32)
    other = rng.normal(0, 1, 16).astype(np.float32)
    windows = np.stack([voice + rng.normal(0, 0.2, 16) for _ in range(40)] + [other for _ in range(10)]).astype(
        np.float32
    )
    labels = np.array([0] * 40 + [1] * 10, dtype=np.int64)
    samples = profile_samples(windows, labels, 0, voice)
    assert samples.shape == (4, 16)  # 40 clean windows in chunks of 10
    assert float((samples @ (voice / np.linalg.norm(voice))).min()) > 0.9


def test_samples_are_spread_and_capped() -> None:
    rng = np.random.default_rng(2)
    voice = rng.normal(0, 1, 8).astype(np.float32)
    windows = np.stack([voice + rng.normal(0, 0.1, 8) for _ in range(500)]).astype(np.float32)
    samples = profile_samples(windows, np.zeros(500, dtype=np.int64), 0, voice, max_samples=20)
    assert samples.shape[0] == 20


def test_ranked_lists_every_candidate_best_first_by_their_own_closest_samples() -> None:
    found = ranked([Neighbour(1, 0.40), Neighbour(2, 0.66), Neighbour(1, 0.45), Neighbour(2, 0.62), Neighbour(3, 0.81)])
    assert [d.person_id for d in found] == [3, 2, 1]
    assert [d.status for d in found] == ["auto", "suggested", "unknown"]
    assert found[1].votes == 2


def test_ranked_of_nothing_is_empty() -> None:
    assert ranked([]) == []
