# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Tests for runtime store in aiohomematic.store.dynamic.

This test suite focuses on lightweight, behavior-centric checks that improve
coverage without touching production logic. It covers:
- CommandCache add/get/remove flows including combined parameter handling.
- PingPongCache counters, threshold flags, event emission, and warnings.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import time
from typing import Any

from freezegun import freeze_time
import pytest

from aiohomematic.async_support import Looper
from aiohomematic.central.event_bus import EventBus
from aiohomematic.central.integration_events import SystemStatusEvent
from aiohomematic.const import ParamsetKey, PingPongMismatchType
from aiohomematic.store import CommandCache, PingPongCache


def get_ping_pong_info(event: SystemStatusEvent) -> tuple[str | None, str | None, int | None, bool]:
    """
    Extract ping pong mismatch info from SystemStatusEvent.

    Returns (interface_id, mismatch_type, mismatch_count, acceptable).
    """
    if not event.issues:
        return (None, None, None, True)

    for issue in event.issues:
        if issue.issue_id.startswith("ping_pong_mismatch_"):
            placeholders = dict(issue.translation_placeholders)
            interface_id = placeholders.get("interface_id")
            mismatch_type = placeholders.get("mismatch_type")
            mismatch_count = int(placeholders.get("mismatch_count", "0"))
            acceptable = issue.severity == "warning"
            return (interface_id, mismatch_type, mismatch_count, acceptable)

    return (None, None, None, True)


class _CapturingEventBus(EventBus):
    """EventBus subclass that captures all published events for testing."""

    def __init__(self) -> None:
        super().__init__()
        self.captured_events: list[SystemStatusEvent] = []

    def publish_sync(self, *, event: Any) -> None:
        """Capture SystemStatusEvents before publishing."""
        if isinstance(event, SystemStatusEvent):
            self.captured_events.append(event)
        super().publish_sync(event=event)


class CentralStub:
    """Minimal stub to capture interface events published by PingPongCache."""

    def __init__(self, name: str = "central-stub") -> None:
        """Initialize the stub with a name and event collection storage."""
        self.name = name
        self._event_bus = _CapturingEventBus()
        # Properties for protocol compatibility
        self.available = True
        self.model = "Test"

    @property
    def event_bus(self) -> EventBus:
        """Return the event bus."""
        return self._event_bus

    @property
    def events(self) -> list[SystemStatusEvent]:
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

    # Match signature used by PingPongCache
    def create_task(self, *, target, name: str) -> None:  # type: ignore[no-untyped-def]
        self.created.append(name)


class TestCommandCache:
    """Test CommandCache functionality."""

    def test_command_cache_add_and_get_last_value_send(self) -> None:
        """Validate add/get/remove flows for CommandCache using set_value path."""
        cache = CommandCache(interface_id="if1")

        # Basic set_value path
        dpk_values = cache.add_set_value(channel_address="OEQ1234:1", parameter="LEVEL", value=0.7)
        assert len(dpk_values) == 1
        (dpk, stored_value) = next(iter(dpk_values))
        assert stored_value == 0.7

        # get_last_value_send returns value while fresh
        assert cache.get_last_value_send(dpk=dpk, max_age=3600) == 0.7

        # With max_age 0, entry is considered stale and should be removed and return None
        assert cache.get_last_value_send(dpk=dpk, max_age=0) is None
        # Calling again still returns None (already purged)
        assert cache.get_last_value_send(dpk=dpk, max_age=3600) is None

    def test_command_cache_add_put_paramset_and_remove(self) -> None:
        """Ensure add_put_paramset store values and targeted remove purges entries."""
        cache = CommandCache(interface_id="if2")

        # Put two parameters
        values = {"LEVEL": 1.0, "ON_TIME": 2}
        dpk_values = cache.add_put_paramset(channel_address="OEQ9999:4", paramset_key=ParamsetKey.VALUES, values=values)
        assert len(dpk_values) == 2

        # Pick one DPK to remove (by matching value) — should delete even if not stale
        dpk_to_remove = next(iter(dpk_values))[0]
        cache.remove_last_value_send(dpk=dpk_to_remove, value=values[dpk_to_remove.parameter], max_age=3600)
        assert cache.get_last_value_send(dpk=dpk_to_remove, max_age=3600) is None


class TestPingPongCache:
    """Test PingPongCache functionality."""

    def test_pingpongcache_cleanup_by_ttl(self) -> None:
        """Confirm TTL-based cleanup removes stale timestamps from both store."""
        central = CentralStub()
        ppc = PingPongCache(
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
        ppc = PingPongCache(
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

    def test_pingpongcache_publishes_single_reset_event_on_drop_from_high(self) -> None:
        """Ensure exactly one reset event (mismatch=0) is sent when dropping from high to low pending state."""
        central = CentralStub()
        ppc = PingPongCache(
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

    def test_pingpongcache_retry_coalesces_single_task(self) -> None:
        """Ensure multiple schedules for the same token are coalesced into a single task creation."""
        central = CentralStub()
        ppc = PingPongCache(
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
        ppc = PingPongCache(
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
        ppc = PingPongCache(
            event_bus_provider=central, central_info=central, interface_id="ifNoLoop", allowed_delta=1, ttl=60
        )

        # Ensure token not present initially
        token = "tok-skip"
        assert token not in ppc._retry_at

        # Attempt to schedule a retry; since central has no looper, it should discard and not retain token
        ppc._schedule_unknown_pong_retry(token=token, delay=0.01)
        assert token not in ppc._retry_at

    @pytest.mark.parametrize("allowed_delta", [1, 2])
    def test_pingpongcache_thresholds_and_events(
        self,
        allowed_delta: int,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify PingPongCache counters, threshold flips, warnings, and event payloads."""
        central = CentralStub()
        ppc = PingPongCache(
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
        ppc = PingPongCache(
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

    def test_pingpongcache_unknown_pong_warning_and_event(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Ensure high unknown pongs trigger a warning and an interface event with correct payload."""
        central = CentralStub()
        ppc = PingPongCache(
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
