# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Device and channel model for AioHomematic.

This module implements the runtime representation of a Homematic device and its
channels, including creation and lookup of data points/events, firmware and
availability handling, link management, value caching, and exporting of device
definitions for diagnostics.

Key classes
-----------
- Device: Encapsulates metadata, channels, and operations for a single device.
- Channel: Represents a functional channel with its data points and events.

Other components
----------------
- _ValueCache: Lazy loading and caching of parameter values to minimize RPCs.
  Accessed externally via ``device.value_cache``.
- _DefinitionExporter: Internal utility to export device and paramset descriptions.

Architecture notes
------------------
Device acts as a **Facade** aggregating 15+ protocol interfaces injected via
constructor. This design enables:
- Centralized access to all protocol interfaces for DataPoints
- Single instantiation point in DeviceCoordinator.create_devices()
- Full Protocol-based dependency injection (no direct CentralUnit reference)

Device responsibilities are organized into 7 areas:
1. **Metadata & Identity**: Address, model, name, manufacturer, firmware version
2. **Channel Hierarchy**: Channel management, grouping, data point access
3. **Value Caching**: Lazy loading and caching of parameter values
4. **Availability & State**: Device availability, config pending status
5. **Firmware Management**: Firmware updates, available updates, update state
6. **Links & Export**: Central link management, device definition export
7. **Week Profile**: Schedule/time program support

The Device/Channel classes are the anchor used by generic, custom, calculated,
and hub model code to attach data points and events.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime
import logging
import os
import random
from typing import Any, Final, cast

import orjson

