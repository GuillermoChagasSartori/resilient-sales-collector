"""The runner -- where failure isolation actually happens.

Every store is collected inside its own try/except and always produces a
StoreResult. There is no code path in which one store's exception prevents
another store from being attempted, and none in which a failure is dropped
instead of reported.
"""

from __future__ import annotations

import logging
import time

from .calculations import build_detail, build_summary
from .collectors import get_collector
from .config import RunConfig, StoreConfig
from .errors import CollectorError, ParseError
from .excel import write_workbook
from .models import StoreResult
from .report import build_report, write_report

log = logging.getLogger(__name__)


def collect_store(store: StoreConfig) -> StoreResult:
    """Collect one store. Never raises -- failures come back as a result."""
    started = time.perf_counter()
    result = StoreResult(
        store_id=store.id, store_name=store.name, collector=store.collector, status="FAILED"
    )
    collector = None
    try:
        collector = get_collector(store.collector)(store)
        rows, attempts = collector.collect()
        result.rows = rows
        result.attempts = attempts
        result.status = "OK"
        log.info("[%s] %s: OK (%d rows)", store.id, store.name, len(rows))
    except CollectorError as error:
        # Expected, classified failures: bad config, unreachable source,
        # changed layout. These carry a message written for a human.
        result.error_type = type(error).__name__
        result.error_message = str(error)
        log.error("[%s] %s: %s: %s", store.id, store.name, result.error_type, error)
    except Exception as error:  # noqa: BLE001
        # Anything a third-party library throws that we did not anticipate.
        # Catching it is the point: an unknown bug in one parser must still
        # cost exactly one store, not the whole run.
        result.error_type = type(error).__name__
        result.error_message = str(error) or repr(error)
        log.exception("[%s] %s: unexpected %s", store.id, store.name, result.error_type)
    finally:
        result.duration_seconds = time.perf_counter() - started
        if collector is not None:
            # A parse failure still used up (successful) fetch attempts; report
            # the real number rather than assuming the retry limit was hit.
            result.attempts = collector.attempts_used

    return result


def run(config: RunConfig) -> tuple[list[StoreResult], str]:
    """Run every store, write the workbook and the report."""
    started = time.perf_counter()
    log.info("Starting collection for %d store(s)", len(config.stores))

    results = [collect_store(store) for store in config.stores]

    stores_by_id = {store.id: store for store in config.stores}
    detail = build_detail(results, stores_by_id)
    summary = build_summary(results, detail, stores_by_id)

    excel_path = write_workbook(config.excel_path, summary, detail)
    runtime = time.perf_counter() - started
    report = build_report(results, runtime, excel_path)
    write_report(config.report_path, report)

    return results, report


__all__ = ["collect_store", "run", "ParseError"]
