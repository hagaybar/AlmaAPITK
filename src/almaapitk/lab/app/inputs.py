"""Inputs pane: a form built from the selected operation's parameters."""
from __future__ import annotations

import json
from typing import Any

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Select, Static, TextArea

from almaapitk.lab.catalog import Operation, Param


class InputsPane(VerticalScroll):
    """Fields for the current operation; scrolls inside itself."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.operation: Operation | None = None

    def compose(self) -> ComposeResult:
        yield Static("Pick an operation on the left.", id="inputs-title")

    def on_mount(self) -> None:
        self.border_title = "Inputs"

    async def load(self, op: Operation) -> None:
        """Rebuild the form for ``op``."""
        self.operation = op
        await self.remove_children()
        widgets: list = [Static(self._title(op), id="inputs-title")]
        for p in op.params:
            widgets.extend(self._field(p))
        widgets.append(Static("Expect (one check per line, optional)", classes="field-label"))
        widgets.append(TextArea("", id="expect", soft_wrap=True))
        widgets.append(Static("", id="error-expect", classes="field-error"))
        label = "Send (write)" if op.writes else "Send"
        widgets.append(Button(label, id="send", variant="warning" if op.writes else "primary",
                              disabled=not op.sendable))
        await self.mount_all(widgets)
        self.scroll_home(animate=False)

    @staticmethod
    def _title(op: Operation) -> str:
        verbs = ",".join(sorted(op.verbs)) or "no request"
        lines = [f"[b]{op.qualname}[/b]  [dim]{verbs}[/dim]"]
        if op.multi_write:
            lines.append("[b $warning]Writes more than once: each write is confirmed.[/]")
        if not op.sendable:
            lines.append("[b $error]A required input cannot be set in the lab.[/]")
        if op.summary:
            lines.append(f"[dim]{op.summary}[/dim]")
        return "\n".join(lines)

    def _field(self, p: Param) -> list:
        star = " *" if p.required else ""
        out: list = [Static(f"{p.name}{star}  [dim]{p.annotation}[/dim]", classes="field-label")]
        default = "" if p.default is None else p.default
        if p.kind == "unsupported":
            out.append(Static("not settable in the lab", classes="unsupported", id=f"field-{p.name}"))
        elif p.kind == "json":
            text = "" if default == "" else json.dumps(default, ensure_ascii=False, indent=1)
            out.append(TextArea(text, id=f"field-{p.name}", language="json"))
        elif p.kind in ("choice", "bool"):
            options = list(p.choices) if p.kind == "choice" else ["true", "false"]
            value = str(default).lower() if p.kind == "bool" and default != "" else str(default)
            out.append(Select([(o, o) for o in options], id=f"field-{p.name}", allow_blank=True,
                              value=value if value in options else Select.BLANK))
        else:
            out.append(Input(str(default), id=f"field-{p.name}", placeholder=p.help[:60]))
        if p.help:
            out.append(Static(p.help, classes="field-help"))
        out.append(Static("", id=f"error-{p.name}", classes="field-error"))
        return out

    # values -----------------------------------------------------------------
    def values(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.operation is None:
            return out
        for p in self.operation.params:
            if p.kind == "unsupported":
                continue
            widget = self.query_one(f"#field-{p.name}")
            if isinstance(widget, Input):
                out[p.name] = widget.value
            elif isinstance(widget, TextArea):
                out[p.name] = widget.text
            elif isinstance(widget, Select):
                out[p.name] = "" if widget.value is Select.BLANK else str(widget.value)
        return out

    def expectations(self) -> list[str]:
        return [line.strip() for line in self.query_one("#expect", TextArea).text.splitlines() if line.strip()]

    def set_values(self, inputs: dict[str, Any], expectations: list[str]) -> None:
        for name, value in inputs.items():
            matches = self.query(f"#field-{name}")
            if not matches:
                continue
            widget = matches.first()
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            if isinstance(widget, Input):
                widget.value = text
            elif isinstance(widget, TextArea):
                widget.text = text
            elif isinstance(widget, Select):
                text = text.lower() if isinstance(value, bool) else text
                widget.value = text
        self.query_one("#expect", TextArea).text = "\n".join(expectations)

    def show_error(self, field: str, message: str) -> None:
        self.clear_errors()
        matches = self.query(f"#error-{field}")
        if matches:
            matches.first().update(message)
            target = self.query(f"#field-{field}")
            if target and target.first().focusable:
                target.first().focus()
        else:
            self.query_one("#error-expect", Static).update(f"{field}: {message}")

    def clear_errors(self) -> None:
        for widget in self.query(".field-error"):
            widget.update("")
