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


def wait_for_full_sync(replica_port: int, deadline: float) -> None:
    while time.monotonic() < deadline:
        with connect_with_retry(replica_port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            info_replication = send_command(sock, b"INFO", b"replication")
            if b"replication_state:connected" in info_replication:
                get_key = send_command(sock, b"GET", b"key")
                get_hash = send_command(sock, b"HGET", b"hash", b"field")
                if get_key == b"$5\r\nvalue\r\n" and get_hash == b"$5\r\nvalue\r\n":
                    return
        time.sleep(0.05)
    raise RuntimeError("replica full sync did not complete in time")


def wait_for_incremental_sync(replica_port: int, deadline: float) -> None:
    while time.monotonic() < deadline:
        with connect_with_retry(replica_port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            get_key = send_command(sock, b"GET", b"key")
            get_hash = send_command(sock, b"HGET", b"hash", b"field")
            get_lua = send_command(sock, b"GET", b"lua-key")
            get_copy = send_command(sock, b"GET", b"keycopy")
            get_list = send_command(sock, b"LRANGE", b"list", b"0", b"-1")
            get_set = send_command(sock, b"SISMEMBER", b"set", b"member")
            get_zset = send_command(sock, b"ZSCORE", b"zset", b"member")
            get_stream = send_command(sock, b"XLEN", b"stream")
            if (
                get_key == b"$5\r\nnewer\r\n"
                and get_hash == b"$4\r\nnext\r\n"
                and get_lua == b"$5\r\nvalue\r\n"
                and get_copy == b"$5\r\nnewer\r\n"
                and get_list == b"*2\r\n$1\r\na\r\n$1\r\nb\r\n"
                and get_set == b":1\r\n"
                and get_zset == b"$1\r\n1\r\n"
                and get_stream == b":1\r\n"
            ):
                return
        time.sleep(0.05)
    raise RuntimeError("replica incremental sync did not converge in time")


def parse_replica_role_offset(reply: bytes) -> int:
    if not reply.startswith(b"*5\r\n$5\r\nslave\r\n"):
        raise AssertionError(f"expected replica ROLE array, got {reply!r}")
    last_line = reply[:-2].rsplit(b"\r\n", 1)[-1]
    if not last_line.startswith(b":"):
        raise AssertionError(f"missing replica ROLE offset: {reply!r}")
    return int(last_line[1:])


def parse_bulk_array(reply: bytes) -> list[bytes]:
    if not reply.startswith(b"*"):
        raise AssertionError(f"expected RESP array, got {reply!r}")
    line_end = reply.index(b"\r\n")
    count = int(reply[1:line_end])
    pos = line_end + 2
    values: list[bytes] = []
    for _ in range(count):
        if reply[pos : pos + 1] != b"$":
            raise AssertionError(f"expected bulk string in array, got {reply[pos:pos + 1]!r}")
        length_end = reply.index(b"\r\n", pos)
        length = int(reply[pos + 1 : length_end])
        value_start = length_end + 2
        value_end = value_start + length
        values.append(reply[value_start:value_end])
        pos = value_end + 2
    if pos != len(reply):
        raise AssertionError(f"unexpected trailing array data: {reply[pos:]!r}")
    return values


def assert_replica_aof_synced(replica_port: int) -> None:
    with connect_with_retry(replica_port, time.monotonic() + 2.0) as sock:
        sock.settimeout(2.0)
        master_offset = parse_replica_role_offset(send_command(sock, b"ROLE"))
        getack = parse_bulk_array(send_command(sock, b"REPLCONF", b"GETACK", b"*"))
    if len(getack) != 5 or getack[0] != b"REPLCONF" or getack[1] != b"ACK" or getack[3] != b"FACK":
        raise AssertionError(f"unexpected REPLCONF GETACK response: {getack!r}")
    ack_offset = int(getack[2])
    fack_offset = int(getack[4])
    if ack_offset != master_offset:
        raise AssertionError(f"expected replica ACK offset {master_offset}, got {ack_offset}")
    if fack_offset != master_offset:
        raise AssertionError(f"expected replica FACK offset {master_offset}, got {fack_offset}")


def assert_restarted_replica_state(replica_port: int) -> None:
    with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
        sock.settimeout(2.0)
        expected = [
            ((b"GET", b"key"), b"$5\r\nnewer\r\n"),
            ((b"HGET", b"hash", b"field"), b"$4\r\nnext\r\n"),
            ((b"GET", b"lua-key"), b"$5\r\nvalue\r\n"),
            ((b"GET", b"keycopy"), b"$5\r\nnewer\r\n"),
            ((b"LRANGE", b"list", b"0", b"-1"), b"*2\r\n$1\r\na\r\n$1\r\nb\r\n"),
            ((b"SISMEMBER", b"set", b"member"), b":1\r\n"),
            ((b"ZSCORE", b"zset", b"member"), b"$1\r\n1\r\n"),
            ((b"XLEN", b"stream"), b":1\r\n"),
            ((b"GET", b"stale"), b"$-1\r\n"),
        ]
        for command, expected_reply in expected:
            reply = send_command(sock, *command)
            if reply != expected_reply:
                raise AssertionError(f"unexpected restart reply for {command!r}: {reply!r}")


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    master_port = find_free_port()
    replica_port = find_free_port()
    master_aof = ROOT / "build" / f"master-incr-{master_port}.aof"
    replica_aof = ROOT / "build" / f"replica-incr-{replica_port}.aof"
    master_aof.unlink(missing_ok=True)
    replica_aof.unlink(missing_ok=True)
    replica_aof.write_bytes(b"*3\r\n$3\r\nSET\r\n$5\r\nstale\r\n$5\r\nvalue\r\n")

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
    restarted_replica: subprocess.Popen[str] | None = None
    try:
        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"SET", b"key", b"value") != b"+OK\r\n":
                raise AssertionError("master SET failed")
            if send_command(sock, b"HSET", b"hash", b"field", b"value") != b":1\r\n":
                raise AssertionError("master HSET failed")

        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"REPLICAOF", b"127.0.0.1", str(master_port).encode()) != b"+OK\r\n":
                raise AssertionError("replica REPLICAOF failed")

        wait_for_full_sync(replica_port, time.monotonic() + 5.0)

        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            if send_command(sock, b"SET", b"key", b"newer") != b"+OK\r\n":
                raise AssertionError("master second SET failed")
            if send_command(sock, b"COPY", b"key", b"keycopy") != b":1\r\n":
                raise AssertionError("master COPY failed")
            if send_command(sock, b"HSET", b"hash", b"field", b"next") != b":0\r\n":
                raise AssertionError("master second HSET failed")
            if send_command(sock, b"EVAL", b"return redis.call('SET', KEYS[1], ARGV[1])", b"1", b"lua-key", b"value") != b"+OK\r\n":
                raise AssertionError("master EVAL SET failed")
            if send_command(sock, b"RPUSH", b"list", b"a", b"b") != b":2\r\n":
                raise AssertionError("master RPUSH failed")
            if send_command(sock, b"SADD", b"set", b"member") != b":1\r\n":
                raise AssertionError("master SADD failed")
            if send_command(sock, b"ZADD", b"zset", b"1", b"member") != b":1\r\n":
                raise AssertionError("master ZADD failed")
            if not send_command(sock, b"XADD", b"stream", b"*", b"field", b"value").startswith(b"$"):
                raise AssertionError("master XADD failed")

        wait_for_incremental_sync(replica_port, time.monotonic() + 5.0)
        assert_replica_aof_synced(replica_port)

        stop_process(master)
        stop_process(replica)
        restarted_port = find_free_port()
        restarted_replica = subprocess.Popen(
            [str(BIN), str(restarted_port), "8", str(replica_aof)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert_restarted_replica_state(restarted_port)
    finally:
        stop_process(master)
        stop_process(replica)
        if restarted_replica is not None:
            stop_process(restarted_replica)
        master_aof.unlink(missing_ok=True)
        replica_aof.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/replication_incremental_sync: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/replication_incremental_sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
