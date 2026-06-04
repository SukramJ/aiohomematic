# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract: the domain model and event-type layers stay backend-agnostic.

``aiohomematic.model`` and ``aiohomematic.event_types`` must not import
``aiohomematic.client`` or ``aiohomematic.central`` at runtime, so an
alternative (daemon-backed) backend can reuse the categorized data-point model
without pulling in the RPC layers. TYPE_CHECKING-only imports are allowed.

This mirrors the ``script/lint_package_imports.py`` contract boundary as a
test-suite guardrail. See ``docs/drop-in-optimizations.md``.
"""

import ast
from pathlib import Path

import pytest

import aiohomematic

_PACKAGE_ROOT = Path(aiohomematic.__file__).parent
_GUARDED_PACKAGES = ("model", "event_types")
_FORBIDDEN_PREFIXES = ("aiohomematic.client", "aiohomematic.central")


def _guarded_files() -> list[Path]:
    """Return every Python module under the guarded packages."""
    files: list[Path] = []
    for package in _GUARDED_PACKAGES:
        files.extend(sorted((_PACKAGE_ROOT / package).rglob("*.py")))
    return files


def _type_checking_line_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """Return (start, end) line ranges of ``if TYPE_CHECKING:`` bodies."""
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            )
            if is_tc and node.body:
                ranges.append((node.body[0].lineno, node.body[-1].end_lineno or node.body[-1].lineno))
    return ranges


def _runtime_forbidden_imports(path: Path) -> list[str]:
    """Return forbidden runtime imports (module:line) found in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tc_ranges = _type_checking_line_ranges(tree)

    def in_type_checking(lineno: int) -> bool:
        return any(start <= lineno <= end for start, end in tc_ranges)

    found: list[str] = []
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        else:
            continue
        if in_type_checking(node.lineno):
            continue
        found.extend(
            f"{module}:{node.lineno}"
            for module in modules
            if any(module == p or module.startswith(p + ".") for p in _FORBIDDEN_PREFIXES)
        )
    return found


@pytest.mark.parametrize("path", _guarded_files(), ids=lambda p: str(p.relative_to(_PACKAGE_ROOT)))
def test_model_layer_is_client_central_free(path: Path) -> None:
    """Verify a guarded module imports no client/central package at runtime."""
    violations = _runtime_forbidden_imports(path)
    assert not violations, (
        f"{path.relative_to(_PACKAGE_ROOT)} must stay client/central-free at runtime "
        f"(TYPE_CHECKING imports are allowed); found: {violations}"
    )


def test_guarded_packages_are_non_empty() -> None:
    """Guard against the discovery silently matching nothing."""
    assert len(_guarded_files()) > 50
