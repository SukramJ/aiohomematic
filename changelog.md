# Version 2025.12.30 (2025-12-15)

## What's Changed

### Breaking Changes

- Rename Protocol classes to follow `-Protocol` suffix convention:
  - `StateChangeCallback` → `StateChangeCallbackProtocol`
  - `HealthRecordCallback` → `HealthRecordCallbackProtocol`
  - `SyncEventHandler` → `SyncEventHandlerProtocol`
  - `AsyncEventHandler` → `AsyncEventHandlerProtocol`

### Bug Fixes

- Fix typo in enum name: `CalulatedParameter` → `CalculatedParameter`

### Improvements

- Document intentional camelCase exceptions for RPC callbacks in CLAUDE.md

# Version 2025.12.29 (2025-12-15)

## What's Changed

### Bug Fixes

- Fix event publication

# Version 2025.12.28 (2025-12-14)

## What's Changed

### Bug Fixes

- Fix central incorrectly transitioning to RUNNING during startup with empty client list: `all()` returns True for empty iterables, causing premature RUNNING state before clients are registered
- Fix central incorrectly transitioning to DEGRADED when all clients are connected: Missing `not all_connected` check in `start()` method allowed transition to DEGRADED even when all clients were CONNECTED
- Fix scheduler not starting when central is in DEGRADED state: Now starts when central is operational (RUNNING or DEGRADED)
- Fix HealthTracker not tracking clients: Clients were never registered with the health tracker after creation, causing `update_client_health()` to be a no-op. Now clients are properly registered during `start()` and unregistered during `stop()`

### Improvements

- Enhance state transition logging:

  - DEGRADED state now shows which clients are not connected (e.g., "clients not connected: Otto-Dev-929-BidCos-RF")
  - Client state machine now includes reason in log messages (e.g., "proxy initialized", "connection check failed")
  - Important client transitions (CONNECTED, DISCONNECTED, FAILED) now log at INFO level
  - Scheduler waiting message now shows current state

- Automatic health data updates:
  - Events received from backend now automatically update `last_event_received` in health tracker
  - RPC request success/failure automatically tracked via circuit breaker callbacks
  - Health tracker now provides accurate `can_receive_events`, `consecutive_failures`, `last_successful_request`, `last_failed_request` metrics

# Version 2025.12.27 (2025-12-14)

## What's Changed

### Bug Fixes

- Fix firmware data not updating after refresh: Device descriptions cache was not being updated for existing devices during `refresh_firmware_data()` calls (both ad-hoc service calls and periodic checks). The cache update was skipped because the code incorrectly returned early when no "new" devices were found, even though existing device descriptions needed updating.

# Version 2025.12.26 (2025-12-14)

## What's Changed

### Breaking Changes

- Replace 9 legacy events with 4 focused integration events:
  - Remove `SystemEventTypeData` - replaced by `DeviceLifecycleEvent` and `DataPointsCreatedEvent`
  - Remove `CallbackStateChangedEvent` - replaced by `SystemStatusEvent.callback_state`
  - Remove `CentralStateChangedEvent` - replaced by `SystemStatusEvent.central_state`
  - Remove `ClientStateChangedEvent` - replaced by `SystemStatusEvent.client_state`
  - Remove `ConnectionStateChangedEvent` - replaced by `SystemStatusEvent.connection_state`
  - Remove `DeviceAvailabilityChangedEvent` - replaced by `DeviceLifecycleEvent.availability_changes`
  - Remove `FetchDataFailedEvent` - replaced by `SystemStatusEvent.issues`
  - Remove `HomematicEvent` - replaced by `DeviceTriggerEvent`
  - Remove `PingPongMismatchEvent` - replaced by `SystemStatusEvent.issues`

### New Features

- Add `SystemStatusEvent` - aggregated event for all infrastructure and lifecycle state changes
  - `central_state: CentralState | None` - central unit state changes
  - `connection_state: tuple[str, bool] | None` - connection state (interface_id, connected)
  - `client_state: tuple[str, ClientState, ClientState] | None` - client state (interface_id, old, new)
  - `callback_state: tuple[str, bool] | None` - callback server state (interface_id, alive)
  - `issues: tuple[IntegrationIssue, ...]` - issues for user notification
- Add `DeviceLifecycleEvent` - aggregated event for device lifecycle and availability
  - `event_type: DeviceLifecycleEventType` - CREATED, UPDATED, REMOVED, AVAILABILITY_CHANGED
  - `device_addresses: tuple[str, ...]` - affected device addresses
  - `availability_changes: tuple[tuple[str, bool], ...]` - availability changes
  - `includes_virtual_remotes: bool` - whether virtual remotes are included
- Add `DataPointsCreatedEvent` - event for new data points (entity discovery)
  - `new_data_points: tuple[tuple[DataPointCategory, tuple[BaseDataPoint, ...]], ...]`
- Add `DeviceTriggerEvent` - event for device triggers (button press, sensor trigger)
  - `interface_id: str` - interface identifier
  - `channel_address: str` - device address (not channel address)
  - `parameter: str` - parameter name (e.g., PRESS_SHORT)
  - `value: str | int | float | bool` - event value
- Add `IntegrationIssue` dataclass for user-facing issues with severity, issue_id, translation_key
- Add `DeviceLifecycleEventType` enum with CREATED, UPDATED, REMOVED, AVAILABILITY_CHANGED values

### Migration Guide

See `docs/migrations/event_migration_2025_12.md` for detailed migration instructions.

# Version 2025.12.25 (2025-12-13)

## What's Changed

### Breaking Changes

- Remove `InterfaceEvent` class and `InterfaceEventType` enum - replaced with typed events
- Remove `EventType.INTERFACE` and `EventType.DEVICE_AVAILABILITY` enum values
- Remove `publish_interface_event` method from `CentralUnit` and `EventCoordinator`
- Remove `InterfaceEventPublisher` protocol from interfaces
- Remove `INTERFACE_EVENT_SCHEMA` from schemas
- Remove delegation methods from `CentralUnit` - use coordinators directly:
  - Remove `get_device()` - use `central.device_coordinator.get_device()` instead
  - Remove `get_channel()` - use `central.device_coordinator.get_channel()` instead
  - Remove `get_virtual_remotes()` - use `central.device_coordinator.get_virtual_remotes()` instead
  - Remove `remove_device()` - use `await central.device_coordinator.remove_device()` instead
- Remove `CentralUnitState` enum - use `CentralState` instead:
  - Removed legacy `_state` attribute from `CentralUnit` - all state now managed by state machine
  - Removed `central_state` property - use `state` property instead (returns `CentralState` from state machine)
  - `CentralUnitState.NEW` → `CentralState.STARTING`
  - `CentralUnitState.INITIALIZING` → `CentralState.INITIALIZING`
  - `CentralUnitState.RUNNING` → `CentralState.RUNNING`
  - `CentralUnitState.STOPPED` → `CentralState.STOPPED`
  - `CentralUnitState.STOPPED_BY_ERROR` → `CentralState.FAILED`
  - `CentralUnitState.STOPPING` state removed (no intermediate stopping state)
- Change `BackgroundScheduler.__init__()` signature - now requires `firmware_data_refresher` parameter
- Change `CentralUnitStateProvider.state` property type from `CentralUnitState` to `CentralState`
- Change `CentralInfo` protocol - renamed `central_state` property to `state` (returns `CentralState`)
- Change `CentralHealthProtocol` - renamed `central_state` property to `state` (returns `CentralState`)
- Change `ClientDependencies` protocol - renamed `central_state` property to `state` (returns `CentralState`)

### New Features

- Add `FetchDataFailedEvent` - typed event for data fetch failures (replaces `InterfaceEventType.FETCH_DATA`)
- Add `PingPongMismatchEvent` - typed event for ping/pong mismatches with `PingPongMismatchType` enum (`PENDING`, `UNKNOWN`)
- Add `DeviceAvailabilityChangedEvent` - typed event for device availability changes (replaces `EventType.DEVICE_AVAILABILITY`)
- Add `PingPongMismatchType` enum with `PENDING` and `UNKNOWN` values

### Enhancements

- Consolidate state management in `CentralUnit` - `state` property now directly delegates to state machine
- Separate `FirmwareDataRefresher` protocol from `DeviceDataRefresher` protocol for clearer separation of concerns
- Implement `FirmwareDataRefresher` in `DeviceCoordinator` instead of `CentralUnit`
- Direct coordinator access pattern improves code clarity and reduces unnecessary delegation
- Unified protocol property naming - all protocols now use `state` instead of mixed `central_state`/`state`

- Replace fixed cool-down with staged reconnection for faster recovery after CCU restart:
  - Stage 0: Initial cool-down (`reconnect_initial_cooldown`, default 10s)
  - Stage 1: Non-invasive TCP port check (no CCU load, bypasses firewall ICMP blocks)
  - Stage 2: First `system.listMethods` check (verify RPC is responding)
  - Stage 3: Warmup delay (`reconnect_warmup_delay`, default 10s)
  - Stage 4: Second `system.listMethods` check (confirm services stable)
  - Stage 5: Full reconnection with proxy recreation
- New `TimeoutConfig` options:
  - `reconnect_initial_cooldown`: Initial wait before checks (default 10s)
  - `reconnect_tcp_check_timeout`: Max time for TCP checks (default 60s)
  - `reconnect_tcp_check_interval`: TCP check interval (default 5s)
  - `reconnect_warmup_delay`: Warmup delay after first RPC check (default 10s)

# Version 2025.12.24 (2025-12-12)

## What's Changed

### Bug Fixes

- Fix "ResponseNotReady" errors after CCU reconnection by recreating proxy objects with fresh HTTP transport after successful PROXY_INIT
- Add configurable cool-down period (`reconnect_cooldown_delay`, default 60s) after connection loss - all communication including pings is suspended during cool-down to allow CCU time to fully restart

# Version 2025.12.23 (2025-12-12)

## What's Changed

### Breaking Changes

- New Central State Machine architecture for improved reconnection reliability
  - Introduces `CentralState` enum with states: STARTING, INITIALIZING, RUNNING, DEGRADED, RECOVERING, FAILED, STOPPED
  - Central is RUNNING only when ALL clients are CONNECTED
  - DEGRADED state when at least one client is not connected
  - FAILED state after max retries (8 attempts) with heartbeat retry every 60 seconds
  - New protocol interfaces: `CentralStateMachineProtocol`, `CentralHealthProtocol`, `HealthTrackerProtocol`

### New Features

- Add `CentralStateMachine` class for orchestrating overall system state (`central/state_machine.py`)
- Add `ConnectionHealth` and `CentralHealth` classes for unified health tracking (`central/health.py`)
- Add `RecoveryCoordinator` for coordinated client recovery with max retry tracking (`central/recovery.py`)
- Add `CentralStateChangedEvent` to EventBus for monitoring state transitions
- Add `ClientStateChangedEvent` to EventBus for monitoring client state changes
- Add `state` property to `ClientConnectionProtocol` protocol for accessing current client state
- Add health score calculation (0.0-1.0) based on state machine, circuit breakers, and activity
- Add exponential backoff for recovery retries (5s base, up to 60s max)
- Add multi-stage data load verification in recovery process
- New test suite for central state machine architecture (33 tests)

### Bug Fixes

- Fix entities not marked unavailable after failed proxy initialization - devices now correctly show unavailable during CCU restart/recovery

# Version 2025.12.22 (2025-12-12)

## What's Changed

### Enhancements

- Improve CCU reconnection behavior with exponential backoff (2s initial, doubles up to 120s max)
- Add configurable `TimeoutConfig` in `CentralConfig` for connection/reconnect timing settings

### Bug Fixes

- Fix data loading after partial reconnect - load data for available interfaces immediately instead of waiting for all
- Fix premature data loading - verify both state machine and actual connection before loading; retry up to 8 times with circuit breaker reset between attempts
- Fix client reconnect logic - use state machine check to prevent skipping reconnect when connection is lost
- Fix state machine allowing recovery from `FAILED` state via reconnect attempts
- Fix JSON-RPC session renewal after CCU restart - `AuthFailure` now triggers fresh login
- Fix race condition in scheduler client iteration with snapshot

# Version 2025.12.21 (2025-12-11)

## What's Changed

### Enhancements

- Circuit breakers automatically reset after successful reconnect to allow immediate data refresh
- Add `reset_circuit_breakers()` method to `ClientConnectionProtocol` protocol

### Bug Fixes

- Fix entities remaining unavailable after CCU reconnect - circuit breakers now reset automatically, allowing immediate data refresh instead of waiting for slow recovery

# Version 2025.12.20 (2025-12-11)

## What's Changed

### Enhancements

- Add BackupData dataclass with filename and content for backup downloads
- Backup filename now includes hostname and CCU version (e.g., `Otto-3.83.6.20251025-2025-12-10-1937.sbk`)
- `create_backup_and_download()` now returns `BackupData | None` instead of `bytes | None`
- Add firmware update support for OpenCCU via `checkFirmwareUpdate.sh`
- Add `HmUpdate` hub entity for system firmware updates (OpenCCU only)
- Add `get_system_update_info()` method to check for available firmware updates
- Add `trigger_firmware_update()` method to initiate firmware update with automatic reboot (runs with nohup)
- Add `SystemUpdateData` dataclass with `check_script_available` field to verify script availability
- Add progress tracking for hub firmware updates:
  - New `in_progress` property on `HmUpdate` to track update status
  - Automatic polling every 30 seconds during update to detect completion
  - Progress detection via firmware version change
  - 30-minute timeout with graceful cleanup
  - Events published on progress state changes for Home Assistant integration

### Architecture

- Migrate `CentralConnectionState` callbacks to unified EventBus pattern:
  - Add `ConnectionStateChangedEvent` for connection state changes (connected/disconnected)
  - Add `EventBus.publish_sync()` method for synchronous event publishing from non-async code
  - Rename `StateChangeCallback` to `StateChangeCallbackProtocol` and remove `register_state_change_callback()` method
  - Add `event_bus` property to `ClientDependencies` protocol
  - All connection state notifications now use the same EventBus as other events
- EventBus now uses TaskScheduler (Looper) for proper task lifecycle management:
  - `publish_sync()` uses TaskScheduler when available for task tracking, shutdown handling, and exception logging
  - Falls back to raw asyncio when no TaskScheduler is provided (e.g., in tests)

### Developer Tools

- Enhance `check_i18n_catalogs.py` to detect unused translation keys:
  - Add detection of translation keys in `strings.json` that are not used in the codebase
  - Add `--remove-unused` flag to automatically remove unused keys from all catalog files
  - Unused keys are reported as warnings (non-blocking) to avoid disrupting commits
  - Current statistics: 185 total keys, 181 used (97.8%), 4 unused (2.2%)
- Add comprehensive i18n management documentation at `docs/i18n_management.md`

