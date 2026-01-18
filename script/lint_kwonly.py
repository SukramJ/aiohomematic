#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Keyword-only parameter linter (mypy-style).

Enforces keyword-only parameters for all functions:
- Class methods: `*` must come after the first parameter (self/cls)
- Module-level functions: `*` must come before the first argument

No runtime overhead: standalone AST-based checker, no decorators required.

Exceptions (no violation reported):
  * Functions using *args (vararg)
  * Functions using positional-only parameters (/ in signature)

Disable options:
  * Class-wise: add a class attribute `__kwonly_check__ = False` or a trailing
    comment `# kwonly: disable` on the class definition line.
  * Function/Method-wise: add a trailing comment `# kwonly: disable` on the def
    line, or assign `__kwonly_check__ = False` as a first-level statement in the
    function body.
  * Module-wise: add `__kwonly_check__ = False` at module level.

Exit status is non-zero if any violations are found. Output is in a grep-friendly
format: "path:lineno:col: message".
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
import os
import sys

DISABLE_MARK = "kwonly: disable"
CLASS_FLAG_NAME = "__kwonly_check__"


@dataclass
class Violation:
    """Represents a single linter violation found in a file."""

    path: str
    line: int
    col: int
    message: str

    def __str__(self) -> str:
        """Return a human-readable representation of the violation."""
        return f"{self.path}:{self.line}:{self.col}: {self.message}"


