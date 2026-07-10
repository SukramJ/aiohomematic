# Plan: Unified validity gating for custom data points (`_validity_relevant_fields`)

Status: implemented (2026-07-10, released as 2026.7.6)
Related issues: #3255, #3279
Target version: 2026.7.6 (verify with `git tag --list '2026.7.*' | sort -V | tail -3` before release; 2026.7.5 is tagged)

## 1. Goal

`CustomDataPoint.is_valid` currently requires **all** readable field data points to be
refreshed. Secondary values (activity/direction readbacks, group-channel readbacks,
colors, extra sensors) can stay unrefreshed for hours after a CCU restart — nothing
re-polls them (the periodic refresh skips `NO_CREATE` data points) — so entities hang in
`value_state=restored` (covers; same class as climate #3255/#3279).

Replace the three coexisting mechanisms (default "all readable", climate blocklist
`_validity_irrelevant_data_points`, per-class allowlist overrides of
`_relevant_data_points`) with **one declarative mechanism**: every custom data point
class declares the fields that gate validity in a `ClassVar` frozenset. A contract test
pins the sets for all 27 concrete classes.

## 2. Design decisions (resolved, no TBDs)

- **D1 — Mechanism**: `_validity_relevant_fields: ClassVar[frozenset[Field]]`, annotated
  (without value) on `CustomDataPoint`, assigned in subclasses, inherited where
  identical. The base `_relevant_data_points` property filters `_data_points` by this
  set **and** `is_readable`. No subclass may override `_relevant_data_points` anymore
  (contract-enforced).
- **D2 — Non-readable / missing fields**: fields not present on a device (or resolved to
  `DpDummy`, which is never readable) drop out via the `is_readable` filter. No special
  handling needed.
- **D3 — Empty set semantics**: `all(())` is `True`, so an empty set means "always
  valid". Used deliberately for `CustomDpTextDisplay` (write-only device; its only
  readable field `BURST_LIMIT_WARNING` is a warning channel, not a state carrier).
- **D4 — Blind `LEVEL_2` is NOT validity-relevant**: `LEVEL_2` is listed in
  `_OPTIONAL_PARAMETERS` ("blinds without slats", `aiohomematic/model/data_point.py`),
  and the existing value-based override in `CustomDpBlind._relevant_data_points` exists
  precisely because devices may never report it (e.g. blind actuators operated as
  shutters). Hard-gating on `LEVEL_2` would recreate the same failure class for those
  devices. Consequence: a blind with a known `LEVEL` but unknown slat position is valid;
  `tilt_position` is exposed as an attribute and may be `None`.
  _Rejected alternative_: `frozenset({Field.LEVEL, Field.LEVEL_2})` on `CustomDpBlind` —
  rejected because permanently-missing `LEVEL_2` would keep the entity restored forever.
- **D5 — Climate keeps mode-bearing fields**: `mode` is computed from `SET_POINT_MODE`
  (IP, `climate.py` `CustomDpIpThermostat.mode`) and `CONTROL_MODE` (RF,
  `CustomDpRfThermostat.mode`), so these stay validity-relevant alongside
  `TEMPERATURE`/`SETPOINT`. `ACTIVE_PROFILE`, `PARTY_MODE`, `CONCENTRATION`, `HUMIDITY`
  and all MASTER fields no longer gate validity.
- **D6 — RGBW/DALI lights gate on `LEVEL` only**: the dynamic per-operation-mode
  allowlist in `CustomDpIpRGBWLight` and the `CustomDpIpDrgDaliLight` override are
  removed. Color values are attributes; an unknown color must not keep the light
  restored. This slightly relaxes the current RGBW behavior (HUE/SATURATION/
  COLOR_TEMPERATURE no longer gate) — deliberate, consistent with the principle.
- **D7 — `CustomDpSoundPlayer` gates on `DIRECTION`**: its `is_on` ("is playing") is
  derived from `ACTIVITY_STATE` (`siren.py` `CustomDpSoundPlayer.is_on`), so `DIRECTION`
  is the state carrier here — the one class where an activity field is critical.
- **D8 — No migration guide**: no public API changes (`_validity_irrelevant_data_points`
  and the removed overrides are protected). Behavior change is documented in the
  changelog and ADR-0025.

## 3. Field sets per class (contract table)

