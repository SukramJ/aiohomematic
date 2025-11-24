# Docstring Audit and Module Categorization

This document categorizes all modules in aiohomematic and aiohomematic_test_support by documentation tier according to [docstring_standards.md](./docstring_standards.md).

**Last Updated**: 2025-11-24

---

## Tier Classification

- **Tier 1 (Comprehensive)**: Core API modules with Overview, Public API, Quick start sections (~15-40 lines)
- **Tier 2 (Medium Detail)**: Coordinators and internal modules with key features (~10-20 lines)
- **Tier 3 (Brief)**: Utilities, generic implementations, simple modules (~3-5 lines)

---

## Tier 1: Core API Modules (Comprehensive Documentation)

These are primary entry points and key packages requiring extensive documentation.

### aiohomematic Package

| Module                               | Status    | Priority | Notes                                                 |
| ------------------------------------ | --------- | -------- | ----------------------------------------------------- |
| `aiohomematic/__init__.py`           | ⚠️ Review | HIGH     | Main package entry point                              |
| `aiohomematic/central/__init__.py`   | ✅ Good   | MEDIUM   | Already comprehensive, may need minor standardization |
| `aiohomematic/client/__init__.py`    | ✅ Good   | MEDIUM   | Already comprehensive, may need minor standardization |
| `aiohomematic/model/__init__.py`     | ⚠️ Review | HIGH     | Core model package entry                              |
| `aiohomematic/model/hub/__init__.py` | ✅ Good   | LOW      | Very detailed documentation already                   |

**Count**: 5 modules

---

## Tier 2: Coordinator & Internal Modules (Medium Detail)

These modules handle coordination, storage, and internal implementation details.

### Central Coordinators

| Module                                       | Status    | Priority | Notes                            |
| -------------------------------------------- | --------- | -------- | -------------------------------- |
| `aiohomematic/central/device_coordinator.py` | ✅ Good   | LOW      | Already well-documented          |
| `aiohomematic/central/cache_coordinator.py`  | ⚠️ Review | MEDIUM   | Check documentation completeness |
| `aiohomematic/central/client_coordinator.py` | ⚠️ Review | MEDIUM   | Check documentation completeness |
| `aiohomematic/central/hub_coordinator.py`    | ⚠️ Review | MEDIUM   | Check documentation completeness |
| `aiohomematic/central/event_coordinator.py`  | ⚠️ Review | MEDIUM   | Check documentation completeness |
| `aiohomematic/central/device_registry.py`    | ⚠️ Review | MEDIUM   | Check documentation completeness |

### Central Infrastructure

| Module                               | Status    | Priority | Notes                       |
| ------------------------------------ | --------- | -------- | --------------------------- |
| `aiohomematic/central/scheduler.py`  | ✅ Good   | LOW      | Already well-documented     |
| `aiohomematic/central/event_bus.py`  | ✅ Good   | LOW      | Very detailed documentation |
| `aiohomematic/central/rpc_server.py` | ⚠️ Review | MEDIUM   | Check documentation         |

### Client Modules

| Module                             | Status    | Priority | Notes                 |
| ---------------------------------- | --------- | -------- | --------------------- |
| `aiohomematic/client/json_rpc.py`  | ⚠️ Review | MEDIUM   | Implementation module |
| `aiohomematic/client/rpc_proxy.py` | ⚠️ Review | MEDIUM   | Implementation module |

### Store Modules

| Module                             | Status    | Priority | Notes                                |
| ---------------------------------- | --------- | -------- | ------------------------------------ |
| `aiohomematic/store/__init__.py`   | ✅ Good   | LOW      | Already has list-style documentation |
| `aiohomematic/store/persistent.py` | ✅ Good   | LOW      | Already well-documented              |
| `aiohomematic/store/dynamic.py`    | ⚠️ Review | MEDIUM   | Check documentation completeness     |
| `aiohomematic/store/visibility.py` | ✅ Good   | LOW      | Already well-documented              |

### Model Core

| Module                               | Status    | Priority | Notes                            |
| ------------------------------------ | --------- | -------- | -------------------------------- |
| `aiohomematic/model/device.py`       | ✅ Good   | LOW      | Already has medium detail docs   |
| `aiohomematic/model/data_point.py`   | ✅ Good   | LOW      | Already has medium detail docs   |
| `aiohomematic/model/event.py`        | ✅ Good   | LOW      | Already documented with sections |
| `aiohomematic/model/week_profile.py` | ⚠️ Review | LOW      | Check documentation              |
| `aiohomematic/model/update.py`       | ⚠️ Review | LOW      | Check documentation              |

### Decorators

| Module                                | Status  | Priority | Notes                       |
| ------------------------------------- | ------- | -------- | --------------------------- |
| `aiohomematic/property_decorators.py` | ✅ Good | LOW      | Very detailed documentation |

