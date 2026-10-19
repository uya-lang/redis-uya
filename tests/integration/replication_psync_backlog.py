#!/usr/bin/env python3
import select
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


def parse_fullresync(resp: bytes) -> tuple[str, int, str | None]:
    if not resp.startswith(b"+FULLRESYNC "):
        raise AssertionError(f"expected FULLRESYNC reply, got {resp!r}")
    body = resp[1:-2].decode()
    fields = body.split(" ")
    if len(fields) not in (3, 4):
        raise AssertionError(f"invalid FULLRESYNC fields: {body!r}")
    _, replid, offset_text = fields[:3]
    checksum = fields[3] if len(fields) == 4 else None
    if checksum is not None and (len(checksum) != 16 or any(ch not in "0123456789abcdefABCDEF" for ch in checksum)):
        raise AssertionError(f"invalid FULLRESYNC CRC64: {checksum!r}")
    return replid, int(offset_text), checksum


def encode_request(*parts: bytes) -> bytes:
    buf = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        buf.append(f"${len(part)}\r\n".encode())
        buf.append(part)
        buf.append(b"\r\n")
    return b"".join(buf)


GETACK_REQUEST = encode_request(b"REPLCONF", b"GETACK", b"*")


def recv_getack(sock: socket.socket) -> None:
    prefix = recv_exact(sock, 1)
    request = prefix + recv_exact(sock, len(GETACK_REQUEST) - 1)
    if request != GETACK_REQUEST:
        raise AssertionError(f"expected GETACK request, got {request!r}")


def send_raw_request(sock: socket.socket, *parts: bytes) -> None:
    sock.sendall(encode_request(*parts))


def recv_pong_handling_getack(sock: socket.socket, ack_offset: int) -> None:
    while True:
        prefix = recv_exact(sock, 1)
        if prefix == b"+":
            if recv_line(sock) != b"PONG":
                raise AssertionError("expected +PONG after PING")
            return
        if prefix == b"*":
            request = prefix + recv_exact(sock, len(GETACK_REQUEST) - 1)
            if request != GETACK_REQUEST:
                raise AssertionError(f"unexpected replication request before PONG: {request!r}")
            send_raw_request(sock, b"REPLCONF", b"ACK", str(ack_offset).encode())
            continue
        raise AssertionError(f"unexpected prefix before PONG: {prefix!r}")


def recv_quit_ok(sock: socket.socket, ack_offset: int) -> None:
    while True:
        prefix = recv_exact(sock, 1)
        if prefix == b"+":
            if recv_line(sock) != b"OK":
                raise AssertionError("expected +OK on QUIT")
            return
        if prefix == b"*":
            request = prefix + recv_exact(sock, len(GETACK_REQUEST) - 1)
            if request != GETACK_REQUEST:
                raise AssertionError(f"unexpected replication request before QUIT reply: {request!r}")
            send_raw_request(sock, b"REPLCONF", b"ACK", str(ack_offset).encode())
            continue
        raise AssertionError(f"unexpected prefix before QUIT reply: {prefix!r}")


def recv_psync_fullresync(sock: socket.socket) -> tuple[str, int, bytes]:
    line = recv_exact(sock, 1)
    if line != b"+":
        raise AssertionError(f"expected simple string prefix, got {line!r}")
    header = recv_line(sock) + b"\r\n"
    replid, offset, _checksum = parse_fullresync(line + header)

    bulk_prefix = recv_exact(sock, 1)
    if bulk_prefix != b"$":
        raise AssertionError(f"expected bulk prefix after FULLRESYNC, got {bulk_prefix!r}")
    snapshot_len = int(recv_line(sock))
    payload = recv_exact(sock, snapshot_len)
    terminator = recv_exact(sock, 2)
    if terminator != b"\r\n":
        raise AssertionError(f"invalid snapshot terminator: {terminator!r}")
    return replid, offset, payload


