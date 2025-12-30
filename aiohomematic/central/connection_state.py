# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Connection state tracking for central unit.

This module provides connection status management for the central unit,
tracking issues per transport (JSON-RPC and XML-RPC proxies).
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import TYPE_CHECKING, Final

from aiohomematic.central.events import SystemStatusChangedEvent
from aiohomematic.client import AioJsonRpcAioHttpClient, BaseRpcProxy
from aiohomematic.support import extract_exc_args

if TYPE_CHECKING:
    from aiohomematic.interfaces.central import EventBusProviderProtocol

_LOGGER: Final = logging.getLogger(__name__)

ConnectionProblemIssuer = AioJsonRpcAioHttpClient | BaseRpcProxy


class CentralConnectionState:
    """
    Track connection status for the central unit.

    Manages connection issues per transport (JSON-RPC and XML-RPC proxies),
    publishing SystemStatusChangedEvent via EventBus for state changes.
    """

    def __init__(self, *, event_bus_provider: EventBusProviderProtocol | None = None) -> None:
        """Initialize the CentralConnectionStatus."""
        self._json_issues: Final[list[str]] = []
        self._rpc_proxy_issues: Final[list[str]] = []
        self._event_bus_provider = event_bus_provider

    @property
    def has_any_issue(self) -> bool:
        """Return True if any connection issue exists."""
        return len(self._json_issues) > 0 or len(self._rpc_proxy_issues) > 0

    @property
    def issue_count(self) -> int:
        """Return total number of connection issues."""
        return len(self._json_issues) + len(self._rpc_proxy_issues)

    @property
    def json_issue_count(self) -> int:
        """Return number of JSON-RPC connection issues."""
        return len(self._json_issues)

    @property
    def rpc_proxy_issue_count(self) -> int:
        """Return number of XML-RPC proxy connection issues."""
        return len(self._rpc_proxy_issues)

    def add_issue(self, *, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection and publish event."""
        added = False
        if isinstance(issuer, AioJsonRpcAioHttpClient) and iid not in self._json_issues:
            self._json_issues.append(iid)
            _LOGGER.debug("add_issue: add issue  [%s] for JsonRpcAioHttpClient", iid)
            added = True
        elif isinstance(issuer, BaseRpcProxy) and iid not in self._rpc_proxy_issues:
            self._rpc_proxy_issues.append(iid)
            _LOGGER.debug("add_issue: add issue [%s] for RpcProxy", iid)
            added = True

        if added:
            self._publish_state_change(interface_id=iid, connected=False)
        return added

    def clear_all_issues(self) -> int:
        """
        Clear all tracked connection issues.

        Returns the number of issues cleared.
        """
        if (count := self.issue_count) > 0:
            all_iids = list(self._json_issues) + list(self._rpc_proxy_issues)
            self._json_issues.clear()
            self._rpc_proxy_issues.clear()
            for iid in all_iids:
                self._publish_state_change(interface_id=iid, connected=True)
            return count
        return 0

    def handle_exception_log(
        self,
        *,
        issuer: ConnectionProblemIssuer,
        iid: str,
        exception: Exception,
        logger: logging.Logger = _LOGGER,
        level: int = logging.ERROR,
        extra_msg: str = "",
        multiple_logs: bool = True,
    ) -> None:
        """Handle Exception and derivates logging."""
        exception_name = exception.name if hasattr(exception, "name") else exception.__class__.__name__
        if self.has_issue(issuer=issuer, iid=iid) and multiple_logs is False:
            logger.debug(
                "%s failed: %s [%s] %s",
                iid,
                exception_name,
                extract_exc_args(exc=exception),
                extra_msg,
            )
        else:
            self.add_issue(issuer=issuer, iid=iid)
            logger.log(
                level,
                "%s failed: %s [%s] %s",
                iid,
                exception_name,
                extract_exc_args(exc=exception),
                extra_msg,
            )

    def has_issue(self, *, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Check if issue exists for the given issuer and interface id."""
        if isinstance(issuer, AioJsonRpcAioHttpClient):
            return iid in self._json_issues
        # issuer is BaseRpcProxy (exhaustive union coverage)
        return iid in self._rpc_proxy_issues

    def has_rpc_proxy_issue(self, *, interface_id: str) -> bool:
        """Return True if XML-RPC proxy has a known connection issue for interface_id."""
        return interface_id in self._rpc_proxy_issues

    def remove_issue(self, *, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Remove issue from collection and publish event."""
        removed = False
        if isinstance(issuer, AioJsonRpcAioHttpClient) and iid in self._json_issues:
            self._json_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for JsonRpcAioHttpClient", iid)
            removed = True
        elif isinstance(issuer, BaseRpcProxy) and iid in self._rpc_proxy_issues:
            self._rpc_proxy_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for RpcProxy", iid)
            removed = True

        if removed:
            self._publish_state_change(interface_id=iid, connected=True)
        return removed

    def _publish_state_change(self, *, interface_id: str, connected: bool) -> None:
        """Publish SystemStatusChangedEvent via EventBus."""
        if self._event_bus_provider is None:
            return
        event = SystemStatusChangedEvent(
            timestamp=datetime.now(),
            connection_state=(interface_id, connected),
        )
        self._event_bus_provider.event_bus.publish_sync(event=event)
