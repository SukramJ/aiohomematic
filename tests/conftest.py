"""Test support for aiohomematic."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
import logging
import os
from typing import cast
from unittest.mock import Mock, patch

from aiohttp import ClientSession
import orjson
import pydevccu
import pytest

from aiohomematic.central import CentralUnit
from aiohomematic.client import BaseRpcProxy, Client
from aiohomematic.client.rpc_proxy import _RpcMethod
from aiohomematic.const import UTF_8, RPCType
from aiohomematic.store import SessionRecorder

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
async def factory_with_local_client() -> helper.FactoryWithLocalClient:
    """Return central factory."""
    return helper.FactoryWithLocalClient()


@pytest.fixture
async def factory_with_ccu_client(
    client_session_from_full_session_ccu, aio_xml_rpc_proxy_from_full_session_ccu
) -> helper.FactoryWithClient:
    """Return central factory."""
    return helper.FactoryWithClient(
        client_session=client_session_from_full_session_ccu, xml_proxy=aio_xml_rpc_proxy_from_full_session_ccu
    )


@pytest.fixture
async def factory_with_homegear_client(aio_xml_rpc_proxy_from_full_session_pydevccu) -> helper.FactoryWithClient:
    """Return central factory."""
    return helper.FactoryWithClient(client_session=None, xml_proxy=aio_xml_rpc_proxy_from_full_session_pydevccu)


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
async def central_client_factory_with_ccu_client(
    port: int,
    un_ignore_list: list[str] | None,
    client_session_from_full_session_ccu,
    aio_xml_rpc_proxy_from_full_session_ccu,
) -> AsyncGenerator[tuple[CentralUnit, Client | Mock, helper.FactoryWithClient]]:
    """Yield central factory using CCU session and XML-RPC proxy."""
    async for result in _central_client_factory(
        un_ignore_list=un_ignore_list,
        client_session=client_session_from_full_session_ccu,
        aio_xml_rpc_proxy=aio_xml_rpc_proxy_from_full_session_ccu,
    ):
        yield result


@pytest.fixture
async def central_client_factory_with_pydevccu_client(
    un_ignore_list: list[str] | None,
    aio_xml_rpc_proxy_from_full_session_pydevccu,
) -> Generator[tuple[CentralUnit, Client | Mock, helper.FactoryWithClient]]:
    """Yield central factory using pydevccu XML-RPC proxy."""
    async for result in _central_client_factory(
        un_ignore_list=un_ignore_list,
        client_session=None,
        aio_xml_rpc_proxy=aio_xml_rpc_proxy_from_full_session_pydevccu,
    ):
        yield result


async def _central_client_factory(
    un_ignore_list: list[str] | None,
    client_session,
    aio_xml_rpc_proxy,
) -> tuple[CentralUnit, Client | Mock, helper.FactoryWithClient]:
    """Return central factory."""
    factory = helper.FactoryWithClient(client_session=client_session, xml_proxy=aio_xml_rpc_proxy)
    central_client = await factory.get_default_central(
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
async def session_recorder_from_full_session_ccu() -> SessionRecorder:
    """Provide a SessionRecorder preloaded from the randomized full session JSON file."""
    return await _session_recorder_session(file_name=const.FULL_SESSION_RANDOMIZED_CCU)


@pytest.fixture
async def session_recorder_from_full_session_pydevccu() -> SessionRecorder:
    """Provide a SessionRecorder preloaded from the randomized full session JSON file."""
    return await _session_recorder_session(file_name=const.FULL_SESSION_RANDOMIZED_PYDEVCCU)


async def _session_recorder_session(*, file_name: str) -> SessionRecorder:
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

    central = _CentralStub()
    # ttl_seconds=0 -> no expiry in tests; refresh_on_get disabled for deterministic reads
    recorder = SessionRecorder(central=central, active=False, ttl_seconds=0, refresh_on_get=False)

    file_path = os.path.join(os.path.dirname(__file__), "data", file_name)
    await recorder.load(file_path=file_path)
    return recorder


@pytest.fixture
async def client_session_from_full_session_ccu(
    session_recorder_from_full_session_ccu: SessionRecorder,
) -> ClientSession:
    """Return a ClientSession-like fixture that answers via SessionRecorder (JSON-RPC)."""
    return await _client_session(recorder=session_recorder_from_full_session_ccu)


@pytest.fixture
async def client_session_from_full_session_pydevccu(
    session_recorder_from_full_session_pydevccu: SessionRecorder,
) -> ClientSession:
    """Return a ClientSession-like fixture that answers via SessionRecorder (JSON-RPC)."""
    return await _client_session(recorder=session_recorder_from_full_session_pydevccu)


async def _client_session(*, recorder: SessionRecorder) -> ClientSession:
    """
    Provide a ClientSession-like fixture that answers via SessionRecorder (JSON-RPC).

    Any POST request will be answered by looking up the latest recorded
    JSON-RPC response in the session recorder using the provided method and params.
    """

    class _MockResponse:
        def __init__(self, json_data: dict | None) -> None:
            # If no match is found, emulate backend error payload
            self._json = json_data or {
                "result": None,
                "error": {"name": "-1", "code": -1, "message": "Not found in session recorder"},
                "id": 0,
            }
            self.status = 200

        async def json(self, encoding: str | None = None):  # mimic aiohttp API
            return self._json

        async def read(self) -> bytes:
            return orjson.dumps(self._json)

    class _MockClientSession:
        async def post(
            self, *, url: str, data: bytes | bytearray | str | None = None, headers=None, timeout=None, ssl=None
        ):
            # Payload is produced by AioJsonRpcAioHttpClient via orjson.dumps
            if isinstance(data, (bytes, bytearray)):
                payload = orjson.loads(data)
            elif isinstance(data, str):
                payload = orjson.loads(data.encode(UTF_8))
            else:
                payload = {}

            method = payload.get("method")
            params = payload.get("params")

            json_data = recorder.get_latest_response_by_params(
                rpc_type=RPCType.JSON_RPC,
                method=str(method) if method is not None else "",
                params=params,
            )
            return _MockResponse(json_data)

        async def close(self) -> None:  # compatibility
            return None

    return cast(ClientSession, _MockClientSession())


@pytest.fixture
async def aio_xml_rpc_proxy_from_full_session_ccu(
    session_recorder_from_full_session_ccu: SessionRecorder,
) -> BaseRpcProxy:
    """Return an AioXmlRpcProxy-like fixture that answers via SessionRecorder (XML-RPC)."""
    return await _aio_xml_rpc_proxy(recorder=session_recorder_from_full_session_ccu)


@pytest.fixture
async def aio_xml_rpc_proxy_from_full_session_pydevccu(
    session_recorder_from_full_session_pydevccu: SessionRecorder,
) -> BaseRpcProxy:
    """Return an AioXmlRpcProxy-like fixture that answers via SessionRecorder (XML-RPC)."""
    return await _aio_xml_rpc_proxy(recorder=session_recorder_from_full_session_pydevccu)


async def _aio_xml_rpc_proxy(*, recorder: SessionRecorder) -> BaseRpcProxy:
    """
    Provide an AioXmlRpcProxy-like fixture that answers via SessionRecorder (XML-RPC).

    Any method call like: await proxy.system.listMethods(...)
    will be answered by looking up the latest recorded XML-RPC response
    in the session recorder using the provided method and positional params.
    """

    class _XmlMethod:
        def __init__(self, full_name: str, caller):
            self._name = full_name
            self._caller = caller

        def __getattr__(self, sub: str):
            # Allow chaining like proxy.system.listMethods
            return _XmlMethod(f"{self._name}.{sub}", self._caller)

        async def __call__(self, *args):
            # Forward to caller with collected method name and positional params
            return await self._caller(self._name, *args)

    class _AioXmlRpcProxyFromRecorder:
        def __init__(self) -> None:
            self._recorder = recorder
            self._supported_methods: tuple[str, ...] = ()

        @property
        def supported_methods(self) -> tuple[str, ...]:
            """Return the supported methods."""
            return self._supported_methods

        def __getattr__(self, name: str):
            # Start of method chain
            return _XmlMethod(name, self._invoke)

        async def _invoke(self, method: str, *args):
            params = tuple(args)
            return self._recorder.get_latest_response_by_params(
                rpc_type=RPCType.XML_RPC,
                method=method,
                params=params,
            )

        async def stop(self) -> None:  # compatibility with AioXmlRpcProxy.stop
            return None

        async def do_init(self) -> None:
            """Init the xml rpc proxy."""
            if supported_methods := await self.system.listMethods():
                # ping is missing in VirtualDevices interface but can be used.
                supported_methods.append(_RpcMethod.PING)
                self._supported_methods = tuple(supported_methods)

    return cast(BaseRpcProxy, _AioXmlRpcProxyFromRecorder())
