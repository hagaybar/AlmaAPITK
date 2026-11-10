"""Confirmation before each write. Production needs the operation name typed."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class ConfirmWrite(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, method: str, url: str, body: str | None, op_name: str, production: bool):
        super().__init__()
        self.method, self.url, self.body = method, url, body
        self.op_name, self.production = op_name, production

    def compose(self) -> ComposeResult:
        env = "PRODUCTION" if self.production else "Sandbox"
        body = (self.body or "(no body)")
        body = body if len(body) <= 1500 else body[:1500] + " …"
        with Vertical(id="confirm-box"):
            yield Static(f"[b]Send this write to {env}?[/b]", id="confirm-title")
            yield Static(f"{self.method} {self.url}", markup=False)
            yield Static(body, id="confirm-body", markup=False)
            if self.production:
                yield Static(f"Type [b]{self.op_name}[/b] and press Enter to send. Esc cancels.")
                yield Input(placeholder=self.op_name, id="confirm-word")
            else:
                with Horizontal(id="confirm-buttons"):
                    yield Button("Send", id="confirm-send", variant="warning")
                    yield Button("Cancel (Esc)", id="confirm-cancel")

    def on_mount(self) -> None:
        self.query_one("#confirm-word" if self.production else "#confirm-send").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() == self.op_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-send")

    def action_cancel(self) -> None:
        self.dismiss(False)
