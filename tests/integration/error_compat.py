#!/usr/bin/env python3
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "build" / "redis-uya"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def connect_with_retry(port: int, deadline: float) -> socket.socket:
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=0.2)
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"failed to connect to redis-uya on port {port}: {last_error}")


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("connection closed before full response")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def roundtrip(sock: socket.socket, request: bytes, expected: bytes) -> None:
    sock.sendall(request)
    actual = recv_exact(sock, len(expected))
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"error-compat-{port}.aof"
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
            sock.settimeout(2.0)
            roundtrip(sock, b"*1\r\n$7\r\nMISSING\r\n", b"-ERR unknown command\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nEXEC\r\n", b"-ERR EXEC without MULTI\r\n")
            roundtrip(sock, b"*1\r\n$7\r\nDISCARD\r\n", b"-ERR DISCARD without MULTI\r\n")
            roundtrip(sock, b"*1\r\n$5\r\nMULTI\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$5\r\nMULTI\r\n", b"-ERR MULTI calls can not be nested\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nWATCH\r\n$3\r\nkey\r\n", b"-ERR WATCH inside MULTI is not allowed\r\n")
            roundtrip(sock, b"*1\r\n$7\r\nUNWATCH\r\n", b"-ERR UNWATCH inside MULTI is not allowed\r\n")
            roundtrip(sock, b"*1\r\n$7\r\nDISCARD\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$3\r\nGET\r\n", b"-ERR wrong number of arguments\r\n")
            roundtrip(
                sock,
                b"*5\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n$2\r\nEX\r\n$2\r\n10\r\n",
                b"-ERR syntax error\r\n",
            )
            roundtrip(sock, b"+PING\r\n", b"-ERR invalid request\r\n")

        with connect_with_retry(port, time.monotonic() + 5.0) as bad_sock:
            bad_sock.settimeout(2.0)
            bad_sock.sendall(b"?bad\r\n")
            actual = recv_exact(bad_sock, len(b"-ERR protocol error\r\n"))
            if actual != b"-ERR protocol error\r\n":
                raise AssertionError(f"expected protocol error, got {actual!r}")
            closed = bad_sock.recv(1)
            if closed != b"":
                raise AssertionError(f"expected protocol error to close connection, got {closed!r}")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/error_compat: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/error_compat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
