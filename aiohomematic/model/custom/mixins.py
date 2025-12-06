# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Shared mixins for custom data point implementations.

This module provides reusable mixin classes that extract common patterns
from custom entity implementations to reduce code duplication.

Mixins
------
- StateChangeTimerMixin: Timer-based state change detection logic
- OnOffActionMixin: Common on/off action logic with timer support
- GroupStateMixin: Common group state property pattern
- PositionMixin: Position conversion logic for covers/blinds
- BrightnessMixin: Brightness conversion logic for lights/dimmers
- TimerUnitMixin: Timer unit conversion for lights with on_time/ramp_time

Usage
-----
Mixins are designed to be used with CustomDataPoint subclasses through
multiple inheritance::

    class CustomDpSwitch(StateChangeTimerMixin, GroupStateMixin, CustomDataPoint):
        _category = DataPointCategory.SWITCH
        ...
"""

from __future__ import annotations

from abc import abstractmethod
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from aiohomematic.model.data_point import CallParameterCollector
    from aiohomematic.model.generic import DpAction, DpSwitch


class StateChangeArg(StrEnum):
    """Common state change arguments for on/off entities."""

    OFF = "off"
    ON = "on"


@runtime_checkable
class TimerCapable(Protocol):
    """Protocol for entities with timer capabilities."""

    @property
    def timer_on_time(self) -> float | None:
        """Return the on_time."""

    @property
    def timer_on_time_running(self) -> bool:
        """Return if on_time is running."""

    def get_and_start_timer(self) -> float | None:
        """Get and start the timer."""

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes."""

    def reset_timer_on_time(self) -> None:
        """Reset the on_time."""

    def set_timer_on_time(self, *, on_time: float) -> None:
        """Set the on_time."""


@runtime_checkable
class ValueCapable(Protocol):
    """Protocol for entities with value property."""

    @property
    def value(self) -> bool | None:
        """Return the current value."""


class StateChangeTimerMixin:
    """
    Mixin providing timer-based state change detection.

    This mixin implements the common state change detection pattern used
    by switch, valve, light, and similar entities that support on_time timers.

    Provides:
    - is_timer_state_change(): Timer-only state change detection
    - is_state_change_for_on_off(): Full on/off state change detection (requires value property)

    Requires the class to implement:
    - timer_on_time property (from BaseDataPoint)
    - timer_on_time_running property (from BaseDataPoint)
    - value property (only for is_state_change_for_on_off)
    """

    __slots__ = ()

    # Declare expected attributes from BaseDataPoint
    timer_on_time: float | None
    timer_on_time_running: bool
    # value is expected for is_state_change_for_on_off but not declared here
    # to avoid interfering with subclasses that don't need it

    def is_state_change_for_on_off(self, **kwargs: Any) -> bool:
        """
        Check if the state changes due to on/off kwargs with timer consideration.

        Requires the subclass to have a `value` property returning bool | None.

        Returns True if:
        - Timer is currently running
        - Timer on_time is set
        - Turning on when not already on
        - Turning off when not already off
        """
        if self.is_timer_state_change():
            return True
        value: bool | None = getattr(self, "value", None)
        if kwargs.get(StateChangeArg.ON) is not None and value is not True:
            return True
        return kwargs.get(StateChangeArg.OFF) is not None and value is not False

    def is_timer_state_change(self) -> bool:
        """
        Check if the state should change due to timer conditions only.

        Returns True if:
        - Timer is currently running
        - Timer on_time is set

        This is useful for entities like lights that have more complex
        on/off logic but still need timer-based state change detection.
        """
        if self.timer_on_time_running is True:
            return True
        return self.timer_on_time is not None


class OnOffActionMixin:
    """
    Mixin providing common on/off action implementations.

    This mixin provides reusable turn_on and turn_off logic that handles
    timer management, state change detection, and value sending.

    Subclasses must provide:
    - _dp_state: DpSwitch data point
    - _dp_on_time_value: DpAction data point for on_time
    - Timer capability methods (from BaseDataPoint)
    """

    __slots__ = ()

    # These are expected to be set by the implementing class
    _dp_state: DpSwitch
    _dp_on_time_value: DpAction

    @abstractmethod
    def get_and_start_timer(self) -> float | None:
        """Get and start the timer."""

    @abstractmethod
    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""

    @abstractmethod
    def reset_timer_on_time(self) -> None:
        """Reset the on_time."""

    @abstractmethod
    def set_timer_on_time(self, *, on_time: float) -> None:
        """Set the on_time."""

    async def _perform_turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """
        Perform turn off action with timer reset.

        This is the common implementation for turn_off/close operations.
        """
        self.reset_timer_on_time()
        if not self.is_state_change(off=True):
            return
        await self._dp_state.turn_off(collector=collector)

    async def _perform_turn_on(
        self, *, on_time: float | None = None, collector: CallParameterCollector | None = None
    ) -> None:
        """
        Perform turn on action with optional timer.

        This is the common implementation for turn_on/open operations.
        """
        if on_time is not None:
            self.set_timer_on_time(on_time=on_time)
        if not self.is_state_change(on=True):
            return

        if (timer := self.get_and_start_timer()) is not None:
            await self._dp_on_time_value.send_value(value=timer, collector=collector, do_validate=False)
        await self._dp_state.turn_on(collector=collector)


class GroupStateMixin:
    """
    Mixin for entities that have a group state.

    Provides common group_value property pattern used by switches,
    valves, and other entities with group state tracking.
    """

    __slots__ = ()

    # Expected to be set by implementing class
    _dp_group_state: Any  # DpBinarySensor

    @property
    def group_value(self) -> bool | None:
        """Return the current group value."""
        value: bool | None = self._dp_group_state.value
        return value


