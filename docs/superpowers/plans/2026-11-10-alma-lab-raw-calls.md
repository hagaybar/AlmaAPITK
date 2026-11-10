# Alma Lab Raw Calls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Raw: all Alma endpoints" console to Alma Lab (app and headless), driven by Alma's published API definitions, with evidence, write safety and the baseline-GET rule for updates.

**Architecture:** A build step turns `docs/alma-swagger/*.json` into one bundled index (`almaapitk/lab/data/alma_endpoints.json`) read by a new `almaapitk.lab.endpoints` module. The runner gains `Session.run_raw` / `Session.fetch_baseline`, which call `AlmaAPIClient.raw_request()` through the existing recorder and write gate. The CLI gains `endpoints` and `raw`; the app gains a Raw branch, a raw form, and a baseline flow.

**Tech Stack:** Python 3.10+, Textual (app, `lab` extra), pytest, stdlib `ast`/`difflib`/`importlib.resources`.

**Spec:** `docs/superpowers/specs/2026-11-10-alma-lab-raw-calls-design.md` (read it first; section numbers below refer to it). Phase 1 design: `docs/superpowers/specs/2026-11-10-alma-lab-design.md`.

## Global Constraints

- Raw calls go through `AlmaAPIClient.raw_request()` only (no `requests` calls in the lab), so the existing `Recorder` captures them and the existing gate confirms every non-GET.
- The core install gains no dependency; the index file is package data under `src/almaapitk/lab/data/` (allowed by `scripts/ci/check_artifact_contents.py`).
- R9: tests and docs use placeholders only (`990000000000001`, `<course_id>`, `PLACEHOLDER`); no real IDs.
- Production write confirmation word for a raw call: `METHOD <last fixed path segment>`, e.g. `PUT courses`, `DELETE items` (spec §4).
- Query parameters non-identifying for redaction: `limit, offset, view, expand, format, order_by, direction, lang, type, status, level` (spec §5.6). Every path value is always redacted.
- PUT with a GET twin: no PUT without a baseline; a repeated GET that differs from the baseline refuses the PUT (`refused = "baseline changed"`).
- No logging of keys or bodies; `get_logger` only, no `print` outside CLI output helpers.
- Before the PR: `make check` green; also `poetry run pytest tests/unit/lab -q` with the `lab` extra installed.

## Review Focus

1. A concrete path with a literal segment that also fits a placeholder (`/conf/code-tables/{codeTableName}` vs a fixed sibling) must match the literal template. Tested in Task 1 (`test_match_prefers_literal`).
2. Path values containing `/`, spaces or `~` must be URL-quoted in the path and still match on rerun. Tested in Task 3 (`test_path_values_are_quoted`).
3. An XML-only body (e.g. `PUT /almaws/v1/bibs/{mms_id}`) must send XML and take an XML baseline; diffing XML must not crash on invalid XML. Tested in Task 3 (`test_xml_put_baseline_and_diff`).
4. A baseline GET that fails (404, 500) must not unlock the PUT. Tested in Task 3 (`test_failed_baseline_does_not_count`) and Task 6 (`test_send_stays_locked_after_failed_baseline`).
5. History rerun of a raw PUT must demand a fresh baseline instead of resending stale data. Tested in Task 3 (`test_rerun_put_needs_fresh_baseline`).

---

### Task 1: Endpoint index (`almaapitk.lab.endpoints`)

**Files:**
- Create: `src/almaapitk/lab/endpoints.py`, `src/almaapitk/lab/data/__init__.py` (empty), `src/almaapitk/lab/data/alma_endpoints.json` (generated), `scripts/build_lab_endpoints.py`
- Test: `tests/unit/lab/test_endpoints.py`

