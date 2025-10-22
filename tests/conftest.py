"""Test support for aiohomematic."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import logging
import os
from unittest.mock import Mock, patch

from aiohttp import ClientSession
import pydevccu
import pytest

from aiohomematic.central import CentralUnit
from aiohomematic.client import Client
from aiohomematic_support import const
from aiohomematic_support.client_support import (
    FactoryWithClient,
    FactoryWithLocalClient,
    SessionPlayer,
    get_pydev_ccu_central_unit_full,
    get_session_player,
)

from tests.helpers.mock_json_rpc import MockJsonRpc
from tests.helpers.mock_xml_rpc import MockXmlRpcServer

logging.basicConfig(level=logging.INFO)

# pylint: disable=protected-access, redefined-outer-name


@pytest.fixture(autouse=True)
def teardown():
    """Clean up."""
    patch.stopall()


@pytest.fixture
def pydev_ccu_full() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_PORT))
    ccu.start()
    try:
        yield ccu
    finally:
        ccu.stop()


@pytest.fixture(scope="module")
def pydev_ccu_mini() -> pydevccu.Server:
    """Create the virtual ccu."""
    ccu = pydevccu.Server(addr=(const.CCU_HOST, const.CCU_MINI_PORT), devices=["HmIP-BWTH", "HmIP-eTRV-2"])
    ccu.start()
    try:
        yield ccu
    finally:
        ccu.stop()


@pytest.fixture
async def central_unit_mini(pydev_ccu_mini: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""
    central = await get_pydev_ccu_central_unit_full(port=const.CCU_MINI_PORT)
    try:
        yield central
    finally:
        await central.stop()
        await central.clear_files()


@pytest.fixture
async def central_unit_full(pydev_ccu_full: pydevccu.Server) -> CentralUnit:
    """Create and yield central."""

    def homematic_callback(*args, **kwargs):
        """Do dummy homematic_callback."""

    def backend_system_callback(*args, **kwargs):
        """Do dummy backend_system_callback."""

    central = await get_pydev_ccu_central_unit_full(port=const.CCU_PORT)

    unregister_homematic_callback = central.register_homematic_callback(cb=homematic_callback)
    unregister_backend_system_callback = central.register_backend_system_callback(cb=backend_system_callback)

    try:
        yield central
    finally:
        unregister_homematic_callback()
        unregister_backend_system_callback()
        await central.stop()
        await central.clear_files()


@pytest.fixture
async def factory_with_local_client() -> FactoryWithLocalClient:
    """Return central factory."""
    return FactoryWithLocalClient()


@pytest.fixture
async def aiohttp_session() -> AsyncGenerator[ClientSession]:
    """Provide a shared aiohttp ClientSession for tests and ensure cleanup."""
    session = ClientSession()
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def central_client_factory_with_local_client(
    port: int,
    address_device_translation: dict[str, str],
    do_mock_client: bool,
    add_sysvars: bool,
    add_programs: bool,
    ignore_devices_on_create: list[str] | None,
    un_ignore_list: list[str] | None,
) -> tuple[CentralUnit, Client | Mock, FactoryWithLocalClient]:
    """Return central factory."""
    factory = FactoryWithLocalClient()
    central_client = await factory.get_default_central(
        port=port,
        address_device_translation=address_device_translation,
        do_mock_client=do_mock_client,
        add_sysvars=add_sysvars,
        add_programs=add_programs,
        ignore_devices_on_create=ignore_devices_on_create,
        un_ignore_list=un_ignore_list,
    )
    central, client = central_client
    try:
        yield central, client, factory
    finally:
        await central.stop()
        await central.clear_files()


@pytest.fixture
async def central_client_factory_with_ccu_client(
    session_recorder_from_full_session_ccu,
    address_device_translation: dict[str, str],
    do_mock_client: bool,
    ignore_devices_on_create: list[str] | None,
    un_ignore_list: list[str] | None,
) -> AsyncGenerator[tuple[CentralUnit, Client | Mock, FactoryWithClient]]:
    """Yield central factory using CCU session and XML-RPC proxy."""
    async for result in get_central_client_factory(
        recorder=session_recorder_from_full_session_ccu,
        address_device_translation=address_device_translation,
        do_mock_client=do_mock_client,
        ignore_devices_on_create=ignore_devices_on_create,
        ignore_custom_device_definition_models=None,
        un_ignore_list=un_ignore_list,
    ):
        yield result


@pytest.fixture
async def central_client_factory_with_pydevccu_client(
    session_recorder_from_full_session_pydevccu,
    address_device_translation: dict[str, str],
    do_mock_client: bool,
    ignore_devices_on_create: list[str] | None,
    un_ignore_list: list[str] | None,
) -> AsyncGenerator[tuple[CentralUnit, Client | Mock, FactoryWithClient]]:
    """Yield central factory using pydevccu XML-RPC proxy."""
    async for result in get_central_client_factory(
        recorder=session_recorder_from_full_session_pydevccu,
        address_device_translation=address_device_translation,
        do_mock_client=do_mock_client,
        ignore_devices_on_create=ignore_devices_on_create,
        ignore_custom_device_definition_models=None,
        un_ignore_list=un_ignore_list,
    ):
        yield result


async def get_central_client_factory(
    recorder: SessionPlayer,
    address_device_translation: dict[str, str],
    do_mock_client: bool,
    ignore_devices_on_create: list[str] | None,
    ignore_custom_device_definition_models: list[str] | None,
    un_ignore_list: list[str] | None,
) -> tuple[CentralUnit, Client | Mock, FactoryWithClient]:
    """Return central factory."""
    factory = FactoryWithClient(
        recorder=recorder,
        address_device_translation=address_device_translation,
        ignore_devices_on_create=ignore_devices_on_create,
    )
    central_client = await factory.get_default_central(
        do_mock_client=do_mock_client,
        ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        un_ignore_list=un_ignore_list,
    )
    central, client = central_client
    try:
        yield central, client, factory
    finally:
        await central.stop()
        await central.clear_files()


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


@pytest.fixture
async def session_recorder_from_full_session_ccu() -> SessionPlayer:
    """Provide a SessionPlayer preloaded from the randomized full session JSON file."""
    file_path = os.path.join(os.path.dirname(__file__), "data", const.FULL_SESSION_RANDOMIZED_CCU)
    return await get_session_player(file_path=file_path)


@pytest.fixture
async def session_recorder_from_full_session_pydevccu() -> SessionPlayer:
    """Provide a SessionPlayer preloaded from the randomized full session JSON file."""
    file_path = os.path.join(os.path.dirname(__file__), "data", const.FULL_SESSION_RANDOMIZED_PYDEVCCU)
    return await get_session_player(file_path=file_path)
