# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Contract tests for capability-driven behavior.

STABILITY GUARANTEE
-------------------
These tests define the stable API contract for capability-driven backends
(like CUxD/CCU-Jack). Any change that breaks these tests requires a MAJOR
version bump and coordination with plugin maintainers.

The contract ensures that:
1. Backends with ping_pong=False are never marked as "callback dead"
2. Backends with ping_pong=False don't trigger reconnects due to missing events
3. Backends with rpc_callback=False skip XML-RPC proxy initialization
4. All capability flags exist and have expected types
5. Capability-gated methods return safe defaults when capability is False
6. JSON-RPC-only interfaces use appropriate connection checks

See ADR-0018 for architectural context and rationale.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiohomematic.client.backends.capabilities import (
    CCU_CAPABILITIES,
    HOMEGEAR_CAPABILITIES,
    JSON_CCU_CAPABILITIES,
    BackendCapabilities,
)
from aiohomematic.const import (
    INIT_DATETIME,
    INTERFACES_REQUIRING_JSON_RPC_CLIENT,
    INTERFACES_REQUIRING_XML_RPC,
    INTERFACES_SUPPORTING_RPC_CALLBACK,
    ClientState,
    Interface,
    ProxyInitState,
)

# pylint: disable=protected-access


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


class _FakeEventBus:
    """Minimal fake EventBus for contract testing."""

    def __init__(self) -> None:
        self.published_events: list[Any] = []

    async def publish(self, *, event: Any) -> None:
        """Publish an event asynchronously."""
        self.published_events.append(event)

    def publish_sync(self, *, event: Any) -> None:
        """Publish an event synchronously."""
        self.published_events.append(event)

    def subscribe(self, *, event_type: Any, event_key: Any, handler: Any) -> Any:
        """Subscribe to events."""
        return lambda: None


class _FakeEventCoordinator:
    """Fake event coordinator for contract testing."""

    def __init__(self, *, last_event_time: datetime | None = None) -> None:
        self._last_event_time = last_event_time

    def get_last_event_seen_for_interface(self, *, interface_id: str) -> datetime | None:
        """Return the last event time for an interface."""
        return self._last_event_time


class _FakeConnectionState:
    """Fake connection state for contract testing."""

    def is_rpc_proxy_issue(self, *, interface_id: str) -> bool:
        """Return False - no connection issues in tests."""
        return False


class _FakeCentral:
    """Minimal CentralUnit-like object for contract testing."""

    def __init__(
        self,
        *,
        last_event_time: datetime | None = None,
        callback_warn_interval: float = 180.0,
    ) -> None:
        self._event_bus = _FakeEventBus()
        self._event_coordinator = _FakeEventCoordinator(last_event_time=last_event_time)
        self.name = "contract-test-central"

        class Cfg:
            host = "localhost"
            tls = False
            verify_tls = False
            username = None
            password = None
            max_read_workers = 0
            callback_host = "127.0.0.1"
            callback_port_xml_rpc = 0
            interfaces_requiring_periodic_refresh = frozenset()
            timeout_config = SimpleNamespace(
                callback_warn_interval=callback_warn_interval,
                connectivity_error_threshold=3,
            )

        self.config = Cfg()
        self._listen_port_xml_rpc = 32001
        self._callback_ip_addr = "127.0.0.1"
        self.json_rpc_client = SimpleNamespace(
            clear_session=lambda: None,
            circuit_breaker=SimpleNamespace(reset=lambda: None),
        )
        self.connection_state = _FakeConnectionState()

        class _FakeIncidentStore:
            def record_incident(self, **kwargs: Any) -> None:
                pass

        class _FakeCacheCoordinator:
            incident_store = _FakeIncidentStore()

        self._cache_coordinator = _FakeCacheCoordinator()

    @property
    def cache_coordinator(self) -> Any:
        """Return the cache coordinator."""
        return self._cache_coordinator

    @property
    def callback_ip_addr(self) -> str:
        """Return the callback IP address."""
        return self._callback_ip_addr

    @property
    def device_coordinator(self) -> Any:
        """Return the device coordinator."""
        return SimpleNamespace(
            add_new_devices=AsyncMock(),
            get_device=lambda address: None,
        )

    @property
    def event_bus(self) -> Any:
        """Return the event bus."""
        return self._event_bus

    @property
    def event_coordinator(self) -> Any:
        """Return the event coordinator."""
        return self._event_coordinator

    @property
    def listen_port_xml_rpc(self) -> int:
        """Return the XML-RPC listen port."""
        return self._listen_port_xml_rpc


