"""The scheduler on a clock (ADR-016): runs start on time, stop at their end, point at their video, start again after
a dropped stream, and are missed when lektyra was not running. Real store (lektyra_test_schedule), fake live."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest

from lektyra.adapters.store.postgres import Store, ensure_database, with_database
from lektyra.app.live import LiveState, LiveStatus
from lektyra.app.schedule import Scheduler
from lektyra.settings import load_settings

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2030, 1, 6, 10, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def _state(session_id: str, status: LiveStatus, event_id: str | None = None) -> LiveState:
    return LiveState(
        id=session_id, status=status, message=f"{status}.", source="ta3:live", title="V politike",
        event_id=event_id, is_live=True, duration_s=None, media=False, started_at=T0, position_ms=0, current=None,
        speakers=[], turns=[], pieces=0, transcribe=True, transcribed=0, stt_errors=0, variant=None, cost_usd=0.0,
    )  # fmt: skip


class FakeLive:
    def __init__(self) -> None:
        self.sessions: dict[str, LiveState] = {}
        self.started: list[str] = []
        self.stopped: list[str] = []

    def start(self, source: str, title: str | None, transcribe: bool) -> LiveState:
        self.started.append(source)
        state = _state(f"s{len(self.started)}", "running")
        self.sessions[state.id] = state
        return state

    def stop(self, session_id: str) -> LiveState:
        self.stopped.append(session_id)
        self.sessions[session_id] = self.sessions[session_id].model_copy(update={"status": "stopping"})
        return self.sessions[session_id]

    def state(self, session_id: str) -> LiveState | None:
        return self.sessions.get(session_id)

    def end(self, session_id: str, status: LiveStatus, event_id: str) -> None:
        self.sessions[session_id] = _state(session_id, status, event_id)


@pytest.fixture
def store() -> Iterator[Store]:
    url = with_database(load_settings().database_url, "lektyra_test_schedule")
    try:
        ensure_database(url, reset=True)
    except psycopg.OperationalError:
        pytest.skip("local Postgres is not running (docker compose up -d)")
    db = Store(url)
    db.migrate(ROOT / "migrations")
    yield db
    db.close()


def _scheduler(store: Store, live: FakeLive, clock: list[datetime]) -> Scheduler:
    return Scheduler(store, live, "test", now=lambda: clock[0])


def test_a_run_starts_on_time_stops_at_its_end_and_points_at_its_video(store: Store) -> None:
    clock, live = [T0 - timedelta(minutes=5)], FakeLive()
    schedule = _scheduler(store, live, clock)
    run = schedule.add("ta3:live", "V politike", T0, T0 + HOUR, True)
    schedule.tick()
    assert (run.status, live.started) == ("scheduled", [])
    clock[0] = T0
    schedule.tick()
    running = schedule.runs()[0]
    assert (running.status, running.session_id, running.message, live.started) == (
        "running", "s1", "Listening.", ["ta3:live"],
    )  # fmt: skip
    clock[0] = T0 + HOUR
    schedule.tick()
    schedule.tick()  # asked to stop once is enough
    assert live.stopped == ["s1"]
    live.end("s1", "finished", "2030-01-06_11-00-00_v-politike")
    schedule.tick()
    done = schedule.runs()[0]
    assert (done.status, done.event_id) == ("done", "2030-01-06_11-00-00_v-politike")


def test_a_dropped_stream_is_started_again_until_the_end(store: Store) -> None:
    clock, live = [T0], FakeLive()
    schedule = _scheduler(store, live, clock)
    schedule.add("stvr:1", "O 5 minút 12", T0, T0 + HOUR, True)  # due now: starts at once
    assert live.started == ["stvr:1"]
    clock[0] = T0 + timedelta(minutes=10)
    live.end("s1", "failed", "2030-01-06_11-00-00_part-1")
    schedule.tick()
    again = schedule.runs()[0]
    assert (again.status, again.session_id, live.started) == ("running", "s2", ["stvr:1", "stvr:1"])
    assert again.message is not None and "started again (1/3)" in again.message


def test_a_run_is_missed_when_lektyra_was_not_running(store: Store) -> None:
    clock, live = [T0 - timedelta(minutes=5)], FakeLive()
    schedule = _scheduler(store, live, clock)
    schedule.add("ta3:live", "V politike", T0, T0 + HOUR, True)
    clock[0] = T0 + 2 * HOUR  # the PC was off the whole time
    schedule.tick()
    missed = schedule.runs()[0]
    assert (missed.status, live.started) == ("missed", [])


def test_a_late_start_says_so(store: Store) -> None:
    clock, live = [T0 - timedelta(minutes=5)], FakeLive()
    schedule = _scheduler(store, live, clock)
    schedule.add("ta3:live", "V politike", T0, T0 + HOUR, True)
    clock[0] = T0 + timedelta(minutes=20)
    schedule.tick()
    late = schedule.runs()[0]
    assert late.status == "running"
    assert late.message is not None and late.message.startswith("Started late")
