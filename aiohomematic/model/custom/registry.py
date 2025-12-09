# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Device profile registry for custom data point configurations.

This module provides a centralized registry for mapping device models to their
custom data point configurations, replacing the distributed ALL_DEVICES pattern.

Key types:
- DeviceConfig: Configuration for a specific device model
- ExtendedDeviceConfig: Extended configuration with additional fields
- DeviceProfileRegistry: Central registry class for device profile configurations

Example usage:
    from aiohomematic.model.custom.registry import DeviceProfileRegistry, DeviceConfig

    # Register a device
    DeviceProfileRegistry.register(
        category=DataPointCategory.CLIMATE,
        models=("HmIP-BWTH", "HmIP-STH"),
        data_point_class=CustomDpIpThermostat,
        profile_type=DeviceProfile.IP_THERMOSTAT,
        schedule_channel_no=1,
    )

    # Get configurations for a model
    configs = DeviceProfileRegistry.get_configs(model="HmIP-BWTH")
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from aiohomematic.const import DataPointCategory, DeviceProfile, Field, Parameter

if TYPE_CHECKING:
    from aiohomematic.model.custom.data_point import CustomDataPoint

__all__ = [
    "DeviceConfig",
    "DeviceProfileRegistry",
    "ExtendedDeviceConfig",
]


@dataclass(frozen=True, kw_only=True, slots=True)
class ExtendedDeviceConfig:
    """Extended configuration for custom data point creation."""

    fixed_channel_fields: Mapping[int, Mapping[Field, Parameter]] | None = None
    additional_data_points: Mapping[int | tuple[int, ...], tuple[Parameter, ...]] | None = None

    @property
    def required_parameters(self) -> tuple[Parameter, ...]:
        """Return required parameters from extended config."""
        required_parameters: list[Parameter] = []
        if fixed_channels := self.fixed_channel_fields:
            for mapping in fixed_channels.values():
                required_parameters.extend(mapping.values())

        if additional_dps := self.additional_data_points:
            for parameters in additional_dps.values():
                required_parameters.extend(parameters)

        return tuple(required_parameters)


@dataclass(frozen=True, kw_only=True, slots=True)
class DeviceConfig:
    """Configuration for mapping a device model to its custom data point implementation."""

    data_point_class: type[CustomDataPoint]
    profile_type: DeviceProfile
    channels: tuple[int | None, ...] = (1,)
    extended: ExtendedDeviceConfig | None = None
    schedule_channel_no: int | None = None


