# Public API Surface

This document defines the **stable public API** of aiohomematic for external consumers
(Home Assistant integration, MQTT bridge, Matter bridge, configuration tools).

Symbols listed here are considered stable. Breaking changes will be documented in
migration guides under `docs/migrations/`.

## Import conventions

All symbols can be imported from their canonical module. The import paths listed
below are the **recommended** paths for external consumers.

---

## Tier 1 -- Core (all consumers)

These symbols are used by virtually every consumer project.

### Central unit

```python
from aiohomematic.central import CentralConfig, CentralUnit, check_config
from aiohomematic.central import CentralConfigBuilder
```

### Client configuration

```python
from aiohomematic.client import InterfaceConfig
```

### Event system

```python
from aiohomematic.central.events import (
    # EventBus core
    Event,
    EventBus,
    EventPriority,
    SubscriptionGroup,

    # Public events (consumed by integrations)
    DataPointsCreatedEvent,
    DataPointStateChangedEvent,
    DeviceLifecycleEvent,
    DeviceLifecycleEventType,
    DeviceTriggerEvent,
    OptimisticRollbackEvent,
    SystemStatusChangedEvent,

    # Recovery events
    RecoveryCompletedEvent,
    RecoveryFailedEvent,
    RecoveryStageChangedEvent,

    # State machine events
    CentralStateChangedEvent,
    ClientStateChangedEvent,

    # Integration support
    IntegrationIssue,
)
```

### Constants and enums

```python
from aiohomematic.const import (
    CentralState,
    ClientState,
    DataPointCategory,
    DataPointKey,
    DataPointType,
    DeviceTriggerEventType,
    Interface,
    Manufacturer,
    Operations,
    OptionalSettings,
    ParamsetKey,
    TimeoutConfig,
)
```

### Type aliases

```python
from aiohomematic.type_aliases import UnsubscribeCallback
```

### Async support

```python
from aiohomematic.async_support import Looper
```

---

## Tier 2 -- Data point models (integration consumers)

These are needed when building platform entities (HA, MQTT, Matter).

### Generic data points

```python
from aiohomematic.model.generic import (
    DpAction,
    DpActionBoolean,
    DpActionFloat,
    DpActionInteger,
    DpActionSelect,
    DpActionString,
    DpBinarySensor,
    DpButton,
    DpFloat,
    DpInteger,
    DpSelect,
    DpSensor,
    DpSwitch,
    DpText,
    BaseDpNumber,
    BaseDpActionNumber,
)
```

### Custom data points

```python
from aiohomematic.model.custom import (
    BaseCustomDpClimate,
    BaseCustomDpLock,
    BaseCustomDpSiren,
    CustomDpBlind,
    CustomDpCover,
    CustomDpDimmer,
    CustomDpGarage,
    CustomDpIpBlind,
    CustomDpIpIrrigationValve,
    CustomDpSwitch,
    CustomDpTextDisplay,
)
```

### Hub data points

```python
from aiohomematic.model.hub import (
    ProgramDpButton,
    ProgramDpSwitch,
    SysvarDpBinarySensor,
    SysvarDpNumber,
    SysvarDpSelect,
    SysvarDpSensor,
    SysvarDpSwitch,
    SysvarDpText,
)
```

### Update and calculated data points

```python
from aiohomematic.model.hub import DpUpdate
from aiohomematic.model.calculated import CalculatedDataPoint
```

### Base classes and protocols

```python
from aiohomematic.model.data_point import CallbackDataPoint
from aiohomematic.interfaces.model import (
    CallbackDataPointProtocol,
    ChannelEventGroupProtocol,
    CombinedDataPointProtocol,
    CustomDataPointProtocol,
    DeviceProtocol,
    GenericDataPointProtocol,
    GenericDataPointProtocolAny,
    GenericEventProtocolAny,
)
```

### Device model

```python
from aiohomematic.model import AvailabilityInfo
from aiohomematic.model.event import ClickEvent
```

---

## Tier 3 -- Specialized (specific consumers)

### Schedule / week profile

```python
from aiohomematic.interfaces.model import ClimateWeekProfileDataPointProtocol
from aiohomematic.model.week_profile_data_point import WeekProfileDataPoint
from aiohomematic.model.schedule_models import ClimateWeekdaySchedule
from aiohomematic.const import ScheduleTimerConfig
```

### Hub coordinator

```python
from aiohomematic.central.coordinators import HubCoordinator
from aiohomematic.model.hub import (
    HmInterfaceConnectivitySensor,
    InstallModeDpButton,
    InstallModeDpSensor,
)
```

### Metrics

```python
from aiohomematic.model.hub import (
    HmConnectionLatencySensor,
    HmLastEventAgeSensor,
    HmSystemHealthSensor,
)
```

### Client internals (advanced)

```python
from aiohomematic.client import CircuitBreaker, CircuitState
from aiohomematic.client.backends import BackendCapabilities
```

---

## Internal APIs (not for external use)

The following are **internal implementation details** and may change without notice:

- `aiohomematic.central.coordinators.*` (except HubCoordinator)
- `aiohomematic.central.events.bus` (internal event types like `CacheInvalidatedEvent`,
  `ConnectionLostEvent`, `HeartbeatTimerFiredEvent`, etc.)
- `aiohomematic.store.*` (persistence internals)
- `aiohomematic.client.json_rpc` (transport implementation)
- `aiohomematic.client.rpc_proxy` (XML-RPC wrapper)
- `aiohomematic.model.custom.registry` (device registration internals)
- `aiohomematic.model.custom.definition` (profile definitions)
