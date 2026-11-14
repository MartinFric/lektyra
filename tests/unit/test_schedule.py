"""What a scheduled run needs now (ADR-016)."""

from datetime import UTC, datetime, timedelta

from lektyra.domain.schedule import SessionState, Slot, actions

T0 = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)  # 11:00 in Bratislava
HOUR = timedelta(hours=1)


def slot(status: str, session: SessionState = "none", start: datetime = T0, end: datetime = T0 + HOUR) -> Slot:
    return Slot(id="r", starts_at=start, ends_at=end, status=status, session=session)


def test_a_run_waits_for_its_time_and_then_starts() -> None:
    assert actions([slot("scheduled")], T0 - timedelta(seconds=1)) == []
    assert actions([slot("scheduled")], T0) == [("r", "start")]


def test_a_run_starts_late_when_lektyra_was_not_running_but_its_time_is_not_over() -> None:
    assert actions([slot("scheduled")], T0 + timedelta(minutes=20)) == [("r", "start")]


def test_a_run_whose_whole_time_passed_is_missed() -> None:
    assert actions([slot("scheduled")], T0 + HOUR) == [("r", "miss")]


def test_a_running_run_stops_at_its_end_and_finishes_when_its_session_has_ended() -> None:
    assert actions([slot("running", "running")], T0 + timedelta(minutes=59)) == []
    assert actions([slot("running", "running")], T0 + HOUR) == [("r", "stop")]
    assert actions([slot("running", "stopping")], T0 + HOUR) == []  # asked once is enough
    assert actions([slot("running", "ended")], T0 + timedelta(minutes=10)) == [("r", "finish")]  # the stream ended


def test_a_run_that_lost_its_session_to_a_restart_starts_again_or_is_lost() -> None:
    assert actions([slot("running", "none")], T0 + timedelta(minutes=30)) == [("r", "start")]
    assert actions([slot("running", "none")], T0 + HOUR) == [("r", "lost")]


def test_ended_runs_are_left_alone() -> None:
    for status in ("done", "failed", "missed", "cancelled"):
        assert actions([slot(status)], T0 + timedelta(minutes=5)) == []
