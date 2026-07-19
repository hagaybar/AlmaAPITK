# Chunk Backlog

_Last rendered: 2026-07-19T12:05:38Z_

> **Generated artifact** — do not hand-edit. Source: `docs/chunks-backlog.yaml`.
> Regenerate with `scripts/agentic/chunks render-backlog`.
> CI runs `--check`; PRs that touch the YAML must include the regenerated markdown.

**Total chunks:** 70
**Total issues:** 97

**Status:** Suggested groupings — revise freely. The chunking is your call; this doc removes the "what do I chunk next" decision fatigue.
**Inputs used:** `docs/issue-finalization-report-2026-05-01.md`, `docs/issue-audit-2026-05-01.md`, handbook §10.1 wave structure, CLAUDE.md priority/prereq notes, `docs/reviews/2026-05-12-release-0.4.x-review.md` (post-0.4.3 retrospective).

---

## How to read this

Each chunk shows:

- **Name** (becomes `chunks/<name>/`)
- **Issues** (becomes `--issues` flag)
- **Phase** — recommended pickup order (do phase 1 before phase 2, etc.)
- **Risk** — low / med / high (drives whether you stay solo at that chunk's breakpoints)
- **Prereqs** — issues that should be merged before this chunk runs
- **Audit flag** — if the issue carried a Not-aligned or needs-decision flag in the finalization report
- **Notes** — anything specific (fixtures, gotchas, why grouped)
- **Status** — derived from GitHub state at render time, never stored here

Single command to start:

```bash
scripts/agentic/chunks define --name <name> --issues <comma-list>
```

Skip any chunk freely. Chunks are independent of each other within a phase, except where Prereqs say otherwise.

**Note on renumbering (2026-05-12):** Phase IDs 4–6 were inserted to capture post-0.4.x review work and deprecation migrations; old Phase 4 (Configuration) is now Phase 7, etc. Phase 16 captures pipeline/dev-experience improvements that surfaced from running the pipeline at scale.

---

## Phase 1 — HTTP foundation (architecture)

Lowest-risk, highest-leverage. Every later chunk benefits from these landing first. Pilot phase per handbook §9.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 1 | ✅ merged | `http-session-and-request` | #3, #4 | med | none | clean | **Recommended pilot.** #4 hard-depends on #3 (consolidated `_request()` requires the session). Touches core client; review carefully. Test fixture: any user_primary_id (read smoke). |
| 2 | ✅ merged | `http-retry` | #5 | med | #3, #4 | clean | Mostly mock-tested; SANDBOX won't reliably emit 429/503. Mark some ACs as `unmappable` and verify in unit tests. |
| 3 | ✅ merged | `http-timeout-and-region` | #6, #7 | low | #3 | #7 partially aligned (region map: APAC has two endpoints `api-ap`+`api-aps`; China is `.com.cn`) | #7 audit fix is in the issue body already (rewritten). Both are config knobs. |
| 4 | ✅ merged | `logger-cleanup` | #14 | low | none | clean | Mechanical multi-file. Replaces `print()` with logger. Solo for clean diff inspection. |

## Phase 2 — Errors and ergonomics

Quality-of-life improvements that change how every later chunk behaves at the edges.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 5 | ✅ merged | `errors-mapping` | #9, #10 | low | none | clean | Closely related: #10 propagates `trackingId`/`errorCode`; #9 maps codes to subclasses. Land together for one cohesive error taxonomy PR. Fixture: a known-bad call (e.g., GET `/users/INVALID`). |
| 6 | ✅ merged | `client-ergonomics` | #13, #16 | low | none | clean | Both narrow internal cleanups (context-manager + exception cleanup + `AlmaResponse.data` caching). Low risk, single small PR. |
| 7 | ✅ merged | `pagination-helper` | #11 | low | #4 | clean | Adds `iter_paged()` public symbol. Fixture: a list endpoint with > limit results (e.g., `users` list). |

## Phase 3 — Quality and distribution

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 8 | · planned | `hierarchical-accessors` | #15 | low | none | clean | Adds `client.acq`, `client.bibs`, etc. as lazy properties. **Soft prereq:** new domain bootstraps land first or the accessor map is incomplete. You can also defer this until all domains exist. |
| 9 | ✅ merged | `pypi-publish-ready` | #1, #17 | low | none | clean | Distribution-only: OIDC release flow (#1) + LICENSE file (#17). **Owner-side decision needed first:** MIT vs Apache-2.0 (audit's prioritized next-action #6). #1 may now be a duplicate of #128 (`pipeline-pypi-publish`) — verify before chunking. |
| 10 | ✅ merged | `logger-noise-fix` | #2 | low | none | clean | Bug fix, not enhancement. Quick. The audit's per-issue note suggested labelling as `bug`. |
| 11 | ✅ merged | `pipeline-pypi-publish` | #128 | low | none | clean | Post-0.4.x. Replace manual `twine upload` with tag-triggered GitHub Actions workflow using PyPI Trusted Publishing (OIDC). Removes the four-version-bump risk of the 0.4.x cycle's manual release flow. Off-pipeline candidate (one workflow file + docs). Likely supersedes #1. |

## Phase 4 — Release quality & next-release-risk reducers (post-0.4.x review)

Filed from the 2026-05-12 0.4.x retrospective (`docs/reviews/2026-05-12-release-0.4.x-review.md`). HIGHEST current priority — these reduce the chance that the next release repeats the 0.4.0→0.4.3 four-bump pattern. Small, cohesive, shares files across tests/meta, tests/unit/regressions, CLAUDE.md, users.py, acquisition.py.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 12 | ✅ merged | `release-quality-cluster` | #131, #132, #133, #134, #135, #136, #137, #138 | low | none | clean | Eight tickets from one review. #131 (meta-tests trio scope-widened), #132 (Users.__init__ alma_logging refactor), #133 (bare-except + ast guard), #134 (R10 backfill for #114), #135 (canonical R10 home), #136 (401129 race docstring), #137 (gitignore swagger caches), #138 (close-then-switch test). All small. Land together for one cohesive "harden next release" PR. Splitting is fine if scope review dictates, but the testing infrastructure (#131, #133, #135) wants to land in one file commit. |

## Phase 5 — Deprecation migrations (must precede related coverage)

Three-stage public-API renames. Must land BEFORE any new coverage method that uses the old name — otherwise the new method is migrated twice. `#120` is gating for `#74` (ResourceSharing partner CRUD); `#111` has no current coverage blocker but locks in `Configuration` as the canonical name.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 13 | · planned | `partners-rename` | #120 | high | none | clean | 3-stage migration: (1) add `Partners` as alias, (2) `DeprecationWarning` on `ResourceSharing` import, (3) cutover after a release cycle. **Hard prereq for `#74`** (rs-partners chunk in Phase 13) — otherwise the partner CRUD ships into a name that's about to be deprecated. Solo, careful review. |
| 14 | · planned | `admin-deprecate` | #111 | high | none | clean | Mirror of `partners-rename`. 3-stage: `Configuration` alias for `Admin`, deprecation warning, cutover. No current Admin coverage tickets, so timing is opportunistic — pair with `partners-rename` for review economy. Solo, careful review. |

## Phase 6 — Documentation overhaul

Public-facing docs lag the public API by 0.2.x. README and API reference are out of sync with v0.4.3 (Configuration / typed errors missing from tables, `Version: 0.2.0` headings on a 0.4.3 release). This phase ships the docs catch-up.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 15 | · planned | `docs-overhaul` | #118 | low | none | clean | README + API reference + examples + migration guides. Large scope; likely its own session. Coordinate with #131 meta-test (`test_top_level_docs_match_all`) — if that test lands first, this chunk closes the failing assertions. If this lands first, the meta-test is born green. |

## Phase 7 — Configuration domain (high priority, post-architecture)

The largest cluster. #22 is the foundation; #23 is independent (extends Admin); the rest depend on #22.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 16 | ✅ merged | `config-bootstrap` | #22 | low | none | clean | Foundation. Empty class; almost trivial. **Blocks all of #24–#35.** |
| 17 | ✅ merged | `config-sets` | #23 | med | none | clean | Substantial CRUD + member ops with `op` query param. State-changing — round-trip test with cleanup. |
| 18 | ✅ merged | `config-orgs-and-locations` | #24, #25 | low | #22 | clean | Both organizational structure (libraries, departments, circ-desks, locations). Read-heavy with one PUT. Shared fixture: library code, location code. |
| 19 | ✅ merged | `config-tables` | #26, #27 | low | #22 | #26 partially aligned (drop undocumented `scope` param) | Lookup tables: code-tables + mapping-tables. Already rewritten. |
| 20 | · planned | `config-jobs` | #28 | med | #22 | clean | 8 endpoints — biggest of Configuration. Solo. Fixture: known job ID; ability to run a benign job for round-trip. |
| 21 | ✅ merged | `config-readonly-profiles` | #30 | low | #22 | clean | Read-only deposit + import profiles. Quick. |
| 22 | · planned | `config-license-terms` | #31 | med | #22 | clean | Full CRUD; round-trip with cleanup. |
| 23 | ⚠ partial | `config-hours-and-letters` | #32, #33 | low | #22 | clean | Smaller endpoints; library-tied config. |
| 24 | ⚠ partial | `config-reminders-and-workflows` | #34, #35 | low | #22 | clean | Two standalone smaller pieces; group for review economy. |
| 25 | · planned | `config-int-str-cleanup` | #139 | low | #22, #11 | clean | Post-0.4.x review. Replace `'100'`/`'0'` strings with ints in `Configuration.list_*` params; or migrate to `iter_paged()`. ~10 call sites. Fold into the next Configuration PR rather than its own chunk if appetite is small. |

## Phase 8 — Users domain (high priority)

Diverse scope. Bootstrap exists already; #36–#45 each add a different user-side capability. #119 adds user-note helpers (post-0.4.x).

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 26 | ✅ merged | `users-list-and-search` | #36 | low | none | #36 partially aligned (signature narrower than docs) | Already rewritten with documented optional filters. Read smoke. |
| 27 | ✅ merged | `users-crud` | #37 | high | none | clean | State-changing (create + delete user). **Use a dedicated test prefix** (e.g., `tau-test-*`) for the user_primary_id so cleanup is guaranteed. |
| 28 | · planned | `users-auth` | #38 | high | none | clean | POST `/users/{id}` with `op=auth` / `op=refresh`. Sensitive (involves password). Isolate. Use the test user from chunk 21. |
| 29 | ✅ merged | `users-attachments` | #39 | med | none | #39 partially aligned (multipart vs JSON unclear at impl) | Open question flagged in body — verify response shape during impl. Round-trip with cleanup. |
| 30 | ✅ merged | `users-loans` | #40 | high | none | #40 partially aligned (query vs body params, item_pid alternative, user_id_type) | Already rewritten. Round-trip needs test user + test item barcode. |
| 31 | ✅ merged | `users-requests` | #41 | med | none | clean | Regular user requests (POST/GET/PUT/DELETE for `/users/{id}/requests`). Shipped 2026-05-10 via PR #125. #42 (RS) and #43 (purchase requests) split out into `users-requests-followup` to allow incremental delivery. |
| 32 | ✅ merged | `users-requests-followup` | #42, #43 | med | none | clean | Follow-up to `users-requests`. #42 (resource-sharing requests) and #43 (purchase requests) — both `priority:high`, same shape as #41. Mirrors the request/cancel/action pattern already shipped. Test user fixture reused. |
| 33 | ▶ in-flight | `rs-borrowing-ergonomics` | #197, #194 | low | none | clean | Second follow-up to `users-requests-followup` (#42), from the 2026-07-19 SANDBOX borrowing-request session. #197 adds `build_user_rs_request(...)`, encoding the body-wrapping rules exactly once (`owner` **plain string**; `format` / `citation_type` / `pickup_location` wrapped `{"value": ...}`; `pickup_location_type` plain). #194 adds an opt-in `validate=` guardrail for the borrowing code-table fields plus a hint when Alma returns its unrenderable `Invalid field value. Field: [Ljava.lang.Object;@… Value: {1}` shape. Both are pure-Python, offline-unit-testable, **no client changes** — hence low risk. Keep the raw-dict path on `create_user_rs_request` working unchanged (back-compat). R10: regression tests land at `tests/unit/regressions/test_issue_197.py` and `test_issue_194.py`. |
| 34 | · planned | `rs-borrowing-reliability` | #198, #196 | high | #197 | #198 partially aligned (401929/401930 are empirical, not in the swagger snapshot; 401607/401608/402039/60340/60258 ARE documented and are free additions) | Companion to `rs-borrowing-ergonomics`; **run it second**. #198 adds typed `AlmaAPIError` subclasses for the RS-create outcomes via the existing `ERROR_CODE_REGISTRY` (`client/AlmaAPIClient.py:308`) — cheap, additive. #196 is the priority:high one: `external_id` idempotency key, `reconcile_on_timeout` (reuses the existing `get_user_rs_request(request_id_type="external")` lookup), a typed `AlmaTimeoutError` wrapping `requests` timeouts, and a per-call `timeout=`. **Scope flag:** `_request()` already accepts `timeout=` (`AlmaAPIClient.py:824`, `:889`) but **none of the `get`/`post`/`put`/`delete` wrappers forward it** (lines 925-1000) — so #196 requires a cross-cutting change to the shared HTTP path every consumer repo uses. That's what makes this chunk high-risk, not the RS logic. Depends on #197 for the builder to carry `external_id`. R10: `tests/unit/regressions/test_issue_198.py`, `test_issue_196.py`. |
| 35 | · planned | `rs-list-user-requests` | #199 | med | none | #199 NOT ALIGNED — the GET-collection endpoint is absent from the swagger snapshot | **Deferred pending a live SANDBOX probe — do not define as a chunk until the endpoint is confirmed.** `docs/alma-swagger/users.json` publishes only `post` on `/almaws/v1/users/{user_id}/resource-sharing-requests`; `get` exists solely on the `/{request_id}` sub-path. Same undocumented-GET-collection risk class as #175 (`list_user_attachments`). Not a hard prereq for `rs-borrowing-reliability` — #196's reconcile path uses lookup-by-`external_id`, not a list call. If a probe confirms the endpoint responds, this becomes a routine `iter_paged`-backed list method. |
| 36 | ✅ merged | `users-fines-and-deposits` | #44, #45 | med | none | #44 partially aligned (op=pay/amount=ALL fix) | Already rewritten. Action-driven (pay/waive/dispute/restore for #44). |
| 37 | ✅ merged | `users-notes` | #119 | med | none | clean | Post-0.4.x. Add `add_user_note` / `list_user_notes` / `remove_user_note` helpers. New surface; mirror existing Users patterns (validate inputs, log entry, raise `AlmaValidationError` / `AlmaAPIError`). |

## Phase 9 — Bibs domain (medium priority)

Mostly read + tightly bounded CRUD. Two audit Not-aligned cases (#52, #57). #103 adds SRU-based keyword search (post-0.4.x).

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 38 | · planned | `bibs-holdings-and-items` | #46, #47 | med | none | #46 partially aligned (`bib` not `override_attached_items`); #47 partially aligned (`bib` not `bibs`, missing `override`) | Already rewritten. Both complete CRUD on tightly related concepts. Test fixture: dedicated test bib MMS. |
| 39 | · planned | `bibs-portfolios-and-ecollections` | #48, #54 | low | #66 | clean | Both bib-level electronic resource access; #48 is CRUD, #54 is read-only. |
| 40 | · planned | `bibs-requests` | #49, #50 | med | none | #49 partially aligned (missing `user_id`/`user_id_type`/`allow_same_request`) | Bib-level + item-level requests. Highly parallel. |
| 41 | · planned | `bibs-loans` | #51 | high | none | #51 partially aligned (query vs body confusion, `op=renew` only) | Already rewritten. Solo for review. |
| 42 | · planned | `bibs-booking` | #52 | high | none | #52 NOT ALIGNED (`period` mandatory `int`, missing `period_type`, `consider_dlr`) | Already rewritten. Verify `period` integer requirement and `consider_dlr` semantics in SANDBOX before final commit (audit's next-action #9). |
| 43 | · planned | `bibs-collections-and-reminders` | #53, #55 | low | none | clean | Both standalone CRUD; group for review economy. |
| 44 | · planned | `bibs-authorities` | #56 | high | none | #56 partially aligned (`authority_xml` not `marc_xml`; missing `normalization`/`override_warning`/`check_match`/`import_profile`) | Already rewritten. Authority XML wrapper; not raw MARC. Solo. |
| 45 | · planned | `bibs-record-ops` | #57 | high | none | #57 NOT ALIGNED (only `op=unlink_from_nz` documented; `suppress_bib`/`unsuppress_bib` removed) | Already rewritten — the original `suppress` wrappers must NOT be reintroduced. Solo. |
| 46 | · planned | `bibs-sru-search` | #103 | med | none | clean | Post-cleanup-monolith. Replaces the removed `search_records()` with an SRU-based keyword-search method. Needs SRU CQL knowledge; design pass recommended before chunking. Off-pipeline candidate if scope is well-bounded. |

## Phase 10 — Acquisitions

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 47 | · planned | `acq-vendors-and-funds` | #58, #59 | med | none | #58 partially aligned (lowercase status, missing `type` filter); #59 partially aligned (op only `activate`/`deactivate`; transfers via #60) | Already rewritten. Top-level acquisition entities. |
| 48 | · planned | `acq-fund-transactions` | #60 | high | #59 | clean | State-changing fund operations (allocate/transfer). Round-trip with cleanup. **Reserve a test fund** so production funds aren't touched. |
| 49 | · planned | `acq-pol` | #61 | high | none | #61 partially aligned (`reason` not `reason_code`; missing `inform_vendor`/`override`/`bib`) | Already rewritten. Cancel POL is destructive; round-trip with a dedicated test POL. |
| 50 | · planned | `acq-attachments` | #62 | med | none | clean | Invoice attachments. Open question flagged: base64 vs multipart upload semantics (audit's next-action #10) — verify in SANDBOX. |
| 51 | · planned | `acq-licenses` | #63 | med | none | clean | 15 endpoints — biggest single chunk in Acq. Mostly CRUD. |
| 52 | · planned | `acq-lookups` | #64 | low | none | clean | Read-only lookups (currencies + fiscal periods). Quickest in this phase. |
| 53 | · planned | `acq-purchase-requests` | #65 | med | none | #65 partially aligned (op constrained to `approve`/`reject`; reject needs reason) | Already rewritten. |

## Phase 11 — Electronic

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 54 | ✅ merged | `electronic-bootstrap` | #66 | low | none | clean | Foundation. **Blocks #67, #68, #69.** |
| 55 | · planned | `electronic-coverage` | #67, #68, #69 | med | #66 | #69 partially aligned (`limit` default 10 not 100; no `q` param) | Already rewritten. e-collections + e-services + portfolios share fixtures and patterns. **All three together** is fine — same shape; one PR is enough. |

## Phase 12 — TaskLists

Three of four tickets in this phase are previously-flagged. Take care.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 56 | · planned | `tasklists-bootstrap` | #70 | low | none | clean | Foundation. **Blocks #71, #72, #73.** |
| 57 | · planned | `tasklists-requested-resources` | #71 | high | #70 | #71 partially aligned (`library`+`circ_desk` mandatory; only `op=mark_reported`; dropped invented `request_ids`) | Already rewritten. |
| 58 | · planned | `tasklists-lending-requests` | #72 | high | #70 | #72 NOT ALIGNED (proposed ship/receive don't map to that endpoint; only `op=mark_reported`) | Already rewritten. Audit's next-action #2 calls for a separate partner-side follow-up ticket — don't try to add ship/receive helpers here. |
| 59 | · planned | `tasklists-printouts` | #73 | high | #70 | #73 partially aligned (no `POST /printouts/create`; documented `op=mark_as_printed`/`mark_as_canceled` only) | Already rewritten. `create_printout` was removed. |

## Phase 13 — ResourceSharing

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 60 | · planned | `rs-partners` | #74 | med | #120 | #74 partially aligned (no `q`/`type_filter`; documented filter is `status`) | Already rewritten. **Hard prereq: `partners-rename` (#120) must land first** — otherwise this chunk ships partner CRUD into a name that's about to be deprecated. |
| 61 | · planned | `rs-directory-members` | #78 | high | #120 | #78 NOT ALIGNED (`localize` POST has no body params; `localization_data` was invented) | Already rewritten — bodyless POST. Solo. Same `#120` prereq as `rs-partners`. |

## Phase 15 — Analytics

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 62 | · planned | `analytics-paths` | #79 | low | none | #79 partially aligned (root `/paths` endpoint — `{path}` is optional) | Already rewritten with single `get_analytics_paths(path=None)`. **Memory note: analytics is PRODUCTION-only** (per project memory `feedback_analytics_prod_only.md`). The SANDBOX test for this MUST use the PROD client + `ALMA_PROD_API_KEY`, BUT R8 forbids the prod key in the orchestration env. **This chunk requires manual SANDBOX-step substitution OR explicit user approval to relax R8 just for this test.** Likely: mark all paths-related ACs `unmappable` and verify by hand. |

## Phase 16 — Pipeline & dev-experience improvements

Improvements to the chunk pipeline itself, surfaced from running it at scale across 0.4.x. Not user-facing; affects how future chunks are run.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 63 | · planned | `pipeline-swagger-enrich` | #123 | med | none | clean | Enrich `_swagger_*.json` sidecars with per-endpoint description/requestBody/responses so the implement agent has structured context instead of just error codes. Pipeline internals only. |
| 64 | · planned | `re-verify-create-user-request` | #129 | low | none | clean | Calendar-tied: re-verify `Users.create_user_request` live SANDBOX behavior around 2026-05-25. Not really a chunk — surface here so it isn't forgotten; execute as a one-shot when the date arrives. |

## Phase 17 — Advanced architecture (deferred until coverage stabilizes)

The handbook recommends doing these in wave 7, after most of the high-priority coverage has merged. Each is non-trivial; some change patterns.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 65 | · planned | `rate-limiting` | #8 | high | #3, #4, #5 | clean | Rolling-window throttler. Hard to validate in SANDBOX. |
| 66 | · planned | `async-bulk` | #18 | high | #3, #4 | clean | Sibling async client + `bulk_call`. Big surface; mostly mock-tested. |
| 67 | · planned | `marc-layer` | #19 | high | #46 | clean | Optional `pymarc` integration; needs careful design review. |
| 68 | · planned | `openapi-validation` | #20 | high | none | clean | Optional opt-in validator vendoring Ex Libris specs. Defer until specs are stable. |
| 69 | · planned | `batch-runner` | #21 | high | #18 | clean | DataFrame batch orchestrator built on #18 async. |
| 70 | · planned | `pydantic-models` | #12 | high | none | clean | Schema-derived models. Defer to last; benefits most from real fixtures. |

## Blocked — resolve before chunking

| Issue | Title | Blocker |
|---|---|---|
| #29 | Coverage: Configuration: integration profiles CRUD | Audit conflict on whether DELETE endpoint exists. Resolve by checking the live developer-network page, then either chunk it or close it. Carries `needs-decision` label. |

> **Note:** the deferred chunks (phase 17) are aspirational. They're listed for completeness so #8/#12/#18–#21 don't get forgotten. You may decide some of them are not worth the effort given the toolkit's actual usage patterns.
