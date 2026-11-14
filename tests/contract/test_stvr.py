"""STVR's live config, parsed from a synthetic answer shaped like the site's (no network, no real token)."""

import json

from lektyra.adapters.media.stvr import channel_of, hls_source

CONFIG = json.dumps(
    {
        "clip": {
            "title": "Jednotka",
            "image": "https://www.stvr.sk/media/x.png",
            "sources": [
                {
                    "src": "https://n00.stv.livebox.sk/stv-tv/_definst_/stv1.smil/playlist.m3u8?auth=b64:EXAMPLE",
                    "type": "application/x-mpegurl",
                },
                {
                    "src": "https://n00.stv.livebox.sk/stv-tv/_definst_/stv1.smil/manifest.mpd?auth=b64:EXAMPLE",
                    "type": "application/dash+xml",
                },
            ],
        }
    }
)


def test_the_hls_address_is_taken_not_the_dash_one() -> None:
    assert hls_source(CONFIG) == "https://n00.stv.livebox.sk/stv-tv/_definst_/stv1.smil/playlist.m3u8?auth=b64:EXAMPLE"


def test_no_hls_means_none() -> None:
    assert hls_source(json.dumps({"clip": {"sources": [{"src": "https://x/manifest.mpd"}]}})) is None


def test_addresses_map_to_channels() -> None:
    assert channel_of("stvr:1") == "1"
    assert channel_of("stvr:2") == "2"
    assert channel_of("stvr:9") is None
    assert channel_of("https://www.stvr.sk/televizia/live") == "1"
    assert channel_of("https://www.stvr.sk/televizia/live-dvojka") == "2"
    assert channel_of("https://www.ta3.com/live") is None
