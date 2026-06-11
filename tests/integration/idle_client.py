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


def send_command(sock: socket.socket, *parts: bytes) -> bytes:
    payload = bytearray()
    payload.extend(f"*{len(parts)}\r\n".encode())
    for part in parts:
        payload.extend(f"${len(part)}\r\n".encode())
        payload.extend(part)
        payload.extend(b"\r\n")
    sock.sendall(payload)
    return sock.recv(64)


def expect_simple(sock: socket.socket, expected: bytes) -> None:
    actual = sock.recv(len(expected))
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def wait_for_closed(sock: socket.socket, deadline: float) -> None:
    previous_timeout = sock.gettimeout()
    try:
        sock.settimeout(0.2)
        while time.monotonic() < deadline:
            try:
                data = sock.recv(1)
                if data == b"":
                    return
                raise AssertionError(f"idle client received unexpected data: {data!r}")
            except (ConnectionResetError, BrokenPipeError):
                return
            except socket.timeout:
                time.sleep(0.05)
        raise AssertionError("idle client was not closed after CONFIG timeout")
    finally:
        sock.settimeout(previous_timeout)


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
        expect_simple(active_sock, b"+PONG\r\n")

        if send_command(active_sock, b"CONFIG", b"SET", b"timeout", b"1") != b"+OK\r\n":
            raise AssertionError("CONFIG SET timeout 1 failed")
        for _ in range(4):
            time.sleep(0.35)
            if send_command(active_sock, b"PING") != b"+PONG\r\n":
                raise AssertionError("active client was closed despite recent activity")
        wait_for_closed(idle_sock, time.monotonic() + 3.0)
        if send_command(active_sock, b"PING") != b"+PONG\r\n":
            raise AssertionError("active client was not usable after idle client close")
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
