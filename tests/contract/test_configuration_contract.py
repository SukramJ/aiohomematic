# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for configuration class stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for configuration classes.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. CentralConfig fields remain stable
2. InterfaceConfig fields remain stable
3. TimeoutConfig fields remain stable
4. ScheduleTimerConfig fields remain stable
5. Factory methods work correctly

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import DEFAULT_TIMEOUT_CONFIG, Interface, RpcServerType, ScheduleTimerConfig, TimeoutConfig

# =============================================================================
# Contract: CentralConfig Fields
# =============================================================================


class TestCentralConfigFieldsContract:
    """Contract: CentralConfig fields must remain stable."""

    def test_centralconfig_has_callback_host(self) -> None:
        """Contract: CentralConfig has callback_host field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
            callback_host="192.168.1.2",
        )
        assert hasattr(config, "callback_host")
        assert config.callback_host == "192.168.1.2"

    def test_centralconfig_has_callback_port_xml_rpc(self) -> None:
        """Contract: CentralConfig has callback_port_xml_rpc field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
            callback_port_xml_rpc=9123,
        )
        assert hasattr(config, "callback_port_xml_rpc")
        assert config.callback_port_xml_rpc == 9123

    def test_centralconfig_has_central_id(self) -> None:
        """Contract: CentralConfig has central_id field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "central_id")
        assert isinstance(config.central_id, str)

    def test_centralconfig_has_enable_program_scan(self) -> None:
        """Contract: CentralConfig has enable_program_scan field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "enable_program_scan")
        assert isinstance(config.enable_program_scan, bool)

    def test_centralconfig_has_enable_sysvar_scan(self) -> None:
        """Contract: CentralConfig has enable_sysvar_scan field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "enable_sysvar_scan")
        assert isinstance(config.enable_sysvar_scan, bool)

    def test_centralconfig_has_host(self) -> None:
        """Contract: CentralConfig has host field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "host")
        assert isinstance(config.host, str)

    def test_centralconfig_has_json_port(self) -> None:
        """Contract: CentralConfig has json_port field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
            json_port=80,
        )
        assert hasattr(config, "json_port")
        assert config.json_port == 80

    def test_centralconfig_has_name(self) -> None:
        """Contract: CentralConfig has name field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "name")
        assert isinstance(config.name, str)

    def test_centralconfig_has_password(self) -> None:
        """Contract: CentralConfig has password field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "password")
        assert isinstance(config.password, str)

    def test_centralconfig_has_storage_directory(self) -> None:
        """Contract: CentralConfig has storage_directory field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "storage_directory")
        assert isinstance(config.storage_directory, str)

    def test_centralconfig_has_timeout_config(self) -> None:
        """Contract: CentralConfig has timeout_config field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "timeout_config")
        assert isinstance(config.timeout_config, TimeoutConfig)

    def test_centralconfig_has_tls(self) -> None:
        """Contract: CentralConfig has tls field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
            tls=True,
        )
        assert hasattr(config, "tls")
        assert config.tls is True

    def test_centralconfig_has_username(self) -> None:
        """Contract: CentralConfig has username field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "username")
        assert isinstance(config.username, str)

    def test_centralconfig_has_verify_tls(self) -> None:
        """Contract: CentralConfig has verify_tls field."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "verify_tls")
        assert isinstance(config.verify_tls, bool)


# =============================================================================
# Contract: CentralConfig Properties
# =============================================================================


