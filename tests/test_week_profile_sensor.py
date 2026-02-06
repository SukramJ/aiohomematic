# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for WeekProfileSensor."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.const import DataPointUsage, ScheduleType
from aiohomematic.model.custom import CustomDpCover, CustomDpRfThermostat, CustomDpSwitch
from aiohomematic.model.schedule_models import SimpleSchedule, SimpleScheduleEntry, TargetChannelInfo
from aiohomematic.model.week_profile import ClimateWeekProfile, DefaultWeekProfile
from aiohomematic.model.week_profile_sensor import WeekProfileSensor
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES_SWITCH: set[str] = {"VCU2128127"}
TEST_DEVICES_COVER: set[str] = {"VCU1223813"}
TEST_DEVICES_CLIMATE: set[str] = {"VCU0000341"}

# pylint: disable=protected-access


class TestWeekProfileSensorDefault:
    """Tests for WeekProfileSensor on non-climate devices."""

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
    async def test_cover_sensor_properties(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test sensor on cover device has correct properties."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        cover: CustomDpCover = cast(CustomDpCover, get_prepared_custom_data_point(central, "VCU1223813", 4))
        sensor = cover.device.week_profile_sensor
        assert sensor is not None
        assert isinstance(sensor, WeekProfileSensor)
        assert sensor.schedule_type == ScheduleType.DEFAULT
        assert sensor.max_entries == 24
        assert sensor.min_temp is None
        assert sensor.max_temp is None

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
    async def test_default_sensor_fire_schedule_updated(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test fire_schedule_updated notifies subscribers."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        sensor = switch.device.week_profile_sensor
        assert sensor is not None

        handler = MagicMock()
        sensor.subscribe_to_data_point_updated(handler=handler, custom_id="test")
        sensor.fire_schedule_updated()
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
    async def test_default_sensor_properties(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test default sensor properties."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        sensor = switch.device.week_profile_sensor
        assert sensor is not None
        assert isinstance(sensor, WeekProfileSensor)
        assert sensor.schedule_type == ScheduleType.DEFAULT
        assert sensor.max_entries == 24
        assert sensor.min_temp is None
        assert sensor.max_temp is None
        assert sensor.schedule_channel_address is not None
        assert isinstance(sensor.value, int)
        assert sensor.value >= 0
        assert sensor.usage == DataPointUsage.DATA_POINT

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
    async def test_default_sensor_schedule_property(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test default sensor schedule property returns dict."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        sensor = switch.device.week_profile_sensor
        assert sensor is not None
        assert isinstance(sensor.schedule, dict)

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
    async def test_default_sensor_schedule_read_write(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test default sensor schedule read and write."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        sensor = switch.device.week_profile_sensor
        assert sensor is not None

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

        schedule = await sensor.get_schedule(force_load=True)
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
        await sensor.set_schedule(schedule_data=new_schedule)  # type: ignore[arg-type]
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
    async def test_default_sensor_target_channels(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test default sensor target channels mapping."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        sensor = switch.device.week_profile_sensor
        assert sensor is not None

        target_channels = sensor.available_target_channels
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


class TestWeekProfileSensorClimateNoSensor:
    """Tests that climate devices without WEEK_PROFILE channels don't get sensors."""

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
    async def test_climate_no_sensor_when_no_schedule_channel(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that climate devices without WEEK_PROFILE channel don't get a sensor."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )
        # Climate device has week_profile but no sensor (no WEEK_PROFILE channel)
        assert climate.device.week_profile is not None
        assert isinstance(climate.device.week_profile, ClimateWeekProfile)
        assert climate.device.week_profile.has_schedule is True
        assert climate.device.default_schedule_channel is None
        assert climate.device.week_profile_sensor is None


class TestWeekProfileSensorLifecycle:
    """Tests for WeekProfileSensor lifecycle and structural properties."""

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
    async def test_sensor_bidirectional_linkage(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test bidirectional linkage between sensor and week profile."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        sensor = switch.device.week_profile_sensor
        assert sensor is not None
        week_profile = switch.device.week_profile
        assert week_profile is not None
        assert isinstance(week_profile, DefaultWeekProfile)
        assert week_profile._sensor is sensor

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
    async def test_sensor_slots(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that sensor uses __slots__ (no __dict__)."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        sensor = switch.device.week_profile_sensor
        assert sensor is not None
        assert hasattr(sensor, "__dict__") is False
