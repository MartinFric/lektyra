"""Short passages to hear a voice by: the speaker's longest turns, trimmed at both ends. Pure.

A reel of a few clips is how Martin recognises a voice before naming it (ADR-004: listen first). Long turns are
the clearest; trimming the edges keeps out the tail of the previous speaker and the start of the next one. A voice
heard only in short bits (interjections) still gets its bits, trimmed less: something to hear beats nothing.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

MIN_MS: Final = 2_500  # a clip at least this long after trimming is enough to recognise someone
MAX_MS: Final = 12_000
TRIM_MS: Final = 400
SHORT_MIN_MS: Final = 1_200  # when nothing longer exists: short bits, trimmed only a little
SHORT_TRIM_MS: Final = 100


@dataclass(frozen=True)
class Span:
    start_ms: int
    end_ms: int


def _longest(turns: Sequence[Span], limit: int, max_ms: int, min_ms: int, trim_ms: int) -> list[Span]:
    usable = [t for t in turns if t.end_ms - t.start_ms - 2 * trim_ms >= min_ms]
    longest = sorted(usable, key=lambda t: t.start_ms - t.end_ms)[:limit]
    clips = [Span(t.start_ms + trim_ms, min(t.end_ms - trim_ms, t.start_ms + trim_ms + max_ms)) for t in longest]
    return sorted(clips, key=lambda c: c.start_ms)


def choose_clips(
    turns: Sequence[Span], limit: int, max_ms: int = MAX_MS, min_ms: int = MIN_MS, trim_ms: int = TRIM_MS
) -> list[Span]:
    """Up to `limit` clips from the longest turns, at most `max_ms` each, in the order they were said. If no turn is
    long enough, the longest short bits instead."""
    return _longest(turns, limit, max_ms, min_ms, trim_ms) or _longest(
        turns, limit, max_ms, SHORT_MIN_MS, SHORT_TRIM_MS
    )
