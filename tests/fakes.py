"""Test doubles for ports (ADR-002)."""

from lektyra.errors import LektyraError


class MemoryObjects:
    """An ObjectStore in memory: what MinIO keeps, without MinIO."""

    def __init__(self) -> None:
        self.files: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.files[key] = (data, content_type)

    def get(self, key: str) -> bytes:
        if key not in self.files:
            raise LektyraError("not_found", "This picture is gone.")
        return self.files[key][0]

    def delete(self, key: str) -> None:
        self.files.pop(key, None)

    def keys(self, prefix: str) -> list[str]:
        return sorted(k for k in self.files if k.startswith(prefix))
