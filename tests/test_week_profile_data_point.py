# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for WeekProfileDataPoint."""

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.events import DataPointStateChangedEvent
from aiohomematic.const import DataPointUsage, Parameter, ParamsetKey, ScheduleType
from aiohomematic.model.custom import CustomDpCover, CustomDpRfThermostat, CustomDpSwitch
from aiohomematic.model.schedule_models import (
    SimpleSchedule,
    SimpleScheduleEntry,
    TargetChannelInfo,
    channel_key_to_bitmask,
    parse_channel_locks,
)
from aiohomematic.model.week_profile import ClimateWeekProfile, DefaultWeekProfile
from aiohomematic.model.week_profile_data_point import WeekProfileDataPoint
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES_SWITCH: set[str] = {"VCU2128127"}
TEST_DEVICES_COVER: set[str] = {"VCU1223813"}
TEST_DEVICES_CLIMATE: set[str] = {"VCU0000341"}

# pylint: disable=protected-access


class TestWeekProfileDataPointDefault:
    """Tests for WeekProfileDataPoint on non-climate devices."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_COVER, True, None, None),
        ],
    )
    async def test_cover_data_point_properties(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test data point on cover device has correct properties."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpCover = cast(CustomDpCover, get_prepared_custom_data_point(central, "VCU1223813", 4))
        data_point = cover.device.week_profile_data_point
        assert data_point is not None
        assert isinstance(data_point, WeekProfileDataPoint)
        assert data_point.schedule_type == ScheduleType.DEFAULT
        assert data_point.max_entries == 24
        assert data_point.min_temp is None
        assert data_point.max_temp is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_default_fire_schedule_updated(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test fire_schedule_updated notifies subscribers."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None

        handler = MagicMock()
        central.event_bus.subscribe(
            event_type=DataPointStateChangedEvent,
            event_key=data_point.unique_id,
            handler=lambda *, event: handler(),
        )
        data_point.fire_schedule_updated()
        await central.looper.block_till_done()
        handler.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_default_properties(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test default data point properties."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None
        assert isinstance(data_point, WeekProfileDataPoint)
        assert data_point.schedule_type == ScheduleType.DEFAULT
        assert data_point.max_entries == 24
        assert data_point.min_temp is None
        assert data_point.max_temp is None
        assert data_point.schedule_channel_address is not None
        assert isinstance(data_point.value, int)
        assert data_point.value >= 0
        assert data_point.usage == DataPointUsage.DATA_POINT

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_default_schedule_property(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test default data point schedule property returns dict."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None
        assert isinstance(data_point.schedule, dict)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_default_schedule_read_write(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test default data point schedule read and write."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None

        schedule_payload = {
            "01_WP_FIXED_HOUR": 7,
            "01_WP_FIXED_MINUTE": 30,
            "01_WP_CONDITION": 0,
            "01_WP_ASTRO_TYPE": 0,
            "01_WP_ASTRO_OFFSET": 0,
            "01_WP_TARGET_CHANNELS": 1,
            "01_WP_WEEKDAY": 2,
            "01_WP_LEVEL": 1.0,
        }
        mock_client.get_paramset = AsyncMock(return_value=schedule_payload)

        schedule = await data_point.get_schedule(force_load=True)
        assert isinstance(schedule, dict)
        assert "entries" in schedule

        # Write schedule using SimpleSchedule Pydantic model
        new_schedule = SimpleSchedule(
            entries={
                1: SimpleScheduleEntry(
                    weekdays=["MONDAY"],
                    time="08:00",
                    target_channels=["1_1"],
                    level=1.0,
                )
            }
        )
        await data_point.set_schedule(schedule_data=new_schedule)  # type: ignore[arg-type]
        mock_client.put_paramset.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_default_target_channels(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test default data point target channels mapping."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None

        target_channels = data_point.available_target_channels
        assert len(target_channels) > 0
        for key, info in target_channels.items():
            # Keys are in "N_M" format
            parts = key.split("_")
            assert len(parts) == 2
            assert parts[0].isdigit()
            assert parts[1].isdigit()
            # Values are TargetChannelInfo
            assert isinstance(info, TargetChannelInfo)
            assert info.name  # non-empty (fallback guarantees this)
            assert info.channel_type in ("primary", "secondary")


class TestWeekProfileDataPointClimateNoDataPoint:
    """Tests that climate devices without WEEK_PROFILE channels don't get data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_CLIMATE, True, None, None),
        ],
    )
    async def test_climate_data_point_resolved_via_schedule_channel_no(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that climate devices resolve schedule channel via schedule_channel_no."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )
        # Climate device has no WEEK_PROFILE channel type but resolves via schedule_channel_no
        assert climate.device.week_profile is not None
        assert isinstance(climate.device.week_profile, ClimateWeekProfile)
        assert climate.device.week_profile.has_schedule is True
        assert climate.device.default_schedule_channel is None
        # Path 2: schedule_channel_no resolves the channel for climate devices
        assert climate.device.week_profile_data_point is not None


class TestScheduleEnabledAndHelpers:
    """Tests for schedule_enabled, set_schedule_enabled, and helper functions."""

    def test_channel_key_to_bitmask_unknown_key(self) -> None:
        """Test channel_key_to_bitmask raises ValueError for unknown keys."""
        with pytest.raises(ValueError, match="Unknown channel key"):
            channel_key_to_bitmask(channel_key="99_99")

    def test_channel_key_to_bitmask_valid_keys(self) -> None:
        """Test channel_key_to_bitmask returns correct bitmask values."""
        assert channel_key_to_bitmask(channel_key="1_1") == 1
        assert channel_key_to_bitmask(channel_key="1_2") == 2
        assert channel_key_to_bitmask(channel_key="2_1") == 8
        assert channel_key_to_bitmask(channel_key="3_1") == 64

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_channel_locks_event_triggers_update(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that a state change on channel locks DP triggers a week profile update event."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None

        # Track update events on the week profile data point
        handler = MagicMock()
        central.event_bus.subscribe(
            event_type=DataPointStateChangedEvent,
            event_key=data_point.unique_id,
            handler=lambda *, event: handler(),
        )

        # Bind a mock locks DP and subscribe to its events
        mock_dp = MagicMock()
        mock_dp.value = 0
        mock_dp.unique_id = "test_locks_dp_id"
        data_point.set_channel_locks_data_point(data_point=mock_dp)

        # Simulate a state change event on the locks DP
        await central.event_bus.publish(
            event=DataPointStateChangedEvent(
                timestamp=datetime.now(tz=UTC),
                unique_id="test_locks_dp_id",
                old_value=0,
                new_value=1,
            ),
        )
        await central.looper.block_till_done()
        handler.assert_called()

    def test_parse_channel_locks_all_enabled(self) -> None:
        """Test parse_channel_locks with bitmask 0 (all channels enabled, inverted logic)."""
        channels = {
            "1_1": TargetChannelInfo(channel_no=4, channel_address="VCU:4", name="Ch4", channel_type="primary"),
            "1_2": TargetChannelInfo(channel_no=5, channel_address="VCU:5", name="Ch5", channel_type="secondary"),
        }
        # bitmask 0 = no bits set → no channels locked → all enabled
        result = parse_channel_locks(locks_value=0, available_channels=channels)
        assert result == {"1_1": True, "1_2": True}

    def test_parse_channel_locks_all_locked(self) -> None:
        """Test parse_channel_locks with all bits set (all channels locked/disabled)."""
        channels = {
            "1_1": TargetChannelInfo(channel_no=4, channel_address="VCU:4", name="Ch4", channel_type="primary"),
            "1_2": TargetChannelInfo(channel_no=5, channel_address="VCU:5", name="Ch5", channel_type="secondary"),
        }
        # bitmask 3 = 0b11 → both bits set → both channels locked (disabled)
        result = parse_channel_locks(locks_value=3, available_channels=channels)
        assert result == {"1_1": False, "1_2": False}

    def test_parse_channel_locks_ignores_unknown_channels(self) -> None:
        """Test parse_channel_locks skips channels not in _CHANNEL_STR_TO_ENUM."""
        channels = {
            "1_1": TargetChannelInfo(channel_no=4, channel_address="VCU:4", name="Ch4", channel_type="primary"),
            "unknown": TargetChannelInfo(channel_no=99, channel_address="VCU:99", name="X", channel_type="primary"),
        }
        # bitmask 0 → channel 1_1 enabled, "unknown" skipped
        result = parse_channel_locks(locks_value=0, available_channels=channels)
        assert result == {"1_1": True}

    def test_parse_channel_locks_partial(self) -> None:
        """Test parse_channel_locks with partial channels locked (inverted logic)."""
        channels = {
            "1_1": TargetChannelInfo(channel_no=4, channel_address="VCU:4", name="Ch4", channel_type="primary"),
            "1_2": TargetChannelInfo(channel_no=5, channel_address="VCU:5", name="Ch5", channel_type="secondary"),
        }
        # bitmask 1 = 0b01 → bit 0 set → channel 1_1 locked (disabled), 1_2 enabled
        result = parse_channel_locks(locks_value=1, available_channels=channels)
        assert result == {"1_1": False, "1_2": True}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_schedule_enabled_all_enabled_when_zero(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test schedule_enabled with bitmask 0 returns all channels enabled (inverted logic)."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None

        mock_dp = MagicMock()
        mock_dp.value = 0  # No bits set → no channels locked → all enabled
        data_point._dp_channel_locks = mock_dp

        result = data_point.schedule_enabled
        assert result is not None
        assert all(v is True for v in result.values())

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_schedule_enabled_none_when_value_is_none(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test schedule_enabled returns None when locks DP value is None."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None
        mock_dp = MagicMock()
        mock_dp.value = None
        data_point._dp_channel_locks = mock_dp
        assert data_point.schedule_enabled is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_schedule_enabled_none_without_locks_dp(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test schedule_enabled returns None when no channel locks DP is bound."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None
        # Unbind channel locks to test None path
        data_point._dp_channel_locks = None
        assert data_point.schedule_enabled is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_schedule_enabled_returns_per_channel_mapping(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test schedule_enabled returns per-channel enabled mapping from bitmask."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None

        # Bind a mock locks DP with a bitmask value
        mock_dp = MagicMock()
        mock_dp.value = 1  # Only channel 1_1 enabled
        data_point._dp_channel_locks = mock_dp

        result = data_point.schedule_enabled
        assert result is not None
        assert isinstance(result, dict)
        # All available target channels should appear in result
        for key in data_point.available_target_channels:
            assert key in result

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_set_schedule_enabled_auto_mode(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_schedule_enabled(enabled=True) sends COMBINED_PARAMETER with AUTO mode."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None
        assert data_point.schedule_channel_address is not None

        mock_client.set_value = AsyncMock()
        await data_point.set_schedule_enabled(enabled=True)

        # All available channels bitmask, mode 2 = AUTO
        all_bitmask = sum(channel_key_to_bitmask(channel_key=key) for key in data_point.available_target_channels)
        mock_client.set_value.assert_called_once_with(
            channel_address=data_point.schedule_channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=Parameter.COMBINED_PARAMETER,
            value=f"WPTCLS={all_bitmask},WPTCL=2",
            wait_for_callback=None,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_set_schedule_enabled_manu_mode(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_schedule_enabled(enabled=False) sends COMBINED_PARAMETER with MANU mode."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None

        mock_client.set_value = AsyncMock()
        await data_point.set_schedule_enabled(enabled=False)

        # All available channels bitmask, mode 0 = MANU
        all_bitmask = sum(channel_key_to_bitmask(channel_key=key) for key in data_point.available_target_channels)
        mock_client.set_value.assert_called_once_with(
            channel_address=data_point.schedule_channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=Parameter.COMBINED_PARAMETER,
            value=f"WPTCLS={all_bitmask},WPTCL=0",
            wait_for_callback=None,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_CLIMATE, True, None, None),
        ],
    )
    async def test_set_schedule_enabled_noop_for_climate(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_schedule_enabled is a no-op for climate week profile data points."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )
        data_point = climate.device.week_profile_data_point
        assert data_point is not None

        mock_client.set_value = AsyncMock()
        await data_point.set_schedule_enabled(enabled=True)

        mock_client.set_value.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_set_schedule_enabled_with_channel_key(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_schedule_enabled with channel_key sends COMBINED_PARAMETER for that channel."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None

        mock_client.set_value = AsyncMock()
        await data_point.set_schedule_enabled(enabled=True, channel_key="1_1")

        # Single COMBINED_PARAMETER call with channel_key bitmask and AUTO mode
        mock_client.set_value.assert_called_once_with(
            channel_address=data_point.schedule_channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=Parameter.COMBINED_PARAMETER,
            value="WPTCLS=1,WPTCL=2",  # bitmask 1 for "1_1", mode 2 = AUTO
            wait_for_callback=None,
        )


class TestWeekProfileDataPointLifecycle:
    """Tests for WeekProfileDataPoint lifecycle and structural properties."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_bidirectional_linkage(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test bidirectional linkage between data point and week profile."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None
        week_profile = switch.device.week_profile
        assert week_profile is not None
        assert isinstance(week_profile, DefaultWeekProfile)
        assert week_profile._week_profile_data_point is data_point

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SWITCH, True, None, None),
        ],
    )
    async def test_slots(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that data point uses __slots__ (no __dict__)."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        data_point = switch.device.week_profile_data_point
        assert data_point is not None
        assert hasattr(data_point, "__dict__") is False
