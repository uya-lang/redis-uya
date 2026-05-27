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


def recv_line(sock: socket.socket) -> bytes:
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed before monitor line")
        data.extend(chunk)
    return bytes(data)


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
    aof_path = ROOT / "build" / f"monitor-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as monitor_sock:
            monitor_sock.settimeout(2.0)
            roundtrip(monitor_sock, b"*1\r\n$7\r\nMONITOR\r\n", b"+OK\r\n")

            with connect_with_retry(port, time.monotonic() + 5.0) as command_sock:
                command_sock.settimeout(2.0)
                roundtrip(
                    command_sock,
                    b"*3\r\n$3\r\nSET\r\n$7\r\nmon-key\r\n$5\r\nvalue\r\n",
                    b"+OK\r\n",
                )

            line = recv_line(monitor_sock)
            if not line.startswith(b"+") or b'"SET" "mon-key" "value"' not in line:
                raise AssertionError(f"unexpected monitor line: {line!r}")

            roundtrip(monitor_sock, b"*1\r\n$5\r\nRESET\r\n", b"+RESET\r\n")
            with connect_with_retry(port, time.monotonic() + 5.0) as ping_sock:
                ping_sock.settimeout(2.0)
                roundtrip(ping_sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")

            monitor_sock.settimeout(0.2)
            try:
                extra = monitor_sock.recv(1)
            except socket.timeout:
                extra = b""
            if extra != b"":
                raise AssertionError(f"monitor still received data after RESET: {extra!r}")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/monitor_smoke: {exc}", file=sys.stderr)
        sys.exit(1)
    print("[PASS] integration/monitor_smoke")
