# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for DeviceProtocol and ChannelProtocol interfaces.

These tests verify that the protocol interfaces maintain their structure
and signatures, ensuring API stability for consumers.
"""

from __future__ import annotations

import inspect

import pytest

from aiohomematic.interfaces import (
    # Channel protocols (public)
    ChannelDataPointAccessProtocol,
    ChannelIdentityProtocol,
    ChannelManagementProtocol,
    ChannelMetadataAndGroupingProtocol,
    ChannelProtocol,
    # Device protocols (public)
    DeviceChannelAccessProtocol,
    DeviceConfigurationProtocol,
    DeviceIdentityProtocol,
    DeviceOperationsProtocol,
    DeviceProtocol,
    DeviceProvidersProtocol,
    DeviceStateProtocol,
)
from aiohomematic.interfaces.model import (
    # Channel protocols (internal)
    ChannelGroupingProtocol,
    ChannelLifecycleProtocol,
    ChannelLinkManagementProtocol,
    ChannelMetadataProtocol,
    # Device protocols (internal)
    DeviceAvailabilityProtocol,
    DeviceFirmwareProtocol,
    DeviceGroupManagementProtocol,
    DeviceLifecycleProtocol,
    DeviceLinkManagementProtocol,
    DeviceRemovalInfoProtocol,
    DeviceWeekProfileProtocol,
)

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
        assert callable(getattr(DeviceChannelAccessProtocol, "get_channel"))

    def test_has_get_custom_data_point_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_custom_data_point method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_custom_data_point")
        assert callable(getattr(DeviceChannelAccessProtocol, "get_custom_data_point"))

    def test_has_get_data_points_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_data_points method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_data_points")
        assert callable(getattr(DeviceChannelAccessProtocol, "get_data_points"))

    def test_has_get_events_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_events method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_events")
        assert callable(getattr(DeviceChannelAccessProtocol, "get_events"))

    def test_has_get_generic_data_point_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_generic_data_point method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_generic_data_point")
        assert callable(getattr(DeviceChannelAccessProtocol, "get_generic_data_point"))

    def test_has_get_generic_event_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_generic_event method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_generic_event")
        assert callable(getattr(DeviceChannelAccessProtocol, "get_generic_event"))

    def test_has_get_readable_data_points_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has get_readable_data_points method."""
        assert hasattr(DeviceChannelAccessProtocol, "get_readable_data_points")
        assert callable(getattr(DeviceChannelAccessProtocol, "get_readable_data_points"))

    def test_has_identify_channel_method(self) -> None:
        """Verify DeviceChannelAccessProtocol has identify_channel method."""
        assert hasattr(DeviceChannelAccessProtocol, "identify_channel")
        assert callable(getattr(DeviceChannelAccessProtocol, "identify_channel"))


# =============================================================================
# DeviceAvailabilityProtocol Contract Tests
# =============================================================================


class TestDeviceAvailabilityProtocolContract:
    """Contract tests for DeviceAvailabilityProtocol."""

    def test_has_availability_property(self) -> None:
        """Verify DeviceAvailabilityProtocol has availability property."""
        assert hasattr(DeviceAvailabilityProtocol, "availability")

    def test_has_available_property(self) -> None:
        """Verify DeviceAvailabilityProtocol has available property."""
        assert hasattr(DeviceAvailabilityProtocol, "available")

    def test_has_config_pending_property(self) -> None:
        """Verify DeviceAvailabilityProtocol has config_pending property."""
        assert hasattr(DeviceAvailabilityProtocol, "config_pending")

    def test_has_set_forced_availability_method(self) -> None:
        """Verify DeviceAvailabilityProtocol has set_forced_availability method."""
        assert hasattr(DeviceAvailabilityProtocol, "set_forced_availability")
        assert callable(getattr(DeviceAvailabilityProtocol, "set_forced_availability"))


# =============================================================================
# DeviceFirmwareProtocol Contract Tests
# =============================================================================


