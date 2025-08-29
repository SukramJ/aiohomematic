Architecture overview

This document describes the high‑level architecture of aiohomematic, focusing on the main components and how they interact at runtime. It is intended for contributors and integrators who want to understand data flow, responsibilities, and the boundaries between modules.

Top‑level components

- Central (aiohomematic/central): Orchestrates the whole system. Manages client lifecycles, creates devices and data points, runs a lightweight scheduler, exposes the local XML‑RPC callback server for events, and provides a query facade over the runtime model and caches. The central is created via CentralConfig and realized by CentralUnit.
- Client (aiohomematic/client): Implements the protocol adapters to a HomeMatic backend (CCU, CCU JSON, Homegear). Clients abstract XML‑RPC and JSON‑RPC calls, maintain connection health, and translate high‑level operations (get/set value, put/get paramset, list devices, system variables, programs) into backend requests. Concrete types: ClientCCU, ClientJsonCCU, ClientHomegear. A client belongs to one Interface (BidCos‑RF, HmIP, etc.).
- Model (aiohomematic/model): Turns device and channel descriptions into runtime objects: Device, Channel, DataPoints and Events. The model layer defines generic data point types (switch, number, sensor, select, …), hub objects for programs and system variables, custom composites for device‑specific behavior, and calculated data points for derived metrics. The entry point create_data_points_and_events wires everything based on paramset descriptions and visibility rules.
- Caches (aiohomematic/caches): Provide persistence and fast lookup for device metadata and runtime values.
  - persistent: DeviceDescriptionCache and ParamsetDescriptionCache store descriptions on disk between runs.
  - dynamic: CentralDataCache, DeviceDetailsCache, CommandCache, PingPongCache hold in‑memory runtime state and connection health.
  - visibility: ParameterVisibilityCache applies rules to decide which paramsets/parameters are relevant and which are hidden/internal.
- Support (aiohomematic/support.py and helpers): Cross‑cutting utilities: URI/header construction for XML‑RPC, input validation, hashing, network helpers, conversion helpers, and small abstractions used across central and client. aiohomematic/async_support.py provides helpers for periodic tasks.

Responsibilities and boundaries

- Central vs Client
  - Central owns system composition: it creates and starts/stops clients per configured interface, starts the XML‑RPC callback server, and maintains the runtime model and caches.
  - Client owns protocol details: it knows how to talk to the backend via XML‑RPC or JSON‑RPC, how to fetch lists and paramsets, and how to write values. Central should not embed protocol specifics; instead it calls client methods.
- Model vs Central/Client
  - Model is pure domain representation plus transformation from paramset descriptions to concrete data points/events. It must not perform network I/O. It consumes metadata provided by Central/Client and exposes typed operations on DataPoints (which then delegate to the client for I/O through the device/channel back‑reference).
- Caches
  - Persistent caches are loaded/saved by Central during startup/shutdown and used by Clients to avoid redundant metadata fetches.
  - Dynamic caches are updated by Clients and Central when values change, and consulted to answer quick queries or de‑duplicate work.
- Support
  - Shared, stateless helpers. No long‑lived state; safe to import anywhere.

Key runtime interactions

Startup/connection

1. CentralConfig is created with central name, host, credentials, interface configs, and options.
2. CentralConfig.create_central() builds a CentralUnit. CentralUnit.\_create_clients() creates one Client per enabled Interface; JSON‑RPC client may be created if json_port is configured.
3. CentralUnit.start():
   - Validates configuration and, if enabled, starts the local XML‑RPC callback server (xml_rpc_server) so the backend can push events.
   - Loads persistent caches (device/paramset descriptions) and initializes clients.
   - Initializes the Hub (programs, system variables) and starts a scheduler thread for periodic refresh and health checks.

Device discovery and model creation

1. Client.list_devices() fetches device descriptions from the backend (or uses cached copies if valid).
2. For new or changed devices, CentralUnit.\_add_new_devices() instantiates Device and Channel objects and attaches paramset descriptions.
3. For each channel, create_data_points_and_events() (model package) iterates over paramset descriptions, applies ParameterVisibilityCache rules, creates Events where appropriate, and instantiates DataPoints via the generic/custom/calculated factories.
4. Central indexes DataPoints and Events for quick lookup and subscription management.

