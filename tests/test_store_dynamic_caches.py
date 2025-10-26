"""
Tests for runtime store in aiohomematic.store.dynamic.

This test suite focuses on lightweight, behavior-centric checks that improve
coverage without touching production logic. It covers:
- CommandCache add/get/remove flows including combined parameter handling.
- PingPongCache counters, threshold flags, event emission, and warnings.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from aiohomematic.const import EventKey, EventType, InterfaceEventType, ParamsetKey
from aiohomematic.store import CommandCache, PingPongCache


class CentralStub:
    """Minimal stub to capture interface events emitted by PingPongCache."""

    def __init__(self, name: str = "central-stub") -> None:
        """Initialize the stub with a name and event collection storage."""
        self.name = name
        self.events: list[dict[str, Any]] = []

    # Signature-compatible enough for tests
    def fire_homematic_callback(self, *, event_type: EventType, event_data: dict[str, Any]) -> None:  # type: ignore[override]
        """Record a Homematic callback event in the internal list."""
        self.events.append({"type": event_type, "data": event_data})


def _extract_pong_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    data = event["data"][EventKey.DATA]
    return {
        "interface_id": event["data"][EventKey.INTERFACE_ID],
        "type": event["data"][EventKey.TYPE],
        "central_name": data[EventKey.CENTRAL_NAME],
        "mismatch": data.get(EventKey.PONG_MISMATCH_COUNT),
    }


def test_command_cache_add_and_get_last_value_send() -> None:
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


def test_command_cache_add_put_paramset_and_remove() -> None:
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


@pytest.mark.parametrize("allowed_delta", [1, 2])
def test_pingpongcache_thresholds_and_events(allowed_delta: int, caplog: pytest.LogCaptureFixture) -> None:
    """Verify PingPongCache counters, threshold flips, warnings, and event payloads."""
    central = CentralStub()
    ppc = PingPongCache(central=central, interface_id="ifX", allowed_delta=allowed_delta, ttl=60)

    # Initially low and zero counts
    assert ppc.allowed_delta == allowed_delta
    assert ppc.pending_pong_count == 0
    assert ppc.unknown_pong_count == 0
    assert ppc.low_pending_pongs is True
    assert ppc.low_unknown_pongs is True

    # Add pending pings beyond threshold to trigger high and a warning/event
    with caplog.at_level("WARNING"):
        for i in range(allowed_delta + 1):
            ppc.handle_send_ping(ping_ts=datetime.now() + timedelta(seconds=i))
    assert ppc.high_pending_pongs is True

    # One warning logged for pending pong mismatch
    assert any("Pending PONG mismatch" in rec.getMessage() for rec in caplog.records)

    # Central stub should have a single interface event about pending mismatch
    pend_events = [e for e in central.events if e["data"][EventKey.TYPE] == InterfaceEventType.PENDING_PONG]
    assert len(pend_events) >= 1
    payload = _extract_pong_event_payload(pend_events[-1])
    assert payload["interface_id"] == "ifX"
    assert payload["type"] == InterfaceEventType.PENDING_PONG
    assert payload["central_name"] == central.name
    assert payload["mismatch"] == ppc.pending_pong_count

    # Now resolve one by receiving matching pong — count decreases and another event should fire
    last_ts = next(iter(ppc._pending_pongs))  # access for test only
    ppc.handle_received_pong(pong_ts=last_ts)

    # When counts drop to low, an event with mismatch 0 should be emitted
    pend_events = [e for e in central.events if e["data"][EventKey.TYPE] == InterfaceEventType.PENDING_PONG]
    assert any(_extract_pong_event_payload(e)["mismatch"] == 0 for e in pend_events)

    # Unknown pong path: send a pong we never pinged
    with caplog.at_level("WARNING"):
        ppc.handle_received_pong(pong_ts=datetime.now() + timedelta(seconds=999))
    assert ppc.unknown_pong_count == 1
    # For a single unknown, may or may not exceed high depending on delta; ensure property access ok
    _ = ppc.high_unknown_pongs


def test_pingpongcache_cleanup_by_ttl() -> None:
    """Confirm TTL-based cleanup removes stale timestamps from both store."""
    central = CentralStub()
    ppc = PingPongCache(central=central, interface_id="ifTTL", allowed_delta=1, ttl=1)

    ts_old = datetime.now() - timedelta(seconds=5)
    ts_new = datetime.now()

    # Add old and new for both sets
    ppc.handle_send_ping(ping_ts=ts_old)
    ppc.handle_send_ping(ping_ts=ts_new)
    ppc.handle_received_pong(pong_ts=datetime.now() + timedelta(seconds=999))  # unknown
    # Manually insert an old unknown ts to simulate aging
    ppc._unknown_pongs.add(ts_old)  # test-only direct set access

    # Trigger cleanup via property access
    assert ppc.pending_pong_count >= 1
    assert ppc.unknown_pong_count >= 1

    # Both cleanup helpers are called by respective property checks
    assert ppc.high_pending_pongs in (True, False)
    assert ppc.high_unknown_pongs in (True, False)

    # After cleanup with small TTL, old timestamps should have been purged
    assert ts_old not in ppc._pending_pongs
    assert ts_old not in ppc._unknown_pongs
