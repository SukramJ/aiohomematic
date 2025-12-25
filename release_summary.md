# Version 2025.11.07 -

## What's Changed

### Connection Reliability

- **Improved Reconnection**: New state machine architecture for faster, more reliable recovery after CCU restarts
- **CircuitBreaker**: Automatic protection against repeated connection failures with staged reconnection
- **Reduced Log Noise**: Less ERROR logging during expected reconnection scenarios

### Device Management

- **Device Inbox**: Accept and rename new devices pending pairing directly from the integration
- **Install Mode**: Separate install mode control per interface (HmIP-RF and BidCos-RF) with countdown timer
- **Backup Support**: Create and download CCU system backups, firmware download and update triggers

### Climate & Schedules

- **Schedule Caching**: Faster schedule operations with intelligent caching
- **Simple Schedule Format**: Easier to read and modify weekly heating schedules
- **Schedule Sync**: Bidirectional get/set schedule operations with filtered data format

### Siren Control

- **Visible Alarm Settings**: Acoustic and optical alarm selection now available as controllable entities
- **Flexible Turn-On**: Siren activation uses entity values as defaults when service parameters omitted

### Bug Fixes

- **RGBW/LSC Auto-Off**: Fixed lights turning off unexpectedly when using transition times
- **Reconnect Availability**: Entities no longer remain unavailable after CCU reconnect
- **STATUS Parameters**: Fixed handling of integer values from backend for status updates
- **Firmware Updates**: Fixed firmware data not refreshing after update check

### New Device Support

- **HmIP-WRCD Text Display**: Wall-mount Remote Control with Display - send text, icons, colors, and sounds to the LCD
- DeviceProfileRegistry for centralized device-to-profile mappings
- DpActionSelect data point type for write-only selection parameters

### Developer Experience

- **Fluent Configuration**: New `CentralConfigBuilder` with method chaining and factory presets for CCU/Homegear
- **Request Tracing**: Context variables pattern for request tracking through async call chains with automatic log prefixing
- **Type Converters**: Extensible `to_homematic_value()` / `from_homematic_value()` using singledispatch pattern

### Internal Improvements

- Protocol-based architecture for better testability and decoupling
- Event bus system replacing legacy callback patterns
- Strict type checking throughout codebase
- Translatable log messages and exceptions
- Generic protocols for improved mypy type inference on data point values
- Declarative field descriptors for custom and calculated data points
- `DelegatedProperty` descriptor for simple property delegation with caching support
- Enhanced linter with DP004 path validation for DelegatedProperty definitions
- Store package restructured into `persistent/` and `dynamic/` subpackages for better maintainability
- Typed dataclasses (`CachedCommand`, `PongTracker`) replace untyped tuples and dicts
