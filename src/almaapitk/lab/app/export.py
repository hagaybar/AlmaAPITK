"""Redacted export with a preview of every replacement (spec 5.4)."""
from __future__ import annotations

import json
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import SelectionList, Static

from almaapitk.lab.evidence import EvidenceRecord
from almaapitk.lab.redact import find_sensitive, redact


class ExportScreen(ModalScreen[None]):
    BINDINGS = [Binding("ctrl+s", "save", "Save redacted copy"), Binding("escape", "close", "Cancel")]

    def __init__(self, record: EvidenceRecord, path: Path):
        super().__init__()
        self.record_dict = record.to_dict()
        self.path = path
        self.found = find_sensitive(self.record_dict)

    def compose(self) -> ComposeResult:
        yield Static("[b]Redacted export[/b]  ·  tick a value to KEEP it  ·  Ctrl+S saves  ·  Esc cancels")
        yield SelectionList(*[(Text(f"{kind}: {value}"), value) for value, kind in self.found],
                            id="export-keep")
        with VerticalScroll():
            yield Static("", id="export-preview", markup=False)

    def on_mount(self) -> None:
        self._preview()
        self.query_one(SelectionList).focus()

    def on_selection_list_selected_changed(self, _event: SelectionList.SelectedChanged) -> None:
        self._preview()

    def _keep(self) -> frozenset[str]:
        return frozenset(self.query_one(SelectionList).selected)

    def _preview(self) -> None:
        targets = self.query("#export-preview")
        if not targets:  # the selection list reports changes while still mounting
            return
        redacted, reps = redact(self.record_dict, keep=self._keep())
        lines = [f"{r['placeholder'] or 'KEPT'}  ({r['kind']})" for r in reps]
        lines.append("")
        lines.append(json.dumps(redacted, ensure_ascii=False, indent=2, default=str)[:20_000])
        targets.first(Static).update("\n".join(lines))

    def action_save(self) -> None:
        redacted, reps = redact(self.record_dict, keep=self._keep())
        redacted["redaction"] = reps
        out = self.path.with_name(self.path.stem + ".redacted.json")
        out.write_text(json.dumps(redacted, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        self.app.notify(f"Saved {out}")
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
