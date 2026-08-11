#!/usr/bin/env python3
from __future__ import annotations

import shutil
import socket
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


def connect_with_retry(port: int) -> socket.socket:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            sock.settimeout(2.0)
            return sock
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"failed to connect to redis-uya on port {port}")


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
    if prefix == b"%":
        count = int(read_line(sock))
        return {read_resp(sock): read_resp(sock) for _ in range(count)}
    raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")


def send_command(sock: socket.socket, *args: bytes):
    request = bytearray(f"*{len(args)}\r\n".encode())
    for arg in args:
        request.extend(f"${len(arg)}\r\n".encode())
        request.extend(arg)
        request.extend(b"\r\n")
    sock.sendall(request)
    return read_resp(sock)


def expect_error(sock: socket.socket, expected: str, *args: bytes) -> None:
    try:
        send_command(sock, *args)
    except RespError as exc:
        if str(exc) != expected:
            raise AssertionError(f"unexpected error for {args!r}: {exc}") from exc
        return
    raise AssertionError(f"expected error for {args!r}")


def pairs(values) -> dict[str, object]:
    if not isinstance(values, list) or len(values) % 2:
        raise AssertionError(f"expected RESP2 map pairs, got {values!r}")
    result: dict[str, object] = {}
    for index in range(0, len(values), 2):
        key = values[index]
        if not isinstance(key, bytes):
            raise AssertionError(f"invalid map key: {key!r}")
        result[key.decode()] = values[index + 1]
    return result


