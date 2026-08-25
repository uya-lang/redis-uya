#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import socket
import stat
import subprocess
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


def connect_with_retry(port: int) -> socket.socket:
    deadline = time.monotonic() + 5.0
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
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed while reading RESP line")
        data.extend(chunk)
    return bytes(data[:-2])


def read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RuntimeError("connection closed while reading RESP payload")
        data.extend(chunk)
    return bytes(data)


def read_resp(sock: socket.socket):
    prefix = read_exact(sock, 1)
    if prefix == b"+":
        return read_line(sock).decode()
    if prefix == b"-":
        raise RespError(read_line(sock).decode())
    if prefix == b":":
        return int(read_line(sock))
    if prefix == b"$":
        length = int(read_line(sock))
        if length < 0:
            return None
        payload = read_exact(sock, length)
        if read_exact(sock, 2) != b"\r\n":
            raise RuntimeError("invalid bulk terminator")
        return payload
    if prefix == b"*":
        count = int(read_line(sock))
        if count < 0:
            return None
        return [read_resp(sock) for _ in range(count)]
    raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")


def send_command(sock: socket.socket, *args: bytes):
    request = bytearray(f"*{len(args)}\r\n".encode())
    for arg in args:
        request.extend(f"${len(arg)}\r\n".encode())
        request.extend(arg)
        request.extend(b"\r\n")
    sock.sendall(request)
    return read_resp(sock)


def expect_error(sock: socket.socket, contains: str, *args: bytes) -> None:
    try:
        send_command(sock, *args)
    except RespError as exc:
        if contains not in str(exc):
            raise AssertionError(f"unexpected error for {args!r}: {exc}") from exc
        return
    raise AssertionError(f"expected error for {args!r}")


def config_value(sock: socket.socket, key: bytes) -> bytes:
    reply = send_command(sock, b"CONFIG", b"GET", key)
    if not isinstance(reply, list) or len(reply) != 2 or reply[0] != key or not isinstance(reply[1], bytes):
        raise AssertionError(f"invalid CONFIG GET {key!r} reply: {reply!r}")
    return reply[1]


def acl_getuser_field(sock: socket.socket, username: bytes, field: bytes):
    reply = send_command(sock, b"ACL", b"GETUSER", username)
    if not isinstance(reply, list) or len(reply) % 2 != 0:
        raise AssertionError(f"invalid ACL GETUSER {username!r} reply: {reply!r}")
    for index in range(0, len(reply), 2):
        if reply[index] == field:
            return reply[index + 1]
    raise AssertionError(f"ACL GETUSER {username!r} omitted {field!r}: {reply!r}")


def authenticate(port: int, username: bytes, password: bytes) -> socket.socket:
    sock = connect_with_retry(port)
    try:
        if send_command(sock, b"AUTH", username, password) != "OK":
            raise AssertionError(f"AUTH failed for {username!r}")
        return sock
    except Exception:
        sock.close()
        raise


def expect_auth_error(port: int, username: bytes, password: bytes) -> None:
    with connect_with_retry(port) as sock:
        expect_error(sock, "WRONGPASS", b"AUTH", username, password)


def expect_connection_closed(sock: socket.socket, context: str) -> None:
    try:
        data = sock.recv(1)
    except OSError:
        return
    if data != b"":
        raise AssertionError(f"{context} left unexpected data on the connection: {data!r}")


