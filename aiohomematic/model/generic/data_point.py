# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Generic python representation of a backend parameter."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Final, TypeAlias

from aiohomematic import i18n
from aiohomematic.const import DP_KEY_VALUE, DataPointUsage, EventType, Parameter, ParameterData, ParamsetKey
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import ValidationException
from aiohomematic.model import data_point as hme, device as hmd
from aiohomematic.model.support import DataPointNameData, get_data_point_name_data
from aiohomematic.property_decorators import hm_property
from aiohomematic.type_aliases import ParamType

_LOGGER: Final = logging.getLogger(__name__)


class GenericDataPoint[ParameterT: ParamType, InputParameterT: ParamType](
    hme.BaseParameterDataPoint[ParameterT, InputParameterT]
):
    """Base class for generic data point."""

    __slots__ = ("_cached_usage",)

    _validate_state_change: bool = True
    is_hmtype: bool = True

    def __init__(
        self,
        *,
        channel: hmd.Channel,
        paramset_key: ParamsetKey,
        parameter: str,
        parameter_data: ParameterData,
    ) -> None:
        """Init the generic data_point."""
        super().__init__(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        )

    @hm_property(cached=True)
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        if self._is_forced_sensor or self._is_un_ignored:
            return DataPointUsage.DATA_POINT
        if (force_enabled := self._enabled_by_channel_operation_mode) is None:
            return self._get_data_point_usage()
        return DataPointUsage.DATA_POINT if force_enabled else DataPointUsage.NO_CREATE  # pylint: disable=using-constant-test

    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Handle event for which this data_point has subscribed."""
        self._device.client.last_value_send_cache.remove_last_value_send(
            dpk=self.dpk,
            value=value,
        )
        old_value, new_value = self.write_value(value=value, write_at=received_at)
        if old_value == new_value:
            return

        if self._parameter == Parameter.CONFIG_PENDING and new_value is False and old_value is True:
            # do what is needed on device config change.
            await self._device.on_config_changed()

        # send device availability events
        if self._parameter in (
            Parameter.UN_REACH,
            Parameter.STICKY_UN_REACH,
        ):
            self._device.emit_device_updated_callback()
            self._central.emit_homematic_callback(
                event_type=EventType.DEVICE_AVAILABILITY,
                event_data=self.get_event_data(value=new_value),
            )

    def is_state_change(self, *, value: ParameterT) -> bool:
        """
        Check if the state/value changes.

        If the state is uncertain, the state should also marked as changed.
        """
        if value != self._value:
            return True
        if self.state_uncertain:
            return True
        _LOGGER.debug("NO_STATE_CHANGE: %s", self.name)
        return False

    @inspector
    async def send_value(
        self,
        *,
        value: InputParameterT,
        collector: hme.CallParameterCollector | None = None,
        collector_order: int = 50,
        do_validate: bool = True,
    ) -> set[DP_KEY_VALUE]:
        """Send value to ccu, or use collector if set."""
        if not self.is_writeable:
            _LOGGER.error(
                i18n.tr(
                    "log.model.generic_data_point.send_value.not_writable",
                    full_name=self.full_name,
                )
            )
            return set()
        try:
            prepared_value = self._prepare_value_for_sending(value=value, do_validate=do_validate)
        except (ValueError, ValidationException) as verr:
            _LOGGER.warning(verr)
            return set()

        converted_value = self._convert_value(value=prepared_value)
        # if collector is set, then add value to collector
        if collector:
            collector.add_data_point(data_point=self, value=converted_value, collector_order=collector_order)
            return set()

        # if collector is not set, then send value directly
        if self._validate_state_change and not self.is_state_change(value=converted_value):
            return set()

        return await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
            value=converted_value,
        )

    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the data_point."""
        return get_data_point_name_data(
            channel=self._channel,
            parameter=self._parameter,
        )

    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data_point."""
        if self._forced_usage:
            return self._forced_usage
        if self._central.parameter_visibility.parameter_is_hidden(
            channel=self._channel,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
        ):
            return DataPointUsage.NO_CREATE

        return (
            DataPointUsage.NO_CREATE
            if (self._device.has_custom_data_point_definition and not self._device.allow_undefined_generic_data_points)
            else DataPointUsage.DATA_POINT
        )

    def _prepare_value_for_sending(self, *, value: InputParameterT, do_validate: bool = True) -> ParameterT:
        """Prepare value, if required, before send."""
        return value  # type: ignore[return-value]


GenericDataPointAny: TypeAlias = GenericDataPoint[Any, Any]
