# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Unit tests for aiohomematic.client (__init__.py)."""

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from aiohomematic import central as hmcu
from aiohomematic.client import ClientConfig, InterfaceClient, InterfaceConfig, get_client as get_client_by_id
from aiohomematic.client.backends.capabilities import CCU_CAPABILITIES
from aiohomematic.client.state_change import (
    _isclose as client_isclose,
    _track_single_data_point_state_change_or_timeout,
    wait_for_state_change_or_timeout,
)
from aiohomematic.const import DEFAULT_TIMEOUT_CONFIG, DataPointKey, Interface, ParamsetKey
from aiohomematic.exceptions import ClientException

from tests.conftest import NoOpTaskScheduler


class _FakeDP:
    """Minimal fake DataPoint that disables events to exercise early-return path."""

    has_events = False


class _FakeDevice:
    """Minimal fake Device exposing get_generic_data_point for event tracker helpers."""

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey):
        return _FakeDP()


class _EventDP:
    """Fake DataPoint that supports events and provides a callback api for tracker timeout path."""

    def __init__(self, *, should_match: bool = False) -> None:
        self.has_events = True
        self._handler: Any | None = None
        self.value = 0.0 if should_match else 1.0
        self.unsub_called = False
        self.unique_id = "event_dp_test"


class _FakeEventBusForDP:
    """Minimal EventBus for _EventDevice."""

    def __init__(self) -> None:
        self.unsub_called = False

    def subscribe(self, *, event_type: type, event_key: Any, handler: Any) -> Callable[[], None]:
        """Return an unsubscribe function that tracks the call."""

        def _unsub() -> None:
            self.unsub_called = True

        return _unsub


class _FakeEventBusProviderForDP:
    """Minimal EventBusProvider for _EventDevice."""

    def __init__(self) -> None:
        self.event_bus = _FakeEventBusForDP()


class _EventDevice:
    """Device returning _EventDP to allow exercising the timeout branch of the tracker."""

    def __init__(self) -> None:
        self.dp = _EventDP()
        self.event_bus_provider = _FakeEventBusProviderForDP()

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey):
        return self.dp


class _MatchingEventDP:
    """Fake DataPoint that supports events and can fire a matching callback."""

    def __init__(self, *, match_value: Any) -> None:
        self.has_events = True
        self.value = match_value
        self.unique_id = "matching_dp_test"
        self.resolved = False


class _MatchingEventBus:
    """EventBus that stores the handler and allows triggering it."""

    def __init__(self) -> None:
        self.unsub_called = False
        self._handler: Any = None

    def fire(self) -> None:
        """Fire the stored handler."""
        if self._handler:
            self._handler(event=None)

    def subscribe(self, *, event_type: type, event_key: Any, handler: Any) -> Callable[[], None]:
        """Store handler and return unsub."""
        self._handler = handler

        def _unsub() -> None:
            self.unsub_called = True

        return _unsub


class _MatchingEventBusProvider:
    """EventBusProvider for _MatchingEventDevice."""

    def __init__(self) -> None:
        self.event_bus = _MatchingEventBus()


class _MatchingEventDevice:
    """Device that fires a matching event for the happy-path tracker test."""

    def __init__(self, *, match_value: Any) -> None:
        self.dp = _MatchingEventDP(match_value=match_value)
        self.event_bus_provider = _MatchingEventBusProvider()

    def fire_event(self) -> None:
        """Fire the stored event handler."""
        self.event_bus_provider.event_bus.fire()

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey) -> Any:
        """Return the matching data point."""
        return self.dp


class _MultiDP:
    """Fake DataPoint for multi-DP parallel test."""

    def __init__(self, *, value: Any, unique_id: str) -> None:
        self.has_events = True
        self.value = value
        self.unique_id = unique_id
        self.resolved = False


class _MultiDpEventBus:
    """EventBus supporting multiple handlers by event_key."""

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}
        self.unsub_called = False

    def fire(self, *, key: str) -> None:
        """Fire handler by key."""
        if handler := self._handlers.get(key):
            handler(event=None)

    def subscribe(self, *, event_type: type, event_key: Any, handler: Any) -> Callable[[], None]:
        """Store handler by key."""
        self._handlers[event_key] = handler

        def _unsub() -> None:
            self.unsub_called = True

        return _unsub


class _MultiDpEventBusProvider:
    """EventBusProvider for _MultiDpDevice."""

    def __init__(self) -> None:
        self.event_bus = _MultiDpEventBus()


