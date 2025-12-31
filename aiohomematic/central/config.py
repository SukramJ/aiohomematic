# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Configuration classes for CentralUnit initialization.

This module provides CentralConfig for configuring and creating CentralUnit instances.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from typing import TYPE_CHECKING, Any, Final

from aiohttp import ClientSession

from aiohomematic import client as hmcl, i18n
from aiohomematic.client import AioJsonRpcAioHttpClient
from aiohomematic.const import (
    DEFAULT_DELAY_NEW_DEVICE_CREATION,
    DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
    DEFAULT_ENABLE_PROGRAM_SCAN,
    DEFAULT_ENABLE_SYSVAR_SCAN,
    DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS,
    DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH,
    DEFAULT_LOCALE,
    DEFAULT_MAX_READ_WORKERS,
    DEFAULT_OPTIONAL_SETTINGS,
    DEFAULT_PROGRAM_MARKERS,
    DEFAULT_SCHEDULE_TIMER_CONFIG,
    DEFAULT_SESSION_RECORDER_START_FOR_SECONDS,
    DEFAULT_STORAGE_DIRECTORY,
    DEFAULT_SYSVAR_MARKERS,
    DEFAULT_TIMEOUT_CONFIG,
    DEFAULT_TLS,
    DEFAULT_UN_IGNORES,
    DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE,
    DEFAULT_VERIFY_TLS,
    IDENTIFIER_SEPARATOR,
    PORT_ANY,
    PRIMARY_CLIENT_CANDIDATE_INTERFACES,
    DescriptionMarker,
    Interface,
    OptionalSettings,
    RpcServerType,
    ScheduleTimerConfig,
    TimeoutConfig,
    get_interface_default_port,
    get_json_rpc_default_port,
)
from aiohomematic.exceptions import AioHomematicConfigException, AioHomematicException, BaseHomematicException
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.support import (
    check_or_create_directory,
    check_password,
    extract_exc_args,
    is_host,
    is_ipv4_address,
    is_port,
)

if TYPE_CHECKING:
    from aiohomematic.central.central_unit import CentralUnit
    from aiohomematic.store import StorageFactoryProtocol


