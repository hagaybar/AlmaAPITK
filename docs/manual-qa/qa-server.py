#!/usr/bin/env python3
"""
Tiny localhost HTTP server for the Plan B manual QA collaboration loop.

Serves the QA HTML and mediates state between the browser (where the user runs
manual QA) and Claude Code (which reads state via Bash and writes replies back
that the HTML displays inline).

Endpoints:
  GET  /                            -> the QA HTML
  GET  /state                       -> current state JSON
  POST /state                       -> save state from HTML
  GET  /replies                     -> all replies from Claude
  GET  /replies/since/<id>          -> replies with id > given id (for polling)
  POST /ping                        -> user-initiated ping (writes ping marker)
  GET  /ping                        -> last ping marker (so Claude can see it)

State files (in /tmp by default):
  /tmp/plan-b-qa-state.json    -> current QA state (statuses + notes)
  /tmp/plan-b-qa-replies.json  -> array of replies from Claude
  /tmp/plan-b-qa-ping.json     -> last ping marker {"testId": "...", "ts": ...}

Bind: 127.0.0.1:8765 (localhost only).
Stop with Ctrl+C or `pkill -f qa-server.py`.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Auto-redact JWT-shaped values from any incoming POST body before persisting.
# Three base64-url segments joined by dots, starting with the standard "eyJ"
# header (base64 of `{"`). Catches Cognito ID/access tokens and any other JWT
# a tester might paste from a Network tab.
_JWT_RE = re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
# Alma API keys: the Authorization header form (`apikey <token>`) and any
# `ALMA_*_API_KEY = <value>` a tester might paste. Conservative — only fires
# in an unambiguous key context, so ordinary notes aren't scrubbed (R9).
_APIKEY_RE = re.compile(r'(?i)\bapikey\s+[A-Za-z0-9._-]{12,}')
_ENVKEY_RE = re.compile(r'(?i)(ALMA_[A-Z_]*API_KEY\s*[=:]\s*)\S+')


def redact_jwts(value):
    """Scrub JWTs and Alma API keys from any value before it is persisted."""
    if isinstance(value, str):
        value = _JWT_RE.sub('<REDACTED-JWT>', value)
        value = _APIKEY_RE.sub('apikey <REDACTED-KEY>', value)
        value = _ENVKEY_RE.sub(r'\1<REDACTED-KEY>', value)
        return value
    if isinstance(value, list):
        return [redact_jwts(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_jwts(v) for k, v in value.items()}
    return value

HOST = "127.0.0.1"
PORT = int(os.environ.get("QA_PORT", "8765"))


def _pick_html() -> Path:
    """Serve the explicitly-requested QA page, else the newest dated
    *-qa.html in this directory (date-prefixed names sort chronologically)."""
    override = os.environ.get("QA_HTML")
    if override:
        return Path(override)
    here = Path(__file__).parent
    candidates = sorted(here.glob("*-qa.html"))
    return candidates[-1] if candidates else here / "2026-05-19-plan-b-staging-qa.html"


HTML_PATH = _pick_html()
# Per-page state files, derived from the served page's name, so different QA
# sessions never collide in /tmp (e.g. Plan B vs. Phase 1 keep separate state).
_STEM = HTML_PATH.stem
STATE_FILE = Path(os.environ.get("QA_STATE_FILE", f"/tmp/qa-{_STEM}-state.json"))
REPLIES_FILE = Path(os.environ.get("QA_REPLIES_FILE", f"/tmp/qa-{_STEM}-replies.json"))
PING_FILE = Path(os.environ.get("QA_PING_FILE", f"/tmp/qa-{_STEM}-ping.json"))


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        # Quieter logging — only show non-200 and POSTs.
        if args and isinstance(args[-1], str) and args[-1].startswith("2"):
            if "POST" not in (fmt % args):
                return
        sys.stderr.write("[qa-server] %s - %s\n" % (
            self.address_string(), fmt % args))

    def _send_json(self, status: int, body) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, status: int, body: str, ctype: str = "text/plain; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length > 0 else b""

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]

        if path == "/" or path == "/index.html":
            if not HTML_PATH.exists():
                self._send_text(500, f"HTML missing: {HTML_PATH}")
                return
            self._send_text(200, HTML_PATH.read_text(), "text/html; charset=utf-8")
            return

        if path == "/state":
            self._send_json(200, read_json(STATE_FILE, {}))
            return

        if path == "/replies":
            self._send_json(200, read_json(REPLIES_FILE, []))
            return

        if path.startswith("/replies/since/"):
            since = path.rsplit("/", 1)[-1]
            replies = read_json(REPLIES_FILE, [])
            new = [r for r in replies if str(r.get("id", "")) > str(since)]
            self._send_json(200, new)
            return

        if path == "/ping":
            self._send_json(200, read_json(PING_FILE, {}))
            return

        if path == "/health":
            self._send_json(200, {"ok": True, "ts": time.time()})
            return

        self._send_text(404, f"not found: {path}")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        body = self._read_body()

        if path == "/state":
            try:
                data = json.loads(body or b"{}")
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid json"})
                return
            data = redact_jwts(data)
            write_json(STATE_FILE, data)
            self._send_json(200, {"ok": True})
            return

        if path == "/ping":
            try:
                data = json.loads(body or b"{}")
            except json.JSONDecodeError:
                data = {}
            data = redact_jwts(data)
            data["ts"] = time.time()
            write_json(PING_FILE, data)
            self._send_json(200, {"ok": True, "ts": data["ts"]})
            return

        if path == "/reply":
            # Endpoint Claude (or anyone with shell access) can POST to from
            # outside if they prefer not to write the file directly.
            try:
                reply = json.loads(body or b"{}")
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid json"})
                return
            reply = redact_jwts(reply)
            replies = read_json(REPLIES_FILE, [])
            reply.setdefault("id", str(int(time.time() * 1000)))
            reply.setdefault("ts", time.time())
            replies.append(reply)
            write_json(REPLIES_FILE, replies)
            self._send_json(200, {"ok": True, "id": reply["id"]})
            return

        self._send_text(404, f"not found: {path}")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main() -> None:
    # Ensure state files start in a known state (don't truncate existing).
    for f, default in [(STATE_FILE, {}), (REPLIES_FILE, []), (PING_FILE, {})]:
        if not f.exists():
            write_json(f, default)

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    sys.stderr.write(f"[qa-server] serving on http://{HOST}:{PORT}\n")
    sys.stderr.write(f"[qa-server] HTML:    {HTML_PATH}\n")
    sys.stderr.write(f"[qa-server] state:   {STATE_FILE}\n")
    sys.stderr.write(f"[qa-server] replies: {REPLIES_FILE}\n")
    sys.stderr.write(f"[qa-server] ping:    {PING_FILE}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[qa-server] shutting down\n")
        server.shutdown()


if __name__ == "__main__":
    main()
