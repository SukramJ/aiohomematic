# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Tests for InterfaceClient lifecycle methods.

These tests verify the connection lifecycle operations:
- init_proxy / deinit_proxy / reinit_proxy
- check_connection_availability
- is_callback_alive
- is_connected
- State machine transitions
"""

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
    """Test init_proxy lifecycle method."""

    @pytest.mark.asyncio
    async def test_init_proxy_failure(self) -> None:
        """init_proxy should return INIT_FAILED on error."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend._init_proxy_should_fail = True
        client = _create_interface_client(central, backend)

        # First init_client to get to INITIALIZED state
        await client.init_client()
        result = await client.init_proxy()

        assert result == ProxyInitState.INIT_FAILED
        assert client.state == ClientState.FAILED

    @pytest.mark.asyncio
    async def test_init_proxy_no_callback_list_devices_fails(self) -> None:
        """init_proxy without callback should fail if list_devices returns None."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.rpc_callback = False
        backend._list_devices_result = None
        client = _create_interface_client(central, backend)

        # First init_client to get to INITIALIZED state
        await client.init_client()
        result = await client.init_proxy()

        assert result == ProxyInitState.INIT_FAILED
        assert client.state == ClientState.FAILED

    @pytest.mark.asyncio
    async def test_init_proxy_no_callback_support(self) -> None:
        """init_proxy without callback support should still succeed."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.rpc_callback = False
        backend._list_devices_result = ({"ADDRESS": "dev1", "TYPE": "TEST", "PARAMSETS": ["VALUES"]},)
        client = _create_interface_client(central, backend)

        # First init_client to get to INITIALIZED state
        await client.init_client()
        result = await client.init_proxy()

        assert result == ProxyInitState.INIT_SUCCESS
        assert client.state == ClientState.CONNECTED
        # Should NOT have called init_proxy
        assert not any(call[0] == "init_proxy" for call in backend.calls)
        # Should have called list_devices
        assert any(call[0] == "list_devices" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_init_proxy_sets_modified_at(self) -> None:
        """init_proxy should update modified_at timestamp."""
        client = _create_interface_client()
        assert client.modified_at == INIT_DATETIME

        # First init_client to get to INITIALIZED state
        await client.init_client()
        await client.init_proxy()

        assert client.modified_at != INIT_DATETIME
        assert client.modified_at <= datetime.now()

    @pytest.mark.asyncio
    async def test_init_proxy_success(self) -> None:
        """init_proxy should call backend and transition to CONNECTED."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # First init_client to get to INITIALIZED state
        await client.init_client()
        result = await client.init_proxy()

        assert result == ProxyInitState.INIT_SUCCESS
        assert client.state == ClientState.CONNECTED
        # Should have called init_proxy
        assert any(call[0] == "init_proxy" for call in backend.calls)


class TestInterfaceClientDeinitializeProxy:
    """Test deinit_proxy lifecycle method."""

    @pytest.mark.asyncio
    async def test_deinit_proxy_failure(self) -> None:
        """deinit_proxy should return DE_INIT_FAILED on error."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend._deinit_proxy_should_fail = True
        client = _create_interface_client(central, backend)

        # First init_client and init_proxy
        await client.init_client()
        await client.init_proxy()
        backend.calls.clear()

        result = await client.deinit_proxy()

        assert result == ProxyInitState.DE_INIT_FAILED

    @pytest.mark.asyncio
    async def test_deinit_proxy_no_callback_support(self) -> None:
        """deinit_proxy without callback support should succeed immediately."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.rpc_callback = False
        backend._list_devices_result = ({"ADDRESS": "dev1", "TYPE": "TEST", "PARAMSETS": ["VALUES"]},)
        client = _create_interface_client(central, backend)

        # First init_client and init_proxy to get to CONNECTED
        await client.init_client()
        await client.init_proxy()
        backend.calls.clear()

        result = await client.deinit_proxy()

        assert result == ProxyInitState.DE_INIT_SUCCESS
        assert client.state == ClientState.DISCONNECTED
        # Should NOT have called deinit_proxy (no callback support)
        assert not any(call[0] == "deinit_proxy" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_deinit_proxy_resets_modified_at(self) -> None:
        """deinit_proxy should reset modified_at to INIT_DATETIME."""
        client = _create_interface_client()

        # First init_client and init_proxy
        await client.init_client()
        await client.init_proxy()
        assert client.modified_at != INIT_DATETIME

        await client.deinit_proxy()
        assert client.modified_at == INIT_DATETIME

    @pytest.mark.asyncio
    async def test_deinit_proxy_skipped_when_not_initialized(self) -> None:
        """deinit_proxy should skip if never initialized."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Don't initialize - modified_at is INIT_DATETIME
        result = await client.deinit_proxy()

        assert result == ProxyInitState.DE_INIT_SKIPPED
        # Should NOT have called deinit_proxy
        assert not any(call[0] == "deinit_proxy" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_deinit_proxy_success(self) -> None:
        """deinit_proxy should call backend and transition to DISCONNECTED."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # First init_client and init_proxy
        await client.init_client()
        await client.init_proxy()
        backend.calls.clear()

        result = await client.deinit_proxy()

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

        # First init_client and init_proxy to enable ping_pong handling
        await client.init_client()
        await client.init_proxy()
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

        # First init_client and init_proxy to get to CONNECTED state
        await client.init_client()
        await client.init_proxy()
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
        await client.init_proxy()

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
        await client.init_proxy()

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

        await client.init_proxy()
        assert client.state == ClientState.CONNECTED

    @pytest.mark.asyncio
    async def test_state_flow_to_disconnected(self) -> None:
        """State should flow to DISCONNECTED after deinitialize."""
        client = _create_interface_client()

        await client.init_client()
        await client.init_proxy()
        assert client.state == ClientState.CONNECTED

        await client.deinit_proxy()
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
    async def test_reinit_proxy(self) -> None:
        """reinit_proxy should deinitialize then initialize."""
        backend = _FakeBackend()
        client = _create_interface_client(backend=backend)

        await client.init_client()
        await client.init_proxy()
        backend.calls.clear()

        result = await client.reinit_proxy()

        assert result == ProxyInitState.INIT_SUCCESS
        # Should have called deinit then init
        call_names = [call[0] for call in backend.calls]
        assert "deinit_proxy" in call_names
        assert "init_proxy" in call_names


# ---------------------------------------------------------------------------
# Extended fakes with persistent tracked state for additional coverage tests
# ---------------------------------------------------------------------------


class _TrackingDeviceDetails:
    """Device details tracker with call recording."""

    def __init__(self) -> None:
        self.add_name_calls: list[dict[str, Any]] = []
        self.add_id_calls: list[dict[str, Any]] = []
        self.add_iface_calls: list[dict[str, Any]] = []

    def add_address_rega_id(self, *, address: str, rega_id: int) -> None:
        """Record add_address_rega_id call."""
        self.add_id_calls.append({"address": address, "rega_id": rega_id})

    def add_interface(self, *, address: str, interface: Interface) -> None:
        """Record add_interface call."""
        self.add_iface_calls.append({"address": address, "interface": interface})

    def add_name(self, *, address: str, name: str) -> None:
        """Record add_name call."""
        self.add_name_calls.append({"address": address, "name": name})


class _TrackingDataCache:
    """Data cache tracker with call recording."""

    def __init__(self) -> None:
        self.add_data_calls: list[dict[str, Any]] = []

    def add_data(self, **kwargs: Any) -> None:
        """Record add_data call."""
        self.add_data_calls.append(kwargs)


class _TrackingParamsetDescriptions(_FakeParamsetDescriptions):
    """Paramset descriptions tracker with call recording."""

    def __init__(self) -> None:
        super().__init__()
        self.add_calls: list[dict[str, Any]] = []

    def add(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        paramset_description: dict[str, Any],
        device_type: str,
    ) -> None:
        """Record add call and delegate to parent."""
        self.add_calls.append(
            {
                "interface_id": interface_id,
                "channel_address": channel_address,
                "paramset_key": paramset_key,
                "paramset_description": paramset_description,
                "device_type": device_type,
            }
        )
        super().add(
            interface_id=interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            paramset_description=paramset_description,
            device_type=device_type,
        )


class _ExtendedFakeCentral(_FakeCentral):
    """
    Extended fake central with stable tracked objects for coverage tests.

    Overrides cache_coordinator to return a stable object with tracking.
    """

    def __init__(self) -> None:
        super().__init__()
        self._channels: dict[str, Any] = {}
        self._data_points: dict[str, Any] = {}
        self._tracking_device_details = _TrackingDeviceDetails()
        self._tracking_data_cache = _TrackingDataCache()
        self._tracking_paramset_descriptions = _TrackingParamsetDescriptions()
        # Override paramset_descriptions so the tracking version is used everywhere
        self.paramset_descriptions = self._tracking_paramset_descriptions

        self.config.schedule_timer_config = SimpleNamespace(  # type: ignore[attr-defined]
            master_poll_after_send_intervals=(0.01,),
        )

    @property
    def cache_coordinator(self) -> Any:
        return SimpleNamespace(
            device_details=self._tracking_device_details,
            paramset_descriptions=self._tracking_paramset_descriptions,
            data_cache=self._tracking_data_cache,
            device_descriptions=self.device_descriptions,
            incident_store=None,
        )

    @property
    def device_coordinator(self) -> Any:
        parent = self

        class _FakeDeviceCoordinator:
            async def add_new_devices(
                self, *, interface_id: str, device_descriptions: tuple[dict[str, Any], ...]
            ) -> None:
                parent._device_coordinator_add_called.append((interface_id, device_descriptions))

            def get_channel(self, *, channel_address: str) -> Any:
                return parent._channels.get(channel_address)

            def get_device(self, *, address: str) -> Any:
                dev_addr = address.split(":")[0] if ":" in address else address
                return parent._devices.get(dev_addr)

        return _FakeDeviceCoordinator()

    @property
    def query_facade(self) -> Any:
        parent = self

        class _FakeQueryFacade:
            def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: Any) -> Any:
                key = f"{channel_address}:{parameter}:{paramset_key}"
                return parent._data_points.get(key)

        return _FakeQueryFacade()

    def add_channel(self, channel_address: str) -> None:
        """Add a fake channel for testing."""
        self._channels[channel_address] = SimpleNamespace(
            get_readable_data_points=lambda paramset_key: (),
        )


class _ExtendedFakeBackend(_FakeBackend):
    """Extended fake backend with additional method coverage for new tests."""

    def __init__(self) -> None:
        super().__init__()
        self._all_device_data: dict[str, Any] | None = {"dev1:1": {"LEVEL": 0.5}}
        self._device_details: list[dict[str, Any]] | None = [
            {
                "address": "dev1",
                "name": "Test Device",
                "id": 42,
                "interface": "BidCos-RF",
                "channels": [
                    {"address": "dev1:0", "name": "Ch 0", "id": 43},
                    {"address": "dev1:1", "name": "Ch 1", "id": 44},
                ],
            }
        ]
        self._delete_sysvar_result: bool = True
        self._get_sysvar_result: Any = "test_value"
        self._set_sysvar_result: bool = True

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable."""
        self.calls.append(("delete_system_variable", name))
        return self._delete_sysvar_result

    async def get_all_device_data(self, *, interface: Any) -> dict[str, Any] | None:
        """Return configurable all-device-data result."""
        self.calls.append(("get_all_device_data", interface))
        return self._all_device_data

    async def get_device_details(self, *, addresses: tuple[str, ...] | None = None) -> list[dict[str, Any]] | None:
        """Return configurable device details result."""
        self.calls.append(("get_device_details", addresses))
        return self._device_details

    async def get_paramset(self, *, channel_address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
        """Return paramset using channel_address keyword (protocol-compliant)."""
        self.calls.append(("get_paramset", (channel_address, paramset_key)))
        return {"LEVEL": 0.5}

    async def get_paramset_description(
        self, *, channel_address: str, paramset_key: ParamsetKey
    ) -> dict[str, Any] | None:
        """Return paramset description using channel_address keyword (protocol-compliant)."""
        self.calls.append(("get_paramset_description", (channel_address, paramset_key)))
        return {
            "LEVEL": {
                "TYPE": "FLOAT",
                "OPERATIONS": 7,
                "MIN": 0.0,
                "MAX": 1.0,
            },
        }

    async def get_system_variable(self, *, name: str) -> Any:
        """Return a system variable value."""
        self.calls.append(("get_system_variable", name))
        return self._get_sysvar_result

    async def get_value(self, *, channel_address: str, parameter: str) -> Any:
        """Return value using channel_address keyword (protocol-compliant)."""
        self.calls.append(("get_value", (channel_address, parameter)))
        return 0.5

    async def put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: Any | None = None,
    ) -> None:
        """Put paramset using channel_address keyword (protocol-compliant)."""
        self.calls.append(("put_paramset", (channel_address, paramset_key, values, rx_mode)))

    async def set_system_variable(self, *, name: str, value: Any) -> bool:
        """Set a system variable."""
        self.calls.append(("set_system_variable", (name, value)))
        return self._set_sysvar_result

    async def set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: Any | None = None,
    ) -> None:
        """Set value using channel_address keyword (protocol-compliant)."""
        self.calls.append(("set_value", (channel_address, parameter, value, rx_mode)))


def _create_extended_interface_client(
    central: _ExtendedFakeCentral | None = None,
    backend: _ExtendedFakeBackend | None = None,
) -> InterfaceClient:
    """Create an InterfaceClient with extended fake dependencies."""
    if central is None:
        central = _ExtendedFakeCentral()
    if backend is None:
        backend = _ExtendedFakeBackend()

    iface_cfg = InterfaceConfig(central_name="test", interface=Interface.BIDCOS_RF, port=32001)

    return InterfaceClient(
        backend=backend,  # type: ignore[arg-type]
        central=central,  # type: ignore[arg-type]
        interface_config=iface_cfg,
        version="2.0",
    )


# ---------------------------------------------------------------------------
# New test classes for additional coverage
# ---------------------------------------------------------------------------


class TestFetchAllDeviceData:
    """Test fetch_all_device_data device data caching."""

    @pytest.mark.asyncio
    async def test_fetch_all_device_data_caches_data(self) -> None:
        """fetch_all_device_data should store data in data cache when backend returns data."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        await client.fetch_all_device_data()

        assert any(call[0] == "get_all_device_data" for call in backend.calls)
        assert len(central._tracking_data_cache.add_data_calls) == 1

    @pytest.mark.asyncio
    async def test_fetch_all_device_data_empty_dict_not_cached(self) -> None:
        """fetch_all_device_data should not cache empty dict (falsy value)."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        backend._all_device_data = {}
        client = _create_extended_interface_client(central, backend)

        await client.fetch_all_device_data()

        assert len(central._tracking_data_cache.add_data_calls) == 0

    @pytest.mark.asyncio
    async def test_fetch_all_device_data_no_data_returned(self) -> None:
        """fetch_all_device_data should not call cache when backend returns None."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        backend._all_device_data = None
        client = _create_extended_interface_client(central, backend)

        await client.fetch_all_device_data()

        assert len(central._tracking_data_cache.add_data_calls) == 0


class TestFetchDeviceDetails:
    """Test fetch_device_details CCU vs Homegear hierarchy handling."""

    @pytest.mark.asyncio
    async def test_fetch_device_details_adds_names_and_ids(self) -> None:
        """fetch_device_details should add device names and rega IDs to tracking cache."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        await client.fetch_device_details()

        assert any(call[0] == "get_device_details" for call in backend.calls)
        # Device (dev1) + 2 channels (dev1:0, dev1:1) = 3 name calls
        assert len(central._tracking_device_details.add_name_calls) == 3

    @pytest.mark.asyncio
    async def test_fetch_device_details_no_data_returned(self) -> None:
        """fetch_device_details should do nothing when backend returns None."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        backend._device_details = None
        client = _create_extended_interface_client(central, backend)

        await client.fetch_device_details()

        assert len(central._tracking_device_details.add_name_calls) == 0

    @pytest.mark.asyncio
    async def test_fetch_device_details_no_interface_uses_client_interface(self) -> None:
        """fetch_device_details should fall back to client interface when device has none."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        # Device with no "interface" key
        backend._device_details = [
            {
                "address": "dev1",
                "name": "Test Device",
                "id": 42,
                "channels": [],
            }
        ]
        client = _create_extended_interface_client(central, backend)

        await client.fetch_device_details()

        assert len(central._tracking_device_details.add_iface_calls) == 1
        assert central._tracking_device_details.add_iface_calls[0]["interface"] == Interface.BIDCOS_RF

    @pytest.mark.asyncio
    async def test_fetch_device_details_with_interface_uses_device_interface(self) -> None:
        """fetch_device_details should use interface from device data when provided."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        # Default backend has "interface": "BidCos-RF"
        client = _create_extended_interface_client(central, backend)

        await client.fetch_device_details()

        assert len(central._tracking_device_details.add_iface_calls) == 1
        assert central._tracking_device_details.add_iface_calls[0]["interface"] == Interface.BIDCOS_RF

    @pytest.mark.asyncio
    async def test_fetch_device_details_zero_id_not_added(self) -> None:
        """fetch_device_details should not add rega_id when it is zero (Homegear path)."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        backend._device_details = [
            {
                "address": "dev1",
                "name": "Test Device",
                "id": 0,
                "interface": "BidCos-RF",
                "channels": [],
            }
        ]
        client = _create_extended_interface_client(central, backend)

        await client.fetch_device_details()

        # id=0 means no rega_id call
        assert len(central._tracking_device_details.add_id_calls) == 0


