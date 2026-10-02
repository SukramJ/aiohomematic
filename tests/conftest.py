# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Test support for aiohomematic."""

import asyncio
from collections.abc import AsyncGenerator, Generator
import logging
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

if TYPE_CHECKING:
    from aiohomematic_test_support.event_capture import EventCapture

from aiohttp import ClientSession
import pytest

from aiohomematic.async_support import Looper
from aiohomematic.central import CentralUnit
from aiohomematic.central.events import DeviceLifecycleEvent, DeviceTriggerEvent, EventBus
from aiohomematic.client import CircuitBreaker
from aiohomematic.interfaces import ClientProtocol
from aiohomematic_test_support import const
from aiohomematic_test_support.factory import (
    FactoryWithClient,
    get_central_client_factory,
    get_godevccu_central_unit_full,
)
from aiohomematic_test_support.mock import SessionPlayer, get_session_player

from tests.helpers.godevccu_process import GodevccuProcess, find_godevccu_binary
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
def _reset_locale_lock() -> None:
    """Reset the i18n locale lock before each test so tests can call set_locale() freely."""
    from aiohomematic.i18n import _reset_locale_for_testing

    _reset_locale_for_testing()


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
def session_player_godevccu() -> SessionPlayer:
    """
    Provide a SessionPlayer preloaded from the godevccu (homegear mode) session file.

    Session-scoped for performance: ZIP file is loaded once per test session.
    SessionPlayer uses class-level caching, so data is shared safely.
    """
    return _load_session_player_sync(const.FULL_SESSION_GODEVCCU)


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


# Homegear/godevccu client fixtures


@pytest.fixture
async def factory_with_homegear_client(session_player_godevccu: SessionPlayer) -> FactoryWithClient:
    """Return central factory."""
    return FactoryWithClient(player=session_player_godevccu)


@pytest.fixture
async def central_client_factory_with_homegear_client(
    session_player_godevccu: SessionPlayer,
    address_device_translation: set[str],
    do_mock_client: bool,
    ignore_devices_on_create: list[str] | None,
    un_ignore_list: list[str] | None,
) -> AsyncGenerator[tuple[CentralUnit, ClientProtocol | Mock, FactoryWithClient]]:
    """Yield central factory using homegear XML-RPC proxy."""
    async for result in get_central_client_factory(
        player=session_player_godevccu,
        address_device_translation=address_device_translation,
        do_mock_client=do_mock_client,
        ignore_devices_on_create=ignore_devices_on_create,
        ignore_custom_device_definition_models=None,
        un_ignore_list=un_ignore_list,
    ):
        yield result


# godevccu simulator fixtures
# The godevccu binary (script/install_godevccu.sh, version in .godevccu-version)
# runs as a subprocess per xdist worker on the worker's ports.


def _start_godevccu(*, args: list[str], tmp_path_factory: pytest.TempPathFactory) -> GodevccuProcess:
    """Start a godevccu subprocess in its own temp directory."""
    process = GodevccuProcess(
        binary=find_godevccu_binary(),
        args=args,
        work_dir=tmp_path_factory.mktemp("godevccu"),
    )
    process.start()
    return process


@pytest.fixture(scope="session")
def godevccu_mini(tmp_path_factory: pytest.TempPathFactory) -> Generator[GodevccuProcess]:
    """Run godevccu in homegear mode with an HmIP-BWTH and an HmIP-eTRV-2."""
    process = _start_godevccu(
        args=[
            "-mode",
            "homegear",
            "-host",
            const.CCU_HOST,
            "-xml-rpc-port",
            str(const.get_ccu_mini_port()),
            "-json-rpc-port",
            "0",
            "-devices",
            "HmIP-BWTH,HmIP-eTRV-2",
        ],
        tmp_path_factory=tmp_path_factory,
    )
    try:
        yield process
    finally:
        process.stop()


@pytest.fixture
async def central_unit_godevccu_mini(godevccu_mini: GodevccuProcess) -> AsyncGenerator[CentralUnit]:
    """Create and yield central."""
    central = await get_godevccu_central_unit_full(port=const.get_ccu_mini_port())
    try:
        yield central
    finally:
        await central.stop()
        await central.cache_coordinator.clear_all()


@pytest.fixture(scope="session")
def godevccu_full(tmp_path_factory: pytest.TempPathFactory) -> Generator[GodevccuProcess]:
    """Run godevccu in homegear mode with every embedded device type."""
    process = _start_godevccu(
        args=[
            "-mode",
            "homegear",
            "-host",
            const.CCU_HOST,
            "-xml-rpc-port",
            str(const.get_ccu_port()),
            "-json-rpc-port",
            "0",
        ],
        tmp_path_factory=tmp_path_factory,
    )
    try:
        yield process
    finally:
        process.stop()


@pytest.fixture
async def central_unit_godevccu_full(godevccu_full: GodevccuProcess) -> AsyncGenerator[CentralUnit]:
    """Create and yield central."""

    def device_trigger_callback(event: DeviceTriggerEvent) -> None:
        """Do dummy device trigger handler."""

    def device_lifecycle_callback(event: DeviceLifecycleEvent) -> None:
        """Do dummy device lifecycle handler."""

    central = await get_godevccu_central_unit_full(port=const.get_ccu_port())

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
        await central.stop()
        await central.cache_coordinator.clear_all()


# ─────────────────────────────────────────────────────────────────────────────
# OpenCCU fixtures (godevccu in openccu mode)
# godevccu simulates an OpenCCU/RaspberryMatic system including the JSON-RPC
# API, ReGa scripts, programs and system variables.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def godevccu_openccu(tmp_path_factory: pytest.TempPathFactory) -> Generator[GodevccuProcess]:
    """
    Run godevccu as a virtual OpenCCU.

    Provides an XML-RPC server (device operations), a JSON-RPC server (programs,
    system variables, rooms, ...), the ReGa script engine, authentication and the
    default test state (programs, system variables, rooms, functions).
    """
    process = _start_godevccu(
        args=[
            "-mode",
            "openccu",
            "-host",
            const.CCU_HOST,
            "-xml-rpc-port",
            str(const.get_openccu_xml_rpc_port()),
            "-json-rpc-port",
            str(const.get_openccu_json_rpc_port()),
            "-username",
            const.CCU_USERNAME,
            "-password",
            const.CCU_PASSWORD,
            "-auth=true",
            "-defaults",
        ],
        tmp_path_factory=tmp_path_factory,
    )
    try:
        yield process
    finally:
        process.stop()


@pytest.fixture
async def central_unit_openccu(godevccu_openccu: GodevccuProcess) -> AsyncGenerator[CentralUnit]:
    """
    Create a CentralUnit connected to the virtual OpenCCU.

    This fixture provides a fully functional CentralUnit configured for
    OpenCCU backend, suitable for testing CCU-specific features like:
    - Programs and system variables
    - Rooms and functions
    - Backup and firmware update
    - ReGa script execution
    """
    import contextlib

    from aiohomematic.central import CentralConfig
    from aiohomematic.central.events import DeviceLifecycleEvent, DeviceLifecycleEventType
    from aiohomematic.client import InterfaceConfig
    from aiohomematic.const import Interface

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
        locale="de",
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
