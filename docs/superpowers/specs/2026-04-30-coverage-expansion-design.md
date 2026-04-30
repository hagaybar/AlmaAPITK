# Coverage Expansion — Design Spec

**Date:** 2026-04-30
**Branch:** `research/wrapper-comparison`
**Status:** Approved by user; backlog filed as GitHub issues with label `api-coverage`.

---

## 1. Goal

Increase AlmaAPITK's coverage of the published Alma REST API. The motivation
is breadth, not a specific librarian need: produce a prioritized backlog of
issues so the toolkit gradually covers the full Alma core API surface.

## 2. Scope

**In scope (Alma core only):** Bibs, Users, Acquisitions, Configuration,
Courses, Resource Sharing Partners, Task Lists, Electronic Resources,
Analytics, Resource Sharing Directory Members.

**Out of scope this round:** Primo, Primo VE, Leganto, Esploro, Rosetta,
Cloud Apps API, NCIP/Z39.50.

## 3. Decisions

### 3.1 Granularity

**One GitHub issue per logical method group** (~3–8 methods per issue). A
future agent picks a single issue and ships a coherent slice in one PR.
Splitting endpoints further produces artificial sequencing; consolidating
further produces multi-week tickets that don't fit one PR.

### 3.2 Filter / metadata scheme

| Dimension | Mechanism | Values |
|---|---|---|
| Coverage filter | Label `api-coverage` | (single) |
| Priority | Labels `priority:high` / `priority:medium` / `priority:low` | three tiers |
| Title prefix | String `Coverage: <Domain>: <topic>` | grep-friendly |
| Body fields | Standard template (§3.3) | structured |

A future agent searches `is:open is:issue label:api-coverage` to get the
full backlog, optionally narrowed by `label:priority:high`.

### 3.3 Issue body template

Every coverage issue MUST start with this block:

```
**Domain:** Configuration / Users / Bibs / Acquisitions / etc.
**Priority:** High / Medium / Low
**Effort:** S (≤½ day) / M (1–3 days) / L (>3 days)
**API endpoints touched:** <list of HTTP method + path>
**Methods to add:** <proposed Python signatures>
**Files to touch:** <paths in src/almaapitk/>
**References:** <Alma dev-network URL + project files to mirror>

## Acceptance criteria
- <bullet list>

## Notes for the implementing agent
- <pitfalls, related skills, test strategy, sandbox prerequisites>
```

For the four partial-overlap issues (§6) the body also includes a
**`DO NOT re-implement`** block listing the existing methods with file:line
refs.

### 3.4 Priority assignment

| Tier | Domains | Rationale |
|---|---|---|
| **High** | Configuration (Admin), Users | Highest volume of consumer-project automation; explicit user direction |
| **Medium** | Bibs, Acquisitions, Electronic, TaskLists, Resource Sharing Partners | Required for coverage parity but lower immediate consumer demand |
| **Low** | Courses, RS Directory Members, Analytics paths | Explicit user direction; small or niche surface |

## 4. Coverage gap matrix

| Domain | Current state | Endpoint groups missing | Issues filed |
|---|---|---|---|
| Configuration | Sets read-only (Admin domain) | 14 | 14 |
| Users & Fulfillment | get/update + helpers | 10 | 10 |
| Bibs / Inventory | core CRUD + MARC + reps + collection members | 12 | 12 |
| Acquisitions | invoices + POLs deep | 8 | 8 |
| Electronic Resources | none | 4 | 4 |
| Task Lists | none | 4 | 4 |
| RS Partners | partial lending | 1 | 1 |
| RS Directory Members | none | 1 | 1 |
| Analytics | reports | 1 | 1 |
| Courses | none | 3 | 3 |
| **Total** | | **58** | **58** |

## 5. The 58 issues

### High priority — Configuration (14 issues)

