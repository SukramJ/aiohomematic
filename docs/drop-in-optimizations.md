# Refactorings to ease a daemon-backed drop-in replacement

Tracks the aiohomematic-side changes that would let an alternative
backend (the openccu-loom daemon, via `py-openccu-loom-client`) reuse
aiohomematic's model instead of re-implementing it — so
`homematicip_local` keeps one code path for both backends.

**Context.** `homematicip_local` consumes a large `CentralUnit` +
coordinator surface. The hard part to reproduce is the _categorized
data-point model_ (`unique_id` / `category` / `data_point_type` /
`registered`) that HA spawns entities from. That logic is ~95 %
backend-agnostic today — it consumes paramset / device descriptions as
_input_ and does not itself make RPC calls — but it lives inside the
RPC-coupled monolith, so an alternative backend cannot reuse it without
copying it.

> If the daemon grows to ship the category on the wire (see
> `openccu-loom/docs/external-clients/drop-in-optimizations.md`, P1),
> the client needs almost none of this and these refactorings become
> optional. They remain valuable as a single source of truth shared by
> both backends.

Each item below carries **Effort / Risk / Blocks** metadata so the
_order_ is explicit, not just the priority. The headline finding: the
model package cannot be extracted before two upward dependencies are
removed (Step 0). Skipping that ordering is the usual way this kind of
split stalls half-done.

---

## Current coupling reality (verified)

Runtime imports (excluding `TYPE_CHECKING`) out of `aiohomematic/model/`:

| Target package         | Runtime imports | What                                                                  |
| ---------------------- | --------------- | --------------------------------------------------------------------- |
| `aiohomematic.store`   | **0**           | clean — no work needed                                                |
| `aiohomematic.client`  | **5 files**     | only `CommandPriority` (an `IntEnum`, no RPC) from `command_throttle` |
| `aiohomematic.central` | **11 imports**  | only `central.events` (`events`, `events.internal`, `events.types`)   |

So "no RPC calls in the model" is true, but "the model is independent"
is **not**: it depends upward on `CommandPriority` (which lives under
`client/`) and on the event _type_ dataclasses + enums that live under
`central/events/`. Those two are the real blockers, and both are pure
data/enum coupling — no behaviour, no I/O — so both are mechanical to
break. The `EventBus` itself is already abstracted behind
`EventBusProviderProtocol` in `interfaces/central.py`; it is the
concrete event _types_ that the model imports directly, not the bus.

`generate_unique_id()` lives in `model/support.py` (~line 480) and makes
no upward imports — it is ready to lift as-is.

---

## Step 0 — Break the two upward dependencies (prerequisite for P1)

Until these are gone, the model package literally cannot import-cleanly,
so the P1 extraction's acceptance criterion ("no import of `client/`")
is unmeetable. Do this first.

**0a. Relocate `CommandPriority`.**
_Effort: S · Risk: low · Blocks: model extraction_

- [ ] Move `CommandPriority` (`client/command_throttle.py`) to a
      neutral home (`const.py` already hosts the other enums, incl.
      `IntEnum`s like `ChannelOffset`).
- [ ] Re-point the 5 model importers (`model/data_point.py`,
      `model/generic/data_point.py`, `model/custom/cover.py`,
      `model/custom/lock.py`, `model/custom/siren.py`) and the `client/`
      users at the new location. No alias/shim left behind (clean-code
      policy).

**0b. Move event types out of `central/` into a neutral layer.**
_Effort: M · Risk: medium · Blocks: model extraction_

The model imports these from `central.events`:
`DataPointStateChangedEvent`, `DeviceLifecycleEvent`,
`DeviceLifecycleEventType`, `OptimisticRollbackEvent`,
`DeviceRemovedEvent`, `ClientStateChangedEvent` (plus
`central.events.internal`).

