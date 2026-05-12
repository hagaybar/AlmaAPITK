"""Guard that the top-of-page ``**Version:**`` headings in the
package-version doc surfaces stay in sync with ``pyproject.toml``.

The 0.4.0 → 0.4.3 release cycle had three doc files with a
``**Version:** 0.2.0`` heading that nobody bumped on each release:

* ``docs/api-reference.md`` (fixed in 0.4.3)
* ``docs/index.md`` (fixed via this issue's accompanying change)
* ``docs/getting-started.md`` (fixed via this issue's accompanying change)

This test pins the invariant for all three files going forward. If a
maintainer adds a new top-level doc page with a ``**Version:**``
heading, they must either bump it on each release or remove the
heading entirely (the test will fail on stale headings, not on missing
ones).

Scope decision: only files whose ``**Version:**`` heading
unambiguously refers to the *package* version are policed. Files that
use ``**Version:**`` for a different semantic (e.g.
``docs/API_CONTRACT.md`` where it denotes the API contract version,
not the package version) are excluded explicitly. Historical release
plans under ``docs/superpowers/`` are also excluded — their version
strings are immutable historical artifacts.

Pattern source: ``tests/test_version.py`` for the
``pyproject.toml`` reading shape; the file-list scoping mirrors
``docs/RELEASE_CHECKLIST.md`` Phase C bullet list of "every domain
discoverability surface".
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Top-of-page Version: heading pattern. Anchored to the start of a line
# so it does not match inline mentions like "... a version: 0.4.3 of ...".
# ``**Version:**`` is the markdown-bold form used at the top of doc pages;
# captured group is the X.Y.Z (or X.Y.Z.suffix) literal.
VERSION_HEADING_RE = re.compile(r"^\*\*Version:\*\*\s*([0-9][0-9A-Za-z.+-]*)", re.MULTILINE)

# Files whose ``**Version:**`` heading refers to the *package* version
# and must therefore match ``pyproject.toml``. This explicit allowlist
# is the test's scope. New top-level doc pages with a package-version
# heading must be added here so this gate covers them.
PACKAGE_VERSION_DOC_FILES: tuple[Path, ...] = (
    REPO_ROOT / "docs" / "index.md",
    REPO_ROOT / "docs" / "getting-started.md",
    REPO_ROOT / "docs" / "api-reference.md",
)


def _read_pyproject_version() -> str:
    """Return the ``version`` field from ``[project]`` in ``pyproject.toml``.

    Pattern source: mirrors the stdlib ``tomllib`` usage in modern
    release tooling; ``pyproject.toml`` is guaranteed to exist in this
    repo (build configuration).
    """
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    version = data.get("project", {}).get("version")
    assert isinstance(version, str) and version, (
        f"Could not read [project].version from {PYPROJECT}. Either the "
        f"key was removed or the toml shape changed."
    )
    return version


@pytest.mark.parametrize(
    "doc_file",
    PACKAGE_VERSION_DOC_FILES,
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_docs_version_matches_pyproject(doc_file: Path) -> None:
    """Every ``**Version:** X.Y.Z`` heading in a policed doc file must
    match ``pyproject.toml`` ``[project].version``.

    Failure modes this catches:

    * Stale ``**Version:** 0.2.0`` heading on a v0.4.x release page
      (the exact bug that pushed 0.4.1 and 0.4.2 into bump territory).
    * A typo / off-by-one bump on one file but not the others.

    The test does NOT enforce that the heading must exist — a doc page
    is free to omit it. The invariant is: *if* the heading exists, it
    must be current.
    """
    expected = _read_pyproject_version()
    text = doc_file.read_text()
    matches = VERSION_HEADING_RE.findall(text)
    if not matches:
        # No heading present — the test deliberately allows this; only
        # stale headings are an error.
        return
    rel = doc_file.relative_to(REPO_ROOT).as_posix()
    stale = [m for m in matches if m != expected]
    assert not stale, (
        f"{rel} has stale **Version:** heading(s) {stale!r}; "
        f"pyproject.toml [project].version is {expected!r}. "
        f"Update the heading(s) as part of the release version bump — "
        f"docs/RELEASE_CHECKLIST.md Phase E covers this. This test "
        f"fires because doc pages with a stale Version heading mislead "
        f"users into thinking they are reading documentation for an "
        f"older release (issue #131)."
    )
