"""Integration and unit tests for the JSON-RPC client using the local mock server."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import json
from json import JSONDecodeError
from typing import Any

from aiohttp import ClientConnectorCertificateError, ClientSession, ContentTypeError
from aiohttp.client_exceptions import ClientConnectorError, ClientError
import orjson
import pytest

from aiohomematic import central as hmcu
from aiohomematic.client.json_rpc import AioJsonRpcAioHttpClient, _get_params, _JsonKey, _JsonRpcMethod
from aiohomematic.const import UTF_8, Interface, ParamsetKey, RegaScript
from aiohomematic.exceptions import (
    AuthFailure,
    ClientException,
    InternalBackendException,
    NoConnectionException,
    UnsupportedException,
)
from aiohomematic.support import cleanup_text_from_html_tags


class _FakeResponse:
    """Minimal fake of aiohttp ClientResponse for testing _get_json_reponse and error branches."""

    def __init__(self, status: int, json_value: Any | Exception, read_bytes: bytes | None = None) -> None:
        self.status = status
        self._json_value = json_value
        self._read_bytes = read_bytes or b"{}"

    async def json(self, encoding: str = UTF_8) -> Any:  # noqa: ARG002
        if isinstance(self._json_value, Exception):
            raise self._json_value
        return self._json_value

    async def read(self) -> bytes:
        return self._read_bytes


SUCCESS = '{"HmIP-RF.0001D3C99C3C93%3A0.CONFIG_PENDING":false,\r\n"VirtualDevices.INT0000001%3A1.SET_POINT_TEMPERATURE":4.500000,\r\n"VirtualDevices.INT0000001%3A1.SWITCH_POINT_OCCURED":false,\r\n"VirtualDevices.INT0000001%3A1.VALVE_STATE":4,\r\n"VirtualDevices.INT0000001%3A1.WINDOW_STATE":0,\r\n"HmIP-RF.001F9A49942EC2%3A0.CARRIER_SENSE_LEVEL":10.000000,\r\n"HmIP-RF.0003D7098F5176%3A0.UNREACH":false,\r\n"BidCos-RF.OEQ1860891%3A0.UNREACH":true,\r\n"BidCos-RF.OEQ1860891%3A0.STICKY_UNREACH":true,\r\n"BidCos-RF.OEQ1860891%3A1.INHIBIT":false,\r\n"HmIP-RF.000A570998B3FB%3A0.CONFIG_PENDING":false,\r\n"HmIP-RF.000A570998B3FB%3A0.UPDATE_PENDING":false,\r\n"HmIP-RF.000A5A4991BDDC%3A0.CONFIG_PENDING":false,\r\n"HmIP-RF.000A5A4991BDDC%3A0.UPDATE_PENDING":false,\r\n"BidCos-RF.NEQ1636407%3A1.STATE":0,\r\n"BidCos-RF.NEQ1636407%3A2.STATE":false,\r\n"BidCos-RF.NEQ1636407%3A2.INHIBIT":false,\r\n"CUxD.CUX2800001%3A12.TS":"0"}'
FAILURE = '{"HmIP-RF.0001D3C99C3C93%3A0.CONFIG_PENDING":false,\r\n"VirtualDevices.INT0000001%3A1.SET_POINT_TEMPERATURE":4.500000,\r\n"VirtualDevices.INT0000001%3A1.SWITCH_POINT_OCCURED":false,\r\n"VirtualDevices.INT0000001%3A1.VALVE_STATE":4,\r\n"VirtualDevices.INT0000001%3A1.WINDOW_STATE":0,\r\n"HmIP-RF.001F9A49942EC2%3A0.CARRIER_SENSE_LEVEL":10.000000,\r\n"HmIP-RF.0003D7098F5176%3A0.UNREACH":false,\r\n,\r\n,\r\n"BidCos-RF.OEQ1860891%3A0.UNREACH":true,\r\n"BidCos-RF.OEQ1860891%3A0.STICKY_UNREACH":true,\r\n"BidCos-RF.OEQ1860891%3A1.INHIBIT":false,\r\n"HmIP-RF.000A570998B3FB%3A0.CONFIG_PENDING":false,\r\n"HmIP-RF.000A570998B3FB%3A0.UPDATE_PENDING":false,\r\n"HmIP-RF.000A5A4991BDDC%3A0.CONFIG_PENDING":false,\r\n"HmIP-RF.000A5A4991BDDC%3A0.UPDATE_PENDING":false,\r\n"BidCos-RF.NEQ1636407%3A1.STATE":0,\r\n"BidCos-RF.NEQ1636407%3A2.STATE":false,\r\n"BidCos-RF.NEQ1636407%3A2.INHIBIT":false,\r\n"CUxD.CUX2800001%3A12.TS":"0"}'


def test_convert_to_json_success() -> None:
    """Test if convert to json is successful."""
    assert orjson.loads(SUCCESS)


def test_convert_to_json_fails() -> None:
    """Test if convert to json is successful."""
    with pytest.raises(json.JSONDecodeError):
        orjson.loads(FAILURE)


def test_defect_json() -> None:
    """Check if json with special characters can be parsed."""
    accepted_chars = ("a", "<", ">", "'", "&", "$", "[", "]", "{", "}")
    faulthy_chars = ('"', "\\", "	")
    for sc in accepted_chars:
        json = "{" + '"name": "Text mit Wert ' + sc + '"' + "}"
        assert orjson.loads(json)

    for sc in faulthy_chars:
        json = "{" + '"name": "Text mit Wert ' + sc + '"' + "}"
        with pytest.raises(orjson.JSONDecodeError):
            orjson.loads(json)


@pytest.mark.parametrize(
    (
        "test_tag",
        "expected_result",
    ),
    [
        (" <>", " "),
        ("Test1", "Test1"),
    ],
)
def test_cleanup_html_tags(test_tag: str, expected_result: str) -> None:
    """Test cleanup html tags."""
    assert cleanup_text_from_html_tags(text=test_tag) == expected_result


@pytest.mark.asyncio
async def test_json_rpc_get_system_information(mock_json_rpc_server, aiohttp_session: ClientSession) -> None:
    """Ensure get_system_information returns expected values from the mock JSON-RPC server."""
    (_, base_url) = mock_json_rpc_server
    conn_state = hmcu.CentralConnectionState()

    client = AioJsonRpcAioHttpClient(
        username="user",
        password="pass",
        device_url=base_url,
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    sysinfo = await client.get_system_information()
    # From mock: auth_enabled True, https redirect False, some interfaces
    assert sysinfo.auth_enabled is True
    assert sysinfo.https_redirect_enabled is False
    assert isinstance(sysinfo.available_interfaces, tuple)
    assert set(sysinfo.available_interfaces) == {"BidCos-RF", "HmIP-RF"}

    await client.stop()


@pytest.mark.asyncio
async def test__get_params_variations() -> None:
    """_get_params should include defaults and stringify keys/values properly."""
    # With defaults and extra
    p = _get_params(session_id="abc", extra_params={"x": 1}, use_default_params=True)  # type: ignore[arg-type]
    assert p == {"_session_id_": "abc", "x": "1"}
    # No defaults, only extra
    p = _get_params(session_id=False, extra_params={"y": "z"}, use_default_params=False)  # type: ignore[arg-type]
    assert p == {"y": "z"}


@pytest.mark.asyncio
async def test_login_and_recent_renew_short_circuit(
    mock_json_rpc_server, aiohttp_session: ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_do_renew_login should skip RPC call if refresh is recent; and login should succeed."""
    (_, base_url) = mock_json_rpc_server
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="user",
        password="pass",
        device_url=base_url,
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Perform initial login
    await client._login_or_renew()
    assert client.is_activated is True
    sid = client._session_id
    assert sid

    # Make session look freshly refreshed
    client._last_session_id_refresh = datetime.now()

    # Guard against network call during renew
    called = {"count": 0}

    async def fail_do_post(**kwargs: Any):  # noqa: ANN001
        called["count"] += 1
        raise AssertionError("_do_post should not be called when recently refreshed")

    monkeypatch.setattr(client, "_do_post", fail_do_post)  # type: ignore[attr-defined]

    new_sid = await client._do_renew_login(session_id=sid)  # type: ignore[arg-type]
    assert new_sid == sid
    assert called["count"] == 0

    await client.stop()


