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


def connect_with_retry(port: int, deadline: float) -> socket.socket:
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            return socket.create_connection(("127.0.0.1", port), timeout=0.2)
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"failed to connect to redis-uya on port {port}: {last_error}")


def recv_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed while reading line")
        chunks.append(chunk)
        if len(chunks) >= 2 and chunks[-2] == b"\r" and chunks[-1] == b"\n":
            return b"".join(chunks[:-2])


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


def send_command(sock: socket.socket, *parts: bytes) -> bytes:
    buf = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        buf.append(f"${len(part)}\r\n".encode())
        buf.append(part)
        buf.append(b"\r\n")
    sock.sendall(b"".join(buf))

    prefix = recv_exact(sock, 1)
    if prefix in (b"+", b"-", b":"):
        return prefix + recv_line(sock) + b"\r\n"
    if prefix == b"$":
        size = int(recv_line(sock))
        if size < 0:
            return b"$-1\r\n"
        payload = recv_exact(sock, size + 2)
        return prefix + str(size).encode() + b"\r\n" + payload
    if prefix == b"*":
        count = int(recv_line(sock))
        out = prefix + str(count).encode() + b"\r\n"
        for _ in range(count):
            out += recv_nested(sock)
        return out
    raise RuntimeError(f"unexpected RESP prefix: {prefix!r}")


def recv_nested(sock: socket.socket) -> bytes:
    prefix = recv_exact(sock, 1)
    if prefix in (b"+", b"-", b":"):
        return prefix + recv_line(sock) + b"\r\n"
    if prefix == b"$":
        size = int(recv_line(sock))
        if size < 0:
            return b"$-1\r\n"
        payload = recv_exact(sock, size + 2)
        return prefix + str(size).encode() + b"\r\n" + payload
    raise RuntimeError(f"unexpected nested RESP prefix: {prefix!r}")


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def parse_fullresync(resp: bytes) -> tuple[str, int]:
    if not resp.startswith(b"+FULLRESYNC "):
        raise AssertionError(f"expected FULLRESYNC reply, got {resp!r}")
    body = resp[1:-2].decode()
    _, replid, offset_text = body.split(" ", 2)
    return replid, int(offset_text)


def send_raw_request(sock: socket.socket, *parts: bytes) -> None:
    buf = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        buf.append(f"${len(part)}\r\n".encode())
        buf.append(part)
        buf.append(b"\r\n")
    sock.sendall(b"".join(buf))


def recv_psync_fullresync(sock: socket.socket) -> tuple[str, int, bytes]:
    line = recv_exact(sock, 1)
    if line != b"+":
        raise AssertionError(f"expected simple string prefix, got {line!r}")
    header = recv_line(sock) + b"\r\n"
    replid, offset = parse_fullresync(line + header)

    bulk_prefix = recv_exact(sock, 1)
    if bulk_prefix != b"$":
        raise AssertionError(f"expected bulk prefix after FULLRESYNC, got {bulk_prefix!r}")
    snapshot_len = int(recv_line(sock))
    payload = recv_exact(sock, snapshot_len)
    terminator = recv_exact(sock, 2)
    if terminator != b"\r\n":
        raise AssertionError(f"invalid snapshot terminator: {terminator!r}")
    return replid, offset, payload


def recv_psync_continue(sock: socket.socket, expected_offset: int, expected_delta: bytes) -> None:
    prefix = recv_exact(sock, 1)
    if prefix != b"+":
        raise AssertionError(f"expected simple string prefix for CONTINUE, got {prefix!r}")
    line = recv_line(sock).decode()
    if not line.startswith("CONTINUE "):
        raise AssertionError(f"expected CONTINUE line, got {line!r}")
    offset = int(line.split(" ", 1)[1])
    if offset != expected_offset:
        raise AssertionError(f"expected CONTINUE offset {expected_offset}, got {offset}")

    bulk_prefix = recv_exact(sock, 1)
    if bulk_prefix != b"$":
        raise AssertionError(f"expected bulk prefix after CONTINUE, got {bulk_prefix!r}")
    payload_len = int(recv_line(sock))
    if payload_len != len(expected_delta):
        raise AssertionError(f"expected delta len {len(expected_delta)}, got {payload_len}")
    delta = recv_exact(sock, payload_len)
    terminator = recv_exact(sock, 2)
    if terminator != b"\r\n":
        raise AssertionError(f"invalid delta terminator: {terminator!r}")
    if delta != expected_delta:
        raise AssertionError(f"expected backlog delta {expected_delta!r}, got {delta!r}")


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"psync-{port}.aof"
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
            sock.settimeout(2.0)

            set_ok = send_command(sock, b"SET", b"key", b"value")
            if set_ok != b"+OK\r\n":
                raise AssertionError(f"expected +OK on SET, got {set_ok!r}")

            send_raw_request(sock, b"PSYNC", b"?", b"-1")
            replid, offset, snapshot = recv_psync_fullresync(sock)
            if len(replid) != 40:
                raise AssertionError(f"expected 40-char replid, got {replid!r}")
            if offset <= 0:
                raise AssertionError(f"expected positive replication offset, got {offset}")
            if not snapshot.startswith(b"RUYARDB1"):
                raise AssertionError(f"expected project RDB snapshot, got {snapshot[:8]!r}")
            if b"key" not in snapshot or b"value" not in snapshot:
                raise AssertionError(f"snapshot missing current key/value: {snapshot!r}")

            second_set = b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nnewer\r\n"
            set_ok_2 = send_command(sock, b"SET", b"key", b"newer")
            if set_ok_2 != b"+OK\r\n":
                raise AssertionError(f"expected +OK on second SET, got {set_ok_2!r}")

            send_raw_request(sock, b"PSYNC", replid.encode(), str(offset).encode())
            recv_psync_continue(sock, offset + len(second_set), second_set)

            quit_ok = send_command(sock, b"QUIT")
            if quit_ok != b"+OK\r\n":
                raise AssertionError(f"expected +OK on QUIT, got {quit_ok!r}")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/replication_psync_backlog: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/replication_psync_backlog")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
