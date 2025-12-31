# ADR 0007: Storage Abstraction Layer

## Status

Implemented

## Context

aiohomematic requires persistent storage for device descriptions, paramset descriptions, and session recordings. The library can run standalone or integrated within Home Assistant. To support both scenarios with a unified API, a storage abstraction layer was introduced.

### Design Goals

1. **Single Point of Responsibility**: All file I/O operations handled by one component
2. **Exchangeability**: Home Assistant Store and local file storage must be interchangeable
3. **Factory Pattern**: Dependency injection via factory for flexible storage backends
4. **Protocol-Based**: DuckTyping-compatible interfaces using Python Protocols

---

## Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    HomematicIP Local                            │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │  HAStoreFactory     │    │  HomeAssistant Store            │ │
│  │  (implements        │───▶│  (native HA persistence)        │ │
│  │  StorageFactory     │    └─────────────────────────────────┘ │
│  │  Protocol)          │                                        │
│  └─────────────────────┘                                        │
└───────────────┬─────────────────────────────────────────────────┘
                │ passes storage_factory
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      aiohomematic                               │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │  StorageProtocol    │    │  Storage                        │ │
│  │  (interface)        │───▶│  (local implementation)         │ │
│  │                     │    │  - orjson serialization         │ │
│  └─────────────────────┘    │  - async I/O                    │ │
│                             │  - ZIP loading support          │ │
│  ┌─────────────────────┐    │  - version migrations           │ │
│  │  LocalStorageFactory│    │  - delayed/debounced saves      │ │
│  │  (default impl)     │───▶└─────────────────────────────────┘ │
│  └─────────────────────┘                                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Persistent Caches                                          ││
│  │  - DeviceDescriptionCache                                   ││
│  │  - ParamsetDescriptionCache                                 ││
│  │  - SessionRecorder                                          ││
│  │  ──────────────────────────────────────────                 ││
│  │  All use Storage via StorageFactoryProtocol                 ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation

### Core Components

#### StorageProtocol (`aiohomematic/store/storage.py`)

Defines the interface for storage operations:

```python
@runtime_checkable
class StorageProtocol(Protocol):
    """Protocol for storage operations."""

    @property
    def key(self) -> str:
        """Return the storage key identifier."""
        ...

    @property
    def version(self) -> int:
        """Return the storage version for migration support."""
        ...

    async def load(self) -> dict[str, Any] | None:
        """Load data from storage (with migration if needed)."""
        ...

    async def save(self, *, data: dict[str, Any]) -> None:
        """Save data to storage immediately."""
        ...

    async def delay_save(
        self,
        *,
        data_func: Callable[[], dict[str, Any]],
        delay: float = 1.0,
    ) -> None:
        """Schedule a delayed save operation."""
        ...

    async def flush(self) -> None:
        """Flush any pending delayed saves immediately."""
        ...

    async def remove(self) -> None:
        """Remove storage data."""
        ...
```

#### StorageFactoryProtocol

Factory interface for creating storage instances:

```python
@runtime_checkable
class StorageFactoryProtocol(Protocol):
    """Protocol for creating storage instances."""

    def create_storage(
        self,
        *,
        key: str,
        version: int = 1,
        sub_directory: str | None = None,
        migrate_func: MigrateFunc | None = None,
    ) -> StorageProtocol:
        """Create a storage instance."""
        ...

    async def cleanup_files(
        self,
        *,
        sub_directory: str | None = None,
    ) -> int:
        """Delete all storage files. Returns number of files deleted."""
        ...
```

#### Storage Class

Local file-based storage implementation with the following features:

- **orjson Serialization**: Fast JSON serialization/deserialization
- **Atomic Writes**: Write to temp file, then rename for crash safety
- **ZIP Support**: Load data from `.json.zip` archives
- **Version Migrations**: Automatic schema migration via `migrate_func`
- **Delayed Saves**: Debounced save operations to batch rapid updates
- **Thread Safety**: All operations protected by asyncio.Lock