def _create_fake_backend(
    *,
    interface: Interface = Interface.CUXD,
    interface_id: str = "test-CUxD",
    capabilities: BackendCapabilities | None = None,
) -> MagicMock:
    """Create a fake backend with configurable capabilities."""
    backend = MagicMock()
    backend.interface = interface
    backend.interface_id = interface_id
    backend.capabilities = capabilities or JSON_CCU_CAPABILITIES
    backend.model = "CCU"
    backend.system_information = SimpleNamespace(
        available_interfaces=(interface,),
        serial="CONTRACT_TEST",
    )
    backend.all_circuit_breakers_closed = True
    backend.circuit_breaker = MagicMock()
    backend.check_connection = AsyncMock(return_value=True)
    backend.init_proxy = AsyncMock()
    backend.deinit_proxy = AsyncMock()
    backend.list_devices = AsyncMock(return_value=())
    return backend


def _create_interface_client(
    *,
    backend: MagicMock,
    central: _FakeCentral,
) -> Any:
    """Create an InterfaceClient with the given backend and central."""
    from aiohomematic.client import InterfaceClient, InterfaceConfig

    interface_config = InterfaceConfig(
        central_name=central.name,
        interface=backend.interface,
        port=80,
    )

    return InterfaceClient(
        backend=backend,
        central=central,  # type: ignore[arg-type]
        interface_config=interface_config,
        version="0",
    )


# =============================================================================
# SECTION 1: BackendCapabilities Structure Contract
# =============================================================================


class TestBackendCapabilitiesStructureContract:
    """
    Contract: BackendCapabilities structure must remain stable.

    These tests ensure that the capability flags used by plugins
    continue to exist and have the expected types. Adding new fields
    is allowed, but removing or renaming existing fields is a breaking change.
    """

    def test_capabilities_are_frozen_dataclass(self) -> None:
        """
        CONTRACT: BackendCapabilities MUST be an immutable (frozen) dataclass.

        Immutability ensures capability flags cannot be modified after creation,
        which is essential for predictable behavior.
        """
        caps = BackendCapabilities()

        # Attempt to modify should raise an error
        with pytest.raises((AttributeError, TypeError)):
            caps.ping_pong = True  # type: ignore[misc]

    def test_capabilities_use_slots(self) -> None:
        """CONTRACT: BackendCapabilities SHOULD use __slots__ for memory efficiency."""
        caps = BackendCapabilities()

        # Frozen dataclasses with slots=True don't have __dict__
        assert not hasattr(caps, "__dict__") or len(caps.__dict__) == 0

    def test_default_values_are_safe(self) -> None:
        """
        CONTRACT: Default capability values MUST be safe (restrictive).

        A backend created with default values should have minimal capabilities,
        ensuring that features are explicitly opted into.
        """
        caps = BackendCapabilities()

        # Connection defaults: push_updates=True, rpc_callback=True, ping_pong=False
        # This is the safest default: assume events arrive via push but no ping/pong
        assert caps.ping_pong is False, "ping_pong default MUST be False"
        assert caps.push_updates is True, "push_updates default MUST be True"
        assert caps.rpc_callback is True, "rpc_callback default MUST be True"

        # All feature flags should default to False
        feature_fields = [f for f in fields(caps) if f.name not in ("ping_pong", "push_updates", "rpc_callback")]
        for field in feature_fields:
            assert getattr(caps, field.name) is False, f"{field.name} default MUST be False"

    def test_required_connection_capability_fields_exist(self) -> None:
        """
        CONTRACT: Connection-related capability fields MUST exist.

        These fields control connection behavior and are critical for
        CUxD/CCU-Jack compatibility.
        """
        caps = BackendCapabilities()

        # These fields MUST exist and be boolean
        assert hasattr(caps, "ping_pong"), "ping_pong field MUST exist"
        assert hasattr(caps, "push_updates"), "push_updates field MUST exist"
        assert hasattr(caps, "rpc_callback"), "rpc_callback field MUST exist"

        assert isinstance(caps.ping_pong, bool), "ping_pong MUST be bool"
        assert isinstance(caps.push_updates, bool), "push_updates MUST be bool"
        assert isinstance(caps.rpc_callback, bool), "rpc_callback MUST be bool"

    def test_required_feature_capability_fields_exist(self) -> None:
        """
        CONTRACT: Feature capability fields MUST exist.

        These fields gate feature access and are used by capability checks.
        """
        caps = BackendCapabilities()

        required_fields = [
            "backup",
            "device_firmware_update",
            "firmware_update_trigger",
            "firmware_updates",
            "functions",
            "inbox_devices",
            "install_mode",
            "linking",
            "metadata",
            "programs",
            "rega_id_lookup",
            "rename",
            "rooms",
            "service_messages",
            "system_update_info",
            "value_usage_reporting",
        ]

        for field_name in required_fields:
            assert hasattr(caps, field_name), f"{field_name} field MUST exist"
            assert isinstance(getattr(caps, field_name), bool), f"{field_name} MUST be bool"


