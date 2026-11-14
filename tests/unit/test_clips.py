"""Clips to hear a voice by: long turns first, trimmed, capped, in spoken order."""

from lektyra.domain.clips import Span, choose_clips


def test_the_longest_turns_become_clips_in_the_order_they_were_said() -> None:
    turns = [Span(0, 4_000), Span(10_000, 40_000), Span(50_000, 58_000), Span(60_000, 61_000)]
    clips = choose_clips(turns, limit=2)
    assert clips == [Span(10_400, 22_400), Span(50_400, 57_600)]  # 30 s turn capped at 12 s; 8 s turn trimmed


def test_short_turns_are_skipped_when_longer_ones_exist() -> None:
    clips = choose_clips([Span(0, 3_000), Span(5_000, 15_000)], limit=3)
    assert clips == [Span(5_400, 14_600)]


def test_a_voice_heard_only_in_short_bits_still_gets_them() -> None:
    # Voice 5 of video A: 13 fragments of 2-3 s and nothing longer (2026-11-14)
    clips = choose_clips([Span(0, 3_000), Span(5_000, 7_000), Span(9_000, 10_000)], limit=3)
    assert clips == [Span(100, 2_900), Span(5_100, 6_900)]  # trimmed a little; the 1 s bit is too short even now


def test_no_more_than_the_limit() -> None:
    turns = [Span(i * 10_000, i * 10_000 + 6_000) for i in range(10)]
    assert len(choose_clips(turns, limit=4)) == 4
