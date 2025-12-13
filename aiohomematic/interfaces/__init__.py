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

    - `CentralInfo`: Central system identification (name, model, version)
    - `ConfigProvider`: Configuration access (config property)
    - `SystemInfoProvider`: Backend system information
    - `CentralUnitStateProvider`: Central unit lifecycle state

**Event System:**
    Protocols for event publishing and subscription.

    - `EventBusProvider`: Access to the central event bus
    - `EventPublisher`: Publishing backend and Homematic events
    - `EventSubscriptionManager`: Managing event subscriptions
    - `LastEventTracker`: Tracking last event timestamps

**Cache Read (Providers):**
    Protocols for reading cached data. Follow naming convention ``*Provider``.

    - `DataCacheProvider`: Read device data cache
    - `DeviceDetailsProvider`: Read device metadata (rooms, names, functions)
    - `DeviceDescriptionProvider`: Read device descriptions
    - `ParamsetDescriptionProvider`: Read paramset descriptions
    - `ParameterVisibilityProvider`: Check parameter visibility rules

**Cache Write (Writers):**
    Protocols for writing to caches. Follow naming convention ``*Writer``.

    - `DataCacheWriter`: Write to device data cache
    - `DeviceDetailsWriter`: Write device metadata
    - `ParamsetDescriptionWriter`: Write paramset descriptions

**Client Management:**
    Protocols for client lifecycle and communication.

    *Client Sub-Protocols (ISP):*
        - `ClientIdentity`: Basic identification (interface, interface_id, model)
        - `ClientConnection`: Connection state management
        - `ClientLifecycle`: Lifecycle operations (init, stop, proxy)
        - `ClientCapabilities`: Feature support flags (supports_*)
        - `DeviceDiscoveryOperations`: Device discovery operations
        - `ParamsetOperations`: Paramset operations
        - `ValueOperations`: Value read/write operations
        - `LinkOperations`: Device linking operations
        - `FirmwareOperations`: Firmware update operations
        - `SystemVariableOperations`: System variable operations
        - `ProgramOperations`: Program execution operations
        - `BackupOperations`: Backup operations
        - `MetadataOperations`: Metadata and system operations
        - `ClientSupport`: Utility methods and caches

    *Client Composite:*
        - `ClientProtocol`: Composite of all client sub-protocols

    *Client Utilities:*
        - `ClientProvider`: Lookup clients by interface_id
        - `ClientFactory`: Create new client instances
        - `ClientDependencies`: Composite of dependencies for clients
        - `PrimaryClientProvider`: Access to primary client
        - `JsonRpcClientProvider`: JSON-RPC client access
        - `ConnectionStateProvider`: Connection state information

**Device & Channel Lookup:**
    Protocols for finding devices and channels.

    - `DeviceProvider`: Access device registry
    - `DeviceLookup`: Find devices by various criteria
    - `ChannelLookup`: Find channels by address
    - `DataPointProvider`: Find data points
    - `DeviceDescriptionsAccess`: Access device descriptions

**Device Operations:**
    Protocols for device-related operations.

    - `DeviceManagement`: Device lifecycle operations
    - `DeviceDataRefresher`: Refresh device data from backend
    - `NewDeviceHandler`: Handle new device discovery

**Hub Operations:**
    Protocols for hub-level operations (programs, sysvars).

    - `HubDataFetcher`: Fetch hub data
    - `HubDataPointManager`: Manage hub data points
    - `HubFetchOperations`: Hub fetch operations

**Task Scheduling:**
    Protocols for async task management.

    - `TaskScheduler`: Schedule and manage async tasks

**Model Protocols:**
    Protocols defining the runtime model structure.

    *Device/Channel:*
        - `DeviceProtocol`: Physical device representation
        - `ChannelProtocol`: Device channel representation
        - `HubProtocol`: Hub-level entity

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

    - `BackupProvider`: Backup operations
    - `FileOperations`: File I/O operations
    - `CoordinatorProvider`: Access to coordinators
    - `CallbackAddressProvider`: Callback address management
    - `ClientCoordination`: Client coordination operations
    - `SessionRecorderProvider`: Session recording access
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
    BackupProvider,
    CentralHealthProtocol,
    CentralInfo,
    # Central composite protocol
    CentralProtocol,
    CentralStateMachineProtocol,
    CentralStateMachineProvider,
    CentralUnitStateProvider,
    ChannelLookup,
    ConfigProvider,
    ConnectionHealthProtocol,
    DataCacheProvider,
    DataPointProvider,
    DeviceDataRefresher,
    DeviceManagement,
    DeviceProvider,
    EventBusProvider,
    EventPublisher,
    EventSubscriptionManager,
    FileOperations,
    HealthProvider,
    HealthTrackerProtocol,
    HubDataFetcher,
    HubDataPointManager,
    HubFetchOperations,
    SystemInfoProvider,
)
from aiohomematic.interfaces.client import (
    # Client sub-protocols
    BackupOperations,
    # Client utilities
    CallbackAddressProvider,
    ClientCapabilities,
    ClientConnection,
    ClientCoordination,
    ClientDependencies,
    ClientFactory,
    ClientIdentity,
    ClientLifecycle,
    # Client composite protocol
    ClientProtocol,
    ClientProvider,
    ClientSupport,
    CommandCacheProtocol,
    ConnectionStateProvider,
    DataCacheWriter,
    DeviceDescriptionsAccess,
    DeviceDetailsWriter,
    DeviceDiscoveryOperations,
    DeviceLookup,
    FirmwareOperations,
    JsonRpcClientProvider,
    LastEventTracker,
    LinkOperations,
    MetadataOperations,
    NewDeviceHandler,
    ParamsetDescriptionWriter,
    ParamsetOperations,
    PingPongCacheProtocol,
    PrimaryClientProvider,
    ProgramOperations,
    SessionRecorderProvider,
    SystemVariableOperations,
    ValueOperations,
)
from aiohomematic.interfaces.coordinators import CoordinatorProvider
from aiohomematic.interfaces.model import (
    BaseDataPointProtocol,
    BaseParameterDataPointProtocol,
    CalculatedDataPointProtocol,
    CallbackDataPointProtocol,
    # Channel sub-protocols
    ChannelDataPointAccess,
    ChannelGrouping,
    ChannelIdentity,
    ChannelLifecycle,
    ChannelLinkManagement,
    ChannelMetadata,
    ChannelProtocol,
    CustomDataPointProtocol,
    # Device sub-protocols
    DeviceAvailability,
    DeviceChannelAccess,
    DeviceConfiguration,
    DeviceFirmware,
    DeviceGroupManagement,
    DeviceIdentity,
    DeviceLifecycle,
    DeviceLinkManagement,
    DeviceProtocol,
    DeviceProviders,
    DeviceWeekProfile,
    GenericDataPointProtocol,
    GenericEventProtocol,
    GenericHubDataPointProtocol,
    GenericInstallModeDataPointProtocol,
    GenericProgramDataPointProtocol,
    GenericSysvarDataPointProtocol,
    HubProtocol,
    HubSensorDataPointProtocol,
    WeekProfileProtocol,
)
from aiohomematic.interfaces.operations import (
    DeviceDescriptionProvider,
    DeviceDetailsProvider,
    ParameterVisibilityProvider,
    ParamsetDescriptionProvider,
    TaskScheduler,
)

