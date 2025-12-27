# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for calculating the apparent temperature in the sensor category."""

from __future__ import annotations

import logging
from typing import Final

from aiohomematic.const import CalculatedParameter, DataPointCategory, Parameter, ParameterType, ParamsetKey
from aiohomematic.interfaces.model import ChannelProtocol
from aiohomematic.model.calculated.data_point import CalculatedDataPoint
from aiohomematic.model.calculated.field import CalculatedDataPointField
from aiohomematic.model.calculated.support import (
    calculate_apparent_temperature,
    calculate_dew_point,
    calculate_dew_point_spread,
    calculate_enthalpy,
    calculate_frost_point,
    calculate_vapor_concentration,
)
from aiohomematic.model.generic import DpSensor
from aiohomematic.property_decorators import state_property
from aiohomematic.support import element_matches_key

_LOGGER: Final = logging.getLogger(__name__)


class BaseClimateSensor[SensorT: float | None](CalculatedDataPoint[SensorT]):
    """Implementation of a calculated climate sensor."""

    __slots__ = ()

    _category = DataPointCategory.SENSOR

    _dp_humidity: Final = CalculatedDataPointField(
        parameter=Parameter.HUMIDITY,
        paramset_key=ParamsetKey.VALUES,
        dpt=DpSensor,
        fallback_parameters=[Parameter.ACTUAL_HUMIDITY],
    )
    _dp_temperature: Final = CalculatedDataPointField(
        parameter=Parameter.TEMPERATURE,
        paramset_key=ParamsetKey.VALUES,
        dpt=DpSensor,
        fallback_parameters=[Parameter.ACTUAL_TEMPERATURE],
    )

    def __init__(self, *, channel: ChannelProtocol) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._type = ParameterType.FLOAT


class ApparentTemperature(BaseClimateSensor[float | None]):
    """Implementation of a calculated sensor for apparent temperature."""

    __slots__ = ()

    _calculated_parameter = CalculatedParameter.APPARENT_TEMPERATURE

    _dp_wind_speed: Final = CalculatedDataPointField(
        parameter=Parameter.WIND_SPEED,
        paramset_key=ParamsetKey.VALUES,
        dpt=DpSensor,
    )

    def __init__(self, *, channel: ChannelProtocol) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._unit = "°C"

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if this calculated data point is relevant for the model."""
        return (
            element_matches_key(
                search_elements=_RELEVANT_MODELS_APPARENT_TEMPERATURE, compare_with=channel.device.model
            )
            and channel.get_generic_data_point(parameter=Parameter.ACTUAL_TEMPERATURE, paramset_key=ParamsetKey.VALUES)
            is not None
            and channel.get_generic_data_point(parameter=Parameter.HUMIDITY, paramset_key=ParamsetKey.VALUES)
            is not None
            and channel.get_generic_data_point(parameter=Parameter.WIND_SPEED, paramset_key=ParamsetKey.VALUES)
            is not None
        )

    @state_property
    def value(self) -> float | None:
        """Return the value."""
        if (
            self._dp_temperature.value is not None
            and self._dp_humidity.value is not None
            and self._dp_wind_speed.value is not None
        ):
            return calculate_apparent_temperature(
                temperature=self._dp_temperature.value,
                humidity=self._dp_humidity.value,
                wind_speed=self._dp_wind_speed.value,
            )
        return None


class DewPoint(BaseClimateSensor[float | None]):
    """Implementation of a calculated sensor for dew point."""

    __slots__ = ()

    _calculated_parameter = CalculatedParameter.DEW_POINT

    def __init__(self, *, channel: ChannelProtocol) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._unit = "°C"

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if this calculated data point is relevant for the model."""
        return _is_relevant_for_model_temperature_and_humidity(channel=channel, relevant_models=None)

    @state_property
    def value(self) -> float | None:
        """Return the value."""
        if self._dp_temperature.value is not None and self._dp_humidity.value is not None:
            return calculate_dew_point(
                temperature=self._dp_temperature.value,
                humidity=self._dp_humidity.value,
            )
        return None


