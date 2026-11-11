"""Inputs pane: a form built from the selected operation's parameters,
or from a raw Alma endpoint's definition (see ``load_raw``).

An update (a PUT whose path also has a GET) starts from the current record: the
body stays locked until **Load current record** has fetched it, and Send stays
disabled until that baseline matches the path values, baseline query and format
on the form. Changing any of them clears it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
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
from almaapitk.lab.evidence import EvidenceRecord
from almaapitk.lab.normalize import looks_like_xml
from almaapitk.lab.runner import InputError, RawRequest, coerce_query

LOCKED_BODY_NOTE = "Fill the path fields, then load the current record"
CHANGED_NOTE = "Path, baseline query or format changed: load the current record again"
STALE_NOTE = ("The record changed since you loaded it: load it again. "
              "Your edit is kept below under \"Your previous edit\"")
PREVIOUS_EDIT_LABEL = "Your previous edit  [dim]read-only: re-apply it to the new version[/dim]"
FAILED_NOTE = "The current record could not be loaded ({status}): nothing to start from"
LOADED_NOTE = "Edit the current record; Send checks it has not changed meanwhile"
HELP_CHARS = 240


class InputsPane(VerticalScroll):
    """Fields for the current operation; scrolls inside itself."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.operation: Operation | None = None
        self.endpoint: Endpoint | None = None
        self.twin: Endpoint | None = None  # the GET an update starts from
        self.baseline: EvidenceRecord | None = None
        self._baseline_key: tuple | None = None
        self._bq_follows: dict[str, bool] = {}  # baseline query field follows the PUT's
        self._example: tuple[str, str] | None = None  # (format, text) of a POST example

    def compose(self) -> ComposeResult:
        yield Static("Pick an operation on the left.", id="inputs-title")

    def on_mount(self) -> None:
        self.border_title = "Inputs"

    async def load(self, op: Operation) -> None:
        """Rebuild the form for ``op``."""
        self.operation, self.endpoint, self.twin = op, None, None
        self.baseline = self._baseline_key = None
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
        return self.twin is not None

    async def load_raw(self, endpoint: Endpoint) -> None:
        """Rebuild the form for one Alma endpoint (or the custom path form)."""
        self.operation, self.endpoint = None, endpoint
        self.twin = (get_twin(endpoint)
                     if endpoint.method == "PUT" and not is_free_form(endpoint) else None)
        self.baseline = self._baseline_key = None
        self._bq_follows, self._example = {}, None
        await self.remove_children()
        widgets: list = [Static(self._raw_title(endpoint), id="inputs-title")]
        if is_free_form(endpoint):
            widgets.extend(self._custom_fields())
        else:
            for p in endpoint.path_params:
                widgets.extend(self._raw_field(p, "path"))
            for p in endpoint.query_params:
                widgets.extend(self._raw_field(p, "query"))
            if len(endpoint.body_formats) > 1:
                widgets.extend(self._format_field(self._default_format(endpoint)))
            if self.twin is not None:
                widgets.extend(self._baseline_section(endpoint, self.twin))
            if endpoint.body_formats:
                widgets.extend(self._body_section(endpoint))
        writes = endpoint.writes or endpoint.custom
        widgets.extend(self._send_section(writes, disabled=self.needs_baseline))
        await self.mount_all(widgets)
        self.scroll_home(animate=False)

    @staticmethod
    def _raw_title(ep: Endpoint) -> str:
        if is_free_form(ep):
            return ("[b]RAW  custom path[/b]\n[dim]For a path the Alma API definitions lack "
                    "(e.g. task lists). Nothing is checked against a definition.[/dim]")
        lines = [f"[b]RAW  {ep.method} {escape(ep.path)}[/b]"]
        if ep.summary:
            lines.append(f"[dim]{escape(ep.summary)}[/dim]")
        fetched = (ep.source_fetched or "")[:10] or "date unknown"
        if ep.custom:  # a custom update on a path whose GET is defined
            lines.append(f"[dim]custom update: the GET on this path is from Alma API definitions, "
                         f"{fetched}[/dim]")
            return "\n".join(lines)
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

    def _baseline_section(self, ep: Endpoint, twin: Endpoint) -> list:
        """The GET's own query fields (prefilled from same-named PUT fields) and the load button."""
        put_defaults = {p.name: p.default or "" for p in ep.query_params}
        out: list = [Static("[b]Baseline[/b]  [dim]the GET the update starts from: "
                            f"GET {escape(twin.short_path)}[/dim]", classes="field-label")]
        for p in twin.query_params:
            follows = p.name in put_defaults
            self._bq_follows[p.name] = follows
            value = put_defaults[p.name] if follows else (p.default or "")
            out.append(Static(f"{escape(p.name)}  [dim]{escape(p.type)} · baseline query[/dim]",
                              classes="field-label"))
            out.append(Input(value, id=f"raw-bq-{p.name}"))
            out.append(Static("", id=f"error-bq-{p.name}", classes="field-error"))
        out.append(Button("Load current record", id="load-baseline"))
        out.append(Static("", id="error-baseline", classes="field-error"))
        return out

    def _body_section(self, ep: Endpoint) -> list:
        """The body editor; locked for an update until the current record is loaded."""
        locked = self.needs_baseline
        fmt = self._default_format(ep)
        text = ""
        if ep.method == "POST" and ep.body_example:
            self._example = ("xml" if looks_like_xml(ep.body_example) else "json", ep.body_example)
            text = ep.body_example if self._example[0] == fmt else ""
        out: list = [
            Static("body  [dim]POST and PUT only[/dim]" if is_free_form(ep) else "body *",
                   classes="field-label"),
            TextArea(text, id="raw-req-body", language=fmt, read_only=locked, soft_wrap=True),
            Static(LOCKED_BODY_NOTE if locked else "", id="raw-body-note", classes="field-help"),
            Button("Load from file", id="body-from-file"),
            Button("Load from earlier response", id="body-from-last"),
            Static("", id="error-body", classes="field-error"),
        ]
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
            Button("Load from GET", id="body-from-get"),
            Static("POST and PUT: GET the same path and start the body from its response "
                   "(nothing is enforced on a custom path).", classes="field-help"),
        ]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "raw-format" and not event.select.is_blank():
            fmt = str(event.value)
            for body in self.query("#raw-req-body"):
                body.language = fmt
                if self._example is not None:  # an untouched example shows only in its format
                    ex_fmt, ex_text = self._example
                    if fmt != ex_fmt and body.text == ex_text:
                        body.text = ""
                    elif fmt == ex_fmt and body.text == "":
                        body.text = ex_text
            self._check_baseline()

    def on_input_changed(self, event: Input.Changed) -> None:
        wid = event.input.id or ""
        if wid.startswith("raw-query-") and self.twin is not None:
            name = wid.removeprefix("raw-query-")
            if self._bq_follows.get(name):
                for bq in self.query(f"#raw-bq-{name}"):
                    bq.value = event.value
        elif wid.startswith("raw-bq-"):
            name = wid.removeprefix("raw-bq-")
            if name in self._bq_follows:  # follows again once it equals the PUT's value
                put = self.query(f"#raw-query-{name}")
                self._bq_follows[name] = bool(put) and put.first().value == event.value
        if wid.startswith(("raw-path-", "raw-bq-")):
            self._check_baseline()

    # baseline ---------------------------------------------------------------
    def baseline_key(self) -> tuple:
        """What a baseline must match: path values, baseline query and format."""
        ep = self.endpoint
        path = tuple((p.name, self._text(f"#raw-path-{p.name}").strip())
                     for p in (ep.path_params if ep else ()))
        bq = tuple((p.name, self._text(f"#raw-bq-{p.name}").strip())
                   for p in (self.twin.query_params if self.twin else ()))
        return path, bq, self._format(ep) if ep else "json"

    def baseline_request(self) -> RawRequest:
        """The update's request as far as the baseline GET needs it (body not required)."""
        return self.raw_request(with_body=False)

    def accept_baseline(self, record: EvidenceRecord, key: tuple) -> bool:
        """Start the update from ``record`` if it loaded and the form still matches ``key``."""
        if self.twin is None:
            return False
        status = record.last_status
        if record.error or status is None or not 200 <= status < 300:
            self.clear_baseline(FAILED_NOTE.format(status=status or "no response"))
            return False
        if key != self.baseline_key():
            self.clear_baseline(CHANGED_NOTE)
            return False
        sent = [r for r in record.requests if r.sent]
        self.baseline, self._baseline_key = record, key
        body = self.query_one("#raw-req-body", TextArea)
        body.text = editable_body((sent[-1].response_body or "") if sent else "", key[2])
        body.read_only = False
        self.query_one("#raw-body-note", Static).update(LOADED_NOTE)
        self.query_one("#send", Button).disabled = False
        return True

    def clear_baseline(self, note: str = LOCKED_BODY_NOTE) -> None:
        """Forget the baseline: body locked, Send disabled until the record is loaded again."""
        if self.twin is None:
            return
        self.baseline = self._baseline_key = None
        for body in self.query("#raw-req-body"):
            body.read_only = True
        for widget in self.query("#raw-body-note"):
            widget.update(note)
        for widget in self.query("#send"):
            widget.disabled = True

    def keep_previous_edit(self, text: str) -> None:
        """Show the body of a refused update read-only, so a reload does not lose it."""
        existing = self.query("#raw-prev-edit")
        if existing:
            existing.first().text = text
            return
        anchor = self.query("#raw-body-note")
        if not anchor:
            return
        self.mount(Static(PREVIOUS_EDIT_LABEL, classes="field-label"),
                   TextArea(text, id="raw-prev-edit", read_only=True, soft_wrap=True,
                            language=self._format(self.endpoint) if self.endpoint else "json"),
                   after=anchor.first())

    def _check_baseline(self) -> None:
        if self.baseline is not None and self.baseline_key() != self._baseline_key:
            self.clear_baseline(CHANGED_NOTE)

    @property
    def body_editable(self) -> bool:
        """A body editor exists and is not locked waiting for a baseline."""
        matches = self.query("#raw-req-body")
        return bool(matches) and not matches.first().read_only

    def set_body(self, text: str) -> bool:
        """Replace the body text; refused while an update's body is locked."""
        if not self.body_editable:
            return False
        self.query_one("#raw-req-body", TextArea).text = text
        return True

    def raw_request(self, with_body: bool = True) -> RawRequest:
        """The form as a ``RawRequest``; ``InputError.field`` is the field id after ``raw-``."""
        ep = self.endpoint
        if ep is None:
            raise InputError("endpoint", "pick an endpoint first")
        if is_free_form(ep):
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
        baseline_query: dict[str, str] = {}
        for p in (self.twin.query_params if self.twin else ()):
            baseline_query[p.name] = self._text(f"#raw-bq-{p.name}").strip()
            try:
                coerce_query(self.twin, {p.name: baseline_query[p.name]})
            except InputError as exc:
                raise InputError(f"bq-{p.name}", exc.message) from None
        return RawRequest(endpoint=ep, path_params=path, query=query,
                          body=self._body() if with_body else None, fmt=self._format(ep),
                          baseline_query=baseline_query)

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
        matches = self.query("#raw-req-body")
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
        for name, value in (inputs.get("baseline_query") or {}).items():
            for widget in self.query(f"#raw-bq-{name}"):
                widget.value = _text_value(value)
                put = self.query(f"#raw-query-{name}")
                self._bq_follows[name] = bool(put) and put.first().value == widget.value
        # an update's old body is not restored: it could be stale; load a fresh baseline
        body = self.query("#raw-req-body")
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
        candidates = [field] + ([f"path-{field}", f"query-{field}", f"bq-{field}"]
                                if prefix == "raw" else [])
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


def is_free_form(ep: Endpoint) -> bool:
    """The custom path form (method and path typed in), not a form built from a definition."""
    return ep.custom and not ep.path


def editable_body(text: str, fmt: str) -> str:
    """A response body as the update's starting text (JSON indented for editing)."""
    if fmt == "json":
        try:
            return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except ValueError:
            pass
    return text


class BodyFilePrompt(ModalScreen[Optional[str]]):
    """Asks for a file path; returns the file's UTF-8 text, or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static("[b]Load the body from a file[/b]")
            yield Static("Type the file path and press Enter. Esc cancels.")
            yield Input(placeholder="path/to/body.json", id="body-file-path")
            yield Static("", id="body-file-error", classes="field-error")

    def on_mount(self) -> None:
        self.query_one("#body-file-path").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        path = Path(event.value.strip()).expanduser()
        try:
            self.dismiss(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as exc:
            self.query_one("#body-file-error", Static).update(f"Cannot read {path}: {exc}")

    def action_cancel(self) -> None:
        self.dismiss(None)


def _text_value(value: Any) -> str:
    """A recorded (typed) value back as form text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
