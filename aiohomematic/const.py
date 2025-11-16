# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Constants used by aiohomematic.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum, StrEnum
import inspect
import os
import re
import sys
from types import MappingProxyType
from typing import Any, Final, NamedTuple, Required, TypedDict

VERSION: Final = "2025.11.17"

# Detect test speedup mode via environment
_TEST_SPEEDUP: Final = (
    bool(os.getenv("AIOHOMEMATIC_TEST_SPEEDUP")) or ("PYTEST_CURRENT_TEST" in os.environ) or ("pytest" in sys.modules)
)

# default
DEFAULT_DELAY_NEW_DEVICE_CREATION: Final = False
DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK: Final = False
DEFAULT_ENABLE_PROGRAM_SCAN: Final = True
DEFAULT_ENABLE_SYSVAR_SCAN: Final = True
DEFAULT_HM_MASTER_POLL_AFTER_SEND_INTERVALS: Final = (5,)
DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS: Final[frozenset[str]] = frozenset()
DEFAULT_INCLUDE_INTERNAL_PROGRAMS: Final = False
DEFAULT_INCLUDE_INTERNAL_SYSVARS: Final = True
DEFAULT_LOCALE: Final = "en"
DEFAULT_MAX_READ_WORKERS: Final = 1
DEFAULT_MAX_WORKERS: Final = 1
DEFAULT_MULTIPLIER: Final = 1.0
DEFAULT_OPTIONAL_SETTINGS: Final[tuple[OptionalSettings | str, ...]] = ()
DEFAULT_PERIODIC_REFRESH_INTERVAL: Final = 15
DEFAULT_PROGRAM_MARKERS: Final[tuple[DescriptionMarker | str, ...]] = ()
DEFAULT_SESSION_RECORDER_START_FOR_SECONDS: Final = 180
DEFAULT_STORAGE_DIRECTORY: Final = "aiohomematic_storage"
DEFAULT_SYSVAR_MARKERS: Final[tuple[DescriptionMarker | str, ...]] = ()
DEFAULT_SYS_SCAN_INTERVAL: Final = 30
DEFAULT_TLS: Final = False
DEFAULT_UN_IGNORES: Final[frozenset[str]] = frozenset()
DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE: Final = True
DEFAULT_VERIFY_TLS: Final = False

# Default encoding for json service calls, persistent cache
UTF_8: Final = "utf-8"
# Default encoding for xmlrpc service calls and script files
ISO_8859_1: Final = "iso-8859-1"

BIDCOS_DEVICE_CHANNEL_DUMMY: Final = 999

# Password can be empty.
# Allowed characters: A-Z, a-z, 0-9, .!$():;#-
# The CCU WebUI also supports ÄäÖöÜüß, but these characters are not supported by the XmlRPC servers
CCU_PASSWORD_PATTERN: Final = re.compile(r"[A-Za-z0-9.!$():;#-]{0,}")
# Pattern is bigger than needed
CHANNEL_ADDRESS_PATTERN: Final = re.compile(r"^[0-9a-zA-Z-]{5,20}:[0-9]{1,3}$")
DEVICE_ADDRESS_PATTERN: Final = re.compile(r"^[0-9a-zA-Z-]{5,20}$")
ALLOWED_HOSTNAME_PATTERN: Final = re.compile(r"(?!-)[a-z0-9-]{1,63}(?<!-)$", re.IGNORECASE)
HTMLTAG_PATTERN: Final = re.compile(r"<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")
SCHEDULER_PROFILE_PATTERN: Final = re.compile(
    r"^P[1-6]_(ENDTIME|TEMPERATURE)_(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)_([1-9]|1[0-3])$"
)
SCHEDULER_TIME_PATTERN: Final = re.compile(r"^(([0-1]{0,1}[0-9])|(2[0-4])):[0-5][0-9]")
WEEK_PROFILE_PATTERN: Final = re.compile(r".*WEEK_PROFILE$")

ALWAYS_ENABLE_SYSVARS_BY_ID: Final[frozenset[str]] = frozenset({"40", "41"})
RENAME_SYSVAR_BY_NAME: Final[Mapping[str, str]] = MappingProxyType(
    {
        "${sysVarAlarmMessages}": "ALARM_MESSAGES",
        "${sysVarPresence}": "PRESENCE",
        "${sysVarServiceMessages}": "SERVICE_MESSAGES",
    }
)

# Deprecated alias (use ALWAYS_ENABLE_SYSVARS_BY_ID). Kept for backward compatibility.
SYSVAR_ENABLE_DEFAULT: Final[frozenset[str]] = ALWAYS_ENABLE_SYSVARS_BY_ID

ADDRESS_SEPARATOR: Final = ":"
BLOCK_LOG_TIMEOUT: Final = 60
CONTENT_PATH: Final = "cache"
CONF_PASSWORD: Final = "password"
CONF_USERNAME: Final = "username"

CONNECTION_CHECKER_INTERVAL: Final = 1 if _TEST_SPEEDUP else 15  # check if connection is available via rpc ping
DATETIME_FORMAT: Final = "%d.%m.%Y %H:%M:%S"
DATETIME_FORMAT_MILLIS: Final = "%d.%m.%Y %H:%M:%S.%f'"
DEVICE_DESCRIPTIONS_DIR: Final = "export_device_descriptions"
DEVICE_FIRMWARE_CHECK_INTERVAL: Final = 21600  # 6h
DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL: Final = 3600  # 1h
DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL: Final = 300  # 5m
DUMMY_SERIAL: Final = "SN0815"
FILE_DEVICES: Final = "homematic_devices"
FILE_PARAMSETS: Final = "homematic_paramsets"
FILE_SESSION_RECORDER: Final = "homematic_session_recorder"
FILE_NAME_TS_PATTERN: Final = "%Y%m%d_%H%M%S"
SUB_DIRECTORY_CACHE: Final = "cache"
SUB_DIRECTORY_SESSION: Final = "session"
HUB_PATH: Final = "hub"
IDENTIFIER_SEPARATOR: Final = "@"
INIT_DATETIME: Final = datetime.strptime("01.01.1970 00:00:00", DATETIME_FORMAT)
IP_ANY_V4: Final = "0.0.0.0"
JSON_SESSION_AGE: Final = 90
KWARGS_ARG_CUSTOM_ID: Final = "custom_id"
KWARGS_ARG_DATA_POINT: Final = "data_point"
LAST_COMMAND_SEND_STORE_TIMEOUT: Final = 60
LOCAL_HOST: Final = "127.0.0.1"
MAX_CACHE_AGE: Final = 10
MAX_CONCURRENT_HTTP_SESSIONS: Final = 3
MAX_WAIT_FOR_CALLBACK: Final = 60
NO_CACHE_ENTRY: Final = "NO_CACHE_ENTRY"
PARAMSET_DESCRIPTIONS_DIR: Final = "export_paramset_descriptions"
PATH_JSON_RPC: Final = "/api/homematic.cgi"
PING_PONG_MISMATCH_COUNT: Final = 15
PING_PONG_MISMATCH_COUNT_TTL: Final = 300
PORT_ANY: Final = 0
PROGRAM_ADDRESS: Final = "program"
RECONNECT_WAIT: Final = 1 if _TEST_SPEEDUP else 120  # wait with reconnect after a first ping was successful
REGA_SCRIPT_PATH: Final = "../rega_scripts"
REPORT_VALUE_USAGE_DATA: Final = "reportValueUsageData"
REPORT_VALUE_USAGE_VALUE_ID: Final = "PRESS_SHORT"
SYSVAR_ADDRESS: Final = "sysvar"
TIMEOUT: Final = 5 if _TEST_SPEEDUP else 60  # default timeout for a connection
UN_IGNORE_WILDCARD: Final = "all"
WAIT_FOR_CALLBACK: Final[int | None] = None

