# Extension points: New device profiles and calculated data points

This guide explains how to extend AioHomematic with:

- Custom device profiles (model/custom)
- Calculated (derived) data points (model/calculated)

It targets contributors who want to add support for new device variants or expose derived metrics that are not provided by the device firmware.

## Prerequisites and conventions

- Be familiar with the architecture overview in docs/architecture.md (Model, Device/Channel, DataPoint lifecycle).
- Prefer small, well-scoped additions. Follow existing naming conventions and module layout.
- Keep public API stable. New types should be added behind existing factory/registration functions.

---

## Custom device profiles (model/custom)

Custom device profiles are used when a specific device (model) requires a bespoke grouping of its generic data points or additional behavior beyond the generic defaults.

### Key modules and types:

- **aiohomematic.model.custom.registry**
  - `DeviceProfileRegistry`: Central registry for device-to-profile mappings
  - `DeviceConfig`: Type-safe configuration for device registration
  - `ExtendedDeviceConfig`: Extended configuration with additional fields
- **aiohomematic.model.custom.definition**
  - `make_custom_data_point(channel, data_point_class, device_profile, custom_config)`: Factory function
  - `is_multi_channel_device(model, category)`: Check for multi-channel devices
  - `get_custom_configs(model, category)`: Get configurations for a model
- **aiohomematic.model.custom.data_point.CustomDataPoint**: Base implementation that:
  - Groups multiple generic data points, sets visibility, service flags, etc.
  - Subscribes to underlying GenericDataPoint updates
  - Provides state_property values derived from the grouped set
- **aiohomematic.const**: Contains `Field`, `DeviceProfile`, and `CDPD` keys used in profile definitions

### Concepts:

- A CustomDataPoint instance sits on a Channel and aggregates underlying GenericDataPoints according to a device profile definition.
- Device profiles are declared in `model/custom/profile.py` as type-safe dataclasses.
- Device-to-profile mappings are registered via `DeviceProfileRegistry` in each entity module.

### When to create a custom device profile:

- Generic model would misrepresent or hide essential device semantics.
- You need to group multiple parameters across one or more channels into a single coherent data point.

### Steps to add a custom device profile:

1. **Choose or create a CustomDataPoint subclass** (optional)

   - Most cases can use an existing CustomDataPoint subclass (e.g., `CustomDpIpThermostat`, `CustomDpSwitch`).
   - If you need special behavior, subclass CustomDataPoint and override:
     - Use `DataPointField` descriptors for declarative field definitions
     - Override `_post_init()` for additional initialization after field resolution
     - `_readable_data_points` / `_relevant_data_points` (to tune exposure)
     - `state_property` getters if you compute an aggregate state

2. **Register the device with DeviceProfileRegistry**

   - In the appropriate entity module (e.g., `climate.py`, `switch.py`), add a registration call:

   ```python
   from aiohomematic.model.custom.registry import DeviceProfileRegistry, ExtendedDeviceConfig

   DeviceProfileRegistry.register(
       category=DataPointCategory.CLIMATE,
       models=("HmIP-NEW-DEVICE", "HmIP-NEW-DEVICE-2"),  # Device model(s)
       data_point_class=CustomDpIpThermostat,            # CustomDataPoint subclass
       profile_type=DeviceProfile.IP_THERMOSTAT,         # Profile type from const.py
       channels=(1,),                                     # Primary channel(s)
       schedule_channel_no=1,                             # Optional: schedule channel
       extended=ExtendedDeviceConfig(                     # Optional: extended config
           additional_data_points={
               0: (Parameter.SOME_PARAM,),
           },
       ),
   )
   ```

3. **For multiple configurations per device**, use `register_multiple`:

   ```python
   DeviceProfileRegistry.register_multiple(
       category=DataPointCategory.LOCK,
       models="HmIP-DLD",
       configs=(
           DeviceConfig(
               data_point_class=CustomDpIpLock,
               profile_type=DeviceProfile.IP_LOCK,
           ),
           DeviceConfig(
               data_point_class=CustomDpButtonLock,
               profile_type=DeviceProfile.IP_BUTTON_LOCK,
               channels=(0,),
           ),
       ),
   )
   ```