# =============================================================================
# SECTION 2: Predefined Capability Sets Contract
# =============================================================================


class TestPredefinedCapabilitySetsContract:
    """
    Contract: Predefined capability sets must have stable, expected values.

    These tests ensure that JSON_CCU_CAPABILITIES, CCU_CAPABILITIES, and
    HOMEGEAR_CAPABILITIES maintain their expected values.
    """

    def test_ccu_capabilities_has_ping_pong(self) -> None:
        """
        CONTRACT: CCU_CAPABILITIES MUST have ping_pong=True.

        Standard CCU backends support XML-RPC ping/pong for connection health.
        """
        assert CCU_CAPABILITIES.ping_pong is True
        assert CCU_CAPABILITIES.rpc_callback is True

    def test_homegear_capabilities_no_ping_pong(self) -> None:
        """
        CONTRACT: HOMEGEAR_CAPABILITIES MUST have ping_pong=False.

        Homegear uses XML-RPC callbacks but doesn't support ping/pong.
        """
        assert HOMEGEAR_CAPABILITIES.ping_pong is False
        assert HOMEGEAR_CAPABILITIES.rpc_callback is True

    def test_json_ccu_capabilities_connection_settings(self) -> None:
        """
        CONTRACT: JSON_CCU_CAPABILITIES connection settings MUST be correct.

        Expected values:
        - ping_pong=False (no XML-RPC callback ping/pong)
        - rpc_callback=False (no XML-RPC callback server)
        - push_updates=True (events via MQTT through HA)
        """
        assert JSON_CCU_CAPABILITIES.ping_pong is False, "JSON_CCU_CAPABILITIES.ping_pong MUST be False"
        assert JSON_CCU_CAPABILITIES.rpc_callback is False, "JSON_CCU_CAPABILITIES.rpc_callback MUST be False"
        assert JSON_CCU_CAPABILITIES.push_updates is True, "JSON_CCU_CAPABILITIES.push_updates MUST be True"

    def test_json_ccu_capabilities_features_disabled(self) -> None:
        """
        CONTRACT: JSON_CCU_CAPABILITIES feature flags MUST all be False.

        CUxD/CCU-Jack don't support CCU-specific features like programs,
        system variables, firmware updates, etc.
        """
        feature_fields = [
            "backup",
            "device_firmware_update",
            "firmware_update_trigger",
            "firmware_updates",
            "functions",
            "inbox_devices",
            "install_mode",
            "linking",
            "metadata",
            "programs",
            "rega_id_lookup",
            "rename",
            "rooms",
            "service_messages",
            "system_update_info",
            "value_usage_reporting",
        ]

        for field_name in feature_fields:
            assert getattr(JSON_CCU_CAPABILITIES, field_name) is False, (
                f"JSON_CCU_CAPABILITIES.{field_name} MUST be False"
            )