# Scheduler sleep durations (used by central scheduler loop)
SCHEDULER_NOT_STARTED_SLEEP: Final = 0.2 if _TEST_SPEEDUP else 10
SCHEDULER_LOOP_SLEEP: Final = 0.2 if _TEST_SPEEDUP else 5

CALLBACK_WARN_INTERVAL: Final = CONNECTION_CHECKER_INTERVAL * 40

# Path
PROGRAM_SET_PATH_ROOT: Final = "program/set"
PROGRAM_STATE_PATH_ROOT: Final = "program/status"
SET_PATH_ROOT: Final = "device/set"
STATE_PATH_ROOT: Final = "device/status"
SYSVAR_SET_PATH_ROOT: Final = "sysvar/set"
SYSVAR_STATE_PATH_ROOT: Final = "sysvar/status"
VIRTDEV_SET_PATH_ROOT: Final = "virtdev/set"
VIRTDEV_STATE_PATH_ROOT: Final = "virtdev/status"


class Backend(StrEnum):
    """Enum with supported aiohomematic backends."""

    CCU = "CCU"
    HOMEGEAR = "Homegear"
    PYDEVCCU = "PyDevCCU"


class BackendSystemEvent(StrEnum):
    """Enum with aiohomematic system events."""

    DELETE_DEVICES = "deleteDevices"
    DEVICES_CREATED = "devicesCreated"
    DEVICES_DELAYED = "devicesDelayed"
    ERROR = "error"
    HUB_REFRESHED = "hubDataPointRefreshed"
    LIST_DEVICES = "listDevices"
    NEW_DEVICES = "newDevices"
    REPLACE_DEVICE = "replaceDevice"
    RE_ADDED_DEVICE = "readdedDevice"
    UPDATE_DEVICE = "updateDevice"


class CallSource(StrEnum):
    """Enum with sources for calls."""

    HA_INIT = "ha_init"
    HM_INIT = "hm_init"
    MANUAL_OR_SCHEDULED = "manual_or_scheduled"


class CalulatedParameter(StrEnum):
    """Enum with calculated Homematic parameters."""

    APPARENT_TEMPERATURE = "APPARENT_TEMPERATURE"
    DEW_POINT = "DEW_POINT"
    DEW_POINT_SPREAD = "DEW_POINT_SPREAD"
    ENTHALPY = "ENTHALPY"
    FROST_POINT = "FROST_POINT"
    OPERATING_VOLTAGE_LEVEL = "OPERATING_VOLTAGE_LEVEL"
    VAPOR_CONCENTRATION = "VAPOR_CONCENTRATION"


class CDPD(StrEnum):
    """Enum for custom data point definitions."""

    ADDITIONAL_DPS = "additional_dps"
    ALLOW_UNDEFINED_GENERIC_DPS = "allow_undefined_generic_dps"
    DEFAULT_DPS = "default_dps"
    DEVICE_DEFINITIONS = "device_definitions"
    DEVICE_GROUP = "device_group"
    FIELDS = "fields"
    INCLUDE_DEFAULT_DPS = "include_default_dps"
    PRIMARY_CHANNEL = "primary_channel"
    REPEATABLE_FIELDS = "repeatable_fields"
    SECONDARY_CHANNELS = "secondary_channels"
    STATE_CHANNEL = "state_channel"
    VISIBLE_FIELDS = "visible_fields"
    VISIBLE_REPEATABLE_FIELDS = "visible_repeatable_fields"


class CentralUnitState(StrEnum):
    """Enum with central unit states."""

    INITIALIZING = "initializing"
    NEW = "new"
    RUNNING = "running"
    STOPPED = "stopped"
    STOPPED_BY_ERROR = "stopped_by_error"
    STOPPING = "stopping"


class CommandRxMode(StrEnum):
    """Enum for Homematic rx modes for commands."""

    BURST = "BURST"
    WAKEUP = "WAKEUP"


class DataOperationResult(Enum):
    """Enum with data operation results."""

    LOAD_FAIL = 0
    LOAD_SUCCESS = 1
    SAVE_FAIL = 10
    SAVE_SUCCESS = 11
    NO_LOAD = 20
    NO_SAVE = 21


class DataPointCategory(StrEnum):
    """Enum with data point types."""

    ACTION = "action"
    BINARY_SENSOR = "binary_sensor"
    BUTTON = "button"
    CLIMATE = "climate"
    COVER = "cover"
    EVENT = "event"
    HUB_BINARY_SENSOR = "hub_binary_sensor"
    HUB_BUTTON = "hub_button"
    HUB_NUMBER = "hub_number"
    HUB_SELECT = "hub_select"
    HUB_SENSOR = "hub_sensor"
    HUB_SWITCH = "hub_switch"
    HUB_TEXT = "hub_text"
    LIGHT = "light"
    LOCK = "lock"
    NUMBER = "number"
    SELECT = "select"
    SENSOR = "sensor"
    SIREN = "siren"
    SWITCH = "switch"
    TEXT = "text"
    UNDEFINED = "undefined"
    UPDATE = "update"
    VALVE = "valve"


class DataPointKey(NamedTuple):
    """Key for data points."""

    interface_id: str
    channel_address: str
    paramset_key: ParamsetKey
    parameter: str


class DataPointUsage(StrEnum):
    """Enum with usage information."""

    CDP_PRIMARY = "ce_primary"
    CDP_SECONDARY = "ce_secondary"
    CDP_VISIBLE = "ce_visible"
    DATA_POINT = "data_point"
    EVENT = "event"
    NO_CREATE = "no_create"


