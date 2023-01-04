"""Helpers for tests."""
from __future__ import annotations

import asyncio

from aiohttp import ClientSession
import const

from hahomematic.central_unit import CentralConfig, CentralUnit
from hahomematic.client import InterfaceConfig, LocalRessources


class CentralUnitLocalFactory:
    def __init__(self, client_session: ClientSession):
        self._client_session = client_session

    async def get_central(
        self, address_device_translation: dict[str, str]
    ) -> CentralUnit:
        """Returns a central based on give address_device_translation."""
        interface_configs = {
            InterfaceConfig(
                central_name=const.CENTRAL_NAME,
                interface="Local",
                port=2002,
                local_resources=LocalRessources(
                    address_device_translation=address_device_translation
                ),
            )
        }

        central_unit = await CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            storage_folder="homematicip_local",
            interface_configs=interface_configs,
            default_callback_port=54321,
            client_session=self._client_session,
        ).get_central()
        await central_unit.start()

        return central_unit