**Interfaces:**
- Produces:
  - `EndpointParam(name: str, location: Literal["path","query"], type: str, required: bool, default: str | None, description: str)` frozen dataclass; `type` is the definition's schema type (`string`, `integer`, `boolean`, …).
  - `Endpoint(area: str, method: str, path: str, summary: str, description: str, params: tuple[EndpointParam, ...], body_formats: tuple[str, ...], body_example: str | None, source_fetched: str | None, custom: bool = False)` frozen dataclass. `path` is the full template, e.g. `/almaws/v1/courses/{course_id}`. `body_formats` holds `"json"` and/or `"xml"`, json first when present. Properties: `key -> "METHOD /path"`, `writes -> method != "GET"`, `short_path -> path without "/almaws/v1"`, `path_params`, `query_params`, `confirm_word -> f"{method} {last segment without braces}"`, `slug -> "raw-" + method + "-" + short_path with non [A-Za-z0-9_] runs as "-"`, stripped of edge dashes.
  - `build_index(swagger_dir: Path) -> dict`: `{"sources": {area: fetchedAt}, "endpoints": [ {...Endpoint fields...} ]}` from every `<area>.json` (not `*.fetched.json`), methods get/post/put/delete, path-level params merged before operation params, sorted by `(area, path, method order GET, POST, PUT, DELETE)`.
  - `load_endpoints() -> tuple[Endpoint, ...]` (cached; reads `alma_endpoints.json` via `importlib.resources`).
  - `get_endpoint(method: str, path: str) -> Endpoint` (KeyError if absent).
  - `get_twin(endpoint: Endpoint) -> Endpoint | None`: the GET on the same path.
  - `match(method: str, concrete_path: str) -> tuple[Endpoint, dict[str, str]] | None`: accepts with or without a leading `/`, with or without `almaws/v1/`; unquotes segment values; when several templates fit, the one with most literal segments wins.
  - `custom_endpoint(method: str, path: str) -> Endpoint`: `area="custom"`, `custom=True`, no params, `body_formats=("json","xml")` for POST/PUT, else `()`.
  - `AREA_TITLES: dict[str, str]` for display (`acq→"Acquisitions"`, `bibs→"Bibs"`, `conf→"Configuration"`, `courses→"Courses"`, `electronic→"Electronic"`, `partners→"Partners (resource sharing)"`, `users→"Users"`, `analytics→"Analytics"`).

- [ ] **Step 1: Write failing tests** in `tests/unit/lab/test_endpoints.py`:

```python
SWAGGER = Path(__file__).resolve().parents[3] / "docs" / "alma-swagger"

def test_bundled_index_matches_snapshot():
    bundled = json.loads(resources.files("almaapitk.lab.data").joinpath("alma_endpoints.json").read_text("utf-8"))
    assert bundled == build_index(SWAGGER)

def test_counts():
    eps = load_endpoints()
    assert len(eps) == 304
    assert Counter(e.area for e in eps)["courses"] == 29
    assert sum(e.method == "PUT" for e in eps) == 43
    assert sum(e.method == "PUT" and get_twin(e) is not None for e in eps) == 42
    assert sum(e.body_formats == ("xml",) for e in eps) == 5

def test_courses_list_params():
    ep = get_endpoint("GET", "/almaws/v1/courses")
    q = {p.name: p for p in ep.query_params}
    assert q["limit"].type == "integer" and q["limit"].default == "10" and not q["limit"].required
    assert "Brief Search" in q["q"].description
    assert ep.source_fetched.startswith("2026-05-29")

def test_match_concrete_path():
    ep, values = match("GET", "almaws/v1/bibs/990000000000001")
    assert ep.path == "/almaws/v1/bibs/{mms_id}" and values == {"mms_id": "990000000000001"}
    assert match("GET", "/almaws/v1/nope/1") is None

def test_match_prefers_literal():
    # pick any area with a literal sibling of a placeholder segment from the index itself
    ...  # assert the literal template wins for its literal path (find a real pair in the index in the test)

def test_confirm_word_and_slug():
    ep = get_endpoint("PUT", "/almaws/v1/courses/{course_id}")
    assert ep.confirm_word == "PUT courses"
    assert ep.slug == "raw-PUT-courses-course_id"

def test_put_bibs_is_xml_only():
    assert get_endpoint("PUT", "/almaws/v1/bibs/{mms_id}").body_formats == ("xml",)
```