### Bug Fixes

- Fix excessive ERROR logging during CCU restart/reconnect - connection errors now log ERROR only on first occurrence, DEBUG for subsequent failures (fixes inverted logic in `CentralConnectionState.add_issue()` usage)
- Fix PING_PONG false alarm mismatch events during CCU restart - PINGs sent during downtime are no longer tracked when connection is known to be down, and cache is cleared on reconnect
- Scheduler now pauses non-essential jobs during connection issues - only `_check_connection` continues to run during CCU downtime, preventing unnecessary RPC calls and log spam
- Reduce INFO-level log noise during reconnection - circuit breaker successful recovery transitions (half_open → closed) now log at DEBUG level instead of INFO

### Notes

- Firmware update features are only available on OpenCCU systems where `/bin/checkFirmwareUpdate.sh` is present
- Backup before firmware update should be done via `create_backup_and_download()` in Home Assistant before triggering the update

# Version 2025.12.19 (2025-12-10)

## What's Changed

### Architecture

- Add combined sub-protocol interfaces to reduce coupling:
  - **Client Combined Protocols (3):** ValueAndParamsetOperations, DeviceDiscoveryWithIdentityProtocol, DeviceDiscoveryAndMetadataProtocol
  - **Device Combined Protocols (1):** DeviceRemovalInfo
  - Components now depend on minimal protocol combinations instead of full composite protocols
- Refactor components to use combined sub-protocols:
  - CacheCoordinator.remove_device_from_caches uses DeviceRemovalInfo instead of DeviceProtocol
  - DeviceCoordinator.refresh_device_descriptions_and_create_missing_devices uses DeviceDiscoveryWithIdentityProtocol
  - DeviceCoordinator.\_rename_new_device uses DeviceDiscoveryAndMetadataProtocol
  - CallParameterCollector uses ValueAndParamsetOperations instead of ClientProtocol
  - DeviceDetailsCache.remove_device uses DeviceRemovalInfo instead of DeviceProtocol
  - DeviceDescriptionCache.remove_device uses DeviceRemovalInfo instead of DeviceProtocol
  - ParamsetDescriptionCache.remove_device uses DeviceRemovalInfo instead of DeviceProtocol
- Split ClientProtocol (85 members) into 14 focused sub-protocols following Interface Segregation Principle:
  - **Core Protocols (4):** ClientIdentityProtocol, ClientConnectionProtocol, ClientLifecycleProtocol, ClientCapabilitiesProtocol
  - **Handler-Based Protocols (9):** DeviceDiscoveryOperationsProtocol, ParamsetOperationsProtocol, ValueOperationsProtocol,
    LinkOperationsProtocol, FirmwareOperationsProtocol, SystemVariableOperationsProtocol, ProgramOperationsProtocol,
    BackupOperationsProtocol, MetadataOperationsProtocol
  - **Support Protocol (1):** ClientSupportProtocol (utility methods and caches)
  - Handler classes explicitly inherit their sub-protocols for compile-time type checking
- Add CentralProtocol composite protocol combining 29 sub-protocols:
  - CentralUnit now inherits from CentralProtocol (+ PayloadMixin, LogContextMixin)
  - Provides single protocol for complete central unit access
  - Maintains ability to depend on specific sub-protocols for better decoupling
- Add CircuitBreaker integration to JSON-RPC client (AioJsonRpcAioHttpClient):
  - Prevents retry-storms during backend outages for JSON-RPC calls
  - Consistent resilience pattern across both XML-RPC and JSON-RPC clients
  - Session management methods (login/logout/renew) bypass circuit breaker
- Add RequestCoalescer for get_device_description in DeviceOperationsHandler:
  - Deduplicates concurrent requests for the same device address
  - Reduces backend load during device discovery
- Add explicit protocol inheritance to coordinators:
  - EventCoordinator now inherits from EventBusProvider, EventPublisher, LastEventTrackerProtocol, InterfaceEventPublisher
  - HubCoordinator now inherits from HubDataFetcher, HubDataPointManager
  - Improves type safety and removes type: ignore comments

### Documentation

- Update architecture_analysis.md with comprehensive evaluation:
  - Accurate metrics: 43,218 LOC across 102 files, 63 protocol interfaces
  - Detailed module breakdown (central, client, model, interfaces, store)
  - New sections for CircuitBreaker, RequestCoalescer, and Handler patterns
  - Architecture maturity assessment with ratings
  - ADR reference table with all 8 decisions

# Version 2025.12.18 (2025-12-10)

## What's Changed

### Architecture

- Refactor ClientCCU into specialized handler classes (BackupHandler, DeviceOpsHandler, FirmwareHandler, LinkManagementHandler, MetadataHandler, ProgramsHandler, SysvarsHandler)
- Add ClientStateMachine for managing client connection lifecycle with validated state transitions
- Add ClientState enum for client connection states (CREATED, INITIALIZING, INITIALIZED, CONNECTING, CONNECTED, DISCONNECTED, RECONNECTING, STOPPING, STOPPED, FAILED)
- Split DeviceProtocol (72 members) into 10 focused sub-protocols following Interface Segregation Principle:
  - DeviceIdentityProtocol, DeviceChannelAccessProtocol, DeviceAvailabilityProtocol, DeviceFirmwareProtocol
  - DeviceLinkManagementProtocol, DeviceGroupManagementProtocol, DeviceConfigurationProtocol
  - DeviceWeekProfileProtocol, DeviceProvidersProtocol, DeviceLifecycleProtocol
- Split ChannelProtocol (39 members) into 6 focused sub-protocols:
  - ChannelIdentityProtocol, ChannelDataPointAccessProtocol, ChannelGroupingProtocol
  - ChannelMetadataProtocol, ChannelLinkManagementProtocol, ChannelLifecycleProtocol
- Add EventPriority enum with four priority levels (CRITICAL, HIGH, NORMAL, LOW) for handler ordering
- Add EventBatch context manager for efficient batch event publishing
- Add publish_batch() method to EventBus for optimized bulk event publishing
- Add CircuitBreaker for preventing retry-storms during backend outages:
  - Three-state machine (CLOSED → OPEN → HALF_OPEN → CLOSED)
  - Configurable failure threshold, recovery timeout, and success threshold
  - Integrated with CentralConnectionState for coordinated health tracking
  - Metrics tracking for failures, successes, and rejections
- Add RequestCoalescer for efficient RPC call deduplication:
  - Merges identical concurrent requests into a single backend call
  - Particularly beneficial during device discovery (getParamsetDescription calls)
  - Includes metrics for monitoring coalesce rate effectiveness

### Bug Fixes

- Fix hub data points initialization by ensuring clients are connected before init_hub() is called
- Fix mock property delegation to support dynamic property value updates in tests
- Add \_\_slots\_\_ support to get_mock() in test support module

### Documentation

- Add comprehensive inline comments for complex algorithms across the codebase:
  - State machine valid transitions diagram and state descriptions
  - Event publishing batching and subscription reference counting
  - bind_collector decorator context variable pattern
  - Cache eviction strategies (LRU, TTL, lazy cleanup)
  - SessionRecorder nested dict structure and purge algorithm
  - freeze/unfreeze parameter transformation for cache keys
  - EventBus dual-key handler lookup and polymorphic handler detection
  - Device discovery set difference algorithm and PARENT address fallback
  - DeviceProfileRegistry hierarchical model matching (exact → prefix)
- Add migration guide for protocol sub-protocols (docs/migrations/protocol_subprotocols_2025_12.md)
- Refactor architecture.md: Move inline decisions to ADRs, reduce from ~450 to ~245 lines
- Add ADR 0007: Device Slots Reduction via Composition (Rejected)
- Add ADR 0008: TaskGroup Migration (Deferred)

# Version 2025.12.17 (2025-12-09)

## What's Changed

- Fix return types

# Version 2025.12.16 (2025-12-09)

## What's Changed

### Concurrency and Thread-Safety

- Add asyncio.Lock for thread-safe task management in InstallModeDpSensor
- Replace bool state flags with asyncio.Event in BackgroundScheduler for thread-safety
- Fix list-modification-during-iteration bug in climate.py subscription cleanup
- Add asyncio.Lock to DeviceRegistry for thread-safe device operations

### Memory Leak Prevention

- Add auto-cleanup of EventBus subscriptions when devices/data points are removed
- Add clear_subscriptions_by_key() method to EventBus for key-based cleanup

### Error Handling

- Add exception logging for scheduler jobs, background tasks, and install mode loops

### Architecture and Dependency Injection

- Add RpcServerCentralProtocol and RpcServerTaskSchedulerProtocol protocols
- Refactor RpcServer to use protocol interfaces instead of direct CentralUnit dependency
- Introduce \_CentralEntry container class for decoupled central/looper storage
- Add HubFetchOperations base protocol for consolidated hub data fetching
- Consolidate UnsubscribeCallback definition in type_aliases.py
- Add ClientDependencies composite protocol for decoupled client architecture
- Refactor ClientConfig and ClientCCU to use ClientDependencies instead of CentralUnit

### Other changes

- Add basic rega script linter to ensure support for session recorder
- Add architecture analysis
- Cleanup scripts for recorder
- Improve backend detection

# Version 2025.12.15 (2025-12-08)

## What's Changed

- Revert get_serial.fn &error removal

# Version 2025.12.14 (2025-12-08)

## What's Changed

- Cleanup ReGa scripts
- Eliminate CDPD dictionary format with pure ProfileConfig implementation
- Refactor CCU backup

# Version 2025.12.13 (2025-12-07)

## What's Changed

- Add is_service param to inspector
- Add inspector to load_data_point_value
- Mark service methods with external/internal scope usage
- Add scan_aiohomematic_calls.py script to find external method calls

# Version 2025.12.12 (2025-12-07)

## What's Changed

- Fix retry

# Version 2025.12.11 (2025-12-07)

## What's Changed

- Cleanup of legacy code in custom entity definition

# Version 2025.12.10 (2025-12-07)

## What's Changed

- Add DeviceProfileRegistry as central registry for device-to-profile mappings
- Add type-safe DeviceConfig and ExtendedDeviceConfig dataclasses
- Add ProfileConfig and ChannelGroupConfig dataclasses for profile definitions
- Migrate all 117 device models to DeviceProfileRegistry
- Remove legacy ALL_DEVICES and ALL_BLACKLISTED_DEVICES dictionaries
- Remove make\_\* factory functions from entity modules
- Simplify get_custom_configs() to use only DeviceProfileRegistry
- Move schemas to schemas.py

# Version 2025.12.9 (2025-12-06)

## What's Changed

- Add TimerUnitMixin for light timer unit conversion
- Refactor valve.py to use StateChangeTimerMixin and GroupStateMixin
- Refactor light.py to use TimerUnitMixin for IP light classes
- Remove unused DirectionStateMixin from mixins.py
- Update imports to use specific protocol submodules

# Version 2025.12.8 (2025-12-06)

## What's Changed

### Architecture and Internals

- Split interfaces.py into interfaces/ package for better maintainability
- Add DataPointTypeResolver class for extensible data point type mapping
- Add shared mixins for custom entities (model/custom/mixins.py)
- Refactor switch.py to use StateChangeTimerMixin and GroupStateMixin
- Refactor cover.py to use PositionMixin for position calculations
- Refactor light.py to use StateChangeTimerMixin and BrightnessMixin

### Reliability and Error Handling

- Add login rate limiting with exponential backoff for JSON-RPC client
- Add error message sanitization helpers (sanitize_error_message, RpcContext.fmt_sanitized)
- Add retry module with RetryStrategy class for transient network errors
- Improve CentralConnectionState
- Add resource limits for internal collections

### High-Level API (HomematicAPI)

- Add HomematicAPI facade class with simplified high-level interface
- Add CentralConfig.for_ccu() and CentralConfig.for_homegear() factory methods
- Add async context manager support for HomematicAPI
- Add `@with_retry` decorator to HomematicAPI operations for automatic retry

### CLI Enhancements (hmcli)

- Add subcommand-based CLI structure with device discovery commands
- Add `list-devices` command to list all devices
- Add `list-channels <device>` command to list channels of a device
- Add `list-parameters <channel>` command to list parameters of a channel
- Add `device-info <address>` command to show detailed device information
- Add `get` and `set` subcommands for parameter operations
- Add `interactive` subcommand for REPL mode with command history and tab completion
- Add shell completion script generation for bash, zsh, and fish shells
- Add `--generate-completion <shell>` option to generate completion scripts

### Documentation

- Add getting_started.md documentation with quick start examples
- Add common_operations.md documenting top 15 most-used operations

# Version 2025.12.7 (2025-12-05)

## What's Changed

- Add helper for config support

# Version 2025.12.6 (2025-12-04)

## What's Changed

- Add ENERGY_COUNTER_FEED_IN
- Fix backend detection
- Fix install mode for HmIP
- Improved delayed device handling
- Refactor add_new_devices_manually to address names

# Version 2025.12.5 (2025-12-03)

## What's Changed

- Add install mode virtual data points with countdown timer (HUB_BUTTON + HUB_SENSOR)
- Support separate install mode data points per interface (HmIP-RF and BidCos-RF)
- Add JSON-RPC methods for HmIP install mode (getInstallMode, setInstallModeHmIP)
- Add init_install_mode, fetch_install_mode_data, publish_install_mode_refreshed to Hub/HubCoordinator/CentralUnit
- Add mandatory interface parameter to get_install_mode/set_install_mode on CentralUnit
- Extend ClientCoordinator.get_client to accept optional interface parameter
- Add ClientProvider to Hub for multi-interface install mode support
- Fix install mode data point creation to check for client availability per interface
- Fix install mode unique_id generation to avoid duplicate prefix
- Mark setInstallMode/setInstallModeHmIP as optional JSON-RPC methods

# Version 2025.12.4 (2025-12-02)

## What's Changed

- Add rename for new devices

# Version 2025.12.3 (2025-12-02)

## What's Changed

- Add create_backup_and_download to BackupProvider/CentralUnit
- Add dedicated inbox devices code
- Add rename_device / accept_device_in_inbox to Central/DeviceManagement
- Refactor Client

# Version 2025.12.2 (2025-12-01)

## What's Changed

- Add HubProtocol and WeekProfileProtocol to interfaces
- Cleanup client api
- Rename regaid to rega_id
- Update documentation

# Version 2025.12.1 (2025-12-01)

## What's Changed

- Migrate to Protocol based model

# Version 2025.12.0 (2025-12-01)

## What's Changed