class DewPointSpread(BaseClimateSensor[float | None]):
    """Implementation of a calculated sensor for dew point spread."""

    __slots__ = ()

    _calculated_parameter = CalculatedParameter.DEW_POINT_SPREAD

    def __init__(self, *, channel: ChannelProtocol) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._unit = "K"

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if this calculated data point is relevant for the model."""
        return _is_relevant_for_model_temperature_and_humidity(channel=channel, relevant_models=None)

    @state_property
    def value(self) -> float | None:
        """Return the value."""
        if self._dp_temperature.value is not None and self._dp_humidity.value is not None:
            return calculate_dew_point_spread(
                temperature=self._dp_temperature.value,
                humidity=self._dp_humidity.value,
            )
        return None


class Enthalpy(BaseClimateSensor[float | None]):
    """Implementation of a calculated sensor for enthalpy."""

    __slots__ = ()

    _calculated_parameter = CalculatedParameter.ENTHALPY

    def __init__(self, *, channel: ChannelProtocol) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._unit = "kJ/kg"

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if this calculated data point is relevant for the model."""
        return _is_relevant_for_model_temperature_and_humidity(channel=channel, relevant_models=None)

    @state_property
    def value(self) -> float | None:
        """Return the value."""
        if self._dp_temperature.value is not None and self._dp_humidity.value is not None:
            return calculate_enthalpy(
                temperature=self._dp_temperature.value,
                humidity=self._dp_humidity.value,
            )
        return None


class FrostPoint(BaseClimateSensor[float | None]):
    """Implementation of a calculated sensor for frost point."""

    __slots__ = ()

    _calculated_parameter = CalculatedParameter.FROST_POINT

    def __init__(self, *, channel: ChannelProtocol) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._unit = "°C"

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if this calculated data point is relevant for the model."""
        return _is_relevant_for_model_temperature_and_humidity(
            channel=channel, relevant_models=_RELEVANT_MODELS_FROST_POINT
        )

    @state_property
    def value(self) -> float | None:
        """Return the value."""
        if self._dp_temperature.value is not None and self._dp_humidity.value is not None:
            return calculate_frost_point(
                temperature=self._dp_temperature.value,
                humidity=self._dp_humidity.value,
            )
        return None


class VaporConcentration(BaseClimateSensor[float | None]):
    """Implementation of a calculated sensor for vapor concentration."""

    __slots__ = ()

    _calculated_parameter = CalculatedParameter.VAPOR_CONCENTRATION

    def __init__(self, *, channel: ChannelProtocol) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._unit = "g/m³"

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if this calculated data point is relevant for the model."""
        return _is_relevant_for_model_temperature_and_humidity(channel=channel, relevant_models=None)

    @state_property
    def value(self) -> float | None:
        """Return the value."""
        if self._dp_temperature.value is not None and self._dp_humidity.value is not None:
            return calculate_vapor_concentration(
                temperature=self._dp_temperature.value,
                humidity=self._dp_humidity.value,
            )
        return None


def _is_relevant_for_model_temperature_and_humidity(
    *, channel: ChannelProtocol, relevant_models: tuple[str, ...] | None = None
) -> bool:
    """Return if this calculated data point is relevant for the model with temperature and humidity."""
    return (
        (
            relevant_models is not None
            and element_matches_key(search_elements=relevant_models, compare_with=channel.device.model)
        )
        or relevant_models is None
    ) and (
        (
            channel.get_generic_data_point(parameter=Parameter.TEMPERATURE, paramset_key=ParamsetKey.VALUES) is not None
            or channel.get_generic_data_point(parameter=Parameter.ACTUAL_TEMPERATURE, paramset_key=ParamsetKey.VALUES)
            is not None
        )
        and (
            channel.get_generic_data_point(parameter=Parameter.HUMIDITY, paramset_key=ParamsetKey.VALUES) is not None
            or channel.get_generic_data_point(parameter=Parameter.ACTUAL_HUMIDITY, paramset_key=ParamsetKey.VALUES)
            is not None
        )
    )


_RELEVANT_MODELS_APPARENT_TEMPERATURE: Final[tuple[str, ...]] = ("HmIP-SWO",)


_RELEVANT_MODELS_FROST_POINT: Final[tuple[str, ...]] = (
    "HmIP-STHO",
    "HmIP-SWO",
)
