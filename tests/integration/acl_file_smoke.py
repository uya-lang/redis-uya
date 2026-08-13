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
            Path(f"{acl_path}.tmp").write_text("stale")
            Path(f"{acl_path}.tmp").chmod(0o666)
            if send_command(admin, b"ACL", b"SAVE") != "OK":
                raise AssertionError("ACL SAVE failed")

            saved = acl_path.read_bytes()
            expected_lines = {
                b"user default on #" + root_hash + b" #" + root2_hash + b" ~* &* +@all",
                b"user app on #" + secret2_hash + b" #" + secret_hash + b" ~safe* &news* +@all -del -set -publish -@admin (~safe* resetchannels -@all +set) (~reports* resetchannels -@all +get) (resetkeys &news* -@all +publish)",
                b"user disabled off #e564b4081d7a9ea4b00dada53bdae70c99b87b6fce869f0c3dd4d2bfa1e53e1c ~* &* +@all",
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

            if send_command(admin, b"ACL", b"SETUSER", b"default", b">changedroot") != "OK":
                raise AssertionError("failed to mutate default password")
            if send_command(admin, b"ACL", b"SETUSER", b"app", b">changed", b"allkeys", b"allchannels", b"+del", b"+set", b"+publish", b"+@admin", b"clearselectors") != "OK":
                raise AssertionError("failed to mutate app user")
            if send_command(admin, b"ACL", b"DELUSER", b"disabled") != 1:
                raise AssertionError("failed to remove disabled user")

            acl_path.write_bytes(saved + b"user app on >duplicate ~* &* +@all\n")
            expect_error(admin, "Error loading the ACLs", b"ACL", b"LOAD")
            with authenticate(port, b"default", b"changedroot") as changed_default:
                if send_command(changed_default, b"PING") != "PONG":
                    raise AssertionError("failed ACL LOAD changed the default user")
            with authenticate(port, b"app", b"changed") as changed_app:
                if send_command(changed_app, b"DEL", b"unsafe") != 0:
                    raise AssertionError("failed ACL LOAD changed app command permissions")
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
            saved_app_line = b"user app on #" + secret2_hash + b" #" + secret_hash + b" ~safe* &news* +@all -del -set -publish -@admin (~safe* resetchannels -@all +set) (~reports* resetchannels -@all +get) (resetkeys &news* -@all +publish)"
            overflow_app_line = b"user app on " + b" ".join(b"#" + item for item in overflow_hashes) + b" ~safe* &news* +@all -del -@admin"
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
