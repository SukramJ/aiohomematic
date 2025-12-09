# Architecture Analysis - aiohomematic

**Stand**: 2025-12-09
**Version**: 2025.11.16
**Python**: 3.13+

---

## Executive Summary

**aiohomematic** is a sophisticated async Python library for controlling Homematic and HomematicIP devices, architected with a three-tier dependency injection (DI) system using 60+ protocol interfaces. The codebase demonstrates advanced architectural patterns including Facade, Factory, Observer, and Protocol-based DI, totaling approximately 39,558 lines of code across 90 Python files.

---

## 1. Module Structure

### Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│         Home Assistant Integration / Consumer            │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  aiohomematic.central (~2,000 LOC)                       │
│  - CentralUnit: Main orchestrator                        │
│  - 6 Coordinators: Backend orchestration                │
│  - EventBus: Type-safe event system                     │
│  - RPC Server: XML-RPC callback server                  │
└──────────────────────┬──────────────────────────────────┘
          │
┌─────────┼────────────────┬────────────────────┬──────────┐
│         │                │                    │          │
├─────────▼──────┐  ┌──────▼────────┐  ┌───────▼────┐  ┌──▼──────────┐
│ .client        │  │ .model        │  │ .interfaces│  │ .store      │
│ (2,348 LOC)    │  │ (~10K LOC)    │  │ (4,020 LOC)│  │ (2,685 LOC) │
│                │  │               │  │            │  │             │
│ Adapters:      │  │ Entity Types: │  │ 60+ Proto: │  │ Caches:     │
│ - ClientCCU    │  │ - Generic     │  │ - Central  │  │ - Persistent│
│ - ClientJson   │  │ - Custom      │  │ - Client   │  │ - Dynamic   │
│ - Homegear     │  │ - Calculated  │  │ - Model    │  │ - Visibility│
└────────────────┘  │ - Hub         │  │ - Ops      │  │             │
                    └───────────────┘  └────────────┘  └─────────────┘
```

### Module Overview

| Module         | LOC     | Files | Responsibility                                                       |
| -------------- | ------- | ----- | -------------------------------------------------------------------- |
| **central**    | ~2,000  | 11    | Orchestration, client lifecycle, device registry, events, scheduling |
| **client**     | 2,347   | 4     | JSON-RPC/XML-RPC adapters, backend communication                     |
| **model**      | ~10,000 | 43    | Device/Channel/DataPoint classes, entity creation                    |
| **interfaces** | 4,020   | 6     | 60+ protocol definitions                                             |
| **store**      | 2,685   | 3     | Device descriptions, paramsets, caches, visibility rules             |

---

## 2. Three-Tier Dependency Injection

### Tier 1: Infrastructure Layer (Full DI)

Coordinators receive only protocol interfaces:

```python
class DeviceCoordinator:
    def __init__(
        self,
        *,
        central_info: CentralInfo,
        channel_lookup: ChannelLookup,
        client_provider: ClientProvider,
        config_provider: ConfigProvider,
        # ... 15+ protocol interfaces total
    ) -> None:
        # Zero references to CentralUnit
```

**Coordinators** (6 classes):

- `CacheCoordinator` - 8 protocols
- `ClientCoordinator` - 6 protocols
- `DeviceCoordinator` - 17 protocols
- `EventCoordinator` - 2 protocols
- `HubCoordinator` - 9+ protocols
- `RPC Server` - 2 protocols

### Tier 2: Coordinator Layer (Protocol-Based DI)

Coordinators compose via protocol interfaces:

```python
class ClientCoordinator:
    def __init__(
        self,
        *,
        client_factory: ClientFactory,
        central_info: CentralInfo,
        config_provider: ConfigProvider,
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
        # ... 12+ more protocols
    ) -> None:
