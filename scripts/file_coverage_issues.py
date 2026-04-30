#!/usr/bin/env python3
"""
File the 58 Alma API coverage-expansion issues defined in
docs/superpowers/specs/2026-04-30-coverage-expansion-design.md.

Idempotent: skips any issue whose exact title already exists on the repo.
Run from repo root: `python scripts/file_coverage_issues.py [--dry-run]`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Issue data model
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    title: str
    domain: str
    priority: str           # "high" | "medium" | "low"
    effort: str             # "S" | "M" | "L"
    endpoints: list[str]    # ["GET /almaws/v1/...", ...]
    methods: list[str]      # ["def list_X(...) -> AlmaResponse", ...]
    files: list[str]
    references: list[str]
    acceptance: list[str]
    notes: str
    foundation: bool = False
    blocks: list[str] = field(default_factory=list)
    extends_existing: Optional[dict] = None  # {"existing": [...], "do_not_reimplement": "..."}

    @property
    def labels(self) -> list[str]:
        out = ["api-coverage", f"priority:{self.priority}"]
        return out


# ---------------------------------------------------------------------------
# Body renderer
# ---------------------------------------------------------------------------

EFFORT_LABEL = {"S": "S (≤½ day)", "M": "M (1–3 days)", "L": "L (>3 days)"}
PRIORITY_LABEL = {"high": "High", "medium": "Medium", "low": "Low"}


def render(issue: Issue) -> str:
    lines: list[str] = []
    lines.append(f"**Domain:** {issue.domain}")
    lines.append(f"**Priority:** {PRIORITY_LABEL[issue.priority]}")
    lines.append(f"**Effort:** {EFFORT_LABEL[issue.effort]}")
    if issue.foundation:
        lines.append(f"**Foundation:** YES — blocks {', '.join(issue.blocks) if issue.blocks else 'sibling issues in same domain'}")
    lines.append("")

    lines.append("## API endpoints touched")
    for ep in issue.endpoints:
        lines.append(f"- `{ep}`")
    lines.append("")

    lines.append("## Methods to add")
    lines.append("```python")
    for m in issue.methods:
        lines.append(m)
    lines.append("```")
    lines.append("")

    lines.append("## Files to touch")
    for f in issue.files:
        lines.append(f"- `{f}`")
    lines.append("")

    lines.append("## References")
    for r in issue.references:
        lines.append(f"- {r}")
    lines.append("")

    if issue.extends_existing:
        lines.append("## DO NOT re-implement")
        lines.append("These methods already exist — extend, don't duplicate:")
        for entry in issue.extends_existing["existing"]:
            lines.append(f"- {entry}")
        lines.append("")
        lines.append(issue.extends_existing.get("note", ""))
        lines.append("")

    lines.append("## Acceptance criteria")
    for a in issue.acceptance:
        lines.append(f"- {a}")
    lines.append("")

    lines.append("## Notes for the implementing agent")
    lines.append(textwrap.dedent(issue.notes).strip())
    lines.append("")

    lines.append("---")
    lines.append("Filed as part of the coverage-expansion backlog. See "
                 "`docs/superpowers/specs/2026-04-30-coverage-expansion-design.md` for context.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standard fragments to keep per-issue data compact
# ---------------------------------------------------------------------------

REF_API_EXPERT = "Use the `alma-api-expert` skill for endpoint quirks and validation rules"
REF_PY_EXPERT = "Use the `python-dev-expert` skill for code patterns (pagination, error handling, type hints)"
REF_CLAUDE_MD = "`CLAUDE.md` — domain-class pattern (Client-Domain pattern)"
REF_CLIENT = "`src/almaapitk/client/AlmaAPIClient.py` — HTTP verbs (`client.get/post/put/delete`)"
REF_RESPONSE = "`src/almaapitk/_internal/response.py` — `AlmaResponse` wrapper"
REF_LOGGING = "`src/almaapitk/alma_logging/` — `get_logger(...)` (NEVER use print)"
REF_PUBLIC_API = "`src/almaapitk/__init__.py` — add to `__all__` and `_lazy_imports` if exposing new public symbols"
REF_CONTRACT_TEST = "`tests/test_public_api_contract.py` — extend if new public symbols are added"
REF_VALIDATION = "Validate inputs with `AlmaValidationError`; raise `AlmaAPIError` for API failures"

STANDARD_NOTES_DOMAIN_METHOD = """
- Mirror an existing domain method as the pattern source (e.g., `Acquisitions.get_invoice` for read, `Acquisitions.create_invoice_simple` for write).
- All public methods must have type hints + Google-style docstrings.
- Validate required inputs at top of method and raise `AlmaValidationError` with a clear message.
- Log method entry with key parameters (info), success with result identifiers (info), and errors with full context (error).
- NEVER print — use `self.logger`.
- Test in SANDBOX first. Add at least one unit test under `tests/unit/` and one integration test under `tests/integration/`.
- After implementation, `poetry run python scripts/smoke_import.py` and the public-API contract test MUST pass.
"""

STANDARD_AC_DOMAIN_EXTENSION = [
    "All listed methods implemented on the existing domain class with type hints and docstrings.",
    "Each method has unit-test coverage (mocked HTTP) and at least one integration test against SANDBOX.",
    "Errors raise `AlmaValidationError` (input) or `AlmaAPIError` / subclass (API).",
    "All operations logged through `alma_logging` (no `print`).",
    "`scripts/smoke_import.py` and `tests/test_public_api_contract.py` still pass.",
    "If new public symbols are exposed, they are added to `almaapitk/__init__.py` `__all__` and the lazy import map.",
]


# ---------------------------------------------------------------------------
# The 58 issues
# ---------------------------------------------------------------------------

ISSUES: list[Issue] = []


def _bootstrap_issue(domain: str, class_name: str, blocks_range: str,
                     module_filename: str, dev_url: str, priority: str) -> Issue:
    return Issue(
        title=f"Coverage: {domain}: bootstrap {domain} domain class",
        domain=domain,
        priority=priority,
        effort="M",
        foundation=True,
        blocks=[blocks_range],
        endpoints=["(no endpoints in this issue — foundation only)"],
        methods=[
            f"class {class_name}:",
            "    def __init__(self, client: AlmaAPIClient): ...",
            "    def get_environment(self) -> str: ...",
            "    def test_connection(self) -> bool: ...",
        ],
        files=[
            f"src/almaapitk/domains/{module_filename} (NEW)",
            "src/almaapitk/__init__.py (add to __all__ + lazy import map)",
            "src/almaapitk/_internal/__init__.py (re-export)",
            "tests/test_public_api_contract.py (assert new symbol exists)",
        ],
        references=[
            f"Alma dev-network: {dev_url}",
            REF_CLAUDE_MD + " — section 'Domain Classes (`src/almaapitk/domains/`)'",
            REF_CLIENT,
            REF_LOGGING,
            REF_PUBLIC_API,
            REF_CONTRACT_TEST,
            "Mirror existing pattern from `src/almaapitk/domains/admin.py` (small, well-bounded existing domain)",
        ],
        acceptance=[
            f"New file `src/almaapitk/domains/{module_filename}` exists with `{class_name}` class.",
            f"`from almaapitk import {class_name}` works (lazy import wired).",
            "`scripts/smoke_import.py` passes.",
            f"`tests/test_public_api_contract.py` asserts the new `{class_name}` symbol.",
            "`CLAUDE.md` 'Domain Classes' table updated to list the new domain.",
            "No actual API methods implemented in this issue — those land in sibling tickets.",
        ],
        notes=f"""
