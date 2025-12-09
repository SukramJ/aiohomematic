# Architecture overview

This document describes the high‑level architecture of aiohomematic, focusing on the main components and how they interact at runtime. It is intended for contributors and integrators who want to understand data flow, responsibilities, and the boundaries between modules.

## Top‑level components

- Central (aiohomematic/central): Orchestrates the whole system. Manages client lifecycles, creates devices and data points, runs a lightweight scheduler, exposes the local XML‑RPC callback server for events, and provides a query facade over the runtime model and caches. The central is created via CentralConfig and realized by CentralUnit.
- Client (aiohomematic/client): Implements the protocol adapters to a Homematic backend (CCU, Homegear). Clients abstract XML‑RPC and JSON‑RPC calls, maintain connection health, and translate high‑level operations (get/set value, put/get paramset, list devices, system variables, programs) into backend requests. Concrete types: ClientCCU, ClientJsonCCU, ClientHomegear. A client belongs to one Interface (BidCos‑RF, HmIP, etc.).
- Model (aiohomematic/model): Turns device and channel descriptions into runtime objects: Device, Channel, DataPoints and Events. The model layer defines generic data point types (switch, number, sensor, select, …), hub objects for programs and system variables, custom composites for device‑specific behavior, and calculated data points for derived metrics. The entry point create_data_points_and_events wires everything based on paramset descriptions and visibility rules.
- Caches (aiohomematic/caches): Provide persistence and fast lookup for device metadata and runtime values.
  - persistent: DeviceDescriptionCache and ParamsetDescriptionCache store descriptions on disk between runs.
  - dynamic: CentralDataCache, DeviceDetailsCache, CommandCache, PingPongCache hold in‑memory runtime state and connection health.
  - visibility: ParameterVisibilityCache applies rules to decide which paramsets/parameters are relevant and which are hidden/internal.
- Support (aiohomematic/support.py and helpers): Cross‑cutting utilities: URI/header construction for XML‑RPC, input validation, hashing, network helpers, conversion helpers, and small abstractions used across central and client. aiohomematic/async_support.py provides helpers for periodic tasks.

## Dependency Injection Architecture

aiohomematic uses a **protocol-based dependency injection** pattern to reduce coupling and improve testability. The architecture follows a three-tier strategy:

### Tier 1: Full Dependency Injection (Infrastructure Layer)

Components receive only protocol interfaces via constructor injection, with **zero references** to CentralUnit:

- **CacheCoordinator**: Receives 8 protocol interfaces (CentralInfo, DeviceProvider, ClientProvider, etc.)
- **DeviceRegistry**: Receives CentralInfo + ClientProvider
- **ParameterVisibilityCache**: Receives ConfigProvider
- **EventCoordinator**: Receives ClientProvider + TaskScheduler
- **DeviceCoordinator**: Receives 3 protocol interfaces
- **BackgroundScheduler**: Receives 7 protocol interfaces

**Benefits**: Complete decoupling from CentralUnit, protocol-based mocking for tests, clear dependency contracts.

### Tier 2: Full Protocol-Based Dependency Injection (Coordinator Layer)

Components use protocol interfaces exclusively with zero CentralUnit references:

- **ClientCoordinator**: Uses ClientFactory protocol for client creation, plus 4 protocol interfaces (CentralInfo, ConfigProvider, CoordinatorProvider, SystemInfoProvider)
- **HubCoordinator**: Constructs Hub with protocol interfaces only (CentralInfo, ChannelLookup, ClientProvider, ConfigProvider, EventBusProvider, EventPublisher, ParameterVisibilityProvider, ParamsetDescriptionProvider, PrimaryClientProvider, TaskScheduler)
- **Hub**: Uses 11+ protocol interfaces for all operations, no CentralUnit reference

**Note**: As of 2025-11-23, Tier 2 coordinators no longer use hybrid DI patterns. The ClientFactory protocol was introduced to enable client creation without requiring the full CentralUnit, and Hub construction was refactored to use only protocol interfaces.

### Tier 3: Full Dependency Injection (Model Layer)

Model classes now use full dependency injection with protocol interfaces:

