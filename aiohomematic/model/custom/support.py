# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Support classes used by aiohomematic custom data points."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aiohomematic.const import Field, Parameter
from aiohomematic.type_aliases import CustomDataPointFactory


@dataclass(frozen=True, kw_only=True, slots=True)
class CustomConfig:
    """Data for custom data_point creation."""

    make_ce_func: CustomDataPointFactory
    channels: tuple[int | None, ...] = (1,)
    extended: ExtendedConfig | None = None
    schedule_channel_no: int | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ExtendedConfig:
    """Extended data for custom data_point creation."""

    fixed_channels: Mapping[int, Mapping[Field, Parameter]] | None = None
    additional_data_points: Mapping[int | tuple[int, ...], tuple[Parameter, ...]] | None = None

    @property
    def required_parameters(self) -> tuple[Parameter, ...]:
        """Return vol.Required parameters from extended config."""
        required_parameters: list[Parameter] = []
        if fixed_channels := self.fixed_channels:
            for mapping in fixed_channels.values():
                required_parameters.extend(mapping.values())

        if additional_dps := self.additional_data_points:
            for parameters in additional_dps.values():
                required_parameters.extend(parameters)

        return tuple(required_parameters)