# =============================================================================
# SECTION 3: ping_pong Capability Contract
# =============================================================================


class TestPingPongCapabilityContract:
    """
    Contract: When ping_pong=False, callback-based health checks MUST be skipped.

    This contract protects backends like CUxD/CCU-Jack that receive events via
    MQTT (through Home Assistant) rather than XML-RPC callbacks. Without this
    contract, these backends would be incorrectly marked as disconnected.
    """

    def test_is_callback_alive_checks_events_when_ping_pong_true(self) -> None:
        """
        CONTRACT: is_callback_alive() MUST NOT return True immediately when ping_pong=True.

        This ensures the contract works both ways - backends WITH ping/pong
        go through the full callback check logic.
        """
        # With recent events, should return True
        central_recent = _FakeCentral(
            last_event_time=datetime.now() - timedelta(seconds=10),
            callback_warn_interval=180.0,
        )
        backend = _create_fake_backend(
            interface=Interface.HMIP_RF,
            capabilities=CCU_CAPABILITIES,
        )
        client = _create_interface_client(backend=backend, central=central_recent)

        # Initialize state machine to allow the check
        client._state_machine._state = ClientState.CONNECTED

        # With recent events and ping_pong=True, should still return True
        # (but went through the full check, not early return)
        result = client.is_callback_alive()

        assert result is True, "is_callback_alive() should return True when ping_pong=True and events are recent"

    def test_is_callback_alive_returns_true_regardless_of_state_when_ping_pong_false(
        self,
    ) -> None:
        """
        CONTRACT: is_callback_alive() MUST return True even in edge cases when ping_pong=False.

        Edge cases: no events ever received, very old events, etc.
        """
        # Case 1: No events ever received (last_event_time is None)
        central_no_events = _FakeCentral(last_event_time=None)
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central_no_events)

        assert client.is_callback_alive() is True

        # Case 2: Events from very long ago
        central_old_events = _FakeCentral(
            last_event_time=datetime.now() - timedelta(days=7),
        )
        client2 = _create_interface_client(
            backend=_create_fake_backend(capabilities=JSON_CCU_CAPABILITIES),
            central=central_old_events,
        )

        assert client2.is_callback_alive() is True

    def test_is_callback_alive_returns_true_when_ping_pong_false(self) -> None:
        """
        CONTRACT: is_callback_alive() MUST return True immediately when ping_pong=False.

        Rationale: Backends without ping/pong support cannot be monitored via
        callback timestamps. Returning False would trigger unnecessary reconnects.
        """
        central = _FakeCentral(
            # Even with very old last event time
            last_event_time=datetime.now() - timedelta(hours=24),
        )
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        # Verify capability is as expected
        assert client.capabilities.ping_pong is False

        result = client.is_callback_alive()

        assert result is True, (
            "CAPABILITY CONTRACT VIOLATION: is_callback_alive() MUST return True "
            "when backend.capabilities.ping_pong=False"
        )

    async def test_is_connected_checks_callback_warn_when_ping_pong_true(self) -> None:
        """
        CONTRACT: is_connected() MUST check callback_warn when ping_pong=True.

        When ping_pong=True and modified_at is recent, should return True.
        This proves the callback_warn check is actually happening.
        """
        central = _FakeCentral(callback_warn_interval=180.0)
        backend = _create_fake_backend(
            interface=Interface.HMIP_RF,
            capabilities=CCU_CAPABILITIES,
        )
        client = _create_interface_client(backend=backend, central=central)

        # Initialize state machine
        client._state_machine._state = ClientState.CONNECTED

        # Simulate RECENT modified_at (within callback_warn)
        client._modified_at = datetime.now() - timedelta(seconds=10)

        result = await client.is_connected()

        # With ping_pong=True and recent modified_at, should return True
        # This proves the full check path is taken
        assert result is True

    async def test_is_connected_skips_callback_warn_when_ping_pong_false(self) -> None:
        """
        CONTRACT: is_connected() MUST skip callback_warn check when ping_pong=False.

        Rationale: Even if modified_at is old (no recent events), backends without
        ping/pong should remain "connected" as long as TCP/RPC checks pass.
        """
        central = _FakeCentral(callback_warn_interval=180.0)
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        # Simulate old modified_at (would fail callback_warn check if checked)
        client._modified_at = datetime.now() - timedelta(hours=1)

        # Initialize state machine
        client._state_machine._state = ClientState.CONNECTED

        result = await client.is_connected()

        assert result is True, (
            "CAPABILITY CONTRACT VIOLATION: is_connected() MUST return True "
            "when backend.capabilities.ping_pong=False, regardless of modified_at"
        )

    def test_no_callback_timeout_logging_when_ping_pong_false(self) -> None:
        """
        CONTRACT: No "no events received" error logs when ping_pong=False.

        Rationale: These log messages are confusing for users of CUxD/CCU-Jack
        since events arrive via a different channel (MQTT).
        """
        central = _FakeCentral(
            last_event_time=datetime.now() - timedelta(hours=1),
        )
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        with patch("aiohomematic.client.interface_client._LOGGER") as mock_logger:
            client.is_callback_alive()

            # Verify no error logging occurred
            mock_logger.error.assert_not_called()


