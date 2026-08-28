# CUxD unique_id Scoping Migration Guide (2026.08)

## Overview

`generate_unique_id` now namespaces CUxD addresses with the central id, the same way
it already namespaced the hub pseudo-addresses, the `INT000*` internal addresses and
the virtual-remote roots.

CUxD hands out the same synthetic addresses on every CCU it runs on — `CUX2801001`
exists on practically every installation that runs CUxD. Two CCUs bridged into one
Home Assistant therefore declared identical CUxD `unique_id`s. Home Assistant keeps
whichever entity arrived first and drops the other CCU's entities, permanently once
the payload is retained.

This is **not** an additive change. It re-keys the CUxD entities of every installation
on upgrade, including direct-CCU installations.

Only the **parameter-level** key changes. `generate_channel_unique_id` is unchanged:
it namespaces the virtual-remote roots only, and did so for CUxD neither before nor
after this change.

## Breaking Changes

### `generate_unique_id` prepends the central id for `CUX*` addresses

**Before:**

```python
generate_unique_id(config_provider=central, address="CUX2801001:1", parameter="STATE")
# "cux2801001_1_state"
```

**After:**

```python
generate_unique_id(config_provider=central, address="CUX2801001:1", parameter="STATE")
# "<central_id>_cux2801001_1_state"
```

The prefix argument keeps its position — the central id is prepended last:

```python
generate_unique_id(
    config_provider=central, address="CUX2801001:1", parameter="STATE", prefix="calculated"
)
# "<central_id>_calculated_cux2801001_1_state"
```

### Unchanged: `generate_channel_unique_id`

```python
generate_channel_unique_id(config_provider=central, address="CUX2801001:1")
# "cux2801001_1"   (before and after)
```

## Migration Steps

### Consumers that persist `unique_id` (Home Assistant integrations)

A registry migration pass is required. Without it, CUxD entities are orphaned together
with their history and every automation that references them.

`homematicip_local` already runs two `async_migrate_entries` passes
(`_async_migrate_loom_unique_ids`, `_async_migrate_aiohomematic_hub_unique_ids`).
Neither covers the direct-CCU CUxD path; a third pass is needed. It must be
idempotent, because the migration runs on every config-entry load.

Shape of the rewrite:

| Old `unique_id`                 | New `unique_id`                              |
| ------------------------------- | -------------------------------------------- |
| `cux2801001_1_state`            | `<central_id>_cux2801001_1_state`            |
| `calculated_cux2801001_1_state` | `<central_id>_calculated_cux2801001_1_state` |

Guard the pass so an id that already carries the central prefix is left alone.

### Consumers that only route events

No action. The routing key is recomputed from the address on both ends, so it stays
consistent as long as every implementation ships the same rule in the same release
wave.

### Other implementations of the routing key

The rule is rebuilt independently in several places. All of them must ship this change
together, or events route to entities that no longer exist:

- `openccu-loom` (Go) — already scopes CUxD; it pinned the difference as a declared
  divergence in `notes/parity/by_design.md` (`BD-Identity-CUxDCentralScoping`) with
  fixtures that fail once the divergence disappears. Its CUxD cases have to be folded
  into the shared fixtures and the divergence entry deleted.
- `aiohomematic-contract` — the shared golden fixtures and the reference algorithm
  (`unique_id.py`, `data/unique_id_golden.json`) still encode the unscoped rule.
- `py-openccu-loom-client` — consumes the contract package.

## Search-and-Replace Patterns

There is no source-level pattern to replace: the change is entirely inside
`generate_unique_id`. What has to be found instead are **persisted** ids.

```bash
# Home Assistant entity registry: CUxD ids that are not yet central-scoped.
grep -o '"unique_id": "[^"]*cux[0-9]\{7\}[^"]*"' .storage/core.entity_registry

# Test fixtures / recorded sessions carrying CUxD unique ids.
grep -rn "cux[0-9]\{7\}_" tests/
```

## Compatibility Notes

- `aiohomematic/model/support.py:generate_unique_id` is the only changed function.
- The channel-level key, the address fold (`:` and `-` → `_`), the parameter append,
  the prefix prepend and the final lowercasing are all unchanged.
- The full cross-implementation golden set — including the newly scoped CUxD cases —
  is pinned by `tests/contract/test_unique_id_routing_key_contract.py`.
- ⚠️ Unmeasured: whether CUxD devices occur in production installations at all, and in
  what numbers. The divergence between the implementations is verified in the source
  trees; its practical blast radius is not.
