# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Configuration coordinator for paramset-level device configuration.

This module provides the ConfigurationCoordinator, a high-level facade
for reading and writing device configuration (MASTER paramsets) without
requiring navigation of internal coordinator structures.

The coordinator combines paramset descriptions, device descriptions, and
client operations behind a clean, consumer-friendly interface.

Public API of this module is defined by __all__.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import inspect
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.ccu_translations import get_channel_type_translation
from aiohomematic.const import CallSource, Flag, ParameterData, ParamsetKey
from aiohomematic.exceptions import BaseHomematicException
from aiohomematic.interfaces import (
    ClientProviderProtocol,
    DeviceDescriptionProviderProtocol,
    ParamsetDescriptionProviderProtocol,
)
from aiohomematic.interfaces.central import ConfigurationFacadeProtocol
from aiohomematic.parameter_tools import (
    is_parameter_internal,
    is_parameter_visible,
    is_parameter_writable,
    validate_paramset,
)
from aiohomematic.support.address import get_device_address

if TYPE_CHECKING:
    from aiohomematic.central.device_registry import DeviceRegistry

_LOGGER: Final = logging.getLogger(__name__)

_MAINTENANCE_PARAMS: Final[frozenset[str]] = frozenset(
    {
        "UNREACH",
        "LOW_BAT",
        "RSSI_DEVICE",
        "RSSI_PEER",
        "DUTYCYCLE",
        "CONFIG_PENDING",
    }
)


@dataclass(frozen=True, slots=True)
class ConfigurableChannel:
    """A channel that has configurable paramsets."""

    address: str
    """Channel address (e.g. ``VCU3373841:1``)."""

    channel_type: str
    """Channel TYPE from the device description."""

    paramset_keys: tuple[ParamsetKey, ...]
    """Available paramset keys for this channel."""


@dataclass(frozen=True, slots=True)
class PutParamsetResult:
    """Result of a put_paramset operation."""

    success: bool
    """Whether the operation succeeded."""

    validated: bool
    """Whether validation was performed before writing."""

    validation_errors: Mapping[str, str]
    """Per-parameter validation error messages (empty on success)."""


@dataclass(frozen=True, slots=True)
class CopyParamsetResult:
    """Result of a paramset copy operation."""

    success: bool
    """Whether the copy operation succeeded."""

    validated: bool
    """Whether validation was performed before writing."""

    validation_errors: dict[str, str]
    """Per-parameter validation error messages (empty on success)."""

    parameters_copied: int
    """Number of parameters successfully copied."""

    parameters_skipped: int
    """Number of parameters skipped (not writable or missing in target)."""


@dataclass(frozen=True, slots=True)
class ConfigurableDeviceChannel:
    """Channel available for configuration with resolved labels."""

    address: str
    """Channel address (e.g. ``VCU3373841:1``)."""

    channel_type: str
    """Channel TYPE from the device description."""

    channel_type_label: str
    """Human-readable label for the channel type."""

    paramset_keys: tuple[str, ...]
    """Effective paramset keys for this channel (as string values)."""


@dataclass(frozen=True, slots=True)
class MaintenanceData:
    """Cached maintenance state from device channel 0."""

    unreach: bool | None = None
    """Whether the device is unreachable."""

    low_bat: bool | None = None
    """Whether the device battery is low."""

    rssi_device: int | None = None
    """RSSI value of the device."""

    rssi_peer: int | None = None
    """RSSI value of the peer."""

    dutycycle: bool | None = None
    """Whether duty cycle limit is reached."""

    config_pending: bool | None = None
    """Whether configuration changes are pending."""


@dataclass(frozen=True, slots=True)
class ConfigurableDevice:
    """Device with configurable channels for the configuration UI."""

    address: str
    """Device address."""

    interface: str
    """Interface name (e.g. HmIP-RF)."""

    interface_id: str
    """Interface identifier."""

    model: str
    """Device model."""

    model_description: str
    """Human-readable model description."""

    name: str
    """Device name."""

    firmware: str
    """Device firmware version."""

    channels: tuple[ConfigurableDeviceChannel, ...]
    """Configurable channels with resolved labels."""

    maintenance: MaintenanceData
    """Maintenance data from channel 0."""


