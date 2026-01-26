# ADR-0019: JSON-RPC Client Plugin Extraction

**Status**: Proposed
**Date**: 2026-01-26
**Author**: Architecture Team

## Context

The aiohomematic library currently includes JSON-RPC client functionality for CUxD and CCU-Jack interfaces directly in the main codebase. This creates several challenges:

1. **Complexity**: The JSON-RPC client (CUxD/CCU-Jack) has different requirements than XML-RPC interfaces
2. **Coupling**: The JSON-RPC code is tightly integrated with the central unit
3. **Maintenance**: Changes to JSON-RPC handling affect the entire codebase
4. **Optional Dependency**: Not all users need CUxD/CCU-Jack support

This ADR proposes extracting the JSON-RPC client infrastructure into a separate plugin package: `aiohomematic-jsonclient`.

## Decision

Extract the JSON-RPC client for CUxD and CCU-Jack interfaces into a separate plugin package with its own:

- State machine (simplified)
- Reconnection logic
- Circuit breaker
- Client implementation

The plugin will be registered with aiohomematic at runtime and loaded on demand when a CUxD or CCU-Jack interface is configured.

---

## Part 1: Current Architecture Analysis

### Components to Extract

The following components are specific to JSON-RPC-only interfaces (CUxD/CCU-Jack):

```
aiohomematic/client/
├── backends/
│   ├── json_ccu.py          # JsonCcuBackend (~250 lines)
│   └── capabilities.py      # JSON_CCU_CAPABILITIES (only the JSON_CCU_CAPABILITIES constant)
```

**Note**: The plugin will contain its own simplified JSON-RPC client implementation,
tailored for the limited operations needed by CUxD/CCU-Jack (no programs, sysvars,
backup, firmware, etc.).

### Shared Components (remain in aiohomematic)

These components are used by CcuBackend (XML-RPC + JSON-RPC hybrid) and must remain:

```
aiohomematic/client/
├── json_rpc.py              # AioJsonRpcAioHttpClient - REQUIRED by CcuBackend for metadata
├── circuit_breaker.py       # CircuitBreaker - used by json_rpc.py
├── state_machine.py         # ClientStateMachine (shared)
├── interface_client.py      # InterfaceClient (facade, shared)
├── config.py                # InterfaceConfig (shared)
├── request_coalescer.py     # RequestCoalescer (shared)
├── rpc_proxy.py             # BaseRpcProxy (XML-RPC only)
├── backends/
│   ├── base.py              # BaseBackend (shared abstract)
│   ├── protocol.py          # BackendOperationsProtocol (shared)
│   ├── ccu.py               # CcuBackend (XML-RPC + JSON-RPC) - uses json_rpc.py
│   └── homegear.py          # HomegearBackend (XML-RPC)
```

**Important**: `json_rpc.py` and `circuit_breaker.py` MUST remain in aiohomematic because
`CcuBackend` uses the JSON-RPC client for metadata operations (rooms, functions, programs,
sysvars, device details, service messages, backup, firmware updates, etc.).

### Current Integration Points

1. **CentralUnit** creates JSON-RPC client via `ClientConfig`
2. **Backend Factory** decides which backend to create based on interface type
3. **InterfaceClient** wraps the backend and provides unified API
4. **EventBus** receives state change events from the client

---

## Part 2: Plugin Architecture Design

### 2.1 Plugin Interface Protocol

