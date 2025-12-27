# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Builder pattern for CentralConfig with fluent interface.

This module provides a builder class that offers step-by-step configuration
with method chaining, early validation, and preset configurations.

Example:
    # Simple CCU setup
    config = (
        CentralConfigBuilder()
        .with_name(name="my-ccu")
        .with_host(host="192.168.1.100")
        .with_credentials(username="Admin", password="secret")
        .add_hmip_interface()
        .add_bidcos_rf_interface()
        .build()
    )

    # Using preset
    config = (
        CentralConfigBuilder.for_ccu(host="192.168.1.100")
        .with_credentials(username="Admin", password="secret")
        .with_tls(enabled=True)
        .build()
    )

Public API of this module is defined by __all__.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

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
    DEFAULT_STORAGE_DIRECTORY,
    DEFAULT_SYSVAR_MARKERS,
    DEFAULT_TIMEOUT_CONFIG,
    DEFAULT_TLS,
    DEFAULT_UN_IGNORES,
    DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE,
    DEFAULT_VERIFY_TLS,
    PORT_ANY,
    DescriptionMarker,
    Interface,
    OptionalSettings,
    ScheduleTimerConfig,
    TimeoutConfig,
    get_interface_default_port,
    get_json_rpc_default_port,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from aiohomematic.central import CentralConfig
    from aiohomematic.client import InterfaceConfig

__all__ = ["CentralConfigBuilder", "ValidationError"]


@dataclass(frozen=True, slots=True)
class ValidationError:
    """Validation error with field name and message."""

    field: str
    message: str


