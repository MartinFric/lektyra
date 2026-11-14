"""Wikidata and Wikimedia Commons: which item a name is, and a free picture of that person (ADR-015).

What leaves the PC: a public figure's name (a search) or a Wikidata id, and the download of a Commons picture.
Never a voice, a transcript or anything from `data/`. Commons pictures carry a licence; it is kept with the picture.

The HTTP getter is injected, so parsing is tested on synthetic answers (`tests/contract/test_wikimedia.py`).
"""

import html
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Final
from urllib.parse import urlencode, urlparse

from pydantic import BaseModel, ConfigDict, ValidationError

from lektyra.adapters.images.pictures import MAX_BYTES
from lektyra.errors import LektyraError

API: Final = "https://www.wikidata.org/w/api.php"
COMMONS: Final = "https://commons.wikimedia.org/w/api.php"
USER_AGENT: Final = "lektyra/0.1 (personal research tool)"
QID: Final = re.compile(r"^Q[1-9][0-9]*$")
HUMAN: Final = "Q5"
LANGUAGES: Final = ("sk", "cs", "en")
TAG: Final = re.compile(r"<[^>]+>")
RETRIES: Final = 2

Fetch = Callable[[str], bytes]


def retry_after(header: str | None, attempt: int) -> float:
    """Seconds to wait before asking again: what the server said (Retry-After, in seconds), else 5, 10…; at most
    30, so a person at the screen is never left waiting long."""
    try:
        said = float(header) if header else 0.0
    except ValueError:
        said = 0.0
    return min(30.0, said if said > 0 else 5.0 * (attempt + 1))


def http_get(url: str, attempts: int = RETRIES + 1) -> bytes:
    """GET over https only, at most MAX_BYTES. Wikimedia asks busy clients to slow down (429/503 with Retry-After):
    lektyra waits as told and asks again, a few times, then says so."""
    if not url.startswith("https://"):
        raise LektyraError("invalid", "Only https:// addresses are fetched.")
    host = urlparse(url).hostname or url
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body: bytes = response.read(MAX_BYTES + 1)
            break
        except urllib.error.HTTPError as err:
            if err.code in (429, 503) and attempt + 1 < attempts:
                time.sleep(retry_after(err.headers.get("Retry-After"), attempt))
                continue
            busy = " (too many requests: try again in a minute)" if err.code == 429 else ""
            raise LektyraError("unavailable", f"{host} answered {err.code}{busy}.") from err
        except (urllib.error.URLError, TimeoutError) as err:
            raise LektyraError("unavailable", f"{host} could not be reached.") from err
    if len(body) > MAX_BYTES:
        raise LektyraError("invalid", "The picture is larger than 15 MB.")
    return body


class WikidataHit(BaseModel):
    qid: str
    label: str
    description: str | None
    human: bool
    has_picture: bool


class PictureSource(BaseModel):
    qid: str
    file: str  # the Commons file name
    image_url: str  # a thumbnail to download
    page_url: str  # the Commons file page: licence and author, for anyone who asks
    license: str | None
    author: str | None


# --- what the APIs answer (only the fields used) -----------------------------------------------------------------
class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _ItemId(_Loose):
    id: str


class _DataValue(_Loose):
    value: str | _ItemId | dict[str, Any]


class _Snak(_Loose):
    datavalue: _DataValue | None = None


class _Claim(_Loose):
    mainsnak: _Snak


class _Text(_Loose):
    value: str


class _Entity(_Loose):
    id: str
    missing: str | None = None
    labels: dict[str, _Text] = {}
    descriptions: dict[str, _Text] = {}
    claims: dict[str, list[_Claim]] = {}

    def strings(self, prop: str) -> list[str]:
        values = [c.mainsnak.datavalue.value for c in self.claims.get(prop, []) if c.mainsnak.datavalue]
        return [v for v in values if isinstance(v, str)]

    def items(self, prop: str) -> list[str]:
        values = [c.mainsnak.datavalue.value for c in self.claims.get(prop, []) if c.mainsnak.datavalue]
        return [v.id for v in values if isinstance(v, _ItemId)]

    def text(self, texts: dict[str, _Text], language: str) -> str | None:
        for lang in (language, *LANGUAGES):
            if lang in texts:
                return texts[lang].value
        return next((t.value for t in texts.values()), None)