- This is a foundation-only ticket. The goal is to establish the class skeleton, public-API plumbing, and tests so that the sibling coverage tickets ({blocks_range}) can each ship one focused PR.
- Pattern source: `src/almaapitk/domains/admin.py` (compact, follows the project conventions).
- Do NOT implement API methods in this PR — they belong to the sibling tickets. Only `__init__`, `get_environment`, `test_connection`.
- Wire the lazy import in `src/almaapitk/__init__.py` exactly like the other domains (see `_lazy_imports` dict).
""",
    )


# ===========================================================================
# CONFIGURATION (high) — issues 1-14
# ===========================================================================

ISSUES.append(_bootstrap_issue(
    "Configuration", "Configuration", "issues 3-14",
    "configuration.py",
    "https://developers.exlibrisgroup.com/alma/apis/conf/",
    "high",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: Sets full CRUD + member management",
    domain="Configuration",
    priority="high",
    effort="M",
    extends_existing={
        "existing": [
            "`Admin.list_sets` — `src/almaapitk/domains/admin.py:439`",
            "`Admin.get_set_info` — `src/almaapitk/domains/admin.py:313`",
            "`Admin.get_set_members` — `src/almaapitk/domains/admin.py:39`",
            "`Admin.get_user_set_members`, `get_bib_set_members` — :107, :123",
            "`Admin.validate_user_set` — :141",
            "`Admin.get_set_metadata_and_member_count` — :353",
        ],
        "note": "Extend the existing `Admin` class. Do NOT move set methods to `Configuration` — that would break the `Admin` public API.",
    },
    endpoints=[
        "POST /almaws/v1/conf/sets — Create set",
        "PUT /almaws/v1/conf/sets/{set_id} — Update set",
        "DELETE /almaws/v1/conf/sets/{set_id} — Delete set",
        "POST /almaws/v1/conf/sets/{set_id} — Manage set members (add/remove with op param)",
    ],
    methods=[
        "def create_set(self, set_data: Dict[str, Any]) -> AlmaResponse",
        "def update_set(self, set_id: str, set_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_set(self, set_id: str) -> AlmaResponse",
        "def add_members_to_set(self, set_id: str, member_ids: List[str]) -> AlmaResponse",
        "def remove_members_from_set(self, set_id: str, member_ids: List[str]) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/admin.py (extend the existing Admin class)",
        "tests/unit/domains/test_admin.py (add unit tests)",
        "tests/integration/test_admin_sets.py (add integration tests)",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
        REF_PY_EXPERT,
        REF_CLIENT,
        "Existing pattern: `Admin.list_sets` (`src/almaapitk/domains/admin.py:439`)",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "Member-management endpoint uses the correct `op` query parameter (`add_members` / `delete_members`).",
        "Round-trip test (create → update → add members → remove members → delete) against SANDBOX.",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- `manage set members` uses POST `/conf/sets/{set_id}` with a query parameter `op` and a body containing the member IDs. Format details: see `alma-api-expert` skill.
- Sets have a content type (`BIB_MMS`, `USER`, `IEP`, etc.). Validate input matches.
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: organization units (libraries, departments, circ desks)",
    domain="Configuration",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/conf/libraries",
        "GET /almaws/v1/conf/libraries/{libraryCode}",
        "GET /almaws/v1/conf/departments",
        "GET /almaws/v1/conf/libraries/{libraryCode}/circ-desks",
        "GET /almaws/v1/conf/libraries/{libraryCode}/circ-desks/{circDeskCode}",
    ],
    methods=[
        "def list_libraries(self) -> List[Dict[str, Any]]",
        "def get_library(self, library_code: str) -> Dict[str, Any]",
        "def list_departments(self) -> List[Dict[str, Any]]",
        "def list_circ_desks(self, library_code: str) -> List[Dict[str, Any]]",
        "def get_circ_desk(self, library_code: str, circ_desk_code: str) -> Dict[str, Any]",
    ],
    files=[
        "src/almaapitk/domains/configuration.py (add to bootstrapped class from #1)",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
        REF_CLIENT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- All five endpoints are read-only — no mutating operations exist for these org units in the API.
- These lookups are commonly used as supporting data for higher-level workflows; cache responses in calling code if needed.
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: locations CRUD",
    domain="Configuration",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/conf/libraries/{libraryCode}/locations",
        "POST /almaws/v1/conf/libraries/{libraryCode}/locations",
        "GET /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}",
        "PUT /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}",
        "DELETE /almaws/v1/conf/libraries/{libraryCode}/locations/{locationCode}",
    ],
    methods=[
        "def list_locations(self, library_code: str) -> List[Dict[str, Any]]",
        "def create_location(self, library_code: str, location_data: Dict[str, Any]) -> AlmaResponse",
        "def get_location(self, library_code: str, location_code: str) -> Dict[str, Any]",
        "def update_location(self, library_code: str, location_code: str, location_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_location(self, library_code: str, location_code: str) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "Location creation validates required fields (code, name, type) before sending to API.",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Location codes are scoped to library — same code can exist in two libraries.
- `delete_location` may fail if items reference the location; surface the Alma error code clearly.
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: code tables (list, get, update)",
    domain="Configuration",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/conf/code-tables",
        "GET /almaws/v1/conf/code-tables/{codeTableName}",
        "PUT /almaws/v1/conf/code-tables/{codeTableName}",
    ],
    methods=[
        "def list_code_tables(self, scope: str = None) -> List[Dict[str, Any]]",
        "def get_code_table(self, code_table_name: str) -> Dict[str, Any]",
        "def update_code_table(self, code_table_name: str, code_table_data: Dict[str, Any]) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Code tables are institution-wide config; updates are usually rare and require admin permissions in Alma.
- The PUT replaces the entire table — pull, mutate, push.
- Add a helper `update_code_table_row(table, code, description)` later if user demand justifies it (out of scope for this issue).
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: mapping tables (list, get, update)",
    domain="Configuration",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/conf/mapping-tables",
        "GET /almaws/v1/conf/mapping-tables/{mappingTableName}",
        "PUT /almaws/v1/conf/mapping-tables/{mappingTableName}",
    ],
    methods=[
        "def list_mapping_tables(self) -> List[Dict[str, Any]]",
        "def get_mapping_table(self, mapping_table_name: str) -> Dict[str, Any]",
        "def update_mapping_table(self, mapping_table_name: str, mapping_table_data: Dict[str, Any]) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Identical shape to code tables (#5) — copy that implementation pattern.
- Mapping tables can grow large; ensure the PUT roundtrip handles them.
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: jobs (list, run, instances, events, matches)",
    domain="Configuration",
    priority="high",
    effort="L",
    endpoints=[
        "GET /almaws/v1/conf/jobs",
        "GET /almaws/v1/conf/jobs/{job_id}",
        "POST /almaws/v1/conf/jobs/{job_id}",
        "GET /almaws/v1/conf/jobs/{job_id}/instances",
        "GET /almaws/v1/conf/jobs/{job_id}/instances/{instance_id}",
        "GET /almaws/v1/conf/jobs/{job_id}/instances/{instance_id}/download",
        "GET /almaws/v1/conf/jobs/{job_id}/instances/{instance_id}/events",
        "GET /almaws/v1/conf/jobs/{job_id}/instances/{instance_id}/matches",
    ],
    methods=[
        "def list_jobs(self, type_filter: str = None) -> List[Dict[str, Any]]",
        "def get_job(self, job_id: str) -> Dict[str, Any]",
        "def run_job(self, job_id: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]",
        "def list_job_instances(self, job_id: str) -> List[Dict[str, Any]]",
        "def get_job_instance(self, job_id: str, instance_id: str) -> Dict[str, Any]",
        "def download_job_input(self, job_id: str, instance_id: str) -> bytes",
        "def get_job_instance_events(self, job_id: str, instance_id: str) -> List[Dict[str, Any]]",
        "def get_job_instance_matches(self, job_id: str, instance_id: str) -> List[Dict[str, Any]]",
        "def wait_for_job_completion(self, job_id: str, instance_id: str, poll_interval_seconds: int = 30, timeout_seconds: int = 3600) -> Dict[str, Any]",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "`run_job` returns the instance_id of the submitted job.",
        "`wait_for_job_completion` polls until the instance reaches a terminal status (COMPLETED_SUCCESS / COMPLETED_FAILED / FAILED).",
        "`download_job_input` returns the raw bytes of the uploaded import file (not parsed).",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Jobs are one of the most useful Configuration endpoints — they let scripts trigger Alma's batch operations (publishing, set-based jobs, scheduled tasks).
- The job-run POST takes a body with parameters; consult `alma-api-expert` skill for the exact shape per job type.
- `wait_for_job_completion` is a convenience helper; implement it with backoff and a clear timeout error.
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: integration profiles CRUD",
    domain="Configuration",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/conf/integration-profiles",
        "POST /almaws/v1/conf/integration-profiles",
        "GET /almaws/v1/conf/integration-profiles/{id}",
        "PUT /almaws/v1/conf/integration-profiles/{id}",
    ],
    methods=[
        "def list_integration_profiles(self, profile_type: str = None) -> List[Dict[str, Any]]",
        "def create_integration_profile(self, profile_data: Dict[str, Any]) -> AlmaResponse",
        "def get_integration_profile(self, profile_id: str) -> Dict[str, Any]",
        "def update_integration_profile(self, profile_id: str, profile_data: Dict[str, Any]) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- No DELETE endpoint exists for integration profiles — that's intentional, not a gap.
- The POST endpoint is dual-purpose ("Create or retrieve profile") — confirm via `alma-api-expert` whether a query parameter switches the mode.
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: deposit profiles + import profiles (read-only)",
    domain="Configuration",
    priority="high",
    effort="S",
    endpoints=[
        "GET /almaws/v1/conf/deposit-profiles",
        "GET /almaws/v1/conf/deposit-profiles/{deposit_profile_id}",
        "GET /almaws/v1/conf/md-import-profiles",
        "GET /almaws/v1/conf/md-import-profiles/{profile_id}",
    ],
    methods=[
        "def list_deposit_profiles(self) -> List[Dict[str, Any]]",
        "def get_deposit_profile(self, deposit_profile_id: str) -> Dict[str, Any]",
        "def list_import_profiles(self) -> List[Dict[str, Any]]",
        "def get_import_profile(self, profile_id: str) -> Dict[str, Any]",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- POST /md-import-profiles/{profile_id} is deprecated per Alma docs — do not implement.
- These are simple read-only lookups, mostly used to discover IDs for use elsewhere.
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: license terms CRUD",
    domain="Configuration",
    priority="high",
    effort="M",
    endpoints=[
        "POST /almaws/v1/conf/license-terms",
        "GET /almaws/v1/conf/license-terms/{license_term_code}",
        "PUT /almaws/v1/conf/license-terms/{license_term_code}",
        "DELETE /almaws/v1/conf/license-terms/{license_term_code}",
    ],
    methods=[
        "def create_license_term(self, license_term_data: Dict[str, Any]) -> AlmaResponse",
        "def get_license_term(self, license_term_code: str) -> Dict[str, Any]",
        "def update_license_term(self, license_term_code: str, license_term_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_license_term(self, license_term_code: str) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- The Alma API does NOT expose GET /license-terms (no list operation) — code accordingly. To enumerate, callers must use Analytics or know the codes.
- License terms are used in conjunction with the Acquisitions licenses API (issue #42).
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: open hours + relations",
    domain="Configuration",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/conf/open-hours",
        "PUT /almaws/v1/conf/open-hours",
        "DELETE /almaws/v1/conf/open-hours",
        "GET /almaws/v1/conf/libraries/{libraryCode}/open-hours",
        "GET /almaws/v1/conf/relations",
        "PUT /almaws/v1/conf/relations",
        "DELETE /almaws/v1/conf/relations",
    ],
    methods=[
        "def get_open_hours(self) -> Dict[str, Any]",
        "def update_open_hours(self, open_hours_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_open_hours(self) -> AlmaResponse",
        "def get_library_open_hours(self, library_code: str) -> Dict[str, Any]",
        "def get_relations(self) -> Dict[str, Any]",
        "def update_relations(self, relations_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_relations(self) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- "Relations" here refers to bib record relationships (parent/child, etc.), not user relations.
- Open hours apply to the institution by default; library-scoped variant is GET only (no library-scoped PUT/DELETE in the API).
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: letters + printers (read + letter update)",
    domain="Configuration",
    priority="high",
    effort="S",
    endpoints=[
        "GET /almaws/v1/conf/letters",
        "GET /almaws/v1/conf/letters/{letterCode}",
        "PUT /almaws/v1/conf/letters/{letterCode}",
        "GET /almaws/v1/conf/printers",
        "GET /almaws/v1/conf/printers/{printer_id}",
    ],
    methods=[
        "def list_letters(self) -> List[Dict[str, Any]]",
        "def get_letter(self, letter_code: str) -> Dict[str, Any]",
        "def update_letter(self, letter_code: str, letter_data: Dict[str, Any]) -> AlmaResponse",
        "def list_printers(self) -> List[Dict[str, Any]]",
        "def get_printer(self, printer_id: str) -> Dict[str, Any]",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Letters CRUD is partial: only GET and PUT exist (no POST/DELETE). Letter codes are predefined by Alma.
- Printers are read-only.
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: reminders CRUD (config-level)",
    domain="Configuration",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/conf/reminders",
        "POST /almaws/v1/conf/reminders",
        "GET /almaws/v1/conf/reminders/{reminder_id}",
        "PUT /almaws/v1/conf/reminders/{reminder_id}",
        "DELETE /almaws/v1/conf/reminders/{reminder_id}",
    ],
    methods=[
        "def list_reminders(self, limit: int = 25, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_reminder(self, reminder_data: Dict[str, Any]) -> AlmaResponse",
        "def get_reminder(self, reminder_id: str) -> Dict[str, Any]",
        "def update_reminder(self, reminder_id: str, reminder_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_reminder(self, reminder_id: str) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- These are config-level reminders (different from bib-level reminders in issue #34).
""",
))

