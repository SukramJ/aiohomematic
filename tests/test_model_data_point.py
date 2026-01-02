# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for data point functionality of aiohomematic."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from unittest.mock import MagicMock, call

import pytest

from aiohomematic.central.events import DeviceLifecycleEvent, DeviceLifecycleEventType
from aiohomematic.const import CallSource, DataPointUsage, Interface, ParamsetKey
from aiohomematic.model.custom import CustomDpSwitch, get_required_parameters
from aiohomematic.model.generic import DpSensor, DpSwitch
from aiohomematic.store.visibility import check_ignore_parameters_is_clean
from aiohomematic_test_support import const
from aiohomematic_test_support.helper import get_prepared_custom_data_point

TEST_DEVICES: set[str] = {"VCU2128127", "VCU3609622"}

# pylint: disable=protected-access


class TestDataPointDefinition:
    """Tests for data point definition validation."""

    def test_custom_required_data_points(self) -> None:
        """Test required parameters from data point definitions."""
        required_parameters = get_required_parameters()
        assert len(required_parameters) == 108
        assert check_ignore_parameters_is_clean() is True


class TestDataPointCallbacks:
    """Tests for data point handler functionality."""

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
    async def test_custom_data_point_handler(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test CustomDpSwitch handler registration and events."""
        central, _, factory = central_client_factory_with_homegear_client
        switch: CustomDpSwitch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        assert switch.usage == DataPointUsage.CDP_PRIMARY

        device_updated_mock = MagicMock()
        device_removed_mock = MagicMock()

        unregister_data_point_updated_handler = switch.subscribe_to_data_point_updated(
            handler=device_updated_mock, custom_id="some_id"
        )
        unregister_device_removed_handler = switch.subscribe_to_device_removed(handler=device_removed_mock)
        assert switch.value is None
        assert str(switch) == "path: device/status/VCU2128127/4/SWITCH, name: HmIP-BSM_VCU2128127"
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:4", parameter="STATE", value=1
        )
        assert switch.value is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:4", parameter="STATE", value=0
        )
        assert switch.value is False
        # Wait for async event bus publish to complete for data point updates
        import asyncio

        await asyncio.sleep(0.1)
        await central.device_coordinator.delete_devices(
            interface_id=const.INTERFACE_ID, addresses=[switch.device.address]
        )
        # Wait for async event bus publish to complete for delete events
        await asyncio.sleep(0.1)
        # Verify the system event mock received a DeviceLifecycleEvent
        assert factory.system_event_mock.called
        # Find the last DeviceLifecycleEvent with REMOVED type
        device_lifecycle_events = [
            call[0][0]
            for call in factory.system_event_mock.call_args_list
            if isinstance(call[0][0], DeviceLifecycleEvent)
            and call[0][0].event_type == DeviceLifecycleEventType.REMOVED
        ]
        assert len(device_lifecycle_events) >= 1
        event = device_lifecycle_events[-1]
        assert event.event_type == DeviceLifecycleEventType.REMOVED
        assert "VCU2128127" in event.device_addresses
        unregister_data_point_updated_handler()
        unregister_device_removed_handler()

        device_updated_mock.assert_called_with(data_point=switch, custom_id="some_id")
        device_removed_mock.assert_called_with()

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
    async def test_generic_data_point_handler(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test generic data point handler registration and events."""
        central, _, factory = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(
            DpSwitch, central.get_generic_data_point(channel_address="VCU2128127:4", parameter="STATE")
        )
        assert switch.usage == DataPointUsage.NO_CREATE

        device_updated_mock = MagicMock()
        device_removed_mock = MagicMock()

        unregister_updated = switch.subscribe_to_data_point_updated(handler=device_updated_mock, custom_id="some_id")
        unregister_removed = switch.subscribe_to_device_removed(handler=device_removed_mock)
        assert switch.value is None
        assert str(switch) == "path: device/status/VCU2128127/4/STATE, name: HmIP-BSM_VCU2128127 State ch4"
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:4", parameter="STATE", value=1
        )
        assert switch.value is True
        await central.event_coordinator.data_point_event(
            interface_id=const.INTERFACE_ID, channel_address="VCU2128127:4", parameter="STATE", value=0
        )
        assert switch.value is False
        # Wait for async event bus publish to complete for data point updates
        import asyncio

        await asyncio.sleep(0.1)
        await central.device_coordinator.delete_devices(
            interface_id=const.INTERFACE_ID, addresses=[switch.device.address]
        )
        # Wait for async event bus publish to complete for delete events
        await asyncio.sleep(0.1)
        # Verify the system event mock received a DeviceLifecycleEvent
        assert factory.system_event_mock.called
        # Find the last DeviceLifecycleEvent with REMOVED type
        device_lifecycle_events = [
            call[0][0]
            for call in factory.system_event_mock.call_args_list
            if isinstance(call[0][0], DeviceLifecycleEvent)
            and call[0][0].event_type == DeviceLifecycleEventType.REMOVED
        ]
        assert len(device_lifecycle_events) >= 1
        event = device_lifecycle_events[-1]
        assert event.event_type == DeviceLifecycleEventType.REMOVED
        assert "VCU2128127" in event.device_addresses
        # Call the unregister handler to clean up
        if unregister_updated:
            unregister_updated()
        if unregister_removed:
            unregister_removed()

        device_updated_mock.assert_called_with(data_point=switch, custom_id="some_id")
        device_removed_mock.assert_called_with()


