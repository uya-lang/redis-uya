#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_command_scope import MatrixEntry, parse_matrix, validate_entries


class VerifyCommandScopeTest(unittest.TestCase):
    def test_repository_matrix_passes_release_scope_gate(self) -> None:
        entries = parse_matrix(ROOT / "docs" / "redis-uya-command-matrix.md")
        self.assertEqual(validate_entries(entries), [])

    def test_tier_a_deferred_command_is_rejected(self) -> None:
        errors = validate_entries([MatrixEntry("get", "string", "deferred", "v0.9.4")])
        self.assertIn("Tier A contains 1 deferred command(s)", errors)

    def test_tier_b_deferred_command_is_rejected(self) -> None:
        errors = validate_entries([MatrixEntry("cluster|help", "cluster", "deferred", "v1.1.0")])
        self.assertIn("Tier B contains 1 deferred command(s)", errors)

    def test_deferred_command_requires_target_version(self) -> None:
        errors = validate_entries([MatrixEntry("ts.read", "timeseries", "deferred", "-")])
        self.assertIn("deferred command has no target version: ts.read", errors)

    def test_parser_rejects_empty_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.md"
            path.write_text("# empty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "has no entries"):
                parse_matrix(path)

    def test_parser_preserves_subcommand_separator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.md"
            path.write_text(
                "## Matrix\n\n"
                "| name | group | status | target | arity | module | pattern | acl |\n"
                "|------|-------|--------|--------|-------|--------|---------|-----|\n"
                "| `acl|help` | `server` | `full` | `-` | `2` | `-` | `no` | `@slow` |\n",
                encoding="utf-8",
            )
            entries = parse_matrix(path)
            self.assertEqual(entries[0].name, "acl|help")


if __name__ == "__main__":
    unittest.main()