**Count**: 23 modules

---

## Tier 3: Utility & Generic Modules (Brief Documentation)

These modules should use the "Public API defined by **all**" pattern.

### Core Utilities

| Module                          | Status          | Priority | Notes                                    |
| ------------------------------- | --------------- | -------- | ---------------------------------------- |
| `aiohomematic/const.py`         | ✅ Good         | LOW      | Already has brief + **all** pattern      |
| `aiohomematic/support.py`       | ✅ Good         | LOW      | Already has brief + **all** pattern      |
| `aiohomematic/exceptions.py`    | ✅ Good         | LOW      | Already has brief + **all** pattern      |
| `aiohomematic/converter.py`     | ✅ Good         | LOW      | Already has brief + **all** pattern      |
| `aiohomematic/decorators.py`    | ✅ Good         | LOW      | Already has brief + **all** pattern      |
| `aiohomematic/validator.py`     | ✅ Good         | LOW      | Already has brief + **all** pattern      |
| `aiohomematic/context.py`       | ✅ Good         | LOW      | Already has brief + **all** pattern      |
| `aiohomematic/type_aliases.py`  | ✅ Good         | LOW      | Already has purpose-focused docs         |
| `aiohomematic/interfaces.py`    | ✅ Good         | LOW      | Already has purpose statement            |
| `aiohomematic/async_support.py` | ❌ Needs Update | HIGH     | Currently minimal, needs standardization |
| `aiohomematic/i18n.py`          | ✅ Good         | LOW      | Already has usage-focused docs           |
| `aiohomematic/hmcli.py`         | ⚠️ Review       | LOW      | CLI entry point                          |

### Central Utilities

| Module                               | Status    | Priority | Notes               |
| ------------------------------------ | --------- | -------- | ------------------- |
| `aiohomematic/central/decorators.py` | ⚠️ Review | LOW      | Decorator utilities |

### Client Utilities

| Module                               | Status    | Priority | Notes          |
| ------------------------------------ | --------- | -------- | -------------- |
| `aiohomematic/client/_rpc_errors.py` | ⚠️ Review | LOW      | Error handling |

### Generic Model Entities

