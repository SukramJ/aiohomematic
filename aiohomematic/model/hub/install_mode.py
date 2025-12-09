# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Module for install mode hub data points."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Final, NamedTuple

from slugify import slugify

from aiohomematic.const import INIT_DATETIME, INSTALL_MODE_ADDRESS, DataPointCategory, HubValueType, InstallModeData
from aiohomematic.decorators import inspector
from aiohomematic.interfaces.central import CentralInfo, ChannelLookup, ConfigProvider, EventBusProvider, EventPublisher
from aiohomematic.interfaces.client import PrimaryClientProvider
from aiohomematic.interfaces.model import (
    ChannelProtocol,
    GenericHubDataPointProtocol,
    GenericInstallModeDataPointProtocol,
)
from aiohomematic.interfaces.operations import ParameterVisibilityProvider, ParamsetDescriptionProvider, TaskScheduler
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.model.support import HubPathData, generate_unique_id, get_hub_data_point_name_data
from aiohomematic.property_decorators import config_property, state_property
from aiohomematic.support import PayloadMixin

_LOGGER: Final = logging.getLogger(__name__)

_SYNC_INTERVAL: Final = 10  # Sync with backend every 10 seconds
_COUNTDOWN_UPDATE_INTERVAL: Final = 1  # Update countdown every second


class InstallModeDpType(NamedTuple):
    """Tuple for install mode data points."""

    button: InstallModeDpButton
    sensor: InstallModeDpSensor