- Added get_install_mode() and set_install_mode() methods
- Added rename_device and rename_channel methods
- Method accept_device_in_inbox to accept new devices
- New hub entity for device inbox (devices pending pairing)
- New hub entity for system update status
- New method create_backup() for creating CCU system backups
- New method download_backup() for downloading backup files
- New method download_firmware() for downloading firmware to CCU
- New method get_service_messages to fetch CCU service messages
- New method get_system_update_info for firmware update status
- Extended SystemInformation with CCU type identification (CCU vs OpenCCU)
- New CCUType enum for backend identification
- New protocols for model data points for better decoupling
- New script trigger_firmware_update.fn to trigger firmware updates
- New script create_backup.fn to create system backups
- New script get_backend_info.fn to retrieve backend information
- Extended get_system_update_info.fn to support OpenCCU online version check

# Version 2025.11.30 (2025-11-26)

## What's Changed

- Use AioXmlRpcProxy for backend detection

# Version 2025.11.29 (2025-11-26)

## What's Changed

- Extend backend detection

# Version 2025.11.28 (2025-11-26)

## What's Changed

- Avoid potential memory leaks
- Clear in-memory caches on stop

# Version 2025.11.27 (2025-11-25)

## What's Changed

- Add backend detection
- Use CentralConnectionState in AioJsonRpcAioHttpClient

# Version 2025.11.26 (2025-11-25)

## What's Changed

- Improve event processing

# Version 2025.11.25 (2025-11-24)

## What's Changed

- Cleanup after event bus migration
- Switch from legacy wrapper to event bus naming

# Version 2025.11.24 (2025-11-24)

## What's Changed

- Add ClientFactoryProtocol for DI
- Improve documentation

# Version 2025.11.23 (2025-11-21)

## What's Changed

- Clean up event bus implementation and remove legacy code
- Extend API to re-add support for mqtt client

# Version 2025.11.22 (2025-11-20)

## What's Changed

- Add data_point_provider to DeviceCoordinator

# Version 2025.11.21 (2025-11-20)

## What's Changed

- De-couple from central unit pt2
- Improve typing in protocols/interfaces

# Version 2025.11.20 (2025-11-19)

## What's Changed

- De-couple from central unit
- Extract coordinators from central unit
- Extract device registry from central
- Extract scheduler from central
- Refactor event handling to event bus
- Rename writeable to writable

# Version 2025.11.19 (2025-11-17)

## What's Changed

- Fix service naming

# Version 2025.11.18 (2025-11-17)

## What's Changed

- Add more simple services and converters to week profile
- Add base_temperature to CLIMATE_SIMPLE_WEEKDAY_DATA
- Filter entries in validate_and_convert_weekday_to_simple
- Refactor simple schedule

# Version 2025.11.17 (2025-11-16)

## What's Changed

- Fix week profile filtering
- Improve test coverage,
- Reorganize test files

# Version 2025.11.16 (2025-11-16)

## What's Changed

- Add schedule support to custom data point
- Improve the test coverage of week_profile
- Optimize climate get/set_schedule
- Return filtered climate schedule data on get_schedule / Accept filtered data in climate set_schedule

# Version 2025.11.15 (2025-11-13)

## What's Changed

- Move reload_and_cache_schedule to load_data_point_value

# Version 2025.11.14 (2025-11-13)

## What's Changed

- Add input converter to climate scheduler setter

# Version 2025.11.13 (2025-11-13)

## What's Changed

- Use schedule cache for climate get/set schedule operations

# Version 2025.11.12 (2025-11-12)

## What's Changed

- Add climate schedule cache

# Version 2025.11.11 (2025-11-09)

## What's Changed

- Add translations for log messages with level >= INFO or translation exclusions
- Move strings.json to root

# Version 2025.11.10 (2025-11-08)

## What's Changed

- Make exceptions translatable

# Version 2025.11.9 (2025-11-07)

## What's Changed

- Do not normalize homematic event data

# Version 2025.11.8 (2025-11-07)

## What's Changed

- Remove need for empty parentheses for bind_collector
- Switch mypy to strict
- Use Protocol for callback with parameters

# Version 2025.11.7 (2025-11-05)

## What's Changed

- Handle early arrival of pong events

# Version 2025.11.6 (2025-11-05)

## What's Changed

- Add code member sorter to pre-commit
- Add post_init_data_point_fields
- Make ping pong handling more robust
- Move on_link_peer_changed and refresh_link_peer_activity_sources to BaseCustomDpClimate

# Version 2025.11.5 (2025-11-04)

## What's Changed

- Remove link support for not linkable interfaces

# Version 2025.11.4 (2025-11-04)

## What's Changed

- Fix issue with linked channels for climate activity
- Store data_point_updated_callbacks by custom_id

# Version 2025.11.3 (2025-11-03)

## What's Changed

- Add fallback to climate.activity to use linked channels, if own dps don't exist

# Version 2025.11.2 (2025-11-02)

## What's Changed

- Add link peer channel to channel
- Add link_peer channels to device

# Version 2025.11.0 (2025-11-01)

## What's Changed

- Fix issue after reconnect
- Use generic DP DpDummy instead of NoneTypeDataPoint replacement

# Version 2025.10.26 (2025-10-30)

## What's Changed

- Run delete_file task in executor

# Version 2025.10.25 (2025-10-30)

## What's Changed

- Handle ping after ping success

# Version 2025.10.24 (2025-10-30)

## What's Changed

- Fix custom HmIP-WGTC definition
- Test support: Improve central unit code/test coverage

# Version 2025.10.22 (2025-10-26)

## What's Changed

- Refactor PingPongCache

# Version 2025.10.21 (2025-10-26)

## What's Changed

- Add pong_mismatch_allowed to ping pong event
- Revert: Improve call back alive check

# Version 2025.10.20 (2025-10-26)

## What's Changed

- Test support: Improve code/test coverage
- Improve call back alive check
- Improve version creation for aiohomematic_test_support

# Version 2025.10.18 (2025-10-24)

## What's Changed

- Test support: Search in secondary sessions if primary session has no results

# Version 2025.10.17 (2025-10-23)

## What's Changed

- Test support: Remove ClientLocal

# Version 2025.10.16 (2025-10-23)

## What's Changed

- Test support: Add option to start central in get_default_central (tests)

# Version 2025.10.15 (2025-10-23)

## What's Changed

- Test support: Refactor tests to use central*client_factory_with*\*\*\*ccu_client

# Version 2025.10.14 (2025-10-22)

## What's Changed

- Test support: Add separate deployment for aiohomematic_test_support
- Test support: Refactor tests to use SessionPlayer instead of ClientLocal
- Test support: Use recorded session for testing

# Version 2025.10.10 (2025-10-19)

## What's Changed

- Add file_path to BasePersitentFile load
- Add get_latest_response_by_params to session recorder
- Add 'optional settings' config option
- Remove individual ttl for session recorder entry
- Rename filename to file_name
- Use enum for internal custom ids

# Version 2025.10.9 (2025-10-18)

## What's Changed

- Add session recorder
- Ensure custom_ids are only used for external registrations
- Fix rpc auth

# Version 2025.10.8 (2025-10-14)

## What's Changed

- Add dew point spread and enthalpy to calculated sensors

# Version 2025.10.7 (2025-10-13)

## What's Changed

- Fix issue with RPC-Server setup

# Version 2025.10.6 (2025-10-13)

## What's Changed

- Add ELV-SH-PSMCI
- Refactor rpc handling

# Version 2025.10.5 (2025-10-10)

## What's Changed

- Fix issue with non existing PARENT in device description

# Version 2025.10.4 (2025-10-07)

## What's Changed

- Add delayed device creation
- Add source of device creation to callback
- Improve test setup and cleanup
- Minimize decorator overhead

# Version 2025.10.3 (2025-10-06)

## What's Changed

- Add Keyword-only method linter (mypy-style)

# Version 2025.10.2 (2025-10-05)

## What's Changed

- API cleanup: ensure that kw arguments are passed to the underlying function

# Version 2025.10.1 (2025-10-01)

## What's Changed

- Add option to cover entities that the current default behaviour can be disabled:
  - The default behaviour is, that the primary cover entity of a group uses the level of the state channel and no its own level to display a correct level.
  - Only HM experts should disable this option, that like to control all three writeable channels of a cover group.

# Version 2025.10.0 (2025-10-01)

## What's Changed

- Improve error message if service is not available
- Make default_callback_port, storage_folder optional
- Re-/Store last manual temperature of climate entity

# Version 2025.9.8 (2025-09-29)

## What's Changed

- Add CuXD parameters CMD_RETL and CMD_RETS to ignore list, to avoid warnings when reading the value without an appropriate configuration.
  - CMD_RETL warning: use CUX28010xx:16.CMD_QUERY_RET=1 to activate CUX28010xx:16.CMD_RETL command!
  - CMD_RETS warning: use CUX28010xx:16.CMD_QUERY_RET=1 to activate CUX28010xx:16.CMD_RETS command!
  - Add them to unignore if you are able to handle the warnings.

# Version 2025.9.7 (2025-09-28)

## What's Changed

- Fix device has_sub_devices pt2

- # Version 2025.9.6 (2025-09-28)

- Fix device has_sub_devices

# Version 2025.9.5 (2025-09-25)

## What's Changed

- Fix magic method issue with log_context in xml_rpc client

# Version 2025.9.4 (2025-09-24)

## What's Changed

- Remove dedicated @cached_property -> use @hm_property(cached=True) instead

# Version 2025.9.3 (2025-09-14)

## What's Changed

- Remove test-only-relevant code from \_get_attributes_by_decorator
- Further decorator refactoring

# Version 2025.9.2 (2025-09-12)

## What's Changed

- Refactor CDP OperatingVoltageLevel
- Refactor event method handling
- Refactor decorators
  - Add log_context to @\*\_property
  - Add overloads to @\*\_property
  - Add overloads to @inspector

# Version 2025.9.1 (2025-09-06)

## What's Changed

- Document how device, channel and data point names are created (docs/naming.md)
- Add worked examples to naming documentation
- Use dedicated loggers for event and performance logging

# Version 2025.8.10 (2025-08-29)

## What's Changed

- Improve documentation
  - Added docs/architecture.md describing high-level components (central, client, model, caches, support) and their interactions
  - Added data flow for XML-RPC/JSON-RPC, event handling, and data point updates
  - Added sequence diagrams for connect, device discovery, state change propagation
  - Add troubleshouting docs
- Add customization for HmIP-LSC
- Avoid deadlocks within locks (cover)
- Detailing the central status
- Improve boundary logging und exception handling
- Improve decorators
- Improve lock handling
- Shield network I/O against cancellation
- Validate custom datapoint definition on startup

# Version 2025.8.9 (2025-08-23)

## What's Changed

- Add signature to model
- Improve immutability
- Improve readability of visibility cache

# Version 2025.8.8 (2025-08-23)

## What's Changed

- Extend DataPointKey usage
- Improve fetch_all_device_data

# Version 2025.8.7 (2025-08-17)

## What's Changed

- Use room from channel 0 for device, if multiple set on channels
- Use room from master channel, if multiple set on channel group

# Version 2025.8.6 (2025-08-14)

## What's Changed

- Do not send additional parameter in kwargs for events
- Fix unique_id_prefix usage
- Rename hahomematic to aiohomematic

# Version 2025.8.5 (2025-08-11

## What's Changed

- Improve module documentation
- Small performance improvements

# Version 2025.8.4 (2025-08-10)

## What's Changed

- Small performance improvements

# Version 2025.8.3 (2025-08-07)

## What's Changed

- Fix refresh shortly

# Version 2025.8.2 (2025-08-07)

## What's Changed

- Simplify should_fire_data_point_updated_callback for calculated data points

# Version 2025.8.1 (2025-08-06)

## What's Changed

- Cleanup slots
- Move timer support to BaseDataPoint

# Version 2025.8.0 (2025-08-03)

## What's Changed

- Use slots

# Version 2025.7.7 (2025-07-26)

## What's Changed

- Align exception naming

# Version 2025.7.6 (2025-07-25)

## What's Changed

- Refactor argument extraction from exceptions

# Version 2025.7.5 (2025-07-23)

## What's Changed

- Add customization for (Deleting of obsolete entities/device) might be required):
  - HmIP-SMO230

# Version 2025.7.4 (2025-07-13)

## What's Changed

- Add customization for (Deleting of obsolete entities/device) might be required):
  - HmIP-WGT/HmIP-WGTC
- Replace asyncio.iscoroutinefunction

# Version 2025.7.3 (2025-07-13)

## What's Changed

- Improve: Fire updated events for calculated DPs when refreshed within a second

# Version 2025.7.2 (2025-07-12)

## What's Changed

- Rename channel* to group* properties for cover, light and switch

# Version 2025.7.1 (2025-07-12)

## What's Changed

- Fire updated events for calculated DPs when refreshed within a second

# Version 2025.7.0 (2025-07-09)

## What's Changed

- Add default customization for ELV-SH-SW1-BAT (Deleting of obsolete entities might be required)
- Enable OPERATING_VOLTAGE_LEVEL for HM-CC-RT-DN and HM-TC-IT-WM-W-EU

# Version 2025.6.0 (2025-06-16)

## What's Changed

- Add batteries for ELV-SH-TACO
- Add state channel to sub_device_channel mapping
- Improve sub_device_channel identification

# Version 2025.5.2 (2025-06-01)

## What's Changed

- Add operating voltage level to ELV-SH-WSM / HmIP-WSM
- Enable ACTUAL_TEMPERATURE on maintenance channel

# Version 2025.5.1 (2025-05-20)

## What's Changed

- Add CustomDP valve for ELV-SH-WSM / HmIP-WSM

# Version 2025.5.0 (2025-05-19)

## What's Changed

- Fix performance measurement
- Improve identify ip address
- Wait with PING/PONG handling until interface is initialized

# Version 2025.4.2 (2025-04-11)

## What's Changed

- Add button_lock to HmIP-DLD

# Version 2025.4.1 (2025-04-07)

## What's Changed

- limit text values to 255 characters

# Version 2025.4.0 (2025-04-03)

## What's Changed

- Create TLS context during module load

# Version 2025.3.0 (2025-03-09)

## What's Changed

- Clear session on auth failure
- Use enums for const parameter values

# Version 2025.2.7 (2025-02-08)

## What's Changed

- Remove @cache and @lru_cache annotations
- Use @cached_property for expensive, one time calculated properties

# Version 2025.2.6 (2025-02-08)

## What's Changed

- Add vapor concentration and dew point to all device channels that support temperature and humidity
- Add HmIP-FCI1 and HmIP-FCI6 to batteries
- Ensure load_data_point_value usage for initial load
- Fix OperatingVoltageLevel attributes: low_bat_limit, low_bat_limit_default
- Ignore parameters on initial load, if not already fetched by rega script (ERROR*, RSSI*, DUTY_CYCLE, DUTYCYCLE, LOW_BAT, LOWBAT, OPERATING_VOLTAGE)
- Ignore model on initial load (HmIP-SWSD, HmIP-SWD)

# Version 2025.2.5 (2025-02-05)

