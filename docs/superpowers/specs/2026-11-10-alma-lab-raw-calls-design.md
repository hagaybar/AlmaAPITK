# Alma Lab: raw calls to any Alma endpoint

Status: design · Date: 2026-11-10 · Follows: Alma Lab phase 1 (#230, PR #235), `raw_request()` (#183, PR #237)
Mockups the owner reviewed: https://claude.ai/artifact/DLgRv7Q92a6HE4ApWtrHw7 (option A chosen)

## 1. Why

The owner built almaapitk around TAU's own needs, method by method. That made it a good fit for
TAU and a thin one for anyone else. The aim now is to make almaapitk worth picking up for
**a Python developer at another Alma library**, whose needs nobody here knows.

For people writing code, `AlmaAPIClient.raw_request()` (#183) already covers any endpoint
almaapitk does not wrap. This design covers the step before code: **exploring**. The Lab gets
an API console in the spirit of Ex Libris' own API console: browse every Alma endpoint, fill
in its parameters from Alma's published definitions, send it, and get the Lab's evidence
record and write safety. Unlike the Ex Libris console, it shows which endpoints almaapitk
already wraps, keeps evidence of every call, and confirms writes.

## 2. Goals

1. A "Raw: all Alma endpoints" branch in the Lab's operations tree, holding every operation in
   the committed API definitions (304 today across acq, analytics, bibs, conf, courses,
   electronic, partners, users), grouped by area as in the Ex Libris docs.
2. Endpoints almaapitk already wraps carry a small mark naming the method
   (e.g. `GET /bibs/{mms_id}  → BibliographicRecords.get_record`).
3. A form built from the definition: path fields, query fields with type, default and Alma's
   own description as help, and a body editor for POST/PUT.
4. **Updates start from a GET** (owner's rule: "we should always start from GET to have a
   baseline"). For a PUT, the Lab fetches the current record from the same path and loads it
   into the body editor. The evidence keeps that baseline and a diff against what was sent.
5. Same write safety as typed operations: every non-GET is confirmed before it leaves, with a
   typed word on Production.
6. Works for a developer who installed almaapitk from PyPI: the definitions ship inside the
   package.
7. Headless use for agents, with the same evidence.

## 3. Non-goals and anti-goals

Non-goals: request-body templates built from Alma's XSD schemas (the definitions only point at
external schema files); raw steps inside `almaapitk-lab run steps.json`; workflows (Lab phase
2); refreshing the definitions automatically from Ex Libris.

Anti-goals (failure even if it technically works):
- **A parallel Alma client.** Raw calls go through `AlmaAPIClient.raw_request()`, so the
  recorder, auth, region, retries and error typing are exactly those of typed calls.
- **A write by accident**, above all on Production, or an update sent without a baseline when
  one was available.
- **A wrong "wrapped by" mark.** A mark that names a method which does not call that endpoint
  misleads exactly the newcomer this is for. When unsure, show no mark.
- **Evidence that can be mistaken for a typed call.** Raw records say so.
- Everything phase 1 lists still applies (keys never in evidence, R9, app-like behaviour).

## 4. Decisions

The owner's:
- Tree layout **A**: one separate branch; almaapitk's own methods stay on top as the
  recommended path.
- Mark endpoints almaapitk already covers.
- Updates always start from a GET of the same path.
- Work in a dedicated branch with the usual safety procedures.

Mine (the owner can overturn any of these):
- **Bundled index.** A build script turns `docs/alma-swagger/*.json` into one compact index
  inside the package (`src/almaapitk/lab/data/alma_endpoints.json`); a unit test fails if the
  index is out of date with the snapshot. The index records each source file's fetch date.
- **No dropdowns from definitions.** The definitions declare no fixed-value lists (0 of 517
  query parameters have an `enum`), so query fields are free text with Alma's description as
  help. Types (integer, boolean) are still checked before sending.
- **Format.** JSON by default. The 5 bodies Alma accepts only as XML (e.g. `PUT /bibs/{mms_id}`)
  default to XML. A JSON/XML switch is offered when the definition allows both. The baseline
  GET uses the same format as the body.
- **Custom path.** An entry at the end of the Raw branch for paths the definitions lack
  (TaskLists has no published definition): method, path, query lines, body. No baseline is
  enforced there, but "Load from GET" is still offered.
- **Production confirmation word** for a raw write: the method and the last fixed path segment,
  e.g. `PUT courses`, `DELETE items`. Headless: `--confirm-write "PUT courses"`.
- **Wrapped-by marks** come from scanning almaapitk's source (see 5.3); a test checks every
  mark points at a real public method that sends that verb.
- **Baseline query** (resolved from the definitions, 5.4): the baseline GET has its own query
  fields, prefilled from the PUT's values where the names match.
- **Stale-baseline guard** (5.4, 5.7): just before a PUT leaves, the Lab fetches the record
  again and refuses the write if it no longer matches the baseline the edit started from.
  This follows from the owner's baseline rule; without it a PUT can silently undo someone
  else's change.
- **Redaction of raw inputs** (5.6): every path value is replaced; query values are replaced
  unless the parameter is on a short list of non-identifying names.

## 5. Design

### 5.1 The endpoint index

`almaapitk.lab.endpoints` loads the bundled index and exposes:

```
Endpoint(area, method, path, summary, description, params, body_formats, has_get_twin,
         wrapped_by, source_fetched)
EndpointParam(name, location: "path"|"query", type, required, default, description)
```

- `area`: the definition file (`acq`, `bibs`, `conf`, `courses`, …), shown with the Ex Libris
  area names.
- `params`: path-level and operation-level parameters, path first, in definition order.
- `body_formats`: from `requestBody.content` (`json`, `xml`), empty when there is no body.
  When a definition carries a body `example` (6 do), keep it: it is offered as a starting
  point for POST.
- `has_get_twin`: a GET exists on the same path template (true for 42 of 43 PUTs).
- `match(method, concrete_path)` → `(Endpoint, path_params)`, by template segments, preferring
  literal segments over placeholders. Used by headless mode and History.
- `scripts/build_lab_endpoints.py` regenerates the index; `tests/unit/lab/` holds the sync test.
  Packaging: the JSON file is included in the wheel and sdist (the wheel-contents check is
  updated if it lists allowed files).

### 5.2 Operations tree

- After the domain branches: `Raw · all Alma endpoints`, collapsed. Under it one node per area
  with its count, then `METHOD  /path-after-/almaws/v1` leaves sorted by path then method.
  Writes carry ✎ as in phase 1. A wrapped endpoint ends with `→ Domain.method` (dim); when
  several methods call it, the first and `+N`.
- The last node is `custom path…`.
- Search (`/`) also matches raw paths and summaries, so typing `courses` finds them.

### 5.3 Wrapped-by marks

Extend the catalog's existing AST scan: for each `self.client.<verb>(<first arg>)` in a domain
method (and the `self.` helpers it calls), turn the first argument into a path template, and
match it against index templates with the same verb (`iter_paged` counts as GET). The first
argument resolves when it is:
- a string or f-string literal (`f"almaws/v1/bibs/{mms_id}"` → `/almaws/v1/bibs/{}`), or
- a local name (most calls, e.g. `endpoint = f"almaws/v1/bibs/{mms_id}"` then
  `self.client.get(endpoint, ...)` in `get_record`) whose **every** assignment in that function
  is such a literal. Each resolved template is an endpoint the method may call (branches can
  legitimately call two). If any assignment is not a literal (a call, a concatenation with a
  non-literal, a parameter, an augmented assignment), the name does not resolve and that call
  gives no mark.
Anything else gives no mark. Better no mark than a wrong one. A test asserts every mark names an existing
public method whose classified verbs include the endpoint's verb, and that a handful of known
pairs are found (e.g. `GET /almaws/v1/bibs/{mms_id}` → `BibliographicRecords.get_record`).

### 5.4 Inputs pane for a raw endpoint

Title block: `RAW  METHOD /full/path`, the summary, "from Alma API definitions, <fetch date>",
and either `almaapitk: Domain.method` or "No almaapitk method for this yet".

Fields: path parameters (required), query parameters (default prefilled, description as help,
integer/boolean checked), a format switch when both are allowed, and for POST/PUT a body editor
with "Load from file" and "Load from earlier response". Expect and Send as in phase 1.

**PUT with a GET twin (the baseline rule):**
- The form has a **Baseline** section with the GET's own query fields from its definition
  (e.g. `scope` is required on `GET /conf/open-hours` and `/conf/relations`; `user_id_type`,
  `view`, `expand` on `GET /users/{user_id}`; `lang` on `GET /conf/code-tables/{codeTableName}`).
  Fields whose name also exists on the PUT are prefilled from the PUT's values and follow them
  until edited.
- The body editor starts empty and locked with the note "Fill the path fields, then load the
  current record". **Load current record** sends that GET with the same path values, the
  baseline query and the body format. It is a read, so it needs no confirmation.
- The response fills the body editor. Send stays disabled until a baseline for exactly the
  current path values and baseline query has been loaded. Changing either clears it.
- **Stale-baseline guard:** on Send, the Lab first repeats the baseline GET. If the response
  body differs from the loaded baseline (compared after the same normalisation the diff uses),
  the PUT is not sent: the record says `refused: baseline changed`, and the app offers to load
  the new version. Both GETs are recorded. The comparison is exact; if some endpoint turns out
  to return a volatile field on every GET, that endpoint's field gets an ignore entry in
  `hints.py` (none is assumed up front).
- The baseline GET is shown in the Result pane like any call, and is recorded (5.6).

PUT without a GET twin (1 today), POST, DELETE: no baseline; POST bodies start from the
definition's example when there is one, else empty.

### 5.5 Running a raw call

`Session.run_raw(endpoint_or_custom, path_params, query, body, fmt, expectations, baseline=None)`
next to `Session.run`, sharing its lock, recorder, gate, evidence writing and expectation
evaluation. It calls `client.raw_request(method, path, params=query, data=body,
content_type=...)`; the result is the `AlmaResponse`, normalised as phase 1 does. Input errors
(missing path value, bad integer, invalid JSON body, missing required baseline) raise
`InputError` before anything is sent. The write gate is the recorder's, unchanged.

### 5.6 Evidence

Same record shape, plus:
- `raw: true`, `endpoint`: `{method, path, area, source_fetched}` or `{method, path, custom: true}`,
  `wrapped_by`: the mark shown, if any.
- `operation`: `raw METHOD /path/template` for display; the file name and id use a safe slug
  (`raw-PUT-courses-course_id`).
- `inputs`: `{path: {...}, query: {...}, format, body}`.
- For a PUT with a baseline: `baseline`: the evidence id of the baseline GET record **and** a
  copy of its response body, and `body_diff`: a unified diff of baseline body → sent body (JSON
  pretty-printed with sorted keys before diffing; XML as text). The baseline GET also gets its
  own record.
- Rerun from History works for raw records: it reloads the form; a PUT rerun requires a fresh
  baseline (the record may have changed since).
- Redacted export: the redactor learns the nested raw `inputs` shape. **Every path value** is
  replaced wherever it appears (URL, body, response). **Query values** are replaced too,
  except for parameters on a short list of non-identifying names (`limit`, `offset`, `view`,
  `expand`, `format`, `order_by`, `direction`, `lang`, `type`, `status`, `level`). That covers
  values like `q=primary_id~…` and names like `codeTableName` that the phase 1 name rule
  misses. Same principle as phase 1: when unsure, replace.

### 5.7 Headless

```
almaapitk-lab endpoints [--area courses] [--search TEXT] [--json]
almaapitk-lab raw GET almaws/v1/courses --query q=name~Math --query limit=5 --expect "status == 200"
almaapitk-lab raw PUT almaws/v1/courses/<course_id> --body-file edited.json --allow-writes
almaapitk-lab raw PUT almaws/v1/courses/<course_id> --baseline-out current.json
```

- The path is concrete; it is matched to the index for metadata. An unmatched path runs as a
  custom path (printed as such).
- `PUT` with a GET twin is two commands, so an agent can fetch → edit → send:
  1. `--baseline-out FILE` sends the baseline GET (with `--baseline-query k=v` for the GET's
     own query), records it, writes the body to FILE and stops.
  2. `--body-file EDITED --baseline FILE` sends the PUT. The command repeats the baseline GET
     first and refuses (exit 1, recorded) if it no longer matches FILE: the stale-baseline
     guard. Without `--baseline` the PUT is refused before anything is sent.
- `--allow-writes`, `--confirm-write "PUT courses"`, `--expect`, `--json`, `--env`,
  `--evidence-dir` and exit codes as in phase 1.

### 5.8 Testing

- Index: build from the snapshot equals the bundled file; counts per area; one sample endpoint's
  params; `match()` cases (literal beats placeholder, unknown path).
- Wrapped-by: the validity test, known pairs (5.3) including `get_record` via its local
  `endpoint` variable, and a function whose variable has a non-literal assignment gives no mark.
- Runner: path/query/body coercion and errors; raw GET recorded with `raw: true`; PUT refuses
  without baseline; PUT refused when the repeated GET differs from the baseline; baseline query
  prefill from shared names; baseline + diff in evidence; redaction of nested raw inputs; Production refusal without the confirmation
  word; Sandbox write refusal without `--allow-writes`; all against a fake HTTP layer as phase 1.
- CLI: `endpoints`, `raw` GET/PUT/`--baseline-out`, custom path, exit codes.
- App (Textual test driver): Raw branch present and searchable, a raw form loads, the PUT Send
  is disabled until the baseline loads, changing a path value clears it, the custom path form.
- Live SANDBOX smoke (opt-in): headless raw GET on a read-only endpoint, evidence checked.

## 6. Left to the builder

Widget choices, exact labels and colours; index file layout; diff format details; how area
names are displayed; how "+N" methods are listed; how the format switch looks; PR split.
