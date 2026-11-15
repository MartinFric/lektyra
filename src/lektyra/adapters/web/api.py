"""The local UI's HTTP API (ADR-009). JSON under /api, the built React app everywhere else, 127.0.0.1 only.

Every error leaves in one shape, which the frontend's single API wrapper parses:

    {"error": {"code": "not_found" | "conflict" | "invalid" | "unavailable" | "internal", "message": "…",
               "details": [{"field": "name", "message": "…"}] | null}}

Messages are for Martin and never carry a key, a voice or a stack trace; the trace goes to the terminal.
"""

import logging
import re
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AfterValidator, AwareDatetime, BaseModel, Field, StringConstraints
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from lektyra.adapters.images.pictures import MAX_BYTES
from lektyra.adapters.store.postgres import FlagKind, PersonFields, PersonKind
from lektyra.app.live import UPLOAD_PREFIX, LiveDevices, LiveManager, LiveState
from lektyra.app.photos import Photos
from lektyra.app.review import (
    ClaimsView,
    Clip,
    EventDetail,
    EventSummary,
    Flag,
    Person,
    Rating,
    Review,
    Speaker,
    SyncResult,
    Transcript,
    VoicePoint,
)
from lektyra.app.schedule import Run, Scheduler
from lektyra.app.uploads import MAX_BYTES as MAX_UPLOAD
from lektyra.app.uploads import Upload, Uploads, clean_name
from lektyra.errors import STATUS, Code, LektyraError

log = logging.getLogger("lektyra.api")
WIKIDATA = re.compile(r"^Q[1-9][0-9]*$")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Score = Annotated[int, Field(ge=1, le=5)]


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: Code
    message: str
    details: list[ErrorDetail] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def _knowledge_link(value: str) -> str:
    if value and not (WIKIDATA.match(value) or value.startswith(("https://", "http://"))):
        raise ValueError("Use a Wikidata id (Q123) or a web address (https://…).")
    return value


class PersonIn(BaseModel):
    name: Name
    kind: PersonKind = "other"
    function: Short = ""
    party: Short = ""
    public_figure: bool = True
    note: Long = ""
    external_ref: Annotated[Short, AfterValidator(_knowledge_link)] = ""

    def fields(self) -> PersonFields:
        return PersonFields(
            name=self.name,
            kind=self.kind,
            function=self.function or None,
            party=self.party or None,
            public_figure=self.public_figure,
            note=self.note or None,
            external_ref=self.external_ref or None,
        )


class NameIn(BaseModel):
    person_id: int


class MergeIn(BaseModel):
    into: int


class OverlapIn(BaseModel):
    person_ids: Annotated[list[int], Field(min_length=2, max_length=8)]


class RatingIn(BaseModel):
    accuracy: Score | None = None
    names_numbers: Score | None = None
    note: Long = ""


class FlagIn(BaseModel):
    variant: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    at_ms: Annotated[int, Field(ge=0)]
    kind: FlagKind
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""


class LiveStartIn(BaseModel):
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    title: Short = ""
    transcribe: bool = True


class RunIn(BaseModel):
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    title: Name
    starts_at: AwareDatetime  # with its time zone: "11:00" alone is not a moment
    ends_at: AwareDatetime
    transcribe: bool = True


class TextOut(BaseModel):
    name: str
    text: str


class Health(BaseModel):
    ok: bool


def _error(code: Code, message: str, details: list[ErrorDetail] | None = None) -> JSONResponse:
    body = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(body.model_dump(), status_code=STATUS[code])


def _field(loc: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in loc if part not in ("body", "query", "path"))


