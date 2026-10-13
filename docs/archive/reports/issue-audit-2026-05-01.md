# Alma API Documentation Conformance Audit — Open Issues

**Repository:** AlmaAPITK
**Issues reviewed:** 79 open issues (#1–#79)
**Source data:** `/tmp/codex-issue-audit/open-issues.json` (gh issue list export, 2026-05-01)
**Documentation reference:** https://developers.exlibrisgroup.com/alma/apis/

## Summary

- **Total open issues reviewed:** 79
- **Aligned:** 35
- **Partially aligned / needs clarification:** 21
- **Not aligned:** 5
- **Cannot verify (out of audit scope — internal architecture):** 18

### Headlines

**Not aligned (5)** — wrapper signatures don't match documented endpoint contracts; should be patched before implementation:
- #52 — Booking availability: `period` is mandatory `xs:int`, signature has it optional and as `str`; missing `period_type`.
- #57 — Bib record operations: docs only support `op=unlink_from_nz`; proposed `suppress_bib`/`unsuppress_bib` aren't implementable via this POST.
- #72 — TaskLists lending requests: proposed ship/receive methods don't map to that endpoint (only `op=mark_reported` documented).
- #76 — Courses enrollment: missing required `op`, `user_ids`, `list_ids` query params (treats as JSON body).
- #78 — RS directory localization: invents body payload that the API does not accept (Body Parameters: None).

**Partially aligned (21)** — endpoints correct but signatures or query params drift from docs. See per-issue detail.

**Cannot verify (18)** — issues #1–#21 are internal-architecture / client-engineering tickets (HTTP transport, error taxonomy, packaging, async, MARC layering, etc.) with no Alma endpoint claims to check. Issue #7 is the exception in that range — it does claim a region/host map, and that's flagged as Partially aligned.

---

## Issue Review

### Issue #1: Approach 3: Trusted Publisher (OIDC) + GitHub Actions release workflow
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Issue concerns PyPI release tooling and GitHub Actions, not Alma API surface.
**Findings:** Ticket scopes a PyPI Trusted Publisher OIDC release workflow and CI hygiene; it makes no claims about Alma endpoints, parameters, or response shapes. Documentation conformance against Alma APIs is not applicable.
**Recommended action:** keep as-is

### Issue #2: Logging: stray '(taskName=None)' on every log line under Python 3.12+
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Issue concerns Python stdlib `logging.LogRecord` behavior, not Alma APIs.
**Findings:** Ticket describes a Python 3.12 logging-formatter regression in `almaapitk.alma_logging` and proposes adding `taskName` to `standard_attrs`. No Alma API surface is touched.
**Recommended action:** keep as-is

### Issue #3: HTTP: use a persistent requests.Session for connection pooling
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Pure HTTP transport refactor (requests.Session lifetime).
**Findings:** Proposes replacing per-call `requests.<verb>(...)` with a persistent `requests.Session` to enable connection pooling. Internal client architecture only; no Alma endpoint, parameter, or schema claims.
**Recommended action:** keep as-is

### Issue #4: HTTP: consolidate get/post/put/delete into a single _request() method
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Pure refactor of HTTP verb methods.
**Findings:** Proposes consolidating four near-duplicate verb methods into a private `_request()` chokepoint. No Alma API claims.
**Recommended action:** keep as-is

### Issue #5: HTTP: add retry with exponential backoff for 429 / 5xx
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). The retry behavior (urllib3.Retry + Retry-After) targets generic HTTP semantics, not Alma-specific endpoints.
**Findings:** Proposes mounting a `urllib3.util.Retry` adapter on the session honoring `Retry-After`. Status codes 429/5xx and `Retry-After` are HTTP standards; the ticket makes no Alma-endpoint-specific claim.
**Recommended action:** keep as-is

### Issue #6: HTTP: make timeout configurable; lower default from 300s to 60s
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Client-side timeout configuration is not an API-surface concern.
**Findings:** Proposes a `timeout` constructor kwarg with a 60s default and per-call override. Internal ergonomics; no Alma documentation claims.
**Recommended action:** keep as-is

