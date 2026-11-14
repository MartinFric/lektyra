---
name: eval
description: How lektyra measures quality: Martin's reference transcripts, WER/CER, names and numbers accuracy, DER, cut quality, profile score distributions, and the report format in docs/eval/. Use before writing evaluation code or reporting a quality number.
---

# Evaluation

## References (the truth)

- Martin writes them, helped by `lektyra compare <event> --window mm:ss-mm:ss`: an HTML page with every
  engine's text side by side every 10 s, disagreements highlighted, each row playing the audio from that second.
- File `data/refs/<event>_<from>-<to>.md` (git-ignored: a transcript of a broadcast is ADR-005 material). The
  `compare` command writes it prefilled; lines are `**[mm:ss] S1:** text`, speaker turns marked in the same pass.
- References start from the engines' disagreements, not from one engine's draft, so no engine is favoured.

## Metrics

| what | metric |
|---|---|
| transcript | WER and CER after normalisation (lower case, punctuation off, numbers as words *and* as digits both accepted) |
| fact-check value | names (persons, parties, institutions, companies) and numbers (amounts, dates, %) correct, % of reference entities |
| speakers | DER (pyannote.metrics), speaker count |
| cutting (ADR-006) | reference words whose span crosses a cut (**must be 0**); WER in ±3 s around cuts vs elsewhere |
| profiles | same-person vs other-person score histograms, EER, hits and **false names** at the chosen threshold |
| practical | cost per audio hour, wall time per audio hour |

## Reports

`docs/eval/YYYY-MM-DD-<topic>.md`. Each report contains:
- the question and the data used (event ids, minutes), with no audio;
- the table of numbers;
- what it decides, linked to the ADR it feeds.

Numbers in chat, the board or an ADR always cite a report.

Evaluation reads saved answers only (ADR-003). It never calls an API.