class DescriptionMarker(StrEnum):
    """Enum with default description markers."""

    HAHM = "HAHM"
    HX = "HX"
    INTERNAL = "INTERNAL"
    MQTT = "MQTT"


class DeviceFirmwareState(StrEnum):
    """Enum with Homematic device firmware states."""

    UNKNOWN = "UNKNOWN"
    UP_TO_DATE = "UP_TO_DATE"
    LIVE_UP_TO_DATE = "LIVE_UP_TO_DATE"
    NEW_FIRMWARE_AVAILABLE = "NEW_FIRMWARE_AVAILABLE"
    LIVE_NEW_FIRMWARE_AVAILABLE = "LIVE_NEW_FIRMWARE_AVAILABLE"
    DELIVER_FIRMWARE_IMAGE = "DELIVER_FIRMWARE_IMAGE"
    LIVE_DELIVER_FIRMWARE_IMAGE = "LIVE_DELIVER_FIRMWARE_IMAGE"
    READY_FOR_UPDATE = "READY_FOR_UPDATE"
    DO_UPDATE_PENDING = "DO_UPDATE_PENDING"
    PERFORMING_UPDATE = "PERFORMING_UPDATE"
    BACKGROUND_UPDATE_NOT_SUPPORTED = "BACKGROUND_UPDATE_NOT_SUPPORTED"


class DeviceProfile(StrEnum):
    """Enum for device profiles."""

    IP_BUTTON_LOCK = "IPButtonLock"
    IP_COVER = "IPCover"
    IP_DIMMER = "IPDimmer"
    IP_DRG_DALI = "IPDRGDALI"
    IP_FIXED_COLOR_LIGHT = "IPFixedColorLight"
    IP_GARAGE = "IPGarage"
    IP_HDM = "IPHdm"
    IP_IRRIGATION_VALVE = "IPIrrigationValve"
    IP_LOCK = "IPLock"
    IP_RGBW_LIGHT = "IPRGBW"
    IP_SIMPLE_FIXED_COLOR_LIGHT = "IPSimpleFixedColorLight"
    IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED = "IPSimpleFixedColorLightWired"
    IP_SIREN = "IPSiren"
    IP_SIREN_SMOKE = "IPSirenSmoke"
    IP_SWITCH = "IPSwitch"
    IP_THERMOSTAT = "IPThermostat"
    IP_THERMOSTAT_GROUP = "IPThermostatGroup"
    RF_BUTTON_LOCK = "RFButtonLock"
    RF_COVER = "RfCover"
    RF_DIMMER = "RfDimmer"
    RF_DIMMER_COLOR = "RfDimmer_Color"
    RF_DIMMER_COLOR_FIXED = "RfDimmer_Color_Fixed"
    RF_DIMMER_COLOR_TEMP = "RfDimmer_Color_Temp"
    RF_DIMMER_WITH_VIRT_CHANNEL = "RfDimmerWithVirtChannel"
    RF_LOCK = "RfLock"
    RF_SIREN = "RfSiren"
    RF_SWITCH = "RfSwitch"
    RF_THERMOSTAT = "RfThermostat"
    RF_THERMOSTAT_GROUP = "RfThermostatGroup"
    SIMPLE_RF_THERMOSTAT = "SimpleRfThermostat"


class EventKey(StrEnum):
    """Enum with aiohomematic event keys."""

    ADDRESS = "address"
    AVAILABLE = "available"
    CENTRAL_NAME = "central_name"
    CHANNEL_NO = "channel_no"
    DATA = "data"
    INTERFACE_ID = "interface_id"
    MODEL = "model"
    PARAMETER = "parameter"
    PONG_MISMATCH_ACCEPTABLE = "pong_mismatch_allowed"
    PONG_MISMATCH_COUNT = "pong_mismatch_count"
    SECONDS_SINCE_LAST_EVENT = "seconds_since_last_event"
    TYPE = "type"
    VALUE = "value"


class EventType(StrEnum):
    """Enum with aiohomematic event types."""

    DEVICE_AVAILABILITY = "homematic.device_availability"
    DEVICE_ERROR = "homematic.device_error"
    IMPULSE = "homematic.impulse"
    INTERFACE = "homematic.interface"
    KEYPRESS = "homematic.keypress"


class Field(Enum):
    """Enum for fields."""

    ACOUSTIC_ALARM_ACTIVE = "acoustic_alarm_active"
    ACOUSTIC_ALARM_SELECTION = "acoustic_alarm_selection"
    ACTIVE_PROFILE = "active_profile"
    AUTO_MODE = "auto_mode"
    BOOST_MODE = "boost_mode"
    BUTTON_LOCK = "button_lock"
    CHANNEL_COLOR = "channel_color"
    COLOR = "color"
    COLOR_BEHAVIOUR = "color_behaviour"
    COLOR_LEVEL = "color_temp"
    COLOR_TEMPERATURE = "color_temperature"
    COMBINED_PARAMETER = "combined_parameter"
    COMFORT_MODE = "comfort_mode"
    CONCENTRATION = "concentration"
    CONTROL_MODE = "control_mode"
    CURRENT = "current"
    DEVICE_OPERATION_MODE = "device_operation_mode"
    DIRECTION = "direction"
    DOOR_COMMAND = "door_command"
    DOOR_STATE = "door_state"
    DURATION = "duration"
    DURATION_UNIT = "duration_unit"
    DUTYCYCLE = "dutycycle"
    DUTY_CYCLE = "duty_cycle"
    EFFECT = "effect"
    ENERGY_COUNTER = "energy_counter"
    ERROR = "error"
    FREQUENCY = "frequency"
    GROUP_LEVEL = "group_level"
    GROUP_LEVEL_2 = "group_level_2"
    GROUP_STATE = "group_state"
    HEATING_COOLING = "heating_cooling"
    HEATING_VALVE_TYPE = "heating_valve_type"
    HUE = "hue"
    HUMIDITY = "humidity"
    INHIBIT = "inhibit"
    LEVEL = "level"
    LEVEL_2 = "level_2"
    LEVEL_COMBINED = "level_combined"
    LOCK_STATE = "lock_state"
    LOCK_TARGET_LEVEL = "lock_target_level"
    LOWBAT = "lowbat"
    LOWERING_MODE = "lowering_mode"
    LOW_BAT = "low_bat"
    LOW_BAT_LIMIT = "low_bat_limit"
    MANU_MODE = "manu_mode"
    MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE = "min_max_value_not_relevant_for_manu_mode"
    ON_TIME_UNIT = "on_time_unit"
    ON_TIME_VALUE = "on_time_value"
    OPEN = "open"
    OPERATING_VOLTAGE = "operating_voltage"
    OPERATION_MODE = "channel_operation_mode"
    OPTICAL_ALARM_ACTIVE = "optical_alarm_active"
    OPTICAL_ALARM_SELECTION = "optical_alarm_selection"
    OPTIMUM_START_STOP = "optimum_start_stop"
    PARTY_MODE = "party_mode"
    POWER = "power"
    PROGRAM = "program"
    RAMP_TIME_TO_OFF_UNIT = "ramp_time_to_off_unit"
    RAMP_TIME_TO_OFF_VALUE = "ramp_time_to_off_value"
    RAMP_TIME_UNIT = "ramp_time_unit"
    RAMP_TIME_VALUE = "ramp_time_value"
    RSSI_DEVICE = "rssi_device"
    RSSI_PEER = "rssi_peer"
    SABOTAGE = "sabotage"
    SATURATION = "saturation"
    SECTION = "section"
    SETPOINT = "setpoint"
    SET_POINT_MODE = "set_point_mode"
    SMOKE_DETECTOR_ALARM_STATUS = "smoke_detector_alarm_status"
    SMOKE_DETECTOR_COMMAND = "smoke_detector_command"
    STATE = "state"
    STOP = "stop"
    SWITCH_MAIN = "switch_main"
    SWITCH_V1 = "vswitch_1"
    SWITCH_V2 = "vswitch_2"
    TEMPERATURE = "temperature"
    TEMPERATURE_MAXIMUM = "temperature_maximum"
    TEMPERATURE_MINIMUM = "temperature_minimum"
    TEMPERATURE_OFFSET = "temperature_offset"
    VALVE_STATE = "valve_state"
    VOLTAGE = "voltage"
    WEEK_PROGRAM_POINTER = "week_program_pointer"


