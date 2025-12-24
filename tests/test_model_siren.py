# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Tests for siren data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
from aiohomematic.model.custom import CustomDpIpSiren, CustomDpIpSirenSmoke
from aiohomematic.model.custom.siren import _SirenCommand
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU8249617", "VCU2822385"}

# pylint: disable=protected-access


class TestIpSiren:
    """Tests for CustomDpIpSiren data points."""

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
    async def test_ip_siren_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpSiren alarm control and parameter validation."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        siren: CustomDpIpSiren = cast(CustomDpIpSiren, get_prepared_custom_data_point(central, "VCU8249617", 3))
        assert siren.usage == DataPointUsage.CDP_PRIMARY
        assert siren.service_method_names == (
            "load_data_point_value",
            "turn_off",
            "turn_on",
        )

        assert siren.is_on is False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8249617:3", parameter="ACOUSTIC_ALARM_ACTIVE", value=1
        )
        assert siren.is_on is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8249617:3", parameter="ACOUSTIC_ALARM_ACTIVE", value=0
        )
        assert siren.is_on is False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8249617:3", parameter="OPTICAL_ALARM_ACTIVE", value=1
        )
        assert siren.is_on is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU8249617:3", parameter="OPTICAL_ALARM_ACTIVE", value=0
        )
        assert siren.is_on is False

        await siren.turn_on(
            acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
            optical_alarm="BLINKING_ALTERNATELY_REPEATING",
            duration=30,
        )
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "FREQUENCY_RISING_AND_FALLING",
                "OPTICAL_ALARM_SELECTION": "BLINKING_ALTERNATELY_REPEATING",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 30,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await siren.turn_on(
            acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
            optical_alarm="BLINKING_ALTERNATELY_REPEATING",
            duration=30,
        )
        assert mock_client.method_calls[-2] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "FREQUENCY_RISING_AND_FALLING",
                "OPTICAL_ALARM_SELECTION": "BLINKING_ALTERNATELY_REPEATING",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 30,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        from aiohomematic.exceptions import ValidationException

        with pytest.raises(ValidationException):
            await siren.turn_on(
                acoustic_alarm="not_in_list",
                optical_alarm="BLINKING_ALTERNATELY_REPEATING",
                duration=30,
            )

        with pytest.raises(ValidationException):
            await siren.turn_on(
                acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
                optical_alarm="not_in_list",
                duration=30,
            )

        await siren.turn_off()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "DISABLE_ACOUSTIC_SIGNAL",
                "OPTICAL_ALARM_SELECTION": "DISABLE_OPTICAL_SIGNAL",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await siren.turn_off()
        call_count = len(mock_client.method_calls)
        await siren.turn_off()
        assert (call_count + 1) == len(mock_client.method_calls)

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
    async def test_ip_siren_turn_on_kwargs_override_prefilled_values(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test turn_on kwargs override pre-filled data point values."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        siren: CustomDpIpSiren = cast(CustomDpIpSiren, get_prepared_custom_data_point(central, "VCU8249617", 3))

        # Pre-fill data points
        siren._dp_acoustic_alarm_selection.value = "FREQUENCY_FALLING"
        siren._dp_optical_alarm_selection.value = "DOUBLE_FLASHING_REPEATING"

        # Call with kwargs - should override pre-filled values
        await siren.turn_on(
            acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
            optical_alarm="BLINKING_ALTERNATELY_REPEATING",
        )
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "FREQUENCY_RISING_AND_FALLING",
                "OPTICAL_ALARM_SELECTION": "BLINKING_ALTERNATELY_REPEATING",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_ip_siren_turn_on_partial_kwargs_with_prefilled_values(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test turn_on with partial kwargs uses pre-filled values for missing params."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        siren: CustomDpIpSiren = cast(CustomDpIpSiren, get_prepared_custom_data_point(central, "VCU8249617", 3))

        # Pre-fill both data points
        siren._dp_acoustic_alarm_selection.value = "FREQUENCY_FALLING"
        siren._dp_optical_alarm_selection.value = "DOUBLE_FLASHING_REPEATING"

        # Only override acoustic_alarm - optical_alarm should use pre-filled value
        await siren.turn_on(acoustic_alarm="FREQUENCY_RISING_AND_FALLING")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "FREQUENCY_RISING_AND_FALLING",
                "OPTICAL_ALARM_SELECTION": "DOUBLE_FLASHING_REPEATING",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        # Only override optical_alarm - acoustic_alarm should use pre-filled value
        await siren.turn_on(optical_alarm="BLINKING_ALTERNATELY_REPEATING")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "FREQUENCY_FALLING",
                "OPTICAL_ALARM_SELECTION": "BLINKING_ALTERNATELY_REPEATING",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_ip_siren_turn_on_uses_prefilled_dp_values(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test turn_on uses pre-filled data point values when no kwargs provided."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        siren: CustomDpIpSiren = cast(CustomDpIpSiren, get_prepared_custom_data_point(central, "VCU8249617", 3))

        # Pre-fill data points via value setter
        siren._dp_acoustic_alarm_selection.value = "FREQUENCY_FALLING"
        siren._dp_optical_alarm_selection.value = "DOUBLE_FLASHING_REPEATING"

        await siren.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "FREQUENCY_FALLING",
                "OPTICAL_ALARM_SELECTION": "DOUBLE_FLASHING_REPEATING",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_ip_siren_turn_on_with_partial_params(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test turn_on with only some parameters uses defaults for missing ones."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        siren: CustomDpIpSiren = cast(CustomDpIpSiren, get_prepared_custom_data_point(central, "VCU8249617", 3))

        # Only acoustic_alarm provided
        await siren.turn_on(acoustic_alarm="FREQUENCY_RISING_AND_FALLING")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "FREQUENCY_RISING_AND_FALLING",
                "OPTICAL_ALARM_SELECTION": "DISABLE_OPTICAL_SIGNAL",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        # Only optical_alarm provided
        await siren.turn_on(optical_alarm="BLINKING_ALTERNATELY_REPEATING")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "DISABLE_ACOUSTIC_SIGNAL",
                "OPTICAL_ALARM_SELECTION": "BLINKING_ALTERNATELY_REPEATING",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
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
    async def test_ip_siren_turn_on_without_params_uses_defaults(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test turn_on without parameters uses default values."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        siren: CustomDpIpSiren = cast(CustomDpIpSiren, get_prepared_custom_data_point(central, "VCU8249617", 3))

        await siren.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU8249617:3",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "ACOUSTIC_ALARM_SELECTION": "DISABLE_ACOUSTIC_SIGNAL",
                "OPTICAL_ALARM_SELECTION": "DISABLE_OPTICAL_SIGNAL",
                "DURATION_UNIT": "S",
                "DURATION_VALUE": 0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )


class TestIpSirenSmoke:
    """Tests for CustomDpIpSirenSmoke data points."""

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
    async def test_ip_siren_smoke_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpSirenSmoke smoke detector alarm control."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        siren: CustomDpIpSirenSmoke = cast(
            CustomDpIpSirenSmoke, get_prepared_custom_data_point(central, "VCU2822385", 1)
        )
        assert siren.usage == DataPointUsage.CDP_PRIMARY

        assert siren.is_on is False
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU2822385:1",
            parameter="SMOKE_DETECTOR_ALARM_STATUS",
            value=1,
        )
        assert siren.is_on is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU2822385:1",
            parameter="SMOKE_DETECTOR_ALARM_STATUS",
            value=2,
        )
        assert siren.is_on is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU2822385:1",
            parameter="SMOKE_DETECTOR_ALARM_STATUS",
            value=3,
        )
        assert siren.is_on is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID,
            channel_address="VCU2822385:1",
            parameter="SMOKE_DETECTOR_ALARM_STATUS",
            value=0,
        )
        assert siren.is_on is False

        await siren.turn_on()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU2822385:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="SMOKE_DETECTOR_COMMAND",
            value=_SirenCommand.ON,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await siren.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU2822385:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="SMOKE_DETECTOR_COMMAND",
            value=_SirenCommand.OFF,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        call_count = len(mock_client.method_calls)
        await siren.turn_off()
        assert (call_count + 1) == len(mock_client.method_calls)