## What's Changed

- Use value instead of default for low_bat_limit

# Version 2025.2.3 (2025-02-05)

## What's Changed

- Fix calculated climate sensor identification

# Version 2025.2.2 (2025-02-05)

## What's Changed

- Catch get_metadata XMLRPC fault
- Catch JSONDecodeError on load/save cache files
- Ignore devices with unknown battery
- Set battery to UNKNOWN for HmIP-PCBS-BAT
- Sort battery list for correct wildcard search

# Version 2025.2.1 (2025-02-02)

## What's Changed

- Add calculated data points for HM devices
- Remove python 3.12 for github tests and pylint
- Use py 3.13 for mypy and pylint

# Version 2025.2.0 (2025-02-01)

## What's Changed

- Fix battery qty

# Version 2025.1.22 (2025-01-31)

## What's Changed

- Add config option to define the hm_master_poll_after_send_intervals
- Enable DEW_POINT calculation for internal thermostats
- Use temporary values where push is not supported

# Version 2025.1.21 (2025-01-30)

## What's Changed

- Improve connection error handling

# Version 2025.1.20 (2025-01-30)

## What's Changed

- Fix index issue with WEEK_PROGRAM_POINTER
- Use ParamsetKey enum in tests

# Version 2025.1.19 (2025-01-29)

## What's Changed

- Don't read on unavailable devices
- Enable schedule on hm thermostat
- Poll master dp values 5s after send for bidcos devices
- Rename paramset_key to paramset_key_or_link_address for put_paramset

# Version 2025.1.18 (2025-01-28)

## What's Changed

- Add climate presets based on WEEK_PROGRAM_POINTER
- Add WEEK_PROGRAM_POINTER for bidcos climate devices
- Define schedule_channel_address for HM schedule usage
- Fix usage of master dps for bidcos climate devices

# Version 2025.1.17 (2025-01-26)

## What's Changed

- Catch math related value errors

# Version 2025.1.16 (2025-01-26)

## What's Changed

- Limit calculated climate sensors to selected devices

# Version 2025.1.15 (2025-01-25)

## What's Changed

- Add calculated data points: FrostPoint

# Version 2025.1.14 (2025-01-25)

## What's Changed

- Add calculated data points: ApparentTemperature, DewPoint, VaporConcentration
- Refactor OperatingVoltageLevel

# Version 2025.1.13 (2025-01-24)

## What's Changed

- Fix OperatingVoltageLevel sensor value

# Version 2025.1.12 (2025-01-24)

## What's Changed

- Add LOW_BAT_LIMIT
- Add calculated data points: OperatingVoltageLevel
- Refactor parameter_visibility

# Version 2025.1.11 (2025-01-20)

## What's Changed

- Cleanup cache file clear
- Delay start of scheduler until devices are created
- Rename instance_name to central_name
- Slugify cache file name

# Version 2025.1.10 (2025-01-17)

## What's Changed

- Return regular dict from list_devices

# Version 2025.1.9 (2025-01-15)

## What's Changed

- Load cached files as defaultdicts

# Version 2025.1.8 (2025-01-15)

## What's Changed

- Improve defaultdict usage

# Version 2025.1.7 (2025-01-14)

## What's Changed

- Fix KeyError on uninitialised dict pt2

# Version 2025.1.6 (2025-01-14)

## What's Changed

- Fix KeyError on uninitialised dict

# Version 2025.1.5 (2025-01-11)

## What's Changed

- Refactor create\_\* methods:
  - create_data_points_and_events
  - create_data_point_and_append_to_channel
  - create_event_and_append_to_channel
- Speedup wildcard lookup

# Version 2025.1.4 (2025-01-09)

## What's Changed

- Cleanup: Use defaultdict, improve naming
- Rename decorator @inspector

# Version 2025.1.3 (2025-01-08)

## What's Changed

- Fix issue with programs/sysvars on backend restart

# Version 2025.1.2 (2025-01-06)

## What's Changed

- Add legacy name for hub entities
- Cleanup hub entity name if channel exists
- Identify channel of a system variable:
  - name ends with channel address
  - name contains channel/device id

# Version 2025.1.1 (2025-01-05)

## What's Changed

- Consider heating value type when calculating hvac action

# Version 2025.1.0 (2025-01-01)

## What's Changed

- Remove get-/set_install_mode

# Version 2024.12.13 (2024-12-27)

## What's Changed

- Add program switch

# Version 2024.12.12 (2024-12-23)

## What's Changed

- Ensure service and alarm messages are always displayed
- Remove sv prefix from sysvar / p prefix from program

# Version 2024.12.11 (2024-12-22)

## What's Changed

- Fix remove last sysvar/program
- Remove unignore file import
- Rename has_markers to enabled_default
- Use NamedTuple for datapoint key

# Version 2024.12.10 (2024-12-21)

## What's Changed

- Refactor scheduler
- Reformat line length to 120

# Version 2024.12.9 (2024-12-20)

## What's Changed

- Add periodic checks for device firmware updates
- Refactor scheduler to use just one task
- Rename marker for extended system variables from hahm to HAHM to better align with other markers

# Version 2024.12.8 (2024-12-20)

## What's Changed

- Rename create methods
- Revert mangled attribute name in json_rpc_client

# Version 2024.12.7 (2024-12-18)

## What's Changed

- Extend element_matches_key search
- Log debug if variable is too long
- Remove default markers from description
- Start json_rpc client only for ccu

# Version 2024.12.6 (2024-12-18)

## What's Changed

- Support markers for sysvar/program selection
- Remove danielperna84 from links after repository transfer to sukramj

# Version 2024.12.5 (2024-12-15)

## What's Changed

- Limit number of concurrent mass operations to json api to 3 parallel executions

# Version 2024.12.4 (2024-12-14)

## What's Changed

- Add missing encoding to unquote
- Ensure default encoding is ISO-8859-1 where needed

# Version 2024.12.3 (2024-12-14)

## What's Changed

- Add method cleanup_text_from_html_tags
- Decode received sysvar/program descriptions
- Replace special character replacement by simple UriEncode() method use by @jens-maus

# Version 2024.12.2 (2024-12-10)

## What's Changed

- Use kelvin instead of mireds for color temp

# Version 2024.12.1 (2024-12-10)

## What's Changed

- Catch orjson.JSONDecodeError on faulthy json script response

# Version 2024.12.0 (2024-12-05)

## What's Changed

- Add description to sysvar and program
- Add BidCos-Wired to list of primary interface candidates
- Remove obsolete try/except in homegear client

# Version 2024.11.11 (2024-11-25)

## What's Changed

- Enable central link management for HmIP-wired
- Reset temporary values before write

# Version 2024.11.10 (2024-11-24)

## What's Changed

- Add TIME_OF_OPERATION to smoke detector
- Switch multiplier from int to float
- Use more constants for cover and light

# Version 2024.11.9 (2024-11-22)

## What's Changed

- Make sysvars eventable

# Version 2024.11.8 (2024-11-21)

## What's Changed

- Add missing @service annotations
- Add performance measurement to @service
- Don't re-raise exception on internal services
- Move @service
- Remove @service from abstract methods

# Version 2024.11.7 (2024-11-19)

## What's Changed

- Set state_uncertain on value write

# Version 2024.11.6 (2024-11-19)

## What's Changed

- Cleanup data point

# Version 2024.11.5 (2024-11-19)

## What's Changed

- Fix returned version of client
- Improve store tmp value
- Store temporary value for sysvar data points

# Version 2024.11.4 (2024-11-19)

## What's Changed

- Add sysvar/program refresh to scheduler
- Run periodic tasks with an individual interval
- Store temporary value for polling client data points

# Version 2024.11.3 (2024-11-18)

## What's Changed

- Add interface(id) to performance log message
- Add interfaces_requiring_periodic_refresh to config
- Add periodic data refresh to CentralUnitChecker for some interfaces
- Add root path for virtual devices
- Maintain data_cache by interface
- Reduce MAX_CACHE_AGE to 10s

# Version 2024.11.2 (2024-11-17)

## What's Changed

- Add get_data_point_path to central
- Allow empty port for some interfaces
- Do reconnect/reload only for affected interfaces
- Ignore unknown interfaces
- Remove clients for not available interfaces

# Version 2024.11.1 (2024-11-14)

## What's Changed

- Add basic support for json clients
- Add data_point_path event
- Add getDeviceDescription, getParamsetDescription, listDevices, getValue, setValue, getParamset, putParamset to json_rpc
- Add option to refresh data by interface
- Add xml_rpc support flag to client
- Extend DP_KEY with interface_id
- Rename event to data_point_event

# Version 2024.11.0 (2024-11-04)

## What's Changed

- Improve on_time usage

# Version 2024.10.17 (2024-10-29)

## What's Changed

- Use enum for json/event keys
- Fire interface event, if data could not be fetched with script from CCU

# Version 2024.10.16 (2024-10-27)

## What's Changed

- Optimize MASTER data load

# Version 2024.10.15 (2024-10-27)

## What's Changed

- Rename model to better distinguish from HA

# Version 2024.10.14 (2024-10-26)

## What's Changed

- Use version from module

# Version 2024.10.13 (2024-10-24)

## What's Changed

- Disable climate temperature validation when turning off

# Version 2024.10.12 (2024-10-19)

## What's Changed

- Small tweaks to improve central link management

# Version 2024.10.11 (2024-10-19)

## What's Changed

- Align method parameters with CCU
- Use PRESS_SHORT for reportValueUsage
- Check if channel has programs before deleting links

# Version 2024.10.10 (2024-10-18)

## What's Changed

- Add create_central_links and remove_central_links to device and central

# Version 2024.10.9 (2024-10-17)

## What's Changed

- Add central link methods to click event
- Add reportValueUsage, addLink, removeLink and getLinks to client
- Add version to code
- Fix wrong channel assignment for HmIP-DRBLI4
- Add operation_mode to channel

# Version 2024.10.8 (2024-10-15)

## What's Changed

- Add services to copy climate schedules
- Make validation for climate schedules optional

# Version 2024.10.7 (2024-10-12)

## What's Changed

- Add MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE, OPTIMUM_START_STOP and TEMPERATURE_OFFSET to climate
- Improve profile validation
- Use regex to identify schedule profiles

# Version 2024.10.6 (2024-10-11)

## What's Changed

- Export SIMPLE_PROFILE_DICT, SIMPLE_WEEKDAY_LIST

# Version 2024.10.5 (2024-10-11)

## What's Changed

- Add simple climate schedule service to store profiles
- Reuse existing dict types
- Convert schedule time from minutes to hh:mm

# Version 2024.10.4 (2024-10-09)

## What's Changed

- Add basic climate schedule services
- Refactor constants
- Rename climate enums and constants to better distinguish from HA

# Version 2024.10.3 (2024-10-07)

## What's Changed

- Add missing import entries

# Version 2024.10.2 (2024-10-07)

## What's Changed

- Simplify entity imports

# Version 2024.10.1 (2024-10-04)

## What's Changed

- Fix rx_mode lazy_config
- Make DEFAULT optional due to homegear support
- Move context var to own module

# Version 2024.10.0 (2024-10-03)

## What's Changed

- Add config option for max read workers
- Disable collector for stop events
- Improve logging when raising exception
- Log exception at the most outer service
- Make UPDATEABLE optional due to homegear support
- Raise exception on set_value, put_paramset
- Remove command queue

# Version 2024.9.12 (2024-09-26)

## What's Changed

- Add config option for listen ip address and port

# Version 2024.9.11 (2024-09-25)

## What's Changed

- Remove CED for ELV-SH-WUA / HmIP-WUA

# Version 2024.9.10 (2024-09-22)

## What's Changed

- Add name to channel
- Catch bind address errors of xml rpc server
- Refactor get_events, get_new_entities
- Remove unnecessary checks
- Separate enable/disable sysvar and program scan
- Use paramset_description from channel

# Version 2024.9.9 (2024-09-21)

## What's Changed

- Use channel instead of channel_addresses

# Version 2024.9.8 (2024-09-21)

## What's Changed

- Refactor device/entity to extract channel
- Replace device_type by model
- Shorten names

# Version 2024.9.7 (2024-09-15)

## What's Changed

- Add bind_collector to all relevant methods with option to disable it
- Identify bind_collector annotated methods
- Mark externally accessed services with service_call if bind_collector is not appropriate

# Version 2024.9.6 (2024-09-13)

## What's Changed

- Add missing PayloadMixin
- Adjust payload and path
- Rename value_property to state_property

# Version 2024.9.5 (2024-09-03)

## What's Changed

- Improve device_description usage
- Reduce number of required characters for an address identification

# Version 2024.9.4 (2024-09-03)

## What's Changed

- Use validator for local schema

# Version 2024.9.3 (2024-09-02)

## What's Changed

- Improve validation of channel address, device address, password and htmltag

# Version 2024.9.2 (2024-09-02)

## What's Changed

- Allow str for get_paramset

# Version 2024.9.1 (2024-09-02)

## What's Changed

- Improve paramset key check

# Version 2024.9.0 (2024-09-01)

## What's Changed

- Add getLinkPeers XmlRPC method
- Do not create update entities that are not updatable (manually remove obsolete update entities)
- Only try device update refresh if device is updatable
- Refactor update entity

# Version 2024.8.15 (2024-08-29)

## What's Changed

- Add check for link paramsets
- Avoid permanent cache save on remove device
- Check rx_mode
- Ensure only one load/save of cache file at time
- Load all paramsets
- Small definition fix for DALI
- Use TypedDict for device_description
- Use TypedDict for parameter_data

# Version 2024.8.14 (2024-08-26)

## What's Changed

- Add paramset_key to entity_key
- Switch typing of paramset_key from str to ParamsetKey
- Mark only level as relevant entity for DALI

# Version 2024.8.13 (2024-08-25)

## What's Changed

- Check/convert values of manual executed put_paramset/set_value

# Version 2024.8.12 (2024-08-24)

## What's Changed

- Add additional validation on config parameters

# Version 2024.8.11 (2024-08-21)

## What's Changed

- Make HEATING_COOLING visible for thermostats
- Use only relevant IP for XmlRPC Server listening on

# Version 2024.8.10 (2024-08-20)

## What's Changed

- Cleanup ParamsetDescriptionCache
- Cleanup DeviceDescriptionCache

# Version 2024.8.9 (2024-08-20)

## What's Changed

- Avoid excessive memory usage in cache

# Version 2024.8.8 (2024-08-18)

## What's Changed

- Refactor folder handling

# Version 2024.8.7 (2024-08-18)

## What's Changed

- Fix empty channel on get_parameters

# Version 2024.8.6 (2024-08-18)

## What's Changed

- Fix get_parameters

# Version 2024.8.5 (2024-08-17)

## What's Changed

- Add un_ignore_candidates to central

