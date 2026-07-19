"""Guard against the discoverability-drift class of bug that triggered
the 0.4.1 and 0.4.2 release bumps.

The 0.4.1 → 0.4.2 cycle was caused by the ``Configuration`` domain class
(and several typed exceptions) being added to ``src/almaapitk/__init__.py``
``__all__`` but **not** to the top-level discoverability surfaces:
``README.md`` (which is what users see on PyPI / GitHub), ``docs/index.md``,
and ``docs/getting-started.md``. The deep reference (``docs/api-reference.md``)
and the per-domain guides under ``docs/domains/`` had the new symbols;
the top-level surfaces did not.

This test parses ``__all__`` from ``src/almaapitk/__init__.py`` and asserts
that **every domain class** appears in every top-level surface (README in
both its bullet list AND its API-reference domain table, ``docs/index.md``,
and ``docs/getting-started.md``). Re-adding a new domain to ``__all__``
without surfacing it in the top-level docs will fail this test.

Scope decision (Option A in issue #131):

The strict assertion is scoped to **domain classes** only — the surface
that Phase C of ``docs/RELEASE_CHECKLIST.md`` explicitly polices, and the
surface that caused the 0.4.1 / 0.4.2 release bumps. The current top-level
docs do not yet mention every ``__all__`` symbol (the typed
``Alma*Error`` subclasses, ``TSVGenerator``, and ``CitationMetadataError``
are inconsistent across surfaces; ``AlmaAPIClient`` / ``AlmaResponse``
are missing from ``docs/index.md``). Issue #118 owns the broader
docs-completeness cleanup. **TODO(#118):** once #118 lands, tighten this
test to enforce coverage of ALL ``__all__`` symbols (not just domains).

Pattern source: regex matching ``\\b<symbol>\\b`` rather than substring
``in`` checks because substring matching produces false positives
(``Admin`` would be falsely "found" inside ``administrator``). The
issue body explicitly calls this out.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_INIT = REPO_ROOT / "src" / "almaapitk" / "__init__.py"
README = REPO_ROOT / "README.md"
DOCS_INDEX = REPO_ROOT / "docs" / "index.md"
DOCS_GETTING_STARTED = REPO_ROOT / "docs" / "getting-started.md"

# Domain classes that MUST appear in every top-level surface. Source of
# truth: this list is a subset of ``__all__`` in src/almaapitk/__init__.py;
# we cross-check via ``test_domain_set_matches_all_subset`` that it stays
# in sync with the actual ``__all__``.
DOMAIN_CLASSES: frozenset[str] = frozenset(
    {
        "Acquisitions",
        "Admin",
        "Analytics",
        "BibliographicRecords",
        "Configuration",
        "ResourceSharing",
        "Users",
    }
)

# Symbols in ``__all__`` that are intentionally NOT policed by the
# domain-class doc-coverage gate. Adding to this set is the explicit
# opt-out signal a maintainer must take when a new ``__all__`` symbol is
# not a domain class. If you add a new domain class to ``__all__``, do
# NOT add it here — add it to ``DOMAIN_CLASSES`` instead so the gate
# polices the new top-level docs surface.
NON_DOMAIN_EXPORTS: frozenset[str] = frozenset(
    {
        # Package metadata
        "__version__",
        # Core client + response
        "AlmaAPIClient",
        "AlmaResponse",
        # Exception hierarchy (TODO(#118): police these on top-level surfaces
        # once the docs cleanup ticket lands)
        "AlmaAPIError",
        "AlmaValidationError",
        "AlmaAuthenticationError",
        "AlmaRateLimitError",
        "AlmaServerError",
        "AlmaResourceNotFoundError",
        "AlmaDuplicateInvoiceError",
        "AlmaInvalidPolModeError",
        # Raised when no API key can be resolved for the client (issue #143)
        "CredentialError",
        # Utilities (TODO(#118): see above)
        "TSVGenerator",
        "CitationMetadataError",
        # Domain helper: a pure MARCXML builder function (issue #179), not a
        # domain class — no top-level docs surface to police.
        "build_alma_bib_xml",
        # Domain helper: a pure resource-sharing request-body builder function
        # (issue #197), not a domain class — same opt-out rationale.
        "build_user_rs_request",
    }
)


def _parse_all_from_init(init_path: Path) -> list[str]:
    """Extract the ``__all__`` list from a package ``__init__.py`` via
    AST parsing — no import side-effects.

    Pattern source: standard ast.literal_eval over the Constant strings
    of an ``ast.List`` value, used here because parsing the package init
    is cheaper and safer than importing it.
    """
    tree = ast.parse(init_path.read_text(), filename=str(init_path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and target.id == "__all__"):
            continue
        if not isinstance(node.value, ast.List):
            continue
        symbols: list[str] = []
        for elt in node.value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                symbols.append(elt.value)
        return symbols
    raise AssertionError(
        f"Could not find __all__ in {init_path}. Either the file no "
        f"longer defines __all__ or the AST shape changed."
    )


def _contains_symbol(text: str, symbol: str) -> bool:
    """Whole-word match for a symbol in a markdown corpus.

    Uses ``\\b`` boundaries so ``Admin`` matches ``Admin`` and ``Admin,``
    but not ``administrator``. The issue body explicitly warns against
    substring ``in`` matching.
    """
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    return bool(pattern.search(text))


def _readme_surfaces() -> tuple[str, str]:
    """Return the README's two top-level surfaces:

    1. The "Features" / domain bullet list (before the "## Installation"
       heading).
    2. The "API Reference" tables (between "## API Reference" and the
       next ``##`` heading at the same level — practically: through the
       end of the file or until "## Environment Configuration", whichever
       comes first).

    Returning them as separate strings lets the test report which
    surface is missing a symbol, matching the issue's "TWO surfaces"
    requirement.
    """
    text = README.read_text()
    # Surface 1: from start of file through (but not including) "## Installation".
    install_idx = text.find("## Installation")
    bullet_surface = text[:install_idx] if install_idx != -1 else text

    # Surface 2: from "## API Reference" through end (or next major section).
    api_ref_idx = text.find("## API Reference")
    if api_ref_idx == -1:
        raise AssertionError(
            "README.md missing '## API Reference' heading — required as "
            "the second discoverability surface."
        )
    rest = text[api_ref_idx:]
    next_section = rest.find("\n## Environment Configuration")
    api_surface = rest[: next_section if next_section != -1 else len(rest)]
    return bullet_surface, api_surface


def test_all_export_list_is_parseable() -> None:
    """Sanity: the AST extraction returns a non-empty list of strings.

    If this fires, ``src/almaapitk/__init__.py`` ``__all__`` was reshaped
    in a way the helper can't read — fix the helper, don't disable the
    test.
    """
    symbols = _parse_all_from_init(PKG_INIT)
    assert symbols, "__all__ parsed as empty — check src/almaapitk/__init__.py"
    assert all(isinstance(s, str) for s in symbols)


def test_domain_set_matches_all_subset() -> None:
    """``DOMAIN_CLASSES`` must stay a subset of the actual ``__all__``.

    If a domain is renamed or removed from ``__all__`` without updating
    this test, fail loudly so the maintainer notices.
    """
    all_symbols = set(_parse_all_from_init(PKG_INIT))
    missing = DOMAIN_CLASSES - all_symbols
    assert not missing, (
        f"DOMAIN_CLASSES contains symbols not in __all__: {sorted(missing)}. "
        f"Update DOMAIN_CLASSES in this test (and possibly the docs) to "
        f"match src/almaapitk/__init__.py."
    )


def test_all_exports_are_categorised() -> None:
    """Every symbol in ``__all__`` must be either a known domain class
    (policed by the top-level docs gate) or an explicit non-domain
    export (opted out). This forces a maintainer who adds a new
    ``__all__`` symbol to make an explicit choice: police it on the
    top-level docs surfaces (add to ``DOMAIN_CLASSES`` + update the
    three doc files), or document why it's exempt (add to
    ``NON_DOMAIN_EXPORTS``).

    This is the safety net for "developer adds a new domain but forgets
    to update the test" — without it, the doc-coverage gate would
    silently skip the new domain.
    """
    all_symbols = set(_parse_all_from_init(PKG_INIT))
    uncategorised = all_symbols - DOMAIN_CLASSES - NON_DOMAIN_EXPORTS
    assert not uncategorised, (
        f"The following __all__ symbol(s) are not categorised in "
        f"tests/meta/test_top_level_docs_match_all.py: "
        f"{sorted(uncategorised)}.\n\n"
        f"If they are domain classes (top-level user-facing APIs), add "
        f"them to DOMAIN_CLASSES *and* update README.md (two surfaces), "
        f"docs/index.md, and docs/getting-started.md.\n\n"
        f"If they are not domain classes (utilities, internal types, "
        f"metadata), add them to NON_DOMAIN_EXPORTS with a comment "
        f"explaining why. TODO(#118) will eventually broaden this gate."
    )


@pytest.mark.parametrize("domain", sorted(DOMAIN_CLASSES))
def test_top_level_docs_match_all(domain: str) -> None:
    """Every domain class in ``__all__`` must appear in all four
    top-level discoverability surfaces:

    * README.md — bullet list (Features section).
    * README.md — API Reference table.
    * docs/index.md.
    * docs/getting-started.md.

    The 0.4.1 and 0.4.2 release bumps were caused by adding
    ``Configuration`` to ``__all__`` without surfacing it in all four
    places. This test makes that omission a CI-failable event rather
    than a release-time discovery.

    Scope note (Option A, issue #131): only domain classes are policed
    today; the broader ``__all__`` coverage gate waits on issue #118.
    """
    readme_bullets, readme_api_ref = _readme_surfaces()
    index_text = DOCS_INDEX.read_text()
    getting_started_text = DOCS_GETTING_STARTED.read_text()

    missing: list[str] = []
    if not _contains_symbol(readme_bullets, domain):
        missing.append("README.md (Features bullet list)")
    if not _contains_symbol(readme_api_ref, domain):
        missing.append("README.md (API Reference table)")
    if not _contains_symbol(index_text, domain):
        missing.append("docs/index.md")
    if not _contains_symbol(getting_started_text, domain):
        missing.append("docs/getting-started.md")

    assert not missing, (
        f"Domain class {domain!r} is in src/almaapitk/__init__.py __all__ "
        f"but is missing from the following top-level discoverability "
        f"surface(s):\n  - " + "\n  - ".join(missing) + "\n\n"
        f"This is the exact regression class that caused the 0.4.1 and "
        f"0.4.2 release bumps (Configuration was added to __all__ but not "
        f"surfaced in README/index/getting-started). See "
        f"docs/RELEASE_CHECKLIST.md Phase C for the manual checks this "
        f"test automates."
    )
