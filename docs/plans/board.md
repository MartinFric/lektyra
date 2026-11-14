# lektyra board

The plan is the intent (`spike-plan.md`); this is the state. Ids `K<n>`, never reused. Detail by id in
[detail.md](detail.md). The board moves in the same commit as the work.

`| id | task | state | since | note |`

## Now

| id | task | state | since | note |
|---|---|---|---|---|
| K7 | **References A (10 min), B, C, D1, D2 (5 min)** [→](detail.md#k7) | blocked:Martin | 2026-11-14 | templates in `data/refs/`, pages `data/events/*/compare-*.html` · LISTEN rows: A 15/60, B 8/30, C 2/30, D1 1/30, D2 8/30 |
| K16 | **Name the speakers** (S1…N per event) | blocked:Martin | 2026-11-14 | now in the UI: `uv run lektyra ui` → a video → Name… (or while it plays) · each name re-matches the other videos · no names guessed (ADR-004) |
| K9 | **Voice profiles: name/reject/identify/forget, s-norm** | doing | 2026-11-14 | ADR-004/009 · name (samples from clean windows), reject, forget, re-match on every change: done in the UI · open: s-norm, live identify (K29), names after a diarization re-run |
| K10 | **Phase 2: claims loop, replay = live** [→](detail.md#k10) | doing | 2026-11-14 | [report](../eval/2026-11-14-claims-replay-A.md) · A: 114 claims, 12.7 s/min (max 25.7), $1.75 · end pass +1 missed, 8 links, 2 duplicates · one claim checked by hand in CRZ: true (amount without VAT) |

## Next / later

| id | task | state | since | note |
|---|---|---|---|---|
| K26 | **Sunday 15. 11. live run: TA3 V politike 11:00, STVR O 5 minút 12 11:55, Markíza Na telo 13:00** | next | 2026-11-14 | guests from Denník N's weekend list; times are the usual slots (verify) · Martin watches |
| K27 | **Guest profiles in advance: Kuffa, Hlina, Gašpar, Karas, Drucker, Šimečka + moderators Gudiak, Lacová, TA3's** | next | 2026-11-14 | 1–2 archive episodes each · Martin names voices in the UI |
| K29 | **Live pipeline: piece → speech-to-text → voice match against profiles → claims every minute** | next | 2026-11-14 | spike-plan §8; online voice matching instead of whole-video clustering |
| K28 | **Orange TV source: record the PC's sound output (WASAPI loopback)** | next | 2026-11-14 | for Markíza; one stream at a time; ADR-007 adapter |
| K31 | **UI: Live and Fact check screens** | next | 2026-11-14 | [mockup](https://claude.ai/artifact/1aFxRsPc2SAiooBCp6jiWA) · with K29 (live pipeline) and K22 (web fallback) |
| K32 | **UI: split the bundle** (694 kB, react-markdown on every page) | later | 2026-11-14 | lazy routes for Documents and Voice map |
| K33 | **Dev-only npm advisories: 7 moderate in typescript-eslint's tree** | later | 2026-11-14 | no non-breaking fix yet; `npm audit` in web/; not in the shipped bundle |
| K23 | **Ad breaks: detect and pause the analysis** | next | 2026-11-14 | ADR-011 |
| K22 | **Fact check web fallback: 2 independent reliable sources, filtered claims kept** | next | 2026-11-14 | ADR-010 · search API bake-off open |
| K18 | **Eval: WER/CER, names and numbers accuracy, cut-word check against references** | next | 2026-11-14 | after K7 · eval skill |
| K20 | **Claims eval: Martin marks the claims worth checking in A (gold set) → live recall/precision** | next | 2026-11-14 | spike-plan §8 step 2.2 |
| K21 | **Quick checks via ps-mcp for 3 claim kinds (contract/amount, company, vote)** | next | 2026-11-14 | spike-plan §8 step 2.3 · manual CRZ check of c23 in the report shows the two queries to automate |
| K19 | **Soniox adapter + pyannote comparison** | later | 2026-11-14 | Martin: "keep soniox and hf for later" |
| K12 | **Check the BMG contract for an IP clause** | blocked:Martin | 2026-11-14 | spike-plan "Name and ownership" |
| K14 | **First commit** | blocked:Martin | 2026-11-14 | all gates green; nothing committed until Martin says so |

## Archive

| id | task | state | since | note |
|---|---|---|---|---|
| K30 | **Review UI** (ADR-009): Videos, Video (speakers + naming), Transcript (player, speaking now, name while playing, rate, flag), Persons, Voice map, Documents | done | 2026-11-14 | React 19 + TanStack Query + zod + sonner, Segoe UI Variable, logo B · one API wrapper, AppError, one error shape · ESLint + hook L9 (no casts/`!`/any/effects/raw fetch/disables) · 11 Vitest + 6 API integration tests · walked with skill manual-testing (16 shots) |
| K24 | **Name a person while the video plays** | done | 2026-11-14 | Transcript → *Speaking now* card |
| K13 | **Migration runner** | done | 2026-11-14 | `Store.migrate` applies newer `migrations/NNNN_*.sql`; 0002 applied; `lektyra ui` runs it on start |
| K17 | **Final round: top 3 engines on all five videos** | done | 2026-11-14 | ElevenLabs, Grok, Gemini × 243 pieces · speech-to-text total $4.18 · Gemini rate limit (20 rpm) waited out by the adapter |
| K8 | **Diarization: ECAPA + own clustering** [→](detail.md#k8) | done | 2026-11-14 | ADR-008 · [voices report](../eval/2026-11-14-voices.md) · one voice in all 5 events at 0.80–0.92, others ≤ 0.47 · transcripts with speakers for all 5 (`report`) · DER waits for references |
| K6 | **`compare` page for Martin's references** | done | 2026-11-14 | 10 s rows, minority words highlighted, click-to-play, LISTEN = top quarter by disagreement · template per row from the engine agreeing most |
| K5 | **Speech-to-text: OpenRouter adapter (all models); screening round** [→](detail.md#k5) | done | 2026-11-14 | [report](../eval/2026-11-14-stt-screening.md) · 11 models × 5 windows · ~$1.45 · top: ElevenLabs, Gemini, Grok, Voxtral |
| K15 | **Live resilience + ffmpeg log** | done | 2026-11-14 | HLS segment retries, HTTP reconnect, live reopen ×20 with gaps in the manifest, `complete` flag, ffmpeg messages → `ffmpeg.log`; TA3's end-of-stream line classed benign · 4 tests with fakes |
| K4 | **Find TA3 videos B, C, D1, D2** [→](detail.md#k4) | done | 2026-11-14 | B 236236 (2022-05-15), C 975381 (2025-01-12), D1 YouTube pgF9MzwE4ds (NR SR), D2 YouTube s_rCdQRlBzA (Úrad vlády) · all complete, 243 pieces, 0 forced |
| K11 | **Local Postgres + pgvector, migration 0001** | done | 2026-11-14 | `docker compose up -d` · 12 tables · pgvector 0.8.6 · 127.0.0.1:55432 only |
| K3 | **Ingest: URL → PCM stream → pieces** [→](detail.md#k3) | done | 2026-11-14 | ADR-007 · TA3 resolver (archive, `ta3:live`, `ta3:nrsr`) · `ta3:live` 156.7 s in 149 s wall |
| K2 | **Cutting in quiet moments (`choose_cut`, `stitch`)** [→](detail.md#k2) | done | 2026-11-14 | ADR-006 · 5 videos: 0 forced cuts · cuts at −60…−65 dB vs speech −27 dB |
| K1 | **Day 1: repo, gates, skills, ADRs** [→](detail.md#k1) | done | 2026-11-14 | ADR-001..008 · hooks L1–L8, 21 hook tests · 10 skills · mypy strict · LICENSE proprietary |
| K0 | **Name: lektyra** | done | 2026-11-14 | lekton + ankyra · no exact company/trademark found · .sk/.eu/.ai/.io free · Martin's pick |
