# Manual-QA / collaboration dashboard

A tiny localhost tool to **organize the consumer-safety testing rollout** and
**talk to Claude from the browser**. Pattern borrowed from `primo_maps`.

## What it is

- **A dashboard** (`*-qa.html`) — cards for each step of the rollout. Set a
  status, jot notes, and hit **💬 Ping Claude** on any card.
- **A tiny server** (`qa-server.py`) — serves the newest `*-qa.html` and
  mediates state/replies/pings between the browser and Claude. Localhost only.
- **Two helper scripts** Claude uses: `qa-watch.sh` (waits for a ping) and
  `qa-reply.sh` (posts a reply that renders inline in the card).

## You (in the browser)

```bash
# from the repo root (this environment has python3, not `python`)
python3 docs/manual-qa/qa-server.py       # serves the newest *-qa.html on :8765
```
Open <http://localhost:8765/>. Work the cards; click **Ping Claude** when you
want me to act on one. My replies appear inline in that card.

Without the server the page still works (statuses/notes saved to
`localStorage`) — you just don't get the live link.

## Claude (in the terminal)

- `bash docs/manual-qa/qa-watch.sh` — blocks until you ping a card, then
  hands me the ping (card + status + notes) so I can act.
- `bash docs/manual-qa/qa-reply.sh <testId|-> <info|success|warn|error|question> "<text>"`
  — posts a reply into that card (`-` = the general-messages area).

## State & safety

- State lives in `/tmp/qa-<page>-{state,replies,ping}.json` (per dashboard).
- The server **auto-redacts** JWTs and Alma API keys
  (`apikey …`, `ALMA_*_API_KEY=…`) from anything posted, before it's written.
- Don't paste real identifiers/keys into notes anyway (R9) — the redactor is a
  safety net, not a license.

## Adding a dashboard

Drop a new `YYYY-MM-DD-<topic>-qa.html` here; the server serves the
newest-dated one automatically (override with `QA_HTML=…`).
