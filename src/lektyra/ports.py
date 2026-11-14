"""The ports (ADR-002): what the use cases need from the outside world, as Protocols.

Adapters implement them; the domain never sees them. More ports (Transcriber, Diarizer, Embedder, Repository) are
added with the first adapter that needs them, not before.
"""

from collections.abc import Iterator
from contextlib import AbstractContextManager
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


class SpeechDetector(Protocol):
    """Speech probability per 512-sample frame. Stateful within one stream: call `reset` between streams."""

    def reset(self) -> None: ...

    def probabilities(self, samples: Samples) -> Curve: ...
