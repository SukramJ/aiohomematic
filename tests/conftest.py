# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Test support for aiohomematic."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import logging
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

if TYPE_CHECKING:
    from aiohomematic_test_support.event_capture import EventCapture

from aiohttp import ClientSession
import pydevccu
import pytest

from aiohomematic.central import CentralUnit
from aiohomematic.central.events import DeviceLifecycleEvent, DeviceTriggerEvent
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

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture(autouse=True)
def teardown():
    """Clean up."""
    patch.stopall()


# CCU client fixtures


@pytest.fixture
async def factory_with_ccu_client(session_player_ccu) -> FactoryWithClient:
    """Return central factory."""
    return FactoryWithClient(player=session_player_ccu)


@pytest.fixture
async def central_client_factory_with_ccu_client(
    session_player_ccu,
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


@pytest.fixture
async def session_player_ccu() -> SessionPlayer:
    """Provide a SessionPlayer preloaded from the randomized full session JSON file."""
    return await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_CCU)


# Homegear/pydevccu client fixtures


@pytest.fixture
async def factory_with_homegear_client(session_player_pydevccu) -> FactoryWithClient:
    """Return central factory."""
    return FactoryWithClient(player=session_player_pydevccu)


@pytest.fixture
async def central_client_factory_with_homegear_client(
    session_player_pydevccu,
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


@pytest.fixture
async def session_player_pydevccu() -> SessionPlayer:
    """Provide a SessionPlayer preloaded from the randomized full session JSON file."""
    return await get_session_player(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)


# homegear mini fixtures


@pytest.fixture(scope="module")
def pydevccu_mini() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_MINI_PORT), devices=["HmIP-BWTH", "HmIP-eTRV-2"])
    ccu.start()
    try:
        yield ccu
    finally:
        ccu.stop()


@pytest.fixture
async def central_unit_pydevccu_mini(pydevccu_mini: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""
    central = await get_pydev_ccu_central_unit_full(port=const.CCU_MINI_PORT)
    try:
        yield central
    finally:
        await central.stop()
        await central.cache_coordinator.clear_all()


# pydevccu full fixtures


@pytest.fixture
def pydevccu_full() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_PORT))
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

    central = await get_pydev_ccu_central_unit_full(port=const.CCU_PORT)

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
    from aiohomematic_test_support.event_capture import EventCapture  # noqa: PLC0415

    capture = EventCapture()
    try:
        yield capture
    finally:
        capture.cleanup()
