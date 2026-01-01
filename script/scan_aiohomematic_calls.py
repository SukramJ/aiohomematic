#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Scan a directory for calls to aiohomematic methods.

This script analyzes Python files to find method calls on aiohomematic objects,
helping to identify which methods are called from external code.

Usage:
    python script/scan_aiohomematic_calls.py /path/to/scan
    python script/scan_aiohomematic_calls.py ../homematicip_local/custom_components/homematicip_local

Output:
    A sorted list of aiohomematic methods being called, grouped by class.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path
import re
import sys
from typing import NamedTuple


class MethodCall(NamedTuple):
    """Represents a method call found in the code."""

    method_name: str
    class_name: str  # The inferred class name (e.g., "CentralUnit", "Device")
    full_class: str  # Full class with module (e.g., "aiohomematic.central.CentralUnit")
    file_path: str
    line_number: int
    context: str  # The full attribute chain or variable type hint


# Home Assistant specific methods to filter out (false positives)
HOME_ASSISTANT_METHODS = frozenset(
    {
        # Home Assistant Device Registry
        "async_get",
        "async_get_device",
        "async_get_or_create",
        "async_remove_device",
        "async_update_device",
        # Home Assistant Entity Registry
        "async_get_entity_id",
        "async_get_entity",
        # Home Assistant Config Entry
        "async_setup_entry",
        "async_unload_entry",
        "async_remove_entry",
        "async_reload_entry",
        # Home Assistant Triggers/Actions
        "async_attach_trigger",
        "async_call_action_from_config",
        "async_get_actions",
        "async_get_action_capabilities",
        "async_get_triggers",
        "async_get_trigger_capabilities",
        # Home Assistant Diagnostics
        "async_get_config_entry_diagnostics",
        "async_get_device_diagnostics",
        # Home Assistant generic async methods
        "async_setup",
        "async_setup_platform",
        "async_forward_entry_setups",
        "async_forward_entry_setup",
        "async_unload_platforms",
        # Other Home Assistant specific
        "async_step_user",
        "async_step_import",
        "async_step_reauth",
        "async_step_central",
        "async_step_central_error",
        "async_added_to_hass",
        "async_will_remove_from_hass",
        "async_device_update",
        "async_get_last_number_data",
        "async_get_last_sensor_data",
        # Home Assistant properties/attributes (not methods but detected as such)
        "entry_id",
        "runtime_data",
        "native_value",  # Sensor attribute
        "device_info",
        "entity_description",
        "should_poll",
        "translation_key",
        "context",  # ConfigFlow context attribute
        # Home Assistant device registry attributes
        "config_entries",  # DeviceEntry.config_entries
        "device_class",  # DeviceEntry.device_class (not DataPoint.device_class)
        "identifiers",  # DeviceEntry.identifiers
        "name_by_user",  # DeviceEntry.name_by_user
        "id",  # DeviceEntry.id
        "ensure_via_device_exists",  # HA helper method
        # Other HA-specific attributes
        "channel_name",  # HA event attribute
        "data_point",  # HA wrapper attribute (not aiohomematic)
        "start_central",  # HA config flow helper
        "stop_central",  # HA config flow helper
        "enable_sub_devices",  # HA-specific device management
        # HA control_unit wrapper methods
        "get_new_data_points",  # HA control_unit wrapper
        "get_new_hub_data_points",  # HA control_unit wrapper
        "async_get_clientsession",  # HA client session wrapper
        # HA-specific SSDP/UPnP attributes (not in aiohomematic)
        "ssdp_location",  # HA SSDP discovery
        "upnp",  # HA UPnP discovery
        "SsdpServiceInfo",  # HA SSDP service info type
        # HA parameter name wrapper
        "parameter_name",  # HA parameter name attribute (uses .parameter in aiohomematic)
    }
)

