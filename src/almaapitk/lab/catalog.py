"""Discover almaapitk operations and classify which HTTP verbs they send.

Operations are the public methods of the domain classes. Forms are built from
their signatures and ``Args:`` docstrings, so new almaapitk coverage appears in
the lab without editing it. Write classification comes from reading each
method's source: every ``self.client.<verb>(...)`` call it (or a ``self.``
helper it calls) makes. A method nothing can be determined for is treated as
a write until ``hints.py`` says otherwise.
"""
from __future__ import annotations

import ast
import collections.abc
import inspect
import re
import textwrap
import typing
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from almaapitk import (
    Acquisitions,
    Admin,
    Analytics,
    BibliographicRecords,
    Configuration,
    ResourceSharing,
    Users,
)
from almaapitk.domains.electronic import Electronic
from almaapitk.lab.hints import HINTS

ParamKind = Literal["str", "int", "float", "bool", "choice", "json", "unsupported"]

DOMAINS: dict[str, type] = {
    "Acquisitions": Acquisitions,
    "Admin": Admin,
    "Analytics": Analytics,
    "BibliographicRecords": BibliographicRecords,
    "Configuration": Configuration,
    "Electronic": Electronic,
    "ResourceSharing": ResourceSharing,
    "Users": Users,
}

ALIASES: dict[str, str] = {
    "acq": "Acquisitions",
    "admin": "Admin",
    "analytics": "Analytics",
    "bibs": "BibliographicRecords",
    "conf": "Configuration",
    "electronic": "Electronic",
    "rs": "ResourceSharing",
    "users": "Users",
}

# Client methods and the HTTP verb each one sends. ``None`` = no request.
_CLIENT_VERBS: dict[str, str | None] = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "delete": "DELETE",
    "iter_paged": "GET",
    "test_connection": "GET",
    "get_environment": None,
}


@dataclass(frozen=True)
class Param:
    """One input of an operation, as the inputs pane shows it."""

    name: str
    annotation: str
    kind: ParamKind
    required: bool
    default: Any
    help: str
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Operation:
    """A public domain method the lab can call."""

    domain: str
    name: str
    params: tuple[Param, ...]
    verbs: frozenset[str]
    multi_write: bool
    doc: str

    @property
    def qualname(self) -> str:
        return f"{self.domain}.{self.name}"

    @property
    def writes(self) -> bool:
        """True when the operation may send anything but GET."""
        return any(v != "GET" for v in self.verbs)

    @property
    def sendable(self) -> bool:
        """False when a required input cannot be entered in the lab."""
        return not any(p.required and p.kind == "unsupported" for p in self.params)

    @property
    def summary(self) -> str:
        return self.doc.strip().splitlines()[0] if self.doc.strip() else ""


def discover_operations() -> list[Operation]:
    """All operations, sorted by qualname."""
    return list(_discover())


@lru_cache(maxsize=1)
def _discover() -> tuple[Operation, ...]:
    ops = []
    for domain, cls in DOMAINS.items():
        for name, func in inspect.getmembers(cls, inspect.isfunction):
            if not name.startswith("_"):
                ops.append(_build_operation(domain, cls, name, func))
    return tuple(sorted(ops, key=lambda o: o.qualname))


def find_operation(qualname: str) -> Operation:
    """Look up ``Domain.method`` or an alias such as ``bibs.get_record``."""
    domain, _, name = qualname.partition(".")
    domain = ALIASES.get(domain.lower(), domain)
    wanted = f"{domain}.{name}"
    for op in _discover():
        if op.qualname == wanted:
            return op
    raise KeyError(f"unknown operation {qualname!r}")


def _build_operation(domain: str, cls: type, name: str, func: Any) -> Operation:
    qualname = f"{domain}.{name}"
    hint = HINTS.get(qualname, {})
    doc = inspect.getdoc(func) or ""
    helps = _arg_help(doc)
    try:
        hints = typing.get_type_hints(func)
    except Exception:  # unresolvable forward refs: fall back to raw annotations
        hints = {}
    params = []
    for p in inspect.signature(func).parameters.values():
        if p.name == "self" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        annotation = hints.get(p.name, p.annotation)
        choices = tuple(hint.get("choices", {}).get(p.name, ()))
        kind = "choice" if choices else _kind(annotation)
        params.append(Param(
            name=p.name,
            annotation=_annotation_text(annotation),
            kind=kind,
            required=p.default is p.empty,
            default=None if p.default is p.empty else p.default,
            help=helps.get(p.name, ""),
            choices=choices or _literal_choices(annotation),
        ))
    if "verbs" in hint:
        verbs, write_sites = frozenset(hint["verbs"]), 2 if hint.get("multi_write") else 0
    else:
        verbs, write_sites = _classify(cls, name)
    return Operation(
        domain=domain,
        name=name,
        params=tuple(params),
        verbs=verbs,
        multi_write=bool(hint.get("multi_write", write_sites > 1)),
        doc=doc,
    )


