"""The money rules, checked against numbers worked out by hand."""

from __future__ import annotations

from datetime import date

import pytest

from collector.calculations import build_detail, build_summary
from collector.config import CostRules, RetryPolicy, StoreConfig
from collector.models import SalesRow, StoreResult

STORE = StoreConfig(
    id="ST-TEST",
    name="Test Shop",
    collector="csv_export",
    source="unused",
    commission_rate=0.10,
    cost_rules=CostRules(
        default_ratio=0.50,
        by_category={"beverages": 0.40},
        by_sku={"SKU-0002": 0.25},
    ),
    retry=RetryPolicy(),
)


def row(sku: str, category: str, quantity: float, price: float) -> SalesRow:
    return SalesRow(
        store_id="ST-TEST", store_name="Test Shop", sale_date=date(2026, 9, 10),
        sku=sku, product=sku, category=category, quantity=quantity, unit_price=price,
    )


def test_cost_rules_resolve_most_specific_first():
    rules = STORE.cost_rules
    assert rules.ratio_for("SKU-0002", "beverages") == 0.25  # sku beats category
    assert rules.ratio_for("SKU-0003", "beverages") == 0.40  # category beats default
    assert rules.ratio_for("SKU-0003", "homeware") == 0.50   # default


def test_profit_columns_on_a_hand_computed_example():
    # 10 x 20.00 = 200.00 gross. Commission 10% = 20.00. Category 'homeware'
    # has no override, so cost = 50% = 100.00. Net = 200 - 20 - 100 = 80.00.
    result = StoreResult(
        store_id="ST-TEST", store_name="Test Shop", collector="csv_export",
        status="OK", rows=[row("SKU-0001", "homeware", 10, 20.00)], attempts=1,
    )
    detail = build_detail([result], {"ST-TEST": STORE})

    assert len(detail) == 1
    line = detail.iloc[0]
    assert line["Gross"] == pytest.approx(200.00)
    assert line["Commission"] == pytest.approx(20.00)
    assert line["Cost"] == pytest.approx(100.00)
    assert line["Net profit"] == pytest.approx(80.00)


def test_overrides_change_cost_but_not_commission():
    rows = [
        row("SKU-0002", "beverages", 4, 25.00),   # sku override: cost 25%
        row("SKU-0009", "beverages", 2, 10.00),   # category rate: cost 40%
    ]
    result = StoreResult(
        store_id="ST-TEST", store_name="Test Shop", collector="csv_export",
        status="OK", rows=rows, attempts=1,
    )
    detail = build_detail([result], {"ST-TEST": STORE})

    assert detail.iloc[0]["Cost"] == pytest.approx(25.00)   # 100.00 x 0.25
    assert detail.iloc[0]["Commission"] == pytest.approx(10.00)
    assert detail.iloc[1]["Cost"] == pytest.approx(8.00)    # 20.00 x 0.40
    assert detail.iloc[1]["Net profit"] == pytest.approx(20.00 - 2.00 - 8.00)


def test_summary_totals_match_the_detail_lines():
    rows = [row("SKU-0001", "homeware", 10, 20.00), row("SKU-0009", "beverages", 2, 10.00)]
    result = StoreResult(
        store_id="ST-TEST", store_name="Test Shop", collector="csv_export",
        status="OK", rows=rows, attempts=1,
    )
    detail = build_detail([result], {"ST-TEST": STORE})
    summary = build_summary([result], detail, {"ST-TEST": STORE})

    store_line = summary.iloc[0]
    assert store_line["Gross"] == pytest.approx(detail["Gross"].sum())
    assert store_line["Net profit"] == pytest.approx(detail["Net profit"].sum())
    # Margin is rounded to two decimals on purpose -- it is a display column.
    assert store_line["Margin %"] == pytest.approx(
        100 * detail["Net profit"].sum() / detail["Gross"].sum(), abs=0.005
    )


def test_failed_store_contributes_zero_and_keeps_its_row():
    failed = StoreResult(
        store_id="ST-TEST", store_name="Test Shop", collector="csv_export",
        status="FAILED", error_type="ParseError", error_message="layout changed", attempts=1,
    )
    detail = build_detail([failed], {"ST-TEST": STORE})
    summary = build_summary([failed], detail, {"ST-TEST": STORE})

    assert detail.empty
    assert summary.iloc[0]["Status"] == "FAILED"
    assert summary.iloc[0]["Gross"] == 0
    assert "ParseError: layout changed" == summary.iloc[0]["Note"]
    assert summary.iloc[-1]["Store ID"] == "TOTAL"
    assert summary.iloc[-1]["Status"] == "PARTIAL"