# Version 2024.8.4 (2024-08-16)

## What's Changed

- Make load only relevant paramset descriptions configurable
- Add UN_IGNORE_WILDCARD to get_parameters

# Version 2024.8.3 (2024-08-15)

## What's Changed

- Ignore parameters on un ignore parameter list

# Version 2024.8.2 (2024-08-15)

## What's Changed

- Add CED for ELV-SH-WUA / HmIP-WUA
- Refactor get_parameters for unignore_candidates

# Version 2024.8.1(2024-08-02)

## What's Changed

- Refactor entity path
- Allow undefined generic entities besides CE

# Version 2024.8.0 (2024-08-01)

## What's Changed

- Reduce data load, if only device description is updated

# Version 2024.7.1 (2024-07-27)

## What's Changed

- Enable button lock for hm devices

# Version 2024.7.0 (2024-07-26)

## What's Changed

- Rename last_updated -> modified_at
- Rename last_refreshed -> refreshed_at
- Add button lock CE
- Add time units to HmIP-RGBW calls

# Version 2024.5.6 (2024-05-31)

## What's Changed

- Catch TypeError on SysVar import

# Version 2024.5.5 (2024-05-29)

## What's Changed

- Fix address for bidcos wired virtual device

# Version 2024.5.4 (2024-05-23)

## What's Changed

- Enable CE visible entities by default

# Version 2024.5.3 (2024-05-16)

## What's Changed

- Fix value assignment to lock enums
- Set open tilt level back to 100%
- Use PEP 695 typing

# Version 2024.5.2 (2024-05-14)

## What's Changed

- Move command_queue handling from device to channel
- Add level sensors to cover/blind
- Allow changing level or tilt while blind is moving by @sleiner

# Version 2024.5.1 (2024-05-06)

## What's Changed

- Improve callback register/unregister

# Version 2024.5.0 (2024-05-01)

## What's Changed

- Make some items from value_property to property
- Rename callbacks
- Fix Homegear reconnect
- Add COLOR_BEHAVIOUR to HmIP-BSL

# Version 2024.4.12 (2024-04-24)

## What's Changed

- Fix missing param in unregister_entity_updated_callback
- Set open tilt level to 50%

# Version 2024.4.11 (2024-04-24)

## What's Changed

- Add command queue
- Move open/close from IpBlind to Blind
- Use central_client_factory fixture
- Ensure central.stop() is called in tests

# Version 2024.4.10 (2024-04-21)

## What's Changed

- Add wait_for_callback to collector
- Wait for target value in wait_for_state_change_or_timeout

# Version 2024.4.9 (2024-04-20)

## What's Changed

- Decompose combined parameter
- Return affected entity keys for service calls
- Add callback to unregister on register return
- Add option to wait for set_value/put_paramset callback

# Version 2024.4.8 (2024-04-13)

## What's Changed

- Make entity event async
- Extract looper from central and reuse for json/xml_rpc
- Move loop_check to async_support
- Record last value send

# Version 2024.4.7 (2024-04-13)

## What's Changed

- Rename loop_safe to loop_check
- Reduce loop_check to minimum
- Update ruff rules / requirements

# Version 2024.4.6 (2024-04-10)

## What's Changed

- Remove unused callback from tests
- Add loop_safe annotation
- Remove entity_data_event_callback
- Make backend_system_callback loop aware

# Version 2024.4.5 (2024-04-09)

## What's Changed

- Align callback naming

# Version 2024.4.4 (2024-04-09)

## What's Changed

- Unify entity update/refresh events

# Version 2024.4.3 (2024-04-09)

## What's Changed

- Restructure check_connection
- Make xml_rpc event async
- Block central stop until tasks are finished

# Version 2024.4.2 (2024-04-08)

## What's Changed

- Adjust cache max size
- Update ruff rules

# Version 2024.4.1 (2024-04-05)

## What's Changed

- Fix register refreshed entity
- Refactor callback naming

# Version 2024.4.0 (2024-04-02)

## What's Changed

- Remove support for python 3.11
- Remove python 3.11 for github tests and pylint
- Use py 3.12 for mypy and pylint
- Use more list comprehension
- Customize HmIP-DRG-DALI

# Version 2024.3.1 (2024-03-12)

## What's Changed

- Add additional parameter to HBW-LC4-IN4-DR
- Add check if init is running in the main thread

# Version 2024.3.0 (2024-03-01)

## What's Changed

- Add HBW-LC4-IN4-DR

# Version 2024.2.4 (2024-02-13)

## What's Changed

- Group entities to sub devices / base channels
- Add mapping for fixed color channel
- Refactor entity name data

# Version 2024.2.3 (2024-02-12)

## What's Changed

- Rename func to make_ce_func
- Add fixed mapping for HBW-LC-RGBWW-IN6-DR
- Fix mapping of HmIP-HDM

# Version 2024.2.2 (2024-02-11)

## What's Changed

- Add option to un ignore mechanism to ignore the automatic creation of custom entities by device type
- Remove incomplete/wrong mapping for HBW-LC-RGBWW-IN6-DR
- Fix mapping of HmIP-HDM

# Version 2024.2.1 (2024-02-02)

## What's Changed

- Accept float as input for int numbers

# Version 2024.2.0 (2024-02-01)

## What's Changed

- Ignore empty unignore line
- All MASTER parameters must be unignored

# Version 2024.1.11 (2024-01-31)

## What's Changed

- Remove deprecation warnings for py3.12
- Fix/improve unignore search

# Version 2024.1.10 (2024-01-28)

## What's Changed

- Remove old complex format for unignore

# Version 2024.1.9 (2024-01-26)

## What's Changed

- Move product group identification to client
- Add new pattern for unignore (parameter:paramset_key@device_type:channel_no)
- Allow all as unignore parameter for device_type and channel_no

# Version 2024.1.8 (2024-01-12)

## What's Changed

- Store old_value in entity model

# Version 2024.1.7 (2024-01-12)

## What's Changed

- Reload master data after config pending event
- Allow direct_call without cache wait time

# Version 2024.1.6 (2024-01-11)

## What's Changed

- Fix unignore doc and improve unignore tests
- Move unignore check to entity

# Version 2024.1.5 (2024-01-09)

## What's Changed

- Remove effects from HmIP-RGBW when in PWM mode

# Version 2024.1.4 (2024-01-07)

## What's Changed

- Fix relevant entities for HmIP-RGBW

# Version 2024.1.3 (2024-01-07)

## What's Changed

- Add duration=111600 when ramp_time used for HmIP-RGBW

# Version 2024.1.2 (2024-01-07)

## What's Changed

- Only consider relevant entities for HmIP-RGBW

# Version 2024.1.1 (2024-01-05)

## What's Changed

- Allow ordered execution of collector paramsets
- Add python 3.12 for github tests and pylint

# Version 2024.1.0 (2024-01-03)

## What's Changed

- Add duration=0 when ramp_time used for HmIP-RGBW

# Version 2023.12.4 (2023-12-19)

## What's Changed

- Add HB-LC-Bl1-Velux to cover

# Version 2023.12.3 (2023-12-16)

## What's Changed

- Set attributes of dataclasses
- Add another reason to ping pong mismatch

# Version 2023.12.2 (2023-12-15)

## What's Changed

- Save all rooms to entity model

# Version 2023.12.1 (2023-12-01)

## What's Changed

- Central name must not contain the identifier separator (@)

# Version 2023.12.0 (2023-12-01)

## What's Changed

- Add support for away_mode and classic homematic thermostats
- Collect config validation errors

# Version 2023.11.4 (2023-11-22)

## What's Changed

- Don't send ts with ping pong if it should not be handled

# Version 2023.11.3 (2023-11-21)

## What's Changed

- Clear ping pong cache on proxy init

# Version 2023.11.2 (2023-11-21)

## What's Changed

- Refactor ping pong, remove semaphore

# Version 2023.11.1 (2023-11-20)

## What's Changed

- Improve ping/pong mechanism. Fire event, if mismatch is 15 within 5 Minutes

# Version 2023.11.0 (2023-11-01)

## What's Changed

- Use last_refreshed for validation check

# Version 2023.10.14 (2023-10-29)

## What's Changed

- Cleanup cover
- Replace last_updated by last_refreshed
- Rename fire events
- Switch formatting from black to ruff-format

# Version 2023.10.13 (2023-10-28)

## What's Changed

- Fix service enable_away_mode_by_calendar
- Add class method default_platform

# Version 2023.10.12 (2023-10-15)

## What's Changed

- Ignore switch to sensor if un ignored
- Update un ignore documentation

# Version 2023.10.11 (2023-10-13)

## What's Changed

- Remove WrapperEntity

# Version 2023.10.10 (2023-10-12)

## What's Changed

- Align method signatures
- Remove get_update_entities

# Version 2023.10.9 (2023-10-12)

## What's Changed

- Fix register_update_callback for update
- Add filter options to device.get_entity\*
- Send relevant entities instead of devices in callback

# Version 2023.10.8 (2023-10-11)

## What's Changed

- Register external sources with custom identifier
- Remove subscribed_entity_unique_identifiers
- Rename custom_identifier to custom_id
- Rename unique_identifier to unique_id

# Version 2023.10.7 (2023-10-10)

## What's Changed

- Adjust typing after move to more enums
- Add measure_execution_time to writing methods
- Fix send sysvar #1249
- Add HmIPW-SCTHD

# Version 2023.10.6 (2023-10-08)

## What's Changed

- Add faultCode and faultString to xmlrpc.client.Fault
- Use Mapping/Set for readonly access
- Use enum for CE fields
- Use Parameter for ED

# Version 2023.10.5 (2023-10-07)

## What's Changed

- Add started property to central
- Rename:
  - value_list -> values
  - effect_list -> effects
- Add more checks to get/set value from/tp values
- Use more tuple instead of list
- Cleanup code
- Collect subscribed entities in central

# Version 2023.10.4 (2023-10-03)

## What's Changed

- Cleanup exception handling
- Reduce log output for InternalBackendException

# Version 2023.10.3 (2023-10-03)

## What's Changed

- Small fix to re raise InternalBackendException

# Version 2023.10.2 (2023-10-03)

## What's Changed

- Catch 'internal error' on \_get_auth_enabled. Relevant for for CCU2 users

# Version 2023.10.1 (2023-10-02)

## What's Changed

- Use enum for JsonRPC and XmlRPC methods
- Get supported JsonRPC and XmlRPC methods and check against used methods

# Version 2023.10.0 (2023-10-01)

## What's Changed

- Code cleanup
  - Remove Hm prefix from enums
  - Use enum for parameters
  - Use more existing constants

# Version 2023.9.8 (2023-09-30)

## What's Changed

- Improve caching
  - Cleanup cache naming
  - Remove max_age from most method signatures
  - Simplify data cache
  - Rename some cache methods
- Remove attr prefix

# Version 2023.9.7 (2023-09-29)

## What's Changed

- Add check to BaseHomematicException
- Reduce log level to 'warning' for get_all_device_data 'JSONDecodeError' exceptions
- Update requirements

# Version 2023.9.6 (2023-09-29)

## What's Changed

- Use freezegun for climate test
- Update ReGa-Script fetch_all_device_data.fn by @Baxxy13
- Parameterize call to fetch_all_device_data.fn
- Simplify json rpc post code
- Improve for ConnectionProblemIssuer json rpc
- Improve handle_exception_log
- Avoid repeated logs
- Move get_system_information to json_rpc
- Add **str** to client and central

# Version 2023.9.5 (2023-09-23)

## What's Changed

- Cleanup light code
- Use more enums for climate, cover, lock
- Use TypedDict for light, siren args
- Update requirements

# Version 2023.9.4 (2023-09-21)

## What's Changed

- Use more assignment-expr
- Make \_LOGGER final

# Version 2023.9.3 (2023-09-18)

## What's Changed

- Improve typing
- Refactor get_paramset_description

# Version 2023.9.2 (2023-09-17)

## What's Changed

- Cleanup logger
- Refactor client and central modules
- Move bind_collector to platforms.entity
- Move config/value_property to platforms.decorators
- Move measure_execution_time to decorators
- Move definition exporter to device
- Move HM_INTERFACE_EVENT_SCHEMA to central
- Update requirements

# Version 2023.9.1 (2023-09-06)

## What's Changed

- Re add channel 7 for HmIPW-WRC6
- Reduce log level for exceptions in fetch_paramset_description
- Filter SSLErrors by code

# Version 2023.9.0 (2023-09-03)

## What's Changed

- Refactor cover api

# Version 2023.8.14 (2023-08-30)

## What's Changed

- Reduce visibility of local constants
- Convert StrEnum and IntEnum in proxy

# Version 2023.8.13 (2023-08-28)

## What's Changed

- Fix measure_execution_time decorator for sync methods
- Add async support to callback_system_event
- Replace constants enums

# Version 2023.8.12 (2023-08-27)

## What's Changed

- Remove unused const
- Remove dead code
- Optimize get readable entities for MASTER

# Version 2023.8.11 (2023-08-25)

## What's Changed

- Always set color_behaviour for HmIPW-WRC6

# Version 2023.8.10 (2023-08-25)

## What's Changed

- Extend HmIPW-WRC6 implementation

# Version 2023.8.9 (2023-08-23)

## What's Changed

- Add decorator to measure function execution time
- Extend HmIPW-WRC6 implementation

# Version 2023.8.8 (2023-08-21)

## What's Changed

- Fix get_all_system_variables return value

# Version 2023.8.7 (2023-08-21)

## What's Changed

- Add SSLError to XmlRpcProxy and JsonRpcAioHttpClient
- Make integration more robust against json result failures

# Version 2023.8.6 (2023-08-17)

## What's Changed

- Remove use_caches and load_un_ignore from central config
- Remove obsolete comments
- Align sslcontext creation with Home Assistant

# Version 2023.8.5 (2023-08-16)

## What's Changed

- Improve testing:
  - Set client_session to None
  - Remove unnecessary async from create_central
- Make start_direct a config option

# Version 2023.8.4 (2023-08-14)

## What's Changed

- Improve testing:
  - Extract ClientLocal code from production code
  - Use own main package for ClientLocal
  - Patch permanent till teardown

# Version 2023.8.3 (2023-08-12)

## What's Changed

- Update project setup
- Restructure test helper
- Add ping pong tests
- Avoid multiple central starts

# Version 2023.8.2 (2023-08-06)

## What's Changed

- Improve exception and log handling

# Version 2023.8.1 (2023-08-04)

## What's Changed

- Prepare backend for HA issue usage

# Version 2023.8.0 (2023-08-01)

## What's Changed

- Remove only the starting device name from entity name
- Remove title from program and sysvar names

# Version 2023.7.6 (2023-07-29)

## What's Changed

- Refactor Json error handling / logging
- Use ping pong only for CCU
- Add primary_client attribute to central_unit

