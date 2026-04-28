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


def roundtrip(sock: socket.socket, request: bytes, expected: bytes) -> None:
    sock.sendall(request)
    actual = recv_exact(sock, len(expected))
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def crash_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5.0)


def wait_for_rewrite_replace(aof_path: Path, deadline: float) -> None:
    rewrite_tmp = Path(str(aof_path) + ".tmp")
    rewrite_tmp_tmp = Path(str(aof_path) + ".tmp.tmp")
    while time.monotonic() < deadline:
        if aof_path.exists():
            payload = aof_path.read_bytes()
            if b"obsolete" not in payload and b"newer" in payload:
                if not rewrite_tmp.exists() and not rewrite_tmp_tmp.exists():
                    return
        time.sleep(0.05)
    raise RuntimeError("BGREWRITEAOF did not replace AOF in time")


def start_server(port: int, aof_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def set_request(key: bytes, value: bytes) -> bytes:
    return (
        b"*3\r\n"
        + b"$3\r\nSET\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
        + f"${len(value)}\r\n".encode()
        + value
        + b"\r\n"
    )


def get_request(key: bytes) -> bytes:
    return (
        b"*2\r\n"
        + b"$3\r\nGET\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
    )


def run_case_aof_only() -> None:
    port = find_free_port()
    aof_path = ROOT / "build" / f"crash-aof-only-{port}.aof"
    rdb_path = ROOT / "build" / "dump.rdb"
    aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)

    proc = start_server(port, aof_path)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            roundtrip(sock, set_request(b"key", b"value"), b"+OK\r\n")
        crash_process(proc)

        proc = start_server(port, aof_path)
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            roundtrip(sock, get_request(b"key"), b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nQUIT\r\n", b"+OK\r\n")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def run_case_rewrite_in_progress() -> None:
    port = find_free_port()
    aof_path = ROOT / "build" / f"crash-rewrite-progress-{port}.aof"
    rdb_path = ROOT / "build" / "dump.rdb"
    aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)

    proc = start_server(port, aof_path)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            for i in range(512):
                roundtrip(sock, set_request(f"k{i}".encode(), b"value"), b"+OK\r\n")
            roundtrip(sock, set_request(b"key", b"obsolete"), b"+OK\r\n")
            roundtrip(sock, set_request(b"key", b"base"), b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$12\r\nBGREWRITEAOF\r\n", b"+Background AOF rewrite scheduled\r\n")
            roundtrip(sock, set_request(b"key", b"newer"), b"+OK\r\n")
            roundtrip(sock, set_request(b"extra", b"value"), b"+OK\r\n")

        crash_process(proc)

        proc = start_server(port, aof_path)
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            roundtrip(sock, get_request(b"key"), b"$5\r\nnewer\r\n")
            roundtrip(sock, get_request(b"extra"), b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nQUIT\r\n", b"+OK\r\n")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def run_case_rewrite_completed() -> None:
    port = find_free_port()
    aof_path = ROOT / "build" / f"crash-rewrite-complete-{port}.aof"
    rdb_path = ROOT / "build" / "dump.rdb"
    aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)

    proc = start_server(port, aof_path)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            for i in range(8):
                roundtrip(sock, set_request(f"k{i}".encode(), b"value"), b"+OK\r\n")
            roundtrip(sock, set_request(b"key", b"obsolete"), b"+OK\r\n")
            roundtrip(sock, set_request(b"key", b"base"), b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$12\r\nBGREWRITEAOF\r\n", b"+Background AOF rewrite scheduled\r\n")
            roundtrip(sock, set_request(b"key", b"newer"), b"+OK\r\n")

        wait_for_rewrite_replace(aof_path, time.monotonic() + 5.0)
        crash_process(proc)

        proc = start_server(port, aof_path)
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            roundtrip(sock, get_request(b"key"), b"$5\r\nnewer\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nQUIT\r\n", b"+OK\r\n")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    run_case_aof_only()
    run_case_rewrite_in_progress()
    run_case_rewrite_completed()


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/persistence_crash_matrix: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/persistence_crash_matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