def classify_verbs(cls: type, method_name: str) -> frozenset[str]:
    """HTTP verbs the method can send, or ``{"UNKNOWN"}``."""
    return _classify(cls, method_name)[0]


def _classify(cls: type, method_name: str) -> tuple[frozenset[str], int]:
    functions = _class_functions(cls)
    verbs: set[str] = set()
    write_sites: set[tuple[str, int]] = set()
    seen: set[str] = set()
    found_anything = False

    def walk(name: str) -> None:
        nonlocal found_anything
        if name in seen or name not in functions:
            return
        seen.add(name)
        for kind, attr, node in _self_calls(functions[name]):
            if kind == "client":
                if attr in _CLIENT_VERBS:
                    found_anything = True
                    verb = _CLIENT_VERBS[attr]
                    if verb:
                        verbs.add(verb)
                        if verb != "GET":
                            write_sites.add((name, node.lineno))
            elif attr in functions:
                found_anything = True
                walk(attr)

    walk(method_name)
    if not found_anything:
        return frozenset({"UNKNOWN"}), 0
    loops = any(
        isinstance(n, (ast.For, ast.While))
        and any(
            isinstance(c, ast.Call) and getattr(c.func, "attr", "") in ("post", "put", "delete")
            for c in ast.walk(n)
        )
        for fname in seen for n in ast.walk(functions[fname])
    )
    return frozenset(verbs), len(write_sites) + (2 if loops else 0)


