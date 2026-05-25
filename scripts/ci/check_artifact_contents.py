#!/usr/bin/env python3
"""Verify the built wheel and sdist contain only what they should (issue #150).

Guards against packaging regressions like the pre-0.3.1 "empty wheel"
footgun and stray ``tests/``/``scripts/``/``docs/`` leaking into a release.
Run after ``poetry build``; exits non-zero (listing every offending entry)
when either artifact contains an unexpected file.

Stdlib only -- runs on a bare CI Python with no project deps installed.
"""
from __future__ import annotations

import glob
import os
import re
import sys
import tarfile
import zipfile


def _version_from(filename: str, suffix: str) -> str:
    """Pull ``<version>`` out of ``almaapitk-<version><suffix...>``."""
    stem = os.path.basename(filename)
    # almaapitk-0.4.5-py3-none-any.whl  /  almaapitk-0.4.5.tar.gz
    return stem.split("-")[1] if suffix == ".whl" else stem[: -len(".tar.gz")].split("-", 1)[1]


def check_wheel(path: str) -> list[str]:
    """A wheel may contain only package code + its ``.dist-info`` metadata."""
    version = _version_from(path, ".whl")
    allowed = ("almaapitk/", f"almaapitk-{version}.dist-info/")
    with zipfile.ZipFile(path) as zf:
        return [n for n in zf.namelist()
                if not n.endswith("/") and not n.startswith(allowed)]


def check_sdist(path: str) -> list[str]:
    """An sdist may contain only the documented metadata files + source."""
    version = _version_from(path, ".tar.gz")
    root = f"almaapitk-{version}/"
    allowed_exact = {"PKG-INFO", "pyproject.toml", "README.md",
                     "CHANGELOG.md", "LICENSE"}
    offenders: list[str] = []
    with tarfile.open(path) as tf:
        for member in tf.getmembers():
            if member.isdir():
                continue
            name = member.name
            if not name.startswith(root):
                offenders.append(name)
                continue
            rel = name[len(root):]
            if rel in allowed_exact:
                continue
            if rel.startswith("src/almaapitk/"):
                continue
            if re.fullmatch(r"docs/releases/.*\.md", rel):
                continue
            offenders.append(name)
    return offenders


def _exactly_one(pattern: str, label: str, problems: list[str]) -> str | None:
    matches = sorted(glob.glob(pattern))
    if len(matches) != 1:
        problems.append(f"expected exactly one {label} matching {pattern}, "
                        f"found {len(matches)}: {matches}")
        return None
    return matches[0]


def main() -> int:
    problems: list[str] = []
    wheel = _exactly_one("dist/*.whl", "wheel", problems)
    sdist = _exactly_one("dist/*.tar.gz", "sdist", problems)
    if problems:
        for p in problems:
            print(f"ERROR: {p}")
        return 1

    failures = 0
    for label, offenders in (("wheel", check_wheel(wheel)),
                             ("sdist", check_sdist(sdist))):
        if offenders:
            failures += len(offenders)
            print(f"ERROR: unexpected {label} entries:")
            for name in offenders:
                print(f"  {name}")
    if failures:
        print(f"\n{failures} unexpected artifact entr(ies). "
              "Tighten pyproject.toml include/exclude.")
        return 1
    print(f"OK: {os.path.basename(wheel)} and {os.path.basename(sdist)} "
          "contain only expected files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