class _MultiDpDevice:
    """Device with multiple data points for parallel test."""

    def __init__(self) -> None:
        self._dps: dict[str, _MultiDP] = {
            "LEVEL": _MultiDP(value=0.5, unique_id="dp_level"),
            "STATE": _MultiDP(value=True, unique_id="dp_state"),
        }
        self.event_bus_provider = _MultiDpEventBusProvider()

    def fire_event(self, *, parameter: str) -> None:
        """Fire event for a specific parameter."""
        dp = self._dps[parameter]
        dp.resolved = True
        self.event_bus_provider.event_bus.fire(key=dp.unique_id)

    def get_dp(self, parameter: str) -> _MultiDP:
        """Get a DP for assertion."""
        return self._dps[parameter]

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey) -> Any:
        """Return DP by parameter name."""
        if dp := self._dps.get(parameter):
            return dp
        return None


class _FakeCentral:
    """Minimal CentralUnit-like object for testing."""

    def __init__(self) -> None:
        from aiohomematic.central.events import EventBus

        self._event_bus = EventBus(task_scheduler=NoOpTaskScheduler())
        self.connection_state = hmcu.CentralConnectionState(event_bus_provider=self)
        self._clients: dict[str, object] = {}
        self.name = "central"
        self._listen_port_xml_rpc = 32001
        self._callback_ip_addr = "127.0.0.1"

        class Cfg:
            host = "localhost"
            tls = False
            verify_tls = False
            username = None
            password = None
            max_read_workers = 0
            callback_host = "127.0.0.1"
            callback_port_xml_rpc = 0
            interfaces_requiring_periodic_refresh = frozenset()
            timeout_config = DEFAULT_TIMEOUT_CONFIG

        self.config = Cfg()

    @property
    def cache_coordinator(self):
        """Return a mock cache coordinator."""
        return SimpleNamespace(
            device_details=SimpleNamespace(device_channel_ise_ids={}),
            paramset_descriptions=SimpleNamespace(get_parameter_data=lambda **kw: None),
            data_cache=SimpleNamespace(add_data=lambda **kw: None),
            device_descriptions=SimpleNamespace(get_device_descriptions=lambda **kw: None),
            incident_store=None,
            recorder=SimpleNamespace(),
        )

    @property
    def callback_ip_addr(self) -> str:
        return self._callback_ip_addr

    @property
    def event_bus(self):
        """Return the event bus."""
        return self._event_bus

    @property
    def listen_port_xml_rpc(self) -> int:
        return self._listen_port_xml_rpc

    def get_client(self, *, interface_id: str):
        return self._clients.get(interface_id)

    def has_client(self, *, interface_id: str) -> bool:
        return interface_id in self._clients


class TestClientEventTracking:
    """Test client event tracking helpers and timeouts."""

    @pytest.mark.asyncio
    async def test_event_tracker_float_fuzzy_match(self) -> None:
        """Tracker should match floats with 2-decimal fuzzy comparison."""
        dpk = DataPointKey(
            interface_id="i", channel_address="addr:1", paramset_key=ParamsetKey.VALUES, parameter="LEVEL"
        )
        # Value sent: 0.505, device reports: 0.504 — rounds to same 2-decimal value
        dev = _MatchingEventDevice(match_value=0.504)

        async def _fire_event() -> None:
            await asyncio.sleep(0.01)
            dev.fire_event()

        asyncio.create_task(_fire_event())  # noqa: RUF006
        await _track_single_data_point_state_change_or_timeout(device=dev, dpk_value=(dpk, 0.505), wait_for_callback=5)
        assert dev.event_bus_provider.event_bus.unsub_called is True

    @pytest.mark.asyncio
    async def test_event_tracker_happy_path_value_match(self) -> None:
        """Tracker should resolve immediately when event fires with matching value."""
        dpk = DataPointKey(
            interface_id="i", channel_address="addr:1", paramset_key=ParamsetKey.VALUES, parameter="LEVEL"
        )
        dev = _MatchingEventDevice(match_value=0.5)

        # Fire matching event shortly after subscription
        async def _fire_event() -> None:
            await asyncio.sleep(0.01)
            dev.fire_event()

        asyncio.create_task(_fire_event())  # noqa: RUF006
        await _track_single_data_point_state_change_or_timeout(device=dev, dpk_value=(dpk, 0.5), wait_for_callback=5)
        # Should have completed well before 5s timeout
        assert dev.event_bus_provider.event_bus.unsub_called is True

    @pytest.mark.asyncio
    async def test_event_tracker_parallel_data_points(self) -> None:
        """wait_for_state_change_or_timeout should wait for multiple DPs in parallel."""
        dpk1 = DataPointKey(
            interface_id="i", channel_address="addr:1", paramset_key=ParamsetKey.VALUES, parameter="LEVEL"
        )
        dpk2 = DataPointKey(
            interface_id="i", channel_address="addr:1", paramset_key=ParamsetKey.VALUES, parameter="STATE"
        )
        dev = _MultiDpDevice()

        # Fire both events shortly
        async def _fire_events() -> None:
            await asyncio.sleep(0.01)
            dev.fire_event(parameter="LEVEL")
            dev.fire_event(parameter="STATE")

        asyncio.create_task(_fire_events())  # noqa: RUF006
        await wait_for_state_change_or_timeout(device=dev, dpk_values={(dpk1, 0.5), (dpk2, True)}, wait_for_callback=5)
        # Both should have resolved
        assert dev.get_dp("LEVEL").resolved
        assert dev.get_dp("STATE").resolved

    @pytest.mark.asyncio
    async def test_event_tracker_timeout_and_unsubscribe(self) -> None:
        """Tracker should timeout and call unsubscribe in finally when event does not meet value condition."""
        dpk = DataPointKey(
            interface_id="i", channel_address="addr:1", paramset_key=ParamsetKey.VALUES, parameter="LEVEL"
        )
        dev = _EventDevice()
        await _track_single_data_point_state_change_or_timeout(device=dev, dpk_value=(dpk, 0.0), wait_for_callback=0)
        assert dev.event_bus_provider.event_bus.unsub_called is True

    @pytest.mark.asyncio
    async def test_event_tracking_helpers_early_return(self) -> None:
        """_track_single_data_point_state_change_or_timeout returns early when dp supports no events."""
        dpk = DataPointKey(
            interface_id="i",
            channel_address="addr:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
        )
        # Should not raise and should return quickly when dp.has_events is False
        await _track_single_data_point_state_change_or_timeout(
            device=_FakeDevice(), dpk_value=(dpk, 0), wait_for_callback=1
        )

        # The wrapper that awaits multiple trackers should also complete successfully
        await wait_for_state_change_or_timeout(device=_FakeDevice(), dpk_values={(dpk, 0)}, wait_for_callback=1)


