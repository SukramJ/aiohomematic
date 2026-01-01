# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Protocol interfaces for reducing CentralUnit coupling.

This package defines protocol interfaces that components can depend on
instead of directly depending on CentralUnit. This allows for:
- Better testability (mock implementations)
- Clearer dependencies (only expose what's needed)
- Reduced coupling (components don't access full CentralUnit API)

Protocol Categories
-------------------

**Identity & Configuration:**
    Protocols providing system identification and configuration access.

    - `CentralInfoProtocol`: Central system identification (name, model, version)
    - `ConfigProviderProtocol`: Configuration access (config property)
    - `SystemInfoProviderProtocol`: Backend system information
    - `CentralUnitStateProviderProtocol`: Central unit lifecycle state

**Event System:**
    Protocols for event publishing and subscription.

    - `EventBusProviderProtocol`: Access to the central event bus
    - `EventPublisherProtocol`: Publishing backend and Homematic events
    - `EventSubscriptionManagerProtocol`: Managing event subscriptions
    - `LastEventTrackerProtocol`: Tracking last event timestamps

**Cache Read (Providers):**
    Protocols for reading cached data. Follow naming convention ``*Provider``.

    - `DataCacheProviderProtocol`: Read device data cache
    - `DeviceDetailsProviderProtocol`: Read device metadata (rooms, names, functions)
    - `DeviceDescriptionProviderProtocol`: Read device descriptions
    - `ParamsetDescriptionProviderProtocol`: Read paramset descriptions
    - `ParameterVisibilityProviderProtocol`: Check parameter visibility rules

**Cache Write (Writers):**
    Protocols for writing to caches. Follow naming convention ``*Writer``.

    - `DataCacheWriter`: Write to device data cache
    - `DeviceDetailsWriter`: Write device metadata
    - `ParamsetDescriptionWriter`: Write paramset descriptions

**Client Management:**
    Protocols for client lifecycle and communication.

    *Client Sub-Protocols (ISP):*
        - `ClientIdentityProtocol`: Basic identification (interface, interface_id, model)
        - `ClientConnectionProtocol`: Connection state management
        - `ClientLifecycleProtocol`: Lifecycle operations (init, stop, proxy)
        - `ClientCapabilitiesProtocol`: Feature support flags (supports_*)
        - `DeviceDiscoveryOperationsProtocol`: Device discovery operations
        - `ParamsetOperationsProtocol`: Paramset operations
        - `ValueOperationsProtocol`: Value read/write operations
        - `LinkOperationsProtocol`: Device linking operations
        - `FirmwareOperationsProtocol`: Firmware update operations
        - `SystemVariableOperationsProtocol`: System variable operations
        - `ProgramOperationsProtocol`: Program execution operations
        - `BackupOperationsProtocol`: Backup operations
        - `MetadataOperationsProtocol`: Metadata and system operations
        - `ClientSupportProtocol`: Utility methods and caches

    *Client Composite:*
        - `ClientProtocol`: Composite of all client sub-protocols

    *Client Utilities:*
        - `ClientProviderProtocol`: Lookup clients by interface_id
        - `ClientFactoryProtocol`: Create new client instances
        - `ClientDependenciesProtocol`: Composite of dependencies for clients
        - `PrimaryClientProviderProtocol`: Access to primary client
        - `JsonRpcClientProviderProtocol`: JSON-RPC client access
        - `ConnectionStateProviderProtocol`: Connection state information

**Device & Channel Lookup:**
    Protocols for finding devices and channels.

    - `DeviceProviderProtocol`: Access device registry
    - `DeviceLookupProtocol`: Find devices by various criteria
    - `ChannelLookupProtocol`: Find channels by address
    - `DataPointProviderProtocol`: Find data points
    - `DeviceDescriptionsAccess`: Access device descriptions

**Device Operations:**
    Protocols for device-related operations.

    - `DeviceManagementProtocol`: Device lifecycle operations
    - `DeviceDataRefresherProtocol`: Refresh device data from backend
    - `NewDeviceHandlerProtocol`: Handle new device discovery

**Hub Operations:**
    Protocols for hub-level operations (programs, sysvars).

    - `HubDataFetcherProtocol`: Fetch hub data
    - `HubDataPointManagerProtocol`: Manage hub data points
    - `HubFetchOperationsProtocol`: Hub fetch operations

**Task Scheduling:**
    Protocols for async task management.

    - `TaskScheduler`: Schedule and manage async tasks

**Model Protocols:**
    Protocols defining the runtime model structure.

    *Device/Channel:*
        - `DeviceProtocol`: Physical device representation
        - `ChannelProtocol`: Device channel representation
        - `HubProtocol`: Hub-level data point

    *DataPoint Hierarchy:*
        - `CallbackDataPointProtocol`: Base for all callback data points
        - `BaseDataPointProtocol`: Base for device data points
        - `BaseParameterDataPointProtocol`: Parameter-based data points
        - `GenericDataPointProtocol`: Generic parameter data points
        - `GenericEventProtocol`: Event-type data points
        - `CustomDataPointProtocol`: Device-specific data points
        - `CalculatedDataPointProtocol`: Derived/calculated values

    *Hub DataPoints:*
        - `GenericHubDataPointProtocol`: Base for hub data points
        - `GenericSysvarDataPointProtocol`: System variable data points
        - `GenericProgramDataPointProtocol`: Program data points
        - `GenericInstallModeDataPointProtocol`: Install mode data points
        - `HubSensorDataPointProtocol`: Hub sensor data points

    *Other:*
        - `WeekProfileProtocol`: Weekly schedule management

**Utility Protocols:**
    Other utility protocols.

    - `BackupProviderProtocol`: Backup operations
    - `FileOperationsProtocol`: File I/O operations
    - `CoordinatorProviderProtocol`: Access to coordinators
    - `CallbackAddressProviderProtocol`: Callback address management
    - `ClientCoordinationProtocol`: Client coordination operations
    - `SessionRecorderProviderProtocol`: Session recording access
    - `CommandCacheProtocol`: Command cache operations
    - `PingPongCacheProtocol`: Ping/pong cache operations

Submodules
----------

For explicit imports, use the submodules:

- ``aiohomematic.interfaces.central``: Central unit protocols
- ``aiohomematic.interfaces.client``: Client-related protocols
- ``aiohomematic.interfaces.model``: Device, Channel, DataPoint protocols
- ``aiohomematic.interfaces.operations``: Cache and visibility protocols
- ``aiohomematic.interfaces.coordinators``: Coordinator-specific protocols
"""

from __future__ import annotations

from aiohomematic.interfaces.central import (
    BackupProviderProtocol,
    CentralHealthProtocol,
    CentralInfoProtocol,
    # Central composite protocol
    CentralProtocol,
    CentralStateMachineProtocol,
    CentralStateMachineProviderProtocol,
    CentralUnitStateProviderProtocol,
    ChannelLookupProtocol,
    ConfigProviderProtocol,
    ConnectionHealthProtocol,
    DataCacheProviderProtocol,
    DataPointProviderProtocol,
    DeviceDataRefresherProtocol,
    DeviceManagementProtocol,
    DeviceProviderProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
    EventSubscriptionManagerProtocol,
    FileOperationsProtocol,
    HealthProviderProtocol,
    HealthTrackerProtocol,
    HubDataFetcherProtocol,
    HubDataPointManagerProtocol,
    HubFetchOperationsProtocol,
    MetricsProviderProtocol,
    SystemInfoProviderProtocol,
)
from aiohomematic.interfaces.client import (
    # Client sub-protocols
    BackupOperationsProtocol,
    # Client utilities
    CallbackAddressProviderProtocol,
    ClientCapabilitiesProtocol,
    ClientConnectionProtocol,
    ClientCoordinationProtocol,
    ClientDependenciesProtocol,
    ClientFactoryProtocol,
    ClientIdentityProtocol,
    ClientLifecycleProtocol,
    # Client composite protocol
    ClientProtocol,
    ClientProviderProtocol,
    ClientSupportProtocol,
    CommandCacheProtocol,
    ConnectionStateProviderProtocol,
    DataCacheWriterProtocol,
    DeviceDescriptionsAccessProtocol,
    DeviceDetailsWriterProtocol,
    DeviceDiscoveryOperationsProtocol,
    DeviceLookupProtocol,
    FirmwareOperationsProtocol,
    JsonRpcClientProviderProtocol,
    LastEventTrackerProtocol,
    LinkOperationsProtocol,
    MetadataOperationsProtocol,
    NewDeviceHandlerProtocol,
    ParamsetDescriptionWriterProtocol,
    ParamsetOperationsProtocol,
    PingPongCacheProtocol,
    PrimaryClientProviderProtocol,
    ProgramOperationsProtocol,
    SessionRecorderProviderProtocol,
    SystemVariableOperationsProtocol,
    ValueOperationsProtocol,
)
from aiohomematic.interfaces.coordinators import CoordinatorProviderProtocol
from aiohomematic.interfaces.model import (
    BaseDataPointProtocol,
    BaseParameterDataPointProtocol,
    BaseParameterDataPointProtocolAny,
    CalculatedDataPointProtocol,
    CallbackDataPointProtocol,
    # Channel sub-protocols
    ChannelDataPointAccessProtocol,
    ChannelGroupingProtocol,
    ChannelIdentityProtocol,
    ChannelLifecycleProtocol,
    ChannelLinkManagementProtocol,
    ChannelMetadataProtocol,
    ChannelProtocol,
    CustomDataPointProtocol,
    # Device sub-protocols
    DeviceAvailabilityProtocol,
    DeviceChannelAccessProtocol,
    DeviceConfigurationProtocol,
    DeviceFirmwareProtocol,
    DeviceGroupManagementProtocol,
    DeviceIdentityProtocol,
    DeviceLifecycleProtocol,
    DeviceLinkManagementProtocol,
    DeviceProtocol,
    DeviceProvidersProtocol,
    DeviceWeekProfileProtocol,
    GenericDataPointProtocol,
    GenericDataPointProtocolAny,
    GenericEventProtocol,
    GenericEventProtocolAny,
    GenericHubDataPointProtocol,
    GenericInstallModeDataPointProtocol,
    GenericProgramDataPointProtocol,
    GenericSysvarDataPointProtocol,
    HubProtocol,
    HubSensorDataPointProtocol,
    WeekProfileProtocol,
)
from aiohomematic.interfaces.operations import (
    DeviceDescriptionProviderProtocol,
    DeviceDetailsProviderProtocol,
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)

__all__ = [
    # Cache providers
    "DataCacheProviderProtocol",
    "DeviceDescriptionProviderProtocol",
    "DeviceDescriptionsAccessProtocol",
    "DeviceDetailsProviderProtocol",
    "ParameterVisibilityProviderProtocol",
    "ParamsetDescriptionProviderProtocol",
    # Cache writers
    "DataCacheWriterProtocol",
    "DeviceDetailsWriterProtocol",
    "ParamsetDescriptionWriterProtocol",
    # Central composite
    "CentralProtocol",
    # Central health
    "CentralHealthProtocol",
    "ConnectionHealthProtocol",
    "HealthProviderProtocol",
    "HealthTrackerProtocol",
    # Central identity
    "CentralInfoProtocol",
    "CentralUnitStateProviderProtocol",
    "ConfigProviderProtocol",
    "SystemInfoProviderProtocol",
    # Central state machine
    "CentralStateMachineProtocol",
    "CentralStateMachineProviderProtocol",
    # Client composite
    "ClientProtocol",
    # Client operations
    "BackupOperationsProtocol",
    "ClientCapabilitiesProtocol",
    "ClientConnectionProtocol",
    "ClientIdentityProtocol",
    "ClientLifecycleProtocol",
    "ClientSupportProtocol",
    "DeviceDiscoveryOperationsProtocol",
    "FirmwareOperationsProtocol",
    "LinkOperationsProtocol",
    "MetadataOperationsProtocol",
    "ParamsetOperationsProtocol",
    "ProgramOperationsProtocol",
    "SystemVariableOperationsProtocol",
    "ValueOperationsProtocol",
    # Client providers
    "ClientDependenciesProtocol",
    "ClientFactoryProtocol",
    "ClientProviderProtocol",
    "ConnectionStateProviderProtocol",
    "JsonRpcClientProviderProtocol",
    "PrimaryClientProviderProtocol",
    # Device and channel lookup
    "ChannelLookupProtocol",
    "DataPointProviderProtocol",
    "DeviceLookupProtocol",
    "DeviceProviderProtocol",
    # Device operations
    "DeviceDataRefresherProtocol",
    "DeviceManagementProtocol",
    "NewDeviceHandlerProtocol",
    # Event system
    "EventBusProviderProtocol",
    "EventPublisherProtocol",
    "EventSubscriptionManagerProtocol",
    "LastEventTrackerProtocol",
    # Hub operations
    "HubDataFetcherProtocol",
    "HubDataPointManagerProtocol",
    "HubFetchOperationsProtocol",
    # Metrics
    "MetricsProviderProtocol",
    # Model channel
    "ChannelDataPointAccessProtocol",
    "ChannelGroupingProtocol",
    "ChannelIdentityProtocol",
    "ChannelLifecycleProtocol",
    "ChannelLinkManagementProtocol",
    "ChannelMetadataProtocol",
    "ChannelProtocol",
    # Model data point
    "BaseDataPointProtocol",
    "BaseParameterDataPointProtocol",
    "BaseParameterDataPointProtocolAny",
    "CalculatedDataPointProtocol",
    "CallbackDataPointProtocol",
    "CustomDataPointProtocol",
    "GenericDataPointProtocol",
    "GenericDataPointProtocolAny",
    "GenericEventProtocol",
    "GenericEventProtocolAny",
    # Model device
    "DeviceAvailabilityProtocol",
    "DeviceChannelAccessProtocol",
    "DeviceConfigurationProtocol",
    "DeviceFirmwareProtocol",
    "DeviceGroupManagementProtocol",
    "DeviceIdentityProtocol",
    "DeviceLifecycleProtocol",
    "DeviceLinkManagementProtocol",
    "DeviceProtocol",
    "DeviceProvidersProtocol",
    "DeviceWeekProfileProtocol",
    # Model hub
    "GenericHubDataPointProtocol",
    "GenericInstallModeDataPointProtocol",
    "GenericProgramDataPointProtocol",
    "GenericSysvarDataPointProtocol",
    "HubProtocol",
    "HubSensorDataPointProtocol",
    # Model week profile
    "WeekProfileProtocol",
    # Task scheduling
    "TaskSchedulerProtocol",
    # Utility protocols
    "BackupProviderProtocol",
    "CallbackAddressProviderProtocol",
    "ClientCoordinationProtocol",
    "CommandCacheProtocol",
    "CoordinatorProviderProtocol",
    "FileOperationsProtocol",
    "PingPongCacheProtocol",
    "SessionRecorderProviderProtocol",
]
