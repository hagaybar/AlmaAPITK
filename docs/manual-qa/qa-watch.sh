#!/usr/bin/env bash
# qa-watch.sh — block until the tester clicks "Ping Claude" on a card, then
# print the ping payload and exit.
#
# Claude runs this in the background. When the tester pings a card, this exits
# with the ping JSON (test id + status + notes), which re-invokes Claude. Claude
# reads it, replies via qa-reply.sh, and relaunches this watcher for the next
# ping. That's the terminal<->browser mirror in the "browser pings me" direction.
#
# Env:
#   QA_SERVER     base URL (default http://localhost:8765)
#   QA_POLL_SECS  poll interval in seconds (default 2)
set -u

SERVER="${QA_SERVER:-http://localhost:8765}"
POLL="${QA_POLL_SECS:-2}"

ping_ts() {
  local body
  body="$(curl -s "$SERVER/ping" 2>/dev/null || true)"
  [[ -z "$body" ]] && { echo 0; return; }
  printf '%s' "$body" | jq -r '.ts // 0' 2>/dev/null || echo 0
}

baseline="$(ping_ts)"
echo "[qa-watch] watching $SERVER/ping (baseline ts=$baseline) — waiting for a card ping…" >&2

while true; do
  cur="$(ping_ts)"
  if [[ "$cur" != "$baseline" && "$cur" != "0" ]]; then
    echo "[qa-watch] NEW PING:"
    curl -s "$SERVER/ping"
    echo
    exit 0
  fi
  sleep "$POLL"
done