class _Entities(_Loose):
    entities: dict[str, _Entity] = {}


class _SearchHit(_Loose):
    id: str


class _Search(_Loose):
    search: list[_SearchHit] = []


class _Meta(_Loose):
    value: str | int | float | None = None


class _ImageInfo(_Loose):
    url: str
    descriptionurl: str
    thumburl: str | None = None
    extmetadata: dict[str, _Meta] = {}


class _Page(_Loose):
    title: str
    imageinfo: list[_ImageInfo] = []


class _Query(_Loose):
    pages: dict[str, _Page] = {}


class _Commons(_Loose):
    query: _Query | None = None


def _plain(meta: _Meta | None) -> str | None:
    """Commons metadata is HTML (an author is often a link): plain text, at most 200 characters."""
    if meta is None or meta.value is None:
        return None
    text = " ".join(html.unescape(TAG.sub(" ", str(meta.value))).split())
    return text[:200] or None


class Wikimedia:
    def __init__(self, fetch: Fetch = http_get) -> None:
        self._fetch = fetch

    def _json[M: BaseModel](self, model: type[M], url: str) -> M:
        try:
            return model.model_validate_json(self._fetch(url))
        except ValidationError as err:
            raise LektyraError("unavailable", "Wikimedia answered something lektyra does not understand.") from err

    def _entities(self, ids: list[str]) -> dict[str, _Entity]:
        query = urlencode(
            {
                "action": "wbgetentities",
                "format": "json",
                "ids": "|".join(ids),
                "props": "labels|descriptions|claims",
                "languages": "|".join(LANGUAGES),
            }
        )
        return self._json(_Entities, f"{API}?{query}").entities

    def search(self, name: str, language: str = "sk") -> list[WikidataHit]:
        """Items whose label or alias matches `name`, people first. Which one is meant is for a person to decide."""
        query = urlencode(
            {
                "action": "wbsearchentities",
                "format": "json",
                "type": "item",
                "limit": 8,
                "language": language,
                "uselang": language,
                "search": name,
            }
        )
        ids = [h.id for h in self._json(_Search, f"{API}?{query}").search]
        if not ids:
            return []
        entities = self._entities(ids)
        hits = [
            WikidataHit(
                qid=e.id,
                label=e.text(e.labels, language) or e.id,
                description=e.text(e.descriptions, language),
                human=HUMAN in e.items("P31"),
                has_picture=bool(e.strings("P18")),
            )
            for e in (entities.get(i) for i in ids)
            if e is not None and e.missing is None
        ]
        return sorted(hits, key=lambda h: not h.human)

    def picture(self, qid: str) -> PictureSource | None:
        """The item's image (P18) on Commons, with its licence and author; None when the item has no image."""
        if not QID.match(qid):
            raise LektyraError("invalid", f"{qid!r} is not a Wikidata id (Q123).")
        entities = self._entities([qid])
        entity = entities.get(qid) or (next(iter(entities.values())) if len(entities) == 1 else None)  # a redirect
        if entity is None or entity.missing is not None:
            raise LektyraError("not_found", f"Wikidata has no item {qid}.")
        files = entity.strings("P18")
        if not files:
            return None
        query = urlencode(
            {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": 640,
                "titles": f"File:{files[0]}",
            }
        )
        found = self._json(_Commons, f"{COMMONS}?{query}").query
        info = next((p.imageinfo[0] for p in found.pages.values() if p.imageinfo), None) if found else None
        if info is None:
            return None
        return PictureSource(
            qid=entity.id,
            file=files[0],
            image_url=info.thumburl or info.url,
            page_url=info.descriptionurl,
            license=_plain(info.extmetadata.get("LicenseShortName")),
            author=_plain(info.extmetadata.get("Artist")),
        )

    def download(self, url: str) -> bytes:
        return self._fetch(url)
