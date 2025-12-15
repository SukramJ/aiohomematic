# ADR 0002: Protocol-Based Dependency Injection

## Status

Accepted

## Context

Components in aiohomematic need to access CentralUnit functionality without tight coupling. The codebase requires:

1. **Testability**: Components should be easily mockable for unit tests
2. **Decoupling**: Avoid circular dependencies and reduce coupling to CentralUnit
3. **Type Safety**: Maintain full type checking with mypy strict mode
4. **Flexibility**: Allow components to depend only on the functionality they need

## Decision

Use Python Protocol classes with `@runtime_checkable` for dependency injection across three tiers:

### Tier 1: Full DI (Infrastructure Layer)

Components receive only protocol interfaces with zero CentralUnit references:

```python
class CacheCoordinator:
    def __init__(
        self,
        *,
        central_info: CentralInfo,
        device_provider: DeviceProvider,
        client_provider: ClientProvider,
        # ... 5 more protocols
    ) -> None:
        self._central_info: Final = central_info
        # Zero references to CentralUnit
```

**Components**: CacheCoordinator, DeviceRegistry, ParameterVisibilityCache, EventCoordinator, DeviceCoordinator, BackgroundScheduler

### Tier 2: Full Protocol-Based DI (Coordinator Layer)

Components use protocol interfaces exclusively:

```python
class ClientCoordinator:
    def __init__(
        self,
        *,
        client_factory: ClientFactoryProtocol,  # Factory protocol
        central_info: CentralInfo,
        config_provider: ConfigProvider,
        # ...
    ) -> None:
        # All operations use protocol interfaces
```

**Components**: ClientCoordinator, HubCoordinator, Hub

### Tier 3: Full DI (Model Layer)

Model classes receive protocol interfaces:

```python
class Device:
    def __init__(
        self,
        *,
        interface_id: str,
        device_address: str,
        central_info: CentralInfo,
        event_bus_provider: EventBusProvider,
        # ... 14 more protocols
    ) -> None:
        self._central_info: Final = central_info
```

**Components**: Device, Channel, CallbackDataPoint, BaseDataPoint

### Protocol Interfaces

Defined in `aiohomematic/interfaces/`:

- **CentralInfo**: System identification (name, model, version)
- **ConfigProvider**: Configuration access
- **ClientFactoryProtocol**: Client instance creation
- **ClientProvider**: Client lookup by interface_id
- **EventBusProvider**: Event system access
- **TaskScheduler**: Background task scheduling
- **DeviceProvider**: Device registry access
- **DataPointProvider**: Data point lookup

CentralUnit implements all protocols via structural subtyping (no explicit inheritance).

## Consequences

### Advantages

- **Full structural subtyping support**: Python protocols work with duck typing
- **Excellent testability**: Mock only the protocols a component needs
- **Clear dependency contracts**: Constructor signature documents requirements
- **No framework dependency**: Pure Python, no DI container needed
- **IDE support**: Full autocomplete and type checking

### Disadvantages

- **Many protocol interfaces to maintain**: ~25 protocols across the codebase
- **Cognitive load for newcomers**: Need to understand protocol pattern
- **Verbose constructors**: Some components have 10+ parameters

### Trade-offs

The verbosity of explicit protocol injection is accepted because:

1. Dependencies are immediately visible in constructor signatures
2. Tests can mock exactly what they need
3. No hidden coupling through implicit dependencies

## Alternatives Considered

### 1. Abstract Base Classes

**Rejected**: Nominal typing requires explicit inheritance. Protocol's structural subtyping is more flexible.

### 2. Duck Typing Without Protocols

**Rejected**: No type safety. mypy strict mode requires typed interfaces.

### 3. Dependency Injection Framework (e.g., dependency-injector)

**Rejected**: External dependency, increased complexity, less explicit than constructor injection.

### 4. Service Locator Pattern

**Rejected**: Hidden dependencies, harder to test, anti-pattern for explicit dependency management.

## References

- `aiohomematic/interfaces/` - Protocol definitions
- `docs/architecture.md` - Dependency Injection Architecture section
- [PEP 544 - Protocols: Structural subtyping](https://peps.python.org/pep-0544/)

---

_Created: 2025-12-10_
_Author: Architecture Review_
