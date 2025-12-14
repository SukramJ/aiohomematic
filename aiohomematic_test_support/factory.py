"""
Test factories for creating CentralUnit and Client instances.

This module provides factory classes that simplify the creation of test instances
with pre-configured mocks and session playback. Factories handle the complexity of
setting up CentralConfig, InterfaceConfig, and mock RPC clients.

Key Classes
-----------
- **FactoryWithClient**: Factory for creating a CentralUnit with a single mocked client.
- **CentralClientFactory**: Factory for creating central with multiple clients.

Usage Pattern
-------------
Factories use the builder pattern with fluent configuration:

    factory = FactoryWithClient(
        player=session_player,
        do_mock_client=True,
        ignore_devices_on_create=["VCU0000099"],
    )
    central, client = await factory()

    # Use central and client for testing
    await central.start()
    # ... test operations ...
    await central.stop()

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable
import contextlib
import logging
from typing import Self, cast
from unittest.mock import MagicMock, Mock, patch

from aiohttp import ClientSession

from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.central.integration_events import (
    DataPointsCreatedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
    SystemStatusEvent,
)
from aiohomematic.client import ClientConfig, InterfaceConfig
from aiohomematic.const import LOCAL_HOST, Interface, OptionalSettings
from aiohomematic.interfaces.client import ClientProtocol
from aiohomematic_test_support import const
from aiohomematic_test_support.mock import SessionPlayer, get_client_session, get_mock, get_xml_rpc_proxy

_LOGGER = logging.getLogger(__name__)


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
        self._event_bus_unsubscribe_callbacks: list[Callable[[], None]] = []

    def cleanup_event_bus_subscriptions(self) -> None:
        """Clean up all event bus subscriptions."""
        for unsubscribe in self._event_bus_unsubscribe_callbacks:
            unsubscribe()
        self._event_bus_unsubscribe_callbacks.clear()

    async def get_default_central(self, *, start: bool = True) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        central = await self.get_raw_central()

        await self._xml_proxy.do_init()
        patch("aiohomematic.client.ClientConfig._create_xml_rpc_proxy", return_value=self._xml_proxy).start()
        patch("aiohomematic.central.CentralUnit._identify_ip_addr", return_value=LOCAL_HOST).start()

        # Optionally patch client creation to return a mocked client
        if self._do_mock_client:
            _orig_create_client = ClientConfig.create_client

            async def _mocked_create_client(config: ClientConfig) -> ClientProtocol | Mock:
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
            await central.hub_coordinator.init_hub()
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

        # Subscribe to events via event bus
        def _device_lifecycle_event_handler(event: DeviceLifecycleEvent) -> None:
            """Handle device lifecycle events."""
            self.system_event_mock(event)

        def _data_points_created_event_handler(event: DataPointsCreatedEvent) -> None:
            """Handle data points created events."""
            self.system_event_mock(event)

        def _device_trigger_event_handler(event: DeviceTriggerEvent) -> None:
            """Handle device trigger events."""
            self.ha_event_mock(event)

        def _system_status_event_handler(event: SystemStatusEvent) -> None:
            """Handle system status events (issues, state changes)."""
            self.ha_event_mock(event)

        self._event_bus_unsubscribe_callbacks.append(
            central.event_bus.subscribe(
                event_type=DeviceLifecycleEvent, event_key=None, handler=_device_lifecycle_event_handler
            )
        )
        self._event_bus_unsubscribe_callbacks.append(
            central.event_bus.subscribe(
                event_type=DataPointsCreatedEvent, event_key=None, handler=_data_points_created_event_handler
            )
        )
        self._event_bus_unsubscribe_callbacks.append(
            central.event_bus.subscribe(
                event_type=DeviceTriggerEvent, event_key=None, handler=_device_trigger_event_handler
            )
        )
        self._event_bus_unsubscribe_callbacks.append(
            central.event_bus.subscribe(
                event_type=SystemStatusEvent, event_key=None, handler=_system_status_event_handler
            )
        )

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
) -> AsyncGenerator[tuple[CentralUnit, ClientProtocol | Mock, FactoryWithClient]]:
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
    client = central.client_coordinator.primary_client
    assert client
    try:
        yield central, client, factory
    finally:
        factory.cleanup_event_bus_subscriptions()
        await central.stop()
        await central.cache_coordinator.clear_all()


async def get_pydev_ccu_central_unit_full(
    *,
    port: int,
    client_session: ClientSession | None = None,
) -> CentralUnit:
    """Create and yield central, after all devices have been created."""
    device_event = asyncio.Event()

    def device_lifecycle_event_handler(event: DeviceLifecycleEvent) -> None:
        """Handle device lifecycle events."""
        if event.event_type == DeviceLifecycleEventType.CREATED:
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
    central.event_bus.subscribe(event_type=DeviceLifecycleEvent, event_key=None, handler=device_lifecycle_event_handler)
    await central.start()

    # Wait up to 60 seconds for the DEVICES_CREATED event which signals that all devices are available
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(device_event.wait(), timeout=60)

    return central