### Issue #7: HTTP: make region/host configurable (currently EU is hardcoded)
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/
**Findings:** Ticket claims five regions (EU/NA/APAC/CA/CN) with a host map. Verified hostnames are correct for EU, NA, AP, CA, but the docs list two APAC endpoints (`api-ap` Singapore and `api-aps` Australia) and the China endpoint is `api-cn.hosted.exlibrisgroup.com.cn` (not `.com`). The proposal collapses APAC into one entry and uses the wrong China TLD.
**Recommended action:** update issue description

### Issue #8: HTTP: implement client-side rolling-window rate limiting
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). The ticket cites "Alma's actual cap is ~25 RPS / institution" as a sizing note but does not propose to verify it; the deliverable is a generic client-side throttle.
**Findings:** Proposes a 60-second rolling-window throttler on the client. The ~25 RPS reference is an informal sizing remark, not a documented claim being verified or shipped.
**Recommended action:** keep as-is

### Issue #9: Errors: map Alma error codes to specific exception subclasses
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/
**Findings:** Ticket builds an exception registry keyed on `errorCode` values from Alma's `errorList.error[].errorCode` payload — that response shape is confirmed by the developer-network docs. Specific codes cited (402459 duplicate invoice, 40166411 POL mode) are not enumerated on the gateway landing page, but the structural claim is correct and the codes are sourced from the in-house `alma-api-expert` skill rather than fabricated.
**Recommended action:** keep as-is

### Issue #10: Errors: propagate Alma tracking_id and error_code onto raised exceptions
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/
**Findings:** Ticket asserts that Alma error payloads carry `errorList.error[0].trackingId` and `errorCode`; the developer-network docs confirm that exact JSON shape (`errorList.error[].errorCode`, `errorMessage`, `trackingId`). The proposal to extract and attach those fields to raised exceptions is consistent with the documented response model.
**Recommended action:** keep as-is

### Issue #11: API: add iter_paged() generator at the client level
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Generic pagination helper across Alma endpoints; no per-endpoint claim.
**Findings:** Proposes a client-level `iter_paged()` generator that uses `limit`/`offset`/`total_record_count` — these are Alma's standard pagination keys, but the ticket frames it as toolkit ergonomics rather than asserting endpoint specifics. No discrete Alma claim to verify.
**Recommended action:** keep as-is

### Issue #12: API: add optional Pydantic response models for hot-path payloads
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Models will eventually mirror Alma payloads, but the ticket does not commit to specific field shapes pending implementation.
**Findings:** Proposes optional Pydantic models for Invoice, PoLine, User, etc., gated behind extras with `extra='allow'`. The ticket explicitly defers schema details to fixture-driven implementation, so no documentable schema claim is made yet.
**Recommended action:** keep as-is

### Issue #13: API: add context-manager support to AlmaAPIClient (with-statement)
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Adds `__enter__`/`__exit__`/`close()` to the Python client.
**Findings:** Proposes context-manager protocol on `AlmaAPIClient` to release the persistent session cleanly. No Alma API surface involved.
**Recommended action:** keep as-is

### Issue #14: Quality: replace print() with logger; remove or harden safe_request()
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Internal logging hygiene + removal of a swallowing helper.
**Findings:** Replaces `print()` calls with `self.logger.*` and deletes/deprecates `safe_request()`. No Alma endpoints or schemas asserted.
**Recommended action:** keep as-is

### Issue #15: API: add hierarchical accessors (client.acq.invoices.get_invoice(...))
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Lazy-property façades on the Python client.
**Findings:** Adds `client.acq`, `client.bibs`, `client.users`, etc. as lazily cached domain accessors mirroring the package's existing domain classes. Pure ergonomics; no Alma claim.
**Recommended action:** keep as-is

### Issue #16: Quality: tighten exception handling and cache AlmaResponse.data
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Narrows `except:` clauses and memoizes `AlmaResponse.data`.
**Findings:** Three correctness fixes inside the Python client (bare except, repeated `response.json()`, helper extraction). No Alma endpoint, parameter, or response claim.
**Recommended action:** keep as-is

### Issue #17: Distribution: add LICENSE file and tighten PyPI metadata
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Repo hygiene (LICENSE, pyproject classifiers, project URLs).
**Findings:** Adds a top-level LICENSE and PyPI metadata classifiers. No Alma API claims.
**Recommended action:** keep as-is

