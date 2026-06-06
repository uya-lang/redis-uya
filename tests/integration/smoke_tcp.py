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


def recv_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed before line response")
        chunks.append(chunk)
        if len(chunks) >= 2 and chunks[-2] == b"\r" and chunks[-1] == b"\n":
            return b"".join(chunks)


def recv_bulk(sock: socket.socket) -> bytes | None:
    header = recv_line(sock)
    if header == b"$-1\r\n":
        return None
    if not header.startswith(b"$") or not header.endswith(b"\r\n"):
        raise AssertionError(f"unexpected bulk header: {header!r}")
    size = int(header[1:-2])
    payload = recv_exact(sock, size + 2)
    if payload[-2:] != b"\r\n":
        raise AssertionError(f"unexpected bulk payload terminator: {payload!r}")
    return payload[:-2]


def roundtrip(sock: socket.socket, request: bytes, expected: bytes) -> None:
    sock.sendall(request)
    actual = recv_exact(sock, len(expected))
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


REDIS_UYA_VERSION = b"v0.9.1-dev"

HELLO3_REPLY = (
    b"%7\r\n"
    b"$6\r\nserver\r\n$9\r\nredis-uya\r\n"
    b"$7\r\nversion\r\n$10\r\n" + REDIS_UYA_VERSION + b"\r\n"
    b"$5\r\nproto\r\n:3\r\n"
    b"$2\r\nid\r\n:0\r\n"
    b"$4\r\nmode\r\n$10\r\nstandalone\r\n"
    b"$4\r\nrole\r\n$6\r\nmaster\r\n"
    b"$7\r\nmodules\r\n*0\r\n"
)

