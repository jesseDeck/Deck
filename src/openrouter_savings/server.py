"""Local web server: a small JSON REST API plus the static single-page UI.

Deliberately built on the standard library's ``http.server`` rather than a
web framework -- this is a single-user, localhost-only tool, and the existing
project already keeps its dependency list to just ``requests``.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from .csv_import import CsvImportError, parse_price_history_csv_text
from .models import TrackedModel, UsageEntry
from .openrouter_client import OpenRouterClient
from .savings import compute_savings
from .snapshot_job import take_snapshot
from .storage import Store
from .uptime import summarize_uptime

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "web" / "static"

_STATIC_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


class ApiError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


Handler = Callable[["RequestContext"], Any]


class RequestContext:
    def __init__(self, store: Store, client: OpenRouterClient, path_params: dict[str, str],
                 query: dict[str, list[str]], body: bytes):
        self.store = store
        self.client = client
        self.path_params = path_params
        self.query = query
        self._body = body

    def json_body(self) -> dict[str, Any]:
        if not self._body:
            return {}
        try:
            return json.loads(self._body)
        except json.JSONDecodeError as exc:
            raise ApiError(400, f"Invalid JSON body: {exc}") from exc

    def raw_body(self) -> bytes:
        return self._body

    def query_flag(self, name: str, default: bool = False) -> bool:
        values = self.query.get(name)
        if not values:
            return default
        return values[0].lower() in ("1", "true", "yes")


class Route:
    def __init__(self, method: str, pattern: str, handler: Handler):
        self.method = method
        self.handler = handler
        regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", pattern)
        self.regex = re.compile(f"^{regex}$")

    def match(self, method: str, path: str) -> dict[str, str] | None:
        if method != self.method:
            return None
        match = self.regex.match(path)
        return match.groupdict() if match else None


def _list_usage(ctx: RequestContext) -> Any:
    return [e.to_dict() for e in ctx.store.usage.all()]


def _add_usage(ctx: RequestContext) -> Any:
    payload = ctx.json_body()
    for field_name in ("model", "provider_used", "timestamp"):
        if not payload.get(field_name):
            raise ApiError(400, f"'{field_name}' is required")
    entry = UsageEntry.from_dict(payload)
    ctx.store.usage.append(entry)
    return entry.to_dict()


def _delete_usage(ctx: RequestContext) -> Any:
    removed = ctx.store.usage.remove_by_id(ctx.path_params["entry_id"])
    if not removed:
        raise ApiError(404, "usage entry not found")
    return {"removed": True}


def _list_tracked(ctx: RequestContext) -> Any:
    return [t.to_dict() for t in ctx.store.tracked_models.all()]


def _add_tracked(ctx: RequestContext) -> Any:
    payload = ctx.json_body()
    if not payload.get("model"):
        raise ApiError(400, "'model' is required")
    existing = {t.model for t in ctx.store.tracked_models.all()}
    if payload["model"] not in existing:
        ctx.store.tracked_models.append(TrackedModel(model=payload["model"], label=payload.get("label", "")))
    return {"tracked": True}


def _delete_tracked(ctx: RequestContext) -> Any:
    model = unquote(ctx.path_params["model"])
    remaining = [t for t in ctx.store.tracked_models.all() if t.model != model]
    ctx.store.tracked_models.replace_all(remaining)
    return {"removed": True}


def _run_snapshot(ctx: RequestContext) -> Any:
    return take_snapshot(ctx.store, ctx.client)


def _get_report(ctx: RequestContext) -> Any:
    live_client = ctx.client if ctx.query_flag("allow_live_fallback", default=True) else None
    report = compute_savings(ctx.store.usage.all(), ctx.store.price_snapshots.all(), live_client=live_client)
    return report.to_dict()


def _get_uptime(ctx: RequestContext) -> Any:
    summaries = summarize_uptime(ctx.store.uptime_snapshots.all())
    return [s.to_dict() for s in summaries]


def _search_models(ctx: RequestContext) -> Any:
    query = (ctx.query.get("q") or [""])[0].lower()
    models = ctx.client.list_models()
    if query:
        models = [
            m for m in models
            if query in m.get("id", "").lower() or query in (m.get("name") or "").lower()
        ][:50]
    else:
        models = models[:50]
    return [{"id": m.get("id"), "name": m.get("name")} for m in models]


def _import_price_history(ctx: RequestContext) -> Any:
    text = ctx.raw_body().decode("utf-8", errors="replace")
    try:
        snapshots = parse_price_history_csv_text(text)
    except CsvImportError as exc:
        raise ApiError(400, str(exc)) from exc
    existing = ctx.store.price_snapshots.all()
    ctx.store.price_snapshots.replace_all(existing + snapshots)
    return {"imported": len(snapshots)}


ROUTES = [
    Route("GET", "/api/usage", _list_usage),
    Route("POST", "/api/usage", _add_usage),
    Route("DELETE", "/api/usage/{entry_id}", _delete_usage),
    Route("GET", "/api/tracked", _list_tracked),
    Route("POST", "/api/tracked", _add_tracked),
    Route("DELETE", "/api/tracked/{model}", _delete_tracked),
    Route("POST", "/api/snapshot", _run_snapshot),
    Route("GET", "/api/report", _get_report),
    Route("GET", "/api/uptime", _get_uptime),
    Route("GET", "/api/models", _search_models),
    Route("POST", "/api/import-price-history", _import_price_history),
]


def _make_handler(store: Store, client: OpenRouterClient) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "OpenRouterSavings/0.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            logger.info("%s - %s", self.address_string(), format % args)

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_static(self, path: str) -> None:
            clean = path.lstrip("/") or "index.html"
            file_path = (STATIC_DIR / clean).resolve()
            if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
                self._send_json(404, {"error": "not found"})
                return
            if not file_path.exists():
                file_path = STATIC_DIR / "index.html"
            content_type = _STATIC_CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _dispatch(self, method: str) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""

            if not parsed.path.startswith("/api/"):
                if method == "GET":
                    self._serve_static(parsed.path)
                else:
                    self._send_json(404, {"error": "not found"})
                return

            for route in ROUTES:
                params = route.match(method, parsed.path)
                if params is None:
                    continue
                ctx = RequestContext(store, client, params, query, body)
                try:
                    result = route.handler(ctx)
                    self._send_json(200, result)
                except ApiError as exc:
                    self._send_json(exc.status_code, {"error": exc.message})
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Unhandled error in %s %s", method, parsed.path)
                    self._send_json(500, {"error": str(exc)})
                return

            self._send_json(404, {"error": "no route matched"})

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def do_DELETE(self) -> None:  # noqa: N802
            self._dispatch("DELETE")

    return Handler


def serve(
    store: Store,
    client: OpenRouterClient,
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    poll_interval_minutes: float | None = None,
) -> None:
    """Start the local web server, blocking until interrupted.

    If ``poll_interval_minutes`` is set, a background thread also calls
    ``take_snapshot`` on that interval so price/uptime history accumulates
    automatically while the server is running.
    """
    handler_cls = _make_handler(store, client)
    httpd = ThreadingHTTPServer((host, port), handler_cls)

    stop_event = threading.Event()
    if poll_interval_minutes:
        def _poll_loop() -> None:
            while not stop_event.is_set():
                try:
                    summary = take_snapshot(store, client)
                    logger.info("Snapshot taken: %s", summary)
                except Exception:  # noqa: BLE001
                    logger.exception("Background snapshot failed")
                stop_event.wait(poll_interval_minutes * 60)

        thread = threading.Thread(target=_poll_loop, daemon=True)
        thread.start()

    print(f"OpenRouter savings calculator running at http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        httpd.shutdown()
