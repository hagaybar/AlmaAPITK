# Alma Lab

Alma Lab runs almaapitk operations against Alma and keeps **evidence of every call**: the
exact request, the raw response, the environment, the versions and the time. Use it to see how
the API really behaves in a specific case, instead of relying on memory, old notes or
documentation that does not cover the case.

It has two front ends over the same engine:

- **The app**: a full-screen terminal app with three panes (operations, inputs, result).
- **The headless command**: `almaapitk-lab call …`, for scripts and AI agents. It prints a short
  summary and leaves the same evidence file the app would.

## Install

```bash
pip install "almaapitk[lab]"      # the app (adds Textual)
pip install almaapitk             # the headless command only
```

Keys come from the usual environment variables: `ALMA_SB_API_KEY` for Sandbox (the default) and
`ALMA_PROD_API_KEY` for Production. The tool never asks for, shows or stores a key.

## The app

```bash
almaapitk-lab                     # Sandbox
almaapitk-lab --env PRODUCTION    # Production: the top bar turns red
```

| Pane | What it does |
|------|--------------|
| Operations | Every public almaapitk method, grouped by domain. `/` searches by name. `✎` marks methods that write, `✎✎` methods that write more than once. Greyed names have a required input the lab cannot set. |
| Inputs | A form built from the method's signature and docstring. Change any value and send again. **Expect** takes optional checks, one per line. |
| Result | Status, duration, Alma tracking ID, error class and check results on top; tabs below: **Response** (a tree that unfolds as you go; XML and MARC show as fields), **Raw**, **Request** (exactly what was sent, key masked) and **Evidence**. Each tab scrolls inside itself. |

Keys: `Ctrl+←/→` switch panes · `↑↓` move · `Enter` edit or send · `Ctrl+S` send · `/` search ·
`h` history · `e` expect · `x` export redacted · `?` help · `Ctrl+Q` quit. The mouse works too.

**History** (`h`) lists the evidence records in the folder, newest first, including those an
agent made with the headless command. Opening one fills all three panes as it was; send again to
re-run it.

## Checks (Expect)

```
status == 200
title exists
payment.payment_status.value == PAID
anies[0].record.datafield[tag=505].subfield[code=a] contains Part
error == AlmaServerError
http[0].body.total_record_count == 3
```

- `status` is the HTTP status of the last request the method made; `error` is the exception
  class name if the method failed.
- A bare path points into what the method returned. Dots for keys, `[N]` for list items,
  `[name=value]` to pick an item or XML element by an attribute. XML (including MARC inside a
  JSON response) is read as elements.
- `http[N].status` and `http[N].body.<path>` point into the N-th raw response, for methods that
  make several requests.

## Writes

Anything but a GET is a write, and **every write is confirmed when it is about to be sent**, not
once per operation. A method that writes several times (for example
`Acquisitions.create_invoice_with_lines`) asks before each one.

| | App | Headless |
|---|---|---|
| Sandbox | Confirm on the screen (Enter sends, Esc cancels) | `--allow-writes` |
| Production | Type the method name (for example `delete_record`) | `--confirm-write delete_record` |

A refused write is not sent; the evidence lists it under "not sent". The lab never retries a
write (its client retries GET only).

## Evidence

One JSON file per call, in `alma-lab-evidence/<date>/<time>-<operation>.json` under the folder
you run the tool from (change with `--evidence-dir`). Each record holds: the operation and its
inputs; every HTTP request the operation made, in order, with masked headers, body, status, raw
response body, duration, tracking ID and retry attempts; what the method returned; the checks
and their outcomes; versions, environment and time.

**Evidence holds real IDs and possibly patron data. Keep the folder out of git.** The tool warns
when it is not in `.gitignore`.

Methods that also call services outside Alma (today:
`ResourceSharing.create_lending_request_from_citation`, which looks up PubMed or Crossref) are
marked **incomplete**: those outside calls are not captured.

### Sharing evidence: redacted export

To quote evidence in an issue, PR or a skill, export a redacted copy. Record IDs, user
identifiers and names, contact details, barcodes, notes, institution codes, identifiers from
the call's inputs, MARC 001, emails and phone numbers are replaced by placeholders such as
`<mms_id_1>`, everywhere they appear. Statuses, codes, counts, dates and structure stay.

- App: `x` shows a preview of every replacement; tick a value to keep it; `Ctrl+S` saves
  `<record>.redacted.json` next to the record.
