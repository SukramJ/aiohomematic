# Architecture Analysis - aiohomematic

**Date**: 2025-12-10
**Version**: 2025.11.16
**Python**: 3.13+

---

## Executive Summary

**aiohomematic** is a production-grade async Python library for controlling Homematic and HomematicIP devices, featuring a sophisticated three-tier dependency injection architecture with 63 protocol interfaces. The codebase demonstrates advanced architectural patterns including Facade, Factory, Observer, Circuit Breaker, and Request Coalescing, totaling **43,218 lines of code** across **102 Python files**.

### Key Characteristics

| Attribute           | Value                 |
| ------------------- | --------------------- |
| Total LOC           | 43,218                |
| Python Files        | 102                   |
| Protocol Interfaces | 63                    |
| Type Safety         | Full mypy strict mode |
| Handler Classes     | 8 specialized         |
| Coordinator Classes | 6                     |
| Custom Device Types | 13                    |
| Event Types         | 13                    |

---

## 1. Module Structure

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│           Home Assistant Integration / Consumer              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  aiohomematic.central (6,342 LOC | 11 files)                │
│  - CentralUnit: Main orchestrator (1,996 LOC)               │
│  - 6 Coordinators: Backend orchestration                    │
│  - EventBus: Type-safe event system (910 LOC)               │
│  - RPC Server: XML-RPC callback server                      │
└──────────────────────┬──────────────────────────────────────┘
          │
┌─────────┼─────────────────┬────────────────────┬────────────┐
│         │                 │                    │            │
├─────────▼───────┐  ┌──────▼────────┐  ┌───────▼────┐  ┌────▼────────┐
│ .client         │  │ .model        │  │ .interfaces│  │ .store      │
│ (7,134 LOC)     │  │ (16,849 LOC)  │  │ (3,725 LOC)│  │ (2,878 LOC) │
│ 16 files        │  │ 48 files      │  │ 6 files    │  │ 4 files     │
│                 │  │               │  │            │  │             │
│ Adapters:       │  │ Entity Types: │  │ 63 Proto:  │  │ Caches:     │
│ - ClientCCU     │  │ - Generic     │  │ - Central  │  │ - Persistent│
│ - ClientJson    │  │ - Custom      │  │ - Client   │  │ - Dynamic   │
│ - Homegear      │  │ - Calculated  │  │ - Model    │  │ - Visibility│
│                 │  │ - Hub         │  │ - Ops      │  │             │
│ Resilience:     │  │               │  │            │  │             │
│ - CircuitBreaker│  │               │  │            │  │             │
│ - Coalescer     │  │               │  │            │  │             │
│                 │  │               │  │            │  │             │
│ Handlers (8):   │  │               │  │            │  │             │
│ - DeviceOps     │  │               │  │            │  │             │
│ - Metadata      │  │               │  │            │  │             │
│ - LinkMgmt      │  │               │  │            │  │             │
│ - Firmware      │  │               │  │            │  │             │
│ - Programs      │  │               │  │            │  │             │
│ - Backup        │  │               │  │            │  │             │
│ - SysVars       │  │               │  │            │  │             │
└─────────────────┘  └───────────────┘  └────────────┘  └─────────────┘
```

### Module Details

| Module         | LOC    | Files | Key Components                                                                              |
| -------------- | ------ | ----- | ------------------------------------------------------------------------------------------- |
| **central**    | 6,342  | 11    | CentralUnit (1,996), EventBus (910), DeviceCoordinator (859)                                |
| **client**     | 7,134  | 16    | ClientCCU (1,650), JsonRPC (1,887), Handlers (2,322), CircuitBreaker (299), Coalescer (239) |
| **model**      | 16,849 | 48    | Device (1,909), WeekProfile (1,834), DataPoint (1,364), Climate (1,176), Light (1,041)      |
| **interfaces** | 3,725  | 6     | model.py (1,800), client.py (923), central.py (466)                                         |
| **store**      | 2,878  | 4     | persistent.py (1,148), dynamic.py (870), visibility.py (826)                                |
| **root**       | 6,290  | 17    | const.py (1,594), hmcli.py (955), support.py (718)                                          |

---

## 2. Three-Tier Dependency Injection

### Tier 1: Infrastructure Layer (Full DI)

Components receive only protocol interfaces with **zero CentralUnit references**:

```python
class DeviceCoordinator:
    def __init__(
        self,
        *,
        central_info: CentralInfo,
        channel_lookup: ChannelLookup,
        client_provider: ClientProvider,
        config_provider: ConfigProvider,
        # ... 17 protocol interfaces total
    ) -> None:
        # Zero references to CentralUnit
