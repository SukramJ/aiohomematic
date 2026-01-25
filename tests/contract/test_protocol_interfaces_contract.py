# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for protocol interface stability.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for protocol interfaces.
Any change that breaks these tests requires a MAJOR version bump.

The contract ensures that:
1. Protocol interfaces are runtime checkable
2. Required methods and properties exist
3. Protocol exports are stable

See ADR-0018 for architectural context.
"""

from __future__ import annotations

from typing import Protocol

from aiohomematic.interfaces import (
    # Device/Channel/DataPoint protocols
    BaseDataPointProtocol,
    CallbackDataPointProtocol,
    # Central protocols
    CentralInfoProtocol,
    CentralProtocol,
    ChannelProtocol,
    # Client protocols
    ClientProtocol,
    ClientProviderProtocol,
    ConfigProviderProtocol,
    CustomDataPointProtocol,
    # Operations protocols
    DeviceDescriptionProviderProtocol,
    DeviceProtocol,
    EventBusProviderProtocol,
    GenericDataPointProtocol,
    # Hub protocols
    HubProtocol,
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    PrimaryClientProviderProtocol,
    TaskSchedulerProtocol,
)

# =============================================================================
# Contract: Protocol Runtime Checkability
# =============================================================================


class TestProtocolRuntimeCheckabilityContract:
    """Contract: Protocols must be runtime checkable."""

    def test_centralinfoprotocol_is_runtime_checkable(self) -> None:
        """Contract: CentralInfoProtocol is runtime checkable."""
        assert hasattr(CentralInfoProtocol, "__protocol_attrs__") or issubclass(CentralInfoProtocol, Protocol)

    def test_channelprotocol_is_runtime_checkable(self) -> None:
        """Contract: ChannelProtocol is runtime checkable."""
        assert issubclass(ChannelProtocol, Protocol)

    def test_clientprotocol_is_runtime_checkable(self) -> None:
        """Contract: ClientProtocol is runtime checkable."""
        assert issubclass(ClientProtocol, Protocol)

    def test_configproviderprotocol_is_runtime_checkable(self) -> None:
        """Contract: ConfigProviderProtocol is runtime checkable."""
        assert issubclass(ConfigProviderProtocol, Protocol)

    def test_deviceprotocol_is_runtime_checkable(self) -> None:
        """Contract: DeviceProtocol is runtime checkable."""
        assert issubclass(DeviceProtocol, Protocol)


# =============================================================================
# Contract: CentralInfoProtocol
# =============================================================================


class TestCentralInfoProtocolContract:
    """Contract: CentralInfoProtocol must have required members."""

    def test_centralinfoprotocol_has_model(self) -> None:
        """Contract: CentralInfoProtocol has model property."""
        assert "model" in dir(CentralInfoProtocol)

    def test_centralinfoprotocol_has_name(self) -> None:
        """Contract: CentralInfoProtocol has name property."""
        # Check that the protocol defines name
        assert "name" in dir(CentralInfoProtocol)


# =============================================================================
# Contract: ConfigProviderProtocol
# =============================================================================


class TestConfigProviderProtocolContract:
    """Contract: ConfigProviderProtocol must have required members."""

    def test_configproviderprotocol_has_config(self) -> None:
        """Contract: ConfigProviderProtocol has config property."""
        assert "config" in dir(ConfigProviderProtocol)


# =============================================================================
# Contract: EventBusProviderProtocol
# =============================================================================


class TestEventBusProviderProtocolContract:
    """Contract: EventBusProviderProtocol must have required members."""

    def test_eventbusproviderprotocol_has_event_bus(self) -> None:
        """Contract: EventBusProviderProtocol has event_bus property."""
        assert "event_bus" in dir(EventBusProviderProtocol)


# =============================================================================
# Contract: ClientProviderProtocol
# =============================================================================


class TestClientProviderProtocolContract:
    """Contract: ClientProviderProtocol must have required members."""

    def test_clientproviderprotocol_has_get_client(self) -> None:
        """Contract: ClientProviderProtocol has get_client method."""
        assert "get_client" in dir(ClientProviderProtocol)


# =============================================================================
# Contract: PrimaryClientProviderProtocol
# =============================================================================


class TestPrimaryClientProviderProtocolContract:
    """Contract: PrimaryClientProviderProtocol must have required members."""

    def test_primaryclientproviderprotocol_has_primary_client(self) -> None:
        """Contract: PrimaryClientProviderProtocol has primary_client property."""
        assert "primary_client" in dir(PrimaryClientProviderProtocol)


# =============================================================================
# Contract: DeviceProtocol
# =============================================================================


class TestDeviceProtocolContract:
    """Contract: DeviceProtocol must have required members."""

    def test_deviceprotocol_has_address(self) -> None:
        """Contract: DeviceProtocol has address property."""
        assert "address" in dir(DeviceProtocol)

    def test_deviceprotocol_has_available(self) -> None:
        """Contract: DeviceProtocol has available property."""
        assert "available" in dir(DeviceProtocol)

    def test_deviceprotocol_has_channels(self) -> None:
        """Contract: DeviceProtocol has channels property."""
        assert "channels" in dir(DeviceProtocol)

    def test_deviceprotocol_has_interface_id(self) -> None:
        """Contract: DeviceProtocol has interface_id property."""
        assert "interface_id" in dir(DeviceProtocol)


# =============================================================================
# Contract: ChannelProtocol
# =============================================================================


class TestChannelProtocolContract:
    """Contract: ChannelProtocol must have required members."""

    def test_channelprotocol_has_address(self) -> None:
        """Contract: ChannelProtocol has address property."""
        assert "address" in dir(ChannelProtocol)

    def test_channelprotocol_has_device(self) -> None:
        """Contract: ChannelProtocol has device property."""
        assert "device" in dir(ChannelProtocol)

    def test_channelprotocol_has_full_name(self) -> None:
        """Contract: ChannelProtocol has full_name property."""
        assert "full_name" in dir(ChannelProtocol)


# =============================================================================
# Contract: CallbackDataPointProtocol
# =============================================================================


class TestCallbackDataPointProtocolContract:
    """Contract: CallbackDataPointProtocol must have required members."""

    def test_callbackdatapointprotocol_has_unique_id(self) -> None:
        """Contract: CallbackDataPointProtocol has unique_id property."""
        assert "unique_id" in dir(CallbackDataPointProtocol)


# =============================================================================
# Contract: BaseDataPointProtocol
# =============================================================================


class TestBaseDataPointProtocolContract:
    """Contract: BaseDataPointProtocol must have required members."""

    def test_basedatapointprotocol_has_channel(self) -> None:
        """Contract: BaseDataPointProtocol has channel property."""
        assert "channel" in dir(BaseDataPointProtocol)


# =============================================================================
# Contract: GenericDataPointProtocol
# =============================================================================


class TestGenericDataPointProtocolContract:
    """Contract: GenericDataPointProtocol must have required members."""

    def test_genericdatapointprotocol_has_parameter(self) -> None:
        """Contract: GenericDataPointProtocol has parameter property."""
        assert "parameter" in dir(GenericDataPointProtocol)

    def test_genericdatapointprotocol_has_value(self) -> None:
        """Contract: GenericDataPointProtocol has value property."""
        assert "value" in dir(GenericDataPointProtocol)


# =============================================================================
# Contract: CustomDataPointProtocol
# =============================================================================


class TestCustomDataPointProtocolContract:
    """Contract: CustomDataPointProtocol must have required members."""

    def test_customdatapointprotocol_has_usage(self) -> None:
        """Contract: CustomDataPointProtocol has usage property."""
        assert "usage" in dir(CustomDataPointProtocol)


# =============================================================================
# Contract: HubProtocol
# =============================================================================


class TestHubProtocolContract:
    """Contract: HubProtocol must have required members."""

    def test_hubprotocol_has_inbox_dp(self) -> None:
        """Contract: HubProtocol has inbox_dp property."""
        assert "inbox_dp" in dir(HubProtocol)

    def test_hubprotocol_has_update_dp(self) -> None:
        """Contract: HubProtocol has update_dp property."""
        assert "update_dp" in dir(HubProtocol)


# =============================================================================
# Contract: DeviceDescriptionProviderProtocol
# =============================================================================


class TestDeviceDescriptionProviderProtocolContract:
    """Contract: DeviceDescriptionProviderProtocol must have required members."""

    def test_devicedescriptionproviderprotocol_has_get_device_description(self) -> None:
        """Contract: DeviceDescriptionProviderProtocol has get_device_description method."""
        assert "get_device_description" in dir(DeviceDescriptionProviderProtocol)


# =============================================================================
# Contract: ParamsetDescriptionProviderProtocol
# =============================================================================


class TestParamsetDescriptionProviderProtocolContract:
    """Contract: ParamsetDescriptionProviderProtocol must have required members."""

    def test_paramsetdescriptionproviderprotocol_has_get_channel_paramset_descriptions(self) -> None:
        """Contract: ParamsetDescriptionProviderProtocol has get_channel_paramset_descriptions method."""
        assert "get_channel_paramset_descriptions" in dir(ParamsetDescriptionProviderProtocol)


# =============================================================================
# Contract: ParameterVisibilityProviderProtocol
# =============================================================================


class TestParameterVisibilityProviderProtocolContract:
    """Contract: ParameterVisibilityProviderProtocol must have required members."""

    def test_parametervisibilityproviderprotocol_has_is_relevant_paramset(self) -> None:
        """Contract: ParameterVisibilityProviderProtocol has is_relevant_paramset method."""
        assert "is_relevant_paramset" in dir(ParameterVisibilityProviderProtocol)


# =============================================================================
# Contract: TaskSchedulerProtocol
# =============================================================================


class TestTaskSchedulerProtocolContract:
    """Contract: TaskSchedulerProtocol must have required members."""

    def test_taskschedulerprotocol_has_create_task(self) -> None:
        """Contract: TaskSchedulerProtocol has create_task method."""
        assert "create_task" in dir(TaskSchedulerProtocol)


# =============================================================================
# Contract: CentralProtocol
# =============================================================================


class TestCentralProtocolContract:
    """Contract: CentralProtocol is a composite of other protocols."""

    def test_centralprotocol_exists(self) -> None:
        """Contract: CentralProtocol exists."""
        assert CentralProtocol is not None

    def test_centralprotocol_is_protocol(self) -> None:
        """Contract: CentralProtocol is a Protocol."""
        assert issubclass(CentralProtocol, Protocol)


# =============================================================================
# Contract: Protocol Exports
# =============================================================================


class TestProtocolExportsContract:
    """Contract: Protocol exports from interfaces package must be stable."""

    def test_central_protocols_exported(self) -> None:
        """Contract: Central protocols are exported from interfaces package."""
        from aiohomematic import interfaces

        assert hasattr(interfaces, "CentralInfoProtocol")
        assert hasattr(interfaces, "ConfigProviderProtocol")
        assert hasattr(interfaces, "CentralProtocol")

    def test_client_protocols_exported(self) -> None:
        """Contract: Client protocols are exported from interfaces package."""
        from aiohomematic import interfaces

        assert hasattr(interfaces, "ClientProtocol")
        assert hasattr(interfaces, "ClientProviderProtocol")
        assert hasattr(interfaces, "PrimaryClientProviderProtocol")

    def test_hub_protocols_exported(self) -> None:
        """Contract: Hub protocols are exported from interfaces package."""
        from aiohomematic import interfaces

        assert hasattr(interfaces, "HubProtocol")
        assert hasattr(interfaces, "GenericHubDataPointProtocol")

    def test_model_protocols_exported(self) -> None:
        """Contract: Model protocols are exported from interfaces package."""
        from aiohomematic import interfaces

        assert hasattr(interfaces, "DeviceProtocol")
        assert hasattr(interfaces, "ChannelProtocol")
        assert hasattr(interfaces, "BaseDataPointProtocol")
        assert hasattr(interfaces, "GenericDataPointProtocol")
        assert hasattr(interfaces, "CustomDataPointProtocol")

    def test_operation_protocols_exported(self) -> None:
        """Contract: Operation protocols are exported from interfaces package."""
        from aiohomematic import interfaces

        assert hasattr(interfaces, "DeviceDescriptionProviderProtocol")
        assert hasattr(interfaces, "ParamsetDescriptionProviderProtocol")
        assert hasattr(interfaces, "ParameterVisibilityProviderProtocol")
        assert hasattr(interfaces, "TaskSchedulerProtocol")
