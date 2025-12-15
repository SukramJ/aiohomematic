# ADR 0003: Explicit over Composite Protocol Injection

## Status

Accepted

## Context

With protocol-based dependency injection (ADR 0002), components receive multiple protocol interfaces. A question arose: should we group related protocols into composite interfaces to reduce constructor parameter count?

**Protocol usage analysis**:

| Component         | Protocol Count |
| ----------------- | -------------- |
| Device            | 16 protocols   |
| Hub               | 12 protocols   |
| DeviceCoordinator | 17 protocols   |
| HubCoordinator    | 10 protocols   |
| CacheCoordinator  | 7 protocols    |

**Common protocol groups identified**:

1. **Core** (all components): `central_info`, `config_provider`, `task_scheduler`
2. **Events** (Device, Hub, coordinators): `event_bus_provider`, `event_publisher`
3. **Visibility** (Device, Hub, coordinators): `parameter_visibility_provider`, `paramset_description_provider`

## Decision

Use **explicit protocol injection** per component rather than grouping protocols into composite interfaces for internal components.

### Exception: ClientDependencies

`ClientDependencies` exists as a composite protocol for the **external client API**, where a stable public interface is valuable. This is the exception, not the rule.

```python
# ClientDependenciesProtocol bundles ~20 methods for external API stability
@runtime_checkable
class ClientDependenciesProtocol(Protocol):
    @property
    def config(self) -> CentralConfig: ...
    @property
    def connection_state(self) -> CentralConnectionState: ...
    # ... stable public contract
```

### Internal Components: Explicit Injection

```python
# Device uses explicit injection (16 parameters)
class Device:
    def __init__(
        self,
        *,
        interface_id: str,
        device_address: str,
        central_info: CentralInfoProtocol,
        config_provider: ConfigProviderProtocol,
        event_bus_provider: EventBusProviderProtocol,
        # ... each dependency explicit
    ) -> None:
        ...
```

**Note**: All protocol interfaces use the `-Protocol` suffix (added 2025-12) to prevent name collisions with implementing classes and make protocols instantly recognizable.

## Consequences

### Advantages

- **Explicitness**: Constructor signature documents exactly what a component needs
- **Testability**: Tests can provide minimal implementations for only required protocols
- **No hidden dependencies**: No need to inspect composite definitions
- **Flexibility**: Each component declares precisely what it requires

### Disadvantages

- **Verbose constructors**: Some components have 10-17 parameters
- **Repetitive declarations**: Common protocols repeated across components

### Why Not Composite Protocols for Internal Components

1. **Hidden dependencies are an anti-pattern**: With explicit injection, dependencies are visible at a glance
2. **No significant testing benefit**: Explicit protocols already enable focused mocking
3. **Marginal readability improvement**: Modern IDEs handle long parameter lists well
4. **Maintenance overhead**: Composite protocols add another layer of types to synchronize

## Alternatives Considered

### 1. DeviceDependencies Composite Protocol

**Rejected**: Would hide 16 dependencies in a single parameter. Trades explicitness for brevity without clear benefit.

### 2. Grouped Composite Protocols (CoreDependencies, EventDependencies, etc.)

**Rejected**: Adds maintenance overhead. Components would need to understand multiple composite definitions instead of individual protocols.

### 3. Builder Pattern for Complex Objects

**Rejected**: More complex than explicit injection. Would require additional classes and methods.

## References

- `aiohomematic/interfaces/client.py` - ClientDependencies (the exception)
- `aiohomematic/model/device.py` - Device with explicit injection
- `docs/architecture.md` - "Protocol Injection: Explicit over Composite" section

---

_Created: 2025-12-10_
_Author: Architecture Review_