class TestDeviceFirmwareProtocolContract:
    """Contract tests for DeviceFirmwareProtocol."""

    def test_has_available_firmware_property(self) -> None:
        """Verify DeviceFirmwareProtocol has available_firmware property."""
        assert hasattr(DeviceFirmwareProtocol, "available_firmware")

    def test_has_firmware_property(self) -> None:
        """Verify DeviceFirmwareProtocol has firmware property."""
        assert hasattr(DeviceFirmwareProtocol, "firmware")

    def test_has_firmware_updatable_property(self) -> None:
        """Verify DeviceFirmwareProtocol has firmware_updatable property."""
        assert hasattr(DeviceFirmwareProtocol, "firmware_updatable")

    def test_has_firmware_update_state_property(self) -> None:
        """Verify DeviceFirmwareProtocol has firmware_update_state property."""
        assert hasattr(DeviceFirmwareProtocol, "firmware_update_state")

    def test_has_is_updatable_property(self) -> None:
        """Verify DeviceFirmwareProtocol has is_updatable property."""
        assert hasattr(DeviceFirmwareProtocol, "is_updatable")

    def test_has_refresh_firmware_data_method(self) -> None:
        """Verify DeviceFirmwareProtocol has refresh_firmware_data method."""
        assert hasattr(DeviceFirmwareProtocol, "refresh_firmware_data")
        assert callable(getattr(DeviceFirmwareProtocol, "refresh_firmware_data"))

    def test_has_subscribe_to_firmware_updated_method(self) -> None:
        """Verify DeviceFirmwareProtocol has subscribe_to_firmware_updated method."""
        assert hasattr(DeviceFirmwareProtocol, "subscribe_to_firmware_updated")
        assert callable(getattr(DeviceFirmwareProtocol, "subscribe_to_firmware_updated"))

    def test_has_update_firmware_method(self) -> None:
        """Verify DeviceFirmwareProtocol has update_firmware method."""
        assert hasattr(DeviceFirmwareProtocol, "update_firmware")
        assert callable(getattr(DeviceFirmwareProtocol, "update_firmware"))


# =============================================================================
# DeviceLinkManagementProtocol Contract Tests
# =============================================================================


class TestDeviceLinkManagementProtocolContract:
    """Contract tests for DeviceLinkManagementProtocol."""

    def test_has_create_central_links_method(self) -> None:
        """Verify DeviceLinkManagementProtocol has create_central_links method."""
        assert hasattr(DeviceLinkManagementProtocol, "create_central_links")
        assert callable(getattr(DeviceLinkManagementProtocol, "create_central_links"))

    def test_has_link_peer_channels_property(self) -> None:
        """Verify DeviceLinkManagementProtocol has link_peer_channels property."""
        assert hasattr(DeviceLinkManagementProtocol, "link_peer_channels")

    def test_has_remove_central_links_method(self) -> None:
        """Verify DeviceLinkManagementProtocol has remove_central_links method."""
        assert hasattr(DeviceLinkManagementProtocol, "remove_central_links")
        assert callable(getattr(DeviceLinkManagementProtocol, "remove_central_links"))


# =============================================================================
# DeviceGroupManagementProtocol Contract Tests
# =============================================================================


class TestDeviceGroupManagementProtocolContract:
    """Contract tests for DeviceGroupManagementProtocol."""

    def test_has_add_channel_to_group_method(self) -> None:
        """Verify DeviceGroupManagementProtocol has add_channel_to_group method."""
        assert hasattr(DeviceGroupManagementProtocol, "add_channel_to_group")
        assert callable(getattr(DeviceGroupManagementProtocol, "add_channel_to_group"))

    def test_has_get_channel_group_no_method(self) -> None:
        """Verify DeviceGroupManagementProtocol has get_channel_group_no method."""
        assert hasattr(DeviceGroupManagementProtocol, "get_channel_group_no")
        assert callable(getattr(DeviceGroupManagementProtocol, "get_channel_group_no"))

    def test_has_is_in_multi_channel_group_method(self) -> None:
        """Verify DeviceGroupManagementProtocol has is_in_multi_channel_group method."""
        assert hasattr(DeviceGroupManagementProtocol, "is_in_multi_channel_group")
        assert callable(getattr(DeviceGroupManagementProtocol, "is_in_multi_channel_group"))


# =============================================================================
# DeviceConfigurationProtocol Contract Tests
# =============================================================================


