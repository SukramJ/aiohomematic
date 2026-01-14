#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Auto-fix prek helper to reorder Python class members.

Order according to the requested convention:

1. Special methods (dunder):
   - __init__ first
   - other dunder methods next (e.g., __str__, __repr__, ...)
2. Class methods (@classmethod)
3. Static methods (@staticmethod)
4. DelegatedProperty assignments (sorted alphabetically)
5. Properties
   - Getter decorators define cross-property sort order: property, config_property, state_property, info_property, hm_property.
   - For each property, place its Setter (@<name>.setter) and Deleter (@<name>.deleter) immediately after its Getter.
6. Public methods (no leading underscore)
7. Protected methods (single leading underscore)
8. Private methods (double leading underscore, but not dunder)
9. _GenericProperty assignments (sorted last - they reference methods by name)

Additional rules implemented:
- Alphabetical sorting within groups (by function name).
- Async methods are handled the same as sync methods (normal alphabetical within their group).
- DelegatedProperty class attributes are detected and sorted alphabetically.
- Rewriting preserves original source text for members (including decorators and comments
  attached immediately above them) by using AST line spans to slice and reassemble.

Limitations:
- If non-sortable statements are interleaved between methods/properties, we keep only the
  contiguous block between the first and last sortable member and reorder within that block.
  Non-sortable statements inside this span will remain where they are, which may lead to
  less-than-perfect placement in rare cases.

Usage:
  python script/sort_class_members.py [FILES...]

Exit codes:
  0: no changes were necessary
  1: files were modified (so prek records changes)
  2: error occurred.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import sys


@dataclass
class MethodSeg:
    """A sliced method block from a class body used for reordering."""

    name: str
    start: int  # 1-based inclusive
    end: int  # 1-based inclusive
    text: str
    group: str  # ordering group key
    subgroup: str  # for properties: getter/setter/deleter
    # property base name if applicable
    propname: str | None = None
    # for getter: the decorator base that defines the property kind (e.g., "property", "config_property", ...)
    prop_kind: str | None = None


DUUNDER = "dunder"
DUUNDER_INIT = "dunder_init"
CLASSMETHOD = "classmethod"
STATICMETHOD = "staticmethod"
DELEGATED_PROPERTY = "delegated_property"
PROPERTY = "property"
PUBLIC = "public"
PROTECTED = "protected"
PRIVATE = "private"
GENERIC_PROPERTY = "generic_property"  # Sorted last - references methods by name


def read_file(path: Path) -> str:
    """Read and return the text content of a file using UTF-8 encoding."""
    with path.open("r", encoding="utf-8") as f:
        return f.read()


def write_file(path: Path, content: str) -> None:
    """Write text content to a file using UTF-8 encoding without altering newlines."""
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(content)


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_private(name: str) -> bool:
    return name.startswith("__") and not _is_dunder(name)


