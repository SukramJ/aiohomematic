from __future__ import annotations

import json
import sys
from typing import Any

import pytest

import aiohomematic.hmcli as hmcli


class FakeServerProxy:
    """Fake xmlrpc ServerProxy capturing calls and returning canned values."""

    last_init: dict[str, Any] | None = None

    def __init__(self, uri: str, *, context: Any = None, headers: dict[str, str] | None = None) -> None:  # type: ignore[no-untyped-def]
        # record constructor args
        FakeServerProxy.last_init = {"uri": uri, "context": context, "headers": headers}
        # Defaults for method results
        self.values: dict[tuple[str, str], Any] = {}
        self.paramsets: dict[tuple[str, hmcli.ParamsetKey], dict[str, Any]] = {}
        self.set_calls: list[tuple[str, str, Any]] = []
        self.put_calls: list[tuple[str, hmcli.ParamsetKey, dict[str, Any]]] = []

    def getParamset(self, address: str, paramset_key: hmcli.ParamsetKey) -> dict[str, Any] | None:  # noqa: N802
        return self.paramsets.get((address, paramset_key), None)

    def getValue(self, address: str, param: str) -> Any:  # noqa: N802 - xmlrpc style
        return self.values.get((address, param), None)

    def putParamset(self, address: str, paramset_key: hmcli.ParamsetKey, values: dict[str, Any]) -> None:  # noqa: N802
        self.put_calls.append((address, paramset_key, values))

    def setValue(self, address: str, param: str, value: Any) -> None:  # noqa: N802 - xmlrpc style
        self.set_calls.append((address, param, value))


@pytest.fixture(autouse=True)
def reset_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch the ServerProxy used by hmcli to our fake
    monkeypatch.setattr(hmcli, "ServerProxy", FakeServerProxy)
    # Provide deterministic helpers
    monkeypatch.setattr(
        hmcli,
        "build_xml_rpc_uri",
        lambda host, port, path, tls: f"{'https' if tls else 'http'}://{host}:{port}{path or ''}",  # type: ignore[no-any-return]
    )

    def fake_headers(username: str | None, password: str | None) -> dict[str, str]:
        hdrs = {}
        if username is not None:
            hdrs["X-User"] = username
        if password is not None:
            hdrs["X-Pass"] = password
        return hdrs

    monkeypatch.setattr(hmcli, "build_xml_rpc_headers", fake_headers)
    monkeypatch.setattr(hmcli, "get_tls_context", lambda verify_tls: {"verify": verify_tls})  # type: ignore[no-any-return]
    # Reset constructor record
    FakeServerProxy.last_init = None


def run_cli(capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """Invoke hmcli.main(), capturing SystemExit and output."""
    try:
        hmcli.main()
    except SystemExit as ex:  # argparse and our code use sys.exit
        code = int(ex.code)
    else:
        code = 0
    out, err = capsys.readouterr()
    return code, out, err


def base_argv(*args: str) -> list[str]:
    return ["aiohomematic", *list(args)]


class TestHmcliGetValue:
    """Test CLI getValue operations."""

    def test_get_value_json(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.values[("ABC0001:2", "STATE")] = True
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "1.2.3.4", "-p", "2001", "-a", "ABC0001:2", "--parameter", "STATE", "--json")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        data = json.loads(out)
        assert data == {"address": "ABC0001:2", "parameter": "STATE", "value": True}
        assert err == ""

    def test_get_value_plain(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        # Prepare fake to return a value
        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.values[("OEQ1234567:1", "LEVEL")] = 0.42
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)  # factory returning instance

        argv = base_argv("-H", "ccu.local", "-p", "2001", "-a", "OEQ1234567:1", "--parameter", "LEVEL")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert out.strip() == "0.42"
        assert err == ""


class TestHmcliSetValue:
    """Test CLI setValue operations."""

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
        fake = FakeServerProxy("uri", context=None, headers={})

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "ccu", "-p", "2001", "-a", "X:1", "--parameter", "FOO", "--value", raw)
        if typ is not None:
            argv += ["--type", typ]
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert out == ""
        assert err == ""
        assert fake.set_calls == [("X:1", "FOO", parsed)]


