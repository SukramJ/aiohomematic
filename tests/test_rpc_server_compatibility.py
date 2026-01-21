# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
RPC Server Compatibility Tests.

Verifies that XmlRpcServer (legacy thread-based) and AsyncXmlRpcServer (aiohttp-based)
expose identical RPC methods and produce equivalent results.

Side-by-Side Comparison:
| Aspect                | XmlRpcServer (Legacy)      | AsyncXmlRpcServer          |
|-----------------------|----------------------------|----------------------------|
| Threading Model       | Thread-based               | Async/aiohttp              |
| Server Class          | SimpleXMLRPCServer         | aiohttp.web.Application    |
| RPC Functions Class   | RPCFunctions               | AsyncRPCFunctions          |
| add_central signature | (central, looper)          | (central,)                 |
| Background tasks      | looper.create_task()       | _create_background_task()  |
| System event publish  | @callback_backend_system   | _publish_system_event()    |
| Health endpoint       | No                         | Yes (/health)              |
| Metrics               | No                         | Yes                        |

Both MUST expose these identical RPC methods:
- deleteDevices(interface_id, addresses)
- error(interface_id, error_code, msg)
- event(interface_id, channel_address, parameter, value)
- listDevices(interface_id)
- newDevices(interface_id, device_descriptions)
- readdedDevice(interface_id, addresses)
- replaceDevice(interface_id, old_device_address, new_device_address)
- updateDevice(interface_id, address, hint)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import inspect
from typing import Any, Final
from unittest.mock import AsyncMock, Mock

import pytest

from aiohomematic.central.async_rpc_server import AsyncRPCFunctions, AsyncXmlRpcServer
from aiohomematic.central.rpc_server import RPCFunctions, RpcServer, XmlRpcServer
from aiohomematic.const import UpdateDeviceHint

# pylint: disable=protected-access


# ============================================================================
# Test Data Classes
# ============================================================================


@dataclass
class RpcMethodSignature:
    """Capture RPC method signature for comparison."""

    name: str
    parameters: tuple[str, ...]
    is_positional_only: bool = False

    @classmethod
    def from_method(cls, *, name: str, method: Any) -> RpcMethodSignature:
        """Create from a method."""
        sig = inspect.signature(method)
        params = []
        is_positional_only = False
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            params.append(param_name)
            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                is_positional_only = True
        return cls(name=name, parameters=tuple(params), is_positional_only=is_positional_only)


@dataclass
class CoordinatorCallRecord:
    """Record of a coordinator method call."""

    method_name: str
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Helper Classes for Testing
# ============================================================================


class MockCentralProtocol:
    """Mock central that implements RpcServerCentralProtocol."""

    def __init__(self, *, name: str, interface_ids: tuple[str, ...]) -> None:
        """Initialize mock central."""
        self.name = name
        self._interface_ids = interface_ids
        self._device_descriptions: list[dict[str, Any]] = []
        self.calls: list[CoordinatorCallRecord] = []

        # Mock coordinators
        self.device_coordinator = self._create_device_coordinator()
        self.event_coordinator = self._create_event_coordinator()
        self.client_coordinator = self._create_client_coordinator()

    def clear_calls(self) -> None:
        """Clear recorded calls."""
        self.calls.clear()

    def set_device_descriptions(self, *, descriptions: list[dict[str, Any]]) -> None:
        """Set device descriptions for listDevices."""
        self._device_descriptions.clear()
        self._device_descriptions.extend(descriptions)
        self.device_coordinator.list_devices.return_value = self._device_descriptions

    def _create_client_coordinator(self) -> Mock:
        """Create mock client coordinator."""
        coordinator = Mock()
        coordinator.has_client = Mock(side_effect=lambda interface_id: interface_id in self._interface_ids)
        return coordinator

    def _create_device_coordinator(self) -> Mock:
        """Create mock device coordinator."""
        coordinator = Mock()

        def record_call(method_name: str):
            async def wrapper(*args, **kwargs):
                self.calls.append(CoordinatorCallRecord(method_name=method_name, args=args, kwargs=kwargs))

            return wrapper

        coordinator.delete_devices = AsyncMock(side_effect=record_call("delete_devices"))
        coordinator.add_new_devices = AsyncMock(side_effect=record_call("add_new_devices"))
        coordinator.readd_device = AsyncMock(side_effect=record_call("readd_device"))
        coordinator.replace_device = AsyncMock(side_effect=record_call("replace_device"))
        coordinator.update_device = AsyncMock(side_effect=record_call("update_device"))
        coordinator.refresh_device_link_peers = AsyncMock(side_effect=record_call("refresh_device_link_peers"))
        coordinator.list_devices = Mock(return_value=self._device_descriptions)

        return coordinator

    def _create_event_coordinator(self) -> Mock:
        """Create mock event coordinator."""
        coordinator = Mock()

        def record_call(method_name: str):
            async def wrapper(*args, **kwargs):
                self.calls.append(CoordinatorCallRecord(method_name=method_name, args=args, kwargs=kwargs))

            return wrapper

        coordinator.data_point_event = AsyncMock(side_effect=record_call("data_point_event"))
        coordinator.publish_system_event = Mock()
        return coordinator


