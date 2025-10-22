"""Helpers for tests."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
import importlib.resources
import json
import logging
import os
from typing import Any, Final, cast
from unittest.mock import MagicMock, Mock, patch
import zipfile

from aiohttp import ClientSession
import orjson

from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.client import BaseRpcProxy, Client, ClientConfig, InterfaceConfig
from aiohomematic.client.json_rpc import _JsonKey, _JsonRpcMethod
from aiohomematic.client.rpc_proxy import _RpcMethod
from aiohomematic.const import (
    LOCAL_HOST,
    UTF_8,
    BackendSystemEvent,
    DataOperationResult,
    Interface,
    Parameter,
    ParamsetKey,
    RPCType,
    SourceOfDeviceCreation,
)
from aiohomematic.model.custom import CustomDataPoint
from aiohomematic.store.persistent import _freeze_params, _unfreeze_params
from aiohomematic_test_support import const
from aiohomematic_test_support.client_local import ClientLocal, LocalRessources

_LOGGER = logging.getLogger(__name__)

EXCLUDE_METHODS_FROM_MOCKS: Final[list[str]] = []
INCLUDE_PROPERTIES_IN_MOCKS: Final[list[str]] = []


# pylint: disable=protected-access
class FactoryWithLocalClient:
    """Factory for a central with one local client."""

    def __init__(self, *, client_session: ClientSession | None = None):
        """Init the central factory."""
        self._client_session = client_session
        self.system_event_mock = MagicMock()
        self.ha_event_mock = MagicMock()

    async def get_raw_central(
        self,
        *,
        interface_config: InterfaceConfig | None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        interface_configs = {interface_config} if interface_config else set()
        central = CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            interface_configs=interface_configs,
            client_session=self._client_session,
            un_ignore_list=frozenset(un_ignore_list or []),
            ignore_custom_device_definition_models=frozenset(ignore_custom_device_definition_models or []),
            start_direct=True,
        ).create_central()

        central.register_backend_system_callback(cb=self.system_event_mock)
        central.register_homematic_callback(cb=self.ha_event_mock)

        return central

    async def get_unpatched_default_central(
        self,
        *,
        port: int,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        interface_config = InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface=Interface.BIDCOS_RF,
            port=port,
        )

        central = await self.get_raw_central(
            interface_config=interface_config,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        )

        _client = ClientLocal(
            client_config=ClientConfig(
                central=central,
                interface_config=interface_config,
            ),
            local_resources=LocalRessources(
                address_device_translation=address_device_translation,
                ignore_devices_on_create=ignore_devices_on_create if ignore_devices_on_create else [],
            ),
        )
        await _client.init_client()
        client = get_mock(_client) if do_mock_client else _client

        assert central
        assert client
        return central, client

    async def get_default_central(
        self,
        *,
        port: int = const.CCU_MINI_PORT,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        add_sysvars: bool = False,
        add_programs: bool = False,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        central, client = await self.get_unpatched_default_central(
            port=port,
            address_device_translation=address_device_translation,
            do_mock_client=True,
            ignore_devices_on_create=ignore_devices_on_create,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        )

        patch("aiohomematic.central.CentralUnit._get_primary_client", return_value=client).start()
        patch("aiohomematic.client.ClientConfig.create_client", return_value=client).start()
        patch(
            "aiohomematic_test_support.client_local.ClientLocal.get_all_system_variables",
            return_value=const.SYSVAR_DATA if add_sysvars else [],
        ).start()
        patch(
            "aiohomematic_test_support.client_local.ClientLocal.get_all_programs",
            return_value=const.PROGRAM_DATA if add_programs else [],
        ).start()
        patch("aiohomematic.central.CentralUnit._identify_ip_addr", return_value=LOCAL_HOST).start()

        await central.start()
        if new_device_addresses := central._check_for_new_device_addresses():
            await central._create_devices(new_device_addresses=new_device_addresses, source=SourceOfDeviceCreation.INIT)
        await central._init_hub()

        assert central
        assert client
        return central, client


class FactoryWithClient:
    """Factory for a central with one local client."""

    def __init__(
        self,
        *,
        recorder: SessionPlayer,
        address_device_translation: dict[str, str] | None = None,
        ignore_devices_on_create: list[str] | None = None,
    ):
        """Init the central factory."""
        self._client_session = _get_client_session(
            recorder=recorder,
            address_device_translation=address_device_translation,
            ignore_devices_on_create=ignore_devices_on_create,
        )
        self._xml_proxy = _get_xml_rpc_proxy(
            recorder=recorder,
            address_device_translation=address_device_translation,
            ignore_devices_on_create=ignore_devices_on_create,
        )
        self.system_event_mock = MagicMock()
        self.ha_event_mock = MagicMock()

    async def get_raw_central(
        self,
        *,
        interface_config: InterfaceConfig | None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        interface_configs = {interface_config} if interface_config else set()
        central = CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            interface_configs=interface_configs,
            client_session=self._client_session,
            un_ignore_list=frozenset(un_ignore_list or []),
            ignore_custom_device_definition_models=frozenset(ignore_custom_device_definition_models or []),
            start_direct=True,
        ).create_central()

        central.register_backend_system_callback(cb=self.system_event_mock)
        central.register_homematic_callback(cb=self.ha_event_mock)

        return central

    async def get_unpatched_default_central(
        self,
        *,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        interface_config = InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface=Interface.BIDCOS_RF,
            port=2001,
        )

        central = await self.get_raw_central(
            interface_config=interface_config,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        )

        assert central
        self._client_session.set_central(central=central)  # type: ignore[attr-defined]
        self._xml_proxy.set_central(central=central)
        return central

    async def get_default_central(
        self,
        *,
        do_mock_client: bool = True,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        central = await self.get_unpatched_default_central(
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        )

        await self._xml_proxy.do_init()
        patch("aiohomematic.client.ClientConfig._create_xml_rpc_proxy", return_value=self._xml_proxy).start()
        patch("aiohomematic.central.CentralUnit._identify_ip_addr", return_value=LOCAL_HOST).start()

        # Optionally patch client creation to return a mocked client
        if do_mock_client:
            _orig_create_client = ClientConfig.create_client

            async def _mocked_create_client(self: ClientConfig) -> Client | Mock:
                real_client = await _orig_create_client(self)
                return cast(Mock, get_mock(real_client))

            patch("aiohomematic.client.ClientConfig.create_client", _mocked_create_client).start()

        await central.start()

        client = central.primary_client
        assert central
        assert client
        return central, client


def get_prepared_custom_data_point(central: CentralUnit, address: str, channel_no: int) -> CustomDataPoint | None:
    """Return the hm custom_data_point."""
    if cdp := central.get_custom_data_point(address=address, channel_no=channel_no):
        for dp in cdp._data_points.values():
            dp._state_uncertain = False
        return cdp
    return None


def load_device_description(file_name: str) -> Any:
    """Load device description."""
    dev_desc = _load_json_file(anchor="pydevccu", resource="device_descriptions", file_name=file_name)
    assert dev_desc
    return dev_desc


def get_mock(instance: Any, **kwargs: Any) -> Any:
    """Create a mock and copy instance attributes over mock."""
    if isinstance(instance, Mock):
        instance.__dict__.update(instance._mock_wraps.__dict__)
        return instance
    mock = MagicMock(spec=instance, wraps=instance, **kwargs)
    mock.__dict__.update(instance.__dict__)
    try:
        for method_name in [
            prop
            for prop in _get_not_mockable_method_names(instance)
            if prop not in INCLUDE_PROPERTIES_IN_MOCKS and prop not in kwargs
        ]:
            setattr(mock, method_name, getattr(instance, method_name))
    except Exception:
        pass

    return mock


def _get_not_mockable_method_names(instance: Any) -> set[str]:
    """Return all relevant method names for mocking."""
    methods: set[str] = set(_get_properties(data_object=instance, decorator=property))

    for method in dir(instance):
        if method in EXCLUDE_METHODS_FROM_MOCKS:
            methods.add(method)
    return methods


def _get_properties(data_object: Any, decorator: Any) -> set[str]:
    """Return the object attributes by decorator."""
    cls = data_object.__class__

    # Resolve function-based decorators to their underlying property class, if provided
    resolved_decorator: Any = decorator
    if not isinstance(decorator, type):
        resolved_decorator = getattr(decorator, "__property_class__", decorator)

    return {y for y in dir(cls) if isinstance(getattr(cls, y), resolved_decorator)}


def _load_json_file(anchor: str, resource: str, file_name: str) -> Any | None:
    """Load json file from disk into dict."""
    package_path = str(importlib.resources.files(anchor))
    with open(
        file=os.path.join(package_path, resource, file_name),
        encoding=UTF_8,
    ) as fptr:
        return orjson.loads(fptr.read())


async def get_pydev_ccu_central_unit_full(
    port: int,
    client_session: ClientSession | None = None,
) -> CentralUnit:
    """Create and yield central, after all devices have been created."""
    device_event = asyncio.Event()

    def systemcallback(system_event: Any, *args: Any, **kwargs: Any) -> None:
        if system_event == BackendSystemEvent.DEVICES_CREATED:
            device_event.set()

    interface_configs = {
        InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface=Interface.BIDCOS_RF,
            port=port,
        )
    }

    central = CentralConfig(
        name=const.CENTRAL_NAME,
        host=const.CCU_HOST,
        username=const.CCU_USERNAME,
        password=const.CCU_PASSWORD,
        central_id="test1234",
        interface_configs=interface_configs,
        client_session=client_session,
        program_markers=(),
        sysvar_markers=(),
    ).create_central()
    central.register_backend_system_callback(cb=systemcallback)
    await central.start()

    # Wait up to 60 seconds for the DEVICES_CREATED event which signals that all devices are available
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(device_event.wait(), timeout=60)

    return central


def _get_client_session(
    *,
    recorder: SessionPlayer,
    address_device_translation: dict[str, str] | None = None,
    ignore_devices_on_create: list[str] | None = None,
) -> ClientSession:
    """
    Provide a ClientSession-like fixture that answers via SimpleSessionRecorder (JSON-RPC).

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

        async def json(self, encoding: str | None = None) -> dict[str, Any]:  # mimic aiohttp API
            return self._json

        async def read(self) -> bytes:
            return orjson.dumps(self._json)

    class _MockClientSession:
        def __init__(self) -> None:
            """Initialize the mock client session."""
            self._central: CentralUnit | None = None

        def set_central(self, *, central: CentralUnit) -> None:
            """Set the central."""
            self._central = central

        async def post(
            self,
            *,
            url: str,
            data: bytes | bytearray | str | None = None,
            headers: Any = None,
            timeout: Any = None,  # noqa: ASYNC109
            ssl: Any = None,
        ) -> _MockResponse:
            # Payload is produced by AioJsonRpcAioHttpClient via orjson.dumps
            if isinstance(data, (bytes, bytearray)):
                payload = orjson.loads(data)
            elif isinstance(data, str):
                payload = orjson.loads(data.encode(UTF_8))
            else:
                payload = {}

            method = payload.get("method")
            params = payload.get("params")

            if self._central:
                if method == _JsonRpcMethod.INTERFACE_SET_VALUE:
                    await self._central.data_point_event(
                        interface_id=params[_JsonKey.INTERFACE],
                        channel_address=params[_JsonKey.ADDRESS],
                        parameter=params[_JsonKey.VALUE_KEY],
                        value=params[_JsonKey.VALUE],
                    )
                    return _MockResponse({"result": "200"})
                if method == _JsonRpcMethod.INTERFACE_PUT_PARAMSET:
                    if params[_JsonKey.PARAMSET_KEY] == ParamsetKey.VALUES:
                        interface_id = params[_JsonKey.INTERFACE]
                        channel_address = params[_JsonKey.ADDRESS]
                        values = params[_JsonKey.SET]
                        for param, value in values.items():
                            await self._central.data_point_event(
                                interface_id=interface_id,
                                channel_address=channel_address,
                                parameter=param,
                                value=value,
                            )
                    return _MockResponse({"result": "200"})

            json_data = recorder.get_latest_response_by_params(
                rpc_type=RPCType.JSON_RPC,
                method=str(method) if method is not None else "",
                params=params,
            )
            # if method == _JsonRpcMethod.INTERFACE_LIST_DEVICES:
            #     if address_device_translation:
            #         devices: dict[str, Any] = {}
            #         for address, device in json_data["result"].items():
            #             if address in address_device_translation:
            #                 device["ADDRESS"] = address_device_translation[address]
            return _MockResponse(json_data)

        async def close(self) -> None:  # compatibility
            return None

    return cast(ClientSession, _MockClientSession())