ISSUES.append(Issue(
    title="Coverage: Configuration: workflows runner + utilities",
    domain="Configuration",
    priority="high",
    effort="S",
    endpoints=[
        "POST /almaws/v1/conf/workflows/{workflow_id}",
        "GET /almaws/v1/conf/utilities/fee-transactions",
        "GET /almaws/v1/conf/general",
    ],
    methods=[
        "def run_workflow(self, workflow_id: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]",
        "def get_fee_transactions_report(self, **filters) -> List[Dict[str, Any]]",
        "def get_general_configuration(self) -> Dict[str, Any]",
    ],
    files=[
        "src/almaapitk/domains/configuration.py",
        "tests/unit/domains/test_configuration.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/conf/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Workflow runner is for institution-defined workflows (not Alma's built-in jobs — those are issue #7).
- Fee-transactions report supports filters (date range, library, etc.) — pass through as kwargs.
""",
))

# ===========================================================================
# USERS (high) — issues 15-24
# ===========================================================================

USER_FILES = [
    "src/almaapitk/domains/users.py (extend existing Users class)",
    "tests/unit/domains/test_users.py",
]

ISSUES.append(Issue(
    title="Coverage: Users: list & search users",
    domain="Users",
    priority="high",
    effort="S",
    endpoints=[
        "GET /almaws/v1/users",
        "GET /almaws/v1/users/{user_id}/personal-data",
    ],
    methods=[
        "def list_users(self, limit: int = 10, offset: int = 0, q: str = None, source_institution_code: str = None) -> Dict[str, Any]",
        "def search_users(self, query: str, limit: int = 10) -> List[Dict[str, Any]]",
        "def get_user_personal_data(self, user_id: str) -> Dict[str, Any]",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT + " — query syntax is Alma's specialized format (e.g., `last_name~Smith`)",
        "Existing pattern: `BibliographicRecords.search_records` (`src/almaapitk/domains/bibs.py:75`)",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- `list_users` returns a paged response with `total_record_count` and `user` array.
- `personal-data` endpoint is the GDPR data-portability export — used carefully.
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: create / delete user (CRUD completeness)",
    domain="Users",
    priority="high",
    effort="M",
    endpoints=[
        "POST /almaws/v1/users",
        "DELETE /almaws/v1/users/{user_id}",
    ],
    methods=[
        "def create_user(self, user_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_user(self, user_id: str) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT + " — required user fields, identifier formats",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "`create_user` validates required fields (primary_id, account_type, status, user_group) before sending.",
        "`delete_user` returns the deleted user payload for audit logging.",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Required fields for user creation are non-trivial; consult `alma-api-expert` for the validation rules.
- `delete_user` may fail for users with active loans/fees; raise the API error clearly.
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: authentication operations (POST /users/{id})",
    domain="Users",
    priority="high",
    effort="S",
    endpoints=[
        "POST /almaws/v1/users/{user_id} — Authenticate or refresh user",
    ],
    methods=[
        "def authenticate_user(self, user_id: str, password: str) -> AlmaResponse",
        "def refresh_user_from_external(self, user_id: str) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT + " — `op` query parameter values (`auth`, `refresh`)",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "Method dispatches on the `op` query parameter to the correct operation.",
        "Password is NEVER logged (logger redaction must catch it).",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- This single endpoint covers two distinct operations (authenticate / refresh-from-external-system) via the `op` query param.
- Authenticate sends the password in the body — the existing logger redaction in `alma_logging` MUST cover it. Verify by inspecting log output during testing.
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: user attachments",
    domain="Users",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/users/{user_id}/attachments",
        "POST /almaws/v1/users/{user_id}/attachments",
        "GET /almaws/v1/users/{user_id}/attachments/{attachment_id}",
    ],
    methods=[
        "def list_user_attachments(self, user_id: str) -> List[Dict[str, Any]]",
        "def get_user_attachment(self, user_id: str, attachment_id: str) -> bytes",
        "def upload_user_attachment(self, user_id: str, file_path: str, attachment_type: str = None) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "`get_user_attachment` returns raw bytes (binary content).",
        "`upload_user_attachment` accepts a local file path and handles multipart form encoding.",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- POST endpoint is multipart — see how `BibliographicRecords.create_representation` / `link_file_to_representation` handle binary uploads (`src/almaapitk/domains/bibs.py:569-690`) for the pattern.
- No DELETE endpoint for attachments per the API.
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: loans (list, create, get, renew, change due date)",
    domain="Users",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/users/{user_id}/loans",
        "POST /almaws/v1/users/{user_id}/loans",
        "GET /almaws/v1/users/{user_id}/loans/{loan_id}",
        "POST /almaws/v1/users/{user_id}/loans/{loan_id}",
        "PUT /almaws/v1/users/{user_id}/loans/{loan_id}",
    ],
    methods=[
        "def list_user_loans(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_user_loan(self, user_id: str, item_barcode: str, library: str, circ_desk: str) -> AlmaResponse",
        "def get_user_loan(self, user_id: str, loan_id: str) -> Dict[str, Any]",
        "def renew_user_loan(self, user_id: str, loan_id: str) -> AlmaResponse",
        "def change_loan_due_date(self, user_id: str, loan_id: str, new_due_date: str) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT + " — `op=renew` query param for renewals",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- POST /loans/{loan_id} uses the `op` query parameter — `op=renew` triggers a renewal.
- PUT /loans/{loan_id} updates the due date directly.
- Date format is ISO 8601 with Z (e.g., `2026-12-31Z`); reuse `Acquisitions._format_invoice_date` pattern.
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: requests (list, create, get, cancel, action, update)",
    domain="Users",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/users/{user_id}/requests",
        "POST /almaws/v1/users/{user_id}/requests",
        "GET /almaws/v1/users/{user_id}/requests/{request_id}",
        "POST /almaws/v1/users/{user_id}/requests/{request_id}",
        "PUT /almaws/v1/users/{user_id}/requests/{request_id}",
        "DELETE /almaws/v1/users/{user_id}/requests/{request_id}",
    ],
    methods=[
        "def list_user_requests(self, user_id: str, limit: int = 100, offset: int = 0, status: str = None) -> List[Dict[str, Any]]",
        "def create_user_request(self, user_id: str, request_data: Dict[str, Any]) -> AlmaResponse",
        "def get_user_request(self, user_id: str, request_id: str) -> Dict[str, Any]",
        "def cancel_user_request(self, user_id: str, request_id: str, reason: str = None) -> AlmaResponse",
        "def update_user_request(self, user_id: str, request_id: str, request_data: Dict[str, Any]) -> AlmaResponse",
        "def perform_user_request_action(self, user_id: str, request_id: str, op: str) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- POST /requests/{id} dispatches via `op` query parameter to actions like `move`, `prioritize`, etc.
- Pair this work with the bib-level/item-level requests issues (#28, #29) for shared validation helpers.
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: resource sharing requests (user-side)",
    domain="Users",
    priority="high",
    effort="M",
    endpoints=[
        "POST /almaws/v1/users/{user_id}/resource-sharing-requests",
        "GET /almaws/v1/users/{user_id}/resource-sharing-requests/{request_id}",
        "DELETE /almaws/v1/users/{user_id}/resource-sharing-requests/{request_id}",
        "POST /almaws/v1/users/{user_id}/resource-sharing-requests/{request_id}",
    ],
    methods=[
        "def create_user_rs_request(self, user_id: str, request_data: Dict[str, Any]) -> AlmaResponse",
        "def get_user_rs_request(self, user_id: str, request_id: str) -> Dict[str, Any]",
        "def cancel_user_rs_request(self, user_id: str, request_id: str) -> AlmaResponse",
        "def perform_user_rs_request_action(self, user_id: str, request_id: str, op: str) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT,
        "Existing pattern: `ResourceSharing.create_lending_request` (`src/almaapitk/domains/resource_sharing.py:165`) — partner-side equivalent",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- USER-SIDE resource sharing requests are distinct from PARTNER-SIDE (which lives in `ResourceSharing` domain). Different endpoints, different objects, different workflows.
- These methods belong on `Users` (the user-side requests are owned by a borrower's record).
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: purchase requests",
    domain="Users",
    priority="high",
    effort="S",
    endpoints=[
        "GET /almaws/v1/users/{user_id}/purchase-requests",
        "POST /almaws/v1/users/{user_id}/purchase-requests",
        "GET /almaws/v1/users/{user_id}/purchase-requests/{purchase_request_id}",
        "POST /almaws/v1/users/{user_id}/purchase-requests/{purchase_request_id}",
    ],
    methods=[
        "def list_user_purchase_requests(self, user_id: str, status: str = None) -> List[Dict[str, Any]]",
        "def create_user_purchase_request(self, user_id: str, purchase_request_data: Dict[str, Any]) -> AlmaResponse",
        "def get_user_purchase_request(self, user_id: str, purchase_request_id: str) -> Dict[str, Any]",
        "def perform_user_purchase_request_action(self, user_id: str, purchase_request_id: str, op: str) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- These are USER-side purchase requests (a patron asking the library to buy something), distinct from acq-side purchase requests (issue #44).
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: fines & fees",
    domain="Users",
    priority="high",
    effort="M",
    endpoints=[
        "GET /almaws/v1/users/{user_id}/fees",
        "POST /almaws/v1/users/{user_id}/fees",
        "GET /almaws/v1/users/{user_id}/fees/{fee_id}",
        "POST /almaws/v1/users/{user_id}/fees/all",
        "POST /almaws/v1/users/{user_id}/fees/{fee_id}",
    ],
    methods=[
        "def list_user_fees(self, user_id: str, status: str = None) -> List[Dict[str, Any]]",
        "def create_user_fee(self, user_id: str, fee_data: Dict[str, Any]) -> AlmaResponse",
        "def get_user_fee(self, user_id: str, fee_id: str) -> Dict[str, Any]",
        "def pay_all_user_fees(self, user_id: str, amount: float = None, method: str = 'CASH') -> AlmaResponse",
        "def pay_user_fee(self, user_id: str, fee_id: str, amount: float = None, method: str = 'CASH') -> AlmaResponse",
        "def waive_user_fee(self, user_id: str, fee_id: str, reason: str) -> AlmaResponse",
        "def dispute_user_fee(self, user_id: str, fee_id: str, reason: str) -> AlmaResponse",
        "def restore_user_fee(self, user_id: str, fee_id: str) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
        REF_API_EXPERT + " — `op` values: `pay`, `waive`, `dispute`, `restore`",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "Each fee-action method dispatches via the correct `op` query parameter and handles partial-amount payments.",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- POST /fees/{fee_id} dispatches on `op` — single endpoint, multiple operations.
- `pay_all_user_fees` posts to `/fees/all` (a special endpoint, not a fee_id of "all").
- Always include `method` (CASH / CREDIT_CARD / ONLINE / etc.) for payment ops.
""",
))

ISSUES.append(Issue(
    title="Coverage: Users: deposits",
    domain="Users",
    priority="high",
    effort="S",
    endpoints=[
        "GET /almaws/v1/users/{user_id}/deposits",
        "POST /almaws/v1/users/{user_id}/deposits",
        "GET /almaws/v1/users/{user_id}/deposits/{deposit_id}",
        "POST /almaws/v1/users/{user_id}/deposits/{deposit_id}",
    ],
    methods=[
        "def list_user_deposits(self, user_id: str) -> List[Dict[str, Any]]",
        "def create_user_deposit(self, user_id: str, deposit_data: Dict[str, Any]) -> AlmaResponse",
        "def get_user_deposit(self, user_id: str, deposit_id: str) -> Dict[str, Any]",
        "def perform_user_deposit_action(self, user_id: str, deposit_id: str, op: str) -> AlmaResponse",
    ],
    files=USER_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/users/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Deposits are typically used for ILL fees, key deposits, etc. Refer to `alma-api-expert` for action `op` values.
""",
))

# ===========================================================================
# BIBS (medium) — issues 25-36
# ===========================================================================

BIBS_FILES = [
    "src/almaapitk/domains/bibs.py (extend existing BibliographicRecords class)",
    "tests/unit/domains/test_bibs.py",
]

ISSUES.append(Issue(
    title="Coverage: Bibs: complete holdings CRUD (update / delete)",
    domain="Bibs",
    priority="medium",
    effort="S",
    endpoints=[
        "PUT /almaws/v1/bibs/{mms_id}/holdings/{holding_id}",
        "DELETE /almaws/v1/bibs/{mms_id}/holdings/{holding_id}",
    ],
    methods=[
        "def update_holding(self, mms_id: str, holding_id: str, holding_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_holding(self, mms_id: str, holding_id: str, override_attached_items: bool = False) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
        "Existing pattern: `BibliographicRecords.update_record` (`src/almaapitk/domains/bibs.py:144`)",
        "Existing pattern: `BibliographicRecords.delete_record` (`src/almaapitk/domains/bibs.py:187`)",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Mirror the record CRUD style for delete (the `override_attached_items` flag toggles cascade behavior).
- Holdings update body is MARC-XML; reuse helpers from existing MARC code.
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: complete items CRUD (update / withdraw)",
    domain="Bibs",
    priority="medium",
    effort="S",
    endpoints=[
        "PUT /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}",
        "DELETE /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}",
    ],
    methods=[
        "def update_item(self, mms_id: str, holding_id: str, item_pid: str, item_data: Dict[str, Any]) -> AlmaResponse",
        "def withdraw_item(self, mms_id: str, holding_id: str, item_pid: str, holdings: str = 'retain', bibs: str = 'retain') -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
        "Existing pattern: `BibliographicRecords.create_item` (`src/almaapitk/domains/bibs.py:423`)",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- `withdraw_item` is the DELETE endpoint; the `holdings` and `bibs` params control cascade behavior (retain vs. delete the parent holding/bib if last item is withdrawn).
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: bib-attached portfolios CRUD",
    domain="Bibs",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/bibs/{mms_id}/portfolios",
        "POST /almaws/v1/bibs/{mms_id}/portfolios/",
        "GET /almaws/v1/bibs/{mms_id}/portfolios/{portfolio_id}",
        "PUT /almaws/v1/bibs/{mms_id}/portfolios/{portfolio_id}",
        "DELETE /almaws/v1/bibs/{mms_id}/portfolios/{portfolio_id}",
    ],
    methods=[
        "def list_bib_portfolios(self, mms_id: str) -> List[Dict[str, Any]]",
        "def create_bib_portfolio(self, mms_id: str, portfolio_data: Dict[str, Any]) -> AlmaResponse",
        "def get_bib_portfolio(self, mms_id: str, portfolio_id: str) -> Dict[str, Any]",
        "def update_bib_portfolio(self, mms_id: str, portfolio_id: str, portfolio_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_bib_portfolio(self, mms_id: str, portfolio_id: str) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- BIB-attached portfolios are accessed via `/bibs/{mms_id}/portfolios`. Issue #48 covers the SAME object via the Electronic domain path `/electronic/.../portfolios/{portfolio_id}`. Both paths exist in the Alma API; expose both.
- Once both paths exist, document in CLAUDE.md when to prefer which.
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: bib-level requests",
    domain="Bibs",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/bibs/{mms_id}/requests",
        "POST /almaws/v1/bibs/{mms_id}/requests",
        "GET /almaws/v1/bibs/{mms_id}/requests/{request_id}",
        "POST /almaws/v1/bibs/{mms_id}/requests/{request_id}",
        "PUT /almaws/v1/bibs/{mms_id}/requests/{request_id}",
        "DELETE /almaws/v1/bibs/{mms_id}/requests/{request_id}",
    ],
    methods=[
        "def list_bib_requests(self, mms_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_bib_request(self, mms_id: str, request_data: Dict[str, Any]) -> AlmaResponse",
        "def get_bib_request(self, mms_id: str, request_id: str) -> Dict[str, Any]",
        "def perform_bib_request_action(self, mms_id: str, request_id: str, op: str) -> AlmaResponse",
        "def update_bib_request(self, mms_id: str, request_id: str, request_data: Dict[str, Any]) -> AlmaResponse",
        "def cancel_bib_request(self, mms_id: str, request_id: str, reason: str = None) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Bib-level requests are title-level holds (any copy fulfills); item-level requests (issue #29) are pin-pointed to one item.
- POST /requests/{id} uses `op` query parameter for actions.
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: item-level requests",
    domain="Bibs",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_id}/requests",
        "GET /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_id}/requests/{request_id}",
        "POST /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/requests",
        "POST /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/requests/{request_id}",
        "PUT /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/requests/{request_id}",
        "DELETE /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/requests/{request_id}",
    ],
    methods=[
        "def list_item_requests(self, mms_id: str, holding_id: str, item_pid: str) -> List[Dict[str, Any]]",
        "def get_item_request(self, mms_id: str, holding_id: str, item_pid: str, request_id: str) -> Dict[str, Any]",
        "def create_item_request(self, mms_id: str, holding_id: str, item_pid: str, request_data: Dict[str, Any]) -> AlmaResponse",
        "def perform_item_request_action(self, mms_id: str, holding_id: str, item_pid: str, request_id: str, op: str) -> AlmaResponse",
        "def update_item_request(self, mms_id: str, holding_id: str, item_pid: str, request_id: str, request_data: Dict[str, Any]) -> AlmaResponse",
        "def cancel_item_request(self, mms_id: str, holding_id: str, item_pid: str, request_id: str, reason: str = None) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Long path with three IDs — wrap in a helper to build the endpoint URL to keep methods readable.
- Pair with issue #28 for shared validation logic.
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: loans (bib + item level)",
    domain="Bibs",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/bibs/{mms_id}/loans",
        "GET /almaws/v1/bibs/{mms_id}/loans/{loan_id}",
        "GET /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_id}/loans",
        "POST /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/loans",
        "GET /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/loans/{loan_id}",
        "POST /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/loans/{loan_id}",
        "PUT /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/loans/{loan_id}",
    ],
    methods=[
        "def list_bib_loans(self, mms_id: str) -> List[Dict[str, Any]]",
        "def get_bib_loan(self, mms_id: str, loan_id: str) -> Dict[str, Any]",
        "def list_item_loans(self, mms_id: str, holding_id: str, item_pid: str) -> List[Dict[str, Any]]",
        "def create_item_loan(self, mms_id: str, holding_id: str, item_pid: str, user_id: str, library: str, circ_desk: str) -> AlmaResponse",
        "def get_item_loan(self, mms_id: str, holding_id: str, item_pid: str, loan_id: str) -> Dict[str, Any]",
        "def perform_item_loan_action(self, mms_id: str, holding_id: str, item_pid: str, loan_id: str, op: str) -> AlmaResponse",
        "def change_item_loan_due_date(self, mms_id: str, holding_id: str, item_pid: str, loan_id: str, new_due_date: str) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- These bib-side loan methods complement the user-side methods in issue #19. Different endpoints; same loans accessible via either path.
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: booking availability + request options",
    domain="Bibs",
    priority="medium",
    effort="S",
    endpoints=[
        "GET /almaws/v1/bibs/{mms_id}/booking-availability",
        "GET /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/booking-availability",
        "GET /almaws/v1/bibs/{mms_id}/request-options",
        "GET /almaws/v1/bibs/{mms_id}/holdings/{holding_id}/items/{item_pid}/request-options",
    ],
    methods=[
        "def get_bib_booking_availability(self, mms_id: str, period: str = None) -> Dict[str, Any]",
        "def get_item_booking_availability(self, mms_id: str, holding_id: str, item_pid: str, period: str = None) -> Dict[str, Any]",
        "def get_bib_request_options(self, mms_id: str, user_id: str = None) -> List[Dict[str, Any]]",
        "def get_item_request_options(self, mms_id: str, holding_id: str, item_pid: str, user_id: str = None) -> List[Dict[str, Any]]",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Read-only utility endpoints. Useful for UI flows showing what a user can request right now.
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: collections CRUD (the collection itself)",
    domain="Bibs",
    priority="medium",
    effort="M",
    extends_existing={
        "existing": [
            "`BibliographicRecords.get_collection_members` — `src/almaapitk/domains/bibs.py:692`",
            "`BibliographicRecords.add_to_collection` — :723",
            "`BibliographicRecords.remove_from_collection` — :754",
        ],
        "note": "Those methods operate on collection MEMBERS. This issue adds methods for the COLLECTION OBJECT itself (create the collection, list collections, etc.).",
    },
    endpoints=[
        "GET /almaws/v1/bibs/collections",
        "POST /almaws/v1/bibs/collections",
        "GET /almaws/v1/bibs/collections/{pid}",
        "PUT /almaws/v1/bibs/collections/{pid}",
        "DELETE /almaws/v1/bibs/collections/{pid}",
    ],
    methods=[
        "def list_collections(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_collection(self, collection_data: Dict[str, Any]) -> AlmaResponse",
        "def get_collection(self, collection_pid: str) -> Dict[str, Any]",
        "def update_collection(self, collection_pid: str, collection_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_collection(self, collection_pid: str) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "`delete_collection` only removes a collection that has no bibs in it (per Alma docs).",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- The Alma docs explicitly mark DELETE as "Remove a collection with no Bibs" — surface the API error if non-empty.
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: bib-level e-collections (read)",
    domain="Bibs",
    priority="medium",
    effort="S",
    endpoints=[
        "GET /almaws/v1/bibs/{mms_id}/e-collections",
        "GET /almaws/v1/bibs/{mms_id}/e-collections/{collection_id}",
    ],
    methods=[
        "def list_bib_ecollections(self, mms_id: str) -> List[Dict[str, Any]]",
        "def get_bib_ecollection(self, mms_id: str, collection_id: str) -> Dict[str, Any]",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Read-only access to electronic collections attached to a bib. Full CRUD of e-collections lives in the Electronic domain (issue #46).
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: bib reminders CRUD",
    domain="Bibs",
    priority="medium",
    effort="S",
    endpoints=[
        "GET /almaws/v1/bibs/{mms_id}/reminders",
        "POST /almaws/v1/bibs/{mms_id}/reminders",
        "GET /almaws/v1/bibs/{mms_id}/reminders/{reminder_id}",
        "PUT /almaws/v1/bibs/{mms_id}/reminders/{reminder_id}",
        "DELETE /almaws/v1/bibs/{mms_id}/reminders/{reminder_id}",
    ],
    methods=[
        "def list_bib_reminders(self, mms_id: str) -> List[Dict[str, Any]]",
        "def create_bib_reminder(self, mms_id: str, reminder_data: Dict[str, Any]) -> AlmaResponse",
        "def get_bib_reminder(self, mms_id: str, reminder_id: str) -> Dict[str, Any]",
        "def update_bib_reminder(self, mms_id: str, reminder_id: str, reminder_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_bib_reminder(self, mms_id: str, reminder_id: str) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Bib-level reminders are distinct from config-level reminders (issue #13).
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: authorities CRUD",
    domain="Bibs",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/bibs/authorities",
        "POST /almaws/v1/bibs/authorities",
        "GET /almaws/v1/bibs/authorities/{authority_record_id}",
        "PUT /almaws/v1/bibs/authorities/{authority_record_id}",
        "DELETE /almaws/v1/bibs/authorities/{authority_record_id}",
    ],
    methods=[
        "def list_authorities(self, q: str = None, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_authority(self, marc_xml: str, validate: bool = True) -> AlmaResponse",
        "def get_authority(self, authority_record_id: str) -> Dict[str, Any]",
        "def update_authority(self, authority_record_id: str, marc_xml: str, validate: bool = True) -> AlmaResponse",
        "def delete_authority(self, authority_record_id: str) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
        "Existing pattern: `BibliographicRecords.create_record` (`src/almaapitk/domains/bibs.py:110`)",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Authority records are MARC-XML format (similar to bib records). Reuse the MARC validation patterns.
""",
))

ISSUES.append(Issue(
    title="Coverage: Bibs: bib record operations (POST /bibs/{mms_id})",
    domain="Bibs",
    priority="medium",
    effort="S",
    endpoints=[
        "POST /almaws/v1/bibs/{mms_id} — Operate on record (suppress, unsuppress, etc.)",
    ],
    methods=[
        "def perform_bib_operation(self, mms_id: str, op: str, **params) -> AlmaResponse",
        "def suppress_bib(self, mms_id: str) -> AlmaResponse",
        "def unsuppress_bib(self, mms_id: str) -> AlmaResponse",
    ],
    files=BIBS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/bibs/",
        REF_API_EXPERT + " — `op` values for bib operations",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Single endpoint with `op` dispatch. Common ops: `suppress`, `unsuppress`, `link`, `unlink`. Provide thin wrappers for the common ones plus the generic `perform_bib_operation` for niche ops.
""",
))

# ===========================================================================
# ACQUISITIONS (medium) — issues 37-44
# ===========================================================================

ACQ_FILES = [
    "src/almaapitk/domains/acquisition.py (extend existing Acquisitions class)",
    "tests/unit/domains/test_acquisition.py",
]

ISSUES.append(Issue(
    title="Coverage: Acquisitions: vendors CRUD + nested invoices/POLs",
    domain="Acquisitions",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/acq/vendors",
        "POST /almaws/v1/acq/vendors",
        "GET /almaws/v1/acq/vendors/{vendorCode}",
        "PUT /almaws/v1/acq/vendors/{vendorCode}",
        "DELETE /almaws/v1/acq/vendors/{vendorCode}",
        "GET /almaws/v1/acq/vendors/{vendorCode}/invoices",
        "GET /almaws/v1/acq/vendors/{vendorCode}/po-lines",
    ],
    methods=[
        "def list_vendors(self, q: str = None, limit: int = 10, offset: int = 0, status: str = None) -> List[Dict[str, Any]]",
        "def create_vendor(self, vendor_data: Dict[str, Any]) -> AlmaResponse",
        "def get_vendor(self, vendor_code: str) -> Dict[str, Any]",
        "def update_vendor(self, vendor_code: str, vendor_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_vendor(self, vendor_code: str) -> AlmaResponse",
        "def list_vendor_invoices(self, vendor_code: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def list_vendor_pol(self, vendor_code: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
    ],
    files=ACQ_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/acq/",
        REF_API_EXPERT + " — vendor required fields, account/contact substructures",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Vendor objects have nested accounts/contacts/financial lists; the existing `Acquisitions.get_vendor_from_pol` is unrelated (it's a data extractor, not an API call).
""",
))

ISSUES.append(Issue(
    title="Coverage: Acquisitions: funds CRUD + fund service",
    domain="Acquisitions",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/acq/funds",
        "POST /almaws/v1/acq/funds",
        "GET /almaws/v1/acq/funds/{fund_id}",
        "POST /almaws/v1/acq/funds/{fund_id} — Fund Service (transfer, allocate, etc.)",
        "PUT /almaws/v1/acq/funds/{fund_id}",
        "DELETE /almaws/v1/acq/funds/{fund_id}",
    ],
    methods=[
        "def list_funds(self, q: str = None, limit: int = 10, offset: int = 0, status: str = 'ACTIVE') -> List[Dict[str, Any]]",
        "def create_fund(self, fund_data: Dict[str, Any]) -> AlmaResponse",
        "def get_fund(self, fund_id: str) -> Dict[str, Any]",
        "def update_fund(self, fund_id: str, fund_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_fund(self, fund_id: str) -> AlmaResponse",
        "def perform_fund_service(self, fund_id: str, op: str, **params) -> AlmaResponse",
    ],
    files=ACQ_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/acq/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Fund service `op` values include `transfer`, `allocation`, etc. — consult `alma-api-expert` for the full list.
- Note: existing `Acquisitions.get_fund_from_pol` is a data extractor, not a fund API method; do not confuse.
""",
))

ISSUES.append(Issue(
    title="Coverage: Acquisitions: fund transactions",
    domain="Acquisitions",
    priority="medium",
    effort="S",
    endpoints=[
        "GET /almaws/v1/acq/funds/{fund_id}/transactions",
        "POST /almaws/v1/acq/funds/{fund_id}/transactions",
    ],
    methods=[
        "def list_fund_transactions(self, fund_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_fund_transaction(self, fund_id: str, transaction_data: Dict[str, Any]) -> AlmaResponse",
    ],
    files=ACQ_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/acq/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD,
))

ISSUES.append(Issue(
    title="Coverage: Acquisitions: PO Lines list + create + cancel",
    domain="Acquisitions",
    priority="medium",
    effort="M",
    extends_existing={
        "existing": [
            "`Acquisitions.get_pol` — `src/almaapitk/domains/acquisition.py:1534`",
            "`Acquisitions.update_pol` — :1866",
            "`Acquisitions.get_pol_items` — :1633",
            "`Acquisitions.receive_item` — :1677",
            "`Acquisitions.receive_and_keep_in_department` — :1767",
        ],
        "note": "POL READ + UPDATE + RECEIVE are already implemented. This issue adds LIST/SEARCH, CREATE, and CANCEL only.",
    },
    endpoints=[
        "GET /almaws/v1/acq/po-lines",
        "POST /almaws/v1/acq/po-lines",
        "DELETE /almaws/v1/acq/po-lines/{po_line_id} — Cancel POL",
    ],
    methods=[
        "def list_pol(self, q: str = None, status: str = None, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]",
        "def search_pol(self, query: str, limit: int = 10) -> List[Dict[str, Any]]",
        "def create_pol(self, pol_data: Dict[str, Any]) -> AlmaResponse",
        "def cancel_pol(self, pol_id: str, reason_code: str, comment: str = None) -> AlmaResponse",
    ],
    files=ACQ_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/acq/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- `cancel_pol` (DELETE) requires a cancellation reason code per Alma's API; surface the constraint in validation.
""",
))