# Version 2023.7.5 (2023-07-26)

## What's Changed

- Add SystemInformation to client api
- Send credentials on XmlRPC api only when authentication is enabled in CCU
- Remove support for python 3.10
- Add available_interfaces to SystemInformation

# Version 2023.7.4 (2023-07-18)

## What's Changed

- Update requirements
- Add identifier to device
- Rename ENTITY_NO_CREATE to NO_CREATE
- Extend Channel
- Add channel related attributes to entity
- Add kwargs to update_entity
- Call update_entity for ENTITY_EVENTS
- Ignore click events on plugs
- Add manufacturer to device

# Version 2023.7.3 (2023-07-13)

## What's Changed

- Fire interface event about ping/pong mismatch
- Add message to fire_interface_event
- Add schema for interface event

# Version 2023.7.2 (2023-07-12)

## What's Changed

- Add new Events PRESS_LOCK and PRESS_UNLOCK for HmIP-WKP

# Version 2023.7.1 (2023-07-11)

## What's Changed

- Log an error about the ping/pong count mismatch

# Version 2023.7.0 (2023-07-07)

## What's Changed

- Project file maintenance
  - Replace isort with ruff
  - Move overlapping pylint rules to ruff, disable mypy overlap

# Version 2023.6.1 (2023-06-23)

## What's Changed

- Fix tunable white support for hmIP-RGBW
- Avoid creating entities that are not usable in selected device operation mode for hmIP-RGBW
- Update requirements

# Version 2023.6.0 (2023-06-01)

## What's Changed

- Update requirements
- Do not create update entities for virtual remotes
- Cleanup FIX_UNIT_BY_PARAM

# Version 2023.5.2 (2023-05-14)

## What's Changed

- Improve update_device_firmware

# Version 2023.5.1 (2023-05-11)

## What's Changed

- Refactor device description cache handling
- Add device firmware update handling
- Make interface an enum
- Add product group to device

# Version 2023.5.0 (2023-05-01)

## What's Changed

- Remove unsupported on_time / refactor HmIP-RGBW
- Update requirements

# Version 2023.4.5 (2023-04-28)

## What's Changed

- Fix division by zero for HmIP-RGBW
- Remove color_temperature from RGBW

# Version 2023.4.4 (2023-04-28)

## What's Changed

- Add missing channel for HmIP-RGBW

# Version 2023.4.3 (2023-04-27)

## What's Changed

- Update requirements
- Add HmIP-RGBW

# Version 2023.4.2 (2023-04-24)

## What's Changed

- Update requirements
- Fix cover (HDM2) no longer working

# Version 2023.4.0 (2023-04-16)

## What's Changed

- Update requirements
- Add log message to negative password check
- Fix 'Cannot parse hex-string value'

# Version 2023.3.1 (2023-03-17)

## What's Changed

- Add name to tasks
- Improve typing
- Move callback calls into exception block
- Remove avoidable usage of deepcopy
- Add dependabot
- Update requirements
- Drop pyupgrade, autoflake, flake8 in favor of ruff
- Refactor cover, add set_combined_position
- Add is_in_multiple_channels to base entity

# Version 2023.3.0 (2023-03-01)

## What's Changed

