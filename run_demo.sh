#!/usr/bin/env bash
# One command to see the whole thing: run the collection, then the tests.
set -euo pipefail
cd "$(dirname "$0")"

python -m collector.run --config stores.yaml

echo
echo "Tests:"
python -m pytest
