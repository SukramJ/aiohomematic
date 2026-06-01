# Refactorings to ease a daemon-backed drop-in replacement

Tracks the aiohomematic-side changes needed so an alternative backend
(the openccu-loom daemon, via `py-openccu-loom-client`) can stand in for
aiohomematic in `homematicip_local`.

**The daemon ships the data-point `category` + `data_point_type` on the
wire** (see `openccu-loom/docs/external-clients/drop-in-optimizations.md`).
That decision changes what this repo has to do: the client no longer needs
to re-derive categories, so **the categorization _logic_ does not have to be
shared at all**. What HA dispatches on does.

---

## Pivotal finding — HA dispatches on enums + Protocols, never on concrete classes (verified)

Checked against `homematicip_local/custom_components/homematicip_local/`:

- **Entity spawning filters by `data_point_type` / `category` enums**, e.g.
  `light.py:76` → `get_new_data_points(data_point_type=DataPointType.LIGHT)`,
  `button.py:77` → `data_point_type=DataPointType.BUTTON, category=DataPointCategory.BUTTON`.
- **Every `isinstance` check is against a `…Protocol`**, never against a
  concrete `DpSwitch` / `CustomDpLight`. See `generic_entity.py:160-356`,
  `entity_helpers/__init__.py:114-124`, `sensor.py:78`, `number.py:146`
  (`CustomDataPointProtocol`, `GenericDataPointProtocol`,
  `CombinedDataPointProtocol`, `CalculatedDataPointProtocol`,
  `ClimateWeekProfileDataPointProtocol`, `CallbackDataPointProtocol`, …).
- **Exception — hub data points filter by the concrete class as a marker**:
  `get_new_hub_data_points(data_point_type=SysvarDpSensor)`
  (`sensor.py:134`, `binary_sensor.py:68`, `button.py:81`, …). The class
  identity _is_ the filter key, so the shim must expose classes of those
  names (`SysvarDp{Sensor,BinarySensor,Number,Text,Select,Switch}`,
  `ProgramDp{Button,Switch}`) — but they are thin markers, not behaviour.

**Consequence:** the contract HA depends on is **the enums + the
`…Protocol` interfaces + `generate_unique_id` + the hub marker classes**.
All of it is static and RPC-free. The shim supplies its own daemon-backed
objects that satisfy the Protocols; it never needs aiohomematic's
categorization classes or their XML-RPC method bodies.

---

## The contract surface is _mostly_ import-clean (verified)

Runtime imports (excluding `TYPE_CHECKING`):

| Source                                                               | Imports `client/` or `central/`?                                                                         |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `const.py`                                                           | **none** — clean                                                                                         |
| `interfaces/model.py` (the DP Protocols HA `isinstance`-checks)      | **none** — clean                                                                                         |
| `model/support.py` (`generate_unique_id`, ~line 480)                 | only `const`, `interfaces`, `property_decorators`, top-level `support.to_bool` — no `client/`/`central/` |
| **hub marker classes** (`SysvarDp*`, `ProgramDp*`, `model/hub/*.py`) | **NOT clean** — see below                                                                                |

Two caveats the surface-narrowing must respect:

- **Not all of `interfaces/` is clean.** `interfaces/client.py:1306` has a
  runtime `from aiohomematic.client.command_throttle import CommandPriority`
  (`# noqa: E402`). Only the DP-Protocol module `interfaces/model.py` is
  clean — lift that, not `interfaces/` wholesale.
- **The hub marker classes are NOT a clean lift.** `SysvarDp*` / `ProgramDp*`
  inherit `GenericSysvarDataPoint`/`GenericProgramDataPoint` →
  `GenericHubDataPoint` → `CallbackDataPoint` (`model/data_point.py`), which
  imports `central.events` (line 75) **and** `client.command_throttle.CommandPriority`
  (line 76) at runtime. Because HA filters hub DPs by **concrete class
  identity** (`get_new_hub_data_points(data_point_type=SysvarDpSensor)`), a
  Protocol cannot stand in — the class itself must be a shared symbol, so its
  coupling cannot simply be defined away.

So the **enums + DP Protocols + `generate_unique_id`** are a clean lift with
**no Step 0**. The **hub marker classes are not**: including them pulls in
`model/data_point.py` and therefore needs Step 0a + 0b (the very items the
"Obsolete" section parks). Resolve that one element via Option A or B in the
P1 extraction below before treating the whole contract as a clean lift.

---

## P1 — Extract a small shared contract package

_Effort: M · Risk: low · Blocks: nothing_

