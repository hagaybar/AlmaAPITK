"""LabApp: three panes (operations | inputs | result) with bars top and bottom."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Input, Static

from almaapitk.lab.app.inputs import InputsPane
from almaapitk.lab.app.operations import OperationsPane
from almaapitk.lab.app.result import ResultPane
from almaapitk.lab.catalog import Operation, find_operation
from almaapitk.lab.runner import Session

PANES = ("operations", "inputs", "result")


class LabApp(App):
    CSS_PATH = "lab.tcss"
    TITLE = "Alma Lab"
    BINDINGS = [
        Binding("slash", "search", "Search", key_display="/"),
        Binding("ctrl+right", "pane(1)", "Next pane", key_display="^→"),
        Binding("ctrl+left", "pane(-1)", "Prev pane", key_display="^←"),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.current_operation: Optional[Operation] = None

    def compose(self) -> ComposeResult:
        yield Static(self._topbar_text(), id="topbar",
                     classes="-production" if self.session.environment == "PRODUCTION" else "")
        with Horizontal(id="panes"):
            yield OperationsPane(id="operations")
            yield InputsPane(id="inputs")
            yield ResultPane(id="result")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#op-tree").focus()

    def _topbar_text(self) -> str:
        try:
            tk = version("almaapitk")
        except PackageNotFoundError:
            tk = "?"
        env = self.session.environment
        warn = "  WRITES NEED A TYPED CONFIRMATION" if env == "PRODUCTION" else ""
        return f" ALMA LAB   almaapitk {tk}   env: {env}{warn}   evidence: {self.session.evidence_dir}"

    # navigation -----------------------------------------------------------
    def action_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_pane(self, step: int) -> None:
        current = self._pane_of(self.focused)
        index = (PANES.index(current) + step) % len(PANES) if current else 0
        pane = self.query_one(f"#{PANES[index]}")
        target = next((w for w in pane.query("*") if w.focusable), None)
        (target or pane).focus()

    @staticmethod
    def _pane_of(widget) -> Optional[str]:
        for node in (widget.ancestors_with_self if widget else ()):
            if node.id in PANES:
                return node.id
        return None

    # operations -----------------------------------------------------------
    def select_operation(self, qualname: str) -> None:
        self.post_message(OperationsPane.Selected(find_operation(qualname)))

    async def on_operations_pane_selected(self, message: OperationsPane.Selected) -> None:
        self.current_operation = message.operation
        await self.query_one(InputsPane).load(message.operation)
