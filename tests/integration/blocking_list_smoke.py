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
    if prefix == b"_":
        if read_exact(sock, 2) != b"\r\n":
            raise RuntimeError("invalid RESP3 null terminator")
        return None
    raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")


def encode_command(*parts: bytes) -> bytes:
    request = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        request.append(f"${len(part)}\r\n".encode())
        request.append(part)
        request.append(b"\r\n")
    return b"".join(request)


def send_command(sock: socket.socket, *parts: bytes):
    sock.sendall(encode_command(*parts))
    return read_resp(sock)


def send_only(sock: socket.socket, *parts: bytes) -> None:
    sock.sendall(encode_command(*parts))


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"blocking-list-{port}.aof"
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
            if send_command(sock, b"RPUSH", b"blk", b"x", b"y") != 2:
                raise AssertionError("RPUSH blk failed")
            if send_command(sock, b"BLPOP", b"miss", b"blk", b"1") != [b"blk", b"x"]:
                raise AssertionError("BLPOP immediate result mismatch")
            if send_command(sock, b"BRPOP", b"miss", b"blk", b"1") != [b"blk", b"y"]:
                raise AssertionError("BRPOP immediate result mismatch")
            if send_command(sock, b"BRPOPLPUSH", b"blk", b"dst", b"1") is not None:
                raise AssertionError("BRPOPLPUSH on missing source should be null")
            if send_command(sock, b"RPUSH", b"mov", b"a", b"b") != 2:
                raise AssertionError("RPUSH mov failed")
            if send_command(sock, b"BLMOVE", b"mov", b"dst", b"RIGHT", b"LEFT", b"1") != b"b":
                raise AssertionError("BLMOVE immediate result mismatch")
            if send_command(sock, b"LRANGE", b"dst", b"0", b"-1") != [b"b"]:
                raise AssertionError("BLMOVE destination mismatch")

        with connect_with_retry(port, time.monotonic() + 5.0) as blocked_sock, connect_with_retry(port, time.monotonic() + 5.0) as wake_sock:
            send_only(blocked_sock, b"BLPOP", b"miss", b"wait", b"0")
            time.sleep(0.1)
            if send_command(wake_sock, b"LPUSH", b"wait", b"wake-left") != 1:
                raise AssertionError("LPUSH wake-left failed")
            blocked_reply = read_resp(blocked_sock)
            if blocked_reply != [b"wait", b"wake-left"]:
                raise AssertionError(f"unexpected BLPOP unblock reply: {blocked_reply!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as blocked_sock, connect_with_retry(port, time.monotonic() + 5.0) as wake_sock:
            send_only(blocked_sock, b"BRPOP", b"miss", b"waitr", b"0")
            time.sleep(0.1)
            if send_command(wake_sock, b"RPUSH", b"waitr", b"wake-right") != 1:
                raise AssertionError("RPUSH wake-right failed")
            blocked_reply = read_resp(blocked_sock)
            if blocked_reply != [b"waitr", b"wake-right"]:
                raise AssertionError(f"unexpected BRPOP unblock reply: {blocked_reply!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as blocked_sock, connect_with_retry(port, time.monotonic() + 5.0) as wake_sock:
            send_only(blocked_sock, b"BRPOPLPUSH", b"movesrc", b"movedst", b"0")
            time.sleep(0.1)
            if send_command(wake_sock, b"RPUSH", b"movesrc", b"move-me") != 1:
                raise AssertionError("RPUSH move-me failed")
            blocked_reply = read_resp(blocked_sock)
            if blocked_reply != b"move-me":
                raise AssertionError(f"unexpected BRPOPLPUSH unblock reply: {blocked_reply!r}")
            moved = send_command(wake_sock, b"LRANGE", b"movedst", b"0", b"-1")
            if moved != [b"move-me"]:
                raise AssertionError(f"unexpected movedst contents: {moved!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as blocked_sock, connect_with_retry(port, time.monotonic() + 5.0) as wake_sock:
            send_only(blocked_sock, b"BLMOVE", b"movesrc2", b"movedst2", b"LEFT", b"RIGHT", b"0")
            time.sleep(0.1)
            if send_command(wake_sock, b"LPUSH", b"movesrc2", b"move-left") != 1:
                raise AssertionError("LPUSH move-left failed")
            blocked_reply = read_resp(blocked_sock)
            if blocked_reply != b"move-left":
                raise AssertionError(f"unexpected BLMOVE unblock reply: {blocked_reply!r}")
            moved = send_command(wake_sock, b"LRANGE", b"movedst2", b"0", b"-1")
            if moved != [b"move-left"]:
                raise AssertionError(f"unexpected movedst2 contents: {moved!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as timeout_sock:
            started = time.monotonic()
            send_only(timeout_sock, b"BLPOP", b"timeout-key", b"0.2")
            timeout_reply = read_resp(timeout_sock)
            elapsed = time.monotonic() - started
            if timeout_reply is not None:
                raise AssertionError(f"BLPOP timeout should return null array, got {timeout_reply!r}")
            if elapsed < 0.15:
                raise AssertionError(f"BLPOP timeout returned too early: {elapsed:.3f}s")

        with connect_with_retry(port, time.monotonic() + 5.0) as timeout_sock:
            started = time.monotonic()
            send_only(timeout_sock, b"BLMOVE", b"timeout-src", b"timeout-dst", b"LEFT", b"RIGHT", b"0.2")
            timeout_reply = read_resp(timeout_sock)
            elapsed = time.monotonic() - started
            if timeout_reply is not None:
                raise AssertionError(f"BLMOVE timeout should return null bulk, got {timeout_reply!r}")
            if elapsed < 0.15:
                raise AssertionError(f"BLMOVE timeout returned too early: {elapsed:.3f}s")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/blocking_list_smoke: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/blocking_list_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
