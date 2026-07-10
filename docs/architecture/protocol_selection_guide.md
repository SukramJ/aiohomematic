# Protocol Selection Guide

## Introduction

aiohomematic uses **83 protocol interfaces** (defined in `aiohomematic/interfaces/`) to
decouple components via the Interface Segregation Principle. Instead of depending on
large classes like `CentralUnit` or `InterfaceClient`, components declare minimal
protocol dependencies that expose only the operations they actually need.

ISP sub-protocol slices without a consumer independent of their composite (e.g. the former
per-operation client slices, or the atomic `Channel*`/`Device*` slices) have been flattened
directly into the relevant composite (`ClientProtocol`, `DeviceProtocol`, `ChannelProtocol`,
`CentralProtocol`) — declare the member directly there instead of importing a slice protocol
that no longer exists. Only sub-protocols with genuine standalone consumers remain separate.

This guide helps developers choose the right protocol when:

- **Writing a new component** that needs central/client/device access
- **Refactoring existing code** to reduce coupling
- **Writing tests** that need mock implementations

### Design Principles

1. **Depend on the narrowest protocol** that provides what you need
2. **Prefer sub-protocols** over composite protocols (e.g., `CentralInfoProtocol` over `CentralProtocol`)
3. **Use composite protocols** only when you genuinely need operations from multiple sub-protocols
4. All protocols use the `-Protocol` suffix and are `@runtime_checkable`

---

## Decision Tree

### "I need to..."

**...identify the central system (name, model, state)?**
Use `CentralInfoProtocol` (central.py)

**...read configuration?**
Use `ConfigProviderProtocol` (central.py)

**...access the event bus?**
Use `EventBusProviderProtocol` (central.py)

**...publish device trigger or system events?**
Use `EventPublisherProtocol` (central.py)

**...schedule async tasks?**
Use `TaskSchedulerProtocol` (operations.py)

**...look up a client by interface_id?**
Use `ClientProviderProtocol` (client.py)

**...create a new client instance?**
Use `ClientFactoryProtocol` (client.py)

**...look up devices?**
Use `DeviceProviderProtocol` (central.py) for the registry,
`DeviceQueryFacadeProtocol` (central.py) for read-only query facade access

**...look up channels by address?**
Use `ChannelLookupProtocol` (central.py)

**...look up data points?**
Use `DataPointProviderProtocol` (central.py)

**...read cached device data?**
Use `DataCacheProviderProtocol` (central.py)

**...write to the data cache?**
Use `DataCacheWriterProtocol` (client.py)

**...read device descriptions?**
Use `DeviceDescriptionProviderProtocol` (operations.py)

**...read paramset descriptions?**
Use `ParamsetDescriptionProviderProtocol` (operations.py)

**...check parameter visibility?**
Use `ParameterVisibilityProviderProtocol` (operations.py)

**...read device metadata (rooms, names)?**
Use `DeviceDetailsProviderProtocol` (operations.py)

**...refresh device data from backend?**
Use `DeviceDataRefresherProtocol` (central.py)

**...manage hub data points (programs, sysvars)?**
Use `HubDataPointManagerProtocol` (central.py)

**...perform file I/O?**
Use `FileOperationsProtocol` (central.py)

**...record diagnostic incidents?**
Use `IncidentRecorderProtocol` (operations.py)

**...access coordinators?**
Use `CoordinatorProviderProtocol` (coordinators.py)

---

## Protocol Categories

### 1. Identity & Configuration (4 protocols)

| Protocol                     | Module  | Purpose                                             |
| ---------------------------- | ------- | --------------------------------------------------- |
| `CentralInfoProtocol`        | central | System identification (name, model, version, state) |
| `ConfigProviderProtocol`     | central | Configuration access (`config` property)            |
| `SystemInfoProviderProtocol` | central | Backend system information                          |
| `CentralConfigProtocol`      | central | Full configuration interface                        |

### 2. Event System (3 protocols)

| Protocol                           | Module  | Purpose                                     |
| ---------------------------------- | ------- | ------------------------------------------- |
| `EventBusProviderProtocol`         | central | Access to the central event bus             |
| `EventPublisherProtocol`           | central | Publishing device trigger and system events |
| `EventSubscriptionManagerProtocol` | central | Managing event subscriptions                |

### 3. Cache Read — Providers (5 protocols)

| Protocol                              | Module     | Purpose                                        |
| ------------------------------------- | ---------- | ---------------------------------------------- |
| `DataCacheProviderProtocol`           | central    | Read device data cache                         |
| `DeviceDetailsProviderProtocol`       | operations | Read device metadata (rooms, names, functions) |
| `DeviceDescriptionProviderProtocol`   | operations | Read device descriptions                       |
| `ParamsetDescriptionProviderProtocol` | operations | Read paramset descriptions                     |
| `ParameterVisibilityProviderProtocol` | operations | Check parameter visibility rules               |

