"""Test support for aiohomematic."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
import logging
import os
from unittest.mock import Mock, patch

from aiohttp import ClientSession
import pydevccu
import pytest

from aiohomematic.central import CentralUnit
from aiohomematic.client import Client

from tests import const, helper
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
    central = await helper.get_pydev_ccu_central_unit_full(port=const.CCU_MINI_PORT)
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

    central = await helper.get_pydev_ccu_central_unit_full(port=const.CCU_PORT)

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
async def factory() -> helper.FactoryWithLocalClient:
    """Return central factory."""
    return helper.FactoryWithLocalClient()


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
) -> tuple[CentralUnit, Client | Mock, helper.FactoryWithLocalClient]:
    """Return central factory."""
    factory = helper.FactoryWithLocalClient()
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
async def session_recorder_from_full_session():
    """Provide a SessionRecorder preloaded from the randomized full session JSON file."""

    # Lightweight stubs to satisfy BasePersistentFile requirements without spinning up a full CentralUnit.
    class _LooperStub:
        async def async_add_executor_job(self, func, name: str | None = None):  # pragma: no cover - simple stub
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, func)

        def create_task(self, target, name: str | None = None):  # pragma: no cover - simple stub
            return asyncio.create_task(target)

    class _ConfigStub:
        def __init__(self) -> None:
            # Use the tests storage directory which exists in the repo
            self.storage_directory = os.path.join(os.path.dirname(__file__), "..", "aiohomematic_storage")
            self.use_caches = True

    class _CentralStub:
        def __init__(self) -> None:
            self.name = "test"
            self.config = _ConfigStub()
            self.devices: list = []
            self.looper = _LooperStub()

    from aiohomematic.store import SessionRecorder

    central = _CentralStub()
    # ttl_seconds=0 -> no expiry in tests; refresh_on_get disabled for deterministic reads
    recorder = SessionRecorder(central=central, active=False, ttl_seconds=0, refresh_on_get=False)

    file_path = os.path.join(os.path.dirname(__file__), "data", "full_session_randomized.json")
    await recorder.load(file_path=file_path)
    return recorder
