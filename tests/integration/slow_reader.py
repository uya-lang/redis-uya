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


def make_set_request(key: bytes, value: bytes) -> bytes:
    return (
        b"*3\r\n"
        + b"$3\r\nSET\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
        + f"${len(value)}\r\n".encode()
        + value
        + b"\r\n"
    )


def make_get_request(key: bytes) -> bytes:
    return (
        b"*2\r\n"
        + b"$3\r\nGET\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
    )


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"slow-reader-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    slow_sock: socket.socket | None = None
    active_sock: socket.socket | None = None
    try:
        slow_sock = connect_with_retry(port, time.monotonic() + 5.0)
        slow_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        slow_sock.settimeout(1.0)

        key = b"payload"
        value = b"x" * 6000
        roundtrip(slow_sock, make_set_request(key, value), b"+OK\r\n")

        pipelined = b"".join(make_get_request(key) for _ in range(256))
        slow_sock.sendall(pipelined)
        time.sleep(0.2)

        active_sock = socket.create_connection(("127.0.0.1", port), timeout=1.0)
        active_sock.settimeout(1.0)
        roundtrip(active_sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")
    finally:
        if active_sock is not None:
            active_sock.close()
        if slow_sock is not None:
            slow_sock.close()
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/slow_reader: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/slow_reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
