#!/usr/bin/env python3
import socket
import subprocess
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


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


class Client:
    def __init__(self, port: int) -> None:
        self.sock = connect_with_retry(port, time.monotonic() + 5.0)
        self.sock.settimeout(2.0)

    def close(self) -> None:
        self.sock.close()

    def read_exact(self, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise RuntimeError("connection closed while reading payload")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def read_line(self) -> bytes:
        data = bytearray()
        while not data.endswith(b"\r\n"):
            data.extend(self.read_exact(1))
        return bytes(data[:-2])

    def read_resp(self):
        prefix = self.read_exact(1)
        if prefix == b"+":
            return self.read_line()
        if prefix == b"-":
            raise RuntimeError(self.read_line().decode())
        if prefix == b":":
            return int(self.read_line())
        if prefix == b"$":
            length = int(self.read_line())
            if length < 0:
                return None
            data = self.read_exact(length)
            if self.read_exact(2) != b"\r\n":
                raise RuntimeError("invalid bulk terminator")
            return data
        if prefix == b"*":
            count = int(self.read_line())
            if count < 0:
                return None
            return [self.read_resp() for _ in range(count)]
        raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")

    def command(self, *parts: bytes):
        request = [f"*{len(parts)}\r\n".encode()]
        for part in parts:
            request.append(f"${len(part)}\r\n".encode())
            request.append(part)
            request.append(b"\r\n")
        self.sock.sendall(b"".join(request))
        return self.read_resp()


def run_smoke() -> None:
    if not BIN.exists():
        raise RuntimeError("build/redis-uya is missing; run `make build` first")

    port = find_free_port()
    aof_path = ROOT / "build" / f"streams-{port}.aof"
    aof_path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    first: bytes
    second: bytes
    try:
        client = Client(port)
        try:
            first = client.command(b"XADD", b"mystream", b"*", b"sensor", b"a", b"value", b"1")
            second = client.command(b"XADD", b"mystream", b"*", b"sensor", b"b")
            if not isinstance(first, bytes) or not isinstance(second, bytes) or first == second:
                raise AssertionError(f"unexpected XADD ids: {first!r}, {second!r}")
            if client.command(b"XLEN", b"mystream") != 2:
                raise AssertionError("XLEN did not report two stream entries")

            info = client.command(b"XINFO", b"STREAM", b"mystream")
            if (
                not isinstance(info, list)
                or b"length" not in info
                or info[info.index(b"length") + 1] != 2
                or b"groups" not in info
                or info[info.index(b"groups") + 1] != 0
                or b"first-entry" not in info
                or info[info.index(b"first-entry") + 1][0] != first
                or b"last-entry" not in info
                or info[info.index(b"last-entry") + 1][0] != second
            ):
                raise AssertionError(f"unexpected XINFO STREAM payload: {info!r}")
            if client.command(b"XINFO", b"GROUPS", b"mystream") != []:
                raise AssertionError("XINFO GROUPS did not return an empty group list")
            try:
                client.command(b"XGROUP", b"CREATE", b"mystream", b"group", b"$")
                raise AssertionError("XGROUP CREATE did not report deferred consumer groups")
            except RuntimeError as exc:
                if "XGROUP CREATE is not supported yet" not in str(exc):
                    raise AssertionError(f"unexpected XGROUP CREATE error: {exc}") from exc
            if client.command(b"XGROUP", b"DESTROY", b"mystream", b"group") != 0:
                raise AssertionError("XGROUP DESTROY did not return zero without consumer groups")
            try:
                client.command(b"XGROUP", b"SETID", b"mystream", b"group", b"$")
                raise AssertionError("XGROUP SETID did not fail without consumer groups")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XGROUP SETID error: {exc}") from exc
            try:
                client.command(b"XINFO", b"CONSUMERS", b"mystream", b"group")
                raise AssertionError("XINFO CONSUMERS did not fail without consumer groups")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XINFO CONSUMERS error: {exc}") from exc

            ranged = client.command(b"XRANGE", b"mystream", b"-", b"+")
            if ranged != [[first, [b"sensor", b"a", b"value", b"1"]], [second, [b"sensor", b"b"]]]:
                raise AssertionError(f"unexpected XRANGE payload: {ranged!r}")

            rev = client.command(b"XREVRANGE", b"mystream", b"+", b"-", b"COUNT", b"1")
            if rev != [[second, [b"sensor", b"b"]]]:
                raise AssertionError(f"unexpected XREVRANGE payload: {rev!r}")

            read = client.command(b"XREAD", b"COUNT", b"2", b"STREAMS", b"mystream", b"0-0")
            if read != [[b"mystream", [[first, [b"sensor", b"a", b"value", b"1"]], [second, [b"sensor", b"b"]]]]]:
                raise AssertionError(f"unexpected XREAD payload: {read!r}")
            try:
                client.command(b"XACK", b"mystream", b"group", first)
                raise AssertionError("XACK did not fail without consumer groups")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XACK error: {exc}") from exc

            try:
                client.command(b"XCLAIM", b"mystream", b"group", b"consumer", b"0", first)
                raise AssertionError("XCLAIM did not fail without consumer groups")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XCLAIM error: {exc}") from exc

            try:
                client.command(b"XPENDING", b"mystream", b"group")
                raise AssertionError("XPENDING did not fail without consumer groups")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XPENDING error: {exc}") from exc

            if client.command(b"XDEL", b"mystream", first) != 1:
                raise AssertionError("XDEL did not remove the first stream entry")
            if client.command(b"XLEN", b"mystream") != 1:
                raise AssertionError("XLEN did not report one stream entry after XDEL")

            if client.command(b"XTRIM", b"mystream", b"MAXLEN", b"~", b"0") != 1:
                raise AssertionError("XTRIM did not remove one stream entry")
            if client.command(b"XLEN", b"mystream") != 0:
                raise AssertionError("XLEN did not report zero stream entries after trim")

            if client.command(b"TYPE", b"mystream") != b"stream":
                raise AssertionError("TYPE mystream did not report stream")
            if client.command(b"QUIT") != b"OK":
                raise AssertionError("QUIT failed")
        finally:
            client.close()
    finally:
        stop_process(proc)

    proc = subprocess.Popen(
        [str(BIN), str(port), "8", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        replay_client = Client(port)
        try:
            if replay_client.command(b"XLEN", b"mystream") != 0:
                raise AssertionError("AOF replay did not restore stream length")
            replayed = replay_client.command(b"XRANGE", b"mystream", b"-", b"+")
            if not isinstance(replayed, list) or len(replayed) != 0:
                raise AssertionError(f"unexpected replayed stream payload: {replayed!r}")
            if replay_client.command(b"QUIT") != b"OK":
                raise AssertionError("replay QUIT failed")
        finally:
            replay_client.close()
    finally:
        stop_process(proc)
        aof_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run_smoke()
    print("[PASS] integration/streams_smoke")
