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

            bitmap_info = send_command(sock, b"COMMAND", b"INFO", b"GETBIT", b"SETBIT", b"BITCOUNT")
            if (
                not isinstance(bitmap_info, list)
                or len(bitmap_info) != 3
                or not isinstance(bitmap_info[0], list)
                or bitmap_info[0][0] != b"getbit"
                or not isinstance(bitmap_info[1], list)
                or bitmap_info[1][0] != b"setbit"
                or not isinstance(bitmap_info[2], list)
                or bitmap_info[2][0] != b"bitcount"
            ):
                raise AssertionError(f"bitmap commands missing from COMMAND INFO: {bitmap_info!r}")

            unsupported_info = send_command(sock, b"COMMAND", b"INFO", b"ACL", b"BLPOP", b"CLUSTER|RESET")
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

            unsupported_docs = send_command(sock, b"COMMAND", b"DOCS", b"ACL", b"BLPOP", b"CLUSTER|RESET")
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
            if b"acl" in docs_all_resp2 or b"blpop" in docs_all_resp2 or b"cluster|reset" in docs_all_resp2:
                raise AssertionError(f"unsupported commands leaked into COMMAND DOCS all RESP2: {docs_all_resp2!r}")

            listed_blocking = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"BL*")
            if not isinstance(listed_blocking, list) or b"blpop" in listed_blocking:
                raise AssertionError(f"unsupported blocking commands leaked into COMMAND LIST: {listed_blocking!r}")

            listed_bitmap = send_command(sock, b"COMMAND", b"LIST", b"FILTERBY", b"PATTERN", b"BIT*")
            if (
                not isinstance(listed_bitmap, list)
                or b"bitcount" not in listed_bitmap
                or b"bitfield" in listed_bitmap
                or b"bitop" in listed_bitmap
                or b"bitpos" in listed_bitmap
            ):
                raise AssertionError(f"unexpected COMMAND LIST bitmap result: {listed_bitmap!r}")

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
            if b"acl" in docs_all or b"blpop" in docs_all or b"cluster|reset" in docs_all:
                raise AssertionError(f"unsupported commands leaked into COMMAND DOCS all RESP3: {docs_all!r}")

            getkeys = send_command(sock, b"COMMAND", b"GETKEYS", b"SORT", b"mylist", b"ALPHA", b"STORE", b"out")
            if getkeys != [b"mylist", b"out"]:
                raise AssertionError(f"unexpected COMMAND GETKEYS result: {getkeys!r}")

            getkeysandflags = send_command(sock, b"COMMAND", b"GETKEYSANDFLAGS", b"RENAME", b"src", b"dst")
            if not isinstance(getkeysandflags, list) or len(getkeysandflags) != 2:
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS shape: {getkeysandflags!r}")
            if getkeysandflags[0][0] != b"src" or getkeysandflags[1][0] != b"dst":
                raise AssertionError(f"unexpected COMMAND GETKEYSANDFLAGS keys: {getkeysandflags!r}")

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