ISSUES.append(Issue(
    title="Coverage: Acquisitions: invoice attachments CRUD",
    domain="Acquisitions",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/acq/invoices/{invoice_id}/attachments",
        "POST /almaws/v1/acq/invoices/{invoice_id}/attachments",
        "GET /almaws/v1/acq/invoices/{invoice_id}/attachments/{attachment_id}",
        "PUT /almaws/v1/acq/invoices/{invoice_id}/attachments/{attachment_id}",
        "DELETE /almaws/v1/acq/invoices/{invoice_id}/attachments/{attachment_id}",
    ],
    methods=[
        "def list_invoice_attachments(self, invoice_id: str) -> List[Dict[str, Any]]",
        "def upload_invoice_attachment(self, invoice_id: str, file_path: str, attachment_type: str = None) -> AlmaResponse",
        "def get_invoice_attachment(self, invoice_id: str, attachment_id: str) -> bytes",
        "def update_invoice_attachment(self, invoice_id: str, attachment_id: str, file_path: str) -> AlmaResponse",
        "def delete_invoice_attachment(self, invoice_id: str, attachment_id: str) -> AlmaResponse",
    ],
    files=ACQ_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/acq/",
        REF_API_EXPERT + " — multipart upload format",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Multipart upload — see issue #18 (user attachments) and the representation file pattern.
""",
))

ISSUES.append(Issue(
    title="Coverage: Acquisitions: licenses + amendments + attachments",
    domain="Acquisitions",
    priority="medium",
    effort="L",
    endpoints=[
        "GET /almaws/v1/acq/licenses/",
        "POST /almaws/v1/acq/licenses",
        "GET /almaws/v1/acq/licenses/{license_code}",
        "PUT /almaws/v1/acq/licenses/{license_code}",
        "DELETE /almaws/v1/acq/licenses/{license_code}",
        "GET /almaws/v1/acq/licenses/{license_code}/attachments",
        "POST /almaws/v1/acq/licenses/{license_code}/attachments",
        "GET /almaws/v1/acq/licenses/{license_code}/attachments/{attachment_id}",
        "PUT /almaws/v1/acq/licenses/{license_code}/attachments/{attachment_id}",
        "DELETE /almaws/v1/acq/licenses/{license_code}/attachments/{attachment_id}",
        "GET /almaws/v1/acq/licenses/{license_code}/amendments",
        "POST /almaws/v1/acq/licenses/{license_code}/amendments",
        "GET /almaws/v1/acq/licenses/{license_code}/amendments/{amendment_code}",
        "PUT /almaws/v1/acq/licenses/{license_code}/amendments/{amendment_code}",
        "DELETE /almaws/v1/acq/licenses/{license_code}/amendments/{amendment_code}",
    ],
    methods=[
        "def list_licenses(self, q: str = None, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_license(self, license_data: Dict[str, Any]) -> AlmaResponse",
        "def get_license(self, license_code: str) -> Dict[str, Any]",
        "def update_license(self, license_code: str, license_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_license(self, license_code: str) -> AlmaResponse",
        "def list_license_attachments(self, license_code: str) -> List[Dict[str, Any]]",
        "def upload_license_attachment(self, license_code: str, file_path: str) -> AlmaResponse",
        "def get_license_attachment(self, license_code: str, attachment_id: str) -> bytes",
        "def update_license_attachment(self, license_code: str, attachment_id: str, file_path: str) -> AlmaResponse",
        "def delete_license_attachment(self, license_code: str, attachment_id: str) -> AlmaResponse",
        "def list_license_amendments(self, license_code: str) -> List[Dict[str, Any]]",
        "def create_license_amendment(self, license_code: str, amendment_data: Dict[str, Any]) -> AlmaResponse",
        "def get_license_amendment(self, license_code: str, amendment_code: str) -> Dict[str, Any]",
        "def update_license_amendment(self, license_code: str, amendment_code: str, amendment_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_license_amendment(self, license_code: str, amendment_code: str) -> AlmaResponse",
    ],
    files=ACQ_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/acq/",
        REF_API_EXPERT,
        "Pairs with: Configuration license terms (issue #10)",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "Round-trip integration test: create license → add attachment → add amendment → update amendment → delete amendment → delete attachment → delete license.",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- This is the largest single Acquisitions ticket — three nested resource trees. Consider splitting if it doesn't fit one PR; otherwise commit incrementally on a feature branch.
""",
))

