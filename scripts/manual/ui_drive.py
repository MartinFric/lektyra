"""Drive the local UI in a headless Edge and take screenshots you read back (skill `manual-testing`).

One browser page lives in a small daemon, so a dialog opened by one command is still open for the next:

    uv run python scripts/manual/ui_drive.py serve --base http://127.0.0.1:8799 --shots <dir>   # background
    uv run python scripts/manual/ui_drive.py goto /persons
    uv run python scripts/manual/ui_drive.py click "role=button[name='New person']"
    uv run python scripts/manual/ui_drive.py fill "role=textbox[name='Name']" "Test Person"
    uv run python scripts/manual/ui_drive.py press Enter
    uv run python scripts/manual/ui_drive.py shot persons-new          # then Read <dir>/persons-new.png
    uv run python scripts/manual/ui_drive.py text "main"               # visible text of an element
    uv run python scripts/manual/ui_drive.py console                   # browser errors, failed requests
    uv run python scripts/manual/ui_drive.py stop

Selectors are Playwright's: CSS, `text=…`, `role=button[name='…']`. A command that finds nothing fails loudly
(exit 1) instead of looking like success. The daemon listens on 127.0.0.1 only and drives only the --base origin.
"""

import argparse
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Final

from playwright.sync_api import ConsoleMessage, Page, Request, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from pydantic import BaseModel

PORT: Final = 8798
TIMEOUT_MS: Final = 5_000


class Command(BaseModel):
    op: str
    args: list[str] = []


class Answer(BaseModel):
    ok: bool
    message: str
    url: str = ""


class Driver:
    def __init__(self, page: Page, base: str, shots: Path) -> None:
        self.page = page
        self.base = base.rstrip("/")
        self.shots = shots
        self.events: list[str] = []
        page.on("console", self._console)
        page.on("pageerror", lambda err: self.events.append(f"pageerror: {err}"))
        page.on("requestfailed", self._failed)
        page.on("response", lambda r: self.events.append(f"http {r.status}: {r.url}") if r.status >= 400 else None)

    def _console(self, msg: ConsoleMessage) -> None:
        if msg.type in ("error", "warning"):
            self.events.append(f"console.{msg.type}: {msg.text}")

    def _failed(self, request: Request) -> None:
        if request.resource_type == "media" and (request.failure or "").endswith("ERR_ABORTED"):
            return  # <audio preload="metadata"> stops its download on purpose
        self.events.append(f"requestfailed: {request.url} ({request.failure or 'unknown'})")

    def run(self, cmd: Command) -> Answer:
        page = self.page
        a = cmd.args
        if cmd.op == "goto":
            path = a[0] if a else "/"
            if not path.startswith(("/", "http")):
                path = f"/{path}"  # Git Bash rewrites a leading "/" into a Windows path; "videos" works everywhere
            if path.startswith("http") and not path.startswith(self.base):
                return Answer(ok=False, message=f"only {self.base} is driven")
            page.goto(path if path.startswith("http") else f"{self.base}{path}", wait_until="networkidle")
            return Answer(ok=True, message="loaded", url=page.url)
        if cmd.op == "shot":
            name = (a[0] if a else "shot").replace("/", "_").replace("\\", "_")
            target = self.shots / f"{name}.png"
            page.screenshot(path=str(target), full_page=len(a) > 1 and a[1] == "full")
            return Answer(ok=True, message=str(target.resolve()), url=page.url)
        if cmd.op == "click":
            page.locator(a[0]).first.click(timeout=TIMEOUT_MS)
            page.wait_for_load_state("networkidle")
            return Answer(ok=True, message=f"clicked {a[0]}", url=page.url)
        if cmd.op == "hover":
            page.locator(a[0]).first.hover(timeout=TIMEOUT_MS)
            return Answer(ok=True, message=f"hovered {a[0]}", url=page.url)
        if cmd.op == "fill":
            page.locator(a[0]).first.fill(a[1], timeout=TIMEOUT_MS)
            return Answer(ok=True, message=f"filled {a[0]}", url=page.url)
        if cmd.op == "press":
            page.keyboard.press(a[0])
            page.wait_for_load_state("networkidle")
            return Answer(ok=True, message=f"pressed {a[0]}", url=page.url)
        if cmd.op == "text":
            return Answer(ok=True, message=page.locator(a[0]).first.inner_text(timeout=TIMEOUT_MS), url=page.url)
        if cmd.op == "wait":
            page.wait_for_timeout(float(a[0]) if a else 500)
            return Answer(ok=True, message="waited", url=page.url)
        if cmd.op == "console":
            events, self.events = self.events, []
            return Answer(ok=True, message="\n".join(events) or "no errors", url=page.url)
        return Answer(ok=False, message=f"unknown command {cmd.op!r}")


def serve(base: str, shots: Path, port: int) -> None:
    shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1, locale="en-GB")
        driver = Driver(page, base, shots)
        stopping = False

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                nonlocal stopping
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                try:
                    cmd = Command.model_validate_json(body)
                    if cmd.op == "stop":
                        stopping = True
                        answer = Answer(ok=True, message="stopping")
                    else:
                        answer = driver.run(cmd)
                except (PlaywrightError, ValueError, IndexError) as err:
                    answer = Answer(ok=False, message=str(err).splitlines()[0], url=page.url)
                data = answer.model_dump_json().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: object) -> None:
                return

        server = HTTPServer(("127.0.0.1", port), Handler)
        print(f"driving {base} in headless Edge; shots in {shots.resolve()}; commands on 127.0.0.1:{port}", flush=True)
        while not stopping:
            server.handle_request()
        server.server_close()
        browser.close()


def send(op: str, args: list[str], port: int) -> int:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/",
        data=Command(op=op, args=args).model_dump_json().encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    waiting_s = float(args[0]) / 1000 if op == "wait" and args else 0.0
    try:
        with urllib.request.urlopen(request, timeout=60 + waiting_s) as response:
            answer = Answer.model_validate_json(response.read())
    except urllib.error.URLError:
        print("no driver running: start `ui_drive.py serve` first", file=sys.stderr)
        return 2
    print(answer.message)
    if answer.url:
        print(f"[{answer.url}]")
    return 0 if answer.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=PORT)
    sub = parser.add_subparsers(dest="op", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--base", default="http://127.0.0.1:8799")
    s.add_argument("--shots", type=Path, required=True)
    for op in ("goto", "shot", "click", "hover", "fill", "press", "text", "wait", "console", "stop"):
        sub.add_parser(op).add_argument("args", nargs="*")
    ns = parser.parse_args()
    if ns.op == "serve":
        serve(str(ns.base), Path(ns.shots), int(ns.port))
        return 0
    return send(str(ns.op), [str(x) for x in ns.args], int(ns.port))


if __name__ == "__main__":
    raise SystemExit(main())
