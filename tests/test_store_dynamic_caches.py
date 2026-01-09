# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Tests for runtime store in aiohomematic.store.dynamic.

This test suite focuses on lightweight, behavior-centric checks that improve
coverage without touching production logic. It covers:
- CommandTracker add/get/remove flows including combined parameter handling.
- PingPongTracker counters, threshold flags, event emission, and warnings.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import time
from typing import Any

from freezegun import freeze_time
import pytest

from aiohomematic.async_support import Looper
from aiohomematic.central.events import EventBus, SystemStatusChangedEvent
from aiohomematic.const import IntegrationIssueSeverity, IntegrationIssueType, ParamsetKey, PingPongMismatchType
from aiohomematic.store.dynamic import CommandTracker, PingPongTracker


def get_ping_pong_info(
    event: SystemStatusChangedEvent,
) -> tuple[str | None, PingPongMismatchType | None, int | None, bool]:
    """
    Extract ping pong mismatch info from SystemStatusChangedEvent.

    Returns (interface_id, mismatch_type, mismatch_count, acceptable).
    """
    if not event.issues:
        return (None, None, None, True)

    for issue in event.issues:
        if issue.issue_type == IntegrationIssueType.PING_PONG_MISMATCH:
            interface_id = issue.interface_id
            mismatch_type = issue.mismatch_type
            mismatch_count = issue.mismatch_count
            acceptable = issue.severity == IntegrationIssueSeverity.WARNING
            return (interface_id, mismatch_type, mismatch_count, acceptable)

    return (None, None, None, True)


class _NoOpTaskScheduler:
    """Task scheduler that does nothing - for sync tests without event loop."""

    def create_task(self, *, target: Any, name: str) -> None:  # noqa: ARG002
        """Ignore task creation in sync tests."""


class _CapturingEventBus(EventBus):
    """EventBus subclass that captures all published events for testing."""

    def __init__(self, *, task_scheduler: Any) -> None:
        super().__init__(task_scheduler=task_scheduler)
        self.captured_events: list[SystemStatusChangedEvent] = []

    def publish_sync(self, *, event: Any) -> None:
        """Capture SystemStatusChangedEvents before publishing."""
        if isinstance(event, SystemStatusChangedEvent):
            self.captured_events.append(event)
        super().publish_sync(event=event)


class CentralStub:
    """Minimal stub to capture interface events published by PingPongTracker."""

    def __init__(self, name: str = "central-stub") -> None:
        """Initialize the stub with a name and event collection storage."""
        self.name = name
        self._event_bus = _CapturingEventBus(task_scheduler=_NoOpTaskScheduler())
        # Properties for protocol compatibility
        self.available = True
        self.model = "Test"

    @property
    def event_bus(self) -> EventBus:
        """Return the event bus."""
        return self._event_bus

    @property
    def events(self) -> list[SystemStatusChangedEvent]:
        """Return captured events."""
        return self._event_bus.captured_events


class CentralWithLooperStub(CentralStub):
    """Central stub that provides a real Looper instance for scheduling tests."""

    def __init__(self, name: str = "central-with-looper") -> None:
        super().__init__(name=name)
        self.looper = Looper()


class TrackingLooper:
    """Test looper to verify coalescing: records task creation without running it."""

    def __init__(self) -> None:
        self.created: list[str] = []

    # Match signature used by PingPongTracker
    def create_task(self, *, target, name: str) -> None:  # type: ignore[no-untyped-def]
        self.created.append(name)


