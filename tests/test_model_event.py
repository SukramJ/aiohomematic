"""Tests for event data points of aiohomematic."""

from __future__ import annotations

from typing import cast

import pytest

from aiohomematic.central.integration_events import DeviceTriggerEvent
from aiohomematic.const import DataPointUsage, DeviceTriggerEventType
from aiohomematic.model.event import ClickEvent, DeviceErrorEvent, ImpulseEvent
from aiohomematic_test_support import const

TEST_DEVICES: set[str] = {"VCU2128127", "VCU0000263"}

# pylint: disable=protected-access


class TestClickEvent:
    """Tests for ClickEvent data points."""

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
    async def test_click_event_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test ClickEvent keypress event handling and event data."""
        central, _, factory = central_client_factory_with_homegear_client
        event: ClickEvent = cast(ClickEvent, central.get_event(channel_address="VCU2128127:1", parameter="PRESS_SHORT"))
        assert event.usage == DataPointUsage.EVENT
        assert event.event_type == DeviceTriggerEventType.KEYPRESS
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:1", parameter="PRESS_SHORT", value=True
        )
        # Wait for async event bus publish to complete
        import asyncio

        await asyncio.sleep(0.1)
        # Verify the ha_event_mock received a DeviceTriggerEvent with the correct data
        assert factory.ha_event_mock.called
        # Find DeviceTriggerEvent calls
        trigger_events = [
            call[0][0] for call in factory.ha_event_mock.call_args_list if isinstance(call[0][0], DeviceTriggerEvent)
        ]
        assert len(trigger_events) >= 1
        event_obj = trigger_events[-1]
        assert event_obj.interface_id == const.INTERFACE_ID
        # channel_address is the device address from EventKey.ADDRESS in get_event_data()
        assert event_obj.channel_address == "VCU2128127"
        assert event_obj.parameter == "PRESS_SHORT"
        assert event_obj.value is True


class TestImpulseEvent:
    """Tests for ImpulseEvent data points."""

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
    async def test_impulse_event_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test ImpulseEvent impulse event handling and event data."""
        central, _, factory = central_client_factory_with_homegear_client
        event: ImpulseEvent = cast(
            ImpulseEvent, central.get_event(channel_address="VCU0000263:1", parameter="SEQUENCE_OK")
        )
        assert event.usage == DataPointUsage.EVENT
        assert event.event_type == DeviceTriggerEventType.IMPULSE
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU0000263:1", parameter="SEQUENCE_OK", value=True
        )
        # Wait for async event bus publish to complete
        import asyncio

        await asyncio.sleep(0.1)
        # Verify the ha_event_mock received a DeviceTriggerEvent with the correct data
        assert factory.ha_event_mock.called
        # Find DeviceTriggerEvent calls
        trigger_events = [
            call[0][0] for call in factory.ha_event_mock.call_args_list if isinstance(call[0][0], DeviceTriggerEvent)
        ]
        assert len(trigger_events) >= 1
        event_obj = trigger_events[-1]
        assert event_obj.interface_id == const.INTERFACE_ID
        # channel_address is the device address from EventKey.ADDRESS in get_event_data()
        assert event_obj.channel_address == "VCU0000263"
        assert event_obj.parameter == "SEQUENCE_OK"
        assert event_obj.value is True


class TestDeviceErrorEvent:
    """Tests for DeviceErrorEvent data points."""

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
    async def test_device_error_event_functionality(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test DeviceErrorEvent device error event handling and event data."""
        central, _, factory = central_client_factory_with_homegear_client
        event: DeviceErrorEvent = cast(
            DeviceErrorEvent,
            central.get_event(channel_address="VCU2128127:0", parameter="ERROR_OVERHEAT"),
        )
        assert event.usage == DataPointUsage.EVENT
        assert event.event_type == DeviceTriggerEventType.DEVICE_ERROR
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:0", parameter="ERROR_OVERHEAT", value=True
        )
        # Wait for async event bus publish to complete
        import asyncio

        await asyncio.sleep(0.1)
        # Verify the ha_event_mock received a DeviceTriggerEvent with the correct data
        assert factory.ha_event_mock.called
        # Find DeviceTriggerEvent calls
        trigger_events = [
            call[0][0] for call in factory.ha_event_mock.call_args_list if isinstance(call[0][0], DeviceTriggerEvent)
        ]
        assert len(trigger_events) >= 1
        event_obj = trigger_events[-1]
        assert event_obj.interface_id == const.INTERFACE_ID
        # channel_address is the device address from EventKey.ADDRESS in get_event_data()
        assert event_obj.channel_address == "VCU2128127"
        assert event_obj.parameter == "ERROR_OVERHEAT"
        assert event_obj.value is True
