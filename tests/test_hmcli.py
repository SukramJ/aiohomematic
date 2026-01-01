# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for the hmcli module."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

import aiohomematic.hmcli as hmcli


class FakeServerProxy:
    """Fake xmlrpc ServerProxy capturing calls and returning canned values."""

    last_init: dict[str, Any] | None = None

    def __init__(self, uri: str, *, context: Any = None, headers: dict[str, str] | None = None) -> None:
        """Initialize fake proxy."""
        FakeServerProxy.last_init = {"uri": uri, "context": context, "headers": headers}
        self.values: dict[tuple[str, str], Any] = {}
        self.paramsets: dict[tuple[str, str], dict[str, Any]] = {}
        self.paramset_descriptions: dict[tuple[str, str], dict[str, Any]] = {}
        self.set_calls: list[tuple[str, str, Any]] = []
        self.put_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.devices: list[dict[str, Any]] = []

    def getParamset(  # noqa: N802
        self, address: str, paramset_key: str
    ) -> dict[str, Any] | None:
        """Return paramset for address."""
        return self.paramsets.get((address, paramset_key), None)

    def getParamsetDescription(  # noqa: N802
        self, address: str, paramset_key: str
    ) -> dict[str, Any]:
        """Return paramset description for address."""
        return self.paramset_descriptions.get((address, paramset_key), {})

    def getValue(self, address: str, param: str) -> Any:  # noqa: N802
        """Return value for address/parameter."""
        return self.values.get((address, param), None)

    def listDevices(self) -> list[dict[str, Any]]:  # noqa: N802
        """Return list of devices."""
        return self.devices

    def putParamset(  # noqa: N802
        self, address: str, paramset_key: str, values: dict[str, Any]
    ) -> None:
        """Record paramset put call."""
        self.put_calls.append((address, paramset_key, values))

    def setValue(self, address: str, param: str, value: Any) -> None:  # noqa: N802
        """Record value set call."""
        self.set_calls.append((address, param, value))


