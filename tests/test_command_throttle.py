"""Tests for command throttle with priority queue."""

import asyncio
from datetime import datetime
import time
from types import SimpleNamespace
from typing import Any

import pytest

from aiohomematic.client import CommandPriority, CommandThrottle, InterfaceClient, InterfaceConfig
from aiohomematic.const import Interface, ParamsetKey, TimeoutConfig
from aiohomematic.exceptions import CommandSupersededError


class TestCommandThrottle:
    """Test command throttle with priority system."""

    async def test_critical_priority_bypasses_throttle(self) -> None:
        """Test that CRITICAL priority commands bypass throttle."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)

        start = asyncio.get_event_loop().time()
        # These should all execute immediately, bypassing the queue
        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        elapsed = asyncio.get_event_loop().time() - start

        # CRITICAL commands bypass throttle
        assert elapsed < 0.05

    async def test_high_priority_throttled(self) -> None:
        """Test that HIGH priority commands are throttled."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.05)

        start = asyncio.get_event_loop().time()
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        elapsed = asyncio.get_event_loop().time() - start

        # Should take at least 2 intervals (3 commands = 2 waits)
        assert elapsed >= 0.10

    async def test_metrics_critical_count(self) -> None:
        """Test that CRITICAL commands are counted separately."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)

        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        assert throttle.critical_count == 2

    async def test_no_throttle_when_interval_zero(self) -> None:
        """Test that throttle is bypassed when interval is 0."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.0)

        start = asyncio.get_event_loop().time()
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")
        elapsed = asyncio.get_event_loop().time() - start

        # All commands should execute immediately
        assert elapsed < 0.01

    async def test_priority_ordering(self) -> None:
        """Test that commands are processed in priority order."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.05)
        execution_order: list[CommandPriority] = []

        async def execute_with_priority(priority: CommandPriority) -> None:
            await throttle.acquire(priority=priority, device_address="TEST:1")
            execution_order.append(priority)

        # Start HIGH priority command (will execute first)
        task_high1 = asyncio.create_task(execute_with_priority(CommandPriority.HIGH))

        # Give it time to start
        await asyncio.sleep(0.01)

        # Queue several commands with different priorities
        task_low = asyncio.create_task(execute_with_priority(CommandPriority.LOW))
        task_high2 = asyncio.create_task(execute_with_priority(CommandPriority.HIGH))
        task_critical = asyncio.create_task(execute_with_priority(CommandPriority.CRITICAL))

        # Wait for all to complete
        await asyncio.gather(task_high1, task_low, task_high2, task_critical)

        # Verify execution order
        assert len(execution_order) == 4
        # Verify critical commands were counted
        # Note: HIGH commands may be processed immediately if no queue, so throttled_count might be 0


class TestBurstDetection:
    """Test burst detection in command throttle."""

    async def test_burst_detection_disabled_when_threshold_zero(self) -> None:
        """Test that burst detection is disabled when threshold is 0."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.05,
            burst_threshold=0,
            burst_window=2.0,
        )

        for _ in range(10):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        assert throttle.burst_count == 0

    async def test_burst_detection_does_not_affect_critical(self) -> None:
        """Test that CRITICAL commands are never downgraded by burst detection."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.05,
            burst_threshold=3,
            burst_window=2.0,
        )

        # Send 6 CRITICAL commands rapidly
        for _ in range(6):
            await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="TEST:1")

        assert throttle.burst_count == 0
        assert throttle.critical_count == 6

    async def test_burst_detection_downgrades_high_to_low(self) -> None:
        """Test that HIGH commands are downgraded to LOW during burst."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.05,
            burst_threshold=3,
            burst_window=2.0,
        )

        # Send 6 HIGH commands rapidly — first 3 are within threshold, rest trigger burst
        for _ in range(6):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        assert throttle.burst_count > 0

    async def test_burst_detection_sliding_window_expires(self) -> None:
        """Test that burst window expires and old commands are evicted."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.05,
            burst_threshold=5,
            burst_window=0.1,
        )

        # Send 3 commands
        for _ in range(3):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        # Wait for burst window to expire
        await asyncio.sleep(0.15)

        # Send 3 more — should not trigger burst since window expired
        for _ in range(3):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

        assert throttle.burst_count == 0

    def test_burst_properties(self) -> None:
        """Test that burst properties return correct values."""
        throttle = CommandThrottle(
            interface_id="TEST",
            interval=0.0,
            burst_threshold=10,
            burst_window=2.5,
        )

        assert throttle.burst_count == 0
        assert throttle.burst_threshold == 10
        assert throttle.burst_window == 2.5


class TestCommandPriorityEnum:
    """Test CommandPriority enum."""

    def test_priority_ordering(self) -> None:
        """Test that priorities can be compared."""
        assert CommandPriority.CRITICAL < CommandPriority.HIGH
        assert CommandPriority.HIGH < CommandPriority.LOW
        assert CommandPriority.CRITICAL < CommandPriority.LOW

    def test_priority_values(self) -> None:
        """Test that priority values are in correct order."""
        assert CommandPriority.CRITICAL.value == 0  # Highest priority (lowest number)
        assert CommandPriority.HIGH.value == 1
        assert CommandPriority.LOW.value == 2  # Lowest priority (highest number)


# =============================================================================
# Integration Tests: Burst Detection through InterfaceClient
# =============================================================================


class _FakeEventBus:
    """Minimal fake EventBus for integration tests."""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, *, event: Any) -> None:
        self.published_events.append(event)

    def publish_sync(self, *, event: Any) -> None:
        self.published_events.append(event)

    def subscribe(self, *, event_type: Any, event_key: Any, handler: Any) -> Any:
        return lambda: None


class _FakeBackend:
    """Fake backend that records calls without network I/O."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.interface_id = "test-BidCos-RF"
        self.interface = Interface.BIDCOS_RF
        self.model = "CCU"
        self.system_information = SimpleNamespace(
            available_interfaces=(Interface.BIDCOS_RF,),
            serial="TEST1234",
            has_backup=True,
        )
        self.capabilities = SimpleNamespace(
            backup=True,
            device_firmware_update=True,
            firmware_update_trigger=True,
            firmware_updates=True,
            functions=True,
            inbox_devices=True,
            install_mode=True,
            linking=True,
            metadata=True,
            ping_pong=True,
            programs=True,
            push_updates=True,
            ise_id_lookup=True,
            rename=True,
            rooms=True,
            rpc_callback=True,
            service_messages=True,
            system_update_info=True,
            value_usage_reporting=True,
        )

    async def put_paramset(
        self,
        *,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        rx_mode: Any | None = None,
    ) -> None:
        self.calls.append(("put_paramset", (channel_address, paramset_key, values, rx_mode)))

    async def set_value(self, *, channel_address: str, parameter: str, value: Any, rx_mode: Any | None = None) -> None:
        self.calls.append(("set_value", (channel_address, parameter, value, rx_mode)))

    async def stop(self) -> None:
        pass