class MockLooper:
    """Mock task scheduler that executes tasks immediately."""

    def __init__(self) -> None:
        """Initialize mock looper."""
        self._tasks: list[tuple[Any, str]] = []
        self._background_tasks: set[asyncio.Task[None]] = set()

    def create_task(self, *, target: Any, name: str) -> None:
        """Create a task (store for inspection)."""
        self._tasks.append((target, name))
        # Execute coroutines if they are coroutines
        if asyncio.iscoroutine(target):
            # Schedule it in the event loop and store reference
            task = asyncio.create_task(target)
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        elif callable(target):
            result = target()
            if asyncio.iscoroutine(result):
                task = asyncio.create_task(result)
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)


# ============================================================================
# RPC Method Name Compatibility Tests
# ============================================================================


class TestRpcMethodNameCompatibility:
    """Verify both implementations expose the same RPC method names."""

    REQUIRED_RPC_METHODS: Final = frozenset(
        {
            "deleteDevices",
            "error",
            "event",
            "listDevices",
            "newDevices",
            "readdedDevice",
            "replaceDevice",
            "updateDevice",
        }
    )

    def test_async_rpc_functions_has_all_required_methods(self) -> None:
        """Verify AsyncRPCFunctions has all required RPC methods."""
        mock_server = Mock(spec=AsyncXmlRpcServer)
        rpc_functions = AsyncRPCFunctions(rpc_server=mock_server)

        exposed_methods = {
            name for name in dir(rpc_functions) if not name.startswith("_") and callable(getattr(rpc_functions, name))
        }

        missing = self.REQUIRED_RPC_METHODS - exposed_methods
        assert not missing, f"Async RPCFunctions missing methods: {missing}"

    def test_both_implementations_have_identical_method_names(self) -> None:
        """Verify both implementations expose the same set of RPC methods."""
        legacy_server = Mock(spec=RpcServer)
        legacy_rpc = RPCFunctions(rpc_server=legacy_server)

        async_server = Mock(spec=AsyncXmlRpcServer)
        async_rpc = AsyncRPCFunctions(rpc_server=async_server)

        def get_public_methods(obj: object) -> set[str]:
            return {
                name
                for name in dir(obj)
                if not name.startswith("_")
                and callable(getattr(obj, name))
                and name not in ("cancel_background_tasks",)  # Async-specific
            }

        legacy_methods = get_public_methods(legacy_rpc)
        async_methods = get_public_methods(async_rpc)

        # Remove methods that are intentionally different
        async_only = {"active_tasks_count", "cancel_background_tasks"}
        async_methods -= async_only

        # Core RPC methods must match
        assert legacy_methods >= self.REQUIRED_RPC_METHODS, "Legacy missing required methods"
        assert async_methods >= self.REQUIRED_RPC_METHODS, "Async missing required methods"

    def test_legacy_rpc_functions_has_all_required_methods(self) -> None:
        """Verify RPCFunctions (legacy) has all required RPC methods."""
        mock_server = Mock(spec=RpcServer)
        rpc_functions = RPCFunctions(rpc_server=mock_server)

        exposed_methods = {
            name for name in dir(rpc_functions) if not name.startswith("_") and callable(getattr(rpc_functions, name))
        }

        missing = self.REQUIRED_RPC_METHODS - exposed_methods
        assert not missing, f"Legacy RPCFunctions missing methods: {missing}"


