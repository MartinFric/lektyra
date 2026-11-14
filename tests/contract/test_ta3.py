"""TA3 address parsing, on synthetic snippets shaped like TA3's pages and Livebox templates (no TA3 content)."""

from lektyra.adapters.media.ta3 import Ta3Resolver, embed_ids, page_title, template_sources, vod_url

PAGE = """
<html><head><title>Hosť a hosť o rozpočte | ta3</title></head><body>
<iframe src="https://www.ta3.com/embed/20991231-t-11111111-2222-3333-4444-555555555555"></iframe>
<a href="https://www.ta3.com/embed/20991231-hw-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee">video</a>
<iframe src="https://www.ta3.com/embed/20991231-t-11111111-2222-3333-4444-555555555555"></iframe>
</body></html>
"""

TEMPLATE = """var LiveboxPlayerSource = (function() { var my = {};
  my.embedurl = [
    {"src" : "//n0.example.livebox/TA3_VOD/_definst_/VideotekaEncoder/smil:{0}_d.smil/playlist.m3u8?auth=x"},
                 {"src" : "//n0.example.livebox/backup/playlist.m3u8"}]
  return my; }());"""


def test_every_embed_once_in_page_order() -> None:
    assert embed_ids(PAGE) == [
        "20991231-t-11111111-2222-3333-4444-555555555555",
        "20991231-hw-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    ]


def test_the_title_drops_the_site_suffix() -> None:
    assert page_title(PAGE) == "Hosť a hosť o rozpočte"


def test_template_sources_get_a_scheme() -> None:
    assert template_sources(TEMPLATE) == [
        "https://n0.example.livebox/TA3_VOD/_definst_/VideotekaEncoder/smil:{0}_d.smil/playlist.m3u8?auth=x",
        "https://n0.example.livebox/backup/playlist.m3u8",
    ]


def test_a_new_id_goes_into_the_encoder_folder() -> None:
    url = vod_url(template_sources(TEMPLATE)[0], "20991231-hw-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert "/VideotekaEncoder/smil:20991231-hw-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee_d.smil/" in url


def test_an_old_upper_case_id_goes_into_the_archive_folder() -> None:
    url = vod_url(template_sources(TEMPLATE)[0], "082EC8A1-C2BD-4AE5-A3B3-A0E897CDE5D9")
    assert "/Videoteka/smil:082EC8A1-C2BD-4AE5-A3B3-A0E897CDE5D9_d.smil/" in url


def test_which_addresses_are_ta3s() -> None:
    r = Ta3Resolver("ffprobe")
    assert r.matches("ta3:live")
    assert r.matches("ta3:nrsr")
    assert r.matches("https://www.ta3.com/clanok/1/x")
    assert not r.matches("https://www.youtube.com/watch?v=x")
    assert not r.matches("https://evil.example/ta3.com/clanok/1")
