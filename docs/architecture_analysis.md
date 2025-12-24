# Architecture Analysis - aiohomematic

**Date**: 2025-12-24
**Version**: 2025.12.47
**Python**: 3.13+

---

## Executive Summary

**aiohomematic** is a production-grade async Python library for controlling Homematic and HomematicIP devices, featuring a sophisticated three-tier dependency injection architecture with 104 protocol interfaces. The codebase demonstrates advanced architectural patterns including Facade, Factory, Observer, Circuit Breaker, and Request Coalescing, totaling **49,401 lines of code** across **124 Python files**.

### Key Characteristics

| Attribute           | Value                 |
| ------------------- | --------------------- |
| Total LOC           | 49,401                |
| Python Files        | 124                   |
| Protocol Interfaces | 104                   |
| Type Safety         | Full mypy strict mode |
| Handler Classes     | 8 specialized         |
| Coordinator Classes | 7                     |
| Custom Data Points  | 22                    |
| Event Types         | 14                    |

---

## 1. Module Structure

### Architecture Layers

```
+-------------------------------------------------------------+
|           Home Assistant Integration / Consumer              |
+---------------------------+---------------------------------+
                            |
+---------------------------v---------------------------------+
|  aiohomematic.central (9,586 LOC | 16 files)                |
|  - CentralUnit: Main orchestrator (1,675 LOC)               |
|  - 7 Coordinators: Backend orchestration                    |
|  - EventBus: Type-safe event system (942 LOC)               |
|  - RPC Server: XML-RPC callback server                      |
+---------------------------+---------------------------------+
            |
+-----------+---------------+------------------+--------------+
|           |               |                  |              |
+-----------v-----+ +-------v--------+ +-------v----+ +-------v-------+
| .client         | | .model         | | .interfaces| | .store        |
| (7,562 LOC)     | | (16,613 LOC)   | | (4,516 LOC)| | (3,549 LOC)   |
| 16 files        | | 51 files       | | 6 files    | | 17 files      |
|                 | |                | |            | |               |
| Adapters:       | | Entity Types:  | | 104 Proto: | | Subpackages:  |
| - ClientCCU     | | - Generic      | | - Central  | | - persistent/ |
| - ClientJson    | | - Custom       | | - Client   | | - dynamic/    |
| - Homegear      | | - Calculated   | | - Model    | | - visibility/ |
|                 | | - Hub          | | - Ops      | |               |
| Resilience:     | |                | |            | | Types:        |
| - CircuitBreaker| |                | |            | | - CachedCmd   |
| - Coalescer     | |                | |            | | - PongTracker |
|                 | |                | |            | |               |
| Handlers (8):   | |                | |            | |               |
| - DeviceOps     | |                | |            | |               |
| - Metadata      | |                | |            | |               |
| - LinkMgmt      | |                | |            | |               |
| - Firmware      | |                | |            | |               |
| - Programs      | |                | |            | |               |
| - Backup        | |                | |            | |               |
| - SysVars       | |                | |            | |               |
+-----------------+ +----------------+ +------------+ +---------------+
```

### Module Details

| Module         | LOC    | Files | Key Components                                                                              |
| -------------- | ------ | ----- | ------------------------------------------------------------------------------------------- |
| **central**    | 9,586  | 16    | CentralUnit (1,675), EventBus (942), Scheduler (905), DeviceCoordinator (878)               |
| **client**     | 7,562  | 16    | ClientCCU (1,774), JsonRPC (1,960), Handlers (2,374), CircuitBreaker (299), Coalescer (239) |
| **model**      | 16,613 | 51    | Device (1,719), WeekProfile (1,813), DataPoint (1,381), Climate (1,119), Light (976)        |
| **interfaces** | 4,516  | 6     | model.py (1,877), client.py (1,183), central.py (28 protocols)                              |
| **store**      | 3,549  | 17    | persistent/ (1,131), dynamic/ (910), visibility/ (1,209), types.py, serialization.py        |
| **root**       | 7,575  | 18    | const.py (1,867), hmcli.py (955), support.py (718)                                          |

---

## 2. Three-Tier Dependency Injection

### Tier 1: Infrastructure Layer (Full DI)

Components receive only protocol interfaces with **zero CentralUnit references**:

