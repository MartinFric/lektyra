from lektyra.domain.chunking import TimedWord
from lektyra.domain.compare import approx_words, compare_row, mean_agreement, row_texts
from lektyra.domain.transcript import Segment


def test_a_segment_without_word_times_is_spread_evenly() -> None:
    words = approx_words(Segment(0, 3000, "jeden dva tri"))
    assert [(w.text, w.start_ms) for w in words] == [("jeden", 0), ("dva", 1000), ("tri", 2000)]


def test_words_land_in_their_10_s_row() -> None:
    seg = Segment(
        0, 25_000, "", (TimedWord("a", 1000, 1500), TimedWord("b", 12_000, 12_500), TimedWord("c", 24_000, 24_200))
    )
    assert row_texts([seg], 0, 30_000, 10_000) == ["a", "b", "c"]


def test_the_word_only_one_engine_heard_is_marked() -> None:
    rows = {
        "x": ["rozpočet je dvanásť miliárd"],
        "y": ["rozpočet je dvanásť miliárd"],
        "z": ["rozpočet je dvadsať miliárd"],
    }
    r = compare_row(rows, 0)
    assert r.minority["z"] == {"dvadsať"}
    assert r.minority["x"] == set()
    assert r.medoid in ("x", "y")
    assert 0 < r.disagreement < 1


def test_a_word_shifted_into_the_next_row_is_not_a_disagreement() -> None:
    rows = {"x": ["koniec vety", "nová"], "y": ["koniec", "vety nová"]}
    assert compare_row(rows, 0).minority["y"] == set()
    assert compare_row(rows, 1).minority["y"] == set()


def test_the_engine_closest_to_the_rest_ranks_highest() -> None:
    rows = {"x": ["a b c"], "y": ["a b c"], "z": ["q r s"]}
    assert mean_agreement(rows, "x") > mean_agreement(rows, "z")
