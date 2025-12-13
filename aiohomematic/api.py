# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Simplified facade API for common Homematic operations.

This module provides `HomematicAPI`, a high-level facade that wraps the most
commonly used operations from `CentralUnit`. It offers a streamlined interface
for typical use cases without requiring deep knowledge of the internal architecture.

Quick start
-----------
Using the async context manager (recommended)::

    from aiohomematic.api import HomematicAPI

    async with HomematicAPI.connect(
        host="192.168.1.100",
        username="Admin",
        password="secret",
    ) as api:
        # List all devices
        for device in api.list_devices():
            print(f"{device.address}: {device.name}")

        # Read and write values
        value = await api.read_value(channel_address="VCU0000001:1", parameter="STATE")
        await api.write_value(channel_address="VCU0000001:1", parameter="STATE", value=True)

    # Connection is automatically closed when exiting the context

Manual lifecycle management::

    from aiohomematic.api import HomematicAPI
    from aiohomematic.central import CentralConfig

    config = CentralConfig.for_ccu(
        host="192.168.1.100",
        username="Admin",
        password="secret",
    )
    api = HomematicAPI(config=config)
    await api.start()

    try:
        for device in api.list_devices():
            print(f"{device.address}: {device.name}")
    finally:
        await api.stop()

"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from types import TracebackType
from typing import Any, Final, Self

from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.central.event_bus import DataPointUpdatedEvent
from aiohomematic.const import ParamsetKey
from aiohomematic.interfaces.model import DeviceProtocol
from aiohomematic.retry import with_retry
from aiohomematic.support import get_device_address
from aiohomematic.type_aliases import UnsubscribeCallback

# Type alias for update callback
UpdateCallback = Callable[[str, str, Any], None]


