# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Model-level visibility validation for the visibility system.

This module provides the ModelVisibilityValidator class which handles
model-level visibility decisions like relevant paramsets and model ignoring.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Final

from aiohomematic.const import ParamsetKey
from aiohomematic.store.visibility.rules import RELEVANT_MASTER_PARAMSETS_BY_CHANNEL
from aiohomematic.store.visibility.types import ChannelNo, ModelName
from aiohomematic.support import element_matches_key

if TYPE_CHECKING:
    from aiohomematic.interfaces import ChannelProtocol


class ModelVisibilityValidator:
    """
    Validate visibility at the device model level.

    Responsibility: Model-level filtering decisions.

    This class handles:
    - Determining if a paramset is relevant for a channel
    - Checking if a model should be ignored for custom data points
    """

    __slots__ = (
        "_ignore_custom_device_definition_models",
        "_relevant_master_channels",
        "_relevant_prefix_cache",
    )

    def __init__(
        self,
        *,
        ignore_custom_device_definition_models: frozenset[ModelName],
        relevant_master_channels: dict[ModelName, set[ChannelNo]],
    ) -> None:
        """
        Initialize with model visibility rules.

        Args:
            ignore_custom_device_definition_models: Models to ignore for custom data points.
            relevant_master_channels: Channels requiring MASTER paramset fetching.

        """
        self._ignore_custom_device_definition_models: Final = ignore_custom_device_definition_models
        self._relevant_master_channels: Final = relevant_master_channels
        self._relevant_prefix_cache: dict[ModelName, str | None] = {}

    def invalidate_prefix_cache(self) -> None:
        """Clear the prefix resolution cache."""
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

        Args:
            channel: The channel to check.
            paramset_key: The paramset key to check.

        Returns:
            True if the paramset is relevant and should be loaded.

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
        """
        Check if a model should be ignored for custom data points.

        Args:
            model: The model name to check.

        Returns:
            True if the model should be ignored.

        """
        return element_matches_key(
            search_elements=self._ignore_custom_device_definition_models,
            compare_with=model,
        )

    def _resolve_prefix_key(
        self,
        *,
        model_l: ModelName,
        models: Iterable[ModelName],
        cache_dict: dict[ModelName, str | None],
    ) -> str | None:
        """
        Resolve and memoize the first model key that is a prefix of model_l.

        Args:
            model_l: The lowercase model name to match.
            models: The model keys to search.
            cache_dict: Cache dictionary for memoization.

        Returns:
            The matching prefix key or None.

        """
        if model_l in cache_dict:
            return cache_dict[model_l]

        dt_short_key = next((k for k in models if model_l.startswith(k)), None)
        cache_dict[model_l] = dt_short_key
        return dt_short_key
