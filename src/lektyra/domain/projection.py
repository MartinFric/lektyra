"""A flat picture of voices: unit fingerprints → two coordinates (PCA). Pure.

Distances on the picture are approximate: 192 dimensions do not fit on a page. The map is for seeing groups; the
similarity a decision uses is always computed in full (ADR-004).
"""

import numpy as np

from lektyra.domain.diarization import Matrix, normalise


def project_2d(points: Matrix) -> Matrix:
    """Rows → (x, y) on the two directions in which the voices differ most, scaled together into [-1, 1]."""
    if len(points) == 0:
        return np.zeros((0, 2), dtype=np.float32)
    if len(points) == 1:
        return np.zeros((1, 2), dtype=np.float32)
    unit = normalise(points)
    centred = unit - unit.mean(axis=0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    flat = centred @ vt[:2].T
    if flat.shape[1] < 2:
        flat = np.hstack([flat, np.zeros((len(flat), 2 - flat.shape[1]), dtype=flat.dtype)])
    reach = float(np.abs(flat).max()) or 1.0  # one scale for both axes: the picture keeps its proportions
    out: Matrix = (flat / reach).astype(np.float32)
    return out