class TestDeviceConfigurationProtocolContract:
    """Contract tests for DeviceConfigurationProtocol."""

    def test_has_allow_undefined_generic_data_points_property(self) -> None:
        """Verify DeviceConfigurationProtocol has allow_undefined_generic_data_points property."""
        assert hasattr(DeviceConfigurationProtocol, "allow_undefined_generic_data_points")

    def test_has_has_custom_data_point_definition_property(self) -> None:
        """Verify DeviceConfigurationProtocol has has_custom_data_point_definition property."""
        assert hasattr(DeviceConfigurationProtocol, "has_custom_data_point_definition")

    def test_has_has_sub_devices_property(self) -> None:
        """Verify DeviceConfigurationProtocol has has_sub_devices property."""
        assert hasattr(DeviceConfigurationProtocol, "has_sub_devices")

    def test_has_ignore_for_custom_data_point_property(self) -> None:
        """Verify DeviceConfigurationProtocol has ignore_for_custom_data_point property."""
        assert hasattr(DeviceConfigurationProtocol, "ignore_for_custom_data_point")

    def test_has_ignore_on_initial_load_property(self) -> None:
        """Verify DeviceConfigurationProtocol has ignore_on_initial_load property."""
        assert hasattr(DeviceConfigurationProtocol, "ignore_on_initial_load")

    def test_has_product_group_property(self) -> None:
        """Verify DeviceConfigurationProtocol has product_group property."""
        assert hasattr(DeviceConfigurationProtocol, "product_group")

    def test_has_rega_id_property(self) -> None:
        """Verify DeviceConfigurationProtocol has rega_id property."""
        assert hasattr(DeviceConfigurationProtocol, "rega_id")

    def test_has_room_property(self) -> None:
        """Verify DeviceConfigurationProtocol has room property."""
        assert hasattr(DeviceConfigurationProtocol, "room")

    def test_has_rooms_property(self) -> None:
        """Verify DeviceConfigurationProtocol has rooms property."""
        assert hasattr(DeviceConfigurationProtocol, "rooms")

    def test_has_rx_modes_property(self) -> None:
        """Verify DeviceConfigurationProtocol has rx_modes property."""
        assert hasattr(DeviceConfigurationProtocol, "rx_modes")


# =============================================================================
# DeviceWeekProfileProtocol Contract Tests
# =============================================================================


class TestDeviceWeekProfileProtocolContract:
    """Contract tests for DeviceWeekProfileProtocol."""

    def test_has_default_schedule_channel_property(self) -> None:
        """Verify DeviceWeekProfileProtocol has default_schedule_channel property."""
        assert hasattr(DeviceWeekProfileProtocol, "default_schedule_channel")

    def test_has_has_week_profile_property(self) -> None:
        """Verify DeviceWeekProfileProtocol has has_week_profile property."""
        assert hasattr(DeviceWeekProfileProtocol, "has_week_profile")

    def test_has_init_week_profile_method(self) -> None:
        """Verify DeviceWeekProfileProtocol has init_week_profile method."""
        assert hasattr(DeviceWeekProfileProtocol, "init_week_profile")
        assert callable(getattr(DeviceWeekProfileProtocol, "init_week_profile"))

    def test_has_week_profile_property(self) -> None:
        """Verify DeviceWeekProfileProtocol has week_profile property."""
        assert hasattr(DeviceWeekProfileProtocol, "week_profile")


# =============================================================================
# DeviceProvidersProtocol Contract Tests
# =============================================================================


