#!/usr/bin/env python3
from __future__ import annotations

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
        raise RuntimeError(read_line(sock).decode())
    if prefix == b":":
        return int(read_line(sock))
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
    raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")


def send_command(sock: socket.socket, *parts: bytes):
    request = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        request.append(f"${len(part)}\r\n".encode())
        request.append(part)
        request.append(b"\r\n")
    sock.sendall(b"".join(request))
    return read_resp(sock)


def run_server(policy: str, maxmemory: int):
    port = find_free_port()
    aof_path = ROOT / "build" / f"{policy}-{port}.aof"
    rdb_path = ROOT / "build" / "dump.rdb"
    aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path), str(maxmemory), policy],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return port, aof_path, rdb_path, proc


def assert_policy(sock: socket.socket, policy: str) -> None:
    config = send_command(sock, b"CONFIG", b"GET", b"maxmemory-policy")
    if not isinstance(config, list) or config != [b"maxmemory-policy", policy.encode()]:
        raise AssertionError(f"unexpected CONFIG GET maxmemory-policy for {policy}: {config!r}")
    info = send_command(sock, b"INFO", b"memory")
    if not isinstance(info, bytes) or f"maxmemory_policy:{policy}".encode() not in info:
        raise AssertionError(f"unexpected INFO memory for {policy}: {info!r}")


def check_volatile_lru() -> None:
    port, aof_path, rdb_path, proc = run_server("volatile-lru", 5500)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            assert_policy(sock, "volatile-lru")
            value = b"v" * 500
            new_value = b"n" * 500
            for key in (b"persistent", b"old", b"hot"):
                if send_command(sock, b"SET", key, value) != "OK":
                    raise AssertionError(f"SET {key!r} failed")
            if send_command(sock, b"EXPIRE", b"old", b"120") != 1:
                raise AssertionError("EXPIRE old failed")
            if send_command(sock, b"EXPIRE", b"hot", b"120") != 1:
                raise AssertionError("EXPIRE hot failed")
            if send_command(sock, b"GET", b"hot") != value:
                raise AssertionError("GET hot failed before volatile-lru eviction")
            if send_command(sock, b"SET", b"new", new_value) != "OK":
                raise AssertionError("SET new should evict an expiring LRU key")
            if send_command(sock, b"GET", b"old") is not None:
                raise AssertionError("old volatile key should be evicted")
            if send_command(sock, b"GET", b"hot") != value:
                raise AssertionError("hot volatile key should survive")
            if send_command(sock, b"GET", b"persistent") != value:
                raise AssertionError("persistent key must not be evicted by volatile-lru")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def check_volatile_lfu() -> None:
    port, aof_path, rdb_path, proc = run_server("volatile-lfu", 5000)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            assert_policy(sock, "volatile-lfu")
            value = b"f" * 500
            new_value = b"n" * 500
            for key in (b"cold", b"hot"):
                if send_command(sock, b"SET", key, value) != "OK":
                    raise AssertionError(f"SET {key!r} failed")
                if send_command(sock, b"EXPIRE", key, b"120") != 1:
                    raise AssertionError(f"EXPIRE {key!r} failed")
            if send_command(sock, b"GET", b"hot") != value:
                raise AssertionError("GET hot failed before volatile-lfu eviction")
            if send_command(sock, b"GET", b"hot") != value:
                raise AssertionError("second GET hot failed before volatile-lfu eviction")
            if send_command(sock, b"SET", b"new", new_value) != "OK":
                raise AssertionError("SET new should evict a low-frequency volatile key")
            if send_command(sock, b"GET", b"cold") is not None:
                raise AssertionError("cold volatile key should be evicted")
            if send_command(sock, b"GET", b"hot") != value:
                raise AssertionError("hot volatile key should survive")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def check_volatile_ttl() -> None:
    port, aof_path, rdb_path, proc = run_server("volatile-ttl", 5000)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            assert_policy(sock, "volatile-ttl")
            value = b"t" * 500
            new_value = b"n" * 500
            if send_command(sock, b"SET", b"soon", value) != "OK":
                raise AssertionError("SET soon failed")
            if send_command(sock, b"EXPIRE", b"soon", b"30") != 1:
                raise AssertionError("EXPIRE soon failed")
            if send_command(sock, b"SET", b"later", value) != "OK":
                raise AssertionError("SET later failed")
            if send_command(sock, b"EXPIRE", b"later", b"120") != 1:
                raise AssertionError("EXPIRE later failed")
            if send_command(sock, b"SET", b"new", new_value) != "OK":
                raise AssertionError("SET new should evict the nearest-expiry volatile key")
            if send_command(sock, b"GET", b"soon") is not None:
                raise AssertionError("soon key should be evicted by volatile-ttl")
            if send_command(sock, b"GET", b"later") != value:
                raise AssertionError("later key should survive volatile-ttl")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")
    check_volatile_lru()
    check_volatile_lfu()
    check_volatile_ttl()


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/maxmemory_volatile_policies: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/maxmemory_volatile_policies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