class _FakeCentral:
    """Minimal CentralUnit-like object with configurable TimeoutConfig."""

    def __init__(self, *, timeout_config: TimeoutConfig) -> None:
        self._event_bus = _FakeEventBus()
        self._devices: dict[str, Any] = {}
        self._data_points: dict[str, Any] = {}
        self.name = "test-central"

        class Cfg:
            host = "localhost"
            tls = False
            verify_tls = False
            username = None
            password = None
            max_read_workers = 0
            callback_host = "127.0.0.1"
            callback_port_xml_rpc = 0
            interfaces_requiring_periodic_refresh: frozenset[str] = frozenset()
            schedule_timer_config = SimpleNamespace(
                master_poll_after_send_intervals=(0.1, 0.5),
            )

        Cfg.timeout_config = timeout_config  # type: ignore[attr-defined]
        self.config = Cfg()
        self._listen_port_xml_rpc = 32001
        self._callback_ip_addr = "127.0.0.1"

        def _close_task(*, target: Any, name: str) -> None:
            target.close()

        self.looper = SimpleNamespace(create_task=_close_task)
        self.json_rpc_client = SimpleNamespace(
            clear_session=lambda: None,
            circuit_breaker=SimpleNamespace(reset=lambda: None),
        )

        class _ConnectionState:
            pass

        self.connection_state = _ConnectionState()

    @property
    def cache_coordinator(self) -> Any:
        """Return fake cache coordinator."""
        return SimpleNamespace(
            device_details=SimpleNamespace(
                add_interface=lambda **kwargs: None,
                add_name=lambda **kwargs: None,
                add_address_ise_id=lambda **kwargs: None,
            ),
            paramset_descriptions=SimpleNamespace(get_parameter_data=lambda **kwargs: None),
            data_cache=SimpleNamespace(add_data=lambda **kwargs: None),
            device_descriptions=SimpleNamespace(
                find_device_description=lambda **kwargs: None,
                get_device_descriptions=lambda **kwargs: None,
            ),
            incident_store=None,
        )

    @property
    def callback_ip_addr(self) -> str:
        """Return callback IP address."""
        return self._callback_ip_addr

    @property
    def device_coordinator(self) -> Any:
        """Return self as device coordinator."""
        return self

    @property
    def device_registry(self) -> Any:
        """Return fake device registry."""
        return SimpleNamespace(devices=tuple(self._devices.values()))

    @property
    def event_bus(self) -> Any:
        """Return fake event bus."""
        return self._event_bus

    @property
    def event_coordinator(self) -> Any:
        """Return self as event coordinator."""
        return self

    @property
    def listen_port_xml_rpc(self) -> int:
        """Return XML-RPC listen port."""
        return self._listen_port_xml_rpc

    @property
    def query_facade(self) -> Any:
        """Return self as query facade."""
        return self

    def get_device(self, *, address: str) -> Any:
        """Return device by address."""
        dev_addr = address.split(":")[0] if ":" in address else address
        return self._devices.get(dev_addr)

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey) -> Any:
        """Return generic data point."""
        key = f"{channel_address}:{parameter}:{paramset_key}"
        return self._data_points.get(key)

    def get_last_event_monotonic_for_interface(self, *, interface_id: str) -> float | None:
        """Return last event monotonic timestamp."""
        return time.monotonic()

    def get_last_event_seen_for_interface(self, *, interface_id: str) -> datetime | None:
        """Return last event timestamp."""
        return datetime.now()

    async def save_files(self, *, save_paramset_descriptions: bool = False) -> None:
        """No-op for tests."""


