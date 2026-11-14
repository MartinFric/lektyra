"""Every database has its own buckets (ADR-015, ADR-016): a test database never sweeps the real pictures."""

from lektyra.app.photos import bucket_name


def test_the_main_database_keeps_the_plain_name() -> None:
    assert bucket_name("lektyra-pictures", None, "lektyra") == "lektyra-pictures"
    assert bucket_name("lektyra-pictures", "lektyra", "lektyra") == "lektyra-pictures"


def test_another_database_gets_its_own_bucket_with_a_valid_name() -> None:
    assert bucket_name("lektyra-pictures", "lektyra_manual", "lektyra") == "lektyra-pictures-lektyra-manual"
    assert bucket_name("lektyra-videos", "Test DB!", "lektyra") == "lektyra-videos-test-db"
    assert len(bucket_name("lektyra-videos", "x" * 100, "lektyra")) <= 63