class DeviceProfileRegistry:
    """Central registry for device profile configurations."""

    _configs: ClassVar[dict[DataPointCategory, dict[str, DeviceConfig | tuple[DeviceConfig, ...]]]] = {}
    _blacklist: ClassVar[set[str]] = set()

    @classmethod
    def blacklist(cls, *models: str) -> None:
        """Blacklist device models."""
        cls._blacklist.update(m.lower().replace("hb-", "hm-") for m in models)

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations. Primarily for testing."""
        cls._configs.clear()
        cls._blacklist.clear()

    @classmethod
    def get_all_configs(
        cls,
        *,
        category: DataPointCategory,
    ) -> Mapping[str, DeviceConfig | tuple[DeviceConfig, ...]]:
        """Return all configurations for a category."""
        return cls._configs.get(category, {})

    @classmethod
    def get_all_extended_configs(cls) -> tuple[ExtendedDeviceConfig, ...]:
        """Return all extended configurations from all categories."""
        extended_configs: list[ExtendedDeviceConfig] = []
        for category_configs in cls._configs.values():
            for device_config in category_configs.values():
                if isinstance(device_config, tuple):
                    extended_configs.extend(cfg.extended for cfg in device_config if cfg.extended)
                elif device_config.extended:
                    extended_configs.append(device_config.extended)
        return tuple(extended_configs)

    @classmethod
    def get_blacklist(cls) -> tuple[str, ...]:
        """Return current blacklist entries."""
        return tuple(sorted(cls._blacklist))

    @classmethod
    def get_configs(
        cls,
        *,
        model: str,
        category: DataPointCategory | None = None,
    ) -> tuple[DeviceConfig, ...]:
        """
        Return device configurations for a model.

        Model matching algorithm (hierarchical, first-match wins):
            1. Normalize model name (lowercase, replace "hb-" with "hm-")
            2. Check blacklist - return empty if blacklisted
            3. For each category, try matching in order:
               a. Exact match: model == registered_key
               b. Prefix match: model.startswith(registered_key)

        Why prefix matching?
            Homematic devices often have variants (e.g., "HmIP-BWTH-1" and "HmIP-BWTH-2")
            that share the same profile. Prefix matching allows registering "hmip-bwth"
            once to cover all variants, reducing duplication.

        Model normalization:
            - Lowercase: Makes matching case-insensitive
            - "hb-" → "hm-": HomeBrew devices use "HB-" prefix but behave like "HM-" devices

        Result aggregation:
            A model can match multiple categories (e.g., a thermostat might have both
            CLIMATE and SENSOR entities). Results from all matching categories are
            combined into a single tuple.

        Storage format:
            Registry entries can be either:
            - Single DeviceConfig: For simple devices
            - Tuple of DeviceConfigs: For devices with multiple entity types
              (e.g., lock + button_lock on same device)
        """
        # Normalize model name for consistent matching
        normalized = model.lower().replace("hb-", "hm-")

        # Check blacklist first (fast path for excluded devices)
        if cls.is_blacklisted(model=model):
            return ()

        configs: list[DeviceConfig] = []

        # Search specified category or all categories
        categories = [category] if category else list(cls._configs.keys())

        for cat in categories:
            if cat not in cls._configs:
                continue

            # Priority 1: Exact match (most specific)
            if result := cls._configs[cat].get(normalized):
                if isinstance(result, tuple):
                    configs.extend(result)
                else:
                    configs.append(result)
                continue  # Found exact match, skip prefix matching for this category

            # Priority 2: Prefix match (for device variants)
            for model_key, result in cls._configs[cat].items():
                if normalized.startswith(model_key):
                    if isinstance(result, tuple):
                        configs.extend(result)
                    else:
                        configs.append(result)
                    break  # First prefix match wins, stop searching this category

        return tuple(configs)

    @classmethod
    def is_blacklisted(cls, *, model: str) -> bool:
        """Check if a model is blacklisted."""
        normalized = model.lower().replace("hb-", "hm-")
        return any(normalized.startswith(bl) for bl in cls._blacklist)

    @classmethod
    def register(
        cls,
        *,
        category: DataPointCategory,
        models: str | tuple[str, ...],
        data_point_class: type[CustomDataPoint],
        profile_type: DeviceProfile,
        channels: tuple[int | None, ...] = (1,),
        extended: ExtendedDeviceConfig | None = None,
        schedule_channel_no: int | None = None,
    ) -> None:
        """Register a device configuration."""
        config = DeviceConfig(
            data_point_class=data_point_class,
            profile_type=profile_type,
            channels=channels,
            extended=extended,
            schedule_channel_no=schedule_channel_no,
        )

        models_tuple = (models,) if isinstance(models, str) else models

        if category not in cls._configs:
            cls._configs[category] = {}

        for model in models_tuple:
            normalized = model.lower().replace("hb-", "hm-")
            cls._configs[category][normalized] = config

    @classmethod
    def register_multiple(
        cls,
        *,
        category: DataPointCategory,
        models: str | tuple[str, ...],
        configs: tuple[DeviceConfig, ...],
    ) -> None:
        """Register multiple configurations for the same model(s)."""
        models_tuple = (models,) if isinstance(models, str) else models

        if category not in cls._configs:
            cls._configs[category] = {}

        for model in models_tuple:
            normalized = model.lower().replace("hb-", "hm-")
            cls._configs[category][normalized] = configs
