# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the async XML-RPC server."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import xmlrpc.client

import aiohttp
import pytest

from aiohomematic.central.async_rpc_server import (
    AsyncRPCFunctions,
    AsyncXmlRpcDispatcher,
    AsyncXmlRpcServer,
    XmlRpcProtocolError,
    create_async_xml_rpc_server,
)
from aiohomematic.const import IP_ANY_V4

# pylint: disable=protected-access


@pytest.fixture(autouse=True)
def clear_server_singleton():
    """Clear singleton instances between tests."""
    AsyncXmlRpcServer._instances.clear()
    yield
    AsyncXmlRpcServer._instances.clear()


# --- AsyncXmlRpcDispatcher Tests ---


def test_dispatcher_register_instance():
    """Test method registration from an instance."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def another_method(self) -> int:
            return 42

        async def public_method(self) -> str:
            return "result"

        async def _private_method(self) -> str:
            return "private"

    instance = TestMethods()
    dispatcher.register_instance(instance=instance)

    assert "public_method" in dispatcher._methods
    assert "another_method" in dispatcher._methods
    assert "_private_method" not in dispatcher._methods


def test_dispatcher_register_introspection_functions():
    """Test introspection method registration."""
    dispatcher = AsyncXmlRpcDispatcher()
    dispatcher.register_introspection_functions()

    assert "system.listMethods" in dispatcher._methods
    assert "system.methodHelp" in dispatcher._methods
    assert "system.methodSignature" in dispatcher._methods


@pytest.mark.asyncio
async def test_dispatcher_system_list_methods():
    """Test system.listMethods introspection."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def method_a(self) -> None:
            pass

        async def method_b(self) -> None:
            pass

    dispatcher.register_instance(instance=TestMethods())
    dispatcher.register_introspection_functions()

    methods = await dispatcher._system_list_methods()

    assert "method_a" in methods
    assert "method_b" in methods
    assert "system.listMethods" in methods


@pytest.mark.asyncio
async def test_dispatcher_system_method_help():
    """Test system.methodHelp introspection."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def documented_method(self) -> None:
            """Perform a documented action."""

        async def undocumented_method(self) -> None:
            pass

    dispatcher.register_instance(instance=TestMethods())
    dispatcher.register_introspection_functions()

    help_text = await dispatcher._system_method_help("documented_method")
    assert "Perform a documented action." in help_text

    no_help = await dispatcher._system_method_help("undocumented_method")
    assert no_help == ""

    missing_help = await dispatcher._system_method_help("nonexistent")
    assert missing_help == ""


@pytest.mark.asyncio
async def test_dispatcher_system_method_signature():
    """Test system.methodSignature introspection."""
    dispatcher = AsyncXmlRpcDispatcher()
    dispatcher.register_introspection_functions()

    result = await dispatcher._system_method_signature("any_method")
    assert result == "signatures not supported"


@pytest.mark.asyncio
async def test_dispatcher_dispatch_success():
    """Test successful method dispatch."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def add(self, a: int, b: int) -> int:
            return a + b

    dispatcher.register_instance(instance=TestMethods())

    xml_request = xmlrpc.client.dumps((5, 3), methodname="add")
    response_bytes = await dispatcher.dispatch(xml_data=xml_request.encode("utf-8"))

    response = xmlrpc.client.loads(response_bytes.decode("utf-8"))
    assert response[0][0] == 8


@pytest.mark.asyncio
async def test_dispatcher_dispatch_method_not_found():
    """Test dispatch with unknown method."""
    dispatcher = AsyncXmlRpcDispatcher()

    xml_request = xmlrpc.client.dumps((), methodname="unknown_method")
    response_bytes = await dispatcher.dispatch(xml_data=xml_request.encode("utf-8"))

    with pytest.raises(xmlrpc.client.Fault) as exc_info:
        xmlrpc.client.loads(response_bytes.decode("utf-8"))

    assert exc_info.value.faultCode == -32601
    assert "Method not found" in exc_info.value.faultString


