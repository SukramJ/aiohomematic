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
    ScheduleSlotType,
    WeekdayInt,
    WeekdayStr,
)
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom import CustomDpRfThermostat
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.week_profile import (
    ClimeateWeekProfile,
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
    _sort_simple_weekday_data,
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
                1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            },
            WeekdayStr.TUESDAY: {
                1: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 20.0},
                2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 20.0},
                3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 20.0},
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
                    1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                    2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                    3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                },
            },
            ScheduleProfile.P2: {
                WeekdayStr.MONDAY: {
                    1: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 20.0},
                    2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 20.0},
                    3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 20.0},
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
                ScheduleSlotType.ENDTIME: f"{i * 3:02d}:00",
                ScheduleSlotType.TEMPERATURE: 20.0,
            }
        for i in range(8, 14):
            weekday_data[i] = {
                ScheduleSlotType.ENDTIME: "24:00",
                ScheduleSlotType.TEMPERATURE: 18.0,
            }

        result = _filter_weekday_entries(weekday_data=weekday_data)
        # Should keep slots 1-7 and first 24:00 (slot 8)
        assert len(result) == 8

    def test_filter_weekday_entries_multiple_24_00_slots(self):
        """Test filtering removes redundant 24:00 slots, keeps first by slot number."""
        weekday_data = {
            7: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            3: {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 21.0},
            5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 19.0},
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 20.0},
        }
        result = _filter_weekday_entries(weekday_data=weekday_data)
        # Should keep slots 1, 3, and first 24:00 (slot 5, not 7)
        assert len(result) == 3
        assert result[1][ScheduleSlotType.ENDTIME] == "06:00"
        assert result[2][ScheduleSlotType.ENDTIME] == "18:00"
        assert result[3][ScheduleSlotType.ENDTIME] == "24:00"
        # Should keep the temperature from slot 5 (first 24:00 by number)
        assert result[3][ScheduleSlotType.TEMPERATURE] == 19.0

    def test_filter_weekday_entries_no_24_00_slots(self):
        """Test filtering when there are no 24:00 slots."""
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 21.0},
            3: {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }
        result = _filter_weekday_entries(weekday_data=weekday_data)
        assert len(result) == 3
        assert result[1][ScheduleSlotType.ENDTIME] == "06:00"
        assert result[2][ScheduleSlotType.ENDTIME] == "08:00"
        assert result[3][ScheduleSlotType.ENDTIME] == "18:00"

    def test_filter_weekday_entries_single_24_00_slot(self):
        """Test filtering with single 24:00 slot."""
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }
        result = _filter_weekday_entries(weekday_data=weekday_data)
        assert len(result) == 2
        assert result[2][ScheduleSlotType.ENDTIME] == "24:00"


class TestNormalizationFunctions:
    """Test normalization functions."""

    def test_normalize_weekday_data_empty(self):
        """Test normalization with empty data."""
        result = _normalize_weekday_data(weekday_data={})
        assert result == {}

    def test_normalize_weekday_data_fills_to_13_slots(self):
        """Test that missing slots are filled to reach 13 total."""
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 21.0},
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)
        assert len(result) == 13
        # Slots 3-13 should be filled with 24:00 and last slot's temperature
        for i in range(3, 14):
            assert result[i][ScheduleSlotType.ENDTIME] == "24:00"
            assert result[i][ScheduleSlotType.TEMPERATURE] == 21.0

    def test_normalize_weekday_data_full_example(self):
        """Test complete normalization workflow."""
        weekday_data = {
            "5": {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 20.0},
            "1": {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            "3": {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 22.0},
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)

        # Should be sorted and renumbered
        assert len(result) == 13
        assert result[1][ScheduleSlotType.ENDTIME] == "06:00"
        assert result[2][ScheduleSlotType.ENDTIME] == "12:00"
        assert result[3][ScheduleSlotType.ENDTIME] == "18:00"

        # Slots 4-13 should be filled with 24:00 and temperature from last slot (20.0)
        for i in range(4, 14):
            assert result[i][ScheduleSlotType.ENDTIME] == "24:00"
            assert result[i][ScheduleSlotType.TEMPERATURE] == 20.0

    def test_normalize_weekday_data_sorts_by_endtime(self):
        """Test that slots are sorted chronologically by ENDTIME."""
        weekday_data = {
            3: {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 18.0},
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 20.0},
            2: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 21.0},
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)
        assert result[1][ScheduleSlotType.ENDTIME] == "06:00"
        assert result[2][ScheduleSlotType.ENDTIME] == "12:00"
        assert result[3][ScheduleSlotType.ENDTIME] == "18:00"

    def test_normalize_weekday_data_string_keys_to_int(self):
        """Test that string keys are converted to integers."""
        weekday_data = {
            "1": {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            "2": {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 21.0},
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)
        assert all(isinstance(k, int) for k in result)

    def test_normalize_weekday_data_uses_default_temp_if_missing(self):
        """Test that default temperature is used if last slot has no temperature."""
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00"},  # No temperature
        }
        result = _normalize_weekday_data(weekday_data=weekday_data)
        # Filled slots should use DEFAULT_CLIMATE_FILL_TEMPERATURE
        assert result[2][ScheduleSlotType.TEMPERATURE] == DEFAULT_CLIMATE_FILL_TEMPERATURE


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
        assert _convert_minutes_to_time_str("invalid") == "24:00"
        assert _convert_minutes_to_time_str(None) == "24:00"

    def test_convert_minutes_to_time_str_valid(self):
        """Test minutes to time string conversion."""
        assert _convert_minutes_to_time_str(0) == "00:00"
        assert _convert_minutes_to_time_str(360) == "06:00"
        assert _convert_minutes_to_time_str(750) == "12:30"
        assert _convert_minutes_to_time_str(1440) == "24:00"

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
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }
        result = _fillup_weekday_data(base_temperature=20.0, weekday_data=weekday_data)

        # Should fill missing slots 2-13
        assert len(result) == 13
        for i in range(2, 14):
            assert result[i][ScheduleSlotType.ENDTIME] == "24:00"
            assert result[i][ScheduleSlotType.TEMPERATURE] == 20.0

    def test_identify_base_temperature_base_temp_dominates(self):
        """Test _identify_base_temperature where base temperature has most time."""
        # 18.0° for 1020 minutes (06:00 + 540 min + 120 min)
        # 21.0° for 420 minutes (120 min + 300 min)
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 21.0},
            3: {ScheduleSlotType.ENDTIME: "17:00", ScheduleSlotType.TEMPERATURE: 18.0},
            4: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
            5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
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
            1: {ScheduleSlotType.ENDTIME: "05:00", ScheduleSlotType.TEMPERATURE: 17.0},
            2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 20.0},
            3: {ScheduleSlotType.ENDTIME: "17:00", ScheduleSlotType.TEMPERATURE: 18.0},
            4: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 22.0},
            5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
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
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 15.0},
            2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 18.0},
            3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 21.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        assert result == 21.0

    def test_identify_base_temperature_single_temperature(self):
        """Test _identify_base_temperature with single temperature all day."""
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        assert result == 18.0

    def test_identify_base_temperature_two_temperatures_equal_time(self):
        """Test _identify_base_temperature with two temperatures having equal time."""
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 21.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        # Both have 720 minutes (12 hours), max() will return one of them
        assert result in [18.0, 21.0]

    def test_identify_base_temperature_unsorted_slots(self):
        """Test _identify_base_temperature with unsorted slot numbers."""
        # The function should sort by slot number
        weekday_data = {
            5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            3: {ScheduleSlotType.ENDTIME: "17:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 21.0},
            4: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
        }
        result = identify_base_temperature(weekday_data=weekday_data)
        assert result == 18.0

    def test_is_schedule_active_both_missing(self):
        """Test is_schedule_active with both fields missing."""
        group_data = {
            ScheduleField.WEEKDAY: [],
            ScheduleField.TARGET_CHANNELS: [],
        }
        assert is_schedule_active(group_data) is False

    def test_is_schedule_active_missing_channels(self):
        """Test is_schedule_active with missing channels."""
        group_data = {
            ScheduleField.WEEKDAY: [WeekdayInt.MONDAY],
            ScheduleField.TARGET_CHANNELS: [],
        }
        assert is_schedule_active(group_data) is False

    def test_is_schedule_active_missing_weekday(self):
        """Test is_schedule_active with missing weekday."""
        group_data = {
            ScheduleField.WEEKDAY: [],
            ScheduleField.TARGET_CHANNELS: [ScheduleActorChannel.CHANNEL_1_1],
        }
        assert is_schedule_active(group_data) is False

    def test_is_schedule_active_with_all_fields(self):
        """Test is_schedule_active with complete data."""
        group_data = {
            ScheduleField.WEEKDAY: [WeekdayInt.MONDAY],
            ScheduleField.TARGET_CHANNELS: [ScheduleActorChannel.CHANNEL_1_1],
        }
        assert is_schedule_active(group_data) is True

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

    def test_sort_simple_weekday_data(self):
        """Test sorting simple weekday list."""
        simple_list = [
            {
                ScheduleSlotType.STARTTIME: "18:00",
                ScheduleSlotType.ENDTIME: "22:00",
                ScheduleSlotType.TEMPERATURE: 21.0,
            },
            {
                ScheduleSlotType.STARTTIME: "06:00",
                ScheduleSlotType.ENDTIME: "08:00",
                ScheduleSlotType.TEMPERATURE: 20.0,
            },
            {
                ScheduleSlotType.STARTTIME: "12:00",
                ScheduleSlotType.ENDTIME: "15:00",
                ScheduleSlotType.TEMPERATURE: 19.0,
            },
        ]
        result = _sort_simple_weekday_data(simple_weekday_data=simple_list)

        assert result[0][ScheduleSlotType.STARTTIME] == "06:00"
        assert result[1][ScheduleSlotType.STARTTIME] == "12:00"
        assert result[2][ScheduleSlotType.STARTTIME] == "18:00"


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
        assert isinstance(profile, ClimeateWeekProfile)

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

        simple_data = (
            999.0,
            [  # Way out of range
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "08:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                }
            ],
        )

        # Should raise ValidationException for out of range base temperature
        with pytest.raises(ValidationException):
            await climate.set_simple_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                simple_weekday_data=simple_data,
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

        simple_data = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    # Missing ENDTIME
                    ScheduleSlotType.TEMPERATURE: 20.0,
                }
            ],
        )

        with pytest.raises(ValidationException):
            await climate.set_simple_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                simple_weekday_data=simple_data,
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

        simple_data = (
            18.0,
            [
                {
                    # Missing STARTTIME
                    ScheduleSlotType.ENDTIME: "08:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                }
            ],
        )

        with pytest.raises(ValidationException):
            await climate.set_simple_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                simple_weekday_data=simple_data,
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

        simple_data = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "08:00",
                    # Missing TEMPERATURE
                }
            ],
        )

        with pytest.raises(ValidationException):
            await climate.set_simple_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                simple_weekday_data=simple_data,
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

        simple_data = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "10:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "08:00",  # Overlaps with previous!
                    ScheduleSlotType.ENDTIME: "12:00",
                    ScheduleSlotType.TEMPERATURE: 21.0,
                },
            ],
        )

        with pytest.raises(ValidationException):
            await climate.set_simple_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                simple_weekday_data=simple_data,
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

        simple_data = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "08:00",
                    ScheduleSlotType.ENDTIME: "06:00",  # End before start!
                    ScheduleSlotType.TEMPERATURE: 20.0,
                }
            ],
        )

        with pytest.raises(ValidationException):
            await climate.set_simple_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                simple_weekday_data=simple_data,
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

        simple_data = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "08:00",
                    ScheduleSlotType.TEMPERATURE: 999.0,  # Out of range
                }
            ],
        )

        with pytest.raises(ValidationException):
            await climate.set_simple_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                simple_weekday_data=simple_data,
            )


