# hmcli -- Homematic Command-Line Tool

`hmcli` is a command-line tool for querying and controlling Homematic hubs directly via XML-RPC. It is bundled with the aiohomematic package and intended for developers who need to inspect devices, read parameter values, or debug Homematic setups without running a full Home Assistant instance.

## When to use hmcli

- **Device discovery**: List all devices, channels, and parameters registered on a CCU or Homegear instance.
- **Debugging**: Read live parameter values (e.g., `STATE`, `TEMPERATURE`, `RSSI_DEVICE`) to verify device behavior.
- **Quick writes**: Set parameter values for testing without going through the Home Assistant UI.
- **Paramset inspection**: View the full paramset description (types, ranges, operations) for any channel.
- **Scripting**: Pipe JSON output into `jq` or other tools for automated checks.

## Installation

`hmcli` is installed automatically as a console script when you install aiohomematic:

```bash
pip install aiohomematic
```

After installation, the `hmcli` command is available on your PATH. You can verify it with:

```bash
hmcli --version
```

If you are working from a development checkout:

```bash
pip install -e .
hmcli --version
```

## Connection options

Every command (except `--generate-completion`) requires at minimum `--host` and `--port`:

| Option       | Short | Description                                |
| ------------ | ----- | ------------------------------------------ |
| `--host`     | `-H`  | Hostname or IP address of the CCU/Homegear |
| `--port`     | `-p`  | XML-RPC port (see table below)             |
| `--path`     |       | URL path, used for heating groups          |
| `--username` | `-U`  | Username for authentication                |
| `--password` | `-P`  | Password for authentication                |
| `--tls`      | `-t`  | Enable TLS encryption                      |
| `--verify`   |       | Verify TLS certificate                     |
| `--json`     | `-j`  | Output all results as JSON                 |

### Common port numbers

| Port  | Interface       |
| ----- | --------------- |
| 2001  | BidCos-RF       |
| 2010  | HmIP-RF         |
| 2000  | BidCos-Wired    |
| 2002  | VirtualDevices  |
| 42001 | BidCos-RF (TLS) |
| 42010 | HmIP-RF (TLS)   |

## Commands

### list-devices

List all parent devices (excluding individual channels) registered on the hub.

```bash
hmcli -H 192.168.1.100 -p 2010 list-devices
```

Example output:

```
ADDRESS      TYPE                    FIRMWARE  FLAGS
-------------------------------------------------------
VCU0000001   HmIP-eTRV-2            1.4.2     1
VCU0000002   HmIP-SWDO              1.10.5    1
VCU0000003   HmIP-SMI55             2.2.2     1
```

### list-channels

List all channels belonging to a specific device.

```bash
hmcli -H 192.168.1.100 -p 2010 list-channels VCU0000001
```

Example output:

```
ADDRESS          TYPE                       FLAGS  DIRECTION
-------------------------------------------------------------
VCU0000001:0     MAINTENANCE                1      0
VCU0000001:1     HEATING_CLIMATECONTROL_..  1      2
```

### list-parameters

List all parameters in a channel's paramset description, showing the parameter type, supported operations, and value range.

```bash
# List VALUES paramset (default)
hmcli -H 192.168.1.100 -p 2010 list-parameters VCU0000001:1

# List MASTER paramset (configuration parameters)
hmcli -H 192.168.1.100 -p 2010 list-parameters VCU0000001:1 -k MASTER
```

The OPERATIONS column uses the following flags:

- **R** -- Readable
- **W** -- Writable
- **E** -- Generates events

Example output:

```
PARAMETER              TYPE     OPERATIONS  MIN   MAX    DEFAULT
-----------------------------------------------------------------
ACTUAL_TEMPERATURE     FLOAT    RE          -273  3276   0.0
SET_POINT_TEMPERATURE  FLOAT    RWE         4.5   30.5   4.5
BOOST_MODE             BOOL     RWE         0     1      0
```

### device-info

Show the full device description dictionary for a given address (device or channel).

```bash
hmcli -H 192.168.1.100 -p 2010 device-info VCU0000001
```

Example output:

```
ADDRESS: VCU0000001
CHILDREN: ['VCU0000001:0', 'VCU0000001:1']
FIRMWARE: 1.4.2
FLAGS: 1
INTERFACE: HmIP-RF
TYPE: HmIP-eTRV-2
```

### get

Read a single parameter value from a channel.

```bash
# Read from VALUES paramset (default)
hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:1 -n ACTUAL_TEMPERATURE

# Read from MASTER paramset
hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:1 -n TEMPERATURE_OFFSET -k MASTER
```

### set

Write a parameter value to a channel. Use `--type` to specify the value type when it cannot be inferred from the string representation.

```bash
# Set a boolean value
hmcli -H 192.168.1.100 -p 2010 set -a VCU0000001:1 -n BOOST_MODE -v 1 --type bool

# Set a float value
hmcli -H 192.168.1.100 -p 2010 set -a VCU0000001:1 -n SET_POINT_TEMPERATURE -v 21.5 --type float

# Set an integer value
hmcli -H 192.168.1.100 -p 2010 set -a VCU0000001:1 -n DURATION_VALUE -v 10 --type int

# Write to MASTER paramset
hmcli -H 192.168.1.100 -p 2010 set -a VCU0000001:1 -n TEMPERATURE_OFFSET -v 1.5 --type float -k MASTER
```

