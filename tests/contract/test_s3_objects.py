"""lektyra's own MinIO through the S3 adapter (ADR-015). Needs it running (`docker compose up -d`) and its login in
~/.secrets/lektyra-minio.env; skipped otherwise. Uses its own bucket and leaves nothing behind."""

import uuid
from collections.abc import Iterator

import pytest

from lektyra.adapters.objects.s3 import S3Objects
from lektyra.errors import LektyraError
from lektyra.settings import load_settings

pytestmark = pytest.mark.slow


@pytest.fixture
def objects() -> Iterator[S3Objects]:
    settings = load_settings()
    if settings.minio_root_user is None or settings.minio_root_password is None:
        pytest.skip("no login for lektyra's MinIO (~/.secrets/lektyra-minio.env)")
    store = S3Objects(
        settings.minio_url,
        settings.minio_root_user.get_secret_value(),
        settings.minio_root_password.get_secret_value(),
        "lektyra-test",
    )
    try:
        store.keys("")
    except LektyraError:
        pytest.skip("lektyra's MinIO is not running (docker compose up -d)")
    yield store
    for key in store.keys(""):
        store.delete(key)


def test_put_get_list_delete(objects: S3Objects) -> None:
    prefix = f"persons/{uuid.uuid4()}/"
    objects.put(f"{prefix}a.webp", b"RIFF-a", "image/webp")  # makes the bucket on first use
    objects.put(f"{prefix}b.webp", b"RIFF-b", "image/webp")
    assert objects.get(f"{prefix}a.webp") == b"RIFF-a"
    assert objects.keys(prefix) == [f"{prefix}a.webp", f"{prefix}b.webp"]
    objects.delete(f"{prefix}a.webp")
    objects.delete(f"{prefix}a.webp")  # deleting twice is fine
    assert objects.keys(prefix) == [f"{prefix}b.webp"]
    with pytest.raises(LektyraError) as gone:
        objects.get(f"{prefix}a.webp")
    assert gone.value.code == "not_found"


def test_a_store_that_is_down_says_so() -> None:
    down = S3Objects("http://127.0.0.1:9", "x", "y", "lektyra-test")
    with pytest.raises(LektyraError) as unreachable:
        down.keys("")
    assert unreachable.value.code == "unavailable"