@pytest.mark.asyncio
async def test_post_keep_session_false_logs_out(mock_json_rpc_server, aiohttp_session: ClientSession) -> None:
    """_post with keep_session=False should login, perform call, and logout clearing the session."""
    (_, base_url) = mock_json_rpc_server
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="user",
        password="pass",
        device_url=base_url,
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Call a lightweight method and force keep_session=False
    await client._post(method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED, keep_session=False)
    # After call, client should have cleared its session
    assert client.is_activated is False

    await client.stop()


@pytest.mark.asyncio
async def test_post_script_parses_json_and_get_serial(mock_json_rpc_server, aiohttp_session: ClientSession) -> None:
    """_post_script should parse string JSON; _get_serial should return last 10 chars of the serial string."""
    (_, base_url) = mock_json_rpc_server
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="user",
        password="pass",
        device_url=base_url,
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Directly call _post_script with GET_SERIAL name; result should be parsed to dict
    resp = await client._post_script(script_name=RegaScript.GET_SERIAL)
    assert isinstance(resp[_JsonKey.RESULT], dict)

    # _get_serial should extract and shorten to last 10 characters
    serial = await client._get_serial()
    assert serial == "CDEF123456"

    await client.stop()


@pytest.mark.asyncio
async def test_get_supported_methods_and_check_warns(
    mock_json_rpc_server, aiohttp_session: ClientSession, caplog: pytest.LogCaptureFixture
) -> None:
    """_check_supported_methods should warn and return False because mock supports only a subset of methods."""
    (_, base_url) = mock_json_rpc_server
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="user",
        password="pass",
        device_url=base_url,
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    with caplog.at_level("WARNING"):
        ok = await client._check_supported_methods()
    assert ok is False
    assert any("methods not supported" in r.message for r in caplog.records)

    await client.stop()