### 4. Cache Write — Writers (3 protocols)

| Protocol                            | Module | Purpose                     |
| ----------------------------------- | ------ | --------------------------- |
| `DataCacheWriterProtocol`           | client | Write to device data cache  |
| `DeviceDetailsWriterProtocol`       | client | Write device metadata       |
| `ParamsetDescriptionWriterProtocol` | client | Write paramset descriptions |

### 5. Client Management (~15 protocols)

**Core sub-protocols:**

| Protocol                   | Module | Purpose                                               |
| -------------------------- | ------ | ----------------------------------------------------- |
| `ClientIdentityProtocol`   | client | Basic identification (interface, interface_id, model) |
| `ClientConnectionProtocol` | client | Connection state management                           |

**Handler-based sub-protocols:**

| Protocol                            | Module | Purpose                        |
| ----------------------------------- | ------ | ------------------------------ |
| `DeviceDiscoveryOperationsProtocol` | client | Device discovery operations    |
| `MetadataOperationsProtocol`        | client | Metadata and system operations |

Lifecycle, value/paramset, linking, firmware, system variable, program, backup, and support
operations have no consumer independent of `ClientProtocol` and are declared directly on it
(formerly separate slices `ClientLifecycleProtocol`, `ParamsetOperationsProtocol`,
`ValueOperationsProtocol`, `LinkOperationsProtocol`, `FirmwareOperationsProtocol`,
`SystemVariableOperationsProtocol`, `ProgramOperationsProtocol`, `BackupOperationsProtocol`,
`ClientSupportProtocol`, and the combined `SystemManagementOperationsProtocol` /
`MaintenanceOperationsProtocol`). Depend on `ClientProtocol` directly for these operations.

**Combined protocols:**

| Protocol                             | Module | Purpose                                   |
| ------------------------------------ | ------ | ----------------------------------------- |
| `ValueAndParamsetOperationsProtocol` | client | Value + Paramset operations               |
| `ClientProtocol`                     | client | **Composite** of all client sub-protocols |

**Utility protocols:**

| Protocol                          | Module | Purpose                                                                                |
| --------------------------------- | ------ | -------------------------------------------------------------------------------------- |
| `ClientProviderProtocol`          | client | Lookup clients by interface_id                                                         |
| `ClientFactoryProtocol`           | client | Create new client instances                                                            |
| `ClientDependenciesProtocol`      | client | Composite of dependencies for clients (includes `json_rpc_client`, `callback_ip_addr`) |
| `PrimaryClientProviderProtocol`   | client | Access to primary client                                                               |
| `ConnectionStateProviderProtocol` | client | Connection state information                                                           |
| `CommandTrackerProtocol`          | client | Command tracker operations                                                             |
| `PingPongTrackerProtocol`         | client | Ping/pong cache operations                                                             |

### 6. Device & Channel Lookup (4 protocols)

| Protocol                    | Module  | Purpose                           |
| --------------------------- | ------- | --------------------------------- |
| `DeviceProviderProtocol`    | central | Access device registry            |
| `ChannelLookupProtocol`     | central | Find channels by address          |
| `DataPointProviderProtocol` | central | Find data points                  |
| `DeviceQueryFacadeProtocol` | central | Read-only query facade over model |

### 7. Device Operations (1 protocol)

| Protocol                      | Module  | Purpose                          |
| ----------------------------- | ------- | -------------------------------- |
| `DeviceDataRefresherProtocol` | central | Refresh device data from backend |

`DeviceManagementProtocol` and `NewDeviceHandlerProtocol` had no consumer and were removed;
`CentralUnit` no longer exposes `get_device()`/`add_new_devices()` outside `DeviceQueryFacadeProtocol`
and the internal `DeviceCoordinator`/`DeviceRegistry`.

### 8. Hub Operations (2 protocols)

| Protocol                      | Module  | Purpose                                    |
| ----------------------------- | ------- | ------------------------------------------ |
| `HubDataFetcherProtocol`      | central | Fetch hub data + program execution/state   |
| `HubDataPointManagerProtocol` | central | Manage hub data points (programs, sysvars) |

`HubFetchOperationsProtocol` had no consumer independent of `HubDataFetcherProtocol` and was
inlined directly into it (its fetch methods are still duplicated independently on `HubProtocol`
in `interfaces/model.py`, unchanged).

### 9. Task Scheduling (1 protocol)

| Protocol                | Module     | Purpose                         |
| ----------------------- | ---------- | ------------------------------- |
| `TaskSchedulerProtocol` | operations | Schedule and manage async tasks |

### 10. Model Protocols

