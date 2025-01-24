"""Module for data points implemented using the sensor category."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Final

from hahomematic.const import DataPointCategory, Parameter, ParameterType, ParamsetKey
from hahomematic.model import device as hmd
from hahomematic.model.calculated.data_point import CalculatedDataPoint
from hahomematic.model.decorators import state_property
from hahomematic.support import element_matches_key, reduce_args

_LOGGER: Final = logging.getLogger(__name__)


class OperatingVoltageLevel[SensorT: float | None](CalculatedDataPoint[SensorT]):
    """
    Implementation of a sensor.

    This is a default data point that gets automatically generated.
    """

    _calculated_parameter = "OPERATING_VOLTAGE_LEVEL"

    _category = DataPointCategory.SENSOR

    def __init__(self, channel: hmd.Channel) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._type = ParameterType.FLOAT
        self._unit = "%"
        self._battery_data = _get_battery_data(model=self._channel.device.model)
        self._max = float(
            _BatteryVoltage.get(self._battery_data.battery) * self._battery_data.quantity  # type: ignore[assignment, operator]
            if self._battery_data is not None
            else 0.0
        )
        self._min = float(self._dp_low_bat_limit.default if self._dp_low_bat_limit is not None else 0.0)  # type: ignore[assignment]

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        super()._init_data_point_fields()
        self._dp_operating_voltage = self._add_data_point(
            parameter=Parameter.OPERATING_VOLTAGE, paramset_key=ParamsetKey.VALUES
        )

        self._dp_low_bat_limit = self._add_data_point(
            parameter=Parameter.LOW_BAT_LIMIT, paramset_key=ParamsetKey.MASTER
        )

    @staticmethod
    def is_relevant_for_model(channel: hmd.Channel) -> bool:
        """Return if this calculated data point is relevant for the model."""
        return (
            element_matches_key(
                search_elements=_OPERATING_VOLTAGE_LEVEL_MODELS.keys(), compare_with=channel.device.model
            )
            and channel.get_generic_data_point(parameter=Parameter.OPERATING_VOLTAGE, paramset_key=ParamsetKey.VALUES)
            is not None
            and channel.get_generic_data_point(parameter=Parameter.LOW_BAT_LIMIT, paramset_key=ParamsetKey.MASTER)
            is not None
        )

    @state_property
    def value(self) -> float | None:
        """Return the value."""
        try:
            if (
                self._min is not None
                or self._max is not None
                or (self._dp_operating_voltage and self._dp_operating_voltage.value is not None)
            ):
                return None
            if self._dp_operating_voltage and self._dp_operating_voltage.value is not None:
                return float(
                    round(((float(self._dp_operating_voltage.value) - self._min) / (self._max - self._min) * 100), 1)  # type: ignore[operator]
                )
        except Exception as ex:
            _LOGGER.debug(
                "OperatingVoltageLevel: Failed to calculate sensor for %s: %s",
                self._channel.name,
                reduce_args(args=ex.args),
            )
            return None
        return None


class _BatteryType(StrEnum):
    AA = "AA"
    AAA = "AAA"
    CR2032 = "CR2032"
    LR44 = "LR44"
    LR14 = "LR14"
    BABY = "BABY"
    UNKNOWN = "UNKNOWN"


_BatteryVoltage: Final[Mapping[_BatteryType, float]] = {
    _BatteryType.AAA: 1.5,
    _BatteryType.AA: 1.5,
    _BatteryType.CR2032: 3.0,
    _BatteryType.LR44: 1.5,
    _BatteryType.LR14: 1.5,
    _BatteryType.BABY: 1.5,
}


@dataclass(frozen=True)
class _BatteryData:
    model: str
    battery: _BatteryType
    quantity: int = 1


_BATTERY_DATA: Final = (
    _BatteryData(model="ELV-SH-CTH", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-CC-RT-DN", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HM-Dis-EP-WM55", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HM-ES-TX-WM", battery=_BatteryType.AA, quantity=4),
    _BatteryData(model="HM-OU-CFM-TW", battery=_BatteryType.BABY, quantity=2),
    _BatteryData(model="HM-PB-2-FM", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HM-PB-2-WM55", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HM-PB-6-WM55", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HM-PBI-4-FM", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-RC-4-2", battery=_BatteryType.AAA),
    _BatteryData(model="HM-RC-8", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HM-RC-Key4-3", battery=_BatteryType.AAA),
    _BatteryData(model="HM-SCI-3-FM", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-Sec-Key", battery=_BatteryType.AA, quantity=3),
    _BatteryData(model="HM-Sec-MDIR-2", battery=_BatteryType.AA, quantity=3),
    _BatteryData(model="HM-Sec-RHS", battery=_BatteryType.LR44, quantity=2),
    _BatteryData(model="HM-Sec-SC-2", battery=_BatteryType.LR44, quantity=2),
    _BatteryData(model="HM-Sec-SCo", battery=_BatteryType.AAA),
    _BatteryData(model="HM-Sec-SD", battery=_BatteryType.AA, quantity=3),
    _BatteryData(model="HM-Sec-SD-2", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HM-Sec-Sir-WM", battery=_BatteryType.LR14, quantity=2),
    _BatteryData(model="HM-Sec-TiS", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-Sec-Win", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HM-Sen-MDIR-O-2", battery=_BatteryType.AA, quantity=3),
    _BatteryData(model="HM-Sen-MDIR-SM", battery=_BatteryType.AA, quantity=3),
    _BatteryData(model="HM-Sen-MDIR-WM55", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HM-SwI-3-FM", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-TC-IT-WM-W-EU", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HM-WDS10-TH-O", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HM-WDS30-OT2-SM", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HM-WDS30-T-O", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HM-WDS40-TH-I", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-ASIR", battery=_BatteryType.AA, quantity=3),
    _BatteryData(model="HmIP-ASIR-O", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HmIP-DLD", battery=_BatteryType.AA, quantity=4),
    _BatteryData(model="HmIP-DLS", battery=_BatteryType.CR2032),
    _BatteryData(model="HmIP-ESI", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-KRC", battery=_BatteryType.AAA),
    _BatteryData(model="HmIP-RC8", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-SAM", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-SCI", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-SLO", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-SMI", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-SMI55", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-SMO", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-SPI", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-SRH", battery=_BatteryType.AAA),
    _BatteryData(model="HmIP-STH", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-STHD", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-STHO", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-STV", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-SWD", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-SWDM", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-SWDO", battery=_BatteryType.AAA),
    _BatteryData(model="HmIP-SWDO-I", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-SWDO-PL", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-SWO", battery=_BatteryType.AA, quantity=3),
    _BatteryData(model="HmIP-SWSD", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HmIP-WGC", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-WRC", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-WTH", battery=_BatteryType.AAA, quantity=2),
    _BatteryData(model="HmIP-WTH-B-2", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-eTRV", battery=_BatteryType.AA, quantity=2),
    _BatteryData(model="HmIP-eTRV-CL", battery=_BatteryType.AA, quantity=4),
    _BatteryData(model="M-WDS40-TH-I", battery=_BatteryType.AA, quantity=2),
)

_OPERATING_VOLTAGE_LEVEL_MODELS: Final[Mapping[str, _BatteryData]] = {
    battery.model: battery for battery in _BATTERY_DATA if battery.model != _BatteryType.UNKNOWN
}


def _get_battery_data(model: str) -> _BatteryData | None:
    """Return the battery data by model."""
    model_l = model.lower()
    for battery_data in _OPERATING_VOLTAGE_LEVEL_MODELS.values():
        if battery_data.model.lower() == model_l:
            return battery_data

    for battery_data in _OPERATING_VOLTAGE_LEVEL_MODELS.values():
        if model_l.startswith(battery_data.model.lower()):
            return battery_data

    return None
