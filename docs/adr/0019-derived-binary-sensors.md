# ADR 0019: Derived Binary Sensors from Enum Data Points

## Status

Proposed (2026-01-28)

---

## Context

### Problem

Some Homematic devices expose enum parameters that are correctly displayed as enum sensors in Home Assistant. However, for certain use cases it would be beneficial to additionally expose these as binary sensors with configurable mapping rules.

**Example 1: HmIP-SRH (Window Handle Sensor)**

| Parameter | Enum Values                | Current HA Entity |
| --------- | -------------------------- | ----------------- |
| STATE     | `CLOSED`, `TILTED`, `OPEN` | Enum sensor       |

**Desired Additional Entity**: Binary sensor where:

- `OFF` when `STATE == CLOSED`
- `ON` when `STATE == TILTED` or `STATE == OPEN`

**Example 2: HmIP-SWSD (Smoke Detector)**

| Parameter                   | Enum Values                       | Current HA Entity |
| --------------------------- | --------------------------------- | ----------------- |
| SMOKE_DETECTOR_ALARM_STATUS | `IDLE_OFF`, `PRIMARY_ALARM`, etc. | Enum sensor       |

**Desired Additional Entity**: Binary sensor where:

- `OFF` when `SMOKE_DETECTOR_ALARM_STATUS == IDLE_OFF`
- `ON` for all other alarm states

### Current State

The existing `CustomDpIpSirenSmoke` class already implements a similar pattern using an `is_on` property:

```python
# In aiohomematic/model/custom/siren.py
@state_property
def is_on(self) -> bool | None:
    """Return if siren is on."""
    return bool(self._dp_smoke_detector_alarm_status.value != _SMOKE_DETECTOR_ALARM_STATUS_IDLE_OFF)
```

However, this approach:

1. Requires a full custom data point class for each device
2. Does not expose a separate binary sensor entity in Home Assistant
3. Is not declarative or reusable

### Requirements

1. **Code-Based Definition**: Mapping rules must be defined in code (not user-configurable)
2. **Declarative**: Similar to the existing `DeviceProfileRegistry` pattern
3. **Flexible Mapping**: Support for mapping multiple enum values to ON or OFF states
4. **Device Identification**: Rule and entity is only created for specific device models
5. **Coexistence**: Both the original enum sensor and the derived binary sensor must exist
6. **Event Propagation**: Updates to the source enum must trigger updates on the derived binary sensor

---

## Decision

Implement a **Derived Binary Sensor** system using the existing **Calculated Data Point** pattern with a specialized registry for enum-to-binary mappings.

### Key Principles

1. **Reuse Existing Infrastructure**: Build on `CalculatedDataPoint` base class
2. **Declarative Registration**: Define mappings via a registry similar to `DeviceProfileRegistry`
3. **Single Source of Truth**: Derived binary sensor subscribes to source enum data point
4. **No Custom Classes Per Device**: Generic `DerivedBinarySensor` class with data-driven mappings

---

## Architecture

### Data Flow

```
┌─────────────────────────────────────┐
│ CCU Backend                         │
└──────────────┬──────────────────────┘
               │ EVENT: STATE = "TILTED"
               ↓
┌─────────────────────────────────────┐
│ Generic Data Point (DpSelect)       │
│ Parameter: STATE                    │
│ Value: "TILTED"                     │
└──────────────┬──────────────────────┘
               │ subscribe_to_internal_data_point_updated
               ↓
┌─────────────────────────────────────┐
│ DerivedBinarySensor                 │
│ (CalculatedDataPoint subclass)      │
│                                     │
│ Mapping: ON = {"TILTED", "OPEN"}    │
│ Value: True (ON)                    │
└─────────────────────────────────────┘
               │ publish_data_point_updated_event
               ↓
┌─────────────────────────────────────┐
│ Home Assistant Binary Sensor        │
│ State: ON                           │
└─────────────────────────────────────┘
```

### Registry Structure

A new registry for derived binary sensor definitions:

```python
# aiohomematic/model/calculated/derived_binary_sensor.py

@dataclass(frozen=True, kw_only=True, slots=True)
class DerivedBinarySensorMapping:
    """Definition of a derived binary sensor mapping rule."""

    model: str | tuple[str, ...]  # Device model(s) this applies to
    source_parameter: Parameter   # Source enum parameter
    source_channel_no: int        # Channel where source parameter lives
    on_values: frozenset[str]     # Enum values that map to ON (binary True)
    off_values: frozenset[str] | None = None  # Optional: explicit OFF values
                                              # If None: all values not in on_values
    calculated_parameter: CalculatedParameter  # Unique identifier for derived DP


# Registration API
class DerivedBinarySensorRegistry:
    """Registry for derived binary sensor mappings."""

    @classmethod
    def register(
        cls,
        *,
        model: str | tuple[str, ...],
        source_parameter: Parameter,
        source_channel_no: int,
        on_values: frozenset[str],
        calculated_parameter: CalculatedParameter,
        off_values: frozenset[str] | None = None,
    ) -> None:
        """Register a derived binary sensor mapping."""
        ...

    @classmethod
    def get_mappings_for_model(cls, *, model: str) -> tuple[DerivedBinarySensorMapping, ...]:
        """Return all derived binary sensor mappings for a device model."""
        ...
```

