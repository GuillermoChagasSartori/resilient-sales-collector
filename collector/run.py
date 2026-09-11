"""Command line entry point: python -m collector.run --config stores.yaml"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_config
from .errors import ConfigError
from .runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m collector.run",
        description="Collect sales from every configured store, consolidate into one Excel file.",
    )
    parser.add_argument(
        "--config", default="stores.yaml", help="path to the store registry (default: stores.yaml)"
    )
    parser.add_argument(
        "--output-dir", default=None, help="override the output directory from the config"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="only log warnings and errors"
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        # Off by default on purpose: a partial run is a *successful* run in this
        # design. Available for schedulers that want a non-zero exit to alert on.
        help="exit with status 1 if any store failed (default: exit 0, report the failures)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        config = load_config(args.config)
    except ConfigError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    if args.output_dir:
        config = type(config)(
            output_dir=Path(args.output_dir).resolve(),
            excel_filename=config.excel_filename,
            report_filename=config.report_filename,
            stores=config.stores,
        )

    results, report = run(config)
    print()
    print(report)

    failed = [r for r in results if not r.ok]
    return 1 if (failed and args.fail_on_error) else 0


if __name__ == "__main__":
    raise SystemExit(main())
