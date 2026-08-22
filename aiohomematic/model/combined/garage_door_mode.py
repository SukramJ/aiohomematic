# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Combined garage door mode data point.

Public API of this module is defined by __all__.
"""

from typing import Final, cast

from aiohomematic import i18n
from aiohomematic.const import (
    CombinedParameter,
    DataPointCategory,
    Field,
    GarageDoorCommand,
    GarageDoorState,
    Operations,
    ParameterType,
)
from aiohomematic.exceptions import ValidationException
from aiohomematic.interfaces import ChannelProtocol, CombinedDataPointProtocol, GenericDataPointProtocolAny
from aiohomematic.model.combined.data_point import CombinedDataPoint
from aiohomematic.model.data_point import CallParameterCollector
from aiohomematic.model.generic import DpDummy

__all__ = ["CombinedDpGarageDoorMode"]

# Map the read-side door state to the write-side door command. The garage door
# reports its discrete states via DOOR_STATE, but commands are issued through
# the separate DOOR_COMMAND parameter. The ventilation position is the only
# mode without a 1:1 state/command name, so the mapping is explicit. This dict
# also defines the selectable values and their order.
_DOOR_STATE_TO_COMMAND: Final[dict[str, GarageDoorCommand]] = {
    GarageDoorState.CLOSED.value: GarageDoorCommand.CLOSE,
    GarageDoorState.OPEN.value: GarageDoorCommand.OPEN,
    GarageDoorState.VENTILATION_POSITION.value: GarageDoorCommand.PARTIAL_OPEN,
}

# Inverse mapping for the (optimistic) value held after a command: the door
# reports the resulting state once the movement completes, but until then
# the select should keep showing the commanded mode rather than dropping to
# unknown. Commands without a resulting mode (STOP, NOP) are absent, so they
# clear the held value instead of leaving a stale one behind.
_COMMAND_TO_DOOR_STATE: Final[dict[GarageDoorCommand, str]] = {
    command: state for state, command in _DOOR_STATE_TO_COMMAND.items()
}


class CombinedDpGarageDoorMode(CombinedDataPoint[str | None], CombinedDataPointProtocol):
    """
    Combined data point for a garage door's discrete mode (closed/ventilation/open).

    Reads the door state via DOOR_STATE and writes commands via DOOR_COMMAND,
    exposing the three physical states as a single SELECT-category data point.
    Home Assistant's cover platform has no native ventilation state, so this
    makes the ventilation command a first-class, tappable select entity without
    any integration-side wiring: the generic SELECT-category dispatch in
    homematicip_local picks it up via `values`/`value`/`send_value`.
    """

    __slots__ = ("_door_command_dp", "_door_state_dp")

    _category = DataPointCategory.SELECT

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        door_state_field: Field,
        door_command_field: Field,
        door_state_dp: GenericDataPointProtocolAny,
        door_command_dp: GenericDataPointProtocolAny,
        visible: bool = False,
    ) -> None:
        """Initialize the combined garage door mode data point."""
        # DOOR_MODE is not a CCU parameter: the mode is read from DOOR_STATE and
        # written to DOOR_COMMAND. Naming it after either source would mislabel the
        # entity ("Door State" for a writable control) and collide with that
        # parameter's translation, so it carries its own name and translation key.
        super().__init__(
            channel=channel,
            combined_parameter=CombinedParameter.DOOR_MODE.value,
            visible=visible,
        )
        self._door_state_dp: Final = door_state_dp
        self._door_command_dp: Final = door_command_dp
        self._data_points[door_state_field] = door_state_dp
        self._data_points[door_command_field] = door_command_dp

        # Subscribe to underlying DPs (state changes refresh the select).
        self._subscribe_to_data_point(data_point=door_state_dp)
        self._subscribe_to_data_point(data_point=door_command_dp)

        # Configure type info for HA entity.
        self._type = ParameterType.ENUM
        self._operations = Operations.READ | Operations.WRITE | Operations.EVENT
        self._values = tuple(_DOOR_STATE_TO_COMMAND)

    @property
    def default(self) -> None:
        """Return the default value."""
        return None

    @property
    def is_valid(self) -> bool:
        """Return True if the door state data point is not a dummy."""
        return not isinstance(self._door_state_dp, DpDummy)

    @property
    def value(self) -> str | None:
        """
        Return the current door mode.

        While the door is travelling, DOOR_STATE reports POSITION_UNKNOWN. To
        avoid the select dropping to `unknown` on every movement, the mode of the
        last issued command (held in _current_value) is returned instead.
        """
        if (state := self._door_state_dp.value) in _DOOR_STATE_TO_COMMAND:
            return cast(str, state)
        return self._current_value

    def note_command(self, *, command: GarageDoorCommand) -> None:
        """
        Record a DOOR_COMMAND that was issued outside this data point.

        CustomDpGarage writes DOOR_COMMAND directly for its cover operations
        (open/close/vent/stop). Without this hook the optimistically held mode
        would keep reporting a mode the door is no longer heading for — and would
        do so indefinitely after a STOP, because that leaves DOOR_STATE at
        POSITION_UNKNOWN with no further event to correct it.
        """
        if (state := _COMMAND_TO_DOOR_STATE.get(command)) == self._current_value:
            return
        old_value = self._current_value
        self._current_value = state
        self.publish_data_point_updated_event(old_value=old_value, new_value=state)

    async def send_default(self, *, collector: CallParameterCollector | None = None) -> None:
        """Send default values. The garage door has no meaningful default command."""
        return

    async def send_value(
        self,
        *,
        value: str,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """
        Send a door mode command.

        Translates the requested mode (a DOOR_STATE string, e.g. VENTILATION_POSITION)
        to the matching DOOR_COMMAND (e.g. PARTIAL_OPEN) and dispatches it. The
        commanded mode is held optimistically so the select keeps showing it
        until the door reports the reached state.

        Raises:
            ValidationException: If value is not one of the selectable door modes.

        """
        if (command := _DOOR_STATE_TO_COMMAND.get(value)) is None:
            raise ValidationException(
                i18n.tr(
                    key="exception.model.select.value_not_in_value_list",
                    name=self.name,
                    unique_id=self.unique_id,
                )
            )
        await self._door_command_dp.send_value(value=command, collector=collector)
        self.note_command(command=command)
