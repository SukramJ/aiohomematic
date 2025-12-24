# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""Threaded XML-RPC mock server used in tests only."""

from __future__ import annotations

from socketserver import ThreadingMixIn
import threading
from xmlrpc.server import SimpleXMLRPCServer


class _ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    daemon_threads = True


class MockXmlRpcServer:
    """Simple threaded XML-RPC server for tests."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        """Initialize the mock XML-RPC server bound to the given host and port."""
        self._server = _ThreadedXMLRPCServer((host, port), allow_none=True, logRequests=False)
        self._server.register_introspection_functions()
        self._server.register_function(self.ping, "ping")
        self._thread: threading.Thread | None = None

    def ping(self) -> str:
        """Respond with a simple pong string to verify connectivity."""
        return "pong"

    def start(self) -> tuple[str, int]:
        """Start the server in a background thread and return the bound host/port."""

        def _serve() -> None:
            self._server.serve_forever()

        self._thread = threading.Thread(target=_serve, daemon=True)
        self._thread.start()
        host, port = self._server.server_address
        return host, port

    def stop(self) -> None:
        """Stop the server and join the background thread."""
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=1)


def create_running_mock_xml_rpc() -> tuple[MockXmlRpcServer, str]:
    """Create and start a mock XML-RPC server."""
    srv = MockXmlRpcServer()
    host, port = srv.start()
    return srv, f"http://{host}:{port}"
