# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Custom lock data points for door locks and access control.

Public API of this module is defined by __all__.
"""

from abc import abstractmethod
from enum import StrEnum, unique
from typing import Any, ClassVar, Final, override

from aiohomematic.client import CommandPriority
from aiohomematic.const import DataPointCategory, DeviceProfile, Field, Parameter
from aiohomematic.interfaces.custom import LockDataPointProtocol
from aiohomematic.model.custom.capabilities.lock import BUTTON_LOCK_CAPABILITIES, IP_LOCK_CAPABILITIES, LockCapabilities
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.field import DataPointField
from aiohomematic.model.custom.registry import DeviceConfig, DeviceProfileRegistry, ExtendedDeviceConfig
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpActionSelect, DpBinarySensor, DpSensor, DpSwitch
from aiohomematic.property_decorators import hm_property


@unique
class _LockActivity(StrEnum):
    """Enum with lock activities."""

    LOCKING = "DOWN"
    STABLE = "STABLE"
    UNKNOWN = "UNKNOWN"
    UNLOCKING = "UP"


@unique
class _LockError(StrEnum):
    """Enum with lock errors."""

    NO_ERROR = "NO_ERROR"
    CLUTCH_FAILURE = "CLUTCH_FAILURE"
    MOTOR_ABORTED = "MOTOR_ABORTED"


@unique
class _LockTargetLevel(StrEnum):
    """Enum with lock target levels."""

    LOCKED = "LOCKED"
    OPEN = "OPEN"
    UNLOCKED = "UNLOCKED"


@unique
class LockState(StrEnum):
    """Enum with lock states."""

    LOCKED = "LOCKED"
    UNKNOWN = "UNKNOWN"
    UNLOCKED = "UNLOCKED"


class BaseCustomDpLock(CustomDataPoint, LockDataPointProtocol):
    """Class for HomematicIP lock data point."""

    __slots__ = ("_cached_capabilities",)

    _category = DataPointCategory.LOCK
    _ignore_multiple_channels_for_name = True

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return False

    @property
    @abstractmethod
    def is_locked(self) -> bool:
        """Return true if lock is on."""

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return None

    @property
    def is_opening(self) -> bool | None:
        """Return true if the lock is opening (latch is being pulled)."""
        return None

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return None

    @hm_property(cached=True)
    def capabilities(self) -> LockCapabilities:
        """Return the lock capabilities."""
        return self._compute_capabilities()

    @abstractmethod
    @bind_collector(priority=CommandPriority.CRITICAL)
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""

    @abstractmethod
    @bind_collector(priority=CommandPriority.CRITICAL)
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""

    @abstractmethod
    @bind_collector(priority=CommandPriority.CRITICAL)
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""

    @abstractmethod
    def _compute_capabilities(self) -> LockCapabilities:
        """Compute static capabilities. Implemented by subclasses."""


class CustomDpIpLock(BaseCustomDpLock):
    """
    Class for HomematicIP lock data point.

    The device reports no open state, only the motor direction (ACTIVITY_STATE)
    and the bolt position (LOCK_STATE). Opening the latch is a movement that starts
    with UP while the lock is already UNLOCKED and returns with DOWN to the unlocked
    position. That DOWN must not be reported as locking, so the open movement is
    tracked until the motor is STABLE (or UNKNOWN) again.
    """

    __slots__ = ("_is_open_movement",)

    # Declarative data point field definitions
    _dp_direction: Final = DataPointField(field=Field.DIRECTION, dpt=DpSensor[str | None])
    _dp_error: Final = DataPointField(field=Field.ERROR, dpt=DpBinarySensor)
    _dp_lock_state: Final = DataPointField(field=Field.LOCK_STATE, dpt=DpSensor[str | None])
    _dp_lock_target_level: Final = DataPointField(field=Field.LOCK_TARGET_LEVEL, dpt=DpActionSelect)
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.LOCK_STATE})

    @property
    def _direction(self) -> str | None:
        """Return the current motor direction."""
        if (value := self._dp_direction.value) is None:
            return None
        return str(value)

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._dp_error.value is True

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._dp_lock_state.value == LockState.LOCKED

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if (direction := self._direction) is None:
            return None
        return direction == _LockActivity.LOCKING and not self._is_open_movement

    @property
    def is_opening(self) -> bool | None:
        """Return true if the lock is opening (latch is being pulled)."""
        if (direction := self._direction) is None:
            return None
        return self._is_opening_up(direction=direction) or (
            direction == _LockActivity.LOCKING and self._is_open_movement
        )

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if (direction := self._direction) is None:
            return None
        return direction == _LockActivity.UNLOCKING and not self._is_opening_up(direction=direction)

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.LOCKED, collector=collector)

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.OPEN, collector=collector)

    @override
    def publish_data_point_updated_event(self, *, old_value: Any = None, new_value: Any = None) -> None:
        """Track the open movement before the update is published."""
        self._update_open_movement()
        super().publish_data_point_updated_event(old_value=old_value, new_value=new_value)

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.UNLOCKED, collector=collector)

    def _compute_capabilities(self) -> LockCapabilities:
        """Compute static capabilities. IP locks support open."""
        return IP_LOCK_CAPABILITIES

    def _is_opening_up(self, *, direction: str) -> bool:
        """Return true if the motor moves UP although the bolt is already unlocked."""
        return direction == _LockActivity.UNLOCKING and self._dp_lock_state.value == LockState.UNLOCKED

    @override
    def _post_init(self) -> None:
        """Initialize the open movement tracking."""
        self._is_open_movement = False
        super()._post_init()

    def _update_open_movement(self) -> None:
        """Start the open movement on UP while unlocked, end it when the motor stops."""
        if (direction := self._direction) is None or direction in (_LockActivity.STABLE, _LockActivity.UNKNOWN):
            self._is_open_movement = False
        elif self._is_opening_up(direction=direction):
            self._is_open_movement = True


class CustomDpButtonLock(BaseCustomDpLock):
    """Class for HomematicIP button lock data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    # Declarative data point field definitions
    _dp_button_lock: Final = DataPointField(field=Field.BUTTON_LOCK, dpt=DpSwitch)
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.BUTTON_LOCK})

    @property
    def data_point_name_postfix(self) -> str:
        """Return the data_point name postfix."""
        return "BUTTON_LOCK"

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._dp_button_lock.value is True

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_button_lock.turn_on(collector=collector)

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        return

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_button_lock.turn_off(collector=collector)

    def _compute_capabilities(self) -> LockCapabilities:
        """Compute static capabilities. Button locks do not support open."""
        return BUTTON_LOCK_CAPABILITIES


