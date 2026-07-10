# ADR-0025: Custom Data Point Validity Gating via Validity-Relevant Fields

## Status

Accepted (2026-07-10)

## Context

### Three coexisting mechanisms

`CustomDataPoint.is_valid` (and, transitively, `is_refreshed` / `state_uncertain`) is
derived from `_relevant_data_points`: the set of the custom data point's own readable
data points that must have refreshed at least once before the custom data point is
considered valid. Historically this set was produced by three different, coexisting
mechanisms:

1. **Default "all readable"** — the base `_relevant_data_points` property returned
   every readable field data point (`self._readable_data_points`).
2. **Climate blocklist** — `BaseCustomDpClimate` and its subclasses defined
   `_validity_irrelevant_data_points`, a set of data points to _subtract_ from the
   default "all readable" set.
3. **Per-class allowlist overrides** — individual classes (`CustomDpBlind`,
   `CustomDpIpRGBWLight`, `CustomDpIpDrgDaliLight`) overrode `_relevant_data_points`
   directly with bespoke, value-dependent logic (e.g. excluding `LEVEL_2` only when the
   device never reports it, or excluding color fields based on the current operation
   mode).

### Failure class

Under the default "all readable" mechanism, _every_ readable field data point gates
validity — including secondary values such as activity/direction readbacks,
group-channel readbacks, colors, and extra sensors. These secondary data points are
frequently `NO_CREATE` and are therefore excluded from the periodic refresh
(`refresh_data_point_data`); nothing re-polls them after a reconnect. If the CCU does
not spontaneously emit an event for a secondary parameter, its data point never
refreshes, and the whole custom data point — including its primary, state-carrying
value — stays `is_valid=False` for hours after a CCU restart.

This was observed and worked around piecemeal:

- Climate (#3255, #3279): mode-independent fields (`ACTIVE_PROFILE`, `PARTY_MODE`,
  `CONCENTRATION`, `HUMIDITY`, MASTER fields) had to be added to
  `_validity_irrelevant_data_points` one at a time as they were discovered.
- Cover/switch/other custom data points: the same class of failure exists for
  every custom data point that still relies on the default "all readable" mechanism —
  e.g. a cover's `DIRECTION` or `GROUP_LEVEL` readback blocking `is_valid` even though
  `LEVEL` — the only value a consumer needs — has already been refreshed.

The blocklist approach does not scale: it requires enumerating every secondary field
retroactively, per class, after each failure report, and the allowlist overrides
duplicated similar logic ad hoc per class with no shared contract.

## Decision

Replace all three mechanisms with a single declarative allowlist:

```python
class CustomDataPoint(...):
    # Fields whose readable data points gate validity. Assigned by subclasses.
    _validity_relevant_fields: ClassVar[frozenset[Field]]

    @property
    def _relevant_data_points(self) -> tuple[GenericDataPointProtocolAny, ...]:
        """Return the readable data points whose fields gate validity."""
        return tuple(
            dp
            for field, dp in self._data_points.items()
            if field in self._validity_relevant_fields and dp.is_readable
        )
```

- `CustomDataPoint` declares `_validity_relevant_fields` as an annotation only (no
  default value) — every concrete subclass must assign it explicitly, either directly
  or by inheriting an identical set from its parent.
- The set is filtered by `is_readable`: fields not present on a particular device (or
  resolved to `DpDummy`, which is never readable) drop out automatically. No special
  casing is needed for devices that lack an optional field.
- An empty set is a deliberate, valid declaration: `all(())` is `True`, so a custom
  data point with no validity-relevant fields is always considered valid. This is used
  for write-only devices (`CustomDpTextDisplay`), whose only readable field
  (`BURST_LIMIT_WARNING`) is a warning channel, not a state carrier.
- No subclass may override `_relevant_data_points` anymore — the frozenset is the only
  mechanism. This is enforced by a contract test.