class HomematicAPI:
    """
    Simplified facade for common Homematic operations.

    This class provides a high-level interface for interacting with Homematic
    devices without requiring deep knowledge of the internal architecture.
    It wraps the most commonly used operations from CentralUnit.

    Attributes:
        central: The underlying CentralUnit instance.
        config: The configuration used to create this API instance.

    """

    def __init__(self, *, config: CentralConfig) -> None:
        """
        Initialize the HomematicAPI.

        Args:
            config: Configuration for the central unit. Use CentralConfig.for_ccu()
                or CentralConfig.for_homegear() for simplified setup.

        """
        self._config: Final = config
        self._central: CentralUnit | None = None

    async def __aenter__(self) -> Self:
        """Enter the async context manager and start the API."""
        await self.start()
        return self

    async def __aexit__(  # kwonly: disable
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context manager and stop the API."""
        await self.stop()

    @classmethod
    def connect(
        cls,
        *,
        host: str,
        username: str,
        password: str,
        central_id: str | None = None,
        tls: bool = False,
        verify_tls: bool = True,
        backend: str = "ccu",
    ) -> Self:
        """
        Create a HomematicAPI instance for use as an async context manager.

        This is the recommended way to use the API, as it ensures proper
        cleanup even when exceptions occur.

        Args:
            host: The hostname or IP address of the Homematic backend.
            username: The username for authentication.
            password: The password for authentication.
            central_id: Optional unique identifier for this central (defaults to host).
            tls: Whether to use TLS encryption (default: False).
            verify_tls: Whether to verify TLS certificates (default: True).
            backend: The backend type, either "ccu" or "homegear" (default: "ccu").

        Returns:
            A HomematicAPI instance that can be used as an async context manager.

        Example:
            async with HomematicAPI.connect(
                host="192.168.1.100",
                username="Admin",
                password="secret",
            ) as api:
                for device in api.list_devices():
                    print(device.address)

            # Connection is automatically closed

        Raises:
            ValueError: If backend is not "ccu" or "homegear".

        """
        if backend == "ccu":
            config = CentralConfig.for_ccu(
                name=central_id or host,
                host=host,
                username=username,
                password=password,
                central_id=central_id or host,
                tls=tls,
                verify_tls=verify_tls,
            )
        elif backend == "homegear":
            config = CentralConfig.for_homegear(
                name=central_id or host,
                host=host,
                username=username,
                password=password,
                central_id=central_id or host,
                tls=tls,
                verify_tls=verify_tls,
            )
        else:
            msg = f"Unknown backend: {backend}. Use 'ccu' or 'homegear'."
            raise ValueError(msg)

        return cls(config=config)

    @staticmethod
    @with_retry
    async def _do_fetch_all_device_data(*, client: Any) -> None:
        """Fetch all device data for a single client with retry."""
        await client.fetch_all_device_data()

    @staticmethod
    @with_retry
    async def _do_get_value(
        *,
        client: Any,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
    ) -> Any:
        """Get a value from a client with retry."""
        return await client.get_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    @staticmethod
    @with_retry
    async def _do_set_value(
        *,
        client: Any,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        value: Any,
    ) -> None:
        """Set a value on a client with retry."""
        await client.set_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            value=value,
        )

    @property
    def central(self) -> CentralUnit:
        """Return the underlying CentralUnit instance."""
        if self._central is None:
            msg = "API not started. Call start() first."
            raise RuntimeError(msg)
        return self._central

    @property
    def config(self) -> CentralConfig:
        """Return the configuration."""
        return self._config

    @property
    def is_connected(self) -> bool:
        """Return True if connected to the backend."""
        return (
            self._central is not None
            and self._central.client_coordinator.has_clients
            and not self._central.connection_state.has_any_issue
        )

    def get_device(self, *, address: str) -> DeviceProtocol | None:
        """
        Get a device by its address.

        Args:
            address: The device address (e.g., "VCU0000001").

        Returns:
            The Device object, or None if not found.

        Example:
            device = api.get_device(address="VCU0000001")
            if device:
                print(f"Found: {device.name}")

        """
        return self.central.device_coordinator.get_device(address=address)

    def list_devices(self) -> Iterable[DeviceProtocol]:
        """
        List all known devices.

        Returns:
            Iterable of Device objects.

        Example:
            for device in api.list_devices():
                print(f"{device.address}: {device.name} ({device.model})")

        """
        return self.central.device_registry.devices

    async def read_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        paramset_key: ParamsetKey = ParamsetKey.VALUES,
    ) -> Any:
        """
        Read a parameter value from a device channel.

        This method automatically retries on transient network errors.

        Args:
            channel_address: The channel address (e.g., "VCU0000001:1").
            parameter: The parameter name (e.g., "STATE", "LEVEL").
            paramset_key: The paramset key (default: VALUES).

        Returns:
            The current parameter value.

        Example:
            # Read switch state
            state = await api.read_value(channel_address="VCU0000001:1", parameter="STATE")

            # Read dimmer level
            level = await api.read_value(channel_address="VCU0000002:1", parameter="LEVEL")

        """
        device_address = get_device_address(address=channel_address)
        if (device := self.central.device_coordinator.get_device(address=device_address)) is None:
            msg = f"Device not found for address: {device_address}"
            raise ValueError(msg)
        client = self.central.client_coordinator.get_client(interface_id=device.interface_id)
        return await self._do_get_value(
            client=client,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    async def refresh_data(self) -> None:
        """
        Refresh data from all devices.

        This fetches the latest values from all connected devices.
        Each client fetch automatically retries on transient network errors.
        """
        for client in self.central.client_coordinator.clients:
            await self._do_fetch_all_device_data(client=client)

    async def start(self) -> None:
        """
        Start the API and connect to the Homematic backend.

        This creates the central unit, initializes clients, and starts
        the background scheduler for connection health checks.
        """
        self._central = self._config.create_central()
        await self._central.start()

    async def stop(self) -> None:
        """
        Stop the API and disconnect from the backend.

        This stops all clients, the XML-RPC server, and the background scheduler.
        """
        if self._central is not None:
            await self._central.stop()
            self._central = None

    def subscribe_to_updates(self, *, callback: UpdateCallback) -> UnsubscribeCallback:
        """
        Subscribe to data point value updates.

        The callback is invoked whenever a data point value changes.

        Args:
            callback: Function called with (channel_address, parameter, value)
                when a data point is updated.

        Returns:
            An unsubscribe function to remove the callback.

        Example:
            def on_update(address: str, parameter: str, value: Any) -> None:
                print(f"{address}.{parameter} = {value}")

            unsubscribe = api.subscribe_to_updates(callback=on_update)

            # Later, to stop receiving updates:
            unsubscribe()

        """

        async def event_handler(*, event: DataPointUpdatedEvent) -> None:
            callback(event.dpk.channel_address, event.dpk.parameter, event.value)

        return self.central.event_bus.subscribe(
            event_type=DataPointUpdatedEvent,
            event_key=None,
            handler=event_handler,
        )

    async def write_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        value: Any,
        paramset_key: ParamsetKey = ParamsetKey.VALUES,
    ) -> None:
        """
        Write a parameter value to a device channel.

        This method automatically retries on transient network errors.

        Args:
            channel_address: The channel address (e.g., "VCU0000001:1").
            parameter: The parameter name (e.g., "STATE", "LEVEL").
            value: The value to write.
            paramset_key: The paramset key (default: VALUES).

        Example:
            # Turn on a switch
            await api.write_value(channel_address="VCU0000001:1", parameter="STATE", value=True)

            # Set dimmer to 50%
            await api.write_value(channel_address="VCU0000002:1", parameter="LEVEL", value=0.5)

        """
        device_address = get_device_address(address=channel_address)
        if (device := self.central.device_coordinator.get_device(address=device_address)) is None:
            msg = f"Device not found for address: {device_address}"
            raise ValueError(msg)
        client = self.central.client_coordinator.get_client(interface_id=device.interface_id)
        await self._do_set_value(
            client=client,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            value=value,
        )
