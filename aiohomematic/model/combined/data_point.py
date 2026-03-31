# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Base implementation for combined data points writing to multiple underlying data points.

Public API of this module is defined by __all__.
"""

from datetime import datetime
import logging
from typing import Final, Unpack, override
import weakref

from aiohomematic import ccu_translations
from aiohomematic.central.events import DataPointStateChangedEvent
from aiohomematic.const import (
    INIT_DATETIME,
    CallSource,
    DataPointKey,
    DataPointUsage,
    Field,
    Operations,
    ParameterType,
    ParamsetKey,
)
from aiohomematic.decorators import inspector
from aiohomematic.interfaces import CallbackDataPointProtocol, ChannelProtocol, GenericDataPointProtocolAny
from aiohomematic.model.custom.mixins import StateChangeArgs
from aiohomematic.model.data_point import BaseDataPoint
from aiohomematic.model.generic import DpDummy
from aiohomematic.model.support import (
    DataPointNameData,
    DataPointPathData,
    PathData,
    generate_translation_key,
    generate_unique_id,
    get_data_point_name_data,
)
from aiohomematic.property_decorators import DelegatedProperty, Kind, hm_property, state_property
from aiohomematic.type_aliases import UnsubscribeCallback

__all__ = ["CombinedDataPoint"]

_LOGGER: Final = logging.getLogger(__name__)


def _cleanup_callbacks(callbacks: list[UnsubscribeCallback]) -> None:  # kwonly: disable
    """Clean up subscription callbacks (invoked by weakref.finalize)."""
    for unreg in callbacks:
        if unreg is not None:
            unreg()
    callbacks.clear()


class CombinedDataPoint[ParameterT](BaseDataPoint, CallbackDataPointProtocol):
    """Base class for combined data points that write to multiple underlying data points."""

    __slots__ = (
        "_combined_parameter",
        "_current_value",
        "_data_points",
        "_default",
        "_max",
        "_min",
        "_operations",
        "_service",
        "_translation",
        "_type",
        "_unit",
        "_unsubscribe_callbacks",
        "_values",
        "_visible",
    )

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        combined_parameter: str,
        visible: bool = False,
    ) -> None:
        """Initialize the combined data point."""
        self._combined_parameter: Final = combined_parameter
        self._unsubscribe_callbacks: list[UnsubscribeCallback] = []
        unique_id = generate_unique_id(
            config_provider=channel.device.config_provider,
            address=channel.address,
            parameter=combined_parameter,
            prefix="combined",
        )
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=False,
        )
        self._data_points: Final[dict[Field, GenericDataPointProtocolAny]] = {}
        self._translation: Final[str | None] = ccu_translations.get_parameter_translation(
            parameter=combined_parameter,
            channel_type=channel.type_name,
            locale=channel.device.config_provider.config.locale,
        )
        self._current_value: ParameterT = None  # type: ignore[assignment]
        self._type: ParameterType = None  # type: ignore[assignment]
        self._values: tuple[str, ...] | None = None
        self._max: ParameterT = None  # type: ignore[assignment]
        self._min: ParameterT = None  # type: ignore[assignment]
        self._default: ParameterT = None  # type: ignore[assignment]
        self._visible: bool = visible
        self._service: bool = False
        self._operations: int = Operations.WRITE
        self._unit: str | None = None
        weakref.finalize(self, _cleanup_callbacks, self._unsubscribe_callbacks)

    _relevant_data_points: Final = DelegatedProperty[tuple[GenericDataPointProtocolAny, ...]](
        path="_readable_data_points"
    )
    hmtype: Final = DelegatedProperty[ParameterType](path="_type")
    max: Final = DelegatedProperty[ParameterT](path="_max", kind=Kind.CONFIG)
    min: Final = DelegatedProperty[ParameterT](path="_min", kind=Kind.CONFIG)
    parameter: Final = DelegatedProperty[str](path="_combined_parameter")
    service: Final = DelegatedProperty[bool](path="_service")
    translation: Final = DelegatedProperty[str | None](path="_translation", kind=Kind.INFO)
    unit: Final = DelegatedProperty[str | None](path="_unit", kind=Kind.CONFIG)
    values: Final = DelegatedProperty[tuple[str, ...] | None](path="_values", kind=Kind.CONFIG)
    visible: Final = DelegatedProperty[bool](path="_visible")

    @property
    def _readable_data_points(self) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the list of readable data points."""
        return tuple(dp for dp in self._data_points.values() if dp.is_readable)

    @property
    def _should_publish_data_point_updated_callback(self) -> bool:
        """Check if a data point has been updated or refreshed."""
        if self.published_event_recently:  # pylint: disable=using-constant-test
            return False
        return self.is_refreshed

    @property
    def data_point_name_postfix(self) -> str:
        """Return the data point name postfix."""
        return ""

    @property
    def has_data_points(self) -> bool:
        """Return if there are data points."""
        return len(self._data_points) > 0

    @property
    def has_events(self) -> bool:
        """Return if data_point supports events."""
        return bool(self._operations & Operations.EVENT)

    @property
    def is_readable(self) -> bool:
        """Return if data_point is readable."""
        return bool(self._operations & Operations.READ)

    @property
    def is_refreshed(self) -> bool:
        """Return if all relevant data_point have been refreshed (received a value)."""
        return all(dp.is_refreshed for dp in self._relevant_data_points)

    @property
    def is_status_valid(self) -> bool:
        """Return if all relevant data points have valid status."""
        return all(dp.is_status_valid for dp in self._relevant_data_points)

    @property
    def is_writable(self) -> bool:
        """Return if data_point is writable."""
        return bool(self._operations & Operations.WRITE)

    @property
    def multiplier(self) -> float:
        """Return multiplier value."""
        return 1.0

    @property
    def paramset_key(self) -> ParamsetKey:
        """Return paramset_key name."""
        return ParamsetKey.COMBINED

    @property
    def state_uncertain(self) -> bool:
        """Return if the state is uncertain."""
        return any(dp.state_uncertain for dp in self._relevant_data_points)

    @property
    def translation_key(self) -> str:
        """Return translation key for Home Assistant."""
        return generate_translation_key(name=self._combined_parameter)

    @state_property
    def modified_at(self) -> datetime:
        """Return the latest last update timestamp."""
        modified_at: datetime = INIT_DATETIME
        for dp in self._readable_data_points:
            if (data_point_modified_at := dp.modified_at) and data_point_modified_at > modified_at:
                modified_at = data_point_modified_at
        return modified_at

    @state_property
    def refreshed_at(self) -> datetime:
        """Return the latest last refresh timestamp."""
        refreshed_at: datetime = INIT_DATETIME
        for dp in self._readable_data_points:
            if (data_point_refreshed_at := dp.refreshed_at) and data_point_refreshed_at > refreshed_at:
                refreshed_at = data_point_refreshed_at
        return refreshed_at

    @hm_property(cached=True)
    def dpk(self) -> DataPointKey:
        """Return data_point key value."""
        return DataPointKey(
            interface_id=self._device.interface_id,
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.COMBINED,
            parameter=self._combined_parameter,
        )

    def is_state_change(self, **kwargs: Unpack[StateChangeArgs]) -> bool:
        """
        Check if the state changes due to kwargs.

        If the state is uncertain, the state should also marked as changed.
        """
        if self.state_uncertain:
            return True
        _LOGGER.debug("NO_STATE_CHANGE: %s", self.name)
        return False

    @inspector(re_raise=False)
    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Initialize the data point values."""
        for dp in self._readable_data_points:
            await dp.load_data_point_value(call_source=call_source, direct_call=direct_call)
        self.publish_data_point_updated_event()

    def unsubscribe_from_data_point_updated(self) -> None:
        """Unsubscribe from all internal update subscriptions."""
        for unreg in self._unsubscribe_callbacks:
            if unreg is not None:
                unreg()
        self._unsubscribe_callbacks.clear()

    @override
    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the data point."""
        return get_data_point_name_data(
            channel=self._channel,
            parameter=self._combined_parameter,
            parameter_translation=ccu_translations.get_parameter_translation(
                parameter=self._combined_parameter,
                channel_type=self._channel.type_name,
                locale=self._channel.device.config_provider.config.locale,
            ),
        )

    @override
    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data point."""
        if self._visible:
            return DataPointUsage.CDP_VISIBLE
        return DataPointUsage.NO_CREATE

    @override
    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return DataPointPathData(
            interface=self._device.client.interface,
            address=self._device.address,
            channel_no=self._channel.no,
            kind=self._category,
        )

    @override
    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self._channel.device.model}/{self._combined_parameter}"

    def _subscribe_to_data_point(self, *, data_point: GenericDataPointProtocolAny) -> None:
        """Subscribe to a source data point's updates."""
        if not isinstance(data_point, DpDummy):
            self._unsubscribe_callbacks.append(
                self._event_bus_provider.event_bus.subscribe(
                    event_type=DataPointStateChangedEvent,
                    event_key=data_point.unique_id,
                    handler=lambda *, event: self.publish_data_point_updated_event(),  # noqa: PLW0108  # pylint: disable=unnecessary-lambda
                )
            )
