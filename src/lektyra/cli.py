"""The command line: parses arguments and calls app/ (ADR-002). The one module that prints (ADR-001)."""

import io
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from lektyra import __version__
from lektyra.settings import SECRETS_FILE, load_settings

if TYPE_CHECKING:
    from lektyra.app.photos import Photos
    from lektyra.errors import LektyraError
    from lektyra.ports import ObjectStore
    from lektyra.settings import Settings

# Windows consoles and pipes default to cp1252; Slovak titles and "→" must never crash a run mid-stream.
for _stream in (sys.stdout, sys.stderr):
    if isinstance(_stream, io.TextIOWrapper):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(no_args_is_help=True, add_completion=False, help="lektyra: speech → transcript → claims")


@app.command()
def version() -> None:
    """Print the version."""
    print(__version__)


def _tool_version(binary: str, arg: str) -> str | None:
    path = shutil.which(binary)
    if path is None:
        return None
    done = subprocess.run([path, arg], capture_output=True, text=True, check=False, timeout=20)
    first = (done.stdout or done.stderr).strip().splitlines()
    return first[0] if first else path


@app.command()
def doctor() -> None:
    """Check tools and keys. Keys are reported as present or missing, never shown."""
    settings = load_settings()
    ok = True
    for name, binary, arg in (
        ("ffmpeg", settings.ffmpeg, "-version"),
        ("yt-dlp", settings.ytdlp, "--version"),
    ):
        found = _tool_version(binary, arg)
        ok = ok and found is not None
        print(f"{name:8} {found or 'MISSING'}")
    print(f"keys     {SECRETS_FILE} {'found' if SECRETS_FILE.exists() else 'MISSING'}")
    for key, value in (
        ("OPENROUTER_API_KEY", settings.openrouter_api_key),
        ("SONIOX_API_KEY", settings.soniox_api_key),
        ("HF_TOKEN", settings.hf_token),
    ):
        print(f"  {key:20} {'present' if value is not None else 'missing'}")
    print(f"data     {settings.data_dir.resolve()}")
    if not ok:
        raise typer.Exit(code=1)


@app.command()
def ingest(
    url: Annotated[str, typer.Argument(help="A live stream, a page with a video, a media URL or a local file")],
    title: Annotated[str | None, typer.Option(help="Override the source's title")] = None,
    realtime: Annotated[bool, typer.Option(help="Read a stored video at live speed (rehearse the live path)")] = False,
    max_minutes: Annotated[float | None, typer.Option(help="Stop after this many minutes of audio")] = None,
) -> None:
    """Read a source as a stream and cut it into pieces in quiet moments (ADR-006, ADR-007)."""
    from lektyra.app.ingest import Gap, run_ingest
    from lektyra.domain.chunking import Piece

    def show(p: Piece) -> None:
        length = (p.end_ms - p.own_start_ms) / 1000
        print(
            f"  piece {p.index:3}  {p.own_start_ms / 1000:8.2f} → {p.end_ms / 1000:8.2f} s"
            f"  ({length:5.1f} s)  cut: {p.cut_kind:6} quiet {p.quiet_ms} ms",
            flush=True,
        )

    def gap(g: Gap) -> None:
        print(
            f"  stream dropped at {g.at_ms / 1000:.1f} s, back after {g.wall_s:.0f} s (attempt {g.attempt})", flush=True
        )

    result = run_ingest(
        url,
        title=title,
        realtime=realtime,
        max_minutes=max_minutes,
        settings=load_settings(),
        on_piece=show,
        on_gap=gap,
    )
    print(f"event    {result.event_dir}")
    print(f"audio    {result.audio_s:.1f} s, {len(result.pieces)} pieces, stopped: {result.stopped}")
    if result.complete is False:
        print("WARNING  the stored video ended before its stated length: see manifest.json and ffmpeg.log")
    if result.gaps:
        print(f"gaps     {len(result.gaps)} (live stream dropped and came back)")
    if result.log_lines:
        print(f"ffmpeg   {result.log_lines} message line(s) in {result.event_dir / 'ffmpeg.log'}")


