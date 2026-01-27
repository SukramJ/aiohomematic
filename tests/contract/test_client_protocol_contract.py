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

See ADR-0018 for architectural context and rationale.
"""

from __future__ import annotations

import inspect

import pytest

from aiohomematic.interfaces import (
    ClientConnectionProtocol,
    ClientIdentityProtocol,
    ClientLifecycleProtocol,
    ClientProtocol,
    ClientProviderProtocol,
    ClientSupportProtocol,
    DeviceDiscoveryOperationsProtocol,
    MaintenanceOperationsProtocol,
    MetadataOperationsProtocol,
    PrimaryClientProviderProtocol,
    SystemManagementOperationsProtocol,
)
from aiohomematic.interfaces.client import (
    BackupOperationsProtocol,
    FirmwareOperationsProtocol,
    LinkOperationsProtocol,
    ParamsetOperationsProtocol,
    ProgramOperationsProtocol,
    SystemVariableOperationsProtocol,
    ValueAndParamsetOperationsProtocol,
    ValueOperationsProtocol,
)

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
# SECTION 4: ClientLifecycleProtocol Contract
# =============================================================================


class TestClientLifecycleProtocolContract:
    """
    Contract: ClientLifecycleProtocol must provide lifecycle operations.

    These methods are essential for client initialization and shutdown.
    """

    def test_has_deinitialize_proxy_method(self) -> None:
        """CONTRACT: ClientLifecycleProtocol MUST have deinitialize_proxy method."""
        assert "deinitialize_proxy" in dir(ClientLifecycleProtocol)

    def test_has_init_client_method(self) -> None:
        """CONTRACT: ClientLifecycleProtocol MUST have init_client method."""
        assert "init_client" in dir(ClientLifecycleProtocol)

    def test_has_initialize_proxy_method(self) -> None:
        """CONTRACT: ClientLifecycleProtocol MUST have initialize_proxy method."""
        assert "initialize_proxy" in dir(ClientLifecycleProtocol)

    def test_has_reinitialize_proxy_method(self) -> None:
        """CONTRACT: ClientLifecycleProtocol MUST have reinitialize_proxy method."""
        assert "reinitialize_proxy" in dir(ClientLifecycleProtocol)

    def test_has_stop_method(self) -> None:
        """CONTRACT: ClientLifecycleProtocol MUST have stop method."""
        assert "stop" in dir(ClientLifecycleProtocol)


# =============================================================================
# SECTION 5: DeviceDiscoveryOperationsProtocol Contract
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
# SECTION 6: ValueOperationsProtocol Contract
# =============================================================================


class TestValueOperationsProtocolContract:
    """
    Contract: ValueOperationsProtocol must provide value read/write operations.

    These are the core methods for reading and writing device parameter values.
    """

    def test_get_value_signature_has_channel_address(self) -> None:
        """CONTRACT: get_value MUST accept channel_address parameter."""
        sig = inspect.signature(ValueOperationsProtocol.get_value)
        assert "channel_address" in sig.parameters

    def test_has_get_value_method(self) -> None:
        """CONTRACT: ValueOperationsProtocol MUST have get_value method."""
        assert "get_value" in dir(ValueOperationsProtocol)

    def test_has_report_value_usage_method(self) -> None:
        """CONTRACT: ValueOperationsProtocol MUST have report_value_usage method."""
        assert "report_value_usage" in dir(ValueOperationsProtocol)

    def test_has_set_value_method(self) -> None:
        """CONTRACT: ValueOperationsProtocol MUST have set_value method."""
        assert "set_value" in dir(ValueOperationsProtocol)

    def test_set_value_signature_has_channel_address(self) -> None:
        """CONTRACT: set_value MUST accept channel_address parameter."""
        sig = inspect.signature(ValueOperationsProtocol.set_value)
        assert "channel_address" in sig.parameters

    def test_set_value_signature_has_parameter(self) -> None:
        """CONTRACT: set_value MUST accept parameter parameter."""
        sig = inspect.signature(ValueOperationsProtocol.set_value)
        assert "parameter" in sig.parameters

    def test_set_value_signature_has_value(self) -> None:
        """CONTRACT: set_value MUST accept value parameter."""
        sig = inspect.signature(ValueOperationsProtocol.set_value)
        assert "value" in sig.parameters


# =============================================================================
# SECTION 7: ParamsetOperationsProtocol Contract
# =============================================================================


class TestParamsetOperationsProtocolContract:
    """
    Contract: ParamsetOperationsProtocol must provide paramset operations.

    These methods are essential for reading and writing paramsets.
    """

    def test_has_fetch_paramset_description_method(self) -> None:
        """CONTRACT: ParamsetOperationsProtocol MUST have fetch_paramset_description method."""
        assert "fetch_paramset_description" in dir(ParamsetOperationsProtocol)

    def test_has_fetch_paramset_descriptions_method(self) -> None:
        """CONTRACT: ParamsetOperationsProtocol MUST have fetch_paramset_descriptions method."""
        assert "fetch_paramset_descriptions" in dir(ParamsetOperationsProtocol)

    def test_has_get_all_paramset_descriptions_method(self) -> None:
        """CONTRACT: ParamsetOperationsProtocol MUST have get_all_paramset_descriptions method."""
        assert "get_all_paramset_descriptions" in dir(ParamsetOperationsProtocol)

    def test_has_get_paramset_descriptions_method(self) -> None:
        """CONTRACT: ParamsetOperationsProtocol MUST have get_paramset_descriptions method."""
        assert "get_paramset_descriptions" in dir(ParamsetOperationsProtocol)

    def test_has_get_paramset_method(self) -> None:
        """CONTRACT: ParamsetOperationsProtocol MUST have get_paramset method."""
        assert "get_paramset" in dir(ParamsetOperationsProtocol)

    def test_has_put_paramset_method(self) -> None:
        """CONTRACT: ParamsetOperationsProtocol MUST have put_paramset method."""
        assert "put_paramset" in dir(ParamsetOperationsProtocol)

    def test_has_update_paramset_descriptions_method(self) -> None:
        """CONTRACT: ParamsetOperationsProtocol MUST have update_paramset_descriptions method."""
        assert "update_paramset_descriptions" in dir(ParamsetOperationsProtocol)


# =============================================================================
# SECTION 8: LinkOperationsProtocol Contract
# =============================================================================


class TestLinkOperationsProtocolContract:
    """
    Contract: LinkOperationsProtocol must provide device linking operations.

    These methods are essential for creating and managing direct device links.
    """

    def test_has_add_link_method(self) -> None:
        """CONTRACT: LinkOperationsProtocol MUST have add_link method."""
        assert "add_link" in dir(LinkOperationsProtocol)

    def test_has_get_link_peers_method(self) -> None:
        """CONTRACT: LinkOperationsProtocol MUST have get_link_peers method."""
        assert "get_link_peers" in dir(LinkOperationsProtocol)

    def test_has_get_links_method(self) -> None:
        """CONTRACT: LinkOperationsProtocol MUST have get_links method."""
        assert "get_links" in dir(LinkOperationsProtocol)

    def test_has_remove_link_method(self) -> None:
        """CONTRACT: LinkOperationsProtocol MUST have remove_link method."""
        assert "remove_link" in dir(LinkOperationsProtocol)


# =============================================================================
# SECTION 9: FirmwareOperationsProtocol Contract
# =============================================================================


class TestFirmwareOperationsProtocolContract:
    """
    Contract: FirmwareOperationsProtocol must provide firmware update operations.

    These methods are essential for device and system firmware updates.
    """

    def test_has_trigger_firmware_update_method(self) -> None:
        """CONTRACT: FirmwareOperationsProtocol MUST have trigger_firmware_update method."""
        assert "trigger_firmware_update" in dir(FirmwareOperationsProtocol)

    def test_has_update_device_firmware_method(self) -> None:
        """CONTRACT: FirmwareOperationsProtocol MUST have update_device_firmware method."""
        assert "update_device_firmware" in dir(FirmwareOperationsProtocol)


# =============================================================================
# SECTION 10: SystemVariableOperationsProtocol Contract
# =============================================================================


class TestSystemVariableOperationsProtocolContract:
    """
    Contract: SystemVariableOperationsProtocol must provide system variable operations.

    These methods are essential for managing CCU system variables.
    """

    def test_has_delete_system_variable_method(self) -> None:
        """CONTRACT: SystemVariableOperationsProtocol MUST have delete_system_variable method."""
        assert "delete_system_variable" in dir(SystemVariableOperationsProtocol)

    def test_has_get_all_system_variables_method(self) -> None:
        """CONTRACT: SystemVariableOperationsProtocol MUST have get_all_system_variables method."""
        assert "get_all_system_variables" in dir(SystemVariableOperationsProtocol)

    def test_has_get_system_variable_method(self) -> None:
        """CONTRACT: SystemVariableOperationsProtocol MUST have get_system_variable method."""
        assert "get_system_variable" in dir(SystemVariableOperationsProtocol)

    def test_has_set_system_variable_method(self) -> None:
        """CONTRACT: SystemVariableOperationsProtocol MUST have set_system_variable method."""
        assert "set_system_variable" in dir(SystemVariableOperationsProtocol)


# =============================================================================
# SECTION 11: ProgramOperationsProtocol Contract
# =============================================================================


class TestProgramOperationsProtocolContract:
    """
    Contract: ProgramOperationsProtocol must provide program operations.

    These methods are essential for managing CCU programs.
    """

    def test_has_execute_program_method(self) -> None:
        """CONTRACT: ProgramOperationsProtocol MUST have execute_program method."""
        assert "execute_program" in dir(ProgramOperationsProtocol)

    def test_has_get_all_programs_method(self) -> None:
        """CONTRACT: ProgramOperationsProtocol MUST have get_all_programs method."""
        assert "get_all_programs" in dir(ProgramOperationsProtocol)

    def test_has_has_program_ids_method(self) -> None:
        """CONTRACT: ProgramOperationsProtocol MUST have has_program_ids method."""
        assert "has_program_ids" in dir(ProgramOperationsProtocol)

    def test_has_set_program_state_method(self) -> None:
        """CONTRACT: ProgramOperationsProtocol MUST have set_program_state method."""
        assert "set_program_state" in dir(ProgramOperationsProtocol)


# =============================================================================
# SECTION 12: BackupOperationsProtocol Contract
# =============================================================================


class TestBackupOperationsProtocolContract:
    """
    Contract: BackupOperationsProtocol must provide backup operations.

    These methods are essential for CCU backup and restore functionality.
    """

    def test_has_create_backup_and_download_method(self) -> None:
        """CONTRACT: BackupOperationsProtocol MUST have create_backup_and_download method."""
        assert "create_backup_and_download" in dir(BackupOperationsProtocol)


# =============================================================================
# SECTION 13: MetadataOperationsProtocol Contract
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

    def test_has_get_metadata_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_metadata method."""
        assert "get_metadata" in dir(MetadataOperationsProtocol)

    def test_has_get_rega_id_by_address_method(self) -> None:
        """CONTRACT: MetadataOperationsProtocol MUST have get_rega_id_by_address method."""
        assert "get_rega_id_by_address" in dir(MetadataOperationsProtocol)

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
# SECTION 14: ClientSupportProtocol Contract
# =============================================================================


