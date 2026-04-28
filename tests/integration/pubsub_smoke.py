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
    aof_path = ROOT / "build" / f"pubsub-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sub_sock:
            sub_sock.settimeout(2.0)
            roundtrip(
                sub_sock,
                b"*2\r\n$9\r\nSUBSCRIBE\r\n$5\r\nchan1\r\n",
                b"*3\r\n$9\r\nsubscribe\r\n$5\r\nchan1\r\n:1\r\n",
            )

            with connect_with_retry(port, time.monotonic() + 5.0) as pub_sock:
                pub_sock.settimeout(2.0)
                roundtrip(
                    pub_sock,
                    b"*3\r\n$7\r\nPUBLISH\r\n$5\r\nchan1\r\n$5\r\nhello\r\n",
                    b":1\r\n",
                )

            actual = recv_exact(sub_sock, len(b"*3\r\n$7\r\nmessage\r\n$5\r\nchan1\r\n$5\r\nhello\r\n"))
            if actual != b"*3\r\n$7\r\nmessage\r\n$5\r\nchan1\r\n$5\r\nhello\r\n":
                raise AssertionError(f"unexpected pubsub message: {actual!r}")

            roundtrip(
                sub_sock,
                b"*2\r\n$11\r\nUNSUBSCRIBE\r\n$5\r\nchan1\r\n",
                b"*3\r\n$11\r\nunsubscribe\r\n$5\r\nchan1\r\n:0\r\n",
            )

            with connect_with_retry(port, time.monotonic() + 5.0) as pub_sock:
                pub_sock.settimeout(2.0)
                roundtrip(
                    pub_sock,
                    b"*3\r\n$7\r\nPUBLISH\r\n$5\r\nchan1\r\n$5\r\nagain\r\n",
                    b":0\r\n",
                )

            sub_sock.settimeout(0.2)
            try:
                extra = sub_sock.recv(1)
            except socket.timeout:
                extra = b""
            if extra != b"":
                raise AssertionError(f"unexpected message after unsubscribe: {extra!r}")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/pubsub_smoke: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/pubsub_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
