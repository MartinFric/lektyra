"""Videos uploaded to be played as live (ADR-016).

Martin uploads a recording (or `lektyra fetch` downloads one) and starts a session on it: it plays in the Live screen
while lektyra hears it at the same speed. The file lives in lektyra's own MinIO (bucket `lektyra-videos`,
`videos/<id>/<name>`); a working copy sits in `data/cache/uploads/` while it is used and is fetched again when it is
gone. Deleting an upload deletes the row, the object and the copy. Research use only, never published (ADR-005).
"""

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel

from lektyra.adapters.store.postgres import Store, UploadRow
from lektyra.app.live import MEDIA_TYPES, media_type
from lektyra.errors import LektyraError
from lektyra.ports import ObjectStore

PREFIX: Final = "videos/"
MAX_BYTES: Final = 8_000_000_000  # a few hours of 720p
UNSAFE: Final = re.compile(r"[^\w .,()\[\]+-]", re.UNICODE)


class Upload(BaseModel):
    id: str
    name: str
    size: int
    kind: Literal["video", "audio"]
    added_at: datetime


def clean_name(name: str) -> str:
    """The file's own name, safe as an object key and in a header: no folders, no control characters."""
    base = UNSAFE.sub("_", Path(name.replace("\\", "/")).name).strip(" .")
    if not base:
        raise LektyraError("invalid", "The file has no name.")
    if Path(base).suffix.lower() not in MEDIA_TYPES:
        raise LektyraError("invalid", "Upload a video or audio file: MP4, WebM, M4A, MP3, FLAC, WAV or OGG.")
    return base[-160:]


def _upload(row: UploadRow) -> Upload:
    kind: Literal["video", "audio"] = "video" if row.content_type.startswith("video/") else "audio"
    return Upload(id=row.id, name=row.name, size=row.size, kind=kind, added_at=row.added_at)


class Uploads:
    def __init__(self, store: Store, objects: ObjectStore, cache_dir: Path, actor: str) -> None:
        self._store = store
        self._objects = objects
        self._cache = cache_dir
        self._actor = actor

    def list(self) -> list[Upload]:
        return [_upload(r) for r in self._store.uploads()]

    def temp_file(self) -> Path:
        """Where an upload in progress is written; `add` takes it over."""
        self._cache.mkdir(parents=True, exist_ok=True)
        return self._cache / f"{uuid.uuid4().hex}.part"

    def add(self, name: str, file: Path) -> Upload:
        """Keep a finished file as an upload: into MinIO, then the row; the file becomes the working copy."""
        name = clean_name(name)
        size = file.stat().st_size
        if size == 0:
            raise LektyraError("invalid", "The file is empty.")
        if size > MAX_BYTES:
            raise LektyraError("invalid", "The file is larger than 8 GB.")
        upload_id = str(uuid.uuid4())
        key = f"{PREFIX}{upload_id}/{name}"
        content_type = media_type(Path(name))
        self._objects.put_file(key, file, content_type)
        row = UploadRow(
            id=upload_id, name=name, size=size, content_type=content_type, object_key=key, added_at=datetime.now()
        )
        self._store.add_upload(row, self._actor)
        self._cache.mkdir(parents=True, exist_ok=True)
        local = self._local_path(row)
        if file.parent.resolve() == self._cache.resolve():
            file.replace(local)
        else:
            shutil.copyfile(file, local)
        return _upload(self._store.upload(upload_id))

    def _local_path(self, row: UploadRow) -> Path:
        return self._cache / f"{row.id}{Path(row.name).suffix.lower()}"

    def local(self, upload_id: str) -> Path:
        """A local copy to play and to hear, fetched from MinIO when it is not here."""
        row = self._store.upload(upload_id)
        path = self._local_path(row)
        if not path.is_file():
            self._cache.mkdir(parents=True, exist_ok=True)
            part = path.with_suffix(path.suffix + ".part")
            self._objects.get_file(row.object_key, part)
            part.replace(path)
        return path

    def delete(self, upload_id: str) -> None:
        row = self._store.upload(upload_id)
        self._store.delete_upload(upload_id, self._actor)
        self._objects.delete(row.object_key)
        self._local_path(row).unlink(missing_ok=True)