```python
# aiohomematic/interfaces/plugin.py

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from aiohomematic.client.backends.protocol import BackendOperationsProtocol
    from aiohomematic.const import Interface


@runtime_checkable
class ClientPluginProtocol(Protocol):
    """Protocol for client plugins that provide backend implementations."""

    @property
    def name(self) -> str:
        """Return the plugin name."""
        ...

    @property
    def version(self) -> str:
        """Return the plugin version."""
        ...

    @property
    def supported_interfaces(self) -> frozenset[Interface]:
        """Return the interfaces this plugin supports."""
        ...

    async def create_backend(
        self,
        *,
        interface: Interface,
        interface_id: str,
        plugin_config: PluginConfig,
    ) -> BackendOperationsProtocol:
        """Create a backend instance for the given interface."""
        ...

    async def start(self) -> None:
        """Start the plugin (initialize resources)."""
        ...

    async def stop(self) -> None:
        """Stop the plugin (cleanup resources)."""
        ...

    @property
    def is_running(self) -> bool:
        """Return True if the plugin is running."""
        ...


@runtime_checkable
class PluginStateObserverProtocol(Protocol):
    """Protocol for observing plugin state changes."""

    def on_plugin_state_changed(
        self,
        *,
        plugin_name: str,
        old_state: PluginState,
        new_state: PluginState,
        reason: str | None = None,
    ) -> None:
        """Called when plugin state changes."""
        ...
```

### 2.2 Plugin Configuration

```python
# aiohomematic/interfaces/plugin.py

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PluginConfig:
    """Configuration passed to plugins during backend creation."""

    # Connection settings
    host: str
    port: int
    username: str
    password: str
    tls: bool
    verify_tls: bool
    device_url: str

    # Session management
    client_session: Any  # aiohttp.ClientSession

    # Dependencies from aiohomematic
    paramset_provider: Any  # ParamsetDescriptionProviderProtocol
    event_bus: Any  # EventBus
    connection_state: Any  # CentralConnectionState
    incident_recorder: Any  # IncidentRecorderProtocol | None
    session_recorder: Any  # SessionRecorder | None

    # Runtime configuration
    has_push_updates: bool
```

### 2.3 Plugin Registry

```python
# aiohomematic/central/plugin_registry.py

from __future__ import annotations

import logging
from typing import Final

from aiohomematic.const import Interface
from aiohomematic.interfaces.plugin import ClientPluginProtocol

_LOGGER: Final = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for client plugins."""

    __slots__ = ("_plugins", "_interface_to_plugin")

    def __init__(self) -> None:
        """Initialize the plugin registry."""
        self._plugins: dict[str, ClientPluginProtocol] = {}
        self._interface_to_plugin: dict[Interface, ClientPluginProtocol] = {}

    def register(self, *, plugin: ClientPluginProtocol) -> None:
        """Register a plugin."""
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin {plugin.name} already registered")

        self._plugins[plugin.name] = plugin

        for interface in plugin.supported_interfaces:
            if interface in self._interface_to_plugin:
                existing = self._interface_to_plugin[interface]
                _LOGGER.warning(
                    "Interface %s already handled by plugin %s, overriding with %s",
                    interface,
                    existing.name,
                    plugin.name,
                )
            self._interface_to_plugin[interface] = plugin

        _LOGGER.info("Registered plugin: %s v%s", plugin.name, plugin.version)

    def unregister(self, *, plugin_name: str) -> None:
        """Unregister a plugin."""
        if plugin_name not in self._plugins:
            return

        plugin = self._plugins.pop(plugin_name)
        for interface in plugin.supported_interfaces:
            if self._interface_to_plugin.get(interface) == plugin:
                del self._interface_to_plugin[interface]

        _LOGGER.info("Unregistered plugin: %s", plugin_name)

    def get_plugin_for_interface(self, *, interface: Interface) -> ClientPluginProtocol | None:
        """Return the plugin handling the given interface, or None."""
        return self._interface_to_plugin.get(interface)

    def has_plugin_for_interface(self, *, interface: Interface) -> bool:
        """Return True if a plugin handles the given interface."""
        return interface in self._interface_to_plugin

    @property
    def plugins(self) -> dict[str, ClientPluginProtocol]:
        """Return all registered plugins."""
        return dict(self._plugins)
```

### 2.4 Plugin State Machine (Simplified)

The plugin will have its own simplified state machine:

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ CREATED │────►│ STARTING│────►│ RUNNING │
└─────────┘     └─────────┘     └────┬────┘
                     │               │
                     ▼               ▼
                ┌─────────┐    ┌──────────┐
                │ FAILED  │◄───│ STOPPING │
                └────┬────┘    └────┬─────┘
                     │              │
                     └───────┬──────┘
                             ▼
                        ┌─────────┐
                        │ STOPPED │
                        └─────────┘
