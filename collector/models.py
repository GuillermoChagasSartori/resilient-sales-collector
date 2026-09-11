"""The normalised shapes every part of the pipeline agrees on."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Granularity = Literal["line_item", "daily_total"]


@dataclass(frozen=True)
class SalesRow:
    """One normalised sales record.

    Every collector, regardless of source format, must produce these. This is
    the contract that lets eleven different sources land in one spreadsheet.
    """

    store_id: str
    store_name: str
    sale_date: date
    sku: str
    product: str
    category: str
    quantity: float
    unit_price: float
    # Sources that only report a daily figure cannot give line items. We keep
    # them in the same table rather than in a special case, and mark them, so
    # the totals stay correct and the reader can see why the detail is thin.
    granularity: Granularity = "line_item"

    @property
    def gross(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class StoreResult:
    """The outcome of one store, successful or not.

    The runner produces one of these per store no matter what happens, which is
    what makes "ten still process" a property of the design and not of luck.
    """

    store_id: str
    store_name: str
    collector: str
    status: Literal["OK", "FAILED"]
    rows: list[SalesRow] = field(default_factory=list)
    attempts: int = 0
    duration_seconds: float = 0.0
    error_type: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "OK"
