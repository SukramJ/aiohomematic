# ADR 0011: Storage Abstraction Layer

## Status

Implemented

---

## Context

aiohomematic requires persistent storage for device descriptions, paramset descriptions, and session recordings. The library can run standalone or integrated within Home Assistant. To support both scenarios with a unified API, a storage abstraction layer was introduced.

### Design Goals

1. **Single Point of Responsibility**: All file I/O operations handled by one component
2. **Exchangeability**: Home Assistant Store and local file storage must be interchangeable
3. **Factory Pattern**: Dependency injection via factory for flexible storage backends
4. **Protocol-Based**: DuckTyping-compatible interfaces using Python Protocols

---

## Decision

Implement a **storage abstraction layer** with protocol-based dependency injection:

1. **StorageProtocol**: Interface defining load/save operations
2. **StorageFactoryProtocol**: Factory interface for creating storage instances
3. **LocalStorageFactory**: Default file-based implementation for standalone usage
4. **HAStoreFactory**: Home Assistant implementation (provided by integration)

### Key Principle

All persistent caches depend on `StorageProtocol`, not concrete implementations. This enables seamless swapping between local files and Home Assistant Store.

---

## Architecture

### High-Level Structure

```
┌──────────────────────┐
│ HomematicIP Local    │
│  └─ HAStoreFactory   │ ← Home Assistant provides factory
└──────────┬───────────┘
           │ StorageFactoryProtocol
           ↓
┌──────────────────────┐
│ aiohomematic         │
│  ├─ StorageProtocol  │ ← Protocol interface
│  ├─ Storage (local)  │ ← Default implementation
│  └─ Persistent Caches│ ← Use StorageProtocol
└──────────────────────┘
```

### Protocol Hierarchy

```
StorageFactoryProtocol
    │
    ├── create_storage() → StorageProtocol
    │                           │
    │                           ├── load()
    │                           ├── save()
    │                           ├── delay_save()
    │                           ├── flush()
    │                           └── remove()
    │
    └── cleanup_files() → int (files deleted)
```

### Storage Features

**LocalStorageFactory features:**

- **orjson Serialization**: Fast JSON encoding/decoding
- **Atomic Writes**: Write to temp file, then rename for crash safety
- **ZIP Support**: Load data from `.json.zip` archives
- **Version Migrations**: Automatic schema migration via `migrate_func`
- **Delayed Saves**: Debounced save operations to batch rapid updates
- **Thread Safety**: All operations protected by asyncio.Lock

---

## Integration Points

### CentralConfig

```python
@dataclass(slots=True)
class CentralConfig:
    # ... other fields ...
    storage_factory: StorageFactoryProtocol | None = None
```

**Standalone usage** (no factory provided):

- CentralConfig creates `LocalStorageFactory` automatically
- Storage location: `{base_directory}/{central_name}/`

**Home Assistant integration** (factory provided):

- Integration creates `HAStoreFactory(hass)`
- Passes via `storage_factory` parameter
- Storage handled by Home Assistant's Store helper

### CacheCoordinator

```python
class CacheCoordinator:
    def __init__(
        self,
        *,
        storage_factory: StorageFactoryProtocol,
        # ... other dependencies ...
    ) -> None:
        # Create storage instances for each cache
        device_storage = storage_factory.create_storage(
            key=FILE_DEVICES,
            sub_directory=SUB_DIRECTORY_CACHE,
        )
        self._device_descriptions_cache = DeviceDescriptionCache(
            storage=device_storage,
            config_provider=config_provider,
        )
```

### Persistent Cache Classes

All persistent caches inherit from `BasePersistentCache`:

| Cache                         | Purpose                   | Storage Key           |
| ----------------------------- | ------------------------- | --------------------- |
| `DeviceDescriptionRegistry`   | Device/channel metadata   | `homematic_devices`   |
| `ParamsetDescriptionRegistry` | Parameter metadata        | `homematic_paramsets` |
| `SessionRecorder`             | RPC session recordings    | Dynamic per-session   |
| `IncidentStore`               | Diagnostics and incidents | `incidents`           |

**BasePersistentCache provides:**

- Hash-based change detection for efficient saves
- Async load/save operations via StorageProtocol
- Optional caching control via config

---

## Usage Patterns