# Common Python methods to filter out (false positives)
PYTHON_BUILTINS = frozenset(
    {
        # String methods
        "lower",
        "upper",
        "strip",
        "lstrip",
        "rstrip",
        "replace",
        "split",
        "join",
        "startswith",
        "endswith",
        "find",
        "rfind",
        "index",
        "rindex",
        "count",
        "format",
        "encode",
        "decode",
        "title",
        "capitalize",
        "casefold",
        "center",
        "ljust",
        "rjust",
        "zfill",
        "expandtabs",
        "partition",
        "rpartition",
        "splitlines",
        "isalpha",
        "isdigit",
        "isalnum",
        "isspace",
        "isupper",
        "islower",
        "istitle",
        "isnumeric",
        "isdecimal",
        "isidentifier",
        "isprintable",
        "isascii",
        "maketrans",
        "translate",
        "swapcase",
        "removeprefix",
        "removesuffix",
        # Dict methods
        "get",
        "keys",
        "values",
        "items",
        "pop",
        "popitem",
        "update",
        "setdefault",
        "clear",
        "copy",
        "fromkeys",
        # List methods
        "append",
        "extend",
        "insert",
        "remove",
        "reverse",
        "sort",
        # Set methods
        "add",
        "discard",
        "union",
        "intersection",
        "difference",
        "symmetric_difference",
        "issubset",
        "issuperset",
        "isdisjoint",
        # Common object methods
        "__init__",
        "__str__",
        "__repr__",
        "__eq__",
        "__ne__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__hash__",
        "__bool__",
        "__len__",
        "__iter__",
        "__next__",
        "__contains__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__call__",
        # Async methods
        "wait",
        "cancel",
        "done",
        "result",
        "exception",
        "cancelled",
        # Logging
        "debug",
        "info",
        "warning",
        "error",
        "critical",
        # Type checking
        "isinstance",
        "issubclass",
        "type",
        "hasattr",
        "getattr",
        "setattr",
        "delattr",
        # Common false positives from context
        "suppress",
        "install",
        "in_progress",
    }
)

# Mapping of class names to their full module paths
AIOHOMEMATIC_CLASS_MAP: dict[str, str] = {
    # Central
    "CentralUnit": "aiohomematic.central.CentralUnit",
    "CentralConfig": "aiohomematic.central.CentralConfig",
    # Client
    "Client": "aiohomematic.client.Client",
    "ClientCCU": "aiohomematic.client.ClientCCU",
    "ClientHomegear": "aiohomematic.client.ClientHomegear",
    "InterfaceConfig": "aiohomematic.client.InterfaceConfig",
    # Model - Device/Channel
    "Device": "aiohomematic.model.device.Device",
    "Channel": "aiohomematic.model.device.Channel",
    # Model - DataPoint base
    "BaseDataPoint": "aiohomematic.model.data_point.BaseDataPoint",
    "CallbackDataPoint": "aiohomematic.model.data_point.CallbackDataPoint",
    # Model - Generic
    "GenericDataPoint": "aiohomematic.model.generic.GenericDataPoint",
    "DpAction": "aiohomematic.model.generic.DpAction",
    "DpBinarySensor": "aiohomematic.model.generic.DpBinarySensor",
    "DpButton": "aiohomematic.model.generic.DpButton",
    "DpFloat": "aiohomematic.model.generic.DpFloat",
    "DpInteger": "aiohomematic.model.generic.DpInteger",
    "DpSelect": "aiohomematic.model.generic.DpSelect",
    "DpSensor": "aiohomematic.model.generic.DpSensor",
    "DpSwitch": "aiohomematic.model.generic.DpSwitch",
    "DpText": "aiohomematic.model.generic.DpText",
    # Model - Custom
    "CustomDataPoint": "aiohomematic.model.custom.CustomDataPoint",
    "BaseCustomDpClimate": "aiohomematic.model.custom.climate.BaseCustomDpClimate",
    "CustomDpIpThermostat": "aiohomematic.model.custom.climate.CustomDpIpThermostat",
    "CustomDpRfThermostat": "aiohomematic.model.custom.climate.CustomDpRfThermostat",
    "CustomDpSimpleRfThermostat": "aiohomematic.model.custom.climate.CustomDpSimpleRfThermostat",
    "CustomDpCover": "aiohomematic.model.custom.cover.CustomDpCover",
    "CustomDpBlind": "aiohomematic.model.custom.cover.CustomDpBlind",
    "CustomDpIpBlind": "aiohomematic.model.custom.cover.CustomDpIpBlind",
    "CustomDpGarage": "aiohomematic.model.custom.cover.CustomDpGarage",
    "CustomDpWindowDrive": "aiohomematic.model.custom.cover.CustomDpWindowDrive",
    "CustomDpDimmer": "aiohomematic.model.custom.light.CustomDpDimmer",
    "CustomDpColorDimmer": "aiohomematic.model.custom.light.CustomDpColorDimmer",
    "CustomDpColorDimmerEffect": "aiohomematic.model.custom.light.CustomDpColorDimmerEffect",
    "CustomDpColorTempDimmer": "aiohomematic.model.custom.light.CustomDpColorTempDimmer",
    "CustomDpIpFixedColorLight": "aiohomematic.model.custom.light.CustomDpIpFixedColorLight",
    "CustomDpIpRGBWLight": "aiohomematic.model.custom.light.CustomDpIpRGBWLight",
    "BaseCustomDpLock": "aiohomematic.model.custom.lock.BaseCustomDpLock",
    "CustomDpIpLock": "aiohomematic.model.custom.lock.CustomDpIpLock",
    "CustomDpRfLock": "aiohomematic.model.custom.lock.CustomDpRfLock",
    "CustomDpButtonLock": "aiohomematic.model.custom.lock.CustomDpButtonLock",
    "BaseCustomDpSiren": "aiohomematic.model.custom.siren.BaseCustomDpSiren",
    "CustomDpIpSiren": "aiohomematic.model.custom.siren.CustomDpIpSiren",
    "CustomDpIpSirenSmoke": "aiohomematic.model.custom.siren.CustomDpIpSirenSmoke",
    "CustomDpSwitch": "aiohomematic.model.custom.switch.CustomDpSwitch",
    "CustomDpIpIrrigationValve": "aiohomematic.model.custom.valve.CustomDpIpIrrigationValve",
    # Model - Calculated
    "CalculatedDataPoint": "aiohomematic.model.calculated.CalculatedDataPoint",
    "ApparentTemperature": "aiohomematic.model.calculated.ApparentTemperature",
    "DewPoint": "aiohomematic.model.calculated.DewPoint",
    "FrostPoint": "aiohomematic.model.calculated.FrostPoint",
    # Model - Hub
    "Hub": "aiohomematic.model.hub.Hub",
    # Model - Event
    "Event": "aiohomematic.model.event.Event",
}

