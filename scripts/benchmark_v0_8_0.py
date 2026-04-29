#!/usr/bin/env python3
import os
import platform
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "build" / "redis-uya"
DEFAULT_OUT = ROOT / "benchmarks" / "v0.8.0-performance.md"

CASE_NAMES = ("ping", "set_16b", "get_16b", "set_1024b", "get_1024b")


def benchmark_output_path() -> Path:
    configured = os.environ.get("REDIS_UYA_BENCH_OUT")
    if configured is None or configured == "":
        return DEFAULT_OUT
    out = Path(configured)
    if out.is_absolute():
        return out
    return ROOT / out


OUT = benchmark_output_path()


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


def value_payload(size: int, seed: int) -> bytes:
    if size <= 0:
        return b""
    pattern = f"value:{seed}:".encode()
    repeats = int(size / len(pattern)) + 1
    return (pattern * repeats)[:size]


def make_set_request(key: bytes, value: bytes) -> bytes:
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


def make_get_request(key: bytes) -> bytes:
    return b"*2\r\n" + b"$3\r\nGET\r\n" + f"${len(key)}\r\n".encode() + key + b"\r\n"


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


def percentile_us(samples_ns: list[int], pct: float) -> int:
    if not samples_ns:
        return 0
    ordered = sorted(samples_ns)
    index = int((len(ordered) - 1) * pct)
    return ordered[index] // 1000


def bench_ping(sock: socket.socket, iterations: int, warmup: int) -> tuple[list[int], float]:
    request = b"*1\r\n$4\r\nPING\r\n"
    expected = b"+PONG\r\n"
    for _ in range(warmup):
        sock.sendall(request)
        recv_exact(sock, len(expected))

    samples: list[int] = []
    started = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        sock.sendall(request)
        recv_exact(sock, len(expected))
        samples.append(time.perf_counter_ns() - t0)
    elapsed = time.perf_counter() - started
    return samples, elapsed


def bench_set(sock: socket.socket, case_name: str, value_bytes: int, iterations: int, warmup: int) -> tuple[list[int], float]:
    expected = b"+OK\r\n"
    for i in range(warmup):
        key = f"warm:{case_name}:{i}".encode()
        value = value_payload(value_bytes, i)
        sock.sendall(make_set_request(key, value))
        recv_exact(sock, len(expected))

    samples: list[int] = []
    started = time.perf_counter()
    for i in range(iterations):
        key = f"bench:{case_name}:{i}".encode()
        value = value_payload(value_bytes, i)
        request = make_set_request(key, value)
        t0 = time.perf_counter_ns()
        sock.sendall(request)
        recv_exact(sock, len(expected))
        samples.append(time.perf_counter_ns() - t0)
    elapsed = time.perf_counter() - started
    return samples, elapsed


def bench_get(sock: socket.socket, case_name: str, value_bytes: int, iterations: int, warmup: int) -> tuple[list[int], float]:
    dataset = max(256, iterations)
    for i in range(dataset):
        key = f"bench:{case_name}:{i}".encode()
        value = value_payload(value_bytes, i)
        sock.sendall(make_set_request(key, value))
        recv_exact(sock, 5)

    for i in range(warmup):
        index = i % dataset
        key = f"bench:{case_name}:{index}".encode()
        value = value_payload(value_bytes, index)
        expected = f"${len(value)}\r\n".encode() + value + b"\r\n"
        sock.sendall(make_get_request(key))
        recv_exact(sock, len(expected))

    samples: list[int] = []
    started = time.perf_counter()
    for i in range(iterations):
        index = i % dataset
        key = f"bench:{case_name}:{index}".encode()
        value = value_payload(value_bytes, index)
        expected = f"${len(value)}\r\n".encode() + value + b"\r\n"
        t0 = time.perf_counter_ns()
        sock.sendall(make_get_request(key))
        recv_exact(sock, len(expected))
        samples.append(time.perf_counter_ns() - t0)
    elapsed = time.perf_counter() - started
    return samples, elapsed


