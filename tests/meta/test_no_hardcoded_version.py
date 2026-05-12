"""Structural guard against hardcoded ``__version__`` literals in the
package source tree.

The 0.4.2 release shipped to PyPI with ``almaapitk.__version__ == "0.3.1"``
because ``src/almaapitk/__init__.py`` had a hardcoded
``__version__ = "0.3.1"`` constant that never got bumped alongside
``pyproject.toml``. The runtime regression test at ``tests/test_version.py``
catches reintroduction at import-time, but only after the bad value is
actually loaded; this test catches the **source-tree cause** by walking
the AST of every module under ``src/almaapitk/`` and failing on any
``__version__ = "<string literal>"`` assignment that could drift from
``pyproject.toml``.

Pattern source: mirrors ``tests/meta/test_logging_policy.py`` — same
``ast.parse`` + ``ast.walk`` + ``rglob("*.py")`` shape; reused for issue
#131 because the structural-guard approach is the right fit for "this
construct must not appear anywhere in src/".

Allowed exceptions:

* The ``PackageNotFoundError`` sentinel ``"0.0.0+unknown"`` in
  ``src/almaapitk/__init__.py`` — documented fallback for the
  not-installed case, guarded by ``tests/test_version.py::
  test_version_is_not_unknown_fallback``.
* Subpackage component versions (``src/almaapitk/<subpkg>/__init__.py``
  with their own ``__version__``) — they don't shadow ``almaapitk.
  __version__``. The toolkit's drift bug was specifically at the
  package root.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "almaapitk"
PACKAGE_ROOT_INIT = SRC_ROOT / "__init__.py"

# Documented sentinel — the PackageNotFoundError fallback in
# src/almaapitk/__init__.py. Cannot drift because it's not a real
# version string; tests/test_version.py guards that this value never
# leaks into a real install.
ALLOWED_FALLBACK_LITERALS = frozenset({"0.0.0+unknown"})


def _hardcoded_version_assignments(file_path: Path) -> list[tuple[int, str]]:
    """Return ``(line_no, literal)`` tuples for hardcoded ``__version__``
    assignments in ``file_path``.

    A hardcoded assignment is an ``ast.Assign`` whose single target is
    ``Name(id='__version__')`` and whose value is ``Constant(value=str)``.
    Dynamic resolutions (e.g. ``__version__ = _pkg_version("almaapitk")``)
    are ``ast.Call`` values and therefore skipped.
    """
    tree = ast.parse(file_path.read_text(), filename=str(file_path))
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and target.id == "__version__"):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            offenders.append((node.lineno, value.value))
    return offenders


def test_no_hardcoded_version_in_src() -> None:
    """The package-root ``__init__.py`` must not contain a real hardcoded
    ``__version__`` literal.

    Only the documented ``PackageNotFoundError`` sentinel
    (``"0.0.0+unknown"``) is allowed; anything else is the exact
    anti-pattern that caused the 0.4.2 PyPI yank (issue #131).
    """
    offenders = _hardcoded_version_assignments(PACKAGE_ROOT_INIT)
    real_offenders = [
        (line, literal)
        for line, literal in offenders
        if literal not in ALLOWED_FALLBACK_LITERALS
    ]
    if real_offenders:
        rel = PACKAGE_ROOT_INIT.relative_to(SRC_ROOT.parent.parent)
        formatted = ", ".join(
            f"line {line}: __version__ = {literal!r}"
            for line, literal in real_offenders
        )
        pytest.fail(
            f"Found {len(real_offenders)} hardcoded __version__ literal(s) "
            f"in {rel} ({formatted}). Use "
            f"importlib.metadata.version('almaapitk') instead — see the "
            f"canonical pattern already present in that file. This guard "
            f"exists because the 0.4.2 PyPI release shipped with a drifted "
            f"hardcoded value (issue #131); only the documented "
            f"PackageNotFoundError sentinel {sorted(ALLOWED_FALLBACK_LITERALS)!r} "
            f"is allowed."
        )
