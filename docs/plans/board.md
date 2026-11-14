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
| K26 | **Sunday 15. 11. live run: TA3 V politike 11:00 (`ta3:live`), STVR O 5 minút 12 11:55 (`stvr:1`), Markíza Na telo 13:00 (PC sound, Orange TV)** | next | 2026-11-14 | [runbook](runbook-2026-11-15.md) · TA3 and STVR live sources tested tonight · Martin watches and names |
| K27 | **Guest profiles in advance** | doing | 2026-11-14 | ready to name in the real DB: Hlina and Takáč (rehearsal), Kuffa (9-min clip, transcribed), Fico (Voice 1, 5 videos), TA3 moderator (Voice 3, 4 videos) · STVR's guests optional (runbook step 3) |
| K29 | **Live pipeline: claims every minute** | next | 2026-11-14 | voices now + words per piece done (K31) · for Sunday: run `lektyra claims` + `end-pass` on each recorded show right after it (replay = live) |
| K47 | **UI: Fact check screen** | later | 2026-11-14 | after K37 (claims model) and K21/K22 · [mockup](https://claude.ai/artifact/1aFxRsPc2SAiooBCp6jiWA) |
| K48 | **Several live sessions in one screen** | later | 2026-11-14 | today: one session per `lektyra ui`, more side by side on other ports, voices serialized by an advisory lock (ADR-013 §1, tested TA3 + STVR at once) · next: session tabs, one shared voice model |
| K50 | **Crosstalk must not found a voice** | next | 2026-11-14 | found by Martin: Voice 4 = small leftovers (1–2 %) in A/B/C where Fico and the host overlap; each sits between both (Fico 0.56–0.68, host 0.55) and they matched each other (0.72–0.78) · rule: a small speaker whose two closest voices are two different people at similar strength stays unclear · later: overlap detection (K19) |
| K32 | **UI: split the bundle** (694 kB, react-markdown on every page) | later | 2026-11-14 | lazy routes for Documents and Voice map |
| K39 | **The go/no-go number: share of claims in 5 real debates that public data can settle** (CRZ, NR SR votes, company registers, government data) | next | 2026-11-14 | market scan: under ~10 % the moat is thin · after K20 gold set and K21 |
| K41 | **Demo package: Sunday's debates with numbers** (names, lag, cost, claims with sources) | next | 2026-11-14 | runs on Martin's PC; recorded |
| K43 | **Facebook / YouTube videos and lives as sources** | next | 2026-11-14 | yt-dlp already reads public ones; login pages need `--cookies-from-browser` · test one politician's page |
| K44 | **Ads and pre-show: end-of-event cheap-model pass marks ad stretches; ad-only voices removed; analysis starts at the moderator's voice** | next | 2026-11-14 | extends K23 / ADR-011 · EPG gives the slot, not the real start or the breaks |
| K37 | **Claims data model v2** (ADR + migration): statement → claim → canonical-claim link → check (append-only, as-of date) · entities with IČO · evidence with query + record ids · media item with platform | later | 2026-11-14 | canonical match = vector recall **and** equal slots (amount, unit, period, entity), else no reuse · typed vector dims + HNSW for claims · unaccent + pg_trgm (+ Slovak hunspell) |
| K38 | **Verdict labels as Demagog's** (pravda, nepravda, zavádzajúce, neoveriteľné) **+ eval on the DemagogSK corpus** | later | 2026-11-14 | their 12.6k labelled claims become a test set (check the dataset's terms) · verdicts on claims, never a per-person "liar" score · contest/correction log |
| K40 | **Legal opinion before anyone else uses it** | blocked:Martin | 2026-11-14 | voiceprints of public figures (GDPR Art. 9, journalism exemption), broadcast capture via Orange TV, defamation · decides which users are possible |
| K23 | **Ad breaks: detect and pause the analysis** | next | 2026-11-14 | ADR-011 |
| K22 | **Fact check web fallback: 2 independent reliable sources, filtered claims kept** | next | 2026-11-14 | ADR-010 · search API bake-off open |
| K18 | **Eval: WER/CER, names and numbers accuracy, cut-word check against references** | next | 2026-11-14 | after K7 · eval skill |
| K20 | **Claims eval: Martin marks the claims worth checking in A (gold set) → live recall/precision** | next | 2026-11-14 | spike-plan §8 step 2.2 |
| K21 | **Own public-data service: CRZ, NR SR votes and prints, company registers → quick checks for 3 claim kinds (contract/amount, company, vote)** | next | 2026-11-14 | ADR-014 · ingest + refresh into lektyra's Postgres, record ids and fetch dates kept (ADR-010) · the manual CRZ check of c23 shows the two queries to automate |
| K19 | **Soniox adapter + pyannote comparison** | later | 2026-11-14 | Martin: "keep soniox and hf for later" |

## Archive

| id | task | state | since | note |
|---|---|---|---|---|
| K31 | **UI: Live screen** | done | 2026-11-14 | ADR-013 · walked on the full V politike Hlina–Takáč episode (YouTube, 720p): moderator recognised as Voice 3 (0.79) from older videos, Takáč as Voice 9 (0.88) from the D2 press conference, Hlina founded Voice 17, named during play, words every piece, 5:53 for $0.023 · player 1 s from lektyra |
| K28 | **PC sound as a source (`pc:sound[:device]`): Orange TV / Markíza in the browser** | done | 2026-11-14 | ADR-013 §7 · WASAPI loopback (soundcard) → 48→16 kHz low-pass decimator (4 tests) · tested: Takáč recognised through the speakers at 0.83, words transcribed · no DRM circumvention · legal question in K40 |
| K49 | **Hear a voice: ▶ plays its clearest passages** (Persons: across videos, newest first; a video's speakers: in that video) | done | 2026-11-14 | longest turns trimmed, ≤ 12 s, up to 6 · one reel at a time, media fragments, no effects · fixed while walking: a clip's end reported twice skipped the next clip; a fragment stops a few ms short of its end |
| K36 | **Pushed to `git@github.com:MartinFric/lektyra.git`** | done | 2026-11-14 | ADR-014 · GitHub holds the server-side date · pre-push: all tests + osv-scanner clean |
| K35 | **lektyra is a personal project** | done | 2026-11-14 | ADR-014 · concept moved into `docs/plans/concept.md`, removed from the old work notes · no client tools, data or keys · checks get their own data service (K21) |
| K45 | **Every voice gets a number across videos; persons get kind, key, knowledge link** | done | 2026-11-14 | ADR-012 · migration 0003 · 7 API integration tests |
| K33 | **Dev-only npm advisories** | done | 2026-11-14 | minimatch pinned to 11.0.8 inside typescript-estree (npm overrides) · `npm audit`: 0 |
| K14 | **First commit** | done | 2026-11-14 | b449ca0, 17:32, all hooks green · author fric@ccsolutions.sk (repo-local git config) |
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
