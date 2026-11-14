"""The review API end to end on a throwaway database (lektyra_test) and synthetic voices: naming teaches a voice,
other videos are matched again, "not this person" sticks, forgetting deletes, and every error has one shape.
No real audio or voice is used (ADR-005). Needs the local Postgres: `docker compose up -d`."""

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient

from lektyra.adapters.store.postgres import Store, ensure_database, with_database
from lektyra.adapters.web.api import create_app
from lektyra.app.live import LiveManager
from lektyra.app.review import Review
from lektyra.settings import Settings, load_settings

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[2]
DIM = 16
ONE, TWO, THREE = "2026-01-01_10-00-00_one", "2026-01-02_10-00-00_two", "2026-01-03_10-00-00_three"
VARIANT = "elevenlabs__scribe-v2@sk"


def _event(folder: Path, voices: list[np.ndarray], rng: np.random.Generator) -> None:
    """An event folder with what sync and naming read: manifest, diarization, centroids, window embeddings."""
    folder.mkdir(parents=True)
    manifest = {
        "event": folder.name,
        "started_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "source": {"url": f"https://example.test/{folder.name}", "title": folder.name, "is_live": False,
                   "resolved_by": "direct"},
        "rule": {},
        "audio_ms": 600_000,
        "finished": True,
        "pieces": [],
    }  # fmt: skip
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    windows, keys, centres, speakers, turns, start = [], [], [], [], [], 0
    for index, voice in enumerate(voices):
        mine = np.stack([voice + rng.normal(0, 0.15, DIM) for _ in range(40)]).astype(np.float32)
        mine /= np.linalg.norm(mine, axis=1, keepdims=True)
        windows.append(mine)
        keys += [[start + i * 1000, start + i * 1000 + 2000, 0] for i in range(40)]
        centre = mine.mean(axis=0)
        centres.append(centre / np.linalg.norm(centre))
        speakers.append({"label": f"S{index + 1}", "talk_s": 40.0, "share": 1 / len(voices), "turns": 1})
        turns.append({"start_ms": start, "end_ms": start + 40_000, "speaker": f"S{index + 1}"})
        start += 40_000
    np.savez(folder / "embeddings.npz", windows=np.array(keys, dtype=np.int64), emb=np.concatenate(windows))
    np.save(folder / "speakers.npy", np.stack(centres).astype(np.float32))
    diarization = {"embedder": "test-embedder", "threshold": 0.55, "windows": len(keys), "speakers": speakers,
                   "unclear_s": 0, "turns": turns}  # fmt: skip
    (folder / "diarization.json").write_text(json.dumps(diarization), encoding="utf-8")
    (folder / "raw" / VARIANT).mkdir(parents=True)


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    url = with_database(load_settings().database_url, "lektyra_test")
    try:
        ensure_database(url, reset=True)
    except psycopg.OperationalError:
        pytest.skip("local Postgres is not running (docker compose up -d)")
    events = tmp_path_factory.mktemp("events")
    rng = np.random.default_rng(7)
    a, b, c = (rng.normal(0, 1, DIM) for _ in range(3))
    _event(events / ONE, [a, b], rng)
    _event(events / TWO, [b, a], rng)
    _event(events / THREE, [c], rng)
    store = Store(url)
    store.migrate(ROOT / "migrations")
    data = events.parent
    review = Review(store, events, "test")

    def no_embedder() -> tuple[Callable[[list[np.ndarray]], np.ndarray], str]:
        raise AssertionError("no live session runs in these tests")

    live = LiveManager(Settings(data_dir=data), store, review, no_embedder)
    with TestClient(create_app(review, live, None)) as test_client:
        yield test_client
    store.close()


def _speakers(client: TestClient, event: str) -> dict[str, dict[str, object]]:
    answer = client.get(f"/api/events/{event}/speakers")
    assert answer.status_code == 200
    return {s["label"]: s for s in answer.json()}


