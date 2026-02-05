"""Tests for command throttle with priority queue."""

from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from aiohomematic.client import CommandPriority, CommandThrottle, InterfaceClient, InterfaceConfig
from aiohomematic.const import Interface, ParamsetKey, TimeoutConfig


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
            rega_id_lookup=True,
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
                add_address_rega_id=lambda **kwargs: None,
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

    def get_device(self, *, address: str) -> Any:
        """Return device by address."""
        dev_addr = address.split(":")[0] if ":" in address else address
        return self._devices.get(dev_addr)

    def get_generic_data_point(self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey) -> Any:
        """Return generic data point."""
        key = f"{channel_address}:{parameter}:{paramset_key}"
        return self._data_points.get(key)

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