Inheritance is used where the set is identical to the parent. "Effective" is what the
contract test asserts.

| Class                            | Declared                                        | Effective set             |
| -------------------------------- | ----------------------------------------------- | ------------------------- |
| `CustomDpCover`                  | `{LEVEL}`                                       | `{LEVEL}`                 |
| `CustomDpWindowDrive`            | inherit                                         | `{LEVEL}`                 |
| `CustomDpBlind`                  | inherit                                         | `{LEVEL}` (D4)            |
| `CustomDpIpBlind`                | inherit                                         | `{LEVEL}`                 |
| `CustomDpGarage`                 | `{DOOR_STATE}`                                  | `{DOOR_STATE}`            |
| `CustomDpSwitch`                 | `{STATE}`                                       | `{STATE}`                 |
| `CustomDpIpIrrigationValve`      | `{STATE}`                                       | `{STATE}`                 |
| `CustomDpDimmer`                 | `{LEVEL}`                                       | `{LEVEL}`                 |
| `CustomDpColorDimmer`            | inherit                                         | `{LEVEL}`                 |
| `CustomDpColorDimmerEffect`      | inherit                                         | `{LEVEL}`                 |
| `CustomDpColorTempDimmer`        | inherit                                         | `{LEVEL}`                 |
| `CustomDpIpRGBWLight`            | inherit                                         | `{LEVEL}` (D6)            |
| `CustomDpIpRGBWColorTempLight`   | inherit                                         | `{LEVEL}`                 |
| `CustomDpIpDrgDaliLight`         | inherit                                         | `{LEVEL}` (D6)            |
| `CustomDpIpFixedColorLight`      | inherit                                         | `{LEVEL}`                 |
| `CustomDpSoundPlayerLed`         | inherit                                         | `{LEVEL}`                 |
| `BaseCustomDpClimate` (abstract) | `{TEMPERATURE, SETPOINT}`                       | —                         |
| `CustomDpSimpleRfThermostat`     | inherit                                         | `{TEMPERATURE, SETPOINT}` |
| `CustomDpRfThermostat`           | `{TEMPERATURE, SETPOINT, CONTROL_MODE}`         | ditto (D5)                |
| `CustomDpIpThermostat`           | `{TEMPERATURE, SETPOINT, SET_POINT_MODE}`       | ditto (D5)                |
| `CustomDpIpLock`                 | `{LOCK_STATE}`                                  | `{LOCK_STATE}`            |
| `CustomDpRfLock`                 | `{STATE}`                                       | `{STATE}`                 |
| `CustomDpButtonLock`             | `{BUTTON_LOCK}`                                 | `{BUTTON_LOCK}`           |
| `CustomDpIpSiren`                | `{ACOUSTIC_ALARM_ACTIVE, OPTICAL_ALARM_ACTIVE}` | ditto                     |
| `CustomDpIpSirenSmoke`           | `{SMOKE_DETECTOR_ALARM_STATUS}`                 | ditto                     |
| `CustomDpSoundPlayer`            | `{DIRECTION}`                                   | `{DIRECTION}` (D7)        |
| `CustomDpTextDisplay`            | `frozenset()`                                   | empty (D3)                |
| `CustomDpIpAccessPermission`     | `{STATE}`                                       | `{STATE}`                 |

## 4. Implementation steps

Execute in order. After all edits run `python script/sort_class_members.py` (fixes
member ordering), then the quality gates in section 7.

### 4.1 `aiohomematic/model/custom/data_point.py`

1. Extend the typing import (line 12):
   `from typing import Any, Final, Unpack, override` →
   `from typing import Any, ClassVar, Final, Unpack, override`
