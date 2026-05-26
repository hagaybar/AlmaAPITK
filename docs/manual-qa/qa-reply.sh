#!/usr/bin/env bash
# qa-reply.sh — post a reply that the HTML renders inline in a test card.
#
# Posts to the running qa-server.py via its /reply endpoint. The server decides
# which on-disk replies file to append to based on whichever QA page it is
# serving, so this script never needs to know the file path.
#
# Usage:
#   qa-reply.sh <testId|->  <level>  "<message text>"
#
#   testId   id of the test card (e.g. preflight-1, core-3) or "-" for global
#   level    info | success | warn | error | question
#   message  the body text; supports `code` and **bold** and \n linebreaks
#
# Env:
#   QA_SERVER   base URL of the server (default http://localhost:8765)
#
# Examples:
#   qa-reply.sh core-2 question "Did the card shake when you clicked the backdrop?"
#   qa-reply.sh core-4 success "Confirmed the auto GET fired at promote — #50 verified."
#   qa-reply.sh - info "Pushing a small tweak, give me 30s."
set -euo pipefail

SERVER="${QA_SERVER:-http://localhost:8765}"

if [[ $# -lt 3 ]]; then
  echo "usage: $0 <testId|-> <level> <text>" >&2
  exit 2
fi

test_id="$1"
level="$2"
text="$3"

if [[ "$test_id" == "-" ]]; then
  payload="$(jq -n --arg level "$level" --arg text "$text" \
    '{level: $level, text: $text}')"
else
  payload="$(jq -n --arg testId "$test_id" --arg level "$level" --arg text "$text" \
    '{testId: $testId, level: $level, text: $text}')"
fi

printf '%s' "$payload" | curl -sf -X POST "$SERVER/reply" \
  -H 'Content-Type: application/json' --data-binary @- \
  || { echo "reply failed — is qa-server.py running on $SERVER?" >&2; exit 1; }

echo
echo "posted reply testId=$test_id level=$level"
