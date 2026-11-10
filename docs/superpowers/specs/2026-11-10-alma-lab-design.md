# Alma Lab — interactive API test tool for almaapitk (issue #230)

Status: design, awaiting approval · Date: 2026-11-10 · Phase covered in detail: 1 of 2

## 1. Why this exists

Answers about how Alma behaves keep coming from the wrong places: Claude's memory, stale
docs, past tests or official documentation that does not cover the specific case. When the
owner asked Claude to test calls, they had to spell out which output to show and which values
to check, and Claude still mixed real results with assumptions.

The idea came out of the `alma-acquisitions-specialist` skill. Its claims must be validated
by real Alma answers, because sometimes the documentation does not say what happens in a
specific case. The owner also wanted to walk an acquisitions workflow stage by stage and see
what each call actually does.

**Alma Lab grounds API behaviour in real calls.** Every call it makes leaves an evidence
record (exact request, raw response, environment, versions, time, checks) that people and
agents cite instead of arguing from recollection.

A prototype exists in `Alma-Acquisitions-Automation` PR 8 (`scripts/sandbox_request_cli.py`,
`sandbox_workflow*.py`, `sandbox_terminal.py`, `docs/WORKFLOW_WIZARD.md`). It proved the
evidence and safety ideas but **is not app-like**: it redraws boxed panels and reads typed
answers with `input()`. App-like behaviour is the foundation the owner asked for, not a
polish item.

## 2. Goals

1. **Feels like a real app** (the owner's top priority): a stable full-screen layout that
   never scrolls the terminal, arrow-key navigation, editable fields whose values can be
   changed and re-sent, inner scrolling inside panes.
2. **Run any almaapitk operation** and see input and output together.
3. **Every call produces an evidence record**, from the app or from an agent.
4. **Agents (Claude) can use it without a screen** and get the same evidence.
5. **Ships with almaapitk**, so every repo that imports almaapitk can use it in development.
6. **Mirrors almaapitk's API surface** and grows automatically as coverage grows (the
   long-term aim is full Alma API coverage).
7. **Phase 2 (later, not urgent): workflows.** Design a chain of related calls where one
   call's output feeds the next, run it, and document the results.

## 3. Non-goals and anti-goals

Non-goals for phase 1: workflows (phase 2); watching an agent's calls live; sharing evidence
between machines; replacing the acquisitions prototype (it stays until this tool covers its
uses); a web UI; batch or bulk operations.

Anti-goals (failure even if it technically works):
- **Not app-like:** anything that scrolls the terminal, needs retyping to change a value, or
  works through question-and-answer prompts.
- **Evidence that isn't trustworthy:** a record that differs from what was actually sent or
  received, or that can be mistaken for a different environment, version or time.
- **A write that happens by accident,** above all on Production.
- **Leaks:** an API key in any evidence file, or real identifiers / personal data in anything
  committed or pushed (repo rule R9).
- **A parallel Alma client:** the tool calls Alma through almaapitk, not around it.

## 4. Decisions the owner made