@pytest.mark.asyncio
async def test__get_json_reponse_valueerror_fallback(
    monkeypatch: pytest.MonkeyPatch, aiohttp_session: ClientSession
) -> None:
    """_get_json_reponse should fall back to reading bytes and orjson when response.json() raises ValueError."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )
    # Fake response returning ValueError on json; read returns valid JSON bytes
    resp = _FakeResponse(status=200, json_value=ValueError("bad json"), read_bytes=b'{"ok": true}')
    parsed = await client._get_json_reponse(response=resp)  # type: ignore[arg-type]
    assert parsed == {"ok": True}


@pytest.mark.asyncio
async def test_record_session_masks_credentials(
    monkeypatch: pytest.MonkeyPatch, aiohttp_session: ClientSession
) -> None:
    """_record_session should mask username and password when recording a login call."""
    conn_state = hmcu.CentralConnectionState()
    recorded: dict[str, Any] = {}

    class Rec:
        active = True

        def add_json_rpc_session(self, *, method: str, params: dict[str, Any], response=None, session_exc=None) -> None:  # noqa: ANN001, D401
            recorded["method"] = method
            recorded["params"] = params
            recorded["response"] = response
            recorded["session_exc"] = session_exc

    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
        session_recorder=Rec(),
    )

    # Emulate recording of a login request
    client._record_session(
        method=_JsonRpcMethod.SESSION_LOGIN,
        params={_JsonKey.USERNAME: "u", _JsonKey.PASSWORD: "p"},
        response={"result": "sess"},
        exc=None,
    )
    assert recorded["method"] == _JsonRpcMethod.SESSION_LOGIN
    assert recorded["params"][_JsonKey.USERNAME] == "********"
    assert recorded["params"][_JsonKey.PASSWORD] == "********"


@pytest.mark.asyncio
async def test_do_post_error_branches(monkeypatch: pytest.MonkeyPatch, aiohttp_session: ClientSession) -> None:
    """_do_post should map various transport and JSON-RPC errors to proper exceptions."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Helper to run _do_post with our patched post returning resp
    async def run_with_response(resp: _FakeResponse):
        async def fake_post(*args, **kwargs):  # noqa: ANN001, ARG001
            return resp

        monkeypatch.setattr(client._client_session, "post", fake_post)
        # Allow any method name; skip supported methods gate
        client._supported_methods = None
        client._url = "http://host/api"  # type: ignore[attr-defined]
        return await client._do_post(session_id="s", method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED)

    # Case 1: 200 with error -> mapped to Client/Auth/Internal depending on message
    err_resp = _FakeResponse(
        status=200, json_value={"error": {"code": 401, "message": "access denied"}, "result": None}
    )
    with pytest.raises(AuthFailure):
        await run_with_response(err_resp)

    # Case 2: non-200 with error -> mapped to InternalBackendException
    err_resp2 = _FakeResponse(
        status=500, json_value={"error": {"code": 500, "message": "internal error"}, "result": None}
    )
    with pytest.raises(InternalBackendException):
        await run_with_response(err_resp2)

    # Case 3: transport errors -> mapped
    class _ConnKey:
        host = "h"
        port = 80
        ssl = False

    async def raise_post(*args, **kwargs):  # noqa: ANN001, ARG001
        raise ClientConnectorError(_ConnKey(), OSError("boom"))

    monkeypatch.setattr(client._client_session, "post", raise_post)
    with pytest.raises(ClientException):
        await client._do_post(session_id="s", method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED)

    # ClientConnectorCertificateError branch with https redirect hint when tls False and ssl True
    class _ConnKeyCert:
        host = "h"
        port = 443
        ssl = True
        is_ssl = True

    async def raise_cert(*args, **kwargs):  # noqa: ANN001, ARG001
        raise ClientConnectorCertificateError(_ConnKeyCert(), OSError("cert"))

    monkeypatch.setattr(client._client_session, "post", raise_cert)
    with pytest.raises(ClientException) as ce:
        await client._do_post(session_id="s", method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED)
    assert "Automatic forwarding to HTTPS" in str(ce.value)

    # ClientError/OSError -> NoConnectionException
    async def raise_client_err(*args, **kwargs):  # noqa: ANN001, ARG001
        raise ClientError("fail")

    monkeypatch.setattr(client._client_session, "post", raise_client_err)
    with pytest.raises(NoConnectionException):
        await client._do_post(session_id="s", method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED)

    # Generic TypeError -> ClientException
    async def raise_type_err(*args, **kwargs):  # noqa: ANN001, ARG001
        raise TypeError("bad type")

    monkeypatch.setattr(client._client_session, "post", raise_type_err)
    with pytest.raises(ClientException):
        await client._do_post(session_id="s", method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED)