```

---

## Part 3: aiohomematic-jsonclient Package Structure

### 3.1 Package Layout

```
aiohomematic-jsonclient/
├── aiohomematic_jsonclient/
│   ├── __init__.py              # Public API, plugin registration
│   ├── const.py                 # Plugin-specific constants
│   ├── exceptions.py            # Plugin-specific exceptions
│   ├── plugin.py                # JsonClientPlugin implementation
│   ├── client/
│   │   ├── __init__.py
│   │   ├── json_rpc.py          # AioJsonRpcClient (simplified)
│   │   ├── circuit_breaker.py   # CircuitBreaker
│   │   ├── state_machine.py     # PluginStateMachine (simplified)
│   │   └── reconnect.py         # ReconnectionManager
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── json_ccu.py          # JsonCcuBackend
│   │   └── capabilities.py      # JSON_CCU_CAPABILITIES
│   └── py.typed
├── tests/
│   ├── conftest.py
│   ├── test_plugin.py
│   ├── test_json_rpc.py
│   └── test_backend.py
├── pyproject.toml
├── README.md
├── changelog.md
└── .github/
    └── workflows/
        ├── ci.yml
        └── publish.yml
```

### 3.2 Plugin Implementation

```python
# aiohomematic_jsonclient/plugin.py

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from aiohomematic_jsonclient.backend.json_ccu import JsonCcuBackend
from aiohomematic_jsonclient.client.json_rpc import AioJsonRpcClient
from aiohomematic_jsonclient.client.state_machine import PluginStateMachine, PluginState
from aiohomematic_jsonclient.const import PLUGIN_NAME, PLUGIN_VERSION

if TYPE_CHECKING:
    from aiohomematic.client.backends.protocol import BackendOperationsProtocol
    from aiohomematic.const import Interface
    from aiohomematic.interfaces.plugin import PluginConfig

_LOGGER: Final = logging.getLogger(__name__)

# Interfaces handled by this plugin
SUPPORTED_INTERFACES: Final[frozenset[Interface]] = frozenset({
    Interface.CUXD,
    Interface.CCU_JACK,
})


class JsonClientPlugin:
    """Plugin providing JSON-RPC client for CUxD and CCU-Jack interfaces."""

    __slots__ = (
        "_backends",
        "_json_rpc_client",
        "_state_machine",
    )

    def __init__(self) -> None:
        """Initialize the plugin."""
        self._state_machine = PluginStateMachine(plugin_name=PLUGIN_NAME)
        self._json_rpc_client: AioJsonRpcClient | None = None
        self._backends: dict[str, JsonCcuBackend] = {}

    @property
    def name(self) -> str:
        """Return the plugin name."""
        return PLUGIN_NAME

    @property
    def version(self) -> str:
        """Return the plugin version."""
        return PLUGIN_VERSION

    @property
    def supported_interfaces(self) -> frozenset[Interface]:
        """Return the interfaces this plugin supports."""
        return SUPPORTED_INTERFACES

    @property
    def is_running(self) -> bool:
        """Return True if the plugin is running."""
        return self._state_machine.state == PluginState.RUNNING

    async def create_backend(
        self,
        *,
        interface: Interface,
        interface_id: str,
        plugin_config: PluginConfig,
    ) -> BackendOperationsProtocol:
        """Create a backend instance for the given interface."""
        if interface not in SUPPORTED_INTERFACES:
            raise ValueError(f"Interface {interface} not supported by this plugin")

        # Ensure plugin is started
        if not self.is_running:
            await self.start()

        # Create JSON-RPC client if not exists
        if self._json_rpc_client is None:
            self._json_rpc_client = AioJsonRpcClient(
                username=plugin_config.username,
                password=plugin_config.password,
                device_url=plugin_config.device_url,
                client_session=plugin_config.client_session,
                tls=plugin_config.tls,
                verify_tls=plugin_config.verify_tls,
                connection_state=plugin_config.connection_state,
                event_bus=plugin_config.event_bus,
                incident_recorder=plugin_config.incident_recorder,
                session_recorder=plugin_config.session_recorder,
            )

        # Create backend
        backend = JsonCcuBackend(
            interface=interface,
            interface_id=interface_id,
            json_rpc=self._json_rpc_client,
            paramset_provider=plugin_config.paramset_provider,
            has_push_updates=plugin_config.has_push_updates,
        )

        self._backends[interface_id] = backend
        _LOGGER.info("Created backend for %s", interface_id)

        return backend

    async def start(self) -> None:
        """Start the plugin."""
        self._state_machine.transition_to(target=PluginState.STARTING)
        try:
            # Plugin-specific initialization
            self._state_machine.transition_to(target=PluginState.RUNNING)
            _LOGGER.info("Plugin %s started", self.name)
        except Exception as exc:
            self._state_machine.transition_to(
                target=PluginState.FAILED,
                reason=str(exc),
            )
            raise

    async def stop(self) -> None:
        """Stop the plugin and cleanup resources."""
        if self._state_machine.state == PluginState.STOPPED:
            return

        self._state_machine.transition_to(target=PluginState.STOPPING)

        try:
            # Stop all backends
            for backend in self._backends.values():
                await backend.stop()
            self._backends.clear()

            # Stop JSON-RPC client
            if self._json_rpc_client is not None:
                await self._json_rpc_client.stop()
                self._json_rpc_client = None

            self._state_machine.transition_to(target=PluginState.STOPPED)
            _LOGGER.info("Plugin %s stopped", self.name)
        except Exception as exc:
            self._state_machine.transition_to(
                target=PluginState.FAILED,
                reason=str(exc),
            )
            raise
