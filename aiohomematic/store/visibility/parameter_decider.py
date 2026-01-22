# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Parameter-level visibility decisions for the visibility system.

This module provides the ParameterVisibilityDecider class which handles
parameter-level ignore/hidden/un-ignore decisions.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic import support as hms
from aiohomematic.const import UN_IGNORE_WILDCARD, ParamsetKey
from aiohomematic.store.visibility.rule_containers import ModelRules
from aiohomematic.store.visibility.rules import (
    ACCEPT_PARAMETER_ONLY_ON_CHANNEL,
    HIDDEN_PARAMETERS,
    IGNORE_DEVICES_FOR_DATA_POINT_EVENTS_LOWER,
    IGNORE_PARAMETERS_BY_DEVICE_LOWER,
    IGNORED_PARAMETERS,
    RELEVANT_MASTER_PARAMSETS_BY_CHANNEL,
    UN_IGNORE_PARAMETERS_BY_MODEL_LOWER,
    parameter_is_wildcard_ignored,
)
from aiohomematic.store.visibility.types import IgnoreCacheKey, ModelName, ParameterName, UnIgnoreCacheKey

if TYPE_CHECKING:
    from aiohomematic.interfaces import ChannelProtocol
    from aiohomematic.store.visibility.parser import UnIgnoreChannelNo

_LOGGER: Final = logging.getLogger(__name__)


@cache
def _get_parameters_for_model_prefix(*, model_prefix: str | None) -> frozenset[ParameterName] | None:
    """Return un-ignore parameters for a model by prefix match."""
    if model_prefix is None:
        return None

    for model, parameters in UN_IGNORE_PARAMETERS_BY_MODEL_LOWER.items():
        if model.startswith(model_prefix):
            return parameters
    return None


class ParameterVisibilityDecider:
    """
    Determine visibility for individual parameters.

    Responsibility: Parameter-level ignore/hidden decisions.

    This class handles:
    - Checking if a parameter should be ignored (not created)
    - Checking if a parameter should be hidden (created but not displayed)
    - Checking if a parameter is on an un-ignore list
    """

    __slots__ = (
        "_custom_un_ignore_rules",
        "_custom_un_ignore_values_parameters",
        "_device_un_ignore_rules",
        "_required_parameters",
        "_un_ignore_prefix_cache",
        "_param_ignored_cache",
        "_param_un_ignored_cache",
    )

    def __init__(
        self,
        *,
        custom_un_ignore_rules: ModelRules,
        custom_un_ignore_values_parameters: frozenset[ParameterName],
        device_un_ignore_rules: ModelRules,
        required_parameters: frozenset[ParameterName],
    ) -> None:
        """
        Initialize with parsed un-ignore rules.

        Args:
            custom_un_ignore_rules: User-provided model-specific un-ignore rules.
            custom_un_ignore_values_parameters: Simple parameter names for VALUES paramsets.
            device_un_ignore_rules: Device-specific rules from RELEVANT_MASTER_PARAMSETS_BY_DEVICE.
            required_parameters: Parameters that must never be ignored.

        """
        self._custom_un_ignore_rules: Final = custom_un_ignore_rules
        self._custom_un_ignore_values_parameters: Final = custom_un_ignore_values_parameters
        self._device_un_ignore_rules: Final = device_un_ignore_rules
        self._required_parameters: Final = required_parameters
        self._un_ignore_prefix_cache: dict[ModelName, str | None] = {}
        self._param_ignored_cache: dict[IgnoreCacheKey, bool] = {}
        self._param_un_ignored_cache: dict[UnIgnoreCacheKey, bool] = {}

    @property
    def size(self) -> int:
        """Return total size of memoization caches."""
        return len(self._param_ignored_cache) + len(self._param_un_ignored_cache)

    def clear_memoization_caches(self) -> None:
        """Clear per-instance memoization caches."""
        self._param_ignored_cache.clear()
        self._param_un_ignored_cache.clear()

    def invalidate_prefix_cache(self) -> None:
        """Invalidate the prefix resolution cache."""
        self._un_ignore_prefix_cache.clear()

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

        Args:
            channel: The channel containing the parameter.
            paramset_key: The paramset key.
            parameter: The parameter name.

        Returns:
            True if the parameter should be hidden.

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
        """
        Check if parameter should be ignored (not created as data point).

        Args:
            channel: The channel containing the parameter.
            paramset_key: The paramset key (VALUES or MASTER).
            parameter: The parameter name.

        Returns:
            True if the parameter should be ignored.

        """
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

        Args:
            channel: The channel containing the parameter.
            paramset_key: The paramset key.
            parameter: The parameter name.
            custom_only: If True, only check custom rules.

        Returns:
            True if the parameter is on an un-ignore list.

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
        """
        Determine if a parameter should be skipped during data point creation.

        Args:
            channel: The channel containing the parameter.
            paramset_key: The paramset key.
            parameter: The parameter name.
            parameter_is_un_ignored: Whether the parameter is on an un-ignore list.

        Returns:
            True if the parameter should be skipped.

        """
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
