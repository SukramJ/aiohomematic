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

    def _systemcallback(self, event: BackendSystemEventData) -> None:
        """Handle system events from the backend."""
        self.got_devices = True
        if (
            event.system_event == const.BackendSystemEvent.NEW_DEVICES
            and event.data
            and event.data.get("device_descriptions")
            and len(event.data["device_descriptions"]) > 0
        ):
            self.got_devices = True
            return
        if (
            event.system_event == const.BackendSystemEvent.DEVICES_CREATED
            and event.data
            and event.data.get("new_data_points")
            and len(event.data["new_data_points"]) > 0
        ):
            if len(event.data["new_data_points"]) > 1:
                self.got_devices = True
            return

    async def example_run(self):
        """Process the example."""
        central_name = "ccu-dev"
        interface_configs = {
            InterfaceConfig(
                central_name=central_name,
                interface=const.Interface.HMIP_RF,
                port=2010,
            ),
            # InterfaceConfig(
            #     central_name=central_name,
            #     interface=const.Interface.BIDCOS_RF,
            #     port=2001,
            # ),
            # InterfaceConfig(
            #     central_name=central_name,
            #     interface=const.Interface.VIRTUAL_DEVICES,
            #     port=9292,
            #     remote_path="/groups",
            # ),
            InterfaceConfig(
                central_name=central_name,
                interface=const.Interface.CUXD,
                port=8701,
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
        # Subscribe to backend system events via EventBus
        self.central.event_bus.subscribe(
            event_type=BackendSystemEventData,
            handler=self._systemcallback,
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


# validate the device description
if validate_custom_data_point_definition():
    example = Example()
    asyncio.run(example.example_run())
    sys.exit(0)
