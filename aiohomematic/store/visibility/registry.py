# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Parameter visibility registry for Homematic data points.

This module provides the ParameterVisibilityRegistry class which determines whether
parameters should be created, shown, hidden, ignored, or un-ignored for channels
and devices. It consolidates rules from multiple sources and memoizes decisions
to avoid repeated computations.

Architecture
------------
The visibility system is organized into focused components:

- **types.py**: Shared type aliases and cache keys
- **parser_handler.py**: UnIgnoreRuleParser for parsing configuration
- **model_validator.py**: ModelVisibilityValidator for model-level decisions
- **parameter_decider.py**: ParameterVisibilityDecider for parameter-level decisions
- **registry.py**: ParameterVisibilityRegistry facade that combines all components

The registry acts as a facade, delegating to the specialized components while
maintaining backward compatibility with the existing public API.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.const import ParamsetKey
from aiohomematic.interfaces import ParameterVisibilityProviderProtocol
from aiohomematic.model.custom import get_required_parameters
from aiohomematic.store.visibility.model_validator import ModelVisibilityValidator
from aiohomematic.store.visibility.parameter_decider import ParameterVisibilityDecider
from aiohomematic.store.visibility.parser_handler import UnIgnoreRuleParser

# Re-export rule containers for backward compatibility
from aiohomematic.store.visibility.rule_containers import ChannelParamsetRules, ModelRules  # noqa: F401
from aiohomematic.store.visibility.rules import (
    IGNORED_PARAMETERS,
    UN_IGNORE_PARAMETERS_BY_MODEL_LOWER,
    parameter_is_wildcard_ignored,
)

# Re-export for backward compatibility and use by other modules
from aiohomematic.store.visibility.types import ChannelNo, ModelName, ParameterName  # noqa: F401

if TYPE_CHECKING:
    from aiohomematic.interfaces import ChannelProtocol, ConfigProviderProtocol, EventBusProviderProtocol

_LOGGER: Final = logging.getLogger(__name__)


class ParameterVisibilityRegistry(ParameterVisibilityProviderProtocol):
    """
    Registry for parameter visibility decisions (facade pattern).

    Centralizes rules that determine whether a data point parameter is created,
    ignored, un-ignored, or merely hidden for UI purposes. Combines static rules
    (per-model/per-channel) with dynamic user-provided overrides and memoizes
    decisions per (model/channel/paramset/parameter) to avoid repeated computations.

    This class acts as a facade, composing specialized components:
    - UnIgnoreRuleParser: Handles initialization and rule parsing
    - ModelVisibilityValidator: Handles model-level visibility decisions
    - ParameterVisibilityDecider: Handles parameter-level decisions
    """

    __slots__ = (
        "_config_provider",
        "_model_validator",
        "_parameter_decider",
        "_storage_directory",
    )

    def __init__(
        self,
        *,
        config_provider: ConfigProviderProtocol,
        event_bus_provider: EventBusProviderProtocol | None = None,  # Kept for compatibility, unused
    ) -> None:
        """Initialize the parameter visibility registry."""
        self._config_provider: Final = config_provider
        self._storage_directory: Final = config_provider.config.storage_directory

        # Parse rules using the parser handler
        parser = UnIgnoreRuleParser(
            raw_un_ignores=config_provider.config.un_ignore_list or frozenset(),
            config_provider=config_provider,
        )
        parsed_rules = parser.parse_entries()

        # Initialize model validator
        self._model_validator: Final = ModelVisibilityValidator(
            ignore_custom_device_definition_models=(
                config_provider.config.ignore_custom_device_definition_models or frozenset()
            ),
            relevant_master_channels=parsed_rules.relevant_master_channels,
        )

        # Initialize parameter decider
        self._parameter_decider: Final = ParameterVisibilityDecider(
            custom_un_ignore_rules=parsed_rules.custom_un_ignore_rules,
            custom_un_ignore_values_parameters=parsed_rules.custom_un_ignore_values_parameters,
            device_un_ignore_rules=parsed_rules.device_un_ignore_rules,
            required_parameters=frozenset(get_required_parameters()),
        )

    @property
    def size(self) -> int:
        """Return total size of memoization caches."""
        return self._parameter_decider.size

    def clear_memoization_caches(self) -> None:
        """Clear the per-instance memoization caches to free memory."""
        self._parameter_decider.clear_memoization_caches()

    def invalidate_all_caches(self) -> None:
        """Invalidate all caches including prefix resolution caches."""
        self._parameter_decider.clear_memoization_caches()
        self._parameter_decider.invalidate_prefix_cache()
        self._model_validator.invalidate_prefix_cache()

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
        return self._model_validator.is_relevant_paramset(channel=channel, paramset_key=paramset_key)

    def model_is_ignored(self, *, model: ModelName) -> bool:
        """Check if a model should be ignored for custom data points."""
        return self._model_validator.model_is_ignored(model=model)

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
        return self._parameter_decider.parameter_is_hidden(
            channel=channel, paramset_key=paramset_key, parameter=parameter
        )

    def parameter_is_ignored(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: ParameterName,
    ) -> bool:
        """Check if parameter should be ignored (not created as data point)."""
        return self._parameter_decider.parameter_is_ignored(
            channel=channel, paramset_key=paramset_key, parameter=parameter
        )

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
        return self._parameter_decider.parameter_is_un_ignored(
            channel=channel, paramset_key=paramset_key, parameter=parameter, custom_only=custom_only
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
        return self._parameter_decider.should_skip_parameter(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_is_un_ignored=parameter_is_un_ignored,
        )


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
