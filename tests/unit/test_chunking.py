"""ADR-006: cut in a quiet moment, never inside a word; ADR-007: replay = live."""

import itertools
from dataclasses import dataclass

import numpy as np
import pytest

from lektyra.domain.audio import FRAME_MS, Curve
from lektyra.domain.chunking import CutPlanner, CutRule, PlannedCut, TimedWord, choose_cut, stitch

SPEECH_PROB = 0.9
SPEECH_DB = -20.0


@dataclass(frozen=True)
class Quiet:
    """A quiet stretch in a synthetic curve."""

    at_ms: int
    length_ms: int
    prob: float = 0.05
    energy_db: float = -60.0


def curves(total_ms: int, quiets: list[Quiet]) -> tuple[Curve, Curve]:
    frames = total_ms // FRAME_MS
    prob = np.full(frames, SPEECH_PROB, dtype=np.float32)
    energy = np.full(frames, SPEECH_DB, dtype=np.float32)
    for q in quiets:
        a = q.at_ms // FRAME_MS
        b = (q.at_ms + q.length_ms) // FRAME_MS
        prob[a:b] = q.prob
        energy[a:b] = q.energy_db
    return prob, energy


def test_nothing_is_decided_before_75_seconds_are_heard() -> None:
    prob, energy = curves(74_000, [Quiet(50_000, 800)])
    assert choose_cut(prob, energy) is None


def test_the_longest_pause_wins_not_the_first() -> None:
    prob, energy = curves(75_000, [Quiet(46_000, 320), Quiet(61_000, 640)])
    cut = choose_cut(prob, energy)
    assert cut is not None
    assert cut.kind == "pause"
    assert 61_000 <= cut.at_ms <= 61_640
    assert cut.quiet_ms >= 600


def test_the_cut_sits_in_the_middle_of_the_pause() -> None:
    prob, energy = curves(75_000, [Quiet(60_000, 640)])
    cut = choose_cut(prob, energy)
    assert cut is not None
    assert abs(cut.at_ms - 60_320) <= FRAME_MS


def test_equal_pauses_tie_break_toward_the_window_middle() -> None:
    prob, energy = curves(75_000, [Quiet(46_000, 320), Quiet(59_000, 320)])
    cut = choose_cut(prob, energy)
    assert cut is not None
    assert 59_000 <= cut.at_ms <= 59_320


def test_a_speaker_change_inside_a_pause_is_a_bonus() -> None:
    prob, energy = curves(75_000, [Quiet(50_000, 320), Quiet(70_000, 320)])
    cut = choose_cut(prob, energy, turn_changes_ms=[70_100])
    assert cut is not None
    assert 70_000 <= cut.at_ms <= 70_320


def test_a_pause_before_45_seconds_is_never_used() -> None:
    prob, energy = curves(75_000, [Quiet(30_000, 2_000), Quiet(55_000, 256)])
    cut = choose_cut(prob, energy)
    assert cut is not None
    assert cut.at_ms >= 45_000


def test_without_a_pause_the_deepest_dip_between_words_is_used() -> None:
    # 160 ms micro-pause: too short to be a pause, quiet enough to be a dip, not speech.
    prob, energy = curves(75_000, [Quiet(66_000, 160, prob=0.3, energy_db=-45.0)])
    cut = choose_cut(prob, energy)
    assert cut is not None
    assert cut.kind == "dip"
    assert 66_000 <= cut.at_ms <= 66_160


def test_a_dip_that_is_still_speech_is_not_a_cut() -> None:
    # Energy drops but the speech detector stays sure: likely a soft syllable inside a word.
    prob, energy = curves(80_000, [Quiet(66_000, 200, prob=0.8, energy_db=-45.0)])
    assert choose_cut(prob, energy) is None


def test_at_90_seconds_the_quietest_frame_is_forced() -> None:
    prob, energy = curves(90_000, [Quiet(80_000, 64, prob=0.6, energy_db=-30.0)])
    cut = choose_cut(prob, energy)
    assert cut is not None
    assert cut.kind == "forced"
    assert 80_000 <= cut.at_ms <= 80_064