ISSUES.append(Issue(
    title="Coverage: Acquisitions: lookups (currencies + fiscal periods)",
    domain="Acquisitions",
    priority="medium",
    effort="S",
    endpoints=[
        "GET /almaws/v1/acq/currencies",
        "GET /almaws/v1/acq/fiscal-periods",
    ],
    methods=[
        "def list_currencies(self) -> List[Dict[str, Any]]",
        "def list_fiscal_periods(self) -> List[Dict[str, Any]]",
    ],
    files=ACQ_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/acq/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Read-only, used as supporting lookups for fund/invoice creation flows.
""",
))

ISSUES.append(Issue(
    title="Coverage: Acquisitions: purchase requests (acq-side)",
    domain="Acquisitions",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/acq/purchase-requests/",
        "GET /almaws/v1/acq/purchase-requests/{id}",
        "POST /almaws/v1/acq/purchase-requests/{id}",
        "PUT /almaws/v1/acq/purchase-requests/{id}",
        "DELETE /almaws/v1/acq/purchase-requests/{id}",
    ],
    methods=[
        "def list_purchase_requests(self, q: str = None, status: str = None, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]",
        "def get_purchase_request(self, purchase_request_id: str) -> Dict[str, Any]",
        "def perform_purchase_request_action(self, purchase_request_id: str, op: str) -> AlmaResponse",
        "def update_purchase_request(self, purchase_request_id: str, request_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_purchase_request(self, purchase_request_id: str) -> AlmaResponse",
    ],
    files=ACQ_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/acq/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- ACQ-side purchase requests; complements the user-side equivalent in issue #22.
- POST /purchase-requests/{id} dispatches via `op` (approve, reject, link to POL).
""",
))

