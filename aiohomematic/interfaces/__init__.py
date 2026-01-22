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

    - `CentralInfoProtocol`: Central system identification (name, model, version, state)
    - `ConfigProviderProtocol`: Configuration access (config property)
    - `SystemInfoProviderProtocol`: Backend system information

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

    *Combined Client Operations:*
        - `DataManagementOperationsProtocol`: Alias for ValueAndParamsetOperationsProtocol
        - `SystemManagementOperationsProtocol`: SystemVariable + Program operations
        - `MaintenanceOperationsProtocol`: Link + Firmware + Backup operations

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

    *Device/Channel (Composite):*
        - `DeviceProtocol`: Physical device representation (uses consolidated sub-protocols)
        - `ChannelProtocol`: Device channel representation (uses consolidated sub-protocols)
        - `HubProtocol`: Hub-level data point

    *Device Combined Protocols:*
        - `DeviceStateProtocol`: Combined (Availability + Firmware + WeekProfile)
        - `DeviceOperationsProtocol`: Combined (LinkManagement + GroupManagement + Lifecycle)

    *Channel Combined Protocols:*
        - `ChannelMetadataAndGroupingProtocol`: Combined (Metadata + Grouping)
        - `ChannelManagementProtocol`: Combined (LinkManagement + Lifecycle)

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
        - `HubBinarySensorDataPointProtocol`: Hub binary sensor data points

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
    - `CommandTrackerProtocol`: Command tracker operations
    - `PingPongTrackerProtocol`: Ping/pong cache operations

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

from aiohomematic._log_context_protocol import LogContextProtocol
from aiohomematic.interfaces.central import (
    BackupProviderProtocol,
    CentralConfigProtocol,
    CentralHealthProtocol,
    CentralInfoProtocol,
    # Central composite protocol
    CentralProtocol,
    CentralStateMachineProtocol,
    CentralStateMachineProviderProtocol,
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
    HealthTrackerProtocol,
    HubDataFetcherProtocol,
    HubDataPointManagerProtocol,
    HubFetchOperationsProtocol,
    MetricsProviderProtocol,
    SystemInfoProviderProtocol,
)
from aiohomematic.interfaces.client import (
    # Client sub-protocols
    # Client utilities
    CallbackAddressProviderProtocol,
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
    CommandTrackerProtocol,
    ConnectionStateProviderProtocol,
    DataCacheWriterProtocol,
    # Combined client operation protocols
    DataManagementOperationsProtocol,
    DeviceDescriptionsAccessProtocol,
    DeviceDetailsWriterProtocol,
    DeviceDiscoveryOperationsProtocol,
    DeviceLookupProtocol,
    JsonRpcClientProviderProtocol,
    LastEventTrackerProtocol,
    MaintenanceOperationsProtocol,
    MetadataOperationsProtocol,
    NewDeviceHandlerProtocol,
    ParamsetDescriptionWriterProtocol,
    PingPongTrackerProtocol,
    PrimaryClientProviderProtocol,
    SessionRecorderProviderProtocol,
    SystemManagementOperationsProtocol,
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
    ChannelEventGroupProtocol,
    ChannelIdentityProtocol,
    # Channel combined protocols
    ChannelManagementProtocol,
    ChannelMetadataAndGroupingProtocol,
    ChannelProtocol,
    CustomDataPointProtocol,
    # Device sub-protocols
    DeviceChannelAccessProtocol,
    DeviceConfigurationProtocol,
    DeviceIdentityProtocol,
    # Device combined protocols
    DeviceOperationsProtocol,
    DeviceProtocol,
    DeviceProvidersProtocol,
    DeviceStateProtocol,
    GenericDataPointProtocol,
    GenericDataPointProtocolAny,
    GenericEventProtocol,
    GenericEventProtocolAny,
    GenericHubDataPointProtocol,
    GenericInstallModeDataPointProtocol,
    GenericProgramDataPointProtocol,
    GenericSysvarDataPointProtocol,
    HubBinarySensorDataPointProtocol,
    HubProtocol,
    HubSensorDataPointProtocol,
    WeekProfileProtocol,
)
from aiohomematic.interfaces.operations import (
    CacheWithStatisticsProtocol,
    DeviceDescriptionProviderProtocol,
    DeviceDetailsProviderProtocol,
    IncidentRecorderProtocol,
    ParameterVisibilityProviderProtocol,
    ParamsetDescriptionProviderProtocol,
    TaskSchedulerProtocol,
)

__all__ = [
    # Cache protocols
    "CacheWithStatisticsProtocol",
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
    # Central config
    "CentralConfigProtocol",
    # Central health
    "CentralHealthProtocol",
    "ConnectionHealthProtocol",
    "HealthTrackerProtocol",
    # Central identity
    "CentralInfoProtocol",
    "ConfigProviderProtocol",
    "SystemInfoProviderProtocol",
    # Central state machine
    "CentralStateMachineProtocol",
    "CentralStateMachineProviderProtocol",
    # Client composite
    "ClientProtocol",
    # Client operations
    "ClientConnectionProtocol",
    "ClientIdentityProtocol",
    "ClientLifecycleProtocol",
    "ClientSupportProtocol",
    "DataManagementOperationsProtocol",
    "DeviceDiscoveryOperationsProtocol",
    "MaintenanceOperationsProtocol",
    "MetadataOperationsProtocol",
    "SystemManagementOperationsProtocol",
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
    # Incident recording
    "IncidentRecorderProtocol",
    # Log context
    "LogContextProtocol",
    # Metrics
    "MetricsProviderProtocol",
    # Model channel
    "ChannelDataPointAccessProtocol",
    "ChannelEventGroupProtocol",
    "ChannelIdentityProtocol",
    "ChannelManagementProtocol",
    "ChannelMetadataAndGroupingProtocol",
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
    "DeviceChannelAccessProtocol",
    "DeviceConfigurationProtocol",
    "DeviceIdentityProtocol",
    "DeviceOperationsProtocol",
    "DeviceProtocol",
    "DeviceProvidersProtocol",
    "DeviceStateProtocol",
    # Model hub
    "GenericHubDataPointProtocol",
    "GenericInstallModeDataPointProtocol",
    "GenericProgramDataPointProtocol",
    "GenericSysvarDataPointProtocol",
    "HubBinarySensorDataPointProtocol",
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
    "CommandTrackerProtocol",
    "CoordinatorProviderProtocol",
    "FileOperationsProtocol",
    "PingPongTrackerProtocol",
    "SessionRecorderProviderProtocol",
]
