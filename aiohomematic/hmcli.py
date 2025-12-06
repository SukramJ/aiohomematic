#!/usr/bin/python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Commandline tool to query Homematic hubs via XML-RPC.

Public API of this module is defined by __all__.

This module provides a command-line interface with:
- Device discovery commands (list-devices, list-channels, list-parameters)
- Parameter read/write operations (get, set)
- Interactive mode with command history and completion
- Shell completion script generation

Usage examples::

    # List all devices
    hmcli -H 192.168.1.100 -p 2010 list-devices

    # List channels of a device
    hmcli -H 192.168.1.100 -p 2010 list-channels VCU0000001

    # Get a parameter value
    hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:1 -n STATE

    # Set a parameter value
    hmcli -H 192.168.1.100 -p 2010 set -a VCU0000001:1 -n STATE -v 1 --type bool

    # Interactive mode
    hmcli -H 192.168.1.100 -p 2010 interactive

    # Generate shell completion
    hmcli --generate-completion bash > /etc/bash_completion.d/hmcli

"""

from __future__ import annotations

import argparse
import cmd
import contextlib
import json
import readline
from ssl import SSLContext
import sys
from typing import Any, Final
from xmlrpc.client import ServerProxy

from aiohomematic import __version__
from aiohomematic.const import ParamsetKey
from aiohomematic.support import build_xml_rpc_headers, build_xml_rpc_uri, get_tls_context

# Define public API for this module (CLI only)
__all__ = ["main"]

# Shell completion templates
_BASH_COMPLETION: Final = """# Bash completion for hmcli
_hmcli_completion() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="list-devices list-channels list-parameters device-info get set interactive"

    case "${prev}" in
        hmcli)
            COMPREPLY=( $(compgen -W "--host -H --port -p --username -U --password -P --tls --verify --json --help --version --generate-completion ${commands}" -- ${cur}) )
            return 0
            ;;
        -H|--host)
            return 0
            ;;
        -p|--port)
            COMPREPLY=( $(compgen -W "2000 2001 2002 2010 42000 42001 42002 42010" -- ${cur}) )
            return 0
            ;;
        list-devices|interactive)
            return 0
            ;;
        list-channels|device-info)
            return 0
            ;;
        list-parameters)
            return 0
            ;;
        get|set)
            COMPREPLY=( $(compgen -W "-a --address -n --parameter --paramset_key" -- ${cur}) )
            return 0
            ;;
        -a|--address)
            return 0
            ;;
        -n|--parameter)
            return 0
            ;;
        --type)
            COMPREPLY=( $(compgen -W "int float bool str" -- ${cur}) )
            return 0
            ;;
        --paramset_key)
            COMPREPLY=( $(compgen -W "VALUES MASTER" -- ${cur}) )
            return 0
            ;;
        --generate-completion)
            COMPREPLY=( $(compgen -W "bash zsh fish" -- ${cur}) )
            return 0
            ;;
        *)
            COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
            return 0
            ;;
    esac
}
complete -F _hmcli_completion hmcli
"""

_ZSH_COMPLETION: Final = """#compdef hmcli
# Zsh completion for hmcli

