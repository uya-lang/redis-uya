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
    data = b""
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed while reading line")
        data += chunk
    return data[:-2]


def send_command(sock: socket.socket, *parts: bytes) -> bytes:
    buf = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        buf.append(f"${len(part)}\r\n".encode())
        buf.append(part)
        buf.append(b"\r\n")
    sock.sendall(b"".join(buf))

    prefix = recv_exact(sock, 1)
    if prefix in (b"+", b"-", b":"):
        return prefix + recv_line(sock) + b"\r\n"
    if prefix == b"$":
        size = int(recv_line(sock))
        if size < 0:
            return b"$-1\r\n"
        payload = recv_exact(sock, size + 2)
        return prefix + str(size).encode() + b"\r\n" + payload
    if prefix == b"*":
        count = int(recv_line(sock))
        out = prefix + str(count).encode() + b"\r\n"
        for _ in range(count):
            out += recv_nested(sock)
        return out
    raise RuntimeError(f"unexpected RESP prefix: {prefix!r}")


def recv_nested(sock: socket.socket) -> bytes:
    prefix = recv_exact(sock, 1)
    if prefix in (b"+", b"-", b":"):
        return prefix + recv_line(sock) + b"\r\n"
    if prefix == b"$":
        size = int(recv_line(sock))
        if size < 0:
            return b"$-1\r\n"
        payload = recv_exact(sock, size + 2)
        return prefix + str(size).encode() + b"\r\n" + payload
    raise RuntimeError(f"unexpected nested RESP prefix: {prefix!r}")


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def wait_for_replica_value(port: int, expected: bytes, deadline: float) -> None:
    while time.monotonic() < deadline:
        with connect_with_retry(port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            value = send_command(sock, b"GET", b"key")
            if value == expected:
                return
        time.sleep(0.05)
    raise RuntimeError(f"replica did not converge to {expected!r} in time")


def wait_for_replication_state(port: int, marker: bytes, deadline: float) -> None:
    last = b""
    while time.monotonic() < deadline:
        with connect_with_retry(port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            last = send_command(sock, b"INFO", b"replication")
            if marker in last:
                return
        time.sleep(0.05)
    raise RuntimeError(f"replication state marker {marker!r} not observed, last={last!r}")


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    master_port = find_free_port()
    replica_port = find_free_port()
    master_aof = ROOT / "build" / f"master-heartbeat-{master_port}.aof"
    replica_aof = ROOT / "build" / f"replica-heartbeat-{replica_port}.aof"
    master_aof.unlink(missing_ok=True)
    replica_aof.unlink(missing_ok=True)

    master = subprocess.Popen(
        [str(BIN), str(master_port), "8", str(master_aof)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    replica = subprocess.Popen(
        [str(BIN), str(replica_port), "8", str(replica_aof)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"SET", b"key", b"value") != b"+OK\r\n":
                raise AssertionError("master initial SET failed")

        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"REPLICAOF", b"127.0.0.1", str(master_port).encode()) != b"+OK\r\n":
                raise AssertionError("replica REPLICAOF failed")

        wait_for_replica_value(replica_port, b"$5\r\nvalue\r\n", time.monotonic() + 5.0)
        wait_for_replication_state(replica_port, b"replication_state:connected", time.monotonic() + 5.0)

        stop_process(master)
        wait_for_replication_state(replica_port, b"replication_state:configured", time.monotonic() + 5.0)

        master = subprocess.Popen(
            [str(BIN), str(master_port), "8", str(master_aof)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        wait_for_replication_state(replica_port, b"replication_state:connected", time.monotonic() + 5.0)
        wait_for_replica_value(replica_port, b"$5\r\nvalue\r\n", time.monotonic() + 5.0)

        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"SET", b"key", b"after") != b"+OK\r\n":
                raise AssertionError("master post-reconnect SET failed")

        wait_for_replica_value(replica_port, b"$5\r\nafter\r\n", time.monotonic() + 5.0)
    finally:
        stop_process(master)
        stop_process(replica)
        master_aof.unlink(missing_ok=True)
        replica_aof.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/replication_heartbeat: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/replication_heartbeat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
