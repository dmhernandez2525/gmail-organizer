#!/usr/bin/env python3
"""Measure validator line, bytecode-branch, and function coverage without plugins."""

from __future__ import annotations

import argparse
import ast
import dis
import json
import sys
import types
from collections import Counter
from pathlib import Path

import pytest


def code_key(code: types.CodeType) -> tuple[str, int]:
    return code.co_qualname, code.co_firstlineno


def iter_code_objects(code: types.CodeType):
    yield code
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            yield from iter_code_objects(constant)


def percentage(covered: int, total: int) -> float:
    return round(100.0 * covered / total, 2) if total else 0.0


def possible_branch_arcs(
    code: types.CodeType, excluded_lines: set[int]
) -> set[tuple[tuple[str, int], int, int]]:
    instructions = list(dis.get_instructions(code))
    unconditional_jumps = {
        "JUMP_ABSOLUTE",
        "JUMP_BACKWARD",
        "JUMP_BACKWARD_NO_INTERRUPT",
        "JUMP_FORWARD",
    }
    arcs: set[tuple[tuple[str, int], int, int]] = set()
    key = code_key(code)
    jump_opcodes = {*dis.hasjabs, *dis.hasjrel}
    for index, instruction in enumerate(instructions[:-1]):
        if instruction.opcode not in jump_opcodes:
            continue
        if instruction.opname in unconditional_jumps:
            continue
        if instruction.positions.lineno in excluded_lines:
            continue
        if not isinstance(instruction.argval, int):
            continue
        arcs.add((key, instruction.offset, instruction.argval))
        arcs.add((key, instruction.offset, instructions[index + 1].offset))
    return arcs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum", type=float, default=80.0)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("scripts/validate_gmail_organizer_runtime.py"),
    )
    parser.add_argument(
        "--tests",
        type=Path,
        default=Path("tests/test_runtime_validator.py"),
    )
    args = parser.parse_args()

    source_path = args.source.resolve()
    source_text = source_path.read_text(encoding="utf-8")
    syntax_tree = ast.parse(source_text, filename=str(source_path))
    excluded_branch_lines = {
        node.lineno for node in ast.walk(syntax_tree) if isinstance(node, ast.ExceptHandler)
    }
    excluded_branch_lines.update(
        node.lineno
        for node in syntax_tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )
    compiled = compile(source_text, str(source_path), "exec")
    code_objects = list(iter_code_objects(compiled))
    measured_code_objects = [
        code
        for code in code_objects
        if code.co_name == "<module>"
        or (not code.co_name.startswith("<") and code.co_name != "__annotate__")
    ]
    static_lines = {
        instruction.positions.lineno
        for code in measured_code_objects
        for instruction in dis.get_instructions(code)
        if instruction.positions and instruction.positions.lineno is not None
    }
    static_functions = {
        code_key(code) for code in measured_code_objects if code.co_name != "<module>"
    }
    static_branches = set().union(
        *(possible_branch_arcs(code, excluded_branch_lines) for code in measured_code_objects)
    )

    executed_lines: set[int] = set()
    called_functions: set[tuple[str, int]] = set()
    executed_arcs: set[tuple[tuple[str, int], int, int]] = set()
    previous_offsets: dict[int, int] = {}
    target_filename = str(source_path)

    def tracer(frame, event, _argument):
        if frame.f_code.co_filename != target_filename:
            return tracer

        frame_id = id(frame)
        key = code_key(frame.f_code)
        if event == "call":
            frame.f_trace_opcodes = True
            called_functions.add(key)
            previous_offsets[frame_id] = -1
        elif event == "line":
            executed_lines.add(frame.f_lineno)
        elif event == "opcode":
            previous = previous_offsets.get(frame_id, -1)
            if previous >= 0:
                executed_arcs.add((key, previous, frame.f_lasti))
            previous_offsets[frame_id] = frame.f_lasti
        elif event == "return":
            previous_offsets.pop(frame_id, None)
        return tracer

    sys.settrace(tracer)
    try:
        pytest_exit = int(pytest.main([str(args.tests), "-q"]))
    finally:
        sys.settrace(None)
    if pytest_exit != 0:
        return pytest_exit

    metrics = {
        "Line": percentage(len(static_lines & executed_lines), len(static_lines)),
        "Branch": percentage(len(static_branches & executed_arcs), len(static_branches)),
        "Function": percentage(len(static_functions & called_functions), len(static_functions)),
    }
    print(json.dumps(metrics, sort_keys=True))
    failures = {name: value for name, value in metrics.items() if value < args.minimum}
    if failures:
        missing_functions = sorted(static_functions - called_functions)
        if missing_functions:
            print(f"Uncovered functions: {missing_functions}", file=sys.stderr)
        instructions_by_offset = {
            (code_key(code), instruction.offset): instruction
            for code in measured_code_objects
            for instruction in dis.get_instructions(code)
        }
        missing_branch_kinds = Counter(
            instructions_by_offset[(key, source)].opname
            for key, source, _target in static_branches - executed_arcs
        )
        if missing_branch_kinds:
            print(f"Uncovered branch opcodes: {dict(missing_branch_kinds)}", file=sys.stderr)
            missing_details = []
            for key, source, target in sorted(static_branches - executed_arcs):
                instruction = instructions_by_offset[(key, source)]
                target_instruction = instructions_by_offset.get((key, target))
                target_line = (
                    target_instruction.positions.lineno if target_instruction is not None else None
                )
                missing_details.append(
                    f"{key[0]}:{instruction.positions.lineno}:{instruction.opname}->{target_line}"
                )
            print(f"Uncovered branch arcs: {missing_details}", file=sys.stderr)
        rendered = ", ".join(f"{name}={value}%" for name, value in failures.items())
        raise SystemExit(f"Validator coverage is below {args.minimum}%: {rendered}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
