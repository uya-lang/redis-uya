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


def connect_with_retry(port: int, deadline: float) -> socket.socket:
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            sock.settimeout(2.0)
            return sock
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"failed to connect to redis-uya on port {port}: {last_error}")


def read_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed while reading line")
        chunks.append(chunk)
        if len(chunks) >= 2 and chunks[-2] == b"\r" and chunks[-1] == b"\n":
            return b"".join(chunks[:-2])


def read_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("connection closed while reading payload")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_resp(sock: socket.socket):
    prefix = read_exact(sock, 1)
    if prefix == b"+":
        return read_line(sock).decode()
    if prefix == b"-":
        raise RespError(read_line(sock).decode())
    if prefix == b":":
        return int(read_line(sock))
    if prefix == b"_":
        line = read_line(sock)
        if line != b"":
            raise RuntimeError(f"invalid RESP3 null suffix: {line!r}")
        return None
    if prefix == b"$":
        length = int(read_line(sock))
        if length < 0:
            return None
        data = read_exact(sock, length)
        if read_exact(sock, 2) != b"\r\n":
            raise RuntimeError("invalid bulk terminator")
        return data
    if prefix == b"*":
        count = int(read_line(sock))
        if count < 0:
            return None
        return [read_resp(sock) for _ in range(count)]
    if prefix == b"%":
        count = int(read_line(sock))
        result = {}
        for _ in range(count):
            key = read_resp(sock)
            result[key] = read_resp(sock)
        return result
    if prefix == b">":
        count = int(read_line(sock))
        return [read_resp(sock) for _ in range(count)]
    raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")


def send_command(sock: socket.socket, *parts: bytes):
    request = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        request.append(f"${len(part)}\r\n".encode())
        request.append(part)
        request.append(b"\r\n")
    sock.sendall(b"".join(request))
    return read_resp(sock)


def send_only(sock: socket.socket, *parts: bytes) -> None:
    request = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        request.append(f"${len(part)}\r\n".encode())
        request.append(part)
        request.append(b"\r\n")
    sock.sendall(b"".join(request))


def send_command_expect_no_reply(sock: socket.socket, *parts: bytes) -> None:
    request = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        request.append(f"${len(part)}\r\n".encode())
        request.append(part)
        request.append(b"\r\n")
    sock.sendall(b"".join(request))
    previous_timeout = sock.gettimeout()
    try:
        sock.settimeout(0.1)
        try:
            unexpected = read_resp(sock)
        except TimeoutError:
            return
        except socket.timeout:
            return
        raise AssertionError(f"expected no reply, got {unexpected!r}")
    finally:
        sock.settimeout(previous_timeout)