def _get_xml_rpc_proxy(  # noqa: C901
    *,
    recorder: SessionPlayer,
    address_device_translation: dict[str, str] | None = None,
    ignore_devices_on_create: list[str] | None = None,
) -> BaseRpcProxy:
    """
    Provide an BaseRpcProxy-like fixture that answers via SimpleSessionRecorder (XML-RPC).

    Any method call like: await proxy.system.listMethods(...)
    will be answered by looking up the latest recorded XML-RPC response
    in the session recorder using the provided method and positional params.
    """

    class _Method:
        def __init__(self, full_name: str, caller: Any) -> None:
            self._name = full_name
            self._caller = caller

        def __getattr__(self, sub: str) -> _Method:
            # Allow chaining like proxy.system.listMethods
            return _Method(f"{self._name}.{sub}", self._caller)

        async def __call__(self, *args: Any) -> Any:
            # Forward to caller with collected method name and positional params
            return await self._caller(self._name, *args)

    class _AioXmlRpcProxyFromRecorder:
        def __init__(self) -> None:
            self._recorder = recorder
            self._supported_methods: tuple[str, ...] = ()
            self._central: CentralUnit | None = None

        def set_central(self, *, central: CentralUnit) -> None:
            """Set the central."""
            self._central = central

        @property
        def supported_methods(self) -> tuple[str, ...]:
            """Return the supported methods."""
            return self._supported_methods

        async def setValue(self, channel_address: str, parameter: str, value: Any, rx_mode: Any | None = None) -> None:
            """Set a value."""
            if self._central:
                await self._central.data_point_event(
                    interface_id=self._central.primary_client.interface_id,  # type: ignore[union-attr]
                    channel_address=channel_address,
                    parameter=parameter,
                    value=value,
                )

        async def putParamset(
            self, channel_address: str, paramset_key: str, values: Any, rx_mode: Any | None = None
        ) -> None:
            """Set a paramset."""
            if self._central and paramset_key == ParamsetKey.VALUES:
                interface_id = self._central.primary_client.interface_id  # type: ignore[union-attr]
                for param, value in values.items():
                    await self._central.data_point_event(
                        interface_id=interface_id, channel_address=channel_address, parameter=param, value=value
                    )

        async def ping(self, callerId: str) -> None:
            """Answer ping with pong."""
            if self._central:
                await self._central.data_point_event(
                    interface_id=callerId,
                    channel_address="",
                    parameter=Parameter.PONG,
                    value=callerId,
                )

        async def clientServerInitialized(self, interface_id: str) -> None:
            """Answer clientServerInitialized with pong."""
            await self.ping(callerId=interface_id)

        async def listDevices(self) -> list[Any]:
            """Return a list of devices."""
            devices = self._recorder.get_latest_response_by_params(
                rpc_type=RPCType.XML_RPC,
                method="listDevices",
                params="()",
            )

            new_devices = []
            if ignore_devices_on_create is None and address_device_translation is None:
                return cast(list[Any], devices)

            for device in devices:
                if ignore_devices_on_create is not None and (
                    device["ADDRESS"] in ignore_devices_on_create or device["PARENT"] in ignore_devices_on_create
                ):
                    continue
                if address_device_translation is not None:
                    if (
                        device["ADDRESS"] in address_device_translation
                        or device["PARENT"] in address_device_translation
                    ):
                        new_devices.append(device)
                else:
                    new_devices.append(device)

            return new_devices

        def __getattr__(self, name: str) -> Any:
            # Start of method chain
            return _Method(name, self._invoke)

        async def _invoke(self, method: str, *args: Any) -> Any:
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


