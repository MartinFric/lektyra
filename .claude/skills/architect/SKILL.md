---
name: architect
description: Where code goes in lektyra (domain, ports, adapters, app, cli), what a new source, engine or feature needs, and when a change needs an ADR. Use before adding a module, a dependency or a new kind of input.
---

# Where code goes

| layer | path | may import | does |
|---|---|---|---|
| domain | `src/lektyra/domain/` | stdlib (no I/O), numpy, other domain modules | the logic: cutting, stitching, alignment, matching, profiles, claims, metrics. Pure; unit-tested |
| ports | `src/lektyra/ports.py` | domain, pydantic | `Protocol`s and the boundary models (`SourceInfo`) |
| adapters | `src/lektyra/adapters/<area>/` | anything | one outside thing each (ffmpeg, yt-dlp, a TV site, an API, a model). Translate to domain types. `Any` allowed here only |
| app | `src/lektyra/app/` | domain, ports, adapters, settings | one use case per module; wires adapters to domain; the composition root |
| cli | `src/lektyra/cli.py` | app, settings | parses arguments, prints. Nothing else prints |

Hook L4 enforces the domain's purity; dependency direction is reviewed.

## Adding…

- **A source site** (a TV station, a parliament player): a `SiteResolver` in `adapters/media/<site>.py`
  (`matches`, `resolve` → `SourceInfo` with `media_url` that ffmpeg can open). Register it in `app/ingest.py`.
  Parsing helpers are pure functions with contract tests on synthetic snippets (`tests/contract/test_ta3.py`).
  Tokens in URLs stay in `media_url` (excluded from saved files).
- **A speech-to-text engine**: see the `stt-engine` skill. An OpenRouter model is a name; a provider is an adapter.
- **A model** (VAD, diarizer, embedder): an adapter; the model file is pinned (URL + SHA-256) and lives under
  `data/models/`.
- **A dependency**: `uv add` and the reason in the board note. A heavy one (torch) goes in its own dependency
  group, added when the first adapter needs it.

## When a change needs an ADR

A new ADR when a change:
- alters a rule in `principles`;
- adds a kind of data that is stored;
- changes what leaves the PC;
- changes how identity or verdicts are decided;
- introduces a new layer.

Format: `docs/adr/NNN-title.md` with status, date, context, decision, consequences, enforced by. Add it to
`docs/adr/README.md`. An ADR is superseded, never silently edited.
