# HTML Dashboard Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a global, all-repos Claude Code skill `html-dashboard` that generates visually compelling HTML (interactive dashboards with a live browser↔Claude link, and static reports/diagrams) from a rich design-patterns library, with the engine isolated in the skill and source-controlled in a dotfiles repo symlinked into `~/.claude/`.

**Architecture:** Master copy lives in a new `~/dotfiles` git repo under `claude/skills/html-dashboard/` and `claude/commands/dashboard.md`; a one-time idempotent `install.sh` symlinks both into `~/.claude/`. The engine (a generalized fork of `AlmaAPITK/docs/manual-qa/qa-server.py`) is a localhost server + `watch.sh`/`reply.sh` helpers, vendored Mermaid for diagrams, a shared `comms.js`/`base.css`, and a `patterns/` catalog of HTML scaffolds indexed by intent. Interactive pages spin up the server on demand (auto-incrementing port so it never fights an already-running server); static pages just open as files.

**Tech Stack:** Python 3.12 stdlib (`http.server`), bash, vanilla JS, Mermaid 11 (vendored), pytest for the engine smoke test.

**Spec:** `docs/superpowers/specs/2026-05-27-html-dashboard-skill-design.md`

**Reference source (read before Task 1):** `AlmaAPITK/docs/manual-qa/qa-server.py`, `qa-watch.sh`, `qa-reply.sh` — the proven originals this generalizes.

**Implementation note on `$DOTFILES`:** every task operates inside the dotfiles repo. Define once at the top of each shell step:
```bash
DOTFILES="$HOME/dotfiles"
SKILL="$DOTFILES/claude/skills/html-dashboard"
```

---

## Task 0: Bootstrap the dotfiles repo + skeleton

**Files:**
- Create: `~/dotfiles/.gitignore`
- Create: `~/dotfiles/README.md`
- Create dirs: `~/dotfiles/claude/skills/html-dashboard/{engine/assets,patterns,references,tests}`, `~/dotfiles/claude/commands`

- [ ] **Step 1: Create the repo and directory tree**

```bash
DOTFILES="$HOME/dotfiles"
mkdir -p "$DOTFILES/claude/skills/html-dashboard/engine/assets"
mkdir -p "$DOTFILES/claude/skills/html-dashboard/patterns"
mkdir -p "$DOTFILES/claude/skills/html-dashboard/references"
mkdir -p "$DOTFILES/claude/skills/html-dashboard/tests"
mkdir -p "$DOTFILES/claude/commands"
cd "$DOTFILES" && git init -q && git branch -M main
```

- [ ] **Step 2: Write `.gitignore` and `README.md`**

`~/dotfiles/.gitignore`:
```gitignore
__pycache__/
*.pyc
.pytest_cache/
*.bak.*
```

`~/dotfiles/README.md`:
```markdown
# dotfiles

Version-controlled config and Claude Code skills, symlinked into `~/.claude/`.

## Install

```bash
./claude/skills/html-dashboard/install.sh
```

## Contents

- `claude/skills/html-dashboard/` — the HTML Dashboard skill (see its `SKILL.md`).
- `claude/commands/dashboard.md` — the `/dashboard` slash command.
```

- [ ] **Step 3: Verify and commit**

Run:
```bash
cd "$HOME/dotfiles" && find claude -type d | sort
```
Expected: the five `html-dashboard` subdirs + `claude/commands` all listed.

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "chore: bootstrap dotfiles repo + html-dashboard skeleton"
```

---

## Task 1: Engine — generalized localhost server (TDD)

This is the load-bearing logic. Write the test first, watch it fail, then implement.

**Files:**
- Test: `~/dotfiles/claude/skills/html-dashboard/tests/test_engine.py`
- Create: `~/dotfiles/claude/skills/html-dashboard/engine/server.py`

- [ ] **Step 1: Write the failing test**

Write `tests/test_engine.py`:
```python
"""Smoke tests for the html-dashboard engine server."""
import importlib.util
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[1] / "engine" / "server.py"
_spec = importlib.util.spec_from_file_location("dash_server", ENGINE)
dash = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dash)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=2) as r:
        return r.status, json.loads(r.read().decode() or "null")