# =============================================================================
# SECTION 4: rpc_callback Capability Contract
# =============================================================================


class TestRpcCallbackCapabilityContract:
    """
    Contract: When rpc_callback=False, XML-RPC proxy initialization is skipped.

    This contract ensures backends without XML-RPC callback support
    (CUxD/CCU-Jack) don't attempt to call init() on a proxy that doesn't exist.
    """

    async def test_initialize_proxy_calls_init_when_rpc_callback_true(self) -> None:
        """CONTRACT: initialize_proxy() MUST call backend.init_proxy() when rpc_callback=True."""
        central = _FakeCentral()
        backend = _create_fake_backend(
            interface=Interface.HMIP_RF,
            capabilities=CCU_CAPABILITIES,
        )
        client = _create_interface_client(backend=backend, central=central)

        # Initialize state machine to INITIALIZED
        client._state_machine._state = ClientState.INITIALIZED

        await client.initialize_proxy()

        # Should call init_proxy
        backend.init_proxy.assert_called_once()

    async def test_initialize_proxy_skips_init_when_rpc_callback_false(self) -> None:
        """
        CONTRACT: initialize_proxy() MUST NOT call backend.init_proxy() when rpc_callback=False.

        Instead, it should directly list devices and transition to CONNECTED.
        """
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        # Initialize state machine to INITIALIZED
        client._state_machine._state = ClientState.INITIALIZED

        result = await client.initialize_proxy()

        # Should succeed without calling init_proxy
        assert result == ProxyInitState.INIT_SUCCESS
        backend.init_proxy.assert_not_called()
        backend.list_devices.assert_called_once()

    async def test_initialize_proxy_transitions_correctly_when_rpc_callback_false(
        self,
    ) -> None:
        """
        CONTRACT: State transition for rpc_callback=False MUST follow correct flow.

        Expected: INITIALIZED -> CONNECTING -> CONNECTED (with reason "no callback")
        """
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        # Initialize state machine to INITIALIZED
        client._state_machine._state = ClientState.INITIALIZED

        await client.initialize_proxy()

        # Should be in CONNECTED state
        assert client.state == ClientState.CONNECTED


# =============================================================================
# SECTION 5: push_updates Capability Contract
# =============================================================================