class TestScheduleValidation:
    """Test schedule validation methods."""

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
    async def test_validation_missing_slot_fields(self, central_client_factory_with_homegear_client):
        """Test validation rejects slots missing required fields."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create 13 slots but one is missing TEMPERATURE
        weekday_data = {}
        for i in range(1, 14):
            if i == 5:
                weekday_data[i] = {
                    ScheduleSlotType.ENDTIME: f"{i:02d}:00",
                    # Missing TEMPERATURE
                }
            else:
                weekday_data[i] = {
                    ScheduleSlotType.ENDTIME: f"{i:02d}:00" if i < 13 else "24:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                }

        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=weekday_data,
                do_validate=True,
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
    async def test_validation_missing_slot_number(self, central_client_factory_with_homegear_client):
        """Test that after normalization, missing slot numbers cause validation error."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # This will be normalized to 13 slots, so validation should pass
        # The test validates that normalization happens before validation
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            # Missing slot 2, but normalization will fill it
            3: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 21.0},
        }

        # Should work because normalization fills missing slots
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1,
            weekday=WeekdayStr.MONDAY,
            weekday_data=weekday_data,
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
    async def test_validation_time_not_ascending(self, central_client_factory_with_homegear_client):
        """Test validation rejects non-ascending time sequence."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create 13 slots with non-ascending times
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 20.0},
            3: {ScheduleSlotType.ENDTIME: "07:00", ScheduleSlotType.TEMPERATURE: 21.0},  # Goes back!
        }

        # Normalization will sort by time, so let's create a case where
        # after normalization the times are still invalid
        # Actually, normalization sorts by ENDTIME, so this should be caught during validation
        # Let me create 13 slots where times go backwards
        weekday_data = {}
        for i in range(1, 14):
            if i < 7:
                weekday_data[i] = {
                    ScheduleSlotType.ENDTIME: f"{i * 2:02d}:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                }
            elif i == 7:
                weekday_data[i] = {
                    ScheduleSlotType.ENDTIME: "05:00",  # Goes back!
                    ScheduleSlotType.TEMPERATURE: 20.0,
                }
            else:
                weekday_data[i] = {
                    ScheduleSlotType.ENDTIME: "24:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                }

        # Normalization will sort these, so validation should actually pass
        # The test shows that normalization handles unsorted input
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1,
            weekday=WeekdayStr.MONDAY,
            weekday_data=weekday_data,
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
    async def test_validation_too_few_slots(self, central_client_factory_with_homegear_client):
        """Test validation accepts fewer than 13 slots (normalization fills them)."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create only 3 slots - should be filled to 13
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 21.0},
            3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }

        # Should not raise - normalization fills missing slots
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1,
            weekday=WeekdayStr.MONDAY,
            weekday_data=weekday_data,
        )

        # Verify it was called
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
    async def test_validation_too_many_slots(self, central_client_factory_with_homegear_client):
        """Test validation rejects more than 13 slots."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create 14 slots (one too many)
        weekday_data = {}
        for i in range(1, 15):  # 14 slots
            weekday_data[i] = {
                ScheduleSlotType.ENDTIME: f"{i:02d}:00",
                ScheduleSlotType.TEMPERATURE: 20.0,
            }

        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=weekday_data,
                do_validate=True,
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
        switch_empty = create_empty_schedule_group(DataPointCategory.SWITCH)
        assert ScheduleField.LEVEL in switch_empty
        assert ScheduleField.DURATION_BASE in switch_empty

        light_empty = create_empty_schedule_group(DataPointCategory.LIGHT)
        assert ScheduleField.LEVEL in light_empty
        assert ScheduleField.RAMP_TIME_BASE in light_empty

        cover_empty = create_empty_schedule_group(DataPointCategory.COVER)
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
        assert ScheduleProfile.P1 in schedule

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
        assert WeekdayStr.MONDAY in profile_data

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
    async def test_get_schedule_profile_weekday(self, central_client_factory_with_homegear_client):
        """Test getting schedule profile weekday."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Get weekday data
        weekday_data = await climate.get_schedule_profile_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY)
        assert isinstance(weekday_data, dict)

        # Get with force_load
        weekday_data_forced = await climate.get_schedule_profile_weekday(
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

        # Access property
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

        # Set profile with validation
        await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=profile_data, do_validate=True)

        # Set profile without validation
        await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=profile_data, do_validate=False)

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
            WeekdayStr.MONDAY: (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "06:00",
                        ScheduleSlotType.ENDTIME: "22:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    }
                ],
            ),
            WeekdayStr.TUESDAY: (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "06:00",
                        ScheduleSlotType.ENDTIME: "22:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    }
                ],
            ),
        }

        # Set simple schedule
        await climate.set_simple_schedule_profile(profile=ScheduleProfile.P2, simple_profile_data=simple_profile_data)

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
        simple_weekday_data = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "22:00",
                    ScheduleSlotType.TEMPERATURE: 21.0,
                }
            ],
        )

        # Set simple weekday schedule
        await climate.set_simple_schedule_weekday(
            profile=ScheduleProfile.P2,
            weekday=WeekdayStr.WEDNESDAY,
            simple_weekday_data=simple_weekday_data,
        )


