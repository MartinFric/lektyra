"""swap (2026-11-15): a reader holding the old file open must not end a live session on Windows."""

import contextlib
import threading
import time
from pathlib import Path

import pytest

from lektyra import atomic
from lektyra.atomic import swap


def test_swap_replaces_the_file(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text("old", encoding="utf-8")
    (tmp_path / "a.json.part").write_text("new", encoding="utf-8")
    swap(tmp_path / "a.json.part", tmp_path / "a.json")
    assert (tmp_path / "a.json").read_text(encoding="utf-8") == "new"
    assert not (tmp_path / "a.json.part").exists()


def test_swap_waits_out_a_short_denial(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    denials = iter([True, True, False])
    real = Path.replace

    def busy(self: Path, target: Path) -> Path:
        if next(denials):
            raise PermissionError(5, "Access is denied")
        return real(self, target)

    monkeypatch.setattr(Path, "replace", busy)
    monkeypatch.setattr(atomic, "PAUSE_S", 0.001)
    (tmp_path / "x.part").write_text("new", encoding="utf-8")
    swap(tmp_path / "x.part", tmp_path / "x")
    assert (tmp_path / "x").read_text(encoding="utf-8") == "new"


def test_swap_gives_up_when_the_file_stays_locked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def locked(self: Path, target: Path) -> Path:
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr(atomic, "PAUSE_S", 0.0)
    with pytest.raises(PermissionError):
        swap(tmp_path / "x.part", tmp_path / "x")


def test_swap_against_a_real_reader(tmp_path: Path) -> None:
    target = tmp_path / "speakers.npy"
    target.write_bytes(b"old")
    stop = threading.Event()

    def reader() -> None:
        while not stop.is_set():
            with contextlib.suppress(OSError):  # the reader may meet the swap: only the writer matters
                target.read_bytes()

    thread = threading.Thread(target=reader)
    thread.start()
    try:
        for i in range(200):
            part = tmp_path / "speakers.part.npy"
            part.write_bytes(str(i).encode())
            swap(part, target)
            time.sleep(0.001)
    finally:
        stop.set()
        thread.join()
    assert target.read_bytes() == b"199"
