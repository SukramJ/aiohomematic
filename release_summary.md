# Version 2025.11.07 -

## What's Changed

### Connection Recovery

- **Unified Recovery Architecture**: New event-driven connection recovery coordinator
  - Staged recovery process: TCP check → RPC check → Warmup → Stability check → Reconnect
  - Automatic retry with exponential backoff (max 8 attempts)
  - Parallel recovery support for multi-interface setups
- **Fixed Authentication Errors**: JSON-RPC sessions are now cleared when recovery starts
  - Prevents "access denied" errors after CCU restarts
- **Device Inbox at Startup**: Inbox sensor now available immediately after integration start
- **Repair Issues Restored**: Delayed device creation again triggers repair issues in HA

### Observability & Metrics

- **Complete Event-Driven Metrics**: All components now emit metric events to EventBus instead of maintaining local state
  - `MetricsObserver` aggregates latency, counter, gauge, and health metrics in real-time
  - Type-safe `MetricKey` dataclass with `MetricKeys` factory for all known metrics
  - `emit_latency()`, `emit_counter()`, `emit_gauge()`, `emit_health()` functions for easy metric emission
  - Dedicated `aiohomematic/metrics/` module with clean separation of concerns
- **Comprehensive System Events**: New events for complete system observability
  - Connection state changes with reason tracking
  - Cache invalidation and refresh events
  - Circuit breaker state transitions and trip notifications
  - Scheduler task execution and data refresh events
  - Request coalescing events for performance monitoring
- **Self-Healing Recovery**: Automatic data refresh after circuit breaker recovery
- **Migrated Components**: All core components use emit-only pattern
  - `PingPongCache`: Emits RTT latency per interface
  - `CentralDataCache`: Emits cache hit/miss counters
  - `CircuitBreaker`: Emits success/failure/rejection counters
  - `@inspector`: Emits service call latency and error counts (global registry deprecated)
  - `HealthTracker`: Emits client health events
- **Hub Metrics Sensors**: Three HA-visible sensors for real-time system monitoring:
  - System Health (0-100%)
  - Connection Latency (ms)
  - Last Event Age (seconds since last CCU event)
- **RPC Monitoring**: Track success/failure rates, latency, and request coalescing effectiveness
- **Cache Statistics**: View hit rates and sizes across all caches

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

- **Cover/Dimmer Restart**: Fixed `is_valid` returning False after CCU restart when status is UNKNOWN
- **Empty Numeric Values**: Fixed conversion error when CCU sends empty strings for FLOAT/INTEGER parameters
- **RGBW/LSC Auto-Off**: Fixed lights turning off unexpectedly when using transition times
- **Reconnect Availability**: Entities no longer remain unavailable after CCU reconnect
- **STATUS Parameters**: Fixed handling of integer values from backend for status updates
- **Firmware Updates**: Fixed firmware data not refreshing after update check

### New Device Support

- **HmIP-MP3P Kombisignalgeber**: Sound player with MP3 playback (channel 2) and RGB LED control (channel 6)
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
- Event-driven test patterns with `EventCapture` fixture for behavior verification through events
