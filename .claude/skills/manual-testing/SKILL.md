---
name: manual-testing
description: "Look at a UI change the way Martin will: the real lektyra UI on a separate database (lektyra_manual), driven in a headless Edge by scripts/manual/ui_drive.py, with screenshots read back after every action. Use after any change under web/ or the review API, before saying it works; it replaces end-to-end tests for this local tool. DO NOT use it for the main database, for live streams, or as a substitute for the unit and API tests (skill testing)."
---

# Manual testing: the real UI, a throwaway database

Tests prove the code; this proves what Martin sees. **A shot you have not read back is not a look.** Every UI
change gets a walk through the screens it touches, with shots, before anyone says it works. That is the bar
instead of end-to-end tests: faster to change, and it catches what tests miss (alignment, overflow, a click that
lands on nothing).

Two pieces:

- `lektyra ui --database lektyra_manual [--reset] --port 8799` serves the built UI on a **separate database**:
  migrated, synced from `data/events/`, so the real videos are there, but every name, rating and flag you make
  stays out of Martin's database.
- `scripts/manual/ui_drive.py` keeps one headless Edge page open in a small daemon, so a dialog opened by one
  command is still open for the next.

## Hard rules

1. **Never the main database.** Always `--database lektyra_manual`. `--reset` refuses the main one; never work
   around that. Martin's names live in `lektyra` and are his decisions (ADR-004).
2. **No real names on voices in the manual database.** Use `Test Voice One`, `Test Voice Two`, … A wrong
   name in a screenshot is still a wrong name (ADR-004, ADR-005).
3. **Shots stay out of the repo** (they show transcripts of broadcasts, ADR-005): the job's tmp folder or the
   session scratchpad, never `docs/` or `web/`.
4. **Shot after every action that should change something, and read it.** The driver fails loudly (exit 1) when
   a selector finds nothing; a click that "worked" can still have done nothing, so look.
5. **Read `console` after each screen.** Browser errors, failed requests and HTTP ≥ 400 are listed there. An
   expected one (a 409 you provoked) is fine; an unexpected one is a finding.
6. **Put things back:** `ui_drive.py stop`, stop the server. Leave the database (it is throwaway) unless asked.

## The loop

```bash
cd C:/Work/dev-personal/lektyra
(cd web && npm run build)                                  # the server serves web/dist
uv run lektyra ui --database lektyra_manual --reset --port 8799        # background
uv run python scripts/manual/ui_drive.py serve --shots <tmp>/shots     # background
D="uv run python scripts/manual/ui_drive.py"
$D goto videos                    # paths without the leading "/": Git Bash rewrites "/videos" into a Windows path
$D shot 01-videos                 # → prints the PNG path; Read it
$D click "text=A V politike"      # Playwright selectors: text=, role=button[name='…'], CSS
$D fill "role=textbox[name='Find or add a person']" "Test Voice One"
$D press Enter
$D hover "li[data-index='1']"     # hover-only controls (the paragraph flag button)
$D text "main"                    # the visible text, when a shot is not enough
$D console                        # errors since the last call
$D stop
```

- A button's accessible name is its **text**, not its `title`: the transcript's time buttons are `role=button[name='0:17']`.
- After a Python change, restart `lektyra ui`; after a web change, `npm run build` (no restart needed: the server
  reads `web/dist` per request). After a change to `ui_drive.py`, `stop` and `serve` again.
- Headless Edge plays audio silently, so playback, seeking and "speaking now" can be checked by shots; whether it
  *sounds* right cannot.

## Scenarios (walk what the change touches)

- **Videos**: every card shows duration, speakers named, transcripts; a click opens the video.
- **Video**: speakers by talk share with their colours; transcripts (complete ones only) and documents listed.
- **Naming**: Name… → type a new name → "Add … as a new person" names the speaker; the row shows a spinner
  ("learning the voice") then *named*; the other videos' speakers of the same voice turn *Sounds like* (≥ 0.70) or
  *Maybe* (≥ 0.55). **Not X** removes a guess for good; **Confirm** names it; ✕ removes a name.
- **Transcript**: Play, ±10 s, speed, click the timeline, click a paragraph's time; the heard paragraph is marked
  and followed; *Speaking now* names the current turn; naming there updates every paragraph at once.
- **Rating and flags**: stars (clicking the chosen one clears it), note, Save (disabled until something changed);
  a paragraph's flag opens the dialog; the flag shows on the paragraph and in the list; delete it.
- **Persons**: create, edit, a duplicate name shows inline under Name and clears when the name changes; Forget
  asks first and lists what will be deleted.
- **Voice map**: dots by person, rings for unconfirmed matches, tooltip with the closest voices (flips below
  dots near the top), the table truncates long titles.
- **Errors**: an unknown video shows the error panel without *Try again*; with the database stopped
  (`docker stop lektyra-db`, then `docker start lektyra-db`) a page retries quietly and recovers; a mutation
  that fails shows a toast.

## Report

Tell Martin what was walked and what each shot showed, in plain words, with the shot paths in full. List what a
shot cannot prove (sound, real latency on a live stream). Findings become board rows like any other.