def run_case(sock: socket.socket, case_name: str, iterations: int, warmup: int) -> tuple[list[int], float, int]:
    if case_name == "ping":
        samples, elapsed = bench_ping(sock, iterations, warmup)
        return samples, elapsed, 0
    if case_name == "set_16b":
        samples, elapsed = bench_set(sock, case_name, 16, iterations, warmup)
        return samples, elapsed, 16
    if case_name == "get_16b":
        samples, elapsed = bench_get(sock, case_name, 16, iterations, warmup)
        return samples, elapsed, 16
    if case_name == "set_1024b":
        samples, elapsed = bench_set(sock, case_name, 1024, iterations, warmup)
        return samples, elapsed, 1024
    if case_name == "get_1024b":
        samples, elapsed = bench_get(sock, case_name, 1024, iterations, warmup)
        return samples, elapsed, 1024
    raise RuntimeError(f"unknown benchmark case: {case_name}")


def bench_target(port: int, iterations: int, warmup: int) -> dict[str, dict[str, float | int]]:
    sock = connect_with_retry(port, time.monotonic() + 5.0)
    sock.settimeout(5.0)
    try:
        results: dict[str, dict[str, float | int]] = {}
        for case_name in CASE_NAMES:
            samples_ns, elapsed, value_bytes = run_case(sock, case_name, iterations, warmup)
            results[case_name] = {
                "value_bytes": value_bytes,
                "p50_us": percentile_us(samples_ns, 0.50),
                "p95_us": percentile_us(samples_ns, 0.95),
                "p99_us": percentile_us(samples_ns, 0.99),
                "req_per_s": int(iterations / elapsed) if elapsed > 0 else 0,
            }
        return results
    finally:
        sock.close()


