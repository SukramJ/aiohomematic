# ADR 0010: Protocol Combination Analysis

## Status

Accepted (No changes recommended)

## Context

A review of the architecture (2025-12-27) raised the question whether some of the 104 protocol interfaces could be combined without compromising testability. This ADR documents the analysis.

### Current Protocol Usage

**Device class** - 16 protocol parameters:

| Protocol                            | Implementer              | Purpose                    |
| ----------------------------------- | ------------------------ | -------------------------- |
| CentralInfoProtocol                 | CentralUnit              | System identification      |
| ChannelLookupProtocol               | CentralUnit              | Channel lookup             |
| ClientProviderProtocol              | CentralUnit              | Client access              |
| ConfigProviderProtocol              | CentralUnit              | Configuration              |
| DataCacheProviderProtocol           | CentralDataCache         | Value cache                |
| DataPointProviderProtocol           | CentralUnit              | DataPoint lookup           |
| DeviceDescriptionProviderProtocol   | DeviceDescriptionCache   | Technical descriptions     |
| DeviceDetailsProviderProtocol       | DeviceDescriptionCache   | UI metadata (names, rooms) |
| EventBusProviderProtocol            | CentralUnit              | Event bus access           |
| EventPublisherProtocol              | EventCoordinator         | Event publishing           |
| EventSubscriptionManagerProtocol    | EventCoordinator         | Subscription management    |
| FileOperationsProtocol              | CentralUnit              | File I/O                   |
| FirmwareDataRefresherProtocol       | DeviceCoordinator        | Firmware refresh           |
| ParameterVisibilityProviderProtocol | ParameterVisibilityCache | Visibility rules           |
| ParamsetDescriptionProviderProtocol | ParamsetDescriptionCache | Parameter metadata         |
| TaskSchedulerProtocol               | Looper                   | Task scheduling            |

**DeviceCoordinator** - 15 protocol parameters (nearly identical to Device)

## Analysis

### Candidate Combinations Evaluated

#### 1. DeviceDescriptionProviderProtocol + DeviceDetailsProviderProtocol

**Rationale**: Both implemented by `DeviceDescriptionCache`.

```python
# Could become:
@runtime_checkable
class DeviceMetadataProviderProtocol(Protocol):
    # From DeviceDescriptionProviderProtocol
    def get_device_description(self, *, interface_id: str, address: str) -> DeviceDescription: ...
    def get_device_with_channels(self, *, interface_id: str, device_address: str) -> Mapping[str, DeviceDescription]: ...

    # From DeviceDetailsProviderProtocol
    def get_address_id(self, *, address: str) -> int: ...
    def get_channel_rooms(self, *, channel_address: str) -> set[str]: ...
    def get_device_rooms(self, *, device_address: str) -> set[str]: ...
    def get_function_text(self, *, address: str) -> str | None: ...
    def get_interface(self, *, address: str) -> Interface: ...
    def get_name(self, *, address: str) -> str | None: ...
```

**Assessment**: POSSIBLE but NOT RECOMMENDED

- **Pro**: Same implementer, logically related
- **Con**: Different abstraction levels (technical vs. UI metadata)
- **Con**: Would force consumers to depend on methods they don't use
- **Impact**: Saves 1 parameter per usage

#### 2. EventBusProviderProtocol + EventPublisherProtocol + EventSubscriptionManagerProtocol

**Rationale**: All event-related.

**Assessment**: NOT RECOMMENDED

- **Con**: Different implementers (CentralUnit vs. EventCoordinator)
- **Con**: Violates Single Responsibility Principle
- **Con**: Would require EventCoordinator to implement event bus access

#### 3. ParamsetDescriptionProviderProtocol + ParameterVisibilityProviderProtocol

**Rationale**: Both parameter-related.

**Assessment**: NOT RECOMMENDED

- **Con**: Completely different implementers (ParamsetDescriptionCache vs. ParameterVisibilityCache)
- **Con**: No real cohesion - one is metadata, other is filtering rules
- **Con**: Would require one cache to know about the other

#### 4. CentralInfoProtocol + ConfigProviderProtocol

**Rationale**: Both provide "meta-information".

**Assessment**: POSSIBLE but MARGINAL

