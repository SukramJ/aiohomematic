# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for data points implemented using the update category."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from aiohomematic.const import (
    HMIP_FIRMWARE_UPDATE_IN_PROGRESS_STATES,
    HMIP_FIRMWARE_UPDATE_READY_STATES,
    DataPointCategory,
    Interface,
    InternalCustomID,
)
from aiohomematic.decorators import inspector
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.interfaces.model import DeviceProtocol
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import DataPointPathData, generate_unique_id
from aiohomematic.property_decorators import config_property, state_property
from aiohomematic.support import PayloadMixin
from aiohomematic.type_aliases import DataPointUpdatedHandler, UnsubscribeCallback

__all__ = ["DpUpdate"]


class DpUpdate(CallbackDataPoint, PayloadMixin):
    """
    Implementation of a update.

    This is a default data point that gets automatically generated.
    """

    __slots__ = ("_device",)

    _category = DataPointCategory.UPDATE

    def __init__(self, *, device: DeviceProtocol) -> None:
        """Initialize the callback data_point."""
        PayloadMixin.__init__(self)
        self._device: Final = device
        super().__init__(
            unique_id=generate_unique_id(
                config_provider=device.config_provider,
                address=device.address,
                parameter="Update",
            ),
            central_info=device.central_info,
            event_bus_provider=device.event_bus_provider,
            event_publisher=device.event_publisher,
            task_scheduler=device.task_scheduler,
            paramset_description_provider=device.paramset_description_provider,
            parameter_visibility_provider=device.parameter_visibility_provider,
        )
        self._set_modified_at(modified_at=datetime.now())

    @property
    def device(self) -> DeviceProtocol:
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
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

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

    async def on_config_changed(self) -> None:
        """Do what is needed on device config change."""

    @inspector
    async def refresh_firmware_data(self) -> None:
        """Refresh device firmware data."""
        await self._device.device_data_refresher.refresh_firmware_data(device_address=self._device.address)
        self._set_modified_at(modified_at=datetime.now())

    def subscribe_to_data_point_updated(
        self, *, handler: DataPointUpdatedHandler, custom_id: str
    ) -> UnsubscribeCallback:
        """Subscribe to data point updates via EventBus."""
        if custom_id != InternalCustomID.DEFAULT:
            if self._custom_id is not None:
                raise AioHomematicException(  # i18n-exc: ignore
                    f"SUBSCRIBE failed: hm_data_point: {self.full_name} is already registered by {self._custom_id}"
                )
            self._custom_id = custom_id

        unsubscribe = self._device.subscribe_to_firmware_updated(handler=handler)

        # Wrap unsubscribe to also reset custom_id
        def wrapped_unsubscribe() -> None:
            unsubscribe()
            if custom_id != InternalCustomID.DEFAULT:
                self._custom_id = None

        return wrapped_unsubscribe

    @inspector
    async def update_firmware(self, *, refresh_after_update_intervals: tuple[int, ...]) -> bool:
        """Turn the update on."""
        return await self._device.update_firmware(refresh_after_update_intervals=refresh_after_update_intervals)

    def _get_path_data(self) -> DataPointPathData:
        """Return the path data of the data_point."""
        return DataPointPathData(
            interface=None,
            address=self._device.address,
            channel_no=None,
            kind=DataPointCategory.UPDATE,
        )

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self._device.model}"
