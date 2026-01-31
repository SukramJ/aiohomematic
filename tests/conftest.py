# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Test support for aiohomematic."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
import logging
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

if TYPE_CHECKING:
    from aiohomematic_test_support.event_capture import EventCapture

from aiohttp import ClientSession
import pydevccu
import pytest

# Check if pydevccu has OpenCCU support (VirtualCCU, BackendMode)
# This will be available in pydevccu 0.2.0+
try:
    from pydevccu import BackendMode, VirtualCCU

    PYDEVCCU_HAS_OPENCCU_SUPPORT = True
except ImportError:
    PYDEVCCU_HAS_OPENCCU_SUPPORT = False
    BackendMode = None  # type: ignore[assignment, misc]
    VirtualCCU = None  # type: ignore[assignment, misc]

from aiohomematic.async_support import Looper
from aiohomematic.central import CentralUnit
from aiohomematic.central.events import DeviceLifecycleEvent, DeviceTriggerEvent, EventBus
from aiohomematic.client import CircuitBreaker
from aiohomematic.interfaces import ClientProtocol
from aiohomematic_test_support import const
from aiohomematic_test_support.factory import (
    FactoryWithClient,
    get_central_client_factory,
    get_pydev_ccu_central_unit_full,
)
from aiohomematic_test_support.mock import SessionPlayer, get_session_player

from tests.helpers.mock_json_rpc import MockJsonRpc
from tests.helpers.mock_xml_rpc import MockXmlRpcServer

logging.basicConfig(level=logging.INFO)


class _UnclosedSessionFilter(logging.Filter):
    """Filter out 'Unclosed client session' messages from asyncio during test shutdown."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress the message."""
        return "Unclosed client session" not in record.getMessage()


# Suppress harmless asyncio warnings about unclosed sessions during xdist worker shutdown
logging.getLogger("asyncio").addFilter(_UnclosedSessionFilter())

# pylint: disable=protected-access, redefined-outer-name


def _load_session_player_sync(file_name: str) -> SessionPlayer:
    """Load SessionPlayer synchronously for session-scoped fixtures."""
    return asyncio.run(get_session_player(file_name=file_name))


@pytest.fixture(autouse=True)
def teardown():
    """Clean up."""
    patch.stopall()


# Session-scoped SessionPlayer fixtures
# These are loaded once per test session and shared across all tests.
# SessionPlayer uses a class-level cache, so sharing instances is safe.


@pytest.fixture(scope="session")
def session_player_ccu() -> SessionPlayer:
    """
    Provide a SessionPlayer preloaded from the CCU session file.

    Session-scoped for performance: ZIP file is loaded once per test session.
    SessionPlayer uses class-level caching, so data is shared safely.
    """
    return _load_session_player_sync(const.FULL_SESSION_RANDOMIZED_CCU)


@pytest.fixture(scope="session")
def session_player_pydevccu() -> SessionPlayer:
    """
    Provide a SessionPlayer preloaded from the pydevccu/Homegear session file.

    Session-scoped for performance: ZIP file is loaded once per test session.
    SessionPlayer uses class-level caching, so data is shared safely.
    """
    return _load_session_player_sync(const.FULL_SESSION_RANDOMIZED_PYDEVCCU)


# CCU client fixtures


@pytest.fixture
async def factory_with_ccu_client(session_player_ccu: SessionPlayer) -> FactoryWithClient:
    """Return central factory."""
    return FactoryWithClient(player=session_player_ccu)


@pytest.fixture
async def central_client_factory_with_ccu_client(
    session_player_ccu: SessionPlayer,
    address_device_translation: set[str],
    do_mock_client: bool,
    ignore_devices_on_create: list[str] | None,
    un_ignore_list: list[str] | None,
) -> AsyncGenerator[tuple[CentralUnit, ClientProtocol | Mock, FactoryWithClient]]:
    """Yield central factory using CCU session and XML-RPC proxy."""
    async for result in get_central_client_factory(
        player=session_player_ccu,
        address_device_translation=address_device_translation,
        do_mock_client=do_mock_client,
        ignore_devices_on_create=ignore_devices_on_create,
        ignore_custom_device_definition_models=None,
        un_ignore_list=un_ignore_list,
    ):
        yield result