# ===========================================================================
# ELECTRONIC (medium) — issues 45-48
# ===========================================================================

ISSUES.append(_bootstrap_issue(
    "Electronic", "Electronic", "issues 46-48",
    "electronic.py",
    "https://developers.exlibrisgroup.com/alma/apis/electronic/",
    "medium",
))

ELECTRONIC_FILES = [
    "src/almaapitk/domains/electronic.py",
    "tests/unit/domains/test_electronic.py",
]

ISSUES.append(Issue(
    title="Coverage: Electronic: e-collections CRUD",
    domain="Electronic",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/electronic/e-collections",
        "POST /almaws/v1/electronic/e-collections",
        "GET /almaws/v1/electronic/e-collections/{collection_id}",
        "PUT /almaws/v1/electronic/e-collections/{collection_id}",
        "DELETE /almaws/v1/electronic/e-collections/{collection_id}",
    ],
    methods=[
        "def list_ecollections(self, q: str = None, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_ecollection(self, ecollection_data: Dict[str, Any]) -> AlmaResponse",
        "def get_ecollection(self, collection_id: str) -> Dict[str, Any]",
        "def update_ecollection(self, collection_id: str, ecollection_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_ecollection(self, collection_id: str) -> AlmaResponse",
    ],
    files=ELECTRONIC_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/electronic/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD,
))

