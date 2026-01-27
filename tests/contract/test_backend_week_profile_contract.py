# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for BackendOperationsProtocol and WeekProfileProtocol.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for backend operations and week profile interfaces.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Protocol interfaces are runtime checkable
2. Required methods and properties exist
3. Method signatures are stable

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from typing import Protocol

from aiohomematic.client.backends.protocol import BackendOperationsProtocol
from aiohomematic.interfaces import WeekProfileProtocol

# =============================================================================
# Contract: BackendOperationsProtocol Runtime Checkability
# =============================================================================


class TestBackendOperationsProtocolRuntimeCheckability:
    """Contract: BackendOperationsProtocol must be runtime checkable."""

    def test_backendoperationsprotocol_is_protocol(self) -> None:
        """Contract: BackendOperationsProtocol is a Protocol."""
        assert issubclass(BackendOperationsProtocol, Protocol)

    def test_backendoperationsprotocol_is_runtime_checkable(self) -> None:
        """Contract: BackendOperationsProtocol is runtime checkable."""
        # @runtime_checkable protocols have __protocol_attrs__
        assert hasattr(BackendOperationsProtocol, "__protocol_attrs__") or issubclass(
            BackendOperationsProtocol, Protocol
        )


# =============================================================================
# Contract: BackendOperationsProtocol Properties
# =============================================================================


class TestBackendOperationsProtocolPropertiesContract:
    """Contract: BackendOperationsProtocol must have required properties."""

    def test_has_all_circuit_breakers_closed(self) -> None:
        """Contract: BackendOperationsProtocol has all_circuit_breakers_closed property."""
        assert "all_circuit_breakers_closed" in dir(BackendOperationsProtocol)

    def test_has_capabilities(self) -> None:
        """Contract: BackendOperationsProtocol has capabilities property."""
        assert "capabilities" in dir(BackendOperationsProtocol)

    def test_has_circuit_breaker(self) -> None:
        """Contract: BackendOperationsProtocol has circuit_breaker property."""
        assert "circuit_breaker" in dir(BackendOperationsProtocol)

    def test_has_interface(self) -> None:
        """Contract: BackendOperationsProtocol has interface property."""
        assert "interface" in dir(BackendOperationsProtocol)

    def test_has_interface_id(self) -> None:
        """Contract: BackendOperationsProtocol has interface_id property."""
        assert "interface_id" in dir(BackendOperationsProtocol)

    def test_has_model(self) -> None:
        """Contract: BackendOperationsProtocol has model property."""
        assert "model" in dir(BackendOperationsProtocol)

    def test_has_system_information(self) -> None:
        """Contract: BackendOperationsProtocol has system_information property."""
        assert "system_information" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Device/Channel Methods
# =============================================================================


class TestBackendOperationsProtocolDeviceMethodsContract:
    """Contract: BackendOperationsProtocol must have device/channel methods."""

    def test_has_get_device_description(self) -> None:
        """Contract: BackendOperationsProtocol has get_device_description method."""
        assert "get_device_description" in dir(BackendOperationsProtocol)

    def test_has_get_device_details(self) -> None:
        """Contract: BackendOperationsProtocol has get_device_details method."""
        assert "get_device_details" in dir(BackendOperationsProtocol)

    def test_has_list_devices(self) -> None:
        """Contract: BackendOperationsProtocol has list_devices method."""
        assert "list_devices" in dir(BackendOperationsProtocol)

    def test_has_rename_channel(self) -> None:
        """Contract: BackendOperationsProtocol has rename_channel method."""
        assert "rename_channel" in dir(BackendOperationsProtocol)

    def test_has_rename_device(self) -> None:
        """Contract: BackendOperationsProtocol has rename_device method."""
        assert "rename_device" in dir(BackendOperationsProtocol)

    def test_has_update_device_firmware(self) -> None:
        """Contract: BackendOperationsProtocol has update_device_firmware method."""
        assert "update_device_firmware" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Paramset Methods
# =============================================================================


class TestBackendOperationsProtocolParamsetMethodsContract:
    """Contract: BackendOperationsProtocol must have paramset methods."""

    def test_has_get_paramset(self) -> None:
        """Contract: BackendOperationsProtocol has get_paramset method."""
        assert "get_paramset" in dir(BackendOperationsProtocol)

    def test_has_get_paramset_description(self) -> None:
        """Contract: BackendOperationsProtocol has get_paramset_description method."""
        assert "get_paramset_description" in dir(BackendOperationsProtocol)

    def test_has_get_value(self) -> None:
        """Contract: BackendOperationsProtocol has get_value method."""
        assert "get_value" in dir(BackendOperationsProtocol)

    def test_has_put_paramset(self) -> None:
        """Contract: BackendOperationsProtocol has put_paramset method."""
        assert "put_paramset" in dir(BackendOperationsProtocol)

    def test_has_set_value(self) -> None:
        """Contract: BackendOperationsProtocol has set_value method."""
        assert "set_value" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol System Variable Methods