- [ ] Move the event _type_ definitions (the dataclasses/enums consumed
      by the model) to a neutral module that both `model/` and
      `central/` depend on — not the other way around. The `EventBus`
      implementation and dispatch can stay in `central/`; only the
      payload types need to move down.
- [ ] Update `central/`, `client/` and `hub/` importers. The blast
      radius is wider than 0a (the bus is used everywhere), so land it
      as its own change with its own contract-test pass.

**0c. Enforce the boundary in-repo before splitting the package.**
_Effort: S · Risk: low · Blocks: nothing (it protects the rest)_

- [ ] Add an `import-linter` contract (or extend
      `script/lint_package_imports.py`, which today checks import
      _style_, not layering) asserting `aiohomematic.model` imports
      neither `aiohomematic.client` nor `aiohomematic.central`.
- [ ] Wire it into prek so the boundary can't regress.

_Why before the physical split:_ this captures 90 % of the architectural
value (a real, enforced dependency boundary) at near-zero cost, and lets
the actual package extraction (P1) be a pure file move with no semantic
risk. A separate distribution also carries real release/versioning
overhead (two packages to co-release), so prove the boundary holds
in-repo first.

---

## P1 (quick win, independent) — Pin `generate_unique_id()` as a shared contract

_Effort: S · Risk: low · Blocks: nothing · Can start today_

`unique_id` is the routing key for every HA value-change subscription.
The client already rebuilds it independently
(`py-openccu-loom-client` `events/types.py:data_point_event_key`); the
two must produce **bit-identical** output (`addr_channel_param`,
lowercased, `:` and `-` folded to `_`, hub addresses prefixed with
`central_id`).

- [ ] Add a golden cross-implementation fixture (input → expected id)
      that both aiohomematic and the client run, so the formats can't
      silently drift. This is valuable _now_, independent of any package
      split.
- [ ] When the model package is extracted (P1, below), `generate_unique_id()`
      moves with it as the canonical implementation; until then the
      fixture is the contract.

This is deliberately split out from the package extraction: it is the
highest-ROI, lowest-risk item and shares none of the extraction's
prerequisites.

---

## P1 (structural) — Extract a backend-agnostic model package

_Effort: L · Risk: medium · Blocks: nothing once Step 0 is done ·
Depends on: Step 0a + 0b + 0c_

Pull the RPC-free, purely model-level code into a standalone package
(e.g. `aiohomematic-model`) that any backend can depend on. After
Step 0 this is mostly a file move, not a semantic change:

- [ ] `const.py` — `DataPointCategory`, `DataPointType`, mappings,
      parameter/enum constants (now incl. the relocated
      `CommandPriority`).
- [ ] `model/data_point.py` — the `CallbackDataPoint` → `BaseDataPoint`
      → `BaseParameterDataPoint` hierarchy.
- [ ] `model/generic/` — the `DataPointTypeResolver` (DpSwitch vs.
      DpSensor vs. DpSelect … decision logic).
- [ ] `model/custom/` — custom-DP definitions, profiles, device-model
      registry (light/cover/climate/lock/siren/valve/switch).
- [ ] `model/calculated/`, `model/event.py`, `interfaces/` (Protocols),
      and the relocated event _types_ from Step 0b.

Acceptance: the package builds and its tests pass with **no import of**
`client/` **or** `central/` (enforced by the Step 0c linter). Device
creation is driven purely by supplied paramset + device-description
inputs.

_Impact:_ the daemon client and the direct-CCU backend share one
categorization source of truth, instead of the client carrying a
drifting copy.

---

## P2 — Put the query facade behind a backend-agnostic protocol

_Effort: M · Risk: low_

`homematicip_local` calls `query_facade.get_data_points`,
`get_event_groups`, `get_state_paths`, `get_un_ignore_candidates`
(`central/query_facade.py`). The facade is ~95 % backend-agnostic but
imports the cache / client / hub coordinators concretely.

- [ ] Define a `HubDataPointProvider` / device-registry protocol for the
      facade's dependencies (in `interfaces/`).
