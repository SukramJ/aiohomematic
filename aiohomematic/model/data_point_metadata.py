# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Metadata mappings for Homematic data points.

Maps Homematic parameters to their semantic quantity and value behavior.
This is Homematic domain knowledge, independent of any smart home platform.

Public API of this module is defined by __all__.
"""

from collections.abc import Mapping
from typing import Final, NamedTuple

from aiohomematic.const import Quantity, ValueBehavior

__all__ = [
    "QuantityMetadata",
    "get_binary_sensor_quantity_by_device_and_param",
    "get_quantity_metadata_by_device_and_param",
    "get_quantity_metadata_by_param",
    "get_quantity_metadata_by_unit",
]


class QuantityMetadata(NamedTuple):
    """Metadata for a data point's semantic classification."""

    quantity: Quantity | None = None
    value_behavior: ValueBehavior | None = None


# ---------------------------------------------------------------------------
# Sensor: parameter → (quantity, value_behavior)
# ---------------------------------------------------------------------------

_SENSOR_METADATA_BY_PARAM: Final[Mapping[str | tuple[str, ...], QuantityMetadata]] = {
    "AIR_PRESSURE": QuantityMetadata(
        quantity=Quantity.PRESSURE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "BRIGHTNESS": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "CARRIER_SENSE_LEVEL": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "CONCENTRATION": QuantityMetadata(
        quantity=Quantity.CO2,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "CURRENT": QuantityMetadata(
        quantity=Quantity.CURRENT,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "DEWPOINT": QuantityMetadata(
        quantity=Quantity.TEMPERATURE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    ("ACTIVITY_STATE", "DIRECTION"): QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    "DOOR_STATE": QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    "DUTY_CYCLE_LEVEL": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "ENERGY_COUNTER": QuantityMetadata(
        quantity=Quantity.ENERGY,
        value_behavior=ValueBehavior.MONOTONIC,
    ),
    "FILLING_LEVEL": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "FREQUENCY": QuantityMetadata(
        quantity=Quantity.FREQUENCY,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "GAS_ENERGY_COUNTER": QuantityMetadata(
        quantity=Quantity.GAS,
        value_behavior=ValueBehavior.MONOTONIC,
    ),
    "GAS_FLOW": QuantityMetadata(
        quantity=Quantity.VOLUME_FLOW_RATE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "GAS_VOLUME": QuantityMetadata(
        quantity=Quantity.GAS,
        value_behavior=ValueBehavior.MONOTONIC,
    ),
    ("HUMIDITY", "ACTUAL_HUMIDITY"): QuantityMetadata(
        quantity=Quantity.HUMIDITY,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "IEC_ENERGY_COUNTER": QuantityMetadata(
        quantity=Quantity.ENERGY,
        value_behavior=ValueBehavior.MONOTONIC,
    ),
    "IEC_POWER": QuantityMetadata(
        quantity=Quantity.POWER,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    (
        "ILLUMINATION",
        "AVERAGE_ILLUMINATION",
        "CURRENT_ILLUMINATION",
        "HIGHEST_ILLUMINATION",
        "LOWEST_ILLUMINATION",
        "LUX",
    ): QuantityMetadata(
        quantity=Quantity.ILLUMINANCE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    ("LEVEL", "LEVEL_2"): QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "LOCK_STATE": QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    (
        "MASS_CONCENTRATION_PM_1",
        "MASS_CONCENTRATION_PM_1_24H_AVERAGE",
    ): QuantityMetadata(
        quantity=Quantity.PM1,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    (
        "MASS_CONCENTRATION_PM_10",
        "MASS_CONCENTRATION_PM_10_24H_AVERAGE",
    ): QuantityMetadata(
        quantity=Quantity.PM10,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    (
        "MASS_CONCENTRATION_PM_2_5",
        "MASS_CONCENTRATION_PM_2_5_24H_AVERAGE",
    ): QuantityMetadata(
        quantity=Quantity.PM25,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "NUMBER_CONCENTRATION_PM_1": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "NUMBER_CONCENTRATION_PM_10": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "NUMBER_CONCENTRATION_PM_2_5": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "TYPICAL_PARTICLE_SIZE": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    ("BATTERY_STATE", "OPERATING_VOLTAGE"): QuantityMetadata(
        quantity=Quantity.VOLTAGE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "POWER": QuantityMetadata(
        quantity=Quantity.POWER,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "RAIN_COUNTER": QuantityMetadata(
        value_behavior=ValueBehavior.MONOTONIC,
    ),
    ("RSSI_DEVICE", "RSSI_PEER"): QuantityMetadata(
        quantity=Quantity.SIGNAL_STRENGTH,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    ("ACTUAL_TEMPERATURE", "TEMPERATURE"): QuantityMetadata(
        quantity=Quantity.TEMPERATURE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "SMOKE_DETECTOR_ALARM_STATUS": QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    "SUNSHINEDURATION": QuantityMetadata(
        value_behavior=ValueBehavior.MONOTONIC,
    ),
    "VALUE": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "VAPOR_CONCENTRATION": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "VOLTAGE": QuantityMetadata(
        quantity=Quantity.VOLTAGE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    (
        "WIND_DIR",
        "WIND_DIR_RANGE",
        "WIND_DIRECTION",
        "WIND_DIRECTION_RANGE",
    ): QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "WIND_SPEED": QuantityMetadata(
        quantity=Quantity.WIND_SPEED,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
}

# ---------------------------------------------------------------------------
# Sensor: (device_model, parameter) → (quantity, value_behavior) overrides
# ---------------------------------------------------------------------------

_SENSOR_METADATA_BY_DEVICE_AND_PARAM: Final[Mapping[tuple[str | tuple[str, ...], str], QuantityMetadata]] = {
    ("HmIP-WKP", "CODE_STATE"): QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    (
        ("HmIP-SRH", "HM-Sec-RHS", "HM-Sec-xx", "ZEL STG RM FDK"),
        "STATE",
    ): QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    ("HM-Sec-Win", "STATUS"): QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    ("HM-Sec-Win", "DIRECTION"): QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    ("HM-Sec-Win", "ERROR"): QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    ("HM-Sec-Key", "DIRECTION"): QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    ("HM-Sec-Key", "ERROR"): QuantityMetadata(
        quantity=Quantity.ENUM,
    ),
    (("HM-CC-RT-DN", "HM-CC-VD"), "VALVE_STATE"): QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
}

# ---------------------------------------------------------------------------
# Sensor: unit → (quantity, value_behavior) fallback
# ---------------------------------------------------------------------------

_SENSOR_METADATA_BY_UNIT: Final[Mapping[str, QuantityMetadata]] = {
    "%": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "bar": QuantityMetadata(
        quantity=Quantity.PRESSURE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "°C": QuantityMetadata(
        quantity=Quantity.TEMPERATURE,
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
    "g/m³": QuantityMetadata(
        value_behavior=ValueBehavior.INSTANTANEOUS,
    ),
}

# ---------------------------------------------------------------------------
# Binary sensor: parameter → quantity
# ---------------------------------------------------------------------------

_BINARY_SENSOR_QUANTITY_BY_PARAM: Final[Mapping[str | tuple[str, ...], Quantity]] = {
    "ALARMSTATE": Quantity.SAFETY,
    "ACOUSTIC_ALARM_ACTIVE": Quantity.SAFETY,
    ("BLOCKED_PERMANENT", "BLOCKED_TEMPORARY"): Quantity.PROBLEM,
    "BURST_LIMIT_WARNING": Quantity.PROBLEM,
    ("DUTYCYCLE", "DUTY_CYCLE"): Quantity.PROBLEM,
    "DEW_POINT_ALARM": Quantity.PROBLEM,
    "EMERGENCY_OPERATION": Quantity.SAFETY,
    "ERROR_JAMMED": Quantity.PROBLEM,
    "HEATER_STATE": Quantity.HEAT,
    ("LOWBAT", "LOW_BAT", "LOWBAT_SENSOR"): Quantity.BATTERY,
    "MOISTURE_DETECTED": Quantity.MOISTURE,
    "MOTION": Quantity.MOTION,
    "OPTICAL_ALARM_ACTIVE": Quantity.SAFETY,
    "POWER_MAINS_FAILURE": Quantity.PROBLEM,
    "PRESENCE_DETECTION_STATE": Quantity.PRESENCE,
    ("PROCESS", "WORKING"): Quantity.RUNNING,
    "RAINING": Quantity.MOISTURE,
    ("SABOTAGE", "SABOTAGE_STICKY"): Quantity.TAMPER,
    "WATERLEVEL_DETECTED": Quantity.MOISTURE,
    "WINDOW_STATE": Quantity.WINDOW,
}

# ---------------------------------------------------------------------------
# Binary sensor: (device_model, parameter) → quantity overrides
# ---------------------------------------------------------------------------

_BINARY_SENSOR_QUANTITY_BY_DEVICE_AND_PARAM: Final[Mapping[tuple[str | tuple[str, ...], str], Quantity]] = {
    ("HmIP-DSD-PCB", "STATE"): Quantity.OCCUPANCY,
    (("HmIP-SCI", "HmIP-FCI1", "HmIP-FCI6"), "STATE"): Quantity.OPENING,
    ("HM-Sec-SD", "STATE"): Quantity.SMOKE,
    (
        (
            "HmIP-SWD",
            "HmIP-SWDO",
            "HmIP-SWDM",
            "HM-Sec-SC",
            "HM-SCI-3-FM",
            "ZEL STG RM FFK",
        ),
        "STATE",
    ): Quantity.WINDOW,
    ("HM-Sen-RD-O", "STATE"): Quantity.MOISTURE,
    ("HM-Sec-Win", "WORKING"): Quantity.RUNNING,
}


# ---------------------------------------------------------------------------
# Public lookup functions
# ---------------------------------------------------------------------------


def _param_matches(*, params: str | tuple[str, ...], parameter: str) -> bool:
    """Check if a parameter matches a key (single string or tuple)."""
    if isinstance(params, str):
        return parameter.upper() == params.upper()
    return any(parameter.upper() == p.upper() for p in params)


def _model_matches(*, models: str | tuple[str, ...], device_model: str) -> bool:
    """Check if a device model matches (prefix match)."""
    if isinstance(models, str):
        return device_model.upper().startswith(models.upper())
    return any(device_model.upper().startswith(m.upper()) for m in models)


def get_quantity_metadata_by_param(*, parameter: str) -> QuantityMetadata | None:
    """Look up quantity metadata for a sensor parameter."""
    for params, metadata in _SENSOR_METADATA_BY_PARAM.items():
        if _param_matches(params=params, parameter=parameter):
            return metadata
    return None


def get_quantity_metadata_by_device_and_param(*, device_model: str, parameter: str) -> QuantityMetadata | None:
    """Look up quantity metadata by device model and parameter (overrides)."""
    for (models, param), metadata in _SENSOR_METADATA_BY_DEVICE_AND_PARAM.items():
        if param.upper() == parameter.upper() and _model_matches(models=models, device_model=device_model):
            return metadata
    return None


def get_quantity_metadata_by_unit(*, unit: str) -> QuantityMetadata | None:
    """Look up quantity metadata by unit (fallback)."""
    return _SENSOR_METADATA_BY_UNIT.get(unit)


def get_binary_sensor_quantity_by_device_and_param(*, device_model: str, parameter: str) -> Quantity | None:
    """Look up binary sensor quantity by device model and parameter (overrides)."""
    for (models, param), quantity in _BINARY_SENSOR_QUANTITY_BY_DEVICE_AND_PARAM.items():
        if param.upper() == parameter.upper() and _model_matches(models=models, device_model=device_model):
            return quantity
    return None


def get_binary_sensor_quantity_by_param(*, parameter: str) -> Quantity | None:
    """Look up binary sensor quantity by parameter."""
    for params, quantity in _BINARY_SENSOR_QUANTITY_BY_PARAM.items():
        if _param_matches(params=params, parameter=parameter):
            return quantity
    return None