class TestCommandTracker:
    """Test CommandTracker functionality."""

    def test_command_tracker_add_and_get_last_value_send(self) -> None:
        """Validate add/get/remove flows for CommandTracker using set_value path."""
        tracker = CommandTracker(interface_id="if1")

        # Basic set_value path
        dpk_values = tracker.add_set_value(channel_address="OEQ1234:1", parameter="LEVEL", value=0.7)
        assert len(dpk_values) == 1
        (dpk, stored_value) = next(iter(dpk_values))
        assert stored_value == 0.7

        # get_last_value_send returns value while fresh
        assert tracker.get_last_value_send(dpk=dpk, max_age=3600) == 0.7

        # With max_age 0, entry is considered stale and should be removed and return None
        assert tracker.get_last_value_send(dpk=dpk, max_age=0) is None
        # Calling again still returns None (already purged)
        assert tracker.get_last_value_send(dpk=dpk, max_age=3600) is None

    def test_command_tracker_add_put_paramset_and_remove(self) -> None:
        """Ensure add_put_paramset store values and targeted remove purges entries."""
        tracker = CommandTracker(interface_id="if2")

        # Put two parameters
        values = {"LEVEL": 1.0, "ON_TIME": 2}
        dpk_values = tracker.add_put_paramset(
            channel_address="OEQ9999:4", paramset_key=ParamsetKey.VALUES, values=values
        )
        assert len(dpk_values) == 2

        # Pick one DPK to remove (by matching value) — should delete even if not stale
        dpk_to_remove = next(iter(dpk_values))[0]
        tracker.remove_last_value_send(dpk=dpk_to_remove, value=values[dpk_to_remove.parameter], max_age=3600)
        assert tracker.get_last_value_send(dpk=dpk_to_remove, max_age=3600) is None