from aiohomematic import i18n
from aiohomematic.async_support import loop_check
from aiohomematic.central.event_bus import DeviceUpdatedEvent, FirmwareUpdatedEvent, LinkPeerChangedEvent
from aiohomematic.const import (
    ADDRESS_SEPARATOR,
    CLICK_EVENTS,
    DEVICE_DESCRIPTIONS_DIR,
    IDENTIFIER_SEPARATOR,
    INIT_DATETIME,
    NO_CACHE_ENTRY,
    PARAMSET_DESCRIPTIONS_DIR,
    RELEVANT_INIT_PARAMETERS,
    REPORT_VALUE_USAGE_DATA,
    REPORT_VALUE_USAGE_VALUE_ID,
    VIRTUAL_REMOTE_MODELS,
    WEEK_PROFILE_PATTERN,
    CallSource,
    DataOperationResult,
    DataPointCategory,
    DataPointKey,
    DataPointUsage,
    DeviceDescription,
    DeviceFirmwareState,
    DeviceTriggerEventType,
    ForcedDeviceAvailability,
    Interface,
    Manufacturer,
    Parameter,
    ParameterData,
    ParamsetKey,
    ProductGroup,
    RxMode,
    ServiceScope,
    check_ignore_model_on_initial_load,
    get_link_source_categories,
    get_link_target_categories,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException, BaseHomematicException, ClientException
from aiohomematic.interfaces.central import (
    CentralInfoProtocol,
    ChannelLookupProtocol,
    ConfigProviderProtocol,
    DataCacheProviderProtocol,
    DataPointProviderProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
    EventSubscriptionManagerProtocol,
    FileOperationsProtocol,
    FirmwareDataRefresherProtocol,
)
from aiohomematic.interfaces.client import ClientProtocol, ClientProviderProtocol
from aiohomematic.interfaces.model import (
    BaseParameterDataPointProtocol,
    CalculatedDataPointProtocol,
    CallbackDataPointProtocol,
    ChannelProtocol,
    CustomDataPointProtocol,
    DeviceProtocol,
    GenericDataPointProtocol,
    GenericDataPointProtocolAny,
    GenericEventProtocol,
    GenericEventProtocolAny,
)
from aiohomematic.interfaces.operations import (
    DeviceDescriptionProviderProtocol,
    DeviceDetailsProviderProtocol,
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)
from aiohomematic.model import week_profile as wp
from aiohomematic.model.custom import data_point as hmce, definition as hmed
from aiohomematic.model.generic import DpBinarySensor
from aiohomematic.model.support import (
    ChannelNameData,
    generate_channel_unique_id,
    get_channel_name_data,
    get_device_name,
)
from aiohomematic.model.update import DpUpdate
from aiohomematic.property_decorators import DelegatedProperty, Kind, hm_property, info_property, state_property
from aiohomematic.support import (
    CacheEntry,
    LogContextMixin,
    PayloadMixin,
    check_or_create_directory,
    extract_exc_args,
    get_channel_address,
    get_channel_no,
    get_rx_modes,
)
from aiohomematic.type_aliases import (
    DeviceUpdatedHandler,
    FirmwareUpdateHandler,
    LinkPeerChangedHandler,
    UnsubscribeCallback,
)

__all__ = ["Channel", "Device"]

_LOGGER: Final = logging.getLogger(__name__)


class Device(DeviceProtocol, LogContextMixin, PayloadMixin):
    """
    Represent a Homematic device with channels and data points.

    Device is the central runtime model for a physical Homematic device. It acts
    as a **Facade** that aggregates 15+ protocol interfaces (injected via constructor)
    and provides unified access for all DataPoint classes.

    Responsibilities
    ----------------
    1. **Metadata & Identity**: Device address, model, name, manufacturer, interface.
    2. **Channel Hierarchy**: Channel creation, grouping, data point lookup.
    3. **Value Caching**: Lazy loading via ``_ValueCache`` (accessed via ``value_cache``).
    4. **Availability & State**: UN_REACH/STICKY_UN_REACH handling, forced availability.
    5. **Firmware Management**: Firmware version, available updates, update operations.
    6. **Links & Export**: Central link management for press events, definition export.
    7. **Week Profile**: Schedule support for climate devices.

    Instantiation
    -------------
    Devices are created exclusively by ``DeviceCoordinator.create_devices()``. All
    dependencies are injected as protocol interfaces, enabling full dependency
    injection without direct CentralUnit references.

    Protocol compliance
    -------------------
    Implements ``DeviceProtocol`` which is a composite of sub-protocols:

    - ``DeviceIdentityProtocol``: Basic identification (address, name, model, manufacturer)
    - ``DeviceChannelAccessProtocol``: Channel and DataPoint access methods
    - ``DeviceAvailabilityProtocol``: Availability state management
    - ``DeviceFirmwareProtocol``: Firmware information and update operations
    - ``DeviceLinkManagementProtocol``: Central link operations
    - ``DeviceGroupManagementProtocol``: Channel group management
    - ``DeviceConfigurationProtocol``: Device configuration and metadata
    - ``DeviceWeekProfileProtocol``: Week profile support
    - ``DeviceProvidersProtocol``: Protocol interface providers
    - ``DeviceLifecycleProtocol``: Lifecycle methods

    Consumers can depend on specific sub-protocols for narrower contracts.
    """

    __slots__ = (
        "_address",
        "_cached_allow_undefined_generic_data_points",
        "_cached_has_sub_devices",
        "_cached_relevant_for_central_link_management",
        "_central_info",
        "_channel_to_group",
        "_channel_lookup",
        "_channels",
        "_client",
        "_client_provider",
        "_config_provider",
        "_data_cache_provider",
        "_data_point_provider",
        "_device_description",
        "_device_data_refresher",
        "_device_description_provider",
        "_device_details_provider",
        "_event_bus_provider",
        "_event_publisher",
        "_event_subscription_manager",
        "_file_operations",
        "_forced_availability",
        "_group_channels",
        "_has_custom_data_point_definition",
        "_rega_id",
        "_ignore_for_custom_data_point",
        "_ignore_on_initial_load",
        "_interface",
        "_interface_id",
        "_is_updatable",
        "_manufacturer",
        "_model",
        "_modified_at",
        "_name",
        "_parameter_visibility_provider",
        "_paramset_description_provider",
        "_product_group",
        "_rooms",
        "_rx_modes",
        "_sub_model",
        "_task_scheduler",
        "_update_data_point",
        "_value_cache",
        "_week_profile",
    )

    def __init__(
        self,
        *,
        interface_id: str,
        device_address: str,
        central_info: CentralInfoProtocol,
        channel_lookup: ChannelLookupProtocol,
        client_provider: ClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        data_cache_provider: DataCacheProviderProtocol,
        data_point_provider: DataPointProviderProtocol,
        device_data_refresher: FirmwareDataRefresherProtocol,
        device_description_provider: DeviceDescriptionProviderProtocol,
        device_details_provider: DeviceDetailsProviderProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        event_subscription_manager: EventSubscriptionManagerProtocol,
        file_operations: FileOperationsProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
    ) -> None:
        """Initialize the device object."""
        PayloadMixin.__init__(self)
        self._interface_id: Final = interface_id
        self._address: Final = device_address
        self._device_details_provider: Final = device_details_provider
        self._device_description_provider: Final = device_description_provider
        self._paramset_description_provider: Final = paramset_description_provider
        self._parameter_visibility_provider: Final = parameter_visibility_provider
        self._client_provider: Final = client_provider
        self._config_provider: Final = config_provider
        self._central_info: Final = central_info
        self._event_bus_provider: Final = event_bus_provider
        self._event_publisher: Final = event_publisher
        self._task_scheduler: Final = task_scheduler
        self._file_operations: Final = file_operations
        self._device_data_refresher: Final = device_data_refresher
        self._data_cache_provider: Final = data_cache_provider
        self._data_point_provider: Final = data_point_provider
        self._channel_lookup: Final = channel_lookup
        self._event_subscription_manager: Final = event_subscription_manager
        self._channel_to_group: Final[dict[int | None, int]] = {}
        self._group_channels: Final[dict[int, set[int | None]]] = {}
        self._rega_id: Final = device_details_provider.get_address_id(address=device_address)
        self._interface: Final = device_details_provider.get_interface(address=device_address)
        self._client: Final = client_provider.get_client(interface_id=interface_id)
        self._device_description = self._device_description_provider.get_device_description(
            interface_id=interface_id, address=device_address
        )
        _LOGGER.debug(
            "__INIT__: Initializing device: %s, %s",
            interface_id,
            device_address,
        )

        self._modified_at: datetime = INIT_DATETIME
        self._forced_availability: ForcedDeviceAvailability = ForcedDeviceAvailability.NOT_SET
        self._model: Final[str] = self._device_description["TYPE"]
        self._ignore_on_initial_load: Final[bool] = check_ignore_model_on_initial_load(model=self._model)
        self._is_updatable: Final = self._device_description.get("UPDATABLE") or False
        self._rx_modes: Final = get_rx_modes(mode=self._device_description.get("RX_MODE", 0))
        self._sub_model: Final[str | None] = self._device_description.get("SUBTYPE")
        self._ignore_for_custom_data_point: Final[bool] = parameter_visibility_provider.model_is_ignored(
            model=self._model
        )
        self._manufacturer = self._identify_manufacturer()
        self._product_group: Final[ProductGroup] = self._client.get_product_group(model=self._model)
        # marker if device will be created as custom data_point
        self._has_custom_data_point_definition: Final = (
            hmed.data_point_definition_exists(model=self._model) and not self._ignore_for_custom_data_point
        )
        self._name: Final = get_device_name(
            device_details_provider=device_details_provider,
            device_address=device_address,
            model=self._model,
        )
        channel_addresses = tuple(
            [device_address] + [address for address in self._device_description["CHILDREN"] if address != ""]
        )
        self._channels: Final[dict[str, ChannelProtocol]] = {
            address: Channel(device=self, channel_address=address) for address in channel_addresses
        }
        self._value_cache: Final[_ValueCache] = _ValueCache(device=self)
        self._rooms: Final = device_details_provider.get_device_rooms(device_address=device_address)
        self._update_data_point: Final = DpUpdate(device=self) if self.is_updatable else None
        self._week_profile: wp.WeekProfile[dict[Any, Any]] | None = None
        _LOGGER.debug(
            "__INIT__: Initialized device: %s, %s, %s, %s",
            self._interface_id,
            self._address,
            self._model,
            self._name,
        )

    def __str__(self) -> str:
        """Provide some useful information."""
        return (
            f"address: {self._address}, "
            f"model: {self._model}, "
            f"name: {self._name}, "
            f"generic dps: {len(self.generic_data_points)}, "
            f"calculated dps: {len(self.calculated_data_points)}, "
            f"custom dps: {len(self.custom_data_points)}, "
            f"events: {len(self.generic_events)}"
        )

    address: Final = DelegatedProperty[str](path="_address", kind=Kind.INFO, log_context=True)
    central_info: Final = DelegatedProperty[CentralInfoProtocol](path="_central_info")
    channel_lookup: Final = DelegatedProperty[ChannelLookupProtocol](path="_channel_lookup")
    channels: Final = DelegatedProperty[Mapping[str, ChannelProtocol]](path="_channels")
    client: Final = DelegatedProperty[ClientProtocol](path="_client")
    config_provider: Final = DelegatedProperty[ConfigProviderProtocol](path="_config_provider")
    data_cache_provider: Final = DelegatedProperty[DataCacheProviderProtocol](path="_data_cache_provider")
    data_point_provider: Final = DelegatedProperty[DataPointProviderProtocol](path="_data_point_provider")
    device_data_refresher: Final = DelegatedProperty[FirmwareDataRefresherProtocol](path="_device_data_refresher")
    device_description_provider: Final = DelegatedProperty[DeviceDescriptionProviderProtocol](
        path="_device_description_provider"
    )
    device_details_provider: Final = DelegatedProperty[DeviceDetailsProviderProtocol](path="_device_details_provider")
    event_bus_provider: Final = DelegatedProperty[EventBusProviderProtocol](path="_event_bus_provider")
    event_publisher: Final = DelegatedProperty[EventPublisherProtocol](path="_event_publisher")
    event_subscription_manager: Final = DelegatedProperty[EventSubscriptionManagerProtocol](
        path="_event_subscription_manager"
    )
    has_custom_data_point_definition: Final = DelegatedProperty[bool](path="_has_custom_data_point_definition")
    ignore_for_custom_data_point: Final = DelegatedProperty[bool](path="_ignore_for_custom_data_point")
    ignore_on_initial_load: Final = DelegatedProperty[bool](path="_ignore_on_initial_load")
    interface: Final = DelegatedProperty[Interface](path="_interface")
    interface_id: Final = DelegatedProperty[str](path="_interface_id", log_context=True)
    is_updatable: Final = DelegatedProperty[bool](path="_is_updatable")
    manufacturer: Final = DelegatedProperty[str](path="_manufacturer", kind=Kind.INFO)
    model: Final = DelegatedProperty[str](path="_model", kind=Kind.INFO, log_context=True)
    name: Final = DelegatedProperty[str](path="_name", kind=Kind.INFO)
    parameter_visibility_provider: Final = DelegatedProperty[ParameterVisibilityProviderProtocol](
        path="_parameter_visibility_provider"
    )
    paramset_description_provider: Final = DelegatedProperty[ParamsetDescriptionProviderProtocol](
        path="_paramset_description_provider"
    )
    product_group: Final = DelegatedProperty[ProductGroup](path="_product_group")
    rega_id: Final = DelegatedProperty[int](path="_rega_id")
    rooms: Final = DelegatedProperty[set[str]](path="_rooms")
    rx_modes: Final = DelegatedProperty[tuple[RxMode, ...]](path="_rx_modes")
    sub_model: Final = DelegatedProperty[str | None](path="_sub_model")
    task_scheduler: Final = DelegatedProperty[TaskSchedulerProtocol](path="_task_scheduler")
    update_data_point: Final = DelegatedProperty[DpUpdate | None](path="_update_data_point")
    value_cache: Final = DelegatedProperty["_ValueCache"](path="_value_cache")
    week_profile: Final = DelegatedProperty[wp.WeekProfile[dict[Any, Any]] | None](path="_week_profile")

    @property
    def _dp_config_pending(self) -> DpBinarySensor | None:
        """Return the CONFIG_PENDING data point."""
        return cast(
            DpBinarySensor | None,
            self.get_generic_data_point(channel_address=f"{self._address}:0", parameter=Parameter.CONFIG_PENDING),
        )

    @property
    def _dp_sticky_un_reach(self) -> DpBinarySensor | None:
        """Return the STICKY_UN_REACH data point."""
        return cast(
            DpBinarySensor | None,
            self.get_generic_data_point(channel_address=f"{self._address}:0", parameter=Parameter.STICKY_UN_REACH),
        )

    @property
    def _dp_un_reach(self) -> DpBinarySensor | None:
        """Return the UN_REACH data point."""
        return cast(
            DpBinarySensor | None,
            self.get_generic_data_point(channel_address=f"{self._address}:0", parameter=Parameter.UN_REACH),
        )

    @property
    def available_firmware(self) -> str | None:
        """Return the available firmware of the device."""
        return str(self._device_description.get("AVAILABLE_FIRMWARE", ""))

    @property
    def calculated_data_points(self) -> tuple[CalculatedDataPointProtocol, ...]:
        """Return the generic data points."""
        data_points: list[CalculatedDataPointProtocol] = []
        for channel in self._channels.values():
            data_points.extend(channel.calculated_data_points)
        return tuple(data_points)

    @property
    def config_pending(self) -> bool:
        """Return if a config change of the device is pending."""
        if self._dp_config_pending is not None and self._dp_config_pending.value is not None:
            return self._dp_config_pending.value is True
        return False

    @property
    def custom_data_points(self) -> tuple[hmce.CustomDataPoint, ...]:
        """Return the custom data points."""
        return tuple(
            cast(hmce.CustomDataPoint, channel.custom_data_point)
            for channel in self._channels.values()
            if channel.custom_data_point is not None
        )

    @property
    def data_point_paths(self) -> tuple[str, ...]:
        """Return the data point paths."""
        data_point_paths: list[str] = []
        for channel in self._channels.values():
            data_point_paths.extend(channel.data_point_paths)
        return tuple(data_point_paths)

    @property
    def default_schedule_channel(self) -> ChannelProtocol | None:
        """Return the schedule channel address."""
        for channel in self._channels.values():
            if channel.is_schedule_channel:
                return channel
        return None

    @property
    def firmware_updatable(self) -> bool:
        """Return the firmware update state of the device."""
        return self._device_description.get("FIRMWARE_UPDATABLE") or False

    @property
    def firmware_update_state(self) -> DeviceFirmwareState:
        """Return the firmware update state of the device."""
        return DeviceFirmwareState(self._device_description.get("FIRMWARE_UPDATE_STATE") or DeviceFirmwareState.UNKNOWN)

    @property
    def generic_data_points(self) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the generic data points."""
        data_points: list[GenericDataPointProtocolAny] = []
        for channel in self._channels.values():
            data_points.extend(channel.generic_data_points)
        return tuple(data_points)

    @property
    def generic_events(self) -> tuple[GenericEventProtocolAny, ...]:
        """Return the generic events."""
        events: list[GenericEventProtocolAny] = []
        for channel in self._channels.values():
            events.extend(channel.generic_events)
        return tuple(events)

    @property
    def info(self) -> Mapping[str, Any]:
        """Return the device info."""
        device_info = dict(self.info_payload)
        device_info["central"] = self._central_info.info_payload
        return device_info

    @property
    def link_peer_channels(self) -> Mapping[ChannelProtocol, tuple[ChannelProtocol, ...]]:
        """Return the link peer channels."""
        return {
            channel: channel.link_peer_channels for channel in self._channels.values() if channel.link_peer_channels
        }

    @property
    def supports_week_profile(self) -> bool:
        """Return if the device supports week profiles."""
        if self._week_profile is None:
            return False
        return self._week_profile.supports_schedule

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._forced_availability != ForcedDeviceAvailability.NOT_SET:
            return self._forced_availability == ForcedDeviceAvailability.FORCE_TRUE
        if (un_reach := self._dp_un_reach) is None:
            un_reach = self._dp_sticky_un_reach
        if un_reach is not None and un_reach.value is not None:
            return not un_reach.value
        return True

    @info_property
    def firmware(self) -> str:
        """Return the firmware of the device."""
        return self._device_description.get("FIRMWARE") or "0.0"

    @info_property
    def identifier(self) -> str:
        """Return the identifier of the device."""
        return f"{self._address}{IDENTIFIER_SEPARATOR}{self._interface_id}"

    @info_property
    def room(self) -> str | None:
        """Return the room of the device, if only one assigned in the backend."""
        if self._rooms and len(self._rooms) == 1:
            return list(self._rooms)[0]
        if (maintenance_channel := self.get_channel(channel_address=f"{self._address}:0")) is not None:
            return maintenance_channel.room
        return None

    @hm_property(cached=True)
    def allow_undefined_generic_data_points(self) -> bool:
        """Return if undefined generic data points of this device are allowed."""
        return bool(
            all(
                channel.custom_data_point.allow_undefined_generic_data_points
                for channel in self._channels.values()
                if channel.custom_data_point is not None
            )
        )

    @hm_property(cached=True)
    def has_sub_devices(self) -> bool:
        """Return if device has multiple sub device channels."""
        # If there is only one channel group, no sub devices are needed
        if len(self._group_channels) <= 1:
            return False
        count = 0
        # If there are multiple channel groups with more than one channel, there are sub devices
        for gcs in self._group_channels.values():
            if len(gcs) > 1:
                count += 1
            if count > 1:
                return True

        return False

    @hm_property(cached=True)
    def relevant_for_central_link_management(self) -> bool:
        """Return if channel is relevant for central link management."""
        return (
            self._interface in (Interface.BIDCOS_RF, Interface.BIDCOS_WIRED, Interface.HMIP_RF)
            and self._model not in VIRTUAL_REMOTE_MODELS
        )

    def add_channel_to_group(self, *, group_no: int, channel_no: int | None) -> None:
        """Add channel to group."""
        if group_no not in self._group_channels:
            self._group_channels[group_no] = set()
        self._group_channels[group_no].add(channel_no)

        if group_no not in self._channel_to_group:
            self._channel_to_group[group_no] = group_no
        if channel_no not in self._channel_to_group:
            self._channel_to_group[channel_no] = group_no

    @inspector
    async def create_central_links(self) -> None:
        """Create a central links to support press events on all channels with click events."""
        if self.relevant_for_central_link_management:  # pylint: disable=using-constant-test
            for channel in self._channels.values():
                await channel.create_central_link()

    @inspector
    async def export_device_definition(self) -> None:
        """Export the device definition for current device."""
        try:
            device_exporter = _DefinitionExporter(device=self)
            await device_exporter.export_data()
        except Exception as exc:
            raise AioHomematicException(
                i18n.tr(
                    key="exception.model.device.export_device_definition.failed",
                    reason=extract_exc_args(exc=exc),
                )
            ) from exc

    async def finalize_init(self) -> None:
        """Finalize the device init action after model setup."""
        await self.load_value_cache()
        for channel in self._channels.values():
            await channel.finalize_init()

    def get_calculated_data_point(self, *, channel_address: str, parameter: str) -> CalculatedDataPointProtocol | None:
        """Return a calculated data_point from device."""
        if channel := self.get_channel(channel_address=channel_address):
            return channel.get_calculated_data_point(parameter=parameter)
        return None

    def get_channel(self, *, channel_address: str) -> ChannelProtocol | None:
        """Get channel of device."""
        return self._channels.get(channel_address)

    def get_channel_group_no(self, *, channel_no: int | None) -> int | None:
        """Return the group no of the channel."""
        return self._channel_to_group.get(channel_no)

    def get_custom_data_point(self, *, channel_no: int) -> hmce.CustomDataPoint | None:
        """Return a custom data_point from device."""
        if channel := self.get_channel(
            channel_address=get_channel_address(device_address=self._address, channel_no=channel_no)
        ):
            return cast(hmce.CustomDataPoint | None, channel.custom_data_point)
        return None

    def get_data_points(
        self,
        *,
        category: DataPointCategory | None = None,
        exclude_no_create: bool = True,
        registered: bool | None = None,
    ) -> tuple[CallbackDataPointProtocol, ...]:
        """Get all data points of the device."""
        all_data_points: list[CallbackDataPointProtocol] = []
        if (
            self._update_data_point
            and (category is None or self._update_data_point.category == category)
            and (
                (exclude_no_create and self._update_data_point.usage != DataPointUsage.NO_CREATE)
                or exclude_no_create is False
            )
            and (registered is None or self._update_data_point.is_registered == registered)
        ):
            all_data_points.append(self._update_data_point)
        for channel in self._channels.values():
            all_data_points.extend(
                channel.get_data_points(category=category, exclude_no_create=exclude_no_create, registered=registered)
            )
        return tuple(all_data_points)

    def get_events(
        self, *, event_type: DeviceTriggerEventType, registered: bool | None = None
    ) -> Mapping[int | None, tuple[GenericEventProtocolAny, ...]]:
        """Return a list of specific events of a channel."""
        events: dict[int | None, tuple[GenericEventProtocolAny, ...]] = {}
        for channel in self._channels.values():
            if (values := channel.get_events(event_type=event_type, registered=registered)) and len(values) > 0:
                events[channel.no] = values
        return events

    def get_generic_data_point(
        self,
        *,
        channel_address: str | None = None,
        parameter: str | None = None,
        paramset_key: ParamsetKey | None = None,
        state_path: str | None = None,
    ) -> GenericDataPointProtocolAny | None:
        """Return a generic data_point from device."""
        if channel_address is None:
            for ch in self._channels.values():
                if dp := ch.get_generic_data_point(
                    parameter=parameter, paramset_key=paramset_key, state_path=state_path
                ):
                    return dp
            return None

        if channel := self.get_channel(channel_address=channel_address):
            return channel.get_generic_data_point(parameter=parameter, paramset_key=paramset_key, state_path=state_path)
        return None

    def get_generic_event(
        self, *, channel_address: str | None = None, parameter: str | None = None, state_path: str | None = None
    ) -> GenericEventProtocolAny | None:
        """Return a generic event from device."""
        if channel_address is None:
            for ch in self._channels.values():
                if event := ch.get_generic_event(parameter=parameter, state_path=state_path):
                    return event
            return None

        if channel := self.get_channel(channel_address=channel_address):
            return channel.get_generic_event(parameter=parameter, state_path=state_path)
        return None

    def get_readable_data_points(self, *, paramset_key: ParamsetKey) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the list of readable master data points."""
        data_points: list[GenericDataPointProtocolAny] = []
        for channel in self._channels.values():
            data_points.extend(channel.get_readable_data_points(paramset_key=paramset_key))
        return tuple(data_points)

    def identify_channel(self, *, text: str) -> ChannelProtocol | None:
        """Identify channel within a text."""
        for channel_address, channel in self._channels.items():
            if text.endswith(channel_address):
                return channel
            if str(channel.rega_id) in text:
                return channel
            if str(channel.device.rega_id) in text:
                return channel

        return None

    def init_week_profile(self, *, data_point: CustomDataPointProtocol) -> None:
        """Initialize the device schedule."""
        # Only initialize if week_profile supports schedule
        if (
            self._week_profile is None
            and (week_profile := wp.create_week_profile(data_point=data_point)) is not None
            and week_profile.supports_schedule
        ):
            self._week_profile = week_profile

    def is_in_multi_channel_group(self, *, channel_no: int | None) -> bool:
        """Return if multiple channels are in the group."""
        if channel_no is None:
            return False

        return len([s for s, m in self._channel_to_group.items() if m == self._channel_to_group.get(channel_no)]) > 1

    @inspector(scope=ServiceScope.INTERNAL)
    async def load_value_cache(self) -> None:
        """Initialize the parameter cache."""
        if len(self.generic_data_points) > 0:
            await self._value_cache.init_base_data_points()
        if len(self.generic_events) > 0:
            await self._value_cache.init_readable_events()

    async def on_config_changed(self) -> None:
        """Do what is needed on device config change."""
        for channel in self._channels.values():
            await channel.on_config_changed()
        if self._update_data_point:
            await self._update_data_point.on_config_changed()

        if self._week_profile:
            await self._week_profile.reload_and_cache_schedule()

        await self._file_operations.save_files(save_paramset_descriptions=True)
        self.publish_device_updated_event()

    @loop_check
    def publish_device_updated_event(self) -> None:
        """Do what is needed when the state of the device has been updated."""
        self._set_modified_at()

        # Publish to EventBus asynchronously
        async def _publish_device_updated() -> None:
            await self._event_bus_provider.event_bus.publish(
                event=DeviceUpdatedEvent(
                    timestamp=datetime.now(),
                    device_address=self._address,
                )
            )

        self._task_scheduler.create_task(
            target=_publish_device_updated,
            name=f"device-updated-{self._address}",
        )

    def refresh_firmware_data(self) -> None:
        """Refresh firmware data of the device."""
        old_available_firmware = self.available_firmware
        old_firmware = self.firmware
        old_firmware_update_state = self.firmware_update_state
        old_firmware_updatable = self.firmware_updatable

        self._device_description = self._device_description_provider.get_device_description(
            interface_id=self._interface_id, address=self._address
        )

        if (
            old_available_firmware != self.available_firmware
            or old_firmware != self.firmware
            or old_firmware_update_state != self.firmware_update_state
            or old_firmware_updatable != self.firmware_updatable
        ):
            # Publish to EventBus asynchronously
            async def _publish_firmware_updated() -> None:
                await self._event_bus_provider.event_bus.publish(
                    event=FirmwareUpdatedEvent(
                        timestamp=datetime.now(),
                        device_address=self._address,
                    )
                )

            self._task_scheduler.create_task(
                target=_publish_firmware_updated,
                name=f"firmware-updated-{self._address}",
            )

    def remove(self) -> None:
        """Remove data points from collections and central."""
        for channel in self._channels.values():
            channel.remove()

    @inspector
    async def remove_central_links(self) -> None:
        """Remove central links."""
        if self.relevant_for_central_link_management:  # pylint: disable=using-constant-test
            for channel in self._channels.values():
                await channel.remove_central_link()

    @inspector
    async def rename(self, *, new_name: str) -> bool:
        """Rename the device on the CCU."""
        return await self._client.rename_device(rega_id=self._rega_id, new_name=new_name)

    def set_forced_availability(self, *, forced_availability: ForcedDeviceAvailability) -> None:
        """Set the availability of the device."""
        if self._forced_availability != forced_availability:
            self._forced_availability = forced_availability
            for dp in self.generic_data_points:
                dp.publish_data_point_updated_event()

    def subscribe_to_device_updated(self, *, handler: DeviceUpdatedHandler) -> UnsubscribeCallback:
        """Subscribe update handler."""

        # Create adapter that filters for this device's events
        def event_handler(*, event: DeviceUpdatedEvent) -> None:
            if event.device_address == self._address:
                handler()

        return self._event_bus_provider.event_bus.subscribe(
            event_type=DeviceUpdatedEvent,
            event_key=self._address,
            handler=event_handler,
        )

    def subscribe_to_firmware_updated(self, *, handler: FirmwareUpdateHandler) -> UnsubscribeCallback:
        """Subscribe firmware update handler."""

        # Create adapter that filters for this device's events
        def event_handler(*, event: FirmwareUpdatedEvent) -> None:
            if event.device_address == self._address:
                handler()

        return self._event_bus_provider.event_bus.subscribe(
            event_type=FirmwareUpdatedEvent,
            event_key=self._address,
            handler=event_handler,
        )

    @inspector
    async def update_firmware(self, *, refresh_after_update_intervals: tuple[int, ...]) -> bool:
        """Update the firmware of the Homematic device."""
        update_result = await self._client.update_device_firmware(device_address=self._address)

        async def refresh_data() -> None:
            for refresh_interval in refresh_after_update_intervals:
                await asyncio.sleep(refresh_interval)
                await self._device_data_refresher.refresh_firmware_data(device_address=self._address)

        if refresh_after_update_intervals:
            self._task_scheduler.create_task(target=refresh_data, name="refresh_firmware_data")

        return update_result

    def _identify_manufacturer(self) -> Manufacturer:
        """Identify the manufacturer of a device."""
        if self._model.lower().startswith("hb"):
            return Manufacturer.HB
        if self._model.lower().startswith("alpha"):
            return Manufacturer.MOEHLENHOFF
        return Manufacturer.EQ3

    def _set_modified_at(self) -> None:
        self._modified_at = datetime.now()


class Channel(ChannelProtocol, LogContextMixin, PayloadMixin):
    """
    Represent a device channel containing data points and events.

    Channels group related parameters and provide the organizational structure
    for data points within a device. Each channel has a unique address (e.g.,
    ``VCU0000001:1``) and contains generic, custom, and calculated data points.

    Responsibilities
    ----------------
    1. **Data Point Storage**: Stores generic, custom, and calculated data points.
    2. **Event Storage**: Stores generic events (KEYPRESS, MOTION, etc.).
    3. **Grouping**: Multi-channel grouping support (e.g., for multi-gang switches).
    4. **Link Peers**: Link partner management for peer-to-peer communication.
    5. **Paramset Access**: Access to VALUES and MASTER paramset descriptions.

    Access pattern
    --------------
    Channels access protocol interfaces through their parent device:
    ``self._device.event_bus_provider``, ``self._device.client``, etc.

    Protocol compliance
    -------------------
    Implements ``ChannelProtocol`` which is a composite of sub-protocols:

    - ``ChannelIdentityProtocol``: Basic identification (address, name, no, type_name)
    - ``ChannelDataPointAccessProtocol``: DataPoint and event access methods
    - ``ChannelGroupingProtocol``: Channel group management (group_master, link_peer_channels)
    - ``ChannelMetadataProtocol``: Additional metadata (device, function, room, paramset_descriptions)
    - ``ChannelLinkManagementProtocol``: Central link operations
    - ``ChannelLifecycleProtocol``: Lifecycle methods (finalize_init, on_config_changed, remove)

    Consumers can depend on specific sub-protocols for narrower contracts.
    """

    __slots__ = (
        "_address",
        "_cached_group_master",
        "_cached_group_no",
        "_cached_is_in_multi_group",
        "_calculated_data_points",
        "_custom_data_point",
        "_channel_description",
        "_device",
        "_function",
        "_generic_data_points",
        "_generic_events",
        "_rega_id",
        "_is_schedule_channel",
        "_link_peer_addresses",
        "_link_source_categories",
        "_link_source_roles",
        "_link_target_categories",
        "_link_target_roles",
        "_modified_at",
        "_name_data",
        "_no",
        "_paramset_keys",
        "_rooms",
        "_state_path_to_dpk",
        "_type_name",
        "_unique_id",
    )

    def __init__(self, *, device: DeviceProtocol, channel_address: str) -> None:
        """Initialize the channel object."""
        PayloadMixin.__init__(self)

        self._device: Final = device
        self._address: Final = channel_address
        self._rega_id: Final = self._device.device_details_provider.get_address_id(address=channel_address)
        self._no: Final[int | None] = get_channel_no(address=channel_address)
        self._name_data: Final = get_channel_name_data(channel=self)
        self._channel_description: DeviceDescription = self._device.device_description_provider.get_device_description(
            interface_id=self._device.interface_id, address=channel_address
        )
        self._type_name: Final[str] = self._channel_description["TYPE"]
        self._is_schedule_channel: Final[bool] = WEEK_PROFILE_PATTERN.match(self._type_name) is not None
        self._paramset_keys: Final = tuple(
            ParamsetKey(paramset_key) for paramset_key in self._channel_description["PARAMSETS"]
        )

        self._unique_id: Final = generate_channel_unique_id(
            config_provider=self._device.config_provider, address=channel_address
        )
        self._calculated_data_points: Final[dict[DataPointKey, CalculatedDataPointProtocol]] = {}
        self._custom_data_point: hmce.CustomDataPoint | None = None
        self._generic_data_points: Final[dict[DataPointKey, GenericDataPointProtocolAny]] = {}
        self._generic_events: Final[dict[DataPointKey, GenericEventProtocolAny]] = {}
        self._state_path_to_dpk: Final[dict[str, DataPointKey]] = {}
        self._link_peer_addresses: tuple[str, ...] = ()
        self._link_source_roles: tuple[str, ...] = (
            tuple(source_roles.split(" "))
            if (source_roles := self._channel_description.get("LINK_SOURCE_ROLES"))
            else ()
        )
        self._link_source_categories: Final = get_link_source_categories(
            source_roles=self._link_source_roles, channel_type_name=self._type_name
        )
        self._link_target_roles: tuple[str, ...] = (
            tuple(target_roles.split(" "))
            if (target_roles := self._channel_description.get("LINK_TARGET_ROLES"))
            else ()
        )
        self._link_target_categories: Final = get_link_target_categories(
            target_roles=self._link_target_roles, channel_type_name=self._type_name
        )
        self._modified_at: datetime = INIT_DATETIME
        self._rooms: Final = self._device.device_details_provider.get_channel_rooms(channel_address=channel_address)
        self._function: Final = self._device.device_details_provider.get_function_text(address=self._address)
        self.init_channel()

    def __str__(self) -> str:
        """Provide some useful information."""
        return (
            f"address: {self._address}, "
            f"type: {self._type_name}, "
            f"generic dps: {len(self._generic_data_points)}, "
            f"calculated dps: {len(self._calculated_data_points)}, "
            f"custom dp: {self._custom_data_point is not None}, "
            f"events: {len(self._generic_events)}"
        )

    address: Final = DelegatedProperty[str](path="_address", kind=Kind.INFO)
    custom_data_point: Final = DelegatedProperty[hmce.CustomDataPoint | None](path="_custom_data_point")
    description: Final = DelegatedProperty[DeviceDescription](path="_channel_description")
    device: Final = DelegatedProperty[DeviceProtocol](path="_device", log_context=True)
    full_name: Final = DelegatedProperty[str](path="_name_data.full_name")
    function: Final = DelegatedProperty[str | None](path="_function")
    is_schedule_channel: Final = DelegatedProperty[bool](path="_is_schedule_channel")
    link_peer_addresses: Final = DelegatedProperty[tuple[str, ...]](path="_link_peer_addresses")
    link_peer_source_categories: Final = DelegatedProperty[tuple[str, ...]](path="_link_source_categories")
    link_peer_target_categories: Final = DelegatedProperty[tuple[str, ...]](path="_link_target_categories")
    name: Final = DelegatedProperty[str](path="_name_data.channel_name")
    name_data: Final = DelegatedProperty[ChannelNameData](path="_name_data")
    no: Final = DelegatedProperty[int | None](path="_no", log_context=True)
    paramset_keys: Final = DelegatedProperty[tuple[ParamsetKey, ...]](path="_paramset_keys")
    rega_id: Final = DelegatedProperty[int](path="_rega_id")
    rooms: Final = DelegatedProperty[set[str]](path="_rooms")
    type_name: Final = DelegatedProperty[str](path="_type_name")
    unique_id: Final = DelegatedProperty[str](path="_unique_id")

    @property
    def _has_key_press_events(self) -> bool:
        """Return if channel has KEYPRESS events."""
        return any(event for event in self.generic_events if event.event_type is DeviceTriggerEventType.KEYPRESS)

    @property
    def calculated_data_points(self) -> tuple[CalculatedDataPointProtocol, ...]:
        """Return the generic data points."""
        return tuple(self._calculated_data_points.values())

    @property
    def data_point_paths(self) -> tuple[str, ...]:
        """Return the data point paths."""
        return tuple(self._state_path_to_dpk.keys())

    @property
    def generic_data_points(self) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the generic data points."""
        return tuple(self._generic_data_points.values())

    @property
    def generic_events(self) -> tuple[GenericEventProtocolAny, ...]:
        """Return the generic events."""
        return tuple(self._generic_events.values())

    @property
    def is_group_master(self) -> bool:
        """Return if group master of channel."""
        return self.group_no == self._no

    @property
    def link_peer_channels(self) -> tuple[ChannelProtocol, ...]:
        """Return the link peer channel."""
        return tuple(
            channel
            for address in self._link_peer_addresses
            if self._link_peer_addresses
            and (channel := self._device.channel_lookup.get_channel(channel_address=address)) is not None
        )

    @property
    def operation_mode(self) -> str | None:
        """Return the channel operation mode if available."""
        if (
            cop := self.get_generic_data_point(parameter=Parameter.CHANNEL_OPERATION_MODE)
        ) is not None and cop.value is not None:
            return str(cop.value)
        return None

    @property
    def paramset_descriptions(self) -> Mapping[ParamsetKey, Mapping[str, ParameterData]]:
        """Return the paramset descriptions of the channel."""
        return self._device.paramset_description_provider.get_channel_paramset_descriptions(
            interface_id=self._device.interface_id, channel_address=self._address
        )

    @info_property
    def room(self) -> str | None:
        """Return the room of the device, if only one assigned in the backend."""
        if self._rooms and len(self._rooms) == 1:
            return list(self._rooms)[0]
        if self.is_group_master:
            return None
        if (master_channel := self.group_master) is not None:
            return master_channel.room
        return None

    @hm_property(cached=True)
    def group_master(self) -> ChannelProtocol | None:
        """Return the master channel of the group."""
        if self.group_no is None:
            return None
        return (
            self
            if self.is_group_master
            else self._device.get_channel(channel_address=f"{self._device.address}:{self.group_no}")
        )

    @hm_property(cached=True)
    def group_no(self) -> int | None:
        """Return the no of the channel group."""
        return self._device.get_channel_group_no(channel_no=self._no)

    @hm_property(cached=True)
    def is_in_multi_group(self) -> bool:
        """Return if multiple channels are in the group."""
        return self._device.is_in_multi_channel_group(channel_no=self._no)

    def add_data_point(self, *, data_point: CallbackDataPointProtocol) -> None:
        """Add a data_point to a channel."""
        if isinstance(data_point, BaseParameterDataPointProtocol):
            self._device.event_subscription_manager.add_data_point_subscription(data_point=data_point)
            self._state_path_to_dpk[data_point.state_path] = data_point.dpk
        if isinstance(data_point, CalculatedDataPointProtocol):
            self._calculated_data_points[data_point.dpk] = data_point
        if isinstance(data_point, GenericDataPointProtocol):
            self._generic_data_points[data_point.dpk] = data_point
        if isinstance(data_point, hmce.CustomDataPoint):
            self._custom_data_point = data_point
        if isinstance(data_point, GenericEventProtocol):
            self._generic_events[data_point.dpk] = data_point

    @inspector(scope=ServiceScope.INTERNAL)
    async def cleanup_central_link_metadata(self) -> None:
        """Cleanup the metadata for central links."""
        if metadata := await self._device.client.get_metadata(address=self._address, data_id=REPORT_VALUE_USAGE_DATA):
            await self._device.client.set_metadata(
                address=self._address,
                data_id=REPORT_VALUE_USAGE_DATA,
                value={key: value for key, value in metadata.items() if key in CLICK_EVENTS},
            )

    @inspector(scope=ServiceScope.INTERNAL)
    async def create_central_link(self) -> None:
        """Create a central link to support press events."""
        if self._has_key_press_events and not await self._has_central_link():
            await self._device.client.report_value_usage(
                address=self._address, value_id=REPORT_VALUE_USAGE_VALUE_ID, ref_counter=1
            )

    async def finalize_init(self) -> None:
        """Finalize the channel init action after model setup."""
        for ge in self._generic_data_points.values():
            await ge.finalize_init()
        for gev in self._generic_events.values():
            await gev.finalize_init()
        for cdp in self._calculated_data_points.values():
            await cdp.finalize_init()
        if self._custom_data_point:
            await self._custom_data_point.finalize_init()

    def get_calculated_data_point(self, *, parameter: str) -> CalculatedDataPointProtocol | None:
        """Return a calculated data_point from device."""
        return self._calculated_data_points.get(
            DataPointKey(
                interface_id=self._device.interface_id,
                channel_address=self._address,
                paramset_key=ParamsetKey.CALCULATED,
                parameter=parameter,
            )
        )

    def get_data_points(
        self,
        *,
        category: DataPointCategory | None = None,
        exclude_no_create: bool = True,
        registered: bool | None = None,
    ) -> tuple[CallbackDataPointProtocol, ...]:
        """Get all data points of the device."""
        all_data_points: list[CallbackDataPointProtocol] = list(self._generic_data_points.values()) + list(
            self._calculated_data_points.values()
        )
        if self._custom_data_point:
            all_data_points.append(self._custom_data_point)

        return tuple(
            dp
            for dp in all_data_points
            if dp is not None
            and (category is None or dp.category == category)
            and ((exclude_no_create and dp.usage != DataPointUsage.NO_CREATE) or exclude_no_create is False)
            and (registered is None or dp.is_registered == registered)
        )

    def get_events(
        self, *, event_type: DeviceTriggerEventType, registered: bool | None = None
    ) -> tuple[GenericEventProtocolAny, ...]:
        """Return a list of specific events of a channel."""
        return tuple(
            event
            for event in self._generic_events.values()
            if (event.event_type == event_type and (registered is None or event.is_registered == registered))
        )

    def get_generic_data_point(
        self, *, parameter: str | None = None, paramset_key: ParamsetKey | None = None, state_path: str | None = None
    ) -> GenericDataPointProtocolAny | None:
        """Return a generic data_point from device."""
        if state_path is not None and (dpk := self._state_path_to_dpk.get(state_path)) is not None:
            return self._generic_data_points.get(dpk)
        if parameter is None:
            return None
        if paramset_key:
            return self._generic_data_points.get(
                DataPointKey(
                    interface_id=self._device.interface_id,
                    channel_address=self._address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                )
            )

        if dp := self._generic_data_points.get(
            DataPointKey(
                interface_id=self._device.interface_id,
                channel_address=self._address,
                paramset_key=ParamsetKey.VALUES,
                parameter=parameter,
            )
        ):
            return dp
        return self._generic_data_points.get(
            DataPointKey(
                interface_id=self._device.interface_id,
                channel_address=self._address,
                paramset_key=ParamsetKey.MASTER,
                parameter=parameter,
            )
        )

    def get_generic_event(
        self, *, parameter: str | None = None, state_path: str | None = None
    ) -> GenericEventProtocolAny | None:
        """Return a generic event from device."""
        if state_path is not None and (dpk := self._state_path_to_dpk.get(state_path)) is not None:
            return self._generic_events.get(dpk)
        if parameter is None:
            return None

        return self._generic_events.get(
            DataPointKey(
                interface_id=self._device.interface_id,
                channel_address=self._address,
                paramset_key=ParamsetKey.VALUES,
                parameter=parameter,
            )
        )

    def get_readable_data_points(self, *, paramset_key: ParamsetKey) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the list of readable master data points."""
        return tuple(
            ge for ge in self._generic_data_points.values() if ge.is_readable and ge.paramset_key == paramset_key
        )

    def has_link_source_category(self, *, category: DataPointCategory) -> bool:
        """Return if channel is receiver."""
        return category in self._link_source_categories

    def has_link_target_category(self, *, category: DataPointCategory) -> bool:
        """Return if channel is transmitter."""
        return category in self._link_target_categories

    def init_channel(self) -> None:
        """Initialize the channel."""
        self._device.task_scheduler.create_task(target=self.init_link_peer(), name=f"init_channel_{self._address}")

    async def init_link_peer(self) -> None:
        """Initialize the link partners."""
        if self._link_source_categories and self._device.model not in VIRTUAL_REMOTE_MODELS:
            try:
                link_peer_addresses = await self._device.client.get_link_peers(address=self._address)
            except ClientException:
                # Device may have been deleted or is temporarily unavailable
                _LOGGER.debug("INIT_LINK_PEER: Failed to get link peers for %s", self._address)
                return
            if self._link_peer_addresses != link_peer_addresses:
                self._link_peer_addresses = link_peer_addresses
                self.publish_link_peer_changed_event()

    async def load_values(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Load data for the channel."""
        for ge in self._generic_data_points.values():
            await ge.load_data_point_value(call_source=call_source, direct_call=direct_call)
        for gev in self._generic_events.values():
            await gev.load_data_point_value(call_source=call_source, direct_call=direct_call)
        for cdp in self._calculated_data_points.values():
            await cdp.load_data_point_value(call_source=call_source, direct_call=direct_call)
        if self._custom_data_point:
            await self._custom_data_point.load_data_point_value(call_source=call_source, direct_call=direct_call)

    async def on_config_changed(self) -> None:
        """Do what is needed on device config change."""
        # reload paramset_descriptions
        await self._reload_paramset_descriptions()

        # re init link peers
        await self.init_link_peer()

        for ge in self._generic_data_points.values():
            await ge.on_config_changed()
        for gev in self._generic_events.values():
            await gev.on_config_changed()
        for cdp in self._calculated_data_points.values():
            await cdp.on_config_changed()
        if self._custom_data_point:
            await self._custom_data_point.on_config_changed()

    @loop_check
    def publish_link_peer_changed_event(self) -> None:
        """Do what is needed when the link peer has been changed for the device."""

        # Publish to EventBus asynchronously
        async def _publish_link_peer_changed() -> None:
            await self._device.event_bus_provider.event_bus.publish(
                event=LinkPeerChangedEvent(
                    timestamp=datetime.now(),
                    channel_address=self._address,
                )
            )

        self._device.task_scheduler.create_task(
            target=_publish_link_peer_changed,
            name=f"link-peer-changed-{self._address}",
        )

    def remove(self) -> None:
        """Remove data points from collections and central."""
        for event in self.generic_events:
            self._remove_data_point(data_point=event)
        self._generic_events.clear()

        for ccdp in self.calculated_data_points:
            self._remove_data_point(data_point=ccdp)
        self._calculated_data_points.clear()

        for gdp in self.generic_data_points:
            self._remove_data_point(data_point=gdp)
        self._generic_data_points.clear()

        if self._custom_data_point:
            self._remove_data_point(data_point=self._custom_data_point)
        self._state_path_to_dpk.clear()

        # Clean up channel-level EventBus subscriptions (e.g., LinkPeerChangedEvent)
        self._device.event_bus_provider.event_bus.clear_subscriptions_by_key(event_key=self._address)

    @inspector(scope=ServiceScope.INTERNAL)
    async def remove_central_link(self) -> None:
        """Remove a central link."""
        if self._has_key_press_events and await self._has_central_link() and not await self._has_program_ids():
            await self._device.client.report_value_usage(
                address=self._address, value_id=REPORT_VALUE_USAGE_VALUE_ID, ref_counter=0
            )

    @inspector
    async def rename(self, *, new_name: str) -> bool:
        """Rename the channel on the CCU."""
        return await self._device.client.rename_channel(rega_id=self._rega_id, new_name=new_name)

    def subscribe_to_link_peer_changed(self, *, handler: LinkPeerChangedHandler) -> UnsubscribeCallback:
        """Subscribe to the link peer changed event."""

        # Create adapter that filters for this channel's events
        def event_handler(*, event: LinkPeerChangedEvent) -> None:
            if event.channel_address == self._address:
                handler()

        return self._device.event_bus_provider.event_bus.subscribe(
            event_type=LinkPeerChangedEvent,
            event_key=self._address,
            handler=event_handler,
        )

    async def _has_central_link(self) -> bool:
        """Check if central link exists."""
        try:
            if metadata := await self._device.client.get_metadata(
                address=self._address, data_id=REPORT_VALUE_USAGE_DATA
            ):
                return any(
                    key
                    for key, value in metadata.items()
                    if isinstance(key, str)
                    and isinstance(value, int)
                    and key == REPORT_VALUE_USAGE_VALUE_ID
                    and value > 0
                )
        except BaseHomematicException as bhexc:
            _LOGGER.debug("HAS_CENTRAL_LINK failed: %s", extract_exc_args(exc=bhexc))
        return False

    async def _has_program_ids(self) -> bool:
        """Return if a channel has program ids."""
        return bool(await self._device.client.has_program_ids(rega_id=self._rega_id))

    @inspector(scope=ServiceScope.INTERNAL)
    async def _reload_paramset_descriptions(self) -> None:
        """Reload paramset for channel."""
        for paramset_key in self._paramset_keys:
            await self._device.client.fetch_paramset_description(
                channel_address=self._address,
                paramset_key=paramset_key,
            )

    def _remove_data_point(self, *, data_point: CallbackDataPointProtocol) -> None:
        """Remove a data_point from a channel."""
        # Clean up internal subscriptions for custom/calculated data points
        if isinstance(data_point, (hmce.CustomDataPoint, CalculatedDataPointProtocol)):
            data_point.unsubscribe_from_data_point_updated()

        # Remove from collections
        if isinstance(data_point, BaseParameterDataPointProtocol):
            self._state_path_to_dpk.pop(data_point.state_path, None)
        if isinstance(data_point, CalculatedDataPointProtocol):
            self._calculated_data_points.pop(data_point.dpk, None)
        if isinstance(data_point, GenericDataPointProtocol):
            self._generic_data_points.pop(data_point.dpk, None)
        if isinstance(data_point, hmce.CustomDataPoint):
            self._custom_data_point = None
        if isinstance(data_point, GenericEventProtocol):
            self._generic_events.pop(data_point.dpk, None)

        # Publish removed event and cleanup subscriptions (async, cleanup after event)
        data_point.publish_device_removed_event()

    def _set_modified_at(self) -> None:
        self._modified_at = datetime.now()


class _ValueCache:
    """
    Cache for lazy loading and temporary storage of parameter values.

    This cache minimizes RPC calls by storing fetched parameter values and
    providing them on subsequent requests within a validity period.

    External access
    ---------------
    Accessed via ``device.value_cache`` property. Used by DataPoint classes in
    ``model/data_point.py`` to load values via ``get_value()``.

    Cache strategy
    --------------
    - First checks the central data cache for VALUES paramset
    - Falls back to device-local cache with timestamp-based validity
    - Uses semaphore for thread-safe concurrent access
    """

    __slots__ = (
        "_device",
        "_device_cache",
        "_sema_get_or_load_value",
    )

    _NO_VALUE_CACHE_ENTRY: Final = "NO_VALUE_CACHE_ENTRY"

    def __init__(self, *, device: DeviceProtocol) -> None:
        """Initialize the value cache."""
        self._sema_get_or_load_value: Final = asyncio.Semaphore()
        self._device: Final = device
        # {key, CacheEntry}
        self._device_cache: Final[dict[DataPointKey, CacheEntry]] = {}

    async def get_value(
        self,
        *,
        dpk: DataPointKey,
        call_source: CallSource,
        direct_call: bool = False,
    ) -> Any:
        """Load data."""
        async with self._sema_get_or_load_value:
            if direct_call is False and (cached_value := self._get_value_from_cache(dpk=dpk)) != NO_CACHE_ENTRY:
                return NO_CACHE_ENTRY if cached_value == self._NO_VALUE_CACHE_ENTRY else cached_value

            value_dict: dict[str, Any] = {dpk.parameter: self._NO_VALUE_CACHE_ENTRY}
            try:
                value_dict = await self._get_values_for_cache(dpk=dpk)
            except BaseHomematicException as bhexc:
                _LOGGER.debug(
                    "GET_OR_LOAD_VALUE: Failed to get data for %s, %s, %s, %s: %s",
                    self._device.model,
                    dpk.channel_address,
                    dpk.parameter,
                    call_source,
                    extract_exc_args(exc=bhexc),
                )
            for d_parameter, d_value in value_dict.items():
                self._add_entry_to_device_cache(
                    dpk=DataPointKey(
                        interface_id=dpk.interface_id,
                        channel_address=dpk.channel_address,
                        paramset_key=dpk.paramset_key,
                        parameter=d_parameter,
                    ),
                    value=d_value,
                )
            return (
                NO_CACHE_ENTRY
                if (value := value_dict.get(dpk.parameter)) and value == self._NO_VALUE_CACHE_ENTRY
                else value
            )

    async def init_base_data_points(self) -> None:
        """Load data by get_value."""
        try:
            for dp in self._get_base_data_points():
                await dp.load_data_point_value(call_source=CallSource.HM_INIT)
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "init_base_data_points: Failed to init cache for channel0 %s, %s [%s]",
                self._device.model,
                self._device.address,
                extract_exc_args(exc=bhexc),
            )

    async def init_readable_events(self) -> None:
        """Load data by get_value."""
        try:
            for event in self._get_readable_events():
                await event.load_data_point_value(call_source=CallSource.HM_INIT)
        except BaseHomematicException as bhexc:
            _LOGGER.debug(
                "init_base_events: Failed to init cache for channel0 %s, %s [%s]",
                self._device.model,
                self._device.address,
                extract_exc_args(exc=bhexc),
            )

    def _add_entry_to_device_cache(self, *, dpk: DataPointKey, value: Any) -> None:
        """Add value to cache."""
        # write value to cache even if an exception has occurred
        # to avoid repetitive calls to the backend within max_age
        self._device_cache[dpk] = CacheEntry(value=value, refresh_at=datetime.now())

    def _get_base_data_points(self) -> set[GenericDataPointProtocolAny]:
        """Get data points of channel 0 and master."""
        return {
            dp
            for dp in self._device.generic_data_points
            if (
                dp.channel.no == 0
                and dp.paramset_key == ParamsetKey.VALUES
                and dp.parameter in RELEVANT_INIT_PARAMETERS
            )
            or dp.paramset_key == ParamsetKey.MASTER
        }

    def _get_readable_events(self) -> set[GenericEventProtocolAny]:
        """Get readable events."""
        return {event for event in self._device.generic_events if event.is_readable}

    def _get_value_from_cache(
        self,
        *,
        dpk: DataPointKey,
    ) -> Any:
        """Load data from store."""
        # Try to get data from central cache
        if (
            dpk.paramset_key == ParamsetKey.VALUES
            and (
                global_value := self._device.data_cache_provider.get_data(
                    interface=self._device.interface,
                    channel_address=dpk.channel_address,
                    parameter=dpk.parameter,
                )
            )
            != NO_CACHE_ENTRY
        ):
            return global_value

        if (cache_entry := self._device_cache.get(dpk, CacheEntry.empty())) and cache_entry.is_valid:
            return cache_entry.value
        return NO_CACHE_ENTRY

    async def _get_values_for_cache(self, *, dpk: DataPointKey) -> dict[str, Any]:
        """Return a value from the backend to store in cache."""
        if not self._device.available:
            _LOGGER.debug(
                "GET_VALUES_FOR_CACHE failed: device %s (%s) is not available", self._device.name, self._device.address
            )
            return {}
        if dpk.paramset_key == ParamsetKey.VALUES:
            return {
                dpk.parameter: await self._device.client.get_value(
                    channel_address=dpk.channel_address,
                    paramset_key=dpk.paramset_key,
                    parameter=dpk.parameter,
                    call_source=CallSource.HM_INIT,
                )
            }
        return await self._device.client.get_paramset(
            address=dpk.channel_address, paramset_key=dpk.paramset_key, call_source=CallSource.HM_INIT
        )


class _DefinitionExporter:
    """
    Export device and paramset descriptions for diagnostics.

    This internal utility class exports device definitions to JSON files for
    debugging and issue reporting. Device addresses are anonymized before export.

    Internal use only
    -----------------
    Used exclusively by ``Device.export_device_definition()``. Not accessible
    from external code.

    Output files
    ------------
    - ``{storage_dir}/device_descriptions/{model}.json`` - Device descriptions
    - ``{storage_dir}/paramset_descriptions/{model}.json`` - Paramset descriptions
    """

    __slots__ = (
        "_client",
        "_config_provider",
        "_device_address",
        "_device_description_provider",
        "_interface_id",
        "_random_id",
        "_storage_directory",
        "_task_scheduler",
    )

    def __init__(self, *, device: DeviceProtocol) -> None:
        """Initialize the device exporter."""
        self._client: Final = device.client
        self._config_provider: Final = device.config_provider
        self._device_description_provider: Final = device.device_description_provider
        self._task_scheduler: Final = device.task_scheduler
        self._storage_directory: Final = self._config_provider.config.storage_directory
        self._interface_id: Final = device.interface_id
        self._device_address: Final = device.address
        self._random_id: Final[str] = f"VCU{int(random.randint(1000000, 9999999))}"

    @inspector(scope=ServiceScope.INTERNAL)
    async def export_data(self) -> None:
        """Export data."""
        device_descriptions: Mapping[str, DeviceDescription] = (
            self._device_description_provider.get_device_with_channels(
                interface_id=self._interface_id, device_address=self._device_address
            )
        )
        paramset_descriptions: dict[
            str, dict[ParamsetKey, dict[str, ParameterData]]
        ] = await self._client.get_all_paramset_descriptions(device_descriptions=tuple(device_descriptions.values()))
        model = device_descriptions[self._device_address]["TYPE"]
        file_name = f"{model}.json"

        # anonymize device_descriptions
        anonymize_device_descriptions: list[DeviceDescription] = []
        for device_description in device_descriptions.values():
            new_device_description: DeviceDescription = device_description.copy()
            new_device_description["ADDRESS"] = self._anonymize_address(address=new_device_description["ADDRESS"])
            if new_device_description.get("PARENT"):
                new_device_description["PARENT"] = new_device_description["ADDRESS"].split(ADDRESS_SEPARATOR)[0]
            elif new_device_description.get("CHILDREN"):
                new_device_description["CHILDREN"] = [
                    self._anonymize_address(address=a) for a in new_device_description["CHILDREN"]
                ]
            anonymize_device_descriptions.append(new_device_description)

        # anonymize paramset_descriptions
        anonymize_paramset_descriptions: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        for address, paramset_description in paramset_descriptions.items():
            anonymize_paramset_descriptions[self._anonymize_address(address=address)] = paramset_description

        # Save device_descriptions for device to file.
        await self._save(
            directory=f"{self._storage_directory}/{DEVICE_DESCRIPTIONS_DIR}",
            file_name=file_name,
            data=anonymize_device_descriptions,
        )

        # Save device_descriptions for device to file.
        await self._save(
            directory=f"{self._storage_directory}/{PARAMSET_DESCRIPTIONS_DIR}",
            file_name=file_name,
            data=anonymize_paramset_descriptions,
        )

    def _anonymize_address(self, *, address: str) -> str:
        address_parts = address.split(ADDRESS_SEPARATOR)
        address_parts[0] = self._random_id
        return ADDRESS_SEPARATOR.join(address_parts)

    async def _save(self, *, directory: str, file_name: str, data: Any) -> DataOperationResult:
        """Save file to disk."""

        def perform_save() -> DataOperationResult:
            if not check_or_create_directory(directory=directory):
                return DataOperationResult.NO_SAVE  # pragma: no cover
            with open(file=os.path.join(directory, file_name), mode="wb") as fptr:
                fptr.write(orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS))
            return DataOperationResult.SAVE_SUCCESS

        return cast(
            DataOperationResult,
            await self._task_scheduler.async_add_executor_job(perform_save, name="save-device-description"),
        )
