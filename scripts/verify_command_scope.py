#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from generate_command_catalog import TIER_A_GROUPS, TIER_B_GROUPS, TIER_C_GROUPS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "docs" / "redis-uya-command-matrix.md"
VALID_STATUSES = {"full", "partial", "standalone-error", "alias", "deferred"}
MATRIX_ROW_RE = re.compile(
    r"^\| `([^`]*)` \| `([^`]*)` \| `([^`]*)` \| `([^`]*)` \| "
    r"`([^`]*)` \| `([^`]*)` \| `([^`]*)` \| `([^`]*)` \|$"
)


@dataclass(frozen=True)
class MatrixEntry:
    name: str
    group: str
    status: str
    target: str


def parse_matrix(path: Path) -> list[MatrixEntry]:
    entries: list[MatrixEntry] = []
    in_matrix = False
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if raw_line == "## Matrix":
            in_matrix = True
            continue
        if not in_matrix or not raw_line.startswith("| `"):
            continue
        match = MATRIX_ROW_RE.fullmatch(raw_line)
        if match is None:
            raise ValueError(f"{path}:{line_number}: expected 8 matrix columns")
        values = match.groups()
        entries.append(MatrixEntry(name=values[0], group=values[1], status=values[2], target=values[3]))
    if not entries:
        raise ValueError(f"{path}: command matrix has no entries")
    return entries


def tier_for(group: str) -> str | None:
    if group in TIER_A_GROUPS:
        return "Tier A"
    if group in TIER_B_GROUPS:
        return "Tier B"
    if group in TIER_C_GROUPS:
        return "Tier C"
    return None


def validate_entries(entries: list[MatrixEntry]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    counts: Counter[tuple[str, str]] = Counter()
    for entry in entries:
        if entry.name in seen:
            errors.append(f"duplicate command entry: {entry.name}")
        seen.add(entry.name)

        tier = tier_for(entry.group)
        if tier is None:
            errors.append(f"unclassified command group: {entry.name} uses {entry.group}")
            continue
        if entry.status not in VALID_STATUSES:
            errors.append(f"invalid status: {entry.name} uses {entry.status}")
            continue
        counts[(tier, entry.status)] += 1

        if entry.status in {"deferred", "standalone-error"} and entry.target == "-":
            errors.append(f"{entry.status} command has no target version: {entry.name}")
        if entry.status not in {"deferred", "standalone-error"} and entry.target != "-":
            errors.append(f"implemented command keeps a target version: {entry.name}")

    for tier in ("Tier A", "Tier B"):
        deferred = counts[(tier, "deferred")]
        if deferred:
            errors.append(f"{tier} contains {deferred} deferred command(s)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="verify redis-uya command scope release gates")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    args = parser.parse_args()

    try:
        entries = parse_matrix(args.matrix)
    except (OSError, ValueError) as exc:
        print(f"command scope verification failed: {exc}")
        return 1
    errors = validate_entries(entries)
    if errors:
        for error in errors:
            print(f"command scope verification failed: {error}")
        return 1

    tier_counts = Counter(tier_for(entry.group) for entry in entries)
    deferred_counts = Counter(tier_for(entry.group) for entry in entries if entry.status == "deferred")
    print(
        "command scope verification ok: "
        f"Tier A {tier_counts['Tier A']} entries/{deferred_counts['Tier A']} deferred, "
        f"Tier B {tier_counts['Tier B']} entries/{deferred_counts['Tier B']} deferred, "
        f"Tier C {tier_counts['Tier C']} entries/{deferred_counts['Tier C']} deferred"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
