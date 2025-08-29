Sequence diagrams: Connect, device discovery, state change propagation

This document provides Mermaid sequence diagrams for key flows in aiohomematic: initial connect, device discovery, and state change propagation.

1. Connect (startup, clients, XML-RPC callback registration)

```mermaid
sequenceDiagram
  actor App
  participant Cfg as CentralConfig
  participant C as CentralUnit
  participant XRS as XmlRpcServer (local)
  participant CCU as Backend (CCU/Homegear)
  participant CX as ClientCCU (XML-RPC)
  participant CJ as ClientJsonCCU (JSON-RPC)
  App->>Cfg: create(name, host, creds, interfaces)
  Cfg->>Cfg: validate
  Cfg->>C: create_central()
  C->>C: _create_clients()
  alt JSON port configured
    C->>CJ: init(json_host, json_port)
    CJ-->>C: ready
  end
  C->>CX: init(xml_host, xml_port)
  CX-->>C: ready
  C->>XRS: start()
  XRS-->>C: listening
  C->>CX: register_callback(interface_id, XRS.url)
  CX->>CCU: init(interface_id, callback_url)
  CCU-->>CX: ok
  CX-->>C: registered
  C-->>App: connected
```

Notes

- Central starts the local XML-RPC callback server before registering with the backend so the CCU can immediately deliver events.
- When JSON-RPC is enabled, the JSON client is initialized as well; authentication occurs on first use.

2. Device discovery (metadata fetch, model creation)

```mermaid
sequenceDiagram
  participant C as CentralUnit
  participant CX as ClientCCU (XML-RPC)
  participant CJ as ClientJsonCCU (JSON-RPC)
  participant PDC as ParamsetDescriptionCache (persistent)
  participant DDC as DeviceDescriptionCache (persistent)
  participant M as Model (Device/Channel/DataPoints)
  Note over C: Startup or metadata refresh
  C->>DDC: load()
  C->>PDC: load()
  alt cache valid
    DDC-->>C: device_descriptions
    PDC-->>C: paramset_descriptions
  else fetch from backend
    opt via JSON-RPC when available
      C->>CJ: list_devices()
      CJ-->>C: device_descriptions
    end
    C->>CX: get_paramset_descriptions(addresses)
    CX-->>C: paramset_descriptions
    C->>DDC: save(...)
    C->>PDC: save(...)
  end
  C->>M: create_devices_and_channels(descriptions)
  M-->>C: Device/Channel objects
  C->>M: create_data_points_and_events(paramset_descriptions)
  M-->>C: DataPoints and Events
  C->>C: index DataPoints/Events
  C-->>App: discovery complete
```

Notes

- Central prefers cached metadata when fresh; otherwise it fetches from the backend using JSON-RPC where available and XML-RPC for paramset details.
- Model creation is pure: no network I/O, just transformations.

3. State change propagation (event -> caches -> subscribers)

```mermaid
sequenceDiagram
  participant CCU as Backend (CCU/Homegear)
  participant XRS as XmlRpcServer (local)
  participant C as CentralUnit
  participant Cache as Dynamic Caches
  participant DP as DataPoint
  participant App as Subscriber/Consumer
  CCU-->>XRS: event(interface_id, channel, parameter, value)
  XRS->>C: data_point_event(...)
  C->>DP: lookup(channel, parameter)
  C->>C: convert/validate value
  C->>Cache: update(DataPointKey, value, ts)
  C->>DP: set_internal(value)
  C-->>App: notify subscribers (callbacks)
  Note over C,App: Pending writes may be reconciled
```

See also

- [for high-level components and responsibilities](docs/architecture.md)
- [for textual data flow and additional sequence diagrams (reads/writes)](docs/data_flow.md)
