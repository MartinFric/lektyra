"""A claims minute that fails is asked again, then skipped for good (review 2026-11-15, point 5)."""

from pathlib import Path

from lektyra.adapters.llm.openrouter_claims import RawCompletion
from lektyra.app.claims import ASK_ATTEMPTS, ask_minute


class Model:
    def __init__(self, statuses: list[int]) -> None:
        self.statuses = statuses
        self.asked = 0

    def ask(self, user: str) -> RawCompletion:
        status = self.statuses[min(self.asked, len(self.statuses) - 1)]
        self.asked += 1
        return RawCompletion(status=status, body='{"ok": true}' if status == 200 else "busy", wall_ms=1)


def test_a_minute_that_fails_once_is_asked_again_and_saved(tmp_path: Path) -> None:
    model, waits = Model([502, 200]), list[float]()
    answer = ask_minute(model.ask, "minute", tmp_path / "m005.json", tmp_path / "m005.skipped", waits.append)
    assert (answer.status, model.asked, waits) == (200, 2, [4.0])
    assert (tmp_path / "m005.json").read_text(encoding="utf-8") == '{"ok": true}'
    assert not (tmp_path / "m005.skipped").exists()


def test_a_minute_that_keeps_failing_is_skipped_for_good(tmp_path: Path) -> None:
    model = Model([500])
    answer = ask_minute(model.ask, "minute", tmp_path / "m005.json", tmp_path / "m005.skipped", lambda _s: None)
    assert (answer.status, model.asked) == (500, ASK_ATTEMPTS)
    assert not (tmp_path / "m005.json").exists()
    assert (tmp_path / "m005.skipped").read_text(encoding="utf-8").startswith("HTTP 500")
