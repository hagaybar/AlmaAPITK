"""Operations pane: the domain tree, the Raw branch and the search box."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Tree

from almaapitk.lab.catalog import Operation, discover_operations
from almaapitk.lab.endpoints import AREA_TITLES, Endpoint, load_endpoints, wrapped_by

RAW_BRANCH = "Raw · all Alma endpoints"
CUSTOM_LABEL = "custom path…"

#: The "custom path…" entry: an endpoint the index does not know, filled in on the form.
CUSTOM_PATH = Endpoint(area="custom", method="GET", path="", summary="", description="",
                       params=(), body_formats=(), body_example=None, source_fetched=None,
                       custom=True)


def raw_label(ep: Endpoint) -> Text:
    """``METHOD  /short/path`` + ✎ for writes + dim ``→ Domain.method[ +N]`` when wrapped."""
    label = Text(f"{ep.method}  {ep.short_path}")
    if ep.writes:
        label.append(" ✎")
    wrapped = wrapped_by(ep)
    if wrapped:
        more = f" +{len(wrapped) - 1}" if len(wrapped) > 1 else ""
        label.append(f" → {wrapped[0]}{more}", style="dim")
    return label


class OperationsPane(Vertical):
    """Operations grouped by domain, then every Alma endpoint; ``/`` filters."""

    class Selected(Message):
        def __init__(self, operation: Operation | Endpoint) -> None:
            super().__init__()
            self.operation = operation

    def compose(self) -> ComposeResult:
        yield Input(placeholder="/ search operations", id="search")
        tree: Tree[Operation | Endpoint | None] = Tree("Operations", id="op-tree")
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
        self._fill_raw(tree, needle)

    @staticmethod
    def _fill_raw(tree: Tree, needle: str) -> None:
        areas: dict[str, list[Endpoint]] = {}
        for ep in load_endpoints():
            if needle and needle not in ep.short_path.lower() and needle not in ep.summary.lower():
                continue
            areas.setdefault(ep.area, []).append(ep)
        show_custom = not needle or needle in CUSTOM_LABEL
        if not areas and not show_custom:
            return
        raw = tree.root.add(RAW_BRANCH, data=None, expand=bool(needle))
        for area, eps in sorted(areas.items(), key=lambda kv: AREA_TITLES.get(kv[0], kv[0])):
            title = AREA_TITLES.get(area, area)
            node = raw.add(Text(f"{title} ({len(eps)})"), data=None, expand=bool(needle))
            for ep in eps:  # the index is sorted by path, then method
                node.add_leaf(raw_label(ep), data=ep)
        if show_custom:
            raw.add_leaf(CUSTOM_LABEL, data=CUSTOM_PATH)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            self._fill(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search":
            self.query_one("#op-tree", Tree).focus()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data is not None:
            self.post_message(self.Selected(event.node.data))
