# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for light data points of aiohomematic."""

from typing import Any, cast
from unittest.mock import call

import pytest

from aiohomematic.client import CommandPriority
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
    "VCU0000079",
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
        assert light.capabilities.brightness is True
        assert light.has_color_temperature is False
        assert light.has_effects is False
        assert light.has_hs_color is False
        assert light.capabilities.transition is True
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
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await light.turn_on(on_time=5.0)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"ON_TIME": 5.0, "LEVEL": 0.10980392156862745},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await light.turn_off(ramp_time=6.0)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"RAMP_TIME": 6.0, "LEVEL": 0.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        # Simulate the state-channel event so that group_level (which is the
        # authoritative status source for is_on / brightness) is in sync.
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1399816:3", parameter="LEVEL", value=0.0
        )
        assert light.brightness == 0
        await light.turn_on()
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1399816:3", parameter="LEVEL", value=1.0
        )
        assert light.brightness == 255
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU1399816:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await light.turn_off()
        light.set_timer_on_time(on_time=0.5)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"ON_TIME": 0.5, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        light.set_timer_on_time(on_time=1.6)
        await light.turn_on()
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU1399816:4",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"ON_TIME": 1.6, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
    async def test_cedimmer_hmip_uses_action_channel_for_state(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        HmIP dimmers must derive state from the action channel only.

        Regression test for #3181: the state channel (primary-1) on HmIP
        devices carries device-specific semantics — e.g. HmIP-FDT echoes a
        section summary on channel 1 instead of a 1:1 mirror of the action
        channel. The 2.7.0 behaviour read ``_dp_level`` directly; the
        #3166/#3177 work introduced a ``_dp_group_level`` priority that
        accidentally surfaced the divergent state-channel value for HmIP
        and produced the user-visible regression (all dimmer channels
        appearing to take the value of channel 1). ``_effective_level`` now
        distinguishes by parameter: ``LEVEL_REAL`` (RF) keeps the stable
        mirror, ``LEVEL`` (HmIP, on a different channel) falls back to the
        action channel.
        """
        central, _, _ = central_client_factory_with_homegear_client
        light: CustomDpDimmer = cast(CustomDpDimmer, get_prepared_custom_data_point(central, "VCU1399816", 4))

        # Action channel reaches 100 % (e.g. user set brightness=255).
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1399816:4", parameter="LEVEL", value=1.0
        )
        # State channel reports a divergent value — simulates the HmIP-FDT
        # case where channel 1 LEVEL is a section summary rather than a
        # mirror.
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1399816:3", parameter="LEVEL", value=0.4
        )
        # _effective_level uses the action channel — brightness reflects
        # what the user commanded, not the divergent group_level.
        assert light.is_on is True
        assert light.brightness == 255
        # group_brightness still exposes the state-channel value as a
        # distinct metric (no regression for consumers that need it).
        assert light.group_brightness == 102

        # 4 ms-gap variant from the #3177 follow-up log: action channel
        # echoes its final value before the state channel catches up. For
        # HmIP this scenario is now trivially handled (action channel wins
        # regardless of modified_at).
        await light.turn_off()
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU1399816:4", parameter="LEVEL", value=0.0
        )
        assert light._dp_group_level.value == 0.4  # state channel still stale
        assert light.is_on is False
        assert light.brightness == 0

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
    async def test_cedimmer_rf_intermediate_echo_during_backend_call(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Echo arriving during the backend call must see the in-flight value.

        Regression test for #3177/#3179 on RF dimmers: previously the
        tracker was only populated AFTER the backend call returned. An
        echo dispatched during the await would clear the optimistic state
        via ``_values_mismatch`` while ``unconfirmed_last_value_send`` was
        still None, so ``_effective_level`` fell back to the stale
        group_level (LEVEL_REAL) — producing a brief flicker.
        """
        central, mock_client, _ = central_client_factory_with_homegear_client
        light: CustomDpDimmer = cast(CustomDpDimmer, get_prepared_custom_data_point(central, "VCU0000079", 1))

        # Confirmed on-state at 75 % — for RF dimmers LEVEL and LEVEL_REAL
        # share the same channel.
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL", value=0.75
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL_REAL", value=0.75
        )
        assert light.is_on is True

        captured: list[tuple[bool, int | None, float | None]] = []

        async def fake_set_value(*, channel_address: str, parameter: str, value: float, **_: Any) -> None:
            # Inject an intermediate ramp echo BEFORE returning. Mirrors the
            # production CCU sequence where LEVEL echoes start streaming
            # before the setValue HTTP response is awaited.
            await central.event_coordinator.data_point_event(
                interface_id=const.INTERFACE_ID,
                channel_address=channel_address,
                parameter=parameter,
                value=0.745,
            )
            captured.append((light.is_on, light.brightness, light._dp_level.unconfirmed_last_value_send))

        mock_client._backend.set_value = fake_set_value

        await light.turn_off()

        # During the race window the in-flight store has the target value,
        # so the echo handler observes is_on=False even though the
        # optimistic state was cleared by the mismatching echo.
        assert captured == [(False, 0, 0.0)]

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
    async def test_cedimmer_rf_intermediate_level_during_ramp(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Intermediate LEVEL echo during an RF ramp must not flip is_on back.

        Regression test for #3177 on RF dimmers: when the CCU echoes an
        intermediate LEVEL value before finishing the ramp,
        ``_values_mismatch`` clears the optimistic state. Without the
        unconfirmed-last-value fallback the next read would surface the
        stale pre-command LEVEL_REAL and ``is_on`` would briefly flip back.
        """
        central, _, _ = central_client_factory_with_homegear_client
        light: CustomDpDimmer = cast(CustomDpDimmer, get_prepared_custom_data_point(central, "VCU0000079", 1))

        # Confirmed on-state at 75 % (LEVEL and LEVEL_REAL share channel 1).
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL", value=0.75
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL_REAL", value=0.75
        )
        assert light.is_on is True
        assert light.brightness == 191

        # User turns the light off — optimistic path reports AUS immediately.
        await light.turn_off()
        assert light.is_on is False
        assert light.brightness == 0
        assert light._dp_level.unconfirmed_last_value_send == 0.0

        # CCU echoes an intermediate ramp value on the action channel.
        # LEVEL_REAL still reports 0.75 — this is the window where the bug
        # used to fire.
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL", value=0.745
        )
        assert light.is_on is False
        assert light.brightness == 0

        # Final echo: action and state value converge to 0.
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL", value=0.0
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL_REAL", value=0.0
        )
        assert light.is_on is False
        assert light.brightness == 0

        # Mirror case: turning on to 75 %. Action channel sends a ramp-
        # start value (LEVEL=0.005) while LEVEL_REAL still reports 0 —
        # is_on must stay True (covered by unconfirmed_last_value_send).
        await light.turn_on(brightness=191)
        assert light.is_on is True
        assert light._dp_level.unconfirmed_last_value_send is not None
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL", value=0.005
        )
        assert light.is_on is True
        assert light.brightness > 0
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL", value=0.75
        )
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000079:1", parameter="LEVEL_REAL", value=0.75
        )
        assert light.is_on is True
        assert light.brightness == 191


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
        assert light.capabilities.brightness is True
        assert light.has_color_temperature is False
        assert light.has_effects is True
        assert light.has_hs_color is True
        assert light.capabilities.transition is True
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.hs_color == (45.0, 100)

        await light.turn_on(hs_color=(0, 50))
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU3747418:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="COLOR",
            value=0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.hs_color == (0.0, 100.0)

        await light.turn_on(effect="Slow color change")

        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU3747418:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="PROGRAM",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU3747418:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="PROGRAM",
            value=1,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
        assert light.capabilities.brightness is True
        assert light.has_color_temperature is True
        assert light.has_effects is False
        assert light.has_hs_color is False
        assert light.capabilities.transition is True
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000115:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000115:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU0000115:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
        assert light.capabilities.brightness is True
        assert light.has_color_temperature is False
        assert light.has_effects is True
        assert light.has_hs_color is True
        assert light.capabilities.transition is True
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
            values={
                "COLOR": FixedColor.WHITE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 0.10980392156862745,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU6985973:8",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 0
        assert light.color_name == FixedColor.WHITE

        await light.turn_on(brightness=28)
        await light.turn_off(ramp_time=5)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.SECONDS,
                "RAMP_TIME_VALUE": 5,
                "LEVEL": 0.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await light.turn_on(hs_color=(350, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.RED,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.color_name == FixedColor.RED

        await light.turn_on(hs_color=(0.0, 0.0))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.WHITE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.color_name == FixedColor.WHITE

        await light.turn_on(hs_color=(60.0, 50.0))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.YELLOW,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.color_name == FixedColor.YELLOW

        await light.turn_on(hs_color=(120, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.GREEN,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.color_name == FixedColor.GREEN

        await light.turn_on(hs_color=(180, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.TURQUOISE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.color_name == FixedColor.TURQUOISE

        await light.turn_on(hs_color=(240, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.BLUE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.color_name == FixedColor.BLUE

        await light.turn_on(hs_color=(300, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.PURPLE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await light.turn_on(ramp_time=18)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.SECONDS,
                "RAMP_TIME_VALUE": 18,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await light.turn_on(ramp_time=17000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.MINUTES,
                "RAMP_TIME_VALUE": 283,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await light.turn_on(ramp_time=1000000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU6985973:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.HOURS,
                "RAMP_TIME_VALUE": 277,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
        assert light.capabilities.brightness is True
        assert light.has_color_temperature is False
        assert light.has_effects is True
        assert light.has_hs_color is True
        assert light.capabilities.transition is True
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
            values={
                "COLOR": FixedColor.WHITE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.WHITE

        await light.turn_on(brightness=100)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 0.39215686274509803,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 0
        assert light.color_name == FixedColor.WHITE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(350, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.RED,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.RED
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(0.0, 0.0))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.WHITE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.WHITE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(60.0, 50.0))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.YELLOW,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.YELLOW
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(120, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.GREEN,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.GREEN
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(180, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.TURQUOISE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.TURQUOISE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(240, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.BLUE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        assert light.color_name == FixedColor.BLUE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(hs_color=(300, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR": FixedColor.PURPLE,
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 0.39215686274509803,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 100
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(brightness=33)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": _ColorBehaviour.ON,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 0.12941176470588237,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 33
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == _ColorBehaviour.ON

        await light.turn_on(effect="FLASH_MIDDLE")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 0.12941176470588237,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 33
        assert light.color_name == FixedColor.PURPLE
        assert light.effect == "FLASH_MIDDLE"

        await light.turn_on(brightness=66)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 0.25882352941176473,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        await light.turn_on(ramp_time=18)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.SECONDS,
                "RAMP_TIME_VALUE": 18,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await light.turn_on(ramp_time=17000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.MINUTES,
                "RAMP_TIME_VALUE": 283,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await light.turn_on(ramp_time=1000000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "RAMP_TIME_UNIT": _TimeUnit.HOURS,
                "RAMP_TIME_VALUE": 277,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            values={
                "COLOR_BEHAVIOUR": "BLINKING_SLOW",
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )

        await light.turn_on(brightness=28)
        await light.turn_on(effect="FLASH_MIDDLE")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU4704397:8",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_BEHAVIOUR": "FLASH_MIDDLE",
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 0.10980392156862745,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
        assert light.capabilities.brightness is True
        assert light.has_color_temperature is False
        assert light.has_effects is True
        assert light.has_hs_color is True
        assert light.capabilities.transition is True
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
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"DURATION_UNIT": _TimeUnit.HOURS, "DURATION_VALUE": _NOT_USED, "LEVEL": 1.0},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"DURATION_UNIT": _TimeUnit.HOURS, "DURATION_VALUE": _NOT_USED, "LEVEL": 0.10980392156862745},
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU5629873:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 0

        assert light.color_temp_kelvin is None
        await light.turn_on(color_temp_kelvin=3000)
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "COLOR_TEMPERATURE": 3000,
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            values={
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "HUE": 44,
                "SATURATION": 0.693,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.hs_color == (44, 69.3)

        await light.turn_on(hs_color=(0, 50))
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "HUE": 0,
                "SATURATION": 0.5,
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.hs_color == (0.0, 50.0)

        await light.turn_on(effect="EFFECT_01_END_CURRENT_PROFILE")
        assert mock_client.method_calls[-1] == call.put_paramset(
            channel_address="VCU5629873:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={
                "DURATION_UNIT": _TimeUnit.HOURS,
                "DURATION_VALUE": _NOT_USED,
                "EFFECT": "EFFECT_01_END_CURRENT_PROFILE",
                "LEVEL": 1.0,
            },
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
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
        assert light.capabilities.brightness is True
        assert light.has_color_temperature is False
        assert light.has_effects is False
        assert light.has_hs_color is True
        assert light.capabilities.transition is True
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 255
        await light.turn_on(brightness=28)
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.10980392156862745,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.brightness == 28
        await light.turn_off()
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.hs_color == (45.0, 100)

        await light.turn_on(hs_color=(0, 50))
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU9973336:15",
            paramset_key=ParamsetKey.VALUES,
            parameter="COLOR",
            value=0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert light.hs_color == (0.0, 100.0)
        await light.turn_on(hs_color=(0, 1))
        assert mock_client.method_calls[-2] == call.set_value(
            channel_address="VCU9973336:15",
            paramset_key=ParamsetKey.VALUES,
            parameter="COLOR",
            value=200,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
        )
        assert mock_client.method_calls[-1] == call.set_value(
            channel_address="VCU9973336:13",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
            wait_for_callback=WAIT_FOR_CALLBACK,
            priority=CommandPriority.HIGH,
            retry=True,
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
