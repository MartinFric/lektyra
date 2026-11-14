# lektyra: live transcription, voice profiles and claims, a standalone local spike (plan)

2026-11-14. Plan, nothing built. Moved here from Martin's notes on 2026-11-14 (day 1). The wider idea (live stream → transcript → fact check)
is summarised in sections 3 and 8; voice-profile reasoning is in ADR-004.

Decided by Martin on 2026-11-14:
- **name: lektyra** (lower case), from lekton + ankyra. In Stoic logic a *lekton* is "what is said": the content
  of a statement, the part that can be true or false. So lektyra is "the anchor of what was said". It is the same
  kind of blend as mnemyra (mnemos + ankyra);
- **speech-to-text through OpenRouter** (cheap: a few dollars for the whole test, profiles included), **plus
  Soniox** through its own API;
- **Martin writes the reference transcripts** and compares the engines;
- the other-channel test uses **both** a parliament speech and a government press conference;
- **HTN's OpenRouter key** is reused for now.

**Name and ownership (checked 2026-11-14, not legal advice):**

- **lektyra**: no company, product or trademark under that exact name found. The closest are Litéra (legal
  software) and Lectra (CAD), which are further away. **.sk, .eu, .ai and .io are free**; **.com is taken**. A
  TMview/EUIPO and ÚPV search comes before commercial use.
- Also checked: Rhemos (clean, but spoken "Remos" collides with other things, and the US mark RHEMORIS, class 9,
  2025, is close).
- Rejected: IntelliVoice (live US mark, a VoIP company, "Intelligent Voice" doing speech-to-text in the UK) and
  IntelliSpeech (live US mark). "Intelli-" is a crowded, weak prefix.
- Ownership: lektyra is Martin Fric's personal project (ADR-014): his account, hardware and keys, a proprietary
  LICENSE from the first commit, the repository `git@github.com:MartinFric/lektyra.git`. The original concept is
  `docs/plans/concept.md`.

**Goal of the spike.** Take archived TA3 videos with at least three people talking, Robert Fico among them, and:
1. transcribe them with **several speech-to-text models** and measure which is best for Slovak;
2. split the voices into speakers;
3. build **voice profiles** that recognise the same people in other videos, and get better when a human corrects
   an "unknown".

It runs **locally** (this PC, a local Postgres) as a standalone tool with its own repo and database. It is built
with HTN's discipline: ADRs, a board, skills, model-agnostic git hooks. Only the speech-to-text calls leave the
PC. Diarization and voice embeddings run locally, because no API offers them and they cost nothing here.

## 1. Python, yes

| | Python | TypeScript/Node | Rust (as HTN) |
|---|---|---|---|
| diarization and voice embeddings (pyannote, SpeechBrain) | native | none | none |
| ffmpeg / yt-dlp / audio handling | first-class | via processes | via processes |
| WER/DER metrics (jiwer, pyannote.metrics) | native | none | none |
| strict typing | mypy strict + pydantic (the spawner already runs this) | best | best |

Speech-to-text is a plain HTTP call in any language. Diarization and voice profiles are only available in Python,
so the tool is Python. Type safety comes from **mypy strict + pydantic at every boundary**. The untyped ML
libraries (torch, pyannote) are allowed only inside `adapters/`, which hand typed domain objects onward.

From HTN we port the ideas and a few hundred lines of logic, not the Rust code:
- the cutting idea (about 60 s per piece, cut in a pause), made stricter for TV: section 4, "Cutting";
- the OpenRouter transcription call and the hallucination filter;
- the correction guard (line count unchanged, ≤ 1/4 of words changed);
- the Markdown transcript format.

## 2. Test material: TA3 archive

Criteria:
- at least 3 voices in one video;
- Fico in at least 3 different videos, across at least 2 years and in more than one setting;
- some cross-talk, to test diarization under overlap.