def _install_errors(app: FastAPI) -> None:
    async def lektyra_error(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, LektyraError):
            return _error(exc.code, exc.message)
        return await internal_error(_, exc)

    async def validation_error(_: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, RequestValidationError):
            return await internal_error(_, exc)
        details: list[ErrorDetail] = []
        for item in exc.errors():
            loc = item.get("loc", ())
            msg = item.get("msg", "Not valid.")
            details.append(ErrorDetail(field=_field(tuple(loc)), message=str(msg)))
        return _error("invalid", "Some fields are not valid.", details)

    async def http_error(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException) and exc.status_code == 404:
            return _error("not_found", "Nothing here.")
        if isinstance(exc, HTTPException) and exc.status_code == 405:
            return _error("invalid", "This action is not allowed here.")
        if isinstance(exc, HTTPException) and 400 <= exc.status_code < 500:
            # The sender's mistake (e.g. a body that is not UTF-8 JSON), never "something went wrong on the server".
            return _error("invalid", "The request could not be read: send UTF-8 JSON.")
        return await internal_error(_, exc)

    async def database_error(_: Request, exc: Exception) -> JSONResponse:
        log.warning("database unavailable: %s", type(exc).__name__)
        return _error("unavailable", "The database is not reachable. Start it with: docker compose up -d")

    async def internal_error(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled error", exc_info=exc)
        return _error("internal", "Something went wrong on the server. The details are in its terminal.")

    app.add_exception_handler(LektyraError, lektyra_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(psycopg.OperationalError, database_error)
    app.add_exception_handler(Exception, internal_error)


def _router(review: Review, live: LiveManager, photos: Photos, uploads: Uploads, schedule: Scheduler) -> APIRouter:
    api = APIRouter(prefix="/api", responses={400: {"model": ErrorEnvelope}})

    @api.get("/health")
    def health() -> Health:
        return Health(ok=True)

    @api.post("/sync")
    def sync() -> SyncResult:
        return review.sync()

    # persons
    @api.get("/persons")
    def persons() -> list[Person]:
        return review.persons()

    @api.post("/persons", status_code=201)
    def create_person(body: PersonIn) -> Person:
        return review.save_person(None, body.fields())

    @api.put("/persons/{person_id}")
    def update_person(person_id: int, body: PersonIn) -> Person:
        return review.save_person(person_id, body.fields())

    @api.get("/persons/{person_id}/clips")
    def person_clips(person_id: int) -> list[Clip]:
        return review.person_clips(person_id)

    @api.delete("/persons/{person_id}", status_code=204)
    def forget_person(person_id: int) -> Response:
        review.forget_person(person_id)
        return Response(status_code=204)

    @api.post("/persons/{person_id}/merge")
    def merge_person(person_id: int, body: MergeIn) -> Person:
        """An unnamed voice is this named person: the whole voice moves to them (ADR-012)."""
        return review.merge_voice(person_id, body.into)

    # pictures (ADR-015)
    @api.get("/persons/{person_id}/photo")
    def person_photo(person_id: int) -> Response:
        data, content_type = photos.get(person_id)
        # The UI asks for /photo?v=<version>: a new picture is a new address, so this one never changes.
        headers = {"Cache-Control": "private, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"}
        return Response(data, media_type=content_type, headers=headers)

    @api.put("/persons/{person_id}/photo")
    async def upload_photo(person_id: int, request: Request) -> Person:
        """The body is the picture itself (image/jpeg, image/png, image/webp, image/gif)."""
        if not request.headers.get("content-type", "").startswith("image/"):
            raise LektyraError("invalid", "Send the picture itself: a JPEG, PNG, WebP or GIF file.")
        raw = bytearray()
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > MAX_BYTES:
                raise LektyraError("invalid", "The picture is larger than 15 MB. Use a smaller one.")
        saved = await run_in_threadpool(photos.upload, person_id, bytes(raw))
        return Person(**saved.model_dump())

    @api.post("/persons/{person_id}/photo/wikidata")
    def photo_from_wikidata(person_id: int) -> Person:
        """The picture Wikidata has for the person's knowledge link (Q…), with its licence and author."""
        return Person(**photos.from_wikidata(person_id).model_dump())

    @api.delete("/persons/{person_id}/photo", status_code=204)
    def remove_photo(person_id: int) -> Response:
        photos.remove(person_id)
        return Response(status_code=204)

    # videos
    @api.get("/events")
    def events() -> list[EventSummary]:
        return review.events()

    @api.get("/events/{event_id}")
    def event(event_id: str) -> EventDetail:
        return review.event(event_id)

    @api.get("/events/{event_id}/audio", response_class=FileResponse)
    def audio(event_id: str) -> FileResponse:
        return FileResponse(review.audio(event_id), media_type="audio/flac")

    @api.get("/events/{event_id}/documents/{name}")
    def document(event_id: str, name: str) -> TextOut:
        return TextOut(name=name, text=review.document(event_id, name))

    # speakers
    @api.get("/events/{event_id}/speakers")
    def speakers(event_id: str) -> list[Speaker]:
        return review.speakers(event_id)

    @api.get("/events/{event_id}/claims")
    def claims(event_id: str) -> ClaimsView:
        """The claims the claims loop found (live, or after the end pass). Not checked yet."""
        return review.claims(event_id)

    @api.get("/events/{event_id}/speakers/{label}/clips")
    def speaker_clips(event_id: str, label: str) -> list[Clip]:
        return review.speaker_clips(event_id, label)

    @api.put("/events/{event_id}/speakers/{label}/person", status_code=204)
    def name_speaker(event_id: str, label: str, body: NameIn) -> Response:
        review.name_speaker(event_id, label, body.person_id)
        return Response(status_code=204)

    @api.delete("/events/{event_id}/speakers/{label}/person", status_code=204)
    def unname_speaker(event_id: str, label: str) -> Response:
        review.unname_speaker(event_id, label)
        return Response(status_code=204)

    @api.put("/events/{event_id}/speakers/{label}/overlap", status_code=204)
    def mark_overlap(event_id: str, label: str, body: OverlapIn) -> Response:
        """This speaker is several known persons talking at once: a label, never a voice (ADR-017)."""
        review.mark_overlap(event_id, label, body.person_ids)
        return Response(status_code=204)

    @api.delete("/events/{event_id}/speakers/{label}/overlap", status_code=204)
    def clear_overlap(event_id: str, label: str) -> Response:
        review.clear_overlap(event_id, label)
        return Response(status_code=204)

    @api.post("/events/{event_id}/speakers/{label}/rejections", status_code=204)
    def reject(event_id: str, label: str, body: NameIn) -> Response:
        review.reject(event_id, label, body.person_id)
        return Response(status_code=204)

    # transcripts
    @api.get("/events/{event_id}/transcripts/{variant}")
    def transcript(event_id: str, variant: str) -> Transcript:
        return review.transcript(event_id, variant)

    @api.get("/events/{event_id}/ratings")
    def ratings(event_id: str) -> list[Rating]:
        return review.ratings(event_id)

    @api.put("/events/{event_id}/ratings/{variant}")
    def rate(event_id: str, variant: str, body: RatingIn) -> Rating:
        return review.rate(event_id, variant, body.accuracy, body.names_numbers, body.note)

    @api.get("/events/{event_id}/flags")
    def flags(event_id: str, variant: str) -> list[Flag]:
        return review.flags(event_id, variant)

    @api.post("/events/{event_id}/flags", status_code=201)
    def add_flag(event_id: str, body: FlagIn) -> Flag:
        return review.add_flag(event_id, body.variant, body.at_ms, body.kind, body.note)

    @api.delete("/events/{event_id}/flags/{flag_id}", status_code=204)
    def delete_flag(event_id: str, flag_id: int) -> Response:
        review.delete_flag(event_id, flag_id)
        return Response(status_code=204)

    # voices
    @api.get("/voices")
    def voices() -> list[VoicePoint]:
        return review.voices()

    # live sessions (ADR-013, ADR-016: several at once)
    @api.get("/live/sessions")
    def live_sessions() -> list[LiveState]:
        return live.sessions()

    @api.get("/live/devices")
    def live_devices() -> LiveDevices:
        return live.devices()

    @api.post("/live", status_code=201)
    def live_start(body: LiveStartIn) -> LiveState:
        return live.start(body.source, body.title or None, body.transcribe)

    @api.post("/live/{session_id}/stop")
    def live_stop(session_id: str) -> LiveState:
        return live.stop(session_id)

    @api.get("/live/{session_id}/media", response_class=FileResponse)
    def live_media(session_id: str) -> FileResponse:
        path, media_type = live.media(session_id)
        return FileResponse(path, media_type=media_type)

    # videos uploaded to play as live (ADR-016)
    @api.get("/uploads")
    def list_uploads() -> list[Upload]:
        return uploads.list()

    @api.put("/uploads", status_code=201)
    async def upload_video(request: Request, name: str) -> Upload:
        """The body is the file itself; `name` is its file name. Written to disk as it arrives, then to MinIO."""
        clean_name(name)  # refuse an unplayable file before reading gigabytes of it
        part = uploads.temp_file()
        try:
            size = 0
            with part.open("wb") as out:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise LektyraError("invalid", "The file is larger than 8 GB.")
                    out.write(chunk)
            return await run_in_threadpool(uploads.add, name, part)
        finally:
            part.unlink(missing_ok=True)

    @api.delete("/uploads/{upload_id}", status_code=204)
    def delete_upload(upload_id: str) -> Response:
        source = f"{UPLOAD_PREFIX}{upload_id}"
        if live.uses(source):
            raise LektyraError("conflict", "A live session is playing this video. Stop it first.")
        if schedule.uses(source):
            raise LektyraError("conflict", "A scheduled run will play this video. Cancel it first.")
        uploads.delete(upload_id)
        return Response(status_code=204)

    # scheduled live runs (ADR-016)
    @api.get("/schedule")
    def list_runs() -> list[Run]:
        return schedule.runs()

    @api.post("/schedule", status_code=201)
    def add_run(body: RunIn) -> Run:
        return schedule.add(body.source, body.title, body.starts_at, body.ends_at, body.transcribe)

    @api.post("/schedule/{run_id}/cancel")
    def cancel_run(run_id: str) -> Run:
        return schedule.cancel(run_id)

    @api.api_route("/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
    def unknown(rest: str) -> JSONResponse:
        return _error("not_found", f"No API route /api/{rest}.")

    return api


def _spa(app: FastAPI, dist: Path) -> None:
    """The built app: hashed assets cached for good, index.html never (a rebuild shows at once)."""
    index = dist / "index.html"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{rest:path}", include_in_schema=False)
    def spa(rest: str) -> Response:
        candidate = (dist / rest).resolve()
        if rest and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate)
        if not index.is_file():
            return _error("not_found", "The UI is not built yet: run `npm run build` in web/.")
        return FileResponse(index, headers={"Cache-Control": "no-store"})


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
HOSTS = frozenset({"127.0.0.1", "localhost", "testserver"})  # testserver: FastAPI's TestClient


class SameMachine:
    """Only this PC's own pages reach the API (review 2026-11-15, point 6). A request for another host name (DNS
    rebinding: a web page that renames itself to 127.0.0.1) is refused, and so is a change (POST, PUT, DELETE) a page
    of another origin sends: a body-less POST could stop a session or start a paid one. Tools without a browser send
    no Origin and pass. Plain ASGI, so uploads still stream."""

    def __init__(self, app: ASGIApp, origins: frozenset[str]) -> None:
        self._app = app
        self._origins = origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
            host = headers.get("host", "").rsplit(":", 1)[0]
            origin = headers.get("origin")
            foreign = scope["method"] not in SAFE_METHODS and origin is not None and origin not in self._origins
            if host not in HOSTS or foreign:
                refused = _error("invalid", "Only lektyra's own pages on this PC may use this.")
                refused.status_code = 403
                await refused(scope, receive, send)
                return
        await self._app(scope, receive, send)


def own_origins(port: int) -> frozenset[str]:
    """The UI itself, and Vite's dev server while the UI is worked on."""
    return frozenset(f"http://{h}:{p}" for h in ("127.0.0.1", "localhost") for p in (port, 5173))


def create_app(
    review: Review,
    live: LiveManager,
    photos: Photos,
    uploads: Uploads,
    schedule: Scheduler,
    dist: Path | None,
    port: int = 8765,
) -> FastAPI:
    app = FastAPI(title="lektyra", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.add_middleware(SameMachine, origins=own_origins(port))
    _install_errors(app)
    app.include_router(_router(review, live, photos, uploads, schedule))
    if dist is not None:
        _spa(app, dist)
    return app