State read and write

- Reads
  - Central or a consumer requests a value: Client.get_value(channel_address, paramset_key, parameter) performs the appropriate RPC call (XML‑RPC or JSON‑RPC) and returns a converted value (model.support.convert_value is used where necessary). Results may be stored in dynamic caches.
- Writes
  - A consumer calls DataPoint.set_value(...), which delegates to the owning Device/Channel/Client. Client.\_set_value/\_exec_set_value sends the RPC write. Optionally the system waits for a callback confirming the new value; otherwise the value may be written into a temporary cache and later reconciled.

Event handling and data point updates

1. The backend pushes events to the local XML‑RPC callback server (Central’s xml_rpc_server). Each event carries interface_id, channel_address, parameter, and value.
2. CentralUnit.data_point_event(interface_id, channel_address, parameter, value) is invoked via decorators wiring. Central looks up the target DataPoint by channel+parameter.
3. The DataPoint’s internal state is updated; any registered callbacks/subscribers are notified. Central updates last event timestamps and connection health.
4. If events indicate new devices or configuration changes, Central may trigger scans to fetch updated descriptions and update the model accordingly.

JSON‑RPC vs XML‑RPC data flow

- XML‑RPC
  - Used primarily for event callbacks and many CCU operations. Client uses XmlRpcProxy to issue method calls to the backend. The local xml_rpc_server exposes endpoints for the backend’s event callbacks.
- JSON‑RPC
  - Optional, when the backend provides a JSON API. ClientJsonCCU routes get/set and list operations through JsonRpcAioHttpClient. Choice of backend per interface is encapsulated by the concrete Client type.

Caching strategy

- Persistent caches (on disk)
  - DeviceDescriptionCache and ParamsetDescriptionCache reduce cold‑start time and load on the backend. Central decides when to refresh and when to trust cached data (based on age and configuration).
- Dynamic caches (in memory)
  - CentralDataCache holds recent values and metadata to accelerate lookups and avoid redundant conversions.
  - CommandCache and PingPongCache support write‑ack workflows and connection health checks.
  - DeviceDetailsCache stores supplementary per‑device data fetched on demand.
- Visibility cache
  - ParameterVisibilityCache determines which parameters are exposed as DataPoints/events, influenced by user un‑ignore lists and marker rules.

Concurrency model

- Central runs a background scheduler thread (\_Scheduler) that periodically:
  - Checks connection health and reconnection needs.
  - Refreshes hub data (programs/system variables) and firmware update information.
  - Optionally polls devices for values where push is unavailable.
- I/O operations in Clients are async‑aware or threaded via proxies where needed; long‑running operations are awaited and protected by timeouts (see const.TIMEOUT) and command queues.

Extension points

- New device profiles: Add custom DataPoints under model/custom and register them via create_custom_data_points.
- Calculated sensors: Implement in model/calculated and wire up create_calculated_data_points for derived metrics.
- Backends/interfaces: Implement a new Client subclass and corresponding protocol proxy to add support for another backend or transport.

Glossary (selected types)

- CentralUnit: The orchestrator instance created from CentralConfig.
- Client: Protocol adapter for a single interface towards CCU/Homegear.
- Device/Channel: Domain model reflecting backend device topology.
- DataPoint: Addressable parameter on a channel, with read/write and event capabilities.
- Event: Push‑style notification mapped to selected parameters (e.g., button clicks, device errors).
- Hub: Program and System Variable data points provided by the backend itself.

Further reading

- [Data flow details (XML-RPC/JSON-RPC, events, updates)](../docs/data_flow.md)
- [Sequence diagrams (connect, discovery, propagation)](../docs/sequence_diagrams.md)

Notes

- This is a high‑level overview. For detailed API and exact behavior, consult the module docstrings and tests under tests/ which cover most features and edge cases.
