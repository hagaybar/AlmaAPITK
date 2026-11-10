"""The Alma Lab full-screen app (needs ``pip install almaapitk[lab]``)."""
from __future__ import annotations

from pathlib import Path

import textual  # noqa: F401  (fail fast with ImportError when the extra is missing)


def run_app(environment: str = "SANDBOX", evidence_dir: Path = Path("alma-lab-evidence")) -> int:
    from almaapitk.lab.app.app import LabApp
    from almaapitk.lab.runner import Session

    session = Session(environment, evidence_dir=evidence_dir, source="app")
    try:
        LabApp(session).run()
    finally:
        session.close()
    return 0