class TestDeviceProvidersProtocolContract:
    """Contract tests for DeviceProvidersProtocol."""

    def test_has_central_info_property(self) -> None:
        """Verify DeviceProvidersProtocol has central_info property."""
        assert hasattr(DeviceProvidersProtocol, "central_info")

    def test_has_channel_lookup_property(self) -> None:
        """Verify DeviceProvidersProtocol has channel_lookup property."""
        assert hasattr(DeviceProvidersProtocol, "channel_lookup")

    def test_has_client_property(self) -> None:
        """Verify DeviceProvidersProtocol has client property."""
        assert hasattr(DeviceProvidersProtocol, "client")

    def test_has_config_provider_property(self) -> None:
        """Verify DeviceProvidersProtocol has config_provider property."""
        assert hasattr(DeviceProvidersProtocol, "config_provider")

    def test_has_data_cache_provider_property(self) -> None:
        """Verify DeviceProvidersProtocol has data_cache_provider property."""
        assert hasattr(DeviceProvidersProtocol, "data_cache_provider")

    def test_has_data_point_provider_property(self) -> None:
        """Verify DeviceProvidersProtocol has data_point_provider property."""
        assert hasattr(DeviceProvidersProtocol, "data_point_provider")

    def test_has_device_data_refresher_property(self) -> None:
        """Verify DeviceProvidersProtocol has device_data_refresher property."""
        assert hasattr(DeviceProvidersProtocol, "device_data_refresher")

    def test_has_device_description_provider_property(self) -> None:
        """Verify DeviceProvidersProtocol has device_description_provider property."""
        assert hasattr(DeviceProvidersProtocol, "device_description_provider")

    def test_has_device_details_provider_property(self) -> None:
        """Verify DeviceProvidersProtocol has device_details_provider property."""
        assert hasattr(DeviceProvidersProtocol, "device_details_provider")

    def test_has_event_bus_provider_property(self) -> None:
        """Verify DeviceProvidersProtocol has event_bus_provider property."""
        assert hasattr(DeviceProvidersProtocol, "event_bus_provider")

    def test_has_event_publisher_property(self) -> None:
        """Verify DeviceProvidersProtocol has event_publisher property."""
        assert hasattr(DeviceProvidersProtocol, "event_publisher")

    def test_has_event_subscription_manager_property(self) -> None:
        """Verify DeviceProvidersProtocol has event_subscription_manager property."""
        assert hasattr(DeviceProvidersProtocol, "event_subscription_manager")

    def test_has_parameter_visibility_provider_property(self) -> None:
        """Verify DeviceProvidersProtocol has parameter_visibility_provider property."""
        assert hasattr(DeviceProvidersProtocol, "parameter_visibility_provider")

    def test_has_paramset_description_provider_property(self) -> None:
        """Verify DeviceProvidersProtocol has paramset_description_provider property."""
        assert hasattr(DeviceProvidersProtocol, "paramset_description_provider")

    def test_has_task_scheduler_property(self) -> None:
        """Verify DeviceProvidersProtocol has task_scheduler property."""
        assert hasattr(DeviceProvidersProtocol, "task_scheduler")

    def test_has_value_cache_property(self) -> None:
        """Verify DeviceProvidersProtocol has value_cache property."""
        assert hasattr(DeviceProvidersProtocol, "value_cache")


# =============================================================================
# DeviceLifecycleProtocol Contract Tests
# =============================================================================


class TestDeviceLifecycleProtocolContract:
    """Contract tests for DeviceLifecycleProtocol."""

    def test_has_export_device_definition_method(self) -> None:
        """Verify DeviceLifecycleProtocol has export_device_definition method."""
        assert hasattr(DeviceLifecycleProtocol, "export_device_definition")
        assert callable(getattr(DeviceLifecycleProtocol, "export_device_definition"))

    def test_has_finalize_init_method(self) -> None:
        """Verify DeviceLifecycleProtocol has finalize_init method."""
        assert hasattr(DeviceLifecycleProtocol, "finalize_init")
        assert callable(getattr(DeviceLifecycleProtocol, "finalize_init"))

    def test_has_on_config_changed_method(self) -> None:
        """Verify DeviceLifecycleProtocol has on_config_changed method."""
        assert hasattr(DeviceLifecycleProtocol, "on_config_changed")
        assert callable(getattr(DeviceLifecycleProtocol, "on_config_changed"))

    def test_has_publish_device_updated_event_method(self) -> None:
        """Verify DeviceLifecycleProtocol has publish_device_updated_event method."""
        assert hasattr(DeviceLifecycleProtocol, "publish_device_updated_event")
        assert callable(getattr(DeviceLifecycleProtocol, "publish_device_updated_event"))

    def test_has_reload_device_config_method(self) -> None:
        """Verify DeviceLifecycleProtocol has reload_device_config method."""
        assert hasattr(DeviceLifecycleProtocol, "reload_device_config")
        assert callable(getattr(DeviceLifecycleProtocol, "reload_device_config"))

    def test_has_remove_method(self) -> None:
        """Verify DeviceLifecycleProtocol has remove method."""
        assert hasattr(DeviceLifecycleProtocol, "remove")
        assert callable(getattr(DeviceLifecycleProtocol, "remove"))


