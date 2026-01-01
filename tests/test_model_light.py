# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for light data points of aiohomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from aiohomematic.const import WAIT_FOR_CALLBACK, DataPointUsage, ParamsetKey
from aiohomematic.model.custom import (
    CustomDpColorDimmer,
    CustomDpColorDimmerEffect,
    CustomDpColorTempDimmer,
    CustomDpDimmer,
    CustomDpIpFixedColorLight,
    CustomDpIpRGBWLight,
)
from aiohomematic.model.custom.light import _NOT_USED, FixedColor, _ColorBehaviour
from aiohomematic.model.custom.mixins import _TimeUnit
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {
    "VCU0000098",
    "VCU0000115",
    "VCU0000122",
    "VCU1399816",
    "VCU6985973",
    "VCU3747418",
    "VCU4704397",
    "VCU5629873",
    "VCU9973336",
}

# pylint: disable=protected-access


class TestCustomDpDimmer:
    """Tests for CustomDpDimmer data points."""

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
    async def test_cedimmer(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpDimmer."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        light: CustomDpDimmer = cast(CustomDpDimmer, get_prepared_custom_data_point(central, "VCU1399816", 4))
        assert light.usage == DataPointUsage.CDP_PRIMARY
        assert light.service_method_names == (
            "load_data_point_value",
            "turn_off",
            "turn_on",
        )
        assert light.color_temp_kelvin is None
        assert light.hs_color is None
        assert light.supports_brightness is True
        assert light.supports_color_temperature is False
        assert light.supports_effects is False
        assert light.supports_hs_color is False
        assert light.supports_transition is True
        assert light.effect is None
        assert light.effects is None

        assert light.brightness == 0
        assert light.brightness_pct == 0
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1399816:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.brightness_pct == 100
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1399816:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 28
        assert light.brightness_pct == 10
        assert light.is_on

        assert light.group_brightness is None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1399816:3", parameter="LEVEL", value=0.4
        )
        assert light.group_brightness == 102

        await light.turn_on(on_time=5.0, ramp_time=6.0)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL": 0.10980392156862745, "RAMP_TIME": 6.0, "ON_TIME": 5.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await light.turn_on(on_time=5.0)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"ON_TIME": 5.0, "LEVEL": 0.10980392156862745},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_off(ramp_time=6.0)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"RAMP_TIME": 6.0, "LEVEL": 0.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 0
        await light.turn_on()
        assert light.brightness == 255
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1399816:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_off()
        light.set_timer_on_time(on_time=0.5)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"ON_TIME": 0.5, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        light.set_timer_on_time(on_time=1.6)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"ON_TIME": 1.6, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on()
        call_count = len(mock_client.method_calls)
        await light.turn_on()
        assert call_count == len(mock_client.method_calls)

        await light.turn_off()
        call_count = len(mock_client.method_calls)
        await light.turn_off()
        assert call_count == len(mock_client.method_calls)


class TestCustomDpColorDimmerEffect:
    """Tests for CustomDpColorDimmerEffect data points."""

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
    async def test_cecolordimmereffect(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpColorDimmerEffect."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        light: CustomDpColorDimmerEffect = cast(
            CustomDpColorDimmerEffect, get_prepared_custom_data_point(central, "VCU3747418", 1)
        )
        assert light.usage == DataPointUsage.CDP_PRIMARY
        assert light.color_temp_kelvin is None
        assert light.hs_color == (0.0, 0.0)
        assert light.supports_brightness is True
        assert light.supports_color_temperature is False
        assert light.supports_effects is True
        assert light.supports_hs_color is True
        assert light.supports_transition is True
        assert light.effect is None
        assert light.effects == (
            "Off",
            "Slow color change",
            "Medium color change",
            "Fast color change",
            "Campemit",
            "Waterfall",
            "TV simulation",
        )

        assert light.brightness == 0
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 0

        assert light.hs_color == (0.0, 0.0)
        await light.turn_on(hs_color=(44.4, 69.3))
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU3747418:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="COLOR",
            value=25,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.hs_color == (45.0, 100)

        await light.turn_on(hs_color=(0, 50))
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU3747418:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="COLOR",
            value=0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.hs_color == (0.0, 100.0)

        await light.turn_on(effect="Slow color change")

        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="PROGRAM",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        assert light.effect == "Slow color change"

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3747418:2", parameter="COLOR", value=201
        )
        assert light.hs_color == (0.0, 0.0)
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU3747418:2", parameter="COLOR", value=None
        )
        assert light.hs_color == (0.0, 0.0)

        await light.turn_on()
        call_count = len(mock_client.method_calls)
        await light.turn_on()
        assert call_count == len(mock_client.method_calls)

        await light.turn_off()
        call_count = len(mock_client.method_calls)
        await light.turn_off()
        assert call_count == len(mock_client.method_calls)

        await light.turn_on(brightness=28, effect="Slow color change")
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="PROGRAM",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )


