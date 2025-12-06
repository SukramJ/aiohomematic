"""
Protocol interfaces for reducing CentralUnit coupling.

This package defines protocol interfaces that components can depend on
instead of directly depending on CentralUnit. This allows for:
- Better testability (mock implementations)
- Clearer dependencies (only expose what's needed)
- Reduced coupling (components don't access full CentralUnit API)

All protocols are re-exported from this module for backward compatibility.
For explicit imports, use the submodules:
- aiohomematic.interfaces.client: Client-related protocols
- aiohomematic.interfaces.central: Central unit protocols
- aiohomematic.interfaces.model: Device, Channel, DataPoint protocols
- aiohomematic.interfaces.operations: Utility/operational protocols
- aiohomematic.interfaces.coordinators: Coordinator-specific protocols
"""

from __future__ import annotations

# Re-export all protocols for backward compatibility
from aiohomematic.interfaces.central import (
    BackupProvider,
    CentralInfo,
    CentralUnitStateProvider,
    ChannelLookup,
    ConfigProvider,
    DataCacheProvider,
    DataPointProvider,
    DeviceDataRefresher,
    DeviceManagement,
    DeviceProvider,
    EventBusProvider,
    EventPublisher,
    EventSubscriptionManager,
    FileOperations,
    HubDataFetcher,
    HubDataPointManager,
    SystemInfoProvider,
)
from aiohomematic.interfaces.client import (
    ClientCoordination,
    ClientFactory,
    ClientProtocol,
    ClientProvider,
    PrimaryClientProvider,
)
from aiohomematic.interfaces.coordinators import CoordinatorProvider
from aiohomematic.interfaces.model import (
    BaseDataPointProtocol,
    BaseParameterDataPointProtocol,
    CalculatedDataPointProtocol,
    CallbackDataPointProtocol,
    ChannelProtocol,
    CustomDataPointProtocol,
    DeviceProtocol,
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
    # Central protocols
    "BackupProvider",
    "CentralInfo",
    "CentralUnitStateProvider",
    "ChannelLookup",
    "ConfigProvider",
    "DataCacheProvider",
    "DataPointProvider",
    "DeviceDataRefresher",
    "DeviceManagement",
    "DeviceProvider",
    "EventBusProvider",
    "EventPublisher",
    "EventSubscriptionManager",
    "FileOperations",
    "HubDataFetcher",
    "HubDataPointManager",
    "SystemInfoProvider",
    # Client protocols
    "ClientCoordination",
    "ClientFactory",
    "ClientProtocol",
    "ClientProvider",
    "PrimaryClientProvider",
    # Coordinator protocols
    "CoordinatorProvider",
    # Model protocols
    "BaseDataPointProtocol",
    "BaseParameterDataPointProtocol",
    "CalculatedDataPointProtocol",
    "CallbackDataPointProtocol",
    "ChannelProtocol",
    "CustomDataPointProtocol",
    "DeviceProtocol",
    "GenericDataPointProtocol",
    "GenericEventProtocol",
    "GenericHubDataPointProtocol",
    "GenericInstallModeDataPointProtocol",
    "GenericProgramDataPointProtocol",
    "GenericSysvarDataPointProtocol",
    "HubProtocol",
    "HubSensorDataPointProtocol",
    "WeekProfileProtocol",
    # Operations protocols
    "DeviceDescriptionProvider",
    "DeviceDetailsProvider",
    "ParameterVisibilityProvider",
    "ParamsetDescriptionProvider",
    "TaskScheduler",
]