#### LocalStorageFactory

Default factory for standalone usage:

```python
factory = LocalStorageFactory(
    base_directory="/path/to/storage",
    central_name="my-ccu",
    task_scheduler=looper,
)

storage = factory.create_storage(
    key="homematic_devices",
    version=1,
    sub_directory="cache",
)
```

### Persistent Cache Classes

All persistent caches inherit from `BasePersistentCache`:

#### BasePersistentCache (`aiohomematic/store/persistent/base.py`)

Abstract base class providing:

- Hash-based change detection for efficient saves
- Async load/save operations via Storage
- Optional caching control via config

Subclasses implement:

- `_create_empty_content()`: Define initial data structure
- `_process_loaded_content()`: Rebuild indexes after load

#### Concrete Implementations

| Cache                      | Purpose                 | Storage Key           |
| -------------------------- | ----------------------- | --------------------- |
| `DeviceDescriptionCache`   | Device/channel metadata | `homematic_devices`   |
| `ParamsetDescriptionCache` | Parameter metadata      | `homematic_paramsets` |
| `SessionRecorder`          | RPC session recordings  | Dynamic per-session   |

### Integration Points

#### CacheCoordinator

Creates all caches with storage instances:

```python
class CacheCoordinator:
    def __init__(
        self,
        *,
        storage_factory: StorageFactoryProtocol,
        # ... other dependencies ...
    ) -> None:
        device_storage = storage_factory.create_storage(
            key=FILE_DEVICES,
            sub_directory=SUB_DIRECTORY_CACHE,
        )
        self._device_descriptions_cache = DeviceDescriptionCache(
            storage=device_storage,
            config_provider=config_provider,
        )
        # ... other caches ...
```

#### CentralConfig

Accepts optional storage factory for Home Assistant integration:

```python
@dataclass(slots=True)
class CentralConfig:
    # ... other fields ...
    storage_factory: StorageFactoryProtocol | None = None
```

When no factory is provided, `LocalStorageFactory` is created automatically.

---

## File Structure

```
aiohomematic/
├── store/
│   ├── __init__.py              # Re-exports including Storage
│   ├── storage.py               # Storage, LocalStorageFactory, Protocols
│   ├── types.py                 # Type definitions
│   ├── serialization.py         # Serialization utilities
│   ├── persistent/
│   │   ├── __init__.py
│   │   ├── base.py              # BasePersistentCache
│   │   ├── device.py            # DeviceDescriptionCache
│   │   ├── paramset.py          # ParamsetDescriptionCache
│   │   └── session.py           # SessionRecorder
│   ├── dynamic/                 # In-memory caches
│   └── visibility/              # Parameter visibility
├── central/
│   ├── config.py                # CentralConfig with storage_factory
│   └── coordinators/
│       └── cache.py             # CacheCoordinator
└── model/
    └── device.py                # _DefinitionExporter uses Storage
```

---

## Usage Examples

### Standalone Usage

```python
from aiohomematic.central import CentralConfig

config = CentralConfig(
    name="ccu-main",
    host="192.168.1.100",
    # ... other config ...
    # storage_factory is None -> LocalStorageFactory created automatically
)
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

1. **Single Responsibility**: All file I/O centralized in Storage class
2. **Exchangeability**: HA Store or local storage transparently swappable
3. **Testability**: Storage easily mocked in tests
4. **Consistency**: Unified API for all caches
5. **Future-Proof**: Additional storage backends easily addable

### Trade-offs

1. **Additional Abstraction**: One more layer between cache and filesystem
2. **Protocol Overhead**: Runtime protocol checks add minimal overhead

---

## References

- [Home Assistant Storage Helper](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/storage.py)
- [aiohomematic Store Module](../../aiohomematic/store/)

---

_Created: 2025-12-31_
_Author: Architecture Review_
