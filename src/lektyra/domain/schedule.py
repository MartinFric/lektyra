"""What a scheduled run needs now (ADR-016). Pure: given the runs and the time, the actions; the scheduler does them.

A run starts at `starts_at` (late if lektyra was not running then, as long as its time is not over), stops at
`ends_at`, and ends when its session ends. A run whose whole time passed while lektyra was not running is missed.
A run that was running when lektyra stopped starts again for the time left, or is lost.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

SessionState = Literal["none", "running", "stopping", "ended"]  # "none": no such session in this process
Action = Literal["start", "stop", "finish", "miss", "lost"]


@dataclass(frozen=True)
class Slot:
    id: str
    starts_at: datetime
    ends_at: datetime
    status: str  # scheduled, running, done, failed, missed, cancelled
    session: SessionState


def actions(slots: Sequence[Slot], now: datetime) -> list[tuple[str, Action]]:
    due: list[tuple[str, Action]] = []
    for s in slots:
        if s.status == "scheduled":
            if now >= s.ends_at:
                due.append((s.id, "miss"))
            elif now >= s.starts_at:
                due.append((s.id, "start"))
        elif s.status == "running":
            if s.session == "none":
                due.append((s.id, "start" if now < s.ends_at else "lost"))
            elif s.session == "ended":
                due.append((s.id, "finish"))
            elif s.session == "running" and now >= s.ends_at:
                due.append((s.id, "stop"))
    return due
