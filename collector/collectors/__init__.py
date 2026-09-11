"""Collector implementations and the type registry.

`stores.yaml` names a collector by string; this is the only place that maps
that string to a class. A new source type is a new module plus one line here.
"""

from __future__ import annotations

from ..base import Collector
from ..errors import ConfigError
from .csv_export import CsvExportCollector
from .email_store import EmailReportCollector
from .html_store import HtmlReportCollector
from .total_only import DailyTotalCollector

REGISTRY: dict[str, type[Collector]] = {
    cls.type_name: cls
    for cls in (
        HtmlReportCollector,
        CsvExportCollector,
        DailyTotalCollector,
        EmailReportCollector,
    )
}


def get_collector(type_name: str) -> type[Collector]:
    try:
        return REGISTRY[type_name]
    except KeyError:
        known = ", ".join(sorted(REGISTRY))
        raise ConfigError(f"unknown collector type '{type_name}' (known: {known})") from None


__all__ = ["REGISTRY", "get_collector", "Collector"]