### Issue #18: API: add async/concurrent bulk-call primitive (asyncio + aiohttp)
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Async sibling client and bulk-call helper; no per-endpoint claim.
**Findings:** Proposes an `AsyncAlmaAPIClient` (aiohttp) and a `bulk_call()` runner with semaphore + token-bucket pacing. Mentions "~25 RPS per-institution" as a sizing note, not a verifiable doc claim. Acceptance criteria section is also truncated in the ticket body.
**Recommended action:** update issue description

### Issue #19: API: dedicated MARC manipulation layer (consider pymarc integration)
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Wraps existing bib MARC-XML payloads with a pymarc-based caller API; relies on the existing `BibliographicRecords` HTTP methods.
**Findings:** Proposes optional pymarc integration with new `get_record_marc`/`update_record_marc` methods. Underlying Alma MARC XML transport is unchanged; this is an in-process abstraction layer.
**Recommended action:** keep as-is

### Issue #20: API: optional OpenAPI-driven request/response validation
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). Proposes vendoring published Ex Libris OpenAPI specs and adding an opt-in validator; the ticket does not assert any specific endpoint contract itself.
**Findings:** Adds an `almaapitk.openapi` module that vendors Alma OpenAPI JSON under `src/almaapitk/openapi/specs/` and validates requests/responses opt-in. The actual schema content comes from the published specs at fetch time, so there is no static doc claim in the ticket to verify.
**Recommended action:** keep as-is

### Issue #21: API: CSV/DataFrame BatchRunner with progress + checkpointing
**Status:** Cannot verify
**Relevant documentation:** N/A — out of audit scope (internal architecture). DataFrame batch orchestrator built on the async primitive in #18.
**Findings:** Proposes a `BatchRunner` for pandas DataFrame/list[dict] inputs with checkpointing, dry-run, and tracking-id-aware error rows. Pure consumer-side scaffolding; no Alma endpoint claims.
**Recommended action:** keep as-is

### Issue #22: Coverage: Configuration: bootstrap Configuration domain class
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** Foundation-only ticket with no API endpoints — only adds a class skeleton (`__init__`, `get_environment`, `test_connection`). Nothing to verify against docs except that the Configuration domain (`/almaws/v1/conf/...`) is the appropriate target, which it is.
**Recommended action:** keep as-is

### Issue #23: Coverage: Configuration: Sets full CRUD + member management
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** All four endpoints (POST/PUT/DELETE on `/almaws/v1/conf/sets[/{set_id}]`) match docs. The acceptance criteria explicitly call out the required `op` query parameter with values `add_members`/`delete_members`, matching the docs (which also allow `replace_members`).
**Recommended action:** keep as-is

### Issue #24: Coverage: Configuration: organization units (libraries, departments, circ desks)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** All five GET endpoints (libraries list/get, departments list, circ-desks list/get) exist in docs at the exact paths given. All read-only as the issue notes correctly. No required query parameters per docs.
**Recommended action:** keep as-is

### Issue #25: Coverage: Configuration: locations CRUD
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** All five endpoints under `/almaws/v1/conf/libraries/{libraryCode}/locations` (GET list, POST, GET/PUT/DELETE by locationCode) match docs exactly. Method signatures align with the path parameters.
**Recommended action:** keep as-is

### Issue #26: Coverage: Configuration: code tables (list, get, update)
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** The three endpoints (GET list, GET by name, PUT) all exist in docs at the spelled paths. However, the proposed `list_code_tables(self, scope: str = None)` accepts a `scope` parameter that does not appear in the documented query parameters for `GET /almaws/v1/conf/code-tables` (docs show no required/optional params for the list endpoint).
**Recommended action:** update issue description (drop or document the `scope` parameter)

### Issue #27: Coverage: Configuration: mapping tables (list, get, update)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** All three endpoints (`GET /conf/mapping-tables`, `GET/PUT /conf/mapping-tables/{name}`) match docs verbatim. Method signatures correctly reflect the PUT-replaces-whole-table semantics noted by the issue.
**Recommended action:** keep as-is