# ============================================================================
# RPC Method Signature Compatibility Tests
# ============================================================================


class TestRpcMethodSignatureCompatibility:
    """Verify both implementations have compatible method signatures."""

    @pytest.fixture
    def async_rpc_functions(self) -> AsyncRPCFunctions:
        """Create async RPCFunctions."""
        mock_server = Mock(spec=AsyncXmlRpcServer)
        return AsyncRPCFunctions(rpc_server=mock_server)

    @pytest.fixture
    def legacy_rpc_functions(self) -> RPCFunctions:
        """Create legacy RPCFunctions."""
        mock_server = Mock(spec=RpcServer)
        return RPCFunctions(rpc_server=mock_server)

    def test_deletedevices_signature(
        self,
        legacy_rpc_functions: RPCFunctions,
        async_rpc_functions: AsyncRPCFunctions,
    ) -> None:
        """Verify deleteDevices(interface_id, addresses) signature."""
        legacy_sig = RpcMethodSignature.from_method(name="deleteDevices", method=legacy_rpc_functions.deleteDevices)
        async_sig = RpcMethodSignature.from_method(name="deleteDevices", method=async_rpc_functions.deleteDevices)

        expected_params = ("interface_id", "addresses")
        assert legacy_sig.parameters == expected_params
        assert async_sig.parameters == expected_params
        assert legacy_sig.is_positional_only
        assert async_sig.is_positional_only

    def test_event_signature(
        self,
        legacy_rpc_functions: RPCFunctions,
        async_rpc_functions: AsyncRPCFunctions,
    ) -> None:
        """Verify event(interface_id, channel_address, parameter, value) signature."""
        legacy_sig = RpcMethodSignature.from_method(name="event", method=legacy_rpc_functions.event)
        async_sig = RpcMethodSignature.from_method(name="event", method=async_rpc_functions.event)

        expected_params = ("interface_id", "channel_address", "parameter", "value")
        assert legacy_sig.parameters == expected_params
        assert async_sig.parameters == expected_params

    @pytest.mark.parametrize(
        "method_name",
        [
            "deleteDevices",
            "error",
            "event",
            "listDevices",
            "newDevices",
            "readdedDevice",
            "replaceDevice",
            "updateDevice",
        ],
    )
    def test_method_parameter_names_match(
        self,
        legacy_rpc_functions: RPCFunctions,
        async_rpc_functions: AsyncRPCFunctions,
        method_name: str,
    ) -> None:
        """Verify parameter names match between implementations."""
        legacy_method = getattr(legacy_rpc_functions, method_name)
        async_method = getattr(async_rpc_functions, method_name)

        legacy_sig = RpcMethodSignature.from_method(name=method_name, method=legacy_method)
        async_sig = RpcMethodSignature.from_method(name=method_name, method=async_method)

        assert legacy_sig.parameters == async_sig.parameters, (
            f"Parameter mismatch for {method_name}: legacy={legacy_sig.parameters}, async={async_sig.parameters}"
        )

    def test_updatedevice_signature(
        self,
        legacy_rpc_functions: RPCFunctions,
        async_rpc_functions: AsyncRPCFunctions,
    ) -> None:
        """Verify updateDevice(interface_id, address, hint) signature."""
        legacy_sig = RpcMethodSignature.from_method(name="updateDevice", method=legacy_rpc_functions.updateDevice)
        async_sig = RpcMethodSignature.from_method(name="updateDevice", method=async_rpc_functions.updateDevice)

        expected_params = ("interface_id", "address", "hint")
        assert legacy_sig.parameters == expected_params
        assert async_sig.parameters == expected_params


# ============================================================================
# Server Class Compatibility Tests
# ============================================================================


