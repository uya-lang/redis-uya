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


HELLO3_REPLY = (
    b"%7\r\n"
    b"$6\r\nserver\r\n$9\r\nredis-uya\r\n"
    b"$7\r\nversion\r\n$9\r\n0.1.0-dev\r\n"
    b"$5\r\nproto\r\n:3\r\n"
    b"$2\r\nid\r\n:0\r\n"
    b"$4\r\nmode\r\n$10\r\nstandalone\r\n"
    b"$4\r\nrole\r\n$6\r\nmaster\r\n"
    b"$7\r\nmodules\r\n*0\r\n"
)

HELLO2_REPLY = (
    b"*14\r\n"
    b"$6\r\nserver\r\n$9\r\nredis-uya\r\n"
    b"$7\r\nversion\r\n$9\r\n0.1.0-dev\r\n"
    b"$5\r\nproto\r\n:2\r\n"
    b"$2\r\nid\r\n:0\r\n"
    b"$4\r\nmode\r\n$10\r\nstandalone\r\n"
    b"$4\r\nrole\r\n$6\r\nmaster\r\n"
    b"$7\r\nmodules\r\n*0\r\n"
)


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"smoke-{port}.aof"
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
            sock.settimeout(2.0)
            roundtrip(sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nHELLO\r\n$1\r\n3\r\n", HELLO3_REPLY)
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$7\r\nmissing\r\n", b"_\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nHELLO\r\n$1\r\n2\r\n", HELLO2_REPLY)
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$7\r\nmissing\r\n", b"$-1\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nHELLO\r\n$1\r\n4\r\n", b"-NOPROTO unsupported protocol version\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*1\r\n$5\r\nMULTI\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$4\r\nmkey\r\n$4\r\nmval\r\n", b"+QUEUED\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$4\r\nmkey\r\n", b"+QUEUED\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nEXEC\r\n", b"*2\r\n+OK\r\n$4\r\nmval\r\n")
            roundtrip(sock, b"*1\r\n$5\r\nMULTI\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$4\r\ndkey\r\n$4\r\ndval\r\n", b"+QUEUED\r\n")
            roundtrip(sock, b"*1\r\n$7\r\nDISCARD\r\n", b"+OK\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$4\r\ndkey\r\n", b"$-1\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nWATCH\r\n$4\r\nmkey\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$5\r\nMULTI\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$4\r\nmkey\r\n$3\r\ntxn\r\n", b"+QUEUED\r\n")
            with connect_with_retry(port, time.monotonic() + 5.0) as other_sock:
                other_sock.settimeout(2.0)
                roundtrip(other_sock, b"*3\r\n$3\r\nSET\r\n$4\r\nmkey\r\n$7\r\noutside\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nEXEC\r\n", b"*-1\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$4\r\nmkey\r\n", b"$7\r\noutside\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nWATCH\r\n$4\r\nmkey\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$7\r\nUNWATCH\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$5\r\nMULTI\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$4\r\nmkey\r\n$2\r\nok\r\n", b"+QUEUED\r\n")
            with connect_with_retry(port, time.monotonic() + 5.0) as other_sock:
                other_sock.settimeout(2.0)
                roundtrip(other_sock, b"*3\r\n$3\r\nSET\r\n$4\r\nmkey\r\n$5\r\nother\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nEXEC\r\n", b"*1\r\n+OK\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$4\r\nmkey\r\n", b"$2\r\nok\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nSAVE\r\n", b"+OK\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nHSET\r\n$4\r\nhash\r\n$5\r\nfield\r\n$5\r\nvalue\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nHGET\r\n$4\r\nhash\r\n$5\r\nfield\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nLPUSH\r\n$4\r\nlist\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$4\r\nlist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*3\r\n$1\r\nc\r\n$1\r\nb\r\n$1\r\na\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nLPOP\r\n$4\r\nlist\r\n", b"$1\r\nc\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nSADD\r\n$3\r\nset\r\n$1\r\na\r\n$1\r\nb\r\n", b":2\r\n")
            sock.sendall(b"*2\r\n$8\r\nSMEMBERS\r\n$3\r\nset\r\n")
            actual = recv_exact(sock, len(b"*2\r\n$1\r\nb\r\n$1\r\na\r\n"))
            if actual not in (b"*2\r\n$1\r\na\r\n$1\r\nb\r\n", b"*2\r\n$1\r\nb\r\n$1\r\na\r\n"):
                raise AssertionError(f"unexpected SMEMBERS reply: {actual!r}")
            roundtrip(sock, b"*6\r\n$4\r\nZADD\r\n$4\r\nzset\r\n$1\r\n2\r\n$1\r\nb\r\n$1\r\n1\r\n$1\r\na\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzset\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*2\r\n$1\r\na\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nZREM\r\n$4\r\nzset\r\n$1\r\na\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzset\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*1\r\n$1\r\nb\r\n")
            roundtrip(
                sock,
                b"*4\r\n$4\r\nSCAN\r\n$1\r\n0\r\n$5\r\nCOUNT\r\n$2\r\n10\r\n",
                b"*2\r\n$1\r\n0\r\n*6\r\n$4\r\nhash\r\n$3\r\nkey\r\n$4\r\nlist\r\n$4\r\nmkey\r\n$3\r\nset\r\n$4\r\nzset\r\n",
            )
            roundtrip(sock, b"*1\r\n$12\r\nBGREWRITEAOF\r\n", b"+Background AOF rewrite scheduled\r\n")
            config_port_expected = f"*2\r\n$4\r\nport\r\n${len(str(port))}\r\n{port}\r\n".encode()
            roundtrip(sock, b"*3\r\n$6\r\nCONFIG\r\n$3\r\nGET\r\n$4\r\nport\r\n", config_port_expected)
            roundtrip(sock, b"*2\r\n$6\r\nEXISTS\r\n$3\r\nkey\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$3\r\nkey\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$6\r\nEXISTS\r\n$3\r\nkey\r\n", b":0\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nQUIT\r\n", b"+OK\r\n")

        stop_process(proc)
        if proc.returncode not in (0, -15):
            stdout, stderr = proc.communicate()
            raise RuntimeError(
                f"redis-uya exited with {proc.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)
        rdb_path.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/smoke_tcp: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/smoke_tcp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
