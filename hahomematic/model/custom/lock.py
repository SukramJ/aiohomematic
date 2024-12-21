"""Module for data points implemented using the lock category."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from enum import StrEnum

from hahomematic.const import DataPointCategory, Parameter
from hahomematic.model import device as hmd
from hahomematic.model.custom import definition as hmed
from hahomematic.model.custom.const import DeviceProfile, Field
from hahomematic.model.custom.data_point import CustomDataPoint
from hahomematic.model.custom.support import CustomConfig, ExtendedConfig
from hahomematic.model.data_point import CallParameterCollector, bind_collector
from hahomematic.model.decorators import state_property
from hahomematic.model.generic import DpAction, DpSensor, DpSwitch


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

    _category = DataPointCategory.LOCK

    @state_property
    @abstractmethod
    def is_locked(self) -> bool:
        """Return true if lock is on."""

    @state_property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return False

    @state_property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        return None

    @state_property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        return None

    @property
    @abstractmethod
    def supports_open(self) -> bool:
        """Flag if lock supports open."""

    @abstractmethod
    @bind_collector()
    async def lock(self, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""

    @abstractmethod
    @bind_collector()
    async def unlock(self, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""

    @abstractmethod
    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""


class CustomDpIpLock(BaseCustomDpLock):
    """Class for HomematicIP lock data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_lock_state: DpSensor[str | None] = self._get_data_point(
            field=Field.LOCK_STATE, data_point_type=DpSensor[str | None]
        )
        self._dp_lock_target_level: DpAction = self._get_data_point(
            field=Field.LOCK_TARGET_LEVEL, data_point_type=DpAction
        )
        self._dp_direction: DpSensor[str | None] = self._get_data_point(
            field=Field.DIRECTION, data_point_type=DpSensor[str | None]
        )

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

    @property
    def supports_open(self) -> bool:
        """Flag if lock supports open."""
        return True

    @bind_collector()
    async def lock(self, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.LOCKED, collector=collector)

    @bind_collector()
    async def unlock(self, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.UNLOCKED, collector=collector)

    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._dp_lock_target_level.send_value(value=_LockTargetLevel.OPEN, collector=collector)


class CustomDpButtonLock(BaseCustomDpLock):
    """Class for HomematicIP button lock data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_button_lock: DpSwitch = self._get_data_point(field=Field.BUTTON_LOCK, data_point_type=DpSwitch)

    @property
    def data_point_name_postfix(self) -> str:
        """Return the data_point name postfix."""
        return "BUTTON_LOCK"

    @state_property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._dp_button_lock.value is True

    @property
    def supports_open(self) -> bool:
        """Flag if lock supports open."""
        return False

    @bind_collector()
    async def lock(self, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_button_lock.turn_on(collector=collector)

    @bind_collector()
    async def unlock(self, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_button_lock.turn_off(collector=collector)

    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        return


class CustomDpRfLock(BaseCustomDpLock):
    """Class for classic HomeMatic lock data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_state: DpSwitch = self._get_data_point(field=Field.STATE, data_point_type=DpSwitch)
        self._dp_open: DpAction = self._get_data_point(field=Field.OPEN, data_point_type=DpAction)
        self._dp_direction: DpSensor[str | None] = self._get_data_point(
            field=Field.DIRECTION, data_point_type=DpSensor[str | None]
        )
        self._dp_error: DpSensor[str | None] = self._get_data_point(
            field=Field.ERROR, data_point_type=DpSensor[str | None]
        )

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

    @state_property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._dp_error.value is not None and self._dp_error.value != _LockError.NO_ERROR

    @property
    def supports_open(self) -> bool:
        """Flag if lock supports open."""
        return True

    @bind_collector()
    async def lock(self, collector: CallParameterCollector | None = None) -> None:
        """Lock the lock."""
        await self._dp_state.send_value(value=False, collector=collector)

    @bind_collector()
    async def unlock(self, collector: CallParameterCollector | None = None) -> None:
        """Unlock the lock."""
        await self._dp_state.send_value(value=True, collector=collector)

    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the lock."""
        await self._dp_open.send_value(value=True, collector=collector)


def make_ip_lock(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP lock data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpLock,
        device_profile=DeviceProfile.IP_LOCK,
        custom_config=custom_config,
    )


def make_ip_button_lock(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP ip button lock data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpButtonLock,
        device_profile=DeviceProfile.IP_BUTTON_LOCK,
        custom_config=custom_config,
    )


def make_rf_button_lock(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP rf button lock data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpButtonLock,
        device_profile=DeviceProfile.RF_BUTTON_LOCK,
        custom_config=custom_config,
    )


def make_rf_lock(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic rf lock data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpRfLock,
        device_profile=DeviceProfile.RF_LOCK,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "HM-Sec-Key": CustomConfig(
        make_ce_func=make_rf_lock,
        channels=(1,),
        extended=ExtendedConfig(
            additional_data_points={
                1: (
                    Parameter.DIRECTION,
                    Parameter.ERROR,
                ),
            }
        ),
    ),
    "HmIP-DLD": CustomConfig(
        make_ce_func=make_ip_lock,
        extended=ExtendedConfig(
            additional_data_points={
                0: (Parameter.ERROR_JAMMED,),
            }
        ),
    ),
    "HM-TC-IT-WM-W-EU": CustomConfig(
        make_ce_func=make_rf_button_lock,
        channels=(None,),
    ),
    "ALPHA-IP-RBG": CustomConfig(
        make_ce_func=make_ip_button_lock,
        channels=(0,),
    ),
    "HmIP-BWTH": CustomConfig(
        make_ce_func=make_ip_button_lock,
        channels=(0,),
    ),
    "HmIP-FAL": CustomConfig(
        make_ce_func=make_ip_button_lock,
        channels=(0,),
    ),
    "HmIP-WTH": CustomConfig(
        make_ce_func=make_ip_button_lock,
        channels=(0,),
    ),
    "HmIP-eTRV": CustomConfig(
        make_ce_func=make_ip_button_lock,
        channels=(0,),
    ),
    "HmIPW-FAL": CustomConfig(
        make_ce_func=make_ip_button_lock,
        channels=(0,),
    ),
    "HmIPW-WTH": CustomConfig(
        make_ce_func=make_ip_button_lock,
        channels=(0,),
    ),
}

hmed.ALL_DEVICES[DataPointCategory.LOCK] = DEVICES