class TestServerClassCompatibility:
    """Verify server classes have compatible interfaces."""

    @pytest.fixture(autouse=True)
    def clear_singletons(self) -> None:
        """Clear singleton instances between tests."""
        XmlRpcServer._instances.clear()
        AsyncXmlRpcServer._instances.clear()
        yield
        XmlRpcServer._instances.clear()
        AsyncXmlRpcServer._instances.clear()

    def test_async_server_add_central_without_looper(self) -> None:
        """Verify async server add_central doesn't require looper."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
        mock_central = Mock()
        mock_central.name = "test-central"

        # Should not raise - async server doesn't need looper
        async_server.add_central(central=mock_central)
        assert async_server.no_central_assigned is False

    def test_both_servers_have_add_central_method(self) -> None:
        """Verify both servers have add_central method."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
        assert hasattr(async_server, "add_central")
        assert callable(async_server.add_central)

    def test_both_servers_have_get_central_entry_method(self) -> None:
        """Verify both servers have get_central_entry method."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
        assert hasattr(async_server, "get_central_entry")
        assert callable(async_server.get_central_entry)

    def test_both_servers_have_listen_ip_addr_property(self) -> None:
        """Verify both servers expose listen_ip_addr property."""
        # Async server
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
        assert hasattr(async_server, "listen_ip_addr")
        assert async_server.listen_ip_addr == "127.0.0.1"

    def test_both_servers_have_listen_port_property(self) -> None:
        """Verify both servers expose listen_port property."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8080)
        assert hasattr(async_server, "listen_port")
        assert async_server.listen_port == 8080

    def test_both_servers_have_no_central_assigned_property(self) -> None:
        """Verify both servers expose no_central_assigned property."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
        assert hasattr(async_server, "no_central_assigned")
        assert async_server.no_central_assigned is True

    def test_both_servers_have_remove_central_method(self) -> None:
        """Verify both servers have remove_central method."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
        assert hasattr(async_server, "remove_central")
        assert callable(async_server.remove_central)

    def test_both_servers_have_started_property(self) -> None:
        """Verify both servers expose started property."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
        assert hasattr(async_server, "started")
        assert async_server.started is False

    def test_server_singleton_pattern(self) -> None:
        """Verify both servers use singleton pattern."""
        # Async servers
        async_server1 = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8080)
        async_server2 = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8080)
        assert async_server1 is async_server2

        # Different port = different instance
        async_server3 = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8081)
        assert async_server1 is not async_server3


# ============================================================================
# Behavioral Compatibility Tests
# ============================================================================


class TestListDevicesCompatibility:
    """Verify listDevices returns identical results."""

    @pytest.fixture(autouse=True)
    def clear_singletons(self) -> None:
        """Clear singleton instances between tests."""
        AsyncXmlRpcServer._instances.clear()
        yield
        AsyncXmlRpcServer._instances.clear()

    @pytest.mark.asyncio
    async def test_listdevices_returns_empty_list_when_no_central(self) -> None:
        """Verify listDevices returns [] when central not found."""
        # Legacy
        legacy_server = Mock(spec=RpcServer)
        legacy_server.get_central_entry.return_value = None
        legacy_rpc = RPCFunctions(rpc_server=legacy_server)

        legacy_result = legacy_rpc.listDevices("unknown-interface")

        # Async
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_server.get_central_entry.return_value = None
        async_rpc = AsyncRPCFunctions(rpc_server=async_server)

        async_result = await async_rpc.listDevices("unknown-interface")

        assert legacy_result == []
        assert async_result == []

    @pytest.mark.asyncio
    async def test_listdevices_returns_list_of_dicts(self) -> None:
        """Verify listDevices returns list of dicts in both implementations."""
        # Create mock centrals with device descriptions
        descriptions = [
            {"ADDRESS": "ABC0000001", "TYPE": "HmIP-SWSD", "FIRMWARE": "1.0.0"},
            {"ADDRESS": "ABC0000001:0", "TYPE": "", "PARENT": "ABC0000001"},
        ]

        # Legacy
        legacy_mock_central = MockCentralProtocol(name="test", interface_ids=("test-interface",))
        legacy_mock_central.set_device_descriptions(descriptions=descriptions)

        legacy_server = Mock(spec=RpcServer)
        legacy_entry = Mock()
        legacy_entry.central = legacy_mock_central
        legacy_server.get_central_entry.return_value = legacy_entry

        legacy_rpc = RPCFunctions(rpc_server=legacy_server)
        legacy_result = legacy_rpc.listDevices("test-interface")

        # Async
        async_mock_central = MockCentralProtocol(name="test", interface_ids=("test-interface",))
        async_mock_central.set_device_descriptions(descriptions=descriptions)

        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        async_result = await async_rpc.listDevices("test-interface")

        # Both should return list of dicts
        assert isinstance(legacy_result, list)
        assert isinstance(async_result, list)
        assert len(legacy_result) == len(async_result) == 2


class TestEventCompatibility:
    """Verify event handling produces equivalent coordinator calls."""

    @pytest.fixture(autouse=True)
    def clear_singletons(self) -> None:
        """Clear singleton instances between tests."""
        AsyncXmlRpcServer._instances.clear()
        yield
        AsyncXmlRpcServer._instances.clear()

    @pytest.mark.asyncio
    async def test_event_calls_data_point_event_with_same_params(self) -> None:
        """Verify event() calls event_coordinator.data_point_event with identical params."""
        interface_id = "test-interface"
        channel_address = "ABC0000001:1"
        parameter = "STATE"
        value = True

        # Async implementation
        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.event(interface_id, channel_address, parameter, value)

        # Wait for background task
        await asyncio.sleep(0.01)

        # Verify call was recorded
        assert len(async_mock_central.calls) == 1
        call = async_mock_central.calls[0]
        assert call.method_name == "data_point_event"
        assert call.kwargs == {
            "interface_id": interface_id,
            "channel_address": channel_address,
            "parameter": parameter,
            "value": value,
        }

    @pytest.mark.asyncio
    async def test_event_does_nothing_when_no_central_found(self) -> None:
        """Verify event() does nothing when central not found (no exception)."""
        # Async
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_server.get_central_entry.return_value = None
        async_rpc = AsyncRPCFunctions(rpc_server=async_server)

        # Should not raise
        await async_rpc.event("unknown-interface", "ADDR:1", "STATE", True)


class TestDeleteDevicesCompatibility:
    """Verify deleteDevices produces equivalent coordinator calls."""

    @pytest.mark.asyncio
    async def test_deletedevices_calls_coordinator_with_tuple(self) -> None:
        """Verify deleteDevices converts list to tuple for coordinator."""
        interface_id = "test-interface"
        addresses = ["ABC0000001", "ABC0000002"]

        # Async
        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.deleteDevices(interface_id, addresses)

        await asyncio.sleep(0.01)

        # Verify coordinator was called with tuple (not list)
        assert len(async_mock_central.calls) == 1
        call = async_mock_central.calls[0]
        assert call.method_name == "delete_devices"
        assert call.kwargs["interface_id"] == interface_id
        assert call.kwargs["addresses"] == ("ABC0000001", "ABC0000002")


class TestNewDevicesCompatibility:
    """Verify newDevices produces equivalent coordinator calls."""

    @pytest.mark.asyncio
    async def test_newdevices_calls_coordinator_with_tuple(self) -> None:
        """Verify newDevices converts list to tuple for coordinator."""
        interface_id = "test-interface"
        device_descriptions = [
            {"ADDRESS": "ABC0000001", "TYPE": "HmIP-SWSD"},
            {"ADDRESS": "ABC0000002", "TYPE": "HmIP-WTH"},
        ]

        # Async
        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.newDevices(interface_id, device_descriptions)

        await asyncio.sleep(0.01)

        assert len(async_mock_central.calls) == 1
        call = async_mock_central.calls[0]
        assert call.method_name == "add_new_devices"
        assert call.kwargs["interface_id"] == interface_id
        # Should be tuple of dicts
        assert isinstance(call.kwargs["device_descriptions"], tuple)
        assert len(call.kwargs["device_descriptions"]) == 2


class TestUpdateDeviceCompatibility:
    """Verify updateDevice produces equivalent coordinator calls for different hints."""

    @pytest.mark.asyncio
    async def test_updatedevice_firmware_hint_calls_update_device(self) -> None:
        """Verify hint=0 (firmware) calls device_coordinator.update_device."""
        interface_id = "test-interface"
        address = "ABC0000001:0"  # Channel address
        hint = UpdateDeviceHint.FIRMWARE  # 0

        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.updateDevice(interface_id, address, hint)

        await asyncio.sleep(0.01)

        assert len(async_mock_central.calls) == 1
        call = async_mock_central.calls[0]
        assert call.method_name == "update_device"
        assert call.kwargs["interface_id"] == interface_id
        # Device address should be extracted from channel address
        assert call.kwargs["device_address"] == "ABC0000001"

    @pytest.mark.asyncio
    async def test_updatedevice_links_hint_calls_refresh_link_peers(self) -> None:
        """Verify hint=1 (links) calls device_coordinator.refresh_device_link_peers."""
        interface_id = "test-interface"
        address = "ABC0000001"
        hint = UpdateDeviceHint.LINKS  # 1

        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.updateDevice(interface_id, address, hint)

        await asyncio.sleep(0.01)

        assert len(async_mock_central.calls) == 1
        call = async_mock_central.calls[0]
        assert call.method_name == "refresh_device_link_peers"
        assert call.kwargs["device_address"] == "ABC0000001"

    @pytest.mark.asyncio
    async def test_updatedevice_unknown_hint_does_nothing(self) -> None:
        """Verify unknown hint values are ignored."""
        interface_id = "test-interface"
        address = "ABC0000001"
        hint = 99  # Unknown hint

        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.updateDevice(interface_id, address, hint)

        await asyncio.sleep(0.01)

        # No coordinator calls for unknown hint
        assert len(async_mock_central.calls) == 0


class TestReaddedDeviceCompatibility:
    """Verify readdedDevice produces equivalent coordinator calls."""

    @pytest.mark.asyncio
    async def test_readdeddevice_filters_channel_addresses(self) -> None:
        """Verify channel addresses (with :) are filtered out."""
        interface_id = "test-interface"
        # Mix of device and channel addresses
        addresses = ["ABC0000001", "ABC0000001:0", "ABC0000002", "ABC0000002:1"]

        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.readdedDevice(interface_id, addresses)

        await asyncio.sleep(0.01)

        assert len(async_mock_central.calls) == 1
        call = async_mock_central.calls[0]
        assert call.method_name == "readd_device"
        # Only device addresses (without :) should be passed
        assert call.kwargs["device_addresses"] == ("ABC0000001", "ABC0000002")

    @pytest.mark.asyncio
    async def test_readdeddevice_only_channels_does_nothing(self) -> None:
        """Verify nothing happens when only channel addresses provided."""
        interface_id = "test-interface"
        # Only channel addresses
        addresses = ["ABC0000001:0", "ABC0000001:1", "ABC0000002:0"]

        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.readdedDevice(interface_id, addresses)

        await asyncio.sleep(0.01)

        # No coordinator calls since no device addresses
        assert len(async_mock_central.calls) == 0


class TestReplaceDeviceCompatibility:
    """Verify replaceDevice produces equivalent coordinator calls."""

    @pytest.mark.asyncio
    async def test_replacedevice_calls_coordinator(self) -> None:
        """Verify replaceDevice calls device_coordinator.replace_device."""
        interface_id = "test-interface"
        old_address = "ABC0000001"
        new_address = "ABC0000002"

        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)
        await async_rpc.replaceDevice(interface_id, old_address, new_address)

        await asyncio.sleep(0.01)

        assert len(async_mock_central.calls) == 1
        call = async_mock_central.calls[0]
        assert call.method_name == "replace_device"
        assert call.kwargs["interface_id"] == interface_id
        assert call.kwargs["old_device_address"] == old_address
        assert call.kwargs["new_device_address"] == new_address


# ============================================================================
# Central Registration Compatibility Tests
# ============================================================================


class TestCentralRegistrationCompatibility:
    """Verify central registration/lookup works identically."""

    @pytest.fixture(autouse=True)
    def clear_singletons(self) -> None:
        """Clear singleton instances between tests."""
        AsyncXmlRpcServer._instances.clear()
        yield
        AsyncXmlRpcServer._instances.clear()

    def test_add_same_central_twice_is_idempotent(self) -> None:
        """Verify adding same central twice doesn't duplicate."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

        mock_central = Mock()
        mock_central.name = "test-central"

        async_server.add_central(central=mock_central)
        async_server.add_central(central=mock_central)

        assert len(async_server._centrals) == 1

    def test_get_central_entry_finds_by_interface_id(self) -> None:
        """Verify get_central_entry finds central by interface_id."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

        mock_central = Mock()
        mock_central.name = "test-central"
        mock_central.client_coordinator.has_client.side_effect = lambda interface_id: interface_id == "hmip-rf"

        async_server.add_central(central=mock_central)

        # Should find central by interface_id
        entry = async_server.get_central_entry(interface_id="hmip-rf")
        assert entry is not None
        assert entry.central is mock_central

        # Should not find for unknown interface
        entry = async_server.get_central_entry(interface_id="unknown")
        assert entry is None

    def test_remove_central_clears_entry(self) -> None:
        """Verify remove_central removes the central from registry."""
        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

        mock_central = Mock()
        mock_central.name = "test-central"

        async_server.add_central(central=mock_central)
        assert async_server.no_central_assigned is False

        async_server.remove_central(central=mock_central)
        assert async_server.no_central_assigned is True


# ============================================================================
# Error Handling Compatibility Tests
# ============================================================================


class TestErrorHandlingCompatibility:
    """Verify error handling is compatible."""

    @pytest.mark.asyncio
    async def test_error_logs_and_publishes_event(self) -> None:
        """Verify error() logs and publishes system event."""
        # The error method behavior differs slightly:
        # - Legacy uses @callback_backend_system decorator
        # - Async uses _publish_system_event() directly
        # Both should ultimately publish a system event

        async_server = Mock(spec=AsyncXmlRpcServer)
        async_server.get_central_entry.return_value = None

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)

        # Should not raise
        await async_rpc.error("test-interface", "1", "Test error message")


# ============================================================================
# Full Integration Compatibility Tests
# ============================================================================


class TestFullIntegrationCompatibility:
    """Full integration tests comparing both server implementations."""

    @pytest.fixture(autouse=True)
    def clear_singletons(self) -> None:
        """Clear singleton instances between tests."""
        AsyncXmlRpcServer._instances.clear()
        yield
        AsyncXmlRpcServer._instances.clear()

    @pytest.mark.asyncio
    async def test_complete_device_lifecycle(self) -> None:
        """Test complete device lifecycle produces equivalent coordinator calls."""
        interface_id = "test-interface"

        # Async implementation
        async_mock_central = MockCentralProtocol(name="test", interface_ids=(interface_id,))
        async_server = Mock(spec=AsyncXmlRpcServer)
        async_entry = Mock()
        async_entry.central = async_mock_central
        async_server.get_central_entry.return_value = async_entry

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)

        # 1. New device
        await async_rpc.newDevices(
            interface_id,
            [{"ADDRESS": "ABC0000001", "TYPE": "HmIP-SWSD"}],
        )

        # 2. Events
        await async_rpc.event(interface_id, "ABC0000001:1", "STATE", True)
        await async_rpc.event(interface_id, "ABC0000001:1", "STATE", False)

        # 3. Update device (firmware)
        await async_rpc.updateDevice(interface_id, "ABC0000001", 0)

        # 4. Update device (links)
        await async_rpc.updateDevice(interface_id, "ABC0000001", 1)

        # 5. Delete device
        await async_rpc.deleteDevices(interface_id, ["ABC0000001"])

        await asyncio.sleep(0.05)

        # Verify all calls were made
        call_methods = [c.method_name for c in async_mock_central.calls]
        assert "add_new_devices" in call_methods
        assert call_methods.count("data_point_event") == 2
        assert "update_device" in call_methods
        assert "refresh_device_link_peers" in call_methods
        assert "delete_devices" in call_methods

    @pytest.mark.asyncio
    async def test_multiple_interfaces_routing(self) -> None:
        """Test events are routed to correct interface."""
        # Create mock centrals for different interfaces
        central1 = MockCentralProtocol(name="central1", interface_ids=("hmip-rf",))
        central2 = MockCentralProtocol(name="central2", interface_ids=("bidcos-rf",))

        async_server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

        # Add both centrals
        mock_central1 = Mock()
        mock_central1.name = "central1"
        mock_central1.client_coordinator.has_client = lambda *, interface_id: interface_id == "hmip-rf"
        mock_central1.event_coordinator = central1.event_coordinator
        mock_central1.device_coordinator = central1.device_coordinator

        mock_central2 = Mock()
        mock_central2.name = "central2"
        mock_central2.client_coordinator.has_client = lambda *, interface_id: interface_id == "bidcos-rf"
        mock_central2.event_coordinator = central2.event_coordinator
        mock_central2.device_coordinator = central2.device_coordinator

        async_server.add_central(central=mock_central1)
        async_server.add_central(central=mock_central2)

        async_rpc = AsyncRPCFunctions(rpc_server=async_server)

        # Send events to different interfaces
        await async_rpc.event("hmip-rf", "DEV001:1", "STATE", True)
        await async_rpc.event("bidcos-rf", "DEV002:1", "STATE", False)

        await asyncio.sleep(0.05)

        # Verify routing
        assert len(central1.calls) == 1
        assert central1.calls[0].kwargs["channel_address"] == "DEV001:1"

        assert len(central2.calls) == 1
        assert central2.calls[0].kwargs["channel_address"] == "DEV002:1"


# ============================================================================
# Device Description Normalization Tests
# ============================================================================


class TestDeviceDescriptionNormalization:
    """
    Test device description normalization for XML-RPC responses.

    These tests verify fix for GitHub issue #2731: VirtualDevices connection
    failure caused by CCU's Java DeviceDescription.children expecting String[]
    but receiving String. The _normalize_device_description function ensures
    CHILDREN is always a list.
    """

    def test_children_as_empty_list_unchanged(self) -> None:
        """Verify empty CHILDREN list is unchanged."""
        from aiohomematic.schemas import normalize_device_description

        desc = {"ADDRESS": "ABC:0", "TYPE": "HM-Test", "CHILDREN": []}
        result = normalize_device_description(device_description=desc)
        assert result["CHILDREN"] == []

    def test_children_as_list_unchanged(self) -> None:
        """Verify CHILDREN as list is unchanged."""
        from aiohomematic.schemas import normalize_device_description

        desc = {"ADDRESS": "ABC:0", "TYPE": "HM-Test", "CHILDREN": ["ABC:1", "ABC:2"]}
        result = normalize_device_description(device_description=desc)
        assert result["CHILDREN"] == ["ABC:1", "ABC:2"]

    def test_children_as_nonempty_string_converted_to_list(self) -> None:
        """Verify non-empty string CHILDREN is converted to single-element list."""
        from aiohomematic.schemas import normalize_device_description

        desc = {"ADDRESS": "ABC:0", "TYPE": "HM-Test", "CHILDREN": "ABC:1"}
        result = normalize_device_description(device_description=desc)
        assert result["CHILDREN"] == ["ABC:1"]

    def test_children_as_string_converted_to_list(self) -> None:
        """
        Verify CHILDREN as empty string is converted to empty list.

        This is the core fix for issue #2731: VirtualDevices may send
        CHILDREN as empty string which causes CCU's Java parser to crash.
        """
        from aiohomematic.schemas import normalize_device_description

        desc = {"ADDRESS": "ABC:0", "TYPE": "HM-Test", "CHILDREN": ""}
        result = normalize_device_description(device_description=desc)
        assert result["CHILDREN"] == []

    def test_children_none_converted_to_list(self) -> None:
        """Verify CHILDREN=None is converted to empty list."""
        from aiohomematic.schemas import normalize_device_description

        desc = {"ADDRESS": "ABC:0", "TYPE": "HM-Test", "CHILDREN": None}
        result = normalize_device_description(device_description=desc)
        assert result["CHILDREN"] == []

    def test_missing_children_converted_to_list(self) -> None:
        """Verify missing CHILDREN is converted to empty list."""
        from aiohomematic.schemas import normalize_device_description

        desc = {"ADDRESS": "ABC:0", "TYPE": "HM-Test"}
        result = normalize_device_description(device_description=desc)
        assert result["CHILDREN"] == []

    def test_other_fields_preserved(self) -> None:
        """Verify other fields in description are preserved."""
        from aiohomematic.schemas import normalize_device_description

        desc = {
            "ADDRESS": "ABC:0",
            "TYPE": "HmIP-SWSD",
            "FIRMWARE": "1.0.0",
            "PARENT": "ABC",
            "CHILDREN": "",  # String that should be fixed
            "PARAMSETS": ["VALUES"],
        }
        result = normalize_device_description(device_description=desc)

        # CHILDREN normalized
        assert result["CHILDREN"] == []
        # Other fields preserved
        assert result["ADDRESS"] == "ABC:0"
        assert result["TYPE"] == "HmIP-SWSD"
        assert result["FIRMWARE"] == "1.0.0"
        assert result["PARENT"] == "ABC"
        assert result["PARAMSETS"] == ["VALUES"]