def _event_dir(selector: str) -> Path:
    """An event folder by path, full id, or a unique part of its id (e.g. 'a-v-politike' or '_d1-')."""
    settings = load_settings()
    as_path = Path(selector)
    if as_path.is_dir() and (as_path / "manifest.json").exists():
        return as_path
    events = settings.data_dir / "events"
    found = (
        sorted(d for d in events.iterdir() if d.is_dir() and selector.lower() in d.name.lower())
        if events.exists()
        else []
    )
    if len(found) != 1:
        names = ", ".join(d.name for d in found) or "none"
        raise typer.BadParameter(f"'{selector}' matches {len(found)} events ({names}); be more specific")
    return found[0]


@app.command()
def catalog() -> None:
    """OpenRouter's transcription models and their list price per audio hour today (ADR-002)."""
    from lektyra.adapters.stt.openrouter import catalog as fetch

    models = fetch(load_settings().openrouter_api_key)
    for m in sorted(models, key=lambda m: (m.usd_per_audio_hour is None, m.usd_per_audio_hour or 0, m.id)):
        price = f"${m.usd_per_audio_hour:6.3f}/h" if m.usd_per_audio_hour is not None else "token-priced"
        print(f"{price:>13}  {m.id}")


@app.command()
def transcribe(
    event: Annotated[str, typer.Argument(help="Event folder, id, or a unique part of the id")],
    models: Annotated[
        str, typer.Option(help="Comma-separated OpenRouter model ids, or 'screening' for the screening set")
    ] = "screening",
    window: Annotated[str | None, typer.Option(help="Only pieces overlapping from-to, e.g. 20:00-30:00")] = None,
    language: Annotated[
        str | None, typer.Option(help="Pin the language (e.g. sk); default: the engine detects")
    ] = None,
    force: Annotated[bool, typer.Option(help="Ask again even where a good answer is saved (costs money)")] = False,
    workers: Annotated[int, typer.Option(help="Requests in flight at once")] = 8,
) -> None:
    """Send pieces to speech-to-text engines; every answer is saved before it is parsed (ADR-003)."""
    from lektyra.app.transcribe import SCREENING, CallRecord, run_transcribe
    from lektyra.domain.timefmt import parse_window

    key = load_settings().openrouter_api_key
    if key is None:
        raise typer.BadParameter("OPENROUTER_API_KEY is missing in ~/.secrets/lektyra.env")
    chosen = list(SCREENING) if models == "screening" else [m.strip() for m in models.split(",") if m.strip()]
    folder = _event_dir(event)
    span = parse_window(window) if window else None

    def show(r: CallRecord) -> None:
        state = "ok" if r.error is None else f"FAILED {r.error[:100]}"
        cost = f"${r.cost_usd:.5f}" if r.cost_usd is not None else "   ?    "
        print(f"  {r.model:42} piece {r.piece:3}  {r.wall_ms / 1000:5.1f} s  {cost}  {state}", flush=True)

    records = run_transcribe(
        folder, chosen, api_key=key, window_ms=span, force=force, workers=workers, language=language, on_call=show
    )
    paid = [r for r in records if not r.cached]
    failed = [r for r in records if r.error is not None]
    cost = sum(r.cost_usd or 0.0 for r in paid)
    print(f"event    {folder.name}")
    print(f"calls    {len(paid)} new, {len(records) - len(paid)} already saved, {len(failed)} failed; cost ${cost:.4f}")
    for model in chosen:
        bad = [r for r in failed if r.model == model]
        if bad:
            print(f"  {model}: {len(bad)} failed, e.g. {bad[0].error}")


@app.command()
def compare(
    event: Annotated[str, typer.Argument(help="Event folder, id, or a unique part of the id")],
    window: Annotated[str, typer.Option(help="from-to, e.g. 20:00-30:00")],
) -> None:
    """Write the side-by-side page of every engine and a reference template to correct (spike-plan §6)."""
    from lektyra.app.compare import run_compare
    from lektyra.domain.timefmt import parse_window

    folder = _event_dir(event)
    result = run_compare(folder, parse_window(window), load_settings().data_dir / "refs")
    print(f"page     {result.page}")
    print(f"template {result.template}  ({result.listen_rows} of {result.rows} rows marked LISTEN)")
    print(f"{'engine':46} agreement  pieces  failed     cost  timing")
    for v in result.variants:
        print(f"  {v.variant:44} {v.agreement:9.2f}  {v.answered:6}  {v.failed:6}  ${v.cost_usd:7.4f}  {v.timing}")


