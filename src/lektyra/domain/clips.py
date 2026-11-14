"""Short passages to hear a voice by: the speaker's longest turns, trimmed at both ends. Pure.

A reel of a few clips is how Martin recognises a voice before naming it (ADR-004: listen first). Long turns are
the clearest; trimming the edges keeps out the tail of the previous speaker and the start of the next one.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

MIN_MS: Final = 2_500  # shorter turns say too little to recognise anyone
MAX_MS: Final = 12_000
TRIM_MS: Final = 400


@dataclass(frozen=True)
class Span:
    start_ms: int
    end_ms: int


def choose_clips(
    turns: Sequence[Span], limit: int, max_ms: int = MAX_MS, min_ms: int = MIN_MS, trim_ms: int = TRIM_MS
) -> list[Span]:
    """Up to `limit` clips from the longest turns, at most `max_ms` each, in the order they were said."""
    usable = [t for t in turns if t.end_ms - t.start_ms - 2 * trim_ms >= min_ms]
    longest = sorted(usable, key=lambda t: t.start_ms - t.end_ms)[:limit]
    clips = [Span(t.start_ms + trim_ms, min(t.end_ms - trim_ms, t.start_ms + trim_ms + max_ms)) for t in longest]
    return sorted(clips, key=lambda c: c.start_ms)
