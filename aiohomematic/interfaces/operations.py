"""
Operation protocol interfaces.

This module defines protocol interfaces for operational tasks like
scheduling, caching, and parameter visibility management.
"""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from aiohomematic.const import DeviceDescription, Interface, ParameterData, ParamsetKey
from aiohomematic.type_aliases import AsyncTaskFactoryAny, CoroutineAny

if TYPE_CHECKING:
    from aiohomematic.interfaces.model import ChannelProtocol


@runtime_checkable
class TaskScheduler(Protocol):
    """
    Protocol for scheduling async tasks.

    Implemented by Looper.
    """

    @abstractmethod
    def async_add_executor_job[T](
        self, target: Callable[..., T], *args: Any, name: str, executor: ThreadPoolExecutor | None = None
    ) -> asyncio.Future[T]:
        """Add an executor job from within the event_loop."""

    @abstractmethod
    async def block_till_done(self, *, wait_time: float | None = None) -> None:
        """Block until all pending work is done."""

    @abstractmethod
    def cancel_tasks(self) -> None:
        """Cancel running tasks."""

    @abstractmethod
    def create_task(self, *, target: CoroutineAny | AsyncTaskFactoryAny, name: str) -> None:
        """Create and schedule an async task."""


@runtime_checkable
class ParameterVisibilityProvider(Protocol):
    """
    Protocol for accessing parameter visibility information.

    Implemented by ParameterVisibilityCache.
    """

    @abstractmethod
    def is_relevant_paramset(self, *, channel: ChannelProtocol, paramset_key: ParamsetKey) -> bool:
        """
        Return if a paramset is relevant.

        Required to load MASTER paramsets, which are not initialized by default.
        """

    @abstractmethod
    def model_is_ignored(self, *, model: str) -> bool:
        """Check if a model should be ignored for custom data points."""

    @abstractmethod
    def parameter_is_hidden(self, *, channel: ChannelProtocol, paramset_key: ParamsetKey, parameter: str) -> bool:
        """Check if a parameter is hidden."""

    @abstractmethod
    def parameter_is_un_ignored(
        self, *, channel: ChannelProtocol, paramset_key: ParamsetKey, parameter: str, custom_only: bool = False
    ) -> bool:
        """Check if a parameter is un-ignored (visible)."""

    @abstractmethod
    def should_skip_parameter(
        self, *, channel: ChannelProtocol, paramset_key: ParamsetKey, parameter: str, parameter_is_un_ignored: bool
    ) -> bool:
        """Determine if a parameter should be skipped."""


@runtime_checkable
class DeviceDetailsProvider(Protocol):
    """
    Protocol for accessing device details.

    Implemented by DeviceDescriptionCache.
    """

    @abstractmethod
    def get_address_id(self, *, address: str) -> int:
        """Get an ID for an address."""

    @abstractmethod
    def get_channel_rooms(self, *, channel_address: str) -> set[str]:
        """Get rooms for a channel."""

    @abstractmethod
    def get_device_rooms(self, *, device_address: str) -> set[str]:
        """Get rooms for a device."""

    @abstractmethod
    def get_function_text(self, *, address: str) -> str | None:
        """Get function text for an address."""

    @abstractmethod
    def get_interface(self, *, address: str) -> Interface:
        """Get interface for an address."""

    @abstractmethod
    def get_name(self, *, address: str) -> str | None:
        """Get name for an address."""


@runtime_checkable
class DeviceDescriptionProvider(Protocol):
    """
    Protocol for accessing device descriptions.

    Implemented by DeviceDescriptionCache.
    """

    @abstractmethod
    def get_device_description(self, *, interface_id: str, address: str) -> DeviceDescription:
        """Get device description."""

    @abstractmethod
    def get_device_with_channels(self, *, interface_id: str, device_address: str) -> Mapping[str, DeviceDescription]:
        """Get device with all channel descriptions."""


@runtime_checkable
class ParamsetDescriptionProvider(Protocol):
    """
    Protocol for accessing paramset descriptions.

    Implemented by ParamsetDescriptionCache.
    """

    @abstractmethod
    def get_channel_paramset_descriptions(
        self, *, interface_id: str, channel_address: str
    ) -> Mapping[ParamsetKey, Mapping[str, ParameterData]]:
        """Get all paramset descriptions for a channel."""

    @abstractmethod
    def get_parameter_data(
        self, *, interface_id: str, channel_address: str, paramset_key: ParamsetKey, parameter: str
    ) -> ParameterData | None:
        """Get parameter data from paramset description."""

    @abstractmethod
    def is_in_multiple_channels(self, *, channel_address: str, parameter: str) -> bool:
        """Check if parameter is in multiple channels per device."""
