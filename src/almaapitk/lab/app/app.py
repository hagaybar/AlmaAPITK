"""LabApp: three panes (operations | inputs | result) with bars top and bottom."""
from __future__ import annotations

import threading
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Input, Static, TextArea

from almaapitk.lab.app.confirm import ConfirmWrite
from almaapitk.lab.app.export import ExportScreen
from almaapitk.lab.app.history import HistoryScreen
from almaapitk.lab.app.inputs import InputsPane
from almaapitk.lab.app.operations import OperationsPane
from almaapitk.lab.app.result import ResultPane
from almaapitk.lab.catalog import Operation, find_operation
from almaapitk.lab.evidence import EvidenceError, EvidenceRecord, gitignore_status, load_record
from almaapitk.lab.runner import InputError, Session

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
        self.last_record: Optional[EvidenceRecord] = None
        self.last_path: Optional[Path] = None
        self._running_op: Optional[Operation] = None

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

    async def on_operations_pane_selected(self, message: OperationsPane.Selected) -> None:
        self.current_operation = message.operation
        await self.query_one(InputsPane).load(message.operation)

    # sending ----------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            self.action_send()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id and event.input.id.startswith("field-"):
            self.action_send()

    def action_send(self) -> None:
        op = self.current_operation
        if op is None:
            self.notify("Pick an operation first.", severity="warning")
            return
        inputs = self.query_one(InputsPane)
        inputs.clear_errors()
        raw, expect = inputs.values(), inputs.expectations()
        self.query_one("#status-line", Static).update(f"Sending {op.qualname} …")
        self.run_worker(lambda: self._call(op, raw, expect), thread=True, exclusive=True, group="send")

    def _call(self, op: Operation, raw: dict, expect: list) -> None:
        self._running_op = op
        try:
            record = self.session.run(op, raw, expect)
        except InputError as exc:
            self.call_from_thread(self.query_one(InputsPane).show_error, exc.field, exc.message)
            self.call_from_thread(self.query_one("#status-line", Static).update, "Not sent: fix the input.")
            return
        except EvidenceError as exc:
            self.call_from_thread(self.notify, str(exc), severity="error", timeout=15)
            return
        except Exception as exc:  # credentials, network setup: show, don't crash the app
            self.call_from_thread(self.notify, f"{type(exc).__name__}: {exc}", severity="error", timeout=15)
            return
        finally:
            self._running_op = None
        self.call_from_thread(self._show, record, self.session.last_path)

    def _show(self, record: EvidenceRecord, path: Optional[Path]) -> None:
        self.last_record, self.last_path = record, path
        self.query_one(ResultPane).show(record, path)

    def _gate(self, method: str, url: str, body: Optional[str]) -> bool:
        """Called from the send worker before each write; waits for the user."""
        op = self._running_op or self.current_operation
        answer: list[bool] = []
        done = threading.Event()

        def ask() -> None:
            screen = ConfirmWrite(method, url, body, op.name if op else "",
                                  production=self.session.environment == "PRODUCTION")
            self.push_screen(screen, callback=lambda ok: (answer.append(bool(ok)), done.set()))

        self.call_from_thread(ask)
        done.wait()
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
            op = find_operation(record.operation)
        except (EvidenceError, KeyError) as exc:
            self.notify(str(exc), severity="error")
            return
        self.current_operation = op
        pane = self.query_one(InputsPane)
        await pane.load(op)
        pane.set_values(record.inputs, [e["text"] for e in record.expectations])
        self._show(record, path)

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