### Issue #28: Coverage: Configuration: jobs (list, run, instances, events, matches)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** All eight job endpoints (list, get, run via POST, instances list/get, download, events, matches) appear in docs at the exact paths. The `wait_for_job_completion` helper is a wrapper over polling `instances/{instance_id}` and is appropriate.
**Recommended action:** keep as-is

### Issue #29: Coverage: Configuration: integration profiles CRUD
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** GET list, POST create, GET single, PUT update endpoints all exist at the paths given. The issue correctly notes there is no DELETE endpoint, matching docs. The `profile_type` filter param on list is documented as optional.
**Recommended action:** keep as-is

### Issue #30: Coverage: Configuration: deposit profiles + import profiles (read-only)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** All four GET endpoints (deposit-profiles list/get, md-import-profiles list/get) exist in docs. The issue correctly notes that POST `/md-import-profiles/{profile_id}` is deprecated and should not be implemented.
**Recommended action:** keep as-is

### Issue #31: Coverage: Configuration: license terms CRUD
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** POST/GET/PUT/DELETE on `/almaws/v1/conf/license-terms[/{license_term_code}]` all match docs. The issue correctly notes that no GET list endpoint is exposed by Alma — confirmed by docs which show only the four listed verbs.
**Recommended action:** keep as-is

### Issue #32: Coverage: Configuration: open hours + relations
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** All seven endpoints (GET/PUT/DELETE for both `/conf/open-hours` and `/conf/relations`, plus library-scoped GET `/conf/libraries/{libraryCode}/open-hours`) match docs exactly. Method signatures correspond appropriately.
**Recommended action:** keep as-is

### Issue #33: Coverage: Configuration: letters + printers (read + letter update)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** GET `/conf/letters[/{letterCode}]`, PUT `/conf/letters/{letterCode}`, GET `/conf/printers[/{printer_id}]` all match docs. The issue correctly notes letters lack POST/DELETE and printers are read-only.
**Recommended action:** keep as-is

### Issue #34: Coverage: Configuration: reminders CRUD (config-level)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** GET list, POST create, GET/PUT/DELETE by reminder_id all exist at the documented paths. `limit`/`offset` are conventional pagination params consistent with other Alma list endpoints.
**Recommended action:** keep as-is

### Issue #35: Coverage: Configuration: workflows runner + utilities
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/conf/
**Findings:** All three endpoints (`POST /conf/workflows/{workflow_id}`, `GET /conf/utilities/fee-transactions`, `GET /conf/general`) match docs exactly. The `**filters` kwargs pass-through for fee-transactions is reasonable since the docs don't enumerate required filter params.
**Recommended action:** keep as-is

### Issue #36: Coverage: Users: list & search users
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** `GET /almaws/v1/users` and `GET /almaws/v1/users/{user_id}/personal-data` exist as documented. The `list_users` signature exposes `limit`, `offset`, `q`, `source_institution_code` (all valid optional params per docs), but omits other documented optional filters (`order_by`, `source_user_id`, `expand`, `modify_date_from`) that callers may want; signature is narrower than docs allow but not incorrect.
**Recommended action:** update issue description (note additional optional query params, or accept `**kwargs`)

### Issue #37: Coverage: Users: create / delete user (CRUD completeness)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** `POST /almaws/v1/users` and `DELETE /almaws/v1/users/{user_id}` both exist at the documented paths. The issue's required-field list (primary_id, account_type, status, user_group) is consistent with Alma's documented user creation requirements.
**Recommended action:** keep as-is

### Issue #38: Coverage: Users: authentication operations (POST /users/{id})
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** `POST /almaws/v1/users/{user_id}` with `op=auth` or `op=refresh` matches docs exactly. The issue explicitly captures both op values and notes password-redaction requirements for logging.
**Recommended action:** keep as-is

### Issue #39: Coverage: Users: user attachments
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** All three endpoints (GET list, GET by attachment_id, POST upload) exist at the documented paths under `/almaws/v1/users/{user_id}/attachments`. The signature for `get_user_attachment` returns `bytes`, which is reasonable for a binary download but the docs page does not explicitly clarify whether the attachment_id GET returns metadata or raw bytes — should be verified at implementation time.
**Recommended action:** request clarification (verify response shape of `GET /attachments/{attachment_id}`)

