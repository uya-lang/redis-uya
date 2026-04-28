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


def wait_for_replica_state(port: int, deadline: float) -> None:
    while time.monotonic() < deadline:
        with connect_with_retry(port, time.monotonic() + 2.0) as sock:
            sock.settimeout(2.0)
            info = send_command(sock, b"INFO", b"replication")
            if b"replication_state:connected" in info:
                return
        time.sleep(0.05)
    raise RuntimeError("replica did not reach connected state")


def replica_matches(port: int) -> bool:
    with connect_with_retry(port, time.monotonic() + 2.0) as sock:
        sock.settimeout(2.0)
        if send_command(sock, b"GET", b"key") != b"$5\r\nnewer\r\n":
            return False
        if send_command(sock, b"HGET", b"hash", b"field") != b"$4\r\nnext\r\n":
            return False
        if send_command(sock, b"LRANGE", b"list", b"0", b"-1") != b"*2\r\n$1\r\nb\r\n$1\r\na\r\n":
            return False
        smembers = send_command(sock, b"SMEMBERS", b"set")
        if smembers not in (b"*1\r\n$1\r\nb\r\n",):
            return False
        if send_command(sock, b"ZRANGE", b"zset", b"0", b"-1") != b"*2\r\n$1\r\na\r\n$1\r\nc\r\n":
            return False
    return True


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    master_port = find_free_port()
    replica_port = find_free_port()
    master_aof = ROOT / "build" / f"master-consistency-{master_port}.aof"
    replica_aof = ROOT / "build" / f"replica-consistency-{replica_port}.aof"
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
            assert send_command(sock, b"SET", b"key", b"value") == b"+OK\r\n"
            assert send_command(sock, b"HSET", b"hash", b"field", b"value") == b":1\r\n"
            assert send_command(sock, b"LPUSH", b"list", b"a", b"b") == b":2\r\n"
            assert send_command(sock, b"SADD", b"set", b"a", b"b") == b":2\r\n"
            assert send_command(sock, b"ZADD", b"zset", b"2", b"b", b"1", b"a") == b":2\r\n"

        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            assert send_command(sock, b"REPLICAOF", b"127.0.0.1", str(master_port).encode()) == b"+OK\r\n"

        wait_for_replica_state(replica_port, time.monotonic() + 5.0)

        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            assert send_command(sock, b"SET", b"key", b"newer") == b"+OK\r\n"
            assert send_command(sock, b"HSET", b"hash", b"field", b"next") == b":0\r\n"
            assert send_command(sock, b"LPUSH", b"list", b"c") == b":3\r\n"
            assert send_command(sock, b"LPOP", b"list") == b"$1\r\nc\r\n"
            assert send_command(sock, b"SREM", b"set", b"a") == b":1\r\n"
            assert send_command(sock, b"ZREM", b"zset", b"b") == b":1\r\n"
            assert send_command(sock, b"ZADD", b"zset", b"3", b"c") == b":1\r\n"

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if replica_matches(replica_port):
                return
            time.sleep(0.05)
        raise RuntimeError("replica did not converge to master state")
    finally:
        stop_process(master)
        stop_process(replica)
        master_aof.unlink(missing_ok=True)
        replica_aof.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/replication_consistency: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/replication_consistency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
