"""Tests for CentralConfigBuilder."""

from __future__ import annotations

import pytest

from aiohomematic.central import CentralConfigBuilder, ValidationError
from aiohomematic.const import Interface


class TestCentralConfigBuilder:
    """Test CentralConfigBuilder."""

    def test_build_full_config(self) -> None:
        """Test building configuration with all options."""
        config = (
            CentralConfigBuilder()
            .with_name(name="production")
            .with_host(host="ccu.local")
            .with_credentials(username="Admin", password="secure123")
            .with_central_id(central_id="custom-id")
            .with_tls(enabled=True, verify=False)
            .add_hmip_interface()
            .add_bidcos_rf_interface()
            .with_storage(directory="/var/lib/test")
            .with_programs(enabled=True)
            .with_sysvars(enabled=True)
            .with_firmware_check(enabled=True)
            .with_locale(locale="de")
            .build()
        )

        assert config.name == "production"
        assert config.host == "ccu.local"
        assert config.central_id == "custom-id"
        assert config.tls is True
        assert config.verify_tls is False
        assert config.storage_directory == "/var/lib/test"
        assert config.enable_program_scan is True
        assert config.enable_sysvar_scan is True
        assert config.enable_device_firmware_check is True
        assert config.locale == "de"
        assert len(config.enabled_interface_configs) == 2

    def test_build_minimal_config(self) -> None:
        """Test building minimal valid configuration."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test-ccu")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .build()
        )

        assert config.name == "test-ccu"
        assert config.host == "192.168.1.100"
        assert config.username == "admin"
        assert config.password == "secret"
        assert config.central_id == "test-ccu-192.168.1.100"
        assert len(config.enabled_interface_configs) == 1


class TestBuilderValidation:
    """Test builder validation."""

    def test_build_raises_on_invalid(self) -> None:
        """Test build raises ValueError on invalid config."""
        builder = CentralConfigBuilder()

        with pytest.raises(ValueError, match="Invalid configuration"):
            builder.build()

    def test_validate_all_errors(self) -> None:
        """Test validation returns all errors."""
        builder = CentralConfigBuilder()
        errors = builder.validate()

        assert len(errors) == 5
        fields = [e.field for e in errors]
        assert "name" in fields
        assert "host" in fields
        assert "username" in fields
        assert "password" in fields
        assert "interfaces" in fields

    def test_validate_missing_credentials(self) -> None:
        """Test validation fails without credentials."""
        builder = CentralConfigBuilder().with_name(name="test").with_host(host="192.168.1.100").add_hmip_interface()

        errors = builder.validate()
        assert len(errors) == 2
        assert any(e.field == "username" for e in errors)
        assert any(e.field == "password" for e in errors)

    def test_validate_missing_host(self) -> None:
        """Test validation fails without host."""
        builder = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
        )

        errors = builder.validate()
        assert len(errors) == 1
        assert errors[0].field == "host"

    def test_validate_missing_interfaces(self) -> None:
        """Test validation fails without interfaces."""
        builder = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
        )

        errors = builder.validate()
        assert len(errors) == 1
        assert errors[0].field == "interfaces"

    def test_validate_missing_name(self) -> None:
        """Test validation fails without name."""
        builder = (
            CentralConfigBuilder()
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
        )

        errors = builder.validate()
        assert len(errors) == 1
        assert errors[0].field == "name"


class TestBuilderPresets:
    """Test builder presets."""

    def test_for_ccu_preset(self) -> None:
        """Test CCU preset creates correct configuration."""
        config = (
            CentralConfigBuilder.for_ccu(host="192.168.1.100")
            .with_credentials(username="Admin", password="secret")
            .build()
        )

        assert config.name == "ccu"
        assert config.host == "192.168.1.100"
        # Should have HMIP_RF and BIDCOS_RF
        interfaces = {ic.interface for ic in config.enabled_interface_configs}
        assert Interface.HMIP_RF in interfaces
        assert Interface.BIDCOS_RF in interfaces

    def test_for_ccu_preset_custom_name(self) -> None:
        """Test CCU preset with custom name."""
        config = (
            CentralConfigBuilder.for_ccu(host="192.168.1.100", name="my-ccu")
            .with_credentials(username="Admin", password="secret")
            .build()
        )

        assert config.name == "my-ccu"

    def test_for_homegear_preset(self) -> None:
        """Test Homegear preset creates correct configuration."""
        config = (
            CentralConfigBuilder.for_homegear(host="192.168.1.50")
            .with_credentials(username="homegear", password="secret")
            .build()
        )

        assert config.name == "homegear"
        assert config.host == "192.168.1.50"
        # Should have BIDCOS_RF only
        interfaces = {ic.interface for ic in config.enabled_interface_configs}
        assert Interface.BIDCOS_RF in interfaces
        assert len(interfaces) == 1

    def test_for_homegear_preset_custom_port(self) -> None:
        """Test Homegear preset with custom port."""
        config = (
            CentralConfigBuilder.for_homegear(host="192.168.1.50", port=2002)
            .with_credentials(username="homegear", password="secret")
            .build()
        )

        interface_config = next(iter(config.enabled_interface_configs))
        assert interface_config.port == 2002


class TestInterfaceConfiguration:
    """Test interface configuration methods."""

    def test_add_all_standard_interfaces(self) -> None:
        """Test adding all standard interfaces."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_all_standard_interfaces()
            .build()
        )

        interfaces = {ic.interface for ic in config.enabled_interface_configs}
        assert Interface.HMIP_RF in interfaces
        assert Interface.BIDCOS_RF in interfaces
        assert len(interfaces) == 2

    def test_add_bidcos_rf_interface(self) -> None:
        """Test adding BidCos RF interface."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_bidcos_rf_interface()
            .build()
        )

        interfaces = {ic.interface for ic in config.enabled_interface_configs}
        assert Interface.BIDCOS_RF in interfaces

    def test_add_bidcos_wired_interface(self) -> None:
        """Test adding BidCos wired interface."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_bidcos_wired_interface()
            .build()
        )

        interfaces = {ic.interface for ic in config.enabled_interface_configs}
        assert Interface.BIDCOS_WIRED in interfaces

    def test_add_cuxd_interface(self) -> None:
        """Test adding CUxD interface with explicit port (CUxD has no default)."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_cuxd_interface(port=8701)
            .build()
        )

        interfaces = {ic.interface for ic in config.enabled_interface_configs}
        assert Interface.CUXD in interfaces
        # Verify the port was set correctly
        cuxd_config = next(ic for ic in config.enabled_interface_configs if ic.interface == Interface.CUXD)
        assert cuxd_config.port == 8701

    def test_add_hmip_interface(self) -> None:
        """Test adding HMIP interface."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .build()
        )

        interfaces = {ic.interface for ic in config.enabled_interface_configs}
        assert Interface.HMIP_RF in interfaces

    def test_add_interface_custom_port(self) -> None:
        """Test adding interface with custom port."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface(port=12345)
            .build()
        )

        interface_config = next(iter(config.enabled_interface_configs))
        assert interface_config.port == 12345

    def test_add_virtual_devices_interface(self) -> None:
        """Test adding virtual devices interface."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_virtual_devices_interface()
            .build()
        )

        interfaces = {ic.interface for ic in config.enabled_interface_configs}
        assert Interface.VIRTUAL_DEVICES in interfaces