### Issue #40: Coverage: Users: loans (list, create, get, renew, change due date)
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** All five endpoints exist at the documented paths and the issue correctly notes `op=renew` for POST `/loans/{loan_id}`. However, `create_user_loan(self, user_id, item_barcode, library, circ_desk)` mis-models the API: per docs, `item_barcode`/`item_pid` are **query parameters** (one of the two required), while `library`/`circ_desk` belong in the **body** loan object — the signature flattens these without distinguishing, and omits the alternative `item_pid` parameter and optional `user_id_type`.
**Recommended action:** update issue description (clarify query vs body params; expose `item_pid` alternative; document `user_id_type`)

### Issue #41: Coverage: Users: requests (list, create, get, cancel, action, update)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** All six endpoints/methods exist with the documented HTTP verbs. The proposed `list_user_requests` covers documented `limit`/`offset`/`status` params, and `perform_user_request_action` correctly captures the required `op` query parameter for POST `/requests/{id}`.
**Recommended action:** keep as-is

### Issue #42: Coverage: Users: resource sharing requests (user-side)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** The four endpoints (POST/GET/DELETE plus action POST with `op`) are all documented at the listed paths. The Python signatures correctly model the action `op` query param. Specific `op` values are not enumerated in the docs index, so verification is at the path/verb level only.
**Recommended action:** keep as-is

### Issue #43: Coverage: Users: purchase requests
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** All four endpoints exist (GET list, POST create, GET single, POST with `op`) and the proposed Python methods match. The action method correctly threads the `op` query param through.
**Recommended action:** keep as-is

### Issue #44: Coverage: Users: fines & fees
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** Endpoints and `op` values (pay/waive/dispute/restore) match docs. However, two signature mismatches: (1) `pay_all_user_fees` omits the mandatory `op=pay` query param and the `amount=ALL` literal value; (2) `dispute_user_fee(... reason: str)` marks `reason` required, but docs only require `reason` for `op=waive` (dispute does not require it). Also `method` should not default to `'CASH'` silently when `op != pay`.
**Recommended action:** update issue description

### Issue #45: Coverage: Users: deposits
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/users/
**Findings:** All four endpoints (list, create, get, action with `op`) exist as documented. Specific `op` values for the deposit action endpoint are not enumerated in the public docs index, so the generic `perform_user_deposit_action(..., op)` shape is appropriate.
**Recommended action:** keep as-is

### Issue #46: Coverage: Bibs: complete holdings CRUD (update / delete)
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** Paths and verbs match docs. However, the proposed `delete_holding(..., override_attached_items: bool = False)` parameter does not exist in the Alma docs; the actual documented query parameter is `bib` (values: `retain`/`delete`/`suppress`) controlling how a bib left without holdings is handled. There is no `override` query param on this endpoint per docs.
**Recommended action:** update issue description

### Issue #47: Coverage: Bibs: complete items CRUD (update / withdraw)
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** Paths and verbs are correct. The withdraw signature uses `bibs: str = 'retain'`, but the actual documented query parameter is singular `bib` (not `bibs`); it accepts `retain`/`delete`/`suppress`. The signature also omits the documented `override` query parameter.
**Recommended action:** update issue description

### Issue #48: Coverage: Bibs: bib-attached portfolios CRUD
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** All five endpoints (including the documented trailing slash on POST `/portfolios/`) match the docs. The list endpoint supports `limit`/`offset` (0-100), which the proposed `list_bib_portfolios(mms_id)` does not yet expose; minor enhancement opportunity but not a hard mismatch.
**Recommended action:** keep as-is

### Issue #49: Coverage: Bibs: bib-level requests
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** Paths and verbs all match docs. However, `create_bib_request(mms_id, request_data)` omits the documented (optional but commonly required) `user_id` and `user_id_type` query parameters, plus `allow_same_request`. Action POST correctly captures `op`.
**Recommended action:** update issue description

### Issue #50: Coverage: Bibs: item-level requests
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** All six endpoints exist exactly as listed (note docs use both `item_id` and `item_pid` in path templates inconsistently — issue mirrors that). Methods correctly thread `op` for the action POST.
**Recommended action:** keep as-is