def start_redis_uya(port: int, aof_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(BIN), str(port), "64", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def start_redis_server(port: int, workdir: Path) -> subprocess.Popen[str] | None:
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
            "--save",
            "",
            "--appendonly",
            "yes",
            "--appendfsync",
            "no",
            "--dir",
            str(workdir),
            "--dbfilename",
            f"redis-baseline-{port}.rdb",
            "--appendfilename",
            "appendonly.aof",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(errors="ignore").splitlines():
            if line.startswith("model name"):
                _, _, value = line.partition(":")
                stripped = value.strip()
                if stripped:
                    return stripped
    return platform.processor() or "unknown"


def quote_env_value(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def format_env_line(case_name: str, value_bytes: int, iterations: int, warmup: int) -> str:
    return (
        "BENCH_ENV version=1 "
        f"host_os={platform.system().lower()} "
        f"host_arch={platform.machine()} "
        f"cpu_model={quote_env_value(cpu_model())} "
        f"cpu_count={os.cpu_count() or 1} "
        "build_mode=debug "
        "durability=aof-no-fsync "
        "dataset_kind=string-kv "
        "benchmark_mode=single-thread "
        f"case_name={case_name} "
        f"value_bytes={value_bytes} "
        f"iterations={iterations} "
        f"warmup={warmup} "
        "client_pipeline=1"
    )


def classify_status(current_rps: int, baseline_rps: int | None, ratio: float) -> str:
    if baseline_rps is None or baseline_rps <= 0:
        return "skip"
    return "pass" if current_rps >= int(baseline_rps * ratio) else "miss"


def format_result_line(
    impl: str,
    case_name: str,
    iterations: int,
    rss_kib: int,
    metrics: dict[str, float | int],
    redis_rps: int | None,
) -> str:
    req_per_s = int(metrics["req_per_s"])
    return (
        "BENCH_RESULT version=1 "
        f"impl={impl} "
        f"case_name={case_name} "
        "benchmark_mode=single-thread "
        f"value_bytes={int(metrics['value_bytes'])} "
        f"iterations={iterations} "
        f"p50_us={int(metrics['p50_us'])} "
        f"p95_us={int(metrics['p95_us'])} "
        f"p99_us={int(metrics['p99_us'])} "
        f"req_per_s={req_per_s} "
        f"rss_kib={rss_kib} "
        f"floor_status={classify_status(req_per_s, redis_rps, 0.25)} "
        f"target_status={classify_status(req_per_s, redis_rps, 1.00)} "
        f"stretch_status={classify_status(req_per_s, redis_rps, 1.10)}"
    )


def parse_result_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in shlex.split(line):
        key, sep, value = token.partition("=")
        if sep == "=":
            fields[key] = value
    return fields


def load_guard_baseline(path: Path | None) -> dict[str, dict[str, int]]:
    if path is None or not path.exists():
        return {}
    baseline: dict[str, dict[str, int]] = {}
    for line in path.read_text().splitlines():
        if not line.startswith("BENCH_RESULT "):
            continue
        fields = parse_result_fields(line)
        if fields.get("impl") != "redis-uya":
            continue
        case_name = fields.get("case_name")
        if case_name is None:
            continue
        baseline[case_name] = {
            "req_per_s": int(fields.get("req_per_s", "0")),
            "p99_us": int(fields.get("p99_us", "0")),
        }
    return baseline


def format_guard_line(
    case_name: str,
    current: dict[str, float | int],
    baseline: dict[str, dict[str, int]],
    min_rps_ratio: float,
    max_p99_ratio: float,
    p99_abs_slack_us: int,
) -> tuple[str, bool]:
    current_rps = int(current["req_per_s"])
    current_p99 = int(current["p99_us"])
    base = baseline.get(case_name)
    if base is None or base["req_per_s"] <= 0 or base["p99_us"] <= 0:
        return (
            "PERF_GUARD_RESULT version=1 "
            f"case_name={case_name} "
            "baseline_req_per_s=0 current_req_per_s="
            f"{current_rps} min_req_per_s=0 throughput_status=skip "
            "baseline_p99_us=0 current_p99_us="
            f"{current_p99} max_p99_us=0 p99_status=skip",
            True,
        )

    min_req_per_s = int(base["req_per_s"] * min_rps_ratio)
    max_p99_us = max(int(base["p99_us"] * max_p99_ratio), base["p99_us"] + p99_abs_slack_us)
    throughput_status = "pass" if current_rps >= min_req_per_s else "miss"
    p99_status = "pass" if current_p99 <= max_p99_us else "miss"
    return (
        "PERF_GUARD_RESULT version=1 "
        f"case_name={case_name} "
        f"baseline_req_per_s={base['req_per_s']} "
        f"current_req_per_s={current_rps} "
        f"min_req_per_s={min_req_per_s} "
        f"throughput_status={throughput_status} "
        f"baseline_p99_us={base['p99_us']} "
        f"current_p99_us={current_p99} "
        f"max_p99_us={max_p99_us} "
        f"p99_status={p99_status}",
        throughput_status == "pass" and p99_status == "pass",
    )


def write_report(report_lines: list[str]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(report_lines) + "\n")


def display_path(path: Path) -> Path:
    if path.is_relative_to(ROOT):
        return path.relative_to(ROOT)
    return path


def main() -> int:
    if not BIN.exists():
        print("[FAIL] benchmark_v0_8_0: build/redis-uya is missing; run `make build` first", file=sys.stderr)
        return 1

    iterations = int(os.environ.get("REDIS_UYA_BENCH_ITERS", "5000"))
    warmup = int(os.environ.get("REDIS_UYA_BENCH_WARMUP", "200"))
    min_rps_ratio = float(os.environ.get("REDIS_UYA_REGRESSION_RPS_RATIO", "0.90"))
    max_p99_ratio = float(os.environ.get("REDIS_UYA_REGRESSION_P99_RATIO", "1.15"))
    p99_abs_slack_us = int(os.environ.get("REDIS_UYA_REGRESSION_P99_ABS_US", "100"))
    baseline_env = os.environ.get("REDIS_UYA_BENCH_BASELINE")
    baseline_path = None if baseline_env is None or baseline_env == "" else Path(baseline_env)
    if baseline_path is not None and not baseline_path.is_absolute():
        baseline_path = ROOT / baseline_path
    guard_baseline = load_guard_baseline(baseline_path)

    redis_uya_port = find_free_port()
    redis_port = find_free_port()
    uya_aof = ROOT / "build" / f"bench-v0.8.0-{redis_uya_port}.aof"
    redis_workdir = ROOT / "build" / f"redis-v0.8.0-{redis_port}"
    uya_aof.unlink(missing_ok=True)
    shutil.rmtree(redis_workdir, ignore_errors=True)

    uya_proc = start_redis_uya(redis_uya_port, uya_aof)
    redis_proc = start_redis_server(redis_port, redis_workdir)

    guard_ok = True
    try:
        uya_results = bench_target(redis_uya_port, iterations, warmup)
        uya_rss = read_rss_kib(uya_proc.pid)

        redis_results: dict[str, dict[str, float | int]] | None = None
        redis_rss = 0
        if redis_proc is not None:
            redis_results = bench_target(redis_port, iterations, warmup)
            redis_rss = read_rss_kib(redis_proc.pid)

        report_lines = [
            "# redis-uya v0.8.0 performance benchmark",
            "",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
            "",
            "## Notes",
            "",
            "- Matrix: `PING`, `SET`/`GET` with 16B values, and `SET`/`GET` with 1KiB values.",
            "- `redis-uya` is benchmarked with AOF enabled and no explicit fsync.",
            "- Redis same-machine baseline uses `appendonly yes`, `appendfsync no`, and `save \"\"`.",
            f"- Regression guard defaults: throughput must stay >= {min_rps_ratio:.2f}x baseline; p99 must stay <= max({max_p99_ratio:.2f}x baseline, baseline + {p99_abs_slack_us}us).",
        ]
        if redis_proc is None:
            report_lines.append("- `redis-server` is not installed on this machine, so same-machine Redis baseline is recorded as `skip`.")
        if baseline_path is None:
            report_lines.append("- No `REDIS_UYA_BENCH_BASELINE` was provided; guard rows are recorded as `skip` for this baseline run.")
        else:
            report_lines.append(f"- Guard baseline: `{display_path(baseline_path)}`.")

        report_lines.extend(["", "## Raw Output", "", "```text"])

        for case_name in CASE_NAMES:
            value_bytes = int(uya_results[case_name]["value_bytes"])
            report_lines.append(format_env_line(case_name, value_bytes, iterations, warmup))
            redis_rps = None
            if redis_results is not None:
                redis_rps = int(redis_results[case_name]["req_per_s"])
            report_lines.append(format_result_line("redis-uya", case_name, iterations, uya_rss, uya_results[case_name], redis_rps))
            if redis_results is not None:
                report_lines.append(
                    format_result_line(
                        "redis",
                        case_name,
                        iterations,
                        redis_rss,
                        redis_results[case_name],
                        int(redis_results[case_name]["req_per_s"]),
                    )
                )
            guard_line, case_guard_ok = format_guard_line(
                case_name,
                uya_results[case_name],
                guard_baseline,
                min_rps_ratio,
                max_p99_ratio,
                p99_abs_slack_us,
            )
            guard_ok = guard_ok and case_guard_ok
            report_lines.append(guard_line)

        report_lines.append("```")
        write_report(report_lines)
    finally:
        stop_process(uya_proc)
        uya_aof.unlink(missing_ok=True)
        if redis_proc is not None:
            stop_process(redis_proc)
        shutil.rmtree(redis_workdir, ignore_errors=True)

    print(f"[PASS] benchmark_v0_8_0: wrote {display_path(OUT)}")
    if not guard_ok:
        print("[FAIL] benchmark_v0_8_0: regression guard missed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
