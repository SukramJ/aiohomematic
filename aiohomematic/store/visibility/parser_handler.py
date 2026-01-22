# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Un-ignore rule parsing for the visibility system.

This module provides the UnIgnoreRuleParser class which handles parsing of
un-ignore configuration entries and initialization of rule structures.
"""

from __future__ import annotations

from collections.abc import Iterable
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.const import ParamsetKey
from aiohomematic.store.visibility.parser import parse_un_ignore_line
from aiohomematic.store.visibility.rule_containers import ModelRules
from aiohomematic.store.visibility.rules import RELEVANT_MASTER_PARAMSETS_BY_DEVICE
from aiohomematic.store.visibility.types import ChannelNo, ModelName, ParameterName, ParsedUnIgnoreRules

if TYPE_CHECKING:
    from aiohomematic.interfaces import ConfigProviderProtocol

_LOGGER: Final = logging.getLogger(__name__)


class UnIgnoreRuleParser:
    """
    Parse configuration entries into rule structures.

    Responsibility: Rule parsing and loading from configuration.

    This class handles:
    - Parsing user-provided un-ignore configuration entries
    - Loading device-specific rules from RELEVANT_MASTER_PARAMSETS_BY_DEVICE
    - Creating the rule structures used by other visibility components
    """

    __slots__ = ("_raw_un_ignores", "_config_provider")

    def __init__(
        self,
        *,
        raw_un_ignores: frozenset[str],
        config_provider: ConfigProviderProtocol,
    ) -> None:
        """
        Initialize parser with raw configuration.

        Args:
            raw_un_ignores: Raw un-ignore entries from user configuration.
            config_provider: Configuration provider for access to settings.

        """
        self._raw_un_ignores: Final = raw_un_ignores
        self._config_provider: Final = config_provider

    def parse_entries(self) -> ParsedUnIgnoreRules:
        """
        Parse all un-ignore entries.

        Returns:
            ParsedUnIgnoreRules with all parsed rule structures.

        """
        # Parse static device rules
        device_rules, relevant_master_channels = self._parse_static_device_rules()

        # Parse user config entries
        custom_rules, custom_values_params = self._parse_user_config_entries(
            lines=self._raw_un_ignores,
            relevant_master_channels=relevant_master_channels,
        )

        return ParsedUnIgnoreRules(
            custom_un_ignore_rules=custom_rules,
            custom_un_ignore_values_parameters=frozenset(custom_values_params),
            device_un_ignore_rules=device_rules,
            relevant_master_channels=relevant_master_channels,
        )

    def _parse_static_device_rules(self) -> tuple[ModelRules, dict[ModelName, set[ChannelNo]]]:
        """
        Parse RELEVANT_MASTER_PARAMSETS_BY_DEVICE static rules.

        Returns:
            Tuple of (device_un_ignore_rules, relevant_master_channels).

        """
        device_rules = ModelRules()
        relevant_master_channels: dict[ModelName, set[ChannelNo]] = {}

        for model, (channel_nos, parameters) in RELEVANT_MASTER_PARAMSETS_BY_DEVICE.items():
            model_l = model.lower()

            effective_channels = channel_nos if channel_nos else frozenset({None})
            for channel_no in effective_channels:
                # Track relevant channels for MASTER paramset fetching
                if model_l not in relevant_master_channels:
                    relevant_master_channels[model_l] = set()
                relevant_master_channels[model_l].add(channel_no)

                # Add un-ignore rules
                device_rules.update_parameters(
                    model=model_l,
                    channel_no=channel_no,
                    paramset_key=ParamsetKey.MASTER,
                    parameters=parameters,
                )

        return device_rules, relevant_master_channels

    def _parse_user_config_entries(
        self,
        *,
        lines: Iterable[str],
        relevant_master_channels: dict[ModelName, set[ChannelNo]],
    ) -> tuple[ModelRules, set[ParameterName]]:
        """
        Parse user-provided un-ignore entries.

        Args:
            lines: Raw un-ignore configuration lines.
            relevant_master_channels: Dict to update with MASTER channel info.

        Returns:
            Tuple of (custom_un_ignore_rules, custom_values_parameters).

        """
        custom_rules = ModelRules()
        custom_values_params: set[ParameterName] = set()

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
                custom_values_params.add(parsed.simple_parameter)  # type: ignore[arg-type]
            elif parsed.is_complex:
                entry = parsed.entry
                assert entry is not None

                # Track MASTER channels for paramset fetching
                if entry.paramset_key == ParamsetKey.MASTER and (
                    isinstance(entry.channel_no, int) or entry.channel_no is None
                ):
                    if entry.model not in relevant_master_channels:
                        relevant_master_channels[entry.model] = set()
                    relevant_master_channels[entry.model].add(entry.channel_no)

                custom_rules.add_parameter(
                    model=entry.model,
                    channel_no=entry.channel_no,
                    paramset_key=entry.paramset_key,
                    parameter=entry.parameter,
                )

        return custom_rules, custom_values_params