- **Layout: three panes** (option A of the mockups, https://claude.ai/artifact/MmLEw4gBCSRooGsv3E7Bos):
  Operations | Inputs | Result, all visible at once.
- **The result pane scrolls inside itself,** like a scroll box in a graphical app, while the
  other panes stay put.
- **Agent use is mostly headless:** the owner usually wants to learn what happened, not watch
  screens. Seeing it in the app matters only for deep bugs.
- **Production:** reads allowed; **writes only after a typed confirmation.**
- **Order:** the app-like shell and single calls first; workflows second.
- **Methods that write more than once** (e.g. `Acquisitions.create_invoice_with_lines`
  creates, adds lines, approves and pays; `update_marc_field` and `add_user_note` GET then
  PUT): **the tool pauses before each write and asks for confirmation every time**, with a
  typed word for each write on Production. They are not hidden.
- **Raw calls for endpoints almaapitk does not wrap ship after phase 1, not in it.** Issue
  #183 (public `raw_request()`) gets higher priority so raw calls can follow soon after.
- **Workflow example the owner gave** (phase 2): read the member identifiers of a set → get
  each record's 505 field → add a 997 field based on that result.

## 5. The design (phase 1)

### 5.1 Screen

```
┌ top bar: ALMA LAB · almaapitk <version> · env: SANDBOX (EU) · ? help ──────────────────┐
│ Operations          │ Inputs                        │ Result                           │
│ ▾ Bibs              │ Bibs.get_record               │ 200 OK · 412 ms · tracking …     │
│   get_record        │ mms_id  [990000000000001]     │ [Response] Request Evidence      │
│   update_record ✎   │ view    (full ▾)              │ { … scrolls inside the pane … }  │
│ ▸ Users             │ Expect: status == 200         │ Checks ✓ ✓   Saved evidence/…    │
│                     │           [ Send ⏎ ]          │                                  │
└ bottom bar: the keys that work right now ──────────────────────────────────────────────┘
```

- **Top bar** always shows the almaapitk version and the environment. Production is shown
  in a distinct warning colour, all the time, not only at confirmation.
- **Operations pane:** a tree grouped by domain (Acquisitions, Admin, Analytics, Bibs,
  Configuration, ResourceSharing, Users, …). Write operations are marked. A search key (`/`)
  filters the tree by name, so the list stays usable as coverage grows past hundreds.
- **Inputs pane:** a form built from the selected method (see 5.3). Text fields, dropdowns
  for fixed choices, checkboxes for flags, a JSON/XML body editor for methods that take a
  body (with "load from file" and "load from an earlier response"). Values stay when you
  re-send; you change one and send again. An **Expect** section takes optional checks. The
  pane scrolls inside itself when a method has many fields.
- **Result pane:** a scroll box (arrow keys, PgUp/PgDn, mouse wheel) with tabs:
  - **Response:** the response as a fold-out tree (JSON, and XML/MARC with fields as nodes,
    e.g. open the 505 node and leave the rest folded), plus a raw-text view.
  - **Request:** exactly what was sent: method, full URL with query, headers with the key
    masked, body.
  - **Evidence:** the saved record, its path and the check results.
  - Status line on top: HTTP status, duration, Alma tracking ID, and the typed almaapitk
    error class if the call failed (`AlmaServerError`, `AlmaValidationError`, …).
- **History** (`h`): this repo's earlier evidence records, newest first. Opening one fills
  all three panes as it was, and "re-run" sends it again with the same inputs. This is also
  how the owner looks at what an agent did.
- **Keys:** ←/→ or Tab between panes, ↑/↓ within a pane, Enter edits or sends, `/` search,
  `h` history, `e` jump to Expect, `?` help, `q` quit. Mouse clicks and wheel work too. The
  bottom bar always lists the keys that work in the current place.
- **Size:** designed for about 120 columns × 30 rows (Windows Terminal maximised). Narrower
  terminals still work: panes shrink, and below a threshold the operations pane collapses
  to the search box.

### 5.2 Environments and write safety

- **Sandbox by default.** The environment is chosen at start (`--env SANDBOX|PRODUCTION`)
  or in the app, and is visible at all times. Keys come from `ALMA_SB_API_KEY` /
  `ALMA_PROD_API_KEY` as almaapitk already does; the tool never asks for, shows or stores a
  key.
- **Write = any method that is not a GET** (POST, PUT, DELETE). The tool knows this per
  operation before sending (see 5.3).
- **Sandbox writes:** a confirm step that shows method, path and body summary; Enter
  confirms.
- **Production writes:** the same screen, plus the user must **type a confirmation word**
  (the operation name, e.g. `update_record`). Anything else cancels. In headless mode a
  Production write requires an explicit `--confirm-write <operation name>` flag matching the
  operation; without it the command refuses.
- **Each write is confirmed when it is about to be sent,** not once per operation. The tool
  installs a pre-send hook on the client: before any non-GET request leaves, the app shows
  method, path and body and waits for confirmation (Enter on Sandbox, the typed operation
  name on Production). Cancelling stops the method there; the evidence records which
  writes were sent and which were cancelled. Headless: `--confirm-write <operation name>`
  approves all writes of that one call on Production; on Sandbox headless writes need
  `--allow-writes`. The operations tree marks methods known to write more than once.
- **No automatic retries of writes** by the tool (my call): the tool builds its client with
  a retry policy that retries GET only. Retried GETs stay, so tests still show almaapitk's
  real behaviour, and every attempt is recorded (see 5.4).
- Repo rule R8 still applies to SANDBOX tooling: the tool does not change it, but in Sandbox
  mode it ignores the Production key entirely.

### 5.3 Where the operations come from

- **Primary: almaapitk's own public methods.** The tool reads the domain classes (today 156
  public methods, 151 fully type-hinted, 139 with `Args:` docstrings) and builds each form
  from the signature (names, types, defaults, required vs optional) and docstring (help text
  per field). New almaapitk coverage appears in the tool without editing it.