- **Device**: Receives 16 protocol interfaces (DeviceDetailsProvider, DeviceDescriptionProvider, ParamsetDescriptionProvider, ParameterVisibilityProvider, ClientProvider, ConfigProvider, CentralInfo, EventBusProvider, TaskScheduler, FileOperations, DeviceDataRefresher, DataCacheProvider, ChannelLookup, EventSubscriptionManager) via constructor injection
- **Channel**: Accesses protocol interfaces through its parent Device instance (self.\_device.\_xxx_provider)
- **CallbackDataPoint**: Receives 5 protocol interfaces (CentralInfo, EventBusProvider, TaskScheduler, ParamsetDescriptionProvider, ParameterVisibilityProvider)
- **BaseDataPoint**: Extracts protocol interfaces from channel.device and passes them to CallbackDataPoint
- **BaseParameterDataPoint**: Uses device protocol interfaces for initialization

**Benefits**: Complete decoupling from CentralUnit throughout the entire model layer, improved testability, clear dependency contracts at all levels.

### Protocol Interfaces

Key protocol interfaces defined in `aiohomematic/interfaces/`:

**Central Protocols** (`interfaces/central.py`):

- **CentralInfo**: System identification (name, model, version)
- **ConfigProvider**: Configuration access (config property)
- **DeviceProvider**: Device registry access
- **DataPointProvider**: Data point lookup
- **EventBusProvider**: Event system access (event_bus property)
- **EventPublisher**: Event emission (publish_backend_system_event, publish_homematic_event)
- **DataCacheProvider**: Data cache access (get_data method)
- **ChannelLookup**: Channel lookup by address
- **EventSubscriptionManager**: Event subscription management
- **DeviceDataRefresher**: Device data refresh operations
- **FileOperations**: File I/O operations
- **SystemInfoProvider**: System information access
- **HubDataFetcher**: Hub data fetching operations
- **HubDataPointManager**: Hub data point management (programs and sysvars)

**Client Protocols** (`interfaces/client.py`):

- **ClientFactory**: Client instance creation (create_client_instance method)
- **ClientProvider**: Client lookup by interface_id
- **ClientProtocol**: Client interface for RPC operations
- **PrimaryClientProvider**: Primary client access

**Operations Protocols** (`interfaces/operations.py`):

- **TaskScheduler**: Background task scheduling (create_task method)
- **DeviceDetailsProvider**: Device metadata (address_id, rooms, interface, name)
- **DeviceDescriptionProvider**: Device descriptions lookup
- **ParamsetDescriptionProvider**: Paramset descriptions and multi-channel checks
- **ParameterVisibilityProvider**: Parameter visibility rules

**Model Protocols** (`interfaces/model.py`):

- **DeviceProtocol**: Device interface
- **ChannelProtocol**: Channel interface
- **HubProtocol**: Hub-level operations (inbox*dp, update_dp, fetch*\*\_data methods)
- **WeekProfileProtocol**: Week profile operations (schedule, get_schedule, set_schedule)
- Various DataPoint protocols (GenericDataPointProtocol, CustomDataPointProtocol, etc.)

**Coordinator Protocols** (`interfaces/coordinators.py`):

- **CoordinatorProvider**: Access to coordinator instances

These protocols use `@runtime_checkable` and structural subtyping, allowing CentralUnit to satisfy all interfaces without explicit inheritance.

## Responsibilities and boundaries

- Central vs Client
  - Central owns system composition: it creates and starts/stops clients per configured interface, starts the XML‑RPC callback server, and maintains the runtime model and caches.
  - Central implements all protocol interfaces and injects them into coordinators during construction.
  - Client owns protocol details: it knows how to talk to the backend via XML‑RPC or JSON‑RPC, how to fetch lists and paramsets, and how to write values. Central should not embed protocol specifics; instead it calls client methods.
- Model vs Central/Client
  - Model is pure domain representation plus transformation from paramset descriptions to concrete data points/events. It must not perform network I/O. It consumes metadata provided by Central/Client and exposes typed operations on DataPoints (which then delegate to the client for I/O through the device/channel back‑reference).
  - Model layer (Device, Channel, DataPoint) uses full dependency injection with protocol interfaces, achieving complete decoupling from CentralUnit.
- Coordinators
  - All coordinators use full dependency injection with protocol interfaces.
  - Infrastructure coordinators (CacheCoordinator, DeviceCoordinator, DeviceRegistry, EventCoordinator) receive only protocol interfaces.
  - Factory coordinators (ClientCoordinator, HubCoordinator) use ClientFactory and other protocol interfaces for all operations including object creation.
