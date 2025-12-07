# Docstring Audit for aiohomematic

This document provides a categorization of all modules in the aiohomematic codebase according to the tier system defined in [docstring_standards.md](./docstring_standards.md).

**Related Documents**:

- [Docstring Standards](./docstring_standards.md) - Complete style guide
- [Docstring Templates](./docstring_templates.md) - Ready-to-use templates

---

## Tier Classification Summary

| Tier | Description | Module Count |
|------|-------------|--------------|
| **Tier 1** | Core API Modules (Comprehensive docstrings) | 5 |
| **Tier 2** | Coordinators/Internal (Medium detail) | 18 |
| **Tier 3** | Utilities/Generic (Brief) | ~68 |

---

## Tier 1: Core API Modules

These modules are entry points and primary packages requiring comprehensive docstrings with Overview, Public API, Quick Start, and Notes sections.

| Module | Status | Notes |
|--------|--------|-------|
| `aiohomematic/__init__.py` | ✅ Complete | Main package entry point |
| `aiohomematic/central/__init__.py` | ✅ Complete | CentralUnit and CentralConfig |
| `aiohomematic/client/__init__.py` | ✅ Complete | Client abstractions |
| `aiohomematic/model/__init__.py` | ✅ Complete | Data point and event model |
| `aiohomematic/model/hub/__init__.py` | ✅ Complete | Hub entities (programs, sysvars) |

---

## Tier 2: Coordinator/Internal Modules

These modules are coordinators, stores, and internal implementations requiring medium-detail docstrings with description and key features.

### Central Coordinators

| Module | Status | Description |
|--------|--------|-------------|
| `central/cache_coordinator.py` | ✅ Complete | Cache management |
| `central/client_coordinator.py` | ✅ Complete | Client lifecycle |
| `central/device_coordinator.py` | ✅ Complete | Device operations |
| `central/event_coordinator.py` | ✅ Complete | Event handling |
| `central/hub_coordinator.py` | ✅ Complete | Hub entities |
| `central/scheduler.py` | ✅ Complete | Background tasks |
| `central/device_registry.py` | ✅ Complete | Device storage |
| `central/event_bus.py` | ✅ Complete | Event system |
| `central/rpc_server.py` | ✅ Complete | XML-RPC callback server |
| `central/decorators.py` | ✅ Complete | RPC function decorators |

### Store Modules

| Module | Status | Description |
|--------|--------|-------------|
| `store/__init__.py` | ✅ Complete | Store package |
| `store/persistent.py` | ✅ Complete | Disk-backed caches |
| `store/dynamic.py` | ✅ Complete | In-memory caches |
| `store/visibility.py` | ✅ Complete | Parameter filtering |

### Client Modules

| Module | Status | Description |
|--------|--------|-------------|
| `client/json_rpc.py` | ✅ Complete | JSON-RPC implementation |
| `client/rpc_proxy.py` | ✅ Complete | XML-RPC proxy wrapper |
| `client/_rpc_errors.py` | ✅ Complete | RPC error handling |

### Interface Modules

| Module | Status | Description |
|--------|--------|-------------|
| `interfaces/__init__.py` | ✅ Complete | Protocol package |
| `interfaces/central.py` | ✅ Complete | Central protocols |
| `interfaces/client.py` | ✅ Complete | Client protocols |
| `interfaces/model.py` | ✅ Complete | Model protocols |
| `interfaces/operations.py` | ✅ Complete | Operations protocols |
| `interfaces/coordinators.py` | ✅ Complete | Coordinator protocols |

---

## Tier 3: Utility/Generic Modules

These modules are utilities, constants, and generic implementations requiring brief docstrings.

### Root Level Modules

| Module | Status | Description |
|--------|--------|-------------|
| `api.py` | ✅ Complete | API helper |
| `async_support.py` | ✅ Complete | Async utilities |
| `backend_detection.py` | ✅ Complete | Backend detection |
| `const.py` | ✅ Complete | Constants and enums |
| `context.py` | ✅ Complete | Context management |
| `converter.py` | ✅ Complete | Value conversion |
| `decorators.py` | ✅ Complete | Function decorators |
| `exceptions.py` | ✅ Complete | Custom exceptions |
| `hmcli.py` | ✅ Complete | CLI entry point |
| `i18n.py` | ✅ Complete | Internationalization |
| `property_decorators.py` | ✅ Complete | Property decorators |
| `retry.py` | ✅ Complete | Retry logic |
| `schemas.py` | ✅ Complete | Validation schemas |
| `support.py` | ✅ Complete | Cross-cutting utilities |
| `type_aliases.py` | ✅ Complete | Type aliases |
| `validator.py` | ✅ Complete | Startup validation |

### Model Core