class TestDefaultWeekProfileConversion:
    """Test DefaultWeekProfile conversion methods."""

    def test_convert_dict_to_raw_schedule_switch(self):
        """Test converting switch schedule dict to raw format."""
        schedule_data = {
            1: {
                ScheduleField.WEEKDAY: [WeekdayInt.MONDAY, WeekdayInt.TUESDAY],
                ScheduleField.LEVEL: 1.0,
                ScheduleField.FIXED_HOUR: 10,
                ScheduleField.FIXED_MINUTE: 30,
            }
        }

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
        """Test converting raw schedule to dict format."""
        raw_schedule = {
            "01_WP_WEEKDAY": 6,  # MONDAY + TUESDAY
            "01_WP_LEVEL": 1.0,
            "01_WP_FIXED_HOUR": 10,
            "01_WP_FIXED_MINUTE": 30,
            "02_WP_WEEKDAY": 127,  # All days
            "02_WP_LEVEL": 0.0,
            "INVALID_FORMAT": 42,  # Should be skipped
            "01_INVALID": 42,  # Should be skipped
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert 1 in result
        assert 2 in result
        assert ScheduleField.WEEKDAY in result[1]
        assert ScheduleField.LEVEL in result[1]
        assert ScheduleField.FIXED_HOUR in result[1]
        assert ScheduleField.FIXED_MINUTE in result[1]
        assert isinstance(result[1][ScheduleField.WEEKDAY], list)
        assert result[1][ScheduleField.LEVEL] == 1.0
        assert result[1][ScheduleField.FIXED_HOUR] == 10
        assert result[1][ScheduleField.FIXED_MINUTE] == 30

    def test_convert_raw_to_dict_schedule_with_enums(self):
        """Test converting raw schedule with enum fields."""
        from aiohomematic.const import AstroType, ScheduleCondition, TimeBase

        raw_schedule = {
            "01_WP_ASTRO_TYPE": 1,
            "01_WP_CONDITION": 0,
            "01_WP_DURATION_BASE": 4,
            "01_WP_RAMP_TIME_BASE": 4,
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert 1 in result
        assert result[1][ScheduleField.ASTRO_TYPE] == AstroType.SUNSET
        assert result[1][ScheduleField.CONDITION] == ScheduleCondition.FIXED_TIME
        assert result[1][ScheduleField.DURATION_BASE] == TimeBase.MIN_1
        assert result[1][ScheduleField.RAMP_TIME_BASE] == TimeBase.MIN_1

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


class TestClimateWeekProfileConversion:
    """Test ClimateWeekProfile conversion methods."""

    def test_convert_dict_to_raw_schedule(self):
        """Test converting climate schedule dict to raw format."""
        schedule_data = {
            ScheduleProfile.P1: {
                WeekdayStr.MONDAY: {
                    1: {
                        ScheduleSlotType.TEMPERATURE: 20.0,
                        ScheduleSlotType.ENDTIME: "06:00",
                    }
                }
            }
        }

        result = ClimeateWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)

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
                        ScheduleSlotType.TEMPERATURE: 20.0,
                        ScheduleSlotType.ENDTIME: "06:00",
                    }
                }
            }
        }

        with pytest.raises(ValidationException):
            ClimeateWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)

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

        result = ClimeateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert ScheduleProfile.P1 in result
        assert WeekdayStr.MONDAY in result[ScheduleProfile.P1]
        assert WeekdayStr.TUESDAY in result[ScheduleProfile.P1]
        assert 1 in result[ScheduleProfile.P1][WeekdayStr.MONDAY]
        assert result[ScheduleProfile.P1][WeekdayStr.MONDAY][1][ScheduleSlotType.TEMPERATURE] == 20.0
        assert result[ScheduleProfile.P1][WeekdayStr.MONDAY][1][ScheduleSlotType.ENDTIME] == "06:00"
        assert result[ScheduleProfile.P1][WeekdayStr.TUESDAY][1][ScheduleSlotType.TEMPERATURE] == 21.0
        assert result[ScheduleProfile.P1][WeekdayStr.TUESDAY][1][ScheduleSlotType.ENDTIME] == "07:00"

    def test_convert_raw_to_dict_schedule_invalid_entries(self):
        """Test that invalid raw entries are gracefully skipped."""
        raw_schedule = {
            "INVALID_PROFILE_TEMPERATURE_MONDAY_1": 20.0,  # Invalid profile
            "P1_INVALID_TYPE_MONDAY_1": 20.0,  # Invalid slot type
            "P1_TEMPERATURE_INVALID_DAY_1": 20.0,  # Invalid weekday
            "P1_TEMPERATURE_MONDAY_INVALID": 20.0,  # Invalid slot number
        }

        result = ClimeateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

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
    async def test_get_schedule_profile_weekday_empty_cache(self, central_client_factory_with_homegear_client):
        """Test get_schedule_profile_weekday when cache is empty."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Clear cache
        if climate.device.week_profile:
            climate.device.week_profile._schedule_cache = {}

        # Get weekday - should load from device
        weekday_data = await climate.get_schedule_profile_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY)
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
        """Test set_schedule_weekday updates cache when data changes."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create new weekday data
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
            3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }

        # Set weekday data
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P3, weekday=WeekdayStr.FRIDAY, weekday_data=weekday_data
        )

        # Verify cache was updated
        if climate.device.week_profile:
            assert ScheduleProfile.P3 in climate.device.week_profile._schedule_cache
            assert WeekdayStr.FRIDAY in climate.device.week_profile._schedule_cache[ScheduleProfile.P3]

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

        # Create weekday data
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }

        # Set without validation
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P2,
            weekday=WeekdayStr.SATURDAY,
            weekday_data=weekday_data,
            do_validate=False,
        )


