"""TA3 (Slovak news TV): its archive and live streams through TA3's own Livebox player (ADR-007).

yt-dlp has no extractor for ta3.com. TA3's player reads public templates from embed.livebox.cz, as any browser
visiting ta3.com does:
- `vod-source.js`: the archive, one HLS playlist per video id, `{0}` replaced by the id;
- `live-source.js`: TA3's live broadcast;
- `nrsr-source.js`: the NR SR (parliament) live stream that TA3 carries.

The templates carry a short-lived signed `auth` token, so they are fetched fresh on every resolve and never stored
(`SourceInfo.media_url` is excluded from what is saved). Used for internal research only (ADR-005).

Accepted inputs: a ta3.com article or embed URL (the longest video on the page is taken: pages often carry a teaser
next to the episode), `ta3:<video id>`, `ta3:live`, `ta3:nrsr`.
"""

import json
import re
import subprocess
import urllib.request
from typing import Final
from urllib.parse import urlparse

from lektyra.ports import SourceInfo

LIVEBOX: Final = "https://embed.livebox.cz/ta3_v2"
USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
)
EMBED_ID: Final = re.compile(r"ta3\.com/embed/([0-9A-Za-z][0-9A-Za-z-]{8,80})")
TEMPLATE_SRC: Final = re.compile(r'"src"\s*:\s*"([^"]+)"')
UUID_UPPER: Final = re.compile(r"^[A-F0-9]{8}(?:-[A-F0-9]{4}){3}-[A-F0-9]{12}")
TITLE: Final = re.compile(r"<title>\s*([^<|]+?)\s*(?:\|[^<]*)?</title>", re.IGNORECASE)
LIVE: Final = {"ta3:live": ("live-source.js", "TA3 live"), "ta3:nrsr": ("nrsr-source.js", "NR SR live (TA3)")}


def embed_ids(html: str) -> list[str]:
    """Video ids of every TA3 embed on a page, in page order, without repeats."""
    seen: list[str] = []
    for found in EMBED_ID.findall(html):
        if found not in seen:
            seen.append(found)
    return seen


def template_sources(js: str) -> list[str]:
    """The `src` URLs of a Livebox source template, scheme added."""
    return [("https:" + s) if s.startswith("//") else s for s in TEMPLATE_SRC.findall(js)]


def vod_url(template: str, video_id: str) -> str:
    url = template.replace("{0}", video_id)
    if UUID_UPPER.match(video_id):  # older archive ids live in another folder, as the player itself does it
        url = url.replace("VideotekaEncoder", "Videoteka")
    return url


def page_title(html: str) -> str | None:
    m = TITLE.search(html)
    return m.group(1).strip() if m else None


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://www.ta3.com/"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body: bytes = response.read()
    return body.decode("utf-8-sig", "replace")


class Ta3Resolver:
    """A site resolver for `FfmpegYtdlpSource`: turns a TA3 address into an HLS media URL."""

    def __init__(self, ffprobe: str) -> None:
        self._ffprobe = ffprobe

    def matches(self, url: str) -> bool:
        if url.startswith("ta3:"):
            return True
        host = urlparse(url).hostname or ""
        return host == "ta3.com" or host.endswith(".ta3.com")

    def resolve(self, url: str) -> SourceInfo:
        if url in LIVE:
            script, live_title = LIVE[url]
            sources = template_sources(_get(f"{LIVEBOX}/{script}"))
            if not sources:
                raise RuntimeError(f"TA3: no stream in {script}")
            return SourceInfo(url=url, title=live_title, is_live=True, media_url=sources[0], resolved_by="ta3")

        title: str | None = None
        if url.startswith("ta3:"):
            ids = [url.removeprefix("ta3:")]
        elif "/embed/" in url:
            ids = [url.rstrip("/").rsplit("/", 1)[-1]]
        else:
            html = _get(url)
            ids, title = embed_ids(html), page_title(html)
        if not ids:
            raise RuntimeError(f"TA3: no video on {url}")

        templates = template_sources(_get(f"{LIVEBOX}/vod-source.js"))
        if not templates:
            raise RuntimeError("TA3: no archive template in vod-source.js")
        candidates = [(self._duration(vod_url(templates[0], i)), i) for i in ids]
        playable = [(d, i) for d, i in candidates if d is not None]
        if not playable:
            raise RuntimeError(f"TA3: none of {len(ids)} video(s) on {url} could be opened")
        duration, video_id = max(playable)
        return SourceInfo(
            url=url,
            title=title or video_id,
            is_live=False,
            duration_s=duration,
            media_url=vod_url(templates[0], video_id),
            resolved_by="ta3",
            source_id=video_id,
        )

    def _duration(self, media_url: str) -> float | None:
        done = subprocess.run(
            [self._ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", media_url],
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
        if done.returncode != 0:
            return None
        try:
            value = json.loads(done.stdout)["format"]["duration"]
            return float(value)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
