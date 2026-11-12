"""Finding the right call: what a method sends, allowed values as dropdowns, Open in Raw.

Found 2026-11-12: to run an invoice ``op`` the owner looked in the almaapitk methods
(``approve_invoice`` hides that it sends ``op=process_invoice``), then in Raw, where
``op`` was free text and the invoice endpoints looked alike.
"""
import asyncio

import pytest

from almaapitk.lab.catalog import DOMAINS, SentRequest, find_operation, sent_requests
from almaapitk.lab.choices import PARAM_CHOICES, param_choices
from almaapitk.lab.endpoints import get_endpoint, load_endpoints, wrapped_with_query

INVOICE = "/almaws/v1/acq/invoices/{invoice_id}"
INVOICE_TEMPLATE = "/almaws/v1/acq/invoices/{}"


class _Fake:
    """Source the analysis reads (never called)."""

    def fixed(self, invoice_id):
        return self._service(invoice_id, "process_invoice")

    def by_keyword(self, invoice_id):
        return self._service(invoice_id=invoice_id, operation="paid")

    def passes_input(self, invoice_id, operation):
        return self._service(invoice_id, operation)

    def _service(self, invoice_id, operation):
        params = {"op": operation, "lang": "en"}
        return self.client.post(f"almaws/v1/acq/invoices/{invoice_id}", data={}, params=params)

    def unknown(self, invoice_id):
        return self.client.get(f"almaws/v1/acq/invoices/{invoice_id}", params={"view": self.view()})

    def view(self):
        return "brief"


# --- what a method sends --------------------------------------------------------

def test_fixed_argument_to_helper_is_followed():
    assert sent_requests(_Fake, "fixed") == (
        SentRequest("POST", INVOICE_TEMPLATE, (("op", "process_invoice"), ("lang", "en"))),)


def test_keyword_argument_to_helper_is_followed():
    assert sent_requests(_Fake, "by_keyword")[0].query_text == "op=paid&lang=en"


def test_input_passed_through_stays_named():
    assert sent_requests(_Fake, "passes_input")[0].query_text == "op={operation}&lang=en"


def test_value_not_readable_from_source_is_marked():
    assert sent_requests(_Fake, "unknown")[0].query_text == "view=…"


@pytest.mark.parametrize("method, op", [
    ("approve_invoice", "process_invoice"),
    ("reject_invoice", "rejected"),
    ("mark_invoice_in_erp", "mark_in_erp"),
    ("mark_invoice_paid", "paid"),
    ("process_invoice_service", "{operation}"),
])
def test_invoice_wrappers_show_their_op(method, op):
    sent = sent_requests(DOMAINS["Acquisitions"], method)
    assert SentRequest("POST", INVOICE_TEMPLATE, (("op", op),)) in sent


def test_raw_endpoint_lists_each_wrapper_with_its_op():
    wrapped = dict(wrapped_with_query(get_endpoint("POST", INVOICE)))
    assert wrapped["Acquisitions.approve_invoice"] == "op=process_invoice"
    assert wrapped["Acquisitions.process_invoice_service"] == "op={operation}"


# --- allowed values -------------------------------------------------------------

def test_every_choice_is_a_real_query_parameter():
    params = {(ep.method, ep.short_path, p.name)
              for ep in load_endpoints() for p in ep.query_params}
    assert set(PARAM_CHOICES) <= params, set(PARAM_CHOICES) - params


def test_invoice_op_choices_match_the_definition():
    ep = get_endpoint("POST", INVOICE)
    choices = param_choices("POST", ep.short_path, "op")
    assert choices == ("mark_in_erp", "paid", "process_invoice", "rejected")
    op_help = next(p.description for p in ep.query_params if p.name == "op")
    assert all(f"'{c}'" in op_help for c in choices)


# --- search and labels ----------------------------------------------------------

def test_search_by_op_value_finds_method_and_endpoint():
    from almaapitk.lab.app.operations import _op_haystack, _raw_haystack

    assert "process_invoice" in _op_haystack(find_operation("Acquisitions.approve_invoice"))
    assert "process_invoice" in _raw_haystack(get_endpoint("POST", INVOICE))
    assert "process_invoice" not in _raw_haystack(get_endpoint("GET", INVOICE))