class Flag(IntEnum):
    """Enum with Homematic flags."""

    VISIBLE = 1
    INTERNAL = 2
    TRANSFORM = 4  # not used
    SERVICE = 8
    STICKY = 10  # This might be wrong. Documentation says 0x10 # not used


class ForcedDeviceAvailability(StrEnum):
    """Enum with aiohomematic event types."""

    FORCE_FALSE = "forced_not_available"
    FORCE_TRUE = "forced_available"
    NOT_SET = "not_set"


class InternalCustomID(StrEnum):
    """Enum for Homematic internal custom IDs."""

    DEFAULT = "cid_default"
    LINK_PEER = "cid_link_peer"
    MANU_TEMP = "cid_manu_temp"


class Manufacturer(StrEnum):
    """Enum with aiohomematic system events."""

    EQ3 = "eQ-3"
    HB = "Homebrew"
    MOEHLENHOFF = "Möhlenhoff"


class Operations(IntEnum):
    """Enum with Homematic operations."""

    NONE = 0  # not used
    READ = 1
    WRITE = 2
    EVENT = 4


class OptionalSettings(StrEnum):
    """Enum with aiohomematic optional settings."""

    ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY = "ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY"
    SR_DISABLE_RANDOMIZE_OUTPUT = "SR_DISABLE_RANDOMIZED_OUTPUT"
    SR_RECORD_SYSTEM_INIT = "SR_RECORD_SYSTEM_INIT"


