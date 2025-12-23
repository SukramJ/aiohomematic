#!/usr/bin/env python3
"""
Lint DelegatedProperty usage for potential issues.

Check for common problems with DelegatedProperty that could cause runtime
errors or type checking failures.

Diagnostic codes
----------------
DP001 (error)
    Subclass overrides DelegatedProperty with @property. This causes mypy
    error "Cannot override writeable attribute with read-only property".

DP002 (error)
    Type imported under TYPE_CHECKING is used without string forward reference.
    Use DelegatedProperty["TypeName"] instead of DelegatedProperty[TypeName].

DP003 (warning)
    DelegatedProperty uses cached=True but the class uses __slots__ without
    __weakref__. Caching will fall back to no-cache mode.

DP100 (info)
    Suggestion for @property that could potentially use DelegatedProperty.

Usage
-----
    python script/lint_delegated_property.py [options]

Options
-------
    --verbose, -v     Show warnings in addition to errors
    --suggestions     Show DP100 suggestions for potential conversions
    --summary         Show statistics about DelegatedProperty usage

Exit codes
----------
    0: No errors found
    1: Errors found
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Final

AIOHOMEMATIC_ROOT: Final = Path(__file__).parent.parent / "aiohomematic"


@dataclass
class DelegatedPropertyInfo:
    """Information about a DelegatedProperty definition."""

    class_name: str
    property_name: str
    file_path: Path
    line_no: int
    type_arg: str | None = None
    is_forward_reference: bool = False  # True if type was a string literal
    cached: bool = False
    path: str = ""


@dataclass
class PropertyOverride:
    """Information about a property override."""

    class_name: str
    property_name: str
    file_path: Path
    line_no: int
    is_property_decorator: bool = False


@dataclass
class LintIssue:
    """A linting issue found."""

    file_path: Path
    line_no: int
    severity: str  # "error", "warning"
    code: str
    message: str

    def __str__(self) -> str:
        """Return formatted lint issue string."""
        return f"{self.file_path}:{self.line_no}: {self.severity}[{self.code}]: {self.message}"


@dataclass
class LintResult:
    """Results from linting."""

    issues: list[LintIssue] = field(default_factory=list)
    delegated_properties: list[DelegatedPropertyInfo] = field(default_factory=list)
    property_overrides: list[PropertyOverride] = field(default_factory=list)


class DelegatedPropertyVisitor(ast.NodeVisitor):
    """AST visitor to find DelegatedProperty definitions and @property overrides."""

    def __init__(self, file_path: Path) -> None:
        """Initialize the visitor with the file path."""
        self.file_path = file_path
        self.delegated_properties: list[DelegatedPropertyInfo] = []
        self.property_overrides: list[PropertyOverride] = []
        self.type_checking_imports: set[str] = set()
        self.regular_imports: set[str] = set()
        self.current_class: str | None = None
        self.class_bases: dict[str, list[str]] = {}
        self.class_slots: dict[str, list[str]] = {}
        self.in_type_checking: bool = False

    def visit_If(self, node: ast.If) -> None:
        """Track TYPE_CHECKING blocks."""
        # Check if this is `if TYPE_CHECKING:`
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            self.in_type_checking = True
            self.generic_visit(node)
            self.in_type_checking = False
        else:
            self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track imports."""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            if self.in_type_checking:
                self.type_checking_imports.add(name)
            else:
                self.regular_imports.add(name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Track imports."""
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            if self.in_type_checking:
                self.type_checking_imports.add(name)
            else:
                self.regular_imports.add(name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definitions."""
        old_class = self.current_class
        self.current_class = node.name

        # Track base classes
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Subscript) and isinstance(base.value, ast.Name):
                bases.append(base.value.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)
        self.class_bases[node.name] = bases

        # Track __slots__
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__slots__" and isinstance(item.value, ast.Tuple):
                        self.class_slots[node.name] = [
                            elt.value
                            for elt in item.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        ]

        self.generic_visit(node)
        self.current_class = old_class

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignments to find DelegatedProperty."""
        if self.current_class is None:
            self.generic_visit(node)
            return

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue

            prop_name = target.id

            # Check for DelegatedProperty[Type]("path", ...)
            if not isinstance(node.value, ast.Call):
                continue

            call = node.value
            func = call.func

            # Check for DelegatedProperty[...](...)
            if (
                isinstance(func, ast.Subscript)
                and isinstance(func.value, ast.Name)
                and func.value.id == "DelegatedProperty"
            ):
                type_arg, is_forward_ref = self._get_type_arg(func.slice)
                dp_path = self._get_path_arg(call)
                cached = self._get_cached_arg(call)

                self.delegated_properties.append(
                    DelegatedPropertyInfo(
                        class_name=self.current_class,
                        property_name=prop_name,
                        file_path=self.file_path,
                        line_no=node.lineno,
                        type_arg=type_arg,
                        is_forward_reference=is_forward_ref,
                        cached=cached,
                        path=dp_path,
                    )
                )

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions to find @property decorators."""
        if self.current_class is None:
            self.generic_visit(node)
            return

        # Check for @property decorator
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "property":
                self.property_overrides.append(
                    PropertyOverride(
                        class_name=self.current_class,
                        property_name=node.name,
                        file_path=self.file_path,
                        line_no=node.lineno,
                        is_property_decorator=True,
                    )
                )
                break

        self.generic_visit(node)

    def _get_type_arg(self, slice_node: ast.expr) -> tuple[str | None, bool]:
        """
        Extract type argument from DelegatedProperty[Type].

        Returns:
            Tuple of (type_name, is_forward_reference).

        """
        if isinstance(slice_node, ast.Name):
            return slice_node.id, False  # Not a forward reference
        if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
            return slice_node.value, True  # Forward reference string
        if isinstance(slice_node, ast.Subscript):
            # Handle types like Optional[str] or list[int]
            return ast.unparse(slice_node), False
        if isinstance(slice_node, ast.BinOp):
            # Handle union types like str | None
            return ast.unparse(slice_node), False
        if isinstance(slice_node, ast.Attribute):
            return ast.unparse(slice_node), False
        return None, False

    def _get_path_arg(self, call: ast.Call) -> str:
        """Extract path argument from DelegatedProperty call."""
        # DelegatedProperty uses keyword-only args: path="..."
        for keyword in call.keywords:
            if keyword.arg == "path" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value)
        return ""

    def _get_cached_arg(self, call: ast.Call) -> bool:
        """Check if cached=True is set."""
        for keyword in call.keywords:
            if keyword.arg == "cached" and isinstance(keyword.value, ast.Constant):
                return bool(keyword.value.value)
        return False


