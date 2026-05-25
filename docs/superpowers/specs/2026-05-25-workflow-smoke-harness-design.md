# Workflow Smoke-Test Harness — Design

**Status:** Approved 2026-05-25. Source: brainstorming session on making
"validate a version" a command instead of a manual day on the `masedet`
workstation.

## 1. Goal

Today, trusting a new version of `almaapitk` (or a downstream consumer
project) means manually re-running every workflow on the `masedet`
workstation and eyeballing the results — roughly a day of work, which is
why prod has stalled on `0.3.1` while `main` is at `0.4.5`+.

Ship a **reusable workflow smoke-test harness inside `almaapitk`** so that
each consumer project can capture its real workflows as small automated
checks, and "did this version break anything?" becomes a single command
returning green/red in seconds.

This spec covers the **shared harness plus one pilot**. Rolling the harness
out to each consumer repository is explicitly out of scope here (separate
follow-on issues, one per repo).

## 2. Hard rules (invariants)

These are the non-negotiable principles. They also seed the tracking
meta-issue's "principles" section.

- **R-H1 — Build concrete first, generalize second.** The base ships with
  what the pilot demonstrably needs plus the obvious shared primitives —
  never speculative components. The base is *expected to grow* as real
  projects adopt it; that growth is a blessed way of working, not scope
  creep.
- **R-H2 — SANDBOX by default; PRODUCTION is read-only, always.** Each
  workflow declares its target environment. A workflow targeting
  PRODUCTION may only read — the harness hands it a client that **refuses**
  any non-GET request, so a test can never mutate live data.
- **R-H3 — Missing credentials skip, never fail.** A live check whose
  environment credentials are absent is reported `skipped`, not `failed`,
  so the suite is runnable anywhere (including credential-free CI).
- **R-H4 — R9 holds in tests too.** Workflow inputs (IDs, report paths,
  vendor codes, …) are synthetic placeholders loaded from a gitignored
  file; real identifiers and fetched data are never printed to shared
  output or committed. Output is run through the existing redactor.
- **R-H5 — The harness tests itself (R10).** Every harness component has
  unit tests, including one that proves the R-H2 read-only rail actually
  blocks a write attempt against PRODUCTION.

## 3. Architecture overview

The harness ships as a new `almaapitk.testing` package, installed via an
optional extra so the core library stays lean for normal consumers:

```
pip install almaapitk[smoke]      # pulls pytest + the harness
```

It is built on **pytest** (the standard Python test runner) — workflow
smokes are ordinary pytest tests that use the harness's fixtures and
helpers. A thin wrapper command (`make smoke`) hides pytest flags so the
day-to-day interface is one friendly command.

Components (v1):

| Component | Responsibility |
|---|---|
| `client` fixture/builder | Hand a workflow a ready-to-use `AlmaAPIClient` for its declared environment, using the `api_key=` injection from #143. For a PRODUCTION + read-only workflow, the returned client is wrapped to refuse non-GET requests (R-H2). |
| dry-run transport | A fake transport that **records** the requests a workflow would make and sends nothing — lets a workflow's wiring be validated with no credentials and no live calls. |
| `@workflow(...)` declaration | A marker each smoke carries: `name`, `environment` (`SANDBOX`/`PRODUCTION`), `readonly`. Drives fixture selection and the read-only rail. |
| request-checks vs response-checks | Request-checks ("it asked Alma for the right thing") run in dry-run **and** live; response-checks ("what came back is correct") run **live only**. |
| test-input loader | Reads synthetic inputs from a gitignored `smoke-data.json`-style file; clear error when an expected input is missing. |
| redaction | Reuses `almaapitk.alma_logging` redaction so output never leaks IDs/credentials (R-H4). |
| flaky-API tolerance | Retries transient `5xx`/`429`, then marks the check `skipped (transient API error)` rather than failed. |
| runner wrapper | `make smoke` (dry-run + any live checks whose creds are present) and `make smoke-live`. Underneath: pytest. |

Deferred (each a later child issue, built on real demand — R-H1):

- **Mutation + teardown** (create/update/delete in SANDBOX with guaranteed
  cleanup). The genuinely hard part; deliberately not in v1.
- **CI integration** — run the dry-run smokes on every PR (credential-free).
- **Cross-project orchestrator** — run all consumer repos' suites and tally.
- **Rollout** — adopt the harness in each consumer repo (one issue per repo).

## 4. Run modes and data flow

- **Dry-run** (default, no credentials): the workflow executes against the
  dry-run transport. Outgoing requests are recorded; **request-checks** are
  evaluated; **response-checks are skipped** (there is no real response).
  Proves the plumbing. Runs anywhere, including CI.
