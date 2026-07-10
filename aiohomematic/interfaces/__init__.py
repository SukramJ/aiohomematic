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
        - `DeviceDiscoveryOperationsProtocol`: Device discovery operations
        - `MetadataOperationsProtocol`: Metadata and system operations

    Sub-protocols without a consumer independent of `ClientProtocol` (lifecycle, value/paramset,
    linking, firmware, system variable, program, backup, support operations) are declared
    directly on the composite; see `aiohomematic.interfaces.client` for details.

    *Combined Client Operations:*
        - `ValueAndParamsetOperationsProtocol`: Value + paramset operations

    *Client Composite:*
        - `ClientProtocol`: Composite of all client sub-protocols

    *Client Utilities:*
        - `ClientProviderProtocol`: Lookup clients by interface_id
        - `ClientFactoryProtocol`: Create new client instances
        - `ClientDependenciesProtocol`: Composite of dependencies for clients
        - `PrimaryClientProviderProtocol`: Access to primary client
        - `ConnectionStateProviderProtocol`: Connection state information

**Device & Channel Lookup:**
    Protocols for finding devices and channels.

    - `DeviceProviderProtocol`: Access device registry
    - `ChannelLookupProtocol`: Find channels by address
    - `DataPointProviderProtocol`: Find data points
    - `DeviceDescriptionsAccess`: Access device descriptions

**Device Operations:**
    Protocols for device-related operations.

    - `DeviceDataRefresherProtocol`: Refresh device data from backend

**Hub Operations:**
    Protocols for hub-level operations (programs, sysvars).

    - `HubDataFetcherProtocol`: Fetch hub data
    - `HubDataPointManagerProtocol`: Manage hub data points

**Task Scheduling:**
    Protocols for async task management.

    - `TaskScheduler`: Schedule and manage async tasks

**Model Protocols:**
    Protocols defining the runtime model structure.

    *Device/Channel (Composite):*
        - `DeviceProtocol`: Physical device representation
        - `ChannelProtocol`: Device channel representation
        - `HubProtocol`: Hub-level data point

    Both `DeviceProtocol` and `ChannelProtocol` are flat composites: sub-protocols without a
    consumer independent of the composite are declared directly rather than split into separate
    sub-protocol classes. `DeviceIdentityProtocol` and `DeviceChannelAccessProtocol` remain
    separate because `DeviceRemovalInfoProtocol` depends on them independently of `DeviceProtocol`.

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

    - `FileOperationsProtocol`: File I/O operations
    - `CoordinatorProviderProtocol`: Access to coordinators
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

