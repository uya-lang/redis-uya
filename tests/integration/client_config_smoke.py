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
        line = read_line(sock)
        if line != b"":
            raise RuntimeError(f"invalid RESP3 null suffix: {line!r}")
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
    aof_path = ROOT / "build" / f"client-config-{port}.aof"
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
            client_id = send_command(sock, b"CLIENT", b"ID")
            if not isinstance(client_id, int) or client_id <= 0:
                raise AssertionError(f"unexpected CLIENT ID: {client_id!r}")

            if send_command(sock, b"CLIENT", b"GETNAME") is not None:
                raise AssertionError("new connection should not have a client name")
            if send_command(sock, b"CLIENT", b"SETNAME", b"smoke-client") != "OK":
                raise AssertionError("CLIENT SETNAME failed")
            if send_command(sock, b"CLIENT", b"GETNAME") != b"smoke-client":
                raise AssertionError("CLIENT GETNAME did not return the stored name")

            if send_command(sock, b"CLIENT", b"SETINFO", b"LIB-NAME", b"redis-uya-test") != "OK":
                raise AssertionError("CLIENT SETINFO LIB-NAME failed")
            if send_command(sock, b"CLIENT", b"SETINFO", b"LIB-VER", b"0.5.0") != "OK":
                raise AssertionError("CLIENT SETINFO LIB-VER failed")

            info = send_command(sock, b"CLIENT", b"INFO")
            if not isinstance(info, bytes):
                raise AssertionError(f"CLIENT INFO returned non-bulk value: {info!r}")
            for needle in (b"name=smoke-client", b"lib-name=redis-uya-test", b"lib-ver=0.5.0"):
                if needle not in info:
                    raise AssertionError(f"missing {needle!r} in CLIENT INFO: {info!r}")

            listed = send_command(sock, b"CLIENT", b"LIST")
            if not isinstance(listed, bytes) or b"name=smoke-client" not in listed:
                raise AssertionError(f"unexpected CLIENT LIST: {listed!r}")

            hello = send_command(sock, b"HELLO", b"3", b"SETNAME", b"resp3-client")
            if not isinstance(hello, dict) or hello.get(b"proto") != 3:
                raise AssertionError(f"unexpected HELLO 3 response: {hello!r}")
            if send_command(sock, b"CLIENT", b"GETNAME") != b"resp3-client":
                raise AssertionError("HELLO SETNAME did not update client name")

            max_config_raw = send_command(sock, b"CONFIG", b"GET", b"max*")
            if not isinstance(max_config_raw, list):
                raise AssertionError(f"CONFIG GET max* returned non-array: {max_config_raw!r}")
            max_config = array_pairs_to_dict(max_config_raw)
            if max_config.get("maxclients") != "8" or max_config.get("maxmemory") != "0":
                raise AssertionError(f"unexpected CONFIG GET max*: {max_config!r}")

            db_config_raw = send_command(sock, b"CONFIG", b"GET", b"databases")
            if array_pairs_to_dict(db_config_raw).get("databases") != "1":
                raise AssertionError(f"unexpected CONFIG GET databases: {db_config_raw!r}")

            help_reply = send_command(sock, b"CONFIG", b"HELP")
            if not isinstance(help_reply, list) or b"CONFIG RESETSTAT" not in help_reply:
                raise AssertionError(f"unexpected CONFIG HELP: {help_reply!r}")
            if send_command(sock, b"CONFIG", b"RESETSTAT") != "OK":
                raise AssertionError("CONFIG RESETSTAT failed")
            if send_command(sock, b"QUIT") != "OK":
                raise AssertionError("QUIT failed")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/client_config_smoke: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/client_config_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
