"""R10 regression tests for issue #172.

The invoice / invoice-line builders sent three fields under names or shapes
the Alma POST schemas do not have, so Alma silently dropped them:
``invoice_line_type`` (schema: ``type``), ``vat`` (schema:
``invoice_line_vat``) and a bare-string ``payment_method`` (schema: ``{value}``).
"""
from almaapitk.domains.acquisition import Acquisitions


class _StubClient:
    def get_environment(self):
        return "SANDBOX"


def _acq():
    return Acquisitions(_StubClient())


def _line(**optional_fields):
    return _acq()._build_invoice_line_structure(
        po_line="POL-0001", amount=10.0, quantity=1, fund_code="FUND1",
        **optional_fields,
    )


def test_invoice_line_type_is_sent_as_type():
    line = _line(invoice_line_type="SHIPMENT")

    assert line["type"] == {"value": "SHIPMENT"}
    assert "invoice_line_type" not in line


def test_invoice_line_type_defaults_to_regular():
    assert _line()["type"] == {"value": "REGULAR"}


def test_line_vat_is_sent_as_invoice_line_vat():
    vat = {"vat_code": {"value": "VAT1"}}

    line = _line(vat=vat)

    assert line["invoice_line_vat"] == vat
    assert "vat" not in line


def test_payment_method_is_wrapped_as_value_object():
    invoice = _acq()._build_invoice_structure(
        number="INV-1", invoice_date="2026-01-01", vendor_code="V1",
        total_amount=10.0, payment_method="CASH",
    )

    assert invoice["payment_method"] == {"value": "CASH"}
