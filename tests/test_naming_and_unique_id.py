"""
Tests for naming and unique_id generation patterns.

This module verifies the exact patterns and rules for:
- unique_id generation (pattern validation, special address handling)
- Name generation (device/channel/parameter name composition)
- Name data structures (ChannelNameData, DataPointNameData)
"""

from __future__ import annotations

import pytest

from aiohomematic.const import ADDRESS_SEPARATOR
from aiohomematic.model.support import (
    ChannelNameData,
    DataPointNameData,
    generate_channel_unique_id,
    generate_unique_id,
)

# =============================================================================
# PART 1: unique_id Pattern Tests
# =============================================================================


class TestUniqueIdPatterns:
    """Test exact unique_id pattern generation."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({}, True, None, None)],
    )
    async def test_channel_unique_id_pattern(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test channel unique_id pattern: {address} with ':' → '_'.

        Channel unique_ids don't include parameter, just the address.
        """
        central, _, _ = central_client_factory_with_homegear_client

        # Normal channel
        uid = generate_channel_unique_id(config_provider=central, address="VCU1234567:1")
        assert uid == "vcu1234567_1"

        # Channel 0
        uid = generate_channel_unique_id(config_provider=central, address="VCU1234567:0")
        assert uid == "vcu1234567_0"

        # With hyphen
        uid = generate_channel_unique_id(config_provider=central, address="ABC-DEF:3")
        assert uid == "abc_def_3"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({}, True, None, None)],
    )
    async def test_unique_id_pattern_address_parameter(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test unique_id pattern: {address}_{parameter}.

        Pattern rules:
        - Address separator ':' becomes '_'
        - Hyphen '-' becomes '_'
        - Result is lowercase
        """
        central, _, _ = central_client_factory_with_homegear_client

        # Test basic pattern: VCU1234567:1 + STATE → vcu1234567_1_state
        uid = generate_unique_id(config_provider=central, address="VCU1234567:1", parameter="STATE")
        assert uid == "vcu1234567_1_state"

        # Test without parameter: VCU1234567:1 → vcu1234567_1
        uid = generate_unique_id(config_provider=central, address="VCU1234567:1")
        assert uid == "vcu1234567_1"

        # Test hyphen replacement: ABC-DEF:2 + LEVEL → abc_def_2_level
        uid = generate_unique_id(config_provider=central, address="ABC-DEF:2", parameter="LEVEL")
        assert uid == "abc_def_2_level"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({}, True, None, None)],
    )
    async def test_unique_id_pattern_internal_addresses(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test unique_id pattern for internal addresses: {central_id}_{address}_{parameter}.

        Internal addresses (INT*, HUB, PROGRAM, SYSVAR, VIRTUAL_REMOTE) include central_id.
        """
        central, _, _ = central_client_factory_with_homegear_client
        central_id = central.config.central_id

        # INT addresses (start with INT000)
        uid = generate_unique_id(config_provider=central, address="INT0001234:1", parameter="LEVEL")
        assert uid == f"{central_id}_int0001234_1_level"

        # hub address (lowercase constant)
        uid = generate_unique_id(config_provider=central, address="hub", parameter="STATUS")
        assert uid == f"{central_id}_hub_status"

        # program address (lowercase constant)
        uid = generate_unique_id(config_provider=central, address="program", parameter="RUN")
        assert uid == f"{central_id}_program_run"

        # sysvar address (lowercase constant)
        uid = generate_unique_id(config_provider=central, address="sysvar", parameter="VALUE")
        assert uid == f"{central_id}_sysvar_value"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({}, True, None, None)],
    )
    async def test_unique_id_pattern_with_prefix(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test unique_id pattern with prefix: {prefix}_{address}_{parameter}.

        Prefix is used for events and buttons.
        """
        central, _, _ = central_client_factory_with_homegear_client

        uid = generate_unique_id(
            config_provider=central, address="VCU1234567:1", parameter="PRESS_SHORT", prefix="event"
        )
        assert uid == "event_vcu1234567_1_press_short"

        uid = generate_unique_id(config_provider=central, address="VCU1234567:0", parameter="BUTTON", prefix="btn")
        assert uid == "btn_vcu1234567_0_button"


# =============================================================================
# PART 2: Name Data Structure Tests
# =============================================================================


class TestChannelNameDataPatterns:
    """Test ChannelNameData name composition patterns."""

    def test_device_name_prefix_stripping(self) -> None:
        """
        Test that channel_name strips device_name prefix.

        When channel_name starts with device_name, the prefix is removed
        to avoid redundancy in the combined name.
        """
        # Channel name starts with device name → prefix stripped
        name_data = ChannelNameData(device_name="Wohnzimmer Licht", channel_name="Wohnzimmer Licht:1")
        assert name_data.channel_name == "1"
        assert name_data.full_name == "Wohnzimmer Licht 1"

        # Channel name starts with device name + space → stripped
        name_data = ChannelNameData(device_name="Thermostat", channel_name="Thermostat Heizung")
        assert name_data.channel_name == "Heizung"
        assert name_data.full_name == "Thermostat Heizung"

    def test_different_device_and_channel_names(self) -> None:
        """
        Test when device and channel names are different.

        When channel_name doesn't start with device_name, both are preserved.
        """
        name_data = ChannelNameData(device_name="Device A", channel_name="Switch Channel")
        assert name_data.channel_name == "Switch Channel"
        assert name_data.full_name == "Device A Switch Channel"
        assert name_data.device_name == "Device A"

    def test_empty_channel_name(self) -> None:
        """Test handling of empty channel name."""
        name_data = ChannelNameData(device_name="Device", channel_name="")
        assert name_data.channel_name == ""
        assert name_data.full_name == "Device"

    def test_full_name_composition(self) -> None:
        """
        Test full_name pattern: '{device_name} {channel_name}'.

        The full_name combines device and channel name with space.
        """
        name_data = ChannelNameData(device_name="Küche", channel_name="Schalter")
        assert name_data.full_name == "Küche Schalter"

        # Empty channel → only device name
        name_data = ChannelNameData(device_name="Küche", channel_name="")
        assert name_data.full_name == "Küche"


class TestDataPointNameDataPatterns:
    """Test DataPointNameData name composition patterns."""

    def test_device_prefix_stripping_in_data_point_name(self) -> None:
        """
        Test device_name prefix stripping from data point name.

        When channel+parameter starts with device_name, the prefix is removed.
        """
        name_data = DataPointNameData(
            device_name="Wohnzimmer",
            channel_name="Wohnzimmer Licht",
            parameter_name="STATE",
        )
        # "Wohnzimmer Licht STATE" starts with "Wohnzimmer" → stripped
        assert name_data.name == "Licht STATE"
        assert name_data.full_name == "Wohnzimmer Licht STATE"

    def test_no_parameter_name(self) -> None:
        """Test DataPointNameData without parameter name."""
        name_data = DataPointNameData(device_name="Device", channel_name="Channel", parameter_name=None)
        assert name_data.parameter_name is None
        assert name_data.name == "Channel"

    def test_parameter_name_in_data_point_name(self) -> None:
        """
        Test that parameter_name is included in the data point name.

        Pattern: '{channel_name} {parameter_name}' with device prefix stripped.
        """
        name_data = DataPointNameData(device_name="Thermostat", channel_name="Heizung", parameter_name="Temperature")
        assert name_data.parameter_name == "Temperature"
        assert name_data.name == "Heizung Temperature"
        assert name_data.full_name == "Thermostat Heizung Temperature"


# =============================================================================
# PART 3: Integrative Tests with Device Details
# =============================================================================


class TestIntegrativeNaming:
    """Test naming behavior with actual device instances."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({"VCU2128127", "VCU0000263", "VCU0000054", "VCU1769958"}, True, None, None)],
    )
    async def test_all_unique_ids_are_unique(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Verify that all unique_ids in the system are actually unique."""
        central, _, _ = central_client_factory_with_homegear_client

        all_unique_ids: dict[str, str] = {}  # uid -> description for debugging
        duplicates: list[str] = []

        for dp in central.get_data_points():
            if dp.unique_id in all_unique_ids:
                duplicates.append(f"{dp.unique_id} (first: {all_unique_ids[dp.unique_id]}, duplicate: {dp.full_name})")
            else:
                all_unique_ids[dp.unique_id] = dp.full_name

        assert not duplicates, f"Duplicate unique_ids found: {duplicates}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({"VCU2128127"}, True, None, None)],
    )
    async def test_channel_unique_id_matches_pattern(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that channel unique_ids follow the expected pattern."""
        central, _, _ = central_client_factory_with_homegear_client

        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None

        for channel in device.channels.values():
            # Pattern: {device_address}_{channel_no}
            expected = channel.address.replace(ADDRESS_SEPARATOR, "_").replace("-", "_").lower()
            assert channel.unique_id == expected, f"Channel unique_id {channel.unique_id} should be {expected}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({"VCU2128127"}, True, None, None)],
    )
    async def test_data_point_full_name_contains_device_name(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that data point full_name includes device name."""
        central, _, _ = central_client_factory_with_homegear_client

        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None
        device_name = device.name

        for dp in device.generic_data_points:
            # full_name should start with device name (or be derived from it)
            assert dp.full_name is not None
            assert len(dp.full_name) > 0
            # The full_name should reference the device somehow
            # Either starts with device name or contains channel info
            assert device_name in dp.full_name or dp.channel.address in dp.full_name or device.model in dp.full_name

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({"VCU2128127"}, True, None, None)],
    )
    async def test_device_unique_id_matches_pattern(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that device data points follow the expected unique_id pattern."""
        central, _, _ = central_client_factory_with_homegear_client

        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None

        for dp in device.generic_data_points:
            # Verify pattern: {address}_{parameter} (lowercase)
            expected_prefix = dp.channel.address.replace(ADDRESS_SEPARATOR, "_").replace("-", "_").lower()
            assert dp.unique_id.startswith(expected_prefix), (
                f"unique_id {dp.unique_id} should start with {expected_prefix}"
            )

            # Parameter should be in unique_id (lowercase)
            assert dp.parameter.lower() in dp.unique_id, (
                f"Parameter {dp.parameter} should be in unique_id {dp.unique_id}"
            )


# =============================================================================
# PART 4: Edge Cases and Special Scenarios
# =============================================================================


class TestNamingEdgeCases:
    """Test edge cases in naming logic."""

    def test_address_separator_in_device_name(self) -> None:
        """Test handling of ':' (ADDRESS_SEPARATOR) in device name."""
        # Device name with colon should not break parsing
        name_data = ChannelNameData(device_name="Device:Special", channel_name="Device:Special:1")
        assert name_data.device_name == "Device:Special"
        # Channel name should have prefix stripped correctly
        assert name_data.channel_name == "1"

    def test_empty_names_structure(self) -> None:
        """Test empty name data structures."""
        channel_empty = ChannelNameData.empty()
        assert channel_empty.device_name == ""
        assert channel_empty.channel_name == ""
        assert channel_empty.full_name == ""

        dp_empty = DataPointNameData.empty()
        assert dp_empty.device_name == ""
        assert dp_empty.channel_name == ""
        assert dp_empty.parameter_name is None

    def test_unicode_in_names(self) -> None:
        """Test handling of unicode characters in names."""
        name_data = ChannelNameData(device_name="Küche Ofen", channel_name="Hauptschalter")
        assert name_data.full_name == "Küche Ofen Hauptschalter"

        name_data = DataPointNameData(device_name="日本語", channel_name="チャンネル", parameter_name="パラメータ")
        assert name_data.full_name == "日本語 チャンネル パラメータ"

    def test_whitespace_handling(self) -> None:
        """Test handling of extra whitespace in names."""
        name_data = ChannelNameData(device_name="Device  Name", channel_name="  Channel  ")
        # Whitespace in names should be preserved but trimmed at edges
        assert name_data.channel_name == "Channel"


# =============================================================================
# PART 5: Hub Data Point Naming Tests
# =============================================================================


class TestHubDataPointNaming:
    """Test naming patterns for hub data points (Programs, Sysvars)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({}, True, None, None)],
    )
    async def test_hub_datapoint_unique_id_includes_central_id(
        self,
        central_client_factory_with_ccu_client,
    ) -> None:
        """Test that hub data point unique_ids include central_id prefix."""
        central, _, _ = central_client_factory_with_ccu_client
        central_id = central.config.central_id

        # Hub data points should have central_id in their unique_id
        for dp in central.get_data_points():
            # Hub data points use special addresses that require central_id
            if any(addr in dp.unique_id for addr in ["hub", "program", "sysvar"]):
                assert dp.unique_id.startswith(central_id), (
                    f"Hub data point unique_id {dp.unique_id} should start with central_id {central_id}"
                )


# =============================================================================
# PART 6: Integration Tests with Mocked Device Details
# =============================================================================


class TestNamingWithMockedDeviceDetails:
    """
    Test naming behavior with mocked device_details_provider.

    These tests verify how the naming logic responds to different
    device/channel name configurations from the CCU.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({"VCU2128127"}, True, None, None)],
    )
    async def test_auto_generated_name_uses_model_and_address(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test that auto-generated names follow the pattern {model}_{address}.

        When no custom name is set in CCU, the library should auto-generate
        a name from the device model and address.
        """
        central, _, _ = central_client_factory_with_homegear_client

        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None

        # Either the device has a custom name OR it follows the auto-generated pattern
        device_name = device.name
        model = device.model
        address = device.address

        # Name should either be custom (from CCU) or auto-generated
        # Auto-generated pattern: {model}_{address}
        auto_pattern = f"{model}_{address}"

        # The name should be meaningful (not empty)
        assert device_name, "Device name should not be empty"
        assert len(device_name) > 0, "Device name should have length > 0"

        # If it's auto-generated, it should follow the pattern
        # If it's custom, it can be anything
        if "_" in device_name and device_name.startswith(model):
            assert device_name == auto_pattern, f"Auto-generated name should be '{auto_pattern}', got '{device_name}'"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({"VCU2128127"}, True, None, None)],
    )
    async def test_channel_custom_name_overrides_device_name_prefix(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test that channel custom name removes device name prefix.

        When channel name starts with device name (e.g., "Living Room Light:1"),
        the device name prefix should be stripped to avoid redundancy.
        """
        central, _, _ = central_client_factory_with_homegear_client

        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None

        for channel in device.channels.values():
            # If channel_name was stripped from device prefix,
            # full_name should not have double device name
            full_name = channel.name_data.full_name
            device_name = channel.name_data.device_name

            # Count occurrences of device_name in full_name
            # It should appear at most once (at the start)
            if device_name:
                # Remove first occurrence and check if it appears again
                remaining = full_name.replace(device_name, "", 1)
                assert device_name not in remaining, (
                    f"Device name '{device_name}' appears multiple times in channel full_name '{full_name}'"
                )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({"VCU2128127"}, True, None, None)],
    )
    async def test_data_point_name_structure(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test that data point names follow the expected structure.

        Expected structure:
        - name: derived from channel_name and parameter
        - full_name: "{device_name} {name}"
        """
        central, _, _ = central_client_factory_with_homegear_client

        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None

        for dp in device.generic_data_points:
            # name should be set (may be empty for some special data points)
            assert dp.name is not None

            # full_name should always be set
            assert dp.full_name is not None
            assert len(dp.full_name) > 0

            # full_name should be longer than or equal to name
            # (because it includes device name prefix)
            assert len(dp.full_name) >= len(dp.name), (
                f"DataPoint {dp.unique_id}: full_name '{dp.full_name}' should be >= name '{dp.name}' in length"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("address_device_translation", "do_mock_client", "ignore_devices_on_create", "un_ignore_list"),
        [({"VCU2128127"}, True, None, None)],
    )
    async def test_device_name_from_ccu_propagates_to_channels(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test that device name from CCU propagates to channel names.

        When a device has a custom name in CCU, that name should be:
        1. Used as the device.name
        2. Propagated to channel.name_data.device_name
        3. Included in data point full_name
        """
        central, _, _ = central_client_factory_with_homegear_client

        device = central.device_coordinator.get_device(address="VCU2128127")
        assert device is not None

        device_name = device.name

        # All channels should have device_name set correctly
        for channel in device.channels.values():
            assert channel.name_data.device_name == device_name, (
                f"Channel {channel.address} should have device_name={device_name}, got {channel.name_data.device_name}"
            )

        # All data points should include device name in full_name
        for dp in device.generic_data_points:
            assert device_name in dp.full_name, (
                f"DataPoint {dp.unique_id} full_name should contain device_name={device_name}, got {dp.full_name}"
            )