### Standalone Mode

```python
from aiohomematic.central import CentralConfig

config = CentralConfig(
    name="ccu-main",
    host="192.168.1.100",
    # ... other config ...
    # storage_factory is None → LocalStorageFactory created automatically
)

# Storage location: {base_directory}/ccu-main/
```

### Home Assistant Integration

```python
from aiohomematic.store.storage import StorageFactoryProtocol

class HAStoreFactory:
    """Factory using Home Assistant's Store."""

    def create_storage(self, *, key: str, **kwargs) -> StorageProtocol:
        return HAStoreWrapper(hass=self.hass, key=key, ...)

# Pass to CentralConfig
config = CentralConfig(
    # ... other config ...
    storage_factory=HAStoreFactory(hass=hass),
)
```

---

## Consequences

### Benefits

✅ **Single Responsibility**: All file I/O centralized in Storage class
✅ **Exchangeability**: HA Store or local storage transparently swappable
✅ **Testability**: Storage easily mocked in tests
✅ **Consistency**: Unified API for all caches
✅ **Future-Proof**: Additional storage backends easily addable (e.g., remote storage, cloud)

### Trade-offs

⚠️ **Additional Abstraction**: One more layer between cache and filesystem
⚠️ **Protocol Overhead**: Runtime protocol checks add minimal overhead (negligible in practice)

### Neutral

ℹ️ **No Breaking Changes**: Internal refactoring, public API unchanged
ℹ️ **Transparent to Users**: Storage backend selection happens automatically

---

## Alternatives Considered

### Alternative 1: Direct File I/O in Caches

Let each cache handle its own file operations directly.

**Rejected**:

- No way to swap backends for Home Assistant
- Duplicated file handling logic across caches
- Hard to test without actual filesystem

### Alternative 2: Adapter Pattern per Backend

Create adapters like `LocalStorageAdapter`, `HAStorageAdapter`.

**Rejected**:

- Essentially what we have, but "Adapter" is less clear than "Factory"
- Factory pattern better communicates intent (creating storage instances)

### Alternative 3: Abstract Base Class Instead of Protocol

Use ABC with abstract methods instead of runtime-checkable Protocol.

**Rejected**:

- Forces inheritance coupling
- Protocol allows structural subtyping (more flexible)
- Home Assistant implementation doesn't need to import from aiohomematic

---

## Implementation

**Status:** ✅ Implemented

### Core Module

**`aiohomematic/store/storage.py`**

- `StorageProtocol` - Protocol interface
- `StorageFactoryProtocol` - Factory protocol
- `Storage` - Local file-based implementation
- `LocalStorageFactory` - Default factory

### Protocol Interfaces

**StorageProtocol methods:**

```python
@property def key(self) -> str
@property def version(self) -> int
async def load(self) -> dict[str, Any] | None
async def save(*, data: dict[str, Any]) -> None
async def delay_save(*, data_func: Callable, delay: float) -> None
async def flush() -> None
async def remove() -> None
```

**StorageFactoryProtocol methods:**

```python
def create_storage(*, key: str, version: int, sub_directory: str | None, migrate_func: MigrateFunc | None) -> StorageProtocol
async def cleanup_files(*, sub_directory: str | None) -> int
```

### Updated Components

**`aiohomematic/store/persistent/base.py`**

- `BasePersistentCache` - Base class for all persistent caches
- Subclasses: `DeviceDescriptionRegistry`, `ParamsetDescriptionRegistry`, `SessionRecorder`, `IncidentStore`

**`aiohomematic/central/config.py`**

- `CentralConfig.storage_factory` parameter
- Auto-creation of `LocalStorageFactory` when None

**`aiohomematic/central/coordinators/cache.py`**

- `CacheCoordinator` creates storage instances via factory
- Passes storage to cache constructors

For detailed API documentation, see docstrings in:

- `aiohomematic/store/storage.py`
- `aiohomematic/store/persistent/base.py`

---

## References

- [Home Assistant Storage Helper](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/storage.py) - HA Store implementation reference
- [ADR 0015: Description Data Normalization](0015-description-normalization-concept.md) - Schema versioning strategy
- `aiohomematic/store/` - Store module implementation

---

_Created: 2025-12-31_
_Author: Architecture Review_