class TestCentralConfigPropertiesContract:
    """Contract: CentralConfig properties must remain stable."""

    def test_centralconfig_has_connection_check_port(self) -> None:
        """Contract: CentralConfig has connection_check_port property."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
            json_port=80,
        )
        assert hasattr(config, "connection_check_port")
        assert isinstance(config.connection_check_port, int)

    def test_centralconfig_has_enable_xml_rpc_server(self) -> None:
        """Contract: CentralConfig has enable_xml_rpc_server property."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "enable_xml_rpc_server")
        assert isinstance(config.enable_xml_rpc_server, bool)

    def test_centralconfig_has_enabled_interface_configs(self) -> None:
        """Contract: CentralConfig has enabled_interface_configs property."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
        )
        assert hasattr(config, "enabled_interface_configs")
        assert isinstance(config.enabled_interface_configs, frozenset)


# =============================================================================
# Contract: CentralConfig Methods
# =============================================================================


class TestCentralConfigMethodsContract:
    """Contract: CentralConfig methods must remain stable."""

    def test_centralconfig_has_check_config_method(self) -> None:
        """Contract: CentralConfig has check_config async method."""
        assert hasattr(CentralConfig, "check_config")
        assert callable(getattr(CentralConfig, "check_config"))

    def test_centralconfig_has_create_central_method(self) -> None:
        """Contract: CentralConfig has create_central async method."""
        assert hasattr(CentralConfig, "create_central")
        assert callable(getattr(CentralConfig, "create_central"))

    def test_centralconfig_has_create_central_url_method(self) -> None:
        """Contract: CentralConfig has create_central_url method."""
        config = CentralConfig(
            central_id="test-id",
            host="192.168.1.1",
            interface_configs=set(),
            name="test",
            password="secret",
            username="admin",
            json_port=80,
        )
        assert hasattr(config, "create_central_url")
        url = config.create_central_url()
        assert isinstance(url, str)
        assert "192.168.1.1" in url


# =============================================================================
# Contract: CentralConfig Factory Methods
# =============================================================================


class TestCentralConfigFactoryMethodsContract:
    """Contract: CentralConfig factory methods must remain stable."""

    def test_centralconfig_has_for_ccu_factory(self) -> None:
        """Contract: CentralConfig.for_ccu factory method exists."""
        assert hasattr(CentralConfig, "for_ccu")
        assert callable(getattr(CentralConfig, "for_ccu"))

    def test_centralconfig_has_for_homegear_factory(self) -> None:
        """Contract: CentralConfig.for_homegear factory method exists."""
        assert hasattr(CentralConfig, "for_homegear")
        assert callable(getattr(CentralConfig, "for_homegear"))


# =============================================================================
# Contract: InterfaceConfig Fields
# =============================================================================


class TestInterfaceConfigFieldsContract:
    """Contract: InterfaceConfig fields must remain stable."""

    def test_interfaceconfig_has_enabled(self) -> None:
        """Contract: InterfaceConfig has enabled field."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.HMIP_RF,
            port=2010,
        )
        assert hasattr(config, "enabled")
        assert isinstance(config.enabled, bool)

    def test_interfaceconfig_has_interface(self) -> None:
        """Contract: InterfaceConfig has interface field."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.HMIP_RF,
            port=2010,
        )
        assert hasattr(config, "interface")
        assert isinstance(config.interface, Interface)

    def test_interfaceconfig_has_interface_id(self) -> None:
        """Contract: InterfaceConfig has interface_id field."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.HMIP_RF,
            port=2010,
        )
        assert hasattr(config, "interface_id")
        assert isinstance(config.interface_id, str)
        assert config.interface_id == "test-HmIP-RF"

    def test_interfaceconfig_has_port(self) -> None:
        """Contract: InterfaceConfig has port field."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.HMIP_RF,
            port=2010,
        )
        assert hasattr(config, "port")
        assert config.port == 2010

    def test_interfaceconfig_has_remote_path(self) -> None:
        """Contract: InterfaceConfig has remote_path field."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.VIRTUAL_DEVICES,
            port=9292,
            remote_path="/groups",
        )
        assert hasattr(config, "remote_path")
        assert config.remote_path == "/groups"

    def test_interfaceconfig_has_rpc_server(self) -> None:
        """Contract: InterfaceConfig has rpc_server field."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.HMIP_RF,
            port=2010,
        )
        assert hasattr(config, "rpc_server")
        assert isinstance(config.rpc_server, RpcServerType)


# =============================================================================
# Contract: InterfaceConfig Methods
# =============================================================================


class TestInterfaceConfigMethodsContract:
    """Contract: InterfaceConfig methods must remain stable."""

    def test_interfaceconfig_has_disable_method(self) -> None:
        """Contract: InterfaceConfig has disable method."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.HMIP_RF,
            port=2010,
        )
        assert hasattr(config, "disable")
        assert callable(getattr(config, "disable"))

        # Test that disable works
        assert config.enabled is True
        config.disable()
        assert config.enabled is False


