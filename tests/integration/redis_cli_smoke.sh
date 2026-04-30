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
RDB_PATH="$ROOT/build/dump.rdb"
rm -f "$AOF_PATH"
rm -f "$RDB_PATH"

cleanup() {
    if [[ -n "${SERVER_PID:-}" ]]; then
        kill "$SERVER_PID" >/dev/null 2>&1 || true
        wait "$SERVER_PID" >/dev/null 2>&1 || true
    fi
    rm -f "$AOF_PATH"
    rm -f "$RDB_PATH"
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

INCR_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" incr counter)"
if [[ "$INCR_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected incr 1, got '$INCR_RESULT'" >&2
    exit 1
fi

INCRBY_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" incrby counter 4)"
if [[ "$INCRBY_RESULT" != "5" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected incrby 5, got '$INCRBY_RESULT'" >&2
    exit 1
fi

DECR_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" decr counter)"
if [[ "$DECR_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected decr 4, got '$DECR_RESULT'" >&2
    exit 1
fi

DECRBY_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" decrby counter 2)"
if [[ "$DECRBY_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected decrby 2, got '$DECRBY_RESULT'" >&2
    exit 1
fi

SETNX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" setnx nx-key first)"
if [[ "$SETNX_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected setnx 1, got '$SETNX_RESULT'" >&2
    exit 1
fi

SETNX_DUP_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" setnx nx-key second)"
if [[ "$SETNX_DUP_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected setnx duplicate 0, got '$SETNX_DUP_RESULT'" >&2
    exit 1
fi

GETSET_MISSING_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getset gs-key first)"
if [[ -n "$GETSET_MISSING_RESULT" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected empty output on missing GETSET, got '$GETSET_MISSING_RESULT'" >&2
    exit 1
fi

GETSET_EXISTING_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getset gs-key second)"
if [[ "$GETSET_EXISTING_RESULT" != "first" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected GETSET first, got '$GETSET_EXISTING_RESULT'" >&2
    exit 1
fi

SETEX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" setex sx-key 2 value)"
if [[ "$SETEX_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SETEX OK, got '$SETEX_RESULT'" >&2
    exit 1
fi

MSET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" mset mk1 v1 mk2 v2)"
if [[ "$MSET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected MSET OK, got '$MSET_RESULT'" >&2
    exit 1
fi

MGET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" mget mk1 missing mk2)"
if [[ "$MGET_RESULT" != $'v1\n\nv2' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected MGET output, got '$MGET_RESULT'" >&2
    exit 1
fi

MSETNX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" msetnx mn1 a mn2 b)"
if [[ "$MSETNX_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected MSETNX 1, got '$MSETNX_RESULT'" >&2
    exit 1
fi

MSETNX_CONFLICT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" msetnx mn1 x mn3 y)"
if [[ "$MSETNX_CONFLICT_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected MSETNX conflict 0, got '$MSETNX_CONFLICT_RESULT'" >&2
    exit 1
fi

STRLEN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" strlen key)"
if [[ "$STRLEN_RESULT" != "5" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected strlen 5, got '$STRLEN_RESULT'" >&2
    exit 1
fi

APPEND_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" append key ++)"
if [[ "$APPEND_RESULT" != "7" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected append result 7, got '$APPEND_RESULT'" >&2
    exit 1
fi

GETRANGE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getrange key 1 3)"
if [[ "$GETRANGE_RESULT" != "alu" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected getrange alu, got '$GETRANGE_RESULT'" >&2
    exit 1
fi

SETRANGE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" setrange key 5 __)"
if [[ "$SETRANGE_RESULT" != "7" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected setrange 7, got '$SETRANGE_RESULT'" >&2
    exit 1
fi

GET_APPENDED_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" get key)"
if [[ "$GET_APPENDED_RESULT" != "value__" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected value__, got '$GET_APPENDED_RESULT'" >&2
    exit 1
fi

GETDEL_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set gd-key once)"
if [[ "$GETDEL_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on gd-key SET, got '$GETDEL_SET_RESULT'" >&2
    exit 1
fi

GETDEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getdel gd-key)"
if [[ "$GETDEL_RESULT" != "once" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected GETDEL once, got '$GETDEL_RESULT'" >&2
    exit 1
fi

GETDEL_MISSING_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getdel gd-key)"
if [[ -n "$GETDEL_MISSING_RESULT" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected empty output on missing GETDEL, got '$GETDEL_MISSING_RESULT'" >&2
    exit 1
fi

COUNTER_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del counter)"
if [[ "$COUNTER_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected counter DEL 1, got '$COUNTER_DEL_RESULT'" >&2
    exit 1
fi

TEMP_STRING_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del nx-key gs-key sx-key)"
if [[ "$TEMP_STRING_DEL_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected temp string DEL 3, got '$TEMP_STRING_DEL_RESULT'" >&2
    exit 1
fi

TEMP_MULTI_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del mk1 mk2 mn1 mn2)"
if [[ "$TEMP_MULTI_DEL_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected temp multi DEL 4, got '$TEMP_MULTI_DEL_RESULT'" >&2
    exit 1
fi

ECHO_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" echo hi)"
if [[ "$ECHO_RESULT" != "hi" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected hi, got '$ECHO_RESULT'" >&2
    exit 1
fi

TYPE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" type key)"
if [[ "$TYPE_RESULT" != "string" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected string, got '$TYPE_RESULT'" >&2
    exit 1
fi

DBSIZE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" dbsize)"
if [[ "$DBSIZE_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected dbsize 1, got '$DBSIZE_RESULT'" >&2
    exit 1
fi

TTL_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set ttlkey value)"
if [[ "$TTL_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on ttlkey SET, got '$TTL_SET_RESULT'" >&2
    exit 1
fi

PEXPIRE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pexpire ttlkey 0)"
if [[ "$PEXPIRE_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected PEXPIRE result 1, got '$PEXPIRE_RESULT'" >&2
    exit 1
fi

PTTL_MISSING_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pttl ttlkey)"
if [[ "$PTTL_MISSING_RESULT" != "-2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected PTTL -2, got '$PTTL_MISSING_RESULT'" >&2
    exit 1
fi

KEEP_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set keep value)"
if [[ "$KEEP_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on keep SET, got '$KEEP_SET_RESULT'" >&2
    exit 1
fi

KEEP_EXPIRE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" expire keep 5)"
if [[ "$KEEP_EXPIRE_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected EXPIRE 1, got '$KEEP_EXPIRE_RESULT'" >&2
    exit 1
fi

PERSIST_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" persist keep)"
if [[ "$PERSIST_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected PERSIST 1, got '$PERSIST_RESULT'" >&2
    exit 1
fi

PTTL_PERSISTED_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pttl keep)"
if [[ "$PTTL_PERSISTED_RESULT" != "-1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected persisted PTTL -1, got '$PTTL_PERSISTED_RESULT'" >&2
    exit 1
fi

KEEP_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del keep)"
if [[ "$KEEP_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected keep DEL 1, got '$KEEP_DEL_RESULT'" >&2
    exit 1
fi

MULTI_RESULT="$(printf 'MULTI\nSET mkey mval\nGET mkey\nEXEC\n' | redis-cli --raw -h 127.0.0.1 -p "$PORT")"
if [[ "$MULTI_RESULT" != $'OK\nQUEUED\nQUEUED\nOK\nmval' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: MULTI/EXEC unexpected output: '$MULTI_RESULT'" >&2
    exit 1
fi

DISCARD_RESULT="$(printf 'MULTI\nSET dkey dval\nDISCARD\nGET dkey\n' | redis-cli --raw -h 127.0.0.1 -p "$PORT")"
if [[ "$DISCARD_RESULT" != $'OK\nQUEUED\nOK' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: DISCARD unexpected output: '$DISCARD_RESULT'" >&2
    exit 1
fi

SAVE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" save)"
if [[ "$SAVE_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on SAVE, got '$SAVE_RESULT'" >&2
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

CONFIG_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" config get port)"
if [[ "$CONFIG_RESULT" != $'port\n'"$PORT" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: CONFIG GET port unexpected output: '$CONFIG_RESULT'" >&2
    exit 1
fi

REWRITE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" BGREWRITEAOF)"
if [[ "$REWRITE_RESULT" != "Background AOF rewrite scheduled" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: BGREWRITEAOF unexpected output: '$REWRITE_RESULT'" >&2
    exit 1
fi

QUIT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" quit)"
if [[ "$QUIT_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on QUIT, got '$QUIT_RESULT'" >&2
    exit 1
fi

echo "[PASS] integration/redis_cli_smoke"
