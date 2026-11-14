"""Clock strings ↔ milliseconds, for windows on the command line and in reports."""

import re
from typing import Final

_CLOCK: Final = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)$|^(\d+(?:\.\d+)?)$")


def parse_clock(text: str) -> int:
    """'1:02:03', '20:00', '75' (seconds) or '75.5' → ms."""
    m = _CLOCK.match(text.strip())
    if not m:
        raise ValueError(f"not a time: {text!r} (use mm:ss, h:mm:ss or seconds)")
    if m.group(4) is not None:
        return round(float(m.group(4)) * 1000)
    hours = int(m.group(1) or 0)
    return round((hours * 3600 + int(m.group(2)) * 60 + float(m.group(3))) * 1000)


def parse_window(text: str) -> tuple[int, int]:
    """'20:00-30:00' → (1_200_000, 1_800_000)."""
    if "-" not in text:
        raise ValueError(f"not a window: {text!r} (use from-to, e.g. 20:00-30:00)")
    a, b = text.split("-", 1)
    lo, hi = parse_clock(a), parse_clock(b)
    if hi <= lo:
        raise ValueError(f"the window ends before it starts: {text!r}")
    return lo, hi


def clock(ms: float) -> str:
    """ms → 'mm:ss' (or 'h:mm:ss' from an hour)."""
    total = int(ms // 1000)
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
