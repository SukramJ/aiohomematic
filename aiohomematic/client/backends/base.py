# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
# pylint: disable=unnecessary-ellipsis
"""
Base backend class with shared functionality.

Provides default implementations that return empty/False for unsupported
operations, allowing subclasses to only implement what they support.

Public API
----------
- BaseBackend: Abstract base class for backend implementations
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.client.backends.capabilities import BackendCapabilities
from aiohomematic.const import (
    BackupData,
    CommandRxMode,
    DescriptionMarker,
    DeviceDescription,
    DeviceDetail,
    InboxDeviceData,
    Interface,
    ParameterData,
    ParamsetKey,
    ProgramData,
    ServiceMessageData,
    ServiceMessageType,
    SystemInformation,
    SystemUpdateData,
    SystemVariableData,
)

if TYPE_CHECKING:
    from aiohomematic.client.circuit_breaker import CircuitBreaker

__all__ = ["BaseBackend"]

_LOGGER: Final = logging.getLogger(__name__)


class BaseBackend(ABC):
    """
    Abstract base class for backend implementations.

    Provides default implementations that return empty/False for
    unsupported operations, allowing subclasses to only implement
    what they support.
    """

    __slots__ = (
        "_capabilities",
        "_interface",
        "_interface_id",
        "_system_information",
    )

    def __init__(
        self,
        *,
        interface: Interface,
        interface_id: str,
        capabilities: BackendCapabilities,
    ) -> None:
        """Initialize the base backend."""
        self._interface: Final = interface
        self._interface_id: Final = interface_id
        self._capabilities = capabilities
        self._system_information: SystemInformation

    @property
    def all_circuit_breakers_closed(self) -> bool:
        """Return True if all circuit breakers are in closed state."""
        return True

    @property
    def capabilities(self) -> BackendCapabilities:
        """Return the capability flags for this backend."""
        return self._capabilities

    @property
    def circuit_breaker(self) -> CircuitBreaker | None:
        """Return the primary circuit breaker for metrics access."""
        return None

    @property
    def interface(self) -> Interface:
        """Return the interface type."""
        return self._interface

    @property
    def interface_id(self) -> str:
        """Return the interface identifier."""
        return self._interface_id

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the backend model name."""
        ...

    @property
    def system_information(self) -> SystemInformation:
        """Return system information."""
        return self._system_information

    async def accept_device_in_inbox(self, *, device_address: str) -> bool:
        """Accept inbox device (unsupported by default)."""
        return False

    async def add_link(
        self,
        *,
        sender_address: str,
        receiver_address: str,
        name: str,
        description: str,
    ) -> None:
        """Add link (unsupported by default)."""

    @abstractmethod
    async def check_connection(self, *, handle_ping_pong: bool, caller_id: str | None = None) -> bool:
        """Check if connection is alive."""
        ...

    async def create_backup_and_download(
        self,
        *,
        max_wait_time: float = 300.0,
        poll_interval: float = 5.0,
    ) -> BackupData | None:
        """Create backup (unsupported by default)."""
        return None

    @abstractmethod
    async def deinit_proxy(self, *, init_url: str) -> None:
        """De-initialize proxy."""
        ...

    async def delete_system_variable(self, *, name: str) -> bool:
        """Delete system variable (unsupported by default)."""
        return False

    async def execute_program(self, *, pid: str) -> bool:
        """Execute program (unsupported by default)."""
        return False

    async def get_all_device_data(self, *, interface: Interface) -> dict[str, Any] | None:
        """Return all device data (unsupported by default)."""
        return None

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Return all functions (unsupported by default)."""
        return {}

    async def get_all_programs(self, *, markers: tuple[DescriptionMarker | str, ...]) -> tuple[ProgramData, ...]:
        """Return all programs (unsupported by default)."""
        return ()

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Return all rooms (unsupported by default)."""
        return {}

    async def get_all_system_variables(
        self, *, markers: tuple[DescriptionMarker | str, ...]
    ) -> tuple[SystemVariableData, ...] | None:
        """Return all system variables (unsupported by default)."""
        return None

    @abstractmethod
    async def get_device_description(self, *, address: str) -> DeviceDescription | None:
        """Return device description for address."""
        ...

    async def get_device_details(self, *, addresses: tuple[str, ...] | None = None) -> list[DeviceDetail] | None:
        """Return device details (unsupported by default)."""
        return None

    async def get_inbox_devices(self) -> tuple[InboxDeviceData, ...]:
        """Return inbox devices (unsupported by default)."""
        return ()

    async def get_install_mode(self) -> int:
        """Return install mode time (unsupported by default)."""
        return 0

    async def get_link_peers(self, *, channel_address: str) -> tuple[str, ...]:
        """Return link peers (unsupported by default)."""
        return ()

    async def get_links(self, *, channel_address: str, flags: int) -> dict[str, Any]:
        """Return links (unsupported by default)."""
        return {}

    async def get_metadata(self, *, address: str, data_id: str) -> dict[str, Any]:
        """Return metadata (unsupported by default)."""
        return {}

    @abstractmethod
    async def get_paramset(self, *, channel_address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
        """Return paramset."""
        ...

    @abstractmethod
    async def get_paramset_description(
        self, *, channel_address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Return paramset description."""
        ...

    async def get_rega_id_by_address(self, *, address: str) -> int | None:
        """Return ReGa ID (unsupported by default)."""
        return None

    async def get_service_messages(
        self, *, message_type: ServiceMessageType | None = None
    ) -> tuple[ServiceMessageData, ...]:
        """Return service messages (unsupported by default)."""
        return ()

    async def get_system_update_info(self) -> SystemUpdateData | None:
        """Return system update info (unsupported by default)."""
        return None

    async def get_system_variable(self, *, name: str) -> Any:
        """Return system variable value (unsupported by default)."""
        return None

    @abstractmethod
    async def get_value(self, *, channel_address: str, parameter: str) -> Any:
        """Return parameter value."""
        ...

    async def has_program_ids(self, *, rega_id: int) -> bool:
        """Check program IDs (unsupported by default)."""
        return False

    @abstractmethod
    async def init_proxy(self, *, init_url: str, interface_id: str) -> None:
        """Initialize proxy with callback URL."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend."""
        ...

    @abstractmethod
    async def list_devices(self) -> tuple[DeviceDescription, ...] | None:
        """Return all device descriptions."""
        ...

    @abstractmethod
    async def put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set paramset values."""
        ...

    async def remove_link(self, *, sender_address: str, receiver_address: str) -> None:
        """Remove link (unsupported by default)."""

    async def rename_channel(self, *, rega_id: int, new_name: str) -> bool:
        """Rename channel (unsupported by default)."""
        return False

    async def rename_device(self, *, rega_id: int, new_name: str) -> bool:
        """Rename device (unsupported by default)."""
        return False

    async def report_value_usage(self, *, channel_address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage (unsupported by default)."""
        return False

    def reset_circuit_breakers(self) -> None:
        """Reset all circuit breakers to closed state."""

    async def set_install_mode(
        self,
        *,
        on: bool = True,
        time: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """Set install mode (unsupported by default)."""
        return False

    async def set_metadata(self, *, address: str, data_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Set metadata (unsupported by default)."""
        return {}

    async def set_program_state(self, *, pid: str, state: bool) -> bool:
        """Set program state (unsupported by default)."""
        return False

    async def set_system_variable(self, *, name: str, value: Any) -> bool:
        """Set system variable (unsupported by default)."""
        return False

    @abstractmethod
    async def set_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: CommandRxMode | None = None,
    ) -> None:
        """Set parameter value."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the backend."""
        ...

    async def trigger_firmware_update(self) -> bool:
        """Trigger system firmware update (unsupported by default)."""
        return False

    async def update_device_firmware(self, *, device_address: str) -> bool:
        """Update device firmware (unsupported by default)."""
        return False