def array_pairs_to_dict(raw: list[bytes]) -> dict[str, str]:
    result: dict[str, str] = {}
    i = 0
    while i + 1 < len(raw):
        result[raw[i].decode()] = raw[i + 1].decode()
        i += 2
    return result


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"client-config-{port}.aof"
    rewrite_path = ROOT / "build" / f"client-config-{port}.aof.conf"
    aof_path.unlink(missing_ok=True)
    rewrite_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            with connect_with_retry(port, time.monotonic() + 5.0) as peer_sock:
                client_id = send_command(sock, b"CLIENT", b"ID")
                if not isinstance(client_id, int) or client_id <= 0:
                    raise AssertionError(f"unexpected CLIENT ID: {client_id!r}")
                peer_id = send_command(peer_sock, b"CLIENT", b"ID")
                if not isinstance(peer_id, int) or peer_id <= 0:
                    raise AssertionError(f"unexpected peer CLIENT ID: {peer_id!r}")

                if send_command(sock, b"CLIENT", b"GETNAME") is not None:
                    raise AssertionError("new connection should not have a client name")
                if send_command(sock, b"CLIENT", b"SETNAME", b"smoke-client") != "OK":
                    raise AssertionError("CLIENT SETNAME failed")
                if send_command(sock, b"CLIENT", b"GETNAME") != b"smoke-client":
                    raise AssertionError("CLIENT GETNAME did not return the stored name")
                if send_command(peer_sock, b"CLIENT", b"SETNAME", b"peer-client") != "OK":
                    raise AssertionError("peer CLIENT SETNAME failed")

                if send_command(sock, b"CLIENT", b"SETINFO", b"LIB-NAME", b"redis-uya-test") != "OK":
                    raise AssertionError("CLIENT SETINFO LIB-NAME failed")
                if send_command(sock, b"CLIENT", b"SETINFO", b"LIB-VER", b"0.5.0") != "OK":
                    raise AssertionError("CLIENT SETINFO LIB-VER failed")

                info = send_command(sock, b"CLIENT", b"INFO")
                if not isinstance(info, bytes):
                    raise AssertionError(f"CLIENT INFO returned non-bulk value: {info!r}")
                for needle in (b"name=smoke-client", b"lib-name=redis-uya-test", b"lib-ver=0.5.0"):
                    if needle not in info:
                        raise AssertionError(f"missing {needle!r} in CLIENT INFO: {info!r}")

                listed = send_command(sock, b"CLIENT", b"LIST")
                if not isinstance(listed, bytes) or b"name=smoke-client" not in listed or b"name=peer-client" not in listed:
                    raise AssertionError(f"unexpected CLIENT LIST: {listed!r}")

                hello = send_command(sock, b"HELLO", b"3", b"SETNAME", b"resp3-client")
                if not isinstance(hello, dict) or hello.get(b"proto") != 3:
                    raise AssertionError(f"unexpected HELLO 3 response: {hello!r}")
                if send_command(sock, b"CLIENT", b"GETNAME") != b"resp3-client":
                    raise AssertionError("HELLO SETNAME did not update client name")

                max_config_raw = send_command(sock, b"CONFIG", b"GET", b"max*")
                if not isinstance(max_config_raw, list):
                    raise AssertionError(f"CONFIG GET max* returned non-array: {max_config_raw!r}")
                max_config = array_pairs_to_dict(max_config_raw)
                if max_config.get("maxclients") != "8" or max_config.get("maxmemory") != "0":
                    raise AssertionError(f"unexpected CONFIG GET max*: {max_config!r}")

                db_config_raw = send_command(sock, b"CONFIG", b"GET", b"databases")
                if array_pairs_to_dict(db_config_raw).get("databases") != "1":
                    raise AssertionError(f"unexpected CONFIG GET databases: {db_config_raw!r}")

                help_reply = send_command(sock, b"CONFIG", b"HELP")
                if not isinstance(help_reply, list) or b"CONFIG RESETSTAT" not in help_reply or b"CONFIG SET <parameter> <value> [<parameter> <value> ...]" not in help_reply:
                    raise AssertionError(f"unexpected CONFIG HELP: {help_reply!r}")
                if send_command(sock, b"CONFIG", b"RESETSTAT") != "OK":
                    raise AssertionError("CONFIG RESETSTAT failed")

                if send_command(sock, b"CLIENT", b"TRACKING", b"ON", b"REDIRECT", str(peer_id).encode(), b"NOLOOP") != "OK":
                    raise AssertionError("CLIENT TRACKING ON failed")
                if send_command(sock, b"CLIENT", b"GETREDIR") != peer_id:
                    raise AssertionError("CLIENT GETREDIR did not expose redirect target")
                tracking_info = send_command(sock, b"CLIENT", b"TRACKINGINFO")
                if (
                    not isinstance(tracking_info, dict)
                    or not isinstance(tracking_info.get(b"flags"), list)
                    or b"on" not in tracking_info[b"flags"]
                    or b"noloop" not in tracking_info[b"flags"]
                    or tracking_info.get(b"redirect") != peer_id
                    or tracking_info.get(b"prefixes") != []
                ):
                    raise AssertionError(f"unexpected CLIENT TRACKINGINFO: {tracking_info!r}")
                if send_command(sock, b"CLIENT", b"TRACKING", b"OFF") != "OK":
                    raise AssertionError("CLIENT TRACKING OFF failed")
                if send_command(sock, b"CLIENT", b"GETREDIR") != -1:
                    raise AssertionError("CLIENT GETREDIR should reset to -1 after TRACKING OFF")

                if send_command(sock, b"CLIENT", b"CACHING", b"YES") != "OK":
                    raise AssertionError("CLIENT CACHING YES failed")
                if send_command(sock, b"CLIENT", b"CACHING", b"NO") != "OK":
                    raise AssertionError("CLIENT CACHING NO failed")
                try:
                    send_command(sock, b"CLIENT", b"CACHING", b"BAD")
                    raise AssertionError("CLIENT CACHING invalid mode should fail")
                except RespError as exc:
                    if "syntax" not in str(exc).lower():
                        raise

                send_command_expect_no_reply(sock, b"CLIENT", b"REPLY", b"SKIP")
                send_command_expect_no_reply(sock, b"PING")
                if send_command(sock, b"PING") != "PONG":
                    raise AssertionError("CLIENT REPLY SKIP should suppress exactly one reply")

                send_command_expect_no_reply(sock, b"CLIENT", b"REPLY", b"OFF")
                send_command_expect_no_reply(sock, b"CLIENT", b"SETNAME", b"reply-off-client")
                if send_command(sock, b"CLIENT", b"REPLY", b"ON") != "OK":
                    raise AssertionError("CLIENT REPLY ON failed")
                if send_command(sock, b"CLIENT", b"GETNAME") != b"reply-off-client":
                    raise AssertionError("CLIENT REPLY OFF should still execute hidden commands")
                try:
                    send_command(sock, b"CLIENT", b"REPLY", b"BAD")
                    raise AssertionError("CLIENT REPLY invalid mode should fail")
                except RespError as exc:
                    if "syntax" not in str(exc).lower():
                        raise

                if send_command(sock, b"CLIENT", b"NO-TOUCH", b"ON") != "OK":
                    raise AssertionError("CLIENT NO-TOUCH ON failed")
                if send_command(sock, b"CLIENT", b"NO-TOUCH", b"OFF") != "OK":
                    raise AssertionError("CLIENT NO-TOUCH OFF failed")
                try:
                    send_command(sock, b"CLIENT", b"NO-TOUCH", b"BAD")
                    raise AssertionError("CLIENT NO-TOUCH invalid mode should fail")
                except RespError as exc:
                    if "syntax" not in str(exc).lower():
                        raise

                if send_command(sock, b"CLIENT", b"NO-EVICT", b"ON") != "OK":
                    raise AssertionError("CLIENT NO-EVICT ON failed")
                if send_command(sock, b"CLIENT", b"NO-EVICT", b"OFF") != "OK":
                    raise AssertionError("CLIENT NO-EVICT OFF failed")
                try:
                    send_command(sock, b"CLIENT", b"NO-EVICT", b"BAD")
                    raise AssertionError("CLIENT NO-EVICT invalid mode should fail")
                except RespError as exc:
                    if "syntax" not in str(exc).lower():
                        raise

                if send_command(sock, b"CLIENT", b"PAUSE", b"1000", b"ALL") != "OK":
                    raise AssertionError("CLIENT PAUSE failed")
                peer_sock.settimeout(0.1)
                peer_sock.sendall(b"*1\r\n$4\r\nPING\r\n")
                try:
                    paused_reply = read_resp(peer_sock)
                except TimeoutError:
                    paused_reply = None
                except socket.timeout:
                    paused_reply = None
                if paused_reply is not None:
                    raise AssertionError(f"CLIENT PAUSE did not block peer command: {paused_reply!r}")
                if send_command(sock, b"CLIENT", b"UNPAUSE") != "OK":
                    raise AssertionError("CLIENT UNPAUSE failed")
                peer_sock.settimeout(2.0)
                if read_resp(peer_sock) != "PONG":
                    raise AssertionError("peer command did not resume after CLIENT UNPAUSE")

                with connect_with_retry(port, time.monotonic() + 5.0) as blocked_sock:
                    blocked_id = send_command(blocked_sock, b"CLIENT", b"ID")
                    if not isinstance(blocked_id, int) or blocked_id <= 0:
                        raise AssertionError(f"unexpected blocked CLIENT ID: {blocked_id!r}")
                    send_only(blocked_sock, b"BLPOP", b"client-unblock-timeout", b"0")
                    time.sleep(0.1)
                    if send_command(sock, b"CLIENT", b"UNBLOCK", str(blocked_id).encode(), b"TIMEOUT") != 1:
                        raise AssertionError("CLIENT UNBLOCK TIMEOUT did not report one unblocked client")
                    if read_resp(blocked_sock) is not None:
                        raise AssertionError("CLIENT UNBLOCK TIMEOUT should return a null blocking reply")
                    if send_command(sock, b"CLIENT", b"UNBLOCK", str(blocked_id).encode(), b"TIMEOUT") != 0:
                        raise AssertionError("CLIENT UNBLOCK should return 0 once the target is no longer blocked")

                with connect_with_retry(port, time.monotonic() + 5.0) as blocked_error_sock:
                    blocked_error_id = send_command(blocked_error_sock, b"CLIENT", b"ID")
                    if not isinstance(blocked_error_id, int) or blocked_error_id <= 0:
                        raise AssertionError(f"unexpected blocked error CLIENT ID: {blocked_error_id!r}")
                    send_only(blocked_error_sock, b"BLPOP", b"client-unblock-error", b"0")
                    time.sleep(0.1)
                    if send_command(sock, b"CLIENT", b"UNBLOCK", str(blocked_error_id).encode(), b"ERROR") != 1:
                        raise AssertionError("CLIENT UNBLOCK ERROR did not report one unblocked client")
                    try:
                        read_resp(blocked_error_sock)
                        raise AssertionError("CLIENT UNBLOCK ERROR should deliver an error reply")
                    except RespError as exc:
                        if "UNBLOCKED" not in str(exc):
                            raise

                with connect_with_retry(port, time.monotonic() + 5.0) as victim_sock:
                    victim_id = send_command(victim_sock, b"CLIENT", b"ID")
                    if not isinstance(victim_id, int) or victim_id <= 0:
                        raise AssertionError(f"unexpected victim CLIENT ID: {victim_id!r}")
                    killed = send_command(sock, b"CLIENT", b"KILL", b"ID", str(victim_id).encode())
                    if killed != 1:
                        raise AssertionError(f"unexpected CLIENT KILL result: {killed!r}")
                    victim_failed = False
                    try:
                        send_command(victim_sock, b"PING")
                    except Exception:
                        victim_failed = True
                    if not victim_failed:
                        raise AssertionError("victim connection stayed alive after CLIENT KILL")

                if send_command(sock, b"CONFIG", b"SET", b"maxmemory", b"1mb") != "OK":
                    raise AssertionError("CONFIG SET maxmemory failed")
                maxmemory_raw = send_command(sock, b"CONFIG", b"GET", b"maxmemory")
                if array_pairs_to_dict(maxmemory_raw).get("maxmemory") != "1048576":
                    raise AssertionError(f"unexpected CONFIG GET maxmemory after SET: {maxmemory_raw!r}")

                if send_command(sock, b"CONFIG", b"SET", b"maxmemory-policy", b"allkeys-lru") != "OK":
                    raise AssertionError("CONFIG SET maxmemory-policy failed")
                policy_raw = send_command(sock, b"CONFIG", b"GET", b"maxmemory-policy")
                if array_pairs_to_dict(policy_raw).get("maxmemory-policy") != "allkeys-lru":
                    raise AssertionError(f"unexpected CONFIG GET maxmemory-policy after SET: {policy_raw!r}")

                if send_command(sock, b"CONFIG", b"SET", b"save", b"60 10") != "OK":
                    raise AssertionError("CONFIG SET save failed")
                save_raw = send_command(sock, b"CONFIG", b"GET", b"save")
                if array_pairs_to_dict(save_raw).get("save") != "60 10":
                    raise AssertionError(f"unexpected CONFIG GET save after SET: {save_raw!r}")

                if send_command(sock, b"CONFIG", b"SET", b"port", b"6391") != "OK":
                    raise AssertionError("CONFIG SET port failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"port")).get("port") != "6391":
                    raise AssertionError("CONFIG GET port did not reflect CONFIG SET")

                if send_command(sock, b"CONFIG", b"SET", b"bind", b"0.0.0.0") != "OK":
                    raise AssertionError("CONFIG SET bind failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"bind")).get("bind") != "0.0.0.0":
                    raise AssertionError("CONFIG GET bind did not reflect CONFIG SET")

                if send_command(sock, b"CONFIG", b"SET", b"dir", b"build/runtime-dir") != "OK":
                    raise AssertionError("CONFIG SET dir failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"dir")).get("dir") != "build/runtime-dir":
                    raise AssertionError("CONFIG GET dir did not reflect CONFIG SET")

                if send_command(sock, b"CONFIG", b"SET", b"dbfilename", b"runtime.rdb") != "OK":
                    raise AssertionError("CONFIG SET dbfilename failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"dbfilename")).get("dbfilename") != "runtime.rdb":
                    raise AssertionError("CONFIG GET dbfilename did not reflect CONFIG SET")

                if send_command(sock, b"CONFIG", b"SET", b"masterauth", b"upstream-pass") != "OK":
                    raise AssertionError("CONFIG SET masterauth failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"masterauth")).get("masterauth") != "upstream-pass":
                    raise AssertionError("CONFIG GET masterauth did not reflect CONFIG SET")

                if send_command(sock, b"CONFIG", b"SET", b"maxclients", b"16") != "OK":
                    raise AssertionError("CONFIG SET maxclients failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"maxclients")).get("maxclients") != "16":
                    raise AssertionError("CONFIG GET maxclients did not reflect CONFIG SET")

                if send_command(sock, b"CONFIG", b"SET", b"databases", b"1") != "OK":
                    raise AssertionError("CONFIG SET databases failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"databases")).get("databases") != "1":
                    raise AssertionError("CONFIG GET databases did not reflect CONFIG SET")

                if send_command(sock, b"CONFIG", b"SET", b"requirepass", b"runtime-secret") != "OK":
                    raise AssertionError("CONFIG SET requirepass failed")
                requirepass_raw = send_command(sock, b"CONFIG", b"GET", b"requirepass")
                if array_pairs_to_dict(requirepass_raw).get("requirepass") != "runtime-secret":
                    raise AssertionError(f"unexpected CONFIG GET requirepass after SET: {requirepass_raw!r}")
                if send_command(sock, b"PING") != "PONG":
                    raise AssertionError("current connection lost access after CONFIG SET requirepass")
                if send_command(sock, b"CONFIG", b"REWRITE") != "OK":
                    raise AssertionError("CONFIG REWRITE failed")
                rewritten = rewrite_path.read_text(encoding="utf-8")
                if f"appendfilename {aof_path}" not in rewritten:
                    raise AssertionError(f"missing rewritten appendfilename in config: {rewritten!r}")
                for needle in (
                    "port 6391",
                    "bind 0.0.0.0",
                    "dir build/runtime-dir",
                    "dbfilename runtime.rdb",
                    "maxclients 16",
                    "databases 1",
                    "maxmemory 1048576",
                    "maxmemory-policy allkeys-lru",
                    "save 60 10",
                    "requirepass runtime-secret",
                    "masterauth upstream-pass",
                ):
                    if needle not in rewritten:
                        raise AssertionError(f"missing {needle!r} in rewritten config: {rewritten!r}")

                next_aof = ROOT / "build" / f"client-config-next-{port}.aof"
                if send_command(sock, b"CONFIG", b"SET", b"appendfilename", str(next_aof).encode()) != "OK":
                    raise AssertionError("CONFIG SET appendfilename failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"appendfilename")).get("appendfilename") != str(next_aof):
                    raise AssertionError("CONFIG GET appendfilename did not reflect CONFIG SET")

                if send_command(sock, b"QUIT") != "OK":
                    raise AssertionError("QUIT failed")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rewrite_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/client_config_smoke: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/client_config_smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
