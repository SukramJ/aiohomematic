"""Example for aiohomematic."""

# !/usr/bin/python3
from __future__ import annotations

import asyncio
import logging
import sys

from aiohomematic import const
from aiohomematic.central import CentralConfig
from aiohomematic.central.events import DataPointsCreatedEvent, DeviceLifecycleEvent, DeviceLifecycleEventType
from aiohomematic.client import InterfaceConfig

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

CCU_HOST = "XXX"
CCU_USERNAME = "xxx"
CCU_PASSWORD = "xxx"


class Example:
    """Example for aiohomematic."""

    # Create a server that listens on LOCAL_HOST:* and identifies itself as myserver.
    got_devices = False

    def __init__(self):
        """Init example."""
        self.SLEEPCOUNTER = 0
        self.central = None

    def _on_device_lifecycle(self, *, event: DeviceLifecycleEvent) -> None:
        """Handle device lifecycle events."""
        if event.event_type == DeviceLifecycleEventType.CREATED and event.device_addresses:
            _LOGGER.info("Devices created: %s", event.device_addresses)
            self.got_devices = True

    def _on_datapoints_created(self, *, event: DataPointsCreatedEvent) -> None:
        """Handle data points created events."""
        total = sum(len(dps) for dps in event.new_data_points.values())
        if total > 0:
            _LOGGER.info("Data points created: %d", total)
            self.got_devices = True

    async def example_run(self):
        """Process the example."""
        central_name = "ccu-dev"
        interface_configs = {
            InterfaceConfig(
                central_name=central_name,
                interface=const.Interface.HMIP_RF,
                port=2010,
            ),
            InterfaceConfig(
                central_name=central_name,
                interface=const.Interface.BIDCOS_RF,
                port=2001,
            ),
            InterfaceConfig(
                central_name=central_name,
                interface=const.Interface.VIRTUAL_DEVICES,
                port=9292,
                remote_path="/groups",
            ),
        }
        self.central = CentralConfig(
            name=central_name,
            host=CCU_HOST,
            username=CCU_USERNAME,
            password=CCU_PASSWORD,
            central_id="1234",
            storage_directory="aiohomematic_storage",
            interface_configs=interface_configs,
            callback_port_xml_rpc=54323,
            optional_settings=(const.OptionalSettings.ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY,),
        ).create_central()

        # For testing we set a short INIT_TIMEOUT
        const.INIT_TIMEOUT = 10
        # Subscribe to device lifecycle events
        self.central.event_bus.subscribe(
            event_type=DeviceLifecycleEvent,
            event_key=None,
            handler=self._on_device_lifecycle,
        )
        # Subscribe to data points created events
        self.central.event_bus.subscribe(
            event_type=DataPointsCreatedEvent,
            event_key=None,
            handler=self._on_datapoints_created,
        )

        await self.central.start()
        while not self.got_devices and self.SLEEPCOUNTER < 20:
            _LOGGER.info("Waiting for devices")
            self.SLEEPCOUNTER += 1
            await asyncio.sleep(1)
        await asyncio.sleep(5)

        for i in range(16):
            _LOGGER.info("Sleeping (%i)", i)
            await asyncio.sleep(2)
        # Stop the central_1 thread so Python can exit properly.
        await self.central.stop()


example = Example()
asyncio.run(example.example_run())
sys.exit(0)
