#!/usr/bin/env python3
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "redis-uya"
OUT = ROOT / "benchmarks" / "v0.4.0-replication.md"


def command_path(name: str) -> str | None:
    path = subprocess.run(
        ["bash", "-lc", f"command -v {name} || true"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return path or None


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
    raise RuntimeError(f"failed to connect on port {port}: {last_error}")


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
    data = b""
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise RuntimeError("connection closed while reading line")
        data += chunk
    return data[:-2]


def send_command(sock: socket.socket, *parts: bytes) -> bytes:
    buf = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        buf.append(f"${len(part)}\r\n".encode())
        buf.append(part)
        buf.append(b"\r\n")
    sock.sendall(b"".join(buf))

    prefix = recv_exact(sock, 1)
    if prefix in (b"+", b"-", b":"):
        return prefix + recv_line(sock) + b"\r\n"
    if prefix == b"$":
        size = int(recv_line(sock))
        if size < 0:
            return b"$-1\r\n"
        payload = recv_exact(sock, size + 2)
        return prefix + str(size).encode() + b"\r\n" + payload
    if prefix == b"*":
        count = int(recv_line(sock))
        out = prefix + str(count).encode() + b"\r\n"
        for _ in range(count):
            out += recv_nested(sock)
        return out
    raise RuntimeError(f"unexpected RESP prefix: {prefix!r}")


def recv_nested(sock: socket.socket) -> bytes:
    prefix = recv_exact(sock, 1)
    if prefix in (b"+", b"-", b":"):
        return prefix + recv_line(sock) + b"\r\n"
    if prefix == b"$":
        size = int(recv_line(sock))
        if size < 0:
            return b"$-1\r\n"
        payload = recv_exact(sock, size + 2)
        return prefix + str(size).encode() + b"\r\n" + payload
    raise RuntimeError(f"unexpected nested RESP prefix: {prefix!r}")


def stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)


def read_rss_kib(pid: int) -> int:
    status_path = Path(f"/proc/{pid}/status")
    if not status_path.exists():
        return 0
    for line in status_path.read_text().splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1])
    return 0


def total_rss_kib(*pids: int) -> int:
    total = 0
    for pid in pids:
        total += read_rss_kib(pid)
    return total


def percentile_ms(samples_ns: list[int], pct: float) -> float:
    if not samples_ns:
        return 0.0
    ordered = sorted(samples_ns)
    index = int((len(ordered) - 1) * pct)
    return ordered[index] / 1_000_000.0


def wait_for_replica_value(port: int, expected: bytes, deadline: float) -> None:
    while time.monotonic() < deadline:
        try:
            with connect_with_retry(port, time.monotonic() + 2.0) as sock:
                sock.settimeout(0.5)
                value = send_command(sock, b"GET", b"key")
                if value == expected:
                    return
        except (OSError, TimeoutError, RuntimeError):
            pass
        time.sleep(0.05)
    raise RuntimeError(f"replica did not converge to {expected!r} in time")


def wait_for_redis_uya_replication_state(port: int, marker: bytes, deadline: float) -> None:
    last = b""
    while time.monotonic() < deadline:
        try:
            with connect_with_retry(port, time.monotonic() + 2.0) as sock:
                sock.settimeout(0.5)
                last = send_command(sock, b"INFO", b"replication")
                if marker in last:
                    return
        except (OSError, TimeoutError, RuntimeError):
            pass
        time.sleep(0.05)
    raise RuntimeError(f"replication state marker {marker!r} not observed, last={last!r}")


def wait_for_redis_replication_status(port: int, status: bytes, deadline: float) -> None:
    last = b""
    marker = b"master_link_status:" + status
    while time.monotonic() < deadline:
        try:
            with connect_with_retry(port, time.monotonic() + 2.0) as sock:
                sock.settimeout(0.5)
                last = send_command(sock, b"INFO", b"replication")
                if marker in last:
                    return
        except (OSError, TimeoutError, RuntimeError):
            pass
        time.sleep(0.05)
    raise RuntimeError(f"redis replication status {status!r} not observed, last={last!r}")