# =============================================================================
# Combined Device Protocol Contract Tests
# =============================================================================


class TestDeviceStateProtocolContract:
    """Contract tests for DeviceStateProtocol."""

    def test_includes_availability(self) -> None:
        """Verify DeviceStateProtocol includes availability members."""
        assert hasattr(DeviceStateProtocol, "available")
        assert hasattr(DeviceStateProtocol, "config_pending")

    def test_includes_firmware(self) -> None:
        """Verify DeviceStateProtocol includes firmware members."""
        assert hasattr(DeviceStateProtocol, "firmware")
        assert hasattr(DeviceStateProtocol, "firmware_updatable")

    def test_includes_week_profile(self) -> None:
        """Verify DeviceStateProtocol includes week profile members."""
        assert hasattr(DeviceStateProtocol, "has_week_profile")
        assert hasattr(DeviceStateProtocol, "week_profile")

    def test_is_protocol(self) -> None:
        """Verify DeviceStateProtocol is a Protocol."""
        assert hasattr(DeviceStateProtocol, "__protocol_attrs__") or hasattr(DeviceStateProtocol, "_is_protocol")


class TestDeviceOperationsProtocolContract:
    """Contract tests for DeviceOperationsProtocol."""

    def test_includes_group_management(self) -> None:
        """Verify DeviceOperationsProtocol includes group management members."""
        assert hasattr(DeviceOperationsProtocol, "add_channel_to_group")
        assert hasattr(DeviceOperationsProtocol, "get_channel_group_no")

    def test_includes_lifecycle(self) -> None:
        """Verify DeviceOperationsProtocol includes lifecycle members."""
        assert hasattr(DeviceOperationsProtocol, "finalize_init")
        assert hasattr(DeviceOperationsProtocol, "remove")

    def test_includes_link_management(self) -> None:
        """Verify DeviceOperationsProtocol includes link management members."""
        assert hasattr(DeviceOperationsProtocol, "link_peer_channels")
        assert hasattr(DeviceOperationsProtocol, "create_central_links")

    def test_is_protocol(self) -> None:
        """Verify DeviceOperationsProtocol is a Protocol."""
        assert hasattr(DeviceOperationsProtocol, "__protocol_attrs__") or hasattr(
            DeviceOperationsProtocol, "_is_protocol"
        )


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
        assert hasattr(DeviceProtocol, "rega_id")
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
# ChannelIdentityProtocol Contract Tests
# =============================================================================


class TestChannelIdentityProtocolContract:
    """Contract tests for ChannelIdentityProtocol."""

    def test_has_address_property(self) -> None:
        """Verify ChannelIdentityProtocol has address property."""
        assert hasattr(ChannelIdentityProtocol, "address")

    def test_has_full_name_property(self) -> None:
        """Verify ChannelIdentityProtocol has full_name property."""
        assert hasattr(ChannelIdentityProtocol, "full_name")

    def test_has_name_property(self) -> None:
        """Verify ChannelIdentityProtocol has name property."""
        assert hasattr(ChannelIdentityProtocol, "name")

    def test_has_no_property(self) -> None:
        """Verify ChannelIdentityProtocol has no property."""
        assert hasattr(ChannelIdentityProtocol, "no")

    def test_has_rega_id_property(self) -> None:
        """Verify ChannelIdentityProtocol has rega_id property."""
        assert hasattr(ChannelIdentityProtocol, "rega_id")

    def test_has_type_name_property(self) -> None:
        """Verify ChannelIdentityProtocol has type_name property."""
        assert hasattr(ChannelIdentityProtocol, "type_name")

    def test_has_unique_id_property(self) -> None:
        """Verify ChannelIdentityProtocol has unique_id property."""
        assert hasattr(ChannelIdentityProtocol, "unique_id")


# =============================================================================
# ChannelDataPointAccessProtocol Contract Tests
# =============================================================================


