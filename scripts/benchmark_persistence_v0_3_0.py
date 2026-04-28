#!/usr/bin/env python3
import os
import platform
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "redis-uya"
OUT = ROOT / "benchmarks" / "v0.3.0-persistence.md"


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


def recv_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        ch = sock.recv(1)
        if not ch:
            raise RuntimeError("connection closed while reading line")
        chunks.append(ch)
        if len(chunks) >= 2 and chunks[-2] == b"\r" and chunks[-1] == b"\n":
            return b"".join(chunks[:-2])


def recv_resp(sock: socket.socket):
    prefix = sock.recv(1)
    if not prefix:
        raise RuntimeError("connection closed while reading response")
    if prefix == b"+":
        return recv_line(sock).decode()
    if prefix == b"-":
        raise RuntimeError(recv_line(sock).decode())
    if prefix == b":":
        return int(recv_line(sock))
    if prefix == b"$":
        length = int(recv_line(sock))
        if length < 0:
            return None
        data = b""
        remaining = length
        while remaining > 0:
            chunk = sock.recv(remaining)
            if not chunk:
                raise RuntimeError("connection closed while reading bulk string")
            data += chunk
            remaining -= len(chunk)
        if sock.recv(2) != b"\r\n":
            raise RuntimeError("invalid bulk string terminator")
        return data
    if prefix == b"*":
        count = int(recv_line(sock))
        if count < 0:
            return None
        return [recv_resp(sock) for _ in range(count)]
    raise RuntimeError(f"unsupported RESP prefix: {prefix!r}")


def send_command(sock: socket.socket, *parts: bytes):
    chunks = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        chunks.append(f"${len(part)}\r\n".encode())
        chunks.append(part)
        chunks.append(b"\r\n")
    sock.sendall(b"".join(chunks))
    return recv_resp(sock)


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


def percentile_ms(samples_ns: list[int], pct: float) -> float:
    if not samples_ns:
        return 0.0
    ordered = sorted(samples_ns)
    index = int((len(ordered) - 1) * pct)
    return ordered[index] / 1_000_000.0


