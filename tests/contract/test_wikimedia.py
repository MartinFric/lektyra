"""Wikidata and Commons answers parsed (ADR-015), on synthetic answers shaped like the real APIs'. No network."""

import json
from urllib.parse import parse_qs, urlparse

import pytest

from lektyra.adapters.knowledge.wikimedia import Wikimedia, retry_after
from lektyra.errors import LektyraError


def _item(qid: str, label: str, description: str, human: bool, image: str | None) -> dict[str, object]:
    claims: dict[str, object] = {
        "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5" if human else "Q4167410"}}}}]
    }
    if image:
        claims["P18"] = [{"mainsnak": {"datavalue": {"value": image, "type": "string"}}}]
    return {
        "id": qid,
        "labels": {"sk": {"language": "sk", "value": label}},
        "descriptions": {"en": {"language": "en", "value": description}},
        "claims": claims,
    }


ITEMS = {
    "Q1": _item("Q1", "Ján Testovací (rozlišovacia stránka)", "Wikimedia disambiguation page", False, None),
    "Q2": _item("Q2", "Ján Testovací", "Slovak politician", True, "Jan Testovaci 2024.jpg"),
    "Q3": _item("Q3", "Ján Testovací", "Slovak footballer", True, None),
}
COMMONS = {
    "batchcomplete": "",
    "query": {
        "pages": {
            "-1": {"title": "File:Jan Testovaci 2024.jpg", "missing": "", "known": ""},
            "77": {
                "title": "File:Jan Testovaci 2024.jpg",
                "imageinfo": [
                    {
                        "url": "https://upload.example.test/full.jpg",
                        "thumburl": "https://upload.example.test/640px.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Jan_Testovaci_2024.jpg",
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC BY-SA 4.0", "source": "commons-desc-page"},
                            "Artist": {
                                "value": '<a href="//commons.wikimedia.org/wiki/User:X">Jana&nbsp;Fotografka</a>'
                            },
                            "DateTime": {"value": 20240101},
                        },
                    }
                ],
            },
        }
    },
}


def fake(url: str) -> bytes:
    query = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    if query.get("action") == "wbsearchentities":
        return json.dumps({"search": [{"id": "Q1"}, {"id": "Q2"}, {"id": "Q3"}, {"id": "Q404"}]}).encode()
    if query.get("action") == "wbgetentities":
        ids = query["ids"].split("|")
        found = {i: ITEMS.get(i, {"id": i, "missing": ""}) for i in ids}
        if ids == ["Q9"]:  # a merged item answers under its new id
            found = {"Q2": ITEMS["Q2"]}
        return json.dumps({"entities": found}).encode()
    if url.startswith("https://commons.wikimedia.org/w/api.php"):
        assert query["titles"] == "File:Jan Testovaci 2024.jpg"
        return json.dumps(COMMONS).encode()
    raise AssertionError(f"unexpected request {url}")


def test_search_puts_people_first_and_says_who_has_a_picture() -> None:
    hits = Wikimedia(fake).search("Ján Testovací")
    assert [(h.qid, h.human, h.has_picture, h.description) for h in hits] == [
        ("Q2", True, True, "Slovak politician"),
        ("Q3", True, False, "Slovak footballer"),
        ("Q1", False, False, "Wikimedia disambiguation page"),
    ]


def test_a_picture_comes_with_its_licence_and_author_in_plain_text() -> None:
    found = Wikimedia(fake).picture("Q2")
    assert found is not None
    assert (found.image_url, found.license, found.author) == (
        "https://upload.example.test/640px.jpg",
        "CC BY-SA 4.0",
        "Jana Fotografka",
    )
    assert found.page_url == "https://commons.wikimedia.org/wiki/File:Jan_Testovaci_2024.jpg"


def test_a_merged_item_still_finds_its_picture() -> None:
    found = Wikimedia(fake).picture("Q9")
    assert found is not None
    assert found.qid == "Q2"


def test_no_picture_and_no_item_are_different_answers() -> None:
    assert Wikimedia(fake).picture("Q3") is None
    with pytest.raises(LektyraError) as missing:
        Wikimedia(fake).picture("Q404")
    assert missing.value.code == "not_found"


def test_only_wikidata_ids_are_asked_and_odd_answers_are_refused() -> None:
    with pytest.raises(LektyraError) as bad:
        Wikimedia(fake).picture("Robert Fico")
    assert bad.value.code == "invalid"
    with pytest.raises(LektyraError) as odd:
        Wikimedia(lambda _: b"<html>maintenance</html>").search("x")
    assert odd.value.code == "unavailable"


def test_a_busy_server_is_asked_again_as_it_says_but_never_waits_long() -> None:
    assert retry_after("3", 0) == 3.0  # as told
    assert retry_after(None, 0) == 5.0  # not told: 5 s, then 10 s
    assert retry_after("soon", 1) == 10.0
    assert retry_after("3600", 0) == 30.0  # at most half a minute
