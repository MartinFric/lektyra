"""Who said which word: words (stream time) onto speaker turns, then utterances, then a transcript in HTN's format.

A word goes to the turn containing its middle, else to the nearest turn within `max_gap_ms`, else to "?". Labels
are the event's own (S1…N, or a name once Martin gives one); nothing here guesses a person (ADR-004).
"""

import bisect
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from lektyra.domain.chunking import TimedWord
from lektyra.domain.timefmt import clock

UNKNOWN: Final = "?"
PARAGRAPH_MS: Final = 60_000  # a long turn is re-stamped every minute (HTN document.rs)


@dataclass(frozen=True)
class LabelledTurn:
    start_ms: int
    end_ms: int
    label: str


@dataclass(frozen=True)
class Utterance:
    start_ms: int
    end_ms: int
    label: str
    text: str


def snap_boundaries(
    turns: Sequence[LabelledTurn], words: Sequence[TimedWord], reach_ms: int = 1_500
) -> list[LabelledTurn]:
    """Move each change of speaker to the largest pause between words within `reach_ms` of it.

    Diarization windows are 2 s with a 1 s hop, so a change lands up to a second off; people switch in a pause,
    not inside a word. A boundary with no words around it stays where it is."""
    ordered = sorted(turns, key=lambda t: t.start_ms)
    if len(ordered) < 2 or not words:
        return list(ordered)
    starts = [w.start_ms for w in words]
    moved = list(ordered)
    for k in range(1, len(moved)):
        prev, cur = moved[k - 1], moved[k]
        if prev.label == cur.label:
            continue
        edge = cur.start_ms
        lo = bisect.bisect_left(starts, edge - reach_ms)
        hi = bisect.bisect_right(starts, edge + reach_ms)
        best_gap, best_at = -1, edge
        for i in range(max(lo, 1), hi):
            gap = words[i].start_ms - words[i - 1].end_ms
            if gap > best_gap:
                best_gap, best_at = gap, (words[i - 1].end_ms + words[i].start_ms) // 2
        if best_gap < 0:
            continue
        best_at = max(prev.start_ms + 1, min(best_at, cur.end_ms - 1))
        moved[k - 1] = LabelledTurn(prev.start_ms, best_at, prev.label)
        moved[k] = LabelledTurn(best_at, cur.end_ms, cur.label)
    return moved


def label_words(words: Sequence[TimedWord], turns: Sequence[LabelledTurn], max_gap_ms: int = 1_000) -> list[str]:
    """The speaker label of each word."""
    ordered = sorted(turns, key=lambda t: t.start_ms)
    starts = [t.start_ms for t in ordered]
    labels: list[str] = []
    for w in words:
        mid = w.center_ms
        i = bisect.bisect_right(starts, mid) - 1
        if i >= 0 and ordered[i].start_ms <= mid < ordered[i].end_ms:
            labels.append(ordered[i].label)
            continue
        best, gap = UNKNOWN, float(max_gap_ms)
        for j in (i, i + 1):
            if 0 <= j < len(ordered):
                t = ordered[j]
                d = t.start_ms - mid if mid < t.start_ms else mid - t.end_ms
                if d <= gap:
                    best, gap = t.label, d
        labels.append(best)
    return labels


def utterances(words: Sequence[TimedWord], labels: Sequence[str], paragraph_ms: int = PARAGRAPH_MS) -> list[Utterance]:
    """Consecutive words of one speaker become one utterance; a long one is split every `paragraph_ms`."""
    out: list[Utterance] = []
    for w, label in zip(words, labels, strict=True):
        last = out[-1] if out else None
        if last is not None and last.label == label and w.start_ms - last.start_ms < paragraph_ms:
            out[-1] = Utterance(last.start_ms, w.end_ms, label, f"{last.text} {w.text}")
        else:
            out.append(Utterance(w.start_ms, w.end_ms, label, w.text))
    return out


def render(title: str, front: Mapping[str, str], items: Sequence[Utterance]) -> str:
    """Markdown in HTN's transcript format: front matter, then `**[hh:mm:ss] label:** text` per paragraph."""
    lines = ["---", f"title: {title}"]
    lines += [f"{k}: {v}" for k, v in front.items()]
    lines += ["---", "", f"# {title}", "", "## Transcript", ""]
    for u in items:
        lines.append(f"**[{clock(u.start_ms)}] {u.label}:** {u.text}")
        lines.append("")
    return "\n".join(lines)