@pytest.mark.asyncio
async def test_dispatcher_dispatch_method_exception():
    """Test dispatch when method raises exception."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def failing_method(self) -> None:
            raise ValueError("Test error")

    dispatcher.register_instance(instance=TestMethods())

    xml_request = xmlrpc.client.dumps((), methodname="failing_method")
    response_bytes = await dispatcher.dispatch(xml_data=xml_request.encode("utf-8"))

    with pytest.raises(xmlrpc.client.Fault) as exc_info:
        xmlrpc.client.loads(response_bytes.decode("utf-8"))

    assert exc_info.value.faultCode == -32603
    assert "Test error" in exc_info.value.faultString


@pytest.mark.asyncio
async def test_dispatcher_dispatch_invalid_xml():
    """Test dispatch with invalid XML."""
    dispatcher = AsyncXmlRpcDispatcher()

    with pytest.raises(XmlRpcProtocolError) as exc_info:
        await dispatcher.dispatch(xml_data=b"not valid xml")

    # Check for translated message or i18n key (in test environment)
    error_msg = str(exc_info.value)
    assert "Invalid XML" in error_msg or "invalid_xml" in error_msg


@pytest.mark.asyncio
async def test_dispatcher_dispatch_none_result_becomes_true():
    """Test that None result is converted to True for Homematic compatibility."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def void_method(self) -> None:
            pass

    dispatcher.register_instance(instance=TestMethods())

    xml_request = xmlrpc.client.dumps((), methodname="void_method")
    response_bytes = await dispatcher.dispatch(xml_data=xml_request.encode("utf-8"))

    response = xmlrpc.client.loads(response_bytes.decode("utf-8"))
    assert response[0][0] is True


@pytest.mark.asyncio
async def test_dispatcher_system_multicall():
    """Test system.multicall for batched method calls."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def add(self, a: int, b: int) -> int:
            return a + b

        async def multiply(self, a: int, b: int) -> int:
            return a * b

        async def void_method(self) -> None:
            pass

    dispatcher.register_instance(instance=TestMethods())
    dispatcher.register_introspection_functions()

    # Test multicall with multiple methods
    calls = [
        {"methodName": "add", "params": [2, 3]},
        {"methodName": "multiply", "params": [4, 5]},
        {"methodName": "void_method", "params": []},
    ]
    result = await dispatcher._system_multicall(calls)

    # Each result is wrapped in a list, None becomes True
    assert result == [[5], [20], [True]]


@pytest.mark.asyncio
async def test_dispatcher_system_multicall_with_unknown_method():
    """Test system.multicall handles unknown methods gracefully."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def known_method(self) -> str:
            return "ok"

    dispatcher.register_instance(instance=TestMethods())
    dispatcher.register_introspection_functions()

    calls = [
        {"methodName": "known_method", "params": []},
        {"methodName": "unknown_method", "params": []},
        {"methodName": "known_method", "params": []},
    ]
    result = await dispatcher._system_multicall(calls)

    assert result[0] == ["ok"]
    assert result[1]["faultCode"] == -32601
    assert "Method not found" in result[1]["faultString"]
    assert result[2] == ["ok"]


@pytest.mark.asyncio
async def test_dispatcher_system_multicall_with_exception():
    """Test system.multicall handles method exceptions gracefully."""
    dispatcher = AsyncXmlRpcDispatcher()

    class TestMethods:
        async def failing_method(self) -> None:
            raise ValueError("Test failure")

        async def ok_method(self) -> str:
            return "success"

    dispatcher.register_instance(instance=TestMethods())
    dispatcher.register_introspection_functions()

    calls = [
        {"methodName": "ok_method", "params": []},
        {"methodName": "failing_method", "params": []},
        {"methodName": "ok_method", "params": []},
    ]
    result = await dispatcher._system_multicall(calls)

    assert result[0] == ["success"]
    assert result[1]["faultCode"] == -32603
    assert "Test failure" in result[1]["faultString"]
    assert result[2] == ["success"]


# --- AsyncRPCFunctions Tests ---


def _create_mock_server():
    """Create mock server and RPC functions."""
    mock_server = MagicMock(spec=AsyncXmlRpcServer)
    rpc_functions = AsyncRPCFunctions(rpc_server=mock_server)
    return rpc_functions, mock_server


