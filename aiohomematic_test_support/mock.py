"""Mocks for tests."""

from __future__ import annotations

import asyncio
from collections import defaultdict
import json
import logging
import os
from typing import Any, cast
from unittest.mock import MagicMock, Mock
import zipfile

from aiohttp import ClientSession
import orjson

from aiohomematic.central import CentralUnit
from aiohomematic.client import BaseRpcProxy
from aiohomematic.client.json_rpc import _JsonKey, _JsonRpcMethod
from aiohomematic.client.rpc_proxy import _RpcMethod
from aiohomematic.const import UTF_8, DataOperationResult, Parameter, ParamsetKey, RPCType
from aiohomematic.store.persistent import _freeze_params, _unfreeze_params
from aiohomematic_test_support import const

_LOGGER = logging.getLogger(__name__)

# pylint: disable=protected-access


def _get_not_mockable_method_names(*, instance: Any, exclude_methods: set[str]) -> set[str]:
    """Return all relevant method names for mocking."""
    methods: set[str] = set(_get_properties(data_object=instance, decorator=property))

    for method in dir(instance):
        if method in exclude_methods:
            methods.add(method)
    return methods


def _get_properties(*, data_object: Any, decorator: Any) -> set[str]:
    """Return the object attributes by decorator."""
    cls = data_object.__class__

    # Resolve function-based decorators to their underlying property class, if provided
    resolved_decorator: Any = decorator
    if not isinstance(decorator, type):
        resolved_decorator = getattr(decorator, "__property_class__", decorator)

    return {y for y in dir(cls) if isinstance(getattr(cls, y), resolved_decorator)}


def get_client_session(  # noqa: C901
    *,
    player: SessionPlayer,
    address_device_translation: set[str] | None = None,
    ignore_devices_on_create: list[str] | None = None,
) -> ClientSession:
    """
    Provide a ClientSession-like fixture that answers via SessionPlayer(JSON-RPC).

    Any POST request will be answered by looking up the latest recorded
    JSON-RPC response in the session player using the provided method and params.
    """

    class _MockResponse:
        def __init__(self, *, json_data: dict[str, Any] | None) -> None:
            # If no match is found, emulate backend error payload
            self._json: dict[str, Any] = json_data or {
                _JsonKey.RESULT: None,
                _JsonKey.ERROR: {"name": "-1", "code": -1, "message": "Not found in session player"},
                _JsonKey.ID: 0,
            }
            self.status = 200

        async def json(self, *, encoding: str | None = None) -> dict[str, Any]:  # mimic aiohttp API
            return self._json

        async def read(self) -> bytes:
            return orjson.dumps(self._json)

    class _MockClientSession:
        def __init__(self) -> None:
            """Initialize the mock client session."""
            self._central: CentralUnit | None = None

        async def close(self) -> None:  # compatibility
            return None

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
                if method in (
                    _JsonRpcMethod.PROGRAM_EXECUTE,
                    _JsonRpcMethod.SYSVAR_SET_BOOL,
                    _JsonRpcMethod.SYSVAR_SET_FLOAT,
                    _JsonRpcMethod.SESSION_LOGOUT,
                ):
                    return _MockResponse(json_data={_JsonKey.ID: 0, _JsonKey.RESULT: "200", _JsonKey.ERROR: None})
                if method == _JsonRpcMethod.SYSVAR_GET_ALL:
                    return _MockResponse(
                        json_data={_JsonKey.ID: 0, _JsonKey.RESULT: const.SYSVAR_DATA_JSON, _JsonKey.ERROR: None}
                    )
                if method == _JsonRpcMethod.PROGRAM_GET_ALL:
                    return _MockResponse(
                        json_data={_JsonKey.ID: 0, _JsonKey.RESULT: const.PROGRAM_DATA_JSON, _JsonKey.ERROR: None}
                    )
                if method == _JsonRpcMethod.REGA_RUN_SCRIPT:
                    if "get_program_descriptions" in params[_JsonKey.SCRIPT]:
                        return _MockResponse(
                            json_data={
                                _JsonKey.ID: 0,
                                _JsonKey.RESULT: const.PROGRAM_DATA_JSON_DESCRIPTION,
                                _JsonKey.ERROR: None,
                            }
                        )

                    if "get_system_variable_descriptions" in params[_JsonKey.SCRIPT]:
                        return _MockResponse(
                            json_data={
                                _JsonKey.ID: 0,
                                _JsonKey.RESULT: const.SYSVAR_DATA_JSON_DESCRIPTION,
                                _JsonKey.ERROR: None,
                            }
                        )

                if method == _JsonRpcMethod.INTERFACE_SET_VALUE:
                    await self._central.data_point_event(
                        interface_id=params[_JsonKey.INTERFACE],
                        channel_address=params[_JsonKey.ADDRESS],
                        parameter=params[_JsonKey.VALUE_KEY],
                        value=params[_JsonKey.VALUE],
                    )
                    return _MockResponse(json_data={_JsonKey.ID: 0, _JsonKey.RESULT: "200", _JsonKey.ERROR: None})
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
                    return _MockResponse(json_data={_JsonKey.RESULT: "200", _JsonKey.ERROR: None})

            json_data = player.get_latest_response_by_params(
                rpc_type=RPCType.JSON_RPC,
                method=str(method) if method is not None else "",
                params=params,
            )
            if method == _JsonRpcMethod.INTERFACE_LIST_DEVICES and (
                ignore_devices_on_create is not None or address_device_translation is not None
            ):
                new_devices = []
                for dd in json_data[_JsonKey.RESULT]:
                    if ignore_devices_on_create is not None and (
                        dd["address"] in ignore_devices_on_create or dd["parent"] in ignore_devices_on_create
                    ):
                        continue
                    if address_device_translation is not None:
                        if dd["address"] in address_device_translation or dd["parent"] in address_device_translation:
                            new_devices.append(dd)
                    else:
                        new_devices.append(dd)

                json_data[_JsonKey.RESULT] = new_devices
            return _MockResponse(json_data=json_data)

        def set_central(self, *, central: CentralUnit) -> None:
            """Set the central."""
            self._central = central

    return cast(ClientSession, _MockClientSession())


