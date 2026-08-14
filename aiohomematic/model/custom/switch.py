# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Custom switch data points for advanced switching devices.

Public API of this module is defined by __all__.
"""

import logging
from typing import ClassVar, Final, Unpack, override

from aiohomematic.const import DataPointCategory, DeviceProfile, Field, Parameter
from aiohomematic.model.combined.field import CombinedTimerField
from aiohomematic.model.custom.access_permission import CustomDpIpAccessPermission
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.field import DataPointField
from aiohomematic.model.custom.mixins import GroupStateMixin, StateChangeArgs, StateChangeTimerMixin
from aiohomematic.model.custom.registry import DeviceProfileRegistry, ExtendedDeviceConfig
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpBinarySensor, DpSwitch
from aiohomematic.property_decorators import DelegatedProperty

_LOGGER: Final = logging.getLogger(__name__)


class CustomDpSwitch(StateChangeTimerMixin, GroupStateMixin, CustomDataPoint):
    """Class for Homematic switch data point."""

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    _category = DataPointCategory.SWITCH

    # Declarative data point field definitions
    _dp_group_state = DataPointField(field=Field.GROUP_STATE, dpt=DpBinarySensor)
    _dp_on_time = CombinedTimerField(value_field=Field.ON_TIME_VALUE)
    _dp_state: Final = DataPointField(field=Field.STATE, dpt=DpSwitch)
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.STATE})

    value: Final = DelegatedProperty[bool | None](path="_dp_state.value")

    @override
    def is_state_change(self, **kwargs: Unpack[StateChangeArgs]) -> bool:
        """Check if the state changes due to kwargs."""
        if self.is_state_change_for_on_off(**kwargs):
            return True
        return super().is_state_change(**kwargs)

    @bind_collector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch off."""
        self.reset_timer_on_time()
        if not self.is_state_change(off=True):
            return
        await self._dp_state.turn_off(collector=collector)

    @bind_collector
    async def turn_on(self, *, on_time: float | None = None, collector: CallParameterCollector | None = None) -> None:
        """Turn the switch on."""
        if on_time is not None:
            self.set_timer_on_time(on_time=on_time)
        if not self.is_state_change(on=True):
            return

        if (timer := self.get_and_start_timer()) is not None:
            await self._dp_on_time.send_value(value=timer, collector=collector)
        await self._dp_state.turn_on(collector=collector)


# =============================================================================
# DeviceProfileRegistry Registration
# =============================================================================

# Data-driven IP Switch registrations: (models, channels)
_IP_SWITCH_REGISTRATIONS: Final[tuple[tuple[str | tuple[str, ...], tuple[int, ...]], ...]] = (
    (("ELV-SH-BS2", "HmIP-BS2", "HmIP-PCBS2"), (4, 8)),
    (
        (
            "ELV-SH-PSMCI",
            "ELV-SH-SW1-BAT",
            "HmIP-DRSI1",
            "HmIP-FSI",
            "HmIP-PCBS",
            "HmIP-PCBS-BAT",
            "HmIP-PS",
            "HmIP-USBSM",
            "HmIP-WGC",
        ),
        (3,),
    ),
    (("HmIP-BSL", "HmIP-BSM"), (4,)),
    ("HmIP-DRSI4", (6, 10, 14, 18)),
    # HmIP-FS6 has no input channel, so the switch channel layout matches HmIP-FSM
    # (channel 1 = SWITCH_TRANSMITTER, channel 2 = SWITCH_VIRTUAL_RECEIVER), while the
    # HmIP-FSI variants add a push-button input on channel 1 and shift the receiver to 3.
    ("HmIP-FS6", (2,)),
    ("HmIP-FSM", (2,)),
    ("HmIP-MOD-OC8", (10, 14, 18, 22, 26, 30, 34, 38)),
    ("HmIP-SCTH230", (8,)),
    ("HmIP-WGT", (4,)),
    ("HmIP-WHS2", (2, 6)),
    ("HmIP-WRC6-230", (9,)),
    ("HmIPW-DRS", (2, 6, 10, 14, 18, 22, 26, 30)),
    ("HmIPW-FIO6", (8, 12, 16, 20, 24, 28)),
)

for _models, _channels in _IP_SWITCH_REGISTRATIONS:
    DeviceProfileRegistry.register(
        category=DataPointCategory.SWITCH,
        models=_models,
        data_point_class=CustomDpSwitch,
        profile_type=DeviceProfile.IP_SWITCH,
        channels=_channels,
    )

# HmIP-SMO230 (Switch with motion sensor - requires extended config)
_SMO230_MOTION_PARAMS: Final = (
    Parameter.ILLUMINATION,
    Parameter.MOTION,
    Parameter.MOTION_DETECTION_ACTIVE,
    Parameter.RESET_MOTION,
)
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-SMO230",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(10,),
    extended=ExtendedDeviceConfig(
        additional_data_points={
            1: _SMO230_MOTION_PARAMS,
            2: _SMO230_MOTION_PARAMS,
            3: _SMO230_MOTION_PARAMS,
            4: _SMO230_MOTION_PARAMS,
        }
    ),
)

# User access permission switches for access-control devices that split the per-user
# permission into read-only STATE + write-only ACCESS_AUTHORIZATION (e.g. HmIP-DLD
# channels 2-9, HmIP-FWI channels 1-8). Registered here (not in access_permission.py)
# so the SWITCH category keeps its usual insertion order in the registry; registering
# from access_permission.py would make SWITCH the first category and reorder
# channel-conflict resolution for unrelated devices.
_IP_ACCESS_PERMISSION_REGISTRATIONS: Final[tuple[tuple[str, tuple[int, ...]], ...]] = (
    ("HmIP-DLD", (2, 3, 4, 5, 6, 7, 8, 9)),
    ("HmIP-FWI", (1, 2, 3, 4, 5, 6, 7, 8)),
)

for _model, _channels in _IP_ACCESS_PERMISSION_REGISTRATIONS:
    DeviceProfileRegistry.register(
        category=DataPointCategory.SWITCH,
        models=_model,
        data_point_class=CustomDpIpAccessPermission,
        profile_type=DeviceProfile.IP_ACCESS_PERMISSION,
        channels=_channels,
    )