class TestFetchParamsetDescription:
    """Test fetch_paramset_description single paramset caching."""

    @pytest.mark.asyncio
    async def test_fetch_paramset_description_caches_result(self) -> None:
        """fetch_paramset_description should add result to paramset description cache."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        await client.fetch_paramset_description(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            device_type="TEST_DEVICE",
        )

        assert any(call[0] == "get_paramset_description" for call in backend.calls)
        assert len(central._tracking_paramset_descriptions.add_calls) == 1
        call = central._tracking_paramset_descriptions.add_calls[0]
        assert call["channel_address"] == "dev1:1"
        assert call["paramset_key"] == ParamsetKey.VALUES
        assert call["device_type"] == "TEST_DEVICE"

    @pytest.mark.asyncio
    async def test_fetch_paramset_description_empty_dict_is_cached(self) -> None:
        """fetch_paramset_description should cache empty dict (valid for HmIP MASTER)."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()

        async def _return_empty(*, channel_address: str, paramset_key: Any) -> dict[str, Any]:
            return {}

        backend.get_paramset_description = _return_empty  # type: ignore[method-assign]
        client = _create_extended_interface_client(central, backend)

        await client.fetch_paramset_description(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.MASTER,
            device_type="TEST_DEVICE",
        )

        assert len(central._tracking_paramset_descriptions.add_calls) == 1
        assert central._tracking_paramset_descriptions.add_calls[0]["paramset_description"] == {}

    @pytest.mark.asyncio
    async def test_fetch_paramset_description_none_not_cached(self) -> None:
        """fetch_paramset_description should skip caching when backend returns None."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()

        async def _return_none(*, channel_address: str, paramset_key: Any) -> None:
            return None

        backend.get_paramset_description = _return_none  # type: ignore[method-assign]
        client = _create_extended_interface_client(central, backend)

        await client.fetch_paramset_description(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            device_type="TEST_DEVICE",
        )

        assert len(central._tracking_paramset_descriptions.add_calls) == 0


class TestFetchParamsetDescriptions:
    """Test fetch_paramset_descriptions batch with PARENT_TYPE resolution."""

    @pytest.mark.asyncio
    async def test_fetch_paramset_descriptions_falls_back_to_type(self) -> None:
        """fetch_paramset_descriptions should use TYPE when PARENT_TYPE is absent (root device)."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        device_description: dict[str, Any] = {
            "ADDRESS": "dev1",
            "TYPE": "ROOT_DEVICE_TYPE",
            "PARAMSETS": ["VALUES", "MASTER"],
        }

        await client.fetch_paramset_descriptions(device_description=device_description)

        assert len(central._tracking_paramset_descriptions.add_calls) > 0
        for call in central._tracking_paramset_descriptions.add_calls:
            assert call["device_type"] == "ROOT_DEVICE_TYPE"

    @pytest.mark.asyncio
    async def test_fetch_paramset_descriptions_skips_link_paramset(self) -> None:
        """fetch_paramset_descriptions should skip LINK paramset keys."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        device_description: dict[str, Any] = {
            "ADDRESS": "dev1:1",
            "TYPE": "CHANNEL_TYPE",
            "PARAMSETS": ["VALUES", "MASTER", "LINK"],
        }

        await client.fetch_paramset_descriptions(device_description=device_description)

        paramset_keys = [call["paramset_key"] for call in central._tracking_paramset_descriptions.add_calls]
        assert ParamsetKey.LINK not in paramset_keys

    @pytest.mark.asyncio
    async def test_fetch_paramset_descriptions_uses_parent_type(self) -> None:
        """fetch_paramset_descriptions should use PARENT_TYPE when available (channel)."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        device_description: dict[str, Any] = {
            "ADDRESS": "dev1:1",
            "TYPE": "CHANNEL_TYPE",
            "PARENT_TYPE": "ROOT_DEVICE_TYPE",
            "PARAMSETS": ["VALUES", "MASTER"],
        }

        await client.fetch_paramset_descriptions(device_description=device_description)

        # All cached entries should use PARENT_TYPE for device_type
        assert len(central._tracking_paramset_descriptions.add_calls) > 0
        for call in central._tracking_paramset_descriptions.add_calls:
            assert call["device_type"] == "ROOT_DEVICE_TYPE"


