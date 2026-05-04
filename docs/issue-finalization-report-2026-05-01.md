# Issue Finalization Report — 2026-05-01

## Summary

- Total issues reviewed: 79
- Issues edited (body rewrites): 34
- Issues commented (without body rewrite): 5
- Issues relabeled (e.g. needs-decision added): 11
- Issues unchanged: 40
- Issues closed: 0 (closing decisions deferred to human via `needs-decision` label + comment)
- Issues requiring human review: 0 (strict rule); 11 issues carry `needs-decision` label and require maintainer attention before implementation
- Highest-risk issues:
  - **#29** Integration profiles CRUD — audit conflict over DELETE endpoint existence; cannot resolve from audit data alone
  - **#52** Booking availability + request options — `period` was modeled as optional `str`; docs require mandatory `xs:int`
  - **#57** Bib record operations (POST `/bibs/{mms_id}`) — proposed suppress/unsuppress wrappers are unimplementable on this verb
  - **#72** TaskLists lending requests workflow — proposed ship/receive helpers don't map to documented endpoint; partner-side follow-up required
  - **#76** Courses CRUD + enrollment — POST is op-driven via query params, not a JSON body; signatures had to be replaced
  - **#78** ResourceSharing directory members — POST Localize Member documents no body; previous `localization_data` Dict was invented