| # | Title | Foundation? |
|---|---|---|
| 1 | Coverage: Configuration: bootstrap Configuration domain class | yes — blocks 3-14 |
| 2 | Coverage: Configuration: Sets full CRUD + member management (extends Admin) | — |
| 3 | Coverage: Configuration: organization units (libraries, departments, circ desks) | — |
| 4 | Coverage: Configuration: locations CRUD | — |
| 5 | Coverage: Configuration: code tables (list/get/update) | — |
| 6 | Coverage: Configuration: mapping tables (list/get/update) | — |
| 7 | Coverage: Configuration: jobs (list, run, instances, events, matches) | — |
| 8 | Coverage: Configuration: integration profiles CRUD | — |
| 9 | Coverage: Configuration: deposit profiles + import profiles (read) | — |
| 10 | Coverage: Configuration: license terms CRUD | — |
| 11 | Coverage: Configuration: open hours + relations | — |
| 12 | Coverage: Configuration: letters + printers | — |
| 13 | Coverage: Configuration: reminders CRUD (config-level) | — |
| 14 | Coverage: Configuration: workflows runner + utilities | — |

### High priority — Users (10 issues)

| # | Title |
|---|---|
| 15 | Coverage: Users: list & search users |
| 16 | Coverage: Users: create / delete user (CRUD completeness) |
| 17 | Coverage: Users: authentication operations (POST /users/{id}) |
| 18 | Coverage: Users: user attachments |
| 19 | Coverage: Users: loans (list/create/get/renew/change due date) |
| 20 | Coverage: Users: requests (list/create/get/cancel/action/update) |
| 21 | Coverage: Users: resource sharing requests (user-side) |
| 22 | Coverage: Users: purchase requests |
| 23 | Coverage: Users: fines & fees |
| 24 | Coverage: Users: deposits |

### Medium priority — Bibs (12 issues)

| # | Title |
|---|---|
| 25 | Coverage: Bibs: complete holdings CRUD (update/delete) |
| 26 | Coverage: Bibs: complete items CRUD (update/withdraw) |
| 27 | Coverage: Bibs: bib-attached portfolios CRUD |
| 28 | Coverage: Bibs: bib-level requests |
| 29 | Coverage: Bibs: item-level requests |
| 30 | Coverage: Bibs: loans (bib + item level) |
| 31 | Coverage: Bibs: booking availability + request options |
| 32 | Coverage: Bibs: collections CRUD (extends existing member ops) |
| 33 | Coverage: Bibs: bib-level e-collections (read) |
| 34 | Coverage: Bibs: bib reminders CRUD |
| 35 | Coverage: Bibs: authorities CRUD |
| 36 | Coverage: Bibs: bib record operations (POST /bibs/{mms_id}) |

### Medium priority — Acquisitions (8 issues)

| # | Title |
|---|---|
| 37 | Coverage: Acquisitions: vendors CRUD + nested invoices/POLs |
| 38 | Coverage: Acquisitions: funds CRUD + fund service |
| 39 | Coverage: Acquisitions: fund transactions |
| 40 | Coverage: Acquisitions: PO Lines list + create + cancel (extends existing POL methods) |
| 41 | Coverage: Acquisitions: invoice attachments CRUD |
| 42 | Coverage: Acquisitions: licenses + amendments + attachments |
| 43 | Coverage: Acquisitions: lookups (currencies + fiscal periods) |
| 44 | Coverage: Acquisitions: purchase requests (acq-side) |

### Medium priority — Electronic / TaskLists / Partners (9 issues)

| # | Title | Foundation? |
|---|---|---|
| 45 | Coverage: Electronic: bootstrap Electronic domain class | yes — blocks 46-48 |
| 46 | Coverage: Electronic: e-collections CRUD | — |
| 47 | Coverage: Electronic: e-services CRUD | — |
| 48 | Coverage: Electronic: electronic portfolios CRUD | — |
| 49 | Coverage: TaskLists: bootstrap TaskLists domain class | yes — blocks 50-52 |
| 50 | Coverage: TaskLists: requested resources | — |
| 51 | Coverage: TaskLists: lending requests workflow (extends ResourceSharing) | — |
| 52 | Coverage: TaskLists: printouts | — |
| 53 | Coverage: ResourceSharing: partner management CRUD | — |

### Low priority (5 issues)

| # | Title | Foundation? |
|---|---|---|
| 54 | Coverage: Courses: bootstrap Courses domain class | yes — blocks 55-56 |
| 55 | Coverage: Courses: courses CRUD + enrollment | — |
| 56 | Coverage: Courses: reading lists + citations + owners + tags | — |
| 57 | Coverage: ResourceSharing: directory members | — |
| 58 | Coverage: Analytics: paths endpoint | — |

