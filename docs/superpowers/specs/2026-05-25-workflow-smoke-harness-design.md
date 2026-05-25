# Consumer-Safety Testing Strategy — Design

**Status:** Approved 2026-05-25; revised same day after reading the first
real consumer (`Fetch_Alma_Analytics_Reports`). Originally scoped as a
"workflow smoke harness"; reframed into the broader strategy below once it
became clear the harness is one *layer* of the answer, not the whole answer.
The filename is kept stable because other docs and issue #158 link to it.

## 1. Goal

Trusting a new `almaapitk` version in a consumer project today means
manually re-running every workflow on the `masedet` workstation and
eyeballing the output — about a day of work, which is why production stalls
behind `main`. Worse, a change in `almaapitk` (the shared client) can break
a consumer in a way nobody notices until it runs live.

Build a **layered, repeatable testing strategy** that (a) catches client
changes that would break consumers *as early and cheaply as possible*, and
(b) gradually replaces the manual `masedet` simulation with automated checks
of equal-or-greater certainty. The strategy must be the **same playbook for
every consumer repo**, so onboarding the next repo is mechanical.

## 2. The model — three test layers + one shared infrastructure

This is the canonical model. Every consumer repo is protected by the same
three layers; only the per-repo content differs.

| | Answers | Lives in | Runs | Owns |
|---|---|---|---|---|
| **Infra (plumbing)** | *(not a test)* the reusable toolkit live tests stand on: build-a-client, read-only rail, dry-run, flaky-tolerance, runner | `almaapitk[smoke]` | — | shared |
| **L1 — Contract tests** | "did `almaapitk` change a behavior a consumer relies on?" | **`almaapitk`** | every `almaapitk` change | shared (all consumers) |
| **L2 — Mock/golden tests** | "did *this repo's* logic or its `almaapitk` integration regress?" | **each repo** | every commit, offline | per repo |
| **L3 — Live smoke** | "does it genuinely still work against real Alma?" (the `masedet` replacement) | **each repo** (uses Infra) | before a bump / scheduled | per repo |

### What each layer does and does not catch

- **L1 (contract)** catches a renamed/removed method, a changed return
  *shape* (e.g. a `list` becoming a lazy generator), a dropped keyword
  argument, a changed exception base class — at the source, before a
  version is even cut, for **every** consumer at once. It does **not** know
  any single repo's specific usage.
- **L2 (mock/golden)** runs the *real* `almaapitk` code against *canned*
  Alma responses and asserts the repo's output is unchanged. Catches repo
  logic regressions and integration breakage deterministically and offline.
  It does **not** prove real Alma still works (responses are canned).
- **L3 (live)** is the only layer with real-Alma certainty — real auth,
  real data, real endpoint. It is the genuine replacement for the manual
  `masedet` run. It is slower, needs credentials, and is run less often.

**Key consequence:** mocked layers (L1, L2) are a faster, broader
*regression* net; they do **not** substitute for L3's live certainty. The
"increased certainty over manual" comes from L3 running *more scenarios*
every time, not from automation alone.

## 3. Hard rules (invariants)

- **R-H1 — Build concrete first, generalize second.** Ship what a real repo
  needs; grow shared pieces (verifiers, L1 coverage) *by extraction* when a
  second repo needs them — never speculatively.
- **R-H2 — SANDBOX by default; PRODUCTION is read-only, always.** L3 clients
  targeting PRODUCTION refuse any non-GET request (enforced in the Infra).
- **R-H3 — Missing credentials skip, never fail.** L1/L2 need no creds; L3
  skips cleanly when its environment key is absent.
- **R-H4 — R9 in tests too.** Synthetic placeholder inputs from gitignored
  files; real identifiers/data never printed or committed.
- **R-H5 — Tests that protect against drift must themselves be trustworthy.**
  No error-swallowing that turns a real failure green; assertions must be
  specific (shape + values), not just "didn't throw".
- **R-H6 — Contract-first.** When a consumer reveals a behavior it depends
  on, encode it as an L1 contract test in `almaapitk` *before* (or as well
  as) relying on a per-repo test to catch it — earliest, cheapest, shared.

## 4. Infra layer (shipped — PR #159)