class Parameter(StrEnum):
    """Enum with Homematic parameters."""

    ACOUSTIC_ALARM_ACTIVE = "ACOUSTIC_ALARM_ACTIVE"
    ACOUSTIC_ALARM_SELECTION = "ACOUSTIC_ALARM_SELECTION"
    ACTIVE_PROFILE = "ACTIVE_PROFILE"
    ACTIVITY_STATE = "ACTIVITY_STATE"
    ACTUAL_HUMIDITY = "ACTUAL_HUMIDITY"
    ACTUAL_TEMPERATURE = "ACTUAL_TEMPERATURE"
    AUTO_MODE = "AUTO_MODE"
    BATTERY_STATE = "BATTERY_STATE"
    BOOST_MODE = "BOOST_MODE"
    CHANNEL_OPERATION_MODE = "CHANNEL_OPERATION_MODE"
    COLOR = "COLOR"
    COLOR_BEHAVIOUR = "COLOR_BEHAVIOUR"
    COLOR_TEMPERATURE = "COLOR_TEMPERATURE"
    COMBINED_PARAMETER = "COMBINED_PARAMETER"
    COMFORT_MODE = "COMFORT_MODE"
    CONCENTRATION = "CONCENTRATION"
    CONFIG_PENDING = "CONFIG_PENDING"
    CONTROL_MODE = "CONTROL_MODE"
    CURRENT = "CURRENT"
    CURRENT_ILLUMINATION = "CURRENT_ILLUMINATION"
    DEVICE_OPERATION_MODE = "DEVICE_OPERATION_MODE"
    DIRECTION = "DIRECTION"
    DOOR_COMMAND = "DOOR_COMMAND"
    DOOR_STATE = "DOOR_STATE"
    DURATION_UNIT = "DURATION_UNIT"
    DURATION_VALUE = "DURATION_VALUE"
    DUTYCYCLE = "DUTYCYCLE"
    DUTY_CYCLE = "DUTY_CYCLE"
    EFFECT = "EFFECT"
    ENERGY_COUNTER = "ENERGY_COUNTER"
    ERROR = "ERROR"
    ERROR_JAMMED = "ERROR_JAMMED"
    FREQUENCY = "FREQUENCY"
    GLOBAL_BUTTON_LOCK = "GLOBAL_BUTTON_LOCK"
    HEATING_COOLING = "HEATING_COOLING"
    HEATING_VALVE_TYPE = "HEATING_VALVE_TYPE"
    HUE = "HUE"
    HUMIDITY = "HUMIDITY"
    ILLUMINATION = "ILLUMINATION"
    LED_STATUS = "LED_STATUS"
    LEVEL = "LEVEL"
    LEVEL_2 = "LEVEL_2"
    LEVEL_COMBINED = "LEVEL_COMBINED"
    LEVEL_SLATS = "LEVEL_SLATS"
    LOCK_STATE = "LOCK_STATE"
    LOCK_TARGET_LEVEL = "LOCK_TARGET_LEVEL"
    LOWBAT = "LOWBAT"
    LOWERING_MODE = "LOWERING_MODE"
    LOW_BAT = "LOW_BAT"
    LOW_BAT_LIMIT = "LOW_BAT_LIMIT"
    MANU_MODE = "MANU_MODE"
    MASS_CONCENTRATION_PM_10_24H_AVERAGE = "MASS_CONCENTRATION_PM_10_24H_AVERAGE"
    MASS_CONCENTRATION_PM_1_24H_AVERAGE = "MASS_CONCENTRATION_PM_1_24H_AVERAGE"
    MASS_CONCENTRATION_PM_2_5_24H_AVERAGE = "MASS_CONCENTRATION_PM_2_5_24H_AVERAGE"
    MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE = "MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE"
    MOTION = "MOTION"
    MOTION_DETECTION_ACTIVE = "MOTION_DETECTION_ACTIVE"
    ON_TIME = "ON_TIME"
    OPEN = "OPEN"
    OPERATING_VOLTAGE = "OPERATING_VOLTAGE"
    OPTICAL_ALARM_ACTIVE = "OPTICAL_ALARM_ACTIVE"
    OPTICAL_ALARM_SELECTION = "OPTICAL_ALARM_SELECTION"
    OPTIMUM_START_STOP = "OPTIMUM_START_STOP"
    PARTY_MODE = "PARTY_MODE"
    PARTY_MODE_SUBMIT = "PARTY_MODE_SUBMIT"
    PARTY_TIME_END = "PARTY_TIME_END"
    PARTY_TIME_START = "PARTY_TIME_START"
    PONG = "PONG"
    POWER = "POWER"
    PRESS = "PRESS"
    PRESS_CONT = "PRESS_CONT"
    PRESS_LOCK = "PRESS_LOCK"
    PRESS_LONG = "PRESS_LONG"
    PRESS_LONG_RELEASE = "PRESS_LONG_RELEASE"
    PRESS_LONG_START = "PRESS_LONG_START"
    PRESS_SHORT = "PRESS_SHORT"
    PRESS_UNLOCK = "PRESS_UNLOCK"
    PROGRAM = "PROGRAM"
    RAMP_TIME = "RAMP_TIME"
    RAMP_TIME_TO_OFF_UNIT = "RAMP_TIME_TO_OFF_UNIT"
    RAMP_TIME_TO_OFF_VALUE = "RAMP_TIME_TO_OFF_VALUE"
    RAMP_TIME_UNIT = "RAMP_TIME_UNIT"
    RAMP_TIME_VALUE = "RAMP_TIME_VALUE"
    RESET_MOTION = "RESET_MOTION"
    RSSI_DEVICE = "RSSI_DEVICE"
    RSSI_PEER = "RSSI_PEER"
    SABOTAGE = "SABOTAGE"
    SATURATION = "SATURATION"
    SECTION = "SECTION"
    SENSOR = "SENSOR"
    SENSOR_ERROR = "SENSOR_ERROR"
    SEQUENCE_OK = "SEQUENCE_OK"
    SETPOINT = "SETPOINT"
    SET_POINT_MODE = "SET_POINT_MODE"
    SET_POINT_TEMPERATURE = "SET_POINT_TEMPERATURE"
    SET_TEMPERATURE = "SET_TEMPERATURE"
    SMOKE_DETECTOR_ALARM_STATUS = "SMOKE_DETECTOR_ALARM_STATUS"
    SMOKE_DETECTOR_COMMAND = "SMOKE_DETECTOR_COMMAND"
    STATE = "STATE"
    STATUS = "STATUS"
    STICKY_UN_REACH = "STICKY_UNREACH"
    STOP = "STOP"
    SUNSHINE_DURATION = "SUNSHINEDURATION"
    TEMPERATURE = "TEMPERATURE"
    TEMPERATURE_MAXIMUM = "TEMPERATURE_MAXIMUM"
    TEMPERATURE_MINIMUM = "TEMPERATURE_MINIMUM"
    TEMPERATURE_OFFSET = "TEMPERATURE_OFFSET"
    TIME_OF_OPERATION = "TIME_OF_OPERATION"
    UN_REACH = "UNREACH"
    UPDATE_PENDING = "UPDATE_PENDING"
    VALVE_STATE = "VALVE_STATE"
    VOLTAGE = "VOLTAGE"
    WATER_FLOW = "WATER_FLOW"
    WATER_VOLUME = "WATER_VOLUME"
    WATER_VOLUME_SINCE_OPEN = "WATER_VOLUME_SINCE_OPEN"
    WEEK_PROGRAM_POINTER = "WEEK_PROGRAM_POINTER"
    WIND_DIRECTION = "WIND_DIRECTION"
    WIND_DIRECTION_RANGE = "WIND_DIRECTION_RANGE"
    WIND_SPEED = "WIND_SPEED"
    WORKING = "WORKING"


class ParamsetKey(StrEnum):
    """Enum with paramset keys."""

    CALCULATED = "CALCULATED"
    DUMMY = "DUMMY"
    LINK = "LINK"
    MASTER = "MASTER"
    SERVICE = "SERVICE"
    VALUES = "VALUES"


class ProductGroup(StrEnum):
    """Enum with Homematic product groups."""

    HM = "BidCos-RF"
    HMIP = "HmIP-RF"
    HMIPW = "HmIP-Wired"
    HMW = "BidCos-Wired"
    UNKNOWN = "unknown"
    VIRTUAL = "VirtualDevices"


class RegaScript(StrEnum):
    """Enum with Homematic rega scripts."""

    FETCH_ALL_DEVICE_DATA: Final = "fetch_all_device_data.fn"
    GET_PROGRAM_DESCRIPTIONS: Final = "get_program_descriptions.fn"
    GET_SERIAL: Final = "get_serial.fn"
    GET_SYSTEM_VARIABLE_DESCRIPTIONS: Final = "get_system_variable_descriptions.fn"
    SET_PROGRAM_STATE: Final = "set_program_state.fn"
    SET_SYSTEM_VARIABLE: Final = "set_system_variable.fn"


class RPCType(StrEnum):
    """Enum with Homematic rpc types."""

    XML_RPC = "xmlrpc"
    JSON_RPC = "jsonrpc"


class Interface(StrEnum):
    """Enum with Homematic interfaces."""

    BIDCOS_RF = "BidCos-RF"
    BIDCOS_WIRED = "BidCos-Wired"
    CCU_JACK = "CCU-Jack"
    CUXD = "CUxD"
    HMIP_RF = "HmIP-RF"
    VIRTUAL_DEVICES = "VirtualDevices"


class InterfaceEventType(StrEnum):
    """Enum with aiohomematic interface event types."""

    CALLBACK = "callback"
    FETCH_DATA = "fetch_data"
    PENDING_PONG = "pending_pong"
    PROXY = "proxy"
    UNKNOWN_PONG = "unknown_pong"