HELLO2_REPLY = (
    b"*14\r\n"
    b"$6\r\nserver\r\n$9\r\nredis-uya\r\n"
    b"$7\r\nversion\r\n$10\r\n" + REDIS_UYA_VERSION + b"\r\n"
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
    auth_port = find_free_port()
    auth_aof_path = ROOT / "build" / f"smoke-auth-{auth_port}.aof"
    rdb_path = ROOT / "build" / "dump.rdb"
    aof_path.unlink(missing_ok=True)
    auth_aof_path.unlink(missing_ok=True)
    rdb_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    auth_proc: subprocess.Popen[str] | None = None
    try:
        with connect_with_retry(port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            roundtrip(sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nHELLO\r\n$1\r\n3\r\n", HELLO3_REPLY)
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$7\r\nmissing\r\n", b"_\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nHELLO\r\n$1\r\n2\r\n", HELLO2_REPLY)
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$7\r\nmissing\r\n", b"$-1\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nHELLO\r\n$1\r\n4\r\n", b"-NOPROTO unsupported protocol version\r\n")
            sock.sendall(b"*1\r\n$4\r\nTIME\r\n")
            time_header = recv_line(sock)
            if time_header != b"*2\r\n":
                raise AssertionError(f"unexpected TIME header: {time_header!r}")
            time_sec = recv_bulk(sock)
            time_usec = recv_bulk(sock)
            if not time_sec.isdigit() or not time_usec.isdigit():
                raise AssertionError(f"unexpected TIME payload: {(time_sec, time_usec)!r}")
            roundtrip(sock, b"*1\r\n$4\r\nROLE\r\n", b"*3\r\n$6\r\nmaster\r\n:0\r\n*0\r\n")
            roundtrip(sock, b"*1\r\n$8\r\nREPLCONF\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$8\r\nREPLCONF\r\n$4\r\nCAPA\r\n$6\r\npsync2\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$8\r\nREPLCONF\r\n$3\r\nACK\r\n$1\r\n0\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$9\r\nRANDOMKEY\r\n", b"$3\r\nkey\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nINCR\r\n$7\r\ncounter\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nINCRBY\r\n$7\r\ncounter\r\n$1\r\n4\r\n", b":5\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nDECR\r\n$7\r\ncounter\r\n", b":4\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nDECRBY\r\n$7\r\ncounter\r\n$1\r\n2\r\n", b":2\r\n")
            roundtrip(sock, b"*3\r\n$11\r\nINCRBYFLOAT\r\n$8\r\nfcounter\r\n$3\r\n1.5\r\n", b"$3\r\n1.5\r\n")
            roundtrip(sock, b"*3\r\n$11\r\nINCRBYFLOAT\r\n$8\r\nfcounter\r\n$1\r\n2\r\n", b"$3\r\n3.5\r\n")
            roundtrip(sock, b"*3\r\n$5\r\nSETNX\r\n$6\r\nnx-key\r\n$5\r\nfirst\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$5\r\nSETNX\r\n$6\r\nnx-key\r\n$6\r\nsecond\r\n", b":0\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nGETSET\r\n$6\r\ngs-key\r\n$5\r\nfirst\r\n", b"$-1\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nGETSET\r\n$6\r\ngs-key\r\n$6\r\nsecond\r\n", b"$5\r\nfirst\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nSETEX\r\n$6\r\nsx-key\r\n$1\r\n2\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*5\r\n$4\r\nMSET\r\n$3\r\nmk1\r\n$2\r\nv1\r\n$3\r\nmk2\r\n$2\r\nv2\r\n", b"+OK\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nMGET\r\n$3\r\nmk1\r\n$7\r\nmissing\r\n$3\r\nmk2\r\n", b"*3\r\n$2\r\nv1\r\n$-1\r\n$2\r\nv2\r\n")
            roundtrip(sock, b"*5\r\n$6\r\nMSETNX\r\n$3\r\nmn1\r\n$1\r\na\r\n$3\r\nmn2\r\n$1\r\nb\r\n", b":1\r\n")
            roundtrip(sock, b"*5\r\n$6\r\nMSETNX\r\n$3\r\nmn1\r\n$1\r\nx\r\n$3\r\nmn3\r\n$1\r\ny\r\n", b":0\r\n")
            roundtrip(sock, b"*2\r\n$6\r\nSTRLEN\r\n$3\r\nkey\r\n", b":5\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nAPPEND\r\n$3\r\nkey\r\n$2\r\n++\r\n", b":7\r\n")
            roundtrip(sock, b"*4\r\n$8\r\nGETRANGE\r\n$3\r\nkey\r\n$1\r\n1\r\n$1\r\n3\r\n", b"$3\r\nalu\r\n")
            roundtrip(sock, b"*4\r\n$8\r\nSETRANGE\r\n$3\r\nkey\r\n$1\r\n5\r\n$2\r\n__\r\n", b":7\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n", b"$7\r\nvalue__\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nRENAME\r\n$3\r\nkey\r\n$4\r\nkey2\r\n", b"+OK\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$4\r\nkey2\r\n", b"$7\r\nvalue__\r\n")
            roundtrip(sock, b"*3\r\n$8\r\nRENAMENX\r\n$4\r\nkey2\r\n$6\r\ngs-key\r\n", b":0\r\n")
            roundtrip(sock, b"*3\r\n$8\r\nRENAMENX\r\n$4\r\nkey2\r\n$3\r\nkey\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$6\r\ngd-key\r\n$4\r\nonce\r\n", b"+OK\r\n")
            roundtrip(sock, b"*2\r\n$6\r\nGETDEL\r\n$6\r\ngd-key\r\n", b"$4\r\nonce\r\n")
            roundtrip(sock, b"*2\r\n$6\r\nGETDEL\r\n$6\r\ngd-key\r\n", b"$-1\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$7\r\ncounter\r\n", b":1\r\n")
            roundtrip(sock, b"*8\r\n$3\r\nDEL\r\n$8\r\nfcounter\r\n$6\r\nnx-key\r\n$6\r\ngs-key\r\n$3\r\nmk1\r\n$3\r\nmk2\r\n$3\r\nmn1\r\n$3\r\nmn2\r\n", b":7\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$6\r\nsx-key\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nECHO\r\n$2\r\nhi\r\n", b"$2\r\nhi\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nTYPE\r\n$3\r\nkey\r\n", b"+string\r\n")
            roundtrip(sock, b"*1\r\n$6\r\nDBSIZE\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$6\r\nSELECT\r\n$1\r\n0\r\n", b"+OK\r\n")
            sock.sendall(b"*2\r\n$6\r\nSELECT\r\n$1\r\n1\r\n")
            select_bad_reply = recv_line(sock)
            if select_bad_reply != b"-ERR DB index is out of range\r\n":
                raise AssertionError(f"unexpected SELECT reply: {select_bad_reply!r}")
            roundtrip(sock, b"*3\r\n$6\r\nOBJECT\r\n$8\r\nENCODING\r\n$3\r\nkey\r\n", b"$3\r\nraw\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nOBJECT\r\n$8\r\nREFCOUNT\r\n$3\r\nkey\r\n", b":1\r\n")
            sock.sendall(b"*3\r\n$6\r\nOBJECT\r\n$4\r\nFREQ\r\n$3\r\nkey\r\n")
            object_freq_reply = recv_line(sock)
            if not object_freq_reply.startswith(b"-ERR An LFU maxmemory policy is not selected"):
                raise AssertionError(f"unexpected OBJECT FREQ reply: {object_freq_reply!r}")
            sock.sendall(b"*3\r\n$4\r\nMOVE\r\n$3\r\nkey\r\n$1\r\n0\r\n")
            move_same_reply = recv_line(sock)
            if move_same_reply != b"-ERR source and destination objects are the same\r\n":
                raise AssertionError(f"unexpected MOVE same-db reply: {move_same_reply!r}")
            sock.sendall(b"*3\r\n$4\r\nMOVE\r\n$3\r\nkey\r\n$1\r\n1\r\n")
            move_range_reply = recv_line(sock)
            if move_range_reply != b"-ERR DB index is out of range\r\n":
                raise AssertionError(f"unexpected MOVE range reply: {move_range_reply!r}")
            roundtrip(sock, b"*3\r\n$6\r\nSWAPDB\r\n$1\r\n0\r\n$1\r\n0\r\n", b"+OK\r\n")
            sock.sendall(b"*3\r\n$6\r\nSWAPDB\r\n$1\r\n0\r\n$1\r\n1\r\n")
            swapdb_range_reply = recv_line(sock)
            if swapdb_range_reply != b"-ERR DB index is out of range\r\n":
                raise AssertionError(f"unexpected SWAPDB range reply: {swapdb_range_reply!r}")
            sock.sendall(b"*3\r\n$6\r\nSWAPDB\r\n$3\r\nbad\r\n$1\r\n0\r\n")
            swapdb_bad_reply = recv_line(sock)
            if swapdb_bad_reply != b"-ERR value is not an integer or out of range\r\n":
                raise AssertionError(f"unexpected SWAPDB bad integer reply: {swapdb_bad_reply!r}")
            sock.sendall(b"*1\r\n$6\r\nLOLWUT\r\n")
            lolwut_reply = recv_bulk(sock)
            if lolwut_reply is None or b"Redis ver. v0.9.1-dev" not in lolwut_reply:
                raise AssertionError(f"unexpected LOLWUT reply: {lolwut_reply!r}")
            sock.sendall(b"*3\r\n$6\r\nLOLWUT\r\n$7\r\nVERSION\r\n$1\r\n5\r\n")
            lolwut_version_reply = recv_bulk(sock)
            if lolwut_version_reply is None or b"Redis-compatible" not in lolwut_version_reply:
                raise AssertionError(f"unexpected LOLWUT VERSION reply: {lolwut_version_reply!r}")
            sock.sendall(b"*3\r\n$6\r\nLOLWUT\r\n$7\r\nVERSION\r\n$3\r\nbad\r\n")
            lolwut_bad_reply = recv_line(sock)
            if lolwut_bad_reply != b"-ERR value is not an integer or out of range\r\n":
                raise AssertionError(f"unexpected LOLWUT bad integer reply: {lolwut_bad_reply!r}")
            sock.sendall(b"*2\r\n$5\r\nDEBUG\r\n$4\r\nHELP\r\n")
            debug_reply = recv_line(sock)
            if debug_reply != b"-ERR DEBUG command not allowed by redis-uya standalone profile\r\n":
                raise AssertionError(f"unexpected DEBUG reply: {debug_reply!r}")
            sock.sendall(b"*1\r\n$8\r\nFAILOVER\r\n")
            failover_reply = recv_line(sock)
            if failover_reply != b"-ERR FAILOVER requires connected replicas.\r\n":
                raise AssertionError(f"unexpected FAILOVER reply: {failover_reply!r}")
            roundtrip(sock, b"*1\r\n$10\r\nPFSELFTEST\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$7\r\nPFDEBUG\r\n$6\r\nGETREG\r\n$3\r\nhll\r\n", b"-ERR PFDEBUG command not allowed by redis-uya standalone profile\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nWAIT\r\n$1\r\n0\r\n$1\r\n0\r\n", b":0\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nWAIT\r\n$1\r\n1\r\n$2\r\n10\r\n", b":0\r\n")
            sock.sendall(b"*3\r\n$4\r\nWAIT\r\n$1\r\n1\r\n$2\r\n-1\r\n")
            wait_negative_reply = recv_line(sock)
            if wait_negative_reply != b"-ERR timeout is negative\r\n":
                raise AssertionError(f"unexpected WAIT negative reply: {wait_negative_reply!r}")
            roundtrip(sock, b"*4\r\n$7\r\nWAITAOF\r\n$1\r\n1\r\n$1\r\n0\r\n$1\r\n0\r\n", b"*2\r\n:1\r\n:0\r\n")
            roundtrip(sock, b"*4\r\n$7\r\nWAITAOF\r\n$1\r\n0\r\n$1\r\n0\r\n$1\r\n0\r\n", b"*2\r\n:0\r\n:0\r\n")
            roundtrip(sock, b"*4\r\n$7\r\nWAITAOF\r\n$1\r\n1\r\n$1\r\n1\r\n$2\r\n10\r\n", b"*2\r\n:1\r\n:0\r\n")
            sock.sendall(b"*4\r\n$7\r\nWAITAOF\r\n$1\r\n1\r\n$1\r\n0\r\n$2\r\n-1\r\n")
            waitaof_negative_reply = recv_line(sock)
            if waitaof_negative_reply != b"-ERR timeout is negative\r\n":
                raise AssertionError(f"unexpected WAITAOF negative reply: {waitaof_negative_reply!r}")
            roundtrip(sock, b"*5\r\n$5\r\nRPUSH\r\n$8\r\nsortnums\r\n$1\r\n3\r\n$1\r\n1\r\n$1\r\n2\r\n", b":3\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nSORT\r\n$8\r\nsortnums\r\n", b"*3\r\n$1\r\n1\r\n$1\r\n2\r\n$1\r\n3\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$7\r\nsortw_1\r\n$2\r\n20\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$7\r\nsortw_2\r\n$2\r\n10\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$7\r\nsortw_3\r\n$2\r\n30\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$5\r\nobj_1\r\n$3\r\none\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$5\r\nobj_2\r\n$3\r\ntwo\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$5\r\nobj_3\r\n$5\r\nthree\r\n", b"+OK\r\n")
            roundtrip(sock, b"*8\r\n$4\r\nSORT\r\n$8\r\nsortnums\r\n$2\r\nBY\r\n$7\r\nsortw_*\r\n$3\r\nGET\r\n$5\r\nobj_*\r\n$3\r\nGET\r\n$1\r\n#\r\n", b"*6\r\n$3\r\ntwo\r\n$1\r\n2\r\n$3\r\none\r\n$1\r\n1\r\n$5\r\nthree\r\n$1\r\n3\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nSORT\r\n$8\r\nsortnums\r\n$5\r\nSTORE\r\n$7\r\nsortout\r\n", b":3\r\n")
            roundtrip(sock, b"*2\r\n$7\r\nSORT_RO\r\n$8\r\nsortnums\r\n", b"*3\r\n$1\r\n1\r\n$1\r\n2\r\n$1\r\n3\r\n")
            roundtrip(sock, b"*4\r\n$7\r\nSORT_RO\r\n$8\r\nsortnums\r\n$5\r\nSTORE\r\n$7\r\nsortout\r\n", b"-ERR syntax error\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$7\r\nsortout\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*3\r\n$1\r\n1\r\n$1\r\n2\r\n$1\r\n3\r\n")
            roundtrip(sock, b"*9\r\n$3\r\nDEL\r\n$8\r\nsortnums\r\n$7\r\nsortout\r\n$7\r\nsortw_1\r\n$7\r\nsortw_2\r\n$7\r\nsortw_3\r\n$5\r\nobj_1\r\n$5\r\nobj_2\r\n$5\r\nobj_3\r\n", b":8\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$3\r\nttl\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$7\r\nPEXPIRE\r\n$3\r\nttl\r\n$1\r\n0\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nPTTL\r\n$3\r\nttl\r\n", b":-2\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$4\r\nkeep\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nEXPIRE\r\n$4\r\nkeep\r\n$1\r\n5\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$7\r\nPERSIST\r\n$4\r\nkeep\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nPTTL\r\n$4\r\nkeep\r\n", b":-1\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$4\r\nkeep\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$3\r\nsec\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            sec_deadline = int(time.time()) + 4
            sec_deadline_bytes = str(sec_deadline).encode()
            sec_request = (
                b"*3\r\n$8\r\nEXPIREAT\r\n$3\r\nsec\r\n$"
                + str(len(sec_deadline_bytes)).encode()
                + b"\r\n"
                + sec_deadline_bytes
                + b"\r\n"
            )
            roundtrip(sock, sec_request, b":1\r\n")
            roundtrip(sock, b"*2\r\n$10\r\nEXPIRETIME\r\n$3\r\nsec\r\n", f":{sec_deadline}\r\n".encode())
            roundtrip(sock, b"*2\r\n$11\r\nPEXPIRETIME\r\n$3\r\nsec\r\n", f":{sec_deadline * 1000}\r\n".encode())
            roundtrip(sock, b"*2\r\n$5\r\nGETEX\r\n$3\r\nsec\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*3\r\n$5\r\nGETEX\r\n$3\r\nsec\r\n$7\r\nPERSIST\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*2\r\n$10\r\nEXPIRETIME\r\n$3\r\nsec\r\n", b":-1\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$5\r\npxkey\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nGETEX\r\n$5\r\npxkey\r\n$2\r\nPX\r\n$4\r\n1200\r\n", b"$5\r\nvalue\r\n")
            sock.sendall(b"*2\r\n$4\r\nPTTL\r\n$5\r\npxkey\r\n")
            pxkey_pttl_reply = recv_line(sock)
            if not pxkey_pttl_reply.startswith(b":"):
                raise AssertionError(f"unexpected pxkey PTTL reply: {pxkey_pttl_reply!r}")
            pxkey_pttl = int(pxkey_pttl_reply[1:-2])
            if pxkey_pttl <= 0 or pxkey_pttl > 1200:
                raise AssertionError(f"unexpected pxkey PTTL value: {pxkey_pttl}")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$5\r\naxkey\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            ax_deadline = int(time.time() * 1000) + 2500
            ax_deadline_bytes = str(ax_deadline).encode()
            ax_request = (
                b"*4\r\n$5\r\nGETEX\r\n$5\r\naxkey\r\n$4\r\nPXAT\r\n$"
                + str(len(ax_deadline_bytes)).encode()
                + b"\r\n"
                + ax_deadline_bytes
                + b"\r\n"
            )
            roundtrip(sock, ax_request, b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*2\r\n$11\r\nPEXPIRETIME\r\n$5\r\naxkey\r\n", f":{ax_deadline}\r\n".encode())
            roundtrip(sock, b"*4\r\n$6\r\nPSETEX\r\n$6\r\nps-key\r\n$4\r\n1500\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            sock.sendall(b"*2\r\n$4\r\nPTTL\r\n$6\r\nps-key\r\n")
            ps_key_pttl_reply = recv_line(sock)
            if not ps_key_pttl_reply.startswith(b":"):
                raise AssertionError(f"unexpected ps-key PTTL reply: {ps_key_pttl_reply!r}")
            ps_key_pttl = int(ps_key_pttl_reply[1:-2])
            if ps_key_pttl <= 0 or ps_key_pttl > 1500:
                raise AssertionError(f"unexpected ps-key PTTL value: {ps_key_pttl}")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$3\r\nabs\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            abs_deadline = int(time.time() * 1000) + 4500
            abs_deadline_bytes = str(abs_deadline).encode()
            request = (
                b"*3\r\n$9\r\nPEXPIREAT\r\n$3\r\nabs\r\n$"
                + str(len(abs_deadline_bytes)).encode()
                + b"\r\n"
                + abs_deadline_bytes
                + b"\r\n"
            )
            roundtrip(sock, request, b":1\r\n")
            sock.sendall(b"*2\r\n$3\r\nTTL\r\n$3\r\nabs\r\n")
            abs_ttl_reply = recv_line(sock)
            if abs_ttl_reply not in (b":3\r\n", b":4\r\n", b":5\r\n"):
                raise AssertionError(f"unexpected abs TTL reply: {abs_ttl_reply!r}")
            roundtrip(sock, b"*6\r\n$3\r\nDEL\r\n$3\r\nabs\r\n$3\r\nsec\r\n$5\r\npxkey\r\n$5\r\naxkey\r\n$6\r\nps-key\r\n", b":5\r\n")
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
            sock.sendall(b"*1\r\n$8\r\nLASTSAVE\r\n")
            lastsave_reply = recv_line(sock)
            if not (lastsave_reply.startswith(b":") and lastsave_reply.endswith(b"\r\n")):
                raise AssertionError(f"unexpected LASTSAVE reply: {lastsave_reply!r}")
            roundtrip(sock, b"*4\r\n$4\r\nHSET\r\n$4\r\nhash\r\n$5\r\nfield\r\n$5\r\nvalue\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nHGET\r\n$4\r\nhash\r\n$5\r\nfield\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*4\r\n$7\r\nHINCRBY\r\n$4\r\nhash\r\n$7\r\ncounter\r\n$1\r\n2\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$12\r\nHINCRBYFLOAT\r\n$4\r\nhash\r\n$5\r\nratio\r\n$3\r\n1.5\r\n", b"$3\r\n1.5\r\n")
            sock.sendall(b"*2\r\n$5\r\nHKEYS\r\n$4\r\nhash\r\n")
            hkeys_actual = recv_exact(sock, len(b"*3\r\n$7\r\ncounter\r\n$5\r\nfield\r\n$5\r\nratio\r\n"))
            if hkeys_actual not in (
                b"*3\r\n$7\r\ncounter\r\n$5\r\nfield\r\n$5\r\nratio\r\n",
                b"*3\r\n$5\r\nfield\r\n$5\r\nratio\r\n$7\r\ncounter\r\n",
                b"*3\r\n$5\r\nratio\r\n$7\r\ncounter\r\n$5\r\nfield\r\n",
                b"*3\r\n$5\r\nfield\r\n$7\r\ncounter\r\n$5\r\nratio\r\n",
                b"*3\r\n$7\r\ncounter\r\n$5\r\nratio\r\n$5\r\nfield\r\n",
                b"*3\r\n$5\r\nratio\r\n$5\r\nfield\r\n$7\r\ncounter\r\n",
            ):
                raise AssertionError(f"unexpected HKEYS reply: {hkeys_actual!r}")
            sock.sendall(b"*2\r\n$5\r\nHVALS\r\n$4\r\nhash\r\n")
            hvals_actual = recv_exact(sock, len(b"*3\r\n$1\r\n2\r\n$5\r\nvalue\r\n$3\r\n1.5\r\n"))
            if hvals_actual not in (
                b"*3\r\n$1\r\n2\r\n$5\r\nvalue\r\n$3\r\n1.5\r\n",
                b"*3\r\n$5\r\nvalue\r\n$3\r\n1.5\r\n$1\r\n2\r\n",
                b"*3\r\n$3\r\n1.5\r\n$1\r\n2\r\n$5\r\nvalue\r\n",
                b"*3\r\n$5\r\nvalue\r\n$1\r\n2\r\n$3\r\n1.5\r\n",
                b"*3\r\n$1\r\n2\r\n$3\r\n1.5\r\n$5\r\nvalue\r\n",
                b"*3\r\n$3\r\n1.5\r\n$5\r\nvalue\r\n$1\r\n2\r\n",
            ):
                raise AssertionError(f"unexpected HVALS reply: {hvals_actual!r}")
            sock.sendall(b"*2\r\n$7\r\nHGETALL\r\n$4\r\nhash\r\n")
            hgetall_actual = recv_exact(sock, len(b"*6\r\n$7\r\ncounter\r\n$1\r\n2\r\n$5\r\nfield\r\n$5\r\nvalue\r\n$5\r\nratio\r\n$3\r\n1.5\r\n"))
            if hgetall_actual != b"*6\r\n$7\r\ncounter\r\n$1\r\n2\r\n$5\r\nfield\r\n$5\r\nvalue\r\n$5\r\nratio\r\n$3\r\n1.5\r\n":
                raise AssertionError(f"unexpected HGETALL reply: {hgetall_actual!r}")
            roundtrip(sock, b"*2\r\n$10\r\nHRANDFIELD\r\n$4\r\nhash\r\n", b"$7\r\ncounter\r\n")
            roundtrip(sock, b"*3\r\n$10\r\nHRANDFIELD\r\n$4\r\nhash\r\n$1\r\n2\r\n", b"*2\r\n$7\r\ncounter\r\n$5\r\nfield\r\n")
            roundtrip(sock, b"*4\r\n$10\r\nHRANDFIELD\r\n$4\r\nhash\r\n$1\r\n2\r\n$10\r\nWITHVALUES\r\n", b"*4\r\n$7\r\ncounter\r\n$1\r\n2\r\n$5\r\nfield\r\n$5\r\nvalue\r\n")
            roundtrip(sock, b"*3\r\n$10\r\nHRANDFIELD\r\n$4\r\nhash\r\n$2\r\n-4\r\n", b"*4\r\n$7\r\ncounter\r\n$5\r\nfield\r\n$5\r\nratio\r\n$7\r\ncounter\r\n")
            roundtrip(sock, b"*3\r\n$7\r\nHEXISTS\r\n$4\r\nhash\r\n$5\r\nfield\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nHLEN\r\n$4\r\nhash\r\n", b":3\r\n")
            roundtrip(sock, b"*3\r\n$7\r\nHSTRLEN\r\n$4\r\nhash\r\n$5\r\nfield\r\n", b":5\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nHMGET\r\n$4\r\nhash\r\n$5\r\nfield\r\n$7\r\nmissing\r\n$7\r\ncounter\r\n", b"*3\r\n$5\r\nvalue\r\n$-1\r\n$1\r\n2\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nHSETNX\r\n$4\r\nhash\r\n$5\r\nextra\r\n$5\r\nvalue\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nHSETNX\r\n$4\r\nhash\r\n$5\r\nfield\r\n$4\r\nnext\r\n", b":0\r\n")
            roundtrip(sock, b"*5\r\n$4\r\nHDEL\r\n$4\r\nhash\r\n$5\r\nfield\r\n$7\r\ncounter\r\n$5\r\nextra\r\n", b":3\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nHLEN\r\n$4\r\nhash\r\n", b":1\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nHSCAN\r\n$4\r\nhash\r\n$1\r\n0\r\n$5\r\nCOUNT\r\n$2\r\n16\r\n", b"*2\r\n$1\r\n0\r\n*2\r\n$5\r\nratio\r\n$3\r\n1.5\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nLPUSH\r\n$4\r\nlist\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$4\r\nlist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*3\r\n$1\r\nc\r\n$1\r\nb\r\n$1\r\na\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nLPOP\r\n$4\r\nlist\r\n", b"$1\r\nc\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nRPUSH\r\n$5\r\nrlist\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nLLEN\r\n$5\r\nrlist\r\n", b":3\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nLINDEX\r\n$5\r\nrlist\r\n$1\r\n0\r\n", b"$1\r\na\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nLINDEX\r\n$5\r\nrlist\r\n$2\r\n-1\r\n", b"$1\r\nc\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nLSET\r\n$5\r\nrlist\r\n$1\r\n1\r\n$3\r\nmid\r\n", b"+OK\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$5\r\nrlist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*3\r\n$1\r\na\r\n$3\r\nmid\r\n$1\r\nc\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nRPOP\r\n$5\r\nrlist\r\n", b"$1\r\nc\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nLLEN\r\n$5\r\nrlist\r\n", b":2\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$5\r\nrlist\r\n", b":1\r\n")
            roundtrip(sock, b"*7\r\n$5\r\nRPUSH\r\n$5\r\nwlist\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n$1\r\nb\r\n$1\r\nd\r\n", b":5\r\n")
            roundtrip(sock, b"*5\r\n$7\r\nLINSERT\r\n$5\r\nwlist\r\n$6\r\nBEFORE\r\n$1\r\nc\r\n$1\r\nx\r\n", b":6\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$5\r\nwlist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*6\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nx\r\n$1\r\nc\r\n$1\r\nb\r\n$1\r\nd\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nLREM\r\n$5\r\nwlist\r\n$1\r\n1\r\n$1\r\nb\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$5\r\nwlist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*5\r\n$1\r\na\r\n$1\r\nx\r\n$1\r\nc\r\n$1\r\nb\r\n$1\r\nd\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nLTRIM\r\n$5\r\nwlist\r\n$1\r\n1\r\n$1\r\n3\r\n", b"+OK\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$5\r\nwlist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*3\r\n$1\r\nx\r\n$1\r\nc\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$5\r\nwlist\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nRPUSH\r\n$5\r\nxlist\r\n$1\r\na\r\n$1\r\nb\r\n", b":2\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nLPUSHX\r\n$7\r\nmissing\r\n$1\r\nz\r\n", b":0\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nLPUSHX\r\n$5\r\nxlist\r\n$4\r\nhead\r\n", b":3\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nRPUSHX\r\n$5\r\nxlist\r\n$4\r\ntail\r\n", b":4\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nLPOS\r\n$5\r\nxlist\r\n$1\r\nb\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$5\r\nxlist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*4\r\n$4\r\nhead\r\n$1\r\na\r\n$1\r\nb\r\n$4\r\ntail\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$5\r\nxlist\r\n", b":1\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nRPUSH\r\n$3\r\nsrc\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*3\r\n$9\r\nRPOPLPUSH\r\n$3\r\nsrc\r\n$3\r\ndst\r\n", b"$1\r\nc\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nLMOVE\r\n$3\r\nsrc\r\n$3\r\ndst\r\n$4\r\nLEFT\r\n$5\r\nRIGHT\r\n", b"$1\r\na\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nLMOVE\r\n$3\r\ndst\r\n$3\r\ndst\r\n$5\r\nRIGHT\r\n$4\r\nLEFT\r\n", b"$1\r\na\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$3\r\nsrc\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*1\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nLRANGE\r\n$3\r\ndst\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*2\r\n$1\r\na\r\n$1\r\nc\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nDEL\r\n$3\r\nsrc\r\n$3\r\ndst\r\n", b":2\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nRPUSH\r\n$5\r\nlmpop\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*7\r\n$5\r\nLMPOP\r\n$1\r\n2\r\n$4\r\nmiss\r\n$5\r\nlmpop\r\n$4\r\nLEFT\r\n$5\r\nCOUNT\r\n$1\r\n2\r\n", b"*2\r\n$5\r\nlmpop\r\n*2\r\n$1\r\na\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nLMPOP\r\n$1\r\n1\r\n$5\r\nlmpop\r\n$5\r\nRIGHT\r\n", b"*2\r\n$5\r\nlmpop\r\n*1\r\n$1\r\nc\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nLMPOP\r\n$1\r\n1\r\n$5\r\nlmpop\r\n$4\r\nLEFT\r\n", b"*-1\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nRPUSH\r\n$6\r\nblmpop\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*8\r\n$6\r\nBLMPOP\r\n$1\r\n1\r\n$1\r\n2\r\n$4\r\nmiss\r\n$6\r\nblmpop\r\n$4\r\nLEFT\r\n$5\r\nCOUNT\r\n$1\r\n2\r\n", b"*2\r\n$6\r\nblmpop\r\n*2\r\n$1\r\na\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*5\r\n$6\r\nBLMPOP\r\n$1\r\n1\r\n$1\r\n1\r\n$6\r\nblmpop\r\n$5\r\nRIGHT\r\n", b"*2\r\n$6\r\nblmpop\r\n*1\r\n$1\r\nc\r\n")
            roundtrip(sock, b"*5\r\n$6\r\nBLMPOP\r\n$3\r\n0.1\r\n$1\r\n1\r\n$6\r\nblmpop\r\n$4\r\nLEFT\r\n", b"*-1\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nSADD\r\n$3\r\nset\r\n$1\r\na\r\n$1\r\nb\r\n", b":2\r\n")
            sock.sendall(b"*2\r\n$8\r\nSMEMBERS\r\n$3\r\nset\r\n")
            actual = recv_exact(sock, len(b"*2\r\n$1\r\nb\r\n$1\r\na\r\n"))
            if actual not in (b"*2\r\n$1\r\na\r\n$1\r\nb\r\n", b"*2\r\n$1\r\nb\r\n$1\r\na\r\n"):
                raise AssertionError(f"unexpected SMEMBERS reply: {actual!r}")
            roundtrip(sock, b"*2\r\n$5\r\nSCARD\r\n$3\r\nset\r\n", b":2\r\n")
            roundtrip(sock, b"*3\r\n$9\r\nSISMEMBER\r\n$3\r\nset\r\n$1\r\na\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$9\r\nSISMEMBER\r\n$3\r\nset\r\n$1\r\nz\r\n", b":0\r\n")
            roundtrip(sock, b"*5\r\n$10\r\nSMISMEMBER\r\n$3\r\nset\r\n$1\r\na\r\n$1\r\nz\r\n$1\r\nb\r\n", b"*3\r\n:1\r\n:0\r\n:1\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nSSCAN\r\n$3\r\nset\r\n$1\r\n0\r\n$5\r\nCOUNT\r\n$2\r\n16\r\n", b"*2\r\n$1\r\n0\r\n*2\r\n$1\r\na\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nSMOVE\r\n$3\r\nset\r\n$3\r\nset\r\n$1\r\na\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nSMOVE\r\n$3\r\nset\r\n$4\r\nmove\r\n$1\r\nb\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$8\r\nSMEMBERS\r\n$4\r\nmove\r\n", b"*1\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nSCARD\r\n$3\r\nset\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$10\r\nSINTERCARD\r\n$1\r\n2\r\n$3\r\nset\r\n$3\r\nset\r\n", b":1\r\n")
            roundtrip(sock, b"*6\r\n$10\r\nSINTERCARD\r\n$1\r\n2\r\n$3\r\nset\r\n$3\r\nset\r\n$5\r\nLIMIT\r\n$1\r\n1\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$4\r\nmove\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nSADD\r\n$4\r\nspin\r\n$1\r\na\r\n$1\r\nb\r\n", b":2\r\n")
            sock.sendall(b"*2\r\n$11\r\nSRANDMEMBER\r\n$4\r\nspin\r\n")
            srand_actual = recv_exact(sock, len(b"$1\r\na\r\n"))
            if srand_actual not in (b"$1\r\na\r\n", b"$1\r\nb\r\n"):
                raise AssertionError(f"unexpected SRANDMEMBER reply: {srand_actual!r}")
            sock.sendall(b"*2\r\n$4\r\nSPOP\r\n$4\r\nspin\r\n")
            spop_actual = recv_exact(sock, len(b"$1\r\na\r\n"))
            if spop_actual not in (b"$1\r\na\r\n", b"$1\r\nb\r\n"):
                raise AssertionError(f"unexpected SPOP reply: {spop_actual!r}")
            sock.sendall(b"*2\r\n$8\r\nSMEMBERS\r\n$4\r\nspin\r\n")
            spin_members_actual = recv_exact(sock, len(b"*1\r\n$1\r\na\r\n"))
            if spin_members_actual not in (b"*1\r\n$1\r\na\r\n", b"*1\r\n$1\r\nb\r\n"):
                raise AssertionError(f"unexpected spin SMEMBERS reply: {spin_members_actual!r}")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$4\r\nspin\r\n", b":1\r\n")
            roundtrip(sock, b"*6\r\n$4\r\nSADD\r\n$2\r\ns1\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n$1\r\nd\r\n", b":4\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nSADD\r\n$2\r\ns2\r\n$1\r\nb\r\n$1\r\nc\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nSADD\r\n$2\r\ns3\r\n$1\r\nc\r\n$1\r\nd\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nSINTER\r\n$2\r\ns1\r\n$2\r\ns2\r\n$2\r\ns3\r\n", b"*1\r\n$1\r\nc\r\n")
            roundtrip(sock, b"*3\r\n$5\r\nSDIFF\r\n$2\r\ns1\r\n$2\r\ns2\r\n", b"*2\r\n$1\r\na\r\n$1\r\nd\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nSUNION\r\n$2\r\ns1\r\n$2\r\ns2\r\n$2\r\ns3\r\n", b"*4\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n$1\r\nd\r\n")
            roundtrip(sock, b"*5\r\n$11\r\nSINTERSTORE\r\n$2\r\nsi\r\n$2\r\ns1\r\n$2\r\ns2\r\n$2\r\ns3\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nSREM\r\n$2\r\nsi\r\n$1\r\nc\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$10\r\nSDIFFSTORE\r\n$2\r\nsd\r\n$2\r\ns1\r\n$2\r\ns2\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$4\r\nSREM\r\n$2\r\nsd\r\n$1\r\na\r\n$1\r\nd\r\n", b":2\r\n")
            roundtrip(sock, b"*5\r\n$11\r\nSUNIONSTORE\r\n$2\r\nsu\r\n$2\r\ns1\r\n$2\r\ns2\r\n$2\r\ns3\r\n", b":4\r\n")
            roundtrip(sock, b"*6\r\n$4\r\nSREM\r\n$2\r\nsu\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nc\r\n$1\r\nd\r\n", b":4\r\n")
            roundtrip(sock, b"*7\r\n$3\r\nDEL\r\n$2\r\ns1\r\n$2\r\ns2\r\n$2\r\ns3\r\n$2\r\nsi\r\n$2\r\nsd\r\n$2\r\nsu\r\n", b":6\r\n")
            roundtrip(sock, b"*6\r\n$4\r\nZADD\r\n$4\r\nzset\r\n$1\r\n2\r\n$1\r\nb\r\n$1\r\n1\r\n$1\r\na\r\n", b":2\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nZCARD\r\n$4\r\nzset\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZCOUNT\r\n$4\r\nzset\r\n$1\r\n1\r\n$1\r\n2\r\n", b":2\r\n")
            roundtrip(sock, b"*2\r\n$11\r\nZRANDMEMBER\r\n$4\r\nzset\r\n", b"$1\r\na\r\n")
            roundtrip(sock, b"*3\r\n$11\r\nZRANDMEMBER\r\n$4\r\nzset\r\n$1\r\n2\r\n", b"*2\r\n$1\r\na\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*4\r\n$11\r\nZRANDMEMBER\r\n$4\r\nzset\r\n$1\r\n2\r\n$10\r\nWITHSCORES\r\n", b"*4\r\n$1\r\na\r\n$1\r\n1\r\n$1\r\nb\r\n$1\r\n2\r\n")
            roundtrip(sock, b"*3\r\n$11\r\nZRANDMEMBER\r\n$4\r\nzset\r\n$2\r\n-3\r\n", b"*3\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\na\r\n")
            roundtrip(sock, b"*6\r\n$4\r\nZADD\r\n$2\r\nz2\r\n$1\r\n2\r\n$1\r\nb\r\n$1\r\n4\r\n$1\r\nd\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$10\r\nZINTERCARD\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n", b":1\r\n")
            roundtrip(sock, b"*6\r\n$10\r\nZINTERCARD\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n$5\r\nLIMIT\r\n$1\r\n1\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZINTER\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n", b"*1\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*5\r\n$6\r\nZINTER\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n$10\r\nWITHSCORES\r\n", b"*2\r\n$1\r\nb\r\n$1\r\n4\r\n")
            roundtrip(sock, b"*5\r\n$11\r\nZINTERSTORE\r\n$4\r\nzist\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*1\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nZSCORE\r\n$4\r\nzist\r\n$1\r\nb\r\n", b"$1\r\n4\r\n")
            roundtrip(sock, b"*5\r\n$11\r\nZINTERSTORE\r\n$4\r\nzist\r\n$1\r\n2\r\n$4\r\nzset\r\n$7\r\nmissing\r\n", b":0\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzist\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*0\r\n")
            roundtrip(sock, b"*5\r\n$11\r\nZRANGESTORE\r\n$4\r\nzrst\r\n$4\r\nzset\r\n$1\r\n0\r\n$1\r\n1\r\n", b":2\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzrst\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*2\r\n$1\r\na\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nZSCORE\r\n$4\r\nzrst\r\n$1\r\nb\r\n", b"$1\r\n2\r\n")
            roundtrip(sock, b"*5\r\n$11\r\nZRANGESTORE\r\n$4\r\nzrst\r\n$7\r\nmissing\r\n$1\r\n0\r\n$2\r\n-1\r\n", b":0\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzrst\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*0\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZUNION\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n", b"*3\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nd\r\n")
            roundtrip(sock, b"*5\r\n$6\r\nZUNION\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n$10\r\nWITHSCORES\r\n", b"*6\r\n$1\r\na\r\n$1\r\n1\r\n$1\r\nb\r\n$1\r\n4\r\n$1\r\nd\r\n$1\r\n4\r\n")
            roundtrip(sock, b"*5\r\n$11\r\nZUNIONSTORE\r\n$4\r\nzust\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n", b":3\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzust\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*3\r\n$1\r\na\r\n$1\r\nb\r\n$1\r\nd\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nZSCORE\r\n$4\r\nzust\r\n$1\r\nb\r\n", b"$1\r\n4\r\n")
            roundtrip(sock, b"*4\r\n$11\r\nZUNIONSTORE\r\n$4\r\nzust\r\n$1\r\n1\r\n$7\r\nmissing\r\n", b":0\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nZDIFF\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n", b"*1\r\n$1\r\na\r\n")
            roundtrip(sock, b"*5\r\n$5\r\nZDIFF\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n$10\r\nWITHSCORES\r\n", b"*2\r\n$1\r\na\r\n$1\r\n1\r\n")
            roundtrip(sock, b"*5\r\n$10\r\nZDIFFSTORE\r\n$4\r\nzdst\r\n$1\r\n2\r\n$4\r\nzset\r\n$2\r\nz2\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzdst\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*1\r\n$1\r\na\r\n")
            roundtrip(sock, b"*5\r\n$10\r\nZDIFFSTORE\r\n$4\r\nzdst\r\n$1\r\n2\r\n$7\r\nmissing\r\n$2\r\nz2\r\n", b":0\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$2\r\nz2\r\n", b":1\r\n")
            roundtrip(sock, b"*10\r\n$4\r\nZADD\r\n$3\r\nlex\r\n$1\r\n0\r\n$5\r\nalpha\r\n$1\r\n0\r\n$4\r\nbeta\r\n$1\r\n0\r\n$7\r\ncharlie\r\n$1\r\n0\r\n$5\r\ndelta\r\n", b":4\r\n")
            roundtrip(sock, b"*4\r\n$9\r\nZLEXCOUNT\r\n$3\r\nlex\r\n$6\r\n[alpha\r\n$8\r\n[charlie\r\n", b":3\r\n")
            roundtrip(sock, b"*4\r\n$9\r\nZLEXCOUNT\r\n$3\r\nlex\r\n$6\r\n(alpha\r\n$6\r\n[delta\r\n", b":3\r\n")
            roundtrip(sock, b"*4\r\n$9\r\nZLEXCOUNT\r\n$3\r\nlex\r\n$1\r\n-\r\n$1\r\n+\r\n", b":4\r\n")
            roundtrip(sock, b"*4\r\n$9\r\nZLEXCOUNT\r\n$7\r\nmissing\r\n$1\r\n-\r\n$1\r\n+\r\n", b":0\r\n")
            roundtrip(sock, b"*4\r\n$11\r\nZRANGEBYLEX\r\n$3\r\nlex\r\n$6\r\n[alpha\r\n$8\r\n[charlie\r\n", b"*3\r\n$5\r\nalpha\r\n$4\r\nbeta\r\n$7\r\ncharlie\r\n")
            roundtrip(sock, b"*7\r\n$11\r\nZRANGEBYLEX\r\n$3\r\nlex\r\n$1\r\n-\r\n$1\r\n+\r\n$5\r\nLIMIT\r\n$1\r\n1\r\n$1\r\n2\r\n", b"*2\r\n$4\r\nbeta\r\n$7\r\ncharlie\r\n")
            roundtrip(sock, b"*7\r\n$11\r\nZRANGEBYLEX\r\n$3\r\nlex\r\n$5\r\n(beta\r\n$1\r\n+\r\n$5\r\nLIMIT\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*2\r\n$7\r\ncharlie\r\n$5\r\ndelta\r\n")
            roundtrip(sock, b"*4\r\n$14\r\nZREVRANGEBYLEX\r\n$3\r\nlex\r\n$6\r\n[delta\r\n$6\r\n(alpha\r\n", b"*3\r\n$5\r\ndelta\r\n$7\r\ncharlie\r\n$4\r\nbeta\r\n")
            roundtrip(sock, b"*7\r\n$14\r\nZREVRANGEBYLEX\r\n$3\r\nlex\r\n$1\r\n+\r\n$1\r\n-\r\n$5\r\nLIMIT\r\n$1\r\n1\r\n$1\r\n2\r\n", b"*2\r\n$7\r\ncharlie\r\n$4\r\nbeta\r\n")
            roundtrip(sock, b"*7\r\n$14\r\nZREVRANGEBYLEX\r\n$3\r\nlex\r\n$8\r\n[charlie\r\n$1\r\n-\r\n$5\r\nLIMIT\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*3\r\n$7\r\ncharlie\r\n$4\r\nbeta\r\n$5\r\nalpha\r\n")
            roundtrip(sock, b"*4\r\n$14\r\nZREMRANGEBYLEX\r\n$3\r\nlex\r\n$6\r\n[alpha\r\n$8\r\n[charlie\r\n", b":3\r\n")
            roundtrip(sock, b"*4\r\n$11\r\nZRANGEBYLEX\r\n$3\r\nlex\r\n$1\r\n-\r\n$1\r\n+\r\n", b"*1\r\n$5\r\ndelta\r\n")
            roundtrip(sock, b"*4\r\n$14\r\nZREMRANGEBYLEX\r\n$3\r\nlex\r\n$1\r\n-\r\n$1\r\n+\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$14\r\nZREMRANGEBYLEX\r\n$7\r\nmissing\r\n$1\r\n-\r\n$1\r\n+\r\n", b":0\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nDEL\r\n$3\r\nlex\r\n", b":0\r\n")
            roundtrip(sock, b"*4\r\n$7\r\nZINCRBY\r\n$4\r\nzset\r\n$1\r\n3\r\n$1\r\na\r\n", b"$1\r\n4\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZCOUNT\r\n$4\r\nzset\r\n$1\r\n4\r\n$1\r\n4\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$5\r\nZRANK\r\n$4\r\nzset\r\n$1\r\nb\r\n", b":0\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nZRANK\r\n$4\r\nzset\r\n$1\r\nb\r\n$9\r\nWITHSCORE\r\n", b"*2\r\n:0\r\n$1\r\n2\r\n")
            roundtrip(sock, b"*3\r\n$8\r\nZREVRANK\r\n$4\r\nzset\r\n$1\r\na\r\n", b":0\r\n")
            roundtrip(sock, b"*4\r\n$8\r\nZREVRANK\r\n$4\r\nzset\r\n$1\r\na\r\n$9\r\nWITHSCORE\r\n", b"*2\r\n:0\r\n$1\r\n4\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nZSCORE\r\n$4\r\nzset\r\n$1\r\na\r\n", b"$1\r\n4\r\n")
            roundtrip(sock, b"*5\r\n$7\r\nZMSCORE\r\n$4\r\nzset\r\n$1\r\na\r\n$7\r\nmissing\r\n$1\r\nb\r\n", b"*3\r\n$1\r\n4\r\n$-1\r\n$1\r\n2\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzset\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*2\r\n$1\r\nb\r\n$1\r\na\r\n")
            roundtrip(sock, b"*4\r\n$9\r\nZREVRANGE\r\n$4\r\nzset\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*2\r\n$1\r\na\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*5\r\n$9\r\nZREVRANGE\r\n$4\r\nzset\r\n$1\r\n0\r\n$1\r\n1\r\n$10\r\nWITHSCORES\r\n", b"*4\r\n$1\r\na\r\n$1\r\n4\r\n$1\r\nb\r\n$1\r\n2\r\n")
            roundtrip(sock, b"*3\r\n$4\r\nZREM\r\n$4\r\nzset\r\n$1\r\na\r\n", b":1\r\n")
            roundtrip(sock, b"*4\r\n$6\r\nZRANGE\r\n$4\r\nzset\r\n$1\r\n0\r\n$2\r\n-1\r\n", b"*1\r\n$1\r\nb\r\n")
            roundtrip(sock, b"*8\r\n$4\r\nZADD\r\n$5\r\nzmset\r\n$1\r\n2\r\n$1\r\nb\r\n$1\r\n1\r\n$1\r\na\r\n$1\r\n3\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*7\r\n$5\r\nZMPOP\r\n$1\r\n2\r\n$7\r\nmissing\r\n$5\r\nzmset\r\n$3\r\nMIN\r\n$5\r\nCOUNT\r\n$1\r\n2\r\n", b"*2\r\n$5\r\nzmset\r\n*2\r\n*2\r\n$1\r\na\r\n$1\r\n1\r\n*2\r\n$1\r\nb\r\n$1\r\n2\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nZMPOP\r\n$1\r\n1\r\n$5\r\nzmset\r\n$3\r\nMAX\r\n", b"*2\r\n$5\r\nzmset\r\n*1\r\n*2\r\n$1\r\nc\r\n$1\r\n3\r\n")
            roundtrip(sock, b"*4\r\n$5\r\nZMPOP\r\n$1\r\n1\r\n$5\r\nzmset\r\n$3\r\nMIN\r\n", b"*-1\r\n")
            roundtrip(sock, b"*8\r\n$4\r\nZADD\r\n$4\r\nzops\r\n$1\r\n2\r\n$1\r\nb\r\n$1\r\n1\r\n$1\r\na\r\n$1\r\n3\r\n$1\r\nc\r\n", b":3\r\n")
            roundtrip(sock, b"*3\r\n$7\r\nZPOPMIN\r\n$4\r\nzops\r\n$1\r\n2\r\n", b"*4\r\n$1\r\na\r\n$1\r\n1\r\n$1\r\nb\r\n$1\r\n2\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nZSCORE\r\n$4\r\nzops\r\n$1\r\nc\r\n", b"$1\r\n3\r\n")
            roundtrip(sock, b"*2\r\n$7\r\nZPOPMAX\r\n$4\r\nzops\r\n", b"*2\r\n$1\r\nc\r\n$1\r\n3\r\n")
            roundtrip(sock, b"*2\r\n$5\r\nZCARD\r\n$4\r\nzops\r\n", b":0\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$7\r\ntouchme\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*3\r\n$5\r\nTOUCH\r\n$7\r\ntouchme\r\n$7\r\nmissing\r\n", b":1\r\n")
            roundtrip(sock, b"*3\r\n$6\r\nUNLINK\r\n$7\r\nmissing\r\n$7\r\ntouchme\r\n", b":1\r\n")
            roundtrip(sock, b"*2\r\n$6\r\nEXISTS\r\n$7\r\ntouchme\r\n", b":0\r\n")
            roundtrip(sock, b"*2\r\n$4\r\nKEYS\r\n$2\r\nk*\r\n", b"*1\r\n$3\r\nkey\r\n")
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
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$9\r\nflush-key\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$7\r\nFLUSHDB\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$6\r\nDBSIZE\r\n", b":0\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$11\r\nflush-key-2\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$8\r\nFLUSHALL\r\n", b"+OK\r\n")
            roundtrip(sock, b"*1\r\n$6\r\nDBSIZE\r\n", b":0\r\n")
            roundtrip(sock, b"*3\r\n$3\r\nSET\r\n$8\r\ndump-src\r\n$5\r\nvalue\r\n", b"+OK\r\n")
            sock.sendall(b"*2\r\n$4\r\nDUMP\r\n$8\r\ndump-src\r\n")
            dump_payload = recv_bulk(sock)
            if dump_payload is None or dump_payload[0:8] != b"RUYARDB1":
                raise AssertionError(f"unexpected DUMP payload: {dump_payload!r}")
            dump_len = str(len(dump_payload)).encode()
            restore_ttl = b"1500"
            restore_request = (
                b"*4\r\n$7\r\nRESTORE\r\n$8\r\ndump-dst\r\n$4\r\n1500\r\n$"
                + dump_len
                + b"\r\n"
                + dump_payload
                + b"\r\n"
            )
            roundtrip(sock, restore_request, b"+OK\r\n")
            roundtrip(sock, b"*2\r\n$3\r\nGET\r\n$8\r\ndump-dst\r\n", b"$5\r\nvalue\r\n")
            roundtrip(sock, b"*1\r\n$4\r\nQUIT\r\n", b"+OK\r\n")

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
        with connect_with_retry(auth_port, time.monotonic() + 5.0) as auth_sock:
            auth_sock.settimeout(2.0)
            roundtrip(auth_sock, b"*1\r\n$4\r\nPING\r\n", b"-NOAUTH Authentication required.\r\n")
            roundtrip(auth_sock, b"*2\r\n$4\r\nAUTH\r\n$5\r\nwrong\r\n", b"-WRONGPASS invalid username-password pair or user is disabled.\r\n")
            roundtrip(auth_sock, b"*3\r\n$4\r\nAUTH\r\n$7\r\ndefault\r\n$6\r\nsecret\r\n", b"+OK\r\n")
            roundtrip(auth_sock, b"*1\r\n$4\r\nPING\r\n", b"+PONG\r\n")
            roundtrip(auth_sock, b"*3\r\n$6\r\nCONFIG\r\n$3\r\nGET\r\n$11\r\nrequirepass\r\n", b"*2\r\n$11\r\nrequirepass\r\n$6\r\nsecret\r\n")
            auth_sock.sendall(b"*2\r\n$8\r\nSHUTDOWN\r\n$6\r\nNOSAVE\r\n")
            closed = auth_sock.recv(1)
            if closed != b"":
                raise AssertionError(f"expected SHUTDOWN connection close, got {closed!r}")

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
        auth_aof_path.unlink(missing_ok=True)
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
