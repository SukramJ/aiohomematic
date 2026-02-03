# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Comprehensive tests for week_profile module."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

from aiohomematic.const import (
    DEFAULT_CLIMATE_FILL_TEMPERATURE,
    DataPointCategory,
    ScheduleActorChannel,
    ScheduleField,
    ScheduleProfile,
    WeekdayInt,
    WeekdayStr,
)
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom import CustomDataPoint, CustomDpRfThermostat
from aiohomematic.model.schedule_models import (
    SCHEDULE_DOMAIN_CONTEXT_KEY,
    ClimateSchedule,
    SimpleSchedule,
    SimpleScheduleEntry,
)
from aiohomematic.model.week_profile import (
    ClimateWeekProfile,
    DefaultWeekProfile,
    _bitwise_to_list,
    _convert_minutes_to_time_str,
    _convert_time_str_to_minutes,
    _fillup_weekday_data,
    _filter_profile_entries,
    _filter_schedule_entries,
    _filter_weekday_entries,
    _list_to_bitwise,
    _normalize_weekday_data,
    create_empty_schedule_group,
    create_week_profile,
    identify_base_temperature,
    is_schedule_active,
)
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES_SCHEDULE: set[str] = {"VCU0000341"}


class TestFilterFunctions:
    """Test filter functions for schedule data."""

    def test_filter_profile_entries_empty_data(self):
        """Test filtering profile with empty data."""
        result = _filter_profile_entries(profile_data={})
        assert result == {}

    def test_filter_profile_entries_filters_all_weekdays(self):
        """Test that filtering is applied to all weekdays in profile."""
        profile_data = {
            WeekdayStr.MONDAY: {
                1: {"endtime": "06:00", "temperature": 18.0},
                2: {"endtime": "24:00", "temperature": 18.0},
                3: {"endtime": "24:00", "temperature": 18.0},
            },
            WeekdayStr.TUESDAY: {
                1: {"endtime": "08:00", "temperature": 20.0},
                2: {"endtime": "24:00", "temperature": 20.0},
                3: {"endtime": "24:00", "temperature": 20.0},
            },
        }
        result = _filter_profile_entries(profile_data=profile_data)
        assert len(result[WeekdayStr.MONDAY]) == 2
        assert len(result[WeekdayStr.TUESDAY]) == 2

    def test_filter_schedule_entries_empty_data(self):
        """Test filtering schedule with empty data."""
        result = _filter_schedule_entries(schedule_data={})
        assert result == {}

    def test_filter_schedule_entries_filters_all_profiles(self):
        """Test that filtering is applied to all profiles in schedule."""
        schedule_data = {
            ScheduleProfile.P1: {
                WeekdayStr.MONDAY: {
                    1: {"endtime": "06:00", "temperature": 18.0},
                    2: {"endtime": "24:00", "temperature": 18.0},
                    3: {"endtime": "24:00", "temperature": 18.0},
                },
            },
            ScheduleProfile.P2: {
                WeekdayStr.MONDAY: {
                    1: {"endtime": "08:00", "temperature": 20.0},
                    2: {"endtime": "24:00", "temperature": 20.0},
                    3: {"endtime": "24:00", "temperature": 20.0},
                },
            },
        }
        result = _filter_schedule_entries(schedule_data=schedule_data)
        assert len(result[ScheduleProfile.P1][WeekdayStr.MONDAY]) == 2
        assert len(result[ScheduleProfile.P2][WeekdayStr.MONDAY]) == 2

    def test_filter_weekday_entries_empty_data(self):
        """Test filtering with empty data."""
        result = _filter_weekday_entries(weekday_data={})
        assert result == {}

    def test_filter_weekday_entries_full_13_slots_with_redundant_24_00(self):
        """Test filtering with all 13 slots where 8-13 are 24:00."""
        weekday_data = {}
        for i in range(1, 8):
            weekday_data[i] = {
                "endtime": f"{i * 3:02d}:00",
                "temperature": 20.0,
            }
        for i in range(8, 14):
            weekday_data[i] = {
                "endtime": "24:00",
                "temperature": 18.0,
            }

        result = _filter_weekday_entries(weekday_data=weekday_data)
        # Should keep slots 1-7 and first 24:00 (slot 8)
        assert len(result) == 8

    def test_filter_weekday_entries_multiple_24_00_slots(self):
        """Test filtering removes redundant 24:00 slots, keeps first by slot number."""
        weekday_data = {
            7: {"endtime": "24:00", "temperature": 18.0},
            3: {"endtime": "18:00", "temperature": 21.0},
            5: {"endtime": "24:00", "temperature": 19.0},
            1: {"endtime": "06:00", "temperature": 20.0},
        }
        result = _filter_weekday_entries(weekday_data=weekday_data)
        # Should keep slots 1, 3, and first 24:00 (slot 5, not 7)
        assert len(result) == 3
        assert result[1]["endtime"] == "06:00"
        assert result[2]["endtime"] == "18:00"
        assert result[3]["endtime"] == "24:00"
        # Should keep the temperature from slot 5 (first 24:00 by number)
        assert result[3]["temperature"] == 19.0

    def test_filter_weekday_entries_no_24_00_slots(self):
        """Test filtering when there are no 24:00 slots."""
        weekday_data = {
            1: {"endtime": "06:00", "temperature": 18.0},
            2: {"endtime": "08:00", "temperature": 21.0},
            3: {"endtime": "18:00", "temperature": 18.0},
        }
        result = _filter_weekday_entries(weekday_data=weekday_data)
        assert len(result) == 3
        assert result[1]["endtime"] == "06:00"
        assert result[2]["endtime"] == "08:00"
        assert result[3]["endtime"] == "18:00"

    def test_filter_weekday_entries_single_24_00_slot(self):
        """Test filtering with single 24:00 slot."""
        weekday_data = {
            1: {"endtime": "06:00", "temperature": 18.0},
            2: {"endtime": "24:00", "temperature": 18.0},
        }
        result = _filter_weekday_entries(weekday_data=weekday_data)
        assert len(result) == 2
        assert result[2]["endtime"] == "24:00"


class TestNormalizationFunctions:
    """Test normalization functions."""

    def test_normalize_weekday_data_empty(self):
        """Test normalization with empty data."""
        result = _normalize_weekday_data(weekday_data={})
        assert result == {}

    def test_normalize_weekday_data_fills_to_13_slots(self):
        """Test that missing slots are filled to reach 13 total."""
        weekday_data = {
            1: {"endtime": "06:00", "temperature": 18.0},
            2: {"endtime": "12:00", "temperature": 21.0},
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)
        assert len(result) == 13
        # Slots 3-13 should be filled with 24:00 and last slot's temperature
        for i in range(3, 14):
            assert result[i]["endtime"] == "24:00"
            assert result[i]["temperature"] == 21.0

    def test_normalize_weekday_data_full_example(self):
        """Test complete normalization workflow."""
        weekday_data = {
            "5": {"endtime": "18:00", "temperature": 20.0},
            "1": {"endtime": "06:00", "temperature": 18.0},
            "3": {"endtime": "12:00", "temperature": 22.0},
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)

        # Should be sorted and renumbered
        assert len(result) == 13
        assert result[1]["endtime"] == "06:00"
        assert result[2]["endtime"] == "12:00"
        assert result[3]["endtime"] == "18:00"

        # Slots 4-13 should be filled with 24:00 and temperature from last slot (20.0)
        for i in range(4, 14):
            assert result[i]["endtime"] == "24:00"
            assert result[i]["temperature"] == 20.0

    def test_normalize_weekday_data_sorts_by_endtime(self):
        """Test that slots are sorted chronologically by ENDTIME."""
        weekday_data = {
            3: {"endtime": "18:00", "temperature": 18.0},
            1: {"endtime": "06:00", "temperature": 20.0},
            2: {"endtime": "12:00", "temperature": 21.0},
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)
        assert result[1]["endtime"] == "06:00"
        assert result[2]["endtime"] == "12:00"
        assert result[3]["endtime"] == "18:00"

    def test_normalize_weekday_data_string_keys_to_int(self):
        """Test that string keys are converted to integers."""
        weekday_data = {
            "1": {"endtime": "06:00", "temperature": 18.0},
            "2": {"endtime": "12:00", "temperature": 21.0},
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)
        assert all(isinstance(k, int) for k in result)

    def test_normalize_weekday_data_uses_default_temp_if_missing(self):
        """Test that default temperature is used if last slot has no temperature."""
        weekday_data = {
            1: {"endtime": "06:00"},  # No temperature
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)
        # Filled slots should use DEFAULT_CLIMATE_FILL_TEMPERATURE
        assert result[2]["temperature"] == DEFAULT_CLIMATE_FILL_TEMPERATURE


