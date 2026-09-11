"""Loading and validating stores.yaml.

Adding a store is a config entry, never a code change -- so this module is the
only place that knows what a store entry looks like.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError


@dataclass(frozen=True)
class CostRules:
    """How cost price is derived from revenue for one store.

    Resolution order is most specific first: a SKU override beats a category
    rate, which beats the store default. Real chains price this way (a supplier
    deal on one product, a margin band per category), so the config mirrors it.
    """

    default_ratio: float = 0.55
    by_category: dict[str, float] = field(default_factory=dict)
    by_sku: dict[str, float] = field(default_factory=dict)

    def ratio_for(self, sku: str, category: str) -> float:
        if sku in self.by_sku:
            return self.by_sku[sku]
        if category in self.by_category:
            return self.by_category[category]
        return self.default_ratio

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CostRules":
        data = data or {}
        return cls(
            default_ratio=float(data.get("default_ratio", 0.55)),
            by_category={str(k): float(v) for k, v in (data.get("by_category") or {}).items()},
            by_sku={str(k): float(v) for k, v in (data.get("by_sku") or {}).items()},
        )


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff settings, shared by every store unless overridden."""

    attempts: int = 3
    backoff_seconds: float = 0.5
    backoff_multiplier: float = 2.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RetryPolicy":
        data = data or {}
        attempts = int(data.get("attempts", 3))
        if attempts < 1:
            raise ConfigError("retry.attempts must be at least 1")
        return cls(
            attempts=attempts,
            backoff_seconds=float(data.get("backoff_seconds", 0.5)),
            backoff_multiplier=float(data.get("backoff_multiplier", 2.0)),
        )


@dataclass(frozen=True)
class StoreConfig:
    id: str
    name: str
    collector: str
    source: Path
    commission_rate: float
    cost_rules: CostRules
    retry: RetryPolicy
    # Collector-specific knobs (CSV delimiter, decimal comma, email subject...).
    # Kept opaque here so a new collector never needs a change to this file.
    options: dict[str, Any] = field(default_factory=dict)
    # Demo-only: lets a fixture "fail" the first N fetches so the retry policy
    # is visible in the console output. Has no counterpart in production.
    simulate: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunConfig:
    output_dir: Path
    excel_filename: str
    report_filename: str
    stores: list[StoreConfig]

    @property
    def excel_path(self) -> Path:
        return self.output_dir / self.excel_filename

    @property
    def report_path(self) -> Path:
        return self.output_dir / self.report_filename


def load_config(path: str | Path) -> RunConfig:
    """Read stores.yaml. Relative paths resolve against the config file itself,
    so the demo runs the same from any working directory."""
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigError(f"config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    base_dir = config_path.parent
    run_section = data.get("run") or {}
    default_retry = RetryPolicy.from_dict(run_section.get("retry"))

    raw_stores = data.get("stores")
    if not raw_stores:
        raise ConfigError("config has no 'stores' section")

    stores: list[StoreConfig] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_stores, start=1):
        for required in ("id", "name", "collector", "source"):
            if not raw.get(required):
                raise ConfigError(f"store #{index} is missing required field '{required}'")
        store_id = str(raw["id"])
        if store_id in seen:
            raise ConfigError(f"duplicate store id: {store_id}")
        seen.add(store_id)

        stores.append(
            StoreConfig(
                id=store_id,
                name=str(raw["name"]),
                collector=str(raw["collector"]),
                source=(base_dir / str(raw["source"])).resolve(),
                commission_rate=float(raw.get("commission_rate", 0.0)),
                cost_rules=CostRules.from_dict(raw.get("cost_rules")),
                retry=RetryPolicy.from_dict(raw["retry"]) if raw.get("retry") else default_retry,
                options=dict(raw.get("options") or {}),
                simulate=dict(raw.get("simulate") or {}),
            )
        )

    output_dir = (base_dir / str(run_section.get("output_dir", "output"))).resolve()
    return RunConfig(
        output_dir=output_dir,
        excel_filename=str(run_section.get("excel_filename", "daily_sales_consolidated.xlsx")),
        report_filename=str(run_section.get("report_filename", "run_report.txt")),
        stores=stores,
    )