class TestPingPongTracker:
    """Test PingPongTracker functionality."""

    def test_pingpongcache_cleanup_by_ttl(self) -> None:
        """Confirm TTL-based cleanup removes stale timestamps from both store."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifTTL", allowed_delta=1, ttl=1
        )

        with freeze_time("2020-01-01 12:00:00"):
            ts_old = str(datetime.now() - timedelta(seconds=5))
            ts_new = str(datetime.now())

        # Add old and new for both sets using public methods
        ppc.handle_send_ping(ping_token=ts_old)
        ppc.handle_send_ping(ping_token=ts_new)
        # Make the first pending entry appear old to the monotonic TTL logic
        ppc._pending.seen_at[ts_old] = time.monotonic() - 5  # test-only direct dict access

        # Add an unknown pong to populate the set, then inject an old one and mark it old
        ppc.handle_received_pong(pong_token=str(datetime.now() + timedelta(seconds=999)))  # unknown (fresh)
        ppc._unknown.tokens.add(ts_old)  # test-only direct set access
        ppc._unknown.seen_at[ts_old] = time.monotonic() - 5  # simulate age for TTL expiry

        # Sanity: counts reflect inserts
        assert len(ppc._pending) >= 1
        assert len(ppc._unknown) >= 1

        # Trigger cleanup and verify old tokens are purged while newer remain
        ppc._cleanup_tracker(tracker=ppc._pending, tracker_name="pending")
        ppc._cleanup_tracker(tracker=ppc._unknown, tracker_name="unknown")
        assert ts_old not in ppc._pending.tokens
        assert ts_old not in ppc._unknown.tokens

    def test_pingpongcache_clear_resets_state(self) -> None:
        """Verify that clear() empties counts and prevents spurious events immediately after."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifC", allowed_delta=1, ttl=60
        )

        # Create some state and cause a high pending condition to ensure internal flags may be set
        ppc.handle_send_ping(ping_token=str(datetime.now()))
        ppc.handle_send_ping(ping_token=str(datetime.now() + timedelta(seconds=1)))  # now count=2 (> delta)
        events_before_clear = len(central.events)

        # Clear should reset internal sets and flags
        ppc.clear()
        assert len(ppc._pending) == 0
        assert len(ppc._unknown) == 0

        # After clear, sending a single ping (count=1) should not emit an event (still low and odd count)
        ppc.handle_send_ping(ping_token=str(datetime.now() + timedelta(seconds=2)))
        assert len(central.events) == events_before_clear

    def test_pingpongcache_journal_clear_resets_journal(self) -> None:
        """Verify clear() also clears the Journal."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifClear",
            allowed_delta=10,
            ttl=60,
        )

        # Add some events
        ppc.handle_send_ping(ping_token="ping-1")
        ppc.handle_received_pong(pong_token="ping-1")

        assert len(ppc.journal.get_recent_events(limit=10)) == 2

        # Clear everything
        ppc.clear()

        # Journal should be empty
        assert len(ppc.journal.get_recent_events(limit=10)) == 0
        assert ppc.journal.get_rtt_statistics()["samples"] == 0

    def test_pingpongcache_journal_records_events(self) -> None:
        """
        Verify Journal records PING/PONG events for diagnostics.

        The Journal provides a diagnostic history that can be accessed
        via HA Diagnostics without parsing logs.
        """
        from aiohomematic.store.types import PingPongEventType

        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifJournal",
            allowed_delta=10,
            ttl=60,
        )

        # Send a PING
        ppc.handle_send_ping(ping_token="journal-ping-1")

        # Verify PING_SENT recorded
        journal = ppc.journal
        events = journal.get_recent_events(limit=10)
        assert len(events) == 1
        assert events[0]["type"] == PingPongEventType.PING_SENT.value
        assert "journal-ping-1" in events[0]["token"]

        # Receive matching PONG
        ppc.handle_received_pong(pong_token="journal-ping-1")

        # Verify PONG_RECEIVED recorded with RTT
        events = journal.get_recent_events(limit=10)
        assert len(events) == 2
        assert events[1]["type"] == PingPongEventType.PONG_RECEIVED.value
        assert "rtt_ms" in events[1]

        # Receive unknown PONG
        ppc.handle_received_pong(pong_token="unknown-pong-1")

        # Verify PONG_UNKNOWN recorded
        events = journal.get_recent_events(limit=10)
        assert len(events) == 3
        assert events[2]["type"] == PingPongEventType.PONG_UNKNOWN.value

        # Check RTT statistics
        stats = journal.get_rtt_statistics()
        assert stats["samples"] == 1
        assert stats["avg_ms"] is not None

        # Check success rate
        success_rate = journal.get_success_rate(minutes=5)
        assert success_rate == 1.0  # 1 PING sent, 1 PONG received

        # Check diagnostics output
        diagnostics = journal.get_diagnostics()
        assert diagnostics["total_events"] == 3
        assert "rtt_statistics" in diagnostics
        assert "recent_events" in diagnostics

    def test_pingpongcache_journal_records_expired_pings(self) -> None:
        """
        Verify Journal records PONG_EXPIRED when PINGs time out.

        Expired PINGs (no response within TTL) are valuable diagnostic info.
        """
        from aiohomematic.store.types import PingPongEventType

        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifExpiry",
            allowed_delta=10,
            ttl=5,  # Short TTL
        )

        # Send a PING
        ppc.handle_send_ping(ping_token="expiring-ping")

        # Manually expire it by setting seen_at to the past
        old_time = time.monotonic() - 10  # 10 seconds ago, past TTL
        ppc._pending.seen_at["expiring-ping"] = old_time

        # Trigger cleanup
        ppc._cleanup_tracker(tracker=ppc._pending, tracker_name="pending")

        # Verify PONG_EXPIRED recorded
        journal = ppc.journal
        events = journal.get_recent_events(limit=10)
        assert len(events) == 2  # PING_SENT + PONG_EXPIRED
        assert events[1]["type"] == PingPongEventType.PONG_EXPIRED.value
        assert "expiring-ping" in events[1]["token"]

    def test_pingpongcache_no_incident_without_recorder(self) -> None:
        """Verify no errors when incident_recorder is not provided."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifNoRecorder",
            allowed_delta=1,
            ttl=60,
            # No incident_recorder - should not cause any errors
        )

        # Exceed threshold - should work fine without recorder
        ppc.handle_send_ping(ping_token="ping-1")
        ppc.handle_send_ping(ping_token="ping-2")

        # Just verify it didn't crash and state is correct
        assert len(ppc._pending) == 2

    def test_pingpongcache_ping_not_tracked_when_connection_down(self) -> None:
        """
        Verify PINGs are not tracked when has_connection_issue=True.

        This prevents false mismatch alarms during CCU restart when
        PINGs cannot be received by the backend.
        """

        class ConnectionStateStub:
            """Stub for CentralConnectionState."""

            def __init__(self, *, has_issue: bool = False) -> None:
                self._has_issue = has_issue

            def has_rpc_proxy_issue(self, *, interface_id: str) -> bool:
                return self._has_issue

        central = CentralStub()
        connection_state = ConnectionStateStub(has_issue=True)

        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifConnDown",
            connection_state=connection_state,
            allowed_delta=5,
            ttl=60,
        )

        # Verify has_connection_issue returns True
        assert ppc.has_connection_issue is True

        # Send PINGs - they should NOT be tracked
        ppc.handle_send_ping(ping_token="ping1")
        ppc.handle_send_ping(ping_token="ping2")
        ppc.handle_send_ping(ping_token="ping3")

        # No PINGs should be in pending
        assert len(ppc._pending) == 0

        # No events should be emitted
        assert len(central.events) == 0

    def test_pingpongcache_ping_tracked_when_connection_ok(self) -> None:
        """
        Verify PINGs are tracked normally when has_connection_issue=False.

        Complementary test to ensure normal operation works.
        """

        class ConnectionStateStub:
            """Stub for CentralConnectionState."""

            def __init__(self, *, has_issue: bool = False) -> None:
                self._has_issue = has_issue

            def has_rpc_proxy_issue(self, *, interface_id: str) -> bool:
                return self._has_issue

        central = CentralStub()
        connection_state = ConnectionStateStub(has_issue=False)

        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifConnOk",
            connection_state=connection_state,
            allowed_delta=5,
            ttl=60,
        )

        # Verify has_connection_issue returns False
        assert ppc.has_connection_issue is False

        # Send PINGs - they SHOULD be tracked
        ppc.handle_send_ping(ping_token="ping1")
        ppc.handle_send_ping(ping_token="ping2")

        # PINGs should be in pending
        assert len(ppc._pending) == 2
        assert "ping1" in ppc._pending.tokens
        assert "ping2" in ppc._pending.tokens

    def test_pingpongcache_pong_received_before_await_returns_is_matched(self) -> None:
        """
        Verify PONG arriving before await returns is correctly matched.

        This tests the race condition fix from commit 7661295c:
        Token must be registered BEFORE sending PING, so if PONG arrives
        immediately (before await returns), it's still found in pending.
        """
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifRace", allowed_delta=5, ttl=60
        )

        token = "race-condition-token"

        # Simulate: Token registered (as done BEFORE await proxy.ping())
        ppc.handle_send_ping(ping_token=token)
        assert token in ppc._pending.tokens
        assert len(ppc._pending) == 1

        # Simulate: PONG arrives immediately (before await returns)
        ppc.handle_received_pong(pong_token=token)

        # Token should be matched and removed from pending
        assert token not in ppc._pending.tokens
        assert len(ppc._pending) == 0

        # Token should NOT be in unknown (it was matched)
        assert token not in ppc._unknown.tokens
        assert len(ppc._unknown) == 0

    def test_pingpongcache_publishes_single_reset_event_on_drop_from_high(self) -> None:
        """Ensure exactly one reset event (mismatch=0) is sent when dropping from high to low pending state."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifR", allowed_delta=1, ttl=60
        )

        # Cause high pending (count becomes 2)
        ts1 = str(datetime.now())
        ts2 = str(datetime.now() + timedelta(seconds=1))
        ppc.handle_send_ping(ping_token=ts1)
        ppc.handle_send_ping(ping_token=ts2)

        # Drop to low by acknowledging one pong
        ppc.handle_received_pong(pong_token=ts1)

        # Extract pending events and their mismatch counts
        pend_events = [
            get_ping_pong_info(e)
            for e in central.events
            if get_ping_pong_info(e)[1] == PingPongMismatchType.PENDING.value
        ]
        mismatch_counts = [info[2] for info in pend_events]

        # There must be one event with mismatch 2 (high), and exactly one reset (0)
        assert 2 in mismatch_counts
        assert mismatch_counts.count(0) == 1

        # Reducing further to 0 should not emit another reset event
        ppc.handle_received_pong(pong_token=ts2)
        pend_events_after = [
            get_ping_pong_info(e)
            for e in central.events
            if get_ping_pong_info(e)[1] == PingPongMismatchType.PENDING.value
        ]
        mismatch_counts_after = [info[2] for info in pend_events_after]
        assert mismatch_counts_after.count(0) == 1

    @pytest.mark.asyncio
    async def test_pingpongcache_records_incident_on_threshold_crossing(self) -> None:
        """Verify incident is recorded when pending/unknown thresholds are crossed."""
        from aiohomematic.store import IncidentSeverity, IncidentSnapshot, IncidentType
        from aiohomematic.store.types import PingPongJournal

        # Track incident recordings
        recorded_incidents: list[dict[str, Any]] = []

        class MockIncidentRecorder:
            """Mock incident recorder for testing."""

            async def record_incident(
                self,
                *,
                incident_type: IncidentType,
                severity: IncidentSeverity,
                message: str,
                interface_id: str | None = None,
                context: dict[str, Any] | None = None,
                journal: PingPongJournal | None = None,
            ) -> IncidentSnapshot:
                """Record incident and return a snapshot."""
                recorded_incidents.append(
                    {
                        "type": incident_type,
                        "severity": severity,
                        "message": message,
                        "interface_id": interface_id,
                        "context": context,
                        "has_journal": journal is not None,
                    }
                )
                return IncidentSnapshot(
                    incident_id="test-incident",
                    timestamp_iso="2026-01-02T12:00:00.000",
                    incident_type=incident_type,
                    severity=severity,
                    interface_id=interface_id,
                    message=message,
                    context=context or {},
                    journal_excerpt=[],
                )

        central = CentralWithLooperStub()
        mock_recorder = MockIncidentRecorder()

        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifIncident",
            allowed_delta=1,
            ttl=60,
            incident_recorder=mock_recorder,
        )

        # Exceed pending threshold - should trigger incident
        ppc.handle_send_ping(ping_token="ping-1")
        ppc.handle_send_ping(ping_token="ping-2")  # Now count=2 > delta=1

        # Wait for async task to complete
        await asyncio.sleep(0.1)
        await central.looper.block_till_done()

        # Should have recorded a PING_PONG_MISMATCH_HIGH incident
        mismatch_incidents = [i for i in recorded_incidents if i["type"] == IncidentType.PING_PONG_MISMATCH_HIGH]
        assert len(mismatch_incidents) == 1
        assert mismatch_incidents[0]["severity"] == IncidentSeverity.ERROR
        assert mismatch_incidents[0]["interface_id"] == "ifIncident"
        assert mismatch_incidents[0]["context"]["pending_count"] == 2
        assert mismatch_incidents[0]["has_journal"] is True

        # Clear recorded incidents
        recorded_incidents.clear()

        # Now test unknown threshold
        ppc2 = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifIncident2",
            allowed_delta=1,
            ttl=60,
            incident_recorder=mock_recorder,
        )

        # Send unknown PONGs (no matching PINGs)
        ppc2.handle_received_pong(pong_token="unknown-1")
        ppc2.handle_received_pong(pong_token="unknown-2")  # Now count=2 > delta=1

        # Wait for async task to complete
        await asyncio.sleep(0.1)
        await central.looper.block_till_done()

        # Should have recorded a PING_PONG_UNKNOWN_HIGH incident
        unknown_incidents = [i for i in recorded_incidents if i["type"] == IncidentType.PING_PONG_UNKNOWN_HIGH]
        assert len(unknown_incidents) == 1
        assert unknown_incidents[0]["severity"] == IncidentSeverity.WARNING
        assert unknown_incidents[0]["interface_id"] == "ifIncident2"
        assert unknown_incidents[0]["context"]["unknown_count"] == 2

    def test_pingpongcache_retry_coalesces_single_task(self) -> None:
        """Ensure multiple schedules for the same token are coalesced into a single task creation."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifCoal", allowed_delta=1, ttl=60
        )

        # Inject a tracking looper
        tracker = TrackingLooper()
        central.looper = tracker  # type: ignore[attr-defined]

        token = "tok-coalesce"
        ppc._schedule_unknown_pong_retry(token=token, delay=10)
        ppc._schedule_unknown_pong_retry(token=token, delay=10)

        # Only one task should have been created for this token
        created_for_token = [name for name in tracker.created if token in name]
        assert len(created_for_token) == 1

    @pytest.mark.asyncio
    async def test_pingpongcache_retry_reconciles_with_looper(self) -> None:
        """With a looper, the retry should reconcile an unknown pong with a late pending ping and publish events."""
        central = CentralWithLooperStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifLoop", allowed_delta=5, ttl=60
        )

        token = "tok-retry"
        # Simulate unknown pong state without scheduling the built-in 15s task
        ppc._unknown.tokens.add(token)
        ppc._unknown.seen_at[token] = time.monotonic()

        # Schedule retry with a short delay
        ppc._schedule_unknown_pong_retry(token=token, delay=0.01)
        assert token in ppc._retry_at

        # Before retry fires, a late PING is sent with same token
        ppc.handle_send_ping(ping_token=token)
        assert token in ppc._pending.tokens

        # Allow the retry task to run
        await asyncio.sleep(0.05)
        await central.looper.block_till_done(wait_time=1)

        # After retry, pending should be removed and token cleared from tracking sets
        assert token not in ppc._pending.tokens
        assert token not in ppc._unknown.tokens
        assert token not in ppc._retry_at

        # Event emission is throttled in low state; it is not guaranteed here.
        # Verify that state has been reconciled as expected (no pending/unknown, reschedulable).
        assert len(ppc._pending) == 0
        assert len(ppc._unknown) == 0

    @pytest.mark.asyncio
    async def test_pingpongcache_retry_skips_without_looper(self) -> None:
        """When no looper is available, scheduling a retry should be skipped and token reschedulable."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifNoLoop", allowed_delta=1, ttl=60
        )

        # Ensure token not present initially
        token = "tok-skip"
        assert token not in ppc._retry_at

        # Attempt to schedule a retry; since central has no looper, it should discard and not retain token
        ppc._schedule_unknown_pong_retry(token=token, delay=0.01)
        assert token not in ppc._retry_at

    def test_pingpongcache_size_limit_evicts_oldest_entries(self) -> None:
        """
        Verify entries beyond PING_PONG_CACHE_MAX_SIZE are evicted.

        The oldest entries should be removed when the limit is exceeded.
        """
        from aiohomematic.const import PING_PONG_CACHE_MAX_SIZE

        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifSize",
            allowed_delta=200,  # High threshold to avoid event spam
            ttl=3600,  # Long TTL so nothing expires
        )

        # Add more entries than the limit
        num_entries = PING_PONG_CACHE_MAX_SIZE + 20

        for i in range(num_entries):
            ppc.handle_send_ping(ping_token=f"token_{i:04d}")

        # Should be capped at max size
        assert len(ppc._pending) == PING_PONG_CACHE_MAX_SIZE

        # Oldest entries should be evicted (token_0000 through token_0019)
        for i in range(20):
            assert f"token_{i:04d}" not in ppc._pending.tokens

        # Newest entries should remain
        for i in range(num_entries - PING_PONG_CACHE_MAX_SIZE, num_entries):
            assert f"token_{i:04d}" in ppc._pending.tokens

    def test_pingpongcache_size_limit_evicts_oldest_unknown_entries(self) -> None:
        """
        Verify unknown PONG entries beyond PING_PONG_CACHE_MAX_SIZE are evicted.

        Same as above but for the unknown tracker.
        """
        from aiohomematic.const import PING_PONG_CACHE_MAX_SIZE

        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central,
            central_info=central,
            interface_id="ifSizeUnk",
            allowed_delta=200,  # High threshold to avoid event spam
            ttl=3600,  # Long TTL so nothing expires
        )

        # Add more unknown PONGs than the limit
        num_entries = PING_PONG_CACHE_MAX_SIZE + 20

        for i in range(num_entries):
            ppc.handle_received_pong(pong_token=f"unknown_{i:04d}")

        # Should be capped at max size
        assert len(ppc._unknown) == PING_PONG_CACHE_MAX_SIZE

        # Oldest entries should be evicted
        for i in range(20):
            assert f"unknown_{i:04d}" not in ppc._unknown.tokens

        # Newest entries should remain
        for i in range(num_entries - PING_PONG_CACHE_MAX_SIZE, num_entries):
            assert f"unknown_{i:04d}" in ppc._unknown.tokens

    @pytest.mark.parametrize("allowed_delta", [1, 2])
    def test_pingpongcache_thresholds_and_events(
        self,
        allowed_delta: int,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify PingPongTracker counters, threshold flips, warnings, and event payloads."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifX", allowed_delta=allowed_delta, ttl=60
        )

        # Initially low and zero counts
        assert ppc.allowed_delta == allowed_delta
        assert len(ppc._pending) == 0
        assert len(ppc._unknown) == 0

        # Add pending pings beyond threshold to trigger high and a warning/event
        with caplog.at_level("WARNING"):
            for i in range(allowed_delta + 1):
                ppc.handle_send_ping(ping_token=f"t{i}")
        assert (len(ppc._pending) > ppc.allowed_delta) is True

        # One warning logged for pending pong mismatch (check for i18n key)
        assert any(
            "pending_pong_mismatch" in rec.getMessage() or "Pending PONG mismatch" in rec.getMessage()
            for rec in caplog.records
        )

        # Central stub should have a single interface event about pending mismatch
        pend_events = [
            get_ping_pong_info(e)
            for e in central.events
            if get_ping_pong_info(e)[1] == PingPongMismatchType.PENDING.value
        ]
        assert len(pend_events) >= 1
        last_info = pend_events[-1]
        assert last_info[0] == "ifX"
        assert last_info[1] == PingPongMismatchType.PENDING.value
        assert last_info[3] is False  # acceptable
        assert last_info[2] == len(ppc._pending)

        # Now resolve one by receiving matching pong — count decreases and another event should publish
        last_token = next(iter(ppc._pending.tokens))  # access for test only
        ppc.handle_received_pong(pong_token=last_token)

        # When counts drop to low, an event with mismatch 0 should be published
        pend_events = [
            get_ping_pong_info(e)
            for e in central.events
            if get_ping_pong_info(e)[1] == PingPongMismatchType.PENDING.value
        ]
        assert any(info[2] == 0 for info in pend_events)

        # Unknown pong path: send a pong we never pinged
        with caplog.at_level("WARNING"):
            ppc.handle_received_pong(pong_token="u999")
        assert len(ppc._unknown) == 1
        # For a single unknown, may or may not exceed high depending on delta; ensure property access ok
        _ = len(ppc._pending) > ppc.allowed_delta

    def test_pingpongcache_throttles_low_state_pending_events(self) -> None:
        """Confirm that in low state, PENDING_PONG events are published only on even counts (2, 4, ...)."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifT", allowed_delta=10, ttl=60
        )

        # Stay in low state and send 5 pings
        for i in range(1, 6):
            ppc.handle_send_ping(ping_token=str(datetime.now() + timedelta(seconds=i)))

        pend_events = [
            get_ping_pong_info(e)
            for e in central.events
            if get_ping_pong_info(e)[1] == PingPongMismatchType.PENDING.value
        ]
        # Extract the mismatch counts for these events
        counts = [info[2] for info in pend_events]
        # Expect events only for even counts up to 4
        assert counts == [2, 4]

    def test_pingpongcache_unknown_pong_publishes_reset_event_on_drop_from_high(self) -> None:
        """Ensure a reset event (mismatch_count=0) is published when unknown pong count drops below threshold."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifUR", allowed_delta=1, ttl=5
        )

        # Add two unknown pongs to exceed allowed_delta=1 (puts us in "high" state)
        ts1 = str(datetime.now() + timedelta(seconds=1000))
        ts2 = str(datetime.now() + timedelta(seconds=1001))
        ppc.handle_received_pong(pong_token=ts1)
        ppc.handle_received_pong(pong_token=ts2)

        # Verify we're in high state
        assert ppc._unknown.logged is True

        # Simulate TTL expiry by manipulating the seen_at timestamps
        # Set timestamps to be older than TTL (5 seconds ago)
        old_time = time.monotonic() - 10  # 10 seconds ago, well past TTL of 5
        ppc._unknown.seen_at[ts1] = old_time
        ppc._unknown.seen_at[ts2] = old_time

        # Trigger cleanup by calling _check_and_publish_pong_event
        # (this happens internally when new pongs arrive or during normal operation)
        ppc._check_and_publish_pong_event(mismatch_type=PingPongMismatchType.UNKNOWN)

        # Now we should be in low state and a reset event should have been published
        assert ppc._unknown.logged is False

        # Extract unknown events and their mismatch counts
        unk_events = [
            get_ping_pong_info(e)
            for e in central.events
            if get_ping_pong_info(e)[1] == PingPongMismatchType.UNKNOWN.value
        ]
        mismatch_counts = [info[2] for info in unk_events]

        # There must be one event with mismatch 2 (high), and exactly one reset (0)
        assert 2 in mismatch_counts
        assert mismatch_counts.count(0) == 1

    def test_pingpongcache_unknown_pong_warning_and_event(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Ensure high unknown pongs trigger a warning and an interface event with correct payload."""
        central = CentralStub()
        ppc = PingPongTracker(
            event_bus_provider=central, central_info=central, interface_id="ifU", allowed_delta=1, ttl=60
        )

        # Add two unknown pongs to exceed allowed_delta
        with caplog.at_level("WARNING"):
            ppc.handle_received_pong(pong_token=str(datetime.now() + timedelta(seconds=1000)))
            ppc.handle_received_pong(pong_token=str(datetime.now() + timedelta(seconds=1001)))

        # Warning should be logged (check for i18n key)
        assert any(
            "unknown_pong_mismatch" in rec.getMessage() or "Unknown PONG Mismatch" in rec.getMessage()
            for rec in caplog.records
        )

        # An UNKNOWN_PONG interface event should have been published
        unk_events = [
            get_ping_pong_info(e)
            for e in central.events
            if get_ping_pong_info(e)[1] == PingPongMismatchType.UNKNOWN.value
        ]
        assert len(unk_events) >= 1
        last_info = unk_events[-1]
        assert last_info[0] == "ifU"
        assert last_info[1] == PingPongMismatchType.UNKNOWN.value
        assert last_info[3] is False  # acceptable
        assert last_info[2] == len(ppc._unknown)
