# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Hub sensors for system metrics.

This module provides hub sensor data points for exposing key system metrics
to Home Assistant. These sensors allow monitoring of system health,
connection latency, and event timing without needing separate diagnostic entities.

Public API
----------
- HmSystemHealthSensor: Overall system health score (0-100%)
- HmConnectionLatencySensor: Average RPC connection latency in milliseconds
- HmLastEventAgeSensor: Seconds since last backend event
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Final

from slugify import slugify

from aiohomematic.const import (
    HUB_ADDRESS,
    METRICS_SENSOR_CONNECTION_LATENCY_NAME,
    METRICS_SENSOR_LAST_EVENT_AGE_NAME,
    METRICS_SENSOR_SYSTEM_HEALTH_NAME,
    DataPointCategory,
    HubValueType,
)
from aiohomematic.interfaces.central import (
    CentralInfoProtocol,
    ConfigProviderProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
)
from aiohomematic.interfaces.model import ChannelProtocol, HubSensorDataPointProtocol
from aiohomematic.interfaces.operations import (
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import HubPathData, PathData, generate_unique_id, get_hub_data_point_name_data
from aiohomematic.property_decorators import DelegatedProperty, Kind, config_property, state_property
from aiohomematic.support import PayloadMixin

if TYPE_CHECKING:
    from aiohomematic.central.metrics import MetricsAggregator

_LOGGER: Final = logging.getLogger(__name__)


class _BaseMetricsSensor(CallbackDataPoint, HubSensorDataPointProtocol, PayloadMixin):
    """Base class for metrics hub sensors."""

    __slots__ = (
        "_metrics_aggregator",
        "_name_data",
        "_previous_value",
        "_sensor_name",
        "_state_uncertain",
    )

    _category = DataPointCategory.HUB_SENSOR
    _enabled_default = True

    def __init__(
        self,
        *,
        sensor_name: str,
        metrics_aggregator: MetricsAggregator,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
    ) -> None:
        """Initialize the metrics sensor."""
        PayloadMixin.__init__(self)
        self._sensor_name: Final = sensor_name
        self._metrics_aggregator: Final = metrics_aggregator
        unique_id: Final = generate_unique_id(
            config_provider=config_provider,
            address=HUB_ADDRESS,
            parameter=slugify(sensor_name),
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
        self._previous_value: float = 0.0

    available: Final = DelegatedProperty[bool](path="_central_info.available", kind=Kind.STATE)
    enabled_default: Final = DelegatedProperty[bool](path="_enabled_default")
    full_name: Final = DelegatedProperty[str](path="_name_data.full_name")
    name: Final = DelegatedProperty[str](path="_name_data.name", kind=Kind.CONFIG)
    state_uncertain: Final = DelegatedProperty[bool](path="_state_uncertain")

    @property
    def channel(self) -> ChannelProtocol | None:
        """Return the identified channel."""
        return None

    @property
    def data_type(self) -> HubValueType | None:
        """Return the data type of the sensor."""
        return HubValueType.FLOAT

    @property
    def description(self) -> str | None:
        """Return data point description."""
        return None

    @property
    def legacy_name(self) -> str | None:
        """Return the original name."""
        return None

    def refresh(self, *, write_at: datetime) -> None:
        """Refresh the sensor value from metrics aggregator."""
        current_value = self._get_current_value()
        if self._previous_value != current_value:
            self._previous_value = current_value
            self._set_modified_at(modified_at=write_at)
        else:
            self._set_refreshed_at(refreshed_at=write_at)
        self._state_uncertain = False
        self.publish_data_point_updated_event()

    def _get_current_value(self) -> float:
        """Return the current metric value. Override in subclasses."""
        raise NotImplementedError

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return HubPathData(name=slugify(self._sensor_name))

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self.name}"


class HmSystemHealthSensor(_BaseMetricsSensor):
    """
    Hub sensor for system health score.

    Exposes the overall system health as a percentage (0-100%).
    The health score is derived from client connection states.
    """

    __slots__ = ()

    def __init__(
        self,
        *,
        metrics_aggregator: MetricsAggregator,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
    ) -> None:
        """Initialize the system health sensor."""
        super().__init__(
            sensor_name=METRICS_SENSOR_SYSTEM_HEALTH_NAME,
            metrics_aggregator=metrics_aggregator,
            config_provider=config_provider,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
        )

    @config_property
    def unit(self) -> str | None:
        """Return the unit of the data_point."""
        return "%"

    @state_property
    def value(self) -> float:
        """Return the system health score as percentage (0-100)."""
        return self._get_current_value()

    def _get_current_value(self) -> float:
        """Return the current health score as percentage."""
        return round(self._metrics_aggregator.health.overall_score * 100, 1)


class HmConnectionLatencySensor(_BaseMetricsSensor):
    """
    Hub sensor for connection latency.

    Exposes the average RPC connection latency in milliseconds.
    """

    __slots__ = ()

    def __init__(
        self,
        *,
        metrics_aggregator: MetricsAggregator,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
    ) -> None:
        """Initialize the connection latency sensor."""
        super().__init__(
            sensor_name=METRICS_SENSOR_CONNECTION_LATENCY_NAME,
            metrics_aggregator=metrics_aggregator,
            config_provider=config_provider,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
        )

    @config_property
    def unit(self) -> str | None:
        """Return the unit of the data_point."""
        return "ms"

    @state_property
    def value(self) -> float:
        """Return the average connection latency in milliseconds."""
        return self._get_current_value()

    def _get_current_value(self) -> float:
        """Return the current average latency."""
        return round(self._metrics_aggregator.rpc.avg_latency_ms, 1)


class HmLastEventAgeSensor(_BaseMetricsSensor):
    """
    Hub sensor for last event age.

    Exposes the time in seconds since the last backend event was received.
    A value of -1 indicates no events have been received yet.
    """

    __slots__ = ()

    def __init__(
        self,
        *,
        metrics_aggregator: MetricsAggregator,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
    ) -> None:
        """Initialize the last event age sensor."""
        super().__init__(
            sensor_name=METRICS_SENSOR_LAST_EVENT_AGE_NAME,
            metrics_aggregator=metrics_aggregator,
            config_provider=config_provider,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
        )

    @config_property
    def unit(self) -> str | None:
        """Return the unit of the data_point."""
        return "s"

    @state_property
    def value(self) -> float:
        """Return the seconds since last backend event."""
        return self._get_current_value()

    def _get_current_value(self) -> float:
        """Return the current last event age in seconds."""
        return round(self._metrics_aggregator.health.last_event_age_seconds, 1)
