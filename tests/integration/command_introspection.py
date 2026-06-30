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


def is_lower_hex(data: bytes, expected_len: int) -> bool:
    return len(data) == expected_len and all((48 <= ch <= 57) or (97 <= ch <= 102) for ch in data)


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

            listed_acl = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ACL*")
            if (
                not isinstance(listed_acl, list)
                or b"acl" not in listed_acl
                or b"acl|cat" not in listed_acl
                or b"acl|deluser" not in listed_acl
                or b"acl|dryrun" not in listed_acl
                or b"acl|genpass" not in listed_acl
                or b"acl|getuser" not in listed_acl
                or b"acl|help" not in listed_acl
                or b"acl|list" not in listed_acl
                or b"acl|load" not in listed_acl
                or b"acl|log" not in listed_acl
                or b"acl|save" not in listed_acl
                or b"acl|setuser" not in listed_acl
                or b"acl|users" not in listed_acl
                or b"acl|whoami" not in listed_acl
                or b"function|load" in listed_acl
            ):
                raise AssertionError(f"unexpected COMMAND LIST acl* result: {listed_acl!r}")

            listed_copy = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"CO*")
            if not isinstance(listed_copy, list) or b"copy" not in listed_copy:
                raise AssertionError(f"unexpected COMMAND LIST co* result: {listed_copy!r}")

            listed_delex = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"DE*")
            if not isinstance(listed_delex, list) or b"delex" not in listed_delex:
                raise AssertionError(f"unexpected COMMAND LIST de* result: {listed_delex!r}")

            listed_digest = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"DI*")
            if not isinstance(listed_digest, list) or b"digest" not in listed_digest:
                raise AssertionError(f"unexpected COMMAND LIST di* result: {listed_digest!r}")

            listed_mset = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"MSET*")
            if not isinstance(listed_mset, list) or b"mset" not in listed_mset or b"msetex" not in listed_mset or b"msetnx" not in listed_mset:
                raise AssertionError(f"unexpected COMMAND LIST mset* result: {listed_mset!r}")

            listed_lcs = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"LCS")
            if not isinstance(listed_lcs, list) or listed_lcs != [b"lcs"]:
                raise AssertionError(f"unexpected COMMAND LIST lcs result: {listed_lcs!r}")

            listed_increx = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"INCREX")
            if not isinstance(listed_increx, list) or listed_increx != [b"increx"]:
                raise AssertionError(f"unexpected COMMAND LIST increx result: {listed_increx!r}")

            listed_substr = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"SUBSTR")
            if not isinstance(listed_substr, list) or listed_substr != [b"substr"]:
                raise AssertionError(f"unexpected COMMAND LIST substr result: {listed_substr!r}")

            listed_hget = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"HGET*")
            if not isinstance(listed_hget, list) or b"hget" not in listed_hget or b"hgetdel" not in listed_hget:
                raise AssertionError(f"unexpected COMMAND LIST hget* result: {listed_hget!r}")

            listed_restore = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"RESTORE*")
            if (
                not isinstance(listed_restore, list)
                or b"restore" not in listed_restore
                or b"restore-asking" not in listed_restore
            ):
                raise AssertionError(f"unexpected COMMAND LIST restore* result: {listed_restore!r}")

            listed_asking = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ASK*")
            if not isinstance(listed_asking, list) or listed_asking != [b"asking"]:
                raise AssertionError(f"unexpected COMMAND LIST ask* result: {listed_asking!r}")

            listed_read = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"READ*")
            if not isinstance(listed_read, list) or b"readonly" not in listed_read or b"readwrite" not in listed_read:
                raise AssertionError(f"unexpected COMMAND LIST read* result: {listed_read!r}")

            acl_help = send_command(sock, b"ACL", b"HELP")
            if not isinstance(acl_help, list) or b"CAT [<category>]" not in acl_help or b"WHOAMI" not in acl_help:
                raise AssertionError(f"unexpected ACL HELP: {acl_help!r}")
            acl_cat = send_command(sock, b"ACL", b"CAT")
            if not isinstance(acl_cat, list) or b"string" not in acl_cat or b"transaction" not in acl_cat:
                raise AssertionError(f"unexpected ACL CAT: {acl_cat!r}")
            acl_cat_string = send_command(sock, b"ACL", b"CAT", b"string")
            if not isinstance(acl_cat_string, list) or b"get" not in acl_cat_string or b"set" not in acl_cat_string:
                raise AssertionError(f"unexpected ACL CAT string: {acl_cat_string!r}")
            acl_getuser = send_command(sock, b"ACL", b"GETUSER", b"default")
            if (
                not isinstance(acl_getuser, list)
                or acl_getuser[0] != b"flags"
                or acl_getuser[1] != [b"on", b"nopass"]
                or b"commands" not in acl_getuser
                or b"+@all" not in acl_getuser
            ):
                raise AssertionError(f"unexpected ACL GETUSER default: {acl_getuser!r}")
            acl_getuser_missing = send_command(sock, b"ACL", b"GETUSER", b"missing")
            if acl_getuser_missing is not None:
                raise AssertionError(f"unexpected ACL GETUSER missing: {acl_getuser_missing!r}")
            acl_log = send_command(sock, b"ACL", b"LOG")
            if acl_log != []:
                raise AssertionError(f"unexpected ACL LOG: {acl_log!r}")
            acl_log_count = send_command(sock, b"ACL", b"LOG", b"10")
            if acl_log_count != []:
                raise AssertionError(f"unexpected ACL LOG count: {acl_log_count!r}")
            acl_log_reset = send_command(sock, b"ACL", b"LOG", b"RESET")
            if acl_log_reset != "OK":
                raise AssertionError(f"unexpected ACL LOG RESET: {acl_log_reset!r}")
            acl_genpass = send_command(sock, b"ACL", b"GENPASS")
            if not isinstance(acl_genpass, bytes) or not is_lower_hex(acl_genpass, 64):
                raise AssertionError(f"unexpected ACL GENPASS: {acl_genpass!r}")
            acl_genpass_bits = send_command(sock, b"ACL", b"GENPASS", b"8")
            if not isinstance(acl_genpass_bits, bytes) or not is_lower_hex(acl_genpass_bits, 2):
                raise AssertionError(f"unexpected ACL GENPASS bits: {acl_genpass_bits!r}")
            try:
                send_command(sock, b"ACL", b"SAVE")
                raise AssertionError("expected ACL SAVE to fail without aclfile")
            except RespError as exc:
                if "not configured to use an ACL file" not in str(exc):
                    raise
            try:
                send_command(sock, b"ACL", b"LOAD")
                raise AssertionError("expected ACL LOAD to fail without aclfile")
            except RespError as exc:
                if "not configured to use an ACL file" not in str(exc):
                    raise
            acl_deluser_missing = send_command(sock, b"ACL", b"DELUSER", b"missing")
            if acl_deluser_missing != 0:
                raise AssertionError(f"unexpected ACL DELUSER missing: {acl_deluser_missing!r}")
            try:
                send_command(sock, b"ACL", b"DELUSER", b"default")
                raise AssertionError("expected ACL DELUSER default to fail")
            except RespError as exc:
                if "default' user cannot be removed" not in str(exc):
                    raise
            acl_dryrun_get = send_command(sock, b"ACL", b"DRYRUN", b"default", b"GET", b"missing")
            if acl_dryrun_get != "OK":
                raise AssertionError(f"unexpected ACL DRYRUN default GET: {acl_dryrun_get!r}")
            try:
                send_command(sock, b"ACL", b"DRYRUN", b"missing", b"GET", b"k")
                raise AssertionError("expected ACL DRYRUN missing user to fail")
            except RespError as exc:
                if "User 'missing' not found" not in str(exc):
                    raise
            acl_setuser_default = send_command(sock, b"ACL", b"SETUSER", b"default", b"on", b"nopass", b"~*", b"&*", b"+@all")
            if acl_setuser_default != "OK":
                raise AssertionError(f"unexpected ACL SETUSER default: {acl_setuser_default!r}")
            try:
                send_command(sock, b"ACL", b"SETUSER", b"default", b"invalidattr")
                raise AssertionError("expected ACL SETUSER invalid modifier to fail")
            except RespError as exc:
                if "Error in ACL SETUSER modifier 'invalidattr': Syntax error" not in str(exc):
                    raise
            acl_whoami = send_command(sock, b"ACL", b"WHOAMI")
            if acl_whoami != b"default":
                raise AssertionError(f"unexpected ACL WHOAMI: {acl_whoami!r}")
            acl_users = send_command(sock, b"ACL", b"USERS")
            if acl_users != [b"default"]:
                raise AssertionError(f"unexpected ACL USERS: {acl_users!r}")
            acl_list = send_command(sock, b"ACL", b"LIST")
            if acl_list != [b"user default on nopass ~* &* +@all"]:
                raise AssertionError(f"unexpected ACL LIST: {acl_list!r}")

            info = send_command(sock, b"COMMAND", b"INFO", b"GET", b"FOO", b"CLIENT|ID", b"COPY", b"DELEX", b"DIGEST", b"HGETDEL", b"RESTORE-ASKING", b"HRANDFIELD", b"WAITAOF", b"SWAPDB", b"LOLWUT", b"REPLCONF", b"SLAVEOF", b"SYNC", b"DEBUG", b"FAILOVER")
            if not isinstance(info, list) or len(info) != 17:
                raise AssertionError(f"unexpected COMMAND INFO shape: {info!r}")
            if info[1] is not None:
                raise AssertionError(f"COMMAND INFO should return null for unknown command: {info!r}")
            if not isinstance(info[0], list) or info[0][0] != b"get":
                raise AssertionError(f"COMMAND INFO GET returned wrong payload: {info!r}")
            if not isinstance(info[2], list) or info[2][0] != b"client|id":
                raise AssertionError(f"COMMAND INFO CLIENT|ID returned wrong payload: {info!r}")
            if not isinstance(info[3], list) or info[3][0] != b"copy":
                raise AssertionError(f"COMMAND INFO COPY returned wrong payload: {info!r}")
            if not isinstance(info[4], list) or info[4][0] != b"delex":
                raise AssertionError(f"COMMAND INFO DELEX returned wrong payload: {info!r}")
            if not isinstance(info[5], list) or info[5][0] != b"digest":
                raise AssertionError(f"COMMAND INFO DIGEST returned wrong payload: {info!r}")
            if not isinstance(info[6], list) or info[6][0] != b"hgetdel":
                raise AssertionError(f"COMMAND INFO HGETDEL returned wrong payload: {info!r}")
            if not isinstance(info[7], list) or info[7][0] != b"restore-asking":
                raise AssertionError(f"COMMAND INFO RESTORE-ASKING returned wrong payload: {info!r}")
            if not isinstance(info[8], list) or info[8][0] != b"hrandfield":
                raise AssertionError(f"COMMAND INFO HRANDFIELD returned wrong payload: {info!r}")
            if not isinstance(info[9], list) or info[9][0] != b"waitaof":
                raise AssertionError(f"COMMAND INFO WAITAOF returned wrong payload: {info!r}")
            if not isinstance(info[10], list) or info[10][0] != b"swapdb":
                raise AssertionError(f"COMMAND INFO SWAPDB returned wrong payload: {info!r}")
            if not isinstance(info[11], list) or info[11][0] != b"lolwut":
                raise AssertionError(f"COMMAND INFO LOLWUT returned wrong payload: {info!r}")
            if not isinstance(info[12], list) or info[12][0] != b"replconf":
                raise AssertionError(f"COMMAND INFO REPLCONF returned wrong payload: {info!r}")
            if not isinstance(info[13], list) or info[13][0] != b"slaveof":
                raise AssertionError(f"COMMAND INFO SLAVEOF returned wrong payload: {info!r}")
            if not isinstance(info[14], list) or info[14][0] != b"sync":
                raise AssertionError(f"COMMAND INFO SYNC returned wrong payload: {info!r}")
            if not isinstance(info[15], list) or info[15][0] != b"debug":
                raise AssertionError(f"COMMAND INFO DEBUG returned wrong payload: {info!r}")
            if not isinstance(info[16], list) or info[16][0] != b"failover":
                raise AssertionError(f"COMMAND INFO FAILOVER returned wrong payload: {info!r}")

            msetex_info = send_command(sock, b"COMMAND", b"INFO", b"MSETEX")
            if (
                not isinstance(msetex_info, list)
                or len(msetex_info) != 1
                or not isinstance(msetex_info[0], list)
                or msetex_info[0][0] != b"msetex"
            ):
                raise AssertionError(f"COMMAND INFO MSETEX returned wrong payload: {msetex_info!r}")

            lcs_info = send_command(sock, b"COMMAND", b"INFO", b"LCS")
            if (
                not isinstance(lcs_info, list)
                or len(lcs_info) != 1
                or not isinstance(lcs_info[0], list)
                or lcs_info[0][0] != b"lcs"
            ):
                raise AssertionError(f"COMMAND INFO LCS returned wrong payload: {lcs_info!r}")

            increx_info = send_command(sock, b"COMMAND", b"INFO", b"INCREX")
            if (
                not isinstance(increx_info, list)
                or len(increx_info) != 1
                or not isinstance(increx_info[0], list)
                or increx_info[0][0] != b"increx"
            ):
                raise AssertionError(f"COMMAND INFO INCREX returned wrong payload: {increx_info!r}")

            substr_info = send_command(sock, b"COMMAND", b"INFO", b"SUBSTR")
            if (
                not isinstance(substr_info, list)
                or len(substr_info) != 1
                or not isinstance(substr_info[0], list)
                or substr_info[0][0] != b"substr"
            ):
                raise AssertionError(f"COMMAND INFO SUBSTR returned wrong payload: {substr_info!r}")

            cluster_mode_info = send_command(sock, b"COMMAND", b"INFO", b"ASKING", b"READONLY", b"READWRITE")
            if (
                not isinstance(cluster_mode_info, list)
                or len(cluster_mode_info) != 3
                or not isinstance(cluster_mode_info[0], list)
                or cluster_mode_info[0][0] != b"asking"
                or not isinstance(cluster_mode_info[1], list)
                or cluster_mode_info[1][0] != b"readonly"
                or not isinstance(cluster_mode_info[2], list)
                or cluster_mode_info[2][0] != b"readwrite"
            ):
                raise AssertionError(f"COMMAND INFO cluster mode commands returned wrong payload: {cluster_mode_info!r}")

            bitmap_info = send_command(sock, b"COMMAND", b"INFO", b"GETBIT", b"SETBIT", b"BITCOUNT", b"BITPOS", b"BITOP", b"BITFIELD", b"BITFIELD_RO", b"PFADD", b"PFCOUNT", b"PFMERGE", b"PFSELFTEST", b"PFDEBUG", b"GEOADD", b"GEODIST", b"GEOHASH", b"GEOPOS", b"GEORADIUS", b"GEORADIUS_RO", b"GEORADIUSBYMEMBER", b"GEORADIUSBYMEMBER_RO", b"GEOSEARCH", b"GEOSEARCHSTORE")
            if (
                not isinstance(bitmap_info, list)
                or len(bitmap_info) != 22
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
                or bitmap_info[10][0] != b"pfselftest"
                or not isinstance(bitmap_info[11], list)
                or bitmap_info[11][0] != b"pfdebug"
                or not isinstance(bitmap_info[12], list)
                or bitmap_info[12][0] != b"geoadd"
                or not isinstance(bitmap_info[13], list)
                or bitmap_info[13][0] != b"geodist"
                or not isinstance(bitmap_info[14], list)
                or bitmap_info[14][0] != b"geohash"
                or not isinstance(bitmap_info[15], list)
                or bitmap_info[15][0] != b"geopos"
                or not isinstance(bitmap_info[16], list)
                or bitmap_info[16][0] != b"georadius"
                or not isinstance(bitmap_info[17], list)
                or bitmap_info[17][0] != b"georadius_ro"
                or not isinstance(bitmap_info[18], list)
                or bitmap_info[18][0] != b"georadiusbymember"
                or not isinstance(bitmap_info[19], list)
                or bitmap_info[19][0] != b"georadiusbymember_ro"
                or not isinstance(bitmap_info[20], list)
                or bitmap_info[20][0] != b"geosearch"
                or not isinstance(bitmap_info[21], list)
                or bitmap_info[21][0] != b"geosearchstore"
            ):
                raise AssertionError(f"bitmap commands missing from COMMAND INFO: {bitmap_info!r}")

            script_info = send_command(sock, b"COMMAND", b"INFO", b"EVAL", b"EVAL_RO", b"EVALSHA", b"EVALSHA_RO", b"FCALL", b"FCALL_RO", b"SCRIPT", b"SCRIPT|LOAD", b"SCRIPT|EXISTS", b"SCRIPT|FLUSH", b"SCRIPT|KILL", b"SCRIPT|DEBUG")
            if (
                not isinstance(script_info, list)
                or len(script_info) != 12
                or not isinstance(script_info[0], list)
                or script_info[0][0] != b"eval"
                or not isinstance(script_info[1], list)
                or script_info[1][0] != b"eval_ro"
                or not isinstance(script_info[2], list)
                or script_info[2][0] != b"evalsha"
                or not isinstance(script_info[3], list)
                or script_info[3][0] != b"evalsha_ro"
                or not isinstance(script_info[4], list)
                or script_info[4][0] != b"fcall"
                or not isinstance(script_info[5], list)
                or script_info[5][0] != b"fcall_ro"
                or not isinstance(script_info[6], list)
                or script_info[6][0] != b"script"
                or not isinstance(script_info[7], list)
                or script_info[7][0] != b"script|load"
                or not isinstance(script_info[8], list)
                or script_info[8][0] != b"script|exists"
                or not isinstance(script_info[9], list)
                or script_info[9][0] != b"script|flush"
                or not isinstance(script_info[10], list)
                or script_info[10][0] != b"script|kill"
                or not isinstance(script_info[11], list)
                or script_info[11][0] != b"script|debug"
            ):
                raise AssertionError(f"scripting commands missing from COMMAND INFO: {script_info!r}")

            memory_info = send_command(sock, b"COMMAND", b"INFO", b"MEMORY", b"MEMORY|DOCTOR", b"MEMORY|MALLOC-STATS", b"MEMORY|PURGE", b"MEMORY|STATS", b"MEMORY|USAGE")
            if (
                not isinstance(memory_info, list)
                or len(memory_info) != 6
                or not isinstance(memory_info[0], list)
                or memory_info[0][0] != b"memory"
                or not isinstance(memory_info[1], list)
                or memory_info[1][0] != b"memory|doctor"
                or not isinstance(memory_info[2], list)
                or memory_info[2][0] != b"memory|malloc-stats"
                or not isinstance(memory_info[3], list)
                or memory_info[3][0] != b"memory|purge"
                or not isinstance(memory_info[4], list)
                or memory_info[4][0] != b"memory|stats"
                or not isinstance(memory_info[5], list)
                or memory_info[5][0] != b"memory|usage"
            ):
                raise AssertionError(f"memory commands missing from COMMAND INFO: {memory_info!r}")

            module_info = send_command(sock, b"COMMAND", b"INFO", b"MODULE", b"MODULE|HELP", b"MODULE|LIST", b"MODULE|LOAD", b"MODULE|LOADEX", b"MODULE|UNLOAD")
            if (
                not isinstance(module_info, list)
                or len(module_info) != 6
                or not isinstance(module_info[0], list)
                or module_info[0][0] != b"module"
                or not isinstance(module_info[1], list)
                or module_info[1][0] != b"module|help"
                or not isinstance(module_info[2], list)
                or module_info[2][0] != b"module|list"
                or not isinstance(module_info[3], list)
                or module_info[3][0] != b"module|load"
                or not isinstance(module_info[4], list)
                or module_info[4][0] != b"module|loadex"
                or not isinstance(module_info[5], list)
                or module_info[5][0] != b"module|unload"
            ):
                raise AssertionError(f"module commands missing from COMMAND INFO: {module_info!r}")

            function_info = send_command(sock, b"COMMAND", b"INFO", b"FUNCTION", b"FUNCTION|HELP", b"FUNCTION|LIST", b"FUNCTION|STATS", b"FUNCTION|FLUSH", b"FUNCTION|DELETE", b"FUNCTION|LOAD", b"FUNCTION|DUMP", b"FUNCTION|RESTORE", b"FUNCTION|KILL")
            if (
                not isinstance(function_info, list)
                or len(function_info) != 10
                or not isinstance(function_info[0], list)
                or function_info[0][0] != b"function"
                or not isinstance(function_info[1], list)
                or function_info[1][0] != b"function|help"
                or not isinstance(function_info[2], list)
                or function_info[2][0] != b"function|list"
                or not isinstance(function_info[3], list)
                or function_info[3][0] != b"function|stats"
                or not isinstance(function_info[4], list)
                or function_info[4][0] != b"function|flush"
                or not isinstance(function_info[5], list)
                or function_info[5][0] != b"function|delete"
                or not isinstance(function_info[6], list)
                or function_info[6][0] != b"function|load"
                or not isinstance(function_info[7], list)
                or function_info[7][0] != b"function|dump"
                or not isinstance(function_info[8], list)
                or function_info[8][0] != b"function|restore"
                or not isinstance(function_info[9], list)
                or function_info[9][0] != b"function|kill"
            ):
                raise AssertionError(f"function commands missing from COMMAND INFO: {function_info!r}")

            acl_info = send_command(sock, b"COMMAND", b"INFO", b"ACL", b"ACL|CAT", b"ACL|DELUSER", b"ACL|DRYRUN", b"ACL|GENPASS", b"ACL|GETUSER", b"ACL|HELP", b"ACL|LIST", b"ACL|LOAD", b"ACL|LOG", b"ACL|SAVE", b"ACL|SETUSER", b"ACL|USERS", b"ACL|WHOAMI")
            if (
                not isinstance(acl_info, list)
                or len(acl_info) != 14
                or not isinstance(acl_info[0], list)
                or acl_info[0][0] != b"acl"
                or not isinstance(acl_info[1], list)
                or acl_info[1][0] != b"acl|cat"
                or not isinstance(acl_info[2], list)
                or acl_info[2][0] != b"acl|deluser"
                or not isinstance(acl_info[3], list)
                or acl_info[3][0] != b"acl|dryrun"
                or not isinstance(acl_info[4], list)
                or acl_info[4][0] != b"acl|genpass"
                or not isinstance(acl_info[5], list)
                or acl_info[5][0] != b"acl|getuser"
                or not isinstance(acl_info[6], list)
                or acl_info[6][0] != b"acl|help"
                or not isinstance(acl_info[7], list)
                or acl_info[7][0] != b"acl|list"
                or not isinstance(acl_info[8], list)
                or acl_info[8][0] != b"acl|load"
                or not isinstance(acl_info[9], list)
                or acl_info[9][0] != b"acl|log"
                or not isinstance(acl_info[10], list)
                or acl_info[10][0] != b"acl|save"
                or not isinstance(acl_info[11], list)
                or acl_info[11][0] != b"acl|setuser"
                or not isinstance(acl_info[12], list)
                or acl_info[12][0] != b"acl|users"
                or not isinstance(acl_info[13], list)
                or acl_info[13][0] != b"acl|whoami"
            ):
                raise AssertionError(f"acl commands missing from COMMAND INFO: {acl_info!r}")

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

            stream_info = send_command(sock, b"COMMAND", b"INFO", b"XACK", b"XNACK", b"XADD", b"XCFGSET", b"XIDMPRECORD", b"XCLAIM", b"XDEL", b"XGROUP", b"XINFO", b"XLEN", b"XPENDING", b"XRANGE", b"XREVRANGE", b"XREAD", b"XTRIM")
            if (
                not isinstance(stream_info, list)
                or len(stream_info) != 15
                or not isinstance(stream_info[0], list)
                or stream_info[0][0] != b"xack"
                or not isinstance(stream_info[1], list)
                or stream_info[1][0] != b"xnack"
                or not isinstance(stream_info[2], list)
                or stream_info[2][0] != b"xadd"
                or not isinstance(stream_info[3], list)
                or stream_info[3][0] != b"xcfgset"
                or not isinstance(stream_info[4], list)
                or stream_info[4][0] != b"xidmprecord"
                or not isinstance(stream_info[5], list)
                or stream_info[5][0] != b"xclaim"
                or not isinstance(stream_info[6], list)
                or stream_info[6][0] != b"xdel"
                or not isinstance(stream_info[7], list)
                or stream_info[7][0] != b"xgroup"
                or not isinstance(stream_info[8], list)
                or stream_info[8][0] != b"xinfo"
                or not isinstance(stream_info[9], list)
                or stream_info[9][0] != b"xlen"
                or not isinstance(stream_info[10], list)
                or stream_info[10][0] != b"xpending"
                or not isinstance(stream_info[11], list)
                or stream_info[11][0] != b"xrange"
                or not isinstance(stream_info[12], list)
                or stream_info[12][0] != b"xrevrange"
                or not isinstance(stream_info[13], list)
                or stream_info[13][0] != b"xread"
                or not isinstance(stream_info[14], list)
                or stream_info[14][0] != b"xtrim"
            ):
                raise AssertionError(f"stream commands missing from COMMAND INFO: {stream_info!r}")

            xgroup_help = send_command(sock, b"XGROUP", b"HELP")
            if (
                not isinstance(xgroup_help, list)
                or b"XGROUP HELP" not in xgroup_help
                or b"XGROUP CREATE <key> <groupname> <id-or-$> [MKSTREAM]" not in xgroup_help
            ):
                raise AssertionError(f"unexpected XGROUP HELP: {xgroup_help!r}")

            xinfo_help = send_command(sock, b"XINFO", b"HELP")
            if (
                not isinstance(xinfo_help, list)
                or b"XINFO HELP" not in xinfo_help
                or b"XINFO STREAM <key> [FULL [COUNT <count>]]" not in xinfo_help
            ):
                raise AssertionError(f"unexpected XINFO HELP: {xinfo_help!r}")

            zset_info = send_command(sock, b"COMMAND", b"INFO", b"ZRANGE", b"ZRANK", b"ZREVRANK", b"ZSCORE", b"ZMSCORE", b"ZDIFF", b"ZDIFFSTORE", b"ZINTER", b"ZINTERCARD", b"ZINTERSTORE", b"ZUNION", b"ZUNIONSTORE", b"ZPOPMAX", b"ZPOPMIN", b"ZRANDMEMBER", b"ZMPOP", b"ZLEXCOUNT", b"ZRANGEBYLEX", b"ZRANGESTORE", b"ZREMRANGEBYLEX", b"ZREVRANGE", b"ZREVRANGEBYLEX", b"BZPOPMAX", b"BZPOPMIN")
            if (
                not isinstance(zset_info, list)
                or len(zset_info) != 24
                or not isinstance(zset_info[0], list)
                or zset_info[0][0] != b"zrange"
                or zset_info[0][1] != -4
                or not isinstance(zset_info[1], list)
                or zset_info[1][0] != b"zrank"
                or not isinstance(zset_info[2], list)
                or zset_info[2][0] != b"zrevrank"
                or not isinstance(zset_info[3], list)
                or zset_info[3][0] != b"zscore"
                or not isinstance(zset_info[4], list)
                or zset_info[4][0] != b"zmscore"
                or not isinstance(zset_info[5], list)
                or zset_info[5][0] != b"zdiff"
                or not isinstance(zset_info[6], list)
                or zset_info[6][0] != b"zdiffstore"
                or not isinstance(zset_info[7], list)
                or zset_info[7][0] != b"zinter"
                or not isinstance(zset_info[8], list)
                or zset_info[8][0] != b"zintercard"
                or not isinstance(zset_info[9], list)
                or zset_info[9][0] != b"zinterstore"
                or not isinstance(zset_info[10], list)
                or zset_info[10][0] != b"zunion"
                or not isinstance(zset_info[11], list)
                or zset_info[11][0] != b"zunionstore"
                or not isinstance(zset_info[12], list)
                or zset_info[12][0] != b"zpopmax"
                or not isinstance(zset_info[13], list)
                or zset_info[13][0] != b"zpopmin"
                or not isinstance(zset_info[14], list)
                or zset_info[14][0] != b"zrandmember"
                or not isinstance(zset_info[15], list)
                or zset_info[15][0] != b"zmpop"
                or not isinstance(zset_info[16], list)
                or zset_info[16][0] != b"zlexcount"
                or not isinstance(zset_info[17], list)
                or zset_info[17][0] != b"zrangebylex"
                or not isinstance(zset_info[18], list)
                or zset_info[18][0] != b"zrangestore"
                or not isinstance(zset_info[19], list)
                or zset_info[19][0] != b"zremrangebylex"
                or not isinstance(zset_info[20], list)
                or zset_info[20][0] != b"zrevrange"
                or not isinstance(zset_info[21], list)
                or zset_info[21][0] != b"zrevrangebylex"
                or not isinstance(zset_info[22], list)
                or zset_info[22][0] != b"bzpopmax"
                or not isinstance(zset_info[23], list)
                or zset_info[23][0] != b"bzpopmin"
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

            list_move_info = send_command(sock, b"COMMAND", b"INFO", b"LMOVE", b"BLMOVE", b"RPOPLPUSH", b"LMPOP", b"BLMPOP")
            if (
                not isinstance(list_move_info, list)
                or len(list_move_info) != 5
                or not isinstance(list_move_info[0], list)
                or list_move_info[0][0] != b"lmove"
                or not isinstance(list_move_info[1], list)
                or list_move_info[1][0] != b"blmove"
                or not isinstance(list_move_info[2], list)
                or list_move_info[2][0] != b"rpoplpush"
                or not isinstance(list_move_info[3], list)
                or list_move_info[3][0] != b"lmpop"
                or not isinstance(list_move_info[4], list)
                or list_move_info[4][0] != b"blmpop"
            ):
                raise AssertionError(f"list move commands missing from COMMAND INFO: {list_move_info!r}")

            unsupported_info = send_command(sock, b"COMMAND", b"INFO", b"CLUSTER|RESET")
            if unsupported_info != [None]:
                raise AssertionError(f"unsupported COMMAND INFO entries must be null: {unsupported_info!r}")

            client_kill_info = send_command(sock, b"COMMAND", b"INFO", b"CLIENT|KILL", b"CLIENT|UNBLOCK", b"CLIENT|REPLY", b"CLIENT|CACHING", b"CLIENT|NO-EVICT", b"CLIENT|NO-TOUCH")
            if (
                not isinstance(client_kill_info, list)
                or len(client_kill_info) != 6
                or not isinstance(client_kill_info[0], list)
                or client_kill_info[0][0] != b"client|kill"
                or not isinstance(client_kill_info[1], list)
                or client_kill_info[1][0] != b"client|unblock"
                or not isinstance(client_kill_info[2], list)
                or client_kill_info[2][0] != b"client|reply"
                or not isinstance(client_kill_info[3], list)
                or client_kill_info[3][0] != b"client|caching"
                or not isinstance(client_kill_info[4], list)
                or client_kill_info[4][0] != b"client|no-evict"
                or not isinstance(client_kill_info[5], list)
                or client_kill_info[5][0] != b"client|no-touch"
            ):
                raise AssertionError(f"implemented CLIENT subcommand disappeared from COMMAND INFO: {client_kill_info!r}")

            docs = send_command(sock, b"COMMAND", b"DOCS", b"GET", b"FOO")
            if not isinstance(docs, list) or len(docs) != 2 or docs[0] != b"get":
                raise AssertionError(f"unexpected COMMAND DOCS RESP2 payload: {docs!r}")
            if not isinstance(docs[1], list) or b"summary" not in docs[1]:
                raise AssertionError(f"missing COMMAND DOCS summary: {docs!r}")

            unsupported_docs = send_command(sock, b"COMMAND", b"DOCS", b"CLUSTER|RESET")
            if unsupported_docs != []:
                raise AssertionError(f"unsupported COMMAND DOCS entries should be omitted: {unsupported_docs!r}")

            docs_all_resp2 = send_command(sock, b"COMMAND", b"DOCS")
            if (
                not isinstance(docs_all_resp2, list)
                or len(docs_all_resp2) <= count * 2
                or b"get" not in docs_all_resp2
                or b"client|reply" not in docs_all_resp2
                or b"client|unblock" not in docs_all_resp2
                or b"client|caching" not in docs_all_resp2
                or b"client|id" not in docs_all_resp2
                or b"client|no-evict" not in docs_all_resp2
                or b"client|no-touch" not in docs_all_resp2
                or b"acl" not in docs_all_resp2
                or b"acl|cat" not in docs_all_resp2
                or b"acl|deluser" not in docs_all_resp2
                or b"acl|dryrun" not in docs_all_resp2
                or b"acl|genpass" not in docs_all_resp2
                or b"acl|getuser" not in docs_all_resp2
                or b"acl|help" not in docs_all_resp2
                or b"acl|list" not in docs_all_resp2
                or b"acl|load" not in docs_all_resp2
                or b"acl|log" not in docs_all_resp2
                or b"acl|save" not in docs_all_resp2
                or b"acl|setuser" not in docs_all_resp2
                or b"acl|users" not in docs_all_resp2
                or b"acl|whoami" not in docs_all_resp2
                or b"function|load" not in docs_all_resp2
                or b"hrandfield" not in docs_all_resp2
                or b"waitaof" not in docs_all_resp2
                or b"swapdb" not in docs_all_resp2
                or b"lolwut" not in docs_all_resp2
                or b"replconf" not in docs_all_resp2
                or b"debug" not in docs_all_resp2
                or b"failover" not in docs_all_resp2
                or b"pfselftest" not in docs_all_resp2
                or b"pfdebug" not in docs_all_resp2
                or b"blmove" not in docs_all_resp2
                or b"blmpop" not in docs_all_resp2
                or b"zmpop" not in docs_all_resp2
                or b"zdiff" not in docs_all_resp2
                or b"zdiffstore" not in docs_all_resp2
                or b"zinter" not in docs_all_resp2
                or b"zintercard" not in docs_all_resp2
                or b"zinterstore" not in docs_all_resp2
                or b"zunion" not in docs_all_resp2
                or b"zunionstore" not in docs_all_resp2
                or b"zrandmember" not in docs_all_resp2
                or b"zlexcount" not in docs_all_resp2
                or b"zrangebylex" not in docs_all_resp2
                or b"zrangestore" not in docs_all_resp2
                or b"zremrangebylex" not in docs_all_resp2
                or b"zrevrange" not in docs_all_resp2
                or b"zrevrangebylex" not in docs_all_resp2
                or b"copy" not in docs_all_resp2
                or b"delex" not in docs_all_resp2
                or b"hgetdel" not in docs_all_resp2
                or b"increx" not in docs_all_resp2
                or b"lcs" not in docs_all_resp2
                or b"msetex" not in docs_all_resp2
                or b"restore-asking" not in docs_all_resp2
                or b"substr" not in docs_all_resp2
                or b"memory|malloc-stats" not in docs_all_resp2
                or b"memory|purge" not in docs_all_resp2
                or b"module" not in docs_all_resp2
                or b"module|help" not in docs_all_resp2
                or b"module|list" not in docs_all_resp2
                or b"module|load" not in docs_all_resp2
                or b"module|loadex" not in docs_all_resp2
                or b"module|unload" not in docs_all_resp2
            ):
                raise AssertionError(f"unexpected COMMAND DOCS all RESP2 payload: {docs_all_resp2!r}")
            if b"cluster|reset" in docs_all_resp2:
                raise AssertionError(f"unsupported commands leaked into COMMAND DOCS all RESP2: {docs_all_resp2!r}")

            listed_client = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"CLIENT*")
            if (
                not isinstance(listed_client, list)
                or b"client" not in listed_client
                or b"client|reply" not in listed_client
                or b"client|caching" not in listed_client
                or b"client|id" not in listed_client
                or b"client|no-evict" not in listed_client
                or b"client|no-touch" not in listed_client
                or b"client|unblock" not in listed_client
            ):
                raise AssertionError(f"unexpected COMMAND LIST client* result: {listed_client!r}")

            listed_blocking = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"BL*")
            if (
                not isinstance(listed_blocking, list)
                or b"blpop" not in listed_blocking
                or b"blmove" not in listed_blocking
                or b"blmpop" not in listed_blocking
            ):
                raise AssertionError(f"unexpected blocking COMMAND LIST result: {listed_blocking!r}")

            listed_wait = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"WAI*")
            if not isinstance(listed_wait, list) or b"wait" not in listed_wait or b"waitaof" not in listed_wait:
                raise AssertionError(f"unexpected COMMAND LIST wai* result: {listed_wait!r}")

            listed_swapdb = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"SWAP*")
            if not isinstance(listed_swapdb, list) or listed_swapdb != [b"swapdb"]:
                raise AssertionError(f"unexpected COMMAND LIST swap* result: {listed_swapdb!r}")

            listed_lolwut = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"LOL*")
            if not isinstance(listed_lolwut, list) or listed_lolwut != [b"lolwut"]:
                raise AssertionError(f"unexpected COMMAND LIST lol* result: {listed_lolwut!r}")

            listed_repl = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"REPL*")
            if not isinstance(listed_repl, list) or b"replicaof" not in listed_repl or b"replconf" not in listed_repl:
                raise AssertionError(f"unexpected COMMAND LIST repl* result: {listed_repl!r}")

            listed_slaveof = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"SLAVE*")
            if not isinstance(listed_slaveof, list) or listed_slaveof != [b"slaveof"]:
                raise AssertionError(f"unexpected COMMAND LIST SLAVE* result: {listed_slaveof!r}")

            listed_sync = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"SYNC")
            if not isinstance(listed_sync, list) or listed_sync != [b"sync"]:
                raise AssertionError(f"unexpected COMMAND LIST SYNC result: {listed_sync!r}")

            listed_debug = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"DEBUG")
            if not isinstance(listed_debug, list) or listed_debug != [b"debug"]:
                raise AssertionError(f"unexpected COMMAND LIST DEBUG result: {listed_debug!r}")

            listed_failover = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"FAIL*")
            if not isinstance(listed_failover, list) or b"failover" not in listed_failover:
                raise AssertionError(f"unexpected COMMAND LIST FAIL* result: {listed_failover!r}")

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
                or b"pfselftest" not in listed_pf
                or b"pfdebug" not in listed_pf
            ):
                raise AssertionError(f"unexpected COMMAND LIST pf* result: {listed_pf!r}")

            listed_geo = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"GEO*")
            if (
                not isinstance(listed_geo, list)
                or b"geoadd" not in listed_geo
                or b"geodist" not in listed_geo
                or b"geohash" not in listed_geo
                or b"geopos" not in listed_geo
                or b"georadius" not in listed_geo
                or b"georadius_ro" not in listed_geo
                or b"georadiusbymember" not in listed_geo
                or b"georadiusbymember_ro" not in listed_geo
                or b"geosearch" not in listed_geo
                or b"geosearchstore" not in listed_geo
            ):
                raise AssertionError(f"unexpected COMMAND LIST geo* result: {listed_geo!r}")

            listed_eval = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"EVAL*")
            if (
                not isinstance(listed_eval, list)
                or b"eval" not in listed_eval
                or b"evalsha" not in listed_eval
                or b"eval_ro" not in listed_eval
                or b"evalsha_ro" not in listed_eval
            ):
                raise AssertionError(f"unexpected COMMAND LIST eval* result: {listed_eval!r}")

            listed_fcall = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"FCALL*")
            if (
                not isinstance(listed_fcall, list)
                or b"fcall" not in listed_fcall
                or b"fcall_ro" not in listed_fcall
            ):
                raise AssertionError(f"unexpected COMMAND LIST fcall* result: {listed_fcall!r}")

            listed_script = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"SCRIPT*")
            if (
                not isinstance(listed_script, list)
                or b"script" not in listed_script
                or b"script|load" not in listed_script
                or b"script|exists" not in listed_script
                or b"script|flush" not in listed_script
                or b"script|kill" not in listed_script
                or b"script|debug" not in listed_script
            ):
                raise AssertionError(f"unexpected COMMAND LIST script* result: {listed_script!r}")

            listed_function = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"FUNCTION*")
            if (
                not isinstance(listed_function, list)
                or b"function" not in listed_function
                or b"function|help" not in listed_function
                or b"function|list" not in listed_function
                or b"function|stats" not in listed_function
                or b"function|flush" not in listed_function
                or b"function|delete" not in listed_function
                or b"function|load" not in listed_function
                or b"function|dump" not in listed_function
                or b"function|restore" not in listed_function
                or b"function|kill" not in listed_function
            ):
                raise AssertionError(f"unexpected COMMAND LIST function* result: {listed_function!r}")

            listed_memory = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"MEMORY*")
            if (
                not isinstance(listed_memory, list)
                or b"memory" not in listed_memory
                or b"memory|doctor" not in listed_memory
                or b"memory|malloc-stats" not in listed_memory
                or b"memory|purge" not in listed_memory
                or b"memory|stats" not in listed_memory
                or b"memory|usage" not in listed_memory
            ):
                raise AssertionError(f"unexpected COMMAND LIST memory* result: {listed_memory!r}")

            listed_module = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"MODULE*")
            if (
                not isinstance(listed_module, list)
                or b"module" not in listed_module
                or b"module|help" not in listed_module
                or b"module|list" not in listed_module
                or b"module|load" not in listed_module
                or b"module|loadex" not in listed_module
                or b"module|unload" not in listed_module
            ):
                raise AssertionError(f"unexpected COMMAND LIST module* result: {listed_module!r}")

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
                or b"xack" not in listed_stream
                or b"xackdel" not in listed_stream
                or b"xadd" not in listed_stream
                or b"xautoclaim" not in listed_stream
                or b"xcfgset" not in listed_stream
                or b"xclaim" not in listed_stream
                or b"xdel" not in listed_stream
                or b"xdelex" not in listed_stream
                or b"xgroup" not in listed_stream
                or b"xgroup|create" not in listed_stream
                or b"xgroup|destroy" not in listed_stream
                or b"xgroup|help" not in listed_stream
                or b"xgroup|setid" not in listed_stream
                or b"xidmprecord" not in listed_stream
                or b"xinfo" not in listed_stream
                or b"xinfo|consumers" not in listed_stream
                or b"xinfo|groups" not in listed_stream
                or b"xinfo|help" not in listed_stream
                or b"xinfo|stream" not in listed_stream
                or b"xlen" not in listed_stream
                or b"xnack" not in listed_stream
                or b"xpending" not in listed_stream
                or b"xrange" not in listed_stream
                or b"xrevrange" not in listed_stream
                or b"xread" not in listed_stream
                or b"xreadgroup" not in listed_stream
                or b"xsetid" not in listed_stream
                or b"xtrim" not in listed_stream
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

            listed_zmpop = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZMPOP")
            if listed_zmpop != [b"zmpop"]:
                raise AssertionError(f"unexpected COMMAND LIST zmpop result: {listed_zmpop!r}")

            listed_zrand = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZRAND*")
            if listed_zrand != [b"zrandmember"]:
                raise AssertionError(f"unexpected COMMAND LIST zrand result: {listed_zrand!r}")

            listed_hrand = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"HRAND*")
            if listed_hrand != [b"hrandfield"]:
                raise AssertionError(f"unexpected COMMAND LIST hrand result: {listed_hrand!r}")

            listed_zdiff = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZDIFF*")
            if listed_zdiff != [b"zdiff", b"zdiffstore"]:
                raise AssertionError(f"unexpected COMMAND LIST zdiff result: {listed_zdiff!r}")

            listed_zinter = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZINTER*")
            if listed_zinter != [b"zinter", b"zintercard", b"zinterstore"]:
                raise AssertionError(f"unexpected COMMAND LIST zinter result: {listed_zinter!r}")

            listed_zunion = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZUNION*")
            if listed_zunion != [b"zunion", b"zunionstore"]:
                raise AssertionError(f"unexpected COMMAND LIST zunion result: {listed_zunion!r}")

            listed_zlex = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZLEX*")
            if listed_zlex != [b"zlexcount"]:
                raise AssertionError(f"unexpected COMMAND LIST zlex result: {listed_zlex!r}")

            listed_zrange = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZRANGE*")
            if (
                not isinstance(listed_zrange, list)
                or b"zrange" not in listed_zrange
                or b"zrangebylex" not in listed_zrange
                or b"zrangestore" not in listed_zrange
                or b"zrangebyscore" not in listed_zrange
            ):
                raise AssertionError(f"unexpected COMMAND LIST zrange result: {listed_zrange!r}")

            listed_zremrange = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZREMRANGE*")
            if (
                not isinstance(listed_zremrange, list)
                or b"zremrangebylex" not in listed_zremrange
                or b"zremrangebyrank" not in listed_zremrange
                or b"zremrangebyscore" not in listed_zremrange
            ):
                raise AssertionError(f"unexpected COMMAND LIST zremrange result: {listed_zremrange!r}")

            listed_zrev = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"ZREV*")
            if (
                not isinstance(listed_zrev, list)
                or b"zrevrange" not in listed_zrev
                or b"zrevrangebylex" not in listed_zrev
                or b"zrevrank" not in listed_zrev
                or b"zrevrangebyscore" not in listed_zrev
            ):
                raise AssertionError(f"unexpected COMMAND LIST zrev result: {listed_zrev!r}")

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
                or not isinstance(docs_all.get(b"client|reply"), dict)
                or not isinstance(docs_all.get(b"client|unblock"), dict)
                or not isinstance(docs_all.get(b"client|caching"), dict)
                or not isinstance(docs_all.get(b"client|id"), dict)
                or not isinstance(docs_all.get(b"client|no-evict"), dict)
                or not isinstance(docs_all.get(b"client|no-touch"), dict)
                or not isinstance(docs_all.get(b"acl"), dict)
                or not isinstance(docs_all.get(b"acl|cat"), dict)
                or not isinstance(docs_all.get(b"acl|deluser"), dict)
                or not isinstance(docs_all.get(b"acl|dryrun"), dict)
                or not isinstance(docs_all.get(b"acl|genpass"), dict)
                or not isinstance(docs_all.get(b"acl|getuser"), dict)
                or not isinstance(docs_all.get(b"acl|help"), dict)
                or not isinstance(docs_all.get(b"acl|list"), dict)
                or not isinstance(docs_all.get(b"acl|load"), dict)
                or not isinstance(docs_all.get(b"acl|log"), dict)
                or not isinstance(docs_all.get(b"acl|save"), dict)
                or not isinstance(docs_all.get(b"acl|setuser"), dict)
                or not isinstance(docs_all.get(b"acl|users"), dict)
                or not isinstance(docs_all.get(b"acl|whoami"), dict)
                or not isinstance(docs_all.get(b"asking"), dict)
                or not isinstance(docs_all.get(b"function|load"), dict)
                or not isinstance(docs_all.get(b"hrandfield"), dict)
                or not isinstance(docs_all.get(b"waitaof"), dict)
                or not isinstance(docs_all.get(b"swapdb"), dict)
                or not isinstance(docs_all.get(b"lolwut"), dict)
                or not isinstance(docs_all.get(b"replconf"), dict)
                or not isinstance(docs_all.get(b"readonly"), dict)
                or not isinstance(docs_all.get(b"readwrite"), dict)
                or not isinstance(docs_all.get(b"slaveof"), dict)
                or not isinstance(docs_all.get(b"sync"), dict)
                or not isinstance(docs_all.get(b"debug"), dict)
                or not isinstance(docs_all.get(b"failover"), dict)
                or not isinstance(docs_all.get(b"pfselftest"), dict)
                or not isinstance(docs_all.get(b"pfdebug"), dict)
                or not isinstance(docs_all.get(b"blmove"), dict)
                or not isinstance(docs_all.get(b"blmpop"), dict)
                or not isinstance(docs_all.get(b"zmpop"), dict)
                or not isinstance(docs_all.get(b"zdiff"), dict)
                or not isinstance(docs_all.get(b"zdiffstore"), dict)
                or not isinstance(docs_all.get(b"zinter"), dict)
                or not isinstance(docs_all.get(b"zintercard"), dict)
                or not isinstance(docs_all.get(b"zinterstore"), dict)
                or not isinstance(docs_all.get(b"zunion"), dict)
                or not isinstance(docs_all.get(b"zunionstore"), dict)
                or not isinstance(docs_all.get(b"zrandmember"), dict)
                or not isinstance(docs_all.get(b"zlexcount"), dict)
                or not isinstance(docs_all.get(b"zrangebylex"), dict)
                or not isinstance(docs_all.get(b"zrangestore"), dict)
                or not isinstance(docs_all.get(b"zremrangebylex"), dict)
                or not isinstance(docs_all.get(b"zrevrange"), dict)
                or not isinstance(docs_all.get(b"zrevrangebylex"), dict)
                or not isinstance(docs_all.get(b"copy"), dict)
                or not isinstance(docs_all.get(b"delex"), dict)
                or not isinstance(docs_all.get(b"hgetdel"), dict)
                or not isinstance(docs_all.get(b"increx"), dict)
                or not isinstance(docs_all.get(b"lcs"), dict)
                or not isinstance(docs_all.get(b"msetex"), dict)
                or not isinstance(docs_all.get(b"restore-asking"), dict)
                or not isinstance(docs_all.get(b"substr"), dict)
                or not isinstance(docs_all.get(b"memory|malloc-stats"), dict)
                or not isinstance(docs_all.get(b"memory|purge"), dict)
                or not isinstance(docs_all.get(b"module"), dict)
                or not isinstance(docs_all.get(b"module|help"), dict)
                or not isinstance(docs_all.get(b"module|list"), dict)
                or not isinstance(docs_all.get(b"module|load"), dict)
                or not isinstance(docs_all.get(b"module|loadex"), dict)
                or not isinstance(docs_all.get(b"module|unload"), dict)
            ):
                raise AssertionError(f"unexpected COMMAND DOCS all RESP3 payload: {docs_all!r}")
            if b"cluster|reset" in docs_all:
                raise AssertionError(f"unsupported commands leaked into COMMAND DOCS all RESP3: {docs_all!r}")

            getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"SORT", b"mylist", b"ALPHA", b"STORE", b"out")
            if getkeys != [b"mylist", b"out"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS result: {getkeys!r}")

            copy_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"COPY", b"src", b"dst")
            if copy_getkeys != [b"src", b"dst"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS COPY result: {copy_getkeys!r}")

            delex_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"DELEX", b"src")
            if delex_getkeys != [b"src"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS DELEX result: {delex_getkeys!r}")

            hgetdel_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"HGETDEL", b"hash", b"FIELDS", b"1", b"field")
            if hgetdel_getkeys != [b"hash"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS HGETDEL result: {hgetdel_getkeys!r}")

            msetex_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"MSETEX", b"2", b"a", b"1", b"b", b"2", b"PX", b"1000")
            if msetex_getkeys != [b"a", b"b"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS MSETEX result: {msetex_getkeys!r}")

            increx_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"INCREX", b"a", b"BYINT", b"2", b"UBOUND", b"10")
            if increx_getkeys != [b"a"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS INCREX result: {increx_getkeys!r}")

            lcs_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"LCS", b"a", b"b", b"LEN")
            if lcs_getkeys != [b"a", b"b"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS LCS result: {lcs_getkeys!r}")

            substr_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"SUBSTR", b"a", b"0", b"1")
            if substr_getkeys != [b"a"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS SUBSTR result: {substr_getkeys!r}")

            blmove_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"BLMOVE", b"src", b"dst", b"LEFT", b"RIGHT", b"1")
            if blmove_getkeys != [b"src", b"dst"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS BLMOVE result: {blmove_getkeys!r}")

            blmpop_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"BLMPOP", b"1", b"2", b"a", b"b", b"LEFT", b"COUNT", b"2")
            if blmpop_getkeys != [b"a", b"b"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS BLMPOP result: {blmpop_getkeys!r}")

            zmpop_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"ZMPOP", b"2", b"a", b"b", b"MIN", b"COUNT", b"2")
            if zmpop_getkeys != [b"a", b"b"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS ZMPOP result: {zmpop_getkeys!r}")

            restore_asking_getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"RESTORE-ASKING", b"dst", b"0", b"payload")
            if restore_asking_getkeys != [b"dst"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS RESTORE-ASKING result: {restore_asking_getkeys!r}")

            getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"RENAME", b"src", b"dst")
            if not isinstance(getkeysandflags, list) or len(getkeysandflags) != 2:
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS shape: {getkeysandflags!r}")
            if getkeysandflags[0][0] != b"src" or getkeysandflags[1][0] != b"dst":
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS keys: {getkeysandflags!r}")

            copy_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"COPY", b"src", b"dst")
            if not isinstance(copy_getkeysandflags, list) or len(copy_getkeysandflags) != 2:
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS COPY shape: {copy_getkeysandflags!r}")
            if (
                copy_getkeysandflags[0][0] != b"src"
                or b"RO" not in copy_getkeysandflags[0][1]
                or b"access" not in copy_getkeysandflags[0][1]
                or copy_getkeysandflags[1][0] != b"dst"
                or b"OW" not in copy_getkeysandflags[1][1]
                or b"update" not in copy_getkeysandflags[1][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS COPY keys: {copy_getkeysandflags!r}")

            delex_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"DELEX", b"src")
            if (
                not isinstance(delex_getkeysandflags, list)
                or len(delex_getkeysandflags) != 1
                or delex_getkeysandflags[0][0] != b"src"
                or b"RM" not in delex_getkeysandflags[0][1]
                or b"delete" not in delex_getkeysandflags[0][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS DELEX keys: {delex_getkeysandflags!r}")

            hgetdel_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"HGETDEL", b"hash", b"FIELDS", b"1", b"field")
            if (
                not isinstance(hgetdel_getkeysandflags, list)
                or len(hgetdel_getkeysandflags) != 1
                or hgetdel_getkeysandflags[0][0] != b"hash"
                or b"RW" not in hgetdel_getkeysandflags[0][1]
                or b"access" not in hgetdel_getkeysandflags[0][1]
                or b"delete" not in hgetdel_getkeysandflags[0][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS HGETDEL keys: {hgetdel_getkeysandflags!r}")

            msetex_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"MSETEX", b"2", b"a", b"1", b"b", b"2", b"PX", b"1000")
            if (
                not isinstance(msetex_getkeysandflags, list)
                or len(msetex_getkeysandflags) != 2
                or msetex_getkeysandflags[0][0] != b"a"
                or b"OW" not in msetex_getkeysandflags[0][1]
                or b"update" not in msetex_getkeysandflags[0][1]
                or msetex_getkeysandflags[1][0] != b"b"
                or b"OW" not in msetex_getkeysandflags[1][1]
                or b"update" not in msetex_getkeysandflags[1][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS MSETEX keys: {msetex_getkeysandflags!r}")

            increx_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"INCREX", b"a", b"BYINT", b"2", b"UBOUND", b"10")
            if (
                not isinstance(increx_getkeysandflags, list)
                or len(increx_getkeysandflags) != 1
                or increx_getkeysandflags[0][0] != b"a"
                or b"RW" not in increx_getkeysandflags[0][1]
                or b"access" not in increx_getkeysandflags[0][1]
                or b"update" not in increx_getkeysandflags[0][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS INCREX keys: {increx_getkeysandflags!r}")

            lcs_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"LCS", b"a", b"b", b"LEN")
            if (
                not isinstance(lcs_getkeysandflags, list)
                or len(lcs_getkeysandflags) != 2
                or lcs_getkeysandflags[0][0] != b"a"
                or b"RO" not in lcs_getkeysandflags[0][1]
                or b"access" not in lcs_getkeysandflags[0][1]
                or lcs_getkeysandflags[1][0] != b"b"
                or b"RO" not in lcs_getkeysandflags[1][1]
                or b"access" not in lcs_getkeysandflags[1][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS LCS keys: {lcs_getkeysandflags!r}")

            substr_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"SUBSTR", b"a", b"0", b"1")
            if (
                not isinstance(substr_getkeysandflags, list)
                or len(substr_getkeysandflags) != 1
                or substr_getkeysandflags[0][0] != b"a"
                or b"RO" not in substr_getkeysandflags[0][1]
                or b"access" not in substr_getkeysandflags[0][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS SUBSTR keys: {substr_getkeysandflags!r}")

            blmove_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"BLMOVE", b"src", b"dst", b"LEFT", b"RIGHT", b"1")
            if not isinstance(blmove_getkeysandflags, list) or len(blmove_getkeysandflags) != 2:
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS BLMOVE shape: {blmove_getkeysandflags!r}")
            if (
                blmove_getkeysandflags[0][0] != b"src"
                or b"RW" not in blmove_getkeysandflags[0][1]
                or b"access" not in blmove_getkeysandflags[0][1]
                or b"delete" not in blmove_getkeysandflags[0][1]
                or blmove_getkeysandflags[1][0] != b"dst"
                or b"RW" not in blmove_getkeysandflags[1][1]
                or b"insert" not in blmove_getkeysandflags[1][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS BLMOVE keys: {blmove_getkeysandflags!r}")

            blmpop_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"BLMPOP", b"1", b"2", b"a", b"b", b"RIGHT", b"COUNT", b"2")
            if not isinstance(blmpop_getkeysandflags, list) or len(blmpop_getkeysandflags) != 2:
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS BLMPOP shape: {blmpop_getkeysandflags!r}")
            if (
                blmpop_getkeysandflags[0][0] != b"a"
                or b"RW" not in blmpop_getkeysandflags[0][1]
                or b"access" not in blmpop_getkeysandflags[0][1]
                or b"delete" not in blmpop_getkeysandflags[0][1]
                or blmpop_getkeysandflags[1][0] != b"b"
                or b"RW" not in blmpop_getkeysandflags[1][1]
                or b"access" not in blmpop_getkeysandflags[1][1]
                or b"delete" not in blmpop_getkeysandflags[1][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS BLMPOP keys: {blmpop_getkeysandflags!r}")

            zmpop_getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"ZMPOP", b"2", b"a", b"b", b"MAX", b"COUNT", b"2")
            if not isinstance(zmpop_getkeysandflags, list) or len(zmpop_getkeysandflags) != 2:
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS ZMPOP shape: {zmpop_getkeysandflags!r}")
            if (
                zmpop_getkeysandflags[0][0] != b"a"
                or b"RW" not in zmpop_getkeysandflags[0][1]
                or b"access" not in zmpop_getkeysandflags[0][1]
                or b"delete" not in zmpop_getkeysandflags[0][1]
                or zmpop_getkeysandflags[1][0] != b"b"
                or b"RW" not in zmpop_getkeysandflags[1][1]
                or b"access" not in zmpop_getkeysandflags[1][1]
                or b"delete" not in zmpop_getkeysandflags[1][1]
            ):
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS ZMPOP keys: {zmpop_getkeysandflags!r}")

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
