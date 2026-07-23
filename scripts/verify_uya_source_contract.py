#!/usr/bin/env python3
"""Reject project-internal exported globals that would create a public C ABI."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = ROOT / "src"
EXPORTED_GLOBAL = re.compile(r"^\s*export\s+(?:const|var)\b")


def main() -> int:
    violations: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.uya")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if EXPORTED_GLOBAL.match(line):
                relative = path.relative_to(ROOT)
                violations.append(f"{relative}:{line_number}: {line.strip()}")

    if violations:
        print("project source must keep globals private and expose module APIs with export fn", file=sys.stderr)
        for violation in violations:
            print(violation, file=sys.stderr)
        return 1

    print("Uya source contract passed: no exported project globals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
