"""Collector for stores on a shared web reporting platform.

Five of the eleven demo stores use this one class. That is the argument for a
collector-per-*format* rather than a collector-per-store: the platform is the
unit of work, the store is just a config entry pointing at it.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..base import Collector
from ..errors import ParseError
from ..models import SalesRow

# Columns we need from the report table, in the platform's own wording.
REQUIRED_HEADERS = ("sku", "product", "category", "qty", "unit price")
DATE_PATTERN = re.compile(r"Date:\s*(\d{4}-\d{2}-\d{2})")


class HtmlReportCollector(Collector):
    type_name = "html_report"

    def parse(self, raw: str) -> list[SalesRow]:
        soup = BeautifulSoup(raw, "lxml")
        table_id = self.store.options.get("table_id", "sales-report")
        table = soup.find("table", id=table_id)

        if table is None:
            # The message names what we looked for *and* what we found. When a
            # platform silently redesigns its report, this line is the whole
            # diagnosis -- it is what store 03 prints in the demo run.
            found = [t.get("id") or "<no id>" for t in soup.find_all("table")] or ["none"]
            raise ParseError(
                f"sales table not found: expected <table id='{table_id}'>, "
                f"page contains: {', '.join(found)} - report layout has changed"
            )

        headers = [th.get_text(strip=True).lower() for th in table.select("thead th")]
        missing = [h for h in REQUIRED_HEADERS if h not in headers]
        if missing:
            raise ParseError(
                f"report table is missing expected column(s): {', '.join(missing)} "
                f"(found: {', '.join(headers)})"
            )

        sale_date = self._extract_date(soup)
        index = {name: headers.index(name) for name in REQUIRED_HEADERS}
        rows: list[SalesRow] = []

        for line_no, tr in enumerate(table.select("tbody tr"), start=1):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) < len(headers):
                raise ParseError(f"row {line_no} has {len(cells)} cells, expected {len(headers)}")
            try:
                quantity = float(cells[index["qty"]])
                unit_price = float(cells[index["unit price"]].replace(",", ""))
            except ValueError as error:
                raise ParseError(f"row {line_no}: non-numeric qty/price ({error})") from error

            rows.append(
                SalesRow(
                    store_id=self.store.id,
                    store_name=self.store.name,
                    sale_date=sale_date,
                    sku=cells[index["sku"]],
                    product=cells[index["product"]],
                    category=cells[index["category"]].lower(),
                    quantity=quantity,
                    unit_price=unit_price,
                )
            )

        if not rows:
            raise ParseError("report table has no data rows")
        return rows

    def _extract_date(self, soup: BeautifulSoup) -> date:
        match = DATE_PATTERN.search(soup.get_text(" ", strip=True))
        if not match:
            raise ParseError("could not find the report date (expected 'Date: YYYY-MM-DD')")
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