- **Pro**: Both implemented by CentralUnit
- **Pro**: Conceptually related (identity + configuration)
- **Con**: CentralInfo is runtime state, ConfigProvider is static configuration
- **Impact**: Saves 1 parameter per usage

#### 5. Core Triple: CentralInfoProtocol + ConfigProviderProtocol + TaskSchedulerProtocol

**Rationale**: Used together in almost every component.

**Assessment**: NOT RECOMMENDED

- **Con**: TaskSchedulerProtocol implemented by Looper, not CentralUnit
- **Con**: Would hide important dependency on scheduling infrastructure

### Pattern Analysis

Components using many protocols:

| Component         | Protocol Count | Notes                                        |
| ----------------- | -------------- | -------------------------------------------- |
| Device            | 16             | Model layer, needs fine-grained access       |
| DeviceCoordinator | 15             | Constructs devices, passes protocols through |
| HubCoordinator    | 11             | Hub entity management                        |
| ClientCoordinator | 6              | Client lifecycle                             |
| EventCoordinator  | 4              | Event handling                               |
| DeviceRegistry    | 2              | Minimal, only needs lookup                   |

**Observation**: The high protocol count in Device and DeviceCoordinator is intentional - they are integration points that need access to many subsystems.

## Decision

**Keep the current protocol granularity.** No combinations recommended.

### Rationale

1. **ADR-0003 applies**: The explicit protocol injection pattern was deliberately chosen. Combining protocols would violate this decision.

2. **Different implementers**: Most candidate combinations involve protocols implemented by different classes:

   - Combining them would require artificial inheritance or delegation
   - Would make testing harder, not easier

3. **Testability preserved**: Current granularity enables precise mocking:

   ```python
   # Easy to mock exactly what's needed
   mock_device_details = Mock(spec=DeviceDetailsProviderProtocol)
   mock_device_details.get_name.return_value = "Test Device"

   # vs. having to mock a combined interface
   mock_metadata = Mock(spec=DeviceMetadataProviderProtocol)
   mock_metadata.get_name.return_value = "Test Device"
   mock_metadata.get_device_description.return_value = {...}  # Also needed
   ```

4. **Single Responsibility**: Each protocol has one clear purpose. Combinations would create "god protocols".

5. **Marginal benefit**: Best-case savings would be 2-3 parameters in Device/DeviceCoordinator. The cost (reduced clarity, harder testing) outweighs this.

### Alternative Considered: Parameter Object Pattern

Instead of combining protocols, could use a `DeviceDependencies` parameter object:

```python
@dataclass
class DeviceDependencies:
    central_info: CentralInfoProtocol
    config_provider: ConfigProviderProtocol
    # ... 14 more

class Device:
    def __init__(self, *, deps: DeviceDependencies) -> None:
        ...
```

**Rejected**: This hides dependencies in a single parameter, making the constructor signature shorter but dependencies less visible. This contradicts ADR-0003's core principle.

## Consequences

### Positive

- Maintains explicit dependency visibility
- Preserves fine-grained testability
- Consistent with ADR-0003
- No migration effort

### Negative

- Long constructor signatures remain (16 parameters for Device)
- Newcomers may find it overwhelming initially

### Mitigation

- Clear documentation in CLAUDE.md
- IDE support handles long parameter lists well
- Protocol names are self-documenting

## Metrics

| Metric                                     | Value                             |
| ------------------------------------------ | --------------------------------- |
| Total protocols analyzed                   | 16 (Device class)                 |
| Candidate combinations evaluated           | 5                                 |
| Combinations recommended                   | 0                                 |
| Protocols that could theoretically combine | 4 (2 pairs with same implementer) |
| Estimated parameter reduction              | 2 per Device (from 16 to 14)      |
| Testability impact                         | Negative if combined              |

## Related

- [ADR-0002: Protocol-Based Dependency Injection](0002-protocol-based-dependency-injection.md)
- [ADR-0003: Explicit over Composite Protocol Injection](0003-explicit-over-composite-protocol-injection.md)
- [Architecture Review 2025-12](../architecture_review_2025_12.md)

---

_Created: 2025-12-27_
_Author: Architecture Analysis_