def run_smoke() -> None:
    port = find_free_port()
    aof_path = ROOT / "build" / f"backup-smoke-{port}.aof"
    backup_dir = ROOT / "build" / f"backup-smoke-{port}"
    restore_root = ROOT / "build" / f"backup-restore-{port}"
    rewritten_config = Path(f"{aof_path}.conf")
    aof_path.unlink(missing_ok=True)
    rewritten_config.unlink(missing_ok=True)
    shutil.rmtree(backup_dir, ignore_errors=True)
    shutil.rmtree(restore_root, ignore_errors=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        with connect_with_retry(port) as sock:
            if send_command(sock, b"CONFIG", b"SET", b"backupdirname", str(backup_dir).encode()) != "OK":
                raise AssertionError("CONFIG SET backupdirname failed")
            if pairs(send_command(sock, b"CONFIG", b"GET", b"backupdirname"))["backupdirname"] != str(backup_dir).encode():
                raise AssertionError("CONFIG GET backupdirname mismatch")
            if send_command(sock, b"CONFIG", b"REWRITE") != "OK":
                raise AssertionError("CONFIG REWRITE failed")
            if f"backupdirname {backup_dir}" not in rewritten_config.read_text():
                raise AssertionError("CONFIG REWRITE omitted backupdirname")
            if pairs(send_command(sock, b"BACKUP", b"STATUS"))["state"] != b"idle":
                raise AssertionError("initial backup state is not idle")
            if not isinstance(send_command(sock, b"HELLO", b"3"), dict):
                raise AssertionError("HELLO 3 failed before BACKUP STATUS")
            resp3_status = send_command(sock, b"BACKUP", b"STATUS")
            if not isinstance(resp3_status, dict) or resp3_status.get(b"state") != b"idle":
                raise AssertionError(f"RESP3 BACKUP STATUS mismatch: {resp3_status!r}")
            send_command(sock, b"HELLO", b"2")
            if send_command(sock, b"BACKUP", b"LIST") != []:
                raise AssertionError("initial backup file list is not empty")
            expect_error(sock, "ERR No backup in progress", b"BACKUP", b"ABORT")
            expect_error(
                sock,
                "ERR No backup ready to seal (must be in the incrementing state)",
                b"BACKUP",
                b"SEAL",
            )

            help_lines = send_command(sock, b"BACKUP", b"HELP")
            if not isinstance(help_lines, list) or b"BACKUP START" not in help_lines:
                raise AssertionError(f"BACKUP HELP is incomplete: {help_lines!r}")
            expect_error(sock, "ERR command is not allowed from script", b"EVAL", b"return redis.call('BACKUP', 'STATUS')", b"0")

            if send_command(sock, b"SET", b"before", b"base") != "OK":
                raise AssertionError("failed to seed base snapshot")
            if send_command(sock, b"BACKUP", b"START") != "OK":
                raise AssertionError("BACKUP START failed")
            status = pairs(send_command(sock, b"BACKUP", b"STATUS"))
            if status["state"] != b"incrementing" or not isinstance(status["start_time"], int):
                raise AssertionError(f"unexpected active status: {status!r}")
            expect_error(
                sock,
                "ERR A backup is already in progress, ABORT it first",
                b"BACKUP",
                b"START",
            )

            active_files = send_command(sock, b"BACKUP", b"LIST")
            if len(active_files) != 1 or not Path(active_files[0].decode()).is_file():
                raise AssertionError(f"active backup base file missing: {active_files!r}")
            if not Path(active_files[0].decode()).read_bytes().startswith(b"RUYARDB1"):
                raise AssertionError("backup base file is not a redis-uya RDB")

            if send_command(sock, b"SET", b"after", b"incremental") != "OK":
                raise AssertionError("failed to append incremental write")
            if send_command(sock, b"DEL", b"before") != 1:
                raise AssertionError("failed to append incremental delete")
            if send_command(sock, b"MULTI") != "OK" or send_command(sock, b"SET", b"tx-key", b"tx-value") != "QUEUED":
                raise AssertionError("failed to queue transactional backup write")
            if send_command(sock, b"EXEC") != ["OK"]:
                raise AssertionError("failed to execute transactional backup write")
            script_result = send_command(sock, b"EVAL", b"return redis.call('SET', KEYS[1], ARGV[1])", b"1", b"lua-key", b"lua-value")
            if script_result not in ("OK", b"+OK\r\n"):
                raise AssertionError(f"failed to execute scripted backup write: {script_result!r}")
            if send_command(sock, b"HIMPORT", b"PREPARE", b"backup-fields", b"field") != "OK":
                raise AssertionError("failed to prepare HIMPORT backup fieldset")
            if send_command(sock, b"HIMPORT", b"SET", b"hash-key", b"backup-fields", b"hash-value") != "OK":
                raise AssertionError("failed to execute HIMPORT backup write")
            if send_command(sock, b"BACKUP", b"SEAL") != "OK":
                raise AssertionError("BACKUP SEAL failed")

            status = pairs(send_command(sock, b"BACKUP", b"STATUS"))
            if status["state"] != b"sealed" or status["end_time"] < status["start_time"]:
                raise AssertionError(f"unexpected sealed status: {status!r}")
            sealed_files = [Path(value.decode()) for value in send_command(sock, b"BACKUP", b"LIST")]
            if len(sealed_files) != 3 or not all(path.is_file() for path in sealed_files):
                raise AssertionError(f"sealed backup artifacts missing: {sealed_files!r}")
            incremental = sealed_files[1].read_bytes()
            if any(value not in incremental for value in (b"incremental", b"DEL", b"tx-value", b"lua-value", b"RESTORE", b"hash-key")):
                raise AssertionError("sealed incremental AOF is missing post-START writes")
            if b"HIMPORT" in incremental:
                raise AssertionError("connection-local HIMPORT leaked into the incremental AOF")
            if b"before\r\n$4\r\nbase" in incremental:
                raise AssertionError("pre-START writes leaked into the incremental AOF")
            if b"redis-uya-backup-v1" not in sealed_files[2].read_bytes():
                raise AssertionError("backup manifest format marker missing")

            restore_port = find_free_port()
            (restore_root / "build").mkdir(parents=True)
            shutil.copyfile(sealed_files[0], restore_root / "build" / "dump.rdb")
            restore_proc = subprocess.Popen(
                [str(BIN), str(restore_port), "8", str(sealed_files[1])],
                cwd=restore_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            try:
                with connect_with_retry(restore_port) as restored:
                    if send_command(restored, b"GET", b"before") is not None:
                        raise AssertionError("backup restore did not replay the incremental delete")
                    if send_command(restored, b"GET", b"after") != b"incremental":
                        raise AssertionError("backup restore lost an ordinary incremental write")
                    if send_command(restored, b"GET", b"tx-key") != b"tx-value":
                        raise AssertionError("backup restore lost a transactional write")
                    if send_command(restored, b"GET", b"lua-key") != b"lua-value":
                        raise AssertionError("backup restore lost a scripted write")
                    if send_command(restored, b"HGET", b"hash-key", b"field") != b"hash-value":
                        raise AssertionError("backup restore lost an HIMPORT write")
            finally:
                restore_proc.terminate()
                try:
                    restore_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    restore_proc.kill()
                    restore_proc.wait(timeout=3)
            expect_error(
                sock,
                "ERR A sealed backup exists, CLEANUP it first",
                b"BACKUP",
                b"START",
            )

            if send_command(sock, b"BACKUP", b"CLEANUP") != "OK":
                raise AssertionError("BACKUP CLEANUP failed")
            if backup_dir.exists() or send_command(sock, b"BACKUP", b"LIST") != []:
                raise AssertionError("BACKUP CLEANUP left backup artifacts")

            if send_command(sock, b"BACKUP", b"START") != "OK":
                raise AssertionError("second BACKUP START failed")
            if send_command(sock, b"BACKUP", b"ABORT") != "OK":
                raise AssertionError("BACKUP ABORT failed")
            aborted = pairs(send_command(sock, b"BACKUP", b"STATUS"))
            if aborted["state"] != b"failed" or aborted["error"] != b"aborted by user":
                raise AssertionError(f"unexpected aborted status: {aborted!r}")
            if send_command(sock, b"BACKUP", b"CLEANUP") != "OK":
                raise AssertionError("cleanup after abort failed")

            if send_command(sock, b"ACL", b"SETUSER", b"default", b"-backup|start") != "OK":
                raise AssertionError("failed to deny BACKUP START")
            expect_error(sock, "NOPERM User default has no permissions to run the 'backup|start' command", b"BACKUP", b"START")
            if send_command(sock, b"BACKUP", b"STATUS")[0] != b"state":
                raise AssertionError("BACKUP STATUS should remain allowed")
            if send_command(sock, b"ACL", b"SETUSER", b"default", b"+backup|start") != "OK":
                raise AssertionError("failed to restore BACKUP START")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        aof_path.unlink(missing_ok=True)
        rewritten_config.unlink(missing_ok=True)
        shutil.rmtree(backup_dir, ignore_errors=True)
        shutil.rmtree(restore_root, ignore_errors=True)


if __name__ == "__main__":
    run_smoke()
    print("backup smoke ok")
