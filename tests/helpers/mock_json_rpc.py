"""Lightweight aiohttp-based JSON-RPC mock used in tests."""

from __future__ import annotations

from typing import Any, Final

from aiohttp import web

from aiohomematic.const import PATH_JSON_RPC, UTF_8


class MockJsonRpc:
    """
    Lightweight mock JSON-RPC server for tests.

    It implements a minimal subset used by JsonRpcAioHttpClient during tests:
    - Session.login -> returns a fake session id
    - Session.renew -> returns True
    - Session.logout -> returns True
    - system.listMethods -> returns a list of supported methods (by name)
    - CCU.getAuthEnabled -> returns True
    - CCU.getHttpsRedirectEnabled -> returns False
    - Interface.listInterfaces -> returns a couple of fake interfaces
    - ReGa.runScript -> echoes a minimal structure to satisfy script-based calls
    - A few other methods can be added on demand
    """

    SUPPORTED_METHODS: Final[tuple[str, ...]] = (
        "Session.login",
        "Session.renew",
        "Session.logout",
        "system.listMethods",
        "CCU.getAuthEnabled",
        "CCU.getHttpsRedirectEnabled",
        "Interface.listInterfaces",
        "ReGa.runScript",
    )

    def __init__(self) -> None:
        """Initialize the aiohttp app and defaults for the mock JSON-RPC server."""
        self._app = web.Application()
        self._app.router.add_post(PATH_JSON_RPC, self._handle)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._session_id: str = "sess-1234"

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> str:
        """Start the aiohttp server on a host/port and return the base URL."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=host, port=port)
        await self._site.start()
        # Retrieve bound port
        assert self._runner.addresses
        bound = self._runner.addresses[0]
        if isinstance(bound, tuple):
            h, p = bound[0], bound[1]
        else:
            # aiohttp 3.9 provides sockaddr as tuple as well; keep fallback
            h, p = host, port
        return f"http://{h}:{p}"

    async def stop(self) -> None:
        """Stop and cleanup the aiohttp server runner/site if running."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        payload = await request.json()
        method: str = payload.get("method")
        params: dict[str, Any] = payload.get("params") or {}
        response: dict[str, Any]
        if method == "Session.login":
            # Validate presence of credentials
            if params.get("username") is None:
                response = {"error": {"message": "missing username"}, "result": None}
            else:
                response = {"error": None, "result": self._session_id}
        elif method == "Session.renew" or method == "Session.logout":
            response = {"error": None, "result": True}
        elif method == "system.listMethods":
            response = {
                "error": None,
                "result": [{"name": name} for name in self.SUPPORTED_METHODS],
            }
        elif method == "CCU.getAuthEnabled":
            response = {"error": None, "result": True}
        elif method == "CCU.getHttpsRedirectEnabled":
            response = {"error": None, "result": False}
        elif method == "Interface.listInterfaces":
            response = {
                "error": None,
                "result": [
                    {"name": "BidCos-RF"},
                    {"name": "HmIP-RF"},
                ],
            }
        elif method == "ReGa.runScript":
            # Simulate script responses used by client (e.g., get_serial.fn)
            # Client expects 'result' to be a JSON string which it will parse.
            import orjson

            script: str = params.get("script", "")
            result_obj = {"serial": "ABCDEF123456"} if "get_serial" in script or '{"serial"' in script else {"ok": True}
            response = {"error": None, "result": orjson.dumps(result_obj).decode(UTF_8)}
        else:
            response = {"error": {"message": f"method not implemented: {method}"}, "result": None}

        return web.json_response(response)


async def create_running_mock_json_rpc() -> tuple[MockJsonRpc, str]:
    """Create and start a mock JSON-RPC server."""
    srv = MockJsonRpc()
    base_url = await srv.start()
    return srv, base_url