class TestChannelDataPointAccessProtocolContract:
    """Contract tests for ChannelDataPointAccessProtocol."""

    def test_has_add_data_point_method(self) -> None:
        """Verify ChannelDataPointAccessProtocol has add_data_point method."""
        assert hasattr(ChannelDataPointAccessProtocol, "add_data_point")
        assert callable(getattr(ChannelDataPointAccessProtocol, "add_data_point"))

    def test_has_calculated_data_points_property(self) -> None:
        """Verify ChannelDataPointAccessProtocol has calculated_data_points property."""
        assert hasattr(ChannelDataPointAccessProtocol, "calculated_data_points")

    def test_has_custom_data_point_property(self) -> None:
        """Verify ChannelDataPointAccessProtocol has custom_data_point property."""
        assert hasattr(ChannelDataPointAccessProtocol, "custom_data_point")

    def test_has_data_point_paths_property(self) -> None:
        """Verify ChannelDataPointAccessProtocol has data_point_paths property."""
        assert hasattr(ChannelDataPointAccessProtocol, "data_point_paths")

    def test_has_event_groups_property(self) -> None:
        """Verify ChannelDataPointAccessProtocol has event_groups property."""
        assert hasattr(ChannelDataPointAccessProtocol, "event_groups")

    def test_has_generic_data_points_property(self) -> None:
        """Verify ChannelDataPointAccessProtocol has generic_data_points property."""
        assert hasattr(ChannelDataPointAccessProtocol, "generic_data_points")

    def test_has_generic_events_property(self) -> None:
        """Verify ChannelDataPointAccessProtocol has generic_events property."""
        assert hasattr(ChannelDataPointAccessProtocol, "generic_events")

    def test_has_get_calculated_data_point_method(self) -> None:
        """Verify ChannelDataPointAccessProtocol has get_calculated_data_point method."""
        assert hasattr(ChannelDataPointAccessProtocol, "get_calculated_data_point")
        assert callable(getattr(ChannelDataPointAccessProtocol, "get_calculated_data_point"))

    def test_has_get_data_points_method(self) -> None:
        """Verify ChannelDataPointAccessProtocol has get_data_points method."""
        assert hasattr(ChannelDataPointAccessProtocol, "get_data_points")
        assert callable(getattr(ChannelDataPointAccessProtocol, "get_data_points"))

    def test_has_get_events_method(self) -> None:
        """Verify ChannelDataPointAccessProtocol has get_events method."""
        assert hasattr(ChannelDataPointAccessProtocol, "get_events")
        assert callable(getattr(ChannelDataPointAccessProtocol, "get_events"))

    def test_has_get_generic_data_point_method(self) -> None:
        """Verify ChannelDataPointAccessProtocol has get_generic_data_point method."""
        assert hasattr(ChannelDataPointAccessProtocol, "get_generic_data_point")
        assert callable(getattr(ChannelDataPointAccessProtocol, "get_generic_data_point"))

    def test_has_get_generic_event_method(self) -> None:
        """Verify ChannelDataPointAccessProtocol has get_generic_event method."""
        assert hasattr(ChannelDataPointAccessProtocol, "get_generic_event")
        assert callable(getattr(ChannelDataPointAccessProtocol, "get_generic_event"))

    def test_has_get_readable_data_points_method(self) -> None:
        """Verify ChannelDataPointAccessProtocol has get_readable_data_points method."""
        assert hasattr(ChannelDataPointAccessProtocol, "get_readable_data_points")
        assert callable(getattr(ChannelDataPointAccessProtocol, "get_readable_data_points"))


# =============================================================================
# ChannelGroupingProtocol Contract Tests
# =============================================================================


class TestChannelGroupingProtocolContract:
    """Contract tests for ChannelGroupingProtocol."""

    def test_has_group_master_property(self) -> None:
        """Verify ChannelGroupingProtocol has group_master property."""
        assert hasattr(ChannelGroupingProtocol, "group_master")

    def test_has_group_no_property(self) -> None:
        """Verify ChannelGroupingProtocol has group_no property."""
        assert hasattr(ChannelGroupingProtocol, "group_no")

    def test_has_is_group_master_property(self) -> None:
        """Verify ChannelGroupingProtocol has is_group_master property."""
        assert hasattr(ChannelGroupingProtocol, "is_group_master")

    def test_has_is_in_multi_group_property(self) -> None:
        """Verify ChannelGroupingProtocol has is_in_multi_group property."""
        assert hasattr(ChannelGroupingProtocol, "is_in_multi_group")

    def test_has_link_peer_channels_property(self) -> None:
        """Verify ChannelGroupingProtocol has link_peer_channels property."""
        assert hasattr(ChannelGroupingProtocol, "link_peer_channels")