@app.command()
def diarize(
    event: Annotated[str, typer.Argument(help="Event folder, id, or a unique part of the id")],
    threshold: Annotated[float, typer.Option(help="Cosine distance at which voices are kept apart")] = 0.55,
) -> None:
    """Who speaks when: S1…N with talk time; speakers.md lists their longest turns for naming (ADR-004)."""
    from lektyra.app.diarize import run_diarize

    folder = _event_dir(event)
    result = run_diarize(folder, load_settings(), threshold)
    print(f"event    {folder.name}")
    print(f"speakers {len(result.speakers)} from {result.windows} windows, {result.turns} turns")
    for s in result.speakers:
        print(f"  {s.label:4} {s.talk_s / 60:6.1f} min  {s.share:5.0%}  {s.turns:4} turns")
    print(f"naming   {folder / 'speakers.md'}")


@app.command()
def voices(
    min_share: Annotated[float, typer.Option(help="Only speakers with at least this share of their event")] = 0.05,
) -> None:
    """Match every diarized speaker against every other event's speakers by voice alone (no names)."""
    import json

    import numpy as np

    from lektyra.domain.diarization import similarity

    events = load_settings().data_dir / "events"
    found: list[tuple[str, str, np.ndarray]] = []
    for d in sorted(events.iterdir()):
        if not (d / "speakers.npy").exists():
            continue
        info = json.loads((d / "diarization.json").read_text(encoding="utf-8"))
        cents = np.load(d / "speakers.npy")
        short = d.name.split("_", 2)[-1][:22]
        for k, s in enumerate(info["speakers"]):
            if s["share"] >= min_share:
                found.append((short, f"{s['label']} {s['talk_s'] / 60:4.1f}m", cents[k]))
    if not found:
        print("no diarized events: run diarize first")
        raise typer.Exit(code=1)
    matrix = similarity(np.stack([f[2] for f in found]), np.stack([f[2] for f in found]))
    for i, (event_name, label, _) in enumerate(found):
        best = []
        for other in sorted({f[0] for f in found} - {event_name}):
            cands = [(float(matrix[i, j]), found[j][1].split()[0]) for j in range(len(found)) if found[j][0] == other]
            if cands:
                score, who = max(cands)
                best.append(f"{other[:12]}:{who}={score:.2f}")
        print(f"{event_name:22} {label:10}  " + "  ".join(best))


@app.command()
def report(
    event: Annotated[str, typer.Argument(help="Event folder, id, or a unique part of the id")],
    engine: Annotated[str, typer.Option(help="The OpenRouter model whose words to use")] = "elevenlabs/scribe-v2",
    language: Annotated[str | None, typer.Option(help="The language variant transcribed (e.g. sk)")] = "sk",
) -> None:
    """The transcript with speakers (S1…N, or names from names.json), in HTN's format."""
    from lektyra.app.report import run_report

    result = run_report(_event_dir(event), engine, language)
    print(f"transcript {result.path}")
    print(f"           {result.utterances} paragraphs, {result.words} words, {result.unknown_words} without a speaker")


