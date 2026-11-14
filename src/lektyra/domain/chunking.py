"""Where the audio is cut into pieces: in a quiet moment, never inside a word (ADR-006).

`choose_cut` looks at one piece's curves (speech probability and energy, one value per 32 ms frame from the piece's
start) and either returns a cut or `None` (keep listening). `CutPlanner` drives it over an endless stream, and it
decides at exactly the same frames whether the frames arrive one at a time (live) or all at once (a stored video):
replay = live (ADR-007). `stitch` joins the words of overlapping pieces.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
import numpy.typing as npt

from lektyra.domain.audio import FRAME_MS, Curve

CutKind = Literal["pause", "dip", "forced"]


@dataclass(frozen=True)
class CutRule:
    """The numbers of ADR-006, in milliseconds."""

    window_start_ms: int = 45_000  # never cut before this
    decide_at_ms: int = 75_000  # nothing is decided before this much is heard
    hard_max_ms: int = 90_000  # a cut is forced here
    min_pause_ms: int = 250  # a pause: speech probability below the threshold this long
    min_dip_ms: int = 120  # a dip: energy this long in the window's quietest 15 % and >= dip_depth_db under the median
    speech_threshold: float = 0.5
    dip_quantile: float = 0.15
    dip_depth_db: float = 10.0
    turn_bonus_ms: int = 300  # a speaker change inside a pause counts as this much extra silence
    turn_tolerance_ms: int = 150
    overlap_ms: int = 1_500  # each piece starts this much before the previous cut

    def __post_init__(self) -> None:
        if not 0 < self.window_start_ms < self.decide_at_ms <= self.hard_max_ms:
            raise ValueError("need 0 < window_start_ms < decide_at_ms <= hard_max_ms")
        if self.overlap_ms >= self.window_start_ms:
            raise ValueError("the overlap must be shorter than the shortest piece")


DEFAULT_RULE: Final = CutRule()


@dataclass(frozen=True)
class Cut:
    """A cut, `at_ms` from the start of the piece's own audio. `quiet_ms` is the length of the quiet run used."""

    at_ms: int
    kind: CutKind
    quiet_ms: int