from aiohomematic._log_context_protocol import LogContextProtocol
from aiohomematic.interfaces.central import (
    CentralInfoProtocol,
    # Central composite protocol
    CentralProtocol,
    ChannelLookupProtocol,
    ConfigProviderProtocol,
    ConfigurationFacadeProtocol,
    DataCacheProviderProtocol,
    DataPointProviderProtocol,
    DeviceDataRefresherProtocol,
    DeviceProviderProtocol,
    DeviceQueryFacadeProtocol,
    EventBusProviderProtocol,
    EventPublisherProtocol,
    EventSubscriptionManagerProtocol,
    FileOperationsProtocol,
    HubDataFetcherProtocol,
    HubDataPointManagerProtocol,
    LinkFacadeProtocol,
    MetricsProviderProtocol,
    SystemInfoProviderProtocol,
)
from aiohomematic.interfaces.client import (
    # Client sub-protocols
    # Client utilities
    ClientConnectionProtocol,
    ClientCoordinationProtocol,
    ClientDependenciesProtocol,
    ClientFactoryProtocol,
    ClientIdentityProtocol,
    # Client composite protocol
    ClientProtocol,
    ClientProviderProtocol,
    CommandTrackerProtocol,
    ConnectionStateProviderProtocol,
    DataCacheWriterProtocol,
    DeviceDescriptionsAccessProtocol,
    DeviceDetailsWriterProtocol,
    DeviceDiscoveryOperationsProtocol,
    LastEventTrackerProtocol,
    MetadataOperationsProtocol,
    ParamsetDescriptionWriterProtocol,
    PingPongTrackerProtocol,
    PrimaryClientProviderProtocol,
    SessionRecorderProviderProtocol,
)
from aiohomematic.interfaces.coordinators import CoordinatorProviderProtocol
from aiohomematic.interfaces.model import (
    BaseDataPointProtocol,
    BaseParameterDataPointProtocol,
    CalculatedDataPointProtocol,
    CallbackDataPointProtocol,
    ChannelEventGroupProtocol,
    ChannelProtocol,
    ClimateWeekProfileDataPointProtocol,
    CombinedDataPointProtocol,
    CustomDataPointProtocol,
    # Device sub-protocols
    DeviceChannelAccessProtocol,
    DeviceIdentityProtocol,
    DeviceProtocol,
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
    ScheduleChannelSwitchProtocol,
    WeekProfileDataPointProtocol,
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
    # Central identity
    "CentralInfoProtocol",
    "ConfigProviderProtocol",
    "ConfigurationFacadeProtocol",
    "LinkFacadeProtocol",
    "SystemInfoProviderProtocol",
    # Client composite
    "ClientProtocol",
    # Client operations
    "ClientConnectionProtocol",
    "ClientIdentityProtocol",
    "DeviceDiscoveryOperationsProtocol",
    "MetadataOperationsProtocol",
    # Client providers
    "ClientDependenciesProtocol",
    "ClientFactoryProtocol",
    "ClientProviderProtocol",
    "ConnectionStateProviderProtocol",
    "PrimaryClientProviderProtocol",
    # Device and channel lookup
    "ChannelLookupProtocol",
    "DataPointProviderProtocol",
    "DeviceProviderProtocol",
    "DeviceQueryFacadeProtocol",
    # Device operations
    "DeviceDataRefresherProtocol",
    # Event system
    "EventBusProviderProtocol",
    "EventPublisherProtocol",
    "EventSubscriptionManagerProtocol",
    "LastEventTrackerProtocol",
    # Hub operations
    "HubDataFetcherProtocol",
    "HubDataPointManagerProtocol",
    # Incident recording
    "IncidentRecorderProtocol",
    # Log context
    "LogContextProtocol",
    # Metrics
    "MetricsProviderProtocol",
    # Model channel
    "ChannelEventGroupProtocol",
    "ChannelProtocol",
    # Model data point
    "BaseDataPointProtocol",
    "BaseParameterDataPointProtocol",
    "CalculatedDataPointProtocol",
    "CallbackDataPointProtocol",
    "CombinedDataPointProtocol",
    "CustomDataPointProtocol",
    "GenericDataPointProtocol",
    "GenericDataPointProtocolAny",
    "GenericEventProtocol",
    "GenericEventProtocolAny",
    # Model device
    "DeviceChannelAccessProtocol",
    "DeviceIdentityProtocol",
    "DeviceProtocol",
    # Model hub
    "GenericHubDataPointProtocol",
    "GenericInstallModeDataPointProtocol",
    "GenericProgramDataPointProtocol",
    "GenericSysvarDataPointProtocol",
    "HubBinarySensorDataPointProtocol",
    "HubProtocol",
    "HubSensorDataPointProtocol",
    # Model week profile
    "ClimateWeekProfileDataPointProtocol",
    "ScheduleChannelSwitchProtocol",
    "WeekProfileDataPointProtocol",
    "WeekProfileProtocol",
    # Task scheduling
    "TaskSchedulerProtocol",
    # Utility protocols
    "ClientCoordinationProtocol",
    "CommandTrackerProtocol",
    "CoordinatorProviderProtocol",
    "FileOperationsProtocol",
    "PingPongTrackerProtocol",
    "SessionRecorderProviderProtocol",
]
