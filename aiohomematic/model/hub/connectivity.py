# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Hub sensors for interface connectivity status.

This module provides binary sensor data points for monitoring the
connectivity status of each CCU interface. These sensors show whether
each interface is connected and operational.

Public API
----------
- HmInterfaceConnectivitySensor: Binary sensor showing interface connectivity
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Final, override

from slugify import slugify

from aiohomematic.const import CONNECTIVITY_SENSOR_PREFIX, HUB_ADDRESS, DataPointCategory, HubValueType, Interface
from aiohomematic.interfaces import (
    CentralInfoProtocol,
    ChannelProtocol,
    ConfigProviderProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
    HealthTrackerProtocol,
    HubBinarySensorDataPointProtocol,
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import HubPathData, PathData, generate_unique_id, get_hub_data_point_name_data
from aiohomematic.property_decorators import DelegatedProperty, Kind, state_property
from aiohomematic.support import PayloadMixin

_LOGGER: Final = logging.getLogger(__name__)


class HmInterfaceConnectivitySensor(CallbackDataPoint, HubBinarySensorDataPointProtocol, PayloadMixin):
    """
    Binary sensor showing interface connectivity status.

    This sensor provides a clear indication of whether a specific
    interface (e.g., HmIP-RF, BidCos-RF) is connected and operational.

    States:
        - True (ON): Interface is connected and circuit breakers are closed
        - False (OFF): Interface is disconnected, failed, or degraded

    The sensor is always available (never shows unavailable) since its
    purpose is to show the connection state itself.
    """

    __slots__ = (
        "_cached_value",
        "_health_tracker",
        "_interface",
        "_interface_id",
        "_name_data",
        "_state_uncertain",
    )

    _category = DataPointCategory.HUB_BINARY_SENSOR
    _enabled_default = True

    def __init__(
        self,
        *,
        interface_id: str,
        interface: Interface,
        health_tracker: HealthTrackerProtocol,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
    ) -> None:
        """Initialize the connectivity sensor."""
        PayloadMixin.__init__(self)
        self._interface_id: Final = interface_id
        self._interface: Final = interface
        self._health_tracker: Final = health_tracker

        # Create unique ID and name
        sensor_name = f"{CONNECTIVITY_SENSOR_PREFIX} {interface.value}"
        unique_id: Final = generate_unique_id(
            config_provider=config_provider,
            address=HUB_ADDRESS,
            parameter=slugify(f"connectivity_{interface_id}"),
        )
        self._name_data: Final = get_hub_data_point_name_data(
            channel=None, legacy_name=sensor_name, central_name=central_info.name
        )

        super().__init__(
            unique_id=unique_id,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
        )
        self._state_uncertain: bool = True
        self._cached_value: bool = False

    enabled_default: Final = DelegatedProperty[bool](path="_enabled_default")
    full_name: Final = DelegatedProperty[str](path="_name_data.full_name")
    name: Final = DelegatedProperty[str](path="_name_data.name", kind=Kind.CONFIG)
    state_uncertain: Final = DelegatedProperty[bool](path="_state_uncertain")

    @property
    def available(self) -> bool:
        """
        Return True - connectivity sensor is always available.

        The sensor itself shows the connection state, so it should
        never be marked unavailable.
        """
        return True

    @property
    def channel(self) -> ChannelProtocol | None:
        """Return the identified channel."""
        return None

    @property
    def data_type(self) -> HubValueType | None:
        """Return the data type of the sensor."""
        return HubValueType.LOGIC

    @property
    def description(self) -> str | None:
        """Return data point description."""
        return f"Connectivity status for {self._interface.value} interface"

    @property
    def interface(self) -> Interface:
        """Return the interface type."""
        return self._interface

    @property
    def interface_id(self) -> str:
        """Return the interface ID."""
        return self._interface_id

    @property
    def legacy_name(self) -> str | None:
        """Return the original name."""
        return None

    @property
    def translation_key(self) -> str:
        """Return translation key for Home Assistant."""
        return "interface_connectivity"

    @state_property
    def value(self) -> bool:
        """Return True if interface is connected."""
        return self._get_current_value()

    def refresh(self, *, write_at: datetime) -> None:
        """Refresh the sensor value from health tracker."""
        current_value = self._get_current_value()
        if self._cached_value != current_value:
            self._cached_value = current_value
            self._set_modified_at(modified_at=write_at)
        else:
            self._set_refreshed_at(refreshed_at=write_at)
        self._state_uncertain = False
        self.publish_data_point_updated_event()

    def _get_current_value(self) -> bool:
        """Return the current connectivity value."""
        if (health := self._health_tracker.get_client_health(interface_id=self._interface_id)) is not None:
            return health.is_available
        return False

    @override
    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return HubPathData(name=slugify(f"connectivity_{self._interface.value}"))

    @override
    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self.name}"