async def get_session_player(*, file_name: str) -> SessionPlayer:
    """Provide a SessionPlayer preloaded from the randomized full session JSON file."""
    player = SessionPlayer(file_id=file_name)
    file_path = os.path.join(os.path.dirname(__file__), "data", file_name)
    await player.load(file_path=file_path)
    return player


class SessionPlayer:
    """Player for sessions."""

    _store: dict[str, dict[str, dict[str, dict[str, dict[int, Any]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    )

    def __init__(self, *, file_id: str) -> None:
        """Initialize the session recorder."""
        self._file_id = file_id

    async def load(self, *, file_path: str) -> DataOperationResult:
        """
        Load data from disk into the dictionary.

        Supports plain JSON files and ZIP archives containing a JSON file.
        When a ZIP archive is provided, the first JSON member inside the archive
        will be loaded.
        """

        if self._store[self._file_id]:
            return DataOperationResult.NO_LOAD

        if not os.path.exists(file_path):
            return DataOperationResult.NO_LOAD

        def _perform_load() -> DataOperationResult:
            try:
                if zipfile.is_zipfile(file_path):
                    with zipfile.ZipFile(file_path, mode="r") as zf:
                        # Prefer json files; pick the first .json entry if available
                        if not (json_members := [n for n in zf.namelist() if n.lower().endswith(".json")]):
                            return DataOperationResult.LOAD_FAIL
                        raw = zf.read(json_members[0]).decode(UTF_8)
                        data = json.loads(raw)
                else:
                    with open(file=file_path, encoding=UTF_8) as file_pointer:
                        data = json.loads(file_pointer.read())

                self._store[self._file_id] = data
            except (json.JSONDecodeError, zipfile.BadZipFile, UnicodeDecodeError, OSError):
                return DataOperationResult.LOAD_FAIL
            return DataOperationResult.LOAD_SUCCESS

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _perform_load)

    def get_latest_response_by_method(self, *, rpc_type: str, method: str) -> list[tuple[Any, Any]]:
        """Return latest non-expired responses for a given (rpc_type, method)."""
        result: list[Any] = []
        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store[self._file_id].get(rpc_type)):
            return result
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return result
        # For each parameter, choose the response at the latest timestamp.
        for frozen_params, bucket_by_ts in bucket_by_parameter.items():
            if not bucket_by_ts:
                continue
            try:
                latest_ts = max(bucket_by_ts.keys())
            except ValueError:
                continue
            resp = bucket_by_ts[latest_ts]
            params = _unfreeze_params(frozen_params=frozen_params)

            result.append((params, resp))
        return result

    def get_latest_response_by_params(
        self,
        *,
        rpc_type: str,
        method: str,
        params: Any,
    ) -> Any:
        """Return latest non-expired responses for a given (rpc_type, method, params)."""
        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store[self._file_id].get(rpc_type)):
            return None
        if not (bucket_by_parameter := bucket_by_method.get(method)):
            return None
        frozen_params = _freeze_params(params=params)

        # For each parameter, choose the response at the latest timestamp.
        if (bucket_by_ts := bucket_by_parameter.get(frozen_params)) is None:
            return None

        try:
            latest_ts = max(bucket_by_ts.keys())
            return bucket_by_ts[latest_ts]
        except ValueError:
            return None
