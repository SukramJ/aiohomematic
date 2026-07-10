# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for DeviceProtocol and ChannelProtocol interfaces.

These tests verify that the protocol interfaces maintain their structure
and signatures, ensuring API stability for consumers.

Note on inlined sub-protocols: `ChannelProtocol` and `DeviceProtocol` are flat composites.
Former ISP slices without a consumer independent of the composite (`ChannelIdentityProtocol`,
`ChannelDataPointAccessProtocol`, `ChannelGroupingProtocol`, `ChannelMetadataProtocol`,
`ChannelLinkManagementProtocol`, `ChannelLifecycleProtocol`, `ChannelMetadataAndGroupingProtocol`,
`ChannelManagementProtocol`, `DeviceAvailabilityProtocol`, `DeviceFirmwareProtocol`,
`DeviceLinkManagementProtocol`, `DeviceGroupManagementProtocol`, `DeviceConfigurationProtocol`,
`DeviceWeekProfileProtocol`, `DeviceProvidersProtocol`, `DeviceLifecycleProtocol`,
`DeviceStateProtocol`, `DeviceOperationsProtocol`) have been inlined directly into the composite
(see `aiohomematic/interfaces/model.py`). Their stability coverage now lives in
`TestDeviceProtocolFullApiContract` / `TestChannelProtocolFullApiContract` below.
`DeviceIdentityProtocol` and `DeviceChannelAccessProtocol` remain separate protocols because
`DeviceRemovalInfoProtocol` depends on them independently of `DeviceProtocol`.
"""

import inspect

import pytest

from aiohomematic.interfaces import (
    ChannelProtocol,
    # Device protocols (public)
    DeviceChannelAccessProtocol,
    DeviceIdentityProtocol,
    DeviceProtocol,
)
from aiohomematic.interfaces.model import DeviceRemovalInfoProtocol

# =============================================================================
# DeviceIdentityProtocol Contract Tests
# =============================================================================


class TestDeviceIdentityProtocolContract:
    """Contract tests for DeviceIdentityProtocol."""

    def test_has_address_property(self) -> None:
        """Verify DeviceIdentityProtocol has address property."""
        assert hasattr(DeviceIdentityProtocol, "address")

    def test_has_identifier_property(self) -> None:
        """Verify DeviceIdentityProtocol has identifier property."""
        assert hasattr(DeviceIdentityProtocol, "identifier")

    def test_has_interface_id_property(self) -> None:
        """Verify DeviceIdentityProtocol has interface_id property."""
        assert hasattr(DeviceIdentityProtocol, "interface_id")

    def test_has_interface_property(self) -> None:
        """Verify DeviceIdentityProtocol has interface property."""
        assert hasattr(DeviceIdentityProtocol, "interface")

    def test_has_manufacturer_property(self) -> None:
        """Verify DeviceIdentityProtocol has manufacturer property."""
        assert hasattr(DeviceIdentityProtocol, "manufacturer")

    def test_has_model_property(self) -> None:
        """Verify DeviceIdentityProtocol has model property."""
        assert hasattr(DeviceIdentityProtocol, "model")

    def test_has_name_property(self) -> None:
        """Verify DeviceIdentityProtocol has name property."""
        assert hasattr(DeviceIdentityProtocol, "name")

    def test_has_sub_model_property(self) -> None:
        """Verify DeviceIdentityProtocol has sub_model property."""
        assert hasattr(DeviceIdentityProtocol, "sub_model")


# =============================================================================
# DeviceChannelAccessProtocol Contract Tests
# =============================================================================


class TestDeviceChannelAccessProtocolContract:
    """Contract tests for DeviceChannelAccessProtocol."""

    def test_has_channels_property(self) -> None:
        """Verify DeviceChannelAccessProtocol has channels property."""
        assert hasattr(DeviceChannelAccessProtocol, "channels")

    def test_has_data_point_paths_property(self) -> None:
        """Verify DeviceChannelAccessProtocol has data_point_paths property."""
        assert hasattr(DeviceChannelAccessProtocol, "data_point_paths")

    def test_has_generic_data_points_property(self) -> None:
        """Verify DeviceChannelAccessProtocol has generic_data_points property."""
        assert hasattr(DeviceChannelAccessProtocol, "generic_data_points")

    def test_has_generic_events_property(self) -> None:
        """Verify DeviceChannelAccessProtocol has generic_events property."""
        assert hasattr(DeviceChannelAccessProtocol, "generic_events")

    def test_has_get_channel_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_channel method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_channel")
        assert callable(DeviceChannelAccessProtocol.get_channel)

    def test_has_get_custom_data_point_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_custom_data_point method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_custom_data_point")
        assert callable(DeviceChannelAccessProtocol.get_custom_data_point)

    def test_has_get_data_points_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_data_points method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_data_points")
        assert callable(DeviceChannelAccessProtocol.get_data_points)

    def test_has_get_events_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_events method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_events")
        assert callable(DeviceChannelAccessProtocol.get_events)

    def test_has_get_generic_data_point_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_generic_data_point method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_generic_data_point")
        assert callable(DeviceChannelAccessProtocol.get_generic_data_point)

    def test_has_get_generic_event_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_generic_event method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_generic_event")
        assert callable(DeviceChannelAccessProtocol.get_generic_event)

    def test_has_get_readable_data_points_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_readable_data_points method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_readable_data_points")
        assert callable(DeviceChannelAccessProtocol.get_readable_data_points)

    def test_has_identify_channel_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has identify_channel method."""
        assert hasattr(DeviceChannelAccessProtocol, "identify_channel")
        assert callable(DeviceChannelAccessProtocol.identify_channel)