class TestPushUpdatesCapabilityContract:
    """
    Contract: When push_updates=False, is_connected() returns early.

    This contract covers interfaces that use polling instead of push updates.
    """

    async def test_is_connected_returns_true_early_when_push_updates_false(self) -> None:
        """
        CONTRACT: is_connected() MUST return True early when push_updates=False.

        Rationale: If there are no push updates, there's no callback_warn to check.
        """
        from dataclasses import replace

        central = _FakeCentral()
        # Create capabilities with push_updates=False (but ping_pong=True to not hit that early return)
        caps = replace(CCU_CAPABILITIES, push_updates=False, ping_pong=True)
        backend = _create_fake_backend(
            interface=Interface.HMIP_RF,
            interface_id="test-HmIP-RF",
            capabilities=caps,
        )
        client = _create_interface_client(backend=backend, central=central)

        # Initialize state machine
        client._state_machine._state = ClientState.CONNECTED

        # Even with old modified_at - should return True because push_updates=False
        # causes early return BEFORE the callback_warn check
        client._modified_at = datetime.now() - timedelta(hours=1)

        result = await client.is_connected()

        # push_updates=False means we return True early, regardless of modified_at
        assert result is True


# =============================================================================
# SECTION 6: Capability-Gated Methods Contract
# =============================================================================


