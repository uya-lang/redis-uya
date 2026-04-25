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
    aof_path = ROOT / "build" / f"idle-client-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    idle_sock: socket.socket | None = None
    active_sock: socket.socket | None = None
    try:
        idle_sock = connect_with_retry(port, time.monotonic() + 5.0)
        active_sock = socket.create_connection(("127.0.0.1", port), timeout=1.0)
        active_sock.settimeout(1.0)
        active_sock.sendall(b"*1\r\n$4\r\nPING\r\n")
        actual = active_sock.recv(7)
        if actual != b"+PONG\r\n":
            raise AssertionError(f"expected b'+PONG\\r\\n', got {actual!r}")
    finally:
        if active_sock is not None:
            active_sock.close()
        if idle_sock is not None:
            idle_sock.close()
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/idle_client: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/idle_client")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
