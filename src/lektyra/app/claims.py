"""Replay an event through the claims loop, minute by minute, exactly as it would run live (spike-plan §8).

Each minute: the new minute plus two minutes of context and the ledger digest go to the extractor. Its answer is
saved verbatim under `data/events/<event>/claims/<model>/mNNN.json` (ADR-003), then `step` applies it. A saved answer
is reused unless `force`, so a replay is free and deterministic. After every minute the ledger is written to
`claims-<model>.json` and `claims-<model>.md`, which is what a live run would show as it goes.
"""

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic import SecretStr, TypeAdapter

from lektyra.adapters.llm.openrouter_claims import END_PASS, OpenRouterClaimExtractor, parse
from lektyra.app.ingest import load_manifest
from lektyra.app.report import speaker_utterances
from lektyra.app.transcribe import model_dir
from lektyra.domain.claims import MINUTE_MS, Claim, Ledger, ledger_digest, minute_window, step
from lektyra.domain.timefmt import clock


@dataclass(frozen=True)
class MinuteRecord:
    minute: int
    actions: int
    problems: list[str]
    cost_usd: float | None
    wall_ms: int
    cached: bool
    error: str | None


@dataclass(frozen=True)
class ClaimsResult:
    ledger: Ledger
    minutes: list[MinuteRecord]
    json_path: Path
    md_path: Path