class ParameterType(StrEnum):
    """Enum for Homematic parameter types."""

    ACTION = "ACTION"  # Usually buttons, send Boolean to trigger
    BOOL = "BOOL"
    DUMMY = "DUMMY"
    ENUM = "ENUM"
    FLOAT = "FLOAT"
    INTEGER = "INTEGER"
    STRING = "STRING"
    EMPTY = ""


class ProxyInitState(Enum):
    """Enum with proxy handling results."""

    INIT_FAILED = 0
    INIT_SUCCESS = 1
    DE_INIT_FAILED = 4
    DE_INIT_SUCCESS = 8
    DE_INIT_SKIPPED = 16


class RpcServerType(StrEnum):
    """Enum for Homematic rpc server types."""

    XML_RPC = "xml_rpc"
    NONE = "none"


class RxMode(IntEnum):
    """Enum for Homematic rx modes."""

    UNDEFINED = 0
    ALWAYS = 1
    BURST = 2
    CONFIG = 4
    WAKEUP = 8
    LAZY_CONFIG = 16


class SourceOfDeviceCreation(StrEnum):
    """Enum with source of device creation."""

    CACHE = "CACHE"
    INIT = "INIT"
    MANUAL = "MANUAL"
    NEW = "NEW"
    REFRESH = "REFRESH"


class SysvarType(StrEnum):
    """Enum for Homematic sysvar types."""

    ALARM = "ALARM"
    FLOAT = "FLOAT"
    INTEGER = "INTEGER"
    LIST = "LIST"
    LOGIC = "LOGIC"
    NUMBER = "NUMBER"
    STRING = "STRING"


CLICK_EVENTS: Final[frozenset[Parameter]] = frozenset(
    {
        Parameter.PRESS,
        Parameter.PRESS_CONT,
        Parameter.PRESS_LOCK,
        Parameter.PRESS_LONG,
        Parameter.PRESS_LONG_RELEASE,
        Parameter.PRESS_LONG_START,
        Parameter.PRESS_SHORT,
        Parameter.PRESS_UNLOCK,
    }
)

DEVICE_ERROR_EVENTS: Final[tuple[Parameter, ...]] = (Parameter.ERROR, Parameter.SENSOR_ERROR)

DATA_POINT_EVENTS: Final[frozenset[EventType]] = frozenset(
    {
        EventType.IMPULSE,
        EventType.KEYPRESS,
    }
)


type DP_KEY_VALUE = tuple[DataPointKey, Any]
type SYSVAR_TYPE = bool | float | int | str | None

HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES: Final[frozenset[DeviceFirmwareState]] = frozenset(
    {
        DeviceFirmwareState.DO_UPDATE_PENDING,
        DeviceFirmwareState.PERFORMING_UPDATE,
    }
)

HMIP_FIRMWARE_UPDATE_READY_STATES: Final[frozenset[DeviceFirmwareState]] = frozenset(
    {
        DeviceFirmwareState.READY_FOR_UPDATE,
        DeviceFirmwareState.DO_UPDATE_PENDING,
        DeviceFirmwareState.PERFORMING_UPDATE,
    }
)

IMPULSE_EVENTS: Final[frozenset[Parameter]] = frozenset({Parameter.SEQUENCE_OK})

KEY_CHANNEL_OPERATION_MODE_VISIBILITY: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        Parameter.STATE: frozenset({"BINARY_BEHAVIOR"}),
        Parameter.PRESS_LONG: frozenset({"KEY_BEHAVIOR", "SWITCH_BEHAVIOR"}),
        Parameter.PRESS_LONG_RELEASE: frozenset({"KEY_BEHAVIOR", "SWITCH_BEHAVIOR"}),
        Parameter.PRESS_LONG_START: frozenset({"KEY_BEHAVIOR", "SWITCH_BEHAVIOR"}),
        Parameter.PRESS_SHORT: frozenset({"KEY_BEHAVIOR", "SWITCH_BEHAVIOR"}),
    }
)

BLOCKED_CATEGORIES: Final[tuple[DataPointCategory, ...]] = (DataPointCategory.ACTION,)

HUB_CATEGORIES: Final[tuple[DataPointCategory, ...]] = (
    DataPointCategory.HUB_BINARY_SENSOR,
    DataPointCategory.HUB_BUTTON,
    DataPointCategory.HUB_NUMBER,
    DataPointCategory.HUB_SELECT,
    DataPointCategory.HUB_SENSOR,
    DataPointCategory.HUB_SWITCH,
    DataPointCategory.HUB_TEXT,
)

CATEGORIES: Final[tuple[DataPointCategory, ...]] = (
    DataPointCategory.BINARY_SENSOR,
    DataPointCategory.BUTTON,
    DataPointCategory.CLIMATE,
    DataPointCategory.COVER,
    DataPointCategory.EVENT,
    DataPointCategory.LIGHT,
    DataPointCategory.LOCK,
    DataPointCategory.NUMBER,
    DataPointCategory.SELECT,
    DataPointCategory.SENSOR,
    DataPointCategory.SIREN,
    DataPointCategory.SWITCH,
    DataPointCategory.TEXT,
    DataPointCategory.UPDATE,
    DataPointCategory.VALVE,
)

PRIMARY_CLIENT_CANDIDATE_INTERFACES: Final[frozenset[Interface]] = frozenset(
    {
        Interface.HMIP_RF,
        Interface.BIDCOS_RF,
        Interface.BIDCOS_WIRED,
    }
)

RELEVANT_INIT_PARAMETERS: Final[frozenset[Parameter]] = frozenset(
    {
        Parameter.CONFIG_PENDING,
        Parameter.STICKY_UN_REACH,
        Parameter.UN_REACH,
    }
)

INTERFACES_SUPPORTING_FIRMWARE_UPDATES: Final[frozenset[Interface]] = frozenset(
    {
        Interface.BIDCOS_RF,
        Interface.BIDCOS_WIRED,
        Interface.HMIP_RF,
    }
)

INTERFACES_REQUIRING_XML_RPC: Final[frozenset[Interface]] = frozenset(
    {
        Interface.BIDCOS_RF,
        Interface.BIDCOS_WIRED,
        Interface.HMIP_RF,
        Interface.VIRTUAL_DEVICES,
    }
)


INTERFACES_SUPPORTING_RPC_CALLBACK: Final[frozenset[Interface]] = frozenset(INTERFACES_REQUIRING_XML_RPC)


INTERFACES_REQUIRING_JSON_RPC_CLIENT: Final[frozenset[Interface]] = frozenset(
    {
        Interface.CUXD,
        Interface.CCU_JACK,
    }
)

DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH: Final[frozenset[Interface]] = frozenset(
    INTERFACES_REQUIRING_JSON_RPC_CLIENT - INTERFACES_REQUIRING_XML_RPC
)