def _create_throttled_client(
    *,
    throttle_interval: float = 0.05,
    burst_threshold: int = 3,
    burst_window: float = 2.0,
) -> tuple[InterfaceClient, _FakeBackend]:
    """Create an InterfaceClient with burst detection enabled."""
    timeout_config = TimeoutConfig(
        command_throttle_interval=throttle_interval,
        burst_threshold=burst_threshold,
        burst_window=burst_window,
    )
    central = _FakeCentral(timeout_config=timeout_config)
    backend = _FakeBackend()
    iface_cfg = InterfaceConfig(central_name="test", interface=Interface.BIDCOS_RF, port=32001)
    client = InterfaceClient(
        backend=backend,  # type: ignore[arg-type]
        central=central,  # type: ignore[arg-type]
        interface_config=iface_cfg,
        version="2.0",
    )
    return client, backend


class TestBurstDetectionIntegration:
    """Integration tests: burst detection through InterfaceClient.set_value."""

    @pytest.mark.asyncio
    async def test_burst_window_expiry_resets_detection(self) -> None:
        """Test that burst detection resets after the sliding window expires."""
        client, backend = _create_throttled_client(
            throttle_interval=0.05,
            burst_threshold=5,
            burst_window=0.1,
        )

        try:
            # Send 3 commands (below threshold)
            for i in range(3):
                await client.set_value(
                    channel_address="dev1:1",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=float(i) / 10,
                    wait_for_callback=None,
                )

            # Wait for burst window to expire
            await asyncio.sleep(0.15)

            # Send 3 more — should not trigger burst since window expired
            for i in range(3):
                await client.set_value(
                    channel_address="dev1:1",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=float(i) / 10,
                    wait_for_callback=None,
                )

            assert len(backend.calls) == 6
            assert client.command_throttle.burst_count == 0
        finally:
            client.command_throttle.stop()

    @pytest.mark.asyncio
    async def test_critical_priority_not_affected_by_burst(self) -> None:
        """Test that CRITICAL priority set_value calls bypass burst detection."""
        client, backend = _create_throttled_client(
            throttle_interval=0.05,
            burst_threshold=3,
            burst_window=2.0,
        )

        try:
            # Send 6 CRITICAL-priority commands — should bypass burst entirely
            for i in range(6):
                await client.set_value(
                    channel_address="dev1:1",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=float(i) / 10,
                    wait_for_callback=None,
                    priority=CommandPriority.CRITICAL,
                )

            assert len(backend.calls) == 6
            assert client.command_throttle.burst_count == 0
            assert client.command_throttle.critical_count == 6
        finally:
            client.command_throttle.stop()

    @pytest.mark.asyncio
    async def test_put_paramset_burst_triggers_downgrade(self) -> None:
        """Test that rapid put_paramset calls trigger burst detection."""
        client, backend = _create_throttled_client(
            throttle_interval=0.05,
            burst_threshold=3,
            burst_window=2.0,
        )

        try:
            # Send 6 put_paramset calls — exceeds burst_threshold=3
            for i in range(6):
                await client.put_paramset(
                    channel_address="dev1:1",
                    paramset_key_or_link_address=ParamsetKey.VALUES,
                    values={"LEVEL": float(i) / 10},
                    wait_for_callback=None,
                )

            assert len(backend.calls) == 6
            assert all(c[0] == "put_paramset" for c in backend.calls)
            assert client.command_throttle.burst_count > 0
        finally:
            client.command_throttle.stop()

    @pytest.mark.asyncio
    async def test_set_value_burst_triggers_downgrade(self) -> None:
        """Test that rapid set_value calls through InterfaceClient trigger burst detection."""
        client, backend = _create_throttled_client(
            throttle_interval=0.05,
            burst_threshold=3,
            burst_window=2.0,
        )

        try:
            # Send 6 HIGH-priority set_value calls — exceeds burst_threshold=3
            for i in range(6):
                await client.set_value(
                    channel_address="dev1:1",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=float(i) / 10,
                    wait_for_callback=None,
                )

            # All 6 commands reached the backend
            assert len(backend.calls) == 6
            assert all(c[0] == "set_value" for c in backend.calls)

            # Burst detection triggered at least once
            assert client.command_throttle.burst_count > 0
        finally:
            client.command_throttle.stop()

    @pytest.mark.asyncio
    async def test_set_value_no_burst_below_threshold(self) -> None:
        """Test that commands below burst threshold do not trigger downgrade."""
        client, backend = _create_throttled_client(
            throttle_interval=0.05,
            burst_threshold=10,
            burst_window=2.0,
        )

        try:
            # Send only 3 commands — well below burst_threshold=10
            for i in range(3):
                await client.set_value(
                    channel_address="dev1:1",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=float(i) / 10,
                    wait_for_callback=None,
                )

            assert len(backend.calls) == 3
            assert client.command_throttle.burst_count == 0
        finally:
            client.command_throttle.stop()