| Module | Status | Description |
|--------|--------|-------------|
| `model/data_point.py` | ✅ Complete | Base DataPoint class |
| `model/device.py` | ✅ Complete | Device & Channel classes |
| `model/event.py` | ✅ Complete | Event representation |
| `model/support.py` | ✅ Complete | Model utilities |
| `model/update.py` | ✅ Complete | Update handling |
| `model/week_profile.py` | ✅ Complete | Weekly schedules |

### Model Generic

| Module | Status | Description |
|--------|--------|-------------|
| `model/generic/__init__.py` | ✅ Complete | Generic package |
| `model/generic/action.py` | ✅ Complete | Action triggers |
| `model/generic/binary_sensor.py` | ✅ Complete | Boolean sensors |
| `model/generic/button.py` | ✅ Complete | Momentary buttons |
| `model/generic/data_point.py` | ✅ Complete | Generic data point impl |
| `model/generic/dummy.py` | ✅ Complete | Dummy entities |
| `model/generic/number.py` | ✅ Complete | Numeric input |
| `model/generic/select.py` | ✅ Complete | Dropdown selectors |
| `model/generic/sensor.py` | ✅ Complete | Numeric/text sensors |
| `model/generic/switch.py` | ✅ Complete | Toggle switches |
| `model/generic/text.py` | ✅ Complete | Text input |

### Model Custom

| Module | Status | Description |
|--------|--------|-------------|
| `model/custom/__init__.py` | ✅ Complete | Custom package |
| `model/custom/climate.py` | ✅ Complete | Thermostats |
| `model/custom/cover.py` | ✅ Complete | Blinds/shutters |
| `model/custom/data_point.py` | ✅ Complete | Custom data point base |
| `model/custom/definition.py` | ✅ Complete | Profile definitions |
| `model/custom/light.py` | ✅ Complete | Lights/dimmers |
| `model/custom/lock.py` | ✅ Complete | Door locks |
| `model/custom/mixins.py` | ✅ Complete | Mixin classes |
| `model/custom/profile.py` | ✅ Complete | ProfileConfig dataclasses |
| `model/custom/registry.py` | ✅ Complete | DeviceProfileRegistry |
| `model/custom/siren.py` | ✅ Complete | Sirens/alarms |
| `model/custom/support.py` | ✅ Complete | Helper utilities |
| `model/custom/switch.py` | ✅ Complete | Switches/relays |
| `model/custom/valve.py` | ✅ Complete | Heating valves |

### Model Calculated

| Module | Status | Description |
|--------|--------|-------------|
| `model/calculated/__init__.py` | ✅ Complete | Calculated package |
| `model/calculated/climate.py` | ✅ Complete | Climate calculations |
| `model/calculated/data_point.py` | ✅ Complete | Calculated data points |
| `model/calculated/operating_voltage_level.py` | ✅ Complete | Battery/voltage |
| `model/calculated/support.py` | ✅ Complete | Calculation utilities |

### Model Hub

| Module | Status | Description |
|--------|--------|-------------|
| `model/hub/binary_sensor.py` | ✅ Complete | Hub binary sensors |
| `model/hub/button.py` | ✅ Complete | Hub buttons |
| `model/hub/data_point.py` | ✅ Complete | Hub data point impl |
| `model/hub/inbox.py` | ✅ Complete | Inbox data points |
| `model/hub/install_mode.py` | ✅ Complete | Install mode |
| `model/hub/number.py` | ✅ Complete | Hub numeric input |
| `model/hub/select.py` | ✅ Complete | Hub dropdown selectors |
| `model/hub/sensor.py` | ✅ Complete | Hub sensors |
| `model/hub/switch.py` | ✅ Complete | Hub switches |
| `model/hub/text.py` | ✅ Complete | Hub text input |
| `model/hub/update.py` | ✅ Complete | Hub updates |

---

## Audit Checklist

When reviewing docstrings, verify:

- [ ] Ends with period
- [ ] Uses imperative mood (functions) or declarative (classes)
- [ ] Consistent verb usage (Return, not Get/Fetch)
- [ ] Appropriate detail level for tier
- [ ] No type repetition from signature
- [ ] Proper grammar and spelling
- [ ] Formatted with `ruff format`
- [ ] Passes `ruff check --select D`

---

## Validation Commands

```bash
# Check docstring compliance
ruff check --select D aiohomematic/

# Auto-fix formatting issues
ruff check --fix --select D aiohomematic/

# Format all code
ruff format aiohomematic/
```

---

## Improvement Roadmap

### Completed

- [x] Tier 1 modules (Core API) - All complete
- [x] Tier 2 modules (Coordinators, Store, Client) - All complete
- [x] Tier 3 modules (Utilities, Generic, Custom, Calculated, Hub) - All complete

### Maintenance

- Regular review during code changes
- Update audit when adding new modules
- Ensure new code follows docstring standards

---

**Last Updated**: 2025-12-07
**Version**: 1.0
