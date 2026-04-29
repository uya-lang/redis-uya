#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

make build
make test
make test-integration

benchmark_out="$(mktemp "$REPO_ROOT/build/benchmark-v0.1.0.XXXXXX.md")"
trap 'rm -f "$benchmark_out"' EXIT
REDIS_UYA_BENCH_OUT="$benchmark_out" python3 scripts/benchmark_v0_1_0.py

if command -v redis-cli >/dev/null 2>&1; then
    make test-redis-cli
else
    echo "redis-cli not found; skipping make test-redis-cli"
fi

git diff --check

echo "redis-uya definition of done verification ok"
