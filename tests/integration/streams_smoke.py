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
            full_info = client.command(b"XINFO", b"STREAM", b"mystream", b"FULL", b"COUNT", b"1")
            if (
                not isinstance(full_info, list)
                or b"entries" not in full_info
                or full_info[full_info.index(b"entries") + 1] != [[first, [b"sensor", b"a", b"value", b"1"]]]
                or b"groups" not in full_info
                or full_info[full_info.index(b"groups") + 1] != []
            ):
                raise AssertionError(f"unexpected XINFO STREAM FULL payload: {full_info!r}")
            if client.command(b"XINFO", b"GROUPS", b"mystream") != []:
                raise AssertionError("XINFO GROUPS did not return an empty group list")
            try:
                client.command(b"XINFO", b"STREAM", b"missing")
                raise AssertionError("XINFO STREAM did not fail for a missing key")
            except RuntimeError as exc:
                if str(exc) != "ERR no such key":
                    raise AssertionError(f"unexpected XINFO STREAM missing-key error: {exc}") from exc
            try:
                client.command(b"XGROUP", b"CREATE", b"mystream", b"group")
                raise AssertionError("XGROUP CREATE accepted too few arguments")
            except RuntimeError as exc:
                if str(exc) != "ERR wrong number of arguments for 'xgroup|create' command":
                    raise AssertionError(f"unexpected XGROUP CREATE arity error: {exc}") from exc
            if client.command(b"XGROUP", b"CREATE", b"mystream", b"group", b"$") != b"OK":
                raise AssertionError("XGROUP CREATE $ did not return OK")
            try:
                client.command(b"XGROUP", b"CREATE", b"mystream", b"group", b"$")
                raise AssertionError("XGROUP CREATE accepted a duplicate group")
            except RuntimeError as exc:
                if str(exc) != "BUSYGROUP Consumer Group name already exists":
                    raise AssertionError(f"unexpected XGROUP CREATE duplicate error: {exc}") from exc
            if client.command(b"XGROUP", b"CREATE", b"mystream", b"midgroup", first) != b"OK":
                raise AssertionError("XGROUP CREATE with a concrete id did not return OK")
            try:
                client.command(b"XGROUP", b"CREATE", b"missing-group-stream", b"group", b"$")
                raise AssertionError("XGROUP CREATE accepted a missing key without MKSTREAM")
            except RuntimeError as exc:
                expected = "ERR The XGROUP subcommand requires the key to exist. Note that for CREATE you may want to use the MKSTREAM option to create an empty stream automatically."
                if str(exc) != expected:
                    raise AssertionError(f"unexpected XGROUP CREATE missing-key error: {exc}") from exc
            if client.command(b"XGROUP", b"CREATE", b"empty-stream", b"empty-group", b"0-0", b"MKSTREAM") != b"OK":
                raise AssertionError("XGROUP CREATE MKSTREAM did not return OK")
            if client.command(b"XLEN", b"empty-stream") != 0:
                raise AssertionError("XGROUP CREATE MKSTREAM did not create an empty stream")

            groups = client.command(b"XINFO", b"GROUPS", b"mystream")
            if not isinstance(groups, list) or len(groups) != 2:
                raise AssertionError(f"XINFO GROUPS did not report two groups: {groups!r}")
            groups_by_name = {group[group.index(b"name") + 1]: group for group in groups}
            if set(groups_by_name) != {b"group", b"midgroup"}:
                raise AssertionError(f"XINFO GROUPS returned unexpected names: {groups_by_name!r}")
            group_info = groups_by_name[b"group"]
            if (
                group_info[group_info.index(b"consumers") + 1] != 0
                or group_info[group_info.index(b"pending") + 1] != 0
                or group_info[group_info.index(b"last-delivered-id") + 1] != second
                or group_info[group_info.index(b"entries-read") + 1] is not None
                or group_info[group_info.index(b"lag") + 1] != 0
            ):
                raise AssertionError(f"unexpected XINFO GROUPS $ payload: {group_info!r}")
            mid_info = groups_by_name[b"midgroup"]
            if (
                mid_info[mid_info.index(b"last-delivered-id") + 1] != first
                or mid_info[mid_info.index(b"lag") + 1] != 1
            ):
                raise AssertionError(f"unexpected XINFO GROUPS concrete-id payload: {mid_info!r}")
            if client.command(b"XGROUP", b"SETID", b"mystream", b"midgroup", first, b"ENTRIESREAD", b"1") != b"OK":
                raise AssertionError("XGROUP SETID ENTRIESREAD did not return OK")
            mid_info = client.command(b"XINFO", b"GROUPS", b"mystream")
            mid_info = {group[group.index(b"name") + 1]: group for group in mid_info}[b"midgroup"]
            if (
                mid_info[mid_info.index(b"last-delivered-id") + 1] != first
                or mid_info[mid_info.index(b"entries-read") + 1] != 1
                or mid_info[mid_info.index(b"lag") + 1] != 1
            ):
                raise AssertionError(f"XGROUP SETID ENTRIESREAD did not update metadata: {mid_info!r}")
            if client.command(b"XGROUP", b"SETID", b"mystream", b"group", b"$", b"ENTRIESREAD", b"2") != b"OK":
                raise AssertionError("XGROUP SETID $ did not return OK")
            group_info = client.command(b"XINFO", b"GROUPS", b"mystream")
            group_info = {group[group.index(b"name") + 1]: group for group in group_info}[b"group"]
            if (
                group_info[group_info.index(b"last-delivered-id") + 1] != second
                or group_info[group_info.index(b"entries-read") + 1] != 2
                or group_info[group_info.index(b"lag") + 1] != 0
            ):
                raise AssertionError(f"XGROUP SETID $ did not update metadata: {group_info!r}")
            if client.command(b"XGROUP", b"DESTROY", b"mystream", b"midgroup") != 1:
                raise AssertionError("XGROUP DESTROY did not report the deleted group")
            if client.command(b"XGROUP", b"DESTROY", b"mystream", b"midgroup") != 0:
                raise AssertionError("XGROUP DESTROY deleted a missing group")
            try:
                client.command(b"XGROUP", b"SETID", b"mystream", b"missing-group", b"$")
                raise AssertionError("XGROUP SETID did not fail for a missing group")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XGROUP SETID missing-group error: {exc}") from exc
            stream_with_groups = client.command(b"XINFO", b"STREAM", b"mystream")
            if stream_with_groups[stream_with_groups.index(b"groups") + 1] != 1:
                raise AssertionError(f"XINFO STREAM did not report the live group count: {stream_with_groups!r}")
            full_with_groups = client.command(b"XINFO", b"STREAM", b"mystream", b"FULL")
            full_groups = full_with_groups[full_with_groups.index(b"groups") + 1]
            if (
                not isinstance(full_groups, list)
                or len(full_groups) != 1
                or full_groups[0][full_groups[0].index(b"name") + 1] != b"group"
                or full_groups[0][full_groups[0].index(b"pel-count") + 1] != 0
                or full_groups[0][full_groups[0].index(b"pending") + 1] != []
                or full_groups[0][full_groups[0].index(b"consumers") + 1] != []
            ):
                raise AssertionError(f"unexpected XINFO STREAM FULL groups payload: {full_groups!r}")
            empty_groups = client.command(b"XINFO", b"GROUPS", b"empty-stream")
            if (
                not isinstance(empty_groups, list)
                or len(empty_groups) != 1
                or empty_groups[0][empty_groups[0].index(b"name") + 1] != b"empty-group"
                or empty_groups[0][empty_groups[0].index(b"last-delivered-id") + 1] != b"0-0"
            ):
                raise AssertionError(f"unexpected MKSTREAM group metadata: {empty_groups!r}")
            try:
                client.command(b"XAUTOCLAIM", b"mystream", b"group", b"consumer", b"0", b"0-0")
                raise AssertionError("XAUTOCLAIM did not report deferred PEL state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XAUTOCLAIM error: {exc}") from exc
            future_id = b"9999999999999-0"
            if client.command(b"XSETID", b"mystream", future_id) != b"OK":
                raise AssertionError("XSETID did not return OK")
            after_xsetid = client.command(b"XINFO", b"STREAM", b"mystream")
            if (
                not isinstance(after_xsetid, list)
                or b"last-generated-id" not in after_xsetid
                or after_xsetid[after_xsetid.index(b"last-generated-id") + 1] != future_id
            ):
                raise AssertionError(f"XSETID did not update last-generated-id: {after_xsetid!r}")
            third = client.command(b"XADD", b"mystream", b"*", b"sensor", b"c")
            if third != b"9999999999999-1":
                raise AssertionError(f"XADD did not continue after XSETID: {third!r}")
            try:
                client.command(b"XSETID", b"mystream", first)
                raise AssertionError("XSETID accepted an id below the current stream top item")
            except RuntimeError as exc:
                if str(exc) != "ERR The ID specified in XSETID is smaller than the target stream top item":
                    raise AssertionError(f"unexpected XSETID backward error: {exc}") from exc
            try:
                client.command(b"XSETID", b"mystream", b"bad")
                raise AssertionError("XSETID accepted an invalid stream id")
            except RuntimeError as exc:
                if str(exc) != "ERR Invalid stream ID specified as stream command argument":
                    raise AssertionError(f"unexpected XSETID invalid-id error: {exc}") from exc
            try:
                client.command(b"XGROUP", b"CREATECONSUMER", b"mystream", b"group", b"consumer")
                raise AssertionError("XGROUP CREATECONSUMER did not report deferred consumer state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XGROUP CREATECONSUMER error: {exc}") from exc
            try:
                client.command(b"XGROUP", b"DELCONSUMER", b"mystream", b"group", b"consumer")
                raise AssertionError("XGROUP DELCONSUMER did not report deferred consumer state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XGROUP DELCONSUMER error: {exc}") from exc
            try:
                client.command(b"XINFO", b"CONSUMERS", b"mystream", b"group")
                raise AssertionError("XINFO CONSUMERS did not report deferred consumer state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XINFO CONSUMERS error: {exc}") from exc

            ranged = client.command(b"XRANGE", b"mystream", b"-", b"+")
            if ranged != [[first, [b"sensor", b"a", b"value", b"1"]], [second, [b"sensor", b"b"]], [third, [b"sensor", b"c"]]]:
                raise AssertionError(f"unexpected XRANGE payload: {ranged!r}")

            rev = client.command(b"XREVRANGE", b"mystream", b"+", b"-", b"COUNT", b"1")
            if rev != [[third, [b"sensor", b"c"]]]:
                raise AssertionError(f"unexpected XREVRANGE payload: {rev!r}")

            read = client.command(b"XREAD", b"COUNT", b"2", b"STREAMS", b"mystream", b"0-0")
            if read != [[b"mystream", [[first, [b"sensor", b"a", b"value", b"1"]], [second, [b"sensor", b"b"]]]]]:
                raise AssertionError(f"unexpected XREAD payload: {read!r}")
            if client.command(b"XCFGSET", b"mystream", b"IDMP-DURATION", b"10", b"IDMP-MAXSIZE", b"100") != b"OK":
                raise AssertionError("XCFGSET did not return OK")
            if client.command(b"XIDMPRECORD", b"mystream", b"pid", b"iid", first) != b"OK":
                raise AssertionError("XIDMPRECORD did not return OK")
            try:
                client.command(b"XREADGROUP", b"GROUP", b"group", b"consumer", b"STREAMS", b"mystream", b">")
                raise AssertionError("XREADGROUP did not report deferred PEL state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XREADGROUP error: {exc}") from exc
            try:
                client.command(b"XACK", b"mystream", b"group", first)
                raise AssertionError("XACK did not report deferred PEL state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XACK error: {exc}") from exc

            try:
                client.command(b"XACKDEL", b"mystream", b"group", b"IDS", b"1", first)
                raise AssertionError("XACKDEL did not report deferred PEL state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XACKDEL error: {exc}") from exc

            try:
                client.command(b"XNACK", b"mystream", b"group", b"FAIL", b"IDS", b"1", first)
                raise AssertionError("XNACK did not report deferred PEL state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XNACK error: {exc}") from exc

            try:
                client.command(b"XCLAIM", b"mystream", b"group", b"consumer", b"0", first)
                raise AssertionError("XCLAIM did not report deferred PEL state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XCLAIM error: {exc}") from exc

            try:
                client.command(b"XPENDING", b"mystream", b"group")
                raise AssertionError("XPENDING did not report deferred PEL state")
            except RuntimeError as exc:
                if "NOGROUP" not in str(exc):
                    raise AssertionError(f"unexpected XPENDING error: {exc}") from exc

            xdelex_first = client.command(b"XADD", b"xdelexstream", b"1-0", b"f", b"a")
            xdelex_second = client.command(b"XADD", b"xdelexstream", b"1-1", b"f", b"b")
            if xdelex_first != b"1-0" or xdelex_second != b"1-1":
                raise AssertionError(f"unexpected XDELEX fixture ids: {xdelex_first!r}, {xdelex_second!r}")
            if client.command(b"XDELEX", b"xdelexstream", b"IDS", b"2", b"1-0", b"9-9") != [1, -1]:
                raise AssertionError("XDELEX did not report per-id delete states")
            if client.command(b"XDELEX", b"xdelexstream", b"ACKED", b"IDS", b"1", b"1-1") != [2]:
                raise AssertionError("XDELEX ACKED did not report not-acked state without consumer groups")
            if client.command(b"XLEN", b"xdelexstream") != 1:
                raise AssertionError("XDELEX ACKED deleted an entry without consumer groups")

            if client.command(b"XADD", b"trimstream", b"1-0", b"f", b"a") != b"1-0":
                raise AssertionError("XADD trimstream seed failed")
            if client.command(b"XADD", b"trimstream", b"MAXLEN", b"=", b"1", b"1-1", b"f", b"b") != b"1-1":
                raise AssertionError("XADD MAXLEN did not append expected id")
            if client.command(b"XLEN", b"trimstream") != 1:
                raise AssertionError("XADD MAXLEN did not trim to one entry")
            if client.command(b"XRANGE", b"trimstream", b"-", b"+") != [[b"1-1", [b"f", b"b"]]]:
                raise AssertionError("XADD MAXLEN kept the wrong stream entry")
            if client.command(b"XADD", b"nomk", b"NOMKSTREAM", b"*", b"f", b"v") is not None:
                raise AssertionError("XADD NOMKSTREAM on missing key did not return null")
            if client.command(b"XLEN", b"nomk") != 0:
                raise AssertionError("XADD NOMKSTREAM created a missing stream")
            if client.command(b"XADD", b"limitstream", b"1-0", b"f", b"a") != b"1-0":
                raise AssertionError("XADD limitstream seed 1-0 failed")
            if client.command(b"XADD", b"limitstream", b"1-1", b"f", b"b") != b"1-1":
                raise AssertionError("XADD limitstream seed 1-1 failed")
            if client.command(b"XADD", b"limitstream", b"MAXLEN", b"~", b"1", b"LIMIT", b"1", b"1-2", b"f", b"c") != b"1-2":
                raise AssertionError("XADD MAXLEN LIMIT did not append expected id")
            if client.command(b"XRANGE", b"limitstream", b"-", b"+") != [[b"1-1", [b"f", b"b"]], [b"1-2", [b"f", b"c"]]]:
                raise AssertionError("XADD MAXLEN LIMIT trimmed the wrong number of entries")
            if client.command(b"XADD", b"xtrimlimit", b"1-0", b"f", b"a") != b"1-0":
                raise AssertionError("XADD xtrimlimit seed 1-0 failed")
            if client.command(b"XADD", b"xtrimlimit", b"1-1", b"f", b"b") != b"1-1":
                raise AssertionError("XADD xtrimlimit seed 1-1 failed")
            if client.command(b"XADD", b"xtrimlimit", b"1-2", b"f", b"c") != b"1-2":
                raise AssertionError("XADD xtrimlimit seed 1-2 failed")
            if client.command(b"XTRIM", b"xtrimlimit", b"MAXLEN", b"0", b"LIMIT", b"2") != 2:
                raise AssertionError("XTRIM MAXLEN LIMIT did not cap removals")
            if client.command(b"XRANGE", b"xtrimlimit", b"-", b"+") != [[b"1-2", [b"f", b"c"]]]:
                raise AssertionError("XTRIM MAXLEN LIMIT kept the wrong stream entry")
            if client.command(b"XADD", b"minidstream", b"1-0", b"f", b"a") != b"1-0":
                raise AssertionError("XADD minidstream seed 1-0 failed")
            if client.command(b"XADD", b"minidstream", b"1-1", b"f", b"b") != b"1-1":
                raise AssertionError("XADD minidstream seed 1-1 failed")
            if client.command(b"XADD", b"minidstream", b"MINID", b"=", b"1-2", b"LIMIT", b"1", b"1-2", b"f", b"c") != b"1-2":
                raise AssertionError("XADD MINID LIMIT did not append expected id")
            if client.command(b"XRANGE", b"minidstream", b"-", b"+") != [[b"1-1", [b"f", b"b"]], [b"1-2", [b"f", b"c"]]]:
                raise AssertionError("XADD MINID LIMIT trimmed the wrong stream entries")
            if client.command(b"XADD", b"xtrimminid", b"1-0", b"f", b"a") != b"1-0":
                raise AssertionError("XADD xtrimminid seed 1-0 failed")
            if client.command(b"XADD", b"xtrimminid", b"1-1", b"f", b"b") != b"1-1":
                raise AssertionError("XADD xtrimminid seed 1-1 failed")
            if client.command(b"XADD", b"xtrimminid", b"1-2", b"f", b"c") != b"1-2":
                raise AssertionError("XADD xtrimminid seed 1-2 failed")
            if client.command(b"XTRIM", b"xtrimminid", b"MINID", b"1-2", b"LIMIT", b"1") != 1:
                raise AssertionError("XTRIM MINID LIMIT did not cap removals")
            if client.command(b"XRANGE", b"xtrimminid", b"-", b"+") != [[b"1-1", [b"f", b"b"]], [b"1-2", [b"f", b"c"]]]:
                raise AssertionError("XTRIM MINID LIMIT kept the wrong stream entries")

            if client.command(b"XDEL", b"mystream", first) != 1:
                raise AssertionError("XDEL did not remove the first stream entry")
            if client.command(b"XLEN", b"mystream") != 2:
                raise AssertionError("XLEN did not report two stream entries after XDEL")

            if client.command(b"XTRIM", b"mystream", b"MAXLEN", b"~", b"0") != 2:
                raise AssertionError("XTRIM did not remove two stream entries")
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
            replayed_groups = replay_client.command(b"XINFO", b"GROUPS", b"mystream")
            if (
                not isinstance(replayed_groups, list)
                or len(replayed_groups) != 1
                or replayed_groups[0][replayed_groups[0].index(b"name") + 1] != b"group"
                or replayed_groups[0][replayed_groups[0].index(b"entries-read") + 1] != 2
                or replayed_groups[0][replayed_groups[0].index(b"consumers") + 1] != 0
                or replayed_groups[0][replayed_groups[0].index(b"pending") + 1] != 0
            ):
                raise AssertionError(f"AOF replay did not preserve group metadata: {replayed_groups!r}")
            replayed_empty_groups = replay_client.command(b"XINFO", b"GROUPS", b"empty-stream")
            if (
                not isinstance(replayed_empty_groups, list)
                or len(replayed_empty_groups) != 1
                or replayed_empty_groups[0][replayed_empty_groups[0].index(b"name") + 1] != b"empty-group"
            ):
                raise AssertionError(f"AOF replay did not preserve MKSTREAM group: {replayed_empty_groups!r}")
            if replay_client.command(b"XLEN", b"trimstream") != 1:
                raise AssertionError("AOF replay did not preserve XADD MAXLEN trim result")
            if replay_client.command(b"XRANGE", b"trimstream", b"-", b"+") != [[b"1-1", [b"f", b"b"]]]:
                raise AssertionError("AOF replay restored the wrong XADD MAXLEN entry")
            if replay_client.command(b"XLEN", b"nomk") != 0:
                raise AssertionError("AOF replay created NOMKSTREAM missing key")
            if replay_client.command(b"XRANGE", b"limitstream", b"-", b"+") != [[b"1-1", [b"f", b"b"]], [b"1-2", [b"f", b"c"]]]:
                raise AssertionError("AOF replay restored the wrong XADD MAXLEN LIMIT entries")
            if replay_client.command(b"XRANGE", b"xtrimlimit", b"-", b"+") != [[b"1-2", [b"f", b"c"]]]:
                raise AssertionError("AOF replay restored the wrong XTRIM MAXLEN LIMIT entry")
            if replay_client.command(b"XRANGE", b"minidstream", b"-", b"+") != [[b"1-1", [b"f", b"b"]], [b"1-2", [b"f", b"c"]]]:
                raise AssertionError("AOF replay restored the wrong XADD MINID LIMIT entries")
            if replay_client.command(b"XRANGE", b"xtrimminid", b"-", b"+") != [[b"1-1", [b"f", b"b"]], [b"1-2", [b"f", b"c"]]]:
                raise AssertionError("AOF replay restored the wrong XTRIM MINID LIMIT entries")
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