- A new contract test, `tests/contract/test_cdp_validity_contract.py`, pins the
  effective `_validity_relevant_fields` set for all 27 concrete custom data point
  classes. Any change to a set is a deliberate, changelog-documented decision, not an
  incidental side effect of refactoring.

### Field set examples

Fields are chosen to be the minimal set of state carriers, not every readable field:

- Cover/blind/dimmer classes: `{LEVEL}` — `DIRECTION`, `GROUP_LEVEL`, `LEVEL_2`
  (optional slats level, per D4 in the implementation plan) no longer gate validity.
- Switch/valve/access permission: `{STATE}`.
- Garage: `{DOOR_STATE}`.
- Locks: `{LOCK_STATE}` / `{STATE}` / `{BUTTON_LOCK}` depending on the class.
- Climate: `{TEMPERATURE, SETPOINT}` plus the field that feeds `mode`
  (`CONTROL_MODE` for RF, `SET_POINT_MODE` for IP). `ACTIVE_PROFILE`, `PARTY_MODE`,
  `CONCENTRATION`, `HUMIDITY` and all MASTER fields no longer gate validity.
- Sirens: the alarm-active state fields (e.g. `ACOUSTIC_ALARM_ACTIVE` /
  `OPTICAL_ALARM_ACTIVE`, or `SMOKE_DETECTOR_ALARM_STATUS`).
- Sound player: `{DIRECTION}`, because its `is_on` ("is playing") is derived from
  `ACTIVITY_STATE`, making that the state carrier for this class.
- RGBW/DALI lights: `{LEVEL}` only — color values (`HUE`, `SATURATION`,
  `COLOR_TEMPERATURE`) are exposed as attributes and no longer gate validity. This is a
  deliberate relaxation versus the previous per-operation-mode allowlist.

The full contract table lives in
`tests/contract/test_cdp_validity_contract.py::EXPECTED_VALIDITY_RELEVANT_FIELDS`.

## Consequences

### Positive

- Entities become valid as soon as their state-carrying fields refresh, regardless of
  whether secondary/readback fields have ever received a value. This closes the
  `value_state=restored` failure class reported in #3255 and #3279.
- A single, uniform mechanism replaces three overlapping ones — no more blocklist
  maintenance, no more bespoke per-class override logic.
- The contract test makes validity gating an explicit, reviewable contract: adding a
  new custom data point class fails the test until its author consciously declares
  `_validity_relevant_fields`, and widening an existing set requires a deliberate,
  changelog-documented change.

### Negative / trade-offs

- Secondary attributes (activity/direction readbacks, colors, group-channel readbacks,
  extra sensors) may report `None` or a stale value while the owning custom data point
  is already valid — they are no longer coupled to `is_valid`. Consumers that need
  freshness guarantees for a specific secondary attribute must check that data point's
  own `is_refreshed` state directly.
- RGBW/DALI lights slightly relax existing behavior: color fields no longer gate
  validity, so a light can report `is_valid=True` with an unrefreshed color. This is
  accepted as consistent with the general principle (see the implementation plan,
  `docs/plans/cdp_validity_relevant_fields_2026_07.md`, decision D6).
- Blinds with a permanently-absent `LEVEL_2` (e.g. operated as plain shutters) are
  valid based on `LEVEL` alone; `tilt_position` may stay `None` indefinitely. This is
  intentional (decision D4) — gating on `LEVEL_2` would recreate the same failure
  class for those devices.
- No migration guide is required: `_validity_irrelevant_data_points` and the removed
  per-class `_relevant_data_points` overrides were protected (non-public) members, so
  this is not a public API change.

## References

- `aiohomematic/model/custom/data_point.py` — `_relevant_data_points` base property
- `tests/contract/test_cdp_validity_contract.py` — contract test pinning all 27 classes
- `docs/plans/cdp_validity_relevant_fields_2026_07.md` — implementation plan with the
  full per-class rationale (design decisions D1–D8)
- Issues #3255, #3279
