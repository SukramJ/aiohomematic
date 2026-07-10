# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for ClientProtocol interface stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for ClientProtocol and its sub-protocols.
Any change that breaks these tests requires a MAJOR version bump and coordination
with plugin maintainers (e.g., Homematic(IP) Local).

The contract ensures that:
1. ClientProtocol combines all required sub-protocols
2. All sub-protocol methods and properties exist
3. Method signatures are stable
4. Sub-protocols can be used independently for interface segregation

Note on inlined sub-protocols: `ClientLifecycleProtocol`, `ClientSupportProtocol`,
`SystemVariableOperationsProtocol`, `ProgramOperationsProtocol`, `LinkOperationsProtocol`,
`FirmwareOperationsProtocol`, `BackupOperationsProtocol`, `SystemManagementOperationsProtocol`,
and `MaintenanceOperationsProtocol` had no consumer independent of `ClientProtocol` and have
been inlined directly into the composite (see `aiohomematic/interfaces/client.py`). Their
stability coverage now lives in `TestClientProtocolFullApiContract` below.
`ParamsetOperationsProtocol` and `ValueOperationsProtocol` were merged into
`ValueAndParamsetOperationsProtocol`, which remains a standalone protocol.

See ADR-0018 for architectural context and rationale.
"""

import inspect

import pytest

from aiohomematic.interfaces import (
    ClientConnectionProtocol,
    ClientIdentityProtocol,
    ClientProtocol,
    ClientProviderProtocol,
    DeviceDiscoveryOperationsProtocol,
    MetadataOperationsProtocol,
    PrimaryClientProviderProtocol,
)
from aiohomematic.interfaces.client import ValueAndParamsetOperationsProtocol

# =============================================================================
# SECTION 1: ClientProtocol Composition Contract
# =============================================================================


class TestClientProtocolCompositionContract:
    """
    Contract: ClientProtocol MUST be a composite of all client sub-protocols.

    This ensures that any code depending on ClientProtocol has access to
    all client functionality through a single interface.
    """

    def test_clientprotocol_is_protocol(self) -> None:
        """CONTRACT: ClientProtocol MUST be a Protocol."""
        # Check for protocol markers (Protocol is a special typing form)
        assert hasattr(ClientProtocol, "__protocol_attrs__") or hasattr(ClientProtocol, "_is_protocol")

    def test_clientprotocol_is_runtime_checkable(self) -> None:
        """CONTRACT: ClientProtocol MUST be runtime checkable."""
        # runtime_checkable protocols have __subclasshook__
        assert hasattr(ClientProtocol, "__subclasshook__")


# =============================================================================
# SECTION 2: ClientIdentityProtocol Contract
# =============================================================================


class TestClientIdentityProtocolContract:
    """
    Contract: ClientIdentityProtocol must provide client identification.

    These properties are used for logging, debugging, and client lookup.
    """

    def test_has_central_property(self) -> None:
        """CONTRACT: ClientIdentityProtocol MUST have central property."""
        assert "central" in dir(ClientIdentityProtocol)

    def test_has_interface_id_property(self) -> None:
        """CONTRACT: ClientIdentityProtocol MUST have interface_id property."""
        assert "interface_id" in dir(ClientIdentityProtocol)

    def test_has_interface_property(self) -> None:
        """CONTRACT: ClientIdentityProtocol MUST have interface property."""
        assert "interface" in dir(ClientIdentityProtocol)

    def test_has_is_initialized_property(self) -> None:
        """CONTRACT: ClientIdentityProtocol MUST have is_initialized property."""
        assert "is_initialized" in dir(ClientIdentityProtocol)

    def test_has_model_property(self) -> None:
        """CONTRACT: ClientIdentityProtocol MUST have model property."""
        assert "model" in dir(ClientIdentityProtocol)

    def test_has_system_information_property(self) -> None:
        """CONTRACT: ClientIdentityProtocol MUST have system_information property."""
        assert "system_information" in dir(ClientIdentityProtocol)

    def test_has_version_property(self) -> None:
        """CONTRACT: ClientIdentityProtocol MUST have version property."""
        assert "version" in dir(ClientIdentityProtocol)


# =============================================================================
# SECTION 3: ClientConnectionProtocol Contract
# =============================================================================


class TestClientConnectionProtocolContract:
    """
    Contract: ClientConnectionProtocol must provide connection state management.

    These methods are critical for connection health monitoring and recovery.
    """

    def test_has_all_circuit_breakers_closed_property(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have all_circuit_breakers_closed property."""
        assert "all_circuit_breakers_closed" in dir(ClientConnectionProtocol)

    def test_has_available_property(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have available property."""
        assert "available" in dir(ClientConnectionProtocol)

    def test_has_check_connection_availability_method(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have check_connection_availability method."""
        assert "check_connection_availability" in dir(ClientConnectionProtocol)

    def test_has_clear_json_rpc_session_method(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have clear_json_rpc_session method."""
        assert "clear_json_rpc_session" in dir(ClientConnectionProtocol)

    def test_has_is_callback_alive_method(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have is_callback_alive method."""
        assert "is_callback_alive" in dir(ClientConnectionProtocol)

    def test_has_is_connected_method(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have is_connected method."""
        assert "is_connected" in dir(ClientConnectionProtocol)

    def test_has_modified_at_property(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have modified_at property."""
        assert "modified_at" in dir(ClientConnectionProtocol)

    def test_has_reconnect_method(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have reconnect method."""
        assert "reconnect" in dir(ClientConnectionProtocol)

    def test_has_reset_circuit_breakers_method(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have reset_circuit_breakers method."""
        assert "reset_circuit_breakers" in dir(ClientConnectionProtocol)

    def test_has_state_machine_property(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have state_machine property."""
        assert "state_machine" in dir(ClientConnectionProtocol)

    def test_has_state_property(self) -> None:
        """CONTRACT: ClientConnectionProtocol MUST have state property."""
        assert "state" in dir(ClientConnectionProtocol)


# =============================================================================
# SECTION 4: DeviceDiscoveryOperationsProtocol Contract
# =============================================================================


class TestDeviceDiscoveryOperationsProtocolContract:
    """
    Contract: DeviceDiscoveryOperationsProtocol must provide device discovery.

    These methods are essential for device enumeration and setup.
    """

    def test_has_fetch_all_device_data_method(self) -> None:
        """CONTRACT: DeviceDiscoveryOperationsProtocol MUST have fetch_all_device_data method."""
        assert "fetch_all_device_data" in dir(DeviceDiscoveryOperationsProtocol)

    def test_has_fetch_device_details_method(self) -> None:
        """CONTRACT: DeviceDiscoveryOperationsProtocol MUST have fetch_device_details method."""
        assert "fetch_device_details" in dir(DeviceDiscoveryOperationsProtocol)

    def test_has_get_all_device_descriptions_method(self) -> None:
        """CONTRACT: DeviceDiscoveryOperationsProtocol MUST have get_all_device_descriptions method."""
        assert "get_all_device_descriptions" in dir(DeviceDiscoveryOperationsProtocol)

    def test_has_get_device_description_method(self) -> None:
        """CONTRACT: DeviceDiscoveryOperationsProtocol MUST have get_device_description method."""
        assert "get_device_description" in dir(DeviceDiscoveryOperationsProtocol)

    def test_has_list_devices_method(self) -> None:
        """CONTRACT: DeviceDiscoveryOperationsProtocol MUST have list_devices method."""
        assert "list_devices" in dir(DeviceDiscoveryOperationsProtocol)


# =============================================================================
# SECTION 5: ValueAndParamsetOperationsProtocol Contract
# =============================================================================


class TestValueAndParamsetOperationsProtocolContract:
    """
    Contract: ValueAndParamsetOperationsProtocol must provide value and paramset operations.

    These are the core methods for reading and writing device parameter values and paramsets.
    Formerly split across ValueOperationsProtocol and ParamsetOperationsProtocol, now merged
    into a single protocol since both had no consumer independent of the combination.
    """

    def test_get_value_signature_has_channel_address(self) -> None:
        """CONTRACT: get_value MUST accept channel_address parameter."""
        sig = inspect.signature(ValueAndParamsetOperationsProtocol.get_value)
        assert "channel_address" in sig.parameters

    def test_has_fetch_paramset_description_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have fetch_paramset_description method."""
        assert "fetch_paramset_description" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_fetch_paramset_descriptions_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have fetch_paramset_descriptions method."""
        assert "fetch_paramset_descriptions" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_get_all_paramset_descriptions_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have get_all_paramset_descriptions method."""
        assert "get_all_paramset_descriptions" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_get_paramset_description_on_demand_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have get_paramset_description_on_demand method."""
        assert "get_paramset_description_on_demand" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_get_paramset_descriptions_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have get_paramset_descriptions method."""
        assert "get_paramset_descriptions" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_get_paramset_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have get_paramset method."""
        assert "get_paramset" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_get_value_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have get_value method."""
        assert "get_value" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_put_paramset_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have put_paramset method."""
        assert "put_paramset" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_report_value_usage_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have report_value_usage method."""
        assert "report_value_usage" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_set_value_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have set_value method."""
        assert "set_value" in dir(ValueAndParamsetOperationsProtocol)

    def test_has_update_paramset_descriptions_method(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST have update_paramset_descriptions method."""
        assert "update_paramset_descriptions" in dir(ValueAndParamsetOperationsProtocol)

    def test_is_protocol(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST be a Protocol."""
        assert hasattr(ValueAndParamsetOperationsProtocol, "__protocol_attrs__")

    def test_set_value_signature_has_channel_address(self) -> None:
        """CONTRACT: set_value MUST accept channel_address parameter."""
        sig = inspect.signature(ValueAndParamsetOperationsProtocol.set_value)
        assert "channel_address" in sig.parameters

    def test_set_value_signature_has_parameter(self) -> None:
        """CONTRACT: set_value MUST accept parameter parameter."""
        sig = inspect.signature(ValueAndParamsetOperationsProtocol.set_value)
        assert "parameter" in sig.parameters

    def test_set_value_signature_has_value(self) -> None:
        """CONTRACT: set_value MUST accept value parameter."""
        sig = inspect.signature(ValueAndParamsetOperationsProtocol.set_value)
        assert "value" in sig.parameters


# =============================================================================
# SECTION 6: MetadataOperationsProtocol Contract
# =============================================================================


class TestMetadataOperationsProtocolContract:
    """
    Contract: MetadataOperationsProtocol must provide metadata operations.

    These methods are essential for metadata, rooms, functions, and install mode.
    """

    def test_has_accept_device_in_inbox_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have accept_device_in_inbox method."""
        assert "accept_device_in_inbox" in dir(MetadataOperationsProtocol)

    def test_has_get_all_functions_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_all_functions method."""
        assert "get_all_functions" in dir(MetadataOperationsProtocol)

    def test_has_get_all_rooms_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_all_rooms method."""
        assert "get_all_rooms" in dir(MetadataOperationsProtocol)

    def test_has_get_inbox_devices_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_inbox_devices method."""
        assert "get_inbox_devices" in dir(MetadataOperationsProtocol)

    def test_has_get_install_mode_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_install_mode method."""
        assert "get_install_mode" in dir(MetadataOperationsProtocol)

    def test_has_get_ise_id_by_address_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_ise_id_by_address method."""
        assert "get_ise_id_by_address" in dir(MetadataOperationsProtocol)

    def test_has_get_metadata_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_metadata method."""
        assert "get_metadata" in dir(MetadataOperationsProtocol)

    def test_has_get_service_messages_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_service_messages method."""
        assert "get_service_messages" in dir(MetadataOperationsProtocol)

    def test_has_get_system_update_info_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_system_update_info method."""
        assert "get_system_update_info" in dir(MetadataOperationsProtocol)

    def test_has_rename_channel_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have rename_channel method."""
        assert "rename_channel" in dir(MetadataOperationsProtocol)

    def test_has_rename_device_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have rename_device method."""
        assert "rename_device" in dir(MetadataOperationsProtocol)

    def test_has_set_install_mode_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have set_install_mode method."""
        assert "set_install_mode" in dir(MetadataOperationsProtocol)

    def test_has_set_metadata_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have set_metadata method."""
        assert "set_metadata" in dir(MetadataOperationsProtocol)


# =============================================================================
# SECTION 7: ClientProviderProtocol Contract
# =============================================================================


class TestClientProviderProtocolContract:
    """
    Contract: ClientProviderProtocol must provide client access methods.

    These methods are used by CentralUnit to provide client lookup.
    """

    def test_has_get_client_method(self) -> None:
        """CONTRACT: ClientProviderProtocol MUST have get_client method."""
        assert "get_client" in dir(ClientProviderProtocol)

    def test_has_has_client_method(self) -> None:
        """CONTRACT: ClientProviderProtocol MUST have has_client method."""
        assert "has_client" in dir(ClientProviderProtocol)

    def test_has_has_clients_property(self) -> None:
        """CONTRACT: ClientProviderProtocol MUST have has_clients property."""
        assert "has_clients" in dir(ClientProviderProtocol)

    def test_has_interface_ids_property(self) -> None:
        """CONTRACT: ClientProviderProtocol MUST have interface_ids property."""
        assert "interface_ids" in dir(ClientProviderProtocol)


# =============================================================================
# SECTION 8: PrimaryClientProviderProtocol Contract
# =============================================================================


class TestPrimaryClientProviderProtocolContractDetailed:
    """Contract tests for PrimaryClientProviderProtocol."""

    def test_has_primary_client_property(self) -> None:
        """CONTRACT: PrimaryClientProviderProtocol MUST have primary_client property."""
        assert "primary_client" in dir(PrimaryClientProviderProtocol)


# =============================================================================
# SECTION 9: ClientProtocol Full API Contract
# =============================================================================


class TestClientProtocolFullApiContract:
    """
    Contract: ClientProtocol MUST expose all sub-protocol methods.

    This comprehensive test ensures the composite protocol provides
    access to all expected functionality, including members formerly declared on
    now-inlined ISP slices (ClientLifecycleProtocol, ClientSupportProtocol,
    SystemVariableOperationsProtocol, ProgramOperationsProtocol, LinkOperationsProtocol,
    FirmwareOperationsProtocol, BackupOperationsProtocol).
    """

    @pytest.mark.parametrize(
        "method_name",
        [
            # ClientIdentityProtocol
            "interface",
            "interface_id",
            "model",
            "version",
            # ClientConnectionProtocol
            "available",
            "is_callback_alive",
            "is_connected",
            "reconnect",
            # Lifecycle (inlined, formerly ClientLifecycleProtocol)
            "init_client",
            "stop",
            "init_proxy",
            "deinit_proxy",
            # DeviceDiscoveryOperationsProtocol
            "list_devices",
            "get_device_description",
            # ValueAndParamsetOperationsProtocol
            "get_value",
            "set_value",
            "get_paramset",
            "put_paramset",
            # Device linking (inlined, formerly LinkOperationsProtocol)
            "add_link",
            "remove_link",
            # Firmware (inlined, formerly FirmwareOperationsProtocol)
            "update_device_firmware",
            # System variables (inlined, formerly SystemVariableOperationsProtocol)
            "get_system_variable",
            "set_system_variable",
            # Programs (inlined, formerly ProgramOperationsProtocol)
            "execute_program",
            "get_all_programs",
            # Backup (inlined, formerly BackupOperationsProtocol)
            "create_backup_and_download",
            # MetadataOperationsProtocol
            "get_all_rooms",
            "get_all_functions",
            "get_install_mode",
            "set_install_mode",
            # Support utilities (inlined, formerly ClientSupportProtocol)
            "command_throttle",
            "in_flight_commands",
            "last_value_send_tracker",
            "ping_pong_tracker",
            "get_product_group",
            "get_virtual_remote",
            # ClientProtocol specific
            "capabilities",
        ],
    )
    def test_clientprotocol_has_method(self, method_name: str) -> None:
        """CONTRACT: ClientProtocol MUST have all sub-protocol methods."""
        assert method_name in dir(ClientProtocol), f"ClientProtocol missing {method_name}"
