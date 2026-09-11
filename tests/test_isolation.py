"""The requirement that matters: one broken source must cost exactly one store."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from collector.config import RetryPolicy
from collector.errors import FetchError
from collector.retry import retry_call
from collector.runner import collect_store, run


def test_full_run_completes_with_one_source_broken(config, tmp_path):
    results, report = run(replace(config, output_dir=tmp_path))

    assert len(results) == len(config.stores)          # every store accounted for
    failed = [r for r in results if not r.ok]
    assert [r.store_id for r in failed] == ["ST-03"]   # exactly the staged one
    assert len([r for r in results if r.ok]) == 10

    # The deliverable exists despite the failure -- this is the whole point.
    assert (tmp_path / config.excel_filename).is_file()
    assert (tmp_path / config.report_filename).is_file()
    assert "ST-03" in report and "ParseError" in report


def test_failure_is_reported_with_store_type_and_reason(config, tmp_path):
    _, report = run(replace(config, output_dir=tmp_path))
    assert "Cedarline Mall" in report        # which store
    assert "ParseError" in report            # what kind of failure
    assert "layout has changed" in report    # one-line reason
    assert "10 of 11 collected successfully" in report


def test_collect_store_never_raises(stores, tmp_path):
    """Even a completely missing source comes back as a result, not an exception."""
    broken = replace(stores["ST-01"], id="ST-99", source=Path(tmp_path / "nope.html"))
    result = collect_store(broken)

    assert result.status == "FAILED"
    assert result.error_type == "FetchError"
    assert "nope.html" in result.error_message


def test_summary_sheet_keeps_a_row_for_the_failed_store(config, tmp_path):
    import pandas as pd

    run(replace(config, output_dir=tmp_path))
    summary = pd.read_excel(tmp_path / config.excel_filename, sheet_name="Summary")

    row = summary[summary["Store ID"] == "ST-03"].iloc[0]
    assert row["Status"] == "FAILED"
    assert row["Gross"] == 0
    assert "ParseError" in row["Note"]
    # A store that vanishes from the file is indistinguishable from a store
    # that sold nothing, so all eleven must be present plus the TOTAL line.
    assert len(summary) == len(config.stores) + 1


def test_retry_gives_up_after_the_configured_attempts():
    calls = []
    policy = RetryPolicy(attempts=3, backoff_seconds=0.01, backoff_multiplier=2.0)

    def always_fails():
        calls.append(1)
        raise FetchError("boom")

    with pytest.raises(FetchError):
        retry_call(always_fails, policy, "test", sleep=lambda _: None)
    assert len(calls) == 3


def test_retry_recovers_and_reports_the_attempt_count():
    attempts = {"n": 0}
    policy = RetryPolicy(attempts=3, backoff_seconds=0.01, backoff_multiplier=2.0)

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise FetchError("transient")
        return "payload"

    result, used = retry_call(flaky, policy, "test", sleep=lambda _: None)
    assert (result, used) == ("payload", 2)


def test_parse_failures_are_not_retried(config, tmp_path):
    """A changed layout is not transient; retrying it only hides the cause."""
    results, _ = run(replace(config, output_dir=tmp_path))
    failed = next(r for r in results if r.store_id == "ST-03")
    assert failed.attempts == 1
