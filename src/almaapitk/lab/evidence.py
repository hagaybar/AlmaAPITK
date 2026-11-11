"""Evidence records: one JSON file per call, under ``alma-lab-evidence/``.

Records hold real identifiers and possibly patron data, so the folder must
stay out of git (repo rule R9). ``gitignore_status`` lets the front ends warn.
"""
from __future__ import annotations

import datetime
import json
import platform
import subprocess
from dataclasses import asdict, dataclass, field, fields
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal, Optional, Union

from almaapitk.lab import TOOL_VERSION
from almaapitk.lab.capture import CapturedRequest

DEFAULT_EVIDENCE_DIR = Path("alma-lab-evidence")


class EvidenceError(Exception):
    """The evidence record could not be written or read."""


@dataclass
class EvidenceRecord:
    id: str
    created_at: str
    tool_version: str
    almaapitk_version: str
    python_version: str
    environment: str
    base_url_host: str
    operation: str
    inputs: dict[str, Any]
    requests: list[CapturedRequest] = field(default_factory=list)
    result: Any = None
    capped: bool = False
    error: Optional[str] = None
    expectations: list[dict] = field(default_factory=list)
    source: str = "app"
    command: Optional[str] = None
    incomplete: bool = False
    incomplete_reason: Optional[str] = None
    cancelled_writes: list[dict] = field(default_factory=list)
    # raw calls (phase 2); defaulted so phase 1 records still load
    raw: bool = False
    endpoint: Optional[dict] = None
    wrapped_by: list[str] = field(default_factory=list)
    baseline: Optional[dict] = None
    body_diff: Optional[str] = None
    refused: Optional[str] = None
    slug: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["requests"] = [r.to_dict() for r in self.requests]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceRecord":
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        values["requests"] = [CapturedRequest(**r) for r in data.get("requests", [])]
        return cls(**values)

    @property
    def last_status(self) -> Optional[int]:
        sent = [r for r in self.requests if r.sent]
        return sent[-1].status if sent else None

    @property
    def checks_passed(self) -> bool:
        if self.refused:
            return False
        return all(e.get("outcome") == "passed" for e in self.expectations)


def new_record(*, operation: str, inputs: dict, environment: str, base_url_host: str,
               source: str, command: Optional[str] = None) -> EvidenceRecord:
    now = datetime.datetime.now().astimezone()
    return EvidenceRecord(
        id=f"{now:%Y%m%d-%H%M%S}-{operation}",
        created_at=now.isoformat(timespec="seconds"),
        tool_version=TOOL_VERSION,
        almaapitk_version=_almaapitk_version(),
        python_version=platform.python_version(),
        environment=environment,
        base_url_host=base_url_host,
        operation=operation,
        inputs=inputs,
        source=source,
        command=command,
    )


def write_record(record: EvidenceRecord, evidence_dir: Path) -> Path:
    """Write the record; on a name collision add ``-2``, ``-3`` and update ``record.id``."""
    evidence_dir = Path(evidence_dir)
    day = evidence_dir / record.created_at[:10]
    stem = f"{record.created_at[11:19].replace(':', '')}-{record.slug or record.operation}"
    try:
        day.mkdir(parents=True, exist_ok=True)
        path, n = day / f"{stem}.json", 1
        while path.exists():
            n += 1
            path = day / f"{stem}-{n}.json"
        base_id = f"{record.created_at[:10].replace('-', '')}-{stem}"
        record.id = base_id if n == 1 else f"{base_id}-{n}"
        with open(path, "x", encoding="utf-8") as fh:
            json.dump(record.to_dict(), fh, ensure_ascii=False, indent=2, default=str)
    except OSError as exc:
        raise EvidenceError(f"cannot write evidence under {evidence_dir}: {exc}") from exc
    return path


def load_record(ref: Union[str, Path], evidence_dir: Path) -> EvidenceRecord:
    """Load by path, or by record id (``YYYYMMDD-HHMMSS-<operation>[-N]``)."""
    path = Path(ref)
    if not path.is_file():
        path = _path_for_id(str(ref), Path(evidence_dir))
    try:
        return EvidenceRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        raise EvidenceError(f"cannot read evidence {ref}: {exc}") from exc


def list_records(evidence_dir: Path, limit: int = 200) -> list[Path]:
    """Newest first."""
    evidence_dir = Path(evidence_dir)
    if not evidence_dir.is_dir():
        return []
    candidates = [p for p in evidence_dir.glob("*/*.json") if not p.name.endswith(".redacted.json")]
    paths = sorted(candidates, key=lambda p: (p.parent.name, p.stat().st_mtime_ns, p.name),
                   reverse=True)
    return paths[:limit]


def _path_for_id(record_id: str, evidence_dir: Path) -> Path:
    try:
        date = datetime.datetime.strptime(record_id[:8], "%Y%m%d").date().isoformat()
    except ValueError:
        raise EvidenceError(f"{record_id!r} is neither a file nor a record id") from None
    rest = record_id[9:]
    path = evidence_dir / date / f"{rest[:6]}{rest[6:]}.json"
    if not path.is_file():
        raise EvidenceError(f"no evidence record {record_id!r} under {evidence_dir}")
    return path


GitignoreStatus = Literal["ignored", "not-ignored", "no-repo"]


def gitignore_status(evidence_dir: Path) -> GitignoreStatus:
    """Whether git would ignore the evidence folder."""
    evidence_dir = Path(evidence_dir).resolve()
    anchor = _existing_parent(evidence_dir)
    try:
        proc = subprocess.run(["git", "-C", str(anchor), "check-ignore", "-q", str(evidence_dir)],
                              capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "no-repo"
    return {0: "ignored", 1: "not-ignored"}.get(proc.returncode, "no-repo")


def add_to_gitignore(evidence_dir: Path) -> None:
    """Append the folder to the repository's top-level ``.gitignore``."""
    evidence_dir = Path(evidence_dir).resolve()
    anchor = _existing_parent(evidence_dir)
    top = subprocess.run(["git", "-C", str(anchor), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, timeout=10)
    if top.returncode != 0:
        raise EvidenceError(f"{evidence_dir} is not inside a git repository")
    root = Path(top.stdout.strip())
    # Anchored and without a trailing slash: matches before the folder exists.
    entry = "/" + evidence_dir.relative_to(root).as_posix()
    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    gitignore.write_text(f"{existing}{prefix}# Alma Lab evidence: real IDs, never commit (R9)\n{entry}\n",
                         encoding="utf-8")


def _existing_parent(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path if path.is_dir() else path.parent


def _almaapitk_version() -> str:
    try:
        return version("almaapitk")
    except PackageNotFoundError:
        return "unknown"
