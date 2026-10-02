# Session playback test infrastructure

This document describes how aiohomematic records and replays RPC sessions for
deterministic, offline testing.

## Overview

The session playback system captures real XML-RPC and JSON-RPC interactions with
a Homematic backend (CCU or Homegear) into ZIP archives. Tests replay these
sessions through mock proxies, enabling fast, reproducible tests without a live
backend.

```
Recording:  CCU <--RPC--> SessionRecorder --> ZIP archive
Playback:   Test --> MockProxy --> SessionPlayer --> ZIP archive
```

## Session ZIP file format

Each ZIP archive contains a single JSON file with the same base name:

```
full_session_randomized_ccu.zip
  +-- full_session_randomized_ccu.json
```

### JSON structure

The JSON file is a nested dictionary organized by RPC type, method, frozen
parameters, and timestamp:

```json
{
  "xmlrpc": {
    "system.listMethods": {
      "()": {
        "1761022910": ["event", "listDevices", "newDevices", ...]
      }
    },
    "listDevices": {
      "()": {
        "1761022910": [{"ADDRESS": "VCU001", ...}, ...]
      }
    },
    "getParamsetDescription": {
      "('VCU001:1', 'VALUES')": {
        "1761022910": {"STATE": {"TYPE": "BOOL", ...}}
      }
    }
  },
  "jsonrpc": {
    "Interface.listInterfaces": {
      "{}": {
        "1761022910": [{"name": "BidCos-RF", ...}]
      }
    }
  }
}
```

**Hierarchy:**

| Level | Key             | Description                                |
| ----- | --------------- | ------------------------------------------ |
| 1     | `rpc_type`      | `"xmlrpc"` or `"jsonrpc"`                  |
| 2     | `method`        | RPC method name (e.g., `"listDevices"`)    |
| 3     | `frozen_params` | String representation of frozen parameters |
| 4     | `timestamp`     | Unix timestamp (seconds) of the recording  |

The value at the deepest level is the raw RPC response.

## How sessions are recorded

### Activating the recorder

The `SessionRecorder` in `aiohomematic/store/persistent/session.py` records the
system init when `OptionalSettings.SR_RECORD_SYSTEM_INIT` is set in `CentralConfig`
(for `DEFAULT_SESSION_RECORDER_START_FOR_SECONDS` after `start()`, then it saves).
`OptionalSettings.SR_DISABLE_RANDOMIZE_OUTPUT` keeps the device addresses as recorded:

```python
config = CentralConfig(
    ...,
    optional_settings=(OptionalSettings.SR_RECORD_SYSTEM_INIT,),
)
```

Or programmatically:

```python
await recorder.activate(on_time=30, auto_save=True, randomize_output=True)
```

- `on_time`: Auto-deactivate after N seconds (0 = manual deactivation)
- `auto_save`: Save automatically on deactivation
- `randomize_output`: Shuffle the device addresses among each other for privacy

### What gets recorded

Every RPC call passes through the recorder:

1. **XML-RPC calls**: `add_xml_rpc_session(method, params, response)`
2. **JSON-RPC calls**: `add_json_rpc_session(method, params, response)`

Parameters are cleaned before storage:

- ReGa script content is stripped to only `# name:` and `# param:` lines
  (removes timestamps and variable content for deterministic lookup)

### Saving sessions

```python
await recorder.save(randomize_output=True, use_ts_in_file_name=True)
```

Sessions are saved to `{storage_dir}/session/` as ZIP files.
When `randomize_output=True`, the device addresses are shuffled among each other
for privacy, so an address no longer belongs to the same device model.

## How sessions are played back

### SessionPlayer

The `SessionPlayer` class in `aiohomematic_test_support/mock.py` loads and
queries recorded sessions.

```python
player = SessionPlayer(file_id="full_session_randomized_ccu.zip")
await player.load(file_path=path_to_zip, file_id="ccu")
```

Multiple session files can be loaded. The primary file takes precedence;
secondary files serve as fallback.

### Lookup algorithm

When a mock proxy needs a response:

1. **Clean parameters**: Remove non-deterministic content (script bodies, etc.)
2. **Freeze parameters**: Convert to a hashable string representation
3. **Navigate the store**: `store[file_id][rpc_type][method][frozen_params]`
4. **Select latest timestamp**: `max(timestamps)` returns the most recent response
5. **Fallback**: If not found in primary file, try secondary files

### Parameter freezing

Parameters must be converted to hashable string keys for dictionary lookup.
The `freeze_params()` function in `aiohomematic/store/serialization.py` handles
this:

