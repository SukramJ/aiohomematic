# Sequence diagrams: Connect, device discovery, state change propagation

This document provides Mermaid sequence diagrams for key flows in aiohomematic: initial connect, device discovery, state change propagation, client state machine, and EventBus architecture.

## 1. Connect (startup, clients, XML-RPC callback registration)

```mermaid
sequenceDiagram
  actor App
  participant Cfg as CentralConfig
  participant C as CentralUnit
  participant CC as ClientCoordinator
  participant CaC as CacheCoordinator
  participant HC as HubCoordinator
  participant XRS as XmlRpcServer (local)
  participant CCU as Backend (CCU/Homegear)
  participant CX as ClientCCU
  participant SM as ClientStateMachine
  participant H as Handlers

  App->>Cfg: create(name, host, creds, interfaces)
  Cfg->>Cfg: validate
  Cfg->>C: create_central()

  Note over C: CentralUnit.start()
  C->>C: detect callback IP
  C->>XRS: start()
  XRS-->>C: listening

  C->>CC: start_clients()
  CC->>CC: _create_clients()

  loop For each interface_config
    CC->>CX: create_client_instance()
    CX->>SM: new(CREATED)
    SM-->>CX: state machine ready
    CX->>CX: fetch system info
    CX->>SM: transition_to(INITIALIZING)
    CX->>H: _init_handlers()
    Note over H: DeviceOps, Firmware,<br/>LinkMgmt, Metadata,<br/>Programs, Sysvars, Backup
    H-->>CX: handlers ready
    CX->>SM: transition_to(INITIALIZED)
    CX-->>CC: client ready
  end

  CC->>CaC: load_all()
  CaC-->>CC: caches loaded

  CC->>CC: _init_clients()
  loop For each client
    CC->>CX: initialize_proxy()
    CX->>SM: transition_to(CONNECTING)
    CX->>CCU: init(interface_id, callback_url)
    CCU-->>CX: ok
    CX->>SM: transition_to(CONNECTED)
    CX-->>CC: proxy initialized
  end

  CC->>HC: init_hub()
  HC-->>CC: hub ready

  CC-->>C: clients started
  C-->>App: connected
```

### Notes

- Central starts the local XML-RPC callback server before registering with the backend so the CCU can immediately deliver events.
- ClientCoordinator orchestrates client lifecycle: creation, cache loading, initialization, and hub setup.
- Each client uses a ClientStateMachine to enforce valid state transitions (CREATED → INITIALIZING → INITIALIZED → CONNECTING → CONNECTED).
- Handlers are initialized during client creation, providing specialized operations (device ops, firmware, metadata, etc.).

---

## 2. Device discovery (metadata fetch, model creation)

```mermaid
sequenceDiagram
  participant C as CentralUnit
  participant CC as ClientCoordinator
  participant DC as DeviceCoordinator
  participant CaC as CacheCoordinator
  participant DDC as DeviceDescriptionCache
  participant PDC as ParamsetDescriptionCache
  participant CX as ClientCCU
  participant DR as DeviceRegistry
  participant D as Device
  participant DP as DataPoint

  Note over C: Startup or metadata refresh
  C->>CC: start_clients()
  CC->>CaC: load_all()
  CaC->>DDC: load()
  CaC->>PDC: load()

  alt cache valid
    DDC-->>CaC: device_descriptions
    PDC-->>CaC: paramset_descriptions
  else fetch from backend
    CaC->>CX: list_devices()
    CX-->>CaC: device_descriptions
    CaC->>CX: get_paramset_descriptions(addresses)
    CX-->>CaC: paramset_descriptions
    CaC->>DDC: save(...)
    CaC->>PDC: save(...)
  end
  CaC-->>CC: caches loaded

  Note over C: Device creation
  C->>DC: check_for_new_device_addresses()
  DC-->>C: new_device_addresses

  C->>DC: create_devices(new_device_addresses)

  loop For each device_address
    DC->>D: new Device(15 protocol interfaces)
    D-->>DC: device instance

    DC->>DC: create_data_points_and_events()
    Note over DC: Generic data points<br/>(sensor, switch, etc.)
    DC->>DC: create_custom_data_points()
    Note over DC: Custom data points<br/>(climate, cover, light, etc.)

    DC->>DR: register(device)
    DR-->>DC: registered

    DC->>D: finalize_init()
    D-->>DC: initialized
  end

  DC->>DC: publish_backend_system_event(DEVICES_CREATED)
  DC-->>C: devices created
  C-->>App: discovery complete
```