class CentralConfig:
    """Configuration for CentralUnit initialization and behavior."""

    def __init__(
        self,
        *,
        central_id: str,
        host: str,
        interface_configs: AbstractSet[hmcl.InterfaceConfig],
        name: str,
        password: str,
        username: str,
        client_session: ClientSession | None = None,
        callback_host: str | None = None,
        callback_port_xml_rpc: int | None = None,
        default_callback_port_xml_rpc: int = PORT_ANY,
        delay_new_device_creation: bool = DEFAULT_DELAY_NEW_DEVICE_CREATION,
        enable_device_firmware_check: bool = DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK,
        enable_program_scan: bool = DEFAULT_ENABLE_PROGRAM_SCAN,
        enable_sysvar_scan: bool = DEFAULT_ENABLE_SYSVAR_SCAN,
        ignore_custom_device_definition_models: frozenset[str] = DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS,
        interfaces_requiring_periodic_refresh: frozenset[Interface] = DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH,
        json_port: int | None = None,
        listen_ip_addr: str | None = None,
        listen_port_xml_rpc: int | None = None,
        max_read_workers: int = DEFAULT_MAX_READ_WORKERS,
        optional_settings: tuple[OptionalSettings | str, ...] = DEFAULT_OPTIONAL_SETTINGS,
        program_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_PROGRAM_MARKERS,
        schedule_timer_config: ScheduleTimerConfig = DEFAULT_SCHEDULE_TIMER_CONFIG,
        start_direct: bool = False,
        storage_directory: str = DEFAULT_STORAGE_DIRECTORY,
        storage_factory: StorageFactoryProtocol | None = None,
        sysvar_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_SYSVAR_MARKERS,
        timeout_config: TimeoutConfig = DEFAULT_TIMEOUT_CONFIG,
        tls: bool = DEFAULT_TLS,
        un_ignore_list: frozenset[str] = DEFAULT_UN_IGNORES,
        use_group_channel_for_cover_state: bool = DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
        locale: str = DEFAULT_LOCALE,
    ) -> None:
        """Initialize the central configuration."""
        self._interface_configs: Final = interface_configs
        self._optional_settings: Final = frozenset(optional_settings or ())
        self.requires_xml_rpc_server: Final = any(
            ic for ic in interface_configs if ic.rpc_server == RpcServerType.XML_RPC
        )
        self.callback_host: Final = callback_host
        self.callback_port_xml_rpc: Final = callback_port_xml_rpc
        self.central_id: Final = central_id
        self.client_session: Final = client_session
        self.default_callback_port_xml_rpc: Final = default_callback_port_xml_rpc
        self.delay_new_device_creation: Final = delay_new_device_creation
        self.enable_device_firmware_check: Final = enable_device_firmware_check
        self.enable_program_scan: Final = enable_program_scan
        self.enable_sysvar_scan: Final = enable_sysvar_scan
        self.host: Final = host
        self.ignore_custom_device_definition_models: Final = frozenset(ignore_custom_device_definition_models or ())
        self.interfaces_requiring_periodic_refresh: Final = frozenset(interfaces_requiring_periodic_refresh or ())
        self.json_port: Final = json_port
        self.listen_ip_addr: Final = listen_ip_addr
        self.listen_port_xml_rpc: Final = listen_port_xml_rpc
        self.max_read_workers = max_read_workers
        self.name: Final = name
        self.password: Final = password
        self.program_markers: Final = program_markers
        self.start_direct: Final = start_direct
        self.session_recorder_randomize_output = (
            OptionalSettings.SR_DISABLE_RANDOMIZE_OUTPUT not in self._optional_settings
        )
        self.session_recorder_start_for_seconds: Final = (
            DEFAULT_SESSION_RECORDER_START_FOR_SECONDS
            if OptionalSettings.SR_RECORD_SYSTEM_INIT in self._optional_settings
            else 0
        )
        self.session_recorder_start = self.session_recorder_start_for_seconds > 0
        self.schedule_timer_config: Final = schedule_timer_config
        self.storage_directory: Final = storage_directory
        self.storage_factory: Final = storage_factory
        self.sysvar_markers: Final = sysvar_markers
        self.timeout_config: Final = timeout_config
        self.tls: Final = tls
        self.un_ignore_list: Final = un_ignore_list
        self.use_group_channel_for_cover_state: Final = use_group_channel_for_cover_state
        self.username: Final = username
        self.verify_tls: Final = verify_tls
        self.locale: Final = locale

    @classmethod
    def for_ccu(
        cls,
        *,
        host: str,
        username: str,
        password: str,
        name: str = "ccu",
        central_id: str | None = None,
        tls: bool = False,
        enable_hmip: bool = True,
        enable_bidcos_rf: bool = True,
        enable_bidcos_wired: bool = False,
        enable_virtual_devices: bool = False,
        **kwargs: Any,
    ) -> CentralConfig:
        """
        Create a CentralConfig preset for CCU3/CCU2 backends.

        This factory method simplifies configuration for CCU backends by
        automatically setting up common interfaces with their default ports.

        Args:
            host: Hostname or IP address of the CCU.
            username: CCU username for authentication.
            password: CCU password for authentication.
            name: Name identifier for the central unit.
            central_id: Unique identifier for the central. Auto-generated if not provided.
            tls: Enable TLS encryption for connections.
            enable_hmip: Enable HomematicIP wireless interface (port 2010/42010).
            enable_bidcos_rf: Enable BidCos RF interface (port 2001/42001).
            enable_bidcos_wired: Enable BidCos wired interface (port 2000/42000).
            enable_virtual_devices: Enable virtual devices interface (port 9292/49292).
            **kwargs: Additional arguments passed to CentralConfig constructor.

        Returns:
            Configured CentralConfig instance ready for create_central().

        Example:
            config = CentralConfig.for_ccu(
                host="192.168.1.100",
                username="Admin",
                password="secret",
            )
            central = config.create_central()

        """
        interface_configs: set[hmcl.InterfaceConfig] = set()

        if enable_hmip and (port := get_interface_default_port(interface=Interface.HMIP_RF, tls=tls)):
            interface_configs.add(
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.HMIP_RF,
                    port=port,
                )
            )

        if enable_bidcos_rf and (port := get_interface_default_port(interface=Interface.BIDCOS_RF, tls=tls)):
            interface_configs.add(
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.BIDCOS_RF,
                    port=port,
                )
            )

        if enable_bidcos_wired and (port := get_interface_default_port(interface=Interface.BIDCOS_WIRED, tls=tls)):
            interface_configs.add(
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.BIDCOS_WIRED,
                    port=port,
                )
            )

        if enable_virtual_devices and (
            port := get_interface_default_port(interface=Interface.VIRTUAL_DEVICES, tls=tls)
        ):
            interface_configs.add(
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.VIRTUAL_DEVICES,
                    port=port,
                    remote_path="/groups",
                )
            )

        return cls(
            central_id=central_id or f"{name}-{host}",
            host=host,
            username=username,
            password=password,
            name=name,
            interface_configs=interface_configs,
            json_port=get_json_rpc_default_port(tls=tls),
            tls=tls,
            **kwargs,
        )

    @classmethod
    def for_homegear(
        cls,
        *,
        host: str,
        username: str,
        password: str,
        name: str = "homegear",
        central_id: str | None = None,
        tls: bool = False,
        port: int | None = None,
        **kwargs: Any,
    ) -> CentralConfig:
        """
        Create a CentralConfig preset for Homegear backends.

        This factory method simplifies configuration for Homegear backends
        with the BidCos-RF interface.

        Args:
            host: Hostname or IP address of the Homegear server.
            username: Homegear username for authentication.
            password: Homegear password for authentication.
            name: Name identifier for the central unit.
            central_id: Unique identifier for the central. Auto-generated if not provided.
            tls: Enable TLS encryption for connections.
            port: Custom port for BidCos-RF interface. Uses default (2001/42001) if not set.
            **kwargs: Additional arguments passed to CentralConfig constructor.

        Returns:
            Configured CentralConfig instance ready for create_central().

        Example:
            config = CentralConfig.for_homegear(
                host="192.168.1.50",
                username="homegear",
                password="secret",
            )
            central = config.create_central()

        """
        interface_port = port or get_interface_default_port(interface=Interface.BIDCOS_RF, tls=tls) or 2001

        interface_configs: set[hmcl.InterfaceConfig] = {
            hmcl.InterfaceConfig(
                central_name=name,
                interface=Interface.BIDCOS_RF,
                port=interface_port,
            )
        }

        return cls(
            central_id=central_id or f"{name}-{host}",
            host=host,
            username=username,
            password=password,
            name=name,
            interface_configs=interface_configs,
            tls=tls,
            **kwargs,
        )

    optional_settings: Final = DelegatedProperty[frozenset[OptionalSettings | str]](path="_optional_settings")

    @property
    def connection_check_port(self) -> int:
        """Return the connection check port."""
        if used_ports := tuple(ic.port for ic in self._interface_configs if ic.port is not None):
            return used_ports[0]
        if self.json_port:
            return self.json_port
        return 443 if self.tls else 80

    @property
    def enable_xml_rpc_server(self) -> bool:
        """Return if server and connection checker should be started."""
        return self.requires_xml_rpc_server and self.start_direct is False

    @property
    def enabled_interface_configs(self) -> frozenset[hmcl.InterfaceConfig]:
        """Return the interface configs."""
        return frozenset(ic for ic in self._interface_configs if ic.enabled is True)

    @property
    def load_un_ignore(self) -> bool:
        """Return if un_ignore should be loaded."""
        return self.start_direct is False

    @property
    def use_caches(self) -> bool:
        """Return if store should be used."""
        return self.start_direct is False

    def check_config(self) -> None:
        """Check config. Throws BaseHomematicException on failure."""
        if config_failures := check_config(
            central_name=self.name,
            host=self.host,
            username=self.username,
            password=self.password,
            storage_directory=self.storage_directory,
            callback_host=self.callback_host,
            callback_port_xml_rpc=self.callback_port_xml_rpc,
            json_port=self.json_port,
            interface_configs=self._interface_configs,
        ):
            failures = ", ".join(config_failures)
            # Localized exception message
            msg = i18n.tr(key="exception.config.invalid", failures=failures)
            raise AioHomematicConfigException(msg)

    def create_central(self) -> CentralUnit:
        """Create the central. Throws BaseHomematicException on validation failure."""
        # Import here to avoid circular imports
        from aiohomematic.central.central_unit import CentralUnit  # noqa: PLC0415

        try:
            self.check_config()
            return CentralUnit(central_config=self)
        except BaseHomematicException as bhexc:  # pragma: no cover
            raise AioHomematicException(
                i18n.tr(
                    key="exception.create_central.failed",
                    reason=extract_exc_args(exc=bhexc),
                )
            ) from bhexc

    def create_central_url(self) -> str:
        """Return the required url."""
        url = "https://" if self.tls else "http://"
        url = f"{url}{self.host}"
        if self.json_port:
            url = f"{url}:{self.json_port}"
        return f"{url}"

    def create_json_rpc_client(
        self,
        *,
        central: CentralUnit,
        interface_id: str | None = None,
    ) -> AioJsonRpcAioHttpClient:
        """Create a json rpc client."""
        return AioJsonRpcAioHttpClient(
            username=self.username,
            password=self.password,
            device_url=central.url,
            connection_state=central.connection_state,
            interface_id=interface_id,
            client_session=self.client_session,
            tls=self.tls,
            verify_tls=self.verify_tls,
            session_recorder=central.cache_coordinator.recorder,
            event_bus=central.event_bus,
        )


