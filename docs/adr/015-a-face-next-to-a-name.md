# ADR-015: A face next to a name; pictures live in lektyra's own MinIO

*Status: accepted · 2026-11-14 · Martin ("assign profile pictures to named persons … so i can see face besides
name", "i would use minio for photo storage. not in postgres as blob", "we have minio … so you can run it")*

## Context

Martin names voices while he watches. A list of names is slow to read; a face is recognised at once. A picture of a
person is personal data and, usually, someone's copyrighted work. lektyra already keeps voices of public figures
locally (ADR-005); pictures join them.

## Decision

1. **One picture per named person.** An unnamed voice has none: name it, or merge it into a person, first.
2. **Where pictures come from:** a file Martin drops into the UI; Wikidata's image of the person (Wikimedia
   Commons, with its licence and author); an official portrait page (the institution's own site), found by the skill
   `profile-pictures`. Never pictures of anyone who is not a public figure from the web, never social media.
3. **lektyra re-encodes every picture:** first frame, turned upright, flattened onto white, at most 512 px, WebP,
   no metadata. Only JPEG, PNG, WebP and GIF are opened; at most 15 MB and 50 megapixels.
4. **Files live in lektyra's own MinIO** (compose service `objects`, `127.0.0.1:59000`, console `:59001`, bucket
   `lektyra-pictures`), as `persons/<person key>/<version>.webp`. It is never another project's MinIO (ADR-014).
   MinIO's own community images stopped in 2025 and its repository is archived: the image is the community fork
   `pgsty/minio`, pinned by digest. Its login is generated into `~/.secrets/lektyra-minio.env`, which compose and
   lektyra's settings both read; it never enters the repo.
5. **Postgres keeps what the picture is:** `person_photo` with the object key, version, size, source address,
   licence, author, who added it and when. The browser never talks to MinIO: the API serves
   `/api/persons/{id}/photo?v=<version>` (cached for good, since a new picture is a new address; `nosniff`).
6. **Forgetting deletes the picture too** (ADR-005): the row goes with the person, then every object no row points
   at is swept, right after a forget and whenever `lektyra ui` starts. Objects are written before rows and deleted
   after them, so a failure leaves an orphan the sweep removes, never a row without its file.
7. **A picture store that is down turns faces off, nothing else:** names show initials, picture actions say why.

## Consequences

- A second container to run (`docker compose up -d` starts both). A backup must cover the `lektyra-minio` volume
  as well as Postgres.
- Pictures with an unknown licence are for Martin's screen only; before lektyra is handed over or shown publicly,
  they are replaced or removed (the credit line under each picture says which).
- The same store can later hold other files lektyra keeps (uploaded videos).

## Enforced by

`migrations/0004_person_photo.sql`; `tests/integration/test_review_api.py` (a picture lektyra made itself, refusals,
Wikidata licence and author, forgetting deletes the picture); `tests/contract/test_pictures.py`,
`test_wikimedia.py`, `test_s3_objects.py` (the real MinIO); the skill `profile-pictures`.
