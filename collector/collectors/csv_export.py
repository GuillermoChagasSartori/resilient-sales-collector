"""Collector for stores that produce a CSV/spreadsheet export.

Two knobs live in config rather than in code, because they are exactly what
differs between one back-office export and the next: the delimiter/decimal
convention, and the column names. A store that renames 'quantity' to 'units'
is a two-line YAML change, not a code change.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from ..base import Collector
from ..errors import ParseError
from ..models import SalesRow

CANONICAL_FIELDS = ("sku", "product", "category", "quantity", "unit_price", "sale_date")


class CsvExportCollector(Collector):
    type_name = "csv_export"

    def parse(self, raw: str) -> list[SalesRow]:
        options = self.store.options
        delimiter = options.get("delimiter", ",")
        decimal_comma = bool(options.get("decimal_comma", False))
        date_format = options.get("date_format", "%Y-%m-%d")
        # {canonical name -> this store's actual header}; identity by default.
        mapping = {field: options.get("columns", {}).get(field, field) for field in CANONICAL_FIELDS}

        reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        missing = [actual for actual in mapping.values() if actual not in headers]
        if missing:
            raise ParseError(
                f"CSV is missing expected column(s): {', '.join(missing)} "
                f"(found: {', '.join(headers) or 'nothing'})"
            )

        rows: list[SalesRow] = []
        for line_no, record in enumerate(reader, start=2):  # line 1 is the header
            clean = {key: (value or "").strip() for key, value in record.items() if key}
            try:
                quantity = self._number(clean[mapping["quantity"]], decimal_comma)
                unit_price = self._number(clean[mapping["unit_price"]], decimal_comma)
                sale_date = datetime.strptime(clean[mapping["sale_date"]], date_format).date()
            except (ValueError, KeyError) as error:
                raise ParseError(f"line {line_no}: {type(error).__name__} {error}") from error

            rows.append(
                SalesRow(
                    store_id=self.store.id,
                    store_name=self.store.name,
                    sale_date=sale_date,
                    sku=clean[mapping["sku"]],
                    product=clean[mapping["product"]],
                    category=clean[mapping["category"]].lower(),
                    quantity=quantity,
                    unit_price=unit_price,
                )
            )

        if not rows:
            raise ParseError("CSV export contains a header but no data rows")
        return rows

    @staticmethod
    def _number(value: str, decimal_comma: bool) -> float:
        if decimal_comma:
            value = value.replace(".", "").replace(",", ".")
        return float(value)