2. Replace the `_relevant_data_points` property (currently returns
   `self._readable_data_points` with docstring "Returns the list of relevant data
   points. To be overridden by subclasses.") with:

```python
    # Fields whose readable data points gate validity (is_refreshed / is_valid /
    # state_uncertain). Assigned by subclasses; enforced for every concrete class by
    # tests/contract/test_cdp_validity_contract.py. An empty set means "always valid"
    # (write-only devices). See ADR-0025.
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

`Field` is already imported in this module.

### 4.2 `aiohomematic/model/custom/climate.py`

1. Typing import: add `ClassVar` → `from typing import ClassVar, Final, Unpack, cast, override`
2. `BaseCustomDpClimate`: **delete** the `_validity_irrelevant_data_points` property
   (lines 216–228) and the `_relevant_data_points` override (lines 230–236). Add next to
   the `DataPointField` definitions:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.TEMPERATURE, Field.SETPOINT})
```

3. `CustomDpRfThermostat`: **delete** its `_validity_irrelevant_data_points` override
   (lines 515–519). Add:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset(
        {Field.TEMPERATURE, Field.SETPOINT, Field.CONTROL_MODE}
    )
```

4. `CustomDpIpThermostat`: **delete** its `_validity_irrelevant_data_points` override
   (lines 729–743). Add:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset(
        {Field.TEMPERATURE, Field.SETPOINT, Field.SET_POINT_MODE}
    )
```

5. `CustomDpSimpleRfThermostat`: no change (inherits base set).
6. If `GenericDataPointProtocolAny` becomes unused after the deletions, remove it from
   the imports (check with `ruff check --select F401`).

### 4.3 `aiohomematic/model/custom/cover.py`

1. Typing import: add `ClassVar`.
2. `CustomDpCover`: add next to the `DataPointField` definitions:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.LEVEL})
```

3. `CustomDpBlind`: **delete** the `_relevant_data_points` override (lines 307–312,
   the value-based `LEVEL_2` special case — superseded by D4).
4. `CustomDpGarage`: add:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.DOOR_STATE})
```

5. `CustomDpWindowDrive`, `CustomDpIpBlind`: no change (inherit).

### 4.4 `aiohomematic/model/custom/light.py`

1. Typing import: add `ClassVar`.
2. `CustomDpDimmer`: add:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.LEVEL})
```

3. `CustomDpIpRGBWLight`: **delete** the `_relevant_data_points` override
   (lines 574–588, the `_device_operation_mode`-based allowlist — superseded by D6).
4. `CustomDpIpDrgDaliLight`: **delete** the `_relevant_data_points` override
   (lines 712–715).
5. All other light classes: no change (inherit `{LEVEL}`).

### 4.5 `aiohomematic/model/custom/switch.py`

Typing import: add `ClassVar`. `CustomDpSwitch`: add:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.STATE})
```

### 4.6 `aiohomematic/model/custom/valve.py`

Typing import: add `ClassVar`. `CustomDpIpIrrigationValve`: add:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.STATE})
```

### 4.7 `aiohomematic/model/custom/lock.py`

Typing import: add `ClassVar` (module currently imports only `Final` from typing).

```python
# CustomDpIpLock:
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.LOCK_STATE})
# CustomDpButtonLock:
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.BUTTON_LOCK})
# CustomDpRfLock:
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.STATE})
```

### 4.8 `aiohomematic/model/custom/siren.py`

Typing import: add `ClassVar`.

```python
# CustomDpIpSiren:
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset(
        {Field.ACOUSTIC_ALARM_ACTIVE, Field.OPTICAL_ALARM_ACTIVE}
    )
# CustomDpIpSirenSmoke:
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.SMOKE_DETECTOR_ALARM_STATUS})
# CustomDpSoundPlayer (D7 — ACTIVITY_STATE carries is_on):
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.DIRECTION})
```

### 4.9 `aiohomematic/model/custom/text_display.py`

Typing import: add `ClassVar`. `CustomDpTextDisplay` (D3 — write-only device):

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset()
```

### 4.10 `aiohomematic/model/custom/access_permission.py`

Typing import: add `ClassVar`. `CustomDpIpAccessPermission`:

```python
    _validity_relevant_fields: ClassVar[frozenset[Field]] = frozenset({Field.STATE})
```

## 5. New contract test — `tests/contract/test_cdp_validity_contract.py`

Create with exactly this content:

