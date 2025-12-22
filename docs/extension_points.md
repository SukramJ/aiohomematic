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
     - `_init_data_point_fields` (to adjust defaults, units, operations)
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

- aiohomematic.model.calculated.data_point.CalculatedDataPoint: Base class to inherit from
  - \_add_data_point(...) / \_add_device_data_point(...) for attaching sources
  - publish_data_point_updated_event is triggered when any source updates
  - Decorators: @state_property, @config_property, @cached_slot_property
- aiohomematic.model.calculated.**init**
  - create_calculated_data_points(channel): factory that evaluates relevance and attaches instances to channels
  - \_CALCULATED_DATA_POINTS: tuple of registered calculated DP classes
- Existing implementations for reference:
  - climate.py: ApparentTemperature, DewPoint, FrostPoint, VaporConcentration
  - operating_voltage_level.py: OperatingVoltageLevel

### Lifecycle:

- On channel initialization, create_calculated_data_points(channel) iterates all registered classes, calls Class.is_relevant_for_model(channel) and adds instances for those that apply by calling channel.add_data_point(...).
- Each CalculatedDataPoint registers callbacks to its source GenericDataPoints in **init** via \_add_data_point/\_add_device_data_point and recomputes its value on updates.

### Steps to add a new calculated data point:

1. Implement a subclass of CalculatedDataPoint
   - Set the \_calculated_parameter to a value from aiohomematic.const.CalculatedParameter (this becomes the parameter name exposed by the DP)
   - In \_init_data_point_fields(), attach required source GenericDataPoints using \_add_data_point(...)
   - Provide properties using decorators:
     - @state_property def value(self) -> T: return computed_value
     - @config_property def unit(self) -> str | None: return unit string (e.g., "°C")
     - Optionally @cached_slot_property for static metadata
   - Implement staticmethod is_relevant_for_model(\*, channel: ChannelProtocol) -> bool to guard which channels get this DP
2. Register your class
   - Add the class to \_CALCULATED_DATA_POINTS in aiohomematic.model.calculated.**init** so the factory can discover it:
     \_CALCULATED_DATA_POINTS = (ApparentTemperature, ..., YourNewCalculatedDP)
3. Ensure correctness
   - The base class manages subscriptions and updating. Call self.publish_data_point_updated_event() if you maintain extra state.
   - Use helper conversions in aiohomematic.model.calculated.support if your formula needs them.

### Minimal template:

```python
# aiohomematic/model/calculated/my_metric.py
from __future__ import annotations
from aiohomematic.model.calculated.data_point import CalculatedDataPoint
from aiohomematic.property_decorators import state_property, config_property
from aiohomematic.const import CalculatedParameter, ParamsetKey
from aiohomematic.interfaces.model import ChannelProtocol
from aiohomematic.model.generic.sensor import DpSensor


class MyMetric(CalculatedDataPoint[float]):
    _calculated_parameter = CalculatedParameter.MY_METRIC

    def _init_data_point_fields(self) -> None:
        super()._init_data_point_fields()
        # Attach sources from the same channel (examples):
        # Note: All parameters are keyword-only
        self._dp_temp = self._add_data_point(
            parameter="TEMPERATURE",
            paramset_key=ParamsetKey.VALUES,
            dpt=DpSensor,
        )
        self._dp_hum = self._add_data_point(
            parameter="HUMIDITY",
            paramset_key=ParamsetKey.VALUES,
            dpt=DpSensor,
        )

    @staticmethod
    def is_relevant_for_model(*, channel: ChannelProtocol) -> bool:
        # Only add if required sources exist on this channel
        return channel.get_generic_data_point(
            parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES
        ) is not None

    @state_property
    def value(self) -> float | None:
        t = self._dp_temp.value if hasattr(self, "_dp_temp") else None
        h = self._dp_hum.value if hasattr(self, "_dp_hum") else None
        if t is None or h is None:
            return None
        # implement your calculation here
        return (t + h) / 2

    @config_property
    def unit(self) -> str | None:
        return "unit"
```

### Notes:

- Use \_add_device_data_point(...) if you need to read from other channels of the same device.
- The base class exposes helper attributes like self.\_unit, \_min/\_max, etc., which you can set in \_init_data_point_fields() if needed.
- Keep calculations side-effect free. The base class will debounce via event callbacks from sources.

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