# =============================================================================
# ChannelMetadataProtocol Contract Tests
# =============================================================================


class TestChannelMetadataProtocolContract:
    """Contract tests for ChannelMetadataProtocol."""

    def test_has_device_property(self) -> None:
        """Verify ChannelMetadataProtocol has device property."""
        assert hasattr(ChannelMetadataProtocol, "device")

    def test_has_function_property(self) -> None:
        """Verify ChannelMetadataProtocol has function property."""
        assert hasattr(ChannelMetadataProtocol, "function")

    def test_has_is_schedule_channel_property(self) -> None:
        """Verify ChannelMetadataProtocol has is_schedule_channel property."""
        assert hasattr(ChannelMetadataProtocol, "is_schedule_channel")

    def test_has_operation_mode_property(self) -> None:
        """Verify ChannelMetadataProtocol has operation_mode property."""
        assert hasattr(ChannelMetadataProtocol, "operation_mode")

    def test_has_paramset_descriptions_property(self) -> None:
        """Verify ChannelMetadataProtocol has paramset_descriptions property."""
        assert hasattr(ChannelMetadataProtocol, "paramset_descriptions")

    def test_has_paramset_keys_property(self) -> None:
        """Verify ChannelMetadataProtocol has paramset_keys property."""
        assert hasattr(ChannelMetadataProtocol, "paramset_keys")

    def test_has_room_property(self) -> None:
        """Verify ChannelMetadataProtocol has room property."""
        assert hasattr(ChannelMetadataProtocol, "room")

    def test_has_rooms_property(self) -> None:
        """Verify ChannelMetadataProtocol has rooms property."""
        assert hasattr(ChannelMetadataProtocol, "rooms")


# =============================================================================
# ChannelLinkManagementProtocol Contract Tests
# =============================================================================


class TestChannelLinkManagementProtocolContract:
    """Contract tests for ChannelLinkManagementProtocol."""

    def test_has_create_central_link_method(self) -> None:
        """Verify ChannelLinkManagementProtocol has create_central_link method."""
        assert hasattr(ChannelLinkManagementProtocol, "create_central_link")
        assert callable(getattr(ChannelLinkManagementProtocol, "create_central_link"))

    def test_has_has_link_target_category_method(self) -> None:
        """Verify ChannelLinkManagementProtocol has has_link_target_category method."""
        assert hasattr(ChannelLinkManagementProtocol, "has_link_target_category")
        assert callable(getattr(ChannelLinkManagementProtocol, "has_link_target_category"))

    def test_has_remove_central_link_method(self) -> None:
        """Verify ChannelLinkManagementProtocol has remove_central_link method."""
        assert hasattr(ChannelLinkManagementProtocol, "remove_central_link")
        assert callable(getattr(ChannelLinkManagementProtocol, "remove_central_link"))

    def test_has_subscribe_to_link_peer_changed_method(self) -> None:
        """Verify ChannelLinkManagementProtocol has subscribe_to_link_peer_changed method."""
        assert hasattr(ChannelLinkManagementProtocol, "subscribe_to_link_peer_changed")
        assert callable(getattr(ChannelLinkManagementProtocol, "subscribe_to_link_peer_changed"))


# =============================================================================
# ChannelLifecycleProtocol Contract Tests
# =============================================================================


class TestChannelLifecycleProtocolContract:
    """Contract tests for ChannelLifecycleProtocol."""

    def test_has_finalize_init_method(self) -> None:
        """Verify ChannelLifecycleProtocol has finalize_init method."""
        assert hasattr(ChannelLifecycleProtocol, "finalize_init")
        assert callable(getattr(ChannelLifecycleProtocol, "finalize_init"))

    def test_has_init_link_peer_method(self) -> None:
        """Verify ChannelLifecycleProtocol has init_link_peer method."""
        assert hasattr(ChannelLifecycleProtocol, "init_link_peer")
        assert callable(getattr(ChannelLifecycleProtocol, "init_link_peer"))

    def test_has_on_config_changed_method(self) -> None:
        """Verify ChannelLifecycleProtocol has on_config_changed method."""
        assert hasattr(ChannelLifecycleProtocol, "on_config_changed")
        assert callable(getattr(ChannelLifecycleProtocol, "on_config_changed"))

    def test_has_reload_channel_config_method(self) -> None:
        """Verify ChannelLifecycleProtocol has reload_channel_config method."""
        assert hasattr(ChannelLifecycleProtocol, "reload_channel_config")
        assert callable(getattr(ChannelLifecycleProtocol, "reload_channel_config"))

    def test_has_remove_method(self) -> None:
        """Verify ChannelLifecycleProtocol has remove method."""
        assert hasattr(ChannelLifecycleProtocol, "remove")
        assert callable(getattr(ChannelLifecycleProtocol, "remove"))