```

**Coordinators** (6 classes):

| Coordinator         | Protocols | LOC | Responsibility                      |
| ------------------- | --------- | --- | ----------------------------------- |
| CacheCoordinator    | 8         | 240 | Device/paramset description caching |
| ClientCoordinator   | 6         | 403 | Client creation, lifecycle          |
| DeviceCoordinator   | 17        | 859 | Device creation, registration       |
| EventCoordinator    | 2         | 320 | Event routing, subscriptions        |
| HubCoordinator      | 11        | 453 | Hub entity management               |
| BackgroundScheduler | 7         | 457 | Periodic tasks, health checks       |

### Tier 2: Coordinator Layer (Protocol-Based DI)

Coordinators compose via protocol interfaces exclusively:

```python
class ClientCoordinator:
    def __init__(
        self,
        *,
        client_factory: ClientFactory,  # Factory protocol
        central_info: CentralInfo,
        config_provider: ConfigProvider,
        coordinator_provider: CoordinatorProvider,
        system_info_provider: SystemInfoProvider,
    ) -> None:
```

### Tier 3: Model Layer (Full DI)

**Device** - 16 protocol interfaces:

```python
class Device:
    def __init__(
        self,
        *,
        central_info: CentralInfo,
        event_bus_provider: EventBusProvider,
        task_scheduler: TaskScheduler,
        client_provider: ClientProvider,
        device_details_provider: DeviceDetailsProvider,
        device_description_provider: DeviceDescriptionProvider,
        paramset_description_provider: ParamsetDescriptionProvider,
        parameter_visibility_provider: ParameterVisibilityProvider,
        config_provider: ConfigProvider,
        file_operations: FileOperations,
        device_data_refresher: DeviceDataRefresher,
        data_cache_provider: DataCacheProvider,
        channel_lookup: ChannelLookup,
        event_subscription_manager: EventSubscriptionManager,
        # ... 2 more
    ) -> None:
```

**Channel & DataPoint** - Access protocols through parent Device.

---

## 3. Protocol Interface Taxonomy

**Total: 63 @runtime_checkable protocols across 6 files**

### Distribution by File

| File            | Protocols | LOC   | Primary Domain                  |
| --------------- | --------- | ----- | ------------------------------- |
| model.py        | 18        | 1,800 | DataPoint, Device, Channel, Hub |
| client.py       | 20        | 923   | Client operations, caching      |
| central.py      | 19        | 466   | Central system, providers       |
| operations.py   | 5         | 159   | Task scheduling, descriptions   |
| coordinators.py | 1         | 59    | Coordinator access              |

### Central Protocols (19)

- **Identity**: `CentralInfo`, `CentralUnitStateProvider`, `ConfigProvider`, `SystemInfoProvider`
- **Events**: `EventBusProvider`, `EventPublisher`, `EventSubscriptionManager`
- **Data Access**: `DataPointProvider`, `DeviceProvider`, `ChannelLookup`, `DeviceLookup`
- **Cache**: `DataCacheProvider`, `DataCacheWriter`, `DeviceDetailsWriter`, `ParamsetDescriptionWriter`
- **Operations**: `DeviceDataRefresher`, `DeviceManagement`, `FileOperations`, `BackupProvider`
- **Hub**: `HubDataFetcher`, `HubDataPointManager`

### Client Protocols (20)

- **Core**: `ClientProtocol` (60+ methods), `ClientProvider`, `ClientFactory`, `ClientDependencies`
- **Caching**: `CommandCacheProtocol`, `PingPongCacheProtocol`
- **Events**: `InterfaceEventPublisher`, `LastEventTracker`
- **Support**: `ConnectionStateProvider`, `SessionRecorderProvider`, `JsonRpcClientProvider`

### Model Protocols (18)

- **DataPoint Hierarchy**:

  - `CallbackDataPointProtocol` → `BaseDataPointProtocol` → `BaseParameterDataPointProtocol`
  - `GenericDataPointProtocol`, `GenericEventProtocol`
  - `CustomDataPointProtocol`, `CalculatedDataPointProtocol`
  - `GenericHubDataPointProtocol`, `GenericSysvarDataPointProtocol`, `GenericProgramDataPointProtocol`

- **Entity Protocols** (Composite with Sub-Protocols):
  - `DeviceProtocol` composed of: Identity, ChannelAccess, Availability, Firmware, LinkManagement, GroupManagement, Configuration, WeekProfile, Providers, Lifecycle
  - `ChannelProtocol` composed of: Identity, DataPointAccess, Grouping, Metadata, LinkManagement, Lifecycle
  - `HubProtocol`, `WeekProfileProtocol`

### Operations Protocols (5)

- `TaskScheduler`, `ParameterVisibilityProvider`
- `DeviceDetailsProvider`, `DeviceDescriptionProvider`, `ParamsetDescriptionProvider`

---

## 4. Key Design Patterns

### 4.1 Facade Pattern

**Device** aggregates 16 protocol interfaces for DataPoints:

```python
class Device:
    """
    Facade aggregating 16 protocol interfaces.

    Responsibilities:
    1. Metadata & Identity
    2. Channel Hierarchy
    3. Value Caching
    4. Availability & State
    5. Firmware Management
    6. Links & Export
    7. Week Profile
    """