| Module                                        | Status          | Priority | Notes                      |
| --------------------------------------------- | --------------- | -------- | -------------------------- |
| `aiohomematic/model/generic/__init__.py`      | ⚠️ Review       | MEDIUM   | Generic entity factory     |
| `aiohomematic/model/generic/data_point.py`    | ❌ Needs Update | HIGH     | Base implementation        |
| `aiohomematic/model/generic/action.py`        | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/generic/binary_sensor.py` | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/generic/button.py`        | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/generic/number.py`        | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/generic/select.py`        | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/generic/sensor.py`        | ❌ Needs Update | HIGH     | Currently minimal          |
| `aiohomematic/model/generic/switch.py`        | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/generic/text.py`          | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/generic/dummy.py`         | ⚠️ Review       | LOW      | Placeholder implementation |

### Custom Model Entities

| Module                                    | Status          | Priority | Notes                      |
| ----------------------------------------- | --------------- | -------- | -------------------------- |
| `aiohomematic/model/custom/__init__.py`   | ⚠️ Review       | MEDIUM   | Custom entity factory      |
| `aiohomematic/model/custom/data_point.py` | ❌ Needs Update | HIGH     | Base custom implementation |
| `aiohomematic/model/custom/definition.py` | ❌ Needs Update | HIGH     | Device definitions         |
| `aiohomematic/model/custom/climate.py`    | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/custom/cover.py`      | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/custom/light.py`      | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/custom/lock.py`       | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/custom/siren.py`      | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/custom/switch.py`     | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/custom/valve.py`      | ❌ Needs Update | MEDIUM   | Currently minimal          |
| `aiohomematic/model/custom/support.py`    | ⚠️ Review       | LOW      | Helper utilities           |

### Calculated Model Entities

| Module                                                     | Status          | Priority | Notes                          |
| ---------------------------------------------------------- | --------------- | -------- | ------------------------------ |
| `aiohomematic/model/calculated/__init__.py`                | ⚠️ Review       | MEDIUM   | Calculated entity factory      |
| `aiohomematic/model/calculated/data_point.py`              | ❌ Needs Update | HIGH     | Base calculated implementation |
| `aiohomematic/model/calculated/climate.py`                 | ❌ Needs Update | MEDIUM   | Climate calculations           |
| `aiohomematic/model/calculated/operating_voltage_level.py` | ❌ Needs Update | MEDIUM   | Battery level calculation      |
| `aiohomematic/model/calculated/support.py`                 | ⚠️ Review       | LOW      | Helper utilities               |

### Hub Model Entities

| Module                                    | Status    | Priority | Notes               |
| ----------------------------------------- | --------- | -------- | ------------------- |
| `aiohomematic/model/hub/data_point.py`    | ⚠️ Review | MEDIUM   | Hub data point base |
| `aiohomematic/model/hub/binary_sensor.py` | ⚠️ Review | LOW      | Hub binary sensor   |
| `aiohomematic/model/hub/button.py`        | ⚠️ Review | LOW      | Hub button          |
| `aiohomematic/model/hub/number.py`        | ⚠️ Review | LOW      | Hub number          |
| `aiohomematic/model/hub/select.py`        | ⚠️ Review | LOW      | Hub select          |
| `aiohomematic/model/hub/sensor.py`        | ⚠️ Review | LOW      | Hub sensor          |
| `aiohomematic/model/hub/switch.py`        | ⚠️ Review | LOW      | Hub switch          |
| `aiohomematic/model/hub/text.py`          | ⚠️ Review | LOW      | Hub text            |

### Model Support

| Module                          | Status          | Priority | Notes             |
| ------------------------------- | --------------- | -------- | ----------------- |
| `aiohomematic/model/support.py` | ❌ Needs Update | MEDIUM   | Currently minimal |

**Count**: 51 modules

---

## Test Support Package (aiohomematic_test_support)

All test support modules need enhancement with usage examples.

| Module                                  | Status          | Priority | Notes                                |
| --------------------------------------- | --------------- | -------- | ------------------------------------ |
| `aiohomematic_test_support/__init__.py` | ❌ Needs Update | HIGH     | Package entry, currently minimal     |
| `aiohomematic_test_support/const.py`    | ❌ Needs Update | MEDIUM   | Test constants                       |
| `aiohomematic_test_support/factory.py`  | ❌ Needs Update | HIGH     | Test factories, needs usage examples |
| `aiohomematic_test_support/mock.py`     | ❌ Needs Update | HIGH     | Mock implementations, needs examples |
| `aiohomematic_test_support/helper.py`   | ❌ Needs Update | MEDIUM   | Test helpers                         |

**Count**: 5 modules

---

## Summary Statistics

| Category               | Total  | ✅ Good      | ⚠️ Review    | ❌ Needs Update |
| ---------------------- | ------ | ------------ | ------------ | --------------- |
| Tier 1 (Comprehensive) | 5      | 3 (60%)      | 2 (40%)      | 0 (0%)          |
| Tier 2 (Medium Detail) | 23     | 11 (48%)     | 12 (52%)     | 0 (0%)          |
| Tier 3 (Brief)         | 51     | 12 (24%)     | 16 (31%)     | 23 (45%)        |
| Test Support           | 5      | 0 (0%)       | 0 (0%)       | 5 (100%)        |
| **TOTAL**              | **84** | **26 (31%)** | **30 (36%)** | **28 (33%)**    |

---

## Priority Breakdown

| Priority   | Count | Modules Requiring Attention                      |
| ---------- | ----- | ------------------------------------------------ |
| **HIGH**   | 11    | Package entry points, base classes, test support |
| **MEDIUM** | 31    | Coordinators, entity implementations             |
| **LOW**    | 42    | Well-documented or simple modules                |

---

## Action Items by Priority

### HIGH Priority (11 modules)

1. `aiohomematic/__init__.py` - Main entry point
2. `aiohomematic/model/__init__.py` - Model package entry
3. `aiohomematic/async_support.py` - Core utility
4. `aiohomematic/model/generic/data_point.py` - Generic base
5. `aiohomematic/model/generic/sensor.py` - Common entity type
6. `aiohomematic/model/custom/data_point.py` - Custom base
7. `aiohomematic/model/custom/definition.py` - Device definitions
8. `aiohomematic/model/calculated/data_point.py` - Calculated base
9. `aiohomematic_test_support/__init__.py` - Test package entry
10. `aiohomematic_test_support/factory.py` - Test factories
11. `aiohomematic_test_support/mock.py` - Test mocks

### MEDIUM Priority (31 modules)

- All coordinator modules needing review
- Generic, custom, and calculated entity implementations
- Various **init**.py files

### LOW Priority (42 modules)

- Already well-documented modules requiring only minor standardization
- Utility modules with established patterns

---

## Notes

- **Legend**:

  - ✅ Good: Documentation already meets or exceeds standards
  - ⚠️ Review: Documentation exists but needs standardization review
  - ❌ Needs Update: Documentation is minimal and requires improvement

- **Focus Areas**:

  1. Test support package (100% needs update)
  2. Generic/custom/calculated entities (45% needs update in Tier 3)
  3. Entry point modules (**init**.py files)

- **Quick Wins**: 26 modules already have good documentation and need minimal changes
