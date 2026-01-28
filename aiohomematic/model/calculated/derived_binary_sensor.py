# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Module for derived binary sensors based on enum data points.

This module provides a registry-based system for creating binary sensors
derived from enum parameters with declarative mapping rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final, override

from aiohomematic.const import CalculatedParameter, DataPointCategory, Parameter, ParameterType, ParamsetKey
from aiohomematic.interfaces import ChannelProtocol
from aiohomematic.model.calculated import CalculatedDataPoint
from aiohomematic.model.generic import DpSelect
from aiohomematic.property_decorators import state_property
from aiohomematic.support import element_matches_key

_LOGGER: Final = logging.getLogger(__name__)

__all__ = [
    "DerivedBinarySensor",
    "DerivedBinarySensorMapping",
    "DerivedBinarySensorRegistry",
]


@dataclass(frozen=True, kw_only=True, slots=True)
class DerivedBinarySensorMapping:
    """Definition of a derived binary sensor mapping rule."""

    model: str | tuple[str, ...]
    source_parameter: Parameter
    source_channel_no: int
    on_values: frozenset[str]
    off_values: frozenset[str] | None = None
    calculated_parameter: CalculatedParameter


class DerivedBinarySensorRegistry:
    """Registry for derived binary sensor mappings."""

    _registry: dict[CalculatedParameter, DerivedBinarySensorMapping] = {}
    _model_index: dict[str, list[CalculatedParameter]] = {}

    @classmethod
    def get_mapping(cls, *, calculated_parameter: CalculatedParameter) -> DerivedBinarySensorMapping | None:
        """Return mapping for a specific calculated parameter."""
        return cls._registry.get(calculated_parameter)

    @classmethod
    def get_mappings_for_model(cls, *, model: str) -> tuple[DerivedBinarySensorMapping, ...]:
        """Return all derived binary sensor mappings for a device model."""
        model_lower = model.lower()
        mappings: list[DerivedBinarySensorMapping] = []

        # Exact match
        for indexed_model, params in cls._model_index.items():
            if indexed_model.lower() == model_lower:
                mappings.extend(cls._registry[param] for param in params)

        # Prefix match if no exact match
        if not mappings:
            for indexed_model, params in cls._model_index.items():
                if model_lower.startswith(indexed_model.lower()):
                    mappings.extend(cls._registry[param] for param in params)

        return tuple(mappings)

    @classmethod
    def register(
        cls,
        *,
        model: str | tuple[str, ...],
        source_parameter: Parameter,
        source_channel_no: int,
        on_values: frozenset[str],
        calculated_parameter: CalculatedParameter,
        off_values: frozenset[str] | None = None,
    ) -> None:
        """Register a derived binary sensor mapping."""
        mapping = DerivedBinarySensorMapping(
            model=model,
            source_parameter=source_parameter,
            source_channel_no=source_channel_no,
            on_values=on_values,
            off_values=off_values,
            calculated_parameter=calculated_parameter,
        )
        cls._registry[calculated_parameter] = mapping

        # Build model index for fast lookup
        models = (model,) if isinstance(model, str) else model
        for model_name in models:
            if model_name not in cls._model_index:
                cls._model_index[model_name] = []
            cls._model_index[model_name].append(calculated_parameter)


class DerivedBinarySensor(CalculatedDataPoint[bool | None]):
    """
    Calculated binary sensor derived from an enum data point.

    This class implements a generic derived binary sensor that maps
    enum values to boolean states based on declarative mapping rules.
    """

    __slots__ = ("_calculated_parameter", "_dp_source", "_mapping")

    _category = DataPointCategory.BINARY_SENSOR

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        mapping: DerivedBinarySensorMapping,
    ) -> None:
        """Initialize the derived binary sensor."""
        self._mapping: Final = mapping
        self._calculated_parameter = mapping.calculated_parameter
        super().__init__(channel=channel)
        self._type = ParameterType.BOOL

    @staticmethod
    def is_relevant_for_mapping(
        *,
        channel: ChannelProtocol,
        mapping: DerivedBinarySensorMapping,
    ) -> bool:
        """Return if a specific mapping is relevant for this channel."""
        # Check model match
        if isinstance(mapping.model, tuple):
            if not element_matches_key(search_elements=mapping.model, compare_with=channel.device.model):
                return False
        elif not element_matches_key(search_elements=(mapping.model,), compare_with=channel.device.model):
            return False

        # Check channel match
        if channel.no != mapping.source_channel_no:
            return False

        # Check source parameter exists
        return (
            channel.get_generic_data_point(
                parameter=mapping.source_parameter,
                paramset_key=ParamsetKey.VALUES,
            )
            is not None
        )

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if any derived binary sensor is relevant for this channel."""
        mappings = DerivedBinarySensorRegistry.get_mappings_for_model(model=channel.device.model)
        for mapping in mappings:
            if DerivedBinarySensor.is_relevant_for_mapping(channel=channel, mapping=mapping):
                return True
        return False

    @state_property
    def value(self) -> bool | None:
        """Return the derived binary value."""
        if (source_value := self._dp_source.value) is None:
            return None
        return source_value in self._mapping.on_values

    @override
    def _post_init(self) -> None:
        """Post action after initialisation of the data point fields."""
        super()._post_init()

        # Dynamically resolve source data point
        self._dp_source = self._add_data_point(
            parameter=self._mapping.source_parameter,
            paramset_key=ParamsetKey.VALUES,
            dpt=DpSelect,
        )


# Register known derived binary sensors
DerivedBinarySensorRegistry.register(
    model=(
        "HmIP-SRH",
        "HM-Sec-RHS",
    ),
    source_parameter=Parameter.STATE,
    source_channel_no=1,
    on_values=frozenset({"TILTED", "OPEN"}),
    calculated_parameter=CalculatedParameter.WINDOW_OPEN,
)

DerivedBinarySensorRegistry.register(
    model="HmIP-SWSD",
    source_parameter=Parameter.SMOKE_DETECTOR_ALARM_STATUS,
    source_channel_no=1,
    on_values=frozenset({"PRIMARY_ALARM", "SECONDARY_ALARM"}),
    calculated_parameter=CalculatedParameter.SMOKE_ALARM,
)

DerivedBinarySensorRegistry.register(
    model="HmIP-SWSD",
    source_parameter=Parameter.SMOKE_DETECTOR_ALARM_STATUS,
    source_channel_no=1,
    on_values=frozenset(
        {
            "INTRUSION_ALARM",
        }
    ),
    calculated_parameter=CalculatedParameter.INTRUSION_ALARM,
)
