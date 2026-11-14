"""Any source as 16 kHz mono s16le PCM on ffmpeg's stdout (ADR-007), and FLAC writing.

- A site resolver claims what it knows first (TA3: `adapters/media/ta3.py`).
- A local file or a direct media URL (`.m3u8`, `.mp4`, …) goes straight to ffmpeg.
- Anything else (a TV site, YouTube, a page with a player) goes through yt-dlp. yt-dlp's `-J` says what it is (title,
  live or not). For reading, `yt-dlp -o -` is piped into ffmpeg, so yt-dlp handles the site's headers, cookies and
  HLS segments.
- An HLS playlist with several variants (resolutions) is read from its lowest-bitrate variant: the audio is the
  same and the video is not downloaded for nothing.
"""

import json
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import TracebackType
from typing import IO, Final, Protocol, Self

from pydantic import BaseModel, ConfigDict

from lektyra.domain.audio import SAMPLE_RATE
from lektyra.ports import SourceInfo

DOWNLOAD_HEIGHT: Final = 720
DIRECT_SUFFIXES: Final = (
    ".m3u8",
    ".mpd",
    ".mp4",
    ".m4a",
    ".mp3",
    ".aac",
    ".ts",
    ".mkv",
    ".webm",
    ".flac",
    ".wav",
)


class SiteResolver(Protocol):
    """Knows one site's addresses (ta3.com, `ta3:live`, …) and turns them into a media URL."""

    def matches(self, url: str) -> bool: ...

    def resolve(self, url: str) -> SourceInfo: ...


class _ProbeStream(BaseModel):
    model_config = ConfigDict(extra="ignore")

    codec_type: str | None = None
    height: int | None = None


class _ProbeProgram(BaseModel):
    model_config = ConfigDict(extra="ignore")

    program_id: int
    tags: dict[str, str] = {}
    streams: list[_ProbeStream] = []


class _Probe(BaseModel):
    model_config = ConfigDict(extra="ignore")

    programs: list[_ProbeProgram] = []


