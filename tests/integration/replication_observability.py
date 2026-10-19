#!/usr/bin/env python3
"""校验 INFO replication 与 ROLE 对外暴露真实在线副本状态。"""
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "build" / "redis-uya"


class RespCursor:
    """最小 RESP2 游标，仅用于解析 ROLE 的嵌套数组。"""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def line(self) -> bytes:
        end = self.data.find(b"\r\n", self.pos)
        if end < 0:
            raise AssertionError(f"RESP 行不完整: {self.data[self.pos:]!r}")
        value = self.data[self.pos:end]
        self.pos = end + 2
        return value

    def value(self):
        if self.pos >= len(self.data):
            raise AssertionError("RESP 数据提前结束")
        prefix = self.data[self.pos:self.pos + 1]
        self.pos += 1
        if prefix in (b"+", b"-", b":"):
            raw = self.line()
            if prefix == b":":
                return int(raw)
            return raw
        if prefix == b"$":
            size = int(self.line())
            if size < 0:
                return None
            end = self.pos + size
            payload = self.data[self.pos:end]
            if self.data[end:end + 2] != b"\r\n":
                raise AssertionError("RESP bulk 缺少终止符")
            self.pos = end + 2
            return payload
        if prefix == b"*":
            count = int(self.line())
            if count < 0:
                return None
            return [self.value() for _ in range(count)]
        raise AssertionError(f"不支持的 RESP 前缀: {prefix!r}")


def parse_resp(data: bytes):
    cursor = RespCursor(data)
    value = cursor.value()
    if cursor.pos != len(data):
        raise AssertionError(f"RESP 尾部存在多余数据: {data[cursor.pos:]!r}")
    return value


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def connect_with_retry(port: int, deadline: float) -> socket.socket:
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            sock.settimeout(3.0)
            return sock
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"无法连接 redis-uya 端口 {port}: {last_error}")


def recv_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("读取 RESP 行时连接已关闭")
        chunks.append(chunk)
        if len(chunks) >= 2 and chunks[-2:] == [b"\r", b"\n"]:
            return b"".join(chunks[:-2])


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("读取 RESP 载荷时连接已关闭")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def encode_request(*parts: bytes) -> bytes:
    payload = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        payload.append(f"${len(part)}\r\n".encode())
        payload.append(part)
        payload.append(b"\r\n")
    return b"".join(payload)


def recv_resp_raw(sock: socket.socket) -> bytes:
    prefix = recv_exact(sock, 1)
    if prefix in (b"+", b"-", b":"):
        return prefix + recv_line(sock) + b"\r\n"
    if prefix == b"$":
        size = int(recv_line(sock))
        if size < 0:
            return b"$-1\r\n"
        return prefix + str(size).encode() + b"\r\n" + recv_exact(sock, size + 2)
    if prefix == b"*":
        count = int(recv_line(sock))
        out = prefix + str(count).encode() + b"\r\n"
        for _ in range(count):
            out += recv_resp_raw(sock)
        return out
    raise AssertionError(f"不支持的 RESP 前缀: {prefix!r}")


def send_command(sock: socket.socket, *parts: bytes) -> bytes:
    sock.sendall(encode_request(*parts))
    return recv_resp_raw(sock)


def recv_psync_fullresync(sock: socket.socket) -> tuple[str, int]:
    prefix = recv_exact(sock, 1)
    if prefix != b"+":
        raise AssertionError(f"FULLRESYNC 前缀错误: {prefix!r}")
    header = recv_line(sock)
    if not header.startswith(b"FULLRESYNC "):
        raise AssertionError(f"期望 FULLRESYNC，实际为 {header!r}")
    fields = header.decode().split(" ")
    if len(fields) not in (3, 4):
        raise AssertionError(f"FULLRESYNC 字段错误: {header!r}")
    if recv_exact(sock, 1) != b"$":
        raise AssertionError("FULLRESYNC 后缺少 bulk 前缀")
    snapshot_len = int(recv_line(sock))
    recv_exact(sock, snapshot_len + 2)
    return fields[1], int(fields[2])