# Homegear/pydevccu client fixtures


@pytest.fixture
async def factory_with_homegear_client(session_player_pydevccu: SessionPlayer) -> FactoryWithClient:
    """Return central factory."""
    return FactoryWithClient(player=session_player_pydevccu)


@pytest.fixture
async def central_client_factory_with_homegear_client(
    session_player_pydevccu: SessionPlayer,
    address_device_translation: set[str],
    do_mock_client: bool,
    ignore_devices_on_create: list[str] | None,
    un_ignore_list: list[str] | None,
) -> AsyncGenerator[tuple[CentralUnit, ClientProtocol | Mock, FactoryWithClient]]:
    """Yield central factory using homegear XML-RPC proxy."""
    async for result in get_central_client_factory(
        player=session_player_pydevccu,
        address_device_translation=address_device_translation,
        do_mock_client=do_mock_client,
        ignore_devices_on_create=ignore_devices_on_create,
        ignore_custom_device_definition_models=None,
        un_ignore_list=un_ignore_list,
    ):
        yield result


# homegear mini fixtures


@pytest.fixture(scope="session")
def pydevccu_mini() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.get_ccu_mini_port()), devices=["HmIP-BWTH", "HmIP-eTRV-2"])
    ccu.start()
    try:
        yield ccu
    finally:
        ccu.stop()


@pytest.fixture
async def central_unit_pydevccu_mini(pydevccu_mini: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""
    central = await get_pydev_ccu_central_unit_full(port=const.get_ccu_mini_port())
    try:
        yield central
    finally:
        # Clear pydevccu's remotes BEFORE stopping central to prevent
        # _askDevices thread from trying to contact stopped XML-RPC server
        pydevccu_mini._rpcfunctions.remotes.clear()
        await central.stop()
        await central.cache_coordinator.clear_all()


# pydevccu full fixtures


@pytest.fixture(scope="session")
def pydevccu_full() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.get_ccu_port()))
    ccu.start()
    try:
        yield ccu
    finally:
        ccu.stop()