_hmcli() {
    local -a commands
    commands=(
        'list-devices:List all devices'
        'list-channels:List channels of a device'
        'list-parameters:List parameters of a channel'
        'device-info:Show detailed device information'
        'get:Get parameter value'
        'set:Set parameter value'
        'interactive:Start interactive mode'
    )

    _arguments -C \\
        '(-H --host)'{-H,--host}'[Hostname/IP address]:host:' \\
        '(-p --port)'{-p,--port}'[Port number]:port:(2000 2001 2002 2010 42000 42001 42002 42010)' \\
        '(-U --username)'{-U,--username}'[Username]:username:' \\
        '(-P --password)'{-P,--password}'[Password]:password:' \\
        '(-t --tls)'{-t,--tls}'[Enable TLS]' \\
        '(-v --verify)'{-v,--verify}'[Verify TLS certificate]' \\
        '(-j --json)'{-j,--json}'[Output as JSON]' \\
        '--version[Show version]' \\
        '--help[Show help]' \\
        '--generate-completion[Generate shell completion]:shell:(bash zsh fish)' \\
        '1:command:->commands' \\
        '*::arg:->args'

    case $state in
        commands)
            _describe -t commands 'hmcli commands' commands
            ;;
        args)
            case $words[1] in
                get|set)
                    _arguments \\
                        '(-a --address)'{-a,--address}'[Device address]:address:' \\
                        '(-n --parameter)'{-n,--parameter}'[Parameter name]:parameter:' \\
                        '--paramset_key[Paramset key]:key:(VALUES MASTER)' \\
                        '(-v --value)'{-v,--value}'[Value to set]:value:' \\
                        '--type[Value type]:type:(int float bool str)'
                    ;;
                list-channels|device-info)
                    _arguments '1:address:'
                    ;;
                list-parameters)
                    _arguments '1:channel_address:'
                    ;;
            esac
            ;;
    esac
}

_hmcli "$@"
"""

_FISH_COMPLETION: Final = """# Fish completion for hmcli

# Disable file completion by default
complete -c hmcli -f

# Global options
complete -c hmcli -s H -l host -d 'Hostname/IP address' -x
complete -c hmcli -s p -l port -d 'Port number' -xa '2000 2001 2002 2010 42000 42001 42002 42010'
complete -c hmcli -s U -l username -d 'Username' -x
complete -c hmcli -s P -l password -d 'Password' -x
complete -c hmcli -s t -l tls -d 'Enable TLS'
complete -c hmcli -s v -l verify -d 'Verify TLS certificate'
complete -c hmcli -s j -l json -d 'Output as JSON'
complete -c hmcli -l version -d 'Show version'
complete -c hmcli -l help -d 'Show help'
complete -c hmcli -l generate-completion -d 'Generate shell completion' -xa 'bash zsh fish'

# Commands
complete -c hmcli -n '__fish_use_subcommand' -a list-devices -d 'List all devices'
complete -c hmcli -n '__fish_use_subcommand' -a list-channels -d 'List channels of a device'
complete -c hmcli -n '__fish_use_subcommand' -a list-parameters -d 'List parameters of a channel'
complete -c hmcli -n '__fish_use_subcommand' -a device-info -d 'Show device information'
complete -c hmcli -n '__fish_use_subcommand' -a get -d 'Get parameter value'
complete -c hmcli -n '__fish_use_subcommand' -a set -d 'Set parameter value'
complete -c hmcli -n '__fish_use_subcommand' -a interactive -d 'Start interactive mode'

