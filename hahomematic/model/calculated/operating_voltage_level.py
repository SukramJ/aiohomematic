"""Module for calculating the operating voltage level in the sensor category."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Any, Final

from hahomematic.const import CalulatedParameter, DataPointCategory, Parameter, ParameterType, ParamsetKey
from hahomematic.model import device as hmd
from hahomematic.model.calculated.data_point import CalculatedDataPoint
from hahomematic.model.decorators import state_property
from hahomematic.model.generic import DpFloat, DpSensor
from hahomematic.support import element_matches_key, reduce_args

_BATTERY_QTY: Final = "Battery Qty"
_BATTERY_TYPE: Final = "Battery Type"
_LOW_BAT_LIMIT: Final = "Low Battery Limit"
_LOW_BAT_LIMIT_DEFAULT: Final = "Low Battery Limit Default"
_VOLTAGE_MAX: Final = "Voltage max"

_LOGGER: Final = logging.getLogger(__name__)


class OperatingVoltageLevel[SensorT: float | None](CalculatedDataPoint[SensorT]):
    """Implementation of a calculated sensor for operating voltage level."""

    _calculated_parameter = CalulatedParameter.OPERATING_VOLTAGE_LEVEL
    _category = DataPointCategory.SENSOR

    def __init__(self, channel: hmd.Channel) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._type = ParameterType.FLOAT
        self._unit = "%"

    def _init_data_point_fields(self) -> None:
        """Init the data point fields."""
        super()._init_data_point_fields()
        self._battery_data = _get_battery_data(model=self._channel.device.model)

        operating_voltage: DpSensor = self._add_data_point(
            parameter=Parameter.OPERATING_VOLTAGE, paramset_key=ParamsetKey.VALUES, data_point_type=DpSensor
        )

        self._dp_operating_voltage: DpSensor = (
            operating_voltage
            if isinstance(operating_voltage, DpSensor)
            else self._add_data_point(
                parameter=Parameter.BATTERY_STATE, paramset_key=ParamsetKey.VALUES, data_point_type=DpSensor
            )
        )

        low_bat_limit: DpSensor = self._add_data_point(
            parameter=Parameter.LOW_BAT_LIMIT, paramset_key=ParamsetKey.MASTER, data_point_type=DpSensor
        )

        self._dp_low_bat_limit: DpFloat = (
            low_bat_limit
            if isinstance(low_bat_limit, DpFloat)
            else self._add_device_data_point(
                channel_address=self.channel.device.address,
                parameter=Parameter.LOW_BAT_LIMIT,
                paramset_key=ParamsetKey.MASTER,
                data_point_type=DpFloat,
            )
        )

        self._low_bat_limit_default = (
            float(self._dp_low_bat_limit.default) if isinstance(self._dp_low_bat_limit, DpFloat) else None
        )
        self._voltage_max = (
            float(_BatteryVoltage.get(self._battery_data.battery) * self._battery_data.quantity)  # type: ignore[operator]
            if self._battery_data is not None
            else None
        )

    @staticmethod
    def is_relevant_for_model(channel: hmd.Channel) -> bool:
        """Return if this calculated data point is relevant for the model."""
        if element_matches_key(
            search_elements=_IGNORE_OPERATING_VOLTAGE_LEVEL_MODELS, compare_with=channel.device.model
        ):
            return False
        return element_matches_key(
            search_elements=_OPERATING_VOLTAGE_LEVEL_MODELS.keys(), compare_with=channel.device.model
        ) and (
            (
                channel.get_generic_data_point(
                    parameter=Parameter.OPERATING_VOLTAGE,
                    paramset_key=ParamsetKey.VALUES,
                )
                and channel.get_generic_data_point(parameter=Parameter.LOW_BAT_LIMIT, paramset_key=ParamsetKey.MASTER)
            )
            is not None
            or (
                channel.get_generic_data_point(
                    parameter=Parameter.BATTERY_STATE,
                    paramset_key=ParamsetKey.VALUES,
                )
                and channel.device.get_generic_data_point(
                    channel_address=channel.device.address,
                    parameter=Parameter.LOW_BAT_LIMIT,
                    paramset_key=ParamsetKey.MASTER,
                )
            )
            is not None
        )

    @state_property
    def additional_information(self) -> dict[str, Any]:
        """Return additional information about the entity."""
        ainfo = super().additional_information
        if self._battery_data is not None:
            ainfo.update(
                {
                    _BATTERY_QTY: self._battery_data.quantity,
                    _BATTERY_TYPE: self._battery_data.battery,
                    _LOW_BAT_LIMIT: f"{self._low_bat_limit}V",
                    _LOW_BAT_LIMIT_DEFAULT: f"{self._low_bat_limit_default}V",
                    _VOLTAGE_MAX: f"{self._voltage_max}V",
                }
            )
        return ainfo

    @state_property
    def value(self) -> float | None:
        """Return the value."""
        try:
            if (low_bat_limit := self._low_bat_limit) is None or self._voltage_max is None:
                return None
            if self._dp_operating_voltage and self._dp_operating_voltage.value is not None:
                return max(
                    0,
                    min(
                        100,
                        float(
                            round(
                                (
                                    (float(self._dp_operating_voltage.value) - low_bat_limit)
                                    / (self._voltage_max - low_bat_limit)
                                    * 100
                                ),
                                1,
                            )
                        ),
                    ),
                )
        except Exception as ex:
            _LOGGER.debug(
                "OperatingVoltageLevel: Failed to calculate sensor for %s: %s",
                self._channel.name,
                reduce_args(args=ex.args),
            )
            return None
        return None

    @property
    def _low_bat_limit(self) -> float | None:
        """Return the min value."""
        return (
            float(self._dp_low_bat_limit.value)
            if self._dp_low_bat_limit is not None and self._dp_low_bat_limit.value is not None
            else None
        )


class _BatteryType(StrEnum):
    CR2032 = "CR2032"
    LR44 = "LR44"
    R03 = "AAA"
    R14 = "BABY"
    R6 = "AA"
    UNKNOWN = "UNKNOWN"


_BatteryVoltage: Final[Mapping[_BatteryType, float]] = {
    _BatteryType.CR2032: 3.0,
    _BatteryType.LR44: 1.5,
    _BatteryType.R03: 1.5,
    _BatteryType.R14: 1.5,
    _BatteryType.R6: 1.5,
}


@dataclass(frozen=True)
class _BatteryData:
    model: str
    battery: _BatteryType
    quantity: int = 1


# This list is sorted. models with shorted model types are sorted to
_BATTERY_DATA: Final = (
    # HM long model str
    _BatteryData(model="HM-CC-RT-DN", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HM-Dis-EP-WM55", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HM-ES-TX-WM", battery=_BatteryType.R6, quantity=4),
    _BatteryData(model="HM-OU-CFM-TW", battery=_BatteryType.R14, quantity=2),
    _BatteryData(model="HM-PB-2-FM", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HM-PB-2-WM55", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HM-PB-6-WM55", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HM-PBI-4-FM", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-RC-4-2", battery=_BatteryType.R03),
    _BatteryData(model="HM-RC-8", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HM-RC-Key4-3", battery=_BatteryType.R03),
    _BatteryData(model="HM-SCI-3-FM", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-Sec-Key", battery=_BatteryType.R6, quantity=3),
    _BatteryData(model="HM-Sec-MDIR-2", battery=_BatteryType.R6, quantity=3),
    _BatteryData(model="HM-Sec-RHS", battery=_BatteryType.LR44, quantity=2),
    _BatteryData(model="HM-Sec-SC-2", battery=_BatteryType.LR44, quantity=2),
    _BatteryData(model="HM-Sec-SCo", battery=_BatteryType.R03),
    _BatteryData(model="HM-Sec-SD-2", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HM-Sec-Sir-WM", battery=_BatteryType.R14, quantity=2),
    _BatteryData(model="HM-Sec-TiS", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-Sec-Win", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HM-Sen-MDIR-O-2", battery=_BatteryType.R6, quantity=3),
    _BatteryData(model="HM-Sen-MDIR-SM", battery=_BatteryType.R6, quantity=3),
    _BatteryData(model="HM-Sen-MDIR-WM55", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HM-SwI-3-FM", battery=_BatteryType.CR2032),
    _BatteryData(model="HM-TC-IT-WM-W-EU", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HM-WDS10-TH-O", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HM-WDS30-OT2-SM", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HM-WDS30-T-O", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HM-WDS40-TH-I", battery=_BatteryType.R6, quantity=2),
    # HM short model str
    _BatteryData(model="HM-Sec-SD", battery=_BatteryType.R6, quantity=3),
    # HmIP model > 4
    _BatteryData(model="HmIP-ASIR-O", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HmIP-DSD-PCB", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-PCBS-BAT", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HmIP-SMI55", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-STE2-PCB", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-SWDO-I", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-SWDO-PL", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-WTH-B-2", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-eTRV-CL", battery=_BatteryType.R6, quantity=4),
    # HmIP model 4
    _BatteryData(model="ELV-SH-SW1-BAT", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="ELV-SH-TACO", battery=_BatteryType.R03, quantity=1),
    _BatteryData(model="HmIP-ASIR", battery=_BatteryType.R6, quantity=3),
    _BatteryData(model="HmIP-FCI1", battery=_BatteryType.CR2032),
    _BatteryData(model="HmIP-FCI6", battery=_BatteryType.R03),
    _BatteryData(model="HmIP-MP3P", battery=_BatteryType.R14, quantity=2),
    _BatteryData(model="HmIP-RCB1", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-SPDR", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-STHD", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-STHO", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-SWDM", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-SWDO", battery=_BatteryType.R03),
    _BatteryData(model="HmIP-SWSD", battery=_BatteryType.UNKNOWN),
    _BatteryData(model="HmIP-eTRV", battery=_BatteryType.R6, quantity=2),
    # HmIP model 3
    _BatteryData(model="ELV-SH-CTH", battery=_BatteryType.CR2032),
    _BatteryData(model="ELV-SH-WSM", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-DBB", battery=_BatteryType.R03),
    _BatteryData(model="HmIP-DLD", battery=_BatteryType.R6, quantity=3),
    _BatteryData(model="HmIP-DLS", battery=_BatteryType.CR2032),
    _BatteryData(model="HmIP-ESI", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-KRC", battery=_BatteryType.R03),
    _BatteryData(model="HmIP-RC8", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-SAM", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-SCI", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-SLO", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-SMI", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-SMO", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-SPI", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-SRH", battery=_BatteryType.R03),
    _BatteryData(model="HmIP-STH", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-STV", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-SWD", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-SWO", battery=_BatteryType.R6, quantity=3),
    _BatteryData(model="HmIP-WGC", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-WKP", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-WRC", battery=_BatteryType.R03, quantity=2),
    _BatteryData(model="HmIP-WSM", battery=_BatteryType.R6, quantity=2),
    _BatteryData(model="HmIP-WTH", battery=_BatteryType.R03, quantity=2),
)

_OPERATING_VOLTAGE_LEVEL_MODELS: Final[Mapping[str, _BatteryData]] = {
    battery.model: battery for battery in _BATTERY_DATA if battery.battery != _BatteryType.UNKNOWN
}

_IGNORE_OPERATING_VOLTAGE_LEVEL_MODELS: Final[tuple[str, ...]] = tuple(
    [battery.model for battery in _BATTERY_DATA if battery.battery == _BatteryType.UNKNOWN]
)


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