class PositionMixin:
    """
    Mixin for entities with position values (0-100%).

    Provides common position conversion logic for covers, blinds,
    and similar entities that work with percentage positions.
    """

    __slots__ = ()

    @staticmethod
    def level_to_position(level: float | None, *, inverted: bool = False) -> int | None:
        """
        Convert level (0.0-1.0) to position percentage (0-100).

        Args:
            level: Level value between 0.0 and 1.0.
            inverted: If True, invert the position (100 - position).

        Returns:
            Position as integer percentage, or None if level is None.

        """
        if level is None:
            return None
        position = int(level * 100)
        return 100 - position if inverted else position

    @staticmethod
    def position_to_level(position: int, *, inverted: bool = False) -> float:
        """
        Convert position percentage (0-100) to level (0.0-1.0).

        Args:
            position: Position as integer percentage.
            inverted: If True, invert before conversion.

        Returns:
            Level value between 0.0 and 1.0.

        """
        if inverted:
            position = 100 - position
        return position / 100.0


class BrightnessMixin:
    """
    Mixin for entities with brightness values (0-255 or 0-100%).

    Provides common brightness conversion logic for lights and dimmers.
    """

    __slots__ = ()

    # Constants for brightness conversion
    _MAX_BRIGHTNESS: int = 255
    _BRIGHTNESS_PCT_MULTIPLIER: int = 100

    @staticmethod
    def brightness_to_level(brightness: int, *, max_brightness: int = 255) -> float:
        """
        Convert brightness (0-max_brightness) to level (0.0-1.0).

        Args:
            brightness: Brightness value.
            max_brightness: Maximum brightness value (default 255).

        Returns:
            Level value between 0.0 and 1.0.

        """
        return brightness / max_brightness

    @staticmethod
    def level_to_brightness(level: float | None, *, max_brightness: int = 255) -> int:
        """
        Convert level (0.0-1.0) to brightness (0-max_brightness).

        Args:
            level: Level value between 0.0 and 1.0.
            max_brightness: Maximum brightness value (default 255).

        Returns:
            Brightness as integer, or 0 if level is None.

        """
        if level is None:
            return 0
        return int(level * max_brightness)

    @staticmethod
    def level_to_brightness_pct(level: float | None) -> int:
        """
        Convert level (0.0-1.0) to brightness percentage (0-100).

        Args:
            level: Level value between 0.0 and 1.0.

        Returns:
            Brightness percentage as integer, or 0 if level is None.

        """
        if level is None:
            return 0
        return int(level * 100)


class _TimeUnit:
    """Time unit constants for timer conversion."""

    SECONDS: int = 0
    MINUTES: int = 1
    HOURS: int = 2


# Marker value indicating timer is not used
_TIMER_NOT_USED: float = 111600.0

# Threshold for time unit conversion (max value before switching units)
_TIME_UNIT_THRESHOLD: int = 16343


class TimerUnitMixin:
    """
    Mixin for lights with time unit conversion for on_time and ramp_time.

    Provides common timer value setting methods that handle automatic
    unit conversion (seconds -> minutes -> hours) for large time values.

    Requires the class to have:
    - _dp_on_time_value: DpAction for on_time value
    - _dp_on_time_unit: DpAction for on_time unit
    - _dp_ramp_time_value: DpAction for ramp_time value
    - _dp_ramp_time_unit: DpAction for ramp_time unit
    """

    __slots__ = ()

    # Expected to be set by implementing class
    _dp_on_time_value: Any
    _dp_on_time_unit: Any
    _dp_ramp_time_value: Any
    _dp_ramp_time_unit: Any

    @staticmethod
    def _recalc_unit_timer(*, time: float) -> tuple[float, int | None]:
        """
        Recalculate unit and value of timer.

        Converts large time values to appropriate units:
        - > 16343 seconds -> minutes
        - > 16343 minutes -> hours

        Args:
            time: Time value in seconds.

        Returns:
            Tuple of (converted_time, unit) where unit is None if time equals NOT_USED marker.

        """
        time_unit = _TimeUnit.SECONDS
        if time == _TIMER_NOT_USED:
            return time, None
        if time > _TIME_UNIT_THRESHOLD:
            time /= 60
            time_unit = _TimeUnit.MINUTES
        if time > _TIME_UNIT_THRESHOLD:
            time /= 60
            time_unit = _TimeUnit.HOURS
        return time, time_unit

    async def _set_on_time_value(self, *, on_time: float, collector: Any | None = None) -> None:
        """Set the on time value with automatic unit conversion."""
        on_time, on_time_unit = self._recalc_unit_timer(time=on_time)
        if on_time_unit:
            await self._dp_on_time_unit.send_value(value=on_time_unit, collector=collector)
        await self._dp_on_time_value.send_value(value=float(on_time), collector=collector)

    async def _set_ramp_time_off_value(self, *, ramp_time: float, collector: Any | None = None) -> None:
        """Set the ramp time off value with automatic unit conversion."""
        await self._set_ramp_time_on_value(ramp_time=ramp_time, collector=collector)

    async def _set_ramp_time_on_value(self, *, ramp_time: float, collector: Any | None = None) -> None:
        """Set the ramp time on value with automatic unit conversion."""
        ramp_time, ramp_time_unit = self._recalc_unit_timer(time=ramp_time)
        if ramp_time_unit:
            await self._dp_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._dp_ramp_time_value.send_value(value=float(ramp_time), collector=collector)