4. **Validate**
   - Run the project tests to ensure your device is correctly registered.
   - Add specific tests for your device if possible.

### Minimal example (adding a new switch device):

```python
# In aiohomematic/model/custom/switch.py

from aiohomematic.const import DataPointCategory, DeviceProfile
from aiohomematic.model.custom.registry import DeviceProfileRegistry

# Register the new device
DeviceProfileRegistry.register(
    category=DataPointCategory.SWITCH,
    models="HmIP-MY-NEW-SWITCH",
    data_point_class=CustomDpSwitch,
    profile_type=DeviceProfile.IP_SWITCH,
    channels=(3,),  # Channel number where STATE parameter lives
)
```

### Tips:

- Look at existing registrations in `climate.py`, `switch.py`, `cover.py`, etc. for patterns.
- Use `ExtendedDeviceConfig` when you need additional data points beyond the profile defaults.
- For multi-channel devices, specify all relevant channels in the `channels` tuple.
- To blacklist a device model, use `DeviceProfileRegistry.blacklist("MODEL-NAME")`.

---

## Calculated (derived) data points (model/calculated)

Calculated data points compute values from one or more underlying GenericDataPoints and behave like read-only data points on a Channel.

### Key modules and types:

- **aiohomematic.model.calculated.field.CalculatedDataPointField**: Descriptor for declarative field definitions
  - `parameter`: The parameter name to resolve
  - `paramset_key`: The paramset key (VALUES, MASTER, etc.)
  - `dpt`: Expected data point type (e.g., DpSensor, DpFloat)
  - `fallback_parameters`: Optional list of fallback parameter names
  - `use_device_fallback`: If True, tries device address (channel 0) if not found
- **aiohomematic.model.calculated.data_point.CalculatedDataPoint**: Base class to inherit from
  - `_resolve_data_point(...)` / `_add_device_data_point(...)` for manual data point resolution
  - `publish_data_point_updated_event` is triggered when any source updates
  - Decorators: @state_property, @config_property
- **aiohomematic.model.calculated.\_\_init\_\_**
  - `create_calculated_data_points(channel)`: factory that evaluates relevance and attaches instances to channels
  - `_CALCULATED_DATA_POINTS`: tuple of registered calculated DP classes
- Existing implementations for reference:
  - climate.py: ApparentTemperature, DewPoint, FrostPoint, VaporConcentration
  - operating_voltage_level.py: OperatingVoltageLevel

### Lifecycle:

- On channel initialization, `create_calculated_data_points(channel)` iterates all registered classes, calls `Class.is_relevant_for_model(channel)` and adds instances for those that apply.
- Each CalculatedDataPoint uses `CalculatedDataPointField` descriptors for lazy data point resolution with automatic subscription handling.
- When any source data point updates, the calculated data point's value is recomputed.

### Steps to add a new calculated data point:

1. **Implement a subclass of CalculatedDataPoint**

   - Set `_calculated_parameter` to a value from `aiohomematic.const.CalculatedParameter`
   - Use `CalculatedDataPointField` descriptors to declare source data points:
     ```python
     _dp_temp = CalculatedDataPointField(
         parameter=Parameter.TEMPERATURE,
         paramset_key=ParamsetKey.VALUES,
         dpt=DpSensor,
     )
     ```
   - For fallback parameters (try alternatives if primary not found):
     ```python
     _dp_temp = CalculatedDataPointField(
         parameter=Parameter.TEMPERATURE,
         paramset_key=ParamsetKey.VALUES,
         dpt=DpSensor,
         fallback_parameters=[Parameter.ACTUAL_TEMPERATURE],
     )
     ```
   - For device-level fallback (try device address if not on channel):
     ```python
     _dp_limit = CalculatedDataPointField(
         parameter=Parameter.LOW_BAT_LIMIT,
         paramset_key=ParamsetKey.MASTER,
         dpt=DpFloat,
         use_device_fallback=True,
     )
     ```
   - Provide properties using decorators:
     - `@state_property def value(self) -> T:` return computed value
     - `@config_property def unit(self) -> str | None:` return unit string
   - Implement `staticmethod is_relevant_for_model(*, channel: ChannelProtocol) -> bool` to guard which channels get this DP
   - Override `_post_init()` for additional initialization after descriptor resolution

