"""Module for data points implemented using the update category."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Final

from hahomematic.const import (
    CALLBACK_TYPE,
    DEFAULT_CUSTOM_ID,
    HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES,
    HMIP_FIRMWARE_UPDATE_READY_STATES,
    DataPointCategory,
    Interface,
)
from hahomematic.decorators import inspector
from hahomematic.exceptions import HaHomematicException
from hahomematic.model import device as hmd
from hahomematic.model.data_point import CallbackDataPoint
from hahomematic.model.decorators import config_property, state_property
from hahomematic.model.support import DataPointPathData, PayloadMixin, generate_unique_id

__all__ = ["DpUpdate"]


class DpUpdate(CallbackDataPoint, PayloadMixin):
    """
    Implementation of a update.

    This is a default data point that gets automatically generated.
    """

    _category = DataPointCategory.UPDATE

    def __init__(self, device: hmd.Device) -> None:
        """Init the callback data_point."""
        PayloadMixin.__init__(self)
        self._device: Final = device
        super().__init__(
            central=device.central,
            unique_id=generate_unique_id(central=device.central, address=device.address, parameter="Update"),
        )
        self._set_modified_at()

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

    @property
    def device(self) -> hmd.Device:
        """Return the device of the data_point."""
        return self._device

    @property
    def full_name(self) -> str:
        """Return the full name of the data_point."""
        return f"{self._device.name} Update"

    @config_property
    def name(self) -> str:
        """Return the name of the data_point."""
        return "Update"

    @state_property
    def firmware(self) -> str | None:
        """Version installed and in use."""
        return self._device.firmware

    @state_property
    def firmware_update_state(self) -> str | None:
        """Latest version available for install."""
        return self._device.firmware_update_state

    @state_property
    def in_progress(self) -> bool:
        """Update installation progress."""
        if self._device.interface == Interface.HMIP_RF:
            return self._device.firmware_update_state in HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES
        return False

    @state_property
    def latest_firmware(self) -> str | None:
        """Latest firmware available for install."""
        if self._device.available_firmware and (
            (
                self._device.interface == Interface.HMIP_RF
                and self._device.firmware_update_state in HMIP_FIRMWARE_UPDATE_READY_STATES
            )
            or self._device.interface in (Interface.BIDCOS_RF, Interface.BIDCOS_WIRED)
        ):
            return self._device.available_firmware
        return self._device.firmware

    def _get_path_data(self) -> DataPointPathData:
        """Return the path data of the data_point."""
        return DataPointPathData(
            interface=None,
            address=self._device.address,
            channel_no=None,
            kind=DataPointCategory.UPDATE,
        )

    def register_data_point_updated_callback(self, cb: Callable, custom_id: str) -> CALLBACK_TYPE:
        """Register update callback."""
        if custom_id != DEFAULT_CUSTOM_ID:
            if self._custom_id is not None:
                raise HaHomematicException(
                    f"REGISTER_UPDATE_CALLBACK failed: hm_data_point: {self.full_name} is already registered by {self._custom_id}"
                )
            self._custom_id = custom_id

        if self._device.register_firmware_update_callback(cb) is not None:
            return partial(self._unregister_data_point_updated_callback, cb=cb, custom_id=custom_id)
        return None

    def _unregister_data_point_updated_callback(self, cb: Callable, custom_id: str) -> None:
        """Unregister update callback."""
        if custom_id is not None:
            self._custom_id = None
        self._device.unregister_firmware_update_callback(cb)

    @inspector()
    async def update_firmware(self, refresh_after_update_intervals: tuple[int, ...]) -> bool:
        """Turn the update on."""
        return await self._device.update_firmware(refresh_after_update_intervals=refresh_after_update_intervals)

    @inspector()
    async def refresh_firmware_data(self) -> None:
        """Refresh device firmware data."""
        await self._device.central.refresh_firmware_data(device_address=self._device.address)
        self._set_modified_at()
