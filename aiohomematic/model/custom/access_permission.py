# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Custom access permission data points for door lock user channels.

Public API of this module is defined by __all__.
"""

from enum import StrEnum, unique
from typing import ClassVar, Final, Unpack, override

from aiohomematic import ccu_translations
from aiohomematic.const import DataPointCategory, Field, Parameter
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.field import DataPointField
from aiohomematic.model.custom.mixins import StateChangeArg, StateChangeArgs
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpActionSelect, DpBinarySensor
from aiohomematic.model.support import DataPointNameData, get_data_point_name_data
from aiohomematic.property_decorators import DelegatedProperty

__all__ = ["CustomDpIpAccessPermission"]


@unique
class _AccessAuthorization(StrEnum):
    """Enum with user access authorization values."""

    DISABLE = "DISABLE"
    ENABLE = "ENABLE"


class CustomDpIpAccessPermission(CustomDataPoint):
    """
    Class for a HomematicIP user access permission switch.

    Combines the read-only ``STATE`` (current permission) with the write-only
    ``ACCESS_AUTHORIZATION`` control (enable/disable) of a single ACCESS_RECEIVER
    channel into one switch, mirroring the ``PERMISSION_STATE`` switch of newer
    door locks (e.g. HmIP-DLP). Used for the per-user channels of the HmIP-DLD.
    """

    __slots__ = ()  # Required to prevent __dict__ creation (descriptors are class-level)

    _category = DataPointCategory.SWITCH

    # Declarative data point field definitions
    _dp_authorization: Final = DataPointField(field=Field.ACCESS_AUTHORIZATION, dpt=DpActionSelect)
    _dp_state: Final = DataPointField(field=Field.STATE, dpt=DpBinarySensor)
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.STATE})

    value: Final = DelegatedProperty[bool | None](path="_dp_state.value")

    @override
    def is_state_change(self, **kwargs: Unpack[StateChangeArgs]) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(StateChangeArg.ON) is not None and self.value is not True:
            return True
        if kwargs.get(StateChangeArg.OFF) is not None and self.value is not False:
            return True
        return super().is_state_change(**kwargs)

    @bind_collector
    async def turn_off(self, *, collector: CallParameterCollector | None = None) -> None:
        """Revoke the user access permission."""
        if not self.is_state_change(off=True):
            return
        await self._dp_authorization.send_value(value=_AccessAuthorization.DISABLE, collector=collector)

    @bind_collector
    async def turn_on(self, *, collector: CallParameterCollector | None = None) -> None:
        """Grant the user access permission."""
        if not self.is_state_change(on=True):
            return
        await self._dp_authorization.send_value(value=_AccessAuthorization.ENABLE, collector=collector)

    @override
    def _get_data_point_name(self) -> DataPointNameData:
        """
        Create a per-channel name so each user channel is distinguishable.

        The ACCESS_RECEIVER channels usually carry only the device name (no channel
        suffix), so the default custom naming would produce identical names for all
        user channels. Use the generic parameter naming instead, which appends a
        ``chN`` marker for parameters present on multiple channels — mirroring the
        per-channel ``PERMISSION_STATE`` switches of the HmIP-DLP.
        """
        return get_data_point_name_data(
            channel=self._channel,
            parameter=Parameter.ACCESS_AUTHORIZATION,
            parameter_translation=ccu_translations.get_parameter_translation(
                parameter=Parameter.ACCESS_AUTHORIZATION,
                channel_type=self._channel.type_name,
                locale=self._channel.device.config_provider.config.locale,
            ),
        )

    @override
    def _post_init(self) -> None:
        """
        Resolve the write-only ACCESS_AUTHORIZATION control after field init.

        ACCESS_AUTHORIZATION is globally ignored; declaring it as a profile field
        would make it a globally-required parameter and expose a bare control data
        point on every unrelated device that has it (HmIP-WKP, HmIP-FWI). It is
        instead un-ignored only for HmIP-DLD and resolved here from the generic data
        point, consumed (NO_CREATE) into this switch so it is not shown separately.
        """
        super()._post_init()
        self._add_data_point(
            field=Field.ACCESS_AUTHORIZATION,
            data_point=self._device.get_generic_data_point(
                channel_address=self._channel.address, parameter=Parameter.ACCESS_AUTHORIZATION
            ),
            is_visible=False,
        )


# NOTE: The DeviceProfileRegistry registration for this SWITCH-category data point
# lives in switch.py (next to the other SWITCH registrations), not here. Registering
# it from this module would make it the first SWITCH-category insertion in the
# registry, which reorders category processing and changes channel-conflict
# resolution for unrelated multi-profile devices (e.g. HmIP-WGTC).