def _is_protected(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


def _decorator_name(dec: ast.expr) -> tuple[str | None, str | None]:
    """
    Return (base, attr) of decorator.

    Examples:
      @property -> ("property", None)
      @classmethod -> ("classmethod", None)
      @name.setter -> ("name", "setter")
      @config_property -> ("config_property", None)
      @info_property(log_context=True) -> ("info_property", None)

    The first value is either the decorator name (for Name/Call) or the left-hand
    base of an attribute decorator (e.g. for @name.setter the base is "name").
    The second value is the attribute part for attribute decorators, such as
    "setter" or "deleter".

    """
    # Unwrap calls like @decorator(...)
    if isinstance(dec, ast.Call):
        func = dec.func
        if isinstance(func, ast.Name):
            return func.id, None
        if isinstance(func, ast.Attribute):
            base = None
            if isinstance(func.value, ast.Name):
                base = func.value.id
            return base, func.attr
        return None, None
    if isinstance(dec, ast.Name):
        return dec.id, None
    if isinstance(dec, ast.Attribute):
        # Drill down left-most Name for simple cases
        base = None
        if isinstance(dec.value, ast.Name):
            base = dec.value.id
        return base, dec.attr
    return None, None


def _is_property_assignment(node: ast.AST) -> tuple[str | None, str | None]:
    """
    Check if a node is a property-like assignment (DelegatedProperty or _GenericProperty).

    Returns (property_name, property_type) if it is, (None, None) otherwise.
    property_type is "DelegatedProperty" or "_GenericProperty".

    Detects patterns like:
        name = DelegatedProperty[Type](path="path")
        name: Final = DelegatedProperty[Type](path="path")
        name: _GenericProperty[T, S] = _GenericProperty(fget=..., fset=...)

    """
    # Handle both ast.Assign and ast.AnnAssign (annotated assignment with Final)
    if isinstance(node, ast.Assign):
        # Must have exactly one target that is a simple name
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            return None, None
        target_name = node.targets[0].id
        value = node.value
    elif isinstance(node, ast.AnnAssign):
        # Annotated assignment: name: Final = DelegatedProperty[...]()
        if not isinstance(node.target, ast.Name) or node.value is None:
            return None, None
        target_name = node.target.id
        value = node.value
    else:
        return None, None

    # Value must be a Call
    if not isinstance(value, ast.Call):
        return None, None

    func = value.func

    # Check for DelegatedProperty[...](...)
    if isinstance(func, ast.Subscript) and isinstance(func.value, ast.Name) and func.value.id == "DelegatedProperty":
        return target_name, "DelegatedProperty"

    # Check for _GenericProperty(...) - may or may not have type subscript
    if isinstance(func, ast.Name) and func.id == "_GenericProperty":
        return target_name, "_GenericProperty"
    if isinstance(func, ast.Subscript) and isinstance(func.value, ast.Name) and func.value.id == "_GenericProperty":
        return target_name, "_GenericProperty"

    return None, None


def _is_delegated_property(node: ast.AST) -> str | None:
    """Check if a node is a DelegatedProperty assignment. Returns property name or None."""
    name, prop_type = _is_property_assignment(node)
    return name if prop_type == "DelegatedProperty" else None


def _is_generic_property(node: ast.AST) -> str | None:
    """Check if a node is a _GenericProperty assignment. Returns property name or None."""
    name, prop_type = _is_property_assignment(node)
    return name if prop_type == "_GenericProperty" else None


def _member_span(node: ast.AST) -> tuple[int, int]:
    """Return the line span (start, end) for a class member node."""
    assert hasattr(node, "lineno") and hasattr(node, "end_lineno")
    start = node.lineno
    # include decorators if present (for functions)
    decos = getattr(node, "decorator_list", []) or []
    if decos:
        start = min(getattr(d, "lineno", start) for d in decos)
    end = getattr(node, "end_lineno", start)
    return start, end


def _method_span(node: ast.AST) -> tuple[int, int]:
    assert hasattr(node, "lineno") and hasattr(node, "end_lineno")
    start = node.lineno
    # include decorators if present
    decos = getattr(node, "decorator_list", []) or []
    if decos:
        start = min(getattr(d, "lineno", start) for d in decos)
    end = getattr(node, "end_lineno", start)
    return start, end


def _collect_members(src_lines: list[str], cls: ast.ClassDef) -> list[MethodSeg]:
    """Collect sortable class members (methods, DelegatedProperty and _GenericProperty assignments)."""
    members: list[MethodSeg] = []
    for node in cls.body:
        # Check for DelegatedProperty assignment first
        dp_name = _is_delegated_property(node)
        if dp_name is not None:
            start, end = _member_span(node)
            text = "".join(src_lines[start - 1 : end])
            members.append(
                MethodSeg(
                    name=dp_name,
                    start=start,
                    end=end,
                    text=text,
                    group=DELEGATED_PROPERTY,
                    subgroup="",
                    propname=None,
                    prop_kind=None,
                )
            )
            continue

        # Check for _GenericProperty assignment (sorted last - references methods by name)
        gp_name = _is_generic_property(node)
        if gp_name is not None:
            start, end = _member_span(node)
            text = "".join(src_lines[start - 1 : end])
            members.append(
                MethodSeg(
                    name=gp_name,
                    start=start,
                    end=end,
                    text=text,
                    group=GENERIC_PROPERTY,
                    subgroup="",
                    propname=None,
                    prop_kind=None,
                )
            )
            continue

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start, end = _method_span(node)
            # Extract exact text
            text = "".join(src_lines[start - 1 : end])
            name = node.name
            # Classify by decorators
            decos = getattr(node, "decorator_list", []) or []
            deco_pairs = [_decorator_name(d) for d in decos]
            # Property detection
            propname: str | None = None
            subgroup = ""
            group = ""
            prop_kind: str | None = None
            getter_names = {"property", "config_property", "state_property", "info_property", "hm_property"}
            # Determine if this is a property getter and capture its kind (decorator base)
            getter_base: str | None = None
            for base, attr in deco_pairs:
                if base and attr is None and (base in getter_names or base.endswith("_property")):
                    getter_base = base
                    break
            if getter_base is not None:
                group = PROPERTY
                subgroup = "getter"
                # getter function name is the property name
                propname = name
                prop_kind = getter_base
            else:
                # setter/deleter like @name.setter
                for base, attr in deco_pairs:
                    if base and attr in {"setter", "deleter"}:
                        group = PROPERTY
                        propname = base
                        subgroup = attr  # 'setter' or 'deleter'
                        break

            if not group:
                if any(base == "classmethod" for base, _ in deco_pairs):
                    group = CLASSMETHOD
                elif any(base == "staticmethod" for base, _ in deco_pairs):
                    group = STATICMETHOD
                elif name == "__init__":
                    group = DUUNDER_INIT
                elif _is_dunder(name):
                    group = DUUNDER
                elif name.startswith("_"):
                    if _is_private(name):
                        group = PRIVATE
                    elif _is_protected(name):
                        group = PROTECTED
                    else:
                        group = PUBLIC  # Fallback
                else:
                    group = PUBLIC

            members.append(
                MethodSeg(
                    name=name,
                    start=start,
                    end=end,
                    text=text,
                    group=group,
                    subgroup=subgroup,
                    propname=propname,
                    prop_kind=prop_kind,
                )
            )
    return members


def _collect_methods(src_lines: list[str], cls: ast.ClassDef) -> list[MethodSeg]:
    """Collect sortable class members (methods and DelegatedProperty assignments)."""
    return _collect_members(src_lines, cls)


def _reorder_methods(methods: list[MethodSeg]) -> list[MethodSeg]:
    if not methods:
        return methods

    # Group properties by property name
    props: dict[str, list[MethodSeg]] = {}
    for m in methods:
        if m.group == PROPERTY and m.propname:
            props.setdefault(m.propname, []).append(m)

    # Build ordered list for non-property groups
    dunder_init = [m for m in methods if m.group == DUUNDER_INIT]
    dunder_other = [m for m in methods if m.group == DUUNDER]
    classmethods = [m for m in methods if m.group == CLASSMETHOD]
    staticmethods = [m for m in methods if m.group == STATICMETHOD]
    delegated_props = [m for m in methods if m.group == DELEGATED_PROPERTY]

    # Properties assembled with priority by getter decorator kind and adjacency of setter/deleter
    PRIORITY = ["property", "config_property", "state_property", "info_property", "hm_property"]
    PRIORITY_INDEX = {k: i for i, k in enumerate(PRIORITY)}

    prop_groups: list[tuple[int, str, list[MethodSeg]]] = []
    for pname, grp in props.items():
        getters = [m for m in grp if m.subgroup == "getter"]
        setters = [m for m in grp if m.subgroup == "setter"]
        deleters = [m for m in grp if m.subgroup == "deleter"]
        # Determine the kind from the primary getter (if multiple, choose first by name for stability)
        primary_getter = sorted(getters, key=lambda m: m.name)[0] if getters else None
        kind = primary_getter.prop_kind if primary_getter else None
        prio = PRIORITY_INDEX.get(kind or "", len(PRIORITY))
        # Strict order within a property group: getter(s) -> setter(s) -> deleter(s)
        ordered_group: list[MethodSeg] = []
        ordered_group += sorted(getters, key=lambda m: m.name)
        ordered_group += sorted(setters, key=lambda m: m.name)
        ordered_group += sorted(deleters, key=lambda m: m.name)
        prop_groups.append((prio, pname, ordered_group))

    # Sort property groups by (priority, property name)
    prop_groups.sort(key=lambda t: (t[0], t[1]))

    # Add any stray property methods that didn't get a propname (edge cases)
    stray_props = [m for m in methods if m.group == PROPERTY and not m.propname]

    public = [m for m in methods if m.group == PUBLIC]
    protected = [m for m in methods if m.group == PROTECTED]
    private = [m for m in methods if m.group == PRIVATE]
    generic_props = [m for m in methods if m.group == GENERIC_PROPERTY]

    def alpha(ms: list[MethodSeg]) -> list[MethodSeg]:
        return sorted(ms, key=lambda m: m.name)

    ordered: list[MethodSeg] = []
    ordered += alpha(dunder_init)
    ordered += alpha(dunder_other)
    ordered += alpha(classmethods)
    ordered += alpha(staticmethods)
    ordered += alpha(delegated_props)
    for _prio, _pname, grp in prop_groups:
        ordered += grp
    ordered += alpha(stray_props)
    ordered += alpha(public)
    ordered += alpha(protected)
    ordered += alpha(private)
    # _GenericProperty assignments go last - they reference methods by name
    ordered += alpha(generic_props)

    return ordered


def _rewrite_class(src_lines: list[str], cls: ast.ClassDef) -> tuple[bool, list[str]]:
    methods = _collect_methods(src_lines, cls)
    if not methods:
        return False, src_lines

    # Determine span that covers all methods in class body
    span_start = min(m.start for m in methods)
    span_end = max(m.end for m in methods)

    # Safety: if there are non-sortable statements between sortable members, skip this class
    for node in cls.body:
        # Skip sortable members (functions, DelegatedProperty and _GenericProperty assignments)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_delegated_property(node) is not None:
            continue
        if _is_generic_property(node) is not None:
            continue

        n_start = getattr(node, "lineno", None)
        n_end = getattr(node, "end_lineno", None)
        if n_start is None or n_end is None:
            continue
        # If this node lies within the sortable members span, then it's interleaved
        if span_start <= n_start <= span_end or span_start <= n_end <= span_end:
            return False, src_lines

    # Desired new order
    ordered = _reorder_methods(methods)

    # If the order is already correct, do nothing to preserve formatting
    current_order_keys = [(m.group, m.propname, m.subgroup, m.name) for m in sorted(methods, key=lambda x: x.start)]
    desired_order_keys = [(m.group, m.propname, m.subgroup, m.name) for m in ordered]
    if current_order_keys == desired_order_keys:
        return False, src_lines

    # Build the replacement text while keeping blocks largely intact.
    # DelegatedProperty definitions should not have blank lines between them.
    result_parts: list[str] = []
    prev_group: str | None = None
    for m in ordered:
        block = m.text.rstrip("\n")

        # Add blank line separator unless both current and previous are DelegatedProperty
        if result_parts:
            if prev_group == DELEGATED_PROPERTY and m.group == DELEGATED_PROPERTY:
                result_parts.append("\n")  # Single newline, no blank line
            else:
                result_parts.append("\n\n")  # Blank line between other members

        result_parts.append(block)
        prev_group = m.group

    replacement = "".join(result_parts) + "\n"

    new_lines = [*src_lines[: span_start - 1], replacement, *src_lines[span_end:]]
    return True, new_lines


def process_file(path: Path) -> bool:
    """
    Process a single Python file and rewrite class method order if needed.

    Returns True if the file was modified, otherwise False.
    """
    src = read_file(path)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # Skip files with syntax errors
        return False
    src_lines = src.splitlines(keepends=True)

    modified = False

    # Walk top-level to find classes
    class_nodes: list[ast.ClassDef] = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    # Sort classes by starting line descending so line offsets remain valid while replacing
    class_nodes.sort(key=lambda n: n.lineno, reverse=True)

    for cls in class_nodes:
        changed, src_lines = _rewrite_class(src_lines, cls)
        modified = modified or changed

    if modified:
        write_file(path, "".join(src_lines))
    return modified


def iter_paths(paths: Iterable[str]) -> Iterable[Path]:
    """Iterate recursively over Python file paths under the given paths."""
    for p in paths:
        path = Path(p)
        if path.is_dir():
            yield from (q for q in path.rglob("*.py"))
        elif path.is_file() and path.suffix == ".py":
            yield path


def main(argv: list[str]) -> int:
    """
    CLI entry point.

    Returns 1 if any file was modified, 0 if no changes were necessary,
    and 2 if an error occurred.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args(argv)

    any_modified = False
    for path in iter_paths(args.paths):
        try:
            if process_file(path):
                any_modified = True
        except Exception as ex:  # pylint: disable=broad-except
            print(f"error processing {path}: {ex}", file=sys.stderr)
            return 2
    return 1 if any_modified else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
