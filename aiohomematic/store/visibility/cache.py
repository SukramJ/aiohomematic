# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Parameter visibility cache for Homematic data points.

This module provides the ParameterVisibilityCache class which determines whether
parameters should be created, shown, hidden, ignored, or un-ignored for channels
and devices. It consolidates rules from multiple sources and memoizes decisions
to avoid repeated computations.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
import logging
from typing import TYPE_CHECKING, Final, NamedTuple

from aiohomematic import support as hms
from aiohomematic.const import UN_IGNORE_WILDCARD, ParamsetKey
from aiohomematic.interfaces.operations import ParameterVisibilityProviderProtocol
from aiohomematic.model.custom import get_required_parameters
from aiohomematic.store.visibility.parser import ParsedUnIgnoreLine, UnIgnoreChannelNo, parse_un_ignore_line
from aiohomematic.store.visibility.rules import (
    ACCEPT_PARAMETER_ONLY_ON_CHANNEL,
    HIDDEN_PARAMETERS,
    IGNORE_DEVICES_FOR_DATA_POINT_EVENTS_LOWER,
    IGNORE_PARAMETERS_BY_DEVICE_LOWER,
    IGNORED_PARAMETERS,
    RELEVANT_MASTER_PARAMSETS_BY_CHANNEL,
    RELEVANT_MASTER_PARAMSETS_BY_DEVICE,
    UN_IGNORE_PARAMETERS_BY_MODEL_LOWER,
    ChannelNo,
    ModelName,
    ParameterName,
    parameter_is_wildcard_ignored,
)
from aiohomematic.support import element_matches_key

if TYPE_CHECKING:
    from aiohomematic.interfaces.central import ConfigProviderProtocol
    from aiohomematic.interfaces.model import ChannelProtocol

_LOGGER: Final = logging.getLogger(__name__)


# =============================================================================
# Typed Cache Keys
# =============================================================================


class IgnoreCacheKey(NamedTuple):
    """Cache key for parameter_is_ignored lookups."""

    model: ModelName
    channel_no: ChannelNo
    paramset_key: ParamsetKey
    parameter: ParameterName


class UnIgnoreCacheKey(NamedTuple):
    """Cache key for parameter_is_un_ignored lookups."""

    model: ModelName
    channel_no: ChannelNo
    paramset_key: ParamsetKey
    parameter: ParameterName
    custom_only: bool


# =============================================================================
# Rule Container Classes
# =============================================================================


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


# =============================================================================
# Cached Helper Functions
# =============================================================================


@cache
def _get_parameters_for_model_prefix(*, model_prefix: str | None) -> frozenset[ParameterName] | None:
    """Return un-ignore parameters for a model by prefix match."""
    if model_prefix is None:
        return None

    for model, parameters in UN_IGNORE_PARAMETERS_BY_MODEL_LOWER.items():
        if model.startswith(model_prefix):
            return parameters
    return None


# =============================================================================
# Parameter Visibility Cache
# =============================================================================


