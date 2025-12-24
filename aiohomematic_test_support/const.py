# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Constants for tests."""

from __future__ import annotations

import functools
import json
import os
from typing import cast

from aiohomematic.client.json_rpc import _JsonKey
from aiohomematic.const import LOCAL_HOST, UTF_8, HubValueType, Interface, ProgramData, SystemVariableData

CENTRAL_NAME = "CentralTest"
CCU_HOST = LOCAL_HOST
CCU_USERNAME = "user"
CCU_PASSWORD = "pass"
CCU_PORT = 2002
CCU_MINI_PORT = 2003
INTERFACE_ID = f"{CENTRAL_NAME}-{Interface.BIDCOS_RF}"

# Backend info response for get_backend_info.fn script
BACKEND_INFO_JSON = {
    "version": "3.75.6.20240316",
    "product": "CCU3",
    "hostname": "ccu-test",
}

FULL_SESSION_RANDOMIZED_PYDEVCCU = "full_session_randomized_pydevccu.zip"
FULL_SESSION_RANDOMIZED_CCU = "full_session_randomized_ccu.zip"

ALL_SESSION_FILES = [
    FULL_SESSION_RANDOMIZED_PYDEVCCU,
    FULL_SESSION_RANDOMIZED_CCU,
]


SYSVAR_DATA: list[SystemVariableData] = [
    SystemVariableData(
        vid="1",
        legacy_name="alarm",
        description="",
        data_type=HubValueType.ALARM,
        unit=None,
        value=False,
        values=None,
        max_value=None,
        min_value=None,
        extended_sysvar=False,
    ),
    SystemVariableData(
        vid="2",
        legacy_name="alarm_ext",
        description="HAHM",
        data_type=HubValueType.ALARM,
        unit=None,
        value=False,
        values=None,
        max_value=None,
        min_value=None,
        extended_sysvar=True,
    ),
    SystemVariableData(
        vid="3",
        legacy_name="logic",
        description="",
        data_type=HubValueType.LOGIC,
        unit=None,
        value=False,
        values=None,
        max_value=None,
        min_value=None,
        extended_sysvar=False,
    ),
    SystemVariableData(
        vid="4",
        legacy_name="logic_ext",
        description="HAHM",
        data_type=HubValueType.LOGIC,
        unit=None,
        value=False,
        values=None,
        max_value=None,
        min_value=None,
        extended_sysvar=True,
    ),
    SystemVariableData(
        vid="5",
        legacy_name="list",
        description="",
        data_type=HubValueType.LIST,
        unit=None,
        value=0,
        values=("v1", "v2", "v3"),
        max_value=None,
        min_value=None,
        extended_sysvar=False,
    ),
    SystemVariableData(
        vid="6",
        legacy_name="list_ext",
        description="HAHM",
        data_type=HubValueType.LIST,
        unit=None,
        value=0,
        values=("v1", "v2", "v3"),
        max_value=None,
        min_value=None,
        extended_sysvar=True,
    ),
    SystemVariableData(
        vid="7",
        legacy_name="string",
        description="",
        data_type=HubValueType.STRING,
        unit=None,
        value="test1",
        values=None,
        max_value=None,
        min_value=None,
        extended_sysvar=False,
    ),
    SystemVariableData(
        vid="8",
        legacy_name="string_ext",
        description="HAHM",
        data_type=HubValueType.STRING,
        unit=None,
        value="test1",
        values=None,
        max_value=None,
        min_value=None,
        extended_sysvar=True,
    ),
    SystemVariableData(
        vid="9",
        legacy_name="float",
        description="",
        data_type=HubValueType.FLOAT,
        unit=None,
        value=23.2,
        values=None,
        max_value=30.0,
        min_value=5.0,
        extended_sysvar=False,
    ),
    SystemVariableData(
        vid="10",
        legacy_name="float_ext",
        description="HAHM",
        data_type=HubValueType.FLOAT,
        unit="°C",
        value=23.2,
        values=None,
        max_value=30.0,
        min_value=5.0,
        extended_sysvar=True,
    ),
    SystemVariableData(
        vid="11",
        legacy_name="integer",
        description="",
        data_type=HubValueType.INTEGER,
        unit=None,
        value=17,
        values=None,
        max_value=30,
        min_value=5,
        extended_sysvar=False,
    ),
    SystemVariableData(
        vid="12",
        legacy_name="integer_ext",
        description="HAHM",
        data_type=HubValueType.INTEGER,
        unit=None,
        value=17,
        values=None,
        max_value=30,
        min_value=5,
        extended_sysvar=True,
    ),
]


SYSVAR_DATA_JSON = [
    {
        _JsonKey.ID: sv.vid,
        _JsonKey.IS_INTERNAL: False,
        _JsonKey.MAX_VALUE: sv.max_value,
        _JsonKey.MIN_VALUE: sv.min_value,
        _JsonKey.NAME: sv.legacy_name,
        _JsonKey.TYPE: sv.data_type,
        _JsonKey.UNIT: sv.unit,
        _JsonKey.VALUE: sv.value,
        _JsonKey.VALUE_LIST: ";".join(sv.values) if sv.values else None,
    }
    for sv in SYSVAR_DATA
]
SYSVAR_DATA_JSON_DESCRIPTION = [
    {
        _JsonKey.ID: sv.vid,
        _JsonKey.DESCRIPTION: sv.description,
    }
    for sv in SYSVAR_DATA
]

SYSVAR_DATA_XML = {sv.legacy_name: sv.value for sv in SYSVAR_DATA}

PROGRAM_DATA: list[ProgramData] = [
    ProgramData(
        legacy_name="p1",
        pid="pid1",
        description="1",
        is_active=True,
        is_internal=False,
        last_execute_time="",
    ),
    ProgramData(
        legacy_name="p_2",
        pid="pid2",
        description="2",
        is_active=False,
        is_internal=False,
        last_execute_time="",
    ),
]
PROGRAM_DATA_JSON = [
    {
        _JsonKey.ID: p.pid,
        _JsonKey.IS_ACTIVE: p.is_active,
        _JsonKey.IS_INTERNAL: p.is_internal,
        _JsonKey.LAST_EXECUTE_TIME: p.last_execute_time,
        _JsonKey.NAME: p.legacy_name,
    }
    for p in PROGRAM_DATA
]
PROGRAM_DATA_JSON_DESCRIPTION = [
    {
        _JsonKey.ID: p.pid,
        _JsonKey.DESCRIPTION: p.description,
    }
    for p in PROGRAM_DATA
]


@functools.cache
def _load_device_translation() -> dict[str, str]:
    """Load device translation mapping from JSON file."""
    file_path = os.path.join(os.path.dirname(__file__), "data", "device_translation.json")
    if os.path.exists(file_path):
        with open(file_path, encoding=UTF_8) as f:
            return cast(dict[str, str], json.load(f))
    return {}


def get_address_device_translation() -> dict[str, str]:
    """Return the address to device translation mapping."""
    return _load_device_translation()


# Public accessor - use this instead of direct dict access
ADDRESS_DEVICE_TRANSLATION = get_address_device_translation()