| Python type                  | Frozen representation                     |
| ---------------------------- | ----------------------------------------- |
| `dict`                       | Recursively freeze values, sort keys      |
| `list` / `tuple`             | Tuple of frozen elements                  |
| `set` / `frozenset`          | `("__set__", sorted_elements)`            |
| `datetime`                   | `("__datetime__", "2024-01-01T00:00:00")` |
| `str`, `int`, `bool`, `None` | Pass through unchanged                    |

The `unfreeze_params()` function reverses this transformation using
`ast.literal_eval()` for safe parsing.

**Example:**

```python
freeze_params(params=("VCU001:1", "VALUES"))
# Result: "('VCU001:1', 'VALUES')"

freeze_params(params={"interface": "BidCos-RF"})
# Result: "{'interface': 'BidCos-RF'}"
```

## Mock proxies

### XML-RPC mock

`get_xml_rpc_proxy()` returns an `_AioXmlRpcProxyFromSession` that intercepts
method calls:

```python
proxy = get_xml_rpc_proxy(player=player, interface_config=config)
methods = await proxy.system.listMethods()  # Looked up from session
devices = await proxy.listDevices()          # Looked up from session
```

Special method overrides:

| Method        | Behavior                                   |
| ------------- | ------------------------------------------ |
| `listDevices` | Filters by device translation/ignore lists |
| `setValue`    | Triggers event on central (if connected)   |
| `putParamset` | Iterates values, triggers events           |
| `ping`        | Returns empty string                       |

### JSON-RPC mock

`get_client_session()` returns a `_MockClientSession` that intercepts POST
requests:

```python
session = get_client_session(player=player)
async with session.post(url, json=payload) as resp:
    data = await resp.json()  # Looked up from session
```

Special method overrides:

| Method                  | Behavior                         |
| ----------------------- | -------------------------------- |
| `Interface.setValue`    | Triggers event coordinator       |
| `Interface.putParamset` | Triggers events per value        |
| `SysVar.getAll`         | Returns test constants           |
| `Program.getAll`        | Returns test constants           |
| `Session.logout`        | Returns success                  |
| `ReGa.runScript`        | Smart routing by script keywords |

## Session data files

Located in `aiohomematic_test_support/data/`:

| File                              | Size   | Source                   |
| --------------------------------- | ------ | ------------------------ |
| `full_session_randomized_ccu.zip` | 716 KB | Real CCU3                |
| `full_session_godevccu.zip`       | 824 KB | godevccu (homegear mode) |
| `device_translation.json`         | 13 KB  | Address-to-model mapping |

### Device translation

The `device_translation.json` maps randomized device addresses to model
identifiers, enabling tests to reference specific device types by address.

## Test factory usage

The `FactoryWithClient` class provides a fluent API for test setup:

```python
factory = FactoryWithClient(
    player=session_player,
    do_mock_client=True,
    ignore_devices_on_create=["VCU0000099"],
)
central = await factory.get_default_central(start=True)

# central is now ready for testing with mocked RPC calls
device = central.device_coordinator.get_device(address="VCU0000001")
```

### Device filtering

Both mock proxies support:

- **`ignore_devices_on_create`**: Skip listed device addresses
- **`address_device_translation`**: Only include translated addresses
  (useful for targeted tests with specific device models)

## Creating new session files

### godevccu session

`full_session_godevccu.zip` is recorded by a script against the godevccu binary
(version pinned in `.godevccu-version`):

```bash
script/install_godevccu.sh
PYTHONPATH=. python script/record_godevccu_session.py
```

The script runs a central with `start_direct=True` (so the central calls
`listDevices` itself, which the playback needs) and the optional settings
`SR_RECORD_SYSTEM_INIT` and `SR_DISABLE_RANDOMIZE_OUTPUT`. Do not randomize this
recording: randomizing shuffles the device addresses, and the playback tests
reference devices by address.

### Session from a live backend

1. Configure `CentralConfig` with `OptionalSettings.SR_RECORD_SYSTEM_INIT`
   (records from `start()` for `DEFAULT_SESSION_RECORDER_START_FOR_SECONDS` and
   saves automatically)
2. Start the central unit and let it discover devices
3. Interact with devices to capture additional RPC calls
4. Or save explicitly:
   ```python
   await central.cache_coordinator.recorder.save(
       randomize_output=True,
       use_ts_in_file_name=True,
   )
   ```
5. Copy the ZIP from `{storage_dir}/session/` to `aiohomematic_test_support/data/`
