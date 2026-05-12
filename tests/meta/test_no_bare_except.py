"""Structural guard against bare ``except:`` clauses in the package
source tree.

The ``client-ergonomics`` chunk's acceptance criteria killed every bare
``except:`` in ``src/almaapitk/client/`` but did not sweep the rest of
``src/almaapitk/``. The 0.4.x review (finding F-003) discovered that
``src/almaapitk/domains/acquisition.py`` still carried a bare
``except:`` in the ``receive_item`` XML-fallback path. Bare ``except:``
silently swallows ``KeyboardInterrupt`` and ``SystemExit`` and obscures
real failures, so we walk the AST of every module under
``src/almaapitk/`` and fail on any ``ast.ExceptHandler`` whose
``type`` attribute is ``None`` (i.e. a bare ``except:``).

Pattern source: mirrors ``tests/meta/test_no_hardcoded_version.py`` —
same ``ast.parse`` + ``ast.walk`` + ``rglob("*.py")`` shape; reused for
issue #133 because the structural-guard approach is the right fit for
"this construct must not appear anywhere in src/".
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "almaapitk"


def _bare_except_lines(file_path: Path) -> list[int]:
    """Return line numbers of bare ``except:`` clauses in ``file_path``.

    A bare ``except:`` is an ``ast.ExceptHandler`` whose ``type`` is
    ``None``. ``except Exception:`` and ``except (A, B):`` populate
    ``type`` with an ``ast.Name`` / ``ast.Tuple`` respectively and are
    therefore skipped.
    """
    tree = ast.parse(file_path.read_text(), filename=str(file_path))
    offenders: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            offenders.append(node.lineno)
    return sorted(offenders)


def test_no_bare_except_in_src() -> None:
    """No module under ``src/almaapitk/`` may contain a bare ``except:``.

    Bare ``except:`` swallows ``KeyboardInterrupt`` and ``SystemExit``,
    making library code uninterruptible and burying real bugs. Always
    name the exception(s) actually being recovered from (e.g.
    ``except ValueError:`` for ``response.json()`` decode failures).
    """
    offenders: list[str] = []
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        for line_no in _bare_except_lines(py_file):
            rel = py_file.relative_to(SRC_ROOT.parent.parent)
            offenders.append(f"{rel}:{line_no}")
    if offenders:
        pytest.fail(
            f"Found {len(offenders)} bare ``except:`` clause(s) in library "
            f"code (must be narrowed to the specific exception(s) actually "
            f"raised — bare except: swallows KeyboardInterrupt and "
            f"SystemExit, obscures real failures, and was eliminated from "
            f"src/almaapitk/client/ in the client-ergonomics chunk; this "
            f"guard exists to prevent reintroduction anywhere else under "
            f"src/almaapitk/ — see issue #133):\n  "
            + "\n  ".join(offenders)
        )