class TestInterfaceConfig:
    """Test InterfaceConfig validation and enabling."""

    def test_interface_config_enabled_and_validation(self) -> None:
        """InterfaceConfig.enabled toggles; validation raises when port is falsy for callback-capable interfaces."""
        cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        assert cfg.enabled is True
        cfg.disable()
        assert cfg.enabled is False

        # Validation error when port is falsy and interface supports callback
        with pytest.raises(ClientException):
            InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=0)


class TestClientHelpers:
    """Test client helper functions and utilities."""

    @pytest.mark.asyncio
    async def test_client_helpers_isclose_and_get_client(self) -> None:
        """Import client module to generate coverage; verify _isclose and get_client(None)."""
        # float closeness uses rounding to 2 decimals
        assert client_isclose(value1=1.234, value2=1.2344) is True
        assert client_isclose(value1=1.234, value2=1.235) is False
        # non-floats: strict equality
        assert client_isclose(value1="a", value2="a") is True
        assert client_isclose(value1="a", value2="b") is False

        # get_client returns None for unknown interface_id, without mutating registry
        assert get_client_by_id(interface_id="non-existent-interface-id") is None


class TestClientConfigBasic:
    """Test ClientConfig basic functionality."""

    def test_client_config_cuxd_interface(self) -> None:
        """Test ClientConfig for CUxD interface (no RPC callback)."""
        central = _FakeCentral()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.CUXD, port=0)
        cfg = ClientConfig(client_deps=central, interface_config=iface_cfg)

        assert cfg.interface == Interface.CUXD
        assert cfg.has_rpc_callback is False
        assert cfg.has_ping_pong is False

    def test_client_config_properties(self) -> None:
        """Test that ClientConfig computes properties correctly."""
        central = _FakeCentral()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)
        cfg = ClientConfig(client_deps=central, interface_config=iface_cfg)

        assert cfg.interface == Interface.BIDCOS_RF
        assert cfg.interface_id == "c-BidCos-RF"
        assert cfg.has_rpc_callback is True
        assert cfg.has_ping_pong is True
        assert cfg.has_push_updates is True


class TestInterfaceClient:
    """Test InterfaceClient basic functionality."""

    def test_interface_client_properties(self) -> None:
        """Test that InterfaceClient exposes backend properties."""
        # Create a minimal fake backend
        fake_backend = SimpleNamespace(
            capabilities=CCU_CAPABILITIES,
            interface=Interface.BIDCOS_RF,
            interface_id="c-BidCos-RF",
            model="CCU",
            system_information=SimpleNamespace(),
            circuit_breaker=None,
            all_circuit_breakers_closed=True,
        )

        # Create minimal central and config
        central = _FakeCentral()
        iface_cfg = InterfaceConfig(central_name="c", interface=Interface.BIDCOS_RF, port=32001)

        # Create InterfaceClient manually (bypassing async init)
        client = object.__new__(InterfaceClient)
        client._backend = fake_backend
        client._central = central
        client._interface_config = iface_cfg
        client._version = "2.1"

        # Test properties
        assert client.interface == Interface.BIDCOS_RF
        assert client.interface_id == "c-BidCos-RF"
        assert client.model == "CCU"
        assert client.version == "2.1"
        assert client.capabilities == CCU_CAPABILITIES
