"""The review API end to end on a throwaway database (lektyra_test) and synthetic voices: naming teaches a voice,
other videos are matched again, "not this person" sticks, a voice merges into a person, pictures, forgetting
deletes, and every error has one shape. No real audio, voice or face is used (ADR-005). Needs the local Postgres:
`docker compose up -d`. Pictures go to an object store in memory; Wikidata answers are canned."""

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import numpy as np
import psycopg
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from lektyra.adapters.knowledge.wikimedia import Wikimedia
from lektyra.adapters.store.postgres import VOICE_LOCK, Store, ensure_database, with_database
from lektyra.adapters.web.api import create_app
from lektyra.app.live import LiveManager
from lektyra.app.photos import Photos
from lektyra.app.review import Person, Review
from lektyra.app.schedule import Scheduler
from lektyra.app.uploads import Uploads
from lektyra.settings import Settings, load_settings
from tests.fakes import MemoryObjects

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[2]
DIM = 16
ONE, TWO, THREE = "2026-01-01_10-00-00_one", "2026-01-02_10-00-00_two", "2026-01-03_10-00-00_three"
VARIANT = "elevenlabs__scribe-v2@sk"
OBJECTS = MemoryObjects()
EVENTS_DIR: list[Path] = []  # the fixture's events folder, for tests that write files a run would write
VIDEOS = MemoryObjects()
COMMONS_PAGE = "https://commons.wikimedia.org/wiki/File:Delta_Person.jpg"


