# ADR 0022: Unified Schedule Access via WeekProfileDataPoint

## Status

Accepted (2026-02-05)

---

## Context

Schedule operations were split across two access paths: non-climate devices used `device.week_profile_data_point`, climate devices used 12 methods on `BaseCustomDpClimate`. This required device-type-specific code in HA. The 12 CDP methods were pure delegation wrappers containing no climate-specific logic. Additionally, `ClimateWeekProfile.copy_schedule()` accepted `BaseCustomDpClimate` as parameter, coupling the schedule layer to the CDP layer.

---

## Decision

`device.week_profile_data_point` is the **single, unified entry point** for all schedule operations -- both climate and non-climate.

### Architecture

```
All devices (unified):
  HA -> device.week_profile_data_point -> WeekProfile (Climate or Default)
```

### Class Hierarchy

```
WeekProfileDataPointProtocol                              (base protocol)
  +-- ClimateWeekProfileDataPointProtocol                 (climate-specific)

WeekProfileDataPoint(BaseDataPoint)                       (handles Default)
  +-- ClimateWeekProfileDataPoint(WeekProfileDataPoint)   (handles Climate)
```

### API Surface

**WeekProfileDataPoint** (all devices):

| Member                      | Type           | Purpose                                          |
| --------------------------- | -------------- | ------------------------------------------------ |
| `schedule`                  | property       | Cached schedule as `ScheduleDict`                |
| `schedule_type`             | property       | `ScheduleType.CLIMATE` or `ScheduleType.DEFAULT` |
| `schedule_channel_address`  | property       | Channel address for RPC calls                    |
| `max_entries`               | property       | Maximum schedule entries                         |
| `min_temp` / `max_temp`     | property       | Temperature bounds (climate only, else `None`)   |
| `available_target_channels` | property       | Target channel mapping (non-climate only)        |
| `value`                     | state property | Number of active entries                         |
| `get_schedule()`            | async method   | Fetch schedule from CCU                          |
| `set_schedule()`            | async method   | Write schedule to CCU                            |
| `reload_schedule()`         | async method   | Force reload from CCU                            |
| `fire_schedule_updated()`   | method         | Notify subscribers of changes                    |

**ClimateWeekProfileDataPoint** (climate devices, extends above):

| Member                        | Type         | Purpose                        |
| ----------------------------- | ------------ | ------------------------------ |
| `available_schedule_profiles` | property     | Available profiles (P1-P6)     |
| `schedule_profile_nos`        | property     | Number of supported profiles   |
| `get_schedule_profile()`      | async method | Read single profile            |
| `set_schedule_profile()`      | async method | Write single profile           |
| `get_schedule_weekday()`      | async method | Read single weekday            |
| `set_schedule_weekday()`      | async method | Write single weekday           |
| `copy_schedule()`             | async method | Copy schedule to target device |
| `copy_schedule_profile()`     | async method | Copy profile to target         |

### Factory: Two-Path Channel Resolution

The `create_week_profile_data_point` factory resolves the schedule channel via two paths:

```
Path 1: default_schedule_channel (non-climate)
  Device has a channel with type WEEK_PROFILE -> use that channel

Path 2: schedule_channel_no (climate)
  CDP.device_config.schedule_channel_no -> resolve to Channel object
  - BIDCOS_DEVICE_CHANNEL_DUMMY (999) -> device channel (bare address)
  - Integer N -> channel N (e.g., "VCU0000001:1")
```

| Device                 | schedule_channel_no | Gets Data Point?      |
| ---------------------- | ------------------- | --------------------- |
| HM-TC-IT-WM-W-EU       | DUMMY (999)         | Yes -- device channel |
| HM-CC-VG-1             | DUMMY (999)         | Yes -- device channel |
| HmIP-BWTH/STH/eTRV/... | 1                   | Yes -- channel 1      |
| HM-CC-TC, HM-CC-RT-DN  | None                | No -- no schedule     |
| ALPHA-IP-RBG           | None                | No -- no schedule     |

### Copy Method Decoupling

Copy operations use two layers to decouple the data point from `ClimateWeekProfile` internals:

```python
# Public API (data point layer):
ClimateWeekProfileDataPoint.copy_schedule(
    *, target_data_point: ClimateWeekProfileDataPointProtocol
)

# Internal (schedule layer, decoupled from CDP):
ClimateWeekProfile.copy_schedule_to(
    *, target_week_profile: ClimateWeekProfile
)
```

The data point extracts `target_data_point._week_profile` and delegates to `ClimateWeekProfile.copy_schedule_to()`.

### Key Implementation Details

**schedule_profile_nos sourcing**: Determined at factory time by inspecting the climate CDP. Passed to the `ClimateWeekProfileDataPoint` constructor to avoid coupling the data point to the CDP.

**Event propagation**: `reload_and_cache_schedule()` calls `fire_schedule_updated()` on the data point, which publishes a `data_point_updated` event via the EventBus.

**Type narrowing**: `ClimateWeekProfileDataPoint` narrows `_week_profile` from `ClimateWeekProfile | DefaultWeekProfile` to `ClimateWeekProfile` via a class-level annotation, avoiding runtime casts.

**Pessimistic cache**: Preserved unchanged. Schedule writes go to CCU via `put_paramset`, cache updates only on `CONFIG_PENDING = False`.

---

## Consequences

### Positive

- **Single access path** for all devices -- no device-type branching in HA
- **Separation of concerns** -- schedule logic on schedule data point, climate CDPs focus on temperature control
- **Decoupled copy operations** -- `ClimateWeekProfile` no longer references `BaseCustomDpClimate`
- **Protocol-typed API** -- consumers depend on protocols, not concrete classes

### Negative

- **Breaking change** for HA -- mitigated by migration guide with search-and-replace patterns
- **Runtime isinstance check** required for climate-specific methods (follows existing pattern)
- **20 additional data point instances** at startup (minimal memory with `__slots__`)

---

## Alternatives Considered

### Keep Schedule Methods on CDP as Secondary Path

**Rejected:** Doubles API surface and creates ambiguity about the authoritative path.

### Expose WeekProfile Directly (No Data Point)

**Rejected:** `WeekProfile` lacks EventBus integration, `BaseDataPoint` metadata, and HA entity compatibility.

### Single WeekProfileDataPoint for Both Types (No Subclass)

**Rejected:** Climate operations (profile/weekday/copy) are fundamentally different from simple schedule operations. A subclass with dedicated protocol provides type safety.

### Deprecation Period Before Removal

**Rejected:** Both projects are maintained together. Atomic migration avoids complexity without benefit.

---

## References

- Proposal: `docs/proposals/climate_schedule_sensor_migration.md`
- Migration Guide: `docs/migrations/week_profile_data_point_migration_2026_02.md`
- `aiohomematic/model/week_profile_data_point.py`
- `aiohomematic/interfaces/model.py`
- ADR 0002: Protocol-Based Dependency Injection

---

_Created: 2026-02-05_
_Author: Architecture Review_
