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
OUT = ROOT / "benchmarks" / "v0.1.0.md"


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
    return (
        b"*2\r\n"
        + b"$3\r\nGET\r\n"
        + f"${len(key)}\r\n".encode()
        + key
        + b"\r\n"
    )


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


def bench_set(sock: socket.socket, iterations: int, warmup: int) -> tuple[list[int], float]:
    expected = b"+OK\r\n"
    for i in range(warmup):
        key = f"warm:set:{i}".encode()
        value = f"value:{i}".encode()
        sock.sendall(make_set_request(key, value))
        recv_exact(sock, len(expected))

    samples: list[int] = []
    started = time.perf_counter()
    for i in range(iterations):
        key = f"bench:set:{i}".encode()
        value = f"value:{i}".encode()
        t0 = time.perf_counter_ns()
        sock.sendall(make_set_request(key, value))
        recv_exact(sock, len(expected))
        samples.append(time.perf_counter_ns() - t0)
    elapsed = time.perf_counter() - started
    return samples, elapsed


def bench_get(sock: socket.socket, iterations: int, warmup: int) -> tuple[list[int], float]:
    dataset = max(256, iterations)
    for i in range(dataset):
        key = f"bench:get:{i}".encode()
        value = f"value:{i}".encode()
        sock.sendall(make_set_request(key, value))
        recv_exact(sock, 5)

    for i in range(warmup):
        key = f"bench:get:{i % dataset}".encode()
        value = f"value:{i % dataset}".encode()
        expected = f"${len(value)}\r\n".encode() + value + b"\r\n"
        sock.sendall(make_get_request(key))
        recv_exact(sock, len(expected))

    samples: list[int] = []
    started = time.perf_counter()
    for i in range(iterations):
        key = f"bench:get:{i % dataset}".encode()
        value = f"value:{i % dataset}".encode()
        expected = f"${len(value)}\r\n".encode() + value + b"\r\n"
        t0 = time.perf_counter_ns()
        sock.sendall(make_get_request(key))
        recv_exact(sock, len(expected))
        samples.append(time.perf_counter_ns() - t0)
    elapsed = time.perf_counter() - started
    return samples, elapsed


def bench_target(port: int, iterations: int, warmup: int) -> dict[str, dict[str, float | int]]:
    sock = connect_with_retry(port, time.monotonic() + 5.0)
    sock.settimeout(2.0)
    try:
        cases = {
            "ping": bench_ping(sock, iterations, warmup),
            "set": bench_set(sock, iterations, warmup),
            "get": bench_get(sock, iterations, warmup),
        }
    finally:
        sock.close()

    results: dict[str, dict[str, float | int]] = {}
    for name, (samples_ns, elapsed) in cases.items():
        results[name] = {
            "p50_us": percentile_us(samples_ns, 0.50),
            "p95_us": percentile_us(samples_ns, 0.95),
            "p99_us": percentile_us(samples_ns, 0.99),
            "req_per_s": int(iterations / elapsed) if elapsed > 0 else 0,
        }
    return results


def start_redis_uya(port: int, aof_path: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [str(BIN), str(port), "16", str(aof_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def start_redis_server(port: int, workdir: Path) -> subprocess.Popen[str] | None:
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
            "--save",
            "",
            "--appendonly",
            "no",
            "--dir",
            str(workdir),
            "--dbfilename",
            f"redis-baseline-{port}.rdb",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def format_env_line(case_name: str) -> str:
    return (
        "BENCH_ENV version=1 "
        f"host_os={platform.system().lower()} "
        f"host_arch={platform.machine()} "
        f"cpu_model=\"{platform.processor() or 'unknown'}\" "
        "cpu_count=1 "
        "build_mode=debug "
        "durability=aof "
        "dataset_kind=string-kv "
        "benchmark_mode=single-thread "
        f"case_name={case_name}"
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
    baseline_rps: int | None,
) -> str:
    req_per_s = int(metrics["req_per_s"])
    return (
        "BENCH_RESULT version=1 "
        f"impl={impl} "
        f"case_name={case_name} "
        "benchmark_mode=single-thread "
        f"iterations={iterations} "
        f"p50_us={int(metrics['p50_us'])} "
        f"p95_us={int(metrics['p95_us'])} "
        f"p99_us={int(metrics['p99_us'])} "
        f"req_per_s={req_per_s} "
        f"rss_kib={rss_kib} "
        f"floor_status={classify_status(req_per_s, baseline_rps, 0.25)} "
        f"target_status={classify_status(req_per_s, baseline_rps, 1.00)} "
        f"stretch_status={classify_status(req_per_s, baseline_rps, 1.10)}"
    )


def write_report(report_lines: list[str]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(report_lines) + "\n")


def main() -> int:
    if not BIN.exists():
        print("[FAIL] benchmark_v0_1_0: build/redis-uya is missing; run `make build` first", file=sys.stderr)
        return 1

    iterations = int(os.environ.get("REDIS_UYA_BENCH_ITERS", "2000"))
    warmup = int(os.environ.get("REDIS_UYA_BENCH_WARMUP", "100"))

    redis_uya_port = find_free_port()
    redis_port = find_free_port()
    uya_aof = ROOT / "build" / f"bench-{redis_uya_port}.aof"
    uya_aof.unlink(missing_ok=True)
    uya_proc = start_redis_uya(redis_uya_port, uya_aof)
    redis_proc = start_redis_server(redis_port, ROOT / "build")

    try:
        uya_results = bench_target(redis_uya_port, iterations, warmup)
        uya_rss = read_rss_kib(uya_proc.pid)

        redis_results: dict[str, dict[str, float | int]] | None = None
        redis_rss = 0
        if redis_proc is not None:
            redis_results = bench_target(redis_port, iterations, warmup)
            redis_rss = read_rss_kib(redis_proc.pid)

        report_lines = [
            "# redis-uya v0.1.0 benchmark",
            "",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
            "",
            "## Notes",
        ]
        if redis_proc is None:
            report_lines.append("- `redis-server` is not installed on this machine, so same-machine Redis baseline is recorded as `skip`.")
        else:
            report_lines.append("- Redis same-machine baseline collected with `redis-server --appendonly no --save \"\"`.")
        report_lines.extend(
            [
                "- `redis-uya` is benchmarked with its default AOF path enabled.",
                "",
                "## Raw Output",
                "",
                "```text",
            ]
        )

        for case_name in ("ping", "set", "get"):
            report_lines.append(format_env_line(case_name))
            baseline_rps = None
            if redis_results is not None:
                baseline_rps = int(redis_results[case_name]["req_per_s"])
            report_lines.append(
                format_result_line("redis-uya", case_name, iterations, uya_rss, uya_results[case_name], baseline_rps)
            )
            if redis_results is not None:
                report_lines.append(
                    format_result_line("redis", case_name, iterations, redis_rss, redis_results[case_name], int(redis_results[case_name]["req_per_s"]))
                )

        report_lines.append("```")
        write_report(report_lines)
    finally:
        stop_process(uya_proc)
        uya_aof.unlink(missing_ok=True)
        if redis_proc is not None:
            stop_process(redis_proc)
            (ROOT / "build" / f"redis-baseline-{redis_port}.rdb").unlink(missing_ok=True)

    print(f"[PASS] benchmark_v0_1_0: wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
