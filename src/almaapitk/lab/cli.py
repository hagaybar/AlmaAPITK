"""``almaapitk-lab``: the headless front end, and the launcher for the app.

    almaapitk-lab                       open the full-screen app (needs almaapitk[lab])
    almaapitk-lab call bibs.get_record --mms-id 990000000000001 --expect "status == 200"
    almaapitk-lab run steps.json        several independent calls
    almaapitk-lab list [--domain bibs] [--json]
    almaapitk-lab show <id|path> [--json]
    almaapitk-lab export <id|path> [--out FILE]
    almaapitk-lab endpoints [--area courses] [--search TEXT] [--json]
    almaapitk-lab raw GET almaws/v1/courses --query limit=5 --expect "status == 200"
    almaapitk-lab raw PUT almaws/v1/courses/<course_id> --baseline-out current.json
    almaapitk-lab raw PUT almaws/v1/courses/<course_id> --body-file edited.json \\
        --baseline current.json --allow-writes     (Production: --confirm-write "PUT courses")

Exit codes: 0 ok · 1 the call failed, a check failed or a write was refused ·
2 usage, input, credential or evidence error.
"""
from __future__ import annotations

import argparse
import json
import logging
import shlex
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from almaapitk.lab.capture import SECRET_MASK, is_secret_param
from almaapitk.lab.catalog import Operation, discover_operations, find_operation, ALIASES
from almaapitk.lab.evidence import (
    DEFAULT_EVIDENCE_DIR,
    EvidenceError,
    EvidenceRecord,
    gitignore_status,
    load_record,
)
from almaapitk.lab.endpoints import (
    AREA_TITLES,
    Endpoint,
    custom_endpoint,
    load_endpoints,
    match,
    wrapped_by,
)
from almaapitk.lab.redact import redact
from almaapitk.lab.runner import InputError, RawRequest, Session, same_path_get, update_twin

ENVIRONMENTS = ("SANDBOX", "PRODUCTION")


def _out(text: str = "") -> None:
    sys.stdout.write(text + "\n")


