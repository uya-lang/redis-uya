#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="$ROOT/build/redis-uya"

if ! command -v redis-cli >/dev/null 2>&1; then
    echo "[FAIL] integration/redis_cli_smoke: redis-cli is not installed" >&2
    exit 2
fi

if [[ ! -x "$BIN" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: build/redis-uya is missing; run \`make build\` first" >&2
    exit 1
fi

PORT="$(python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"

AOF_PATH="$ROOT/build/redis-cli-smoke-${PORT}.aof"
rm -f "$AOF_PATH"

cleanup() {
    if [[ -n "${SERVER_PID:-}" ]]; then
        kill "$SERVER_PID" >/dev/null 2>&1 || true
        wait "$SERVER_PID" >/dev/null 2>&1 || true
    fi
    rm -f "$AOF_PATH"
}
trap cleanup EXIT

"$BIN" "$PORT" "8" "$AOF_PATH" >/tmp/redis-uya-redis-cli-smoke.out 2>/tmp/redis-uya-redis-cli-smoke.err &
SERVER_PID="$!"

DEADLINE=$((SECONDS + 5))
until redis-cli --raw -h 127.0.0.1 -p "$PORT" ping >/tmp/redis-uya-redis-cli-ping.out 2>/dev/null; do
    if (( SECONDS >= DEADLINE )); then
        echo "[FAIL] integration/redis_cli_smoke: redis-uya did not start in time" >&2
        exit 1
    fi
    sleep 0.1
done

PING_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" ping)"
if [[ "$PING_RESULT" != "PONG" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected PONG, got '$PING_RESULT'" >&2
    exit 1
fi

SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set key value)"
if [[ "$SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK, got '$SET_RESULT'" >&2
    exit 1
fi

GET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" get key)"
if [[ "$GET_RESULT" != "value" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected value, got '$GET_RESULT'" >&2
    exit 1
fi

DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del key)"
if [[ "$DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected 1, got '$DEL_RESULT'" >&2
    exit 1
fi

INFO_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" info server)"
if [[ "$INFO_RESULT" != *"redis_uya_version:0.1.0-dev"* ]]; then
    echo "[FAIL] integration/redis_cli_smoke: INFO output missing redis_uya_version" >&2
    exit 1
fi

QUIT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" quit)"
if [[ "$QUIT_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on QUIT, got '$QUIT_RESULT'" >&2
    exit 1
fi

echo "[PASS] integration/redis_cli_smoke"