### Issue #51: Coverage: Bibs: loans (bib + item level)
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** All paths/verbs are documented. Two issues: (1) `create_item_loan` puts `library` and `circ_desk` in the Python signature as if they were query params, but docs show only `user_id`/`user_id_type` as query params — `library`/`circ_desk` belong inside the Loan body object; (2) `perform_item_loan_action` is correct but docs say only `op=renew` is supported, which is worth noting.
**Recommended action:** update issue description

### Issue #52: Coverage: Bibs: booking availability + request options
**Status:** Not aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** Paths and verbs are correct. But `period` is documented as a **mandatory** integer (`xs:int`) on both booking-availability endpoints, while the issue declares `period: str = None` (optional string). The signature also omits `period_type` (days/weeks/months) and the `consider_dlr` query param on request-options.
**Recommended action:** update issue description

### Issue #53: Coverage: Bibs: collections CRUD (the collection itself)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** All five endpoints match docs at `/almaws/v1/bibs/collections` and `/almaws/v1/bibs/collections/{pid}`. The DO-NOT-re-implement note correctly distinguishes member-level methods from collection-object CRUD.
**Recommended action:** keep as-is

### Issue #54: Coverage: Bibs: bib-level e-collections (read)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** Both GET endpoints (list and get-by-id) at `/bibs/{mms_id}/e-collections` match docs. Read-only scope is correct — Alma exposes only GET at the bib-level e-collections path.
**Recommended action:** keep as-is

### Issue #55: Coverage: Bibs: bib reminders CRUD
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** All five reminder endpoints (GET list, POST create, GET/PUT/DELETE single) at `/bibs/{mms_id}/reminders/...` match docs. Method signatures are appropriate.
**Recommended action:** keep as-is

### Issue #56: Coverage: Bibs: authorities CRUD
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** Paths/verbs match docs. Mismatches: (1) the body parameter is named `marc_xml: str`, but the API requires an Authority XML wrapper (not raw MARC) and JSON is not supported; (2) the issue exposes only `validate`, omitting documented query params `normalization`, `override_warning`, `check_match`, `import_profile`. Terminology should be `authority_xml` not `marc_xml`.
**Recommended action:** update issue description

### Issue #57: Coverage: Bibs: bib record operations (POST /bibs/{mms_id})
**Status:** Not aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/bibs/
**Findings:** Docs explicitly state: "Currently, the supported operation is to unlink from NZ" (`op=unlink_from_nz`). The proposed `suppress_bib`/`unsuppress_bib` are not implementable via this POST endpoint — bib suppression is controlled by the `suppress_from_publishing` field on PUT `/bibs/{mms_id}`, not a POST `op`.
**Recommended action:** update issue description

### Issue #58: Coverage: Acquisitions: vendors CRUD + nested invoices/POLs
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/acq/
**Findings:** All seven endpoints match the docs. Minor: `list_vendors(... status: str)` — docs accept lowercase `active`/`inactive` and also expose a `type` filter (material_supplier/access_provider/licensor/governmental) that is not in the proposed signature. Path-level alignment is correct including `vendorCode` casing.
**Recommended action:** update issue description

### Issue #59: Coverage: Acquisitions: funds CRUD + fund service
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/acq/
**Findings:** Paths/verbs match docs. However, the issue's reference to "Fund Service (transfer, allocate, etc.)" is incorrect — docs say the `op` query param accepts only `activate` or `deactivate`. Transfer/allocate are handled via POST `/funds/{fund_id}/transactions` (issue #60), not the fund-service endpoint. Also `list_funds(... status='ACTIVE')` is reasonable but the docs define more filters (mode, view, entity_type, fiscal_period, owner, library, parent_id) worth surfacing.
**Recommended action:** update issue description

### Issue #60: Coverage: Acquisitions: fund transactions
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/acq/
**Findings:** Both GET and POST endpoints at `/acq/funds/{fund_id}/transactions` are documented. The body Transaction object requires `type`, `amount`, and `related_fund` (this is where allocate/transfer actually happens). Proposed signatures correctly leave the body open as `transaction_data: Dict[str, Any]`.
**Recommended action:** keep as-is