def _create_mock_central_entry():
    """Create a mock central entry."""
    mock_entry = MagicMock()
    mock_entry.central = MagicMock()
    mock_entry.central.device_coordinator = MagicMock()
    mock_entry.central.device_coordinator.delete_devices = AsyncMock()
    mock_entry.central.device_coordinator.add_new_devices = AsyncMock()
    mock_entry.central.device_coordinator.list_devices = MagicMock(return_value=[])
    mock_entry.central.event_coordinator = MagicMock()
    mock_entry.central.event_coordinator.data_point_event = AsyncMock()
    mock_entry.central.event_coordinator.publish_system_event = MagicMock()
    return mock_entry


@pytest.mark.asyncio
async def test_rpc_functions_delete_devices():
    """Test deleteDevices callback."""
    rpc_functions, mock_server = _create_mock_server()
    mock_entry = _create_mock_central_entry()
    mock_server.get_central_entry.return_value = mock_entry

    await rpc_functions.deleteDevices("test-interface", ["ADDR1", "ADDR2"])

    mock_entry.central.device_coordinator.delete_devices.assert_called_once_with(
        interface_id="test-interface",
        addresses=("ADDR1", "ADDR2"),
    )


@pytest.mark.asyncio
async def test_rpc_functions_delete_devices_no_central():
    """Test deleteDevices when no central is found."""
    rpc_functions, mock_server = _create_mock_server()
    mock_server.get_central_entry.return_value = None

    # Should not raise
    await rpc_functions.deleteDevices("unknown-interface", ["ADDR1"])


@pytest.mark.asyncio
async def test_rpc_functions_event():
    """Test event callback."""
    rpc_functions, mock_server = _create_mock_server()
    mock_entry = _create_mock_central_entry()
    mock_server.get_central_entry.return_value = mock_entry

    await rpc_functions.event("test-interface", "ADDR:1", "STATE", True)

    mock_entry.central.event_coordinator.data_point_event.assert_called_once_with(
        interface_id="test-interface",
        channel_address="ADDR:1",
        parameter="STATE",
        value=True,
    )


@pytest.mark.asyncio
async def test_rpc_functions_error():
    """Test error callback."""
    rpc_functions, _ = _create_mock_server()

    with patch("aiohomematic.central.async_rpc_server.hmcl") as mock_hmcl:
        mock_client = MagicMock()
        mock_client.central.event_coordinator.publish_system_event = MagicMock()
        mock_hmcl.get_client.return_value = mock_client

        await rpc_functions.error("test-interface", "1", "Test error message")

        mock_hmcl.get_client.assert_called_with(interface_id="test-interface")


@pytest.mark.asyncio
async def test_rpc_functions_list_devices():
    """Test listDevices callback."""
    rpc_functions, mock_server = _create_mock_server()
    mock_entry = _create_mock_central_entry()

    mock_descriptions = [
        MagicMock(__iter__=lambda s: iter([("ADDRESS", "ADDR1"), ("TYPE", "SWITCH")])),
        MagicMock(__iter__=lambda s: iter([("ADDRESS", "ADDR2"), ("TYPE", "DIMMER")])),
    ]
    mock_entry.central.device_coordinator.list_devices.return_value = mock_descriptions
    mock_server.get_central_entry.return_value = mock_entry

    result = await rpc_functions.listDevices("test-interface")

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_rpc_functions_list_devices_no_central():
    """Test listDevices when no central is found."""
    rpc_functions, mock_server = _create_mock_server()
    mock_server.get_central_entry.return_value = None

    result = await rpc_functions.listDevices("unknown-interface")

    assert result == []


@pytest.mark.asyncio
async def test_rpc_functions_new_devices():
    """Test newDevices callback."""
    rpc_functions, mock_server = _create_mock_server()
    mock_entry = _create_mock_central_entry()
    mock_server.get_central_entry.return_value = mock_entry

    device_descriptions = [
        {"ADDRESS": "ADDR1", "TYPE": "SWITCH"},
        {"ADDRESS": "ADDR2", "TYPE": "DIMMER"},
    ]

    await rpc_functions.newDevices("test-interface", device_descriptions)

    mock_entry.central.device_coordinator.add_new_devices.assert_called_once()
    call_args = mock_entry.central.device_coordinator.add_new_devices.call_args
    assert call_args.kwargs["interface_id"] == "test-interface"