class ParameterVisibilityCache(ParameterVisibilityProviderProtocol):
    """
    Cache for parameter visibility decisions.

    Centralizes rules that determine whether a data point parameter is created,
    ignored, un-ignored, or merely hidden for UI purposes. Combines static rules
    (per-model/per-channel) with dynamic user-provided overrides and memoizes
    decisions per (model/channel/paramset/parameter) to avoid repeated computations.
    """

    __slots__ = (
        "_config_provider",
        "_custom_un_ignore_rules",
        "_custom_un_ignore_values_parameters",
        "_device_un_ignore_rules",
        "_ignore_custom_device_definition_models",
        "_param_ignored_cache",
        "_param_un_ignored_cache",
        "_raw_un_ignores",
        "_relevant_master_channels",
        "_relevant_prefix_cache",
        "_required_parameters",
        "_storage_directory",
        "_un_ignore_prefix_cache",
    )

    def __init__(
        self,
        *,
        config_provider: ConfigProviderProtocol,
    ) -> None:
        """Initialize the parameter visibility cache."""
        self._config_provider: Final = config_provider
        self._storage_directory: Final = config_provider.config.storage_directory
        self._required_parameters: Final = get_required_parameters()
        self._raw_un_ignores: Final[frozenset[str]] = config_provider.config.un_ignore_list or frozenset()
        self._ignore_custom_device_definition_models: Final[frozenset[ModelName]] = (
            config_provider.config.ignore_custom_device_definition_models
        )

        # Simple un-ignore: parameter names that apply to all VALUES paramsets
        self._custom_un_ignore_values_parameters: Final[set[ParameterName]] = set()

        # Complex un-ignore: model -> channel/paramset/parameter rules
        self._custom_un_ignore_rules: Final[ModelRules] = ModelRules()

        # Device-specific un-ignore rules from RELEVANT_MASTER_PARAMSETS_BY_DEVICE
        self._device_un_ignore_rules: Final[ModelRules] = ModelRules()

        # Channels that need MASTER paramset fetching
        self._relevant_master_channels: Final[dict[ModelName, set[ChannelNo]]] = {}

        # Prefix resolution caches
        self._un_ignore_prefix_cache: dict[ModelName, str | None] = {}
        self._relevant_prefix_cache: dict[ModelName, str | None] = {}

        # Per-instance memoization caches
        self._param_ignored_cache: dict[IgnoreCacheKey, bool] = {}
        self._param_un_ignored_cache: dict[UnIgnoreCacheKey, bool] = {}

        self._init()

    def clear_memoization_caches(self) -> None:
        """Clear the per-instance memoization caches to free memory."""
        self._param_ignored_cache.clear()
        self._param_un_ignored_cache.clear()

    def invalidate_all_caches(self) -> None:
        """Invalidate all caches including prefix resolution caches."""
        self.clear_memoization_caches()
        self._un_ignore_prefix_cache.clear()
        self._relevant_prefix_cache.clear()

    def is_relevant_paramset(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
    ) -> bool:
        """
        Return if a paramset is relevant.

        Required to load MASTER paramsets, which are not initialized by default.
        """
        if paramset_key == ParamsetKey.VALUES:
            return True

        if paramset_key == ParamsetKey.MASTER:
            if channel.no in RELEVANT_MASTER_PARAMSETS_BY_CHANNEL:
                return True

            model_l = channel.device.model.lower()
            dt_short_key = self._resolve_prefix_key(
                model_l=model_l,
                models=self._relevant_master_channels.keys(),
                cache_dict=self._relevant_prefix_cache,
            )
            if dt_short_key is not None:
                return channel.no in self._relevant_master_channels.get(dt_short_key, set())

        return False

    def model_is_ignored(self, *, model: ModelName) -> bool:
        """Check if a model should be ignored for custom data points."""
        return element_matches_key(
            search_elements=self._ignore_custom_device_definition_models,
            compare_with=model,
        )

    def parameter_is_hidden(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
    ) -> bool:
        """
        Return if parameter should be hidden.

        Hidden parameters are created but not displayed by default.
        Returns False if the parameter is on an un-ignore list.
        """
        return parameter in HIDDEN_PARAMETERS and not self._parameter_is_un_ignored(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    def parameter_is_ignored(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
    ) -> bool:
        """Check if parameter should be ignored (not created as data point)."""
        model_l = channel.device.model.lower()

        if (cache_key := IgnoreCacheKey(model_l, channel.no, paramset_key, parameter)) in self._param_ignored_cache:
            return self._param_ignored_cache[cache_key]

        result = self._check_parameter_is_ignored(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
            model_l=model_l,
        )
        self._param_ignored_cache[cache_key] = result
        return result

    def parameter_is_un_ignored(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
        custom_only: bool = False,
    ) -> bool:
        """
        Return if parameter is on an un-ignore list.

        Includes both device-specific rules from RELEVANT_MASTER_PARAMSETS_BY_DEVICE
        and custom user-provided un-ignore rules.
        """
        if not custom_only:
            model_l = channel.device.model.lower()
            dt_short_key = self._resolve_prefix_key(
                model_l=model_l,
                models=self._device_un_ignore_rules.get_models(),
                cache_dict=self._un_ignore_prefix_cache,
            )

            if dt_short_key is not None and self._device_un_ignore_rules.contains(
                model=dt_short_key,
                channel_no=channel.no,
                paramset_key=paramset_key,
                parameter=parameter,
            ):
                return True

        return self._parameter_is_un_ignored(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
            custom_only=custom_only,
        )

    def should_skip_parameter(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
        parameter_is_un_ignored: bool,
    ) -> bool:
        """Determine if a parameter should be skipped during data point creation."""
        if self.parameter_is_ignored(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            _LOGGER.debug(
                "SHOULD_SKIP_PARAMETER: Ignoring parameter: %s [%s]",
                parameter,
                channel.address,
            )
            return True

        if (
            paramset_key == ParamsetKey.MASTER
            and (parameters := RELEVANT_MASTER_PARAMSETS_BY_CHANNEL.get(channel.no)) is not None
            and parameter in parameters
        ):
            return False

        return paramset_key == ParamsetKey.MASTER and not parameter_is_un_ignored

    def _check_master_parameter_is_ignored(
        self,
        *,
        channel: ChannelProtocol,
        parameter: ParameterName,
        model_l: ModelName,
    ) -> bool:
        """Check if a MASTER parameter should be ignored."""
        # Check channel-level relevance
        if (parameters := RELEVANT_MASTER_PARAMSETS_BY_CHANNEL.get(channel.no)) is not None and parameter in parameters:
            return False

        # Check custom un-ignore rules
        if self._custom_un_ignore_rules.contains(
            model=model_l,
            channel_no=channel.no,
            paramset_key=ParamsetKey.MASTER,
            parameter=parameter,
        ):
            return False

        # Check device-specific rules
        dt_short_key = self._resolve_prefix_key(
            model_l=model_l,
            models=self._device_un_ignore_rules.get_models(),
            cache_dict=self._un_ignore_prefix_cache,
        )

        return dt_short_key is not None and not self._device_un_ignore_rules.contains(
            model=dt_short_key,
            channel_no=channel.no,
            paramset_key=ParamsetKey.MASTER,
            parameter=parameter,
        )

    def _check_parameter_is_ignored(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
        model_l: ModelName,
    ) -> bool:
        """Check if a parameter is ignored based on paramset type."""
        if paramset_key == ParamsetKey.VALUES:
            return self._check_values_parameter_is_ignored(
                channel=channel,
                parameter=parameter,
                model_l=model_l,
            )

        if paramset_key == ParamsetKey.MASTER:
            return self._check_master_parameter_is_ignored(
                channel=channel,
                parameter=parameter,
                model_l=model_l,
            )

        return False

    def _check_parameter_is_un_ignored(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
        model_l: ModelName,
        custom_only: bool,
    ) -> bool:
        """Check if a parameter matches any un-ignore rule."""
        # Build search matrix for wildcard matching
        search_patterns: tuple[tuple[ModelName, UnIgnoreChannelNo], ...]
        if paramset_key == ParamsetKey.VALUES:
            search_patterns = (
                (model_l, channel.no),
                (model_l, UN_IGNORE_WILDCARD),
                (UN_IGNORE_WILDCARD, channel.no),
                (UN_IGNORE_WILDCARD, UN_IGNORE_WILDCARD),
            )
        else:
            search_patterns = ((model_l, channel.no),)

        # Check custom rules
        for ml, cno in search_patterns:
            if self._custom_un_ignore_rules.contains(
                model=ml,
                channel_no=cno,
                paramset_key=paramset_key,
                parameter=parameter,
            ):
                return True

        # Check predefined un-ignore parameters
        if not custom_only:
            un_ignore_parameters = _get_parameters_for_model_prefix(model_prefix=model_l)
            if un_ignore_parameters and parameter in un_ignore_parameters:
                return True

        return False

    def _check_values_parameter_is_ignored(
        self,
        *,
        channel: ChannelProtocol,
        parameter: ParameterName,
        model_l: ModelName,
    ) -> bool:
        """Check if a VALUES parameter should be ignored."""
        # Check if un-ignored first
        if self.parameter_is_un_ignored(
            channel=channel,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        ):
            return False

        # Check static ignore lists
        if (
            parameter in IGNORED_PARAMETERS or parameter_is_wildcard_ignored(parameter=parameter)
        ) and parameter not in self._required_parameters:
            return True

        # Check device-specific ignore lists
        if hms.element_matches_key(
            search_elements=IGNORE_PARAMETERS_BY_DEVICE_LOWER.get(parameter, []),
            compare_with=model_l,
        ):
            return True

        # Check event suppression
        if hms.element_matches_key(
            search_elements=IGNORE_DEVICES_FOR_DATA_POINT_EVENTS_LOWER,
            compare_with=parameter,
            search_key=model_l,
            do_right_wildcard_search=False,
        ):
            return True

        # Check channel-specific parameter rules
        accept_channel = ACCEPT_PARAMETER_ONLY_ON_CHANNEL.get(parameter)
        return accept_channel is not None and accept_channel != channel.no

    def _init(self) -> None:
        """Initialize the cache with static and configured rules."""
        # Load device-specific rules from RELEVANT_MASTER_PARAMSETS_BY_DEVICE
        for model, (channel_nos, parameters) in RELEVANT_MASTER_PARAMSETS_BY_DEVICE.items():
            model_l = model.lower()

            effective_channels = channel_nos if channel_nos else frozenset({None})
            for channel_no in effective_channels:
                # Track relevant channels for MASTER paramset fetching
                if model_l not in self._relevant_master_channels:
                    self._relevant_master_channels[model_l] = set()
                self._relevant_master_channels[model_l].add(channel_no)

                # Add un-ignore rules
                self._device_un_ignore_rules.update_parameters(
                    model=model_l,
                    channel_no=channel_no,
                    paramset_key=ParamsetKey.MASTER,
                    parameters=parameters,
                )

        # Process user-provided un-ignore entries
        self._process_un_ignore_entries(lines=self._raw_un_ignores)

    def _parameter_is_un_ignored(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
        custom_only: bool = False,
    ) -> bool:
        """
        Check if parameter is on a custom un-ignore list.

        This can be either the user's un-ignore configuration or the
        predefined UN_IGNORE_PARAMETERS_BY_DEVICE.
        """
        # Fast path: simple VALUES parameter un-ignore
        if paramset_key == ParamsetKey.VALUES and parameter in self._custom_un_ignore_values_parameters:
            return True

        model_l = channel.device.model.lower()
        cache_key = UnIgnoreCacheKey(model_l, channel.no, paramset_key, parameter, custom_only)

        if cache_key in self._param_un_ignored_cache:
            return self._param_un_ignored_cache[cache_key]

        result = self._check_parameter_is_un_ignored(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
            model_l=model_l,
            custom_only=custom_only,
        )
        self._param_un_ignored_cache[cache_key] = result
        return result

    def _process_complex_un_ignore_entry(self, *, parsed: ParsedUnIgnoreLine) -> None:
        """Process a complex un-ignore entry."""
        entry = parsed.entry
        assert entry is not None  # noqa: S101

        # Track MASTER channels for paramset fetching
        if entry.paramset_key == ParamsetKey.MASTER and (isinstance(entry.channel_no, int) or entry.channel_no is None):
            if entry.model not in self._relevant_master_channels:
                self._relevant_master_channels[entry.model] = set()
            self._relevant_master_channels[entry.model].add(entry.channel_no)

        self._custom_un_ignore_rules.add_parameter(
            model=entry.model,
            channel_no=entry.channel_no,
            paramset_key=entry.paramset_key,
            parameter=entry.parameter,
        )

    def _process_un_ignore_entries(self, *, lines: Iterable[str]) -> None:
        """Process un-ignore configuration entries into the cache."""
        for line in lines:
            if not line.strip():
                continue

            parsed = parse_un_ignore_line(line=line)

            if parsed.is_error:
                _LOGGER.error(  # i18n-log: ignore
                    "PROCESS_UN_IGNORE_ENTRY failed: %s",
                    parsed.error,
                )
            elif parsed.is_simple:
                self._custom_un_ignore_values_parameters.add(parsed.simple_parameter)  # type: ignore[arg-type]
            elif parsed.is_complex:
                self._process_complex_un_ignore_entry(parsed=parsed)

    def _resolve_prefix_key(
        self,
        *,
        model_l: ModelName,
        models: Iterable[ModelName],
        cache_dict: dict[ModelName, str | None],
    ) -> str | None:
        """Resolve and memoize the first model key that is a prefix of model_l."""
        if model_l in cache_dict:
            return cache_dict[model_l]

        dt_short_key = next((k for k in models if model_l.startswith(k)), None)
        cache_dict[model_l] = dt_short_key
        return dt_short_key


# =============================================================================
# Validation Helper
# =============================================================================


def check_ignore_parameters_is_clean() -> bool:
    """Check if any required parameter is incorrectly in the ignored parameters list."""
    un_ignore_parameters_by_device: list[str] = []
    for params in UN_IGNORE_PARAMETERS_BY_MODEL_LOWER.values():
        un_ignore_parameters_by_device.extend(params)

    required = get_required_parameters()
    conflicting = [
        parameter
        for parameter in required
        if (parameter in IGNORED_PARAMETERS or parameter_is_wildcard_ignored(parameter=parameter))
        and parameter not in un_ignore_parameters_by_device
    ]

    return len(conflicting) == 0