# =============================================================================
# DeviceRemovalInfoProtocol Contract Tests
# =============================================================================


class TestDeviceRemovalInfoProtocolContract:
    """Contract tests for DeviceRemovalInfoProtocol."""

    def test_includes_channel_access(self) -> None:
        """Verify DeviceRemovalInfoProtocol includes channel access members."""
        assert hasattr(DeviceRemovalInfoProtocol, "channels")
        assert hasattr(DeviceRemovalInfoProtocol, "get_channel")

    def test_includes_identity(self) -> None:
        """Verify DeviceRemovalInfoProtocol includes identity members."""
        assert hasattr(DeviceRemovalInfoProtocol, "address")
        assert hasattr(DeviceRemovalInfoProtocol, "interface_id")

    def test_is_runtime_checkable(self) -> None:
        """Verify DeviceRemovalInfoProtocol is runtime_checkable."""
        assert hasattr(DeviceRemovalInfoProtocol, "__subclasshook__")


# =============================================================================
# DeviceProtocol Composite Contract Tests
# =============================================================================


class TestDeviceProtocolCompositeContract:
    """Contract tests for DeviceProtocol composite interface."""

    def test_includes_all_channel_access_members(self) -> None:
        """Verify DeviceProtocol includes all channel access members."""
        assert hasattr(DeviceProtocol, "channels")
        assert hasattr(DeviceProtocol, "get_channel")
        assert hasattr(DeviceProtocol, "get_data_points")
        assert hasattr(DeviceProtocol, "generic_data_points")

    def test_includes_all_configuration_members(self) -> None:
        """Verify DeviceProtocol includes all configuration members."""
        assert hasattr(DeviceProtocol, "product_group")
        assert hasattr(DeviceProtocol, "ise_id")
        assert hasattr(DeviceProtocol, "room")

    def test_includes_all_identity_members(self) -> None:
        """Verify DeviceProtocol includes all identity members."""
        assert hasattr(DeviceProtocol, "address")
        assert hasattr(DeviceProtocol, "identifier")
        assert hasattr(DeviceProtocol, "interface")
        assert hasattr(DeviceProtocol, "interface_id")
        assert hasattr(DeviceProtocol, "manufacturer")
        assert hasattr(DeviceProtocol, "model")
        assert hasattr(DeviceProtocol, "name")
        assert hasattr(DeviceProtocol, "sub_model")

    def test_includes_all_operations_members(self) -> None:
        """Verify DeviceProtocol includes all operations members."""
        assert hasattr(DeviceProtocol, "create_central_links")
        assert hasattr(DeviceProtocol, "add_channel_to_group")
        assert hasattr(DeviceProtocol, "finalize_init")

    def test_includes_all_providers_members(self) -> None:
        """Verify DeviceProtocol includes all providers members."""
        assert hasattr(DeviceProtocol, "central_info")
        assert hasattr(DeviceProtocol, "client")
        assert hasattr(DeviceProtocol, "config_provider")

    def test_includes_all_state_members(self) -> None:
        """Verify DeviceProtocol includes all state members."""
        assert hasattr(DeviceProtocol, "available")
        assert hasattr(DeviceProtocol, "firmware")
        assert hasattr(DeviceProtocol, "has_week_profile")

    def test_is_protocol(self) -> None:
        """Verify DeviceProtocol is a Protocol."""
        assert hasattr(DeviceProtocol, "__protocol_attrs__") or hasattr(DeviceProtocol, "_is_protocol")

    def test_is_runtime_checkable(self) -> None:
        """Verify DeviceProtocol is runtime_checkable."""
        assert hasattr(DeviceProtocol, "__subclasshook__")