```python
class DeviceCoordinator:
    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        channel_lookup: ChannelLookupProtocol,
        client_provider: ClientProviderProtocol,
        config_provider: ConfigProviderProtocol,
        # ... 17 protocol interfaces total
    ) -> None:
        # Zero references to CentralUnit
```

**Coordinators** (7 classes):

| Coordinator         | Protocols | LOC | Responsibility                      |
| ------------------- | --------- | --- | ----------------------------------- |
| CacheCoordinator    | 8         | 227 | Device/paramset description caching |
| ClientCoordinator   | 6         | 453 | Client creation, lifecycle          |
| DeviceCoordinator   | 17        | 878 | Device creation, registration       |
| EventCoordinator    | 3         | 462 | Event routing, subscriptions        |
| HubCoordinator      | 11        | 463 | Hub entity management               |
| BackgroundScheduler | 7         | 905 | Periodic tasks, health checks       |
| RecoveryCoordinator | -         | 715 | Connection recovery orchestration   |

### Tier 2: Coordinator Layer (Protocol-Based DI)

Coordinators compose via protocol interfaces exclusively:

```python
class ClientCoordinator:
    def __init__(
        self,
        *,
        client_factory: ClientFactoryProtocol,  # Factory protocol
        central_info: CentralInfoProtocol,
        config_provider: ConfigProviderProtocol,
        coordinator_provider: CoordinatorProviderProtocol,
        system_info_provider: SystemInfoProviderProtocol,
    ) -> None:
```

### Tier 3: Model Layer (Full DI)

**Device** - 16 protocol interfaces:

```python
class Device:
    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        event_bus_provider: EventBusProviderProtocol,
        task_scheduler: TaskSchedulerProtocol,
        client_provider: ClientProviderProtocol,
        device_details_provider: DeviceDetailsProviderProtocol,
        device_description_provider: DeviceDescriptionProviderProtocol,
        paramset_description_provider: ParamsetDescriptionProviderProtocol,
        parameter_visibility_provider: ParameterVisibilityProviderProtocol,
        config_provider: ConfigProviderProtocol,
        file_operations: FileOperationsProtocol,
        device_data_refresher: DeviceDataRefresherProtocol,
        data_cache_provider: DataCacheProviderProtocol,
        channel_lookup: ChannelLookupProtocol,
        event_subscription_manager: EventSubscriptionManagerProtocol,
        # ... 2 more
    ) -> None:
```

**Channel & DataPoint** - Access protocols through parent Device.

---

## 3. Protocol Interface Taxonomy

**Total: 104 @runtime_checkable protocols across 6 files**

### Distribution by File

| File            | Protocols | LOC   | Primary Domain                  |
| --------------- | --------- | ----- | ------------------------------- |
| model.py        | 33        | 1,877 | DataPoint, Device, Channel, Hub |
| client.py       | 37        | 1,183 | Client operations, caching      |
| central.py      | 28        | 466   | Central system, providers       |
| operations.py   | 5         | 159   | Task scheduling, descriptions   |
| coordinators.py | 1         | 59    | Coordinator access              |

### Central Protocols (28)

- **Identity**: `CentralInfoProtocol`, `CentralUnitStateProviderProtocol`, `ConfigProviderProtocol`, `SystemInfoProviderProtocol`
- **Events**: `EventBusProviderProtocol`, `EventPublisherProtocol`, `EventSubscriptionManagerProtocol`
- **Data Access**: `DataPointProviderProtocol`, `DeviceProviderProtocol`, `ChannelLookupProtocol`, `DeviceLookupProtocol`
- **Cache**: `DataCacheProviderProtocol`, `DataCacheWriterProtocol`, `DeviceDetailsWriterProtocol`, `ParamsetDescriptionWriterProtocol`
- **Operations**: `DeviceDataRefresherProtocol`, `DeviceManagementProtocol`, `FileOperationsProtocol`, `BackupProviderProtocol`
- **Hub**: `HubDataFetcherProtocol`, `HubDataPointManagerProtocol`

### Client Protocols (37)

