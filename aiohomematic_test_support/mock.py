"""
Mock implementations for RPC clients with session playback.

This module provides mock RPC proxy implementations that replay pre-recorded
backend responses from session data files. This enables deterministic, fast
testing without live Homematic backend dependencies.

Key Classes
-----------
- **SessionPlayer**: Loads and plays back recorded RPC session data from ZIP archives.
- **get_mock**: Creates mock instances of data points and devices with configurable
  method/property exclusions.
- **get_xml_rpc_proxy**: Returns mock XML-RPC proxy with session playback.
- **get_client_session**: Returns mock aiohttp ClientSession for JSON-RPC tests.

Session Playback
----------------
Session data is stored in ZIP archives containing JSON files with recorded
RPC method calls and responses. The SessionPlayer replays these responses
when tests invoke RPC methods:

    player = SessionPlayer(session_data_path="tests/data/ccu_full.zip")
    proxy = get_xml_rpc_proxy(player=player, interface="BidCos-RF")

    # Calls return pre-recorded responses
    devices = await proxy.listDevices()

This approach provides:
- Fast test execution (no network I/O)
- Reproducible results (same responses every time)
- Offline testing (no backend required)

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
import contextlib
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
from aiohomematic.store.persistent import _cleanup_params_for_session, _freeze_params, _unfreeze_params
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

                    if "get_backend_info" in params[_JsonKey.SCRIPT]:
                        return _MockResponse(
                            json_data={
                                _JsonKey.ID: 0,
                                _JsonKey.RESULT: const.BACKEND_INFO_JSON,
                                _JsonKey.ERROR: None,
                            }
                        )

                if method == _JsonRpcMethod.INTERFACE_SET_VALUE:
                    await self._central.event_coordinator.data_point_event(
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
                            await self._central.event_coordinator.data_point_event(
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

        def clear_connection_issue(self) -> None:
            """Clear connection issue (no-op for test mock)."""

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
                await self._central.event_coordinator.data_point_event(
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
                interface_id = self._central.client_coordinator.primary_client.interface_id  # type: ignore[union-attr]
                for param, value in values.items():
                    await self._central.event_coordinator.data_point_event(
                        interface_id=interface_id, channel_address=channel_address, parameter=param, value=value
                    )

        async def setValue(self, channel_address: str, parameter: str, value: Any, rx_mode: Any | None = None) -> None:
            """Set a value."""
            if self._central:
                await self._central.event_coordinator.data_point_event(
                    interface_id=self._central.client_coordinator.primary_client.interface_id,  # type: ignore[union-attr]
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


def _get_instance_attributes(instance: Any) -> set[str]:
    """
    Get all instance attribute names, supporting both __dict__ and __slots__.

    For classes with __slots__, iterates through the class hierarchy to collect
    all slot names. For classes with __dict__, returns the keys of __dict__.
    Handles hybrid classes that have both __slots__ and __dict__.

    Why this is needed:
        Python classes can store instance attributes in two ways:
        1. __dict__: A dictionary attached to each instance (default behavior)
        2. __slots__: Pre-declared attribute names stored more efficiently

        When copying attributes to a mock, we can't just use instance.__dict__
        because __slots__-based classes don't have __dict__ (or have a limited one).
        We must inspect the class hierarchy to find all declared slots.

    Algorithm:
        1. Walk the Method Resolution Order (MRO) to find all classes in hierarchy
        2. For each class with __slots__, collect slot names (skip internal ones)
        3. Verify each slot actually has a value on this instance (getattr check)
        4. Also collect any __dict__ attributes if the instance has __dict__
        5. Return the union of all found attribute names
    """
    attrs: set[str] = set()

    # Walk the class hierarchy via MRO (Method Resolution Order).
    # __slots__ are inherited but each class defines its own slots separately,
    # so we must check every class in the hierarchy.
    for cls in type(instance).__mro__:
        if hasattr(cls, "__slots__"):
            for slot in cls.__slots__:
                # Skip internal slots like __dict__ and __weakref__ which are
                # automatically added by Python when a class uses __slots__
                if not slot.startswith("__"):
                    try:
                        # Only include if the attribute actually exists on the instance.
                        # Slots can be declared but unset (raises AttributeError).
                        getattr(instance, slot)
                        attrs.add(slot)
                    except AttributeError:
                        # Slot is declared but not initialized on this instance
                        pass

    # Also include __dict__ attributes if the instance has __dict__.
    # Some classes have both __slots__ and __dict__ (e.g., if a parent class
    # doesn't use __slots__, or if __dict__ is explicitly in __slots__).
    if hasattr(instance, "__dict__"):
        attrs.update(instance.__dict__.keys())

    return attrs


def get_mock(
    *, instance: Any, exclude_methods: set[str] | None = None, include_properties: set[str] | None = None, **kwargs: Any
) -> Any:
    """
    Create a mock that wraps an instance with proper property delegation.

    Supports both __dict__-based and __slots__-based classes. Properties are
    delegated dynamically to the wrapped instance to ensure current values
    are always returned.

    Problem solved:
        MagicMock(wraps=instance) only delegates method calls, not property access.
        When you access mock.some_property, MagicMock returns the value that was
        captured at mock creation time, not the current value on the wrapped instance.
        This causes test failures when the wrapped instance's state changes after
        the mock is created (e.g., client.available changes from False to True
        after initialize_proxy() is called).

    Solution:
        Create a dynamic MagicMock subclass with property descriptors that delegate
        to the wrapped instance on every access. This ensures properties always
        return current values.

    Algorithm:
        1. If already a Mock, just sync attributes from wrapped instance
        2. Identify all properties on the instance's class
        3. Create a MagicMock subclass with delegating property descriptors
        4. Create mock instance with spec and wraps
        5. Copy instance attributes (supports both __slots__ and __dict__)
        6. Copy non-mockable methods directly to mock
    """
    if exclude_methods is None:
        exclude_methods = set()
    if include_properties is None:
        include_properties = set()

    # Early return: if already a Mock, just refresh attributes from wrapped instance
    if isinstance(instance, Mock):
        if hasattr(instance, "_mock_wraps") and instance._mock_wraps is not None:
            for attr in _get_instance_attributes(instance._mock_wraps):
                with contextlib.suppress(AttributeError, TypeError):
                    setattr(instance, attr, getattr(instance._mock_wraps, attr))
        return instance

    # Step 1: Identify all @property decorated attributes on the class
    # These need special handling because MagicMock doesn't delegate property access
    property_names = _get_properties(data_object=instance, decorator=property)

    # Step 2: Create a dynamic MagicMock subclass
    # We add property descriptors to this subclass that delegate to _mock_wraps.
    # This is the key technique: property descriptors on the class take precedence
    # over MagicMock's attribute access, allowing us to intercept property reads.
    class _DynamicMock(MagicMock):
        pass

    # Helper factory functions to create closures with correct name binding.
    # Using a factory function ensures each property gets its own 'name' variable,
    # avoiding the classic lambda closure bug where all properties would share
    # the last loop value.
    def _make_getter(name: str) -> Callable[[Any], Any]:
        """Create a getter that delegates to the wrapped instance."""

        def getter(self: Any) -> Any:
            # Access _mock_wraps which holds the original instance
            return getattr(self._mock_wraps, name)

        return getter

    def _make_setter(name: str) -> Callable[[Any, Any], None]:
        """Create a setter that delegates to the wrapped instance."""

        def setter(self: Any, value: Any) -> None:
            setattr(self._mock_wraps, name, value)

        return setter

    # Step 3: Add property descriptors to the dynamic subclass
    for prop_name in property_names:
        # Skip properties that should be mocked or overridden via kwargs
        if prop_name not in include_properties and prop_name not in kwargs:
            # Check if the original property has a setter (is writable)
            prop_descriptor = getattr(type(instance), prop_name, None)
            if prop_descriptor is not None and getattr(prop_descriptor, "fset", None) is not None:
                # Writable property: create descriptor with both getter and setter
                setattr(
                    _DynamicMock,
                    prop_name,
                    property(_make_getter(prop_name), _make_setter(prop_name)),
                )
            else:
                # Read-only property: create descriptor with getter only
                setattr(
                    _DynamicMock,
                    prop_name,
                    property(_make_getter(prop_name)),
                )

    # Step 4: Create the mock instance
    # spec=instance: ensures mock only allows access to attributes that exist on instance
    # wraps=instance: delegates method calls to the real instance
    mock = _DynamicMock(spec=instance, wraps=instance, **kwargs)

    # Step 5: Copy instance attributes to mock
    # This handles both __slots__ and __dict__ based classes via _get_instance_attributes()
    for attr in _get_instance_attributes(instance):
        with contextlib.suppress(AttributeError, TypeError):
            setattr(mock, attr, getattr(instance, attr))

    # Step 6: Copy non-mockable methods directly
    # Some methods (like bound methods or special attributes) need to be copied
    # directly rather than being mocked
    try:
        for method_name in [
            prop
            for prop in _get_not_mockable_method_names(instance=instance, exclude_methods=exclude_methods)
            if prop not in include_properties and prop not in kwargs and prop not in property_names
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
        frozen_params = _freeze_params(params=_cleanup_params_for_session(params=params))

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
