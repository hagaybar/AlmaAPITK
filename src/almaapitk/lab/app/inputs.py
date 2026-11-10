"""Inputs pane: a form built from the selected operation's parameters."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from almaapitk.lab.catalog import Operation


class InputsPane(VerticalScroll):
    """Fields for the current operation; scrolls inside itself."""

    def compose(self) -> ComposeResult:
        yield Static("Pick an operation on the left.", id="inputs-title")

    def on_mount(self) -> None:
        self.border_title = "Inputs"

    async def load(self, op: Operation) -> None:
        self.query_one("#inputs-title", Static).update(f"[b]{op.qualname}[/b]")
