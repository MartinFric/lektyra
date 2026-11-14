"""Speech to text through OpenRouter: one adapter for every transcription model there (ADR-002, ADR-003).

`POST /api/v1/audio/transcriptions`, JSON with the audio as base64 (the call HTN's recorder makes), asking for
`verbose_json`, temperature 0, word and segment timestamps, and zero data retention:
- a provider that refuses the timestamp option is asked again without it;
- a model with no zero-retention provider is asked again without ZDR. TA3 is a public broadcast (ADR-005).

What was actually used is recorded with the answer. The raw answer is returned verbatim for saving before parsing,
and `parse` turns any of the shapes engines return into domain types, leniently: fields depend on the provider
OpenRouter picked.
"""

import base64
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, SecretStr

from lektyra.domain.chunking import TimedWord
from lektyra.domain.transcript import Heard, Segment, spoken

ENDPOINT: Final = "https://openrouter.ai/api/v1/audio/transcriptions"
MODELS_URL: Final = "https://openrouter.ai/api/v1/models?output_modalities=transcription"
TIMEOUT_S: Final = 180
RETRIES: Final = 5  # on 429 (rate limit) and 5xx: wait and ask again
BACKOFF_S: Final = (5.0, 15.0, 30.0, 60.0, 60.0)


@dataclass(frozen=True)
class RawAnswer:
    """The answer as it came, and how it was asked for."""

    status: int
    body: str
    wall_ms: int
    zdr: bool
    timestamps_asked: bool
    language: str | None
    response_format: str = "verbose_json"


class _Word(BaseModel):
    model_config = ConfigDict(extra="ignore")
    word: str | None = None
    text: str | None = None
    start: float | None = None
    end: float | None = None


class _Segment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    start: float | None = None
    end: float | None = None
    text: str = ""
    no_speech_prob: float | None = None
    avg_logprob: float | None = None
    words: list[_Word] | None = None


class _Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cost: float | None = None