def start_replica_connection(port: int, listening_port: int) -> tuple[socket.socket, int]:
    sock = connect_with_retry(port, time.monotonic() + 5.0)
    try:
        if send_command(sock, b"REPLCONF", b"listening-port", str(listening_port).encode()) != b"+OK\r\n":
            raise AssertionError("REPLCONF listening-port 未返回 +OK")
        sock.sendall(encode_request(b"PSYNC", b"?", b"-1"))
        _, offset = recv_psync_fullresync(sock)
        return sock, offset
    except Exception:
        sock.close()
        raise


def info_fields(port: int) -> dict[str, str]:
    with connect_with_retry(port, time.monotonic() + 5.0) as sock:
        response = parse_resp(send_command(sock, b"INFO", b"replication"))
    if not isinstance(response, bytes):
        raise AssertionError(f"INFO replication 不是 bulk 字符串: {response!r}")
    fields: dict[str, str] = {}
    for line in response.decode().split("\r\n"):
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key] = value
    return fields


def role_replicas(port: int) -> list[list[object]]:
    with connect_with_retry(port, time.monotonic() + 5.0) as sock:
        response = parse_resp(send_command(sock, b"ROLE"))
    if not isinstance(response, list) or len(response) != 3 or response[0] != b"master":
        raise AssertionError(f"master ROLE 结构错误: {response!r}")
    replicas = response[2]
    if not isinstance(replicas, list):
        raise AssertionError(f"master ROLE 副本数组错误: {replicas!r}")
    for replica in replicas:
        if not isinstance(replica, list) or len(replica) != 3:
            raise AssertionError(f"master ROLE 副本三元组错误: {replica!r}")
    return replicas


def wait_for_observation(port: int, predicate, deadline: float) -> tuple[dict[str, str], list[list[object]]]:
    last_info: dict[str, str] = {}
    last_role: list[list[object]] = []
    while time.monotonic() < deadline:
        last_info = info_fields(port)
        last_role = role_replicas(port)
        if predicate(last_info, last_role):
            return last_info, last_role
        time.sleep(0.05)
    raise AssertionError(f"复制可观测状态未收敛，INFO={last_info!r}, ROLE={last_role!r}")


