# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Static visibility rules for Homematic parameters.

This module contains all static mappings and constants that determine parameter
visibility, including:

- MASTER paramset relevance by channel and device
- Parameters to ignore/un-ignore per device model
- Hidden parameters that are created but not displayed by default
- Event suppression rules for specific devices

These rules are used by ParameterVisibilityCache to make visibility decisions.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Final, TypeAlias

from aiohomematic.const import CLICK_EVENTS, Parameter

# =============================================================================
# Type Aliases
# =============================================================================

ModelName: TypeAlias = str
ChannelNo: TypeAlias = int | None
ParameterName: TypeAlias = str

# =============================================================================
# MASTER Paramset Relevance Rules
# =============================================================================
# Define which additional parameters from MASTER paramset should be created as
# data points. By default these are also in HIDDEN_PARAMETERS, which prevents
# them from being displayed. Usually these entities are used within custom data
# points, not for general display.

RELEVANT_MASTER_PARAMSETS_BY_CHANNEL: Final[Mapping[ChannelNo, frozenset[Parameter]]] = {
    None: frozenset({Parameter.GLOBAL_BUTTON_LOCK, Parameter.LOW_BAT_LIMIT}),
    0: frozenset({Parameter.GLOBAL_BUTTON_LOCK, Parameter.LOW_BAT_LIMIT}),
}

CLIMATE_MASTER_PARAMETERS: Final[frozenset[Parameter]] = frozenset(
    {
        Parameter.HEATING_VALVE_TYPE,
        Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
        Parameter.OPTIMUM_START_STOP,
        Parameter.TEMPERATURE_MAXIMUM,
        Parameter.TEMPERATURE_MINIMUM,
        Parameter.TEMPERATURE_OFFSET,
        Parameter.WEEK_PROGRAM_POINTER,
    }
)