def recv_sync_snapshot(sock: socket.socket) -> bytes:
    bulk_prefix = recv_exact(sock, 1)
    if bulk_prefix != b"$":
        raise AssertionError(f"expected SYNC bulk prefix, got {bulk_prefix!r}")
    snapshot_len = int(recv_line(sock))
    payload = recv_exact(sock, snapshot_len)
    terminator = recv_exact(sock, 2)
    if terminator != b"\r\n":
        raise AssertionError(f"invalid SYNC snapshot terminator: {terminator!r}")
    return payload


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

            send_raw_request(sock, b"SYNC")
            sync_snapshot = recv_sync_snapshot(sock)
            if not sync_snapshot.startswith(b"RUYARDB1"):
                raise AssertionError(f"expected SYNC project RDB snapshot, got {sync_snapshot[:8]!r}")
            if b"key" not in sync_snapshot or b"value" not in sync_snapshot:
                raise AssertionError(f"SYNC snapshot missing current key/value: {sync_snapshot!r}")

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

            with connect_with_retry(port, time.monotonic() + 5.0) as ordinary:
                ordinary.settimeout(2.5)
                sock.settimeout(2.5)
                readable, _, _ = select.select([sock, ordinary], [], [], 2.5)
                if sock not in readable:
                    raise AssertionError("expected periodic GETACK on the PSYNC replica connection")
                if ordinary in readable:
                    raise AssertionError("ordinary client unexpectedly received replication traffic")
                recv_getack(sock)
                send_raw_request(sock, b"REPLCONF", b"ACK", str(offset + len(second_set)).encode())

            with connect_with_retry(port, time.monotonic() + 5.0) as writer:
                writer.settimeout(10.0)
                wait_set = encode_request(b"SET", b"wait-key", b"wait-value")
                if send_command(writer, b"SET", b"wait-key", b"wait-value") != b"+OK\r\n":
                    raise AssertionError("expected WAIT setup SET to succeed")
                wait_target_offset = offset + len(second_set) + len(wait_set)
                send_raw_request(writer, b"WAIT", b"1", b"2000")
                recv_getack(sock)
                send_raw_request(sock, b"REPLCONF", b"ACK", str(wait_target_offset).encode())
                if recv_line(writer) != b":1":
                    raise AssertionError("expected WAIT to wake with one acknowledged replica")

                # FACK 与 PING 同连接顺序发送，+PONG 作为处理屏障，避免
                # WAITAOF 的按需 GETACK 与周期 GETACK 在测试端串包。
                send_raw_request(
                    sock,
                    b"REPLCONF",
                    b"ACK",
                    str(wait_target_offset).encode(),
                    b"FACK",
                    str(wait_target_offset).encode(),
                )
                send_raw_request(sock, b"PING")
                recv_pong_handling_getack(sock, wait_target_offset)
                send_raw_request(writer, b"WAITAOF", b"1", b"1", b"5000")
                waitaof_reply = recv_exact(writer, len(b"*2\r\n:1\r\n:1\r\n"))
                if waitaof_reply != b"*2\r\n:1\r\n:1\r\n":
                    raise AssertionError(
                        f"expected WAITAOF to report local and replica fsync acknowledgements, got {waitaof_reply!r}"
                    )

                timeout_set = encode_request(b"SET", b"wait-key", b"newer")
                if send_command(writer, b"SET", b"wait-key", b"newer") != b"+OK\r\n":
                    raise AssertionError("expected WAIT timeout setup SET to succeed")
                send_raw_request(writer, b"WAIT", b"1", b"50")
                recv_getack(sock)
                if recv_line(writer) != b":0":
                    raise AssertionError("expected WAIT timeout to return zero acknowledged replicas")
                if wait_target_offset + len(timeout_set) <= wait_target_offset:
                    raise AssertionError("expected the second write to advance the replication target")

            send_raw_request(sock, b"QUIT")
            recv_quit_ok(sock, wait_target_offset)
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
