"""Raw form: a method that sends two requests wrapped its name onto a line of its own.

Found 2026-11-17 in the owner's terminal: on POST /acq/invoices/{invoice_id} the row
``op=process_invoice | op=paid  Acquisitions.create_invoice_with_lines`` (66 characters) did
not fit the Inputs pane, so the method name broke away from its query.
"""
import pytest

pytest.importorskip("textual")

from rich.text import Text  # noqa: E402

from almaapitk.lab.app.inputs import InputsPane  # noqa: E402
from almaapitk.lab.endpoints import get_endpoint  # noqa: E402

PANE_WIDTH = 50  # text width of the Inputs pane at the 120-column minimum, with margin


def _rows(path: str, method: str = "POST") -> list[str]:
    plain = Text.from_markup(InputsPane._raw_title(get_endpoint(method, path))).plain
    lines = plain.splitlines()
    return lines[next(i for i, line in enumerate(lines) if line.startswith("almaapitk")):]


def test_invoice_wrapper_rows_fit_the_pane():
    rows = _rows("/almaws/v1/acq/invoices/{invoice_id}")
    assert max(len(r) for r in rows) <= PANE_WIDTH, rows


def test_each_request_of_a_two_request_method_gets_its_own_row():
    rows = _rows("/almaws/v1/acq/invoices/{invoice_id}")
    assert "  op=process_invoice  create_invoice_with_lines" in rows
    assert "  op=paid  create_invoice_with_lines" in rows
    assert rows[0] == "almaapitk (Acquisitions):"