class TestCustomDpColorTempDimmer:
    """Tests for CustomDpColorTempDimmer data points."""

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
    async def test_cecolortempdimmer(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpColorTempDimmer."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        light: CustomDpColorTempDimmer = cast(
            CustomDpColorTempDimmer, get_prepared_custom_data_point(central, "VCU0000115", 1)
        )
        assert light.usage == DataPointUsage.CDP_PRIMARY
        assert light.color_temp_kelvin == 2000
        assert light.hs_color is None
        assert light.supports_brightness is True
        assert light.supports_color_temperature is True
        assert light.supports_effects is False
        assert light.supports_hs_color is False
        assert light.supports_transition is True
        assert light.effect is None
        assert light.effects is None
        assert light.brightness == 0
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000115:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000115:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000115:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 0

        assert light.color_temp_kelvin == 2000
        await light.turn_on(color_temp_kelvin=2309)
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU0000115:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.1930835734870317,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000115:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_temp_kelvin == 2309

        await light.turn_on()
        call_count = len(mock_client.method_calls)
        await light.turn_on()
        assert call_count == len(mock_client.method_calls)

        await light.turn_off()
        call_count = len(mock_client.method_calls)
        await light.turn_off()
        assert call_count == len(mock_client.method_calls)


class TestCustomDpIpFixedColorLight:
    """Tests for CustomDpIpFixedColorLight data points."""

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
    async def test_ceipfixedcolorlight(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpFixedColorLight."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        light: CustomDpIpFixedColorLight = cast(
            CustomDpIpFixedColorLight, get_prepared_custom_data_point(central, "VCU6985973", 8)
        )
        assert light.usage == DataPointUsage.CDP_PRIMARY
        assert light.color_temp_kelvin is None
        assert light.hs_color == (0.0, 0.0)
        assert light.supports_brightness is True
        assert light.supports_color_temperature is False
        assert light.supports_effects is True
        assert light.supports_hs_color is True
        assert light.supports_transition is True
        assert light.effect is None
        assert light.effects == (
            "ON",
            "BLINKING_SLOW",
            "BLINKING_MIDDLE",
            "BLINKING_FAST",
            "FLASH_SLOW",
            "FLASH_MIDDLE",
            "FLASH_FAST",
            "BILLOW_SLOW",
            "BILLOW_MIDDLE",
            "BILLOW_FAST",
        )
        assert light.brightness == 0
        assert light.is_on is False
        assert light.color_name == FixedColor.BLACK
        assert light.channel_color_name is None
        assert light.group_brightness is None
        assert light.channel_hs_color is None
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.WHITE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "LEVEL": 0.10980392156862745,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6985973:8",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 0
        assert light.color_name == FixedColor.WHITE

        await light.turn_on(hs_color=(350, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.RED, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_name == FixedColor.RED

        await light.turn_on(hs_color=(0.0, 0.0))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.WHITE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_name == FixedColor.WHITE

        await light.turn_on(hs_color=(60.0, 50.0))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.YELLOW, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_name == FixedColor.YELLOW

        await light.turn_on(hs_color=(120, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.GREEN, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_name == FixedColor.GREEN

        await light.turn_on(hs_color=(180, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.TURQUOISE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_name == FixedColor.TURQUOISE

        await light.turn_on(hs_color=(240, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.BLUE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_name == FixedColor.BLUE

        await light.turn_on(hs_color=(300, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.PURPLE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_name == FixedColor.PURPLE

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6985973:7", parameter="LEVEL", value=0.5
        )
        assert light.group_brightness == 127

        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU6985973:7", parameter="COLOR", value=1
        )
        assert light.channel_hs_color == (240.0, 100.0)
        assert light.channel_color_name == FixedColor.BLUE

        await light.turn_off()
        light.set_timer_on_time(on_time=18)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.SECONDS,
                "DURATION_VALUE": 18,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_off()
        light.set_timer_on_time(on_time=17000)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.MINUTES,
                "DURATION_VALUE": 283,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_off()
        light.set_timer_on_time(on_time=1000000)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": 277,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await light.turn_on(ramp_time=18)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "RAMP_TIME_UNIT": _TimeUnit.SECONDS,
                "RAMP_TIME_VALUE": 18,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on(ramp_time=17000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "RAMP_TIME_UNIT": _TimeUnit.MINUTES,
                "RAMP_TIME_VALUE": 283,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on(ramp_time=1000000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "RAMP_TIME_UNIT": _TimeUnit.HOURS,
                "RAMP_TIME_VALUE": 277,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on()
        call_count = len(mock_client.method_calls)
        await light.turn_on()
        assert call_count == len(mock_client.method_calls)

        await light.turn_off()
        call_count = len(mock_client.method_calls)
        await light.turn_off()
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
    async def test_ceipfixedcolorlightwired(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpFixedColorLight."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        light: CustomDpIpFixedColorLight = cast(
            CustomDpIpFixedColorLight, get_prepared_custom_data_point(central, "VCU4704397", 8)
        )
        assert light.channel.device.has_sub_devices is False
        assert light.usage == DataPointUsage.CDP_PRIMARY
        assert light.color_temp_kelvin is None
        assert light.hs_color == (0.0, 0.0)
        assert light.supports_brightness is True
        assert light.supports_color_temperature is False
        assert light.supports_effects is True
        assert light.supports_hs_color is True
        assert light.supports_transition is True
        assert light.effect is None
        assert light.effects == (
            _ColorBehaviour.ON,
            "BLINKING_SLOW",
            "BLINKING_MIDDLE",
            "BLINKING_FAST",
            "FLASH_SLOW",
            "FLASH_MIDDLE",
            "FLASH_FAST",
            "BILLOW_SLOW",
            "BILLOW_MIDDLE",
            "BILLOW_FAST",
        )
        assert light.brightness == 0
        assert light.is_on is False
        assert light.color_name == FixedColor.BLACK
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.WHITE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.WHITE

        await light.turn_on(brightness=100)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 0.39215686274509803},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 100
        assert light.color_name == FixedColor.WHITE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU4704397:8",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 0
        assert light.color_name == FixedColor.WHITE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(350, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.RED, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.RED
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(0.0, 0.0))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.WHITE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.WHITE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(60.0, 50.0))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.YELLOW, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.YELLOW
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(120, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.GREEN, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.GREEN
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(180, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.TURQUOISE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.TURQUOISE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(240, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.BLUE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.BLUE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(300, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR": FixedColor.PURPLE, "COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_off()
        assert light.brightness == 0
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(brightness=100)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 0.39215686274509803},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 100
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(brightness=33)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR_BEHAVIOUR": _ColorBehaviour.ON, "LEVEL": 0.12941176470588237},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 33
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(effect="FLASH_MIDDLE")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR_BEHAVIOUR": "FLASH_MIDDLE", "LEVEL": 0.12941176470588237},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 33
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == "FLASH_MIDDLE"

        await light.turn_on(brightness=66)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR_BEHAVIOUR": "FLASH_MIDDLE", "LEVEL": 0.25882352941176473},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 66
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == "FLASH_MIDDLE"

        await light.turn_off()

        light.set_timer_on_time(on_time=18)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.SECONDS,
                "DURATION_VALUE": 18,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_off()
        light.set_timer_on_time(on_time=17000)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.MINUTES,
                "DURATION_VALUE": 283,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_off()
        light.set_timer_on_time(on_time=1000000)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": 277,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        await light.turn_on(ramp_time=18)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "RAMP_TIME_UNIT": _TimeUnit.SECONDS,
                "RAMP_TIME_VALUE": 18,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on(ramp_time=17000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "RAMP_TIME_UNIT": _TimeUnit.MINUTES,
                "RAMP_TIME_VALUE": 283,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on(ramp_time=1000000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "RAMP_TIME_UNIT": _TimeUnit.HOURS,
                "RAMP_TIME_VALUE": 277,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on()
        call_count = len(mock_client.method_calls)
        await light.turn_on()
        assert call_count == len(mock_client.method_calls)

        await light.turn_off()
        call_count = len(mock_client.method_calls)
        await light.turn_off()
        assert call_count == len(mock_client.method_calls)

        await light.turn_off()
        await light.turn_on(effect="BLINKING_SLOW")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR_BEHAVIOUR": "BLINKING_SLOW", "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on(brightness=28)
        await light.turn_on(effect="FLASH_MIDDLE")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR_BEHAVIOUR": "FLASH_MIDDLE", "LEVEL": 0.10980392156862745},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )


class TestCustomDpIpRGBWLight:
    """Tests for CustomDpIpRGBWLight data points."""

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
    async def test_ceiprgbwlight(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpIpRGBWLight."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        light: CustomDpIpRGBWLight = cast(CustomDpIpRGBWLight, get_prepared_custom_data_point(central, "VCU5629873", 1))
        assert light.channel.device.has_sub_devices is False
        assert light.usage == DataPointUsage.CDP_PRIMARY
        assert light.color_temp_kelvin is None
        assert light.hs_color is None
        assert light.supports_brightness is True
        assert light.supports_color_temperature is False
        assert light.supports_effects is True
        assert light.supports_hs_color is True
        assert light.supports_transition is True
        assert light.effect is None
        assert light.effects == (
            "NO_EFFECT",
            "EFFECT_01_END_CURRENT_PROFILE",
            "EFFECT_01_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_02_END_CURRENT_PROFILE",
            "EFFECT_02_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_03_END_CURRENT_PROFILE",
            "EFFECT_03_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_04_END_CURRENT_PROFILE",
            "EFFECT_04_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_05_END_CURRENT_PROFILE",
            "EFFECT_05_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_06_END_CURRENT_PROFILE",
            "EFFECT_06_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_07_END_CURRENT_PROFILE",
            "EFFECT_07_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_08_END_CURRENT_PROFILE",
            "EFFECT_08_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_09_END_CURRENT_PROFILE",
            "EFFECT_09_INTERRUPT_CURRENT_PROFILE",
            "EFFECT_10_END_CURRENT_PROFILE",
            "EFFECT_10_INTERRUPT_CURRENT_PROFILE",
        )

        assert light.brightness == 0

        await light.turn_on()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU5629873:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU5629873:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU5629873:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 0

        assert light.color_temp_kelvin is None
        await light.turn_on(color_temp_kelvin=3000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"COLOR_TEMPERATURE": 3000, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.color_temp_kelvin == 3000

        await light.turn_on()
        call_count = len(mock_client.method_calls)
        await light.turn_on()
        assert call_count == len(mock_client.method_calls)

        await light.turn_off()
        call_count = len(mock_client.method_calls)
        await light.turn_off()
        assert call_count == len(mock_client.method_calls)

        assert light.hs_color is None
        await light.turn_on(hs_color=(44.4, 69.3))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"HUE": 44, "SATURATION": 0.693, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.hs_color == (44, 69.3)

        await light.turn_on(hs_color=(0, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"HUE": 0, "SATURATION": 0.5, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.hs_color == (0.0, 50.0)

        await light.turn_on(effect="EFFECT_01_END_CURRENT_PROFILE")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"EFFECT": "EFFECT_01_END_CURRENT_PROFILE", "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on(hs_color=(44, 66), ramp_time=5)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "HUE": 44,
                "SATURATION": 0.66,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.SECONDS,
                "RAMP_TIME_VALUE": 5,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_off(ramp_time=5)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.SECONDS,
                "RAMP_TIME_VALUE": 5,
                "LEVEL": 0.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )

        await light.turn_on(hs_color=(44, 66), ramp_time=5, on_time=8760)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "HUE": 44,
                "SATURATION": 0.66,
                "RAMP_TIME_UNIT": _TimeUnit.SECONDS,
                "RAMP_TIME_VALUE": 5,
                "DURATION_UNIT": _TimeUnit.SECONDS,
                "DURATION_VALUE": 8760,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
        )


class TestCustomDpColorDimmer:
    """Tests for CustomDpColorDimmer data points."""

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
    async def test_cecolordimmer(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpColorDimmer."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        light: CustomDpColorDimmer = cast(
            CustomDpColorDimmer, get_prepared_custom_data_point(central, "VCU9973336", 13)
        )
        assert light.usage == DataPointUsage.CDP_PRIMARY
        assert light.color_temp_kelvin is None
        assert light.hs_color == (0.0, 0.0)
        assert light.supports_brightness is True
        assert light.supports_color_temperature is False
        assert light.supports_effects is False
        assert light.supports_hs_color is True
        assert light.supports_transition is True
        assert light.effect is None

        assert light.brightness == 0
        assert light.brightness_pct == 0
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.brightness == 0

        assert light.hs_color == (0.0, 0.0)
        await light.turn_on(hs_color=(44.4, 69.3))
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU9973336:15",
            paramset_key=ParamsetKey.VALUES,
            parameter="COLOR",
            value=25,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.hs_color == (45.0, 100)

        await light.turn_on(hs_color=(0, 50))
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU9973336:15",
            paramset_key=ParamsetKey.VALUES,
            parameter="COLOR",
            value=0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.hs_color == (0.0, 100.0)
        await light.turn_on(hs_color=(0, 1))
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU9973336:15",
            paramset_key=ParamsetKey.VALUES,
            parameter="COLOR",
            value=200,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
        )
        assert light.hs_color == (0.0, 0.0)
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9973336:15", parameter="COLOR", value=201
        )
        assert light.hs_color == (0.0, 0.0)
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU9973336:15", parameter="COLOR", value=None
        )
        assert light.hs_color == (0.0, 0.0)

        await light.turn_on()
        call_count = len(mock_client.method_calls)
        await light.turn_on()
        assert call_count == len(mock_client.method_calls)

        await light.turn_off()
        call_count = len(mock_client.method_calls)
        await light.turn_off()
        assert call_count == len(mock_client.method_calls)
