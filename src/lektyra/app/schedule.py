"""Live runs on a schedule (ADR-016): TA3 at 11:00 for an hour, STVR at 11:55… lektyra starts and stops them itself.

A thread in `lektyra ui` looks every few seconds, so the PC must be on and `lektyra ui` running at the time. Each
run is an ordinary live session (several may overlap); when it ends it points at the video it became. A run that
fails before its time is over is started again (a dropped stream), a few times at most.
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final, Protocol

from pydantic import BaseModel

from lektyra.adapters.store.postgres import RunRow, RunStatus, Store
from lektyra.app.live import LiveState, check_source
from lektyra.domain.schedule import Action, SessionState, Slot, actions
from lektyra.errors import LektyraError

log = logging.getLogger("lektyra.schedule")

TICK_S: Final = 5.0
LONGEST: Final = timedelta(hours=6)
FURTHEST: Final = timedelta(days=60)
KEEP: Final = timedelta(days=14)  # ended runs still listed
RETRIES: Final = 3  # a run whose session fails before its end is started again this many times
LATE: Final = timedelta(minutes=1)


class LiveControl(Protocol):
    def start(self, source: str, title: str | None, transcribe: bool) -> LiveState: ...

    def stop(self, session_id: str) -> LiveState: ...

    def state(self, session_id: str) -> LiveState | None: ...


class Run(BaseModel):
    id: str
    source: str
    title: str
    starts_at: datetime
    ends_at: datetime
    transcribe: bool
    status: RunStatus
    session_id: str | None
    event_id: str | None
    message: str | None


def _run(row: RunRow) -> Run:
    return Run(**row.model_dump(exclude={"created_at"}))


def _session_state(state: LiveState | None) -> SessionState:
    if state is None:
        return "none"
    if state.status in ("finished", "failed"):
        return "ended"
    return "stopping" if state.status == "stopping" else "running"


class Scheduler:
    def __init__(
        self,
        store: Store,
        live: LiveControl,
        actor: str,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._live = live
        self._actor = actor
        self._now = now
        self._retries: dict[str, int] = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # what Martin does -------------------------------------------------------------------------------------------
    def runs(self) -> list[Run]:
        return [_run(r) for r in self._store.runs(self._now() - KEEP)]

    def add(self, source: str, title: str, starts_at: datetime, ends_at: datetime, transcribe: bool) -> Run:
        check_source(source)
        now = self._now()
        if ends_at <= starts_at:
            raise LektyraError("invalid", "The end must be after the start.")
        if ends_at - starts_at > LONGEST:
            raise LektyraError("invalid", "A run is at most 6 hours long.")
        if ends_at <= now:
            raise LektyraError("invalid", "This time is over already: pick a time still to come.")
        if starts_at - now > FURTHEST:
            raise LektyraError("invalid", "Schedule at most 60 days ahead.")
        run = _run(self._store.add_run(source, title.strip(), starts_at, ends_at, transcribe, self._actor))
        self.tick()  # a run that should be on air already starts now, not in a few seconds
        return _run(self._store.run(run.id))

    def cancel(self, run_id: str) -> Run:
        """A run still to come is cancelled; a running one is stopped now (what it heard stays a video)."""
        with self._lock:
            run = self._store.run(run_id)
            if run.status == "scheduled":
                self._store.update_run(run_id, "cancelled", "Cancelled.")
            elif run.status == "running":
                state = self._live.state(run.session_id) if run.session_id else None
                if state is not None and _session_state(state) == "running":
                    self._live.stop(state.id)
                event = state.event_id if state else None
                self._store.update_run(run_id, "cancelled", "Stopped early by you; what it heard is kept.", None, event)
            else:
                raise LektyraError("conflict", "This run has ended already.")
            return _run(self._store.run(run_id))

    def uses(self, source: str) -> bool:
        """Does a run still to come (or running) need this source (an upload about to be deleted)?"""
        return any(r.source == source and r.status in ("scheduled", "running") for r in self.runs())

    # the clock --------------------------------------------------------------------------------------------------
    def tick(self) -> None:
        with self._lock:
            now = self._now()
            rows = {r.id: r for r in self._store.runs(now - KEEP)}
            states = {r.id: self._live.state(r.session_id) if r.session_id else None for r in rows.values()}
            slots = [Slot(r.id, r.starts_at, r.ends_at, r.status, _session_state(states[r.id])) for r in rows.values()]
            for run_id, action in actions(slots, now):
                try:
                    self._do(rows[run_id], action, states[run_id], now)
                except LektyraError as err:
                    self._store.update_run(run_id, "failed", err.message)
                except Exception as error:  # one broken run must not stop the others
                    log.error("scheduled run %s failed", run_id, exc_info=error)
                    self._store.update_run(run_id, "failed", f"Could not {action}: {type(error).__name__}.")

    def _do(self, run: RunRow, action: Action, state: LiveState | None, now: datetime) -> None:
        if action == "start":
            started = self._live.start(run.source, run.title, run.transcribe)
            if run.status == "running":
                message = "Started again after lektyra restarted."
            elif now - run.starts_at > LATE:
                message = f"Started late, at {now.astimezone():%H:%M}: lektyra was not running at the time."
            else:
                message = "Listening."
            self._store.update_run(run.id, "running", message, started.id, None)
        elif action == "stop":
            if state is not None:
                self._live.stop(state.id)
            self._store.update_run(run.id, "running", "Stopping at the end of its time…")
        elif action == "finish" and state is not None:
            tries = self._retries.get(run.id, 0)
            if state.status == "failed" and now < run.ends_at - LATE and tries < RETRIES:
                self._retries[run.id] = tries + 1
                again = self._live.start(run.source, run.title, run.transcribe)
                note = f"The source dropped ({state.message}); started again ({tries + 1}/{RETRIES})."
                self._store.update_run(run.id, "running", note, again.id, None)
                return
            status: RunStatus = "done" if state.status == "finished" else "failed"
            self._store.update_run(run.id, status, state.message, None, state.event_id)
        elif action == "miss":
            self._store.update_run(run.id, "missed", "Missed: lektyra was not running during this time.")
        elif action == "lost":
            self._store.update_run(run.id, "failed", "lektyra stopped during this run; what it heard is in Videos.")

    def start(self) -> None:
        threading.Thread(target=self._loop, name="lektyra-schedule", daemon=True).start()

    def close(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(TICK_S):
            try:
                self.tick()
            except Exception as error:  # a database restart must not end the schedule for good
                log.warning("schedule check failed: %s", type(error).__name__)
