"""Voice embeddings with SpeechBrain's ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`, 192 numbers per clip).

Public on Hugging Face (no token, unlike pyannote's gated models). Downloaded once into data/models/ and copied, not
symlinked (Windows). CPU is enough for the spike. Torch and SpeechBrain are in the `voice` dependency group:
`uv sync --group voice`.
"""

import os
from pathlib import Path
from typing import Any, Final

import numpy as np
import numpy.typing as npt

MODEL: Final = "speechbrain/spkrec-ecapa-voxceleb"
BATCH: Final = 64


class EcapaEmbedder:
    name: Final = "ecapa-voxceleb"

    def __init__(self, models_dir: Path) -> None:
        # Keep Hugging Face's cache with our other models under data/ (ADR-005), quietly: Windows has no symlinks.
        os.environ.setdefault("HF_HOME", str((models_dir / "huggingface").resolve()))
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        import torch
        from speechbrain.inference.speaker import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy

        self._torch: Any = torch
        self._model: Any = EncoderClassifier.from_hparams(
            source=MODEL,
            savedir=str(models_dir / "speechbrain-ecapa"),
            run_opts={"device": "cpu"},
            local_strategy=LocalStrategy.COPY,
        )

    def embed(self, clips: list[npt.NDArray[np.int16]]) -> npt.NDArray[np.float32]:
        """One embedding per clip (16 kHz mono int16), shape (n, 192)."""
        torch = self._torch
        out: list[npt.NDArray[np.float32]] = []
        for i in range(0, len(clips), BATCH):
            batch = clips[i : i + BATCH]
            longest = max(len(c) for c in batch)
            wavs = torch.zeros(len(batch), longest)
            for k, c in enumerate(batch):
                wavs[k, : len(c)] = torch.from_numpy(c.astype(np.float32) / 32768.0)
            lens = torch.tensor([len(c) / longest for c in batch])
            with torch.no_grad():
                emb = self._model.encode_batch(wavs, lens)
            out.append(np.asarray(emb.squeeze(1).cpu().numpy(), dtype=np.float32))
        return np.concatenate(out) if out else np.zeros((0, 192), dtype=np.float32)
