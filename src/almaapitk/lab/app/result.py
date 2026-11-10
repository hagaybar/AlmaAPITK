"""Result pane: status line and tabs (Response tree, Raw, Request, Evidence).

The Response tree is lazy: a node's children are built when it is expanded,
100 at a time, so a response with thousands of rows opens instantly. XML (and
MARC inside JSON) appears as elements with their attributes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, TabbedContent, TabPane, Tree
from textual.widgets.tree import TreeNode

from almaapitk.lab.evidence import EvidenceRecord
from almaapitk.lab.normalize import _is_node, looks_like_xml, xml_to_tree

PAGE = 100


class ResultPane(Vertical):
    def compose(self) -> ComposeResult:
        yield Static("No call yet.", id="status-line")
        with TabbedContent(id="result-tabs"):
            with TabPane("Response", id="tab-response"):
                tree: Tree = Tree("result", id="response-tree")
                tree.show_root = False
                yield tree
            with TabPane("Raw", id="tab-raw"):
                with VerticalScroll(id="result-scroll"):
                    yield Static("", id="raw-body", markup=False)
            with TabPane("Request", id="tab-request"):
                with VerticalScroll():
                    yield Static("", id="request-body", markup=False)
            with TabPane("Evidence", id="tab-evidence"):
                with VerticalScroll():
                    yield Static("", id="evidence-body", markup=False)

    def on_mount(self) -> None:
        self.border_title = "Result"

    def show(self, record: EvidenceRecord, path: Optional[Path]) -> None:
        self.record, self.path = record, path
        self.query_one("#status-line", Static).update(status_text(record))
        self._fill_tree(record.result)
        raw = json.dumps(record.result, ensure_ascii=False, indent=2, default=str)
        self.query_one("#raw-body", Static).update(raw[:200_000])
        self.query_one("#request-body", Static).update(requests_text(record))
        self.query_one("#evidence-body", Static).update(evidence_text(record, path))

    # lazy tree --------------------------------------------------------------
    def _fill_tree(self, result: Any) -> None:
        tree = self.query_one("#response-tree", Tree)
        tree.clear()
        tree.root.data = _container(result)
        if tree.root.data is None:
            tree.root.add_leaf(Text(_scalar(result)))
        else:
            _populate(tree.root, 0)
        tree.root.expand()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        node = event.node
        if node.data is not None and not node.children:
            _populate(node, 0)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if isinstance(node.data, tuple) and node.data[0] == "more":
            _, parent_data, offset = node.data
            parent = node.parent
            node.remove()
            _add_page(parent, parent_data, offset)


def _container(value: Any) -> Optional[tuple]:
    if looks_like_xml(value):
        try:
            return ("xml", xml_to_tree(value))
        except Exception:
            return None
    if _is_node(value):
        return ("xml", value)
    if isinstance(value, dict):
        return ("dict", value)
    if isinstance(value, list):
        return ("list", value)
    return None


def _items(data: tuple) -> list[tuple[str, Any]]:
    kind, value = data
    if kind == "dict":
        return list(value.items())
    if kind == "list":
        return [(str(i), v) for i, v in enumerate(value)]
    return [(c["tag"], c) for c in value["children"]]


def _populate(node: TreeNode, offset: int) -> None:
    _add_page(node, node.data, offset)


def _add_page(node: TreeNode, data: tuple, offset: int) -> None:
    items = _items(data)
    for key, value in items[offset:offset + PAGE]:
        child = _container(value)
        if child is None:
            node.add_leaf(Text(f"{key}: {_scalar(value)}"))
        else:
            node.add(_label(key, child), data=child, allow_expand=bool(_items(child)) or child[0] == "xml")
    rest = len(items) - offset - PAGE
    if rest > 0:
        node.add_leaf(f"… {rest} more (Enter)", data=("more", data, offset + PAGE))


def _label(key: str, data: tuple) -> Text:
    kind, value = data
    if kind == "dict":
        return Text(f"{key} {{{len(value)}}}")
    if kind == "list":
        return Text(f"{key} [{len(value)}]")
    attrs = " ".join(f"{k}={v}" for k, v in value["attrs"].items())
    text = f"  {value['text']}" if value["text"] else ""
    return Text(f"{value['tag']}{' ' + attrs if attrs else ''}{text}")


def _scalar(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= 300 else text[:300] + " …"


def status_text(record: EvidenceRecord) -> str:
    sent = [r for r in record.requests if r.sent]
    status = sent[-1].status if sent else "—"
    ms = sum(r.duration_ms for r in sent)
    tracking = next((r.tracking_id for r in reversed(sent) if r.tracking_id), None)
    parts = [f"[b]{status}[/b]", f"{ms} ms", f"{len(sent)} request(s)"]
    if tracking:
        parts.append(f"tracking {escape(tracking)}")
    if record.error:
        parts.append(f"[b $error]{escape(record.error.split(':', 1)[0])}[/]")
    if record.expectations:
        ok = sum(e["outcome"] == "passed" for e in record.expectations)
        colour = "$success" if ok == len(record.expectations) else "$error"
        parts.append(f"[{colour}]{ok}/{len(record.expectations)} checks[/]")
    if record.incomplete:
        parts.append("[$warning]incomplete[/]")
    return "  ·  ".join(parts)


def requests_text(record: EvidenceRecord) -> str:
    blocks = []
    for n, r in enumerate(record.requests):
        head = f"[{n}] {r.method} {r.url}" + ("" if r.sent else "   NOT SENT")
        lines = [head] + [f"    {k}: {v}" for k, v in r.headers.items()]
        if r.body:
            lines.append(f"    body: {r.body}")
        if r.sent:
            lines.append(f"  → {r.status}  {r.duration_ms} ms" + (f"  tracking {r.tracking_id}" if r.tracking_id else ""))
            if r.attempts:
                lines.append(f"    retries: {r.attempts}")
            if r.error:
                lines.append(f"    error: {r.error}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) or "No request was made."


def evidence_text(record: EvidenceRecord, path: Optional[Path]) -> str:
    lines = [f"id: {record.id}", f"file: {path or '—'}", f"time: {record.created_at}",
             f"environment: {record.environment} ({record.base_url_host})",
             f"almaapitk {record.almaapitk_version} · python {record.python_version} · lab {record.tool_version}",
             f"inputs: {json.dumps(record.inputs, ensure_ascii=False, default=str)}"]
    if record.raw:
        info = record.endpoint or {}
        kind = "custom path" if info.get("custom") else f"area {info.get('area')}"
        lines.insert(1, f"raw: {info.get('method')} {info.get('path')} ({kind})")
    if record.refused:
        lines.append(f"refused: {record.refused}")
    if record.error:
        lines.append(f"error: {record.error}")
    for e in record.expectations:
        mark = "✓" if e["outcome"] == "passed" else "✗"
        lines.append(f"{mark} {e['text']}" + ("" if e["outcome"] == "passed" else f"   (actual: {e['actual']})"))
    for w in record.cancelled_writes:
        lines.append(f"not sent: {w['method']} {w['url']}")
    if record.incomplete:
        lines.append(f"INCOMPLETE: {record.incomplete_reason}")
    if record.capped:
        lines.append("result capped at 1000 items")
    lines.append("x: export a redacted copy for sharing")
    return "\n".join(lines)