### Notes

- CacheCoordinator manages persistent caches (device descriptions, paramset descriptions) with disk persistence.
- DeviceCoordinator handles device creation with full protocol-based DI (15 protocol interfaces per device).
- Model creation is pure: no network I/O, just transformations from cached descriptions.
- Generic and custom data points are created based on paramset descriptions and device profiles.

---

## 3. State change propagation (event → EventBus → subscribers)

```mermaid
sequenceDiagram
  participant CCU as Backend (CCU/Homegear)
  participant XRS as XmlRpcServer (local)
  participant RPC as RPCFunctions
  participant EC as EventCoordinator
  participant EB as EventBus
  participant DP as DataPoint
  participant App as Subscriber/Consumer

  CCU-->>XRS: event(interface_id, channel, parameter, value)
  XRS->>RPC: event(...)
  RPC->>RPC: looper.create_task()

  Note over EC: Async task scheduled
  RPC->>EC: data_point_event(interface_id, channel, parameter, value)

  EC->>EC: validate interface_id
  EC->>EC: set_last_event_seen_for_interface()

  alt PONG response
    EC->>EC: handle_received_pong()
    EC-->>RPC: done
  else Normal parameter event
    EC->>EC: create DataPointKey(dpk)

    EC->>EB: publish(DataPointUpdatedEvent)

    Note over EB: Dual-key handler lookup
    EB->>EB: lookup handlers by event.key (dpk)
    EB->>EB: fallback to handlers with key=None

    par Concurrent handler invocation
      EB->>DP: event_handler(event)
      Note over DP: Filter by dpk match
      DP->>DP: event(value, received_at)
      DP->>DP: update internal state
      DP->>DP: notify_update()

      EB->>App: custom_handler(event)
      Note over App: External subscriber
    end

    EB-->>EC: handlers completed
    EC-->>RPC: done
  end

  Note over DP,App: Pending writes may be reconciled
```

### Notes