@app.command()
def claims(
    event: Annotated[str, typer.Argument(help="Event folder, id, or a unique part of the id")],
    llm: Annotated[
        str, typer.Option(help="OpenRouter chat model that extracts the claims")
    ] = "google/gemini-3.5-flash",
    engine: Annotated[str, typer.Option(help="Whose transcript words to use")] = "elevenlabs/scribe-v2",
    language: Annotated[str | None, typer.Option(help="The transcript's language variant")] = "sk",
    until: Annotated[int | None, typer.Option(help="Stop after this minute (for a trial)")] = None,
    force: Annotated[bool, typer.Option(help="Ask again even where an answer is saved (costs money)")] = False,
) -> None:
    """Replay the claims loop minute by minute, as live (spike-plan §8): the ledger of checkable claims."""
    from lektyra.app.claims import MinuteRecord, run_claims
    from lektyra.domain.claims import Ledger

    key = load_settings().openrouter_api_key
    if key is None:
        raise typer.BadParameter("OPENROUTER_API_KEY is missing in ~/.secrets/lektyra.env")

    def show(r: MinuteRecord, ledger: Ledger) -> None:
        state = r.error or (f"{len(r.problems)} problem(s)" if r.problems else "ok")
        cost = f"${r.cost_usd:.4f}" if r.cost_usd is not None else "   ?   "
        print(f"  minute {r.minute:3}  {r.actions:2} action(s)  ledger {len(ledger.claims):3}  {cost}  "
              f"{'saved' if r.cached else f'{r.wall_ms / 1000:4.1f} s'}  {state}", flush=True)  # fmt: skip

    result = run_claims(
        _event_dir(event), api_key=key, llm=llm, engine=engine, language=language, until_minute=until, force=force,
        on_minute=show,
    )  # fmt: skip
    opened = [c for c in result.ledger.claims if c.status == "open"]
    print(
        f"claims   {len(result.ledger.claims)} ({len(opened)} open), {len(result.ledger.rejected)} rejected action(s)"
    )
    print(f"ledger   {result.md_path}")


@app.command("end-pass")
def end_pass(
    event: Annotated[str, typer.Argument(help="Event folder, id, or a unique part of the id")],
    llm: Annotated[str, typer.Option(help="OpenRouter chat model")] = "google/gemini-3.5-flash",
    engine: Annotated[str, typer.Option(help="Whose transcript words to use")] = "elevenlabs/scribe-v2",
    language: Annotated[str | None, typer.Option(help="The transcript's language variant")] = "sk",
    force: Annotated[bool, typer.Option(help="Ask again even if an answer is saved")] = False,
) -> None:
    """The whole-picture review after an event: missed claims, links, duplicates, corrections (spike-plan §8)."""
    from lektyra.app.claims import run_end_pass

    key = load_settings().openrouter_api_key
    if key is None:
        raise typer.BadParameter("OPENROUTER_API_KEY is missing in ~/.secrets/lektyra.env")
    r = run_end_pass(_event_dir(event), api_key=key, llm=llm, engine=engine, language=language, force=force)
    print(f"live     {len(r.before.claims)} claims")
    print(f"end pass +{len(r.added)} missed live, {r.linked} links, {r.withdrawn} withdrawn, {r.amended} amended")
    print(f"recall   live {len(r.before.claims) / max(1, len(r.before.claims) + len(r.added)):.0%} of the final ledger")
    print(f"cost     ${r.cost_usd or 0:.4f}")
    print(f"ledger   {r.md_path}")


@app.command()
def fetch(
    url: Annotated[str, typer.Argument(help="A TA3 article or ta3:<id>, YouTube, Facebook, a direct .m3u8/.mp4")],
    name: Annotated[str | None, typer.Option(help="File name (default: from the title)")] = None,
    database: Annotated[str | None, typer.Option(help="Another database (e.g. lektyra_manual)")] = None,
) -> None:
    """Download a video and keep it as an upload (lektyra's MinIO): it appears in the Live screen, to be played as
    live (ADR-016). Research use only, stays local (ADR-005)."""
    from lektyra.adapters.store.postgres import Store, with_database
    from lektyra.app.ingest import default_source
    from lektyra.app.photos import open_objects
    from lektyra.app.uploads import Uploads
    from lektyra.domain.naming import slug
    from lektyra.errors import LektyraError

    settings = load_settings()
    source = default_source(settings)
    info = source.resolve(url)
    if info.is_live:
        raise typer.BadParameter("this is a live stream: start it in the UI's Live screen instead of downloading it")
    stem = name or slug(info.title, 80) or "video"
    file_name = stem if stem.endswith(".mp4") else f"{stem}.mp4"
    store = Store(with_database(settings.database_url, database) if database else settings.database_url)
    store.migrate(Path("migrations"))
    objects = open_objects(settings, "videos", database)
    uploads = Uploads(store, objects, settings.data_dir / "cache" / "uploads", settings.reviewer)
    out = uploads.temp_file().with_suffix(".download.mp4")  # ffmpeg picks the container by the extension
    print(f"title    {info.title}")
    print(f"length   {info.duration_s / 60:.1f} min" if info.duration_s else "length   unknown")
    try:
        source.download(info, out)
        upload = uploads.add(file_name, out)
    except LektyraError as err:
        _fail(err)
    finally:
        out.unlink(missing_ok=True)
    print(f"done     {upload.name}, {upload.size / 1e6:.0f} MB: Live → Uploaded videos")