class _YtdlpInfo(BaseModel):
    """The part of `yt-dlp -J` we use, parsed at the boundary (ADR-001)."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    is_live: bool | None = None
    live_status: str | None = None
    duration: float | None = None
    webpage_url: str | None = None


def _pcm_args(realtime: bool) -> list[str]:
    return ["-hide_banner", "-loglevel", "warning", "-nostdin", *(["-re"] if realtime else [])]


def _network_args(media_url: str) -> list[str]:
    """Retries for network inputs: an HLS segment that fails is fetched again; a plain HTTP stream reconnects."""
    if not media_url.lower().startswith(("http://", "https://")):
        return []
    timeout = ["-rw_timeout", "20000000"]  # 20 s without data counts as a failure, not a hang
    if ".m3u8" in media_url.split("?", 1)[0].lower():
        return [*timeout, "-seg_max_retry", "5"]
    return [
        *timeout,
        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_on_network_error", "1",
        "-reconnect_delay_max", "15",
    ]  # fmt: skip


def _pcm_out() -> list[str]:
    return ["-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"]


class PcmStream:
    """An `AudioStream`: the processes behind it are stopped when the stream is closed or the `with` ends."""

    def __init__(self, processes: list[subprocess.Popen[bytes]], stdout: IO[bytes]) -> None:
        self._processes = processes
        self._stdout = stdout

    def chunks(self, chunk_bytes: int) -> Iterator[bytes]:
        while True:
            data = self._stdout.read(chunk_bytes)
            if not data:
                return
            yield data

    def close(self) -> None:
        for p in reversed(self._processes):
            if p.poll() is None:
                p.terminate()
        for p in self._processes:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()


class FfmpegYtdlpSource:
    """A `MediaSource`."""

    def __init__(self, ffmpeg: str, ffprobe: str, ytdlp: str, resolvers: Sequence[SiteResolver] = ()) -> None:
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._ytdlp = ytdlp
        self._resolvers = tuple(resolvers)

    def resolve(self, url: str) -> SourceInfo:
        for resolver in self._resolvers:
            if resolver.matches(url):
                return resolver.resolve(url)
        path = Path(url)
        if path.exists():
            return SourceInfo(url=url, title=path.stem, is_live=False, media_url=str(path), resolved_by="direct")
        if url.split("?", 1)[0].lower().endswith(DIRECT_SUFFIXES):
            name = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
            live = url.split("?", 1)[0].lower().endswith((".m3u8", ".mpd"))  # a playlist may be live; assume so
            return SourceInfo(url=url, title=name, is_live=live, media_url=url, resolved_by="direct")
        done = subprocess.run(
            [self._ytdlp, "-J", "--no-playlist", "--no-warnings", url],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if done.returncode != 0:
            raise RuntimeError(f"yt-dlp cannot open {url}: {done.stderr.decode('utf-8', 'replace').strip()[-500:]}")
        info = _YtdlpInfo.model_validate(json.loads(done.stdout))
        live = bool(info.is_live) or info.live_status in {"is_live", "is_upcoming"}
        return SourceInfo(
            url=url,
            title=info.title or url,
            is_live=live,
            duration_s=info.duration,
            media_url=info.webpage_url or url,
            resolved_by="yt-dlp",
        )

    def open(self, info: SourceInfo, *, realtime: bool, log: IO[bytes] | None = None) -> PcmStream:
        err = log if log is not None else subprocess.DEVNULL
        if info.resolved_by in ("direct", "ta3"):
            ffmpeg = subprocess.Popen(
                [
                    self._ffmpeg,
                    *_pcm_args(realtime),
                    *_network_args(info.media_url),
                    "-i",
                    info.media_url,
                    *self._audio_map(info.media_url),
                    *_pcm_out(),
                ],
                stdout=subprocess.PIPE,
                stderr=err,
            )
            if ffmpeg.stdout is None:
                raise RuntimeError("ffmpeg gave no stdout")
            return PcmStream([ffmpeg], ffmpeg.stdout)
        ytdlp = subprocess.Popen(
            [
                self._ytdlp,
                "-q",
                "--no-warnings",
                "--no-playlist",
                "-f",
                "bestaudio/best",
                "-o",
                "-",
                info.media_url,
            ],
            stdout=subprocess.PIPE,
            stderr=err,
        )
        if ytdlp.stdout is None:
            raise RuntimeError("yt-dlp gave no stdout")
        ffmpeg = subprocess.Popen(
            [self._ffmpeg, *_pcm_args(realtime), "-i", "pipe:0", *_pcm_out()],
            stdin=ytdlp.stdout,
            stdout=subprocess.PIPE,
            stderr=err,
        )
        ytdlp.stdout.close()  # ffmpeg owns the pipe now; yt-dlp gets SIGPIPE if ffmpeg stops
        if ffmpeg.stdout is None:
            raise RuntimeError("ffmpeg gave no stdout")
        return PcmStream([ytdlp, ffmpeg], ffmpeg.stdout)

    def download(self, info: SourceInfo, out: Path, max_height: int = DOWNLOAD_HEIGHT) -> None:
        """Save the source as a video file to watch next to a live session. HLS: the variant closest to
        `max_height` (enough to see faces and name captions), copied, not re-encoded. Sites: yt-dlp, same cap."""
        out.parent.mkdir(parents=True, exist_ok=True)
        part = out.with_name(out.stem + ".part" + out.suffix)
        if info.resolved_by in ("direct", "ta3"):
            command = [
                self._ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-nostdin", "-y",
                *_network_args(info.media_url), "-i", info.media_url,
                *self._video_map(info.media_url, max_height),
                "-c", "copy", "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart", str(part),
            ]  # fmt: skip
        else:
            command = [
                self._ytdlp, "--no-playlist", "--no-warnings", "-f",
                f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
                "--merge-output-format", "mp4", "-o", str(part), info.media_url,
            ]  # fmt: skip
        done = subprocess.run(command, check=False)
        if done.returncode != 0 or not part.exists():
            raise RuntimeError(f"the download failed (exit {done.returncode})")
        part.replace(out)

    def _video_map(self, media_url: str, max_height: int) -> list[str]:
        """For a multi-variant HLS playlist: video and audio of the variant closest to `max_height` from below."""
        if ".m3u8" not in media_url.split("?", 1)[0].lower():
            return []
        done = subprocess.run(
            [self._ffprobe, "-v", "error", "-show_programs", "-show_streams", "-of", "json", media_url],
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
        if done.returncode != 0:
            return []
        probe = _Probe.model_validate_json(done.stdout or "{}")

        def height(p: _ProbeProgram) -> int:
            return max((s.height or 0 for s in p.streams if s.codec_type == "video"), default=0)

        both = [p for p in probe.programs if height(p) > 0 and any(s.codec_type == "audio" for s in p.streams)]
        if not both:
            return []
        fitting = [p for p in both if height(p) <= max_height]
        chosen = max(fitting, key=height) if fitting else min(both, key=height)
        return ["-map", f"0:p:{chosen.program_id}:v:0", "-map", f"0:p:{chosen.program_id}:a:0"]

    def _audio_map(self, media_url: str) -> list[str]:
        """For a multi-variant HLS playlist: map the audio of its lowest-bitrate variant; else let ffmpeg choose."""
        if ".m3u8" not in media_url.split("?", 1)[0].lower():
            return []
        done = subprocess.run(
            [self._ffprobe, "-v", "error", "-show_programs", "-of", "json", media_url],
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
        if done.returncode != 0:
            return []
        probe = _Probe.model_validate_json(done.stdout or "{}")
        with_audio = [p for p in probe.programs if any(s.codec_type == "audio" for s in p.streams)]
        if not with_audio:
            return []
        lowest = min(with_audio, key=lambda p: int(p.tags.get("variant_bitrate", "0") or "0"))
        return ["-map", f"0:p:{lowest.program_id}:a:0"]


class FlacWriter:
    """Writes PCM to a FLAC file through ffmpeg, as it arrives."""

    def __init__(self, ffmpeg: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._process = subprocess.Popen(
            [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "pipe:0",
                "-c:a", "flac", str(path),
            ],
            stdin=subprocess.PIPE,
        )  # fmt: skip
        if self._process.stdin is None:
            raise RuntimeError("ffmpeg gave no stdin")
        self._stdin = self._process.stdin

    def write(self, pcm: bytes) -> None:
        self._stdin.write(pcm)

    def close(self) -> None:
        self._stdin.close()
        if self._process.wait(timeout=60) != 0:
            raise RuntimeError(f"ffmpeg FLAC encoding failed ({self._process.returncode})")

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()


def write_flac(ffmpeg: str, path: Path, pcm: bytes) -> None:
    with FlacWriter(ffmpeg, path) as writer:
        writer.write(pcm)


def decode_file(ffmpeg: str, path: Path) -> bytes:
    """A local audio file → 16 kHz mono s16le PCM, all of it (for re-analysis of a saved event)."""
    done = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(path), *_pcm_out()],
        capture_output=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"ffmpeg could not decode {path}: {done.stderr.decode('utf-8', 'replace')[-300:]}")
    return done.stdout
