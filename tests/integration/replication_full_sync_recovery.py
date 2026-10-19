#!/usr/bin/env python3
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "build" / "redis-uya"
REPLID = b"a" * 40
FULL_SYNC_OFFSET = 37
CRC64_POLY = 0x95AC9329AC4BC9B5


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
        return prefix + str(size).encode() + b"\r\n" + recv_exact(sock, size + 2)
    raise RuntimeError(f"unexpected nested RESP prefix: {prefix!r}")


def send_command(sock: socket.socket, *parts: bytes) -> bytes:
    payload = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        payload.append(f"${len(part)}\r\n".encode())
        payload.append(part)
        payload.append(b"\r\n")
    sock.sendall(b"".join(payload))

    prefix = recv_exact(sock, 1)
    if prefix in (b"+", b"-", b":"):
        return prefix + recv_line(sock) + b"\r\n"
    if prefix == b"$":
        size = int(recv_line(sock))
        if size < 0:
            return b"$-1\r\n"
        return prefix + str(size).encode() + b"\r\n" + recv_exact(sock, size + 2)
    if prefix == b"*":
        count = int(recv_line(sock))
        out = prefix + str(count).encode() + b"\r\n"
        for _ in range(count):
            out += recv_nested(sock)
        return out
    raise RuntimeError(f"unexpected RESP prefix: {prefix!r}")


def recv_command(sock: socket.socket) -> list[bytes] | None:
    try:
        first = recv_line(sock)
    except (OSError, RuntimeError):
        return None
    if not first.startswith(b"*"):
        return None
    count = int(first[1:])
    parts: list[bytes] = []
    for _ in range(count):
        header = recv_line(sock)
        if not header.startswith(b"$"):
            return None
        parts.append(recv_exact(sock, int(header[1:])))
        if recv_exact(sock, 2) != b"\r\n":
            return None
    return parts


