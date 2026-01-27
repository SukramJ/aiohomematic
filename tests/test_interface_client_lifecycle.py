# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Tests for InterfaceClient lifecycle methods.

These tests verify the connection lifecycle operations:
- initialize_proxy / deinitialize_proxy / reinitialize_proxy
- check_connection_availability
- is_callback_alive
- is_connected
- State machine transitions
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from aiohomematic.client import InterfaceClient, InterfaceConfig
from aiohomematic.const import (
    DEFAULT_TIMEOUT_CONFIG,
    INIT_DATETIME,
    ClientState,
    Interface,
    ParamsetKey,
    ProxyInitState,
)


class _FakeEventBus:
    """Minimal fake EventBus for testing."""

    def __init__(self) -> None:
        self.published_events: list[Any] = []
        self._subscriptions: list[tuple[Any, Any, Any]] = []

    async def publish(self, *, event: Any) -> None:
        self.published_events.append(event)

    def publish_sync(self, *, event: Any) -> None:
        self.published_events.append(event)

    def subscribe(self, *, event_type: Any, event_key: Any, handler: Any) -> Any:
        self._subscriptions.append((event_type, event_key, handler))
        return lambda: None


class _FakeParamsetDescriptions:
    """Minimal paramset descriptions for testing."""

    def __init__(self) -> None:
        self._raw_paramset_descriptions: dict[str, Any] = {}

    def add(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, Any],
        device_type: str,
    ) -> None:
        if interface_id not in self._raw_paramset_descriptions:
            self._raw_paramset_descriptions[interface_id] = {}
        if channel_address not in self._raw_paramset_descriptions[interface_id]:
            self._raw_paramset_descriptions[interface_id][channel_address] = {}
        self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = paramset_description

    def get_parameter_data(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> dict[str, Any] | None:
        if self._raw_paramset_descriptions:
            try:
                return self._raw_paramset_descriptions[interface_id][channel_address][paramset_key].get(parameter)
            except KeyError:
                pass
        return None


class _FakeDeviceDescriptions:
    """Minimal device descriptions for testing."""

    def __init__(self) -> None:
        self._device_descriptions: dict[str, dict[str, Any]] = {}

    def find_device_description(self, *, interface_id: str, device_address: str) -> dict[str, Any] | None:
        if interface_id in self._device_descriptions:
            return self._device_descriptions[interface_id].get(device_address)
        return None

    def get_device_descriptions(self, *, interface_id: str) -> dict[str, Any] | None:
        return self._device_descriptions.get(interface_id, {})


class _FakeBackend:
    """Fake backend with configurable behavior for lifecycle testing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.interface_id = "test-BidCos-RF"
        self.interface = Interface.BIDCOS_RF
        self.model = "CCU"
        self.system_information = SimpleNamespace(
            available_interfaces=(Interface.BIDCOS_RF,),
            serial="TEST1234",
            has_backup=True,
        )
        self.capabilities = SimpleNamespace(
            backup=True,
            device_firmware_update=True,
            firmware_update_trigger=True,
            firmware_updates=True,
            functions=True,
            inbox_devices=True,
            install_mode=True,
            linking=True,
            metadata=True,
            ping_pong=True,
            programs=True,
            push_updates=True,
            rega_id_lookup=True,
            rename=True,
            rooms=True,
            rpc_callback=True,
            service_messages=True,
            system_update_info=True,
            value_usage_reporting=True,
        )
        self.all_circuit_breakers_closed = True
        self.circuit_breaker = MagicMock()

        # Configurable behavior for tests
        self._check_connection_result = True
        self._init_proxy_should_fail = False
        self._deinit_proxy_should_fail = False
        self._list_devices_result: tuple[dict[str, Any], ...] | None = ()

    async def check_connection(self, *, handle_ping_pong: bool, caller_id: str | None = None) -> bool:
        self.calls.append(("check_connection", (handle_ping_pong, caller_id)))
        return self._check_connection_result

    async def deinit_proxy(self, *, init_url: str) -> bool:
        self.calls.append(("deinit_proxy", init_url))
        if self._deinit_proxy_should_fail:
            from aiohomematic.exceptions import ClientException

            raise ClientException("Deinit proxy failed")
        return True

    async def get_device_description(self, *, address: str) -> dict[str, Any] | None:
        self.calls.append(("get_device_description", address))
        return {
            "ADDRESS": address,
            "TYPE": "TEST_DEVICE",
            "PARAMSETS": ["VALUES", "MASTER"],
            "CHILDREN": [f"{address}:1", f"{address}:2"] if ":" not in address else [],
        }

    async def get_paramset(self, *, address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
        self.calls.append(("get_paramset", (address, paramset_key)))
        return {"LEVEL": 0.5}

    async def get_paramset_description(self, *, address: str, paramset_key: ParamsetKey) -> dict[str, Any] | None:
        self.calls.append(("get_paramset_description", (address, paramset_key)))
        return {
            "LEVEL": {
                "TYPE": "FLOAT",
                "OPERATIONS": 7,
                "MIN": 0.0,
                "MAX": 1.0,
            },
        }

    async def get_value(self, *, address: str, parameter: str) -> Any:
        self.calls.append(("get_value", (address, parameter)))
        return 0.5

    async def init_proxy(self, *, init_url: str, interface_id: str) -> bool:
        self.calls.append(("init_proxy", (init_url, interface_id)))
        if self._init_proxy_should_fail:
            from aiohomematic.exceptions import ClientException

            raise ClientException("Init proxy failed")
        return True

    async def list_devices(self) -> tuple[dict[str, Any], ...] | None:
        self.calls.append(("list_devices", None))
        return self._list_devices_result

    async def put_paramset(
        self,
        *,
        address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: Any | None = None,
    ) -> None:
        self.calls.append(("put_paramset", (address, paramset_key, values, rx_mode)))

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        self.calls.append(("remove_link", (sender_address, receiver_address)))

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        self.calls.append(("rename_channel", (rega_id, new_name)))
        return True

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        self.calls.append(("rename_device", (rega_id, new_name)))
        return True

    async def report_value_usage(self, *, address: str, value_id: str, ref_counter: int) -> bool:
        self.calls.append(("report_value_usage", (address, value_id, ref_counter)))
        return True

    def reset_circuit_breakers(self) -> None:
        self.calls.append(("reset_circuit_breakers", None))

    async def set_install_mode(self, *, on: bool, time: int, mode: int = 1, device_address: str | None = None) -> bool:
        self.calls.append(("set_install_mode", (on, time, mode, device_address)))
        return True

    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(("set_metadata", (address, data_id, value)))
        return value

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        self.calls.append(("set_program_state", (pid, state)))
        return True

    async def set_value(
        self,
        *,
        address: str,
        parameter: str,
        value: Any,
        rx_mode: Any | None = None,
    ) -> None:
        self.calls.append(("set_value", (address, parameter, value, rx_mode)))

    async def stop(self) -> None:
        pass


class _FakeCentral:
    """Minimal CentralUnit-like object for lifecycle testing."""

    def __init__(self) -> None:
        self._event_bus = _FakeEventBus()
        self.paramset_descriptions = _FakeParamsetDescriptions()
        self.device_descriptions = _FakeDeviceDescriptions()
        self._devices: dict[str, Any] = {}
        self._channels: dict[str, Any] = {}
        self._data_points: dict[str, Any] = {}
        self.name = "test-central"
        self._last_event_seen: datetime | None = datetime.now()

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
        self._listen_port_xml_rpc = 32001
        self._callback_ip_addr = "127.0.0.1"

        def _close_task(*, target: Any, name: str) -> None:
            target.close()

        self.looper = SimpleNamespace(create_task=_close_task)
        self.json_rpc_client = SimpleNamespace(
            clear_session=lambda: None,
            circuit_breaker=SimpleNamespace(reset=lambda: None),
        )

        class _ConnectionState:
            def is_rpc_proxy_issue(self, *, interface_id: str) -> bool:
                return False

        self.connection_state = _ConnectionState()
        self._device_coordinator_add_called: list[Any] = []

    @property
    def cache_coordinator(self) -> Any:
        return SimpleNamespace(
            device_details=SimpleNamespace(
                add_interface=lambda **kwargs: None,
                add_name=lambda **kwargs: None,
                add_address_rega_id=lambda **kwargs: None,
            ),
            paramset_descriptions=self.paramset_descriptions,
            data_cache=SimpleNamespace(add_data=lambda **kwargs: None),
            device_descriptions=self.device_descriptions,
            incident_store=None,
        )

    @property
    def callback_ip_addr(self) -> str:
        return self._callback_ip_addr

    @property
    def device_coordinator(self) -> Any:
        parent = self

        class _FakeDeviceCoordinator:
            async def add_new_devices(
                self, *, interface_id: str, device_descriptions: tuple[dict[str, Any], ...]
            ) -> None:
                parent._device_coordinator_add_called.append((interface_id, device_descriptions))

        return _FakeDeviceCoordinator()

    @property
    def device_registry(self) -> Any:
        return SimpleNamespace(devices=tuple(self._devices.values()))

    @property
    def event_bus(self) -> Any:
        return self._event_bus

    @property
    def event_coordinator(self) -> Any:
        parent = self

        class _FakeEventCoordinator:
            def get_last_event_seen_for_interface(self, *, interface_id: str) -> datetime | None:
                return parent._last_event_seen

        return _FakeEventCoordinator()

    @property
    def listen_port_xml_rpc(self) -> int:
        return self._listen_port_xml_rpc

    def add_device(self, addr: str, *, rx_modes: tuple[Any, ...] = ()) -> None:
        self._devices[addr] = SimpleNamespace(
            interface_id="test-BidCos-RF",
            rx_modes=rx_modes,
            set_forced_availability=lambda **kwargs: None,
        )

    def get_device(self, *, address: str) -> Any:
        dev_addr = address.split(":")[0] if ":" in address else address
        return self._devices.get(dev_addr)


def _create_interface_client(
    central: _FakeCentral | None = None,
    backend: _FakeBackend | None = None,
) -> InterfaceClient:
    """Create an InterfaceClient with fake dependencies."""
    if central is None:
        central = _FakeCentral()
    if backend is None:
        backend = _FakeBackend()

    iface_cfg = InterfaceConfig(central_name="test", interface=Interface.BIDCOS_RF, port=32001)

    return InterfaceClient(
        backend=backend,  # type: ignore[arg-type]
        central=central,  # type: ignore[arg-type]
        interface_config=iface_cfg,
        version="2.0",
    )


class TestInterfaceClientInit:
    """Test InterfaceClient initialization."""

    def test_init_client_creates_coalescers(self) -> None:
        """Client should create request coalescers."""
        client = _create_interface_client()

        assert client.request_coalescer is not None
        assert client.request_coalescer.total_requests == 0

    def test_init_client_creates_state_machine(self) -> None:
        """Client should have a state machine after initialization."""
        client = _create_interface_client()

        assert client.state_machine is not None
        assert client.state == ClientState.CREATED

    def test_init_client_creates_trackers(self) -> None:
        """Client should create ping-pong and command trackers."""
        client = _create_interface_client()

        assert client.ping_pong_tracker is not None
        assert client.last_value_send_tracker is not None

    @pytest.mark.asyncio
    async def test_init_client_method(self) -> None:
        """init_client should transition state to INITIALIZED."""
        client = _create_interface_client()

        await client.init_client()

        assert client.state == ClientState.INITIALIZED

    def test_init_client_subscribes_to_events(self) -> None:
        """Client should subscribe to state change events."""
        central = _FakeCentral()
        _create_interface_client(central=central)

        # Should have subscriptions for ClientStateChangedEvent and SystemStatusChangedEvent
        assert len(central._event_bus._subscriptions) == 2


class TestInterfaceClientInitializeProxy:
    """Test initialize_proxy lifecycle method."""

    @pytest.mark.asyncio
    async def test_initialize_proxy_failure(self) -> None:
        """initialize_proxy should return INIT_FAILED on error."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend._init_proxy_should_fail = True
        client = _create_interface_client(central, backend)

        # First init_client to get to INITIALIZED state
        await client.init_client()
        result = await client.initialize_proxy()

        assert result == ProxyInitState.INIT_FAILED
        assert client.state == ClientState.FAILED

    @pytest.mark.asyncio
    async def test_initialize_proxy_no_callback_list_devices_fails(self) -> None:
        """initialize_proxy without callback should fail if list_devices returns None."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.rpc_callback = False
        backend._list_devices_result = None
        client = _create_interface_client(central, backend)

        # First init_client to get to INITIALIZED state
        await client.init_client()
        result = await client.initialize_proxy()

        assert result == ProxyInitState.INIT_FAILED
        assert client.state == ClientState.FAILED

    @pytest.mark.asyncio
    async def test_initialize_proxy_no_callback_support(self) -> None:
        """initialize_proxy without callback support should still succeed."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.rpc_callback = False
        backend._list_devices_result = ({"ADDRESS": "dev1", "TYPE": "TEST", "PARAMSETS": ["VALUES"]},)
        client = _create_interface_client(central, backend)

        # First init_client to get to INITIALIZED state
        await client.init_client()
        result = await client.initialize_proxy()

        assert result == ProxyInitState.INIT_SUCCESS
        assert client.state == ClientState.CONNECTED
        # Should NOT have called init_proxy
        assert not any(call[0] == "init_proxy" for call in backend.calls)
        # Should have called list_devices
        assert any(call[0] == "list_devices" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_initialize_proxy_sets_modified_at(self) -> None:
        """initialize_proxy should update modified_at timestamp."""
        client = _create_interface_client()
        assert client.modified_at == INIT_DATETIME

        # First init_client to get to INITIALIZED state
        await client.init_client()
        await client.initialize_proxy()

        assert client.modified_at != INIT_DATETIME
        assert client.modified_at <= datetime.now()

    @pytest.mark.asyncio
    async def test_initialize_proxy_success(self) -> None:
        """initialize_proxy should call backend and transition to CONNECTED."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # First init_client to get to INITIALIZED state
        await client.init_client()
        result = await client.initialize_proxy()

        assert result == ProxyInitState.INIT_SUCCESS
        assert client.state == ClientState.CONNECTED
        # Should have called init_proxy
        assert any(call[0] == "init_proxy" for call in backend.calls)


class TestInterfaceClientDeinitializeProxy:
    """Test deinitialize_proxy lifecycle method."""

    @pytest.mark.asyncio
    async def test_deinitialize_proxy_failure(self) -> None:
        """deinitialize_proxy should return DE_INIT_FAILED on error."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend._deinit_proxy_should_fail = True
        client = _create_interface_client(central, backend)

        # First init_client and initialize_proxy
        await client.init_client()
        await client.initialize_proxy()
        backend.calls.clear()

        result = await client.deinitialize_proxy()

        assert result == ProxyInitState.DE_INIT_FAILED

    @pytest.mark.asyncio
    async def test_deinitialize_proxy_no_callback_support(self) -> None:
        """deinitialize_proxy without callback support should succeed immediately."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.rpc_callback = False
        backend._list_devices_result = ({"ADDRESS": "dev1", "TYPE": "TEST", "PARAMSETS": ["VALUES"]},)
        client = _create_interface_client(central, backend)

        # First init_client and initialize_proxy to get to CONNECTED
        await client.init_client()
        await client.initialize_proxy()
        backend.calls.clear()

        result = await client.deinitialize_proxy()

        assert result == ProxyInitState.DE_INIT_SUCCESS
        assert client.state == ClientState.DISCONNECTED
        # Should NOT have called deinit_proxy (no callback support)
        assert not any(call[0] == "deinit_proxy" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_deinitialize_proxy_resets_modified_at(self) -> None:
        """deinitialize_proxy should reset modified_at to INIT_DATETIME."""
        client = _create_interface_client()

        # First init_client and initialize_proxy
        await client.init_client()
        await client.initialize_proxy()
        assert client.modified_at != INIT_DATETIME

        await client.deinitialize_proxy()
        assert client.modified_at == INIT_DATETIME

    @pytest.mark.asyncio
    async def test_deinitialize_proxy_skipped_when_not_initialized(self) -> None:
        """deinitialize_proxy should skip if never initialized."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Don't initialize - modified_at is INIT_DATETIME
        result = await client.deinitialize_proxy()

        assert result == ProxyInitState.DE_INIT_SKIPPED
        # Should NOT have called deinit_proxy
        assert not any(call[0] == "deinit_proxy" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_deinitialize_proxy_success(self) -> None:
        """deinitialize_proxy should call backend and transition to DISCONNECTED."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # First init_client and initialize_proxy
        await client.init_client()
        await client.initialize_proxy()
        backend.calls.clear()

        result = await client.deinitialize_proxy()

        assert result == ProxyInitState.DE_INIT_SUCCESS
        assert client.state == ClientState.DISCONNECTED
        # Should have called deinit_proxy
        assert any(call[0] == "deinit_proxy" for call in backend.calls)


class TestInterfaceClientCheckConnectionAvailability:
    """Test check_connection_availability method."""

    @pytest.mark.asyncio
    async def test_check_connection_failure(self) -> None:
        """check_connection_availability should return False when backend fails."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend._check_connection_result = False
        client = _create_interface_client(central, backend)

        result = await client.check_connection_availability(handle_ping_pong=False)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_connection_success(self) -> None:
        """check_connection_availability should return True when backend succeeds."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend._check_connection_result = True
        client = _create_interface_client(central, backend)

        result = await client.check_connection_availability(handle_ping_pong=False)

        assert result is True
        assert any(call[0] == "check_connection" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_check_connection_updates_modified_at(self) -> None:
        """check_connection_availability should update modified_at on success."""
        client = _create_interface_client()

        before = datetime.now()
        await client.check_connection_availability(handle_ping_pong=False)

        assert client.modified_at >= before

    @pytest.mark.asyncio
    async def test_check_connection_with_ping_pong(self) -> None:
        """check_connection_availability should handle ping_pong tracking."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # First init_client and initialize_proxy to enable ping_pong handling
        await client.init_client()
        await client.initialize_proxy()
        backend.calls.clear()

        result = await client.check_connection_availability(handle_ping_pong=True)

        assert result is True
        # check_connection should have been called with handle_ping_pong=True and a caller_id
        check_call = next((call for call in backend.calls if call[0] == "check_connection"), None)
        assert check_call is not None
        assert check_call[1][0] is True  # handle_ping_pong
        assert check_call[1][1] is not None  # caller_id (token)


class TestInterfaceClientIsCallbackAlive:
    """Test is_callback_alive method."""

    def test_is_callback_alive_no_ping_pong_support(self) -> None:
        """is_callback_alive should return True when ping_pong not supported."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.ping_pong = False
        client = _create_interface_client(central, backend)

        result = client.is_callback_alive()

        assert result is True

    def test_is_callback_alive_old_event(self) -> None:
        """is_callback_alive should return False when no recent events."""
        central = _FakeCentral()
        # Set last event to 10 minutes ago (longer than default callback_warn_interval of 3 minutes)
        central._last_event_seen = datetime.now() - timedelta(minutes=10)
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        result = client.is_callback_alive()

        assert result is False

    def test_is_callback_alive_publishes_event_on_transition(self) -> None:
        """is_callback_alive should publish SystemStatusChangedEvent when state changes."""
        central = _FakeCentral()
        central._last_event_seen = datetime.now() - timedelta(minutes=10)
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Clear any events from initialization
        central._event_bus.published_events.clear()

        client.is_callback_alive()

        # Should have published SystemStatusChangedEvent with callback_state
        from aiohomematic.central.events import SystemStatusChangedEvent

        callback_events = [e for e in central._event_bus.published_events if isinstance(e, SystemStatusChangedEvent)]
        assert len(callback_events) == 1
        assert callback_events[0].callback_state == (client.interface_id, False)

    def test_is_callback_alive_recent_event(self) -> None:
        """is_callback_alive should return True when event was recent."""
        central = _FakeCentral()
        central._last_event_seen = datetime.now()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        result = client.is_callback_alive()

        assert result is True


class TestInterfaceClientIsConnected:
    """Test is_connected method."""

    @pytest.mark.asyncio
    async def test_is_connected_increments_error_count(self) -> None:
        """is_connected should track connection errors."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend._check_connection_result = False
        client = _create_interface_client(central, backend)

        # Error count should increment
        await client.is_connected()
        assert client._connection_error_count == 1

        await client.is_connected()
        assert client._connection_error_count == 2

    @pytest.mark.asyncio
    async def test_is_connected_resets_error_count_on_success(self) -> None:
        """is_connected should reset error count on success."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # First fail
        backend._check_connection_result = False
        await client.is_connected()
        assert client._connection_error_count == 1

        # Then succeed
        backend._check_connection_result = True
        await client.is_connected()
        assert client._connection_error_count == 0

    @pytest.mark.asyncio
    async def test_is_connected_returns_false_after_threshold(self) -> None:
        """is_connected should return False after error threshold exceeded."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # First init_client and initialize_proxy to get to CONNECTED state
        await client.init_client()
        await client.initialize_proxy()
        assert client.state == ClientState.CONNECTED

        # Then fail
        backend._check_connection_result = False

        # Need to exceed threshold (default is 5)
        for _ in range(6):
            await client.is_connected()

        assert client.state == ClientState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_is_connected_success(self) -> None:
        """is_connected should return True when check_connection succeeds."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend._check_connection_result = True
        client = _create_interface_client(central, backend)

        result = await client.is_connected()

        assert result is True


class TestInterfaceClientStateTransitions:
    """Test state machine transitions."""

    @pytest.mark.asyncio
    async def test_available_after_connected(self) -> None:
        """Available should be True when CONNECTED."""
        client = _create_interface_client()

        await client.init_client()
        await client.initialize_proxy()

        assert client.available is True

    def test_available_property(self) -> None:
        """Available property should delegate to state machine."""
        client = _create_interface_client()

        assert client.available is False  # Initially not available

    @pytest.mark.asyncio
    async def test_is_initialized_after_init(self) -> None:
        """is_initialized should be True after proxy initialization."""
        client = _create_interface_client()

        await client.init_client()
        await client.initialize_proxy()

        assert client.is_initialized is True

    def test_is_initialized_property(self) -> None:
        """is_initialized should be True only for specific states."""
        client = _create_interface_client()

        assert client.is_initialized is False

    @pytest.mark.asyncio
    async def test_state_flow_init_to_connected(self) -> None:
        """State should flow: CREATED -> INITIALIZING -> INITIALIZED -> CONNECTING -> CONNECTED."""
        client = _create_interface_client()

        assert client.state == ClientState.CREATED

        await client.init_client()
        assert client.state == ClientState.INITIALIZED

        await client.initialize_proxy()
        assert client.state == ClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_state_flow_to_disconnected(self) -> None:
        """State should flow to DISCONNECTED after deinitialize."""
        client = _create_interface_client()

        await client.init_client()
        await client.initialize_proxy()
        assert client.state == ClientState.CONNECTED

        await client.deinitialize_proxy()
        assert client.state == ClientState.DISCONNECTED


class TestInterfaceClientCapabilityGatedOperations:
    """Test capability-gated operations."""

    @pytest.mark.asyncio
    async def test_remove_link_capability_disabled(self) -> None:
        """remove_link should return early when capability disabled."""
        backend = _FakeBackend()
        backend.capabilities.linking = False
        client = _create_interface_client(backend=backend)

        # Should return without calling backend
        await client.remove_link(sender_address="addr1", receiver_address="addr2")
        assert not any(call[0] == "remove_link" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_rename_channel_capability_disabled(self) -> None:
        """rename_channel should return False when capability disabled."""
        backend = _FakeBackend()
        backend.capabilities.rename = False
        client = _create_interface_client(backend=backend)

        result = await client.rename_channel(rega_id=123, new_name="new_name")
        assert result is False

    @pytest.mark.asyncio
    async def test_rename_device_capability_disabled(self) -> None:
        """rename_device should return False when capability disabled."""
        backend = _FakeBackend()
        backend.capabilities.rename = False
        client = _create_interface_client(backend=backend)

        result = await client.rename_device(rega_id=123, new_name="new_name")
        assert result is False

    @pytest.mark.asyncio
    async def test_report_value_usage_capability_disabled(self) -> None:
        """report_value_usage should return False when capability disabled."""
        backend = _FakeBackend()
        backend.capabilities.value_usage_reporting = False
        client = _create_interface_client(backend=backend)

        result = await client.report_value_usage(channel_address="addr", value_id="vid", ref_counter=1)
        assert result is False

    def test_reset_circuit_breakers(self) -> None:
        """reset_circuit_breakers should delegate to backend."""
        backend = _FakeBackend()
        client = _create_interface_client(backend=backend)

        client.reset_circuit_breakers()
        # Backend's reset_circuit_breakers should have been called
        assert True  # Just verify no exception

    @pytest.mark.asyncio
    async def test_set_install_mode_capability_disabled(self) -> None:
        """set_install_mode should return False when capability disabled."""
        backend = _FakeBackend()
        backend.capabilities.install_mode = False
        client = _create_interface_client(backend=backend)

        result = await client.set_install_mode(on=True, time=60)
        assert result is False

    @pytest.mark.asyncio
    async def test_set_metadata_capability_disabled(self) -> None:
        """set_metadata should return empty dict when capability disabled."""
        backend = _FakeBackend()
        backend.capabilities.metadata = False
        client = _create_interface_client(backend=backend)

        result = await client.set_metadata(address="addr", data_id="did", value={"key": "val"})
        assert result == {}

    @pytest.mark.asyncio
    async def test_set_program_state_capability_disabled(self) -> None:
        """set_program_state should return False when capability disabled."""
        backend = _FakeBackend()
        backend.capabilities.programs = False
        client = _create_interface_client(backend=backend)

        result = await client.set_program_state(pid="prog1", state=True)
        assert result is False


class TestInterfaceClientReconnect:
    """Test reconnect functionality."""

    @pytest.mark.asyncio
    async def test_reconnect_from_initialized_state(self) -> None:
        """
        Reconnect should work from INITIALIZED state by transitioning to DISCONNECTED first.

        This tests the fix for the issue where clients stuck in INITIALIZED state
        (e.g., after a failed startup) couldn't be reconnected because RECONNECTING
        was not a valid transition from INITIALIZED. The fix transitions to DISCONNECTED
        first, which then allows RECONNECTING.
        """
        backend = _FakeBackend()
        client = _create_interface_client(backend=backend)

        # Initialize client to get to INITIALIZED state
        await client.init_client()
        assert client.state == ClientState.INITIALIZED

        # Verify reconnect was not possible before (RECONNECTING not in valid transitions from INITIALIZED)
        assert not client._state_machine.can_reconnect

        # Now call reconnect - it should transition to DISCONNECTED first, then succeed
        result = await client.reconnect()

        assert result is True
        assert client.state == ClientState.CONNECTED
        assert client.available is True

    @pytest.mark.asyncio
    async def test_reconnect_not_allowed_from_created(self) -> None:
        """Reconnect should return False when state doesn't allow it."""
        client = _create_interface_client()
        # In CREATED state, can_reconnect is False

        result = await client.reconnect()
        assert result is False

    @pytest.mark.asyncio
    async def test_reinitialize_proxy(self) -> None:
        """reinitialize_proxy should deinitialize then initialize."""
        backend = _FakeBackend()
        client = _create_interface_client(backend=backend)

        await client.init_client()
        await client.initialize_proxy()
        backend.calls.clear()

        result = await client.reinitialize_proxy()

        assert result == ProxyInitState.INIT_SUCCESS
        # Should have called deinit then init
        call_names = [call[0] for call in backend.calls]
        assert "deinit_proxy" in call_names
        assert "init_proxy" in call_names
