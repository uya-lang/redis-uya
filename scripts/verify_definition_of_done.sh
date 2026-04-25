#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

make build
make test
make test-integration
python3 scripts/benchmark_v0_1_0.py

if command -v redis-cli >/dev/null 2>&1; then
    make test-redis-cli
else
    echo "redis-cli not found; skipping make test-redis-cli"
fi

echo "redis-uya definition of done verification ok"
