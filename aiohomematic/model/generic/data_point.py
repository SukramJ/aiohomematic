# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Base implementation for generic data points.

Public API of this module is defined by __all__.
"""

from datetime import datetime
import logging
from typing import Any, Final, TypeAlias

from aiohomematic import ccu_translations, i18n
from aiohomematic.central.events import DeviceLifecycleEvent, DeviceLifecycleEventType
from aiohomematic.client.command_throttle import CommandPriority
from aiohomematic.const import DP_KEY_VALUE, DataPointUsage, Parameter, ParameterData, ParamsetKey
from aiohomematic.context import get_request_context
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import ValidationException
from aiohomematic.interfaces import ChannelProtocol, GenericDataPointProtocol
from aiohomematic.model import data_point as hme
from aiohomematic.model.support import DataPointNameData, get_data_point_name_data
from aiohomematic.property_decorators import hm_property
from aiohomematic.type_aliases import ParamType

_LOGGER: Final = logging.getLogger(__name__)


class GenericDataPoint[ParameterT: ParamType, InputParameterT: ParamType](
    hme.BaseParameterDataPoint[ParameterT, InputParameterT],
    GenericDataPointProtocol[ParameterT | None],
):
    """Base class for generic data point."""

    __slots__ = ("_cached_usage",)

    _validate_state_change: bool = True
    is_hmtype: bool = True

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        paramset_key: ParamsetKey,
        parameter: str,
        parameter_data: ParameterData,
    ) -> None:
        """Initialize the generic data_point."""
        super().__init__(
            channel=channel,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        )

    @staticmethod
    def _values_mismatch(*, optimistic: Any, actual: Any) -> bool:
        """Check if optimistic and actual values differ, rounding floats to 2 decimals."""
        if isinstance(optimistic, float) and isinstance(actual, float):
            return round(optimistic, 2) != round(actual, 2)
        return optimistic != actual  # type: ignore[no-any-return]

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
        # PHASE 3: CCU CONFIRMATION - Handle optimistic value confirmation
        if self._optimistic.is_active and self._optimistic.confirm_one():
            # Final confirmation — evaluate mismatch and clear state

            # Check for value mismatch (round floats to 2 decimals to avoid
            # false positives from CCU rounding, e.g. 0.3803… vs 0.38).
            # Mismatch is logged at DEBUG only — no rollback event, because the
            # CCU value is authoritative and silently accepted (not a real rollback).
            if self._values_mismatch(optimistic=self._optimistic.value, actual=value):
                _LOGGER.debug(
                    i18n.tr(
                        key="log.model.data_point.optimistic_mismatch",
                        full_name=self.full_name,
                        expected=self._optimistic.value,
                        actual=value,
                        age=self._optimistic.age or 0.0,
                    )
                )

            # Clear optimistic state (either confirmed or corrected)
            self._optimistic.clear()

        self._device.client.last_value_send_tracker.remove_last_value_send(
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
            # notify_data_points=True ensures entities on all channels refresh their availability
            self._device.publish_device_updated_event(notify_data_points=True)
            await self._event_bus_provider.event_bus.publish(
                event=DeviceLifecycleEvent(
                    timestamp=datetime.now(),
                    event_type=DeviceLifecycleEventType.AVAILABILITY_CHANGED,
                    availability_changes=((self._device.address, new_value is False),),
                    device_names=(self._device.name,),
                )
            )

    def is_state_change(self, *, value: ParameterT | None) -> bool:
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
        if not self.is_writable:
            _LOGGER.error(
                i18n.tr(
                    key="log.model.generic_data_point.send_value.not_writable",
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

        # COLLECTOR PATH: Defer optimistic update to collector.send_data()
        # This prevents optimistic values from interfering with is_state_change()
        # checks in parent turn_on() methods that read from sibling data points.
        if collector:
            collector.add_data_point(data_point=self, value=converted_value, collector_order=collector_order)
            return set()

        # DIRECT SEND PATH: Check state change BEFORE applying optimistic update.
        # Applying optimistic first would start a 30s rollback timer even when
        # no RPC is sent (value unchanged), causing spurious timeout rollbacks.
        if self._validate_state_change and not self.is_state_change(value=converted_value):
            return set()

        # Skip duplicate sends when an optimistic value with the same target is
        # already pending. The CCU confirms identical values only once, so a
        # second apply() would increment pending_sends to 2 while only one
        # confirmation arrives, causing a spurious rollback after 30s (#3049).
        if self._optimistic.is_active and self._optimistic.value == converted_value:
            return set()

        self.apply_optimistic_value(value=converted_value)

        # Detect command priority for throttling (CRITICAL/HIGH/LOW)
        ctx = get_request_context()
        if ctx and isinstance(ctx_priority := ctx.extra.get(hme.CONTEXT_KEY_PRIORITY), CommandPriority):
            priority = ctx_priority
        else:
            priority = self.get_command_priority()

        # Get purge addresses from context (set by bind_collector for CRITICAL commands)
        purge_addresses: frozenset[str] = (
            ctx.extra.get(hme.CONTEXT_KEY_PURGE_ADDRESSES, frozenset()) if ctx else frozenset()
        )

        try:
            if purge_addresses:
                return await self._client.set_value(
                    channel_address=self._channel.address,
                    paramset_key=self._paramset_key,
                    parameter=self._parameter,
                    value=converted_value,
                    priority=priority,
                    purge_addresses=purge_addresses,
                )
            return await self._client.set_value(
                channel_address=self._channel.address,
                paramset_key=self._paramset_key,
                parameter=self._parameter,
                value=converted_value,
                priority=priority,
            )
        except Exception as err:
            # Immediate rollback on send error
            self._rollback_optimistic_value(reason="send_error", error=str(err))
            raise

    def _get_data_point_name(self) -> DataPointNameData:
        """Create the name for the data_point."""
        return get_data_point_name_data(
            channel=self._channel,
            parameter=self._parameter,
            parameter_translation=ccu_translations.get_parameter_translation(
                parameter=self._parameter,
                channel_type=self._channel.type_name,
                locale=self._channel.device.config_provider.config.locale,
            ),
        )

    def _get_data_point_usage(self) -> DataPointUsage:
        """Generate the usage for the data_point."""
        if self._forced_usage:
            return self._forced_usage
        if self._parameter_visibility_provider.parameter_is_hidden(
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