class TestHmcliMasterOperations:
    """Test CLI master paramset operations."""

    def test_master_get_plain_and_json(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.paramsets[("DEV:0", hmcli.ParamsetKey.MASTER)] = {"PROFILE": 2}
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        # Plain
        argv = base_argv(
            "-H", "h", "-p", "2001", "-a", "DEV:0", "--paramset_key", hmcli.ParamsetKey.MASTER, "--parameter", "PROFILE"
        )
        monkeypatch.setattr(sys, "argv", argv)
        code, out, err = run_cli(capsys)
        assert code == 0 and out.strip() == "2" and err == ""

        # JSON
        argv = base_argv(
            "-H",
            "h",
            "-p",
            "2001",
            "-a",
            "DEV:0",
            "--paramset_key",
            hmcli.ParamsetKey.MASTER,
            "--parameter",
            "PROFILE",
            "--json",
        )
        monkeypatch.setattr(sys, "argv", argv)
        code, out, err = run_cli(capsys)
        assert code == 0
        data = json.loads(out)
        assert data == {
            "address": "DEV:0",
            "paramset_key": hmcli.ParamsetKey.MASTER,
            "parameter": "PROFILE",
            "value": 2,
        }

    def test_master_put_value(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        fake = FakeServerProxy("uri", context=None, headers={})

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv(
            "-H",
            "h",
            "-p",
            "2001",
            "-a",
            "DEV:0",
            "--paramset_key",
            hmcli.ParamsetKey.MASTER,
            "--parameter",
            "PROFILE",
            "--value",
            "7",
            "--type",
            "int",
        )
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert fake.put_calls == [("DEV:0", hmcli.ParamsetKey.MASTER, {"PROFILE": 7})]


class TestHmcliConnectionSettings:
    """Test CLI connection settings and authentication."""

    def test_tls_and_headers_in_proxy_init(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
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
            "-a",
            "D:1",
            "--parameter",
            "STATE",
        )
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        # Validate constructor args captured; outcome code isn't essential for this test
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
        class Boom(FakeServerProxy):
            def getValue(self, address: str, param: str) -> Any:  # noqa: N802
                raise RuntimeError("boom")

        monkeypatch.setattr(hmcli, "ServerProxy", lambda *a, **k: Boom("uri"))

        argv = base_argv("-H", "h", "-p", "2001", "-a", "A:1", "--parameter", "X")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 1
        assert out == ""
        assert "boom" in err

    def test_missing_required_address(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that missing --address argument causes error."""
        argv = base_argv("-H", "host", "-p", "2001", "--parameter", "X")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 2
        assert "--address" in err or "-a" in err

    def test_missing_required_host(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that missing --host argument causes error."""
        argv = base_argv("-p", "2001", "-a", "A:1", "--parameter", "X")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 2  # argparse exits with 2 for errors
        assert "--host" in err or "-H" in err

    def test_missing_required_parameter(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that missing --parameter argument causes error."""
        argv = base_argv("-H", "host", "-p", "2001", "-a", "A:1")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 2
        assert "--parameter" in err

    def test_missing_required_port(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that missing --port argument causes error."""
        argv = base_argv("-H", "host", "-a", "A:1", "--parameter", "X")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 2
        assert "--port" in err or "-p" in err


class TestHmcliMasterEdgeCases:
    """Test CLI master paramset edge cases."""

    def test_master_get_empty_paramset(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test getting parameter when paramset doesn't exist."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            # No paramsets defined - return empty proxy
            return FakeServerProxy("uri", context=context, headers=headers)

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv(
            "-H", "h", "-p", "2001", "-a", "DEV:0", "--paramset_key", hmcli.ParamsetKey.MASTER, "--parameter", "PROFILE"
        )
        monkeypatch.setattr(sys, "argv", argv)
        code, out, err = run_cli(capsys)
        # Should succeed but output nothing
        assert code == 0
        assert out.strip() == ""

    def test_master_get_missing_parameter(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test getting a parameter that doesn't exist in master paramset."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            # Paramset exists but doesn't have the requested parameter
            fake.paramsets[("DEV:0", hmcli.ParamsetKey.MASTER)] = {"OTHER_PARAM": 5}
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv(
            "-H",
            "h",
            "-p",
            "2001",
            "-a",
            "DEV:0",
            "--paramset_key",
            hmcli.ParamsetKey.MASTER,
            "--parameter",
            "NONEXISTENT",
        )
        monkeypatch.setattr(sys, "argv", argv)
        code, out, err = run_cli(capsys)
        # Should succeed but output nothing (parameter not in paramset)
        assert code == 0
        assert out.strip() == ""


class TestHmcliPathParameter:
    """Test CLI path parameter for heating groups."""

    def test_path_parameter_included_in_uri(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --path is included in the XML-RPC URI."""
        argv = base_argv("-H", "host", "-p", "2001", "--path", "/groups", "-a", "D:1", "--parameter", "STATE")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        init = FakeServerProxy.last_init
        assert init is not None
        assert "/groups" in init["uri"]


class TestHmcliValueTypes:
    """Test CLI value type conversions and edge cases."""

    def test_get_value_complex_type_json(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test getting complex value with JSON output."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.values[("DEV:1", "WEEK_PROFILE")] = {"MONDAY": [6, 22]}
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "ccu", "-p", "2001", "-a", "DEV:1", "--parameter", "WEEK_PROFILE", "--json")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        data = json.loads(out)
        assert data["value"] == {"MONDAY": [6, 22]}

    def test_get_value_none(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test getting value that returns None."""

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            fake = FakeServerProxy("uri", context=context, headers=headers)
            fake.values[("DEV:1", "STATE")] = None
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv("-H", "ccu", "-p", "2001", "-a", "DEV:1", "--parameter", "STATE")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert out.strip() == "None"

    def test_set_bool_zero(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test setting boolean value with 0."""
        fake = FakeServerProxy("uri", context=None, headers={})

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv(
            "-H", "ccu", "-p", "2001", "-a", "X:1", "--parameter", "STATE", "--value", "0", "--type", "bool"
        )
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert fake.set_calls == [("X:1", "STATE", False)]

    def test_set_float_negative(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test setting negative float value."""
        fake = FakeServerProxy("uri", context=None, headers={})

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv(
            "-H", "ccu", "-p", "2001", "-a", "X:1", "--parameter", "TEMP", "--value", "-5.5", "--type", "float"
        )
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert fake.set_calls == [("X:1", "TEMP", -5.5)]

    def test_set_negative_int(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test setting negative integer value."""
        fake = FakeServerProxy("uri", context=None, headers={})

        def construct(_: str, *, context: Any = None, headers: dict[str, str] | None = None) -> FakeServerProxy:
            return fake

        monkeypatch.setattr(hmcli, "ServerProxy", construct)

        argv = base_argv(
            "-H", "ccu", "-p", "2001", "-a", "X:1", "--parameter", "OFFSET", "--value", "-10", "--type", "int"
        )
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        assert code == 0
        assert fake.set_calls == [("X:1", "OFFSET", -10)]


class TestHmcliNoTls:
    """Test CLI without TLS."""

    def test_no_tls_uses_http(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that without --tls flag, HTTP is used."""
        argv = base_argv("-H", "host", "-p", "2001", "-a", "D:1", "--parameter", "STATE")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        init = FakeServerProxy.last_init
        assert init is not None
        assert init["uri"].startswith("http://")
        assert init["context"] is None  # No TLS context

    def test_tls_without_verify(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Test TLS without certificate verification."""
        argv = base_argv("-H", "host", "-p", "2001", "--tls", "-a", "D:1", "--parameter", "STATE")
        monkeypatch.setattr(sys, "argv", argv)

        code, out, err = run_cli(capsys)
        init = FakeServerProxy.last_init
        assert init is not None
        assert init["uri"].startswith("https://")
        assert init["context"] == {"verify": False}  # TLS but no verify