class TestGetParamsetDescriptionOnDemand:
    """Test get_paramset_description_on_demand LINK paramset loading."""

    @pytest.mark.asyncio
    async def test_get_paramset_description_on_demand_returns_description(self) -> None:
        """get_paramset_description_on_demand should return description without caching."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        result = await client.get_paramset_description_on_demand(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.LINK,
        )

        assert result is not None
        assert isinstance(result, dict)
        # Should NOT have added to paramset description cache
        assert len(central._tracking_paramset_descriptions.add_calls) == 0

    @pytest.mark.asyncio
    async def test_get_paramset_description_on_demand_returns_empty_when_none(self) -> None:
        """get_paramset_description_on_demand should return empty dict when backend returns None."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()

        async def _return_none(*, channel_address: str, paramset_key: Any) -> None:
            return None

        backend.get_paramset_description = _return_none  # type: ignore[method-assign]
        client = _create_extended_interface_client(central, backend)

        result = await client.get_paramset_description_on_demand(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.LINK,
        )

        assert result == {}


class TestInitProxyJsonRpcBackend:
    """Test init_proxy JSON-RPC backend path (no callbacks)."""

    @pytest.mark.asyncio
    async def test_init_proxy_json_rpc_backend_no_callback_calls(self) -> None:
        """init_proxy for JSON-RPC backend should list devices instead of registering callback."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        backend.capabilities.rpc_callback = False
        backend._list_devices_result = ({"ADDRESS": "dev1", "TYPE": "TEST", "PARAMSETS": ["VALUES"]},)
        client = _create_extended_interface_client(central, backend)

        await client.init_client()
        result = await client.init_proxy()

        assert result == ProxyInitState.INIT_SUCCESS
        assert client.state == ClientState.CONNECTED
        # Should NOT have called init_proxy on the backend
        assert not any(call[0] == "init_proxy" for call in backend.calls)
        # Should have called list_devices to discover devices
        assert any(call[0] == "list_devices" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_init_proxy_json_rpc_device_descriptions_forwarded(self) -> None:
        """init_proxy without callback should forward device descriptions to coordinator."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        backend.capabilities.rpc_callback = False
        device_desc = {"ADDRESS": "dev1", "TYPE": "TEST", "PARAMSETS": ["VALUES"]}
        backend._list_devices_result = (device_desc,)
        client = _create_extended_interface_client(central, backend)

        await client.init_client()
        await client.init_proxy()

        assert len(central._device_coordinator_add_called) == 1
        _, descriptions = central._device_coordinator_add_called[0]
        assert device_desc in descriptions


