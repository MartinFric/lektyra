---
name: privacy
description: What lektyra may store, show, send and commit, given copyrighted broadcasts and biometric voice data (ADR-005). Use before touching data/, logging, exports, profiles, reports or anything that leaves the PC.
---

# Privacy and rights (ADR-005)

## The material

- **Broadcasts** (TA3 and others) are copyrighted. They are downloaded for internal research only, kept under
  `data/`, never published or shared as audio or video. Reports may quote short passages with the source.
- **Voice embeddings and profiles are biometric data** (GDPR Art. 9 when used to identify someone). They stay in
  the local database. Before anything runs continuously or leaves this PC: a DPIA.
- **Pictures of persons** (ADR-015) are personal data and someone's work: only for named public figures, from
  Commons (licence kept) or their institution's own page; kept in lektyra's own MinIO, deleted by `forget`.
- Persons in scope: people in a **public role**, speaking publicly. Moderators, journalists and guests are weaker
  cases: profile them only when needed for the test, and `forget` them after.

## Never

- commit anything under `data/`, audio, video, embeddings or model files (hooks L1, L2);
- print or log a key, a token-bearing URL, or an embedding (`SecretStr`, `SourceInfo.media_url` excluded);
- send audio anywhere but the speech-to-text engine being evaluated;
- put real voices or TA3 transcripts into tests or fixtures;
- read `~/.secrets/` or `data/` into a chat or an agent's context beyond what the task needs.

## Always

- ask for zero data retention where an engine offers it, and record it;
- keep `forget` working: a new table holding person-linked data must be deleted by `forget` and covered by its
  test;
- audit every naming, rejection and forget (who, when, what), with no biometric content in the audit.
