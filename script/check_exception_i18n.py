# SPDX-License-Identifier: MIT
"""
Pre-commit hook: ensure exceptions use translated messages.

Rules:
- For each `raise` constructing an Exception, if the first argument (or `message`/`msg` kw)
  is a string literal or f-string, it must be wrapped using `i18n.tr(...)` or `tr(...)`.
- If there is no message argument, this check is skipped.
- Pragma to skip a single occurrence:
  - Inline on the same line: `# i18n-exc: ignore`
  - On the previous line: `# i18n-exc: ignore-next`

Outputs lines in the form:
  <path>:<line>: Missing exception translation
and exits non-zero if any issues are found.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

PRAGMA_INLINE = "i18n-exc: ignore"
PRAGMA_NEXT = "i18n-exc: ignore-next"


@dataclass
class Finding:
    """Represents a single missing-translation finding from a file scan."""

    path: Path
    line: int
    message: str = "Missing exception translation"

    def __str__(self) -> str:  # pragma: no cover - trivial
        """Return CLI-friendly representation of the finding."""
        return f"{self.path}:{self.line}: {self.message}"


def _is_tr_call(node: ast.AST) -> bool:
    """Return True if node is a call to i18n.tr(...) or tr(...)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.attr == "tr" and func.value.id == "i18n"
    if isinstance(func, ast.Name):
        return func.id == "tr"
    return False


def _is_literal_or_fstring(node: ast.AST) -> bool:
    """Return True if node represents a string literal or f-string-like expression."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):  # f"..."
        return True
    # str.format on a literal: "...".format(...)
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Constant)
        and isinstance(node.func.value.value, str)
        and node.func.attr == "format"
    )


def _get_exception_msg_arg(call: ast.Call) -> ast.AST | None:
    """Return the AST node used as the message argument for an exception call if present."""
    # first positional argument
    if call.args:
        return call.args[0]
    # keyword argument commonly used
    for kw in call.keywords or []:
        if kw.arg in {"message", "msg"}:
            return kw.value
    return None


def _line_has_inline_pragma(lines: list[str], line_no_1based: int) -> bool:
    idx = max(0, min(len(lines), line_no_1based) - 1)
    line = lines[idx]
    return PRAGMA_INLINE in line


def _prev_line_has_next_pragma(lines: list[str], line_no_1based: int) -> bool:
    prev_idx = line_no_1based - 2
    if prev_idx < 0:
        return False
    return PRAGMA_NEXT in lines[prev_idx]


def check_file(path: Path) -> list[Finding]:
    """Scan a Python file and report raises with literal messages lacking i18n."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # skip invalid files
    lines = source.splitlines()

    findings: list[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue
        if node.exc is None:
            continue
        exc = node.exc
        call: ast.Call | None
        if isinstance(exc, ast.Call):
            call = exc
        elif isinstance(exc, (ast.Name, ast.Attribute)):
            # `raise SomeExc` — no args
            call = None
        else:
            call = None
        if call is None:
            continue

        # Pragma checks
        lineno = getattr(node, "lineno", 1)
        if _line_has_inline_pragma(lines, lineno) or _prev_line_has_next_pragma(lines, lineno):
            continue

        msg_node = _get_exception_msg_arg(call)
        if msg_node is None:
            continue  # no message provided

        # OK if it's a tr(...) call
        if _is_tr_call(msg_node):
            continue

        # If the arg is a literal/f-string or literal.format(...) -> must be translated
        if _is_literal_or_fstring(msg_node):
            findings.append(Finding(path=path, line=lineno))
            continue

        # If it's another Call like func(...), we cannot know; be lenient and allow.
        # If it's a Name / Attribute (variable), also allow.

    return findings


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point: parse args, run checks, print findings, and return exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(list(argv) if argv is not None else None)

    findings: list[Finding] = []
    for name in args.files:
        p = Path(name)
        if not p.exists() or p.suffix != ".py":
            continue
        findings.extend(check_file(p))

    for f in findings:
        print(str(f))

    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
