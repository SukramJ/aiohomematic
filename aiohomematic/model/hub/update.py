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
from aiohomematic.const import HUB_ADDRESS, DataPointCategory, SystemUpdateData
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.central import (
    CentralInfoProtocol,
    ConfigProviderProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
)
from aiohomematic.interfaces.client import PrimaryClientProviderProtocol
from aiohomematic.interfaces.model import ChannelProtocol, GenericHubDataPointProtocol
from aiohomematic.interfaces.operations import (
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import HubPathData, PathData, generate_unique_id, get_hub_data_point_name_data
from aiohomematic.property_decorators import DelegatedProperty, Kind
from aiohomematic.support import PayloadMixin

_LOGGER: Final = logging.getLogger(__name__)

_UPDATE_NAME: Final = "System Update"


class HmUpdate(CallbackDataPoint, GenericHubDataPointProtocol, PayloadMixin):
    """Class for a Homematic system update data point."""

    __slots__ = (
        "_available_firmware",
        "_config_provider",
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
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        event_publisher: EventPublisherProtocol,
        task_scheduler: TaskSchedulerProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        primary_client_provider: PrimaryClientProviderProtocol,
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
        self._config_provider: Final = config_provider
        self._primary_client_provider: Final = primary_client_provider
        self._state_uncertain: bool = True
        self._current_firmware: str = ""
        self._available_firmware: str = ""
        self._update_available: bool = False
        self._update_in_progress: bool = False
        self._version_before_update: str | None = None

    available: Final = DelegatedProperty[bool](path="_central_info.available", kind=Kind.STATE)
    available_firmware: Final = DelegatedProperty[str](path="_available_firmware", kind=Kind.STATE)
    current_firmware: Final = DelegatedProperty[str](path="_current_firmware", kind=Kind.STATE)
    enabled_default: Final = DelegatedProperty[bool](path="_enabled_default")
    full_name: Final = DelegatedProperty[str](path="_name_data.full_name")
    in_progress: Final = DelegatedProperty[bool](path="_update_in_progress", kind=Kind.STATE)
    name: Final = DelegatedProperty[str](path="_name_data.name", kind=Kind.CONFIG)
    state_uncertain: Final = DelegatedProperty[bool](path="_state_uncertain")
    update_available: Final = DelegatedProperty[bool](path="_update_available", kind=Kind.STATE)

    @property
    def channel(self) -> ChannelProtocol | None:
        """Return the identified channel."""
        return None

    @property
    def description(self) -> str | None:
        """Return data point description."""
        return None

    @property
    def legacy_name(self) -> str | None:
        """Return the original name."""
        return None

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
            while (
                datetime.now() - start_time
            ).total_seconds() < self._config_provider.config.schedule_timer_config.system_update_progress_timeout:
                await asyncio.sleep(
                    self._config_provider.config.schedule_timer_config.system_update_progress_check_interval
                )

                if client := self._primary_client_provider.primary_client:
                    try:
                        update_info = await client.get_system_update_info()

                        if update_info and update_info.current_firmware != self._version_before_update:
                            _LOGGER.info(
                                i18n.tr(
                                    key="log.model.hub.update.progress_completed",
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
                                key="log.model.hub.update.progress_poll_error",
                                error=str(err),
                            )
                        )
            else:
                _LOGGER.warning(
                    i18n.tr(
                        key="log.model.hub.update.progress_timeout",
                        timeout=self._config_provider.config.schedule_timer_config.system_update_progress_timeout,
                    )
                )
        finally:
            self._update_in_progress = False
            self._version_before_update = None
            self._set_modified_at(modified_at=datetime.now())
            self.publish_data_point_updated_event()
