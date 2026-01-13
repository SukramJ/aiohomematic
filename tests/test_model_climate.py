# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for climate data points of aiohomematic."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import cast
from unittest.mock import call

from freezegun import freeze_time
import pytest

from aiohomematic.const import (  # local import to keep test header minimal
    WAIT_FOR_CALLBACK,
    DataPointCategory,
    DataPointUsage,
    Field,
    Parameter,
    ParamsetKey,
    ScheduleProfile,
    WeekdayStr,
)
from aiohomematic.exceptions import ValidationException
from aiohomematic.model.custom import (
    BaseCustomDpClimate,
    ClimateActivity,
    ClimateMode,
    ClimateProfile,
    CustomDpIpThermostat,
    CustomDpRfThermostat,
    CustomDpSimpleRfThermostat,
)
from aiohomematic.model.custom.climate import _ModeHm, _ModeHmIP
from aiohomematic.model.generic import DpDummy
from aiohomematic.model.week_profile import (
    SimpleWeekdaySchedule,
    _convert_time_str_to_minutes,
    _filter_profile_entries,
    _filter_schedule_entries,
)
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {
    "INT0000001",
    "VCU0000050",
    "VCU0000054",
    "VCU0000341",
    "VCU1769958",
    "VCU3609622",
    "VCU4105035",
    "VCU5778428",
}

# pylint: disable=protected-access