class ConfigurationCoordinator(ConfigurationFacadeProtocol):
    """
    High-level facade for device configuration operations.

    Provides clean access to paramset descriptions, reading, and writing
    without exposing internal coordinator structure. Intended for consumption
    by configuration UIs, diagnostic tools, and third-party integrations.
    """

    __slots__ = (
        "_client_provider",
        "_device_description_provider",
        "_device_registry",
        "_paramset_description_provider",
    )

    def __init__(
        self,
        *,
        client_provider: ClientProviderProtocol,
        device_description_provider: DeviceDescriptionProviderProtocol,
        device_registry: DeviceRegistry,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
    ) -> None:
        """Initialize the configuration coordinator."""
        self._client_provider: Final = client_provider
        self._device_description_provider: Final = device_description_provider
        self._device_registry: Final = device_registry
        self._paramset_description_provider: Final = paramset_description_provider

    async def copy_paramset(
        self,
        *,
        source_interface_id: str,
        source_channel_address: str,
        target_interface_id: str,
        target_channel_address: str,
        paramset_key: ParamsetKey,
    ) -> tuple[CopyParamsetResult, dict[str, Any], dict[str, Any]]:
        """
        Copy writable paramset values from source to target channel.

        Return (result, old_target_values, copied_values) for change tracking.
        """
        source_values = await self.get_paramset(
            interface_id=source_interface_id,
            channel_address=source_channel_address,
            paramset_key=paramset_key,
        )

        target_descriptions = self.get_paramset_description(
            interface_id=target_interface_id,
            channel_address=target_channel_address,
            paramset_key=paramset_key,
        )

        # Filter: only parameters present in target description AND writable
        filtered_values: dict[str, Any] = {}
        skipped = 0
        for param, value in source_values.items():
            if param in target_descriptions and is_parameter_writable(parameter_data=target_descriptions[param]):
                filtered_values[param] = value
            else:
                skipped += 1

        if not filtered_values:
            return (
                CopyParamsetResult(
                    success=True,
                    validated=True,
                    validation_errors={},
                    parameters_copied=0,
                    parameters_skipped=skipped,
                ),
                {},
                {},
            )

        # Read old target values for change tracking
        try:
            old_values = await self.get_paramset(
                interface_id=target_interface_id,
                channel_address=target_channel_address,
                paramset_key=paramset_key,
            )
        except BaseHomematicException:
            old_values = {}

        result = await self.put_paramset(
            interface_id=target_interface_id,
            channel_address=target_channel_address,
            paramset_key=paramset_key,
            values=filtered_values,
            validate=True,
        )

        return (
            CopyParamsetResult(
                success=result.success,
                validated=result.validated,
                validation_errors=dict(result.validation_errors),
                parameters_copied=len(filtered_values) if result.success else 0,
                parameters_skipped=skipped,
            ),
            old_values,
            filtered_values if result.success else {},
        )

    def get_all_paramset_descriptions(
        self,
        *,
        interface_id: str,
        channel_address: str,
    ) -> Mapping[ParamsetKey, Mapping[str, ParameterData]]:
        """Return all paramset descriptions for a channel, keyed by paramset key."""
        return self._paramset_description_provider.get_channel_paramset_descriptions(
            interface_id=interface_id,
            channel_address=channel_address,
        )

    def get_configurable_channels(
        self,
        *,
        interface_id: str,
        device_address: str,
    ) -> tuple[ConfigurableChannel, ...]:
        """
        Return all channels of a device that have configurable paramsets.

        A channel is considered configurable when its device description
        lists at least one paramset key (typically MASTER and/or VALUES).

        Channels are filtered using the same rules as the CCU WebUI:
        - Channel FLAGS must have VISIBLE set
        - Channel FLAGS must not have INTERNAL set
        - WEEK_PROGRAM channels are excluded (handled by schedule cards)
        """
        device_with_channels = self._device_description_provider.get_device_with_channels(
            interface_id=interface_id,
            device_address=device_address,
        )
        channels: list[ConfigurableChannel] = []
        for address, description in sorted(device_with_channels.items()):
            # Skip WEEK_PROGRAM channels (handled by schedule cards)
            if (channel_type := description.get("TYPE", "")) == "WEEK_PROGRAM":
                continue

            # Device-level entry (no colon) and internal channels (e.g. :0):
            # include only if they have a MASTER paramset
            is_device_level = get_device_address(address=address) == address and ":" not in address
            channel_flags: int = description.get("FLAGS") or 0
            is_hidden = not (channel_flags & Flag.VISIBLE) or (channel_flags & Flag.INTERNAL)

            if is_device_level or is_hidden:
                raw_ps = description.get("PARAMSETS", [])
                if ParamsetKey.MASTER.value not in raw_ps:
                    continue

            raw_paramsets = description.get("PARAMSETS", [])
            if is_device_level or is_hidden:
                # Only expose MASTER for device-level and internal channels
                paramset_keys: tuple[ParamsetKey, ...] = (ParamsetKey.MASTER,)
            else:
                paramset_keys = tuple(ParamsetKey(ps) for ps in raw_paramsets if ps in {pk.value for pk in ParamsetKey})
            if paramset_keys:
                channels.append(
                    ConfigurableChannel(
                        address=address,
                        channel_type=channel_type,
                        paramset_keys=paramset_keys,
                    )
                )
        return tuple(channels)

    def get_configurable_devices(self, *, locale: str = "en") -> tuple[ConfigurableDevice, ...]:
        """Return all devices with configurable channels for the configuration UI."""
        devices: list[ConfigurableDevice] = []

        for device in self._device_registry.devices:
            try:
                channels = self.get_configurable_channels(
                    interface_id=device.interface_id,
                    device_address=device.address,
                )
            except BaseHomematicException:
                continue
            if not channels:
                continue

            channel_list: list[ConfigurableDeviceChannel] = []
            for ch in channels:
                # Only advertise MASTER if it has visible, non-internal parameters
                effective_keys: list[str] = []
                for pk in ch.paramset_keys:
                    if pk == ParamsetKey.MASTER:
                        descriptions = self.get_paramset_description(
                            interface_id=device.interface_id,
                            channel_address=ch.address,
                            paramset_key=pk,
                        )
                        has_visible = any(
                            is_parameter_visible(parameter_data=pd) and not is_parameter_internal(parameter_data=pd)
                            for pd in descriptions.values()
                        )
                        if has_visible:
                            effective_keys.append(pk.value)
                    else:
                        effective_keys.append(pk.value)

                channel_list.append(
                    ConfigurableDeviceChannel(
                        address=ch.address,
                        channel_type=ch.channel_type,
                        channel_type_label=get_channel_type_translation(
                            channel_type=ch.channel_type,
                            locale=locale,
                        )
                        or ch.channel_type,
                        paramset_keys=tuple(effective_keys),
                    )
                )

            # Collect maintenance data from channel 0
            maintenance_data: dict[str, Any] = {}
            for dp in device.generic_data_points:
                if dp.channel.address.endswith(":0") and dp.parameter in _MAINTENANCE_PARAMS:
                    maintenance_data[dp.parameter.lower()] = dp.value

            devices.append(
                ConfigurableDevice(
                    address=device.address,
                    interface=str(device.interface),
                    interface_id=device.interface_id,
                    model=device.model,
                    model_description=device.model_description or "",
                    name=device.name or device.address,
                    firmware=device.firmware,
                    channels=tuple(channel_list),
                    maintenance=MaintenanceData(**maintenance_data),
                )
            )

        return tuple(devices)

    async def get_link_paramset_description(
        self,
        *,
        interface_id: str,
        channel_address: str,
    ) -> Mapping[str, ParameterData]:
        """
        Fetch the LINK paramset description for a channel on demand.

        LINK paramset descriptions are not cached during device discovery.
        This method fetches them directly from the backend when needed
        for direct link configuration.
        """
        client = self._client_provider.get_client(interface_id=interface_id)
        return await client.get_paramset_description_on_demand(
            channel_address=channel_address,
            paramset_key=ParamsetKey.LINK,
        )

    def get_parameter_data(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
    ) -> ParameterData | None:
        """Return the parameter description for a single parameter."""
        return self._paramset_description_provider.get_parameter_data(
            interface_id=interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    async def get_paramset(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
    ) -> dict[str, Any]:
        """
        Read the current paramset values from the backend.

        Returns the live values for the given channel and paramset key.
        """
        client = self._client_provider.get_client(interface_id=interface_id)
        return await client.get_paramset(
            channel_address=channel_address,
            paramset_key=paramset_key,
            call_source=CallSource.MANUAL_OR_SCHEDULED,
        )

    def get_paramset_description(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
    ) -> Mapping[str, ParameterData]:
        """
        Return the paramset description for a channel.

        This is the set of parameter definitions (type, min, max, default, etc.)
        for the given channel and paramset key.
        """
        all_descriptions = self._paramset_description_provider.get_channel_paramset_descriptions(
            interface_id=interface_id,
            channel_address=channel_address,
        )
        return all_descriptions.get(paramset_key, {})

    async def put_paramset(
        self,
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
        values: dict[str, Any],
        validate: bool = True,
    ) -> PutParamsetResult:
        """
        Write paramset values to the backend.

        When *validate* is ``True`` (the default), each value is checked against
        its parameter description before writing. On validation failure the
        write is skipped and the result contains the per-parameter error messages.
        """
        if validate:
            descriptions = self.get_paramset_description(
                interface_id=interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
            )
            if failures := validate_paramset(descriptions=descriptions, values=values):
                return PutParamsetResult(
                    success=False,
                    validated=True,
                    validation_errors={param: result.reason for param, result in failures.items()},
                )

        client = self._client_provider.get_client(interface_id=interface_id)
        await client.put_paramset(
            channel_address=channel_address,
            paramset_key_or_link_address=paramset_key,
            values=values,
        )
        return PutParamsetResult(success=True, validated=validate, validation_errors={})


__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (name.isupper() or inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