def parse_file(file_path: Path) -> DelegatedPropertyVisitor | None:
    """Parse a Python file and return the visitor with collected data."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        visitor: Final = DelegatedPropertyVisitor(file_path)
        visitor.visit(tree)
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return None
    else:
        return visitor


def build_inheritance_map(
    all_visitors: list[DelegatedPropertyVisitor],
) -> dict[str, list[str]]:
    """Build a map of class -> direct subclasses."""
    # First, collect all class bases
    all_bases: dict[str, list[str]] = {}
    for visitor in all_visitors:
        all_bases.update(visitor.class_bases)

    # Build reverse map: base -> subclasses
    subclass_map: dict[str, list[str]] = defaultdict(list)
    for class_name, bases in all_bases.items():
        for base in bases:
            subclass_map[base].append(class_name)

    return dict(subclass_map)


def get_all_subclasses(class_name: str, subclass_map: dict[str, list[str]]) -> set[str]:
    """Get all subclasses (direct and indirect) of a class."""
    result: set[str] = set()
    to_process = [class_name]

    while to_process:
        current = to_process.pop()
        for subclass in subclass_map.get(current, []):
            if subclass not in result:
                result.add(subclass)
                to_process.append(subclass)

    return result


def _class_has_weakref_in_hierarchy(
    class_name: str,
    all_visitors: list[DelegatedPropertyVisitor],
) -> bool:
    """
    Check if a class or any of its parent classes has __weakref__ or __dict__ in slots.

    This is needed because __weakref__ in a parent class's __slots__ enables weak
    references for all subclasses.
    """
    # Build maps for efficient lookup
    class_slots: dict[str, list[str]] = {}
    class_bases: dict[str, list[str]] = {}
    for visitor in all_visitors:
        class_slots.update(visitor.class_slots)
        class_bases.update(visitor.class_bases)

    # Check this class and all parent classes
    visited: set[str] = set()
    to_check = [class_name]

    while to_check:
        current = to_check.pop()
        if current in visited:
            continue
        visited.add(current)

        # Check if this class has __weakref__ or __dict__ in its slots
        if current in class_slots:
            slots = class_slots[current]
            if "__dict__" in slots or "__weakref__" in slots:
                return True

        # Add parent classes to check
        if current in class_bases:
            to_check.extend(class_bases[current])

    return False


def lint_delegated_properties(verbose: bool = False) -> LintResult:
    """Lint all DelegatedProperty usages in the codebase."""
    result = LintResult()

    # Parse all Python files
    all_visitors: list[DelegatedPropertyVisitor] = []
    for py_file in AIOHOMEMATIC_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        visitor = parse_file(py_file)
        if visitor:
            all_visitors.append(visitor)
            result.delegated_properties.extend(visitor.delegated_properties)
            result.property_overrides.extend(visitor.property_overrides)

    # Build inheritance map
    subclass_map = build_inheritance_map(all_visitors)

    # Collect all @property definitions by class
    property_by_class: dict[str, set[str]] = defaultdict(set)
    for override in result.property_overrides:
        property_by_class[override.class_name].add(override.property_name)

    # Check each DelegatedProperty
    for dp in result.delegated_properties:
        # Check 1: Subclass override with @property
        subclasses = get_all_subclasses(dp.class_name, subclass_map)
        for subclass in subclasses:
            if dp.property_name in property_by_class.get(subclass, set()):
                # Find the override info
                for override in result.property_overrides:
                    if override.class_name == subclass and override.property_name == dp.property_name:
                        result.issues.append(
                            LintIssue(
                                file_path=dp.file_path,
                                line_no=dp.line_no,
                                severity="error",
                                code="DP001",
                                message=(
                                    f"DelegatedProperty '{dp.property_name}' in {dp.class_name} "
                                    f"is overridden with @property in subclass {subclass} "
                                    f"({override.file_path}:{override.line_no}). "
                                    f"This causes mypy error 'Cannot override writeable attribute "
                                    f"with read-only property'."
                                ),
                            )
                        )
                        break

        # Check 2: Forward reference without TYPE_CHECKING import
        if dp.type_arg and not dp.is_forward_reference:
            # Type is not a string forward reference
            for visitor in all_visitors:
                if visitor.file_path == dp.file_path:
                    # Check if type is only in TYPE_CHECKING
                    type_name = dp.type_arg.split("[")[0].split("|")[0].strip()
                    if type_name in visitor.type_checking_imports and type_name not in visitor.regular_imports:
                        result.issues.append(
                            LintIssue(
                                file_path=dp.file_path,
                                line_no=dp.line_no,
                                severity="error",
                                code="DP002",
                                message=(
                                    f"Type '{type_name}' in DelegatedProperty[{dp.type_arg}] "
                                    f"is imported under TYPE_CHECKING but not used as string forward reference. "
                                    f'Use DelegatedProperty["{dp.type_arg}"] instead.'
                                ),
                            )
                        )
                    break

        # Check 3: Cached property warning (informational)
        if dp.cached and verbose:
            for visitor in all_visitors:
                if visitor.file_path == dp.file_path:
                    if dp.class_name in visitor.class_slots:
                        # Check if __weakref__ or __dict__ is in this class or any parent class
                        has_weakref = _class_has_weakref_in_hierarchy(dp.class_name, all_visitors)
                        if not has_weakref:
                            result.issues.append(
                                LintIssue(
                                    file_path=dp.file_path,
                                    line_no=dp.line_no,
                                    severity="warning",
                                    code="DP003",
                                    message=(
                                        f"DelegatedProperty '{dp.property_name}' uses cached=True "
                                        f"but class {dp.class_name} uses __slots__ without __weakref__. "
                                        f"Caching will fall back to no-cache mode if weak references fail."
                                    ),
                                )
                            )
                    break

    return result


def check_potential_conversions(verbose: bool = False) -> list[LintIssue]:
    """
    Check for @property methods that could potentially be converted to DelegatedProperty.

    This helps identify opportunities for using DelegatedProperty.
    """
    issues: list[LintIssue] = []

    for py_file in AIOHOMEMATIC_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        class ConversionChecker(ast.NodeVisitor):
            def __init__(self) -> None:
                self.current_class: str | None = None
                self.suggestions: list[tuple[int, str, str, str]] = []

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                if self.current_class is None:
                    return

                # Check for @property decorator
                is_property = False
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "property":
                        is_property = True
                        break
                    if isinstance(decorator, ast.Attribute) and decorator.attr == "getter":
                        is_property = True
                        break

                if not is_property:
                    return

                # Check if body is simple delegation: return self._attr or return self._attr.sub
                if len(node.body) != 1:
                    return

                stmt = node.body[0]
                if not isinstance(stmt, ast.Return) or stmt.value is None:
                    return

                # Check for self._attr pattern
                path = self._extract_delegation_path(stmt.value)
                if path and verbose:
                    self.suggestions.append((node.lineno, self.current_class, node.name, path))

            def _extract_delegation_path(self, node: ast.expr) -> str | None:
                """Extract delegation path like '_config.interface' from an expression."""
                if isinstance(node, ast.Attribute):
                    # Check if it's self._something
                    if isinstance(node.value, ast.Name) and node.value.id == "self":
                        return node.attr
                    # Check for self._something.attr
                    if isinstance(node.value, ast.Attribute):
                        base_path = self._extract_delegation_path(node.value)
                        if base_path:
                            return f"{base_path}.{node.attr}"
                return None

        checker = ConversionChecker()
        checker.visit(tree)

        for line_no, class_name, prop_name, path in checker.suggestions:
            issues.append(
                LintIssue(
                    file_path=py_file,
                    line_no=line_no,
                    severity="info",
                    code="DP100",
                    message=(
                        f"@property '{prop_name}' in {class_name} could potentially use "
                        f'DelegatedProperty["{path}"] if no subclass overrides it.'
                    ),
                )
            )

    return issues


def main() -> int:
    """Run the DelegatedProperty linter and return exit code."""
    parser = argparse.ArgumentParser(description="Lint DelegatedProperty usage for potential issues.")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output including warnings and suggestions",
    )
    parser.add_argument(
        "--suggestions",
        action="store_true",
        help="Show suggestions for properties that could use DelegatedProperty",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show summary statistics",
    )
    args = parser.parse_args()

    # Run linting
    result = lint_delegated_properties(verbose=args.verbose)

    # Filter issues by severity
    errors = [i for i in result.issues if i.severity == "error"]
    warnings = [i for i in result.issues if i.severity == "warning"]

    # Print errors
    for issue in errors:
        print(issue)

    # Print warnings if verbose
    if args.verbose:
        for issue in warnings:
            print(issue)

    # Check for potential conversions
    if args.suggestions:
        suggestions = check_potential_conversions(verbose=True)
        for issue in suggestions:
            print(issue)

    # Print summary
    if args.summary:
        print("\n=== Summary ===")
        print(f"DelegatedProperty definitions: {len(result.delegated_properties)}")
        print(f"@property definitions: {len(result.property_overrides)}")
        print(f"Errors: {len(errors)}")
        print(f"Warnings: {len(warnings)}")

        # Group by class
        by_class: dict[str, int] = defaultdict(int)
        for dp in result.delegated_properties:
            by_class[dp.class_name] += 1

        print("\nTop classes using DelegatedProperty:")
        for class_name, count in sorted(by_class.items(), key=lambda x: -x[1])[:10]:
            print(f"  {class_name}: {count}")

    if errors:
        print(f"\nFound {len(errors)} error(s).", file=sys.stderr)
        return 1

    if not args.summary and not errors and not warnings:
        print("All checks passed!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