def _post(base, path, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(
        base + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        return r.status, json.loads(r.read().decode() or "null")


@pytest.fixture
def server(tmp_path):
    html = tmp_path / "demo-dash.html"
    html.write_text("<html><body>hello-dash</body></html>")
    cfg = dash.DashConfig(
        html_path=html,
        state_file=tmp_path / "state.json",
        replies_file=tmp_path / "replies.json",
        ping_file=tmp_path / "ping.json",
    )
    httpd, port = dash.serve(cfg, "127.0.0.1", 8800)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/health", timeout=0.5)
            break
        except urllib.error.URLError:
            time.sleep(0.02)
    yield base
    httpd.shutdown()


def test_redact_jwt_and_keys():
    payload = {
        "note": "token eyJhbGciOiJ.eyJzdWIiOiIx.SflKxwRJ here",
        "cfg": "ALMA_PROD_API_KEY=supersecretvalue123",
        "auth": "Authorization: apikey abcdef0123456789",
    }
    out = dash.redact(payload)
    assert "REDACTED-JWT" in out["note"]
    assert "eyJzdWIiOiIx" not in out["note"]
    assert "supersecretvalue123" not in out["cfg"]
    assert "REDACTED-KEY" in out["cfg"]
    assert "abcdef0123456789" not in out["auth"]


def test_serves_html(server):
    with urllib.request.urlopen(server + "/", timeout=2) as r:
        body = r.read().decode()
    assert "hello-dash" in body


def test_health(server):
    status, body = _get(server, "/health")
    assert status == 200 and body["ok"] is True


def test_state_roundtrip_and_redacts(server):
    _post(server, "/state", {"a": 1, "leak": "ALMA_SB_API_KEY=zzzzzzsecret"})
    status, body = _get(server, "/state")
    assert status == 200 and body["a"] == 1
    assert "zzzzzzsecret" not in json.dumps(body)


def test_reply_roundtrip(server):
    _, posted = _post(server, "/reply", {"testId": "c1", "level": "info", "text": "hi"})
    rid = posted["id"]
    _, all_replies = _get(server, "/replies")
    assert any(r["text"] == "hi" for r in all_replies)
    _, since = _get(server, "/replies/since/0")
    assert any(r["id"] == rid for r in since)


def test_ping_roundtrip(server):
    _post(server, "/ping", {"testId": "c2"})
    status, body = _get(server, "/ping")
    assert status == 200 and body["testId"] == "c2" and "ts" in body


def test_find_free_port_skips_taken():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    taken = s.getsockname()[1]
    try:
        chosen = dash.find_free_port("127.0.0.1", taken)
        assert chosen != taken
    finally:
        s.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard" && python3 -m pytest tests/test_engine.py -q
```
Expected: collection/exec error — `server.py` does not exist yet (`No such file or directory` on the spec load, or `AttributeError: module ... has no attribute 'DashConfig'`).

- [ ] **Step 3: Write the engine implementation**

Write `engine/server.py`:
```python
#!/usr/bin/env python3
"""Generalized localhost dashboard server for the html-dashboard skill.

Serves a generated dashboard HTML and mediates two-way state between the
browser (where the operator works) and Claude Code (which reads state via
Bash and posts replies the page renders inline). Generalized from
AlmaAPITK/docs/manual-qa/qa-server.py with neutral DASH_* env vars.

Endpoints:
  GET  /                     -> the dashboard HTML
  GET  /state                -> current state JSON
  POST /state                -> save state from the page (redacted)
  GET  /replies              -> all replies from Claude
  GET  /replies/since/<id>   -> replies with id > given id (polling)
  POST /reply                -> Claude posts a reply (redacted)
  POST /ping                 -> operator pings an element (redacted)
  GET  /ping                 -> last ping marker
  GET  /health               -> liveness probe
  GET  /assets/<name>        -> vendored static asset (mermaid/css/js)

Env:
  DASH_HTML    explicit HTML file to serve (overrides DASH_DIR scan)
  DASH_DIR     dir to scan for newest *-dash.html (default: cwd)
  DASH_PORT    preferred port (default 8765; auto-increments if taken)
  DASH_HOST    bind host (default 127.0.0.1)
  DASH_STATE_FILE / DASH_REPLIES_FILE / DASH_PING_FILE  override /tmp paths
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# --- Redaction (carried over from qa-server.py) ---------------------------
# Three base64-url segments joined by dots, starting with the "eyJ" header.
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_APIKEY_RE = re.compile(r"(?i)\bapikey\s+[A-Za-z0-9._-]{12,}")
_ENVKEY_RE = re.compile(r"(?i)(ALMA_[A-Z_]*API_KEY\s*[=:]\s*)\S+")


def redact(value):
    """Scrub JWTs and Alma API keys from any value before it is persisted."""
    if isinstance(value, str):
        value = _JWT_RE.sub("<REDACTED-JWT>", value)
        value = _APIKEY_RE.sub("apikey <REDACTED-KEY>", value)
        value = _ENVKEY_RE.sub(r"\1<REDACTED-KEY>", value)
        return value
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value


# --- Config + helpers ------------------------------------------------------
ASSETS_DIR = Path(__file__).parent / "assets"
_ASSET_TYPES = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".map": "application/json; charset=utf-8",
}


@dataclass
class DashConfig:
    html_path: Path
    state_file: Path
    replies_file: Path
    ping_file: Path


def resolve_html(dash_dir: Path, override: str | None) -> Path:
    """Serve the explicit DASH_HTML, else newest *-dash.html in dash_dir."""
    if override:
        return Path(override)
    candidates = sorted(dash_dir.glob("*-dash.html"))
    if candidates:
        return candidates[-1]
    raise SystemExit(
        f"no *-dash.html in {dash_dir}; set DASH_HTML to an explicit file"
    )


def config_from_env() -> DashConfig:
    dash_dir = Path(os.environ.get("DASH_DIR", os.getcwd()))
    html_path = resolve_html(dash_dir, os.environ.get("DASH_HTML"))
    stem = html_path.stem
    return DashConfig(
        html_path=html_path,
        state_file=Path(os.environ.get("DASH_STATE_FILE", f"/tmp/dash-{stem}-state.json")),
        replies_file=Path(os.environ.get("DASH_REPLIES_FILE", f"/tmp/dash-{stem}-replies.json")),
        ping_file=Path(os.environ.get("DASH_PING_FILE", f"/tmp/dash-{stem}-ping.json")),
    )


def find_free_port(host: str, start: int, span: int = 25) -> int:
    """Return the first free port at or after `start` (probes by binding)."""
    for port in range(start, start + span):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"no free port in [{start}, {start + span})")


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


# --- Request handler -------------------------------------------------------
def make_handler(cfg: DashConfig):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and isinstance(args[-1], str) and args[-1].startswith("2"):
                if "POST" not in (fmt % args):
                    return
            sys.stderr.write("[dash] %s - %s\n" % (self.address_string(), fmt % args))

        def _send_json(self, status, body):
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        def _send_bytes(self, status, data: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0"))
            return self.rfile.read(length) if length > 0 else b""

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                if not cfg.html_path.exists():
                    self._send_bytes(500, f"HTML missing: {cfg.html_path}".encode(), "text/plain")
                    return
                self._send_bytes(200, cfg.html_path.read_bytes(), "text/html; charset=utf-8")
                return
            if path.startswith("/assets/"):
                name = path[len("/assets/"):]
                asset = (ASSETS_DIR / name).resolve()
                if ASSETS_DIR.resolve() not in asset.parents or not asset.is_file():
                    self._send_bytes(404, b"asset not found", "text/plain")
                    return
                ctype = _ASSET_TYPES.get(asset.suffix, "application/octet-stream")
                self._send_bytes(200, asset.read_bytes(), ctype)
                return
            if path == "/state":
                self._send_json(200, read_json(cfg.state_file, {}))
                return
            if path == "/replies":
                self._send_json(200, read_json(cfg.replies_file, []))
                return
            if path.startswith("/replies/since/"):
                since = path.rsplit("/", 1)[-1]
                replies = read_json(cfg.replies_file, [])
                self._send_json(200, [r for r in replies if str(r.get("id", "")) > str(since)])
                return
            if path == "/ping":
                self._send_json(200, read_json(cfg.ping_file, {}))
                return
            if path == "/health":
                self._send_json(200, {"ok": True, "ts": time.time()})
                return
            self._send_bytes(404, f"not found: {path}".encode(), "text/plain")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            body = self._read_body()
            if path == "/state":
                try:
                    data = json.loads(body or b"{}")
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "invalid json"})
                    return
                write_json(cfg.state_file, redact(data))
                self._send_json(200, {"ok": True})
                return
            if path == "/ping":
                try:
                    data = json.loads(body or b"{}")
                except json.JSONDecodeError:
                    data = {}
                data = redact(data)
                data["ts"] = time.time()
                write_json(cfg.ping_file, data)
                self._send_json(200, {"ok": True, "ts": data["ts"]})
                return
            if path == "/reply":
                try:
                    reply = json.loads(body or b"{}")
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "invalid json"})
                    return
                reply = redact(reply)
                replies = read_json(cfg.replies_file, [])
                reply.setdefault("id", str(int(time.time() * 1000)))
                reply.setdefault("ts", time.time())
                replies.append(reply)
                write_json(cfg.replies_file, replies)
                self._send_json(200, {"ok": True, "id": reply["id"]})
                return
            self._send_bytes(404, f"not found: {path}".encode(), "text/plain")

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

    return Handler


def serve(cfg: DashConfig, host: str, port: int):
    """Build a ThreadingHTTPServer on the first free port >= `port`.

    Returns (httpd, actual_port). Caller runs serve_forever().
    """
    for f, default in [(cfg.state_file, {}), (cfg.replies_file, []), (cfg.ping_file, {})]:
        if not f.exists():
            write_json(f, default)
    actual = find_free_port(host, port)
    httpd = ThreadingHTTPServer((host, actual), make_handler(cfg))
    return httpd, actual


def main() -> None:
    cfg = config_from_env()
    host = os.environ.get("DASH_HOST", "127.0.0.1")
    port = int(os.environ.get("DASH_PORT", "8765"))
    httpd, actual = serve(cfg, host, port)
    sys.stderr.write(f"[dash] serving on http://{host}:{actual}\n")
    sys.stderr.write(f"[dash] HTML:    {cfg.html_path}\n")
    sys.stderr.write(f"[dash] state:   {cfg.state_file}\n")
    sys.stderr.write(f"[dash] replies: {cfg.replies_file}\n")
    sys.stderr.write(f"[dash] ping:    {cfg.ping_file}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[dash] shutting down\n")
        httpd.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard" && python3 -m pytest tests/test_engine.py -q
```
Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "feat(engine): generalized dashboard server + smoke tests"
```

---

## Task 2: Engine — watch + reply helper scripts

**Files:**
- Create: `~/dotfiles/claude/skills/html-dashboard/engine/watch.sh`
- Create: `~/dotfiles/claude/skills/html-dashboard/engine/reply.sh`

- [ ] **Step 1: Write `watch.sh`**

```bash
#!/usr/bin/env bash
# watch.sh — block until the operator pings an element in the browser, then
# print the ping payload and exit (re-invoking Claude). Generalized from
# AlmaAPITK qa-watch.sh.
#   Env: DASH_SERVER (default http://localhost:8765), DASH_POLL_SECS (default 2)
set -u
SERVER="${DASH_SERVER:-http://localhost:8765}"
POLL="${DASH_POLL_SECS:-2}"

ping_ts() {
  local body
  body="$(curl -s "$SERVER/ping" 2>/dev/null || true)"
  [[ -z "$body" ]] && { echo 0; return; }
  printf '%s' "$body" | jq -r '.ts // 0' 2>/dev/null || echo 0
}

baseline="$(ping_ts)"
echo "[dash-watch] watching $SERVER/ping (baseline ts=$baseline) — waiting for a ping…" >&2
while true; do
  cur="$(ping_ts)"
  if [[ "$cur" != "$baseline" && "$cur" != "0" ]]; then
    echo "[dash-watch] NEW PING:"
    curl -s "$SERVER/ping"
    echo
    exit 0
  fi
  sleep "$POLL"
done
```

- [ ] **Step 2: Write `reply.sh`**

```bash
#!/usr/bin/env bash
# reply.sh — post a reply that the dashboard renders inline. Generalized from
# AlmaAPITK qa-reply.sh.
#   Usage: reply.sh <elementId|-> <info|success|warn|error|question> "<text>"
#   Env:   DASH_SERVER (default http://localhost:8765)
set -euo pipefail
SERVER="${DASH_SERVER:-http://localhost:8765}"
if [[ $# -lt 3 ]]; then
  echo "usage: $0 <elementId|-> <level> <text>" >&2
  exit 2
fi
target="$1"; level="$2"; text="$3"
if [[ "$target" == "-" ]]; then
  payload="$(jq -n --arg level "$level" --arg text "$text" '{level:$level, text:$text}')"
else
  payload="$(jq -n --arg id "$target" --arg level "$level" --arg text "$text" \
    '{testId:$id, level:$level, text:$text}')"
fi
printf '%s' "$payload" | curl -sf -X POST "$SERVER/reply" \
  -H 'Content-Type: application/json' --data-binary @- \
  || { echo "reply failed — is the dashboard server running on $SERVER?" >&2; exit 1; }
echo
echo "posted reply target=$target level=$level"
```

- [ ] **Step 3: Make executable and syntax-check**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard/engine"
chmod +x watch.sh reply.sh
bash -n watch.sh && bash -n reply.sh && echo "syntax OK"
```
Expected: `syntax OK`.

- [ ] **Step 4: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "feat(engine): watch.sh + reply.sh comms helpers"
```

---

## Task 3: Engine assets — comms.js, base.css, vendored Mermaid

**Files:**
- Create: `~/dotfiles/claude/skills/html-dashboard/engine/assets/comms.js`
- Create: `~/dotfiles/claude/skills/html-dashboard/engine/assets/base.css`
- Create: `~/dotfiles/claude/skills/html-dashboard/engine/assets/mermaid.min.js` (downloaded)

- [ ] **Step 1: Write `assets/comms.js`** (the reusable browser↔Claude wiring)

```javascript
/* comms.js — shared browser<->Claude wiring for interactive dashboards.
 * Served by the engine at /assets/comms.js. Patterns include it only in
 * interactive mode. Exposes window.Dash. No-ops gracefully with no server
 * (falls back to localStorage for state). */
(function () {
  const KEY = "dash-state-" + location.pathname;
  const Dash = {
    async loadState() {
      try {
        const r = await fetch("/state", { cache: "no-store" });
        if (r.ok) return await r.json();
      } catch (e) {}
      try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; }
    },
    async saveState(state) {
      try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
      try {
        await fetch("/state", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state),
        });
      } catch (e) {}
    },
    async ping(elementId, payload) {
      const body = Object.assign({ testId: elementId }, payload || {});
      try {
        await fetch("/ping", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        return true;
      } catch (e) { return false; }
    },
    /* Poll for new replies; calls cb(reply) for each. Tracks last-seen id. */
    onReplies(cb, intervalMs) {
      let last = 0;
      const tick = async () => {
        try {
          const r = await fetch("/replies/since/" + last, { cache: "no-store" });
          if (r.ok) {
            const items = await r.json();
            for (const reply of items) {
              if (Number(reply.id) > Number(last)) last = reply.id;
              cb(reply);
            }
          }
        } catch (e) {}
      };
      tick();
      return setInterval(tick, intervalMs || 2500);
    },
  };
  window.Dash = Dash;
})();
```

- [ ] **Step 2: Write `assets/base.css`** (shared visual style)

```css
/* base.css — shared styling for html-dashboard patterns. Served at
 * /assets/base.css for interactive pages; inlined for standalone static pages. */
:root {
  --bg: #0f1116; --panel: #181b22; --panel-2: #1f242d; --line: #2b313c;
  --ink: #e6e9ef; --muted: #9aa4b2; --accent: #6ea8fe; --accent-2: #7ee0c0;
  --info: #6ea8fe; --success: #54d18c; --warn: #f0c36d; --error: #f08a8a;
  --radius: 12px; --gap: 16px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --mono: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: var(--font); line-height: 1.5; padding: 24px;
}
h1, h2, h3 { line-height: 1.25; margin: 0 0 .4em; }
header.dash-head { margin-bottom: 24px; }
header.dash-head .sub { color: var(--muted); font-size: 14px; }
.grid { display: grid; gap: var(--gap); grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.card {
  background: var(--panel); border: 1px solid var(--line);
  border-radius: var(--radius); padding: 16px;
}
.card h3 { font-size: 15px; }
.muted { color: var(--muted); }
code, pre { font-family: var(--mono); }
pre { background: var(--panel-2); padding: 12px; border-radius: 8px; overflow: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 600; cursor: pointer; user-select: none; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.badge.info { background: rgba(110,168,254,.15); color: var(--info); }
.badge.success { background: rgba(84,209,140,.15); color: var(--success); }
.badge.warn { background: rgba(240,195,109,.15); color: var(--warn); }
.badge.error { background: rgba(240,138,138,.15); color: var(--error); }
.reply { border-left: 3px solid var(--line); padding: 6px 10px; margin: 8px 0; background: var(--panel-2); border-radius: 6px; }
.reply.info { border-color: var(--info); } .reply.success { border-color: var(--success); }
.reply.warn { border-color: var(--warn); } .reply.error { border-color: var(--error); }
.reply.question { border-color: var(--accent-2); }
button { font: inherit; color: var(--ink); background: var(--panel-2); border: 1px solid var(--line); border-radius: 8px; padding: 6px 12px; cursor: pointer; }
button:hover { border-color: var(--accent); }
.metric { font-size: 34px; font-weight: 700; }
```

- [ ] **Step 3: Vendor Mermaid (pin v11)**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard/engine/assets"
curl -fsSL https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js -o mermaid.min.js \
  && echo "vendored $(wc -c < mermaid.min.js) bytes"
```
Expected: a multi-hundred-KB file. **If offline / curl fails:** create a one-line stub `mermaid.min.js` containing only the comment `/* vendored Mermaid missing — patterns fall back to CDN; rerun curl when online */` and continue; diagram patterns (Task 4) already include a CDN fallback `<script>`.

- [ ] **Step 4: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "feat(engine): comms.js, base.css, vendored Mermaid asset"
```

---

## Task 4: Pattern library — INDEX + exemplar patterns

Two complete exemplars are given in full: one **static diagram** (flowchart) and one **interactive dashboard** (status-cards). They define the two house styles every other pattern follows.

**Files:**
- Create: `~/dotfiles/claude/skills/html-dashboard/patterns/INDEX.md`
- Create: `~/dotfiles/claude/skills/html-dashboard/patterns/diagram-flowchart.html`
- Create: `~/dotfiles/claude/skills/html-dashboard/patterns/dashboard-status-cards.html`

- [ ] **Step 1: Write `patterns/INDEX.md`**

```markdown
# Pattern library index

Each pattern is a self-contained HTML scaffold with `<!-- SLOT: ... -->`
markers and a header comment. To use one: copy it to the target repo as
`<topic>-dash.html` (interactive) or `<topic>.html` (static), fill the slots,
and follow `references/building-html.md`.

| Pattern file | Category | Mode | When to use |
|--------------|----------|------|-------------|
| `diagram-flowchart.html` | Diagram | static | Processes, request lifecycles ("how does X work?") |
| `diagram-sequence.html` | Diagram | static | Ordered calls between actors (client↔server↔Alma) |
| `diagram-architecture.html` | Diagram | static | Module/component relationships |
| `diagram-state.html` | Diagram | static | Lifecycle / state machines |
| `dashboard-status-cards.html` | Dashboard | interactive | Track a multi-step workflow; two-way Claude link |
| `dashboard-progress.html` | Dashboard | static/interactive | Progress + timeline of a rollout |
| `data-table.html` | Data | static | Sortable/filterable tabular results |
| `data-metrics.html` | Data | static | Headline KPI tiles |
| `data-chart.html` | Data | static | Simple bar/line trend |
| `compare-side-by-side.html` | Comparison | static | Option A vs B, before/after |
| `compare-decision-matrix.html` | Comparison | static | Weighted option scoring |
| `narrative-stepper.html` | Narrative | static | Guided multi-step explanation |

Diagram patterns load vendored Mermaid from `/assets/mermaid.min.js` when
served by the engine, with a CDN `<script>` fallback for standalone files.
```

- [ ] **Step 2: Write `patterns/diagram-flowchart.html`** (static diagram exemplar)

```html
<!doctype html>
<!-- PATTERN: diagram-flowchart (static)
     WHEN: explain a process or request lifecycle ("how does the API work?").
     SLOTS: TITLE, SUBTITLE, MERMAID (a flowchart definition).
     MODE: static — open as a file. Loads vendored Mermaid via the engine if
           served, else falls back to the CDN script below. -->
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title><!-- SLOT: TITLE -->Flowchart</title>
  <style>
    :root { --bg:#0f1116; --ink:#e6e9ef; --muted:#9aa4b2; --line:#2b313c; }
    body { margin:0; background:var(--bg); color:var(--ink); padding:24px;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
    h1 { margin:0 0 4px; } .sub { color:var(--muted); margin-bottom:24px; }
    .diagram { background:#181b22; border:1px solid var(--line); border-radius:12px; padding:20px; }
  </style>
</head>
<body>
  <h1><!-- SLOT: TITLE -->Flowchart</h1>
  <div class="sub"><!-- SLOT: SUBTITLE -->What this diagram shows.</div>
  <div class="diagram">
    <pre class="mermaid">
<!-- SLOT: MERMAID -->
flowchart TD
  A[Start] --> B{Decision}
  B -->|yes| C[Do thing]
  B -->|no| D[Other thing]
  C --> E[End]
  D --> E
    </pre>
  </div>
  <script>
    // Prefer the engine-vendored asset; fall back to CDN for standalone files.
    function boot() { window.mermaid && window.mermaid.initialize({ startOnLoad: true, theme: "dark" }); }
    var s = document.createElement("script");
    s.src = "/assets/mermaid.min.js";
    s.onload = boot;
    s.onerror = function () {
      var c = document.createElement("script");
      c.src = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js";
      c.onload = boot; document.head.appendChild(c);
    };
    document.head.appendChild(s);
  </script>
</body>
</html>
```

- [ ] **Step 3: Write `patterns/dashboard-status-cards.html`** (interactive exemplar)

```html
<!doctype html>
<!-- PATTERN: dashboard-status-cards (interactive)
     WHEN: track a multi-step workflow with a live browser<->Claude link.
     SLOTS: TITLE, SUBTITLE, CARDS (repeat the .card block per step).
     MODE: interactive — requires the engine server. Each card has a status
           select, a notes box, and a "Ping Claude" button; Claude's replies
           render inline via /assets/comms.js. -->
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title><!-- SLOT: TITLE -->Workflow dashboard</title>
  <link rel="stylesheet" href="/assets/base.css" />
</head>
<body>
  <header class="dash-head">
    <h1><!-- SLOT: TITLE -->Workflow dashboard</h1>
    <div class="sub"><!-- SLOT: SUBTITLE -->Live status; ping Claude on any card.</div>
  </header>
  <div class="grid" id="cards">
    <!-- SLOT: CARDS — duplicate this block per step; give each a unique data-id -->
    <section class="card" data-id="step-1">
      <h3>Step 1 title</h3>
      <p class="muted">What this step verifies.</p>
      <label>Status
        <select class="status">
          <option value="todo">To do</option>
          <option value="doing">In progress</option>
          <option value="done">Done</option>
          <option value="blocked">Blocked</option>
        </select>
      </label>
      <textarea class="notes" rows="2" placeholder="notes…" style="width:100%;margin-top:8px"></textarea>
      <div style="margin-top:8px"><button class="ping">💬 Ping Claude</button></div>
      <div class="replies"></div>
    </section>
  </div>
  <script src="/assets/comms.js"></script>
  <script>
    const cards = [...document.querySelectorAll(".card")];
    function collect() {
      const s = {};
      cards.forEach(c => {
        s[c.dataset.id] = { status: c.querySelector(".status").value, notes: c.querySelector(".notes").value };
      });
      return s;
    }
    async function init() {
      const st = await Dash.loadState();
      cards.forEach(c => {
        const v = st[c.dataset.id]; if (!v) return;
        c.querySelector(".status").value = v.status || "todo";
        c.querySelector(".notes").value = v.notes || "";
      });
    }
    cards.forEach(c => {
      c.querySelector(".status").addEventListener("change", () => Dash.saveState(collect()));
      c.querySelector(".notes").addEventListener("input", () => Dash.saveState(collect()));
      c.querySelector(".ping").addEventListener("click", () => {
        const v = collect()[c.dataset.id];
        Dash.ping(c.dataset.id, v);
        c.querySelector(".ping").textContent = "💬 Pinged — waiting…";
      });
    });
    Dash.onReplies(reply => {
      const id = reply.testId;
      const host = id ? document.querySelector(`.card[data-id="${id}"] .replies`)
                      : document.querySelector(".replies");
      if (!host) return;
      const div = document.createElement("div");
      div.className = "reply " + (reply.level || "info");
      div.textContent = reply.text;
      host.appendChild(div);
    });
    init();
  </script>
</body>
</html>
```

- [ ] **Step 4: Verify the exemplars render via the engine**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard"
cp patterns/dashboard-status-cards.html /tmp/smoke-dash.html
DASH_HTML=/tmp/smoke-dash.html DASH_PORT=8790 python3 engine/server.py &
SRV=$!; sleep 1
curl -sf http://127.0.0.1:8790/ | grep -q "Workflow dashboard" && echo "HTML OK"
curl -sf http://127.0.0.1:8790/assets/comms.js | grep -q "window.Dash" && echo "comms OK"
curl -sf http://127.0.0.1:8790/assets/base.css | grep -q ".card" && echo "css OK"
kill $SRV
```
Expected: `HTML OK`, `comms OK`, `css OK`. (Port 8790 avoids the manual-qa server on 8765.)

- [ ] **Step 5: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "feat(patterns): INDEX + flowchart + status-cards exemplars"
```

---

## Task 5: Pattern library — remaining patterns

Each file below follows one of the two exemplars from Task 4. Create them with the structure specified. **Diagram patterns** are byte-for-byte the `diagram-flowchart.html` exemplar with only the `<title>`, header comment `PATTERN`/`WHEN`, and the `MERMAID` slot body changed to the diagram source shown. **Data/comparison/narrative patterns** are static: copy the `<head>`/`base.css`-inline approach from `diagram-flowchart.html` (self-contained `<style>` is fine, or link `/assets/base.css` if interactive), with the body markup shown.

**Files (all under `~/dotfiles/claude/skills/html-dashboard/patterns/`):**

- [ ] **Step 1: `diagram-sequence.html`** — clone the flowchart exemplar; set MERMAID slot to:
```
sequenceDiagram
  participant Caller
  participant Toolkit
  participant Alma
  Caller->>Toolkit: method(args)
  Toolkit->>Alma: GET /almaws/v1/...
  Alma-->>Toolkit: 200 + payload
  Toolkit-->>Caller: AlmaResponse
```

- [ ] **Step 2: `diagram-architecture.html`** — clone the flowchart exemplar; set MERMAID slot to:
```
flowchart LR
  subgraph Client
    A[AlmaAPIClient]
  end
  subgraph Domains
    B[Acquisitions]; C[Users]; D[Bibs]
  end
  A --> B & C & D
  B & C & D --> E[(Alma REST API)]
```

- [ ] **Step 3: `diagram-state.html`** — clone the flowchart exemplar; set MERMAID slot to:
```
stateDiagram-v2
  [*] --> defined
  defined --> impl_running
  impl_running --> testing
  testing --> merged
  testing --> aborted
  merged --> [*]
  aborted --> [*]
```

- [ ] **Step 4: `data-table.html`** — static, self-contained `<style>` (mirror flowchart head). Body:
```html
<h1><!-- SLOT: TITLE -->Results</h1>
<div class="sub"><!-- SLOT: SUBTITLE --></div>
<input id="filter" placeholder="filter…" style="margin-bottom:12px;padding:6px 10px" />
<table id="t">
  <thead><tr><!-- SLOT: HEADERS --><th>Col A</th><th>Col B</th></tr></thead>
  <tbody><!-- SLOT: ROWS --><tr><td>a</td><td>b</td></tr></tbody>
</table>
<script>
  // click-to-sort + live filter (no deps)
  const t = document.getElementById("t");
  t.querySelectorAll("th").forEach((th, i) => th.addEventListener("click", () => {
    const rows = [...t.tBodies[0].rows];
    const asc = th.dataset.asc !== "true"; th.dataset.asc = asc;
    rows.sort((a, b) => a.cells[i].textContent.localeCompare(b.cells[i].textContent, undefined, {numeric:true}) * (asc?1:-1));
    rows.forEach(r => t.tBodies[0].appendChild(r));
  }));
  document.getElementById("filter").addEventListener("input", e => {
    const q = e.target.value.toLowerCase();
    [...t.tBodies[0].rows].forEach(r => r.style.display = r.textContent.toLowerCase().includes(q) ? "" : "none");
  });
</script>
```
Include the same `<style>` block as `diagram-flowchart.html` plus the `table`/`th`/`td` rules from `base.css`.

- [ ] **Step 5: `data-metrics.html`** — static. Body is a `.grid` of metric tiles:
```html
<h1><!-- SLOT: TITLE -->Key metrics</h1>
<div class="grid"><!-- SLOT: TILES — repeat per metric -->
  <div class="card"><div class="muted">Metric label</div><div class="metric">0</div></div>
</div>
```
Include the `base.css` `:root`, `body`, `.grid`, `.card`, `.muted`, `.metric` rules inline.

- [ ] **Step 6: `data-chart.html`** — static, dependency-free inline SVG bar chart:
```html
<h1><!-- SLOT: TITLE -->Trend</h1>
<svg id="chart" width="640" height="240" role="img"></svg>
<script>
  // SLOT: DATA — array of {label, value}
  const data = [{label:"A",value:3},{label:"B",value:7},{label:"C",value:5}];
  const svg = document.getElementById("chart"), W=640,H=240,P=30;
  const max = Math.max(...data.map(d=>d.value),1), bw = (W-2*P)/data.length*0.7;
  data.forEach((d,i)=>{
    const x = P + i*(W-2*P)/data.length, h=(H-2*P)*d.value/max;
    const r=document.createElementNS("http://www.w3.org/2000/svg","rect");
    r.setAttribute("x",x); r.setAttribute("y",H-P-h); r.setAttribute("width",bw); r.setAttribute("height",h); r.setAttribute("fill","#6ea8fe");
    svg.appendChild(r);
  });
</script>
```
Include the flowchart `<style>` head; add `svg{background:#181b22;border-radius:12px}`.

- [ ] **Step 7: `compare-side-by-side.html`** — static two-column `.grid` (force 2 cols):
```html
<h1><!-- SLOT: TITLE -->A vs B</h1>
<div class="grid" style="grid-template-columns:1fr 1fr">
  <div class="card"><h3><!-- SLOT: LEFT_TITLE -->Option A</h3><div><!-- SLOT: LEFT_BODY --></div></div>
  <div class="card"><h3><!-- SLOT: RIGHT_TITLE -->Option B</h3><div><!-- SLOT: RIGHT_BODY --></div></div>
</div>
```
Inline the `base.css` `:root`/`body`/`.grid`/`.card` rules.

- [ ] **Step 8: `compare-decision-matrix.html`** — static table; reuse the `data-table.html` `<style>`/table rules but no JS. Body:
```html
<h1><!-- SLOT: TITLE -->Decision matrix</h1>
<table>
  <thead><tr><th>Criterion</th><th>Weight</th><th>Option A</th><th>Option B</th></tr></thead>
  <tbody><!-- SLOT: ROWS --><tr><td>Criterion 1</td><td>3</td><td>4</td><td>2</td></tr></tbody>
  <tfoot><tr><th>Weighted total</th><th></th><th><!-- SLOT: TOTAL_A --></th><th><!-- SLOT: TOTAL_B --></th></tr></tfoot>
</table>
```

- [ ] **Step 9: `narrative-stepper.html`** — static ordered steps:
```html
<h1><!-- SLOT: TITLE -->Walkthrough</h1>
<ol style="max-width:720px"><!-- SLOT: STEPS — repeat <li> per step -->
  <li class="card" style="margin-bottom:12px"><h3>Step title</h3><p class="muted">Explanation.</p></li>
</ol>
```
Inline the `base.css` `:root`/`body`/`.card`/`.muted` rules.

- [ ] **Step 10: `dashboard-progress.html`** — static-or-interactive. Copy `dashboard-status-cards.html` but replace the cards grid with a vertical timeline list; keep the `/assets/base.css` link and optional `comms.js` block (a progress dashboard may be read-only — include the `comms.js` script but no ping buttons). Body:
```html
<header class="dash-head"><h1><!-- SLOT: TITLE -->Rollout progress</h1>
  <div class="sub"><!-- SLOT: SUBTITLE --></div></header>
<ol id="timeline"><!-- SLOT: STEPS -->
  <li class="card" data-id="s1"><span class="badge info">in progress</span> <b>Phase 1</b>
    <p class="muted">detail</p></li>
</ol>
```

- [ ] **Step 11: Validate all pattern files are well-formed**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard/patterns"
for f in *.html; do
  python3 - "$f" <<'PY'
import sys, html.parser
class P(html.parser.HTMLParser):
    pass
P().feed(open(sys.argv[1]).read())
print("ok", sys.argv[1])
PY
done
ls *.html | wc -l   # expect 12
```
Expected: `ok <file>` for each, and a count of `12`.

- [ ] **Step 12: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "feat(patterns): diagrams, data, comparison, narrative, progress"
```

---

## Task 6: SKILL.md — triggers, modes, workflow

**Files:**
- Create: `~/dotfiles/claude/skills/html-dashboard/SKILL.md`

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: html-dashboard
description: Generate visually compelling HTML — interactive dashboards with a live browser↔Claude link, or static reports/diagrams — from a pattern library. Use when the user wants to track a multi-step or long-running workflow, monitor live progress, understand a flow or architecture ("how does X work?"), compare options or review a decision, or present complex/tabular data clearly. Triggers: dashboard, diagram, flowchart, visualize, "show me", "lay this out", track progress, compare options.
---

# HTML Dashboard

Turn an idea into a styled HTML artifact from a library of patterns. Two modes:

- **Static** — pick a pattern, fill it, write the file into the current repo,
  open it. No server. For reports, diagrams, comparisons, one-shot data views.
- **Interactive** — same, plus a localhost server giving a live two-way
  browser↔Claude link (the operator pings; you reply inline).

## When to suggest it

Offer a dashboard/diagram (don't wait to be asked) when the user wants to:
track a multi-step or long workflow, monitor live progress, understand a flow
or architecture, compare options, or present complex/tabular data. **Suggest,
then let the user accept.** Never start a server unprompted.

## Choosing a pattern

Read `patterns/INDEX.md` and match intent → pattern. The catalog covers
diagrams (flowchart/sequence/architecture/state, via Mermaid), dashboards
(status-cards/progress), data (table/metrics/chart), comparison
(side-by-side/decision-matrix), and narrative (stepper).

## Workflow — static

1. Copy the chosen pattern to the repo as `<topic>.html` (default location:
   `docs/dashboards/`, or the dir that fits — see `references/building-html.md`).
2. Fill every `<!-- SLOT: ... -->`. Remove the comms `<script>` if present.
3. Open it (`python3 -m http.server` in that dir, or a `file://` path).
4. Offer to commit it (it's a per-repo, committable artifact).

## Workflow — interactive

1. Copy the chosen interactive pattern to the repo as `<topic>-dash.html`
   (the `-dash.html` suffix is what the server auto-discovers).
2. Fill slots; keep the `/assets/comms.js` + `/assets/base.css` links.
3. Start the server (it auto-picks a free port if 8765 is taken):
   ```bash
   DASH_DIR=docs/dashboards DASH_PORT=8765 python3 ~/.claude/skills/html-dashboard/engine/server.py
   ```
   Tell the user the URL printed on stderr.
4. Run the watcher to receive the operator's pings:
   ```bash
   DASH_SERVER=http://localhost:<port> bash ~/.claude/skills/html-dashboard/engine/watch.sh
   ```
5. On a ping, act, then reply inline:
   ```bash
   DASH_SERVER=http://localhost:<port> bash ~/.claude/skills/html-dashboard/engine/reply.sh <elementId|-> <info|success|warn|error|question> "text"
   ```
   Relaunch the watcher for the next ping.

## Safety

- The server redacts JWTs and Alma API keys from every POST before persisting.
- Never write real operator-supplied identifiers into committed HTML (R9-style
  discipline). The redactor is a safety net, not a license.
- Localhost-bind only.

## Adding a pattern

Drop a new `<name>.html` in `patterns/` (follow an existing exemplar) and add a
row to `patterns/INDEX.md`. No code changes needed.
```

- [ ] **Step 2: Verify frontmatter parses**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard"
python3 - <<'PY'
import re
t = open("SKILL.md").read()
m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
assert m, "missing frontmatter"
assert "name: html-dashboard" in m.group(1)
assert "description:" in m.group(1)
print("frontmatter OK")
PY
```
Expected: `frontmatter OK`.

- [ ] **Step 3: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "feat(skill): SKILL.md (triggers, modes, workflow)"
```

---

## Task 7: references/building-html.md

**Files:**
- Create: `~/dotfiles/claude/skills/html-dashboard/references/building-html.md`

- [ ] **Step 1: Write the reference**

```markdown
# Building HTML for this skill

## Style

- Default to the dark theme in `engine/assets/base.css`. Interactive pages
  `<link>` it from `/assets/base.css`; standalone static pages inline the rules
  they use (keeps the file portable).
- Keep it clean and information-dense. Use the `frontend-design` skill when a
  page needs more than the base patterns give.

## File naming & location

- Interactive dashboards: `<topic>-dash.html` (the `-dash.html` suffix is what
  the engine auto-discovers via `DASH_DIR`).
- Static pages: `<topic>.html`.
- Default repo location `docs/dashboards/`; use the dir that fits the repo's
  conventions (e.g. an existing `docs/manual-qa/`-style home).

## The comms wiring (interactive only)

Include exactly these two lines and the `window.Dash` API from
`/assets/comms.js`:
```html
<link rel="stylesheet" href="/assets/base.css" />
<script src="/assets/comms.js"></script>
```
`Dash.loadState()`, `Dash.saveState(obj)`, `Dash.ping(id, payload)`,
`Dash.onReplies(cb, intervalMs)`. State falls back to `localStorage` when no
server is running, so the page degrades gracefully.

## Diagrams

Diagram patterns load `/assets/mermaid.min.js` (vendored) and fall back to the
Mermaid CDN for standalone files. Write the diagram source in the `MERMAID`
slot; Mermaid supports flowchart, sequenceDiagram, stateDiagram-v2, classDiagram,
erDiagram, gantt.

## Security (R9)

Never put real identifiers (user IDs, MMS IDs, vendor codes, emails) in a
committed HTML file. Use synthetic placeholders. The server redacts JWTs and
`ALMA_*_API_KEY` / `apikey …` values from posted state as a safety net.
```

- [ ] **Step 2: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "docs(skill): references/building-html.md"
```

---

## Task 8: The /dashboard slash command

**Files:**
- Create: `~/dotfiles/claude/commands/dashboard.md`

- [ ] **Step 1: Write the command**

```markdown
---
description: Create or serve an HTML dashboard/diagram via the html-dashboard skill
argument-hint: [what to visualize]
---

Invoke the `html-dashboard` skill to build a dashboard, report, or diagram for
the following request, choosing a pattern from its library and the right mode
(static vs interactive):

$ARGUMENTS

If the request is empty, ask what to visualize and suggest fitting patterns
from `patterns/INDEX.md`.
```

- [ ] **Step 2: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "feat(command): /dashboard alias routes into the skill"
```

---

## Task 9: install.sh — symlink into ~/.claude, then run + verify

**Files:**
- Create: `~/dotfiles/claude/skills/html-dashboard/install.sh`

- [ ] **Step 1: Write `install.sh`**

```bash
#!/usr/bin/env bash
# install.sh — symlink the html-dashboard skill + /dashboard command into
# ~/.claude. Idempotent: re-running re-points the symlinks; any pre-existing
# real file is backed up to <name>.bak.<epoch> first.
set -euo pipefail

# dotfiles root = three levels up from this script (.../claude/skills/html-dashboard/install.sh)
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
DOTFILES_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"

mkdir -p "$CLAUDE_DIR/skills" "$CLAUDE_DIR/commands"

link() {
  local src="$1" dest="$2"
  if [ -L "$dest" ]; then
    rm "$dest"
  elif [ -e "$dest" ]; then
    mv "$dest" "$dest.bak.$(date +%s)"
    echo "backed up existing $dest"
  fi
  ln -s "$src" "$dest"
  echo "linked $dest -> $src"
}

link "$SKILL_DIR" "$CLAUDE_DIR/skills/html-dashboard"
link "$DOTFILES_ROOT/claude/commands/dashboard.md" "$CLAUDE_DIR/commands/dashboard.md"
echo "done."
```

- [ ] **Step 2: Make executable, run it, verify symlinks**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard"
chmod +x install.sh
bash -n install.sh && ./install.sh
echo "--- verify ---"
readlink ~/.claude/skills/html-dashboard
readlink ~/.claude/commands/dashboard.md
test -f ~/.claude/skills/html-dashboard/SKILL.md && echo "SKILL.md reachable through symlink"
```
Expected: both `readlink`s print paths under `~/dotfiles/...`, and `SKILL.md reachable through symlink`.

- [ ] **Step 3: Final engine test through the symlinked path**

Run:
```bash
cd ~/.claude/skills/html-dashboard && python3 -m pytest tests/test_engine.py -q
```
Expected: `7 passed`.

- [ ] **Step 4: Commit**

```bash
cd "$HOME/dotfiles"
git add -A
git commit -q -m "feat(install): idempotent symlink installer; installed"
```

---

## Task 10: Final verification

- [ ] **Step 1: Full test + structure check**

Run:
```bash
cd "$HOME/dotfiles/claude/skills/html-dashboard"
python3 -m pytest tests/test_engine.py -q
echo "patterns: $(ls patterns/*.html | wc -l) (expect 12)"
test -L ~/.claude/skills/html-dashboard && echo "skill symlink present"
test -L ~/.claude/commands/dashboard.md && echo "command symlink present"
git -C "$HOME/dotfiles" status --short | head
```
Expected: `7 passed`; `patterns: 12`; both symlink lines; clean (or only untracked-pycache) git status.

- [ ] **Step 2: Note for the operator**

The skill becomes available to Claude on the **next** session (skills are
discovered at session start). Confirm by checking `html-dashboard` appears in
the available-skills list and `/dashboard` is offered.

---

## Self-review notes (author)

- **Spec coverage:** §3 layout → Tasks 0,9; §4 modes → SKILL.md (Task 6); §5
  pattern library → Tasks 4–5 (all 12 catalog entries); §6 Mermaid vendoring →
  Task 3 (+ CDN fallback in diagram patterns); §7 engine/data-flow/ports →
  Task 1 (`find_free_port`, per-stem `/tmp` keying, DASH_* env); §8 bootstrap →
  Tasks 0,3,9; §9 testing → Task 1 test file; §10 security → redaction in
  Task 1 + R9 notes in Tasks 6,7; §11 triggers → SKILL.md description. All
  covered.
- **Engine isolation:** nothing is copied into consumer repos — only generated
  HTML (created at use time, not in this plan) lands per-repo.
- **Type consistency:** `DashConfig`, `redact`, `serve`, `find_free_port`,
  `make_handler`, `resolve_html`, `config_from_env` names match across the test
  (Task 1 Step 1) and implementation (Step 3). Endpoints used by `comms.js`
  (`/state`, `/ping`, `/reply`, `/replies/since/<id>`) match the handler.
- **Out of scope:** manual-qa migration, auth, non-localhost — per spec §12.
```
