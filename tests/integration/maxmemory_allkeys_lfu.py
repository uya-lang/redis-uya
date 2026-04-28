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


def array_pairs_to_dict(raw: list[bytes]) -> dict[str, str]:
    result: dict[str, str] = {}
    i = 0
    while i + 1 < len(raw):
        result[raw[i].decode()] = raw[i + 1].decode()
        i += 2
    return result


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"allkeys-lfu-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path), "5000", "allkeys-lfu"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            config = send_command(sock, b"CONFIG", b"GET", b"maxmemory-policy")
            if not isinstance(config, list) or array_pairs_to_dict(config).get("maxmemory-policy") != "allkeys-lfu":
                raise AssertionError(f"unexpected CONFIG GET maxmemory-policy: {config!r}")

            info = send_command(sock, b"INFO", b"memory")
            if not isinstance(info, bytes) or b"maxmemory_policy:allkeys-lfu" not in info:
                raise AssertionError(f"unexpected INFO memory: {info!r}")

            cold_value = b"c" * 900
            hot_value = b"h" * 900
            new_value = b"n" * 900
            if send_command(sock, b"SET", b"cold", cold_value) != "OK":
                raise AssertionError("SET cold failed")
            if send_command(sock, b"SET", b"hot", hot_value) != "OK":
                raise AssertionError("SET hot failed")
            if send_command(sock, b"GET", b"hot") != hot_value:
                raise AssertionError("GET hot failed before eviction")
            if send_command(sock, b"GET", b"hot") != hot_value:
                raise AssertionError("second GET hot failed before eviction")
            if send_command(sock, b"SET", b"new", new_value) != "OK":
                raise AssertionError("SET new should evict the least frequently used key")

            if send_command(sock, b"GET", b"cold") is not None:
                raise AssertionError("cold key should be evicted by allkeys-lfu")
            if send_command(sock, b"GET", b"hot") != hot_value:
                raise AssertionError("hot key should survive allkeys-lfu")
            if send_command(sock, b"GET", b"new") != new_value:
                raise AssertionError("new key should be stored after eviction")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/maxmemory_allkeys_lfu: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/maxmemory_allkeys_lfu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
