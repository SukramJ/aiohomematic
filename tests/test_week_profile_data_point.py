# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for WeekProfileDataPoint."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.const import DataPointUsage, ScheduleType
from aiohomematic.model.custom import CustomDpCover, CustomDpRfThermostat, CustomDpSwitch
from aiohomematic.model.schedule_models import SimpleSchedule, SimpleScheduleEntry, TargetChannelInfo
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
        data_point.subscribe_to_data_point_updated(handler=handler, custom_id="test")
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