```python
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for custom data point validity gating.

STABILITY GUARANTEE
-------------------
``CustomDataPoint`` validity (``is_refreshed``/``is_valid``/``state_uncertain``) is
gated exclusively by the readable data points of the fields declared in
``_validity_relevant_fields`` (ADR-0025). This contract pins, for every concrete
custom data point class, exactly which fields gate validity. Any change to the sets
below changes Home Assistant entity availability (``value_state``) and must be a
deliberate, changelog-documented decision.

Background: #3255, #3279 — secondary values (activity/direction readbacks,
group-channel readbacks, colors, extra sensors) can stay unrefreshed for hours after
a CCU restart. If they gate validity, entities hang in ``value_state=restored`` until
a device event arrives.
"""

from __future__ import annotations

import inspect

from aiohomematic.const import Field
import aiohomematic.model.custom  # noqa: F401  # ensure all CDP classes are defined
from aiohomematic.model.custom.data_point import CustomDataPoint

# pylint: disable=protected-access

# Effective validity-relevant fields per concrete custom data point class.
EXPECTED_VALIDITY_RELEVANT_FIELDS: dict[str, frozenset[Field]] = {
    "CustomDpBlind": frozenset({Field.LEVEL}),
    "CustomDpButtonLock": frozenset({Field.BUTTON_LOCK}),
    "CustomDpColorDimmer": frozenset({Field.LEVEL}),
    "CustomDpColorDimmerEffect": frozenset({Field.LEVEL}),
    "CustomDpColorTempDimmer": frozenset({Field.LEVEL}),
    "CustomDpCover": frozenset({Field.LEVEL}),
    "CustomDpDimmer": frozenset({Field.LEVEL}),
    "CustomDpGarage": frozenset({Field.DOOR_STATE}),
    "CustomDpIpAccessPermission": frozenset({Field.STATE}),
    "CustomDpIpBlind": frozenset({Field.LEVEL}),
    "CustomDpIpDrgDaliLight": frozenset({Field.LEVEL}),
    "CustomDpIpFixedColorLight": frozenset({Field.LEVEL}),
    "CustomDpIpIrrigationValve": frozenset({Field.STATE}),
    "CustomDpIpLock": frozenset({Field.LOCK_STATE}),
    "CustomDpIpRGBWColorTempLight": frozenset({Field.LEVEL}),
    "CustomDpIpRGBWLight": frozenset({Field.LEVEL}),
    "CustomDpIpSiren": frozenset({Field.ACOUSTIC_ALARM_ACTIVE, Field.OPTICAL_ALARM_ACTIVE}),
    "CustomDpIpSirenSmoke": frozenset({Field.SMOKE_DETECTOR_ALARM_STATUS}),
    "CustomDpIpThermostat": frozenset({Field.TEMPERATURE, Field.SETPOINT, Field.SET_POINT_MODE}),
    "CustomDpRfLock": frozenset({Field.STATE}),
    "CustomDpRfThermostat": frozenset({Field.TEMPERATURE, Field.SETPOINT, Field.CONTROL_MODE}),
    "CustomDpSimpleRfThermostat": frozenset({Field.TEMPERATURE, Field.SETPOINT}),
    "CustomDpSoundPlayer": frozenset({Field.DIRECTION}),
    "CustomDpSoundPlayerLed": frozenset({Field.LEVEL}),
    "CustomDpSwitch": frozenset({Field.STATE}),
    "CustomDpTextDisplay": frozenset(),
    "CustomDpWindowDrive": frozenset({Field.LEVEL}),
}


def _all_cdp_classes() -> list[type[CustomDataPoint]]:
    """Return all (direct and indirect) subclasses of CustomDataPoint."""
    result: list[type[CustomDataPoint]] = []

    def _walk(cls: type[CustomDataPoint]) -> None:
        for sub in cls.__subclasses__():
            result.append(sub)
            _walk(sub)

    _walk(CustomDataPoint)
    return result


def _concrete_cdp_classes() -> list[type[CustomDataPoint]]:
    """Return all concrete (instantiable) custom data point classes."""
    return [cls for cls in _all_cdp_classes() if not inspect.isabstract(cls)]


class TestCdpValidityContract:
    """Pin the validity gating of every custom data point class."""

    def test_every_concrete_cdp_class_is_covered(self) -> None:
        """Every concrete CDP class must have an entry in the contract table."""
        concrete = {cls.__name__ for cls in _concrete_cdp_classes()}
        expected = set(EXPECTED_VALIDITY_RELEVANT_FIELDS)
        assert concrete - expected == set(), (
            f"New custom data point class(es) without validity contract: "
            f"{sorted(concrete - expected)}. Add them to EXPECTED_VALIDITY_RELEVANT_FIELDS."
        )
        assert expected - concrete == set(), (
            f"Contract table contains unknown class(es): {sorted(expected - concrete)}."
        )

    def test_validity_relevant_fields_match_contract(self) -> None:
        """The effective field set of every concrete CDP class matches the contract."""
        for cls in _concrete_cdp_classes():
            declared = getattr(cls, "_validity_relevant_fields", None)
            assert declared is not None, (
                f"{cls.__name__} does not resolve _validity_relevant_fields — "
                f"declare it on the class or a base class."
            )
            assert declared == EXPECTED_VALIDITY_RELEVANT_FIELDS[cls.__name__], (
                f"{cls.__name__}: validity-relevant fields changed. "
                f"Expected {sorted(EXPECTED_VALIDITY_RELEVANT_FIELDS[cls.__name__])}, "
                f"got {sorted(declared)}. If intentional, update the contract and changelog."
            )

    def test_no_relevant_data_points_overrides(self) -> None:
        """No subclass may override _relevant_data_points — the frozenset is the only mechanism."""
        for cls in _all_cdp_classes():
            assert "_relevant_data_points" not in vars(cls), (
                f"{cls.__name__} overrides _relevant_data_points. "
                f"Declare _validity_relevant_fields instead (ADR-0025)."
            )

    def test_base_class_has_no_default(self) -> None:
        """CustomDataPoint must not define a default — subclasses must decide explicitly."""
        assert "_validity_relevant_fields" not in vars(CustomDataPoint)
```