### Issue #61: Coverage: Acquisitions: PO Lines list + create + cancel
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/acq/
**Findings:** Endpoints and methods match. The `cancel_pol(pol_id, reason_code, comment)` signature is close, but Alma's actual query param is named `reason` (not `reason_code`), and the endpoint also exposes useful optional params `inform_vendor`, `override`, and `bib` that the signature does not surface.
**Recommended action:** update issue description

### Issue #62: Coverage: Acquisitions: invoice attachments CRUD
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/acq/
**Findings:** All five endpoints (GET list, POST create, GET/PUT/DELETE single) and HTTP methods match the documented `/almaws/v1/acq/invoices/{invoice_id}/attachments[/{attachment_id}]` resource. Multipart upload requirement is correctly flagged in implementation notes.
**Recommended action:** keep as-is

### Issue #63: Coverage: Acquisitions: licenses + amendments + attachments
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/acq/
**Findings:** All 15 endpoints across licenses, license attachments, and license amendments match the documented Acq API surface, and all HTTP methods (GET/POST/PUT/DELETE) are correct. Method signatures are reasonable for the resource shape.
**Recommended action:** keep as-is

### Issue #64: Coverage: Acquisitions: lookups (currencies + fiscal periods)
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/acq/
**Findings:** Both `GET /almaws/v1/acq/currencies` and `GET /almaws/v1/acq/fiscal-periods` are documented read-only endpoints, and the `list_*` no-arg signatures fit a lookup endpoint.
**Recommended action:** keep as-is

### Issue #65: Coverage: Acquisitions: purchase requests (acq-side)
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/acq/
**Findings:** Endpoints and HTTP methods match. The `op` query param is correctly surfaced in `perform_purchase_request_action(op)`, but Alma documents only `approve` and `reject` — the issue note says "approve, reject, link to POL", and "link to POL" is not a documented `op` value. Reject also requires a reason in the body (alma_code 60308) which the signature does not flag.
**Recommended action:** update issue description

### Issue #66: Coverage: Electronic: bootstrap Electronic domain class
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/electronic/
**Findings:** Foundation-only ticket; touches no API endpoints. The Electronic API category exists in the Alma developer network, so the new `Electronic` domain class is well-justified. No API surface to verify.
**Recommended action:** keep as-is

### Issue #67: Coverage: Electronic: e-collections CRUD
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/electronic/
**Findings:** All five endpoints and HTTP methods match. The `list_ecollections(q, limit, offset)` signature aligns with the documented optional query parameters `q`, `limit` (default 10), and `offset` (default 0).
**Recommended action:** keep as-is

### Issue #68: Coverage: Electronic: e-services CRUD
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/electronic/
**Findings:** All five `/electronic/e-collections/{collection_id}/e-services[/{service_id}]` endpoints and HTTP methods match the documented Alma surface. Method signatures correctly thread `collection_id` and `service_id` through the path.
**Recommended action:** keep as-is

### Issue #69: Coverage: Electronic: electronic portfolios CRUD
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/electronic/
**Findings:** Paths and HTTP methods all match (note the documented trailing slash on POST). Signature `list_portfolios(..., limit: int = 100, ...)` proposes a default of 100, but Alma documents `limit` default as 10 with valid range 0–100; the default is non-standard but stays inside the valid range. Doc also confirms no `q` parameter is supported here.
**Recommended action:** update issue description

### Issue #70: Coverage: TaskLists: bootstrap TaskLists domain class
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/tasklists/
**Findings:** Foundation-only ticket; the TaskLists API category exists on the Alma developer network, so the new domain class skeleton is well-justified. No API surface to verify.
**Recommended action:** keep as-is

### Issue #71: Coverage: TaskLists: requested resources
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/tasklists/
**Findings:** Endpoint paths and methods are correct. However, the POST endpoint requires `library`, `circ_desk`, AND `op` as mandatory query params, and the only documented `op` value is `mark_reported` (not the broad action surface implied by `request_ids: List[str]`). The proposed `perform_requested_resource_action(op, request_ids, **params)` doesn't reflect that `library`/`circ_desk` are mandatory and that `request_ids` is not a documented parameter for this endpoint.
**Recommended action:** update issue description