- **Per-method hints** (small, optional, kept next to the tool): dropdown choices for
  fixed-value parameters, which parameter is the body and its format, and the HTTP method /
  endpoint for display and write classification when it cannot be derived. A method with
  no hint still works as plain fields.
- **Write classification must be reliable.** If a method's HTTP method cannot be determined
  from hints or from the recorded request of a previous run, the tool treats it as a write.
  The build should add a test that every public method has a known classification, so new
  methods cannot land unclassified.
- **Raw calls are not in phase 1** (owner's decision). They follow once issue #183 (public
  `raw_request()`) lands: method + path + query + body, with endpoints and parameters taken
  from the committed swagger snapshot (`docs/alma-swagger/`), marked as raw in evidence.
  Phase 1 should leave room for a "Raw" branch in the operations tree.
- **Parameters that cannot be form fields** (callbacks such as `progress_callback` /
  `should_stop`, predicates, pymarc objects) are shown greyed out with "not settable in the
  lab" and left at their defaults (my call). A method whose required parameter is one of
  these is listed but cannot be sent.
- Calls always go through an `AlmaAPIClient`, so each test exercises both Alma and
  almaapitk (retries, timeouts, error typing included).

### 5.4 Evidence records

One JSON file per call. Fields:

- `id`, `created_at` (local time with offset), `tool_version`, `almaapitk_version`,
  `python_version`, `environment`, `region`/base URL host;
- `operation` (e.g. `BibliographicRecords.get_record`) or `raw: true`; `inputs` (the
  method arguments as given);
- `requests`: **every HTTP request the operation actually made**, in order (a method can
  make several, e.g. paging), each with method, URL, query, headers with the key masked, body,
  and its response status, headers, raw body, duration and Alma tracking ID;
- `result`: what the almaapitk method returned (serialised), or the exception class and
  message;
- `expectations` and their outcomes (`passed` / `failed` / `error`), if any were set;
- `source`: `app` or `headless`, and, for headless runs, the command line minus anything
  secret.

Capturing the real requests must use a hook on the client's HTTP layer (one chokepoint,
`AlmaAPIClient._request` or the session), not a re-construction of what was probably sent.
This is what makes the record trustworthy. **Retries happen below that hook** (urllib3,
inside the adapter), so each recorded request also carries its retry history from the
urllib3 response (`retries.history`: status or error per attempt), so a GET that Alma
received four times shows four attempts (my call).

**Requests that bypass the client** (today: the PubMed lookup in
`ResourceSharing.create_lending_request_from_citation`, via `utils/citation_metadata.py`)
are not captured. Evidence for such methods carries `"incomplete": true` with the reason, and
the app shows a warning on the Evidence tab (my call). Routing those lookups through a
capturable session is a possible later improvement, not phase 1.

**Where:** `alma-lab-evidence/<YYYY-MM-DD>/<HHMMSS>-<operation>.json` under the current
working directory (the repo that runs the tool), overridable by `--evidence-dir`. The tool
warns at start if that folder is not gitignored, and offers to add it. Records hold real IDs
and possibly patron data, so they never go into git (R9).

**Redacted export:** an action (app) and a command (headless) that write a copy with
identifiers and personal data replaced by stable placeholders (`<mms_id_1>`, `<user_1>`),
keeping structure and types. This copy is what gets quoted in skills, issues and PRs.
Rule (my call): a maintained list of sensitive field names and value patterns is replaced
by default: record IDs (MMS, holding, item, POL, invoice, vendor and set IDs), user
identifiers and names, emails, phone numbers, addresses, barcodes, notes and free text
under user records, and institution codes; plus anything that matches an identifier taken
from the call's own inputs, wherever it appears (URL, body, response). Status values, codes,
counts, dates and field structure stay. In the app the export shows a preview of every
replacement; the user can keep a specific value on purpose, and the export records that
choice. Headless export uses the default list only. When unsure, replace: a lost value can
be read from the local record; a leaked one cannot be taken back.

