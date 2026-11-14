# Architecture decision records

An ADR wins over instinct and over the plan. A change of mind is a new ADR that supersedes the old one, never a
silent edit. Each record: status, date, context, decision, consequences, and **enforced by** (the hook rule, test or
review that keeps it true).

| ADR | title | status |
|---|---|---|
| [001](001-python-uv-mypy-strict.md) | Python 3.12, uv, mypy strict, data parsed at the boundary | accepted |
| [002](002-ports-and-adapters.md) | Ports and adapters; the domain is pure; OpenRouter is the speech-to-text gateway | accepted |
| [003](003-raw-answers-kept-costs-recorded.md) | Every paid answer is kept; every cost is recorded | accepted |
| [004](004-profiles-derived-from-samples.md) | A voice profile is derived from its samples; a wrong name is worse than unknown | accepted |
| [005](005-data-stays-local.md) | Data stays local; nothing biometric or copyrighted in git; forget | accepted |
| [006](006-cut-in-quiet-moments.md) | Audio is cut in quiet moments, never inside a word | accepted |
| [007](007-everything-is-a-stream.md) | One ingest path: a stored video is a stream that runs faster | accepted |
| [008](008-speaker-embeddings-ecapa-for-the-spike.md) | Speaker embeddings for the spike: SpeechBrain ECAPA, our own clustering | accepted |
| [009](009-local-review-ui.md) | A local review UI: React on a small JSON API, decisions in the database | accepted |
| [010](010-fact-check-sources.md) | Fact check: our data first, the web as fallback, two reliable sources | accepted, amended by 014 |
| [011](011-ad-breaks-pause.md) | Ad breaks pause the analysis; listening continues | accepted |
| [012](012-every-voice-has-a-number.md) | Every voice gets a number that continues across videos | accepted |
| [013](013-live-session.md) | A live session: voices now, words a piece behind | accepted |
| [014](014-personal-project-own-data.md) | lektyra is a personal project and checks against its own data | accepted |
| [015](015-a-face-next-to-a-name.md) | A face next to a name; pictures live in lektyra's own MinIO | accepted |
