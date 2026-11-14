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
from pydantic import AfterValidator, BaseModel, Field, StringConstraints
from starlette.exceptions import HTTPException

from lektyra.adapters.store.postgres import FlagKind, PersonFields, PersonKind
from lektyra.app.live import LiveDevices, LiveManager, LiveSource, LiveState
from lektyra.app.review import (
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


def _router(review: Review, live: LiveManager) -> APIRouter:
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

    # live
    @api.get("/live")
    def live_state() -> LiveState | None:
        return live.state()

    @api.get("/live/sources")
    def live_sources() -> list[LiveSource]:
        return live.sources()

    @api.get("/live/devices")
    def live_devices() -> LiveDevices:
        return live.devices()

    @api.post("/live", status_code=201)
    def live_start(body: LiveStartIn) -> LiveState:
        return live.start(body.source, body.title or None, body.transcribe)

    @api.post("/live/stop")
    def live_stop() -> LiveState:
        return live.stop()

    @api.get("/live/media", response_class=FileResponse)
    def live_media() -> FileResponse:
        path, media_type = live.media()
        return FileResponse(path, media_type=media_type)

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


def create_app(review: Review, live: LiveManager, dist: Path | None) -> FastAPI:
    app = FastAPI(title="lektyra", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    _install_errors(app)
    app.include_router(_router(review, live))
    if dist is not None:
        _spa(app, dist)
    return app