def get_xml_rpc_proxy(  # noqa: C901
    *,
    player: SessionPlayer,
    address_device_translation: set[str] | None = None,
    ignore_devices_on_create: list[str] | None = None,
) -> BaseRpcProxy:
    """
    Provide an BaseRpcProxy-like fixture that answers via SessionPlayer (XML-RPC).

    Any method call like: await proxy.system.listMethods(...)
    will be answered by looking up the latest recorded XML-RPC response
    in the session player using the provided method and positional params.
    """

    class _Method:
        def __init__(self, full_name: str, caller: Any) -> None:
            self._name = full_name
            self._caller = caller

        async def __call__(self, *args: Any) -> Any:
            # Forward to caller with collected method name and positional params
            return await self._caller(self._name, *args)

        def __getattr__(self, sub: str) -> _Method:
            # Allow chaining like proxy.system.listMethods
            return _Method(f"{self._name}.{sub}", self._caller)

    class _AioXmlRpcProxyFromSession:
        def __init__(self) -> None:
            self._player = player
            self._supported_methods: tuple[str, ...] = ()
            self._central: CentralUnit | None = None

        def __getattr__(self, name: str) -> Any:
            # Start of method chain
            return _Method(name, self._invoke)

        @property
        def supported_methods(self) -> tuple[str, ...]:
            """Return the supported methods."""
            return self._supported_methods

        async def clientServerInitialized(self, interface_id: str) -> None:
            """Answer clientServerInitialized with pong."""
            await self.ping(callerId=interface_id)

        async def do_init(self) -> None:
            """Init the xml rpc proxy."""
            if supported_methods := await self.system.listMethods():
                # ping is missing in VirtualDevices interface but can be used.
                supported_methods.append(_RpcMethod.PING)
                self._supported_methods = tuple(supported_methods)

        async def getAllSystemVariables(self) -> dict[str, Any]:
            """Return all system variables."""
            return const.SYSVAR_DATA_XML

        async def getParamset(self, channel_address: str, paramset: str) -> Any:
            """Set a value."""
            if self._central:
                result = self._player.get_latest_response_by_params(
                    rpc_type=RPCType.XML_RPC,
                    method="getParamset",
                    params=(channel_address, paramset),
                )
                return result if result else {}

        async def listDevices(self) -> list[Any]:
            """Return a list of devices."""
            devices = self._player.get_latest_response_by_params(
                rpc_type=RPCType.XML_RPC,
                method="listDevices",
                params="()",
            )

            new_devices = []
            if ignore_devices_on_create is None and address_device_translation is None:
                return cast(list[Any], devices)

            for dd in devices:
                if ignore_devices_on_create is not None and (
                    dd["ADDRESS"] in ignore_devices_on_create or dd["PARENT"] in ignore_devices_on_create
                ):
                    continue
                if address_device_translation is not None:
                    if dd["ADDRESS"] in address_device_translation or dd["PARENT"] in address_device_translation:
                        new_devices.append(dd)
                else:
                    new_devices.append(dd)

            return new_devices

        async def ping(self, callerId: str) -> None:
            """Answer ping with pong."""
            if self._central:
                await self._central.data_point_event(
                    interface_id=callerId,
                    channel_address="",
                    parameter=Parameter.PONG,
                    value=callerId,
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

        async def setValue(self, channel_address: str, parameter: str, value: Any, rx_mode: Any | None = None) -> None:
            """Set a value."""
            if self._central:
                await self._central.data_point_event(
                    interface_id=self._central.primary_client.interface_id,  # type: ignore[union-attr]
                    channel_address=channel_address,
                    parameter=parameter,
                    value=value,
                )

        def set_central(self, *, central: CentralUnit) -> None:
            """Set the central."""
            self._central = central

        async def stop(self) -> None:  # compatibility with AioXmlRpcProxy.stop
            return None

        async def _invoke(self, method: str, *args: Any) -> Any:
            params = tuple(args)
            return self._player.get_latest_response_by_params(
                rpc_type=RPCType.XML_RPC,
                method=method,
                params=params,
            )

    return cast(BaseRpcProxy, _AioXmlRpcProxyFromSession())


def get_mock(
    *, instance: Any, exclude_methods: set[str] | None = None, include_properties: set[str] | None = None, **kwargs: Any
) -> Any:
    """Create a mock and copy instance attributes over mock."""
    if exclude_methods is None:
        exclude_methods = set()
    if include_properties is None:
        include_properties = set()

    if isinstance(instance, Mock):
        instance.__dict__.update(instance._mock_wraps.__dict__)
        return instance
    mock = MagicMock(spec=instance, wraps=instance, **kwargs)
    mock.__dict__.update(instance.__dict__)
    try:
        for method_name in [
            prop
            for prop in _get_not_mockable_method_names(instance=instance, exclude_methods=exclude_methods)
            if prop not in include_properties and prop not in kwargs
        ]:
            setattr(mock, method_name, getattr(instance, method_name))
    except Exception:
        pass

    return mock


async def get_session_player(*, file_name: str) -> SessionPlayer:
    """Provide a SessionPlayer preloaded from the randomized full session JSON file."""
    player = SessionPlayer(file_id=file_name)
    if player.supports_file_id(file_id=file_name):
        return player

    for load_fn in const.ALL_SESSION_FILES:
        file_path = os.path.join(os.path.dirname(__file__), "data", load_fn)
        await player.load(file_path=file_path, file_id=load_fn)
    return player


class SessionPlayer:
    """Player for sessions."""

    _store: dict[str, dict[str, dict[str, dict[str, dict[int, Any]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    )

    def __init__(self, *, file_id: str) -> None:
        """Initialize the session player."""
        self._file_id = file_id

    @property
    def _secondary_file_ids(self) -> list[str]:
        """Return the secondary store for the given file_id."""
        return [fid for fid in self._store if fid != self._file_id]

    def get_latest_response_by_method(self, *, rpc_type: str, method: str) -> list[tuple[Any, Any]]:
        """Return latest non-expired responses for a given (rpc_type, method)."""
        if pri_result := self.get_latest_response_by_method_for_file_id(
            file_id=self._file_id,
            rpc_type=rpc_type,
            method=method,
        ):
            return pri_result

        for secondary_file_id in self._secondary_file_ids:
            if sec_result := self.get_latest_response_by_method_for_file_id(
                file_id=secondary_file_id,
                rpc_type=rpc_type,
                method=method,
            ):
                return sec_result
        return pri_result

    def get_latest_response_by_method_for_file_id(
        self, *, file_id: str, rpc_type: str, method: str
    ) -> list[tuple[Any, Any]]:
        """Return latest non-expired responses for a given (rpc_type, method)."""
        result: list[Any] = []
        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store[file_id].get(rpc_type)):
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
        if pri_result := self.get_latest_response_by_params_for_file_id(
            file_id=self._file_id,
            rpc_type=rpc_type,
            method=method,
            params=params,
        ):
            return pri_result

        for secondary_file_id in self._secondary_file_ids:
            if sec_result := self.get_latest_response_by_params_for_file_id(
                file_id=secondary_file_id,
                rpc_type=rpc_type,
                method=method,
                params=params,
            ):
                return sec_result
        return pri_result

    def get_latest_response_by_params_for_file_id(
        self,
        *,
        file_id: str,
        rpc_type: str,
        method: str,
        params: Any,
    ) -> Any:
        """Return latest non-expired responses for a given (rpc_type, method, params)."""
        # Access store safely to avoid side effects from creating buckets.
        if not (bucket_by_method := self._store[file_id].get(rpc_type)):
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

    async def load(self, *, file_path: str, file_id: str) -> DataOperationResult:
        """
        Load data from disk into the dictionary.

        Supports plain JSON files and ZIP archives containing a JSON file.
        When a ZIP archive is provided, the first JSON member inside the archive
        will be loaded.
        """

        if self.supports_file_id(file_id=file_id):
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

                self._store[file_id] = data
            except (json.JSONDecodeError, zipfile.BadZipFile, UnicodeDecodeError, OSError):
                return DataOperationResult.LOAD_FAIL
            return DataOperationResult.LOAD_SUCCESS

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _perform_load)

    def supports_file_id(self, *, file_id: str) -> bool:
        """Return whether the session player supports the given file_id."""
        return file_id in self._store