def _picture(color: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    out = BytesIO()
    Image.new("RGB", (900, 1200), color).save(out, "PNG")
    return out.getvalue()


def _wikimedia(url: str) -> bytes:
    """Wikidata says Q4242 has a picture on Commons; Commons gives its licence, author and a thumbnail."""
    if "action=wbgetentities" in url:
        p18 = [{"mainsnak": {"datavalue": {"value": "Delta Person.jpg"}}}]
        return json.dumps({"entities": {"Q4242": {"id": "Q4242", "claims": {"P18": p18}}}}).encode()
    if url.startswith("https://commons.wikimedia.org/w/api.php"):
        info = {
            "url": "https://upload.example.test/delta.jpg",
            "thumburl": "https://upload.example.test/640px-delta.jpg",
            "descriptionurl": COMMONS_PAGE,
            "extmetadata": {"LicenseShortName": {"value": "CC BY 4.0"}, "Artist": {"value": "Jane Doe"}},
        }
        return json.dumps({"query": {"pages": {"1": {"title": "File:Delta Person.jpg", "imageinfo": [info]}}}}).encode()
    if url == "https://upload.example.test/640px-delta.jpg":
        return _picture((0, 90, 200))
    raise AssertionError(f"unexpected request {url}")


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
    (folder / "audio.flac").write_bytes(b"")  # clips only need it to exist; nothing is played in tests


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
    EVENTS_DIR.append(events)
    data = events.parent
    photos = Photos(store, OBJECTS, "test", Wikimedia(_wikimedia))
    review = Review(store, events, "test", photos)

    def no_embedder() -> tuple[Callable[[list[np.ndarray]], np.ndarray], str]:
        raise AssertionError("no live session runs in these tests")

    uploads = Uploads(store, VIDEOS, data / "cache" / "uploads", "test")
    live = LiveManager(Settings(data_dir=data), store, review, no_embedder, resolve_upload=uploads.local)
    schedule = Scheduler(store, live, "test")  # its clock thread is not started: runs here are in the future
    with TestClient(create_app(review, live, photos, uploads, schedule, None)) as test_client:
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


def _person(client: TestClient, name: str) -> Person:
    return next(Person.model_validate(p) for p in client.get("/api/persons").json() if p["name"] == name)


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


def test_naming_a_speaker_only_matched_to_a_voice_moves_it_alone(client: TestClient) -> None:
    # TWO/S1 was matched (auto) to Voice 2, which ONE/S2 founded. Naming TWO/S1 must not rename Voice 2.
    assert _speakers(client, TWO)["S1"]["status"] == "auto"
    beta = client.post("/api/persons", json={"name": "Beta Person"}).json()
    assert client.put(f"/api/events/{TWO}/speakers/S1/person", json={"person_id": beta["id"]}).status_code == 204
    assert (_speakers(client, TWO)["S1"]["status"], _speakers(client, TWO)["S1"]["person_name"]) == (
        "confirmed",
        "Beta Person",
    )
    founder = _speakers(client, ONE)["S2"]
    assert (founder["status"], founder["person_name"], founder["person_anonymous"]) == ("new", "Voice 2", True)
    assert client.delete(f"/api/persons/{beta['id']}").status_code == 204


def test_a_voice_can_be_heard_from_its_clearest_passages_in_every_video(client: TestClient) -> None:
    one = client.get(f"/api/events/{ONE}/speakers/S1/clips").json()
    assert [(c["label"], c["start_ms"], c["end_ms"]) for c in one] == [
        ("S1", 400, 12_400)
    ]  # 40 s turn, trimmed, capped
    voice_1 = next(p for p in client.get("/api/persons").json() if p["number"] == 1)
    reel = client.get(f"/api/persons/{voice_1['id']}/clips").json()
    assert [(c["event_id"], c["label"]) for c in reel] == [(TWO, "S2"), (ONE, "S1")]  # newest video first
    assert client.get("/api/persons/999999/clips").status_code == 404


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


def test_a_body_that_is_not_utf8_is_the_senders_error_not_the_servers(client: TestClient) -> None:
    # 2026-11-14: a Windows shell sent "Š" as cp1250 (0x8a); the server answered 500 "something went wrong".
    answer = client.post(
        "/api/persons", content=b'{"name": "\x8avevulova"}', headers={"content-type": "application/json"}
    )
    assert answer.status_code == 422
    assert _error(answer)["code"] == "invalid"


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


def test_live_guards(client: TestClient) -> None:
    assert client.get("/api/live/sessions").json() == []
    for source in ("C:/Windows/notepad.exe", "stvr:3"):
        bad = client.post("/api/live", json={"source": source})
        assert bad.status_code == 422
        assert _error(bad)["code"] == "invalid"  # a live channel, an address, PC sound or an upload; never a path
    assert client.post("/api/live/nope/stop").status_code == 404
    assert client.get("/api/live/nope/media").status_code == 404


def _when(hours: float) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def test_a_video_is_uploaded_to_play_as_live_and_deleted_on_demand(client: TestClient) -> None:
    body = b"\x00\x00\x00\x18ftypmp42" + b"0" * 100
    answer = client.put("/api/uploads", params={"name": "../Hlina vs Takáč.mp4"}, content=body)
    assert answer.status_code == 201
    upload = answer.json()
    assert (upload["name"], upload["kind"], upload["size"]) == ("Hlina vs Takáč.mp4", "video", len(body))
    assert VIDEOS.keys("videos/") == [f"videos/{upload['id']}/Hlina vs Takáč.mp4"]
    assert [u["id"] for u in client.get("/api/uploads").json()] == [upload["id"]]
    source = f"upload:{upload['id']}"
    run = client.post(
        "/api/schedule", json={"source": source, "title": "Replay", "starts_at": _when(1), "ends_at": _when(2)}
    ).json()
    kept = client.delete(f"/api/uploads/{upload['id']}")
    assert (kept.status_code, _error(kept)["code"]) == (409, "conflict")  # a scheduled run needs it
    assert client.post(f"/api/schedule/{run['id']}/cancel").json()["status"] == "cancelled"
    assert client.delete(f"/api/uploads/{upload['id']}").status_code == 204
    assert (VIDEOS.keys("videos/"), client.get("/api/uploads").json()) == ([], [])


def test_only_playable_files_are_uploaded(client: TestClient) -> None:
    for name, body in (("notes.pdf", b"%PDF"), ("empty.mp4", b"")):
        answer = client.put("/api/uploads", params={"name": name}, content=body)
        assert (answer.status_code, _error(answer)["code"]) == (422, "invalid")
    assert VIDEOS.keys("videos/") == []


def test_runs_are_scheduled_listed_and_cancelled(client: TestClient) -> None:
    run = {"source": "ta3:live", "title": "V politike", "starts_at": _when(1), "ends_at": _when(2)}
    made = client.post("/api/schedule", json=run)
    assert made.status_code == 201
    assert (made.json()["status"], made.json()["session_id"]) == ("scheduled", None)
    assert made.json()["id"] in [r["id"] for r in client.get("/api/schedule").json()]
    for wrong in (
        {**run, "ends_at": _when(0.5)},  # ends before it starts
        {**run, "starts_at": _when(-3), "ends_at": _when(-2)},  # over already
        {**run, "ends_at": _when(8)},  # longer than 6 hours
        {**run, "source": "C:/Windows/notepad.exe"},
    ):
        answer = client.post("/api/schedule", json=wrong)
        assert (answer.status_code, _error(answer)["code"]) == (422, "invalid")
    assert client.post(f"/api/schedule/{made.json()['id']}/cancel").json()["status"] == "cancelled"
    again = client.post(f"/api/schedule/{made.json()['id']}/cancel")
    assert (again.status_code, _error(again)["code"]) == (409, "conflict")


def test_voices_are_written_by_one_process_at_a_time(client: TestClient) -> None:
    url = with_database(load_settings().database_url, "lektyra_test")
    first = Store(url)
    with psycopg.connect(url, autocommit=True) as other:  # stands in for a second `lektyra ui`
        with first.exclusive(), first.exclusive():  # re-entrant within one process
            assert other.execute("SELECT pg_try_advisory_lock(%s)", (VOICE_LOCK,)).fetchone() == (False,)
        assert other.execute("SELECT pg_try_advisory_lock(%s)", (VOICE_LOCK,)).fetchone() == (True,)
        other.execute("SELECT pg_advisory_unlock(%s)", (VOICE_LOCK,))
    first.close()


def test_an_unnamed_voice_merges_into_a_named_person_in_every_video(client: TestClient) -> None:
    voice = _person(client, "Voice 3")
    gamma = client.post("/api/persons", json={"name": "Gamma Person", "kind": "politician"}).json()
    assert gamma["number"] > voice.number
    answer = client.post(f"/api/persons/{voice.id}/merge", json={"into": gamma["id"]})
    assert answer.status_code == 200
    merged = Person.model_validate(answer.json())
    assert (merged.id, merged.name, merged.number, merged.anonymous, merged.events) == (
        gamma["id"],
        "Gamma Person",
        voice.number,  # the older number stays
        False,
        1,
    )
    assert merged.samples > 0
    founder = _speakers(client, THREE)["S1"]
    assert (founder["status"], founder["person_name"]) == ("confirmed", "Gamma Person")  # Martin's word, not a guess
    assert "Voice 3" not in {p["name"] for p in client.get("/api/persons").json()}


def test_only_an_unnamed_voice_merges_and_only_into_a_named_person(client: TestClient) -> None:
    voice, gamma = _person(client, "Voice 2"), _person(client, "Gamma Person")
    for source, into, status in ((voice.id, voice.id, 409), (gamma.id, voice.id, 409), (voice.id, 999_999, 404)):
        answer = client.post(f"/api/persons/{source}/merge", json={"into": into})
        assert answer.status_code == status
        assert _error(answer)["code"] == ("conflict" if status == 409 else "not_found")
    assert _person(client, "Voice 2").samples == voice.samples  # nothing moved


def test_a_named_person_gets_a_picture_lektyra_made_itself(client: TestClient) -> None:
    gamma = _person(client, "Gamma Person")
    url = f"/api/persons/{gamma.id}/photo"
    first = client.put(url, content=_picture(), headers={"content-type": "image/png"})
    assert first.status_code == 200
    photo = first.json()["photo"]
    assert (photo["source_url"], photo["license"], len(photo["version"])) == (None, None, 16)
    served = client.get(f"{url}?v={photo['version']}")
    assert (served.headers["content-type"], served.headers["x-content-type-options"]) == ("image/webp", "nosniff")
    assert Image.open(BytesIO(served.content)).size == (384, 512)
    second = client.put(url, content=_picture((0, 0, 200)), headers={"content-type": "image/png"}).json()["photo"]
    assert second["version"] != photo["version"]
    assert OBJECTS.keys("persons/") == [f"persons/{gamma.key}/{second['version']}.webp"]  # the old file is gone
    assert client.delete(url).status_code == 204
    assert _person(client, "Gamma Person").photo is None
    assert OBJECTS.keys("persons/") == []
    assert client.get(url).status_code == 404


def test_pictures_refuse_what_is_not_a_picture_or_has_no_name(client: TestClient) -> None:
    voice, gamma = _person(client, "Voice 2"), _person(client, "Gamma Person")
    png = {"content-type": "image/png"}
    for path, body, headers, status in (
        (f"/api/persons/{voice.id}/photo", _picture(), png, 409),  # name the voice first
        (f"/api/persons/{gamma.id}/photo", b"%PDF-1.7", png, 422),
        (f"/api/persons/{gamma.id}/photo", b"hello", {"content-type": "text/plain"}, 422),
        ("/api/persons/999999/photo", _picture(), png, 404),
    ):
        answer = client.put(path, content=body, headers=headers)
        assert answer.status_code == status
        assert _error(answer)["code"] in ("conflict", "invalid", "not_found")
    assert OBJECTS.keys("persons/") == []


def test_a_picture_from_wikidata_keeps_its_licence_and_author(client: TestClient) -> None:
    delta = client.post("/api/persons", json={"name": "Delta Person", "external_ref": "Q4242"}).json()
    answer = client.post(f"/api/persons/{delta['id']}/photo/wikidata")
    assert answer.status_code == 200
    photo = answer.json()["photo"]
    assert (photo["license"], photo["author"], photo["source_url"]) == ("CC BY 4.0", "Jane Doe", COMMONS_PAGE)
    no_link = client.post(f"/api/persons/{_person(client, 'Gamma Person').id}/photo/wikidata")
    assert (no_link.status_code, _error(no_link)["code"]) == (422, "invalid")


def test_forgetting_a_person_deletes_their_picture(client: TestClient) -> None:
    delta = _person(client, "Delta Person")
    assert len(OBJECTS.keys("persons/")) == 1
    assert client.delete(f"/api/persons/{delta.id}").status_code == 204
    assert OBJECTS.keys("persons/") == []  # the file in the picture store
    with psycopg.connect(with_database(load_settings().database_url, "lektyra_test")) as db:
        assert db.execute("SELECT count(*) FROM person_photo").fetchone() == (0,)  # and its row


def test_renaming_a_voice_in_the_form_names_the_speaker_it_was_first_heard_in(client: TestClient) -> None:
    # 2026-11-14: Voice 7 renamed "Zuzana Števulová" in the form; its first speaker still showed "Unknown voice".
    voice = _person(client, "Voice 2")
    founder = next(s for s in _speakers(client, ONE).values() if s["person_id"] == voice.id)
    assert founder["status"] == "new"
    renamed = client.put(f"/api/persons/{voice.id}", json={"name": "Epsilon Person", "kind": "politician"})
    assert renamed.status_code == 200
    assert (renamed.json()["anonymous"], renamed.json()["number"]) == (False, voice.number)
    after = _speakers(client, ONE)[str(founder["label"])]
    assert (after["status"], after["person_name"]) == ("confirmed", "Epsilon Person")


def test_a_speaker_can_be_several_known_people_at_once_a_label_never_a_voice(client: TestClient) -> None:
    # ADR-017 (Martin: "it will be only a label right? we wont merge those mixed up voices into both profiles"):
    # THREE/S1 is named Gamma; marking it as Gamma + Epsilon takes its samples back and adds none to anyone.
    gamma, epsilon = _person(client, "Gamma Person"), _person(client, "Epsilon Person")
    assert gamma.samples > 0
    url = f"/api/events/{THREE}/speakers/S1/overlap"
    assert client.put(url, json={"person_ids": [gamma.id, epsilon.id]}).status_code == 204
    speaker = _speakers(client, THREE)["S1"]
    assert (speaker["status"], speaker["person_id"]) == ("overlap", None)
    assert speaker["overlap"] == [
        {"person_id": epsilon.id, "name": "Epsilon Person"},
        {"person_id": gamma.id, "name": "Gamma Person"},
    ]
    assert _person(client, "Gamma Person").samples == 0  # the crosstalk no longer teaches Gamma's voice
    assert _person(client, "Epsilon Person").samples == epsilon.samples  # and teaches nobody else
    client.post("/api/sync")
    assert _speakers(client, THREE)["S1"]["status"] == "overlap"  # matching leaves it alone
    for body, status in (({"person_ids": [gamma.id]}, 422), ({"person_ids": [gamma.id, 999_999]}, 404)):
        answer = client.put(url, json=body)
        assert answer.status_code == status
    assert client.delete(url).status_code == 204
    assert _speakers(client, THREE)["S1"]["status"] in ("new", "auto", "unknown")  # an ordinary speaker again
    again = client.delete(url)
    assert (again.status_code, _error(again)["code"]) == (409, "conflict")


def _claim(claim_id: str, at_ms: int) -> dict[str, object]:
    return {
        "id": claim_id, "speaker": "S1", "at_ms": at_ms, "quote": "vláda dala 416 tisíc eur",
        "lekton": "Vláda uzavrela zmluvu za 416 000 eur.", "kind": "money", "entities": ["vláda"],
        "numbers": ["416 000 €"], "sources": ["crz"], "worth": 0.8, "status": "open", "links": [],
        "history": ["m2 add"],
    }  # fmt: skip


def test_claims_of_a_video_live_then_after_the_end_pass(client: TestClient) -> None:
    folder = EVENTS_DIR[0] / ONE
    url = f"/api/events/{ONE}/claims"
    assert client.get(url).json() == {"model": None, "stage": "none", "minutes": 0, "claims": [], "hidden_host": 0}
    live = {"ledger": {"claims": [_claim("c1", 61_000)], "minute": 3, "next_id": 2, "rejected": []}, "minutes": []}
    (folder / "claims-google__gemini-3.5-flash.json").write_text(json.dumps(live), encoding="utf-8")
    seen = client.get(url).json()
    assert (seen["model"], seen["stage"], seen["minutes"]) == ("google/gemini-3.5-flash", "live", 3)
    assert [(c["id"], c["numbers"], c["sources"]) for c in seen["claims"]] == [("c1", ["416 000 €"], ["crz"])]
    final = {"ledger": {"claims": [_claim("c1", 61_000), _claim("c2", 5_000)], "minute": 4, "next_id": 3}}
    (folder / "claims-google__gemini-3.5-flash-final.json").write_text(json.dumps(final), encoding="utf-8")
    after = client.get(url).json()
    assert (after["stage"], [c["id"] for c in after["claims"]]) == ("final", ["c2", "c1"])  # by time


def test_claims_said_by_a_host_are_left_out(client: TestClient) -> None:
    # K60 (Martin: "if we already recognise the host it will be easy to skip host claims"): ONE/S2 is Epsilon;
    # once Epsilon is a host, the claims of S2 leave the view; the ledger keeps them (ids stay as answers know them).
    host = next(s for s in _speakers(client, ONE).values() if s["person_name"] == "Epsilon Person")
    claims = [_claim("c1", 1_000), {**_claim("c2", 2_000), "speaker": host["label"]}]
    ledger = {"ledger": {"claims": claims, "minute": 1, "next_id": 3}}
    folder = EVENTS_DIR[0] / ONE
    for name in folder.glob("claims-*.json"):
        name.unlink()
    (folder / "claims-google__gemini-3.5-flash.json").write_text(json.dumps(ledger), encoding="utf-8")
    url = f"/api/events/{ONE}/claims"
    assert ([c["id"] for c in client.get(url).json()["claims"]], client.get(url).json()["hidden_host"]) == (
        ["c1", "c2"],
        0,
    )
    epsilon = _person(client, "Epsilon Person")
    client.put(f"/api/persons/{epsilon.id}", json={"name": "Epsilon Person", "kind": "host"})
    seen = client.get(url).json()
    assert ([c["id"] for c in seen["claims"]], seen["hidden_host"]) == (["c1"], 1)


def test_the_audience_is_left_out_of_claims_like_a_host(client: TestClient) -> None:
    epsilon = _person(client, "Epsilon Person")
    assert (
        client.put(f"/api/persons/{epsilon.id}", json={"name": "Epsilon Person", "kind": "audience"}).status_code == 200
    )
    seen = client.get(f"/api/events/{ONE}/claims").json()
    assert ([c["id"] for c in seen["claims"]], seen["hidden_host"]) == (["c1"], 1)


def test_only_this_pcs_own_pages_reach_the_api(client: TestClient) -> None:
    # review 2026-11-15, point 6: DNS rebinding (another host name) and other sites' pages are refused
    rebinding = client.get("/api/persons", headers={"host": "evil.example"})
    assert (rebinding.status_code, _error(rebinding)["code"]) == (403, "invalid")
    foreign = client.post("/api/sync", headers={"origin": "https://evil.example"})
    assert foreign.status_code == 403
    assert client.post("/api/sync", headers={"origin": "http://127.0.0.1:8765"}).status_code == 200
    assert client.post("/api/sync").status_code == 200  # a tool without a browser sends no Origin
    # the name another computer uses through an SSH tunnel
    tunnel = {"host": "lektyra.localhost:8765", "origin": "http://lektyra.localhost:8765"}
    assert client.get("/api/persons", headers={"host": tunnel["host"]}).status_code == 200
    assert client.post("/api/sync", headers=tunnel).status_code == 200


def test_a_scheduled_time_needs_its_time_zone(client: TestClient) -> None:
    # review 2026-11-15, point 10: a naive time was a server error, now it is the sender's
    run = {
        "source": "ta3:live",
        "title": "V politike",
        "starts_at": "2030-01-06T11:00:00",
        "ends_at": "2030-01-06T12:00:00",
    }
    answer = client.post("/api/schedule", json=run)
    assert (answer.status_code, _error(answer)["code"]) == (422, "invalid")