## 5.5 Recommended logical order

The 77 issues span architecture (#3–#21) and coverage (#22–#79). Some
architecture changes pay back across every coverage method that ships after
them — landing them first prevents repeated rework. The recommended sequence
below treats the architecture suite as a foundation, then layers coverage on
top by priority.

A future agent may pick out-of-order if a specific business need overrides;
the ordering is a recommendation, not a hard requirement.

### Phase 1 — HTTP foundation (architecture)

Land these before any bulk new method work; they touch every HTTP call.

- #3 Persistent `requests.Session`
- #4 Consolidate verbs into `_request()`
- #5 Retry with exponential backoff (429 / 5xx)
- #6 Configurable timeout (60s default)
- #14 Replace `print()` with logger; remove `safe_request()`

### Phase 2 — Correctness & ergonomics (architecture)

- #16 Tighten exception handling; cache `AlmaResponse.data`
- #9 Map Alma error codes to specific exception subclasses
- #10 Propagate `tracking_id` and `alma_code` on errors
- #13 Context-manager (`with`-statement) support
- #7 Configurable region / host

### Phase 3 — Pagination + accessor ergonomics (architecture)

- #11 `iter_paged()` generator at the client level
- #15 Hierarchical accessors (`client.acq.invoices...`)

### Phase 4 — Coverage foundations (high & medium priority)

These bootstrap tickets create new domain classes; their siblings can't start
until these merge.

- #22 Configuration domain class — unblocks 12 high-priority Configuration tickets
- #66 Electronic domain class — unblocks 3 medium-priority tickets
- #70 TaskLists domain class — unblocks 3 medium-priority tickets

(#75 Courses bootstrap stays in Phase 9 due to LOW priority.)

### Phase 5 — High-priority coverage

24 tickets that the toolkit's consumer projects need most.

- Configuration: #23–#35 (13 tickets)
- Users: #36–#45 (10 tickets)

### Phase 6 — Architecture: rate-limit, async, advanced

These add capabilities that materially change how Phase 7 work is built; if
you're about to write a 10-method bulk batch, land these first.

- #8 Client-side rolling-window rate limiting
- #18 Async / concurrent bulk-call primitive
- #21 CSV/DataFrame `BatchRunner` with checkpointing
- #19 Dedicated MARC manipulation layer
- #20 OpenAPI-driven request/response validation
- #12 Optional Pydantic response models (derived from #20's vendored specs)

### Phase 7 — Medium-priority coverage

29 tickets covering Bibs, Acquisitions, Electronic, TaskLists, Resource Sharing
Partners.

- Bibs: #46–#57 (12 tickets)
- Acquisitions: #58–#65 (8 tickets)
- Electronic: #67–#69 (3 tickets, after #66 from Phase 4)
- TaskLists: #71–#73 (3 tickets, after #70 from Phase 4)
- Resource Sharing Partners: #74

### Phase 8 — Distribution / metadata

- #17 LICENSE file + PyPI metadata cleanup

### Phase 9 — Low-priority coverage

Defer until everything above is in good shape.

- #75 Courses bootstrap → #76 → #77
- #78 Resource Sharing Directory Members
- #79 Analytics paths endpoint

### Quick-start summary

If a future agent has limited time and wants the highest-value first move,
start with **#3 → #4 → #14**. Those three together unlock retries, timeouts,
rate-limiting, and any new domain method that follows; nothing else materially
benefits all of #22–#79 the way they do.

## 6. Partial-overlap warnings

These four issues **extend** existing methods rather than introducing a new
group. The implementing agent must read the issue's `DO NOT re-implement`
block before starting.

| # | Existing today | Issue adds (only) |
|---|---|---|
| 2 | `Admin.list_sets`, `get_set_info`, `get_set_members`, `validate_user_set` (`src/almaapitk/domains/admin.py`) | `create_set`, `update_set`, `delete_set`, `manage_set_members` |
| 32 | `BibliographicRecords.get_collection_members`, `add_to_collection`, `remove_from_collection` (`src/almaapitk/domains/bibs.py:692-779`) | `list_collections`, `create_collection`, `get_collection`, `update_collection`, `delete_collection` |
| 40 | `Acquisitions.get_pol`, `update_pol`, `get_pol_items`, `receive_item` (`src/almaapitk/domains/acquisition.py:1534-1866`) | `list_pol`, `search_pol`, `create_pol`, `cancel_pol` |
| 51 | `ResourceSharing.create_lending_request`, `get_lending_request`, `get_request_summary` (partner-side; `src/almaapitk/domains/resource_sharing.py:165-478`) | task-lists workflow endpoint `/almaws/v1/task-lists/rs/lending-requests` for ship/receive/return/cancel actions on existing lending requests |

## 7. Foundation / blocking dependencies

Foundation tickets create a new domain class (with `__init__`, lazy import,
public-API export, and smoke test). They block all sibling tickets in the
same domain. There are four:

- **#1** Configuration bootstrap → blocks #3–#14
- **#45** Electronic bootstrap → blocks #46–#48
- **#49** TaskLists bootstrap → blocks #50–#52
- **#54** Courses bootstrap → blocks #55–#56

`#2 Sets full CRUD + member management` extends the existing `Admin`
domain (does NOT depend on #1 — `Admin` already exists).

## 8. References

| Domain | Alma developer-network URL |
|---|---|
| Bibs | https://developers.exlibrisgroup.com/alma/apis/bibs/ |
| Users | https://developers.exlibrisgroup.com/alma/apis/users/ |
| Acquisitions | https://developers.exlibrisgroup.com/alma/apis/acq/ |
| Configuration | https://developers.exlibrisgroup.com/alma/apis/conf/ |
| Courses | https://developers.exlibrisgroup.com/alma/apis/courses/ |
| Electronic | https://developers.exlibrisgroup.com/alma/apis/electronic/ |
| Partners | https://developers.exlibrisgroup.com/alma/apis/partners/ |
| Task Lists | https://developers.exlibrisgroup.com/alma/apis/tasklists/ |
| Analytics | https://developers.exlibrisgroup.com/alma/apis/analytics/ |
| RS Directory | https://developers.exlibrisgroup.com/alma/apis/rsdirectorymember/ |

For complete endpoint method lists, see the per-issue **API endpoints
touched** block.

## 9. Future agent runbook

When picking up a coverage issue:

1. **Filter:** `gh issue list --label api-coverage --label priority:high --state open` (start at high priority).
2. **Check foundation:** if the issue depends on a `bootstrap` ticket, verify that ticket has been completed first.
3. **Read the partial-overlap warning** (§6) if present in the issue body.
4. **Read the relevant skill:** every coverage issue references the `alma-api-expert` and `python-dev-expert` skills. Use them.
5. **Read the file the issue says to touch** plus the closest existing domain method as a pattern source. Mirror its style: parameter validation via `AlmaValidationError`, logging via `self.logger`, return `AlmaResponse` (raw HTTP) or `Dict[str, Any]` (parsed payload), use the client's `get/post/put/delete` methods, never call `requests` directly.
6. **Test in SANDBOX first.** Production credentials are off-limits unless the issue explicitly calls for them.
7. **Run validation:** `poetry run python scripts/smoke_import.py` and `poetry run pytest tests/test_public_api_contract.py -v` must still pass.
8. **Update the public API contract test** if the issue adds new public symbols.
9. **Update CLAUDE.md** if the issue adds a new domain class.

## 10. Issue creation tooling

Issues are created via `scripts/file_coverage_issues.py` (one-off; can be
re-run idempotently — script checks `gh issue list` for existing titles
and skips duplicates). The script is a record of exactly what was filed
and serves as the single source of truth for issue bodies.

## 11. Open follow-ups (post-filing)

- Once the issues are filed, link this spec to `CLAUDE.md` "Skills
  Integration" section so the `alma-api-expert` skill picks it up.
- Consider creating a coverage progress dashboard view in the GitHub
  project after a few issues are closed.
- Future rounds: if Primo / Esploro / Leganto coverage is later wanted,
  spawn a separate spec; do not stretch this one.