**Expectations** (optional, per call): `status == 200`, `<path> exists`,
`<path> == <value>`, `<path> contains <text>`. What they point into (my call):
- `status` = the HTTP status of the **last** request the method made; `error` = the
  exception class name if the method raised (e.g. `error == AlmaServerError`).
- A bare path points into the **method's return value**, normalised: an `AlmaResponse` →
  its parsed JSON data; a dict or list → as is; XML text → parsed so MARC fields are
  addressable as `record.datafield[tag=505].subfield[code=a]`. Example:
  `payment.payment_status.value == PAID`.
- `http[N].status` / `http[N].body.<path>` point into the N-th raw HTTP response, for
  methods that make several requests.
The outcomes are recorded. Mapping to the skills' four verdicts is the skill's job: a passed
check supports "Sandbox-confirmed within tested scope", a failed one supports
"contradicted". The tool records facts; it does not assign verdicts.

### 5.5 Headless mode (for agents)

Same package, a command instead of the screen. Shape (exact flags are the builder's call):

```
almaapitk-lab call bibs.get_record --mms-id 990000000000001 --view full \
    --expect "status == 200" --expect "title exists" --env SANDBOX
almaapitk-lab run steps.json          # several independent calls from a file
almaapitk-lab list [--domain bibs]    # operations and their parameters
almaapitk-lab show <evidence id|path> # print one record
almaapitk-lab export <evidence id> --redacted
```

Output is a short summary on stdout (operation, status, duration, tracking ID, check
results, evidence path) and a non-zero exit when the call fails or a check fails, plus
`--json` for the full record. Agents read the summary and point the owner at the evidence
path; the owner opens it in the app via History. `run steps.json` in phase 1 is a list of
independent calls (no data passed between them); passing data between steps is phase 2.

### 5.6 Packaging

- Lives in almaapitk as `almaapitk.lab`, installed with an optional extra:
  `pip install almaapitk[lab]` / `poetry add almaapitk -E lab`. The core install gains no
  dependency.
- Console command: `almaapitk-lab` (no arguments opens the app).
- **UI library: Textual** (my call). It provides full-screen layout, focus and arrow-key
  navigation, scrollable containers, tree and form widgets, mouse support and Windows
  Terminal support, which together cover goal 1 without hand-written terminal control.
- Must run on the masedet Windows workstation (Windows Terminal, PowerShell) and in
  WSL/Linux terminals.
- Logging through `almaapitk.alma_logging` as the rest of the package; no `print` outside
  the headless output.

### 5.7 Testing (expectations for the build)

- Unit tests for: operation discovery and form building from signatures; write
  classification (every public method classified); evidence capture against a recorded
  fake HTTP layer (the record must match what was sent byte for byte apart from the masked
  key); redaction; expectation parsing; headless exit codes; Production write refusal
  without the confirmation flag.
- App behaviour tested with Textual's built-in test driver (keys pressed, panes focused,
  result pane scrolled, re-send with a changed value).
- A live SANDBOX smoke (opt-in, not a release gate) that runs one read through headless mode
  and checks the evidence record.

## 6. Phase 2 sketch: workflows (not designed yet)

To be designed in its own spec. What phase 1 must keep possible:
- A workflow is an ordered list of steps; each step is an operation with inputs, where an
  input can refer to an earlier step's result by path (e.g. step 2's `mms_id` = each member
  of step 1's set). Loops over a list are needed for the owner's example.
- Each run records a hypothesis, the expected results per step, the actual evidence records
  and a verdict, as the acquisitions prototype's wizard does (re-read before writing,
  typed confirmation per write, no automatic write chain).
- Phase 1 delivers no "save as step" action (my call); it only keeps the door open: the
  evidence record's `operation` + `inputs` are already a reusable step, and the evidence
  format should not need to change for workflows.

## 7. Left to the builder

- Exact keys beyond those listed, colours, widget choices, pane proportions.
- Headless flag spelling and the `steps.json` format.
- How per-method hints are stored and how the swagger snapshot is indexed for raw calls.
- Serialisation of non-JSON results (XML strings, AlmaResponse, generators: materialise with
  a cap and record that it was capped).
- Whether History reads the folder each time or keeps an index.
- How to land the work in reviewable PRs (e.g. capture + evidence + headless first, then
  the screen).