# =============================================================================
# ChannelProtocol Composite Contract Tests
# =============================================================================


class TestChannelProtocolCompositeContract:
    """Contract tests for ChannelProtocol composite interface."""

    def test_includes_all_data_point_access_members(self) -> None:
        """Verify ChannelProtocol includes all data point access members."""
        assert hasattr(ChannelProtocol, "calculated_data_points")
        assert hasattr(ChannelProtocol, "custom_data_point")
        assert hasattr(ChannelProtocol, "generic_data_points")
        assert hasattr(ChannelProtocol, "get_data_points")
        assert hasattr(ChannelProtocol, "add_data_point")

    def test_includes_all_grouping_members(self) -> None:
        """Verify ChannelProtocol includes all grouping members."""
        assert hasattr(ChannelProtocol, "group_master")
        assert hasattr(ChannelProtocol, "group_no")
        assert hasattr(ChannelProtocol, "is_group_master")
        assert hasattr(ChannelProtocol, "link_peer_channels")

    def test_includes_all_identity_members(self) -> None:
        """Verify ChannelProtocol includes all identity members."""
        assert hasattr(ChannelProtocol, "address")
        assert hasattr(ChannelProtocol, "full_name")
        assert hasattr(ChannelProtocol, "name")
        assert hasattr(ChannelProtocol, "no")
        assert hasattr(ChannelProtocol, "ise_id")
        assert hasattr(ChannelProtocol, "type_name")
        assert hasattr(ChannelProtocol, "unique_id")

    def test_includes_all_management_members(self) -> None:
        """Verify ChannelProtocol includes all management members."""
        assert hasattr(ChannelProtocol, "create_central_link")
        assert hasattr(ChannelProtocol, "remove_central_link")
        assert hasattr(ChannelProtocol, "finalize_init")
        assert hasattr(ChannelProtocol, "remove")

    def test_includes_all_metadata_members(self) -> None:
        """Verify ChannelProtocol includes all metadata members."""
        assert hasattr(ChannelProtocol, "device")
        assert hasattr(ChannelProtocol, "function")
        assert hasattr(ChannelProtocol, "room")
        assert hasattr(ChannelProtocol, "paramset_descriptions")

    def test_is_protocol(self) -> None:
        """Verify ChannelProtocol is a Protocol."""
        assert hasattr(ChannelProtocol, "__protocol_attrs__") or hasattr(ChannelProtocol, "_is_protocol")

    def test_is_runtime_checkable(self) -> None:
        """Verify ChannelProtocol is runtime_checkable."""
        assert hasattr(ChannelProtocol, "__subclasshook__")


# =============================================================================
# Method Signature Contract Tests
# =============================================================================


class TestDeviceMethodSignaturesContract:
    """Contract tests for DeviceProtocol method signatures."""

    def test_get_channel_signature(self) -> None:
        """Verify get_channel method signature."""
        sig = inspect.signature(DeviceChannelAccessProtocol.get_channel)
        params = list(sig.parameters.keys())
        assert "channel_address" in params

    def test_get_custom_data_point_signature(self) -> None:
        """Verify get_custom_data_point method signature."""
        sig = inspect.signature(DeviceChannelAccessProtocol.get_custom_data_point)
        params = list(sig.parameters.keys())
        assert "channel_no" in params

    def test_get_data_points_signature(self) -> None:
        """Verify get_data_points method signature."""
        sig = inspect.signature(DeviceChannelAccessProtocol.get_data_points)
        params = list(sig.parameters.keys())
        assert "category" in params
        assert "registered" in params

    def test_set_forced_availability_signature(self) -> None:
        """Verify set_forced_availability method signature (declared directly on DeviceProtocol)."""
        sig = inspect.signature(DeviceProtocol.set_forced_availability)
        params = list(sig.parameters.keys())
        assert "forced_availability" in params

    def test_update_firmware_signature(self) -> None:
        """Verify update_firmware method signature (declared directly on DeviceProtocol)."""
        sig = inspect.signature(DeviceProtocol.update_firmware)
        params = list(sig.parameters.keys())
        assert "refresh_after_update_intervals" in params