def _runs(mask: npt.NDArray[np.bool_], offset: int) -> list[tuple[int, int]]:
    """Runs of True in `mask` as (start, end) frame indices, end exclusive, shifted by `offset`."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(mask.tolist()):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start + offset, i + offset))
            start = None
    if start is not None:
        runs.append((start + offset, len(mask) + offset))
    return runs


def _has_turn(start: int, end: int, turn_changes_ms: Sequence[int], rule: CutRule) -> bool:
    lo = start * FRAME_MS - rule.turn_tolerance_ms
    hi = end * FRAME_MS + rule.turn_tolerance_ms
    return any(lo <= t <= hi for t in turn_changes_ms)


def choose_cut(
    speech_prob: Curve,
    energy_db: Curve,
    turn_changes_ms: Sequence[int] = (),
    rule: CutRule = DEFAULT_RULE,
) -> Cut | None:
    """The best cut in what has been heard of this piece, or None to keep listening.

    `speech_prob` and `energy_db` have one value per 32 ms frame from the piece's start; `turn_changes_ms` are
    speaker changes (from diarization, when known) in ms from the same start.
    """
    if len(speech_prob) != len(energy_db):
        raise ValueError("speech_prob and energy_db must have one value per frame each")
    heard = len(speech_prob)  # frames; compared in frames, as 90 s is 2812 frames = 89,984 ms
    if heard < rule.decide_at_ms // FRAME_MS:
        return None

    lo = -(-rule.window_start_ms // FRAME_MS)  # the first frame starting at or after window_start_ms
    hi = min(heard, rule.hard_max_ms // FRAME_MS)
    window_mid_ms = (rule.window_start_ms + rule.decide_at_ms) // 2
    prob = speech_prob[lo:hi]
    energy = energy_db[lo:hi]

    # 1. The longest pause, a speaker change counting extra; a tie goes to the pause nearer the window's middle.
    best: tuple[int, int, int, int] | None = None  # (score, -distance, start, end)
    for start, end in _runs(prob < rule.speech_threshold, lo):
        length_ms = (end - start) * FRAME_MS
        if length_ms < rule.min_pause_ms:
            continue
        score = length_ms + (rule.turn_bonus_ms if _has_turn(start, end, turn_changes_ms, rule) else 0)
        at_ms = (start + end) * FRAME_MS // 2
        key = (score, -abs(at_ms - window_mid_ms), start, end)
        if best is None or key[:2] > best[:2]:
            best = key
    if best is not None:
        _, _, start, end = best
        return Cut(at_ms=(start + end) * FRAME_MS // 2, kind="pause", quiet_ms=(end - start) * FRAME_MS)

    # 2. The deepest energy dip whose least speech-like frame is not speech: micro-pauses fall between words.
    if len(energy) > 0:
        threshold = min(float(np.quantile(energy, rule.dip_quantile)), float(np.median(energy)) - rule.dip_depth_db)
        best_dip: tuple[float, int, int, int] | None = None  # (mean energy, -length, frame, length)
        for start, end in _runs(energy <= threshold, lo):
            length_ms = (end - start) * FRAME_MS
            if length_ms < rule.min_dip_ms:
                continue
            run_prob = speech_prob[start:end]
            frame = start + int(np.argmin(run_prob))
            if float(speech_prob[frame]) > rule.speech_threshold:
                continue
            key_dip = (float(np.mean(energy_db[start:end])), -length_ms, frame, length_ms)
            if best_dip is None or key_dip[:2] < best_dip[:2]:
                best_dip = key_dip
        if best_dip is not None:
            _, _, frame, length_ms = best_dip
            return Cut(at_ms=frame * FRAME_MS + FRAME_MS // 2, kind="dip", quiet_ms=length_ms)

    # 3. Forced at the hard maximum: the quietest frame of the whole window, speech probability first.
    if heard >= rule.hard_max_ms // FRAME_MS:
        order = np.lexsort((energy, prob))
        frame = lo + int(order[0])
        return Cut(at_ms=frame * FRAME_MS + FRAME_MS // 2, kind="forced", quiet_ms=0)
    return None


@dataclass(frozen=True)
class PlannedCut:
    """A cut in stream time: `at_ms` from the start of the stream."""

    at_ms: int
    kind: CutKind
    quiet_ms: int


class CutPlanner:
    """Feeds a stream's curves to `choose_cut`, piece after piece.

    It evaluates at the same frames however the frames arrive: once when a piece reaches `decide_at_ms`, then at
    every further frame until a cut is found or `hard_max_ms` forces one. Deterministic and I/O-free.
    """

    def __init__(self, rule: CutRule = DEFAULT_RULE) -> None:
        self._rule = rule
        self._prob: list[float] = []
        self._energy: list[float] = []
        self._turns_ms: list[int] = []
        self._piece_start_frame = 0
        self._piece_start_ms = 0

    @property
    def piece_start_ms(self) -> int:
        """Stream time where the current piece's own audio starts (the last cut, or 0)."""
        return self._piece_start_ms

    def add_turn_change(self, at_ms: int) -> None:
        """A speaker change at stream time `at_ms`, when diarization knows it."""
        self._turns_ms.append(at_ms)

    def feed(self, speech_prob: Curve, energy_db: Curve) -> list[PlannedCut]:
        """Append frames; return the cuts they complete, in order."""
        if len(speech_prob) != len(energy_db):
            raise ValueError("speech_prob and energy_db must have one value per frame each")
        cuts: list[PlannedCut] = []
        decide_frames = self._rule.decide_at_ms // FRAME_MS
        for p, e in zip(speech_prob.tolist(), energy_db.tolist(), strict=True):
            self._prob.append(p)
            self._energy.append(e)
            heard = len(self._prob) - self._piece_start_frame
            if heard < decide_frames:
                continue
            cut = self._evaluate()
            if cut is not None:
                cuts.append(cut)
        return cuts

    def _evaluate(self) -> PlannedCut | None:
        start = self._piece_start_frame
        prob = np.asarray(self._prob[start:], dtype=np.float32)
        energy = np.asarray(self._energy[start:], dtype=np.float32)
        turns = [t - self._piece_start_ms for t in self._turns_ms if t >= self._piece_start_ms]
        cut = choose_cut(prob, energy, turns, self._rule)
        if cut is None:
            return None
        at_ms = self._piece_start_ms + cut.at_ms
        self._piece_start_ms = at_ms
        self._piece_start_frame = at_ms // FRAME_MS
        return PlannedCut(at_ms=at_ms, kind=cut.kind, quiet_ms=cut.quiet_ms)


PieceEnd = Literal["pause", "dip", "forced", "end"]


@dataclass(frozen=True)
class Piece:
    """One piece of the stream, in stream ms. `start_ms` includes the overlap; `own_start_ms` is the previous cut."""

    index: int
    start_ms: int
    own_start_ms: int
    end_ms: int
    cut_kind: PieceEnd
    quiet_ms: int


def piece_after(previous_cut_ms: int, index: int, end_ms: int, kind: PieceEnd, quiet_ms: int, overlap_ms: int) -> Piece:
    """The piece that ends at `end_ms`, its own audio starting at the previous cut, plus the overlap before it."""
    return Piece(
        index=index,
        start_ms=max(0, previous_cut_ms - overlap_ms),
        own_start_ms=previous_cut_ms,
        end_ms=end_ms,
        cut_kind=kind,
        quiet_ms=quiet_ms,
    )


@dataclass(frozen=True)
class TimedWord:
    """A word with its time in the stream, in ms."""

    text: str
    start_ms: int
    end_ms: int

    @property
    def center_ms(self) -> float:
        return (self.start_ms + self.end_ms) / 2


def stitch(earlier: Sequence[TimedWord], later: Sequence[TimedWord], cut_ms: int, overlap_ms: int) -> list[TimedWord]:
    """Join two overlapping pieces' words, all in stream time.

    The later piece starts `overlap_ms` before `cut_ms`. In the overlap each word comes from the piece where it lies
    further from that piece's edge. The boundary is the middle of the overlap, so a word cut by either edge is
    dropped and its whole copy kept.
    """
    boundary = cut_ms - overlap_ms / 2
    return [w for w in earlier if w.center_ms < boundary] + [w for w in later if w.center_ms >= boundary]
