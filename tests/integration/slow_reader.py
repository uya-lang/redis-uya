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


def connect_with_retry(port: int, deadline: float, receive_buffer: int | None = None) -> socket.socket:
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if receive_buffer is not None:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, receive_buffer)
            sock.settimeout(0.2)
            sock.connect(("127.0.0.1", port))
            return sock
        except OSError as exc:
            sock.close()
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


def roundtrip(sock: socket.socket, request: bytes, expected: bytes) -> None:
    sock.sendall(request)
    actual = recv_exact(sock, len(expected))
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def read_bulk(sock: socket.socket) -> bytes:
    prefix = recv_exact(sock, 1)
    if prefix != b"$":
        raise AssertionError(f"expected bulk response, got prefix {prefix!r}")
    length_bytes = bytearray()
    while True:
        byte = recv_exact(sock, 1)
        if byte == b"\r":
            if recv_exact(sock, 1) != b"\n":
                raise AssertionError("invalid bulk length terminator")
            break
        length_bytes.extend(byte)
    length = int(length_bytes)
    payload = recv_exact(sock, length)
    if recv_exact(sock, 2) != b"\r\n":
        raise AssertionError("invalid bulk payload terminator")
    return payload


def parse_client_fields(line: bytes) -> dict[bytes, bytes]:
    fields: dict[bytes, bytes] = {}
    for item in line.split():
        key, separator, value = item.partition(b"=")
        if separator:
            fields[key] = value
    return fields


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def make_set_request(key: bytes, value: bytes) -> bytes:
    return (
        b"*3\r\n"
        + b"$3\r\nSET\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
        + f"${len(value)}\r\n".encode()
        + value
        + b"\r\n"
    )


def make_get_request(key: bytes) -> bytes:
    return (
        b"*2\r\n"
        + b"$3\r\nGET\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
    )


def make_mget_request(key: bytes) -> bytes:
    return (
        b"*2\r\n"
        + b"$4\r\nMGET\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
    )


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"slow-reader-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    slow_sock: socket.socket | None = None
    active_sock: socket.socket | None = None
    try:
        slow_sock = connect_with_retry(port, time.monotonic() + 5.0, receive_buffer=1024)
        slow_sock.settimeout(1.0)
        roundtrip(
            slow_sock,
            b"*3\r\n$6\r\nCLIENT\r\n$7\r\nSETNAME\r\n$11\r\nslow-reader\r\n",
            b"+OK\r\n",
        )

        key = b"payload"
        value = b"x" * 6000
        roundtrip(slow_sock, make_set_request(key, value), b"+OK\r\n")

        active_sock = socket.create_connection(("127.0.0.1", port), timeout=1.0)
        active_sock.settimeout(1.0)
        roundtrip(active_sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")
        slow_line: bytes | None = None
        slow_fields: dict[bytes, bytes] = {}
        get_request = make_get_request(key)
        mget_request = make_mget_request(key)
        for request_index in range(600):
            expected_cmd = b"get"
            request = get_request
            if request_index % 2 != 0:
                expected_cmd = b"mget"
                request = mget_request
            slow_sock.sendall(request)
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                active_sock.sendall(b"*2\r\n$6\r\nCLIENT\r\n$4\r\nLIST\r\n")
                clients = read_bulk(active_sock)
                slow_line = next(
                    (line for line in clients.splitlines() if b"name=slow-reader" in line),
                    None,
                )
                if slow_line is None:
                    raise AssertionError(f"slow reader missing from CLIENT LIST: {clients!r}")
                slow_fields = parse_client_fields(slow_line)
                if int(slow_fields.get(b"obl", b"0")) > 0:
                    break
                if slow_fields.get(b"cmd") == expected_cmd:
                    break
                time.sleep(0.001)
            if int(slow_fields.get(b"obl", b"0")) > 0:
                break
            if slow_fields.get(b"cmd") != expected_cmd:
                raise AssertionError(
                    f"slow reader did not consume request {request_index}: {slow_line!r}"
                )
        if slow_line is None or int(slow_fields.get(b"obl", b"0")) <= 0:
            raise AssertionError(f"slow reader has no pending output bytes: {slow_line!r}")
        if slow_fields.get(b"oll") != b"0" or slow_fields.get(b"omem") != b"0":
            raise AssertionError(f"slow reader returned invalid output queue usage: {slow_line!r}")
    finally:
        if active_sock is not None:
            active_sock.close()
        if slow_sock is not None:
            slow_sock.close()
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/slow_reader: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/slow_reader")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
