# Release process: `aiohomematic-contract` first

`aiohomematic-contract` is **not** a test-fixture repo — it is a foundational
**runtime** package. It ships the symbols that more than one backend must
reproduce identically:

- the enums Home Assistant filters on — `DataPointCategory`, `DataPointType`
  (and `CommandPriority`),
- the routing-key reference implementations — `generate_unique_id`,
  `generate_channel_unique_id`, `hub_slug`,
- the golden fixtures that pin all of the above.

`aiohomematic` imports these at runtime (`const.py` re-exports the enums), so
`aiohomematic-contract` is a hard runtime dependency. `homematicip_local` and
`py-openccu-loom-client` consume it too. That coupling makes the release order
non-negotiable.

## The dependency invariant

```
aiohomematic-contract        ← bottom of the stack: imports NOTHING from aiohomematic
        ▲ ▲ ▲
        │ │ └─ py-openccu-loom-client
        │ └─── homematicip_local
        └───── aiohomematic   (const.py re-exports the enums)
```

`aiohomematic-contract` must never import `aiohomematic` (it would create a
cycle). Event payload types therefore deliberately live in the neutral
in-repo package `aiohomematic.event_types`, **not** in the contract
distribution — they depend on `const` state-enums that cannot move down without
dragging the whole enum set along. See
[`drop-in-optimizations.md`](../drop-in-optimizations.md) and
[`contract-gaps.md`](../contract-gaps.md).

## Versioning

- Scheme: `YYYY.MM.NN` (same as aiohomematic).
- **Single source of truth:** `aiohomematic_contract/const.py:VERSION`.
  `pyproject.toml` reads it via setuptools dynamic `attr`
  (`version = {attr = "aiohomematic_contract.const.VERSION"}`) — the version is
  never duplicated in code, exactly like `aiohomematic.const.VERSION`.
- **Bump the contract version on every published change to the shared surface**
  (new symbol, new/changed fixture case, enum value change). A pure docs/test
  change inside the contract repo does not require a bump.

## Pinning

- Consumers pin a lower bound: `aiohomematic-contract>=X.Y.Z`.
- The bound must be the version that actually **contains the symbols the
  consumer uses** — not just "any contract". When you add a use of a new
  contract symbol in aiohomematic, raise the pin in `aiohomematic/pyproject.toml`
  to the contract version that introduced it.
- Current state: aiohomematic uses only `CommandPriority` /
  `DataPointCategory` / `DataPointType` / `generate_unique_id` at runtime (all
  present since `2026.6.0`), so `aiohomematic-contract>=2026.6.0` is correct.
  `hub_slug` / `generate_channel_unique_id` are consumed by the client only.

## Release order (contract first)

For any change that touches the shared surface:

1. **`aiohomematic-contract`** — land the change, bump `const.VERSION`, update
   `changelog.md`, merge to `main`, tag `vX.Y.Z`, publish to PyPI (the
   `publish.yml` workflow does this on a GitHub Release; Trusted Publishing).
2. **`aiohomematic`** — raise the `aiohomematic-contract>=…` pin to the new
   version, merge, release.
3. **`homematicip_local`** / **`py-openccu-loom-client`** — bump their pins and
   release against the published aiohomematic + contract.

You cannot release an `aiohomematic` that uses a new contract symbol before that
contract version is on PyPI.

## Local development

While iterating on a coordinated cross-repo change, install the contract (and,
for downstream repos, aiohomematic) **editable** into each consumer's venv so
you can develop before publishing:

```bash
# in aiohomematic's venv
pip install -e ../aiohomematic-contract

# in homematicip_local's venv
pip install -e ../aiohomematic-contract -e ../aiohomematic
```

CI and released builds always use the **published** versions, never editable
installs.

## What belongs in the contract

Only backend-agnostic, RPC-free surface that two backends must reproduce
identically: the filter enums, the routing-key rules, and their golden
fixtures. **Not** behaviour, I/O, model classes, or anything that pulls in
`const` state-enums / `client` / `central`.