- Headless: `almaapitk-lab export <id> --out redacted.json`.

## Headless use (scripts and agents)

```bash
almaapitk-lab call bibs.get_record --mms-id 990000000000001 --view full \
    --expect "status == 200" --expect "title exists"
almaapitk-lab call acq.get_invoice --param invoice_id=<invoice_id> --json
almaapitk-lab run steps.json
almaapitk-lab list --domain bibs
almaapitk-lab show <evidence id>
almaapitk-lab export <evidence id> --out redacted.json
```

Inputs are `--<param-name> value` (dashes or underscores) or `--param name=value`. Operation
names are `Domain.method` or an alias: `acq`, `admin`, `analytics`, `bibs`, `conf`,
`electronic`, `rs`, `users`. `steps.json` is a list of independent calls:

```json
[
  {"operation": "bibs.get_record", "inputs": {"mms_id": "990000000000001"}, "expect": ["status == 200"]},
  {"operation": "users.get_user", "inputs": {"user_id": "<user_primary_id>"}}
]
```

The summary on stdout gives the operation, status, duration, tracking ID, each check (`✓`/`✗`)
and the evidence id. Exit codes: `0` ok · `1` the call failed, a check failed or a write was
refused · `2` usage, input, credential or evidence error. almaapitk's own log lines are quiet so
the output stays readable and `--json` stays parseable; `--verbose` brings them back.

## Raw calls: all Alma endpoints

almaapitk wraps only part of Alma. The **Raw** branch reaches every endpoint in Ex Libris'
published API definitions (the snapshot in `docs/alma-swagger/`: acquisitions, bibs,
configuration, courses, electronic, partners, users, analytics). Use it to see what an
endpoint really returns before you write code for it. Raw calls go through
`AlmaAPIClient.raw_request` (see the raw requests guide), so auth, region and redacted
evidence work as for any other call. Evidence marks them `raw: true` and records the endpoint
and, if almaapitk wraps it, which method (`wrapped_by`).

### In the app

Open the **Raw · all Alma endpoints** branch in the Operations pane. Endpoints are grouped by
area, with counts. An endpoint that almaapitk already wraps shows `→ Domain.method`; pick that
method instead if you want the library's own behaviour. `custom path…` lets you type any
path. If the path matches a defined endpoint, the lab switches to that endpoint's form.

The form is built from the definitions: path parameters, query parameters and a body. Bodies
can be typed, or filled with **Load from file** or **Load from earlier response**.

**Updating a record (PUT)** starts from the current record, so you never send a body built
from memory:

1. The form has a **Baseline** section, with the query fields of the matching GET. Press
   **Load current record**. This is a read, and it fills the body.
2. Edit the body. **Send** stays locked until the record is loaded.
3. If Alma's copy changed while you were editing, the send is refused and nothing is
   written. Press **Load the new version** and redo the edit.

A custom path that has a defined GET follows the same rule. The evidence of an update holds
the baseline, the body and their diff; a refusal is recorded as `refused`.

Writes are confirmed like all lab writes. On Production the word to type is the method plus
the last fixed segment of the path, for example `PUT courses`.

### Headless

```bash
almaapitk-lab endpoints --area courses            # list, or --search TEXT, --json
almaapitk-lab raw GET almaws/v1/courses --query limit=2 --expect "status == 200"
almaapitk-lab raw GET almaws/v1/courses/<course_id> --format xml
```

A PUT in three steps (the first two do not change anything):

```bash
# 1. fetch the current record; also writes current.json.evidence
almaapitk-lab raw PUT almaws/v1/courses/<course_id> --baseline-out current.json
# 2. edit a copy
cp current.json edited.json
# 3. send it; refused if the record changed since step 1
almaapitk-lab raw PUT almaws/v1/courses/<course_id> --body-file edited.json \
    --baseline current.json --allow-writes
```

On Production use `--confirm-write "PUT courses"` instead of `--allow-writes`. Use
`--baseline-query k=v` when the GET needs query parameters. Exit codes are as for `call`.

### Refreshing the endpoint list

The list is a bundled file, `src/almaapitk/lab/data/alma_endpoints.json`, built from
`docs/alma-swagger/`. After you refresh the snapshot, rebuild it and commit both:

```bash
python -m scripts.build_lab_endpoints
```

A unit test fails if the bundled file is out of date.

## Not yet

- Workflows: chains of calls where one call's output feeds the next (phase 2).