def run_claims(
    event_dir: Path,
    *,
    api_key: SecretStr,
    llm: str,
    engine: str,
    language: str | None,
    until_minute: int | None = None,
    force: bool = False,
    on_minute: Callable[[MinuteRecord, Ledger], None] = lambda _r, _l: None,
) -> ClaimsResult:
    manifest = load_manifest(event_dir)
    items, _, _ = speaker_utterances(event_dir, engine, language)
    folder = event_dir / "claims" / model_dir(llm)
    folder.mkdir(parents=True, exist_ok=True)
    extractor = OpenRouterClaimExtractor(api_key, llm)
    last = -(-manifest.audio_ms // MINUTE_MS)
    if until_minute is not None:
        last = min(last, until_minute)
    ledger = Ledger()
    records: list[MinuteRecord] = []
    json_path = event_dir / f"claims-{model_dir(llm)}.json"
    md_path = event_dir / f"claims-{model_dir(llm)}.md"

    for minute in range(1, last + 1):
        context, new = minute_window(items, minute)
        start_ms = (minute - 1) * MINUTE_MS
        if not new.strip():
            ledger = step(ledger, minute, [])
            continue
        raw = folder / f"m{minute:03d}.json"
        cached = raw.exists() and not force
        error: str | None = None
        wall = 0
        if cached:
            body = raw.read_text(encoding="utf-8")
        else:
            user = (
                f"LEDGER:\n{ledger_digest(ledger)}\n\nCONTEXT (already processed):\n{context or '(none)'}\n\n"
                f"NEW MINUTE {clock(start_ms)}-{clock(start_ms + MINUTE_MS)}:\n{new}"
            )
            answer = extractor.ask(user)
            body, wall = answer.body, answer.wall_ms
            if answer.status == 200:
                raw.write_text(body, encoding="utf-8")
            else:
                error = f"HTTP {answer.status}"
        try:
            parsed = parse(body, start_ms)
            ledger = step(ledger, minute, parsed.actions)
            record = MinuteRecord(minute, len(parsed.actions), parsed.problems, parsed.cost_usd, wall, cached, error)
        except ValueError as problem:
            ledger = step(ledger, minute, [])
            record = MinuteRecord(minute, 0, [], None, wall, cached, error or str(problem))
        records.append(record)
        _write(ledger, records, json_path, md_path, manifest.source.title, llm, engine)
        on_minute(record, ledger)
    _write(ledger, records, json_path, md_path, manifest.source.title, llm, engine)
    return ClaimsResult(ledger=ledger, minutes=records, json_path=json_path, md_path=md_path)


def _write(ledger: Ledger, records: list[MinuteRecord], json_path: Path, md_path: Path, title: str, llm: str,
           engine: str) -> None:  # fmt: skip
    body = json.dumps({"ledger": asdict(ledger), "minutes": [asdict(r) for r in records]}, ensure_ascii=False, indent=1)
    _replace(json_path, body)  # the UI reads these while a live run writes them: never half a file
    _replace(md_path, _markdown(ledger, records, title, llm, engine))


def _replace(path: Path, text: str) -> None:
    part = path.with_name(path.name + ".part")
    part.write_text(text, encoding="utf-8")
    part.replace(path)


def _row(c: Claim) -> str:
    links = ", ".join(f"{rel} {other}" for rel, other in c.links)
    flags = " ~~withdrawn~~" if c.status == "withdrawn" else ""
    return (
        f"| {c.id}{flags} | {clock(c.at_ms)} | {c.speaker} | {c.worth:.2f} | {c.kind} | {c.lekton} | "
        f"{', '.join(c.sources)} | {links} | {' · '.join(c.history)} |"
    )


def _markdown(ledger: Ledger, records: list[MinuteRecord], title: str, llm: str, engine: str) -> str:
    cost = sum(r.cost_usd or 0.0 for r in records)
    open_claims = [c for c in ledger.claims if c.status == "open"]
    top = sorted(open_claims, key=lambda c: -c.worth)[:15]
    head = (
        "| id | at | speaker | worth | kind | lekton | check in | links | history |\n"
        "|---|---|---|---|---|---|---|---|---|"
    )
    lines = [
        f"# Claims: {title}",
        "",
        f"Replay minute by minute (spike-plan §8) · extractor `{llm}` · transcript `{engine}` · "
        f"{ledger.minute} minutes · {len(ledger.claims)} claims ({len(open_claims)} open) · "
        f"{sum(len(c.links) for c in ledger.claims)} links · cost ${cost:.3f}",
        "",
        "Speakers are the event's voice labels; names come from names.json, never guessed (ADR-004).",
        "These are candidates for checking, not verdicts.",
        "",
        "## Most worth checking",
        "",
        head,
        *[_row(c) for c in top],
        "",
        "## All, in order",
        "",
        head,
        *[_row(c) for c in ledger.claims],
    ]
    if ledger.rejected:
        lines += ["", "## Rejected actions (unknown ids)", "", *[f"- {r}" for r in ledger.rejected]]
    problems = [f"- m{r.minute}: {p}" for r in records for p in r.problems] + [
        f"- m{r.minute}: {r.error}" for r in records if r.error
    ]
    if problems:
        lines += ["", "## Problems", "", *problems]
    return "\n".join(lines) + "\n"


_LEDGER = TypeAdapter(Ledger)


@dataclass(frozen=True)
class EndPassResult:
    before: Ledger
    after: Ledger
    added: list[Claim]
    linked: int
    withdrawn: int
    amended: int
    problems: list[str]
    cost_usd: float | None
    md_path: Path


def run_end_pass(
    event_dir: Path, *, api_key: SecretStr, llm: str, engine: str, language: str | None, force: bool = False
) -> EndPassResult:
    """The whole-picture review after the event (spike-plan §8). What it adds is what the live loop missed."""
    manifest = load_manifest(event_dir)
    saved = json.loads((event_dir / f"claims-{model_dir(llm)}.json").read_text(encoding="utf-8"))
    before = _LEDGER.validate_python(saved["ledger"])
    items, _, _ = speaker_utterances(event_dir, engine, language)
    transcript = "\n".join(f"[{clock(u.start_ms)}] {u.label}: {u.text}" for u in items)
    raw = event_dir / "claims" / model_dir(llm) / "end.json"
    if raw.exists() and not force:
        body = raw.read_text(encoding="utf-8")
    else:
        user = f"LEDGER:\n{ledger_digest(before, limit=500)}\n\nWHOLE TRANSCRIPT:\n{transcript}"
        answer = OpenRouterClaimExtractor(api_key, llm).ask(user, system=END_PASS)
        body = answer.body
        if answer.status != 200:
            raise ValueError(f"end pass failed: HTTP {answer.status}: {body[:300]}")
        raw.write_text(body, encoding="utf-8")
    parsed = parse(body, 0)
    after = step(before, before.minute + 1, parsed.actions)
    added = list(after.claims[len(before.claims) :])
    tag = f"m{before.minute + 1} "
    changed = [c for c in after.claims[: len(before.claims)] if any(h.startswith(tag) for h in c.history)]
    linked = sum(1 for c in changed for h in c.history if h.startswith(tag + "link"))
    withdrawn = sum(1 for c in changed for h in c.history if h.startswith(tag + "withdraw"))
    amended = sum(1 for c in changed for h in c.history if h.startswith(tag + "amend"))
    md_path = event_dir / f"claims-{model_dir(llm)}-final.md"
    summary = [
        "## End-of-event pass",
        "",
        f"- live ledger: {len(before.claims)} claims; the end pass **added {len(added)}** (missed live), "
        f"linked {linked}, withdrew {withdrawn} (duplicates, corrections), amended {amended}",
        f"- live recall against the final ledger: {len(before.claims) / max(1, len(before.claims) + len(added)):.0%}",
        *[f"- problem: {p}" for p in parsed.problems],
        "",
    ]
    page = _markdown(after, [], manifest.source.title, llm, engine)
    page = page.replace("## Most worth checking", "\n".join(summary) + "\n## Most worth checking", 1)
    md_path.write_text(page, encoding="utf-8")
    (event_dir / f"claims-{model_dir(llm)}-final.json").write_text(
        json.dumps({"ledger": asdict(after)}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return EndPassResult(before, after, added, linked, withdrawn, amended, parsed.problems, parsed.cost_usd, md_path)