INTERFACE_RPC_SERVER_TYPE: Final[Mapping[Interface, RpcServerType]] = MappingProxyType(
    {
        Interface.BIDCOS_RF: RpcServerType.XML_RPC,
        Interface.BIDCOS_WIRED: RpcServerType.XML_RPC,
        Interface.HMIP_RF: RpcServerType.XML_RPC,
        Interface.VIRTUAL_DEVICES: RpcServerType.XML_RPC,
        Interface.CUXD: RpcServerType.NONE,
        Interface.CCU_JACK: RpcServerType.NONE,
    }
)

LINKABLE_INTERFACES: Final[frozenset[Interface]] = frozenset(
    {
        Interface.BIDCOS_RF,
        Interface.BIDCOS_WIRED,
        Interface.HMIP_RF,
    }
)


DEFAULT_USE_PERIODIC_SCAN_FOR_INTERFACES: Final = True

IGNORE_FOR_UN_IGNORE_PARAMETERS: Final[frozenset[Parameter]] = frozenset(
    {
        Parameter.CONFIG_PENDING,
        Parameter.STICKY_UN_REACH,
        Parameter.UN_REACH,
    }
)


# Ignore Parameter on initial load that end with
_IGNORE_ON_INITIAL_LOAD_PARAMETERS_END_RE: Final = re.compile(r".*(_ERROR)$")
# Ignore Parameter on initial load that start with
_IGNORE_ON_INITIAL_LOAD_PARAMETERS_START_RE: Final = re.compile(r"^(ERROR_|RSSI_)")
_IGNORE_ON_INITIAL_LOAD_PARAMETERS: Final[frozenset[Parameter]] = frozenset(
    {
        Parameter.DUTY_CYCLE,
        Parameter.DUTYCYCLE,
        Parameter.LOW_BAT,
        Parameter.LOWBAT,
        Parameter.OPERATING_VOLTAGE,
    }
)

_CLIMATE_SOURCE_ROLES: Final[tuple[str, ...]] = ("CLIMATE",)
_CLIMATE_TARGET_ROLES: Final[tuple[str, ...]] = ("CLIMATE", "SWITCH", "LEVEL")
_CLIMATE_TRANSMITTER_RE: Final = re.compile(r"(?:CLIMATE|HEATING).*(?:TRANSMITTER|TRANSCEIVER)")
_CLIMATE_RECEIVER_RE: Final = re.compile(r"(?:CLIMATE|HEATING).*(?:TRANSCEIVER|RECEIVER)")


def get_link_source_categories(
    *, source_roles: tuple[str, ...], channel_type_name: str
) -> tuple[DataPointCategory, ...]:
    """Return the channel sender roles."""
    result: set[DataPointCategory] = set()
    has_climate = False
    if _CLIMATE_TRANSMITTER_RE.search(channel_type_name):
        result.add(DataPointCategory.CLIMATE)
        has_climate = True

    if not has_climate and source_roles and any("CLIMATE" in role for role in source_roles):
        result.add(DataPointCategory.CLIMATE)

    return tuple(result)


def get_link_target_categories(
    *, target_roles: tuple[str, ...], channel_type_name: str
) -> tuple[DataPointCategory, ...]:
    """Return the channel receiver roles."""
    result: set[DataPointCategory] = set()
    has_climate = False
    if _CLIMATE_RECEIVER_RE.search(channel_type_name):
        result.add(DataPointCategory.CLIMATE)
        has_climate = True

    if (
        not has_climate
        and target_roles
        and any(cl_role in role for role in target_roles for cl_role in _CLIMATE_TARGET_ROLES)
    ):
        result.add(DataPointCategory.CLIMATE)

    return tuple(result)


RECEIVER_PARAMETERS: Final[frozenset[Parameter]] = frozenset(
    {
        Parameter.LEVEL,
        Parameter.STATE,
    }
)


def check_ignore_parameter_on_initial_load(parameter: str) -> bool:
    """Check if a parameter matches common wildcard patterns."""
    return (
        bool(_IGNORE_ON_INITIAL_LOAD_PARAMETERS_START_RE.match(parameter))
        or bool(_IGNORE_ON_INITIAL_LOAD_PARAMETERS_END_RE.match(parameter))
        or parameter in _IGNORE_ON_INITIAL_LOAD_PARAMETERS
    )


# Ignore Parameter on initial load that start with
_IGNORE_ON_INITIAL_LOAD_MODEL_START_RE: Final = re.compile(r"^(HmIP-SWSD)")
_IGNORE_ON_INITIAL_LOAD_MODEL: Final = ("HmIP-SWD",)
_IGNORE_ON_INITIAL_LOAD_MODEL_LOWER: Final = tuple(model.lower() for model in _IGNORE_ON_INITIAL_LOAD_MODEL)


def check_ignore_model_on_initial_load(model: str) -> bool:
    """Check if a model matches common wildcard patterns."""
    return (
        bool(_IGNORE_ON_INITIAL_LOAD_MODEL_START_RE.match(model))
        or model.lower() in _IGNORE_ON_INITIAL_LOAD_MODEL_LOWER
    )


# virtual remotes s
VIRTUAL_REMOTE_MODELS: Final[tuple[str, ...]] = (
    "HM-RCV-50",
    "HMW-RCV-50",
    "HmIP-RCV-50",
)

VIRTUAL_REMOTE_ADDRESSES: Final[tuple[str, ...]] = (
    "BidCoS-RF",
    "BidCoS-Wir",
    "HmIP-RCV-1",
)


@dataclass(frozen=True, kw_only=True, slots=True)
class HubData:
    """Dataclass for hub data points."""

    legacy_name: str
    enabled_default: bool = False
    description: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ProgramData(HubData):
    """Dataclass for programs."""

    pid: str
    is_active: bool
    is_internal: bool
    last_execute_time: str


@dataclass(frozen=True, kw_only=True, slots=True)
class SystemVariableData(HubData):
    """Dataclass for system variables."""

    vid: str
    value: SYSVAR_TYPE
    data_type: SysvarType | None = None
    extended_sysvar: bool = False
    max_value: float | int | None = None
    min_value: float | int | None = None
    unit: str | None = None
    values: tuple[str, ...] | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class SystemInformation:
    """System information of the backend."""

    available_interfaces: tuple[str, ...] = field(default_factory=tuple)
    auth_enabled: bool | None = None
    https_redirect_enabled: bool | None = None
    serial: str | None = None


class ParameterData(TypedDict, total=False):
    """Typed dict for parameter data."""

    DEFAULT: Any
    FLAGS: int
    ID: str
    MAX: Any
    MIN: Any
    OPERATIONS: int
    SPECIAL: Mapping[str, Any]
    TYPE: ParameterType
    UNIT: str
    VALUE_LIST: Iterable[Any]