@pytest.fixture(autouse=True)
def reset_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the ServerProxy used by hmcli to our fake."""
    monkeypatch.setattr(hmcli, "ServerProxy", FakeServerProxy)
    monkeypatch.setattr(
        hmcli,
        "build_xml_rpc_uri",
        lambda host, port, path, tls: f"{'https' if tls else 'http'}://{host}:{port}{path or ''}",
    )

    def fake_headers(username: str, password: str) -> dict[str, str]:
        hdrs: dict[str, str] = {}
        if username:
            hdrs["X-User"] = username
        if password:
            hdrs["X-Pass"] = password
        return hdrs

    monkeypatch.setattr(hmcli, "build_xml_rpc_headers", fake_headers)
    monkeypatch.setattr(hmcli, "get_tls_context", lambda verify_tls: {"verify": verify_tls})
    FakeServerProxy.last_init = None


def run_cli(capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """Invoke hmcli.main(), capturing SystemExit and output."""
    try:
        hmcli.main()
    except SystemExit as ex:
        code = int(ex.code) if ex.code is not None else 0
    else:
        code = 0
    out, err = capsys.readouterr()
    return code, out, err


def base_argv(*args: str) -> list[str]:
    """Build CLI arguments."""
    return ["hmcli", *list(args)]


class TestHmcliGetCommand:
    """Test CLI get command."""

    def test_get_value_json(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test get command with JSON output."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.values[("ABC0001:2", "STATE")] = True
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "1.2.3.4", "-p", "2001", "--json", "get", "-a", "ABC0001:2", "-n", "STATE")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        data = json.loads(out)
        assert data == {"address": "ABC0001:2", "parameter": "STATE", "value": True}
        assert err == ""

    def test_get_value_plain(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test get command with plain output."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.values[("OEQ1234567:1", "LEVEL")] = 0.42
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "ccu.local", "-p", "2001", "get", "-a", "OEQ1234567:1", "-n", "LEVEL")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert out.strip() == "0.42"
        assert err == ""


class TestHmcliSetCommand:
    """Test CLI set command."""

    @pytest.mark.parametrize(
        ("typ", "raw", "parsed"),
        [
            ("int", "5", 5),
            ("float", "3.14", 3.14),
            ("bool", "1", True),
            (None, "abc", "abc"),
        ],
    )
    def test_set_value_types(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        typ: str | None,
        raw: str,
        parsed: Any,
    ) -> None:
        """Test set command with different value types."""
        fake = FakeServerProxy("uri", context=None, headers={})

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "ccu", "-p", "2001", "set", "-a", "X:1", "-n", "FOO", "-v", raw)
        if typ is not None:
            argv += ["--type", typ]
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert fake.set_calls == [("X:1", "FOO", parsed)]


class TestHmcliListDevicesCommand:
    """Test CLI list-devices command."""

    def test_list_devices_json(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test list-devices command with JSON output."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.devices = [
                {"ADDRESS": "VCU0000001", "TYPE": "HmIP-BROLL", "FIRMWARE": "1.2.3", "FLAGS": 1},
            ]
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "192.168.1.100", "-p", "2010", "--json", "list-devices")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        data = json.loads(out)
        assert len(data) == 1
        assert data[0]["ADDRESS"] == "VCU0000001"

    def test_list_devices_plain(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test list-devices command with plain output."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.devices = [
                {"ADDRESS": "VCU0000001", "TYPE": "HmIP-BROLL", "FIRMWARE": "1.2.3", "FLAGS": 1},
                {"ADDRESS": "VCU0000001:1", "TYPE": "CHANNEL", "FLAGS": 0},
                {"ADDRESS": "VCU0000002", "TYPE": "HmIP-SMI", "FIRMWARE": "2.0.0", "FLAGS": 1},
            ]
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "192.168.1.100", "-p", "2010", "list-devices")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert "VCU0000001" in out
        assert "VCU0000002" in out
        assert "HmIP-BROLL" in out
        assert "HmIP-SMI" in out
        # Channels should be filtered out
        assert "CHANNEL" not in out
        assert err == ""


class TestHmcliListChannelsCommand:
    """Test CLI list-channels command."""

    def test_list_channels_not_found(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test list-channels command when device not found."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.devices = []
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "192.168.1.100", "-p", "2010", "list-channels", "NONEXISTENT")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 1
        assert "No channels found" in out

    def test_list_channels_plain(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test list-channels command with plain output."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.devices = [
                {"ADDRESS": "VCU0000001", "TYPE": "HmIP-BROLL", "FLAGS": 1},
                {"ADDRESS": "VCU0000001:0", "TYPE": "MAINTENANCE", "FLAGS": 1, "DIRECTION": 0},
                {"ADDRESS": "VCU0000001:1", "TYPE": "BLIND", "FLAGS": 1, "DIRECTION": 1},
                {"ADDRESS": "VCU0000001:2", "TYPE": "BLIND", "FLAGS": 1, "DIRECTION": 1},
                {"ADDRESS": "VCU0000002:1", "TYPE": "OTHER", "FLAGS": 1, "DIRECTION": 1},
            ]
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "192.168.1.100", "-p", "2010", "list-channels", "VCU0000001")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert "VCU0000001:0" in out
        assert "VCU0000001:1" in out
        assert "VCU0000001:2" in out
        assert "VCU0000002" not in out
        assert err == ""


class TestHmcliListParametersCommand:
    """Test CLI list-parameters command."""

    def test_list_parameters_plain(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test list-parameters command with plain output."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.paramset_descriptions[("VCU0000001:1", "VALUES")] = {
                "LEVEL": {
                    "TYPE": "FLOAT",
                    "OPERATIONS": 7,  # R+W+E
                    "MIN": 0.0,
                    "MAX": 1.0,
                    "DEFAULT": 0.0,
                },
                "STATE": {
                    "TYPE": "BOOL",
                    "OPERATIONS": 5,  # R+E
                    "MIN": False,
                    "MAX": True,
                    "DEFAULT": False,
                },
            }
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "192.168.1.100", "-p", "2010", "list-parameters", "VCU0000001:1")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert "LEVEL" in out
        assert "STATE" in out
        assert "FLOAT" in out
        assert "BOOL" in out
        assert "RWE" in out  # Operations
        assert err == ""


class TestHmcliDeviceInfoCommand:
    """Test CLI device-info command."""

    def test_device_info_not_found(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test device-info command when device not found."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.devices = []
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "192.168.1.100", "-p", "2010", "device-info", "NONEXISTENT")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 1
        assert "Device not found" in out

    def test_device_info_plain(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test device-info command with plain output."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.devices = [
                {
                    "ADDRESS": "VCU0000001",
                    "TYPE": "HmIP-BROLL",
                    "FIRMWARE": "1.2.3",
                    "FLAGS": 1,
                    "INTERFACE": "HmIP-RF",
                },
            ]
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "192.168.1.100", "-p", "2010", "device-info", "VCU0000001")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert "ADDRESS: VCU0000001" in out
        assert "TYPE: HmIP-BROLL" in out
        assert err == ""


class TestHmcliShellCompletion:
    """Test CLI shell completion generation."""

    def test_bash_completion(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test bash completion script generation."""
        argv = base_argv("--generate-completion", "bash")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert "_hmcli_completion" in out
        assert "complete -F" in out

    def test_fish_completion(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test fish completion script generation."""
        argv = base_argv("--generate-completion", "fish")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert "complete -c hmcli" in out
        assert "list-devices" in out

    def test_zsh_completion(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test zsh completion script generation."""
        argv = base_argv("--generate-completion", "zsh")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert "#compdef hmcli" in out
        assert "_hmcli" in out


class TestHmcliConnectionSettings:
    """Test CLI connection settings and authentication."""

    def test_no_tls_uses_http(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that without --tls flag, HTTP is used."""
        argv = base_argv("-H", "host", "-p", "2001", "get", "-a", "D:1", "-n", "STATE")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        init = FakeServerProxy.last_init
        assert init is not None
        assert init["uri"].startswith("http://")
        assert init["context"] is None

    def test_tls_and_headers_in_proxy_init(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test TLS and authentication headers are passed to proxy."""
        argv = base_argv(
            "-H",
            "host",
            "-p",
            "2001",
            "--tls",
            "--verify",
            "-U",
            "user",
            "-P",
            "pass",
            "get",
            "-a",
            "D:1",
            "-n",
            "STATE",
        )
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        init = FakeServerProxy.last_init
        assert init is not None
        assert init["uri"].startswith("https://host:2001")
        assert init["context"] == {"verify": True}
        assert init["headers"] == {"X-User": "user", "X-Pass": "pass"}


class TestHmcliErrorHandling:
    """Test CLI error handling."""

    def test_error_handling_prints_and_exits(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that errors are printed and exit code is 1."""

        class Boom(FakeServerProxy):
            def getValue(self, address: str, param: str) -> Any:  # noqa: N802
                raise RuntimeError("boom")

        monkeypatch.setattr(hmcli, "ServerProxy", lambda *a, **k: Boom("uri"))

        argv = base_argv("-H", "h", "-p", "2001", "get", "-a", "A:1", "-n", "X")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 1
        assert "boom" in err

    def test_missing_required_host(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that missing --host argument causes error."""
        argv = base_argv("-p", "2001", "get", "-a", "A:1", "-n", "X")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 1
        assert "--host" in err or "required" in err.lower()

    def test_missing_required_port(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that missing --port argument causes error."""
        argv = base_argv("-H", "host", "get", "-a", "A:1", "-n", "X")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 1
        assert "--port" in err or "required" in err.lower()

    def test_no_command_shows_help(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that running without command shows help."""
        argv = base_argv()
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 1
        # Help or usage should be shown


class TestHmcliMasterParamset:
    """Test CLI operations with MASTER paramset."""

    def test_get_master_value(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test getting value from MASTER paramset."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.paramsets[("DEV:0", "MASTER")] = {"PROFILE": 2}
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "h", "-p", "2001", "get", "-a", "DEV:0", "-n", "PROFILE", "-k", "MASTER")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert out.strip() == "2"

    def test_set_master_value(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test setting value in MASTER paramset."""
        fake = FakeServerProxy("uri", context=None, headers={})

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv(
            "-H", "h", "-p", "2001", "set", "-a", "DEV:0", "-n", "PROFILE", "-v", "7", "--type", "int", "-k", "MASTER"
        )
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert fake.put_calls == [("DEV:0", "MASTER", {"PROFILE": 7})]


class TestHmcliHmCliConnection:
    """Test _HmCliConnection class."""

    def test_get_channel_addresses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_channel_addresses with device filter."""
        connection = hmcli._HmCliConnection(host="h", port=2001)

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.devices = [
                {"ADDRESS": "VCU0000001"},
                {"ADDRESS": "VCU0000001:0"},
                {"ADDRESS": "VCU0000001:1"},
                {"ADDRESS": "VCU0000002:0"},
            ]
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        # All channels
        channels = connection.get_channel_addresses()
        assert "VCU0000001:0" in channels
        assert "VCU0000001:1" in channels
        assert "VCU0000002:0" in channels

        # Filtered channels
        channels = connection.get_channel_addresses(device_address="VCU0000001")
        assert channels == ["VCU0000001:0", "VCU0000001:1"]

    def test_get_device_addresses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_device_addresses filters channels."""
        connection = hmcli._HmCliConnection(host="h", port=2001)

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.devices = [
                {"ADDRESS": "VCU0000001"},
                {"ADDRESS": "VCU0000001:0"},
                {"ADDRESS": "VCU0000001:1"},
                {"ADDRESS": "VCU0000002"},
            ]
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        addresses = connection.get_device_addresses()
        assert addresses == ["VCU0000001", "VCU0000002"]

    def test_list_devices_caches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that list_devices caches results."""
        call_count = 0

        class CountingProxy(FakeServerProxy):
            def listDevices(self) -> list[dict[str, Any]]:  # noqa: N802
                nonlocal call_count
                call_count += 1
                return [{"ADDRESS": "VCU0001"}]

        monkeypatch.setattr(hmcli, "ServerProxy", CountingProxy)

        connection = hmcli._HmCliConnection(host="h", port=2001)
        connection.list_devices()
        connection.list_devices()
        connection.list_devices()

        assert call_count == 1  # Only called once due to caching
