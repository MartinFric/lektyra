"""Transcribe an event's pieces with one or more engines (ADR-002, ADR-003).

Every answer is saved verbatim under `data/events/<event>/raw/<model>/<piece>.json` before it is parsed, with a
`.meta.json` beside it: status, cost, wall time, ZDR, timestamps asked. A piece that already has a good answer is
never sent again unless `force`. A failed answer is kept as `.error.json` and retried on the next run. Every call is
appended to `stt-calls.jsonl`.
"""

import json
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Final

from pydantic import SecretStr

from lektyra.adapters.stt.openrouter import OpenRouterTranscriber, error_of, parse
from lektyra.app.ingest import load_manifest
from lektyra.domain.chunking import Piece
from lektyra.domain.transcript import Segment, filtered, join_pieces, to_stream

# The screening round (spike-plan §3): every OpenRouter model that may handle Slovak, cheap to expensive.
SCREENING: Final = (
    "openai/whisper-large-v3",
    "openai/gpt-transcribe",
    "openai/gpt-4o-transcribe",
    "elevenlabs/scribe-v2",
    "assemblyai/universal-3-6-pro",
    "deepgram/nova-3",
    "google/gemini-3.5-transcribe",
    "google/chirp-3",
    "mistralai/voxtral-small-transcribe-3-0",
    "x-ai/grok-stt-2.0",
    "nvidia/parakeet-tdt-0.6b-v3",
)


@dataclass(frozen=True)
class CallRecord:
    model: str
    piece: int
    status: int
    cached: bool
    cost_usd: float | None
    wall_ms: int
    zdr: bool | None
    timestamps_asked: bool | None
    error: str | None
    at: str
    response_format: str | None = None


def model_dir(model: str, language: str | None = None) -> str:
    """The folder of one engine variant: the model, and the pinned language if any (`openai__whisper-large-v3@sk`)."""
    return model.replace("/", "__") + (f"@{language}" if language else "")


def variant_of(folder_name: str) -> tuple[str, str | None]:
    """Inverse of `model_dir`."""
    name, _, language = folder_name.partition("@")
    return name.replace("__", "/"), language or None


def pieces_in(pieces: Sequence[Piece], window_ms: tuple[int, int] | None) -> list[Piece]:
    if window_ms is None:
        return list(pieces)
    lo, hi = window_ms
    return [p for p in pieces if p.end_ms > lo and p.own_start_ms < hi]


def transcribe_piece(
    event_dir: Path,
    model: str,
    piece: Piece,
    *,
    api_key: SecretStr,
    language: str | None,
    force: bool = False,
    lock: "Lock | None" = None,  # threading.Lock is a function at run time on 3.12
    on_call: Callable[[CallRecord], None] = lambda _r: None,
) -> CallRecord:
    """One piece through one engine; the raw answer is kept next to the audio (ADR-003). Used by batch runs
    and by a live session, piece by piece."""
    ledger = event_dir / "stt-calls.jsonl"
    guard = lock or Lock()
    folder = event_dir / "raw" / model_dir(model, language)
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / f"{piece.index:04d}.json"
    meta = folder / f"{piece.index:04d}.meta.json"
    if raw.exists() and meta.exists() and not force:
        m = json.loads(meta.read_text(encoding="utf-8"))
        return CallRecord(model, piece.index, 200, True, m.get("cost_usd"), m.get("wall_ms", 0), m.get("zdr"),
                          m.get("timestamps_asked"), None, m.get("at", ""))  # fmt: skip
    audio = (event_dir / "pieces" / f"{piece.index:04d}.flac").read_bytes()
    answer = OpenRouterTranscriber(api_key, model, language).transcribe(audio, "flac")
    at = datetime.now().astimezone().isoformat(timespec="seconds")
    cost: float | None = None
    error: str | None = None
    if answer.status == 200:
        try:
            cost = parse(answer.body, piece.end_ms - piece.start_ms).cost_usd
        except ValueError as problem:
            error = str(problem)
    else:
        error = f"HTTP {answer.status}: {error_of(answer.body)}"
    record = CallRecord(model, piece.index, answer.status, False, cost, answer.wall_ms, answer.zdr,
                        answer.timestamps_asked, error, at, answer.response_format)  # fmt: skip
    body = {k: v for k, v in asdict(record).items() if k not in ("cached",)}
    if error is None:
        raw.write_text(answer.body, encoding="utf-8")
        meta.write_text(json.dumps(body, indent=2), encoding="utf-8")
    else:
        (folder / f"{piece.index:04d}.error.json").write_text(
            json.dumps({**body, "body": answer.body[:2000]}, indent=2), encoding="utf-8"
        )
    with guard:
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(body) + "\n")
        on_call(record)
    return record


def run_transcribe(
    event_dir: Path,
    models: Sequence[str],
    *,
    api_key: SecretStr,
    window_ms: tuple[int, int] | None = None,
    force: bool = False,
    workers: int = 8,
    language: str | None = None,
    on_call: Callable[[CallRecord], None] = lambda _r: None,
) -> list[CallRecord]:
    manifest = load_manifest(event_dir)
    chosen = pieces_in(manifest.pieces, window_ms)
    lock = Lock()

    def one(model: str, piece: Piece) -> CallRecord:
        return transcribe_piece(
            event_dir, model, piece, api_key=api_key, language=language, force=force, lock=lock, on_call=on_call
        )

    tasks = [(m, p) for p in chosen for m in models]  # interleaved: no single model gets a burst
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda t: one(*t), tasks))


def assemble(
    event_dir: Path, model: str, window_ms: tuple[int, int] | None = None, language: str | None = None
) -> list[Segment]:
    """One model's transcript of the event (or a window), stream time, joined across pieces. Reads saved answers."""
    manifest = load_manifest(event_dir)
    chosen = pieces_in(manifest.pieces, window_ms)
    per_piece: list[list[Segment]] = []
    for piece in chosen:
        raw = event_dir / "raw" / model_dir(model, language) / f"{piece.index:04d}.json"
        if not raw.exists():
            per_piece.append([])
            continue
        heard = filtered(parse(raw.read_text(encoding="utf-8"), piece.end_ms - piece.start_ms))
        per_piece.append(to_stream(heard, piece))
    joined = join_pieces(chosen, per_piece, manifest.rule.overlap_ms)
    if window_ms is None:
        return joined
    lo, hi = window_ms
    return [s for s in joined if lo <= s.center_ms < hi]
