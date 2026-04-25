#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

make build
make test
make test-integration

echo "redis-uya definition of done verification ok"