For `test_match_prefers_literal`, find in the index a pair of same-method templates of equal length where one has a literal segment at the position the other has a placeholder, and assert `match` on the literal path returns the literal template. If no such pair exists, build two `Endpoint`s and call the internal matcher with them.

- [ ] **Step 2: Run** `poetry run pytest tests/unit/lab/test_endpoints.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `endpoints.py` and `scripts/build_lab_endpoints.py` (`python -m scripts.build_lab_endpoints` writes the JSON with `indent=None, separators=(",", ":")`, `ensure_ascii=False`, sorted keys, trailing newline). Parameters with `$ref` are not present in today's snapshot; resolve `#/components/parameters/...` anyway when present. Generate the JSON by running the script.
- [ ] **Step 4: Run** the tests. Expected: PASS. Also `poetry build && unzip -l dist/*.whl | grep alma_endpoints.json` shows the file.
- [ ] **Step 5: Commit** `feat(lab): bundled Alma endpoint index from the swagger snapshot`.

### Task 2: Wrapped-by marks

**Files:**
- Modify: `src/almaapitk/lab/catalog.py` (add `endpoint_calls`), `src/almaapitk/lab/endpoints.py` (add `wrapped_by`)
- Test: `tests/unit/lab/test_wrapped_by.py`

**Interfaces:**
- Consumes: `catalog._class_functions`, `catalog.DOMAINS`, `catalog.discover_operations()`, `endpoints.load_endpoints()`.
- Produces:
  - `catalog.endpoint_calls(cls: type, method_name: str) -> frozenset[tuple[str, str]]`: `(verb, template)` with placeholders written `{}` and a leading `/`, e.g. `("GET", "/almaws/v1/bibs/{}")`, following `self.` helpers like `_classify` does. Resolution rules exactly as spec §5.3 (literal / f-string; or a local name whose every assignment in that function is a literal / f-string; otherwise skip).
  - `endpoints.wrapped_by(endpoint: Endpoint) -> tuple[str, ...]`: sorted qualnames of public operations calling it (cached map built once).

- [ ] **Step 1: Failing tests:**

```python
def test_get_record_via_local_variable():
    assert "BibliographicRecords.get_record" in wrapped_by(get_endpoint("GET", "/almaws/v1/bibs/{mms_id}"))

def test_every_mark_is_a_real_method_with_that_verb():
    ops = {o.qualname: o for o in discover_operations()}
    marks = 0
    for ep in load_endpoints():
        for q in wrapped_by(ep):
            marks += 1
            assert q in ops and ep.method in ops[q].verbs
    assert marks >= 40

def test_non_literal_assignment_gives_no_mark():
    src = '''class D:
    def m(self, x):
        endpoint = f"almaws/v1/bibs/{x}"
        if x: endpoint = self._build(x)
        return self.client.get(endpoint)
'''
    # exec into a throwaway module with inspect.getsource patched, or call the internal
    # template resolver on the parsed FunctionDef: result must be empty
```

