"""The run report: what succeeded, what broke, and why -- in plain sentences.

The client's requirement was "he must be told what broke". That means a human
sentence naming the store, the error type and a one-line reason, not a stack
trace in a log file.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import StoreResult


def build_report(results: list[StoreResult], runtime: float, excel_path: Path) -> str:
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    retried = [r for r in ok if r.attempts > 1]

    lines = [
        "=" * 72,
        "DAILY SALES COLLECTION - RUN REPORT",
        f"Finished at : {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Runtime     : {runtime:.2f}s",
        f"Stores      : {len(ok)} of {len(results)} collected successfully",
        f"Workbook    : {excel_path}",
        "=" * 72,
        "",
    ]

    if failed:
        lines.append(f"FAILED SOURCES ({len(failed)}) - these stores are NOT in today's totals:")
        for result in failed:
            lines.append(f"  [{result.store_id}] {result.store_name} ({result.collector})")
            lines.append(f"      {result.error_type}: {result.error_message}")
            lines.append(f"      fetch attempts used: {result.attempts}")
        lines.append("")
    else:
        lines.append("FAILED SOURCES: none")
        lines.append("")

    if retried:
        lines.append("RECOVERED AFTER RETRY (worth watching):")
        for result in retried:
            lines.append(
                f"  [{result.store_id}] {result.store_name} - succeeded on attempt {result.attempts}"
            )
        lines.append("")

    lines.append("COLLECTED:")
    for result in ok:
        rows = len(result.rows)
        lines.append(
            f"  [{result.store_id}] {result.store_name:<22} {rows:>3} row(s)  "
            f"{result.duration_seconds:>5.2f}s  via {result.collector}"
        )

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


def write_report(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    return path