- RPCFunctions schedules async tasks via looper to avoid blocking the XML-RPC callback thread.
- EventCoordinator creates typed events (DataPointUpdatedEvent) with DataPointKey for filtering.
- EventBus uses dual-key lookup: specific key (dpk) first, then wildcard (None) fallback.
- Handlers run concurrently via asyncio.gather with error isolation (one failure doesn't affect others).
- Both async and sync handlers are supported transparently.

---

## 4. Client state machine (lifecycle states and transitions)

```mermaid
stateDiagram-v2
  [*] --> CREATED: new ClientStateMachine()

  CREATED --> INITIALIZING: init_client()

  INITIALIZING --> INITIALIZED: success
  INITIALIZING --> FAILED: error

  INITIALIZED --> CONNECTING: initialize_proxy()

  CONNECTING --> CONNECTED: success
  CONNECTING --> FAILED: error

  CONNECTED --> DISCONNECTED: connection lost
  CONNECTED --> RECONNECTING: auto reconnect
  CONNECTED --> STOPPING: stop()

  DISCONNECTED --> CONNECTING: manual reconnect
  DISCONNECTED --> RECONNECTING: auto reconnect
  DISCONNECTED --> STOPPING: stop()
  DISCONNECTED --> DISCONNECTED: idempotent deinitialize

  RECONNECTING --> CONNECTED: success
  RECONNECTING --> DISCONNECTED: abandoned
  RECONNECTING --> FAILED: permanent failure
  RECONNECTING --> CONNECTING: retry

  FAILED --> INITIALIZING: retry init
  FAILED --> CONNECTING: retry connect

  STOPPING --> STOPPED: cleanup complete

  STOPPED --> [*]
```

### State descriptions

| State        | Description                                               |
| ------------ | --------------------------------------------------------- |
| CREATED      | Initial state after client instantiation                  |
| INITIALIZING | Loading metadata, creating proxies, initializing handlers |
| INITIALIZED  | Ready to establish connection to backend                  |
| CONNECTING   | Registering callback with backend via XML-RPC init()      |
| CONNECTED    | Fully operational, receiving events                       |
| DISCONNECTED | Connection lost or intentionally closed                   |
| RECONNECTING | Automatic reconnection attempt in progress                |
| STOPPING     | Graceful shutdown in progress                             |
| STOPPED      | Terminal state, no further transitions                    |
| FAILED       | Error state, allows retry via re-initialization           |

### Notes

- ClientStateMachine enforces valid transitions and raises InvalidStateTransitionError for invalid ones.
- State changes are logged for debugging and can trigger optional callbacks.
- The DISCONNECTED state allows idempotent deinitialize calls (self-transition).
- FAILED state provides recovery paths back to INITIALIZING or CONNECTING.

---

## 5. EventBus architecture (subscription and publishing)

```mermaid
sequenceDiagram
  participant Sub as Subscriber
  participant EB as EventBus
  participant H1 as Handler 1 (async)
  participant H2 as Handler 2 (sync)
  participant Pub as Publisher

  Note over Sub,EB: Subscription phase
  Sub->>EB: subscribe(DataPointUpdatedEvent, dpk, handler1)
  EB->>EB: _subscriptions[event_type][event_key].append(handler)
  EB-->>Sub: unsubscribe_callback

  Sub->>EB: subscribe(DataPointUpdatedEvent, None, handler2)
  Note over EB: None key = wildcard subscriber
  EB-->>Sub: unsubscribe_callback

  Note over Pub,EB: Publishing phase
  Pub->>EB: publish(DataPointUpdatedEvent(dpk, value))

  EB->>EB: lookup handlers by event.key
  alt specific key found
    EB->>EB: use handlers for dpk
  else fallback to wildcard
    EB->>EB: use handlers for None key
  end

  EB->>EB: _event_count[event_type] += 1

  par asyncio.gather (error isolated)
    EB->>H1: _safe_call_handler(handler1, event)
    H1->>H1: await handler1(event)
    H1-->>EB: done

    EB->>H2: _safe_call_handler(handler2, event)
    H2->>H2: handler2(event)
    Note over H2: Sync handler, no await needed
    H2-->>EB: done
  end

  EB-->>Pub: all handlers completed

  Note over Sub,EB: Cleanup phase
  Sub->>Sub: unsubscribe_callback()
  Note over EB: Handler removed from list
```

### Event types

| Event                         | Key             | Description                           |
| ----------------------------- | --------------- | ------------------------------------- |
| DataPointUpdatedEvent         | DataPointKey    | Backend data point value update       |
| BackendParameterEvent         | DataPointKey    | Raw parameter event from RPC          |
| BackendSystemEventData        | None            | System events (DEVICES_CREATED, etc.) |
| HomematicEvent                | None            | Homematic events (KEYPRESS, etc.)     |
| SysvarUpdatedEvent            | state_path      | System variable update                |
| InterfaceEvent                | interface_id    | Interface state changes               |
| DeviceUpdatedEvent            | device_address  | Device state update                   |
| FirmwareUpdatedEvent          | device_address  | Firmware info update                  |
| LinkPeerChangedEvent          | channel_address | Channel link changes                  |
| DataPointUpdatedCallbackEvent | unique_id       | External integration notification     |
| DeviceRemovedEvent            | unique_id       | Device/data point removal             |

### Notes

- EventBus is async-first but supports both sync and async handlers transparently.
- Dual-key lookup: specific event.key first, then None (wildcard) fallback.
- Error isolation via return_exceptions=True in asyncio.gather.
- Memory management: clear_subscriptions_by_key() for cleanup when devices are removed.
- Event statistics tracked for debugging via get_event_stats().

---

## 6. Handler architecture (specialized client operations)

```mermaid
classDiagram
  class ClientCCU {
    -state_machine: ClientStateMachine
    -device_ops: DeviceOperationsHandler
    -firmware: FirmwareHandler
    -link_mgmt: LinkManagementHandler
    -metadata: MetadataHandler
    -programs: ProgramHandler
    -sysvars: SystemVariableHandler
    -backup: BackupHandler
    +init_client()
    +initialize_proxy()
  }

  class BaseHandler {
    #_central: ClientDependencies
    #_interface: Interface
    #_interface_id: str
    #_json_rpc_client
    #_proxy: BaseRpcProxy
    #_proxy_read: BaseRpcProxy
  }

  class DeviceOperationsHandler {
    +fetch_all_device_data()
    +get_value()
    +set_value()
    +get_paramset()
    +put_paramset()
    +fetch_device_descriptions()
    +fetch_paramset_descriptions()
  }

  class FirmwareHandler {
    +get_firmware_update_state()
    +install_device_firmware()
    +install_system_firmware()
  }

  class LinkManagementHandler {
    +get_link_peers()
    +add_link()
    +remove_link()
  }

  class MetadataHandler {
    +rename_device()
    +set_device_room()
    +set_device_function()
    +set_install_mode()
    +get_inbox()
    +accept_device()
  }

  class ProgramHandler {
    +get_programs()
    +execute_program()
    +set_program_active()
  }

  class SystemVariableHandler {
    +get_system_variables()
    +set_system_variable()
    +delete_system_variable()
  }

  class BackupHandler {
    +create_backup()
    +download_backup()
  }

  ClientCCU --> DeviceOperationsHandler
  ClientCCU --> FirmwareHandler
  ClientCCU --> LinkManagementHandler
  ClientCCU --> MetadataHandler
  ClientCCU --> ProgramHandler
  ClientCCU --> SystemVariableHandler
  ClientCCU --> BackupHandler

  BaseHandler <|-- DeviceOperationsHandler
  BaseHandler <|-- FirmwareHandler
  BaseHandler <|-- LinkManagementHandler
  BaseHandler <|-- MetadataHandler
  BaseHandler <|-- ProgramHandler
  BaseHandler <|-- SystemVariableHandler
  BaseHandler <|-- BackupHandler
```

### Notes

- ClientCCU delegates operations to specialized handler classes for separation of concerns.
- All handlers extend BaseHandler which provides common dependencies via ClientDependencies protocol.
- Handlers receive protocol interfaces (not direct CentralUnit references) for decoupled architecture.
- Each handler focuses on a specific domain: device ops, firmware, linking, metadata, programs, sysvars, backup.

---

## 7. Client reconnection flow (connection recovery)

```mermaid
sequenceDiagram
  participant Sched as BackgroundScheduler
  participant CC as ClientCoordination
  participant CX as ClientCCU
  participant SM as ClientStateMachine
  participant Proxy as BaseRpcProxy
  participant CCU as Backend (CCU/Homegear)
  participant CS as CentralConnectionState
  participant EB as EventBus

  Note over Sched: Periodic check_connection (120s default)
  Sched->>CC: all_clients_active?

  alt All clients inactive
    CC-->>Sched: false
    Sched->>CC: restart_clients()
    Note over CC: Full client restart
  else Check individual clients
    CC-->>Sched: true

    loop For each interface_id
      Sched->>CC: get_client(interface_id)
      CC-->>Sched: client

      Sched->>CX: available?
      Sched->>CX: is_connected()
      Sched->>CX: is_callback_alive()

      alt Connection unhealthy
        Note over Sched: available=false OR not connected OR callback dead

        Sched->>CX: reconnect()
        CX->>SM: transition_to(RECONNECTING)

        CX->>CX: deinitialize_proxy()
        CX->>Proxy: stop()
        Proxy->>CCU: de-register callback
        CCU-->>Proxy: ok
        Proxy-->>CX: stopped

        CX->>SM: transition_to(CONNECTING)

        CX->>CX: reinitialize_proxy()
        CX->>Proxy: init(callback_url)
        Proxy->>CCU: register callback
        CCU-->>Proxy: ok
        Proxy-->>CX: initialized

        CX->>SM: transition_to(CONNECTED)
        CX->>CS: remove_issue(interface_id)
        CS->>EB: publish(InterfaceEvent, connected=true)

        CX-->>Sched: reconnected

        Sched->>CC: load_and_refresh_data_point_data(interface)
        Note over CC: Refresh device data after reconnect
      else Connection healthy
        Note over Sched: Skip reconnect
      end
    end
  end
```

### Connection health checks

| Check            | Method                          | Description                           |
| ---------------- | ------------------------------- | ------------------------------------- |
| Client available | `client.available`              | Client not in error state             |
| Proxy connected  | `client.is_connected()`         | Proxy init successful                 |
| Callback alive   | `client.is_callback_alive()`    | Events received within threshold      |
| Ping/Pong        | `check_connection_availability` | Backend responds to ping (if enabled) |

### State transitions during reconnect

```
CONNECTED → RECONNECTING → CONNECTING → CONNECTED
     │                          │
     └──────────────────────────┴───→ FAILED (on permanent error)
```

### Notes

- BackgroundScheduler runs `_check_connection` every 120 seconds (configurable via `RECONNECT_WAIT`).
- Reconnection is attempted for each unhealthy client independently.
- After successful reconnect, device data is refreshed via `load_and_refresh_data_point_data`.
- CentralConnectionState tracks issues and notifies external consumers (Home Assistant) via callbacks.

---

## 8. Cache invalidation strategy

```mermaid
sequenceDiagram
  participant App as Application
  participant C as CentralUnit
  participant CaC as CacheCoordinator
  participant DDC as DeviceDescriptionCache
  participant PDC as ParamsetDescriptionCache
  participant CDC as CentralDataCache
  participant DDtC as DeviceDetailsCache
  participant CX as ClientCCU
  participant CCU as Backend

  Note over C: Startup - Cache Loading
  C->>CaC: load_all()

  par Load persistent caches
    CaC->>DDC: load()
    DDC->>DDC: check file exists & age
    alt Cache valid (< MAX_CACHE_AGE)
      DDC-->>CaC: loaded from disk
    else Cache stale or missing
      DDC->>CX: list_devices()
      CX->>CCU: listDevices()
      CCU-->>CX: device_descriptions
      CX-->>DDC: device_descriptions
      DDC->>DDC: save to disk
      DDC-->>CaC: loaded from backend
    end

    CaC->>PDC: load()
    PDC->>PDC: check file exists & age
    alt Cache valid
      PDC-->>CaC: loaded from disk
    else Cache stale or missing
      PDC->>CX: get_paramset_descriptions()
      CX->>CCU: getParamsetDescription()
      CCU-->>CX: paramset_descriptions
      CX-->>PDC: paramset_descriptions
      PDC->>PDC: save to disk
      PDC-->>CaC: loaded from backend
    end
  end

  CaC-->>C: caches loaded

  Note over C: Runtime - Dynamic Cache Updates

  rect rgb(240, 248, 255)
    Note over CDC: CentralDataCache (in-memory)
    CX->>CDC: add_data(interface, all_device_data)
    Note over CDC: Stores parameter values per interface
    CDC->>CDC: update _refreshed_at timestamp
  end

  rect rgb(255, 248, 240)
    Note over DDtC: DeviceDetailsCache (in-memory)
    CX->>DDtC: add_name(address, name)
    CX->>DDtC: add_interface(address, interface)
    Note over DDtC: Cached until explicit clear() or refresh
  end

  Note over C: Invalidation Triggers

  alt Device added/removed (NEW_DEVICES/DELETE_DEVICES event)
    C->>DDC: clear()
    C->>PDC: clear()
    C->>CX: fetch fresh descriptions
    CX->>CCU: listDevices()
    CCU-->>CX: updated descriptions
    CX-->>C: devices
    C->>DDC: save()
    C->>PDC: save()
  end

  alt Connection lost/reconnect
    C->>CDC: clear(interface)
    Note over CDC: Clear stale values for interface
    C->>CX: fetch_all_device_data()
    CX->>CCU: getAllValues()
    CCU-->>CX: values
    CX-->>CDC: add_data()
  end

  alt Periodic refresh (periodic_refresh_interval)
    C->>CDC: load(interface)
    Note over CDC: Refresh if age > MAX_CACHE_AGE/3
    CDC->>CX: fetch_all_device_data()
    CX->>CCU: getAllValues()
    CCU-->>CX: fresh values
    CX-->>CDC: update values
  end

  alt Manual clear_all
    App->>C: clear_all_caches()
    C->>DDC: clear()
    C->>PDC: clear()
    C->>CDC: clear()
    C->>DDtC: clear()
  end
```

### Cache types and invalidation rules

| Cache                    | Type       | Storage | Invalidation Trigger                         | TTL             |
| ------------------------ | ---------- | ------- | -------------------------------------------- | --------------- |
| DeviceDescriptionCache   | Persistent | Disk    | NEW_DEVICES, DELETE_DEVICES, manual clear    | MAX_CACHE_AGE   |
| ParamsetDescriptionCache | Persistent | Disk    | Device structure change, manual clear        | MAX_CACHE_AGE   |
| CentralDataCache         | Dynamic    | Memory  | Reconnect, periodic refresh, interface clear | MAX_CACHE_AGE/3 |
| DeviceDetailsCache       | Dynamic    | Memory  | Explicit refresh, manual clear               | None (refresh)  |
| CommandCache             | Dynamic    | Memory  | TTL expiry per entry, clear on write confirm | Per-entry TTL   |
| PingPongCache            | Dynamic    | Memory  | Pong received, TTL expiry                    | Per-entry TTL   |
| ParameterVisibilityCache | Computed   | Memory  | Never (static rules)                         | Unbounded       |

### Notes

- **Persistent caches** survive restarts and reduce cold-start time.
- **Dynamic caches** are cleared on connection issues to ensure data freshness.
- **MAX_CACHE_AGE** default is typically 24 hours for persistent caches.
- **ParameterVisibilityCache** is intentionally unbounded (see ADR 0005).
- Backend events (NEW_DEVICES, DELETE_DEVICES) trigger cache invalidation automatically.

---

## 9. Week profile update flow

```mermaid
sequenceDiagram
  participant App as Application/Consumer
  participant DP as CustomDpClimate
  participant WP as WeekProfile
  participant D as Device
  participant CX as ClientCCU
  participant Proxy as BaseRpcProxy
  participant CCU as Backend

  Note over App: Get current schedule

  App->>DP: get_schedule(force_load=false)
  DP->>WP: get_schedule(force_load=false)

  alt Schedule cached and not forced
    WP->>WP: return _schedule_cache
    WP-->>DP: cached schedule_data
  else Force load or no cache
    WP->>WP: reload_and_cache_schedule()
    WP->>WP: _validate_and_get_schedule_channel_address()

    WP->>CX: get_paramset(channel_address, MASTER)
    CX->>Proxy: getParamset(address, "MASTER")
    Proxy->>CCU: getParamset(...)
    CCU-->>Proxy: raw_paramset (all MASTER params)
    Proxy-->>CX: raw_paramset
    CX-->>WP: raw_paramset

    WP->>WP: _convert_schedule_entries(raw_paramset)
    Note over WP: Extract XX_WP_* entries only

    WP->>WP: convert_raw_to_dict_schedule()
    Note over WP: Convert to structured dict<br/>e.g., {1: {WEEKDAY: [...], LEVEL: 0.5}}

    WP->>WP: _filter_schedule_entries()
    WP->>WP: _schedule_cache = schedule_data
    WP-->>DP: schedule_data
  end

  DP-->>App: schedule_data

  Note over App: Modify and set new schedule

  App->>App: modify schedule_data
  App->>DP: set_schedule(schedule_data)
  DP->>WP: set_schedule(schedule_data)

  WP->>WP: _validate_and_get_schedule_channel_address()
  WP->>WP: convert_dict_to_raw_schedule(schedule_data)
  Note over WP: Convert back to raw format<br/>e.g., {"01_WP_WEEKDAY": 127, ...}

  WP->>CX: put_paramset(channel_address, MASTER, raw_schedule)
  CX->>Proxy: putParamset(address, "MASTER", values)
  Proxy->>CCU: putParamset(...)
  CCU-->>Proxy: ok
  Proxy-->>CX: ok
  CX-->>WP: ok

  WP->>WP: reload_and_cache_schedule(force=true)
  Note over WP: Verify write by reloading

  WP->>CX: get_paramset(channel_address, MASTER)
  CX->>CCU: getParamset(...)
  CCU-->>CX: updated raw_paramset
  CX-->>WP: raw_paramset
  WP->>WP: update _schedule_cache
  WP-->>DP: ok

  DP-->>App: schedule updated
```

### Schedule data structure

```python
# Raw CCU format (MASTER paramset)
raw_schedule = {
    "01_WP_WEEKDAY": 127,        # Bitmask: all days
    "01_WP_LEVEL": 0.5,          # Target level (0.0-1.0)
    "01_WP_FIXED_HOUR": 6,       # Start hour
    "01_WP_FIXED_MINUTE": 0,     # Start minute
    "01_WP_ASTRO_TYPE": 0,       # Astro type enum
    "01_WP_CONDITION": 0,        # Condition enum
    # ... more entries for groups 01-10
}

# Structured Python format
schedule_data = {
    1: {
        ScheduleField.WEEKDAY: [Weekday.MONDAY, Weekday.TUESDAY, ...],
        ScheduleField.LEVEL: 0.5,
        ScheduleField.FIXED_HOUR: 6,
        ScheduleField.FIXED_MINUTE: 0,
        ScheduleField.ASTRO_TYPE: AstroType.NONE,
        ScheduleField.CONDITION: ScheduleCondition.NONE,
    },
    2: { ... },
    # ... up to 10 schedule groups
}
```

### Week profile types

| Type               | Device Types             | Schedule Fields                   |
| ------------------ | ------------------------ | --------------------------------- |
| DefaultWeekProfile | Switches, lights, covers | WEEKDAY, LEVEL, TIME, ASTRO, etc. |
| ClimateWeekProfile | Thermostats              | WEEKDAY, TEMPERATURE, TIME, etc.  |

### Notes

- Week profiles are stored in the MASTER paramset of the schedule channel.
- Schedules are cached after loading to avoid repeated backend calls.
- Conversion between raw CCU format and structured Python dicts is bidirectional.
- Setting a schedule triggers a reload to verify the write was successful.
- Schedule entries are identified by pattern `XX_WP_FIELDNAME` where XX is group number (01-10).

---

## See also

- [Architecture](../docs/architecture.md) for high-level components and responsibilities
- [Data flow](../docs/data_flow.md) for textual data flow and additional sequence diagrams (reads/writes)
- [ADR 0005](../docs/adr/0005-unbounded-parameter-visibility-cache.md) for cache strategy rationale