Pull the static, dispatch-relevant surface into a tiny package (e.g.
`aiohomematic-contract`) that both aiohomematic and the daemon client can
depend on — so the three parties (HA filter, daemon wire, client router)
share one definition instead of drifting copies:

- [ ] `const.py` enums HA filters on — `DataPointCategory`, `DataPointType`.
      (Note: `default_category()` is **not** on the enum; it is a classmethod
      on `CallbackDataPoint`, `model/data_point.py:273`. The mapping helper HA
      uses lives in `homematicip_local` `control_unit.py:338` — a cross-repo
      reference, not aiohomematic.)
- [ ] `interfaces/model.py` Protocols HA `isinstance`-checks —
      `CallbackDataPointProtocol`, `GenericDataPointProtocol`,
      `CustomDataPointProtocol`, `CombinedDataPointProtocol`,
      `CalculatedDataPointProtocol`, `GenericHubDataPointProtocol`,
      `GenericSysvar/ProgramDataPointProtocol`,
      `ClimateWeekProfileDataPointProtocol`, plus the event/central provider
      protocols already there (`EventBusProviderProtocol`). Lift `model.py`
      specifically — `interfaces/client.py` is **not** client/central-free.
- [ ] `generate_unique_id()` as the canonical routing-key implementation.
- [ ] The hub marker classes (`SysvarDp*`, `ProgramDp*`) used as
      `get_new_hub_data_points` filter keys. **These are not a clean lift**
      (they inherit `CallbackDataPoint`, which imports `client/` + `central/`).
      **Decided: Option A** — change `homematicip_local` to filter hub DPs by an
      enum/`…Protocol` instead of the concrete class, so no concrete class
      crosses the boundary and the lift stays clean. (Rejected alternative —
      Option B: decouple `CallbackDataPoint` from `CommandPriority` + `central.events`;
      larger, re-introduces a scoped Step 0.)

Acceptance: the package imports neither `client/` nor `central/`. The enum +
Protocol + `generate_unique_id` subset already satisfies this (enforced by the
lint boundary below); the hub marker classes satisfy it once the Option-A
filter change has landed in `homematicip_local`.

_Impact:_ the shim implements daemon-backed objects against these
Protocols and reuses the exact enums HA filters on — no categorization
port, no concrete-class reuse.

## P1 — Pin `generate_unique_id()` with a golden fixture

_Effort: S · Risk: low · Blocks: nothing · Can start today_

`unique_id` is the routing key for every HA value-change subscription.
The client rebuilds it independently
(`py-openccu-loom-client` `events/types.py:data_point_event_key`); the two
must produce **bit-identical** output (`addr_channel_param`, lowercased,
`:` and `-` folded to `_`, hub addresses prefixed with `central_id`).

- [x] **Done (aiohomematic side).** Golden fixture at
      `tests/fixtures/unique_id_golden.json`, exercised by
      `tests/test_unique_id_golden.py`. The client repo vendors the same
      fixture and runs the equivalent assertion so the format can't drift.

## P1 — Align the enum catalogue with the daemon wire values + drift test

_Effort: S · Risk: low_

The daemon emits `category` / `data_point_type` strings; HA filters on
`aiohomematic.const` enums. **They must be byte-equal.** A
renamed or reordered value is now a breaking wire change across two repos.

- [ ] Verify `DataPointCategory` / `DataPointType` string values match the
      daemon's published `assets/schemas/enums.json` exactly (light, cover,
      climate, lock, siren, valve, switch, sensor, binary_sensor, button,
      plus the hub/event/schedule variants).
- [ ] Add a cross-repo drift test (or a documented release check) so
      neither side adds/drops/renames a value unilaterally. Pairs with the
      daemon-side drift detector in the openccu-loom task list.

## P1 — Enforce the contract boundary with a lint rule

_Effort: S · Risk: low_

- [x] **Done.** `script/lint_package_imports.py` now enforces a contract
      boundary (`CONTRACT_SURFACE_MODULES` = `const.py`, `interfaces/model.py`,
      `model/support.py`): they may not import `aiohomematic.client` /
      `aiohomematic.central` at runtime (TYPE_CHECKING imports are allowed).
      Checked on every run, independent of the paths passed. The hub marker
      classes are added once the Option-A filter change has landed.

## P2 — Make the consumed coordinator surface an executable contract

_Effort: M · Risk: low_

Entity _spawning_ is solved by enums + Protocols above, but
`homematicip_local` also drives a wide coordinator surface. A Markdown
checklist drifts the moment a method is renamed — bind it to Protocols +
a conformance test instead:

- [x] Express the surface below as `…Protocol` definitions under
      `interfaces/` — **already present** (`CentralProtocol`,
      `DeviceQueryFacadeProtocol`, `LinkFacadeProtocol`, `HubDataFetcherProtocol`,
      `HubDataPointManagerProtocol`, `ClientProviderProtocol`, …).
