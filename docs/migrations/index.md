# Migration Guides

This section contains guides for upgrading between major versions of aiohomematic and handling breaking changes.

## Current Version

The current version is documented in the [Changelog](../changelog.md).

## Migration Philosophy

aiohomematic follows these principles for breaking changes:

1. **Minimize breaking changes** - Prefer deprecation warnings before removal
2. **Clear documentation** - Document all breaking changes with migration paths
3. **Semantic versioning** - Major version bumps for breaking API changes

## Breaking Changes by Version

### 2026.x

No breaking changes in 2026 releases so far.

### 2025.x

The 2025 series introduced the modern EventBus-based architecture:

| Version | Change                             | Migration                    |
| ------- | ---------------------------------- | ---------------------------- |
| 2025.12 | EventBus replaces legacy callbacks | Use `subscribe_to_*` methods |
| 2025.11 | Protocol-based DI throughout       | Update custom extensions     |

## Common Migration Tasks

### Updating Event Subscriptions

**Old pattern (legacy):**

```python
# Legacy callback registration
central.register_callback(handler_func)
```

**New pattern (recommended):**

```python
from aiohomematic.central.events import DataPointValueReceivedEvent

async def handler(*, event: DataPointValueReceivedEvent) -> None:
    print(event.value)

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    handler=handler,
)
```

### Updating Protocol Imports

**Old pattern:**

```python
from aiohomematic.central import CentralUnit
# Using CentralUnit directly as dependency
```

**New pattern:**

```python
from aiohomematic.interfaces import (
    CentralInfoProtocol,
    DeviceProviderProtocol,
)

# Use protocol interfaces for dependencies
class MyComponent:
    def __init__(
        self,
        *,
        central_info: CentralInfoProtocol,
        device_provider: DeviceProviderProtocol,
    ) -> None:
        ...
```

## Deprecation Warnings

When a feature is deprecated, you'll see warnings in the logs. These indicate:

1. **What** is deprecated
2. **Why** it's being removed
3. **What** to use instead
4. **When** it will be removed

Example:

```
DeprecationWarning: register_callback() is deprecated since 2025.11.
Use event_bus.subscribe() instead. Will be removed in 2026.1.
```

## Testing After Migration

After migrating:

1. **Run tests**: `pytest tests/`
2. **Check logs**: Look for deprecation warnings
3. **Verify functionality**: Test core use cases

## Getting Help

If you encounter issues during migration:

1. Check the [Changelog](../changelog.md) for detailed notes
2. Search [GitHub Issues](https://github.com/sukramj/aiohomematic/issues)
3. Ask in [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions)

## Related Documentation

- [Changelog](../changelog.md) - Version history
- [Consumer API](../developer/consumer_api.md) - Current API patterns
- [Event System](../architecture/events/index.md) - Modern event handling
