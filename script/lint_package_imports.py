#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Lint script to enforce package import conventions.

This script validates that public symbols from packages are imported via
the package's __init__.py rather than directly from submodules.

Rules:
1. External consumers (tests, aiohomematic_test_support) must import public
   symbols from packages, not directly from submodules
2. Internal aiohomematic modules may use direct submodule imports
3. __init__.py files are skipped (they are package facades that re-export)
4. Private symbols (_prefix) can always be imported directly from submodules

Usage:
    python script/lint_package_imports.py [paths...]

Exit codes:
    0 - All imports are valid
    1 - Invalid imports found
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterator
from pathlib import Path
import sys
from typing import NamedTuple

# Packages that define __all__ and should enforce import rules
PACKAGES_WITH_PUBLIC_API: tuple[str, ...] = (
    "aiohomematic.model.custom",
    "aiohomematic.model.generic",
    "aiohomematic.model.calculated",
    "aiohomematic.model.hub",
    "aiohomematic.central",
    "aiohomematic.client",
    "aiohomematic.interfaces",
    "aiohomematic.store",
)

# Directories to skip
SKIP_DIRS: frozenset[str] = frozenset({"__pycache__", ".git", "build", "dist", ".venv", "venv"})

# Files to skip (package facades that legitimately import from submodules)
SKIP_FILES: frozenset[str] = frozenset({"__init__.py"})


class ImportViolation(NamedTuple):
    """Represents an import rule violation."""

    file_path: Path
    line_number: int
    symbol: str
    submodule: str
    package: str
    message: str


def is_internal_aiohomematic_import(importing_file: Path, base_path: Path) -> bool:
    """
    Check if the importing file is within aiohomematic itself.

    Internal aiohomematic modules are allowed to use direct submodule imports.
    Only external consumers (tests, aiohomematic_test_support) must use package imports.
    """
    try:
        relative = importing_file.relative_to(base_path)
        parts = relative.parts
        # Check if file is within the aiohomematic package (not tests or aiohomematic_test_support)
        return parts and parts[0] == "aiohomematic"
    except ValueError:
        return False


def load_package_all(package_path: str, base_path: Path) -> set[str]:
    """Load the __all__ from a package's __init__.py."""
    init_path = base_path / package_path.replace(".", "/") / "__init__.py"
    if not init_path.exists():
        return set()

    try:
        with open(init_path, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, ast.List):
                        return {
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        }
    except (SyntaxError, OSError):
        pass
    return set()


def check_file(
    file_path: Path,
    base_path: Path,
    package_exports: dict[str, set[str]],
    *,
    check_internal: bool = False,
) -> list[ImportViolation]:
    """Check a file for import violations."""
    violations: list[ImportViolation] = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)
    except (SyntaxError, OSError):
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module

            # Check each package with public API
            for package in PACKAGES_WITH_PUBLIC_API:
                # Pattern: from <package>.<submodule> import ...
                # where submodule is not empty
                if module.startswith(package + "."):
                    submodule = module[len(package) + 1 :]
                    # Skip if it's the __init__ itself
                    if not submodule or submodule == "__init__":
                        continue

                    # Allow intra-package imports (imports within the same package)
                    # e.g., aiohomematic/interfaces/client.py importing from aiohomematic.interfaces.operations
                    try:
                        relative_file = file_path.relative_to(base_path)
                    except ValueError:
                        # file_path is already relative or not under base_path
                        relative_file = file_path
                    file_package = ".".join(relative_file.parts[:-1])  # e.g., "aiohomematic.interfaces"
                    if file_package.startswith(package) or package.startswith(file_package):
                        # This is an intra-package import, allow it
                        continue

                    # Allow internal aiohomematic imports unless check_internal is True
                    if not check_internal and is_internal_aiohomematic_import(file_path, base_path):
                        continue

                    # Get public exports for this package
                    exports = package_exports.get(package, set())

                    # Check each imported name
                    for alias in node.names:
                        name = alias.name

                        # Skip private symbols (they're intentionally not exported)
                        if name.startswith("_"):
                            continue

                        # If the symbol is in __all__, it should be imported from package
                        if name in exports:
                            violations.append(
                                ImportViolation(
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    symbol=name,
                                    submodule=module,
                                    package=package,
                                    message=(
                                        f"'{name}' is a public API of '{package}'. "
                                        f"Import from '{package}' instead of '{module}'."
                                    ),
                                )
                            )

    return violations


def iter_python_files(paths: list[Path], base_path: Path) -> Iterator[Path]:
    """Iterate over Python files in the given paths."""
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            # Skip __init__.py files (they are package facades)
            if path.name not in SKIP_FILES:
                yield path
        elif path.is_dir():
            for py_file in path.rglob("*.py"):
                # Skip excluded directories
                if any(skip in py_file.parts for skip in SKIP_DIRS):
                    continue
                # Skip __init__.py files (they are package facades)
                if py_file.name in SKIP_FILES:
                    continue
                yield py_file


def main() -> int:
    """Run the import linter."""
    parser = argparse.ArgumentParser(
        description="Lint package imports to enforce public API usage for external consumers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("tests"), Path("aiohomematic_test_support")],
        help="Paths to check (default: tests aiohomematic_test_support)",
    )
    parser.add_argument(
        "--base-path",
        type=Path,
        default=Path.cwd(),
        help="Base path for resolving packages (default: current directory)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="check_all",
        help="Check all files including internal aiohomematic modules",
    )
    args = parser.parse_args()

    base_path = args.base_path.resolve()

    # When --all is used, also include aiohomematic in paths
    paths_to_check = args.paths
    if args.check_all and Path("aiohomematic") not in paths_to_check:
        paths_to_check = [Path("aiohomematic"), *list(paths_to_check)]

    # Load __all__ from all packages
    package_exports: dict[str, set[str]] = {}
    for package in PACKAGES_WITH_PUBLIC_API:
        exports = load_package_all(package, base_path)
        if exports:
            package_exports[package] = exports
            print(f"Loaded {len(exports)} exports from {package}")

    # Check all files
    all_violations: list[ImportViolation] = []
    files_checked = 0

    for py_file in iter_python_files(paths_to_check, base_path):
        violations = check_file(py_file, base_path, package_exports, check_internal=args.check_all)
        all_violations.extend(violations)
        files_checked += 1

    # Report results
    print(f"\nChecked {files_checked} files")

    if all_violations:
        print(f"\nFound {len(all_violations)} import violation(s):\n")
        for v in sorted(all_violations, key=lambda x: (x.file_path, x.line_number)):
            print(f"{v.file_path}:{v.line_number}: {v.message}")
        return 1
    print("All imports are valid!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