- Caches
  - Persistent caches are loaded/saved by Central during startup/shutdown and used by Clients to avoid redundant metadata fetches.
  - Dynamic caches are updated by Clients and Central when values change, and consulted to answer quick queries or de‑duplicate work.
  - All cache classes use dependency injection to receive only required interfaces.
- Support
  - Shared, stateless helpers. No long‑lived state; safe to import anywhere.

## Key runtime interactions

### Startup/connection

1. CentralConfig is created with central name, host, credentials, interface configs, and options.
2. CentralConfig.create_central() builds a CentralUnit. CentralUnit.\_create_clients() creates one Client per enabled Interface.
3. CentralUnit.start():
   - Validates configuration and, if enabled, starts the local XML‑RPC callback server (xml_rpc_server) so the backend can push events.
   - Loads persistent caches (device/paramset descriptions) and initializes clients.
   - Initializes the Hub (programs, system variables) and starts a scheduler thread for periodic refresh and health checks.

### Device discovery and model creation

1. Client.list_devices() fetches device descriptions from the backend (or uses cached copies if valid).
2. For new or changed devices, CentralUnit.\_add_new_devices() instantiates Device and Channel objects and attaches paramset descriptions.
3. For each channel, create_data_points_and_events() (model package) iterates over paramset descriptions, applies ParameterVisibilityCache rules, creates Events where appropriate, and instantiates DataPoints via the generic/custom/calculated factories.
4. Central indexes DataPoints and Events for quick lookup and subscription management.

## State read and write

- Reads
  - Central or a consumer requests a value: Client.get_value(channel_address, paramset_key, parameter) performs the appropriate RPC call (XML‑RPC or JSON‑RPC) and returns a converted value (model.support.convert_value is used where necessary). Results may be stored in dynamic caches.
- Writes
  - A consumer calls DataPoint.set_value(...), which delegates to the owning Device/Channel/Client. Client.\_set_value/\_exec_set_value sends the RPC write. Optionally the system waits for an event confirming the new value; otherwise the value may be written into a temporary cache and later reconciled.

## Event handling and data point updates

