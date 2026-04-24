# CLAUDE.md - AI Assistant Guide for aiohomematic

This document is the entry point for AI assistants (like Claude) working on the aiohomematic codebase.
It intentionally stays **concise** and delegates deep details to `docs/` — treat the linked documents
as the source of truth and only fall back to this file for orientation.

## Table of Contents

1. [CUxD / CCU-Jack Special Handling](#-critical-cuxdccu-jack-special-handling) (critical)
2. [Project Overview](#project-overview)
3. [Codebase Structure](#codebase-structure)
4. [Development Environment](#development-environment)
5. [Code Quality & Standards](#code-quality--standards)
6. [Testing Guidelines](#testing-guidelines)
7. [Architecture & Design Patterns](#architecture--design-patterns)
8. [Common Development Tasks](#common-development-tasks)
9. [Git Workflow](#git-workflow)
10. [Key Conventions](#key-conventions)
11. [Implementation Policy](#implementation-policy)
12. [Interaction Protocol](#interaction-protocol)
13. [Tips for AI Assistants](#tips-for-ai-assistants)

---

## ⚠️ CRITICAL: CUxD/CCU-Jack Special Handling

> **STOP AND READ THIS BEFORE ANY REFACTORING**
>
> CUxD and CCU-Jack are **NOT** normal Homematic interfaces. They require special handling that has been broken multiple times during AI-assisted refactoring. Before making any changes, run:
>
> ```bash
> pytest tests/contract/test_cuxd_ccu_jack_contract.py -v
> ```

### What Makes CUxD/CCU-Jack Different

| Aspect            | Standard Interfaces (HmIP-RF, BidCos-RF) | CUxD / CCU-Jack                             |
| ----------------- | ---------------------------------------- | ------------------------------------------- |
| **Protocol**      | XML-RPC                                  | JSON-RPC                                    |
| **Ports**         | 2001, 2010, 2000, 2002                   | 80 (HTTP) / 443 (HTTPS)                     |
| **Events**        | XML-RPC Server (push)                    | Polling (default) or MQTT (optional via HA) |
| **Ping/Pong**     | ✅ Yes                                   | ❌ No                                       |
| **Backend Class** | `CcuBackend` or `HomegearBackend`        | `JsonCcuBackend`                            |
| **XML-RPC Proxy** | Required                                 | **NOT used**                                |
| **Capabilities**  | `CCU_CAPABILITIES`                       | `JSON_CCU_CAPABILITIES`                     |

### Key Constants to Check

```python
# In aiohomematic/const.py:

# CUxD/CCU-Jack MUST be in this set:
INTERFACES_REQUIRING_JSON_RPC_CLIENT = frozenset({Interface.CUXD, Interface.CCU_JACK, ...})

# CUxD/CCU-Jack MUST NOT be in these sets:
INTERFACES_REQUIRING_XML_RPC = frozenset({Interface.HMIP_RF, Interface.BIDCOS_RF, ...})
INTERFACES_SUPPORTING_RPC_CALLBACK = frozenset({...})  # Same as XML_RPC
```

### Critical Capability Flags

```python
# In aiohomematic/client/backends/capabilities.py:

JSON_CCU_CAPABILITIES = BackendCapabilities(
    ping_pong=False,      # ❌ NO ping/pong - events via MQTT
    rpc_callback=False,   # ❌ NO XML-RPC callback server
    push_updates=True/False,    # ✅, if Events arrive via MQTT, otherwise ❌
    # All other feature flags = False (no programs, sysvars, etc.)
)
```

### Common Regression Patterns

- **❌ Adding CUxD to XML-RPC interfaces** — breaks CUxD (tries to create XML-RPC proxies)
- **❌ Enabling `ping_pong=True` for JSON backends** — causes false disconnects after 180 s without events
- **❌ Requiring XML-RPC proxy in the factory** — fails for CUxD (no proxy exists)
- **❌ Using a dedicated port** — CUxD/CCU-Jack use JSON-RPC on 80/443, **not** a dedicated port
- **✅ Correct**: check `INTERFACES_REQUIRING_JSON_RPC_CLIENT` first; for those interfaces return a `JsonCcuBackend` and do not require a proxy.

### Refactoring Checklist for CUxD/CCU-Jack

Before committing any changes that touch:

- `aiohomematic/const.py` (interface constants)
- `aiohomematic/client/backends/` (backend factory or capabilities)
- `aiohomematic/client/interface_client.py` (connection checks)
- `aiohomematic/central/coordinators/connection_recovery.py` (recovery logic)

**Run these commands:**

```bash
# 1. CUxD/CCU-Jack contract tests
pytest tests/contract/test_cuxd_ccu_jack_contract.py -v

# 2. Capability contract tests
pytest tests/contract/test_capability_contract.py -v

# 3. Verify interface classification
python -c "from aiohomematic.const import *; print('JSON-RPC only:', INTERFACES_REQUIRING_JSON_RPC_CLIENT - INTERFACES_REQUIRING_XML_RPC)"
# Expected output: JSON-RPC only: frozenset({<Interface.CUXD: 'CUxD'>, <Interface.CCU_JACK: 'CCU-Jack'>})
```

See also: `docs/architecture/protocol_selection_guide.md`.

---

## Project Overview

**aiohomematic** is a modern, async Python library for controlling and monitoring Homematic and HomematicIP
devices. It powers the Home Assistant integration "Homematic(IP) Local".

### Key Characteristics

- **Language**: Python 3.14+
- **Framework**: AsyncIO-based
- **Status**: Production/Stable
- **Type Safety**: Fully typed, mypy strict mode
- **License**: MIT
- **Version**: single source of truth is `aiohomematic/const.py:VERSION` (matches the top entry of `changelog.md`)

### Core Dependencies

```python
aiohttp>=3.12.0         # Async HTTP client
openccu-data>=2026.4.1  # CCU translation/easymode data (extract + custom overrides)
orjson>=3.11.0          # Fast JSON serialization (optional fast extra)
pydantic>=2.10.0        # Data validation using Python type hints
python-slugify>=8.0.0   # URL-safe string conversion
```

CCU-derived translation and easymode metadata is no longer vendored in this
repo; it is loaded at runtime via `importlib.resources` from the
`openccu_data.data` package. Regenerate the artifacts in the
[openccu-data](https://github.com/sukramj/openccu-data) repository and
release a new version when the underlying CCU data changes.

### Project Goals

- Automatic entity discovery from device/channel parameters
- Extensible via custom entity classes for complex devices
- Fast startup through caching of paramsets
- Designed for Home Assistant integration

---

## Codebase Structure

> **Do not hand-maintain a full file tree here** — it drifts within weeks.
> Regenerate a current view on demand:
>
> ```bash
> find aiohomematic -type d -not -path '*__pycache__*' | sort
> ```

### High-level package map

```
aiohomematic/
├── central/         Orchestration: CentralUnit, coordinators, event bus, scheduler,
│                    XML-RPC callback server, device/state registries
│   ├── coordinators/   cache, client, configuration, connection_recovery,
│   │                   device, event, hub, link
│   └── events/         event bus and event type definitions
├── client/          Protocol adapters (InterfaceClient, JSON-RPC, XML-RPC proxy,
│                    circuit breaker, command_retry, command_throttle,
│                    request_coalescer, state_machine)
│   ├── backends/       Backend Strategy implementations (ccu, json_ccu, homegear)
│   └── handlers/       Protocol-specific request handlers
├── model/           Pure domain model (no I/O)
│   ├── custom/         Device-specific types (climate, cover, light, lock, siren,
│   │                   switch, valve, text_display, …) + DeviceProfileRegistry
│   │                   and `capabilities/` mixin package
│   ├── generic/        Generic entity types (binary_sensor, button, number,
│   │                   select, sensor, switch, text, action)
│   ├── hub/            Hub-level entities (programs, sysvars, metrics, inbox,
│   │                   install_mode, connectivity, service/alarm messages, update)
│   ├── calculated/     Derived metrics (climate, voltage level, …)
│   ├── combined/       Multi-parameter writable data points (hs_color, timer)
│   ├── mixins/         Shared domain mixins
│   └── (device, data_point, availability, optimistic, schedule_models,
│        week_profile, week_profile_data_point, …)
├── interfaces/      Protocol definitions for DI (see the module docstring for
│                    the authoritative, categorised protocol list)
├── store/           Persistence & caching
│   ├── persistent/     disk-backed registries (device, paramset, session, incident)
│   ├── dynamic/        in-memory caches (command, data, details, ping_pong)
│   ├── visibility/     parameter filtering rules
│   └── patches/        paramset description patches
├── support/         Cross-cutting utilities (address, file_ops, mixins, text_utils)
├── schemas/         Pydantic schemas (device_description, parameter_description)
├── metrics/         Performance/telemetry emitters, aggregator, stats
├── translations/    Runtime i18n catalogs (en.json, de.json)
├── rega_scripts/    ReGa scripts run on the CCU
└── (top-level modules: api, const, async_support, backend_detection, ccu_translations,
    compat, context, converter, decorators, easymode_data, exceptions, hmcli, i18n,
    logging_context, parameter_tools, property_decorators, tracing, type_aliases, validator)
```

### Companion packages and folders

```
aiohomematic_test_support/   Reusable test infrastructure (factories, mock players,
                             pre-recorded sessions) — separate package config.
tests/                       Main test suite.
  ├── contract/              Contract tests (protocol / capability boundaries,
  │                          CUxD/CCU-Jack, field visibility, event system, …).
  ├── benchmarks/            Micro-benchmarks (cache, circuit breaker, event bus,
  │                          request coalescer).
  └── helpers/               Mock helpers (JSON-RPC, XML-RPC, …).
docs/                        Documentation, organised into subsections — see below.
script/                      Dev scripts (linters, generators, bootstrap, …).
.github/workflows/           CI/CD workflows.
```

### Documentation layout (`docs/`)

- `docs/architecture/` — architecture overview, data flow, event_driven_metrics, protocol_selection_guide, sequence_diagrams, value_resolution, caching
- `docs/adr/` — Architecture Decision Records
- `docs/contributor/` — `contributing.md`, `dev-environment.md`, `git-workflow.md`, `release_process.md`, `coding/` (docstring standards & templates, naming, i18n), `testing/`
- `docs/developer/` — backend_detection, cli_tool, consumer_api, error_handling, extension_points, homeassistant_lifecycle, homematicip_local_api_usage, incident_system
- `docs/reference/` — glossary, common operations, API reference (`api/`)
- `docs/user/` — user-facing device support, HA integration, features, troubleshooting
- `docs/migrations/` — migration guides for breaking changes
- `docs/plans/`, `docs/review/`, `docs/troubleshooting/`, `docs/hooks/`, `docs/includes/` — supporting content

When in doubt, start with `docs/architecture.md` (top-level) or `docs/index.md`.

---

## Development Environment

Detailed setup, prek configuration, dependency installation and CI invocation are documented in
**`docs/contributor/dev-environment.md`**. Only the essentials are repeated here.

### Prerequisites

- Python 3.14+
- `uv` recommended (or pip)
- Git

### Everyday commands

```bash
# Tests
pytest tests/                                   # full suite
pytest --cov=aiohomematic tests/                # with coverage
pytest tests/contract/ -v                       # contract tests only
pytest tests/benchmarks/ -v                     # benchmarks only

# Lint / type / format
prek run --all-files                            # all hooks
ruff check --fix
ruff format
mypy
pylint -j 0 aiohomematic

# Project scripts
python script/sort_class_members.py
python script/check_i18n.py
python script/check_docs_references.py          # docs drift check (see docs/contributor/testing/docs_drift_check.md)
```

---

## Code Quality & Standards

### Type Checking (mypy — STRICT)

This project uses mypy in **strict mode**. All code MUST be fully typed — `disallow_untyped_defs`,
`disallow_incomplete_defs`, `disallow_untyped_calls`, `warn_return_any` are all enabled.

```python
# ✅ fully annotated, keyword-only where appropriate
async def fetch_devices(self, *, include_internal: bool = False) -> dict[str, DeviceDescription]:
    """Fetch all device descriptions."""
    ...

# Use TYPE_CHECKING for import-only type references
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from aiohomematic.central import CentralUnit
```

### Linting (ruff + pylint)

- Target Python 3.14, line length 120
- Enabled rule groups: A, ASYNC, B, C, D, E, F, FLY, G, I, INP, ISC, LOG, PERF, PGH, PIE, PL, PT, PYI, RET, RSE, RUF, S, SIM, SLOT, T, TID, TRY, UP, W

**Imports:** group in four blocks (stdlib → third-party → first-party → `TYPE_CHECKING`).
**Lazy imports are forbidden in production code** — they hide circular dependencies. Use
`TYPE_CHECKING` for forward references instead. Test code (`tests/`) may use lazy imports
where necessary for isolation.

### Style rules that the linters don't catch

- **Keyword-only arguments** for functions with > 2 parameters (enforced partly by `script/lint_kwonly.py`).
- **Pylint R6103 (`consider-using-assignment-expr`)**: use the walrus operator when pylint suggests it.
  ```python
  if (total := self.hits + self.misses) == 0:
      return 100.0
  return (self.hits / total) * 100
  ```
- **`DelegatedProperty` over boilerplate `@property`** for simple read-only attribute delegation.
  Enforced by `script/lint_delegated_property.py`. Full rules (including when _not_ to use it,
  `Kind` assignment and the `Final` typing pattern) live in the module docstring of
  `aiohomematic/property_decorators.py`.

### Docstrings

Full style guide and templates live in `docs/contributor/coding/docstring_standards.md` and
`docs/contributor/coding/docstring_templates.md`. The essentials:

- End every docstring with a period.
- Functions/methods use imperative mood (`"Return …"`, not `"Returns …"`).
- Classes use declarative statements (`"Represent …"`).
- Don't repeat type information in prose.
- Validated by `ruff check --select D`.

---

## Testing Guidelines

### Test layout

```
tests/
├── conftest.py         Shared fixtures and configuration
├── helpers/            Mock servers (XML-RPC, JSON-RPC) and utilities
├── contract/           Contract tests — verify protocol / capability boundaries
├── benchmarks/         Micro-benchmarks
├── aiohomematic_storage/  Pre-recorded storage fixtures
├── fixtures/           Test data
└── test_*.py           Module tests
```

**Contract tests are the primary guardrail for protocol and capability invariants** (e.g. the
CUxD/CCU-Jack differences). New features that touch protocols, capabilities, or state machines
MUST add or update a contract test. See `tests/contract/` and the corresponding guidance in
`docs/adr/0018-contract-tests.md`.

Deeper guidance: `docs/contributor/testing/` (session_playback, testing_with_events, coverage,
debug_data_importance).

### Key fixtures (`tests/conftest.py`)

- `factory_with_ccu_client`, `factory_with_homegear_client` — client factories
- `central_client_factory_with_ccu_client`, `central_client_factory_with_homegear_client` — full central + client
- `session_player_ccu`, `session_player_pydevccu` — session playback
- `central_unit_pydevccu_mini`, `central_unit_pydevccu_full` — virtual CCU instances
- `aiohttp_session`, `mock_xml_rpc_server`, `mock_json_rpc_server`

### Coverage

- Target: 90 %+ for core logic
- Excluded: `aiohomematic/validator.py`, `aiohomematic/exceptions.py`
- Report: `pytest --cov=aiohomematic --cov-report=html tests/`

---

## Architecture & Design Patterns

### Layered architecture

```
┌─────────────────────────────────────────┐
│         Home Assistant / Consumer       │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│         Central (Orchestrator)          │
│  CentralUnit, coordinators, event bus,  │
│  registries, RPC callback server        │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
┌───────▼───┐  ┌──▼────┐  ┌──▼────┐
│  Client   │  │ Model │  │ Store │
│  XML-RPC  │  │Device │  │ Cache │
│  JSON-RPC │  │Data   │  │Persist│
└───────────┘  │Point  │  └───────┘
               └───────┘
```

For the detailed picture (component responsibilities, data flow, sequence diagrams, value
resolution, event-driven metrics) see `docs/architecture/`.

### Integration with Homematic(IP) Local (Home Assistant)

For most interfaces (HmIP-RF, BidCos-RF, BidCos-Wired, VirtualDevices) events arrive via an
XML-RPC callback from the CCU, and connection health is monitored via ping/pong (180 s default
warn interval, `callback_warn_interval`).

CUxD and CCU-Jack are different: events are forwarded via MQTT through Homematic(IP) Local and
delivered through JSON-RPC. There is **no ping/pong**. The safeguard is that both
`is_callback_alive()` and `is_connected()` short-circuit when `capabilities.ping_pong` is false,
regardless of the `push_updates` setting. This prevents false reconnect loops for MQTT-based
interfaces.

Full write-up (including debugging steps) lives in
`docs/developer/homeassistant_lifecycle.md` and `docs/architecture/protocol_selection_guide.md`.

### Key components

- **`central/`** — orchestrates everything: lifecycles, device/data-point creation, scheduler,
  XML-RPC callback server, query facade over the runtime model.
- **`client/`** — protocol adapters. `InterfaceClient` is the unified client; the actual protocol
  work sits in **Backend Strategy** implementations (`CcuBackend`, `JsonCcuBackend`,
  `HomegearBackend`). Command retries, throttling, circuit breaking, and request coalescing are
  separate concerns under `client/`.
- **`model/`** — runtime representation of devices, channels, data points and events. **No I/O.**
  Transforms paramset descriptions into typed data points; supports generic, custom, calculated
  and combined entity types.
- **`store/`** — caches (`persistent/`, `dynamic/`, `visibility/`, `patches/`). Persistent stores
  are disk-backed; dynamic stores live in memory; visibility applies filtering rules.

### Schedule cache (pessimistic update)

Schedule data for climate devices uses a **pessimistic** cache: `set_schedule_*()` writes to the
CCU but does **not** update the local cache. The cache is refreshed by
`reload_and_cache_schedule()` once the CCU signals `CONFIG_PENDING = False`. That guarantees the
cache always matches the CCU state, at the cost of ~0.5–2 s latency. See
`aiohomematic/model/week_profile.py` for the implementation.

### Dependency Injection via Protocols

aiohomematic uses three tiers of protocol-based DI. The authoritative, categorised list of all
protocol interfaces lives in **`aiohomematic/interfaces/__init__.py`** (see its module docstring)
— treat that as the source of truth.

Key principles (see ADR `0002-protocol-based-dependency-injection.md` and
`0003-explicit-over-composite-protocol-injection.md`):

- All protocol names carry the **`…Protocol`** suffix to avoid collisions with implementing
  classes (e.g. `DeviceProtocol` vs. `Device`). Variable names keep semantic suffixes
  (`config_provider: ConfigProviderProtocol`).
- Implementers **must explicitly inherit** from the protocols they implement — structural
  subtyping alone is not enough (mypy catches missing methods at class definition time;
  `@runtime_checkable` isinstance checks work reliably).
- Known exceptions to explicit inheritance are documented inline where they occur
  (`LogContextMixin`, `CalculatedDataPoint`, `CombinedDataPoint`).

### Other patterns

- **Factory** — e.g. `create_data_points_and_events` in `aiohomematic/model/generic/__init__.py`.
- **EventBus (Observer)** — all subscriptions go through `EventBus.subscribe()` with an
  `event_type`, optional `event_key` and `handler`. Every subscription returns an `unsubscribe`
  callable. See `docs/architecture/events/`.
- **Decorators** — `config_property`, `info_property`, `state_property`, `hm_property`,
  `DelegatedProperty` (see `aiohomematic/property_decorators.py`).

### Concurrency

- Async I/O for all network operations.
- The scheduler runs in a dedicated background thread for periodic tasks.
- Shared collections use appropriate locking.

---

## Common Development Tasks

### Adding a new device type

Use the `/add-device` skill — it walks through `DeviceProfileRegistry` registration, the custom
data point class, and the required tests.

### Adding a translation

Use the `/add-translation` skill for the full i18n workflow (`strings.json` → `en.json` sync →
`de.json`). Background: `docs/contributor/coding/i18n_management.md`.

### Updating documentation after refactors

After renaming classes/methods/files, verify that `docs/` still matches reality. Common checks:

```bash
grep -rn "OldClassName\|old_method_name\|old_file.py" docs/
```

Watch for: stale file paths, renamed classes (`XmlRpcProxy` → `AioXmlRpcProxy`), moved event
types, protocol renames. Critical docs to re-scan: `docs/architecture.md`,
`docs/architecture/data_flow.md`, `docs/developer/extension_points.md`,
`docs/architecture/events/`, `docs/architecture/sequence_diagrams.md`.

### Debugging aids

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Session recorder and performance metrics are opt-in:
from aiohomematic.const import OptionalSettings
config = CentralConfig(
    ...,
    optional_settings=(OptionalSettings.SESSION_RECORDER, OptionalSettings.PERFORMANCE_METRICS),
)
```

---

## Git Workflow

Full workflow, branch rules and PR process: **`docs/contributor/git-workflow.md`**.
Release process (tagging, changelog rules): **`docs/contributor/release_process.md`**.

### Essentials

- Main branch: `master` (protected). Development branch: `devel` (protected).
- Feature branches: `feature/<desc>`; fixes: `fix/<desc>`; AI sessions: `claude/claude-md-<session>`.
- Conventional-commit style: `<type>(<scope>): <subject>`.
- Pre-commit hooks (prek): sort-class-members, check-i18n, lint-package-imports,
  lint-all-exports, lint-delegated-property, lint-event-tiers, lint-kwonly, ruff, mypy, pylint,
  codespell, bandit, yamllint. **Do not bypass hooks** (`--no-verify`) except when explicitly
  asked; fix the underlying issue.

---

## Key Conventions

### Documentation language

**All documentation is written in English** — ADRs, technical docs, docstrings, commit messages,
PR descriptions, README, changelog.

### Import aliases (enforced by ruff)

```python
from aiohomematic import central as hmcu
from aiohomematic.central import rpc_server as rpc
from aiohomematic import client as hmcl
from aiohomematic.model.custom import definition as hmed
from aiohomematic.model.custom import data_point as hmce
from aiohomematic.model import data_point as hme
import aiohomematic.support as hms
```

### Naming

- Modules/packages: `snake_case` / `lowercase`.
- Classes: `PascalCase`. **Protocol interfaces: `PascalCase` + `-Protocol` suffix** (see
  `docs/contributor/coding/naming.md`).
- Functions/methods: `snake_case`. Constants: `UPPER_SNAKE_CASE`. Private: leading underscore.
- Variable names keep semantic suffixes (`config_provider`, `client_provider`, …).

#### Intentional camelCase exceptions

Only where the Homematic XML-RPC wire protocol forces it:

- XML-RPC callback methods in `aiohomematic/central/rpc_server.py` (`event`, `newDevices`,
  `deleteDevices`, `updateDevice`, `replaceDevice`, `readdedDevice`, `listDevices`) —
  the CCU calls these by name.
- `SystemEventType` enum values in `aiohomematic/const.py` mirror those backend event names.

### Error handling

Use the custom hierarchy from `aiohomematic/exceptions.py`
(`AioHomematicException`, `ClientException`, `NoConnectionException`, `ValidationException`, …).
Always re-raise with context (`raise ClientException(...) from err`). Deeper guidance:
`docs/developer/error_handling.md`.

### Async patterns

- Prefer `async with` for session/resource lifecycles.
- `asyncio.gather(..., return_exceptions=True)` for parallel fan-out.
- `async with asyncio.timeout(...)` for bounded waits.

### Type hints

- Modern union syntax (`str | None`), `Mapping`/`Sequence` for read-only collections,
  `Final` for constants, `TypeAlias` for complex aliases.
- No `Any` without justification.

---

## Implementation Policy

### Refactoring Completion Checklist

```
□ 1. Clean Code    — no legacy shims, deprecated aliases or compatibility layers
□ 2. Migration     — migration guide in docs/migrations/ (for breaking changes)
□ 3. Tests         — pytest tests/ passes (incl. contract tests for affected areas)
□ 4. Linting       — prek run --all-files passes
□ 5. Changelog     — changelog.md updated (check `git tag` FIRST!)
□ 6. Version Sync  — aiohomematic/const.py:VERSION matches the new changelog entry
```

### Changelog & versioning

Version schema: `YYYY.MM.NN` (running number per month). Full rules:
`docs/contributor/release_process.md`. Non-negotiable procedure:

1. **Check existing tags FIRST** — `git tag --list '2026.04.*' | sort -V | tail -3`.
   Never trust conversation context.
2. Pick the next unused `NN`. **Tagged versions are immutable.**
3. Update `changelog.md` AND `aiohomematic/const.py:VERSION` in the same commit.
4. Verify sync:
   ```bash
   head -1 changelog.md
   grep "^VERSION" aiohomematic/const.py
   ```

### Implementation plan quality

Plans written by Opus/Sonnet MUST be executable by Haiku without questions:

- Every ambiguity resolved upfront (no "TBD" / "decide later").
- Exact file paths, complete code snippets, complete imports.
- Exact locations for edits (line numbers or unique context strings).
- Explicit execution order and dependencies.
- Concrete test cases and expected file locations.

### Clean code policy

Refactorings must not leave legacy around:

- No type aliases for old names, no re-exports of renamed symbols, no deprecation shims, no
  `# TODO: remove after migration` comments.
- Complete migration in one change. Partial migrations are not acceptable.
- When splitting protocols, implementation classes inherit from all sub-protocols directly.
- Update affected docstrings and `docs/*.md`; add a migration guide for downstream consumers
  (e.g. the Home Assistant integration) when the public API changes.

### Quality gate commands

```bash
pytest tests/
prek run --all-files
grep -r "TODO.*migration\|FIXME.*migration\|TODO.*remove\|TODO.*deprecated" aiohomematic/
ruff check --select F401,F841
```

### Migration guide template (`docs/migrations/{feature}_migration_{year}_{month}.md`)

Required sections: Overview · Breaking Changes (with before/after) · Migration Steps ·
Search-and-Replace Patterns · Compatibility Notes. Link from the corresponding changelog entry.

---

## Interaction Protocol

Non-negotiable rules for how the assistant works with the user:

1. **Describe approach before coding** — explain files, approach and trade-offs; wait for
   approval. Trivial edits (typo fixes, single-line changes) may proceed directly.
2. **Clarify ambiguous requirements** — ask before guessing.
3. **Suggest edge cases and tests after implementation** — list what the change covers and what
   is worth testing next.
4. **Bug fixing is test-first** — write a failing reproducer, then fix, then verify nothing else
   broke.
5. **Learn from corrections** — identify the root cause, and update memory when a pattern
   recurs.

---

## Tips for AI Assistants

### Do's

- ✅ Full type annotations on every function/method.
- ✅ Run `prek run --all-files` before committing.
- ✅ Write (or update) tests for every change; add a **contract test** when touching protocols,
  capabilities or state machines.
- ✅ Update docs when public APIs change; re-scan `docs/` after renames.
- ✅ Keyword-only arguments for every parameter except `self`/`cls`.
- ✅ Descriptive variable names and proper exception context.
- ✅ Complete the Refactoring Completion Checklist before finishing.
- ✅ `git tag --list` BEFORE touching `changelog.md`. Tagged versions are immutable.
- ✅ Update `changelog.md` AND `aiohomematic/const.py:VERSION` together.
- ✅ Plans must be Haiku-executable.
- ✅ Describe approach, wait for approval, ask clarifying questions.
- ✅ Suggest edge cases and tests after each change.
- ✅ Fix bugs test-first. Reflect on corrections.

### Don'ts

- ❌ No untyped code or skipped hooks.
- ❌ No direct commits to `master` or `devel`.
- ❌ No `Any` without justification.
- ❌ No I/O in the model layer.
- ❌ No bare `except:`.
- ❌ No changes to `aiohomematic/const.py` without review.
- ❌ No backwards-incompat changes without a major bump + migration guide.
- ❌ No legacy compatibility layers or deprecated aliases.
- ❌ No plans with ambiguities or "TBD".
- ❌ No coding before describing the approach (except trivial edits).
- ❌ No guessing when the requirement is ambiguous.
- ❌ No bug fix without a reproducing test first.

### Refactoring workflow

1. **Describe** the approach, wait for approval.
2. **Clarify** every ambiguity.
3. **Plan** in detail (Haiku-executable).
4. **Implement** exactly as planned.
5. **Clean** — remove every shim/alias.
6. **Test** — `pytest tests/` (incl. contract tests).
7. **Edge cases** — suggest additional tests.
8. **Lint** — `prek run --all-files`.
9. **Document** — `changelog.md`, migration guide if needed, `aiohomematic/const.py:VERSION`.
10. **Verify** — no leftover migration TODOs.

### When in doubt

1. Read `docs/architecture.md` and the relevant `docs/architecture/*`.
2. Look at existing similar code in the codebase.
3. Run the tests (`pytest tests/`, plus `tests/contract/`).
4. Let mypy guide you.
5. Check `changelog.md` for recent context and `docs/migrations/` for patterns.

---

_This file points at `docs/` for anything that would go stale. When in doubt, prefer the linked
document over this summary._
