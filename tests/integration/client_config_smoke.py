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
                if (
                    send_command(
                        sock,
                        b"ACL",
                        b"SETUSER",
                        b"peer-user",
                        b"on",
                        b">secret",
                        b"~*",
                        b"&*",
                        b"+@all",
                    )
                    != "OK"
                ):
                    raise AssertionError("ACL SETUSER peer-user failed")
                if send_command(peer_sock, b"AUTH", b"peer-user", b"secret") != "OK":
                    raise AssertionError("peer named-user AUTH failed")
                if send_command(peer_sock, b"CLIENT", b"TRACKING", b"ON") != "OK":
                    raise AssertionError("peer CLIENT TRACKING ON failed")
                if send_command(peer_sock, b"MULTI") != "OK":
                    raise AssertionError("peer MULTI failed")
                time.sleep(1.05)

                if send_command(sock, b"CLIENT", b"SETINFO", b"LIB-NAME", b"redis-uya-test") != "OK":
                    raise AssertionError("CLIENT SETINFO LIB-NAME failed")
                if send_command(sock, b"CLIENT", b"SETINFO", b"LIB-VER", b"0.5.0") != "OK":
                    raise AssertionError("CLIENT SETINFO LIB-VER failed")

                info = send_command(sock, b"CLIENT", b"INFO")
                if not isinstance(info, bytes):
                    raise AssertionError(f"CLIENT INFO returned non-bulk value: {info!r}")
                client_addr = f"{sock.getsockname()[0]}:{sock.getsockname()[1]}".encode()
                client_local_addr = f"{sock.getpeername()[0]}:{sock.getpeername()[1]}".encode()
                for needle in (
                    b"addr=" + client_addr,
                    b"laddr=" + client_local_addr,
                    b"name=smoke-client",
                    b"lib-name=redis-uya-test",
                    b"lib-ver=0.5.0",
                ):
                    if needle not in info:
                        raise AssertionError(f"missing {needle!r} in CLIENT INFO: {info!r}")
                info_fields = dict(part.split(b"=", 1) for part in info.strip().split() if b"=" in part)
                if not info_fields.get(b"fd", b"").isdigit() or int(info_fields[b"fd"]) <= 0:
                    raise AssertionError(f"CLIENT INFO returned invalid fd: {info!r}")
                if info_fields.get(b"db") != b"0":
                    raise AssertionError(f"CLIENT INFO returned invalid db: {info!r}")
                if info_fields.get(b"user") != b"default":
                    raise AssertionError(f"CLIENT INFO returned invalid user: {info!r}")
                if info_fields.get(b"flags") != b"N":
                    raise AssertionError(f"CLIENT INFO returned invalid flags: {info!r}")
                if info_fields.get(b"cmd") != b"client|info":
                    raise AssertionError(f"CLIENT INFO returned invalid command: {info!r}")
                if info_fields.get(b"redir") != b"-1":
                    raise AssertionError(f"CLIENT INFO returned invalid default redirect: {info!r}")
                if info_fields.get(b"multi") != b"-1":
                    raise AssertionError(f"CLIENT INFO returned invalid transaction count: {info!r}")
                if info_fields.get(b"sub") != b"0" or info_fields.get(b"psub") != b"0" or info_fields.get(b"ssub") != b"0":
                    raise AssertionError(f"CLIENT INFO returned invalid subscription counts: {info!r}")
                if info_fields.get(b"qbuf") != b"26" or info_fields.get(b"qbuf-free") != b"8166":
                    raise AssertionError(f"CLIENT INFO returned invalid query buffer usage: {info!r}")
                if info_fields.get(b"argv-mem") != b"0":
                    raise AssertionError(f"CLIENT INFO returned invalid argument memory usage: {info!r}")
                if info_fields.get(b"multi-mem") != b"0":
                    raise AssertionError(f"CLIENT INFO returned invalid transaction memory usage: {info!r}")
                if info_fields.get(b"rbs") != b"81920" or info_fields.get(b"rbp") != b"81920":
                    raise AssertionError(f"CLIENT INFO returned invalid fixed reply buffer sizing: {info!r}")
                if info_fields.get(b"obl") != b"0" or info_fields.get(b"oll") != b"0" or info_fields.get(b"omem") != b"0":
                    raise AssertionError(f"CLIENT INFO returned invalid output buffer usage: {info!r}")
                info_total_memory_raw = info_fields.get(b"tot-mem", b"")
                if not info_total_memory_raw.isdigit() or int(info_total_memory_raw) <= 81920 + 8192:
                    raise AssertionError(f"CLIENT INFO returned invalid total client memory: {info!r}")
                info_total_memory = int(info_total_memory_raw)
                if info_fields.get(b"events") != b"r":
                    raise AssertionError(f"CLIENT INFO returned invalid event interest: {info!r}")
                if info_fields.get(b"io-thread") != b"0":
                    raise AssertionError(f"CLIENT INFO returned invalid I/O thread id: {info!r}")
                if not info_fields.get(b"age", b"").isdigit() or int(info_fields[b"age"]) < 1:
                    raise AssertionError(f"CLIENT INFO returned invalid age: {info!r}")
                if info_fields.get(b"idle") != b"0":
                    raise AssertionError(f"CLIENT INFO returned invalid idle: {info!r}")

                listed = send_command(sock, b"CLIENT", b"LIST")
                peer_addr = f"{peer_sock.getsockname()[0]}:{peer_sock.getsockname()[1]}".encode()
                if (
                    not isinstance(listed, bytes)
                    or b"addr=" + client_addr not in listed
                    or b"laddr=" + client_local_addr not in listed
                    or b"addr=" + peer_addr not in listed
                    or b"name=smoke-client" not in listed
                    or b"name=peer-client" not in listed
                ):
                    raise AssertionError(f"unexpected CLIENT LIST: {listed!r}")
                listed_lines = listed.splitlines()
                current_lines = [line for line in listed_lines if line.startswith(f"id={client_id} ".encode())]
                if len(current_lines) != 1:
                    raise AssertionError(f"CLIENT LIST did not return the current client: {listed!r}")
                current_fields = dict(part.split(b"=", 1) for part in current_lines[0].split() if b"=" in part)
                if current_fields.get(b"cmd") != b"client|list":
                    raise AssertionError(f"CLIENT LIST returned invalid current command: {current_lines[0]!r}")
                peer_lines = [line for line in listed_lines if line.startswith(f"id={peer_id} ".encode())]
                if len(peer_lines) != 1:
                    raise AssertionError(f"CLIENT LIST did not return one peer line: {listed!r}")
                peer_fields = dict(part.split(b"=", 1) for part in peer_lines[0].split() if b"=" in part)
                if not peer_fields.get(b"fd", b"").isdigit() or int(peer_fields[b"fd"]) <= 0:
                    raise AssertionError(f"CLIENT LIST returned invalid peer fd: {peer_lines[0]!r}")
                if peer_fields.get(b"db") != b"0":
                    raise AssertionError(f"CLIENT LIST returned invalid peer db: {peer_lines[0]!r}")
                if peer_fields.get(b"user") != b"peer-user":
                    raise AssertionError(f"CLIENT LIST returned invalid peer user: {peer_lines[0]!r}")
                if peer_fields.get(b"flags") != b"xt":
                    raise AssertionError(f"CLIENT LIST returned invalid peer flags: {peer_lines[0]!r}")
                if peer_fields.get(b"cmd") != b"multi":
                    raise AssertionError(f"CLIENT LIST returned invalid peer command: {peer_lines[0]!r}")
                if peer_fields.get(b"redir") != b"-1":
                    raise AssertionError(f"CLIENT LIST returned invalid peer redirect: {peer_lines[0]!r}")
                if peer_fields.get(b"multi") != b"0":
                    raise AssertionError(f"CLIENT LIST returned invalid empty transaction count: {peer_lines[0]!r}")
                if peer_fields.get(b"multi-mem") != b"0":
                    raise AssertionError(f"CLIENT LIST returned invalid empty transaction memory: {peer_lines[0]!r}")
                if peer_fields.get(b"tot-mem") != str(info_total_memory).encode():
                    raise AssertionError(f"CLIENT LIST returned inconsistent fixed client memory: {peer_lines[0]!r}")
                if peer_fields.get(b"io-thread") != b"0":
                    raise AssertionError(f"CLIENT LIST returned invalid peer I/O thread id: {peer_lines[0]!r}")
                peer_empty_total_memory = int(peer_fields[b"tot-mem"])
                if not peer_fields.get(b"age", b"").isdigit() or int(peer_fields[b"age"]) < 1:
                    raise AssertionError(f"CLIENT LIST returned invalid peer age: {peer_lines[0]!r}")
                if not peer_fields.get(b"idle", b"").isdigit() or int(peer_fields[b"idle"]) < 1:
                    raise AssertionError(f"CLIENT LIST returned invalid peer idle: {peer_lines[0]!r}")

                filtered_peer = send_command(sock, b"CLIENT", b"LIST", b"ID", str(peer_id).encode())
                if (
                    not isinstance(filtered_peer, bytes)
                    or f"id={peer_id} ".encode() not in filtered_peer
                    or f"id={client_id} ".encode() in filtered_peer
                ):
                    raise AssertionError(f"unexpected CLIENT LIST ID peer result: {filtered_peer!r}")

                filtered_both = send_command(
                    sock,
                    b"CLIENT",
                    b"LIST",
                    b"ID",
                    str(peer_id).encode(),
                    str(client_id).encode(),
                )
                filtered_both_lines = filtered_both.splitlines() if isinstance(filtered_both, bytes) else []
                if (
                    len(filtered_both_lines) != 2
                    or not filtered_both_lines[0].startswith(f"id={peer_id} ".encode())
                    or not filtered_both_lines[1].startswith(f"id={client_id} ".encode())
                ):
                    raise AssertionError(f"unexpected CLIENT LIST ID ordering: {filtered_both!r}")

                filtered_duplicate = send_command(
                    sock,
                    b"CLIENT",
                    b"LIST",
                    b"ID",
                    str(client_id).encode(),
                    str(client_id).encode(),
                )
                filtered_duplicate_lines = filtered_duplicate.splitlines() if isinstance(filtered_duplicate, bytes) else []
                if len(filtered_duplicate_lines) != 2 or any(
                    not line.startswith(f"id={client_id} ".encode()) for line in filtered_duplicate_lines
                ):
                    raise AssertionError(f"unexpected duplicate CLIENT LIST ID result: {filtered_duplicate!r}")

                if send_command(sock, b"CLIENT", b"LIST", b"ID", b"99999999") != b"":
                    raise AssertionError("missing CLIENT LIST ID should return an empty bulk string")
                if send_command(peer_sock, b"PING") != "QUEUED":
                    raise AssertionError("peer transaction PING was not queued")
                peer_after_queue = send_command(sock, b"CLIENT", b"LIST", b"ID", str(peer_id).encode())
                peer_after_queue_fields = dict(
                    part.split(b"=", 1)
                    for part in peer_after_queue.strip().split()
                    if b"=" in part
                )
                if peer_after_queue_fields.get(b"multi") != b"1":
                    raise AssertionError(f"peer queued transaction count was not visible: {peer_after_queue!r}")
                if peer_after_queue_fields.get(b"multi-mem") != b"14":
                    raise AssertionError(f"peer queued transaction memory was not visible: {peer_after_queue!r}")
                peer_queued_total_memory_raw = peer_after_queue_fields.get(b"tot-mem", b"")
                if (
                    not peer_queued_total_memory_raw.isdigit()
                    or int(peer_queued_total_memory_raw) <= peer_empty_total_memory + 14
                ):
                    raise AssertionError(f"peer queued total memory did not include owned queue metadata: {peer_after_queue!r}")
                if send_command(peer_sock, b"DISCARD") != "OK":
                    raise AssertionError("peer DISCARD failed")
                peer_after_discard = send_command(sock, b"CLIENT", b"LIST", b"ID", str(peer_id).encode())
                peer_after_discard_fields = dict(
                    part.split(b"=", 1)
                    for part in peer_after_discard.strip().split()
                    if b"=" in part
                )
                if peer_after_discard_fields.get(b"flags") != b"N":
                    raise AssertionError(f"peer flags did not reset after DISCARD: {peer_after_discard!r}")
                if peer_after_discard_fields.get(b"cmd") != b"discard":
                    raise AssertionError(f"peer command did not update after DISCARD: {peer_after_discard!r}")
                if peer_after_discard_fields.get(b"multi") != b"-1":
                    raise AssertionError(f"peer transaction count did not reset after DISCARD: {peer_after_discard!r}")
                if peer_after_discard_fields.get(b"multi-mem") != b"0":
                    raise AssertionError(f"peer transaction memory did not reset after DISCARD: {peer_after_discard!r}")
                if peer_after_discard_fields.get(b"tot-mem") != str(peer_empty_total_memory).encode():
                    raise AssertionError(f"peer total memory did not reset after DISCARD: {peer_after_discard!r}")

                if send_command(sock, b"WATCH", b"dirty-cas-key") != "OK":
                    raise AssertionError("WATCH for dirty-CAS flag failed")
                if send_command(peer_sock, b"SET", b"dirty-cas-key", b"changed") != "OK":
                    raise AssertionError("peer mutation for dirty-CAS flag failed")
                dirty_cas_info = send_command(sock, b"CLIENT", b"INFO")
                dirty_cas_fields = dict(
                    part.split(b"=", 1)
                    for part in dirty_cas_info.strip().split()
                    if b"=" in part
                )
                if dirty_cas_fields.get(b"flags") != b"d":
                    raise AssertionError(f"CLIENT INFO did not expose dirty-CAS: {dirty_cas_info!r}")
                if dirty_cas_fields.get(b"watch") != b"1":
                    raise AssertionError(f"CLIENT INFO did not expose WATCH count: {dirty_cas_info!r}")
                dirty_cas_list = send_command(sock, b"CLIENT", b"LIST", b"ID", str(client_id).encode())
                if b" flags=d " not in dirty_cas_list:
                    raise AssertionError(f"CLIENT LIST did not expose dirty-CAS: {dirty_cas_list!r}")
                if b" watch=1 " not in dirty_cas_list:
                    raise AssertionError(f"CLIENT LIST did not expose WATCH count: {dirty_cas_list!r}")
                if send_command(sock, b"UNWATCH") != "OK":
                    raise AssertionError("UNWATCH after dirty-CAS flag failed")
                dirty_cas_clean_info = send_command(sock, b"CLIENT", b"INFO")
                dirty_cas_clean_fields = dict(
                    part.split(b"=", 1)
                    for part in dirty_cas_clean_info.strip().split()
                    if b"=" in part
                )
                if dirty_cas_clean_fields.get(b"flags") != b"N":
                    raise AssertionError(f"dirty-CAS flag did not clear after UNWATCH: {dirty_cas_clean_info!r}")
                if dirty_cas_clean_fields.get(b"watch") != b"0":
                    raise AssertionError(f"WATCH count did not clear after UNWATCH: {dirty_cas_clean_info!r}")

                peer_config = send_command(peer_sock, b"CONFIG", b"GET", b"databases")
                if not isinstance(peer_config, list):
                    raise AssertionError(f"peer CONFIG GET returned invalid reply: {peer_config!r}")
                peer_after_config = send_command(sock, b"CLIENT", b"LIST", b"ID", str(peer_id).encode())
                peer_after_config_fields = dict(
                    part.split(b"=", 1)
                    for part in peer_after_config.strip().split()
                    if b"=" in part
                )
                if peer_after_config_fields.get(b"cmd") != b"config|get":
                    raise AssertionError(f"peer command did not expose CONFIG subcommand: {peer_after_config!r}")

                with connect_with_retry(port, time.monotonic() + 5.0) as type_pubsub_sock:
                    type_pubsub_id = send_command(type_pubsub_sock, b"CLIENT", b"ID")
                    if not isinstance(type_pubsub_id, int) or type_pubsub_id <= 0:
                        raise AssertionError(f"unexpected TYPE pubsub CLIENT ID: {type_pubsub_id!r}")
                    subscribe_reply = send_command(type_pubsub_sock, b"SUBSCRIBE", b"type-channel")
                    if not isinstance(subscribe_reply, list) or subscribe_reply[0] != b"subscribe":
                        raise AssertionError(f"unexpected TYPE subscription reply: {subscribe_reply!r}")
                    psubscribe_reply = send_command(type_pubsub_sock, b"PSUBSCRIBE", b"type-*")
                    if not isinstance(psubscribe_reply, list) or psubscribe_reply[0] != b"psubscribe":
                        raise AssertionError(f"unexpected TYPE pattern subscription reply: {psubscribe_reply!r}")
                    ssubscribe_reply = send_command(type_pubsub_sock, b"SSUBSCRIBE", b"type-shard")
                    if not isinstance(ssubscribe_reply, list) or ssubscribe_reply[0] != b"ssubscribe":
                        raise AssertionError(f"unexpected TYPE shard subscription reply: {ssubscribe_reply!r}")

                    type_normal = send_command(sock, b"CLIENT", b"LIST", b"TYPE", b"NORMAL")
                    if (
                        not isinstance(type_normal, bytes)
                        or f"id={client_id} ".encode() not in type_normal
                        or f"id={type_pubsub_id} ".encode() in type_normal
                    ):
                        raise AssertionError(f"unexpected CLIENT LIST TYPE NORMAL result: {type_normal!r}")

                    type_pubsub = send_command(sock, b"CLIENT", b"LIST", b"TYPE", b"PUBSUB")
                    if (
                        not isinstance(type_pubsub, bytes)
                        or f"id={type_pubsub_id} ".encode() not in type_pubsub
                        or f"id={client_id} ".encode() in type_pubsub
                    ):
                        raise AssertionError(f"unexpected CLIENT LIST TYPE PUBSUB result: {type_pubsub!r}")
                    type_pubsub_fields = dict(
                        part.split(b"=", 1)
                        for part in type_pubsub.strip().split()
                        if b"=" in part
                    )
                    if type_pubsub_fields.get(b"flags") != b"P":
                        raise AssertionError(f"PUBSUB client returned invalid flags: {type_pubsub!r}")
                    if type_pubsub_fields.get(b"cmd") != b"ssubscribe":
                        raise AssertionError(f"PUBSUB client returned invalid command: {type_pubsub!r}")
                    if (
                        type_pubsub_fields.get(b"sub") != b"1"
                        or type_pubsub_fields.get(b"psub") != b"1"
                        or type_pubsub_fields.get(b"ssub") != b"1"
                    ):
                        raise AssertionError(f"PUBSUB client returned invalid subscription counts: {type_pubsub!r}")
                    if type_pubsub_fields.get(b"qbuf") != b"0" or type_pubsub_fields.get(b"qbuf-free") != b"8192":
                        raise AssertionError(f"PUBSUB client returned invalid query buffer usage: {type_pubsub!r}")
                    if type_pubsub_fields.get(b"argv-mem") != b"0":
                        raise AssertionError(f"PUBSUB client returned invalid argument memory usage: {type_pubsub!r}")
                    if type_pubsub_fields.get(b"multi-mem") != b"0":
                        raise AssertionError(f"PUBSUB client returned invalid transaction memory usage: {type_pubsub!r}")
                    if type_pubsub_fields.get(b"rbs") != b"81920" or type_pubsub_fields.get(b"rbp") != b"81920":
                        raise AssertionError(f"PUBSUB client returned invalid fixed reply buffer sizing: {type_pubsub!r}")
                    if type_pubsub_fields.get(b"obl") != b"0" or type_pubsub_fields.get(b"oll") != b"0" or type_pubsub_fields.get(b"omem") != b"0":
                        raise AssertionError(f"PUBSUB client returned invalid output buffer usage: {type_pubsub!r}")
                    if type_pubsub_fields.get(b"tot-mem") != str(info_total_memory).encode():
                        raise AssertionError(f"PUBSUB client returned invalid fixed total memory: {type_pubsub!r}")
                    if type_pubsub_fields.get(b"events") != b"r":
                        raise AssertionError(f"PUBSUB client returned invalid event interest: {type_pubsub!r}")

                    for replica_type in (b"MASTER", b"REPLICA", b"SLAVE"):
                        replica_clients = send_command(sock, b"CLIENT", b"LIST", b"TYPE", replica_type)
                        if replica_clients != b"":
                            raise AssertionError(
                                f"standalone CLIENT LIST TYPE {replica_type!r} should be empty: {replica_clients!r}"
                            )

                    try:
                        send_command(sock, b"CLIENT", b"LIST", b"TYPE", b"bad")
                        raise AssertionError("invalid CLIENT LIST TYPE should fail")
                    except RespError as exc:
                        if "Unknown client type 'bad'" not in str(exc):
                            raise

                    try:
                        send_command(sock, b"CLIENT", b"LIST", b"TYPE", b"NORMAL", b"ID", str(client_id).encode())
                        raise AssertionError("combined CLIENT LIST TYPE/ID should fail")
                    except RespError as exc:
                        if "syntax error" not in str(exc):
                            raise

                client_help = send_command(sock, b"CLIENT", b"HELP")
                if (
                    not isinstance(client_help, list)
                    or b"CLIENT REPLY <ON|OFF|SKIP>" not in client_help
                    or b"CLIENT LIST [TYPE NORMAL|MASTER|REPLICA|PUBSUB] | [ID <id> ...]" not in client_help
                    or b"CLIENT TRACKINGINFO" not in client_help
                ):
                    raise AssertionError(f"unexpected CLIENT HELP: {client_help!r}")

                with connect_with_retry(port, time.monotonic() + 5.0) as monitor_sock:
                    monitor_id = send_command(monitor_sock, b"CLIENT", b"ID")
                    if send_command(monitor_sock, b"MONITOR") != "OK":
                        raise AssertionError("MONITOR failed")
                    monitor_line = send_command(sock, b"CLIENT", b"LIST", b"ID", str(monitor_id).encode())
                    monitor_fields = dict(
                        part.split(b"=", 1)
                        for part in monitor_line.strip().split()
                        if b"=" in part
                    )
                    if monitor_fields.get(b"flags") != b"O":
                        raise AssertionError(f"MONITOR client returned invalid flags: {monitor_line!r}")
                    if monitor_fields.get(b"cmd") != b"monitor":
                        raise AssertionError(f"MONITOR client returned invalid command: {monitor_line!r}")

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
                tracking_client_info = send_command(sock, b"CLIENT", b"INFO")
                tracking_client_fields = dict(
                    part.split(b"=", 1)
                    for part in tracking_client_info.strip().split()
                    if b"=" in part
                )
                if tracking_client_fields.get(b"redir") != str(peer_id).encode():
                    raise AssertionError(f"CLIENT INFO did not expose redirect target: {tracking_client_info!r}")
                if tracking_client_fields.get(b"tot-mem") != str(info_total_memory).encode():
                    raise AssertionError(f"tracking without prefixes changed total memory: {tracking_client_info!r}")
                tracking_client_list = send_command(sock, b"CLIENT", b"LIST", b"ID", str(client_id).encode())
                tracking_list_fields = dict(
                    part.split(b"=", 1)
                    for part in tracking_client_list.strip().split()
                    if b"=" in part
                )
                if tracking_list_fields.get(b"redir") != str(peer_id).encode():
                    raise AssertionError(f"CLIENT LIST did not expose redirect target: {tracking_client_list!r}")
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
                tracking_off_info = send_command(sock, b"CLIENT", b"INFO")
                tracking_off_fields = dict(
                    part.split(b"=", 1)
                    for part in tracking_off_info.strip().split()
                    if b"=" in part
                )
                if tracking_off_fields.get(b"redir") != b"-1":
                    raise AssertionError(f"CLIENT INFO did not clear redirect target: {tracking_off_info!r}")
                try:
                    send_command(sock, b"CLIENT", b"TRACKING", b"ON", b"PREFIX", b"cache:")
                    raise AssertionError("CLIENT TRACKING PREFIX without BCAST should fail")
                except RespError as exc:
                    if "prefix option requires bcast" not in str(exc).lower():
                        raise
                if send_command(sock, b"CLIENT", b"TRACKING", b"ON", b"BCAST", b"PREFIX", b"cache:", b"PREFIX", b"user:") != "OK":
                    raise AssertionError("CLIENT TRACKING BCAST PREFIX failed")
                tracking_prefix_info = send_command(sock, b"CLIENT", b"TRACKINGINFO")
                if (
                    not isinstance(tracking_prefix_info, dict)
                    or not isinstance(tracking_prefix_info.get(b"flags"), list)
                    or b"on" not in tracking_prefix_info[b"flags"]
                    or b"bcast" not in tracking_prefix_info[b"flags"]
                    or tracking_prefix_info.get(b"redirect") != -1
                    or tracking_prefix_info.get(b"prefixes") != [b"cache:", b"user:"]
                ):
                    raise AssertionError(f"unexpected CLIENT TRACKINGINFO prefixes: {tracking_prefix_info!r}")
                tracking_prefix_client_info = send_command(sock, b"CLIENT", b"INFO")
                tracking_prefix_client_fields = dict(
                    part.split(b"=", 1)
                    for part in tracking_prefix_client_info.strip().split()
                    if b"=" in part
                )
                tracking_prefix_total_memory = tracking_prefix_client_fields.get(b"tot-mem", b"")
                if not tracking_prefix_total_memory.isdigit() or int(tracking_prefix_total_memory) <= info_total_memory:
                    raise AssertionError(f"tracking prefixes did not increase total memory: {tracking_prefix_client_info!r}")
                if tracking_prefix_client_fields.get(b"flags") != b"tB":
                    raise AssertionError(f"tracking BCAST flag was not visible: {tracking_prefix_client_info!r}")
                tracking_prefix_client_list = send_command(sock, b"CLIENT", b"LIST", b"ID", str(client_id).encode())
                if b" flags=tB " not in tracking_prefix_client_list:
                    raise AssertionError(f"CLIENT LIST did not expose tracking BCAST: {tracking_prefix_client_list!r}")
                if send_command(sock, b"CLIENT", b"TRACKING", b"OFF") != "OK":
                    raise AssertionError("CLIENT TRACKING OFF after prefixes failed")
                tracking_prefix_off_info = send_command(sock, b"CLIENT", b"INFO")
                tracking_prefix_off_fields = dict(
                    part.split(b"=", 1)
                    for part in tracking_prefix_off_info.strip().split()
                    if b"=" in part
                )
                if tracking_prefix_off_fields.get(b"tot-mem") != str(info_total_memory).encode():
                    raise AssertionError(f"tracking prefix memory did not clear after OFF: {tracking_prefix_off_info!r}")

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
                no_touch_info = send_command(sock, b"CLIENT", b"INFO")
                no_touch_fields = dict(
                    part.split(b"=", 1)
                    for part in no_touch_info.strip().split()
                    if b"=" in part
                )
                if no_touch_fields.get(b"flags") != b"T":
                    raise AssertionError(f"CLIENT NO-TOUCH flag was not visible: {no_touch_info!r}")
                no_touch_list = send_command(sock, b"CLIENT", b"LIST", b"ID", str(client_id).encode())
                if b" flags=T " not in no_touch_list:
                    raise AssertionError(f"CLIENT LIST did not expose NO-TOUCH: {no_touch_list!r}")
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
                no_evict_info = send_command(sock, b"CLIENT", b"INFO")
                no_evict_fields = dict(
                    part.split(b"=", 1)
                    for part in no_evict_info.strip().split()
                    if b"=" in part
                )
                if no_evict_fields.get(b"flags") != b"e":
                    raise AssertionError(f"CLIENT NO-EVICT flag was not visible: {no_evict_info!r}")
                no_evict_list = send_command(sock, b"CLIENT", b"LIST", b"ID", str(client_id).encode())
                if b" flags=e " not in no_evict_list:
                    raise AssertionError(f"CLIENT LIST did not expose NO-EVICT: {no_evict_list!r}")
                if send_command(sock, b"CLIENT", b"NO-EVICT", b"OFF") != "OK":
                    raise AssertionError("CLIENT NO-EVICT OFF failed")
                try:
                    send_command(sock, b"CLIENT", b"NO-EVICT", b"BAD")
                    raise AssertionError("CLIENT NO-EVICT invalid mode should fail")
                except RespError as exc:
                    if "syntax" not in str(exc).lower():
                        raise

                try:
                    send_command(sock, b"CLIENT", b"PAUSE", b"bad")
                    raise AssertionError("CLIENT PAUSE accepted a non-integer timeout")
                except RespError as exc:
                    if str(exc) != "ERR timeout is not an integer or out of range":
                        raise AssertionError(f"unexpected CLIENT PAUSE timeout error: {exc}") from exc

                if send_command(sock, b"CLIENT", b"PAUSE", b"1000", b"WRITE") != "OK":
                    raise AssertionError("CLIENT PAUSE WRITE failed")
                peer_sock.settimeout(1.0)
                peer_sock.sendall(b"*1\r\n$4\r\nPING\r\n")
                if read_resp(peer_sock) != "PONG":
                    raise AssertionError("CLIENT PAUSE WRITE should not block peer read command")
                peer_sock.settimeout(0.1)
                peer_sock.sendall(b"*3\r\n$3\r\nSET\r\n$15\r\npause-write-key\r\n$1\r\n1\r\n")
                try:
                    paused_write_reply = read_resp(peer_sock)
                except TimeoutError:
                    paused_write_reply = None
                except socket.timeout:
                    paused_write_reply = None
                if paused_write_reply is not None:
                    raise AssertionError(f"CLIENT PAUSE WRITE did not block peer write command: {paused_write_reply!r}")
                if send_command(sock, b"CLIENT", b"UNPAUSE") != "OK":
                    raise AssertionError("CLIENT UNPAUSE after WRITE failed")
                peer_sock.settimeout(2.0)
                if read_resp(peer_sock) != "OK":
                    raise AssertionError("peer write command did not resume after CLIENT UNPAUSE")

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
                    blocked_line = send_command(sock, b"CLIENT", b"LIST", b"ID", str(blocked_id).encode())
                    blocked_fields = dict(
                        part.split(b"=", 1)
                        for part in blocked_line.strip().split()
                        if b"=" in part
                    )
                    if blocked_fields.get(b"flags") != b"b":
                        raise AssertionError(f"blocked client returned invalid flags: {blocked_line!r}")
                    if blocked_fields.get(b"cmd") != b"blpop":
                        raise AssertionError(f"blocked client returned invalid command: {blocked_line!r}")
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

                if send_command(sock, b"CLIENT", b"KILL", b"ADDR", b"127.0.0.1:1") != 0:
                    raise AssertionError("missing CLIENT KILL ADDR should return 0")

                with connect_with_retry(port, time.monotonic() + 5.0) as addr_victim_sock:
                    addr_victim_id = send_command(addr_victim_sock, b"CLIENT", b"ID")
                    if not isinstance(addr_victim_id, int) or addr_victim_id <= 0:
                        raise AssertionError(f"unexpected ADDR victim CLIENT ID: {addr_victim_id!r}")
                    addr_victim_host, addr_victim_port = addr_victim_sock.getsockname()
                    addr_victim = f"{addr_victim_host}:{addr_victim_port}".encode()
                    mismatched = send_command(
                        sock,
                        b"CLIENT",
                        b"KILL",
                        b"ID",
                        str(addr_victim_id).encode(),
                        b"ADDR",
                        client_addr,
                    )
                    if mismatched != 0:
                        raise AssertionError(f"mismatched CLIENT KILL ID/ADDR should return 0, got {mismatched!r}")
                    if send_command(addr_victim_sock, b"PING") != "PONG":
                        raise AssertionError("mismatched CLIENT KILL ID/ADDR closed the victim")
                    if send_command(sock, b"CLIENT", b"KILL", b"ADDR", addr_victim) != 1:
                        raise AssertionError("CLIENT KILL ADDR did not report one killed client")
                    addr_victim_failed = False
                    try:
                        send_command(addr_victim_sock, b"PING")
                    except Exception:
                        addr_victim_failed = True
                    if not addr_victim_failed:
                        raise AssertionError("ADDR victim connection stayed alive after CLIENT KILL")

                with connect_with_retry(port, time.monotonic() + 5.0) as duplicate_addr_victim_sock:
                    if send_command(duplicate_addr_victim_sock, b"PING") != "PONG":
                        raise AssertionError("duplicate ADDR victim registration failed")
                    duplicate_host, duplicate_port = duplicate_addr_victim_sock.getsockname()
                    duplicate_addr = f"{duplicate_host}:{duplicate_port}".encode()
                    duplicate_killed = send_command(
                        sock,
                        b"CLIENT",
                        b"KILL",
                        b"ADDR",
                        duplicate_addr,
                        b"ADDR",
                        duplicate_addr,
                    )
                    if duplicate_killed != 1:
                        raise AssertionError(f"duplicate CLIENT KILL ADDR result: {duplicate_killed!r}")
                    duplicate_addr_failed = False
                    try:
                        send_command(duplicate_addr_victim_sock, b"PING")
                    except Exception:
                        duplicate_addr_failed = True
                    if not duplicate_addr_failed:
                        raise AssertionError("duplicate ADDR victim stayed alive after CLIENT KILL")

                with connect_with_retry(port, time.monotonic() + 5.0) as legacy_victim_sock:
                    if send_command(legacy_victim_sock, b"PING") != "PONG":
                        raise AssertionError("legacy ADDR victim registration failed")
                    legacy_host, legacy_port = legacy_victim_sock.getsockname()
                    legacy_addr = f"{legacy_host}:{legacy_port}".encode()
                    legacy_killed = send_command(sock, b"CLIENT", b"KILL", legacy_addr)
                    if legacy_killed != "OK":
                        raise AssertionError(f"unexpected legacy CLIENT KILL result: {legacy_killed!r}")
                    legacy_failed = False
                    try:
                        send_command(legacy_victim_sock, b"PING")
                    except Exception:
                        legacy_failed = True
                    if not legacy_failed:
                        raise AssertionError("legacy address victim stayed alive after CLIENT KILL")

                with connect_with_retry(port, time.monotonic() + 5.0) as self_kill_sock:
                    self_kill_id = send_command(self_kill_sock, b"CLIENT", b"ID")
                    if not isinstance(self_kill_id, int) or self_kill_id <= 0:
                        raise AssertionError(f"unexpected self-kill CLIENT ID: {self_kill_id!r}")
                    skipped = send_command(self_kill_sock, b"CLIENT", b"KILL", b"ID", str(self_kill_id).encode(), b"SKIPME", b"YES")
                    if skipped != 0:
                        raise AssertionError(f"CLIENT KILL SKIPME YES should skip self, got {skipped!r}")
                    if send_command(self_kill_sock, b"PING") != "PONG":
                        raise AssertionError("self connection should survive CLIENT KILL SKIPME YES")
                    self_killed = send_command(self_kill_sock, b"CLIENT", b"KILL", b"SKIPME", b"NO", b"ID", str(self_kill_id).encode())
                    if self_killed != 1:
                        raise AssertionError(f"CLIENT KILL SKIPME NO should kill self, got {self_killed!r}")
                    self_failed = False
                    try:
                        send_command(self_kill_sock, b"PING")
                    except Exception:
                        self_failed = True
                    if not self_failed:
                        raise AssertionError("self connection stayed alive after CLIENT KILL SKIPME NO")

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

                if send_command(sock, b"CONFIG", b"SET", b"maxmemory", b"64mb", b"maxmemory-policy", b"volatile-lru") != "OK":
                    raise AssertionError("CONFIG SET multi-parameter maxmemory/policy failed")
                multi_max_raw = send_command(sock, b"CONFIG", b"GET", b"maxmemory")
                if array_pairs_to_dict(multi_max_raw).get("maxmemory") != "67108864":
                    raise AssertionError(f"unexpected CONFIG GET maxmemory after multi SET: {multi_max_raw!r}")
                multi_policy_raw = send_command(sock, b"CONFIG", b"GET", b"maxmemory-policy")
                if array_pairs_to_dict(multi_policy_raw).get("maxmemory-policy") != "volatile-lru":
                    raise AssertionError(f"unexpected CONFIG GET maxmemory-policy after multi SET: {multi_policy_raw!r}")
                if send_command(sock, b"CONFIG", b"SET", b"maxmemory", b"1mb") != "OK":
                    raise AssertionError("CONFIG SET maxmemory restore failed")
                if send_command(sock, b"CONFIG", b"SET", b"maxmemory-policy", b"allkeys-lru") != "OK":
                    raise AssertionError("CONFIG SET maxmemory-policy restore failed")

                if send_command(sock, b"CONFIG", b"SET", b"maxmemory-policy", b"allkeys-lfu") != "OK":
                    raise AssertionError("CONFIG SET maxmemory-policy allkeys-lfu for no-touch failed")
                if send_command(sock, b"SET", b"client-no-touch-key", b"value") != "OK":
                    raise AssertionError("SET before CLIENT NO-TOUCH check failed")
                if send_command(sock, b"OBJECT", b"FREQ", b"client-no-touch-key") != 1:
                    raise AssertionError("unexpected initial OBJECT FREQ before CLIENT NO-TOUCH")
                if send_command(sock, b"CLIENT", b"NO-TOUCH", b"ON") != "OK":
                    raise AssertionError("CLIENT NO-TOUCH ON failed")
                if send_command(sock, b"GET", b"client-no-touch-key") != b"value":
                    raise AssertionError("GET with CLIENT NO-TOUCH ON failed")
                if send_command(sock, b"OBJECT", b"FREQ", b"client-no-touch-key") != 1:
                    raise AssertionError("CLIENT NO-TOUCH ON still updated OBJECT FREQ")
                if send_command(sock, b"CLIENT", b"NO-TOUCH", b"OFF") != "OK":
                    raise AssertionError("CLIENT NO-TOUCH OFF failed")
                if send_command(sock, b"GET", b"client-no-touch-key") != b"value":
                    raise AssertionError("GET after CLIENT NO-TOUCH OFF failed")
                if send_command(sock, b"OBJECT", b"FREQ", b"client-no-touch-key") != 2:
                    raise AssertionError("CLIENT NO-TOUCH OFF did not restore OBJECT FREQ updates")
                if send_command(sock, b"CONFIG", b"SET", b"maxmemory-policy", b"allkeys-lru") != "OK":
                    raise AssertionError("CONFIG SET maxmemory-policy restore after no-touch failed")

                if send_command(sock, b"CONFIG", b"SET", b"save", b"60 10") != "OK":
                    raise AssertionError("CONFIG SET save failed")
                save_raw = send_command(sock, b"CONFIG", b"GET", b"save")
                if array_pairs_to_dict(save_raw).get("save") != "60 10":
                    raise AssertionError(f"unexpected CONFIG GET save after SET: {save_raw!r}")

                if send_command(sock, b"CONFIG", b"SET", b"latency-tracking", b"no") != "OK":
                    raise AssertionError("CONFIG SET latency-tracking no failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"latency-tracking")).get("latency-tracking") != "no":
                    raise AssertionError("CONFIG GET latency-tracking did not reflect disabled state")
                if send_command(sock, b"CONFIG", b"RESETSTAT") != "OK":
                    raise AssertionError("CONFIG RESETSTAT before latency-tracking check failed")
                if send_command(sock, b"SET", b"latency-track-off", b"1") != "OK":
                    raise AssertionError("SET while latency-tracking disabled failed")
                disabled_histogram = send_command(sock, b"LATENCY", b"HISTOGRAM", b"SET")
                if disabled_histogram != []:
                    raise AssertionError(f"latency-tracking no still recorded SET histogram: {disabled_histogram!r}")
                if send_command(sock, b"CONFIG", b"SET", b"latency-tracking", b"yes") != "OK":
                    raise AssertionError("CONFIG SET latency-tracking yes failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"latency-tracking")).get("latency-tracking") != "yes":
                    raise AssertionError("CONFIG GET latency-tracking did not reflect enabled state")
                if send_command(sock, b"SET", b"latency-track-on", b"1") != "OK":
                    raise AssertionError("SET while latency-tracking enabled failed")
                enabled_histogram = send_command(sock, b"LATENCY", b"HISTOGRAM", b"SET")
                if not isinstance(enabled_histogram, list) or b"set" not in enabled_histogram:
                    raise AssertionError(f"latency-tracking yes did not record SET histogram: {enabled_histogram!r}")
                if send_command(sock, b"CONFIG", b"SET", b"latency-monitor-threshold", b"1000000") != "OK":
                    raise AssertionError("CONFIG SET latency-monitor-threshold high failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"latency-monitor-threshold")).get("latency-monitor-threshold") != "1000000":
                    raise AssertionError("CONFIG GET latency-monitor-threshold did not reflect high threshold")
                config_set_histogram = send_command(sock, b"LATENCY", b"HISTOGRAM", b"CONFIG|SET")
                if not isinstance(config_set_histogram, list) or b"config|set" not in config_set_histogram:
                    raise AssertionError(f"latency histogram did not record CONFIG SET subcommand: {config_set_histogram!r}")
                if send_command(sock, b"LATENCY", b"RESET") not in (0, 1):
                    raise AssertionError("LATENCY RESET before threshold check failed")
                if send_command(sock, b"SET", b"latency-threshold-off", b"1") != "OK":
                    raise AssertionError("SET while latency-monitor-threshold high failed")
                if send_command(sock, b"LATENCY", b"LATEST") != []:
                    raise AssertionError("latency-monitor-threshold high still recorded event")
                if send_command(sock, b"CONFIG", b"SET", b"latency-monitor-threshold", b"1") != "OK":
                    raise AssertionError("CONFIG SET latency-monitor-threshold 1 failed")
                if send_command(sock, b"LATENCY", b"RESET") not in (0, 1):
                    raise AssertionError("LATENCY RESET before threshold enabled check failed")
                if send_command(sock, b"SET", b"latency-threshold-on", b"1") != "OK":
                    raise AssertionError("SET while latency-monitor-threshold enabled failed")
                enabled_latest = send_command(sock, b"LATENCY", b"LATEST")
                if not isinstance(enabled_latest, list) or len(enabled_latest) == 0:
                    raise AssertionError("latency-monitor-threshold 1 did not record event")
                if send_command(sock, b"CONFIG", b"SET", b"latency-tracking", b"no") != "OK":
                    raise AssertionError("CONFIG SET latency-tracking no before rewrite failed")

                if send_command(sock, b"CONFIG", b"SET", b"slowlog-log-slower-than", b"-1") != "OK":
                    raise AssertionError("CONFIG SET slowlog-log-slower-than -1 failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"slowlog-log-slower-than")).get("slowlog-log-slower-than") != "-1":
                    raise AssertionError("CONFIG GET slowlog-log-slower-than did not reflect disabled state")
                if send_command(sock, b"SLOWLOG", b"RESET") != "OK":
                    raise AssertionError("SLOWLOG RESET before threshold check failed")
                if send_command(sock, b"SET", b"slowlog-threshold-off", b"1") != "OK":
                    raise AssertionError("SET while slowlog disabled failed")
                if send_command(sock, b"SLOWLOG", b"LEN") != 0:
                    raise AssertionError("slowlog-log-slower-than -1 still recorded command")

                if send_command(sock, b"CONFIG", b"SET", b"slowlog-max-len", b"1") != "OK":
                    raise AssertionError("CONFIG SET slowlog-max-len 1 failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"slowlog-max-len")).get("slowlog-max-len") != "1":
                    raise AssertionError("CONFIG GET slowlog-max-len did not reflect configured state")
                if send_command(sock, b"CONFIG", b"SET", b"slowlog-log-slower-than", b"0") != "OK":
                    raise AssertionError("CONFIG SET slowlog-log-slower-than 0 failed")
                if send_command(sock, b"SLOWLOG", b"RESET") != "OK":
                    raise AssertionError("SLOWLOG RESET before max-len check failed")
                if send_command(sock, b"SET", b"slowlog-max-one", b"1") != "OK":
                    raise AssertionError("SET before slowlog max-len check failed")
                if send_command(sock, b"GET", b"slowlog-max-one") != b"1":
                    raise AssertionError("GET before slowlog max-len check failed")
                if send_command(sock, b"SLOWLOG", b"LEN") != 1:
                    raise AssertionError("slowlog-max-len 1 did not trim slowlog to one entry")
                if send_command(sock, b"CONFIG", b"SET", b"slowlog-log-slower-than", b"-1") != "OK":
                    raise AssertionError("CONFIG SET slowlog-log-slower-than -1 before rewrite failed")

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

                if send_command(sock, b"CONFIG", b"SET", b"timeout", b"30") != "OK":
                    raise AssertionError("CONFIG SET timeout failed")
                if array_pairs_to_dict(send_command(sock, b"CONFIG", b"GET", b"timeout")).get("timeout") != "30":
                    raise AssertionError("CONFIG GET timeout did not reflect CONFIG SET")

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
                    "timeout 30",
                    "maxmemory 1048576",
                    "maxmemory-policy allkeys-lru",
                    "latency-tracking no",
                    "latency-monitor-threshold 1",
                    "slowlog-log-slower-than -1",
                    "slowlog-max-len 1",
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