@pytest.fixture
async def central_unit_pydevccu_full(pydevccu_full: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""

    def device_trigger_callback(event: DeviceTriggerEvent) -> None:
        """Do dummy device trigger handler."""

    def device_lifecycle_callback(event: DeviceLifecycleEvent) -> None:
        """Do dummy device lifecycle handler."""

    central = await get_pydev_ccu_central_unit_full(port=const.get_ccu_port())

    unsubscribe_device_trigger_callback = central.event_bus.subscribe(
        event_type=DeviceTriggerEvent, event_key=None, handler=device_trigger_callback
    )
    unsubscribe_device_lifecycle_callback = central.event_bus.subscribe(
        event_type=DeviceLifecycleEvent, event_key=None, handler=device_lifecycle_callback
    )

    try:
        yield central
    finally:
        unsubscribe_device_trigger_callback()
        unsubscribe_device_lifecycle_callback()
        # Clear pydevccu's remotes BEFORE stopping central to prevent
        # _askDevices thread from trying to contact stopped XML-RPC server
        pydevccu_full._rpcfunctions.remotes.clear()
        await central.stop()
        await central.cache_coordinator.clear_all()


# ─────────────────────────────────────────────────────────────────────────────
# OpenCCU fixtures (requires pydevccu 0.2.0+ with VirtualCCU support)
# These fixtures use VirtualCCU with BackendMode.OPENCCU to simulate a real
# OpenCCU/RaspberryMatic system including JSON-RPC API, ReGa scripts, and
# programs/system variables support.
# ─────────────────────────────────────────────────────────────────────────────

# Marker for tests requiring OpenCCU support
requires_openccu = pytest.mark.skipif(
    not PYDEVCCU_HAS_OPENCCU_SUPPORT,
    reason="Requires pydevccu 0.2.0+ with VirtualCCU/BackendMode support",
)


@pytest.fixture(scope="session")
def pydevccu_openccu() -> VirtualCCU | None:  # type: ignore[name-defined]
    """
    Create a virtual OpenCCU instance for testing.

    This fixture provides a complete OpenCCU simulation including:
    - XML-RPC server (for device operations)
    - JSON-RPC server (for programs, system variables, rooms, etc.)
    - ReGa script engine (for CCU-specific scripts)
    - Default test state (programs, system variables, rooms)

    The JSON-RPC server runs in a background thread with its own event loop
    to allow the test event loop to communicate with it via HTTP.

    Requires pydevccu 0.2.0+ with VirtualCCU support.
    """
    if not PYDEVCCU_HAS_OPENCCU_SUPPORT:
        pytest.skip("Requires pydevccu 0.2.0+ with VirtualCCU/BackendMode support")
        return None

    import asyncio
    import threading

    ccu = VirtualCCU(
        mode=BackendMode.OPENCCU,
        host=const.CCU_HOST,
        xml_rpc_port=const.get_openccu_xml_rpc_port(),
        json_rpc_port=const.get_openccu_json_rpc_port(),
        auth_enabled=True,
        username=const.CCU_USERNAME,
        password=const.CCU_PASSWORD,
    )
    ccu.setup_default_state()

    # Create a dedicated event loop and thread for the JSON-RPC server
    # This is necessary because aiohttp servers only respond to requests
    # in the same event loop they were started in.
    server_loop: asyncio.AbstractEventLoop | None = None
    server_started = threading.Event()

    def run_server() -> None:
        nonlocal server_loop
        server_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(server_loop)
        server_loop.run_until_complete(ccu.start())
        server_started.set()
        # Keep the loop running to handle requests
        server_loop.run_forever()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to start
    server_started.wait(timeout=10)
    if not server_started.is_set():
        raise RuntimeError("VirtualCCU server failed to start within 10 seconds")

    try:
        yield ccu
    finally:
        # Stop the server and cleanup
        if server_loop is not None:

            def stop_server() -> None:
                stop_task = asyncio.ensure_future(ccu.stop())  # noqa: F841, RUF006
                server_loop.call_soon(server_loop.stop)

            server_loop.call_soon_threadsafe(stop_server)
            server_thread.join(timeout=5)


@pytest.fixture
async def central_unit_openccu(pydevccu_openccu: VirtualCCU) -> CentralUnit:  # type: ignore[name-defined]
    """
    Create a CentralUnit connected to virtual OpenCCU.

    This fixture provides a fully functional CentralUnit configured for
    OpenCCU backend, suitable for testing CCU-specific features like:
    - Programs and system variables
    - Rooms and functions
    - Backup and firmware update
    - ReGa script execution

    Requires pydevccu 0.2.0+ with VirtualCCU support.
    """
    import contextlib

    from aiohomematic.central import CentralConfig
    from aiohomematic.central.events import DeviceLifecycleEvent, DeviceLifecycleEventType
    from aiohomematic.client import InterfaceConfig
    from aiohomematic.const import Interface

    if not PYDEVCCU_HAS_OPENCCU_SUPPORT:
        pytest.skip("Requires pydevccu 0.2.0+ with VirtualCCU/BackendMode support")

    # Wait for devices to be created
    device_event = asyncio.Event()

    def device_lifecycle_event_handler(event: DeviceLifecycleEvent) -> None:
        """Handle device lifecycle events."""
        if event.event_type == DeviceLifecycleEventType.CREATED:
            device_event.set()

    config = CentralConfig(
        name=const.OPENCCU_CENTRAL_NAME,
        host=const.CCU_HOST,
        username=const.CCU_USERNAME,
        password=const.CCU_PASSWORD,
        central_id="test-openccu-123",
        interface_configs={
            InterfaceConfig(
                central_name=const.OPENCCU_CENTRAL_NAME,
                interface=Interface.BIDCOS_RF,
                port=const.get_openccu_xml_rpc_port(),
            ),
        },
        json_port=const.get_openccu_json_rpc_port(),
        program_markers=(),
        sysvar_markers=(),
        start_direct=True,
    )

    central = await config.create_central()
    central.event_bus.subscribe(event_type=DeviceLifecycleEvent, event_key=None, handler=device_lifecycle_event_handler)
    await central.start()

    # Wait up to 60 seconds for the DEVICES_CREATED event
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(device_event.wait(), timeout=60)

    try:
        yield central
    finally:
        # Clear pydevccu's remotes BEFORE stopping central
        if hasattr(pydevccu_openccu, "_xml_rpc_server") and pydevccu_openccu._xml_rpc_server:
            pydevccu_openccu._xml_rpc_server._rpcfunctions.remotes.clear()
        await central.stop()
        await central.cache_coordinator.clear_all()


# Other fixtures


@pytest.fixture
async def aiohttp_session() -> AsyncGenerator[ClientSession]:
    """Provide a shared aiohttp ClientSession for tests and ensure cleanup."""
    session = ClientSession()
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
def mock_xml_rpc_server() -> Generator[tuple[MockXmlRpcServer, str]]:
    """Yield a running mock XML-RPC server and its base URL for tests."""
    srv = MockXmlRpcServer()
    host, port = srv.start()
    try:
        yield srv, f"http://{host}:{port}"
    finally:
        srv.stop()


@pytest.fixture
async def mock_json_rpc_server() -> AsyncGenerator[tuple[MockJsonRpc, str]]:
    """Yield a running mock JSON-RPC server and its base URL for tests."""
    srv = MockJsonRpc()
    base_url = await srv.start()
    try:
        yield srv, base_url
    finally:
        await srv.stop()


# Event capture fixtures


@pytest.fixture
def event_capture() -> Generator[EventCapture]:
    """Provide an EventCapture instance with automatic cleanup."""
    from aiohomematic_test_support.event_capture import EventCapture

    capture = EventCapture()
    try:
        yield capture
    finally:
        capture.cleanup()


# Task scheduler and event bus fixtures


class NoOpTaskScheduler:
    """
    Task scheduler that does nothing - for sync tests without event loop.

    Use this in sync tests where you need a TaskSchedulerProtocol but don't
    actually need to run async tasks. This avoids the Python 3.14+ issue where
    asyncio.get_event_loop() raises RuntimeError outside async context.
    """

    def create_task(self, *, target: object, name: str) -> None:
        """Close coroutine to avoid 'never awaited' warning."""
        if hasattr(target, "close"):
            target.close()  # type: ignore[union-attr]


@pytest.fixture
def no_op_task_scheduler() -> NoOpTaskScheduler:
    """Provide a NoOpTaskScheduler for sync tests."""
    return NoOpTaskScheduler()


@pytest.fixture
def looper() -> Looper:
    """
    Provide a Looper instance for task scheduling in tests.

    Note: Only use in async tests. For sync tests, use no_op_task_scheduler.
    """
    return Looper()


@pytest.fixture
def event_bus(looper: Looper) -> EventBus:
    """Provide an EventBus instance with task_scheduler for tests."""
    return EventBus(task_scheduler=looper)


@pytest.fixture
def circuit_breaker(looper: Looper, event_bus: EventBus) -> CircuitBreaker:
    """Provide a CircuitBreaker instance for tests."""
    return CircuitBreaker(interface_id="test", event_bus=event_bus, task_scheduler=looper)
