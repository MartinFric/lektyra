"""Transcripts: what an engine heard in one piece, moved to stream time and joined across pieces.

Engines answer per piece, in seconds from the piece's start (which includes the overlap). `to_stream` moves an
answer to stream ms; `join_pieces` stitches consecutive pieces by the rule of ADR-006 (each word or segment taken
from the piece where it lies further from the edge). The hallucination filter is HTN's recorder rule.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from lektyra.domain.chunking import Piece, TimedWord

# Whisper-family inventions on silence or music, learned from subtitle credits in training data (HTN ADR-062),
# plus the Slovak/Czech ones seen on broadcast audio.
INVENTED: Final = (
    "titulky vytvořil",
    "titulky vytvoril",
    "titulky vytvořila",
    "titulky vytvorila",
    "www.hradeckesluzby.cz",
    "ďakujem za pozornosť",
    "děkuji za pozornost",
    "titulky:",
    "amara.org",
)
NO_SPEECH_PROB: Final = 0.6
LOW_LOGPROB: Final = -1.0


@dataclass(frozen=True)
class Segment:
    """A stretch of text with its time; `words` when the engine gave word timestamps."""

    start_ms: int
    end_ms: int
    text: str
    words: tuple[TimedWord, ...] = ()
    no_speech_prob: float | None = None
    avg_logprob: float | None = None

    @property
    def center_ms(self) -> float:
        return (self.start_ms + self.end_ms) / 2


@dataclass(frozen=True)
class Heard:
    """One engine's answer for one piece, parsed: segments in piece time, cost, what was dropped."""

    segments: tuple[Segment, ...]
    text: str
    cost_usd: float | None
    dropped: int = 0


def spoken(text: str) -> str:
    """One line, no Markdown emphasis: nothing heard can forge a speaker label in a transcript (HTN review #1)."""
    return " ".join(text.replace("*", "").replace("`", "").split())


def is_invented(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in INVENTED)


def keep(segment: Segment) -> bool:
    """HTN's rule: drop what the model itself marks as probably not speech, and known inventions."""
    if not segment.text:
        return False
    if (
        segment.no_speech_prob is not None
        and segment.avg_logprob is not None
        and segment.no_speech_prob > NO_SPEECH_PROB
        and segment.avg_logprob < LOW_LOGPROB
    ):
        return False
    return not is_invented(segment.text)


def filtered(heard: Heard) -> Heard:
    kept = tuple(s for s in heard.segments if keep(s))
    return Heard(
        segments=kept,
        text=heard.text,
        cost_usd=heard.cost_usd,
        dropped=heard.dropped + len(heard.segments) - len(kept),
    )


def to_stream(heard: Heard, piece: Piece) -> list[Segment]:
    """Piece time → stream time."""
    shift = piece.start_ms
    return [
        Segment(
            start_ms=s.start_ms + shift,
            end_ms=s.end_ms + shift,
            text=s.text,
            words=tuple(TimedWord(w.text, w.start_ms + shift, w.end_ms + shift) for w in s.words),
            no_speech_prob=s.no_speech_prob,
            avg_logprob=s.avg_logprob,
        )
        for s in heard.segments
    ]


def join_pieces(pieces: Sequence[Piece], per_piece: Sequence[Sequence[Segment]], overlap_ms: int) -> list[Segment]:
    """Join consecutive pieces' segments (stream time) across their overlaps.

    In the overlap before each cut, a segment is kept from the piece where its middle lies further from the edge:
    from the earlier piece if its middle is before (cut - overlap/2), else from the later one.
    """
    if len(pieces) != len(per_piece):
        raise ValueError("one list of segments per piece")
    joined: list[Segment] = []
    for i, segments in enumerate(per_piece):
        lo = -float("inf") if i == 0 else pieces[i].own_start_ms - overlap_ms / 2
        hi = float("inf") if i == len(pieces) - 1 else pieces[i + 1].own_start_ms - overlap_ms / 2
        for s in segments:
            if not s.words:  # no word times: the whole segment goes by its middle
                if lo <= s.center_ms < hi:
                    joined.append(s)
                continue
            kept = tuple(w for w in s.words if lo <= w.center_ms < hi)  # word times: stitch word by word
            if kept:
                joined.append(
                    Segment(
                        start_ms=kept[0].start_ms,
                        end_ms=kept[-1].end_ms,
                        text=" ".join(w.text for w in kept),
                        words=kept,
                        no_speech_prob=s.no_speech_prob,
                        avg_logprob=s.avg_logprob,
                    )
                )
    return joined


def plain_words(text: str) -> list[str]:
    """Lower-case words without punctuation, for comparing engines and scoring (numbers kept as written)."""
    return re.findall(r"[0-9]+(?:[.,][0-9]+)*|[^\W\d_]+", text.lower())