def crc64(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ CRC64_POLY
            else:
                crc >>= 1
    return crc & 0xFFFFFFFFFFFFFFFF


def make_snapshot(key: bytes, value: bytes) -> bytes:
    return (
        b"RUYARDB1"
        + bytes([0])
        + struct.pack(">I", len(key))
        + key
        + struct.pack(">I", len(value))
        + value
        + bytes([0xFF])
    )


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


class FakeFullSyncMaster:
    def __init__(self, snapshot: bytes, corrupt_snapshot: bytes) -> None:
        self.snapshot = snapshot
        self.corrupt_snapshot = corrupt_snapshot
        self.allow_corrupt = threading.Event()
        self.allow_valid = threading.Event()
        self.stop_event = threading.Event()
        self.psync_count = 0
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = int(self.sock.getsockname()[1])
        self.sock.listen()

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.stop_event.set()
        self.sock.close()
        self.thread.join(timeout=2.0)

    def _fullresync(self, checksum: int) -> bytes:
        return (
            b"+FULLRESYNC "
            + REPLID
            + b" "
            + str(FULL_SYNC_OFFSET).encode()
            + b" "
            + f"{checksum:016x}".encode()
            + b"\r\n"
        )

    def _send_bulk(self, conn: socket.socket, payload: bytes) -> None:
        conn.sendall(b"$" + str(len(payload)).encode() + b"\r\n" + payload + b"\r\n")

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(6.0)
        while not self.stop_event.is_set():
            parts = recv_command(conn)
            if parts is None:
                return
            command = parts[0].upper()
            if command == b"PSYNC":
                self.psync_count += 1
                if self.psync_count == 1:
                    partial = self.snapshot[: max(1, len(self.snapshot) // 2)]
                    conn.sendall(
                        self._fullresync(crc64(self.snapshot))
                        + b"$"
                        + str(len(self.snapshot)).encode()
                        + b"\r\n"
                        + partial
                    )
                    return
                if self.psync_count == 2:
                    if not self.allow_corrupt.wait(timeout=5.0):
                        return
                    conn.sendall(self._fullresync(crc64(self.snapshot)))
                    self._send_bulk(conn, self.corrupt_snapshot)
                    return
                if self.psync_count == 3:
                    if not self.allow_valid.wait(timeout=5.0):
                        return
                    conn.sendall(self._fullresync(crc64(self.snapshot)))
                    self._send_bulk(conn, self.snapshot)
                    return
                offset = int(parts[2]) if len(parts) > 2 else FULL_SYNC_OFFSET
                conn.sendall(b"+CONTINUE " + str(offset).encode() + b"\r\n$0\r\n\r\n")
                return
            if command == b"PING":
                conn.sendall(b"+PONG\r\n")
                return
            if command == b"REPLCONF":
                conn.sendall(b"+OK\r\n")
                continue
            return

    def _serve(self) -> None:
        while not self.stop_event.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                try:
                    self._handle(conn)
                except (OSError, RuntimeError, ValueError):
                    pass


def parse_info_field(reply: bytes, field: bytes) -> bytes:
    marker = field + b":"
    for line in reply.split(b"\r\n"):
        if line.startswith(marker):
            return line[len(marker) :]
    raise AssertionError(f"missing INFO field {field!r}: {reply!r}")


def wait_for_info(port: int, expected: dict[bytes, bytes], deadline: float) -> bytes:
    last = b""
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with connect_with_retry(port, time.monotonic() + 2.0) as sock:
                sock.settimeout(2.0)
                last = send_command(sock, b"INFO", b"replication")
        except (OSError, RuntimeError) as exc:
            last_error = str(exc)
            time.sleep(0.05)
            continue
        if all(parse_info_field(last, field) == value for field, value in expected.items()):
            return last
        time.sleep(0.05)
    raise RuntimeError(
        f"INFO fields did not converge: expected={expected!r}, "
        f"last_error={last_error!r}, last={last!r}"
    )


def wait_for_value(port: int, key: bytes, expected: bytes, deadline: float) -> None:
    last = b""
    while time.monotonic() < deadline:
        with connect_with_retry(port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            last = send_command(sock, b"GET", key)
        if last == expected:
            return
        time.sleep(0.05)
    raise RuntimeError(f"replica key {key!r} did not converge: expected={expected!r}, last={last!r}")


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    replica_port = find_free_port()
    replica_aof = ROOT / "build" / f"replica-full-sync-recovery-{replica_port}.aof"
    replica_aof.unlink(missing_ok=True)

    snapshot = make_snapshot(b"fresh-key", b"fresh-value")
    corrupt_snapshot = bytearray(snapshot)
    corrupt_snapshot[-2] ^= 0x01
    fake_master = FakeFullSyncMaster(snapshot, bytes(corrupt_snapshot))
    fake_master.start()

    replica = subprocess.Popen(
        [str(BIN), str(replica_port), "8", str(replica_aof)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"SET", b"local-before-sync", b"retained") != b"+OK\r\n":
                raise AssertionError("failed to seed replica-local value")

        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"REPLICAOF", b"127.0.0.1", str(fake_master.port).encode()) != b"+OK\r\n":
                raise AssertionError("replica REPLICAOF failed")

        wait_for_info(
            replica_port,
            {
                b"replication_state": b"configured",
                b"master_sync_attempts": b"1",
                b"master_sync_failures": b"1",
                b"master_sync_last_error": b"snapshot_read",
                b"master_sync_total_bytes": str(len(snapshot)).encode(),
            },
            time.monotonic() + 5.0,
        )
        first_failure = wait_for_info(
            replica_port,
            {b"master_sync_failures": b"1"},
            time.monotonic() + 2.0,
        )
        read_bytes = int(parse_info_field(first_failure, b"master_sync_read_bytes"))
        if not 0 < read_bytes < len(snapshot):
            raise AssertionError(f"expected partial transfer progress, got {read_bytes}/{len(snapshot)}")
        with connect_with_retry(replica_port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"GET", b"local-before-sync") != b"$8\r\nretained\r\n":
                raise AssertionError("interrupted sync replaced replica-local state")

        fake_master.allow_corrupt.set()
        wait_for_info(
            replica_port,
            {
                b"replication_state": b"configured",
                b"master_sync_attempts": b"2",
                b"master_sync_failures": b"2",
                b"master_sync_retry_count": b"1",
                b"master_sync_last_error": b"snapshot_checksum",
                b"master_sync_read_bytes": str(len(snapshot)).encode(),
            },
            time.monotonic() + 5.0,
        )

        fake_master.allow_valid.set()
        try:
            wait_for_info(
                replica_port,
                {
                    b"replication_state": b"connected",
                    b"master_sync_attempts": b"3",
                    b"master_sync_failures": b"2",
                    b"master_sync_retry_count": b"2",
                    b"master_sync_last_error": b"snapshot_checksum",
                },
                time.monotonic() + 5.0,
            )
        except RuntimeError as exc:
            raise RuntimeError(f"{exc}; fake_master.psync_count={fake_master.psync_count}") from exc
        wait_for_value(replica_port, b"fresh-key", b"$11\r\nfresh-value\r\n", time.monotonic() + 5.0)
        wait_for_value(replica_port, b"local-before-sync", b"$-1\r\n", time.monotonic() + 5.0)
    finally:
        fake_master.close()
        stop_process(replica)
        replica_aof.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/replication_full_sync_recovery: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/replication_full_sync_recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