# {model: (channel_numbers, parameters)}
RELEVANT_MASTER_PARAMSETS_BY_DEVICE: Final[Mapping[ModelName, tuple[frozenset[ChannelNo], frozenset[Parameter]]]] = {
    "ALPHA-IP-RBG": (frozenset({1}), CLIMATE_MASTER_PARAMETERS),
    "ELV-SH-TACO": (frozenset({2}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HM-CC-RT-DN": (frozenset({None}), CLIMATE_MASTER_PARAMETERS),
    "HM-CC-VG-1": (frozenset({None}), CLIMATE_MASTER_PARAMETERS),
    "HM-TC-IT-WM-W-EU": (frozenset({None}), CLIMATE_MASTER_PARAMETERS),
    "HmIP-BWTH": (frozenset({1, 8}), CLIMATE_MASTER_PARAMETERS),
    "HmIP-DRBLI4": (
        frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 17, 21}),
        frozenset({Parameter.CHANNEL_OPERATION_MODE}),
    ),
    "HmIP-DRDI3": (frozenset({1, 2, 3}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-DRSI1": (frozenset({1}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-DRSI4": (frozenset({1, 2, 3, 4}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-DSD-PCB": (frozenset({1}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-FCI1": (frozenset({1}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-FCI6": (frozenset(range(1, 7)), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-FSI16": (frozenset({1}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-HEATING": (frozenset({1}), CLIMATE_MASTER_PARAMETERS),
    "HmIP-MIO16-PCB": (frozenset({13, 14, 15, 16}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-MOD-RC8": (frozenset(range(1, 9)), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIP-RGBW": (frozenset({0}), frozenset({Parameter.DEVICE_OPERATION_MODE})),
    "HmIP-STH": (frozenset({1}), CLIMATE_MASTER_PARAMETERS),
    "HmIP-WGT": (frozenset({8, 14}), CLIMATE_MASTER_PARAMETERS),
    "HmIP-WTH": (frozenset({1}), CLIMATE_MASTER_PARAMETERS),
    "HmIP-eTRV": (frozenset({1}), CLIMATE_MASTER_PARAMETERS),
    "HmIPW-DRBL4": (frozenset({1, 5, 9, 13}), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIPW-DRI16": (frozenset(range(1, 17)), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIPW-DRI32": (frozenset(range(1, 33)), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIPW-FIO6": (frozenset(range(1, 7)), frozenset({Parameter.CHANNEL_OPERATION_MODE})),
    "HmIPW-STH": (frozenset({1}), CLIMATE_MASTER_PARAMETERS),
}

# =============================================================================
# Event Suppression Rules
# =============================================================================
# Ignore events for some devices to reduce noise in event streams.

IGNORE_DEVICES_FOR_DATA_POINT_EVENTS: Final[Mapping[ModelName, frozenset[Parameter]]] = {
    "HmIP-PS": CLICK_EVENTS,
}

IGNORE_DEVICES_FOR_DATA_POINT_EVENTS_LOWER: Final[Mapping[ModelName, frozenset[Parameter]]] = {
    model.lower(): frozenset(events) for model, events in IGNORE_DEVICES_FOR_DATA_POINT_EVENTS.items()
}

# =============================================================================
# Hidden Parameters
# =============================================================================
# Data points that will be created but should be hidden from UI by default.

HIDDEN_PARAMETERS: Final[frozenset[Parameter]] = frozenset(
    {
        Parameter.ACTIVITY_STATE,
        Parameter.CHANNEL_OPERATION_MODE,
        Parameter.CONFIG_PENDING,
        Parameter.DIRECTION,
        Parameter.ERROR,
        Parameter.HEATING_VALVE_TYPE,
        Parameter.LOW_BAT_LIMIT,
        Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
        Parameter.OPTIMUM_START_STOP,
        Parameter.SECTION,
        Parameter.STICKY_UN_REACH,
        Parameter.TEMPERATURE_MAXIMUM,
        Parameter.TEMPERATURE_MINIMUM,
        Parameter.TEMPERATURE_OFFSET,
        Parameter.UN_REACH,
        Parameter.UPDATE_PENDING,
        Parameter.WORKING,
    }
)

# =============================================================================
# Ignored Parameters
# =============================================================================
# Parameters within the VALUES paramset for which we don't create data points.

IGNORED_PARAMETERS: Final[frozenset[ParameterName]] = frozenset(
    {
        "ACCESS_AUTHORIZATION",
        "ADAPTION_DRIVE",
        "AES_KEY",
        "ALARM_COUNT",
        "ALL_LEDS",
        "ARROW_DOWN",
        "ARROW_UP",
        "BACKLIGHT",
        "BEEP",
        "BELL",
        "BLIND",
        "BOOST_STATE",
        "BOOST_TIME",
        "BOOT",
        "BULB",
        "CLEAR_ERROR",
        "CLEAR_WINDOW_OPEN_SYMBOL",
        "CLOCK",
        "CMD_RETL",  # CUxD
        "CMD_RETS",  # CUxD
        "CONTROL_DIFFERENTIAL_TEMPERATURE",
        "DATE_TIME_UNKNOWN",
        "DECISION_VALUE",
        "DEVICE_IN_BOOTLOADER",
        "DOOR",
        "EXTERNAL_CLOCK",
        "FROST_PROTECTION",
        "HUMIDITY_LIMITER",
        "IDENTIFICATION_MODE_KEY_VISUAL",
        "IDENTIFICATION_MODE_LCD_BACKLIGHT",
        "INCLUSION_UNSUPPORTED_DEVICE",
        "INHIBIT",
        "INSTALL_MODE",
        "LEVEL_REAL",
        "OLD_LEVEL",
        "OVERFLOW",
        "OVERRUN",
        "PARTY_SET_POINT_TEMPERATURE",
        "PARTY_TEMPERATURE",
        "PARTY_TIME_END",
        "PARTY_TIME_START",
        "PHONE",
        "PROCESS",
        "QUICK_VETO_TIME",
        "RAMP_STOP",
        "RELOCK_DELAY",
        "SCENE",
        "SELF_CALIBRATION",
        "SERVICE_COUNT",
        "SET_SYMBOL_FOR_HEATING_PHASE",
        "SHADING_SPEED",
        "SHEV_POS",
        "SPEED",
        "STATE_UNCERTAIN",
        "SUBMIT",
        "SWITCH_POINT_OCCURED",
        "TEMPERATURE_LIMITER",
        "TEMPERATURE_OUT_OF_RANGE",
        "TEXT",
        "USER_COLOR",
        "USER_PROGRAM",
        "VALVE_ADAPTION",
        "WINDOW",
        "WIN_RELEASE",
        "WIN_RELEASE_ACT",
    }
)

# Precompiled regex patterns for wildcard parameter checks
IGNORED_PARAMETERS_END_PATTERN: Final = re.compile(r".*(_OVERFLOW|_OVERRUN|_REPORTING|_RESULT|_STATUS|_SUBMIT)$")
IGNORED_PARAMETERS_START_PATTERN: Final = re.compile(
    r"^(ADJUSTING_|ERR_TTM_|HANDLE_|IDENTIFY_|PARTY_START_|PARTY_STOP_|STATUS_FLAG_|WEEK_PROGRAM_)"
)


def parameter_is_wildcard_ignored(*, parameter: ParameterName) -> bool:
    """Check if a parameter matches common wildcard patterns."""
    return bool(IGNORED_PARAMETERS_END_PATTERN.match(parameter) or IGNORED_PARAMETERS_START_PATTERN.match(parameter))


# =============================================================================
# Un-Ignore Rules by Device
# =============================================================================
# Parameters that are normally ignored but should be created for specific devices.

UN_IGNORE_PARAMETERS_BY_DEVICE: Final[Mapping[ModelName, frozenset[Parameter]]] = {
    "HmIP-DLD": frozenset({Parameter.ERROR_JAMMED}),
    "HmIP-SWSD": frozenset({Parameter.DIRT_LEVEL, Parameter.SMOKE_LEVEL, Parameter.SMOKE_DETECTOR_ALARM_STATUS}),
    # Text display parameters for HmIP-WRCD
    "HmIP-WRCD": frozenset(
        {Parameter.DISPLAY_DATA_COMMIT, Parameter.DISPLAY_DATA_ID, Parameter.DISPLAY_DATA_STRING, Parameter.INTERVAL}
    ),
    "HM-OU-LED16": frozenset({Parameter.LED_STATUS}),
    "HM-Sec-Win": frozenset({Parameter.DIRECTION, Parameter.WORKING, Parameter.ERROR, Parameter.STATUS}),
    "HM-Sec-Key": frozenset({Parameter.DIRECTION, Parameter.ERROR}),
    "HmIP-PCBS-BAT": frozenset({Parameter.OPERATING_VOLTAGE, Parameter.LOW_BAT}),  # Override HmIP-PCBS
    # RF thermostats need WEEK_PROGRAM_POINTER for climate presets
    "BC-RT-TRX-CyG": frozenset({Parameter.WEEK_PROGRAM_POINTER}),
    "BC-RT-TRX-CyN": frozenset({Parameter.WEEK_PROGRAM_POINTER}),
    "BC-TC-C-WM": frozenset({Parameter.WEEK_PROGRAM_POINTER}),
    "HM-CC-RT-DN": frozenset({Parameter.WEEK_PROGRAM_POINTER}),
    "HM-CC-VG-1": frozenset({Parameter.WEEK_PROGRAM_POINTER}),
    "HM-TC-IT-WM-W-EU": frozenset({Parameter.WEEK_PROGRAM_POINTER}),
}

UN_IGNORE_PARAMETERS_BY_MODEL_LOWER: Final[dict[ModelName, frozenset[Parameter]]] = {
    model.lower(): frozenset(parameters) for model, parameters in UN_IGNORE_PARAMETERS_BY_DEVICE.items()
}

# =============================================================================
# Ignore Rules by Device
# =============================================================================
# Parameters to ignore for specific device models.

IGNORE_PARAMETERS_BY_DEVICE: Final[Mapping[Parameter, frozenset[ModelName]]] = {
    Parameter.CURRENT_ILLUMINATION: frozenset({"HmIP-SMI", "HmIP-SMO", "HmIP-SPI"}),
    Parameter.LOWBAT: frozenset(
        {
            "HM-LC-Sw1-DR",
            "HM-LC-Sw1-FM",
            "HM-LC-Sw1-PCB",
            "HM-LC-Sw1-Pl",
            "HM-LC-Sw1-Pl-DN-R1",
            "HM-LC-Sw1PBU-FM",
            "HM-LC-Sw2-FM",
            "HM-LC-Sw4-DR",
            "HM-SwI-3-FM",
        }
    ),
    Parameter.LOW_BAT: frozenset({"HmIP-BWTH", "HmIP-PCBS"}),
    Parameter.OPERATING_VOLTAGE: frozenset(
        {
            "ELV-SH-BS2",
            "HmIP-BDT",
            "HmIP-BROLL",
            "HmIP-BS2",
            "HmIP-BSL",
            "HmIP-BSM",
            "HmIP-BWTH",
            "HmIP-DR",
            "HmIP-FDT",
            "HmIP-FROLL",
            "HmIP-FSM",
            "HmIP-MOD-OC8",
            "HmIP-PCBS",
            "HmIP-PDT",
            "HmIP-PMFS",
            "HmIP-PS",
            "HmIP-SFD",
            "HmIP-SMO230",
            "HmIP-WGT",
        }
    ),
    Parameter.VALVE_STATE: frozenset({"HmIP-FALMOT-C8", "HmIPW-FALMOT-C12", "HmIP-FALMOT-C12"}),
}

IGNORE_PARAMETERS_BY_DEVICE_LOWER: Final[dict[ParameterName, frozenset[ModelName]]] = {
    parameter: frozenset(model.lower() for model in s) for parameter, s in IGNORE_PARAMETERS_BY_DEVICE.items()
}

# =============================================================================
# Channel-Specific Parameter Rules
# =============================================================================
# Some devices have parameters on multiple channels, but we want to use it only
# from a certain channel.

ACCEPT_PARAMETER_ONLY_ON_CHANNEL: Final[Mapping[ParameterName, int]] = {
    Parameter.LOWBAT: 0,
}