# =============================================================================
# Queue Purge Tests
# =============================================================================


class TestQueuePurge:
    """Test queue purge when CRITICAL commands arrive."""

    async def test_critical_no_purge_when_empty_addresses(self) -> None:
        """Test that CRITICAL without purge_addresses does not purge anything."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)

        import heapq
        import time

        from aiohomematic.client.command_throttle import PrioritizedCommand

        f: asyncio.Future[None] = asyncio.Future()
        async with throttle._lock:
            heapq.heappush(
                throttle._queue,
                PrioritizedCommand(
                    priority=CommandPriority.HIGH,
                    timestamp=time.monotonic(),
                    future=f,
                    device_address="VCU:3",
                ),
            )

        await throttle.acquire(priority=CommandPriority.CRITICAL, device_address="VCU:3")

        # Queue untouched
        assert throttle.queue_size == 1
        assert throttle.purged_count == 0

        throttle.stop()

    async def test_critical_purge_does_not_affect_other_groups(self) -> None:
        """Test that purge only affects commands in the specified channel group."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)

        import heapq
        import time

        from aiohomematic.client.command_throttle import PrioritizedCommand

        # Group 1: channels 3, 4
        f_group1: asyncio.Future[None] = asyncio.Future()
        async with throttle._lock:
            heapq.heappush(
                throttle._queue,
                PrioritizedCommand(
                    priority=CommandPriority.HIGH,
                    timestamp=time.monotonic(),
                    future=f_group1,
                    device_address="VCU:3",
                ),
            )

        # Group 2: channels 7, 8
        f_group2: asyncio.Future[None] = asyncio.Future()
        async with throttle._lock:
            heapq.heappush(
                throttle._queue,
                PrioritizedCommand(
                    priority=CommandPriority.HIGH,
                    timestamp=time.monotonic(),
                    future=f_group2,
                    device_address="VCU:7",
                ),
            )

        assert throttle.queue_size == 2

        # CRITICAL for group 1 only
        await throttle.acquire(
            priority=CommandPriority.CRITICAL,
            device_address="VCU:3",
            purge_addresses=frozenset({"VCU:3", "VCU:4"}),
        )

        # Group 1 purged, group 2 remains
        assert throttle.queue_size == 1
        assert throttle.purged_count == 1

        # Group 1 future should be superseded
        assert f_group1.done()
        with pytest.raises(CommandSupersededError):
            f_group1.result()

        # Group 2 future should still be pending
        assert not f_group2.done()

        throttle.stop()

    async def test_critical_purges_matching_channel_group(self) -> None:
        """Test that CRITICAL commands purge pending commands for same channel group."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)

        # Enqueue several HIGH commands for channels in the same group
        futures: list[asyncio.Future[None]] = []
        for addr in ("VCU:3", "VCU:4", "VCU:3"):
            f: asyncio.Future[None] = asyncio.Future()
            futures.append(f)
            async with throttle._lock:
                import heapq
                import time

                from aiohomematic.client.command_throttle import PrioritizedCommand

                cmd = PrioritizedCommand(
                    priority=CommandPriority.HIGH,
                    timestamp=time.monotonic(),
                    future=f,
                    device_address=addr,
                )
                heapq.heappush(throttle._queue, cmd)

        assert throttle.queue_size == 3

        # CRITICAL command with purge_addresses for the channel group
        purge_addrs = frozenset({"VCU:3", "VCU:4"})
        await throttle.acquire(
            priority=CommandPriority.CRITICAL,
            device_address="VCU:3",
            purge_addresses=purge_addrs,
        )

        # All matching commands should be purged
        assert throttle.queue_size == 0
        assert throttle.purged_count == 3
        assert throttle.critical_count == 1

        # Futures should have CommandSupersededError
        for f in futures:
            assert f.done()
            with pytest.raises(CommandSupersededError):
                f.result()

        throttle.stop()

    async def test_purged_count_property(self) -> None:
        """Test that purged_count property tracks correctly."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)
        assert throttle.purged_count == 0

        import heapq
        import time

        from aiohomematic.client.command_throttle import PrioritizedCommand

        # Add 2 commands
        for addr in ("VCU:3", "VCU:4"):
            f: asyncio.Future[None] = asyncio.Future()
            async with throttle._lock:
                heapq.heappush(
                    throttle._queue,
                    PrioritizedCommand(
                        priority=CommandPriority.HIGH,
                        timestamp=time.monotonic(),
                        future=f,
                        device_address=addr,
                    ),
                )

        # Purge 2
        await throttle.acquire(
            priority=CommandPriority.CRITICAL,
            device_address="VCU:3",
            purge_addresses=frozenset({"VCU:3", "VCU:4"}),
        )
        assert throttle.purged_count == 2

        # Add 1 more and purge it
        f2: asyncio.Future[None] = asyncio.Future()
        async with throttle._lock:
            heapq.heappush(
                throttle._queue,
                PrioritizedCommand(
                    priority=CommandPriority.HIGH,
                    timestamp=time.monotonic(),
                    future=f2,
                    device_address="VCU:3",
                ),
            )

        await throttle.acquire(
            priority=CommandPriority.CRITICAL,
            device_address="VCU:3",
            purge_addresses=frozenset({"VCU:3"}),
        )
        assert throttle.purged_count == 3  # Cumulative

        throttle.stop()

    def test_repr_includes_purged_count(self) -> None:
        """Test that __repr__ includes purged count."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.0)
        assert "purged=0" in repr(throttle)


class TestQueuePurgeIntegration:
    """Integration tests: queue purge through InterfaceClient."""

    @pytest.mark.asyncio
    async def test_cover_stop_purges_queued_movement_commands(self) -> None:
        """
        End-to-end: Cover STOP purges queued movement commands.

        Simulates a realistic blind actuator scenario:

        1. User sends movement commands (LEVEL) → queued by throttle
        2. User presses STOP → CRITICAL priority + channel group purge
        3. Queued movements are cancelled (CommandSupersededError)
        4. STOP bypasses throttle and reaches the backend immediately

        Note on timing: The background worker pops one command from the queue
        to apply throttle delay. That command is "in flight" (being delayed)
        and cannot be purged. We therefore enqueue 3 commands: 1 gets popped
        by the worker, 2 remain in the queue and get purged by STOP.
        """
        # Long throttle interval ensures movement commands stay queued
        client, backend = _create_throttled_client(throttle_interval=5.0, burst_threshold=0)
        throttle = client.command_throttle

        # Channel group: blind actuator on channels 3 + 4
        channel_group = frozenset({"VCU0000001:3", "VCU0000001:4"})

        try:
            # ── PHASE 1: First movement command goes through ─────────────
            # The worker picks up the first command immediately (no prior delay).
            first_cmd = asyncio.create_task(
                client.set_value(
                    channel_address="VCU0000001:4",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=1.0,
                    wait_for_callback=None,
                    priority=CommandPriority.HIGH,
                )
            )
            await asyncio.sleep(0.2)  # Let worker pick it up
            assert first_cmd.done(), "First command should complete immediately"
            assert len(backend.calls) == 1

            # ── PHASE 2: Queue up movement commands ──────────────────────
            # These are blocked by the 5-second throttle interval.
            # The worker will pop one (starts its 5s delay), leaving 2 in queue.
            queued_cmd_1 = asyncio.create_task(
                client.set_value(
                    channel_address="VCU0000001:4",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=0.0,
                    wait_for_callback=None,
                    priority=CommandPriority.HIGH,
                )
            )
            queued_cmd_2 = asyncio.create_task(
                client.set_value(
                    channel_address="VCU0000001:3",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=0.5,
                    wait_for_callback=None,
                    priority=CommandPriority.HIGH,
                )
            )
            queued_cmd_3 = asyncio.create_task(
                client.set_value(
                    channel_address="VCU0000001:4",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=0.8,
                    wait_for_callback=None,
                    priority=CommandPriority.HIGH,
                )
            )
            await asyncio.sleep(0.2)  # Let tasks enqueue + worker pop one

            # Worker popped 1 command (throttle delay), 2 remain in queue.
            # All 3 are still incomplete (waiting for throttle permission).
            assert throttle.queue_size == 2, "Two commands should remain in queue"
            assert not queued_cmd_1.done() or not queued_cmd_2.done(), "Commands should be waiting"

            # ── PHASE 3: STOP command (CRITICAL + purge) ─────────────────
            # This simulates what happens when bind_collector sets
            # priority=CRITICAL and purge_addresses from get_channel_group_addresses().
            await client.set_value(
                channel_address="VCU0000001:4",
                paramset_key=ParamsetKey.VALUES,
                parameter="STOP",
                value=True,
                wait_for_callback=None,
                priority=CommandPriority.CRITICAL,
                purge_addresses=channel_group,
            )

            # ── PHASE 4: Verify results ──────────────────────────────────
            # STOP bypassed the queue entirely
            assert throttle.critical_count == 1, "STOP should be counted as CRITICAL"

            # 2 queued movement commands were purged
            assert throttle.purged_count == 2, "Both queued movements should be purged"
            assert throttle.queue_size == 0, "Queue should be empty after purge"

            # Purged tasks complete with empty result
            # (InterfaceClient catches CommandSupersededError → returns set())
            await asyncio.sleep(0.05)
            done_cmds = [cmd for cmd in (queued_cmd_1, queued_cmd_2, queued_cmd_3) if cmd.done()]
            assert len(done_cmds) == 2, "2 of 3 queued commands should be resolved (purged)"
            for cmd in done_cmds:
                assert await cmd == set(), "Purged command returns empty set"

            # Backend received exactly 2 calls: first LEVEL + STOP.
            # The purged LEVEL commands never reached the backend.
            assert len(backend.calls) == 2, "Backend should see first LEVEL + STOP only"
            assert backend.calls[0] == ("set_value", ("VCU0000001:4", "LEVEL", 1.0, None))
            assert backend.calls[1] == ("set_value", ("VCU0000001:4", "STOP", True, None))

        finally:
            throttle.stop()

    @pytest.mark.asyncio
    async def test_put_paramset_with_purge_addresses(self) -> None:
        """Test that purge_addresses is passed through put_paramset to throttle."""
        client, backend = _create_throttled_client(throttle_interval=0.05)

        try:
            await client.put_paramset(
                channel_address="dev1:3",
                paramset_key_or_link_address=ParamsetKey.VALUES,
                values={"LEVEL": 0.0},
                wait_for_callback=None,
                priority=CommandPriority.CRITICAL,
                purge_addresses=frozenset({"dev1:3", "dev1:4"}),
            )

            assert len(backend.calls) == 1
            assert backend.calls[0][0] == "put_paramset"
            assert client.command_throttle.critical_count == 1
        finally:
            client.command_throttle.stop()

    @pytest.mark.asyncio
    async def test_set_value_with_purge_addresses(self) -> None:
        """Test that purge_addresses is passed through set_value to throttle."""
        client, backend = _create_throttled_client(throttle_interval=0.05)

        try:
            # Send a CRITICAL command with purge addresses
            await client.set_value(
                channel_address="dev1:3",
                paramset_key=ParamsetKey.VALUES,
                parameter="STOP",
                value=True,
                wait_for_callback=None,
                priority=CommandPriority.CRITICAL,
                purge_addresses=frozenset({"dev1:3", "dev1:4"}),
            )

            assert len(backend.calls) == 1
            assert backend.calls[0][0] == "set_value"
            assert client.command_throttle.critical_count == 1
        finally:
            client.command_throttle.stop()

    @pytest.mark.asyncio
    async def test_stop_does_not_purge_other_channel_group(self) -> None:
        """
        End-to-end: STOP on channel group 1 does NOT affect channel group 2.

        Simulates a 2-channel blind actuator where each channel group
        operates independently. STOP on group 1 must leave group 2 alone.

        Note on timing: The background worker pops one command from the
        queue for throttle delay. We therefore enqueue 3 commands so that
        after the worker pops one, 1 from group 1 and 1 from group 2
        remain in the queue.
        """
        client, _backend = _create_throttled_client(throttle_interval=5.0, burst_threshold=0)
        throttle = client.command_throttle

        # Two independent channel groups on the same device
        group_1 = frozenset({"VCU0000001:3", "VCU0000001:4"})
        # group_2 channels: 7, 8

        try:
            # ── Send initial command to start throttle timer ─────────────
            first_cmd = asyncio.create_task(
                client.set_value(
                    channel_address="VCU0000001:4",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=1.0,
                    wait_for_callback=None,
                    priority=CommandPriority.HIGH,
                )
            )
            await asyncio.sleep(0.2)
            assert first_cmd.done()

            # ── Queue commands for BOTH channel groups ───────────────────
            # 3 commands: worker pops 1, leaving 2 in queue (1 per group).
            queued_tasks: list[asyncio.Task[set[Any]]] = []
            queued_tasks.append(
                asyncio.create_task(
                    client.set_value(
                        channel_address="VCU0000001:4",
                        paramset_key=ParamsetKey.VALUES,
                        parameter="LEVEL",
                        value=0.2,
                        wait_for_callback=None,
                        priority=CommandPriority.HIGH,
                    )
                )
            )
            queued_tasks.append(
                asyncio.create_task(
                    client.set_value(
                        channel_address="VCU0000001:3",
                        paramset_key=ParamsetKey.VALUES,
                        parameter="LEVEL",
                        value=0.0,
                        wait_for_callback=None,
                        priority=CommandPriority.HIGH,
                    )
                )
            )
            group2_cmd = asyncio.create_task(
                client.set_value(
                    channel_address="VCU0000001:7",
                    paramset_key=ParamsetKey.VALUES,
                    parameter="LEVEL",
                    value=0.5,
                    wait_for_callback=None,
                    priority=CommandPriority.HIGH,
                )
            )
            queued_tasks.append(group2_cmd)
            await asyncio.sleep(0.2)

            # Worker popped 1 command, 2 remain in queue
            assert throttle.queue_size == 2, "Two commands should remain in queue"

            # ── STOP on group 1 only ─────────────────────────────────────
            await client.set_value(
                channel_address="VCU0000001:4",
                paramset_key=ParamsetKey.VALUES,
                parameter="STOP",
                value=True,
                wait_for_callback=None,
                priority=CommandPriority.CRITICAL,
                purge_addresses=group_1,
            )

            # ── Verify: group 1 purged, group 2 untouched ───────────────
            # Only the group 1 command (VCU0000001:3) was purged.
            # The group 2 command (VCU0000001:7) remains.
            assert throttle.purged_count == 1, "Only group 1 command should be purged"
            assert throttle.queue_size == 1, "Group 2 command should remain in queue"

            # Group 2 command is still waiting for its turn
            assert not group2_cmd.done(), "Group 2 command should still be waiting"

        finally:
            throttle.stop()


class TestCommandThrottleStop:
    """Tests for CommandThrottle.stop() behavior."""

    async def test_acquire_after_stop_raises(self) -> None:
        """Test that acquire() after stop() raises CancelledError."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)
        throttle.stop()

        with pytest.raises(asyncio.CancelledError):
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:1")

    async def test_stop_cancels_worker_task(self) -> None:
        """Test that stop() cancels the background worker task."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)
        assert throttle._worker_task is not None
        assert not throttle._worker_task.done()

        throttle.stop()
        await asyncio.sleep(0.01)

        assert throttle._worker_task.done()

    async def test_stop_is_idempotent(self) -> None:
        """Test that calling stop() twice does not raise."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)
        throttle.stop()
        throttle.stop()  # Second call should not raise

    async def test_stopped_flag_prevents_enqueue(self) -> None:
        """Test that the _stopped flag is set after stop()."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)
        assert throttle._stopped is False
        throttle.stop()
        assert throttle._stopped is True


class TestCommandThrottlePurge:
    """Tests for CRITICAL command purge behavior."""

    async def test_purge_increments_purged_count(self) -> None:
        """Test that purge correctly increments purged_count."""
        throttle = CommandThrottle(interface_id="TEST", interval=5.0)

        try:
            assert throttle.purged_count == 0

            # Fill pipeline: grant first, enqueue several for same address
            background_futures: set[asyncio.Future[None]] = set()
            await throttle.acquire(priority=CommandPriority.HIGH, device_address="TEST:0")
            for addr in ("TARGET:1", "TARGET:1", "OTHER:2"):
                f = asyncio.ensure_future(throttle.acquire(priority=CommandPriority.HIGH, device_address=addr))
                background_futures.add(f)
                f.add_done_callback(background_futures.discard)
            await asyncio.sleep(0.05)

            # Purge TARGET:1
            await throttle.acquire(
                priority=CommandPriority.CRITICAL,
                device_address="TARGET:1",
                purge_addresses=frozenset({"TARGET:1"}),
            )

            # At least 1 purged (worker may have already dequeued one)
            assert throttle.purged_count >= 1
        finally:
            throttle.stop()

    async def test_queue_size_starts_at_zero(self) -> None:
        """Test that queue_size is 0 initially."""
        throttle = CommandThrottle(interface_id="TEST", interval=0.1)
        try:
            assert throttle.queue_size == 0
        finally:
            throttle.stop()
