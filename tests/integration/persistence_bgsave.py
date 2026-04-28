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


def roundtrip_one_of(sock: socket.socket, request: bytes, expected_options: tuple[bytes, ...]) -> None:
    sock.sendall(request)
    size = len(expected_options[0])
    actual = recv_exact(sock, size)
    if actual not in expected_options:
        raise AssertionError(f"expected one of {expected_options!r}, got {actual!r}")


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def start_server(port: int, aof_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"bgsave-{port}.aof"
    rdb_path = ROOT / "build" / "dump.rdb"
    aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)

    proc = start_server(port, aof_path)
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nHSET\r\n$4\r\nhash\r\n$5\r\nfield\r\n$5\r\nvalue\r\n", b":1\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nLPUSH\r\n$4\r\nlist\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nSADD\r\n$3\r\nset\r\n$1\r\na\r\n$1\r\nb\r\n", b":2\r\n")
            roundtrip(sock, b"*6\r\n$4\r\nZADD\r\n$4\r\nzset\r\n$1\r\n2\r\n$1\r\nb\r\n$1\r\n1\r\n$1\r\na\r\n", b":2\r\n")
            roundtrip(sock, b"*1\r\n$6\r\nBGSAVE\r\n", b"+Background saving scheduled\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n", b"$5\r\nvalue\r\n")

            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if rdb_path.exists():
                    payload = rdb_path.read_bytes()
                    if payload.startswith(b"RUYARDB1"):
                        break
                time.sleep(0.05)
            else:
                raise RuntimeError("BGSAVE did not produce a valid dump.rdb in time")

            roundtrip(sock, b"*1\r\n$4\r\nQUIT\r\n", b"+OK\r\n")

        stop_process(proc)
        if proc.returncode not in (0, -15):
            stdout, stderr = proc.communicate()
            raise RuntimeError(
                f"redis-uya exited with {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )

        aof_path.unlink(missing_ok=True)

        proc = start_server(port, aof_path)
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nHGET\r\n$4\r\nhash\r\n$5\r\nfield\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$4\r\nlist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*3\r\n$1\r\nc\r\n$1\r\nb\r\n$1\r\na\r\n")
            roundtrip_one_of(
                sock,
                b"*2\r\n$8\r\nSMEMBERS\r\n$3\r\nset\r\n",
                (b"*2\r\n$1\r\na\r\n$1\r\nb\r\n", b"*2\r\n$1\r\nb\r\n$1\r\na\r\n"),
            )
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzset\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*2\r\n$1\r\na\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nQUIT\r\n", b"+OK\r\n")
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/persistence_bgsave: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/persistence_bgsave")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
