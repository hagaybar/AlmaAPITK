"""Operations pane: the domain tree and the search box."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Tree

from almaapitk.lab.catalog import Operation, discover_operations


class OperationsPane(Vertical):
    """Operations grouped by domain; ``/`` filters by name."""

    class Selected(Message):
        def __init__(self, operation: Operation) -> None:
            super().__init__()
            self.operation = operation

    def compose(self) -> ComposeResult:
        yield Input(placeholder="/ search operations", id="search")
        tree: Tree[Operation | None] = Tree("Operations", id="op-tree")
        tree.show_root = False
        tree.guide_depth = 2
        yield tree

    def on_mount(self) -> None:
        self.border_title = "Operations"
        self._fill("")

    def _fill(self, needle: str) -> None:
        tree = self.query_one("#op-tree", Tree)
        tree.clear()
        needle = needle.strip().lower()
        groups: dict[str, list[Operation]] = {}
        for op in discover_operations():
            if needle and needle not in op.name.lower() and needle not in op.qualname.lower():
                continue
            groups.setdefault(op.domain, []).append(op)
        for domain, ops in groups.items():
            branch = tree.root.add(domain, data=None, expand=bool(needle))
            for op in ops:
                mark = "  ✎✎" if op.multi_write else ("  ✎" if op.writes else "")
                label = f"{op.name}{mark}" if op.sendable else f"[dim]{op.name}{mark}[/dim]"
                branch.add_leaf(label, data=op)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._fill(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            self.query_one("#op-tree", Tree).focus()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data is not None:
            self.post_message(self.Selected(event.node.data))