`almaapitk.testing`, installed via the `[smoke]` extra:
`RecordingTransport` (dry-run, no network), the read-only guard
(`ReadOnlyViolation`), `build_smoke_client(...)`, `smoke_input` (gitignored
inputs), `run_with_flaky_tolerance`, the `@workflow` marker + `alma` pytest
fixture, and `make smoke` / `make smoke-live`. The `tests/smoke/` analytics
example is a **self-demo of the kit**, not a consumer's L3 test (L3 lives in
each repo). Unit tests prove the read-only rail blocks writes.

## 5. L1 — Contract tests (the next build)

**Source of truth:** a consumer's almaapitk-usage audit (the model is
`Fetch_Alma_Analytics_Reports/docs/almaapitk-0.4.5-audit.md`, which
enumerates exactly the surface that repo depends on). Each row of such an
audit becomes a contract test in `almaapitk` so the manual audit never has
to be re-done by hand.

**First target — the Analytics contract** (relied on by the analytics repo;
verified against canned analytics responses, no credentials):

- `AlmaAPIClient`, `Analytics`, `AlmaAPIError`, `AlmaValidationError` are importable.
- `AlmaAPIClient("PRODUCTION")` works (environment positional; new params keyword-only).
- `AlmaValidationError` subclasses `ValueError`; typed errors subclass `AlmaAPIError`.
- `Analytics(client).get_report_headers(path)` returns an ordered `list[str]`.
- `Analytics.fetch_report_rows(path, limit=, max_rows=, progress_callback=)`:
  accepts those exact kwargs, returns a **sized** `list` of `dict` rows
  keyed `Column0..N`, and calls `progress_callback` with a cumulative `int`
  per page. *(This pins the `len(rows)` reliance in the consumer's runner.)*
- `limit` outside 25–1000 raises `AlmaValidationError`.

These run in `almaapitk`'s normal unit suite (and its CI), on every change.

## 6. L2 — Mock/golden tests (per repo; pattern already exists)

The analytics repo's `tests/test_diff_harness.py` is the reference pattern:
mock Alma's HTTP responses with committed fixtures, run the *real* `almaapitk`
code + the repo's runner/output, and assert byte/content-identical output
against committed golden files. Other repos copy this pattern. No new
`almaapitk` work required; document it as the canonical L2 recipe.

## 7. L3 — Live smoke (per repo; uses Infra)

Each repo gets a small live smoke that runs its real workflow against real
Alma (read-only) and asserts on real results, built on the Infra layer
(read-only PROD client, flaky tolerance, `smoke_input` for the report path).
This is the per-repo replacement for the `masedet` simulation, and the
"more scenarios than a human would run" is where the extra certainty lives.
Runs standalone (not inside the SANDBOX-only chunks pipeline; R8).

## 8. Onboarding a new consumer repo (the playbook)

1. **Audit** the repo's `almaapitk` usage (which symbols, signatures, shapes,
   error types). Write it down (mirror the analytics audit doc).
2. **L1:** turn each audited behavior into a contract test in `almaapitk`.
   Reuse existing contract tests where the repo shares operations; add new
   ones for new operations.
3. **L2:** ensure the repo has a mock/golden harness for its outputs (copy
   the analytics pattern).
4. **L3:** add a live read-only smoke for its real workflow(s) using the
   Infra layer.
5. **Extract** any verification logic a *second* repo reuses into a shared
   `almaapitk` helper (R-H1).

## 9. Decomposition into child issues (meta-issue #158)

- **Infra** — harness core (#156, delivered in #159).
- **L1** — Analytics domain contract tests in `almaapitk` *(next build)*.
- **L2** — analytics repo already has it; document the pattern; adopt per repo later.
- **L3** — analytics repo live smoke (#157, reframed); per-repo rollout later.
- **Deferred** — mutation/teardown Infra (only for repos with mutating
  workflows), CI integration (run L1 + dry-run L2 on every PR),
  cross-project orchestrator.

## 10. What this design intentionally does NOT do

- Does not claim mocked layers (L1/L2) replace live certainty (L3).
- Does not build speculative shared abstractions (R-H1 — extract on 2nd use).
- Does not run live PROD checks inside the chunks pipeline (R8).
- Does not, in this phase, touch consumer repos beyond reading them; L2/L3
  rollout into each repo is separate, repo-by-repo work.