- Update ruff, adjust module aliases
- Fix spamming CCU logs with errors (#981)

# Version 2023.2.11 (2023-02-24)

## What's Changed

- Update ruff, fix comments
- Switch to orjson
- Fix climate: compare set temperature to target temperature

# Version 2023.2.10 (2023-02-23)

## What's Changed

- Use sets for central callbacks
- Add get_all_entities for device

# Version 2023.2.9 (2023-02-18)

## What's Changed

- Fix property types
- Ensure modules for platforms are loaded
- Use local dicts for device lists
- Clear central data cache if identified as outdated
- Avoid redundant cache loads within init phase
- Extract value preparation from send_value
- Differentiate between input and default parameter type
- Fix asyncio-dangling-task (RUF006)
- Add typed dict for light and siren

# Version 2023.2.8 (2023-02-11)

## What's Changed

- Add project setup script
- Add entity_data event
- Add payload mixin
- Cleanup module dependencies
- Use cache decorators for some high-traffic methods
- Allow that channel_no could be None
- Add and use get_channel_address
- Add HmIP-SWSD as siren
- Raise CALLBACK_WARN_INTERVAL to 10 minutes

# Version 2023.2.7 (2023-02-07)

## What's Changed

- Disable validation of state change for action and button
- Check if entity is writable on send

# Version 2023.2.6 (2023-02-07)

## What's Changed

- Add missing bind_collector
- Add more `Final` typing
- Add option to collector to disable put_paramset
- Add on_time Mixin to temporary store on_time
- Add pre-commit check
- Basic linting for tests

# Version 2023.2.5 (2023-02-05)

## What's Changed

- Fix GitHub build/publish
- Add comments to parameter_visibility
- Use `put_paramset` only when there is more than one parameter to sent
- Use only one implementation for garage doors (HO/TM)
- Avoid backend calls if value/state doesn't change
  - If an entity (e.g. `switch`) has only **one** parameter that represents its state, then a call to the backend will be made,
    if the parameter value sent is not identical to the current state.
  - If an entity (e.g. `cover`, `climate`, `light`) has **multiple** parameters that represent its state, then a call to the backend will be made,
    if one of these parameter values sent is not identical to its current state.
  - Not covered by this approach:
    - platforms: lock and siren.
    - services: `stop_cover`, `stop_cover_tilt`, `enable_away_mode_*`, `disable_away_mode`, `set_on_time_value`
    - system variables
- Add virtual channels for HmIP cover/blind:
  - Channel no as examples from HmIP-BROLL. The implementation of the first actor channel (4) remains unchanged, which means that this channel (4) shows the correct cover position from sensor channel (3).
    The other actor channels (5+6) are generated as initially deactivated and only use the cover position from their own channel after activation.

# Version 2023.2.1 (2023-02-01)

## What's Changed

- Separate check for parameter is un_ignored based on if it should be hidden or not

# Version 2023.2.0 (2023-02-01)

## What's Changed

- Log validation exceptions in central
- Add typing to decorators
- Add tests for better code coverage

# Version 2023.1.8 (2023-01-29)

## What's Changed

- Cleanup LOGGER messages
- Cleanup code base with ruff
- Ensure the signal handler gets called at most once by @mtdcr
- Fix stop central, if another central is active on the same XmlRPC server
- JsonRpcAioHttpClient: Allow empty password by @mtdcr
- Remove VALVE_STATE from HmIPW-FALMOT-C12
- Remove put_paramset from custom_entity
- Remove set_value, put_paramset from central
- Remove support for python 3.9
- Remove to int converter for HmIP-SCTH230 CONCENTRATION
- Replace old-style union syntax
- Validate password with regex (warning only!)

# Version 2023.1.7 (2023-01-24)

## What's Changed

- Aggregate calls to backend
- Fix HmIP-MOD-TM: inverted direction

# Version 2023.1.6 (2023-01-22)

## What's Changed

- Add a new custom entity type for windows drive
- Return True if sending service calls succeed

# Version 2023.1.5 (2023-01-20)

## What's Changed

- Add ExtendedConfig and use for additional_entities
- Add ExtendedConfig to custom entities
- Add LED_STATUS to HM-OU-LED16
- Allow multiple CustomConfigs for a hm device
- Cleanup test imports
- Increase the line length to 99
- Remove LOWBAT from HM-LC-Sw1-DR
- Remove obsolete ED_ADDITIONAL_ENTITIES_BY_DEVICE_TYPE from entity_definition
- Replace custom entity config data structure by CustomConfig
- Sort lists in parameter_visibility.py

# Version 2023.1.4 (2023-01-16)

## What's Changed

- Add helper, central tests
- Add more tests and test based refactorings
- Reduce backend calls and logging during lost connection
- Remove obsolete parse_ccu_sys_var
- Update color_conversion threshold by @guillempages

# Version 2023.1.3 (2023-01-13)

## What's Changed

- Unify event parameters
- Refactor entity.py for better event support
- Fix wrong warning after set_system_variable
- Add validation to event_data

# Version 2023.1.2 (2023-01-10)

## What's Changed

- Remove OPERATING_VOLTAGE from HmIP-BROLL, HmIP-FROLL
- Remove loop from test signature
- Cleanup ignore/unignore handling and add tests

# Version 2023.1.1 (2023-01-09)

## What's Changed

- No longer create ClientSession in json_rpc_client for tests
- Add backend tests
- Use mocked local client to check method_calls
- Remove sleep after connection_checker stops
- Remove LOWBAT from HM-LC-Sw1-Pl, HM-LC-Sw2-FM
- Simplify entity de-/registration
- Refactor add/delete device and add tests
- Add un_ignore_list to test config
- Allow unignore for DEVICE_ERROR_EVENTS

# Version 2023.1.0 (2023-01-01)

## What's Changed

- API Cleanup
- Allow to disable cache
- Allow to disable un_ignore load
- Add local client
- Use local client in tests
- Move event() code to central_unit
- Move listDevices() code to central_unit

# Version 2022.12.12 (2022-12-30)

## What's Changed

- Add un_ignore list to central config
- Fix entity_definition schema
- Rename cache_dict to persistent_cache
- Reduce access to internal complex objects for custom_component

# Version 2022.12.11 (2022-12-28)

## What's Changed

- Rename climate presets from 'Profile _' to 'week*program*_'
- Add support for python 3.11

# Version 2022.12.10 (2022-12-27)

## What's Changed

- Make constant assignment final
- Fix native device units

# Version 2022.12.9 (2022-12-25)

## What's Changed

- Remove empty unit for numeric sysvars
- Add enable_default to entity
- Remove some warn level parameters from ignore list

# Version 2022.12.8 (2022-12-22)

## What's Changed

- Reformat code / check with flake8
- Refactor entity inheritance

# Version 2022.12.7 (2022-12-21)

## What's Changed

- Send ERROR\_\* parameters as homematic.device_error event

# Version 2022.12.6 (2022-12-20)

## What's Changed

- Add additional checks for custom entities
- Code Cleanup

# Version 2022.12.5 (2022-12-17)

## What's Changed

- Code Cleanup
- Remove sub_type from model to simplify code
- Remove obsolete methods
- Refactor binary_sensor check
- Convert value_list to tuple
- Use tuple for immutable lists

# Version 2022.12.4 (2022-12-13)

## What's Changed

- Fix disable away_mode in climate. Now goes back to the origin control_mode.

# Version 2022.12.3 (2022-12-12)

## What's Changed

- Disable temperature validation for setting to off for HM heating group HM-CC-VG-1

# Version 2022.12.2 (2022-12-09)

## What's Changed

- Add HM-LC-AO-SM as light
- Remove hub from HmPlatform
- Hub is no longer an entity

# Version 2022.12.1 (2022-12-01)

## What's Changed

- Improve naming of modules
- Add new platform for text sysvars

# Version 2022.12.0 (2022-12-01)

## What's Changed

- Add transition to light turn_off
- Remove min brightness of 10 for lights

# Version 2022.11.2 (2022-11-13)

## What's Changed

- Generalize some collection helpers

# Version 2022.11.1 (2022-11-03)

## What's Changed

- Rename protected attributes to \_attr\*
- Code cleanup
- Add option to wrap entities to a different platform
  - Wrap LEVEL of HmIP-TRV\*, HmIP-HEATING to sensor

# Version 2022.11.0 (2022-11-02)

## What's Changed

- Rename ATTR*HM*_ to HM_
- Use generic property implementation

# Version 2022.10.10 (2022-10-25)

## What's Changed

- Use min_temp if target_temp < min_temp
- Remove event_loop from signatures
- Refactor central_config, create xml_rpc server in central_unit

# Version 2022.10.9 (2022-10-23)

## What's Changed

- Fix don't hide unignored parameters
- Refactor refesh_entity_data. Allow restriction to paramset and cache age.

# Version 2022.10.8 (2022-10-21)

## What's Changed

- Add semaphore to fetch sysvar and programs from backend

# Version 2022.10.7 (2022-10-20)

## What's Changed

- Accept some existing prefix for sysvars and programs to avoid additional prefixing with Sv* / P*
  - accepted sysvar prefixes: V*, Sv*
  - accepted program prefixes: P*, Prg*
- Read min/max temperature for climate devices
- Min set temperature for thermostats is now 5.0 degree. 4.5. degree is only off

# Version 2022.10.6 (2022-10-15)

## What's Changed

- Replace data\_\* by HmDataOperationResult
- Use HmHvacMode HEAT instead of AUTO for simple thermostats
- Add HUMIDITY and ACTUAL_TEMPERATURE to heating groups

# Version 2022.10.5 (2022-10-11)

## What's Changed

- Set Hm Thermostat to manual mode before switching off

# Version 2022.10.4 (2022-10-10)

## What's Changed

- Allow entity creation for some internal parameters

# Version 2022.10.3 (2022-10-10)

## What's Changed

- Fix HM Blind/Cover custom entity types

# Version 2022.10.2 (2022-10-08)

## What's Changed

- Make connection checker more resilient:
- Reduce connection checker interval to 15s
- Connection is not connected, if three consecutive checks fail.

# Version 2022.10.1 (2022-10-05)

## What's Changed

- Ignore OPERATING_VOLTAGE for HmIP-PMFS
- Add ALPHA-IP-RBG

# Version 2022.10.0 (2022-10-01)

## What's Changed

- Rename hub event
- Remove "Servicemeldungen" from sysvars. It's already included in the hub_entity (sensor.{instance_name})

# Version 2022.9.1 (2022-09-20)

## What's Changed

- Improve XmlServer shutdown
- Add name to threads and executors
- Improve ThreadPoolExecutor shutdown

# Version 2022.9.0 (2022-09-02)

## What's Changed

- Exclude value from event_data if None

# Version 2022.8.15 (2022-08-27)

## What's Changed

- Fix select entity detection

# Version 2022.8.14 (2022-08-23)

## What's Changed

- Exclude STRING sysvar from extended check

# Version 2022.8.13 (2022-08-23)

## What's Changed

- Allow three states for a forced availability of a device

# Version 2022.8.12 (2022-08-23)

## What's Changed

- Add device_type to device availability event
- Code deduplication and small fixes

# Version 2022.8.11 (2022-08-18)

## What's Changed

- Adjust logging (level and message)
- Delete sysvar if type changes

# Version 2022.8.10 (2022-08-16)

## What's Changed

- Improve readability of XmlRpc server
- Remove module data

# Version 2022.8.9 (2022-08-16)

## What's Changed

- Fix check if thread is started

# Version 2022.8.8 (2022-08-16)

## What's Changed

- Remove unused local_ip from XmlRPCServer
- Create all XmlRpc server by requested port(s)

# Version 2022.8.7 (2022-08-12)

## What's Changed

- Fix hs_color for CeColorDimmer(HM-LC-RGBW-WM)

# Version 2022.8.6 (2022-08-12)

## What's Changed

- Reduce api calls for light

# Version 2022.8.5 (2022-08-11)

## What's Changed

- Add cache for rega script files

# Version 2022.8.4 (2022-08-08)

## What's Changed

- Add platform as field and remove obsolete constructors
- Reduce member

# Version 2022.8.3 (2022-08-07)

## What's Changed

- Remove CHANNEL_OPERATION_MODE from cover ce
- Refactor get_value/set_value
- Remove domain from model
- Rename unique_id to unique_identifier
- Remove should_poll from model

# Version 2022.8.2 (2022-08-02)

## What's Changed

- Remove obsolete methods
- Remove obsolete device_address parameter
- Rename sysvar to hub entity
- Add program buttons

# Version 2022.8.0 (2022-08-01)

## What's Changed

- Fix pylint, mypy issues due to newer versions
- Remove properties of final members
- Add types to Final
- Init entity fields in init method
- Remove device_info from model
- Remove attributes from model

# Version 2022.7.14 (2022-07-28)

## What's Changed

- Add HmIP-BS2 to custom entities
- Remove force and add call_source for getValue

# Version 2022.7.13 (2022-07-22)

## What's Changed

- Cleanup API
- Limit init cache time usage
- Avoid repetitive calls to CCU within max_age_seconds

# Version 2022.7.12 (2022-07-21)

## What's Changed

- Add ELV-SH-BS2 to custom entities
- Code Cleanup
- Rearrange validity check
- Cleanup entity code

# Version 2022.7.11 (2022-07-19)

## What's Changed

- Raise interval for alive checks

# Version 2022.7.10 (2022-07-19)

## What's Changed

- Use entities instead of values inside custom entities
- Fix \_check_connection for Homegear/CCU

# Version 2022.7.9 (2022-07-17)

## What's Changed

- Remove state_uncertain from default attributes

# Version 2022.7.8 (2022-07-13)

## What's Changed

- Fix entity update

# Version 2022.7.7 (2022-07-12)

## What's Changed

- Fix naming of custom entity

# Version 2022.7.6 (2022-07-12)

## What's Changed

- Fix last_state handling for custom entities

# Version 2022.7.5 (2022-07-11)

## What's Changed

- Rename value_uncertain to state_uncertain
- Add state_uncertain to custom entity

# Version 2022.7.4 (2022-07-11)

## What's Changed

- Set value_uncertain to True if no data could be loaded from CCU

# Version 2022.7.3 (2022-07-10)

## What's Changed

- Set default value for hub entity to None

# Version 2022.7.2 (2022-07-10)

## What's Changed

- Align entity naming to HA entity name
- Ensure entity value refresh after reconnect
- Ignore further parameters by device

# Version 2022.7.1 (2022-07-07)

## What's Changed

- Better distinguish between NO_CACHE_ENTRY and None

# Version 2022.7.0 (2022-07-07)

## What's Changed

- Switch to calendar versioning

# Version 1.9.4 (2022-07-03)

## What's Changed

- Load MASTER data on initial load

# Version 1.9.3 (2022-07-02)

## What's Changed

- Fix export of device definitions

# Version 1.9.2 (2022-07-01)

## What's Changed

- Use CHANNEL_OPERATION_MODE for devices with MULTI_MODE_INPUT_TRANSMITTER, KEY_TRANSCEIVER channels
- Re-Add HmIPW-FIO6 to custom device handling

# Version 1.9.1 (2022-06-29)

## What's Changed

- Remove HmIPW-FIO6 from custom device handling

# Version 1.9.0 (2022-06-09)

## What's Changed

- Refactor entity name creation
- Cleanup entity selection
- Add button to virtual remote

# Version 1.8.6 (2022-06-07)

## What's Changed

- Code cleanup

# Version 1.8.5 (2022-06-06)

## What's Changed

- Remove sysvars if deleted from CCU
- Add check for sysvar type in sensor
- Remove unused sysvar attributes
- Refactor HmEntityDefinition

# Version 1.8.4 (2022-06-04)

## What's Changed

- Refactor all sysvar script
- Use ext_marker script in combination with SysVar.getAll

# Version 1.8.3 (2022-06-04)

## What's Changed

- Refactor sysvar creation eventing

# Version 1.8.2 (2022-06-03)

## What's Changed

- Fix build

# Version 1.8.1 (2022-06-03)

## What's Changed

- Use marker in sysvar description for extended sysvars

# Version 1.8.0 (2022-06-02)

## What's Changed

- Enable additional sysvar entity types

# Version 1.7.3 (2022-06-01)

## What's Changed

- Add more debug logging

# Version 1.7.2 (2022-06-01)

## What's Changed

- Better differentiate between float and int for sysvars
- Switch from # as unit placeholder for sysvars to ' '
- Move sysvar length check to sensor

# Version 1.7.1 (2022-05-31)

## What's Changed

- Rename parameter channel_address to address for put/get_paramset

# Version 1.7.0 (2022-05-31)

## What's Changed

- Refactor system variables
- Add more types for sysvar entities

# Version 1.6.2 (2022-05-30)

## What's Changed

- Add more options for boolean conversions

# Version 1.6.1 (2022-05-29)

## What's Changed

- Fix entity definition for HMIP-HEATING

# Version 1.6.0 (2022-05-29)

## What's Changed

- Add impulse event
- Add LEVEL and STATE to HmIP-Heating group to display hvac_action
- Add device_type as model to attributes

# Version 1.5.4 (2022-05-24)

## What's Changed

- Add function attribute only if set

# Version 1.5.3 (2022-05-24)

## What's Changed

- Rename subsection to function

# Version 1.5.2 (2022-05-24)

## What's Changed

- Add subsection to attributes
- Use parser for internal sysvars

# Version 1.5.0 (2022-05-23)

## What's Changed

- Add option to replace too technical parameter name by friendly parameter name
- Ignore more parameters by device
- Use dataclass for sysvars
- Limit sysvar length to 255 chars due to HA limitations

# Version 1.4.0 (2022-05-16)

## What's Changed

- Block parameters by device_type that should not create entities in HA
- Fix remove instance on shutdown

# Version 1.3.1 (2022-05-13)

## What's Changed

- Increase connection timeout(30s->60s) and reconnect interval(90s->120s) to better support slower hardware

# Version 1.3.0 (2022-05-06)

## What's Changed

- Use unit for vars, if available
- Remove special handling for pydevccu
- Remove set boost mode to false, when preset is none for bidcos climate entities

# Version 1.2.2 (2022-05-02)

## What's Changed

- Fix light channel for multi dimmer

# Version 1.2.1 (2022-04-27)

## What's Changed

- Fix callback alive check
- Reconnect clients based on outstanding xml callback events

# Version 1.2.0 (2022-04-26)

## What's Changed

- Cleanup build

# Version 1.1.5 (2022-04-25)

## What's Changed

- Reorg light attributes
- Add on_time to light and switch

# Version 1.1.4 (2022-04-21)

## What's Changed

- Use min as default if default is unset for parameter_data

# Version 1.1.3 (2022-04-20)

## What's Changed

- Add CeColorDimmer
- Fix interface_event

# Version 1.1.2 (2022-04-12)

## What's Changed

- Add extra_params to \_post_script
- Add set_system_variable with string value
- Disallow html tags in string system variable

# Version 1.1.1 (2022-04-11)

## What's Changed

- Read # Version and serial in get_client

# Version 1.1.0 (2022-04-09)

## What's Changed

- Add BATTERY_STATE to DEFAULT_ENTITIES
- Migrate device_info to dataclass
- Add rega script (provided by @baxxy13) to get serial from CCU
- Add method to clean up cache dirs

# Version 1.0.6 (2022-04-06)

## What's Changed

- Revert to XmlRPC getValue and getParamset for CCU

# Version 1.0.5 (2022-04-05)

## What's Changed

- Limit hub_state to ccu only

# Version 1.0.4 (2022-03-30)

## What's Changed

- Use max # Version of interfaces for backend version
- Remove device as parameter from parameter_availability
- Add XmlRPC.listDevice to Client
- Add start_direct for starts without waiting for events (only for temporary usage)

# Version 1.0.3 (2022-03-30)

## What's Changed

- Revert to XmlRPC get# Version for CCU

# Version 1.0.2 (2022-03-29)

## What's Changed

- Revert to XmlRPC getParamsetDescription for CCU

# Version 1.0.1 (2022-03-29)

## What's Changed

- Add central_id for uniqueness of heating groups, sysvars and hub

# Version 1.0.0 (2022-03-28)

## What's Changed

- Simplify json usage
- Move json methods to json client
- Make json client independent from central config
- Add get_serial to validate
- Use serial for sysvar unique_ids
- Rename domain for test and example from hahm to homematicip_local

# Version 0.38.5 (2022-03-22)

## What's Changed

- Use interface_id for interface events
- Add support for color temp dimmer

# Version 0.38.4 (2022-03-21)

## What's Changed

- Fix interface name for BidCos-Wired

# Version 0.38.3 (2022-03-20)

## What's Changed

- Add check for available API method to identify BidCos Wired
- Cleanup backend identification

# Version 0.38.2 (2022-03-20)

## What's Changed

- Catch SysVar parsing exceptions

# Version 0.38.1 (2022-03-20)

## What's Changed

- Fix lock/unlock for HM-Sec-Key

# Version 0.38.0 (2022-03-20)

## What's Changed

- Add central validation
- Add jso_rpc.post_script

# Version 0.37.7 (2022-03-18)

## What's Changed

- Add additional system_listMethods to avoid errors on CCU

# Version 0.37.6 (2022-03-18)

## What's Changed

- Add JsonRPC.Session.logout before central stop to avoid warn logs at CCU.

# Version 0.37.5 (2022-03-18)

## What's Changed

- Add api for available interfaces
- Send event if interface is not available
- Don't block available interfaces

# Version 0.37.4 (2022-03-17)

## What's Changed

- Fix reload paramset
- Fix value converter

# Version 0.37.3 (2022-03-17)

## What's Changed

- Cleanup caching code

# Version 0.37.2 (2022-03-17)

## What's Changed

- Use homematic script to fetch initial data for CCU/HM

# Version 0.37.1 (2022-03-16)

## What's Changed

- Add semaphore(1) to improve cache usage (less api calls)

# Version 0.37.0 (2022-03-15)

## What's Changed

- Avoid unnecessary prefetches
- Fix JsonRPC Session handling
- Rename NamesCache to DeviceDetailsCache
- Move RoomCache to DeviceDetailsCache
- Move hm value converter to helpers
- Use JSON RPC for get_value, get_paramset, get_paramset_description
- Use default for binary_sensor

# Version 0.36.3 (2022-03-09)

## What's Changed

- Add hub property
- Add check if callback is already registered
- Use callback when hub is created

# Version 0.36.2 (2022-03-06)

## What's Changed

- Fix cover device mapping

# Version 0.36.1 (2022-03-06)

## What's Changed

- Small climate fix
- Make more devices custom_entities

# Version 0.36.0 (2022-02-24)

## What's Changed

- Remove HA constants
- Use enums own constants

# Version 0.35.3 (2022-02-23)

## What's Changed

- Move xmlrpc credentials to header

# Version 0.35.2 (2022-02-22)

## What's Changed

- Remove password from Exceptions

# Version 0.35.1 (2022-02-21)

## What's Changed

- Fix IpBlind
- Fix parameter visibility

# Version 0.35.0 (2022-02-19)

## What's Changed

- Fix usage of async_add_executor_job
- Improve local_ip identification

# Version 0.34.2 (2022-02-16)

## What's Changed

- Add is_locking/is_unlocking to lock

# Version 0.34.1 (2022-02-16)

## What's Changed

- Fix siren definition

# Version 0.34.0 (2022-02-15)

## What's Changed

- Use backported StrEnum
- Sort constants to identify HA constants
- Add new platform siren

# Version 0.33.0 (2022-02-14)

## What's Changed

- Make parameter availability more robust
- Add hvac_action to IP Thermostats
- Add hvac_action to some HM Thermostats

# Version 0.32.4 (2022-02-12)

## What's Changed

- add opening/closing to IPGarage

# Version 0.32.3 (2022-02-12)

## What's Changed

- Add state to HmIP-MOD-HO
- Use enum value for actions

# Version 0.32.2 (2022-02-11)

## What's Changed

- Fix HmIP-MOD-HO

# Version 0.32.1 (2022-02-11)

## What's Changed

- Update to pydevccu 0.1.3
- Priotize detection of devices for custom entities (e.g. HmIP-PCBS2)
- Add HmIPW-FIO6 as CE

# Version 0.32.0 (2022-02-10)

## What's Changed

- Move create_devices to central
- Move parameter visibility relevant data to own module

# Version 0.31.2 (2022-02-08)

## What's Changed

- Add HmIP-HDM2 to cover
- Fix unignore filename

# Version 0.31.1 (2022-02-07)

## What's Changed

- Improve naming
- Add multiplier to entity
- Substitute device_type of HB devices for usage in custom_entities

# Version 0.31.0 (2022-02-06)

## What's Changed

- Add missing return statement
- Add last_update to every value_cache_entry
- Rename init_entity_value to load_entity_value
- move (un)ignore methods to device
- Add support for unignore file
- Make PROCESS a binary_sensor
- Add DIRECTION & ACTIVITY_STATE to cover (is_opening, is_closing)

# Version 0.30.1 (2022-02-04)

## What's Changed

- Start hub earlier

# Version 0.30.0 (2022-02-03)

## What's Changed

- Add paramset to entity
- Add CHANNEL_OPERATION_MODE for HmIP(W)-DRBL4
- Fix DLD lock_state
- Add is_jammed to locks

# Version 0.29.2 (2022-02-02)

## What's Changed

- Add support for blacklisting a custom entity
- Add HmIP-STH to climate custom entities

# Version 0.29.1 (2022-02-02)

## What's Changed

- Check if interface callback is alive
- Add class for HomeamaticIP Blinds

# Version 0.29.0 (2022-02-01)

## What's Changed

- Make device availability dependent on the client
- Fire event about interface availability

# Version 0.28.7 (2022-01-30)

## What's Changed

- Add additional check to reconnect

# Version 0.28.6 (2022-01-30)

## What's Changed

- Optimize get_value caching

# Version 0.28.5 (2022-01-30)

## What's Changed

- Extend device cache to use get_value

# Version 0.28.4 (2022-01-30)

## What's Changed

- Limit read proxy workers to 1

# Version 0.28.3 (2022-01-29)

## What's Changed

- Rename RawDevicesCache to DeviceDescriptionCache

# Version 0.28.2 (2022-01-29)

## What's Changed

- Make names cache non persistent
- Bump pydevccu to 0.1.2

# Version 0.28.1 (2022-01-28)

## What's Changed

- Update hub.py to match GenericEntity
- Cleanup central API
- Use dedicated proxy for mass read operations, to avoid blocking of connection checker

# Version 0.28.0 (2022-01-27)

## What's Changed

- Try create client after init failure
- Reduce CCU calls

# Version 0.27.2 (2022-01-25)

## What's Changed

- Optimize data_load

# Version 0.27.1 (2022-01-25)

## What's Changed

- Fix naming paramset -> paramset_description pt2
- Optimize data_load by using get_paramset

# Version 0.27.0 (2022-01-25)

## What's Changed

- Fix naming paramset -> paramset_description
- Add get_value and get_paramset to central
- Add hmcli.py as command line script

# Version 0.26.0 (2022-01-22)

## What's Changed

- Make whitelist for parameter depend on the device_type/sub_type
- Add additional params for HM-SEC-Win (DIRECTION, ERROR, WORKING, STATUS)
- Add additional params for HM-SEC-Key (DIRECTION, ERROR)
- Assign secondary channels for HM dimmers
- Remove explicit wildcard in entity_definition

# Version 0.25.0 (2022-01-19)

## What's Changed

- Remove SpecialEvents
- Make UNREACH, STICKY_UNREACH, CONFIG_PENDING generic entities
- init UNREACH ... on init
- only poll sysvars when central is available

# Version 0.24.4 (2022-01-18)

## What's Changed

- Improve logging
- Generic schema for entities is name(str):channel(int), everything else is custom.

- Fix sysvar unique_id
- Slugify sysvar name
- Kill executor on shutdown
- Catch ValueError on conversion
- Add more data to logging

# Version 0.24.0-0.24.2 (2022-01-17)

## What's Changed

- Improve exception handling

# Version 0.23.3 (2022-01-16)

## What's Changed

- Update fix_rssi according to doc

# Version 0.23.1 (2022-01-16)

## What's Changed

- Add more logging to reconnect
- Add doc link for RSSI fix

# Version 0.23.0 (2022-01-16)

## What's Changed

- Make ["DRY", "RAIN"] sensor a binary_sensor
- Add converter to sensor value
  - HmIP-SCTH230 CONCENTRATION to int
  - Fix RSSI
- raise connection_checker interval to 60s
- Add sleep interval(120s) to wait with reconnect after successful connection check

# Version 0.22.2 (2022-01-15)

## What's Changed

- Rename hub extra_state_attributes to attributes

# Version 0.22.1 (2022-01-15)

## What's Changed

- Add VALVE_STATE for hm climate
- Add entity_type to attributes
- Accept LOWBAT only on channel 0

# Version 0.22.0 (2022-01-14)

## What's Changed

- Move client management to central
- Add rooms
- Move calls to create_devices and start_connection_checker

# Version 0.21.2 (2022-01-13)

## What's Changed

- Add ERROR_LOCK form HmIP-DLD
- Remove ALARM_EVENTS

# Version 0.21.1 (2022-01-13)

## What's Changed

- Fix event identification and generation

# Version 0.21.0 (2022-01-13)

## What's Changed

- Remove typecast for text, binary_sensor and number
- Don't exclude Servicemeldungen from sysvars
- Use Servicemeldungen sysvar for hub state
- Add test for HM-CC-VG-1 (HM-Heatinggroup)
- Remove additional typecasts for number

# Version 0.20.0 (2022-01-12)

## What's Changed

- Add converter to BaseParameterEntity/GenericEntity
- Fix number entities returning None when 0

# Version 0.19.0 (2022-01-11)

## What's Changed

- Mark secondary channels name with a V --> Vch

# Version 0.18.1 (2022-01-10)

## What's Changed

- Reduce some log_level
- Fix callback to notify un_reach

# Version 0.18.0 (2022-01-09)

## What's Changed

- Add config option to specify storage directory
- Move Exceptions to own module
- Add binary_sensor platform for SVs
- Add config check
- Add hub_entities_by_platform
- Remove option_enable_sensors_for_system_variables

# Version 0.17.1 (2022-01-09)

## What's Changed

- Fix naming for multi channel custom entities

# Version 0.17.0 (2022-01-09)

## What's Changed

- Refactor entity definition
  - improve naming
  - classify entities (primary, secondary, sensor, Generic, Event)
- remove option_enable_virtual_channels from central
- remove entity.create_in_ha. Replaced by HmEntityUsage

# Version 0.16.2 (2022-01-08)

## What's Changed

- Fix enum str in entity definition

# Version 0.16.1 (2022-01-08)

## What's Changed

- Use helper for device_name
- Add logging to show usage of unique_id in name
- Add HmIPW-WRC6 to custom entities
- Add HmIP-SCTH230 to custom entities
- Refactor entity definition
  - Remove unnecessary field names from additional entity definitions
  - Add additional entity definitions by device type

# Version 0.16.0 (2022-01-08)

## What's Changed

- Return unique_id if name is not in cache
- Remove no longer needed press_virtual_remote_key

# Version 0.15.2 (2022-01-07)

## What's Changed

- Add devices to CustomEntity
  - HmIP-WGC
  - HmIP-WHS
- Update to pydevccu 0.1.0

# Version 0.15.1 (2022-01-07)

## What's Changed

- Identify virtual remote by device type
- Fix Device Exporter / format output

# Version 0.15.0 (2022-01-07)

## What's Changed

- Use actions instead of buttons for virtual remotes

# Version 0.14.1 (2022-01-06)

## What's Changed

- Remove SVs from EXCLUDED_FROM_SENSOR

# Version 0.14.0 (2022-01-06)

## What's Changed

- Switch some HM-LC-Bl1 to cover
- Use decorators on central methods
- Make decorators async aware
- Don't exclude DutyCycle, needed for old rf-modules
- Don't exclude Watchdog from SV sensor
- Ignore mypy error

# Version 0.13.3 (2022-01-05)

## What's Changed

- HM cover fix: check level for None
- Only device_address is required for HA callback
- Fix: max_temp issue for hm thermostats
- Fix: hm const are str instead of int

# Version 0.13.2 (2022-01-04)

## What's Changed

- Fix cover state
- Move delete_devices from RPCFunctions to central
- Move new_devices from RPCFunctions to central
- Add method to delete a single device to central

# Version 0.13.1 (2022-01-04)

## What's Changed

- Use generic climate profiles list

# Version 0.13.0 (2022-01-04)

## What's Changed

- Remove dedicated json tls option
- Fix unique_id for heating_groups
- Use domain name as base folder name
- Remove domain const from aiohomematic

# Version 0.12.0 (2022-01-03)

## What's Changed

- Split number to integer and float

# Version 0.11.2 (2022-01-02)

## What's Changed

- Precise entity definitions

# Version 0.11.1 (2022-01-02)

## What's Changed

- Improve detection of multi channel devices

# Version 0.11.0 (2022-01-02)

## What's Changed

- Add positional arguments
- Add missing channel no
- Set ED_PHY_CHANNEL min_length to 1
- Add platform zu hub entities
- Use entities in properties
- Add transition to dimmer
- Rename entity.state to entity.value
- Remove channel no, if channel is the only_primary_channel

# Version 0.10.0 (2021-12-31)

## What's Changed

- Make reset_motion, reset_presence a button
- add check to device_name / Fixes

# Version 0.9.1 (2021-12-30)

## What's Changed

- Load and clear caches async
- Extend naming strategy to use device name if channel name is not customized

# Version 0.9.0 (2021-12-30)

## What's Changed

- Add new helper for event_name
- Add channel to click_event payload

# Version 0.8.0 (2021-12-29)

## What's Changed

- Use base class for file cache
- Rename primary_client to client
- Add export for device definition

# Version 0.7.0 (2021-12-28)

## What's Changed

- Remove deleted entities from device and central collections
- use datetime for last_events
- Climate IP: use calendar for duration away

# Version 0.6.1 (2021-12-27)

## What's Changed

- Display profiles only when hvac_mode auto is enabled
- Fix binary sensor state update for hmip 2-state sensors

# Version 0.6.0 (2021-12-27)

## What's Changed

- Add climate methods for away mode
- Fix HVAC_MODE_OFF for climate

# Version 0.5.1 (2021-12-26)

## What's Changed

- Fix hm_light turn_off

# Version 0.5.0 (2021-12-25)

## What's Changed

- Fix Select Entity
- Remove internal device temperature (ACTUAL_TEMPERATURE CH0)
- Support Cool Mode for IPThermostats
- Display if AWAY_MODE is set on thermostat
- Separate device_address and channel_address

# Version 0.4.0 (2021-12-24)

## What's Changed

- Use datetime for last_updated (time_initialized)
- Fix example
- Add ACTUAL_TEMPERATURE as separate entity by @towo
- Add HEATING_COOLING to IPThermostat and Group
- Add (_)HUMIDITY and (_)TEMPERATURE as separate entities for Bidcos thermostats
- use ACTIVE_PROFILE in climate presets

# Version 0.3.1 (2021-12-23)

## What's Changed

- Make HmIP-BSM a switch (only dimable devices should be lights)

# Version 0.3.0 (2021-12-23)

## What's Changed

- Cleanup API, device/entity
- Add ACTIVE_PROFILE to IPThermostat

# Version 0.2.0 (2021-12-22)

## What's Changed

- Cleanup API, reduce visibility
- Add setValue to client

# Version 0.1.2 (2021-12-21)

## What's Changed

- Rotate device identifier

# Version 0.1.1 (2021-12-21)

## What's Changed

- Remove unnecessary async
- Removed unused helper
- Add interface_id to identifiers in device_info

# Version 0.1.0 (2021-12-20)

## What's Changed

- Bump # Version to 0.1.0
- Remove interface_id from get_entity_name and get_custom_entity_name
- Add initial test
- Add coverage config

# Version 0.0.22 (2021-12-16)

## What's Changed

- Resolve names without interface
- Fix device.entities for virtual remotes
- Remove unused const
- Cache model and primary_client

# Version 0.0.21 (2021-12-15)

## What's Changed

- Fix number set_state
- Update ignore list
- Fix select entity

# Version 0.0.20 (2021-12-14)

## What's Changed

- Move caches to classes

# Version 0.0.19 (2021-12-12)

## What's Changed

- Add helper for address
- Fixes for Hub init

# Version 0.0.18 (2021-12-11)

## What's Changed

- Add type hints based on HA coding guidelines
- Rename device_description to entity_definition
- Send alarm event on value change
- Rename impulse to special events
- reduce event_callbacks

# Version 0.0.17 (2021-12-05)

## What's Changed

- Remove variables that are covered by other sensors (CCU only)
- Remove dummy from service message (HmIP-RF always sends 0001D3C98DD4B6:3 unreach)
- Rename Bidcos thermostats to SimpleRfThermostat and RfThermostat
- Use more Enums (like HA does): HmPlatform, HmEventType
- Use assignment expressions
- Add more type hints (fix most mypy errors)

# Version 0.0.16 (2021-12-02)

## What's Changed

- Don't use default entities for climate groups (already included in device)

# Version 0.0.15 (2021-12-01)

## What's Changed

- Fix: remove wildcard for HmIP-STHD
- Add unit to hub entities

# Version 0.0.14 (2021-11-30)

## What's Changed

- Add KeyMatic
- Add HmIP-MOD-OC8
- Add HmIP-PCBS, HmIP-PCBS2, HmIP-PCBS-BAT, HmIP-USBSM
- Remove xmlrpc calls related to ccu system variables (not supported by api)
- Update hub sensor excludes

# Version 0.0.13 (2021-11-29)

## What's Changed

- Add HmIP-MOD-HO, HmIP-MOD-TM
- Add sub_type to device/entity
- Add PRESET_NONE to climate
- Add level und state as additional entities for climate

# Version 0.0.12 (2021-11-27)

## What's Changed

- Add more type converter
- Move get_tls_context to helper
- Update requirements
- Cleanup constants
- Use flags from parameter_data
- Add wildcard start to exclude parameters that start with word
- Fix channel assignment for dimmers
- Fix entity name: add channel only if a parameter name exists is in multiple channels of the device.

# Version 0.0.11 (2021-11-26)

## What's Changed

- Fix: cover open/close default values to float
- Fix: add missing async/await
- make get_primary_client public

# Version 0.0.10 (2021-11-26)

## What's Changed

- Fix TLS handling

# Version 0.0.9 (2021-11-25)

## What's Changed

- Don't start connection checker for pydevccu
- Use a dummy hub for pydevccu
- Convert min, max, default values (fix for cover)

# Version 0.0.8 (2021-11-25)

## What's Changed

- Add button platform. This allows to use the virtual remotes of a ccu in automations.
- Cleanup entity inheritance.

# Version 0.0.7 (2021-11-23)

## What's Changed

- Switch to a non-permanent session for jsonrpc calls
  The json capabilities of a ccu are limited (3 parallel session!?!).
  So we no longer us a persisted session. (like pyhomematic)
- Enable write-only params as HMAction(solves a problem with climate writing CONTROL_MODE)

# Version 0.0.6 (2021-11-22)

## What's Changed

- Rename server to central_unit (after the extraction of the XMLRPC-Server server has not been a server anymore).
- Rename json_rpc to json_rpc_client
- Move json_rpc from client to central_unit to remove number of active sessions
- Add hub with option to enable own system variables as sensors

# Version 0.0.5 (2021-11-20)

## What's Changed

- Add method for virtual remote
- Update entity availability based on connection status
- Fix action_event for ha device trigger

# Version 0.0.4 (2021-11-18)

## What's Changed

- Use one XMLRPC-Server for all backends

# Version 0.0.3 (2021-11-16)

## What's Changed

- Reduce back to parameters with events
- Rewrite climate-entity creation
- Refactor to Async
- Remove entity_id and replace by unique_id
- Reorg Client/Server/Caches
- Use One Server per backend (CCU/Homegear) with multiple clients/interfaces
- Define device_description for custom_entities
- Create custom_entities for climate, cover, light, lock and switch
- Maintain ignored parameters
- Add collection with wildcard parameters to ignore
- Enable click, impulse and alarm events
- Add connection checker

# Version 0.0.2 (2021-04-20)

## What's Changed

- Use input_select for ENUM actors (Issue #8)
- Added `DEVICE_IN_BOOTLOADER` and `INSTALL_TEST` to ignored parameters
- Create `switch` for type `ACTION` for parameters with only write-flag
- Create `number` for type `FLOAT` for parameters with only write-flag
- Add exceptions to abort startup under certain conditions
- Refactoring, introduce `Device` class
- Allow to fetch single paramset on demand
- Renew JSON-RPC sessions instead of logging in and out all the time

# Version 0.0.1 (2021-04-08)

## What's Changed

- Initial testing release