- [ ] Make `DeviceQueryFacade` depend on those protocols, so the compat
      adapter becomes an _implementation_ of the facade rather than a
      re-creation of it.

---

## P2 — Make the consumed surface an executable contract (not a prose list)

_Effort: M · Risk: low_

A backend must know exactly what it has to satisfy. A Markdown checklist
drifts the moment a method is renamed — the very failure mode this repo
guards against elsewhere. Bind the surface to the existing `interfaces/`
protocols plus a conformance test instead:

- [ ] Express the consumption surface below as `…Protocol` definitions
      under `interfaces/` (several already exist, e.g.
      `EventBusProviderProtocol` in `interfaces/central.py`).
- [ ] Add a conformance test that asserts the concrete `CentralUnit` /
      coordinators implement those protocols, so a rename breaks CI
      rather than this document.

The real consumption surface (from `homematicip_local`), to be encoded
as protocols:

- **CentralUnit**: `start`/`stop`, `state`, `name`, `model`,
  `version`, `url`, `system_information`, `central_info.name`.
- **event_bus**: `create_subscription_group`, `subscribe`,
  `unsubscribe_all`; events `DataPointStateChangedEvent` (unique_id-
  keyed), `DataPointsCreatedEvent`, `DeviceLifecycleEvent`,
  `SystemStatusChangedEvent`, `CentralStateChangedEvent`,
  `DeviceTriggerEvent`, `OptimisticRollbackEvent`, `DeviceRemovedEvent`.
- **query_facade**: `get_data_points`, `get_event_groups`,
  `get_state_paths`, `get_un_ignore_candidates`.
- **device_coordinator**: `get_device`, `delete_device`,
  `add_new_devices_manually`, `get_virtual_remotes`,
  `refresh_firmware_data`, `create/remove_central_links`, `devices`.
- **hub_coordinator**: `get_hub_data_points`, `get/set_system_variable`,
  `fetch_program_data`/`fetch_sysvar_data`, and the `*_dp(s)`
  properties (`install_mode_dps`, `connectivity_dps`,
  `alarm_messages_dp`, `service_messages_dp`, `inbox_dp`, `update_dp`,
  `metrics_dps`).
- **client_coordinator**: `has_client`, `has_clients`, `clients`.
- **link**: `get_device_links`, `add_link`, `remove_link`,
  `get_linkable_channels`.
- **json_rpc_client**: inbox devices, accept-in-inbox, rename,
  service/alarm messages, acknowledge.
- **config**: `CentralConfig`, `check_config`, `detect_backend`
  (must be able to recognize "Loom" as a backend), `InterfaceConfig`,
  `SystemInformation`.

---

## Recommended order

1. **Step 0a** — relocate `CommandPriority`. _(S, low)_
2. **Step 0b** — move event types into a neutral layer. _(M, medium)_
3. **Step 0c** — add the `model/ ⇏ client/ + central/` import linter. _(S, low)_
4. **P1 quick win** — `generate_unique_id` golden fixture (can run in
   parallel with Step 0; no shared prerequisites). _(S, low)_
5. **P1 structural** — extract the model package (now a file move). _(L, medium)_
6. **P2** — query-facade protocol + executable consumed-surface contract. _(M, low)_

## Notes

- Splitting the model out is the high-value move; it benefits the
  existing direct-CCU path too (clearer dependency boundaries, model
  testable without RPC mocks).
- The two Step-0 dependencies are pure data/enum coupling (no behaviour,
  no I/O), which is why the split is mechanical once they're gone — and
  why it is _blocked_ until they are.
- The hub coordinator's _logic_ is model-level but its data fetch is
  RPC-bound — the daemon supplies sysvars/programs as events instead,
  so the provider protocol (P2) is the seam that matters there.
- Enforcing the import boundary (Step 0c) captures most of the
  architectural value cheaply; the physical package split is then a
  low-risk follow-up rather than a prerequisite.
