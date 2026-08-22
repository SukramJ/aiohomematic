# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Combined garage door mode data point.

Public API of this module is defined by __all__.
"""

from typing import Final, cast

from aiohomematic.const import DataPointCategory, Field, Operations, ParameterType
from aiohomematic.interfaces import ChannelProtocol, CombinedDataPointProtocol, GenericDataPointProtocolAny
from aiohomematic.model.combined.data_point import CombinedDataPoint
from aiohomematic.model.custom.garage import GarageDoorCommand, GarageDoorState
from aiohomematic.model.data_point import CallParameterCollector
from aiohomematic.model.generic import DpDummy

__all__ = ["CombinedDpGarageDoorMode"]

# Map the read-side door state to the write-side door command. The garage door
# reports its discrete states via DOOR_STATE, but commands are issued through
# the separate DOOR_COMMAND parameter. The ventilation position is the only
# mode without a 1:1 state/command name, so the mapping is explicit.
_DOOR_STATE_TO_COMMAND: Final[dict[str, GarageDoorCommand]] = {
    GarageDoorState.CLOSED: GarageDoorCommand.CLOSE,
    GarageDoorState.OPEN: GarageDoorCommand.OPEN,
    GarageDoorState.VENTILATION_POSITION: GarageDoorCommand.PARTIAL_OPEN,
}

# Inverse mapping for the (optimistic) value held after a send: the door
# reports the resulting state once the movement completes, but until then
# the select should keep showing the commanded mode rather than dropping to
# unknown. This maps the command back to the state string the integration
# exposes via `value`.
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
        super().__init__(
            channel=channel,
            combined_parameter=door_state_field.value,
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
        self._values = (
            GarageDoorState.CLOSED,
            GarageDoorState.OPEN,
            GarageDoorState.VENTILATION_POSITION,
        )

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

        While the door is travelling, DOOR_STATE may report POSITION_UNKNOWN.
        To avoid the select dropping to `unknown` on every movement, the last
        commanded value (held in _current_value) is returned instead.
        """
        state = self._door_state_dp.value
        if state in _DOOR_STATE_TO_COMMAND:
            return cast(str, state)
        return self._current_value

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
        commanded state is held optimistically so the select keeps showing it
        until the door reports the reached state.
        """
        if (command := _DOOR_STATE_TO_COMMAND.get(value)) is not None:
            await self._door_command_dp.send_value(value=command, collector=collector)
            self._current_value = value
