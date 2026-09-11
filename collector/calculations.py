"""Commission, cost and net profit -- the money rules, in one place.

Per line:  gross      = quantity x unit price
           commission = gross x the store's commission rate
           cost       = gross x the cost ratio resolved for that SKU/category
           net profit = gross - commission - cost

Keeping this module free of I/O is what makes the arithmetic testable against a
hand-computed example, which is one of the tests in tests/test_calculations.py.
"""

from __future__ import annotations

import pandas as pd

from .config import StoreConfig
from .models import StoreResult

DETAIL_COLUMNS = [
    "Store ID", "Store", "Date", "SKU", "Product", "Category", "Detail level",
    "Qty", "Unit price", "Gross", "Commission", "Cost", "Net profit",
]
SUMMARY_COLUMNS = [
    "Store ID", "Store", "Source type", "Status", "Rows", "Gross", "Commission",
    "Cost", "Net profit", "Margin %", "Attempts", "Seconds", "Note",
]

MONEY_DP = 2


def _money(value: float) -> float:
    return round(value + 0.0, MONEY_DP)


def build_detail(results: list[StoreResult], stores: dict[str, StoreConfig]) -> pd.DataFrame:
    """One row per sales line, with the money columns computed."""
    records = []
    for result in results:
        store = stores[result.store_id]
        for row in result.rows:
            gross = row.gross
            commission = gross * store.commission_rate
            cost = gross * store.cost_rules.ratio_for(row.sku, row.category)
            records.append(
                {
                    "Store ID": row.store_id,
                    "Store": row.store_name,
                    "Date": row.sale_date,
                    "SKU": row.sku,
                    "Product": row.product,
                    "Category": row.category,
                    "Detail level": "line item" if row.granularity == "line_item" else "daily total",
                    "Qty": row.quantity,
                    "Unit price": _money(row.unit_price),
                    "Gross": _money(gross),
                    "Commission": _money(commission),
                    "Cost": _money(cost),
                    "Net profit": _money(gross - commission - cost),
                }
            )
    return pd.DataFrame(records, columns=DETAIL_COLUMNS)


def build_summary(
    results: list[StoreResult], detail: pd.DataFrame, stores: dict[str, StoreConfig]
) -> pd.DataFrame:
    """One row per store -- including the ones that failed.

    A failed store keeps its row with zeroed money and a Status of FAILED. A
    store that silently vanishes from the report is the failure mode this whole
    project exists to prevent: the reader must see eleven rows, always.
    """
    records = []
    for result in results:
        store = stores[result.store_id]
        rows = detail[detail["Store ID"] == result.store_id] if not detail.empty else detail
        gross = float(rows["Gross"].sum()) if len(rows) else 0.0
        commission = float(rows["Commission"].sum()) if len(rows) else 0.0
        cost = float(rows["Cost"].sum()) if len(rows) else 0.0
        net = float(rows["Net profit"].sum()) if len(rows) else 0.0

        if result.ok:
            note = f"recovered after {result.attempts} attempts" if result.attempts > 1 else ""
        else:
            note = f"{result.error_type}: {result.error_message}"

        records.append(
            {
                "Store ID": result.store_id,
                "Store": result.store_name,
                "Source type": store.collector,
                "Status": result.status,
                "Rows": len(rows),
                "Gross": _money(gross),
                "Commission": _money(commission),
                "Cost": _money(cost),
                "Net profit": _money(net),
                "Margin %": _money(100 * net / gross) if gross else 0.0,
                "Attempts": result.attempts,
                "Seconds": round(result.duration_seconds, 2),
                "Note": note,
            }
        )

    summary = pd.DataFrame(records, columns=SUMMARY_COLUMNS)
    return pd.concat([summary, _total_row(summary)], ignore_index=True)


def _total_row(summary: pd.DataFrame) -> pd.DataFrame:
    gross = float(summary["Gross"].sum())
    net = float(summary["Net profit"].sum())
    failed = int((summary["Status"] == "FAILED").sum())
    return pd.DataFrame(
        [
            {
                "Store ID": "TOTAL",
                "Store": f"{len(summary) - failed} of {len(summary)} stores collected",
                "Source type": "",
                # "PARTIAL", not "FAILED": the run did its job -- it delivered
                # ten stores and said so. Calling the total FAILED would tell
                # the reader the opposite of what happened.
                "Status": "PARTIAL" if failed else "OK",
                "Rows": int(summary["Rows"].sum()),
                "Gross": _money(gross),
                "Commission": _money(float(summary["Commission"].sum())),
                "Cost": _money(float(summary["Cost"].sum())),
                "Net profit": _money(net),
                "Margin %": _money(100 * net / gross) if gross else 0.0,
                "Attempts": "",
                "Seconds": round(float(summary["Seconds"].sum()), 2),
                "Note": f"{failed} source(s) failed - see Note column" if failed else "all sources OK",
            }
        ],
        columns=SUMMARY_COLUMNS,
    )
