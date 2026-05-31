"""VM-facing web server for the final Inno Fantasy app.

This serves the built React frontend with Python's standard library and proxies
same-origin API requests to the FastAPI backend. It is intentionally dependency
free so the VM only needs Python/uv after the frontend build has been copied.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


APP_ROOT = Path(__file__).resolve().parent
DEFAULT_BUILD_DIR = APP_ROOT / "frontend" / "inno-fantasy" / "build"
DEFAULT_BACKEND_URL = f"http://{os.getenv('BACKEND_HOST', '127.0.0.1')}:{os.getenv('BACKEND_PORT', '10006')}"

API_PREFIXES = (
    "/upload",
    "/progress",
    "/public-data",
    "/scores",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {value!r}") from exc


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Inno Fantasy frontend and proxy API routes.")
    parser.add_argument(
        "--host",
        default=os.getenv("INNO_FANTASY_HOST", os.getenv("APP_HOST", "127.0.0.1")),
        help="Bind host for the public web/proxy server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=env_int("INNO_FANTASY_PORT", env_int("APP_PORT", 6004)),
        help="Bind port for the public web/proxy server.",
    )
    parser.add_argument(
        "--backend-url",
        default=os.getenv("INNO_FANTASY_BACKEND_URL", DEFAULT_BACKEND_URL),
        help="Internal FastAPI backend base URL.",
    )
    parser.add_argument(
        "--build-dir",
        default=os.getenv("FRONTEND_BUILD_DIR", str(DEFAULT_BUILD_DIR)),
        help="Path to the React production build directory.",
    )
    return parser.parse_args(argv)


def validate_build_dir(build_dir: Path) -> None:
    index_html = build_dir / "index.html"
    if index_html.is_file():
        return
    raise SystemExit(
        "Missing frontend build at "
        f"{index_html}. Build it before deploying, then copy frontend/inno-fantasy/build to the VM."
    )


def normalize_backend_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit(f"Invalid backend URL: {url!r}")
    return url.rstrip("/")


class InnoFantasyHandler(SimpleHTTPRequestHandler):
    backend_url = DEFAULT_BACKEND_URL.rstrip("/")
    proxy_timeout_seconds = 3600

    def log_message(self, format: str, *args: object) -> None:
        if sys.stderr:
            super().log_message(format, *args)

    def do_GET(self) -> None:
        self.route_request()

    def do_HEAD(self) -> None:
        self.route_request()

    def do_POST(self) -> None:
        self.route_request()

    def do_PUT(self) -> None:
        self.route_request()

    def do_PATCH(self) -> None:
        self.route_request()

    def do_DELETE(self) -> None:
        self.route_request()

    def do_OPTIONS(self) -> None:
        self.route_request()

    def route_request(self) -> None:
        path = urlsplit(self.path).path
        if self.is_api_path(path):
            self.proxy_to_backend()
            return

        if self.command not in {"GET", "HEAD"}:
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Static assets only support GET/HEAD")
            return

        if self.command == "HEAD":
            super().do_HEAD()
            return

        super().do_GET()

    def send_head(self):  # type: ignore[override]
        path = self.translate_path(self.path)
        if not os.path.exists(path):
            self.path = "/index.html"
        return super().send_head()

    @staticmethod
    def is_api_path(path: str) -> bool:
        return any(path == prefix or path.startswith(f"{prefix}/") for prefix in API_PREFIXES)

    def proxy_to_backend(self) -> None:
        body = self.read_body()
        request = Request(
            self.target_url(),
            data=body,
            headers=self.forward_request_headers(),
            method=self.command,
        )

        try:
            with urlopen(request, timeout=self.proxy_timeout_seconds) as upstream:
                self.send_upstream_response(upstream.status, upstream.reason, upstream.headers, upstream)
        except HTTPError as error:
            self.send_upstream_response(error.code, error.reason, error.headers, error)
        except URLError as error:
            self.send_json(
                {"detail": f"Backend proxy failed: {getattr(error, 'reason', error)}"},
                status=HTTPStatus.BAD_GATEWAY,
            )

    def target_url(self) -> str:
        parsed = urlsplit(self.path)
        return urlunsplit(
            (
                urlsplit(self.backend_url).scheme,
                urlsplit(self.backend_url).netloc,
                parsed.path,
                parsed.query,
                "",
            )
        )

    def read_body(self) -> bytes | None:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length <= 0:
            return None
        return self.rfile.read(content_length)

    def forward_request_headers(self) -> dict[str, str]:
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS and name.lower() != "host"
        }
        backend_host = urlsplit(self.backend_url).netloc
        client_ip = self.client_address[0]
        existing_forwarded_for = self.headers.get("X-Forwarded-For")

        headers["Host"] = backend_host
        headers["X-Forwarded-For"] = (
            f"{existing_forwarded_for}, {client_ip}" if existing_forwarded_for else client_ip
        )
        headers["X-Forwarded-Host"] = self.headers.get("Host", backend_host)
        headers["X-Forwarded-Proto"] = self.headers.get("X-Forwarded-Proto", "http")
        return headers

    def send_upstream_response(self, status: int, reason: str, headers, upstream) -> None:
        self.send_response(status, reason)
        for name, value in headers.items():
            if name.lower() not in HOP_BY_HOP_HEADERS:
                self.send_header(name, value)
        self.end_headers()

        if self.command == "HEAD":
            return

        while True:
            chunk = upstream.read(64 * 1024)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()

    def send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    build_dir = Path(args.build_dir).resolve()
    validate_build_dir(build_dir)

    backend_url = normalize_backend_url(args.backend_url)
    handler_class = type("ConfiguredInnoFantasyHandler", (InnoFantasyHandler,), {"backend_url": backend_url})
    handler = partial(handler_class, directory=str(build_dir))

    ThreadingHTTPServer.allow_reuse_address = True
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f"Inno Fantasy app: http://{args.host}:{args.port}", flush=True)
        print(f"Frontend build: {build_dir}", flush=True)
        print(f"Backend proxy: {backend_url}", flush=True)
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
