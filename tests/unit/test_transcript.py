from lektyra.domain.chunking import Piece, TimedWord
from lektyra.domain.transcript import Heard, Segment, filtered, join_pieces, keep, plain_words, to_stream


def piece(index: int, own_start: int, end: int, overlap: int = 1500) -> Piece:
    return Piece(index, max(0, own_start - overlap), own_start, end, "pause", 400)


def words(*items: tuple[str, int, int]) -> tuple[TimedWord, ...]:
    return tuple(TimedWord(t, a, b) for t, a, b in items)


def test_whispers_silence_inventions_are_dropped() -> None:
    assert not keep(Segment(0, 1000, "Titulky vytvoril JohnyX"))
    assert not keep(Segment(0, 1000, "...", no_speech_prob=0.9, avg_logprob=-1.5))
    assert keep(Segment(0, 1000, "Rozpočet je schválený.", no_speech_prob=0.9, avg_logprob=-0.2))


def test_filtered_counts_what_it_dropped() -> None:
    heard = Heard((Segment(0, 1, "Áno"), Segment(1, 2, "Ďakujem za pozornosť")), "Áno …", 0.001)
    assert filtered(heard).dropped == 1


def test_piece_time_moves_to_stream_time_with_the_overlap() -> None:
    p = piece(1, own_start=60_000, end=120_000)  # starts at 58.5 s with the overlap
    heard = Heard((Segment(0, 2000, "a", words(("a", 100, 400))),), "a", None)
    s = to_stream(heard, p)[0]
    assert (s.start_ms, s.words[0].start_ms) == (58_500, 58_600)


def test_word_level_join_keeps_each_overlap_word_once() -> None:
    p0, p1 = piece(0, 0, 60_000), piece(1, 60_000, 120_000)
    # Both pieces heard "zaplatilo dvesto" in the overlap 58.5–60 s; the later piece also starts mid-word.
    early = [Segment(57_000, 59_900, "", words(("ministerstvo", 57_000, 57_800), ("zaplatilo", 58_100, 58_900),
                                             ("dvesto", 59_300, 59_900)))]  # fmt: skip
    late = [Segment(58_500, 61_000, "", words(("platilo", 58_500, 58_900), ("dvesto", 59_300, 59_900),
                                            ("miliónov", 60_200, 60_800)))]  # fmt: skip
    joined = join_pieces([p0, p1], [early, late], overlap_ms=1500)
    assert [w.text for s in joined for w in s.words] == ["ministerstvo", "zaplatilo", "dvesto", "miliónov"]


def test_segment_level_join_without_word_times_goes_by_the_middle() -> None:
    p0, p1 = piece(0, 0, 60_000), piece(1, 60_000, 120_000)
    early = [Segment(50_000, 59_000, "koniec prvého"), Segment(58_600, 60_000, "dvojité")]
    late = [Segment(58_600, 60_000, "dvojité"), Segment(60_000, 70_000, "druhý kus")]
    joined = join_pieces([p0, p1], [early, late], overlap_ms=1500)
    assert [s.text for s in joined] == ["koniec prvého", "dvojité", "druhý kus"]


def test_plain_words_for_comparison() -> None:
    assert plain_words("Rozpočet: 12,5 miliardy eur, t.j. 3 %!") == [
        "rozpočet",
        "12,5",
        "miliardy",
        "eur",
        "t",
        "j",
        "3",
    ]