@pytest.mark.asyncio
async def test_rpc_functions_readded_device():
    """Test readdedDevice callback."""
    rpc_functions, _ = _create_mock_server()

    with patch("aiohomematic.central.async_rpc_server.hmcl") as mock_hmcl:
        mock_client = MagicMock()
        mock_client.central.event_coordinator.publish_system_event = MagicMock()
        mock_hmcl.get_client.return_value = mock_client

        await rpc_functions.readdedDevice("test-interface", ["ADDR1", "ADDR2"])

        mock_hmcl.get_client.assert_called_with(interface_id="test-interface")


@pytest.mark.asyncio
async def test_rpc_functions_replace_device():
    """Test replaceDevice callback."""
    rpc_functions, _ = _create_mock_server()

    with patch("aiohomematic.central.async_rpc_server.hmcl") as mock_hmcl:
        mock_client = MagicMock()
        mock_client.central.event_coordinator.publish_system_event = MagicMock()
        mock_hmcl.get_client.return_value = mock_client

        await rpc_functions.replaceDevice("test-interface", "OLD_ADDR", "NEW_ADDR")

        mock_hmcl.get_client.assert_called_with(interface_id="test-interface")


@pytest.mark.asyncio
async def test_rpc_functions_update_device():
    """Test updateDevice callback."""
    rpc_functions, _ = _create_mock_server()

    with patch("aiohomematic.central.async_rpc_server.hmcl") as mock_hmcl:
        mock_client = MagicMock()
        mock_client.central.event_coordinator.publish_system_event = MagicMock()
        mock_hmcl.get_client.return_value = mock_client

        await rpc_functions.updateDevice("test-interface", "ADDR1", 1)

        mock_hmcl.get_client.assert_called_with(interface_id="test-interface")


# --- AsyncXmlRpcServer Tests ---


def test_server_singleton_pattern():
    """Test that same parameters return same instance."""
    server1 = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8080)
    server2 = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8080)

    assert server1 is server2


def test_server_singleton_different_params():
    """Test that different parameters create different instances."""
    server1 = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8080)
    server2 = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8081)

    assert server1 is not server2


def test_server_properties_before_start():
    """Test server properties before starting."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=8080)

    assert server.listen_ip_addr == "127.0.0.1"
    assert server.listen_port == 8080
    assert server.started is False
    assert server.no_central_assigned is True


@pytest.mark.asyncio
async def test_server_start_stop():
    """Test server start and stop lifecycle."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

    await server.start()
    assert server.started is True
    assert server.listen_port != 0  # Should be assigned

    await server.stop()
    assert server.started is False


@pytest.mark.asyncio
async def test_server_start_twice_is_noop():
    """Test that starting an already started server is a no-op."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

    await server.start()
    original_port = server.listen_port

    await server.start()  # Should be no-op
    assert server.listen_port == original_port

    await server.stop()


@pytest.mark.asyncio
async def test_server_stop_without_start():
    """Test that stopping a non-started server is safe."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

    # Should not raise
    await server.stop()


@pytest.mark.asyncio
async def test_server_add_remove_central():
    """Test central registration and unregistration."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

    mock_central = MagicMock()
    mock_central.name = "test-central"

    assert server.no_central_assigned is True

    server.add_central(central=mock_central)
    assert server.no_central_assigned is False

    server.remove_central(central=mock_central)
    assert server.no_central_assigned is True


@pytest.mark.asyncio
async def test_server_add_central_twice():
    """Test that adding same central twice is handled."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

    mock_central = MagicMock()
    mock_central.name = "test-central"

    server.add_central(central=mock_central)
    server.add_central(central=mock_central)

    assert len(server._centrals) == 1


@pytest.mark.asyncio
async def test_server_get_central_entry():
    """Test getting central entry by interface_id."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

    mock_central = MagicMock()
    mock_central.name = "test-central"
    mock_central.client_coordinator.has_client.return_value = True

    server.add_central(central=mock_central)

    entry = server.get_central_entry(interface_id="test-interface")
    assert entry is not None
    assert entry.central is mock_central


@pytest.mark.asyncio
async def test_server_get_central_entry_not_found():
    """Test getting central entry when not found."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

    mock_central = MagicMock()
    mock_central.name = "test-central"
    mock_central.client_coordinator.has_client.return_value = False

    server.add_central(central=mock_central)

    entry = server.get_central_entry(interface_id="unknown-interface")
    assert entry is None


