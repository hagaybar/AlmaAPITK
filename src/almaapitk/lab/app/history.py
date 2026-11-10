"""History: earlier evidence records in this folder, newest first."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from almaapitk.lab.evidence import list_records


class HistoryScreen(ModalScreen[Optional[Path]]):
    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, evidence_dir: Path):
        super().__init__()
        self.paths = list_records(evidence_dir)

    def compose(self) -> ComposeResult:
        yield Static(f"[b]History[/b]  {len(self.paths)} record(s)  ·  Enter opens  ·  Esc closes", id="history-title")
        yield OptionList(*[Option(Text(self._label(p)), id=str(i)) for i, p in enumerate(self.paths)],
                         id="history-list")

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        if self.paths:
            options.highlighted = 0
        options.focus()

    @staticmethod
    def _label(path: Path) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return f"{path.name}  (unreadable)"
        sent = [r for r in data.get("requests", []) if r.get("sent")]
        status = sent[-1].get("status") if sent else "—"
        checks = data.get("expectations") or []
        ok = sum(c.get("outcome") == "passed" for c in checks)
        tail = f"  {ok}/{len(checks)} checks" if checks else ""
        err = f"  {data['error'].split(':', 1)[0]}" if data.get("error") else ""
        return f"{data.get('created_at', '')[:19]}  {data.get('environment', '')[:4]}  {status}  {data.get('operation')}{err}{tail}  [{data.get('source', '')}]"

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.paths[int(event.option.id)])

    def action_close(self) -> None:
        self.dismiss(None)