### Example Registrations

```python
# In aiohomematic/model/calculated/derived_binary_sensor.py

# HmIP-SRH: Window Handle Sensor → Window Open Binary Sensor
DerivedBinarySensorRegistry.register(
    model="HmIP-SRH",
    source_parameter=Parameter.STATE,
    source_channel_no=1,
    on_values=frozenset({"TILTED", "OPEN"}),
    calculated_parameter=CalculatedParameter.WINDOW_OPEN,
)

# HmIP-SWSD: Smoke Detector → Smoke Alarm Binary Sensor
DerivedBinarySensorRegistry.register(
    model="HmIP-SWSD",
    source_parameter=Parameter.SMOKE_DETECTOR_ALARM_STATUS,
    source_channel_no=1,
    on_values=frozenset({"PRIMARY_ALARM", "INTRUSION_ALARM", "SECONDARY_ALARM"}),
    calculated_parameter=CalculatedParameter.SMOKE_ALARM,
)
```

### Generic Implementation Class

```python
class DerivedBinarySensor(CalculatedDataPoint[bool | None]):
    """
    Calculated binary sensor derived from an enum data point.

    This class implements a generic derived binary sensor that maps
    enum values to boolean states based on declarative mapping rules.
    """

    __slots__ = ("_mapping", "_dp_source")

    _category = DataPointCategory.BINARY_SENSOR

    def __init__(
        self,
        *,
        channel: ChannelProtocol,
        mapping: DerivedBinarySensorMapping,
    ) -> None:
        """Initialize the derived binary sensor."""
        self._mapping: Final = mapping
        self._calculated_parameter = mapping.calculated_parameter
        super().__init__(channel=channel)
        self._type = ParameterType.BOOL

        # Resolve source data point
        self._dp_source = self._add_data_point(
            parameter=mapping.source_parameter,
            paramset_key=ParamsetKey.VALUES,
            dpt=DpSelect,
        )

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if any derived binary sensor is relevant for this channel."""
        # Delegated to factory - this method checks individual mappings
        return False  # Factory handles relevance

    @staticmethod
    def is_relevant_for_mapping(
        *,
        channel: ChannelProtocol,
        mapping: DerivedBinarySensorMapping,
    ) -> bool:
        """Return if a specific mapping is relevant for this channel."""
        # Check model match
        if isinstance(mapping.model, tuple):
            if not element_matches_key(search_elements=mapping.model, compare_with=channel.device.model):
                return False
        elif not element_matches_key(search_elements=(mapping.model,), compare_with=channel.device.model):
            return False

        # Check channel match
        if channel.no != mapping.source_channel_no:
            return False

        # Check source parameter exists
        return channel.get_generic_data_point(
            parameter=mapping.source_parameter,
            paramset_key=ParamsetKey.VALUES,
        ) is not None

    @state_property
    def value(self) -> bool | None:
        """Return the derived binary value."""
        if (source_value := self._dp_source.value) is None:
            return None
        return source_value in self._mapping.on_values
```

### Factory Integration

The factory for creating derived binary sensors integrates with the existing device initialization flow:

```python
# In aiohomematic/model/calculated/__init__.py

def create_derived_binary_sensors(
    *,
    channel: ChannelProtocol,
) -> tuple[DerivedBinarySensor, ...]:
    """Create all relevant derived binary sensors for a channel."""
    derived_sensors: list[DerivedBinarySensor] = []

    for mapping in DerivedBinarySensorRegistry.get_mappings_for_model(model=channel.device.model):
        if DerivedBinarySensor.is_relevant_for_mapping(channel=channel, mapping=mapping):
            derived_sensors.append(
                DerivedBinarySensor(channel=channel, mapping=mapping)
            )

    return tuple(derived_sensors)
```

### New Calculated Parameters

Add new calculated parameters for derived binary sensors:

```python
# In aiohomematic/const.py

class CalculatedParameter(StrEnum):
    """Enum with calculated Homematic parameters."""

    # Existing
    APPARENT_TEMPERATURE = "APPARENT_TEMPERATURE"
    DEW_POINT = "DEW_POINT"
    DEW_POINT_SPREAD = "DEW_POINT_SPREAD"
    ENTHALPY = "ENTHALPY"
    FROST_POINT = "FROST_POINT"
    OPERATING_VOLTAGE_LEVEL = "OPERATING_VOLTAGE_LEVEL"
    VAPOR_CONCENTRATION = "VAPOR_CONCENTRATION"

    # New: Derived binary sensors
    SMOKE_ALARM = "SMOKE_ALARM"
    WINDOW_OPEN = "WINDOW_OPEN"
    # Future: Add more as needed
```

---

## Consequences

### Positive