class TestHelperFunctions:
    """Test helper functions."""

    def test_bitwise_to_list_all_days(self):
        """Test bitwise to list with all weekdays."""
        result = _bitwise_to_list(value=127, enum_class=WeekdayInt)  # 0b1111111
        assert len(result) == 7

    def test_bitwise_to_list_empty(self):
        """Test bitwise to list with zero."""
        result = _bitwise_to_list(value=0, enum_class=WeekdayInt)
        assert result == []

    def test_bitwise_to_list_single_day(self):
        """Test bitwise to list with single day."""
        result = _bitwise_to_list(value=1, enum_class=WeekdayInt)  # Monday
        assert len(result) == 1

    def test_convert_minutes_to_time_str_invalid_type(self):
        """Test that non-int input returns max time."""
        assert _convert_minutes_to_time_str(minutes="invalid") == "24:00"
        assert _convert_minutes_to_time_str(minutes=None) == "24:00"

    def test_convert_minutes_to_time_str_valid(self):
        """Test minutes to time string conversion."""
        assert _convert_minutes_to_time_str(minutes=0) == "00:00"
        assert _convert_minutes_to_time_str(minutes=360) == "06:00"
        assert _convert_minutes_to_time_str(minutes=750) == "12:30"
        assert _convert_minutes_to_time_str(minutes=1440) == "24:00"

    def test_convert_time_str_to_minutes_invalid_format(self):
        """Test that invalid time format raises exception."""
        with pytest.raises(ValidationException):
            _convert_time_str_to_minutes(time_str="25:00")

        with pytest.raises(ValidationException):
            _convert_time_str_to_minutes(time_str="12:60")

        with pytest.raises(ValidationException):
            _convert_time_str_to_minutes(time_str="invalid")

    def test_convert_time_str_to_minutes_valid(self):
        """Test time string to minutes conversion."""
        assert _convert_time_str_to_minutes(time_str="00:00") == 0
        assert _convert_time_str_to_minutes(time_str="06:00") == 360
        assert _convert_time_str_to_minutes(time_str="12:30") == 750
        assert _convert_time_str_to_minutes(time_str="24:00") == 1440

    def test_create_empty_schedule_group_cover(self):
        """Test create_empty_schedule_group for cover."""
        result = create_empty_schedule_group(category=DataPointCategory.COVER)
        assert ScheduleField.LEVEL in result
        assert ScheduleField.LEVEL_2 in result

    def test_create_empty_schedule_group_light(self):
        """Test create_empty_schedule_group for light."""
        result = create_empty_schedule_group(category=DataPointCategory.LIGHT)
        assert ScheduleField.RAMP_TIME_BASE in result
        assert ScheduleField.RAMP_TIME_FACTOR in result
        assert ScheduleField.LEVEL in result

    def test_create_empty_schedule_group_no_category(self):
        """Test create_empty_schedule_group with no category."""
        result = create_empty_schedule_group()
        assert ScheduleField.WEEKDAY in result
        assert result[ScheduleField.WEEKDAY] == []
        assert result[ScheduleField.TARGET_CHANNELS] == []

    def test_create_empty_schedule_group_switch(self):
        """Test create_empty_schedule_group for switch."""
        result = create_empty_schedule_group(category=DataPointCategory.SWITCH)
        assert ScheduleField.DURATION_BASE in result
        assert ScheduleField.DURATION_FACTOR in result
        assert ScheduleField.LEVEL in result

    def test_create_empty_schedule_group_valve(self):
        """Test create_empty_schedule_group for valve."""
        result = create_empty_schedule_group(category=DataPointCategory.VALVE)
        assert ScheduleField.LEVEL in result

    def test_fillup_weekday_data(self):
        """Test fillup weekday data."""
        weekday_data = {
            1: {"endtime": "06:00", "temperature": 18.0},
        }
        result = _fillup_weekday_data(base_temperature=20.0, weekday_data=weekday_data)

        # Should fill missing slots 2-13
        assert len(result) == 13
        for i in range(2, 14):
            assert result[i]["endtime"] == "24:00"
            assert result[i]["temperature"] == 20.0

    def test_identify_base_temperature_base_temp_dominates(self):
        """Test _identify_base_temperature where base temperature has most time."""
        # 18.0° for 1020 minutes (06:00 + 540 min + 120 min)
        # 21.0° for 420 minutes (120 min + 300 min)
        weekday_data = {
            1: {"endtime": "06:00", "temperature": 18.0},
            2: {"endtime": "08:00", "temperature": 21.0},
            3: {"endtime": "17:00", "temperature": 18.0},
            4: {"endtime": "22:00", "temperature": 21.0},
            5: {"endtime": "24:00", "temperature": 18.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        assert result == 18.0

    def test_identify_base_temperature_complex_schedule(self):
        """Test _identify_base_temperature with complex schedule."""
        # 17.0° for 300 minutes (00:00-05:00)
        # 20.0° for 180 minutes (05:00-08:00)
        # 18.0° for 540 minutes (08:00-17:00)
        # 22.0° for 300 minutes (17:00-22:00)
        # 18.0° for 120 minutes (22:00-24:00)
        # Total: 18.0° = 660 minutes (most), 17.0° = 300, 20.0° = 180, 22.0° = 300
        weekday_data = {
            1: {"endtime": "05:00", "temperature": 17.0},
            2: {"endtime": "08:00", "temperature": 20.0},
            3: {"endtime": "17:00", "temperature": 18.0},
            4: {"endtime": "22:00", "temperature": 22.0},
            5: {"endtime": "24:00", "temperature": 18.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        assert result == 18.0

    def test_identify_base_temperature_empty_data(self):
        """Test _identify_base_temperature with empty data."""
        result = identify_base_temperature(weekday_data={})
        assert result is DEFAULT_CLIMATE_FILL_TEMPERATURE

    def test_identify_base_temperature_multiple_temperatures(self):
        """Test _identify_base_temperature with multiple different temperatures."""
        # 15.0° for 360 minutes (00:00-06:00)
        # 18.0° for 120 minutes (06:00-08:00)
        # 21.0° for 960 minutes (08:00-24:00)
        weekday_data = {
            1: {"endtime": "06:00", "temperature": 15.0},
            2: {"endtime": "08:00", "temperature": 18.0},
            3: {"endtime": "24:00", "temperature": 21.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        assert result == 21.0

    def test_identify_base_temperature_single_temperature(self):
        """Test _identify_base_temperature with single temperature all day."""
        weekday_data = {
            1: {"endtime": "24:00", "temperature": 18.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        assert result == 18.0

    def test_identify_base_temperature_two_temperatures_equal_time(self):
        """Test _identify_base_temperature with two temperatures having equal time."""
        weekday_data = {
            1: {"endtime": "12:00", "temperature": 18.0},
            2: {"endtime": "24:00", "temperature": 21.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        # Both have 720 minutes (12 hours), max() will return one of them
        assert result in [18.0, 21.0]

    def test_identify_base_temperature_unsorted_slots(self):
        """Test _identify_base_temperature with unsorted slot numbers."""
        # The function should sort by slot number
        weekday_data = {
            5: {"endtime": "24:00", "temperature": 18.0},
            1: {"endtime": "06:00", "temperature": 18.0},
            3: {"endtime": "17:00", "temperature": 18.0},
            2: {"endtime": "08:00", "temperature": 21.0},
            4: {"endtime": "22:00", "temperature": 21.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        assert result == 18.0

    def test_is_schedule_active_both_missing(self):
        """Test is_schedule_active with both fields missing."""
        group_data = {
            ScheduleField.WEEKDAY: [],
            ScheduleField.TARGET_CHANNELS: [],
        }
        assert is_schedule_active(group_data=group_data) is False

    def test_is_schedule_active_missing_channels(self):
        """Test is_schedule_active with missing channels."""
        group_data = {
            ScheduleField.WEEKDAY: [WeekdayInt.MONDAY],
            ScheduleField.TARGET_CHANNELS: [],
        }
        assert is_schedule_active(group_data=group_data) is False

    def test_is_schedule_active_missing_weekday(self):
        """Test is_schedule_active with missing weekday."""
        group_data = {
            ScheduleField.WEEKDAY: [],
            ScheduleField.TARGET_CHANNELS: [ScheduleActorChannel.CHANNEL_1_1],
        }
        assert is_schedule_active(group_data=group_data) is False

    def test_is_schedule_active_with_all_fields(self):
        """Test is_schedule_active with complete data."""
        group_data = {
            ScheduleField.WEEKDAY: [WeekdayInt.MONDAY],
            ScheduleField.TARGET_CHANNELS: [ScheduleActorChannel.CHANNEL_1_1],
        }
        assert is_schedule_active(group_data=group_data) is True

    def test_list_to_bitwise_all_days(self):
        """Test list to bitwise with all weekdays."""
        all_days = list(WeekdayInt)
        result = _list_to_bitwise(items=all_days)
        assert result == 127

    def test_list_to_bitwise_empty(self):
        """Test list to bitwise with empty list."""
        result = _list_to_bitwise(items=[])
        assert result == 0

    def test_list_to_bitwise_single_day(self):
        """Test list to bitwise with single day."""
        result = _list_to_bitwise(items=[WeekdayInt.MONDAY])
        assert result == 2  # MONDAY = 2

    # NOTE: test_sort_simple_weekday_data was removed because _sort_simple_weekday_data
    # function was removed from week_profile.py during simple schedule optimization.
    # The sorting logic is now internal to the simple schedule conversion functions.


class TestWeekProfileCreation:
    """Test week profile creation."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_create_week_profile_climate(self, central_client_factory_with_homegear_client):
        """Test creating climate week profile."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        profile = create_week_profile(data_point=climate)
        assert isinstance(profile, ClimateWeekProfile)

    def test_create_week_profile_non_climate(self):
        """Test creating non-climate week profile."""
        # Create a mock data point with non-climate category
        dp = MagicMock(spec=CustomDataPoint)
        dp.category = DataPointCategory.SWITCH

        profile = create_week_profile(data_point=dp)
        assert isinstance(profile, DefaultWeekProfile)


class TestScheduleOperations:
    """Test schedule operations like copy, simple schedule."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_copy_schedule_profile_same_device_validation(self, central_client_factory_with_homegear_client):
        """Test that copying same profile to itself on same device raises error."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Should raise ValidationException
        with pytest.raises(ValidationException):
            await climate.copy_schedule_profile(
                source_profile=ScheduleProfile.P1,
                target_profile=ScheduleProfile.P1,  # Same profile
                target_climate_data_point=None,  # Same device
            )

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_simple_schedule_validation_base_temp_out_of_range(self, central_client_factory_with_homegear_client):
        """Test that simple schedule validates base temperature range."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        simple_data = {
            "base_temperature": 999.0,
            "periods": [  # Way out of range
                {
                    "starttime": "06:00",
                    "endtime": "08:00",
                    "temperature": 20.0,
                }
            ],
        }

        # Should raise ValidationException for out of range base temperature
        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=simple_data,
            )

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_simple_schedule_validation_missing_endtime(self, central_client_factory_with_homegear_client):
        """Test that simple schedule validates required ENDTIME."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        simple_data = {
            "base_temperature": 18.0,
            "periods": [
                {
                    "starttime": "06:00",
                    # Missing ENDTIME
                    "temperature": 20.0,
                }
            ],
        }

        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=simple_data,
            )

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_simple_schedule_validation_missing_starttime(self, central_client_factory_with_homegear_client):
        """Test that simple schedule validates required fields."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        simple_data = {
            "base_temperature": 18.0,
            "periods": [
                {
                    # Missing STARTTIME
                    "endtime": "08:00",
                    "temperature": 20.0,
                }
            ],
        }

        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=simple_data,
            )

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_simple_schedule_validation_missing_temperature(self, central_client_factory_with_homegear_client):
        """Test that simple schedule validates required TEMPERATURE."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        simple_data = {
            "base_temperature": 18.0,
            "periods": [
                {
                    "starttime": "06:00",
                    "endtime": "08:00",
                    # Missing TEMPERATURE
                }
            ],
        }

        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=simple_data,
            )

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_simple_schedule_validation_overlapping_periods(self, central_client_factory_with_homegear_client):
        """Test that simple schedule validates non-overlapping periods."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        simple_data = {
            "base_temperature": 18.0,
            "periods": [
                {
                    "starttime": "06:00",
                    "endtime": "10:00",
                    "temperature": 20.0,
                },
                {
                    "starttime": "08:00",  # Overlaps with previous!
                    "endtime": "12:00",
                    "temperature": 21.0,
                },
            ],
        }

        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=simple_data,
            )

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_simple_schedule_validation_start_after_end(self, central_client_factory_with_homegear_client):
        """Test that simple schedule validates start before end."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        simple_data = {
            "base_temperature": 18.0,
            "periods": [
                {
                    "starttime": "08:00",
                    "endtime": "06:00",  # End before start!
                    "temperature": 20.0,
                }
            ],
        }

        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=simple_data,
            )

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_simple_schedule_validation_temp_out_of_range(self, central_client_factory_with_homegear_client):
        """Test that simple schedule validates temperature range."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        simple_data = {
            "base_temperature": 18.0,
            "periods": [
                {
                    "starttime": "06:00",
                    "endtime": "08:00",
                    "temperature": 999.0,  # Out of range
                }
            ],
        }

        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=simple_data,
            )


class TestDefaultWeekProfile:
    """Test DefaultWeekProfile for non-climate devices."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_default_week_profile_empty_schedule_group(self, central_client_factory_with_homegear_client):
        """Test empty_schedule_group for different categories."""
        # Test that different categories return appropriate empty schedule groups
        switch_empty = create_empty_schedule_group(category=DataPointCategory.SWITCH)
        assert ScheduleField.LEVEL in switch_empty
        assert ScheduleField.DURATION_BASE in switch_empty

        light_empty = create_empty_schedule_group(category=DataPointCategory.LIGHT)
        assert ScheduleField.LEVEL in light_empty
        assert ScheduleField.RAMP_TIME_BASE in light_empty

        cover_empty = create_empty_schedule_group(category=DataPointCategory.COVER)
        assert ScheduleField.LEVEL in cover_empty
        assert ScheduleField.LEVEL_2 in cover_empty

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_default_week_profile_unsupported_device(self, central_client_factory_with_homegear_client):
        """Test DefaultWeekProfile with device that doesn't support schedules."""
        # This would require a mock device that doesn't support schedules
        # Skipping for now as it requires complex setup


class TestClimateWeekProfileIntegration:
    """Integration tests for ClimateWeekProfile async methods."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_available_schedule_profiles_property(self, central_client_factory_with_homegear_client):
        """Test available_schedule_profiles property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule()

        # Access property
        available_profiles = climate.available_schedule_profiles
        assert isinstance(available_profiles, tuple)
        assert len(available_profiles) > 0

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_copy_schedule(self, central_client_factory_with_homegear_client):
        """Test copying schedule between devices."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Copy to same device should work if profile count matches
        await climate.copy_schedule(target_climate_data_point=climate)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_copy_schedule_profile_different_profiles(self, central_client_factory_with_homegear_client):
        """Test copying schedule profile to different profile on same device."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Copy P1 to P2 on same device
        await climate.copy_schedule_profile(
            source_profile=ScheduleProfile.P1, target_profile=ScheduleProfile.P2, target_climate_data_point=None
        )

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_get_schedule(self, central_client_factory_with_homegear_client):
        """Test getting complete schedule."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Get schedule without forcing load (uses cache)
        schedule = await climate.get_schedule()
        assert isinstance(schedule, dict)
        assert "P1" in schedule

        # Get schedule with force_load=True
        schedule_forced = await climate.get_schedule(force_load=True)
        assert isinstance(schedule_forced, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_get_schedule_profile(self, central_client_factory_with_homegear_client):
        """Test getting schedule profile."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Get profile
        profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert isinstance(profile_data, dict)
        assert "MONDAY" in profile_data

        # Get with force_load
        profile_data_forced = await climate.get_schedule_profile(profile=ScheduleProfile.P1, force_load=True)
        assert isinstance(profile_data_forced, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_get_schedule_weekday(self, central_client_factory_with_homegear_client):
        """Test getting schedule profile weekday."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Get weekday data
        weekday_data = await climate.get_schedule_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY)
        assert isinstance(weekday_data, dict)
        assert "base_temperature" in weekday_data
        assert "periods" in weekday_data

        # Get with force_load
        weekday_data_forced = await climate.get_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, force_load=True
        )
        assert isinstance(weekday_data_forced, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_schedule_property(self, central_client_factory_with_homegear_client):
        """Test schedule property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Access property - returns JSON-serializable dict
        schedule = climate.schedule
        assert isinstance(schedule, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_set_schedule(self, central_client_factory_with_homegear_client):
        """Test setting complete schedule."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Get existing schedule
        schedule = await climate.get_schedule()

        # Set schedule (same data to avoid breaking things)
        await climate.set_schedule(schedule_data=schedule)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_set_schedule_profile(self, central_client_factory_with_homegear_client):
        """Test setting schedule profile."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Get existing profile
        profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Set profile back (validation always happens with Pydantic models)
        await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=profile_data)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_set_simple_schedule_profile(self, central_client_factory_with_homegear_client):
        """Test setting simple schedule profile."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create simple schedule data
        simple_profile_data = {
            WeekdayStr.MONDAY: {
                "base_temperature": 18.0,
                "periods": [
                    {
                        "starttime": "06:00",
                        "endtime": "22:00",
                        "temperature": 21.0,
                    }
                ],
            },
            WeekdayStr.TUESDAY: {
                "base_temperature": 18.0,
                "periods": [
                    {
                        "starttime": "06:00",
                        "endtime": "22:00",
                        "temperature": 21.0,
                    }
                ],
            },
        }

        # Set simple schedule
        await climate.set_schedule_profile(profile=ScheduleProfile.P2, profile_data=simple_profile_data)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_set_simple_schedule_weekday(self, central_client_factory_with_homegear_client):
        """Test setting simple schedule profile weekday."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create simple weekday data
        simple_weekday_data = {
            "base_temperature": 18.0,
            "periods": [
                {
                    "starttime": "06:00",
                    "endtime": "22:00",
                    "temperature": 21.0,
                }
            ],
        }

        # Set simple weekday schedule
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P2,
            weekday=WeekdayStr.WEDNESDAY,
            weekday_data=simple_weekday_data,
        )


class TestDefaultWeekProfileConversion:
    """Test DefaultWeekProfile conversion methods with SimpleSchedule format."""

    def test_convert_dict_to_raw_schedule_switch(self):
        """Test converting SimpleSchedule to raw format."""
        schedule_data = SimpleSchedule(
            entries={
                1: SimpleScheduleEntry(
                    weekdays=["MONDAY", "TUESDAY"],
                    time="10:30",
                    target_channels=["1_1"],
                    level=1.0,
                )
            }
        )

        result = DefaultWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)

        assert "01_WP_WEEKDAY" in result
        assert "01_WP_LEVEL" in result
        assert "01_WP_FIXED_HOUR" in result
        assert "01_WP_FIXED_MINUTE" in result
        assert result["01_WP_WEEKDAY"] == _list_to_bitwise(items=[WeekdayInt.MONDAY, WeekdayInt.TUESDAY])
        assert result["01_WP_LEVEL"] == 1.0
        assert result["01_WP_FIXED_HOUR"] == 10
        assert result["01_WP_FIXED_MINUTE"] == 30

    def test_convert_raw_to_dict_schedule(self):
        """Test converting raw schedule to SimpleSchedule format."""
        raw_schedule = {
            "01_WP_WEEKDAY": 6,  # MONDAY + TUESDAY
            "01_WP_TARGET_CHANNELS": 1,  # CHANNEL_1_1
            "01_WP_LEVEL": 1.0,
            "01_WP_FIXED_HOUR": 10,
            "01_WP_FIXED_MINUTE": 30,
            "01_WP_CONDITION": 0,  # FIXED_TIME
            "01_WP_ASTRO_TYPE": 0,  # SUNRISE
            "01_WP_ASTRO_OFFSET": 0,
            "INVALID_FORMAT": 42,  # Should be skipped
            "01_INVALID": 42,  # Should be skipped
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert isinstance(result, SimpleSchedule)
        assert 1 in result.entries
        entry = result.entries[1]
        assert "MONDAY" in entry.weekdays
        assert "TUESDAY" in entry.weekdays
        assert entry.time == "10:30"
        assert entry.level == 1.0
        assert entry.condition == "fixed_time"

    def test_convert_raw_to_dict_schedule_with_astro(self):
        """Test converting raw schedule with astro condition to SimpleSchedule."""
        raw_schedule = {
            "01_WP_WEEKDAY": 2,  # MONDAY
            "01_WP_TARGET_CHANNELS": 1,  # CHANNEL_1_1
            "01_WP_LEVEL": 0.5,
            "01_WP_FIXED_HOUR": 7,
            "01_WP_FIXED_MINUTE": 0,
            "01_WP_ASTRO_TYPE": 1,  # SUNSET
            "01_WP_CONDITION": 1,  # ASTRO
            "01_WP_ASTRO_OFFSET": 30,
            "01_WP_DURATION_BASE": 1,  # SEC_1
            "01_WP_DURATION_FACTOR": 10,
            "01_WP_RAMP_TIME_BASE": 1,  # SEC_1
            "01_WP_RAMP_TIME_FACTOR": 2,
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert isinstance(result, SimpleSchedule)
        assert 1 in result.entries
        entry = result.entries[1]
        assert entry.condition == "astro"
        assert entry.astro_type == "sunset"
        assert entry.astro_offset_minutes == 30
        assert entry.duration == "10s"
        assert entry.ramp_time == "2s"

    def test_convert_schedule_entries(self):
        """Test _convert_schedule_entries filtering."""
        raw_values = {
            "01_WP_WEEKDAY": 127,
            "01_WP_LEVEL": 1.0,
            "01_WP_FIXED_HOUR": 12,
            "02_WP_WEEKDAY": 64,
            "SOME_OTHER_PARAM": "value",
            "UNRELATED": 42,
        }

        result = DefaultWeekProfile._convert_schedule_entries(values=raw_values)

        # Should only include WP entries
        assert "01_WP_WEEKDAY" in result
        assert "01_WP_LEVEL" in result
        assert "01_WP_FIXED_HOUR" in result
        assert "02_WP_WEEKDAY" in result
        assert "SOME_OTHER_PARAM" not in result
        assert "UNRELATED" not in result
        assert result["01_WP_WEEKDAY"] == 127
        assert result["01_WP_LEVEL"] == 1.0

    def test_convert_schedule_entries_with_floats(self):
        """Test _convert_schedule_entries with float conversion."""
        raw_values = {
            "01_WP_LEVEL": 1.5,  # Already float
            "02_WP_LEVEL": 2,  # Int should stay int
        }

        result = DefaultWeekProfile._convert_schedule_entries(values=raw_values)
        assert result["01_WP_LEVEL"] == 1.5
        assert result["02_WP_LEVEL"] == 2

    def test_simple_schedule_duration_format(self):
        """Test duration and ramp_time format validation."""
        # Valid durations
        entry = SimpleScheduleEntry(
            weekdays=["MONDAY"],
            time="07:30",
            target_channels=["1_1"],
            level=0.5,
            duration="10s",
            ramp_time="500ms",
        )
        assert entry.duration == "10s"
        assert entry.ramp_time == "500ms"

        # Invalid duration format
        with pytest.raises(ValueError):
            SimpleScheduleEntry(
                weekdays=["MONDAY"],
                time="07:30",
                target_channels=["1_1"],
                level=0.5,
                duration="invalid",
            )

    def test_simple_schedule_entry_astro_validation(self):
        """Test that astro_type is required when condition uses astro."""
        # Valid: fixed_time without astro_type
        entry = SimpleScheduleEntry(
            weekdays=["MONDAY"],
            time="07:30",
            target_channels=["1_1"],
            level=0.5,
            condition="fixed_time",
        )
        assert entry.astro_type is None

        # Valid: astro with astro_type
        entry = SimpleScheduleEntry(
            weekdays=["MONDAY"],
            time="07:30",
            target_channels=["1_1"],
            level=0.5,
            condition="astro",
            astro_type="sunrise",
        )
        assert entry.astro_type == "sunrise"

        # Invalid: astro without astro_type
        with pytest.raises(ValueError):
            SimpleScheduleEntry(
                weekdays=["MONDAY"],
                time="07:30",
                target_channels=["1_1"],
                level=0.5,
                condition="astro",
            )

    def test_simple_schedule_entry_validation(self):
        """Test that SimpleScheduleEntry validates input correctly."""
        # Valid entry
        entry = SimpleScheduleEntry(
            weekdays=["MONDAY"],
            time="07:30",
            target_channels=["1_1"],
            level=0.5,
        )
        assert entry.weekdays == ["MONDAY"]
        assert entry.time == "07:30"
        assert entry.level == 0.5

        # Invalid weekday
        with pytest.raises(ValueError):
            SimpleScheduleEntry(
                weekdays=["INVALID"],
                time="07:30",
                target_channels=["1_1"],
                level=0.5,
            )

        # Invalid time format
        with pytest.raises(ValueError):
            SimpleScheduleEntry(
                weekdays=["MONDAY"],
                time="25:00",
                target_channels=["1_1"],
                level=0.5,
            )

        # Invalid channel format
        with pytest.raises(ValueError):
            SimpleScheduleEntry(
                weekdays=["MONDAY"],
                time="07:30",
                target_channels=["9_5"],
                level=0.5,
            )

        # Level out of range
        with pytest.raises(ValueError):
            SimpleScheduleEntry(
                weekdays=["MONDAY"],
                time="07:30",
                target_channels=["1_1"],
                level=1.5,
            )


class TestClimateWeekProfileConversion:
    """Test ClimateWeekProfile conversion methods."""

    def test_convert_dict_to_raw_schedule(self):
        """Test converting climate schedule dict to raw format."""
        schedule_data = {
            ScheduleProfile.P1: {
                WeekdayStr.MONDAY: {
                    1: {
                        "temperature": 20.0,
                        "endtime": "06:00",
                    }
                }
            }
        }

        result = ClimateWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)

        assert "P1_TEMPERATURE_MONDAY_1" in result
        assert "P1_ENDTIME_MONDAY_1" in result
        assert result["P1_TEMPERATURE_MONDAY_1"] == 20.0
        assert result["P1_ENDTIME_MONDAY_1"] == 360  # 6 hours * 60 minutes

    def test_convert_dict_to_raw_schedule_invalid_profile_name(self):
        """Test that invalid profile names raise ValidationException."""
        # Create a schedule with invalid profile/weekday/slot combination
        schedule_data = {
            ScheduleProfile.P1: {
                WeekdayStr.MONDAY: {
                    999: {  # Invalid slot number
                        "temperature": 20.0,
                        "endtime": "06:00",
                    }
                }
            }
        }

        with pytest.raises(ValidationException):
            ClimateWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)

    def test_convert_raw_to_dict_schedule(self):
        """Test converting raw climate schedule to dict format."""
        raw_schedule = {
            "P1_TEMPERATURE_MONDAY_1": 20.0,
            "P1_ENDTIME_MONDAY_1": 360,
            "P1_TEMPERATURE_TUESDAY_1": 21.0,
            "P1_ENDTIME_TUESDAY_1": 420,
            "INVALID_FORMAT": 42,  # Should be skipped
            "P1_TEMP_MON": 42,  # Should be skipped (not 4 parts)
        }

        result = ClimateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert ScheduleProfile.P1 in result
        assert WeekdayStr.MONDAY in result[ScheduleProfile.P1]
        assert WeekdayStr.TUESDAY in result[ScheduleProfile.P1]
        assert 1 in result[ScheduleProfile.P1][WeekdayStr.MONDAY]
        assert result[ScheduleProfile.P1][WeekdayStr.MONDAY][1]["temperature"] == 20.0
        assert result[ScheduleProfile.P1][WeekdayStr.MONDAY][1]["endtime"] == "06:00"
        assert result[ScheduleProfile.P1][WeekdayStr.TUESDAY][1]["temperature"] == 21.0
        assert result[ScheduleProfile.P1][WeekdayStr.TUESDAY][1]["endtime"] == "07:00"

    def test_convert_raw_to_dict_schedule_invalid_entries(self):
        """Test that invalid raw entries are gracefully skipped."""
        raw_schedule = {
            "INVALID_PROFILE_TEMPERATURE_MONDAY_1": 20.0,  # Invalid profile
            "P1_INVALID_TYPE_MONDAY_1": 20.0,  # Invalid slot type
            "P1_TEMPERATURE_INVALID_DAY_1": 20.0,  # Invalid weekday
            "P1_TEMPERATURE_MONDAY_INVALID": 20.0,  # Invalid slot number
        }

        result = ClimateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        # Should return empty dict as all entries are invalid
        assert result == {}


class TestErrorPaths:
    """Test error paths and edge cases."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_get_schedule_force_load_empty_cache(self, central_client_factory_with_homegear_client):
        """Test get_schedule when cache is empty and force_load is False."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Clear cache
        if climate.device.week_profile:
            climate.device.week_profile._schedule_cache = {}

        # Get schedule without force_load - should load from device
        schedule = await climate.get_schedule()
        assert isinstance(schedule, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_get_schedule_profile_empty_cache(self, central_client_factory_with_homegear_client):
        """Test get_schedule_profile when cache is empty."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Clear cache
        if climate.device.week_profile:
            climate.device.week_profile._schedule_cache = {}

        # Get profile - should load from device
        profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert isinstance(profile_data, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_get_schedule_weekday_empty_cache(self, central_client_factory_with_homegear_client):
        """Test get_schedule_weekday when cache is empty."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Clear cache
        if climate.device.week_profile:
            climate.device.week_profile._schedule_cache = {}

        # Get weekday - should load from device
        weekday_data = await climate.get_schedule_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY)
        assert isinstance(weekday_data, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_set_schedule_weekday_cache_update(self, central_client_factory_with_homegear_client):
        """Test set_schedule_weekday updates cache via CONFIG_PENDING."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create new weekday data in Simple format
        weekday_data = {
            "base_temperature": 18.0,
            "periods": [
                {"starttime": "06:00", "endtime": "22:00", "temperature": 21.0},
            ],
        }

        # Set weekday data
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P3, weekday=WeekdayStr.FRIDAY, weekday_data=weekday_data
        )

        # Note: With pessimistic cache and mock client, the cache won't be updated immediately.
        # We verify the operation succeeded by checking that put_paramset was called.
        # In real scenarios with a CCU, CONFIG_PENDING would trigger cache reload with updated data.

        # Verify operation completed successfully - mock should have received put_paramset call
        assert mock_client.put_paramset.called

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_set_schedule_weekday_no_validation(self, central_client_factory_with_homegear_client):
        """Test set_schedule_weekday with validation disabled."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create weekday data in Simple format (base temperature only, no heating periods)
        weekday_data = {
            "base_temperature": 18.0,
            "periods": [],
        }

        # Set weekday data (validation always happens with Pydantic)
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P2,
            weekday=WeekdayStr.SATURDAY,
            weekday_data=weekday_data,
        )


class TestDefaultWeekProfileAdditionalEdgeCases:
    """Test additional edge cases for DefaultWeekProfile with SimpleSchedule format."""

    def test_convert_dict_to_raw_schedule_with_all_field_types(self):
        """Test converting SimpleSchedule with all supported field types to raw format."""
        schedule_data = SimpleSchedule(
            entries={
                1: SimpleScheduleEntry(
                    weekdays=["MONDAY"],
                    time="12:30",
                    target_channels=["1_1"],
                    level=0.5,
                    condition="astro",
                    astro_type="sunset",
                    astro_offset_minutes=30,
                    duration="10min",
                    ramp_time="5s",
                )
            }
        )

        result = DefaultWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)

        assert result["01_WP_ASTRO_TYPE"] == 1  # AstroType.SUNSET
        assert result["01_WP_CONDITION"] == 1  # ScheduleCondition.ASTRO
        assert result["01_WP_ASTRO_OFFSET"] == 30
        assert result["01_WP_FIXED_HOUR"] == 12
        assert result["01_WP_FIXED_MINUTE"] == 30
        # Duration 10min = TimeBase.MIN_1 (4) + factor 10
        assert result["01_WP_DURATION_BASE"] == 4  # TimeBase.MIN_1
        assert result["01_WP_DURATION_FACTOR"] == 10
        # Ramp time 5s = TimeBase.SEC_1 (1) + factor 5
        assert result["01_WP_RAMP_TIME_BASE"] == 1  # TimeBase.SEC_1
        assert result["01_WP_RAMP_TIME_FACTOR"] == 5

    def test_convert_dict_to_raw_schedule_with_level_2(self):
        """Test converting SimpleSchedule with LEVEL_2 (for covers)."""
        schedule_data = SimpleSchedule(
            entries={
                1: SimpleScheduleEntry(
                    weekdays=["MONDAY"],
                    time="08:00",
                    target_channels=["1_1"],
                    level=0.5,
                    level_2=0.75,
                )
            }
        )

        result = DefaultWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)
        assert "01_WP_LEVEL" in result
        assert "01_WP_LEVEL_2" in result
        assert result["01_WP_LEVEL"] == 0.5
        assert result["01_WP_LEVEL_2"] == 0.75

    def test_convert_raw_to_dict_schedule_filters_inactive(self):
        """Test that inactive schedules (no weekdays/channels) are filtered."""
        # Schedule with no weekdays or channels should be filtered out
        raw_schedule = {
            "01_WP_LEVEL": 1.0,
            "01_WP_FIXED_HOUR": 10,
            "01_WP_FIXED_MINUTE": 0,
            # Missing WEEKDAY and TARGET_CHANNELS - should be inactive
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        # Inactive schedules are filtered out
        assert isinstance(result, SimpleSchedule)
        assert 1 not in result.entries

    def test_convert_raw_to_dict_schedule_with_level_2(self):
        """Test converting raw schedule with LEVEL_2 to SimpleSchedule."""
        raw_schedule = {
            "01_WP_WEEKDAY": 2,  # MONDAY
            "01_WP_TARGET_CHANNELS": 1,  # CHANNEL_1_1
            "01_WP_LEVEL": 0.5,
            "01_WP_LEVEL_2": 0.75,
            "01_WP_FIXED_HOUR": 8,
            "01_WP_FIXED_MINUTE": 0,
            "01_WP_CONDITION": 0,
            "01_WP_ASTRO_TYPE": 0,
            "01_WP_ASTRO_OFFSET": 0,
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert isinstance(result, SimpleSchedule)
        assert 1 in result.entries
        assert result.entries[1].level == 0.5
        assert result.entries[1].level_2 == 0.75

    def test_convert_raw_to_dict_schedule_with_multiple_channels(self):
        """Test converting raw schedule with multiple TARGET_CHANNELS."""
        raw_schedule = {
            "01_WP_WEEKDAY": 2,  # MONDAY
            "01_WP_TARGET_CHANNELS": 3,  # CHANNEL_1_1 + CHANNEL_1_2
            "01_WP_LEVEL": 1.0,
            "01_WP_FIXED_HOUR": 10,
            "01_WP_FIXED_MINUTE": 0,
            "01_WP_CONDITION": 0,
            "01_WP_ASTRO_TYPE": 0,
            "01_WP_ASTRO_OFFSET": 0,
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert isinstance(result, SimpleSchedule)
        assert 1 in result.entries
        # Channels 1_1 and 1_2 should be in the list
        assert "1_1" in result.entries[1].target_channels
        assert "1_2" in result.entries[1].target_channels


class TestClimateWeekProfileAdditionalEdgeCases:
    """Test additional edge cases for ClimateWeekProfile."""

    def test_convert_raw_to_dict_schedule_with_int_endtime(self):
        """Test that ENDTIME as int is converted to time string."""
        raw_schedule = {
            "P1_ENDTIME_MONDAY_1": 360,  # 6 hours * 60 minutes
        }

        result = ClimateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert result[ScheduleProfile.P1][WeekdayStr.MONDAY][1]["endtime"] == "06:00"

    def test_convert_raw_to_dict_schedule_with_invalid_slot_number_str(self):
        """Test that invalid slot number strings are skipped."""
        raw_schedule = {
            "P1_TEMPERATURE_MONDAY_ABC": 20.0,  # Invalid slot number
        }

        result = ClimateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        # Should return empty dict as entry is invalid
        assert result == {}

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_set_schedule_cache_no_change(self, central_client_factory_with_homegear_client):
        """Test set_schedule when cache doesn't change."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Get current schedule
        schedule = await climate.get_schedule()

        # Set same schedule again (cache shouldn't trigger event)
        await climate.set_schedule(schedule_data=schedule)


class TestPropertyAccessAndValidation:
    """Test property access and validation methods."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_has_schedule_property(self, central_client_factory_with_homegear_client):
        """Test has_schedule property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Check has_schedule property
        if climate.device.week_profile:
            supports = climate.device.week_profile.has_schedule
            assert isinstance(supports, bool)
            assert supports is True  # VCU0000341 supports schedules

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_schedule_channel_address_property(self, central_client_factory_with_homegear_client):
        """Test schedule_channel_address property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Access schedule channel address
        if climate.device.week_profile:
            sca = climate.device.week_profile.schedule_channel_address
            assert sca is not None
            assert isinstance(sca, str)
            assert "VCU0000341" in sca

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_schedule_property_returns_filtered_data(self, central_client_factory_with_homegear_client):
        """Test that schedule property returns filtered data."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule()

        # Access schedule property directly - returns JSON-serializable dict
        schedule = climate.schedule
        assert isinstance(schedule, dict)
        # Schedule is now a dict with periods instead of 13-slot structure
        # Verify we have valid data
        for profile_data in schedule.values():
            for weekday_data in profile_data.values():
                # weekday_data is dict with periods list
                assert "periods" in weekday_data
                assert "base_temperature" in weekday_data


class TestSimpleScheduleConversionMethods:
    """Test simple schedule conversion helper methods."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_convert_simple_to_profile_multiple_weekdays(self, central_client_factory_with_homegear_client):
        """Test converting simple schedule for multiple weekdays."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Simple schedule for multiple weekdays
        simple_profile_data = {
            WeekdayStr.MONDAY: {
                "base_temperature": 18.0,
                "periods": [
                    {
                        "starttime": "06:00",
                        "endtime": "22:00",
                        "temperature": 21.0,
                    }
                ],
            },
            WeekdayStr.TUESDAY: {
                "base_temperature": 18.0,
                "periods": [
                    {
                        "starttime": "07:00",
                        "endtime": "23:00",
                        "temperature": 22.0,
                    }
                ],
            },
            WeekdayStr.WEDNESDAY: {
                "base_temperature": 18.0,
                "periods": [
                    {
                        "starttime": "05:00",
                        "endtime": "21:00",
                        "temperature": 20.0,
                    }
                ],
            },
        }

        # Set and verify
        await climate.set_schedule_profile(profile=ScheduleProfile.P4, profile_data=simple_profile_data)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_convert_simple_to_weekday_with_gap(self, central_client_factory_with_homegear_client):
        """Test converting simple schedule with gap between periods."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Simple schedule with gap: 06:00-08:00 and 18:00-22:00
        simple_weekday_data = {
            "base_temperature": 18.0,
            "periods": [
                {
                    "starttime": "06:00",
                    "endtime": "08:00",
                    "temperature": 21.0,
                },
                {
                    "starttime": "18:00",
                    "endtime": "22:00",
                    "temperature": 21.0,
                },
            ],
        }

        # Set and verify it works
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P3,
            weekday=WeekdayStr.SUNDAY,
            weekday_data=simple_weekday_data,
        )


class TestWeekProfileProperties:
    """Test week profile properties and basic functionality."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_base_schedule_property(self, central_client_factory_with_homegear_client):
        """Test base schedule property access."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Access base schedule property (cache now stores Pydantic model)
            base_schedule = climate.device.week_profile._schedule_cache
            assert isinstance(base_schedule, ClimateSchedule)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_reload_schedule_updates_cache(self, central_client_factory_with_homegear_client):
        """Test that reload_and_cache_schedule updates the cache."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Get initial schedule
        await climate.get_schedule()

        if climate.device.week_profile:
            dict(climate.device.week_profile._schedule_cache)

            # Force reload
            await climate.device.week_profile.reload_and_cache_schedule(force=True)

            # Cache should still be valid (might be same data), now Pydantic model
            new_cache = climate.device.week_profile._schedule_cache
            assert isinstance(new_cache, ClimateSchedule)


class TestComplexScheduleScenarios:
    """Test complex real-world schedule scenarios."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_full_week_schedule_simple_api(self, central_client_factory_with_homegear_client):
        """Test setting a full week schedule using simple API."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create a full week schedule
        full_week_schedule = {}
        for weekday in [
            WeekdayStr.MONDAY,
            WeekdayStr.TUESDAY,
            WeekdayStr.WEDNESDAY,
            WeekdayStr.THURSDAY,
            WeekdayStr.FRIDAY,
        ]:
            # Workday schedule
            full_week_schedule[weekday] = {
                "base_temperature": 18.0,
                "periods": [
                    {
                        "starttime": "06:00",
                        "endtime": "08:00",
                        "temperature": 21.0,
                    },
                    {
                        "starttime": "17:00",
                        "endtime": "22:00",
                        "temperature": 21.0,
                    },
                ],
            }

        for weekday in [WeekdayStr.SATURDAY, WeekdayStr.SUNDAY]:
            # Weekend schedule
            full_week_schedule[weekday] = {
                "base_temperature": 18.0,
                "periods": [
                    {
                        "starttime": "08:00",
                        "endtime": "23:00",
                        "temperature": 21.0,
                    }
                ],
            }

        # Set the full week schedule
        await climate.set_schedule_profile(profile=ScheduleProfile.P5, profile_data=full_week_schedule)

        # Note: With pessimistic cache and mock client, reading back won't return the exact
        # data we just set (mock doesn't update its state). We verify the operation succeeded.
        # In real scenarios with a CCU, CONFIG_PENDING would trigger cache reload with updated data.

        # Verify operation completed successfully - mock should have received put_paramset call
        assert mock_client.put_paramset.called

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_multiple_temperature_changes_per_day(self, central_client_factory_with_homegear_client):
        """Test schedule with many temperature changes throughout the day."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create schedule with 6 temperature changes
        simple_weekday_data = {
            "base_temperature": 17.0,
            "periods": [
                {
                    "starttime": "06:00",
                    "endtime": "08:00",
                    "temperature": 21.0,
                },
                {
                    "starttime": "08:00",
                    "endtime": "12:00",
                    "temperature": 19.0,
                },
                {
                    "starttime": "12:00",
                    "endtime": "14:00",
                    "temperature": 20.0,
                },
                {
                    "starttime": "14:00",
                    "endtime": "17:00",
                    "temperature": 19.0,
                },
                {
                    "starttime": "17:00",
                    "endtime": "22:00",
                    "temperature": 21.5,
                },
                {
                    "starttime": "22:00",
                    "endtime": "24:00",
                    "temperature": 18.5,
                },
            ],
        }

        # Set and verify
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P3,
            weekday=WeekdayStr.WEDNESDAY,
            weekday_data=simple_weekday_data,
        )

        # Note: With pessimistic cache and mock client, reading back won't return the exact
        # data we just set (mock doesn't update its state). We verify the operation succeeded.
        # In real scenarios with a CCU, CONFIG_PENDING would trigger cache reload with updated data.

        # Verify operation completed successfully - mock should have received put_paramset call
        assert mock_client.put_paramset.called


class TestEdgeCasesAndErrorPaths:
    """Test edge cases and error paths for complete coverage."""

    def test_convert_minutes_to_time_str_invalid_pattern(self):
        """Test that invalid minute values raise ValidationException."""
        # Test with value that would create invalid time format (> 24 hours)
        invalid_minutes = 25 * 60  # 25:00

        # Should raise ValidationException for invalid time
        with pytest.raises(ValidationException):
            _convert_minutes_to_time_str(minutes=invalid_minutes)

    def test_convert_time_str_to_minutes_exception_handling(self):
        """Test exception handling in time string conversion."""
        # Test with invalid format that causes split to fail
        with pytest.raises(ValidationException):
            _convert_time_str_to_minutes(time_str="invalid")

    def test_convert_time_str_to_minutes_value_error(self):
        """Test ValueError handling in time conversion."""
        # Test with valid format but non-numeric values
        with pytest.raises(ValidationException):
            _convert_time_str_to_minutes(time_str="ab:cd")

    def test_filter_profile_entries_with_all_empty_weekdays(self):
        """Test filter_profile_entries when all weekdays have empty data."""
        # All weekdays have only 24:00 slots that get filtered out
        profile_data = {
            WeekdayStr.MONDAY: {},
            WeekdayStr.TUESDAY: {},
        }

        result = _filter_profile_entries(profile_data=profile_data)
        # Empty weekdays should be filtered out
        assert result == {}

    def test_filter_schedule_entries_with_all_empty_profiles(self):
        """Test filter_schedule_entries when all profiles are empty."""
        # All profiles are empty
        schedule_data = {
            ScheduleProfile.P1: {},
            ScheduleProfile.P2: {},
        }

        result = _filter_schedule_entries(schedule_data=schedule_data)
        # Empty profiles should be filtered out
        assert result == {}

    def test_filter_weekday_entries_returns_empty_when_all_filtered(self):
        """Test that filter returns empty dict when all slots are redundant 24:00."""
        # Create weekday data with only 24:00 slots (except one should be kept)
        weekday_data = {
            1: {"endtime": "24:00", "temperature": 18.0},
            2: {"endtime": "24:00", "temperature": 18.0},
            3: {"endtime": "24:00", "temperature": 18.0},
        }

        result = _filter_weekday_entries(weekday_data=weekday_data)
        # Should keep only one 24:00 slot
        assert len(result) == 1
        assert result[1]["endtime"] == "24:00"

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_get_schedule_profile_missing_profile(self, central_client_factory_with_homegear_client):
        """Test getting a profile that doesn't exist returns empty data."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Try to get a profile that might not exist in the cache
        if climate.device.week_profile:
            climate.device.week_profile._schedule_cache = {}

        profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P3)
        # Should return empty or valid dict
        assert isinstance(profile_data, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_get_schedule_weekday_missing_data(self, central_client_factory_with_homegear_client):
        """Test getting weekday data that doesn't exist."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Try to get weekday from non-existent profile
        if climate.device.week_profile:
            climate.device.week_profile._schedule_cache = {}

        weekday_data = await climate.get_schedule_weekday(profile=ScheduleProfile.P3, weekday=WeekdayStr.SUNDAY)
        # Should return empty dict
        assert isinstance(weekday_data, dict)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_set_schedule_weekday_creates_new_profile(self, central_client_factory_with_homegear_client):
        """Test that setting weekday data creates profile if it doesn't exist."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create fresh weekday data in Simple format for a profile that might not exist
        weekday_data = {
            "base_temperature": 18.0,
            "periods": [
                {"starttime": "00:00", "endtime": "12:00", "temperature": 20.0},
            ],
        }

        # Set for a profile (P3)
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P3, weekday=WeekdayStr.SATURDAY, weekday_data=weekday_data
        )

        # Note: With pessimistic cache and mock client, the cache won't be updated immediately.
        # We verify the operation succeeded by checking that put_paramset was called.
        # In real scenarios with a CCU, CONFIG_PENDING would trigger cache reload with updated data.

        # Verify operation completed successfully - mock should have received put_paramset call
        assert mock_client.put_paramset.called


class TestWeekProfileHelperMethods:
    """Tests for untested week profile helper methods and properties."""

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_convert_raw_to_dict_handles_invalid_entries(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test convert_raw_to_dict_schedule handles invalid entries gracefully."""
        central, mock_client, _ = central_client_factory_with_homegear_client

        # Raw schedule with some invalid entries
        raw_schedule = {
            "P1_TEMPERATURE_MONDAY_1": 20.0,
            "P1_ENDTIME_MONDAY_1": 360,
            "INVALID_ENTRY": "value",
            "P1_BADTYPE_MONDAY_1": 100,  # Invalid slot type
            "P99_TEMPERATURE_MONDAY_1": 20.0,  # Invalid profile
        }

        # Should handle gracefully and only convert valid entries
        result = ClimateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        # Should have P1 profile
        assert ScheduleProfile.P1 in result
        assert WeekdayStr.MONDAY in result[ScheduleProfile.P1]

        # Should have valid slot
        assert 1 in result[ScheduleProfile.P1][WeekdayStr.MONDAY]
        slot = result[ScheduleProfile.P1][WeekdayStr.MONDAY][1]
        assert "temperature" in slot
        assert "endtime" in slot

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_convert_schedule_entries_filters_wp_entries(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test _convert_schedule_entries filters week profile entries correctly."""
        central, mock_client, _ = central_client_factory_with_homegear_client

        # Mock raw paramset with mixed entries
        raw_values = {
            "01_WP_WEEKDAY": 127,
            "01_WP_LEVEL": 1.0,
            "02_WP_WEEKDAY": 64,
            "SOME_OTHER_PARAM": "value",
            "ANOTHER_PARAM": 42,
        }

        # Should extract only WP entries
        result = DefaultWeekProfile._convert_schedule_entries(values=raw_values)

        # Should only have WP entries
        assert "01_WP_WEEKDAY" in result
        assert "01_WP_LEVEL" in result
        assert "02_WP_WEEKDAY" in result
        assert "SOME_OTHER_PARAM" not in result
        assert "ANOTHER_PARAM" not in result
        assert len(result) == 3

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_empty_schedule_entry(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test empty_schedule_entry method for DefaultWeekProfile."""
        central, mock_client, _ = central_client_factory_with_homegear_client

        # Create a mock custom data point with non-climate category
        mock_data_point = MagicMock(spec=CustomDataPoint)
        mock_data_point.device.address = "TEST123"
        mock_data_point.device.client = mock_client
        mock_data_point.device.central = central
        mock_data_point.category = DataPointCategory.SWITCH
        mock_data_point.device_config.schedule_channel_no = None

        # Create DefaultWeekProfile
        week_profile = DefaultWeekProfile(data_point=mock_data_point)

        # Get empty schedule entry
        empty_entry = week_profile.empty_schedule_entry()

        # Should return a SimpleScheduleEntry
        assert isinstance(empty_entry, SimpleScheduleEntry)
        assert empty_entry.weekdays == ["MONDAY"]
        assert empty_entry.time == "00:00"
        assert empty_entry.level == 0.0

    def test_empty_schedule_group_cover_category(self):
        """Test create_empty_schedule_group for cover category."""
        empty_group = create_empty_schedule_group(category=DataPointCategory.COVER)

        # Should have cover-specific fields
        assert ScheduleField.LEVEL in empty_group
        assert ScheduleField.LEVEL_2 in empty_group
        assert empty_group[ScheduleField.LEVEL] == 0.0
        assert empty_group[ScheduleField.LEVEL_2] == 0.0

    def test_empty_schedule_group_light_category(self):
        """Test create_empty_schedule_group for light category."""
        empty_group = create_empty_schedule_group(category=DataPointCategory.LIGHT)

        # Should have light-specific fields
        assert ScheduleField.LEVEL in empty_group
        assert ScheduleField.RAMP_TIME_BASE in empty_group
        assert ScheduleField.RAMP_TIME_FACTOR in empty_group
        assert ScheduleField.DURATION_BASE in empty_group
        assert ScheduleField.DURATION_FACTOR in empty_group

    def test_empty_schedule_group_switch_category(self):
        """Test create_empty_schedule_group for switch category."""
        empty_group = create_empty_schedule_group(category=DataPointCategory.SWITCH)

        # Should have all required fields
        assert ScheduleField.WEEKDAY in empty_group
        assert ScheduleField.TARGET_CHANNELS in empty_group
        assert ScheduleField.LEVEL in empty_group
        assert ScheduleField.DURATION_BASE in empty_group
        assert ScheduleField.DURATION_FACTOR in empty_group

        # Weekday and target channels should be empty
        assert empty_group[ScheduleField.WEEKDAY] == []
        assert empty_group[ScheduleField.TARGET_CHANNELS] == []

    def test_empty_schedule_group_valve_category(self):
        """Test create_empty_schedule_group for valve category."""
        empty_group = create_empty_schedule_group(category=DataPointCategory.VALVE)

        # Should have valve-specific fields
        assert ScheduleField.LEVEL in empty_group
        assert empty_group[ScheduleField.LEVEL] == 0.0

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_has_schedule_property(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test has_schedule property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Should return True for devices with schedule support
            assert climate.device.week_profile.has_schedule is True

    def test_identify_base_temperature_with_integer_endtimes(self):
        """
        Test identify_base_temperature handles integer endtime values from CCU (fixes #2797).

        The CCU always returns endtime values as integers (minutes since midnight).
        This test verifies that identify_base_temperature correctly handles this format
        without raising ValidationException: "Time 360 is invalid".
        """
        # Raw schedule data from CCU with integer endtime values (minutes since midnight)
        weekday_data = {
            1: {"endtime": 360, "temperature": 18.0},  # 06:00 - base temperature
            2: {"endtime": 480, "temperature": 21.0},  # 08:00 - comfort temperature
            3: {"endtime": 1200, "temperature": 18.0},  # 20:00 - back to base
            4: {"endtime": 1440, "temperature": 18.0},  # 24:00 - end of day
        }

        # Should handle integer endtime values without raising ValidationException
        base_temp = identify_base_temperature(weekday_data=weekday_data)

        # Base temperature should be 18.0 (most minutes used):
        # Slot 1: 00:00-06:00 = 360 min at 18.0°C
        # Slot 2: 06:00-08:00 = 120 min at 21.0°C
        # Slot 3: 08:00-20:00 = 720 min at 18.0°C
        # Slot 4: 20:00-24:00 = 240 min at 18.0°C
        # Total: 18.0°C = 1320 min, 21.0°C = 120 min
        assert base_temp == 18.0

    def test_identify_base_temperature_with_numeric_string_endtimes(self):
        """
        Test identify_base_temperature handles numeric string endtime values from legacy cache.

        Old cached data might store endtime as string representation of minutes (e.g., "360"
        instead of integer 360 or time string "06:00"). This test verifies that the migration
        fix correctly handles this legacy format without raising ValidationException.
        """
        # Legacy cache format with numeric string endtime values (minutes as strings)
        weekday_data = {
            1: {"endtime": "360", "temperature": 18.0},  # 06:00 - base temperature (as string)
            2: {"endtime": "480", "temperature": 21.0},  # 08:00 - comfort temperature
            3: {"endtime": "1200", "temperature": 18.0},  # 20:00 - back to base
            4: {"endtime": "1440", "temperature": 18.0},  # 24:00 - end of day
        }

        # Should handle numeric string endtime values without raising ValidationException
        base_temp = identify_base_temperature(weekday_data=weekday_data)

        # Base temperature should be 18.0 (most minutes used):
        # Slot 1: 00:00-06:00 = 360 min at 18.0°C
        # Slot 2: 06:00-08:00 = 120 min at 21.0°C
        # Slot 3: 08:00-20:00 = 720 min at 18.0°C
        # Slot 4: 20:00-24:00 = 240 min at 18.0°C
        # Total: 18.0°C = 1320 min, 21.0°C = 120 min
        assert base_temp == 18.0

    def test_normalize_weekday_data_with_numeric_string_endtimes(self):
        """
        Test _normalize_weekday_data handles numeric string endtime values from legacy cache.

        The normalization function must handle the legacy cache format where endtime
        is stored as a numeric string (e.g., "360") to avoid ValidationException during
        sorting.
        """
        # Legacy cache format with numeric string endtime values and string slot keys
        weekday_data = {
            "2": {"endtime": "480", "temperature": 21.0},  # 08:00 - listed second but earlier slot
            "1": {"endtime": "1440", "temperature": 18.0},  # 24:00 - listed first but later time
        }

        # Should handle numeric string endtime values and sort correctly
        result = _normalize_weekday_data(weekday_data=weekday_data)

        # Result should be sorted by endtime and have 13 slots
        assert len(result) == 13
        # First slot should be the one with earlier endtime (08:00/480)
        assert result[1]["endtime"] == "480"
        assert result[1]["temperature"] == 21.0
        # Second slot should be the one with later endtime (24:00/1440)
        assert result[2]["endtime"] == "1440"
        assert result[2]["temperature"] == 18.0

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_schedule_channel_address_property(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test schedule_channel_address property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        assert climate.device.week_profile is not None, "Device should have week_profile"
        # Should return channel address
        channel_address = climate.device.week_profile.schedule_channel_address
        assert channel_address is not None
        assert isinstance(channel_address, str)

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_schedule_property_returns_filtered(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test that schedule property returns filtered data."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        if climate.device.week_profile and isinstance(climate.device.week_profile, ClimateWeekProfile):
            # Get schedule via property
            schedule = climate.device.week_profile.schedule

            # Should return filtered schedule (no redundant 24:00 slots)
            assert isinstance(schedule, ClimateSchedule)

            # If there's data, verify it's filtered
            if schedule:
                for profile_data in schedule.values():
                    for weekday_data in profile_data.values():
                        # Filtered data should have fewer than 13 slots
                        # (unless all slots have different times)
                        if weekday_data:
                            # At least verify the data structure is correct
                            for period in weekday_data.periods:
                                assert hasattr(period, "endtime")
                                assert hasattr(period, "temperature")

    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES_SCHEDULE, True, None, None),
        ],
    )
    async def test_validate_and_get_schedule_channel_address(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test _validate_and_get_schedule_channel_address method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Should return valid channel address
            channel_address = climate.device.week_profile._validate_and_get_schedule_channel_address()
            assert channel_address is not None
            assert isinstance(channel_address, str)


class TestDomainSpecificScheduleValidation:
    """Test domain-specific validation for SimpleScheduleEntry."""

    def test_cover_schedule_duration_rejected(self):
        """Test that COVER schedules reject duration."""
        with pytest.raises(ValueError, match="duration.*not supported for cover"):
            SimpleSchedule.model_validate(
                {
                    "entries": {
                        1: {
                            "weekdays": ["MONDAY"],
                            "time": "07:00",
                            "target_channels": ["1_1"],
                            "level": 0.5,
                            "duration": "10s",
                        }
                    }
                },
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.COVER},
            )

    def test_cover_schedule_level_2_allowed(self):
        """Test that COVER schedules allow level_2."""
        schedule = SimpleSchedule.model_validate(
            {
                "entries": {
                    1: {
                        "weekdays": ["MONDAY"],
                        "time": "07:00",
                        "target_channels": ["1_1"],
                        "level": 0.5,
                        "level_2": 0.3,
                    }
                }
            },
            context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.COVER},
        )
        assert schedule.entries[1].level_2 == 0.3

    def test_cover_schedule_ramp_time_rejected(self):
        """Test that COVER schedules reject ramp_time."""
        with pytest.raises(ValueError, match="ramp_time.*not supported for cover"):
            SimpleSchedule.model_validate(
                {
                    "entries": {
                        1: {
                            "weekdays": ["MONDAY"],
                            "time": "07:00",
                            "target_channels": ["1_1"],
                            "level": 0.5,
                            "ramp_time": "5s",
                        }
                    }
                },
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.COVER},
            )

    def test_direct_entry_validation_with_context(self):
        """Test that SimpleScheduleEntry can be validated with context directly."""
        # Valid SWITCH entry
        entry = SimpleScheduleEntry.model_validate(
            {"weekdays": ["MONDAY"], "time": "07:00", "target_channels": ["1_1"], "level": 1.0},
            context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.SWITCH},
        )
        assert entry.level == 1.0

        # Invalid SWITCH entry (non-binary level)
        with pytest.raises(ValueError, match="Switch level must be 0.0 or 1.0"):
            SimpleScheduleEntry.model_validate(
                {"weekdays": ["MONDAY"], "time": "07:00", "target_channels": ["1_1"], "level": 0.5},
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.SWITCH},
            )

    def test_light_schedule_level_2_rejected(self):
        """Test that LIGHT schedules reject level_2."""
        with pytest.raises(ValueError, match="level_2.*not supported for light"):
            SimpleSchedule.model_validate(
                {
                    "entries": {
                        1: {
                            "weekdays": ["MONDAY"],
                            "time": "07:00",
                            "target_channels": ["1_1"],
                            "level": 0.8,
                            "level_2": 0.5,
                        }
                    }
                },
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.LIGHT},
            )

    def test_light_schedule_ramp_time_allowed(self):
        """Test that LIGHT schedules allow ramp_time."""
        schedule = SimpleSchedule.model_validate(
            {
                "entries": {
                    1: {
                        "weekdays": ["MONDAY"],
                        "time": "07:00",
                        "target_channels": ["1_1"],
                        "level": 0.8,
                        "ramp_time": "5s",
                    }
                }
            },
            context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.LIGHT},
        )
        assert schedule.entries[1].ramp_time == "5s"

    def test_no_context_skips_domain_validation(self):
        """Test that validation without context allows all fields (backward compatibility)."""
        # Without context, non-binary level should be allowed for any entry
        schedule = SimpleSchedule.model_validate(
            {
                "entries": {
                    1: {
                        "weekdays": ["MONDAY"],
                        "time": "07:00",
                        "target_channels": ["1_1"],
                        "level": 0.5,
                        "level_2": 0.3,
                        "ramp_time": "5s",
                        "duration": "10s",
                    }
                }
            }
        )
        assert schedule.entries[1].level == 0.5
        assert schedule.entries[1].level_2 == 0.3
        assert schedule.entries[1].ramp_time == "5s"
        assert schedule.entries[1].duration == "10s"

    def test_switch_schedule_binary_level_valid(self):
        """Test that SWITCH schedules accept binary level (0.0 or 1.0)."""
        # Valid: level = 0.0
        schedule = SimpleSchedule.model_validate(
            {"entries": {1: {"weekdays": ["MONDAY"], "time": "07:00", "target_channels": ["1_1"], "level": 0.0}}},
            context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.SWITCH},
        )
        assert schedule.entries[1].level == 0.0

        # Valid: level = 1.0
        schedule = SimpleSchedule.model_validate(
            {"entries": {1: {"weekdays": ["MONDAY"], "time": "07:00", "target_channels": ["1_1"], "level": 1.0}}},
            context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.SWITCH},
        )
        assert schedule.entries[1].level == 1.0

    def test_switch_schedule_level_2_rejected(self):
        """Test that SWITCH schedules reject level_2."""
        with pytest.raises(ValueError, match="level_2.*not supported for switch"):
            SimpleSchedule.model_validate(
                {
                    "entries": {
                        1: {
                            "weekdays": ["MONDAY"],
                            "time": "07:00",
                            "target_channels": ["1_1"],
                            "level": 1.0,
                            "level_2": 0.5,
                        }
                    }
                },
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.SWITCH},
            )

    def test_switch_schedule_non_binary_level_rejected(self):
        """Test that SWITCH schedules reject non-binary level."""
        with pytest.raises(ValueError, match="Switch level must be 0.0 or 1.0"):
            SimpleSchedule.model_validate(
                {"entries": {1: {"weekdays": ["MONDAY"], "time": "07:00", "target_channels": ["1_1"], "level": 0.5}}},
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.SWITCH},
            )

    def test_switch_schedule_ramp_time_rejected(self):
        """Test that SWITCH schedules reject ramp_time."""
        with pytest.raises(ValueError, match="ramp_time.*not supported for switch"):
            SimpleSchedule.model_validate(
                {
                    "entries": {
                        1: {
                            "weekdays": ["MONDAY"],
                            "time": "07:00",
                            "target_channels": ["1_1"],
                            "level": 1.0,
                            "ramp_time": "5s",
                        }
                    }
                },
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.SWITCH},
            )

    def test_valve_schedule_level_2_rejected(self):
        """Test that VALVE schedules reject level_2."""
        with pytest.raises(ValueError, match="level_2.*not supported for valve"):
            SimpleSchedule.model_validate(
                {
                    "entries": {
                        1: {
                            "weekdays": ["MONDAY"],
                            "time": "07:00",
                            "target_channels": ["1_1"],
                            "level": 0.5,
                            "level_2": 0.3,
                        }
                    }
                },
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.VALVE},
            )

    def test_valve_schedule_ramp_time_rejected(self):
        """Test that VALVE schedules reject ramp_time."""
        with pytest.raises(ValueError, match="ramp_time.*not supported for valve"):
            SimpleSchedule.model_validate(
                {
                    "entries": {
                        1: {
                            "weekdays": ["MONDAY"],
                            "time": "07:00",
                            "target_channels": ["1_1"],
                            "level": 0.5,
                            "ramp_time": "5s",
                        }
                    }
                },
                context={SCHEDULE_DOMAIN_CONTEXT_KEY: DataPointCategory.VALVE},
            )
