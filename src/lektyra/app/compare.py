"""The comparison page Martin writes references from (spike-plan §6), and the reference template.

`data/events/<event>/compare-<from>-<to>.html`: every engine variant side by side in 10 s rows, the words fewer than
half of the other engines heard highlighted, rows ranked by disagreement, and each row's time playing the audio from
that second (the page sits next to `audio.flac`). The template `data/refs/<event>_<from>-<to>.md` holds, per row, the
text of the engine that agrees most with the others in that row (a different engine per row, so no engine is
favoured), and marks the rows worth listening to.

Both stay under `data/`: a reference is a transcript of the broadcast (ADR-005).
"""

import html
import json
from dataclasses import dataclass
from pathlib import Path

from lektyra.app.ingest import load_manifest
from lektyra.app.transcribe import assemble, variant_of
from lektyra.domain.compare import RowComparison, compare_row, mean_agreement, row_texts
from lektyra.domain.timefmt import clock
from lektyra.domain.transcript import plain_words

ROW_MS = 10_000
LISTEN_SHARE = 0.25  # the quarter of rows where engines disagree most are marked LISTEN
LISTEN_FLOOR = 0.15  # …but never a row where they nearly agree
MIN_COVERAGE = 0.8  # an engine variant appears only if it answered this share of the window's pieces


@dataclass(frozen=True)
class VariantSummary:
    variant: str
    answered: int
    failed: int
    cost_usd: float
    timing: str  # "words" or "approx"
    agreement: float


@dataclass(frozen=True)
class CompareResult:
    page: Path
    template: Path
    variants: list[VariantSummary]
    rows: int
    listen_rows: int


def _variants(event_dir: Path) -> list[str]:
    raw = event_dir / "raw"
    return sorted(d.name for d in raw.iterdir() if d.is_dir() and any(d.glob("*.json"))) if raw.exists() else []


def _cost_and_counts(event_dir: Path, variant: str, pieces: set[int]) -> tuple[int, int, float]:
    folder = event_dir / "raw" / variant
    answered = failed = 0
    cost = 0.0
    for p in pieces:
        meta = folder / f"{p:04d}.meta.json"
        if meta.exists():
            answered += 1
            cost += float(json.loads(meta.read_text(encoding="utf-8")).get("cost_usd") or 0.0)
        elif (folder / f"{p:04d}.error.json").exists():
            failed += 1
    return answered, failed, cost


def run_compare(event_dir: Path, window_ms: tuple[int, int], refs_dir: Path) -> CompareResult:
    manifest = load_manifest(event_dir)
    lo, hi = window_ms
    piece_ids = {p.index for p in manifest.pieces if p.end_ms > lo and p.own_start_ms < hi}
    rows_by: dict[str, list[str]] = {}
    timing: dict[str, str] = {}
    for variant in _variants(event_dir):
        answered, _, _ = _cost_and_counts(event_dir, variant, piece_ids)
        if answered < MIN_COVERAGE * len(piece_ids):
            continue  # a variant tried on a piece or two (a smoke test) is not a column
        model, language = variant_of(variant)
        segments = assemble(event_dir, model, window_ms, language)
        if not segments:
            continue
        rows_by[variant] = row_texts(segments, lo, hi, ROW_MS)
        timing[variant] = "words" if all(s.words for s in segments) else "approx"
    if not rows_by:
        raise ValueError(f"no saved answers in {event_dir / 'raw'} for that window: run transcribe first")

    summaries = []
    for v in rows_by:
        answered, failed, cost = _cost_and_counts(event_dir, v, piece_ids)
        summaries.append(VariantSummary(v, answered, failed, cost, timing[v], mean_agreement(rows_by, v)))
    summaries.sort(key=lambda s: -s.agreement)
    order = [s.variant for s in summaries]
    n_rows = len(next(iter(rows_by.values())))
    comparisons = [compare_row(rows_by, k) for k in range(n_rows)]
    ranked = sorted((c.disagreement for c in comparisons), reverse=True)
    cutoff = max(LISTEN_FLOOR, ranked[max(0, round(len(ranked) * LISTEN_SHARE) - 1)] if ranked else 1.0)

    tag = f"{clock(lo).replace(':', '')}-{clock(hi).replace(':', '')}"
    page = event_dir / f"compare-{tag}.html"
    page.write_text(
        _page(manifest.source.title, lo, hi, order, summaries, rows_by, comparisons, cutoff), encoding="utf-8"
    )

    refs_dir.mkdir(parents=True, exist_ok=True)
    template = refs_dir / f"{event_dir.name}_{tag}.md"
    listen = 0
    lines = [
        f"<!-- Reference for {manifest.source.title}, {clock(lo)}–{clock(hi)}. Correct each line by listening; mark",
        "     speakers S1, S2, … (the same person keeps the same number). Lines marked LISTEN: the engines disagreed",
        f"     most there. Prefilled per row from the engine that agreed most with the others. Page: {page.name} -->",
        "",
    ]
    for k, c in enumerate(comparisons):
        mark = ""
        if c.disagreement >= cutoff:
            listen += 1
            mark = f"  <!-- LISTEN {c.disagreement:.2f} -->"
        lines.append(f"**[{clock(lo + k * ROW_MS)}] ?:** {rows_by[c.medoid][k]}{mark}")
    if not template.exists():  # never overwrite Martin's work
        template.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return CompareResult(page=page, template=template, variants=summaries, rows=n_rows, listen_rows=listen)


