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
    if [[ -n "${AUTH_SERVER_PID:-}" ]]; then
        kill "$AUTH_SERVER_PID" >/dev/null 2>&1 || true
        wait "$AUTH_SERVER_PID" >/dev/null 2>&1 || true
    fi
    rm -f "$AOF_PATH"
    rm -f "${AUTH_AOF_PATH:-}"
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

TIME_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" time)"
if ! [[ "$TIME_RESULT" =~ ^[0-9]+$'\n'[0-9]+$ ]]; then
    echo "[FAIL] integration/redis_cli_smoke: unexpected TIME output '$TIME_RESULT'" >&2
    exit 1
fi

ROLE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" role)"
if ! [[ "$ROLE_RESULT" =~ ^master$'\n'[0-9]+$ ]]; then
    echo "[FAIL] integration/redis_cli_smoke: unexpected ROLE output '$ROLE_RESULT'" >&2
    exit 1
fi

RANDOMKEY_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" randomkey)"
if [[ "$RANDOMKEY_RESULT" != "key" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RANDOMKEY key, got '$RANDOMKEY_RESULT'" >&2
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

INCRBYFLOAT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" incrbyfloat fcounter 1.5)"
if [[ "$INCRBYFLOAT_RESULT" != "1.5" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected incrbyfloat 1.5, got '$INCRBYFLOAT_RESULT'" >&2
    exit 1
fi

INCRBYFLOAT_AGAIN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" incrbyfloat fcounter 2)"
if [[ "$INCRBYFLOAT_AGAIN_RESULT" != "3.5" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected incrbyfloat 3.5, got '$INCRBYFLOAT_AGAIN_RESULT'" >&2
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

RENAME_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" rename key key2)"
if [[ "$RENAME_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RENAME OK, got '$RENAME_RESULT'" >&2
    exit 1
fi

GET_RENAMED_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" get key2)"
if [[ "$GET_RENAMED_RESULT" != "value__" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected renamed key value__, got '$GET_RENAMED_RESULT'" >&2
    exit 1
fi

RENAMENX_CONFLICT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" renamenx key2 gs-key)"
if [[ "$RENAMENX_CONFLICT_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RENAMENX conflict 0, got '$RENAMENX_CONFLICT_RESULT'" >&2
    exit 1
fi

RENAMENX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" renamenx key2 key)"
if [[ "$RENAMENX_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RENAMENX 1, got '$RENAMENX_RESULT'" >&2
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

RPUSH_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" rpush rlist a b c)"
if [[ "$RPUSH_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RPUSH 3, got '$RPUSH_RESULT'" >&2
    exit 1
fi

LLEN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" llen rlist)"
if [[ "$LLEN_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected LLEN 3, got '$LLEN_RESULT'" >&2
    exit 1
fi

LINDEX_HEAD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lindex rlist 0)"
if [[ "$LINDEX_HEAD_RESULT" != "a" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected LINDEX head a, got '$LINDEX_HEAD_RESULT'" >&2
    exit 1
fi

LINDEX_TAIL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lindex rlist -1)"
if [[ "$LINDEX_TAIL_RESULT" != "c" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected LINDEX tail c, got '$LINDEX_TAIL_RESULT'" >&2
    exit 1
fi

LSET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lset rlist 1 mid)"
if [[ "$LSET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected LSET OK, got '$LSET_RESULT'" >&2
    exit 1
fi

RLIST_RANGE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lrange rlist 0 -1)"
if [[ "$RLIST_RANGE_RESULT" != $'a\nmid\nc' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RLIST range a/mid/c, got '$RLIST_RANGE_RESULT'" >&2
    exit 1
fi

RPOP_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" rpop rlist)"
if [[ "$RPOP_RESULT" != "c" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RPOP c, got '$RPOP_RESULT'" >&2
    exit 1
fi

LLEN_AFTER_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" llen rlist)"
if [[ "$LLEN_AFTER_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected LLEN after RPOP 2, got '$LLEN_AFTER_RESULT'" >&2
    exit 1
fi

RLIST_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del rlist)"
if [[ "$RLIST_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected rlist DEL 1, got '$RLIST_DEL_RESULT'" >&2
    exit 1
fi

WLIST_RPUSH_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" rpush wlist a b c b d)"
if [[ "$WLIST_RPUSH_RESULT" != "5" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected wlist RPUSH 5, got '$WLIST_RPUSH_RESULT'" >&2
    exit 1
fi

WLIST_LINSERT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" linsert wlist before c x)"
if [[ "$WLIST_LINSERT_RESULT" != "6" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected wlist LINSERT 6, got '$WLIST_LINSERT_RESULT'" >&2
    exit 1
fi

WLIST_RANGE_BEFORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lrange wlist 0 -1)"
if [[ "$WLIST_RANGE_BEFORE_RESULT" != $'a\nb\nx\nc\nb\nd' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected wlist range before trim, got '$WLIST_RANGE_BEFORE_RESULT'" >&2
    exit 1
fi

WLIST_LREM_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lrem wlist 1 b)"
if [[ "$WLIST_LREM_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected wlist LREM 1, got '$WLIST_LREM_RESULT'" >&2
    exit 1
fi

WLIST_RANGE_AFTER_LREM_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lrange wlist 0 -1)"
if [[ "$WLIST_RANGE_AFTER_LREM_RESULT" != $'a\nx\nc\nb\nd' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected wlist range after LREM, got '$WLIST_RANGE_AFTER_LREM_RESULT'" >&2
    exit 1
fi

WLIST_LTRIM_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" ltrim wlist 1 3)"
if [[ "$WLIST_LTRIM_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected wlist LTRIM OK, got '$WLIST_LTRIM_RESULT'" >&2
    exit 1
fi

WLIST_RANGE_AFTER_LTRIM_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lrange wlist 0 -1)"
if [[ "$WLIST_RANGE_AFTER_LTRIM_RESULT" != $'x\nc\nb' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected wlist range after LTRIM, got '$WLIST_RANGE_AFTER_LTRIM_RESULT'" >&2
    exit 1
fi

WLIST_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del wlist)"
if [[ "$WLIST_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected wlist DEL 1, got '$WLIST_DEL_RESULT'" >&2
    exit 1
fi

XLIST_RPUSH_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" rpush xlist a b)"
if [[ "$XLIST_RPUSH_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected xlist RPUSH 2, got '$XLIST_RPUSH_RESULT'" >&2
    exit 1
fi

LPUSHX_MISSING_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lpushx missing z)"
if [[ "$LPUSHX_MISSING_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected missing LPUSHX 0, got '$LPUSHX_MISSING_RESULT'" >&2
    exit 1
fi

LPUSHX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lpushx xlist head)"
if [[ "$LPUSHX_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected xlist LPUSHX 3, got '$LPUSHX_RESULT'" >&2
    exit 1
fi

RPUSHX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" rpushx xlist tail)"
if [[ "$RPUSHX_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected xlist RPUSHX 4, got '$RPUSHX_RESULT'" >&2
    exit 1
fi

LPOS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lpos xlist b)"
if [[ "$LPOS_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected xlist LPOS 2, got '$LPOS_RESULT'" >&2
    exit 1
fi

XLIST_RANGE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lrange xlist 0 -1)"
if [[ "$XLIST_RANGE_RESULT" != $'head\na\nb\ntail' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected xlist range head/a/b/tail, got '$XLIST_RANGE_RESULT'" >&2
    exit 1
fi

XLIST_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del xlist)"
if [[ "$XLIST_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected xlist DEL 1, got '$XLIST_DEL_RESULT'" >&2
    exit 1
fi

ZADD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zadd zset 2 b 1 a)"
if [[ "$ZADD_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZADD 2, got '$ZADD_RESULT'" >&2
    exit 1
fi

ZCARD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zcard zset)"
if [[ "$ZCARD_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZCARD 2, got '$ZCARD_RESULT'" >&2
    exit 1
fi

ZCOUNT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zcount zset 1 2)"
if [[ "$ZCOUNT_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZCOUNT 2, got '$ZCOUNT_RESULT'" >&2
    exit 1
fi

ZINCRBY_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zincrby zset 3 a)"
if [[ "$ZINCRBY_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZINCRBY 4, got '$ZINCRBY_RESULT'" >&2
    exit 1
fi

ZCOUNT_AFTER_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zcount zset 4 4)"
if [[ "$ZCOUNT_AFTER_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZCOUNT after ZINCRBY 1, got '$ZCOUNT_AFTER_RESULT'" >&2
    exit 1
fi

ZSCORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zscore zset a)"
if [[ "$ZSCORE_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZSCORE 4, got '$ZSCORE_RESULT'" >&2
    exit 1
fi

ZSCORE_MISSING_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zscore zset missing)"
if [[ -n "$ZSCORE_MISSING_RESULT" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected missing ZSCORE to be empty, got '$ZSCORE_MISSING_RESULT'" >&2
    exit 1
fi

ZMSCORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zmscore zset a missing b)"
if [[ "$ZMSCORE_RESULT" != $'4\n\n2' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZMSCORE 4/null/2, got '$ZMSCORE_RESULT'" >&2
    exit 1
fi

ZRANGE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zrange zset 0 -1)"
if [[ "$ZRANGE_RESULT" != $'b\na' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZRANGE b/a after ZINCRBY, got '$ZRANGE_RESULT'" >&2
    exit 1
fi

ZSET_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del zset)"
if [[ "$ZSET_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected zset DEL 1, got '$ZSET_DEL_RESULT'" >&2
    exit 1
fi

TOUCH_SEED_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set touchme value)"
if [[ "$TOUCH_SEED_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected touchme SET OK, got '$TOUCH_SEED_RESULT'" >&2
    exit 1
fi

TOUCH_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" touch touchme missing)"
if [[ "$TOUCH_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected TOUCH 1, got '$TOUCH_RESULT'" >&2
    exit 1
fi

UNLINK_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" unlink missing touchme)"
if [[ "$UNLINK_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected UNLINK 1, got '$UNLINK_RESULT'" >&2
    exit 1
fi

KEY_EXISTS_AFTER_UNLINK_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" exists touchme)"
if [[ "$KEY_EXISTS_AFTER_UNLINK_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected touchme to be removed by UNLINK, got '$KEY_EXISTS_AFTER_UNLINK_RESULT'" >&2
    exit 1
fi

KEYS_ALL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" keys '*' )"
if ! grep -qx 'key' <<<"$KEYS_ALL_RESULT"; then
    echo "[FAIL] integration/redis_cli_smoke: expected KEYS * to include key, got '$KEYS_ALL_RESULT'" >&2
    exit 1
fi

KEYS_K_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" keys 'k*' )"
if [[ "$KEYS_K_RESULT" != "key" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected KEYS k* to return key, got '$KEYS_K_RESULT'" >&2
    exit 1
fi

ZWORK_ADD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zadd zwork 2 b 1 a 3 c)"
if [[ "$ZWORK_ADD_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected zwork ZADD 3, got '$ZWORK_ADD_RESULT'" >&2
    exit 1
fi

ZSCAN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zscan zwork 0 count 16)"
if [[ "$ZSCAN_RESULT" != $'0\na\n1\nb\n2\nc\n3' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZSCAN payload, got '$ZSCAN_RESULT'" >&2
    exit 1
fi

ZREMRANGEBYRANK_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zremrangebyrank zwork 0 1)"
if [[ "$ZREMRANGEBYRANK_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZREMRANGEBYRANK 2, got '$ZREMRANGEBYRANK_RESULT'" >&2
    exit 1
fi

ZWORK_RANGE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zrange zwork 0 -1)"
if [[ "$ZWORK_RANGE_RESULT" != "c" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected zwork range c, got '$ZWORK_RANGE_RESULT'" >&2
    exit 1
fi

ZREMRANGEBYSCORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zremrangebyscore zwork 3 3)"
if [[ "$ZREMRANGEBYSCORE_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZREMRANGEBYSCORE 1, got '$ZREMRANGEBYSCORE_RESULT'" >&2
    exit 1
fi

ZWORK_CARD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zcard zwork)"
if [[ "$ZWORK_CARD_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected zwork ZCARD 0, got '$ZWORK_CARD_RESULT'" >&2
    exit 1
fi

ZOPS_ADD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zadd zops 2 b 1 a 3 c)"
if [[ "$ZOPS_ADD_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected zops ZADD 3, got '$ZOPS_ADD_RESULT'" >&2
    exit 1
fi

ZPOPMIN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zpopmin zops 2)"
if [[ "$ZPOPMIN_RESULT" != $'a\n1\nb\n2' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZPOPMIN a/1/b/2, got '$ZPOPMIN_RESULT'" >&2
    exit 1
fi

ZOPS_SCORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zscore zops c)"
if [[ "$ZOPS_SCORE_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected zops ZSCORE 3, got '$ZOPS_SCORE_RESULT'" >&2
    exit 1
fi

ZPOPMAX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zpopmax zops)"
if [[ "$ZPOPMAX_RESULT" != $'c\n3' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ZPOPMAX c/3, got '$ZPOPMAX_RESULT'" >&2
    exit 1
fi

ZOPS_CARD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" zcard zops)"
if [[ "$ZOPS_CARD_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected zops ZCARD 0, got '$ZOPS_CARD_RESULT'" >&2
    exit 1
fi

HSET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hset hash field value)"
if [[ "$HSET_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HSET 1, got '$HSET_RESULT'" >&2
    exit 1
fi

HGET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hget hash field)"
if [[ "$HGET_RESULT" != "value" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HGET value, got '$HGET_RESULT'" >&2
    exit 1
fi

HINCRBY_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hincrby hash counter 2)"
if [[ "$HINCRBY_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HINCRBY 2, got '$HINCRBY_RESULT'" >&2
    exit 1
fi

HINCRBYFLOAT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hincrbyfloat hash ratio 1.5)"
if [[ "$HINCRBYFLOAT_RESULT" != "1.5" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HINCRBYFLOAT 1.5, got '$HINCRBYFLOAT_RESULT'" >&2
    exit 1
fi

HKEYS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hkeys hash | sort)"
if [[ "$HKEYS_RESULT" != $'counter\nfield\nratio' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HKEYS set, got '$HKEYS_RESULT'" >&2
    exit 1
fi

HVALS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hvals hash | sort)"
if [[ "$HVALS_RESULT" != $'1.5\n2\nvalue' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HVALS set, got '$HVALS_RESULT'" >&2
    exit 1
fi

HGETALL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hgetall hash | wc -l | tr -d ' ')"
if [[ "$HGETALL_RESULT" != "6" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HGETALL 6 lines, got '$HGETALL_RESULT'" >&2
    exit 1
fi

HEXISTS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hexists hash field)"
if [[ "$HEXISTS_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HEXISTS 1, got '$HEXISTS_RESULT'" >&2
    exit 1
fi

HLEN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hlen hash)"
if [[ "$HLEN_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HLEN 3, got '$HLEN_RESULT'" >&2
    exit 1
fi

HMGET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hmget hash field missing counter)"
if [[ "$HMGET_RESULT" != $'value\n\n2' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HMGET value/null/2, got '$HMGET_RESULT'" >&2
    exit 1
fi

HSETNX_NEW_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hsetnx hash extra value)"
if [[ "$HSETNX_NEW_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HSETNX new 1, got '$HSETNX_NEW_RESULT'" >&2
    exit 1
fi

HSETNX_DUP_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hsetnx hash field next)"
if [[ "$HSETNX_DUP_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HSETNX duplicate 0, got '$HSETNX_DUP_RESULT'" >&2
    exit 1
fi

HSTRLEN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hstrlen hash field)"
if [[ "$HSTRLEN_RESULT" != "5" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HSTRLEN 5, got '$HSTRLEN_RESULT'" >&2
    exit 1
fi

HDEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hdel hash field counter extra)"
if [[ "$HDEL_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HDEL 3, got '$HDEL_RESULT'" >&2
    exit 1
fi

HLEN_AFTER_HDEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hlen hash)"
if [[ "$HLEN_AFTER_HDEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HLEN after HDEL 1, got '$HLEN_AFTER_HDEL_RESULT'" >&2
    exit 1
fi

HSCAN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" hscan hash 0 count 16 | wc -l | tr -d ' ')"
if [[ "$HSCAN_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected HSCAN 3 lines, got '$HSCAN_RESULT'" >&2
    exit 1
fi

SPIN_SADD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sadd spin a b)"
if [[ "$SPIN_SADD_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin SADD 2, got '$SPIN_SADD_RESULT'" >&2
    exit 1
fi

SPIN_SCARD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" scard spin)"
if [[ "$SPIN_SCARD_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin SCARD 2, got '$SPIN_SCARD_RESULT'" >&2
    exit 1
fi

SPIN_SISMEMBER_YES_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sismember spin a)"
if [[ "$SPIN_SISMEMBER_YES_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin SISMEMBER yes 1, got '$SPIN_SISMEMBER_YES_RESULT'" >&2
    exit 1
fi

SPIN_SISMEMBER_NO_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sismember spin z)"
if [[ "$SPIN_SISMEMBER_NO_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin SISMEMBER no 0, got '$SPIN_SISMEMBER_NO_RESULT'" >&2
    exit 1
fi

SPIN_SMISMEMBER_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" smismember spin a z b)"
if [[ "$SPIN_SMISMEMBER_RESULT" != $'1\n0\n1' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin SMISMEMBER 1/0/1, got '$SPIN_SMISMEMBER_RESULT'" >&2
    exit 1
fi

SPIN_SSCAN_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sscan spin 0 count 16)"
if [[ "$SPIN_SSCAN_RESULT" != $'0\na\nb' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin SSCAN payload, got '$SPIN_SSCAN_RESULT'" >&2
    exit 1
fi

SMOVE_SAME_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" smove spin spin a)"
if [[ "$SMOVE_SAME_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected same-key SMOVE 1, got '$SMOVE_SAME_RESULT'" >&2
    exit 1
fi

SMOVE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" smove spin move b)"
if [[ "$SMOVE_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SMOVE 1, got '$SMOVE_RESULT'" >&2
    exit 1
fi

MOVE_MEMBERS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" smembers move)"
if [[ "$MOVE_MEMBERS_RESULT" != "b" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected move members b, got '$MOVE_MEMBERS_RESULT'" >&2
    exit 1
fi

SPIN_SCARD_AFTER_SMOVE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" scard spin)"
if [[ "$SPIN_SCARD_AFTER_SMOVE_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin SCARD 1 after SMOVE, got '$SPIN_SCARD_AFTER_SMOVE_RESULT'" >&2
    exit 1
fi

MOVE_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del move)"
if [[ "$MOVE_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected move DEL 1, got '$MOVE_DEL_RESULT'" >&2
    exit 1
fi

SRANDMEMBER_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" srandmember spin)"
case "$SRANDMEMBER_RESULT" in
    a|b) ;;
    *)
        echo "[FAIL] integration/redis_cli_smoke: unexpected SRANDMEMBER '$SRANDMEMBER_RESULT'" >&2
        exit 1
        ;;
esac

SPOP_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" spop spin)"
case "$SPOP_RESULT" in
    a|b) ;;
    *)
        echo "[FAIL] integration/redis_cli_smoke: unexpected SPOP '$SPOP_RESULT'" >&2
        exit 1
        ;;
esac

SPIN_MEMBERS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" smembers spin | wc -l | tr -d ' ')"
if [[ "$SPIN_MEMBERS_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin to retain 1 member, got '$SPIN_MEMBERS_RESULT'" >&2
    exit 1
fi

SPIN_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del spin)"
if [[ "$SPIN_DEL_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected spin DEL 0 after SPOP emptied key, got '$SPIN_DEL_RESULT'" >&2
    exit 1
fi

S1_SADD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sadd s1 a b c d)"
if [[ "$S1_SADD_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected s1 SADD 4, got '$S1_SADD_RESULT'" >&2
    exit 1
fi

S2_SADD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sadd s2 b c)"
if [[ "$S2_SADD_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected s2 SADD 2, got '$S2_SADD_RESULT'" >&2
    exit 1
fi

S3_SADD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sadd s3 c d)"
if [[ "$S3_SADD_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected s3 SADD 2, got '$S3_SADD_RESULT'" >&2
    exit 1
fi

SINTER_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sinter s1 s2 s3)"
if [[ "$SINTER_RESULT" != "c" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SINTER c, got '$SINTER_RESULT'" >&2
    exit 1
fi

SINTERCARD_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sintercard 3 s1 s2 s3)"
if [[ "$SINTERCARD_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SINTERCARD 1, got '$SINTERCARD_RESULT'" >&2
    exit 1
fi

SINTERCARD_LIMIT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sintercard 3 s1 s2 s3 limit 1)"
if [[ "$SINTERCARD_LIMIT_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SINTERCARD LIMIT 1, got '$SINTERCARD_LIMIT_RESULT'" >&2
    exit 1
fi

SDIFF_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sdiff s1 s2)"
if [[ "$SDIFF_RESULT" != $'a\nd' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SDIFF a/d, got '$SDIFF_RESULT'" >&2
    exit 1
fi

SUNION_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sunion s1 s2 s3)"
if [[ "$SUNION_RESULT" != $'a\nb\nc\nd' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SUNION a/b/c/d, got '$SUNION_RESULT'" >&2
    exit 1
fi

SINTERSTORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sinterstore si s1 s2 s3)"
if [[ "$SINTERSTORE_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SINTERSTORE 1, got '$SINTERSTORE_RESULT'" >&2
    exit 1
fi

SI_MEMBERS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" smembers si)"
if [[ "$SI_MEMBERS_RESULT" != "c" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected si members c, got '$SI_MEMBERS_RESULT'" >&2
    exit 1
fi

SDIFFSTORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sdiffstore sd s1 s2)"
if [[ "$SDIFFSTORE_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SDIFFSTORE 2, got '$SDIFFSTORE_RESULT'" >&2
    exit 1
fi

SD_MEMBERS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" smembers sd | sort)"
if [[ "$SD_MEMBERS_RESULT" != $'a\nd' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected sd members a/d, got '$SD_MEMBERS_RESULT'" >&2
    exit 1
fi

SUNIONSTORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sunionstore su s1 s2 s3)"
if [[ "$SUNIONSTORE_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SUNIONSTORE 4, got '$SUNIONSTORE_RESULT'" >&2
    exit 1
fi

SU_MEMBERS_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" smembers su | sort)"
if [[ "$SU_MEMBERS_RESULT" != $'a\nb\nc\nd' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected su members a/b/c/d, got '$SU_MEMBERS_RESULT'" >&2
    exit 1
fi

SET_ALGEBRA_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del s1 s2 s3 si sd su)"
if [[ "$SET_ALGEBRA_DEL_RESULT" != "6" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected set algebra DEL 6, got '$SET_ALGEBRA_DEL_RESULT'" >&2
    exit 1
fi

HASH_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del hash)"
if [[ "$HASH_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected hash DEL 1, got '$HASH_DEL_RESULT'" >&2
    exit 1
fi

COUNTER_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del counter)"
if [[ "$COUNTER_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected counter DEL 1, got '$COUNTER_DEL_RESULT'" >&2
    exit 1
fi

TEMP_STRING_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del fcounter nx-key gs-key sx-key)"
if [[ "$TEMP_STRING_DEL_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected temp string DEL 4, got '$TEMP_STRING_DEL_RESULT'" >&2
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

SELECT_ZERO_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" select 0)"
if [[ "$SELECT_ZERO_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SELECT 0 OK, got '$SELECT_ZERO_RESULT'" >&2
    exit 1
fi

SELECT_ONE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" select 1 2>&1 || true)"
if [[ "$SELECT_ONE_RESULT" != "ERR DB index is out of range" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SELECT 1 range error, got '$SELECT_ONE_RESULT'" >&2
    exit 1
fi

OBJECT_ENCODING_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" object encoding key)"
if [[ "$OBJECT_ENCODING_RESULT" != "raw" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OBJECT ENCODING raw, got '$OBJECT_ENCODING_RESULT'" >&2
    exit 1
fi

OBJECT_REFCOUNT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" object refcount key)"
if [[ "$OBJECT_REFCOUNT_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OBJECT REFCOUNT 1, got '$OBJECT_REFCOUNT_RESULT'" >&2
    exit 1
fi

OBJECT_FREQ_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" object freq key 2>&1 || true)"
if [[ "$OBJECT_FREQ_RESULT" != ERR\ An\ LFU\ maxmemory\ policy\ is\ not\ selected* ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OBJECT FREQ LFU policy error, got '$OBJECT_FREQ_RESULT'" >&2
    exit 1
fi

MOVE_ZERO_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" move key 0 2>&1 || true)"
if [[ "$MOVE_ZERO_RESULT" != "ERR source and destination objects are the same" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected MOVE key 0 same-db error, got '$MOVE_ZERO_RESULT'" >&2
    exit 1
fi

MOVE_ONE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" move key 1 2>&1 || true)"
if [[ "$MOVE_ONE_RESULT" != "ERR DB index is out of range" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected MOVE key 1 range error, got '$MOVE_ONE_RESULT'" >&2
    exit 1
fi

WAIT_ZERO_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" wait 0 0)"
if [[ "$WAIT_ZERO_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected WAIT 0 0 to return 0, got '$WAIT_ZERO_RESULT'" >&2
    exit 1
fi

WAIT_ONE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" wait 1 10)"
if [[ "$WAIT_ONE_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected WAIT 1 10 to return 0, got '$WAIT_ONE_RESULT'" >&2
    exit 1
fi

WAIT_NEGATIVE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" wait 1 -1 2>&1 || true)"
if [[ "$WAIT_NEGATIVE_RESULT" != "ERR timeout is negative" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected WAIT negative timeout error, got '$WAIT_NEGATIVE_RESULT'" >&2
    exit 1
fi

SORT_SEED_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" rpush sortnums 3 1 2)"
if [[ "$SORT_SEED_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RPUSH sortnums 3, got '$SORT_SEED_RESULT'" >&2
    exit 1
fi

SORT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sort sortnums)"
if [[ "$SORT_RESULT" != $'1\n2\n3' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SORT default 1/2/3, got '$SORT_RESULT'" >&2
    exit 1
fi

SORT_RO_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sort_ro sortnums)"
if [[ "$SORT_RO_RESULT" != $'1\n2\n3' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SORT_RO default 1/2/3, got '$SORT_RO_RESULT'" >&2
    exit 1
fi

redis-cli --raw -h 127.0.0.1 -p "$PORT" set sortw_1 20 >/dev/null
redis-cli --raw -h 127.0.0.1 -p "$PORT" set sortw_2 10 >/dev/null
redis-cli --raw -h 127.0.0.1 -p "$PORT" set sortw_3 30 >/dev/null
redis-cli --raw -h 127.0.0.1 -p "$PORT" set obj_1 one >/dev/null
redis-cli --raw -h 127.0.0.1 -p "$PORT" set obj_2 two >/dev/null
redis-cli --raw -h 127.0.0.1 -p "$PORT" set obj_3 three >/dev/null

SORT_GET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sort sortnums by 'sortw_*' get 'obj_*' get '#')"
if [[ "$SORT_GET_RESULT" != $'two\n2\none\n1\nthree\n3' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: unexpected SORT BY/GET output: '$SORT_GET_RESULT'" >&2
    exit 1
fi

SORT_STORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sort sortnums store sortout)"
if [[ "$SORT_STORE_RESULT" != "3" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SORT STORE 3, got '$SORT_STORE_RESULT'" >&2
    exit 1
fi

SORT_STORE_LRANGE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lrange sortout 0 -1)"
if [[ "$SORT_STORE_LRANGE_RESULT" != $'1\n2\n3' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: unexpected SORT STORE LRANGE output: '$SORT_STORE_LRANGE_RESULT'" >&2
    exit 1
fi

SORT_RO_STORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" sort_ro sortnums store sortout 2>&1 || true)"
if [[ "$SORT_RO_STORE_RESULT" != "ERR syntax error" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected SORT_RO STORE syntax error, got '$SORT_RO_STORE_RESULT'" >&2
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

SEC_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set sec value)"
if [[ "$SEC_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on sec SET, got '$SEC_SET_RESULT'" >&2
    exit 1
fi

SEC_DEADLINE="$(( $(date +%s) + 4 ))"
EXPIREAT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" expireat sec "$SEC_DEADLINE")"
if [[ "$EXPIREAT_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected EXPIREAT 1, got '$EXPIREAT_RESULT'" >&2
    exit 1
fi

EXPIRETIME_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" expiretime sec)"
if [[ "$EXPIRETIME_RESULT" != "$SEC_DEADLINE" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected EXPIRETIME $SEC_DEADLINE, got '$EXPIRETIME_RESULT'" >&2
    exit 1
fi

PEXPIRETIME_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pexpiretime sec)"
if [[ "$PEXPIRETIME_RESULT" != "$(( SEC_DEADLINE * 1000 ))" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected PEXPIRETIME $(( SEC_DEADLINE * 1000 )), got '$PEXPIRETIME_RESULT'" >&2
    exit 1
fi

GETEX_NOOPT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getex sec)"
if [[ "$GETEX_NOOPT_RESULT" != "value" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected GETEX sec value, got '$GETEX_NOOPT_RESULT'" >&2
    exit 1
fi

GETEX_PERSIST_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getex sec persist)"
if [[ "$GETEX_PERSIST_RESULT" != "value" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected GETEX sec persist value, got '$GETEX_PERSIST_RESULT'" >&2
    exit 1
fi

SEC_EXPIRETIME_PERSISTED_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" expiretime sec)"
if [[ "$SEC_EXPIRETIME_PERSISTED_RESULT" != "-1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected persisted EXPIRETIME -1, got '$SEC_EXPIRETIME_PERSISTED_RESULT'" >&2
    exit 1
fi

PXKEY_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set pxkey value)"
if [[ "$PXKEY_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on pxkey SET, got '$PXKEY_SET_RESULT'" >&2
    exit 1
fi

GETEX_PX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getex pxkey px 1200)"
if [[ "$GETEX_PX_RESULT" != "value" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected GETEX pxkey px value, got '$GETEX_PX_RESULT'" >&2
    exit 1
fi

PXKEY_PTTL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pttl pxkey)"
if ! [[ "$PXKEY_PTTL_RESULT" =~ ^[0-9]+$ ]] || [[ "$PXKEY_PTTL_RESULT" -le 0 ]] || [[ "$PXKEY_PTTL_RESULT" -gt 1200 ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected pxkey PTTL in (0,1200], got '$PXKEY_PTTL_RESULT'" >&2
    exit 1
fi

AXKEY_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set axkey value)"
if [[ "$AXKEY_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on axkey SET, got '$AXKEY_SET_RESULT'" >&2
    exit 1
fi

AX_DEADLINE_MS="$(( $(date +%s) * 1000 + 2500 ))"
GETEX_PXAT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" getex axkey pxat "$AX_DEADLINE_MS")"
if [[ "$GETEX_PXAT_RESULT" != "value" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected GETEX axkey pxat value, got '$GETEX_PXAT_RESULT'" >&2
    exit 1
fi

AXKEY_PEXPIRETIME_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pexpiretime axkey)"
if [[ "$AXKEY_PEXPIRETIME_RESULT" != "$AX_DEADLINE_MS" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected axkey PEXPIRETIME $AX_DEADLINE_MS, got '$AXKEY_PEXPIRETIME_RESULT'" >&2
    exit 1
fi

PSETEX_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" psetex ps-key 1500 value)"
if [[ "$PSETEX_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected PSETEX OK, got '$PSETEX_RESULT'" >&2
    exit 1
fi

PS_KEY_PTTL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pttl ps-key)"
if ! [[ "$PS_KEY_PTTL_RESULT" =~ ^[0-9]+$ ]] || [[ "$PS_KEY_PTTL_RESULT" -le 0 ]] || [[ "$PS_KEY_PTTL_RESULT" -gt 1500 ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected ps-key PTTL in (0,1500], got '$PS_KEY_PTTL_RESULT'" >&2
    exit 1
fi

ABS_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set abs value)"
if [[ "$ABS_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on abs SET, got '$ABS_SET_RESULT'" >&2
    exit 1
fi

ABS_DEADLINE_MS="$(( $(date +%s) * 1000 + 4500 ))"
PEXPIREAT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pexpireat abs "$ABS_DEADLINE_MS")"
if [[ "$PEXPIREAT_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected PEXPIREAT 1, got '$PEXPIREAT_RESULT'" >&2
    exit 1
fi

ABS_TTL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" ttl abs)"
if [[ "$ABS_TTL_RESULT" != "3" && "$ABS_TTL_RESULT" != "4" && "$ABS_TTL_RESULT" != "5" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected abs TTL 3-5, got '$ABS_TTL_RESULT'" >&2
    exit 1
fi

ABS_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del abs)"
if [[ "$ABS_DEL_RESULT" != "1" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected abs DEL 1, got '$ABS_DEL_RESULT'" >&2
    exit 1
fi

TTL_EXTRA_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del sec pxkey axkey ps-key)"
if [[ "$TTL_EXTRA_DEL_RESULT" != "4" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected TTL extra DEL 4, got '$TTL_EXTRA_DEL_RESULT'" >&2
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

LASTSAVE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" lastsave)"
if ! [[ "$LASTSAVE_RESULT" =~ ^[0-9]+$ ]] || [[ "$LASTSAVE_RESULT" == "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected LASTSAVE positive integer, got '$LASTSAVE_RESULT'" >&2
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

FLUSH_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set flush-key value)"
if [[ "$FLUSH_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on flush-key SET, got '$FLUSH_SET_RESULT'" >&2
    exit 1
fi

FLUSHDB_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" flushdb)"
if [[ "$FLUSHDB_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected FLUSHDB OK, got '$FLUSHDB_RESULT'" >&2
    exit 1
fi

DBSIZE_AFTER_FLUSHDB_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" dbsize)"
if [[ "$DBSIZE_AFTER_FLUSHDB_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected DBSIZE 0 after FLUSHDB, got '$DBSIZE_AFTER_FLUSHDB_RESULT'" >&2
    exit 1
fi

FLUSHALL_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set flush-key-2 value)"
if [[ "$FLUSHALL_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on flush-key-2 SET, got '$FLUSHALL_SET_RESULT'" >&2
    exit 1
fi

FLUSHALL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" flushall)"
if [[ "$FLUSHALL_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected FLUSHALL OK, got '$FLUSHALL_RESULT'" >&2
    exit 1
fi

DBSIZE_AFTER_FLUSHALL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" dbsize)"
if [[ "$DBSIZE_AFTER_FLUSHALL_RESULT" != "0" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected DBSIZE 0 after FLUSHALL, got '$DBSIZE_AFTER_FLUSHALL_RESULT'" >&2
    exit 1
fi

DUMP_SET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" set dump-src value)"
if [[ "$DUMP_SET_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on dump-src SET, got '$DUMP_SET_RESULT'" >&2
    exit 1
fi

DUMP_FILE="$ROOT/build/redis-cli-smoke-dump-${PORT}.rdbfrag"
rm -f "$DUMP_FILE"
redis-cli --raw -h 127.0.0.1 -p "$PORT" dump dump-src > "$DUMP_FILE"
if ! head -c 8 "$DUMP_FILE" | grep -q '^RUYARDB1'; then
    echo "[FAIL] integration/redis_cli_smoke: unexpected DUMP header" >&2
    exit 1
fi

RESTORE_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" -x restore dump-dst 1500 < "$DUMP_FILE")"
if [[ "$RESTORE_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected RESTORE OK, got '$RESTORE_RESULT'" >&2
    exit 1
fi

DUMP_GET_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" get dump-dst)"
if [[ "$DUMP_GET_RESULT" != "value" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected dump-dst value, got '$DUMP_GET_RESULT'" >&2
    exit 1
fi

DUMP_PTTL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" pttl dump-dst)"
if ! [[ "$DUMP_PTTL_RESULT" =~ ^[0-9]+$ ]] || [[ "$DUMP_PTTL_RESULT" -le 0 ]] || [[ "$DUMP_PTTL_RESULT" -gt 1500 ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected dump-dst PTTL in (0,1500], got '$DUMP_PTTL_RESULT'" >&2
    exit 1
fi

DUMP_DEL_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" del dump-src dump-dst)"
if [[ "$DUMP_DEL_RESULT" != "2" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected dump keys DEL 2, got '$DUMP_DEL_RESULT'" >&2
    exit 1
fi

rm -f "$DUMP_FILE"

QUIT_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$PORT" quit)"
if [[ "$QUIT_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected OK on QUIT, got '$QUIT_RESULT'" >&2
    exit 1
fi

AUTH_PORT="$(python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"

AUTH_AOF_PATH="$ROOT/build/redis-cli-auth-${AUTH_PORT}.aof"
rm -f "$AUTH_AOF_PATH"
"$BIN" "$AUTH_PORT" "8" "$AUTH_AOF_PATH" "0" "noeviction" "secret" >/tmp/redis-uya-redis-cli-auth.out 2>/tmp/redis-uya-redis-cli-auth.err &
AUTH_SERVER_PID="$!"

AUTH_DEADLINE=$((SECONDS + 5))
until redis-cli --raw -h 127.0.0.1 -p "$AUTH_PORT" ping >/dev/null 2>&1; do
    if (( SECONDS >= AUTH_DEADLINE )); then
        echo "[FAIL] integration/redis_cli_smoke: auth redis-uya did not start in time" >&2
        exit 1
    fi
    sleep 0.1
done

AUTH_NOAUTH_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$AUTH_PORT" ping 2>&1 || true)"
if [[ "$AUTH_NOAUTH_RESULT" != "NOAUTH Authentication required." ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected NOAUTH on unauthenticated ping, got '$AUTH_NOAUTH_RESULT'" >&2
    exit 1
fi

AUTH_WRONG_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$AUTH_PORT" auth wrong 2>&1 || true)"
if [[ "$AUTH_WRONG_RESULT" != "WRONGPASS invalid username-password pair or user is disabled." ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected WRONGPASS on bad AUTH, got '$AUTH_WRONG_RESULT'" >&2
    exit 1
fi

AUTH_OK_RESULT="$(redis-cli --raw -h 127.0.0.1 -p "$AUTH_PORT" auth secret)"
if [[ "$AUTH_OK_RESULT" != "OK" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected AUTH OK, got '$AUTH_OK_RESULT'" >&2
    exit 1
fi

AUTH_PING_RESULT="$(redis-cli -a secret --raw -h 127.0.0.1 -p "$AUTH_PORT" ping 2>/dev/null)"
if [[ "$AUTH_PING_RESULT" != "PONG" ]]; then
    echo "[FAIL] integration/redis_cli_smoke: expected authenticated PONG, got '$AUTH_PING_RESULT'" >&2
    exit 1
fi

AUTH_CONFIG_RESULT="$(redis-cli -a secret --raw -h 127.0.0.1 -p "$AUTH_PORT" config get requirepass 2>/dev/null)"
if [[ "$AUTH_CONFIG_RESULT" != $'requirepass\nsecret' ]]; then
    echo "[FAIL] integration/redis_cli_smoke: unexpected CONFIG GET requirepass output: '$AUTH_CONFIG_RESULT'" >&2
    exit 1
fi

redis-cli -a secret --raw -h 127.0.0.1 -p "$AUTH_PORT" shutdown nosave >/dev/null 2>&1 || true
wait "$AUTH_SERVER_PID" >/dev/null 2>&1 || true
AUTH_SERVER_PID=""

echo "[PASS] integration/redis_cli_smoke"
