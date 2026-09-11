"""Shared fixtures. Everything here reads the same offline files the demo uses."""

from __future__ import annotations

from pathlib import Path

import pytest

from collector.config import RunConfig, StoreConfig, load_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "stores.yaml"


@pytest.fixture(scope="session")
def config() -> RunConfig:
    return load_config(CONFIG_PATH)


@pytest.fixture(scope="session")
def stores(config: RunConfig) -> dict[str, StoreConfig]:
    return {store.id: store for store in config.stores}
