"""Helpers for tests."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.resources
import logging
import os
from typing import Any, Final
from unittest.mock import MagicMock, Mock, patch

from aiohttp import ClientSession
import orjson

from aiohomematic import const as aiohomematic_const
from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.client import Client, ClientConfig, InterfaceConfig
from aiohomematic.const import LOCAL_HOST, BackendSystemEvent, Interface, SourceOfDeviceCreation
from aiohomematic.model.custom import CustomDataPoint
from aiohomematic_support.client_local import ClientLocal, LocalRessources

from tests import const

_LOGGER = logging.getLogger(__name__)

EXCLUDE_METHODS_FROM_MOCKS: Final = []
INCLUDE_PROPERTIES_IN_MOCKS: Final = []
GOT_DEVICES = False


# pylint: disable=protected-access
class FactoryWithLocalClient:
    """Factory for a central with one local client."""

    def __init__(self, *, client_session: ClientSession | None = None):
        """Init the central factory."""
        self._client_session = client_session
        self.system_event_mock = MagicMock()
        self.ha_event_mock = MagicMock()

    async def get_raw_central(
        self,
        *,
        interface_config: InterfaceConfig | None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        interface_configs = {interface_config} if interface_config else set()
        central = CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            interface_configs=interface_configs,
            client_session=self._client_session,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
            start_direct=True,
        ).create_central()

        central.register_backend_system_callback(cb=self.system_event_mock)
        central.register_homematic_callback(cb=self.ha_event_mock)

        return central

    async def get_unpatched_default_central(
        self,
        *,
        port: int,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        interface_config = InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface=aiohomematic_const.Interface.BIDCOS_RF,
            port=port,
        )

        central = await self.get_raw_central(
            interface_config=interface_config,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        )

        _client = ClientLocal(
            client_config=ClientConfig(
                central=central,
                interface_config=interface_config,
            ),
            local_resources=LocalRessources(
                address_device_translation=address_device_translation,
                ignore_devices_on_create=ignore_devices_on_create if ignore_devices_on_create else [],
            ),
        )
        await _client.init_client()
        client = get_mock(_client) if do_mock_client else _client

        assert central
        assert client
        return central, client

    async def get_default_central(
        self,
        *,
        port: int = const.CCU_MINI_PORT,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        add_sysvars: bool = False,
        add_programs: bool = False,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        central, client = await self.get_unpatched_default_central(
            port=port,
            address_device_translation=address_device_translation,
            do_mock_client=True,
            ignore_devices_on_create=ignore_devices_on_create,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        )

        patch("aiohomematic.central.CentralUnit._get_primary_client", return_value=client).start()
        patch("aiohomematic.client.ClientConfig.create_client", return_value=client).start()
        patch(
            "aiohomematic_support.client_local.ClientLocal.get_all_system_variables",
            return_value=const.SYSVAR_DATA if add_sysvars else [],
        ).start()
        patch(
            "aiohomematic_support.client_local.ClientLocal.get_all_programs",
            return_value=const.PROGRAM_DATA if add_programs else [],
        ).start()
        patch("aiohomematic.central.CentralUnit._identify_ip_addr", return_value=LOCAL_HOST).start()

        await central.start()
        if new_device_addresses := central._check_for_new_device_addresses():
            await central._create_devices(new_device_addresses=new_device_addresses, source=SourceOfDeviceCreation.INIT)
        await central._init_hub()

        assert central
        assert client
        return central, client


class FactoryWithClientCCU:
    """Factory for a central with one local client."""

    def __init__(self, *, client_session: ClientSession | None = None):
        """Init the central factory."""
        self._client_session = client_session
        self.system_event_mock = MagicMock()
        self.ha_event_mock = MagicMock()

    async def get_raw_central(
        self,
        *,
        interface_config: InterfaceConfig | None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> CentralUnit:
        """Return a central based on give address_device_translation."""
        interface_configs = {interface_config} if interface_config else set()
        central = CentralConfig(
            name=const.CENTRAL_NAME,
            host=const.CCU_HOST,
            username=const.CCU_USERNAME,
            password=const.CCU_PASSWORD,
            central_id="test1234",
            interface_configs=interface_configs,
            client_session=self._client_session,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
            start_direct=True,
        ).create_central()

        central.register_backend_system_callback(cb=self.system_event_mock)
        central.register_homematic_callback(cb=self.ha_event_mock)

        return central

    async def get_unpatched_default_central(
        self,
        *,
        port: int,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        interface_config = InterfaceConfig(
            central_name=const.CENTRAL_NAME,
            interface=aiohomematic_const.Interface.BIDCOS_RF,
            port=port,
        )

        central = await self.get_raw_central(
            interface_config=interface_config,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        )

        _client = ClientLocal(
            client_config=ClientConfig(
                central=central,
                interface_config=interface_config,
            ),
            local_resources=LocalRessources(
                address_device_translation=address_device_translation,
                ignore_devices_on_create=ignore_devices_on_create if ignore_devices_on_create else [],
            ),
        )
        await _client.init_client()
        client = get_mock(_client) if do_mock_client else _client

        assert central
        assert client
        return central, client

    async def get_default_central(
        self,
        *,
        port: int = const.CCU_MINI_PORT,
        address_device_translation: dict[str, str],
        do_mock_client: bool = True,
        add_sysvars: bool = False,
        add_programs: bool = False,
        ignore_devices_on_create: list[str] | None = None,
        un_ignore_list: list[str] | None = None,
        ignore_custom_device_definition_models: list[str] | None = None,
    ) -> tuple[CentralUnit, Client | Mock]:
        """Return a central based on give address_device_translation."""
        central, client = await self.get_unpatched_default_central(
            port=port,
            address_device_translation=address_device_translation,
            do_mock_client=True,
            ignore_devices_on_create=ignore_devices_on_create,
            un_ignore_list=un_ignore_list,
            ignore_custom_device_definition_models=ignore_custom_device_definition_models,
        )

        patch("aiohomematic.central.CentralUnit._get_primary_client", return_value=client).start()
        patch("aiohomematic.client.ClientConfig.create_client", return_value=client).start()
        patch(
            "aiohomematic_support.client_local.ClientLocal.get_all_system_variables",
            return_value=const.SYSVAR_DATA if add_sysvars else [],
        ).start()
        patch(
            "aiohomematic_support.client_local.ClientLocal.get_all_programs",
            return_value=const.PROGRAM_DATA if add_programs else [],
        ).start()
        patch("aiohomematic.central.CentralUnit._identify_ip_addr", return_value=LOCAL_HOST).start()

        await central.start()
        if new_device_addresses := central._check_for_new_device_addresses():
            await central._create_devices(new_device_addresses=new_device_addresses, source=SourceOfDeviceCreation.INIT)
        await central._init_hub()

        assert central
        assert client
        return central, client


def get_prepared_custom_data_point(
    central: CentralUnit, address: str, channel_no: int | None
) -> CustomDataPoint | None:
    """Return the hm custom_data_point."""
    if cdp := central.get_custom_data_point(address=address, channel_no=channel_no):
        for dp in cdp._data_points.values():
            dp._state_uncertain = False
        return cdp
    return None


def load_device_description(central: CentralUnit, file_name: str) -> Any:
    """Load device description."""
    dev_desc = _load_json_file(anchor="pydevccu", resource="device_descriptions", file_name=file_name)
    assert dev_desc
    return dev_desc


def get_mock(instance: Any, **kwargs):
    """Create a mock and copy instance attributes over mock."""
    if isinstance(instance, Mock):
        instance.__dict__.update(instance._mock_wraps.__dict__)
        return instance
    mock = MagicMock(spec=instance, wraps=instance, **kwargs)
    mock.__dict__.update(instance.__dict__)
    try:
        for method_name in [
            prop
            for prop in _get_not_mockable_method_names(instance)
            if prop not in INCLUDE_PROPERTIES_IN_MOCKS and prop not in kwargs
        ]:
            setattr(mock, method_name, getattr(instance, method_name))
    except Exception:
        pass
    finally:
        return mock


def _get_not_mockable_method_names(instance: Any) -> set[str]:
    """Return all relevant method names for mocking."""
    methods: set[str] = set(_get_properties(data_object=instance, decorator=property))

    for method in dir(instance):
        if method in EXCLUDE_METHODS_FROM_MOCKS:
            methods.add(method)
    return methods


def _get_properties(data_object: Any, decorator: Any) -> set[str]:
    """Return the object attributes by decorator."""
    cls = data_object.__class__

    # Resolve function-based decorators to their underlying property class, if provided
    resolved_decorator: Any = decorator
    if not isinstance(decorator, type):
        resolved_decorator = getattr(decorator, "__property_class__", decorator)

    return {y for y in dir(cls) if isinstance(getattr(cls, y), resolved_decorator)}


def _load_json_file(anchor: str, resource: str, file_name: str) -> Any | None:
    """Load json file from disk into dict."""
    package_path = str(importlib.resources.files(anchor))
    with open(
        file=os.path.join(package_path, resource, file_name),
        encoding=aiohomematic_const.UTF_8,
    ) as fptr:
        return orjson.loads(fptr.read())


async def get_pydev_ccu_central_unit_full(
    port: int,
    client_session: ClientSession | None = None,
) -> CentralUnit:
    """Create and yield central, after all devices have been created."""
    device_event = asyncio.Event()

    def systemcallback(system_event, *args, **kwargs):
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
