# ADR 0007: Device Slots Reduction via Composition - Rejected

## Status

Rejected

## Context

The `Device` class has approximately 31 `__slots__` entries. A proposal was made to reduce this by grouping related fields into internal dataclasses:

```python
# Proposed change
@dataclass(frozen=True, slots=True)
class _DeviceMetadata:
    model: str
    sub_model: str | None
    manufacturer: Manufacturer
    product_group: ProductGroup
    rx_modes: tuple[RxMode, ...]
    # ... more fields

@dataclass(slots=True)
class _DeviceState:
    modified_at: datetime
    forced_availability: ForcedDeviceAvailability

class Device:
    __slots__ = (
        "_address",
        "_metadata",  # Replaces 8 individual slots
        "_state",     # Replaces 2 individual slots
        # ...
    )
```

The goal was to improve code organization and reduce the apparent complexity of the Device class.

## Decision

**Reject this proposal.** Keep the current flat `__slots__` structure.

## Rationale

### 1. Performance Overhead

Additional indirection on every property access:

```python
# Current (direct access)
return self._model  # 1 lookup

# With composition
return self._metadata.model  # 2 lookups
```

For frequently accessed properties like `model`, `address`, `interface`, this adds measurable overhead in hot paths.

### 2. Memory Overhead

Each dataclass instance requires its own object header:

```python
# With 100 devices:

# Current: 100 Device instances
# Memory: ~100 * (base + 31 * 8 bytes) ≈ 25KB

# With composition: 100 Devices + 200-300 dataclass instances
# Memory: ~35KB + additional GC pressure
```

### 3. No Real Problem to Solve

- 31 slots is not unusual for a central domain class
- The slots are already logically grouped via comments in the source
- Device instances are created rarely (only during discovery)
- No measured performance or memory issues exist

### 4. The Real Problem Was Already Solved

The actual issue was the **large DeviceProtocol interface** (72 members), not the implementation. This was addressed by splitting DeviceProtocol into focused sub-protocols:

- DeviceIdentityProtocol
- DeviceChannelAccessProtocol
- DeviceAvailabilityProtocol
- DeviceFirmwareProtocol
- DeviceLinkManagementProtocol
- DeviceGroupManagementProtocol
- DeviceConfigurationProtocol
- DeviceWeekProfileProtocol
- DeviceProvidersProtocol
- DeviceLifecycleProtocol

Consumers now depend only on the sub-protocols they need, achieving the organizational benefits without implementation overhead.

### 5. Unnecessary Complexity

- More classes to understand and maintain
- All internal property accesses would need updating
- Risk of subtle bugs during migration
- No functional benefit to users

## Alternatives Considered

### Alternative 1: Partial Composition (Rejected)

Group only some fields (e.g., firmware-related) into dataclasses.

**Rejected because**: Inconsistent design - some fields composed, others not - would be confusing.

### Alternative 2: Named Tuples (Rejected)

Use named tuples instead of dataclasses for immutable groups.

**Rejected because**: Same overhead issues, plus less flexibility for mutable state.

### Alternative 3: Keep Current Design (Accepted)

Maintain the flat `__slots__` structure with clear comments for logical grouping.

**Accepted because**: Efficient, simple, and the interface complexity was solved at the protocol level.

## Consequences

### Positive

- No migration effort required
- No performance regression risk
- Simpler codebase with fewer classes
- Device implementation remains efficient

### Negative

- Device class source appears "large" (31 slots)
- New contributors may initially find it overwhelming

### Mitigation

- Clear comments in `__slots__` definition grouping related fields
- Documentation explaining the design decision
- Sub-protocols provide clean external API regardless of implementation

## Related

- Section 1.2 in `docs/architecture_improvements.md` (marked as Won't Implement)
- ADR 0002: Protocol-Based Dependency Injection
- DeviceProtocol sub-protocol split (implemented in 2025.12.18)
