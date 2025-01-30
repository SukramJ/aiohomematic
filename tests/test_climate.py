"""Tests for climate data points of hahomematic."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import cast
from unittest.mock import Mock, call

from freezegun import freeze_time
import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
from hahomematic.exceptions import ValidationException
from hahomematic.model.custom import (
    BaseCustomDpClimate,
    ClimateActivity,
    ClimateMode,
    ClimateProfile,
    CustomDpIpThermostat,
    CustomDpRfThermostat,
    CustomDpSimpleRfThermostat,
)
from hahomematic.model.custom.climate import ScheduleProfile, ScheduleSlotType, ScheduleWeekday, _ModeHm, _ModeHmIP

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU1769958": "HmIP-BWTH.json",
    "VCU3609622": "HmIP-eTRV-2.json",
    "INT0000001": "HM-CC-VG-1.json",
    "VCU5778428": "HmIP-HEATING.json",
    "VCU0000054": "HM-CC-TC.json",
    "VCU0000050": "HM-CC-RT-DN.json",
    "VCU0000341": "HM-TC-IT-WM-W-EU.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_cesimplerfthermostat(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CustomDpSimpleRfThermostat."""
    central, mock_client, _ = central_client_factory
    climate: CustomDpSimpleRfThermostat = cast(
        CustomDpSimpleRfThermostat, helper.get_prepared_custom_data_point(central, "VCU0000054", 1)
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
        "get_schedule_profile_weekday",
        "set_mode",
        "set_profile",
        "set_schedule_profile",
        "set_schedule_profile_weekday",
        "set_simple_schedule_profile",
        "set_simple_schedule_profile_weekday",
        "set_temperature",
    )
    assert climate.state_uncertain is False
    assert climate.temperature_unit == "°C"
    assert climate.min_temp == 6.0
    assert climate.max_temp == 30.0
    assert climate.supports_profiles is False
    assert climate.target_temperature_step == 0.5

    assert climate.current_humidity is None
    await central.data_point_event(const.INTERFACE_ID, "VCU0000054:1", "HUMIDITY", 75)
    assert climate.current_humidity == 75

    assert climate.target_temperature is None
    await climate.set_temperature(12.0)
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
    await central.data_point_event(const.INTERFACE_ID, "VCU0000054:1", "TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.mode == ClimateMode.HEAT
    assert climate.modes == (ClimateMode.HEAT,)
    assert climate.profile == ClimateProfile.NONE
    assert climate.profiles == (ClimateProfile.NONE,)
    assert climate.activity is None
    await central.data_point_event(const.INTERFACE_ID, "VCU0000054:1", "TEMPERATURE", 11.0)

    # No new method call, because called methods has no implementation
    await climate.set_mode(ClimateMode.HEAT)
    assert mock_client.method_calls[-1] == last_call
    await climate.set_profile(ClimateProfile.NONE)
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
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_cerfthermostat(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CustomDpRfThermostat."""
    central, mock_client, _ = central_client_factory
    climate: CustomDpRfThermostat = cast(
        CustomDpRfThermostat, helper.get_prepared_custom_data_point(central, "VCU0000050", 4)
    )
    assert climate.usage == DataPointUsage.CDP_PRIMARY
    assert climate.service_method_names == (
        "copy_schedule",
        "copy_schedule_profile",
        "disable_away_mode",
        "enable_away_mode_by_calendar",
        "enable_away_mode_by_duration",
        "get_schedule_profile",
        "get_schedule_profile_weekday",
        "set_mode",
        "set_profile",
        "set_schedule_profile",
        "set_schedule_profile_weekday",
        "set_simple_schedule_profile",
        "set_simple_schedule_profile_weekday",
        "set_temperature",
    )
    assert climate.min_temp == 5.0
    assert climate.max_temp == 30.5
    assert climate.supports_profiles is True
    assert climate.target_temperature_step == 0.5
    assert climate.profile == ClimateProfile.NONE
    assert climate.activity is None
    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "VALVE_STATE", 10)
    assert climate.activity == ClimateActivity.HEAT
    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "VALVE_STATE", 0)
    assert climate.activity == ClimateActivity.IDLE
    assert climate.current_humidity is None
    assert climate.target_temperature is None
    await climate.set_temperature(12.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="SET_TEMPERATURE",
        value=12.0,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert climate.target_temperature == 12.0

    assert climate.current_temperature is None
    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "ACTUAL_TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.mode == ClimateMode.AUTO
    assert climate.modes == (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)
    await climate.set_mode(ClimateMode.HEAT)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="MANU_MODE",
        value=12.0,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", _ModeHmIP.MANU.value)
    assert climate.mode == ClimateMode.HEAT

    await climate.set_mode(ClimateMode.OFF)
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU0000050:4",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={"MANU_MODE": 12.0, "SET_TEMPERATURE": 4.5},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    assert climate.mode == ClimateMode.OFF
    assert climate.activity == ClimateActivity.OFF

    await climate.set_mode(ClimateMode.AUTO)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="AUTO_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 0)
    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "SET_TEMPERATURE", 24.0)
    assert climate.mode == ClimateMode.AUTO

    assert climate.profile == ClimateProfile.NONE
    assert climate.profiles == (
        ClimateProfile.BOOST,
        ClimateProfile.COMFORT,
        ClimateProfile.ECO,
        ClimateProfile.NONE,
    )
    await climate.set_profile(ClimateProfile.BOOST)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="BOOST_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 3)
    assert climate.profile == ClimateProfile.BOOST
    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 2)
    assert climate.profile == ClimateProfile.AWAY
    await climate.set_profile(ClimateProfile.COMFORT)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="COMFORT_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await climate.set_profile(ClimateProfile.ECO)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="LOWERING_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await central.data_point_event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 3)
    call_count = len(mock_client.method_calls)
    await climate.set_profile(ClimateProfile.BOOST)
    assert call_count == len(mock_client.method_calls)

    await climate.set_mode(ClimateMode.AUTO)
    call_count = len(mock_client.method_calls)
    await climate.set_mode(ClimateMode.AUTO)
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
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_cerfthermostat_with_profiles(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CustomDpRfThermostat."""
    central, mock_client, _ = central_client_factory
    climate: CustomDpRfThermostat = cast(
        CustomDpRfThermostat, helper.get_prepared_custom_data_point(central, "VCU0000341", 2)
    )
    assert climate.usage == DataPointUsage.CDP_PRIMARY
    assert climate.service_method_names == (
        "copy_schedule",
        "copy_schedule_profile",
        "disable_away_mode",
        "enable_away_mode_by_calendar",
        "enable_away_mode_by_duration",
        "get_schedule_profile",
        "get_schedule_profile_weekday",
        "set_mode",
        "set_profile",
        "set_schedule_profile",
        "set_schedule_profile_weekday",
        "set_simple_schedule_profile",
        "set_simple_schedule_profile_weekday",
        "set_temperature",
    )
    assert climate.min_temp == 5.0
    assert climate.max_temp == 30.5
    assert climate.supports_profiles is True
    assert climate.target_temperature_step == 0.5
    assert climate.profile == ClimateProfile.NONE
    assert climate.activity is None
    assert climate.current_humidity is None
    assert climate.target_temperature is None
    await climate.set_temperature(12.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000341:2",
        paramset_key=ParamsetKey.VALUES,
        parameter="SET_TEMPERATURE",
        value=12.0,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert climate.target_temperature == 12.0

    assert climate.current_temperature is None
    await central.data_point_event(const.INTERFACE_ID, "VCU0000341:2", "ACTUAL_TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.mode == ClimateMode.AUTO
    assert climate.modes == (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)
    await climate.set_mode(ClimateMode.HEAT)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000341:2",
        paramset_key=ParamsetKey.VALUES,
        parameter="MANU_MODE",
        value=12.0,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU0000341:2", "CONTROL_MODE", _ModeHmIP.MANU.value)
    assert climate.mode == ClimateMode.HEAT

    await climate.set_mode(ClimateMode.OFF)
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU0000341:2",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={"MANU_MODE": 12.0, "SET_TEMPERATURE": 4.5},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    assert climate.mode == ClimateMode.OFF

    await climate.set_mode(ClimateMode.AUTO)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000341:2",
        paramset_key=ParamsetKey.VALUES,
        parameter="AUTO_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU0000341:2", "CONTROL_MODE", 0)
    await central.data_point_event(const.INTERFACE_ID, "VCU0000341:2", "SET_TEMPERATURE", 24.0)
    assert climate.mode == ClimateMode.AUTO

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
    await climate.set_profile(ClimateProfile.BOOST)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000341:2",
        paramset_key=ParamsetKey.VALUES,
        parameter="BOOST_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU0000341:2", "CONTROL_MODE", 3)
    assert climate.profile == ClimateProfile.BOOST
    await central.data_point_event(const.INTERFACE_ID, "VCU0000341:2", "CONTROL_MODE", 2)
    assert climate.profile == ClimateProfile.AWAY
    await climate.set_profile(ClimateProfile.COMFORT)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000341:2",
        paramset_key=ParamsetKey.VALUES,
        parameter="COMFORT_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await climate.set_profile(ClimateProfile.ECO)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000341:2",
        paramset_key=ParamsetKey.VALUES,
        parameter="LOWERING_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await central.data_point_event(const.INTERFACE_ID, "VCU0000341:2", "CONTROL_MODE", 3)
    call_count = len(mock_client.method_calls)
    await climate.set_profile(ClimateProfile.BOOST)
    assert call_count == len(mock_client.method_calls)

    await climate.set_mode(ClimateMode.AUTO)
    call_count = len(mock_client.method_calls)
    await climate.set_mode(ClimateMode.AUTO)
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
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_ceipthermostat(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CustomDpIpThermostat."""
    central, mock_client, _ = central_client_factory
    climate: CustomDpIpThermostat = cast(
        CustomDpIpThermostat, helper.get_prepared_custom_data_point(central, "VCU1769958", 1)
    )
    assert climate.usage == DataPointUsage.CDP_PRIMARY
    assert climate.service_method_names == (
        "copy_schedule",
        "copy_schedule_profile",
        "disable_away_mode",
        "enable_away_mode_by_calendar",
        "enable_away_mode_by_duration",
        "get_schedule_profile",
        "get_schedule_profile_weekday",
        "set_mode",
        "set_profile",
        "set_schedule_profile",
        "set_schedule_profile_weekday",
        "set_simple_schedule_profile",
        "set_simple_schedule_profile_weekday",
        "set_temperature",
    )
    assert climate.min_temp == 5.0
    assert climate.max_temp == 30.5
    assert climate.supports_profiles is True
    assert climate.target_temperature_step == 0.5
    assert climate.activity == ClimateActivity.IDLE
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:9", "STATE", 1)
    assert climate.activity == ClimateActivity.HEAT
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:9", "STATE", 0)
    assert climate.activity == ClimateActivity.IDLE

    assert climate.current_humidity is None
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "HUMIDITY", 75)
    assert climate.current_humidity == 75

    assert climate.target_temperature is None
    await climate.set_temperature(12.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="SET_POINT_TEMPERATURE",
        value=12.0,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert climate.target_temperature == 12.0

    assert climate.current_temperature is None
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "ACTUAL_TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.mode == ClimateMode.AUTO
    assert climate.modes == (ClimateMode.AUTO, ClimateMode.HEAT, ClimateMode.OFF)
    assert climate.profile == ClimateProfile.NONE

    await climate.set_mode(ClimateMode.OFF)
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU1769958:1",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={"CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 4.5},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert climate.mode == ClimateMode.OFF
    assert climate.activity == ClimateActivity.OFF

    await climate.set_mode(ClimateMode.HEAT)
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU1769958:1",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={"CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 5.0},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", _ModeHmIP.MANU.value)
    assert climate.mode == ClimateMode.HEAT

    assert climate.profile == ClimateProfile.NONE
    assert climate.profiles == (
        ClimateProfile.BOOST,
        ClimateProfile.NONE,
    )
    await climate.set_profile(ClimateProfile.BOOST)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="BOOST_MODE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "BOOST_MODE", 1)
    assert climate.profile == ClimateProfile.BOOST

    await climate.set_mode(ClimateMode.AUTO)
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU1769958:1",
        paramset_key_or_link_address=ParamsetKey.VALUES,
        values={"BOOST_MODE": False, "CONTROL_MODE": 0},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", _ModeHmIP.AUTO.value)
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "BOOST_MODE", 1)
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
    await climate.set_profile(ClimateProfile.NONE)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1",
        paramset_key=ParamsetKey.VALUES,
        parameter="BOOST_MODE",
        value=False,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", _ModeHmIP.AWAY.value)
    assert climate.profile == ClimateProfile.AWAY

    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", _ModeHmIP.AUTO.value)
    await climate.set_profile(ClimateProfile.WEEK_PROGRAM_1)
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

    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "BOOST_MODE", 1)
    call_count = len(mock_client.method_calls)
    await climate.set_profile(ClimateProfile.BOOST)
    assert call_count == len(mock_client.method_calls)

    await central.data_point_event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_TEMPERATURE", 12.0)
    call_count = len(mock_client.method_calls)
    await climate.set_temperature(12.0)
    assert call_count == len(mock_client.method_calls)

    await climate.set_mode(ClimateMode.AUTO)
    call_count = len(mock_client.method_calls)
    await climate.set_mode(ClimateMode.AUTO)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_climate_ip_with_pydevccu(central_unit_mini) -> None:
    """Test the central."""
    assert central_unit_mini

    climate_bwth: BaseCustomDpClimate = cast(
        BaseCustomDpClimate,
        central_unit_mini.get_custom_data_point(address="VCU1769958", channel_no=1),
    )
    climate_etrv: BaseCustomDpClimate = cast(
        BaseCustomDpClimate,
        central_unit_mini.get_custom_data_point(address="VCU3609622", channel_no=1),
    )
    assert climate_bwth
    profile_data = await climate_bwth.get_schedule_profile(profile=ScheduleProfile.P1)
    assert len(profile_data) == 7
    weekday_data = await climate_bwth.get_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY
    )
    assert len(weekday_data) == 13
    await climate_bwth.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=profile_data)
    await climate_bwth.set_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, weekday_data=weekday_data
    )
    copy_weekday_data = deepcopy(weekday_data)
    copy_weekday_data[1][ScheduleSlotType.TEMPERATURE] = 38.0
    with pytest.raises(ValidationException):
        await climate_bwth.set_schedule_profile_weekday(
            profile=ScheduleProfile.P1,
            weekday=ScheduleWeekday.MONDAY,
            weekday_data=copy_weekday_data,
        )

    copy_weekday_data2 = deepcopy(weekday_data)
    copy_weekday_data2[4][ScheduleSlotType.ENDTIME] = "1:40"
    with pytest.raises(ValidationException):
        await climate_bwth.set_schedule_profile_weekday(
            profile=ScheduleProfile.P1,
            weekday=ScheduleWeekday.MONDAY,
            weekday_data=copy_weekday_data2,
        )

    copy_weekday_data3 = deepcopy(weekday_data)
    copy_weekday_data3[4][ScheduleSlotType.ENDTIME] = "35:00"
    with pytest.raises(ValidationException):
        await climate_bwth.set_schedule_profile_weekday(
            profile=ScheduleProfile.P1,
            weekday=ScheduleWeekday.MONDAY,
            weekday_data=copy_weekday_data3,
        )

    copy_weekday_data4 = deepcopy(weekday_data)
    copy_weekday_data4[4][ScheduleSlotType.ENDTIME] = 100
    with pytest.raises(ValidationException):
        await climate_bwth.set_schedule_profile_weekday(
            profile=ScheduleProfile.P1,
            weekday=ScheduleWeekday.MONDAY,
            weekday_data=copy_weekday_data4,
        )
    manual_week_profile_data = {
        1: {"TEMPERATURE": 17, "ENDTIME": "06:00"},
        2: {"TEMPERATURE": 21, "ENDTIME": "07:00"},
        3: {"TEMPERATURE": 17, "ENDTIME": "10:00"},
        4: {"TEMPERATURE": 21, "ENDTIME": "23:00"},
        5: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
        6: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
        7: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
        8: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
        9: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
        10: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
        11: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
        12: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
        13: {"TEMPERATURE": 17, "ENDTIME": "24:00"},
    }
    await climate_bwth.set_schedule_profile_weekday(
        profile="P1",
        weekday="MONDAY",
        weekday_data=manual_week_profile_data,
    )

    manual_simple_weekday_list = [
        {"TEMPERATURE": 17.0, "STARTTIME": "05:00", "ENDTIME": "06:00"},
        {"TEMPERATURE": 22.0, "STARTTIME": "19:00", "ENDTIME": "22:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "09:00", "ENDTIME": "15:00"},
    ]
    weekday_data = climate_bwth._validate_and_convert_simple_to_profile_weekday(
        base_temperature=16.0, simple_weekday_list=manual_simple_weekday_list
    )
    assert weekday_data == {
        1: {ScheduleSlotType.ENDTIME: "05:00", ScheduleSlotType.TEMPERATURE: 16.0},
        2: {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 17.0},
        3: {ScheduleSlotType.ENDTIME: "09:00", ScheduleSlotType.TEMPERATURE: 16.0},
        4: {ScheduleSlotType.ENDTIME: "15:00", ScheduleSlotType.TEMPERATURE: 17.0},
        5: {ScheduleSlotType.ENDTIME: "19:00", ScheduleSlotType.TEMPERATURE: 16.0},
        6: {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 22.0},
        7: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        8: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        9: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        10: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        11: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        12: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        13: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
    }
    await climate_bwth.set_simple_schedule_profile_weekday(
        profile="P1",
        weekday="MONDAY",
        base_temperature=16.0,
        simple_weekday_list=manual_simple_weekday_list,
    )

    manual_simple_weekday_list2 = []
    weekday_data2 = climate_bwth._validate_and_convert_simple_to_profile_weekday(
        base_temperature=16.0, simple_weekday_list=manual_simple_weekday_list2
    )
    assert weekday_data2 == {
        1: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        2: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        3: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        4: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        5: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        6: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        7: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        8: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        9: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        10: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        11: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        12: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        13: {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
    }
    await climate_bwth.set_simple_schedule_profile_weekday(
        profile="P1",
        weekday="MONDAY",
        base_temperature=16.0,
        simple_weekday_list=manual_simple_weekday_list2,
    )

    with pytest.raises(ValidationException):
        await climate_bwth.set_simple_schedule_profile_weekday(
            profile="P1",
            weekday="MONDAY",
            base_temperature=16.0,
            simple_weekday_list=[
                {"TEMPERATURE": 34.0, "STARTTIME": "05:00", "ENDTIME": "06:00"},
            ],
        )

    with pytest.raises(ValidationException):
        await climate_bwth.set_simple_schedule_profile_weekday(
            profile="P1",
            weekday="MONDAY",
            base_temperature=34.0,
            simple_weekday_list=[],
        )

    with pytest.raises(ValidationException):
        await climate_bwth.set_simple_schedule_profile_weekday(
            profile="P1",
            weekday="MONDAY",
            base_temperature=16.0,
            simple_weekday_list=[
                {"TEMPERATURE": 17.0, "STARTTIME": "05:00", "ENDTIME": "06:00"},
                {"TEMPERATURE": 22.0, "STARTTIME": "19:00", "ENDTIME": "22:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "09:00", "ENDTIME": "20:00"},
            ],
        )

    await climate_bwth.set_simple_schedule_profile(
        profile="P1",
        base_temperature=16.0,
        simple_profile_data={
            "MONDAY": [
                {"TEMPERATURE": 17.0, "STARTTIME": "05:00", "ENDTIME": "06:00"},
                {"TEMPERATURE": 22.0, "STARTTIME": "19:00", "ENDTIME": "22:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "09:00", "ENDTIME": "15:00"},
            ],
            "TUESDAY": [
                {"TEMPERATURE": 17.0, "STARTTIME": "05:00", "ENDTIME": "06:00"},
                {"TEMPERATURE": 22.0, "STARTTIME": "19:00", "ENDTIME": "22:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "09:00", "ENDTIME": "15:00"},
            ],
        },
    )

    await climate_bwth.set_simple_schedule_profile(
        profile="P1",
        base_temperature=16.0,
        simple_profile_data={
            "MONDAY": [],
        },
    )

    manual_simple_weekday_list3 = [
        {"TEMPERATURE": 17.0, "STARTTIME": "05:00", "ENDTIME": "06:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "06:00", "ENDTIME": "07:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "07:00", "ENDTIME": "08:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "08:00", "ENDTIME": "09:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "09:00", "ENDTIME": "10:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "10:00", "ENDTIME": "11:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "11:00", "ENDTIME": "12:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "12:00", "ENDTIME": "13:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "13:00", "ENDTIME": "14:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "14:00", "ENDTIME": "15:00"},
        {"TEMPERATURE": 17.0, "STARTTIME": "15:00", "ENDTIME": "16:00"},
    ]
    weekday_data3 = climate_bwth._validate_and_convert_simple_to_profile_weekday(
        base_temperature=16.0, simple_weekday_list=manual_simple_weekday_list3
    )
    assert weekday_data3 == {
        1: {"ENDTIME": "05:00", "TEMPERATURE": 16.0},
        2: {"ENDTIME": "06:00", "TEMPERATURE": 17.0},
        3: {"ENDTIME": "07:00", "TEMPERATURE": 17.0},
        4: {"ENDTIME": "08:00", "TEMPERATURE": 17.0},
        5: {"ENDTIME": "09:00", "TEMPERATURE": 17.0},
        6: {"ENDTIME": "10:00", "TEMPERATURE": 17.0},
        7: {"ENDTIME": "11:00", "TEMPERATURE": 17.0},
        8: {"ENDTIME": "12:00", "TEMPERATURE": 17.0},
        9: {"ENDTIME": "13:00", "TEMPERATURE": 17.0},
        10: {"ENDTIME": "14:00", "TEMPERATURE": 17.0},
        11: {"ENDTIME": "15:00", "TEMPERATURE": 17.0},
        12: {"ENDTIME": "16:00", "TEMPERATURE": 17.0},
        13: {"ENDTIME": "24:00", "TEMPERATURE": 16.0},
    }
    await climate_bwth.set_simple_schedule_profile_weekday(
        profile="P1",
        weekday="MONDAY",
        base_temperature=16.0,
        simple_weekday_list=manual_simple_weekday_list3,
    )

    await climate_bwth.set_simple_schedule_profile_weekday(
        profile="P1",
        weekday="MONDAY",
        base_temperature=16.0,
        simple_weekday_list=[
            {"TEMPERATURE": 17.0, "STARTTIME": "05:00", "ENDTIME": "06:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "06:00", "ENDTIME": "07:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "13:00", "ENDTIME": "14:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "14:00", "ENDTIME": "15:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "15:00", "ENDTIME": "16:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "12:00", "ENDTIME": "13:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "07:00", "ENDTIME": "08:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "08:00", "ENDTIME": "09:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "10:00", "ENDTIME": "11:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "11:00", "ENDTIME": "12:00"},
            {"TEMPERATURE": 17.0, "STARTTIME": "09:00", "ENDTIME": "10:00"},
        ],
    )

    # 14 entries
    with pytest.raises(ValidationException):
        await climate_bwth.set_simple_schedule_profile_weekday(
            profile="P1",
            weekday="MONDAY",
            base_temperature=16.0,
            simple_weekday_list=[
                {"TEMPERATURE": 17.0, "STARTTIME": "05:00", "ENDTIME": "06:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "06:00", "ENDTIME": "07:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "07:00", "ENDTIME": "08:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "08:00", "ENDTIME": "09:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "09:00", "ENDTIME": "10:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "10:00", "ENDTIME": "11:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "11:00", "ENDTIME": "12:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "12:00", "ENDTIME": "13:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "13:00", "ENDTIME": "14:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "14:00", "ENDTIME": "15:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "15:00", "ENDTIME": "16:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "16:00", "ENDTIME": "17:00"},
                {"TEMPERATURE": 22.0, "STARTTIME": "17:00", "ENDTIME": "18:00"},
                {"TEMPERATURE": 17.0, "STARTTIME": "18:00", "ENDTIME": "19:00"},
            ],
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
