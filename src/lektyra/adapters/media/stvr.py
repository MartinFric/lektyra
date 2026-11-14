"""STVR (Slovak public TV) live channels as an HLS media URL.

yt-dlp has no extractor for stvr.sk. The site's own player asks `https://www.stvr.sk/json/live5f.json?c=<channel>`
and gets the stream address on the livebox CDN, with a short-lived `auth` token. So the address is fetched fresh at
every start and every reconnect, and never saved (`SourceInfo.media_url` is excluded, ADR-005).

Addresses: `stvr:1` (Jednotka), `stvr:2` (Dvojka), or a page under stvr.sk/televizia/live (Jednotka).
"""

import urllib.request
from typing import Final
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from lektyra.ports import SourceInfo

CONFIG: Final = "https://www.stvr.sk/json/live5f.json?c={channel}&b=chrome&p=win&f=0&d=1"
USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
)
CHANNELS: Final = {"1": "STVR Jednotka (live)", "2": "STVR Dvojka (live)"}


class _Source(BaseModel):
    model_config = ConfigDict(extra="ignore")

    src: str
    type: str | None = None


class _Clip(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sources: list[_Source] = []


class _Config(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clip: _Clip


def hls_source(config_json: str) -> str | None:
    """The HLS address in the player's config, or None."""
    config = _Config.model_validate_json(config_json)
    return next((s.src for s in config.clip.sources if ".m3u8" in s.src.split("?", 1)[0]), None)


def channel_of(url: str) -> str | None:
    if url.startswith("stvr:"):
        channel = url.removeprefix("stvr:")
        return channel if channel in CHANNELS else None
    host = urlparse(url).hostname or ""
    if (host == "stvr.sk" or host.endswith(".stvr.sk")) and "/televizia/live" in url:
        return "2" if "dvojka" in url.lower() else "1"
    return None


def _get(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Referer": "https://www.stvr.sk/televizia/live"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body: bytes = response.read()
    return body.decode("utf-8-sig", "replace")


class StvrResolver:
    """A site resolver for `FfmpegYtdlpSource`: an STVR live channel → its HLS address, fetched fresh."""

    def matches(self, url: str) -> bool:
        return channel_of(url) is not None

    def resolve(self, url: str) -> SourceInfo:
        channel = channel_of(url)
        if channel is None:
            raise RuntimeError(f"STVR: not a live channel address: {url} (use stvr:1 or stvr:2)")
        media_url = hls_source(_get(CONFIG.format(channel=channel)))
        if media_url is None:
            raise RuntimeError(f"STVR: no live stream for channel {channel} right now")
        return SourceInfo(
            url=url, title=CHANNELS[channel], is_live=True, media_url=media_url, resolved_by="stvr", source_id=channel
        )
