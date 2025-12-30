#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Lint script to validate __all__ exports in package __init__.py files.

This script validates:
1. All non-private imports in __init__.py are listed in __all__
2. All entries in __all__ are actually imported
3. __all__ is grouped with comments (# GroupName)
4. Groups are sorted alphabetically
5. Entries within each group are sorted alphabetically
6. No duplicates in __all__

Expected __all__ format:
    __all__ = [
        # GroupA
        "SymbolA1",
        "SymbolA2",
        # GroupB
        "SymbolB1",
        "SymbolB2",
    ]

Usage:
    python script/lint_all_exports.py [--fix] [packages...]

Exit codes:
    0 - All exports are valid
    1 - Validation errors found
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from typing import NamedTuple

# Packages to validate
PACKAGES_TO_VALIDATE: tuple[str, ...] = (
    "aiohomematic.central",
    "aiohomematic.central.coordinators",
    "aiohomematic.central.events",
    "aiohomematic.client",
    "aiohomematic.interfaces",
    "aiohomematic.metrics",
    "aiohomematic.model",
    "aiohomematic.model.calculated",
    "aiohomematic.model.custom",
    "aiohomematic.model.generic",
    "aiohomematic.model.hub",
    "aiohomematic.store",
    "aiohomematic.store.dynamic",
    "aiohomematic.store.persistent",
    "aiohomematic.store.visibility",
)


class ValidationError(NamedTuple):
    """A validation error."""

    package: str
    message: str
    line: int | None = None


@dataclass
class GroupedAll:
    """Parsed __all__ with groups."""

    groups: dict[str, list[str]] = field(default_factory=dict)
    group_order: list[str] = field(default_factory=list)

    def all_symbols(self) -> set[str]:
        """Return all symbols across all groups."""
        result: set[str] = set()
        for symbols in self.groups.values():
            result.update(symbols)
        return result


def parse_all_with_groups(init_path: Path) -> tuple[GroupedAll | None, int | None]:
    """
    Parse __all__ from an __init__.py file, extracting group comments.

    Returns:
        Tuple of (GroupedAll or None if not found, line number of __all__)

    """
    if not init_path.exists():
        return None, None

    content = init_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Find __all__ assignment
    all_pattern = re.compile(r"^__all__\s*=\s*\[")
    all_start_line: int | None = None

    for i, line in enumerate(lines):
        if all_pattern.match(line):
            all_start_line = i
            break

    if all_start_line is None:
        return None, None

    # Extract the __all__ block (handle multi-line)
    bracket_count = 0
    all_lines: list[str] = []
    in_all = False

    for _i, line in enumerate(lines[all_start_line:], start=all_start_line):
        if not in_all:
            if "[" in line:
                in_all = True
                bracket_count += line.count("[") - line.count("]")
                all_lines.append(line)
        else:
            bracket_count += line.count("[") - line.count("]")
            all_lines.append(line)
            if bracket_count <= 0:
                break

    # Parse the block
    result = GroupedAll()
    current_group = "_ungrouped"
    result.groups[current_group] = []
    result.group_order.append(current_group)

    # Pattern for group comment: # GroupName
    group_pattern = re.compile(r"^\s*#\s*(\w[\w\s]*\w|\w)\s*$")
    # Pattern for symbol: "SymbolName" or 'SymbolName'
    symbol_pattern = re.compile(r'["\'](\w+)["\']')

    for line in all_lines:
        # Check for group comment
        group_match = group_pattern.match(line)
        if group_match:
            current_group = group_match.group(1).strip()
            if current_group not in result.groups:
                result.groups[current_group] = []
                result.group_order.append(current_group)
            continue

        # Check for symbols
        for match in symbol_pattern.finditer(line):
            symbol = match.group(1)
            result.groups[current_group].append(symbol)

    # Remove empty _ungrouped if it exists and is empty
    if "_ungrouped" in result.groups and not result.groups["_ungrouped"]:
        del result.groups["_ungrouped"]
        result.group_order.remove("_ungrouped")

    return result, all_start_line + 1  # 1-indexed line number


# Standard library and typing modules that should NOT be exported
STDLIB_MODULES: frozenset[str] = frozenset(
    {
        "__future__",
        "abc",
        "asyncio",
        "collections",
        "collections.abc",
        "contextlib",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "hashlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "re",
        "sys",
        "time",
        "typing",
        "types",
        "uuid",
        "weakref",
    }
)

# Typing symbols that should NOT be exported
TYPING_SYMBOLS: frozenset[str] = frozenset(
    {
        "annotations",
        "Any",
        "Callable",
        "ClassVar",
        "Collection",
        "Final",
        "Generic",
        "Iterator",
        "Literal",
        "Mapping",
        "NamedTuple",
        "Optional",
        "Protocol",
        "Sequence",
        "Set",
        "TYPE_CHECKING",
        "TypeAlias",
        "TypedDict",
        "TypeVar",
        "Union",
        "cast",
        "overload",
        "runtime_checkable",
    }
)


def get_exported_symbols(init_path: Path) -> set[str]:
    """
    Get all non-private symbols that should be exported from an __init__.py file.

    Includes:
    - Symbols imported from aiohomematic submodules (re-exports)
    - Classes and functions defined locally in __init__.py
    - Module-level assignments (constants, type aliases)

    Excludes:
    - Standard library imports
    - Typing-related imports
    - Private symbols (starting with _)
    """
    if not init_path.exists():
        return set()

    try:
        content = init_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except (SyntaxError, OSError):
        return set()

    symbols: set[str] = set()

    for node in ast.walk(tree):
        # Handle imports from aiohomematic submodules
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""

            # Skip stdlib and typing imports
            if module in STDLIB_MODULES or module.split(".")[0] in STDLIB_MODULES:
                continue

            # Only include aiohomematic imports (re-exports)
            if not module.startswith("aiohomematic"):
                continue

            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                # Skip private symbols and typing symbols
                if not name.startswith("_") and name not in TYPING_SYMBOLS:
                    symbols.add(name)

        # Handle locally defined classes and functions
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                symbols.add(node.name)

    return symbols


def validate_package(package: str, base_path: Path) -> list[ValidationError]:
    """Validate a single package's __all__ exports."""
    errors: list[ValidationError] = []
    init_path = base_path / package.replace(".", "/") / "__init__.py"

    if not init_path.exists():
        errors.append(ValidationError(package, f"__init__.py not found: {init_path}"))
        return errors

    # Parse __all__
    grouped_all, all_line = parse_all_with_groups(init_path)
    if grouped_all is None:
        errors.append(ValidationError(package, "__all__ not defined"))
        return errors

    # Get exportable symbols (imports + local definitions)
    exportable = get_exported_symbols(init_path)
    exported = grouped_all.all_symbols()

    # Check 1: All __all__ entries should be either imported or locally defined
    extra_exports = exported - exportable
    errors.extend(
        ValidationError(
            package,
            f"'{symbol}' is in __all__ but not imported or defined locally",
            all_line,
        )
        for symbol in sorted(extra_exports)
    )

    # Check 3: No ungrouped symbols (all should have a group comment)
    if "_ungrouped" in grouped_all.groups and grouped_all.groups["_ungrouped"]:
        ungrouped = grouped_all.groups["_ungrouped"]
        errors.append(
            ValidationError(
                package,
                f"Symbols without group comment: {', '.join(sorted(ungrouped))}",
                all_line,
            )
        )

    # Check 4: Groups should be sorted alphabetically
    groups_without_ungrouped = [g for g in grouped_all.group_order if g != "_ungrouped"]
    sorted_groups = sorted(groups_without_ungrouped)
    if groups_without_ungrouped != sorted_groups:
        errors.append(
            ValidationError(
                package,
                f"Groups not sorted. Expected: {sorted_groups}, got: {groups_without_ungrouped}",
                all_line,
            )
        )

    # Check 5: Symbols within each group should be sorted
    for group_name, symbols in grouped_all.groups.items():
        if group_name == "_ungrouped":
            continue
        sorted_symbols = sorted(symbols)
        if symbols != sorted_symbols:
            errors.append(
                ValidationError(
                    package,
                    f"Symbols in group '{group_name}' not sorted. Expected: {sorted_symbols}",
                    all_line,
                )
            )

    # Check 6: No duplicates
    all_symbols_list: list[str] = []
    for symbols in grouped_all.groups.values():
        all_symbols_list.extend(symbols)
    seen: set[str] = set()
    duplicates: set[str] = set()
    for symbol in all_symbols_list:
        if symbol in seen:
            duplicates.add(symbol)
        seen.add(symbol)
    if duplicates:
        errors.append(
            ValidationError(
                package,
                f"Duplicate entries in __all__: {', '.join(sorted(duplicates))}",
                all_line,
            )
        )

    return errors


def generate_fixed_all(
    package: str,
    base_path: Path,
    group_assignments: dict[str, str] | None = None,
) -> str | None:
    """
    Generate a fixed __all__ declaration.

    Args:
        package: Package path (e.g., "aiohomematic.central")
        base_path: Base path for the project
        group_assignments: Optional dict mapping symbol -> group name

    Returns:
        Fixed __all__ string or None if unable to generate

    """
    init_path = base_path / package.replace(".", "/") / "__init__.py"
    if not init_path.exists():
        return None

    exportable = get_exported_symbols(init_path)
    if not exportable:
        return None

    # Default group assignments if not provided
    if group_assignments is None:
        group_assignments = dict.fromkeys(exportable, "General")

    # Group symbols
    groups: dict[str, list[str]] = {}
    for symbol in exportable:
        group = group_assignments.get(symbol, "General")
        if group not in groups:
            groups[group] = []
        groups[group].append(symbol)

    # Sort groups and symbols within groups
    sorted_groups = sorted(groups.keys())

    # Generate __all__
    lines = ["__all__ = ["]
    for group in sorted_groups:
        symbols = sorted(groups[group])
        lines.append(f"    # {group}")
        lines.extend(f'    "{symbol}",' for symbol in symbols)
    lines.append("]")

    return "\n".join(lines)


def main() -> int:
    """Run the __all__ export linter."""
    parser = argparse.ArgumentParser(
        description="Validate __all__ exports in package __init__.py files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "packages",
        nargs="*",
        default=list(PACKAGES_TO_VALIDATE),
        help=f"Packages to validate (default: {', '.join(PACKAGES_TO_VALIDATE[:3])}...)",
    )
    parser.add_argument(
        "--base-path",
        type=Path,
        default=Path.cwd(),
        help="Base path for resolving packages (default: current directory)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Show suggested fixes (does not modify files)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output",
    )
    args = parser.parse_args()

    base_path = args.base_path.resolve()
    all_errors: list[ValidationError] = []

    for package in args.packages:
        if args.verbose:
            print(f"Checking {package}...")
        errors = validate_package(package, base_path)
        all_errors.extend(errors)

        if args.fix and errors:
            print(f"\n--- Suggested __all__ for {package} ---")
            fixed = generate_fixed_all(package, base_path)
            if fixed:
                print(fixed)
            print()

    # Report results
    if all_errors:
        print(f"\nFound {len(all_errors)} error(s):\n")
        for error in sorted(all_errors, key=lambda e: (e.package, e.line or 0)):
            loc = f":{error.line}" if error.line else ""
            print(f"  {error.package}{loc}: {error.message}")
        return 1

    print(f"Validated {len(args.packages)} packages - all exports are valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