```

### 4.2 Factory Pattern

- **ClientFactory Protocol**: Creates client instances without CentralUnit coupling
- **DeviceProfileRegistry**: Device model → CustomDataPoint mappings
- **Entity Creation Factory**: `create_data_points_and_events()`

### 4.3 Observer Pattern (EventBus)

```python
@dataclass(frozen=True, slots=True)
class DataPointUpdatedEvent(Event):
    timestamp: datetime
    dpk: DataPointKey
    value: ParamType

# 13 Event Types:
# - DataPointUpdatedEvent, DataPointUpdatedCallbackEvent
# - BackendParameterEvent, BackendSystemEventData
# - HomematicEvent, SysvarUpdatedEvent
# - InterfaceEvent, DeviceUpdatedEvent
# - FirmwareUpdatedEvent, LinkPeerChangedEvent
# - DeviceRemovedEvent, plus more
```

### 4.4 Circuit Breaker Pattern

**New in recent refactoring** - Prevents retry-storms when backend unavailable:

```
State Machine:
    CLOSED (normal operation)
        │
        │ failure_threshold failures
        ▼
    OPEN (fast-fail all requests)
        │
        │ recovery_timeout elapsed
        ▼
    HALF_OPEN (test one request)
        │
        ├── success_threshold successes → CLOSED
        └── failure → OPEN
```

**Implementation** (`client/circuit_breaker.py` - 299 LOC):

- Per-interface circuit breakers
- Configurable thresholds (failure, recovery, success)
- Integrates with `CentralConnectionState`
- Metrics tracking (total, successful, failed, rejected requests)

### 4.5 Request Coalescing Pattern

**New in recent refactoring** - Deduplicates identical concurrent requests:

```python
# Multiple concurrent identical requests:
Request A (key="X") ──┬──> Execute ──> Result
                      │               │
Request B (key="X") ──┤               │
                      │               │
Request C (key="X") ──┴───────────────┴──> All receive Result
```

**Implementation** (`client/request_coalescer.py` - 239 LOC):

- Key-based request deduplication
- Single Future shared across callers
- Particularly beneficial during device discovery
- Metrics: coalesce rate tracking

### 4.6 Handler Pattern

**8 Specialized Handler Classes** (2,322 LOC total):

| Handler                 | LOC   | Responsibility                            |
| ----------------------- | ----- | ----------------------------------------- |
| DeviceOperationsHandler | 1,032 | Device-specific operations, value get/set |
| MetadataHandler         | 432   | Device/paramset metadata fetching         |
| LinkManagementHandler   | 197   | Central link operations                   |
| FirmwareHandler         | 146   | Firmware updates                          |
| ProgramHandler          | 142   | Program management                        |
| BackupHandler           | 138   | Backup operations                         |
| BaseHandler             | 100   | Common handler functionality              |
| SystemVariableHandler   | 98    | Sysvar operations                         |

### 4.7 Strategy Pattern (Entity Polymorphism)

- `GenericDataPoint` - Fallback entity type
- `CustomDpIpThermostat`, `CustomDpIpCover`, etc. - Device-specific
- `CalculatedDataPoint` - Derived values
- `GenericHubDataPoint` - Hub programs/sysvars

### 4.8 Coordinator Pattern

| Coordinator         | Responsibility                        |
| ------------------- | ------------------------------------- |
| CacheCoordinator    | Device/paramset description caching   |
| ClientCoordinator   | Client creation, lifecycle management |
| DeviceCoordinator   | Device creation, registration         |
| EventCoordinator    | Event routing, subscriptions          |
| HubCoordinator      | Hub entity management                 |
| BackgroundScheduler | Periodic tasks, health checks         |

---

## 5. Concurrency Model

### Async-First Architecture

- **asyncio**: Main event loop for all I/O operations
- **Looper**: Helper implementing `TaskScheduler` protocol
- **Background Scheduler**: Periodic tasks in separate thread

### Synchronization Primitives

```python
# Device Registry
self._lock: Final = asyncio.Lock()