Pick the `marks >= 40` floor by running the scan once and setting it to roughly 80% of the real count (record the real count in the test's comment).

- [ ] **Step 2: Run**; expected FAIL.
- [ ] **Step 3: Implement.** Template from an `ast.JoinedStr`: literal parts kept, each `FormattedValue` → `{}`; strip a leading `/`, then prefix `/`. Match index templates after rewriting `{name}` → `{}`.
- [ ] **Step 4: Run**; expected PASS.
- [ ] **Step 5: Commit** `feat(lab): mark raw endpoints that almaapitk already wraps`.

### Task 3: Runner, evidence and redaction for raw calls

**Files:**
- Modify: `src/almaapitk/lab/runner.py`, `src/almaapitk/lab/evidence.py`, `src/almaapitk/lab/redact.py`
- Test: `tests/unit/lab/test_raw_runner.py`, extend `tests/unit/lab/test_redact.py`

**Interfaces:**
- Consumes: Task 1 `Endpoint`, `get_twin`, `match`, `custom_endpoint`; Task 2 `wrapped_by`.
- Produces:
  - `EvidenceRecord` new fields (all defaulted, so old records load): `raw: bool = False`, `endpoint: Optional[dict] = None` (`{"method","path","area","source_fetched","custom"}`), `wrapped_by: list[str]`, `baseline: Optional[dict] = None` (`{"evidence_id": str | None, "body": str}`), `body_diff: Optional[str] = None`, `refused: Optional[str] = None`, `slug: Optional[str] = None`. `write_record` names the file from `record.slug or record.operation`.
  - `RawRequest` dataclass in `runner.py`: `endpoint: Endpoint`, `path_params: dict[str, str]`, `query: dict[str, str]`, `body: str | None = None`, `fmt: Literal["json","xml"] = "json"`, `baseline_query: dict[str, str] = {}`.
  - `resolve_path(endpoint, path_params) -> str`: relative path for `raw_request` (no leading `/`), each value `urllib.parse.quote(value, safe="")`; `InputError(name, "is required")` when missing.
  - `coerce_query(endpoint, query) -> dict[str, Any]`: drops blanks; `integer` → int, `boolean` → bool (same words as `_TRUE/_FALSE`); unknown names → `InputError` unless `endpoint.custom`.
  - `Session.fetch_baseline(req: RawRequest) -> EvidenceRecord`: GET on `get_twin(req.endpoint)` with `req.path_params`, `req.baseline_query`, `Accept` matching `req.fmt`; a normal raw record.
  - `Session.run_raw(req: RawRequest, expectations: Iterable[str] = (), baseline: Optional[EvidenceRecord] = None) -> EvidenceRecord`.
  - `Session.rerun(record)` handles raw records (rebuilds `RawRequest` via `match`/`custom_endpoint`; a PUT whose endpoint has a twin raises `InputError("baseline", "load the current record again before resending an update")`).
  - Module helper `normalise_body(text: str, fmt: str) -> str` (JSON: `json.dumps(sort_keys=True, indent=2, ensure_ascii=False)`; XML or unparsable: text with trailing whitespace per line stripped) and `body_diff(before: str, after: str, fmt: str) -> str` (`difflib.unified_diff`, labels `baseline` / `sent`).

`run_raw` behaviour:
1. Validate (path, query, body JSON parses when `fmt == "json"`, required body for POST/PUT when the definition has one) → `InputError` before anything is sent.
2. PUT with a twin: `baseline` required (`InputError("baseline", "load the current record first")`); baseline must be a raw GET record with status 2xx, the twin's path, the same path values and baseline query, else the same InputError.
3. Record: `operation = f"raw {method} {path}"`, `raw=True`, `slug=endpoint.slug`, `inputs={"path":…, "query":…, "format": fmt, "body": body}`, `endpoint`, `wrapped_by`.
4. PUT with a twin: send the GET again (inside this record's requests); if its normalised body differs from the baseline's response body → `refused = "baseline changed"`, no PUT, write record, return.
5. Send `client.raw_request(method, resolve_path(...), params=query, data=parsed_json_or_xml_text, content_type="application/xml" if fmt == "xml" and body else None, custom_headers={"Accept": "application/xml"} if fmt == "xml" else None)`; result normalised and expectations evaluated as `_run` does (share the code, do not copy it).
6. With a baseline: `baseline = {"evidence_id": baseline.id, "body": <baseline response body>}`, `body_diff = body_diff(...)`.

Redaction (`redact.py`): when `inputs` has dict `path` / `query` keys (a raw record), yield every path value (kind = param name) and every query value whose name is not in the non-identifying list (Global Constraints).

- [ ] **Step 1: Failing tests** (use the `lab_client` fixture and patch `make_lab_client` as `test_runner.py` does):
  - `test_raw_get_records_raw_evidence`: GET `/almaws/v1/courses` with `query={"limit": "5"}` → `rec.raw`, `rec.endpoint["path"] == "/almaws/v1/courses"`, request URL ends with `/almaws/v1/courses?limit=5`, expectation `status == 200` passes, file name contains `raw-GET-courses`.
  - `test_query_type_errors_before_sending`: `limit="abc"` → `InputError` field `limit`, `lab_client.http.calls == []`.
  - `test_missing_path_value`: `InputError` field `course_id`, nothing sent.
  - `test_path_values_are_quoted`: value `"a/b c"` → URL contains `a%2Fb%20c`; `match` on the recorded path returns the same values.
  - `test_put_requires_baseline`: no baseline → `InputError` field `baseline`, nothing sent.
  - `test_put_with_baseline_sends_and_diffs` (allow writes via `gate=lambda *a: True`): answers = [baseline GET `{"code":"X","name":"Old"}`, repeated GET same, PUT 200]; `rec.baseline["evidence_id"] == base.id`; `"-  \"name\": \"Old\""` and `"+  \"name\": \"New\""` in `rec.body_diff`; three requests in total across the two records (1 + 2).
  - `test_put_refused_when_record_changed`: repeated GET returns a different body → `rec.refused == "baseline changed"`, no PUT in `http.calls`.
  - `test_failed_baseline_does_not_count`: baseline GET answered 404 → `run_raw` raises `InputError` field `baseline`.
  - `test_xml_put_baseline_and_diff`: `PUT /almaws/v1/bibs/{mms_id}` fmt xml: baseline GET sent with `Accept: application/xml`; PUT sent with `Content-Type: application/xml`; diff present; an invalid-XML baseline still diffs as text.
  - `test_put_without_twin_needs_no_baseline`: the one PUT without a GET twin (find it in the index in the test) runs without a baseline.
  - `test_custom_path`: `custom_endpoint("GET", "almaws/v1/task-lists/requested-resources")` with arbitrary query → sent as given; `rec.endpoint["custom"] is True`.
  - `test_rerun_get_and_rerun_put_needs_fresh_baseline`.
  - `test_old_records_still_load`: a phase-1 record dict without the new keys loads.
  - Redaction: `test_raw_inputs_redacted`: path value and `q` value replaced everywhere, `limit` value kept.
- [ ] **Step 2: Run**; expected FAIL.
- [ ] **Step 3: Implement** per the interface; keep `_run` and `run_raw` sharing a private `_finish(record, value, error, parsed_expectations)` helper.
- [ ] **Step 4: Run** `poetry run pytest tests/unit/lab -q`; expected PASS (phase 1 tests untouched and green).
- [ ] **Step 5: Commit** `feat(lab): run raw calls with baseline-checked updates and raw evidence`.

### Task 4: Headless `endpoints` and `raw` commands

**Files:**
- Modify: `src/almaapitk/lab/cli.py` (module docstring usage lines too)
- Test: `tests/unit/lab/test_cli_raw.py`

**Interfaces:**
- Consumes: Task 1 `load_endpoints`, `match`, `custom_endpoint`, `AREA_TITLES`; Task 2 `wrapped_by`; Task 3 `RawRequest`, `Session.run_raw`, `Session.fetch_baseline`, `load_record`.
- Produces CLI:
  - `almaapitk-lab endpoints [--area AREA] [--search TEXT] [--json]`: one line per endpoint `METHOD /short/path  summary  [→ Domain.method]`; `--json` lists dicts with `method, path, area, summary, writes, wrapped_by, params`.
  - `almaapitk-lab raw METHOD PATH [--query k=v]... [--format json|xml] [--body-file F] [--baseline-query k=v]... [--baseline-out F] [--baseline F] [--expect C]... [--allow-writes] [--confirm-write WORD] [--json]` plus the common `--env/--evidence-dir/--verbose`.
  - `PATH` is concrete; matched with `match`, else run as custom (stderr: `note: not in the Alma API definitions; sending as a custom path`). `--format` defaults to the endpoint's first body format, else json.
  - PUT with a twin: `--baseline-out F` → `fetch_baseline`, write its response body to F, print summary, exit 0 (1 if the GET failed). `--body-file` + `--baseline F` → build a baseline record object from F's text (the CLI loads the evidence record whose id is stored next to F in `F + ".evidence"`, written by `--baseline-out`; if that sidecar is missing → exit 2 with a message to re-run `--baseline-out`), then `run_raw`. PUT body without `--baseline` → exit 2, nothing sent.
  - Gate: Production requires `--confirm-write` equal to `endpoint.confirm_word` (message names the word); Sandbox requires `--allow-writes`. Same refusal messages and exit codes as phase 1 (`_gate_for` generalised to take the word).
  - `refused == "baseline changed"` → stderr explains, exit 1.

- [ ] **Step 1: Failing tests** (drive `cli.main([...])` with the scripted client as `test_cli.py` does): `endpoints --area courses` lists 29 lines; `endpoints --search bibs/{mms_id} --json` includes `wrapped_by`; `raw GET almaws/v1/courses --query limit=5 --expect "status == 200"` exit 0 and summary shows `raw GET /almaws/v1/courses`; unknown path → custom note; PUT without `--baseline` → exit 2, no calls; `--baseline-out` writes the body and sidecar; full PUT with `--allow-writes` exit 0; Production PUT without `--confirm-write` → exit 1 and message contains `PUT courses`; changed record → exit 1.
- [ ] **Step 2: Run**; expected FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `poetry run pytest tests/unit/lab -q`; PASS.
- [ ] **Step 5: Commit** `feat(lab): headless endpoints and raw commands`.

### Task 5: App: Raw branch and raw form (reads)

**Files:**
- Modify: `src/almaapitk/lab/app/operations.py`, `src/almaapitk/lab/app/inputs.py`, `src/almaapitk/lab/app/app.py`, `src/almaapitk/lab/app/lab.tcss` (if needed)
- Test: `tests/unit/lab/test_app_raw.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `OperationsPane.Selected` carries `operation: Operation | Endpoint` (custom path is `custom_endpoint("GET", "")` with a flag `custom=True`). Tree: after the domain branches, a collapsed `Raw · all Alma endpoints` node; children = `AREA_TITLES[area] (count)`; leaves `METHOD  short_path` + ` ✎` for writes + dim ` → first_qualname[ +N]`; last child `custom path…`. Search matches raw short paths and summaries.
  - `InputsPane.load_raw(endpoint: Endpoint) -> Awaitable[None]`: title block per spec §5.4 (incl. "from Alma API definitions, <date>" and the almaapitk line); fields `#raw-path-<name>`, `#raw-query-<name>`, format `Select#raw-format` when two formats, `TextArea#raw-body` for bodies; custom: `Input#raw-method` (`Select` of GET/POST/PUT/DELETE), `Input#raw-custom-path`, `TextArea#raw-custom-query` (`k=v` lines). Expect and Send as phase 1.
  - `InputsPane.raw_request() -> RawRequest` (raises `InputError` with the field id suffix as `field`).
  - `LabApp.select_endpoint(method: str, path: str)` for tests; `action_send` dispatches to `session.run_raw` for endpoints; History opens raw records into the raw form (`load_record` uses `match`/`custom_endpoint` when `record.raw`).
  - Confirm screen: pass `endpoint.confirm_word` instead of `op.name` for raw writes.

- [ ] **Step 1: Failing tests** (Textual pilot, as `test_app_flow.py`): Raw branch exists with 8 area nodes + custom; searching `courses` shows raw leaves; selecting `GET /almaws/v1/courses`, typing `limit=5`, Send → result shows status 200 and evidence `raw`; wrapped endpoint title shows `almaapitk: BibliographicRecords.get_record`; custom path GET sends to the typed path; History reopens a raw record with values filled.
- [ ] **Step 2: Run**; expected FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `poetry run pytest tests/unit/lab -q`; PASS.
- [ ] **Step 5: Commit** `feat(lab): Raw branch and raw call form in the app`.

### Task 6: App: baseline flow for updates and raw writes

**Files:**
- Modify: `src/almaapitk/lab/app/inputs.py`, `src/almaapitk/lab/app/app.py`
- Test: extend `tests/unit/lab/test_app_raw.py`

**Interfaces:**
- Consumes: Task 3 `Session.fetch_baseline`, `run_raw(baseline=...)`; Task 5 form.
- Produces: for a PUT with a twin, a `Baseline` section (`#raw-bq-<name>` fields from the twin's query params, prefilled from same-named PUT query fields until edited), `Button#load-baseline` ("Load current record"), body `TextArea#raw-body` read-only until loaded, Send disabled until `InputsPane.baseline` (an `EvidenceRecord`) matches the current path values + baseline query; editing either clears it. POST bodies prefill `endpoint.body_example` when present. Any body editor also offers `Button#body-from-file` (path prompt, reads UTF-8 text) and `Button#body-from-last` (the last result's response body); for a PUT with a twin these replace the body text only after a baseline is loaded.

- [ ] **Step 1: Failing tests:** Send disabled before baseline; Load current record fills the body from the GET and enables Send; changing a path value disables Send again; `test_send_stays_locked_after_failed_baseline` (404 baseline); full PUT on Sandbox confirms with Enter and the result shows the diff in the Evidence tab; Production PUT confirmation asks for `PUT courses`; changed record → result shows "Not sent: the record changed since you loaded it" and offers reload (button `#reload-baseline`).
- [ ] **Step 2: Run**; FAIL.
- [ ] **Step 3: Implement** (baseline GET in a thread worker like `_call`).
- [ ] **Step 4: Run** `poetry run pytest tests/unit/lab -q`; PASS.
- [ ] **Step 5: Commit** `feat(lab): baseline-first updates for raw PUTs in the app`.

### Task 7: Docs, changelog, full verification, live smoke

**Files:**
- Modify: `docs/site/guides/alma-lab.md` (new "Raw calls" section: tree, form, baseline rule, custom path, headless examples, how to refresh the index with `python -m scripts.build_lab_endpoints`), `CHANGELOG.md` ([Unreleased] → Added), `docs/alma-swagger/README.md` (one line: refreshing the snapshot requires rebuilding the lab index; the sync test enforces it)

- [ ] **Step 1:** Write the docs (placeholders only).
- [ ] **Step 2:** `make check` → all pass; `poetry run pytest tests/unit/lab -q` → all pass.
- [ ] **Step 3:** `poetry build` then `python scripts/ci/check_artifact_contents.py` → no offenders; the wheel lists `almaapitk/lab/data/alma_endpoints.json`.
- [ ] **Step 4:** Live SANDBOX smoke (reads only, `env -u ALMA_PROD_API_KEY`): `poetry run almaapitk-lab raw GET almaws/v1/conf/libraries --expect "status == 200" --evidence-dir <scratch>` → exit 0; `almaapitk-lab raw GET almaws/v1/courses --query limit=2` → exit 0 or an Alma error recorded with tracking id. Do not commit evidence.
- [ ] **Step 5: Commit** `docs(lab): raw calls guide and changelog`.