2. **Register your class**

   - Add the class to `_CALCULATED_DATA_POINTS` in `aiohomematic.model.calculated.__init__`:
     ```python
     _CALCULATED_DATA_POINTS = (ApparentTemperature, ..., YourNewCalculatedDP)
     ```

3. **Ensure correctness**
   - The base class manages subscriptions automatically via descriptors
   - Use helper functions in `aiohomematic.model.calculated.support` for common calculations

### Minimal template:

```python
# aiohomematic/model/calculated/my_metric.py
from __future__ import annotations

from aiohomematic.const import CalculatedParameter, Parameter, ParameterType, ParamsetKey
from aiohomematic.interfaces.model import ChannelProtocol
from aiohomematic.model.calculated.data_point import CalculatedDataPoint
from aiohomematic.model.calculated.field import CalculatedDataPointField
from aiohomematic.model.generic import DpSensor
from aiohomematic.property_decorators import state_property


class MyMetric(CalculatedDataPoint[float | None]):
    """Calculate a custom metric from temperature and humidity."""

    __slots__ = ()

    _calculated_parameter = CalculatedParameter.MY_METRIC

    # Declarative field definitions using descriptors
    _dp_temp = CalculatedDataPointField(
        parameter=Parameter.TEMPERATURE,
        paramset_key=ParamsetKey.VALUES,
        dpt=DpSensor,
    )
    _dp_hum = CalculatedDataPointField(
        parameter=Parameter.HUMIDITY,
        paramset_key=ParamsetKey.VALUES,
        dpt=DpSensor,
    )

    def __init__(self, *, channel: ChannelProtocol) -> None:
        """Initialize the data point."""
        super().__init__(channel=channel)
        self._type = ParameterType.FLOAT
        self._unit = "unit"

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        """Return if this calculated data point is relevant for the model."""
        return (
            channel.get_generic_data_point(
                parameter=Parameter.TEMPERATURE, paramset_key=ParamsetKey.VALUES
            )
            is not None
            and channel.get_generic_data_point(
                parameter=Parameter.HUMIDITY, paramset_key=ParamsetKey.VALUES
            )
            is not None
        )

    @state_property
    def value(self) -> float | None:
        """Return the calculated value."""
        if self._dp_temp.value is None or self._dp_hum.value is None:
            return None
        # Implement your calculation here
        return (self._dp_temp.value + self._dp_hum.value) / 2
```

### Notes:

- Use `use_device_fallback=True` or `_add_device_data_point(...)` if you need to read from other channels of the same device.
- The base class exposes helper attributes like `self._unit`, `_min`/`_max`, etc., which you can set in `__init__()`.
- Override `_post_init()` for additional initialization that depends on resolved data points.
- Keep calculations side-effect free. The base class handles event subscriptions automatically.

---

### Testing and validation

- Run the test suite (see README.md for instructions) and add targeted tests for your new profile or calculated DP.
- For calculated DPs, add unit tests around your formula and a small channel/device stub if possible.
- For custom profiles, test that required GenericDataPoints are attached and visible fields behave as expected.

### Documentation and discoverability

- After adding a new calculated data point, update aiohomematic.model.calculated.**init** \_CALCULATED_DATA_POINTS.
- If you add a reusable helper or pattern, include a short docstring and cross-link from this page.

## Where to look for examples

- model/calculated/climate.py and operating_voltage_level.py
- model/custom/definition.py and model/custom/data_point.py

If anything in this guide is unclear, open an issue or PR with questions and we’ll help refine these docs.
