#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from cluster_smoke import (
    BIN,
    ROOT,
    RespError,
    connect_with_retry,
    find_free_port,
    send_command,
    stop_process,
)


def expect_error(sock, expected: str, *parts: bytes) -> None:
    try:
        send_command(sock, *parts)
    except RespError as exc:
        if str(exc) != expected:
            raise AssertionError(f"expected {expected!r}, got {str(exc)!r}") from exc
        return
    raise AssertionError(f"expected RESP error {expected!r}")


def node_line(nodes: bytes, needle: bytes) -> bytes:
    lines = [line for line in nodes.splitlines() if needle in line]
    if len(lines) != 1:
        raise AssertionError(f"expected one node line matching {needle!r}, got {nodes!r}")
    return lines[0]


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    remote_port = port + 1
    aof_path = ROOT / "build" / f"cluster-consistency-{port}.aof"
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
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            if send_command(sock, b"SET", b"local-key", b"local-value") != "OK":
                raise AssertionError("local SET did not return OK")
            if send_command(sock, b"GET", b"local-key") != b"local-value":
                raise AssertionError("local key was not readable before cluster changes")

            if send_command(sock, b"CLUSTER", b"MEET", b"127.0.0.2", str(remote_port).encode()) != "OK":
                raise AssertionError("CLUSTER MEET did not return OK")

            nodes_after_meet = send_command(sock, b"CLUSTER", b"NODES")
            if not isinstance(nodes_after_meet, bytes):
                raise AssertionError(f"CLUSTER NODES returned non-bulk value: {nodes_after_meet!r}")
            local_id = node_line(nodes_after_meet, f"127.0.0.1:{port}".encode()).split()[0]
            remote_id = node_line(nodes_after_meet, f"127.0.0.2:{remote_port}".encode()).split()[0]

            if send_command(sock, b"CLUSTER", b"SETSLOT", b"12182", b"NODE", remote_id) != "OK":
                raise AssertionError("CLUSTER SETSLOT NODE did not return OK")

            nodes_after_node = send_command(sock, b"CLUSTER", b"NODES")
            if not isinstance(nodes_after_node, bytes):
                raise AssertionError(f"CLUSTER NODES after SETSLOT returned non-bulk value: {nodes_after_node!r}")
            local_line = node_line(nodes_after_node, f"127.0.0.1:{port}".encode())
            remote_line = node_line(nodes_after_node, f"127.0.0.2:{remote_port}".encode())
            if b"0-12181" not in local_line or b"12183-16383" not in local_line:
                raise AssertionError(f"local slot ranges were not split around remote slot: {local_line!r}")
            if not remote_line.endswith(b" 12182"):
                raise AssertionError(f"remote slot owner line missing slot 12182: {remote_line!r}")

            moved = f"MOVED 12182 127.0.0.2:{remote_port}"
            expect_error(sock, moved, b"SET", b"foo", b"remote-value")
            expect_error(sock, moved, b"GET", b"foo")

            if send_command(sock, b"CLUSTER", b"SETSLOT", b"5061", b"MIGRATING", remote_id) != "OK":
                raise AssertionError("CLUSTER SETSLOT MIGRATING did not return OK")
            ask = f"ASK 5061 127.0.0.2:{remote_port}"
            expect_error(sock, ask, b"SET", b"foo{bar}zap", b"migrating-value")
            expect_error(sock, ask, b"GET", b"foo{bar}zap")

            if send_command(sock, b"CLUSTER", b"SETSLOT", b"5061", b"STABLE") != "OK":
                raise AssertionError("CLUSTER SETSLOT STABLE did not return OK")
            if send_command(sock, b"SET", b"foo{bar}zap", b"local-hash-value") != "OK":
                raise AssertionError("local SET after STABLE did not return OK")
            if send_command(sock, b"GET", b"foo{bar}zap") != b"local-hash-value":
                raise AssertionError("STABLE did not restore local access for migrating slot")

            if send_command(sock, b"CLUSTER", b"SETSLOT", b"12182", b"NODE", local_id) != "OK":
                raise AssertionError("CLUSTER SETSLOT back to local node did not return OK")
            if send_command(sock, b"GET", b"foo") is not None:
                raise AssertionError("redirected SET unexpectedly wrote the remote-owned key locally")

        stop_process(proc)
        if proc.returncode not in (0, -15):
            stdout, stderr = proc.communicate()
            raise RuntimeError(
                f"redis-uya exited with {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )

        aof_data = aof_path.read_bytes()
        if b"local-value" not in aof_data or b"local-hash-value" not in aof_data:
            raise AssertionError(f"AOF missing successful local writes: {aof_data!r}")
        for forbidden in (b"remote-value", b"migrating-value"):
            if forbidden in aof_data:
                raise AssertionError(f"redirected write leaked into AOF: {forbidden!r}")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run_smoke()
    print("cluster consistency smoke passed")
