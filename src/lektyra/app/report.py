"""The transcript with speakers: one engine's words on the diarization's turns, in HTN's Markdown format.

`data/events/<event>/transcript-<variant>.md`. Labels are S1…N (and "?" for unclear stretches) unless Martin has
put names in `names.json` next to the event: `{"S1": "…", "S3": "…"}`. Nothing here guesses a name (ADR-004).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from lektyra.app.ingest import load_manifest
from lektyra.app.transcribe import assemble, model_dir
from lektyra.domain.align import LabelledTurn, Utterance, label_words, render, snap_boundaries, utterances
from lektyra.domain.compare import approx_words
from lektyra.domain.timefmt import clock

_NAMES = TypeAdapter(dict[str, str])


@dataclass(frozen=True)
class ReportResult:
    path: Path
    utterances: int
    words: int
    unknown_words: int


def speaker_names(event_dir: Path) -> dict[str, str]:
    names_file = event_dir / "names.json"
    return _NAMES.validate_json(names_file.read_text(encoding="utf-8")) if names_file.exists() else {}


def speaker_utterances(
    event_dir: Path, model: str, language: str | None, names: Mapping[str, str] | None = None
) -> tuple[list[Utterance], int, int]:
    """The event's words (one engine) on its speaker turns: (utterances, words, words without a speaker).
    Labels are S1…N unless `names` (default: names.json) maps them; the UI passes `{}` and names on its side."""
    diarization = json.loads((event_dir / "diarization.json").read_text(encoding="utf-8"))
    names = speaker_names(event_dir) if names is None else names
    turns = [
        LabelledTurn(t["start_ms"], t["end_ms"], names.get(t["speaker"], t["speaker"])) for t in diarization["turns"]
    ]
    words = [w for s in assemble(event_dir, model, None, language) for w in approx_words(s)]
    labels = label_words(words, snap_boundaries(turns, words))
    return utterances(words, labels), len(words), labels.count("?")


def run_report(event_dir: Path, model: str, language: str | None) -> ReportResult:
    manifest = load_manifest(event_dir)
    diarization = json.loads((event_dir / "diarization.json").read_text(encoding="utf-8"))
    names = speaker_names(event_dir)
    items, n_words, unknown = speaker_utterances(event_dir, model, language)
    speakers = ", ".join(
        f"{names.get(s['label'], s['label'])} {s['talk_s'] / 60:.1f} min" for s in diarization["speakers"]
    )
    front = {
        "source": manifest.source.url,
        "length": clock(manifest.audio_ms),
        "engine": f"{model}{f' ({language})' if language else ''}",
        "diarization": f"{diarization['embedder']}, threshold {diarization['threshold']}",
        "speakers": speakers,
        "names": "from names.json" if names else "none yet (S1…N are voices, not people)",
    }
    path = event_dir / f"transcript-{model_dir(model, language)}.md"
    path.write_text(render(manifest.source.title, front, items), encoding="utf-8")
    return ReportResult(path=path, utterances=len(items), words=n_words, unknown_words=unknown)
