"""Who speaks when, from voice embeddings (pure: numpy only; the embedder is an adapter).

1. `speech_regions`: stretches of speech from the speech-probability curve (Silero, 32 ms frames).
2. `windows`: 2 s windows every 1 s inside them, embedded by the adapter.
3. `group`: three consecutive windows of one region averaged into a ~4 s group: fewer, steadier points.
4. `cluster`: average-linkage clustering on cosine distance, stopping at `threshold`: S1…N, largest first.
5. `assign` + `turns`: every window goes to its nearest speaker centroid; runs shorter than `min_turn_ms` are
   absorbed by their neighbours.

Speaker numbers are per event. Matching across events is `similarity` of centroids (ADR-004 builds on it).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from lektyra.domain.audio import FRAME_MS, Curve

Matrix = npt.NDArray[np.float32]
Labels = npt.NDArray[np.int64]

WINDOW_MS: Final = 2_000
HOP_MS: Final = 1_000
GROUP: Final = 3
DEFAULT_THRESHOLD: Final = 0.55  # cosine distance at which two groups are no longer the same voice (tuned on A)


@dataclass(frozen=True)
class Turn:
    start_ms: int
    end_ms: int
    speaker: int  # 0-based, shown as S{speaker + 1}; UNCLEAR (-1) shown as "?"


def speech_regions(
    prob: Curve, threshold: float = 0.5, min_ms: int = 600, bridge_ms: int = 300
) -> list[tuple[int, int]]:
    """Speech stretches in ms; gaps shorter than `bridge_ms` are bridged, stretches shorter than `min_ms` dropped."""
    regions: list[tuple[int, int]] = []
    start: int | None = None
    for i, p in enumerate(prob.tolist()):
        if p >= threshold and start is None:
            start = i
        elif p < threshold and start is not None:
            regions.append((start * FRAME_MS, i * FRAME_MS))
            start = None
    if start is not None:
        regions.append((start * FRAME_MS, len(prob) * FRAME_MS))
    bridged: list[tuple[int, int]] = []
    for a, b in regions:
        if bridged and a - bridged[-1][1] < bridge_ms:
            bridged[-1] = (bridged[-1][0], b)
        else:
            bridged.append((a, b))
    return [(a, b) for a, b in bridged if b - a >= min_ms]


def windows(
    regions: Sequence[tuple[int, int]], window_ms: int = WINDOW_MS, hop_ms: int = HOP_MS
) -> list[tuple[int, int, int]]:
    """(start, end, region index) windows inside each region; a region shorter than a window gives one window."""
    out: list[tuple[int, int, int]] = []
    for r, (a, b) in enumerate(regions):
        if b - a <= window_ms:
            out.append((a, b, r))
            continue
        t = a
        while t + window_ms <= b:
            out.append((t, t + window_ms, r))
            t += hop_ms
        if out[-1][1] < b:
            out.append((b - window_ms, b, r))
    return out


def normalise(x: Matrix) -> Matrix:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return (x / np.maximum(norms, 1e-9)).astype(np.float32)


def group(
    embeddings: Matrix, wins: Sequence[tuple[int, int, int]], size: int = GROUP
) -> tuple[Matrix, list[list[int]]]:
    """Average runs of `size` consecutive windows of the same region. Returns group embeddings and their members."""
    members: list[list[int]] = []
    for i, (_, _, region) in enumerate(wins):
        if members and len(members[-1]) < size and wins[members[-1][0]][2] == region:
            members[-1].append(i)
        else:
            members.append([i])
    unit = normalise(embeddings)
    grouped = np.stack([unit[m].mean(axis=0) for m in members]) if members else np.zeros((0, unit.shape[1]))
    return normalise(grouped.astype(np.float32)), members


def cluster(points: Matrix, threshold: float = DEFAULT_THRESHOLD) -> Labels:
    """Average-linkage clustering on cosine distance; merging stops when the closest clusters are farther apart than
    `threshold`. Labels 0..k-1, the largest cluster 0."""
    n = len(points)
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    unit = normalise(points)
    dist = (1.0 - unit @ unit.T).astype(np.float64)
    np.fill_diagonal(dist, np.inf)
    size = np.ones(n)
    parent = np.arange(n)
    alive = np.ones(n, dtype=bool)
    while alive.sum() > 1:
        flat = int(np.argmin(dist))
        i, j = divmod(flat, n)
        if dist[i, j] > threshold:
            break
        # Lance–Williams for average linkage: the merged row is the size-weighted mean of the two rows.
        merged = (size[i] * dist[i] + size[j] * dist[j]) / (size[i] + size[j])
        dist[i, :] = merged
        dist[:, i] = merged
        dist[i, i] = np.inf
        dist[j, :] = np.inf
        dist[:, j] = np.inf
        size[i] += size[j]
        alive[j] = False
        parent[parent == j] = i
    roots, labels = np.unique(parent, return_inverse=True)
    counts = np.bincount(labels, minlength=len(roots))
    order = np.argsort(-counts, kind="stable")
    rank = np.empty_like(order)
    rank[order] = np.arange(len(order))
    return rank[labels].astype(np.int64)


UNCLEAR: Final = -1  # a window that belongs to no clear speaker: cross-talk, a jingle, a voice heard for seconds
MIN_SHARE: Final = 0.01  # a cluster with less than 1 % of the groups is not counted as a speaker
ASSIGN_FLOOR: Final = 0.30  # a window less similar than this to every speaker is UNCLEAR, not forced onto one


def drop_minor(labels: Labels, min_share: float = MIN_SHARE, min_count: int = 5) -> Labels:
    """Clusters smaller than `min_share` of all points (and than `min_count`) become UNCLEAR; the rest renumbered
    0..k-1, largest first."""
    if len(labels) == 0:
        return labels
    counts = np.bincount(labels[labels >= 0])
    keep = [
        c for c in np.argsort(-counts, kind="stable").tolist() if counts[c] >= max(min_count, min_share * len(labels))
    ]
    new = {old: i for i, old in enumerate(keep)}
    return np.array([new.get(int(x), UNCLEAR) for x in labels], dtype=np.int64)


def centroids(points: Matrix, labels: Labels) -> Matrix:
    """One unit centroid per speaker 0..k-1 (UNCLEAR points are left out)."""
    k = int(labels.max()) + 1 if len(labels) and labels.max() >= 0 else 0
    return (
        normalise(np.stack([points[labels == c].mean(axis=0) for c in range(k)]).astype(np.float32))
        if k
        else points[:0]
    )


def assign(embeddings: Matrix, centres: Matrix, floor: float = ASSIGN_FLOOR) -> Labels:
    """Each window to its nearest centroid (cosine), or UNCLEAR when no centroid is at least `floor` similar."""
    if len(centres) == 0:
        return np.full(len(embeddings), UNCLEAR, dtype=np.int64)
    sims = normalise(embeddings) @ centres.T
    best = np.argmax(sims, axis=1).astype(np.int64)
    best[sims.max(axis=1) < floor] = UNCLEAR
    return best


def turns(wins: Sequence[tuple[int, int, int]], labels: Labels, min_turn_ms: int = 1_500) -> list[Turn]:
    """Windows → speaker turns. Overlapping windows split at their midpoint; short runs join their neighbours."""
    if not wins:
        return []
    raw: list[Turn] = []
    for k, (a, b, _) in enumerate(wins):
        start = a if k == 0 or wins[k - 1][1] <= a else (a + wins[k - 1][1]) // 2
        end = b if k == len(wins) - 1 or wins[k + 1][0] >= b else (b + wins[k + 1][0]) // 2
        speaker = int(labels[k])
        if raw and raw[-1].speaker == speaker and start - raw[-1].end_ms < 500:
            raw[-1] = Turn(raw[-1].start_ms, end, speaker)
        else:
            raw.append(Turn(start, end, speaker))
    changed = True
    while changed and len(raw) > 1:
        changed = False
        for k, t in enumerate(raw):
            if t.end_ms - t.start_ms >= min_turn_ms:
                continue
            neighbour = k - 1 if k > 0 else k + 1
            if (
                0 < k < len(raw) - 1
                and raw[k + 1].end_ms - raw[k + 1].start_ms > raw[k - 1].end_ms - raw[k - 1].start_ms
            ):
                neighbour = k + 1
            n = raw[neighbour]
            raw[neighbour] = Turn(min(n.start_ms, t.start_ms), max(n.end_ms, t.end_ms), n.speaker)
            del raw[k]
            changed = True
            break
    merged: list[Turn] = []
    for t in raw:
        if merged and merged[-1].speaker == t.speaker and t.start_ms - merged[-1].end_ms < 500:
            merged[-1] = Turn(merged[-1].start_ms, t.end_ms, t.speaker)
        else:
            merged.append(t)
    return merged


def similarity(a: Matrix, b: Matrix) -> Matrix:
    """Cosine similarity of every centroid in `a` with every one in `b`."""
    return (normalise(a) @ normalise(b).T).astype(np.float32)