# Mapping of context patterns to class info (keywords, class_name, full_path)
CONTEXT_PATTERN_MAP: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("central",), "CentralUnit", "aiohomematic.central.CentralUnit"),
    (("client",), "Client", "aiohomematic.client.Client"),
    (("device",), "Device", "aiohomematic.model.device.Device"),
    (("channel",), "Channel", "aiohomematic.model.device.Channel"),
    (("climate", "thermostat"), "CustomDpClimate", "aiohomematic.model.custom.climate.BaseCustomDpClimate"),
    (("cover", "blind"), "CustomDpCover", "aiohomematic.model.custom.cover.CustomDpCover"),
    (("garage",), "CustomDpGarage", "aiohomematic.model.custom.cover.CustomDpGarage"),
    (("light", "dimmer"), "CustomDpLight", "aiohomematic.model.custom.light.CustomDpDimmer"),
    (("lock",), "CustomDpLock", "aiohomematic.model.custom.lock.BaseCustomDpLock"),
    (("siren",), "CustomDpSiren", "aiohomematic.model.custom.siren.BaseCustomDpSiren"),
    (("switch",), "CustomDpSwitch", "aiohomematic.model.custom.switch.CustomDpSwitch"),
    (("valve",), "CustomDpValve", "aiohomematic.model.custom.valve.CustomDpIpIrrigationValve"),
    (("hub",), "Hub", "aiohomematic.model.hub.Hub"),
    (("event",), "Event", "aiohomematic.model.event.Event"),
    (("data_point", "dp", "_dp"), "DataPoint", "aiohomematic.model.data_point.BaseDataPoint"),
)


def _match_context_pattern(context_str: str) -> tuple[str, str] | None:
    """Match context string against known patterns."""
    for keywords, class_name, full_path in CONTEXT_PATTERN_MAP:
        if any(kw in context_str for kw in keywords):
            return class_name, full_path
    return None