# =============================================================================
# Contract: InterfaceConfig Interface Mapping
# =============================================================================


class TestInterfaceConfigInterfaceMappingContract:
    """Contract: InterfaceConfig interface to RPC server mapping must remain stable."""

    def test_bidcos_rf_uses_xml_rpc(self) -> None:
        """Contract: BidCos-RF uses XML-RPC server."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.BIDCOS_RF,
            port=2001,
        )
        assert config.rpc_server == RpcServerType.XML_RPC

    def test_ccu_jack_uses_none_rpc(self) -> None:
        """Contract: CCU-Jack uses NONE RPC server (no XML-RPC callback)."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.CCU_JACK,
            port=None,
        )
        assert config.rpc_server == RpcServerType.NONE
        # CCU-Jack should have port set to None
        assert config.port is None

    def test_cuxd_uses_none_rpc(self) -> None:
        """Contract: CUxD uses NONE RPC server (no XML-RPC callback)."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.CUXD,
            port=None,
        )
        assert config.rpc_server == RpcServerType.NONE
        # CUxD should have port set to None
        assert config.port is None

    def test_hmip_rf_uses_xml_rpc(self) -> None:
        """Contract: HmIP-RF uses XML-RPC server."""
        config = InterfaceConfig(
            central_name="test",
            interface=Interface.HMIP_RF,
            port=2010,
        )
        assert config.rpc_server == RpcServerType.XML_RPC


# =============================================================================
# Contract: TimeoutConfig Fields
# =============================================================================


class TestTimeoutConfigFieldsContract:
    """Contract: TimeoutConfig fields must remain stable."""

    def test_timeoutconfig_has_callback_warn_interval(self) -> None:
        """Contract: TimeoutConfig has callback_warn_interval field."""
        config = TimeoutConfig()
        assert hasattr(config, "callback_warn_interval")
        assert isinstance(config.callback_warn_interval, (int, float))

    def test_timeoutconfig_has_connectivity_error_threshold(self) -> None:
        """Contract: TimeoutConfig has connectivity_error_threshold field."""
        config = TimeoutConfig()
        assert hasattr(config, "connectivity_error_threshold")
        assert isinstance(config.connectivity_error_threshold, int)

    def test_timeoutconfig_has_ping_timeout(self) -> None:
        """Contract: TimeoutConfig has ping_timeout field."""
        config = TimeoutConfig()
        assert hasattr(config, "ping_timeout")
        assert isinstance(config.ping_timeout, (int, float))

    def test_timeoutconfig_has_reconnect_backoff_factor(self) -> None:
        """Contract: TimeoutConfig has reconnect_backoff_factor field."""
        config = TimeoutConfig()
        assert hasattr(config, "reconnect_backoff_factor")
        assert isinstance(config.reconnect_backoff_factor, (int, float))

    def test_timeoutconfig_has_reconnect_initial_delay(self) -> None:
        """Contract: TimeoutConfig has reconnect_initial_delay field."""
        config = TimeoutConfig()
        assert hasattr(config, "reconnect_initial_delay")
        assert isinstance(config.reconnect_initial_delay, (int, float))

    def test_timeoutconfig_has_reconnect_max_delay(self) -> None:
        """Contract: TimeoutConfig has reconnect_max_delay field."""
        config = TimeoutConfig()
        assert hasattr(config, "reconnect_max_delay")
        assert isinstance(config.reconnect_max_delay, (int, float))

    def test_timeoutconfig_has_reconnect_tcp_check_timeout(self) -> None:
        """Contract: TimeoutConfig has reconnect_tcp_check_timeout field."""
        config = TimeoutConfig()
        assert hasattr(config, "reconnect_tcp_check_timeout")
        assert isinstance(config.reconnect_tcp_check_timeout, (int, float))

    def test_timeoutconfig_has_reconnect_warmup_delay(self) -> None:
        """Contract: TimeoutConfig has reconnect_warmup_delay field."""
        config = TimeoutConfig()
        assert hasattr(config, "reconnect_warmup_delay")
        assert isinstance(config.reconnect_warmup_delay, (int, float))

    def test_timeoutconfig_has_rpc_timeout(self) -> None:
        """Contract: TimeoutConfig has rpc_timeout field."""
        config = TimeoutConfig()
        assert hasattr(config, "rpc_timeout")
        assert isinstance(config.rpc_timeout, (int, float))


# =============================================================================
# Contract: TimeoutConfig Default Values
# =============================================================================


class TestTimeoutConfigDefaultsContract:
    """Contract: TimeoutConfig default value guarantees."""

    def test_connectivity_error_threshold_is_at_least_1(self) -> None:
        """Contract: Default connectivity_error_threshold is at least 1."""
        config = TimeoutConfig()
        assert config.connectivity_error_threshold >= 1

    def test_reconnect_backoff_factor_is_2(self) -> None:
        """Contract: Default reconnect_backoff_factor is 2."""
        config = TimeoutConfig()
        assert config.reconnect_backoff_factor == 2


# =============================================================================
# Contract: ScheduleTimerConfig Fields
# =============================================================================


class TestScheduleTimerConfigFieldsContract:
    """Contract: ScheduleTimerConfig fields must remain stable."""

    def test_scheduletimerconfig_has_connection_checker_interval(self) -> None:
        """Contract: ScheduleTimerConfig has connection_checker_interval field."""
        config = ScheduleTimerConfig()
        assert hasattr(config, "connection_checker_interval")
        assert isinstance(config.connection_checker_interval, int)

    def test_scheduletimerconfig_has_device_firmware_check_interval(self) -> None:
        """Contract: ScheduleTimerConfig has device_firmware_check_interval field."""
        config = ScheduleTimerConfig()
        assert hasattr(config, "device_firmware_check_interval")
        assert isinstance(config.device_firmware_check_interval, int)

    def test_scheduletimerconfig_has_metrics_refresh_interval(self) -> None:
        """Contract: ScheduleTimerConfig has metrics_refresh_interval field."""
        config = ScheduleTimerConfig()
        assert hasattr(config, "metrics_refresh_interval")
        assert isinstance(config.metrics_refresh_interval, int)

    def test_scheduletimerconfig_has_periodic_refresh_interval(self) -> None:
        """Contract: ScheduleTimerConfig has periodic_refresh_interval field."""
        config = ScheduleTimerConfig()
        assert hasattr(config, "periodic_refresh_interval")
        assert isinstance(config.periodic_refresh_interval, int)

    def test_scheduletimerconfig_has_sys_scan_interval(self) -> None:
        """Contract: ScheduleTimerConfig has sys_scan_interval field."""
        config = ScheduleTimerConfig()
        assert hasattr(config, "sys_scan_interval")
        assert isinstance(config.sys_scan_interval, int)


# =============================================================================
# Contract: Default Config Constants
# =============================================================================


class TestDefaultConfigConstantsContract:
    """Contract: Default configuration constants must remain stable."""

    def test_default_timeout_config_exists(self) -> None:
        """Contract: DEFAULT_TIMEOUT_CONFIG exists and is TimeoutConfig."""
        assert isinstance(DEFAULT_TIMEOUT_CONFIG, TimeoutConfig)

    def test_default_timeout_config_is_immutable(self) -> None:
        """Contract: DEFAULT_TIMEOUT_CONFIG is a NamedTuple (immutable)."""
        # NamedTuples are immutable by design
        assert hasattr(DEFAULT_TIMEOUT_CONFIG, "_fields")
