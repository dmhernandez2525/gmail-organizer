#!/usr/bin/env python3
"""Enforce separate line, branch, and function coverage thresholds."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def percentage(covered: int, total: int) -> float:
    return round(100.0 * covered / total, 2) if total else 0.0


def find_validator_record(document: dict, source_path: Path) -> dict:
    expected = source_path.as_posix()
    matches = [
        record
        for path, record in document.get("files", {}).items()
        if path.replace("\\", "/").endswith(expected)
    ]
    if len(matches) != 1:
        raise ValueError("Coverage JSON did not contain exactly one validator source record.")
    return matches[0]


def function_entry_lines(source_path: Path) -> list[int]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    return [
        node.body[0].lineno
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.body
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--minimum", type=float, default=80.0)
    args = parser.parse_args()

    document = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    record = find_validator_record(document, args.source)
    summary = record["summary"]
    executed_lines = set(record["executed_lines"])
    entries = function_entry_lines(args.source)
    metrics = {
        "Line": percentage(summary["covered_lines"], summary["num_statements"]),
        "Branch": percentage(summary["covered_branches"], summary["num_branches"]),
        "Function": percentage(sum(line in executed_lines for line in entries), len(entries)),
    }
    print(json.dumps(metrics, sort_keys=True))
    failures = {name: value for name, value in metrics.items() if value < args.minimum}
    if failures:
        rendered = ", ".join(f"{name}={value}%" for name, value in failures.items())
        raise SystemExit(f"Validator coverage is below {args.minimum}%: {rendered}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