```

**Channel & DataPoint** - Access protocols through parent Device.

---

## 3. Protocol Interface Taxonomy

**Total: 60 @runtime_checkable protocols**

### Central Protocols (20)

- Identity: `CentralInfo`, `CentralUnitStateProvider`, `ConfigProvider`
- Operations: `BackupProvider`, `EventBusProvider`, `EventPublisher`
- Data Access: `DataPointProvider`, `DeviceProvider`, `ChannelLookup`
- Hub: `HubFetchOperations`, `HubDataFetcher`, `HubDataPointManager`

### Client Protocols (18)

- `ClientProtocol` (60+ properties/methods)
- `ClientFactory`, `ClientProvider`, `ClientDependencies`
- `InterfaceEventPublisher`, `LastEventTracker`

### Model Protocols (16)

- DataPoint Hierarchy: `CallbackDataPointProtocol`, `GenericDataPointProtocol`, `CustomDataPointProtocol`, `CalculatedDataPointProtocol`
- Entity: `ChannelProtocol`, `DeviceProtocol`, `HubProtocol`

### Operations Protocols (5)

- `TaskScheduler`, `ParameterVisibilityProvider`
- `DeviceDetailsProvider`, `DeviceDescriptionProvider`, `ParamsetDescriptionProvider`

---

## 4. Key Design Patterns

### 4.1 Facade Pattern

**Device** aggregates 15+ protocol interfaces for DataPoints:

```python
class Device:
    """
    Facade aggregating 15+ protocol interfaces.

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

- **ClientFactory Protocol**: Creates client instances
- **DeviceProfileRegistry**: Device model -> CustomDataPoint mappings
- **Entity Creation Factory**: `create_data_points_and_events()`

### 4.3 Observer Pattern (EventBus)

```python
@dataclass(frozen=True, slots=True)
class DataPointUpdatedEvent(Event):
    timestamp: datetime
    dpk: DataPointKey
    value: ParamType

unsubscribe = event_bus.subscribe(
    event_type=DataPointUpdatedEvent,
    handler=on_update
)
```

### 4.4 Strategy Pattern (Entity Polymorphism)

- `GenericDataPoint` - Fallback entity
- `CustomDpIpThermostat`, `CustomDpIpCover`, etc. - Device-specific
- `CalculatedDataPoint` - Derived values
- `GenericHubDataPoint` - Hub programs/sysvars

### 4.5 Coordinator Pattern

| Coordinator       | Responsibility                      |
| ----------------- | ----------------------------------- |
| CacheCoordinator  | Device/paramset description caching |
| ClientCoordinator | Client creation, lifecycle          |
| DeviceCoordinator | Device creation, registration       |
| EventCoordinator  | Event routing, subscriptions        |
| HubCoordinator    | Hub entity management               |
| RPC Server        | XML-RPC callback server             |

---

## 5. Concurrency Model

### Async-First Architecture

- **asyncio**: Main event loop for all I/O
- **Looper**: Helper implementing `TaskScheduler` protocol
- **Background Scheduler**: Periodic tasks

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

### Threading

**RPC Server** runs in separate thread for XML-RPC callbacks.

---

## 6. Code Metrics

### Lines of Code Distribution

```
Total: ~39,558 LOC across 90 files

Top Modules:
1. client/__init__.py        2,347 LOC
2. central/__init__.py       1,988 LOC
3. model/device.py           1,887 LOC
4. client/json_rpc.py        1,887 LOC
5. interfaces/model.py       1,562 LOC
6. const.py                  1,540 LOC
```

### Protocol Statistics

- 60 Protocol Interfaces
- 100% @runtime_checkable
- CentralUnit implements all via structural subtyping

---

## 7. Architecture Strengths

1. **Decoupling**: 60 protocol interfaces eliminate circular dependencies
2. **Type Safety**: Full mypy strict mode compliance
3. **Testability**: Protocol-based DI enables comprehensive mocking
4. **Extensibility**: DeviceProfileRegistry for device-specific implementations
5. **Event-Driven**: Modern EventBus with type-safe events
6. **Caching**: Multiple strategies (persistent, dynamic, visibility)
7. **Concurrency Safety**: Strategic use of locks/semaphores

---

## 8. Pattern Summary

| Pattern         | Location                | Benefits                           |
| --------------- | ----------------------- | ---------------------------------- |
| **Facade**      | Device, Channel         | Single protocol distribution point |
| **Factory**     | ClientFactory, Registry | Flexible creation                  |
| **Observer**    | EventBus                | Decoupled event handling           |
| **Strategy**    | Entity types            | Multiple implementations           |
| **Coordinator** | 6 coordinators          | Clear separation                   |
| **DI (3-Tier)** | All layers              | Minimal coupling, full type safety |

---

## 9. Key Entry Points

```python
from aiohomematic.central import CentralConfig, CentralUnit
from aiohomematic.client import InterfaceConfig, Interface
from aiohomematic.model import Device, Channel
from aiohomematic.interfaces import (
    CentralInfo, DeviceProtocol, CallbackDataPointProtocol
)
```

---

## 10. Conclusion

**aiohomematic** demonstrates:

- Advanced three-tier DI with 60 protocols
- Modern Python patterns (Protocol, dataclasses, async/await)
- Full mypy strict mode across 90 files
- Multiple extension points for device types
- Async-first with strategic locking
- Production-grade architecture for Home Assistant integration
