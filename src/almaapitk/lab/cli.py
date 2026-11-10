"""``almaapitk-lab``: the headless front end, and the launcher for the app.

    almaapitk-lab                       open the full-screen app (needs almaapitk[lab])
    almaapitk-lab call bibs.get_record --mms-id 990000000000001 --expect "status == 200"
    almaapitk-lab run steps.json        several independent calls
    almaapitk-lab list [--domain bibs] [--json]
    almaapitk-lab show <id|path> [--json]
    almaapitk-lab export <id|path> [--out FILE]

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

from almaapitk.lab.catalog import Operation, discover_operations, find_operation, ALIASES
from almaapitk.lab.evidence import (
    DEFAULT_EVIDENCE_DIR,
    EvidenceError,
    EvidenceRecord,
    gitignore_status,
    load_record,
)
from almaapitk.lab.redact import redact
from almaapitk.lab.runner import InputError, Session

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
        _warn_if_tracked(args.evidence_dir)
        if args.command == "call":
            return _call(args, extra, argv)
        return _run_steps(args, argv)
    except (InputError, EvidenceError, KeyError, ValueError) as exc:
        _err(f"error: {exc.args[0] if isinstance(exc, KeyError) else exc}")
        return 2


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env", default="SANDBOX", type=str.upper, choices=ENVIRONMENTS)
    common.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    common.add_argument("--verbose", action="store_true",
                        help="keep almaapitk's own log lines (they go to stdout)")
    parser = argparse.ArgumentParser(prog="almaapitk-lab", parents=[common],
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


def _gate_for(args: argparse.Namespace, op: Operation, refusals: list[str]):
    def gate(method: str, url: str, body: Optional[str]) -> bool:
        if args.env == "PRODUCTION":
            if args.confirm_write in (op.name, op.qualname):
                return True
            refusals.append(f"Production write refused: {method} {url}. "
                            f"Re-run with --confirm-write {op.name} to send it.")
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
            session.gate = _gate_for(args, op, refusals)
            record = session.run(op, raw, expect)
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
    _out(f"  evidence {record.id}")


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
        args.out.write_text(text + "\n", encoding="utf-8")
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
    return "almaapitk-lab " + " ".join(shlex.quote(a) for a in argv)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
