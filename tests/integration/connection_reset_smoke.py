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


def expect_error(sock: socket.socket, *parts: bytes, needle: str) -> None:
    try:
        send_command(sock, *parts)
    except RespError as exc:
        if needle not in str(exc):
            raise AssertionError(f"unexpected error {exc!r}, expected {needle!r}") from exc
        return
    raise AssertionError(f"expected error containing {needle!r}")


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"connection-reset-{port}.aof"
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
            if send_command(sock, b"CONFIG", b"SET", b"requirepass", b"runtime-secret") != "OK":
                raise AssertionError("CONFIG SET requirepass failed")
            if send_command(sock, b"PING") != "PONG":
                raise AssertionError("current connection should stay usable after CONFIG SET requirepass")

            hello = send_command(sock, b"HELLO", b"3", b"SETNAME", b"reset-client")
            if not isinstance(hello, dict) or hello.get(b"proto") != 3:
                raise AssertionError(f"unexpected HELLO 3 response: {hello!r}")

            subscribe = send_command(sock, b"SUBSCRIBE", b"reset-chan")
            if subscribe != [b"subscribe", b"reset-chan", 1]:
                raise AssertionError(f"unexpected RESP3 subscribe push: {subscribe!r}")

            if send_command(sock, b"GET", b"missing") is not None:
                raise AssertionError("RESP3 subscribed GET missing should return Null")

            if send_command(sock, b"MULTI") != "OK":
                raise AssertionError("MULTI failed")
            if send_command(sock, b"GET", b"missing") != "QUEUED":
                raise AssertionError("GET was not queued inside MULTI")

            if send_command(sock, b"RESET") != "RESET":
                raise AssertionError("RESET failed")

            expect_error(sock, b"PING", needle="Authentication required")
            if send_command(sock, b"RESET") != "RESET":
                raise AssertionError("RESET should remain available while unauthenticated")

            if send_command(sock, b"AUTH", b"default", b"runtime-secret") != "OK":
                raise AssertionError("AUTH after RESET failed")

            client_info = send_command(sock, b"CLIENT", b"INFO")
            if not isinstance(client_info, bytes) or b"resp=2" not in client_info or b"name=reset-client" in client_info:
                raise AssertionError(f"unexpected CLIENT INFO after RESET: {client_info!r}")

            expect_error(sock, b"EXEC", needle="EXEC without MULTI")

            with connect_with_retry(port, time.monotonic() + 5.0) as pub_sock:
                if send_command(pub_sock, b"AUTH", b"default", b"runtime-secret") != "OK":
                    raise AssertionError("publisher AUTH after RESET scenario failed")
                if send_command(pub_sock, b"PUBLISH", b"reset-chan", b"payload") != 0:
                    raise AssertionError("PUBLISH after RESET should report zero receivers")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/connection_reset_smoke: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/connection_reset_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
