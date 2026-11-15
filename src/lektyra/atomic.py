"""Swap a finished file into place, also on Windows while someone reads the old one.

`Path.replace` is atomic, but on Windows it fails with "Access is denied" for as long as another handle has the
target open. The UI's API reads speakers.npy, diarization.json and the claim ledger every few seconds while a live
session rewrites them; on 2026-11-15 one such collision ended the TA3 session after nine minutes. A read lasts
milliseconds, so the swap tries again for up to two seconds before it gives up.
"""

import time
from pathlib import Path
from typing import Final

ATTEMPTS: Final = 40
PAUSE_S: Final = 0.05


def swap(part: Path, path: Path) -> None:
    """Move the finished `part` onto `path` in one step, waiting out a reader that holds `path` open."""
    for attempt in range(ATTEMPTS):
        try:
            part.replace(path)
            return
        except PermissionError:
            if attempt == ATTEMPTS - 1:
                raise
            time.sleep(PAUSE_S)
