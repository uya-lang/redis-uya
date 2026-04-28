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
    if prefix == b"_":
        if read_line(sock) != b"":
            raise RuntimeError("invalid RESP3 null terminator")
        return None
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
    if prefix == b"%":
        count = int(read_line(sock))
        result = {}
        for _ in range(count):
            key = read_resp(sock)
            result[key] = read_resp(sock)
        return result
    if prefix == b">":
        count = int(read_line(sock))
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


def expect_error(sock: socket.socket, *parts: bytes, needle: str) -> None:
    try:
        send_command(sock, *parts)
    except RespError as exc:
        if needle not in str(exc):
            raise AssertionError(f"expected error containing {needle!r}, got {exc!r}") from exc
        return
    raise AssertionError(f"expected error containing {needle!r}")


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
    aof_path = ROOT / "build" / f"v0-5-compat-{port}.aof"
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
            if send_command(sock, b"CLIENT", b"SETINFO", b"LIB-NAME", b"redis-py") != "OK":
                raise AssertionError("CLIENT SETINFO compatibility path failed")
            hello = send_command(sock, b"HELLO", b"3", b"SETNAME", b"resp3-compat")
            if not isinstance(hello, dict) or hello.get(b"proto") != 3:
                raise AssertionError(f"unexpected HELLO response: {hello!r}")
            if send_command(sock, b"GET", b"missing") is not None:
                raise AssertionError("RESP3 GET missing should return Null")

            config = send_command(sock, b"CONFIG", b"GET", b"max*")
            if not isinstance(config, list):
                raise AssertionError(f"CONFIG GET max* returned non-array: {config!r}")
            config_dict = array_pairs_to_dict(config)
            if config_dict.get("maxclients") != "8" or config_dict.get("maxmemory") != "0":
                raise AssertionError(f"unexpected CONFIG GET max*: {config_dict!r}")

            client_info = send_command(sock, b"CLIENT", b"INFO")
            if not isinstance(client_info, bytes):
                raise AssertionError(f"CLIENT INFO returned non-bulk value: {client_info!r}")
            for needle in (b"name=resp3-compat", b"resp=3", b"lib-name=redis-py"):
                if needle not in client_info:
                    raise AssertionError(f"missing {needle!r} in CLIENT INFO: {client_info!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as watcher:
            if send_command(watcher, b"WATCH", b"watched") != "OK":
                raise AssertionError("WATCH failed")
            with connect_with_retry(port, time.monotonic() + 5.0) as writer:
                if send_command(writer, b"SET", b"watched", b"changed") != "OK":
                    raise AssertionError("writer SET failed")
            if send_command(watcher, b"MULTI") != "OK":
                raise AssertionError("MULTI failed")
            if send_command(watcher, b"GET", b"watched") != "QUEUED":
                raise AssertionError("GET was not queued")
            if send_command(watcher, b"EXEC") is not None:
                raise AssertionError("WATCH conflict should return a Null Array")

            if send_command(watcher, b"MULTI") != "OK":
                raise AssertionError("second MULTI failed")
            expect_error(watcher, b"CLIENT", b"ID", needle="CLIENT command inside MULTI")
            if send_command(watcher, b"DISCARD") != "OK":
                raise AssertionError("DISCARD after CLIENT error failed")

            if send_command(watcher, b"MULTI") != "OK":
                raise AssertionError("third MULTI failed")
            expect_error(watcher, b"SUBSCRIBE", b"compat", needle="pubsub command inside MULTI")
            if send_command(watcher, b"DISCARD") != "OK":
                raise AssertionError("DISCARD after Pub/Sub error failed")

        with connect_with_retry(port, time.monotonic() + 5.0) as sub_sock:
            hello = send_command(sub_sock, b"HELLO", b"3")
            if not isinstance(hello, dict) or hello.get(b"proto") != 3:
                raise AssertionError(f"unexpected subscriber HELLO: {hello!r}")
            subscribe = send_command(sub_sock, b"SUBSCRIBE", b"compat")
            if subscribe != [b"subscribe", b"compat", 1]:
                raise AssertionError(f"unexpected RESP3 subscribe push: {subscribe!r}")
            with connect_with_retry(port, time.monotonic() + 5.0) as pub_sock:
                if send_command(pub_sock, b"PUBLISH", b"compat", b"payload") != 1:
                    raise AssertionError("PUBLISH should report one receiver")
            message = read_resp(sub_sock)
            if message != [b"message", b"compat", b"payload"]:
                raise AssertionError(f"unexpected RESP3 pubsub message: {message!r}")
            unsubscribe = send_command(sub_sock, b"UNSUBSCRIBE", b"compat")
            if unsubscribe != [b"unsubscribe", b"compat", 0]:
                raise AssertionError(f"unexpected RESP3 unsubscribe push: {unsubscribe!r}")

        with connect_with_retry(port, time.monotonic() + 5.0) as err_sock:
            expect_error(err_sock, b"HELLO", b"4", needle="unsupported protocol version")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/v0_5_compat: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/v0_5_compat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
