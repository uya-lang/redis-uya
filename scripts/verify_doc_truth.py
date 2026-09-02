#!/usr/bin/env python3
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "readme.md"
TODO = ROOT / "docs" / "redis-uya-todo.md"
DOD = ROOT / "docs" / "redis-uya-definition-of-done.md"
API = ROOT / "docs" / "redis-uya-api.md"
ARCHITECTURE = ROOT / "docs" / "redis-uya-architecture.md"
QUICKSTART = ROOT / "docs" / "redis-uya-quickstart.md"
DESIGN = ROOT / "docs" / "redis-uya-design.md"
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
        api = API.read_text()
        architecture = ARCHITECTURE.read_text()
        quickstart = QUICKSTART.read_text()
        design = DESIGN.read_text()
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

        status_texts = (("README", readme), ("TODO", todo), ("DoD", dod))
        semantic_texts = (
            ("API", api),
            ("Architecture", architecture),
            ("Quickstart", quickstart),
            ("Design", design),
        )
        all_current_texts = (*status_texts, *semantic_texts)
        for label, text in all_current_texts:
            if version not in text[:1000]:
                errors.append(f"{label} does not declare current version {version}")

        for label, text in status_texts:
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

        for label, text in (("API", api), ("Quickstart", quickstart), ("Design", design)):
            if str(official) not in text or str(top_level) not in text:
                errors.append(f"{label} does not record current command counts {official}/{top_level}")

        design_plain = design.replace("`", "")
        tier_a_pairs = (
            ("full", tier_a[1]),
            ("partial", tier_a[2]),
            ("standalone-error", tier_a[3]),
            ("alias", tier_a[4]),
            ("deferred", tier_a[5]),
        )
        if any(f"{status}={count}" not in design_plain for status, count in tier_a_pairs):
            errors.append("Design does not record current Tier A counts")

        if f"{integration_count} \u9879" not in quickstart:
            errors.append(f"Quickstart does not record current integration count {integration_count}")
        if f"{bench_iters // 1000}K" not in quickstart or str(bench_warmup) not in quickstart:
            errors.append(f"Quickstart does not record quick benchmark defaults {bench_iters}/{bench_warmup}")
        if "50K" not in quickstart or "2000" not in quickstart:
            errors.append("Quickstart does not record formal benchmark size 50000/2000")

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
            for label, text in status_texts:
                if ratios not in text:
                    errors.append(f"{label} does not match current Redis ratios {ratios}")
                if rss_ratio not in text:
                    errors.append(f"{label} does not match current RSS ratio {rss_ratio}")

            report_reference = str(report_path.relative_to(ROOT))
            if report_reference not in quickstart:
                errors.append(f"Quickstart does not reference current 50K report {report_reference}")

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

        required_capability_markers = {
            "API": ("`SSUBSCRIBE`", "`NOMKSTREAM`", "field TTL", "\u590d\u5236 backlog"),
            "Architecture": ("`SSUBSCRIBE`", "NOMKSTREAM", "field TTL", "replication backlog"),
            "Quickstart": ("`SSUBSCRIBE", "`NOMKSTREAM`", "Lua/Functions", "consumer group/PEL"),
            "Design": ("Sharded Pub/Sub", "`EVAL*`", "consumer group/PEL", "libc `fork()`"),
        }
        semantic_map = {
            "API": api,
            "Architecture": architecture,
            "Quickstart": quickstart,
            "Design": design,
        }
        for label, markers in required_capability_markers.items():
            text = semantic_map[label]
            for marker in markers:
                if marker not in text:
                    errors.append(f"{label} is missing current capability marker: {marker}")

        stale_semantic_phrases = {
            "API": ("`531` \u4e2a\u5b98\u65b9\u547d\u4ee4\u540d",),
            "Quickstart": (
                "> \u7248\u672c: v0.7.0",
                "\u4e0d\u652f\u6301 master \u4e3b\u52a8\u6d41\u5f0f\u63a8\u9001\u590d\u5236\u3001\u5b8c\u6574\u96c6\u7fa4 gossip/failover\u3001Lua\u3001Redis \u6a21\u5757",
            ),
            "Design": (
                "> \u7248\u672c: v0.9.0-planning",
                "| Lua | \u274c \u4e0d\u652f\u6301",
                "| Streams | \u274c \u4e0d\u652f\u6301",
                "| Functions | \u274c \u4e0d\u652f\u6301",
                "\u7531\u4e8e uya \u76ee\u524d\u4e0d\u652f\u6301\u76f4\u63a5 fork()",
                "v0.1.0 \u521d\u59cb\u7248\u672c",
            ),
        }
        for label, phrases in stale_semantic_phrases.items():
            text = semantic_map[label]
            for phrase in phrases:
                if phrase in text:
                    errors.append(f"{label} retains stale statement: {phrase}")
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