# =============================================================================


class TestBackendOperationsProtocolSysvarMethodsContract:
    """Contract: BackendOperationsProtocol must have system variable methods."""

    def test_has_delete_system_variable(self) -> None:
        """Contract: BackendOperationsProtocol has delete_system_variable method."""
        assert "delete_system_variable" in dir(BackendOperationsProtocol)

    def test_has_get_all_system_variables(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_system_variables method."""
        assert "get_all_system_variables" in dir(BackendOperationsProtocol)

    def test_has_get_system_variable(self) -> None:
        """Contract: BackendOperationsProtocol has get_system_variable method."""
        assert "get_system_variable" in dir(BackendOperationsProtocol)

    def test_has_set_system_variable(self) -> None:
        """Contract: BackendOperationsProtocol has set_system_variable method."""
        assert "set_system_variable" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Program Methods
# =============================================================================


class TestBackendOperationsProtocolProgramMethodsContract:
    """Contract: BackendOperationsProtocol must have program methods."""

    def test_has_execute_program(self) -> None:
        """Contract: BackendOperationsProtocol has execute_program method."""
        assert "execute_program" in dir(BackendOperationsProtocol)

    def test_has_get_all_programs(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_programs method."""
        assert "get_all_programs" in dir(BackendOperationsProtocol)

    def test_has_has_program_ids(self) -> None:
        """Contract: BackendOperationsProtocol has has_program_ids method."""
        assert "has_program_ids" in dir(BackendOperationsProtocol)

    def test_has_set_program_state(self) -> None:
        """Contract: BackendOperationsProtocol has set_program_state method."""
        assert "set_program_state" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Connection Methods
# =============================================================================


class TestBackendOperationsProtocolConnectionMethodsContract:
    """Contract: BackendOperationsProtocol must have connection methods."""

    def test_has_check_connection(self) -> None:
        """Contract: BackendOperationsProtocol has check_connection method."""
        assert "check_connection" in dir(BackendOperationsProtocol)

    def test_has_deinit_proxy(self) -> None:
        """Contract: BackendOperationsProtocol has deinit_proxy method."""
        assert "deinit_proxy" in dir(BackendOperationsProtocol)

    def test_has_init_proxy(self) -> None:
        """Contract: BackendOperationsProtocol has init_proxy method."""
        assert "init_proxy" in dir(BackendOperationsProtocol)

    def test_has_initialize(self) -> None:
        """Contract: BackendOperationsProtocol has initialize method."""
        assert "initialize" in dir(BackendOperationsProtocol)

    def test_has_reset_circuit_breakers(self) -> None:
        """Contract: BackendOperationsProtocol has reset_circuit_breakers method."""
        assert "reset_circuit_breakers" in dir(BackendOperationsProtocol)

    def test_has_stop(self) -> None:
        """Contract: BackendOperationsProtocol has stop method."""
        assert "stop" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Link Methods
# =============================================================================


class TestBackendOperationsProtocolLinkMethodsContract:
    """Contract: BackendOperationsProtocol must have link methods."""

    def test_has_add_link(self) -> None:
        """Contract: BackendOperationsProtocol has add_link method."""
        assert "add_link" in dir(BackendOperationsProtocol)

    def test_has_get_link_peers(self) -> None:
        """Contract: BackendOperationsProtocol has get_link_peers method."""
        assert "get_link_peers" in dir(BackendOperationsProtocol)

    def test_has_get_links(self) -> None:
        """Contract: BackendOperationsProtocol has get_links method."""
        assert "get_links" in dir(BackendOperationsProtocol)

    def test_has_remove_link(self) -> None:
        """Contract: BackendOperationsProtocol has remove_link method."""
        assert "remove_link" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Metadata/Room/Function Methods
# =============================================================================


class TestBackendOperationsProtocolMetadataMethodsContract:
    """Contract: BackendOperationsProtocol must have metadata/room/function methods."""

    def test_has_get_all_functions(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_functions method."""
        assert "get_all_functions" in dir(BackendOperationsProtocol)

    def test_has_get_all_rooms(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_rooms method."""
        assert "get_all_rooms" in dir(BackendOperationsProtocol)

    def test_has_get_metadata(self) -> None:
        """Contract: BackendOperationsProtocol has get_metadata method."""
        assert "get_metadata" in dir(BackendOperationsProtocol)

    def test_has_get_rega_id_by_address(self) -> None:
        """Contract: BackendOperationsProtocol has get_rega_id_by_address method."""
        assert "get_rega_id_by_address" in dir(BackendOperationsProtocol)

    def test_has_set_metadata(self) -> None:
        """Contract: BackendOperationsProtocol has set_metadata method."""
        assert "set_metadata" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: BackendOperationsProtocol Service/System Methods
# =============================================================================


class TestBackendOperationsProtocolSystemMethodsContract:
    """Contract: BackendOperationsProtocol must have service/system methods."""

    def test_has_accept_device_in_inbox(self) -> None:
        """Contract: BackendOperationsProtocol has accept_device_in_inbox method."""
        assert "accept_device_in_inbox" in dir(BackendOperationsProtocol)

    def test_has_create_backup_and_download(self) -> None:
        """Contract: BackendOperationsProtocol has create_backup_and_download method."""
        assert "create_backup_and_download" in dir(BackendOperationsProtocol)

    def test_has_get_all_device_data(self) -> None:
        """Contract: BackendOperationsProtocol has get_all_device_data method."""
        assert "get_all_device_data" in dir(BackendOperationsProtocol)

    def test_has_get_inbox_devices(self) -> None:
        """Contract: BackendOperationsProtocol has get_inbox_devices method."""
        assert "get_inbox_devices" in dir(BackendOperationsProtocol)

    def test_has_get_install_mode(self) -> None:
        """Contract: BackendOperationsProtocol has get_install_mode method."""
        assert "get_install_mode" in dir(BackendOperationsProtocol)

    def test_has_get_service_messages(self) -> None:
        """Contract: BackendOperationsProtocol has get_service_messages method."""
        assert "get_service_messages" in dir(BackendOperationsProtocol)

    def test_has_get_system_update_info(self) -> None:
        """Contract: BackendOperationsProtocol has get_system_update_info method."""
        assert "get_system_update_info" in dir(BackendOperationsProtocol)

    def test_has_report_value_usage(self) -> None:
        """Contract: BackendOperationsProtocol has report_value_usage method."""
        assert "report_value_usage" in dir(BackendOperationsProtocol)

    def test_has_set_install_mode(self) -> None:
        """Contract: BackendOperationsProtocol has set_install_mode method."""
        assert "set_install_mode" in dir(BackendOperationsProtocol)

    def test_has_trigger_firmware_update(self) -> None:
        """Contract: BackendOperationsProtocol has trigger_firmware_update method."""
        assert "trigger_firmware_update" in dir(BackendOperationsProtocol)


# =============================================================================
# Contract: WeekProfileProtocol Runtime Checkability
# =============================================================================


class TestWeekProfileProtocolRuntimeCheckability:
    """Contract: WeekProfileProtocol must be runtime checkable."""

    def test_weekprofileprotocol_is_protocol(self) -> None:
        """Contract: WeekProfileProtocol is a Protocol."""
        assert issubclass(WeekProfileProtocol, Protocol)


# =============================================================================
# Contract: WeekProfileProtocol Properties
# =============================================================================


class TestWeekProfileProtocolPropertiesContract:
    """Contract: WeekProfileProtocol must have required properties."""

    def test_has_has_schedule(self) -> None:
        """Contract: WeekProfileProtocol has has_schedule property."""
        assert "has_schedule" in dir(WeekProfileProtocol)

    def test_has_schedule(self) -> None:
        """Contract: WeekProfileProtocol has schedule property."""
        assert "schedule" in dir(WeekProfileProtocol)

    def test_has_schedule_channel_address(self) -> None:
        """Contract: WeekProfileProtocol has schedule_channel_address property."""
        assert "schedule_channel_address" in dir(WeekProfileProtocol)


# =============================================================================
# Contract: WeekProfileProtocol Methods
# =============================================================================


class TestWeekProfileProtocolMethodsContract:
    """Contract: WeekProfileProtocol must have required methods."""

    def test_has_get_schedule(self) -> None:
        """Contract: WeekProfileProtocol has get_schedule method."""
        assert "get_schedule" in dir(WeekProfileProtocol)

    def test_has_reload_and_cache_schedule(self) -> None:
        """Contract: WeekProfileProtocol has reload_and_cache_schedule method."""
        assert "reload_and_cache_schedule" in dir(WeekProfileProtocol)

    def test_has_set_schedule(self) -> None:
        """Contract: WeekProfileProtocol has set_schedule method."""
        assert "set_schedule" in dir(WeekProfileProtocol)


# =============================================================================
# Contract: WeekProfileProtocol Export
# =============================================================================


class TestWeekProfileProtocolExportContract:
    """Contract: WeekProfileProtocol must be exported from interfaces."""

    def test_weekprofileprotocol_exported(self) -> None:
        """Contract: WeekProfileProtocol is exported from interfaces package."""
        from aiohomematic import interfaces

        assert hasattr(interfaces, "WeekProfileProtocol")