def test_a_cut_never_lands_where_speech_probability_is_above_threshold_unless_forced() -> None:
    rng = np.random.default_rng(7)
    for _ in range(50):
        prob = rng.uniform(0.0, 1.0, size=80_000 // FRAME_MS).astype(np.float32)
        energy = rng.uniform(-70.0, -10.0, size=prob.size).astype(np.float32)
        cut = choose_cut(prob, energy)
        if cut is None or cut.kind == "forced":
            continue
        assert float(prob[cut.at_ms // FRAME_MS]) < 0.5 or cut.kind == "dip"
        if cut.kind == "dip":
            assert float(prob[cut.at_ms // FRAME_MS]) <= 0.5


def test_curves_of_different_length_are_refused() -> None:
    with pytest.raises(ValueError):
        choose_cut(np.zeros(10, dtype=np.float32), np.zeros(9, dtype=np.float32))


def test_rule_numbers_must_be_ordered() -> None:
    with pytest.raises(ValueError):
        CutRule(window_start_ms=80_000)


def stream(total_ms: int) -> tuple[Curve, Curve]:
    """Five minutes of speech with a sentence pause every ~17 s and one long monologue without pauses."""
    quiets = [Quiet(t, 260 + (t // 1000) % 5 * 40) for t in range(17_000, total_ms, 17_000)]
    quiets = [q for q in quiets if not 180_000 <= q.at_ms <= 280_000]  # 100 s monologue
    return curves(total_ms, quiets)


def run_planner(prob: Curve, energy: Curve, batch: int) -> list[PlannedCut]:
    planner = CutPlanner()
    cuts: list[PlannedCut] = []
    for i in range(0, prob.size, batch):
        cuts += planner.feed(prob[i : i + batch], energy[i : i + batch])
    return cuts


def test_replay_equals_live_the_same_cuts_whatever_the_batch_size() -> None:
    prob, energy = stream(360_000)
    live = run_planner(prob, energy, batch=1)
    assert live == run_planner(prob, energy, batch=31)
    assert live == run_planner(prob, energy, batch=prob.size)
    assert len(live) >= 4


def test_every_piece_is_between_45_and_90_seconds() -> None:
    prob, energy = stream(360_000)
    starts = [0, *[c.at_ms for c in run_planner(prob, energy, batch=64)]]
    lengths = [b - a for a, b in itertools.pairwise(starts)]
    assert lengths
    assert all(45_000 <= n <= 90_000 for n in lengths), lengths


def test_the_monologue_without_pauses_still_gets_cut_by_90_seconds() -> None:
    prob, energy = stream(360_000)
    kinds = {c.kind for c in run_planner(prob, energy, batch=64)}
    assert "forced" in kinds or "dip" in kinds


def w(text: str, start: int, end: int) -> TimedWord:
    return TimedWord(text=text, start_ms=start, end_ms=end)


def test_stitch_takes_each_overlap_word_from_the_piece_where_it_is_whole() -> None:
    cut, overlap = 60_000, 1_500  # the later piece starts at 58.5 s
    earlier = [w("ministerstvo", 57_000, 57_800), w("zaplatilo", 58_200, 58_900), w("dvesto", 59_300, 59_900)]
    # The later piece starts mid-"zaplatilo": its copy is garbled and lies at the edge.
    later = [w("platilo", 58_500, 58_900), w("dvesto", 59_300, 59_900), w("miliónov", 60_200, 60_800)]
    joined = [x.text for x in stitch(earlier, later, cut, overlap)]
    assert joined == ["ministerstvo", "zaplatilo", "dvesto", "miliónov"]


def test_stitch_replaces_a_word_a_forced_cut_split() -> None:
    cut, overlap = 90_000, 1_500
    earlier = [w("rozpočet", 88_000, 88_700), w("verej", 89_700, 90_000)]  # cut inside "verejných"
    later = [w("rozpočet", 88_000, 88_700), w("verejných", 89_700, 90_400), w("financií", 90_500, 91_100)]
    joined = [x.text for x in stitch(earlier, later, cut, overlap)]
    assert joined == ["rozpočet", "verejných", "financií"]