def check_config(
    *,
    central_name: str,
    host: str,
    username: str,
    password: str,
    storage_directory: str,
    callback_host: str | None,
    callback_port_xml_rpc: int | None,
    json_port: int | None,
    interface_configs: AbstractSet[hmcl.InterfaceConfig] | None = None,
) -> list[str]:
    """Check config. Throws BaseHomematicException on failure."""
    config_failures: list[str] = []
    if central_name and IDENTIFIER_SEPARATOR in central_name:
        config_failures.append(i18n.tr(key="exception.config.check.instance_name.separator", sep=IDENTIFIER_SEPARATOR))

    if not (is_host(host=host) or is_ipv4_address(address=host)):
        config_failures.append(i18n.tr(key="exception.config.check.host.invalid"))
    if not username:
        config_failures.append(i18n.tr(key="exception.config.check.username.empty"))
    if not password:
        config_failures.append(i18n.tr(key="exception.config.check.password.required"))
    if not check_password(password=password):
        config_failures.append(i18n.tr(key="exception.config.check.password.invalid"))
    try:
        check_or_create_directory(directory=storage_directory)
    except BaseHomematicException as bhexc:
        config_failures.append(extract_exc_args(exc=bhexc)[0])
    if callback_host and not (is_host(host=callback_host) or is_ipv4_address(address=callback_host)):
        config_failures.append(i18n.tr(key="exception.config.check.callback_host.invalid"))
    if callback_port_xml_rpc and not is_port(port=callback_port_xml_rpc):
        config_failures.append(i18n.tr(key="exception.config.check.callback_port_xml_rpc.invalid"))
    if json_port and not is_port(port=json_port):
        config_failures.append(i18n.tr(key="exception.config.check.json_port.invalid"))
    if interface_configs and not _has_primary_client(interface_configs=interface_configs):
        config_failures.append(
            i18n.tr(
                key="exception.config.check.primary_interface.missing",
                interfaces=", ".join(PRIMARY_CLIENT_CANDIDATE_INTERFACES),
            )
        )

    return config_failures


def _has_primary_client(*, interface_configs: AbstractSet[hmcl.InterfaceConfig]) -> bool:
    """Check if all configured clients exists in central."""
    for interface_config in interface_configs:
        if interface_config.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES:
            return True
    return False