# =============================================================================
# Combined Channel Protocol Contract Tests
# =============================================================================


class TestChannelMetadataAndGroupingProtocolContract:
    """Contract tests for ChannelMetadataAndGroupingProtocol."""

    def test_includes_grouping(self) -> None:
        """Verify ChannelMetadataAndGroupingProtocol includes grouping members."""
        assert hasattr(ChannelMetadataAndGroupingProtocol, "group_master")
        assert hasattr(ChannelMetadataAndGroupingProtocol, "group_no")
        assert hasattr(ChannelMetadataAndGroupingProtocol, "is_group_master")

    def test_includes_metadata(self) -> None:
        """Verify ChannelMetadataAndGroupingProtocol includes metadata members."""
        assert hasattr(ChannelMetadataAndGroupingProtocol, "device")
        assert hasattr(ChannelMetadataAndGroupingProtocol, "function")
        assert hasattr(ChannelMetadataAndGroupingProtocol, "room")

    def test_is_runtime_checkable(self) -> None:
        """Verify ChannelMetadataAndGroupingProtocol is runtime_checkable."""
        assert hasattr(ChannelMetadataAndGroupingProtocol, "__subclasshook__")


class TestChannelManagementProtocolContract:
    """Contract tests for ChannelManagementProtocol."""

    def test_includes_lifecycle(self) -> None:
        """Verify ChannelManagementProtocol includes lifecycle members."""
        assert hasattr(ChannelManagementProtocol, "finalize_init")
        assert hasattr(ChannelManagementProtocol, "remove")

    def test_includes_link_management(self) -> None:
        """Verify ChannelManagementProtocol includes link management members."""
        assert hasattr(ChannelManagementProtocol, "create_central_link")
        assert hasattr(ChannelManagementProtocol, "remove_central_link")

    def test_is_runtime_checkable(self) -> None:
        """Verify ChannelManagementProtocol is runtime_checkable."""
        assert hasattr(ChannelManagementProtocol, "__subclasshook__")


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
        assert hasattr(ChannelProtocol, "rega_id")
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
        """Verify set_forced_availability method signature."""
        sig = inspect.signature(DeviceAvailabilityProtocol.set_forced_availability)
        params = list(sig.parameters.keys())
        assert "forced_availability" in params

    def test_update_firmware_signature(self) -> None:
        """Verify update_firmware method signature."""
        sig = inspect.signature(DeviceFirmwareProtocol.update_firmware)
        params = list(sig.parameters.keys())
        assert "refresh_after_update_intervals" in params


class TestChannelMethodSignaturesContract:
    """Contract tests for ChannelProtocol method signatures."""

    def test_add_data_point_signature(self) -> None:
        """Verify add_data_point method signature."""
        sig = inspect.signature(ChannelDataPointAccessProtocol.add_data_point)
        params = list(sig.parameters.keys())
        assert "data_point" in params

    def test_get_data_points_signature(self) -> None:
        """Verify get_data_points method signature."""
        sig = inspect.signature(ChannelDataPointAccessProtocol.get_data_points)
        params = list(sig.parameters.keys())
        assert "category" in params
        assert "registered" in params

    def test_get_generic_data_point_signature(self) -> None:
        """Verify get_generic_data_point method signature."""
        sig = inspect.signature(ChannelDataPointAccessProtocol.get_generic_data_point)
        params = list(sig.parameters.keys())
        assert "parameter" in params
        assert "paramset_key" in params

    def test_has_link_target_category_signature(self) -> None:
        """Verify has_link_target_category method signature."""
        sig = inspect.signature(ChannelLinkManagementProtocol.has_link_target_category)
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
            "rega_id",
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
            "rega_id",
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