class CentralConfigBuilder:
    """
    Builder for CentralConfig with fluent interface.

    Provides step-by-step configuration with method chaining, early validation,
    and preset configurations for common backends.

    The builder enforces that required fields (name, host, username, password)
    are set before building, and provides sensible defaults for all optional fields.

    Example:
        # Full configuration
        config = (
            CentralConfigBuilder()
            .with_name(name="production-ccu")
            .with_host(host="ccu.local")
            .with_credentials(username="admin", password="secret")
            .with_tls(enabled=True, verify=True)
            .add_hmip_interface()
            .add_bidcos_rf_interface()
            .with_storage(directory="/var/lib/aiohomematic")
            .with_programs(enabled=True)
            .with_sysvars(enabled=True)
            .build()
        )

        # Validate before building
        builder = CentralConfigBuilder().with_name(name="test")
        errors = builder.validate()
        if errors:
            for error in errors:
                print(f"{error.field}: {error.message}")

    """

    __slots__ = (
        # Required
        "_name",
        "_host",
        "_username",
        "_password",
        # Interfaces
        "_interfaces",
        # Connection
        "_tls",
        "_verify_tls",
        "_json_port",
        "_client_session",
        # Callback server
        "_callback_host",
        "_callback_port_xml_rpc",
        "_default_callback_port_xml_rpc",
        "_listen_ip_addr",
        "_listen_port_xml_rpc",
        # Features
        "_enable_program_scan",
        "_enable_sysvar_scan",
        "_enable_device_firmware_check",
        "_program_markers",
        "_sysvar_markers",
        # Storage
        "_storage_directory",
        # Advanced
        "_central_id",
        "_delay_new_device_creation",
        "_ignore_custom_device_definition_models",
        "_interfaces_requiring_periodic_refresh",
        "_max_read_workers",
        "_optional_settings",
        "_schedule_timer_config",
        "_start_direct",
        "_timeout_config",
        "_un_ignore_list",
        "_use_group_channel_for_cover_state",
        "_locale",
    )

    def __init__(self) -> None:
        """Initialize builder with default values."""
        # Required (no default)
        self._name: str | None = None
        self._host: str | None = None
        self._username: str | None = None
        self._password: str | None = None

        # Interfaces
        self._interfaces: list[tuple[Interface, int | None, str | None]] = []

        # Connection
        self._tls: bool = DEFAULT_TLS
        self._verify_tls: bool = DEFAULT_VERIFY_TLS
        self._json_port: int | None = None
        self._client_session: ClientSession | None = None

        # Callback server
        self._callback_host: str | None = None
        self._callback_port_xml_rpc: int | None = None
        self._default_callback_port_xml_rpc: int = PORT_ANY
        self._listen_ip_addr: str | None = None
        self._listen_port_xml_rpc: int | None = None

        # Features
        self._enable_program_scan: bool = DEFAULT_ENABLE_PROGRAM_SCAN
        self._enable_sysvar_scan: bool = DEFAULT_ENABLE_SYSVAR_SCAN
        self._enable_device_firmware_check: bool = DEFAULT_ENABLE_DEVICE_FIRMWARE_CHECK
        self._program_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_PROGRAM_MARKERS
        self._sysvar_markers: tuple[DescriptionMarker | str, ...] = DEFAULT_SYSVAR_MARKERS

        # Storage
        self._storage_directory: str = DEFAULT_STORAGE_DIRECTORY

        # Advanced
        self._central_id: str | None = None
        self._delay_new_device_creation: bool = DEFAULT_DELAY_NEW_DEVICE_CREATION
        self._ignore_custom_device_definition_models: frozenset[str] = DEFAULT_IGNORE_CUSTOM_DEVICE_DEFINITION_MODELS
        self._interfaces_requiring_periodic_refresh: frozenset[Interface] = (
            DEFAULT_INTERFACES_REQUIRING_PERIODIC_REFRESH
        )
        self._max_read_workers: int = DEFAULT_MAX_READ_WORKERS
        self._optional_settings: tuple[OptionalSettings | str, ...] = DEFAULT_OPTIONAL_SETTINGS
        self._schedule_timer_config: ScheduleTimerConfig = DEFAULT_SCHEDULE_TIMER_CONFIG
        self._start_direct: bool = False
        self._timeout_config: TimeoutConfig = DEFAULT_TIMEOUT_CONFIG
        self._un_ignore_list: frozenset[str] = DEFAULT_UN_IGNORES
        self._use_group_channel_for_cover_state: bool = DEFAULT_USE_GROUP_CHANNEL_FOR_COVER_STATE
        self._locale: str = DEFAULT_LOCALE

    @classmethod
    def for_ccu(cls, *, host: str, name: str = "ccu") -> Self:
        """
        Create builder preset for CCU3/CCU2 backends.

        Pre-configures standard CCU interfaces (HMIP_RF, BIDCOS_RF).

        Args:
            host: CCU hostname or IP address.
            name: Central unit name (default: "ccu").

        Returns:
            Pre-configured builder. Add credentials and call build().

        Example:
            config = (
                CentralConfigBuilder.for_ccu(host="192.168.1.100")
                .with_credentials(username="Admin", password="secret")
                .build()
            )

        """
        return cls().with_name(name=name).with_host(host=host).add_all_standard_interfaces()

    @classmethod
    def for_homegear(cls, *, host: str, name: str = "homegear", port: int | None = None) -> Self:
        """
        Create builder preset for Homegear backends.

        Pre-configures BidCos-RF interface.

        Args:
            host: Homegear hostname or IP address.
            name: Central unit name (default: "homegear").
            port: Custom BidCos-RF port (default: 2001).

        Returns:
            Pre-configured builder. Add credentials and call build().

        Example:
            config = (
                CentralConfigBuilder.for_homegear(host="192.168.1.50")
                .with_credentials(username="homegear", password="secret")
                .build()
            )

        """
        return cls().with_name(name=name).with_host(host=host).add_bidcos_rf_interface(port=port)

    def add_all_standard_interfaces(self) -> Self:
        """
        Add all standard CCU interfaces (HMIP_RF, BIDCOS_RF).

        Returns:
            Self for method chaining.

        """
        return self.add_hmip_interface().add_bidcos_rf_interface()

    def add_bidcos_rf_interface(self, *, port: int | None = None) -> Self:
        """
        Add BidCos RF wireless interface.

        Default ports: 2001 (plain), 42001 (TLS).

        Args:
            port: Custom port. Uses default if not specified.

        Returns:
            Self for method chaining.

        """
        return self.add_interface(interface=Interface.BIDCOS_RF, port=port)

    def add_bidcos_wired_interface(self, *, port: int | None = None) -> Self:
        """
        Add BidCos wired interface.

        Default ports: 2000 (plain), 42000 (TLS).

        Args:
            port: Custom port. Uses default if not specified.

        Returns:
            Self for method chaining.

        """
        return self.add_interface(interface=Interface.BIDCOS_WIRED, port=port)

    def add_cuxd_interface(self, *, port: int | None = None) -> Self:
        """
        Add CUxD interface.

        Default port: 8701.

        Args:
            port: Custom port. Uses default if not specified.

        Returns:
            Self for method chaining.

        """
        return self.add_interface(interface=Interface.CUXD, port=port)

    def add_hmip_interface(self, *, port: int | None = None) -> Self:
        """
        Add HomematicIP wireless interface (HMIP_RF).

        Default ports: 2010 (plain), 42010 (TLS).

        Args:
            port: Custom port. Uses default if not specified.

        Returns:
            Self for method chaining.

        """
        return self.add_interface(interface=Interface.HMIP_RF, port=port)

    def add_interface(
        self,
        *,
        interface: Interface,
        port: int | None = None,
        remote_path: str | None = None,
    ) -> Self:
        """
        Add a Homematic interface.

        Args:
            interface: Interface type (HMIP_RF, BIDCOS_RF, etc.).
            port: Custom port. If not specified, uses default port
                  (adjusted for TLS if enabled).
            remote_path: Optional remote path for the interface.

        Returns:
            Self for method chaining.

        """
        self._interfaces.append((interface, port, remote_path))
        return self

    def add_virtual_devices_interface(self, *, port: int | None = None) -> Self:
        """
        Add virtual devices interface.

        Default ports: 9292 (plain), 49292 (TLS).

        Args:
            port: Custom port. Uses default if not specified.

        Returns:
            Self for method chaining.

        """
        return self.add_interface(interface=Interface.VIRTUAL_DEVICES, port=port, remote_path="/groups")

    def build(self) -> CentralConfig:
        """
        Build the CentralConfig instance.

        Returns:
            Configured CentralConfig ready for create_central().

        Raises:
            ValueError: If required configuration is missing or invalid.

        """
        if errors := self.validate():
            error_msgs = [f"{e.field}: {e.message}" for e in errors]
            raise ValueError(f"Invalid configuration: {', '.join(error_msgs)}")  # i18n-exc: ignore

        # Import here to avoid circular imports
        from aiohomematic.central import CentralConfig  # noqa: PLC0415
        from aiohomematic.client import InterfaceConfig  # noqa: PLC0415

        # Build interface configs with resolved ports
        interface_configs: set[InterfaceConfig] = set()
        for interface, port, remote_path in self._interfaces:
            if resolved_port := port or get_interface_default_port(interface=interface, tls=self._tls):
                config_kwargs: dict[str, Any] = {
                    "central_name": self._name,
                    "interface": interface,
                    "port": resolved_port,
                }
                if remote_path:
                    config_kwargs["remote_path"] = remote_path
                interface_configs.add(InterfaceConfig(**config_kwargs))

        # Determine central_id
        central_id = self._central_id or f"{self._name}-{self._host}"

        # Determine json_port
        json_port = self._json_port or get_json_rpc_default_port(tls=self._tls)

        return CentralConfig(
            # Required
            central_id=central_id,
            host=self._host,  # type: ignore[arg-type]
            interface_configs=interface_configs,
            name=self._name,  # type: ignore[arg-type]
            password=self._password,  # type: ignore[arg-type]
            username=self._username,  # type: ignore[arg-type]
            # Connection
            client_session=self._client_session,
            tls=self._tls,
            verify_tls=self._verify_tls,
            json_port=json_port,
            # Callback
            callback_host=self._callback_host,
            callback_port_xml_rpc=self._callback_port_xml_rpc,
            default_callback_port_xml_rpc=self._default_callback_port_xml_rpc,
            listen_ip_addr=self._listen_ip_addr,
            listen_port_xml_rpc=self._listen_port_xml_rpc,
            # Features
            enable_program_scan=self._enable_program_scan,
            enable_sysvar_scan=self._enable_sysvar_scan,
            enable_device_firmware_check=self._enable_device_firmware_check,
            program_markers=self._program_markers,
            sysvar_markers=self._sysvar_markers,
            # Storage
            storage_directory=self._storage_directory,
            # Advanced
            delay_new_device_creation=self._delay_new_device_creation,
            ignore_custom_device_definition_models=self._ignore_custom_device_definition_models,
            interfaces_requiring_periodic_refresh=self._interfaces_requiring_periodic_refresh,
            max_read_workers=self._max_read_workers,
            optional_settings=self._optional_settings,
            schedule_timer_config=self._schedule_timer_config,
            start_direct=self._start_direct,
            timeout_config=self._timeout_config,
            un_ignore_list=self._un_ignore_list,
            use_group_channel_for_cover_state=self._use_group_channel_for_cover_state,
            locale=self._locale,
        )

    def validate(self) -> list[ValidationError]:
        """
        Validate the current configuration.

        Returns:
            List of validation errors. Empty if configuration is valid.

        """
        errors: list[ValidationError] = []

        if not self._name:
            errors.append(ValidationError(field="name", message="Name is required"))

        if not self._host:
            errors.append(ValidationError(field="host", message="Host is required"))

        if self._username is None:
            errors.append(ValidationError(field="username", message="Username is required"))

        if self._password is None:
            errors.append(ValidationError(field="password", message="Password is required"))

        if not self._interfaces:
            errors.append(ValidationError(field="interfaces", message="At least one interface is required"))

        return errors

    def with_callback(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        listen_ip: str | None = None,
        listen_port: int | None = None,
    ) -> Self:
        """
        Configure XML-RPC callback server settings.

        The callback server receives events from the CCU. If not configured,
        the system auto-detects appropriate values.

        Args:
            host: Callback host address reported to CCU. Auto-detected if None.
            port: Callback port reported to CCU. Auto-assigned if None.
            listen_ip: IP address to bind the server to. Uses host if None.
            listen_port: Port to listen on. Uses port if None.

        Returns:
            Self for method chaining.

        """
        self._callback_host = host
        self._callback_port_xml_rpc = port
        self._listen_ip_addr = listen_ip
        self._listen_port_xml_rpc = listen_port
        return self

    def with_central_id(self, *, central_id: str) -> Self:
        """
        Set custom central ID.

        Args:
            central_id: Unique ID for this central. Auto-generated as
                        "{name}-{host}" if not specified.

        Returns:
            Self for method chaining.

        """
        self._central_id = central_id
        return self

    def with_client_session(self, *, session: ClientSession) -> Self:
        """
        Provide a custom aiohttp ClientSession.

        Args:
            session: Existing aiohttp session to use for HTTP requests.
                     If not provided, a new session will be created.

        Returns:
            Self for method chaining.

        """
        self._client_session = session
        return self

    def with_credentials(self, *, username: str, password: str) -> Self:
        """
        Set authentication credentials (required).

        Args:
            username: CCU/Homegear username.
            password: CCU/Homegear password.

        Returns:
            Self for method chaining.

        """
        self._username = username
        self._password = password
        return self

    def with_firmware_check(self, *, enabled: bool = True) -> Self:
        """
        Enable device firmware update checking.

        Args:
            enabled: Enable periodic firmware update availability checks.

        Returns:
            Self for method chaining.

        """
        self._enable_device_firmware_check = enabled
        return self

    def with_host(self, *, host: str) -> Self:
        """
        Set the CCU/Homegear host address (required).

        Args:
            host: IP address or hostname of the CCU/Homegear backend.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If host is empty or whitespace-only.

        """
        if not host or not host.strip():
            raise ValueError("Host cannot be empty")  # i18n-exc: ignore
        self._host = host.strip()
        return self

    def with_json_port(self, *, port: int) -> Self:
        """
        Set JSON-RPC port for ReGaHss communication.

        Args:
            port: JSON-RPC port (default: 80 plain, 443 TLS).

        Returns:
            Self for method chaining.

        """
        self._json_port = port
        return self

    def with_locale(self, *, locale: str) -> Self:
        """
        Set locale for translations.

        Args:
            locale: Locale code (e.g., "en", "de").

        Returns:
            Self for method chaining.

        """
        self._locale = locale
        return self

    def with_name(self, *, name: str) -> Self:
        """
        Set the central unit name (required).

        Args:
            name: Unique identifier for this central unit.
                  Used in logging, entity IDs, and storage paths.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If name is empty or whitespace-only.

        """
        if not name or not name.strip():
            raise ValueError("Name cannot be empty")  # i18n-exc: ignore
        self._name = name.strip()
        return self

    def with_optional_settings(self, *, settings: tuple[OptionalSettings | str, ...]) -> Self:
        """
        Set optional feature settings.

        Args:
            settings: Tuple of OptionalSettings flags.

        Returns:
            Self for method chaining.

        """
        self._optional_settings = settings
        return self

    def with_programs(
        self,
        *,
        enabled: bool = True,
        markers: tuple[DescriptionMarker | str, ...] | None = None,
    ) -> Self:
        """
        Configure CCU program scanning.

        Args:
            enabled: Enable program discovery and synchronization.
            markers: Optional markers to filter programs by description content.

        Returns:
            Self for method chaining.

        """
        self._enable_program_scan = enabled
        if markers is not None:
            self._program_markers = markers
        return self

    def with_schedule_timer_config(self, *, config: ScheduleTimerConfig) -> Self:
        """
        Set custom scheduler timer configuration.

        Args:
            config: ScheduleTimerConfig with custom interval values.

        Returns:
            Self for method chaining.

        """
        self._schedule_timer_config = config
        return self

    def with_start_direct(self, *, enabled: bool = True) -> Self:
        """
        Enable direct start mode (skip some initialization).

        Args:
            enabled: Enable direct start mode.

        Returns:
            Self for method chaining.

        """
        self._start_direct = enabled
        return self

    def with_storage(self, *, directory: str) -> Self:
        """
        Configure persistent storage location.

        Args:
            directory: Path to storage directory for caches and descriptions.

        Returns:
            Self for method chaining.

        """
        self._storage_directory = directory
        return self

    def with_sysvars(
        self,
        *,
        enabled: bool = True,
        markers: tuple[DescriptionMarker | str, ...] | None = None,
    ) -> Self:
        """
        Configure CCU system variable scanning.

        Args:
            enabled: Enable sysvar discovery and synchronization.
            markers: Optional markers to filter sysvars by description content.

        Returns:
            Self for method chaining.

        """
        self._enable_sysvar_scan = enabled
        if markers is not None:
            self._sysvar_markers = markers
        return self

    def with_timeout_config(self, *, config: TimeoutConfig) -> Self:
        """
        Set custom timeout configuration.

        Args:
            config: TimeoutConfig with custom timeout values.

        Returns:
            Self for method chaining.

        """
        self._timeout_config = config
        return self

    def with_tls(self, *, enabled: bool = True, verify: bool = True) -> Self:
        """
        Configure TLS settings.

        When TLS is enabled, interface ports automatically use TLS variants
        (e.g., 2010 → 42010 for HMIP_RF).

        Args:
            enabled: Enable TLS encryption for all connections.
            verify: Verify TLS certificates. Set to False for self-signed certs.
                    Note: Disabling verification reduces security.

        Returns:
            Self for method chaining.

        """
        self._tls = enabled
        self._verify_tls = verify
        return self

    def with_un_ignore_list(self, *, parameters: frozenset[str]) -> Self:
        """
        Set parameters to un-ignore (make visible).

        Args:
            parameters: Frozenset of parameter names to un-ignore.

        Returns:
            Self for method chaining.

        """
        self._un_ignore_list = parameters
        return self