class DeviceDescription(TypedDict, total=False):
    """Typed dict for device descriptions."""

    TYPE: Required[str]
    ADDRESS: Required[str]
    PARAMSETS: Required[list[str]]
    SUBTYPE: str | None
    CHILDREN: list[str]
    PARENT: str | None
    FIRMWARE: str | None
    AVAILABLE_FIRMWARE: str | None
    UPDATABLE: bool
    FIRMWARE_UPDATE_STATE: str | None
    FIRMWARE_UPDATABLE: bool | None
    INTERFACE: str | None
    RX_MODE: int | None
    LINK_SOURCE_ROLES: str | None
    LINK_TARGET_ROLES: str | None
    # RF_ADDRESS: int | None
    # PARENT_TYPE: str | None
    # INDEX: int | None
    # AES_ACTIVE: int | None
    # VERSION: Required[int]
    # FLAGS: Required[int]
    # DIRECTION: int | None
    # GROUP: str | None
    # TEAM: str | None
    # TEAM_TAG: str | None
    # TEAM_CHANNELS: list
    # ROAMING: int | None


# Define public API for this module
__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (
            name.isupper()  # constants like VERSION, patterns, defaults
            or inspect.isclass(obj)  # Enums, dataclasses, TypedDicts, NamedTuple classes
            or inspect.isfunction(obj)  # module functions
        )
        and (
            getattr(obj, "__module__", __name__) == __name__
            if not isinstance(obj, int | float | str | bytes | tuple | frozenset | dict)
            else True
        )
    )
)


class AstroType(IntEnum):
    """Enum for astro event types."""

    SUNRISE = 0
    SUNSET = 1


class ScheduleActorChannel(IntEnum):
    """Enum for target actor channels (bitwise)."""

    CHANNEL_1_1 = 1
    CHANNEL_1_2 = 2
    CHANNEL_1_3 = 4
    CHANNEL_2_1 = 8
    CHANNEL_2_2 = 16
    CHANNEL_2_3 = 32
    CHANNEL_3_1 = 64
    CHANNEL_3_2 = 128
    CHANNEL_3_3 = 256
    CHANNEL_4_1 = 512
    CHANNEL_4_2 = 1024
    CHANNEL_4_3 = 2048
    CHANNEL_5_1 = 4096
    CHANNEL_5_2 = 8192
    CHANNEL_5_3 = 16384
    CHANNEL_6_1 = 32768
    CHANNEL_6_2 = 65536
    CHANNEL_6_3 = 131072
    CHANNEL_7_1 = 262144
    CHANNEL_7_2 = 524288
    CHANNEL_7_3 = 1048576
    CHANNEL_8_1 = 2097152
    CHANNEL_8_2 = 4194304
    CHANNEL_8_3 = 8388608


class ScheduleCondition(IntEnum):
    """Enum for schedule trigger conditions."""

    FIXED_TIME = 0
    ASTRO = 1


class ScheduleField(StrEnum):
    """Enum for switch schedule field names."""

    ASTRO_OFFSET = "ASTRO_OFFSET"
    ASTRO_TYPE = "ASTRO_TYPE"
    CONDITION = "CONDITION"
    DURATION_BASE = "DURATION_BASE"
    DURATION_FACTOR = "DURATION_FACTOR"
    FIXED_HOUR = "FIXED_HOUR"
    FIXED_MINUTE = "FIXED_MINUTE"
    LEVEL = "LEVEL"
    LEVEL_2 = "LEVEL_2"
    RAMP_TIME_BASE = "RAMP_TIME_BASE"
    RAMP_TIME_FACTOR = "RAMP_TIME_FACTOR"
    TARGET_CHANNELS = "TARGET_CHANNELS"
    WEEKDAY = "WEEKDAY"


class ScheduleSlotType(StrEnum):
    """Enum for climate item type."""

    ENDTIME = "ENDTIME"
    STARTTIME = "STARTTIME"
    TEMPERATURE = "TEMPERATURE"


class ScheduleProfile(StrEnum):
    """Enum for climate profiles."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"


class TimeBase(IntEnum):
    """Enum for duration base units."""

    MS_100 = 0  # 100 milliseconds
    SEC_1 = 1  # 1 second
    SEC_5 = 2  # 5 seconds
    SEC_10 = 3  # 10 seconds
    MIN_1 = 4  # 1 minute
    MIN_5 = 5  # 5 minutes
    MIN_10 = 6  # 10 minutes
    HOUR_1 = 7  # 1 hour


class WeekdayInt(IntEnum):
    """Enum for weekdays (bitwise)."""

    SUNDAY = 1
    MONDAY = 2
    TUESDAY = 4
    WEDNESDAY = 8
    THURSDAY = 16
    FRIDAY = 32
    SATURDAY = 64


class WeekdayStr(StrEnum):
    """Enum for climate week days."""

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


CLIMATE_MAX_SCHEDULER_TIME: Final = "24:00"
CLIMATE_MIN_SCHEDULER_TIME: Final = "00:00"
CLIMATE_WEEKDAY_DICT = dict[int, dict[ScheduleSlotType, str | float]]
CLIMATE_PROFILE_DICT = dict[WeekdayStr, CLIMATE_WEEKDAY_DICT]
CLIMATE_RELEVANT_SLOT_TYPES: Final = (ScheduleSlotType.ENDTIME, ScheduleSlotType.TEMPERATURE)
CLIMATE_SCHEDULE_DICT = dict[ScheduleProfile, CLIMATE_PROFILE_DICT]
CLIMATE_SCHEDULE_SLOT_IN_RANGE: Final = range(1, 14)
CLIMATE_SCHEDULE_SLOT_RANGE: Final = range(1, 13)
CLIMATE_SCHEDULE_TIME_RANGE: Final = range(1441)
CLIMATE_SIMPLE_WEEKDAY_LIST = list[dict[ScheduleSlotType, str | float]]
CLIMATE_SIMPLE_PROFILE_DICT = dict[WeekdayStr, CLIMATE_SIMPLE_WEEKDAY_LIST]
DEFAULT_CLIMATE_FILL_TEMPERATURE: Final = 18.0
DEFAULT_SCHEDULE_GROUP = dict[ScheduleField, Any]
DEFAULT_SCHEDULE_DICT = dict[int, DEFAULT_SCHEDULE_GROUP]
RAW_SCHEDULE_DICT = dict[str, float | int]
SCHEDULE_PATTERN: Final = re.compile(r"^\d+_WP_")
