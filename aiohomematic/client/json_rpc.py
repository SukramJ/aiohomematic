# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Asynchronous JSON-RPC client for Homematic CCU-compatible backends.

Overview
--------
JsonRpcAioHttpClient wraps CCU JSON-RPC endpoints to provide:
- Login and session handling with automatic renewal
- Execution of ReGa scripts and JSON-RPC methods
- Access to system variables, programs, and device/channel metadata
- Reading/writing paramsets and values where supported
- Robust error handling, optional TLS, and rate-limiting via semaphores

Usage
-----
This client is usually managed by CentralUnit through ClientJsonCCU, but can be
used directly for advanced tasks. Typical flow:

    client = JsonRpcAioHttpClient(username, password, device_url, connection_state, aiohttp_session, tls=True)
    await client.get_system_information()
    data = await client.get_all_device_data(interface)

Notes
-----
- Some JSON-RPC methods are backend/firmware dependent. The client detects and
  store supported methods at runtime.
- Binary/text encodings are handled carefully (UTF-8 / ISO-8859-1) for script IO.

"""

from __future__ import annotations

import asyncio
from asyncio import Semaphore
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from functools import partial
from json import JSONDecodeError
import logging
import os
from pathlib import Path
from ssl import SSLContext
from typing import Any, Final
from urllib.parse import unquote

from aiohttp import (
    ClientConnectorCertificateError,
    ClientConnectorError,
    ClientError,
    ClientResponse,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
    TCPConnector,
)
import orjson

from aiohomematic import central as hmcu, i18n
from aiohomematic.async_support import Looper
from aiohomematic.client._rpc_errors import RpcContext, map_jsonrpc_error
from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from aiohomematic.const import (
    ALWAYS_ENABLE_SYSVARS_BY_ID,
    DEFAULT_INCLUDE_INTERNAL_PROGRAMS,
    DEFAULT_INCLUDE_INTERNAL_SYSVARS,
    ISO_8859_1,
    JSON_SESSION_AGE,
    LOGIN_BACKOFF_MULTIPLIER,
    LOGIN_INITIAL_BACKOFF_SECONDS,
    LOGIN_MAX_BACKOFF_SECONDS,
    LOGIN_MAX_FAILED_ATTEMPTS,
    MAX_CONCURRENT_HTTP_SESSIONS,
    PATH_JSON_RPC,
    REGA_SCRIPT_PATH,
    RENAME_SYSVAR_BY_NAME,
    TIMEOUT,
    UTF_8,
    BackupStatus,
    BackupStatusData,
    CCUType,
    DescriptionMarker,
    DeviceDescription,
    HubValueType,
    InboxDeviceData,
    Interface,
    ParameterData,
    ParamsetKey,
    ProgramData,
    RegaScript,
    ServiceMessageData,
    ServiceMessageType,
    SystemInformation,
    SystemUpdateData,
    SystemVariableData,
)
from aiohomematic.exceptions import (
    AuthFailure,
    BaseHomematicException,
    CircuitBreakerOpenException,
    ClientException,
    InternalBackendException,
    NoConnectionException,
    UnsupportedException,
)
from aiohomematic.model.support import convert_value
from aiohomematic.property_decorators import hm_property
from aiohomematic.retry import with_retry
from aiohomematic.store import SessionRecorder
from aiohomematic.support import (
    LogContextMixin,
    cleanup_script_for_session_recorder,
    cleanup_text_from_html_tags,
    element_matches_key,
    extract_exc_args,
    get_tls_context,
    is_device_address,
    log_boundary_error,
    parse_sys_var,
)

_LOGGER: Final = logging.getLogger(__name__)


class _JsonKey(StrEnum):
    """Enum for Homematic json keys."""

    ACTION = "action"
    ADDRESS = "address"
    AVAILABLE_FIRMWARE = "available_firmware"
    CHANNELS = "channels"
    CHANNEL_IDS = "channelIds"
    CHECK_SCRIPT_AVAILABLE = "check_script_available"
    CURRENT_FIRMWARE = "current_firmware"
    DESCRIPTION = "description"
    DEVICE_ADDRESS = "device_address"
    DEVICE_NAME = "device_name"
    ERROR = "error"
    FILE = "file"
    FILENAME = "filename"
    HOSTNAME = "hostname"
    ID = "id"
    INSTALL_MODE = "installMode"
    INTERFACE = "interface"
    IS_ACTIVE = "isActive"
    IS_INTERNAL = "isInternal"
    KEY = "key"
    KEYMODE = "keymode"
    LAST_EXECUTE_TIME = "lastExecuteTime"
    MAX_VALUE = "maxValue"
    MESSAGE = "message"
    MIN_VALUE = "minValue"
    MODE = "mode"
    NAME = "name"
    ON = "on"
    PARAMSET_KEY = "paramsetKey"
    PASSWORD = "password"
    PRODUCT = "product"
    RESULT = "result"
    SCRIPT = "script"
    SERIAL = "serial"
    SESSION_ID = "_session_id_"
    SET = "set"
    SID = "sid"
    SIZE = "size"
    STATE = "state"
    STATUS = "status"
    SUCCESS = "success"
    TIME = "time"
    TIMESTAMP = "timestamp"
    TYPE = "type"
    UNIT = "unit"
    UPDATE_AVAILABLE = "update_available"
    URL = "url"
    USERNAME = "username"
    VALUE = "value"
    VALUE_KEY = "valueKey"
    VALUE_LIST = "valueList"
    VERSION = "version"


class _JsonRpcMethod(StrEnum):
    """Enum for Homematic json rpc methods types."""

    CCU_GET_AUTH_ENABLED = "CCU.getAuthEnabled"
    CCU_GET_HTTPS_REDIRECT_ENABLED = "CCU.getHttpsRedirectEnabled"
    CHANNEL_HAS_PROGRAM_IDS = "Channel.hasProgramIds"
    CHANNEL_SET_NAME = "Channel.setName"
    DEVICE_LIST_ALL_DETAIL = "Device.listAllDetail"
    DEVICE_SET_NAME = "Device.setName"
    INTERFACE_GET_DEVICE_DESCRIPTION = "Interface.getDeviceDescription"
    INTERFACE_GET_INSTALL_MODE = "Interface.getInstallMode"
    INTERFACE_GET_MASTER_VALUE = "Interface.getMasterValue"
    INTERFACE_GET_PARAMSET = "Interface.getParamset"
    INTERFACE_GET_PARAMSET_DESCRIPTION = "Interface.getParamsetDescription"
    INTERFACE_GET_VALUE = "Interface.getValue"
    INTERFACE_IS_PRESENT = "Interface.isPresent"
    INTERFACE_LIST_DEVICES = "Interface.listDevices"
    INTERFACE_LIST_INTERFACES = "Interface.listInterfaces"
    INTERFACE_PUT_PARAMSET = "Interface.putParamset"
    INTERFACE_SET_INSTALL_MODE_HMIP = "Interface.setInstallModeHMIP"
    INTERFACE_SET_VALUE = "Interface.setValue"
    PROGRAM_EXECUTE = "Program.execute"
    PROGRAM_GET_ALL = "Program.getAll"
    REGA_RUN_SCRIPT = "ReGa.runScript"
    ROOM_GET_ALL = "Room.getAll"
    SESSION_LOGIN = "Session.login"
    SESSION_LOGOUT = "Session.logout"
    SESSION_RENEW = "Session.renew"
    SUBSECTION_GET_ALL = "Subsection.getAll"
    SYSTEM_LIST_METHODS = "system.listMethods"
    SYSVAR_DELETE_SYSVAR_BY_NAME = "SysVar.deleteSysVarByName"
    SYSVAR_GET_ALL = "SysVar.getAll"
    SYSVAR_GET_VALUE_BY_NAME = "SysVar.getValueByName"
    SYSVAR_SET_BOOL = "SysVar.setBool"
    SYSVAR_SET_FLOAT = "SysVar.setFloat"


# Methods allowed through even when circuit breaker is open (session management)
_CIRCUIT_BREAKER_BYPASS_METHODS: Final = (
    _JsonRpcMethod.SESSION_LOGIN,
    _JsonRpcMethod.SESSION_LOGOUT,
    _JsonRpcMethod.SESSION_RENEW,
)


class AioJsonRpcAioHttpClient(LogContextMixin):
    """Connection to CCU JSON-RPC Server."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        device_url: str,
        connection_state: hmcu.CentralConnectionState,
        client_session: ClientSession | None = None,
        tls: bool = False,
        verify_tls: bool = False,
        session_recorder: SessionRecorder | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Session setup."""
        self._client_session: Final = (
            ClientSession(connector=TCPConnector(limit=MAX_CONCURRENT_HTTP_SESSIONS))
            if client_session is None
            else client_session
        )
        self._is_internal_session: Final = bool(client_session is None)
        self._connection_state: Final = connection_state
        self._username: Final = username
        self._password: Final = password
        self._looper = Looper()
        self._tls: Final = tls
        self._tls_context: Final[SSLContext | bool] = get_tls_context(verify_tls=verify_tls) if tls else False
        self._url: Final = f"{device_url}{PATH_JSON_RPC}"
        self._script_cache: Final[dict[str, str]] = {}
        self._last_session_id_refresh: datetime | None = None
        self._session_id: str | None = None
        self._session_recorder: Final = session_recorder
        self._supported_methods: tuple[str, ...] | None = None
        self._http_session_semaphore: Final = Semaphore(value=MAX_CONCURRENT_HTTP_SESSIONS)

        # Login rate limiting state
        self._failed_login_attempts: int = 0
        self._last_failed_login: datetime | None = None
        self._current_backoff: float = LOGIN_INITIAL_BACKOFF_SECONDS

        # Circuit breaker for preventing retry-storms during backend outages
        self._circuit_breaker: Final = CircuitBreaker(
            config=circuit_breaker_config,
            interface_id=self._url,
            connection_state=connection_state,
            issuer=self,
        )

    @staticmethod
    def _convert_device_description(*, json_data: dict[str, Any]) -> DeviceDescription:
        """Convert json data to device description."""
        device_description = DeviceDescription(
            TYPE=json_data["type"],
            ADDRESS=json_data["address"],
            PARAMSETS=json_data["paramsets"],
        )
        if available_firmware := json_data.get("availableFirmware"):
            device_description["AVAILABLE_FIRMWARE"] = available_firmware
        if children := json_data.get("children"):
            device_description["CHILDREN"] = children
        if firmware := json_data.get("firmware"):
            device_description["FIRMWARE"] = firmware
        if firmware_updatable := json_data.get("firmwareUpdatable"):
            device_description["FIRMWARE_UPDATABLE"] = firmware_updatable
        if firmware_update_state := json_data.get("firmwareUpdateState"):
            device_description["FIRMWARE_UPDATE_STATE"] = firmware_update_state
        if interface := json_data.get("interface"):
            device_description["INTERFACE"] = interface
        if parent := json_data.get("parent"):
            device_description["PARENT"] = parent
        if link_source_role := json_data.get("linkSourceRole"):
            device_description["LINK_SOURCE_ROLES"] = link_source_role
        if link_target_role := json_data.get("linkTargetRole"):
            device_description["LINK_TARGET_ROLES"] = link_target_role
        if rx_mode := json_data.get("rxMode"):
            device_description["RX_MODE"] = rx_mode
        if subtype := json_data.get("subType"):
            device_description["SUBTYPE"] = subtype
        if updatable := json_data.get("updatable"):
            device_description["UPDATABLE"] = updatable
        return device_description

    @staticmethod
    def _convert_parameter_data(*, json_data: dict[str, Any]) -> ParameterData:
        """Convert json data to parameter data."""
        _type = json_data["TYPE"]
        _value_list = json_data.get("VALUE_LIST", ())

        parameter_data = ParameterData(
            DEFAULT=convert_value(value=json_data["DEFAULT"], target_type=_type, value_list=_value_list),
            FLAGS=int(json_data["FLAGS"]),
            ID=json_data["ID"],
            MAX=convert_value(value=json_data.get("MAX"), target_type=_type, value_list=_value_list),
            MIN=convert_value(value=json_data.get("MIN"), target_type=_type, value_list=_value_list),
            OPERATIONS=int(json_data["OPERATIONS"]),
            TYPE=_type,
        )
        if special := json_data.get("SPECIAL"):
            parameter_data["SPECIAL"] = special
        if unit := json_data.get("UNIT"):
            parameter_data["UNIT"] = str(unit)
        if value_list := _value_list:
            parameter_data["VALUE_LIST"] = value_list.split(" ")

        return parameter_data

    @property
    def _has_credentials(self) -> bool:
        """Return if credentials are available."""
        return self._username is not None and self._username != "" and self._password is not None

    @property
    def _has_session_recently_refreshed(self) -> bool:
        """Check if session id has been modified within 90 seconds."""
        if self._last_session_id_refresh is None:
            return False
        delta = datetime.now() - self._last_session_id_refresh
        return delta.seconds < JSON_SESSION_AGE

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Return the circuit breaker instance."""
        return self._circuit_breaker

    @property
    def is_activated(self) -> bool:
        """If session exists, then it is activated."""
        return self._session_id is not None

    @hm_property(log_context=True)
    def tls(self) -> bool:
        """Return tls."""
        return self._tls

    @hm_property(log_context=True)
    def url(self) -> str | None:
        """Return url."""
        return self._url

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """
        Accept a device from the CCU inbox.

        Args:
            device_address: The address of the device to accept.

        Returns:
            True if the device was accepted successfully.

        """
        try:
            response = await self._post_script(
                script_name=RegaScript.ACCEPT_DEVICE_IN_INBOX,
                extra_params={_JsonKey.DEVICE_ADDRESS: device_address},
            )

            _LOGGER.debug("ACCEPT_DEVICE_IN_INBOX: Accepting device %s", device_address)
            if json_result := response[_JsonKey.RESULT]:
                return bool(json_result.get(_JsonKey.SUCCESS, False))
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.accept_device_in_inbox.failed",
                    device_address=device_address,
                    reason=extract_exc_args(exc=jderr),
                )
            )

        return False

    def clear_session(self) -> None:
        """Clear the current session."""
        self._session_id = None

    async def create_backup_start(self) -> bool:
        """Start a system backup on the CCU in the background."""
        try:
            response = await self._post_script(script_name=RegaScript.CREATE_BACKUP_START)

            _LOGGER.debug("CREATE_BACKUP_START: Starting system backup in background")
            if json_result := response[_JsonKey.RESULT]:
                return bool(json_result.get(_JsonKey.SUCCESS, False))
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.create_backup_start.failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )

        return False

    async def create_backup_status(self) -> BackupStatusData:
        """Check the status of a backup started by create_backup_start."""
        try:
            response = await self._post_script(script_name=RegaScript.CREATE_BACKUP_STATUS)

            _LOGGER.debug("CREATE_BACKUP_STATUS: Checking backup status")
            if json_result := response[_JsonKey.RESULT]:
                status_str = json_result.get(_JsonKey.STATUS, BackupStatus.IDLE)
                try:
                    status = BackupStatus(status_str)
                except ValueError:
                    status = BackupStatus.IDLE

                return BackupStatusData(
                    status=status,
                    file_path=json_result.get(_JsonKey.FILE, ""),
                    filename=json_result.get(_JsonKey.FILENAME, ""),
                    size=json_result.get(_JsonKey.SIZE, 0),
                )
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.create_backup_status.failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )

        return BackupStatusData(status=BackupStatus.IDLE)

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete a system variable from the backend."""
        params = {_JsonKey.NAME: name}
        response = await self._post(
            method=_JsonRpcMethod.SYSVAR_DELETE_SYSVAR_BY_NAME,
            extra_params=params,
        )

        _LOGGER.debug("DELETE_SYSTEM_VARIABLE: Getting System variable")
        if json_result := response[_JsonKey.RESULT]:
            deleted = json_result
            _LOGGER.debug("DELETE_SYSTEM_VARIABLE: Deleted: %s", str(deleted))

        return True

    async def download_backup(self) -> bytes | None:
        """
        Download a backup file from the CCU.

        The CCU's cp_security.cgi endpoint creates and downloads a fresh backup.

        Returns:
            Backup file content as bytes, or None if download failed.

        """
        if not self._client_session:
            _LOGGER.error(i18n.tr("exception.client.json_post.no_session"))
            return None

        # Get session ID for authentication
        await self._login_or_renew()
        if not self._session_id:
            _LOGGER.error(i18n.tr("log.client.json_rpc.download_backup.no_session"))
            return None

        # Build download URL - CCU creates and serves backup via cp_security.cgi
        # Session ID must be wrapped in @ symbols: sid=@SESSION_ID@
        download_url = f"{self._url.replace(PATH_JSON_RPC, '')}/config/cp_security.cgi?sid=@{self._session_id}@&action=create_backup"

        try:
            _LOGGER.debug("DOWNLOAD_BACKUP: Downloading backup from %s", download_url)
            async with self._client_session.get(
                url=download_url,
                timeout=ClientTimeout(total=300),  # 5 minutes timeout for large backups
                ssl=self._tls_context,
            ) as response:
                if response.status == 200:
                    content = await response.read()
                    _LOGGER.debug("DOWNLOAD_BACKUP: Downloaded %d bytes", len(content))
                    return content
                _LOGGER.error(
                    i18n.tr(
                        "log.client.json_rpc.download_backup.failed",
                        status=response.status,
                    )
                )
        except ClientError as cerr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.download_backup.error",
                    reason=extract_exc_args(exc=cerr),
                )
            )

        return None

    async def download_firmware(self, *, firmware_url: str) -> bool:
        """
        Download firmware to the CCU for installation.

        Args:
            firmware_url: URL to download the firmware from.

        Returns:
            True if firmware was downloaded successfully, False otherwise.

        """
        if not self._client_session:
            _LOGGER.error(i18n.tr("exception.client.json_post.no_session"))
            return False

        # CCU downloads firmware via /config/cp_maintenance.cgi with POST
        upload_url = f"{self._url.replace(PATH_JSON_RPC, '')}/config/cp_maintenance.cgi"

        try:
            _LOGGER.debug("DOWNLOAD_FIRMWARE: Downloading firmware from %s", firmware_url)
            # Get session ID for authentication
            await self._login_or_renew()
            if not self._session_id:
                _LOGGER.error(i18n.tr("log.client.json_rpc.download_firmware.no_session"))
                return False

            # CCU expects firmware URL to be passed to maintenance CGI
            params = {
                _JsonKey.SID: self._session_id,
                _JsonKey.ACTION: "download_firmware",
                _JsonKey.URL: firmware_url,
            }

            async with self._client_session.post(
                url=upload_url,
                data=params,
                timeout=ClientTimeout(total=600),  # 10 minutes timeout for large firmware
                ssl=self._tls_context,
            ) as response:
                if response.status == 200:
                    _LOGGER.debug("DOWNLOAD_FIRMWARE: Firmware download initiated")
                    return True
                _LOGGER.error(
                    i18n.tr(
                        "log.client.json_rpc.download_firmware.failed",
                        status=response.status,
                    )
                )
        except ClientError as cerr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.download_firmware.error",
                    reason=extract_exc_args(exc=cerr),
                )
            )

        return False

    async def execute_program(self, *, pid: str) -> bool:
        """Execute a program on the backend."""
        params = {
            _JsonKey.ID: pid,
        }

        response = await self._post(method=_JsonRpcMethod.PROGRAM_EXECUTE, extra_params=params)
        _LOGGER.debug("EXECUTE_PROGRAM: Executing a program")

        if json_result := response[_JsonKey.RESULT]:
            _LOGGER.debug(
                "EXECUTE_PROGRAM: Result while executing program: %s",
                str(json_result),
            )

        return True

    async def get_all_channel_rega_ids_function(self) -> Mapping[int, set[str]]:
        """Get all rega_ids per function from the backend."""
        rega_ids_function: dict[int, set[str]] = {}

        response = await self._post(
            method=_JsonRpcMethod.SUBSECTION_GET_ALL,
        )

        _LOGGER.debug("GET_ALL_CHANNEL_IDS_PER_FUNCTION: Getting all functions")
        if json_result := response[_JsonKey.RESULT]:
            for function in json_result:
                function_id = int(function[_JsonKey.ID])
                function_name = function[_JsonKey.NAME]
                if function_id not in rega_ids_function:
                    rega_ids_function[function_id] = set()
                rega_ids_function[function_id].add(function_name)
                for rega_id in function[_JsonKey.CHANNEL_IDS]:
                    if rega_id not in rega_ids_function:
                        rega_ids_function[rega_id] = set()
                    rega_ids_function[rega_id].add(function_name)

        return rega_ids_function

    async def get_all_channel_rega_ids_room(self) -> Mapping[int, set[str]]:
        """Get all rega_ids per room from the backend."""
        rega_ids_room: dict[int, set[str]] = {}

        response = await self._post(
            method=_JsonRpcMethod.ROOM_GET_ALL,
        )

        _LOGGER.debug("GET_ALL_CHANNEL_IDS_PER_ROOM: Getting all rooms")
        if json_result := response[_JsonKey.RESULT]:
            for room in json_result:
                room_id = int(room[_JsonKey.ID])
                room_name = room[_JsonKey.NAME]
                if room_id not in rega_ids_room:
                    rega_ids_room[room_id] = set()
                rega_ids_room[room_id].add(room_name)
                for rega_id in room[_JsonKey.CHANNEL_IDS]:
                    if rega_id not in rega_ids_room:
                        rega_ids_room[rega_id] = set()
                    rega_ids_room[rega_id].add(room_name)

        return rega_ids_room

    async def get_all_device_data(self, *, interface: Interface) -> Mapping[str, Any]:
        """Get the all device data of the backend."""
        all_device_data: dict[str, Any] = {}
        params = {
            _JsonKey.INTERFACE: interface,
        }
        try:
            response = await self._post_script(script_name=RegaScript.FETCH_ALL_DEVICE_DATA, extra_params=params)

            _LOGGER.debug("GET_ALL_DEVICE_DATA: Getting all device data for interface %s", interface)
            if json_result := response[_JsonKey.RESULT]:
                all_device_data = {
                    unquote(string=k, encoding=ISO_8859_1): unquote(string=v, encoding=ISO_8859_1)
                    if isinstance(v, str)
                    else v
                    for k, v in json_result.items()
                }

        except (ContentTypeError, JSONDecodeError) as cerr:
            raise ClientException(
                i18n.tr(
                    "exception.client.get_all_device_data.failed",
                    interface=interface,
                )
            ) from cerr

        return all_device_data

    async def get_all_programs(self, *, markers: tuple[DescriptionMarker | str, ...]) -> tuple[ProgramData, ...]:
        """Get the all programs of the backend."""
        all_programs: list[ProgramData] = []

        response = await self._post(
            method=_JsonRpcMethod.PROGRAM_GET_ALL,
        )

        _LOGGER.debug("GET_ALL_PROGRAMS: Getting all programs")
        if json_result := response[_JsonKey.RESULT]:
            descriptions = await self._get_program_descriptions()
            for prog in json_result:
                enabled_default = False
                if (is_internal := prog[_JsonKey.IS_INTERNAL]) is True:
                    if markers:
                        if DescriptionMarker.INTERNAL not in markers:
                            continue
                        enabled_default = True
                    elif DEFAULT_INCLUDE_INTERNAL_PROGRAMS is False:
                        continue

                pid = prog[_JsonKey.ID]
                description = descriptions.get(pid)
                if not is_internal and markers:
                    if not element_matches_key(
                        search_elements=markers,
                        compare_with=description,
                        ignore_case=False,
                        do_left_wildcard_search=True,
                    ):
                        continue
                    enabled_default = True
                if description:
                    # Remove default markers from description
                    for marker in DescriptionMarker:
                        description = description.replace(marker, "").strip()
                name = prog[_JsonKey.NAME]
                is_active = prog[_JsonKey.IS_ACTIVE]
                last_execute_time = prog[_JsonKey.LAST_EXECUTE_TIME]

                all_programs.append(
                    ProgramData(
                        pid=pid,
                        legacy_name=name,
                        description=description,
                        is_active=is_active,
                        is_internal=is_internal,
                        last_execute_time=last_execute_time,
                        enabled_default=enabled_default,
                    )
                )

        return tuple(all_programs)

    async def get_all_system_variables(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...]:
        """Get all system variables from the backend."""
        variables: list[SystemVariableData] = []

        response = await self._post(
            method=_JsonRpcMethod.SYSVAR_GET_ALL,
        )

        _LOGGER.debug("GET_ALL_SYSTEM_VARIABLES: Getting all system variables")
        if json_result := response[_JsonKey.RESULT]:
            descriptions = await self._get_system_variable_descriptions()
            for var in json_result:
                enabled_default = False
                extended_sysvar = False
                var_id = var[_JsonKey.ID]
                legacy_name = var[_JsonKey.NAME]
                is_internal = var[_JsonKey.IS_INTERNAL]
                if new_name := RENAME_SYSVAR_BY_NAME.get(legacy_name):
                    legacy_name = new_name
                if var_id in ALWAYS_ENABLE_SYSVARS_BY_ID:
                    enabled_default = True

                if enabled_default is False and is_internal is True:
                    if var_id in ALWAYS_ENABLE_SYSVARS_BY_ID:
                        enabled_default = True
                    elif markers:
                        if DescriptionMarker.INTERNAL not in markers:
                            continue
                        enabled_default = True
                    elif DEFAULT_INCLUDE_INTERNAL_SYSVARS is False:
                        continue  # type: ignore[unreachable]

                description = descriptions.get(var_id)
                if enabled_default is False and not is_internal and markers:
                    if not element_matches_key(
                        search_elements=markers,
                        compare_with=description,
                        ignore_case=False,
                        do_left_wildcard_search=True,
                    ):
                        continue
                    enabled_default = True

                org_data_type = var[_JsonKey.TYPE]
                raw_value = var[_JsonKey.VALUE]
                if org_data_type == HubValueType.NUMBER:
                    data_type = HubValueType.FLOAT if "." in raw_value else HubValueType.INTEGER
                else:
                    data_type = org_data_type

                if description:
                    extended_sysvar = DescriptionMarker.HAHM in description
                    # Remove default markers from description
                    for marker in DescriptionMarker:
                        description = description.replace(marker, "").strip()
                unit = var[_JsonKey.UNIT]
                values: tuple[str, ...] | None = None
                if val_list := var.get(_JsonKey.VALUE_LIST):
                    values = tuple(val_list.split(";"))
                try:
                    value = parse_sys_var(data_type=data_type, raw_value=raw_value)
                    max_value = None
                    if raw_max_value := var.get(_JsonKey.MAX_VALUE):
                        max_value = parse_sys_var(data_type=data_type, raw_value=raw_max_value)
                    min_value = None
                    if raw_min_value := var.get(_JsonKey.MIN_VALUE):
                        min_value = parse_sys_var(data_type=data_type, raw_value=raw_min_value)
                    variables.append(
                        SystemVariableData(
                            vid=var_id,
                            legacy_name=legacy_name,
                            data_type=data_type,
                            description=description,
                            unit=unit,
                            value=value,
                            values=values,
                            max_value=max_value,
                            min_value=min_value,
                            extended_sysvar=extended_sysvar,
                            enabled_default=enabled_default,
                        )
                    )
                except (ValueError, TypeError) as vterr:
                    _LOGGER.error(
                        i18n.tr(
                            "log.client.json_rpc.get_all_system_variables.parse_failed",
                            exc_type=vterr.__class__.__name__,
                            reason=extract_exc_args(exc=vterr),
                            legacy_name=legacy_name,
                        )
                    )

        return tuple(variables)

    async def get_device_description(self, *, interface: Interface, address: str) -> DeviceDescription | None:
        """Get device descriptions from the backend."""
        device_description: DeviceDescription | None = None
        params = {
            _JsonKey.INTERFACE: interface,
            _JsonKey.ADDRESS: address,
        }

        response = await self._post(method=_JsonRpcMethod.INTERFACE_GET_DEVICE_DESCRIPTION, extra_params=params)

        _LOGGER.debug("GET_DEVICE_DESCRIPTION: Getting the device description")
        if json_result := response[_JsonKey.RESULT]:
            device_description = self._convert_device_description(json_data=json_result)

        return device_description

    async def get_device_details(self) -> tuple[dict[str, Any], ...]:
        """Get the device details of the backend."""
        device_details: tuple[dict[str, Any], ...] = ()

        response = await self._post(
            method=_JsonRpcMethod.DEVICE_LIST_ALL_DETAIL,
        )

        _LOGGER.debug("GET_DEVICE_DETAILS: Getting the device details")
        if json_result := response[_JsonKey.RESULT]:
            device_details = tuple(json_result)

        return device_details

    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """Get all devices in the inbox (not yet configured)."""
        devices: list[InboxDeviceData] = []

        try:
            response = await self._post_script(script_name=RegaScript.GET_INBOX_DEVICES)

            _LOGGER.debug("GET_INBOX_DEVICES: Getting inbox devices")
            if json_result := response[_JsonKey.RESULT]:
                devices.extend(
                    InboxDeviceData(
                        device_id=dev[_JsonKey.ID],
                        address=dev.get(_JsonKey.ADDRESS, ""),
                        name=unquote(string=dev.get(_JsonKey.NAME, ""), encoding=ISO_8859_1),
                        device_type=dev.get(_JsonKey.TYPE, ""),
                        interface=dev.get(_JsonKey.INTERFACE, ""),
                    )
                    for dev in json_result
                )
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.get_inbox_devices.decode_failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )

        return tuple(devices)

    async def get_install_mode(self, *, interface: Interface) -> int:
        """Get the remaining install mode time for an interface."""
        params = {_JsonKey.INTERFACE: interface}

        response = await self._post(method=_JsonRpcMethod.INTERFACE_GET_INSTALL_MODE, extra_params=params)

        _LOGGER.debug("GET_INSTALL_MODE: Getting remaining install mode time for %s", interface)
        if json_result := response[_JsonKey.RESULT]:
            return int(json_result)

        return 0

    async def get_paramset(
        self, *, interface: Interface, address: str, paramset_key: ParamsetKey | str
    ) -> dict[str, Any] | None:
        """Get paramset from the backend."""
        paramset: dict[str, Any] = {}
        params = {
            _JsonKey.INTERFACE: interface,
            _JsonKey.ADDRESS: address,
            _JsonKey.PARAMSET_KEY: paramset_key,
        }

        response = await self._post(
            method=_JsonRpcMethod.INTERFACE_GET_PARAMSET,
            extra_params=params,
        )

        _LOGGER.debug("GET_PARAMSET: Getting the paramset")
        if json_result := response[_JsonKey.RESULT]:
            paramset = json_result

        return paramset

    async def get_paramset_description(
        self, *, interface: Interface, address: str, paramset_key: ParamsetKey
    ) -> Mapping[str, ParameterData] | None:
        """Get paramset description from the backend."""
        paramset_description: dict[str, ParameterData] = {}
        params = {
            _JsonKey.INTERFACE: interface,
            _JsonKey.ADDRESS: address,
            _JsonKey.PARAMSET_KEY: paramset_key,
        }

        response = await self._post(method=_JsonRpcMethod.INTERFACE_GET_PARAMSET_DESCRIPTION, extra_params=params)

        _LOGGER.debug("GET_PARAMSET_DESCRIPTIONS: Getting the paramset descriptions")
        if json_result := response[_JsonKey.RESULT]:
            paramset_description = {data["NAME"]: self._convert_parameter_data(json_data=data) for data in json_result}

        return paramset_description

    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        """
        Get the ReGa ID for a device or channel address.

        Args:
            address: The address of the device or channel.

        Returns:
            The ReGa ID if found, None otherwise.

        """
        is_dev = is_device_address(address=address)

        details = await self.get_device_details()
        for detail in details:
            if is_dev:
                if detail[_JsonKey.ADDRESS] == address:
                    return int(detail[_JsonKey.ID])
            else:
                for channel in detail[_JsonKey.CHANNELS]:
                    if channel[_JsonKey.ADDRESS] == address:
                        return int(channel[_JsonKey.ID])

        return None

    async def get_service_messages(
        self,
        *,
        message_type: ServiceMessageType | None = None,
    ) -> tuple[ServiceMessageData, ...]:
        """
        Get all active service messages from the backend.

        Args:
            message_type: Filter by message type. If None, return all messages.

        """
        messages: list[ServiceMessageData] = []

        try:
            response = await self._post_script(script_name=RegaScript.GET_SERVICE_MESSAGES)

            _LOGGER.debug("GET_SERVICE_MESSAGES: Getting service messages")
            if json_result := response[_JsonKey.RESULT]:
                for msg in json_result:
                    msg_type = msg[_JsonKey.TYPE]
                    if message_type is not None and msg_type != message_type:
                        continue
                    messages.append(
                        ServiceMessageData(
                            msg_id=msg[_JsonKey.ID],
                            name=unquote(string=msg[_JsonKey.NAME], encoding=ISO_8859_1),
                            timestamp=msg[_JsonKey.TIMESTAMP],
                            msg_type=msg_type,
                            address=msg.get(_JsonKey.ADDRESS, ""),
                            device_name=unquote(string=msg.get(_JsonKey.DEVICE_NAME, ""), encoding=ISO_8859_1),
                        )
                    )
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.get_service_messages.decode_failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )

        return tuple(messages)

    async def get_system_information(self) -> SystemInformation:
        """Get system information of the the backend."""
        auth_enabled = await self._get_auth_enabled()

        # Get backend info (version, product, hostname, ccu_type)
        version = ""
        hostname = ""
        ccu_type = CCUType.UNKNOWN
        try:
            response = await self._post_script(script_name=RegaScript.GET_BACKEND_INFO)
            _LOGGER.debug("GET_SYSTEM_INFORMATION: Getting backend information")
            if json_result := response[_JsonKey.RESULT]:
                version = json_result.get(_JsonKey.VERSION, "")
                ccu_type = _determine_ccu_type(product=json_result.get(_JsonKey.PRODUCT, ""))
                hostname = json_result.get(_JsonKey.HOSTNAME, "")
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.get_backend_info.failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )

        return SystemInformation(
            auth_enabled=auth_enabled,
            available_interfaces=await self._list_interfaces(),
            https_redirect_enabled=await self._get_https_redirect_enabled(),
            serial=await self._get_serial(),
            version=version,
            hostname=hostname,
            ccu_type=ccu_type,
        )

    async def get_system_update_info(self) -> SystemUpdateData:
        """Get system update information from the backend."""
        try:
            response = await self._post_script(script_name=RegaScript.GET_SYSTEM_UPDATE_INFO)

            _LOGGER.debug("GET_SYSTEM_UPDATE_INFO: Getting system update info")
            if json_result := response[_JsonKey.RESULT]:
                return SystemUpdateData(
                    current_firmware=json_result.get(_JsonKey.CURRENT_FIRMWARE, ""),
                    available_firmware=json_result.get(_JsonKey.AVAILABLE_FIRMWARE, ""),
                    update_available=json_result.get(_JsonKey.UPDATE_AVAILABLE, False),
                    check_script_available=json_result.get(_JsonKey.CHECK_SCRIPT_AVAILABLE, False),
                )
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.get_system_update_info.decode_failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )

        return SystemUpdateData(
            current_firmware="",
            available_firmware="",
            update_available=False,
        )

    async def get_system_variable(self, *, name: str) -> Any:
        """Get single system variable from the backend."""
        params = {_JsonKey.NAME: name}
        response = await self._post(
            method=_JsonRpcMethod.SYSVAR_GET_VALUE_BY_NAME,
            extra_params=params,
        )

        _LOGGER.debug("GET_SYSTEM_VARIABLE: Getting System variable")
        return response[_JsonKey.RESULT]

    async def get_value(self, *, interface: Interface, address: str, paramset_key: ParamsetKey, parameter: str) -> Any:
        """Get value from the backend."""
        value: Any = None
        params = {
            _JsonKey.INTERFACE: interface,
            _JsonKey.ADDRESS: address,
            _JsonKey.VALUE_KEY: parameter,
        }

        response = (
            await self._post(method=_JsonRpcMethod.INTERFACE_GET_MASTER_VALUE, extra_params=params)
            if paramset_key == ParamsetKey.MASTER
            else await self._post(method=_JsonRpcMethod.INTERFACE_GET_VALUE, extra_params=params)
        )

        _LOGGER.debug("GET_VALUE: Getting the value")
        if json_result := response[_JsonKey.RESULT]:
            value = json_result

        return value

    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Return if a channel has program ids."""
        params = {_JsonKey.ID: rega_id}
        response = await self._post(
            method=_JsonRpcMethod.CHANNEL_HAS_PROGRAM_IDS,
            extra_params=params,
        )

        _LOGGER.debug("HAS_PROGRAM_IDS: Checking if channel has program ids")
        if json_result := response[_JsonKey.RESULT]:
            return bool(json_result)

        return False

    async def is_present(self, *, interface: Interface) -> bool:
        """Get value from the backend."""
        value: bool = False
        params = {_JsonKey.INTERFACE: interface}

        response = await self._post(method=_JsonRpcMethod.INTERFACE_IS_PRESENT, extra_params=params)

        _LOGGER.debug("IS_PRESENT: Getting the value")
        if json_result := response[_JsonKey.RESULT]:
            value = bool(json_result)

        return value

    async def is_service_available(self) -> bool:
        """
        Check if the JSON-RPC service is available.

        This method attempts a login to verify the service is ready.
        Useful after CCU restart to ensure the service is fully available
        before attempting other operations.

        Returns True if login succeeds, False otherwise.
        """
        try:
            session_id = await self._do_login()
        except BaseHomematicException:
            return False
        else:
            return session_id is not None

    async def list_devices(self, *, interface: Interface) -> tuple[DeviceDescription, ...]:
        """List devices from the backend."""
        devices: tuple[DeviceDescription, ...] = ()
        _LOGGER.debug("LIST_DEVICES: Getting all available interfaces")
        params = {
            _JsonKey.INTERFACE: interface,
        }

        response = await self._post(
            method=_JsonRpcMethod.INTERFACE_LIST_DEVICES,
            extra_params=params,
        )

        if json_result := response[_JsonKey.RESULT]:
            devices = tuple(self._convert_device_description(json_data=data) for data in json_result)

        return devices

    async def logout(self) -> None:
        """Logout of the backend."""
        try:
            await self._looper.block_till_done()
            await self._do_logout(session_id=self._session_id)
        except BaseHomematicException:
            _LOGGER.debug("LOGOUT: logout failed")

    async def put_paramset(
        self,
        *,
        interface: Interface,
        address: str,
        paramset_key: ParamsetKey | str,
        values: list[dict[str, Any]],
    ) -> None:
        """Set paramset to the backend."""
        params = {
            _JsonKey.INTERFACE: interface,
            _JsonKey.ADDRESS: address,
            _JsonKey.PARAMSET_KEY: paramset_key,
            _JsonKey.SET: values,
        }

        response = await self._post(
            method=_JsonRpcMethod.INTERFACE_PUT_PARAMSET,
            extra_params=params,
        )

        _LOGGER.debug("PUT_PARAMSET: Putting the paramset")
        if json_result := response[_JsonKey.RESULT]:
            _LOGGER.debug(
                "PUT_PARAMSET: Result while putting the paramset: %s",
                str(json_result),
            )

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """
        Rename a channel on the CCU.

        Args:
            rega_id: The ReGa ID of the channel to rename.
            new_name: The new name for the channel.

        Returns:
            True if the channel was renamed successfully.

        """
        params = {
            _JsonKey.ID: rega_id,
            _JsonKey.NAME: new_name,
        }

        response = await self._post(method=_JsonRpcMethod.CHANNEL_SET_NAME, extra_params=params)
        _LOGGER.debug("RENAME_CHANNEL: Renaming channel with rega_id %s to %s", rega_id, new_name)

        return response.get(_JsonKey.RESULT) is True

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """
        Rename a device on the CCU.

        Args:
            rega_id: The ReGa ID of the device to rename.
            new_name: The new name for the device.

        Returns:
            True if the device was renamed successfully.

        """
        params = {
            _JsonKey.ID: rega_id,
            _JsonKey.NAME: new_name,
        }

        response = await self._post(method=_JsonRpcMethod.DEVICE_SET_NAME, extra_params=params)
        _LOGGER.debug("RENAME_DEVICE: Renaming device with rega_id %s to %s", rega_id, new_name)

        return response.get(_JsonKey.RESULT) is True

    async def set_install_mode_hmip(
        self,
        *,
        interface: Interface,
        on: bool = True,
        time: int = 60,
        device_address: str | None = None,
    ) -> bool:
        """
        Set the install mode on the backend for HmIP-RF.

        Args:
            interface: The interface to set install mode for.
            on: Enable or disable install mode.
            time: Duration in seconds (default 60).
            device_address: Optional device SGTIN to limit pairing.

        Returns:
            True if successful.

        """
        params: dict[str, Any] = {
            _JsonKey.INTERFACE: interface,
            _JsonKey.ON: "true" if on else "false",
            _JsonKey.TIME: time,
            _JsonKey.INSTALL_MODE: "ALL",
            _JsonKey.ADDRESS: device_address or "",
            _JsonKey.KEY: "",
            _JsonKey.KEYMODE: "",
        }

        response = await self._post(method=_JsonRpcMethod.INTERFACE_SET_INSTALL_MODE_HMIP, extra_params=params)

        _LOGGER.debug("SET_INSTALL_MODE_HMIP: Setting install mode for HmIP-RF")
        return response[_JsonKey.RESULT] is not None

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set the program state on the backend."""
        params = {
            _JsonKey.ID: pid,
            _JsonKey.STATE: "1" if state else "0",
        }
        response = await self._post_script(script_name=RegaScript.SET_PROGRAM_STATE, extra_params=params)

        _LOGGER.debug("SET_PROGRAM_STATE: Setting program state: %s", state)
        if json_result := response[_JsonKey.RESULT]:
            _LOGGER.debug(
                "SET_PROGRAM_STATE: Result while setting program state: %s",
                str(json_result),
            )

        return True

    async def set_system_variable(self, *, legacy_name: str, value: Any) -> bool:
        """Set a system variable on the backend."""
        params = {_JsonKey.NAME: legacy_name, _JsonKey.VALUE: value}
        if isinstance(value, bool):
            params[_JsonKey.VALUE] = int(value)
            response = await self._post(method=_JsonRpcMethod.SYSVAR_SET_BOOL, extra_params=params)
        elif isinstance(value, str):
            if (clean_text := cleanup_text_from_html_tags(text=value)) != value:
                params[_JsonKey.VALUE] = clean_text
                _LOGGER.error(
                    i18n.tr(
                        "log.client.json_rpc.set_system_variable.value_contains_html",
                        value=value,
                    )
                )
            response = await self._post_script(script_name=RegaScript.SET_SYSTEM_VARIABLE, extra_params=params)
        else:
            response = await self._post(method=_JsonRpcMethod.SYSVAR_SET_FLOAT, extra_params=params)

        _LOGGER.debug("SET_SYSTEM_VARIABLE: Setting System variable")
        if json_result := response[_JsonKey.RESULT]:
            _LOGGER.debug(
                "SET_SYSTEM_VARIABLE: Result while setting variable: %s",
                str(json_result),
            )

        return True

    async def set_value(
        self, *, interface: Interface, address: str, parameter: str, value_type: str, value: Any
    ) -> None:
        """Set value to the backend."""
        params = {
            _JsonKey.INTERFACE: interface,
            _JsonKey.ADDRESS: address,
            _JsonKey.VALUE_KEY: parameter,
            _JsonKey.TYPE: value_type,
            _JsonKey.VALUE: value,
        }

        response = await self._post(
            method=_JsonRpcMethod.INTERFACE_SET_VALUE,
            extra_params=params,
        )

        _LOGGER.debug("SET_VALUE: Setting the value")
        if json_result := response[_JsonKey.RESULT]:
            _LOGGER.debug(
                "SET_VALUE: Result while setting the value: %s",
                str(json_result),
            )

    async def stop(self) -> None:
        """Stop the json rpc client."""
        if self._is_internal_session:
            await self._client_session.close()

    async def trigger_firmware_update(self) -> bool:
        """
        Trigger unattended firmware update.

        Only supported on OpenCCU (uses checkFirmwareUpdate.sh).
        The script runs with nohup in the background and will download the update
        and reboot to apply. Use create_backup_and_download() before this method
        to create a backup.

        Returns:
            True if update was successfully triggered, False otherwise.

        """
        try:
            response = await self._post_script(script_name=RegaScript.TRIGGER_FIRMWARE_UPDATE)

            _LOGGER.debug("TRIGGER_FIRMWARE_UPDATE: Triggering firmware update")
            if json_result := response[_JsonKey.RESULT]:
                success = bool(json_result.get(_JsonKey.SUCCESS, False))
                message = json_result.get(_JsonKey.MESSAGE, "")

                if success:
                    _LOGGER.info(
                        i18n.tr(
                            "log.client.json_rpc.trigger_firmware_update.success",
                            message=message,
                        )
                    )
                else:
                    _LOGGER.warning(
                        i18n.tr(
                            "log.client.json_rpc.trigger_firmware_update.not_triggered",
                            message=message,
                        )
                    )
                return success
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.trigger_firmware_update.failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )

        return False

    async def _check_supported_methods(self) -> bool:
        """Check, if all required api methods are supported by the backend."""
        if self._supported_methods is None:
            self._supported_methods = await self._get_supported_methods()
        if unsupported_methods := tuple(method for method in _JsonRpcMethod if method not in self._supported_methods):
            _LOGGER.error(  # i18n-log: ignore
                "CHECK_SUPPORTED_METHODS: methods not supported by the backend: %s",
                ", ".join(unsupported_methods),
            )
            return False
        return True

    async def _do_login(self) -> str | None:
        """Login to the backend and return session with rate limiting."""
        if not self._has_credentials:
            _LOGGER.error(i18n.tr("log.client.json_rpc.do_login.no_credentials"))
            return None

        # Apply rate limiting if we've had recent failed attempts
        if (
            self._failed_login_attempts > 0
            and self._last_failed_login
            and (elapsed := (datetime.now() - self._last_failed_login).total_seconds()) < self._current_backoff
        ):
            wait_time = self._current_backoff - elapsed
            _LOGGER.warning(
                i18n.tr(
                    "log.client.json_rpc.do_login.rate_limited",
                    attempts=self._failed_login_attempts,
                    wait_time=wait_time,
                )
            )
            await asyncio.sleep(wait_time)

        session_id: str | None = None

        params = {
            _JsonKey.USERNAME: self._username,
            _JsonKey.PASSWORD: self._password,
        }
        method = _JsonRpcMethod.SESSION_LOGIN
        response = await self._do_post(
            session_id=False,
            method=method,
            extra_params=params,
            use_default_params=False,
        )

        if result := response[_JsonKey.RESULT]:
            session_id = result
            # Reset rate limiting on successful login
            self._failed_login_attempts = 0
            self._current_backoff = LOGIN_INITIAL_BACKOFF_SECONDS
            self._last_failed_login = None
        else:
            # Track failed login attempt
            self._failed_login_attempts += 1
            self._last_failed_login = datetime.now()
            # Apply exponential backoff up to max
            self._current_backoff = min(
                self._current_backoff * LOGIN_BACKOFF_MULTIPLIER,
                LOGIN_MAX_BACKOFF_SECONDS,
            )
            if self._failed_login_attempts >= LOGIN_MAX_FAILED_ATTEMPTS:
                _LOGGER.error(
                    i18n.tr(
                        "log.client.json_rpc.do_login.max_attempts_reached",
                        max_attempts=LOGIN_MAX_FAILED_ATTEMPTS,
                    )
                )

        _LOGGER.debug("DO_LOGIN: method: %s [%s]", method, session_id)

        return session_id

    async def _do_logout(self, *, session_id: str | None) -> None:
        """Logout of the backend."""
        if not session_id:
            _LOGGER.debug("DO_LOGOUT: Not logged in. Not logging out.")
            return

        method = _JsonRpcMethod.SESSION_LOGOUT
        params = {_JsonKey.SESSION_ID: session_id}
        try:
            await self._do_post(
                session_id=session_id,
                method=method,
                extra_params=params,
            )
            _LOGGER.debug("DO_LOGOUT: method: %s [%s]", method, session_id)
        finally:
            self.clear_session()

    @with_retry
    async def _do_post(
        self,
        *,
        session_id: bool | str,
        method: _JsonRpcMethod,
        extra_params: Mapping[Any, Any] | None = None,
        use_default_params: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST function."""
        if not self._client_session:
            raise ClientException(i18n.tr("exception.client.json_post.no_session"))
        if not self._has_credentials:
            raise ClientException(i18n.tr("exception.client.json_post.no_credentials"))
        if self._supported_methods and method not in self._supported_methods:
            raise UnsupportedException(i18n.tr("exception.client.json_post.method_unsupported", method=method))

        # Check circuit breaker state (allow session management methods through)
        if method not in _CIRCUIT_BREAKER_BYPASS_METHODS and not self._circuit_breaker.is_available:
            self._circuit_breaker.record_rejection()
            raise CircuitBreakerOpenException(i18n.tr("exception.client.json_rpc.circuit_open", url=self._url))

        params = _get_params(session_id=session_id, extra_params=extra_params, use_default_params=use_default_params)

        try:
            payload = orjson.dumps({"method": method, "params": params, "jsonrpc": "1.1", "id": 0})

            headers = {
                "Content-Type": "application/json",
                "Content-Length": str(len(payload)),
            }

            post_call = partial(
                self._client_session.post,
                url=self._url,
                data=payload,
                headers=headers,
                timeout=ClientTimeout(total=TIMEOUT),
                ssl=self._tls_context,
            )
            # Limit all JSON-RPC requests to prevent CCU session overload
            async with self._http_session_semaphore:
                if (response := await asyncio.shield(post_call())) is None:
                    raise ClientException(i18n.tr("exception.client.json_post.no_response"))

            if response.status == 200:
                json_response = await asyncio.shield(self._get_json_reponse(response=response))
                self._record_session(method=method, params=params, response=json_response)
                if error := json_response[_JsonKey.ERROR]:
                    # Map JSON-RPC error to actionable exception with context
                    ctx = RpcContext(protocol="json-rpc", method=str(method), host=self._url)
                    exc = map_jsonrpc_error(error=error, ctx=ctx)
                    # For session management methods (login, renew), use DEBUG level
                    # as these may fail during CCU restart polling and are expected
                    # For other methods, use WARNING level
                    level = logging.DEBUG if method in _CIRCUIT_BREAKER_BYPASS_METHODS else logging.WARNING
                    log_boundary_error(
                        logger=_LOGGER,
                        boundary="json-rpc",
                        action=str(method),
                        err=exc,
                        level=level,
                        log_context=self.log_context,
                    )
                    _LOGGER.debug("POST: %s", exc)
                    raise exc

                self._connection_state.remove_issue(issuer=self, iid=self._url)
                self._circuit_breaker.record_success()
                return json_response

            message = i18n.tr("exception.client.json_post.http_status", status=response.status)
            json_response = await asyncio.shield(self._get_json_reponse(response=response))
            if error := json_response[_JsonKey.ERROR]:
                ctx = RpcContext(protocol="json-rpc", method=str(method), host=self._url)
                exc = map_jsonrpc_error(error=error, ctx=ctx)
                # Use DEBUG level for session management methods during CCU restart polling
                level = logging.DEBUG if method in _CIRCUIT_BREAKER_BYPASS_METHODS else logging.WARNING
                log_boundary_error(
                    logger=_LOGGER,
                    boundary="json-rpc",
                    action=str(method),
                    err=exc,
                    level=level,
                    log_context=dict(self.log_context) | {"status": response.status},
                )
                raise exc
            raise ClientException(message)
        except BaseHomematicException as bhe:
            self._record_session(method=method, params=params, exc=bhe)
            if method in _CIRCUIT_BREAKER_BYPASS_METHODS:
                self.clear_session()
            # Note: Don't log here - the exception was already logged at its source
            # (either by map_jsonrpc_error handler above or by the caller)
            raise

        except ClientConnectorCertificateError as cccerr:
            self.clear_session()
            self._circuit_breaker.record_failure()
            message = f"ClientConnectorCertificateError[{cccerr}]"
            if self._tls is False and cccerr.ssl is True:
                message = (
                    f"{message}. Possible reason: 'Automatic forwarding to HTTPS' is enabled in the backend, "
                    f"but this integration is not configured to use TLS"
                )
            # Log ERROR only on first occurrence, DEBUG for subsequent failures
            level = logging.ERROR if self._connection_state.add_issue(issuer=self, iid=self._url) else logging.DEBUG
            log_boundary_error(
                logger=_LOGGER,
                boundary="json-rpc",
                action=str(method),
                err=cccerr,
                level=level,
                log_context=self.log_context,
            )
            raise ClientException(
                i18n.tr("exception.client.json_post.connector_certificate_error", reason=message)
            ) from cccerr
        except ClientConnectorError as cceerr:
            self.clear_session()
            self._circuit_breaker.record_failure()
            message = f"ClientConnectorError[{cceerr}]"
            # Log ERROR only on first occurrence, DEBUG for subsequent failures
            level = logging.ERROR if self._connection_state.add_issue(issuer=self, iid=self._url) else logging.DEBUG
            log_boundary_error(
                logger=_LOGGER,
                boundary="json-rpc",
                action=str(method),
                err=cceerr,
                level=level,
                log_context=self.log_context,
            )
            raise ClientException(i18n.tr("exception.client.json_post.connector_error", reason=message)) from cceerr
        except (ClientError, OSError) as err:
            self.clear_session()
            self._circuit_breaker.record_failure()
            # Log ERROR only on first occurrence, DEBUG for subsequent failures
            level = logging.ERROR if self._connection_state.add_issue(issuer=self, iid=self._url) else logging.DEBUG
            log_boundary_error(
                logger=_LOGGER,
                boundary="json-rpc",
                action=str(method),
                err=err,
                level=level,
                log_context=self.log_context,
            )
            raise NoConnectionException(err) from err
        except (TypeError, Exception) as exc:
            self.clear_session()
            log_boundary_error(
                logger=_LOGGER,
                boundary="json-rpc",
                action=str(method),
                err=exc,
                level=logging.ERROR,
                log_context=self.log_context,
            )
            raise ClientException(exc) from exc

    async def _do_renew_login(self, *, session_id: str) -> str | None:
        """Renew JSON-RPC session or perform login."""
        if self._has_session_recently_refreshed:
            return session_id
        method = _JsonRpcMethod.SESSION_RENEW
        try:
            response = await self._do_post(
                session_id=session_id,
                method=method,
                extra_params={_JsonKey.SESSION_ID: session_id},
            )
            if response[_JsonKey.RESULT] is True:
                self._last_session_id_refresh = datetime.now()
                _LOGGER.debug("DO_RENEW_LOGIN: method: %s [%s]", method, session_id)
                return session_id
        except AuthFailure:
            # Session is invalid (e.g., after CCU restart)
            # Try to logout old session before creating new one to prevent session leaks
            _LOGGER.debug("DO_RENEW_LOGIN: Session expired, attempting logout before fresh login")
            try:
                await self._do_logout(session_id=session_id)
            except BaseHomematicException:
                # Logout may fail if CCU was restarted, but that's okay
                # The CCU will eventually clean up expired sessions
                _LOGGER.debug("DO_RENEW_LOGIN: Logout of expired session failed (expected after CCU restart)")

        return await self._do_login()

    async def _get_auth_enabled(self) -> bool:
        """Get the auth_enabled flag of the backend."""
        _LOGGER.debug("GET_AUTH_ENABLED: Getting the flag auth_enabled")
        try:
            response = await self._post(method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED)
            if (json_result := response[_JsonKey.RESULT]) is not None:
                return bool(json_result)
        except InternalBackendException:
            return True

        return True

    async def _get_https_redirect_enabled(self) -> bool | None:
        """Get the auth_enabled flag of the backend."""
        _LOGGER.debug("GET_HTTPS_REDIRECT_ENABLED: Getting the flag https_redirect_enabled")

        response = await self._post(method=_JsonRpcMethod.CCU_GET_HTTPS_REDIRECT_ENABLED)
        if (json_result := response[_JsonKey.RESULT]) is not None:
            return bool(json_result)
        return None

    async def _get_json_reponse(self, *, response: ClientResponse) -> dict[str, Any] | Any:
        """Return the json object from response."""
        try:
            return await response.json(encoding=UTF_8)
        except ValueError as verr:
            _LOGGER.debug(
                "DO_POST: ValueError [%s] Unable to parse JSON. Trying workaround",
                extract_exc_args(exc=verr),
            )
            # Workaround for bug in CCU
            return orjson.loads((await response.read()).decode(encoding=UTF_8))

    async def _get_program_descriptions(self) -> Mapping[str, str]:
        """Get all program descriptions from the backend via script."""
        descriptions: dict[str, str] = {}
        try:
            response = await self._post_script(script_name=RegaScript.GET_PROGRAM_DESCRIPTIONS)

            _LOGGER.debug("GET_PROGRAM_DESCRIPTIONS: Getting program descriptions")
            if json_result := response[_JsonKey.RESULT]:
                for data in json_result:
                    descriptions[data[_JsonKey.ID]] = cleanup_text_from_html_tags(
                        text=unquote(string=data[_JsonKey.DESCRIPTION], encoding=ISO_8859_1)
                    )
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.get_program_descriptions.decode_failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )
        return descriptions

    async def _get_script(self, *, script_name: str) -> str | None:
        """Return a script from the script cache. Load if required."""
        if script_name in self._script_cache:
            return self._script_cache[script_name]

        def _load_script(script_name: str) -> str | None:
            """Load script from file system."""
            script_file = os.path.join(Path(__file__).resolve().parent, REGA_SCRIPT_PATH, script_name)
            try:
                if script := Path(script_file).read_text(encoding=UTF_8):
                    self._script_cache[script_name] = script
                    return script
            except FileNotFoundError:
                return None
            return None

        return await self._looper.async_add_executor_job(_load_script, script_name, name=f"load_script-{script_name}")

    async def _get_serial(self) -> str | None:
        """Get the serial of the backend."""
        _LOGGER.debug("GET_SERIAL: Getting the backend serial")
        try:
            response = await self._post_script(script_name=RegaScript.GET_SERIAL)

            if json_result := response[_JsonKey.RESULT]:
                # The backend may return a JSON string which needs to be decoded first
                # or an already-parsed dict. Support both.
                if isinstance(json_result, str):
                    try:
                        json_result = orjson.loads(json_result)
                    except Exception:
                        # Fall back to plain string handling; return last 10 chars
                        serial_exc = str(json_result)
                        return serial_exc[-10:] if len(serial_exc) > 10 else serial_exc
                serial: str = str(json_result.get(_JsonKey.SERIAL) if isinstance(json_result, dict) else json_result)
                if len(serial) > 10:
                    serial = serial[-10:]
                return serial
        except JSONDecodeError as jderr:
            raise ClientException(jderr) from jderr
        return None

    async def _get_supported_methods(self) -> tuple[str, ...]:
        """Get the supported methods of the backend."""
        supported_methods: tuple[str, ...] = ()

        try:
            await self._login_or_renew()
            if not (session_id := self._session_id):
                raise ClientException(i18n.tr("exception.client.json_post.login_failed"))

            response = await self._do_post(
                session_id=session_id,
                method=_JsonRpcMethod.SYSTEM_LIST_METHODS,
            )

            _LOGGER.debug("GET_SUPPORTED_METHODS: Getting the supported methods")
            if json_result := response[_JsonKey.RESULT]:
                supported_methods = tuple(method_description[_JsonKey.NAME] for method_description in json_result)
        except BaseHomematicException:
            return ()

        return supported_methods

    async def _get_system_variable_descriptions(self) -> Mapping[str, str]:
        """Get all system variable descriptions from the backend via script."""
        descriptions: dict[str, str] = {}
        try:
            response = await self._post_script(script_name=RegaScript.GET_SYSTEM_VARIABLE_DESCRIPTIONS)

            _LOGGER.debug("GET_SYSTEM_VARIABLE_DESCRIPTIONS: Getting system variable descriptions")
            if json_result := response[_JsonKey.RESULT]:
                for data in json_result:
                    descriptions[data[_JsonKey.ID]] = cleanup_text_from_html_tags(
                        text=unquote(string=data[_JsonKey.DESCRIPTION], encoding=ISO_8859_1)
                    )
        except JSONDecodeError as jderr:
            _LOGGER.error(
                i18n.tr(
                    "log.client.json_rpc.get_system_variable_descriptions.decode_failed",
                    reason=extract_exc_args(exc=jderr),
                )
            )
        return descriptions

    async def _list_interfaces(self) -> tuple[str, ...]:
        """List all available interfaces from the backend."""
        _LOGGER.debug("LIST_INTERFACES: Getting all available interfaces")

        response = await self._post(
            method=_JsonRpcMethod.INTERFACE_LIST_INTERFACES,
        )

        if json_result := response[_JsonKey.RESULT]:
            return tuple(interface[_JsonKey.NAME] for interface in json_result)
        return ()

    async def _login_or_renew(self) -> bool:
        """Renew JSON-RPC session or perform login."""
        if not self.is_activated:
            self._session_id = await self._do_login()
            self._last_session_id_refresh = datetime.now()
            return self._session_id is not None
        if self._session_id:
            self._session_id = await self._do_renew_login(session_id=self._session_id)
        return self._session_id is not None

    async def _post(
        self,
        *,
        method: _JsonRpcMethod,
        extra_params: Mapping[Any, Any] | None = None,
        use_default_params: bool = True,
        keep_session: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST function."""
        if keep_session:
            await self._login_or_renew()
            session_id = self._session_id
        else:
            session_id = await self._do_login()

        if not session_id:
            raise ClientException(i18n.tr("exception.client.json_post.login_failed"))

        if self._supported_methods is None:
            await self._check_supported_methods()

        response = await self._do_post(
            session_id=session_id,
            method=method,
            extra_params=extra_params,
            use_default_params=use_default_params,
        )

        if extra_params:
            _LOGGER.debug("POST method: %s [%s]", method, extra_params)
        else:
            _LOGGER.debug("POST method: %s", method)

        if not keep_session:
            await self._do_logout(session_id=session_id)

        return response

    async def _post_script(
        self,
        *,
        script_name: str,
        extra_params: dict[_JsonKey, Any] | None = None,
        keep_session: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST_SCRIPT function."""
        # Load and validate script first to avoid any network when script is missing
        if (script := await self._get_script(script_name=script_name)) is None:
            raise ClientException(i18n.tr("exception.client.script.missing", script=script_name))

        # Prepare session only after we know we have a script to run
        if keep_session:
            await self._login_or_renew()
            session_id = self._session_id
        else:
            session_id = await self._do_login()

        if not session_id:
            raise ClientException(i18n.tr("exception.client.json_post.login_failed"))

        if self._supported_methods is None:
            await self._check_supported_methods()

        if extra_params:
            for variable, value in extra_params.items():
                script = script.replace(f"##{variable}##", value)

        method = _JsonRpcMethod.REGA_RUN_SCRIPT
        response = await self._do_post(
            session_id=session_id,
            method=method,
            extra_params={_JsonKey.SCRIPT: script},
        )

        _LOGGER.debug("POST_SCRIPT: method: %s [%s]", method, script_name)

        try:
            if not response[_JsonKey.ERROR] and (resp := response[_JsonKey.RESULT]) and isinstance(resp, str):
                response[_JsonKey.RESULT] = orjson.loads(resp)
        finally:
            if not keep_session:
                await self._do_logout(session_id=session_id)

        return response

    def _record_session(
        self,
        *,
        method: str,
        params: Mapping[str, Any],
        response: dict[str, Any] | None = None,
        exc: Exception | None = None,
    ) -> bool:
        """Record the session."""
        params = dict(params)
        if method == _JsonRpcMethod.SESSION_LOGIN and isinstance(params, dict):
            if params.get(_JsonKey.USERNAME):
                params[_JsonKey.USERNAME] = "********"
            if params.get(_JsonKey.PASSWORD):
                params[_JsonKey.PASSWORD] = "********"

        if script := params.get(_JsonKey.SCRIPT):
            params[_JsonKey.SCRIPT] = cleanup_script_for_session_recorder(script=script)

        if self._session_recorder and self._session_recorder.active:
            self._session_recorder.add_json_rpc_session(
                method=method, params=params, response=response, session_exc=exc
            )
            return True
        return False


def _determine_ccu_type(*, product: str) -> CCUType:
    """
    Determine the CCU type.

    CCU types:
    - CCU: Original CCU2/CCU3 hardware and debmatic (CCU clone)
    - OPENCCU: OpenCCU (modern variants with online update check)

    """
    # Check for original CCU hardware and debmatic
    if (product_lower := product.lower()) in ("ccu"):
        return CCUType.CCU

    if product_lower in ("openccu"):
        return CCUType.OPENCCU

    return CCUType.UNKNOWN


def _get_params(
    *,
    session_id: bool | str,
    extra_params: Mapping[Any, Any] | None,
    use_default_params: bool,
) -> Mapping[str, Any]:
    """Add additional params to default prams."""
    params: dict[Any, Any] = {_JsonKey.SESSION_ID: session_id} if use_default_params else {}
    if extra_params:
        params.update(extra_params)

    return {str(key): str(value) for key, value in params.items()}