class _Answer(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str | None = None
    segments: list[_Segment] | None = None
    words: list[_Word] | None = None
    usage: _Usage | None = None
    duration: float | None = None


class _Price(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prompt: str | None = None
    completion: str | None = None


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str | None = None
    pricing: _Price | None = None

    @property
    def usd_per_audio_hour(self) -> float | None:
        """Seconds-priced models (prompt is $ per audio second, completion 0); token-priced ones give None."""
        if self.pricing is None or self.pricing.prompt is None:
            return None
        if self.pricing.completion not in (None, "0"):
            return None
        return float(self.pricing.prompt) * 3600


def _ms(seconds: float | None) -> int:
    return round((seconds or 0.0) * 1000)


def _words(items: list[_Word] | None) -> tuple[TimedWord, ...]:
    out: list[TimedWord] = []
    for w in items or []:
        text = spoken(w.word or w.text or "")
        if text and w.start is not None:
            out.append(TimedWord(text, _ms(w.start), _ms(w.end if w.end is not None else w.start)))
    return tuple(out)


def error_of(body: str) -> str | None:
    """The provider's error message, if the body is an error, shortened to one line."""
    try:
        data: Any = json.loads(body)
    except json.JSONDecodeError:
        return " ".join(body.split())[:300] or "not JSON"
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        message = data["error"].get("message")
        return " ".join(str(message).split())[:300]
    return None


def parse(body: str, piece_ms: int) -> Heard:
    """Any engine's answer → segments in piece time. Raises ValueError for an error or unusable body."""
    problem = error_of(body)
    if problem is not None:
        raise ValueError(problem)
    answer = _Answer.model_validate_json(body)
    all_words = _words(answer.words)
    raw_segments = [(s, _ms(s.start), _ms(s.end if s.end is not None else s.start)) for s in answer.segments or []]
    # Top-level words go to the segment containing their middle, else the nearest one (edges can disagree by ms).
    owned: list[list[TimedWord]] = [[] for _ in raw_segments]
    for w in all_words:
        if not raw_segments:
            break
        mid = (w.start_ms + w.end_ms) / 2
        best = min(
            range(len(raw_segments)),
            key=lambda i: 0 if raw_segments[i][1] <= mid < raw_segments[i][2]
            else min(abs(mid - raw_segments[i][1]), abs(mid - raw_segments[i][2])),
        )  # fmt: skip
        owned[best].append(w)
    segments: list[Segment] = []
    for i, (s, start, end) in enumerate(raw_segments):
        own = _words(s.words) or tuple(owned[i])
        segments.append(Segment(start, end, spoken(s.text), own, s.no_speech_prob, s.avg_logprob))
    if not segments and all_words:
        # Words only: one segment per pause-free run is overkill here; one segment spanning the words will do.
        segments.append(Segment(all_words[0].start_ms, all_words[-1].end_ms, spoken(answer.text or ""), all_words))
    if not segments and answer.text:
        segments.append(Segment(0, piece_ms, spoken(answer.text)))
    if not segments and answer.text is None:
        raise ValueError("the answer had neither segments, words nor text")
    cost = answer.usage.cost if answer.usage else None
    return Heard(
        segments=tuple(segments), text=spoken(answer.text or " ".join(s.text for s in segments)), cost_usd=cost
    )


class OpenRouterTranscriber:
    """A `Transcriber` for any OpenRouter transcription model."""

    def __init__(self, api_key: SecretStr, model: str, language: str | None = None) -> None:
        self._key = api_key
        self.model = model
        self._language = language

    def _post(self, payload: dict[str, Any]) -> tuple[int, str]:
        """One request, retried on a rate limit (429) or a server error (5xx), honouring Retry-After."""
        status, body, retry_after = self._post_once(payload)
        for attempt in range(RETRIES):
            if status != 429 and status < 500:
                break
            time.sleep(retry_after if retry_after is not None else BACKOFF_S[attempt])
            status, body, retry_after = self._post_once(payload)
        return status, body

    def _post_once(self, payload: dict[str, Any]) -> tuple[int, str, float | None]:
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._key.get_secret_value()}",
                "Content-Type": "application/json",
                "X-Title": "lektyra",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                body: bytes = response.read()
                return response.status, body.decode("utf-8", "replace"), None
        except urllib.error.HTTPError as err:
            after = err.headers.get("Retry-After") if err.headers else None
            wait = min(120.0, float(after)) if after and after.replace(".", "", 1).isdigit() else None
            return err.code, err.read().decode("utf-8", "replace"), wait
        except (TimeoutError, urllib.error.URLError) as err:
            return 599, json.dumps({"error": {"message": f"network: {err}"}}), None

    def transcribe(self, audio: bytes, audio_format: str) -> RawAnswer:
        base: dict[str, Any] = {
            "model": self.model,
            "input_audio": {"data": base64.b64encode(audio).decode("ascii"), "format": audio_format},
            "response_format": "verbose_json",
            "temperature": 0,
        }
        if self._language:
            base["language"] = self._language
        started = time.monotonic()
        attempts = [(True, True), (True, False), (False, True), (False, False)]  # (zdr, timestamps)
        status, body, zdr, stamps, fmt = 0, "", True, True, "verbose_json"
        for zdr, stamps in attempts:
            payload = dict(base)
            payload["response_format"] = fmt
            if stamps and fmt == "verbose_json":
                payload["timestamp_granularities"] = ["word", "segment"]
            if zdr:
                payload["provider"] = {"zdr": True}
            status, body = self._post(payload)
            if status == 400 and fmt == "verbose_json" and "response_format" in (error_of(body) or ""):
                fmt = "json"  # some models only answer plain json (text, no times): ask again that way
                payload["response_format"] = fmt
                payload.pop("timestamp_granularities", None)
                status, body = self._post(payload)
            if status == 200:
                break
            if status in (401, 402, 429) or status >= 500:
                break  # a key, credit, rate or server problem (already retried): changing options will not help
        return RawAnswer(
            status=status,
            body=body,
            wall_ms=round((time.monotonic() - started) * 1000),
            zdr=zdr,
            timestamps_asked=stamps and fmt == "verbose_json",
            language=self._language,
            response_format=fmt,
        )


def catalog(api_key: SecretStr | None) -> list[CatalogModel]:
    headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"} if api_key else {}
    request = urllib.request.Request(MODELS_URL, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        data: Any = json.loads(response.read())
    return [CatalogModel.model_validate(m) for m in data.get("data", [])]
