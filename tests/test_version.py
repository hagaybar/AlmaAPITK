"""Regression test: `almaapitk.__version__` must always match the installed
package's metadata version.

Before `0.4.3`, `src/almaapitk/__init__.py` had `__version__ = "0.3.1"`
hardcoded and was never updated when `pyproject.toml` was bumped. The
`0.4.2` release shipped to PyPI with `__version__ == "0.3.1"` even though
`pip install almaapitk==0.4.2` correctly resolved 0.4.2 from PyPI metadata.

This test fails if anyone reintroduces a hardcoded `__version__`, or if
the dynamic resolution path breaks. Per CLAUDE.md R10 (bug-driven
regression tests), it ships with the fix in the same commit.
"""
from __future__ import annotations

from importlib.metadata import version as _pkg_version

import almaapitk


def test_version_matches_package_metadata():
    """The package's runtime `__version__` must equal its installed-metadata
    version.

    Mismatch indicates either: (a) someone reintroduced a hardcoded
    `__version__` literal, or (b) the dynamic resolution path broke (e.g.
    package renamed, metadata not packaged).
    """
    metadata_version = _pkg_version("almaapitk")
    assert almaapitk.__version__ == metadata_version, (
        f"almaapitk.__version__ is {almaapitk.__version__!r} but installed-package "
        f"metadata reports {metadata_version!r}. See tests/test_version.py docstring "
        f"for the 0.4.2 regression that motivated this guard."
    )


def test_version_is_not_unknown_fallback():
    """Sanity: the `PackageNotFoundError` fallback indicates a broken install.

    If this fires in a normal test run, the package isn't installed properly —
    `poetry install` / `pip install -e .` should resolve it.
    """
    assert almaapitk.__version__ != "0.0.0+unknown", (
        "almaapitk.__version__ resolved to the 'unknown package' fallback. "
        "The package metadata is not installed in the current environment — "
        "re-run `poetry install` or `pip install -e .`."
    )