def _self_calls(func: ast.AST):
    """Yield ``(kind, attr, node)`` for ``self.client.<attr>(...)`` ("client")
    and ``self.<attr>(...)`` ("self") calls inside ``func``."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        target = node.func.value
        attr = node.func.attr
        if (isinstance(target, ast.Attribute) and target.attr == "client"
                and isinstance(target.value, ast.Name) and target.value.id == "self"):
            yield "client", attr, node
        elif isinstance(target, ast.Name) and target.id == "self":
            yield "self", attr, node


def _reachable(cls: type, method_name: str) -> list[ast.FunctionDef]:
    """``method_name`` plus every ``self.`` helper it (transitively) calls."""
    functions = _class_functions(cls)
    seen: dict[str, ast.FunctionDef] = {}
    todo = [method_name]
    while todo:
        name = todo.pop()
        if name in seen or name not in functions:
            continue
        seen[name] = functions[name]
        todo.extend(a for k, a, _ in _self_calls(functions[name]) if k == "self")
    return list(seen.values())


def _template(node: ast.AST) -> str | None:
    """Path template of a literal / f-string node, placeholders as ``{}``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value
    elif isinstance(node, ast.JoinedStr):
        text = "".join(
            v.value if isinstance(v, ast.Constant) else "{}" for v in node.values
        )
    else:
        return None
    return "/" + text.lstrip("/")


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _own_nodes(func: ast.AST):
    """Nodes of ``func``'s own scope: nested functions, lambdas and classes are
    yielded themselves but not entered."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _SCOPES):
            stack.extend(ast.iter_child_nodes(node))


def _param_names(func: ast.AST) -> set[str]:
    args = getattr(func, "args", None)
    if args is None:
        return set()
    every = [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]
    return {a.arg for a in every if a is not None}


def _binds_name(node: ast.AST, name: str) -> bool:
    """True for bindings of ``name`` that are not plain ``Name`` stores."""
    if isinstance(node, ast.ExceptHandler):
        return node.name == name
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return any((a.asname or a.name.split(".")[0]) == name for a in node.names)
    if isinstance(node, (ast.Global, ast.Nonlocal)):
        return name in node.names
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, (ast.MatchAs, ast.MatchStar)):
        return node.name == name
    if isinstance(node, ast.MatchMapping):
        return node.rest == name
    return False


def _literal_store_count(node: ast.AST, name: str) -> int:
    """Stores of ``name`` this node makes with a literal / f-string value."""
    if isinstance(node, ast.Assign) and _template(node.value) is not None:
        return sum(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    if (isinstance(node, ast.AnnAssign) and node.value is not None
            and _template(node.value) is not None):
        target = node.target
        return int(isinstance(target, ast.Name) and target.id == name)
    return 0


def _resolve_templates(func: ast.AST, arg: ast.AST) -> set[str]:
    """Templates for a request-path argument; empty unless every binding of the
    name in ``func`` is a plain literal / f-string assignment."""
    direct = _template(arg)
    if direct is not None:
        return {direct}
    if not isinstance(arg, ast.Name) or arg.id in _param_names(func):
        return set()
    name = arg.id
    nodes = list(_own_nodes(func))
    if any(_binds_name(n, name) for n in nodes):
        return set()
    stores = sum(
        isinstance(n, ast.Name) and n.id == name and not isinstance(n.ctx, ast.Load)
        for n in nodes)
    literal = sum(_literal_store_count(n, name) for n in nodes)
    if stores == 0 or stores != literal:
        return set()
    templates: set[str] = set()
    for n in nodes:
        if _literal_store_count(n, name):
            templates.add(_template(n.value))  # type: ignore[attr-defined,arg-type]
    return templates


def _function_calls(func: ast.AST) -> set[tuple[str, str]]:
    """``(verb, template)`` for each client call in ``func``'s own scope with a
    literal path."""
    out: set[tuple[str, str]] = set()
    for node in _own_nodes(func):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        target = node.func.value
        if not (isinstance(target, ast.Attribute) and target.attr == "client"
                and isinstance(target.value, ast.Name) and target.value.id == "self"):
            continue
        attr = node.func.attr
        verb = _CLIENT_VERBS.get(attr)
        if not verb or attr == "test_connection":
            continue
        arg = node.args[0] if node.args else next(
            (k.value for k in node.keywords if k.arg == "endpoint"), None)
        if arg is not None:
            out.update((verb, t) for t in _resolve_templates(func, arg))
    return out


def endpoint_calls(cls: type, method_name: str) -> frozenset[tuple[str, str]]:
    """``(verb, template)`` requests a method (and its helpers) sends to literal
    paths, placeholders written ``{}``, e.g. ``("GET", "/almaws/v1/bibs/{}")``."""
    calls: set[tuple[str, str]] = set()
    for func in _reachable(cls, method_name):
        calls |= _function_calls(func)
    return frozenset(calls)


@dataclass(frozen=True)
class SentRequest:
    """One request a method sends: verb, path template (placeholders ``{}``) and the
    query it passes. A query value is a literal, ``{name}`` for one of the method's
    own inputs, or ``…`` when it cannot be read from the source."""

    verb: str
    template: str
    query: tuple[tuple[str, str], ...] = ()

    @property
    def query_text(self) -> str:
        return "&".join(f"{k}={v}" for k, v in self.query)


_UNKNOWN = "…"


def _value(node: ast.AST | None, bindings: dict[str, str], params: set[str]) -> str:
    """A query value or helper argument as text (see ``SentRequest``)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool)):
        return str(node.value).lower() if isinstance(node.value, bool) else str(node.value)
    if isinstance(node, ast.Name):
        if node.id in bindings:
            return bindings[node.id]
        if node.id in params:
            return "{" + node.id + "}"
    return _UNKNOWN


def _dict_node(func: ast.AST, node: ast.AST | None) -> ast.Dict | None:
    """A ``params=`` argument as a dict literal: inline, or a name assigned one once."""
    if isinstance(node, ast.Dict):
        return node
    if not isinstance(node, ast.Name):
        return None
    found = [n.value for n in _own_nodes(func)
             if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
             and any(isinstance(t, ast.Name) and t.id == node.id for t in n.targets)]
    return found[0] if len(found) == 1 else None


def _query(func: ast.AST, call: ast.Call, bindings: dict[str, str]) -> tuple[tuple[str, str], ...]:
    arg = next((k.value for k in call.keywords if k.arg == "params"), None)
    found = _dict_node(func, arg)
    if found is None:
        return ()
    params = _param_names(func) - {"self"}
    out = []
    for key, value in zip(found.keys, found.values):
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            out.append((key.value, _value(value, bindings, params)))
    return tuple(out)


