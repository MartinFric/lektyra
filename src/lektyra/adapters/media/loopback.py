"""The PC's own sound output as a live source (K28): whatever plays on the speakers or headset, captured through
Windows' WASAPI loopback, as 16 kHz mono PCM (ADR-007).

Use: watch a channel in its official player (Orange TV in the browser) and give lektyra `pc:sound` (the default
output) or `pc:sound:<device name>`. Nothing is decrypted or downloaded: lektyra hears exactly what Martin hears, so
other sounds on the PC (notifications, music) are heard too. Silence still arrives (as zeros), so the stream's
clock keeps running when nothing plays.
"""

from collections.abc import Iterator
from types import TracebackType
from typing import IO, Any, Final, Self

import numpy as np

from lektyra.domain.audio import SAMPLE_BYTES
from lektyra.domain.resample import CAPTURE_RATE, FACTOR, Decimator
from lektyra.ports import SourceInfo

PREFIX: Final = "pc:sound"


def device_of(url: str) -> str | None:
    """`pc:sound` → None (the default output); `pc:sound:<name>` → that output's name."""
    rest = url.removeprefix(PREFIX)
    return rest[1:] if rest.startswith(":") and len(rest) > 1 else None


def output_devices() -> tuple[list[str], str | None]:
    """The sound outputs that can be listened to, and the default one. Empty where capture is not available."""
    try:
        import soundcard
    except Exception:  # not Windows, or no audio stack: the UI simply offers no device
        return [], None
    speakers: list[Any] = list(soundcard.all_speakers())
    default: Any = soundcard.default_speaker()
    return [str(s.name) for s in speakers], str(default.name) if default is not None else None


class LoopbackStream:
    """An `AudioStream` over the loopback recorder. Closing it stops the capture."""

    def __init__(self, device: str | None) -> None:
        import soundcard

        speaker: Any = soundcard.get_speaker(device) if device else soundcard.default_speaker()
        microphone: Any = soundcard.get_microphone(id=str(speaker.name), include_loopback=True)
        self._recorder: Any = microphone.recorder(samplerate=CAPTURE_RATE, channels=2)
        self._recorder.__enter__()
        self._decimator = Decimator()
        self._open = True

    def chunks(self, chunk_bytes: int) -> Iterator[bytes]:
        frames = max(1, chunk_bytes // SAMPLE_BYTES) * FACTOR
        while self._open:
            block = np.asarray(self._recorder.record(numframes=frames), dtype=np.float32)
            yield self._decimator.feed(block).tobytes()

    def close(self) -> None:
        if self._open:
            self._open = False
            self._recorder.__exit__(None, None, None)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()


class LoopbackSource:
    """A `MediaSource` for `pc:sound[:device]`."""

    def resolve(self, url: str) -> SourceInfo:
        if not url.startswith(PREFIX):
            raise RuntimeError(f"not a PC sound address: {url}")
        devices, default = output_devices()
        device = device_of(url)
        if device is not None and device not in devices:
            raise RuntimeError(f"no sound output called {device!r} (found: {', '.join(devices) or 'none'})")
        name = device or default or "default output"
        return SourceInfo(url=url, title=f"PC sound: {name}", is_live=True, media_url=name, resolved_by="loopback")

    def open(self, info: SourceInfo, *, realtime: bool, log: IO[bytes] | None = None) -> LoopbackStream:
        return LoopbackStream(device_of(info.url))
