"""ID handles in the app: the picker (Ctrl+O) and the <ask> prompt."""
from __future__ import annotations

from typing import Optional

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from almaapitk.lab.handles import Handles


class HandlePicker(ModalScreen[Optional[str]]):
    """The user IDs this app has shown, each with its handle; Enter picks one."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, handles: Handles):
        super().__init__()
        self.items = handles.items()

    def compose(self) -> ComposeResult:
        yield Static(f"[b]User ID handles[/b]  {len(self.items)}  ·  Enter inserts the handle  ·  "
                     "Esc closes  ·  kept in memory only, while the app is open", id="handles-title")
        yield OptionList(*[Option(Text(f"{handle:<6} {real}"), id=handle)
                           for handle, real in self.items], id="handles-list")

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        if self.items:
            options.highlighted = 0
        options.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_close(self) -> None:
        self.dismiss(None)


class AskValue(ModalScreen[Optional[str]]):
    """The value for an ``<ask>`` field: sent, shown in the confirmation, never saved."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, field: str):
        super().__init__()
        self.field = field

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static(f"[b]Value for {escape(self.field)}[/b] (<ask>)", markup=True, id="ask-title")
            yield Static("Not echoed. Sent to Alma and shown in the confirmation; never saved. "
                         "Enter continues, Esc cancels (nothing is sent).", markup=False)
            yield Input(password=True, id="ask-value")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value or None)

    def action_cancel(self) -> None:
        self.dismiss(None)
