# HTML Dashboard Skill — Design

**Date:** 2026-05-27
**Status:** Approved design, pending spec review
**Author:** Claude Code session with operator

## 1. Motivation

The `docs/manual-qa/` tool (a localhost dashboard + a browser↔Claude messaging
loop) proved its worth during the consumer-safety testing rollout: it makes long
workflows easy to track, lets the operator and Claude pass information back and
forth, and presents complex data in a visually compelling way.

Today every use of HTML is bespoke — the operator must ask for it and re-specify
the format each time. We want to **generalize the pattern into a reusable
capability** that:

- is available to Claude in **every session and every repo**,
- Claude can **proactively suggest** when a task fits,
- covers a **variety of needs** through a library of design patterns (diagrams,
  dashboards, data presentation, comparisons, narratives), and
- preserves the **two-way browser↔Claude communication** the operator valued.

## 2. Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Scope | **Both** interactive dashboards (live two-way link) **and** static visual reports/diagrams (no server) |
| 2 | Generated HTML home | **Per-repo, committable** by default; ephemeral offered when clearly throwaway |
| 3 | Packaging | **Global skill** `html-dashboard` **+** a thin `/dashboard` slash-command alias |
| 4 | Capability | A **rich design-patterns library** Claude selects from (not just a few templates) |
| 5 | Source of truth | Master copy in a **dotfiles git repo**, **symlinked** into `~/.claude/skills/` (versioned, backed up, testable, still global) |

**Engine isolation principle:** the engine (server + helper scripts + vendored
assets) lives **once** in the skill and is **never copied into consumer repos**.
Only the generated HTML — and transient `/tmp` state — is per-repo. Every repo
stays clean.

## 3. Architecture

### 3.1 Layout

Master copy lives in a dotfiles repo; a symlink exposes it where Claude Code
looks for skills:

```
~/dotfiles/                              # NEW git repo (bootstrap step)
└── claude/
    ├── skills/html-dashboard/
    │   ├── SKILL.md                     # triggers, modes, workflow, pattern index
    │   ├── engine/                      # interactive mode only
    │   │   ├── server.py                # generalized qa-server.py (page-agnostic)
    │   │   ├── watch.sh                 # browser → Claude (ping watcher)
    │   │   ├── reply.sh                 # Claude → browser (reply poster)
    │   │   └── assets/                  # vendored mermaid.min.js, base.css, (opt) chart lib
    │   ├── patterns/
    │   │   ├── INDEX.md                 # intent → pattern → file (the catalog)
    │   │   └── *.html                   # standalone styled scaffolds (see §5)
    │   ├── references/building-html.md  # style conventions, comms-wiring snippet, R9 notes
    │   └── tests/test_engine.py         # engine smoke test (see §9)
    └── commands/dashboard.md            # /dashboard → routes into the skill

# One-time symlinks into the live Claude config:
~/.claude/skills/html-dashboard   ->  ~/dotfiles/claude/skills/html-dashboard
~/.claude/commands/dashboard.md   ->  ~/dotfiles/claude/commands/dashboard.md
```

(Exact dotfiles sub-paths are illustrative; the install script in §8 pins them.)

### 3.2 Why a skill

Skills are the Claude Code mechanism that surfaces a capability **to Claude**
each session in every repo — exactly "available to you, that you could suggest."
The `/dashboard` command additionally lets the **operator** summon it directly.

## 4. Two modes

- **Static** — Claude picks a pattern, fills it with content, writes the `.html`
  into the repo, and opens it (via `file://` or a throwaway
  `python3 -m http.server`). No persistent server, no comms JS. For reports,
  diagrams, comparisons, one-shot data views.

- **Interactive** — same, plus Claude starts `engine/server.py` pointed at the
  repo's dashboard dir and the page includes the comms JS. Claude runs
  `watch.sh` to receive pings and `reply.sh` to answer inline. This is the
  manual-qa loop, generalized. The page includes the comms wiring **only** when
  interactive.

The pattern scaffold declares whether it is interactive-capable; Claude chooses
the mode based on the task and confirms with the operator before starting any
server.

## 5. The design-patterns library

`patterns/INDEX.md` maps **intent → pattern → file**. Each pattern is a
self-contained, styled HTML scaffold with labeled placeholder slots and a header
comment documenting its slots and "when to use." Adding a pattern later is just a
new `.html` plus an INDEX line.

Initial catalog:

