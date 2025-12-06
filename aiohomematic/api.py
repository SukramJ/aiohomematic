# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Simplified facade API for common Homematic operations.

This module provides `HomematicAPI`, a high-level facade that wraps the most
commonly used operations from `CentralUnit`. It offers a streamlined interface
for typical use cases without requiring deep knowledge of the internal architecture.

Quick start
-----------
    from aiohomematic.api import HomematicAPI
    from aiohomematic.central import CentralConfig

    # Create and start the API
    config = CentralConfig.for_ccu(
        host="192.168.1.100",
        username="Admin",
        password="secret",
    )
    api = HomematicAPI(config=config)
    await api.start()

    # List all devices
    for device in api.list_devices():
        print(f"{device.address}: {device.name}")

    # Read a value
    value = await api.read_value(channel_address="VCU0000001:1", parameter="STATE")

    # Write a value
    await api.write_value(channel_address="VCU0000001:1", parameter="STATE", value=True)

    # Subscribe to updates
    def on_update(address: str, parameter: str, value: Any) -> None:
        print(f"{address}.{parameter} = {value}")

    unsubscribe = api.subscribe_to_updates(callback=on_update)

    # Clean up
    unsubscribe()
    await api.stop()

"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.central.event_bus import DataPointUpdatedEvent
from aiohomematic.const import ParamsetKey
from aiohomematic.support import get_device_address

if TYPE_CHECKING:
    from aiohomematic.interfaces.model import DeviceProtocol

# Type alias for update callback
UpdateCallback = Callable[[str, str, Any], None]
UnsubscribeCallback = Callable[[], None]


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
            self._central is not None and self._central.has_clients and not self._central.connection_state.has_any_issue
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
        return self.central.get_device(address=address)

    def list_devices(self) -> Iterable[DeviceProtocol]:
        """
        List all known devices.

        Returns:
            Iterable of Device objects.

        Example:
            for device in api.list_devices():
                print(f"{device.address}: {device.name} ({device.model})")

        """
        return self.central.devices

    async def read_value(
        self,
        *,
        channel_address: str,
        parameter: str,
        paramset_key: ParamsetKey = ParamsetKey.VALUES,
    ) -> Any:
        """
        Read a parameter value from a device channel.

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
        if (device := self.central.get_device(address=device_address)) is None:
            msg = f"Device not found for address: {device_address}"
            raise ValueError(msg)
        client = self.central.get_client(interface_id=device.interface_id)
        return await client.get_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    async def refresh_data(self) -> None:
        """
        Refresh data from all devices.

        This fetches the latest values from all connected devices.
        """
        for client in self.central.clients:
            await client.fetch_all_device_data()

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

        async def event_handler(event: DataPointUpdatedEvent) -> None:
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
        if (device := self.central.get_device(address=device_address)) is None:
            msg = f"Device not found for address: {device_address}"
            raise ValueError(msg)
        client = self.central.get_client(interface_id=device.interface_id)
        await client.set_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            value=value,
        )
