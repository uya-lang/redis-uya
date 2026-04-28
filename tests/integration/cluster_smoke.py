#!/usr/bin/env python3
from __future__ import annotations

import socket
import subprocess
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


def read_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = read_exact(sock, 1)
        chunks.append(chunk)
        if len(chunks) >= 2 and chunks[-2] == b"\r" and chunks[-1] == b"\n":
            return b"".join(chunks[:-2])


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


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"cluster-smoke-{port}.aof"
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
            if send_command(sock, b"CLUSTER", b"KEYSLOT", b"123456789") != 12739:
                raise AssertionError("CLUSTER KEYSLOT returned wrong slot for 123456789")
            if send_command(sock, b"CLUSTER", b"KEYSLOT", b"foo{bar}zap") != 5061:
                raise AssertionError("CLUSTER KEYSLOT did not honor hash tags")

            info = send_command(sock, b"CLUSTER", b"INFO")
            if not isinstance(info, bytes):
                raise AssertionError(f"CLUSTER INFO returned non-bulk value: {info!r}")
            for needle in (b"cluster_enabled:1\r\n", b"cluster_state:ok\r\n", b"cluster_slots_assigned:16384\r\n"):
                if needle not in info:
                    raise AssertionError(f"missing {needle!r} in CLUSTER INFO: {info!r}")

            nodes = send_command(sock, b"CLUSTER", b"NODES")
            if not isinstance(nodes, bytes):
                raise AssertionError(f"CLUSTER NODES returned non-bulk value: {nodes!r}")
            for needle in (b"myself,master", f"127.0.0.1:{port}@{port + 10000}".encode(), b"0-16383"):
                if needle not in nodes:
                    raise AssertionError(f"missing {needle!r} in CLUSTER NODES: {nodes!r}")

            slots = send_command(sock, b"CLUSTER", b"SLOTS")
            if not isinstance(slots, list) or len(slots) != 1:
                raise AssertionError(f"unexpected CLUSTER SLOTS shape: {slots!r}")
            slot_range = slots[0]
            if slot_range[0] != 0 or slot_range[1] != 16383:
                raise AssertionError(f"unexpected slot range: {slot_range!r}")
            node = slot_range[2]
            if node[0] != b"127.0.0.1" or node[1] != port or not isinstance(node[2], bytes) or len(node[2]) != 40:
                raise AssertionError(f"unexpected slot owner: {node!r}")

            help_reply = send_command(sock, b"CLUSTER", b"HELP")
            if not isinstance(help_reply, list) or b"CLUSTER KEYSLOT <key>" not in help_reply:
                raise AssertionError(f"unexpected CLUSTER HELP: {help_reply!r}")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run_smoke()
    print("cluster smoke passed")