def _picture_store(settings: "Settings", database: str | None) -> "ObjectStore":
    from lektyra.app.photos import open_objects

    return open_objects(settings, "pictures", database)


def _sweep(photos: "Photos") -> None:
    """Pictures nobody points at go (a forgotten person's); a store that is down only turns faces off."""
    from lektyra.errors import LektyraError

    try:
        gone = photos.sweep()
        print(f"pictures lektyra's MinIO{f', swept {gone} left over' if gone else ''}")
    except LektyraError as err:
        print(f"pictures off: {err.message}")


# pictures (ADR-015, skill profile-pictures) -----------------------------------------------------------------------
photo = typer.Typer(no_args_is_help=True, help="Profile pictures of named persons (ADR-015).")
app.add_typer(photo, name="photo")
Database = Annotated[str | None, typer.Option(help="Another database on the same server (e.g. lektyra_manual)")]


def _photos(database: str | None) -> "Photos":
    from lektyra.adapters.store.postgres import Store, with_database
    from lektyra.app.photos import Photos

    settings = load_settings()
    store = Store(with_database(settings.database_url, database) if database else settings.database_url)
    store.migrate(Path("migrations"))
    return Photos(store, _picture_store(settings, database), settings.reviewer)


def _fail(err: "LektyraError") -> NoReturn:
    print(f"error    {err.message}", file=sys.stderr)
    raise typer.Exit(code=1)


@photo.command("missing")
def photo_missing(database: Database = None) -> None:
    """Named persons without a picture: id, name, kind, function, party, knowledge link."""
    rows = _photos(database).missing()
    for p in rows:
        private = "" if p.public_figure else "   (not a public figure: no picture from the web)"
        print(
            f"{p.id:>5}  {p.name:<30} {p.kind:<10} {p.function or '-':<26} {p.party or '-':<12} "
            f"{p.external_ref or '-'}{private}"
        )
    print(f"{len(rows)} named without a picture")


@photo.command("find")
def photo_find(name: Annotated[str, typer.Argument(help="The name as people say it")]) -> None:
    """Wikidata items for a name, people first: which one is meant is yours (or the skill's) to decide."""
    from lektyra.adapters.knowledge.wikimedia import Wikimedia
    from lektyra.errors import LektyraError

    try:
        hits = Wikimedia().search(name)
    except LektyraError as err:
        _fail(err)
    for h in hits:
        kind = "person" if h.human else "other "
        has = "picture" if h.has_picture else "-      "
        print(f"{h.qid:<11} {kind} {has}  {h.label} — {h.description or 'no description'}")
    if not hits:
        print("nothing on Wikidata")


@photo.command("set")
def photo_set(
    person: Annotated[int, typer.Argument(help="Person id (see `lektyra photo missing`)")],
    wikidata: Annotated[str | None, typer.Option(help="Q-id: Wikidata's picture, licence and author")] = None,
    file: Annotated[Path | None, typer.Option(help="A picture on this PC", exists=True, dir_okay=False)] = None,
    url: Annotated[str | None, typer.Option(help="An https address of a picture")] = None,
    source_url: Annotated[str | None, typer.Option(help="The page the picture is from (for --file / --url)")] = None,
    license: Annotated[
        str | None, typer.Option(help="As the source states it; empty = unknown, local use only")
    ] = None,
    author: Annotated[str | None, typer.Option(help="Photographer or owner, as credited")] = None,
    database: Database = None,
) -> None:
    """Give a named person a picture. lektyra re-encodes it (WebP, ≤ 512 px, no metadata) and keeps its source."""
    from lektyra.adapters.store.postgres import PhotoSource
    from lektyra.errors import LektyraError

    if sum(x is not None for x in (wikidata, file, url)) != 1:
        raise typer.BadParameter("give exactly one of --wikidata, --file, --url")
    photos = _photos(database)
    source = PhotoSource(source_url=source_url, license=license, author=author)
    try:
        if wikidata is not None:
            saved = photos.from_wikidata(person, wikidata)
        elif file is not None:
            saved = photos.upload(person, file.read_bytes(), source)
        else:
            saved = photos.from_url(person, url or "", source)
    except LektyraError as err:
        _fail(err)
    p = saved.photo
    if p is None:
        _fail(LektyraError("internal", "The picture was not saved."))
    print(f"{saved.name}: picture {p.version} · {p.license or 'licence unknown (local use only)'}")
    print(f"         from {p.source_url or 'a file'}{f' · by {p.author}' if p.author else ''}")
    if wikidata is not None and saved.external_ref == wikidata:
        print(f"         knowledge link {wikidata}")


