"""Result pane: status line and tabs; scrolls inside itself."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static


class ResultPane(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("No call yet.", id="status-line")
        with VerticalScroll(id="result-scroll"):
            yield Static("", id="result-body")

    def on_mount(self) -> None:
        self.border_title = "Result"