- **Core**: `ClientProtocol` (60+ methods), `ClientProviderProtocol`, `ClientFactoryProtocol`, `ClientDependenciesProtocol`
- **Caching**: `CommandCacheProtocol`, `PingPongCacheProtocol`
- **Events**: `InterfaceEventPublisherProtocol`, `LastEventTrackerProtocol`
- **Support**: `ConnectionStateProviderProtocol`, `SessionRecorderProviderProtocol`, `JsonRpcClientProviderProtocol`

### Model Protocols (33)

- **DataPoint Hierarchy**:

  - `CallbackDataPointProtocol` -> `BaseDataPointProtocol` -> `BaseParameterDataPointProtocol`
  - `GenericDataPointProtocol`, `GenericEventProtocol`
  - `CustomDataPointProtocol`, `CalculatedDataPointProtocol`
  - `GenericHubDataPointProtocol`, `GenericSysvarDataPointProtocol`, `GenericProgramDataPointProtocol`

- **Entity Protocols** (Composite with Sub-Protocols):
  - `DeviceProtocol` composed of: Identity, ChannelAccess, Availability, Firmware, LinkManagement, GroupManagement, Configuration, WeekProfile, Providers, Lifecycle
  - `ChannelProtocol` composed of: Identity, DataPointAccess, Grouping, Metadata, LinkManagement, Lifecycle
  - `HubProtocol`, `WeekProfileProtocol`

### Operations Protocols (5)

- `TaskSchedulerProtocol`, `ParameterVisibilityProviderProtocol`
- `DeviceDetailsProviderProtocol`, `DeviceDescriptionProviderProtocol`, `ParamsetDescriptionProviderProtocol`

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

- **ClientFactoryProtocol**: Creates client instances without CentralUnit coupling
- **DeviceProfileRegistry**: Device model -> CustomDataPoint mappings
- **Entity Creation Factory**: `create_data_points_and_events()`

### 4.3 Observer Pattern (EventBus)

```python
@dataclass(frozen=True, slots=True)
class DataPointUpdatedEvent(Event):
    timestamp: datetime
    dpk: DataPointKey
    value: ParamType

# Core Event Types (from event_bus.py):
# - DataPointUpdatedEvent, DataPointUpdatedCallbackEvent
# - BackendParameterEvent, DataPointStatusUpdatedEvent
# - SysvarUpdatedEvent, DeviceUpdatedEvent
# - FirmwareUpdatedEvent, LinkPeerChangedEvent
# - DeviceRemovedEvent
#
# Integration Event Types (from integration_events.py):
# - SystemStatusEvent, DeviceLifecycleEvent
# - DeviceTriggerEvent, DataPointsCreatedEvent
```

### 4.4 Circuit Breaker Pattern

Prevents retry-storms when backend unavailable:

```
State Machine:
    CLOSED (normal operation)
        |
        | failure_threshold failures
        v
    OPEN (fast-fail all requests)
        |
        | recovery_timeout elapsed
        v
    HALF_OPEN (test one request)
        |
        +-- success_threshold successes -> CLOSED
        +-- failure -> OPEN
```

**Implementation** (`client/circuit_breaker.py` - 299 LOC):

- Per-interface circuit breakers
- Configurable thresholds (failure, recovery, success)
- Integrates with `CentralConnectionState`
- Metrics tracking (total, successful, failed, rejected requests)

### 4.5 Request Coalescing Pattern

Deduplicates identical concurrent requests:

```python
# Multiple concurrent identical requests:
Request A (key="X") --+--> Execute --> Result
                      |               |
Request B (key="X") --+               |
                      |               |
Request C (key="X") --+---------------+--> All receive Result
```

**Implementation** (`client/request_coalescer.py` - 239 LOC):

- Key-based request deduplication
- Single Future shared across callers
- Particularly beneficial during device discovery
- Metrics: coalesce rate tracking

### 4.6 Handler Pattern

**8 Specialized Handler Classes** (2,374 LOC total):

| Handler                 | LOC   | Responsibility                            |
| ----------------------- | ----- | ----------------------------------------- |
| DeviceOperationsHandler | 1,086 | Device-specific operations, value get/set |
| MetadataHandler         | 435   | Device/paramset metadata fetching         |
| LinkManagementHandler   | 198   | Central link operations                   |
| BackupHandler           | 156   | Backup operations                         |
| FirmwareHandler         | 143   | Firmware updates                          |
| ProgramHandler          | 143   | Program management                        |
| SystemVariableHandler   | 98    | Sysvar operations                         |
| BaseHandler             | 78    | Common handler functionality              |

