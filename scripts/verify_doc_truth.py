#!/usr/bin/env python3
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "readme.md"
TODO = ROOT / "docs" / "redis-uya-todo.md"
DOD = ROOT / "docs" / "redis-uya-definition-of-done.md"
MATRIX = ROOT / "docs" / "redis-uya-command-matrix.md"
MAKEFILE = ROOT / "Makefile"
BENCH_SCRIPT = ROOT / "scripts" / "benchmark_v0_8_0.py"
VERSION_SOURCE = ROOT / "src" / "version.uya"


def require_match(pattern: str, text: str, label: str) -> re.Match[str]:
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise RuntimeError(f"missing {label}")
    return match


def integration_target_count(makefile: str) -> int:
    in_target = False
    count = 0
    for line in makefile.splitlines():
        if line.startswith("test-integration:"):
            in_target = True
            continue
        if in_target and line and not line.startswith("\t"):
            break
        if in_target and re.search(r"python3 tests/integration/[^ ]+\.py$", line.strip()):
            count += 1
    return count


def current_report_path(texts: list[str]) -> Path:
    pattern = re.compile(r"benchmarks/v0\.9\.3-release-performance-\d{4}-\d{2}-\d{2}-current-50k\.md")
    path_sets = [set(pattern.findall(text)) for text in texts]
    common = set.intersection(*path_sets)
    if len(common) != 1:
        raise RuntimeError(f"README/TODO/DoD must share one current 50K report, got {sorted(common)}")
    return ROOT / next(iter(common))


def report_ratios(report: str) -> tuple[str, str]:
    ratios: list[str] = []
    rss_ratio = ""
    for line in report.splitlines():
        match = re.match(
            r"\| (ping|set_16b|get_16b|set_1024b|get_1024b) \| \d+ \| \d+ \| ([0-9.]+x) \|.*\| ([0-9.]+x) \| (?:target|watch|critical) \|$",
            line,
        )
        if match is not None:
            ratios.append(match.group(2))
            if not rss_ratio:
                rss_ratio = match.group(3)
    if len(ratios) != 5 or not rss_ratio:
        raise RuntimeError("current 50K report case matrix is incomplete")
    return "/".join(ratios), rss_ratio


def main() -> int:
    errors: list[str] = []
    try:
        readme = README.read_text()
        todo = TODO.read_text()
        dod = DOD.read_text()
        matrix = MATRIX.read_text()
        makefile = MAKEFILE.read_text()
        bench_script = BENCH_SCRIPT.read_text()
        version_source = VERSION_SOURCE.read_text()

        version = require_match(r'return &"([^"]+)"', version_source, "runtime version").group(1)
        official = int(require_match(r"tracked official command names: `([0-9]+)`", matrix, "official command count").group(1))
        top_level = int(require_match(r"tracked top-level command names: `([0-9]+)`", matrix, "top-level command count").group(1))
        tier_a_match = require_match(
            r"\| Tier A: standalone core \| ([0-9]+) \| [0-9]+ \| ([0-9]+) \| ([0-9]+) \| ([0-9]+) \| ([0-9]+) \| ([0-9]+) \|",
            matrix,
            "Tier A counts",
        )
        tier_a = tuple(int(value) for value in tier_a_match.groups())
        integration_count = integration_target_count(makefile)
        bench_iters = int(require_match(r'REDIS_UYA_BENCH_ITERS", "([0-9]+)"', bench_script, "benchmark iterations default").group(1))
        bench_warmup = int(require_match(r'REDIS_UYA_BENCH_WARMUP", "([0-9]+)"', bench_script, "benchmark warmup default").group(1))

        texts = (("README", readme), ("TODO", todo), ("DoD", dod))
        for label, text in texts:
            if version not in text[:1000]:
                errors.append(f"{label} does not declare current version {version}")
            if str(official) not in text or str(top_level) not in text:
                errors.append(f"{label} does not record current command counts {official}/{top_level}")
            plain_text = text.replace("`", "")
            tier_a_pairs = (
                ("full", tier_a[1]),
                ("partial", tier_a[2]),
                ("standalone-error", tier_a[3]),
                ("alias", tier_a[4]),
                ("deferred", tier_a[5]),
            )
            if any(f"{status}={count}" not in plain_text for status, count in tier_a_pairs):
                errors.append(f"{label} does not record current Tier A counts")
            if f"{integration_count} \u9879" not in text:
                errors.append(f"{label} does not record current integration count {integration_count}")
            if f"{bench_iters // 1000}K" not in text or str(bench_warmup) not in text:
                errors.append(f"{label} does not record quick benchmark defaults {bench_iters}/{bench_warmup}")
            if "50K" not in text or "2000" not in text:
                errors.append(f"{label} does not record formal benchmark size 50000/2000")

        report_path = current_report_path([readme, todo, dod])
        if not report_path.exists():
            errors.append(f"current 50K report does not exist: {report_path.relative_to(ROOT)}")
        else:
            report = report_path.read_text()
            if report.count("iterations=50000") < 5 or report.count("warmup=2000") < 5:
                errors.append("current report is not a five-case 50K/2000 run")
            absolute_throughput_passes = len(re.findall(r"(?<!normalized_)throughput_status=pass", report))
            if absolute_throughput_passes != 5 or report.count("p99_status=pass") != 5:
                errors.append("current report absolute throughput/p99 guard is not fully green")
            ratios, rss_ratio = report_ratios(report)
            for label, text in texts:
                if ratios not in text:
                    errors.append(f"{label} does not match current Redis ratios {ratios}")
                if rss_ratio not in text:
                    errors.append(f"{label} does not match current RSS ratio {rss_ratio}")

        stale_readme_phrases = (
            "未实现 `SSUBSCRIBE/SPUBLISH`",
            "生成 `531` 个官方命令名目录",
            "尚未存储真实 field TTL 元数据",
            "尚不支持 `XADD` trim / `NOMKSTREAM`",
            "当前仓库主线已完成 `v0.8.1`",
        )
        for phrase in stale_readme_phrases:
            if phrase in readme:
                errors.append(f"README retains stale capability statement: {phrase}")
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            print(f"[FAIL] doc truth: {error}", file=sys.stderr)
        return 1
    print("document truth verification ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
