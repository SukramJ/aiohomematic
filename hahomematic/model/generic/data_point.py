"""Generic python representation of a CCU parameter."""

from __future__ import annotations

from functools import cached_property
import logging
from typing import Any, Final

from hahomematic.const import DP_KEY_VALUE, CallSource, DataPointUsage, EventType, Parameter, ParameterData, ParamsetKey
from hahomematic.decorators import inspector
from hahomematic.model import data_point as hme, device as hmd
from hahomematic.model.support import DataPointNameData, GenericParameterType, get_data_point_name_data

_LOGGER: Final = logging.getLogger(__name__)


class GenericDataPoint[ParameterT: GenericParameterType, InputParameterT: GenericParameterType](
    hme.BaseParameterDataPoint
):
    """Base class for generic data point."""

    _validate_state_change: bool = True
    is_hmtype: Final = True

    def __init__(
        self,
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

    @cached_property
    def usage(self) -> DataPointUsage:
        """Return the data_point usage."""
        if self._is_forced_sensor or self._is_un_ignored:
            return DataPointUsage.DATA_POINT
        if (force_enabled := self._enabled_by_channel_operation_mode) is None:
            return self._get_data_point_usage()
        return DataPointUsage.DATA_POINT if force_enabled else DataPointUsage.NO_CREATE

    async def event(self, value: Any) -> None:
        """Handle event for which this data_point has subscribed."""
        self._device.client.last_value_send_cache.remove_last_value_send(
            dpk=self.dpk,
            value=value,
        )
        old_value, new_value = self.write_value(value=value)
        if old_value == new_value:
            return

        # reload paramset_descriptions, if value has changed
        if self._parameter == Parameter.CONFIG_PENDING and new_value is False and old_value is True:
            await self._device.reload_paramset_descriptions()

            for data_point in self._device.get_readable_data_points(paramset_key=ParamsetKey.MASTER):
                await data_point.load_data_point_value(call_source=CallSource.MANUAL_OR_SCHEDULED, direct_call=True)

        # send device availability events
        if self._parameter in (
            Parameter.UN_REACH,
            Parameter.STICKY_UN_REACH,
        ):
            self._device.fire_device_updated_callback(self._unique_id)
            self._central.fire_homematic_callback(
                event_type=EventType.DEVICE_AVAILABILITY,
                event_data=self.get_event_data(new_value),
            )

    @inspector()
    async def send_value(
        self,
        value: InputParameterT,
        collector: hme.CallParameterCollector | None = None,
        collector_order: int = 50,
        do_validate: bool = True,
    ) -> set[DP_KEY_VALUE]:
        """Send value to ccu, or use collector if set."""
        if not self.is_writeable:
            _LOGGER.error("SEND_VALUE: writing to non-writable data_point %s is not possible", self.full_name)
            return set()
        try:
            prepared_value = self._prepare_value_for_sending(value=value, do_validate=do_validate)
        except ValueError as verr:
            _LOGGER.warning(verr)
            return set()

        converted_value = self._convert_value(value=prepared_value)
        if collector:
            collector.add_data_point(self, value=converted_value, collector_order=collector_order)
            return set()

        if self._validate_state_change and not self.is_state_change(value=converted_value):
            return set()

        return await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=self._paramset_key,
            parameter=self._parameter,
            value=converted_value,
        )

    def _prepare_value_for_sending(self, value: InputParameterT, do_validate: bool = True) -> ParameterT:
        """Prepare value, if required, before send."""
        return value  # type: ignore[return-value]

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

    def is_state_change(self, value: ParameterT) -> bool:
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