class TestChannelMethodSignaturesContract:
    """Contract tests for ChannelProtocol method signatures."""

    def test_add_data_point_signature(self) -> None:
        """Verify add_data_point method signature (declared directly on ChannelProtocol)."""
        sig = inspect.signature(ChannelProtocol.add_data_point)
        params = list(sig.parameters.keys())
        assert "data_point" in params

    def test_get_data_points_signature(self) -> None:
        """Verify get_data_points method signature (declared directly on ChannelProtocol)."""
        sig = inspect.signature(ChannelProtocol.get_data_points)
        params = list(sig.parameters.keys())
        assert "category" in params
        assert "registered" in params

    def test_get_generic_data_point_signature(self) -> None:
        """Verify get_generic_data_point method signature (declared directly on ChannelProtocol)."""
        sig = inspect.signature(ChannelProtocol.get_generic_data_point)
        params = list(sig.parameters.keys())
        assert "parameter" in params
        assert "paramset_key" in params

    def test_has_link_target_category_signature(self) -> None:
        """Verify has_link_target_category method signature (declared directly on ChannelProtocol)."""
        sig = inspect.signature(ChannelProtocol.has_link_target_category)
        params = list(sig.parameters.keys())
        assert "category" in params


# =============================================================================
# Full API Stability Contract Tests
# =============================================================================


class TestDeviceProtocolFullApiContract:
    """Full API contract tests for DeviceProtocol."""

    @pytest.mark.parametrize(
        "member",
        [
            # Identity
            "address",
            "identifier",
            "interface",
            "interface_id",
            "manufacturer",
            "model",
            "name",
            "sub_model",
            # Channel Access
            "channels",
            "data_point_paths",
            "generic_data_points",
            "generic_events",
            "get_channel",
            "get_custom_data_point",
            "get_data_points",
            "get_events",
            "get_generic_data_point",
            "get_generic_event",
            "get_readable_data_points",
            "identify_channel",
            # Availability
            "availability",
            "available",
            "config_pending",
            "set_forced_availability",
            # Firmware
            "available_firmware",
            "firmware",
            "firmware_updatable",
            "firmware_update_state",
            "is_updatable",
            "refresh_firmware_data",
            "subscribe_to_firmware_updated",
            "update_firmware",
            # Week Profile
            "default_schedule_channel",
            "has_week_profile",
            "week_profile",
            "init_week_profile",
            # Link Management
            "link_peer_channels",
            "create_central_links",
            "remove_central_links",
            # Group Management
            "add_channel_to_group",
            "get_channel_group_no",
            "is_in_multi_channel_group",
            # Lifecycle
            "export_device_definition",
            "finalize_init",
            "on_config_changed",
            "publish_device_updated_event",
            "reload_device_config",
            "remove",
            # Configuration
            "allow_undefined_generic_data_points",
            "has_custom_data_point_definition",
            "has_sub_devices",
            "ignore_for_custom_data_point",
            "ignore_on_initial_load",
            "product_group",
            "ise_id",
            "room",
            "rooms",
            "rx_modes",
            # Providers
            "central_info",
            "channel_lookup",
            "client",
            "config_provider",
            "data_cache_provider",
            "data_point_provider",
            "device_data_refresher",
            "device_description_provider",
            "device_details_provider",
            "event_bus_provider",
            "event_publisher",
            "event_subscription_manager",
            "parameter_visibility_provider",
            "paramset_description_provider",
            "task_scheduler",
            "value_cache",
        ],
    )
    def test_deviceprotocol_has_member(self, member: str) -> None:
        """Verify DeviceProtocol has all expected members."""
        assert hasattr(DeviceProtocol, member), f"DeviceProtocol missing member: {member}"


class TestChannelProtocolFullApiContract:
    """Full API contract tests for ChannelProtocol."""

    @pytest.mark.parametrize(
        "member",
        [
            # Identity
            "address",
            "full_name",
            "name",
            "no",
            "ise_id",
            "type_name",
            "unique_id",
            # Data Point Access
            "calculated_data_points",
            "custom_data_point",
            "data_point_paths",
            "event_groups",
            "generic_data_points",
            "generic_events",
            "add_data_point",
            "get_calculated_data_point",
            "get_data_points",
            "get_events",
            "get_generic_data_point",
            "get_generic_event",
            "get_readable_data_points",
            # Grouping
            "group_master",
            "group_no",
            "is_group_master",
            "is_in_multi_group",
            "link_peer_channels",
            # Metadata
            "device",
            "function",
            "is_schedule_channel",
            "operation_mode",
            "paramset_descriptions",
            "paramset_keys",
            "room",
            "rooms",
            # Link Management
            "create_central_link",
            "has_link_target_category",
            "remove_central_link",
            "subscribe_to_link_peer_changed",
            # Lifecycle
            "finalize_init",
            "init_link_peer",
            "on_config_changed",
            "reload_channel_config",
            "remove",
        ],
    )
    def test_channelprotocol_has_member(self, member: str) -> None:
        """Verify ChannelProtocol has all expected members."""
        assert hasattr(ChannelProtocol, member), f"ChannelProtocol missing member: {member}"