@photo.command("remove")
def photo_remove(
    person: Annotated[int, typer.Argument(help="Person id")],
    database: Database = None,
) -> None:
    """Remove a person's picture (the file goes from the picture store too)."""
    from lektyra.errors import LektyraError

    try:
        _photos(database).remove(person)
    except LektyraError as err:
        _fail(err)
    print("removed")


def serve(
    port: Annotated[int, typer.Option(help="Port on 127.0.0.1")] = 8765,
    database: Annotated[
        str | None, typer.Option(help="Another database on the same server (e.g. lektyra_manual)")
    ] = None,
    reset: Annotated[bool, typer.Option(help="Drop and recreate --database first (never the main one)")] = False,
) -> None:
    """lektyra's backend: the schedule, live sessions and the API, and the review UI it serves (ADR-009, ADR-016).
    Migrates, syncs data/events, then runs until stopped. The browser is only a view: closing it stops nothing.
    Started at logon by the Windows task "lektyra" (scripts/install-service.ps1)."""
    import logging

    import uvicorn

    from lektyra.adapters.store.postgres import Store, database_name, ensure_database, with_database
    from lektyra.adapters.web.api import create_app
    from lektyra.app.live import LiveManager, ecapa
    from lektyra.app.photos import Photos, open_objects
    from lektyra.app.review import Review
    from lektyra.app.schedule import Scheduler
    from lektyra.app.uploads import Uploads

    settings = load_settings()
    main_db = database_name(settings.database_url)
    url = with_database(settings.database_url, database) if database else settings.database_url
    if reset and (database is None or database == main_db):
        raise typer.BadParameter(f"--reset only with --database other than the main one ({main_db})")
    if database:
        created = ensure_database(url, reset)
        print(f"database {database} {'created' if created else 'kept'}")
    store = Store(url)
    applied = store.migrate(Path("migrations"))
    print(f"migrated {applied or 'nothing new'}")
    photos = Photos(store, _picture_store(settings, database), settings.reviewer)
    review = Review(store, settings.data_dir / "events", settings.reviewer, photos)
    synced = review.sync()
    print(f"synced   {synced.events} videos, {synced.speakers} speakers")
    _sweep(photos)
    dist = Path("web") / "dist"
    built = (dist / "index.html").exists()
    print(f"ui       http://127.0.0.1:{port}/{'' if built else '  (not built: npm run build in web/)'}")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    uploads = Uploads(
        store,
        open_objects(settings, "videos", database),
        settings.data_dir / "cache" / "uploads",
        settings.reviewer,
    )
    live = LiveManager(settings, store, review, ecapa(settings), resolve_upload=uploads.local)
    schedule = Scheduler(store, live, settings.reviewer)
    schedule.start()
    upcoming = [r for r in schedule.runs() if r.status in ("scheduled", "running")]
    print(
        f"schedule {len(upcoming)} run(s) to come"
        + (f", next {upcoming[0].starts_at.astimezone():%d.%m. %H:%M}" if upcoming else "")
    )
    print("         this process runs the schedule and the live sessions; the browser only shows them")
    app_ = create_app(review, live, photos, uploads, schedule, dist, port)
    uvicorn.run(app_, host="127.0.0.1", port=port, log_level="warning")


app.command(name="serve")(serve)
app.command(name="ui", help="The same as `serve` (its first name).")(serve)