def start_redis_uya(port: int, aof_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(BIN), str(port), "16", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def start_redis_server(port: int, workdir: Path, appendfilename: str, dbfilename: str) -> subprocess.Popen[str] | None:
    redis_server = command_path("redis-server")
    if redis_server is None:
        return None
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


def wait_ready(port: int) -> socket.socket:
    sock = connect_with_retry(port, time.monotonic() + 5.0)
    sock.settimeout(2.0)
    return sock


def populate_dataset(sock: socket.socket, keys: int, value_bytes: int) -> None:
    value = b"x" * value_bytes
    for i in range(keys):
        key = f"k{i:06d}".encode()
        result = send_command(sock, b"SET", key, value)
        if result != "OK":
            raise RuntimeError(f"SET failed during populate: {result!r}")


def cleanup_paths(*paths: Path) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def bench_save_once(start_proc, port: int, keys: int, value_bytes: int, cleanup) -> tuple[int, int]:
    proc = start_proc()
    try:
        sock = wait_ready(port)
        try:
            populate_dataset(sock, keys, value_bytes)
            t0 = time.perf_counter_ns()
            result = send_command(sock, b"SAVE")
            if result != "OK":
                raise RuntimeError(f"SAVE failed: {result!r}")
            elapsed_ns = time.perf_counter_ns() - t0
            return elapsed_ns, read_rss_kib(proc.pid)
        finally:
            sock.close()
    finally:
        stop_process(proc)
        cleanup()


def bench_restart_recovery_aof_once(start_fresh_proc, start_existing_proc, port: int, keys: int, value_bytes: int, cleanup) -> tuple[int, int]:
    proc = start_fresh_proc()
    key = f"k{keys - 1:06d}".encode()
    expected = b"x" * value_bytes
    try:
        sock = wait_ready(port)
        try:
            populate_dataset(sock, keys, value_bytes)
        finally:
            sock.close()
        stop_process(proc)

        t0 = time.perf_counter_ns()
        proc = start_existing_proc()
        sock = wait_ready(port)
        try:
            value = send_command(sock, b"GET", key)
            if value != expected:
                raise RuntimeError(f"unexpected recovered value: {value!r}")
        finally:
            sock.close()
        elapsed_ns = time.perf_counter_ns() - t0
        return elapsed_ns, read_rss_kib(proc.pid)
    finally:
        stop_process(proc)
        cleanup()


def bench_restart_recovery_rdb_aof_once(start_fresh_proc, start_existing_proc, port: int, keys: int, value_bytes: int, cleanup) -> tuple[int, int]:
    proc = start_fresh_proc()
    try:
        sock = wait_ready(port)
        try:
            populate_dataset(sock, keys, value_bytes)
            if send_command(sock, b"SET", b"key", b"base") != "OK":
                raise RuntimeError("SET key base failed")
            if send_command(sock, b"SAVE") != "OK":
                raise RuntimeError("SAVE failed")
            if send_command(sock, b"SET", b"key", b"newer") != "OK":
                raise RuntimeError("SET key newer failed")
            if send_command(sock, b"SET", b"extra", b"value") != "OK":
                raise RuntimeError("SET extra failed")
        finally:
            sock.close()
        stop_process(proc)

        t0 = time.perf_counter_ns()
        proc = start_existing_proc()
        sock = wait_ready(port)
        try:
            key_value = send_command(sock, b"GET", b"key")
            extra_value = send_command(sock, b"GET", b"extra")
            if key_value != b"newer" or extra_value != b"value":
                raise RuntimeError(f"unexpected mixed recovery values: key={key_value!r} extra={extra_value!r}")
        finally:
            sock.close()
        elapsed_ns = time.perf_counter_ns() - t0
        return elapsed_ns, read_rss_kib(proc.pid)
    finally:
        stop_process(proc)
        cleanup()


def format_env_line(case_name: str, dataset_kind: str) -> str:
    return (
        "PERSIST_BENCH_ENV version=1 "
        f"host_os={platform.system().lower()} "
        f"host_arch={platform.machine()} "
        f"cpu_model=\"{platform.processor() or 'unknown'}\" "
        "cpu_count=1 "
        "build_mode=debug "
        "durability=persistence "
        f"dataset_kind={dataset_kind} "
        f"case_name={case_name}"
    )


def format_result_line(impl: str, case_name: str, runs: int, rss_kib: int, samples_ns: list[int]) -> str:
    return (
        "PERSIST_BENCH_RESULT version=1 "
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


def run_case(name: str, runs: int, fn) -> tuple[list[int], int]:
    samples: list[int] = []
    rss: list[int] = []
    for _ in range(runs):
        elapsed_ns, rss_kib = fn()
        samples.append(elapsed_ns)
        rss.append(rss_kib)
    return samples, max(rss) if rss else 0


def main() -> int:
    if not BIN.exists():
        print("[FAIL] benchmark_persistence_v0_3_0: build/redis-uya is missing; run `make build` first", file=sys.stderr)
        return 1

    runs = int(os.environ.get("REDIS_UYA_PERSIST_BENCH_RUNS", "3"))
    keys = int(os.environ.get("REDIS_UYA_PERSIST_BENCH_KEYS", "2000"))
    value_bytes = int(os.environ.get("REDIS_UYA_PERSIST_BENCH_VALUE_BYTES", "32"))

    uya_port = find_free_port()
    redis_port = find_free_port()
    uya_aof = ROOT / "build" / f"persist-bench-{uya_port}.aof"
    uya_rdb = ROOT / "build" / "dump.rdb"
    redis_aof_name = f"redis-persist-{redis_port}.aof"
    redis_rdb_name = f"redis-persist-{redis_port}.rdb"
    redis_aof = ROOT / "build" / redis_aof_name
    redis_rdb = ROOT / "build" / redis_rdb_name

    def cleanup_uya() -> None:
        cleanup_paths(uya_aof, uya_rdb)

    def cleanup_redis() -> None:
        cleanup_paths(redis_aof, redis_rdb)

    def uya_proc_fresh() -> subprocess.Popen[str]:
        cleanup_uya()
        return start_redis_uya(uya_port, uya_aof)

    def uya_proc_existing() -> subprocess.Popen[str]:
        return start_redis_uya(uya_port, uya_aof)

    redis_server_available = command_path("redis-server") is not None

    def redis_proc_fresh() -> subprocess.Popen[str]:
        cleanup_redis()
        proc = start_redis_server(redis_port, ROOT / "build", redis_aof_name, redis_rdb_name)
        if proc is None:
            raise RuntimeError("redis-server is unavailable")
        return proc

    def redis_proc_existing() -> subprocess.Popen[str]:
        proc = start_redis_server(redis_port, ROOT / "build", redis_aof_name, redis_rdb_name)
        if proc is None:
            raise RuntimeError("redis-server is unavailable")
        return proc

    report_lines = [
        "# redis-uya v0.3.0 persistence benchmark",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "## Notes",
        f"- Dataset: {keys} keys, value size {value_bytes} bytes.",
        "- Cases measure blocking `SAVE`, restart recovery from AOF, and restart recovery from mixed RDB+AOF state.",
    ]
    if redis_server_available:
        report_lines.append("- Redis same-machine baseline collected with `redis-server --appendonly yes --save \"\"`.")
    else:
        report_lines.append("- `redis-server` is not installed on this machine, so Redis baseline is recorded as `skip`.")
    report_lines.extend(["", "## Raw Output", "", "```text"])

    cases = [
        ("save", "string-kv", lambda: bench_save_once(uya_proc_fresh, uya_port, keys, value_bytes, cleanup_uya)),
        ("restart_recovery_aof", "string-kv", lambda: bench_restart_recovery_aof_once(uya_proc_fresh, uya_proc_existing, uya_port, keys, value_bytes, cleanup_uya)),
        ("restart_recovery_rdb_aof", "string-kv", lambda: bench_restart_recovery_rdb_aof_once(uya_proc_fresh, uya_proc_existing, uya_port, keys, value_bytes, cleanup_uya)),
    ]

    redis_cases = None
    if redis_server_available:
        redis_cases = [
            ("save", "string-kv", lambda: bench_save_once(redis_proc_fresh, redis_port, keys, value_bytes, cleanup_redis)),
            ("restart_recovery_aof", "string-kv", lambda: bench_restart_recovery_aof_once(redis_proc_fresh, redis_proc_existing, redis_port, keys, value_bytes, cleanup_redis)),
            ("restart_recovery_rdb_aof", "string-kv", lambda: bench_restart_recovery_rdb_aof_once(redis_proc_fresh, redis_proc_existing, redis_port, keys, value_bytes, cleanup_redis)),
        ]

    for case_name, dataset_kind, fn in cases:
        samples, rss_kib = run_case(case_name, runs, fn)
        report_lines.append(format_env_line(case_name, dataset_kind))
        report_lines.append(format_result_line("redis-uya", case_name, runs, rss_kib, samples))

        if redis_cases is not None:
            redis_fn = next(case_fn for redis_case_name, _, case_fn in redis_cases if redis_case_name == case_name)
            redis_samples, redis_rss = run_case(case_name, runs, redis_fn)
            report_lines.append(format_result_line("redis", case_name, runs, redis_rss, redis_samples))

    report_lines.append("```")
    write_report(report_lines)
    print(f"[PASS] benchmark_persistence_v0_3_0: wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