def _error(answer: object) -> dict[str, object]:
    assert hasattr(answer, "json")
    body = answer.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    error: dict[str, object] = body["error"]
    return error


def _number(speaker: dict[str, object]) -> object:
    return speaker["person_number"]


def test_every_voice_gets_a_number_that_continues_across_videos(client: TestClient) -> None:
    assert client.post("/api/sync").json() == {"events": 3, "speakers": 5}
    one, two, three = _speakers(client, ONE), _speakers(client, TWO), _speakers(client, THREE)
    # The oldest video founds Voice 1 and 2; the next video hears the same two voices; the third a new one.
    assert [(one[s]["status"], _number(one[s])) for s in ("S1", "S2")] == [("new", 1), ("new", 2)]
    assert [(two[s]["status"], _number(two[s])) for s in ("S1", "S2")] == [("auto", 2), ("auto", 1)]
    assert (three["S1"]["status"], _number(three["S1"])) == ("new", 3)
    voices = client.get("/api/persons").json()
    assert [(p["name"], p["anonymous"]) for p in voices] == [("Voice 1", True), ("Voice 2", True), ("Voice 3", True)]
    assert client.post("/api/sync").json() == {"events": 3, "speakers": 5}
    assert _number(_speakers(client, THREE)["S1"]) == 3  # a re-sync never renumbers


def test_a_person_has_a_kind_a_lasting_key_and_a_knowledge_link(client: TestClient) -> None:
    bad = client.post("/api/persons", json={"name": "Linked", "external_ref": "wikipedia please"})
    assert bad.status_code == 422
    assert _error(bad)["details"] == [
        {"field": "external_ref", "message": "Value error, Use a Wikidata id (Q123) or a web address (https://…)."}
    ]
    made = client.post("/api/persons", json={"name": "Linked", "kind": "host", "external_ref": "Q42"}).json()
    assert (made["kind"], made["external_ref"], len(made["key"])) == ("host", "Q42", 36)
    renamed = client.put(f"/api/persons/{made['id']}", json={"name": "Linked Again", "kind": "host"}).json()
    assert renamed["key"] == made["key"]  # the key outlives renames
    assert client.delete(f"/api/persons/{made['id']}").status_code == 204


def test_naming_a_voice_names_it_in_every_video_and_keeps_its_number(client: TestClient) -> None:
    person = client.post("/api/persons", json={"name": "Alpha Person", "function": "tester", "kind": "politician"})
    assert person.status_code == 201
    pid = person.json()["id"]

    assert client.put(f"/api/events/{ONE}/speakers/S1/person", json={"person_id": pid}).status_code == 204
    alpha = next(p for p in client.get("/api/persons").json() if p["id"] == pid)
    assert (alpha["number"], alpha["anonymous"], alpha["samples"]) == (1, False, 4)  # Voice 1 merged into Alpha
    assert alpha["events"] == 2
    assert [p["name"] for p in client.get("/api/persons").json() if p["anonymous"]] == ["Voice 2", "Voice 3"]

    two = _speakers(client, TWO)["S2"]
    assert (two["status"], two["person_name"]) == ("auto", "Alpha Person")
    assert float(str(two["score"])) >= 0.70


def test_not_this_person_founds_its_own_voice_until_named(client: TestClient) -> None:
    pid = next(p["id"] for p in client.get("/api/persons").json() if p["name"] == "Alpha Person")
    assert client.post(f"/api/events/{TWO}/speakers/S2/rejections", json={"person_id": pid}).status_code == 204
    two = _speakers(client, TWO)["S2"]
    assert (two["status"], two["person_anonymous"], two["rejected"]) == ("new", True, [pid])
    candidates = two["candidates"]
    assert isinstance(candidates, list)
    assert all(c["person_id"] != pid for c in candidates)

    assert client.put(f"/api/events/{TWO}/speakers/S2/person", json={"person_id": pid}).status_code == 204
    two = _speakers(client, TWO)["S2"]
    assert (two["status"], two["person_name"], two["rejected"]) == ("confirmed", "Alpha Person", [])
    assert [p["name"] for p in client.get("/api/persons").json() if p["anonymous"]] == ["Voice 2", "Voice 3"]