class CustomDpRfLock(BaseCustomDpLock):
    """Class for classic Homematic lock data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    # Declarative data point field definitions
    _dp_direction: Final = DataPointField(field=Field.DIRECTION, dpt=DpSensor[str | None])
    _dp_error: Final = DataPointField(field=Field.ERROR, dpt=DpSensor[str | None])
    _dp_open: Final = DataPointField(field=Field.OPEN, dpt=DpAction)
    _dp_state: Final = DataPointField(field=Field.STATE, dpt=DpSwitch)
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.STATE})

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._dp_error.value is not None and self._dp_error.value != _LockError.NO_ERROR

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._dp_state.value is not True

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _LockActivity.LOCKING
        return None

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _LockActivity.UNLOCKING
        return None

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_state.send_value(value=False, collector=collector)

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._dp_open.send_value(value=True, collector=collector)

    @bind_collector(priority=CommandPriority.CRITICAL)
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_state.send_value(value=True, collector=collector)

    def _compute_capabilities(self) -> LockCapabilities:
        """Compute static capabilities. RF locks support open."""
        return IP_LOCK_CAPABILITIES


# =============================================================================
# DeviceProfileRegistry Registration
# =============================================================================

# RF Lock (HM-Sec-Key)
DeviceProfileRegistry.register(
    category=DataPointCategory.LOCK,
    models="HM-Sec-Key",
    data_point_class=CustomDpRfLock,
    profile_type=DeviceProfile.RF_LOCK,
    channels=(1,),
    extended=ExtendedDeviceConfig(
        additional_data_points={
            1: (
                Parameter.DIRECTION,
                Parameter.ERROR,
            ),
        }
    ),
)

# IP Lock with Button Lock (HmIP-DLD - multiple configs)
DeviceProfileRegistry.register_multiple(
    category=DataPointCategory.LOCK,
    models="HmIP-DLD",
    configs=(
        DeviceConfig(
            data_point_class=CustomDpIpLock,
            profile_type=DeviceProfile.IP_LOCK,
            extended=ExtendedDeviceConfig(
                additional_data_points={
                    0: (Parameter.ERROR_JAMMED,),
                }
            ),
            schedule_channel_no=10,
        ),
        DeviceConfig(
            data_point_class=CustomDpButtonLock,
            profile_type=DeviceProfile.IP_BUTTON_LOCK,
            channels=(0,),
        ),
    ),
)

# IP Lock with Button Lock (HmIP-DLP - multiple configs)
DeviceProfileRegistry.register_multiple(
    category=DataPointCategory.LOCK,
    models="HmIP-DLP",
    configs=(
        DeviceConfig(
            data_point_class=CustomDpIpLock,
            profile_type=DeviceProfile.IP_LOCK,
            extended=ExtendedDeviceConfig(
                # The profile looks on the channel before the lock channel, which is the DLD layout.
                fixed_channel_fields={12: {Field.ERROR: Parameter.ERROR_JAMMED}},
                additional_data_points={
                    0: (
                        Parameter.SABOTAGE_ACCELERATION,
                        Parameter.SABOTAGE_BATTERY,
                        Parameter.SABOTAGE_MAGNETIC_FIELD,
                        Parameter.SABOTAGE_VERTICAL,
                    ),
                    3: (Parameter.STATE,),
                    (4, 5, 6, 7, 8, 9, 10, 11): (Parameter.PERMISSION_STATE,),
                    12: (
                        Parameter.ERROR_JAMMED,
                        Parameter.LOCK_STATE_REASON,
                    ),
                    13: (Parameter.AUTO_RELOCK_STATE,),
                },
            ),
            channels=(12,),
            schedule_channel_no=14,
        ),
        DeviceConfig(
            data_point_class=CustomDpButtonLock,
            profile_type=DeviceProfile.IP_BUTTON_LOCK,
            channels=(0,),
        ),
    ),
)

# RF Button Lock
DeviceProfileRegistry.register(
    category=DataPointCategory.LOCK,
    models="HM-TC-IT-WM-W-EU",
    data_point_class=CustomDpButtonLock,
    profile_type=DeviceProfile.RF_BUTTON_LOCK,
    channels=(None,),
)

# IP Button Lock (various thermostats and controls)
DeviceProfileRegistry.register(
    category=DataPointCategory.LOCK,
    models=(
        "ALPHA-IP-RBG",
        "HmIP-BWTH",
        "HmIP-FAL",
        "HmIP-WGT",
        "HmIP-WTH",
        "HmIP-eTRV",
        "HmIPW-FAL",
        "HmIPW-WTH",
    ),
    data_point_class=CustomDpButtonLock,
    profile_type=DeviceProfile.IP_BUTTON_LOCK,
    channels=(0,),
)