class AioHomematicCallScanner(ast.NodeVisitor):
    """AST visitor that finds calls to aiohomematic methods."""

    # Known aiohomematic type prefixes and patterns
    AIOHOMEMATIC_PATTERNS: tuple[str, ...] = (
        "central",
        "client",
        "device",
        "channel",
        "data_point",
        "dp",
        "custom_dp",
        "generic_dp",
        "calculated_dp",
        "hub",
        "event",
        "climate",
        "cover",
        "light",
        "lock",
        "siren",
        "switch",
        "valve",
        "dimmer",
        "blind",
        "thermostat",
        "garage",
        "button",
        "sensor",
        "binary_sensor",
        "select",
        "number",
        "text",
        "action",
    )

    # Type annotation patterns that indicate aiohomematic types
    AIOHOMEMATIC_TYPE_PATTERNS = (
        r"CentralUnit",
        r"CentralConfig",
        r"Client\w*",
        r"Device",
        r"Channel",
        r"DataPoint",
        r"CustomDp\w+",
        r"DpSwitch",
        r"DpSensor",
        r"DpBinarySensor",
        r"DpSelect",
        r"DpFloat",
        r"DpInteger",
        r"DpText",
        r"DpAction",
        r"DpButton",
        r"GenericDataPoint",
        r"BaseDataPoint",
        r"CalculatedDataPoint",
        r"Hub",
        r"Event",
        r"BaseCustomDp\w+",
    )

    def __init__(
        self,
        file_path: str,
        source: str,
        *,
        include_builtins: bool = False,
        include_private: bool = False,
        include_constants: bool = False,
    ) -> None:
        """Initialize the scanner."""
        self.file_path = file_path
        self.source_lines = source.splitlines()
        self.calls: list[MethodCall] = []
        self.type_hints: dict[str, str] = {}  # variable name -> type hint
        self.import_map: dict[str, str] = {}  # imported name -> full module.class
        self.include_builtins = include_builtins
        self.include_private = include_private
        self.include_constants = include_constants

    def visit_Import(self, node: ast.Import) -> None:
        """Track aiohomematic imports."""
        for alias in node.names:
            if "aiohomematic" in alias.name:
                name = alias.asname or alias.name
                self.import_map[name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track imports from aiohomematic."""
        if node.module and "aiohomematic" in node.module:
            for alias in node.names:
                name = alias.asname or alias.name
                full_path = f"{node.module}.{alias.name}"
                self.import_map[name] = full_path
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Track type-annotated assignments."""
        if isinstance(node.target, ast.Name) and node.annotation:
            type_str = ast.unparse(node.annotation)
            self.type_hints[node.target.id] = type_str
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function parameter type hints."""
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                type_str = ast.unparse(arg.annotation)
                self.type_hints[arg.arg] = type_str
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function parameter type hints."""
        for arg in node.args.args + node.args.kwonlyargs:
            if arg.annotation:
                type_str = ast.unparse(arg.annotation)
                self.type_hints[arg.arg] = type_str
        self.generic_visit(node)

    def _extract_class_name(self, type_hint: str) -> str | None:
        """Extract the class name from a type hint."""
        # Handle Optional, Union, etc.
        type_hint = re.sub(r"Optional\[(.+)\]", r"\1", type_hint)
        type_hint = re.sub(r"Union\[(.+),\s*None\]", r"\1", type_hint)
        type_hint = re.sub(r"\|.*None", "", type_hint)
        type_hint = type_hint.strip()

        # Extract the base class name
        for pattern in self.AIOHOMEMATIC_TYPE_PATTERNS:
            match = re.search(pattern, type_hint)
            if match:
                return match.group(0)
        return None

    def _get_full_class(self, class_name: str) -> str:
        """Return the full module path for a class name."""
        # Check if we have it in imports
        if class_name in self.import_map:
            return self.import_map[class_name]
        # Check if we have it in the known class map
        if class_name in AIOHOMEMATIC_CLASS_MAP:
            return AIOHOMEMATIC_CLASS_MAP[class_name]
        # Try to infer from name patterns
        if class_name.startswith("CustomDp"):
            return f"aiohomematic.model.custom.{class_name}"
        if class_name.startswith("Dp"):
            return f"aiohomematic.model.generic.{class_name}"
        return f"aiohomematic.?.{class_name}"

    def _infer_from_type_hint(self, var_name: str) -> tuple[str, str] | None:
        """Infer class from type hint if available."""
        if var_name in self.type_hints:
            type_hint = self.type_hints[var_name]
            class_name = self._extract_class_name(type_hint)
            if class_name:
                return class_name, self._get_full_class(class_name)
        return None

    def _infer_class_from_context(self, chain: list[str]) -> tuple[str, str]:
        """Infer the class name and full path from the context chain."""
        if chain:
            base_var = chain[0]
            # Check type hint for base variable
            if result := self._infer_from_type_hint(base_var):
                return result

            # Check for self._xxx patterns
            if base_var == "self" and len(chain) > 1:
                attr = chain[1]
                if result := self._infer_from_type_hint(attr):
                    return result
                # Infer from attribute name
                if result := _match_context_pattern(attr.lower()):
                    return result

        # Infer from full context string
        context_str = ".".join(chain).lower()
        if result := _match_context_pattern(context_str):
            return result

        return "Unknown", "aiohomematic.?.Unknown"

    # Home Assistant variable name patterns to exclude (exact matches)
    HA_VARIABLE_PATTERNS: tuple[str, ...] = (
        "device_registry",
        "entity_registry",
        "config_entry",
        "config_entries",
        "hass",
        "entry",
        "platform",
        "trigger_data",
        "trigger_info",
        "action_data",
        "event_trigger",
    )

    def _is_aiohomematic_variable(self, name: str) -> bool:
        """Check if a variable name suggests it's an aiohomematic object."""
        name_lower = name.lower()

        # Exclude Home Assistant specific variable names
        if name_lower in self.HA_VARIABLE_PATTERNS:
            return False

        # Check variable name patterns
        for pattern in self.AIOHOMEMATIC_PATTERNS:
            if pattern in name_lower:
                return True
        # Check if we have a type hint for this variable
        if name in self.type_hints:
            type_hint = self.type_hints[name]
            for type_pattern in self.AIOHOMEMATIC_TYPE_PATTERNS:
                if re.search(type_pattern, type_hint):
                    return True
        return False

    def _get_attribute_chain(self, node: ast.expr) -> list[str]:
        """Return the full attribute chain from a node."""
        chain: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            chain.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            chain.append(current.id)
        elif isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute):
            # Handle chained calls like obj.method1().method2()
            chain.extend(self._get_attribute_chain(current.func))
        chain.reverse()
        return chain

    def _should_include_method(self, method_name: str) -> bool:
        """Check if the method should be included in results."""
        # Skip private/protected attributes (start with underscore)
        if not self.include_private and method_name.startswith("_"):
            return False
        # Skip enum values and constants (ALL_CAPS or ALL_CAPS_WITH_UNDERSCORES)
        if not self.include_constants and (
            method_name.isupper() or (method_name.replace("_", "").isupper() and "_" in method_name)
        ):
            return False
        # Skip Home Assistant specific methods
        if method_name in HOME_ASSISTANT_METHODS:
            return False
        if self.include_builtins:
            return True
        return method_name not in PYTHON_BUILTINS

    def visit_Call(self, node: ast.Call) -> None:
        """Visit a function/method call."""
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            chain = self._get_attribute_chain(node.func)

            # Check if this looks like an aiohomematic call
            is_aiohomematic = False
            context = ".".join(chain)

            # Check the base variable
            if chain:
                base_var = chain[0]
                if self._is_aiohomematic_variable(base_var):
                    is_aiohomematic = True
                # Check for self._xxx patterns where xxx suggests aiohomematic
                if base_var == "self" and len(chain) > 1:
                    attr = chain[1]
                    if self._is_aiohomematic_variable(attr):
                        is_aiohomematic = True

            # Check if any part of the chain matches aiohomematic patterns
            for part in chain:
                if self._is_aiohomematic_variable(part):
                    is_aiohomematic = True
                    break

            if is_aiohomematic and self._should_include_method(method_name):
                class_name, full_class = self._infer_class_from_context(chain)
                self.calls.append(
                    MethodCall(
                        method_name=method_name,
                        class_name=class_name,
                        full_class=full_class,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        context=context,
                    )
                )

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access (for property access)."""
        chain = self._get_attribute_chain(node)

        if chain:
            base_var = chain[0]
            is_aiohomematic = False

            if self._is_aiohomematic_variable(base_var):
                is_aiohomematic = True
            if base_var == "self" and len(chain) > 1:
                attr = chain[1]
                if self._is_aiohomematic_variable(attr):
                    is_aiohomematic = True

            if is_aiohomematic and len(chain) > 1:
                attr_name = chain[-1]
                if self._should_include_method(attr_name):
                    context = ".".join(chain)
                    class_name, full_class = self._infer_class_from_context(chain)
                    self.calls.append(
                        MethodCall(
                            method_name=attr_name,
                            class_name=class_name,
                            full_class=full_class,
                            file_path=self.file_path,
                            line_number=node.lineno,
                            context=context,
                        )
                    )

        self.generic_visit(node)


def scan_file(
    file_path: Path,
    *,
    include_builtins: bool = False,
    include_private: bool = False,
    include_constants: bool = False,
) -> list[MethodCall]:
    """Scan a single Python file for aiohomematic calls."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        scanner = AioHomematicCallScanner(
            str(file_path),
            source,
            include_builtins=include_builtins,
            include_private=include_private,
            include_constants=include_constants,
        )
        scanner.visit(tree)
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:  # noqa: BLE001
        print(f"Error scanning {file_path}: {e}", file=sys.stderr)
        return []
    else:
        return scanner.calls