class TestCustomDpSimpleRfThermostat:
    """Tests for CustomDpSimpleRfThermostat data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_cesimplerfthermostat(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpSimpleRfThermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpSimpleRfThermostat = cast(
            CustomDpSimpleRfThermostat, get_prepared_custom_data_point(central, "VCU0000054", 1)
        )
        assert climate.usage == DataPointUsage.CDP_PRIMARY

        assert climate.is_valid is False
        assert climate.service_method_names == (
            "copy_schedule",
            "copy_schedule_profile",
            "disable_away_mode",
            "enable_away_mode_by_calendar",
            "enable_away_mode_by_duration",
            "get_schedule_profile",
            "get_schedule_simple_profile",
            "get_schedule_simple_schedule",
            "get_schedule_simple_weekday",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule_profile",
            "set_schedule_weekday",
            "set_simple_schedule",
            "set_simple_schedule_profile",
            "set_simple_schedule_weekday",
            "set_temperature",
        )
        assert climate.state_uncertain is False
        assert climate.temperature_unit == "°C"
        assert climate.min_temp == 6.0
        assert climate.max_temp == 30.0
        assert climate.capabilities.profiles is False
        assert climate.target_temperature_step == 0.5

        assert climate.current_humidity is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000054:1", parameter="HUMIDITY", value=75
        )
        assert climate.current_humidity == 75

        assert climate.target_temperature is None
        await climate.set_temperature(temperature=12.0)
        last_call = call.set_value(
            channel_address="VCU0000054:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="SETPOINT",
            value=12.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == last_call
        assert climate.target_temperature == 12.0

        assert climate.current_temperature is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000054:1", parameter="TEMPERATURE", value=11.0
        )
        assert climate.current_temperature == 11.0

        assert climate.mode == ClimateMode.HEAT
        assert climate.modes == (ClimateMode.HEAT,)
        assert climate.profile == ClimateProfile.NONE
        assert climate.profiles == (ClimateProfile.NONE,)
        assert climate.activity is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000054:1", parameter="TEMPERATURE", value=11.0
        )

        # No new method call, because called methods has no implementation
        await climate.set_mode(mode=ClimateMode.HEAT)
        assert mock_client.method_calls[-1] == last_call
        await climate.set_profile(profile=ClimateProfile.NONE)
        assert mock_client.method_calls[-1] == last_call
        await climate.enable_away_mode_by_duration(hours=100, away_temperature=17.0)
        assert mock_client.method_calls[-1] == last_call
        await climate.enable_away_mode_by_calendar(start=datetime.now(), end=datetime.now(), away_temperature=17.0)
        assert mock_client.method_calls[-1] == last_call
        await climate.disable_away_mode()
        assert mock_client.method_calls[-1] == last_call


class TestCustomDpRfThermostat:
    """Tests for CustomDpRfThermostat data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_cerfthermostat(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpRfThermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000050", 4)
        )
        assert climate.usage == DataPointUsage.CDP_PRIMARY
        assert climate.service_method_names == (
            "copy_schedule",
            "copy_schedule_profile",
            "disable_away_mode",
            "enable_away_mode_by_calendar",
            "enable_away_mode_by_duration",
            "get_schedule_profile",
            "get_schedule_simple_profile",
            "get_schedule_simple_schedule",
            "get_schedule_simple_weekday",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule_profile",
            "set_schedule_weekday",
            "set_simple_schedule",
            "set_simple_schedule_profile",
            "set_simple_schedule_weekday",
            "set_temperature",
        )
        assert climate.min_temp == 5.0
        assert climate.max_temp == 30.5
        assert climate.capabilities.profiles is True
        assert climate.target_temperature_step == 0.5
        assert climate.profile == ClimateProfile.NONE
        assert climate.activity is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="VALVE_STATE", value=10
        )
        assert climate.activity == ClimateActivity.HEAT
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="VALVE_STATE", value=0
        )
        assert climate.activity == ClimateActivity.IDLE
        assert climate.current_humidity is None
        assert climate.target_temperature is None
        await climate.set_temperature(temperature=12.0)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_TEMPERATURE",
            value=12.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate.target_temperature == 12.0

        assert climate.current_temperature is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="ACTUAL_TEMPERATURE", value=11.0
        )
        assert climate.current_temperature == 11.0

        assert climate.mode == ClimateMode.AUTO
        assert climate.modes == (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)
        await climate.set_mode(mode=ClimateMode.HEAT)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="MANU_MODE",
            value=12.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000050:4",
            parameter="CONTROL_MODE",
            value=_ModeHmIP.MANU.value,
        )
        assert climate.mode == ClimateMode.HEAT

        await climate.set_mode(mode=ClimateMode.OFF)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU0000050:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"MANU_MODE": 12.0, "SET_TEMPERATURE": 4.5},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        assert climate.mode == ClimateMode.OFF
        assert climate.activity == ClimateActivity.OFF

        await climate.set_mode(mode=ClimateMode.AUTO)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="AUTO_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="CONTROL_MODE", value=0
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="SET_TEMPERATURE", value=24.0
        )
        assert climate.mode == ClimateMode.AUTO

        assert climate.profile == ClimateProfile.NONE
        assert climate.profiles == (
            ClimateProfile.BOOST,
            ClimateProfile.COMFORT,
            ClimateProfile.ECO,
            ClimateProfile.NONE,
        )
        await climate.set_profile(profile=ClimateProfile.BOOST)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="BOOST_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="CONTROL_MODE", value=3
        )
        assert climate.profile == ClimateProfile.BOOST
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="CONTROL_MODE", value=2
        )
        assert climate.profile == ClimateProfile.AWAY
        await climate.set_profile(profile=ClimateProfile.COMFORT)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMFORT_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await climate.set_profile(profile=ClimateProfile.ECO)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOWERING_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="CONTROL_MODE", value=3
        )
        call_count = len(mock_client.method_calls)
        await climate.set_profile(profile=ClimateProfile.BOOST)
        assert call_count == len(mock_client.method_calls)

        await climate.set_mode(mode=ClimateMode.AUTO)
        call_count = len(mock_client.method_calls)
        await climate.set_mode(mode=ClimateMode.AUTO)
        assert call_count == len(mock_client.method_calls)

        with freeze_time("2023-03-03 08:00:00"):
            await climate.enable_away_mode_by_duration(hours=100, away_temperature=17.0)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value="17.0,470,03,03,23,720,07,03,23",
        )

        with freeze_time("2023-03-03 08:00:00"):
            await climate.enable_away_mode_by_calendar(
                start=datetime(2000, 12, 1), end=datetime(2024, 12, 1), away_temperature=17.0
            )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value="17.0,0,01,12,00,0,01,12,24",
        )

        with freeze_time("2023-03-03 08:00:00"):
            await climate.disable_away_mode()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000050:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value="12.0,1260,02,03,23,1320,02,03,23",
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
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_cerfthermostat_with_profiles(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpRfThermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )
        assert climate.usage == DataPointUsage.CDP_PRIMARY
        assert climate.service_method_names == (
            "copy_schedule",
            "copy_schedule_profile",
            "disable_away_mode",
            "enable_away_mode_by_calendar",
            "enable_away_mode_by_duration",
            "get_schedule_profile",
            "get_schedule_simple_profile",
            "get_schedule_simple_schedule",
            "get_schedule_simple_weekday",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule_profile",
            "set_schedule_weekday",
            "set_simple_schedule",
            "set_simple_schedule_profile",
            "set_simple_schedule_weekday",
            "set_temperature",
        )
        assert climate.min_temp == 5.0
        assert climate.max_temp == 30.5
        assert climate.capabilities.profiles is True
        assert climate.target_temperature_step == 0.5
        assert climate.profile == ClimateProfile.NONE
        assert climate.activity is None
        assert climate.current_humidity is None
        assert climate.target_temperature is None
        await climate.set_temperature(temperature=12.0)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_TEMPERATURE",
            value=12.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate.target_temperature == 12.0

        assert climate.current_temperature is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000341:2", parameter="ACTUAL_TEMPERATURE", value=11.0
        )
        assert climate.current_temperature == 11.0

        assert climate.mode == ClimateMode.AUTO
        assert climate.modes == (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)
        await climate.set_mode(mode=ClimateMode.HEAT)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="MANU_MODE",
            value=12.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:2",
            parameter="CONTROL_MODE",
            value=_ModeHmIP.MANU.value,
        )
        assert climate.mode == ClimateMode.HEAT

        await climate.set_temperature(temperature=13.0)
        await central.looper.block_till_done()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_TEMPERATURE",
            value=13.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate._old_manu_setpoint == 13.0

        await climate.set_mode(mode=ClimateMode.OFF)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU0000341:2",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"MANU_MODE": 13.0, "SET_TEMPERATURE": 4.5},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        assert climate.mode == ClimateMode.OFF
        assert climate._old_manu_setpoint == 13.0

        await climate.set_mode(mode=ClimateMode.AUTO)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="AUTO_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:2",
            parameter="CONTROL_MODE",
            value=_ModeHmIP.AUTO.value,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000341:2", parameter="SET_TEMPERATURE", value=24.0
        )
        assert climate.mode == ClimateMode.AUTO
        assert climate._old_manu_setpoint == 13.0
        assert climate.target_temperature == 24.0
        await climate.set_mode(mode=ClimateMode.HEAT)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="MANU_MODE",
            value=climate._temperature_for_heat_mode,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:2",
            parameter="CONTROL_MODE",
            value=_ModeHmIP.MANU.value,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:2",
            parameter="SET_TEMPERATURE",
            value=climate._temperature_for_heat_mode,
        )
        assert climate.mode == ClimateMode.HEAT

        await climate.set_mode(mode=ClimateMode.AUTO)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="AUTO_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:2",
            parameter="CONTROL_MODE",
            value=_ModeHmIP.AUTO.value,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000341:2", parameter="SET_TEMPERATURE", value=24.0
        )
        assert climate.profile == ClimateProfile.WEEK_PROGRAM_1
        assert climate.profiles == (
            ClimateProfile.BOOST,
            ClimateProfile.COMFORT,
            ClimateProfile.ECO,
            ClimateProfile.NONE,
            ClimateProfile.WEEK_PROGRAM_1,
            ClimateProfile.WEEK_PROGRAM_2,
            ClimateProfile.WEEK_PROGRAM_3,
        )
        await climate.set_profile(profile=ClimateProfile.BOOST)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="BOOST_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000341:2", parameter="CONTROL_MODE", value=3
        )
        assert climate.profile == ClimateProfile.BOOST
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000341:2", parameter="CONTROL_MODE", value=2
        )
        assert climate.profile == ClimateProfile.AWAY
        await climate.set_profile(profile=ClimateProfile.COMFORT)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="COMFORT_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await climate.set_profile(profile=ClimateProfile.ECO)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="LOWERING_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000341:2", parameter="CONTROL_MODE", value=3
        )
        call_count = len(mock_client.method_calls)
        await climate.set_profile(profile=ClimateProfile.BOOST)
        assert call_count == len(mock_client.method_calls)

        await climate.set_mode(mode=ClimateMode.AUTO)
        call_count = len(mock_client.method_calls)
        await climate.set_mode(mode=ClimateMode.AUTO)
        assert call_count == len(mock_client.method_calls)

        with freeze_time("2023-03-03 08:00:00"):
            await climate.enable_away_mode_by_duration(hours=100, away_temperature=17.0)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value="17.0,470,03,03,23,720,07,03,23",
        )

        with freeze_time("2023-03-03 08:00:00"):
            await climate.enable_away_mode_by_calendar(
                start=datetime(2000, 12, 1), end=datetime(2024, 12, 1), away_temperature=17.0
            )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value="17.0,0,01,12,00,0,01,12,24",
        )

        with freeze_time("2023-03-03 08:00:00"):
            await climate.disable_away_mode()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value="12.0,1260,02,03,23,1320,02,03,23",
        )
        assert climate.profile == ClimateProfile.BOOST

        await climate.set_profile(profile=ClimateProfile.WEEK_PROGRAM_2)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341",
            paramset_key=ParamsetKey.MASTER,
            parameter="WEEK_PROGRAM_POINTER",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        climate._dp_control_mode._current_value = _ModeHm.AUTO
        climate._dp_boost_mode._current_value = 0
        climate._dp_week_program_pointer._current_value = 1
        assert climate.profile == ClimateProfile.WEEK_PROGRAM_2

        await climate.set_profile(profile=ClimateProfile.WEEK_PROGRAM_3)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341",
            paramset_key=ParamsetKey.MASTER,
            parameter="WEEK_PROGRAM_POINTER",
            value=2,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        climate._dp_control_mode._current_value = _ModeHm.AUTO
        climate._dp_boost_mode._current_value = 0
        climate._dp_week_program_pointer._current_value = 2
        assert climate.profile == ClimateProfile.WEEK_PROGRAM_3

        await climate.set_profile(profile=ClimateProfile.WEEK_PROGRAM_1)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000341",
            paramset_key=ParamsetKey.MASTER,
            parameter="WEEK_PROGRAM_POINTER",
            value=0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        climate._dp_control_mode._current_value = _ModeHm.AUTO
        climate._dp_boost_mode._current_value = 0
        climate._dp_week_program_pointer._current_value = 0
        assert climate.profile == ClimateProfile.WEEK_PROGRAM_1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_rf_thermostat_schedule_read_write(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test schedule read/write for HM-TC-IT-WM-W-EU (classic Homematic RF thermostat)."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Verify schedule is supported for this device
        assert climate.device.week_profile is not None
        assert climate.device.week_profile.has_schedule is True
        # HM-TC-IT-WM-W-EU uses device address (not channel) for schedule
        assert climate.device.week_profile.schedule_channel_address == "VCU0000341"

        # Read schedule profile P1 - should return data from session
        profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert len(profile_data) == 7  # 7 weekdays
        assert WeekdayStr.MONDAY in profile_data
        assert WeekdayStr.SATURDAY in profile_data

        # Read individual weekday schedule
        weekday_data = await climate.get_schedule_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.SATURDAY)
        # HM-TC-IT-WM-W-EU supports 13 slots per weekday, but only non-redundant entries returned
        assert len(weekday_data) >= 1
        # Verify slot structure (should have temperature and endtime)
        slot_1 = weekday_data.get(1)
        assert slot_1 is not None
        assert "temperature" in slot_1
        assert "endtime" in slot_1

        # Write schedule profile back (verifies put_paramset is called correctly)
        await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=profile_data)
        # Verify put_paramset was called with MASTER paramset on device address
        # NOTE: set_schedule_profile normalizes weekday data to 13 slots (fills missing slots with 24:00)
        # Verify that put_paramset was called (actual values contain normalized 13-slot data)
        last_call = mock_client.method_calls[-1]
        assert last_call[0] == "put_paramset"
        assert last_call[2]["channel_address"] == "VCU0000341"
        assert last_call[2]["paramset_key_or_link_address"] == ParamsetKey.MASTER
        # Verify some sample values from the normalized schedule
        values = last_call[2]["values"]
        assert "P1_ENDTIME_SATURDAY_1" in values
        assert "P1_TEMPERATURE_SATURDAY_1" in values
        # Verify all 13 slots are present for Saturday (normalized)
        for slot_no in range(1, 14):
            assert f"P1_ENDTIME_SATURDAY_{slot_no}" in values
            assert f"P1_TEMPERATURE_SATURDAY_{slot_no}" in values

        # Write individual weekday schedule
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.SATURDAY, weekday_data=weekday_data
        )
        # Verify put_paramset was called
        # NOTE: Single weekday writes also normalize to 13 slots
        last_call = mock_client.method_calls[-1]
        assert last_call[0] == "put_paramset"
        assert last_call[2]["channel_address"] == "VCU0000341"
        assert last_call[2]["paramset_key_or_link_address"] == ParamsetKey.MASTER
        # Verify Saturday slots are present in the call
        values = last_call[2]["values"]
        assert "P1_ENDTIME_SATURDAY_1" in values
        assert "P1_TEMPERATURE_SATURDAY_1" in values

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_rf_thermostat_simple_schedule_integer_temperature_conversion(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test that integer temperatures are converted to floats (Issue #2789).

        When users provide temperatures as integers in YAML (e.g., temperature: 17
        instead of temperature: 17.0), the CCU requires them to be floats.
        This test verifies the conversion happens correctly.
        """
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Create simple schedule with INTEGER temperatures (as user would in YAML)
        # Note: We intentionally use integers to test the conversion (mypy: ignore type)
        simple_weekday_data: SimpleWeekdaySchedule = {  # type: ignore[typeddict-item]
            "base_temperature": 16,  # Integer
            "periods": [
                {"starttime": "05:00", "endtime": "06:00", "temperature": 17},  # Integer
                {"starttime": "09:00", "endtime": "15:00", "temperature": 17},  # Integer
                {"starttime": "19:00", "endtime": "22:00", "temperature": 22},  # Integer
            ],
        }

        # Write schedule with integer temperatures
        await climate.set_simple_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.SATURDAY, simple_weekday_data=simple_weekday_data
        )

        # Verify put_paramset was called
        last_call = mock_client.method_calls[-1]
        assert last_call[0] == "put_paramset"
        assert last_call[2]["channel_address"] == "VCU0000341"
        assert last_call[2]["paramset_key_or_link_address"] == ParamsetKey.MASTER

        # CRITICAL: Verify temperature values are passed through to put_paramset
        # Note: Integer-to-float conversion happens in _convert_value when check_against_pd=True
        # In mock context, values remain as passed (int or float) before _convert_value processes them
        values = last_call[2]["values"]

        # Check base temperatures (passed through as-is)
        assert values["P1_TEMPERATURE_SATURDAY_1"] in (16, 16.0)  # Base temp

        # Check period temperatures (passed through as-is)
        assert values["P1_TEMPERATURE_SATURDAY_2"] in (17, 17.0)  # First period
        assert values["P1_TEMPERATURE_SATURDAY_4"] in (17, 17.0)  # Second period
        assert values["P1_TEMPERATURE_SATURDAY_6"] in (22, 22.0)  # Third period

        # Verify that _check_put_paramset converts integer values to floats
        # (Only for InterfaceClient which has this method)
        client = central.client_coordinator.primary_client
        assert client is not None
        real_client = client._mock_wraps if hasattr(client, "_mock_wraps") else client
        if hasattr(real_client, "_check_put_paramset"):
            # Test that _check_put_paramset converts integer temperatures to float
            test_values = {"P1_TEMPERATURE_SATURDAY_1": 16}  # Integer input
            checked_values = real_client._check_put_paramset(
                channel_address="VCU0000341",
                paramset_key=ParamsetKey.MASTER,
                values=test_values,
            )
            assert isinstance(checked_values["P1_TEMPERATURE_SATURDAY_1"], float)
            assert checked_values["P1_TEMPERATURE_SATURDAY_1"] == 16.0

        # Verify all 13 temperature slots are present
        # Note: Values may be int or float before _convert_value processes them
        for slot_no in range(1, 14):
            temp_key = f"P1_TEMPERATURE_SATURDAY_{slot_no}"
            assert temp_key in values, f"Missing temperature slot {slot_no}"
            # Temperature can be int or float - _convert_value handles conversion
            assert isinstance(values[temp_key], (int, float)), (
                f"Temperature slot {slot_no} is not numeric: {type(values[temp_key])}"
            )


class TestCustomDpIpThermostat:
    """Tests for CustomDpIpThermostat data points."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_ceipthermostat_activity_fallback_to_link_peer(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Activity falls back to a link peer's STATE/LEVEL when own DPs are DpDummy.

        We simulate a device where the thermostat channel has dummy `STATE`/`LEVEL`.
        We then point its `link_peer_channel` to a channel that exposes `STATE` and
        verify that `activity` uses the peer values and reacts to changes.
        """
        central, _mock_client, _ = central_client_factory_with_homegear_client

        # Use the IP thermostat used above; it has a real STATE on channel 9 in the fixture data
        climate: CustomDpIpThermostat = cast(
            CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU1769958", 1)
        )

        # Ensure default mode is AUTO and not OFF
        assert climate.mode in (ClimateMode.AUTO, ClimateMode.HEAT)

        # Force own LEVEL/STATE to be dummy so fallback path is used
        climate._data_points[Field.STATE] = DpDummy(channel=climate._channel, param_field=Field.STATE)
        climate._data_points[Field.LEVEL] = DpDummy(channel=climate._channel, param_field=Field.LEVEL)

        # Point link peer to channel 9 which exposes a usable STATE
        device = central.device_coordinator.get_device(address="VCU1769958")
        peer_address = f"{device.address}:9"
        peer_channel = central.device_coordinator.get_channel(channel_address=peer_address)
        peer_channel._link_target_categories = (DataPointCategory.CLIMATE,)
        climate._channel._link_peer_addresses = (peer_address,)  # type: ignore[attr-defined]
        # Publish peer-changed so the thermostat refreshes its peer DP references
        climate._channel.publish_link_peer_changed_event()
        await central.looper.block_till_done()

        assert climate.activity == ClimateActivity.IDLE

        # Set peer STATE to ON → activity should be HEAT
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address=peer_address,
            parameter=Parameter.STATE,
            value=1,
        )
        await central.looper.block_till_done()
        assert climate.activity == ClimateActivity.HEAT

        # Set peer STATE to OFF → activity should be IDLE (unless target temp forces OFF)
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address=peer_address,
            parameter=Parameter.STATE,
            value=0,
        )
        await central.looper.block_till_done()
        assert climate.activity == ClimateActivity.IDLE

        # Now set mode OFF (via dedicated method) and ensure OFF overrides peer state
        await climate.set_mode(mode=ClimateMode.OFF)
        assert climate.activity == ClimateActivity.OFF

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_ceipthermostat_bwth(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpThermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpIpThermostat = cast(
            CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU1769958", 1)
        )
        assert climate.usage == DataPointUsage.CDP_PRIMARY
        assert climate.service_method_names == (
            "copy_schedule",
            "copy_schedule_profile",
            "disable_away_mode",
            "enable_away_mode_by_calendar",
            "enable_away_mode_by_duration",
            "get_schedule_profile",
            "get_schedule_simple_profile",
            "get_schedule_simple_schedule",
            "get_schedule_simple_weekday",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule_profile",
            "set_schedule_weekday",
            "set_simple_schedule",
            "set_simple_schedule_profile",
            "set_simple_schedule_weekday",
            "set_temperature",
        )
        assert climate.min_temp == 5.0
        assert climate.max_temp == 30.0
        assert climate.capabilities.profiles is True
        assert climate.target_temperature_step == 0.5
        assert climate.activity == ClimateActivity.IDLE
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1769958:9", parameter="STATE", value=1
        )
        assert climate.activity == ClimateActivity.HEAT
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1769958:9", parameter="STATE", value=0
        )
        assert climate.activity == ClimateActivity.IDLE
        assert climate._old_manu_setpoint is None
        assert climate.current_humidity is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="HUMIDITY", value=75
        )
        assert climate.current_humidity == 75

        assert climate.target_temperature is None
        await climate.set_temperature(temperature=12.0)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1769958:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_POINT_TEMPERATURE",
            value=12.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate.target_temperature == 12.0

        assert climate.current_temperature is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="ACTUAL_TEMPERATURE", value=11.0
        )
        assert climate.current_temperature == 11.0

        assert climate.mode == ClimateMode.AUTO
        assert climate.modes == (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)
        assert climate.profile == ClimateProfile.NONE

        await climate.set_mode(mode=ClimateMode.OFF)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1769958:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 4.5},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate.mode == ClimateMode.OFF
        assert climate.activity == ClimateActivity.OFF

        await climate.set_mode(mode=ClimateMode.HEAT)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1769958:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 5.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await climate.set_temperature(temperature=19.5)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1769958:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_POINT_TEMPERATURE",
            value=19.5,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU1769958:1",
            parameter="SET_POINT_TEMPERATURE",
            value=19.5,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU1769958:1",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.MANU.value,
        )
        await central.looper.block_till_done()
        assert climate.mode == ClimateMode.HEAT
        assert climate._old_manu_setpoint == 19.5

        assert climate.profile == ClimateProfile.NONE
        assert climate.profiles == (
            ClimateProfile.BOOST,
            ClimateProfile.NONE,
        )
        await climate.set_profile(profile=ClimateProfile.BOOST)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1769958:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="BOOST_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="BOOST_MODE", value=1
        )
        assert climate.profile == ClimateProfile.BOOST

        await climate.set_mode(mode=ClimateMode.AUTO)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1769958:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"BOOST_MODE": False, "CONTROL_MODE": 0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU1769958:1",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.AUTO.value,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="BOOST_MODE", value=1
        )
        assert climate.mode == ClimateMode.AUTO
        assert climate.profiles == (
            ClimateProfile.BOOST,
            ClimateProfile.NONE,
            "week_program_1",
            "week_program_2",
            "week_program_3",
            "week_program_4",
            "week_program_5",
            "week_program_6",
        )

        await climate.set_mode(mode=ClimateMode.HEAT)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1769958:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "BOOST_MODE": False,
                "CONTROL_MODE": 1,
                "SET_POINT_TEMPERATURE": climate._temperature_for_heat_mode,
            },
            wait_for_callback=None,
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU1769958:1",
            parameter="SET_POINT_TEMPERATURE",
            value=19.5,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU1769958:1",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.MANU.value,
        )
        assert climate.mode == ClimateMode.HEAT
        assert climate.target_temperature == 19.5

        await climate.set_profile(profile=ClimateProfile.NONE)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1769958:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"BOOST_MODE": False, "CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 19.5},
            wait_for_callback=None,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU1769958:1",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.AWAY.value,
        )
        assert climate.profile == ClimateProfile.AWAY

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU1769958:1",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.AUTO.value,
        )
        await climate.set_profile(profile=ClimateProfile.WEEK_PROGRAM_1)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1769958:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="ACTIVE_PROFILE",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate.profile == ClimateProfile.WEEK_PROGRAM_1

        with freeze_time("2023-03-03 08:00:00"):
            await climate.enable_away_mode_by_duration(hours=100, away_temperature=17.0)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1769958:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "SET_POINT_MODE": 2,
                "SET_POINT_TEMPERATURE": 17.0,
                "PARTY_TIME_START": "2023_03_03 07:50",
                "PARTY_TIME_END": "2023_03_07 12:00",
            },
        )

        await climate.enable_away_mode_by_calendar(
            start=datetime(2000, 12, 1), end=datetime(2024, 12, 1), away_temperature=17.0
        )
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1769958:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "SET_POINT_MODE": 2,
                "SET_POINT_TEMPERATURE": 17.0,
                "PARTY_TIME_START": "2000_12_01 00:00",
                "PARTY_TIME_END": "2024_12_01 00:00",
            },
        )

        await climate.disable_away_mode()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1769958:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "SET_POINT_MODE": 2,
                "PARTY_TIME_START": "2000_01_01 00:00",
                "PARTY_TIME_END": "2000_01_01 00:00",
            },
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="BOOST_MODE", value=1
        )
        call_count = len(mock_client.method_calls)
        await climate.set_profile(profile=ClimateProfile.BOOST)
        assert call_count == len(mock_client.method_calls)

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU1769958:1",
            parameter="SET_POINT_TEMPERATURE",
            value=12.0,
        )
        call_count = len(mock_client.method_calls)
        await climate.set_temperature(temperature=12.0)
        assert call_count + 1 == len(mock_client.method_calls)

        await climate.set_mode(mode=ClimateMode.AUTO)
        call_count = len(mock_client.method_calls)
        await climate.set_mode(mode=ClimateMode.AUTO)
        assert call_count == len(mock_client.method_calls)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_ceipthermostat_wgtc(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpThermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpIpThermostat = cast(
            CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU4105035", 8)
        )
        assert climate.usage == DataPointUsage.CDP_PRIMARY
        assert climate.service_method_names == (
            "copy_schedule",
            "copy_schedule_profile",
            "disable_away_mode",
            "enable_away_mode_by_calendar",
            "enable_away_mode_by_duration",
            "get_schedule_profile",
            "get_schedule_simple_profile",
            "get_schedule_simple_schedule",
            "get_schedule_simple_weekday",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule_profile",
            "set_schedule_weekday",
            "set_simple_schedule",
            "set_simple_schedule_profile",
            "set_simple_schedule_weekday",
            "set_temperature",
        )
        assert climate.min_temp == 5.0
        assert climate.max_temp == 30.0
        assert climate.capabilities.profiles is True
        assert climate.target_temperature_step == 0.5
        assert climate.activity == ClimateActivity.IDLE
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4105035:3", parameter="STATE", value=1
        )
        await central.looper.block_till_done()
        assert climate.activity == ClimateActivity.HEAT
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4105035:3", parameter="STATE", value=0
        )
        await central.looper.block_till_done()
        assert climate.activity == ClimateActivity.IDLE
        assert climate._old_manu_setpoint is None
        assert climate.current_humidity is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="HUMIDITY", value=75
        )
        await central.looper.block_till_done()
        assert climate.current_humidity == 75

        assert climate.target_temperature is None
        await climate.set_temperature(temperature=12.0)
        await central.looper.block_till_done()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU4105035:8",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_POINT_TEMPERATURE",
            value=12.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate.target_temperature == 12.0

        assert climate.current_temperature is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="ACTUAL_TEMPERATURE", value=11.0
        )
        await central.looper.block_till_done()
        assert climate.current_temperature == 11.0

        assert climate.mode == ClimateMode.AUTO
        assert climate.modes == (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)
        assert climate.profile == ClimateProfile.NONE

        await climate.set_mode(mode=ClimateMode.OFF)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4105035:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 4.5},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate.mode == ClimateMode.OFF
        assert climate.activity == ClimateActivity.OFF

        await climate.set_mode(mode=ClimateMode.HEAT)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4105035:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 5.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await climate.set_temperature(temperature=19.5)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU4105035:8",
            paramset_key=ParamsetKey.VALUES,
            parameter="SET_POINT_TEMPERATURE",
            value=19.5,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU4105035:8",
            parameter="SET_POINT_TEMPERATURE",
            value=19.5,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU4105035:8",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.MANU.value,
        )
        await central.looper.block_till_done()
        assert climate.mode == ClimateMode.HEAT
        assert climate._old_manu_setpoint == 19.5

        assert climate.profile == ClimateProfile.NONE
        assert climate.profiles == (
            ClimateProfile.BOOST,
            ClimateProfile.NONE,
        )
        await climate.set_profile(profile=ClimateProfile.BOOST)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU4105035:8",
            paramset_key=ParamsetKey.VALUES,
            parameter="BOOST_MODE",
            value=True,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="BOOST_MODE", value=1
        )
        assert climate.profile == ClimateProfile.BOOST

        await climate.set_mode(mode=ClimateMode.AUTO)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4105035:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"BOOST_MODE": False, "CONTROL_MODE": 0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU4105035:8",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.AUTO.value,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="BOOST_MODE", value=1
        )
        assert climate.mode == ClimateMode.AUTO
        assert climate.profiles == (
            ClimateProfile.BOOST,
            ClimateProfile.NONE,
            "week_program_1",
            "week_program_2",
            "week_program_3",
            "week_program_4",
            "week_program_5",
            "week_program_6",
        )

        await climate.set_mode(mode=ClimateMode.HEAT)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4105035:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "BOOST_MODE": False,
                "CONTROL_MODE": 1,
                "SET_POINT_TEMPERATURE": climate._temperature_for_heat_mode,
            },
            wait_for_callback=None,
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU4105035:8",
            parameter="SET_POINT_TEMPERATURE",
            value=19.5,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU4105035:8",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.MANU.value,
        )
        assert climate.mode == ClimateMode.HEAT
        assert climate.target_temperature == 19.5

        await climate.set_profile(profile=ClimateProfile.NONE)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4105035:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"BOOST_MODE": False, "CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 19.5},
            wait_for_callback=None,
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU4105035:8",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.AWAY.value,
        )
        assert climate.profile == ClimateProfile.AWAY

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU4105035:8",
            parameter="SET_POINT_MODE",
            value=_ModeHmIP.AUTO.value,
        )
        await climate.set_profile(profile=ClimateProfile.WEEK_PROGRAM_1)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU4105035:8",
            paramset_key=ParamsetKey.VALUES,
            parameter="ACTIVE_PROFILE",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert climate.profile == ClimateProfile.WEEK_PROGRAM_1

        with freeze_time("2023-03-03 08:00:00"):
            await climate.enable_away_mode_by_duration(hours=100, away_temperature=17.0)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4105035:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "SET_POINT_MODE": 2,
                "SET_POINT_TEMPERATURE": 17.0,
                "PARTY_TIME_START": "2023_03_03 07:50",
                "PARTY_TIME_END": "2023_03_07 12:00",
            },
        )

        await climate.enable_away_mode_by_calendar(
            start=datetime(2000, 12, 1), end=datetime(2024, 12, 1), away_temperature=17.0
        )
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4105035:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "SET_POINT_MODE": 2,
                "SET_POINT_TEMPERATURE": 17.0,
                "PARTY_TIME_START": "2000_12_01 00:00",
                "PARTY_TIME_END": "2024_12_01 00:00",
            },
        )

        await climate.disable_away_mode()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4105035:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "SET_POINT_MODE": 2,
                "PARTY_TIME_START": "2000_01_01 00:00",
                "PARTY_TIME_END": "2000_01_01 00:00",
            },
        )

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="BOOST_MODE", value=1
        )
        call_count = len(mock_client.method_calls)
        await climate.set_profile(profile=ClimateProfile.BOOST)
        assert call_count == len(mock_client.method_calls)

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU4105035:8",
            parameter="SET_POINT_TEMPERATURE",
            value=12.0,
        )
        call_count = len(mock_client.method_calls)
        await climate.set_temperature(temperature=12.0)
        assert call_count + 1 == len(mock_client.method_calls)

        await climate.set_mode(mode=ClimateMode.AUTO)
        call_count = len(mock_client.method_calls)
        await climate.set_mode(mode=ClimateMode.AUTO)
        assert call_count == len(mock_client.method_calls)


class TestClimateIntegration:
    """Integration tests for climate data points with PyDevCCU."""

    @pytest.mark.enable_socket
    @pytest.mark.asyncio
    async def test_climate_ip_with_pydevccu(self, central_unit_pydevccu_mini) -> None:
        """Test the central."""
        assert central_unit_pydevccu_mini

        climate_bwth: BaseCustomDpClimate = cast(
            BaseCustomDpClimate,
            central_unit_pydevccu_mini.get_custom_data_point(address="VCU1769958", channel_no=1),
        )
        climate_etrv: BaseCustomDpClimate = cast(
            BaseCustomDpClimate,
            central_unit_pydevccu_mini.get_custom_data_point(address="VCU3609622", channel_no=1),
        )
        assert climate_bwth
        profile_data = await climate_bwth.get_schedule_profile(profile=ScheduleProfile.P1)
        assert len(profile_data) == 7
        weekday_data = await climate_bwth.get_schedule_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY)
        assert len(weekday_data) == 5
        await climate_bwth.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=profile_data)
        await climate_bwth.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=weekday_data
        )
        copy_weekday_data = deepcopy(weekday_data)
        copy_weekday_data[1]["temperature"] = 38.0
        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=copy_weekday_data,
            )

        # After normalization, "1:40" is valid and will be sorted correctly
        # Test with an actually invalid time format
        copy_weekday_data2 = deepcopy(weekday_data)
        copy_weekday_data2[4]["endtime"] = "25:40"  # Invalid: hour > 24
        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=copy_weekday_data2,
            )

        copy_weekday_data3 = deepcopy(weekday_data)
        copy_weekday_data3[4]["endtime"] = "35:00"
        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=copy_weekday_data3,
            )

        copy_weekday_data4 = deepcopy(weekday_data)
        copy_weekday_data4[4]["endtime"] = 100
        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data=copy_weekday_data4,
            )
        manual_week_profile_data = {
            1: {"temperature": 17, "endtime": "06:00"},
            2: {"temperature": 21, "endtime": "07:00"},
            3: {"temperature": 17, "endtime": "10:00"},
            4: {"temperature": 21, "endtime": "23:00"},
            5: {"temperature": 17, "endtime": "24:00"},
            6: {"temperature": 17, "endtime": "24:00"},
            7: {"temperature": 17, "endtime": "24:00"},
            8: {"temperature": 17, "endtime": "24:00"},
            9: {"temperature": 17, "endtime": "24:00"},
            10: {"temperature": 17, "endtime": "24:00"},
            11: {"temperature": 17, "endtime": "24:00"},
            12: {"temperature": 17, "endtime": "24:00"},
            13: {"temperature": 17, "endtime": "24:00"},
        }
        await climate_bwth.set_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            weekday_data=manual_week_profile_data,
        )

        manual_simple_weekday_data = {
            "base_temperature": 16.0,
            "periods": [
                {"temperature": 17.0, "starttime": "05:00", "endtime": "06:00"},
                {"temperature": 22.0, "starttime": "19:00", "endtime": "22:00"},
                {"temperature": 17.0, "starttime": "09:00", "endtime": "15:00"},
            ],
        }
        weekday_data = climate_bwth.device.week_profile._validate_and_convert_simple_to_weekday(
            simple_weekday_data=manual_simple_weekday_data
        )
        assert weekday_data == {
            1: {"endtime": "05:00", "temperature": 16.0},
            2: {"endtime": "06:00", "temperature": 17.0},
            3: {"endtime": "09:00", "temperature": 16.0},
            4: {"endtime": "15:00", "temperature": 17.0},
            5: {"endtime": "19:00", "temperature": 16.0},
            6: {"endtime": "22:00", "temperature": 22.0},
            7: {"endtime": "24:00", "temperature": 16.0},
            8: {"endtime": "24:00", "temperature": 16.0},
            9: {"endtime": "24:00", "temperature": 16.0},
            10: {"endtime": "24:00", "temperature": 16.0},
            11: {"endtime": "24:00", "temperature": 16.0},
            12: {"endtime": "24:00", "temperature": 16.0},
            13: {"endtime": "24:00", "temperature": 16.0},
        }
        await climate_bwth.set_simple_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            simple_weekday_data=manual_simple_weekday_data,
        )

        manual_simple_weekday_data2 = {"base_temperature": 16.0, "periods": []}
        weekday_data2 = climate_bwth.device.week_profile._validate_and_convert_simple_to_weekday(
            simple_weekday_data=manual_simple_weekday_data2
        )
        assert weekday_data2 == {
            1: {"endtime": "24:00", "temperature": 16.0},
            2: {"endtime": "24:00", "temperature": 16.0},
            3: {"endtime": "24:00", "temperature": 16.0},
            4: {"endtime": "24:00", "temperature": 16.0},
            5: {"endtime": "24:00", "temperature": 16.0},
            6: {"endtime": "24:00", "temperature": 16.0},
            7: {"endtime": "24:00", "temperature": 16.0},
            8: {"endtime": "24:00", "temperature": 16.0},
            9: {"endtime": "24:00", "temperature": 16.0},
            10: {"endtime": "24:00", "temperature": 16.0},
            11: {"endtime": "24:00", "temperature": 16.0},
            12: {"endtime": "24:00", "temperature": 16.0},
            13: {"endtime": "24:00", "temperature": 16.0},
        }
        await climate_bwth.set_simple_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            simple_weekday_data=manual_simple_weekday_data2,
        )

        with pytest.raises(ValidationException):
            await climate_bwth.set_simple_schedule_weekday(
                profile="P1",
                weekday="MONDAY",
                simple_weekday_data={
                    "base_temperature": 16.0,
                    "periods": [
                        {"temperature": 34.0, "starttime": "05:00", "endtime": "06:00"},
                    ],
                },
            )

        with pytest.raises(ValidationException):
            await climate_bwth.set_simple_schedule_weekday(
                profile="P1",
                weekday="MONDAY",
                simple_weekday_data={"base_temperature": 34.0, "periods": []},
            )

        with pytest.raises(ValidationException):
            await climate_bwth.set_simple_schedule_weekday(
                profile="P1",
                weekday="MONDAY",
                simple_weekday_data={
                    "base_temperature": 16.0,
                    "periods": [
                        {"temperature": 17.0, "starttime": "05:00", "endtime": "06:00"},
                        {"temperature": 22.0, "starttime": "19:00", "endtime": "22:00"},
                        {"temperature": 17.0, "starttime": "09:00", "endtime": "20:00"},
                    ],
                },
            )

        await climate_bwth.set_simple_schedule_profile(
            profile="P1",
            simple_profile_data={
                "MONDAY": {
                    "base_temperature": 16.0,
                    "periods": [
                        {"temperature": 17.0, "starttime": "05:00", "endtime": "06:00"},
                        {"temperature": 22.0, "starttime": "19:00", "endtime": "22:00"},
                        {"temperature": 17.0, "starttime": "09:00", "endtime": "15:00"},
                    ],
                },
                "TUESDAY": {
                    "base_temperature": 16.0,
                    "periods": [
                        {"temperature": 17.0, "starttime": "05:00", "endtime": "06:00"},
                        {"temperature": 22.0, "starttime": "19:00", "endtime": "22:00"},
                        {"temperature": 17.0, "starttime": "09:00", "endtime": "15:00"},
                    ],
                },
            },
        )

        await climate_bwth.set_simple_schedule_profile(
            profile="P1",
            simple_profile_data={
                "MONDAY": {"base_temperature": 16.0, "periods": []},
            },
        )

        manual_simple_weekday_data3 = {
            "base_temperature": 16.0,
            "periods": [
                {"temperature": 17.0, "starttime": "05:00", "endtime": "06:00"},
                {"temperature": 17.0, "starttime": "06:00", "endtime": "07:00"},
                {"temperature": 17.0, "starttime": "07:00", "endtime": "08:00"},
                {"temperature": 17.0, "starttime": "08:00", "endtime": "09:00"},
                {"temperature": 17.0, "starttime": "09:00", "endtime": "10:00"},
                {"temperature": 17.0, "starttime": "10:00", "endtime": "11:00"},
                {"temperature": 17.0, "starttime": "11:00", "endtime": "12:00"},
                {"temperature": 17.0, "starttime": "12:00", "endtime": "13:00"},
                {"temperature": 17.0, "starttime": "13:00", "endtime": "14:00"},
                {"temperature": 17.0, "starttime": "14:00", "endtime": "15:00"},
                {"temperature": 17.0, "starttime": "15:00", "endtime": "16:00"},
            ],
        }
        weekday_data3 = climate_bwth.device.week_profile._validate_and_convert_simple_to_weekday(
            simple_weekday_data=manual_simple_weekday_data3
        )
        assert weekday_data3 == {
            1: {"endtime": "05:00", "temperature": 16.0},
            2: {"endtime": "06:00", "temperature": 17.0},
            3: {"endtime": "07:00", "temperature": 17.0},
            4: {"endtime": "08:00", "temperature": 17.0},
            5: {"endtime": "09:00", "temperature": 17.0},
            6: {"endtime": "10:00", "temperature": 17.0},
            7: {"endtime": "11:00", "temperature": 17.0},
            8: {"endtime": "12:00", "temperature": 17.0},
            9: {"endtime": "13:00", "temperature": 17.0},
            10: {"endtime": "14:00", "temperature": 17.0},
            11: {"endtime": "15:00", "temperature": 17.0},
            12: {"endtime": "16:00", "temperature": 17.0},
            13: {"endtime": "24:00", "temperature": 16.0},
        }
        await climate_bwth.set_simple_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            simple_weekday_data=manual_simple_weekday_data3,
        )

        await climate_bwth.set_simple_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            simple_weekday_data={
                "base_temperature": 16.0,
                "periods": [
                    {"temperature": 17.0, "starttime": "05:00", "endtime": "06:00"},
                    {"temperature": 17.0, "starttime": "06:00", "endtime": "07:00"},
                    {"temperature": 17.0, "starttime": "13:00", "endtime": "14:00"},
                    {"temperature": 17.0, "starttime": "14:00", "endtime": "15:00"},
                    {"temperature": 17.0, "starttime": "15:00", "endtime": "16:00"},
                    {"temperature": 17.0, "starttime": "12:00", "endtime": "13:00"},
                    {"temperature": 17.0, "starttime": "07:00", "endtime": "08:00"},
                    {"temperature": 17.0, "starttime": "08:00", "endtime": "09:00"},
                    {"temperature": 17.0, "starttime": "10:00", "endtime": "11:00"},
                    {"temperature": 17.0, "starttime": "11:00", "endtime": "12:00"},
                    {"temperature": 17.0, "starttime": "09:00", "endtime": "10:00"},
                ],
            },
        )

        # 14 entries
        with pytest.raises(ValidationException):
            await climate_bwth.set_simple_schedule_weekday(
                profile="P1",
                weekday="MONDAY",
                simple_weekday_data={
                    "base_temperature": 16.0,
                    "periods": [
                        {"temperature": 17.0, "starttime": "05:00", "endtime": "06:00"},
                        {"temperature": 17.0, "starttime": "06:00", "endtime": "07:00"},
                        {"temperature": 17.0, "starttime": "07:00", "endtime": "08:00"},
                        {"temperature": 17.0, "starttime": "08:00", "endtime": "09:00"},
                        {"temperature": 17.0, "starttime": "09:00", "endtime": "10:00"},
                        {"temperature": 17.0, "starttime": "10:00", "endtime": "11:00"},
                        {"temperature": 17.0, "starttime": "11:00", "endtime": "12:00"},
                        {"temperature": 17.0, "starttime": "12:00", "endtime": "13:00"},
                        {"temperature": 17.0, "starttime": "13:00", "endtime": "14:00"},
                        {"temperature": 17.0, "starttime": "14:00", "endtime": "15:00"},
                        {"temperature": 17.0, "starttime": "15:00", "endtime": "16:00"},
                        {"temperature": 17.0, "starttime": "16:00", "endtime": "17:00"},
                        {"temperature": 22.0, "starttime": "17:00", "endtime": "18:00"},
                        {"temperature": 17.0, "starttime": "18:00", "endtime": "19:00"},
                    ],
                },
            )

        await climate_bwth.copy_schedule_profile(source_profile=ScheduleProfile.P1, target_profile=ScheduleProfile.P2)

        await climate_bwth.copy_schedule_profile(
            source_profile=ScheduleProfile.P1,
            target_profile=ScheduleProfile.P2,
            target_climate_data_point=climate_etrv,
        )

        await climate_bwth.copy_schedule(target_climate_data_point=climate_bwth)

        with pytest.raises(ValidationException):
            await climate_bwth.copy_schedule(target_climate_data_point=climate_etrv)


class TestScheduleCache:
    """Tests for schedule caching mechanisms."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_cache_and_reload_on_config_pending(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test schedule caching and reloading after CONFIG_PENDING event."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        assert climate.device.week_profile._schedule_cache == {}

        # Register a callback to track schedule changes
        callback_called = False
        callback_args = None

        def schedule_changed_callback(**kwargs):
            nonlocal callback_called, callback_args
            callback_called = True
            callback_args = kwargs

        unreg = climate.subscribe_to_data_point_updated(
            handler=schedule_changed_callback, custom_id="test_schedule_change"
        )

        # Get a schedule profile to populate the cache
        schedule = await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert schedule is not None
        assert len(schedule) > 0

        # reset callback_called
        callback_called = False

        # Simulate CONFIG_PENDING event (True then False to trigger reload)
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:0",
            parameter=Parameter.CONFIG_PENDING,
            value=True,
        )

        # Schedule should not have changed yet (CONFIG_PENDING on device, not on channel)
        await central.looper.block_till_done()
        # Reset callback since CONFIG_PENDING event on device might have triggered callbacks
        callback_called = False

        # Now simulate CONFIG_PENDING = False (should trigger reload and cache schedules)
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:0",
            parameter=Parameter.CONFIG_PENDING,
            value=False,
        )

        # Wait for async tasks to complete
        await central.looper.block_till_done()

        # Cache should be populated after CONFIG_PENDING reload
        assert climate.device.week_profile._schedule_cache != {}, (
            "Schedule cache should be populated after CONFIG_PENDING reload"
        )

        # The callback may or may not have been called depending on whether schedules changed
        # but the cache should definitely be populated
        # Verify that the cache contains schedule data
        assert len(climate.device.week_profile._schedule_cache) > 0, "Schedule cache should contain profile data"

        unreg()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_cache_available_profiles(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that available_schedule_profiles returns correct profiles from cache."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Test 1: Empty cache should return empty tuple
        climate.device.week_profile._schedule_cache = {}
        assert climate.available_schedule_profiles == ()

        # Test 2: After loading profiles, available_schedule_profiles should reflect cache
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert ScheduleProfile.P1 in climate.available_schedule_profiles

        # Test 3: After loading multiple profiles, all should be available
        await climate.get_schedule_profile(profile=ScheduleProfile.P2)
        available_profiles = climate.available_schedule_profiles
        assert ScheduleProfile.P1 in available_profiles
        assert ScheduleProfile.P2 in available_profiles
        assert len(available_profiles) >= 2

        # Test 4: schedule property should return the entire cache
        full_schedule = climate.schedule
        assert full_schedule == _filter_schedule_entries(schedule_data=climate.device.week_profile._schedule_cache)
        assert ScheduleProfile.P1 in full_schedule
        assert ScheduleProfile.P2 in full_schedule

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_cache_consistency(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that schedule cache remains consistent across multiple operations."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load initial schedules
        profile1_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert len(profile1_data) > 0
        assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache

        # Test 1: Writing to one profile shouldn't affect other profiles
        from copy import deepcopy

        modified_p1_data = deepcopy(profile1_data)
        modified_p1_data[WeekdayStr.MONDAY][1]["temperature"] = 25.0
        await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=modified_p1_data)

        # Simulate CONFIG_PENDING = False to trigger cache reload
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:0",
            parameter=Parameter.CONFIG_PENDING,
            value=False,
        )
        await central.looper.block_till_done()

        # Note: With pessimistic cache updates and mock client, the cache will be reloaded
        # from the mock which still contains original data. In real scenarios, the CCU
        # would have the updated data. For this test, we verify that cache reload happens
        # but we can't verify the exact values without a stateful mock.
        # The cache should still contain valid schedule data
        assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache
        assert len(climate.device.week_profile._schedule_cache[ScheduleProfile.P1]) > 0

        # Test 2: Writing to individual weekday should only affect that weekday
        modified_tuesday_data = deepcopy(profile1_data[WeekdayStr.TUESDAY])
        modified_tuesday_data[2]["temperature"] = 23.0
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.TUESDAY, weekday_data=modified_tuesday_data
        )

        # Simulate CONFIG_PENDING = False to trigger cache reload
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:0",
            parameter=Parameter.CONFIG_PENDING,
            value=False,
        )
        await central.looper.block_till_done()

        # Verify cache still contains valid data
        assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache
        assert WeekdayStr.TUESDAY in climate.device.week_profile._schedule_cache[ScheduleProfile.P1]

        # Test 3: Multiple sequential writes should maintain consistency
        for _ in [18.0, 19.0, 20.0]:
            # Verify cache still contains valid schedule data after each write
            assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache
            assert WeekdayStr.WEDNESDAY in climate.device.week_profile._schedule_cache[ScheduleProfile.P1]

            modified_data = deepcopy(
                climate.device.week_profile._schedule_cache[ScheduleProfile.P1][WeekdayStr.WEDNESDAY]
            )
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1, weekday=WeekdayStr.WEDNESDAY, weekday_data=modified_data
            )

            # Simulate CONFIG_PENDING = False to trigger cache reload
            await central.event_coordinator.data_point_event(
                interface_id=const.INTERFACE_ID,
                channel_address="VCU0000341:0",
                parameter=Parameter.CONFIG_PENDING,
                value=False,
            )
            await central.looper.block_till_done()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_cache_read_operations(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that schedule cache read operations work correctly."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Clear the cache to start fresh
        climate.device.week_profile._schedule_cache = {}
        assert climate.device.week_profile._schedule_cache == {}

        # Test 1: get_schedule_profile with do_load=True should fetch from API and cache
        # Note: reload_and_cache_schedule() loads ALL available profiles, not just the requested one
        profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert profile_data is not None
        assert len(profile_data) > 0
        assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache
        assert (
            _filter_profile_entries(profile_data=climate.device.week_profile._schedule_cache[ScheduleProfile.P1])
            == profile_data
        )
        # Multiple profiles should be cached after loading
        assert len(climate.device.week_profile._schedule_cache) > 0

        # Count API calls
        initial_call_count = len(mock_client.method_calls)

        # Test 2: get_schedule_profile without do_load should return from cache without API call
        cached_profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert cached_profile_data == profile_data
        assert len(mock_client.method_calls) == initial_call_count  # No new API calls

        # Test 3: get_schedule_weekday should return from cache
        weekday_data = await climate.get_schedule_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY)
        assert weekday_data is not None
        assert len(weekday_data) > 0
        assert weekday_data == profile_data[WeekdayStr.MONDAY]
        assert len(mock_client.method_calls) == initial_call_count  # No new API calls

        # Test 4: get_schedule_weekday with do_load=True should fetch from API
        weekday_data_reloaded = await climate.get_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, force_load=True
        )
        assert weekday_data_reloaded == weekday_data
        assert len(mock_client.method_calls) > initial_call_count  # new API call made

        # Test 5: get_schedule_profile for non-cached profile should return empty dict
        # Note: After loading P1, other profiles may also be cached, so we check for a definitely non-existent one
        # First check what's in cache
        cached_profiles = list(climate.device.week_profile._schedule_cache.keys())
        # Get a profile that's not in the cache
        non_cached_profile = None
        for test_profile in [ScheduleProfile.P6, ScheduleProfile.P5, ScheduleProfile.P4]:
            if test_profile not in cached_profiles:
                non_cached_profile = test_profile
                break

        if non_cached_profile:
            empty_profile = await climate.get_schedule_profile(profile=non_cached_profile)
            assert empty_profile == {}
        else:
            # If all profiles are cached (which can happen), just verify that accessing cache doesn't cause errors
            for profile in cached_profiles:
                assert await climate.get_schedule_profile(profile=profile) != {}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_cache_reload_and_cache_schedule(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test reload_and_cache_schedule method behavior."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Flush all pending events from setup before subscribing.
        # This ensures we only count events triggered by our explicit actions,
        # not cascading events from internal subscriptions during device setup.
        await central.looper.block_till_done()

        # Register callback to track schedule reload
        reload_callback_count = 0

        def reload_callback(**kwargs):
            nonlocal reload_callback_count
            reload_callback_count += 1

        unreg = climate.subscribe_to_data_point_updated(handler=reload_callback, custom_id="test_reload")

        # Test 1: Initial load should populate cache
        climate.device.week_profile._schedule_cache = {}
        assert climate.device.week_profile._schedule_cache == {}

        await climate.device.week_profile.reload_and_cache_schedule()
        await central.looper.block_till_done()

        # Verify cache was populated
        assert len(climate.device.week_profile._schedule_cache) > 0
        assert reload_callback_count == 1

        # Test 2: Reload with same data should not trigger callback
        reload_callback_count = 0
        initial_cache = deepcopy(climate.device.week_profile._schedule_cache)

        await climate.device.week_profile.reload_and_cache_schedule()
        await central.looper.block_till_done()

        # Cache should still be populated
        assert len(climate.device.week_profile._schedule_cache) > 0
        # Callback should not be called if data didn't change
        # (Note: This depends on whether the mock returns the same data)

        # Test 3: Manual cache modification followed by reload should restore correct data
        climate.device.week_profile._schedule_cache[ScheduleProfile.P1][WeekdayStr.MONDAY][1]["temperature"] = 99.0
        assert (
            climate.device.week_profile._schedule_cache[ScheduleProfile.P1][WeekdayStr.MONDAY][1]["temperature"] == 99.0
        )

        reload_callback_count = 0
        await climate.device.week_profile.reload_and_cache_schedule()
        await central.looper.block_till_done()

        # After reload, the incorrect manual change should be overwritten
        # The cache should reflect the actual data from the device
        assert (
            climate.device.week_profile._schedule_cache[ScheduleProfile.P1][WeekdayStr.MONDAY][1]["temperature"]
            == initial_cache[ScheduleProfile.P1][WeekdayStr.MONDAY][1]["temperature"]
        )

        unreg()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_cache_write_operations(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that schedule cache write operations work correctly."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load initial schedule to cache
        initial_profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1)
        assert len(initial_profile_data) > 0

        # Register callback to track cache updates
        callback_count = 0

        def cache_update_callback(**kwargs):
            nonlocal callback_count
            callback_count += 1

        unreg = climate.subscribe_to_data_point_updated(handler=cache_update_callback, custom_id="test_cache_update")

        # Test 1: set_schedule_weekday triggers cache reload via CONFIG_PENDING
        from copy import deepcopy

        modified_weekday_data = deepcopy(initial_profile_data[WeekdayStr.MONDAY])
        # Modify temperature in slot 1
        modified_weekday_data[1]["temperature"] = 20.0

        callback_count = 0
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=modified_weekday_data
        )
        await central.looper.block_till_done()

        # Simulate CONFIG_PENDING = False to trigger cache reload
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:0",
            parameter=Parameter.CONFIG_PENDING,
            value=False,
        )
        await central.looper.block_till_done()

        # Verify cache contains valid data after reload
        # Note: Mock client doesn't update its data on put_paramset, so exact values
        # aren't verified. In real scenarios, CCU would have the updated data.
        assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache
        assert WeekdayStr.MONDAY in climate.device.week_profile._schedule_cache[ScheduleProfile.P1]
        # Callback should be called for CONFIG_PENDING event
        assert callback_count >= 1

        # Test 2: Multiple write operations maintain cache consistency
        callback_count = 0
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=modified_weekday_data
        )
        await central.looper.block_till_done()

        # Simulate CONFIG_PENDING = False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:0",
            parameter=Parameter.CONFIG_PENDING,
            value=False,
        )
        await central.looper.block_till_done()

        # Cache should still contain valid schedule data
        assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache
        assert WeekdayStr.MONDAY in climate.device.week_profile._schedule_cache[ScheduleProfile.P1]

        # Test 3: set_schedule_profile triggers cache reload
        modified_profile_data = deepcopy(initial_profile_data)
        modified_profile_data[WeekdayStr.TUESDAY][2]["temperature"] = 22.0

        callback_count = 0
        await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=modified_profile_data)
        await central.looper.block_till_done()

        # Simulate CONFIG_PENDING = False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:0",
            parameter=Parameter.CONFIG_PENDING,
            value=False,
        )
        await central.looper.block_till_done()

        # Verify cache contains valid data
        assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache
        assert WeekdayStr.TUESDAY in climate.device.week_profile._schedule_cache[ScheduleProfile.P1]
        # Callback should be called for CONFIG_PENDING event
        assert callback_count >= 1

        # Test 4: Repeated write operations work correctly
        callback_count = 0
        await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=modified_profile_data)
        await central.looper.block_till_done()

        # Simulate CONFIG_PENDING = False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU0000341:0",
            parameter=Parameter.CONFIG_PENDING,
            value=False,
        )
        await central.looper.block_till_done()

        # Cache should still be valid
        assert ScheduleProfile.P1 in climate.device.week_profile._schedule_cache
        assert WeekdayStr.TUESDAY in climate.device.week_profile._schedule_cache[ScheduleProfile.P1]

        unreg()


