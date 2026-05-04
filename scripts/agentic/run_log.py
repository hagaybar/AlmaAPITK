"""Append-only chunk log per handbook §11.2 + spec §8 step 5."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

_HEADER = (
    "# AGENTIC RUN LOG\n\n"
    "Append-only log of chunk runs. One row per finished chunk.\n\n"
    "| chunk_name | date | issues | attempts | passed | failed | skipped"
    " | time_s | pr_url |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def append_chunk_row(
    log_path: Path,
    chunk_name: str,
    issue_numbers: list[int],
    attempts_used: dict[int, int],
    test_outcomes: dict[str, int],
    time_total_seconds: int,
    pr_url: str,
) -> None:
    issues_str = ", ".join(f"#{n}" for n in issue_numbers)
    attempts_str = ", ".join(f"#{n}:{a}" for n, a in sorted(attempts_used.items()))
    date = dt.datetime.now(dt.UTC).date().isoformat()
    row = (
        f"| {chunk_name} | {date} | {issues_str} | {attempts_str}"
        f" | {test_outcomes.get('passed', 0)}"
        f" | {test_outcomes.get('failed', 0)}"
        f" | {test_outcomes.get('skipped', 0)}"
        f" | {time_total_seconds}"
        f" | {pr_url} |\n"
    )
    if not log_path.exists():
        log_path.write_text(_HEADER + row)
    else:
        existing = log_path.read_text()
        if "| chunk_name |" not in existing:
            log_path.write_text(_HEADER + row)
        else:
            with log_path.open("a") as f:
                f.write(row)


def main() -> int:
    import json
    import sys

    payload = json.load(sys.stdin)
    append_chunk_row(
        log_path=Path(payload["log_path"]),
        chunk_name=payload["chunk_name"],
        issue_numbers=payload["issue_numbers"],
        attempts_used={int(k): int(v) for k, v in payload["attempts_used"].items()},
        test_outcomes=payload["test_outcomes"],
        time_total_seconds=int(payload["time_total_seconds"]),
        pr_url=payload["pr_url"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
