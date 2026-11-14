"""Who a voice is: profile samples and the decision from the nearest ones (ADR-004). Pure.

A sample is a ~20 s stretch of one person's speech: the mean of about ten consecutive clean 2 s windows. Means of
that length compare like whole-speaker centroids (same voice 0.80–0.92, different ≤ 0.47 in the voices report), so
the thresholds below apply to them. `decide` takes the k nearest samples, lets them vote by summed similarity and
judges the winner by its mean similarity: a wrong name is worse than "unknown".
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
import numpy.typing as npt

from lektyra.domain.diarization import Labels, Matrix, normalise

ACCEPT: Final = 0.70
SUGGEST: Final = 0.55
K: Final = 5
CHUNK: Final = 10  # windows per sample (≈ 10–20 s of speech, windows overlap by half)
MAX_SAMPLES: Final = 20
CLEAN: Final = 0.55  # a window less similar than this to its speaker's centroid is not used for a sample

Status = Literal["auto", "suggested", "unknown"]


@dataclass(frozen=True)
class Neighbour:
    person_id: int
    similarity: float


@dataclass(frozen=True)
class Decision:
    person_id: int | None
    score: float
    status: Status
    votes: int


def decide(neighbours: Sequence[Neighbour], k: int = K, accept: float = ACCEPT, suggest: float = SUGGEST) -> Decision:
    """The person the k nearest samples point to, and how sure that is."""
    top = sorted(neighbours, key=lambda n: -n.similarity)[:k]
    if not top:
        return Decision(None, 0.0, "unknown", 0)
    totals: dict[int, list[float]] = {}
    for n in top:
        totals.setdefault(n.person_id, []).append(n.similarity)
    person, sims = max(totals.items(), key=lambda kv: (sum(kv[1]), max(kv[1])))
    score = sum(sims) / len(sims)
    status: Status = "auto" if score >= accept else "suggested" if score >= suggest else "unknown"
    return Decision(person, round(score, 4), status, len(sims))


def ranked(
    neighbours: Sequence[Neighbour], k: int = K, accept: float = ACCEPT, suggest: float = SUGGEST
) -> list[Decision]:
    """Every person among the neighbours, best first, each judged by the mean of their own k closest samples.
    For showing candidates; the name a speaker gets on its own comes from `decide`."""
    per_person: dict[int, list[float]] = {}
    for n in neighbours:
        per_person.setdefault(n.person_id, []).append(n.similarity)
    out: list[Decision] = []
    for person, sims in per_person.items():
        best = sorted(sims, reverse=True)[:k]
        score = sum(best) / len(best)
        status: Status = "auto" if score >= accept else "suggested" if score >= suggest else "unknown"
        out.append(Decision(person, round(score, 4), status, len(best)))
    return sorted(out, key=lambda d: -d.score)


def profile_samples(
    windows: Matrix, labels: Labels, speaker: int, centroid: npt.NDArray[np.float32],
    chunk: int = CHUNK, max_samples: int = MAX_SAMPLES, clean: float = CLEAN, min_windows: int = 1,
) -> Matrix:  # fmt: skip
    """Samples for a speaker's profile: means of `chunk` consecutive clean windows, unit length, at most
    `max_samples`, spread over the whole event (evenly picked when there are more)."""
    unit = normalise(windows)
    centre = centroid / max(float(np.linalg.norm(centroid)), 1e-9)
    mine = [i for i in range(len(unit)) if int(labels[i]) == speaker and float(unit[i] @ centre) >= clean]
    if len(mine) < min_windows:
        mine = []
    groups = [mine[i : i + chunk] for i in range(0, len(mine) - chunk + 1, chunk)]
    if not groups and mine:
        groups = [mine]
    if len(groups) > max_samples:
        step = len(groups) / max_samples
        groups = [groups[int(j * step)] for j in range(max_samples)]
    if not groups:
        return np.zeros((0, unit.shape[1] if unit.ndim == 2 else 0), dtype=np.float32)
    return normalise(np.stack([unit[g].mean(axis=0) for g in groups]).astype(np.float32))
