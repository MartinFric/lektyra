---
name: profile-pictures
description: Give every named person in lektyra a profile picture (ADR-015) — Wikidata/Commons first with licence and author, an official portrait page second, never private persons or social media. Use when Martin asks for pictures or faces, after new people are named, or when `lektyra photo missing` lists anyone.
---

# Profile pictures (ADR-015)

Faces next to names, so Martin recognises a name at a glance. lektyra re-encodes every picture (WebP, at most
512 px, no metadata) and keeps it in its own MinIO; the database keeps the source, licence and author, and the UI
shows them under the picture.

## Before

- Postgres and MinIO run: `docker compose up -d` (both containers healthy).
- The main database by default. `--database lektyra_manual` is the manual-test copy: its persons are made up, so
  they get no real pictures.

## Steps

1. **Who is missing:** `uv run lektyra photo missing` prints id, name, kind, function, party and knowledge link.
   Rows marked *not a public figure* are skipped: no picture from the web for them (ADR-005).
2. **Knowledge link is a Wikidata id (Q…):** `uv run lektyra photo set <id> --wikidata <Q…>`.
3. **No link yet:** `uv run lektyra photo find "<name>"` lists Wikidata items, people first, with their description
   and whether they have a picture. Take an item **only when it is clearly the same person**: a human, the right
   country, and a description that agrees with the person's function, party or kind (an MP is "slovenský politik",
   a host a "moderátor"). Two plausible items (namesakes), or a description that does not fit: skip it and say
   why. A wrong face misleads as much as a wrong name (ADR-004).
   Then `uv run lektyra photo set <id> --wikidata <Q…>`: it also fills the knowledge link, so the person is joined
   to that item from now on.
4. **The item has no picture, or there is no item:** an official portrait from the person's own institution:
   - the National Council's member page (nrsr.sk) for MPs;
   - the Government Office (vlada.gov.sk) or the ministry for ministers and state secretaries;
   - the organisation they speak for (a chamber, a university, a company's leadership page);
   - the broadcaster's own page for a host.

   `uv run lektyra photo set <id> --url <the image address> --source-url <the page it is on>`, plus
   `--license "<as the page states it>"` and `--author "<as credited>"` when the page says so. With no licence, leave
   `--license` out: the UI then says "licence unknown, local use only".
   If the site refuses lektyra's download (403), save the image with `curl -o "$CLAUDE_JOB_DIR/tmp/<id>.jpg"` and use
   `--file <that path> --source-url <the page>` instead.
5. **Nothing official:** skip and report. Never use social media accounts, news photos credited to an agency
   (TASR, SITA, Reuters…), stock or search-engine thumbnails, or a crop of a group photo, unless Martin asks for
   that one picture himself.
6. **Report** a table: name · source (Wikimedia Commons / site) · licence · or why it was skipped. Martin checks the
   faces on the Persons screen. A wrong picture: `uv run lektyra photo remove <id>`, and say what went wrong.

## Rules

- Unnamed voices get no picture (the command refuses): they are named or merged first.
- One request at a time to Wikimedia; no parallel fetching.
- What leaves the PC: a public figure's name (the Wikidata search) and picture downloads. Never a voice, a
  transcript or anything under `data/`.
- A picture Martin uploaded in the UI is his choice: never replace it without asking.

## Check

`uv run lektyra photo missing` again: whatever is left was skipped, and the report says why.
