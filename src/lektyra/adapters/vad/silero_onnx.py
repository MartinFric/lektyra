"""Silero VAD v5 through onnxruntime: speech probability per 512-sample frame at 16 kHz.

No torch needed. The model file is pinned to a release tag and checked by SHA-256 before it is loaded. It lives
under data/models/ (git-ignored, ADR-005).
"""

import hashlib
import urllib.request
from pathlib import Path
from typing import Final

import numpy as np
import onnxruntime as ort

from lektyra.domain.audio import FRAME_SAMPLES, SAMPLE_RATE, Curve, Samples

MODEL_URL: Final = "https://raw.githubusercontent.com/snakers4/silero-vad/v5.1.2/src/silero_vad/data/silero_vad.onnx"
MODEL_SHA256: Final = "2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f"
CONTEXT_SAMPLES: Final = 64  # v5 sees the last 64 samples of the previous frame, as Silero's own wrapper feeds it


def ensure_model(models_dir: Path) -> Path:
    """The model file, downloaded once and verified."""
    path = models_dir / "silero_vad.onnx"
    if not path.exists():
        models_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
            tmp.write_bytes(response.read())
        tmp.replace(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != MODEL_SHA256:
        raise RuntimeError(f"{path}: SHA-256 {digest} is not the pinned {MODEL_SHA256}; delete it to re-download")
    return path


class SileroVad:
    """A `SpeechDetector`. Keeps the model's recurrent state and context between calls within one stream."""

    def __init__(self, model_path: Path) -> None:
        options = ort.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 1
        self._session = ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])
        self._sr = np.array(SAMPLE_RATE, dtype=np.int64)
        self.reset()

    def reset(self) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, CONTEXT_SAMPLES), dtype=np.float32)

    def probabilities(self, samples: Samples) -> Curve:
        whole = len(samples) // FRAME_SAMPLES
        out = np.empty(whole, dtype=np.float32)
        audio = samples[: whole * FRAME_SAMPLES].astype(np.float32) / 32768.0
        for i in range(whole):
            frame = audio[i * FRAME_SAMPLES : (i + 1) * FRAME_SAMPLES].reshape(1, FRAME_SAMPLES)
            x = np.concatenate([self._context, frame], axis=1)
            prob, state = self._session.run(None, {"input": x, "state": self._state, "sr": self._sr})
            self._state = np.asarray(state, dtype=np.float32)
            self._context = x[:, -CONTEXT_SAMPLES:]
            out[i] = float(np.asarray(prob, dtype=np.float32).reshape(-1)[0])
        return out