ISSUES.append(Issue(
    title="Coverage: Electronic: e-services CRUD",
    domain="Electronic",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/electronic/e-collections/{collection_id}/e-services",
        "POST /almaws/v1/electronic/e-collections/{collection_id}/e-services",
        "GET /almaws/v1/electronic/e-collections/{collection_id}/e-services/{service_id}",
        "PUT /almaws/v1/electronic/e-collections/{collection_id}/e-services/{service_id}",
        "DELETE /almaws/v1/electronic/e-collections/{collection_id}/e-services/{service_id}",
    ],
    methods=[
        "def list_eservices(self, collection_id: str) -> List[Dict[str, Any]]",
        "def create_eservice(self, collection_id: str, eservice_data: Dict[str, Any]) -> AlmaResponse",
        "def get_eservice(self, collection_id: str, service_id: str) -> Dict[str, Any]",
        "def update_eservice(self, collection_id: str, service_id: str, eservice_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_eservice(self, collection_id: str, service_id: str) -> AlmaResponse",
    ],
    files=ELECTRONIC_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/electronic/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD,
))

ISSUES.append(Issue(
    title="Coverage: Electronic: electronic portfolios CRUD",
    domain="Electronic",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/electronic/e-collections/{collection_id}/e-services/{service_id}/portfolios",
        "POST /almaws/v1/electronic/e-collections/{collection_id}/e-services/{service_id}/portfolios/",
        "GET /almaws/v1/electronic/e-collections/{collection_id}/e-services/{service_id}/portfolios/{portfolio_id}",
        "PUT /almaws/v1/electronic/e-collections/{collection_id}/e-services/{service_id}/portfolios/{portfolio_id}",
        "DELETE /almaws/v1/electronic/e-collections/{collection_id}/e-services/{service_id}/portfolios/{portfolio_id}",
    ],
    methods=[
        "def list_portfolios(self, collection_id: str, service_id: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_portfolio(self, collection_id: str, service_id: str, portfolio_data: Dict[str, Any]) -> AlmaResponse",
        "def get_portfolio(self, collection_id: str, service_id: str, portfolio_id: str) -> Dict[str, Any]",
        "def update_portfolio(self, collection_id: str, service_id: str, portfolio_id: str, portfolio_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_portfolio(self, collection_id: str, service_id: str, portfolio_id: str) -> AlmaResponse",
    ],
    files=ELECTRONIC_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/electronic/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Same portfolio object as bib-attached portfolios (issue #27); different access path. Document the distinction in CLAUDE.md.
""",
))

# ===========================================================================
# TASKLISTS (medium) — issues 49-52
# ===========================================================================

ISSUES.append(_bootstrap_issue(
    "TaskLists", "TaskLists", "issues 50-52",
    "tasklists.py",
    "https://developers.exlibrisgroup.com/alma/apis/tasklists/",
    "medium",
))

TASKLISTS_FILES = [
    "src/almaapitk/domains/tasklists.py",
    "tests/unit/domains/test_tasklists.py",
]

ISSUES.append(Issue(
    title="Coverage: TaskLists: requested resources",
    domain="TaskLists",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/task-lists/requested-resources",
        "POST /almaws/v1/task-lists/requested-resources",
    ],
    methods=[
        "def list_requested_resources(self, library: str = None, circ_desk: str = None, location: str = None, request_type: str = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def perform_requested_resource_action(self, op: str, request_ids: List[str], **params) -> AlmaResponse",
    ],
    files=TASKLISTS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/tasklists/",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Requested resources are the staff pull-list view. Filtering by library/circ_desk/location is essential.
""",
))

ISSUES.append(Issue(
    title="Coverage: TaskLists: lending requests workflow",
    domain="TaskLists",
    priority="medium",
    effort="M",
    extends_existing={
        "existing": [
            "`ResourceSharing.create_lending_request` — `src/almaapitk/domains/resource_sharing.py:165` (partner-side creation)",
            "`ResourceSharing.get_lending_request` — :351",
            "`ResourceSharing.get_request_summary` — :430",
            "`ResourceSharing.create_lending_request_from_citation` — :479",
        ],
        "note": "Existing methods on ResourceSharing operate on `/almaws/v1/partners/{code}/lending-requests` (partner-side). This issue covers the DIFFERENT endpoint `/almaws/v1/task-lists/rs/lending-requests` for workflow ACTIONS on lending requests already in the queue (ship/receive/return/cancel).",
    },
    endpoints=[
        "GET /almaws/v1/task-lists/rs/lending-requests",
        "POST /almaws/v1/task-lists/rs/lending-requests",
    ],
    methods=[
        "def list_lending_requests_in_queue(self, library: str = None, status: str = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def perform_lending_request_action(self, op: str, request_ids: List[str], **params) -> AlmaResponse",
        "def ship_lending_requests(self, request_ids: List[str]) -> AlmaResponse",
        "def receive_lending_requests(self, request_ids: List[str]) -> AlmaResponse",
    ],
    files=TASKLISTS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/tasklists/",
        "Existing: `src/almaapitk/domains/resource_sharing.py` (partner-side, do NOT duplicate)",
        REF_API_EXPERT,
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION + [
        "Methods are placed on the new `TaskLists` domain, NOT on `ResourceSharing`.",
        "Test verifies the partner-side and task-list-side paths return consistent state for the same request.",
    ],
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- The two paths to lending requests are by design in Alma. Partner-side = "create / read this specific request". Task-list-side = "what's in my workflow queue right now and how do I action a batch".
- Document the split in CLAUDE.md so callers know which to use when.
""",
))

ISSUES.append(Issue(
    title="Coverage: TaskLists: printouts",
    domain="TaskLists",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/task-lists/printouts",
        "POST /almaws/v1/task-lists/printouts",
        "POST /almaws/v1/task-lists/printouts/create",
        "GET /almaws/v1/task-lists/printouts/{printout_id}",
        "POST /almaws/v1/task-lists/printouts/{printout_id}",
    ],
    methods=[
        "def list_printouts(self, status: str = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def perform_printouts_action(self, op: str, printout_ids: List[str]) -> AlmaResponse",
        "def create_printout(self, printout_data: Dict[str, Any]) -> AlmaResponse",
        "def get_printout(self, printout_id: str) -> Dict[str, Any]",
        "def perform_printout_service(self, printout_id: str, op: str) -> AlmaResponse",
    ],
    files=TASKLISTS_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/tasklists/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD,
))

# ===========================================================================
# RESOURCE SHARING PARTNERS (medium) — issue 53
# ===========================================================================

ISSUES.append(Issue(
    title="Coverage: ResourceSharing: partner management CRUD",
    domain="ResourceSharing",
    priority="medium",
    effort="M",
    endpoints=[
        "GET /almaws/v1/partners",
        "POST /almaws/v1/partners",
        "GET /almaws/v1/partners/{partner_code}",
        "PUT /almaws/v1/partners/{partner_code}",
        "DELETE /almaws/v1/partners/{partner_code}",
    ],
    methods=[
        "def list_partners(self, q: str = None, limit: int = 10, offset: int = 0, type_filter: str = None) -> List[Dict[str, Any]]",
        "def create_partner(self, partner_data: Dict[str, Any]) -> AlmaResponse",
        "def get_partner(self, partner_code: str) -> Dict[str, Any]",
        "def update_partner(self, partner_code: str, partner_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_partner(self, partner_code: str) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/resource_sharing.py (extend existing ResourceSharing class)",
        "tests/unit/domains/test_resource_sharing.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/partners/",
        REF_API_EXPERT,
        "Existing: `ResourceSharing.create_lending_request` (`src/almaapitk/domains/resource_sharing.py:165`) — same partner_code identifier",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- Partner objects have nested types (ISO_18626, NCIP, EMAIL, EXTERNAL, etc.). Validation must match the type's required fields.
""",
))

# ===========================================================================
# COURSES (low) — issues 54-56
# ===========================================================================

ISSUES.append(_bootstrap_issue(
    "Courses", "Courses", "issues 55-56",
    "courses.py",
    "https://developers.exlibrisgroup.com/alma/apis/courses/",
    "low",
))

COURSES_FILES = [
    "src/almaapitk/domains/courses.py",
    "tests/unit/domains/test_courses.py",
]

