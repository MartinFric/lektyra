from lektyra.domain.align import UNKNOWN, LabelledTurn, label_words, render, utterances
from lektyra.domain.chunking import TimedWord

TURNS = [LabelledTurn(0, 5_000, "S1"), LabelledTurn(5_000, 9_000, "S2"), LabelledTurn(12_000, 20_000, "S1")]


def w(text: str, a: int, b: int) -> TimedWord:
    return TimedWord(text, a, b)


def test_a_word_goes_to_the_turn_holding_its_middle() -> None:
    words = [w("dobrý", 100, 400), w("deň", 4_800, 5_400), w("áno", 6_000, 6_300)]
    assert label_words(words, TURNS) == ["S1", "S2", "S2"]  # "deň" has its middle at 5.1 s


def test_a_word_between_turns_goes_to_the_nearest_within_a_second_else_unknown() -> None:
    words = [w("hm", 9_200, 9_400), w("ticho", 10_400, 10_600)]
    assert label_words(words, TURNS) == ["S2", UNKNOWN]


def test_utterances_group_a_speaker_and_restamp_each_minute() -> None:
    words = [w("a", 0, 100), w("b", 200, 300), w("c", 61_000, 61_100), w("d", 62_000, 62_100)]
    labels = ["S1", "S1", "S1", "S2"]
    us = utterances(words, labels)
    assert [(u.start_ms, u.label, u.text) for u in us] == [(0, "S1", "a b"), (61_000, "S1", "c"), (62_000, "S2", "d")]


def test_render_is_htn_format() -> None:
    us = utterances([w("Dobrý", 0, 300), w("večer", 300, 700)], ["S1", "S1"])
    md = render("V politike", {"engine": "x"}, us)
    assert "**[00:00] S1:** Dobrý večer" in md
    assert md.startswith("---\ntitle: V politike\nengine: x\n---")


def test_a_change_of_speaker_moves_to_the_nearest_pause() -> None:
    from lektyra.domain.align import snap_boundaries

    # S1 talks until 10.0 s, a 400 ms pause, S2 from 10.4 s; diarization put the change at 11.0 s.
    words = [w("koniec", 9_300, 10_000), w("ďalej", 10_400, 10_900), w("hovorím", 11_000, 11_600)]
    turns = [LabelledTurn(0, 11_000, "S1"), LabelledTurn(11_000, 20_000, "S2")]
    snapped = snap_boundaries(turns, words)
    assert snapped[0].end_ms == snapped[1].start_ms == 10_200
    assert label_words(words, snapped) == ["S1", "S2", "S2"]