- [x] **Done.** Conformance test at
      `tests/contract/test_consumed_surface_contract.py`: asserts the consumed
      members exist on the live classes and that each class explicitly
      implements its consumed protocol, so a rename breaks CI, not the drop-in.

The real consumption surface (from `homematicip_local`):

- **CentralUnit**: `start`/`stop`, `state`, `name`, `model`, `version`,
  `url`, `system_information`, `central_info.name`.
- **event_bus**: `create_subscription_group` (+ `subscribe`); the returned
  `SubscriptionGroup` exposes `subscribe` / `unsubscribe_all`. Events:
  `DataPointStateChangedEvent` (unique_id-keyed),
  `DataPointsCreatedEvent`, `DeviceLifecycleEvent`,
  `SystemStatusChangedEvent`, `CentralStateChangedEvent`,
  `DeviceTriggerEvent`, `OptimisticRollbackEvent`, `DeviceRemovedEvent`.
- **query_facade**: `get_data_points`, `get_event_groups`,
  `get_state_paths`, `get_un_ignore_candidates`.
- **device_coordinator**: `get_device`, `delete_device`,
  `add_new_devices_manually`, `get_virtual_remotes`,
  `refresh_firmware_data`, `create/remove_central_links`, `devices`.
- **hub_coordinator**: `get_hub_data_points`, `get/set_system_variable`,
  `fetch_program_data`/`fetch_sysvar_data`, and the `*_dp(s)` properties
  (`install_mode_dps`, `connectivity_dps`, `alarm_messages_dp`,
  `service_messages_dp`, `inbox_dp`, `update_dp`, `metrics_dps`).
- **client_coordinator**: `has_client`, `has_clients`, `clients`.
- **link**: `get_device_links`, `add_link`, `remove_link`,
  `get_linkable_channels`.
- **json_rpc_client**: inbox devices, accept-in-inbox, rename,
  service/alarm messages, acknowledge.
- **config**: `CentralConfig`, `check_config`, `detect_backend` (must be
  able to recognize "Loom" as a backend), `InterfaceConfig`,
  `SystemInformation`.

---

## Recommended order

1. ✅ **P1 unique_id fixture** — golden cross-impl test
   (`tests/test_unique_id_golden.py`). _(S, low)_
2. ⬜ **P1 enum alignment** — match daemon wire values + drift test. Infra
   already present (`tests/contract/loom_wire_enums.json`). _(S, low)_
3. ⬜ **P1 contract extraction** — enums + Protocols + `generate_unique_id`
   into the (currently empty) `../aiohomematic-contract` package (clean lift);
   hub markers after the **Option A** filter change lands in `homematicip_local`.
   _(M, low; hub markers M after Option A)_
4. ✅ **P1 lint boundary** — contract surface kept client/central-free
   (`script/lint_package_imports.py`). _(S, low)_
5. ✅ **P2 coordinator conformance** — Protocols + conformance test
   (`tests/contract/test_consumed_surface_contract.py`). _(M, low)_

Done now: 1, 4, 5. Open: 2 (enum drift test) and 3 (package extraction +
the `homematicip_local` Option-A change — a second-repo edit).

---

## Obsolete given daemon-side categorization (optional aiohomematic hygiene only)

Because the daemon categorizes and the shim re-implements behaviour
against the daemon, **none of the following is needed for the drop-in**.
They remain reasonable internal cleanups but are off the critical path —
do not block the drop-in on them.

- **Extracting the full model package** (`model/data_point.py`,
  `model/generic/` `DataPointTypeResolver`, `model/custom/` registry +
  profiles + behaviour classes, `model/calculated/`). The shim does not
  reuse categorization logic or XML-RPC-backed behaviour.
- **Step 0a — relocating `CommandPriority`** out of `client/`. A
  prerequisite for the full model extraction above; verified that 5 model
  files import it (`model/data_point.py`, `model/generic/data_point.py`,
  `model/custom/{cover,lock,siren}.py`). With **Option A decided**, it is
  **not** needed for the contract surface (only the rejected Option B would
  have re-armed it).
- **Step 0b — moving event _types_ out of `central/`** (the
  `central.events` imports from `model/`, incl. `model/data_point.py:75`).
  Same status as 0a: a full-model-extraction prerequisite only — not a
  contract-surface one under Option A.

If aiohomematic later wants the direct-CCU path and the daemon path to
share categorization _logic_ too, revisit these — but that is an
aiohomematic-internal goal, not a drop-in requirement.
