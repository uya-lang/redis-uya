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

    def auth(self, password: str, username: str | None = None) -> bool:
        if username is None:
            return self._request(b"AUTH", password.encode()) == "OK"
        return self._request(b"AUTH", username.encode(), password.encode()) == "OK"

    def set(self, key: str, value: str) -> bool:
        return self._request(b"SET", key.encode(), value.encode()) == "OK"

    def echo(self, value: str) -> bytes:
        result = self._request(b"ECHO", value.encode())
        assert isinstance(result, bytes)
        return result

    def get(self, key: str) -> bytes | None:
        return self._request(b"GET", key.encode())

    def incr(self, key: str) -> int:
        return int(self._request(b"INCR", key.encode()))

    def decr(self, key: str) -> int:
        return int(self._request(b"DECR", key.encode()))

    def incrby(self, key: str, amount: int) -> int:
        return int(self._request(b"INCRBY", key.encode(), str(amount).encode()))

    def decrby(self, key: str, amount: int) -> int:
        return int(self._request(b"DECRBY", key.encode(), str(amount).encode()))

    def getset(self, key: str, value: str) -> bytes | None:
        return self._request(b"GETSET", key.encode(), value.encode())

    def setnx(self, key: str, value: str) -> int:
        return int(self._request(b"SETNX", key.encode(), value.encode()))

    def setex(self, key: str, seconds: int, value: str) -> bool:
        return self._request(b"SETEX", key.encode(), str(seconds).encode(), value.encode()) == "OK"

    def psetex(self, key: str, milliseconds: int, value: str) -> bool:
        return self._request(b"PSETEX", key.encode(), str(milliseconds).encode(), value.encode()) == "OK"

    def mget(self, *keys: str) -> list[bytes | None]:
        result = self._request(b"MGET", *(key.encode() for key in keys))
        assert isinstance(result, list)
        return result

    def mset(self, mapping: dict[str, str]) -> bool:
        parts: list[bytes] = [b"MSET"]
        for key, value in mapping.items():
            parts.append(key.encode())
            parts.append(value.encode())
        return self._request(*parts) == "OK"

    def msetnx(self, mapping: dict[str, str]) -> int:
        parts: list[bytes] = [b"MSETNX"]
        for key, value in mapping.items():
            parts.append(key.encode())
            parts.append(value.encode())
        return int(self._request(*parts))

    def getrange(self, key: str, start: int, stop: int) -> bytes:
        result = self._request(b"GETRANGE", key.encode(), str(start).encode(), str(stop).encode())
        assert isinstance(result, bytes)
        return result

    def setrange(self, key: str, offset: int, value: str) -> int:
        return int(self._request(b"SETRANGE", key.encode(), str(offset).encode(), value.encode()))

    def incrbyfloat(self, key: str, amount: str) -> bytes:
        result = self._request(b"INCRBYFLOAT", key.encode(), amount.encode())
        assert isinstance(result, bytes)
        return result

    def append(self, key: str, value: str) -> int:
        return int(self._request(b"APPEND", key.encode(), value.encode()))

    def rename(self, source: str, target: str) -> bool:
        return self._request(b"RENAME", source.encode(), target.encode()) == "OK"

    def renamenx(self, source: str, target: str) -> int:
        return int(self._request(b"RENAMENX", source.encode(), target.encode()))

    def strlen(self, key: str) -> int:
        return int(self._request(b"STRLEN", key.encode()))

    def getdel(self, key: str) -> bytes | None:
        return self._request(b"GETDEL", key.encode())

    def getex(self, key: str, *parts: str) -> bytes | None:
        encoded: list[bytes] = [b"GETEX", key.encode()]
        for part in parts:
            encoded.append(part.encode())
        return self._request(*encoded)

    def key_type(self, key: str) -> str:
        result = self._request(b"TYPE", key.encode())
        assert isinstance(result, str)
        return result

    def delete(self, *keys: str) -> int:
        return int(self._request(b"DEL", *(key.encode() for key in keys)))

    def dbsize(self) -> int:
        return int(self._request(b"DBSIZE"))

    def select(self, db: int) -> bool:
        return self._request(b"SELECT", str(db).encode()) == "OK"

    def object_encoding(self, key: str) -> bytes | None:
        return self._request(b"OBJECT", b"ENCODING", key.encode())

    def object_refcount(self, key: str) -> int | None:
        result = self._request(b"OBJECT", b"REFCOUNT", key.encode())
        if result is None:
            return None
        return int(result)

    def object_idletime(self, key: str) -> int | None:
        result = self._request(b"OBJECT", b"IDLETIME", key.encode())
        if result is None:
            return None
        return int(result)

    def object_freq(self, key: str) -> int | None:
        result = self._request(b"OBJECT", b"FREQ", key.encode())
        if result is None:
            return None
        return int(result)

    def move(self, key: str, db: int) -> int:
        return int(self._request(b"MOVE", key.encode(), str(db).encode()))

    def wait(self, replicas: int, timeout_ms: int) -> int:
        return int(self._request(b"WAIT", str(replicas).encode(), str(timeout_ms).encode()))

    def sort(self, key: str, *parts: str) :
        encoded: list[bytes] = [b"SORT", key.encode()]
        for part in parts:
            encoded.append(part.encode())
        return self._request(*encoded)

    def exists(self, *keys: str) -> int:
        return int(self._request(b"EXISTS", *(key.encode() for key in keys)))

    def expire(self, key: str, seconds: int) -> bool:
        return int(self._request(b"EXPIRE", key.encode(), str(seconds).encode())) == 1

    def ttl(self, key: str) -> int:
        return int(self._request(b"TTL", key.encode()))

    def pexpire(self, key: str, milliseconds: int) -> bool:
        return int(self._request(b"PEXPIRE", key.encode(), str(milliseconds).encode())) == 1

    def pttl(self, key: str) -> int:
        return int(self._request(b"PTTL", key.encode()))

    def persist(self, key: str) -> bool:
        return int(self._request(b"PERSIST", key.encode())) == 1

    def pexpireat(self, key: str, unix_ms: int) -> bool:
        return int(self._request(b"PEXPIREAT", key.encode(), str(unix_ms).encode())) == 1

    def expireat(self, key: str, unix_s: int) -> bool:
        return int(self._request(b"EXPIREAT", key.encode(), str(unix_s).encode())) == 1

    def expiretime(self, key: str) -> int:
        return int(self._request(b"EXPIRETIME", key.encode()))

    def pexpiretime(self, key: str) -> int:
        return int(self._request(b"PEXPIRETIME", key.encode()))

    def hset(self, key: str, field: str, value: str) -> int:
        return int(self._request(b"HSET", key.encode(), field.encode(), value.encode()))

    def hget(self, key: str, field: str) -> bytes | None:
        return self._request(b"HGET", key.encode(), field.encode())

    def hincrby(self, key: str, field: str, amount: int) -> int:
        return int(self._request(b"HINCRBY", key.encode(), field.encode(), str(amount).encode()))

    def hincrbyfloat(self, key: str, field: str, amount: str) -> bytes:
        result = self._request(b"HINCRBYFLOAT", key.encode(), field.encode(), amount.encode())
        assert isinstance(result, bytes)
        return result

    def hkeys(self, key: str) -> list[bytes]:
        result = self._request(b"HKEYS", key.encode())
        assert isinstance(result, list)
        return result

    def hvals(self, key: str) -> list[bytes]:
        result = self._request(b"HVALS", key.encode())
        assert isinstance(result, list)
        return result

    def hgetall(self, key: str) -> list[bytes]:
        result = self._request(b"HGETALL", key.encode())
        assert isinstance(result, list)
        return result

    def hdel(self, key: str, *fields: str) -> int:
        return int(self._request(b"HDEL", key.encode(), *(field.encode() for field in fields)))

    def hexists(self, key: str, field: str) -> int:
        return int(self._request(b"HEXISTS", key.encode(), field.encode()))

    def hlen(self, key: str) -> int:
        return int(self._request(b"HLEN", key.encode()))

    def hmget(self, key: str, *fields: str) -> list[bytes | None]:
        result = self._request(b"HMGET", key.encode(), *(field.encode() for field in fields))
        assert isinstance(result, list)
        return result

    def hsetnx(self, key: str, field: str, value: str) -> int:
        return int(self._request(b"HSETNX", key.encode(), field.encode(), value.encode()))

    def hstrlen(self, key: str, field: str) -> int:
        return int(self._request(b"HSTRLEN", key.encode(), field.encode()))

    def hscan(self, key: str, cursor: int = 0, count: int | None = None) -> tuple[int, list[bytes]]:
        parts: list[bytes] = [b"HSCAN", key.encode(), str(cursor).encode()]
        if count is not None:
            parts.extend([b"COUNT", str(count).encode()])
        result = self._request(*parts)
        assert isinstance(result, list) and len(result) == 2
        next_cursor = int(result[0])
        items = result[1]
        assert isinstance(items, list)
        return next_cursor, items

    def lpush(self, key: str, *values: str) -> int:
        return int(self._request(b"LPUSH", key.encode(), *(value.encode() for value in values)))

    def lrange(self, key: str, start: int, stop: int) -> list[bytes]:
        result = self._request(b"LRANGE", key.encode(), str(start).encode(), str(stop).encode())
        assert isinstance(result, list)
        return result

    def lpop(self, key: str) -> bytes | None:
        return self._request(b"LPOP", key.encode())

    def rpush(self, key: str, *values: str) -> int:
        return int(self._request(b"RPUSH", key.encode(), *(value.encode() for value in values)))

    def rpop(self, key: str) -> bytes | None:
        return self._request(b"RPOP", key.encode())

    def lindex(self, key: str, index: int) -> bytes | None:
        return self._request(b"LINDEX", key.encode(), str(index).encode())

    def lset(self, key: str, index: int, value: str) -> bool:
        return self._request(b"LSET", key.encode(), str(index).encode(), value.encode()) == "OK"

    def llen(self, key: str) -> int:
        return int(self._request(b"LLEN", key.encode()))

    def linsert(self, key: str, where: str, pivot: str, value: str) -> int:
        return int(self._request(b"LINSERT", key.encode(), where.encode(), pivot.encode(), value.encode()))

    def ltrim(self, key: str, start: int, stop: int) -> bool:
        return self._request(b"LTRIM", key.encode(), str(start).encode(), str(stop).encode()) == "OK"

    def lrem(self, key: str, count: int, value: str) -> int:
        return int(self._request(b"LREM", key.encode(), str(count).encode(), value.encode()))

    def lpushx(self, key: str, *values: str) -> int:
        return int(self._request(b"LPUSHX", key.encode(), *(value.encode() for value in values)))

    def rpushx(self, key: str, *values: str) -> int:
        return int(self._request(b"RPUSHX", key.encode(), *(value.encode() for value in values)))

    def lpos(self, key: str, value: str) -> int | None:
        result = self._request(b"LPOS", key.encode(), value.encode())
        if result is None:
            return None
        return int(result)

    def sadd(self, key: str, *members: str) -> int:
        return int(self._request(b"SADD", key.encode(), *(member.encode() for member in members)))

    def smembers(self, key: str) -> set[bytes]:
        result = self._request(b"SMEMBERS", key.encode())
        assert isinstance(result, list)
        return set(result)

    def srem(self, key: str, *members: str) -> int:
        return int(self._request(b"SREM", key.encode(), *(member.encode() for member in members)))

    def spop(self, key: str) -> bytes | None:
        return self._request(b"SPOP", key.encode())

    def srandmember(self, key: str) -> bytes | None:
        return self._request(b"SRANDMEMBER", key.encode())

    def sinter(self, *keys: str) -> set[bytes]:
        result = self._request(b"SINTER", *(key.encode() for key in keys))
        assert isinstance(result, list)
        return set(result)

    def sdiff(self, *keys: str) -> set[bytes]:
        result = self._request(b"SDIFF", *(key.encode() for key in keys))
        assert isinstance(result, list)
        return set(result)

    def sunion(self, *keys: str) -> set[bytes]:
        result = self._request(b"SUNION", *(key.encode() for key in keys))
        assert isinstance(result, list)
        return set(result)

    def sinterstore(self, dest: str, *keys: str) -> int:
        return int(self._request(b"SINTERSTORE", dest.encode(), *(key.encode() for key in keys)))

    def sdiffstore(self, dest: str, *keys: str) -> int:
        return int(self._request(b"SDIFFSTORE", dest.encode(), *(key.encode() for key in keys)))

    def sunionstore(self, dest: str, *keys: str) -> int:
        return int(self._request(b"SUNIONSTORE", dest.encode(), *(key.encode() for key in keys)))

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

    def zincrby(self, key: str, amount: int, member: str) -> bytes:
        result = self._request(b"ZINCRBY", key.encode(), str(amount).encode(), member.encode())
        assert isinstance(result, bytes)
        return result

    def zcard(self, key: str) -> int:
        return int(self._request(b"ZCARD", key.encode()))

    def zcount(self, key: str, minimum: int, maximum: int) -> int:
        return int(self._request(b"ZCOUNT", key.encode(), str(minimum).encode(), str(maximum).encode()))

    def zrangebyscore(self, key: str, minimum: int, maximum: int) -> list[bytes]:
        result = self._request(b"ZRANGEBYSCORE", key.encode(), str(minimum).encode(), str(maximum).encode())
        assert isinstance(result, list)
        return result

    def zrevrangebyscore(self, key: str, maximum: int, minimum: int) -> list[bytes]:
        result = self._request(b"ZREVRANGEBYSCORE", key.encode(), str(maximum).encode(), str(minimum).encode())
        assert isinstance(result, list)
        return result

    def zremrangebyrank(self, key: str, start: int, stop: int) -> int:
        return int(self._request(b"ZREMRANGEBYRANK", key.encode(), str(start).encode(), str(stop).encode()))

    def zremrangebyscore(self, key: str, minimum: int, maximum: int) -> int:
        return int(self._request(b"ZREMRANGEBYSCORE", key.encode(), str(minimum).encode(), str(maximum).encode()))

    def zscan(self, key: str, cursor: int = 0, count: int | None = None) -> tuple[int, list[bytes]]:
        parts: list[bytes] = [b"ZSCAN", key.encode(), str(cursor).encode()]
        if count is not None:
            parts.extend([b"COUNT", str(count).encode()])
        result = self._request(*parts)
        assert isinstance(result, list) and len(result) == 2
        next_cursor = int(result[0])
        items = result[1]
        assert isinstance(items, list)
        return next_cursor, items

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

    def lastsave(self) -> int:
        return int(self._request(b"LASTSAVE"))

    def flushdb(self) -> bool:
        return self._request(b"FLUSHDB") == "OK"

    def flushall(self) -> bool:
        return self._request(b"FLUSHALL") == "OK"

    def dump(self, key: str) -> bytes | None:
        return self._request(b"DUMP", key.encode())

    def restore(self, key: str, ttl_ms: int, payload: bytes) -> bool:
        return self._request(b"RESTORE", key.encode(), str(ttl_ms).encode(), payload) == "OK"

    def save(self) -> bool:
        return self._request(b"SAVE") == "OK"

    def bgrewriteaof(self) -> bool:
        return self._request(b"BGREWRITEAOF") == "Background AOF rewrite scheduled"

    def quit(self) -> bool:
        return self._request(b"QUIT") == "OK"

    def shutdown_nosave(self) -> None:
        self._sock.sendall(b"*2\r\n$8\r\nSHUTDOWN\r\n$6\r\nNOSAVE\r\n")
        try:
            chunk = self._sock.recv(1)
        except OSError:
            return
        if chunk not in (b"",):
            raise RuntimeError(f"expected connection close on SHUTDOWN, got {chunk!r}")


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"redis-py-subset-{port}.aof"
    rdb_path = ROOT / "build" / "dump.rdb"
    auth_port = find_free_port()
    auth_aof_path = ROOT / "build" / f"redis-py-auth-{auth_port}.aof"
    aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)
    auth_aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    auth_proc: subprocess.Popen[str] | None = None
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
            assert client.incr("counter") == 1
            assert client.incrby("counter", 4) == 5
            assert client.decr("counter") == 4
            assert client.decrby("counter", 2) == 2
            assert client.incrbyfloat("fcounter", "1.5") == b"1.5"
            assert client.incrbyfloat("fcounter", "2") == b"3.5"
            assert client.setnx("nx-key", "first") == 1
            assert client.setnx("nx-key", "second") == 0
            assert client.getset("gs-key", "first") is None
            assert client.getset("gs-key", "second") == b"first"
            assert client.setex("sx-key", 2, "value")
            assert client.mset({"mk1": "v1", "mk2": "v2"})
            assert client.mget("mk1", "missing", "mk2") == [b"v1", None, b"v2"]
            assert client.msetnx({"mn1": "a", "mn2": "b"}) == 1
            assert client.msetnx({"mn1": "x", "mn3": "y"}) == 0
            assert client.strlen("key") == 5
            assert client.append("key", "++") == 7
            assert client.getrange("key", 1, 3) == b"alu"
            assert client.setrange("key", 5, "__") == 7
            assert client.get("key") == b"value__"
            assert client.rename("key", "key2")
            assert client.get("key2") == b"value__"
            assert client.renamenx("key2", "gs-key") == 0
            assert client.renamenx("key2", "key") == 1
            assert client.get("key") == b"value__"
            assert client.set("gd-key", "once")
            assert client.getdel("gd-key") == b"once"
            assert client.getdel("gd-key") is None
            assert client.delete("counter") == 1
            assert client.delete("fcounter", "nx-key", "gs-key", "sx-key", "mk1", "mk2", "mn1", "mn2") == 8
            assert client.echo("hi") == b"hi"
            assert client.key_type("key") == "string"
            assert client.dbsize() == 1
            assert client.select(0)
            try:
                client.select(1)
                raise AssertionError("expected SELECT 1 to fail with single db")
            except RespError as exc:
                if str(exc) != "ERR DB index is out of range":
                    raise AssertionError(f"unexpected SELECT error: {exc}") from exc
            assert client.object_encoding("key") == b"raw"
            if client.object_refcount("key") != 1:
                raise AssertionError("expected OBJECT REFCOUNT key to be 1")
            object_idle = client.object_idletime("key")
            if object_idle is None or object_idle < 0:
                raise AssertionError(f"unexpected OBJECT IDLETIME: {object_idle}")
            try:
                client.object_freq("key")
                raise AssertionError("expected OBJECT FREQ to fail without LFU policy")
            except RespError as exc:
                if "An LFU maxmemory policy is not selected" not in str(exc):
                    raise AssertionError(f"unexpected OBJECT FREQ error: {exc}") from exc
            try:
                client.move("key", 0)
                raise AssertionError("expected MOVE key 0 to fail in single-db mode")
            except RespError as exc:
                if str(exc) != "ERR source and destination objects are the same":
                    raise AssertionError(f"unexpected MOVE same-db error: {exc}") from exc
            try:
                client.move("key", 1)
                raise AssertionError("expected MOVE key 1 to fail in single-db mode")
            except RespError as exc:
                if str(exc) != "ERR DB index is out of range":
                    raise AssertionError(f"unexpected MOVE range error: {exc}") from exc
            if client.wait(0, 0) != 0:
                raise AssertionError("expected WAIT 0 0 to return 0")
            if client.wait(1, 10) != 0:
                raise AssertionError("expected WAIT 1 10 to return 0 without replicas")
            try:
                client.wait(1, -1)
                raise AssertionError("expected WAIT negative timeout to fail")
            except RespError as exc:
                if str(exc) != "ERR timeout is negative":
                    raise AssertionError(f"unexpected WAIT timeout error: {exc}") from exc
            assert client.rpush("sortnums", "3", "1", "2") == 3
            assert client.sort("sortnums") == [b"1", b"2", b"3"]
            assert client.set("sortw_1", "20")
            assert client.set("sortw_2", "10")
            assert client.set("sortw_3", "30")
            assert client.set("obj_1", "one")
            assert client.set("obj_2", "two")
            assert client.set("obj_3", "three")
            assert client.sort("sortnums", "BY", "sortw_*", "GET", "obj_*", "GET", "#") == [b"two", b"2", b"one", b"1", b"three", b"3"]
            assert client.sort("sortnums", "STORE", "sortout") == 3
            assert client.lrange("sortout", 0, -1) == [b"1", b"2", b"3"]
            assert client.delete("sortnums", "sortout", "sortw_1", "sortw_2", "sortw_3", "obj_1", "obj_2", "obj_3") == 8
            assert client.exists("key", "missing") == 1
            assert client.expire("key", 2)
            ttl = client.ttl("key")
            if ttl not in (1, 2):
                raise AssertionError(f"unexpected ttl: {ttl}")
            assert client.set("ms", "value")
            assert client.pexpire("ms", 1500)
            pttl = client.pttl("ms")
            if pttl <= 0 or pttl > 1500:
                raise AssertionError(f"unexpected pttl: {pttl}")
            assert client.persist("ms")
            assert client.pttl("ms") == -1
            assert client.delete("ms") == 1
            assert client.set("sec", "value")
            sec_deadline = int(time.time()) + 4
            assert client.expireat("sec", sec_deadline)
            assert client.expiretime("sec") == sec_deadline
            assert client.pexpiretime("sec") == sec_deadline * 1000
            assert client.getex("sec") == b"value"
            assert client.getex("sec", "PERSIST") == b"value"
            assert client.expiretime("sec") == -1
            assert client.set("pxkey", "value")
            assert client.getex("pxkey", "PX", "1200") == b"value"
            pxkey_pttl = client.pttl("pxkey")
            if pxkey_pttl <= 0 or pxkey_pttl > 1200:
                raise AssertionError(f"unexpected pxkey pttl: {pxkey_pttl}")
            assert client.set("axkey", "value")
            axkey_deadline = int(time.time() * 1000) + 2500
            assert client.getex("axkey", "PXAT", str(axkey_deadline)) == b"value"
            assert client.pexpiretime("axkey") == axkey_deadline
            assert client.psetex("ps-key", 1500, "value")
            ps_key_pttl = client.pttl("ps-key")
            if ps_key_pttl <= 0 or ps_key_pttl > 1500:
                raise AssertionError(f"unexpected ps-key pttl: {ps_key_pttl}")
            assert client.set("abs", "value")
            abs_deadline = int(time.time() * 1000) + 4500
            assert client.pexpireat("abs", abs_deadline)
            abs_ttl = client.ttl("abs")
            if abs_ttl < 3 or abs_ttl > 5:
                raise AssertionError(f"unexpected abs ttl: {abs_ttl}")
            assert client.delete("abs", "sec", "pxkey", "axkey", "ps-key") == 5
            assert client.save()
            if client.lastsave() <= 0:
                raise AssertionError("expected LASTSAVE > 0")

            assert client.hset("hash", "field", "value") == 1
            assert client.hget("hash", "field") == b"value"
            assert client.hincrby("hash", "counter", 2) == 2
            assert client.hincrbyfloat("hash", "ratio", "1.5") == b"1.5"
            assert set(client.hkeys("hash")) == {b"counter", b"field", b"ratio"}
            assert set(client.hvals("hash")) == {b"2", b"value", b"1.5"}
            hgetall = client.hgetall("hash")
            if len(hgetall) != 6:
                raise AssertionError(f"unexpected hgetall size: {hgetall!r}")
            assert client.hexists("hash", "field") == 1
            assert client.hexists("hash", "missing") == 0
            assert client.hlen("hash") == 3
            assert client.hmget("hash", "field", "missing", "counter") == [b"value", None, b"2"]
            assert client.hsetnx("hash", "extra", "value") == 1
            assert client.hsetnx("hash", "field", "next") == 0
            assert client.hstrlen("hash", "field") == 5
            assert client.hstrlen("hash", "missing") == 0
            assert client.hdel("hash", "field", "counter", "extra") == 3
            assert client.hlen("hash") == 1
            cursor, hscan_items = client.hscan("hash", 0, count=16)
            if cursor != 0 or len(hscan_items) != 2:
                raise AssertionError(f"unexpected hscan result: cursor={cursor} items={hscan_items!r}")

            assert client.lpush("list", "a", "b", "c") == 3
            assert client.lrange("list", 0, -1) == [b"c", b"b", b"a"]
            assert client.lpop("list") == b"c"
            assert client.rpush("rlist", "a", "b", "c") == 3
            assert client.llen("rlist") == 3
            assert client.lindex("rlist", 0) == b"a"
            assert client.lindex("rlist", -1) == b"c"
            assert client.lset("rlist", 1, "mid")
            assert client.lrange("rlist", 0, -1) == [b"a", b"mid", b"c"]
            assert client.rpop("rlist") == b"c"
            assert client.llen("rlist") == 2
            assert client.delete("rlist") == 1
            assert client.rpush("wlist", "a", "b", "c", "b", "d") == 5
            assert client.linsert("wlist", "BEFORE", "c", "x") == 6
            assert client.lrange("wlist", 0, -1) == [b"a", b"b", b"x", b"c", b"b", b"d"]
            assert client.lrem("wlist", 1, "b") == 1
            assert client.lrange("wlist", 0, -1) == [b"a", b"x", b"c", b"b", b"d"]
            assert client.ltrim("wlist", 1, 3)
            assert client.lrange("wlist", 0, -1) == [b"x", b"c", b"b"]
            assert client.delete("wlist") == 1
            assert client.rpush("xlist", "a", "b") == 2
            assert client.lpushx("missing", "z") == 0
            assert client.lpushx("xlist", "head") == 3
            assert client.rpushx("xlist", "tail") == 4
            assert client.lpos("xlist", "b") == 2
            assert client.lrange("xlist", 0, -1) == [b"head", b"a", b"b", b"tail"]
            assert client.delete("xlist") == 1

            assert client.sadd("set", "a", "b") == 2
            assert client.smembers("set") == {b"a", b"b"}
            assert client.srem("set", "a") == 1
            assert client.sadd("spin", "a", "b") == 2
            srand = client.srandmember("spin")
            if srand not in (b"a", b"b"):
                raise AssertionError(f"unexpected srandmember: {srand!r}")
            spop = client.spop("spin")
            if spop not in (b"a", b"b"):
                raise AssertionError(f"unexpected spop: {spop!r}")
            if len(client.smembers("spin")) != 1:
                raise AssertionError("expected spin to retain exactly one member after SPOP")
            assert client.delete("spin") == 1
            assert client.sadd("s1", "a", "b", "c", "d") == 4
            assert client.sadd("s2", "b", "c") == 2
            assert client.sadd("s3", "c", "d") == 2
            assert client.sinter("s1", "s2", "s3") == {b"c"}
            assert client.sdiff("s1", "s2") == {b"a", b"d"}
            assert client.sunion("s1", "s2", "s3") == {b"a", b"b", b"c", b"d"}
            assert client.sinterstore("si", "s1", "s2", "s3") == 1
            assert client.smembers("si") == {b"c"}
            assert client.sdiffstore("sd", "s1", "s2") == 2
            assert client.smembers("sd") == {b"a", b"d"}
            assert client.sunionstore("su", "s1", "s2", "s3") == 4
            assert client.smembers("su") == {b"a", b"b", b"c", b"d"}
            assert client.delete("s1", "s2", "s3", "si", "sd", "su") == 6

            assert client.zadd("zset", {"b": 2, "a": 1}) == 2
            assert client.zcard("zset") == 2
            assert client.zcount("zset", 1, 2) == 2
            assert client.zincrby("zset", 3, "a") == b"4"
            assert client.zcount("zset", 4, 4) == 1
            assert client.zrange("zset", 0, -1) == [b"b", b"a"]
            assert client.zrangebyscore("zset", 2, 4) == [b"b", b"a"]
            assert client.zrevrangebyscore("zset", 4, 2) == [b"a", b"b"]
            assert client.zrem("zset", "a") == 1
            assert client.zadd("zwork", {"b": 2, "a": 1, "c": 3}) == 3
            cursor, zscan_items = client.zscan("zwork", 0, count=16)
            if cursor != 0 or zscan_items != [b"a", b"1", b"b", b"2", b"c", b"3"]:
                raise AssertionError(f"unexpected zscan result: cursor={cursor} items={zscan_items!r}")
            assert client.zremrangebyrank("zwork", 0, 1) == 2
            assert client.zrange("zwork", 0, -1) == [b"c"]
            assert client.zremrangebyscore("zwork", 3, 3) == 1
            assert client.zcard("zwork") == 0
            assert client.delete("zwork") == 0

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

            assert client.set("flush-key", "value")
            assert client.flushdb()
            assert client.dbsize() == 0
            assert client.set("flush-key-2", "value")
            assert client.flushall()
            assert client.dbsize() == 0
            assert client.set("dump-src", "value")
            dump_payload = client.dump("dump-src")
            if dump_payload is None or dump_payload[0:8] != b"RUYARDB1":
                raise AssertionError(f"unexpected dump payload: {dump_payload!r}")
            assert client.restore("dump-dst", 1500, dump_payload)
            assert client.get("dump-dst") == b"value"
            dump_pttl = client.pttl("dump-dst")
            if dump_pttl <= 0 or dump_pttl > 1500:
                raise AssertionError(f"unexpected dump restore pttl: {dump_pttl}")
            assert client.delete("dump-src", "dump-dst") == 2

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

        auth_proc = subprocess.Popen(
            [str(BIN), str(auth_port), "8", str(auth_aof_path), "0", "noeviction", "secret"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        auth_deadline = time.monotonic() + 5.0
        auth_client: RedisPySubsetClient | None = None
        while time.monotonic() < auth_deadline:
            try:
                auth_client = RedisPySubsetClient("127.0.0.1", auth_port)
                break
            except OSError:
                time.sleep(0.05)
        if auth_client is None:
            raise RuntimeError("auth redis-uya did not start in time")

        try:
            try:
                auth_client.ping()
                raise AssertionError("expected PING before AUTH to fail")
            except RespError as exc:
                if str(exc) != "NOAUTH Authentication required.":
                    raise AssertionError(f"unexpected NOAUTH reply: {exc}") from exc
            try:
                auth_client.auth("wrong")
                raise AssertionError("expected AUTH wrong to fail")
            except RespError as exc:
                if str(exc) != "WRONGPASS invalid username-password pair or user is disabled.":
                    raise AssertionError(f"unexpected WRONGPASS reply: {exc}") from exc
            assert auth_client.auth("secret", username="default")
            assert auth_client.ping()
            auth_config = auth_client.config_get("requirepass")
            if auth_config.get("requirepass") != "secret":
                raise AssertionError(f"unexpected requirepass config: {auth_config!r}")
            auth_client.shutdown_nosave()
        finally:
            if auth_client is not None:
                auth_client.close()

        stop_process(auth_proc)
        if auth_proc.returncode not in (0, -15):
            stdout, stderr = auth_proc.communicate()
            raise RuntimeError(
                f"auth redis-uya exited with {auth_proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
    finally:
        stop_process(proc)
        if auth_proc is not None:
            stop_process(auth_proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)
        auth_aof_path.unlink(missing_ok=True)


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