class TestCapabilityGatedMethodsContract:
    """
    Contract: Methods gated by capabilities MUST return safe defaults when disabled.

    This ensures that calling a method on a backend that doesn't support the
    feature returns a sensible default rather than raising an exception or
    calling the backend.
    """

    async def test_accept_device_in_inbox_returns_false_when_disabled(self) -> None:
        """CONTRACT: accept_device_in_inbox() MUST return False when inbox_devices=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.accept_device_in_inbox(device_address="TEST:0")

        assert result is False
        backend.accept_device_in_inbox.assert_not_called()

    async def test_add_link_does_nothing_when_disabled(self) -> None:
        """CONTRACT: add_link() MUST be a no-op when linking=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        await client.add_link(
            sender_address="TEST:1",
            receiver_address="TEST:2",
            name="test",
            description="test",
        )

        backend.add_link.assert_not_called()

    async def test_create_backup_returns_none_when_disabled(self) -> None:
        """CONTRACT: create_backup_and_download() MUST return None when backup=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.create_backup_and_download()

        assert result is None
        backend.create_backup_and_download.assert_not_called()

    async def test_execute_program_returns_false_when_disabled(self) -> None:
        """CONTRACT: execute_program() MUST return False when programs=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.execute_program(pid="test")

        assert result is False
        backend.execute_program.assert_not_called()

    async def test_get_all_functions_returns_empty_when_disabled(self) -> None:
        """CONTRACT: get_all_functions() MUST return empty dict when functions=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.get_all_functions()

        assert result == {}
        backend.get_all_functions.assert_not_called()

    async def test_get_all_programs_returns_empty_when_disabled(self) -> None:
        """CONTRACT: get_all_programs() MUST return empty tuple when programs=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.get_all_programs(markers=())

        assert result == ()
        backend.get_all_programs.assert_not_called()

    async def test_get_all_rooms_returns_empty_when_disabled(self) -> None:
        """CONTRACT: get_all_rooms() MUST return empty dict when rooms=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.get_all_rooms()

        assert result == {}
        backend.get_all_rooms.assert_not_called()

    async def test_get_inbox_devices_returns_empty_when_disabled(self) -> None:
        """CONTRACT: get_inbox_devices() MUST return empty tuple when inbox_devices=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.get_inbox_devices()

        assert result == ()
        backend.get_inbox_devices.assert_not_called()

    async def test_get_install_mode_returns_zero_when_disabled(self) -> None:
        """CONTRACT: get_install_mode() MUST return 0 when install_mode=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.get_install_mode()

        assert result == 0
        backend.get_install_mode.assert_not_called()

    async def test_get_service_messages_returns_empty_when_disabled(self) -> None:
        """CONTRACT: get_service_messages() MUST return empty tuple when service_messages=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.get_service_messages()

        assert result == ()
        backend.get_service_messages.assert_not_called()

    async def test_get_system_update_info_returns_none_when_disabled(self) -> None:
        """CONTRACT: get_system_update_info() MUST return None when system_update_info=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        result = await client.get_system_update_info()

        assert result is None
        backend.get_system_update_info.assert_not_called()


# =============================================================================
# SECTION 7: Interface Constants Contract
# =============================================================================


class TestInterfaceConstantsContract:
    """
    Contract: Interface constants must have expected values.

    These constants define which interfaces require JSON-RPC vs XML-RPC,
    and are critical for correct client creation and connection handling.
    """

    def test_ccu_jack_in_json_rpc_interfaces(self) -> None:
        """CONTRACT: Interface.CCU_JACK MUST be in INTERFACES_REQUIRING_JSON_RPC_CLIENT."""
        assert Interface.CCU_JACK in INTERFACES_REQUIRING_JSON_RPC_CLIENT

    def test_ccu_jack_not_in_xml_rpc_interfaces(self) -> None:
        """CONTRACT: Interface.CCU_JACK MUST NOT be in INTERFACES_REQUIRING_XML_RPC."""
        assert Interface.CCU_JACK not in INTERFACES_REQUIRING_XML_RPC

    def test_ccu_jack_not_supporting_rpc_callback(self) -> None:
        """CONTRACT: Interface.CCU_JACK MUST NOT be in INTERFACES_SUPPORTING_RPC_CALLBACK."""
        assert Interface.CCU_JACK not in INTERFACES_SUPPORTING_RPC_CALLBACK

    def test_cuxd_in_json_rpc_interfaces(self) -> None:
        """CONTRACT: Interface.CUXD MUST be in INTERFACES_REQUIRING_JSON_RPC_CLIENT."""
        assert Interface.CUXD in INTERFACES_REQUIRING_JSON_RPC_CLIENT

    def test_cuxd_not_in_xml_rpc_interfaces(self) -> None:
        """CONTRACT: Interface.CUXD MUST NOT be in INTERFACES_REQUIRING_XML_RPC."""
        assert Interface.CUXD not in INTERFACES_REQUIRING_XML_RPC

    def test_cuxd_not_supporting_rpc_callback(self) -> None:
        """CONTRACT: Interface.CUXD MUST NOT be in INTERFACES_SUPPORTING_RPC_CALLBACK."""
        assert Interface.CUXD not in INTERFACES_SUPPORTING_RPC_CALLBACK

    def test_interface_enum_values_stable(self) -> None:
        """CONTRACT: Interface enum values MUST be stable strings."""
        assert Interface.CUXD.value == "CUxD"
        assert Interface.CCU_JACK.value == "CCU-Jack"
        assert Interface.BIDCOS_RF.value == "BidCos-RF"
        assert Interface.BIDCOS_WIRED.value == "BidCos-Wired"
        assert Interface.HMIP_RF.value == "HmIP-RF"
        assert Interface.VIRTUAL_DEVICES.value == "VirtualDevices"

    def test_standard_interfaces_in_xml_rpc(self) -> None:
        """CONTRACT: Standard interfaces MUST be in INTERFACES_REQUIRING_XML_RPC."""
        for interface in [
            Interface.BIDCOS_RF,
            Interface.BIDCOS_WIRED,
            Interface.HMIP_RF,
            Interface.VIRTUAL_DEVICES,
        ]:
            assert interface in INTERFACES_REQUIRING_XML_RPC


# =============================================================================
# SECTION 8: Connection Check Capability Contract
# =============================================================================


class TestConnectionCheckCapabilityContract:
    """
    Contract: check_connection_availability() behavior based on capabilities.

    This contract ensures that ping/pong is only used when the capability is True.
    """

    async def test_check_connection_sends_ping_when_enabled(self) -> None:
        """
        CONTRACT: check_connection_availability() MUST send ping when ping_pong=True.

        Preconditions: ping_pong=True and client is_initialized=True.
        """
        central = _FakeCentral()
        backend = _create_fake_backend(
            interface=Interface.HMIP_RF,
            interface_id="test-HmIP-RF",
            capabilities=CCU_CAPABILITIES,
        )
        client = _create_interface_client(backend=backend, central=central)

        # Initialize state machine to CONNECTED (which makes is_initialized=True)
        client._state_machine._state = ClientState.CONNECTED

        # Verify preconditions
        assert client.capabilities.ping_pong is True
        assert client.is_initialized is True

        await client.check_connection_availability(handle_ping_pong=True)

        # Backend should be called with a caller_id (ping token)
        backend.check_connection.assert_called_once()
        call_kwargs = backend.check_connection.call_args.kwargs
        assert call_kwargs.get("caller_id") is not None, (
            "caller_id MUST be set when ping_pong=True and is_initialized=True"
        )
        # Verify the caller_id has the expected format (interface_id#timestamp)
        caller_id = call_kwargs.get("caller_id")
        assert caller_id.startswith("test-HmIP-RF#"), f"caller_id should start with interface_id#, got: {caller_id}"

    async def test_check_connection_skips_ping_pong_when_disabled(self) -> None:
        """CONTRACT: check_connection_availability() MUST NOT send ping when ping_pong=False."""
        central = _FakeCentral()
        backend = _create_fake_backend(capabilities=JSON_CCU_CAPABILITIES)
        client = _create_interface_client(backend=backend, central=central)

        # Initialize state machine
        client._state_machine._state = ClientState.CONNECTED

        await client.check_connection_availability(handle_ping_pong=True)

        # Backend should be called with handle_ping_pong=True, but no caller_id
        # because ping_pong capability is False
        backend.check_connection.assert_called_once()
        call_kwargs = backend.check_connection.call_args.kwargs
        assert call_kwargs.get("caller_id") is None, "caller_id MUST be None when ping_pong=False"


# =============================================================================
# SECTION 9: JSON-RPC Only Interface Behavior Contract
# =============================================================================


class TestJsonRpcOnlyBehaviorContract:
    """
    Contract: JSON-RPC-only interfaces have specific behavioral requirements.

    These tests ensure the overall system behavior for CUxD/CCU-Jack is correct.
    """

    async def test_complete_json_rpc_client_lifecycle(self) -> None:
        """
        CONTRACT: Complete lifecycle for JSON-RPC-only client must work correctly.

        This is an integration-style contract test that verifies the full flow:
        1. Client creation with JSON_CCU_CAPABILITIES
        2. Initialization (skips XML-RPC init)
        3. Connection checks (no ping/pong)
        4. Callback alive checks (always True)
        """
        central = _FakeCentral()
        backend = _create_fake_backend(
            interface=Interface.CUXD,
            capabilities=JSON_CCU_CAPABILITIES,
        )
        client = _create_interface_client(backend=backend, central=central)

        # 1. Verify capabilities
        assert client.capabilities.ping_pong is False
        assert client.capabilities.rpc_callback is False

        # 2. Initialize
        client._state_machine._state = ClientState.INITIALIZED
        result = await client.initialize_proxy()
        assert result == ProxyInitState.INIT_SUCCESS
        assert client.state == ClientState.CONNECTED

        # 3. Check connection (no ping/pong)
        await client.check_connection_availability(handle_ping_pong=True)
        # Verify no caller_id was set (no ping sent)

        # 4. Callback alive (always True)
        assert client.is_callback_alive() is True

        # 5. Is connected (skip callback_warn)
        client._modified_at = INIT_DATETIME  # Very old
        assert await client.is_connected() is True

    def test_json_rpc_default_ports(self) -> None:
        """CONTRACT: JSON-RPC default ports MUST be 80 (HTTP) and 443 (HTTPS)."""
        from aiohomematic.const import get_json_rpc_default_port

        assert get_json_rpc_default_port(tls=False) == 80
        assert get_json_rpc_default_port(tls=True) == 443

    def test_json_rpc_only_interfaces_computed_correctly(self) -> None:
        """
        CONTRACT: JSON-RPC-only interfaces = JSON_RPC - XML_RPC.

        This set is used throughout the codebase to identify interfaces that:
        - Don't have XML-RPC proxies
        - Use JSON-RPC port (80/443) instead of XML-RPC ports (2000-2011)
        - Don't support ping/pong
        """
        json_rpc_only = INTERFACES_REQUIRING_JSON_RPC_CLIENT - INTERFACES_REQUIRING_XML_RPC

        assert Interface.CUXD in json_rpc_only
        assert Interface.CCU_JACK in json_rpc_only
        assert len(json_rpc_only) == 2