## 6. Behavior tests (regression for the restored-entity pattern)

### 6.1 `tests/test_model_cover.py` — add to the existing test class

Follow the pattern of `tests/test_model_climate.py::test_ip_thermostat_level_excluded_from_validity`
(same fixture and `@pytest.mark.parametrize` block as the surrounding tests in this
file; `TEST_DEVICES` already contains the addresses). Add:

```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_cover_validity_gated_by_level_only(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """DIRECTION/GROUP_LEVEL must not block cover is_valid after a CCU restart."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        cover = cast(CustomDpCover, get_prepared_custom_data_point(central, "VCU8537918", 4))
        # Preconditions: DIRECTION is a real, readable data point on this device.
        assert cover._dp_direction.is_readable
        # Secondary fields must not gate validity.
        assert cover._dp_direction not in cover._relevant_data_points
        assert cover._dp_group_level not in cover._relevant_data_points
        # Nothing refreshed yet -> invalid.
        assert cover.is_valid is False
        # Simulate a post-CCU-restart init where only LEVEL arrives (bulk fetch).
        cover._dp_level._set_refreshed_at(refreshed_at=datetime.now())
        # The cover must be valid even though DIRECTION/GROUP_LEVEL never refreshed.
        assert cover.is_valid is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_blind_validity_not_gated_by_level_2(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """LEVEL_2 (optional slats level) must not block blind is_valid (ADR-0025)."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        cover = cast(CustomDpBlind, get_prepared_custom_data_point(central, "VCU0000144", 1))
        assert cover._dp_level_2.is_readable
        assert cover._dp_level_2 not in cover._relevant_data_points
        assert cover.is_valid is False
        cover._dp_level._set_refreshed_at(refreshed_at=datetime.now())
        assert cover.is_valid is True
```

Required imports in `tests/test_model_cover.py` (add if missing):
`from datetime import datetime` — `cast`, `CustomDpCover`, `CustomDpBlind`,
`get_prepared_custom_data_point` are already imported there.

### 6.2 `tests/test_model_switch.py` — add analogous test

Same parametrize block as surrounding tests; device `VCU2128127`, channel 4:

```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_switch_validity_gated_by_state_only(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """GROUP_STATE must not block switch is_valid."""
        central, _mock_client, _ = central_client_factory_with_homegear_client
        switch = cast(CustomDpSwitch, get_prepared_custom_data_point(central, "VCU2128127", 4))
        assert switch._dp_group_state not in switch._relevant_data_points
        assert switch.is_valid is False
        switch._dp_state._set_refreshed_at(refreshed_at=datetime.now())
        assert switch.is_valid is True
```

Add `from datetime import datetime` to the imports if missing.

### 6.3 Existing tests

