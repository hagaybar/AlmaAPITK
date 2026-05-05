# Chunk Backlog

_Last rendered: 2026-05-05T09:35:34Z_

> **Generated artifact** — do not hand-edit. Source: `docs/chunks-backlog.yaml`.
> Regenerate with `scripts/agentic/chunks render-backlog`.
> CI runs `--check`; PRs that touch the YAML must include the regenerated markdown.

**Total chunks:** 59
**Total issues:** 79

**Status:** Suggested groupings — revise freely. The chunking is your call; this doc removes the "what do I chunk next" decision fatigue.
**Inputs used:** `docs/issue-finalization-report-2026-05-01.md`, `docs/issue-audit-2026-05-01.md`, handbook §10.1 wave structure, CLAUDE.md priority/prereq notes.

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
| 6 | · planned | `client-ergonomics` | #13, #16 | low | none | clean | Both narrow internal cleanups (context-manager + exception cleanup + `AlmaResponse.data` caching). Low risk, single small PR. |
| 7 | · planned | `pagination-helper` | #11 | low | #4 | clean | Adds `iter_paged()` public symbol. Fixture: a list endpoint with > limit results (e.g., `users` list). |

## Phase 3 — Quality and distribution

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 8 | · planned | `hierarchical-accessors` | #15 | low | none | clean | Adds `client.acq`, `client.bibs`, etc. as lazy properties. **Soft prereq:** new domain bootstraps land first or the accessor map is incomplete. You can also defer this until all domains exist. |
| 9 | ⚠ partial | `pypi-publish-ready` | #1, #17 | low | none | clean | Distribution-only: OIDC release flow (#1) + LICENSE file (#17). **Owner-side decision needed first:** MIT vs Apache-2.0 (audit's prioritized next-action #6). |
| 10 | · planned | `logger-noise-fix` | #2 | low | none | clean | Bug fix, not enhancement. Quick. The audit's per-issue note suggested labelling as `bug`. |

## Phase 4 — Configuration domain (high priority, post-architecture)

The largest cluster. #22 is the foundation; #23 is independent (extends Admin); the rest depend on #22.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 11 | · planned | `config-bootstrap` | #22 | low | none | clean | Foundation. Empty class; almost trivial. **Blocks all of #24–#35.** |
| 12 | · planned | `config-sets` | #23 | med | none | clean | Substantial CRUD + member ops with `op` query param. State-changing — round-trip test with cleanup. |
| 13 | · planned | `config-orgs-and-locations` | #24, #25 | low | #22 | clean | Both organizational structure (libraries, departments, circ-desks, locations). Read-heavy with one PUT. Shared fixture: library code, location code. |
| 14 | · planned | `config-tables` | #26, #27 | low | #22 | #26 partially aligned (drop undocumented `scope` param) | Lookup tables: code-tables + mapping-tables. Already rewritten. |
| 15 | · planned | `config-jobs` | #28 | med | #22 | clean | 8 endpoints — biggest of Configuration. Solo. Fixture: known job ID; ability to run a benign job for round-trip. |
| 16 | · planned | `config-readonly-profiles` | #30 | low | #22 | clean | Read-only deposit + import profiles. Quick. |
| 17 | · planned | `config-license-terms` | #31 | med | #22 | clean | Full CRUD; round-trip with cleanup. |
| 18 | · planned | `config-hours-and-letters` | #32, #33 | low | #22 | clean | Smaller endpoints; library-tied config. |
| 19 | · planned | `config-reminders-and-workflows` | #34, #35 | low | #22 | clean | Two standalone smaller pieces; group for review economy. |

## Phase 5 — Users domain (high priority)

Diverse scope. Bootstrap exists already; #36–#45 each add a different user-side capability.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 20 | · planned | `users-list-and-search` | #36 | low | none | #36 partially aligned (signature narrower than docs) | Already rewritten with documented optional filters. Read smoke. |
| 21 | · planned | `users-crud` | #37 | high | none | clean | State-changing (create + delete user). **Use a dedicated test prefix** (e.g., `tau-test-*`) for the user_primary_id so cleanup is guaranteed. |
| 22 | · planned | `users-auth` | #38 | high | none | clean | POST `/users/{id}` with `op=auth` / `op=refresh`. Sensitive (involves password). Isolate. Use the test user from chunk 21. |
| 23 | · planned | `users-attachments` | #39 | med | none | #39 partially aligned (multipart vs JSON unclear at impl) | Open question flagged in body — verify response shape during impl. Round-trip with cleanup. |
| 24 | · planned | `users-loans` | #40 | high | none | #40 partially aligned (query vs body params, item_pid alternative, user_id_type) | Already rewritten. Round-trip needs test user + test item barcode. |
| 25 | · planned | `users-requests` | #41, #42, #43 | med | none | clean | Three request types (regular requests, RS, purchase). Same shape; share the test user fixture. |
| 26 | · planned | `users-fines-and-deposits` | #44, #45 | med | none | #44 partially aligned (op=pay/amount=ALL fix) | Already rewritten. Action-driven (pay/waive/dispute/restore for #44). |

