# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Device query facade for centralized data point and event lookups.

This module extracts the query-oriented methods from CentralUnit into a
dedicated facade, reducing CentralUnit's responsibility surface and grouping
related read-only lookups in one place.

Public API of this module is defined by __all__.
"""

import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.const import (
    IGNORE_FOR_UN_IGNORE_PARAMETERS,
    UN_IGNORE_WILDCARD,
    DataPointCategory,
    DeviceTriggerEventType,
    Interface,
    Operations,
    ParamsetKey,
)
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.interfaces.central import DeviceQueryFacadeProtocol
from aiohomematic.interfaces.model import (
    CallbackDataPointProtocol,
    ChannelEventGroupProtocol,
    CustomDataPointProtocol,
    GenericDataPointProtocol,
    GenericDataPointProtocolAny,
    GenericEventProtocolAny,
)
from aiohomematic.support.address import get_channel_no, get_device_address

if TYPE_CHECKING:
    from aiohomematic.central.coordinators import CacheCoordinator, ClientCoordinator, DeviceCoordinator, HubCoordinator
    from aiohomematic.central.device_registry import DeviceRegistry

__all__ = ["DeviceQueryFacade"]

_LOGGER: Final = logging.getLogger(__name__)


class DeviceQueryFacade(DeviceQueryFacadeProtocol):
    """
    Facade for querying devices, data points, and events.

    Aggregates the 12 query methods previously hosted directly on CentralUnit.
    All methods are read-only lookups; mutation is still handled by coordinators.

    Dependencies are injected via constructor to keep the facade decoupled
    from CentralUnit.
    """

    __slots__ = (
        "_cache_coordinator",
        "_client_coordinator",
        "_device_coordinator",
        "_device_registry",
        "_hub_coordinator",
    )

    def __init__(
        self,
        *,
        device_registry: DeviceRegistry,
        device_coordinator: DeviceCoordinator,
        cache_coordinator: CacheCoordinator,
        client_coordinator: ClientCoordinator,
        hub_coordinator: HubCoordinator,
    ) -> None:
        """Initialize the query facade."""
        self._device_registry: Final = device_registry
        self._device_coordinator: Final = device_coordinator
        self._cache_coordinator: Final = cache_coordinator
        self._client_coordinator: Final = client_coordinator
        self._hub_coordinator: Final = hub_coordinator

    def get_custom_data_point(self, *, address: str, channel_no: int) -> CustomDataPointProtocol | None:
        """Return the hm custom_data_point."""
        if device := self._device_coordinator.get_device(address=address):
            return device.get_custom_data_point(channel_no=channel_no)
        return None

    def get_data_point_by_custom_id(self, *, custom_id: str) -> CallbackDataPointProtocol | None:
        """Return Homematic data_point by custom_id."""
        for device in self._device_registry.devices:
            for dp in device.get_data_points(registered=True):
                if dp.custom_id == custom_id:
                    return dp
        return None

    def get_data_points(
        self,
        *,
        category: DataPointCategory | None = None,
        interface: Interface | None = None,
        exclude_no_create: bool = True,
        registered: bool | None = None,
    ) -> tuple[CallbackDataPointProtocol, ...]:
        """Return all externally registered data points."""
        all_data_points: list[CallbackDataPointProtocol] = []
        for device in self._device_registry.devices:
            if interface and interface != device.interface:
                continue
            all_data_points.extend(
                device.get_data_points(category=category, exclude_no_create=exclude_no_create, registered=registered)
            )
        return tuple(all_data_points)

    def get_event(
        self, *, channel_address: str | None = None, parameter: str | None = None, state_path: str | None = None
    ) -> GenericEventProtocolAny | None:
        """Return the hm event."""
        if channel_address is None:
            for dev in self._device_registry.devices:
                if event := dev.get_generic_event(parameter=parameter, state_path=state_path):
                    return event
            return None

        if device := self._device_coordinator.get_device(address=channel_address):
            return device.get_generic_event(channel_address=channel_address, parameter=parameter, state_path=state_path)
        return None

    def get_event_groups(
        self,
        *,
        event_type: DeviceTriggerEventType,
        registered: bool | None = None,
    ) -> tuple[ChannelEventGroupProtocol, ...]:
        """
        Return all channel event groups for the given event type.

        Each ChannelEventGroup is a virtual data point bound to its channel,
        providing unified access for Home Assistant entity creation.

        Args:
            event_type: The event type to filter by.
            registered: Filter by registration status (None = all).

        Returns:
            Tuple of ChannelEventGroup instances.

        """
        groups: list[ChannelEventGroupProtocol] = []
        for device in self._device_registry.devices:
            for channel in device.channels.values():
                if (event_group := channel.event_groups.get(event_type)) is None:
                    continue
                # Filter by registration status
                if registered is not None and event_group.is_registered != registered:
                    continue
                groups.append(event_group)
        return tuple(groups)

    def get_events(
        self, *, event_type: DeviceTriggerEventType, registered: bool | None = None
    ) -> tuple[tuple[GenericEventProtocolAny, ...], ...]:
        """Return all channel event data points."""
        hm_channel_events: list[tuple[GenericEventProtocolAny, ...]] = []
        for device in self._device_registry.devices:
            for channel_events in device.get_events(event_type=event_type).values():
                if registered is None or (channel_events[0].is_registered == registered):
                    hm_channel_events.append(channel_events)
                    continue
        return tuple(hm_channel_events)

    def get_generic_data_point(
        self,
        *,
        channel_address: str | None = None,
        parameter: str | None = None,
        paramset_key: ParamsetKey | None = None,
        state_path: str | None = None,
    ) -> GenericDataPointProtocolAny | None:
        """Get data_point by channel_address and parameter."""
        if channel_address is None:
            for dev in self._device_registry.devices:
                if dp := dev.get_generic_data_point(
                    parameter=parameter, paramset_key=paramset_key, state_path=state_path
                ):
                    return dp
            return None

        if device := self._device_coordinator.get_device(address=channel_address):
            return device.get_generic_data_point(
                channel_address=channel_address, parameter=parameter, paramset_key=paramset_key, state_path=state_path
            )
        return None

    async def get_install_mode(self, *, interface: Interface) -> int:
        """
        Return the remaining time in install mode for an interface.

        Args:
            interface: The interface to query (HMIP_RF or BIDCOS_RF).

        Returns:
            Remaining time in seconds, or 0 if not in install mode.

        """
        try:
            client = self._client_coordinator.get_client(interface=interface)
            return await client.get_install_mode()
        except AioHomematicException:
            return 0

    def get_parameters(
        self,
        *,
        paramset_key: ParamsetKey,
        operations: tuple[Operations, ...],
        full_format: bool = False,
        un_ignore_candidates_only: bool = False,
        use_channel_wildcard: bool = False,
    ) -> tuple[str, ...]:
        """
        Return all parameters from VALUES paramset.

        Performance optimized to minimize repeated lookups and computations
        when iterating over all channels and parameters.
        """
        parameters: set[str] = set()

        # Precompute operations mask to avoid repeated checks in the inner loop
        op_mask: int = 0
        for op in operations:
            op_mask |= int(op)

        raw_psd = self._cache_coordinator.paramset_descriptions.raw_paramset_descriptions
        ignore_set = IGNORE_FOR_UN_IGNORE_PARAMETERS

        # Prepare optional helpers only if needed
        get_model = self._cache_coordinator.device_descriptions.get_model if full_format else None
        model_cache: dict[str, str | None] = {}
        channel_no_cache: dict[str, int | None] = {}

        for channels in raw_psd.values():
            for channel_address, channel_paramsets in channels.items():
                # Resolve model lazily and cache per device address when full_format is requested
                model: str | None = None
                if get_model is not None:
                    dev_addr = get_device_address(address=channel_address)
                    if (model := model_cache.get(dev_addr)) is None:
                        model = get_model(device_address=dev_addr)
                        model_cache[dev_addr] = model

                if (paramset := channel_paramsets.get(paramset_key)) is None:
                    continue

                for parameter, parameter_data in paramset.items():
                    # Fast bitmask check: ensure all requested ops are present
                    if (int(parameter_data["OPERATIONS"]) & op_mask) != op_mask:
                        continue

                    if un_ignore_candidates_only:
                        # Cheap check first to avoid expensive dp lookup when possible
                        if parameter in ignore_set:
                            continue
                        dp = self.get_generic_data_point(
                            channel_address=channel_address,
                            parameter=parameter,
                            paramset_key=paramset_key,
                        )
                        if dp and dp.enabled_default and not dp.is_un_ignored:
                            continue

                    if not full_format:
                        parameters.add(parameter)
                        continue

                    if use_channel_wildcard:
                        channel_repr: int | str | None = UN_IGNORE_WILDCARD
                    elif channel_address in channel_no_cache:
                        channel_repr = channel_no_cache[channel_address]
                    else:
                        channel_repr = get_channel_no(address=channel_address)
                        channel_no_cache[channel_address] = channel_repr

                    # Build the full parameter string
                    if channel_repr is None:
                        parameters.add(f"{parameter}:{paramset_key}@{model}:")
                    else:
                        parameters.add(f"{parameter}:{paramset_key}@{model}:{channel_repr}")

        return tuple(parameters)

    def get_readable_generic_data_points(
        self, *, paramset_key: ParamsetKey | None = None, interface: Interface | None = None
    ) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the readable generic data points."""
        return tuple(
            ge
            for ge in self.get_data_points(interface=interface)
            if (
                isinstance(ge, GenericDataPointProtocol)
                and ge.is_readable
                and ((paramset_key and ge.paramset_key == paramset_key) or paramset_key is None)
            )
        )

    def get_state_paths(self, *, rpc_callback_supported: bool | None = None) -> tuple[str, ...]:
        """Return the data point paths."""
        data_point_paths: list[str] = []
        for device in self._device_registry.devices:
            if rpc_callback_supported is None or device.client.capabilities.rpc_callback == rpc_callback_supported:
                data_point_paths.extend(device.data_point_paths)
        data_point_paths.extend(self._hub_coordinator.data_point_paths)
        return tuple(data_point_paths)

    def get_un_ignore_candidates(self, *, include_master: bool = False) -> list[str]:
        """Return the candidates for un_ignore."""
        candidates = sorted(
            # 1. request simple parameter list for values parameters
            self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                un_ignore_candidates_only=True,
            )
            # 2. request full_format parameter list with channel wildcard for values parameters
            + self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                full_format=True,
                un_ignore_candidates_only=True,
                use_channel_wildcard=True,
            )
            # 3. request full_format parameter list for values parameters
            + self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                full_format=True,
                un_ignore_candidates_only=True,
            )
        )
        if include_master:
            # 4. request full_format parameter list for master parameters
            candidates += sorted(
                self.get_parameters(
                    paramset_key=ParamsetKey.MASTER,
                    operations=(Operations.READ,),
                    full_format=True,
                    un_ignore_candidates_only=True,
                )
            )
        return candidates