- **Declarative**: Mapping rules are data, not code - easy to add new device support
- **Reusable**: Single implementation class serves all derived binary sensors
- **Consistent**: Uses existing calculated data point infrastructure
- **Maintainable**: New device mappings require only registry entries
- **Type-Safe**: Full mypy support through existing patterns
- **Event-Driven**: Automatic update propagation via existing subscription mechanism
- **No HA Changes**: Works with existing Home Assistant binary_sensor platform

### Negative

- **Additional Entities**: Each derived sensor is a separate entity in HA
- **Enum Values Coupling**: Mapping rules must match exact CCU enum value strings
- **Calculated Parameter Growth**: Each unique derived sensor type needs a new enum value

### Risks and Mitigations

| Risk                         | Mitigation                                               |
| ---------------------------- | -------------------------------------------------------- |
| Enum values vary by firmware | Document CCU firmware version requirements per mapping   |
| Duplicate entities           | Clear naming via calculated_parameter for disambiguation |
| Stale mappings               | Unit tests verify all registered source parameters exist |
| Performance overhead         | Minimal: one additional subscription per derived sensor  |

---

## Alternatives Considered

### Alternative 1: Extend Custom Data Points

Add derived binary sensors as additional properties on existing custom data point classes.

**Rejected**:

- Requires custom class per device (more code)
- Does not create separate HA entity (property, not entity)
- Not declarative

### Alternative 2: Home Assistant Template Sensors

Let users create template binary sensors in HA configuration.

**Rejected**:

- User configuration burden
- Not discoverable
- Inconsistent across installations

### Alternative 3: Visibility Rules with Device Class Override

Use visibility rules to create binary sensor variants of enum sensors.

**Rejected**:

- Visibility rules control exposure, not transformation
- Would require fundamental changes to data point typing
- Conflates filtering with transformation

### Alternative 4: Generic Calculated Data Point with External Config

Make mappings configurable via YAML or JSON file.

**Rejected**:

- Adds configuration complexity
- External file management
- Harder to validate at startup
- Against requirement "only in code"

---

## Implementation

**Status:** Proposed (NOT yet implemented)

**When Implemented:**

**New Files:**

- `aiohomematic/model/calculated/derived_binary_sensor.py` - Registry, mapping dataclass, and implementation class

**Modified Files:**

- `aiohomematic/const.py` - Add new `CalculatedParameter` enum values
- `aiohomematic/model/calculated/__init__.py` - Re-export and factory integration
- `aiohomematic/model/device.py` - Call factory during device initialization

**Key Components:**

- `DerivedBinarySensorMapping` - Declarative mapping definition
- `DerivedBinarySensorRegistry` - Central registry for mappings
- `DerivedBinarySensor` - Generic calculated data point implementation
- `create_derived_binary_sensors()` - Factory function

**Testing:**

- Unit tests for registry lookup (exact match, prefix match)
- Unit tests for value mapping (ON values, OFF values, None handling)
- Unit tests for `is_relevant_for_mapping()` logic
- Integration tests with HmIP-SRH and HmIP-SWSD devices
- Tests verifying event propagation from source to derived sensor

---

## Adding New Derived Binary Sensors

To add support for a new device/parameter combination:

1. **Identify the source parameter and its enum values**

   ```bash
   # Check paramset description for the device
   grep -r "PARAMETER_NAME" tests/fixtures/
   ```

2. **Add CalculatedParameter enum value** (if new sensor type):

   ```python
   # In aiohomematic/const.py
   class CalculatedParameter(StrEnum):
       MY_NEW_SENSOR = "MY_NEW_SENSOR"
   ```

3. **Register the mapping**:

   ```python
   # In aiohomematic/model/calculated/derived_binary_sensor.py
   DerivedBinarySensorRegistry.register(
       model="HmIP-XYZ",
       source_parameter=Parameter.MY_ENUM_PARAM,
       source_channel_no=1,
       on_values=frozenset({"VALUE_A", "VALUE_B"}),
       calculated_parameter=CalculatedParameter.MY_NEW_SENSOR,
   )
   ```

4. **Add tests**:

   ```python
   # In tests/test_model_calculated_derived_binary_sensor.py
   async def test_my_new_sensor_mapping(...) -> None:
       ...
   ```

5. **Update changelog**

---

## References

- [CalculatedDataPoint Implementation](https://github.com/sukramj/aiohomematic/blob/devel/aiohomematic/model/calculated/data_point.py) - Base class for calculated data points
- [OperatingVoltageLevel](https://github.com/sukramj/aiohomematic/blob/devel/aiohomematic/model/calculated/operating_voltage_level.py) - Example calculated data point
- [DeviceProfileRegistry](https://github.com/sukramj/aiohomematic/blob/devel/aiohomematic/model/custom/registry.py) - Similar registry pattern
- [CustomDpIpSirenSmoke](https://github.com/sukramj/aiohomematic/blob/devel/aiohomematic/model/custom/siren.py) - Current workaround with `is_on` property
- [HmIP-SRH Documentation](../user/devices/hmip_srh_window_handle.md) - Window handle sensor
- [HmIP-SWSD Documentation](../user/devices/hmip_swsd_smoke_detector.md) - Smoke detector

---

_Created: 2026-01-28_
_Author: Architecture Review_
