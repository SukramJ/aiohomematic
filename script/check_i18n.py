# SPDX-License-Identifier: MIT
"""
Pre-commit hook: ensure exceptions and selected log messages use translated messages.

Rules:
- Exceptions:
  - For each `raise` constructing an Exception, if the first argument (or `message`/`msg` kw)
    is a string literal or f-string, it must be wrapped using `i18n.tr(...)` or `tr(...)`.
  - If there is no message argument, this check is skipped.
  - Pragmas to skip a single occurrence:
    - Inline on the same line: `# i18n-exc: ignore`
    - On the previous line: `# i18n-exc: ignore-next`

- Logging:
  - For each call like `logger.<level>(...)` or `logging.<level>(...)`, where `<level>` is one of the
    configured levels, if the first positional arg (or `msg` kw) is a string literal or f-string,
    it must be wrapped using `i18n.tr(...)` or `tr(...)`.
  - Pragmas to skip a single occurrence:
    - Inline on the same line: `# i18n-log: ignore`
    - On the previous line: `# i18n-log: ignore-next`

Outputs lines in the form:
  <path>:<line>: <message>
…and exits non-zero if any issues are found.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

PRAGMA_EXC_INLINE = "i18n-exc: ignore"
PRAGMA_EXC_NEXT = "i18n-exc: ignore-next"
PRAGMA_LOG_INLINE = "i18n-log: ignore"
PRAGMA_LOG_NEXT = "i18n-log: ignore-next"


@dataclass
class Finding:
    """Represents a single missing-translation finding from a file scan."""

    path: Path
    line: int
    message: str

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


def _get_log_msg_arg(call: ast.Call) -> ast.AST | None:
    """Return the AST node used as the message argument for a logging call if present."""
    # logging API uses first positional arg as the format string, or `msg=` kw
    if call.args:
        return call.args[0]
    for kw in call.keywords or []:
        if kw.arg == "msg":
            return kw.value
    return None


def _line_has_inline_pragma(lines: list[str], line_no_1based: int, *, for_logs: bool) -> bool:
    idx = max(0, min(len(lines), line_no_1based) - 1)
    line = lines[idx]
    return (PRAGMA_LOG_INLINE if for_logs else PRAGMA_EXC_INLINE) in line


def _prev_line_has_next_pragma(lines: list[str], line_no_1based: int, *, for_logs: bool) -> bool:
    prev_idx = line_no_1based - 2
    if prev_idx < 0:
        return False
    return (PRAGMA_LOG_NEXT if for_logs else PRAGMA_EXC_NEXT) in lines[prev_idx]


def _is_logging_level_call(node: ast.AST, levels: set[str]) -> ast.Call | None:
    """Return the Call if this node is a call of the form logger.<level>(...) or logging.<level>(...)."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Attribute):
        # Something like <expr>.<attr>(...)
        level = func.attr.lower()
        if level in levels:
            return node
    return None


def check_file(path: Path, *, log_levels: set[str]) -> list[Finding]:
    """Scan a Python file and report raises/logs with literal messages lacking i18n."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # skip invalid files
    lines = source.splitlines()

    findings: list[Finding] = []

    # 1) Exceptions
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
        if _line_has_inline_pragma(lines, lineno, for_logs=False) or _prev_line_has_next_pragma(
            lines, lineno, for_logs=False
        ):
            continue

        msg_node = _get_exception_msg_arg(call)
        if msg_node is None:
            continue  # no message provided

        # OK if it's a tr(...) call
        if _is_tr_call(msg_node):
            continue

        # If the arg is a literal/f-string or literal.format(...) -> must be translated
        if _is_literal_or_fstring(msg_node):
            findings.append(Finding(path=path, line=lineno, message="Missing exception translation"))
            continue

        # If it's another Call like func(...), we cannot know; be lenient and allow.
        # If it's a Name / Attribute (variable), also allow.

    # 2) Logging at configured levels
    if log_levels:
        for node in ast.walk(tree):
            call = _is_logging_level_call(node, log_levels)
            if call is None:
                continue

            lineno = getattr(call, "lineno", 1)
            if _line_has_inline_pragma(lines, lineno, for_logs=True) or _prev_line_has_next_pragma(
                lines, lineno, for_logs=True
            ):
                continue

            msg_node = _get_log_msg_arg(call)
            if msg_node is None:
                continue

            if _is_tr_call(msg_node):
                continue

            if _is_literal_or_fstring(msg_node):
                findings.append(Finding(path=path, line=lineno, message="Missing log translation"))
                continue

    return findings


def _parse_levels(value: str | None) -> set[str]:
    if not value:
        # Default: require translation for ERROR and above
        return {"error", "exception", "critical"}
    levels = {v.strip().lower() for v in value.split(",") if v.strip()}
    allowed = {"debug", "info", "warning", "error", "exception", "critical"}
    unknown = levels - allowed
    if unknown:
        # silently ignore unknown names but keep the known ones
        levels -= unknown
    return levels


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point: parse args, run checks, print findings, and return exit code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+")
    parser.add_argument(
        "--log-levels",
        help=(
            "Comma-separated logging levels to enforce translation for (e.g. 'warning,error'). "
            "Defaults to 'warning,error,exception,critical'."
        ),
        default=None,
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    log_levels = _parse_levels(args.log_levels)

    findings: list[Finding] = []
    for name in args.files:
        p = Path(name)
        if not p.exists() or p.suffix != ".py":
            continue
        findings.extend(check_file(p, log_levels=log_levels))

    for f in findings:
        print(str(f))

    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