## Phase 6 — Bibs domain (medium priority)

Mostly read + tightly bounded CRUD. Two audit Not-aligned cases (#52, #57).

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 27 | · planned | `bibs-holdings-and-items` | #46, #47 | med | none | #46 partially aligned (`bib` not `override_attached_items`); #47 partially aligned (`bib` not `bibs`, missing `override`) | Already rewritten. Both complete CRUD on tightly related concepts. Test fixture: dedicated test bib MMS. |
| 28 | · planned | `bibs-portfolios-and-ecollections` | #48, #54 | low | #66 | clean | Both bib-level electronic resource access; #48 is CRUD, #54 is read-only. |
| 29 | · planned | `bibs-requests` | #49, #50 | med | none | #49 partially aligned (missing `user_id`/`user_id_type`/`allow_same_request`) | Bib-level + item-level requests. Highly parallel. |
| 30 | · planned | `bibs-loans` | #51 | high | none | #51 partially aligned (query vs body confusion, `op=renew` only) | Already rewritten. Solo for review. |
| 31 | · planned | `bibs-booking` | #52 | high | none | #52 NOT ALIGNED (`period` mandatory `int`, missing `period_type`, `consider_dlr`) | Already rewritten. Verify `period` integer requirement and `consider_dlr` semantics in SANDBOX before final commit (audit's next-action #9). |
| 32 | · planned | `bibs-collections-and-reminders` | #53, #55 | low | none | clean | Both standalone CRUD; group for review economy. |
| 33 | · planned | `bibs-authorities` | #56 | high | none | #56 partially aligned (`authority_xml` not `marc_xml`; missing `normalization`/`override_warning`/`check_match`/`import_profile`) | Already rewritten. Authority XML wrapper; not raw MARC. Solo. |
| 34 | · planned | `bibs-record-ops` | #57 | high | none | #57 NOT ALIGNED (only `op=unlink_from_nz` documented; `suppress_bib`/`unsuppress_bib` removed) | Already rewritten — the original `suppress` wrappers must NOT be reintroduced. Solo. |

## Phase 7 — Acquisitions

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 35 | · planned | `acq-vendors-and-funds` | #58, #59 | med | none | #58 partially aligned (lowercase status, missing `type` filter); #59 partially aligned (op only `activate`/`deactivate`; transfers via #60) | Already rewritten. Top-level acquisition entities. |
| 36 | · planned | `acq-fund-transactions` | #60 | high | #59 | clean | State-changing fund operations (allocate/transfer). Round-trip with cleanup. **Reserve a test fund** so production funds aren't touched. |
| 37 | · planned | `acq-pol` | #61 | high | none | #61 partially aligned (`reason` not `reason_code`; missing `inform_vendor`/`override`/`bib`) | Already rewritten. Cancel POL is destructive; round-trip with a dedicated test POL. |
| 38 | · planned | `acq-attachments` | #62 | med | none | clean | Invoice attachments. Open question flagged: base64 vs multipart upload semantics (audit's next-action #10) — verify in SANDBOX. |
| 39 | · planned | `acq-licenses` | #63 | med | none | clean | 15 endpoints — biggest single chunk in Acq. Mostly CRUD. |
| 40 | · planned | `acq-lookups` | #64 | low | none | clean | Read-only lookups (currencies + fiscal periods). Quickest in this phase. |
| 41 | · planned | `acq-purchase-requests` | #65 | med | none | #65 partially aligned (op constrained to `approve`/`reject`; reject needs reason) | Already rewritten. |

## Phase 8 — Electronic

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 42 | · planned | `electronic-bootstrap` | #66 | low | none | clean | Foundation. **Blocks #67, #68, #69.** |
| 43 | · planned | `electronic-coverage` | #67, #68, #69 | med | #66 | #69 partially aligned (`limit` default 10 not 100; no `q` param) | Already rewritten. e-collections + e-services + portfolios share fixtures and patterns. **All three together** is fine — same shape; one PR is enough. |

## Phase 9 — TaskLists

Three of four tickets in this phase are previously-flagged. Take care.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 44 | · planned | `tasklists-bootstrap` | #70 | low | none | clean | Foundation. **Blocks #71, #72, #73.** |
| 45 | · planned | `tasklists-requested-resources` | #71 | high | #70 | #71 partially aligned (`library`+`circ_desk` mandatory; only `op=mark_reported`; dropped invented `request_ids`) | Already rewritten. |
| 46 | · planned | `tasklists-lending-requests` | #72 | high | #70 | #72 NOT ALIGNED (proposed ship/receive don't map to that endpoint; only `op=mark_reported`) | Already rewritten. Audit's next-action #2 calls for a separate partner-side follow-up ticket — don't try to add ship/receive helpers here. |
| 47 | · planned | `tasklists-printouts` | #73 | high | #70 | #73 partially aligned (no `POST /printouts/create`; documented `op=mark_as_printed`/`mark_as_canceled` only) | Already rewritten. `create_printout` was removed. |

## Phase 10 — ResourceSharing

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 48 | · planned | `rs-partners` | #74 | med | none | #74 partially aligned (no `q`/`type_filter`; documented filter is `status`) | Already rewritten. |
| 49 | · planned | `rs-directory-members` | #78 | high | none | #78 NOT ALIGNED (`localize` POST has no body params; `localization_data` was invented) | Already rewritten — bodyless POST. Solo. |

## Phase 11 — Courses

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 50 | · planned | `courses-bootstrap` | #75 | low | none | clean | Foundation. **Blocks #76, #77.** |
| 51 | · planned | `courses-crud-enrollment` | #76 | high | #75 | #76 NOT ALIGNED (POST is op-driven via query params: `op` + `user_ids`/`list_ids`, NOT a JSON body) | Already rewritten. Method signature is now `enroll_users_in_course(user_ids)` and `associate_reading_lists(list_ids)`. |
| 52 | · planned | `courses-reading-lists` | #77 | med | #75 | #77 partially aligned (citation file removal needs `op`; tags are objects not strings) | Already rewritten. |

## Phase 12 — Analytics

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 53 | · planned | `analytics-paths` | #79 | low | none | #79 partially aligned (root `/paths` endpoint — `{path}` is optional) | Already rewritten with single `get_analytics_paths(path=None)`. **Memory note: analytics is PRODUCTION-only** (per project memory `feedback_analytics_prod_only.md`). The SANDBOX test for this MUST use the PROD client + `ALMA_PROD_API_KEY`, BUT R8 forbids the prod key in the orchestration env. **This chunk requires manual SANDBOX-step substitution OR explicit user approval to relax R8 just for this test.** Likely: mark all paths-related ACs `unmappable` and verify by hand. |

## Phase 13 — Advanced architecture (deferred until coverage stabilizes)

The handbook recommends doing these in wave 7, after most of the high-priority coverage has merged. Each is non-trivial; some change patterns.

| # | Status | Chunk | Issues | Risk | Prereqs | Audit | Notes |
|---|---|---|---|---|---|---|---|
| 54 | · planned | `rate-limiting` | #8 | high | #3, #4, #5 | clean | Rolling-window throttler. Hard to validate in SANDBOX. |
| 55 | · planned | `async-bulk` | #18 | high | #3, #4 | clean | Sibling async client + `bulk_call`. Big surface; mostly mock-tested. |
| 56 | · planned | `marc-layer` | #19 | high | #46 | clean | Optional `pymarc` integration; needs careful design review. |
| 57 | · planned | `openapi-validation` | #20 | high | none | clean | Optional opt-in validator vendoring Ex Libris specs. Defer until specs are stable. |
| 58 | · planned | `batch-runner` | #21 | high | #18 | clean | DataFrame batch orchestrator built on #18 async. |
| 59 | · planned | `pydantic-models` | #12 | high | none | clean | Schema-derived models. Defer to last; benefits most from real fixtures. |

## Blocked — resolve before chunking

| Issue | Title | Blocker |
|---|---|---|
| #29 | Coverage: Configuration: integration profiles CRUD | Audit conflict on whether DELETE endpoint exists. Resolve by checking the live developer-network page, then either chunk it or close it. Carries `needs-decision` label. |

> **Note:** the deferred chunks (phase 13) are aspirational. They're listed for completeness so #8/#12/#18–#21 don't get forgotten. You may decide some of them are not worth the effort given the toolkit's actual usage patterns.
