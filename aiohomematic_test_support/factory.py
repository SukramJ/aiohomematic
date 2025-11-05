"""Factories for tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import contextlib
import logging
from typing import Any, Self, cast
from unittest.mock import MagicMock, Mock, patch

from aiohttp import ClientSession

from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.client import Client, ClientConfig, InterfaceConfig
from aiohomematic.const import LOCAL_HOST, BackendSystemEvent, Interface, OptionalSettings
from aiohomematic_test_support import const
from aiohomematic_test_support.mock import SessionPlayer, get_client_session, get_mock, get_xml_rpc_proxy

_LOGGER = logging.getLogger(__name__)


# pylint: disable=protected-access
class FactoryWithClient:
    """Factory for a central with one local client."""

    def __init__(
        self,
        *,
        player: SessionPlayer,
        address_device_translation: set[str] | None = None,
        do_mock_client: bool = True,
        exclude_methods_from_mocks: set[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
        ignore_devices_on_create: list[str] | None = None,
        include_properties_in_mocks: set[str] | None = None,
        interface_configs: set[InterfaceConfig] | None = None,
        un_ignore_list: list[str] | None = None,
    ) -> None:
        """Init the central factory."""
        self._player = player
        self.init(
            address_device_translation=address_device_translation,
            do_mock_client=do_mock_client,
            exclude_methods_from_mocks=exclude_methods_from_mocks,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
            ignore_devices_on_create=ignore_devices_on_create,
            include_properties_in_mocks=include_properties_in_mocks,
            interface_configs=interface_configs,
            un_ignore_list=un_ignore_list,
        )
        self.system_event_mock = MagicMock()
        self.ha_event_mock = MagicMock()

    async def get_default_central(self, *, start: bool = True) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        central = await self.get_raw_central()

        await self._xml_proxy.do_init()
        patch("aiohomematic.client.ClientConfig._create_xml_rpc_proxy", return_value=self._xml_proxy).start()
        patch("aiohomematic.central.CentralUnit._identify_ip_addr", return_value=LOCAL_HOST).start()

        # Optionally patch client creation to return a mocked client
        if self._do_mock_client:
            _orig_create_client = ClientConfig.create_client

            async def _mocked_create_client(config: ClientConfig) -> Client | Mock:
                real_client = await _orig_create_client(config)
                return cast(
                    Mock,
                    get_mock(
                        instance=real_client,
                        exclude_methods=self._exclude_methods_from_mocks,
                        include_properties=self._include_properties_in_mocks,
                    ),
                )

            patch("aiohomematic.client.ClientConfig.create_client", _mocked_create_client).start()

        if start:
            await central.start()
            await central._init_hub()
        assert central
        return central

    async def get_raw_central(self) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        interface_configs = self._interface_configs if self._interface_configs else set()
        central = CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            interface_configs=interface_configs,
            client_session=self._client_session,
            un_ignore_list=self._un_ignore_list,
            ignore_custom_device_definition_models=frozenset(self._ignore_custom_device_definition_models or []),
            start_direct=True,
            optional_settings=(OptionalSettings.ENABLE_LINKED_ENTITY_CLIMATE_ACTIVITY,),
        ).create_central()

        central.register_backend_system_callback(cb=self.system_event_mock)
        central.register_homematic_callback(cb=self.ha_event_mock)

        assert central
        self._client_session.set_central(central=central)  # type: ignore[attr-defined]
        self._xml_proxy.set_central(central=central)
        return central

    def init(
        self,
        *,
        address_device_translation: set[str] | None = None,
        do_mock_client: bool = True,
        exclude_methods_from_mocks: set[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
        ignore_devices_on_create: list[str] | None = None,
        include_properties_in_mocks: set[str] | None = None,
        interface_configs: set[InterfaceConfig] | None = None,
        un_ignore_list: list[str] | None = None,
    ) -> Self:
        """Init the central factory."""
        self._address_device_translation = address_device_translation
        self._do_mock_client = do_mock_client
        self._exclude_methods_from_mocks = exclude_methods_from_mocks
        self._ignore_custom_device_definition_models = ignore_custom_device_definition_models
        self._ignore_devices_on_create = ignore_devices_on_create
        self._include_properties_in_mocks = include_properties_in_mocks
        self._interface_configs = (
            interface_configs
            if interface_configs is not None
            else {
                InterfaceConfig(
                    central_name=const.CENTRAL_NAME,
                    interface=Interface.BIDCOS_RF,
                    port=2001,
                )
            }
        )
        self._un_ignore_list = frozenset(un_ignore_list or [])
        self._client_session = get_client_session(
            player=self._player,
            address_device_translation=self._address_device_translation,
            ignore_devices_on_create=self._ignore_devices_on_create,
        )
        self._xml_proxy = get_xml_rpc_proxy(
            player=self._player,
            address_device_translation=self._address_device_translation,
            ignore_devices_on_create=self._ignore_devices_on_create,
        )
        return self


async def get_central_client_factory(
    *,
    player: SessionPlayer,
    address_device_translation: set[str],
    do_mock_client: bool,
    ignore_devices_on_create: list[str] | None,
    ignore_custom_device_definition_models: list[str] | None,
    un_ignore_list: list[str] | None,
) -> AsyncGenerator[tuple[CentralUnit, Client | Mock, FactoryWithClient]]:
    """Return central factory."""
    factory = FactoryWithClient(
        player=player,
        address_device_translation=address_device_translation,
        do_mock_client=do_mock_client,
        ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        ignore_devices_on_create=ignore_devices_on_create,
        un_ignore_list=un_ignore_list,
    )
    central = await factory.get_default_central()
    client = central.primary_client
    assert client
    try:
        yield central, client, factory
    finally:
        await central.stop()
        await central.clear_files()


async def get_pydev_ccu_central_unit_full(
    *,
    port: int,
    client_session: ClientSession | None = None,
) -> CentralUnit:
    """Create and yield central, after all devices have been created."""
    device_event = asyncio.Event()

    def systemcallback(system_event: Any, *args: Any, **kwargs: Any) -> None:
        if system_event == BackendSystemEvent.DEVICES_CREATED:
            device_event.set()

    interface_configs = {
        InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface=Interface.BIDCOS_RF,
            port=port,
        )
    }

    central = CentralConfig(
        name=const.CENTRAL_NAME,
        host=const.CCU_HOST,
        username=const.CCU_USERNAME,
        password=const.CCU_PASSWORD,
        central_id="test1234",
        interface_configs=interface_configs,
        client_session=client_session,
        program_markers=(),
        sysvar_markers=(),
    ).create_central()
    central.register_backend_system_callback(cb=systemcallback)
    await central.start()

    # Wait up to 60 seconds for the DEVICES_CREATED event which signals that all devices are available
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(device_event.wait(), timeout=60)

    return central