- Prioritized next actions:
  1. Resolve audit conflict on **#29** (DELETE on integration profiles) by checking the live developer-network page.
  2. Decide partner-side follow-up ticket scope for **#72** (lending request ship/receive helpers).
  3. Confirm helper drops on **#73** (`create_printout` removed) and **#76** (replaced enroll helper).
  4. Choose validation policy (clamp vs raise) for out-of-range `limit` values flagged across **#69**, **#74**.
  5. Finalize op-whitelist policy across action-style endpoints (**#65**, **#71**, **#73**, **#77**) — strict whitelist vs pass-through.
  6. Pick PyPI license for **#17** (MIT or Apache-2.0) — only owner-side decision blocking that ticket.
  7. Implement architectural foundation tickets in order: **#3** (Session) → **#4** (`_request()`) → **#14** (logger) → **#5/#16** (retry, response cache).
  8. Begin Configuration domain bootstrap (**#22**) to unblock **#24–#35**.
  9. Verify `period` integer requirement and `consider_dlr` scope at item-level for **#52** in SANDBOX before coding.
  10. Verify Attachment-object (base64) vs multipart-upload semantics flagged on **#39**, **#62**, **#63** before coding upload helpers.

## Aggregate decisions

| Classification | Edited | Commented | Relabeled | Unchanged | Human Review |
|---|---|---|---|---|---|
| api-coverage | 28 | 0 | 11 | 30 | 0 |
| general | 6 | 5 | 0 | 10 | 0 |

| Overall status | Count |
|---|---|
| Ready / finalized (Aligned) | 40 |
| Needs minor edit | 2 |
| Needs major rewrite (partially-aligned + rewritten) | 32 |
| Needs clarification (audit conflict / needs-decision) | 1 |
| Should be split | 0 |
| Should be closed | 0 |
| Cannot safely finalize | 0 |
| Not aligned (substantive rewrite) | 4 |

## Per-issue detail

### Issue #1: Approach 3: Trusted Publisher (OIDC) + GitHub Actions release workflow

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 4/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** PyPI release tooling, fully out of Alma API audit scope. Both audits agree: keep as-is. Body has clear scope, lessons-learned section, and references to the design spec and audit findings. No AC formally enumerated but scope bullets serve that purpose for a process/CI ticket.
**Remaining concerns:** Could optionally promote scope bullets to formal acceptance criteria, but body is already actionable for an implementer.

### Issue #2: Logging: stray '(taskName=None)' on every log line under Python 3.12+

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 4/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** Ready / finalized
**Final decision:** commented
**Changes made:** gh issue comment 2
**Reasoning:** Python stdlib logging regression — out of Alma API scope. Symptom, root cause, fix, and reproduction are all clearly documented. One-line fix. Added an audit-notes comment confirming the diagnosis and suggesting the bug label (left for human maintainer to apply).
**Remaining concerns:** Should arguably carry the bug label rather than (or in addition to) being treated as an enhancement.

### Issue #3: HTTP: use a persistent requests.Session for connection pooling

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Pure HTTP transport refactor; AC are concrete and testable; downstream blockers documented in Prerequisites. Both audits agree: keep as-is.
**Remaining concerns:** None.

### Issue #4: HTTP: consolidate get/post/put/delete into a single _request() method

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 2/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Internal refactor with concrete proposal, hard prereq on #3 declared, AC explicitly preserves public signatures. Nothing to verify against Alma docs.
**Remaining concerns:** None.

### Issue #5: HTTP: add retry with exponential backoff for 429 / 5xx

**Classification:** general
**Scores:** docTech 4/5, clarity 5/5, tech 5/5, robust 4/5, ready 4/5, ac 4/5, scope 5/5, align 4/5, risk 3/5
**Overall status:** Ready / finalized
**Final decision:** commented
**Changes made:** gh issue comment 5
**Reasoning:** Codex direct audit flagged that 502/504/Retry-After are not explicitly enumerated on the public Error Handling page, and POST/PUT retries are risky. The existing AC already calls out the POST idempotency hazard, so a body rewrite is unnecessary. Added an audit-notes comment recording the 502/504/Retry-After clarification and a stronger recommendation to default `allowed_methods` to idempotent verbs only.
**Remaining concerns:** Implementer should decide whether to default-include POST/PUT in `allowed_methods`. Strongly recommend idempotent verbs only by default.

### Issue #6: HTTP: make timeout configurable; lower default from 300s to 60s

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 2/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Internal ergonomics ticket; no Alma API claim. AC are testable; CHANGELOG note for the behavior change is explicit. Soft prereq on #4 documented.
**Remaining concerns:** None.

### Issue #7: HTTP: make region/host configurable (currently EU is hardcoded)

**Classification:** general
**Scores:** docTech 3/5, clarity 5/5, tech 4/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 3/5, risk 2/5
**Overall status:** Needs minor edit
**Final decision:** edited
**Changes made:** gh issue edit 7 --body-file
**Reasoning:** Both audits flag the same two errors in the proposed REGION_HOSTS map: (1) APAC was collapsed into one entry but Ex Libris documents two distinct datacenters (api-ap Singapore, api-aps Australia); (2) CN used `.com` TLD but the documented host is `.com.cn`. Rewrote body to split APAC into AP/APS and corrected the CN TLD; preserved the public downstream caller motivation from the existing comment, added Audit notes section.
**Remaining concerns:** Region code naming (AP/APS vs APAC/AU) is a convention choice. The rewrite uses the host-prefix-based codes (AP, APS) to mirror the actual hostnames; an alternative `APAC_SG` / `APAC_AU` style would also be defensible.

### Issue #8: HTTP: implement client-side rolling-window rate limiting

**Classification:** general
**Scores:** docTech 4/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 4/5, risk 2/5
**Overall status:** Needs minor edit
**Final decision:** edited
**Changes made:** gh issue edit 8 --body-file
**Reasoning:** Codex direct audit flagged the '~25 RPS' sizing claim as unsupported by Ex Libris's published API Governance Thresholds (50 RPS / 1500 RPM prod, 10 RPS / 300 RPM sandbox). Replaced the unsupported claim with documented thresholds, kept the implementation proposal and AC intact, added stronger acceptance criterion (test for the 100 RPM default) and an open-question on whether to clamp.
**Remaining concerns:** Decision on per-process vs cross-process throttling left to implementer; documented as a known limitation in the rewrite.

### Issue #9: Errors: map Alma error codes to specific exception subclasses

**Classification:** general
**Scores:** docTech 4/5, clarity 5/5, tech 5/5, robust 5/5, ready 4/5, ac 5/5, scope 5/5, align 4/5, risk 2/5
**Overall status:** Ready / finalized
**Final decision:** commented
**Changes made:** gh issue comment 9
**Reasoning:** Structural design (errorList.error[].errorCode, registry, status fallback) is verified by the public docs. Codex flagged that the two example codes (402459, 40166411) have broader documented meanings than the proposed class names imply. The structural audit notes the same is sourced from alma-api-expert. This is a class-naming/registry-curation question, not an API documentation correction. Added an audit-notes comment recording both interpretations and the decision points; existing AC (table + cross-link to alma-api-expert) already covers the documentation requirement.
**Remaining concerns:** Implementer must decide whether to keep narrow class names (AlmaDuplicateInvoiceError, AlmaInvalidPolModeError) or broaden to AlmaInvalidParameterError + context.

### Issue #10: Errors: propagate Alma tracking_id and error_code onto raised exceptions

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Aligned with Alma error response shape (errorList.error[].trackingId / errorCode). Existing domain code already references these attributes optimistically; this issue closes the silent dead-code path. AC are concrete and testable. Codex noted minor terminology ('errorCode' camelCase) which the proposal already addresses by exposing `alma_code` as the Pythonic alias.
**Remaining concerns:** None.

### Issue #11: API: add iter_paged() generator at the client level

**Classification:** general
**Scores:** docTech 4/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 4/5, risk 2/5
**Overall status:** Ready / finalized
**Final decision:** commented
**Changes made:** gh issue comment 11
**Reasoning:** Internal pagination helper. Codex correctly noted that record_key and total_record_count semantics vary by endpoint. The proposed signature already requires record_key as an explicit argument, which addresses the concern. Added an audit-notes comment with two practical refinements (handling of missing total_record_count, per-endpoint limit caps) without rewriting the body.
**Remaining concerns:** None.

### Issue #12: API: add optional Pydantic response models for hot-path payloads

**Classification:** general
**Scores:** docTech 4/5, clarity 5/5, tech 5/5, robust 4/5, ready 4/5, ac 5/5, scope 5/5, align 4/5, risk 3/5
**Overall status:** Ready / finalized
**Final decision:** commented
**Changes made:** gh issue comment 12
**Reasoning:** Largest item in the improvement pool, but architecturally sound (extras gating, extra='allow', fixture-based tests). Codex flagged that hand-modeling from sandbox payloads should be cross-checked against XSD/OpenAPI. Added an audit-notes comment with concrete implementation guidance (cross-check at model creation, recommended order Acquisitions → Users → Bibs, defer RS/Partners/TaskLists until OpenAPI matures).
**Remaining concerns:** Body could optionally be rewritten to formalize the per-domain milestone plan, but the existing 'Notes' section already records that intent.

### Issue #13: API: add context-manager support to AlmaAPIClient (with-statement)

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Pure Python ergonomics. Concrete proposal, hard prereq on #3 declared, AC are concrete and testable.
**Remaining concerns:** None.

### Issue #14: Quality: replace print() with logger; remove or harden safe_request()

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 2/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Closes a project-policy violation explicitly documented in CLAUDE.md. AC include the grep-asserts-no-print check and a stdout-capture test. Deprecation path for safe_request is sound.
**Remaining concerns:** None.

### Issue #15: API: add hierarchical accessors (client.acq.invoices.get_invoice(...))

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Pure ergonomics; existing instantiation API preserved; lazy caching well-specified. AC explicitly cover both styles and the contract test.
**Remaining concerns:** None.

### Issue #16: Quality: tighten exception handling and cache AlmaResponse.data

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** Ready / finalized
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Three correctness fixes inside the client (bare except, repeated json() parsing, helper extraction). Each has a concrete code proposal and a corresponding AC. Soft prereq on #4 documented.
**Remaining concerns:** None.

### Issue #17: Distribution: add LICENSE file and tighten PyPI metadata

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — packaging hygiene with concrete AC
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits classify as out-of-scope-for-Alma-API but well-formed. AC is concrete and testable (LICENSE present, classifiers, twine check clean, badge, CHANGELOG entry). No corrections to apply.
**Remaining concerns:** None — pick a license (MIT or Apache-2.0) is the only owner-side decision.

### Issue #18: API: add async/concurrent bulk-call primitive (asyncio + aiohttp)

**Classification:** general
**Scores:** docTech 4/5, clarity 5/5, tech 4/5, robust 4/5, ready 3/5, ac 4/5, scope 4/5, align 4/5, risk 3/5
**Overall status:** Partially aligned (rate-limit sizing wrong; mutating-verb retry safety missing)
**Final decision:** Edit body + comment
**Changes made:** gh issue edit 18 --body-file (rewrote body to use documented Alma thresholds 50 RPS prod / 10 RPS sandbox; environment-aware default throttle ≤ 25 prod / ≤ 8 sandbox; AC reformatted as checklist; added Open questions and Audit notes; added explicit caveat that POST/PUT/DELETE retries must be opt-in); gh issue comment 18 (summarized the audit-driven changes)
**Reasoning:** Codex audit cites Alma's documented thresholds (50 RPS / 1500 RPM prod, 10 RPS / 300 RPM sandbox). Original '~25 RPS' default was unsourced. Codex also flags `Retry-After` is not documented on Alma's error-handling page; treat as opportunistic. Issue #5 audit notes mutating-verb retries are risky — propagated that into AC.
**Remaining concerns:** Whether AsyncAlmaAPIClient and the sync client should share a single rate-limit budget; tracked in Open questions.

### Issue #19: API: dedicated MARC manipulation layer (consider pymarc integration)

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — pymarc integration consistent with Alma's MARCXML-only Bibs/Holdings APIs
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. Codex notes Alma docs say Create/Update Bib/Holdings APIs do not support JSON input — pymarc layer is a natural fit. AC is concrete (round-trip test, optional dep, preserved hand-rolled helpers).
**Remaining concerns:** None.

### Issue #20: API: optional OpenAPI-driven request/response validation

**Classification:** general
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 3/5, ready 3/5, ac 4/5, scope 3/5, align 3/5, risk 3/5
**Overall status:** Partially aligned (API-area list incomplete; missing OpenAPI early-stage caveat)
**Final decision:** Edit body + comment
**Changes made:** gh issue edit 20 --body-file (expanded vendored-specs list to all current Alma areas including Courses, Partners, TaskLists, RSDirectoryMember; added Ex Libris early-phase caveat; AC now requires silent pass-through for endpoints not in vendored spec); gh issue comment 20 (summarized audit-driven changes)
**Reasoning:** Codex audit explicitly flagged that the original area list (bibs/conf/electronic/users/acq/analytics) misses surfaces that this toolkit's coverage backlog targets, and that Ex Libris labels its OpenAPI support as early-phase, so missing-from-spec must NOT be treated as invalid.
**Remaining concerns:** Validator library choice (openapi-core vs jsonschema) tracked in Open questions; refresh-strategy (committed snapshots vs install-time fetch) also Open.

### Issue #21: API: CSV/DataFrame BatchRunner with progress + checkpointing

**Classification:** general
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 4/5, ac 5/5, scope 5/5, align 5/5, risk 4/5
**Overall status:** Aligned — workflow scaffolding with clear AC and concrete migration target
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Pure consumer-side scaffolding on top of #18. Both audits classify as wrapper task, not API claim. AC includes resume-from-checkpoint test and a real consumer migration as proof.
**Remaining concerns:** Depends on #18 landing first (correctly listed as hard prereq).

### Issue #22: Coverage: Configuration: bootstrap Configuration domain class

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — foundation-only ticket, no endpoint claims
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. Foundation-only with explicit no-API-methods note and concrete AC (smoke import, public-API contract test, lazy import wired). Pattern source listed (admin.py).
**Remaining concerns:** None.

### Issue #23: Coverage: Configuration: Sets full CRUD + member management

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — extends existing Admin class; correctly captures op query parameter
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. Endpoints, op values (add_members/delete_members), and DO-NOT-re-implement list are all correct. Round-trip test in AC.
**Remaining concerns:** None.

### Issue #24: Coverage: Configuration: organization units (libraries, departments, circ desks)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — five read-only endpoints all match docs
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. Read-only scope correctly noted. Path parameters spelled correctly (libraryCode, circDeskCode).
**Remaining concerns:** None.

### Issue #25: Coverage: Configuration: locations CRUD

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — five endpoints match docs exactly
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. Path params correctly use camelCase placeholders. AC includes required-field validation note.
**Remaining concerns:** None.

### Issue #26: Coverage: Configuration: code tables (list, get, update)

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 4/5, scope 4/5, align 3/5, risk 4/5
**Overall status:** Partially aligned — undocumented `scope` parameter on list endpoint
**Final decision:** Edit body + comment
**Changes made:** gh issue edit 26 --body-file (dropped `scope` param from list_code_tables signature; AC now explicitly forbids shipping undocumented filters; added Open questions for future-filter case; reorganized into the canonical body template); gh issue comment 26 (summarized the audit-driven change)
**Reasoning:** Doc-conformance audit explicitly flagged that `GET /almaws/v1/conf/code-tables` does not document a `scope` parameter. Codex audit treated as aligned but did not contradict. Safer to ship without the undocumented filter.
**Remaining concerns:** If Alma adds a documented filter later, expose it via typed kwarg — captured in Open questions.

### Issue #27: Coverage: Configuration: mapping tables (list, get, update)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — three endpoints match docs verbatim; PUT-replaces-whole-table semantics noted
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. Identical shape to code-tables; correctly references that as the pattern source.
**Remaining concerns:** None.

### Issue #28: Coverage: Configuration: jobs (list, run, instances, events, matches)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — eight endpoints match docs; wait_for_job_completion helper appropriate
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. AC explicitly requires the wait helper to wait for terminal status with timeout, and download to return raw bytes.
**Remaining concerns:** None.

### Issue #29: Coverage: Configuration: integration profiles CRUD

**Classification:** api-coverage
**Scores:** docTech 3/5, clarity 4/5, tech 4/5, robust 3/5, ready 2/5, ac 4/5, scope 3/5, align 3/5, risk 3/5
**Overall status:** Audit conflict — DELETE endpoint existence disputed
**Final decision:** Edit body + comment + add needs-decision label
**Changes made:** gh issue edit 29 --body-file (preserved the four GET/POST/PUT methods, called out the audit conflict explicitly in Background and Open questions, made DELETE conditional on doc verification); gh issue comment 29 (Closing recommendation comment explaining the audit conflict and asking the implementing agent to verify against the live developer-network page); gh issue edit 29 --add-label needs-decision
**Reasoning:** Doc-conformance audit said docs show only the 4 listed verbs (no DELETE) and the issue is correct. Codex audit said docs DO list DELETE and the issue is incomplete. Cannot resolve from the audit data alone — flagged for maintainer/implementer to verify.
**Remaining concerns:** DELETE endpoint existence; POST dual-purpose semantics.

### Issue #30: Coverage: Configuration: deposit profiles + import profiles (read-only)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — four GET endpoints match docs; deprecated POST correctly omitted
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. The note that POST /md-import-profiles/{profile_id} is deprecated is documented and correctly excluded.
**Remaining concerns:** None.

### Issue #31: Coverage: Configuration: license terms CRUD

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — POST/GET/PUT/DELETE all match docs; absence of GET-list correctly noted
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. The note that no GET-list endpoint is exposed (callers must use Analytics or know codes) is doc-confirmed.
**Remaining concerns:** None.

### Issue #32: Coverage: Configuration: open hours + relations

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 5/5
**Overall status:** Aligned — seven endpoints match docs; library-scoped variant correctly GET-only
**Final decision:** Leave unchanged
**Changes made:** None
**Reasoning:** Both audits aligned. Disambiguation of 'relations' (bib record relationships, not user) and library-scoped open-hours being read-only are both correct.
**Remaining concerns:** None.

### Issue #33: Coverage: Configuration: letters + printers (read + letter update)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits (primary + codex direct) agree the endpoint set, HTTP verbs, read/write scope, and signatures match docs. AC are explicit and testable. No edit needed.
**Remaining concerns:** None.

### Issue #34: Coverage: Configuration: reminders CRUD (config-level)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits confirm full CRUD endpoints (list/create/get/update/delete) match docs at /almaws/v1/conf/reminders[/{id}]. Pagination params are conventional. AC + impl notes are explicit.
**Remaining concerns:** None.

### Issue #35: Coverage: Configuration: workflows runner + utilities

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits agree the three endpoints (workflow run, fee-transactions report, general configuration) are documented and signatures are reasonable. **filters kwargs pass-through is appropriate since docs don't enumerate required filters.
**Remaining concerns:** None.

### Issue #36: Coverage: Users: list & search users

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 3/5, ready 4/5, ac 4/5, scope 4/5, align 3/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewritten
**Changes made:** body-rewritten
**Reasoning:** Primary audit flagged the signature as narrower than docs allow — missing optional filters (order_by, expand, source_user_id, modify_date_from). Rewrote body using template, exposed all documented optional query params explicitly (rather than **kwargs) so type-checker/IDE users get autocomplete. Added redaction concern for personal-data endpoint.
**Remaining concerns:** Open question on whether search_users should keep List return or use full envelope for symmetry — left for implementer to decide.

### Issue #37: Coverage: Users: create / delete user (CRUD completeness)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits confirm POST and DELETE endpoints match docs. Required-field list (primary_id, account_type, status, user_group) is consistent with docs. AC explicit, no signature mismatches.
**Remaining concerns:** None.

### Issue #38: Coverage: Users: authentication operations (POST /users/{id})

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 2/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits confirm POST /almaws/v1/users/{user_id} with op=auth/refresh matches docs. AC explicitly captures both op values and password-redaction requirement. No changes needed.
**Remaining concerns:** None.

### Issue #39: Coverage: Users: user attachments

**Classification:** api-coverage
**Scores:** docTech 3/5, clarity 3/5, tech 3/5, robust 3/5, ready 3/5, ac 3/5, scope 4/5, align 2/5, risk 3/5
**Overall status:** partially-aligned
**Final decision:** rewritten
**Changes made:** body-rewritten
**Reasoning:** Both audits flagged: (1) get_user_attachment -> bytes is wrong; docs describe Attachment object with expand=content/content_no_encoding query param, (2) POST upload shape (multipart vs JSON+base64) not verified. Rewrote body with corrected return type Dict[str, Any], added expand parameter, flagged the multipart-vs-JSON question as an Open question requiring doc verification before coding.
**Remaining concerns:** Multipart vs JSON+base64 must be verified at implementation time — left as explicit Open question.

### Issue #40: Coverage: Users: loans (list, create, get, renew, change due date)

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 4/5, scope 4/5, align 2/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewritten
**Changes made:** body-rewritten
**Reasoning:** Both audits flagged that create_user_loan flattens query and body params: per docs, item_barcode/item_pid + user_id_type are query params (one of barcode/pid mandatory), while library/circ_desk live in the body. Rewrote signature to separate query kwargs (item_barcode/item_pid/user_id_type as keyword-only) from a dedicated loan_data body dict. Added validation requirements for mutual exclusivity.
**Remaining concerns:** Whether change_loan_due_date PUT requires full Loan object or accepts partial — left as Open question for implementer.

### Issue #41: Coverage: Users: requests (list, create, get, cancel, action, update)

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 4/5, scope 4/5, align 3/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewritten
**Changes made:** body-rewritten
**Reasoning:** Primary audit said Aligned, but codex direct flagged that cancel_user_request should require reason because Alma documents reason as a required query parameter on DELETE /requests/{id}. Took the stricter codex finding: rewrote signature to make reason a required positional parameter with non-empty validation, explicitly using DELETE (not POST op=cancel). Also clarified that DELETE is the documented cancel verb.
**Remaining concerns:** Specific op values for action POST are not enumerated on public docs index — implementer should document the ones tested.

### Issue #42: Coverage: Users: resource sharing requests (user-side)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits confirm the four endpoints (POST/GET/DELETE plus action POST with op) are documented at the listed paths. Python signatures correctly model the action op query param. Note about user-side vs partner-side is preserved.
**Remaining concerns:** Specific op values are not enumerated in docs — verification at implementation time only.

### Issue #43: Coverage: Users: purchase requests

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits confirm all four endpoints exist (GET list, POST create, GET single, POST with op). Action method correctly threads op query param. Note distinguishing user-side vs acq-side is preserved.
**Remaining concerns:** None.

### Issue #44: Coverage: Users: fines & fees

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 3/5, ready 4/5, ac 4/5, scope 4/5, align 2/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewritten
**Changes made:** body-rewritten
**Reasoning:** Primary audit flagged three signature issues: (1) pay_all_user_fees missed op=pay + amount=ALL, (2) dispute_user_fee.reason wrongly required (only waive requires reason), (3) method='CASH' default leaks into non-pay ops. Codex direct said aligned but missed signature-level concerns. Took stricter primary-audit finding. Rewrote signatures so each op carries exactly the params Alma documents; amount as str (avoid float precision); method only on payment ops.
**Remaining concerns:** external_transaction_id usage for online payments — verify during integration testing.

### Issue #45: Coverage: Users: deposits

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits confirm all four endpoints (list, create, get, action with op) are documented. Generic perform_user_deposit_action(op) shape is appropriate since specific op values are not enumerated in public docs index.
**Remaining concerns:** None.

### Issue #46: Coverage: Bibs: complete holdings CRUD (update / delete)

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 3/5, robust 3/5, ready 4/5, ac 4/5, scope 4/5, align 2/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewritten
**Changes made:** body-rewritten
**Reasoning:** Both audits flagged: (1) override_attached_items is not a documented delete param — actual is bib (retain/delete/suppress), (2) codex direct also flagged that update body must be MARC-XML, not JSON. Rewrote signature: renamed parameter to holding_marc_xml: str, replaced override_attached_items with bib (literal allow-list validated), and prominently documented MARC-XML constraint.
**Remaining concerns:** Optional dict-to-MARC-XML helper is deferred to a follow-up unless callers ask.

### Issue #47: Coverage: Bibs: complete items CRUD (update / withdraw)

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 4/5, scope 4/5, align 3/5, risk 1/5
**Overall status:** partially-aligned
**Final decision:** rewritten
**Changes made:** body-rewritten
**Reasoning:** Both audits flagged: bibs (plural) parameter name must be bib (singular) to match Alma docs, and override query param is missing. Rewrote signature: renamed bibs -> bib, added override: bool = False, validated literal allow-lists for both holdings and bib values.
**Remaining concerns:** Whether update body is JSON only or also accepts MARC-XML — left as Open question for implementer.

### Issue #48: Coverage: Bibs: bib-attached portfolios CRUD

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 4/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits confirm all five endpoints (including documented trailing slash on POST) match docs. Primary audit notes minor enhancement opportunity (limit/offset on list_bib_portfolios) but classifies as aligned, not a hard mismatch. Skipping per Aligned + AC present rule.
**Remaining concerns:** Optional limit/offset enhancement on list method — minor, not blocking.

### Issue #49: Coverage: Bibs: bib-level requests

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 5/5, scope 4/5, align 4/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Audit (md) flagged missing user_id/user_id_type/allow_same_request query params on create. Audit (codex) flagged missing required reason on cancel. Body rewritten with documented optional/required query params on create_bib_request and required reason (plus note/notify_user) on cancel_bib_request. Added Background, Audit notes, checkbox AC, and preserved Domain/Priority/Effort/Files/References/Prerequisites.
**Remaining concerns:** op values for action POST not enumerated by Alma; surfaced as open question.

### Issue #50: Coverage: Bibs: item-level requests

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 5/5, scope 5/5, align 4/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Audit (md) marked aligned but codex flagged that cancel item request requires reason (camelCase placeholder {requestId}). Rewrote signatures to make reason required, surfaced documented user_id/user_id_type on create, added path-builder helper requirement, included open question on item_id vs item_pid placeholder inconsistency.
**Remaining concerns:** Alma docs use {item_id} and {item_pid} interchangeably; flagged for SANDBOX verification.

### Issue #51: Coverage: Bibs: loans (bib + item level)

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 5/5, scope 4/5, align 4/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Audit (md and codex) flagged that create_item_loan put library/circ_desk in signature as if they were query params; per docs only user_id (and optional user_id_type) are query params, library/circ_desk go in the loan body. Also docs document only op=renew for loan-action POST. Rewrote signature accordingly and defaulted op to 'renew'.
**Remaining concerns:** Some sites use library/circ_desk as query params despite undocumented; flagged in open questions.

### Issue #52: Coverage: Bibs: booking availability + request options

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 4/5, align 5/5, risk 1/5
**Overall status:** not-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Audit (md) flagged Not aligned: period is documented as mandatory xs:int but signature had period: str = None; period_type and consider_dlr were missing. Rewrote with period: int (required), period_type: str = 'days' (validated against {days, weeks, months}), and consider_dlr on bib request-options.
**Remaining concerns:** consider_dlr only documented at bib-level request-options; flagged for SANDBOX verification at item-level.

### Issue #53: Coverage: Bibs: collections CRUD (the collection itself)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits classify as aligned. AC includes the docs constraint (delete only when no bibs). Existing DO NOT re-implement note correctly distinguishes member-level vs collection-object methods. No edit needed.
**Remaining concerns:** None.

### Issue #54: Coverage: Bibs: bib-level e-collections (read)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits classify as aligned. Read-only scope correctly bounded; full e-collection CRUD lives under the Electronic domain (#67).
**Remaining concerns:** None.

### Issue #55: Coverage: Bibs: bib reminders CRUD

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits classify as aligned. Five reminder endpoints match docs verbatim; signatures appropriate.
**Remaining concerns:** None.

### Issue #56: Coverage: Bibs: authorities CRUD

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 5/5, scope 4/5, align 4/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Audit (md) flagged that body parameter should be authority_xml (not marc_xml) since the API requires an Authority XML wrapper, not raw MARC; also missing documented query params normalization, override_warning, check_match, import_profile. Audit (codex) added that list endpoint does NOT document a q parameter; documented filters are originating-system identifiers, limit, offset, view. Rewrote signatures to drop q from list_authorities, rename body to authority_xml, and surface all documented optional query params.
**Remaining concerns:** Whether wrapper helpers are needed to convert MARC XML to Authority XML; flagged as open question (recommend caller-provided for v1).

### Issue #57: Coverage: Bibs: bib record operations (POST /bibs/{mms_id})

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** not-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Both audits flagged Not aligned: docs only document op=unlink_from_nz on this POST endpoint. The previously proposed suppress_bib/unsuppress_bib are NOT implementable here — bib suppression is via PUT /bibs/{mms_id} with suppress_from_publishing. Rewrote to keep generic perform_bib_operation plus the only documented thin wrapper unlink_bib_from_nz. AC explicitly forbids introducing suppress/unsuppress wrappers and points callers to update_record.
**Remaining concerns:** SANDBOX may not have NZ-attached bibs to exercise unlink_from_nz; flagged in open questions.

### Issue #58: Coverage: Acquisitions: vendors CRUD + nested invoices/POLs

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 4/5, robust 4/5, ready 4/5, ac 5/5, scope 5/5, align 4/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Audit (md) flagged missing type filter (material_supplier/access_provider/licensor/governmental) and that status accepts lowercase active/inactive. Audit (codex) classified as aligned at path level. Rewrote list_vendors to expose documented type filter and status case requirement; preserved vendorCode camelCase URL convention.
**Remaining concerns:** Vendor type filter values may have additional documented values; capture in implementation.

### Issue #59: Coverage: Acquisitions: funds CRUD + fund service

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 4/5, robust 4/5, ready 4/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Both audits flagged that fund-service op only accepts activate/deactivate (NOT transfer/allocate — those go via fund-transactions endpoint #60). Also list_funds previously forced status='ACTIVE'. Rewrote to validate op enum, add convenience activate_fund/deactivate_fund wrappers, expand list_funds filter set, and default status to None. Cross-referenced #60 explicitly for transfers/allocations.
**Remaining concerns:** delete_fund cascade behavior with existing transactions; flagged for SANDBOX observation.

### Issue #60: Coverage: Acquisitions: fund transactions

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits classify as aligned. Generic transaction_data: Dict[str, Any] is correct since type/amount/related_fund are body fields (transfers/allocations live here). No edit needed.
**Remaining concerns:** None.

### Issue #61: Coverage: Acquisitions: PO Lines list + create + cancel

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 4/5, robust 4/5, ready 4/5, ac 5/5, scope 5/5, align 4/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Both audits flagged: (a) cancel_pol's reason_code should be reason (Alma's documented param name), and (b) missing documented optional inform_vendor/override/bib query params. Rewrote signature to rename to reason (required, no default), surface all documented optional params, and expand list_pol filter set to documented params. DO NOT re-implement section preserved.
**Remaining concerns:** Whether search_pol stays as separate convenience or becomes alias of list_pol; flagged as open question (recommended: keep both).

### Issue #62: Coverage: Acquisitions: invoice attachments CRUD

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 4/5, tech 5/5, robust 4/5, ready 4/5, ac 5/5, scope 5/5, align 5/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Audit (md) classified as aligned at path level, but audit (codex) correctly flagged that the rendered Alma docs describe Attachment JSON objects with base64 content (and expand=content/content_no_encoding), NOT multipart upload as the previous signatures assumed. Rewrote core CRUD to operate on Attachment dicts; layered file-IO convenience helpers (upload_invoice_attachment_from_file, download_invoice_attachment_to_file) on top.
**Remaining concerns:** Practical max base64 inline content size; flagged for SANDBOX observation.

### Issue #63: Coverage: Acquisitions: licenses + amendments + attachments

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 4/5, tech 5/5, robust 4/5, ready 4/5, ac 5/5, scope 5/5, align 5/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** body-rewritten-via-gh-issue-edit
**Reasoning:** Audit (md) classified as aligned at path level. Audit (codex) flagged that license attachments use Attachment JSON objects (base64 content), not multipart upload — same correction as #62. Rewrote attachment methods to operate on Attachment dicts plus file-IO convenience helpers. Round-trip integration test AC preserved.
**Remaining concerns:** Whether delete_license cascades or rejects when amendments/attachments exist; flagged for SANDBOX observation.

### Issue #64: Coverage: Acquisitions: lookups (currencies + fiscal periods)

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 5/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits classify as aligned. Read-only lookup endpoints with no-arg signatures. No edit needed.
**Remaining concerns:** None.

### Issue #65: Coverage: Acquisitions: purchase requests (acq-side)

**Classification:** api-coverage
**Scores:** docTech 3/5, clarity 4/5, tech 3/5, robust 3/5, ready 3/5, ac 3/5, scope 4/5, align 3/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit (claude.md + codex_direct) flagged the list endpoint's filters: documented filters are format / owning_library / status / citation_type / limit / offset, not q. The op POST is documented for approve and reject only; reject requires a reason. Rewrote signatures to match docs and added validation requirements.
**Remaining concerns:** Maintainer must confirm whether the wrapper should strict-whitelist op values or pass-through and let Alma surface the error.

### Issue #66: Coverage: Electronic: bootstrap Electronic domain class

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Foundation-only ticket; both audits mark it Aligned. No API endpoint claims to verify. Acceptance criteria are explicit and testable.
**Remaining concerns:** None.

### Issue #67: Coverage: Electronic: e-collections CRUD

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 4/5, robust 4/5, ready 4/5, ac 4/5, scope 5/5, align 5/5, risk 2/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits mark Aligned. All five endpoints/methods match documented Alma surface; signature defaults align with documented limit=10/offset=0 and optional q.
**Remaining concerns:** None.

### Issue #68: Coverage: Electronic: e-services CRUD

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 4/5, robust 4/5, ready 4/5, ac 4/5, scope 5/5, align 5/5, risk 2/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Both audits mark Aligned. All five endpoints exist and method signatures correctly thread collection_id and service_id.
**Remaining concerns:** None.

### Issue #69: Coverage: Electronic: electronic portfolios CRUD

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 3/5, robust 3/5, ready 3/5, ac 3/5, scope 4/5, align 3/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit: documented limit default is 10 (range 0..100); the proposed default of 100 was non-standard. List endpoint does not support q. Documented POST URL has trailing slash. Rewrote to align defaults and call out the trailing slash explicitly.
**Remaining concerns:** Validation policy for out-of-range limit values (clamp vs raise) needs maintainer confirmation.

### Issue #70: Coverage: TaskLists: bootstrap TaskLists domain class

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Foundation-only ticket; both audits mark it Aligned. TaskLists is an official Alma API area.
**Remaining concerns:** None.

### Issue #71: Coverage: TaskLists: requested resources

**Classification:** api-coverage
**Scores:** docTech 3/5, clarity 4/5, tech 2/5, robust 3/5, ready 2/5, ac 3/5, scope 4/5, align 2/5, risk 3/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit: POST endpoint requires library + circ_desk + op as mandatory query params; only op=mark_reported is documented; request_ids is not a documented input. Rewrote action signature to require library/circ_desk and drop request_ids.
**Remaining concerns:** Whether to whitelist op values or pass-through; whether undocumented op values are used in production.

### Issue #72: Coverage: TaskLists: lending requests workflow

**Classification:** api-coverage
**Scores:** docTech 2/5, clarity 4/5, tech 2/5, robust 2/5, ready 1/5, ac 3/5, scope 3/5, align 1/5, risk 4/5
**Overall status:** not-aligned
**Final decision:** rewrite-substantive
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit (flagship Not aligned): proposed ship_lending_requests / receive_lending_requests do NOT map to POST /almaws/v1/task-lists/rs/lending-requests, which only documents op=mark_reported and requires library. Ship/receive workflows live on partner-side endpoints. Removed those helpers from the ticket and noted that a follow-up partner-side ticket should be filed.
**Remaining concerns:** Need a follow-up ticket for partner-side ship/receive/return/cancel against POST /almaws/v1/partners/{code}/lending-requests/{id}; maintainer must confirm the helper drop.

### Issue #73: Coverage: TaskLists: printouts

**Classification:** api-coverage
**Scores:** docTech 3/5, clarity 4/5, tech 2/5, robust 3/5, ready 2/5, ac 3/5, scope 4/5, align 2/5, risk 3/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit: POST /almaws/v1/task-lists/printouts/create is not present in published Alma docs and the proposed JSON-body create_printout signature is unimplementable; documented op values for the bulk action are mark_as_printed and mark_as_canceled. Removed create_printout from the ticket and added op whitelist guidance.
**Remaining concerns:** Maintainer should confirm the dropped create_printout method and decide on op whitelist vs pass-through.

### Issue #74: Coverage: ResourceSharing: partner management CRUD

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 3/5, robust 3/5, ready 3/5, ac 3/5, scope 5/5, align 3/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Both audits flagged the same issue: documented filters on GET /almaws/v1/partners are limit, offset, status only; q and type_filter are not documented. Partner type taxonomy is response metadata, not a list filter. Rewrote list_partners signature accordingly.
**Remaining concerns:** Type-validation policy on create_partner (per partner type) needs maintainer direction.

### Issue #75: Coverage: Courses: bootstrap Courses domain class

**Classification:** api-coverage
**Scores:** docTech 5/5, clarity 5/5, tech 5/5, robust 4/5, ready 5/5, ac 5/5, scope 5/5, align 5/5, risk 1/5
**Overall status:** aligned
**Final decision:** unchanged
**Changes made:** None
**Reasoning:** Foundation-only ticket; both audits mark Aligned. Courses is an official Alma API area.
**Remaining concerns:** None.

### Issue #76: Coverage: Courses: courses CRUD + enrollment

**Classification:** api-coverage
**Scores:** docTech 2/5, clarity 4/5, tech 2/5, robust 2/5, ready 1/5, ac 3/5, scope 4/5, align 1/5, risk 4/5
**Overall status:** not-aligned
**Final decision:** rewrite-substantive
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit (flagship Not aligned): POST /almaws/v1/courses/{course_id} is dispatched by query params (op + user_ids/list_ids comma-separated), not a JSON body. Replaced enroll_to_course(enrollment_data: Dict) with two strict-dispatch helpers enroll_users_in_course and associate_reading_lists.
**Remaining concerns:** Maintainer must confirm the helper split and decide whether to chunk large user_ids lists.

### Issue #77: Coverage: Courses: reading lists + citations + owners + tags

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 3/5, robust 3/5, ready 3/5, ac 3/5, scope 3/5, align 3/5, risk 3/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit: POST .../citations/{citation_id} is op-driven per Alma convention; tags are objects, not bare strings. Rewrote remove_citation_file as a generic perform_citation_action(op) and changed update_citation_tags to accept List[Dict[str, Any]].
**Remaining concerns:** Whether to ship convenience remove_citation_file after verifying op value; whether to split into three PRs; whether tags accepts strings for ergonomics.

### Issue #78: Coverage: ResourceSharing: directory members (list/get/localize)

**Classification:** api-coverage
**Scores:** docTech 2/5, clarity 4/5, tech 2/5, robust 2/5, ready 1/5, ac 3/5, scope 4/5, align 1/5, risk 4/5
**Overall status:** not-aligned
**Final decision:** rewrite-substantive
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit (flagship Not aligned): POST /RSDirectoryMember/{partner_code} (Localize Member) documents Body Parameters: None and no extra query params; the previous localization_data: Dict body was invented. List endpoint does not document limit/offset. Rewrote both signatures.
**Remaining concerns:** Maintainer should confirm the no-body POST and decide whether localize should auto-fetch the resulting Partner.

### Issue #79: Coverage: Analytics: paths endpoint

**Classification:** api-coverage
**Scores:** docTech 4/5, clarity 4/5, tech 3/5, robust 3/5, ready 3/5, ac 3/5, scope 5/5, align 3/5, risk 2/5
**Overall status:** partially-aligned
**Final decision:** rewrite
**Changes made:** edited-body, added-comment, added-label:needs-decision
**Reasoning:** Audit: {path} placeholder is documented as optional; collapsed the two proposed methods into one get_analytics_paths(path=None) that mirrors the documented contract. Made the XML response format and project-memory PRODUCTION-only credential constraint explicit in the docstring requirements.
**Remaining concerns:** Single method vs original two-method ergonomic split; return type (XML vs pre-parsed dict) — both for maintainer decision.
