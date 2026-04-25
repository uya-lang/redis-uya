#!/usr/bin/env python3
import os
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


def make_del_request(key: bytes) -> bytes:
    return (
        b"*2\r\n"
        + b"$3\r\nDEL\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
    )


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    duration_seconds = int(os.environ.get("REDIS_UYA_LONG_RUN_SECONDS", "1800"))
    if duration_seconds <= 0:
        raise RuntimeError("REDIS_UYA_LONG_RUN_SECONDS must be > 0")

    port = find_free_port()
    aof_path = ROOT / "build" / f"long-run-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    sock: socket.socket | None = None
    try:
        sock = connect_with_retry(port, time.monotonic() + 5.0)
        sock.settimeout(2.0)
        deadline = time.monotonic() + duration_seconds
        iteration = 0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                raise RuntimeError(
                    f"redis-uya exited with {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
                )

            key = f"smoke:{iteration % 256}".encode()
            value = f"value:{iteration}".encode()
            roundtrip(sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")
            roundtrip(sock, make_set_request(key, value), b"+OK\r\n")
            roundtrip(
                sock,
                make_get_request(key),
                f"${len(value)}\r\n".encode() + value + b"\r\n",
            )
            roundtrip(sock, make_del_request(key), b":1\r\n")
            iteration += 1
            if iteration % 128 == 0:
                time.sleep(0.01)
    finally:
        if sock is not None:
            sock.close()
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/long_run_smoke: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/long_run_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