def _helper_bindings(helper: ast.AST, call: ast.Call, bindings: dict[str, str],
                     params: set[str]) -> dict[str, str]:
    """What a ``self.helper(...)`` call passes, by the helper's parameter names. A value
    the caller takes from its own input stays ``{caller_input}``, so the Lab can fill it
    from the caller's form."""
    args = getattr(helper, "args", None)
    if args is None:
        return {}
    names = [a.arg for a in [*args.posonlyargs, *args.args] if a.arg != "self"]
    out: dict[str, str] = {}
    for name, node in zip(names, call.args):
        if not isinstance(node, ast.Starred):
            out[name] = _value(node, bindings, params)
    for kw in call.keywords:
        if kw.arg:
            out[kw.arg] = _value(kw.value, bindings, params)
    return out


@lru_cache(maxsize=None)
def sent_requests(cls: type, method_name: str) -> tuple[SentRequest, ...]:
    """Requests a method (and the ``self.`` helpers it calls) sends to literal paths,
    with the query it passes. Literal arguments a method hands to a helper are
    followed, so a convenience wrapper shows its fixed ``op``."""
    functions = _class_functions(cls)
    out: dict[SentRequest, None] = {}
    seen: set[tuple[str, tuple]] = set()

    def walk(name: str, bindings: dict[str, str]) -> None:
        key = (name, tuple(sorted(bindings.items())))
        if name not in functions or key in seen:
            return
        seen.add(key)
        func = functions[name]
        params = _param_names(func) - {"self"}
        own = {id(n) for n in _own_nodes(func)}  # as endpoint_calls: nested scopes are not entered
        calls = sorted((c for c in _self_calls(func) if id(c[2]) in own),
                       key=lambda c: (c[2].lineno, c[2].col_offset))
        for kind, attr, node in calls:
            if kind == "client":
                verb = _CLIENT_VERBS.get(attr)
                if not verb or attr == "test_connection":
                    continue
                arg = node.args[0] if node.args else next(
                    (k.value for k in node.keywords if k.arg == "endpoint"), None)
                if arg is None:
                    continue
                for template in sorted(_resolve_templates(func, arg)):
                    out[SentRequest(verb, template, _query(func, node, bindings))] = None
            elif attr in functions:
                walk(attr, _helper_bindings(functions[attr], node, bindings, params))

    walk(method_name, {})
    return tuple(out)


@lru_cache(maxsize=None)
def _class_functions(cls: type) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    return {
        n.name: n for n in klass.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


_JSON_ORIGINS = (
    dict, list, tuple,
    collections.abc.Mapping, collections.abc.Sequence, collections.abc.Iterable,
)


def _kind(annotation: Any) -> ParamKind:
    if annotation is inspect.Parameter.empty:
        return "str"
    origin = typing.get_origin(annotation)
    if origin is typing.Union or str(origin) == "<class 'types.UnionType'>":
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _kind(args[0]) if len(args) == 1 else (
            "json" if all(_kind(a) in ("json", "str") for a in args) else "unsupported")
    if origin is Literal:
        return "choice"
    if annotation is bool:
        return "bool"
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is str:
        return "str"
    if annotation in (dict, list, Any) or origin in _JSON_ORIGINS:
        return "json"
    # Callables, pymarc objects and other class instances cannot be typed in.
    return "unsupported"


def _literal_choices(annotation: Any) -> tuple[str, ...]:
    if typing.get_origin(annotation) is Literal:
        return tuple(str(a) for a in typing.get_args(annotation))
    return ()


def _annotation_text(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return ""
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


_ARG_LINE = re.compile(r"^\s{0,8}(\*{0,2}\w+)\s*(\([^)]*\))?\s*:\s*(.*)$")


def _arg_help(doc: str) -> dict[str, str]:
    """Map parameter name → first line of its ``Args:`` entry."""
    helps: dict[str, str] = {}
    in_args = False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped in ("Args:", "Arguments:", "Parameters:"):
            in_args = True
            continue
        if in_args and stripped.endswith(":") and not line.startswith((" ", "\t")):
            break
        if in_args:
            m = _ARG_LINE.match(line)
            if m and line.startswith((" ", "\t")) and len(line) - len(line.lstrip()) <= 8:
                helps.setdefault(m.group(1).lstrip("*"), m.group(3).strip())
    return helps
