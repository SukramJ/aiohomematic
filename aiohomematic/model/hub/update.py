# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for hub update data point."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Final

from slugify import slugify

from aiohomematic import i18n
from aiohomematic.const import (
    HUB_ADDRESS,
    SYSTEM_UPDATE_PROGRESS_CHECK_INTERVAL,
    SYSTEM_UPDATE_PROGRESS_TIMEOUT,
    DataPointCategory,
    SystemUpdateData,
)
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.central import CentralInfo, ConfigProvider, EventBusProvider, EventPublisher
from aiohomematic.interfaces.client import PrimaryClientProvider
from aiohomematic.interfaces.model import ChannelProtocol, GenericHubDataPointProtocol
from aiohomematic.interfaces.operations import ParameterVisibilityProvider, ParamsetDescriptionProvider, TaskScheduler
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import HubPathData, PathData, generate_unique_id, get_hub_data_point_name_data
from aiohomematic.property_decorators import config_property, state_property
from aiohomematic.support import PayloadMixin

_LOGGER: Final = logging.getLogger(__name__)

_UPDATE_NAME: Final = "System Update"


class HmUpdate(CallbackDataPoint, GenericHubDataPointProtocol, PayloadMixin):
    """Class for a Homematic system update data point."""

    __slots__ = (
        "_available_firmware",
        "_current_firmware",
        "_name_data",
        "_primary_client_provider",
        "_state_uncertain",
        "_update_available",
        "_update_in_progress",
        "_version_before_update",
    )

    _category = DataPointCategory.HUB_UPDATE
    _enabled_default = True

    def __init__(
        self,
        *,
        config_provider: ConfigProvider,
        central_info: CentralInfo,
        event_bus_provider: EventBusProvider,
        event_publisher: EventPublisher,
        task_scheduler: TaskScheduler,
        paramset_description_provider: ParamsetDescriptionProvider,
        parameter_visibility_provider: ParameterVisibilityProvider,
        primary_client_provider: PrimaryClientProvider,
    ) -> None:
        """Initialize the data_point."""
        PayloadMixin.__init__(self)
        unique_id: Final = generate_unique_id(
            config_provider=config_provider,
            address=HUB_ADDRESS,
            parameter=slugify(_UPDATE_NAME),
        )
        self._name_data: Final = get_hub_data_point_name_data(
            channel=None, legacy_name=_UPDATE_NAME, central_name=central_info.name
        )

        super().__init__(
            unique_id=unique_id,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
        )
        self._primary_client_provider: Final = primary_client_provider
        self._state_uncertain: bool = True
        self._current_firmware: str = ""
        self._available_firmware: str = ""
        self._update_available: bool = False
        self._update_in_progress: bool = False
        self._version_before_update: str | None = None

    @property
    def channel(self) -> ChannelProtocol | None:
        """Return the identified channel."""
        return None

    @property
    def description(self) -> str | None:
        """Return data point description."""
        return None

    @property
    def enabled_default(self) -> bool:
        """Return if the data_point should be enabled."""
        return self._enabled_default

    @property
    def full_name(self) -> str:
        """Return the fullname of the data_point."""
        return self._name_data.full_name

    @property
    def legacy_name(self) -> str | None:
        """Return the original name."""
        return None

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._state_uncertain

    @config_property
    def name(self) -> str:
        """Return the name of the data_point."""
        return self._name_data.name

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._central_info.available

    @state_property
    def available_firmware(self) -> str:
        """Return the available firmware version."""
        return self._available_firmware

    @state_property
    def current_firmware(self) -> str:
        """Return the current firmware version."""
        return self._current_firmware

    @state_property
    def in_progress(self) -> bool:
        """Return if an update is currently in progress."""
        return self._update_in_progress

    @state_property
    def update_available(self) -> bool:
        """Return if an update is available."""
        return self._update_available

    @inspector
    async def install(self) -> bool:
        """Trigger the firmware update process with progress monitoring."""
        if client := self._primary_client_provider.primary_client:
            # Store current version for progress detection
            self._version_before_update = self._current_firmware
            if result := await client.trigger_firmware_update():
                self._update_in_progress = True
                self.publish_data_point_updated_event()

                # Start progress monitoring task
                self._task_scheduler.create_task(
                    target=self._monitor_update_progress(),
                    name="hub_update_progress_monitor",
                )

            return result
        return False

    def update_data(self, *, data: SystemUpdateData, write_at: datetime) -> None:
        """Update the data point with new system update data."""
        do_update: bool = False
        if self._current_firmware != data.current_firmware:
            self._current_firmware = data.current_firmware
            do_update = True
        if self._available_firmware != data.available_firmware:
            self._available_firmware = data.available_firmware
            do_update = True
        if self._update_available != data.update_available:
            self._update_available = data.update_available
            do_update = True

        if do_update:
            self._set_modified_at(modified_at=write_at)
        else:
            self._set_refreshed_at(refreshed_at=write_at)
        self._state_uncertain = False
        self.publish_data_point_updated_event()

    def _get_path_data(self) -> PathData:
        """Return the path data of the data_point."""
        return HubPathData(name=slugify(_UPDATE_NAME))

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self.name}"

    async def _monitor_update_progress(self) -> None:
        """Monitor update progress by polling system information."""
        start_time = datetime.now()

        try:
            while (datetime.now() - start_time).total_seconds() < SYSTEM_UPDATE_PROGRESS_TIMEOUT:
                await asyncio.sleep(SYSTEM_UPDATE_PROGRESS_CHECK_INTERVAL)

                if client := self._primary_client_provider.primary_client:
                    try:
                        update_info = await client.get_system_update_info()

                        if update_info and update_info.current_firmware != self._version_before_update:
                            _LOGGER.info(
                                i18n.tr(
                                    "log.model.hub.update.progress_completed",
                                    old_version=self._version_before_update,
                                    new_version=update_info.current_firmware,
                                )
                            )
                            # Update data with new firmware info
                            self._current_firmware = update_info.current_firmware
                            self._available_firmware = update_info.available_firmware
                            self._update_available = update_info.update_available
                            # Reset circuit breakers after successful update
                            # to allow immediate data refresh
                            client.reset_circuit_breakers()
                            break
                    except Exception as err:
                        # CCU may be offline during reboot - continue polling
                        _LOGGER.debug(
                            i18n.tr(
                                "log.model.hub.update.progress_poll_error",
                                error=str(err),
                            )
                        )
            else:
                _LOGGER.warning(
                    i18n.tr(
                        "log.model.hub.update.progress_timeout",
                        timeout=SYSTEM_UPDATE_PROGRESS_TIMEOUT,
                    )
                )
        finally:
            self._update_in_progress = False
            self._version_before_update = None
            self._set_modified_at(modified_at=datetime.now())
            self.publish_data_point_updated_event()