__all__ = [
    # Central Composite Protocol
    "CentralProtocol",
    # Identity & Configuration
    "CentralInfo",
    "CentralUnitStateProvider",
    "ConfigProvider",
    "SystemInfoProvider",
    # Central State Machine
    "CentralStateMachineProtocol",
    "CentralStateMachineProvider",
    # Health Tracking
    "CentralHealthProtocol",
    "ConnectionHealthProtocol",
    "HealthProvider",
    "HealthTrackerProtocol",
    # Event System
    "EventBusProvider",
    "EventPublisher",
    "EventSubscriptionManager",
    "LastEventTracker",
    # Cache Read (Providers)
    "DataCacheProvider",
    "DeviceDescriptionProvider",
    "DeviceDescriptionsAccess",
    "DeviceDetailsProvider",
    "ParameterVisibilityProvider",
    "ParamsetDescriptionProvider",
    # Cache Write (Writers)
    "DataCacheWriter",
    "DeviceDetailsWriter",
    "ParamsetDescriptionWriter",
    # Client Management - Sub-Protocols (ISP)
    "BackupOperations",
    "ClientCapabilities",
    "ClientConnection",
    "ClientIdentity",
    "ClientLifecycle",
    "ClientSupport",
    "DeviceDiscoveryOperations",
    "FirmwareOperations",
    "LinkOperations",
    "MetadataOperations",
    "ParamsetOperations",
    "ProgramOperations",
    "SystemVariableOperations",
    "ValueOperations",
    # Client Management - Composite
    "ClientProtocol",
    # Client Management - Utilities
    "ClientDependencies",
    "ClientFactory",
    "ClientProvider",
    "ConnectionStateProvider",
    "JsonRpcClientProvider",
    "PrimaryClientProvider",
    # Device & Channel Lookup
    "ChannelLookup",
    "DataPointProvider",
    "DeviceLookup",
    "DeviceProvider",
    # Device Operations
    "DeviceDataRefresher",
    "DeviceManagement",
    "NewDeviceHandler",
    # Hub Operations
    "HubDataFetcher",
    "HubDataPointManager",
    "HubFetchOperations",
    # Task Scheduling
    "TaskScheduler",
    # Model Protocols - Channel (sub-protocols + composite)
    "ChannelDataPointAccess",
    "ChannelGrouping",
    "ChannelIdentity",
    "ChannelLifecycle",
    "ChannelLinkManagement",
    "ChannelMetadata",
    "ChannelProtocol",
    # Model Protocols - Device (sub-protocols + composite)
    "DeviceAvailability",
    "DeviceChannelAccess",
    "DeviceConfiguration",
    "DeviceFirmware",
    "DeviceGroupManagement",
    "DeviceIdentity",
    "DeviceLifecycle",
    "DeviceLinkManagement",
    "DeviceProtocol",
    "DeviceProviders",
    "DeviceWeekProfile",
    # Model Protocols - Hub
    "HubProtocol",
    # Model Protocols - DataPoint Hierarchy
    "BaseDataPointProtocol",
    "BaseParameterDataPointProtocol",
    "CalculatedDataPointProtocol",
    "CallbackDataPointProtocol",
    "CustomDataPointProtocol",
    "GenericDataPointProtocol",
    "GenericEventProtocol",
    # Model Protocols - Hub DataPoints
    "GenericHubDataPointProtocol",
    "GenericInstallModeDataPointProtocol",
    "GenericProgramDataPointProtocol",
    "GenericSysvarDataPointProtocol",
    "HubSensorDataPointProtocol",
    # Model Protocols - Other
    "WeekProfileProtocol",
    # Utility Protocols
    "BackupProvider",
    "CallbackAddressProvider",
    "ClientCoordination",
    "CommandCacheProtocol",
    "CoordinatorProvider",
    "FileOperations",
    "PingPongCacheProtocol",
    "SessionRecorderProvider",
]