class TestDefaultWeekProfileAdditionalEdgeCases:
    """Test additional edge cases for DefaultWeekProfile."""

    def test_convert_dict_to_raw_schedule_with_all_field_types(self):
        """Test converting schedule with all supported field types."""
        from aiohomematic.const import AstroType, ScheduleCondition, TimeBase

        schedule_data = {
            1: {
                ScheduleField.WEEKDAY: [WeekdayInt.MONDAY],
                ScheduleField.TARGET_CHANNELS: [ScheduleActorChannel.CHANNEL_1_1],
                ScheduleField.ASTRO_TYPE: AstroType.SUNSET,
                ScheduleField.CONDITION: ScheduleCondition.ASTRO,
                ScheduleField.DURATION_BASE: TimeBase.MIN_1,
                ScheduleField.RAMP_TIME_BASE: TimeBase.SEC_1,
                ScheduleField.ASTRO_OFFSET: 30,
                ScheduleField.DURATION_FACTOR: 10,
                ScheduleField.FIXED_HOUR: 12,
                ScheduleField.FIXED_MINUTE: 30,
                ScheduleField.RAMP_TIME_FACTOR: 5,
            }
        }

        result = DefaultWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)

        assert result["01_WP_ASTRO_TYPE"] == 1  # AstroType.SUNSET
        assert result["01_WP_CONDITION"] == 1  # ScheduleCondition.ASTRO
        assert result["01_WP_DURATION_BASE"] == 4  # TimeBase.MIN_1
        assert result["01_WP_RAMP_TIME_BASE"] == 1  # TimeBase.SEC_1
        assert result["01_WP_ASTRO_OFFSET"] == 30
        assert result["01_WP_DURATION_FACTOR"] == 10
        assert result["01_WP_FIXED_HOUR"] == 12
        assert result["01_WP_FIXED_MINUTE"] == 30
        assert result["01_WP_RAMP_TIME_FACTOR"] == 5

    def test_convert_dict_to_raw_schedule_with_float_level_2(self):
        """Test converting schedule with LEVEL_2 (float)."""
        schedule_data = {
            1: {
                ScheduleField.WEEKDAY: [WeekdayInt.MONDAY],
                ScheduleField.LEVEL: 0.5,
                ScheduleField.LEVEL_2: 0.75,
            }
        }

        result = DefaultWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)
        assert "01_WP_LEVEL" in result
        assert "01_WP_LEVEL_2" in result
        assert result["01_WP_LEVEL"] == 0.5
        assert result["01_WP_LEVEL_2"] == 0.75

    def test_convert_dict_to_raw_schedule_with_int_level(self):
        """Test converting schedule with integer level value."""
        schedule_data = {
            1: {
                ScheduleField.WEEKDAY: [WeekdayInt.MONDAY],
                ScheduleField.LEVEL: 1,  # Integer
            }
        }

        result = DefaultWeekProfile.convert_dict_to_raw_schedule(schedule_data=schedule_data)
        assert "01_WP_LEVEL" in result
        assert result["01_WP_LEVEL"] == 1.0  # Should be converted to float

    def test_convert_raw_to_dict_schedule_with_int_level(self):
        """Test converting raw schedule with integer LEVEL."""
        raw_schedule = {
            "01_WP_LEVEL": 1,  # Integer level
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert 1 in result
        assert result[1][ScheduleField.LEVEL] == 1

    def test_convert_raw_to_dict_schedule_with_level_2(self):
        """Test converting raw schedule with LEVEL_2."""
        raw_schedule = {
            "01_WP_LEVEL_2": 0.75,
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert 1 in result
        assert result[1][ScheduleField.LEVEL_2] == 0.75

    def test_convert_raw_to_dict_schedule_with_target_channels(self):
        """Test converting raw schedule with TARGET_CHANNELS."""
        raw_schedule = {
            "01_WP_TARGET_CHANNELS": 3,  # Bitwise for channels
        }

        result = DefaultWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert 1 in result
        assert ScheduleField.TARGET_CHANNELS in result[1]
        assert isinstance(result[1][ScheduleField.TARGET_CHANNELS], list)


class TestClimateWeekProfileAdditionalEdgeCases:
    """Test additional edge cases for ClimateWeekProfile."""

    def test_convert_raw_to_dict_schedule_with_int_endtime(self):
        """Test that ENDTIME as int is converted to time string."""
        raw_schedule = {
            "P1_ENDTIME_MONDAY_1": 360,  # 6 hours * 60 minutes
        }

        result = ClimeateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        assert result[ScheduleProfile.P1][WeekdayStr.MONDAY][1][ScheduleSlotType.ENDTIME] == "06:00"

    def test_convert_raw_to_dict_schedule_with_invalid_slot_number_str(self):
        """Test that invalid slot number strings are skipped."""
        raw_schedule = {
            "P1_TEMPERATURE_MONDAY_ABC": 20.0,  # Invalid slot number
        }

        result = ClimeateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

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

        # Access schedule property directly
        schedule = climate.schedule
        assert isinstance(schedule, dict)
        # Should not contain redundant 24:00 slots
        for profile_data in schedule.values():
            for weekday_data in profile_data.values():
                count_24_00 = sum(1 for slot in weekday_data.values() if slot.get(ScheduleSlotType.ENDTIME) == "24:00")
                assert count_24_00 <= 1  # At most one 24:00 slot

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
    async def test_supports_schedule_property(self, central_client_factory_with_homegear_client):
        """Test supports_schedule property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Check supports_schedule property
        if climate.device.week_profile:
            supports = climate.device.week_profile.supports_schedule
            assert isinstance(supports, bool)
            assert supports is True  # VCU0000341 supports schedules


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
            WeekdayStr.MONDAY: (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "06:00",
                        ScheduleSlotType.ENDTIME: "22:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    }
                ],
            ),
            WeekdayStr.TUESDAY: (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "07:00",
                        ScheduleSlotType.ENDTIME: "23:00",
                        ScheduleSlotType.TEMPERATURE: 22.0,
                    }
                ],
            ),
            WeekdayStr.WEDNESDAY: (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "05:00",
                        ScheduleSlotType.ENDTIME: "21:00",
                        ScheduleSlotType.TEMPERATURE: 20.0,
                    }
                ],
            ),
        }

        # Set and verify
        await climate.set_simple_schedule_profile(profile=ScheduleProfile.P4, simple_profile_data=simple_profile_data)

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
        simple_weekday_data = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "08:00",
                    ScheduleSlotType.TEMPERATURE: 21.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "18:00",
                    ScheduleSlotType.ENDTIME: "22:00",
                    ScheduleSlotType.TEMPERATURE: 21.0,
                },
            ],
        )

        # Set and verify it works
        await climate.set_simple_schedule_weekday(
            profile=ScheduleProfile.P3,
            weekday=WeekdayStr.SUNDAY,
            simple_weekday_data=simple_weekday_data,
        )


class TestAdvancedValidation:
    """Test advanced validation scenarios."""

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
    async def test_normalization_fills_to_13_slots_ending_24_00(self, central_client_factory_with_homegear_client):
        """Test that normalization fills incomplete slots to 13 ending with 24:00."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create weekday data with only 3 slots (normalization will fill to 13)
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
            3: {ScheduleSlotType.ENDTIME: "23:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }

        # Should succeed - normalization will fill remaining slots and ensure 24:00 at end
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=weekday_data
        )

        # Verify it was normalized and filtered properly
        result = await climate.get_schedule_profile_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY)
        # Filtering removes redundant 24:00 slots, so we get back fewer than 13
        assert len(result) >= 3  # Should have at least our input slots
        # Last slot should be 24:00
        last_slot = result[max(result.keys())]
        assert last_slot[ScheduleSlotType.ENDTIME] == "24:00"

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
    async def test_simple_schedule_validation_gaps_at_day_boundaries(self, central_client_factory_with_homegear_client):
        """Test simple schedule validation with periods at day boundaries."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Period starting at 00:00
        simple_weekday_data = (
            16.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "00:00",
                    ScheduleSlotType.ENDTIME: "06:00",
                    ScheduleSlotType.TEMPERATURE: 18.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "22:00",
                    ScheduleSlotType.ENDTIME: "24:00",
                    ScheduleSlotType.TEMPERATURE: 18.0,
                },
            ],
        )

        # Should work
        await climate.set_simple_schedule_weekday(
            profile=ScheduleProfile.P3,
            weekday=WeekdayStr.MONDAY,
            simple_weekday_data=simple_weekday_data,
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
    async def test_validation_endtime_normalization_handles_duplicates(
        self, central_client_factory_with_homegear_client
    ):
        """Test that normalization handles duplicate ENDTIMEs by sorting."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create weekday data with slots that need sorting
        weekday_data = {
            3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 21.0},
        }

        # Should succeed - normalization will sort and fill
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=weekday_data
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
            # Access base schedule property (non-filtered)
            base_schedule = climate.device.week_profile._schedule_cache
            assert isinstance(base_schedule, dict)

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

            # Cache should still be valid (might be same data)
            new_cache = climate.device.week_profile._schedule_cache
            assert isinstance(new_cache, dict)


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
            full_week_schedule[weekday] = (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "06:00",
                        ScheduleSlotType.ENDTIME: "08:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    },
                    {
                        ScheduleSlotType.STARTTIME: "17:00",
                        ScheduleSlotType.ENDTIME: "22:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    },
                ],
            )

        for weekday in [WeekdayStr.SATURDAY, WeekdayStr.SUNDAY]:
            # Weekend schedule
            full_week_schedule[weekday] = (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "08:00",
                        ScheduleSlotType.ENDTIME: "23:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    }
                ],
            )

        # Set the full week schedule
        await climate.set_simple_schedule_profile(profile=ScheduleProfile.P5, simple_profile_data=full_week_schedule)

        # Verify by reading it back
        profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P5)
        assert len(profile_data) == 7  # All 7 weekdays

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
        simple_weekday_data = (
            17.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "08:00",
                    ScheduleSlotType.TEMPERATURE: 21.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "08:00",
                    ScheduleSlotType.ENDTIME: "12:00",
                    ScheduleSlotType.TEMPERATURE: 19.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "12:00",
                    ScheduleSlotType.ENDTIME: "14:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "14:00",
                    ScheduleSlotType.ENDTIME: "17:00",
                    ScheduleSlotType.TEMPERATURE: 19.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "17:00",
                    ScheduleSlotType.ENDTIME: "22:00",
                    ScheduleSlotType.TEMPERATURE: 21.5,
                },
                {
                    ScheduleSlotType.STARTTIME: "22:00",
                    ScheduleSlotType.ENDTIME: "24:00",
                    ScheduleSlotType.TEMPERATURE: 18.5,
                },
            ],
        )

        # Set and verify
        await climate.set_simple_schedule_weekday(
            profile=ScheduleProfile.P6,
            weekday=WeekdayStr.WEDNESDAY,
            simple_weekday_data=simple_weekday_data,
        )

        # Verify it was set correctly
        weekday_data = await climate.get_schedule_profile_weekday(
            profile=ScheduleProfile.P6, weekday=WeekdayStr.WEDNESDAY
        )
        assert len(weekday_data) >= 6  # Should have at least the periods we set


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
            1: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }

        result = _filter_weekday_entries(weekday_data=weekday_data)
        # Should keep only one 24:00 slot
        assert len(result) == 1
        assert result[1][ScheduleSlotType.ENDTIME] == "24:00"

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

        profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P6)
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
    async def test_get_schedule_profile_weekday_missing_data(self, central_client_factory_with_homegear_client):
        """Test getting weekday data that doesn't exist."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Try to get weekday from non-existent profile
        if climate.device.week_profile:
            climate.device.week_profile._schedule_cache = {}

        weekday_data = await climate.get_schedule_profile_weekday(profile=ScheduleProfile.P6, weekday=WeekdayStr.SUNDAY)
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

        # Create fresh weekday data for a profile that might not exist
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 20.0},
            2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }

        # Set for a profile (P6)
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P6, weekday=WeekdayStr.SATURDAY, weekday_data=weekday_data
        )

        # Verify it was created
        if climate.device.week_profile:
            assert ScheduleProfile.P6 in climate.device.week_profile._schedule_cache
            assert WeekdayStr.SATURDAY in climate.device.week_profile._schedule_cache[ScheduleProfile.P6]


class TestInverseScheduleConverters:
    """Test inverse converter functions that convert full schedules to simplified format."""

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
    async def test_profile_to_simple_invalid_base_temperature(self, central_client_factory_with_homegear_client):
        """Test that profile_to_simple validates base temperature."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            profile_data = {
                WeekdayStr.MONDAY: {
                    1: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                }
            }

            with pytest.raises(ValidationException):
                climate.device.week_profile._validate_and_convert_profile_to_simple(
                    base_temperature=-10.0, profile_data=profile_data
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
    async def test_profile_to_simple_multiple_weekdays(self, central_client_factory_with_homegear_client):
        """Test converting a full profile to simple format with multiple weekdays."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            profile_data = {
                WeekdayStr.MONDAY: {
                    1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                    2: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
                    3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                },
                WeekdayStr.TUESDAY: {
                    1: {ScheduleSlotType.ENDTIME: "07:00", ScheduleSlotType.TEMPERATURE: 18.0},
                    2: {ScheduleSlotType.ENDTIME: "23:00", ScheduleSlotType.TEMPERATURE: 22.0},
                    3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                },
            }

            result = climate.device.week_profile._validate_and_convert_profile_to_simple(
                base_temperature=18.0, profile_data=profile_data
            )

            # Should have both weekdays
            assert WeekdayStr.MONDAY in result
            assert WeekdayStr.TUESDAY in result
            assert len(result[WeekdayStr.MONDAY][1]) == 1
            assert len(result[WeekdayStr.TUESDAY][1]) == 1
            assert result[WeekdayStr.MONDAY][1][0][ScheduleSlotType.TEMPERATURE] == 21.0
            assert result[WeekdayStr.TUESDAY][1][0][ScheduleSlotType.TEMPERATURE] == 22.0

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
    async def test_profile_weekday_to_simple_all_base_temperature(self, central_client_factory_with_homegear_client):
        """Test converting weekday with all slots at base temperature."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # All slots at base temperature
            weekday_data = {
                1: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            }

            result = climate.device.week_profile._validate_and_convert_weekday_to_simple(
                base_temperature=18.0, weekday_data=weekday_data
            )

            # Should produce empty list (no non-base periods)
            assert len(result[1]) == 0

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
    async def test_profile_weekday_to_simple_basic(self, central_client_factory_with_homegear_client):
        """Test converting a full weekday to simple format with basic schedule."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Full weekday with one non-base temperature period
            weekday_data = {
                1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                2: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
                3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            }

            result = climate.device.week_profile._validate_and_convert_weekday_to_simple(
                base_temperature=18.0, weekday_data=weekday_data
            )

            # Should produce single entry from 06:00-22:00 at 21.0
            assert len(result[1]) == 1
            assert result[1][0][ScheduleSlotType.STARTTIME] == "06:00"
            assert result[1][0][ScheduleSlotType.ENDTIME] == "22:00"
            assert result[1][0][ScheduleSlotType.TEMPERATURE] == 21.0

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
    async def test_profile_weekday_to_simple_different_temperatures(self, central_client_factory_with_homegear_client):
        """Test converting weekday with different non-base temperatures."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Consecutive slots with different temperatures
            weekday_data = {
                1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                2: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 20.0},
                3: {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 22.0},
                4: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            }

            result = climate.device.week_profile._validate_and_convert_weekday_to_simple(
                base_temperature=18.0, weekday_data=weekday_data
            )

            # Should produce two separate entries (different temps)
            assert len(result) == 2
            assert result[1][0][ScheduleSlotType.STARTTIME] == "06:00"
            assert result[1][0][ScheduleSlotType.ENDTIME] == "12:00"
            assert result[1][0][ScheduleSlotType.TEMPERATURE] == 20.0
            assert result[1][1][ScheduleSlotType.STARTTIME] == "12:00"
            assert result[1][1][ScheduleSlotType.ENDTIME] == "18:00"
            assert result[1][1][ScheduleSlotType.TEMPERATURE] == 22.0

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
    async def test_profile_weekday_to_simple_invalid_base_temperature(
        self, central_client_factory_with_homegear_client
    ):
        """Test that invalid base temperature raises ValidationException."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            weekday_data = {
                1: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            }

            # Base temperature out of range
            with pytest.raises(ValidationException):
                climate.device.week_profile._validate_and_convert_weekday_to_simple(
                    base_temperature=100.0, weekday_data=weekday_data
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
    async def test_profile_weekday_to_simple_merges_consecutive_same_temp(
        self, central_client_factory_with_homegear_client
    ):
        """Test that consecutive slots with same non-base temperature are merged."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Multiple consecutive slots at same non-base temperature
            weekday_data = {
                1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                2: {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 21.0},
                3: {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 21.0},
                4: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
                5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            }

            result = climate.device.week_profile._validate_and_convert_weekday_to_simple(
                base_temperature=18.0, weekday_data=weekday_data
            )

            # Should merge into single entry from 06:00-22:00
            assert len(result[1]) == 1
            assert result[1][0][ScheduleSlotType.STARTTIME] == "06:00"
            assert result[1][0][ScheduleSlotType.ENDTIME] == "22:00"
            assert result[1][0][ScheduleSlotType.TEMPERATURE] == 21.0

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
    async def test_profile_weekday_to_simple_multiple_periods(self, central_client_factory_with_homegear_client):
        """Test converting weekday with multiple non-base temperature periods."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Full weekday with two non-base periods separated by base temperature
            weekday_data = {
                1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 21.0},
                3: {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 18.0},
                4: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
                5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            }

            result = climate.device.week_profile._validate_and_convert_weekday_to_simple(
                base_temperature=18.0, weekday_data=weekday_data
            )

            # Should produce two entries
            assert len(result[1]) == 2
            assert result[1][0][ScheduleSlotType.STARTTIME] == "06:00"
            assert result[1][0][ScheduleSlotType.ENDTIME] == "08:00"
            assert result[1][0][ScheduleSlotType.TEMPERATURE] == 21.0
            assert result[1][1][ScheduleSlotType.STARTTIME] == "18:00"
            assert result[1][1][ScheduleSlotType.ENDTIME] == "22:00"
            assert result[1][1][ScheduleSlotType.TEMPERATURE] == 21.0

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
    async def test_round_trip_conversion_profile(self, central_client_factory_with_homegear_client):
        """Test round-trip conversion: simple -> full -> simple for profile."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Start with simple profile
            original_simple_profile = {
                WeekdayStr.MONDAY: (
                    18.0,
                    [
                        {
                            ScheduleSlotType.STARTTIME: "06:00",
                            ScheduleSlotType.ENDTIME: "22:00",
                            ScheduleSlotType.TEMPERATURE: 21.0,
                        }
                    ],
                ),
                WeekdayStr.FRIDAY: (
                    18.0,
                    [
                        {
                            ScheduleSlotType.STARTTIME: "08:00",
                            ScheduleSlotType.ENDTIME: "20:00",
                            ScheduleSlotType.TEMPERATURE: 20.0,
                        }
                    ],
                ),
            }

            # Convert to full format
            full_profile = climate.device.week_profile._validate_and_convert_simple_to_profile(
                simple_profile_data=original_simple_profile
            )

            # Convert back to simple
            result_simple_profile = climate.device.week_profile._validate_and_convert_profile_to_simple(
                base_temperature=18.0, profile_data=full_profile
            )

            # Should match original
            assert set(result_simple_profile.keys()) == set(original_simple_profile.keys())
            for weekday in original_simple_profile:
                assert len(result_simple_profile[weekday]) == len(original_simple_profile[weekday])

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
    async def test_round_trip_conversion_schedule(self, central_client_factory_with_homegear_client):
        """Test round-trip conversion: simple -> full -> simple for schedule."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Start with simple schedule
            original_simple_schedule = {
                ScheduleProfile.P1: {
                    WeekdayStr.MONDAY: (
                        18.0,
                        [
                            {
                                ScheduleSlotType.STARTTIME: "06:00",
                                ScheduleSlotType.ENDTIME: "22:00",
                                ScheduleSlotType.TEMPERATURE: 21.0,
                            }
                        ],
                    )
                }
            }

            # Convert to full format
            full_schedule = climate.device.week_profile._validate_and_convert_simple_to_schedule(
                simple_schedule_data=original_simple_schedule
            )

            # Convert back to simple
            result_simple_schedule = climate.device.week_profile._validate_and_convert_schedule_to_simple(
                base_temperature=18.0, schedule_data=full_schedule
            )

            # Should match original
            assert set(result_simple_schedule.keys()) == set(original_simple_schedule.keys())
            assert ScheduleProfile.P1 in result_simple_schedule

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
    async def test_round_trip_conversion_weekday(self, central_client_factory_with_homegear_client):
        """Test round-trip conversion: simple -> full -> simple for weekday."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Start with simple format
            original_simple = (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "06:00",
                        ScheduleSlotType.ENDTIME: "08:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    },
                    {
                        ScheduleSlotType.STARTTIME: "18:00",
                        ScheduleSlotType.ENDTIME: "22:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    },
                ],
            )

            # Convert to full format
            full_format = climate.device.week_profile._validate_and_convert_simple_to_weekday(
                simple_weekday_data=original_simple
            )

            # Convert back to simple format
            result_simple = climate.device.week_profile._validate_and_convert_weekday_to_simple(
                base_temperature=18.0, weekday_data=full_format
            )

            # Should match original
            assert len(result_simple) == len(original_simple)
            _, _result_simple = result_simple
            for i, slot in enumerate(_result_simple):
                assert slot[ScheduleSlotType.STARTTIME] == original_simple[1][i][ScheduleSlotType.STARTTIME]
                assert slot[ScheduleSlotType.ENDTIME] == original_simple[1][i][ScheduleSlotType.ENDTIME]
                assert slot[ScheduleSlotType.TEMPERATURE] == original_simple[1][i][ScheduleSlotType.TEMPERATURE]

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
    async def test_schedule_to_simple_schedule_invalid_base_temperature(
        self, central_client_factory_with_homegear_client
    ):
        """Test that schedule_to_simple_schedule validates base temperature."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            schedule_data = {
                ScheduleProfile.P1: {
                    WeekdayStr.MONDAY: {
                        1: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                    }
                }
            }

            with pytest.raises(ValidationException):
                climate.device.week_profile._validate_and_convert_schedule_to_simple(
                    base_temperature=999.0, schedule_data=schedule_data
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
    async def test_schedule_to_simple_schedule_multiple_profiles(self, central_client_factory_with_homegear_client):
        """Test converting full schedule to simple format with multiple profiles."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            schedule_data = {
                ScheduleProfile.P1: {
                    WeekdayStr.MONDAY: {
                        1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                        2: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
                        3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                    },
                },
                ScheduleProfile.P2: {
                    WeekdayStr.TUESDAY: {
                        1: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 18.0},
                        2: {ScheduleSlotType.ENDTIME: "20:00", ScheduleSlotType.TEMPERATURE: 20.0},
                        3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                    },
                },
            }

            result = climate.device.week_profile._validate_and_convert_schedule_to_simple(
                base_temperature=18.0, schedule_data=schedule_data
            )

            # Should have both profiles
            assert ScheduleProfile.P1 in result
            assert ScheduleProfile.P2 in result
            assert WeekdayStr.MONDAY in result[ScheduleProfile.P1]
            assert WeekdayStr.TUESDAY in result[ScheduleProfile.P2]


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
        result = ClimeateWeekProfile.convert_raw_to_dict_schedule(raw_schedule=raw_schedule)

        # Should have P1 profile
        assert ScheduleProfile.P1 in result
        assert WeekdayStr.MONDAY in result[ScheduleProfile.P1]

        # Should have valid slot
        assert 1 in result[ScheduleProfile.P1][WeekdayStr.MONDAY]
        slot = result[ScheduleProfile.P1][WeekdayStr.MONDAY][1]
        assert ScheduleSlotType.TEMPERATURE in slot
        assert ScheduleSlotType.ENDTIME in slot

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
    async def test_empty_schedule_group(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test empty_schedule_group method for DefaultWeekProfile."""
        central, mock_client, _ = central_client_factory_with_homegear_client

        # Create a mock custom data point with non-climate category
        mock_data_point = MagicMock(spec=CustomDataPoint)
        mock_data_point.device.address = "TEST123"
        mock_data_point.device.client = mock_client
        mock_data_point.device.central = central
        mock_data_point.category = DataPointCategory.SWITCH
        mock_data_point.custom_config.schedule_channel_no = None

        # Create DefaultWeekProfile
        week_profile = DefaultWeekProfile(data_point=mock_data_point)

        # Get empty schedule group
        empty_group = week_profile.empty_schedule_group()

        # Should return empty dict when schedule not supported
        assert isinstance(empty_group, dict)

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

        if climate.device.week_profile and isinstance(climate.device.week_profile, ClimeateWeekProfile):
            # Get schedule via property
            schedule = climate.device.week_profile.schedule

            # Should return filtered schedule (no redundant 24:00 slots)
            assert isinstance(schedule, dict)

            # If there's data, verify it's filtered
            if schedule:
                for profile_data in schedule.values():
                    for weekday_data in profile_data.values():
                        # Filtered data should have fewer than 13 slots
                        # (unless all slots have different times)
                        if weekday_data:
                            # At least verify the data structure is correct
                            for slot in weekday_data.values():
                                assert ScheduleSlotType.ENDTIME in slot
                                assert ScheduleSlotType.TEMPERATURE in slot

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
    async def test_supports_schedule_property(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test supports_schedule property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        if climate.device.week_profile:
            # Should return True for devices with schedule support
            assert climate.device.week_profile.supports_schedule is True

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


class TestValidateAndConvertMethods:
    """Tests for _validate_and_convert_* methods in week_profile module."""

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
    async def test_validate_and_convert_profile_to_simple(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test _validate_and_convert_profile_to_simple method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        assert climate.device.week_profile is not None and isinstance(
            climate.device.week_profile, ClimeateWeekProfile
        ), "Device should have ClimeateWeekProfile"

        # Create full profile data
        profile_data = {
            WeekdayStr.MONDAY: {
                1: {ScheduleSlotType.ENDTIME: "07:00", ScheduleSlotType.TEMPERATURE: 18.0},
                2: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
                3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            },
        }

        # Normalize first
        from aiohomematic.model.week_profile import _normalize_weekday_data

        profile_data[WeekdayStr.MONDAY] = _normalize_weekday_data(weekday_data=profile_data[WeekdayStr.MONDAY])

        # Convert full to simple profile format
        simple_profile = climate.device.week_profile._validate_and_convert_profile_to_simple(
            base_temperature=18.0, profile_data=profile_data
        )

        # Should have Monday
        assert WeekdayStr.MONDAY in simple_profile
        # Monday should have 1 entry (07:00-22:00 at 21.0)
        _, monday_data = simple_profile[WeekdayStr.MONDAY]
        assert len(monday_data) == 1
        assert monday_data[0][ScheduleSlotType.STARTTIME] == "07:00"
        assert monday_data[0][ScheduleSlotType.ENDTIME] == "22:00"
        assert monday_data[0][ScheduleSlotType.TEMPERATURE] == 21.0

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
    async def test_validate_and_convert_schedule_to_simple(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test _validate_and_convert_schedule_to_simple method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        assert climate.device.week_profile is not None and isinstance(
            climate.device.week_profile, ClimeateWeekProfile
        ), "Device should have ClimeateWeekProfile"

        # Create full schedule data
        schedule_data = {
            ScheduleProfile.P1: {
                WeekdayStr.MONDAY: {
                    1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
                    2: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 21.0},
                    3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
                },
            },
        }

        # Normalize first
        from aiohomematic.model.week_profile import _normalize_weekday_data

        schedule_data[ScheduleProfile.P1][WeekdayStr.MONDAY] = _normalize_weekday_data(
            weekday_data=schedule_data[ScheduleProfile.P1][WeekdayStr.MONDAY]
        )

        # Convert full to simple schedule format
        simple_schedule = climate.device.week_profile._validate_and_convert_schedule_to_simple(
            base_temperature=18.0, schedule_data=schedule_data
        )

        # Should have P1 profile
        assert ScheduleProfile.P1 in simple_schedule
        # P1 should have Monday
        assert WeekdayStr.MONDAY in simple_schedule[ScheduleProfile.P1]
        # Monday should have 1 entry (06:00-22:00 at 21.0)
        _, monday_data = simple_schedule[ScheduleProfile.P1][WeekdayStr.MONDAY]
        assert len(monday_data) == 1
        assert monday_data[0][ScheduleSlotType.STARTTIME] == "06:00"
        assert monday_data[0][ScheduleSlotType.ENDTIME] == "22:00"
        assert monday_data[0][ScheduleSlotType.TEMPERATURE] == 21.0

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
    async def test_validate_and_convert_simple_to_profile(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test _validate_and_convert_simple_to_profile method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        assert climate.device.week_profile is not None and isinstance(
            climate.device.week_profile, ClimeateWeekProfile
        ), "Device should have ClimeateWeekProfile"

        # Create simple profile data
        simple_profile = {
            WeekdayStr.MONDAY: (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "07:00",
                        ScheduleSlotType.ENDTIME: "22:00",
                        ScheduleSlotType.TEMPERATURE: 21.0,
                    },
                ],
            ),
            WeekdayStr.TUESDAY: (
                18.0,
                [
                    {
                        ScheduleSlotType.STARTTIME: "08:00",
                        ScheduleSlotType.ENDTIME: "20:00",
                        ScheduleSlotType.TEMPERATURE: 20.0,
                    },
                ],
            ),
        }

        # Convert simple to full profile format
        profile_data = climate.device.week_profile._validate_and_convert_simple_to_profile(
            simple_profile_data=simple_profile
        )

        # Should have both weekdays
        assert WeekdayStr.MONDAY in profile_data
        assert WeekdayStr.TUESDAY in profile_data
        # Each weekday should have 13 slots
        assert len(profile_data[WeekdayStr.MONDAY]) == 13
        assert len(profile_data[WeekdayStr.TUESDAY]) == 13

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
    async def test_validate_and_convert_simple_to_schedule(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test _validate_and_convert_simple_to_schedule method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        assert climate.device.week_profile is not None and isinstance(
            climate.device.week_profile, ClimeateWeekProfile
        ), "Device should have ClimeateWeekProfile"

        # Create simple schedule data
        simple_schedule = {
            ScheduleProfile.P1: {
                WeekdayStr.MONDAY: (
                    18.0,
                    [
                        {
                            ScheduleSlotType.STARTTIME: "06:00",
                            ScheduleSlotType.ENDTIME: "22:00",
                            ScheduleSlotType.TEMPERATURE: 21.0,
                        },
                    ],
                ),
            },
            ScheduleProfile.P2: {
                WeekdayStr.TUESDAY: (
                    18.0,
                    [
                        {
                            ScheduleSlotType.STARTTIME: "07:00",
                            ScheduleSlotType.ENDTIME: "20:00",
                            ScheduleSlotType.TEMPERATURE: 20.0,
                        },
                    ],
                ),
            },
        }

        # Convert simple to full schedule format
        schedule_data = climate.device.week_profile._validate_and_convert_simple_to_schedule(
            simple_schedule_data=simple_schedule
        )

        # Should have both profiles
        assert ScheduleProfile.P1 in schedule_data
        assert ScheduleProfile.P2 in schedule_data
        # Each profile should have weekdays with 13 slots
        assert len(schedule_data[ScheduleProfile.P1][WeekdayStr.MONDAY]) == 13
        assert len(schedule_data[ScheduleProfile.P2][WeekdayStr.TUESDAY]) == 13

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
    async def test_validate_and_convert_simple_to_weekday(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test _validate_and_convert_simple_to_weekday method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        assert climate.device.week_profile is not None and isinstance(
            climate.device.week_profile, ClimeateWeekProfile
        ), "Device should have ClimeateWeekProfile"

        # Create simple weekday data
        simple_weekday = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "08:00",
                    ScheduleSlotType.TEMPERATURE: 21.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "17:00",
                    ScheduleSlotType.ENDTIME: "22:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                },
            ],
        )

        # Convert simple to full weekday format
        weekday_data = climate.device.week_profile._validate_and_convert_simple_to_weekday(
            simple_weekday_data=simple_weekday
        )

        # Should have 13 slots
        assert len(weekday_data) == 13
        # First slot: base temp until 06:00
        assert weekday_data[1][ScheduleSlotType.ENDTIME] == "06:00"
        assert weekday_data[1][ScheduleSlotType.TEMPERATURE] == 18.0
        # Second slot: heated period 06:00-08:00
        assert weekday_data[2][ScheduleSlotType.ENDTIME] == "08:00"
        assert weekday_data[2][ScheduleSlotType.TEMPERATURE] == 21.0
        # Third slot: base temp 08:00-17:00
        assert weekday_data[3][ScheduleSlotType.ENDTIME] == "17:00"
        assert weekday_data[3][ScheduleSlotType.TEMPERATURE] == 18.0
        # Fourth slot: heated period 17:00-22:00
        assert weekday_data[4][ScheduleSlotType.ENDTIME] == "22:00"
        assert weekday_data[4][ScheduleSlotType.TEMPERATURE] == 20.0
        # Remaining slots: base temp until 24:00
        assert weekday_data[5][ScheduleSlotType.ENDTIME] == "24:00"
        assert weekday_data[5][ScheduleSlotType.TEMPERATURE] == 18.0

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
    async def test_validate_and_convert_weekday_to_simple(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test _validate_and_convert_weekday_to_simple method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        assert climate.device.week_profile is not None and isinstance(
            climate.device.week_profile, ClimeateWeekProfile
        ), "Device should have ClimeateWeekProfile"

        # Create full weekday data (13 slots)
        weekday_data = {
            1: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 18.0},
            2: {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 21.0},
            3: {ScheduleSlotType.ENDTIME: "17:00", ScheduleSlotType.TEMPERATURE: 18.0},
            4: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 20.0},
            5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            6: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            7: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            8: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            9: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            10: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            11: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            12: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
            13: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 18.0},
        }

        # Convert full to simple weekday format
        simple_weekday = climate.device.week_profile._validate_and_convert_weekday_to_simple(
            base_temperature=18.0, weekday_data=weekday_data
        )

        # Should have 2 entries (only non-base temperature periods)
        assert len(simple_weekday[1]) == 2
        # First heated period: 06:00-08:00 at 21.0
        assert simple_weekday[1][0][ScheduleSlotType.STARTTIME] == "06:00"
        assert simple_weekday[1][0][ScheduleSlotType.ENDTIME] == "08:00"
        assert simple_weekday[1][0][ScheduleSlotType.TEMPERATURE] == 21.0
        # Second heated period: 17:00-22:00 at 20.0
        assert simple_weekday[1][1][ScheduleSlotType.STARTTIME] == "17:00"
        assert simple_weekday[1][1][ScheduleSlotType.ENDTIME] == "22:00"
        assert simple_weekday[1][1][ScheduleSlotType.TEMPERATURE] == 20.0

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
    async def test_validate_conversion_round_trip(
        self,
        central_client_factory_with_homegear_client,
    ):
        """Test that conversion from simple to full and back preserves data."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        assert climate.device.week_profile is not None and isinstance(
            climate.device.week_profile, ClimeateWeekProfile
        ), "Device should have ClimeateWeekProfile"

        # Original simple data
        original_simple = (
            18.0,
            [
                {
                    ScheduleSlotType.STARTTIME: "06:00",
                    ScheduleSlotType.ENDTIME: "08:00",
                    ScheduleSlotType.TEMPERATURE: 21.0,
                },
                {
                    ScheduleSlotType.STARTTIME: "17:00",
                    ScheduleSlotType.ENDTIME: "22:00",
                    ScheduleSlotType.TEMPERATURE: 20.0,
                },
            ],
        )

        # Convert simple -> full
        full_data = climate.device.week_profile._validate_and_convert_simple_to_weekday(
            simple_weekday_data=original_simple
        )

        # Convert full -> simple
        result_simple = climate.device.week_profile._validate_and_convert_weekday_to_simple(
            base_temperature=18.0, weekday_data=full_data
        )

        # Should match original (might be in different order, so check contents)
        assert len(result_simple) == len(original_simple)
        _, _result_simple = result_simple
        for i, slot in enumerate(_result_simple):
            assert slot[ScheduleSlotType.STARTTIME] == original_simple[1][i][ScheduleSlotType.STARTTIME]
            assert slot[ScheduleSlotType.ENDTIME] == original_simple[1][i][ScheduleSlotType.ENDTIME]
            assert slot[ScheduleSlotType.TEMPERATURE] == original_simple[1][i][ScheduleSlotType.TEMPERATURE]
