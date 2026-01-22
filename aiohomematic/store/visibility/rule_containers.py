# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Rule container classes for the visibility system.

This module provides the ChannelParamsetRules and ModelRules classes which
manage parameter rules indexed by channel/paramset and model name respectively.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from aiohomematic.const import ParamsetKey
from aiohomematic.store.visibility.types import ChannelNo, ModelName, ParameterName

if TYPE_CHECKING:
    from aiohomematic.store.visibility.parser import UnIgnoreChannelNo


class ChannelParamsetRules:
    """
    Manage parameter rules indexed by (channel_no, paramset_key).

    Replaces nested defaultdict structures with a cleaner interface.
    """

    __slots__ = ("_data",)

    def __init__(self) -> None:
        """Initialize empty rules container."""
        self._data: dict[tuple[UnIgnoreChannelNo, ParamsetKey], set[ParameterName]] = {}

    def add(
        self,
        *,
        channel_no: UnIgnoreChannelNo,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
    ) -> None:
        """Add a parameter to the rules for a channel/paramset combination."""
        if (key := (channel_no, paramset_key)) not in self._data:
            self._data[key] = set()
        self._data[key].add(parameter)

    def contains(
        self,
        *,
        channel_no: UnIgnoreChannelNo,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
    ) -> bool:
        """Check if a parameter exists in the rules for a channel/paramset combination."""
        return parameter in self._data.get((channel_no, paramset_key), set())

    def get_parameters(
        self,
        *,
        channel_no: UnIgnoreChannelNo,
        paramset_key: ParamsetKey,
    ) -> set[ParameterName]:
        """Return the set of parameters for a channel/paramset combination."""
        return self._data.get((channel_no, paramset_key), set())

    def update(
        self,
        *,
        channel_no: UnIgnoreChannelNo,
        paramset_key: ParamsetKey,
        parameters: Iterable[ParameterName],
    ) -> None:
        """Add multiple parameters to the rules for a channel/paramset combination."""
        if (key := (channel_no, paramset_key)) not in self._data:
            self._data[key] = set()
        self._data[key].update(parameters)


class ModelRules:
    """
    Manage parameter rules indexed by model name.

    Each model has its own ChannelParamsetRules and a set of relevant channels.
    """

    __slots__ = ("_channel_rules", "_relevant_channels")

    def __init__(self) -> None:
        """Initialize empty model rules container."""
        self._channel_rules: dict[ModelName, ChannelParamsetRules] = {}
        self._relevant_channels: dict[ModelName, set[ChannelNo]] = {}

    def add_parameter(
        self,
        *,
        model: ModelName,
        channel_no: UnIgnoreChannelNo,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
    ) -> None:
        """Add a parameter rule for a model/channel/paramset combination."""
        if model not in self._channel_rules:
            self._channel_rules[model] = ChannelParamsetRules()
        self._channel_rules[model].add(channel_no=channel_no, paramset_key=paramset_key, parameter=parameter)

    def add_relevant_channel(self, *, model: ModelName, channel_no: ChannelNo) -> None:
        """Mark a channel as relevant for MASTER paramset fetching."""
        if model not in self._relevant_channels:
            self._relevant_channels[model] = set()
        self._relevant_channels[model].add(channel_no)

    def contains(
        self,
        *,
        model: ModelName,
        channel_no: UnIgnoreChannelNo,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
    ) -> bool:
        """Check if a parameter exists in the rules."""
        if model not in self._channel_rules:
            return False
        return self._channel_rules[model].contains(
            channel_no=channel_no, paramset_key=paramset_key, parameter=parameter
        )

    def get_models(self) -> Iterable[ModelName]:
        """Return all model names with rules."""
        return self._channel_rules.keys()

    def get_relevant_channels(self, *, model: ModelName) -> set[ChannelNo]:
        """Return the set of relevant channels for a model."""
        return self._relevant_channels.get(model, set())

    def has_relevant_channel(self, *, model: ModelName, channel_no: ChannelNo) -> bool:
        """Check if a channel is relevant for a model."""
        return channel_no in self._relevant_channels.get(model, set())

    def update_parameters(
        self,
        *,
        model: ModelName,
        channel_no: UnIgnoreChannelNo,
        paramset_key: ParamsetKey,
        parameters: Iterable[ParameterName],
    ) -> None:
        """Add multiple parameter rules for a model/channel/paramset combination."""
        if model not in self._channel_rules:
            self._channel_rules[model] = ChannelParamsetRules()
        self._channel_rules[model].update(channel_no=channel_no, paramset_key=paramset_key, parameters=parameters)
