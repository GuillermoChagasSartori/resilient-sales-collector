"""Collector for a store that reports one daily revenue figure and nothing else.

This source cannot be made to produce line items, so the pipeline does not
pretend otherwise: it emits a single row marked `daily_total`. Store totals
stay correct, the detail sheet stays honest about where detail is unavailable,
and no downstream code needs a special case.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..base import Collector
from ..errors import ParseError
from ..models import SalesRow

DATE_PATTERN = re.compile(r"^DATE:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
TOTAL_PATTERN = re.compile(r"^TOTAL SALES:\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.MULTILINE)


class DailyTotalCollector(Collector):
    type_name = "daily_total"

    def parse(self, raw: str) -> list[SalesRow]:
        date_match = DATE_PATTERN.search(raw)
        total_match = TOTAL_PATTERN.search(raw)
        if not date_match:
            raise ParseError("terminal export has no 'DATE: YYYY-MM-DD' line")
        if not total_match:
            raise ParseError("terminal export has no 'TOTAL SALES: <amount>' line")

        total = float(total_match.group(1))
        return [
            SalesRow(
                store_id=self.store.id,
                store_name=self.store.name,
                sale_date=datetime.strptime(date_match.group(1), "%Y-%m-%d").date(),
                sku="DAILY-TOTAL",
                product="Daily total (source reports no line items)",
                category=self.store.options.get("category", "unclassified"),
                quantity=1.0,
                unit_price=total,
                granularity="daily_total",
            )
        ]
