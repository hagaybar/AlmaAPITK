"""LabApp: three panes (operations | inputs | result) with bars top and bottom."""
from __future__ import annotations

import threading
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable, Optional

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Input, Static, TextArea

from almaapitk.lab.app.confirm import ConfirmWrite
from almaapitk.lab.app.export import ExportScreen
from almaapitk.lab.app.history import HistoryScreen
from almaapitk.lab.app.inputs import STALE_NOTE, BodyFilePrompt, InputsPane
from almaapitk.lab.app.operations import CUSTOM_PATH, OperationsPane
from almaapitk.lab.app.result import ResultPane
from almaapitk.lab.catalog import Operation, find_operation
from almaapitk.lab.endpoints import Endpoint, custom_endpoint, get_endpoint, match
from almaapitk.lab.evidence import EvidenceError, EvidenceRecord, gitignore_status, load_record
from almaapitk.lab.runner import InputError, RawRequest, Session, resolve_path

PANES = ("operations", "inputs", "result")


class LabApp(App):
    CSS_PATH = "lab.tcss"
    TITLE = "Alma Lab"
    BINDINGS = [
        Binding("slash", "search", "Search", key_display="/"),
        Binding("ctrl+right", "pane(1)", "Next pane", key_display="^→", priority=True),
        Binding("ctrl+left", "pane(-1)", "Prev pane", key_display="^←", priority=True),
        Binding("ctrl+s", "send", "Send"),
        Binding("h", "history", "History"),
        Binding("e", "expect", "Expect"),
        Binding("x", "export", "Export"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.session.gate = self._gate
        self.current_operation: Optional[Operation] = None
        self.current_endpoint: Optional[Endpoint] = None
        self.last_record: Optional[EvidenceRecord] = None
        self.last_path: Optional[Path] = None
        self._running_op: Optional[Operation | Endpoint] = None
        self._confirm_word = ""  # what Production asks to be typed for the running call

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
        if gitignore_status(self.session.evidence_dir) == "not-ignored":
            self.notify(f"{self.session.evidence_dir} is not in .gitignore. Evidence holds real IDs: "
                        "add it before committing (R9).", severity="warning", timeout=10)

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

    def select_endpoint(self, method: str, path: str) -> None:
        """Open the raw form for an indexed endpoint (``path`` is the full template)."""
        self.post_message(OperationsPane.Selected(get_endpoint(method, path)))

    def select_custom(self) -> None:
        """Open the custom path form."""
        self.post_message(OperationsPane.Selected(CUSTOM_PATH))

    async def on_operations_pane_selected(self, message: OperationsPane.Selected) -> None:
        chosen = message.operation
        if isinstance(chosen, Endpoint):
            self.current_operation, self.current_endpoint = None, chosen
            await self.query_one(InputsPane).load_raw(chosen)
        else:
            self.current_operation, self.current_endpoint = chosen, None
            await self.query_one(InputsPane).load(chosen)

    # sending ----------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        handlers = {"send": self.action_send, "load-baseline": self.load_baseline,
                    "reload-baseline": self.load_baseline, "body-from-file": self._body_from_file,
                    "body-from-last": self._body_from_last}
        handler = handlers.get(event.button.id or "")
        if handler is not None:
            handler()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        wid = event.input.id or ""
        if wid.startswith("raw-bq-"):
            self.load_baseline()
        elif wid.startswith(("field-", "raw-")):
            self.action_send()

    def _busy(self) -> bool:
        if self._running_op is not None:
            self.notify("A call is still running; wait for its result.", severity="warning")
            return True
        return False

    def action_send(self) -> None:
        if self._busy():
            return
        if self.current_endpoint is not None:
            self._send_raw(self.current_endpoint)
            return
        op = self.current_operation
        if op is None:
            self.notify("Pick an operation first.", severity="warning")
            return
        inputs = self.query_one(InputsPane)
        inputs.clear_errors()
        raw, expect = inputs.values(), inputs.expectations()
        self.query_one("#status-line", Static).update(f"Sending {op.qualname} …")
        self._running_op, self._confirm_word = op, op.name
        self.run_worker(lambda: self._call(lambda: self.session.run(op, raw, expect)),
                        thread=True, group="send")

    def _send_raw(self, ep: Endpoint) -> None:
        inputs = self.query_one(InputsPane)
        inputs.clear_errors()
        if inputs.needs_baseline and inputs.baseline is None:
            self.notify("Load the current record before sending an update.", severity="warning")
            return
        try:
            req = inputs.raw_request()
        except InputError as exc:
            inputs.show_error(exc.field, exc.message)
            self.query_one("#status-line", Static).update("Not sent: fix the input.")
            return
        expect = inputs.expectations()
        if req.endpoint.custom:
            found = match(req.endpoint.method, "/" + resolve_path(req.endpoint, {}))
            if found is not None:  # the index knows it: use its form (and its baseline rule)
                self.run_worker(self._switch_to_indexed(found[0], found[1], req, expect),
                                group="switch")
                return
        baseline = inputs.baseline if inputs.needs_baseline else None
        self.query_one("#status-line", Static).update(
            f"Sending {req.endpoint.method} {req.endpoint.short_path} …")
        self._running_op, self._confirm_word = ep, _confirm_word(req)
        then = (lambda record: self._after_update(inputs, ep, record)) if baseline else None
        self.run_worker(lambda: self._call(lambda: self.session.run_raw(req, expect, baseline=baseline),
                                           then=then),
                        thread=True, group="send")

    async def _switch_to_indexed(self, ep: Endpoint, values: dict[str, str], req: RawRequest,
                                 expect: list[str]) -> None:
        """A custom path the index knows: open its form with the values carried over; send nothing."""
        self.current_operation, self.current_endpoint = None, ep
        pane = self.query_one(InputsPane)
        await pane.load_raw(ep)
        pane.set_raw_values({"path": values, "query": req.query, "format": req.fmt,
                             "body": req.body}, expect)
        known = {p.name for p in ep.query_params}
        dropped = [name for name in req.query if name not in known]
        text = ("This path is in the Alma API definitions; switched to its form so the update "
                "can start from the current record." if pane.needs_baseline else
                "This path is in the Alma API definitions; switched to its form. Check it and send again.")
        if dropped:
            text += f" Not a query parameter there, left out: {', '.join(dropped)}."
        self.query_one("#status-line", Static).update(escape(text))
        self.notify(text, timeout=10)

    def load_baseline(self) -> None:
        """Load current record: the update's GET twin, a read (no confirmation)."""
        if self._busy():
            return
        pane, ep = self.query_one(InputsPane), self.current_endpoint
        if ep is None or not pane.needs_baseline:
            self.notify("Only an update (PUT) starts from the current record.", severity="warning")
            return
        pane.clear_errors()
        try:
            req = pane.baseline_request()
        except InputError as exc:
            pane.show_error(exc.field, exc.message)
            self.query_one("#status-line", Static).update("Not loaded: fix the input.")
            return
        key = pane.baseline_key()
        self.query_one("#status-line", Static).update(
            f"Loading the current record: GET {ep.short_path} …")
        self._running_op = ep

        def accept(record: EvidenceRecord) -> None:
            if pane.endpoint is ep:
                pane.accept_baseline(record, key)
        self.run_worker(lambda: self._call(lambda: self.session.fetch_baseline(req), then=accept),
                        thread=True, group="send")

    def _after_update(self, pane: InputsPane, ep: Endpoint, record: EvidenceRecord) -> None:
        """After an update: a refused one, or one that changed the record, needs a fresh baseline."""
        if pane.endpoint is not ep:
            return
        status = record.last_status
        if record.refused == "baseline changed":
            pane.clear_baseline(STALE_NOTE)
        elif status is not None and 200 <= status < 300 and not record.error:
            pane.clear_baseline("Sent. Load the current record again before another update")

    def _body_from_file(self) -> None:
        pane = self.query_one(InputsPane)
        if not pane.body_editable:
            self.notify("Load the current record first: the update starts from it.", severity="warning")
            return

        def loaded(text: Optional[str]) -> None:
            if text is not None:
                pane.set_body(text)
        self.push_screen(BodyFilePrompt(), callback=loaded)

    def _body_from_last(self) -> None:
        pane = self.query_one(InputsPane)
        sent = [r for r in self.last_record.requests if r.sent] if self.last_record else []
        if not sent or not sent[-1].response_body:
            self.notify("No earlier response body to load.", severity="warning")
            return
        if not pane.set_body(sent[-1].response_body):
            self.notify("Load the current record first: the update starts from it.", severity="warning")

    def _call(self, run: Callable[[], EvidenceRecord],
              then: Optional[Callable[[EvidenceRecord], None]] = None) -> None:
        try:
            record = run()
        except InputError as exc:
            self.call_from_thread(self.query_one(InputsPane).show_error, exc.field, exc.message)
            self.call_from_thread(self.query_one("#status-line", Static).update, "Not sent: fix the input.")
            return
        except EvidenceError as exc:
            self.call_from_thread(self.notify, str(exc), severity="error", timeout=15)
            record = getattr(exc, "record", None)
            if record is not None:  # the call went out; show what came back anyway
                self.call_from_thread(self._show, record, None)
            return
        except Exception as exc:  # credentials, network setup: show, don't crash the app
            self.call_from_thread(self.notify, f"{type(exc).__name__}: {exc}", severity="error", timeout=15)
            return
        finally:
            self._running_op = None
        self.call_from_thread(self._show, record, self.session.last_path)
        if then is not None:
            self.call_from_thread(then, record)

    def _show(self, record: EvidenceRecord, path: Optional[Path]) -> None:
        self.last_record, self.last_path = record, path
        self.query_one(ResultPane).show(record, path)

    def _gate(self, method: str, url: str, body: Optional[str]) -> bool:
        """Called from the send worker before each write; waits for the user."""
        word = self._confirm_word
        answer: list[bool] = []
        done = threading.Event()

        def ask() -> None:
            screen = ConfirmWrite(method, url, body, word,
                                  production=self.session.environment == "PRODUCTION")
            self.push_screen(screen, callback=lambda ok: (answer.append(bool(ok)), done.set()))

        self.call_from_thread(ask)
        while not done.wait(0.2):
            if not self.is_running:  # quit while the question was open: send nothing
                return False
        return answer[0]

    # history, export, help -------------------------------------------------
    def action_history(self) -> None:
        def opened(path: Optional[Path]) -> None:
            if path is not None:
                self.run_worker(self.load_record(path), group="history")
        self.push_screen(HistoryScreen(self.session.evidence_dir), callback=opened)

    async def load_record(self, path: Path) -> None:
        try:
            record = load_record(path, self.session.evidence_dir)
            if record.raw:
                await self._load_raw_record(record)
                self._show(record, path)
                return
            op = find_operation(record.operation)
        except (EvidenceError, KeyError, InputError, ValueError) as exc:
            self.notify(str(exc), severity="error")
            return
        self.current_operation, self.current_endpoint = op, None
        pane = self.query_one(InputsPane)
        await pane.load(op)
        pane.set_values(record.inputs, [e["text"] for e in record.expectations])
        self._show(record, path)

    async def _load_raw_record(self, record: EvidenceRecord) -> None:
        """Reopen a raw record in the raw form (an update still needs a fresh baseline)."""
        info, inputs = record.endpoint or {}, record.inputs
        method, template = info.get("method", ""), info.get("path", "")
        expectations = [e["text"] for e in record.expectations]
        pane = self.query_one(InputsPane)
        if info.get("custom"):
            self.current_operation, self.current_endpoint = None, CUSTOM_PATH
            await pane.load_raw(CUSTOM_PATH)
            pane.set_raw_values(inputs, expectations, custom=(method, template))
            return
        values = {k: str(v) for k, v in (inputs.get("path") or {}).items()}
        concrete = "/" + resolve_path(custom_endpoint(method, template), values)
        found = match(method, concrete)
        if found is None:
            raise InputError("endpoint", f"{method} {template} is no longer in the endpoint index")
        self.current_operation, self.current_endpoint = None, found[0]
        await pane.load_raw(found[0])
        pane.set_raw_values(inputs, expectations)

    def action_export(self) -> None:
        if self.last_record is None or self.last_path is None:
            self.notify("Send a call or open one from History first.", severity="warning")
            return
        self.push_screen(ExportScreen(self.last_record, self.last_path))

    def action_expect(self) -> None:
        matches = self.query("#expect")
        if matches:
            matches.first().focus()

    def action_help(self) -> None:
        self.notify(
            "Ctrl+←/→ switch panes · ↑↓ move · Enter edit/send · Ctrl+S send · / search · "
            "h history · e expect · x export redacted · Ctrl+Q quit.\n"
            "Checks: status == 200 · <path> exists · <path> == value · <path> contains text. "
            "Paths: payment.payment_status.value · lines[0].id · anies[0].record.datafield[tag=505].subfield[code=a]",
            timeout=20)


def _confirm_word(req: RawRequest) -> str:
    """The word Production asks for: the indexed endpoint's, also for a custom path it matches."""
    ep = req.endpoint
    if ep.custom:
        found = match(ep.method, ep.path)
        if found is not None:
            return found[0].confirm_word
    return ep.confirm_word
