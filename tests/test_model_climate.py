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
from aiohomematic.model.custom.climate import ScheduleProfile, ScheduleSlotType, ScheduleWeekday, _ModeHm, _ModeHmIP
from aiohomematic.model.generic import DpDummy
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
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000054:1", parameter="TEMPERATURE", value=11.0
    )
    assert climate.current_temperature == 11.0

    assert climate.mode == ClimateMode.HEAT
    assert climate.modes == (ClimateMode.HEAT,)
    assert climate.profile == ClimateProfile.NONE
    assert climate.profiles == (ClimateProfile.NONE,)
    assert climate.activity is None
    await central.data_point_event(
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
async def test_cerfthermostat(
    central_client_factory_with_homegear_client,
) -> None:
    """Test CustomDpRfThermostat."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000050", 4))
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="VALVE_STATE", value=10
    )
    assert climate.activity == ClimateActivity.HEAT
    await central.data_point_event(
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
    await central.data_point_event(
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
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="CONTROL_MODE", value=0
    )
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000050:4", parameter="CONTROL_MODE", value=3
    )
    assert climate.profile == ClimateProfile.BOOST
    await central.data_point_event(
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

    await central.data_point_event(
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
    central_client_factory_with_homegear_client,
) -> None:
    """Test CustomDpRfThermostat."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))
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
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU0000341:2",
        parameter="CONTROL_MODE",
        value=_ModeHmIP.MANU.value,
    )
    assert climate.mode == ClimateMode.HEAT

    await climate.set_temperature(temperature=13.0)
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU0000341:2",
        parameter="CONTROL_MODE",
        value=_ModeHmIP.AUTO.value,
    )
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU0000341:2",
        parameter="CONTROL_MODE",
        value=_ModeHmIP.MANU.value,
    )
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU0000341:2",
        parameter="CONTROL_MODE",
        value=_ModeHmIP.AUTO.value,
    )
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU0000341:2", parameter="CONTROL_MODE", value=3
    )
    assert climate.profile == ClimateProfile.BOOST
    await central.data_point_event(
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

    await central.data_point_event(
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
async def test_ceipthermostat_bwth(
    central_client_factory_with_homegear_client,
) -> None:
    """Test CustomDpIpThermostat."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpIpThermostat = cast(CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU1769958", 1))
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
    assert climate.max_temp == 30.0
    assert climate.supports_profiles is True
    assert climate.target_temperature_step == 0.5
    assert climate.activity == ClimateActivity.IDLE
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU1769958:9", parameter="STATE", value=1
    )
    assert climate.activity == ClimateActivity.HEAT
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU1769958:9", parameter="STATE", value=0
    )
    assert climate.activity == ClimateActivity.IDLE
    assert climate._old_manu_setpoint is None
    assert climate.current_humidity is None
    await central.data_point_event(
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
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="SET_POINT_TEMPERATURE", value=19.5
    )
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU1769958:1",
        parameter="SET_POINT_MODE",
        value=_ModeHmIP.MANU.value,
    )
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
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU1769958:1",
        parameter="SET_POINT_MODE",
        value=_ModeHmIP.AUTO.value,
    )
    await central.data_point_event(
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
        values={"BOOST_MODE": False, "CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": climate._temperature_for_heat_mode},
        wait_for_callback=None,
    )

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="SET_POINT_TEMPERATURE", value=19.5
    )
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU1769958:1",
        parameter="SET_POINT_MODE",
        value=_ModeHmIP.AWAY.value,
    )
    assert climate.profile == ClimateProfile.AWAY

    await central.data_point_event(
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

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="BOOST_MODE", value=1
    )
    call_count = len(mock_client.method_calls)
    await climate.set_profile(profile=ClimateProfile.BOOST)
    assert call_count == len(mock_client.method_calls)

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU1769958:1", parameter="SET_POINT_TEMPERATURE", value=12.0
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
    central_client_factory_with_homegear_client,
) -> None:
    """Test CustomDpIpThermostat."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpIpThermostat = cast(CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU4105035", 8))
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
    assert climate.max_temp == 30.0
    assert climate.supports_profiles is True
    assert climate.target_temperature_step == 0.5
    assert climate.activity == ClimateActivity.IDLE
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU4105035:3", parameter="STATE", value=1
    )
    assert climate.activity == ClimateActivity.HEAT
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU4105035:3", parameter="STATE", value=0
    )
    assert climate.activity == ClimateActivity.IDLE
    assert climate._old_manu_setpoint is None
    assert climate.current_humidity is None
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="HUMIDITY", value=75
    )
    assert climate.current_humidity == 75

    assert climate.target_temperature is None
    await climate.set_temperature(temperature=12.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU4105035:8",
        paramset_key=ParamsetKey.VALUES,
        parameter="SET_POINT_TEMPERATURE",
        value=12.0,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert climate.target_temperature == 12.0

    assert climate.current_temperature is None
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="ACTUAL_TEMPERATURE", value=11.0
    )
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="SET_POINT_TEMPERATURE", value=19.5
    )
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU4105035:8",
        parameter="SET_POINT_MODE",
        value=_ModeHmIP.MANU.value,
    )
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
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU4105035:8",
        parameter="SET_POINT_MODE",
        value=_ModeHmIP.AUTO.value,
    )
    await central.data_point_event(
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
        values={"BOOST_MODE": False, "CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": climate._temperature_for_heat_mode},
        wait_for_callback=None,
    )

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="SET_POINT_TEMPERATURE", value=19.5
    )
    await central.data_point_event(
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
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU4105035:8",
        parameter="SET_POINT_MODE",
        value=_ModeHmIP.AWAY.value,
    )
    assert climate.profile == ClimateProfile.AWAY

    await central.data_point_event(
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

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="BOOST_MODE", value=1
    )
    call_count = len(mock_client.method_calls)
    await climate.set_profile(profile=ClimateProfile.BOOST)
    assert call_count == len(mock_client.method_calls)

    await central.data_point_event(
        interface_id=const.INTERFACE_ID, channel_address="VCU4105035:8", parameter="SET_POINT_TEMPERATURE", value=12.0
    )
    call_count = len(mock_client.method_calls)
    await climate.set_temperature(temperature=12.0)
    assert call_count + 1 == len(mock_client.method_calls)

    await climate.set_mode(mode=ClimateMode.AUTO)
    call_count = len(mock_client.method_calls)
    await climate.set_mode(mode=ClimateMode.AUTO)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_climate_ip_with_pydevccu(central_unit_pydevccu_mini) -> None:
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
    profile_data = await climate_bwth.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)
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

    # After normalization, "1:40" is valid and will be sorted correctly
    # Test with an actually invalid time format
    copy_weekday_data2 = deepcopy(weekday_data)
    copy_weekday_data2[4][ScheduleSlotType.ENDTIME] = "25:40"  # Invalid: hour > 24
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
    climate: CustomDpIpThermostat = cast(CustomDpIpThermostat, get_prepared_custom_data_point(central, "VCU1769958", 1))

    # Ensure default mode is AUTO and not OFF
    assert climate.mode in (ClimateMode.AUTO, ClimateMode.HEAT)

    # Force own LEVEL/STATE to be dummy so fallback path is used
    climate._dp_state = DpDummy(channel=climate._channel, param_field=Field.STATE)
    climate._dp_level = DpDummy(channel=climate._channel, param_field=Field.LEVEL)

    # Point link peer to channel 9 which exposes a usable STATE
    device = central.get_device(address="VCU1769958")
    peer_address = f"{device.address}:9"
    peer_channel = central.get_channel(channel_address=peer_address)
    peer_channel._link_target_categories = (DataPointCategory.CLIMATE,)
    climate._channel._link_peer_addresses = (peer_address,)  # type: ignore[attr-defined]
    # Emit peer-changed so the thermostat refreshes its peer DP references
    climate._channel.emit_link_peer_changed_event()

    assert climate.activity == ClimateActivity.IDLE

    # Set peer STATE to ON → activity should be HEAT
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address=peer_address,
        parameter=Parameter.STATE,
        value=1,
    )
    assert climate.activity == ClimateActivity.HEAT

    # Set peer STATE to OFF → activity should be IDLE (unless target temp forces OFF)
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address=peer_address,
        parameter=Parameter.STATE,
        value=0,
    )
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
async def test_schedule_cache_and_reload_on_config_pending(
    central_client_factory_with_homegear_client,
) -> None:
    """Test schedule caching and reloading after CONFIG_PENDING event."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Initially schedule cache should not be empty
    assert climate._schedule_cache

    climate._schedule_cache = {}

    assert climate._schedule_cache == {}

    # Register a callback to track schedule changes
    callback_called = False
    callback_args = None

    def schedule_changed_callback(**kwargs):
        nonlocal callback_called, callback_args
        callback_called = True
        callback_args = kwargs

    unreg = climate.register_data_point_updated_callback(cb=schedule_changed_callback, custom_id="test_schedule_change")

    # Get a schedule profile to populate the cache
    schedule = await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)
    assert schedule is not None
    assert len(schedule) > 0

    # reset callback_called
    callback_called = False

    # Simulate CONFIG_PENDING event (True then False to trigger reload)
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU0000341:0",
        parameter=Parameter.CONFIG_PENDING,
        value=True,
    )

    # Schedule should not have changed yet
    assert callback_called is False

    # Now simulate CONFIG_PENDING = False (should trigger reload and cache schedules)
    await central.data_point_event(
        interface_id=const.INTERFACE_ID,
        channel_address="VCU0000341:0",
        parameter=Parameter.CONFIG_PENDING,
        value=False,
    )

    # Give async tasks time to complete
    import asyncio

    await asyncio.sleep(0.1)

    # Cache should be populated after CONFIG_PENDING reload
    assert climate._schedule_cache != {}, "Schedule cache should be populated after CONFIG_PENDING reload"

    # The callback may or may not have been called depending on whether schedules changed
    # but the cache should definitely be populated
    # Verify that the cache contains schedule data
    assert len(climate._schedule_cache) > 0, "Schedule cache should contain profile data"

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
async def test_schedule_cache_read_operations(
    central_client_factory_with_homegear_client,
) -> None:
    """Test that schedule cache read operations work correctly."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Clear the cache to start fresh
    climate._schedule_cache = {}
    assert climate._schedule_cache == {}

    # Test 1: get_schedule_profile with do_load=True should fetch from API and cache
    # Note: reload_and_cache_schedules() loads ALL available profiles, not just the requested one
    profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)
    assert profile_data is not None
    assert len(profile_data) > 0
    assert ScheduleProfile.P1 in climate._schedule_cache
    assert climate._schedule_cache[ScheduleProfile.P1] == profile_data
    # Multiple profiles should be cached after loading
    assert len(climate._schedule_cache) > 0

    # Count API calls
    initial_call_count = len(mock_client.method_calls)

    # Test 2: get_schedule_profile without do_load should return from cache without API call
    cached_profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=False)
    assert cached_profile_data == profile_data
    assert len(mock_client.method_calls) == initial_call_count  # No new API calls

    # Test 3: get_schedule_profile_weekday should return from cache
    weekday_data = await climate.get_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, do_load=False
    )
    assert weekday_data is not None
    assert len(weekday_data) > 0
    assert weekday_data == profile_data[ScheduleWeekday.MONDAY]
    assert len(mock_client.method_calls) == initial_call_count  # No new API calls

    # Test 4: get_schedule_profile_weekday with do_load=True should fetch from API
    weekday_data_reloaded = await climate.get_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, do_load=True
    )
    assert weekday_data_reloaded == weekday_data
    assert len(mock_client.method_calls) > initial_call_count  # New API call made

    # Test 5: get_schedule_profile for non-cached profile should return empty dict
    # Note: After loading P1, other profiles may also be cached, so we check for a definitely non-existent one
    # First check what's in cache
    cached_profiles = list(climate._schedule_cache.keys())
    # Get a profile that's not in the cache
    non_cached_profile = None
    for test_profile in [ScheduleProfile.P6, ScheduleProfile.P5, ScheduleProfile.P4]:
        if test_profile not in cached_profiles:
            non_cached_profile = test_profile
            break

    if non_cached_profile:
        empty_profile = await climate.get_schedule_profile(profile=non_cached_profile, do_load=False)
        assert empty_profile == {}
    else:
        # If all profiles are cached (which can happen), just verify that accessing cache doesn't cause errors
        for profile in cached_profiles:
            assert await climate.get_schedule_profile(profile=profile, do_load=False) != {}


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
    central_client_factory_with_homegear_client,
) -> None:
    """Test that schedule cache write operations work correctly."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Load initial schedule to cache
    initial_profile_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)
    assert len(initial_profile_data) > 0

    # Register callback to track cache updates
    callback_count = 0

    def cache_update_callback(**kwargs):
        nonlocal callback_count
        callback_count += 1

    unreg = climate.register_data_point_updated_callback(cb=cache_update_callback, custom_id="test_cache_update")

    # Test 1: set_schedule_profile_weekday should update cache
    from copy import deepcopy

    modified_weekday_data = deepcopy(initial_profile_data[ScheduleWeekday.MONDAY])
    # Modify temperature in slot 1
    modified_weekday_data[1][ScheduleSlotType.TEMPERATURE] = 20.0

    callback_count = 0
    await climate.set_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, weekday_data=modified_weekday_data
    )

    # Verify cache was updated
    assert climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY] == modified_weekday_data
    assert climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY][1][ScheduleSlotType.TEMPERATURE] == 20.0
    # Callback should be called once for the change
    assert callback_count == 1

    # Test 2: set_schedule_profile_weekday with same data should not update cache or call callback
    callback_count = 0
    await climate.set_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, weekday_data=modified_weekday_data
    )
    # Callback should not be called since data didn't change
    assert callback_count == 0

    # Test 3: set_schedule_profile should update entire profile in cache
    modified_profile_data = deepcopy(initial_profile_data)
    modified_profile_data[ScheduleWeekday.TUESDAY][2][ScheduleSlotType.TEMPERATURE] = 22.0

    callback_count = 0
    await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=modified_profile_data)

    # Verify cache was updated
    assert climate._schedule_cache[ScheduleProfile.P1] == modified_profile_data
    assert climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.TUESDAY][2][ScheduleSlotType.TEMPERATURE] == 22.0
    # Callback should be called once
    assert callback_count == 1

    # Test 4: set_schedule_profile with same data should not trigger callback
    callback_count = 0
    await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=modified_profile_data)
    # Callback should not be called since data didn't change
    assert callback_count == 0

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
async def test_schedule_cache_consistency(
    central_client_factory_with_homegear_client,
) -> None:
    """Test that schedule cache remains consistent across multiple operations."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Load initial schedules
    profile1_data = await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)
    assert len(profile1_data) > 0
    assert ScheduleProfile.P1 in climate._schedule_cache

    # Test 1: Writing to one profile shouldn't affect other profiles
    from copy import deepcopy

    modified_p1_data = deepcopy(profile1_data)
    modified_p1_data[ScheduleWeekday.MONDAY][1][ScheduleSlotType.TEMPERATURE] = 25.0
    await climate.set_schedule_profile(profile=ScheduleProfile.P1, profile_data=modified_p1_data)

    # Verify P1 was updated
    assert climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY][1][ScheduleSlotType.TEMPERATURE] == 25.0

    # Test 2: Writing to individual weekday should only affect that weekday
    modified_tuesday_data = deepcopy(profile1_data[ScheduleWeekday.TUESDAY])
    modified_tuesday_data[2][ScheduleSlotType.TEMPERATURE] = 23.0
    await climate.set_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.TUESDAY, weekday_data=modified_tuesday_data
    )

    # Verify Tuesday was updated
    assert climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.TUESDAY][2][ScheduleSlotType.TEMPERATURE] == 23.0
    # Verify Monday still has the previous change
    assert climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY][1][ScheduleSlotType.TEMPERATURE] == 25.0
    # Verify other weekdays weren't affected
    assert (
        climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.WEDNESDAY]
        == profile1_data[ScheduleWeekday.WEDNESDAY]
    )

    # Test 3: Multiple sequential writes should maintain consistency
    for temp in [18.0, 19.0, 20.0]:
        modified_data = deepcopy(climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.WEDNESDAY])
        modified_data[3][ScheduleSlotType.TEMPERATURE] = temp
        await climate.set_schedule_profile_weekday(
            profile=ScheduleProfile.P1, weekday=ScheduleWeekday.WEDNESDAY, weekday_data=modified_data
        )
        # Verify the last write is reflected
        assert (
            climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.WEDNESDAY][3][ScheduleSlotType.TEMPERATURE]
            == temp
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
async def test_schedule_cache_reload_and_cache_schedules(
    central_client_factory_with_homegear_client,
) -> None:
    """Test reload_and_cache_schedules method behavior."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Register callback to track schedule reload
    reload_callback_count = 0

    def reload_callback(**kwargs):
        nonlocal reload_callback_count
        reload_callback_count += 1

    unreg = climate.register_data_point_updated_callback(cb=reload_callback, custom_id="test_reload")

    # Test 1: Initial load should populate cache
    climate._schedule_cache = {}
    assert climate._schedule_cache == {}

    await climate.reload_and_cache_schedules()

    # Verify cache was populated
    assert len(climate._schedule_cache) > 0
    assert reload_callback_count == 1

    # Test 2: Reload with same data should not trigger callback
    reload_callback_count = 0
    initial_cache = deepcopy(climate._schedule_cache)

    await climate.reload_and_cache_schedules()

    # Cache should still be populated
    assert len(climate._schedule_cache) > 0
    # Callback should not be called if data didn't change
    # (Note: This depends on whether the mock returns the same data)

    # Test 3: Manual cache modification followed by reload should restore correct data
    climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY][1][ScheduleSlotType.TEMPERATURE] = 99.0
    assert climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY][1][ScheduleSlotType.TEMPERATURE] == 99.0

    reload_callback_count = 0
    await climate.reload_and_cache_schedules()

    # After reload, the incorrect manual change should be overwritten
    # The cache should reflect the actual data from the device
    assert (
        climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY][1][ScheduleSlotType.TEMPERATURE]
        == initial_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY][1][ScheduleSlotType.TEMPERATURE]
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
async def test_schedule_cache_available_profiles(
    central_client_factory_with_homegear_client,
) -> None:
    """Test that available_schedule_profiles returns correct profiles from cache."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Test 1: Empty cache should return empty tuple
    climate._schedule_cache = {}
    assert climate.available_schedule_profiles == ()

    # Test 2: After loading profiles, available_schedule_profiles should reflect cache
    await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)
    assert ScheduleProfile.P1 in climate.available_schedule_profiles

    # Test 3: After loading multiple profiles, all should be available
    await climate.get_schedule_profile(profile=ScheduleProfile.P2, do_load=True)
    available_profiles = climate.available_schedule_profiles
    assert ScheduleProfile.P1 in available_profiles
    assert ScheduleProfile.P2 in available_profiles
    assert len(available_profiles) >= 2

    # Test 4: schedule property should return the entire cache
    full_schedule = climate.schedule
    assert full_schedule == climate._schedule_cache
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
async def test_schedule_normalization_string_keys_to_int(
    central_client_factory_with_homegear_client,
) -> None:
    """Test that string keys are converted to integers."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Load valid schedule first
    await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)

    # Create weekday data with string keys (as might come from JSON)
    weekday_data_with_string_keys = {
        "1": {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 17.0},
        "2": {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 21.0},
        "3": {ScheduleSlotType.ENDTIME: "10:00", ScheduleSlotType.TEMPERATURE: 17.0},
        "4": {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 21.0},
        "5": {ScheduleSlotType.ENDTIME: "14:00", ScheduleSlotType.TEMPERATURE: 17.0},
        "6": {ScheduleSlotType.ENDTIME: "16:00", ScheduleSlotType.TEMPERATURE: 21.0},
        "7": {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 17.0},
        "8": {ScheduleSlotType.ENDTIME: "20:00", ScheduleSlotType.TEMPERATURE: 21.0},
        "9": {ScheduleSlotType.ENDTIME: "22:00", ScheduleSlotType.TEMPERATURE: 17.0},
        "10": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "11": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "12": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "13": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
    }

    # Should not raise an exception - string keys should be converted to int
    await climate.set_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, weekday_data=weekday_data_with_string_keys
    )

    # Verify data was cached with integer keys
    cached_data = climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY]
    assert all(isinstance(key, int) for key in cached_data)
    assert len(cached_data) == 13


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
    central_client_factory_with_homegear_client,
) -> None:
    """Test that slots are sorted by ENDTIME and slot numbers are reassigned."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Load valid schedule first
    await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)

    # Create weekday data with unsorted ENDTIME values
    unsorted_weekday_data = {
        "1": {ScheduleSlotType.ENDTIME: "10:00", ScheduleSlotType.TEMPERATURE: 15.0},
        "2": {ScheduleSlotType.ENDTIME: "11:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "3": {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 22.0},
        "4": {ScheduleSlotType.ENDTIME: "15:00", ScheduleSlotType.TEMPERATURE: 15.0},
        "5": {ScheduleSlotType.ENDTIME: "19:00", ScheduleSlotType.TEMPERATURE: 12.0},
        "6": {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 14.0},  # Out of order!
        "7": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "8": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "9": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "10": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "11": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "12": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "13": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
    }

    # Should not raise an exception - data should be sorted and slot numbers reassigned
    await climate.set_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, weekday_data=unsorted_weekday_data
    )

    # Verify data was sorted correctly in cache
    cached_data = climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY]

    # Check that slot numbers are 1-13
    assert list(cached_data.keys()) == list(range(1, 14))

    # Check that times are in ascending order
    previous_endtime_minutes = 0
    for slot_no in range(1, 14):
        endtime_str = cached_data[slot_no][ScheduleSlotType.ENDTIME]
        h, m = endtime_str.split(":")
        endtime_minutes = int(h) * 60 + int(m)
        assert endtime_minutes >= previous_endtime_minutes, f"Slot {slot_no} has non-ascending ENDTIME"
        previous_endtime_minutes = endtime_minutes

    # Verify specific slot contents after sorting
    # Original slot 6 (18:00, 14.0) should now be slot 5 (after 15:00, before 19:00)
    assert cached_data[5][ScheduleSlotType.ENDTIME] == "18:00"
    assert cached_data[5][ScheduleSlotType.TEMPERATURE] == 14.0

    # Original slot 5 (19:00, 12.0) should now be slot 6
    assert cached_data[6][ScheduleSlotType.ENDTIME] == "19:00"
    assert cached_data[6][ScheduleSlotType.TEMPERATURE] == 12.0


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
    central_client_factory_with_homegear_client,
) -> None:
    """Test the exact example from the user with string keys and unsorted times."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Load valid schedule first
    await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)

    # Exact example from user request
    user_example_data = {
        "1": {"ENDTIME": "10:00", "TEMPERATURE": 15},
        "10": {"ENDTIME": "24:00", "TEMPERATURE": 16},
        "11": {"ENDTIME": "24:00", "TEMPERATURE": 16},
        "12": {"ENDTIME": "24:00", "TEMPERATURE": 16},
        "13": {"ENDTIME": "24:00", "TEMPERATURE": 16},
        "2": {"ENDTIME": "11:00", "TEMPERATURE": 16},
        "3": {"ENDTIME": "12:00", "TEMPERATURE": 22},
        "4": {"ENDTIME": "15:00", "TEMPERATURE": 15},
        "5": {"ENDTIME": "19:00", "TEMPERATURE": 12},
        "6": {"ENDTIME": "18:00", "TEMPERATURE": 14},  # Out of order!
        "7": {"ENDTIME": "24:00", "TEMPERATURE": 16},
        "8": {"ENDTIME": "24:00", "TEMPERATURE": 16},
        "9": {"ENDTIME": "24:00", "TEMPERATURE": 16},
    }

    # Convert string slot types to ScheduleSlotType enums
    normalized_input = {}
    for key, value in user_example_data.items():
        normalized_input[key] = {
            ScheduleSlotType.ENDTIME: value["ENDTIME"],
            ScheduleSlotType.TEMPERATURE: float(value["TEMPERATURE"]),
        }

    # Should not raise an exception
    await climate.set_schedule_profile_weekday(
        profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, weekday_data=normalized_input
    )

    # Verify normalization worked correctly
    cached_data = climate._schedule_cache[ScheduleProfile.P1][ScheduleWeekday.MONDAY]

    # All keys should be integers 1-13
    assert list(cached_data.keys()) == list(range(1, 14))

    # Verify sorted order
    expected_order = [
        ("10:00", 15.0),  # Original slot 1
        ("11:00", 16.0),  # Original slot 2
        ("12:00", 22.0),  # Original slot 3
        ("15:00", 15.0),  # Original slot 4
        ("18:00", 14.0),  # Original slot 6 (moved before 19:00)
        ("19:00", 12.0),  # Original slot 5
        ("24:00", 16.0),  # Original slots 7-13
        ("24:00", 16.0),
        ("24:00", 16.0),
        ("24:00", 16.0),
        ("24:00", 16.0),
        ("24:00", 16.0),
        ("24:00", 16.0),
    ]

    for slot_no, (expected_time, expected_temp) in enumerate(expected_order, start=1):
        assert cached_data[slot_no][ScheduleSlotType.ENDTIME] == expected_time
        assert cached_data[slot_no][ScheduleSlotType.TEMPERATURE] == expected_temp


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
    central_client_factory_with_homegear_client,
) -> None:
    """Test that normalization still allows validation to catch errors."""
    central, mock_client, _ = central_client_factory_with_homegear_client
    climate: CustomDpRfThermostat = cast(CustomDpRfThermostat, get_prepared_custom_data_point(central, "VCU0000341", 2))

    # Load valid schedule first
    await climate.get_schedule_profile(profile=ScheduleProfile.P1, do_load=True)

    # Test that validation still catches invalid temperature ranges
    invalid_temp_data = {
        "1": {ScheduleSlotType.ENDTIME: "06:00", ScheduleSlotType.TEMPERATURE: 15.0},
        "2": {ScheduleSlotType.ENDTIME: "08:00", ScheduleSlotType.TEMPERATURE: 999.0},  # Way out of range!
        "3": {ScheduleSlotType.ENDTIME: "12:00", ScheduleSlotType.TEMPERATURE: 22.0},
        "4": {ScheduleSlotType.ENDTIME: "15:00", ScheduleSlotType.TEMPERATURE: 15.0},
        "5": {ScheduleSlotType.ENDTIME: "18:00", ScheduleSlotType.TEMPERATURE: 12.0},
        "6": {ScheduleSlotType.ENDTIME: "20:00", ScheduleSlotType.TEMPERATURE: 14.0},
        "7": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "8": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "9": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "10": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "11": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "12": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
        "13": {ScheduleSlotType.ENDTIME: "24:00", ScheduleSlotType.TEMPERATURE: 16.0},
    }

    # Should raise ValidationException for invalid temperature
    with pytest.raises(ValidationException):
        await climate.set_schedule_profile_weekday(
            profile=ScheduleProfile.P1, weekday=ScheduleWeekday.MONDAY, weekday_data=invalid_temp_data
        )