### 4.7 Strategy Pattern (Entity Polymorphism)

- `GenericDataPoint` - Fallback entity type
- `CustomDpIpThermostat`, `CustomDpIpCover`, etc. - Device-specific (22 types)
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
| RecoveryCoordinator | Connection recovery orchestration     |

---

## 5. Store Architecture

The `store` package manages all caching and persistence with a clean subpackage structure:

### Package Structure

```
store/
+-- __init__.py           # Re-exports public API
+-- types.py              # Shared types (CachedCommand, PongTracker)
+-- serialization.py      # Session recording utilities
+-- persistent/           # Disk-backed caches (1,131 LOC)
|   +-- base.py           # BasePersistentFile
|   +-- device.py         # DeviceDescriptionCache
|   +-- paramset.py       # ParamsetDescriptionCache
|   +-- session.py        # SessionRecorder
+-- dynamic/              # In-memory caches (910 LOC)
|   +-- command.py        # CommandCache
|   +-- data.py           # CentralDataCache
|   +-- details.py        # DeviceDetailsCache
|   +-- ping_pong.py      # PingPongCache
+-- visibility/           # Parameter filtering (1,209 LOC)
    +-- cache.py          # ParameterVisibilityCache
    +-- rules.py          # Visibility rules
    +-- parser.py         # Rule parsing
```

### Typed Cache Entries

```python
@dataclass(frozen=True, slots=True)
class CachedCommand:
    """Immutable cache entry for sent commands."""
    value: Any
    sent_at: datetime

@dataclass(slots=True)
class PongTracker:
    """Tracks ping/pong tokens with TTL."""
    tokens: set[str]
    seen_at: dict[str, float]
    logged: bool = False
```

---

## 6. Concurrency Model

### Async-First Architecture

- **asyncio**: Main event loop for all I/O operations
- **Looper**: Helper implementing `TaskSchedulerProtocol`
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

## 7. Code Metrics

### Lines of Code Distribution

```
Total: 49,401 LOC across 124 Python files

Top Files by LOC:
1. client/json_rpc.py         1,960 LOC (JsonRpcAioHttpClient)
2. interfaces/model.py        1,877 LOC (33 protocols)
3. const.py                   1,867 LOC (Constants, enums)
4. model/week_profile.py      1,813 LOC (WeekProfile)
5. client/__init__.py         1,774 LOC (ClientCCU)
6. model/device.py            1,719 LOC (Device)
7. central/__init__.py        1,675 LOC (CentralUnit)
8. model/data_point.py        1,381 LOC (BaseDataPoint)
9. interfaces/client.py       1,183 LOC (37 protocols)
10. model/custom/climate.py   1,119 LOC (Climate entities)
```

### Protocol Statistics

- 104 Protocol Interfaces
- 72 @runtime_checkable decorators
- CentralUnit implements all via structural subtyping
- No explicit inheritance required

### Module Size Distribution

| Module         | % of Total | LOC    |
| -------------- | ---------- | ------ |
| model          | 33.6%      | 16,613 |
| central        | 19.4%      | 9,586  |
| root utilities | 15.3%      | 7,575  |
| client         | 15.3%      | 7,562  |
| interfaces     | 9.1%       | 4,516  |
| store          | 7.2%       | 3,549  |

---

## 8. Architecture Strengths

### 8.1 Decoupling Excellence

- **104 protocol interfaces** eliminate circular dependencies
- **Three-tier DI** ensures minimal coupling at all levels
- **Facade pattern** provides single distribution point for protocols
- **Zero CentralUnit references** in model and coordinator layers

### 8.2 Type Safety

- **Full mypy strict mode** compliance across all 124 files
- **@runtime_checkable** protocols for dynamic verification
- **Complete type annotations** on all public APIs
- **TypeAlias** for complex type documentation
- **Typed dataclasses** for cache entries

### 8.3 Testability

- **Protocol-based DI** enables comprehensive mocking
- **Pure model layer** (no I/O) simplifies unit testing
- **Handler pattern** isolates domain-specific operations
- **Factory protocols** allow test doubles

