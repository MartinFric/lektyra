"""Profile pictures, re-encoded by lektyra (ADR-015). Pillow.

Whatever arrives (a file Martin drops in, a Commons thumbnail), what is stored and served is an image lektyra made
itself: the first frame, turned upright by its EXIF orientation, flattened onto white, at most 512 px on its longer
side, WebP, with no metadata (no EXIF, no GPS, no colour profile). Only common photo formats are even opened.
"""

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Final

from PIL import Image, ImageOps, UnidentifiedImageError

from lektyra.errors import LektyraError

MAX_BYTES: Final = 15_000_000
MAX_PIXELS: Final = 50_000_000  # a 7000 x 7000 photo; anything bigger is not a portrait
SIDE: Final = 512
FORMATS: Final = ("JPEG", "PNG", "WEBP", "GIF")
CONTENT_TYPE: Final = "image/webp"
NOT_A_PICTURE: Final = "This is not a picture lektyra can read. Use a JPEG, PNG, WebP or GIF."


@dataclass(frozen=True)
class Picture:
    data: bytes
    width: int
    height: int
    version: str  # the start of its SHA-256: a new picture gets a new URL, so browsers may cache forever

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE


def _flatten(image: Image.Image) -> Image.Image:
    """RGB on white: a transparent PNG must not turn black."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    return image.convert("RGB")


def normalise_picture(raw: bytes) -> Picture:
    if not raw:
        raise LektyraError("invalid", "The file is empty.")
    if len(raw) > MAX_BYTES:
        raise LektyraError("invalid", "The picture is larger than 15 MB. Use a smaller one.")
    try:
        with Image.open(BytesIO(raw), formats=FORMATS) as probe:
            width, height = probe.size
            probe.verify()
        if width * height > MAX_PIXELS:
            raise LektyraError("invalid", "The picture has too many pixels. Use a smaller one.")
        with Image.open(BytesIO(raw), formats=FORMATS) as source:
            source.seek(0)
            upright = ImageOps.exif_transpose(source)
            flat = _flatten(upright)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as err:
        raise LektyraError("invalid", NOT_A_PICTURE) from err
    flat.thumbnail((SIDE, SIDE), Image.Resampling.LANCZOS)
    clean = Image.new("RGB", flat.size)  # a fresh image carries no metadata from the source
    clean.paste(flat)
    out = BytesIO()
    clean.save(out, "WEBP", quality=84, method=6)
    data = out.getvalue()
    return Picture(data=data, width=clean.width, height=clean.height, version=hashlib.sha256(data).hexdigest()[:16])