# Device Coordinator
self._device_add_semaphore: Final = asyncio.Semaphore()

# Background Scheduler
self._active_event: Final = asyncio.Event()
self._devices_created_event: Final = asyncio.Event()
```

### Threading Model

- **Main Thread**: asyncio event loop
- **RPC Server Thread**: XML-RPC callbacks (separate thread)
- **Scheduler Thread**: Background periodic tasks

---

## 6. Code Metrics

### Lines of Code Distribution

```
Total: 43,218 LOC across 102 Python files

Top Files by LOC:
1. central/__init__.py        1,996 LOC (CentralUnit)
2. model/device.py            1,909 LOC (Device)
3. client/json_rpc.py         1,887 LOC (JsonRpcAioHttpClient)
4. model/week_profile.py      1,834 LOC (WeekProfile)
5. interfaces/model.py        1,800 LOC (18 protocols)
6. client/__init__.py         1,650 LOC (ClientCCU)
7. const.py                   1,594 LOC (Constants, enums)
8. model/data_point.py        1,364 LOC (BaseDataPoint)
9. model/custom/climate.py    1,176 LOC (Climate entities)
10. store/persistent.py       1,148 LOC (Persistent caches)
```

### Protocol Statistics

- 63 Protocol Interfaces
- 100% @runtime_checkable
- CentralUnit implements all via structural subtyping
- No explicit inheritance required

### Module Size Distribution

| Module         | % of Total | LOC    |
| -------------- | ---------- | ------ |
| model          | 39.0%      | 16,849 |
| client         | 16.5%      | 7,134  |
| central        | 14.7%      | 6,342  |
| root utilities | 14.6%      | 6,290  |
| interfaces     | 8.6%       | 3,725  |
| store          | 6.7%       | 2,878  |

---

## 7. Architecture Strengths

### 7.1 Decoupling Excellence

- **63 protocol interfaces** eliminate circular dependencies
- **Three-tier DI** ensures minimal coupling at all levels
- **Facade pattern** provides single distribution point for protocols
- **Zero CentralUnit references** in model and coordinator layers

### 7.2 Type Safety

- **Full mypy strict mode** compliance across all 102 files
- **@runtime_checkable** protocols for dynamic verification
- **Complete type annotations** on all public APIs
- **TypeAlias** for complex type documentation

### 7.3 Testability

- **Protocol-based DI** enables comprehensive mocking
- **Pure model layer** (no I/O) simplifies unit testing
- **Handler pattern** isolates domain-specific operations
- **Factory protocols** allow test doubles

### 7.4 Resilience

- **Circuit Breaker** prevents retry-storms during outages
- **Request Coalescing** reduces backend load during discovery
- **Connection state tracking** per interface
- **Graceful degradation** when backends unavailable

### 7.5 Extensibility

- **DeviceProfileRegistry** for device-specific implementations
- **Composite protocols** with sub-protocols for narrower contracts
- **Event system** with typed events and priority levels
- **Handler pattern** for adding domain operations

### 7.6 Caching Strategy

- **Persistent caches**: DeviceDescription, ParamsetDescription (disk)
- **Dynamic caches**: CentralData, Command, PingPong (memory)
- **Visibility cache**: Parameter filtering rules
- **Age-based invalidation** and refresh policies

### 7.7 Event-Driven Architecture

- **Modern EventBus** with type-safe events
- **13 event types** for comprehensive state notification
- **Handler priority levels**: CRITICAL, HIGH, NORMAL, LOW
- **Batch publishing** for efficient multi-event scenarios

---

## 8. Architecture Evaluation

### 8.1 Maturity Assessment

| Aspect        | Rating    | Notes                      |
| ------------- | --------- | -------------------------- |
| Decoupling    | Excellent | 63 protocols, 3-tier DI    |
| Type Safety   | Excellent | Full mypy strict mode      |
| Testability   | Excellent | Protocol-based mocking     |
| Resilience    | Good      | CircuitBreaker, Coalescing |
| Performance   | Good      | Caching, coalescing, async |
| Extensibility | Excellent | Registry, handlers, events |
| Documentation | Good      | ADRs, architecture docs    |

### 8.2 Recent Improvements

1. **CircuitBreaker Pattern** (ADR 0001)

   - Prevents retry-storms during backend unavailability
   - Per-interface state tracking
   - Integrates with CentralConnectionState

2. **RequestCoalescer Pattern**

   - Deduplicates identical concurrent requests
   - Reduces backend load during device discovery
   - Metrics for monitoring effectiveness

3. **Handler Refactoring**

   - 8 specialized handler classes
   - Clear domain separation
   - Reduced ClientCCU complexity

4. **Protocol-Based DI** (ADR 0002, 0003)
   - 63 protocol interfaces
   - Three-tier architecture
   - Zero CentralUnit coupling in model/coordinators

### 8.3 Architectural Decisions (ADRs)

| ADR  | Title                                      | Status   |
| ---- | ------------------------------------------ | -------- |
| 0001 | CircuitBreaker and CentralConnectionState  | Accepted |
| 0002 | Protocol-Based Dependency Injection        | Accepted |
| 0003 | Explicit over Composite Protocol Injection | Accepted |
| 0004 | Thread-Based XML-RPC Server                | Accepted |
| 0005 | Unbounded Parameter Visibility Cache       | Accepted |
| 0006 | Event System Priorities and Batching       | Accepted |
| 0007 | Device Slots Reduction via Composition     | Rejected |
| 0008 | TaskGroup Migration                        | Deferred |

---

## 9. Pattern Summary

| Pattern                | Location                    | Benefit                            |
| ---------------------- | --------------------------- | ---------------------------------- |
| **Facade**             | Device, Channel             | Single protocol distribution point |
| **Factory**            | ClientFactory, Registry     | Flexible creation                  |
| **Observer**           | EventBus                    | Decoupled event handling           |
| **Strategy**           | Entity types                | Multiple implementations           |
| **Coordinator**        | 6 coordinators              | Clear separation                   |
| **Circuit Breaker**    | client/circuit_breaker.py   | Resilience                         |
| **Request Coalescing** | client/request_coalescer.py | Efficiency                         |
| **Handler**            | client/handlers/            | Domain separation                  |
| **DI (3-Tier)**        | All layers                  | Minimal coupling, type safety      |

---

## 10. Key Entry Points

```python
# Central configuration and orchestration
from aiohomematic.central import CentralConfig, CentralUnit

# Client configuration
from aiohomematic.client import InterfaceConfig, Interface

# Model classes
from aiohomematic.model import Device, Channel

# Protocol interfaces
from aiohomematic.interfaces import (
    CentralInfo,
    DeviceProtocol,
    CallbackDataPointProtocol,
    ClientFactory,
)

# Resilience patterns
from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from aiohomematic.client.request_coalescer import RequestCoalescer
```

---

## 11. Conclusion

**aiohomematic** demonstrates a mature, production-grade architecture:

- **Advanced 3-tier DI** with 63 protocols achieving complete decoupling
- **Modern Python patterns** (Protocol, dataclasses, async/await)
- **Full mypy strict mode** across 102 files / 43,218 LOC
- **Resilience patterns** (CircuitBreaker, RequestCoalescing)
- **Multiple extension points** for device types and operations
- **Async-first** with strategic threading and synchronization
- **Well-documented decisions** via 8 ADRs

The architecture successfully balances:

- **Flexibility** (protocols, factories, registries)
- **Safety** (type system, circuit breakers)
- **Performance** (caching, coalescing, async)
- **Maintainability** (clear boundaries, handlers, coordinators)
