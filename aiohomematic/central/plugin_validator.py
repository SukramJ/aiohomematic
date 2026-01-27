# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Plugin contract validator.

Validates that plugins correctly implement the required protocols
before they are registered and used.

The validator dynamically inspects BackendOperationsProtocol to ensure
it stays in sync with any protocol changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import logging
from typing import Any, Final

from aiohomematic.client.backends.protocol import BackendOperationsProtocol
from aiohomematic.interfaces.plugin import ClientPluginProtocol

_LOGGER: Final = logging.getLogger(__name__)

# Current plugin protocol version - increment on breaking changes
PLUGIN_PROTOCOL_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class ValidationError:
    """A single validation error."""

    category: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass(slots=True)
class ValidationResult:
    """Result of plugin validation."""

    plugin_name: str
    is_valid: bool = True
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def add_error(self, *, category: str, message: str) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(category=category, message=message, severity="error"))
        self.is_valid = False

    def add_warning(self, *, category: str, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(ValidationError(category=category, message=message, severity="warning"))


def _get_protocol_members(*, protocol: type) -> tuple[set[str], set[str]]:
    """
    Extract properties and methods from a Protocol class.

    Returns:
        Tuple of (property_names, method_names).

    """
    properties: set[str] = set()
    methods: set[str] = set()

    for name in dir(protocol):
        if name.startswith("_"):
            continue

        # Skip Protocol internals
        if name in ("mro", "register"):
            continue

        if (member := getattr(protocol, name, None)) is None:
            continue

        # Check if it's a property (defined with @property in Protocol)
        if isinstance(inspect.getattr_static(protocol, name), property):
            properties.add(name)
        elif callable(member):
            methods.add(name)

    return properties, methods


def _get_method_signature(*, protocol: type, method_name: str) -> dict[str, Any]:
    """
    Get method signature details.

    Returns:
        Dict with 'params' (list of param names) and 'is_async' (bool).

    """
    if (method := getattr(protocol, method_name, None)) is None:
        return {"params": [], "is_async": False}

    try:
        sig = inspect.signature(method)
        params = [p for p in sig.parameters if p not in ("self", "cls", "return")]

        # Check if method is async (has 'async' in source or is coroutine)
        is_async = inspect.iscoroutinefunction(method)
    except (ValueError, TypeError):
        return {"params": [], "is_async": False}
    else:
        return {"params": params, "is_async": is_async}


# =============================================================================
# Dynamically extracted requirements from protocols
# =============================================================================


def get_required_plugin_properties() -> dict[str, type | None]:
    """Return required plugin properties from ClientPluginProtocol."""
    properties, _ = _get_protocol_members(protocol=ClientPluginProtocol)
    # Return dict with None as type (we don't enforce types at runtime)
    return dict.fromkeys(properties)


def get_required_plugin_methods() -> dict[str, dict[str, Any]]:
    """Return required plugin methods from ClientPluginProtocol."""
    _, methods = _get_protocol_members(protocol=ClientPluginProtocol)
    return {name: _get_method_signature(protocol=ClientPluginProtocol, method_name=name) for name in methods}


def get_required_backend_properties() -> dict[str, type | None]:
    """Return required backend properties from BackendOperationsProtocol."""
    properties, _ = _get_protocol_members(protocol=BackendOperationsProtocol)
    return dict.fromkeys(properties)


def get_required_backend_methods() -> dict[str, dict[str, Any]]:
    """Return required backend methods from BackendOperationsProtocol."""
    _, methods = _get_protocol_members(protocol=BackendOperationsProtocol)
    return {name: _get_method_signature(protocol=BackendOperationsProtocol, method_name=name) for name in methods}


# Cached versions for performance (computed once at import time)
REQUIRED_PLUGIN_PROPERTIES: Final = get_required_plugin_properties()
REQUIRED_PLUGIN_METHODS: Final = get_required_plugin_methods()
REQUIRED_BACKEND_PROPERTIES: Final = get_required_backend_properties()
REQUIRED_BACKEND_METHODS: Final = get_required_backend_methods()


def _check_properties(
    *,
    obj: Any,
    required: dict[str, type | None],
    result: ValidationResult,
    category_prefix: str,
) -> None:
    """Check that an object has required properties."""
    for prop_name, expected_type in required.items():
        if not hasattr(obj, prop_name):
            result.add_error(
                category=f"{category_prefix}.property",
                message=f"Missing required property: {prop_name}",
            )
            continue

        # Try to get the property value
        try:
            value = getattr(obj, prop_name)
            if expected_type is not None and not isinstance(value, expected_type):
                result.add_warning(
                    category=f"{category_prefix}.property_type",
                    message=f"Property '{prop_name}' has type {type(value).__name__}, expected {expected_type.__name__}",
                )
        except Exception as exc:
            result.add_error(
                category=f"{category_prefix}.property_access",
                message=f"Error accessing property '{prop_name}': {exc}",
            )


def _check_methods(
    *,
    obj: Any,
    required: dict[str, dict[str, Any]],
    result: ValidationResult,
    category_prefix: str,
) -> None:
    """Check that an object has required methods with correct signatures."""
    for method_name, method_spec in required.items():
        if not hasattr(obj, method_name):
            result.add_error(
                category=f"{category_prefix}.method",
                message=f"Missing required method: {method_name}",
            )
            continue

        method = getattr(obj, method_name)

        # Check if it's callable
        if not callable(method):
            result.add_error(
                category=f"{category_prefix}.method",
                message=f"'{method_name}' is not callable",
            )
            continue

        # Check if async/sync matches
        is_async = inspect.iscoroutinefunction(method)
        expected_async = method_spec.get("is_async", False)
        if is_async != expected_async:
            result.add_error(
                category=f"{category_prefix}.method_async",
                message=f"Method '{method_name}' should be {'async' if expected_async else 'sync'}, "
                f"but is {'async' if is_async else 'sync'}",
            )

        # Check parameters
        try:
            sig = inspect.signature(method)
            param_names = [p for p in sig.parameters if p not in ("self", "cls", "return")]

            expected_params = method_spec.get("params", [])
            for expected_param in expected_params:
                if expected_param not in param_names:
                    result.add_error(
                        category=f"{category_prefix}.method_param",
                        message=f"Method '{method_name}' missing parameter: {expected_param}",
                    )
        except (ValueError, TypeError) as exc:
            result.add_warning(
                category=f"{category_prefix}.method_signature",
                message=f"Could not inspect signature of '{method_name}': {exc}",
            )


def validate_plugin(*, plugin: ClientPluginProtocol) -> ValidationResult:
    """
    Validate that a plugin correctly implements the ClientPluginProtocol.

    The requirements are dynamically extracted from the protocol definition,
    so this validator automatically stays in sync with protocol changes.

    Args:
        plugin: The plugin to validate.

    Returns:
        ValidationResult with errors and warnings.

    """
    result = ValidationResult(plugin_name=getattr(plugin, "name", "<unknown>"))

    # Check plugin properties
    _check_properties(
        obj=plugin,
        required=REQUIRED_PLUGIN_PROPERTIES,
        result=result,
        category_prefix="plugin",
    )

    # Check plugin methods
    _check_methods(
        obj=plugin,
        required=REQUIRED_PLUGIN_METHODS,
        result=result,
        category_prefix="plugin",
    )

    # Validate supported_interfaces is not empty
    if hasattr(plugin, "supported_interfaces") and not plugin.supported_interfaces:
        result.add_error(
            category="plugin.interfaces",
            message="Plugin must support at least one interface",
        )

    return result


async def validate_backend(*, backend: Any, interface_id: str) -> ValidationResult:
    """
    Validate that a backend correctly implements BackendOperationsProtocol.

    The requirements are dynamically extracted from the protocol definition,
    so this validator automatically stays in sync with protocol changes.

    Args:
        backend: The backend instance to validate.
        interface_id: The interface ID for logging.

    Returns:
        ValidationResult with errors and warnings.

    """
    result = ValidationResult(plugin_name=f"backend:{interface_id}")

    # Check backend properties
    _check_properties(
        obj=backend,
        required=REQUIRED_BACKEND_PROPERTIES,
        result=result,
        category_prefix="backend",
    )

    # Check backend methods
    _check_methods(
        obj=backend,
        required=REQUIRED_BACKEND_METHODS,
        result=result,
        category_prefix="backend",
    )

    return result


def validate_and_raise(*, plugin: ClientPluginProtocol) -> None:
    """
    Validate plugin and raise exception if invalid.

    Args:
        plugin: The plugin to validate.

    Raises:
        TypeError: If the plugin fails validation.

    """
    result = validate_plugin(plugin=plugin)

    if not result.is_valid:
        error_messages = [f"  - [{e.category}] {e.message}" for e in result.errors]
        raise TypeError(f"Plugin '{result.plugin_name}' failed contract validation:\n" + "\n".join(error_messages))

    # Log warnings
    for warning in result.warnings:
        _LOGGER.warning(  # i18n-log: ignore
            "Plugin '%s' validation warning [%s]: %s",
            result.plugin_name,
            warning.category,
            warning.message,
        )


async def validate_backend_and_raise(*, backend: Any, interface_id: str) -> None:
    """
    Validate backend and raise exception if invalid.

    Args:
        backend: The backend to validate.
        interface_id: Interface ID for error messages.

    Raises:
        TypeError: If the backend fails validation.

    """
    result = await validate_backend(backend=backend, interface_id=interface_id)

    if not result.is_valid:
        error_messages = [f"  - [{e.category}] {e.message}" for e in result.errors]
        raise TypeError(f"Backend for '{interface_id}' failed contract validation:\n" + "\n".join(error_messages))

    # Log warnings
    for warning in result.warnings:
        _LOGGER.warning(  # i18n-log: ignore
            "Backend '%s' validation warning [%s]: %s",
            interface_id,
            warning.category,
            warning.message,
        )
