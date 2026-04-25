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
    aof_path = ROOT / "build" / f"smoke-{port}.aof"
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
            roundtrip(sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*2\r\n$6\r\nEXISTS\r\n$3\r\nkey\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$3\r\nkey\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$6\r\nEXISTS\r\n$3\r\nkey\r\n", b":0\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nQUIT\r\n", b"+OK\r\n")

        stop_process(proc)
        if proc.returncode not in (0, -15):
            stdout, stderr = proc.communicate()
            raise RuntimeError(
                f"redis-uya exited with {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/smoke_tcp: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/smoke_tcp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