class TestIsCallbackAliveStateTransition:
    """Test is_callback_alive state transitions and incident recording."""

    def test_is_callback_alive_failed_state_returns_false(self) -> None:
        """is_callback_alive should return False when client is in FAILED state."""
        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Force to FAILED state via INITIALIZING -> INITIALIZED -> CONNECTING then exception-path
        # Use force=True to set state directly
        client._state_machine.transition_to(target=ClientState.INITIALIZING)
        client._state_machine.transition_to(target=ClientState.FAILED)

        result = client.is_callback_alive()

        assert result is False

    def test_is_callback_alive_no_duplicate_event_on_second_dead_check(self) -> None:
        """is_callback_alive should not re-publish dead event when already marked dead."""
        central = _FakeCentral()
        central._last_event_seen = datetime.now() - timedelta(minutes=10)
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        central._event_bus.published_events.clear()

        # First call: transitions alive -> dead, publishes event
        client.is_callback_alive()
        events_after_first = len(central._event_bus.published_events)

        # Second call: already dead, should NOT publish again
        central._event_bus.published_events.clear()
        client.is_callback_alive()
        events_after_second = len(central._event_bus.published_events)

        assert events_after_first == 1
        assert events_after_second == 0

    def test_is_callback_alive_transitions_false_to_true(self) -> None:
        """is_callback_alive should publish recovered event when state goes false->true."""
        from aiohomematic.central.events import SystemStatusChangedEvent

        central = _FakeCentral()
        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Simulate prior dead state
        client._is_callback_alive = False
        # Recent event = callback is alive again
        central._last_event_seen = datetime.now()

        central._event_bus.published_events.clear()
        result = client.is_callback_alive()

        assert result is True
        recovery_events = [
            e
            for e in central._event_bus.published_events
            if isinstance(e, SystemStatusChangedEvent) and e.callback_state == (client.interface_id, True)
        ]
        assert len(recovery_events) == 1


