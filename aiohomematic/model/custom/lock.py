# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom lock data points for door locks and access control.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from abc import abstractmethod
from enum import StrEnum
from typing import Final

from aiohomematic.const import DataPointCategory, DeviceProfile, Field, Parameter
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.field import DataPointField
from aiohomematic.model.custom.registry import DeviceConfig, DeviceProfileRegistry, ExtendedDeviceConfig
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpActionSelect, DpSensor, DpSwitch
from aiohomematic.property_decorators import state_property


class _LockActivity(StrEnum):
    """Enum with lock activities."""

    LOCKING = "DOWN"
    UNLOCKING = "UP"


class _LockError(StrEnum):
    """Enum with lock errors."""

    NO_ERROR = "NO_ERROR"
    CLUTCH_FAILURE = "CLUTCH_FAILURE"
    MOTOR_ABORTED = "MOTOR_ABORTED"


class _LockTargetLevel(StrEnum):
    """Enum with lock target levels."""

    LOCKED = "LOCKED"
    OPEN = "OPEN"
    UNLOCKED = "UNLOCKED"


class LockState(StrEnum):
    """Enum with lock states."""

    LOCKED = "LOCKED"
    UNKNOWN = "UNKNOWN"
    UNLOCKED = "UNLOCKED"


class BaseCustomDpLock(CustomDataPoint):
    """Class for HomematicIP lock data point."""

    __slots__ = ()

    _category = DataPointCategory.LOCK
    _ignore_multiple_channels_for_name = True

    @property
    @abstractmethod
    def supports_open(self) -> bool:
        """Flag if lock supports open."""

    @state_property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return False

    @state_property
    @abstractmethod
    def is_locked(self) -> bool:
        """Return true if lock is on."""

    @state_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return None

    @state_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return None

    @abstractmethod
    @bind_collector
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""

    @abstractmethod
    @bind_collector
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""

    @abstractmethod
    @bind_collector
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""


class CustomDpIpLock(BaseCustomDpLock):
    """Class for HomematicIP lock data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    # Declarative data point field definitions
    _dp_direction: Final = DataPointField(field=Field.DIRECTION, dpt=DpSensor[str | None])
    _dp_lock_state: Final = DataPointField(field=Field.LOCK_STATE, dpt=DpSensor[str | None])
    _dp_lock_target_level: Final = DataPointField(field=Field.LOCK_TARGET_LEVEL, dpt=DpActionSelect)

    @property
    def supports_open(self) -> bool:
        """Flag if lock supports open."""
        return True

    @state_property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._dp_lock_state.value == LockState.LOCKED

    @state_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _LockActivity.LOCKING
        return None

    @state_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _LockActivity.UNLOCKING
        return None

    @bind_collector
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.LOCKED, collector=collector)

    @bind_collector
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.OPEN, collector=collector)

    @bind_collector
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.UNLOCKED, collector=collector)


class CustomDpButtonLock(BaseCustomDpLock):
    """Class for HomematicIP button lock data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    # Declarative data point field definitions
    _dp_button_lock: Final = DataPointField(field=Field.BUTTON_LOCK, dpt=DpSwitch)

    @property
    def data_point_name_postfix(self) -> str:
        """Return the data_point name postfix."""
        return "BUTTON_LOCK"

    @property
    def supports_open(self) -> bool:
        """Flag if lock supports open."""
        return False

    @state_property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._dp_button_lock.value is True

    @bind_collector
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_button_lock.turn_on(collector=collector)

    @bind_collector
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        return

    @bind_collector
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_button_lock.turn_off(collector=collector)


class CustomDpRfLock(BaseCustomDpLock):
    """Class for classic Homematic lock data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    # Declarative data point field definitions
    _dp_direction: Final = DataPointField(field=Field.DIRECTION, dpt=DpSensor[str | None])
    _dp_error: Final = DataPointField(field=Field.ERROR, dpt=DpSensor[str | None])
    _dp_open: Final = DataPointField(field=Field.OPEN, dpt=DpAction)
    _dp_state: Final = DataPointField(field=Field.STATE, dpt=DpSwitch)

    @property
    def supports_open(self) -> bool:
        """Flag if lock supports open."""
        return True

    @state_property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._dp_error.value is not None and self._dp_error.value != _LockError.NO_ERROR

    @state_property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._dp_state.value is not True

    @state_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _LockActivity.LOCKING
        return None

    @state_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._dp_direction.value is not None:
            return str(self._dp_direction.value) == _LockActivity.UNLOCKING
        return None

    @bind_collector
    async def lock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_state.send_value(value=False, collector=collector)

    @bind_collector
    async def open(self, *, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._dp_open.send_value(value=True, collector=collector)

    @bind_collector
    async def unlock(self, *, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_state.send_value(value=True, collector=collector)


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