- **Live** (credentials present): the workflow executes against a real
  `AlmaAPIClient` for its environment. Request-checks **and** response-checks
  are evaluated. A live check whose env credentials are absent is `skipped`
  (R-H3). Transient API errors are retried, then `skipped` (§5).

## 5. Error handling

- **Missing credentials for the target env** → `skipped`, with reason.
- **Transient API failure** (`5xx`, `429`) → retried a small fixed number of
  times; if still failing, `skipped (transient API error)` so a flaky Alma
  (e.g. the analytics 500s observed 2026-05-25) never cries wolf.
- **Write attempted against a PRODUCTION/read-only client** → hard error
  (the R-H2 rail fired); this is a real bug in the workflow, surfaced loudly.

## 6. Pilot — `analytics-report-fetch` (PRODUCTION, read-only)

Chosen because it is read-only (no teardown needed) yet exercises the full
harness, and because it forces honest environment handling on day one:
**Analytics has no SANDBOX endpoint — it only works against PRODUCTION**
(single shared analytics DB). So the pilot is inherently a PRODUCTION
read-only workflow.

```python
@workflow(name="analytics-report-fetch", environment="PRODUCTION", readonly=True)
def analytics_report_fetch(alma):
    report_path = test_input("analytics_report_path")   # gitignored placeholder

    headers = alma.analytics.get_report_headers(report_path)   # request-check: hit analytics reports endpoint w/ path
    rows    = list(alma.analytics.fetch_report_rows(report_path, max_rows=5))

    assert headers, "report returned no column headers"        # response-check (live only)
    assert rows,    "report returned no rows"                  # response-check (live only)
```

- **Dry-run:** always runs; asserts the workflow issues the right analytics
  request with the configured path. No credentials needed.
- **Live (PROD, read-only):** runs when `ALMA_PROD_API_KEY` (or an injected
  key) is present; `skipped` otherwise (R-H3). The client is the
  read-only-pinned PROD client (R-H2).
- **R9:** `analytics_report_path` is a placeholder from the gitignored
  inputs file; report rows are never printed or committed.
- **R8 footnote:** because the chunks pipeline is SANDBOX-only (refuses a
  prod key), this live smoke runs **standalone** (local / `masedet` /
  CI-with-secret), not inside a chunk run.

## 7. Testing the harness itself (R-H5 / R10)

Unit tests under `tests/unit/` (and regressions under
`tests/unit/regressions/` for any bug found):

- dry-run transport records the intended request(s) and sends nothing;
- the **read-only rail blocks a write** against a PRODUCTION/read-only
  client (the load-bearing safety test);
- redaction strips IDs/credentials from rendered output;
- the input loader raises a clear error on a missing key;
- transient-error classification → `skipped`, real failure → `failed`.

The pilot itself is the harness's first integration smoke.

## 8. Decomposition into child issues (meta-issue checklist)

**v1 (this effort):**

1. **Harness core** — `almaapitk.testing` package + `[smoke]` extra: client
   fixture (env-aware, #143 injection, PROD read-only wrapper), dry-run
   transport, `@workflow` declaration + request/response-check split,
   input loader, redaction wiring, flaky-API tolerance, `make smoke`
   wrapper. Ships with its own unit tests including the read-only-rail
   proof (R-H5).
2. **Pilot** — the `analytics-report-fetch` smoke (dry-run + live read-only
   PROD), serving as the copy-me template.

**Deferred (later children, built on real demand — R-H1):**

3. Mutation + teardown framework.
4. CI integration (dry-run smokes on every PR).
5. Cross-project orchestrator.
6. Rollout to each consumer repo (one issue per repo).

## 9. What this design intentionally does NOT do

- Does not run mutating workflows in v1 (R-H1; deferred to child #3).
- Does not touch the consumer repositories (rollout is child #6+).
- Does not invent a custom test runner or a config-only workflow language —
  it uses pytest and thin Python per workflow (rejected alternatives from
  the brainstorm).
- Does not run live PROD checks inside the chunks pipeline (R8).

## 10. Open questions / risks

- **Analytics PROD flakiness** — mitigated by the transient-error → skip
  policy (§5); the live pilot may often skip rather than pass on a bad
  Alma day. Acceptable: dry-run still gates wiring.
- **`make` availability on `masedet`/CI** — if `make` is awkward, the
  wrapper can instead be a console script (`almaapitk-smoke`) or
  `python -m almaapitk.testing`. Decide at implementation time.