def test_label_keeps_distinguishing_tail():
    from almaapitk.lab.app.operations import compact_path, raw_label

    ep = get_endpoint("GET", "/almaws/v1/acq/invoices/{invoice_id}/lines/{invoice_line_id}")
    assert compact_path(ep) == "/acq/invoices/{}/lines/{}"
    # six methods send six different ops: the label names none of them as "the" one
    assert "almaapitk methods" in str(raw_label(get_endpoint("POST", INVOICE)))
    assert "→ BibliographicRecords." in str(raw_label(get_endpoint("GET", "/almaws/v1/bibs/{mms_id}")))


# --- the app --------------------------------------------------------------------

pytest.importorskip("textual")

from textual.widgets import Input, Select  # noqa: E402

from almaapitk.lab.app.app import LabApp  # noqa: E402
from almaapitk.lab.app.inputs import InputsPane  # noqa: E402
from almaapitk.lab.runner import Session  # noqa: E402


@pytest.fixture
def make_app(lab_client, monkeypatch, tmp_path):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)
    return lambda: LabApp(Session("SANDBOX", evidence_dir=tmp_path / "ev"))


def _run(app, scenario):
    async def main():
        async with app.run_test(size=(140, 40)) as pilot:
            await scenario(pilot)
    asyncio.run(main())


def test_method_form_says_what_it_sends(make_app):
    async def scenario(pilot):
        pilot.app.select_operation("Acquisitions.approve_invoice")
        await pilot.pause()
        title = str(pilot.app.query_one("#inputs-title").render())
        assert "sends POST /acq/invoices/{invoice_id}?op=process_invoice" in title
        assert pilot.app.query("#open-raw")
    _run(make_app(), scenario)


def test_raw_op_is_a_dropdown(make_app):
    async def scenario(pilot):
        pilot.app.select_endpoint("POST", INVOICE)
        await pilot.pause()
        op = pilot.app.query_one("#raw-query-op", Select)
        assert op.is_blank()
        op.value = "process_invoice"
        pilot.app.query_one("#raw-path-invoice_id", Input).value = "<invoice_id>"
        await pilot.pause()
        req = pilot.app.query_one(InputsPane).raw_request(with_body=False)
        assert req.query["op"] == "process_invoice"
    _run(make_app(), scenario)


def test_open_in_raw_carries_values_and_sends_nothing(make_app, lab_client):
    async def scenario(pilot):
        app = pilot.app
        app.select_operation("Acquisitions.approve_invoice")
        await pilot.pause()
        app.query_one("#field-invoice_id", Input).value = "<invoice_id>"
        app.action_open_raw()
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.current_endpoint.key == f"POST {INVOICE}"
        assert app.query_one("#raw-path-invoice_id", Input).value == "<invoice_id>"
        assert app.query_one("#raw-query-op", Select).value == "process_invoice"
        assert lab_client.http.calls == []
    _run(make_app(), scenario)


def test_open_in_raw_fills_op_from_the_generic_methods_input(make_app):
    async def scenario(pilot):
        app = pilot.app
        app.select_operation("Acquisitions.process_invoice_service")
        await pilot.pause()
        app.query_one("#field-invoice_id", Input).value = "<invoice_id>"
        app.query_one("#field-operation", Input).value = "paid"
        app.action_open_raw()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.query_one("#raw-query-op", Select).value == "paid"
    _run(make_app(), scenario)


def test_recorded_value_outside_the_choices_is_kept(make_app):
    async def scenario(pilot):
        app = pilot.app
        app.select_endpoint("POST", INVOICE)
        await pilot.pause()
        pane = app.query_one(InputsPane)
        pane.set_raw_values({"path": {"invoice_id": "<invoice_id>"},
                             "query": {"op": "some_new_op"}}, [])
        await pilot.pause()
        assert app.query_one("#raw-query-op", Select).value == "some_new_op"
    _run(make_app(), scenario)