The three #3255/#3279 tests in `tests/test_model_climate.py`
(`test_ip_heating_group_humidity_heating_cooling_excluded_from_validity`,
`test_ip_thermostat_level_excluded_from_validity`,
`test_rf_thermostat_valve_state_excluded_from_validity`) assert exclusion via
`_relevant_data_points` and stay green unchanged (the excluded fields are also absent
from the new sets). If any other test fails because it relied on a secondary field
gating `is_valid`/`state_uncertain`, adjust the **test expectation** to the new gating —
do not widen a field set without updating the contract table (section 5) and changelog.

## 7. Quality gates and finalization

1. `python script/sort_class_members.py`
2. `pytest tests/contract/test_cdp_validity_contract.py tests/test_model_cover.py tests/test_model_switch.py tests/test_model_climate.py -v`
3. `pytest tests/`
4. `prek run --all-files`
5. `ruff check --select F401,F841` (removed overrides may orphan imports, e.g.
   `GenericDataPointProtocolAny` in `climate.py`/`light.py`)
6. `grep -rn "_validity_irrelevant_data_points" aiohomematic/ tests/` → must be empty
   (clean-code policy: no leftovers in code; ADR-0025 may reference the removed
   identifier when describing the superseded mechanism).

### 7.1 ADR — `docs/adr/0025-cdp-validity-relevant-fields.md`

New ADR (next free number after 0024). Sections: Status (accepted) · Context (three
coexisting mechanisms; #3255/#3279 failure class: secondary fields gate validity
but are never re-polled after reconnect because the periodic refresh excludes
`NO_CREATE` data points) · Decision (single declarative
`_validity_relevant_fields: ClassVar[frozenset[Field]]`; readable-filtered; empty set =
always valid; contract test pins all classes) · Consequences (entities become valid as
soon as their state-carrying fields refresh; secondary attributes may be `None`/stale
while the entity is valid; new CDP classes fail the contract test until they declare a
set). Add the entry to `docs/adr/index.md` following the existing format.

### 7.2 Documentation

- `docs/developer/homematicip_local_api_usage.md` (around line 272, the `is_valid`
  bullet): add one sentence — for custom data points, `is_valid` is gated only by the
  validity-relevant fields (link ADR-0025).

### 7.3 Changelog and version

1. `git tag --list '2026.7.*' | sort -V | tail -3` — confirm 2026.7.5 is still the
   latest tag; the new version is **2026.7.6** (adjust NN if a newer tag appeared).
2. New section at the top of `changelog.md`:

```markdown
# Version 2026.7.6 (2026-07-XX)

## What's Changed

### Changed

- **Custom data point validity is now gated only by state-carrying fields
  (ADR-0025).** Secondary values (activity/direction readbacks, group-channel
  readbacks, colors, extra sensors, MASTER config values) can stay unrefreshed for
  hours after a CCU restart — nothing re-polls them — and previously dragged the whole
  custom data point to `is_valid=False`, leaving Home Assistant entities stuck in
  `value_state=restored` (covers; same class as climate #3255/#3279). Every
  custom data point class now declares its validity-relevant fields in a single
  declarative `_validity_relevant_fields` set (cover/blind/dimmer: `LEVEL`;
  switch/valve/access permission: `STATE`; garage: `DOOR_STATE`; locks:
  `LOCK_STATE`/`STATE`/`BUTTON_LOCK`; climate: `ACTUAL_TEMPERATURE` + setpoint + mode
  source; sirens: alarm-active states; sound player: `ACTIVITY_STATE`). The climate
  blocklist `_validity_irrelevant_data_points` (#3255) and the per-class
  `_relevant_data_points` overrides (blind `LEVEL_2`, RGBW operation-mode allowlist,
  DALI) are replaced by the unified mechanism. A new contract test
  (`tests/contract/test_cdp_validity_contract.py`) pins the field set of all 27
  classes.
```

3. Set `aiohomematic/const.py` `VERSION: Final = "2026.7.6"` in the same commit and
   verify: `head -1 changelog.md` matches `grep "^VERSION" aiohomematic/const.py`.

## 8. Explicitly out of scope

- Re-polling custom-DP field data points after reconnect (the `exclude_no_create` gap
  in `refresh_data_point_data`) — separate decision with duty-cycle implications;
  this plan removes the _symptom coupling_, not the polling gap.
- Home Assistant integration changes (`supported_features` derivation is HA-core
  emergent behavior and resolves itself once entities report valid positions).