class KwOnlyChecker(ast.NodeVisitor):
    """AST visitor that collects keyword-only parameter violations."""

    def __init__(self, *, path: str, lines: list[str]) -> None:
        """Initialize the checker with the file path and the file's source lines."""
        self.path = path
        self.lines = lines
        self.violations: list[Violation] = []
        self._class_disable_stack: list[bool] = []
        self._module_disabled: bool = False

    # Utility helpers
    def _line_has_disable_comment(self, *, lineno: int) -> bool:
        """Return True if the source line contains the inline disable marker."""
        # AST lineno is 1-based
        if not (1 <= lineno <= len(self.lines)):
            return False
        line = self.lines[lineno - 1]
        return DISABLE_MARK in line

    @staticmethod
    def _has_disable_flag_in_body(body: list[ast.stmt]) -> bool:
        """Return True if the body contains `__kwonly_check__ = False` assignment."""
        for node in body:
            # Look for simple assignments like: __kwonly_check__ = False
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if (
                        isinstance(t, ast.Name)
                        and t.id == CLASS_FLAG_NAME
                        and isinstance(node.value, ast.Constant)
                        and node.value.value is False
                    ):
                        return True
            # Stop scanning after first docstring/statement sequence
            # but in practice scanning entire body is fine and cheap
        return False

    @staticmethod
    def _first_param_name(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        """Return the first parameter name of a function (e.g., 'self' or 'cls')."""
        if func.args.args:
            return func.args.args[0].arg
        return None

    def _is_function_disabled(self, *, func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Return True if checking is disabled for this function."""
        # Disable via comment on def line
        if self._line_has_disable_comment(lineno=func.lineno):
            return True
        # Disable via in-body flag assignment
        return self._has_disable_flag_in_body(func.body)

    def _check_class_method_signature(
        self, *, func: ast.FunctionDef | ast.AsyncFunctionDef, class_disabled: bool
    ) -> None:
        """Check a class method and record a violation if it is not keyword-only."""
        # If module-level disable is set, skip
        if self._module_disabled:
            return

        if self._is_function_disabled(func=func):
            return

        # Ignore property setters: decorated with @<prop>.setter
        for dec in func.decorator_list:
            if isinstance(dec, ast.Attribute) and dec.attr == "setter":
                return

        # If class-level disable is set, skip
        if class_disabled:
            return

        args = func.args
        # Enforce: beyond the first arg (self/cls), there must be no positional parameters.
        extra_positional = args.args[1:] if len(args.args) > 1 else []
        has_vararg = args.vararg is not None
        has_posonly = bool(args.posonlyargs)

        # If *args is present in the signature, do not report a violation per policy.
        if has_vararg:
            return

        # If positional-only parameters are used (/ in signature), this is a deliberate
        # design choice and should not be flagged as a violation.
        if has_posonly:
            return

        # If there are any explicit positional parameters beyond the first, report.
        if extra_positional:
            suggestion = "add '*' after the first parameter to make the rest keyword-only"
            msg = f"method '{func.name}' must be keyword-only beyond first parameter; {suggestion}"
            self.violations.append(Violation(self.path, func.lineno, func.col_offset + 1, msg))

    def _check_module_function_signature(self, *, func: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Check a module-level function and record a violation if it is not keyword-only."""
        if self._module_disabled:
            return

        if self._is_function_disabled(func=func):
            return

        args = func.args
        # For module-level functions, ALL positional parameters are violations
        # (the * must come before the first argument)
        has_positional = bool(args.args)
        has_vararg = args.vararg is not None
        has_posonly = bool(args.posonlyargs)

        # If *args is present in the signature, do not report a violation per policy.
        if has_vararg:
            return

        # If positional-only parameters are used (/ in signature), this is a deliberate
        # design choice and should not be flagged as a violation.
        if has_posonly:
            return

        # If there are any positional parameters, report.
        if has_positional:
            suggestion = "add '*' before the first parameter to make all parameters keyword-only"
            msg = f"function '{func.name}' must be keyword-only; {suggestion}"
            self.violations.append(Violation(self.path, func.lineno, func.col_offset + 1, msg))

    # Node visitor implementations (visitor interface requires positional args)
    def visit_Module(self, node: ast.Module) -> None:
        """Visit a module, check for module-level disable, and process children."""
        # Check for module-level __kwonly_check__ = False
        self._module_disabled = self._has_disable_flag_in_body(node.body)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit a class, determine disable state, and check its methods."""
        # Determine if class-level disable applies
        class_disabled = self._line_has_disable_comment(lineno=node.lineno)
        if not class_disabled:
            # Look for __kwonly_check__ = False at class body level
            class_disabled = self._has_disable_flag_in_body(node.body)

        self._class_disable_stack.append(class_disabled)
        try:
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._check_class_method_signature(func=stmt, class_disabled=class_disabled)
                else:
                    self.visit(stmt)
        finally:
            self._class_disable_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check module-level functions for keyword-only parameters."""
        # Only top-level functions reach here (class methods handled in visit_ClassDef)
        self._check_module_function_signature(func=node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Check module-level async functions for keyword-only parameters."""
        self._check_module_function_signature(func=node)


def iter_python_files(*, paths: Iterable[str]) -> Iterable[str]:
    """Yield Python file paths discovered under given files/directories."""
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    if f.endswith(".py"):
                        yield os.path.join(root, f)
        elif p.endswith(".py") and os.path.exists(p):
            yield p


def check_file(*, path: str) -> list[Violation]:
    """Parse and check a Python file, returning any violations found."""
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
    except Exception as e:  # pragma: no cover - IO errors are not expected in CI
        return [Violation(path, 1, 1, f"failed to read file: {e}")]

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        return [Violation(path, e.lineno or 1, (e.offset or 0) + 1, f"syntax error: {e.msg}")]

    checker = KwOnlyChecker(path=path, lines=source.splitlines())
    checker.visit(tree)
    return checker.violations


def main(*, argv: list[str]) -> int:
    """Run the linter CLI and return a non-zero exit code on violations."""
    parser = argparse.ArgumentParser(description="Linter to enforce keyword-only parameters.")
    parser.add_argument("paths", nargs="+", help="Files or directories to check.")
    args = parser.parse_args(argv)

    all_violations: list[Violation] = []
    for file in iter_python_files(paths=args.paths):
        # Check all provided files; prek 'files' filter controls scope.
        all_violations.extend(check_file(path=file))

    if all_violations:
        # Print each unique violation only once (deduplicate by path/line/col/message)
        seen: set[tuple[str, int, int, str]] = set()
        for v in sorted(all_violations, key=lambda x: (x.path, x.line, x.col, x.message)):
            key = (v.path, v.line, v.col, v.message)
            if key in seen:
                continue
            seen.add(key)
            print(str(v))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
