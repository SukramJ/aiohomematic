#!/usr/bin/env python3
"""
Linter for ReGa scripts (.fn files).

This script validates and auto-fixes ReGa script headers:
1. First line must be '!# name: <filename>'
2. All parameters (##param##) used in the script must be declared with '!# param: "##param##"'
3. Header lines (!# name: and !# param:) must be at the top of the file

Usage:
    python script/lint_rega_scripts.py [--fix] [files...]

If no files are specified, all .fn files in aiohomematic/rega_scripts/ are checked.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

# Pattern to find parameters like ##interface##, ##id##, ##value##
PARAM_PATTERN = re.compile(r"##([a-zA-Z_][a-zA-Z0-9_]*)##")

# Header line patterns
NAME_PATTERN = re.compile(r"^!# name:\s*(.+)$")
PARAM_DECL_PATTERN = re.compile(r'^!# param:\s*"##([a-zA-Z_][a-zA-Z0-9_]*)##"$')


def find_used_parameters(content: str) -> set[str]:
    """Find all ##param## style parameters used in the script content."""
    return set(PARAM_PATTERN.findall(content))


def parse_script(content: str) -> tuple[str | None, set[str], list[str]]:
    """
    Parse a ReGa script and extract header info.

    Returns:
        - declared_name: The name declared in !# name: line (or None)
        - declared_params: Set of parameters declared with !# param:
        - other_lines: All lines except !# name: and !# param: lines

    """
    lines = content.splitlines()
    declared_name: str | None = None
    declared_params: set[str] = set()
    other_lines: list[str] = []

    for line in lines:
        if match := NAME_PATTERN.match(line):
            declared_name = match.group(1).strip()
            # Skip this line - will be regenerated
        elif match := PARAM_DECL_PATTERN.match(line):
            declared_params.add(match.group(1))
            # Skip this line - will be regenerated
        else:
            other_lines.append(line)

    return declared_name, declared_params, other_lines


def generate_fixed_content(
    filename: str,
    used_params: set[str],
    other_lines: list[str],
) -> str:
    """Generate fixed script content with proper header."""
    header = [f"!# name: {filename}"]

    # Add param declarations in sorted order for consistency
    header.extend(f'!# param: "##{param}##"' for param in sorted(used_params))

    # Remove leading empty lines from other_lines
    while other_lines and not other_lines[0].strip():
        other_lines.pop(0)

    # Combine header and content
    # Add empty line after header if there's content and it doesn't start with !#
    if other_lines and not other_lines[0].startswith("!#"):
        header.append("")

    return "\n".join(header + other_lines) + "\n"


def _check_header_order(content: str, used_params: set[str]) -> bool:
    """Check if !# name: and !# param: lines are at the top in correct order."""
    lines = content.splitlines()
    if not lines:
        return False

    # First line must be !# name:
    if not NAME_PATTERN.match(lines[0]):
        return False

    # Count expected param lines
    expected_param_count = len(used_params)
    if expected_param_count == 0:
        return True

    # Check that param lines follow immediately after name line
    param_lines_found = 0
    for i, line in enumerate(lines[1:], start=1):
        if PARAM_DECL_PATTERN.match(line):
            # Param line must be consecutive (right after name or other param lines)
            if i != param_lines_found + 1:
                return False
            param_lines_found += 1
        elif param_lines_found > 0:
            # We've seen param lines and now hit a non-param line - that's fine
            break

    return param_lines_found == expected_param_count


def check_script(filepath: Path, fix: bool = False) -> list[str]:
    """
    Check a single ReGa script for header compliance.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []
    filename = filepath.name

    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{filepath}: Cannot read file: {e}"]

    # Parse the script
    declared_name, declared_params, other_lines = parse_script(content)

    # Find parameters used in the non-header content
    non_header_content = "\n".join(other_lines)
    used_params = find_used_parameters(non_header_content)

    needs_fix = False

    # Check 1: First line must have correct !# name:
    if declared_name != filename:
        errors.append(f"{filepath}: First line must be '!# name: {filename}', got '{declared_name}'")
        needs_fix = True

    # Check 2: All used parameters must be declared
    missing_params = used_params - declared_params
    if missing_params:
        errors.extend(
            f'{filepath}: Missing parameter declaration: !# param: "##{param}##"' for param in sorted(missing_params)
        )
        needs_fix = True

    # Check 3: No extra parameter declarations
    extra_params = declared_params - used_params
    if extra_params:
        errors.extend(
            f'{filepath}: Unused parameter declaration: !# param: "##{param}##"' for param in sorted(extra_params)
        )
        needs_fix = True

    # Check 4: Header must be at the top (check if content starts with header)
    if content and not content.startswith("!# name:"):
        errors.append(f"{filepath}: Script must start with '!# name:' header")
        needs_fix = True

    # Check 5: !# param: lines must be directly after !# name: line
    if not needs_fix and used_params and not _check_header_order(content, used_params):
        errors.append(f"{filepath}: !# param: lines must be directly after !# name: line")
        needs_fix = True

    # Apply fix if requested
    if fix and needs_fix:
        fixed_content = generate_fixed_content(filename, used_params, other_lines)
        try:
            filepath.write_text(fixed_content, encoding="utf-8")
            print(f"Fixed: {filepath}")
            # Clear errors after successful fix
            errors.clear()
        except OSError as e:
            errors.append(f"{filepath}: Cannot write file: {e}")

    return errors


def main() -> int:
    """Run the linter on ReGa scripts."""
    parser = argparse.ArgumentParser(
        description="Lint ReGa scripts for proper header format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix issues by rewriting files",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files to check (default: all .fn files in aiohomematic/rega_scripts/)",
    )

    args = parser.parse_args()

    # Determine files to check
    if args.files:
        files = [f for f in args.files if f.suffix == ".fn"]
    else:
        rega_dir = Path(__file__).parent.parent / "aiohomematic" / "rega_scripts"
        files = sorted(rega_dir.glob("*.fn"))

    if not files:
        print("No .fn files to check")
        return 0

    all_errors: list[str] = []

    for filepath in files:
        errors = check_script(filepath, fix=args.fix)
        all_errors.extend(errors)

    if all_errors:
        for error in all_errors:
            print(error, file=sys.stderr)
        if not args.fix:
            print(f"\nFound {len(all_errors)} error(s). Run with --fix to auto-fix.", file=sys.stderr)
        return 1

    print(f"Checked {len(files)} file(s): OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