class TestTlsConfiguration:
    """Test TLS configuration."""

    def test_tls_disabled_by_default(self) -> None:
        """Test TLS is disabled by default."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .build()
        )

        assert config.tls is False
        assert config.verify_tls is False

    def test_tls_enabled(self) -> None:
        """Test enabling TLS."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .with_tls(enabled=True, verify=True)
            .add_hmip_interface()
            .build()
        )

        assert config.tls is True
        assert config.verify_tls is True

    def test_tls_without_verification(self) -> None:
        """Test TLS without certificate verification."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .with_tls(enabled=True, verify=False)
            .add_hmip_interface()
            .build()
        )

        assert config.tls is True
        assert config.verify_tls is False


class TestFeatureConfiguration:
    """Test feature configuration methods."""

    def test_firmware_check_disabled_by_default(self) -> None:
        """Test firmware check is disabled by default."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .build()
        )

        assert config.enable_device_firmware_check is False

    def test_firmware_check_enabled(self) -> None:
        """Test enabling firmware check."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .with_firmware_check(enabled=True)
            .build()
        )

        assert config.enable_device_firmware_check is True

    def test_programs_disabled(self) -> None:
        """Test disabling programs."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .with_programs(enabled=False)
            .build()
        )

        assert config.enable_program_scan is False

    def test_programs_enabled_by_default(self) -> None:
        """Test programs are enabled by default."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .build()
        )

        assert config.enable_program_scan is True

    def test_sysvars_disabled(self) -> None:
        """Test disabling sysvars."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .with_sysvars(enabled=False)
            .build()
        )

        assert config.enable_sysvar_scan is False

    def test_sysvars_enabled_by_default(self) -> None:
        """Test sysvars are enabled by default."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .build()
        )

        assert config.enable_sysvar_scan is True


class TestInputValidation:
    """Test input validation."""

    def test_empty_host_raises(self) -> None:
        """Test empty host raises ValueError."""
        builder = CentralConfigBuilder()
        with pytest.raises(ValueError, match="Host cannot be empty"):
            builder.with_host(host="")

    def test_empty_name_raises(self) -> None:
        """Test empty name raises ValueError."""
        builder = CentralConfigBuilder()
        with pytest.raises(ValueError, match="Name cannot be empty"):
            builder.with_name(name="")

    def test_host_trimmed(self) -> None:
        """Test host is trimmed."""
        config = (
            CentralConfigBuilder()
            .with_name(name="test")
            .with_host(host="  192.168.1.100  ")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .build()
        )

        assert config.host == "192.168.1.100"

    def test_name_trimmed(self) -> None:
        """Test name is trimmed."""
        config = (
            CentralConfigBuilder()
            .with_name(name="  test  ")
            .with_host(host="192.168.1.100")
            .with_credentials(username="admin", password="secret")
            .add_hmip_interface()
            .build()
        )

        assert config.name == "test"

    def test_whitespace_host_raises(self) -> None:
        """Test whitespace-only host raises ValueError."""
        builder = CentralConfigBuilder()
        with pytest.raises(ValueError, match="Host cannot be empty"):
            builder.with_host(host="   ")

    def test_whitespace_name_raises(self) -> None:
        """Test whitespace-only name raises ValueError."""
        builder = CentralConfigBuilder()
        with pytest.raises(ValueError, match="Name cannot be empty"):
            builder.with_name(name="   ")


class TestMethodChaining:
    """Test method chaining returns correct type."""

    def test_all_methods_return_self(self) -> None:
        """Test all configuration methods return self for chaining."""
        builder = CentralConfigBuilder()

        # All these should return the same builder instance
        assert builder.with_name(name="test") is builder
        assert builder.with_host(host="192.168.1.100") is builder
        assert builder.with_credentials(username="admin", password="secret") is builder
        assert builder.with_tls(enabled=True) is builder
        assert builder.add_hmip_interface() is builder
        assert builder.add_bidcos_rf_interface() is builder
        assert builder.add_bidcos_wired_interface() is builder
        assert builder.add_virtual_devices_interface() is builder
        assert builder.add_cuxd_interface() is builder
        assert builder.add_all_standard_interfaces() is builder
        assert builder.with_callback(host="192.168.1.1") is builder
        assert builder.with_programs(enabled=True) is builder
        assert builder.with_sysvars(enabled=True) is builder
        assert builder.with_firmware_check(enabled=True) is builder
        assert builder.with_storage(directory="/var/lib/test") is builder
        assert builder.with_central_id(central_id="custom-id") is builder
        assert builder.with_json_port(port=8080) is builder
        assert builder.with_locale(locale="de") is builder
        assert builder.with_start_direct(enabled=True) is builder
        assert builder.with_un_ignore_list(parameters=frozenset({"PARAM"})) is builder


class TestValidationErrorDataclass:
    """Test ValidationError dataclass."""

    def test_validation_error_immutable(self) -> None:
        """Test ValidationError is immutable."""
        error = ValidationError(field="test", message="Test message")
        assert error.field == "test"
        assert error.message == "Test message"

        # Should raise on modification attempt
        with pytest.raises(AttributeError):
            error.field = "other"  # type: ignore[misc]
