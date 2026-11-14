"""Diarize an event: speech regions → 2 s windows → ECAPA embeddings → clusters → turns (S1…N).

Writes, in the event folder (data/, git-ignored: embeddings are biometric, ADR-005):
- `vad.npy`: speech probability per 32 ms frame, kept for reuse;
- `diarization.json`: settings, speakers with talk time, turns;
- `speakers.npy`: one centroid per speaker, for matching across events;
- `speakers.md`: per speaker, the longest turns with their time and, when a transcript exists, what was said. Martin
  names speakers from this file; nothing here guesses a name (ADR-004).
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from lektyra.adapters.embed.speechbrain_ecapa import EcapaEmbedder
from lektyra.adapters.media.ffmpeg_ytdlp import decode_file
from lektyra.adapters.vad.silero_onnx import SileroVad, ensure_model
from lektyra.app.ingest import load_manifest
from lektyra.app.transcribe import assemble, variant_of
from lektyra.domain.audio import Curve, Samples, ms_to_samples, samples_from_bytes
from lektyra.domain.diarization import (
    DEFAULT_THRESHOLD,
    UNCLEAR,
    Matrix,
    Turn,
    assign,
    centroids,
    cluster,
    drop_minor,
    group,
    normalise,
    speech_regions,
    turns,
    windows,
)
from lektyra.domain.timefmt import clock
from lektyra.settings import Settings

TEXT_VARIANT = "elevenlabs__scribe-v2@sk"  # the transcript quoted in speakers.md when it exists (top of screening)


@dataclass(frozen=True)
class SpeakerSummary:
    label: str
    talk_s: float
    share: float
    turns: int


@dataclass(frozen=True)
class DiarizeResult:
    event_dir: Path
    speakers: list[SpeakerSummary]
    turns: int
    windows: int


def _speech_probabilities(event_dir: Path, samples: Samples, settings: Settings) -> Curve:
    cached = event_dir / "vad.npy"
    if cached.exists():
        loaded: Curve = np.asarray(np.load(cached), dtype=np.float32)
        return loaded
    vad = SileroVad(ensure_model(settings.data_dir / "models"))
    probs = vad.probabilities(samples)
    np.save(cached, probs)
    return probs


def run_diarize(event_dir: Path, settings: Settings, threshold: float = DEFAULT_THRESHOLD) -> DiarizeResult:
    samples = samples_from_bytes(decode_file(settings.ffmpeg, event_dir / "audio.flac"))
    probs = _speech_probabilities(event_dir, samples, settings)
    regions = speech_regions(probs)
    wins = windows(regions)
    emb = _embeddings(event_dir, samples, wins, settings)
    grouped, _ = group(emb, wins)
    centres = centroids(grouped, drop_minor(cluster(grouped, threshold)))
    labels = assign(emb, centres)
    centres = centroids(emb, labels)  # final centroids from the windows themselves
    found = turns(wins, labels)
    used = sorted({t.speaker for t in found if t.speaker != UNCLEAR})
    by_talk = sorted(used, key=lambda s: -sum(t.end_ms - t.start_ms for t in found if t.speaker == s))
    remap = {old: new for new, old in enumerate(by_talk)}
    remap[UNCLEAR] = UNCLEAR
    found = [Turn(t.start_ms, t.end_ms, remap[t.speaker]) for t in found]
    centres = centres[by_talk] if by_talk else centres[:0]
    total = sum(t.end_ms - t.start_ms for t in found) or 1
    speakers = []
    for s in range(len(by_talk)):
        mine = [t for t in found if t.speaker == s]
        talk = sum(t.end_ms - t.start_ms for t in mine)
        speakers.append(SpeakerSummary(f"S{s + 1}", round(talk / 1000, 1), round(talk / total, 3), len(mine)))

    np.save(event_dir / "speakers.npy", centres.astype(np.float32))
    (event_dir / "diarization.json").write_text(
        json.dumps(
            {
                "embedder": EcapaEmbedder.name,
                "threshold": threshold,
                "windows": len(wins),
                "speakers": [asdict(s) for s in speakers],
                "unclear_s": round(sum(t.end_ms - t.start_ms for t in found if t.speaker == UNCLEAR) / 1000, 1),
                "turns": [{"start_ms": t.start_ms, "end_ms": t.end_ms, "speaker": label_of(t.speaker)} for t in found],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    _write_speakers_md(event_dir, speakers, found)
    return DiarizeResult(event_dir=event_dir, speakers=speakers, turns=len(found), windows=len(wins))


def label_of(speaker: int) -> str:
    return "?" if speaker == UNCLEAR else f"S{speaker + 1}"


def _embeddings(event_dir: Path, samples: Samples, wins: list[tuple[int, int, int]], settings: Settings) -> Matrix:
    """Window embeddings, cached in embeddings.npz next to the audio (biometric: data/ only, ADR-005)."""
    cache = event_dir / "embeddings.npz"
    key = np.array([[a, b, r] for a, b, r in wins], dtype=np.int64)
    if cache.exists():
        saved = np.load(cache)
        if saved["windows"].shape == key.shape and bool((saved["windows"] == key).all()):
            cached: Matrix = np.asarray(saved["emb"], dtype=np.float32)
            return cached
    clips = [samples[ms_to_samples(a) : ms_to_samples(b)] for a, b, _ in wins]
    emb = normalise(EcapaEmbedder(settings.data_dir / "models").embed(clips))
    np.savez(cache, windows=key, emb=emb)
    return emb


def _write_speakers_md(event_dir: Path, speakers: list[SpeakerSummary], found: list[Turn]) -> None:
    manifest = load_manifest(event_dir)
    model, language = variant_of(TEXT_VARIANT)
    lines = [f"# Speakers of {manifest.source.title}", "", "Name them by listening; this file guesses no names.", ""]
    for s_index, s in enumerate(speakers):
        lines.append(f"## {s.label}: {s.talk_s / 60:.1f} min ({s.share:.0%}), {s.turns} turns")
        longest = sorted((t for t in found if t.speaker == s_index), key=lambda t: t.start_ms - t.end_ms)[:3]
        for t in sorted(longest, key=lambda t: t.start_ms):
            text = ""
            if (event_dir / "raw" / TEXT_VARIANT).exists():
                said = assemble(event_dir, model, (t.start_ms, min(t.end_ms, t.start_ms + 20_000)), language)
                text = " ".join(seg.text for seg in said)[:220]
            lines.append(f"- [{clock(t.start_ms)}–{clock(t.end_ms)}] {text}")
        lines.append("")
    (event_dir / "speakers.md").write_text("\n".join(lines), encoding="utf-8")
