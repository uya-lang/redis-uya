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
    aof_path = ROOT / "build" / f"blocking-zset-{port}.aof"
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
            if send_command(sock, b"ZADD", b"zs", b"2", b"b", b"1", b"a") != 2:
                raise AssertionError("ZADD zs failed")
            if send_command(sock, b"BZPOPMIN", b"miss", b"zs", b"1") != [b"zs", b"a", b"1"]:
                raise AssertionError("BZPOPMIN immediate result mismatch")
            if send_command(sock, b"BZPOPMAX", b"miss", b"zs", b"1") != [b"zs", b"b", b"2"]:
                raise AssertionError("BZPOPMAX immediate result mismatch")

        with connect_with_retry(port, time.monotonic() + 5.0) as blocked_sock, connect_with_retry(port, time.monotonic() + 5.0) as wake_sock:
            send_only(blocked_sock, b"BZPOPMIN", b"miss", b"zwait", b"0")
            time.sleep(0.1)
            if send_command(wake_sock, b"ZADD", b"zwait", b"5", b"late", b"1", b"early") != 2:
                raise AssertionError("ZADD zwait failed")
            blocked_reply = read_resp(blocked_sock)
            if blocked_reply != [b"zwait", b"early", b"1"]:
                raise AssertionError(f"unexpected BZPOPMIN unblock reply: {blocked_reply!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as blocked_sock, connect_with_retry(port, time.monotonic() + 5.0) as wake_sock:
            send_only(blocked_sock, b"BZPOPMAX", b"zwait2", b"0")
            time.sleep(0.1)
            if send_command(wake_sock, b"ZADD", b"zwait2", b"5", b"late", b"1", b"early") != 2:
                raise AssertionError("ZADD zwait2 failed")
            blocked_reply = read_resp(blocked_sock)
            if blocked_reply != [b"zwait2", b"late", b"5"]:
                raise AssertionError(f"unexpected BZPOPMAX unblock reply: {blocked_reply!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            if send_command(sock, b"ZADD", b"zm", b"2", b"b", b"1", b"a", b"3", b"c") != 3:
                raise AssertionError("ZADD zm failed")
            if send_command(sock, b"BZMPOP", b"1", b"2", b"miss", b"zm", b"MIN", b"COUNT", b"2") != [b"zm", [[b"a", b"1"], [b"b", b"2"]]]:
                raise AssertionError("BZMPOP immediate MIN COUNT result mismatch")
            if send_command(sock, b"BZMPOP", b"1", b"1", b"zm", b"MAX") != [b"zm", [[b"c", b"3"]]]:
                raise AssertionError("BZMPOP immediate MAX result mismatch")

        with connect_with_retry(port, time.monotonic() + 5.0) as blocked_sock, connect_with_retry(port, time.monotonic() + 5.0) as wake_sock:
            send_only(blocked_sock, b"BZMPOP", b"0", b"1", b"zwait3", b"MIN", b"COUNT", b"2")
            time.sleep(0.1)
            if send_command(wake_sock, b"ZADD", b"zwait3", b"5", b"late", b"1", b"early", b"2", b"mid") != 3:
                raise AssertionError("ZADD zwait3 failed")
            blocked_reply = read_resp(blocked_sock)
            if blocked_reply != [b"zwait3", [[b"early", b"1"], [b"mid", b"2"]]]:
                raise AssertionError(f"unexpected BZMPOP unblock reply: {blocked_reply!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as timeout_sock:
            started = time.monotonic()
            send_only(timeout_sock, b"BZPOPMIN", b"timeout-zs", b"0.2")
            timeout_reply = read_resp(timeout_sock)
            elapsed = time.monotonic() - started
            if timeout_reply is not None:
                raise AssertionError(f"BZPOPMIN timeout should return null array, got {timeout_reply!r}")
            if elapsed < 0.15:
                raise AssertionError(f"BZPOPMIN timeout returned too early: {elapsed:.3f}s")

        with connect_with_retry(port, time.monotonic() + 5.0) as timeout_sock:
            started = time.monotonic()
            send_only(timeout_sock, b"BZMPOP", b"0.2", b"1", b"timeout-zm", b"MIN")
            timeout_reply = read_resp(timeout_sock)
            elapsed = time.monotonic() - started
            if timeout_reply is not None:
                raise AssertionError(f"BZMPOP timeout should return null array, got {timeout_reply!r}")
            if elapsed < 0.15:
                raise AssertionError(f"BZMPOP timeout returned too early: {elapsed:.3f}s")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/blocking_zset_smoke: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/blocking_zset_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
