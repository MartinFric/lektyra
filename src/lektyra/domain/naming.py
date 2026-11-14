"""Names of events on disk. Pure: the caller passes the time (ADR-002)."""

import re
import unicodedata
from datetime import datetime


def slug(text: str, max_len: int = 48) -> str:
    """ASCII, lower case, words joined by '-'. Slovak diacritics fold to their base letters."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    words = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return words[:max_len].rstrip("-") or "event"


def event_id(title: str, started: datetime) -> str:
    return f"{started:%Y-%m-%d_%H-%M-%S}_{slug(title)}"