```

### 3.3 Simplified State Machine

```python
# aiohomematic_jsonclient/client/state_machine.py

from __future__ import annotations

from enum import StrEnum
import logging
from typing import Final

_LOGGER: Final = logging.getLogger(__name__)


class PluginState(StrEnum):
    """Plugin lifecycle states."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


_VALID_TRANSITIONS: Final[dict[PluginState, frozenset[PluginState]]] = {
    PluginState.CREATED: frozenset({PluginState.STARTING}),
    PluginState.STARTING: frozenset({PluginState.RUNNING, PluginState.FAILED}),
    PluginState.RUNNING: frozenset({PluginState.STOPPING, PluginState.FAILED}),
    PluginState.STOPPING: frozenset({PluginState.STOPPED, PluginState.FAILED}),
    PluginState.STOPPED: frozenset(),
    PluginState.FAILED: frozenset({PluginState.STARTING}),
}


class PluginStateMachine:
    """Simplified state machine for plugin lifecycle."""

    __slots__ = ("_plugin_name", "_state", "_failure_reason")

    def __init__(self, *, plugin_name: str) -> None:
        """Initialize the state machine."""
        self._plugin_name = plugin_name
        self._state = PluginState.CREATED
        self._failure_reason: str = ""

    @property
    def state(self) -> PluginState:
        """Return current state."""
        return self._state

    @property
    def failure_reason(self) -> str:
        """Return failure reason if in FAILED state."""
        return self._failure_reason

    def can_transition_to(self, *, target: PluginState) -> bool:
        """Check if transition is valid."""
        return target in _VALID_TRANSITIONS.get(self._state, frozenset())

    def transition_to(self, *, target: PluginState, reason: str = "") -> None:
        """Transition to new state."""
        if not self.can_transition_to(target=target):
            raise ValueError(
                f"Invalid transition from {self._state} to {target} for plugin {self._plugin_name}"
            )

        old_state = self._state
        self._state = target

        if target == PluginState.FAILED:
            self._failure_reason = reason
        else:
            self._failure_reason = ""

        _LOGGER.info(
            "PLUGIN_STATE: %s: %s -> %s%s",
            self._plugin_name,
            old_state,
            target,
            f" ({reason})" if reason else "",
        )
```

### 3.4 Reconnection Manager

```python
# aiohomematic_jsonclient/client/reconnect.py

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from aiohomematic_jsonclient.client.json_rpc import AioJsonRpcClient

_LOGGER: Final = logging.getLogger(__name__)

# Reconnection configuration
INITIAL_BACKOFF: Final = 5.0  # seconds
MAX_BACKOFF: Final = 300.0  # 5 minutes
BACKOFF_MULTIPLIER: Final = 2.0


class ReconnectionManager:
    """Manages automatic reconnection for JSON-RPC client."""

    __slots__ = (
        "_client",
        "_current_backoff",
        "_is_running",
        "_max_attempts",
        "_reconnect_task",
    )

    def __init__(
        self,
        *,
        client: AioJsonRpcClient,
        max_attempts: int = 0,  # 0 = unlimited
    ) -> None:
        """Initialize the reconnection manager."""
        self._client = client
        self._max_attempts = max_attempts
        self._current_backoff = INITIAL_BACKOFF
        self._is_running = False
        self._reconnect_task: asyncio.Task[None] | None = None

    async def start_reconnection(self) -> None:
        """Start the reconnection loop."""
        if self._is_running:
            return

        self._is_running = True
        self._current_backoff = INITIAL_BACKOFF
        self._reconnect_task = asyncio.create_task(
            self._reconnection_loop(),
            name="json_rpc_reconnection",
        )

    async def stop_reconnection(self) -> None:
        """Stop the reconnection loop."""
        self._is_running = False
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

    async def _reconnection_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        attempt = 0

        while self._is_running:
            attempt += 1

            if self._max_attempts > 0 and attempt > self._max_attempts:
                _LOGGER.error(
                    "RECONNECT: Max attempts (%d) reached, giving up",
                    self._max_attempts,
                )
                break

            _LOGGER.info(
                "RECONNECT: Attempt %d, waiting %.1f seconds",
                attempt,
                self._current_backoff,
            )

            await asyncio.sleep(self._current_backoff)

            if not self._is_running:
                break

            try:
                if await self._client.is_service_available():
                    _LOGGER.info("RECONNECT: Connection restored after %d attempts", attempt)
                    self._current_backoff = INITIAL_BACKOFF
                    break
            except Exception as exc:
                _LOGGER.debug("RECONNECT: Attempt %d failed: %s", attempt, exc)

            # Exponential backoff
            self._current_backoff = min(
                self._current_backoff * BACKOFF_MULTIPLIER,
                MAX_BACKOFF,
            )

        self._is_running = False
```

---

## Part 4: Integration with aiohomematic

### 4.1 Modified Backend Factory

```python
# aiohomematic/client/backends/factory.py (modified)

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohomematic.const import INTERFACES_REQUIRING_JSON_RPC_CLIENT, Interface

if TYPE_CHECKING:
    from aiohomematic.central.plugin_registry import PluginRegistry
    from aiohomematic.client.backends.protocol import BackendOperationsProtocol
    from aiohomematic.interfaces.plugin import PluginConfig


async def create_backend(
    *,
    interface: Interface,
    interface_id: str,
    version: str,
    plugin_registry: PluginRegistry,
    plugin_config: PluginConfig,
    # ... other parameters for non-plugin backends
) -> BackendOperationsProtocol:
    """Create the appropriate backend based on interface type."""

    # Check if a plugin handles this interface
    if plugin := plugin_registry.get_plugin_for_interface(interface=interface):
        return await plugin.create_backend(
            interface=interface,
            interface_id=interface_id,
            plugin_config=plugin_config,
        )

    # Fall back to built-in backends (CCU, Homegear)
    if interface in INTERFACES_REQUIRING_JSON_RPC_CLIENT:
        raise ValueError(
            f"Interface {interface} requires aiohomematic-jsonclient plugin. "
            "Install it with: pip install aiohomematic-jsonclient"
        )

    # Create XML-RPC backends as before
    # ...
```

### 4.2 Plugin Auto-Discovery

```python
# aiohomematic/central/plugin_discovery.py

from __future__ import annotations

import importlib.metadata
import logging
from typing import Final

from aiohomematic.central.plugin_registry import PluginRegistry
from aiohomematic.interfaces.plugin import ClientPluginProtocol

_LOGGER: Final = logging.getLogger(__name__)

PLUGIN_ENTRY_POINT_GROUP: Final = "aiohomematic.plugins"


def discover_and_register_plugins(*, registry: PluginRegistry) -> None:
    """Discover and register all installed plugins."""
    try:
        entry_points = importlib.metadata.entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    except TypeError:
        # Python < 3.10 compatibility
        eps = importlib.metadata.entry_points()
        entry_points = eps.get(PLUGIN_ENTRY_POINT_GROUP, [])

    for ep in entry_points:
        try:
            plugin_factory = ep.load()
            plugin: ClientPluginProtocol = plugin_factory()
            registry.register(plugin=plugin)
            _LOGGER.info(
                "Auto-discovered plugin: %s v%s from %s",
                plugin.name,
                plugin.version,
                ep.name,
            )
        except Exception as exc:
            _LOGGER.warning(
                "Failed to load plugin from entry point %s: %s",
                ep.name,
                exc,
            )
```

### 4.3 Plugin Entry Point (aiohomematic-jsonclient)

```toml
# aiohomematic-jsonclient/pyproject.toml

[project.entry-points."aiohomematic.plugins"]
jsonclient = "aiohomematic_jsonclient:create_plugin"
```

```python
# aiohomematic_jsonclient/__init__.py

from aiohomematic_jsonclient.plugin import JsonClientPlugin

def create_plugin() -> JsonClientPlugin:
    """Factory function for plugin auto-discovery."""
    return JsonClientPlugin()
```

### 4.4 CentralUnit Integration

```python
# aiohomematic/central/central_unit.py (modified sections)

class CentralUnit:
    """Central unit orchestrating all Homematic communication."""

    def __init__(self, ...) -> None:
        # ...
        self._plugin_registry = PluginRegistry()

        # Auto-discover installed plugins
        discover_and_register_plugins(registry=self._plugin_registry)

    async def stop(self) -> None:
        """Stop the central unit."""
        # ...

        # Stop all plugins
        for plugin in self._plugin_registry.plugins.values():
            try:
                await plugin.stop()
            except Exception as exc:
                _LOGGER.warning("Failed to stop plugin %s: %s", plugin.name, exc)
```

---

## Part 5: Implementation Plan

### Phase 1: Prepare aiohomematic for Plugins (1-2 days)

1. Create plugin protocol interfaces in `aiohomematic/interfaces/plugin.py`
2. Create `PluginRegistry` in `aiohomematic/central/plugin_registry.py`
3. Create plugin discovery mechanism
4. Modify backend factory to support plugin backends
5. Add tests for plugin infrastructure

### Phase 2: Create aiohomematic-jsonclient Package (2-3 days)

1. Initialize new package with proper structure
2. Copy and adapt:
   - `json_rpc.py` → `aiohomematic_jsonclient/client/json_rpc.py`
   - `circuit_breaker.py` → `aiohomematic_jsonclient/client/circuit_breaker.py`
   - `json_ccu.py` → `aiohomematic_jsonclient/backend/json_ccu.py`
   - `capabilities.py` (JSON parts) → `aiohomematic_jsonclient/backend/capabilities.py`
3. Create simplified state machine
4. Create reconnection manager
5. Create plugin implementation
6. Set up pyproject.toml with entry points
7. Copy and adapt CI workflows

### Phase 3: Simplify aiohomematic-jsonclient (1-2 days)

1. Remove dependencies on aiohomematic internals not exposed via protocols
2. Simplify JSON-RPC client (remove CCU-specific methods not used by CUxD/CCU-Jack)
3. Simplify circuit breaker if possible
4. Review and reduce code duplication

### Phase 4: Remove CUxD/CCU-Jack Backend from aiohomematic (1 day)

1. Remove `JsonCcuBackend` from aiohomematic (`backends/json_ccu.py`)
2. Remove `JSON_CCU_CAPABILITIES` from aiohomematic (`backends/capabilities.py`)
3. Update backend factory to delegate to plugin for CUxD/CCU-Jack interfaces
4. Add aiohomematic-jsonclient as optional dependency
5. Keep `json_rpc.py` and `circuit_breaker.py` (required by `CcuBackend` for metadata operations)

### Phase 5: Testing and Documentation (1-2 days)

1. Integration tests with plugin loaded
2. Integration tests without plugin (graceful error)
3. Update documentation
4. Update CLAUDE.md
5. Create migration guide

---

## Part 6: Benefits and Trade-offs

### Benefits

1. **Separation of Concerns**: JSON-RPC functionality isolated in its own package
2. **Optional Installation**: Users not using CUxD/CCU-Jack don't need the extra code
3. **Independent Versioning**: Plugin can be versioned separately
4. **Simplified Maintenance**: Changes to JSON-RPC don't affect core library
5. **Extensibility**: Other plugins can be created for different backends

### Trade-offs

1. **Additional Package**: Users needing CUxD/CCU-Jack must install extra package
2. **Version Coordination**: Plugin version must be compatible with aiohomematic version
3. **Additional Complexity**: Plugin infrastructure adds some complexity
4. **Testing Overhead**: Need to test both with and without plugin

### Risk Mitigation

1. **Breaking Changes**: Document protocol versions clearly
2. **Compatibility**: Use semantic versioning and compatibility ranges
3. **Discovery Issues**: Provide clear error messages when plugin is missing
4. **Performance**: Plugin loading is lazy (on-demand)

---

## Part 7: Code Simplification Opportunities

The plugin will contain its **own simplified JSON-RPC client** (`AioJsonRpcClient`), separate
from aiohomematic's `AioJsonRpcAioHttpClient`. This allows the plugin to be much smaller
since CUxD/CCU-Jack only need a subset of JSON-RPC operations.

**Key insight**: aiohomematic's `json_rpc.py` (~2100 lines) stays in aiohomematic for
`CcuBackend`, while the plugin gets a new, minimal implementation (~800 lines).

### 7.1 Plugin JSON-RPC Client (New Implementation)

Methods to **keep** (used by CUxD/CCU-Jack):

- `is_present()` - connection check
- `list_devices()` - device discovery
- `get_paramset()` - read paramsets
- `get_paramset_description()` - metadata
- `get_value()` - read values
- `set_value()` - write values
- Session management (login, renew, logout)

Methods to **remove** (not used by CUxD/CCU-Jack):

- `get_all_programs()` - programs not supported
- `get_all_system_variables()` - sysvars not supported
- `set_system_variable()` - sysvars not supported
- `execute_program()` - programs not supported
- `get_device_details()` - metadata not supported
- `get_service_messages()` - service messages not supported
- `download_backup()` / `create_backup_*()` - backup not supported
- `download_firmware()` / `trigger_firmware_update()` - firmware not supported
- `rename_device()` / `rename_channel()` - rename not supported
- `get_inbox_devices()` / `accept_device_in_inbox()` - inbox not supported
- `set_install_mode_hmip()` - install mode not supported
- All ReGa script methods

### 7.2 Plugin Size Estimate

| Component         | aiohomematic (stays) | Plugin (new)    |
| ----------------- | -------------------- | --------------- |
| JSON-RPC client   | ~2100 lines          | ~800 lines      |
| Circuit breaker   | ~200 lines           | ~150 lines      |
| JsonCcuBackend    | ~250 lines           | ~250 lines      |
| State machine     | N/A                  | ~100 lines      |
| Reconnect manager | N/A                  | ~100 lines      |
| **Total**         | **stays unchanged**  | **~1400 lines** |

The plugin is approximately **~1400 lines** of new/adapted code, providing a
lightweight JSON-RPC client specifically for CUxD/CCU-Jack interfaces.

---

## Conclusion

The plugin extraction provides a clean separation of the JSON-RPC client infrastructure while maintaining compatibility with existing integrations. The plugin architecture is extensible and allows for future backends to be added without modifying the core library.

## References

- [aiohomematic Architecture](../architecture.md)
- [Backend Strategy Pattern](../data_flow.md)
- [Plugin Entry Points (PEP 660)](https://peps.python.org/pep-0660/)