def scan_directory(
    path: Path,
    *,
    include_builtins: bool = False,
    include_private: bool = False,
    include_constants: bool = False,
) -> list[MethodCall]:
    """Recursively scan a directory for aiohomematic calls."""
    all_calls: list[MethodCall] = []

    for py_file in path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        calls = scan_file(
            py_file,
            include_builtins=include_builtins,
            include_private=include_private,
            include_constants=include_constants,
        )
        all_calls.extend(calls)

    return all_calls


def build_aiohomematic_method_index(aiohomematic_path: Path) -> set[str]:
    """Build an index of all methods/properties defined in aiohomematic."""
    methods: set[str] = set()

    for py_file in aiohomematic_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))

            # Walk through classes to find methods and properties
            for node in ast.walk(tree):
                # Method definitions (including __init__, properties, etc.)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.add(node.name)

                    # Check for @property decorator
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Name) and decorator.id == "property":
                            methods.add(node.name)
                        elif (
                            isinstance(decorator, ast.Attribute)
                            and decorator.attr
                            in (
                                "setter",
                                "deleter",
                                "getter",
                            )
                            and isinstance(decorator.value, ast.Name)
                        ):
                            methods.add(decorator.value.id)

                # Class-level assignments (could be attributes accessed as properties)
                elif isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            # Type-annotated class attributes
                            methods.add(item.target.id)
                        elif isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    methods.add(target.id)

        except (SyntaxError, Exception):
            continue

    return methods


