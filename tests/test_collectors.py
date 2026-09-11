"""Every collector parses its fixture into the expected normalised rows.

These are the tests that would catch a source changing shape. In production
they would run against a recently captured payload from each real source.
"""

from __future__ import annotations

from datetime import date

import pytest

from collector.collectors import REGISTRY, get_collector
from collector.errors import ConfigError, ParseError

BUSINESS_DATE = date(2026, 9, 10)


def collect(stores, store_id):
    store = stores[store_id]
    return get_collector(store.collector)(store).collect()[0]


def test_html_collector_parses_all_columns(stores):
    rows = collect(stores, "ST-01")
    assert len(rows) == 5
    first = rows[0]
    assert (first.sku, first.product, first.category) == (
        "SKU-1001", "Espresso Blend 1kg", "beverages",
    )
    assert (first.quantity, first.unit_price) == (18, 24.90)
    assert first.sale_date == BUSINESS_DATE
    assert first.gross == pytest.approx(448.20)
    assert all(row.granularity == "line_item" for row in rows)


def test_one_html_collector_serves_several_stores(stores):
    """ST-01, ST-02, ST-04 and ST-05 are different shops, one collector class."""
    used = {stores[sid].collector for sid in ("ST-01", "ST-02", "ST-04", "ST-05")}
    assert used == {"html_report"}
    for store_id in ("ST-02", "ST-04", "ST-05"):
        rows = collect(stores, store_id)
        assert rows and all(row.store_id == store_id for row in rows)


def test_csv_collector_handles_european_format_and_renamed_columns(stores):
    """ST-06 uses ';', decimal commas and its own header names -- all config."""
    rows = collect(stores, "ST-06")
    assert len(rows) == 5
    assert rows[0].unit_price == pytest.approx(24.90)
    assert rows[0].sale_date == BUSINESS_DATE
    assert rows[1].quantity == 52


def test_csv_collector_handles_plain_format(stores):
    rows = collect(stores, "ST-08")
    assert len(rows) == 6
    assert sum(row.gross for row in rows) == pytest.approx(1285.60)


def test_daily_total_collector_yields_one_marked_row(stores):
    rows = collect(stores, "ST-09")
    assert len(rows) == 1
    assert rows[0].granularity == "daily_total"
    assert rows[0].gross == pytest.approx(4812.65)
    assert rows[0].sale_date == BUSINESS_DATE


def test_email_collector_reads_body_line_items(stores):
    rows = collect(stores, "ST-11")
    assert len(rows) == 5
    assert rows[0].sku == "SKU-1001"
    assert rows[0].unit_price == pytest.approx(26.50)  # airport surcharge price
    assert rows[-1].product == "Gel Pen Pack"
    assert rows[0].sale_date == BUSINESS_DATE


def test_changed_html_layout_raises_a_named_parse_error(stores):
    """ST-03's page was redesigned. The error must say so in one readable line."""
    with pytest.raises(ParseError) as excinfo:
        collect(stores, "ST-03")
    message = str(excinfo.value)
    assert "sales-report" in message
    assert "report-grid" in message
    assert "layout has changed" in message


def test_registry_covers_every_collector_named_in_the_config(config):
    for store in config.stores:
        assert store.collector in REGISTRY


def test_unknown_collector_type_is_rejected_clearly():
    with pytest.raises(ConfigError, match="unknown collector type"):
        get_collector("carrier_pigeon")