# get/set options
complete -c hmcli -n '__fish_seen_subcommand_from get set' -s a -l address -d 'Device address' -x
complete -c hmcli -n '__fish_seen_subcommand_from get set' -s n -l parameter -d 'Parameter name' -x
complete -c hmcli -n '__fish_seen_subcommand_from get set' -l paramset_key -d 'Paramset key' -xa 'VALUES MASTER'
complete -c hmcli -n '__fish_seen_subcommand_from set' -s v -l value -d 'Value to set' -x
complete -c hmcli -n '__fish_seen_subcommand_from set' -l type -d 'Value type' -xa 'int float bool str'
"""


class _HmCliConnection:
    """Manage connection to Homematic hub."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        path: str | None = None,
        username: str | None = None,
        password: str | None = None,
        tls: bool = False,
        verify_tls: bool = False,
    ) -> None:
        """Initialize connection."""
        self.host = host
        self.port = port
        self.path = path
        self.username = username
        self.password = password
        self.tls = tls
        self.verify_tls = verify_tls
        self._proxy: ServerProxy | None = None
        self._devices: list[dict[str, Any]] | None = None

    @property
    def proxy(self) -> ServerProxy:
        """Return XML-RPC proxy, creating if needed."""
        if self._proxy is None:
            url = build_xml_rpc_uri(
                host=self.host,
                port=self.port,
                path=self.path,
                tls=self.tls,
            )
            headers = build_xml_rpc_headers(
                username=self.username or "",
                password=self.password or "",
            )
            context: SSLContext | None = None
            if self.tls:
                context = get_tls_context(verify_tls=self.verify_tls)
            self._proxy = ServerProxy(url, context=context, headers=headers)
        return self._proxy

    def get_channel_addresses(self, *, device_address: str | None = None) -> list[str]:
        """Return list of channel addresses."""
        devices = self.list_devices()
        channels = [d["ADDRESS"] for d in devices if ":" in d["ADDRESS"]]
        if device_address:
            channels = [c for c in channels if c.startswith(f"{device_address}:")]
        return sorted(channels)

    def get_device_addresses(self) -> list[str]:
        """Return list of device addresses (without channels)."""
        devices = self.list_devices()
        return sorted({d["ADDRESS"].split(":")[0] for d in devices if ":" not in d["ADDRESS"]})

    def get_device_info(self, *, address: str) -> dict[str, Any] | None:
        """Return device info for an address."""
        devices = self.list_devices()
        for device in devices:
            if device["ADDRESS"] == address:
                return device
        return None

    def get_paramset(self, *, address: str, paramset_key: str) -> dict[str, Any]:
        """Get full paramset."""
        return self.proxy.getParamset(address, paramset_key)  # type: ignore[return-value]

    def get_paramset_description(self, *, address: str, paramset_key: str = "VALUES") -> dict[str, Any]:
        """Return paramset description for a channel."""
        return self.proxy.getParamsetDescription(address, paramset_key)  # type: ignore[return-value]

    def get_value(self, *, address: str, parameter: str) -> Any:
        """Get parameter value."""
        return self.proxy.getValue(address, parameter)

    def list_devices(self) -> list[dict[str, Any]]:
        """List all devices from the hub."""
        if self._devices is None:
            self._devices = self.proxy.listDevices()  # type: ignore[assignment]
        return self._devices or []

    def put_paramset(self, *, address: str, paramset_key: str, values: dict[str, Any]) -> None:
        """Put paramset values."""
        self.proxy.putParamset(address, paramset_key, values)

    def set_value(self, *, address: str, parameter: str, value: Any) -> None:
        """Set parameter value."""
        self.proxy.setValue(address, parameter, value)


