"""Structural guards for the toolkit's logging policy.

CLAUDE.md mandates "Use almaapitk.alma_logging framework — never print
statements". These tests fail loudly if a future change reintroduces
``print()`` to library code or restores the deleted ``safe_request()``
shim. Issue #14.

Detection uses ``ast`` (not grep) so that:

* docstring examples (``>>> print(...)``) are correctly skipped — they
  live inside string literals, not as executable calls;
* prints inside ``if __name__ == "__main__":`` demo blocks are skipped
  per the issue's acceptance criteria.
"""
from __future__ import annotations

import ast
from pathlib import Path

from almaapitk import AlmaAPIClient


SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "almaapitk"


def _is_main_guard(node: ast.AST) -> bool:
    """``True`` for an ``if __name__ == "__main__":`` node."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    name_node = left if isinstance(left, ast.Name) else right
    str_node = right if name_node is left else left
    if not (isinstance(name_node, ast.Name) and name_node.id == '__name__'):
        return False
    return isinstance(str_node, ast.Constant) and str_node.value == '__main__'


def _print_call_lines(file_path: Path) -> list[int]:
    """Return line numbers of ``print(...)`` calls in this file, excluding
    anything inside ``if __name__ == "__main__":`` blocks."""
    tree = ast.parse(file_path.read_text(), filename=str(file_path))
    main_lines: set[int] = set()
    for top_node in tree.body:
        if _is_main_guard(top_node):
            for child in ast.walk(top_node):
                if hasattr(child, 'lineno'):
                    main_lines.add(child.lineno)

    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == 'print':
            if node.lineno not in main_lines:
                offenders.append(node.lineno)
    return sorted(offenders)


def test_no_print_in_library() -> None:
    offenders: list[str] = []
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        for line_no in _print_call_lines(py_file):
            rel = py_file.relative_to(SRC_ROOT.parent.parent)
            offenders.append(f"{rel}:{line_no}")
    assert not offenders, (
        f"Found {len(offenders)} print() call(s) in library code "
        f"(must be replaced with logger calls per CLAUDE.md):\n  "
        + "\n  ".join(offenders)
    )


def test_safe_request_removed() -> None:
    assert not hasattr(AlmaAPIClient, "safe_request"), (
        "AlmaAPIClient.safe_request was deleted in issue #14 (it swallowed "
        "exceptions and returned None, making error handling impossible). "
        "Use the typed verb methods (get/post/put/delete) and catch "
        "AlmaAPIError instead."
    )
