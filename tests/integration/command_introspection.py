#!/usr/bin/env python3
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "build" / "redis-uya"


class RespError(RuntimeError):
    pass


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def connect_with_retry(port: int, deadline: float) -> socket.socket:
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            sock.settimeout(2.0)
            return sock
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"failed to connect to redis-uya on port {port}: {last_error}")


def read_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed while reading line")
        chunks.append(chunk)
        if len(chunks) >= 2 and chunks[-2] == b"\r" and chunks[-1] == b"\n":
            return b"".join(chunks[:-2])


def read_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("connection closed while reading payload")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_resp(sock: socket.socket):
    prefix = read_exact(sock, 1)
    if prefix == b"+":
        return read_line(sock).decode()
    if prefix == b"-":
        raise RespError(read_line(sock).decode())
    if prefix == b":":
        return int(read_line(sock))
    if prefix == b"_":
        line = read_line(sock)
        if line != b"":
            raise RuntimeError(f"invalid RESP3 null suffix: {line!r}")
        return None
    if prefix == b"$":
        length = int(read_line(sock))
        if length < 0:
            return None
        data = read_exact(sock, length)
        if read_exact(sock, 2) != b"\r\n":
            raise RuntimeError("invalid bulk terminator")
        return data
    if prefix == b"*":
        count = int(read_line(sock))
        if count < 0:
            return None
        return [read_resp(sock) for _ in range(count)]
    if prefix == b"%":
        count = int(read_line(sock))
        result = {}
        for _ in range(count):
            key = read_resp(sock)
            result[key] = read_resp(sock)
        return result
    if prefix == b"~":
        count = int(read_line(sock))
        return [read_resp(sock) for _ in range(count)]
    if prefix == b">":
        count = int(read_line(sock))
        return [read_resp(sock) for _ in range(count)]
    raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")


