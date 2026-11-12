"""Alma Lab app shell: layout, operations tree, bars (issue #230)."""
import asyncio

import pytest

pytest.importorskip("textual")

from almaapitk.lab.app.app import LabApp  # noqa: E402
from almaapitk.lab.runner import Session  # noqa: E402


@pytest.fixture
def make_app(lab_client, monkeypatch, tmp_path):
    monkeypatch.setattr("almaapitk.lab.runner.make_lab_client", lambda env: lab_client)

    def factory(env="SANDBOX"):
        return LabApp(Session(env, evidence_dir=tmp_path / "ev"))
    return factory


def _run(app, scenario):
    async def main():
        async with app.run_test(size=(120, 30)) as pilot:
            await scenario(pilot)
    asyncio.run(main())


def test_three_panes_present(make_app):
    async def scenario(pilot):
        app = pilot.app
        for pane in ("#operations", "#inputs", "#result"):
            assert app.query_one(pane).display
        assert "almaapitk" in str(app.query_one("#topbar").render())
        assert "SANDBOX" in str(app.query_one("#topbar").render())
    _run(make_app(), scenario)


def test_production_banner_class(make_app):
    async def scenario(pilot):
        assert pilot.app.query_one("#topbar").has_class("-production")
        assert "PRODUCTION" in str(pilot.app.query_one("#topbar").render())
    _run(make_app("PRODUCTION"), scenario)


def test_search_filters_tree(make_app):
    async def scenario(pilot):
        await pilot.press("slash")
        await pilot.press(*"get_rec")
        await pilot.pause()
        tree = pilot.app.query_one("#op-tree")
        # Raw endpoints match too (by the methods that call them); the domain leaves are ops
        leaves = [n.data.qualname for n in _walk(tree.root) if hasattr(n.data, "qualname")]
        assert "BibliographicRecords.get_record" in leaves
        assert all("get_rec" in q.split(".")[1] for q in leaves)
    _run(make_app(), scenario)


def test_select_operation_loads_it(make_app):
    async def scenario(pilot):
        app = pilot.app
        app.select_operation("BibliographicRecords.get_record")
        await pilot.pause()
        assert app.current_operation.qualname == "BibliographicRecords.get_record"
        assert "BibliographicRecords.get_record" in str(app.query_one("#inputs-title").render())
    _run(make_app(), scenario)


def test_ctrl_arrows_switch_panes(make_app):
    async def scenario(pilot):
        app = pilot.app
        app.select_operation("BibliographicRecords.get_record")
        await pilot.pause()
        app.query_one("#op-tree").focus()
        await pilot.press("ctrl+right")
        assert _inside(app.focused, "inputs")
        await pilot.press("ctrl+right")
        assert _inside(app.focused, "result")
        await pilot.press("ctrl+left")
        assert _inside(app.focused, "inputs")
    _run(make_app(), scenario)


def _inside(widget, pane_id):
    return widget is not None and any(a.id == pane_id for a in widget.ancestors_with_self)


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)