class TestClientSupportProtocolContract:
    """
    Contract: ClientSupportProtocol must provide support utilities.

    These properties and methods provide access to client caches and utilities.
    """

    def test_has_get_product_group_method(self) -> None:
        """CONTRACT: ClientSupportProtocol MUST have get_product_group method."""
        assert "get_product_group" in dir(ClientSupportProtocol)

    def test_has_get_virtual_remote_method(self) -> None:
        """CONTRACT: ClientSupportProtocol MUST have get_virtual_remote method."""
        assert "get_virtual_remote" in dir(ClientSupportProtocol)

    def test_has_last_value_send_tracker_property(self) -> None:
        """CONTRACT: ClientSupportProtocol MUST have last_value_send_tracker property."""
        assert "last_value_send_tracker" in dir(ClientSupportProtocol)

    def test_has_ping_pong_tracker_property(self) -> None:
        """CONTRACT: ClientSupportProtocol MUST have ping_pong_tracker property."""
        assert "ping_pong_tracker" in dir(ClientSupportProtocol)


# =============================================================================
# SECTION 15: Combined Protocol Contracts
# =============================================================================


class TestValueAndParamsetOperationsProtocolContract:
    """Contract tests for ValueAndParamsetOperationsProtocol."""

    def test_includes_get_paramset(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST include get_paramset."""
        assert "get_paramset" in dir(ValueAndParamsetOperationsProtocol)

    def test_includes_get_value(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST include get_value."""
        assert "get_value" in dir(ValueAndParamsetOperationsProtocol)

    def test_includes_put_paramset(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST include put_paramset."""
        assert "put_paramset" in dir(ValueAndParamsetOperationsProtocol)

    def test_includes_set_value(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST include set_value."""
        assert "set_value" in dir(ValueAndParamsetOperationsProtocol)

    def test_is_protocol(self) -> None:
        """CONTRACT: ValueAndParamsetOperationsProtocol MUST be a Protocol."""
        assert hasattr(ValueAndParamsetOperationsProtocol, "__protocol_attrs__")


class TestMaintenanceOperationsProtocolContract:
    """Contract tests for MaintenanceOperationsProtocol."""

    def test_includes_add_link(self) -> None:
        """CONTRACT: MaintenanceOperationsProtocol MUST include add_link."""
        assert "add_link" in dir(MaintenanceOperationsProtocol)

    def test_includes_create_backup_and_download(self) -> None:
        """CONTRACT: MaintenanceOperationsProtocol MUST include create_backup_and_download."""
        assert "create_backup_and_download" in dir(MaintenanceOperationsProtocol)

    def test_includes_update_device_firmware(self) -> None:
        """CONTRACT: MaintenanceOperationsProtocol MUST include update_device_firmware."""
        assert "update_device_firmware" in dir(MaintenanceOperationsProtocol)

    def test_is_protocol(self) -> None:
        """CONTRACT: MaintenanceOperationsProtocol MUST be a Protocol."""
        assert hasattr(MaintenanceOperationsProtocol, "__protocol_attrs__")


class TestSystemManagementOperationsProtocolContract:
    """Contract tests for SystemManagementOperationsProtocol."""

    def test_includes_execute_program(self) -> None:
        """CONTRACT: SystemManagementOperationsProtocol MUST include execute_program."""
        assert "execute_program" in dir(SystemManagementOperationsProtocol)

    def test_includes_get_system_variable(self) -> None:
        """CONTRACT: SystemManagementOperationsProtocol MUST include get_system_variable."""
        assert "get_system_variable" in dir(SystemManagementOperationsProtocol)

    def test_is_protocol(self) -> None:
        """CONTRACT: SystemManagementOperationsProtocol MUST be a Protocol."""
        assert hasattr(SystemManagementOperationsProtocol, "__protocol_attrs__")


# =============================================================================
# SECTION 16: ClientProviderProtocol Contract
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
# SECTION 17: PrimaryClientProviderProtocol Contract
# =============================================================================


class TestPrimaryClientProviderProtocolContractDetailed:
    """Contract tests for PrimaryClientProviderProtocol."""

    def test_has_primary_client_property(self) -> None:
        """CONTRACT: PrimaryClientProviderProtocol MUST have primary_client property."""
        assert "primary_client" in dir(PrimaryClientProviderProtocol)


# =============================================================================
# SECTION 18: ClientProtocol Full API Contract
# =============================================================================


class TestClientProtocolFullApiContract:
    """
    Contract: ClientProtocol MUST expose all sub-protocol methods.

    This comprehensive test ensures the composite protocol provides
    access to all expected functionality.
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
            # ClientLifecycleProtocol
            "init_client",
            "stop",
            "initialize_proxy",
            "deinitialize_proxy",
            # DeviceDiscoveryOperationsProtocol
            "list_devices",
            "get_device_description",
            # ValueOperationsProtocol
            "get_value",
            "set_value",
            # ParamsetOperationsProtocol
            "get_paramset",
            "put_paramset",
            # LinkOperationsProtocol
            "add_link",
            "remove_link",
            # FirmwareOperationsProtocol
            "update_device_firmware",
            # SystemVariableOperationsProtocol
            "get_system_variable",
            "set_system_variable",
            # ProgramOperationsProtocol
            "execute_program",
            "get_all_programs",
            # BackupOperationsProtocol
            "create_backup_and_download",
            # MetadataOperationsProtocol
            "get_all_rooms",
            "get_all_functions",
            "get_install_mode",
            "set_install_mode",
            # ClientProtocol specific
            "capabilities",
        ],
    )
    def test_clientprotocol_has_method(self, method_name: str) -> None:
        """CONTRACT: ClientProtocol MUST have all sub-protocol methods."""
        assert method_name in dir(ClientProtocol), f"ClientProtocol missing {method_name}"
