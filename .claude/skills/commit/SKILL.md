---
name: commit
description: lektyra's commit format and rules. Use only when Martin asks for a commit.
---

# Commit (only when Martin asks)

- Run the `verify` skill first.
- Subject: `type(scope): what`, ≤ 72 characters. Types: feat, fix, docs, test, refactor, perf, build, ci, chore.
  Scopes: ingest, chunking, media, ta3, vad, stt, diarize, profiles, claims, eval, cli, hooks, skills, adr, board.
- Body: why, and the evidence (numbers, report, test names). Reference ADRs (`Refs: ADR-006`) and board ids
  (`Board: K2`).
- **No AI attribution** (no Co-Authored-By AI, no "Generated with"); hook L7 refuses it.
- The board moves in the same commit as the work.
- Never `--no-verify`. If a hook blocks, fix the cause, or change the ADR first and say so.
- Never commit `data/`, audio, video, embeddings, models or keys (hooks L1, L2, L5).
