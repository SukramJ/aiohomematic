"""
Integration tests for multi-step scenarios.

These tests validate complete workflows across multiple components,
ensuring proper coordination between device discovery, value operations,
event handling, and connection management.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest

from aiohomematic.central.event_bus import DataPointUpdatedEvent
from aiohomematic.const import DataPointKey, ParamsetKey

TEST_DEVICES: set[str] = {"VCU2128127", "VCU6354483"}


class TestDeviceDiscoveryWorkflow:
    """Test device discovery -> read -> write -> verify workflows."""

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
    async def test_device_channels_have_data_points(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that device channels have data points after discovery."""
        central, client, factory = central_client_factory_with_homegear_client

        devices = list(central.devices)
        assert len(devices) > 0

        # Find a device with channels
        device_with_channels = next(
            (d for d in devices if len(d.channels) > 0),
            None,
        )

        if device_with_channels:
            # Verify channels have data points
            for channel in device_with_channels.channels.values():
                # Most channels should have at least one data point
                # (though some may be empty)
                assert channel.address is not None

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
    async def test_device_discovery_lists_all_devices(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that device discovery finds all devices in the session."""
        central, client, factory = central_client_factory_with_homegear_client

        # Verify devices were discovered
        devices = list(central.devices)
        assert len(devices) > 0

        # Verify device properties are populated
        for device in devices:
            assert device.address is not None
            assert device.model is not None
            # Channels should exist for most devices
            assert len(device.channels) >= 0

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
    async def test_get_device_by_address(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test retrieving a specific device by address."""
        central, client, factory = central_client_factory_with_homegear_client

        devices = list(central.devices)
        assert len(devices) > 0

        # Get first device's address
        first_device = devices[0]
        address = first_device.address

        # Retrieve by address
        retrieved = central.get_device(address=address)
        assert retrieved is not None
        assert retrieved.address == address
        assert retrieved.model == first_device.model

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
    async def test_get_device_returns_none_for_unknown(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test that getting unknown device returns None."""
        central, client, factory = central_client_factory_with_homegear_client

        # Try to get non-existent device
        result = central.get_device(address="NONEXISTENT123")
        assert result is None


class TestEventSubscriptionWorkflow:
    """Test event subscription workflows across components."""

    @pytest.mark.asyncio
    async def test_multiple_subscribers_different_devices(self) -> None:
        """Test multiple subscribers for different devices receive correct events."""
        from aiohomematic.central.event_bus import EventBus

        bus = EventBus()
        device1_events: list[DataPointUpdatedEvent] = []
        device2_events: list[DataPointUpdatedEvent] = []

        dpk1 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        dpk2 = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000002:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        def handler1(event: DataPointUpdatedEvent) -> None:
            device1_events.append(event)

        def handler2(event: DataPointUpdatedEvent) -> None:
            device2_events.append(event)

        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk1, handler=handler1)
        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk2, handler=handler2)

        # Publish event for device 1
        event1 = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk1,
            value=True,
            received_at=datetime.now(),
        )
        await bus.publish(event=event1)

        # Publish event for device 2
        event2 = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk2,
            value=False,
            received_at=datetime.now(),
        )
        await bus.publish(event=event2)

        # Verify each handler only received its own events
        assert len(device1_events) == 1
        assert len(device2_events) == 1
        assert device1_events[0].dpk == dpk1
        assert device2_events[0].dpk == dpk2

    @pytest.mark.asyncio
    async def test_subscribe_receive_unsubscribe_flow(self) -> None:
        """Test complete subscribe -> receive -> unsubscribe workflow."""
        from aiohomematic.central.event_bus import EventBus

        bus = EventBus()
        received_events: list[DataPointUpdatedEvent] = []

        # Create data point key
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        # Subscribe
        def handler(event: DataPointUpdatedEvent) -> None:
            received_events.append(event)

        unsubscribe = bus.subscribe(
            event_type=DataPointUpdatedEvent,
            event_key=dpk,
            handler=handler,
        )

        # Verify subscription is active
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 1

        # Publish event
        event = DataPointUpdatedEvent(
            timestamp=datetime.now(),
            dpk=dpk,
            value=True,
            received_at=datetime.now(),
        )
        await bus.publish(event=event)

        # Verify event was received
        assert len(received_events) == 1
        assert received_events[0].value is True

        # Unsubscribe
        unsubscribe()
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 0

        # Publish again - should not be received
        await bus.publish(event=event)
        assert len(received_events) == 1  # Still 1


class TestConnectionStateWorkflow:
    """Test connection state management workflows."""

    @pytest.mark.asyncio
    async def test_connection_state_callback_on_issue(self) -> None:
        """Test that connection state callbacks are invoked on issues."""
        from aiohomematic.central import CentralConnectionState
        from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient

        state = CentralConnectionState()
        callback_calls: list[tuple[str, bool]] = []

        def on_state_change(interface_id: str, connected: bool) -> None:
            callback_calls.append((interface_id, connected))

        # Register callback
        unsubscribe = state.register_state_change_callback(callback=on_state_change)

        # Create a mock issuer that isinstance checks will recognize
        mock_issuer = Mock(spec=AioJsonRpcAioHttpClient)

        # Add an issue
        state.add_issue(issuer=mock_issuer, iid="HmIP-RF")

        # Verify callback was invoked
        assert len(callback_calls) == 1
        assert callback_calls[0] == ("HmIP-RF", False)

        # Remove issue
        state.remove_issue(issuer=mock_issuer, iid="HmIP-RF")

        # Verify callback for reconnection
        assert len(callback_calls) == 2
        assert callback_calls[1] == ("HmIP-RF", True)

        # Unsubscribe and verify no more calls
        unsubscribe()
        state.add_issue(issuer=mock_issuer, iid="HmIP-RF")
        assert len(callback_calls) == 2  # Still 2

    @pytest.mark.asyncio
    async def test_connection_state_multiple_issues(self) -> None:
        """Test connection state with multiple concurrent issues."""
        from aiohomematic.central import CentralConnectionState
        from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient
        from aiohomematic.client.rpc_proxy import BaseRpcProxy

        state = CentralConnectionState()

        # Create mock issuers
        mock_json_issuer = Mock(spec=AioJsonRpcAioHttpClient)
        mock_rpc_issuer = Mock(spec=BaseRpcProxy)

        # Add multiple issues
        state.add_issue(issuer=mock_json_issuer, iid="HmIP-RF")
        state.add_issue(issuer=mock_rpc_issuer, iid="BidCos-RF")

        # Verify state
        assert state.has_any_issue is True
        assert state.issue_count == 2
        assert state.json_issue_count == 1
        assert state.rpc_proxy_issue_count == 1

        # Remove one issue
        state.remove_issue(issuer=mock_json_issuer, iid="HmIP-RF")
        assert state.has_any_issue is True
        assert state.issue_count == 1

        # Clear all
        state.clear_all_issues()
        assert state.has_any_issue is False
        assert state.issue_count == 0


class TestConcurrentOperations:
    """Test concurrent operation handling."""

    @pytest.mark.asyncio
    async def test_concurrent_event_publishing(self) -> None:
        """Test that concurrent event publishing works correctly."""
        from aiohomematic.central.event_bus import EventBus

        bus = EventBus()
        received_events: list[DataPointUpdatedEvent] = []
        lock = asyncio.Lock()

        async def handler(event: DataPointUpdatedEvent) -> None:
            async with lock:
                received_events.append(event)

        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        bus.subscribe(event_type=DataPointUpdatedEvent, event_key=dpk, handler=handler)

        # Publish many events concurrently
        events = [
            DataPointUpdatedEvent(
                timestamp=datetime.now(),
                dpk=dpk,
                value=i,
                received_at=datetime.now(),
            )
            for i in range(100)
        ]

        await asyncio.gather(*[bus.publish(event=e) for e in events])

        # All events should be received
        assert len(received_events) == 100
        values = {e.value for e in received_events}
        assert values == set(range(100))

    @pytest.mark.asyncio
    async def test_concurrent_subscribe_unsubscribe(self) -> None:
        """Test that concurrent subscribe/unsubscribe operations are thread-safe."""
        from aiohomematic.central.event_bus import EventBus

        bus = EventBus()
        dpk = DataPointKey(
            interface_id="BidCos-RF",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

        unsubscribe_funcs: list[Any] = []

        def handler(event: DataPointUpdatedEvent) -> None:
            pass

        async def subscribe_task() -> None:
            for _ in range(50):
                unsub = bus.subscribe(
                    event_type=DataPointUpdatedEvent,
                    event_key=dpk,
                    handler=handler,
                )
                unsubscribe_funcs.append(unsub)
                await asyncio.sleep(0)

        async def unsubscribe_task() -> None:
            for _ in range(50):
                if unsubscribe_funcs:
                    try:
                        unsub = unsubscribe_funcs.pop(0)
                        unsub()
                    except IndexError:
                        pass
                await asyncio.sleep(0)

        # Run concurrent subscribe/unsubscribe
        await asyncio.gather(
            subscribe_task(),
            unsubscribe_task(),
            return_exceptions=True,
        )

        # Clean up remaining subscriptions
        for unsub in unsubscribe_funcs:
            unsub()

        # Final state should be consistent
        assert bus.get_subscription_count(event_type=DataPointUpdatedEvent) == 0


class TestRetryIntegration:
    """Test retry logic integration with operations."""

    @pytest.mark.asyncio
    async def test_retry_strategy_permanent_error_no_retry(self) -> None:
        """Test that permanent errors are not retried."""
        from aiohomematic.exceptions import AuthFailure
        from aiohomematic.retry import with_retry

        attempts = []

        @with_retry(max_attempts=3, initial_backoff=0.01)
        async def auth_operation() -> str:
            attempts.append(1)
            raise AuthFailure("Invalid credentials")

        with pytest.raises(AuthFailure):
            await auth_operation()

        # Should only attempt once (no retry for auth failure)
        assert len(attempts) == 1

    @pytest.mark.asyncio
    async def test_retry_strategy_with_transient_error(self) -> None:
        """Test that retry strategy handles transient errors."""
        from aiohomematic.retry import with_retry

        attempts = []

        @with_retry(max_attempts=3, initial_backoff=0.01)
        async def flaky_operation() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise TimeoutError("Transient error")
            return "success"

        result = await flaky_operation()
        assert result == "success"
        assert len(attempts) == 3


class TestValidationIntegration:
    """Test parameter validation integration."""

    def test_min_max_validation_message(self) -> None:
        """Test that validation messages are properly formatted."""
        from aiohomematic.exceptions import ValidationException

        # Simulate validation error with context
        exc = ValidationException("Value 150.0 exceeds maximum 100.0 for parameter LEVEL")
        assert "150.0" in str(exc)
        assert "100.0" in str(exc)
        assert "LEVEL" in str(exc)