| id | video | voices | why |
|---|---|---|---|
| **A** | TA3 *V politike*, 24 Sep 2023, Fico + Kollár before the election ([ta3.com/clanok/902387](https://www.ta3.com/clanok/902387/v-politike-fico-a-kollar-o-poslednych-dnoch-do-volieb-migrantoch-aj-verejnych-financiach)) | moderator, Fico, Kollár | the main set: references, enrolment |
| **B** | another *V politike* duel of Fico and Kollár, 2022 ([ta3.com/clanok/255727](https://www.ta3.com/clanok/255727/referendum-poda-kollara-nema-sancu-uz-ani-nemozeme-povedat-cigan-stazoval-sa-fico); also as an audio podcast: [ta3.com/relacia/25304](https://www.ta3.com/relacia/25304/podcast-ta3-v-politike-s-borisom-kollarom-a-robertom-ficom)) | moderator (maybe different), Fico, Kollár | same people, another year: re-identification |
| **C** | Fico's TA3 interview, January 2025, as prime minister ([ta3.com/clanok/975381](https://www.ta3.com/clanok/975381/robert-fico-v-ta3-koalicii-som-povedal-ze-ideme-do-pekla-pripusta-predcasne-volby-ukrajine-sa-chce-revansovat-vetom-v-eu)) | moderator, Fico | another year and role: does his profile still hit? |
| **D1** | Fico speaking in the NR SR (parliament hall, the parliament's own video) | Fico, chair, others | hall acoustics: the "Person X → correction → recalculate" test |
| **D2** | a government press conference with Fico (Úrad vlády stream) | Fico, ministers, journalists | another room, many voices, questions from the floor |

Step 1 confirms that these episodes can still be played and downloaded. `yt-dlp` on the page; if it has no
extractor for the site, the HLS address from the player goes straight to `ffmpeg`. Replacements are easy to find,
since TA3 has years of *V politike*. The exact D1 and D2 recordings are picked then.

**Rules for this material** (also in the `privacy` skill and in a hook):
- TA3's videos are copyrighted: they are downloaded for internal research only, kept only locally, never published;
- the voice profiles are biometric data of real people: they stay in the local database, and
  `lektyra forget <person>` deletes a person completely;
- **no audio, video or embedding ever goes into git** (a hook enforces it);
- before anything runs continuously or leaves this PC: the DPIA from the concept, section 4.

## 3. The engines

### Speech to text: about 10 through OpenRouter, plus Soniox

OpenRouter's transcription endpoint has ~30 models (checked 2026-11-14 via
`/api/v1/models?output_modalities=transcription`). They share one API, so **one adapter serves all of them**: a
model is a name in a list. Adding a model costs no code.

The run has two rounds:
- **Screening round**: about 10 engines on the reference minutes only (A 10 min, B 5 min, C 5 min = 20 min each).
- **Final round**: the 3 best on all the videos.

| engine | via | list price per hour of audio | why |
|---|---|---|---|
| `openai/whisper-large-v3` | OpenRouter | $0.027 | the baseline; what HTN uses |
| `openai/gpt-transcribe` | OpenRouter | $0.27 | OpenAI's newest |
| `openai/gpt-4o-transcribe` | OpenRouter | token-priced (~$0.36) | in HTN's catalog already |
| `elevenlabs/scribe-v2` | OpenRouter | $0.22 | lists Slovak, vendor claims low Slovak WER (unverified) |
| `assemblyai/universal-3-6-pro` | OpenRouter | $0.30 | lists Slovak with diarization |
| `deepgram/nova-3` | OpenRouter | $0.26 | lists Slovak |
| `google/gemini-3.5-transcribe` | OpenRouter | token-priced | Google's transcriber |
| `google/chirp-3` | OpenRouter | $0.96 | Google's speech model, the most expensive here |
| `mistralai/voxtral-small-transcribe-3-0` | OpenRouter | $0.24 | open-weight family; could later run locally |
| `x-ai/grok-stt-2.0` | OpenRouter | $0.10 | cheap newcomer |
| **Soniox** | own API (second adapter) | check at run time | vendor claims the lowest Slovak WER and real-time diarization |

Cost of the spike:
- screening: 11 engines × 20 min ≈ 3.7 h of audio, about **$1–2**;
- final: 3 engines × ~5 h of video, about **$3–5**;
- with the correction passes, **under $10 in total**.

Prices are OpenRouter's list on 2026-11-14 (per second of audio × 3600). The `catalog` command records the price
at run time.

Things the spike has to check, because OpenRouter normalises the API:
- Does an engine's **own diarization** come through OpenRouter, or only the text? Diarization runs locally either
  way.
- Which engines give **word timestamps**? These are needed to put words onto speakers. Engines without them can
  only be judged on the text.
- **Zero data retention**: HTN asks for it on every request. Here it is on where a provider offers it and off
  otherwise. TA3 is a public broadcast, so nothing confidential leaves the PC.

### Diarization and voice embeddings: local, free

- **pyannote `speaker-diarization-community-1`** (pyannote.audio 4.0, autumn 2025), on the RTX 4060 Ti 8 GB (CPU
  works too). It is gated on Hugging Face: accept its conditions once and use a token.
  [Model card](https://huggingface.co/pyannote/speaker-diarization-community-1).
- **Voice embeddings for profiles**:
  - the WeSpeaker ResNet embedding used inside pyannote;
  - SpeechBrain ECAPA-TDNN.

  They are compared by how well they separate Fico from the others across A–D2.
- Local Whisper is dropped (Martin: send the speech to OpenRouter).

## 4. How it is built

### Repo layout

`C:\Work\dev-personal\lektyra`, pushed to `git@github.com:MartinFric/lektyra.git` (ADR-014).

```
lektyra/
  AGENTS.md, CLAUDE.md          rules for every agent (as HTN: decisions in ADRs, board, gates are git hooks)
  pyproject.toml, uv.lock       Python 3.12, uv
  compose.yaml                  Postgres 17 + pgvector, local only (127.0.0.1)
  migrations/0001_init.sql …    plain SQL, numbered, a schema_version table
  .githooks/                    pre-commit, commit-msg, pre-push, hook-tests.sh (core.hooksPath)
  .claude/skills/  .claude/settings.json (post-edit guard)
  docs/adr/  docs/plans/board.md + detail.md  docs/eval/ (the reports)  docs/runbooks/
  refs/                         Martin's reference transcripts (text only, no audio)
  src/lektyra/
    domain/        pure, no I/O, fully unit-tested
      types.py       Event, Chunk, Word, Utterance, Turn, EventSpeaker, Person, VoiceSample, Match (frozen dataclasses)
      chunking.py    choose_cut(vad, energy, turns) → the quietest point near 60 s, never inside a word; overlap + stitching
      align.py       words ↔ speaker turns (who said which word)
      matching.py    cosine, k nearest samples, score normalisation (s-norm), thresholds → auto / suggested / unknown
      profiles.py    rebuild(samples) → profile; rejections; weights
      metrics.py     WER/CER, entity accuracy (names, numbers), DER bookkeeping
      render.py      transcript Markdown in HTN's format; the side-by-side comparison
    ports.py         Protocols: MediaFetcher, Transcriber, Diarizer, Embedder, Repository
    adapters/
      media/ytdlp_ffmpeg.py
      stt/openrouter.py (every OpenRouter model), soniox.py
      diarize/pyannote_local.py
      embed/pyannote_wespeaker.py, speechbrain_ecapa.py
      store/postgres.py (psycopg 3 + pgvector)
    app/             one use case per file: ingest, transcribe, compare, diarize, identify, name, reject, forget, evaluate, report
    settings.py      pydantic-settings; keys from ~/.secrets/lektyra.env (OPENROUTER_API_KEY = HTN's for now, SONIOX_API_KEY, HF_TOKEN)
    cli.py           typer
  tests/  unit/ (domain) · contract/ (adapters against saved API answers, no network) · integration/ (Postgres, marked slow)
  data/   git-ignored: events/<id>/{source.json, audio.flac, chunks/, raw/<engine>/*.json, clips/}
```

**Principles** (they become the `principles` skill, ranked as in HTN):
1. **The domain is pure.** All the logic (cutting, alignment, matching, profiles, metrics) is in `domain/` without
   I/O and is tested there. Adapters only translate.
2. **Every engine is a name or an adapter behind one Protocol.** A new OpenRouter model is a line in the engine
   list. A new provider is one file plus one contract test.
3. **Every paid answer is kept** (`data/…/raw/<engine>/`), with its cost and wall time in the database. Evaluation
   reruns without paying again, and results are reproducible.
4. **A profile is a function of its samples.** Never patched in place: rebuilt (concept §2a).
5. **A wrong name is worse than "unknown".** Thresholds are set for zero false names first, hits second.
6. **Data is parsed at the boundary**: pydantic for API answers, settings and CLI input. No `cast`, no
   `# type: ignore`, no `Any` outside `adapters/`.

### Cutting: in a quiet moment, never inside a word

A TV debate has few long pauses: people talk over each other, music runs under the intro. HTN's rule ("a pause
≥ 600 ms, forced at 90 s") would often end in the forced cut, in the middle of a word. So:

1. **Listen locally first.** Silero VAD (local, CPU, milliseconds) gives the speech probability every 30 ms, and an
   energy curve runs alongside it.
2. **Look for a cut between 45 and 75 s, and take the best spot in that window, not the first:**
   - first choice: the longest silence of at least 250 ms. Broadcast speech pauses 200–400 ms between sentences;
   - bonus points for a change of speaker (a diarization turn boundary), which is a natural seam;
   - if there is no such pause: the deepest dip in energy of at least 120 ms. Even fast speech has micro-pauses
     between words, never inside one.
3. **The hard limit is 90 s, and even then it is the best dip in 75–90 s,** never a point where speech probability
   is above 0.5. The cut goes in the middle of the chosen silence, not at its edge.
4. **Overlap as a safety net.** Every piece also carries 1.5 s from before its cut. Words in the overlap are taken
   from the piece where they lie further from the edge, using word timestamps. Engines without word timestamps
   fall back to matching the last words as text, which is weaker. That is one more reason to prefer engines with
   timestamps.
5. **Measured, not assumed:**
   - "words cut" counts reference words whose time span crosses a cut, and must be 0;
   - WER in the 3 seconds around each cut is compared with WER elsewhere; a bump means the cutting hurts.

`choose_cut` is a pure function over the VAD and energy arrays, so it is unit-tested with synthetic curves:
continuous speech, cross-talk, music, a long pause at 46 s against a short one at 61 s.

The claims loop's overlapping windows (section 8) handle sentences that run across minutes. This handles words.

### Database (local Postgres + pgvector)

| table | holds |
|---|---|
| `event` | a video: source URL, title, aired at, channel/show, length, path to audio |
| `transcript_run` / `utterance` | one engine's transcript: engine, model, parameters, cost, wall time; utterances with words and times |
| `diarization_run` / `turn` | one diarizer's turns: start, end, label |
| `event_speaker` | S1…N of an event with its embedding; best match (person, score); status `auto` / `suggested` / `unknown` / `confirmed` |
| `person` | name, function, party, public-figure flag |
| `voice_sample` | one clean stretch of one person: event, times, embedding, embedding model, provenance (`auto` / `human_confirmed` / `human_corrected`), quality, weight |
| `voice_rejection` | "S2 of event X is NOT person P" |
| `audit_log` | who named, rejected or forgot whom, and when |

### The command line (the whole UI of the spike)

```
lektyra catalog                     OpenRouter's transcription models + prices today
lektyra ingest <url> --title "V politike 2023-09-24"   video → 16 kHz mono FLAC + chunks cut in silences; event in DB
lektyra transcribe <event> --engine openai/whisper-large-v3 [--engine …] [--from 10:00 --to 20:00]
lektyra compare <event> --from 10:00 --to 20:00   all engines side by side for Martin (see section 6)
lektyra diarize <event>             pyannote, locally
lektyra speakers <event>            S1…N: talk time, 3 clips each in data/…/clips/, suggested names with scores
lektyra name <event> S2 "Robert Fico"     → samples → profile rebuilt → past unknowns matched again
lektyra reject <event> S2 "Robert Fico"   → a rejection; profile rebuilt without that event's auto samples
lektyra identify <event>            match all speakers of an event against the profiles
lektyra eval <event> --ref refs/A.md      WER/CER/names/numbers per engine, DER → docs/eval/<date>-<event>.md
lektyra report <event>              transcript.md in HTN's format with names
lektyra forget "<person>"           person, samples and profile deleted, an audit entry kept
```

A small web screen for naming speakers (listen and click) comes only after the spike, if the tool lives on.

## 5. Skills, guards and hooks (HTN as the model)

**Hooks** (`.githooks/`, `core.hooksPath`, plain bash, model-agnostic, each rule with a test in `hook-tests.sh`,
each rule naming its ADR):

| hook | rules |
|---|---|
| pre-commit | gitleaks · `ruff check` + `ruff format --check` · `mypy --strict` · `pytest -m "not slow"` · **data guard**: refuses `*.wav *.flac *.mp3 *.mp4 *.m4a *.opus *.webm *.npy *.pt *.pkl *.parquet`, anything under `data/`, any file > 1 MB · no `cast(`, `# type: ignore`, `Any` outside `adapters/` · no `print(` outside `cli.py` · no keys or tokens in tracked files · LF only |
| commit-msg | conventional subject · no AI attribution |
| pre-push | `pytest` incl. slow (Postgres via compose) · `pip-audit` / osv-scanner on `uv.lock` |
| Claude post-edit (`.claude/settings.json`) | `ruff` + `mypy` on the file just edited (HTN's `post-edit-guard.sh` pattern): catches a rule break while the reasoning is still in context |

**Skills** (`.claude/skills/`):

| skill | content | from |
|---|---|---|
| `principles` | the ranked list above, and how to decide when two rules collide | HTN `principles` |
| `architect` | where code goes (domain / ports / adapters / app), what a new engine needs | HTN `architect`, mnemyra-lite `decide` |
| `stt-engine` | adding an OpenRouter model (a line) or a provider (an adapter): saving the raw answer, recording cost, the contract test, HTN's hallucination filter | new |
| `voice-profiles` | profile = f(samples), k-NN, s-norm, thresholds, rejections, forget | concept §2a |
| `eval` | how Martin's references are written, WER/CER/DER, entity accuracy, the report format | new |
| `privacy` | biometric and copyright rules, what may never leave the PC or enter git | concept §4 |
| `testing` | a fix starts with a failing test; fixtures are license-clean (LibriSpeech CC BY / generated speech, never TA3 audio); no wall clock | es-sk/HTN `testing` |
| `verify` | numbered checklist; "check that a guard can actually fire" | HTN `verify` |
| `commit`, `review` | message format; a review that refutes its own findings | HTN |

**ADRs to write on day 1:**
1. Python + uv + mypy strict.
2. Ports and adapters; OpenRouter as the one gateway for speech-to-text, Soniox as the exception.
3. Raw answers are kept; costs are recorded.
4. A profile is derived from samples (k-NN, s-norm, rejections).
5. Data stays local; nothing biometric or copyrighted in git; `forget`.

Then `docs/plans/board.md`, following Martin's board convention.

## 6. How we measure

**References** (the "truth"), written by Martin:
- **Which minutes**: 10 min of A with cross-talk inside, plus 5 min each of B and C.
- **`lektyra compare`** makes it quick. It writes one HTML page per window:
  - a row every 10 seconds with each engine's text side by side;
  - the words where engines disagree highlighted;
  - each row's timestamp playing the audio from that second (a local `<audio>` with `#t=`).

  Martin listens only where engines disagree, and writes the right text into `refs/A.md`: plain Markdown,
  `**[mm:ss] S1:** text`, speaker turns in the same pass. About 1 h per 10 minutes, so about 2 hours in total.
- Starting from the engines' disagreements, not from one engine's draft, keeps the reference from favouring one
  engine.

**Metrics:**

| what | metric | target (set before the run) |
|---|---|---|
| transcript | WER and CER on the references | WER ≤ 10 % on studio speech (to be revised after A) |
| what matters for fact checks | **names** (politicians, parties, institutions) and **numbers** (sums, dates, percentages) correct, % | names ≥ 95 %, numbers ≥ 95 % |
| speakers | DER (diarization error rate); speaker count right | DER ≤ 15 %, count exact |
| cutting | reference words whose time span crosses a cut; WER in the 3 s around cuts vs elsewhere | **0 words cut**; no WER bump at cuts |
| profiles | same-person vs other-person score distributions, EER; at the chosen threshold: **false names = 0**, then as many hits as possible | Fico, Kollár and the moderator found in B, Fico in C, D1, D2 |
| practical | cost per hour of audio, wall time per hour | for the record |

**The profile test, step by step:**
1. **Enrol on A**: name S1–S3 by hand → profiles for Fico, Kollár, the moderator.
2. **Studio, other years**: run `identify` on B and C without naming. Record each speaker's scores and status.
3. **Other rooms**: run `identify` on D1 (parliament) and D2 (press conference). Where Fico comes out `unknown` or
   `suggested`, name him by hand. The profile is rebuilt. Then run on the held-back half of D1/D2: the score must go
   up and the name must be found. This is the "recalculate" loop proven. Ministers and journalists in D2 must
   **not** be named as Fico or Kollár.
4. **Reject test**: deliberately name a wrong person, reject it, and check that the profile returns to its previous
   state.

## 7. Plan

| day | step | result |
|---|---|---|
| 1 | repo skeleton, `pyproject`, compose (Postgres + pgvector), hooks + `hook-tests.sh`, AGENTS.md, skills, ADRs 1–5, board; install `uv`, `ffmpeg`, `yt-dlp` (none of them is on this PC yet; winget); `~/.secrets/lektyra.env` with HTN's OpenRouter key | gates fire, empty pipeline is green |
| 2 | `ingest`: download A, B, C, D1, D2, FLAC 16 kHz mono, Silero VAD, `choose_cut` + stitching + their unit tests; `catalog` | 5 events in the database |
| 3 | `transcribe`: OpenRouter adapter (all models) + Soniox, raw answers, cost; **screening round** on the 20 reference minutes; `compare` | the comparison pages for Martin |
| 3–5 | **Martin**: references for A, B, C (~2 h) · meanwhile `diarize` (pyannote) + `align` words to turns | refs/A.md, B.md, C.md |
| 5 | `eval` → **report 1: which engine** (WER, names, numbers, cost); **final round**: top 3 on all videos | docs/eval/…-stt.md |
| 6 | DER → **report 2: diarization** | docs/eval/…-diarization.md |
| 7–8 | embeddings ×2, `speakers`, `name`, `reject`, `identify`, `forget`; s-norm, thresholds; the profile test → **report 3: profiles** | docs/eval/…-profiles.md |
| 9 | final report, ADR 6 "the chosen engine and embedding", board, the next proposal (live ingest, caption OCR, own public-data service) | decision |

About 9 working days. Martin: about 2 hours of listening, plus naming the speakers.

**Hardware:**
- The RTX 4060 Ti has 8 GB: pyannote and the embedding models fit.
- The CPU (9950X3D) carries them too if the GPU is busy.

**Keys** (in `~/.secrets/lektyra.env`, never printed):
- OpenRouter: HTN's key for now. Martin keeps its spending limit in view; the spike needs under $10.
- Soniox: a new account.
- Hugging Face: a token, after accepting pyannote's conditions.

## 8. Phase 2: the live claims loop (the lekton)

Martin's design (2026-11-14), with refinements. Every minute the new transcript piece goes through claim
extraction. Only interesting, checkable claims are kept (numbers, companies, contracts, laws, votes): public
registers hold the data to check exactly these (ADR-014). Every new minute also looks back at whether the previous extraction missed or cut
something. At the end, a pass over the whole event looks for what was missed, what compounds, and what was
corrected later.

### Identity unlocks layers; it does not block the check

A claim's **content** is checkable without knowing who said it. "The state paid company X €200 M in 2024" is true or
false whoever says it.

Who said it matters for four other things:
- **attribution**, i.e. what may be published;
- **context**: his history, connections, contracts of companies around him, earlier findings;
- **consistency**: does it contradict what he said before;
- **priority**: the prime minister's claim ranks above a guest's.

So a claim is stored against the **event speaker (S2)**, not a person. When S2 is resolved, all of S2's claims get
the person at once:
- live, through the voice profile or the caption OCR;
- or at the end, when a human names S2.

The person layer (dossier, consistency check) then runs for them. The better the profiles, the more of it runs
live. Without them, the content checks still run live and attribution comes at the end.

### The loop, every minute

```
new minute of transcript (speakers S1…N, names where known)
  → extraction over a sliding window: the new minute + the 2 before it, plus the ledger of claims so far
      actions: ADD a new claim · AMEND a claim the new minute completed ("…in 2020" + "…we raised pensions 30 %")
               · WITHDRAW (the speaker corrected himself) · LINK (it supports or contradicts claim #12)
  → normalise: entities resolved (company → IČO, person, institution, law), amounts, dates, units
  → triage score = checkability (do we have a source: CRZ, ministry invoices, NR SR votes and prints, finstat,
                   budget) × weight (magnitude, topic, speaker) × novelty (said before? already checked → reuse)
  → quick checks live (a database lookup: does this contract exist, what was its amount)
     · deep checks queued (an agent with web search and the registers, minutes per claim)
```

- **The ledger holds claims with stable ids and a status:** `candidate → normalised → triaged → checking → verdict
  (true / misleading / false / unverifiable) → human-reviewed`. Also tracked: `withdrawn` and `superseded`, and
  links `supports` / `contradicts`.
- **The sliding window is what answers "did we miss part of it last minute":** a claim cut at the minute boundary
  is completed by the AMEND action, not extracted twice.
- **Opinions, promises and value judgements are not fact-checked.** Promises go to their own list, because they
  can be checked later against what happened.

### The end-of-event pass

The final transcript has the final diarization and the confirmed names. One pass over the whole of it, with the
ledger, looks for:
- missed claims;
- duplicates to merge;
- self-corrections ("I misspoke, it was 2019");
- contradictions between speakers or within one speaker;
- claims that only make sense together (a number at minute 5 and its context at minute 40);
- moderators' challenges.

**The difference between the live ledger and the end pass is the live loop's quality measure.** Every event
evaluates the live extractor for free.

### The person layer (once a speaker is identified)

Public sources come together around the person, from lektyra's own public-data service (ADR-014):
- their earlier statements (lektyra's own archive) and contradictions with them;
- NR SR votes and bills;
- companies around them (company registers: ownership, boards) and those companies' contracts (CRZ);
- party financing, where it is published;
- earlier verdicts on the same claims.

### Safeguards

- **A misheard number makes a false verdict.** When a claim is picked for checking, its 20 seconds of audio go
  through the second-best engine once more. If the two engines disagree on a number or a name, the claim is
  flagged "verify the quote by ear". Every claim links to its second in the audio.
- **Nothing leaves without a human.** The verdicts are drafts until a reviewer confirms them.
- **A person dossier is personal data**, even for a public figure in a public role. It needs a legal basis and the
  DPIA from the concept (`concept.md` §4) before anyone else sees it.

### Built so that replay = live

The loop is one pure function, `step(ledger, new_minute) → ledger' + actions`, in `domain/claims.py`. A recorded
video replayed minute by minute is exactly the live run. It is testable, deterministic with the saved model
answers, and needs no live stream until the very end.

| step | content | size |
|---|---|---|
| 2.1 | claim schema, ledger state machine, `step()`, replay of video A minute by minute | 2 days |
| 2.2 | **gold set**: Martin marks the claims worth checking in A (est. 20–40); metrics: live recall and precision against gold, end-pass recall, minute-boundary cuts caught, latency per minute | 1 day + Martin ~1 h |
| 2.3 | triage + quick checks against lektyra's own public-data service for 3 claim types: a contract or amount (CRZ), a company (registers/CRZ), a vote (NR SR) | 2 days + the service |
| 2.4 | end-of-event pass, second-engine quote check, report → ADR "claims loop" | 1–2 days |
| 2.5 | (after the spike) a real live stream, the person layer, the review screen for analysts | later |

The extraction model per minute is a cheap fast one; HTN's correction pass uses gemini-3.1-flash-lite. That costs
cents per hour. The deep checks are the real cost, and triage keeps their number down.
