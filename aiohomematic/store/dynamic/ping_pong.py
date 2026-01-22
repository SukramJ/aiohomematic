# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Ping/pong tracker for connection health monitoring.

This module provides PingPongTracker which tracks ping/pong timestamps to detect
connection health issues and publishes interface events on mismatch thresholds.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import time
from typing import TYPE_CHECKING, Final

from aiohomematic import i18n
from aiohomematic.central.events import IntegrationIssue, SystemStatusChangedEvent
from aiohomematic.const import (
    PING_PONG_CACHE_MAX_SIZE,
    PING_PONG_MISMATCH_COUNT,
    PING_PONG_MISMATCH_COUNT_TTL,
    IntegrationIssueSeverity,
    IntegrationIssueType,
    PingPongMismatchType,
)
from aiohomematic.interfaces import CentralInfoProtocol, EventBusProviderProtocol, IncidentRecorderProtocol
from aiohomematic.metrics import MetricKeys, emit_latency
from aiohomematic.property_decorators import DelegatedProperty
from aiohomematic.store.types import IncidentSeverity, IncidentType, PingPongJournal, PongTracker

if TYPE_CHECKING:
    from aiohomematic.central import CentralConnectionState

_LOGGER: Final = logging.getLogger(__name__)


class PingPongTracker:
    """Tracker for ping/pong events to monitor connection health."""

    __slots__ = (
        "_allowed_delta",
        "_central_info",
        "_connection_state",
        "_event_bus_provider",
        "_incident_recorder",
        "_interface_id",
        "_journal",
        "_pending",
        "_retry_at",
        "_ttl",
        "_unknown",
    )

    def __init__(
        self,
        *,
        event_bus_provider: EventBusProviderProtocol,
        central_info: CentralInfoProtocol,
        interface_id: str,
        connection_state: CentralConnectionState | None = None,
        incident_recorder: IncidentRecorderProtocol | None = None,
        allowed_delta: int = PING_PONG_MISMATCH_COUNT,
        ttl: int = PING_PONG_MISMATCH_COUNT_TTL,
    ):
        """Initialize the cache with ttl."""
        assert ttl > 0
        self._event_bus_provider: Final = event_bus_provider
        self._central_info: Final = central_info
        self._interface_id: Final = interface_id
        self._connection_state: Final = connection_state
        self._incident_recorder: Final = incident_recorder
        self._allowed_delta: Final = allowed_delta
        self._ttl: Final = ttl
        self._pending: Final = PongTracker(tokens=set(), seen_at={})
        self._unknown: Final = PongTracker(tokens=set(), seen_at={})
        self._retry_at: Final[set[str]] = set()
        self._journal: Final = PingPongJournal()

    allowed_delta: Final = DelegatedProperty[int](path="_allowed_delta")

    @property
    def has_connection_issue(self) -> bool:
        """Return True if there is a known connection issue for this interface."""
        if self._connection_state is None:
            return False
        return self._connection_state.is_rpc_proxy_issue(interface_id=self._interface_id)

    @property
    def journal(self) -> PingPongJournal:
        """Return the diagnostic journal for this tracker."""
        return self._journal

    @property
    def size(self) -> int:
        """Return total size of pending and unknown pong sets."""
        return len(self._pending) + len(self._unknown)

    def clear(self) -> None:
        """Clear the cache and journal."""
        self._pending.clear()
        self._unknown.clear()
        self._journal.clear()

    def handle_received_pong(self, *, pong_token: str) -> None:
        """Handle received pong token."""
        if self._pending.contains(token=pong_token):
            # Calculate round-trip latency and emit metric event
            rtt_ms: float | None = None
            if (send_time := self._pending.seen_at.get(pong_token)) is not None:
                rtt_ms = (time.monotonic() - send_time) * 1000
                emit_latency(
                    event_bus=self._event_bus_provider.event_bus,
                    key=MetricKeys.ping_pong_rtt(interface_id=self._interface_id),
                    duration_ms=rtt_ms,
                )
            # Record successful PONG in journal
            self._journal.record_pong_received(token=pong_token, rtt_ms=rtt_ms or 0.0)
            self._pending.remove(token=pong_token)
            self._cleanup_tracker(tracker=self._pending, tracker_name="pending")
            count = len(self._pending)
            self._check_and_publish_pong_event(mismatch_type=PingPongMismatchType.PENDING)
            _LOGGER.debug(
                "PING PONG CACHE: Reduce pending PING count: %s - %i for token: %s",
                self._interface_id,
                count,
                pong_token,
            )
        else:
            # Record unknown PONG in journal
            self._journal.record_pong_unknown(token=pong_token)
            # Track unknown pong with monotonic insertion time for TTL expiry.
            self._unknown.add(token=pong_token, timestamp=time.monotonic())
            self._cleanup_tracker(tracker=self._unknown, tracker_name="unknown")
            count = len(self._unknown)
            self._check_and_publish_pong_event(mismatch_type=PingPongMismatchType.UNKNOWN)
            _LOGGER.debug(
                "PING PONG CACHE: Increase unknown PONG count: %s - %i for token: %s",
                self._interface_id,
                count,
                pong_token,
            )
            # Schedule a single retry after 15s to try reconciling this PONG with a possible late PING.
            self._schedule_unknown_pong_retry(token=pong_token, delay=15.0)

    def handle_send_ping(self, *, ping_token: str) -> None:
        """Handle send ping token by tracking it as pending and publishing events."""
        # Skip tracking if connection is known to be down - prevents false alarm
        # mismatch events during CCU restart when PINGs cannot be received.
        if self.has_connection_issue:
            _LOGGER.debug(
                "PING PONG CACHE: Skip tracking PING (connection issue): %s - token: %s",
                self._interface_id,
                ping_token,
            )
            return
        # Record PING in journal
        self._journal.record_ping_sent(token=ping_token)
        self._pending.add(token=ping_token, timestamp=time.monotonic())
        self._cleanup_tracker(tracker=self._pending, tracker_name="pending")
        # Throttle event emission to every second ping to avoid spamming callbacks,
        # but always publish when crossing the high threshold.
        count = len(self._pending)
        if (count > self._allowed_delta) or (count % 2 == 0):
            self._check_and_publish_pong_event(mismatch_type=PingPongMismatchType.PENDING)
        _LOGGER.debug(
            "PING PONG CACHE: Increase pending PING count: %s - %i for token: %s",
            self._interface_id,
            count,
            ping_token,
        )

    def _check_and_publish_pong_event(self, *, mismatch_type: PingPongMismatchType) -> None:
        """Publish an event about the pong status."""

        def _publish_event(mismatch_count: int) -> None:
            """Publish event."""
            acceptable = mismatch_count <= self._allowed_delta
            issue = IntegrationIssue(
                issue_type=IntegrationIssueType.PING_PONG_MISMATCH,
                severity=IntegrationIssueSeverity.WARNING if acceptable else IntegrationIssueSeverity.ERROR,
                interface_id=self._interface_id,
                mismatch_type=mismatch_type,
                mismatch_count=mismatch_count,
            )
            self._event_bus_provider.event_bus.publish_sync(
                event=SystemStatusChangedEvent(
                    timestamp=datetime.now(),
                    issues=(issue,),
                )
            )
            _LOGGER.debug(
                "PING PONG CACHE: Emitting event %s for %s with mismatch_count: %i with %i acceptable",
                mismatch_type,
                self._interface_id,
                mismatch_count,
                self._allowed_delta,
            )

        if mismatch_type == PingPongMismatchType.PENDING:
            self._cleanup_tracker(tracker=self._pending, tracker_name="pending")
            if (count := len(self._pending)) > self._allowed_delta:
                # Publish event to inform subscribers about high pending pong count.
                _publish_event(mismatch_count=count)
                if self._pending.logged is False:
                    _LOGGER.warning(
                        i18n.tr(
                            key="log.store.dynamic.pending_pong_mismatch",
                            interface_id=self._interface_id,
                        )
                    )
                    # Record incident for persistent diagnostics
                    self._record_incident_async(
                        incident_type=IncidentType.PING_PONG_MISMATCH_HIGH,
                        severity=IncidentSeverity.ERROR,
                        message=f"Pending PONG count ({count}) exceeded threshold ({self._allowed_delta})",
                        context={"pending_count": count, "threshold": self._allowed_delta},
                    )
                self._pending.logged = True
            # In low state:
            # - If we previously logged a high state, publish a reset event (mismatch=0) exactly once.
            # - Otherwise, throttle emission to every second ping (even counts > 0) to avoid spamming.
            elif self._pending.logged:
                _publish_event(mismatch_count=0)
                self._pending.logged = False
            elif count > 0 and count % 2 == 0:
                _publish_event(mismatch_count=count)
        elif mismatch_type == PingPongMismatchType.UNKNOWN:
            self._cleanup_tracker(tracker=self._unknown, tracker_name="unknown")
            count = len(self._unknown)
            if len(self._unknown) > self._allowed_delta:
                # Publish event to inform subscribers about high unknown pong count.
                _publish_event(mismatch_count=count)
                if self._unknown.logged is False:
                    _LOGGER.warning(
                        i18n.tr(
                            key="log.store.dynamic.unknown_pong_mismatch",
                            interface_id=self._interface_id,
                        )
                    )
                    # Record incident for persistent diagnostics
                    self._record_incident_async(
                        incident_type=IncidentType.PING_PONG_UNKNOWN_HIGH,
                        severity=IncidentSeverity.WARNING,
                        message=f"Unknown PONG count ({count}) exceeded threshold ({self._allowed_delta})",
                        context={"unknown_count": count, "threshold": self._allowed_delta},
                    )
                self._unknown.logged = True
            elif self._unknown.logged:
                # Publish reset event when dropping below threshold after being in high state.
                _publish_event(mismatch_count=0)
                self._unknown.logged = False

    def _cleanup_tracker(self, *, tracker: PongTracker, tracker_name: str) -> None:
        """Clean up expired entries and enforce size limit for a tracker."""
        now = time.monotonic()

        # Remove expired entries
        expired_tokens = [
            token
            for token in list(tracker.tokens)
            if (seen_at := tracker.seen_at.get(token)) is not None and (now - seen_at) > self._ttl
        ]
        for token in expired_tokens:
            tracker.remove(token=token)
            # Record expired PINGs in journal (pending tracker only - these are unanswered PINGs)
            if tracker_name == "pending":
                self._journal.record_pong_expired(token=token)
            _LOGGER.debug(
                "PING PONG CACHE: Removing expired %s PONG: %s - %i for ts: %s",
                tracker_name,
                self._interface_id,
                len(tracker),
                token,
            )

        # Enforce size limit by removing oldest entries
        if len(tracker) > PING_PONG_CACHE_MAX_SIZE:
            sorted_entries = sorted(
                tracker.seen_at.items(),
                key=lambda item: item[1],
            )
            remove_count = len(tracker) - PING_PONG_CACHE_MAX_SIZE
            for token, _ in sorted_entries[:remove_count]:
                tracker.remove(token=token)
            _LOGGER.debug(
                "PING PONG CACHE: Evicted %d oldest %s entries on %s (limit: %d)",
                remove_count,
                tracker_name,
                self._interface_id,
                PING_PONG_CACHE_MAX_SIZE,
            )

    def _record_incident_async(
        self,
        *,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        message: str,
        context: dict[str, int],
    ) -> None:
        """
        Schedule async incident recording via the looper.

        This method fires and forgets the incident recording since we don't want
        to block the sync caller. If no incident_recorder or looper is available,
        the incident is silently skipped.
        """
        if (incident_recorder := self._incident_recorder) is None:
            return

        if (looper := getattr(self._central_info, "looper", None)) is None:
            _LOGGER.debug(
                "PING PONG CACHE: Skip incident recording for %s on %s (no looper)",
                incident_type.value,
                self._interface_id,
            )
            return

        async def _record() -> None:
            try:
                await incident_recorder.record_incident(
                    incident_type=incident_type,
                    severity=severity,
                    message=message,
                    interface_id=self._interface_id,
                    context=context,
                    journal=self._journal,
                )
            except Exception as err:  # pragma: no cover
                _LOGGER.debug(
                    "PING PONG CACHE: Failed to record incident %s on %s: %s",
                    incident_type.value,
                    self._interface_id,
                    err,
                )

        looper.create_task(target=_record, name=f"ppc_incident_{self._interface_id}_{incident_type.value}")

    async def _retry_reconcile_pong(self, *, token: str) -> None:
        """Attempt to reconcile a previously-unknown PONG with a late pending PING."""
        # Always allow another schedule after the retry completes
        try:
            # Cleanup any expired entries first to avoid outdated counts
            self._cleanup_tracker(tracker=self._pending, tracker_name="pending")
            self._cleanup_tracker(tracker=self._unknown, tracker_name="unknown")

            if self._pending.contains(token=token):
                # Remove from pending
                self._pending.remove(token=token)

                # If still marked unknown, clear it
                unknown_before = len(self._unknown)
                if self._unknown.contains(token=token):
                    self._unknown.remove(token=token)

                # Re-publish events to reflect new counts (respecting existing throttling)
                self._check_and_publish_pong_event(mismatch_type=PingPongMismatchType.PENDING)
                if len(self._unknown) != unknown_before:
                    self._check_and_publish_pong_event(mismatch_type=PingPongMismatchType.UNKNOWN)

                _LOGGER.debug(
                    "PING PONG CACHE: Retry reconciled PONG on %s for token: %s (pending now: %i, unknown now: %i)",
                    self._interface_id,
                    token,
                    len(self._pending),
                    len(self._unknown),
                )
            else:
                _LOGGER.debug(
                    "PING PONG CACHE: Retry found no pending PING on %s for token: %s (unknown: %s)",
                    self._interface_id,
                    token,
                    self._unknown.contains(token=token),
                )
        finally:
            self._retry_at.discard(token)

    def _schedule_unknown_pong_retry(self, *, token: str, delay: float) -> None:
        """
        Schedule a one-shot retry to reconcile an unknown PONG after delay seconds.

        If no looper is available on the central (e.g. in unit tests), skip scheduling.
        """
        # Coalesce multiple schedules for the same token
        if token in self._retry_at:
            return
        self._retry_at.add(token)

        if (looper := getattr(self._central_info, "looper", None)) is None:
            # In testing contexts without a looper, we cannot schedule — leave to TTL expiry.
            _LOGGER.debug(
                "PING PONG CACHE: Skip scheduling retry for token %s on %s (no looper)",
                token,
                self._interface_id,
            )
            # Allow a future attempt to schedule if environment changes
            self._retry_at.discard(token)
            return

        async def _retry() -> None:
            try:
                await asyncio.sleep(delay)
                await self._retry_reconcile_pong(token=token)
            except Exception as err:  # pragma: no cover
                _LOGGER.debug(
                    "PING PONG CACHE: Retry task error for token %s on %s: %s",
                    token,
                    self._interface_id,
                    err,
                )
                # Ensure token can be rescheduled if needed
                self._retry_at.discard(token)

        looper.create_task(target=_retry, name=f"ppc_retry_{self._interface_id}_{token}")
