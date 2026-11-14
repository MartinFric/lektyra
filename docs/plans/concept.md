# Live stream → transcript → voices → claims → checks: the concept

2026-11-14, Martin Fric's idea; lektyra is his personal project (ADR-014). This is the original concept, kept as
written in substance. What was decided since is in `docs/adr/`; what is in flight is in `docs/plans/board.md`; the
build plan is `spike-plan.md`.

Hook onto a live news or debate stream and transcribe it as it runs. Speakers come out as voices with numbers, and
the same voice keeps its number (ADR-012). Names come from a human, from a stored voice profile, or from the screen
caption. Minutes after the end there is a full transcript with names; its checkable claims are checked against
public data, and the findings go to whoever reviews them: an editor, an analyst, a fact-checker.

## 1. What HTN already gives us

HTN, Martin's own app (`C:\Work\dev-personal\hts`), has a recorder that solves half of this for a voice room:

| piece | HTN today | carries over? |
|---|---|---|
| cutting audio | a piece once there is 60 s of speech, cut at the next pause, forced at 90 s | **the rule** (ADR-006 refines it) |
| speech-to-text | OpenRouter, `verbose_json`, temperature 0, zero-data-retention routing, hallucination filter | yes |
| correction | a cheap model with a glossary, one speaker at a time, kept only if few words changed | yes, and the guard matters even more for TV |
| document | front matter, summary, timeline, `**[hh:mm:ss] name:** text` transcript | yes |
| speed and cost | the document ready about 20 s after stop; about $0.25–0.30 an hour with the model passes | yes |
| who speaks | **not guessed**: every person has their own audio stream | **no**: a broadcast is one mixed track |

So the speed is proven. What is new is **ingest** (HLS, YouTube, Facebook, local files) and **diarization** (who
speaks in a mixed track).

## 2. The pipeline

```
stream or video ──ffmpeg/yt-dlp──▶ 16 kHz mono audio ──cut in quiet moments──▶ pieces
   │                                                     │
   │                                                     ├─▶ speech-to-text ──▶ words with times
   │                                                     └─▶ voices ──▶ who spoke when; every voice has a number
   │                                                              ├─▶ match against voice profiles ──▶ "Voice 14 = P (0.86)"
   └──frame every few s──▶ lower-third caption OCR ──▶ "Name Surname, function" + time (a second, independent hint)
                                                                  ▼
                       rolling transcript, a minute behind live ──▶ a human confirms or corrects names
                                                                  │                └─▶ the profile learns (ADR-004)
                                                                  ▼
                       claims every minute (the lekton) + a pass over the whole event at the end
                                                                  ▼
                       checks: public registers first, the web as fallback (ADR-010, ADR-014)
                                                                  ▼
                       human review ──▶ findings, each with its sources and the second in the video
```

**Diarization, the hard part.** Each minute's piece on its own would number speakers differently every minute. The
fix is one voice fingerprint per speaker for the whole event, matched minute by minute; a new voice gets the next
number. Overlapping speech is where it errs most; the final pass corrects the live labels.

**Names from the screen, not from faces.** TV shows a caption when someone speaks; OCR of that strip gives a
**suggested** name, and a human confirms it. No face recognition.

## 2a. Voice profiles

A database of voice profiles with persons assigned. When a profile exists but a speaker still ends up unknown and a
human names them, **the profile learns** so it hits next time.

- A profile is **derived from its samples**, never patched in place: a wrong confirmation is undone by deleting its
  samples; a newer embedding model means re-embedding them (ADR-004).
- **Matching goes against a person's samples** (k nearest in pgvector), not one average, so a phone interview
  matches the next phone interview without dragging the studio voice to the middle. No profile per voice quality.
- **Quality is a gate and a weight, not a key**: overlap, length and noise decide whether a stretch becomes a sample.
- **"This is not P"** is stored and never suggested again for that speaker.
- **Look back**: after a profile changes, the unnamed voices of past videos are matched again.

## 3. The checks

1. **Claims** are extracted every minute: who, when, the sentence, its kind (a number, a contract, a vote, a
   promise, a quote). Opinions and promises are not fact-checked; promises are kept to check later.
2. **Each claim is checked against public data lektyra holds itself** (ADR-014): CRZ contracts, NR SR votes and
   prints, company registers, state budget and statistics, and lektyra's own archive of earlier statements.
3. **The web is the fallback**, with at least two independent reliable sources (ADR-010).
4. **A human reviews every verdict** before anything goes out. Speech-to-text mishears numbers and names, so a quote
   is checked against the audio at its second.

## 4. Legal and policy, before anything is used outside

- **Voice profiles are biometric data** (GDPR Art. 9). They need a DPIA and a lawyer's view of the legal basis;
  public figures in a public role are the strongest case. Scope limited to them; deletion on request is deleting
  their rows; an audit log of every confirmation (ADR-005).
- **No face recognition.**
- **Broadcaster rights**: transcribing a stream for analysis is not publishing it. What goes out is short quotes with
  the source.
- **Accuracy and reputation**: a finding that names a politician goes out only after human review, with a link to
  the moment in the video. Verdicts are on claims, never a score of a person.

## 5. Phases

| # | what | result |
|---|---|---|
| 0 | spike on archived TA3 videos: engines, voices, cutting | numbers to decide on (done, see `docs/eval/`) |
| 1 | batch: a recorded video → transcript with numbered voices and names; a screen to confirm names | the review UI (ADR-009) |
| 2 | live: a stream or a video played as live, voices now, words a piece behind | the Live screen (ADR-013) |
| 2a | voice profiles that learn from every name | ADR-004, ADR-012 |
| 3 | claims every minute + checks against lektyra's own public-data service | ADR-010, ADR-014 |
| 4 | who gets what, in which form | open |

## 6. Open questions

1. Which first: parliament sessions, government press conferences, TV debates, politicians' own videos?
2. Who receives the findings, and in what form?
3. Keep short audio clips of confirmed samples (to change the embedding model later), or only the embeddings?