def verify_methods_exist(
    calls: list[MethodCall],
    aiohomematic_path: Path,
) -> tuple[list[MethodCall], list[MethodCall]]:
    """Verify which methods actually exist in aiohomematic."""
    print("Building aiohomematic method index...", file=sys.stderr)
    method_index = build_aiohomematic_method_index(aiohomematic_path)
    print(f"Found {len(method_index)} methods/properties in aiohomematic", file=sys.stderr)

    verified_calls: list[MethodCall] = []
    unverified_calls: list[MethodCall] = []

    for call in calls:
        if call.method_name in method_index:
            verified_calls.append(call)
        else:
            unverified_calls.append(call)

    return verified_calls, unverified_calls


def group_by_class(calls: list[MethodCall]) -> dict[str, dict[str, set[str]]]:
    """Group methods by their full class path."""
    # full_class -> {method_name -> set of file:line locations}
    grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for call in calls:
        loc = f"{call.file_path}:{call.line_number}"
        grouped[call.full_class][call.method_name].add(loc)

    return dict(grouped)


def main() -> None:
    """Run the scanner and output results."""
    parser = argparse.ArgumentParser(
        description="Scan a directory for calls to aiohomematic methods.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s ../homematicip_local/custom_components/homematicip_local
    %(prog)s /path/to/project --verbose
    %(prog)s . --output methods.txt --verify-methods
        """,
    )
    parser.add_argument("path", type=Path, help="Path to scan for aiohomematic calls")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show file locations for each method")
    parser.add_argument("-o", "--output", type=Path, help="Write output to file")
    parser.add_argument(
        "--include-builtins",
        action="store_true",
        help="Include Python builtin methods (get, items, lower, etc.)",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include private/protected attributes (starting with _)",
    )
    parser.add_argument(
        "--include-constants",
        action="store_true",
        help="Include constants and enum values (ALL_CAPS names)",
    )
    parser.add_argument("--show-all", action="store_true", help="Show all occurrences with locations")
    parser.add_argument(
        "--verify-methods",
        action="store_true",
        help="Verify that detected methods actually exist in aiohomematic",
    )
    parser.add_argument(
        "--aiohomematic-path",
        type=Path,
        help="Path to aiohomematic repository (for method verification)",
    )
    parser.add_argument(
        "--show-unverified",
        action="store_true",
        help="Show methods that could not be verified (requires --verify-methods)",
    )

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)

    # Determine aiohomematic path for verification
    aiohomematic_path = args.aiohomematic_path
    if args.verify_methods and not aiohomematic_path:
        # Try to find aiohomematic relative to the script
        script_dir = Path(__file__).parent.parent
        if (script_dir / "aiohomematic").exists():
            aiohomematic_path = script_dir / "aiohomematic"
        else:
            print(
                "Error: --verify-methods requires --aiohomematic-path or script in aiohomematic repo", file=sys.stderr
            )
            sys.exit(1)

    print(f"Scanning {args.path} for aiohomematic calls...", file=sys.stderr)

    if args.path.is_file():
        calls = scan_file(
            args.path,
            include_builtins=args.include_builtins,
            include_private=args.include_private,
            include_constants=args.include_constants,
        )
    else:
        calls = scan_directory(
            args.path,
            include_builtins=args.include_builtins,
            include_private=args.include_private,
            include_constants=args.include_constants,
        )

    if not calls:
        print("No aiohomematic calls found.", file=sys.stderr)
        sys.exit(0)

    # Verify methods if requested
    unverified_calls: list[MethodCall] = []
    if args.verify_methods:
        calls, unverified_calls = verify_methods_exist(calls, aiohomematic_path)
        print(f"Verified {len(calls)} calls, {len(unverified_calls)} unverified", file=sys.stderr)

    # Prepare output
    output_lines: list[str] = []
    grouped = group_by_class(calls)

    total_methods = sum(len(methods) for methods in grouped.values())
    if args.verify_methods:
        output_lines.append(
            f"Found {len(calls)} verified calls to {total_methods} unique methods in {len(grouped)} classes "
            f"({len(unverified_calls)} unverified calls filtered out):\n"
        )
    else:
        output_lines.append(f"Found {len(calls)} calls to {total_methods} unique methods in {len(grouped)} classes:\n")

    if args.show_all:
        # Show all occurrences with locations
        for call in sorted(calls, key=lambda c: (c.full_class, c.method_name, c.file_path, c.line_number)):
            output_lines.append(f"  {call.full_class}.{call.method_name}")
            output_lines.append(f"    -> {call.file_path}:{call.line_number}")
    else:
        # Group by class and show methods
        for full_class in sorted(grouped.keys()):
            methods = grouped[full_class]
            output_lines.append(f"\n{full_class} ({len(methods)} methods):")
            output_lines.append("-" * 70)

            for method_name in sorted(methods.keys()):
                locations = methods[method_name]
                if args.verbose:
                    output_lines.append(f"  {method_name}")
                    output_lines.extend(f"    -> {loc}" for loc in sorted(locations)[:3])
                    if len(locations) > 3:
                        output_lines.append(f"    -> ... and {len(locations) - 3} more")
                else:
                    output_lines.append(f"  {method_name}")

        # Summary
        output_lines.append(f"\n\n{'=' * 70}")
        if args.verify_methods:
            output_lines.append(
                f"SUMMARY: {len(calls)} verified calls, {total_methods} unique methods, {len(grouped)} classes, "
                f"{len(unverified_calls)} unverified calls filtered"
            )
        else:
            output_lines.append(
                f"SUMMARY: {len(calls)} total calls, {total_methods} unique methods, {len(grouped)} classes"
            )
        output_lines.append("=" * 70)

    # Show unverified calls if requested
    if args.show_unverified and unverified_calls:
        unverified_grouped = group_by_class(unverified_calls)
        output_lines.append(f"\n\n{'=' * 70}")
        output_lines.append("UNVERIFIED METHODS (not found in aiohomematic)")
        output_lines.append("=" * 70)

        for full_class in sorted(unverified_grouped.keys()):
            methods = unverified_grouped[full_class]
            output_lines.append(f"\n{full_class} ({len(methods)} methods):")
            output_lines.append("-" * 70)

            for method_name in sorted(methods.keys()):
                locations = methods[method_name]
                if args.verbose:
                    output_lines.append(f"  {method_name}")
                    output_lines.extend(f"    -> {loc}" for loc in sorted(locations)[:3])
                    if len(locations) > 3:
                        output_lines.append(f"    -> ... and {len(locations) - 3} more")
                else:
                    output_lines.append(f"  {method_name}")

    # Output
    output_text = "\n".join(output_lines)

    if args.output:
        args.output.write_text(output_text, encoding="utf-8")
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output_text)


if __name__ == "__main__":
    main()