def wait_for_replica_connected(port: int, master_port: int, deadline: float) -> None:
    last: dict[str, str] = {}
    while time.monotonic() < deadline:
        last = info_fields(port)
        if (
            last.get("role") == "slave"
            and last.get("master_port") == str(master_port)
            and last.get("replication_state") == "connected"
        ):
            return
        time.sleep(0.05)
    raise AssertionError(f"配置型 replica 未进入 connected 状态: {last!r}")


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
        raise RuntimeError("缺少 build/redis-uya，请先执行 make build")

    port = find_free_port()
    replica_port = find_free_port()
    master_aof = ROOT / "build" / f"replication-observability-master-{port}.aof"
    replica_aof = ROOT / "build" / f"replication-observability-replica-{replica_port}.aof"
    master_aof.unlink(missing_ok=True)
    replica_aof.unlink(missing_ok=True)
    master = subprocess.Popen(
        [str(BIN), str(port), "16", str(master_aof)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    replica: subprocess.Popen[str] | None = None
    first: socket.socket | None = None
    second: socket.socket | None = None
    ordinary_ack: socket.socket | None = None
    try:
        initial_info = info_fields(port)
        initial_role = role_replicas(port)
        if initial_info.get("connected_slaves") != "0" or initial_role:
            raise AssertionError(f"初始 master 不应有副本: INFO={initial_info!r}, ROLE={initial_role!r}")

        first_listening_port = 16381
        first, _ = start_replica_connection(port, first_listening_port)
        first.sendall(encode_request(b"REPLCONF", b"ACK", b"42", b"FACK", b"40"))
        expected_ack = 42
        expected_fack = 40

        def first_observed(info: dict[str, str], role: list[list[object]]) -> bool:
            slave = info.get("slave0", "")
            return (
                info.get("connected_slaves") == "1"
                and f"ip=127.0.0.1" in slave
                and f"port={first_listening_port}" in slave
                and "state=online" in slave
                and f"offset={expected_ack}" in slave
                and f"fack_offset={expected_fack}" in slave
                and role == [[b"127.0.0.1", first_listening_port, expected_ack]]
            )

        observed_info, _ = wait_for_observation(port, first_observed, time.monotonic() + 5.0)
        lag_text = observed_info["slave0"].split("lag=", 1)[1].split(",", 1)[0]
        if int(lag_text) < 0:
            raise AssertionError(f"lag 不应为负: {observed_info['slave0']!r}")

        ordinary_ack = connect_with_retry(port, time.monotonic() + 5.0)
        ordinary_ack.sendall(encode_request(b"REPLCONF", b"ACK", b"999"))
        if send_command(ordinary_ack, b"PING") != b"+PONG\r\n":
            raise AssertionError("普通 ACK 连接处理屏障 PING 失败")
        after_ordinary = info_fields(port)
        if after_ordinary.get("connected_slaves") != "1":
            raise AssertionError(f"未 PSYNC 的普通 ACK 连接被错误计入副本: {after_ordinary!r}")

        second_listening_port = 16382
        second, _ = start_replica_connection(port, second_listening_port)
        second.sendall(encode_request(b"REPLCONF", b"ACK", b"22", b"FACK", b"20"))

        def both_observed(info: dict[str, str], role: list[list[object]]) -> bool:
            normalized = sorted((str(item[0].decode()), int(item[1]), int(item[2])) for item in role)
            return info.get("connected_slaves") == "2" and normalized == [
                ("127.0.0.1", first_listening_port, 42),
                ("127.0.0.1", second_listening_port, 22),
            ]

        wait_for_observation(port, both_observed, time.monotonic() + 5.0)

        first.close()
        first = None
        wait_for_observation(
            port,
            lambda info, role: info.get("connected_slaves") == "1"
            and role == [[b"127.0.0.1", second_listening_port, 22]],
            time.monotonic() + 5.0,
        )

        second.close()
        second = None
        wait_for_observation(
            port,
            lambda info, role: info.get("connected_slaves") == "0" and role == [],
            time.monotonic() + 5.0,
        )

        replica = subprocess.Popen(
            [str(BIN), str(replica_port), "16", str(replica_aof)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with connect_with_retry(replica_port, time.monotonic() + 5.0) as replica_client:
            if send_command(replica_client, b"REPLICAOF", b"127.0.0.1", str(port).encode()) != b"+OK\r\n":
                raise AssertionError("配置型 replica 的 REPLICAOF 未返回 +OK")
        wait_for_replica_connected(replica_port, port, time.monotonic() + 10.0)

        # pull replica 的握手、增量同步和心跳均为短连接，稳定后 master 不应持续计数。
        stable_deadline = time.monotonic() + 5.0
        zero_streak = 0
        while time.monotonic() < stable_deadline:
            if info_fields(port).get("connected_slaves") == "0" and role_replicas(port) == []:
                zero_streak += 1
                if zero_streak >= 3:
                    break
            else:
                zero_streak = 0
            time.sleep(0.1)
        else:
            raise AssertionError("配置型 pull replica 稳定后仍在 master 可观测状态中计数")
    finally:
        if ordinary_ack is not None:
            ordinary_ack.close()
        if first is not None:
            first.close()
        if second is not None:
            second.close()
        if replica is not None:
            stop_process(replica)
        stop_process(master)
        master_aof.unlink(missing_ok=True)
        replica_aof.unlink(missing_ok=True)


def main() -> int:
    try:
        run_smoke()
    except Exception as exc:
        print(f"[FAIL] integration/replication_observability: {exc}", file=sys.stderr)
        return 1
    print("[PASS] integration/replication_observability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
