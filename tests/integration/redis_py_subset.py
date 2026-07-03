#!/usr/bin/env python3
from __future__ import annotations
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "build" / "redis-uya"
REDIS_UYA_VERSION = "v0.9.1-dev"


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

    def copy(self, source: str, destination: str, *parts: str) -> int:
        return int(self._request(b"COPY", source.encode(), destination.encode(), *(part.encode() for part in parts)))

    def incr(self, key: str) -> int:
        return int(self._request(b"INCR", key.encode()))

    def decr(self, key: str) -> int:
        return int(self._request(b"DECR", key.encode()))

    def incrby(self, key: str, amount: int) -> int:
        return int(self._request(b"INCRBY", key.encode(), str(amount).encode()))

    def increx(self, key: str, *options: str) -> list[int]:
        result = self._request(b"INCREX", key.encode(), *(option.encode() for option in options))
        if not isinstance(result, list):
            raise AssertionError(f"unexpected INCREX result: {result!r}")
        return [int(item) for item in result]

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

    def msetex(self, mapping: dict[str, str], *options: str) -> int:
        parts: list[bytes] = [b"MSETEX", str(len(mapping)).encode()]
        for key, value in mapping.items():
            parts.append(key.encode())
            parts.append(value.encode())
        for option in options:
            parts.append(option.encode())
        return int(self._request(*parts))

    def lcs(self, key1: str, key2: str, *options: str):
        result = self._request(b"LCS", key1.encode(), key2.encode(), *(option.encode() for option in options))
        if options and options[0].upper() == "LEN":
            return int(result)
        assert isinstance(result, bytes)
        return result

    def getrange(self, key: str, start: int, stop: int) -> bytes:
        result = self._request(b"GETRANGE", key.encode(), str(start).encode(), str(stop).encode())
        assert isinstance(result, bytes)
        return result

    def substr(self, key: str, start: int, stop: int) -> bytes:
        result = self._request(b"SUBSTR", key.encode(), str(start).encode(), str(stop).encode())
        assert isinstance(result, bytes)
        return result

    def digest(self, key: str) -> bytes | None:
        result = self._request(b"DIGEST", key.encode())
        assert result is None or isinstance(result, bytes)
        return result

    def getbit(self, key: str, offset: int) -> int:
        return int(self._request(b"GETBIT", key.encode(), str(offset).encode()))

    def setbit(self, key: str, offset: int, value: int) -> int:
        return int(self._request(b"SETBIT", key.encode(), str(offset).encode(), str(value).encode()))

    def bitcount(self, key: str, *parts: str) -> int:
        encoded: list[bytes] = [b"BITCOUNT", key.encode()]
        for part in parts:
            encoded.append(part.encode())
        return int(self._request(*encoded))

    def bitpos(self, key: str, bit: int, *parts: str) -> int:
        encoded: list[bytes] = [b"BITPOS", key.encode(), str(bit).encode()]
        for part in parts:
            encoded.append(part.encode())
        return int(self._request(*encoded))

    def bitop(self, operation: str, dest: str, *keys: str) -> int:
        return int(self._request(b"BITOP", operation.encode(), dest.encode(), *(key.encode() for key in keys)))

    def bitfield(self, key: str, *parts: str):
        result = self._request(b"BITFIELD", key.encode(), *(part.encode() for part in parts))
        assert isinstance(result, list)
        return result

    def bitfield_ro(self, key: str, *parts: str):
        result = self._request(b"BITFIELD_RO", key.encode(), *(part.encode() for part in parts))
        assert isinstance(result, list)
        return result

    def pfadd(self, key: str, *elements: str) -> int:
        return int(self._request(b"PFADD", key.encode(), *(element.encode() for element in elements)))

    def pfcount(self, *keys: str) -> int:
        return int(self._request(b"PFCOUNT", *(key.encode() for key in keys)))

    def pfmerge(self, dest: str, *sources: str) -> bool:
        return self._request(b"PFMERGE", dest.encode(), *(source.encode() for source in sources)) == "OK"

    def pfselftest(self) -> bool:
        return self._request(b"PFSELFTEST") == "OK"

    def pfdebug(self, subcommand: bytes, key: str):
        return self._request(b"PFDEBUG", subcommand, key.encode())

    def geoadd(self, key: str, *parts: str) -> int:
        return int(self._request(b"GEOADD", key.encode(), *(part.encode() for part in parts)))

    def geodist(self, key: str, member1: str, member2: str, unit: str = "m") -> bytes | None:
        result = self._request(b"GEODIST", key.encode(), member1.encode(), member2.encode(), unit.encode())
        assert result is None or isinstance(result, bytes)
        return result

    def geopos(self, key: str, *members: str):
        result = self._request(b"GEOPOS", key.encode(), *(member.encode() for member in members))
        assert isinstance(result, list)
        return result

    def geohash(self, key: str, *members: str):
        result = self._request(b"GEOHASH", key.encode(), *(member.encode() for member in members))
        assert isinstance(result, list)
        return result

    def geosearch(self, key: str, *parts: str):
        result = self._request(b"GEOSEARCH", key.encode(), *(part.encode() for part in parts))
        assert isinstance(result, list)
        return result

    def geosearchstore(self, destination: str, source: str, *parts: str) -> int:
        return int(self._request(b"GEOSEARCHSTORE", destination.encode(), source.encode(), *(part.encode() for part in parts)))

    def georadius_ro(self, key: str, longitude: str, latitude: str, radius: str, unit: str, *parts: str):
        result = self._request(b"GEORADIUS_RO", key.encode(), longitude.encode(), latitude.encode(), radius.encode(), unit.encode(), *(part.encode() for part in parts))
        assert isinstance(result, list)
        return result

    def georadius(self, key: str, longitude: str, latitude: str, radius: str, unit: str, *parts: str):
        result = self._request(b"GEORADIUS", key.encode(), longitude.encode(), latitude.encode(), radius.encode(), unit.encode(), *(part.encode() for part in parts))
        assert isinstance(result, list)
        return result

    def georadiusbymember_ro(self, key: str, member: str, radius: str, unit: str, *parts: str):
        result = self._request(b"GEORADIUSBYMEMBER_RO", key.encode(), member.encode(), radius.encode(), unit.encode(), *(part.encode() for part in parts))
        assert isinstance(result, list)
        return result

    def georadiusbymember(self, key: str, member: str, radius: str, unit: str, *parts: str):
        result = self._request(b"GEORADIUSBYMEMBER", key.encode(), member.encode(), radius.encode(), unit.encode(), *(part.encode() for part in parts))
        assert isinstance(result, list)
        return result

    def eval(self, script: str, numkeys: int, *parts: str):
        return self._request(b"EVAL", script.encode(), str(numkeys).encode(), *(part.encode() for part in parts))

    def eval_ro(self, script: str, numkeys: int, *parts: str):
        return self._request(b"EVAL_RO", script.encode(), str(numkeys).encode(), *(part.encode() for part in parts))

    def evalsha(self, sha1: str, numkeys: int, *parts: str):
        return self._request(b"EVALSHA", sha1.encode(), str(numkeys).encode(), *(part.encode() for part in parts))

    def evalsha_ro(self, sha1: str, numkeys: int, *parts: str):
        return self._request(b"EVALSHA_RO", sha1.encode(), str(numkeys).encode(), *(part.encode() for part in parts))

    def fcall(self, function: bytes, numkeys: int, *parts: bytes):
        return self._request(b"FCALL", function, str(numkeys).encode(), *parts)

    def fcall_ro(self, function: bytes, numkeys: int, *parts: bytes):
        return self._request(b"FCALL_RO", function, str(numkeys).encode(), *parts)

    def script_load(self, script: str) -> bytes:
        result = self._request(b"SCRIPT", b"LOAD", script.encode())
        assert isinstance(result, bytes)
        return result

    def script_exists(self, *sha1s: str):
        result = self._request(b"SCRIPT", b"EXISTS", *(sha.encode() for sha in sha1s))
        assert isinstance(result, list)
        return result

    def script_flush(self) -> bool:
        return self._request(b"SCRIPT", b"FLUSH") == "OK"

    def script_debug(self, mode: bytes):
        return self._request(b"SCRIPT", b"DEBUG", mode)

    def script_kill(self):
        return self._request(b"SCRIPT", b"KILL")

    def function_help(self):
        result = self._request(b"FUNCTION", b"HELP")
        assert isinstance(result, list)
        return result

    def function_list(self):
        result = self._request(b"FUNCTION", b"LIST")
        assert isinstance(result, list)
        return result

    def function_stats(self):
        result = self._request(b"FUNCTION", b"STATS")
        assert isinstance(result, list)
        return result

    def function_flush(self, mode: bytes | None = None):
        parts = [b"FUNCTION", b"FLUSH"]
        if mode is not None:
            parts.append(mode)
        return self._request(*parts)

    def function_delete(self, library_name: bytes):
        return self._request(b"FUNCTION", b"DELETE", library_name)

    def function_load(self, code: bytes, replace: bool = False):
        parts = [b"FUNCTION", b"LOAD"]
        if replace:
            parts.append(b"REPLACE")
        parts.append(code)
        return self._request(*parts)

    def function_dump(self):
        result = self._request(b"FUNCTION", b"DUMP")
        assert isinstance(result, bytes)
        return result

    def function_restore(self, payload: bytes, policy: bytes | None = None):
        parts = [b"FUNCTION", b"RESTORE", payload]
        if policy is not None:
            parts.append(policy)
        return self._request(*parts)

    def function_kill(self):
        return self._request(b"FUNCTION", b"KILL")

    def acl_help(self):
        result = self._request(b"ACL", b"HELP")
        assert isinstance(result, list)
        return result

    def acl_whoami(self):
        result = self._request(b"ACL", b"WHOAMI")
        assert isinstance(result, bytes)
        return result

    def acl_users(self):
        result = self._request(b"ACL", b"USERS")
        assert isinstance(result, list)
        return result

    def acl_list(self):
        result = self._request(b"ACL", b"LIST")
        assert isinstance(result, list)
        return result

    def acl_cat(self, category: bytes | None = None):
        if category is None:
            result = self._request(b"ACL", b"CAT")
        else:
            result = self._request(b"ACL", b"CAT", category)
        assert isinstance(result, list)
        return result

    def acl_getuser(self, username: bytes):
        result = self._request(b"ACL", b"GETUSER", username)
        assert result is None or isinstance(result, list)
        return result

    def acl_log(self, count_or_reset: bytes | None = None):
        if count_or_reset is None:
            result = self._request(b"ACL", b"LOG")
        else:
            result = self._request(b"ACL", b"LOG", count_or_reset)
        assert isinstance(result, list) or isinstance(result, str)
        return result

    def acl_genpass(self, bits: bytes | None = None):
        if bits is None:
            result = self._request(b"ACL", b"GENPASS")
        else:
            result = self._request(b"ACL", b"GENPASS", bits)
        assert isinstance(result, bytes)
        return result

    def acl_save(self):
        return self._request(b"ACL", b"SAVE")

    def acl_load(self):
        return self._request(b"ACL", b"LOAD")

    def acl_deluser(self, *users: bytes):
        result = self._request(b"ACL", b"DELUSER", *users)
        assert isinstance(result, int)
        return result

    def acl_dryrun(self, username: bytes, *command: bytes):
        return self._request(b"ACL", b"DRYRUN", username, *command)

    def acl_setuser(self, username: bytes, *modifiers: bytes):
        return self._request(b"ACL", b"SETUSER", username, *modifiers)

    def memory_usage(self, key: str, samples: int | None = None) -> int | None:
        parts = [b"MEMORY", b"USAGE", key.encode()]
        if samples is not None:
            parts.extend([b"SAMPLES", str(samples).encode()])
        result = self._request(*parts)
        assert result is None or isinstance(result, int)
        return result

    def memory_stats(self):
        result = self._request(b"MEMORY", b"STATS")
        assert isinstance(result, list)
        return result

    def memory_doctor(self) -> bytes:
        result = self._request(b"MEMORY", b"DOCTOR")
        assert isinstance(result, bytes)
        return result

    def memory_malloc_stats(self) -> bytes:
        result = self._request(b"MEMORY", b"MALLOC-STATS")
        assert isinstance(result, bytes)
        return result

    def memory_purge(self):
        return self._request(b"MEMORY", b"PURGE")

    def module_list(self):
        result = self._request(b"MODULE", b"LIST")
        assert isinstance(result, list)
        return result

    def module_load(self, path: bytes):
        return self._request(b"MODULE", b"LOAD", path)

    def module_loadex(self, path: bytes):
        return self._request(b"MODULE", b"LOADEX", path)

    def module_unload(self, name: bytes):
        return self._request(b"MODULE", b"UNLOAD", name)

    def slowlog_len(self) -> int:
        return int(self._request(b"SLOWLOG", b"LEN"))

    def slowlog_get(self, count: int | None = None):
        if count is None:
            result = self._request(b"SLOWLOG", b"GET")
        else:
            result = self._request(b"SLOWLOG", b"GET", str(count).encode())
        assert isinstance(result, list)
        return result

    def slowlog_reset(self) -> bool:
        return self._request(b"SLOWLOG", b"RESET") == "OK"

    def latency_latest(self):
        result = self._request(b"LATENCY", b"LATEST")
        assert isinstance(result, list)
        return result

    def latency_history(self, event: str):
        result = self._request(b"LATENCY", b"HISTORY", event.encode())
        assert isinstance(result, list)
        return result

    def latency_histogram(self, *commands: str):
        args = [b"LATENCY", b"HISTOGRAM"]
        for command in commands:
            args.append(command.encode())
        result = self._request(*args)
        assert isinstance(result, list)
        return result

    def latency_doctor(self) -> bytes:
        result = self._request(b"LATENCY", b"DOCTOR")
        assert isinstance(result, bytes)
        return result

    def latency_reset(self) -> int:
        return int(self._request(b"LATENCY", b"RESET"))

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

    def delex(self, key: str, *parts: str) -> int:
        return int(self._request(b"DELEX", key.encode(), *(part.encode() for part in parts)))

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

    def randomkey(self) -> bytes | None:
        return self._request(b"RANDOMKEY")

    def keys(self, pattern: str) -> list[bytes]:
        result = self._request(b"KEYS", pattern.encode())
        assert isinstance(result, list)
        return result

    def touch(self, *keys: str) -> int:
        return int(self._request(b"TOUCH", *(key.encode() for key in keys)))

    def unlink(self, *keys: str) -> int:
        return int(self._request(b"UNLINK", *(key.encode() for key in keys)))

    def time(self) -> tuple[int, int]:
        result = self._request(b"TIME")
        assert isinstance(result, list) and len(result) == 2
        return int(result[0]), int(result[1])

    def role(self):
        return self._request(b"ROLE")

    def replconf(self, *args: bytes) -> bool:
        return self._request(b"REPLCONF", *args) == "OK"

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

    def swapdb(self, first: int | str, second: int | str) -> bool:
        result = self._request(b"SWAPDB", str(first).encode(), str(second).encode())
        return result == "OK"

    def lolwut(self, *args: bytes) -> bytes:
        result = self._request(b"LOLWUT", *args)
        if not isinstance(result, bytes):
            raise AssertionError(f"unexpected LOLWUT result: {result!r}")
        return result

    def debug(self, *args: bytes):
        return self._request(b"DEBUG", *args)

    def failover(self, *args: bytes):
        return self._request(b"FAILOVER", *args)

    def wait(self, replicas: int, timeout_ms: int) -> int:
        return int(self._request(b"WAIT", str(replicas).encode(), str(timeout_ms).encode()))

    def waitaof(self, local: int, replicas: int, timeout_ms: int) -> list[int]:
        result = self._request(b"WAITAOF", str(local).encode(), str(replicas).encode(), str(timeout_ms).encode())
        if not isinstance(result, list):
            raise AssertionError(f"unexpected WAITAOF result: {result!r}")
        return [int(item) for item in result]

    def sort(self, key: str, *parts: str) :
        encoded: list[bytes] = [b"SORT", key.encode()]
        for part in parts:
            encoded.append(part.encode())
        return self._request(*encoded)

    def sort_ro(self, key: str, *parts: str):
        encoded: list[bytes] = [b"SORT_RO", key.encode()]
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

    def hset(self, key: str, *field_values: str) -> int:
        return int(self._request(b"HSET", key.encode(), *(item.encode() for item in field_values)))

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

    def hrandfield(self, key: str, count: int | None = None, withvalues: bool = False) -> bytes | list[bytes] | None:
        parts: list[bytes] = [b"HRANDFIELD", key.encode()]
        if count is not None:
            parts.append(str(count).encode())
            if withvalues:
                parts.append(b"WITHVALUES")
        result = self._request(*parts)
        assert result is None or isinstance(result, bytes) or isinstance(result, list)
        return result

    def hdel(self, key: str, *fields: str) -> int:
        return int(self._request(b"HDEL", key.encode(), *(field.encode() for field in fields)))

    def hgetdel(self, key: str, *fields: str) -> list[bytes | None]:
        result = self._request(
            b"HGETDEL",
            key.encode(),
            b"FIELDS",
            str(len(fields)).encode(),
            *(field.encode() for field in fields),
        )
        assert isinstance(result, list)
        return result

    def hgetex(self, key: str, *fields: str, option: bytes | None = None, value: bytes | None = None) -> list[bytes | None]:
        parts: list[bytes] = [b"HGETEX", key.encode()]
        if option is not None:
            parts.append(option)
            if value is not None:
                parts.append(value)
        parts.extend([b"FIELDS", str(len(fields)).encode()])
        parts.extend(field.encode() for field in fields)
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def hsetex(self, key: str, field: str, value: str, option: bytes | None = None, option_value: bytes | None = None) -> int:
        parts: list[bytes] = [b"HSETEX", key.encode()]
        if option is not None:
            parts.append(option)
            if option_value is not None:
                parts.append(option_value)
        parts.extend([b"FIELDS", b"1", field.encode(), value.encode()])
        return int(self._request(*parts))

    def hexpire(self, key: str, seconds: int, *fields: str, option: bytes | None = None) -> list[int]:
        parts: list[bytes] = [b"HEXPIRE", key.encode(), str(seconds).encode()]
        if option is not None:
            parts.append(option)
        parts.extend([b"FIELDS", str(len(fields)).encode()])
        parts.extend(field.encode() for field in fields)
        result = self._request(*parts)
        assert isinstance(result, list)
        return [int(item) for item in result]

    def hexpireat(self, key: str, unix_seconds: int, *fields: str, option: bytes | None = None) -> list[int]:
        parts: list[bytes] = [b"HEXPIREAT", key.encode(), str(unix_seconds).encode()]
        if option is not None:
            parts.append(option)
        parts.extend([b"FIELDS", str(len(fields)).encode()])
        parts.extend(field.encode() for field in fields)
        result = self._request(*parts)
        assert isinstance(result, list)
        return [int(item) for item in result]

    def hpexpire(self, key: str, milliseconds: int, *fields: str, option: bytes | None = None) -> list[int]:
        parts: list[bytes] = [b"HPEXPIRE", key.encode(), str(milliseconds).encode()]
        if option is not None:
            parts.append(option)
        parts.extend([b"FIELDS", str(len(fields)).encode()])
        parts.extend(field.encode() for field in fields)
        result = self._request(*parts)
        assert isinstance(result, list)
        return [int(item) for item in result]

    def hpexpireat(self, key: str, unix_milliseconds: int, *fields: str, option: bytes | None = None) -> list[int]:
        parts: list[bytes] = [b"HPEXPIREAT", key.encode(), str(unix_milliseconds).encode()]
        if option is not None:
            parts.append(option)
        parts.extend([b"FIELDS", str(len(fields)).encode()])
        parts.extend(field.encode() for field in fields)
        result = self._request(*parts)
        assert isinstance(result, list)
        return [int(item) for item in result]

    def httl(self, key: str, *fields: str) -> list[int]:
        result = self._request(
            b"HTTL",
            key.encode(),
            b"FIELDS",
            str(len(fields)).encode(),
            *(field.encode() for field in fields),
        )
        assert isinstance(result, list)
        return [int(item) for item in result]

    def hpttl(self, key: str, *fields: str) -> list[int]:
        result = self._request(
            b"HPTTL",
            key.encode(),
            b"FIELDS",
            str(len(fields)).encode(),
            *(field.encode() for field in fields),
        )
        assert isinstance(result, list)
        return [int(item) for item in result]

    def hexpiretime(self, key: str, *fields: str) -> list[int]:
        result = self._request(
            b"HEXPIRETIME",
            key.encode(),
            b"FIELDS",
            str(len(fields)).encode(),
            *(field.encode() for field in fields),
        )
        assert isinstance(result, list)
        return [int(item) for item in result]

    def hpexpiretime(self, key: str, *fields: str) -> list[int]:
        result = self._request(
            b"HPEXPIRETIME",
            key.encode(),
            b"FIELDS",
            str(len(fields)).encode(),
            *(field.encode() for field in fields),
        )
        assert isinstance(result, list)
        return [int(item) for item in result]

    def hpersist(self, key: str, *fields: str) -> list[int]:
        result = self._request(
            b"HPERSIST",
            key.encode(),
            b"FIELDS",
            str(len(fields)).encode(),
            *(field.encode() for field in fields),
        )
        assert isinstance(result, list)
        return [int(item) for item in result]

    def hexists(self, key: str, field: str) -> int:
        return int(self._request(b"HEXISTS", key.encode(), field.encode()))

    def hlen(self, key: str) -> int:
        return int(self._request(b"HLEN", key.encode()))

    def hmget(self, key: str, *fields: str) -> list[bytes | None]:
        result = self._request(b"HMGET", key.encode(), *(field.encode() for field in fields))
        assert isinstance(result, list)
        return result

    def hmset(self, key: str, *field_values: str) -> bool:
        return self._request(b"HMSET", key.encode(), *(item.encode() for item in field_values)) == "OK"

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

    def lpop(self, key: str, count: int | None = None):
        if count is None:
            return self._request(b"LPOP", key.encode())
        return self._request(b"LPOP", key.encode(), str(count).encode())

    def rpush(self, key: str, *values: str) -> int:
        return int(self._request(b"RPUSH", key.encode(), *(value.encode() for value in values)))

    def rpop(self, key: str, count: int | None = None):
        if count is None:
            return self._request(b"RPOP", key.encode())
        return self._request(b"RPOP", key.encode(), str(count).encode())

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

    def lmove(self, source: str, destination: str, wherefrom: str, whereto: str) -> bytes | None:
        result = self._request(
            b"LMOVE",
            source.encode(),
            destination.encode(),
            wherefrom.encode(),
            whereto.encode(),
        )
        assert result is None or isinstance(result, bytes)
        return result

    def blmove(self, source: str, destination: str, wherefrom: str, whereto: str, timeout: float) -> bytes | None:
        result = self._request(
            b"BLMOVE",
            source.encode(),
            destination.encode(),
            wherefrom.encode(),
            whereto.encode(),
            str(timeout).encode(),
        )
        assert result is None or isinstance(result, bytes)
        return result

    def rpoplpush(self, source: str, destination: str) -> bytes | None:
        result = self._request(b"RPOPLPUSH", source.encode(), destination.encode())
        assert result is None or isinstance(result, bytes)
        return result

    def lmpop(self, direction: str, *keys: str, count: int | None = None) -> list[bytes | list[bytes]] | None:
        parts: list[bytes] = [b"LMPOP", str(len(keys)).encode(), *(key.encode() for key in keys), direction.encode()]
        if count is not None:
            parts.append(b"COUNT")
            parts.append(str(count).encode())
        result = self._request(*parts)
        assert result is None or isinstance(result, list)
        return result

    def blmpop(self, timeout: float, direction: str, *keys: str, count: int | None = None) -> list[bytes | list[bytes]] | None:
        parts: list[bytes] = [b"BLMPOP", str(timeout).encode(), str(len(keys)).encode(), *(key.encode() for key in keys), direction.encode()]
        if count is not None:
            parts.append(b"COUNT")
            parts.append(str(count).encode())
        result = self._request(*parts)
        assert result is None or isinstance(result, list)
        return result

    def sadd(self, key: str, *members: str) -> int:
        return int(self._request(b"SADD", key.encode(), *(member.encode() for member in members)))

    def smembers(self, key: str) -> set[bytes]:
        result = self._request(b"SMEMBERS", key.encode())
        assert isinstance(result, list)
        return set(result)

    def scard(self, key: str) -> int:
        return int(self._request(b"SCARD", key.encode()))

    def sismember(self, key: str, member: str) -> int:
        return int(self._request(b"SISMEMBER", key.encode(), member.encode()))

    def smismember(self, key: str, *members: str) -> list[int]:
        result = self._request(b"SMISMEMBER", key.encode(), *(member.encode() for member in members))
        assert isinstance(result, list)
        return [int(item) for item in result]

    def srem(self, key: str, *members: str) -> int:
        return int(self._request(b"SREM", key.encode(), *(member.encode() for member in members)))

    def smove(self, source: str, destination: str, member: str) -> int:
        return int(self._request(b"SMOVE", source.encode(), destination.encode(), member.encode()))

    def spop(self, key: str) -> bytes | None:
        return self._request(b"SPOP", key.encode())

    def srandmember(self, key: str) -> bytes | None:
        return self._request(b"SRANDMEMBER", key.encode())

    def sinter(self, *keys: str) -> set[bytes]:
        result = self._request(b"SINTER", *(key.encode() for key in keys))
        assert isinstance(result, list)
        return set(result)

    def sintercard(self, *keys: str, limit: int | None = None) -> int:
        parts: list[bytes] = [b"SINTERCARD", str(len(keys)).encode(), *(key.encode() for key in keys)]
        if limit is not None:
            parts.extend([b"LIMIT", str(limit).encode()])
        return int(self._request(*parts))

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

    def sscan(self, key: str, cursor: int = 0, count: int | None = None) -> tuple[int, list[bytes]]:
        parts: list[bytes] = [b"SSCAN", key.encode(), str(cursor).encode()]
        if count is not None:
            parts.extend([b"COUNT", str(count).encode()])
        result = self._request(*parts)
        assert isinstance(result, list) and len(result) == 2
        next_cursor = int(result[0])
        items = result[1]
        assert isinstance(items, list)
        return next_cursor, items

    def zadd(self, key: str, mapping: dict[str, int]) -> int:
        parts: list[bytes] = [b"ZADD", key.encode()]
        for member, score in mapping.items():
            parts.append(str(score).encode())
            parts.append(member.encode())
        return int(self._request(*parts))

    def zrange(
        self,
        key: str,
        start: int | str,
        stop: int | str,
        withscores: bool = False,
        rev: bool = False,
        byscore: bool = False,
        bylex: bool = False,
        limit_start: int | None = None,
        limit_num: int | None = None,
    ) -> list[bytes]:
        parts: list[bytes] = [b"ZRANGE", key.encode(), str(start).encode(), str(stop).encode()]
        if byscore:
            parts.append(b"BYSCORE")
        if bylex:
            parts.append(b"BYLEX")
        if rev:
            parts.append(b"REV")
        if limit_start is not None or limit_num is not None:
            assert limit_start is not None and limit_num is not None
            parts.extend([b"LIMIT", str(limit_start).encode(), str(limit_num).encode()])
        if withscores:
            parts.append(b"WITHSCORES")
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zrangestore(
        self,
        destination: str,
        source: str,
        start: int | str,
        stop: int | str,
        rev: bool = False,
        byscore: bool = False,
        bylex: bool = False,
        limit_start: int | None = None,
        limit_num: int | None = None,
    ) -> int:
        parts: list[bytes] = [b"ZRANGESTORE", destination.encode(), source.encode(), str(start).encode(), str(stop).encode()]
        if byscore:
            parts.append(b"BYSCORE")
        if bylex:
            parts.append(b"BYLEX")
        if rev:
            parts.append(b"REV")
        if limit_start is not None or limit_num is not None:
            assert limit_start is not None and limit_num is not None
            parts.extend([b"LIMIT", str(limit_start).encode(), str(limit_num).encode()])
        return int(self._request(*parts))

    def zrevrange(self, key: str, start: int, stop: int, withscores: bool = False) -> list[bytes]:
        parts: list[bytes] = [b"ZREVRANGE", key.encode(), str(start).encode(), str(stop).encode()]
        if withscores:
            parts.append(b"WITHSCORES")
        result = self._request(*parts)
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

    def zinter(self, *keys: str, withscores: bool = False, weights: list[int] | None = None, aggregate: str | None = None) -> list[bytes]:
        parts: list[bytes] = [b"ZINTER", str(len(keys)).encode(), *(key.encode() for key in keys)]
        if weights is not None:
            parts.extend([b"WEIGHTS", *(str(weight).encode() for weight in weights)])
        if aggregate is not None:
            parts.extend([b"AGGREGATE", aggregate.encode()])
        if withscores:
            parts.append(b"WITHSCORES")
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zintercard(self, *keys: str, limit: int | None = None) -> int:
        parts: list[bytes] = [b"ZINTERCARD", str(len(keys)).encode(), *(key.encode() for key in keys)]
        if limit is not None:
            parts.extend([b"LIMIT", str(limit).encode()])
        return int(self._request(*parts))

    def zlexcount(self, key: str, minimum: str, maximum: str) -> int:
        return int(self._request(b"ZLEXCOUNT", key.encode(), minimum.encode(), maximum.encode()))

    def zrangebylex(self, key: str, minimum: str, maximum: str, offset: int | None = None, count: int | None = None) -> list[bytes]:
        parts: list[bytes] = [b"ZRANGEBYLEX", key.encode(), minimum.encode(), maximum.encode()]
        if offset is not None and count is not None:
            parts.extend([b"LIMIT", str(offset).encode(), str(count).encode()])
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zrevrangebylex(self, key: str, maximum: str, minimum: str, offset: int | None = None, count: int | None = None) -> list[bytes]:
        parts: list[bytes] = [b"ZREVRANGEBYLEX", key.encode(), maximum.encode(), minimum.encode()]
        if offset is not None and count is not None:
            parts.extend([b"LIMIT", str(offset).encode(), str(count).encode()])
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zremrangebylex(self, key: str, minimum: str, maximum: str) -> int:
        return int(self._request(b"ZREMRANGEBYLEX", key.encode(), minimum.encode(), maximum.encode()))

    def zrank(self, key: str, member: str, withscore: bool = False) -> int | tuple[int, bytes] | None:
        parts: list[bytes] = [b"ZRANK", key.encode(), member.encode()]
        if withscore:
            parts.append(b"WITHSCORE")
        result = self._request(*parts)
        if result is None:
            return None
        if withscore:
            assert isinstance(result, list) and len(result) == 2 and isinstance(result[0], int) and isinstance(result[1], bytes)
            return result[0], result[1]
        assert isinstance(result, int)
        return result

    def zrevrank(self, key: str, member: str, withscore: bool = False) -> int | tuple[int, bytes] | None:
        parts: list[bytes] = [b"ZREVRANK", key.encode(), member.encode()]
        if withscore:
            parts.append(b"WITHSCORE")
        result = self._request(*parts)
        if result is None:
            return None
        if withscore:
            assert isinstance(result, list) and len(result) == 2 and isinstance(result[0], int) and isinstance(result[1], bytes)
            return result[0], result[1]
        assert isinstance(result, int)
        return result

    def zscore(self, key: str, member: str) -> bytes | None:
        result = self._request(b"ZSCORE", key.encode(), member.encode())
        assert result is None or isinstance(result, bytes)
        return result

    def zmscore(self, key: str, *members: str) -> list[bytes | None]:
        result = self._request(b"ZMSCORE", key.encode(), *(member.encode() for member in members))
        assert isinstance(result, list)
        return result

    def zpopmin(self, key: str, count: int | None = None) -> list[bytes]:
        parts: list[bytes] = [b"ZPOPMIN", key.encode()]
        if count is not None:
            parts.append(str(count).encode())
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zpopmax(self, key: str, count: int | None = None) -> list[bytes]:
        parts: list[bytes] = [b"ZPOPMAX", key.encode()]
        if count is not None:
            parts.append(str(count).encode())
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zmpop(self, direction: str, *keys: str, count: int | None = None) -> list[bytes | list[list[bytes]]] | None:
        parts: list[bytes] = [b"ZMPOP", str(len(keys)).encode(), *(key.encode() for key in keys), direction.encode()]
        if count is not None:
            parts.append(b"COUNT")
            parts.append(str(count).encode())
        result = self._request(*parts)
        assert result is None or isinstance(result, list)
        return result

    def zrandmember(self, key: str, count: int | None = None, withscores: bool = False) -> bytes | list[bytes] | None:
        parts: list[bytes] = [b"ZRANDMEMBER", key.encode()]
        if count is not None:
            parts.append(str(count).encode())
        if withscores:
            parts.append(b"WITHSCORES")
        result = self._request(*parts)
        assert result is None or isinstance(result, bytes) or isinstance(result, list)
        return result

    def zdiff(self, *keys: str, withscores: bool = False) -> list[bytes]:
        parts: list[bytes] = [b"ZDIFF", str(len(keys)).encode(), *(key.encode() for key in keys)]
        if withscores:
            parts.append(b"WITHSCORES")
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zdiffstore(self, destination: str, *keys: str) -> int:
        return int(self._request(b"ZDIFFSTORE", destination.encode(), str(len(keys)).encode(), *(key.encode() for key in keys)))

    def zinterstore(self, destination: str, *keys: str, weights: list[int] | None = None, aggregate: str | None = None) -> int:
        parts: list[bytes] = [b"ZINTERSTORE", destination.encode(), str(len(keys)).encode(), *(key.encode() for key in keys)]
        if weights is not None:
            parts.extend([b"WEIGHTS", *(str(weight).encode() for weight in weights)])
        if aggregate is not None:
            parts.extend([b"AGGREGATE", aggregate.encode()])
        return int(self._request(*parts))

    def zunion(self, *keys: str, withscores: bool = False, weights: list[int] | None = None, aggregate: str | None = None) -> list[bytes]:
        parts: list[bytes] = [b"ZUNION", str(len(keys)).encode(), *(key.encode() for key in keys)]
        if weights is not None:
            parts.extend([b"WEIGHTS", *(str(weight).encode() for weight in weights)])
        if aggregate is not None:
            parts.extend([b"AGGREGATE", aggregate.encode()])
        if withscores:
            parts.append(b"WITHSCORES")
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zunionstore(self, destination: str, *keys: str, weights: list[int] | None = None, aggregate: str | None = None) -> int:
        parts: list[bytes] = [b"ZUNIONSTORE", destination.encode(), str(len(keys)).encode(), *(key.encode() for key in keys)]
        if weights is not None:
            parts.extend([b"WEIGHTS", *(str(weight).encode() for weight in weights)])
        if aggregate is not None:
            parts.extend([b"AGGREGATE", aggregate.encode()])
        return int(self._request(*parts))

    def zrangebyscore(
        self,
        key: str,
        minimum: int,
        maximum: int,
        withscores: bool = False,
        start: int | None = None,
        num: int | None = None,
    ) -> list[bytes]:
        parts: list[bytes] = [b"ZRANGEBYSCORE", key.encode(), str(minimum).encode(), str(maximum).encode()]
        if start is not None or num is not None:
            assert start is not None and num is not None
            parts.extend([b"LIMIT", str(start).encode(), str(num).encode()])
        if withscores:
            parts.append(b"WITHSCORES")
        result = self._request(*parts)
        assert isinstance(result, list)
        return result

    def zrevrangebyscore(
        self,
        key: str,
        maximum: int,
        minimum: int,
        withscores: bool = False,
        start: int | None = None,
        num: int | None = None,
    ) -> list[bytes]:
        parts: list[bytes] = [b"ZREVRANGEBYSCORE", key.encode(), str(maximum).encode(), str(minimum).encode()]
        if withscores:
            parts.append(b"WITHSCORES")
        if start is not None or num is not None:
            assert start is not None and num is not None
            parts.extend([b"LIMIT", str(start).encode(), str(num).encode()])
        result = self._request(*parts)
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

    def config_set(self, key: str, value: str) -> bool:
        return self._request(b"CONFIG", b"SET", key.encode(), value.encode()) == "OK"

    def config_resetstat(self) -> bool:
        return self._request(b"CONFIG", b"RESETSTAT") == "OK"

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

    def restore_asking(self, key: str, ttl_ms: int, payload: bytes) -> bool:
        return self._request(b"RESTORE-ASKING", key.encode(), str(ttl_ms).encode(), payload) == "OK"

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
            server_sec, server_usec = client.time()
            if server_sec <= 0 or server_usec < 0 or server_usec >= 1_000_000:
                raise AssertionError(f"unexpected TIME reply: {(server_sec, server_usec)}")
            role = client.role()
            if role != [b"master", 0, []]:
                raise AssertionError(f"unexpected ROLE reply: {role!r}")
            if not client.replconf():
                raise AssertionError("expected REPLCONF with no args to return OK")
            if not client.replconf(b"CAPA", b"psync2"):
                raise AssertionError("expected REPLCONF CAPA psync2 to return OK")
            if not client.replconf(b"ACK", b"0"):
                raise AssertionError("expected REPLCONF ACK 0 to return OK")
            assert client.set("key", "value")
            assert client.randomkey() == b"key"
            assert client.get("key") == b"value"
            assert client.copy("key", "keycopy") == 1
            assert client.get("keycopy") == b"value"
            assert client.copy("key", "keycopy") == 0
            assert client.copy("key", "keycopy", "REPLACE") == 1
            assert client.copy("missing", "none") == 0
            assert client.delete("keycopy") == 1
            assert client.incr("counter") == 1
            assert client.incrby("counter", 4) == 5
            assert client.increx("excounter") == [1, 1]
            assert client.increx("excounter", "BYINT", "4") == [5, 4]
            assert client.increx("excounter", "UBOUND", "6", "BYINT", "4") == [5, 0]
            assert client.increx("excounter", "UBOUND", "6", "BYINT", "4", "SATURATE") == [6, 1]
            assert client.increx("excounter", "PX", "1500") == [7, 1]
            assert 0 < client.pttl("excounter") <= 1500
            assert client.increx("excounter", "ENX", "PX", "3000") == [8, 1]
            assert 0 < client.pttl("excounter") <= 1500
            assert client.increx("excounter", "PERSIST") == [9, 1]
            assert client.pttl("excounter") == -1
            try:
                client.increx("excounter", "BYFLOAT", "1.5")
                raise AssertionError("expected INCREX BYFLOAT to fail in current partial")
            except RespError as exc:
                if "INCREX BYFLOAT is not supported" not in str(exc):
                    raise
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
            assert client.msetex({"me1": "v1", "me2": "v2"}, "PX", "1500") == 1
            assert client.mget("me1", "me2") == [b"v1", b"v2"]
            assert 0 < client.pttl("me1") <= 1500
            assert client.msetex({"me1": "x", "me3": "v3"}, "NX") == 0
            assert client.get("me3") is None
            assert client.msetex({"me1": "x", "me2": "y"}, "XX") == 1
            assert client.mget("me1", "me2") == [b"x", b"y"]
            assert client.mset({"lcs-a": "ohmytext", "lcs-b": "mynewtext"})
            assert client.lcs("lcs-a", "lcs-b") == b"mytext"
            assert client.lcs("lcs-a", "lcs-b", "LEN") == 6
            assert client.strlen("key") == 5
            assert client.append("key", "++") == 7
            assert client.getrange("key", 1, 3) == b"alu"
            assert client.substr("key", 1, 3) == b"alu"
            assert client.set("digest-key", "Hello world")
            assert client.digest("digest-key") == b"b6acb9d84a38ff74"
            assert client.digest("missing") is None
            assert client.delete("digest-key") == 1
            assert client.getbit("missing", 0) == 0
            assert client.getbit("key", 0) == 0
            assert client.setbit("key", 1, 1) == 1
            assert client.bitcount("key") == 29
            assert client.bitcount("key", "0", "0") == 5
            assert client.bitcount("key", "0", "7", "BIT") == 5
            assert client.bitpos("missing", 0) == 0
            assert client.bitpos("missing", 1) == -1
            assert client.bitpos("key", 0) == 0
            assert client.bitpos("key", 1) == 1
            assert client.setbit("allones", 0, 1) == 0
            assert client.setbit("allones", 1, 1) == 0
            assert client.setbit("allones", 2, 1) == 0
            assert client.setbit("allones", 3, 1) == 0
            assert client.setbit("allones", 4, 1) == 0
            assert client.setbit("allones", 5, 1) == 0
            assert client.setbit("allones", 6, 1) == 0
            assert client.setbit("allones", 7, 1) == 0
            assert client.bitpos("allones", 0) == 8
            assert client.bitpos("allones", 0, "0", "0") == -1
            assert client.bitpos("allones", 1, "4", "7", "BIT") == 4
            assert client.set("srca", "foo")
            assert client.set("srcb", "bar")
            assert client.bitop("AND", "dstbit", "srca", "srcb") == 3
            assert client.get("dstbit") == b"bab"
            assert client.bitop("NOT", "dstbit", "srca") == 3
            assert client.bitcount("dstbit") == 8
            assert client.set("dropbit", "x")
            assert client.bitop("AND", "dropbit", "missing") == 0
            assert client.get("dropbit") is None
            assert client.bitfield("bf", "SET", "u8", "0", "5") == [0]
            assert client.bitfield("bf", "GET", "u8", "0") == [5]
            assert client.bitfield("bf", "INCRBY", "u8", "0", "3") == [8]
            assert client.bitfield("bf", "OVERFLOW", "FAIL", "INCRBY", "u8", "0", "300", "GET", "u8", "0") == [None, 8]
            assert client.bitfield("bf", "SET", "u8", "#1", "7") == [0]
            assert client.bitfield("bf", "GET", "u8", "8") == [7]
            assert client.bitfield("bf", "SET", "i8", "0", "-1") == [8]
            assert client.bitfield("bf", "GET", "i8", "0") == [-1]
            assert client.bitfield_ro("bf", "GET", "u8", "0") == [255]
            assert client.pfadd("hll", "a", "b", "c") == 1
            assert client.pfcount("hll") == 3
            assert client.pfadd("hll", "a", "b") == 0
            assert client.pfcount("hll", "missing") == 3
            assert client.pfmerge("dsthll", "hll", "missing")
            assert client.pfcount("dsthll") == 3
            assert client.pfadd("emptyhll") == 1
            assert client.pfcount("emptyhll") == 0
            assert client.pfselftest()
            try:
                client.pfdebug(b"GETREG", "hll")
                raise AssertionError("expected PFDEBUG to fail")
            except RespError as exc:
                if str(exc) != "ERR PFDEBUG command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected PFDEBUG error: {exc}") from exc
            assert client.geoadd("geo", "13.361389", "38.115556", "Palermo", "15.087269", "37.502669", "Catania") == 2
            assert client.geodist("geo", "Palermo", "Catania", "km") == b"166.2742"
            assert client.geopos("geo", "Palermo", "Missing", "Catania") == [[b"13.361389", b"38.115555"], None, [b"15.087268", b"37.502668"]]
            assert client.geohash("geo", "Palermo", "Missing", "Catania") == [b"sqc8b49rny0", None, b"sqdtr74hyu0"]
            assert client.geosearch("geo", "FROMLONLAT", "15", "37", "BYRADIUS", "200", "km") == [b"Palermo", b"Catania"]
            assert client.geosearchstore("geodst", "geo", "FROMLONLAT", "15", "37", "BYRADIUS", "200", "km") == 2
            assert client.zrange("geodst", 0, -1) == [b"Palermo", b"Catania"]
            assert client.geosearchstore("distdst", "geo", "FROMMEMBER", "Palermo", "BYRADIUS", "200", "km", "STOREDIST") == 2
            assert client.zscore("distdst", "Catania") == b"166"
            assert client.georadius("geo", "15", "37", "200", "km") == [b"Palermo", b"Catania"]
            assert client.georadius_ro("geo", "15", "37", "200", "km") == [b"Palermo", b"Catania"]
            assert client.georadiusbymember("geo", "Palermo", "200", "km") == [b"Palermo", b"Catania"]
            assert client.georadiusbymember_ro("geo", "Palermo", "200", "km") == [b"Palermo", b"Catania"]
            assert client.geosearch("geo", "FROMMEMBER", "Palermo", "BYRADIUS", "200", "km", "WITHDIST") == [[b"Palermo", b"0.0000"], [b"Catania", b"166.2742"]]
            assert client.eval("return redis.call('SET', KEYS[1], ARGV[1])", 1, "lua-key", "value") == "OK"
            assert client.script_exists("d8f2fad9f8e86a53d2a6ebd960b33c4972cacc37") == [1]
            assert client.script_debug(b"YES") == "OK"
            assert client.script_debug(b"SYNC") == "OK"
            assert client.script_debug(b"NO") == "OK"
            assert client.script_load("return redis.call('GET', KEYS[1])") == b"d3c21d0c2b9ca22f82737626a27bcaf5d288f99f"
            assert client.evalsha("D3C21D0C2B9CA22F82737626A27BCAF5D288F99F", 1, "lua-key") == b"value"
            assert client.eval_ro("return redis.call('GET', KEYS[1])", 1, "lua-key") == b"value"
            try:
                client.eval_ro("return redis.call('SET', KEYS[1], ARGV[1])", 1, "lua-key", "blocked")
                raise AssertionError("expected EVAL_RO write script to fail")
            except RespError as exc:
                if str(exc) != "ERR Write commands are not allowed from read-only scripts":
                    raise AssertionError(f"unexpected EVAL_RO write error: {exc}") from exc
            assert client.evalsha_ro("D3C21D0C2B9CA22F82737626A27BCAF5D288F99F", 1, "lua-key") == b"value"
            assert client.script_flush()
            try:
                client.script_kill()
                raise AssertionError("expected SCRIPT KILL with no running script to fail")
            except RespError as exc:
                if str(exc) != "NOTBUSY No scripts in execution right now.":
                    raise AssertionError(f"unexpected SCRIPT KILL error: {exc}") from exc
            try:
                client.evalsha("d3c21d0c2b9ca22f82737626a27bcaf5d288f99f", 1, "lua-key")
                raise AssertionError("expected EVALSHA after SCRIPT FLUSH to fail")
            except RespError as exc:
                if str(exc) != "NOSCRIPT No matching script. Please use EVAL.":
                    raise AssertionError(f"unexpected EVALSHA error: {exc}") from exc
            try:
                client.evalsha_ro("d3c21d0c2b9ca22f82737626a27bcaf5d288f99f", 1, "lua-key")
                raise AssertionError("expected EVALSHA_RO after SCRIPT FLUSH to fail")
            except RespError as exc:
                if str(exc) != "NOSCRIPT No matching script. Please use EVAL.":
                    raise AssertionError(f"unexpected EVALSHA_RO error: {exc}") from exc
            try:
                client.fcall(b"missing", 0)
                raise AssertionError("expected FCALL missing function to fail")
            except RespError as exc:
                if str(exc) != "ERR Function not found":
                    raise AssertionError(f"unexpected FCALL error: {exc}") from exc
            try:
                client.fcall_ro(b"missing", 0)
                raise AssertionError("expected FCALL_RO missing function to fail")
            except RespError as exc:
                if str(exc) != "ERR Function not found":
                    raise AssertionError(f"unexpected FCALL_RO error: {exc}") from exc
            acl_help = client.acl_help()
            if b"ACL <subcommand> [<arg> [value] [opt] ...]. Subcommands are:" not in acl_help or b"WHOAMI" not in acl_help:
                raise AssertionError(f"unexpected ACL HELP result: {acl_help!r}")
            acl_cat = client.acl_cat()
            if b"string" not in acl_cat or b"transaction" not in acl_cat:
                raise AssertionError(f"unexpected ACL CAT result: {acl_cat!r}")
            acl_cat_string = client.acl_cat(b"string")
            if b"get" not in acl_cat_string or b"set" not in acl_cat_string:
                raise AssertionError(f"unexpected ACL CAT string result: {acl_cat_string!r}")
            acl_getuser = client.acl_getuser(b"default")
            if not isinstance(acl_getuser, list) or acl_getuser[0] != b"flags" or acl_getuser[1] != [b"on", b"nopass"] or b"+@all" not in acl_getuser:
                raise AssertionError(f"unexpected ACL GETUSER default result: {acl_getuser!r}")
            if client.acl_getuser(b"missing") is not None:
                raise AssertionError("expected ACL GETUSER missing user to return null")
            if client.acl_log() != [] or client.acl_log(b"10") != []:
                raise AssertionError("expected ACL LOG empty result")
            if client.acl_log(b"RESET") != "OK":
                raise AssertionError("expected ACL LOG RESET OK")
            acl_genpass = client.acl_genpass()
            if len(acl_genpass) != 64 or any(ch not in b"0123456789abcdef" for ch in acl_genpass):
                raise AssertionError(f"unexpected ACL GENPASS result: {acl_genpass!r}")
            acl_genpass_bits = client.acl_genpass(b"8")
            if len(acl_genpass_bits) != 2 or any(ch not in b"0123456789abcdef" for ch in acl_genpass_bits):
                raise AssertionError(f"unexpected ACL GENPASS bits result: {acl_genpass_bits!r}")
            try:
                client.acl_save()
                raise AssertionError("expected ACL SAVE to fail without aclfile")
            except RespError as exc:
                if "not configured to use an ACL file" not in str(exc):
                    raise AssertionError(f"unexpected ACL SAVE error: {exc}") from exc
            try:
                client.acl_load()
                raise AssertionError("expected ACL LOAD to fail without aclfile")
            except RespError as exc:
                if "not configured to use an ACL file" not in str(exc):
                    raise AssertionError(f"unexpected ACL LOAD error: {exc}") from exc
            if client.acl_deluser(b"missing") != 0:
                raise AssertionError("expected ACL DELUSER missing to return 0")
            try:
                client.acl_deluser(b"default")
                raise AssertionError("expected ACL DELUSER default to fail")
            except RespError as exc:
                if str(exc) != "ERR The 'default' user cannot be removed":
                    raise AssertionError(f"unexpected ACL DELUSER default error: {exc}") from exc
            if client.acl_dryrun(b"default", b"GET", b"missing") != "OK":
                raise AssertionError("expected ACL DRYRUN default GET to return OK")
            try:
                client.acl_dryrun(b"missing", b"GET", b"k")
                raise AssertionError("expected ACL DRYRUN missing user to fail")
            except RespError as exc:
                if str(exc) != "ERR User 'missing' not found":
                    raise AssertionError(f"unexpected ACL DRYRUN missing user error: {exc}") from exc
            if client.acl_setuser(b"default", b"on", b"nopass", b"~*", b"&*", b"+@all") != "OK":
                raise AssertionError("expected ACL SETUSER default no-op modifiers to return OK")
            if client.acl_setuser(b"default", b"resetkeys", b"resetchannels") != "OK":
                raise AssertionError("expected ACL SETUSER default resetkeys/resetchannels to return OK")
            if client.acl_list() != [b"user default on nopass ~* &* +@all"]:
                raise AssertionError("expected ACL SETUSER resetkeys/resetchannels no-op to keep default user view")
            if client.acl_setuser(b"default", b"clearselectors", b"resetselectors") != "OK":
                raise AssertionError("expected ACL SETUSER default clearselectors/resetselectors to return OK")
            if client.acl_setuser(b"default", b"-get") != "OK":
                raise AssertionError("expected ACL SETUSER default -get to return OK")
            denied_acl_list = client.acl_list()
            if not denied_acl_list or b"+@all -get" not in denied_acl_list[0]:
                raise AssertionError(f"expected ACL LIST to include denied get command, got {denied_acl_list!r}")
            denied_acl_getuser = client.acl_getuser(b"default")
            if not isinstance(denied_acl_getuser, list) or b"+@all -get" not in denied_acl_getuser:
                raise AssertionError(f"expected ACL GETUSER to include denied get command, got {denied_acl_getuser!r}")
            try:
                client.acl_dryrun(b"default", b"GET", b"missing")
                raise AssertionError("expected ACL DRYRUN denied GET to fail")
            except RespError as exc:
                if str(exc) != "NOPERM User default has no permissions to run the 'get' command":
                    raise AssertionError(f"unexpected ACL DRYRUN denied GET error: {exc}") from exc
            try:
                client.get("missing")
                raise AssertionError("expected ACL denied GET to fail")
            except RespError as exc:
                if str(exc) != "NOPERM User default has no permissions to run the 'get' command":
                    raise AssertionError(f"unexpected ACL denied GET error: {exc}") from exc
            acl_log_one = client.acl_log(b"1")
            acl_log_client_info = b""
            if len(acl_log_one) == 1 and b"client-info" in acl_log_one[0]:
                info_index = acl_log_one[0].index(b"client-info") + 1
                if info_index < len(acl_log_one[0]) and isinstance(acl_log_one[0][info_index], bytes):
                    acl_log_client_info = acl_log_one[0][info_index]
            if (
                len(acl_log_one) != 1
                or b"context" not in acl_log_one[0]
                or b"command" not in acl_log_one[0]
                or b"object" not in acl_log_one[0]
                or b"get" not in acl_log_one[0]
                or b"username" not in acl_log_one[0]
                or b"default" not in acl_log_one[0]
                or b"entry-id" not in acl_log_one[0]
                or b"timestamp-created" not in acl_log_one[0]
                or b"timestamp-last-updated" not in acl_log_one[0]
                or b"client-info" not in acl_log_one[0]
                or b"id=0" in acl_log_client_info
                or b"addr=unknown" in acl_log_client_info
                or b"laddr=unknown" in acl_log_client_info
                or b"addr=127.0.0.1:" not in acl_log_client_info
                or b"laddr=127.0.0.1:" not in acl_log_client_info
            ):
                raise AssertionError(f"expected ACL LOG to include denied GET command entry, got {acl_log_one!r}")
            acl_log_two = client.acl_log(b"2")
            if len(acl_log_two) != 2 or b"dryrun" not in acl_log_two[1]:
                raise AssertionError(f"expected ACL LOG count to include dryrun entry, got {acl_log_two!r}")
            if client.acl_log(b"RESET") != "OK" or client.acl_log() != []:
                raise AssertionError("expected ACL LOG RESET to clear denied entries")
            if client.acl_setuser(b"default", b"+get") != "OK":
                raise AssertionError("expected ACL SETUSER default +get to return OK")
            if client.acl_dryrun(b"default", b"GET", b"missing") != "OK":
                raise AssertionError("expected ACL DRYRUN default GET to recover after +get")
            if client.get("missing") is not None:
                raise AssertionError("expected GET missing to recover after ACL +get")
            if client.acl_setuser(b"default", b"-@string") != "OK":
                raise AssertionError("expected ACL SETUSER default -@string to return OK")
            category_acl_list = client.acl_list()
            if not category_acl_list or b"-@string" not in category_acl_list[0]:
                raise AssertionError(f"expected ACL LIST to include denied string category, got {category_acl_list!r}")
            try:
                client.get("missing")
                raise AssertionError("expected ACL denied GET through -@string to fail")
            except RespError as exc:
                if str(exc) != "NOPERM User default has no permissions to run the 'get' command":
                    raise AssertionError(f"unexpected ACL category denied GET error: {exc}") from exc
            if client.acl_setuser(b"default", b"-get") != "OK":
                raise AssertionError("expected ACL SETUSER default -get after -@string to return OK")
            if client.acl_setuser(b"default", b"resetcommands") != "OK":
                raise AssertionError("expected ACL SETUSER default resetcommands to return OK")
            reset_acl_list = client.acl_list()
            if reset_acl_list != [b"user default on nopass ~* &* +@all"]:
                raise AssertionError(f"expected ACL LIST to reset command rules, got {reset_acl_list!r}")
            if client.get("missing") is not None:
                raise AssertionError("expected GET missing to recover after ACL resetcommands")
            try:
                client.acl_setuser(b"default", b"invalidattr")
                raise AssertionError("expected ACL SETUSER invalid modifier to fail")
            except RespError as exc:
                if str(exc) != "ERR Error in ACL SETUSER modifier 'invalidattr': Syntax error":
                    raise AssertionError(f"unexpected ACL SETUSER invalid modifier error: {exc}") from exc
            if client.acl_whoami() != b"default":
                raise AssertionError("expected ACL WHOAMI default user")
            if client.acl_users() != [b"default"]:
                raise AssertionError("expected ACL USERS default user list")
            if client.acl_list() != [b"user default on nopass ~* &* +@all"]:
                raise AssertionError("expected ACL LIST default user config")
            function_help = client.function_help()
            if (
                b"FUNCTION HELP" not in function_help
                or b"FUNCTION LIST [LIBRARYNAME <pattern>] [WITHCODE]" not in function_help
                or b"FUNCTION LOAD [REPLACE] <function-code>" not in function_help
                or b"FUNCTION DUMP" not in function_help
                or not any(item.startswith(b"FUNCTION RESTORE") for item in function_help)
                or b"FUNCTION KILL" not in function_help
            ):
                raise AssertionError(f"unexpected FUNCTION HELP result: {function_help!r}")
            if client.function_list() != []:
                raise AssertionError("expected empty FUNCTION LIST partial result")
            function_stats = client.function_stats()
            if (
                b"running_script" not in function_stats
                or b"engines" not in function_stats
                or b"libraries_count" not in function_stats[3][1]
                or b"functions_count" not in function_stats[3][1]
            ):
                raise AssertionError(f"unexpected FUNCTION STATS result: {function_stats!r}")
            if client.function_flush(b"SYNC") != "OK" or client.function_flush(b"ASYNC") != "OK":
                raise AssertionError("expected FUNCTION FLUSH SYNC/ASYNC to return OK")
            try:
                client.function_delete(b"missing")
                raise AssertionError("expected FUNCTION DELETE missing library to fail")
            except RespError as exc:
                if str(exc) != "ERR Library not found":
                    raise AssertionError(f"unexpected FUNCTION DELETE error: {exc}") from exc
            try:
                client.function_load(b"return 1")
                raise AssertionError("expected FUNCTION LOAD to return partial unsupported error")
            except RespError as exc:
                if str(exc) != "ERR FUNCTION LOAD is not supported by redis-uya partial":
                    raise AssertionError(f"unexpected FUNCTION LOAD error: {exc}") from exc
            try:
                client.function_load(b"return 1", replace=True)
                raise AssertionError("expected FUNCTION LOAD REPLACE to return partial unsupported error")
            except RespError as exc:
                if str(exc) != "ERR FUNCTION LOAD is not supported by redis-uya partial":
                    raise AssertionError(f"unexpected FUNCTION LOAD REPLACE error: {exc}") from exc
            empty_function_dump = client.function_dump()
            if empty_function_dump != bytes.fromhex("0a005d9b5c400f7fa2da"):
                raise AssertionError("expected FUNCTION DUMP empty-library payload")
            if client.function_restore(empty_function_dump) != "OK" or client.function_restore(empty_function_dump, b"REPLACE") != "OK":
                raise AssertionError("expected FUNCTION RESTORE empty-library payload to return OK")
            try:
                client.function_restore(b"bad")
                raise AssertionError("expected FUNCTION RESTORE bad payload to fail")
            except RespError as exc:
                if str(exc) != "ERR DUMP payload version or checksum are wrong":
                    raise AssertionError(f"unexpected FUNCTION RESTORE payload error: {exc}") from exc
            try:
                client.function_restore(b"bad", b"BAD")
                raise AssertionError("expected FUNCTION RESTORE bad policy to fail")
            except RespError as exc:
                if str(exc) != "ERR Wrong restore policy given, value should be either FLUSH, APPEND or REPLACE.":
                    raise AssertionError(f"unexpected FUNCTION RESTORE policy error: {exc}") from exc
            try:
                client.function_kill()
                raise AssertionError("expected FUNCTION KILL with no running function to fail")
            except RespError as exc:
                if str(exc) != "NOTBUSY No scripts in execution right now.":
                    raise AssertionError(f"unexpected FUNCTION KILL error: {exc}") from exc
            memory_usage = client.memory_usage("key")
            if memory_usage is None or memory_usage <= 0:
                raise AssertionError(f"unexpected MEMORY USAGE key: {memory_usage!r}")
            if client.memory_usage("missing") is not None:
                raise AssertionError("expected MEMORY USAGE missing to be None")
            memory_usage_samples = client.memory_usage("key", samples=0)
            if memory_usage_samples is None or memory_usage_samples <= 0:
                raise AssertionError(f"unexpected MEMORY USAGE key SAMPLES 0: {memory_usage_samples!r}")
            memory_stats = client.memory_stats()
            if b"used_memory" not in memory_stats or b"maxmemory_policy" not in memory_stats:
                raise AssertionError(f"unexpected MEMORY STATS payload: {memory_stats!r}")
            memory_doctor = client.memory_doctor()
            if b"diagnosis" not in memory_doctor and b"No obvious allocator" not in memory_doctor:
                raise AssertionError(f"unexpected MEMORY DOCTOR payload: {memory_doctor!r}")
            memory_malloc_stats = client.memory_malloc_stats()
            if b"redis-uya allocator stats" not in memory_malloc_stats or b"allocator_slab_cached_bytes" not in memory_malloc_stats:
                raise AssertionError(f"unexpected MEMORY MALLOC-STATS payload: {memory_malloc_stats!r}")
            if client.memory_purge() != "OK":
                raise AssertionError("unexpected MEMORY PURGE result")
            if client.module_list() != []:
                raise AssertionError("unexpected MODULE LIST result")
            try:
                client.module_load(b"redis.so")
                raise AssertionError("expected MODULE LOAD to be disabled")
            except RespError as exc:
                if str(exc) != "ERR MODULE LOAD command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected MODULE LOAD error: {exc}") from exc
            try:
                client.module_loadex(b"redis.so")
                raise AssertionError("expected MODULE LOADEX to be disabled")
            except RespError as exc:
                if str(exc) != "ERR MODULE LOADEX command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected MODULE LOADEX error: {exc}") from exc
            try:
                client.module_unload(b"json")
                raise AssertionError("expected MODULE UNLOAD to be disabled")
            except RespError as exc:
                if str(exc) != "ERR MODULE UNLOAD command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected MODULE UNLOAD error: {exc}") from exc
            try:
                client._request(b"ARCOUNT", b"ar")
                raise AssertionError("expected ARCOUNT to be disabled")
            except RespError as exc:
                if str(exc) != "ERR ARCOUNT command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected ARCOUNT error: {exc}") from exc
            try:
                client._request(b"BF.ADD", b"bf", b"x")
                raise AssertionError("expected BF.ADD to be disabled")
            except RespError as exc:
                if str(exc) != "ERR BF.ADD command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected BF.ADD error: {exc}") from exc
            try:
                client._request(b"CF.ADD", b"cf", b"x")
                raise AssertionError("expected CF.ADD to be disabled")
            except RespError as exc:
                if str(exc) != "ERR CF.ADD command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected CF.ADD error: {exc}") from exc
            try:
                client._request(b"CMS.INCRBY", b"cms", b"x", b"1")
                raise AssertionError("expected CMS.INCRBY to be disabled")
            except RespError as exc:
                if str(exc) != "ERR CMS.INCRBY command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected CMS.INCRBY error: {exc}") from exc
            try:
                client._request(b"TOPK.ADD", b"topk", b"x")
                raise AssertionError("expected TOPK.ADD to be disabled")
            except RespError as exc:
                if str(exc) != "ERR TOPK.ADD command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected TOPK.ADD error: {exc}") from exc
            try:
                client._request(b"TDIGEST.ADD", b"td", b"1")
                raise AssertionError("expected TDIGEST.ADD to be disabled")
            except RespError as exc:
                if str(exc) != "ERR TDIGEST.ADD command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected TDIGEST.ADD error: {exc}") from exc
            try:
                client._request(b"TS.ADD", b"ts", b"*", b"1")
                raise AssertionError("expected TS.ADD to be disabled")
            except RespError as exc:
                if str(exc) != "ERR TS.ADD command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected TS.ADD error: {exc}") from exc
            try:
                client._request(b"MEMORY")
                raise AssertionError("expected MEMORY without subcommand to fail")
            except RespError as exc:
                if str(exc) != "ERR wrong number of arguments":
                    raise AssertionError(f"unexpected MEMORY arity error: {exc}") from exc
            if not client.config_set("slowlog-log-slower-than", "0"):
                raise AssertionError("CONFIG SET slowlog-log-slower-than 0 failed")
            if client.config_get("slowlog-log-slower-than").get("slowlog-log-slower-than") != "0":
                raise AssertionError("CONFIG GET slowlog-log-slower-than did not reflect enabled state")
            assert client.slowlog_reset()
            assert client.set("slow-k", "1")
            assert client.get("slow-k") == b"1"
            if client.slowlog_len() != 2:
                raise AssertionError("expected SLOWLOG LEN 2 after SET/GET")
            slow_entries = client.slowlog_get(1)
            if (
                len(slow_entries) != 1
                or not isinstance(slow_entries[0], list)
                or len(slow_entries[0]) < 4
                or slow_entries[0][3] != [b"GET", b"slow-k"]
            ):
                raise AssertionError(f"unexpected SLOWLOG GET payload: {slow_entries!r}")
            assert client.slowlog_reset()
            if client.slowlog_len() != 0:
                raise AssertionError("expected SLOWLOG LEN 0 after RESET")
            if not client.config_resetstat():
                raise AssertionError("CONFIG RESETSTAT failed before LATENCY checks")
            client.latency_reset()
            if client.latency_latest() != []:
                raise AssertionError("expected empty LATENCY LATEST after RESET")
            if client.latency_history("command") != []:
                raise AssertionError("expected empty LATENCY HISTORY after RESET")
            if not client.config_set("latency-monitor-threshold", "1"):
                raise AssertionError("CONFIG SET latency-monitor-threshold failed before LATENCY checks")
            assert client.set("latency-k", "1")
            latest_latency = client.latency_latest()
            if (
                len(latest_latency) != 1
                or not isinstance(latest_latency[0], list)
                or latest_latency[0][0] != b"command"
            ):
                raise AssertionError(f"unexpected LATENCY LATEST payload: {latest_latency!r}")
            history_latency = client.latency_history("command")
            if len(history_latency) == 0 or not isinstance(history_latency[0], list):
                raise AssertionError(f"unexpected LATENCY HISTORY payload: {history_latency!r}")
            set_histogram = client.latency_histogram("SET")
            if (
                len(set_histogram) != 2
                or set_histogram[0] != b"set"
                or not isinstance(set_histogram[1], list)
                or b"calls" not in set_histogram[1]
                or b"histogram_usec" not in set_histogram[1]
            ):
                raise AssertionError(f"unexpected LATENCY HISTOGRAM SET payload: {set_histogram!r}")
            if client.latency_histogram("missing") != []:
                raise AssertionError("expected empty LATENCY HISTOGRAM missing result")
            if b"recorded command events" not in client.latency_doctor():
                raise AssertionError("expected LATENCY DOCTOR minimal diagnostic")
            if client.latency_reset() != 1:
                raise AssertionError("expected LATENCY RESET 1")
            if not client.config_resetstat():
                raise AssertionError("CONFIG RESETSTAT failed after LATENCY checks")
            if client.latency_histogram("SET") != []:
                raise AssertionError("CONFIG RESETSTAT did not clear SET latency histogram")
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
            assert client.set("delex-key", "value")
            assert client.delex("delex-key", "IFEQ", "other") == 0
            assert client.get("delex-key") == b"value"
            assert client.delex("delex-key", "IFNE", "other") == 1
            assert client.delex("delex-key") == 0
            assert client.delete("counter") == 1
            assert client.delete("excounter", "fcounter", "nx-key", "gs-key", "sx-key", "mk1", "mk2", "mn1", "mn2", "me1", "me2", "lcs-a", "lcs-b", "allones", "srca", "srcb", "dstbit", "bf", "hll", "dsthll", "emptyhll", "geo", "geodst", "distdst", "lua-key", "slow-k", "latency-k") == 27
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
            if not client.swapdb(0, 0):
                raise AssertionError("expected SWAPDB 0 0 to return OK")
            try:
                client.swapdb(0, 1)
                raise AssertionError("expected SWAPDB 0 1 to fail in single-db mode")
            except RespError as exc:
                if str(exc) != "ERR DB index is out of range":
                    raise AssertionError(f"unexpected SWAPDB range error: {exc}") from exc
            try:
                client.swapdb("bad", 0)
                raise AssertionError("expected SWAPDB bad 0 to fail")
            except RespError as exc:
                if str(exc) != "ERR value is not an integer or out of range":
                    raise AssertionError(f"unexpected SWAPDB integer error: {exc}") from exc
            if b"Redis ver. v0.9.1-dev" not in client.lolwut():
                raise AssertionError("expected LOLWUT to include redis-uya version")
            if b"Redis-compatible" not in client.lolwut(b"VERSION", b"5"):
                raise AssertionError("expected LOLWUT VERSION 5 to return compatibility text")
            if b"Redis ver." not in client.lolwut(b"bad", b"5"):
                raise AssertionError("expected LOLWUT unknown option to return default output")
            try:
                client.lolwut(b"VERSION", b"bad")
                raise AssertionError("expected LOLWUT VERSION bad to fail")
            except RespError as exc:
                if str(exc) != "ERR value is not an integer or out of range":
                    raise AssertionError(f"unexpected LOLWUT integer error: {exc}") from exc
            try:
                client.debug(b"HELP")
                raise AssertionError("expected DEBUG HELP to be disabled")
            except RespError as exc:
                if str(exc) != "ERR DEBUG command not allowed by redis-uya standalone profile":
                    raise AssertionError(f"unexpected DEBUG error: {exc}") from exc
            try:
                client.failover()
                raise AssertionError("expected FAILOVER without replicas to fail")
            except RespError as exc:
                if str(exc) != "ERR FAILOVER requires connected replicas.":
                    raise AssertionError(f"unexpected FAILOVER error: {exc}") from exc
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
            if client.waitaof(1, 0, 0) != [1, 0]:
                raise AssertionError("expected WAITAOF 1 0 0 to return [1, 0]")
            if client.waitaof(0, 0, 0) != [0, 0]:
                raise AssertionError("expected WAITAOF 0 0 0 to return [0, 0]")
            if client.waitaof(1, 1, 10) != [1, 0]:
                raise AssertionError("expected WAITAOF 1 1 10 to return [1, 0] without replicas")
            try:
                client.waitaof(1, 0, -1)
                raise AssertionError("expected WAITAOF negative timeout to fail")
            except RespError as exc:
                if str(exc) != "ERR timeout is negative":
                    raise AssertionError(f"unexpected WAITAOF timeout error: {exc}") from exc
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
            assert client.sort_ro("sortnums") == [b"1", b"2", b"3"]
            try:
                client.sort_ro("sortnums", "STORE", "sortout")
            except RespError as exc:
                if "syntax error" not in str(exc):
                    raise AssertionError(f"unexpected SORT_RO STORE error: {exc}") from exc
            else:
                raise AssertionError("expected SORT_RO STORE to fail")
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
            assert client.hrandfield("hash") == b"counter"
            assert client.hrandfield("hash", 2) == [b"counter", b"field"]
            assert client.hrandfield("hash", 2, withvalues=True) == [b"counter", b"2", b"field", b"value"]
            assert client.hrandfield("hash", -4) == [b"counter", b"field", b"ratio", b"counter"]
            assert client.hrandfield("missing") is None
            assert client.hrandfield("missing", 2) == []
            assert client.hexists("hash", "field") == 1
            assert client.hexists("hash", "missing") == 0
            assert client.hlen("hash") == 3
            assert client.hmget("hash", "field", "missing", "counter") == [b"value", None, b"2"]
            assert client.hset("hash", "multi", "one", "second", "two") == 2
            assert client.hmget("hash", "multi", "second") == [b"one", b"two"]
            assert client.hdel("hash", "multi", "second") == 2
            assert client.hmset("hash", "multi", "one", "second", "two")
            assert client.hmget("hash", "multi", "second") == [b"one", b"two"]
            assert client.hdel("hash", "multi", "second") == 2
            assert client.hsetnx("hash", "extra", "value") == 1
            assert client.hsetnx("hash", "field", "next") == 0
            assert client.hstrlen("hash", "field") == 5
            assert client.hstrlen("hash", "missing") == 0
            assert client.hgetex("hash", "field", "missing") == [b"value", None]
            assert client.hgetex("hash", "field", "missing", option=b"EX", value=b"10") == [b"value", None]
            assert client.hget("hash", "field") == b"value"
            assert client.hsetex("hash", "fresh", "one", option=b"EX", option_value=b"10") == 1
            assert client.hget("hash", "fresh") == b"one"
            assert client.hexpire("hash", 10, "field", "missing") == [1, -2]
            assert client.hexpire("hash", 10, "field", option=b"XX") == [0]
            assert client.hexpire("hash", 0, "fresh", option=b"NX") == [2]
            assert client.hget("hash", "fresh") is None
            assert client.hset("hash", "freshms", "one") == 1
            assert client.hpexpire("hash", 100, "field", "missing") == [1, -2]
            assert client.hpexpire("hash", 100, "field", option=b"XX") == [0]
            assert client.hpexpire("hash", 0, "freshms", option=b"NX") == [2]
            assert client.hget("hash", "freshms") is None
            assert client.hset("hash", "freshat", "one") == 1
            future_seconds = int(time.time()) + 60
            assert client.hexpireat("hash", future_seconds, "field", "missing") == [1, -2]
            assert client.hexpireat("hash", future_seconds, "field", option=b"XX") == [0]
            assert client.hexpireat("hash", 1, "freshat", option=b"NX") == [2]
            assert client.hget("hash", "freshat") is None
            assert client.hset("hash", "freshpm", "one") == 1
            future_milliseconds = int(time.time() * 1000) + 60000
            assert client.hpexpireat("hash", future_milliseconds, "field", "missing") == [1, -2]
            assert client.hpexpireat("hash", future_milliseconds, "field", option=b"XX") == [0]
            assert client.hpexpireat("hash", 1, "freshpm", option=b"NX") == [2]
            assert client.hget("hash", "freshpm") is None
            assert client.httl("hash", "field", "missing") == [-1, -2]
            assert client.hpttl("hash", "field", "missing") == [-1, -2]
            assert client.hexpiretime("hash", "field") == [-1]
            assert client.hpexpiretime("hash", "field") == [-1]
            assert client.hpersist("hash", "field", "missing") == [-1, -2]
            assert client.httl("missing", "field") == [-2]
            assert client.hgetdel("hash", "field", "missing") == [b"value", None]
            assert client.hget("hash", "field") is None
            assert client.hdel("hash", "field", "counter", "extra") == 2
            assert client.hlen("hash") == 1
            cursor, hscan_items = client.hscan("hash", 0, count=16)
            if cursor != 0 or len(hscan_items) != 2:
                raise AssertionError(f"unexpected hscan result: cursor={cursor} items={hscan_items!r}")

            assert client.lpush("list", "a", "b", "c") == 3
            assert client.lrange("list", 0, -1) == [b"c", b"b", b"a"]
            assert client.lpop("list") == b"c"
            assert client.lpush("countlist", "a", "b", "c") == 3
            assert client.lpop("countlist", 3) == [b"c", b"b", b"a"]
            assert client.rpush("rlist", "a", "b", "c") == 3
            assert client.llen("rlist") == 3
            assert client.lindex("rlist", 0) == b"a"
            assert client.lindex("rlist", -1) == b"c"
            assert client.lset("rlist", 1, "mid")
            assert client.lrange("rlist", 0, -1) == [b"a", b"mid", b"c"]
            assert client.rpop("rlist") == b"c"
            assert client.llen("rlist") == 2
            assert client.rpop("rlist", 2) == [b"mid", b"a"]
            assert client.delete("rlist") == 0
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
            assert client.rpush("src", "a", "b", "c") == 3
            assert client.rpoplpush("src", "dst") == b"c"
            assert client.lmove("src", "dst", "LEFT", "RIGHT") == b"a"
            assert client.lmove("dst", "dst", "RIGHT", "LEFT") == b"a"
            assert client.blmove("src", "dst", "RIGHT", "RIGHT", 1) == b"b"
            assert client.lrange("src", 0, -1) == []
            assert client.lrange("dst", 0, -1) == [b"a", b"c", b"b"]
            assert client.delete("src", "dst") == 1
            assert client.rpush("lmpop", "a", "b", "c") == 3
            assert client.lmpop("LEFT", "missing", "lmpop", count=2) == [b"lmpop", [b"a", b"b"]]
            assert client.lmpop("RIGHT", "lmpop") == [b"lmpop", [b"c"]]
            assert client.lmpop("LEFT", "lmpop") is None
            assert client.rpush("blmpop", "a", "b", "c") == 3
            assert client.blmpop(1, "LEFT", "missing", "blmpop", count=2) == [b"blmpop", [b"a", b"b"]]
            assert client.blmpop(1, "RIGHT", "blmpop") == [b"blmpop", [b"c"]]
            assert client.blmpop(0.1, "LEFT", "blmpop") is None

            assert client.sadd("set", "a", "b") == 2
            assert client.smembers("set") == {b"a", b"b"}
            assert client.scard("set") == 2
            assert client.sismember("set", "a") == 1
            assert client.sismember("set", "z") == 0
            if client.smismember("set", "a", "z", "b") != [1, 0, 1]:
                raise AssertionError("unexpected smismember result")
            cursor, sscan_items = client.sscan("set", 0, count=16)
            if cursor != 0 or sscan_items != [b"a", b"b"]:
                raise AssertionError(f"unexpected sscan result: cursor={cursor} items={sscan_items!r}")
            assert client.smove("set", "set", "a") == 1
            assert client.smove("set", "move", "b") == 1
            assert client.smembers("move") == {b"b"}
            assert client.scard("set") == 1
            assert client.delete("move") == 1
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
            assert client.sintercard("s1", "s2", "s3") == 1
            assert client.sintercard("s1", "s2", "s3", limit=1) == 1
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
            assert client.zadd("lex", {"alpha": 0, "beta": 0, "charlie": 0, "delta": 0}) == 4
            assert client.zlexcount("lex", "[alpha", "[charlie") == 3
            assert client.zlexcount("lex", "(alpha", "[delta") == 3
            assert client.zlexcount("lex", "-", "+") == 4
            assert client.zlexcount("missing", "-", "+") == 0
            assert client.zrangebylex("lex", "[alpha", "[charlie") == [b"alpha", b"beta", b"charlie"]
            assert client.zrangebylex("lex", "-", "+", offset=1, count=2) == [b"beta", b"charlie"]
            assert client.zrangebylex("lex", "(beta", "+", offset=0, count=-1) == [b"charlie", b"delta"]
            assert client.zrange("lex", "[alpha", "[charlie", bylex=True) == [b"alpha", b"beta", b"charlie"]
            assert client.zrange("lex", "-", "+", bylex=True, limit_start=1, limit_num=2) == [b"beta", b"charlie"]
            assert client.zrange("lex", "[delta", "(alpha", bylex=True, rev=True) == [b"delta", b"charlie", b"beta"]
            assert client.zrangestore("zlexstore", "lex", "[alpha", "[charlie", bylex=True) == 3
            assert client.zrange("zlexstore", 0, -1) == [b"alpha", b"beta", b"charlie"]
            assert client.zscore("zlexstore", "charlie") == b"0"
            assert client.zrangestore("zlexstorerev", "lex", "[delta", "(alpha", bylex=True, rev=True, limit_start=1, limit_num=1) == 1
            assert client.zrange("zlexstorerev", 0, -1) == [b"charlie"]
            assert client.delete("zlexstore", "zlexstorerev") == 2
            assert client.zrevrangebylex("lex", "[delta", "(alpha") == [b"delta", b"charlie", b"beta"]
            assert client.zrevrangebylex("lex", "+", "-", offset=1, count=2) == [b"charlie", b"beta"]
            assert client.zrevrangebylex("lex", "[charlie", "-", offset=0, count=-1) == [b"charlie", b"beta", b"alpha"]
            assert client.zremrangebylex("lex", "[alpha", "[charlie") == 3
            assert client.zrangebylex("lex", "-", "+") == [b"delta"]
            assert client.zremrangebylex("lex", "-", "+") == 1
            assert client.zcard("lex") == 0
            assert client.zremrangebylex("missing", "-", "+") == 0
            assert client.delete("lex") == 0
            assert client.zincrby("zset", 3, "a") == b"4"
            assert client.zcount("zset", 4, 4) == 1
            assert client.zrank("zset", "b") == 0
            assert client.zrank("zset", "b", withscore=True) == (0, b"2")
            assert client.zrevrank("zset", "a") == 0
            assert client.zrevrank("zset", "a", withscore=True) == (0, b"4")
            assert client.zrank("zset", "missing") is None
            assert client.zscore("zset", "a") == b"4"
            assert client.zscore("zset", "missing") is None
            assert client.zmscore("zset", "a", "missing", "b") == [b"4", None, b"2"]
            assert client.zrandmember("zset") == b"b"
            assert client.zrandmember("zset", 2) == [b"b", b"a"]
            assert client.zrandmember("zset", 2, withscores=True) == [b"b", b"2", b"a", b"4"]
            assert client.zrandmember("zset", -3) == [b"b", b"a", b"b"]
            assert client.zadd("zdiff2", {"b": 2, "d": 5}) == 2
            assert client.zintercard("zset", "zdiff2") == 1
            assert client.zintercard("zset", "zdiff2", limit=1) == 1
            assert client.zinter("zset", "zdiff2") == [b"b"]
            assert client.zinter("zset", "zdiff2", withscores=True) == [b"b", b"4"]
            assert client.zinter("zset", "zdiff2", withscores=True, weights=[2, 3], aggregate="MAX") == [b"b", b"6"]
            assert client.zinter("zset", "missing") == []
            assert client.zinterstore("zinterdst", "zset", "zdiff2") == 1
            assert client.zrange("zinterdst", 0, -1) == [b"b"]
            assert client.zscore("zinterdst", "b") == b"4"
            assert client.zinterstore("zinterdst", "zset", "zdiff2", weights=[5, 2], aggregate="MIN") == 1
            assert client.zscore("zinterdst", "b") == b"4"
            assert client.zinterstore("zinterdst", "zset", "missing") == 0
            assert client.zrange("zinterdst", 0, -1) == []
            assert client.zrangestore("zrangestoredst", "zset", 0, 1) == 2
            assert client.zrange("zrangestoredst", 0, -1) == [b"b", b"a"]
            assert client.zscore("zrangestoredst", "a") == b"4"
            assert client.zrangestore("zrangestorerev", "zset", 0, 1, rev=True) == 2
            assert client.zrange("zrangestorerev", 0, -1) == [b"b", b"a"]
            assert client.zrangestore("zrangestorescore", "zset", 2, 4, byscore=True) == 2
            assert client.zrange("zrangestorescore", 0, -1) == [b"b", b"a"]
            assert client.zscore("zrangestorescore", "a") == b"4"
            assert client.zrangestore("zrangestorescorerev", "zset", 4, 2, byscore=True, rev=True, limit_start=1, limit_num=1) == 1
            assert client.zrange("zrangestorescorerev", 0, -1) == [b"b"]
            assert client.zrangestore("zrangestoredst", "missing", 0, -1) == 0
            assert client.zrange("zrangestoredst", 0, -1) == []
            assert client.delete("zrangestorerev", "zrangestorescore", "zrangestorescorerev") == 3
            assert client.zunion("zset", "zdiff2") == [b"a", b"b", b"d"]
            assert client.zunion("zset", "zdiff2", withscores=True) == [b"a", b"4", b"b", b"4", b"d", b"5"]
            assert client.zunion("zset", "zdiff2", withscores=True, weights=[4, 1], aggregate="MIN") == [b"b", b"2", b"d", b"5", b"a", b"16"]
            assert client.zunion("missing", "zdiff2") == [b"b", b"d"]
            assert client.zunionstore("zuniondst", "zset", "zdiff2") == 3
            assert client.zrange("zuniondst", 0, -1) == [b"a", b"b", b"d"]
            assert client.zscore("zuniondst", "b") == b"4"
            assert client.zunionstore("zuniondst", "zset", "zdiff2", weights=[2, 3], aggregate="MAX") == 3
            assert client.zscore("zuniondst", "b") == b"6"
            assert client.zunionstore("zuniondst", "missing") == 0
            assert client.zrange("zuniondst", 0, -1) == []
            assert client.zdiff("zset", "zdiff2") == [b"a"]
            assert client.zdiff("zset", "zdiff2", withscores=True) == [b"a", b"4"]
            assert client.zdiffstore("zdiffdst", "zset", "zdiff2") == 1
            assert client.zrange("zdiffdst", 0, -1) == [b"a"]
            assert client.zscore("zdiffdst", "a") == b"4"
            assert client.zdiffstore("zdiffdst", "missing", "zdiff2") == 0
            assert client.zrange("zdiffdst", 0, -1) == []
            assert client.delete("zdiff2") == 1
            assert client.zrange("zset", 0, -1) == [b"b", b"a"]
            assert client.zrange("zset", 0, 1, withscores=True) == [b"b", b"2", b"a", b"4"]
            assert client.zrange("zset", 0, -1, rev=True) == [b"a", b"b"]
            assert client.zrange("zset", 0, 1, withscores=True, rev=True) == [b"a", b"4", b"b", b"2"]
            assert client.zrange("zset", 2, 4, byscore=True) == [b"b", b"a"]
            assert client.zrange("zset", 4, 2, byscore=True, withscores=True, rev=True) == [b"a", b"4", b"b", b"2"]
            assert client.zrange("zset", 2, 4, byscore=True, withscores=True, limit_start=1, limit_num=1) == [b"a", b"4"]
            assert client.zrevrange("zset", 0, -1) == [b"a", b"b"]
            assert client.zrevrange("zset", 0, 1, withscores=True) == [b"a", b"4", b"b", b"2"]
            assert client.zrangebyscore("zset", 2, 4) == [b"b", b"a"]
            assert client.zrangebyscore("zset", 2, 4, withscores=True) == [b"b", b"2", b"a", b"4"]
            assert client.zrangebyscore("zset", 2, 4, start=1, num=1) == [b"a"]
            assert client.zrangebyscore("zset", 2, 4, withscores=True, start=1, num=1) == [b"a", b"4"]
            assert client.zrevrangebyscore("zset", 4, 2) == [b"a", b"b"]
            assert client.zrevrangebyscore("zset", 4, 2, withscores=True) == [b"a", b"4", b"b", b"2"]
            assert client.zrevrangebyscore("zset", 4, 2, start=1, num=1) == [b"b"]
            assert client.zrevrangebyscore("zset", 4, 2, withscores=True, start=1, num=1) == [b"b", b"2"]
            assert client.zrem("zset", "a") == 1
            assert client.zadd("zmset", {"b": 2, "a": 1, "c": 3}) == 3
            assert client.zmpop("MIN", "missing", "zmset", count=2) == [b"zmset", [[b"a", b"1"], [b"b", b"2"]]]
            assert client.zmpop("MAX", "zmset") == [b"zmset", [[b"c", b"3"]]]
            assert client.zmpop("MIN", "zmset") is None
            assert client.zadd("bzset", {"b": 2, "a": 1, "c": 3}) == 3
            assert client._request(b"BZMPOP", b"1", b"2", b"missing", b"bzset", b"MIN", b"COUNT", b"2") == [b"bzset", [[b"a", b"1"], [b"b", b"2"]]]
            assert client._request(b"BZMPOP", b"1", b"1", b"bzset", b"MAX") == [b"bzset", [[b"c", b"3"]]]
            assert client.zadd("zwork", {"b": 2, "a": 1, "c": 3}) == 3
            cursor, zscan_items = client.zscan("zwork", 0, count=16)
            if cursor != 0 or zscan_items != [b"a", b"1", b"b", b"2", b"c", b"3"]:
                raise AssertionError(f"unexpected zscan result: cursor={cursor} items={zscan_items!r}")
            assert client.zpopmin("zwork", 2) == [b"a", b"1", b"b", b"2"]
            assert client.zscore("zwork", "c") == b"3"
            assert client.zpopmax("zwork") == [b"c", b"3"]
            assert client.zremrangebyrank("zwork", 0, 1) == 0
            assert client.zrange("zwork", 0, -1) == []
            assert client.zremrangebyscore("zwork", 3, 3) == 0
            assert client.zcard("zwork") == 0
            assert client.delete("zwork") == 0

            assert client.set("touchme", "value")
            assert client.touch("touchme", "missing") == 1
            assert client.unlink("missing", "touchme") == 1
            assert client.exists("touchme") == 0

            keys_all = client.keys("*")
            if keys_all != [b"hash", b"key", b"list", b"set", b"zset"]:
                raise AssertionError(f"unexpected KEYS * result: {keys_all!r}")
            keys_k = client.keys("k*")
            if keys_k != [b"key"]:
                raise AssertionError(f"unexpected KEYS k* result: {keys_k!r}")

            cursor, keys = client.scan(0, count=16)
            if cursor != 0:
                raise AssertionError(f"expected final scan cursor 0, got {cursor}")
            expected_keys = {b"hash", b"key", b"list", b"set", b"zset"}
            if set(keys) != expected_keys:
                raise AssertionError(f"unexpected scan keys: {keys!r}")

            info = client.info("server")
            if info.get("redis_uya_version") != REDIS_UYA_VERSION:
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
            assert client.restore_asking("dump-asking", 0, dump_payload)
            assert client.get("dump-asking") == b"value"
            dump_pttl = client.pttl("dump-dst")
            if dump_pttl <= 0 or dump_pttl > 1500:
                raise AssertionError(f"unexpected dump restore pttl: {dump_pttl}")
            assert client.delete("dump-src", "dump-dst", "dump-asking") == 3

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
            auth_acl_getuser = auth_client.acl_getuser(b"default")
            if (
                not isinstance(auth_acl_getuser, list)
                or len(auth_acl_getuser) < 4
                or auth_acl_getuser[0] != b"flags"
                or auth_acl_getuser[1] != [b"on"]
                or auth_acl_getuser[2] != b"passwords"
                or not isinstance(auth_acl_getuser[3], list)
                or len(auth_acl_getuser[3]) != 1
                or not auth_acl_getuser[3][0].startswith(b"#")
                or b"nopass" in auth_acl_getuser[1]
                or auth_acl_getuser[3][0] == b"secret"
            ):
                raise AssertionError(f"unexpected ACL GETUSER with requirepass: {auth_acl_getuser!r}")
            auth_acl_list = auth_client.acl_list()
            if (
                auth_acl_list == []
                or b"#" not in auth_acl_list[0]
                or b"nopass" in auth_acl_list[0]
                or b"secret" in auth_acl_list[0]
            ):
                raise AssertionError(f"unexpected ACL LIST with requirepass: {auth_acl_list!r}")
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
