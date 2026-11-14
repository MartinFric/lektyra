# ADR-005: Data stays local; nothing biometric or copyrighted in git; forget

*Status: accepted · 2026-11-14 · Martin*

## Context

The material is broadcast video (copyrighted, e.g. TA3) and the profiles are voice embeddings of real people
(biometric data, GDPR Art. 9 when used to identify someone). The spike runs on Martin's PC. Only speech-to-text
calls leave it.

## Decision

- Audio, video, pieces, embeddings, model answers and the database live under `data/` and in the local Postgres.
  Both are git-ignored. **None of it enters git**, and nothing is exported or published.
- Downloaded broadcasts are for internal research only.
- Speech-to-text requests ask for zero data retention where the provider offers it.
- `lektyra forget "<person>"` deletes a person, their samples and profile completely, and leaves an audit entry.
- Keys live in `~/.secrets/lektyra.env`, are loaded as `SecretStr`, and are never printed or logged.
- Before anything runs continuously, or data leaves this PC: a DPIA (see the concept, section 4).

## Consequences

Tests use license-clean fixtures (synthetic signals, LibriSpeech CC BY, generated speech). Sharing results means
sharing reports (text, numbers), never audio or embeddings.

## Enforced by

pre-commit L1 (data file types and `data/`), L2 (files > 1 MB) and L5 (gitleaks); `.gitignore`; `SourceInfo.media_url`
excluded from saved files; `.claude/settings.json` denies agents `data/` and `~/.secrets/`; the `privacy` skill.
