#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

make build
make test
make test-integration

benchmark_v0_1_out="$(mktemp "$REPO_ROOT/build/benchmark-v0.1.0.XXXXXX.md")"
benchmark_v0_9_3_release_out="$(mktemp "$REPO_ROOT/build/benchmark-v0.9.3-release.XXXXXX.md")"
gap_v0_8_out="$(mktemp "$REPO_ROOT/build/gap-v0.8.0.XXXXXX.md")"
io_uring_v0_8_out="$(mktemp "$REPO_ROOT/build/io-uring-v0.8.0.XXXXXX.md")"
trap 'rm -f "$benchmark_v0_1_out" "$benchmark_v0_9_3_release_out" "$gap_v0_8_out" "$io_uring_v0_8_out"' EXIT
REDIS_UYA_BENCH_OUT="$benchmark_v0_1_out" python3 scripts/benchmark_v0_1_0.py
REDIS_UYA_BENCH_OUT="$benchmark_v0_9_3_release_out" \
    REDIS_UYA_BENCH_BASELINE=benchmarks/v0.9.3-release-performance-2026-07-20-resp-borrow.md \
    make benchmark-v0.9.3-release
REDIS_UYA_GAP_INPUT=benchmarks/v0.8.0-performance.md REDIS_UYA_GAP_OUT="$gap_v0_8_out" make report-v0.8.0-gaps
REDIS_UYA_IO_URING_OUT="$io_uring_v0_8_out" make evaluate-io-uring-v0.8.0

if command -v redis-cli >/dev/null 2>&1; then
    make test-redis-cli
else
    echo "redis-cli not found; skipping make test-redis-cli"
fi

git diff --check

echo "redis-uya definition of done verification ok"
