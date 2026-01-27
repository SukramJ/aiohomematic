# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Configuration classes for CentralUnit initialization.

This module provides CentralConfig for configuring and creating CentralUnit instances.
"""

from __future__ import annotations

# Pydantic validators require a fixed signature that cannot use keyword-only args
__kwonly_check__ = False

import asyncio
from collections.abc import Set as AbstractSet
from typing import Any

from aiohttp import ClientSession
from pydantic import BaseModel, ConfigDict, PrivateAttr, SkipValidation, model_validator

from aiohomematic import client as hmcl, i18n
from aiohomematic.central.central_unit import CentralUnit
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
from aiohomematic.store import StorageFactoryProtocol
from aiohomematic.support import (
    _check_or_create_directory_sync,
    check_password,
    extract_exc_args,
    is_host,
    is_ipv4_address,
    is_port,
)


class CentralConfig(BaseModel):
    """Configuration for CentralUnit initialization and behavior."""

    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True, extra="allow")

    # Required fields
    central_id: str
    """Unique identifier for the central unit."""

    host: str
    """Hostname or IP address of the CCU/Homegear."""

    interface_configs: frozenset[hmcl.InterfaceConfig]
    """Set of interface configurations."""

    name: str
    """Name identifier for the central unit."""

    password: str
    """Password for authentication."""

    username: str
    """Username for authentication."""

    # Optional fields with defaults
    client_session: SkipValidation[ClientSession | None] = None
    """Optional aiohttp client session to use."""

    callback_host: str | None = None
    """Hostname/IP for XML-RPC callback server."""

    callback_port_xml_rpc: int | None = None
    """Port for XML-RPC callback server."""

    default_callback_port_xml_rpc: int = PORT_ANY
    """Default port for XML-RPC callback if not specified."""

    delay_new_device_creation: bool = DEFAULT_DELAY_NEW_DEVICE_CREATION
    """Delay creation of new devices."""

    enable_device_firmware_check: bool = DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK
    """Enable periodic device firmware checks."""

    enable_program_scan: bool = DEFAULT_ENABLE_PROGRAM_SCAN
    """Enable scanning of CCU programs."""

    enable_sysvar_scan: bool = DEFAULT_ENABLE_SYSVAR_SCAN
    """Enable scanning of CCU system variables."""

    ignore_custom_device_definition_models: frozenset[str] = DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS
    """Device models to ignore for custom definitions."""

    interfaces_requiring_periodic_refresh: frozenset[Interface] = DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH
    """Interfaces that need periodic refresh instead of push updates."""

    json_port: int | None = None
    """Port for JSON-RPC communication."""

    listen_ip_addr: str | None = None
    """IP address to listen on for callback server."""

    listen_port_xml_rpc: int | None = None
    """Port to listen on for XML-RPC callback server."""

    max_read_workers: int = DEFAULT_MAX_READ_WORKERS
    """Maximum number of concurrent read workers."""

    optional_settings: frozenset[OptionalSettings | str] = frozenset(DEFAULT_OPTIONAL_SETTINGS)
    """Optional feature flags."""

    program_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_PROGRAM_MARKERS
    """Markers to filter programs."""

    schedule_timer_config: ScheduleTimerConfig = DEFAULT_SCHEDULE_TIMER_CONFIG
    """Timer configuration for scheduled tasks."""

    start_direct: bool = False
    """Start without XML-RPC server (direct mode)."""

    storage_directory: str = DEFAULT_STORAGE_DIRECTORY
    """Directory for persistent storage."""

    storage_factory: SkipValidation[StorageFactoryProtocol | None] = None
    """Optional storage factory for custom storage implementations."""

    sysvar_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_SYSVAR_MARKERS
    """Markers to filter system variables."""

    timeout_config: TimeoutConfig = DEFAULT_TIMEOUT_CONFIG
    """Timeout configuration for various operations."""

    tls: bool = DEFAULT_TLS
    """Enable TLS encryption."""

    un_ignore_list: frozenset[str] = DEFAULT_UN_IGNORES
    """List of parameters to un-ignore."""

    use_group_channel_for_cover_state: bool = DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE
    """Use group channel for cover state."""

    verify_tls: bool = DEFAULT_VERIFY_TLS
    """Verify TLS certificates."""

    locale: str = DEFAULT_LOCALE
    """Locale for translations."""

    # Private attributes for computed values
    _requires_xml_rpc_server: bool = PrivateAttr(default=False)
    _session_recorder_randomize_output: bool = PrivateAttr(default=True)
    _session_recorder_start_for_seconds: int = PrivateAttr(default=0)
    _session_recorder_start: bool = PrivateAttr(default=False)

    @model_validator(mode="before")
    @classmethod
    def _normalize_collections(cls, data: Any) -> Any:
        """Normalize collection types before validation."""
        if isinstance(data, dict):
            # Convert interface_configs to frozenset if it's a set or other iterable
            if "interface_configs" in data and not isinstance(data["interface_configs"], frozenset):
                data["interface_configs"] = frozenset(data["interface_configs"])
            # Convert optional_settings tuple to frozenset
            if "optional_settings" in data:
                val = data["optional_settings"]
                if isinstance(val, tuple):
                    data["optional_settings"] = frozenset(val)
                elif val is None:
                    data["optional_settings"] = frozenset()
            # Convert ignore_custom_device_definition_models
            if (
                "ignore_custom_device_definition_models" in data
                and data["ignore_custom_device_definition_models"] is None
            ):
                data["ignore_custom_device_definition_models"] = frozenset()
            # Convert interfaces_requiring_periodic_refresh
            if (
                "interfaces_requiring_periodic_refresh" in data
                and data["interfaces_requiring_periodic_refresh"] is None
            ):
                data["interfaces_requiring_periodic_refresh"] = frozenset()
        return data

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
            central = await config.create_central()

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
            interface_configs=frozenset(interface_configs),
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
            central = await config.create_central()

        """
        interface_port = port or get_interface_default_port(interface=Interface.BIDCOS_RF, tls=tls) or 2001

        interface_configs: frozenset[hmcl.InterfaceConfig] = frozenset(
            {
                hmcl.InterfaceConfig(
                    central_name=name,
                    interface=Interface.BIDCOS_RF,
                    port=interface_port,
                )
            }
        )

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

    @property
    def connection_check_port(self) -> int:
        """Return the connection check port."""
        if used_ports := tuple(ic.port for ic in self.interface_configs if ic.port is not None):
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
        return frozenset(ic for ic in self.interface_configs if ic.enabled is True)

    @property
    def load_un_ignore(self) -> bool:
        """Return if un_ignore should be loaded."""
        return self.start_direct is False

    @property
    def requires_xml_rpc_server(self) -> bool:
        """Return if XML-RPC server is required."""
        return self._requires_xml_rpc_server

    @property
    def session_recorder_randomize_output(self) -> bool:
        """Return if session recorder should randomize output."""
        return self._session_recorder_randomize_output

    @session_recorder_randomize_output.setter
    def session_recorder_randomize_output(self, value: bool) -> None:
        """Set session recorder randomize output."""
        self._session_recorder_randomize_output = value

    @property
    def session_recorder_start(self) -> bool:
        """Return if session recorder should start."""
        return self._session_recorder_start

    @session_recorder_start.setter
    def session_recorder_start(self, value: bool) -> None:
        """Set session recorder start flag."""
        self._session_recorder_start = value

    @property
    def session_recorder_start_for_seconds(self) -> int:
        """Return session recorder start duration in seconds."""
        return self._session_recorder_start_for_seconds

    @property
    def use_caches(self) -> bool:
        """Return if store should be used."""
        return self.start_direct is False

    async def check_config(self) -> None:
        """Check central config asynchronously."""
        if config_failures := await check_config(
            central_name=self.name,
            host=self.host,
            username=self.username,
            password=self.password,
            storage_directory=self.storage_directory,
            callback_host=self.callback_host,
            callback_port_xml_rpc=self.callback_port_xml_rpc,
            json_port=self.json_port,
            interface_configs=self.interface_configs,
        ):
            failures = ", ".join(config_failures)
            msg = i18n.tr(key="exception.config.invalid", failures=failures)
            raise AioHomematicConfigException(msg)

    async def create_central(self) -> CentralUnit:
        """Create the central asynchronously."""
        try:
            await self.check_config()
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

    def model_post_init(self, _context: Any, /) -> None:
        """Initialize computed private attributes after model creation."""
        self._requires_xml_rpc_server = any(
            ic for ic in self.interface_configs if ic.rpc_server == RpcServerType.XML_RPC
        )
        self._session_recorder_randomize_output = (
            OptionalSettings.SR_DISABLE_RANDOMIZE_OUTPUT not in self.optional_settings
        )
        self._session_recorder_start_for_seconds = (
            DEFAULT_SESSION_RECORDER_START_FOR_SECONDS
            if OptionalSettings.SR_RECORD_SYSTEM_INIT in self.optional_settings
            else 0
        )
        self._session_recorder_start = self._session_recorder_start_for_seconds > 0


def _check_config_sync(
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
    """Check config (internal sync implementation)."""
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
        _check_or_create_directory_sync(directory=storage_directory)
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


async def check_config(
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
    """Check config asynchronously."""
    return await asyncio.to_thread(
        _check_config_sync,
        central_name=central_name,
        host=host,
        username=username,
        password=password,
        storage_directory=storage_directory,
        callback_host=callback_host,
        callback_port_xml_rpc=callback_port_xml_rpc,
        json_port=json_port,
        interface_configs=interface_configs,
    )


def _has_primary_client(*, interface_configs: AbstractSet[hmcl.InterfaceConfig]) -> bool:
    """Check if all configured clients exists in central."""
    for interface_config in interface_configs:
        if interface_config.interface in PRIMARY_CLIENT_CANDIDATE_INTERFACES:
            return True
    return False