### Issue #72: Coverage: TaskLists: lending requests workflow
**Status:** Not aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/tasklists/
**Findings:** Paths/methods are correct, but the issue claims the POST endpoint supports ship/receive/return/cancel actions and proposes `ship_lending_requests` and `receive_lending_requests` methods. Per Alma docs, this endpoint requires `library` + `op` and the only documented `op` value is `mark_reported`; ship/receive workflows live elsewhere (on partner-side `/lending-requests/{request_id}` POST). The proposed methods do not map to this endpoint.
**Recommended action:** update issue description

### Issue #73: Coverage: TaskLists: printouts
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/tasklists/
**Findings:** Most endpoints/methods match; however `POST /almaws/v1/task-lists/printouts/create` is not present in the published Alma docs (the documented printout-creation flow uses `POST /printouts` with `op`). Also, the `create_printout(printout_data)` signature implies a JSON body, but the documented `POST /printouts` endpoint accepts no body and only query params (`op` = `mark_as_printed` | `mark_as_canceled`).
**Recommended action:** update issue description

### Issue #74: Coverage: ResourceSharing: partner management CRUD
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/partners/
**Findings:** All five endpoints and HTTP methods are correct. The `list_partners(q, limit, offset, type_filter)` signature is misaligned with docs: there is no `q` parameter and no `type` filter — the documented filter is `status` (ACTIVE/INACTIVE). Issue notes about partner types (ISO_18626, NCIP, etc.) are accurate as object-shape guidance but not as list query filters.
**Recommended action:** update issue description

### Issue #75: Coverage: Courses: bootstrap Courses domain class
**Status:** Aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/courses/
**Findings:** Foundation-only ticket. The Courses API category exists on the Alma developer network, so the new domain class skeleton is justified. No API surface to verify.
**Recommended action:** keep as-is

### Issue #76: Coverage: Courses: courses CRUD + enrollment
**Status:** Not aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/courses/
**Findings:** Confirmed precedent: Alma's `POST /almaws/v1/courses/{course_id}` requires query param `op` with values `enroll_user` or `associate_to_reading_lists`, plus `user_ids` or `list_ids` as comma-separated strings. The proposed `enroll_to_course(course_id, enrollment_data: Dict)` does not surface `op`, `user_ids`, or `list_ids`, treating it as a JSON-body call — a mismatch with the actual query-param dispatch pattern.
**Recommended action:** update issue description

### Issue #77: Coverage: Courses: reading lists + citations + owners + tags
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/courses/
**Findings:** All listed endpoint paths and HTTP methods are present in Alma's Courses API. The `POST /citations/{citation_id} — Remove file` is an `op`-driven endpoint per Alma convention; `remove_citation_file(course_id, reading_list_id, citation_id)` should accept/pass the `op` query param explicitly. Also, `update_citation_tags(... tags: List[str])` glosses over Alma's tag object structure (tags are objects, not bare strings) per the citation tags schema.
**Recommended action:** update issue description

### Issue #78: Coverage: ResourceSharing: directory members (list/get/localize)
**Status:** Not aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/rsdirectorymember/
**Findings:** Confirmed precedent: Alma's `POST /almaws/v1/RSDirectoryMember/{partner_code}` (Localize Member) documents Body Parameters: None and no query parameters beyond the path param — it just creates a Partner from the directory entry. The proposed `localize_directory_member(partner_code, localization_data: Dict[str, Any])` invents a body payload that the API does not accept.
**Recommended action:** update issue description

### Issue #79: Coverage: Analytics: paths endpoint
**Status:** Partially aligned
**Relevant documentation:** https://developers.exlibrisgroup.com/alma/apis/analytics/
**Findings:** Confirmed precedent: Alma documents `GET /almaws/v1/analytics/paths/{path}` with `{path}` explicitly optional ("If not sent the root directory will be returned"); the issue lists only the parameterized form without noting that omitting `{path}` returns the root. The two proposed methods (`get_analytics_path` and `list_analytics_paths`) effectively cover both behaviors but the issue body should make the optional-path semantics explicit.
**Recommended action:** update issue description