**Device hierarchy:**

```
DeviceProtocol (composite)
├── DeviceIdentityProtocol          — address, interface, model, name
├── DeviceChannelAccessProtocol     — channels, data points, events
└── (declared directly, no separate sub-protocol classes)
    ├── availability, available, config_pending, set_forced_availability
    ├── firmware, firmware_updatable, update_firmware, ...
    ├── link_peer_channels, create_central_links, remove_central_links
    ├── channel_groups, add_channel_to_group, get_channel_group_no, ...
    ├── product_group, rooms, rx_modes, ...  (configuration)
    ├── central_info, client, config_provider, ...  (dependency providers)
    ├── week_profile, has_week_profile, init_week_profile, ...
    └── finalize_init, on_config_changed, remove, ...  (lifecycle)
```

`DeviceIdentityProtocol` and `DeviceChannelAccessProtocol` remain separate protocols because
`DeviceRemovalInfoProtocol` depends on them independently of `DeviceProtocol`. All other former
sub-protocols (`DeviceStateProtocol`, `DeviceOperationsProtocol`, `DeviceAvailabilityProtocol`,
`DeviceFirmwareProtocol`, `DeviceLinkManagementProtocol`, `DeviceGroupManagementProtocol`,
`DeviceConfigurationProtocol`, `DeviceWeekProfileProtocol`, `DeviceProvidersProtocol`,
`DeviceLifecycleProtocol`) had no consumer independent of `DeviceProtocol` and were inlined.

**Channel hierarchy:**

```
ChannelProtocol (composite, flat — declares all members directly)
├── address, name, no, type_name, unique_id, ise_id  (identity)
├── calculated_data_points, generic_data_points, get_data_points, ...  (data point access)
├── group_master, group_no, link_peer_channels, ...  (grouping)
├── device, function, room, paramset_descriptions, ...  (metadata)
├── create_central_link, remove_central_link, ...  (link management)
└── finalize_init, on_config_changed, remove, ...  (lifecycle)
```

All former `Channel*` sub-protocols (`ChannelIdentityProtocol`, `ChannelDataPointAccessProtocol`,
`ChannelGroupingProtocol`, `ChannelMetadataProtocol`, `ChannelLinkManagementProtocol`,
`ChannelLifecycleProtocol`, and the mid-composites `ChannelMetadataAndGroupingProtocol` /
`ChannelManagementProtocol`) had no consumer independent of `ChannelProtocol` and were inlined —
unlike the device side, there is no `ChannelRemovalInfoProtocol` requiring them to stay separate.

**DataPoint hierarchy:**

```
CallbackDataPointProtocol (base for all)
├── GenericHubDataPointProtocol       — hub-level data points
│   ├── GenericSysvarDataPointProtocol   — system variables
│   ├── GenericProgramDataPointProtocol  — programs
│   ├── HubSensorDataPointProtocol       — hub sensors
│   ├── HubBinarySensorDataPointProtocol — hub binary sensors
│   └── GenericInstallModeDataPointProtocol — install mode
├── BaseDataPointProtocol             — channel-bound data points
│   └── BaseParameterDataPointProtocol[T] — parameter-backed
│       ├── GenericDataPointProtocol[T]   — generic entities
│       └── GenericEventProtocol[T]       — event entities
├── CustomDataPointProtocol           — device-specific data points
└── CalculatedDataPointProtocol       — derived/calculated values
```

### 11. Utility Protocols

| Protocol                          | Module       | Purpose                        |
| --------------------------------- | ------------ | ------------------------------ |
| `FileOperationsProtocol`          | central      | File I/O operations            |
| `CoordinatorProviderProtocol`     | coordinators | Access to coordinators         |
| `ClientCoordinationProtocol`      | client       | Client coordination operations |
| `SessionRecorderProviderProtocol` | client       | Session recording access       |
| `CommandTrackerProtocol`          | client       | Command tracker operations     |
| `PingPongTrackerProtocol`         | client       | Ping/pong cache operations     |
| `IncidentRecorderProtocol`        | operations   | Diagnostic incident recording  |
| `CacheWithStatisticsProtocol`     | operations   | Cache statistics access        |
| `MetricsProviderProtocol`         | central      | Metrics observer access        |

`BackupProviderProtocol` and `CallbackAddressProviderProtocol` had no consumer independent of
`CentralProtocol`. `create_backup_and_download` is now declared directly on `CentralProtocol`;
`callback_ip_addr`/`listen_port_xml_rpc`/`json_rpc_client` were already provided verbatim by
`ClientDependenciesProtocol` (also a `CentralProtocol` base), so removing the redundant slices
did not change `CentralProtocol`'s effective member set.

---

## Common Patterns

### Pattern 1: Coordinator with multiple protocol dependencies

