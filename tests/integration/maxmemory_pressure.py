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


def parse_info_memory(raw: bytes) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    for line in raw.decode().splitlines():
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key] = int(value) if value.isdigit() else value
    return result


def memory_info(sock: socket.socket) -> dict[str, int | str]:
    raw = send_command(sock, b"INFO", b"memory")
    if not isinstance(raw, bytes):
        raise AssertionError(f"unexpected INFO memory response: {raw!r}")
    info = parse_info_memory(raw)
    required = (
        "used_memory",
        "used_memory_peak",
        "total_allocated",
        "total_freed",
        "allocator_active_allocations",
        "allocator_slab_cached_blocks",
        "allocator_slab_reuse_count",
        "maxmemory",
        "maxmemory_policy",
    )
    for field in required:
        if field not in info:
            raise AssertionError(f"missing INFO memory field {field}: {raw!r}")
    if int(info["used_memory_peak"]) < int(info["used_memory"]):
        raise AssertionError(f"used_memory_peak should cover used_memory: {info!r}")
    return info


def run_server(policy: str, maxmemory: int):
    port = find_free_port()
    aof_path = ROOT / "build" / f"pressure-{policy}-{port}.aof"
    rdb_paths = (ROOT / "dump.rdb", ROOT / "build" / "dump.rdb")
    aof_path.unlink(missing_ok=True)
    for rdb_path in rdb_paths:
        rdb_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "16", str(aof_path), str(maxmemory), policy],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return port, aof_path, rdb_paths, proc


def assert_policy(info: dict[str, int | str], policy: str, maxmemory: int) -> None:
    if info.get("maxmemory_policy") != policy:
        raise AssertionError(f"unexpected maxmemory policy: {info!r}")
    if int(info["maxmemory"]) != maxmemory:
        raise AssertionError(f"unexpected maxmemory limit: {info!r}")


def check_noeviction_pressure() -> None:
    maxmemory = 3200
    port, aof_path, rdb_paths, proc = run_server("noeviction", maxmemory)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            assert_policy(memory_info(sock), "noeviction", maxmemory)
            ok_count = 0
            oom_count = 0
            value = b"n" * 256
            for index in range(24):
                try:
                    if send_command(sock, b"SET", f"n{index:02d}".encode(), value) == "OK":
                        ok_count += 1
                except RespError as exc:
                    if "maxmemory" not in str(exc):
                        raise
                    oom_count += 1
            if ok_count == 0 or oom_count == 0:
                raise AssertionError(f"noeviction should mix successful writes and OOM: ok={ok_count} oom={oom_count}")
            if send_command(sock, b"GET", b"n23") is not None:
                raise AssertionError("late OOM write should not be stored")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        for rdb_path in rdb_paths:
            rdb_path.unlink(missing_ok=True)


def check_allkeys_lru_pressure() -> None:
    maxmemory = 24000
    port, aof_path, rdb_paths, proc = run_server("allkeys-lru", maxmemory)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            assert_policy(memory_info(sock), "allkeys-lru", maxmemory)
            value = b"l" * 512
            for index in range(36):
                if send_command(sock, b"SET", f"l{index:02d}".encode(), value) != "OK":
                    raise AssertionError(f"SET l{index:02d} failed under allkeys-lru pressure")
                if index % 6 == 0:
                    _ = send_command(sock, b"GET", f"l{index:02d}".encode())
            if send_command(sock, b"GET", b"l00") is not None:
                raise AssertionError("oldest allkeys-lru key should be evicted under pressure")
            if send_command(sock, b"GET", b"l35") != value:
                raise AssertionError("newest allkeys-lru key should survive pressure")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        for rdb_path in rdb_paths:
            rdb_path.unlink(missing_ok=True)


def check_allkeys_lfu_pressure() -> None:
    maxmemory = 24000
    port, aof_path, rdb_paths, proc = run_server("allkeys-lfu", maxmemory)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            assert_policy(memory_info(sock), "allkeys-lfu", maxmemory)
            value = b"f" * 512
            if send_command(sock, b"SET", b"hot", value) != "OK":
                raise AssertionError("SET hot failed")
            for _ in range(8):
                if send_command(sock, b"GET", b"hot") != value:
                    raise AssertionError("GET hot failed during warmup")
            for index in range(30):
                if send_command(sock, b"SET", f"f{index:02d}".encode(), value) != "OK":
                    raise AssertionError(f"SET f{index:02d} failed under allkeys-lfu pressure")
                if index % 4 == 0 and send_command(sock, b"GET", b"hot") != value:
                    raise AssertionError("hot key should survive during allkeys-lfu pressure")
            if send_command(sock, b"GET", b"hot") != value:
                raise AssertionError("frequently used key should survive allkeys-lfu pressure")
            if send_command(sock, b"GET", b"f29") != value:
                raise AssertionError("latest allkeys-lfu key should survive pressure")
            if send_command(sock, b"GET", b"f00") is not None:
                raise AssertionError("cold allkeys-lfu key should be evicted under pressure")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        for rdb_path in rdb_paths:
            rdb_path.unlink(missing_ok=True)


def check_volatile_ttl_pressure() -> None:
    maxmemory = 40000
    port, aof_path, rdb_paths, proc = run_server("volatile-ttl", maxmemory)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            assert_policy(memory_info(sock), "volatile-ttl", maxmemory)
            value = b"v" * 384
            if send_command(sock, b"SET", b"persistent", value) != "OK":
                raise AssertionError("SET persistent failed")
            for index in range(32):
                key = f"v{index:02d}".encode()
                if send_command(sock, b"SET", key, value) != "OK":
                    raise AssertionError(f"SET {key!r} failed under volatile-ttl pressure")
                ttl = str(30 + index).encode()
                if send_command(sock, b"EXPIRE", key, ttl) != 1:
                    raise AssertionError(f"EXPIRE {key!r} failed under volatile-ttl pressure")
            if send_command(sock, b"GET", b"persistent") != value:
                raise AssertionError("persistent key must survive volatile-ttl pressure")
            if send_command(sock, b"GET", b"v31") != value:
                raise AssertionError("latest volatile key should survive pressure")
            if send_command(sock, b"GET", b"v00") is not None:
                raise AssertionError("nearest-deadline volatile key should be evicted under pressure")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        for rdb_path in rdb_paths:
            rdb_path.unlink(missing_ok=True)


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")
    check_noeviction_pressure()
    check_allkeys_lru_pressure()
    check_allkeys_lfu_pressure()
    check_volatile_ttl_pressure()


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/maxmemory_pressure: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/maxmemory_pressure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
