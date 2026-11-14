"""The ports (ADR-002): what the use cases need from the outside world, as Protocols.

Adapters implement them; the domain never sees them. More ports (Transcriber, Diarizer, Embedder, Repository) are
added with the first adapter that needs them, not before.
"""

from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import IO, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from lektyra.domain.audio import Curve, Samples


class SourceInfo(BaseModel):
    """What is known about a source before it is read."""

    model_config = ConfigDict(frozen=True)

    url: str
    title: str
    is_live: bool
    duration_s: float | None = None
    # What ffmpeg or yt-dlp opens. It may carry a short-lived token (TA3), so it is never saved (ADR-005).
    media_url: str = Field(exclude=True)
    resolved_by: Literal["yt-dlp", "direct", "ta3", "stvr", "loopback"]
    source_id: str | None = None  # the site's own id of the video, when it has one


class AudioStream(AbstractContextManager["AudioStream"], Protocol):
    """16 kHz mono s16le PCM, in order, until the source ends (ADR-007)."""

    def chunks(self, chunk_bytes: int) -> Iterator[bytes]: ...


class MediaSource(Protocol):
    def resolve(self, url: str) -> SourceInfo: ...

    def open(self, info: SourceInfo, *, realtime: bool, log: IO[bytes] | None = None) -> AudioStream:
        """Start reading. What the decoder says goes to `log` (a file), never to the console."""
        ...


class PcmSink(AbstractContextManager["PcmSink"], Protocol):
    """Where PCM goes: a FLAC file in production, memory in tests."""

    def write(self, pcm: bytes) -> None: ...


class ObjectStore(Protocol):
    """Files kept by key (pictures ADR-015, uploaded videos ADR-016): lektyra's own MinIO in production, memory in
    tests. A store that cannot be reached raises LektyraError("unavailable"); a missing key LektyraError("not_found").
    """

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def put_file(self, key: str, path: Path, content_type: str) -> None:
        """A file too large for memory (a video), sent in parts."""
        ...

    def get_file(self, key: str, path: Path) -> None: ...

    def delete(self, key: str) -> None:
        """Gone afterwards; deleting a missing key is fine."""
        ...

    def keys(self, prefix: str) -> list[str]: ...


class SpeechDetector(Protocol):
    """Speech probability per 512-sample frame. Stateful within one stream: call `reset` between streams."""

    def reset(self) -> None: ...

    def probabilities(self, samples: Samples) -> Curve: ...
