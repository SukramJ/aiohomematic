# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for plugin interface stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for plugin interfaces.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Plugin protocols are runtime checkable
2. Required methods and properties exist with correct signatures
3. Plugin validator correctly identifies compliant and non-compliant plugins
4. Backend contract is enforced

See ADR-0019 for architectural context.
"""

from __future__ import annotations

import inspect
from typing import Any, Protocol
from unittest.mock import MagicMock

import pytest

from aiohomematic.central.plugin_registry import PluginRegistry
from aiohomematic.central.plugin_validator import (
    PLUGIN_PROTOCOL_VERSION,
    REQUIRED_BACKEND_METHODS,
    REQUIRED_BACKEND_PROPERTIES,
    REQUIRED_PLUGIN_METHODS,
    REQUIRED_PLUGIN_PROPERTIES,
    get_required_backend_methods,
    get_required_backend_properties,
    get_required_plugin_methods,
    get_required_plugin_properties,
    validate_plugin,
)
from aiohomematic.client.backends.protocol import BackendOperationsProtocol
from aiohomematic.interfaces import ClientPluginProtocol, PluginState

# =============================================================================
# Contract: Protocol Runtime Checkability
# =============================================================================


class TestPluginProtocolRuntimeCheckabilityContract:
    """Contract: Plugin protocols must be runtime checkable."""

    def test_backendoperationsprotocol_is_runtime_checkable(self) -> None:
        """Contract: BackendOperationsProtocol is runtime checkable."""
        assert issubclass(BackendOperationsProtocol, Protocol)

    def test_clientpluginprotocol_is_runtime_checkable(self) -> None:
        """Contract: ClientPluginProtocol is runtime checkable."""
        assert issubclass(ClientPluginProtocol, Protocol)


# =============================================================================
# Contract: ClientPluginProtocol Required Members
# =============================================================================


class TestClientPluginProtocolContract:
    """Contract: ClientPluginProtocol must have required members."""

    def test_has_create_backend_method(self) -> None:
        """Contract: ClientPluginProtocol has create_backend method."""
        assert "create_backend" in dir(ClientPluginProtocol)
        assert callable(getattr(ClientPluginProtocol, "create_backend", None))

    def test_has_get_diagnostics_method(self) -> None:
        """Contract: ClientPluginProtocol has get_diagnostics method."""
        assert "get_diagnostics" in dir(ClientPluginProtocol)

    def test_has_is_running_property(self) -> None:
        """Contract: ClientPluginProtocol has is_running property."""
        assert "is_running" in dir(ClientPluginProtocol)

    def test_has_name_property(self) -> None:
        """Contract: ClientPluginProtocol has name property."""
        assert "name" in dir(ClientPluginProtocol)

    def test_has_start_method(self) -> None:
        """Contract: ClientPluginProtocol has start method."""
        assert "start" in dir(ClientPluginProtocol)

    def test_has_state_property(self) -> None:
        """Contract: ClientPluginProtocol has state property."""
        assert "state" in dir(ClientPluginProtocol)

    def test_has_stop_method(self) -> None:
        """Contract: ClientPluginProtocol has stop method."""
        assert "stop" in dir(ClientPluginProtocol)

    def test_has_supported_interfaces_property(self) -> None:
        """Contract: ClientPluginProtocol has supported_interfaces property."""
        assert "supported_interfaces" in dir(ClientPluginProtocol)

    def test_has_version_property(self) -> None:
        """Contract: ClientPluginProtocol has version property."""
        assert "version" in dir(ClientPluginProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Required Members
# =============================================================================


class TestBackendOperationsProtocolContract:
    """Contract: BackendOperationsProtocol must have required members."""

    def test_check_connection_has_caller_id_param(self) -> None:
        """Contract: check_connection method has caller_id parameter."""
        method = getattr(BackendOperationsProtocol, "check_connection")
        sig = inspect.signature(method)
        param_names = list(sig.parameters.keys())
        assert "caller_id" in param_names

    def test_has_check_connection_method(self) -> None:
        """Contract: BackendOperationsProtocol has check_connection method."""
        assert "check_connection" in dir(BackendOperationsProtocol)

    def test_has_get_value_method(self) -> None:
        """Contract: BackendOperationsProtocol has get_value method."""
        assert "get_value" in dir(BackendOperationsProtocol)

    def test_has_interface_id_property(self) -> None:
        """Contract: BackendOperationsProtocol has interface_id property."""
        assert "interface_id" in dir(BackendOperationsProtocol)

    def test_has_interface_property(self) -> None:
        """Contract: BackendOperationsProtocol has interface property."""
        assert "interface" in dir(BackendOperationsProtocol)

    def test_has_list_devices_method(self) -> None:
        """Contract: BackendOperationsProtocol has list_devices method."""
        assert "list_devices" in dir(BackendOperationsProtocol)

    def test_has_set_value_method(self) -> None:
        """Contract: BackendOperationsProtocol has set_value method."""
        assert "set_value" in dir(BackendOperationsProtocol)

    def test_has_stop_method(self) -> None:
        """Contract: BackendOperationsProtocol has stop method."""
        assert "stop" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: Plugin Validator
# =============================================================================


class MockValidPlugin:
    """A mock plugin that implements all required members."""

    @property
    def is_running(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return "mock-plugin"

    @property
    def state(self) -> PluginState:
        return PluginState.CREATED

    @property
    def supported_interfaces(self) -> frozenset[str]:
        return frozenset({"TestInterface"})

    @property
    def version(self) -> str:
        return "1.0.0"

    async def create_backend(
        self,
        *,
        interface: str,
        interface_id: str,
        username: str,
        password: str,
        device_url: str,
        client_session: Any = None,
        tls: bool = False,
        verify_tls: bool = False,
        has_push_updates: bool = True,
    ) -> Any:
        return MagicMock()

    def get_diagnostics(self) -> dict[str, Any]:
        return {}

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


class MockInvalidPlugin:
    """A mock plugin missing required members (but enough to register)."""

    @property
    def name(self) -> str:
        return "invalid-plugin"

    @property
    def supported_interfaces(self) -> frozenset[str]:
        # Has this so registry.register() doesn't crash
        return frozenset({"TestInterface"})

    @property
    def version(self) -> str:
        # Has this so registry logging doesn't crash
        return "0.0.0"

    # Missing: state, is_running
    # Missing: create_backend, start, stop, get_diagnostics


class TestPluginValidatorContract:
    """Contract: Plugin validator correctly identifies compliant plugins."""

    def test_invalid_plugin_fails_validation(self) -> None:
        """Contract: Invalid plugin fails validation."""
        plugin = MockInvalidPlugin()
        result = validate_plugin(plugin=plugin)
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_missing_method_detected(self) -> None:
        """Contract: Missing method is detected."""
        plugin = MockInvalidPlugin()
        result = validate_plugin(plugin=plugin)
        error_messages = [e.message for e in result.errors]
        assert any("create_backend" in msg or "start" in msg or "stop" in msg for msg in error_messages)

    def test_missing_property_detected(self) -> None:
        """Contract: Missing property is detected."""
        plugin = MockInvalidPlugin()
        result = validate_plugin(plugin=plugin)
        error_messages = [e.message for e in result.errors]
        # MockInvalidPlugin is missing 'state' and 'is_running' properties
        assert any("state" in msg for msg in error_messages)

    def test_valid_plugin_passes_validation(self) -> None:
        """Contract: Valid plugin passes validation."""
        plugin = MockValidPlugin()
        result = validate_plugin(plugin=plugin)
        assert result.is_valid, f"Errors: {result.errors}"


# =============================================================================
# Contract: Plugin Registry Validation
# =============================================================================


class TestPluginRegistryValidationContract:
    """Contract: Plugin registry validates plugins on registration."""

    def test_invalid_plugin_rejected_on_registration(self) -> None:
        """Contract: Invalid plugin is rejected on registration."""
        registry = PluginRegistry()
        plugin = MockInvalidPlugin()
        with pytest.raises(TypeError, match="failed contract validation"):
            registry.register(plugin=plugin)

    def test_valid_plugin_registers_successfully(self) -> None:
        """Contract: Valid plugin can be registered."""
        registry = PluginRegistry()
        plugin = MockValidPlugin()
        registry.register(plugin=plugin)
        assert plugin.name in registry.plugins

    def test_validation_can_be_disabled(self) -> None:
        """Contract: Validation can be disabled for testing."""
        registry = PluginRegistry()
        plugin = MockInvalidPlugin()
        # Should not raise when validation is disabled
        registry.register(plugin=plugin, validate=False)
        assert plugin.name in registry.plugins


# =============================================================================
# Contract: Required Properties and Methods Lists (Dynamic Extraction)
# =============================================================================


class TestRequiredMembersContract:
    """Contract: Required members are dynamically extracted from protocols."""

    def test_cached_values_match_dynamic_extraction(self) -> None:
        """Contract: Cached values match fresh dynamic extraction."""
        # Verify cached REQUIRED_* constants match fresh extraction
        assert get_required_plugin_properties() == REQUIRED_PLUGIN_PROPERTIES
        assert get_required_plugin_methods() == REQUIRED_PLUGIN_METHODS
        assert get_required_backend_properties() == REQUIRED_BACKEND_PROPERTIES
        assert get_required_backend_methods() == REQUIRED_BACKEND_METHODS

    def test_protocol_version_is_defined(self) -> None:
        """Contract: Plugin protocol version is defined."""
        assert PLUGIN_PROTOCOL_VERSION >= 1

    def test_required_backend_methods_match_protocol(self) -> None:
        """Contract: Backend methods are extracted from BackendOperationsProtocol."""
        methods = get_required_backend_methods()
        # Core methods must be present
        assert "initialize" in methods
        assert "stop" in methods
        assert "check_connection" in methods
        assert "list_devices" in methods
        assert "get_value" in methods
        assert "set_value" in methods
        assert "get_all_device_data" in methods

    def test_required_backend_properties_match_protocol(self) -> None:
        """Contract: Backend properties are extracted from BackendOperationsProtocol."""
        props = get_required_backend_properties()
        # Core properties must be present
        assert "interface" in props
        assert "interface_id" in props
        assert "capabilities" in props
        assert "system_information" in props

    def test_required_plugin_methods_match_protocol(self) -> None:
        """Contract: Plugin methods are extracted from ClientPluginProtocol."""
        methods = get_required_plugin_methods()
        # Core methods must be present
        assert "create_backend" in methods
        assert "start" in methods
        assert "stop" in methods
        assert "get_diagnostics" in methods

    def test_required_plugin_properties_match_protocol(self) -> None:
        """Contract: Plugin properties are extracted from ClientPluginProtocol."""
        props = get_required_plugin_properties()
        # Core properties must be present
        assert "name" in props
        assert "version" in props
        assert "supported_interfaces" in props
        assert "state" in props
        assert "is_running" in props


class TestDynamicExtractionSyncContract:
    """Contract: Dynamic extraction stays in sync with protocol changes."""

    def test_backend_protocol_methods_all_extracted(self) -> None:
        """Contract: All BackendOperationsProtocol methods are extracted."""
        # Get all public methods from BackendOperationsProtocol
        protocol_methods = {
            name
            for name in dir(BackendOperationsProtocol)
            if not name.startswith("_")
            and name not in ("mro", "register")
            and callable(getattr(BackendOperationsProtocol, name))
            and not isinstance(inspect.getattr_static(BackendOperationsProtocol, name), property)
        }

        extracted_methods = set(get_required_backend_methods().keys())

        # All protocol methods should be in extracted methods
        missing = protocol_methods - extracted_methods
        assert not missing, f"Methods in protocol but not extracted: {missing}"

    def test_backend_protocol_properties_all_extracted(self) -> None:
        """Contract: All BackendOperationsProtocol properties are extracted."""
        # Get all public properties from BackendOperationsProtocol
        protocol_properties = {
            name
            for name in dir(BackendOperationsProtocol)
            if not name.startswith("_")
            and name not in ("mro", "register")
            and isinstance(inspect.getattr_static(BackendOperationsProtocol, name), property)
        }

        extracted_properties = set(get_required_backend_properties().keys())

        # All protocol properties should be in extracted properties
        missing = protocol_properties - extracted_properties
        assert not missing, f"Properties in protocol but not extracted: {missing}"


# =============================================================================
# Contract: PluginState Enum
# =============================================================================


class TestPluginStateContract:
    """Contract: PluginState enum has required values."""

    def test_has_created_state(self) -> None:
        """Contract: PluginState has CREATED value."""
        assert hasattr(PluginState, "CREATED")

    def test_has_failed_state(self) -> None:
        """Contract: PluginState has FAILED value."""
        assert hasattr(PluginState, "FAILED")

    def test_has_running_state(self) -> None:
        """Contract: PluginState has RUNNING value."""
        assert hasattr(PluginState, "RUNNING")

    def test_has_starting_state(self) -> None:
        """Contract: PluginState has STARTING value."""
        assert hasattr(PluginState, "STARTING")

    def test_has_stopped_state(self) -> None:
        """Contract: PluginState has STOPPED value."""
        assert hasattr(PluginState, "STOPPED")

    def test_has_stopping_state(self) -> None:
        """Contract: PluginState has STOPPING value."""
        assert hasattr(PluginState, "STOPPING")
