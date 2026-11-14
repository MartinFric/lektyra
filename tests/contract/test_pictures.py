"""Pictures are re-encoded by lektyra (ADR-015): upright, flattened, at most 512 px, WebP, no metadata. Synthetic
images only."""

from io import BytesIO

import pytest
from PIL import Image

from lektyra.adapters.images.pictures import normalise_picture
from lektyra.errors import LektyraError


def _encode(image: Image.Image, fmt: str, **options: object) -> bytes:
    out = BytesIO()
    image.save(out, fmt, **options)
    return out.getvalue()


def _open(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data))


def test_a_large_portrait_becomes_a_small_webp_with_the_same_shape() -> None:
    picture = normalise_picture(_encode(Image.new("RGB", (900, 1200), (200, 30, 30)), "JPEG"))
    image = _open(picture.data)
    assert (image.format, image.size, picture.width, picture.height) == ("WEBP", (384, 512), 384, 512)
    assert picture.content_type == "image/webp"
    assert len(picture.version) == 16


def test_the_same_picture_gets_the_same_version() -> None:
    raw = _encode(Image.new("RGB", (64, 64), (1, 2, 3)), "PNG")
    assert normalise_picture(raw).version == normalise_picture(raw).version


def test_a_small_picture_is_not_blown_up() -> None:
    assert _open(normalise_picture(_encode(Image.new("RGB", (120, 90)), "PNG")).data).size == (120, 90)


def test_transparency_turns_white_not_black() -> None:
    clear = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    pixel = _open(normalise_picture(_encode(clear, "PNG")).data).convert("RGB").getpixel((20, 20))
    assert isinstance(pixel, tuple)
    assert min(pixel) > 240


def test_a_phone_photo_is_turned_upright_and_loses_its_metadata() -> None:
    sideways = Image.new("RGB", (300, 100), (0, 128, 0))
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90° to view
    exif[0x010F] = "Phone maker"
    image = _open(normalise_picture(_encode(sideways, "JPEG", exif=exif.tobytes())).data)
    assert image.size == (100, 300)
    assert len(image.getexif()) == 0
    assert "icc_profile" not in image.info


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"", "empty"),
        (b"%PDF-1.7 not a picture", "not a picture"),
        (_encode(Image.new("RGB", (10, 10)), "BMP"), "not a picture"),  # only common photo formats are opened
        (_encode(Image.new("1", (8_000, 7_000)), "PNG"), "too many pixels"),
    ],
)
def test_what_is_not_a_usable_picture_is_refused(raw: bytes, message: str) -> None:
    with pytest.raises(LektyraError) as refused:
        normalise_picture(raw)
    assert refused.value.code == "invalid"
    assert message in refused.value.message