class _InteractiveShell(cmd.Cmd):
    """Interactive shell for hmcli."""

    intro = "Homematic CLI - Interactive Mode. Type 'help' for commands, 'quit' to exit."
    prompt = "hmcli> "

    def __init__(self, *, connection: _HmCliConnection, json_output: bool = False) -> None:
        """Initialize interactive shell."""
        super().__init__()
        self.connection = connection
        self.json_output = json_output
        self._setup_readline()

    def complete_device_info(  # kwonly: disable
        self, text: str, line: str, begidx: int, endidx: int
    ) -> list[str]:
        """Complete addresses for device-info."""
        try:
            devices = self.connection.list_devices()
            addresses = [d["ADDRESS"] for d in devices]
            return [a for a in addresses if a.startswith(text)]
        except Exception:
            return []

    def complete_get(  # kwonly: disable
        self, text: str, line: str, begidx: int, endidx: int
    ) -> list[str]:
        """Complete for get command."""
        parts = line.split()
        if len(parts) <= 2:
            # Complete channel address
            try:
                channels = self.connection.get_channel_addresses()
                return [c for c in channels if c.startswith(text)]
            except Exception:
                return []
        elif len(parts) == 3:
            # Complete parameter name
            try:
                address = parts[1]
                params = self.connection.get_paramset_description(address=address)
                return [p for p in params if p.startswith(text.upper())]
            except Exception:
                return []
        elif len(parts) == 4:
            return [k for k in ("VALUES", "MASTER") if k.startswith(text.upper())]
        return []

    def complete_list_channels(  # kwonly: disable
        self, text: str, line: str, begidx: int, endidx: int
    ) -> list[str]:
        """Complete device addresses for list-channels."""
        try:
            addresses = self.connection.get_device_addresses()
            return [a for a in addresses if a.startswith(text)]
        except Exception:
            return []

    def complete_list_parameters(  # kwonly: disable
        self, text: str, line: str, begidx: int, endidx: int
    ) -> list[str]:
        """Complete channel addresses for list-parameters."""
        parts = line.split()
        if len(parts) <= 2:
            try:
                channels = self.connection.get_channel_addresses()
                return [c for c in channels if c.startswith(text)]
            except Exception:
                return []
        elif len(parts) == 3:
            return [k for k in ("VALUES", "MASTER") if k.startswith(text.upper())]
        return []

    def complete_set(  # kwonly: disable
        self, text: str, line: str, begidx: int, endidx: int
    ) -> list[str]:
        """Complete for set command."""
        parts = line.split()
        if len(parts) <= 2:
            try:
                channels = self.connection.get_channel_addresses()
                return [c for c in channels if c.startswith(text)]
            except Exception:
                return []
        elif len(parts) == 3:
            try:
                address = parts[1]
                params = self.connection.get_paramset_description(address=address)
                return [p for p in params if p.startswith(text.upper())]
            except Exception:
                return []
        return []

    def default(self, line: str) -> None:  # kwonly: disable
        """Handle unknown commands."""
        print(f"Unknown command: {line}. Type 'help' for available commands.")

    def do_EOF(self, arg: str) -> bool:  # kwonly: disable
        """Handle Ctrl+D."""
        print()
        return self.do_quit(arg)

    def do_device_info(self, arg: str) -> None:  # kwonly: disable
        """Show detailed device information (usage: device-info <address>)."""
        if not arg:
            print("Usage: device-info <address>", file=sys.stderr)
            return

        address = arg.strip()
        try:
            if (info := self.connection.get_device_info(address=address)) is None:
                print(f"Device not found: {address}")
                return

            if self.json_output:
                print(json.dumps(info, ensure_ascii=False, indent=2))
            else:
                for key, value in sorted(info.items()):
                    print(f"{key}: {value}")
        except Exception as ex:
            print(f"Error: {ex}", file=sys.stderr)

    def do_exit(self, arg: str) -> bool:  # kwonly: disable
        """Exit the interactive shell."""
        return self.do_quit(arg)

    def do_get(self, arg: str) -> None:  # kwonly: disable
        """Get parameter value (usage: get <channel_address> <parameter> [VALUES|MASTER])."""
        parts = arg.strip().split()
        if len(parts) < 2:
            print("Usage: get <channel_address> <parameter> [VALUES|MASTER]", file=sys.stderr)
            return

        address = parts[0]
        parameter = parts[1]
        paramset_key = parts[2] if len(parts) > 2 else "VALUES"

        try:
            if paramset_key == "VALUES":
                result = self.connection.get_value(address=address, parameter=parameter)
            else:
                paramset = self.connection.get_paramset(address=address, paramset_key=paramset_key)
                result = paramset.get(parameter, "Parameter not found")

            self._print_result(result=result, context={"address": address, "parameter": parameter})
        except Exception as ex:
            print(f"Error: {ex}", file=sys.stderr)

    def do_json(self, arg: str) -> None:  # kwonly: disable
        """Toggle JSON output mode (usage: json [on|off])."""
        if arg.strip().lower() in ("on", "true", "1"):
            self.json_output = True
            print("JSON output enabled")
        elif arg.strip().lower() in ("off", "false", "0"):
            self.json_output = False
            print("JSON output disabled")
        else:
            self.json_output = not self.json_output
            print(f"JSON output {'enabled' if self.json_output else 'disabled'}")

    def do_list_channels(self, arg: str) -> None:  # kwonly: disable
        """List channels of a device (usage: list-channels <device_address>)."""
        if not arg:
            print("Usage: list-channels <device_address>", file=sys.stderr)
            return

        device_address = arg.strip()
        try:
            devices = self.connection.list_devices()
            if not (channels := [d for d in devices if d["ADDRESS"].startswith(f"{device_address}:")]):
                print(f"No channels found for device {device_address}")
                return

            headers = ["ADDRESS", "TYPE", "FLAGS", "DIRECTION"]
            rows = [
                [
                    d.get("ADDRESS", ""),
                    d.get("TYPE", ""),
                    str(d.get("FLAGS", "")),
                    str(d.get("DIRECTION", "")),
                ]
                for d in sorted(channels, key=lambda x: x.get("ADDRESS", ""))
            ]
            self._print_table(headers=headers, rows=rows)
        except Exception as ex:
            print(f"Error: {ex}", file=sys.stderr)

    def do_list_devices(self, arg: str) -> None:  # kwonly: disable
        """List all devices."""
        del arg  # unused
        try:
            devices = self.connection.list_devices()
            # Filter to only parent devices (no channel suffix)
            parent_devices = [d for d in devices if ":" not in d["ADDRESS"]]

            headers = ["ADDRESS", "TYPE", "FIRMWARE", "FLAGS"]
            rows = [
                [
                    d.get("ADDRESS", ""),
                    d.get("TYPE", ""),
                    d.get("FIRMWARE", ""),
                    str(d.get("FLAGS", "")),
                ]
                for d in sorted(parent_devices, key=lambda x: x.get("ADDRESS", ""))
            ]
            self._print_table(headers=headers, rows=rows)
        except Exception as ex:
            print(f"Error: {ex}", file=sys.stderr)

    def do_list_parameters(self, arg: str) -> None:  # kwonly: disable
        """List parameters of a channel (usage: list-parameters <address> [VALUES|MASTER])."""
        if not (parts := arg.strip().split()):
            print("Usage: list-parameters <channel_address> [VALUES|MASTER]", file=sys.stderr)
            return

        channel_address = parts[0]
        paramset_key = parts[1] if len(parts) > 1 else "VALUES"

        try:
            params = self.connection.get_paramset_description(address=channel_address, paramset_key=paramset_key)

            headers = ["PARAMETER", "TYPE", "OPERATIONS", "MIN", "MAX", "DEFAULT"]
            rows = []
            for name, info in sorted(params.items()):
                ops = []
                op_val = info.get("OPERATIONS", 0)
                if op_val & 1:
                    ops.append("R")
                if op_val & 2:
                    ops.append("W")
                if op_val & 4:
                    ops.append("E")

                rows.append(
                    [
                        name,
                        info.get("TYPE", ""),
                        "".join(ops),
                        str(info.get("MIN", "")),
                        str(info.get("MAX", "")),
                        str(info.get("DEFAULT", "")),
                    ]
                )
            self._print_table(headers=headers, rows=rows)
        except Exception as ex:
            print(f"Error: {ex}", file=sys.stderr)

    def do_quit(self, arg: str) -> bool:  # kwonly: disable
        """Exit the interactive shell."""
        del arg  # unused
        self._save_history()
        print("Goodbye!")
        return True

    def do_set(self, arg: str) -> None:  # kwonly: disable
        """Set parameter value (usage: set <address> <parameter> <value> [type])."""
        parts = arg.strip().split()
        if len(parts) < 3:
            print("Usage: set <channel_address> <parameter> <value> [int|float|bool] [VALUES|MASTER]", file=sys.stderr)
            return

        address = parts[0]
        parameter = parts[1]
        value_str = parts[2]
        value_type = parts[3] if len(parts) > 3 and parts[3] in ("int", "float", "bool") else None
        paramset_key = parts[-1] if parts[-1] in ("VALUES", "MASTER") else "VALUES"

        try:
            value: Any = value_str
            if value_type == "int":
                value = int(value_str)
            elif value_type == "float":
                value = float(value_str)
            elif value_type == "bool":
                value = value_str.lower() in ("1", "true", "yes", "on")

            if paramset_key == "VALUES":
                self.connection.set_value(address=address, parameter=parameter, value=value)
            else:
                self.connection.put_paramset(address=address, paramset_key=paramset_key, values={parameter: value})

            print(f"Set {address}.{parameter} = {value}")
        except Exception as ex:
            print(f"Error: {ex}", file=sys.stderr)

    def emptyline(self) -> bool:
        """Do nothing on empty line."""
        return False

    def _print_result(self, *, result: Any, context: dict[str, Any] | None = None) -> None:
        """Print a result value."""
        if self.json_output:
            output = {"value": result}
            if context:
                output.update(context)
            print(json.dumps(output, ensure_ascii=False))
        else:
            print(result)

    def _print_table(self, *, headers: list[str], rows: list[list[str]]) -> None:
        """Print data as formatted table."""
        if self.json_output:
            data = [dict(zip(headers, row, strict=False)) for row in rows]
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return

        if not rows:
            print("No data found.")
            return

        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))

        # Print header
        header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
        print(header_line)
        print("-" * len(header_line))

        # Print rows
        for row in rows:
            print("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))

    def _save_history(self) -> None:
        """Save command history."""
        with contextlib.suppress(OSError):
            readline.write_history_file(".hmcli_history")

    def _setup_readline(self) -> None:
        """Configure readline for history and completion."""
        with contextlib.suppress(FileNotFoundError):
            readline.read_history_file(".hmcli_history")
        readline.set_history_length(1000)
        readline.parse_and_bind("tab: complete")


def _format_output(data: Any, as_json: bool, context: dict[str, Any] | None = None) -> str:
    """Format output as JSON or plain text."""
    if as_json:
        output = {"value": data}
        if context:
            output.update(context)
        return json.dumps(output, ensure_ascii=False)
    return str(data)


def _print_table(headers: list[str], *, rows: list[list[str]], as_json: bool) -> None:
    """Print data as table or JSON."""
    if as_json:
        data = [dict(zip(headers, row, strict=False)) for row in rows]
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("No data found.")
        return

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("-" * len(header_line))
    for row in rows:
        print("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))


def _cmd_list_devices(connection: _HmCliConnection, args: argparse.Namespace) -> int:
    """Handle list-devices command."""
    try:
        devices = connection.list_devices()
        parent_devices = [d for d in devices if ":" not in d["ADDRESS"]]

        headers = ["ADDRESS", "TYPE", "FIRMWARE", "FLAGS"]
        rows = [
            [d.get("ADDRESS", ""), d.get("TYPE", ""), d.get("FIRMWARE", ""), str(d.get("FLAGS", ""))]
            for d in sorted(parent_devices, key=lambda x: x.get("ADDRESS", ""))
        ]
        _print_table(headers, rows=rows, as_json=args.json)
    except Exception as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1
    return 0


def _cmd_list_channels(connection: _HmCliConnection, args: argparse.Namespace) -> int:
    """Handle list-channels command."""
    try:
        devices = connection.list_devices()

        if not (channels := [d for d in devices if d["ADDRESS"].startswith(f"{args.device_address}:")]):
            print(f"No channels found for device {args.device_address}")
            return 1

        headers = ["ADDRESS", "TYPE", "FLAGS", "DIRECTION"]
        rows = [
            [d.get("ADDRESS", ""), d.get("TYPE", ""), str(d.get("FLAGS", "")), str(d.get("DIRECTION", ""))]
            for d in sorted(channels, key=lambda x: x.get("ADDRESS", ""))
        ]
        _print_table(headers, rows=rows, as_json=args.json)
    except Exception as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1
    return 0


def _cmd_list_parameters(connection: _HmCliConnection, args: argparse.Namespace) -> int:
    """Handle list-parameters command."""
    try:
        params = connection.get_paramset_description(address=args.channel_address, paramset_key=args.paramset_key)

        headers = ["PARAMETER", "TYPE", "OPERATIONS", "MIN", "MAX", "DEFAULT"]
        rows = []
        for name, info in sorted(params.items()):
            ops = []
            op_val = info.get("OPERATIONS", 0)
            if op_val & 1:
                ops.append("R")
            if op_val & 2:
                ops.append("W")
            if op_val & 4:
                ops.append("E")

            rows.append(
                [
                    name,
                    info.get("TYPE", ""),
                    "".join(ops),
                    str(info.get("MIN", "")),
                    str(info.get("MAX", "")),
                    str(info.get("DEFAULT", "")),
                ]
            )
        _print_table(headers, rows=rows, as_json=args.json)
    except Exception as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1
    return 0


def _cmd_device_info(connection: _HmCliConnection, args: argparse.Namespace) -> int:
    """Handle device-info command."""
    try:
        if (info := connection.get_device_info(address=args.device_address)) is None:
            print(f"Device not found: {args.device_address}")
            return 1

        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            for key, value in sorted(info.items()):
                print(f"{key}: {value}")
    except Exception as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1
    return 0


def _cmd_get(connection: _HmCliConnection, args: argparse.Namespace) -> int:
    """Handle get command."""
    try:
        if args.paramset_key == ParamsetKey.VALUES:
            result = connection.get_value(address=args.address, parameter=args.parameter)
        else:
            paramset = connection.get_paramset(address=args.address, paramset_key=args.paramset_key)
            if args.parameter not in paramset:
                print(f"Parameter not found: {args.parameter}", file=sys.stderr)
                return 1
            result = paramset[args.parameter]

        print(_format_output(result, args.json, {"address": args.address, "parameter": args.parameter}))
    except Exception as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1
    return 0


def _cmd_set(connection: _HmCliConnection, args: argparse.Namespace) -> int:
    """Handle set command."""
    try:
        value: Any = args.value
        if args.type == "int":
            value = int(args.value)
        elif args.type == "float":
            value = float(args.value)
        elif args.type == "bool":
            value = bool(int(args.value))

        if args.paramset_key == ParamsetKey.VALUES:
            connection.set_value(address=args.address, parameter=args.parameter, value=value)
        else:
            connection.put_paramset(
                address=args.address, paramset_key=args.paramset_key, values={args.parameter: value}
            )
    except Exception as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1
    return 0


def _cmd_interactive(connection: _HmCliConnection, args: argparse.Namespace) -> int:
    """Handle interactive command."""
    shell = _InteractiveShell(connection=connection, json_output=args.json)
    try:
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nInterrupted")
    return 0


def main() -> None:
    """Start the CLI."""
    parser = argparse.ArgumentParser(
        description="Commandline tool to query Homematic hubs via XML-RPC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hmcli -H 192.168.1.100 -p 2010 list-devices
  hmcli -H 192.168.1.100 -p 2010 list-channels VCU0000001
  hmcli -H 192.168.1.100 -p 2010 list-parameters VCU0000001:1
  hmcli -H 192.168.1.100 -p 2010 get -a VCU0000001:1 -n STATE
  hmcli -H 192.168.1.100 -p 2010 set -a VCU0000001:1 -n STATE -v 1 --type bool
  hmcli -H 192.168.1.100 -p 2010 interactive
  hmcli --generate-completion bash > /etc/bash_completion.d/hmcli
""",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--generate-completion",
        choices=["bash", "zsh", "fish"],
        help="Generate shell completion script and exit",
    )

    # Connection options
    conn_group = parser.add_argument_group("connection options")
    conn_group.add_argument("--host", "-H", type=str, help="Hostname / IP address to connect to")
    conn_group.add_argument("--port", "-p", type=int, help="Port to connect to")
    conn_group.add_argument("--path", type=str, help="Path, used for heating groups")
    conn_group.add_argument("--username", "-U", nargs="?", help="Username required for access")
    conn_group.add_argument("--password", "-P", nargs="?", help="Password required for access")
    conn_group.add_argument("--tls", "-t", action="store_true", help="Enable TLS encryption")
    conn_group.add_argument("--verify", action="store_true", help="Verify TLS encryption")
    conn_group.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", title="commands")

    # list-devices
    subparsers.add_parser("list-devices", help="List all devices")

    # list-channels
    parser_channels = subparsers.add_parser("list-channels", help="List channels of a device")
    parser_channels.add_argument("device_address", help="Device address (e.g., VCU0000001)")

    # list-parameters
    parser_params = subparsers.add_parser("list-parameters", help="List parameters of a channel")
    parser_params.add_argument("channel_address", help="Channel address (e.g., VCU0000001:1)")
    parser_params.add_argument(
        "--paramset_key",
        "-k",
        default="VALUES",
        choices=["VALUES", "MASTER"],
        help="Paramset key (default: VALUES)",
    )

    # device-info
    parser_info = subparsers.add_parser("device-info", help="Show detailed device information")
    parser_info.add_argument("device_address", help="Device or channel address")

    # get
    parser_get = subparsers.add_parser("get", help="Get parameter value")
    parser_get.add_argument("--address", "-a", required=True, help="Channel address")
    parser_get.add_argument("--parameter", "-n", required=True, help="Parameter name")
    parser_get.add_argument(
        "--paramset_key",
        "-k",
        default=ParamsetKey.VALUES,
        choices=[ParamsetKey.VALUES, ParamsetKey.MASTER],
        help="Paramset key (default: VALUES)",
    )

    # set
    parser_set = subparsers.add_parser("set", help="Set parameter value")
    parser_set.add_argument("--address", "-a", required=True, help="Channel address")
    parser_set.add_argument("--parameter", "-n", required=True, help="Parameter name")
    parser_set.add_argument("--value", "-v", required=True, help="Value to set")
    parser_set.add_argument("--type", choices=["int", "float", "bool"], help="Value type")
    parser_set.add_argument(
        "--paramset_key",
        "-k",
        default=ParamsetKey.VALUES,
        choices=[ParamsetKey.VALUES, ParamsetKey.MASTER],
        help="Paramset key (default: VALUES)",
    )

    # interactive
    subparsers.add_parser("interactive", help="Start interactive mode")

    args = parser.parse_args()

    # Handle shell completion generation
    if args.generate_completion:
        if args.generate_completion == "bash":
            print(_BASH_COMPLETION)
        elif args.generate_completion == "zsh":
            print(_ZSH_COMPLETION)
        elif args.generate_completion == "fish":
            print(_FISH_COMPLETION)
        sys.exit(0)

    # Require host and port for all commands
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not args.host or not args.port:
        print("Error: --host and --port are required", file=sys.stderr)
        sys.exit(1)

    # Create connection
    connection = _HmCliConnection(
        host=args.host,
        port=args.port,
        path=args.path,
        username=args.username,
        password=args.password,
        tls=args.tls,
        verify_tls=args.verify,
    )

    # Dispatch to command handler
    handlers = {
        "list-devices": _cmd_list_devices,
        "list-channels": _cmd_list_channels,
        "list-parameters": _cmd_list_parameters,
        "device-info": _cmd_device_info,
        "get": _cmd_get,
        "set": _cmd_set,
        "interactive": _cmd_interactive,
    }

    if handler := handlers.get(args.command):
        sys.exit(handler(connection, args))

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
