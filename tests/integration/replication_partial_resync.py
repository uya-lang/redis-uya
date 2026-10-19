#!/usr/bin/env python3
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "build" / "redis-uya"
BACKLOG_BYTES = 16384
OVERSIZE_WRITES = 24
OVERSIZE_VALUE_BYTES = 1024


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


def recv_line(sock: socket.socket) -> bytes:
    data = b""
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed while reading line")
        data += chunk
    return data[:-2]


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


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGCONT)
        except ProcessLookupError:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def parse_info_field(reply: bytes, field: bytes) -> int:
    marker = field + b":"
    for line in reply.split(b"\r\n"):
        if line.startswith(marker):
            return int(line[len(marker) :])
    raise AssertionError(f"missing INFO field {field!r}: {reply!r}")


def parse_replica_role_offset(reply: bytes) -> int:
    if not reply.startswith(b"*5\r\n$5\r\nslave\r\n"):
        raise AssertionError(f"expected replica ROLE array, got {reply!r}")
    last_line = reply[:-2].rsplit(b"\r\n", 1)[-1]
    if not last_line.startswith(b":"):
        raise AssertionError(f"missing replica ROLE offset: {reply!r}")
    return int(last_line[1:])


def fetch_master_offsets(port: int) -> tuple[int, int]:
    with connect_with_retry(port, time.monotonic() + 2.0) as sock:
        sock.settimeout(2.0)
        info = send_command(sock, b"INFO", b"replication")
    master_offset = parse_info_field(info, b"master_repl_offset")
    history_len = parse_info_field(info, b"repl_backlog_histlen")
    return master_offset, master_offset - history_len


def fetch_replica_offset(port: int) -> int:
    with connect_with_retry(port, time.monotonic() + 2.0) as sock:
        sock.settimeout(2.0)
        return parse_replica_role_offset(send_command(sock, b"ROLE"))


def wait_for_replication_state(port: int, marker: bytes, deadline: float) -> None:
    last = b""
    while time.monotonic() < deadline:
        with connect_with_retry(port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            last = send_command(sock, b"INFO", b"replication")
            if marker in last:
                return
        time.sleep(0.05)
    raise RuntimeError(f"replication state marker {marker!r} not observed, last={last!r}")


def wait_for_replica_values(port: int, expected: list[tuple[bytes, bytes]], deadline: float) -> None:
    last: list[bytes] = []
    while time.monotonic() < deadline:
        with connect_with_retry(port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            last = [send_command(sock, b"GET", key) for key, _ in expected]
            if all(actual == value for actual, (_, value) in zip(last, expected)):
                return
        time.sleep(0.05)
    raise RuntimeError(f"replica values did not converge: expected={expected!r}, last={last!r}")


def wait_for_offsets_equal(master_port: int, replica_port: int, deadline: float) -> int:
    last_master = -1
    last_replica = -1
    while time.monotonic() < deadline:
        master_offset, _ = fetch_master_offsets(master_port)
        replica_offset = fetch_replica_offset(replica_port)
        if master_offset == replica_offset:
            return replica_offset
        last_master = master_offset
        last_replica = replica_offset
        time.sleep(0.05)
    raise RuntimeError(
        f"replica offset did not catch up: master={last_master}, replica={last_replica}"
    )


def send_payload_writes(port: int) -> None:
    payload = b"x" * OVERSIZE_VALUE_BYTES
    with connect_with_retry(port, time.monotonic() + 2.0) as sock:
        sock.settimeout(3.0)
        for index in range(OVERSIZE_WRITES):
            key = f"oversize-{index}".encode()
            if send_command(sock, b"SET", key, payload) != b"+OK\r\n":
                raise AssertionError(f"master oversize SET {index} failed")


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    master_port = find_free_port()
    replica_port = find_free_port()
    master_aof = ROOT / "build" / f"master-partial-resync-{master_port}.aof"
    replica_aof = ROOT / "build" / f"replica-partial-resync-{replica_port}.aof"
    master_aof.unlink(missing_ok=True)
    replica_aof.unlink(missing_ok=True)

    master = subprocess.Popen(
        [str(BIN), str(master_port), "8", str(master_aof)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    replica = subprocess.Popen(
        [str(BIN), str(replica_port), "8", str(replica_aof)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"SET", b"stable", b"initial") != b"+OK\r\n":
                raise AssertionError("master initial SET failed")

        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            replicaof = send_command(sock, b"REPLICAOF", b"127.0.0.1", str(master_port).encode())
            if replicaof != b"+OK\r\n":
                raise AssertionError(f"replica REPLICAOF failed: {replicaof!r}")

        wait_for_replication_state(replica_port, b"replication_state:connected", time.monotonic() + 5.0)
        wait_for_replica_values(replica_port, [(b"stable", b"$7\r\ninitial\r\n")], time.monotonic() + 5.0)
        wait_for_offsets_equal(master_port, replica_port, time.monotonic() + 5.0)

        os.kill(replica.pid, signal.SIGSTOP)
        with connect_with_retry(master_port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"SET", b"partial-key", b"partial-value") != b"+OK\r\n":
                raise AssertionError("master partial SET failed")
        os.kill(replica.pid, signal.SIGCONT)
        wait_for_replica_values(
            replica_port,
            [(b"partial-key", b"$13\r\npartial-value\r\n")],
            time.monotonic() + 5.0,
        )
        wait_for_offsets_equal(master_port, replica_port, time.monotonic() + 5.0)

        os.kill(replica.pid, signal.SIGSTOP)
        send_payload_writes(master_port)
        master_offset, first_offset = fetch_master_offsets(master_port)
        if master_offset - first_offset > BACKLOG_BYTES:
            raise AssertionError(
                f"master backlog grew beyond configured bound: {master_offset - first_offset}"
            )
        if first_offset <= 0:
            raise AssertionError(f"expected backlog trim past its first offset, got {first_offset}")
        os.kill(replica.pid, signal.SIGCONT)

        expected = [(f"oversize-{index}".encode(), b"$1024\r\n" + b"x" * 1024 + b"\r\n") for index in range(OVERSIZE_WRITES)]
        expected.append((b"stable", b"$7\r\ninitial\r\n"))
        wait_for_replica_values(replica_port, expected, time.monotonic() + 8.0)
        wait_for_replication_state(replica_port, b"replication_state:connected", time.monotonic() + 5.0)
        wait_for_offsets_equal(master_port, replica_port, time.monotonic() + 5.0)

        with connect_with_retry(master_port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"SET", b"after-fullresync", b"ok") != b"+OK\r\n":
                raise AssertionError("master post-FULLRESYNC SET failed")
        wait_for_replica_values(
            replica_port,
            [(b"after-fullresync", b"$2\r\nok\r\n")],
            time.monotonic() + 5.0,
        )
        wait_for_offsets_equal(master_port, replica_port, time.monotonic() + 5.0)
    finally:
        stop_process(master)
        stop_process(replica)
        master_aof.unlink(missing_ok=True)
        replica_aof.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/replication_partial_resync: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/replication_partial_resync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