def _err(text: str) -> None:
    sys.stderr.write(text + "\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    args, extra = parser.parse_known_args(argv)
    if args.command != "call" and extra:
        parser.error(f"unrecognised arguments: {' '.join(extra)}")
    if not args.verbose:
        _quiet_library_logs()
    try:
        if args.command is None:
            return _launch_app(args)
        if args.command == "list":
            return _list(args)
        if args.command == "show":
            return _show(args)
        if args.command == "export":
            return _export(args)
        if args.command == "endpoints":
            return _endpoints(args)
        _warn_if_tracked(args.evidence_dir)
        if args.command == "call":
            return _call(args, extra, argv)
        if args.command == "raw":
            return _raw(args, argv)
        return _run_steps(args, argv)
    except (InputError, EvidenceError, KeyError, ValueError, RuntimeError) as exc:
        _err(f"error: {exc.args[0] if isinstance(exc, KeyError) else exc}")
        return 2


def _common(defaults: bool) -> argparse.ArgumentParser:
    """Options accepted before and after the subcommand.

    The copy on each subcommand uses SUPPRESS defaults, so an option given only
    before the subcommand is not overwritten by the subcommand's default.
    """
    p = argparse.ArgumentParser(add_help=False)
    d = (lambda v: v) if defaults else (lambda v: argparse.SUPPRESS)
    p.add_argument("--env", default=d("SANDBOX"), type=str.upper, choices=ENVIRONMENTS)
    p.add_argument("--evidence-dir", type=Path, default=d(DEFAULT_EVIDENCE_DIR))
    p.add_argument("--verbose", action="store_true", default=d(False),
                   help="keep almaapitk's own log lines (they go to stdout)")
    return p


def _parser() -> argparse.ArgumentParser:
    common = _common(defaults=False)
    parser = argparse.ArgumentParser(prog="almaapitk-lab", parents=[_common(defaults=True)],
                                     description="Run almaapitk operations and keep evidence of every call.")
    sub = parser.add_subparsers(dest="command")
    call = sub.add_parser("call", parents=[common], help="run one operation")
    call.add_argument("operation", help="Domain.method or alias, e.g. bibs.get_record")
    call.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    _write_flags(call)
    run = sub.add_parser("run", parents=[common], help="run several independent calls from a JSON file")
    run.add_argument("steps", type=Path)
    _write_flags(run)
    lst = sub.add_parser("list", parents=[common], help="list operations")
    lst.add_argument("--domain")
    lst.add_argument("--json", action="store_true")
    show = sub.add_parser("show", parents=[common], help="print one evidence record")
    show.add_argument("ref")
    show.add_argument("--json", action="store_true")
    export = sub.add_parser("export", parents=[common], help="write a redacted copy of a record")
    export.add_argument("ref")
    export.add_argument("--out", type=Path)
    eps = sub.add_parser("endpoints", parents=[common], help="list the Alma API endpoints raw can call")
    eps.add_argument("--area", help="one of: " + ", ".join(AREA_TITLES))
    eps.add_argument("--search", metavar="TEXT")
    eps.add_argument("--json", action="store_true")
    raw = sub.add_parser("raw", parents=[common], help="send one raw Alma API call")
    raw.add_argument("method", type=str.upper, choices=("GET", "POST", "PUT", "DELETE"))
    raw.add_argument("path", help="concrete path, e.g. almaws/v1/courses/<course_id>")
    raw.add_argument("--query", action="append", default=[], metavar="K=V")
    raw.add_argument("--format", dest="fmt", choices=("json", "xml"))
    raw.add_argument("--body-file", type=Path, metavar="F")
    raw.add_argument("--baseline-query", action="append", default=[], metavar="K=V",
                     help="query of the baseline GET (PUT only)")
    raw.add_argument("--baseline-out", type=Path, metavar="F",
                     help="PUT, or custom POST/PUT: fetch the current record (GET of the same path), "
                          "write it to F and stop")
    raw.add_argument("--baseline", type=Path, metavar="F",
                     help="the unedited file written by --baseline-out")
    _write_flags(raw)
    return parser


def _write_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--expect", action="append", default=[], metavar="CHECK")
    p.add_argument("--allow-writes", action="store_true", help="Sandbox: allow non-GET requests")
    p.add_argument("--confirm-write", metavar="OPERATION",
                   help="Production: allow the writes of this one operation (its method name)")
    p.add_argument("--json", action="store_true", help="print the full evidence record")


def _inputs_from_flags(op: Operation, params: list[str], extra: list[str]) -> dict[str, str]:
    raw: dict[str, str] = {}
    for item in params:
        name, sep, value = item.partition("=")
        if not sep:
            raise InputError(name, "use --param name=value")
        raw[name.strip()] = value
    i = 0
    while i < len(extra):
        token = extra[i]
        if not token.startswith("--"):
            raise InputError(token, "unexpected argument")
        name, sep, value = token[2:].partition("=")
        name = name.replace("-", "_")
        if not sep:
            if i + 1 < len(extra) and not extra[i + 1].startswith("--"):
                value, i = extra[i + 1], i + 1
            else:
                value = "true"
        raw[name] = value
        i += 1
    return raw


def _gate_for(args: argparse.Namespace, words: tuple[str, ...], refusals: list[str]):
    """The write gate; ``words`` are the accepted --confirm-write values, the first is shown."""
    def gate(method: str, url: str, body: Optional[str]) -> bool:
        if args.env == "PRODUCTION":
            if args.confirm_write in words:
                return True
            refusals.append(f"Production write refused: {method} {url}. "
                            f"Re-run with --confirm-write {shlex.quote(words[0])} to send it.")
            return False
        if args.allow_writes:
            return True
        refusals.append(f"Sandbox write refused: {method} {url}. Re-run with --allow-writes to send it.")
        return False
    return gate


def _call(args: argparse.Namespace, extra: list[str], argv: list[str]) -> int:
    op = find_operation(args.operation)
    raw = _inputs_from_flags(op, args.param, extra)
    return _execute(args, [(op, raw, args.expect)], argv)


def _run_steps(args: argparse.Namespace, argv: list[str]) -> int:
    if args.confirm_write:
        raise InputError("confirm-write", "approves the writes of one call only; send Production "
                                          "writes one at a time with `almaapitk-lab call`")
    try:
        steps = json.loads(args.steps.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError("steps", f"cannot read {args.steps}: {exc}") from None
    if not isinstance(steps, list):
        raise InputError("steps", "the file must hold a JSON list of steps")
    planned = []
    for n, step in enumerate(steps, 1):
        if not isinstance(step, dict) or "operation" not in step:
            raise InputError("steps", f"step {n} needs an \"operation\"")
        planned.append((find_operation(step["operation"]), step.get("inputs") or {}, step.get("expect") or []))
    return _execute(args, planned, argv)


def _execute(args: argparse.Namespace, planned: list, argv: list[str]) -> int:
    session = Session(args.env, evidence_dir=args.evidence_dir, source="headless",
                      command=_safe_command(argv))
    worst = 0
    try:
        for op, raw, expect in planned:
            refusals: list[str] = []
            session.gate = _gate_for(args, (op.name, op.qualname), refusals)
            try:
                record = session.run(op, raw, expect)
            except EvidenceError as exc:
                record = getattr(exc, "record", None)
                if record is None:
                    raise
                _summary(record)  # the call went out: show its result even without evidence
                _err(f"error: {exc}")
                return 2
            for line in refusals:
                _err(line)
            if args.json:
                _out(json.dumps(record.to_dict(), ensure_ascii=False, indent=2, default=str))
            else:
                _summary(record)
            if record.error or not record.checks_passed:
                worst = max(worst, 1)
    except Exception as exc:
        if isinstance(exc, (InputError, EvidenceError, KeyError, ValueError)):
            raise
        _err(f"error: {type(exc).__name__}: {exc}")
        return 2
    finally:
        session.close()
    return worst


def _summary(record: EvidenceRecord) -> None:
    sent = [r for r in record.requests if r.sent]
    last = sent[-1] if sent else None
    status = last.status if last else "-"
    ms = sum(r.duration_ms for r in sent)
    tracking = next((r.tracking_id for r in reversed(sent) if r.tracking_id), None)
    _out(f"{record.operation}  {record.environment}  status {status}  {ms} ms"
         + (f"  tracking {tracking}" if tracking else ""))
    if record.error:
        _out(f"  error   {record.error}")
    for r in record.cancelled_writes:
        _out(f"  not sent  {r['method']} {r['url']}")
    for e in record.expectations:
        mark = "✓" if e["outcome"] == "passed" else "✗"
        actual = "" if e["outcome"] == "passed" else f"   (actual: {e['actual']})"
        _out(f"  {mark} {e['text']}{actual}")
    if record.incomplete:
        _out(f"  incomplete: {record.incomplete_reason}")
    if record.refused:
        _out(f"  refused: {record.refused}")
    _out(f"  evidence {record.id}")


_REFUSED_HELP = {
    "baseline changed": "the record changed in Alma since --baseline-out; nothing was sent. "
                        "Run --baseline-out again, redo your edit on the new copy and retry.",
    "baseline could not be checked": "the baseline GET failed, so the update was not sent. Retry.",
}


def _pairs(items: list[str], flag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not name.strip():
            raise InputError(name or flag, f"use {flag} name=value")
        out[name.strip()] = value
    return out


def _read(path: Path, what: str) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(what, f"cannot read {path}: {exc}") from None


def _endpoints(args: argparse.Namespace) -> int:
    area = (args.area or "").lower()
    if area and area not in AREA_TITLES:
        raise InputError("area", f"unknown area {args.area!r}; use one of: {', '.join(AREA_TITLES)}")
    needle = (args.search or "").lower()
    chosen = [e for e in load_endpoints()
              if (not area or e.area == area)
              and (not needle or needle in f"{e.method} {e.short_path} {e.summary}".lower())]
    if args.json:
        _out(json.dumps([{
            "method": e.method, "path": e.short_path, "area": e.area, "summary": e.summary,
            "writes": e.writes, "wrapped_by": list(wrapped_by(e)),
            "params": [{"name": p.name, "in": p.location, "type": p.type, "required": p.required}
                       for p in e.params],
        } for e in chosen], ensure_ascii=False, indent=2))
        return 0
    for e in chosen:
        wrapped = wrapped_by(e)
        _out(f"{e.method} {e.short_path}  {e.summary}" + (f"  [→ {', '.join(wrapped)}]" if wrapped else ""))
    return 0


def _raw_request(args: argparse.Namespace) -> RawRequest:
    if "?" in args.path:
        raise InputError("path", "put query parameters in --query, not in the path")
    found = match(args.method, args.path)
    if found:
        endpoint, path_params = found
    else:
        endpoint, path_params = custom_endpoint(args.method, args.path), {}
        _err("note: not in the Alma API definitions; sending as a custom path")
    fmt = args.fmt or (endpoint.body_formats[0] if endpoint.body_formats else "json")
    body = _read(args.body_file, "body-file") if args.body_file else None
    return RawRequest(endpoint=endpoint, path_params=path_params, query=_pairs(args.query, "--query"),
                      body=body, fmt=fmt, baseline_query=_pairs(args.baseline_query, "--baseline-query"))


def _load_baseline(args: argparse.Namespace) -> EvidenceRecord:
    """The record behind a --baseline-out file; the file must be unedited."""
    sidecar = Path(str(args.baseline) + ".evidence")
    if not sidecar.is_file():
        raise InputError("baseline", f"{args.baseline} has no {sidecar.name}; "
                                     "re-run with --baseline-out to fetch the current record")
    record = load_record(_read(sidecar, "baseline").strip(), args.evidence_dir)
    sent = [r for r in record.requests if r.sent]
    body = (sent[-1].response_body or "") if sent else ""
    if _read(args.baseline, "baseline") != body:
        raise InputError("baseline", "the file differs from the fetched record; pass the unedited "
                                     "--baseline-out file (edit a copy and give it to --body-file)")
    return record


def _raw(args: argparse.Namespace, argv: list[str]) -> int:
    req = _raw_request(args)
    ep: Endpoint = req.endpoint
    twin = update_twin(req)
    if (args.baseline_out or args.baseline) and twin is None and same_path_get(req) is None:
        raise InputError("baseline", "applies to a PUT that has a GET on the same path, "
                                     "or a custom POST or PUT (the GET of the same path)")
    if args.baseline_out and (args.baseline or args.body_file):
        raise InputError("baseline-out", "fetches the baseline and stops; send the PUT in a second "
                                         "command with --body-file and --baseline")
    if twin is not None and not args.baseline_out and not args.baseline:
        raise InputError("baseline", "a PUT needs the current record first: run with "
                                     "--baseline-out FILE, edit a copy, then send it with "
                                     "--body-file and --baseline FILE")
    # a custom POST/PUT may pass one too: informational, but still checked for staleness
    baseline = _load_baseline(args) if args.baseline else None
    refusals: list[str] = []
    session = Session(args.env, evidence_dir=args.evidence_dir, source="headless",
                      command=_safe_command(argv))
    session.gate = _gate_for(args, (ep.confirm_word,), refusals)
    try:
        try:
            if args.baseline_out:
                record = session.fetch_baseline(req)
            else:
                record = session.run_raw(req, args.expect, baseline)
        except EvidenceError as exc:
            record = getattr(exc, "record", None)
            if record is None:
                raise
            _summary(record)
            _err(f"error: {exc}")
            return 2
        fetched = not record.error and record.last_status is not None \
            and 200 <= record.last_status < 300
        if args.baseline_out and fetched:
            _write_baseline(args.baseline_out, record)
        elif args.baseline_out:
            _err(f"error: the baseline GET failed ({record.error or f'status {record.last_status}'}); "
                 f"{args.baseline_out} was not written")
        for line in refusals:
            _err(line)
        if record.refused:
            _err(f"refused: {_REFUSED_HELP.get(record.refused, record.refused)}")
        if args.json:
            _out(json.dumps(record.to_dict(), ensure_ascii=False, indent=2, default=str))
        else:
            _summary(record)
        failed = record.error or not record.checks_passed or (args.baseline_out and not fetched)
        return 1 if failed else 0
    finally:
        session.close()


def _write_baseline(path: Path, record: EvidenceRecord) -> None:
    sent = [r for r in record.requests if r.sent]
    body = (sent[-1].response_body or "") if sent else ""
    try:
        path.write_bytes(body.encode("utf-8"))
        Path(str(path) + ".evidence").write_text(record.id + "\n", encoding="utf-8")
    except OSError as exc:
        raise EvidenceError(f"cannot write {path}: {exc}") from exc


def _list(args: argparse.Namespace) -> int:
    domain = ALIASES.get((args.domain or "").lower(), args.domain)
    ops = [o for o in discover_operations() if not domain or o.domain == domain]
    if args.json:
        _out(json.dumps([{
            "operation": o.qualname, "verbs": sorted(o.verbs), "writes": o.writes,
            "multi_write": o.multi_write, "sendable": o.sendable, "summary": o.summary,
            "params": [{"name": p.name, "kind": p.kind, "required": p.required,
                        "default": p.default if isinstance(p.default, (str, int, float, bool)) else None,
                        "help": p.help, "choices": list(p.choices)} for p in o.params],
        } for o in ops], ensure_ascii=False, indent=2))
        return 0
    for o in ops:
        verbs = ",".join(sorted(o.verbs)) or "local"
        params = " ".join(p.name if p.required else f"[{p.name}]" for p in o.params)
        _out(f"{o.qualname:<55} {verbs:<16} {params}")
    return 0


def _show(args: argparse.Namespace) -> int:
    record = load_record(args.ref, args.evidence_dir)
    if args.json:
        _out(json.dumps(record.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        _summary(record)
    return 0


def _export(args: argparse.Namespace) -> int:
    record = load_record(args.ref, args.evidence_dir)
    redacted, replacements = redact(record.to_dict())
    text = json.dumps(redacted, ensure_ascii=False, indent=2, default=str)
    if args.out:
        try:
            args.out.write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            raise EvidenceError(f"cannot write {args.out}: {exc}") from exc
        _err(f"wrote {args.out} ({len(replacements)} values replaced)")
    else:
        _out(text)
    return 0


def _launch_app(args: argparse.Namespace) -> int:
    try:
        from almaapitk.lab.app import run_app
    except ImportError:
        _err("The Alma Lab app needs Textual: pip install almaapitk[lab]  "
             "(the headless commands work without it: almaapitk-lab --help)")
        return 2
    return run_app(environment=args.env, evidence_dir=args.evidence_dir)


def _quiet_library_logs() -> None:
    """almaapitk logs to stdout; that would corrupt summaries, --json and the app.

    Everything a run needs is in its evidence record, so the toolkit's own log
    lines are switched off through its documented single gate (#142).
    """
    logging.getLogger("almapi").setLevel(logging.CRITICAL + 1)


def _warn_if_tracked(evidence_dir: Path) -> None:
    if gitignore_status(evidence_dir) == "not-ignored":
        _err(f"warning: {evidence_dir} is not in .gitignore. Evidence holds real IDs; "
             f"add it before committing (R9).")


def _safe_command(argv: list[str]) -> str:
    """The command line as recorded: credential values (``--query password=…``,
    ``--query=password=…``, ``--password …``) replaced by ``***``."""
    out: list[str] = []
    mask_next = False
    for arg in argv:
        if mask_next:
            out.append(SECRET_MASK)
            mask_next = False
            continue
        if arg.startswith("--") and "=" not in arg and is_secret_param(arg[2:].replace("-", "_")):
            mask_next = True  # a typed operation's --password VALUE
        out.append(_mask_arg(arg))
    return "almaapitk-lab " + " ".join(shlex.quote(a) for a in out)


def _mask_arg(arg: str) -> str:
    """``[--flag=]name=value`` with a credential name → value masked."""
    prefix, rest = "", arg
    if arg.startswith("--") and "=" in arg:
        flag, _, rest = arg.partition("=")
        if is_secret_param(flag[2:].replace("-", "_")):
            return f"{flag}={SECRET_MASK}"
        prefix = flag + "="
    name, sep, _ = rest.partition("=")
    if sep and is_secret_param(name):
        return f"{prefix}{name}={SECRET_MASK}"
    return arg


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
