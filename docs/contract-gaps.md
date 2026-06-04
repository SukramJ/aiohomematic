# `aiohomematic-contract` — gap list & missing golden fixtures

Companion to [`drop-in-optimizations.md`](./drop-in-optimizations.md). That
doc explains _why_ a shared contract exists; this one tracks what the contract
package (`../aiohomematic-contract`) still has to cover before
`py-openccu-loom-client` can be trusted as a bit-identical drop-in.

The `unique_id` is the routing key `homematicip_local` stores per HA entity in
the registry. **Any divergence on cutover = lost entities + history**, so every
call site that builds a `unique_id` is part of the contract, not just the
generic function.

Status as of `aiohomematic-contract==2026.6.0`:

- ✅ `generate_unique_id(...)` reference impl + `unique_id_golden.json`
  (now 19 cases, incl. the P0 sysvar/program/custom/internal call sites)
- ✅ `DataPointCategory` / `DataPointType` / `CommandPriority` enums
- ✅ `hub_slug(...)` reference + `hub_slug_golden.json` (P0b)
- ✅ `generate_channel_unique_id(...)` reference + `channel_unique_id_golden.json` (P1)
- ✅ `category_golden.json` / `command_golden.json` enum name→value fixtures (P2)

**Contract side of P0–P2 is now complete.** What remains is _client-side
reconciliation_ in `py-openccu-loom-client` (it must adopt these references —
see the "what the client does instead" notes below); that work lives in the
client repo, not here.

---

## P0 — fixture cases for the call sites where the two backends diverge **today**

The generic golden fixture is green, but the client routes around
`generate_unique_id` with hand-rolled helpers that do **not** match aiohomematic.
These are real, verified mismatches — add the cases below to
`unique_id_golden.json` so both repos are forced onto the same output.

Reference call sites in aiohomematic:

| case               | aiohomematic call                                                                              | example output                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| internal `INT000*` | `generate_unique_id(address="INT0001234:1", parameter=…)`                                      | `{central_id}_int0001234_1_…`                                     |
| sysvar             | `generate_unique_id(address="sysvar", parameter=slugify(name))` — `model/hub/data_point.py:80` | `{central_id}_sysvar_…`                                           |
| program            | `generate_unique_id(address="program", parameter=slugify(name))`                               | `{central_id}_program_…`                                          |
| custom DP          | `generate_unique_id(address=channel.address)` — `model/custom/definition.py:119`               | `{device_address}_{channel}` (no parameter, **no `_cdp_` infix**) |

What the client does instead (must be reconciled, then frozen by these cases):

- `sysvar_unique_id(name)` → `sysvar_{name}` — **drops `central_id`**
  (`compat/.../model/hub/__init__.py:30`)
- `program_unique_id(id)` → `program_{id}` — **drops `central_id`**
- `custom_unique_id(device_address, name)` → `{device}_cdp_{name}` — **invents `_cdp_`**
  (`compat/.../model/custom/__init__.py:42`)
- generic `data_point_event_key` (`openccu_loom_client/events/types.py:47`) matches
  the _plain_ path but has **no `central_id` branch** for `INT000*` / virtual-remote / hub.

Fixture cases to add (expected = aiohomematic output):

```json
{"central_id": "ccu3", "address": "sysvar",  "parameter": "my_var",   "prefix": null, "expected": "ccu3_sysvar_my_var"},
{"central_id": "ccu3", "address": "program", "parameter": "my_prog",  "prefix": null, "expected": "ccu3_program_my_prog"},
{"central_id": "1234", "address": "VCU1234567:1", "parameter": null,  "prefix": null, "expected": "vcu1234567_1"},
{"central_id": "1234", "address": "INT0001234:2", "parameter": "LEVEL","prefix": null, "expected": "1234_int0001234_2_level"}
```

> ⚠️ **`slugify` vs the client's `_clean`.** Hub DPs pass
> `parameter=slugify(legacy_name)`; the client uses
> `_clean` (`replace(":"/"-"/" ", "_").lower()`). These must produce the same
> token. If they don't, that is a second contract gap — the slug rule itself
> belongs in the contract (a `slugify` reference impl + fixture), and the
> `parameter` column above should carry the _already-slugified_ value.

---

## P1 — `generate_channel_unique_id` is not in the contract at all

aiohomematic has a **second** routing-key function for the channel/device level
(`model/support.py:507`, used at `model/device.py:1047` to set
`Channel._unique_id`). Distinct format: no `parameter`, own virtual-remote rule.
The client builds channel identity independently, so this is reproduction-bound
just like `generate_unique_id` — but it has no reference impl and no fixture.

Add to the contract:

- `generate_channel_unique_id(central_id, address)` reference impl, and
- `channel_unique_id_golden.json` covering: plain channel, channel 0,
  `-`/`:` folding, and a virtual-remote address (`BidCoS-RF:1`,
  `HmIP-RCV-1:2`) where the `central_id` prefix kicks in.

---

## P2 — the enums are duplicated, not single-sourced

`aiohomematic` imports `DataPointCategory` / `DataPointType` from the contract
(`const.py:22`). The client does **not** — it imports a second, independently
maintained copy from `openccu_loom_types.enums` (PascalCase members vs. the
contract's SCREAMING_CASE; same string values for now). aiohomematic uses the
contract copy, the client uses the loom-types copy → the "single source of
truth" is nominal only, and nothing guarantees the two stay byte-identical.

Options (pick one, then enforce it):

1. Client imports the enums from `aiohomematic-contract` directly (true single
   source), or
2. keep the loom-types copy (it's daemon-generated wire) but add a
   `category_golden.json` / `command_golden.json` of `name → value` pairs that
   **both** repos assert against, so drift fails a test on both sides.

The README claims "each contract ships a golden fixture"; `category` and
`command` currently ship only the enum. Option 2 closes that too.

---

## Priority summary

| P       | Gap                                                            | Why it bites                                                                      | Contract side                                             |
| ------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **P0**  | sysvar / program / custom / internal `unique_id` fixture cases | the two backends produce different keys _right now_ → lost HA entities on cutover | ✅ cases added                                            |
| **P0b** | `slugify` vs `_clean` parity (sub-case of P0)                  | hub-DP parameter tokens differ on non-ASCII names                                 | ✅ `hub_slug` ref + golden                                |
| **P1**  | `generate_channel_unique_id` + fixture                         | second routing key, entirely ungoverned                                           | ✅ ref + golden                                           |
| **P2**  | enum single-sourcing + `category`/`command` fixtures           | duplicated enums can silently drift                                               | ✅ goldens; client may still keep its own copy (option 2) |

All four are covered on the `aiohomematic-contract` side; the remaining work is
client-side adoption in `py-openccu-loom-client`.
