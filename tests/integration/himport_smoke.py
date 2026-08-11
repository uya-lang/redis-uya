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
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def connect_with_retry(port: int) -> socket.socket:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            sock.settimeout(2.0)
            return sock
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"failed to connect to redis-uya on port {port}")


def read_line(sock: socket.socket) -> bytes:
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed while reading RESP line")
        data.extend(chunk)
    return bytes(data[:-2])


def read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RuntimeError("connection closed while reading RESP payload")
        data.extend(chunk)
    return bytes(data)


def read_resp(sock: socket.socket):
    prefix = read_exact(sock, 1)
    if prefix == b"+":
        return read_line(sock).decode()
    if prefix == b"-":
        raise RespError(read_line(sock).decode())
    if prefix == b":":
        return int(read_line(sock))
    if prefix == b"$":
        length = int(read_line(sock))
        if length < 0:
            return None
        payload = read_exact(sock, length)
        if read_exact(sock, 2) != b"\r\n":
            raise RuntimeError("invalid bulk terminator")
        return payload
    if prefix == b"*":
        count = int(read_line(sock))
        if count < 0:
            return None
        return [read_resp(sock) for _ in range(count)]
    raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")


def send_command(sock: socket.socket, *args: bytes):
    request = bytearray(f"*{len(args)}\r\n".encode())
    for arg in args:
        request.extend(f"${len(arg)}\r\n".encode())
        request.extend(arg)
        request.extend(b"\r\n")
    sock.sendall(request)
    return read_resp(sock)


def expect_error(sock: socket.socket, expected: str, *args: bytes) -> None:
    try:
        send_command(sock, *args)
    except RespError as exc:
        if str(exc) != expected:
            raise AssertionError(f"unexpected error for {args!r}: {exc}") from exc
        return
    raise AssertionError(f"expected error for {args!r}")


def expect_error_contains(sock: socket.socket, expected: str, *args: bytes) -> None:
    try:
        send_command(sock, *args)
    except RespError as exc:
        if expected not in str(exc):
            raise AssertionError(f"unexpected error for {args!r}: {exc}") from exc
        return
    raise AssertionError(f"expected error for {args!r}")