def _cell(text: str, minority: set[str]) -> str:
    out = []
    for token in text.split():
        words = plain_words(token)
        esc = html.escape(token)
        out.append(f"<mark>{esc}</mark>" if words and any(w in minority for w in words) else esc)
    return " ".join(out) or '<span class="empty">—</span>'


def _page(title: str, lo: int, hi: int, order: list[str], summaries: list[VariantSummary],
          rows_by: dict[str, list[str]], comparisons: list[RowComparison], cutoff: float) -> str:  # fmt: skip
    head = "".join(f"<th>{html.escape(v)}</th>" for v in order)
    summary_rows = "".join(
        f"<tr><td>{html.escape(s.variant)}</td><td>{s.agreement:.2f}</td><td>{s.answered}</td><td>{s.failed}</td>"
        f"<td>${s.cost_usd:.4f}</td><td>{s.timing}</td></tr>"
        for s in summaries
    )
    body = []
    for k, c in enumerate(comparisons):
        t = lo + k * ROW_MS
        level = "hi" if c.disagreement >= cutoff else ("mid" if c.disagreement >= cutoff * 0.66 else "lo")
        cells = "".join(f"<td>{_cell(rows_by[v][k], c.minority.get(v, set()))}</td>" for v in order)
        body.append(
            f'<tr class="{level}"><th><button onclick="play({t / 1000:.1f})">{clock(t)}</button>'
            f'<div class="d">{c.disagreement:.2f}</div></th>{cells}</tr>'
        )
    return f"""<!doctype html><html lang="sk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>lektyra · {html.escape(title)}</title>
<style>
:root {{ --bg:#fff; --fg:#1b1b1b; --mute:#666; --line:#ddd; --mark:#ffe08a; --hi:#fde2e2; --mid:#fff6dd; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141414; --fg:#e8e8e8; --mute:#999; --line:#333;
  --mark:#7a5d00; --hi:#4a1f1f; --mid:#3d3420; }} }}
body {{ background:var(--bg); color:var(--fg); font:14px/1.45 system-ui,sans-serif; margin:16px; }}
h1 {{ font-size:18px; margin:0 0 4px; }} .sub {{ color:var(--mute); margin-bottom:12px; }}
#player {{ position:sticky; top:0; background:var(--bg); padding:6px 0; z-index:3;
  border-bottom:1px solid var(--line); }}
audio {{ width:100%; }}
table {{ border-collapse:collapse; width:100%; }}
td, th {{ border:1px solid var(--line); padding:6px; vertical-align:top; }}
thead th {{ position:sticky; top:58px; background:var(--bg); font-size:12px; z-index:2; }}
tbody th {{ white-space:nowrap; width:70px; }}
.d {{ color:var(--mute); font-size:11px; font-weight:normal; }}
tr.hi > th {{ background:var(--hi); }} tr.mid > th {{ background:var(--mid); }}
mark {{ background:var(--mark); color:inherit; }} .empty {{ color:var(--mute); }}
button {{ font:inherit; cursor:pointer; }} .summary td, .summary th {{ font-size:12px; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="sub">{clock(lo)}–{clock(hi)} · rows of {ROW_MS // 1000} s ·
<mark>highlighted</mark> = fewer than half of the other engines heard it nearby ·
red rows: listen first · click a time to play from there</div>
<table class="summary">
<tr><th>engine</th><th>agreement</th><th>pieces</th><th>failed</th><th>cost</th><th>timing</th></tr>
{summary_rows}</table><br>
<div id="player"><audio id="a" src="audio.flac" controls preload="metadata"></audio></div>
<table><thead><tr><th>time</th>{head}</tr></thead><tbody>
{"".join(body)}
</tbody></table>
<script>const a=document.getElementById('a');function play(t){{a.currentTime=Math.max(0,t-1);a.play();}}</script>
</body></html>
"""