1. The backend pushes events to the local XML‑RPC callback server (Central's xml_rpc_server). Each event carries interface_id, channel_address, parameter, and value.
2. CentralUnit.data_point_event(interface_id, channel_address, parameter, value) is invoked via decorators wiring. Central looks up the target DataPoint by channel+parameter.
3. The DataPoint's internal state is updated; events are published to subscribers via EventBus. Central updates last event timestamps and connection health.
4. If events indicate new devices or configuration changes, Central may trigger scans to fetch updated descriptions and update the model accordingly.

## JSON‑RPC vs XML‑RPC data flow

- XML‑RPC
  - Used primarily for event callbacks and many CCU operations. Client uses XmlRpcProxy to issue method calls to the backend. The local xml_rpc_server exposes endpoints for the backend’s event callbacks.
- JSON‑RPC
  - Optional, when the backend provides a JSON API. ClientCCU/ClientJsonCCU routes some operations through JsonRpcAioHttpClient. Choice of backend per interface is encapsulated by the concrete Client type.

## Caching strategy

- Persistent caches (on disk)
  - DeviceDescriptionCache and ParamsetDescriptionCache reduce cold‑start time and load on the backend. Central decides when to refresh and when to trust cached data (based on age and configuration).
- Dynamic caches (in memory)
  - CentralDataCache holds recent values and metadata to accelerate lookups and avoid redundant conversions.
  - CommandCache and PingPongCache support write‑ack workflows and connection health checks.
  - DeviceDetailsCache stores supplementary per‑device data fetched on demand.
- Visibility cache
  - ParameterVisibilityCache determines which parameters are exposed as DataPoints/events, influenced by user un‑ignore lists and marker rules.

## Concurrency model

- Central runs a background scheduler thread (\_Scheduler) that periodically:
  - Checks connection health and reconnection needs.
  - Refreshes hub data (programs/system variables) and firmware update information.
  - Optionally polls devices for values where push is unavailable.
- I/O operations in Clients are async‑aware or threaded via proxies where needed; long‑running operations are awaited and protected by timeouts (see const.TIMEOUT) and command queues.

## Extension points

- **New device profiles**: Add custom DataPoints under `model/custom/` and register them via `DeviceProfileRegistry.register()`. See `docs/extension_points.md` for detailed instructions.
- **Calculated sensors**: Implement in `model/calculated/` and add to `_CALCULATED_DATA_POINTS` in `model/calculated/__init__.py`.
- **Backends/interfaces**: Implement a new Client subclass and corresponding protocol proxy to add support for another backend or transport.

## Glossary (selected types)

- CentralUnit: The orchestrator instance created from CentralConfig.
- Client: Protocol adapter for a single interface towards CCU/Homegear.
- Device/Channel: Domain model reflecting backend device topology.
- DataPoint: Addressable parameter on a channel, with read/write and event capabilities.
- Event: Push‑style notification mapped to selected parameters (e.g., button clicks, device errors).
- Hub: Program and System Variable data points provided by the backend itself.

## Further reading

- [Data flow](../docs/data_flow.md) details (XML-RPC/JSON-RPC, events, updates)
- [Sequence diagrams](../docs/sequence_diagrams.md) (connect, discovery, propagation)

## Architectural Decisions and Rationale

This section documents key architectural decisions and their rationale for future reviews.

### Caching Strategies

#### ParameterVisibilityCache: Unbounded Memoization

**Decision**: The `ParameterVisibilityCache` uses unbounded memoization (via `@functools.lru_cache` or similar) without explicit size limits.

**Rationale**: Unbounded memoization is intentional and appropriate here because:

1. **Natural bounds from domain**: The cache is inherently bounded by the finite number of devices and parameters in a Homematic installation. A typical installation has:

   - 10-200 devices
   - Each device has 1-20 channels
   - Each channel has 5-50 parameters
   - Total unique (interface_id, channel_address, paramset_key, parameter) tuples: typically < 50,000

2. **Static data**: Parameter visibility rules don't change during runtime. Once computed, the visibility of a parameter remains constant until the system restarts.

3. **Memory efficiency**: Each cache entry is small (key tuple + boolean result). Even with 50,000 entries, memory usage is negligible (< 5 MB).

4. **Performance critical path**: Visibility checks are called frequently during device/data point creation and UI rendering. Caching eliminates repeated rule evaluation.

**Conclusion**: Adding LRU eviction or TTL expiration would add complexity without benefit. The cache naturally stays bounded by the physical device count in the installation.

### Protocol Injection: Explicit over Composite

**Decision**: Use explicit protocol injection per component rather than grouping protocols into composite interfaces for internal components.

**Analysis**: Protocol usage across components was analyzed:

| Component         | Protocol Count |
| ----------------- | -------------- |
| Device            | 16 protocols   |
| Hub               | 12 protocols   |
| DeviceCoordinator | 17 protocols   |
| HubCoordinator    | 10 protocols   |
| CacheCoordinator  | 7 protocols    |

**Common protocol groups identified**:

1. **Core** (all components): `central_info`, `config_provider`, `task_scheduler`
2. **Events** (Device, Hub, coordinators): `event_bus_provider`, `event_publisher`
3. **Visibility** (Device, Hub, coordinators): `parameter_visibility_provider`, `paramset_description_provider`

**Existing composite protocols**:

- `ClientDependencies` - Groups ~20 methods for client external API
- `BaseHandler` - Abstracts common handler dependencies (6 protocols)

**Rationale**: No additional composite protocols are needed because:

1. **Explicitness**: Each component documents exactly what it needs via its constructor signature. This makes dependencies visible without consulting external type definitions.

2. **Testability**: Explicit protocols make it easy to mock specific dependencies. Tests can provide minimal implementations for only the protocols a component actually uses.

3. **Decoupling**: CentralUnit already acts as a de-facto composite by implementing all protocols. Components receive the specific slices they need without coupling to the full interface.

4. **Structural typing**: Python's protocol system provides flexibility. Components depend on behavior (methods/properties) rather than nominal types, so there's no need to define intermediate composite types.

**Trade-offs considered**: Creating formal composite protocols for internal components would:

- Add maintenance overhead (another layer of types to keep synchronized)
- Hide actual dependencies (consumers would need to inspect the composite to understand requirements)
- Not significantly improve testability (explicit protocols already enable focused mocking)

**Conclusion**: `ClientDependencies` makes sense for the external client API contract where a stable public interface is valuable. Internal coordinators and model classes benefit from explicit dependency injection, which prioritizes clarity and testability over brevity.

## Notes

- This is a high‑level overview. For detailed API and exact behavior, consult the module docstrings and tests under tests/ which cover most features and edge cases.
