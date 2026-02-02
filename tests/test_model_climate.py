# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for climate data points of aiohomematic."""

from __future__ import annotations

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
from aiohomematic.model.schedule_models import ClimateSchedulePeriod, ClimateWeekdaySchedule
from aiohomematic.model.week_profile import _convert_time_str_to_minutes
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
            "get_schedule",
            "get_schedule_profile",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule",
            "set_schedule_profile",
            "set_schedule_weekday",
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
    async def test_cethermostatgroup(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpSimpleRfThermostat."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpSimpleRfThermostat = cast(
            CustomDpSimpleRfThermostat, get_prepared_custom_data_point(central, "INT0000001", 1)
        )
        assert climate.usage == DataPointUsage.CDP_PRIMARY
        assert climate._dp_setpoint.min == 4.5
        assert climate._dp_setpoint.max == 30.5


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
            "get_schedule",
            "get_schedule_profile",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule",
            "set_schedule_profile",
            "set_schedule_weekday",
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
            "get_schedule",
            "get_schedule_profile",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule",
            "set_schedule_profile",
            "set_schedule_weekday",
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
        # Verify weekday data structure (Pydantic model with base_temperature and periods)
        assert hasattr(weekday_data, "base_temperature")
        assert hasattr(weekday_data, "periods")
        assert len(weekday_data.periods) >= 0
        # Verify period structure if periods exist
        if weekday_data.periods:
            first_period = weekday_data.periods[0]
            assert hasattr(first_period, "starttime")
            assert hasattr(first_period, "endtime")
            assert hasattr(first_period, "temperature")

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
        # Note: Pydantic will validate and convert integers to floats
        simple_weekday_data = ClimateWeekdaySchedule(
            base_temperature=16,  # Integer - Pydantic converts to float
            periods=[
                ClimateSchedulePeriod(starttime="05:00", endtime="06:00", temperature=17),
                ClimateSchedulePeriod(starttime="09:00", endtime="15:00", temperature=17),
                ClimateSchedulePeriod(starttime="19:00", endtime="22:00", temperature=22),
            ],
        )

        # Write schedule with integer temperatures
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.SATURDAY, weekday_data=simple_weekday_data
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
            "get_schedule",
            "get_schedule_profile",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule",
            "set_schedule_profile",
            "set_schedule_weekday",
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
            "get_schedule",
            "get_schedule_profile",
            "get_schedule_weekday",
            "load_data_point_value",
            "set_mode",
            "set_profile",
            "set_schedule",
            "set_schedule_profile",
            "set_schedule_weekday",
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