def send_command(sock: socket.socket, *parts: bytes):
    request = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        request.append(f"${len(part)}\r\n".encode())
        request.append(part)
        request.append(b"\r\n")
    sock.sendall(b"".join(request))
    return read_resp(sock)


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"command-introspection-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            count = send_command(sock, b"COMMAND", b"COUNT")
            if not isinstance(count, int) or count <= 0:
                raise AssertionError(f"unexpected COMMAND COUNT: {count!r}")

            listed = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"CL*")
            if not isinstance(listed, list) or b"client" not in listed or b"cluster" not in listed:
                raise AssertionError(f"unexpected COMMAND LIST result: {listed!r}")

            info = send_command(sock, b"COMMAND", b"INFO", b"GET", b"FOO", b"CLIENT|ID")
            if not isinstance(info, list) or len(info) != 3:
                raise AssertionError(f"unexpected COMMAND INFO shape: {info!r}")
            if info[1] is not None:
                raise AssertionError(f"COMMAND INFO should return null for unknown command: {info!r}")
            if not isinstance(info[0], list) or info[0][0] != b"get":
                raise AssertionError(f"COMMAND INFO GET returned wrong payload: {info!r}")
            if not isinstance(info[2], list) or info[2][0] != b"client|id":
                raise AssertionError(f"COMMAND INFO CLIENT|ID returned wrong payload: {info!r}")

            bitmap_info = send_command(sock, b"COMMAND", b"INFO", b"GETBIT", b"SETBIT", b"BITCOUNT", b"BITPOS", b"BITOP", b"BITFIELD", b"BITFIELD_RO", b"PFADD", b"PFCOUNT", b"PFMERGE", b"GEOADD", b"GEODIST", b"GEOSEARCH")
            if (
                not isinstance(bitmap_info, list)
                or len(bitmap_info) != 13
                or not isinstance(bitmap_info[0], list)
                or bitmap_info[0][0] != b"getbit"
                or not isinstance(bitmap_info[1], list)
                or bitmap_info[1][0] != b"setbit"
                or not isinstance(bitmap_info[2], list)
                or bitmap_info[2][0] != b"bitcount"
                or not isinstance(bitmap_info[3], list)
                or bitmap_info[3][0] != b"bitpos"
                or not isinstance(bitmap_info[4], list)
                or bitmap_info[4][0] != b"bitop"
                or not isinstance(bitmap_info[5], list)
                or bitmap_info[5][0] != b"bitfield"
                or not isinstance(bitmap_info[6], list)
                or bitmap_info[6][0] != b"bitfield_ro"
                or not isinstance(bitmap_info[7], list)
                or bitmap_info[7][0] != b"pfadd"
                or not isinstance(bitmap_info[8], list)
                or bitmap_info[8][0] != b"pfcount"
                or not isinstance(bitmap_info[9], list)
                or bitmap_info[9][0] != b"pfmerge"
                or not isinstance(bitmap_info[10], list)
                or bitmap_info[10][0] != b"geoadd"
                or not isinstance(bitmap_info[11], list)
                or bitmap_info[11][0] != b"geodist"
                or not isinstance(bitmap_info[12], list)
                or bitmap_info[12][0] != b"geosearch"
            ):
                raise AssertionError(f"bitmap commands missing from COMMAND INFO: {bitmap_info!r}")

            script_info = send_command(sock, b"COMMAND", b"INFO", b"EVAL", b"EVALSHA", b"SCRIPT", b"SCRIPT|LOAD", b"SCRIPT|EXISTS", b"SCRIPT|FLUSH")
            if (
                not isinstance(script_info, list)
                or len(script_info) != 6
                or not isinstance(script_info[0], list)
                or script_info[0][0] != b"eval"
                or not isinstance(script_info[1], list)
                or script_info[1][0] != b"evalsha"
                or not isinstance(script_info[2], list)
                or script_info[2][0] != b"script"
                or not isinstance(script_info[3], list)
                or script_info[3][0] != b"script|load"
                or not isinstance(script_info[4], list)
                or script_info[4][0] != b"script|exists"
                or not isinstance(script_info[5], list)
                or script_info[5][0] != b"script|flush"
            ):
                raise AssertionError(f"scripting commands missing from COMMAND INFO: {script_info!r}")

            memory_info = send_command(sock, b"COMMAND", b"INFO", b"MEMORY", b"MEMORY|DOCTOR", b"MEMORY|STATS", b"MEMORY|USAGE")
            if (
                not isinstance(memory_info, list)
                or len(memory_info) != 4
                or not isinstance(memory_info[0], list)
                or memory_info[0][0] != b"memory"
                or not isinstance(memory_info[1], list)
                or memory_info[1][0] != b"memory|doctor"
                or not isinstance(memory_info[2], list)
                or memory_info[2][0] != b"memory|stats"
                or not isinstance(memory_info[3], list)
                or memory_info[3][0] != b"memory|usage"
            ):
                raise AssertionError(f"memory commands missing from COMMAND INFO: {memory_info!r}")

            slowlog_info = send_command(sock, b"COMMAND", b"INFO", b"SLOWLOG", b"SLOWLOG|GET", b"SLOWLOG|LEN", b"SLOWLOG|RESET")
            if (
                not isinstance(slowlog_info, list)
                or len(slowlog_info) != 4
                or not isinstance(slowlog_info[0], list)
                or slowlog_info[0][0] != b"slowlog"
                or not isinstance(slowlog_info[1], list)
                or slowlog_info[1][0] != b"slowlog|get"
                or not isinstance(slowlog_info[2], list)
                or slowlog_info[2][0] != b"slowlog|len"
                or not isinstance(slowlog_info[3], list)
                or slowlog_info[3][0] != b"slowlog|reset"
            ):
                raise AssertionError(f"slowlog commands missing from COMMAND INFO: {slowlog_info!r}")

            latency_info = send_command(sock, b"COMMAND", b"INFO", b"LATENCY", b"LATENCY|LATEST", b"LATENCY|HISTORY", b"LATENCY|RESET", b"LATENCY|DOCTOR")
            if (
                not isinstance(latency_info, list)
                or len(latency_info) != 5
                or not isinstance(latency_info[0], list)
                or latency_info[0][0] != b"latency"
                or not isinstance(latency_info[1], list)
                or latency_info[1][0] != b"latency|latest"
                or not isinstance(latency_info[2], list)
                or latency_info[2][0] != b"latency|history"
                or not isinstance(latency_info[3], list)
                or latency_info[3][0] != b"latency|reset"
                or not isinstance(latency_info[4], list)
                or latency_info[4][0] != b"latency|doctor"
            ):
                raise AssertionError(f"latency commands missing from COMMAND INFO: {latency_info!r}")

            monitor_info = send_command(sock, b"COMMAND", b"INFO", b"MONITOR")
            if (
                not isinstance(monitor_info, list)
                or len(monitor_info) != 1
                or not isinstance(monitor_info[0], list)
                or monitor_info[0][0] != b"monitor"
            ):
                raise AssertionError(f"monitor command missing from COMMAND INFO: {monitor_info!r}")

            stream_info = send_command(sock, b"COMMAND", b"INFO", b"XADD", b"XLEN", b"XRANGE", b"XREVRANGE", b"XREAD", b"XTRIM")
            if (
                not isinstance(stream_info, list)
                or len(stream_info) != 6
                or not isinstance(stream_info[0], list)
                or stream_info[0][0] != b"xadd"
                or not isinstance(stream_info[1], list)
                or stream_info[1][0] != b"xlen"
                or not isinstance(stream_info[2], list)
                or stream_info[2][0] != b"xrange"
                or not isinstance(stream_info[3], list)
                or stream_info[3][0] != b"xrevrange"
                or not isinstance(stream_info[4], list)
                or stream_info[4][0] != b"xread"
                or not isinstance(stream_info[5], list)
                or stream_info[5][0] != b"xtrim"
            ):
                raise AssertionError(f"stream commands missing from COMMAND INFO: {stream_info!r}")

            zset_info = send_command(sock, b"COMMAND", b"INFO", b"ZRANK", b"ZREVRANK", b"ZSCORE", b"ZMSCORE", b"ZPOPMAX", b"ZPOPMIN", b"BZPOPMAX", b"BZPOPMIN")
            if (
                not isinstance(zset_info, list)
                or len(zset_info) != 8
                or not isinstance(zset_info[0], list)
                or zset_info[0][0] != b"zrank"
                or not isinstance(zset_info[1], list)
                or zset_info[1][0] != b"zrevrank"
                or not isinstance(zset_info[2], list)
                or zset_info[2][0] != b"zscore"
                or not isinstance(zset_info[3], list)
                or zset_info[3][0] != b"zmscore"
                or not isinstance(zset_info[4], list)
                or zset_info[4][0] != b"zpopmax"
                or not isinstance(zset_info[5], list)
                or zset_info[5][0] != b"zpopmin"
                or not isinstance(zset_info[6], list)
                or zset_info[6][0] != b"bzpopmax"
                or not isinstance(zset_info[7], list)
                or zset_info[7][0] != b"bzpopmin"
            ):
                raise AssertionError(f"zset score/pop commands missing from COMMAND INFO: {zset_info!r}")

            blocking_zset_info = send_command(sock, b"COMMAND", b"INFO", b"BZMPOP")
            if (
                not isinstance(blocking_zset_info, list)
                or len(blocking_zset_info) != 1
                or not isinstance(blocking_zset_info[0], list)
                or blocking_zset_info[0][0] != b"bzmpop"
            ):
                raise AssertionError(f"BZMPOP missing from COMMAND INFO: {blocking_zset_info!r}")

            list_move_info = send_command(sock, b"COMMAND", b"INFO", b"LMOVE", b"RPOPLPUSH", b"LMPOP")
            if (
                not isinstance(list_move_info, list)
                or len(list_move_info) != 3
                or not isinstance(list_move_info[0], list)
                or list_move_info[0][0] != b"lmove"
                or not isinstance(list_move_info[1], list)
                or list_move_info[1][0] != b"rpoplpush"
                or not isinstance(list_move_info[2], list)
                or list_move_info[2][0] != b"lmpop"
            ):
                raise AssertionError(f"list move commands missing from COMMAND INFO: {list_move_info!r}")

            unsupported_info = send_command(sock, b"COMMAND", b"INFO", b"ACL", b"BLMOVE", b"CLUSTER|RESET")
            if unsupported_info != [None, None, None]:
                raise AssertionError(f"unsupported COMMAND INFO entries must be null: {unsupported_info!r}")

            client_kill_info = send_command(sock, b"COMMAND", b"INFO", b"CLIENT|KILL")
            if (
                not isinstance(client_kill_info, list)
                or len(client_kill_info) != 1
                or not isinstance(client_kill_info[0], list)
                or client_kill_info[0][0] != b"client|kill"
            ):
                raise AssertionError(f"implemented CLIENT subcommand disappeared from COMMAND INFO: {client_kill_info!r}")

            docs = send_command(sock, b"COMMAND", b"DOCS", b"GET", b"FOO")
            if not isinstance(docs, list) or len(docs) != 2 or docs[0] != b"get":
                raise AssertionError(f"unexpected COMMAND DOCS RESP2 payload: {docs!r}")
            if not isinstance(docs[1], list) or b"summary" not in docs[1]:
                raise AssertionError(f"missing COMMAND DOCS summary: {docs!r}")

            unsupported_docs = send_command(sock, b"COMMAND", b"DOCS", b"ACL", b"BLMOVE", b"CLUSTER|RESET")
            if unsupported_docs != []:
                raise AssertionError(f"unsupported COMMAND DOCS entries should be omitted: {unsupported_docs!r}")

            docs_all_resp2 = send_command(sock, b"COMMAND", b"DOCS")
            if (
                not isinstance(docs_all_resp2, list)
                or len(docs_all_resp2) <= count * 2
                or b"get" not in docs_all_resp2
                or b"client|id" not in docs_all_resp2
            ):
                raise AssertionError(f"unexpected COMMAND DOCS all RESP2 payload: {docs_all_resp2!r}")
            if b"acl" in docs_all_resp2 or b"blmove" in docs_all_resp2 or b"cluster|reset" in docs_all_resp2:
                raise AssertionError(f"unsupported commands leaked into COMMAND DOCS all RESP2: {docs_all_resp2!r}")

            listed_blocking = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"BL*")
            if (
                not isinstance(listed_blocking, list)
                or b"blpop" not in listed_blocking
                or b"blmove" in listed_blocking
                or b"blmpop" in listed_blocking
            ):
                raise AssertionError(f"unexpected blocking COMMAND LIST result: {listed_blocking!r}")

            listed_bitmap = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"BIT*")
            if (
                not isinstance(listed_bitmap, list)
                or b"bitcount" not in listed_bitmap
                or b"bitpos" not in listed_bitmap
                or b"bitop" not in listed_bitmap
                or b"bitfield" not in listed_bitmap
                or b"bitfield_ro" not in listed_bitmap
            ):
                raise AssertionError(f"unexpected COMMAND LIST bitmap result: {listed_bitmap!r}")

            listed_pf = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"PF*")
            if (
                not isinstance(listed_pf, list)
                or b"pfadd" not in listed_pf
                or b"pfcount" not in listed_pf
                or b"pfmerge" not in listed_pf
                or b"pfdebug" in listed_pf
            ):
                raise AssertionError(f"unexpected COMMAND LIST pf* result: {listed_pf!r}")

            listed_geo = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"GEO*")
            if (
                not isinstance(listed_geo, list)
                or b"geoadd" not in listed_geo
                or b"geodist" not in listed_geo
                or b"geosearch" not in listed_geo
                or b"geohash" in listed_geo
                or b"geopos" in listed_geo
                or b"georadius" in listed_geo
            ):
                raise AssertionError(f"unexpected COMMAND LIST geo* result: {listed_geo!r}")

            listed_eval = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"EVAL*")
            if (
                not isinstance(listed_eval, list)
                or b"eval" not in listed_eval
                or b"evalsha" not in listed_eval
                or b"eval_ro" in listed_eval
                or b"evalsha_ro" in listed_eval
            ):
                raise AssertionError(f"unexpected COMMAND LIST eval* result: {listed_eval!r}")

            listed_script = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"SCRIPT*")
            if (
                not isinstance(listed_script, list)
                or b"script" not in listed_script
                or b"script|load" not in listed_script
                or b"script|exists" not in listed_script
                or b"script|flush" not in listed_script
                or b"script|debug" in listed_script
                or b"script|kill" in listed_script
            ):
                raise AssertionError(f"unexpected COMMAND LIST script* result: {listed_script!r}")

            listed_memory = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"MEMORY*")
            if (
                not isinstance(listed_memory, list)
                or b"memory" not in listed_memory
                or b"memory|doctor" not in listed_memory
                or b"memory|stats" not in listed_memory
                or b"memory|usage" not in listed_memory
                or b"memory|malloc-stats" in listed_memory
                or b"memory|purge" in listed_memory
            ):
                raise AssertionError(f"unexpected COMMAND LIST memory* result: {listed_memory!r}")

            listed_slowlog = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"SLOWLOG*")
            if (
                not isinstance(listed_slowlog, list)
                or b"slowlog" not in listed_slowlog
                or b"slowlog|get" not in listed_slowlog
                or b"slowlog|len" not in listed_slowlog
                or b"slowlog|reset" not in listed_slowlog
                or b"slowlog|help" not in listed_slowlog
            ):
                raise AssertionError(f"unexpected COMMAND LIST slowlog* result: {listed_slowlog!r}")

            listed_latency = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"LATENCY*")
            if (
                not isinstance(listed_latency, list)
                or b"latency" not in listed_latency
                or b"latency|latest" not in listed_latency
                or b"latency|history" not in listed_latency
                or b"latency|reset" not in listed_latency
                or b"latency|doctor" not in listed_latency
                or b"latency|histogram" not in listed_latency
                or b"latency|graph" not in listed_latency
                or b"latency|help" not in listed_latency
            ):
                raise AssertionError(f"unexpected COMMAND LIST latency* result: {listed_latency!r}")

            listed_monitor = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"MONITOR")
            if listed_monitor != [b"monitor"]:
                raise AssertionError(f"unexpected COMMAND LIST monitor result: {listed_monitor!r}")

            listed_stream = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"X*")
            if (
                not isinstance(listed_stream, list)
                or b"xadd" not in listed_stream
                or b"xlen" not in listed_stream
                or b"xrange" not in listed_stream
                or b"xrevrange" not in listed_stream
                or b"xread" not in listed_stream
                or b"xtrim" not in listed_stream
                or b"xgroup" in listed_stream
                or b"xack" in listed_stream
                or b"xpending" in listed_stream
            ):
                raise AssertionError(f"unexpected COMMAND LIST stream result: {listed_stream!r}")

            listed_zpop = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZPOP*")
            if (
                not isinstance(listed_zpop, list)
                or b"zpopmax" not in listed_zpop
                or b"zpopmin" not in listed_zpop
                or b"zrandmember" in listed_zpop
            ):
                raise AssertionError(f"unexpected COMMAND LIST zpop result: {listed_zpop!r}")

            listed_bz = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"BZ*")
            if (
                not isinstance(listed_bz, list)
                or b"bzpopmax" not in listed_bz
                or b"bzpopmin" not in listed_bz
                or b"bzmpop" not in listed_bz
            ):
                raise AssertionError(f"unexpected COMMAND LIST bz* result: {listed_bz!r}")

            listed_lmove = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"L*MOVE")
            if (
                not isinstance(listed_lmove, list)
                or b"lmove" not in listed_lmove
                or b"lmpop" in listed_lmove
            ):
                raise AssertionError(f"unexpected COMMAND LIST lmove result: {listed_lmove!r}")

            help_reply = send_command(sock, b"COMMAND", b"HELP")
            if not isinstance(help_reply, list) or b"GETKEYS <full-command>" not in help_reply:
                raise AssertionError(f"unexpected COMMAND HELP: {help_reply!r}")

            resp3_hello = send_command(sock, b"HELLO", b"3")
            if not isinstance(resp3_hello, dict) or resp3_hello.get(b"proto") != 3:
                raise AssertionError(f"unexpected HELLO 3 response: {resp3_hello!r}")

            resp3_docs = send_command(sock, b"COMMAND", b"DOCS", b"GET")
            if not isinstance(resp3_docs, dict):
                raise AssertionError(f"COMMAND DOCS should return RESP3 map: {resp3_docs!r}")
            get_docs = resp3_docs.get(b"get")
            if not isinstance(get_docs, dict) or get_docs.get(b"group") != b"string":
                raise AssertionError(f"unexpected RESP3 COMMAND DOCS GET payload: {resp3_docs!r}")

            docs_all = send_command(sock, b"COMMAND", b"DOCS")
            if (
                not isinstance(docs_all, dict)
                or len(docs_all) <= count
                or not isinstance(docs_all.get(b"get"), dict)
                or not isinstance(docs_all.get(b"client|id"), dict)
            ):
                raise AssertionError(f"unexpected COMMAND DOCS all RESP3 payload: {docs_all!r}")
            if b"acl" in docs_all or b"blmove" in docs_all or b"cluster|reset" in docs_all:
                raise AssertionError(f"unsupported commands leaked into COMMAND DOCS all RESP3: {docs_all!r}")

            getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"SORT", b"mylist", b"ALPHA", b"STORE", b"out")
            if getkeys != [b"mylist", b"out"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS result: {getkeys!r}")

            getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"RENAME", b"src", b"dst")
            if not isinstance(getkeysandflags, list) or len(getkeysandflags) != 2:
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS shape: {getkeysandflags!r}")
            if getkeysandflags[0][0] != b"src" or getkeysandflags[1][0] != b"dst":
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS keys: {getkeysandflags!r}")

            memory_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"MEMORY", b"USAGE", b"mkey")
            if memory_getkeys != [b"mkey"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS MEMORY USAGE result: {memory_getkeys!r}")

            memory_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"MEMORY", b"USAGE", b"mkey")
            if (
                not isinstance(memory_getkeysandflags, list)
                or len(memory_getkeysandflags) != 1
                or memory_getkeysandflags[0][0] != b"mkey"
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS MEMORY USAGE result: {memory_getkeysandflags!r}")

            bad_arity_error = None
            try:
                send_command(sock, b"COMMAND", b"GETKEYS", b"GET")
            except RespError as exc:
                bad_arity_error = str(exc)
            if bad_arity_error is None or "Invalid number of arguments" not in bad_arity_error:
                raise AssertionError(f"unexpected COMMAND GETKEYS arity result: {bad_arity_error!r}")

            missing_error = None
            try:
                send_command(sock, b"COMMAND", b"GETKEYS")
            except RespError as exc:
                missing_error = str(exc)
            if missing_error is None or "wrong number of arguments" not in missing_error:
                raise AssertionError(f"unexpected COMMAND GETKEYS missing-args result: {missing_error!r}")

            if send_command(sock, b"QUIT") != "OK":
                raise AssertionError("QUIT failed")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/command_introspection: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/command_introspection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