ISSUES.append(Issue(
    title="Coverage: Courses: courses CRUD + enrollment",
    domain="Courses",
    priority="low",
    effort="M",
    endpoints=[
        "GET /almaws/v1/courses",
        "POST /almaws/v1/courses",
        "GET /almaws/v1/courses/{course_id}",
        "PUT /almaws/v1/courses/{course_id}",
        "DELETE /almaws/v1/courses/{course_id}",
        "POST /almaws/v1/courses/{course_id} — Enroll",
        "GET /almaws/v1/courses/{course_id}/users",
        "DELETE /almaws/v1/courses/{course_id}/users/{user_id}",
        "DELETE /almaws/v1/courses/{course_id}/lists/{list_id}",
    ],
    methods=[
        "def list_courses(self, q: str = None, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]",
        "def create_course(self, course_data: Dict[str, Any]) -> AlmaResponse",
        "def get_course(self, course_id: str) -> Dict[str, Any]",
        "def update_course(self, course_id: str, course_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_course(self, course_id: str) -> AlmaResponse",
        "def enroll_to_course(self, course_id: str, enrollment_data: Dict[str, Any]) -> AlmaResponse",
        "def list_course_enrollments(self, course_id: str) -> List[Dict[str, Any]]",
        "def remove_course_enrollment(self, course_id: str, user_id: str) -> AlmaResponse",
        "def remove_reading_list_from_course(self, course_id: str, list_id: str) -> AlmaResponse",
    ],
    files=COURSES_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/courses/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- LOW PRIORITY per user direction. Implement only after high/medium tickets are complete.
""",
))

ISSUES.append(Issue(
    title="Coverage: Courses: reading lists + citations + owners + tags",
    domain="Courses",
    priority="low",
    effort="L",
    endpoints=[
        "GET /almaws/v1/courses/{course_id}/reading-lists",
        "POST /almaws/v1/courses/{course_id}/reading-lists",
        "GET /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}",
        "PUT /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}",
        "DELETE /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}",
        "GET /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/citations",
        "POST /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/citations",
        "GET /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/citations/{citation_id}",
        "PUT /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/citations/{citation_id}",
        "DELETE /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/citations/{citation_id}",
        "POST /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/citations/{citation_id} — Remove file",
        "GET /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/owners",
        "POST /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/owners",
        "GET /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/owners/{primary_id}",
        "PUT /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/owners/{primary_id}",
        "DELETE /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/owners/{primary_id}",
        "GET /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/citations/{citation_id}/tags",
        "PUT /almaws/v1/courses/{course_id}/reading-lists/{reading_list_id}/citations/{citation_id}/tags",
    ],
    methods=[
        "def list_reading_lists(self, course_id: str) -> List[Dict[str, Any]]",
        "def create_reading_list(self, course_id: str, reading_list_data: Dict[str, Any]) -> AlmaResponse",
        "def get_reading_list(self, course_id: str, reading_list_id: str) -> Dict[str, Any]",
        "def update_reading_list(self, course_id: str, reading_list_id: str, reading_list_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_reading_list(self, course_id: str, reading_list_id: str) -> AlmaResponse",
        "def list_citations(self, course_id: str, reading_list_id: str) -> List[Dict[str, Any]]",
        "def create_citation(self, course_id: str, reading_list_id: str, citation_data: Dict[str, Any]) -> AlmaResponse",
        "def get_citation(self, course_id: str, reading_list_id: str, citation_id: str) -> Dict[str, Any]",
        "def update_citation(self, course_id: str, reading_list_id: str, citation_id: str, citation_data: Dict[str, Any]) -> AlmaResponse",
        "def delete_citation(self, course_id: str, reading_list_id: str, citation_id: str) -> AlmaResponse",
        "def remove_citation_file(self, course_id: str, reading_list_id: str, citation_id: str) -> AlmaResponse",
        "def list_reading_list_owners(self, course_id: str, reading_list_id: str) -> List[Dict[str, Any]]",
        "def add_reading_list_owner(self, course_id: str, reading_list_id: str, owner_data: Dict[str, Any]) -> AlmaResponse",
        "def get_reading_list_owner(self, course_id: str, reading_list_id: str, primary_id: str) -> Dict[str, Any]",
        "def update_reading_list_owner(self, course_id: str, reading_list_id: str, primary_id: str, owner_data: Dict[str, Any]) -> AlmaResponse",
        "def remove_reading_list_owner(self, course_id: str, reading_list_id: str, primary_id: str) -> AlmaResponse",
        "def get_citation_tags(self, course_id: str, reading_list_id: str, citation_id: str) -> List[str]",
        "def update_citation_tags(self, course_id: str, reading_list_id: str, citation_id: str, tags: List[str]) -> AlmaResponse",
    ],
    files=COURSES_FILES,
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/courses/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- LOW PRIORITY. Largest single ticket — consider splitting into reading-lists vs. citations vs. owners-and-tags if it doesn't fit one PR.
""",
))

# ===========================================================================
# RS DIRECTORY MEMBERS (low) — issue 57
# ===========================================================================

ISSUES.append(Issue(
    title="Coverage: ResourceSharing: directory members (list/get/localize)",
    domain="ResourceSharing",
    priority="low",
    effort="S",
    endpoints=[
        "GET /almaws/v1/RSDirectoryMember",
        "GET /almaws/v1/RSDirectoryMember/{partner_code}",
        "POST /almaws/v1/RSDirectoryMember/{partner_code}",
    ],
    methods=[
        "def list_directory_members(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]",
        "def get_directory_member(self, partner_code: str) -> Dict[str, Any]",
        "def localize_directory_member(self, partner_code: str, localization_data: Dict[str, Any]) -> AlmaResponse",
    ],
    files=[
        "src/almaapitk/domains/resource_sharing.py (extend existing ResourceSharing class)",
        "tests/unit/domains/test_resource_sharing.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/rsdirectorymember/",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- LOW PRIORITY. Niche resource sharing directory; small surface area. Place on existing `ResourceSharing` domain (do NOT create a new domain class).
""",
))

# ===========================================================================
# ANALYTICS (low) — issue 58
# ===========================================================================

ISSUES.append(Issue(
    title="Coverage: Analytics: paths endpoint",
    domain="Analytics",
    priority="low",
    effort="S",
    endpoints=[
        "GET /almaws/v1/analytics/paths/{path}",
    ],
    methods=[
        "def get_analytics_path(self, path: str) -> Dict[str, Any]",
        "def list_analytics_paths(self, parent_path: str = '/shared') -> List[Dict[str, Any]]",
    ],
    files=[
        "src/almaapitk/domains/analytics.py (extend existing Analytics class)",
        "tests/unit/domains/test_analytics.py",
    ],
    references=[
        "Alma dev-network: https://developers.exlibrisgroup.com/alma/apis/analytics/",
        "Existing pattern: `Analytics.get_report_headers` (`src/almaapitk/domains/analytics.py:47`)",
    ],
    acceptance=STANDARD_AC_DOMAIN_EXTENSION,
    notes=STANDARD_NOTES_DOMAIN_METHOD + """
- LOW PRIORITY. Single-method addition; useful for discovering report directory structure programmatically.
- IMPORTANT: per project memory, Analytics requires PRODUCTION credentials (single shared DB; no SANDBOX endpoint). Document this in the new methods' docstrings.
""",
))


# ---------------------------------------------------------------------------
# Issue creation
# ---------------------------------------------------------------------------


def existing_titles() -> set[str]:
    """Pull existing open and closed coverage-issue titles to skip duplicates."""
    result = subprocess.run(
        ["gh", "issue", "list", "--label", "api-coverage",
         "--state", "all", "--limit", "200",
         "--json", "title"],
        check=True, capture_output=True, text=True,
    )
    return {item["title"] for item in json.loads(result.stdout)}


def ensure_labels() -> None:
    """Create the four labels if they don't exist."""
    wanted = {
        "api-coverage": ("0E8A16", "API surface coverage-expansion ticket"),
        "priority:high": ("D93F0B", "High priority"),
        "priority:medium": ("FBCA04", "Medium priority"),
        "priority:low": ("C5DEF5", "Low priority"),
    }
    existing = subprocess.run(
        ["gh", "label", "list", "--limit", "100", "--json", "name"],
        check=True, capture_output=True, text=True,
    )
    have = {item["name"] for item in json.loads(existing.stdout)}
    for name, (color, desc) in wanted.items():
        if name in have:
            continue
        subprocess.run(
            ["gh", "label", "create", name,
             "--color", color, "--description", desc],
            check=True,
        )
        print(f"  + label created: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be filed without creating issues")
    parser.add_argument("--filter", help="Only file issues whose title contains this substring")
    args = parser.parse_args()

    if not args.dry_run:
        print("Ensuring labels exist...")
        ensure_labels()

    skip_titles = set() if args.dry_run else existing_titles()

    filed = 0
    skipped = 0
    failed: list[tuple[str, str]] = []

    for i, issue in enumerate(ISSUES, start=1):
        if args.filter and args.filter not in issue.title:
            continue
        if issue.title in skip_titles:
            print(f"[{i:02}/{len(ISSUES)}] SKIP (exists): {issue.title}")
            skipped += 1
            continue
        body = render(issue)
        labels = ",".join(issue.labels)
        if args.dry_run:
            print(f"[{i:02}/{len(ISSUES)}] WOULD FILE: {issue.title}  (labels: {labels})")
            filed += 1
            continue
        try:
            result = subprocess.run(
                ["gh", "issue", "create",
                 "--title", issue.title,
                 "--body", body,
                 "--label", labels],
                check=True, capture_output=True, text=True,
            )
            url = result.stdout.strip().splitlines()[-1]
            print(f"[{i:02}/{len(ISSUES)}] {url}  ({issue.title})")
            filed += 1
        except subprocess.CalledProcessError as e:
            err = (e.stderr or "").strip() or (e.stdout or "").strip()
            print(f"[{i:02}/{len(ISSUES)}] FAIL: {issue.title}\n    {err}")
            failed.append((issue.title, err))

    print()
    print(f"Filed:   {filed}")
    print(f"Skipped: {skipped}")
    if failed:
        print(f"Failed:  {len(failed)}")
        for title, err in failed:
            print(f"  - {title}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