class _BaseInstallModeDataPoint(CallbackDataPoint, GenericHubDataPointProtocol, PayloadMixin):
    """Base class for install mode data points."""

    __slots__ = (
        "_channel",
        "_name_data",
        "_primary_client_provider",
    )

    def __init__(
        self,
        *,
        data: InstallModeData,
        config_provider: ConfigProvider,
        central_info: CentralInfo,
        event_bus_provider: EventBusProvider,
        event_publisher: EventPublisher,
        task_scheduler: TaskScheduler,
        paramset_description_provider: ParamsetDescriptionProvider,
        parameter_visibility_provider: ParameterVisibilityProvider,
        channel_lookup: ChannelLookup,
        primary_client_provider: PrimaryClientProvider,
    ) -> None:
        """Initialize the data_point."""
        PayloadMixin.__init__(self)
        unique_id: Final = generate_unique_id(
            config_provider=config_provider,
            address=INSTALL_MODE_ADDRESS,
            parameter=slugify(data.name),
        )
        self._channel = channel_lookup.identify_channel(text=data.name)
        self._name_data: Final = get_hub_data_point_name_data(
            channel=self._channel, legacy_name=f"{INSTALL_MODE_ADDRESS}_{data.name}", central_name=central_info.name
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

    @property
    def channel(self) -> ChannelProtocol | None:
        """Return the identified channel."""
        return self._channel

    @property
    def enabled_default(self) -> bool:
        """Return if the data_point should be enabled."""
        return True

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
        """Return if the state is uncertain."""
        return False

    @config_property
    def description(self) -> str | None:
        """Return description."""
        return None

    @config_property
    def name(self) -> str:
        """Return the name of the data_point."""
        return self._name_data.name

    @state_property
    def available(self) -> bool:
        """Return the availability of the device."""
        if client := self._primary_client_provider.primary_client:
            return client.supports_install_mode and self._central_info.available
        return False

    def _get_path_data(self) -> HubPathData:
        """Return the path data of the data_point."""
        return HubPathData(name=self._name_data.name)

    def _get_signature(self) -> str:
        """Return the signature of the data_point."""
        return f"{self._category}/{self.name}"


class InstallModeDpSensor(GenericInstallModeDataPointProtocol, _BaseInstallModeDataPoint):
    """Sensor showing remaining install mode time."""

    __slots__ = (
        "_countdown_end",
        "_countdown_task",
        "_sync_task",
        "_task_lock",
    )

    _category = DataPointCategory.HUB_SENSOR

    def __init__(
        self,
        *,
        data: InstallModeData,
        config_provider: ConfigProvider,
        central_info: CentralInfo,
        event_bus_provider: EventBusProvider,
        event_publisher: EventPublisher,
        task_scheduler: TaskScheduler,
        paramset_description_provider: ParamsetDescriptionProvider,
        parameter_visibility_provider: ParameterVisibilityProvider,
        channel_lookup: ChannelLookup,
        primary_client_provider: PrimaryClientProvider,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            config_provider=config_provider,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
            channel_lookup=channel_lookup,
            primary_client_provider=primary_client_provider,
            data=data,
        )
        self._countdown_end: datetime = INIT_DATETIME
        self._countdown_task: asyncio.Task[None] | None = None
        self._sync_task: asyncio.Task[None] | None = None
        self._task_lock: Final = asyncio.Lock()

    @property
    def data_type(self) -> HubValueType | None:
        """Return the data type of the system variable."""
        return HubValueType.INTEGER

    @property
    def is_active(self) -> bool:
        """Return if install mode is active."""
        return self.value > 0

    @config_property
    def unit(self) -> str | None:
        """Return the unit of the data_point."""
        return None

    @state_property
    def value(self) -> int:
        """Return remaining seconds."""
        if self._countdown_end <= datetime.now():
            return 0
        return max(0, int((self._countdown_end - datetime.now()).total_seconds()))

    def start_countdown(self, *, seconds: int) -> None:
        """Start local countdown."""
        self._countdown_end = datetime.now() + timedelta(seconds=seconds)
        self._task_scheduler.create_task(
            target=self._start_tasks_locked(),
            name="install_mode_start_tasks",
        )
        self.publish_data_point_updated_event()

    def stop_countdown(self) -> None:
        """Stop countdown."""
        self._countdown_end = INIT_DATETIME
        self._task_scheduler.create_task(
            target=self._stop_tasks_locked(),
            name="install_mode_stop_tasks",
        )
        self.publish_data_point_updated_event()

    def sync_from_backend(self, *, remaining_seconds: int) -> None:
        """Sync countdown from backend value."""
        if remaining_seconds <= 0:
            self.stop_countdown()
        else:
            # Only resync if significant drift (>3 seconds)
            if abs(self.value - remaining_seconds) > 3:
                self._countdown_end = datetime.now() + timedelta(seconds=remaining_seconds)
            self._task_scheduler.create_task(
                target=self._ensure_tasks_running_locked(),
                name="install_mode_ensure_tasks",
            )
            self.publish_data_point_updated_event()

    async def _backend_sync_loop(self) -> None:
        """Periodically sync with backend."""
        try:
            while self.is_active:
                await asyncio.sleep(_SYNC_INTERVAL)
                if client := self._primary_client_provider.primary_client:
                    if (backend_remaining := await client.get_install_mode()) == 0:
                        self.stop_countdown()
                        break
                    # Resync if significant drift
                    if abs(self.value - backend_remaining) > 3:
                        self._countdown_end = datetime.now() + timedelta(seconds=backend_remaining)
                        self.publish_data_point_updated_event()
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("INSTALL_MODE: Backend sync loop failed")  # i18n-log: ignore
            self.stop_countdown()

    async def _countdown_update_loop(self) -> None:
        """Update countdown value every second."""
        try:
            while self.is_active:
                await asyncio.sleep(_COUNTDOWN_UPDATE_INTERVAL)
                if self.value <= 0:
                    self.stop_countdown()
                    break
                self.publish_data_point_updated_event()
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("INSTALL_MODE: Countdown update loop failed")  # i18n-log: ignore
            self.stop_countdown()

    async def _ensure_tasks_running_locked(self) -> None:
        """Ensure tasks are running with lock protection."""
        async with self._task_lock:
            if not self._countdown_task or self._countdown_task.done():
                self._countdown_task = self._task_scheduler.create_task(
                    target=self._countdown_update_loop(),
                    name="install_mode_countdown",
                )
            if not self._sync_task or self._sync_task.done():
                self._sync_task = self._task_scheduler.create_task(
                    target=self._backend_sync_loop(),
                    name="install_mode_sync",
                )

    async def _start_tasks_locked(self) -> None:
        """Start all tasks with lock protection."""
        async with self._task_lock:
            self._stop_countdown_task_unlocked()
            self._stop_sync_task_unlocked()
            self._countdown_task = self._task_scheduler.create_task(
                target=self._countdown_update_loop(),
                name="install_mode_countdown",
            )
            self._sync_task = self._task_scheduler.create_task(
                target=self._backend_sync_loop(),
                name="install_mode_sync",
            )

    def _stop_countdown_task_unlocked(self) -> None:
        """Stop countdown task without lock. Must be called with _task_lock held."""
        if self._countdown_task and not self._countdown_task.done():
            self._countdown_task.cancel()
        self._countdown_task = None

    def _stop_sync_task_unlocked(self) -> None:
        """Stop sync task without lock. Must be called with _task_lock held."""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
        self._sync_task = None

    async def _stop_tasks_locked(self) -> None:
        """Stop all tasks with lock protection."""
        async with self._task_lock:
            self._stop_countdown_task_unlocked()
            self._stop_sync_task_unlocked()


class InstallModeDpButton(_BaseInstallModeDataPoint):
    """Button to activate/deactivate install mode."""

    __slots__ = ("_sensor",)

    _category = DataPointCategory.HUB_BUTTON

    def __init__(
        self,
        *,
        data: InstallModeData,
        sensor: InstallModeDpSensor,
        config_provider: ConfigProvider,
        central_info: CentralInfo,
        event_bus_provider: EventBusProvider,
        event_publisher: EventPublisher,
        task_scheduler: TaskScheduler,
        paramset_description_provider: ParamsetDescriptionProvider,
        parameter_visibility_provider: ParameterVisibilityProvider,
        channel_lookup: ChannelLookup,
        primary_client_provider: PrimaryClientProvider,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            data=data,
            config_provider=config_provider,
            central_info=central_info,
            event_bus_provider=event_bus_provider,
            event_publisher=event_publisher,
            task_scheduler=task_scheduler,
            paramset_description_provider=paramset_description_provider,
            parameter_visibility_provider=parameter_visibility_provider,
            channel_lookup=channel_lookup,
            primary_client_provider=primary_client_provider,
        )
        self._sensor: Final = sensor

    @property
    def sensor(self) -> GenericInstallModeDataPointProtocol:
        """Return the associated sensor."""
        return self._sensor

    @inspector
    async def activate(
        self,
        *,
        time: int = 60,
        device_address: str | None = None,
    ) -> bool:
        """
        Activate install mode.

        Args:
            time: Duration in seconds (default 60).
            device_address: Optional device address to limit pairing.

        Returns:
            True if successful.

        """
        if (client := self._primary_client_provider.primary_client) and await client.set_install_mode(
            on=True, time=time, device_address=device_address
        ):
            self._sensor.start_countdown(seconds=time)
            return True
        return False

    @inspector
    async def deactivate(self) -> bool:
        """
        Deactivate install mode.

        Returns:
            True if successful.

        """
        if (client := self._primary_client_provider.primary_client) and await client.set_install_mode(on=False):
            self._sensor.stop_countdown()
            return True
        return False

    @inspector
    async def press(self) -> None:
        """Activate install mode with default settings."""
        await self.activate()
