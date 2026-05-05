"""Read/write chunks/<name>/status.json per spec §8.5.

The status file is the source of truth for chunk lifecycle. Stages are
discrete; transitions are explicit.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

VALID_STAGES = (
    "defined",
    "impl-running",
    "impl-done",
    "test-data-pending",
    "test-running",
    "test-done",
    "pr-opened",
    "merged",
    "aborted",
)
TERMINAL_STAGES = {"merged", "aborted"}


def _now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_status(chunk_dir: Path, chunk_name: str, issues: list[int]) -> None:
    """Create the initial status.json for a new chunk (stage: defined)."""
    chunk_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "chunk": chunk_name,
        "issues": list(issues),
        "stage": "defined",
        "branch": f"chunk/{chunk_name}",
        "createdAt": _now(),
        "updatedAt": _now(),
        "lastEvent": "Chunk defined; awaiting implementation trigger.",
        "nextAction": f"chunks run-impl {chunk_name}",
        "openBreakpoints": [],
        "implRunId": None,
        "testRunId": None,
        "prUrl": None,
    }
    (chunk_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")


def read_status(chunk_dir: Path) -> dict[str, Any]:
    return json.loads((chunk_dir / "status.json").read_text())


def transition(
    chunk_dir: Path,
    new_stage: str,
    last_event: str,
    next_action: str,
    **extra: Any,
) -> None:
    """Update stage and metadata. `extra` keys overwrite top-level fields."""
    if new_stage not in VALID_STAGES:
        raise ValueError(
            f"invalid stage {new_stage!r}; must be one of {VALID_STAGES}"
        )
    status = read_status(chunk_dir)
    status["stage"] = new_stage
    status["lastEvent"] = last_event
    status["nextAction"] = next_action
    status["updatedAt"] = _now()
    for k, v in extra.items():
        status[k] = v
    (chunk_dir / "status.json").write_text(json.dumps(status, indent=2) + "\n")


def list_active(chunks_root: Path) -> list[dict[str, Any]]:
    """Return status objects for all non-terminal chunks, newest first."""
    out: list[dict[str, Any]] = []
    if not chunks_root.exists():
        return out
    for child in chunks_root.iterdir():
        sf = child / "status.json"
        if not sf.exists():
            continue
        status = json.loads(sf.read_text())
        if status["stage"] in TERMINAL_STAGES:
            continue
        out.append(status)
    out.sort(key=lambda s: s.get("updatedAt", ""), reverse=True)
    return out


def list_all(chunks_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not chunks_root.exists():
        return out
    for child in chunks_root.iterdir():
        sf = child / "status.json"
        if sf.exists():
            out.append(json.loads(sf.read_text()))
    out.sort(key=lambda s: s.get("updatedAt", ""), reverse=True)
    return out


def compute_empty_scope_warning(manifest: dict, chunk_name: str) -> str | None:
    """Return a stderr-bound warning string when any issue in `manifest` has
    an empty ``files_to_touch`` list, else ``None``.

    Surfaced by ``chunks define`` so the operator catches a metadata bug
    that would otherwise stall the impl run on R7 scope-check (issue #99).
    The R7 gate uses ``files_to_touch`` as an allowlist; an empty list
    rejects every change the agent makes. Architectural issues filed
    before the structured template (#3-#21) commonly omit the section.
    """
    empty_issues = [
        issue["number"]
        for issue in manifest.get("issues", [])
        if not (issue.get("files_to_touch") or [])
    ]
    if not empty_issues:
        return None
    nums = ", ".join(f"#{n}" for n in empty_issues)
    return (
        f"WARNING: empty files_to_touch for: {nums}\n"
        f"  scope-check (R7) will fail every implement attempt.\n"
        f"  Resolve BEFORE run-impl by EITHER:\n"
        f"    (a) amending the issue body to add a '## Files to touch'\n"
        f"        section listing the paths the impl will touch, then\n"
        f"        re-run `chunks define`,\n"
        f"    (b) editing chunks/{chunk_name}/manifest.json directly to\n"
        f"        add files_to_touch arrays for the affected issues."
    )