def test_forgetting_sticks(client: TestClient) -> None:
    pid = next(p["id"] for p in client.get("/api/persons").json() if p["name"] == "Alpha Person")
    assert client.delete(f"/api/persons/{pid}").status_code == 204
    assert [p["name"] for p in client.get("/api/persons").json()] == ["Voice 2", "Voice 3"]
    client.post("/api/sync")
    for event in (ONE, TWO):
        forgotten = next(s for s in _speakers(client, event).values() if s["no_profile"])
        assert (forgotten["status"], forgotten["person_id"]) == ("unknown", None)  # no new profile grows back


def test_errors_have_one_shape(client: TestClient) -> None:
    client.post("/api/persons", json={"name": "Twice"})
    duplicate = client.post("/api/persons", json={"name": "Twice"})
    assert duplicate.status_code == 409
    assert _error(duplicate)["code"] == "conflict"

    blank = client.post("/api/persons", json={"name": "   "})
    assert blank.status_code == 422
    details = _error(blank)["details"]
    assert isinstance(details, list)
    assert details[0]["field"] == "name"

    missing = client.get("/api/events/nope/speakers")
    assert missing.status_code == 404
    assert _error(missing)["code"] == "not_found"
    assert "events" not in str(_error(missing)["message"])  # no server paths in messages

    assert _error(client.get("/api/nothing-here"))["code"] == "not_found"
    assert client.put(f"/api/events/{ONE}/ratings/no-such-variant", json={}).status_code == 404
    assert client.put(f"/api/events/{ONE}/ratings/{VARIANT}", json={"accuracy": 7}).status_code == 422


def test_ratings_and_flags(client: TestClient) -> None:
    rated = client.put(f"/api/events/{ONE}/ratings/{VARIANT}", json={"accuracy": 4, "note": "fine"})
    assert rated.status_code == 200
    assert (rated.json()["accuracy"], rated.json()["names_numbers"]) == (4, None)

    flag = client.post(f"/api/events/{ONE}/flags", json={"variant": VARIANT, "at_ms": 8000, "kind": "name_number"})
    assert flag.status_code == 201
    listed = client.get(f"/api/events/{ONE}/flags", params={"variant": VARIANT}).json()
    assert [f["kind"] for f in listed] == ["name_number"]
    assert client.delete(f"/api/events/{ONE}/flags/{flag.json()['id']}").status_code == 204
    assert client.get(f"/api/events/{ONE}/flags", params={"variant": VARIANT}).json() == []
    assert (
        client.post(f"/api/events/{ONE}/flags", json={"variant": VARIANT, "at_ms": 0, "kind": "bad"}).status_code == 422
    )


def test_voice_map_places_every_speaker(client: TestClient) -> None:
    points = client.get("/api/voices").json()
    assert len(points) == 5
    assert all(-1.0 <= p["x"] <= 1.0 and -1.0 <= p["y"] <= 1.0 for p in points)
    one_s1 = next(p for p in points if p["event_id"] == ONE and p["label"] == "S1")
    assert (one_s1["nearest"][0]["event_id"], one_s1["nearest"][0]["label"]) == (TWO, "S2")


def test_live_guards(client: TestClient, tmp_path_factory: pytest.TempPathFactory) -> None:
    assert client.get("/api/live").json() is None
    assert client.get("/api/live/sources").json() == []
    bad = client.post("/api/live", json={"source": "C:/Windows/notepad.exe"})
    assert bad.status_code == 422
    assert _error(bad)["code"] == "invalid"  # only files from data/videos or a stream address
    assert client.post("/api/live/stop").status_code == 409
    assert client.get("/api/live/media").status_code == 404
