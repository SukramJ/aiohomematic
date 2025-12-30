#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Analyze which exports from aiohomematic packages are actually used.

This script scans:
1. Cross-package usage within aiohomematic
2. Usage in homematicip_local

Output shows which symbols are:
- Used externally (should be exported)
- Only used internally (should NOT be exported)
- Not used at all (can be removed from exports)

Usage:
    python script/analyze_exports_usage.py
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys

# Packages to analyze
PACKAGES: tuple[str, ...] = (
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


@dataclass
class SymbolUsage:
    """Track usage of a symbol."""

    symbol: str
    package: str
    used_in_aiohomematic: set[str] = field(default_factory=set)  # files that use it
    used_in_homematicip_local: set[str] = field(default_factory=set)
    used_in_other: set[str] = field(default_factory=set)

    @property
    def is_used_externally(self) -> bool:
        """Check if symbol is used outside its own package."""
        return bool(self.used_in_homematicip_local or self.used_in_other)

    @property
    def is_used_cross_package(self) -> bool:
        """Check if symbol is used by other aiohomematic packages."""
        # Check if any usage is from outside the symbol's package
        for file_path in self.used_in_aiohomematic:
            # Convert file path to package
            parts = Path(file_path).parts
            if "aiohomematic" in parts:
                idx = parts.index("aiohomematic")
                file_package = ".".join(parts[idx:-1])  # e.g., "aiohomematic.client"
                # If file is not in the same package tree, it's cross-package
                if not file_package.startswith(self.package) and not self.package.startswith(file_package):
                    return True
        return False


def get_package_exports(package: str, base_path: Path) -> set[str]:
    """Get all symbols exported in __all__ from a package."""
    init_path = base_path / package.replace(".", "/") / "__init__.py"
    if not init_path.exists():
        return set()

    content = init_path.read_text(encoding="utf-8")

    # Find __all__ list
    all_pattern = re.compile(r"__all__\s*=\s*\[(.*?)\]", re.DOTALL)
    match = all_pattern.search(content)
    if not match:
        return set()

    # Extract symbols
    symbols_text = match.group(1)
    symbol_pattern = re.compile(r'["\'](\w+)["\']')
    return set(symbol_pattern.findall(symbols_text))


def find_imports_in_file(file_path: Path) -> dict[str, set[str]]:
    """
    Find all imports from aiohomematic packages in a file.

    Returns dict mapping package -> set of imported symbols.
    """
    result: dict[str, set[str]] = defaultdict(set)

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except (SyntaxError, OSError, UnicodeDecodeError):
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module

            # Check if it's an aiohomematic import
            if not module.startswith("aiohomematic"):
                continue

            # Find which package this import is from
            for package in sorted(PACKAGES, key=len, reverse=True):
                if module == package or module.startswith(package + "."):
                    for alias in node.names:
                        name = alias.name
                        if not name.startswith("_"):
                            result[package].add(name)
                    break

    return result


def scan_directory(
    directory: Path,
    *,
    exclude_dirs: set[str] | None = None,
) -> dict[str, dict[str, set[str]]]:
    """
    Scan a directory for aiohomematic imports.

    Returns dict mapping file_path -> (package -> symbols).
    """
    if exclude_dirs is None:
        exclude_dirs = {"__pycache__", ".git", "venv", ".venv", "build", "dist"}

    result: dict[str, dict[str, set[str]]] = {}

    for py_file in directory.rglob("*.py"):
        # Skip excluded directories
        if any(excl in py_file.parts for excl in exclude_dirs):
            continue

        imports = find_imports_in_file(py_file)
        if imports:
            result[str(py_file)] = imports

    return result


def analyze_usage(
    aiohomematic_path: Path,
    homematicip_local_path: Path | None = None,
) -> dict[str, dict[str, SymbolUsage]]:
    """
    Analyze usage of all exported symbols.

    Returns dict mapping package -> (symbol -> SymbolUsage).
    """
    # Initialize with all exported symbols
    usage: dict[str, dict[str, SymbolUsage]] = {}
    for package in PACKAGES:
        exports = get_package_exports(package, aiohomematic_path)
        usage[package] = {symbol: SymbolUsage(symbol=symbol, package=package) for symbol in exports}

    # Scan aiohomematic
    print("Scanning aiohomematic...")
    aiohomematic_imports = scan_directory(aiohomematic_path / "aiohomematic")
    for file_path, imports in aiohomematic_imports.items():
        for package, symbols in imports.items():
            if package in usage:
                for symbol in symbols:
                    if symbol in usage[package]:
                        usage[package][symbol].used_in_aiohomematic.add(file_path)

    # Scan homematicip_local if available
    if homematicip_local_path and homematicip_local_path.exists():
        print("Scanning homematicip_local...")
        hm_local_imports = scan_directory(homematicip_local_path)
        for file_path, imports in hm_local_imports.items():
            for package, symbols in imports.items():
                if package in usage:
                    for symbol in symbols:
                        if symbol in usage[package]:
                            usage[package][symbol].used_in_homematicip_local.add(file_path)

    return usage


def print_report(usage: dict[str, dict[str, SymbolUsage]]) -> None:
    """Print a usage report."""
    print("\n" + "=" * 80)
    print("EXPORT USAGE ANALYSIS")
    print("=" * 80)

    for package in sorted(usage.keys()):
        symbols = usage[package]
        if not symbols:
            continue

        # Categorize symbols
        used_external: list[str] = []
        used_cross_package: list[str] = []
        used_internal_only: list[str] = []
        unused: list[str] = []

        for symbol, sym_usage in sorted(symbols.items()):
            if sym_usage.is_used_externally:
                used_external.append(symbol)
            elif sym_usage.is_used_cross_package:
                used_cross_package.append(symbol)
            elif sym_usage.used_in_aiohomematic:
                used_internal_only.append(symbol)
            else:
                unused.append(symbol)

        print(f"\n{package}")
        print("-" * len(package))
        print(f"  Total exports: {len(symbols)}")
        print(f"  Used by homematicip_local: {len(used_external)}")
        print(f"  Used cross-package: {len(used_cross_package)}")
        print(f"  Used internally only: {len(used_internal_only)}")
        print(f"  Unused: {len(unused)}")

        if used_external:
            print(f"\n  [KEEP - External] {', '.join(sorted(used_external))}")
        if used_cross_package:
            print(f"\n  [KEEP - Cross-package] {', '.join(sorted(used_cross_package))}")
        if used_internal_only:
            print(f"\n  [CONSIDER REMOVING] {', '.join(sorted(used_internal_only))}")
        if unused:
            print(f"\n  [REMOVE] {', '.join(sorted(unused))}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_exports = sum(len(s) for s in usage.values())
    total_external = sum(1 for symbols in usage.values() for s in symbols.values() if s.is_used_externally)
    total_cross = sum(
        1
        for symbols in usage.values()
        for s in symbols.values()
        if s.is_used_cross_package and not s.is_used_externally
    )
    total_internal = sum(
        1
        for symbols in usage.values()
        for s in symbols.values()
        if s.used_in_aiohomematic and not s.is_used_externally and not s.is_used_cross_package
    )
    total_unused = sum(
        1
        for symbols in usage.values()
        for s in symbols.values()
        if not s.used_in_aiohomematic and not s.is_used_externally
    )

    print(f"Total exports: {total_exports}")
    print(f"Used externally (homematicip_local): {total_external}")
    print(f"Used cross-package: {total_cross}")
    print(f"Used internally only: {total_internal}")
    print(f"Unused: {total_unused}")
    print(f"\nRecommended to keep: {total_external + total_cross}")
    print(f"Recommended to remove: {total_internal + total_unused}")


def main() -> int:
    """Run the analysis."""
    # Determine paths
    script_path = Path(__file__).resolve()
    aiohomematic_path = script_path.parent.parent
    homematicip_local_path = aiohomematic_path.parent / "homematicip_local"

    print(f"aiohomematic path: {aiohomematic_path}")
    print(f"homematicip_local path: {homematicip_local_path}")
    print(f"homematicip_local exists: {homematicip_local_path.exists()}")

    # Run analysis
    usage = analyze_usage(
        aiohomematic_path,
        homematicip_local_path if homematicip_local_path.exists() else None,
    )

    # Print report
    print_report(usage)

    return 0


if __name__ == "__main__":
    sys.exit(main())