| Category | Patterns | Typical use |
|----------|----------|-------------|
| **Diagrams** (Mermaid) | flowchart, sequence, architecture/component, state-machine | "How does the API work right now?", call ordering, module relationships, lifecycle/state |
| **Dashboards** | status-cards (interactive-capable), progress/timeline | Rollout tracking, multi-step workflows |
| **Data** | sortable/filterable table, metric tiles (KPIs), simple bar/line chart | Tabular results, headline numbers, trends |
| **Comparison** | side-by-side / before-after, decision matrix | Option trade-offs, A/B, change diffs |
| **Narrative** | stepper / annotated walkthrough | Guided explanations |

Mermaid covers class/ER/gantt diagrams for free without dedicated files.

## 6. Diagram rendering

Default to **Mermaid**, **vendored locally** in `engine/assets/mermaid.min.js`:
works offline, makes no external calls (consistent with this project's
secret-handling posture), and renders flowcharts/sequence/state/etc. from concise
text Claude generates.

- **Interactive pages** load the vendored asset served by `server.py`.
- **Standalone static pages** (no server) either **inline** the library for a
  single portable file, or reference a **CDN** `<script>` — chosen per file when
  portability matters. Default: vendored/inlined (no external dependency).

## 7. Engine: data flow, ports, state

Generalized from `docs/manual-qa/qa-server.py`, neutral naming (`DASH_*` env
vars rather than `QA_*`). Endpoints unchanged:

- `POST /state` → persist page state (statuses/notes) → `/tmp/dash-<stem>-state.json`
- `POST /ping`  → operator pings an element → `/tmp/dash-<stem>-ping.json`
- `POST /reply` → Claude posts a reply → appended to `/tmp/dash-<stem>-replies.json`
- `GET /state | /replies | /replies/since/<id> | /ping | /health`
- `GET /` → the served HTML page

**Per-page state keying** (by the served page's filename stem) means **multiple
dashboards coexist** without colliding in `/tmp`.

**Port handling:** server reads `DASH_PORT` (default `8765`) and
**auto-increments to the next free port if taken** — so a new dashboard will not
fight an already-running server (e.g. the manual-qa server currently on `:8765`).
`watch.sh` / `reply.sh` take the resolved base URL.

The existing `docs/manual-qa/` tool is **left untouched**; migrating it to the
global skill is optional future work, out of scope here.

## 8. Bootstrap / installation

One-time, scripted (`install.sh` in the dotfiles repo):

1. Create the dotfiles git repo (`~/dotfiles`, `git init`). Push to a private
   GitHub remote is **optional** and left to the operator.
2. Author the skill (engine, patterns, references, command, tests) under the
   dotfiles repo.
3. Vendor `mermaid.min.js` (and any chart lib) into `engine/assets/`.
4. Symlink the skill dir and command file into `~/.claude/` (idempotent; backs
   up any pre-existing real file before linking).
5. Verify Claude Code discovers `html-dashboard` and `/dashboard` in a new
   session.

## 9. Testing

`tests/test_engine.py` (pytest) boots `server.py` on an ephemeral port and
asserts:

- `/` serves the target HTML; `/health` returns ok.
- state/ping/reply round-trip through the `/tmp` files.
- a planted JWT and a planted `ALMA_*_API_KEY=…` / `apikey …` are **redacted**
  before persistence.
- port auto-increment picks a free port when the default is occupied.

Because the source of truth is a git repo (Decision 5, §2), this test is
version-controlled and can run in CI for the dotfiles repo. It does **not** run
in AlmaAPITK CI (the skill is not part of this package).

## 10. Security

- Generalize and keep the existing **redaction** (JWT, `apikey …`,
  `ALMA_*_API_KEY=…`) applied to every POST body before it is persisted.
- **Localhost-bind only** (`127.0.0.1`).
- Local asset vendoring → **zero external calls**.
- Reaffirm **R9**: never write real operator-supplied identifiers into committed
  HTML. The redactor is a safety net, not a license.

## 11. When Claude suggests it (proactive triggers)

`SKILL.md` encodes triggers. Claude offers a dashboard/diagram when the operator:

- asks to **track a long or multi-step workflow**, or **monitor live progress**,
- wants to **understand a flow or architecture** ("how does X work?"),
- needs to **compare options** or review a decision,
- needs to **present complex or tabular data** clearly.

Claude **suggests**; the operator accepts. Claude never auto-starts a server
unprompted.

## 12. Out of scope (YAGNI)

- Migrating `docs/manual-qa/` onto the global skill (optional later).
- Authentication / non-localhost serving.
- A pattern-authoring GUI — patterns are added by hand (file + INDEX line).
- Charting beyond simple bar/line in v1.

## 13. Open items

- Exact dotfiles repo path and whether to add a GitHub remote (operator's call at
  install time).
- Whether to later migrate manual-qa to consume the skill.
