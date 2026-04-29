#!/usr/bin/env python3
from __future__ import annotations

import os
import shlex
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "benchmarks" / "v0.8.0-performance.md"
DEFAULT_OUT = ROOT / "benchmarks" / "v0.8.0-gap-report.md"
CASE_ORDER = ("ping", "set_16b", "get_16b", "set_1024b", "get_1024b")


def configured_path(env_name: str, default: Path) -> Path:
    configured = os.environ.get(env_name)
    if configured is None or configured == "":
        return default
    path = Path(configured)
    if path.is_absolute():
        return path
    return ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def quote_field(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_result_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in shlex.split(line):
        key, sep, value = token.partition("=")
        if sep == "=":
            fields[key] = value
    return fields


def load_results(path: Path) -> dict[str, dict[str, dict[str, int]]]:
    results: dict[str, dict[str, dict[str, int]]] = {}
    for line in path.read_text().splitlines():
        if not line.startswith("BENCH_RESULT "):
            continue
        fields = parse_result_fields(line)
        impl = fields.get("impl")
        case_name = fields.get("case_name")
        if impl is None or case_name is None:
            continue
        results.setdefault(case_name, {})[impl] = {
            "p50_us": int(fields.get("p50_us", "0")),
            "p95_us": int(fields.get("p95_us", "0")),
            "p99_us": int(fields.get("p99_us", "0")),
            "req_per_s": int(fields.get("req_per_s", "0")),
            "rss_kib": int(fields.get("rss_kib", "0")),
        }
    return results


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def ratio_text(value: float | None) -> str:
    if value is None:
        return "skip"
    return f"{value:.2f}x"


def status_for(throughput_ratio: float | None, p99_ratio: float | None) -> str:
    if throughput_ratio is None or p99_ratio is None:
        return "skip"
    if throughput_ratio < 0.25 or p99_ratio > 4.0:
        return "critical"
    if throughput_ratio < 0.75 or p99_ratio > 2.0:
        return "high"
    if throughput_ratio < 1.00 or p99_ratio > 1.15:
        return "watch"
    return "pass"


def gap_rows(results: dict[str, dict[str, dict[str, int]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case_name in CASE_ORDER:
        impls = results.get(case_name, {})
        uya = impls.get("redis-uya")
        redis = impls.get("redis")
        if uya is None:
            continue
        throughput_ratio = ratio(uya["req_per_s"], 0 if redis is None else redis["req_per_s"])
        p99_ratio = ratio(uya["p99_us"], 0 if redis is None else redis["p99_us"])
        rss_ratio = ratio(uya["rss_kib"], 0 if redis is None else redis["rss_kib"])
        rows.append(
            {
                "case_name": case_name,
                "uya": uya,
                "redis": redis,
                "throughput_ratio": throughput_ratio,
                "p99_ratio": p99_ratio,
                "rss_ratio": rss_ratio,
                "status": status_for(throughput_ratio, p99_ratio),
            }
        )
    return rows


def machine_gap_line(row: dict[str, object]) -> str:
    uya = row["uya"]  # type: ignore[assignment]
    redis = row["redis"]  # type: ignore[assignment]
    redis_req_per_s = 0 if redis is None else redis["req_per_s"]  # type: ignore[index]
    redis_p99_us = 0 if redis is None else redis["p99_us"]  # type: ignore[index]
    redis_rss_kib = 0 if redis is None else redis["rss_kib"]  # type: ignore[index]
    throughput_ratio = row["throughput_ratio"]
    p99_ratio = row["p99_ratio"]
    rss_ratio = row["rss_ratio"]
    return (
        "PERF_GAP_RESULT version=1 "
        f"case_name={row['case_name']} "
        f"redis_uya_req_per_s={uya['req_per_s']} "
        f"redis_req_per_s={redis_req_per_s} "
        f"throughput_ratio={0.0 if throughput_ratio is None else throughput_ratio:.4f} "
        f"redis_uya_p99_us={uya['p99_us']} "
        f"redis_p99_us={redis_p99_us} "
        f"p99_ratio={0.0 if p99_ratio is None else p99_ratio:.4f} "
        f"redis_uya_rss_kib={uya['rss_kib']} "
        f"redis_rss_kib={redis_rss_kib} "
        f"rss_ratio={0.0 if rss_ratio is None else rss_ratio:.4f} "
        f"status={row['status']}"
    )


def row_summary(row: dict[str, object]) -> str:
    case_name = str(row["case_name"])
    throughput = ratio_text(row["throughput_ratio"])  # type: ignore[arg-type]
    p99 = ratio_text(row["p99_ratio"])  # type: ignore[arg-type]
    return f"{case_name} throughput_ratio={throughput} p99_ratio={p99}"


def debt_queue(rows: list[dict[str, object]]) -> list[dict[str, str]]:
    queue: list[dict[str, str]] = []
    rows_by_name = {str(row["case_name"]): row for row in rows}
    set_rows = [rows_by_name[name] for name in ("set_16b", "set_1024b") if name in rows_by_name]
    get_rows = [rows_by_name[name] for name in ("get_16b", "get_1024b") if name in rows_by_name]
    ping = rows_by_name.get("ping")

    if any(row["status"] in ("critical", "high") for row in set_rows):
        worst = min(
            set_rows,
            key=lambda row: 999.0 if row["throughput_ratio"] is None else row["throughput_ratio"],  # type: ignore[operator]
        )
        queue.append(
            {
                "priority": "P0",
                "area": "set_write_path",
                "cases": ",".join(str(row["case_name"]) for row in set_rows),
                "evidence": row_summary(worst),
                "next": "split AOF append, dict insert, object allocation, and SDS copy cost with counters before changing semantics",
            }
        )

    if any(row["status"] in ("critical", "high", "watch") for row in get_rows):
        worst_get = min(
            get_rows,
            key=lambda row: 999.0 if row["throughput_ratio"] is None else row["throughput_ratio"],  # type: ignore[operator]
        )
        queue.append(
            {
                "priority": "P1",
                "area": "get_response_path",
                "cases": ",".join(str(row["case_name"]) for row in get_rows),
                "evidence": row_summary(worst_get),
                "next": "measure parser, lookup, reply encode, writev, and event loop costs separately for hit-only GET",
            }
        )

    rss_rows = [row for row in rows if row["rss_ratio"] is not None and row["rss_ratio"] > 3.0]  # type: ignore[operator]
    if rss_rows:
        worst_rss = max(rss_rows, key=lambda row: row["rss_ratio"])  # type: ignore[arg-type]
        queue.append(
            {
                "priority": "P1",
                "area": "rss_residency",
                "cases": "all",
                "evidence": f"{worst_rss['case_name']} rss_ratio={ratio_text(worst_rss['rss_ratio'])}",  # type: ignore[arg-type]
                "next": "separate debug build footprint from allocator/object residency and add release-build benchmark mode",
            }
        )

    if ping is not None and ping["status"] in ("high", "watch"):
        queue.append(
            {
                "priority": "P2",
                "area": "round_trip_overhead",
                "cases": "ping",
                "evidence": row_summary(ping),
                "next": "profile request parse, command dispatch, reply formatting, and epoll wakeups on empty-command path",
            }
        )

    queue.append(
        {
            "priority": "P2",
            "area": "pipeline_and_batching",
            "cases": "all",
            "evidence": "current matrix is single-thread client_pipeline=1",
            "next": "add pipelined benchmark cases before making batched RESP parsing part of the production connection loop",
        }
    )
    return queue


def machine_debt_line(item: dict[str, str]) -> str:
    return (
        "PERF_DEBT_RESULT version=1 "
        f"priority={item['priority']} "
        f"area={item['area']} "
        f"cases={item['cases']} "
        f"evidence={quote_field(item['evidence'])} "
        f"next={quote_field(item['next'])}"
    )


def write_report(source: Path, out: Path, rows: list[dict[str, object]], queue: list[dict[str, str]]) -> None:
    analyzed = len(rows)
    critical = sum(1 for row in rows if row["status"] == "critical")
    high = sum(1 for row in rows if row["status"] == "high")
    watch = sum(1 for row in rows if row["status"] == "watch")
    best = max(rows, key=lambda row: -1.0 if row["throughput_ratio"] is None else row["throughput_ratio"]) if rows else None
    worst = min(rows, key=lambda row: 999.0 if row["throughput_ratio"] is None else row["throughput_ratio"]) if rows else None

    lines = [
        "# redis-uya v0.8.0 Redis gap report",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"Source: `{display_path(source)}`",
        "",
        "## Summary",
        "",
        f"- Analyzed cases: {analyzed}",
        f"- Status counts: critical={critical}, high={high}, watch={watch}",
    ]
    if best is not None:
        lines.append(f"- Best throughput ratio: `{best['case_name']}` at {ratio_text(best['throughput_ratio'])}")  # type: ignore[arg-type]
    if worst is not None:
        lines.append(f"- Largest throughput gap: `{worst['case_name']}` at {ratio_text(worst['throughput_ratio'])}")  # type: ignore[arg-type]
    lines.extend(
        [
            "- This report is a follow-up queue, not a v0.8.0 release gate.",
            "",
            "## Case Matrix",
            "",
            "| Case | redis-uya req/s | Redis req/s | Throughput ratio | redis-uya p99 us | Redis p99 us | p99 ratio | RSS ratio | Status |",
            "|------|-----------------|-------------|------------------|------------------|--------------|-----------|-----------|--------|",
        ]
    )
    for row in rows:
        uya = row["uya"]  # type: ignore[assignment]
        redis = row["redis"]  # type: ignore[assignment]
        redis_req_per_s = 0 if redis is None else redis["req_per_s"]  # type: ignore[index]
        redis_p99_us = 0 if redis is None else redis["p99_us"]  # type: ignore[index]
        lines.append(
            f"| `{row['case_name']}` | {uya['req_per_s']} | {redis_req_per_s} | "
            f"{ratio_text(row['throughput_ratio'])} | {uya['p99_us']} | {redis_p99_us} | "
            f"{ratio_text(row['p99_ratio'])} | {ratio_text(row['rss_ratio'])} | `{row['status']}` |"
        )

    lines.extend(
        [
            "",
            "## Follow-up Queue",
            "",
            "| Priority | Area | Cases | Evidence | Next action |",
            "|----------|------|-------|----------|-------------|",
        ]
    )
    for item in queue:
        lines.append(
            f"| `{item['priority']}` | `{item['area']}` | `{item['cases']}` | "
            f"{item['evidence']} | {item['next']} |"
        )

    lines.extend(["", "## Raw Output", "", "```text"])
    lines.extend(machine_gap_line(row) for row in rows)
    lines.extend(machine_debt_line(item) for item in queue)
    lines.append("```")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


def main() -> int:
    source = configured_path("REDIS_UYA_GAP_INPUT", DEFAULT_INPUT)
    out = configured_path("REDIS_UYA_GAP_OUT", DEFAULT_OUT)
    if not source.exists():
        print(f"[FAIL] report_v0_8_0_gaps: missing input report {display_path(source)}")
        return 1
    rows = gap_rows(load_results(source))
    if not rows:
        print(f"[FAIL] report_v0_8_0_gaps: no BENCH_RESULT rows in {display_path(source)}")
        return 1
    queue = debt_queue(rows)
    write_report(source, out, rows, queue)
    print(f"[PASS] report_v0_8_0_gaps: wrote {display_path(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