### 8.4 Resilience

- **Circuit Breaker** prevents retry-storms during outages
- **Request Coalescing** reduces backend load during discovery
- **Connection state tracking** per interface
- **Graceful degradation** when backends unavailable
- **Recovery Coordinator** for connection recovery orchestration

### 8.5 Extensibility

- **DeviceProfileRegistry** for device-specific implementations
- **Composite protocols** with sub-protocols for narrower contracts
- **Event system** with typed events and priority levels
- **Handler pattern** for adding domain operations

### 8.6 Caching Strategy

- **Persistent caches**: DeviceDescription, ParamsetDescription (disk)
- **Dynamic caches**: CentralData, Command, PingPong (memory)
- **Visibility cache**: Parameter filtering rules
- **Age-based invalidation** and refresh policies
- **Typed entries**: CachedCommand, PongTracker dataclasses

### 8.7 Event-Driven Architecture

- **Modern EventBus** with type-safe events
- **14 event types** for comprehensive state notification
- **Handler priority levels**: CRITICAL, HIGH, NORMAL, LOW
- **Batch publishing** for efficient multi-event scenarios

---

## 9. Architecture Evaluation

### 9.1 Maturity Assessment

| Aspect        | Rating    | Notes                      |
| ------------- | --------- | -------------------------- |
| Decoupling    | Excellent | 104 protocols, 3-tier DI   |
| Type Safety   | Excellent | Full mypy strict mode      |
| Testability   | Excellent | Protocol-based mocking     |
| Resilience    | Excellent | CircuitBreaker, Recovery   |
| Performance   | Good      | Caching, coalescing, async |
| Extensibility | Excellent | Registry, handlers, events |
| Documentation | Good      | ADRs, architecture docs    |

### 9.2 Architectural Decisions (ADRs)

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
| 0009 | Interface Event Consolidation              | Accepted |

---

## 10. Pattern Summary

| Pattern                | Location                        | Benefit                            |
| ---------------------- | ------------------------------- | ---------------------------------- |
| **Facade**             | Device, Channel                 | Single protocol distribution point |
| **Factory**            | ClientFactoryProtocol, Registry | Flexible creation                  |
| **Observer**           | EventBus                        | Decoupled event handling           |
| **Strategy**           | 22 custom data point types      | Multiple implementations           |
| **Coordinator**        | 7 coordinators                  | Clear separation                   |
| **Circuit Breaker**    | client/circuit_breaker.py       | Resilience                         |
| **Request Coalescing** | client/request_coalescer.py     | Efficiency                         |
| **Handler**            | client/handlers/                | Domain separation                  |
| **DI (3-Tier)**        | All layers                      | Minimal coupling, type safety      |

---

## 11. Key Entry Points

```python
# Central configuration and orchestration
from aiohomematic.central import CentralConfig, CentralUnit

# Client configuration
from aiohomematic.client import InterfaceConfig, Interface

# Model classes
from aiohomematic.model import Device, Channel

# Protocol interfaces
from aiohomematic.interfaces import (
    CentralInfoProtocol,
    DeviceProtocol,
    CallbackDataPointProtocol,
    ClientFactoryProtocol,
)

# Store types
from aiohomematic.store.types import CachedCommand, PongTracker

# Resilience patterns
from aiohomematic.client.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from aiohomematic.client.request_coalescer import RequestCoalescer
```

---

## 12. Conclusion

**aiohomematic** demonstrates a mature, production-grade architecture:

- **Advanced 3-tier DI** with 104 protocols achieving complete decoupling
- **Modern Python patterns** (Protocol, dataclasses, async/await)
- **Full mypy strict mode** across 124 files / 49,401 LOC
- **Resilience patterns** (CircuitBreaker, RequestCoalescing, RecoveryCoordinator)
- **Multiple extension points** for device types and operations
- **Async-first** with strategic threading and synchronization
- **Well-documented decisions** via 9 ADRs
- **Clean store architecture** with typed dataclasses

The architecture successfully balances:

- **Flexibility** (protocols, factories, registries)
- **Safety** (type system, circuit breakers)
- **Performance** (caching, coalescing, async)
- **Maintainability** (clear boundaries, handlers, coordinators)