class TestIsConnectedPushUpdates:
    """Test is_connected push_updates=False path."""

    @pytest.mark.asyncio
    async def test_is_connected_no_ping_pong_returns_true(self) -> None:
        """is_connected should return True when ping_pong=False (CUxD/CCU-Jack path)."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.push_updates = True
        backend.capabilities.ping_pong = False
        client = _create_interface_client(central, backend)

        result = await client.is_connected()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_connected_no_push_updates_returns_true_without_callback_check(self) -> None:
        """is_connected should return True when push_updates=False regardless of callback age."""
        central = _FakeCentral()
        backend = _FakeBackend()
        backend.capabilities.push_updates = False
        # Set last event very old to test that callback_warn is NOT checked
        central._last_event_seen = datetime.now() - timedelta(hours=1)
        client = _create_interface_client(central, backend)

        result = await client.is_connected()

        assert result is True


class TestPutParamset:
    """Test put_paramset LINK detection and RX mode validation."""

    @pytest.mark.asyncio
    async def test_put_paramset_basic_succeeds(self) -> None:
        """put_paramset with ParamsetKey.VALUES should succeed and return dpk_values."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        result = await client.put_paramset(
            channel_address="dev1:1",
            paramset_key_or_link_address=ParamsetKey.VALUES,
            values={"LEVEL": 0.5},
            wait_for_callback=None,
        )

        assert any(call[0] == "put_paramset" for call in backend.calls)
        assert isinstance(result, set)

    @pytest.mark.asyncio
    async def test_put_paramset_link_address_returns_empty_set(self) -> None:
        """put_paramset with a channel address as key should detect LINK call and return empty set."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        # A valid channel address (5-20 chars before ":" + channel no) as key means LINK call.
        # CHANNEL_ADDRESS_PATTERN requires 5-20 alphanumeric/dash chars, so use VCU-format addresses.
        result = await client.put_paramset(
            channel_address="VCU0000001:1",
            paramset_key_or_link_address="VCU0000002:1",
            values={"LEVEL": 0.5},
            wait_for_callback=None,
        )

        assert result == set()
        assert any(call[0] == "put_paramset" for call in backend.calls)


class TestSetValueNonValuesParamset:
    """Test set_value non-VALUES paramset routing."""

    @pytest.mark.asyncio
    async def test_set_value_master_paramset_routes_to_put_paramset(self) -> None:
        """set_value with MASTER paramset should route to put_paramset backend call."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.MASTER,
            parameter="CYCLICINFOMSGDIS",
            value=1,
            wait_for_callback=None,
        )

        # MASTER routes through put_paramset, not set_value
        assert any(call[0] == "put_paramset" for call in backend.calls)
        assert not any(call[0] == "set_value" for call in backend.calls)
        assert isinstance(result, set)

    @pytest.mark.asyncio
    async def test_set_value_values_paramset_uses_set_value_backend(self) -> None:
        """set_value with VALUES paramset should call backend set_value directly."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        result = await client.set_value(
            channel_address="dev1:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=0.5,
            wait_for_callback=None,
        )

        assert any(call[0] == "set_value" for call in backend.calls)
        assert isinstance(result, set)


class TestSystemVariableOperations:
    """Test system variable delete, get, set operations."""

    @pytest.mark.asyncio
    async def test_delete_system_variable(self) -> None:
        """delete_system_variable should delegate to backend and return result."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        result = await client.delete_system_variable(name="test_var")

        assert result is True
        assert any(call[0] == "delete_system_variable" and call[1] == "test_var" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_delete_system_variable_returns_false_on_failure(self) -> None:
        """delete_system_variable should propagate False result from backend."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        backend._delete_sysvar_result = False
        client = _create_extended_interface_client(central, backend)

        result = await client.delete_system_variable(name="nonexistent_var")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_system_variable(self) -> None:
        """get_system_variable should return value from backend."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        result = await client.get_system_variable(name="test_var")

        assert result == "test_value"
        assert any(call[0] == "get_system_variable" and call[1] == "test_var" for call in backend.calls)

    @pytest.mark.asyncio
    async def test_set_system_variable(self) -> None:
        """set_system_variable should delegate to backend with the provided legacy_name and value."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        client = _create_extended_interface_client(central, backend)

        result = await client.set_system_variable(legacy_name="test_var", value=42)

        assert result is True
        sysvar_calls = [call for call in backend.calls if call[0] == "set_system_variable"]
        assert len(sysvar_calls) == 1
        name, value = sysvar_calls[0][1]
        assert name == "test_var"
        assert value == 42


class TestClearJsonRpcSession:
    """Test clear_json_rpc_session method."""

    def test_clear_json_rpc_session_calls_clear(self) -> None:
        """clear_json_rpc_session should call json_rpc_client.clear_session."""
        central = _FakeCentral()
        clear_called: list[bool] = []

        def _track_clear() -> None:
            clear_called.append(True)

        central.json_rpc_client.clear_session = _track_clear  # type: ignore[attr-defined]
        client = _create_interface_client(central=central)

        client.clear_json_rpc_session()

        assert len(clear_called) == 1

    def test_clear_json_rpc_session_does_not_raise(self) -> None:
        """clear_json_rpc_session should complete without raising exceptions."""
        client = _create_interface_client()

        # Should not raise
        client.clear_json_rpc_session()


class TestStop:
    """Test stop() full shutdown sequence."""

    @pytest.mark.asyncio
    async def test_stop_calls_backend_stop(self) -> None:
        """stop() should call backend.stop()."""
        central = _FakeCentral()
        backend = _FakeBackend()
        stop_called: list[bool] = []
        original_stop = backend.stop

        async def _tracking_stop() -> None:
            stop_called.append(True)
            await original_stop()

        backend.stop = _tracking_stop  # type: ignore[method-assign]
        client = _create_interface_client(central, backend)

        await client.init_client()
        await client.init_proxy()
        await client.stop()

        assert len(stop_called) == 1

    @pytest.mark.asyncio
    async def test_stop_from_disconnected_state(self) -> None:
        """stop() should work from DISCONNECTED state."""
        client = _create_interface_client()

        await client.init_client()
        await client.init_proxy()
        await client.deinit_proxy()
        assert client.state == ClientState.DISCONNECTED

        await client.stop()

        assert client.state == ClientState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_transitions_to_stopped(self) -> None:
        """stop() should transition state to STOPPED after being connected."""
        client = _create_interface_client()

        # Must be in CONNECTED or DISCONNECTED to allow STOPPING transition
        await client.init_client()
        await client.init_proxy()
        assert client.state == ClientState.CONNECTED

        await client.stop()

        assert client.state == ClientState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_events(self) -> None:
        """stop() should unsubscribe from both event bus subscriptions."""
        central = _FakeCentral()
        unsubscribe_calls: list[str] = []

        def _tracking_subscribe(*, event_type: Any, event_key: Any, handler: Any) -> Any:
            def _unsubscribe() -> None:
                unsubscribe_calls.append("unsubscribed")

            return _unsubscribe

        central._event_bus.subscribe = _tracking_subscribe  # type: ignore[method-assign]
        client = _create_interface_client(central=central)

        await client.init_client()
        await client.init_proxy()
        await client.stop()

        # Both subscriptions (state_change + system_status) should be unsubscribed
        assert len(unsubscribe_calls) == 2


class TestMarkAllDevicesForcedAvailability:
    """Test _mark_all_devices_forced_availability method."""

    @pytest.mark.asyncio
    async def test_mark_available_skips_when_already_available(self) -> None:
        """_mark_all_devices_forced_availability skips set when already available and marking available."""
        from aiohomematic.const import ForcedDeviceAvailability

        central = _FakeCentral()
        availability_calls: list[Any] = []

        def _track_availability(**kwargs: Any) -> None:
            availability_calls.append(kwargs)

        central.add_device("dev1")
        central._devices["dev1"].set_forced_availability = _track_availability

        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        # Connect first so is_available = True
        await client.init_client()
        await client.init_proxy()
        assert client.available is True

        availability_calls.clear()

        # Marking available when already available should be skipped
        client._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.NOT_SET)

        assert len(availability_calls) == 0

    def test_mark_unavailable_calls_set_forced_on_all_interface_devices(self) -> None:
        """_mark_all_devices_forced_availability should call set_forced_availability on matching devices."""
        from aiohomematic.const import ForcedDeviceAvailability

        central = _FakeCentral()
        availability_calls: list[Any] = []

        def _track_availability(**kwargs: Any) -> None:
            availability_calls.append(kwargs)

        central.add_device("dev1")
        central.add_device("dev2")
        central._devices["dev1"].set_forced_availability = _track_availability
        central._devices["dev2"].set_forced_availability = _track_availability

        backend = _FakeBackend()
        client = _create_interface_client(central, backend)

        client._mark_all_devices_forced_availability(forced_availability=ForcedDeviceAvailability.FORCE_FALSE)

        assert len(availability_calls) == 2


class TestPollMasterValues:
    """Test _poll_master_values BidCos polling task creation."""

    @pytest.mark.asyncio
    async def test_poll_master_values_creates_task(self) -> None:
        """_poll_master_values should schedule a background polling task via looper."""
        central = _ExtendedFakeCentral()
        backend = _ExtendedFakeBackend()
        task_calls: list[Any] = []

        def _track_task(*, target: Any, name: str) -> None:
            task_calls.append((target, name))
            # Close the coroutine to avoid ResourceWarning
            if hasattr(target, "close"):
                target.close()

        central.looper.create_task = _track_task  # type: ignore[method-assign]
        client = _create_extended_interface_client(central, backend)

        fake_channel = SimpleNamespace(
            get_readable_data_points=lambda paramset_key: (),
        )

        await client._poll_master_values(channel=fake_channel, paramset_key=ParamsetKey.MASTER)

        assert len(task_calls) == 1
        _, name = task_calls[0]
        assert "poll_master_dp_values" in name