Supported `--type` values: `int`, `float`, `bool`. If omitted, the value is sent as a string.

For `--type bool`, the following string values are interpreted as `True`: `1`, `true`, `yes`, `on`. Everything else is `False`.

### interactive

Start an interactive shell with command history, tab completion, and persistent history (saved to `.hmcli_history`).

```bash
hmcli -H 192.168.1.100 -p 2010 interactive
```

Inside the interactive shell, all commands are available without the connection flags:

```
hmcli> list-devices
hmcli> list-channels VCU0000001
hmcli> list-parameters VCU0000001:1
hmcli> get VCU0000001:1 ACTUAL_TEMPERATURE
hmcli> get VCU0000001:1 TEMPERATURE_OFFSET MASTER
hmcli> set VCU0000001:1 SET_POINT_TEMPERATURE 21.5 float
hmcli> device-info VCU0000001
hmcli> json on
hmcli> list-devices
hmcli> json off
hmcli> quit
```

Interactive mode features:

- **Tab completion**: Press Tab to complete device addresses, channel addresses, parameter names, and paramset keys.
- **Command history**: Use arrow keys to navigate previous commands. History is persisted across sessions in `.hmcli_history`.
- **JSON toggle**: Use `json on` / `json off` to switch output format without restarting.
- **Exit**: Type `quit`, `exit`, or press Ctrl+D.

## JSON output

Pass `--json` (or `-j`) to get machine-readable JSON output from any command.

```bash
# JSON device list
hmcli -H 192.168.1.100 -p 2010 -j list-devices

# JSON parameter value with context
hmcli -H 192.168.1.100 -p 2010 -j get -a VCU0000001:1 -n ACTUAL_TEMPERATURE
```

The `get` command returns a JSON object with `value`, `address`, and `parameter` fields:

```json
{ "value": 21.3, "address": "VCU0000001:1", "parameter": "ACTUAL_TEMPERATURE" }
```

Table commands (`list-devices`, `list-channels`, `list-parameters`) return a JSON array of objects:

```json
[
  {
    "ADDRESS": "VCU0000001",
    "TYPE": "HmIP-eTRV-2",
    "FIRMWARE": "1.4.2",
    "FLAGS": "1"
  }
]
```

JSON output can be combined with `jq` for filtering and formatting:

```bash
# Get all device types
hmcli -H 192.168.1.100 -p 2010 -j list-devices | jq '.[].TYPE'

# Find devices of a specific type
hmcli -H 192.168.1.100 -p 2010 -j list-devices | jq '.[] | select(.TYPE == "HmIP-SWDO")'

# Get all writable parameters of a channel
hmcli -H 192.168.1.100 -p 2010 -j list-parameters VCU0000001:1 | jq '.[] | select(.OPERATIONS | contains("W"))'
```

## Shell completion

Generate completion scripts for your shell:

```bash
# Bash
hmcli --generate-completion bash > /etc/bash_completion.d/hmcli
# or for user-local installation:
hmcli --generate-completion bash >> ~/.bash_completion

# Zsh
hmcli --generate-completion zsh > ~/.zfunc/_hmcli

# Fish
hmcli --generate-completion fish > ~/.config/fish/completions/hmcli.fish
```

Completion covers commands, flags, port numbers, paramset keys, and value types.

## Common use cases

### Verify a device is reachable

```bash
hmcli -H 192.168.1.100 -p 2010 device-info VCU0000001
```

If this returns data, the CCU knows about the device. If it returns "Device not found", the device is not registered on this interface/port.

### Check signal strength

```bash
hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:0 -n RSSI_DEVICE
hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:0 -n RSSI_PEER
```

The maintenance channel (`:0`) typically exposes RSSI values. Negative values closer to zero indicate stronger signal.

### Read thermostat state

```bash
hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:1 -n ACTUAL_TEMPERATURE
hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:1 -n SET_POINT_TEMPERATURE
hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:1 -n VALVE_STATE
```

### Discover parameters for an unknown device

```bash
# Step 1: Find the device
hmcli -H 192.168.1.100 -p 2010 list-devices

# Step 2: List its channels
hmcli -H 192.168.1.100 -p 2010 list-channels VCU0000001

# Step 3: Inspect parameters on a channel
hmcli -H 192.168.1.100 -p 2010 list-parameters VCU0000001:1

# Step 4: Read a specific value
hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:1 -n STATE
```

### Export full device inventory as JSON

```bash
hmcli -H 192.168.1.100 -p 2010 -j list-devices > devices.json
```

### Check configuration parameters

```bash
# List MASTER paramset to see configurable settings
hmcli -H 192.168.1.100 -p 2010 list-parameters VCU0000001:1 -k MASTER
```

### Query multiple interfaces

Different device types are accessible on different ports. Query them separately:

```bash
# HomematicIP devices
hmcli -H 192.168.1.100 -p 2010 list-devices

# Classic Homematic (BidCos-RF) devices
hmcli -H 192.168.1.100 -p 2001 list-devices

# Wired devices
hmcli -H 192.168.1.100 -p 2000 list-devices
```

### Connecting with authentication and TLS

```bash
hmcli -H 192.168.1.100 -p 42010 -U admin -P secret --tls --verify list-devices
```