@pytest.mark.asyncio
async def test_get_auth_enabled_handles_internal_error(
    mock_json_rpc_server, aiohttp_session: ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_get_auth_enabled should catch InternalBackendException and return True as fallback."""
    (_, base_url) = mock_json_rpc_server
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="user",
        password="pass",
        device_url=base_url,
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    async def raise_internal(*args, **kwargs):  # noqa: ANN001, ARG001
        raise InternalBackendException("internal")

    monkeypatch.setattr(client, "_post", raise_internal)
    assert await client._get_auth_enabled() is True

    await client.stop()


@pytest.mark.asyncio
async def test__get_script_cache_and_missing(aiohttp_session: ClientSession) -> None:
    """_get_script should cache scripts, and _post_script should raise when script missing."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Load an existing script twice to hit cache path
    s1 = await client._get_script(script_name="get_serial.fn")
    s2 = await client._get_script(script_name="get_serial.fn")
    assert isinstance(s1, str) and s1 == s2 and "serial" in s1

    # Non-existing script should make _post_script raise ClientException
    with pytest.raises(ClientException):
        await client._post_script(script_name="does_not_exist.fn")


@pytest.mark.asyncio
async def test__do_login_without_credentials_raises_on_post(aiohttp_session: ClientSession) -> None:
    """_do_login returns None without credentials causing _post to raise ClientException."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="",
        password="",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    with pytest.raises(ClientException):
        await client._post(method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED)


@pytest.mark.asyncio
async def test__do_post_unsupported_method_raises(
    aiohttp_session: ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_do_post should raise UnsupportedException if method not in supported list."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Bypass network; set URL and provide minimal supported methods that exclude our method
    client._url = "http://host/api"  # type: ignore[attr-defined]
    client._supported_methods = (str(_JsonRpcMethod.SESSION_LOGIN),)  # type: ignore[attr-defined]

    with pytest.raises(UnsupportedException):
        await client._do_post(session_id="s", method=_JsonRpcMethod.CCU_GET_AUTH_ENABLED)


@pytest.mark.asyncio
async def test_logout_and__do_logout_paths(aiohttp_session: ClientSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Logout should swallow backend errors; _do_logout should clear session and handle missing session."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # _do_logout with no session just returns
    await client._do_logout(session_id=None)

    # Set a dummy session and make _do_post raise to trigger finally: clear_session
    client._session_id = "s"  # type: ignore[attr-defined]

    async def raise_exc(**kwargs: Any):  # noqa: ANN001
        raise ClientException("fail")

    monkeypatch.setattr(client, "_do_post", raise_exc)
    await client.logout()  # Should not raise
    assert client._session_id is None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_execute_and_program_and_sysvar_methods(
    aiohttp_session: ClientSession, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover execute_program, set_program_state, and set_system_variable branches including HTML stripping for strings and bool/float paths."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Avoid real login and supported methods gate
    client._session_id = "s"  # type: ignore[attr-defined]
    client._supported_methods = None  # type: ignore[attr-defined]

    async def fake_post(
        *,
        method: _JsonRpcMethod,
        extra_params: Mapping[_JsonKey, Any] | None = None,
        use_default_params: bool = True,
        keep_session: bool = True,
    ):  # noqa: ARG001,E501
        return {"result": True, "error": None}

    async def fake_post_script(
        *, script_name: str, extra_params: Mapping[_JsonKey, Any] | None = None, keep_session: bool = True
    ):  # noqa: ARG001,E501
        return {"result": {"ok": True}, "error": None}

    monkeypatch.setattr(client, "_post", fake_post)
    monkeypatch.setattr(client, "_post_script", fake_post_script)

    # execute_program and set_program_state should return True
    assert await client.execute_program(pid="123") is True
    assert await client.set_program_state(pid="123", state=True) is True

    # set_system_variable: bool -> SYSVAR_SET_BOOL path
    assert await client.set_system_variable(legacy_name="X", value=True) is True

    # set_system_variable: float -> SYSVAR_SET_FLOAT path
    assert await client.set_system_variable(legacy_name="X", value=1.23) is True

    # set_system_variable: string with HTML -> triggers cleaning and warning and post_script path
    with caplog.at_level("WARNING"):
        assert await client.set_system_variable(legacy_name="X", value="<b>bad</b>") is True
    assert any("contains html tags" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_device_and_value_and_paramset_methods(
    aiohttp_session: ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover list_devices/_list_interfaces/is_present/get/put paramset/get/set value/get_paramset_description conversions."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Bypass login gate
    client._session_id = "s"  # type: ignore[attr-defined]
    client._supported_methods = None  # type: ignore[attr-defined]

    # Prepare responses by method name
    def resp_for(method: _JsonRpcMethod) -> dict[str, Any]:
        if method == _JsonRpcMethod.INTERFACE_LIST_DEVICES:
            return {
                "result": [
                    {
                        "type": "DEVICE",
                        "address": "abc:1",
                        "paramsets": ["VALUES"],
                        "children": [],
                        "interface": "BidCos-RF",
                    }
                ],
                "error": None,
            }
        if method == _JsonRpcMethod.INTERFACE_LIST_INTERFACES:
            return {"result": [{"name": "BidCos-RF"}, {"name": "HmIP-RF"}], "error": None}
        if method == _JsonRpcMethod.INTERFACE_IS_PRESENT:
            return {"result": True, "error": None}
        if method == _JsonRpcMethod.INTERFACE_GET_DEVICE_DESCRIPTION:
            return {
                "result": {"type": "DEVICE", "address": "abc:1", "paramsets": ["MASTER"], "firmware": "1.0"},
                "error": None,
            }
        if method == _JsonRpcMethod.INTERFACE_GET_PARAMSET:
            return {"result": {"LEVEL": 1}, "error": None}
        if method == _JsonRpcMethod.INTERFACE_PUT_PARAMSET:
            return {"result": True, "error": None}
        if method == _JsonRpcMethod.INTERFACE_GET_VALUE:
            return {"result": 42, "error": None}
        if method == _JsonRpcMethod.INTERFACE_SET_VALUE:
            return {"result": True, "error": None}
        if method == _JsonRpcMethod.INTERFACE_GET_PARAMSET_DESCRIPTION:
            return {
                "result": [
                    {
                        "NAME": "LEVEL",
                        "TYPE": "FLOAT",
                        "DEFAULT": 0,
                        "FLAGS": 1,
                        "ID": 1,
                        "MAX": 1,
                        "MIN": 0,
                        "OPERATIONS": 3,
                        "UNIT": "%",
                    }
                ],
                "error": None,
            }
        if method == _JsonRpcMethod.DEVICE_LIST_ALL_DETAIL:
            return {"result": [{"id": 1}], "error": None}
        if method == _JsonRpcMethod.PROGRAM_GET_ALL:
            return {
                "result": [
                    {
                        "id": "p1",
                        "name": "P",
                        "isActive": True,
                        "isInternal": False,
                        "lastExecuteTime": "2020-01-01T00:00:00",
                    }
                ],
                "error": None,
            }
        if method == _JsonRpcMethod.SYSVAR_GET_ALL:
            return {
                "result": [{"id": 100, "name": "sv", "isInternal": False, "type": "NUMBER", "unit": "", "value": "1"}],
                "error": None,
            }
        if method == _JsonRpcMethod.SYSVAR_GET_VALUE_BY_NAME:
            return {"result": 7, "error": None}
        if method == _JsonRpcMethod.SYSVAR_DELETE_SYSVAR_BY_NAME:
            return {"result": True, "error": None}
        if method == _JsonRpcMethod.CCU_GET_AUTH_ENABLED:
            return {"result": True, "error": None}
        if method == _JsonRpcMethod.CCU_GET_HTTPS_REDIRECT_ENABLED:
            return {"result": False, "error": None}
        if method == _JsonRpcMethod.CHANNEL_HAS_PROGRAM_IDS:
            return {"result": True, "error": None}
        return {"result": None, "error": None}

    async def fake_post(
        *,
        method: _JsonRpcMethod,
        extra_params: Mapping[_JsonKey, Any] | None = None,
        use_default_params: bool = True,
        keep_session: bool = True,
    ):  # noqa: ARG001,E501
        return resp_for(method)

    async def fake_post_script(
        *, script_name: str, extra_params: Mapping[_JsonKey, Any] | None = None, keep_session: bool = True
    ):  # noqa: ARG001,E501
        # FETCH_ALL_DEVICE_DATA returns percent-encoded keys/values to test unquote
        if script_name == RegaScript.FETCH_ALL_DEVICE_DATA:
            return {"result": {"BidCos-RF.OEQ%3A1.STATE": "ON%2FOFF"}, "error": None}
        return {"result": {"LEVEL": 1}, "error": None}

    # Patch
    monkeypatch.setattr(client, "_post", fake_post)
    monkeypatch.setattr(client, "_post_script", fake_post_script)

    # Device listing and description
    devs = await client.list_devices(interface=Interface.BIDCOS_RF)
    assert devs and devs[0]["ADDRESS"] == "abc:1"
    desc = await client.get_device_description(interface=Interface.BIDCOS_RF, address="abc:1")
    assert desc and desc["FIRMWARE"] == "1.0"

    # Interfaces and presence
    ifaces = await client._list_interfaces()
    assert set(ifaces) == {"BidCos-RF", "HmIP-RF"}
    assert await client.is_present(interface=Interface.BIDCOS_RF) is True

    # Paramset get/put and values
    assert await client.get_paramset(
        interface=Interface.BIDCOS_RF, address="abc:1", paramset_key=ParamsetKey.VALUES
    ) == {"LEVEL": 1}
    await client.put_paramset(
        interface=Interface.BIDCOS_RF,
        address="abc:1",
        paramset_key=ParamsetKey.MASTER,
        values=[{"NAME": "X", "VALUE": 1}],
    )
    assert (
        await client.get_value(
            interface=Interface.BIDCOS_RF, address="abc:1", paramset_key=ParamsetKey.VALUES, parameter="LEVEL"
        )
        == 42
    )
    await client.set_value(
        interface=Interface.BIDCOS_RF, address="abc:1", parameter="LEVEL", value_type="FLOAT", value=0.5
    )

    # Paramset description conversion
    pdesc = await client.get_paramset_description(
        interface=Interface.BIDCOS_RF, address="abc:1", paramset_key=ParamsetKey.VALUES
    )
    assert pdesc and pdesc["LEVEL"]["UNIT"] == "%"

    # Device details passthrough
    details = await client.get_device_details()
    assert details and details[0]["id"] == 1

    # Programs and system variables
    # Patch description providers first, then call get_all_programs
    async def fake_prog_desc():
        return {"p1": "desc"}

    monkeypatch.setattr(client, "_get_program_descriptions", fake_prog_desc)
    progs = await client.get_all_programs(markers=())
    assert progs and progs[0].legacy_name == "P"

    # Simplify system variable descriptions to empty and default markers handling by patching helpers
    async def fake_sysvar_desc():
        return {}

    monkeypatch.setattr(client, "_get_system_variable_descriptions", fake_sysvar_desc)

    # System variables list, get, delete
    sysvars = await client.get_all_system_variables(markers=())
    assert isinstance(sysvars, tuple)
    assert await client.get_system_variable(name="sv") == 7
    assert await client.delete_system_variable(name="sv") is True

    # Booleans and misc
    assert await client.has_program_ids(channel_hmid="ch") is True
    assert await client._get_auth_enabled() is True
    assert await client._get_https_redirect_enabled() is False

    # All device data unquoting
    all_data = await client.get_all_device_data(interface=Interface.BIDCOS_RF)
    assert all_data == {"BidCos-RF.OEQ:1.STATE": "ON/OFF"}


@pytest.mark.asyncio
async def test_get_all_device_data_error_paths(aiohttp_session: ClientSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_all_device_data should wrap JSONDecodeError/ContentTypeError in ClientException."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=False,
    )

    # Bypass login/supported
    client._session_id = "s"  # type: ignore[attr-defined]
    client._supported_methods = None  # type: ignore[attr-defined]

    async def raise_json(
        *, script_name: str, extra_params: Mapping[_JsonKey, Any] | None = None, keep_session: bool = True
    ):  # noqa: ARG001,E501
        raise JSONDecodeError("bad", "{}", 0)

    async def raise_ct(
        *, script_name: str, extra_params: Mapping[_JsonKey, Any] | None = None, keep_session: bool = True
    ):  # noqa: ARG001,E501
        raise ContentTypeError(None, None)

    # JSONDecodeError
    monkeypatch.setattr(client, "_post_script", raise_json)
    with pytest.raises(ClientException):
        await client.get_all_device_data(interface=Interface.BIDCOS_RF)

    # ContentTypeError
    monkeypatch.setattr(client, "_post_script", raise_ct)
    with pytest.raises(ClientException):
        await client.get_all_device_data(interface=Interface.BIDCOS_RF)


@pytest.mark.asyncio
async def test_properties_and_supported_methods_error(
    aiohttp_session: ClientSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """url/tls properties return expected values; _get_supported_methods returns empty on exception."""
    conn_state = hmcu.CentralConnectionState()
    client = AioJsonRpcAioHttpClient(
        username="u",
        password="p",
        device_url="http://example",
        connection_state=conn_state,
        client_session=aiohttp_session,
        tls=True,
    )

    # Properties
    assert client.url.endswith("/api/homematic.cgi")
    assert client.tls is True

    # Force _do_post to raise to hit exception return path of _get_supported_methods
    async def raise_ce(**kwargs: Any):  # noqa: ANN001
        raise ClientException("x")

    monkeypatch.setattr(client, "_do_post", raise_ce)
    assert await client._get_supported_methods() == ()
