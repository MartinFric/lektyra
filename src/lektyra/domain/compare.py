"""Comparing engines on the same audio: rows of 10 s, agreement, and the words only a minority heard.

Used by the comparison page that Martin writes his references from (spike-plan §6). An engine without word times
gets them spread evenly over each segment (`approx_words`), good enough to place text in a 10 s row.
"""

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from lektyra.domain.chunking import TimedWord
from lektyra.domain.transcript import Segment, plain_words


def approx_words(segment: Segment) -> tuple[TimedWord, ...]:
    """The segment's own words, or its text split evenly over its time when the engine gave no word times."""
    if segment.words:
        return segment.words
    tokens = segment.text.split()
    if not tokens:
        return ()
    span = max(1, segment.end_ms - segment.start_ms)
    step = span / len(tokens)
    return tuple(
        TimedWord(t, round(segment.start_ms + i * step), round(segment.start_ms + (i + 1) * step))
        for i, t in enumerate(tokens)
    )


def row_texts(segments: Sequence[Segment], lo_ms: int, hi_ms: int, row_ms: int) -> list[str]:
    """The text of each row [lo + k·row, lo + (k+1)·row), words placed by their start."""
    rows: list[list[str]] = [[] for _ in range(max(1, -(-(hi_ms - lo_ms) // row_ms)))]
    for s in segments:
        for w in approx_words(s):
            k = (w.start_ms - lo_ms) // row_ms
            if 0 <= k < len(rows):
                rows[k].append(w.text)
    return [" ".join(r) for r in rows]


def covered(a: set[str], near_b: set[str], b: set[str], near_a: set[str]) -> float:
    """How much two engines heard the same words, tolerant of a word placed one row off: the mean of the share of
    a's words found near b and the share of b's words found near a (1 = the same, 0 = nothing in common)."""
    if not a and not b:
        return 1.0
    left = len(a & near_b) / len(a) if a else 0.0
    right = len(b & near_a) / len(b) if b else 0.0
    return (left + right) / 2


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class RowComparison:
    """One row across engines: how much they agree, and per engine the words few others heard."""

    disagreement: float  # 1 - mean pairwise `covered` (0 = all heard the same words, row shifts tolerated)
    minority: dict[str, set[str]]  # engine → its words that fewer than half of the other engines heard nearby
    medoid: str  # the engine agreeing most with the rest in this row


def compare_row(rows_by_engine: Mapping[str, Sequence[str]], k: int) -> RowComparison:
    """Compare row k. Words are matched against the other engines' rows k-1..k+1, so a word placed in the
    neighbouring row by a slightly different clock does not count as disagreement."""
    engines = list(rows_by_engine)
    own = {e: set(plain_words(rows_by_engine[e][k])) for e in engines}
    near: dict[str, set[str]] = {}
    for e in engines:
        rows = rows_by_engine[e]
        near[e] = set().union(*(set(plain_words(rows[j])) for j in range(max(0, k - 1), min(len(rows), k + 2))))
    pairs = list(itertools.combinations(engines, 2))
    scores = [covered(own[a], near[b], own[b], near[a]) for a, b in pairs]
    disagreement = 1.0 - (sum(scores) / len(scores) if scores else 1.0)
    minority: dict[str, set[str]] = {}
    for e in engines:
        others = [o for o in engines if o != e]
        minority[e] = {w for w in own[e] if 2 * sum(w in near[o] for o in others) < len(others)}

    def support(e: str) -> float:
        return sum(covered(own[e], near[o], own[o], near[e]) for o in engines if o != e)

    medoid = max(engines, key=support) if engines else ""
    return RowComparison(disagreement=disagreement, minority=minority, medoid=medoid)


def mean_agreement(rows_by_engine: Mapping[str, Sequence[str]], engine: str) -> float:
    """How much one engine agrees with the others over all rows (mean Jaccard), for ranking the columns."""
    others = [o for o in rows_by_engine if o != engine]
    if not others:
        return 1.0
    n = len(rows_by_engine[engine])
    total = 0.0
    for k in range(n):
        mine = set(plain_words(rows_by_engine[engine][k]))
        total += sum(jaccard(mine, set(plain_words(rows_by_engine[o][k]))) for o in others) / len(others)
    return total / n if n else 0.0