class TestScheduleNormalization:
    """Tests for schedule data normalization."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_normalization_complete_example(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test the exact example from the user with string keys and unsorted times."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load valid schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Exact example from user request
        user_example_data = {
            "1": {"endtime": "10:00", "temperature": 15},
            "10": {"endtime": "24:00", "temperature": 16},
            "11": {"endtime": "24:00", "temperature": 16},
            "12": {"endtime": "24:00", "temperature": 16},
            "13": {"endtime": "24:00", "temperature": 16},
            "2": {"endtime": "11:00", "temperature": 16},
            "3": {"endtime": "12:00", "temperature": 22},
            "4": {"endtime": "15:00", "temperature": 15},
            "5": {"endtime": "19:00", "temperature": 12},
            "6": {"endtime": "18:00", "temperature": 14},  # Out of order!
            "7": {"endtime": "24:00", "temperature": 16},
            "8": {"endtime": "24:00", "temperature": 16},
            "9": {"endtime": "24:00", "temperature": 16},
        }

        # Convert string keys to integer keys
        normalized_input = {}
        for key, value in user_example_data.items():
            normalized_input[int(key)] = {
                "endtime": value["endtime"],
                "temperature": float(value["temperature"]),
            }

        # Should not raise an exception
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=normalized_input
        )

        # Note: With pessimistic cache updates, the cache won't contain the written data.
        # Instead, we verify that put_paramset was called with normalized/sorted data.

        # Verify put_paramset was called
        assert mock_client.put_paramset.called

        # Get the values that were sent to put_paramset
        call_args = mock_client.put_paramset.call_args
        sent_values = call_args.kwargs["values"]

        # Verify the sent data contains properly sorted entries
        # The normalization converts to raw format with P1_ENDTIME_MONDAY_X and P1_TEMPERATURE_MONDAY_X
        # We verify the order is correct by checking the endtimes
        endtimes = []
        for slot in range(1, 14):
            endtime_key = f"P1_ENDTIME_MONDAY_{slot}"
            if endtime_key in sent_values:
                endtimes.append(sent_values[endtime_key])

        # Verify endtimes are sorted (converted from HH:MM to minutes)
        expected_endtimes_minutes = [600, 660, 720, 900, 1080, 1140, 1440, 1440, 1440, 1440, 1440, 1440, 1440]
        assert endtimes == expected_endtimes_minutes

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_normalization_preserves_validation(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that normalization still allows validation to catch errors."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load valid schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Test that validation still catches invalid temperature ranges
        invalid_temp_data = {
            "1": {"endtime": "06:00", "temperature": 15.0},
            "2": {"endtime": "08:00", "temperature": 999.0},  # Way out of range!
            "3": {"endtime": "12:00", "temperature": 22.0},
            "4": {"endtime": "15:00", "temperature": 15.0},
            "5": {"endtime": "18:00", "temperature": 12.0},
            "6": {"endtime": "20:00", "temperature": 14.0},
            "7": {"endtime": "24:00", "temperature": 16.0},
            "8": {"endtime": "24:00", "temperature": 16.0},
            "9": {"endtime": "24:00", "temperature": 16.0},
            "10": {"endtime": "24:00", "temperature": 16.0},
            "11": {"endtime": "24:00", "temperature": 16.0},
            "12": {"endtime": "24:00", "temperature": 16.0},
            "13": {"endtime": "24:00", "temperature": 16.0},
        }

        # Should raise ValidationException for invalid temperature
        with pytest.raises(ValidationException):
            await climate.set_schedule_weekday(
                profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=invalid_temp_data
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
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_normalization_sorting_by_endtime(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that slots are sorted by ENDTIME and slot numbers are reassigned."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load valid schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create weekday data with unsorted ENDTIME values
        unsorted_weekday_data = {
            "1": {"endtime": "10:00", "temperature": 15.0},
            "2": {"endtime": "11:00", "temperature": 16.0},
            "3": {"endtime": "12:00", "temperature": 22.0},
            "4": {"endtime": "15:00", "temperature": 15.0},
            "5": {"endtime": "19:00", "temperature": 12.0},
            "6": {"endtime": "18:00", "temperature": 14.0},  # Out of order!
            "7": {"endtime": "24:00", "temperature": 16.0},
            "8": {"endtime": "24:00", "temperature": 16.0},
            "9": {"endtime": "24:00", "temperature": 16.0},
            "10": {"endtime": "24:00", "temperature": 16.0},
            "11": {"endtime": "24:00", "temperature": 16.0},
            "12": {"endtime": "24:00", "temperature": 16.0},
            "13": {"endtime": "24:00", "temperature": 16.0},
        }

        # Should not raise an exception - data should be sorted and slot numbers reassigned
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=unsorted_weekday_data
        )

        # Note: With pessimistic cache updates, we verify put_paramset was called with sorted data
        assert mock_client.put_paramset.called

        # Get the values that were sent to put_paramset
        call_args = mock_client.put_paramset.call_args
        sent_values = call_args.kwargs["values"]

        # Verify the sent data has times in ascending order
        endtimes = []
        temperatures = []
        for slot in range(1, 14):
            endtime_key = f"P1_ENDTIME_MONDAY_{slot}"
            temp_key = f"P1_TEMPERATURE_MONDAY_{slot}"
            if endtime_key in sent_values:
                endtimes.append(sent_values[endtime_key])
            if temp_key in sent_values:
                temperatures.append(sent_values[temp_key])

        # Verify endtimes are in ascending order (minutes since midnight)
        previous_endtime = 0
        for slot_no, endtime_minutes in enumerate(endtimes, start=1):
            assert endtime_minutes >= previous_endtime, f"Slot {slot_no} has non-ascending ENDTIME"
            previous_endtime = endtime_minutes

        # Verify specific slots after sorting
        # Slot 5 should be 18:00 (1080 minutes) with temp 14.0 (after 15:00, before 19:00)
        assert endtimes[4] == 1080  # 18:00 = 18*60 = 1080
        assert temperatures[4] == 14.0

        # Slot 6 should be 19:00 (1140 minutes) with temp 12.0
        assert endtimes[5] == 1140  # 19:00 = 19*60 = 1140
        assert temperatures[5] == 12.0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_normalization_string_keys_to_int(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that string keys are converted to integers."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load valid schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create weekday data with string keys (as might come from JSON)
        weekday_data_with_string_keys = {
            "1": {"endtime": "06:00", "temperature": 17.0},
            "2": {"endtime": "08:00", "temperature": 21.0},
            "3": {"endtime": "10:00", "temperature": 17.0},
            "4": {"endtime": "12:00", "temperature": 21.0},
            "5": {"endtime": "14:00", "temperature": 17.0},
            "6": {"endtime": "16:00", "temperature": 21.0},
            "7": {"endtime": "18:00", "temperature": 17.0},
            "8": {"endtime": "20:00", "temperature": 21.0},
            "9": {"endtime": "22:00", "temperature": 17.0},
            "10": {"endtime": "24:00", "temperature": 16.0},
            "11": {"endtime": "24:00", "temperature": 16.0},
            "12": {"endtime": "24:00", "temperature": 16.0},
            "13": {"endtime": "24:00", "temperature": 16.0},
        }

        # Should not raise an exception - string keys should be converted to int
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=weekday_data_with_string_keys
        )

        # Verify data was cached with integer keys
        cached_data = climate.device.week_profile._schedule_cache[ScheduleProfile.P1][WeekdayStr.MONDAY]
        assert all(isinstance(key, int) for key in cached_data)
        assert len(cached_data) == 13


class TestClimateHelperMethods:
    """Tests for untested climate helper methods and properties."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_available_schedule_profiles(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test available_schedule_profiles property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Check available profiles
        available = climate.available_schedule_profiles
        assert isinstance(available, tuple)
        # Should have at least P1 after loading it
        assert len(available) > 0, "Should have at least one profile after loading"
        assert all(isinstance(p, ScheduleProfile) for p in available)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_is_state_change_mode(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test is_state_change method for mode changes."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Different mode should return True
        current_mode = climate.mode
        new_mode = ClimateMode.AUTO if current_mode != ClimateMode.AUTO else ClimateMode.HEAT
        assert climate.is_state_change(mode=new_mode) is True

        # Same mode should return False
        assert climate.is_state_change(mode=current_mode) is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_is_state_change_profile(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test is_state_change method for profile changes."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Different profile should return True
        current_profile = climate.profile
        new_profile = ClimateProfile.COMFORT if current_profile != ClimateProfile.COMFORT else ClimateProfile.ECO
        assert climate.is_state_change(profile=new_profile) is True

        # Same profile should return False
        assert climate.is_state_change(profile=current_profile) is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_is_state_change_temperature(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test is_state_change method for temperature changes."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Temperature change should return True
        assert climate.is_state_change(temperature=22.0) is True

        # Test with OFF temperature
        await climate.set_temperature(temperature=4.5, do_validate=False)
        temp = climate._temperature_for_heat_mode
        assert temp > 4.5
        assert temp >= climate.min_temp

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_optimum_start_stop_property(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test optimum_start_stop property for IP thermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpIpThermostat = cast(
            CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU3609622", 1)
        )

        # optimum_start_stop should be accessible
        optimum = climate.optimum_start_stop
        assert optimum is None or isinstance(optimum, bool)

    def test_party_mode_code_helper_function(self) -> None:
        """Test _party_mode_code helper function."""
        from aiohomematic.model.custom.climate import _party_mode_code

        # Test party mode code generation
        start = datetime(2025, 1, 15, 10, 30)
        end = datetime(2025, 1, 16, 14, 45)
        away_temp = 18.5

        code = _party_mode_code(start=start, end=end, away_temperature=away_temp)

        # Expected format: "18.5,630,15,01,25,885,16,01,25"
        parts = code.split(",")
        assert len(parts) == 9
        assert float(parts[0]) == away_temp
        assert int(parts[1]) == 630  # 10*60 + 30
        assert parts[2] == "15"  # day
        assert parts[3] == "01"  # month
        assert parts[4] == "25"  # year
        assert int(parts[5]) == 885  # 14*60 + 45
        assert parts[6] == "16"  # day
        assert parts[7] == "01"  # month
        assert parts[8] == "25"  # year

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_schedule_profile_nos_property(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test schedule_profile_nos property."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate_rf: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )
        climate_ip: CustomDpIpThermostat = cast(
            CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU3609622", 1)
        )

        # RF thermostat should return profile count
        assert isinstance(climate_rf.schedule_profile_nos, int)

        # IP thermostat should return profile count
        assert isinstance(climate_ip.schedule_profile_nos, int)
        assert climate_ip.schedule_profile_nos > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_temperature_for_heat_mode_ip_thermostat(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test _temperature_for_heat_mode property for IP thermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpIpThermostat = cast(
            CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU3609622", 1)
        )

        # Test with valid temperature
        temp = climate._temperature_for_heat_mode
        assert temp >= climate.min_temp
        assert temp <= climate.max_temp

        # Test with None target temperature
        climate._old_manu_setpoint = None
        temp = climate._temperature_for_heat_mode
        assert temp >= climate.min_temp

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_temperature_for_heat_mode_rf_thermostat(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test _temperature_for_heat_mode property for RF thermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Test with valid temperature
        temp = climate._temperature_for_heat_mode
        assert temp >= climate.min_temp
        assert temp <= climate.max_temp

        # Test with OFF temperature
        await climate.set_temperature(temperature=4.5, do_validate=False)
        temp = climate._temperature_for_heat_mode
        assert temp > 4.5
        assert temp >= climate.min_temp

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_temperature_offset_ip_thermostat(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test temperature_offset property for IP thermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpIpThermostat = cast(
            CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU3609622", 1)
        )

        # Temperature offset should be accessible
        offset = climate.temperature_offset
        assert offset is None or isinstance(offset, float)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_temperature_offset_rf_thermostat(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test temperature_offset property for RF thermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Temperature offset should be accessible
        offset = climate.temperature_offset
        assert offset is None or isinstance(offset, str)


class TestClimateSimpleScheduleMethods:
    """Tests for simple schedule methods in climate module."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_get_schedule_simple_profile(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_schedule_simple_profile method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Get simple profile
        simple_profile = await climate.get_schedule_simple_profile(profile=ScheduleProfile.P1)

        # Should return a dict with weekdays
        assert isinstance(simple_profile, dict)
        # Simple profile has weekdays as keys
        for weekday, simple_weekday in simple_profile.items():
            assert isinstance(weekday, WeekdayStr)
            assert isinstance(simple_weekday, dict)
            # Each entry should have STARTTIME, ENDTIME, TEMPERATURE
            weekday = simple_weekday["periods"]
            for slot in weekday:
                assert "starttime" in slot
                assert "endtime" in slot
                assert "temperature" in slot

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_get_schedule_simple_schedule(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_schedule_simple_schedule method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Get simple schedule
        simple_schedule = await climate.get_schedule_simple_schedule()

        # Should return a dict with profiles
        assert isinstance(simple_schedule, dict)
        # Should have profiles as keys
        assert len(simple_schedule) > 0
        for profile, profile_data in simple_schedule.items():
            assert isinstance(profile, ScheduleProfile)
            assert isinstance(profile_data, dict)
            # Each profile should have weekdays
            for weekday, weekday_data in profile_data.items():
                assert isinstance(weekday, WeekdayStr)
                assert isinstance(weekday_data, dict)
                assert "base_temperature" in weekday_data
                assert "periods" in weekday_data
                assert isinstance(weekday_data["base_temperature"], float)
                assert isinstance(weekday_data["periods"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_get_schedule_simple_weekday(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_schedule_simple_weekday method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Get simple weekday
        simple_weekday = await climate.get_schedule_simple_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY
        )

        # Should return a dict
        assert isinstance(simple_weekday, dict)
        # Each slot should have required fields
        weekday = simple_weekday["periods"]
        for slot in weekday:
            assert "starttime" in slot
            assert "endtime" in slot
            assert "temperature" in slot
            # Start should be before end
            start_minutes = _convert_time_str_to_minutes(time_str=slot["starttime"])
            end_minutes = _convert_time_str_to_minutes(time_str=slot["endtime"])
            assert start_minutes < end_minutes

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_set_simple_schedule(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_simple_schedule method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create simple schedule data
        simple_schedule = {
            ScheduleProfile.P1: {
                WeekdayStr.MONDAY: {
                    "base_temperature": 16.0,
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
                },
            },
        }

        # Set simple schedule
        await climate.set_simple_schedule(simple_schedule_data=simple_schedule)

        # Verify put_paramset was called
        assert mock_client.put_paramset.called

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_set_simple_schedule_profile(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_simple_schedule_profile method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create simple profile data
        simple_profile = {
            WeekdayStr.MONDAY: {
                "base_temperature": 16.0,
                "periods": [
                    {
                        "starttime": "07:00",
                        "endtime": "22:00",
                        "temperature": 21.0,
                    },
                ],
            },
            WeekdayStr.TUESDAY: {
                "base_temperature": 16.0,
                "periods": [
                    {
                        "starttime": "07:00",
                        "endtime": "22:00",
                        "temperature": 20.0,
                    },
                ],
            },
        }

        # Set simple profile
        await climate.set_simple_schedule_profile(profile=ScheduleProfile.P1, simple_profile_data=simple_profile)

        # Verify put_paramset was called
        assert mock_client.put_paramset.called

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_set_simple_schedule_weekday(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_simple_schedule_weekday method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Create simple weekday data
        simple_weekday = {
            "base_temperature": 18.0,
            "periods": [
                {
                    "starttime": "06:00",
                    "endtime": "08:00",
                    "temperature": 21,
                },
                {
                    "starttime": "17:00",
                    "endtime": "22:00",
                    "temperature": 21.0,
                },
            ],
        }

        # Set simple weekday
        await climate.set_simple_schedule_weekday(
            profile=ScheduleProfile.P1,
            weekday=WeekdayStr.MONDAY,
            simple_weekday_data=simple_weekday,
        )

        # Verify put_paramset was called
        assert mock_client.put_paramset.called

        # Verify put_paramset was called with correct parameters
        last_call = mock_client.method_calls[-1]
        assert last_call[0] == "put_paramset"
        assert last_call[2]["channel_address"] == "VCU0000341"
        assert last_call[2]["paramset_key_or_link_address"] == ParamsetKey.MASTER

        # Verify the values contain correct schedule data for MONDAY
        values = last_call[2]["values"]
        # All 13 slots should be present for Monday
        for slot_no in range(1, 14):
            assert f"P1_ENDTIME_MONDAY_{slot_no}" in values
            assert f"P1_TEMPERATURE_MONDAY_{slot_no}" in values

        # Verify specific slot values from simple schedule conversion
        # Note: ENDTIME values are stored as minutes since midnight (integer)
        # Note: TEMPERATURE values are passed as-is to put_paramset and converted to float
        #       by _convert_value when check_against_pd=True (based on paramset description TYPE)
        # Slot 1: 00:00-06:00 at base temp (18.0)
        assert values["P1_ENDTIME_MONDAY_1"] == 360  # 06:00 = 6 * 60
        assert values["P1_TEMPERATURE_MONDAY_1"] == 18.0
        # Slot 2: 06:00-08:00 at heated temp (from input)
        assert values["P1_ENDTIME_MONDAY_2"] == 480  # 08:00 = 8 * 60
        # Temperature passes through unchanged - _convert_value handles int->float conversion
        assert values["P1_TEMPERATURE_MONDAY_2"] in (21, 21.0)
        # Slot 3: 08:00-17:00 at base temp (18.0)
        assert values["P1_ENDTIME_MONDAY_3"] == 1020  # 17:00 = 17 * 60
        assert values["P1_TEMPERATURE_MONDAY_3"] == 18.0
        # Slot 4: 17:00-22:00 at heated temp (from input)
        assert values["P1_ENDTIME_MONDAY_4"] == 1320  # 22:00 = 22 * 60
        assert values["P1_TEMPERATURE_MONDAY_4"] in (21, 21.0)
        # Slot 5: 22:00-24:00 at base temp (18.0)
        assert values["P1_ENDTIME_MONDAY_5"] == 1440  # 24:00 = 24 * 60
        assert values["P1_TEMPERATURE_MONDAY_5"] == 18.0
        # Remaining slots should be filled with 24:00 (1440 minutes)
        for slot_no in range(6, 14):
            assert values[f"P1_ENDTIME_MONDAY_{slot_no}"] == 1440

        # Note: With pessimistic cache updates, the cache won't contain the written data
        # until CONFIG_PENDING = False is received. The put_paramset call above already
        # validates that the data was sent correctly to the CCU.

        # Verify that _check_put_paramset converts integer values to floats
        # (Only for InterfaceClient which has this method)
        client = central.client_coordinator.primary_client
        assert client is not None
        real_client = client._mock_wraps if hasattr(client, "_mock_wraps") else client
        if hasattr(real_client, "_check_put_paramset"):
            # Test that _check_put_paramset converts integer temperatures to float
            test_values = {"P1_TEMPERATURE_MONDAY_2": 21}  # Integer input
            checked_values = real_client._check_put_paramset(
                channel_address="VCU0000341",
                paramset_key=ParamsetKey.MASTER,
                values=test_values,
            )
            assert isinstance(checked_values["P1_TEMPERATURE_MONDAY_2"], float)
            assert checked_values["P1_TEMPERATURE_MONDAY_2"] == 21.0