def start_server(port: int, aof_path: Path, acl_path: Path | None = None) -> subprocess.Popen[str]:
    args = [str(BIN), str(port), "8", str(aof_path)]
    if acl_path is not None:
        args.extend(["0", "noeviction", "", str(acl_path)])
    return subprocess.Popen(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    acl_path = ROOT / "build" / f"acl-file-smoke-{port}.acl"
    aof_path = ROOT / "build" / f"acl-file-smoke-{port}.aof"
    restart_aof_path = ROOT / "build" / f"acl-file-restart-{port}.aof"
    invalid_path = ROOT / "build" / f"acl-file-invalid-{port}.acl"
    invalid_aof_path = ROOT / "build" / f"acl-file-invalid-{port}.aof"
    for path in (acl_path, Path(f"{acl_path}.tmp"), aof_path, restart_aof_path, invalid_path, invalid_aof_path):
        path.unlink(missing_ok=True)

    proc = start_server(port, aof_path)
    try:
        with connect_with_retry(port) as admin:
            expect_error(admin, "not configured to use an ACL file", b"ACL", b"SAVE")
            expect_error(admin, "not configured to use an ACL file", b"ACL", b"LOAD")
            if config_value(admin, b"aclfile") != b"":
                raise AssertionError("aclfile default is not empty")
            if send_command(admin, b"CONFIG", b"SET", b"aclfile", str(acl_path).encode()) != "OK":
                raise AssertionError("CONFIG SET aclfile failed")
            if config_value(admin, b"aclfile") != str(acl_path).encode():
                raise AssertionError("CONFIG GET aclfile mismatch")

            for invalid_username in (b"bad user", b"bad\tuser", b"bad\nuser", b"bad\x00user"):
                expect_error(
                    admin,
                    "Usernames can't contain spaces or null characters",
                    b"ACL",
                    b"SETUSER",
                    invalid_username,
                    b"on",
                )
                if send_command(admin, b"ACL", b"GETUSER", invalid_username) is not None:
                    raise AssertionError(f"invalid ACL username was created: {invalid_username!r}")

            if send_command(admin, b"ACL", b"SETUSER", b"DEFAULT", b"on", b"nopass", b"+ping", b"+acl") != "OK":
                raise AssertionError("failed to create case-sensitive DEFAULT named user")
            if acl_getuser_field(admin, b"DEFAULT", b"commands") != b"-@all +ping +acl":
                raise AssertionError("ACL GETUSER routed DEFAULT to the default user")
            if send_command(admin, b"ACL", b"GETUSER", b"Default") is not None:
                raise AssertionError("ACL GETUSER matched a differently cased username")
            case_user = authenticate(port, b"DEFAULT", b"ignored")
            try:
                if send_command(case_user, b"ACL", b"WHOAMI") != b"DEFAULT":
                    raise AssertionError("ACL WHOAMI did not preserve username case")
                if send_command(case_user, b"PING") != "PONG":
                    raise AssertionError("case-sensitive DEFAULT named user cannot run PING")
                expect_error(case_user, "NOPERM User DEFAULT", b"GET", b"missing")
                case_log = send_command(admin, b"ACL", b"LOG", b"1")
                if not isinstance(case_log, list) or len(case_log) != 1 or not isinstance(case_log[0], list):
                    raise AssertionError(f"ACL LOG omitted DEFAULT denial entry: {case_log!r}")
                case_log_username = None
                for index in range(0, len(case_log[0]), 2):
                    if case_log[0][index] == b"username":
                        case_log_username = case_log[0][index + 1]
                        break
                if case_log_username != b"DEFAULT":
                    raise AssertionError(f"ACL LOG did not preserve username case: {case_log!r}")
                if send_command(admin, b"ACL", b"LOG", b"RESET") != "OK":
                    raise AssertionError("failed to reset ACL LOG after username-case check")
                expect_auth_error(port, b"Default", b"ignored")
                expect_auth_error(port, b"Default", b"ignored")
                auth_log = send_command(admin, b"ACL", b"LOG", b"1")
                if not isinstance(auth_log, list) or len(auth_log) != 1 or not isinstance(auth_log[0], list):
                    raise AssertionError(f"ACL LOG omitted failed authentication: {auth_log!r}")
                auth_fields = dict(zip(auth_log[0][::2], auth_log[0][1::2]))
                if auth_fields.get(b"reason") != b"auth" or auth_fields.get(b"context") != b"toplevel":
                    raise AssertionError(f"ACL LOG used wrong failed-auth metadata: {auth_log!r}")
                if auth_fields.get(b"object") != b"AUTH" or auth_fields.get(b"username") != b"Default":
                    raise AssertionError(f"ACL LOG lost failed-auth username/object: {auth_log!r}")
                if auth_fields.get(b"count") != 2:
                    raise AssertionError(f"ACL LOG did not group repeated authentication failures: {auth_log!r}")
                if send_command(admin, b"ACL", b"LOG", b"RESET") != "OK":
                    raise AssertionError("failed to reset ACL LOG after authentication check")
                if send_command(admin, b"ACL", b"SAVE") != "OK":
                    raise AssertionError("failed to save case-sensitive DEFAULT named user")
                case_saved = acl_path.read_bytes()
                if not any(line.startswith(b"user DEFAULT on nopass ") for line in case_saved.splitlines()):
                    raise AssertionError(f"ACL SAVE did not preserve DEFAULT username case: {case_saved!r}")
                if send_command(admin, b"ACL", b"SETUSER", b"DEFAULT", b"+set") != "OK":
                    raise AssertionError("failed to mutate case-sensitive DEFAULT named user")
                if send_command(admin, b"ACL", b"LOAD") != "OK":
                    raise AssertionError("failed to reload case-sensitive DEFAULT named user")
                if acl_getuser_field(admin, b"DEFAULT", b"commands") != b"-@all +ping +acl":
                    raise AssertionError("ACL LOAD did not preserve DEFAULT named user rules")
                if send_command(admin, b"ACL", b"DELUSER", b"DeFaUlT") != 0:
                    raise AssertionError("ACL DELUSER matched a differently cased username")
                if send_command(admin, b"ACL", b"DELUSER", b"DEFAULT") != 1:
                    raise AssertionError("ACL DELUSER could not remove DEFAULT named user")
                expect_connection_closed(case_user, "case-sensitive DEFAULT DELUSER")
            finally:
                case_user.close()

            if send_command(admin, b"ACL", b"SETUSER", b"audit-object", b"on", b"nopass", b"+mget", b"+subscribe", b"~AllowedKey", b"&AllowedChannel") != "OK":
                raise AssertionError("failed to create ACL audit object user")
            audit_user = authenticate(port, b"audit-object", b"ignored")
            try:
                expect_error(audit_user, "permissions to access one of the keys", b"MGET", b"AllowedKey", b"AuditKey")
                key_audit_log = send_command(admin, b"ACL", b"LOG", b"1")
                key_audit_fields = dict(zip(key_audit_log[0][::2], key_audit_log[0][1::2]))
                if key_audit_fields.get(b"reason") != b"key" or key_audit_fields.get(b"object") != b"AuditKey":
                    raise AssertionError(f"ACL LOG lost denied key object: {key_audit_log!r}")
                if send_command(admin, b"ACL", b"LOG", b"RESET") != "OK":
                    raise AssertionError("failed to reset ACL LOG after key object check")
                expect_error(audit_user, "permissions to access one of the channels", b"SUBSCRIBE", b"AllowedChannel", b"AuditChannel")
                channel_audit_log = send_command(admin, b"ACL", b"LOG", b"1")
                channel_audit_fields = dict(zip(channel_audit_log[0][::2], channel_audit_log[0][1::2]))
                if channel_audit_fields.get(b"reason") != b"channel" or channel_audit_fields.get(b"object") != b"AuditChannel":
                    raise AssertionError(f"ACL LOG lost denied channel object: {channel_audit_log!r}")
                if send_command(admin, b"ACL", b"LOG", b"RESET") != "OK":
                    raise AssertionError("failed to reset ACL LOG after channel object check")
                if send_command(admin, b"ACL", b"DELUSER", b"audit-object") != 1:
                    raise AssertionError("failed to remove ACL audit object user")
                expect_connection_closed(audit_user, "ACL audit object DELUSER")
            finally:
                audit_user.close()

            if send_command(admin, b"ACL", b"SETUSER", b"subacl", b"on", b"nopass", b"+acl|whoami") != "OK":
                raise AssertionError("failed to create ACL child-command user")
            if acl_getuser_field(admin, b"subacl", b"commands") != b"-@all +acl|whoami":
                raise AssertionError("ACL GETUSER lost child-command rule")
            subacl = authenticate(port, b"subacl", b"ignored")
            try:
                if send_command(subacl, b"ACL", b"WHOAMI") != b"subacl":
                    raise AssertionError("ACL child-command rule did not allow WHOAMI")
                expect_error(subacl, "NOPERM", b"ACL", b"USERS")
                if send_command(admin, b"ACL", b"SAVE") != "OK":
                    raise AssertionError("failed to save ACL child-command rule")
                if send_command(admin, b"ACL", b"SETUSER", b"subacl", b"+acl|users") != "OK":
                    raise AssertionError("failed to mutate ACL child-command rule")
                if send_command(admin, b"ACL", b"LOAD") != "OK":
                    raise AssertionError("failed to reload ACL child-command rule")
                expect_error(subacl, "NOPERM", b"ACL", b"USERS")
                if send_command(admin, b"ACL", b"DELUSER", b"subacl") != 1:
                    raise AssertionError("failed to remove ACL child-command user")
                expect_connection_closed(subacl, "ACL child-command DELUSER")
            finally:
                subacl.close()

            expect_error(admin, "modifier 'bogus': Syntax error", b"ACL", b"SETUSER", b"default", b"off", b"resetpass", b"bogus")
            if acl_getuser_field(admin, b"default", b"flags") != [b"on", b"nopass"]:
                raise AssertionError("failed ACL SETUSER changed default user state")
            if send_command(admin, b"ACL", b"SETUSER", b"atomic", b"reset", b"on", b"nopass", b"+set", b"allkeys", b"allchannels") != "OK":
                raise AssertionError("failed to create ACL SETUSER rollback user")
            expect_error(admin, "password you are trying to remove", b"ACL", b"SETUSER", b"atomic", b"off", b"+get", b"<missing")
            if acl_getuser_field(admin, b"atomic", b"flags") != [b"on", b"nopass"]:
                raise AssertionError("failed ACL SETUSER changed named user flags")
            if acl_getuser_field(admin, b"atomic", b"commands") != b"-@all +set":
                raise AssertionError("failed ACL SETUSER changed named user commands")
            if send_command(admin, b"ACL", b"DELUSER", b"atomic") != 1:
                raise AssertionError("failed to remove ACL SETUSER rollback user")

            if send_command(admin, b"ACL", b"SETUSER", b"session", b"on", b"nopass", b"+ping") != "OK":
                raise AssertionError("failed to create ACL session lifecycle user")
            session = authenticate(port, b"session", b"ignored")
            try:
                if send_command(admin, b"ACL", b"SETUSER", b"session", b"off") != "OK":
                    raise AssertionError("failed to disable ACL session lifecycle user")
                if send_command(session, b"PING") != "PONG":
                    raise AssertionError("disabling named user invalidated an existing connection")
                expect_auth_error(port, b"session", b"ignored")
            finally:
                session.close()
            if send_command(admin, b"ACL", b"DELUSER", b"session") != 1:
                raise AssertionError("failed to remove ACL session lifecycle user")

            for username in (b"delete-one", b"delete-two"):
                if send_command(admin, b"ACL", b"SETUSER", username, b"on", b"nopass", b"+ping") != "OK":
                    raise AssertionError(f"failed to create ACL delete lifecycle user {username!r}")
            delete_one = authenticate(port, b"delete-one", b"ignored")
            delete_two = authenticate(port, b"delete-two", b"ignored")
            try:
                if send_command(admin, b"ACL", b"DELUSER", b"delete-one", b"delete-two") != 2:
                    raise AssertionError("ACL DELUSER did not delete both lifecycle users")
                expect_connection_closed(delete_one, "ACL DELUSER delete-one")
                expect_connection_closed(delete_two, "ACL DELUSER delete-two")
            finally:
                delete_one.close()
                delete_two.close()

            if send_command(admin, b"ACL", b"SETUSER", b"delete-self", b"on", b"nopass", b"+acl") != "OK":
                raise AssertionError("failed to create ACL self-delete lifecycle user")
            delete_self = authenticate(port, b"delete-self", b"ignored")
            try:
                if send_command(delete_self, b"ACL", b"DELUSER", b"delete-self") != 1:
                    raise AssertionError("ACL DELUSER self-delete returned the wrong count")
                expect_connection_closed(delete_self, "ACL DELUSER self-delete")
            finally:
                delete_self.close()

            for username in (b"load-removed", b"load-self", b"load-disabled"):
                rules = (b"+acl",) if username == b"load-self" else (b"+ping",)
                if send_command(admin, b"ACL", b"SETUSER", username, b"on", b"nopass", *rules) != "OK":
                    raise AssertionError(f"failed to create ACL LOAD lifecycle user {username!r}")
            if send_command(admin, b"ACL", b"SAVE") != "OK":
                raise AssertionError("failed to save ACL LOAD lifecycle users")
            load_file_lines = []
            for line in acl_path.read_bytes().splitlines():
                if line.startswith((b"user load-removed ", b"user load-self ")):
                    continue
                if line.startswith(b"user load-disabled on "):
                    line = line.replace(b"user load-disabled on ", b"user load-disabled off ", 1)
                load_file_lines.append(line)
            acl_path.write_bytes(b"\n".join(load_file_lines) + b"\n")
            load_removed = authenticate(port, b"load-removed", b"ignored")
            load_self = authenticate(port, b"load-self", b"ignored")
            load_disabled = authenticate(port, b"load-disabled", b"ignored")
            try:
                if send_command(load_self, b"ACL", b"LOAD") != "OK":
                    raise AssertionError("ACL LOAD self-removal did not return OK")
                expect_connection_closed(load_removed, "ACL LOAD removed user")
                expect_connection_closed(load_self, "ACL LOAD self-removal")
                if send_command(load_disabled, b"PING") != "PONG":
                    raise AssertionError("ACL LOAD disabled an existing named-user connection")
                expect_auth_error(port, b"load-disabled", b"ignored")
                if send_command(admin, b"ACL", b"DELUSER", b"load-disabled") != 1:
                    raise AssertionError("failed to remove ACL LOAD disabled lifecycle user")
                expect_connection_closed(load_disabled, "ACL DELUSER after ACL LOAD disabled user")
            finally:
                load_removed.close()
                load_self.close()
                load_disabled.close()

            idle_default = connect_with_retry(port)
            if send_command(admin, b"ACL", b"SETUSER", b"default", b"resetpass", b">rootpass", b">rootpass2", b">rootpass") != "OK":
                raise AssertionError("failed to set default ACL passwords")
            root_hash = b"5012f5182061c46e57859cf617128c6f70eddfba4db27772bdede5a039fa7085"
            root2_hash = b"5f707b584687d17d3564a315087d400ba2359635ef1e1f05d3d03e53f5fb97cb"
            if acl_getuser_field(admin, b"default", b"passwords") != [root_hash, root2_hash]:
                raise AssertionError("ACL GETUSER did not return both default password hashes")
            with authenticate(port, b"default", b"rootpass"):
                pass
            with authenticate(port, b"default", b"rootpass2"):
                pass
            secret_hash = b"2bb80d537b1da3e38bd30361aa855686bde0eacd7162fef6a25fe97bf527a25b"
            secret2_hash = b"35224d0d3465d74e855f8d69a136e79c744ea35a675d3393360a327cbf6359a2"
            expect_error(admin, "password hash must be exactly 64 characters", b"ACL", b"SETUSER", b"app", b"#abc")
            expect_error(
                admin,
                "password hash must be exactly 64 characters",
                b"ACL",
                b"SETUSER",
                b"app",
                b"#2BB80d537b1da3e38bd30361aa855686bde0eacd7162fef6a25fe97bf527a25b",
            )
            if send_command(
                admin,
                b"ACL",
                b"SETUSER",
                b"app",
                b"on",
                b"#" + secret_hash,
                b">secret2",
                b"#" + secret_hash,
                b"resetkeys",
                b"~safe*",
                b"resetchannels",
                b"&news*",
                b"-del",
                b"-set",
                b"-publish",
                b"-@admin",
                b"+ping",
                b"(~safe* +set)",
                b"(~reports* +get)",
                b"(&news* +publish)",
            ) != "OK":
                raise AssertionError("failed to create app ACL user")
            with authenticate(port, b"app", b"secret") as hashed_app:
                if send_command(hashed_app, b"PING") != "PONG":
                    raise AssertionError("direct password hash cannot authenticate")
                if send_command(hashed_app, b"SET", b"safe:key", b"value") != "OK":
                    raise AssertionError("selector cannot grant SET on an allowed key")
                if send_command(hashed_app, b"GET", b"reports:one") is not None:
                    raise AssertionError("selector cannot grant GET on its own key pattern")
                expect_error(hashed_app, "has no permissions to run the 'set' command", b"SET", b"reports:one", b"value")
            with authenticate(port, b"app", b"secret2") as second_app:
                if send_command(second_app, b"PING") != "PONG":
                    raise AssertionError("second app password cannot authenticate")
            if acl_getuser_field(admin, b"app", b"passwords") != [secret_hash, secret2_hash]:
                raise AssertionError("ACL GETUSER did not return both password hashes in insertion order")
            expect_error(
                admin,
                "password you are trying to remove from the user does not exist",
                b"ACL",
                b"SETUSER",
                b"app",
                b"!" + (b"0" * 64),
            )
            if send_command(admin, b"ACL", b"SETUSER", b"app", b"!" + secret_hash) != "OK":
                raise AssertionError("failed to remove app password hash")
            expect_auth_error(port, b"app", b"secret")
            with authenticate(port, b"app", b"secret2"):
                pass
            if send_command(admin, b"ACL", b"SETUSER", b"app", b"#" + secret_hash) != "OK":
                raise AssertionError("failed to restore app password hash")
            expect_error(
                admin,
                "password you are trying to remove from the user does not exist",
                b"ACL",
                b"SETUSER",
                b"app",
                b"<wrong",
            )
            if send_command(admin, b"ACL", b"SETUSER", b"app", b"<secret") != "OK":
                raise AssertionError("failed to remove app password by plaintext")
            expect_auth_error(port, b"app", b"secret")
            with authenticate(port, b"app", b"secret2"):
                pass
            if send_command(admin, b"ACL", b"SETUSER", b"app", b"#" + secret_hash) != "OK":
                raise AssertionError("failed to restore app password after plaintext removal")
            capacity_passwords = tuple(f">capacity-{index}".encode() for index in range(8))
            if send_command(admin, b"ACL", b"SETUSER", b"capacity", b"on", b"resetpass", *capacity_passwords) != "OK":
                raise AssertionError("failed to fill ACL password capacity")
            expect_error(admin, "password list is full", b"ACL", b"SETUSER", b"capacity", b">capacity-8")
            with authenticate(port, b"capacity", b"capacity-7"):
                pass
            if send_command(admin, b"ACL", b"DELUSER", b"capacity") != 1:
                raise AssertionError("failed to remove capacity test user")
            if send_command(admin, b"ACL", b"SETUSER", b"disabled", b"off", b">hidden") != "OK":
                raise AssertionError("failed to create disabled ACL user")
            if send_command(admin, b"ACL", b"SETUSER", b"reader", b"on", b">readerpass", b"-@all", b"+@read", b"-get", b"+get", b"~safe*") != "OK":
                raise AssertionError("failed to create whitelist ACL user")
            with authenticate(port, b"reader", b"readerpass") as reader:
                if send_command(reader, b"GET", b"safe:key") != b"value":
                    raise AssertionError("whitelist user cannot run the final allowed command")
                expect_error(reader, "has no permissions to access one of the keys", b"GET", b"unsafe")
                expect_error(reader, "has no permissions to run the 'set' command", b"SET", b"safe:key", b"value")
            if send_command(admin, b"ACL", b"SETUSER", b"directional", b"on", b">directionpass", b"+@all", b"resetkeys", b"%R~read:*", b"%W~write:*", b"~both:*") != "OK":
                raise AssertionError("failed to create directional ACL user")
            if send_command(admin, b"SET", b"read:source", b"seed") != "OK":
                raise AssertionError("failed to seed directional source key")
            with authenticate(port, b"directional", b"directionpass") as directional:
                if send_command(directional, b"GET", b"read:source") != b"seed":
                    raise AssertionError("read pattern cannot read its key")
                expect_error(directional, "has no permissions to access one of the keys", b"SET", b"read:source", b"changed")
                if send_command(directional, b"SET", b"write:target", b"value") != "OK":
                    raise AssertionError("write pattern cannot write its key")
                expect_error(directional, "has no permissions to access one of the keys", b"GET", b"write:target")
                if send_command(directional, b"COPY", b"read:source", b"write:copy") != 1:
                    raise AssertionError("directional COPY source/destination permissions failed")
                expect_error(directional, "has no permissions to access one of the keys", b"GETSET", b"write:target", b"next")
                if send_command(directional, b"SET", b"both:key", b"before") != "OK":
                    raise AssertionError("read-write pattern cannot write its key")
                if send_command(directional, b"GETSET", b"both:key", b"after") != b"before":
                    raise AssertionError("GETSET did not require and accept read-write permission")
            if acl_getuser_field(admin, b"directional", b"keys") != b"%R~read:* %W~write:* ~both:*":
                raise AssertionError("ACL GETUSER did not preserve directional key patterns")

            if send_command(admin, b"ACL", b"SETUSER", b"operator", b"on", b"nopass", b"+@all", b"allkeys", b"allchannels") != "OK":
                raise AssertionError("failed to create default-state test operator")
            try:
                with authenticate(port, b"operator", b"ignored") as operator:
                    if send_command(operator, b"ACL", b"SETUSER", b"default", b"off") != "OK":
                        raise AssertionError("failed to disable the default user")
                    if send_command(admin, b"PING") != "PONG":
                        raise AssertionError("disabling the default user invalidated an active connection")
                    if send_command(idle_default, b"PING") != "PONG":
                        raise AssertionError("disabling the default user invalidated a pre-existing idle connection")
                    expect_auth_error(port, b"default", b"rootpass")
                    if acl_getuser_field(operator, b"default", b"flags") != [b"off"]:
                        raise AssertionError("ACL GETUSER did not expose the disabled default user")

                    if send_command(operator, b"ACL", b"SETUSER", b"default", b"on") != "OK":
                        raise AssertionError("failed to re-enable the default user")
                    with authenticate(port, b"default", b"rootpass"):
                        pass
                    if send_command(operator, b"ACL", b"SETUSER", b"default", b"(~temporary* +get)") != "OK":
                        raise AssertionError("failed to add the default reset selector")

                    if send_command(operator, b"ACL", b"SETUSER", b"default", b"reset") != "OK":
                        raise AssertionError("failed to reset the default user")
                    if acl_getuser_field(operator, b"default", b"flags") != [b"off"]:
                        raise AssertionError("default reset did not disable the user")
                    if acl_getuser_field(operator, b"default", b"passwords") != []:
                        raise AssertionError("default reset did not clear passwords")
                    if acl_getuser_field(operator, b"default", b"commands") != b"-@all":
                        raise AssertionError("default reset did not clear command permissions")
                    if acl_getuser_field(operator, b"default", b"keys") != b"resetkeys":
                        raise AssertionError("default reset did not clear key patterns")
                    if acl_getuser_field(operator, b"default", b"channels") != b"resetchannels":
                        raise AssertionError("default reset did not clear channel patterns")
                    if acl_getuser_field(operator, b"default", b"selectors") != []:
                        raise AssertionError("default reset did not clear selectors")
                    expect_auth_error(port, b"default", b"rootpass")

                    if send_command(operator, b"ACL", b"SAVE") != "OK":
                        raise AssertionError("failed to save the reset default user")
                    reset_saved = acl_path.read_bytes()
                    if b"user default off resetpass resetkeys resetchannels -@all\n" not in reset_saved:
                        raise AssertionError(f"ACL SAVE omitted the reset default state: {reset_saved!r}")
                    if send_command(operator, b"ACL", b"SETUSER", b"default", b"on", b"nopass", b"allkeys", b"allchannels", b"+@all") != "OK":
                        raise AssertionError("failed to mutate the default user before reset-state load")
                    if send_command(operator, b"ACL", b"LOAD") != "OK":
                        raise AssertionError("failed to load the reset default user")
                    if acl_getuser_field(operator, b"default", b"flags") != [b"off"]:
                        raise AssertionError("ACL LOAD did not restore the default enabled state")
                    if acl_getuser_field(operator, b"default", b"commands") != b"-@all":
                        raise AssertionError("ACL LOAD did not restore default command permissions")

                    if send_command(
                        operator,
                        b"ACL",
                        b"SETUSER",
                        b"default",
                        b"on",
                        b"resetpass",
                        b"#" + root_hash,
                        b"#" + root2_hash,
                        b"allkeys",
                        b"allchannels",
                        b"+@all",
                    ) != "OK":
                        raise AssertionError("failed to restore the default user after reset-state load")
            finally:
                idle_default.close()
            if send_command(admin, b"ACL", b"DELUSER", b"operator") != 1:
                raise AssertionError("failed to remove default-state test operator")

            Path(f"{acl_path}.tmp").write_text("stale")
            Path(f"{acl_path}.tmp").chmod(0o666)
            if send_command(admin, b"ACL", b"SAVE") != "OK":
                raise AssertionError("ACL SAVE failed")

            saved = acl_path.read_bytes()
            expected_lines = {
                b"user default on #" + root_hash + b" #" + root2_hash + b" ~* &* +@all",
                b"user app on #" + secret2_hash + b" #" + secret_hash + b" ~safe* &news* -@all -del -set -publish -@admin +ping (~safe* resetchannels -@all +set) (~reports* resetchannels -@all +get) (resetkeys &news* -@all +publish)",
                b"user disabled off #e564b4081d7a9ea4b00dada53bdae70c99b87b6fce869f0c3dd4d2bfa1e53e1c resetkeys resetchannels -@all",
                b"user reader on #df14634a7777444be41e5bae441440f6a7d8de675a9b6c2af9ae00e33e9d114f ~safe* resetchannels -@all +@read +get",
                b"user directional on #4b43ff2cd4be774e13fcd1ed3036afe6bbca166ba16d45036a3c9372af754e04 %R~read:* %W~write:* ~both:* resetchannels +@all",
            }
            if set(saved.splitlines()) != expected_lines:
                raise AssertionError(f"unexpected ACL file payload: {saved!r}")
            if stat.S_IMODE(acl_path.stat().st_mode) != 0o600:
                raise AssertionError("ACL SAVE did not create a mode 0600 file")
            if Path(f"{acl_path}.tmp").exists():
                raise AssertionError("ACL SAVE left its temporary file behind")
            if any(password in saved for password in (b"rootpass", b"rootpass2", b"secret", b"secret2", b"hidden")):
                raise AssertionError("ACL SAVE exposed a plaintext password")
            acl_list = send_command(admin, b"ACL", b"LIST")
            if b"rootpass" in repr(acl_list).encode() or b"secret" in repr(acl_list).encode():
                raise AssertionError("ACL LIST exposed a plaintext password")
            if not isinstance(acl_list, list) or not all(
                isinstance(entry, bytes) and (b" nopass " in entry or any(len(token) == 65 and token.startswith(b"#") for token in entry.split()))
                for entry in acl_list
            ):
                raise AssertionError(f"ACL LIST did not expose canonical SHA-256 markers: {acl_list!r}")

            acl_path.write_bytes(
                saved
                + b"user resetload on >temporary ~* &* +@all reset\n"
                + b"user noload on nopass ~* &* nocommands\n"
            )
            if send_command(admin, b"ACL", b"LOAD") != "OK":
                raise AssertionError("ACL LOAD rejected named reset/nocommands modifiers")
            if acl_getuser_field(admin, b"resetload", b"flags") != [b"off"]:
                raise AssertionError("ACL file reset did not disable the named user")
            if acl_getuser_field(admin, b"resetload", b"passwords") != []:
                raise AssertionError("ACL file reset did not clear named user passwords")
            if acl_getuser_field(admin, b"resetload", b"commands") != b"-@all":
                raise AssertionError("ACL file reset did not restore nocommands")
            if acl_getuser_field(admin, b"resetload", b"keys") != b"resetkeys":
                raise AssertionError("ACL file reset did not clear key patterns")
            if acl_getuser_field(admin, b"resetload", b"channels") != b"resetchannels":
                raise AssertionError("ACL file reset did not clear channel patterns")
            expect_error(admin, "has no permissions to run the 'ping' command", b"ACL", b"DRYRUN", b"noload", b"PING")
            acl_path.write_bytes(saved)
            if send_command(admin, b"ACL", b"LOAD") != "OK":
                raise AssertionError("ACL LOAD failed to restore the canonical test state")

            if send_command(admin, b"ACL", b"SETUSER", b"default", b"off", b">changedroot") != "OK":
                raise AssertionError("failed to mutate default password")
            if send_command(admin, b"ACL", b"SETUSER", b"app", b">changed", b"allkeys", b"allchannels", b"+del", b"+set", b"+publish", b"+@admin", b"clearselectors") != "OK":
                raise AssertionError("failed to mutate app user")
            if send_command(admin, b"ACL", b"DELUSER", b"disabled") != 1:
                raise AssertionError("failed to remove disabled user")

            acl_path.write_bytes(saved + b"user app on >duplicate ~* &* +@all\n")
            expect_error(admin, "Error loading the ACLs", b"ACL", b"LOAD")
            if acl_getuser_field(admin, b"default", b"flags") != [b"off"]:
                raise AssertionError("failed ACL LOAD changed the default enabled state")
            expect_auth_error(port, b"default", b"changedroot")
            if send_command(admin, b"ACL", b"SETUSER", b"default", b"on") != "OK":
                raise AssertionError("failed to re-enable the rolled-back default user")
            with authenticate(port, b"default", b"changedroot") as changed_default:
                if send_command(changed_default, b"PING") != "PONG":
                    raise AssertionError("failed ACL LOAD changed the default user")
            with authenticate(port, b"app", b"changed") as changed_app:
                if send_command(changed_app, b"DEL", b"unsafe") != 0:
                    raise AssertionError("failed ACL LOAD changed app command permissions")
            with authenticate(port, b"reader", b"readerpass") as rollback_reader:
                expect_error(rollback_reader, "has no permissions to run the 'set' command", b"SET", b"safe:key", b"value")
            expect_auth_error(port, b"disabled", b"hidden")

            first_selector = b"(~safe* resetchannels -@all +set)"
            acl_path.write_bytes(saved.replace(first_selector, b"(~safe* resetchannels -@all +set"))
            expect_error(admin, "Error loading the ACLs", b"ACL", b"LOAD")
            with authenticate(port, b"app", b"changed") as selector_rollback_app:
                if send_command(selector_rollback_app, b"SET", b"unsafe", b"value") != "OK":
                    raise AssertionError("invalid selector load did not restore the previous ACL state")

            acl_path.write_bytes(saved.replace(secret_hash, b"2BB80d537b1da3e38bd30361aa855686bde0eacd7162fef6a25fe97bf527a25b"))
            expect_error(admin, "Error loading the ACLs", b"ACL", b"LOAD")
            with authenticate(port, b"app", b"changed") as unchanged_app:
                if send_command(unchanged_app, b"PING") != "PONG":
                    raise AssertionError("invalid password hash load changed app authentication")

            overflow_hashes = [hashlib.sha256(f"overflow-{index}".encode()).hexdigest().encode() for index in range(9)]
            saved_app_line = b"user app on #" + secret2_hash + b" #" + secret_hash + b" ~safe* &news* -@all -del -set -publish -@admin +ping (~safe* resetchannels -@all +set) (~reports* resetchannels -@all +get) (resetkeys &news* -@all +publish)"
            overflow_app_line = b"user app on " + b" ".join(b"#" + item for item in overflow_hashes) + b" ~safe* &news* -@all -del -@admin +ping"
            acl_path.write_bytes(saved.replace(saved_app_line, overflow_app_line))
            expect_error(admin, "Error loading the ACLs", b"ACL", b"LOAD")
            with authenticate(port, b"app", b"changed") as capacity_rollback_app:
                if send_command(capacity_rollback_app, b"PING") != "PONG":
                    raise AssertionError("password capacity load failure changed app authentication")

            acl_path.write_bytes(saved)
            if send_command(admin, b"ACL", b"LOAD") != "OK":
                raise AssertionError("ACL LOAD failed")

        expect_auth_error(port, b"default", b"changedroot")
        expect_auth_error(port, b"app", b"changed")
        with authenticate(port, b"default", b"rootpass") as restored_default:
            if send_command(restored_default, b"PING") != "PONG":
                raise AssertionError("restored default user cannot run PING")
        with authenticate(port, b"default", b"rootpass2"):
            pass
        with authenticate(port, b"app", b"secret") as app:
            if send_command(app, b"SET", b"safe:key", b"value") != "OK":
                raise AssertionError("restored app user cannot access an allowed key")
            if send_command(app, b"GET", b"reports:one") is not None:
                raise AssertionError("restored selector cannot access its allowed key")
            expect_error(app, "has no permissions to run the 'set' command", b"SET", b"reports:one", b"value")
            expect_error(app, "has no permissions to run the 'set' command", b"SET", b"unsafe", b"value")
            expect_error(app, "has no permissions to run the 'del' command", b"DEL", b"safe:key")
            if send_command(app, b"PUBLISH", b"news:one", b"message") != 0:
                raise AssertionError("restored app user cannot publish to an allowed channel")
            expect_error(app, "has no permissions to run the 'publish' command", b"PUBLISH", b"other", b"message")
        with authenticate(port, b"app", b"secret2"):
            pass
        with authenticate(port, b"reader", b"readerpass") as restored_reader:
            if send_command(restored_reader, b"GET", b"safe:key") != b"value":
                raise AssertionError("restored whitelist user cannot run GET")
            expect_error(restored_reader, "has no permissions to run the 'set' command", b"SET", b"safe:key", b"value")
        with authenticate(port, b"directional", b"directionpass") as restored_directional:
            if send_command(restored_directional, b"GET", b"read:source") != b"seed":
                raise AssertionError("restored directional user cannot read its key")
            expect_error(restored_directional, "has no permissions to access one of the keys", b"GET", b"write:target")
        expect_auth_error(port, b"disabled", b"hidden")
    finally:
        stop_process(proc)

    restart_port = find_free_port()
    restart_proc = start_server(restart_port, restart_aof_path, acl_path)
    try:
        with connect_with_retry(restart_port) as unauthenticated:
            expect_error(unauthenticated, "NOAUTH", b"PING")
        with authenticate(restart_port, b"default", b"rootpass") as restarted:
            if config_value(restarted, b"aclfile") != str(acl_path).encode():
                raise AssertionError("startup ACL path was not retained in runtime config")
        with authenticate(restart_port, b"default", b"rootpass2"):
            pass
        with authenticate(restart_port, b"app", b"secret") as restarted_app:
            expect_error(restarted_app, "has no permissions to run the 'del' command", b"DEL", b"safe:key")
            if send_command(restarted_app, b"SET", b"safe:key", b"restart") != "OK":
                raise AssertionError("startup ACL selector cannot grant SET")
            if send_command(restarted_app, b"GET", b"reports:restart") is not None:
                raise AssertionError("startup ACL selector cannot grant GET")
        with authenticate(restart_port, b"app", b"secret2"):
            pass
        with authenticate(restart_port, b"reader", b"readerpass") as restarted_reader:
            if send_command(restarted_reader, b"GET", b"safe:key") != b"restart":
                raise AssertionError("startup ACL whitelist cannot run GET")
            expect_error(restarted_reader, "has no permissions to run the 'set' command", b"SET", b"safe:key", b"value")
        with authenticate(restart_port, b"directional", b"directionpass") as restarted_directional:
            if send_command(restarted_directional, b"GET", b"read:missing") is not None:
                raise AssertionError("startup ACL directional user cannot read its key")
            expect_error(restarted_directional, "has no permissions to access one of the keys", b"SET", b"read:source", b"changed")
            if send_command(restarted_directional, b"SET", b"write:startup", b"value") != "OK":
                raise AssertionError("startup ACL directional user cannot write its key")
    finally:
        stop_process(restart_proc)

    invalid_path.write_text(f"user app on #{secret_hash.decode()} ~* &* +@all\n")
    invalid_proc = start_server(find_free_port(), invalid_aof_path, invalid_path)
    try:
        return_code = invalid_proc.wait(timeout=5.0)
        if return_code == 0:
            raise AssertionError("startup accepted an ACL file without the default user")
        output = "".join(invalid_proc.communicate())
        if "failed to load aclfile" not in output:
            raise AssertionError(f"startup ACL failure was not reported: {output!r}")
    finally:
        stop_process(invalid_proc)
        for path in (acl_path, Path(f"{acl_path}.tmp"), aof_path, restart_aof_path, invalid_path, invalid_aof_path):
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    run_smoke()
    print("acl_file_smoke: ok")
