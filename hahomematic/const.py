"""Constants used by hahomematic."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum, StrEnum
import re
from typing import Any, Final, NamedTuple, Required, TypedDict

VERSION: Final = "2025.7.1"

# default
DEFAULT_CUSTOM_ID: Final = "custom_id"
DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK: Final = False
DEFAULT_ENABLE_PROGRAM_SCAN: Final = True
DEFAULT_ENABLE_SYSVAR_SCAN: Final = True
DEFAULT_HM_MASTER_POLL_AFTER_SEND_INTERVALS: Final = (5,)
DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS: Final[tuple[str, ...]] = ()
DEFAULT_INCLUDE_INTERNAL_PROGRAMS: Final = False
DEFAULT_INCLUDE_INTERNAL_SYSVARS: Final = True
DEFAULT_MAX_READ_WORKERS: Final = 1
DEFAULT_MAX_WORKERS: Final = 1
DEFAULT_MULTIPLIER: Final = 1.0
DEFAULT_PERIODIC_REFRESH_INTERVAL: Final = 15
DEFAULT_PROGRAM_MARKERS: Final[tuple[DescriptionMarker | str, ...]] = ()
DEFAULT_SYSVAR_MARKERS: Final[tuple[DescriptionMarker | str, ...]] = ()
DEFAULT_SYS_SCAN_INTERVAL: Final = 30
DEFAULT_TLS: Final = False
DEFAULT_UN_IGNORES: Final[tuple[str, ...]] = ()
DEFAULT_VERIFY_TLS: Final = False

# Default encoding for json service calls, persistent cache
UTF_8: Final = "utf-8"
# Default encoding for xmlrpc service calls and script files
ISO_8859_1: Final = "iso-8859-1"

# Password can be empty.
# Allowed characters: A-Z, a-z, 0-9, .!$():;#-
# The CCU WebUI also supports ÄäÖöÜüß, but these characters are not supported by the XmlRPC servers
CCU_PASSWORD_PATTERN: Final = re.compile(r"[A-Za-z0-9.!$():;#-]{0,}")
# Pattern is bigger than needed
CHANNEL_ADDRESS_PATTERN: Final = re.compile(r"^[0-9a-zA-Z-]{5,20}:[0-9]{1,3}$")
DEVICE_ADDRESS_PATTERN: Final = re.compile(r"^[0-9a-zA-Z-]{5,20}$")
ALLOWED_HOSTNAME_PATTERN: Final = re.compile(r"(?!-)[a-z0-9-]{1,63}(?<!-)$", re.IGNORECASE)
HTMLTAG_PATTERN: Final = re.compile(r"<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});")
SCHEDULER_PROFILE_PATTERN = re.compile(
    r"^P[1-6]_(ENDTIME|TEMPERATURE)_(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)_([1-9]|1[0-3])$"
)
SCHEDULER_TIME_PATTERN = re.compile(r"^(([0-1]{0,1}[0-9])|(2[0-4])):[0-5][0-9]")

ALWAYS_ENABLE_SYSVARS_BY_ID: Final = "40", "41"
RENAME_SYSVAR_BY_NAME: Final = {
    "${sysVarAlarmMessages}": "ALARM_MESSAGES",
    "${sysVarPresence}": "PRESENCE",
    "${sysVarServiceMessages}": "SERVICE_MESSAGES",
}

SYSVAR_ENABLE_DEFAULT: Final = "40", "41"

ADDRESS_SEPARATOR: Final = ":"
BLOCK_LOG_TIMEOUT = 60
CACHE_PATH: Final = "cache"
CONF_PASSWORD: Final = "password"
CONF_USERNAME: Final = "username"
CONNECTION_CHECKER_INTERVAL: Final = 15  # check if connection is available via rpc ping
DATETIME_FORMAT: Final = "%d.%m.%Y %H:%M:%S"
DATETIME_FORMAT_MILLIS: Final = "%d.%m.%Y %H:%M:%S.%f'"
DEVICE_DESCRIPTIONS_DIR: Final = "export_device_descriptions"
DEVICE_FIRMWARE_CHECK_INTERVAL: Final = 21600  # 6h
DEVICE_FIRMWARE_DELIVERING_CHECK_INTERVAL: Final = 3600  # 1h
DEVICE_FIRMWARE_UPDATING_CHECK_INTERVAL: Final = 300  # 5m
DUMMY_SERIAL = "SN0815"
FILE_DEVICES: Final = "homematic_devices.json"
FILE_PARAMSETS: Final = "homematic_paramsets.json"
HUB_PATH: Final = "hub"
IDENTIFIER_SEPARATOR: Final = "@"
INIT_DATETIME: Final = datetime.strptime("01.01.1970 00:00:00", DATETIME_FORMAT)
IP_ANY_V4: Final = "0.0.0.0"
JSON_SESSION_AGE: Final = 90
KWARGS_ARG_DATA_POINT = "data_point"
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
RECONNECT_WAIT: Final = 120  # wait with reconnect after a first ping was successful
REGA_SCRIPT_PATH: Final = "../rega_scripts"
REPORT_VALUE_USAGE_DATA: Final = "reportValueUsageData"
REPORT_VALUE_USAGE_VALUE_ID: Final = "PRESS_SHORT"
SYSVAR_ADDRESS: Final = "sysvar"
TIMEOUT: Final = 60  # default timeout for a connection
UN_IGNORE_WILDCARD: Final = "all"
WAIT_FOR_CALLBACK: Final[int | None] = None


CALLBACK_WARN_INTERVAL = CONNECTION_CHECKER_INTERVAL * 40

# Path
PROGRAM_SET_PATH_ROOT: Final = "program/set"
PROGRAM_STATE_PATH_ROOT: Final = "program/status"
SET_PATH_ROOT: Final = "device/set"
STATE_PATH_ROOT: Final = "device/status"
SYSVAR_SET_PATH_ROOT: Final = "sysvar/set"
SYSVAR_STATE_PATH_ROOT: Final = "sysvar/status"
VIRTDEV_SET_PATH_ROOT: Final = "virtdev/set"
VIRTDEV_STATE_PATH_ROOT: Final = "virtdev/status"

CALLBACK_TYPE = Callable[[], None] | None


class Backend(StrEnum):
    """Enum with supported hahomematic backends."""

    CCU = "CCU"
    HOMEGEAR = "Homegear"
    PYDEVCCU = "PyDevCCU"


class BackendSystemEvent(StrEnum):
    """Enum with hahomematic system events."""

    DELETE_DEVICES = "deleteDevices"
    DEVICES_CREATED = "devicesCreated"
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
    UPDATE = "update"
    VALVE = "valve"


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
    """Enum with homematic device firmware states."""

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


class EventKey(StrEnum):
    """Enum with hahomematic event keys."""

    ADDRESS = "address"
    AVAILABLE = "available"
    CENTRAL_NAME = "central_name"
    CHANNEL_NO = "channel_no"
    DATA = "data"
    INTERFACE_ID = "interface_id"
    MODEL = "model"
    PARAMETER = "parameter"
    PONG_MISMATCH_COUNT = "pong_mismatch_count"
    SECONDS_SINCE_LAST_EVENT = "seconds_since_last_event"
    TYPE = "type"
    VALUE = "value"


class EventType(StrEnum):
    """Enum with hahomematic event types."""

    DEVICE_AVAILABILITY = "homematic.device_availability"
    DEVICE_ERROR = "homematic.device_error"
    IMPULSE = "homematic.impulse"
    INTERFACE = "homematic.interface"
    KEYPRESS = "homematic.keypress"


class Flag(IntEnum):
    """Enum with homematic flags."""

    VISIBLE = 1
    INTERNAL = 2
    TRANSFORM = 4  # not used
    SERVICE = 8
    STICKY = 10  # This might be wrong. Documentation says 0x10 # not used


class ForcedDeviceAvailability(StrEnum):
    """Enum with hahomematic event types."""

    FORCE_FALSE = "forced_not_available"
    FORCE_TRUE = "forced_available"
    NOT_SET = "not_set"


class Manufacturer(StrEnum):
    """Enum with hahomematic system events."""

    EQ3 = "eQ-3"
    HB = "Homebrew"
    MOEHLENHOFF = "Möhlenhoff"


class Operations(IntEnum):
    """Enum with homematic operations."""

    NONE = 0  # not used
    READ = 1
    WRITE = 2
    EVENT = 4


class CalulatedParameter(StrEnum):
    """Enum with calculated homematic parameters."""

    APPARENT_TEMPERATURE = "APPARENT_TEMPERATURE"
    DEW_POINT = "DEW_POINT"
    FROST_POINT = "FROST_POINT"
    OPERATING_VOLTAGE_LEVEL = "OPERATING_VOLTAGE_LEVEL"
    VAPOR_CONCENTRATION = "VAPOR_CONCENTRATION"


class Parameter(StrEnum):
    """Enum with homematic parameters."""

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
    LINK = "LINK"
    MASTER = "MASTER"
    SERVICE = "SERVICE"
    VALUES = "VALUES"


class ProductGroup(StrEnum):
    """Enum with homematic product groups."""

    HM = "BidCos-RF"
    HMIP = "HmIP-RF"
    HMIPW = "HmIP-Wired"
    HMW = "BidCos-Wired"
    UNKNOWN = "unknown"
    VIRTUAL = "VirtualDevices"


class RegaScript(StrEnum):
    """Enum with homematic rega scripts."""

    FETCH_ALL_DEVICE_DATA: Final = "fetch_all_device_data.fn"
    GET_PROGRAM_DESCRIPTIONS: Final = "get_program_descriptions.fn"
    GET_SERIAL: Final = "get_serial.fn"
    GET_SYSTEM_VARIABLE_DESCRIPTIONS: Final = "get_system_variable_descriptions.fn"
    SET_PROGRAM_STATE: Final = "set_program_state.fn"
    SET_SYSTEM_VARIABLE: Final = "set_system_variable.fn"


class Interface(StrEnum):
    """Enum with homematic interfaces."""

    BIDCOS_RF = "BidCos-RF"
    BIDCOS_WIRED = "BidCos-Wired"
    CCU_JACK = "CCU-Jack"
    CUXD = "CUxD"
    HMIP_RF = "HmIP-RF"
    VIRTUAL_DEVICES = "VirtualDevices"


class InterfaceEventType(StrEnum):
    """Enum with hahomematic interface event types."""

    CALLBACK = "callback"
    FETCH_DATA = "fetch_data"
    PENDING_PONG = "pending_pong"
    PROXY = "proxy"
    UNKNOWN_PONG = "unknown_pong"


class ProxyInitState(Enum):
    """Enum with proxy handling results."""

    INIT_FAILED = 0
    INIT_SUCCESS = 1
    DE_INIT_FAILED = 4
    DE_INIT_SUCCESS = 8
    DE_INIT_SKIPPED = 16


class RxMode(IntEnum):
    """Enum for homematic rx modes."""

    UNDEFINED = 0
    ALWAYS = 1
    BURST = 2
    CONFIG = 4
    WAKEUP = 8
    LAZY_CONFIG = 16


class CommandRxMode(StrEnum):
    """Enum for homematic rx modes for commands."""

    BURST = "BURST"
    WAKEUP = "WAKEUP"


class SysvarType(StrEnum):
    """Enum for homematic sysvar types."""

    ALARM = "ALARM"
    FLOAT = "FLOAT"
    INTEGER = "INTEGER"
    LIST = "LIST"
    LOGIC = "LOGIC"
    NUMBER = "NUMBER"
    STRING = "STRING"


class ParameterType(StrEnum):
    """Enum for homematic parameter types."""

    ACTION = "ACTION"  # Usually buttons, send Boolean to trigger
    BOOL = "BOOL"
    ENUM = "ENUM"
    FLOAT = "FLOAT"
    INTEGER = "INTEGER"
    STRING = "STRING"
    EMPTY = ""


CLICK_EVENTS: Final[tuple[Parameter, ...]] = (
    Parameter.PRESS,
    Parameter.PRESS_CONT,
    Parameter.PRESS_LOCK,
    Parameter.PRESS_LONG,
    Parameter.PRESS_LONG_RELEASE,
    Parameter.PRESS_LONG_START,
    Parameter.PRESS_SHORT,
    Parameter.PRESS_UNLOCK,
)

DEVICE_ERROR_EVENTS: Final[tuple[Parameter, ...]] = (Parameter.ERROR, Parameter.SENSOR_ERROR)

DATA_POINT_EVENTS: Final[tuple[EventType, ...]] = (
    EventType.IMPULSE,
    EventType.KEYPRESS,
)


class DataPointKey(NamedTuple):
    """Key for data points."""

    interface_id: str
    channel_address: str
    paramset_key: ParamsetKey
    parameter: str


type DP_KEY_VALUE = tuple[DataPointKey, Any]
type SYSVAR_TYPE = bool | float | int | str | None

HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES: Final[tuple[DeviceFirmwareState, ...]] = (
    DeviceFirmwareState.DO_UPDATE_PENDING,
    DeviceFirmwareState.PERFORMING_UPDATE,
)

HMIP_FIRMWARE_UPDATE_READY_STATES: Final[tuple[DeviceFirmwareState, ...]] = (
    DeviceFirmwareState.READY_FOR_UPDATE,
    DeviceFirmwareState.DO_UPDATE_PENDING,
    DeviceFirmwareState.PERFORMING_UPDATE,
)

IMPULSE_EVENTS: Final[tuple[Parameter, ...]] = (Parameter.SEQUENCE_OK,)

KEY_CHANNEL_OPERATION_MODE_VISIBILITY: Final[Mapping[str, tuple[str, ...]]] = {
    Parameter.STATE: ("BINARY_BEHAVIOR",),
    Parameter.PRESS_LONG: ("KEY_BEHAVIOR", "SWITCH_BEHAVIOR"),
    Parameter.PRESS_LONG_RELEASE: ("KEY_BEHAVIOR", "SWITCH_BEHAVIOR"),
    Parameter.PRESS_LONG_START: ("KEY_BEHAVIOR", "SWITCH_BEHAVIOR"),
    Parameter.PRESS_SHORT: ("KEY_BEHAVIOR", "SWITCH_BEHAVIOR"),
}

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

PRIMARY_CLIENT_CANDIDATE_INTERFACES: Final = (
    Interface.HMIP_RF,
    Interface.BIDCOS_RF,
    Interface.BIDCOS_WIRED,
)

RELEVANT_INIT_PARAMETERS: Final[tuple[Parameter, ...]] = (
    Parameter.CONFIG_PENDING,
    Parameter.STICKY_UN_REACH,
    Parameter.UN_REACH,
)

INTERFACES_SUPPORTING_FIRMWARE_UPDATES: Final[tuple[Interface, ...]] = (
    Interface.BIDCOS_RF,
    Interface.BIDCOS_WIRED,
    Interface.HMIP_RF,
)

INTERFACES_SUPPORTING_XML_RPC: Final[tuple[Interface, ...]] = (
    Interface.BIDCOS_RF,
    Interface.BIDCOS_WIRED,
    Interface.HMIP_RF,
    Interface.VIRTUAL_DEVICES,
)

INTERFACES_REQUIRING_PERIODIC_REFRESH: Final[tuple[Interface, ...]] = (
    Interface.CCU_JACK,
    Interface.CUXD,
)

DEFAULT_USE_PERIODIC_SCAN_FOR_INTERFACES: Final = True

IGNORE_FOR_UN_IGNORE_PARAMETERS: Final[tuple[Parameter, ...]] = (
    Parameter.CONFIG_PENDING,
    Parameter.STICKY_UN_REACH,
    Parameter.UN_REACH,
)


# Ignore Parameter on initial load that end with
_IGNORE_ON_INITIAL_LOAD_PARAMETERS_END_RE: Final = re.compile(r".*(_ERROR)$")
# Ignore Parameter on initial load that start with
_IGNORE_ON_INITIAL_LOAD_PARAMETERS_START_RE: Final = re.compile(r"^(ERROR_|RSSI_)")
_IGNORE_ON_INITIAL_LOAD_PARAMETERS: Final = (
    Parameter.DUTY_CYCLE,
    Parameter.DUTYCYCLE,
    Parameter.LOW_BAT,
    Parameter.LOWBAT,
    Parameter.OPERATING_VOLTAGE,
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
    SUBTYPE: str | None
    ADDRESS: Required[str]
    # RF_ADDRESS: int | None
    CHILDREN: list[str]
    PARENT: str | None
    # PARENT_TYPE: str | None
    # INDEX: int | None
    # AES_ACTIVE: int | None
    PARAMSETS: list[str]
    FIRMWARE: str
    AVAILABLE_FIRMWARE: str | None
    UPDATABLE: bool
    FIRMWARE_UPDATE_STATE: str | None
    FIRMWARE_UPDATABLE: bool | None
    # VERSION: Required[int]
    # FLAGS: Required[int]
    # LINK_SOURCE_ROLES: str | None
    # LINK_TARGET_ROLES: str | None
    # DIRECTION: int | None
    # GROUP: str | None
    # TEAM: str | None
    # TEAM_TAG: str | None
    # TEAM_CHANNELS: list
    INTERFACE: str | None
    # ROAMING: int | None
    RX_MODE: int
