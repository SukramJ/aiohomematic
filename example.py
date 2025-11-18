"""Example for aiohomematic."""

# !/usr/bin/python3
from __future__ import annotations

import asyncio
import logging
import sys

from aiohomematic import const
from aiohomematic.central import CentralConfig
from aiohomematic.central.event_bus import BackendSystemEventData
from aiohomematic.client import InterfaceConfig
from aiohomematic.model.custom import validate_custom_data_point_definition

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)

CCU_HOST = "192.168.1.173"
CCU_USERNAME = "Admin"
CCU_PASSWORD = ""


class Example:
    """Example for aiohomematic."""

    # Create a server that listens on LOCAL_HOST:* and identifies itself as myserver.
    got_devices = False

    def __init__(self):
        """Init example."""
        self.SLEEPCOUNTER = 0
        self.central = None

    def _systemcallback(self, event: BackendSystemEventData) -> None:
        """Handle backend system events."""
        if event.system_event == const.BackendSystemEvent.DEVICES_CREATED:
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
            interface_configs=interface_configs,
        ).create_central()

        # For testing we set a short INIT_TIMEOUT
        const.INIT_TIMEOUT = 10
        # Add callbacks to handle the events and see what happens on the system.
        self.central.event_bus.subscribe(event_type=BackendSystemEventData, handler=self._systemcallback)

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


# validate the device description
if validate_custom_data_point_definition():
    example = Example()
    asyncio.run(example.example_run())
    sys.exit(0)