class TestDataPointLoading:
    """Tests for data point value loading."""

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
    async def test_load_custom_data_point(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test custom data point value loading."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(DpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        await switch.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
        assert mock_client.method_calls[-3] == call.get_value(
            channel_address="VCU2128127:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            call_source="hm_init",
        )
        assert mock_client.method_calls[-2] == call.get_value(
            channel_address="VCU2128127:3",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            call_source="hm_init",
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
    async def test_load_generic_data_point(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test generic data point value loading."""
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(
            DpSwitch, central.get_generic_data_point(channel_address="VCU2128127:4", parameter="STATE")
        )
        await switch.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
        assert mock_client.method_calls[-1] == call.get_value(
            channel_address="VCU2128127:4",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            call_source="hm_init",
        )


class TestWrappedDataPoint:
    """Tests for wrapped data point functionality."""

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
    async def test_generic_wrapped_data_point(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test wrapped data point category and forced sensor behavior."""
        central, _, _ = central_client_factory_with_homegear_client
        wrapped_data_point: DpSensor = cast(
            DpSensor, central.get_generic_data_point(channel_address="VCU3609622:1", parameter="LEVEL")
        )
        assert wrapped_data_point.default_category() == "number"
        assert wrapped_data_point._is_forced_sensor is True
        assert wrapped_data_point.category == "sensor"
        assert wrapped_data_point.usage == DataPointUsage.DATA_POINT


class TestIgnoreOnInitialLoad:
    """Tests for ignore_on_initial_load parameter handling."""

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
    async def test_ignore_on_initial_load_no_cache_remains_none(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test that ignore_on_initial_load data points with no cache stay None.

        When there's no cached value and ignore_on_initial_load=True,
        the value should remain None (no RPC call to wake battery devices).
        """
        central, mock_client, _ = central_client_factory_with_homegear_client
        switch: DpSwitch = cast(
            DpSwitch, central.get_generic_data_point(channel_address="VCU2128127:4", parameter="STATE")
        )
        assert switch.value is None

        # Record the number of method calls before our test
        call_count_before = len(mock_client.method_calls)

        # Mock the data point to have ignore_on_initial_load=True
        switch._ignore_on_initial_load = True

        # Try to load the value with HA_INIT call source (no cache, should not call backend)
        await switch.load_data_point_value(call_source=CallSource.HA_INIT)

        # Value should remain None (no cache, and we don't make RPC calls for ignored params)
        assert switch.value is None

        # Verify no RPC calls were made
        assert len(mock_client.method_calls) == call_count_before

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
    async def test_ignore_on_initial_load_uses_cache(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """
        Test that ignore_on_initial_load data points load from cache on init.

        Regression test for issue #2674:
        OperatingVoltageLevel sensor shows unknown after restart until device is triggered.
        The fix ensures that even when ignore_on_initial_load=True, cached values are used.
        """
        central, mock_client, _ = central_client_factory_with_homegear_client
        # Get a data point to test
        switch: DpSwitch = cast(
            DpSwitch, central.get_generic_data_point(channel_address="VCU2128127:4", parameter="STATE")
        )
        assert switch.value is None

        # Pre-populate the central data cache with a value (use BIDCOS_RF, matching test fixture)
        cache_key = f"{Interface.BIDCOS_RF}.VCU2128127:4.STATE"
        data_cache = central.cache_coordinator.data_cache
        data_cache._value_cache.setdefault(Interface.BIDCOS_RF, {})[cache_key] = True
        # Set refreshed_at to prevent cache from being considered stale
        data_cache._refreshed_at[Interface.BIDCOS_RF] = datetime.now()

        # Record the number of method calls before our test
        call_count_before = len(mock_client.method_calls)

        # Mock the data point to have ignore_on_initial_load=True
        switch._ignore_on_initial_load = True

        # Try to load the value with HA_INIT call source (should use cache, not RPC)
        await switch.load_data_point_value(call_source=CallSource.HA_INIT)

        # Verify the value was loaded from cache
        assert switch.value is True

        # Verify is_refreshed and is_valid are True after loading from cache
        # This is critical for HA integration - if is_valid is False, HA marks the entity as "restored"
        assert switch.is_refreshed is True
        assert switch.is_valid is True

        # Verify no RPC calls were made (should have used cache only)
        assert len(mock_client.method_calls) == call_count_before