def wait_for_replication_connected(impl: str, port: int, deadline: float) -> None:
    if impl == "redis-uya":
        wait_for_redis_uya_replication_state(port, b"replication_state:connected", deadline)
        return
    wait_for_redis_replication_status(port, b"up", deadline)


def wait_for_replication_disconnected(impl: str, port: int, deadline: float) -> None:
    if impl == "redis-uya":
        wait_for_redis_uya_replication_state(port, b"replication_state:configured", deadline)
        return
    wait_for_redis_replication_status(port, b"down", deadline)


def populate_master(sock: socket.socket, keys: int, value_bytes: int) -> None:
    value = b"x" * value_bytes
    for i in range(keys):
        key = f"k{i:06d}".encode()
        result = send_command(sock, b"SET", key, value)
        if result != b"+OK\r\n":
            raise RuntimeError(f"SET failed during populate: {result!r}")
    if send_command(sock, b"SET", b"key", b"value") != b"+OK\r\n":
        raise RuntimeError("SET key value failed")


def cleanup_paths(*paths: Path) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def cleanup_dirs(*paths: Path) -> None:
    for path in paths:
        if path.exists():
            shutil.rmtree(path)


def start_redis_uya(port: int, aof_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(BIN), str(port), "16", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def start_redis_server(port: int, workdir: Path, appendfilename: str, dbfilename: str, appenddirname: str) -> subprocess.Popen[str] | None:
    redis_server = command_path("redis-server")
    if redis_server is None:
        return None
    workdir.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            redis_server,
            "--port",
            str(port),
            "--bind",
            "127.0.0.1",
            "--appendonly",
            "yes",
            "--appendfilename",
            appendfilename,
            "--appenddirname",
            appenddirname,
            "--save",
            "",
            "--dir",
            str(workdir),
            "--dbfilename",
            dbfilename,
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def bench_full_sync_once(impl: str, start_master, start_replica, master_port: int, replica_port: int, cleanup, keys: int, value_bytes: int) -> tuple[int, int]:
    master = start_master()
    replica = start_replica()
    try:
        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            populate_master(sock, keys, value_bytes)
        t0 = time.perf_counter_ns()
        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            result = send_command(sock, b"REPLICAOF", b"127.0.0.1", str(master_port).encode())
            if result != b"+OK\r\n":
                raise RuntimeError(f"REPLICAOF failed: {result!r}")
        wait_for_replication_connected(impl, replica_port, time.monotonic() + 60.0)
        wait_for_replica_value(replica_port, b"$5\r\nvalue\r\n", time.monotonic() + 60.0)
        elapsed_ns = time.perf_counter_ns() - t0
        return elapsed_ns, total_rss_kib(master.pid, replica.pid)
    finally:
        stop_process(master)
        stop_process(replica)
        cleanup()


def bench_incremental_sync_once(impl: str, start_master, start_replica, master_port: int, replica_port: int, cleanup, keys: int, value_bytes: int) -> tuple[int, int]:
    master = start_master()
    replica = start_replica()
    try:
        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            populate_master(sock, keys, value_bytes)
        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            result = send_command(sock, b"REPLICAOF", b"127.0.0.1", str(master_port).encode())
            if result != b"+OK\r\n":
                raise RuntimeError(f"REPLICAOF failed: {result!r}")
        wait_for_replication_connected(impl, replica_port, time.monotonic() + 60.0)
        wait_for_replica_value(replica_port, b"$5\r\nvalue\r\n", time.monotonic() + 60.0)
        t0 = time.perf_counter_ns()
        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            result = send_command(sock, b"SET", b"key", b"newer")
            if result != b"+OK\r\n":
                raise RuntimeError(f"SET newer failed: {result!r}")
        wait_for_replica_value(replica_port, b"$5\r\nnewer\r\n", time.monotonic() + 60.0)
        elapsed_ns = time.perf_counter_ns() - t0
        return elapsed_ns, total_rss_kib(master.pid, replica.pid)
    finally:
        stop_process(master)
        stop_process(replica)
        cleanup()


def bench_reconnect_once(impl: str, start_master, start_replica, master_port: int, replica_port: int, cleanup, keys: int, value_bytes: int) -> tuple[int, int]:
    master = start_master()
    replica = start_replica()
    try:
        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            populate_master(sock, keys, value_bytes)
        with connect_with_retry(replica_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            result = send_command(sock, b"REPLICAOF", b"127.0.0.1", str(master_port).encode())
            if result != b"+OK\r\n":
                raise RuntimeError(f"REPLICAOF failed: {result!r}")
        wait_for_replication_connected(impl, replica_port, time.monotonic() + 60.0)
        wait_for_replica_value(replica_port, b"$5\r\nvalue\r\n", time.monotonic() + 60.0)

        stop_process(master)
        wait_for_replication_disconnected(impl, replica_port, time.monotonic() + 60.0)

        t0 = time.perf_counter_ns()
        master = start_master()
        wait_for_replication_connected(impl, replica_port, time.monotonic() + 60.0)
        with connect_with_retry(master_port, time.monotonic() + 5.0) as sock:
            sock.settimeout(2.0)
            result = send_command(sock, b"SET", b"key", b"after")
            if result != b"+OK\r\n":
                raise RuntimeError(f"SET after failed: {result!r}")
        wait_for_replica_value(replica_port, b"$5\r\nafter\r\n", time.monotonic() + 60.0)
        elapsed_ns = time.perf_counter_ns() - t0
        return elapsed_ns, total_rss_kib(master.pid, replica.pid)
    finally:
        stop_process(master)
        stop_process(replica)
        cleanup()


def format_env_line(case_name: str, dataset_kind: str) -> str:
    return (
        "REPL_BENCH_ENV version=1 "
        f"host_os={platform.system().lower()} "
        f"host_arch={platform.machine()} "
        f"cpu_model=\"{platform.processor() or 'unknown'}\" "
        "cpu_count=1 "
        "build_mode=debug "
        "durability=aof "
        f"dataset_kind={dataset_kind} "
        "benchmark_mode=master-replica "
        f"case_name={case_name}"
    )


def format_result_line(impl: str, case_name: str, runs: int, rss_kib: int, samples_ns: list[int]) -> str:
    return (
        "REPL_BENCH_RESULT version=1 "
        f"impl={impl} "
        f"case_name={case_name} "
        f"runs={runs} "
        f"p50_ms={percentile_ms(samples_ns, 0.50):.3f} "
        f"p95_ms={percentile_ms(samples_ns, 0.95):.3f} "
        f"p99_ms={percentile_ms(samples_ns, 0.99):.3f} "
        f"rss_kib={rss_kib}"
    )


def write_report(lines: list[str]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n")


def run_case(runs: int, fn) -> tuple[list[int], int]:
    samples: list[int] = []
    rss: list[int] = []
    for _ in range(runs):
        elapsed_ns, rss_kib = fn()
        samples.append(elapsed_ns)
        rss.append(rss_kib)
    return samples, max(rss) if rss else 0


def main() -> int:
    if not BIN.exists():
        print("[FAIL] benchmark_replication_v0_4_0: build/redis-uya is missing; run `make build` first", file=sys.stderr)
        return 1

    runs = int(os.environ.get("REDIS_UYA_REPL_BENCH_RUNS", "3"))
    keys = int(os.environ.get("REDIS_UYA_REPL_BENCH_KEYS", "150"))
    value_bytes = int(os.environ.get("REDIS_UYA_REPL_BENCH_VALUE_BYTES", "32"))

    redis_server_available = command_path("redis-server") is not None

    def make_uya_scenario():
        master_port = find_free_port()
        replica_port = find_free_port()
        master_aof = ROOT / "build" / f"repl-bench-master-{master_port}.aof"
        replica_aof = ROOT / "build" / f"repl-bench-replica-{replica_port}.aof"

        def cleanup() -> None:
            cleanup_paths(master_aof, replica_aof)

        def master_proc() -> subprocess.Popen[str]:
            return start_redis_uya(master_port, master_aof)

        def replica_proc() -> subprocess.Popen[str]:
            return start_redis_uya(replica_port, replica_aof)

        return master_proc, replica_proc, master_port, replica_port, cleanup

    def make_redis_scenario():
        master_port = find_free_port()
        replica_port = find_free_port()
        master_dir = ROOT / "build" / f"redis-repl-master-{master_port}"
        replica_dir = ROOT / "build" / f"redis-repl-replica-{replica_port}"
        master_aof_name = f"redis-repl-master-{master_port}.aof"
        replica_aof_name = f"redis-repl-replica-{replica_port}.aof"
        master_rdb_name = f"redis-repl-master-{master_port}.rdb"
        replica_rdb_name = f"redis-repl-replica-{replica_port}.rdb"
        master_aof = master_dir / master_aof_name
        replica_aof = replica_dir / replica_aof_name
        master_rdb = master_dir / master_rdb_name
        replica_rdb = replica_dir / replica_rdb_name

        def cleanup() -> None:
            cleanup_paths(master_aof, replica_aof, master_rdb, replica_rdb)
            cleanup_dirs(master_dir, replica_dir)

        def master_proc() -> subprocess.Popen[str]:
            proc = start_redis_server(
                master_port,
                master_dir,
                master_aof_name,
                master_rdb_name,
                "appendonlydir",
            )
            if proc is None:
                raise RuntimeError("redis-server is unavailable")
            return proc

        def replica_proc() -> subprocess.Popen[str]:
            proc = start_redis_server(
                replica_port,
                replica_dir,
                replica_aof_name,
                replica_rdb_name,
                "appendonlydir",
            )
            if proc is None:
                raise RuntimeError("redis-server is unavailable")
            return proc

        return master_proc, replica_proc, master_port, replica_port, cleanup

    report_lines = [
        "# redis-uya v0.4.0 replication benchmark",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "## Notes",
        f"- Dataset: {keys} string keys, value size {value_bytes} bytes.",
        "- Cases measure full sync, incremental convergence, and master reconnect recovery.",
        "- `rss_kib` records combined RSS of master + replica.",
    ]
    if redis_server_available:
        report_lines.append("- Redis same-machine baseline collected with two `redis-server` processes and `appendonly yes`.")
    else:
        report_lines.append("- `redis-server` is not installed on this machine, so Redis baseline is recorded as `skip`.")
    report_lines.extend(["", "## Raw Output", "", "```text"])

    cases = [
        ("full_sync", "string-kv", lambda: bench_full_sync_once("redis-uya", *make_uya_scenario(), keys, value_bytes)),
        ("incremental_sync", "string-kv", lambda: bench_incremental_sync_once("redis-uya", *make_uya_scenario(), keys, value_bytes)),
        ("reconnect_recovery", "string-kv", lambda: bench_reconnect_once("redis-uya", *make_uya_scenario(), keys, value_bytes)),
    ]

    redis_cases = None
    if redis_server_available:
        redis_cases = [
            ("full_sync", "string-kv", lambda: bench_full_sync_once("redis", *make_redis_scenario(), keys, value_bytes)),
            ("incremental_sync", "string-kv", lambda: bench_incremental_sync_once("redis", *make_redis_scenario(), keys, value_bytes)),
            ("reconnect_recovery", "string-kv", lambda: bench_reconnect_once("redis", *make_redis_scenario(), keys, value_bytes)),
        ]

    for case_name, dataset_kind, fn in cases:
        samples, rss_kib = run_case(runs, fn)
        report_lines.append(format_env_line(case_name, dataset_kind))
        report_lines.append(format_result_line("redis-uya", case_name, runs, rss_kib, samples))

        if redis_cases is not None:
            redis_fn = next(case_fn for redis_case_name, _, case_fn in redis_cases if redis_case_name == case_name)
            redis_samples, redis_rss = run_case(runs, redis_fn)
            report_lines.append(format_result_line("redis", case_name, runs, redis_rss, redis_samples))

    report_lines.append("```")
    write_report(report_lines)
    print(f"[PASS] benchmark_replication_v0_4_0: wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