Coordinators receive narrow protocol interfaces instead of the full `CentralUnit`:

```python
class CacheCoordinator:
    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        device_provider: DeviceProviderProtocol,
        client_provider: ClientProviderProtocol,
        data_point_provider: DataPointProviderProtocol,
        primary_client_provider: PrimaryClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
    ) -> None:
        ...
```

### Pattern 2: Model class with provider protocols

Device and Channel classes declare specific provider protocols:

```python
class Device:
    def __init__(
        self,
        *,
        device_details_provider: DeviceDetailsProviderProtocol,
        device_description_provider: DeviceDescriptionProviderProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        client_provider: ClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
        # ...more protocols
    ) -> None:
        ...
```

### Pattern 3: Internal helper with device protocol

Internal facade classes use the `DeviceProtocol` to access the parent device:

```python
class _DeviceAvailability:
    def __init__(self, *, device: DeviceProtocol) -> None:
        self._device = device
        # Access providers via self._device.device_description_provider, etc.
```

### Pattern 4: Test mocks with protocol compliance

Tests create minimal mock objects that satisfy protocol interfaces:

```python
class MockCentralInfo:
    """Mock implementation of CentralInfoProtocol for tests."""
    name = "test-central"
    model = "CCU3"
    state = CentralState.RUNNING
    # ...
```

---

## Anti-Patterns

### 1. Using composite when specific suffices

```python
# BAD: Depends on full CentralProtocol but only reads config
def process(central: CentralProtocol) -> None:
    timeout = central.config.timeout_config.rpc_timeout

# GOOD: Depends only on ConfigProviderProtocol
def process(config_provider: ConfigProviderProtocol) -> None:
    timeout = config_provider.config.timeout_config.rpc_timeout
```

### 2. Using ClientProtocol when only one operation group is needed

```python
# BAD: Full client when only reading values
async def read_state(client: ClientProtocol) -> Any:
    return await client.get_value(...)

# GOOD: Narrow to the specific operation protocol
async def read_state(client: ValueAndParamsetOperationsProtocol) -> Any:
    return await client.get_value(...)
```

### 3. Passing provider protocols through deep call chains

```python
# BAD: Threading 10 protocols through 5 layers of calls
def deep_function(
    central_info: CentralInfoProtocol,
    config_provider: ConfigProviderProtocol,
    event_bus_provider: EventBusProviderProtocol,
    ...
) -> None:
    ...

# GOOD: Accept a combined protocol or restructure the dependency graph
# so each layer only receives what it directly needs.
```

---

## Quick Reference

| I need to...               | Protocol                              | Import from               |
| -------------------------- | ------------------------------------- | ------------------------- |
| Get central name/model     | `CentralInfoProtocol`                 | `interfaces.central`      |
| Read config                | `ConfigProviderProtocol`              | `interfaces.central`      |
| Access event bus           | `EventBusProviderProtocol`            | `interfaces.central`      |
| Publish events             | `EventPublisherProtocol`              | `interfaces.central`      |
| Schedule tasks             | `TaskSchedulerProtocol`               | `interfaces.operations`   |
| Lookup client              | `ClientProviderProtocol`              | `interfaces.client`       |
| Create client              | `ClientFactoryProtocol`               | `interfaces.client`       |
| Lookup device              | `DeviceProviderProtocol`              | `interfaces.central`      |
| Lookup channel             | `ChannelLookupProtocol`               | `interfaces.central`      |
| Read data cache            | `DataCacheProviderProtocol`           | `interfaces.central`      |
| Write data cache           | `DataCacheWriterProtocol`             | `interfaces.client`       |
| Read device descriptions   | `DeviceDescriptionProviderProtocol`   | `interfaces.operations`   |
| Read paramset descriptions | `ParamsetDescriptionProviderProtocol` | `interfaces.operations`   |
| Check parameter visibility | `ParameterVisibilityProviderProtocol` | `interfaces.operations`   |
| Read device metadata       | `DeviceDetailsProviderProtocol`       | `interfaces.operations`   |
| Refresh device data        | `DeviceDataRefresherProtocol`         | `interfaces.central`      |
| Manage hub data points     | `HubDataPointManagerProtocol`         | `interfaces.central`      |
| Record incidents           | `IncidentRecorderProtocol`            | `interfaces.operations`   |
| Access coordinators        | `CoordinatorProviderProtocol`         | `interfaces.coordinators` |
| Full device access         | `DeviceProtocol`                      | `interfaces.model`        |
| Full channel access        | `ChannelProtocol`                     | `interfaces.model`        |
| Full client access         | `ClientProtocol`                      | `interfaces.client`       |
| Full central access        | `CentralProtocol`                     | `interfaces.central`      |