@pytest.mark.asyncio
async def test_server_http_request_handling():
    """Test HTTP request handling end-to-end."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
    await server.start()

    try:
        xml_request = xmlrpc.client.dumps((), methodname="system.listMethods")

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"http://127.0.0.1:{server.listen_port}/",
                data=xml_request.encode("utf-8"),
                headers={"Content-Type": "text/xml"},
            ) as response,
        ):
            assert response.status == 200
            assert response.content_type == "text/xml"

            body = await response.read()
            result = xmlrpc.client.loads(body.decode("utf-8"))
            assert isinstance(result[0][0], list)  # List of methods
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_server_http_rpc2_endpoint():
    """Test /RPC2 endpoint."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
    await server.start()

    try:
        xml_request = xmlrpc.client.dumps((), methodname="system.listMethods")

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"http://127.0.0.1:{server.listen_port}/RPC2",
                data=xml_request.encode("utf-8"),
                headers={"Content-Type": "text/xml"},
            ) as response,
        ):
            assert response.status == 200
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_server_http_invalid_xml_returns_400():
    """Test that invalid XML returns 400 status."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
    await server.start()

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"http://127.0.0.1:{server.listen_port}/",
                data=b"not valid xml",
                headers={"Content-Type": "text/xml"},
            ) as response,
        ):
            assert response.status == 400
    finally:
        await server.stop()


# --- create_async_xml_rpc_server Factory Tests ---


@pytest.mark.asyncio
async def test_factory_creates_and_starts_server():
    """Test that factory creates and starts server."""
    server = await create_async_xml_rpc_server(ip_addr="127.0.0.1", port=0)

    try:
        assert server.started is True
        assert server.listen_port != 0
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_factory_returns_existing_started_server():
    """Test that factory returns existing started server."""
    server1 = await create_async_xml_rpc_server(ip_addr="127.0.0.1", port=0)

    # Create same server again (same singleton)
    server2 = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)

    assert server1 is server2
    assert server2.started is True

    await server1.stop()


@pytest.mark.asyncio
async def test_factory_default_parameters():
    """Test factory with default parameters."""
    server = await create_async_xml_rpc_server()

    try:
        assert server.listen_ip_addr == IP_ANY_V4
        assert server.started is True
    finally:
        await server.stop()


# --- Health Check Endpoint Tests ---


@pytest.mark.asyncio
async def test_server_health_check_endpoint():
    """Test health check endpoint returns server status."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
    await server.start()

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(f"http://127.0.0.1:{server.listen_port}/health") as response,
        ):
            assert response.status == 200
            assert response.content_type == "application/json"

            data = await response.json()
            assert data["status"] == "healthy"
            assert data["started"] is True
            assert data["centrals_count"] == 0
            assert data["centrals"] == []
            assert data["active_background_tasks"] == 0
            assert data["request_count"] == 0
            assert data["error_count"] == 0
            assert "listen_address" in data
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_server_health_check_with_requests():
    """Test health check shows request and error counts."""
    server = AsyncXmlRpcServer(ip_addr="127.0.0.1", port=0)
    await server.start()

    try:
        async with aiohttp.ClientSession() as session:
            # Make a valid request
            valid_xml = xmlrpc.client.dumps((), methodname="system.listMethods")
            async with session.post(
                f"http://127.0.0.1:{server.listen_port}/",
                data=valid_xml.encode("utf-8"),
                headers={"Content-Type": "text/xml"},
            ) as response:
                assert response.status == 200

            # Make an invalid request (will cause error)
            async with session.post(
                f"http://127.0.0.1:{server.listen_port}/",
                data=b"not valid xml",
                headers={"Content-Type": "text/xml"},
            ) as response:
                assert response.status == 400

            # Check health reflects the requests
            async with session.get(f"http://127.0.0.1:{server.listen_port}/health") as response:
                data = await response.json()
                assert data["request_count"] == 2
                assert data["error_count"] == 1
    finally:
        await server.stop()
