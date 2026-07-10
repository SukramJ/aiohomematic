# Simplification Migration Guide (2026.07)

## Overview

An audit against the sole downstream consumer (`homematicip_local`) identified several
subsystems with zero external and zero (or dead-end) internal consumers. This release
removes them. No functionality used by `homematicip_local` is affected; every removal
was verified against the integration's actual import and call surface.

Removed in this release:

| Area              | Removed                                                                                        | Replacement                                                                                            |
| ----------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| CLI               | `aiohomematic/hmcli.py` + `aiohomematic` console script                                        | `hmcli` from [openccu-loom](https://github.com/sukramj/openccu-loom)                                   |
| Facade            | `aiohomematic/api.py` (`HomematicAPI`)                                                         | Use `CentralConfig` / `CentralUnit` directly                                                           |
| Events            | `SysvarStateChangedEvent`                                                                      | None needed — it was never published                                                                   |
| Observability     | `aiohomematic/tracing.py` (`Span`, `span`, …)                                                  | None — unused                                                                                          |
| Logging           | `aiohomematic/logging_context.py`                                                              | None — unused; `LogContextMixin` and `RequestContext` remain                                           |
| Protocols         | Zero-use ISP slice protocols in `aiohomematic.interfaces`                                      | Use the composite protocols (`ClientProtocol`, `CentralProtocol`, `DeviceProtocol`, `ChannelProtocol`) |
| Property metadata | `Kind` enum, `config_property`/`info_property`/`state_property`, `PayloadMixin`, `Device.info` | Plain `@property`; `hm_property(cached=…, log_context=…)` and `DelegatedProperty` remain               |

## Breaking Changes

### 1. `aiohomematic` console script (hmcli) removed

**Before:**

```bash
aiohomematic -H ccu.local -p 2010 getValue --address VCU0000001:1 --parameter STATE
```

**After:** use the Go `hmcli` shipped with openccu-loom, which covers devices,
paramsets, sysvars and programs.

### 2. `HomematicAPI` facade removed

**Before:**

```python
from aiohomematic.api import HomematicAPI

api = HomematicAPI(config)
async with api.connect():
    device = api.get_device("VCU0000001")
```

**After:**

```python
from aiohomematic.central import CentralConfig

config = CentralConfig.for_ccu(host="...", username="...", password="...")
central = await config.create_central()
async with central:
    device = central.device_coordinator.get_device(address="VCU0000001")
```

Every `HomematicAPI` method was a 1:1 delegation; the table below covers the
most common calls:

| `HomematicAPI`                                 | Direct equivalent                                                                                  |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `api.get_device(addr)`                         | `central.device_coordinator.get_device(address=addr)`                                              |
| `api.list_devices()`                           | `central.devices`                                                                                  |
| `api.read_value(...)` / `api.write_value(...)` | `client.get_value(...)` / `client.set_value(...)` via `central.client_coordinator.get_client(...)` |
| `api.subscribe_to_updates(...)`                | `central.event_bus.subscribe(event_type=..., event_key=..., handler=...)`                          |
| `api.start()` / `api.stop()`                   | `config.create_central()` + `central.start()` / `central.stop()`                                   |

### 3. `SysvarStateChangedEvent` removed

The event had no production publisher; subscriptions could never fire. Consumers
update sysvar data points by calling `sysvar_dp.event(...)` directly (as
`homematicip_local` already does) or subscribe to `DataPointStateChangedEvent`.

### 4. `aiohomematic.tracing` and `aiohomematic.logging_context` removed

`Span`, `span`, `get_current_span`, `get_current_trace_id`, `set_current_span`,
`reset_current_span`, `ContextualLoggerAdapter`, `RequestContextFilter` and
`get_contextual_logger` no longer exist. There is no replacement — no consumer
ever imported them. `aiohomematic.context` (`RequestContext`) and the structured
error logging via `LogContextMixin` are unaffected.

### 5. Zero-use interface protocols flattened

37 ISP slice protocols in `aiohomematic.interfaces` were deleted or inlined into
their composites (protocol count: 120 → 83). The composite protocols keep their
exact member sets (verified via AST diff), so code typed against
`ClientProtocol`, `CentralProtocol`, `DeviceProtocol` or `ChannelProtocol` — and
every protocol name imported by `homematicip_local` — is unaffected.

Removed outright: `DeviceLookupProtocol`, `NewDeviceHandlerProtocol`,
`DeviceManagementProtocol`, `CentralStateMachineProviderProtocol`,
`DataManagementOperationsProtocol` (alias).

Inlined into `ClientProtocol`: `ClientLifecycleProtocol`, `ClientSupportProtocol`,
`SystemVariableOperationsProtocol`, `ProgramOperationsProtocol`,
`LinkOperationsProtocol`, `FirmwareOperationsProtocol`, `BackupOperationsProtocol`,
`SystemManagementOperationsProtocol`, `MaintenanceOperationsProtocol`.
Inlined into `ValueAndParamsetOperationsProtocol`: `ParamsetOperationsProtocol`,
`ValueOperationsProtocol`. Inlined into `CentralProtocol`:
`BackupProviderProtocol`, `JsonRpcClientProviderProtocol`,
`CallbackAddressProviderProtocol`. Inlined into `HubDataFetcherProtocol`:
`HubFetchOperationsProtocol`. Inlined into `ChannelProtocol` / `DeviceProtocol`:
all `Channel*` / `Device*` slice and mid-composite protocols (e.g.
`ChannelIdentityProtocol`, `DeviceStateProtocol`, `DeviceOperationsProtocol`).

Still available (production-used bases): `ClientIdentityProtocol`,
`MetadataOperationsProtocol`, `DeviceIdentityProtocol`,
`DeviceChannelAccessProtocol`, `DeviceRemovalInfoProtocol`.

**Migration:** replace any import of a removed slice protocol with the composite
it was inlined into.

### 6. Kind/payload property subsystem removed

The `Kind` enum, the `config_property` / `info_property` / `state_property`
decorator factories, `get_hm_property_by_kind`, `PayloadMixin`
(`config_payload` / `info_payload` / `state_payload`), `PayloadProtocol` and
`Device.info` no longer exist. Their only consumption chain ended in
`Device.info`, which had zero readers.

**Before:**

```python
from aiohomematic.property_decorators import config_property, state_property

class MyDataPoint:
    @state_property
    def value(self) -> int: ...

    @config_property
    def interval(self) -> int: ...
```

**After:**

```python
from aiohomematic.property_decorators import hm_property

class MyDataPoint:
    @property
    def value(self) -> int: ...          # plain property

    @hm_property(cached=True)
    def interval(self) -> int: ...       # only if you need slots-compatible caching
```

Still available: `hm_property(cached=…, log_context=…)`, `DelegatedProperty`
(without the removed `kind=` / `alt_name=` parameters), `LogContextMixin`,
`get_hm_property_by_log_context`, and the new `get_hm_property_names()` helper
that lists all decorated property names of a class.

## Migration Steps

1. Replace any `HomematicAPI` usage with direct `CentralConfig`/`CentralUnit` calls
   (see table above).
2. Replace `aiohomematic` CLI invocations with openccu-loom's `hmcli`.
3. Drop imports of removed modules/symbols; mypy will point at every remaining use.

## Search-and-Replace Patterns

| Search                                         | Replace                                                         |
| ---------------------------------------------- | --------------------------------------------------------------- |
| `from aiohomematic.api import HomematicAPI`    | `from aiohomematic.central import CentralConfig`                |
| `from aiohomematic.tracing import ...`         | _(delete — no replacement)_                                     |
| `from aiohomematic.logging_context import ...` | _(delete — no replacement)_                                     |
| `SysvarStateChangedEvent`                      | `DataPointStateChangedEvent` (or direct `sysvar_dp.event(...)`) |

## Compatibility Notes

- `homematicip_local` is unaffected: it never imported any removed symbol (verified
  against its full import and attribute-access surface).
- The CUxD/CCU-Jack JSON-RPC contract and the MQTT push-update path
  (`get_state_paths`, `push_updates`, periodic-refresh configuration) are untouched.
- Historical changelog entries referring to removed modules remain unchanged.
