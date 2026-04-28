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


class RedisPySubsetClient:
    def __init__(self, host: str, port: int) -> None:
        self._sock = socket.create_connection((host, port), timeout=1.0)
        self._sock.settimeout(2.0)

    def close(self) -> None:
        self._sock.close()

    def _read_line(self) -> bytes:
        chunks: list[bytes] = []
        while True:
            chunk = self._sock.recv(1)
            if not chunk:
                raise RuntimeError("connection closed while reading line")
            chunks.append(chunk)
            if len(chunks) >= 2 and chunks[-2] == b"\r" and chunks[-1] == b"\n":
                return b"".join(chunks[:-2])

    def _read_exact(self, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self._sock.recv(remaining)
            if not chunk:
                raise RuntimeError("connection closed while reading payload")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_resp(self):
        prefix = self._read_exact(1)
        if prefix == b"+":
            return self._read_line().decode()
        if prefix == b"-":
            raise RespError(self._read_line().decode())
        if prefix == b":":
            return int(self._read_line())
        if prefix == b"$":
            length = int(self._read_line())
            if length < 0:
                return None
            data = self._read_exact(length)
            crlf = self._read_exact(2)
            if crlf != b"\r\n":
                raise RuntimeError(f"invalid bulk terminator: {crlf!r}")
            return data
        if prefix == b"*":
            count = int(self._read_line())
            if count < 0:
                return None
            return [self._read_resp() for _ in range(count)]
        raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")

    def _request(self, *parts: bytes):
        buf = [f"*{len(parts)}\r\n".encode()]
        for part in parts:
            buf.append(f"${len(part)}\r\n".encode())
            buf.append(part)
            buf.append(b"\r\n")
        self._sock.sendall(b"".join(buf))
        return self._read_resp()

    def ping(self) -> bool:
        return self._request(b"PING") == "PONG"

    def set(self, key: str, value: str) -> bool:
        return self._request(b"SET", key.encode(), value.encode()) == "OK"

    def get(self, key: str) -> bytes | None:
        return self._request(b"GET", key.encode())

    def delete(self, *keys: str) -> int:
        return int(self._request(b"DEL", *(key.encode() for key in keys)))

    def exists(self, *keys: str) -> int:
        return int(self._request(b"EXISTS", *(key.encode() for key in keys)))

    def expire(self, key: str, seconds: int) -> bool:
        return int(self._request(b"EXPIRE", key.encode(), str(seconds).encode())) == 1

    def ttl(self, key: str) -> int:
        return int(self._request(b"TTL", key.encode()))

    def hset(self, key: str, field: str, value: str) -> int:
        return int(self._request(b"HSET", key.encode(), field.encode(), value.encode()))

    def hget(self, key: str, field: str) -> bytes | None:
        return self._request(b"HGET", key.encode(), field.encode())

    def lpush(self, key: str, *values: str) -> int:
        return int(self._request(b"LPUSH", key.encode(), *(value.encode() for value in values)))

    def lrange(self, key: str, start: int, stop: int) -> list[bytes]:
        result = self._request(b"LRANGE", key.encode(), str(start).encode(), str(stop).encode())
        assert isinstance(result, list)
        return result

    def lpop(self, key: str) -> bytes | None:
        return self._request(b"LPOP", key.encode())

    def sadd(self, key: str, *members: str) -> int:
        return int(self._request(b"SADD", key.encode(), *(member.encode() for member in members)))

    def smembers(self, key: str) -> set[bytes]:
        result = self._request(b"SMEMBERS", key.encode())
        assert isinstance(result, list)
        return set(result)

    def srem(self, key: str, *members: str) -> int:
        return int(self._request(b"SREM", key.encode(), *(member.encode() for member in members)))

    def zadd(self, key: str, mapping: dict[str, int]) -> int:
        parts: list[bytes] = [b"ZADD", key.encode()]
        for member, score in mapping.items():
            parts.append(str(score).encode())
            parts.append(member.encode())
        return int(self._request(*parts))

    def zrange(self, key: str, start: int, stop: int) -> list[bytes]:
        result = self._request(b"ZRANGE", key.encode(), str(start).encode(), str(stop).encode())
        assert isinstance(result, list)
        return result

    def zrem(self, key: str, *members: str) -> int:
        return int(self._request(b"ZREM", key.encode(), *(member.encode() for member in members)))

    def scan(self, cursor: int = 0, count: int | None = None) -> tuple[int, list[bytes]]:
        parts: list[bytes] = [b"SCAN", str(cursor).encode()]
        if count is not None:
            parts.extend([b"COUNT", str(count).encode()])
        result = self._request(*parts)
        assert isinstance(result, list) and len(result) == 2
        next_cursor = int(result[0])
        keys = result[1]
        assert isinstance(keys, list)
        return next_cursor, keys

    def info(self, section: str = "server") -> dict[str, str]:
        raw = self._request(b"INFO", section.encode())
        assert isinstance(raw, bytes)
        result: dict[str, str] = {}
        for line in raw.decode().splitlines():
            if not line or line.startswith("#"):
                continue
            key, value = line.split(":", 1)
            result[key] = value
        return result

    def config_get(self, pattern: str) -> dict[str, str]:
        raw = self._request(b"CONFIG", b"GET", pattern.encode())
        assert isinstance(raw, list)
        result: dict[str, str] = {}
        i = 0
        while i + 1 < len(raw):
            key = raw[i].decode()
            value = raw[i + 1].decode()
            result[key] = value
            i += 2
        return result

    def save(self) -> bool:
        return self._request(b"SAVE") == "OK"

    def bgrewriteaof(self) -> bool:
        return self._request(b"BGREWRITEAOF") == "Background AOF rewrite scheduled"

    def quit(self) -> bool:
        return self._request(b"QUIT") == "OK"


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"redis-py-subset-{port}.aof"
    rdb_path = ROOT / "build" / "dump.rdb"
    aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5.0
        client: RedisPySubsetClient | None = None
        while time.monotonic() < deadline:
            try:
                client = RedisPySubsetClient("127.0.0.1", port)
                break
            except OSError:
                time.sleep(0.05)
        if client is None:
            raise RuntimeError("redis-uya did not start in time")

        try:
            assert client.ping()
            assert client.set("key", "value")
            assert client.get("key") == b"value"
            assert client.exists("key", "missing") == 1
            assert client.expire("key", 2)
            ttl = client.ttl("key")
            if ttl not in (1, 2):
                raise AssertionError(f"unexpected ttl: {ttl}")
            assert client.save()

            assert client.hset("hash", "field", "value") == 1
            assert client.hget("hash", "field") == b"value"

            assert client.lpush("list", "a", "b", "c") == 3
            assert client.lrange("list", 0, -1) == [b"c", b"b", b"a"]
            assert client.lpop("list") == b"c"

            assert client.sadd("set", "a", "b") == 2
            assert client.smembers("set") == {b"a", b"b"}
            assert client.srem("set", "a") == 1

            assert client.zadd("zset", {"b": 2, "a": 1}) == 2
            assert client.zrange("zset", 0, -1) == [b"a", b"b"]
            assert client.zrem("zset", "a") == 1

            cursor, keys = client.scan(0, count=16)
            if cursor != 0:
                raise AssertionError(f"expected final scan cursor 0, got {cursor}")
            expected_keys = {b"hash", b"key", b"list", b"set", b"zset"}
            if set(keys) != expected_keys:
                raise AssertionError(f"unexpected scan keys: {keys!r}")

            info = client.info("server")
            if info.get("redis_uya_version") != "0.1.0-dev":
                raise AssertionError(f"unexpected info server: {info!r}")

            keyspace = client.info("keyspace")
            if "db0" not in keyspace:
                raise AssertionError(f"missing db0 keyspace: {keyspace!r}")

            config = client.config_get("port")
            if config.get("port") != str(port):
                raise AssertionError(f"unexpected config get port: {config!r}")

            assert client.bgrewriteaof()
            assert client.quit()
        finally:
            if client is not None:
                client.close()

        stop_process(proc)
        if proc.returncode not in (0, -15):
            stdout, stderr = proc.communicate()
            raise RuntimeError(
                f"redis-uya exited with {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/redis_py_subset: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/redis_py_subset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