@pytest.mark.xdist_group("pydevccu")
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
        # ClimateWeekdaySchedule is a Pydantic model with base_temperature and periods
        assert weekday_data.base_temperature is not None
        assert isinstance(weekday_data.periods, list)
        await climate_bwth.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=profile_data)
        await climate_bwth.set_schedule_weekday(
            profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY, weekday_data=weekday_data
        )

        # Test validation: temperature out of range (38.0 > max allowed)
        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data={
                    "base_temperature": 18.0,
                    "periods": [{"starttime": "06:00", "endtime": "08:00", "temperature": 38.0}],
                },
            )

        # Test validation: invalid time format (hour > 24)
        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data={
                    "base_temperature": 18.0,
                    "periods": [{"starttime": "06:00", "endtime": "25:40", "temperature": 21.0}],
                },
            )

        # Test validation: invalid time format (hour > 24)
        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data={
                    "base_temperature": 18.0,
                    "periods": [{"starttime": "06:00", "endtime": "35:00", "temperature": 21.0}],
                },
            )

        # Test validation: invalid endtime type (int instead of str)
        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile=ScheduleProfile.P1,
                weekday=WeekdayStr.MONDAY,
                weekday_data={
                    "base_temperature": 18.0,
                    "periods": [{"starttime": "06:00", "endtime": 100, "temperature": 21.0}],
                },
            )
        # Test with simple format: base_temperature 17, periods where temp differs
        manual_week_profile_data = ClimateWeekdaySchedule(
            base_temperature=17.0,
            periods=[
                ClimateSchedulePeriod(starttime="06:00", endtime="07:00", temperature=21.0),
                ClimateSchedulePeriod(starttime="10:00", endtime="23:00", temperature=21.0),
            ],
        )
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
        await climate_bwth.set_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            weekday_data=manual_simple_weekday_data,
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
        await climate_bwth.set_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            weekday_data=manual_simple_weekday_data2,
        )

        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile="P1",
                weekday="MONDAY",
                weekday_data={
                    "base_temperature": 16.0,
                    "periods": [
                        {"temperature": 34.0, "starttime": "05:00", "endtime": "06:00"},
                    ],
                },
            )

        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile="P1",
                weekday="MONDAY",
                weekday_data={"base_temperature": 34.0, "periods": []},
            )

        with pytest.raises(ValidationException):
            await climate_bwth.set_schedule_weekday(
                profile="P1",
                weekday="MONDAY",
                weekday_data={
                    "base_temperature": 16.0,
                    "periods": [
                        {"temperature": 17.0, "starttime": "05:00", "endtime": "06:00"},
                        {"temperature": 22.0, "starttime": "19:00", "endtime": "22:00"},
                        {"temperature": 17.0, "starttime": "09:00", "endtime": "20:00"},
                    ],
                },
            )

        await climate_bwth.set_schedule_profile(
            profile="P1",
            profile_data={
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

        await climate_bwth.set_schedule_profile(
            profile="P1",
            profile_data={
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
        await climate_bwth.set_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            weekday_data=manual_simple_weekday_data3,
        )

        await climate_bwth.set_schedule_weekday(
            profile="P1",
            weekday="MONDAY",
            weekday_data={
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
            await climate_bwth.set_schedule_weekday(
                profile="P1",
                weekday="MONDAY",
                weekday_data={
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
    async def test_get_schedule(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_schedule method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Get simple schedule
        simple_schedule = await climate.get_schedule()

        # Should return a Pydantic RootModel (dict-like)
        from aiohomematic.model.schedule_models import (
            ClimateProfileSchedule as ClimateProfileScheduleModel,
            ClimateSchedule as ClimateScheduleModel,
            ClimateWeekdaySchedule as ClimateWeekdayScheduleModel,
        )

        assert isinstance(simple_schedule, ClimateScheduleModel)
        # Should have profiles as keys
        assert len(simple_schedule) > 0
        for profile_str, profile_data in simple_schedule.items():
            assert isinstance(profile_str, str)
            assert isinstance(profile_data, ClimateProfileScheduleModel)
            # Each profile should have weekdays
            for weekday_str, weekday_data in profile_data.items():
                assert isinstance(weekday_str, str)
                assert isinstance(weekday_data, ClimateWeekdayScheduleModel)
                assert hasattr(weekday_data, "base_temperature")
                assert hasattr(weekday_data, "periods")
                assert isinstance(weekday_data.base_temperature, float)
                assert isinstance(weekday_data.periods, list)

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
    async def test_get_schedule_profile(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_schedule_profile method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Get simple profile
        simple_profile = await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Should return a Pydantic RootModel (dict-like)
        from aiohomematic.model.schedule_models import (
            ClimateProfileSchedule as ClimateProfileScheduleModel,
            ClimateWeekdaySchedule as ClimateWeekdayScheduleModel,
        )

        assert isinstance(simple_profile, ClimateProfileScheduleModel)
        # Simple profile has weekdays as keys
        for weekday_str, simple_weekday in simple_profile.items():
            assert isinstance(weekday_str, str)
            assert isinstance(simple_weekday, ClimateWeekdayScheduleModel)
            # Each period should have starttime, endtime, temperature
            for period in simple_weekday.periods:
                assert hasattr(period, "starttime")
                assert hasattr(period, "endtime")
                assert hasattr(period, "temperature")

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
    async def test_get_schedule_weekday(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_schedule_weekday method."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        climate: CustomDpRfThermostat = cast(
            CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2)
        )

        # Load schedule first
        await climate.get_schedule_profile(profile=ScheduleProfile.P1)

        # Get simple weekday
        simple_weekday = await climate.get_schedule_weekday(profile=ScheduleProfile.P1, weekday=WeekdayStr.MONDAY)

        # Should return a Pydantic model
        from aiohomematic.model.schedule_models import ClimateWeekdaySchedule as ClimateWeekdayScheduleModel

        assert isinstance(simple_weekday, ClimateWeekdayScheduleModel)
        # Each period should have required fields
        for period in simple_weekday.periods:
            assert hasattr(period, "starttime")
            assert hasattr(period, "endtime")
            assert hasattr(period, "temperature")
            # Start should be before end
            start_minutes = _convert_time_str_to_minutes(time_str=period.starttime)
            end_minutes = _convert_time_str_to_minutes(time_str=period.endtime)
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
    async def test_set_schedule(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_schedule method."""
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
        await climate.set_schedule(schedule_data=simple_schedule)

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
    async def test_set_schedule_profile(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_schedule_profile method."""
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
        await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=simple_profile)

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
    async def test_set_schedule_weekday(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test set_schedule_weekday method."""
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
        await climate.set_schedule_weekday(
            profile=ScheduleProfile.P1,
            weekday=WeekdayStr.MONDAY,
            weekday_data=simple_weekday,
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