def start_server(port: int, aof_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def run_smoke() -> None:
    port = find_free_port()
    aof_path = ROOT / "build" / f"himport-smoke-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = start_server(port, aof_path)
    try:
        with connect_with_retry(port) as client, connect_with_retry(port) as other:
            if send_command(client, b"HIMPORT", b"PREPARE", b"fs", b"b", b"aa") != "OK":
                raise AssertionError("HIMPORT PREPARE failed")
            if send_command(client, b"MULTI") != "OK":
                raise AssertionError("MULTI before DISCARD failed")
            if send_command(client, b"PING") != "QUEUED":
                raise AssertionError("PING was not queued before DISCARD")
            if send_command(client, b"DISCARD") != "OK":
                raise AssertionError("transaction DISCARD failed")
            if send_command(client, b"HIMPORT", b"SET", b"key", b"fs", b"one", b"two") != "OK":
                raise AssertionError("transaction DISCARD cleared the connection fieldset")
            if send_command(client, b"HGET", b"key", b"b") != b"one":
                raise AssertionError("HIMPORT positional field mapping failed")
            if send_command(client, b"HGET", b"key", b"aa") != b"two":
                raise AssertionError("HIMPORT second field mapping failed")

            expect_error(other, "ERR no such fieldset", b"HIMPORT", b"SET", b"other", b"fs", b"x", b"y")
            expect_error(client, "ERR duplicate field name in fieldset", b"HIMPORT", b"PREPARE", b"dup", b"a", b"a")
            expect_error(client, "ERR value count does not match fieldset field count", b"HIMPORT", b"SET", b"key", b"fs", b"one")

            if send_command(client, b"HSET", b"key", b"stale", b"value") != 1:
                raise AssertionError("failed to seed stale hash field")
            if send_command(client, b"PEXPIRE", b"key", b"60000") != 1:
                raise AssertionError("failed to seed key TTL")
            if send_command(client, b"HIMPORT", b"SET", b"key", b"fs", b"new-one", b"new-two") != "OK":
                raise AssertionError("HIMPORT replacement failed")
            if send_command(client, b"HGET", b"key", b"stale") is not None:
                raise AssertionError("HIMPORT SET did not replace the complete hash")
            if send_command(client, b"PTTL", b"key") != -1:
                raise AssertionError("HIMPORT SET did not clear the key TTL")

            if send_command(client, b"MULTI") != "OK":
                raise AssertionError("MULTI failed")
            if send_command(client, b"HIMPORT", b"PREPARE", b"txfs", b"field") != "QUEUED":
                raise AssertionError("HIMPORT PREPARE was not queued")
            if send_command(client, b"HIMPORT", b"SET", b"txkey", b"txfs", b"value") != "QUEUED":
                raise AssertionError("HIMPORT SET was not queued")
            if send_command(client, b"EXEC") != ["OK", "OK"]:
                raise AssertionError("HIMPORT transaction execution failed")
            if send_command(client, b"HGET", b"txkey", b"field") != b"value":
                raise AssertionError("HIMPORT transaction result missing")

            if send_command(client, b"HIMPORT", b"DISCARD", b"fs") != 1:
                raise AssertionError("HIMPORT DISCARD failed")
            if send_command(client, b"HIMPORT", b"DISCARD", b"fs") != 0:
                raise AssertionError("HIMPORT DISCARD missing result failed")
            if send_command(client, b"HIMPORT", b"DISCARDALL") != 1:
                raise AssertionError("HIMPORT DISCARDALL failed")

            if send_command(client, b"ACL", b"SETUSER", b"default", b"-himport|set") != "OK":
                raise AssertionError("failed to deny HIMPORT SET")
            if send_command(client, b"HIMPORT", b"PREPARE", b"aclfs", b"field") != "OK":
                raise AssertionError("HIMPORT PREPARE should remain allowed by a SET-only deny")
            expect_error_contains(client, "NOPERM", b"HIMPORT", b"SET", b"acl-key", b"aclfs", b"value")
            if send_command(client, b"ACL", b"SETUSER", b"default", b"+himport|set") != "OK":
                raise AssertionError("failed to restore HIMPORT SET")
            if send_command(client, b"ACL", b"SETUSER", b"default", b"-himport") != "OK":
                raise AssertionError("failed to deny the HIMPORT parent")
            expect_error_contains(client, "NOPERM", b"HIMPORT", b"PREPARE", b"blocked-fs", b"field")
            expect_error_contains(client, "NOPERM", b"HIMPORT", b"SET", b"acl-key", b"aclfs", b"value")
            if send_command(client, b"ACL", b"SETUSER", b"default", b"+himport") != "OK":
                raise AssertionError("failed to restore the HIMPORT parent")
            if send_command(client, b"ACL", b"SETUSER", b"default", b"-@write") != "OK":
                raise AssertionError("failed to deny write commands")
            if send_command(client, b"HIMPORT", b"PREPARE", b"category-fs", b"field") != "OK":
                raise AssertionError("HIMPORT PREPARE should not require write permission")
            expect_error_contains(client, "NOPERM", b"HIMPORT", b"SET", b"acl-key", b"category-fs", b"value")
            if send_command(client, b"ACL", b"SETUSER", b"default", b"+@write") != "OK":
                raise AssertionError("failed to restore write commands")
            if send_command(client, b"ACL", b"SETUSER", b"default", b"resetkeys", b"~safe*") != "OK":
                raise AssertionError("failed to set ACL key pattern")
            expect_error_contains(client, "NOPERM", b"HIMPORT", b"SET", b"unsafe", b"aclfs", b"value")
            if send_command(client, b"HIMPORT", b"SET", b"safe-key", b"aclfs", b"value") != "OK":
                raise AssertionError("HIMPORT SET should honor an allowed key pattern")
            if send_command(client, b"ACL", b"SETUSER", b"default", b"allkeys") != "OK":
                raise AssertionError("failed to restore allkeys")
            time.sleep(0.2)
    finally:
        stop_process(proc)

    raw_aof = aof_path.read_bytes()
    if b"RESTORE" not in raw_aof or b"HIMPORT" in raw_aof or b"PREPARE" in raw_aof:
        raise AssertionError("HIMPORT AOF must contain standalone RESTORE commands only")

    replay_port = find_free_port()
    replay_proc = start_server(replay_port, aof_path)
    try:
        with connect_with_retry(replay_port) as replay:
            if send_command(replay, b"HGET", b"key", b"b") != b"new-one":
                raise AssertionError("HIMPORT AOF replay lost the first field")
            if send_command(replay, b"HGET", b"key", b"aa") != b"new-two":
                raise AssertionError("HIMPORT AOF replay lost the second field")
            if send_command(replay, b"HGET", b"txkey", b"field") != b"value":
                raise AssertionError("transactional HIMPORT AOF replay failed")
    finally:
        stop_process(replay_proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/himport_smoke: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/himport_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
