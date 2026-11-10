"""Inputs pane: a form built from the selected operation's parameters,
or from a raw Alma endpoint's definition (see ``load_raw``)."""
from __future__ import annotations

import json
from typing import Any

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Select, Static, TextArea

from almaapitk.lab.catalog import Operation, Param
from almaapitk.lab.endpoints import (
    METHODS,
    Endpoint,
    EndpointParam,
    custom_endpoint,
    get_twin,
    wrapped_by,
)
from almaapitk.lab.runner import InputError, RawRequest, coerce_query

LOCKED_BODY_NOTE = "Fill the path fields, then load the current record"
HELP_CHARS = 240


class InputsPane(VerticalScroll):
    """Fields for the current operation; scrolls inside itself."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.operation: Operation | None = None
        self.endpoint: Endpoint | None = None

    def compose(self) -> ComposeResult:
        yield Static("Pick an operation on the left.", id="inputs-title")

    def on_mount(self) -> None:
        self.border_title = "Inputs"

    async def load(self, op: Operation) -> None:
        """Rebuild the form for ``op``."""
        self.operation, self.endpoint = op, None
        await self.remove_children()
        widgets: list = [Static(self._title(op), id="inputs-title")]
        for p in op.params:
            widgets.extend(self._field(p))
        widgets.extend(self._send_section(op.writes, disabled=not op.sendable))
        await self.mount_all(widgets)
        self.scroll_home(animate=False)

    @staticmethod
    def _send_section(writes: bool, disabled: bool) -> list:
        """Expect and Send, the same for typed operations and raw endpoints."""
        return [
            Static("Expect (one check per line, optional)", classes="field-label"),
            TextArea("", id="expect", soft_wrap=True),
            Static("", id="error-expect", classes="field-error"),
            Button("Send (write)" if writes else "Send", id="send",
                   variant="warning" if writes else "primary", disabled=disabled),
        ]

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
                              value=value if value in options else Select.NULL))
        else:
            out.append(Input(str(default), id=f"field-{p.name}", placeholder=p.help[:60]))
        if p.help:
            out.append(Static(p.help, classes="field-help"))
        out.append(Static("", id=f"error-{p.name}", classes="field-error"))
        return out

    # raw endpoints ------------------------------------------------------------
    @property
    def needs_baseline(self) -> bool:
        """A PUT whose path has a GET: the body starts from the current record."""
        ep = self.endpoint
        return bool(ep and ep.method == "PUT" and not ep.custom and get_twin(ep) is not None)

    async def load_raw(self, endpoint: Endpoint) -> None:
        """Rebuild the form for one Alma endpoint (or the custom path form)."""
        self.operation, self.endpoint = None, endpoint
        await self.remove_children()
        widgets: list = [Static(self._raw_title(endpoint), id="inputs-title")]
        if endpoint.custom:
            widgets.extend(self._custom_fields())
        else:
            for p in endpoint.path_params:
                widgets.extend(self._raw_field(p, "path"))
            for p in endpoint.query_params:
                widgets.extend(self._raw_field(p, "query"))
            if len(endpoint.body_formats) > 1:
                widgets.extend(self._format_field(self._default_format(endpoint)))
            if endpoint.body_formats:
                widgets.extend(self._body_section(endpoint))
        writes = endpoint.writes or endpoint.custom
        widgets.extend(self._send_section(writes, disabled=self.needs_baseline))
        await self.mount_all(widgets)
        self.scroll_home(animate=False)

    @staticmethod
    def _raw_title(ep: Endpoint) -> str:
        if ep.custom:
            return ("[b]RAW  custom path[/b]\n[dim]For a path the Alma API definitions lack "
                    "(e.g. task lists). Nothing is checked against a definition.[/dim]")
        lines = [f"[b]RAW  {ep.method} {escape(ep.path)}[/b]"]
        if ep.summary:
            lines.append(f"[dim]{escape(ep.summary)}[/dim]")
        fetched = (ep.source_fetched or "")[:10] or "date unknown"
        lines.append(f"[dim]from Alma API definitions, {fetched}[/dim]")
        wrapped = wrapped_by(ep)
        lines.append(f"almaapitk: {', '.join(wrapped)}" if wrapped
                     else "[dim]No almaapitk method for this yet[/dim]")
        return "\n".join(lines)

    @staticmethod
    def _raw_field(p: EndpointParam, where: str) -> list:
        star = " *" if p.required else ""
        out: list = [
            Static(f"{escape(p.name)}{star}  [dim]{escape(p.type)} · {where}[/dim]",
                   classes="field-label"),
            Input(p.default or "", id=f"raw-{where}-{p.name}"),
        ]
        if p.description:
            text = p.description if len(p.description) <= HELP_CHARS else p.description[:HELP_CHARS] + " …"
            out.append(Static(text, classes="field-help", markup=False))
        out.append(Static("", id=f"error-{where}-{p.name}", classes="field-error"))
        return out

    @staticmethod
    def _default_format(ep: Endpoint) -> str:
        return ep.body_formats[0] if ep.body_formats else "json"

    @staticmethod
    def _format_field(value: str) -> list:
        return [
            Static("format", classes="field-label"),
            Select([("JSON", "json"), ("XML", "xml")], id="raw-format", allow_blank=False,
                   value=value),
            Static("", id="error-format", classes="field-error"),
        ]

    def _body_section(self, ep: Endpoint) -> list:
        """The body editor; locked for an update until the current record is loaded."""
        locked = self.needs_baseline
        text = "" if locked or ep.method != "POST" else (ep.body_example or "")
        out: list = [
            Static("body *" if not ep.custom else "body  [dim]POST and PUT only[/dim]",
                   classes="field-label"),
            TextArea(text, id="raw-body", language=self._default_format(ep), read_only=locked,
                     soft_wrap=True),
        ]
        if locked:
            out.append(Static(LOCKED_BODY_NOTE, id="raw-body-note", classes="field-help"))
        out.append(Static("", id="error-body", classes="field-error"))
        return out

    def _custom_fields(self) -> list:
        return [
            Static("method *", classes="field-label"),
            Select([(m, m) for m in METHODS], id="raw-method", allow_blank=False, value="GET"),
            Static("", id="error-method", classes="field-error"),
            Static("path *", classes="field-label"),
            Input("", id="raw-custom-path", placeholder="almaws/v1/task-lists/..."),
            Static("The concrete path, values filled in; query parameters go below.",
                   classes="field-help"),
            Static("", id="error-custom-path", classes="field-error"),
            Static("query  [dim]name=value, one per line[/dim]", classes="field-label"),
            TextArea("", id="raw-custom-query", soft_wrap=True),
            Static("", id="error-custom-query", classes="field-error"),
            *self._format_field("json"),
            *self._body_section(custom_endpoint("POST", "custom")),
        ]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "raw-format" and not event.select.is_blank():
            for body in self.query("#raw-body"):
                body.language = str(event.value)

    def raw_request(self) -> RawRequest:
        """The form as a ``RawRequest``; ``InputError.field`` is the field id after ``raw-``."""
        ep = self.endpoint
        if ep is None:
            raise InputError("endpoint", "pick an endpoint first")
        if ep.custom:
            return self._custom_request()
        path: dict[str, str] = {}
        for p in ep.path_params:
            path[p.name] = self._text(f"#raw-path-{p.name}").strip()
            if not path[p.name]:
                raise InputError(f"path-{p.name}", "is required")
        query: dict[str, str] = {}
        for p in ep.query_params:
            query[p.name] = self._text(f"#raw-query-{p.name}")
            try:
                coerce_query(ep, {p.name: query[p.name]})
            except InputError as exc:
                raise InputError(f"query-{p.name}", exc.message) from None
        return RawRequest(endpoint=ep, path_params=path, query=query, body=self._body(),
                          fmt=self._format(ep))

    def _custom_request(self) -> RawRequest:
        method = self._text("#raw-method")
        if method not in METHODS:
            raise InputError("method", "pick a method")
        path = self._text("#raw-custom-path").strip()
        if not path:
            raise InputError("custom-path", "is required")
        if "?" in path:
            raise InputError("custom-path", "put query parameters in the query box below")
        if "{" in path:
            raise InputError("custom-path", "type the concrete path, values filled in")
        try:
            ep = custom_endpoint(method, path)
        except ValueError as exc:
            raise InputError("custom-path", str(exc)) from None
        query: dict[str, str] = {}
        for line in self._text("#raw-custom-query").splitlines():
            if not line.strip():
                continue
            name, sep, value = line.partition("=")
            if not sep or not name.strip():
                raise InputError("custom-query", f"use name=value, one per line (not {line.strip()!r})")
            query[name.strip()] = value.strip()
        body = self._body() if method in ("POST", "PUT") else None
        return RawRequest(endpoint=ep, path_params={}, query=query, body=body,
                          fmt=self._format(ep))

    def _text(self, selector: str) -> str:
        widget = self.query_one(selector)
        if isinstance(widget, Input):
            return widget.value
        if isinstance(widget, TextArea):
            return widget.text
        if isinstance(widget, Select):
            return "" if widget.is_blank() else str(widget.value)
        return ""

    def _body(self) -> str | None:
        matches = self.query("#raw-body")
        if not matches or matches.first().read_only:
            return None
        return matches.first().text or None

    def _format(self, ep: Endpoint) -> str:
        if self.query("#raw-format"):
            return self._text("#raw-format") or "json"
        return self._default_format(ep)

    def set_raw_values(self, inputs: dict[str, Any], expectations: list[str],
                       custom: tuple[str, str] | None = None) -> None:
        """Fill the raw form from a record's ``inputs``; ``custom`` is ``(method, path)``."""
        if custom is not None:
            method, path = custom
            self.query_one("#raw-method", Select).value = method
            self.query_one("#raw-custom-path", Input).value = path
            self.query_one("#raw-custom-query", TextArea).text = "\n".join(
                f"{k}={_text_value(v)}" for k, v in (inputs.get("query") or {}).items())
        for where in ("path", "query"):
            for name, value in (inputs.get(where) or {}).items():
                for widget in self.query(f"#raw-{where}-{name}"):
                    widget.value = _text_value(value)
        if inputs.get("format") in ("json", "xml") and self.query("#raw-format"):
            self.query_one("#raw-format", Select).value = inputs["format"]
        body = self.query("#raw-body")
        if body and not body.first().read_only and inputs.get("body"):
            body.first().text = inputs["body"]
        self.query_one("#expect", TextArea).text = "\n".join(expectations)

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
                out[p.name] = "" if widget.is_blank() else str(widget.value)
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
        prefix = "raw" if self.endpoint is not None else "field"
        candidates = [field] + ([f"path-{field}", f"query-{field}"] if prefix == "raw" else [])
        for name in candidates:
            matches = self.query(f"#error-{name}")
            if matches:
                matches.first().update(message)
                target = self.query(f"#{prefix}-{name}")
                if target and target.first().focusable:
                    target.first().focus()
                return
        self.query_one("#error-expect", Static).update(f"{field}: {message}")

    def clear_errors(self) -> None:
        for widget in self.query(".field-error"):
            widget.update("")


def _text_value(value: Any) -> str:
    """A recorded (typed) value back as form text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
