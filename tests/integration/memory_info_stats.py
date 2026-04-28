#!/usr/bin/env python3
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "build" / "redis-uya"


class RespError(RuntimeError):
    pass


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
        raise RespError(read_line(sock).decode())
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


def parse_info_memory(raw: bytes) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in raw.decode().splitlines():
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if value.isdigit():
            result[key] = int(value)
    return result


def require_field(info: dict[str, int], name: str) -> int:
    if name not in info:
        raise AssertionError(f"missing INFO memory field: {name}")
    return info[name]


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"memory-info-{port}.aof"
    rdb_path = ROOT / "dump.rdb"
    aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            initial_raw = send_command(sock, b"INFO", b"memory")
            if not isinstance(initial_raw, bytes):
                raise AssertionError(f"unexpected INFO memory response: {initial_raw!r}")
            initial = parse_info_memory(initial_raw)
            require_field(initial, "used_memory")
            require_field(initial, "used_memory_peak")
            require_field(initial, "total_allocated")
            require_field(initial, "total_freed")
            require_field(initial, "allocator_total_allocations")
            require_field(initial, "allocator_active_allocations")

            if send_command(sock, b"SET", b"payload", b"x" * 256) != "OK":
                raise AssertionError("SET payload failed")
            after_set = parse_info_memory(send_command(sock, b"INFO", b"memory"))
            used_after_set = require_field(after_set, "used_memory")
            peak_after_set = require_field(after_set, "used_memory_peak")
            total_allocated = require_field(after_set, "total_allocated")
            total_allocations = require_field(after_set, "allocator_total_allocations")
            active_allocations = require_field(after_set, "allocator_active_allocations")
            if used_after_set <= 0:
                raise AssertionError(f"used_memory should grow after SET: {after_set!r}")
            if peak_after_set < used_after_set:
                raise AssertionError(f"peak should cover current used memory: {after_set!r}")
            if total_allocated < used_after_set:
                raise AssertionError(f"total_allocated should cover used memory: {after_set!r}")
            if total_allocations < active_allocations:
                raise AssertionError(f"total allocations should cover active allocations: {after_set!r}")

            if send_command(sock, b"DEL", b"payload") != 1:
                raise AssertionError("DEL payload failed")
            after_del = parse_info_memory(send_command(sock, b"INFO", b"memory"))
            if require_field(after_del, "used_memory_peak") < peak_after_set:
                raise AssertionError(f"peak should not shrink after DEL: {after_del!r}")
            if require_field(after_del, "total_freed") < require_field(after_set, "total_freed"):
                raise AssertionError(f"total_freed should be monotonic: {after_del!r}")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/memory_info_stats: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/memory_info_stats")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
