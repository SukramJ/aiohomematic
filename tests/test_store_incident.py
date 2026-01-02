# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for IncidentStore in aiohomematic."""

from __future__ import annotations

import pytest

from aiohomematic.async_support import Looper
from aiohomematic.const import FILE_INCIDENTS, SUB_DIRECTORY_CACHE, DataOperationResult
from aiohomematic.store import IncidentSeverity, IncidentSnapshot, IncidentType, LocalStorageFactory, StorageProtocol
from aiohomematic.store.persistent import IncidentStore
from aiohomematic.store.types import PingPongJournal


class _Cfg:
    """Simple central config stub used by tests."""

    def __init__(self, storage_directory: str, use_caches: bool = True) -> None:
        self.storage_directory = storage_directory
        self.use_caches = use_caches


class _CentralStub:
    """Minimal Central stub for testing IncidentStore."""

    def __init__(self, name: str, storage_directory: str, use_caches: bool = True) -> None:
        self.name = name
        self.config = _Cfg(storage_directory=storage_directory, use_caches=use_caches)
        self.looper = Looper()
        self.storage_factory = LocalStorageFactory(
            base_directory=storage_directory,
            central_name=name,
            task_scheduler=self.looper,
        )

    def create_incident_storage(self) -> StorageProtocol:
        """Create storage for incidents."""
        return self.storage_factory.create_storage(
            key=FILE_INCIDENTS,
            sub_directory=SUB_DIRECTORY_CACHE,
        )


class TestIncidentSnapshot:
    """Tests for IncidentSnapshot dataclass."""

    def test_incident_snapshot_from_dict(self) -> None:
        """Test IncidentSnapshot deserialization from dict."""
        data = {
            "incident_id": "test_456",
            "timestamp": "2026-01-02T11:00:00.000",
            "type": "RPC_ERROR",
            "severity": "warning",
            "interface_id": "HmIP-RF",
            "message": "RPC call failed",
            "context": {"method": "setValue"},
            "journal_excerpt": [],
        }

        incident = IncidentSnapshot.from_dict(data=data)

        assert incident.incident_id == "test_456"
        assert incident.timestamp_iso == "2026-01-02T11:00:00.000"
        assert incident.incident_type == IncidentType.RPC_ERROR
        assert incident.severity == IncidentSeverity.WARNING
        assert incident.interface_id == "HmIP-RF"
        assert incident.message == "RPC call failed"
        assert incident.context == {"method": "setValue"}
        assert incident.journal_excerpt == []

    def test_incident_snapshot_roundtrip(self) -> None:
        """Test IncidentSnapshot serialization/deserialization roundtrip."""
        original = IncidentSnapshot(
            incident_id="roundtrip_test",
            timestamp_iso="2026-01-02T12:00:00.000",
            incident_type=IncidentType.PING_PONG_MISMATCH_HIGH,
            severity=IncidentSeverity.CRITICAL,
            interface_id="VirtualDevices",
            message="PingPong mismatch exceeded threshold",
            context={"pending_count": 15, "threshold": 10},
            journal_excerpt=[{"type": "PONG_EXPIRED", "token": "xyz"}],
        )

        serialized = original.to_dict()
        restored = IncidentSnapshot.from_dict(data=serialized)

        assert restored.incident_id == original.incident_id
        assert restored.timestamp_iso == original.timestamp_iso
        assert restored.incident_type == original.incident_type
        assert restored.severity == original.severity
        assert restored.interface_id == original.interface_id
        assert restored.message == original.message
        assert restored.context == original.context
        assert restored.journal_excerpt == original.journal_excerpt

    def test_incident_snapshot_to_dict(self) -> None:
        """Test IncidentSnapshot serialization to dict."""
        incident = IncidentSnapshot(
            incident_id="test_123",
            timestamp_iso="2026-01-02T10:00:00.000",
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            interface_id="BidCos-RF",
            message="Connection lost to backend",
            context={"error_code": 42},
            journal_excerpt=[{"type": "PING_SENT", "token": "abc123"}],
        )

        result = incident.to_dict()

        assert result["incident_id"] == "test_123"
        assert result["timestamp"] == "2026-01-02T10:00:00.000"
        assert result["type"] == "CONNECTION_LOST"
        assert result["severity"] == "error"
        assert result["interface_id"] == "BidCos-RF"
        assert result["message"] == "Connection lost to backend"
        assert result["context"] == {"error_code": 42}
        assert len(result["journal_excerpt"]) == 1


class TestIncidentStore:
    """Tests for IncidentStore persistent cache."""

    @pytest.mark.asyncio
    async def test_clear_incidents(self, tmp_path) -> None:
        """Test clearing incidents."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Lost",
        )
        assert store.incident_count == 1

        store.clear_incidents()
        assert store.incident_count == 0

    @pytest.mark.asyncio
    async def test_get_diagnostics(self, tmp_path) -> None:
        """Test diagnostics output."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Lost",
        )
        await store.record_incident(
            incident_type=IncidentType.CONNECTION_RESTORED,
            severity=IncidentSeverity.INFO,
            message="Restored",
        )

        diag = await store.get_diagnostics()

        assert diag["total_incidents"] == 2
        assert "incidents_by_type" in diag
        assert "incidents_by_severity" in diag
        assert "recent_incidents" in diag
        assert diag["incidents_by_type"]["CONNECTION_LOST"] == 1
        assert diag["incidents_by_severity"]["error"] == 1
        assert diag["incidents_by_severity"]["info"] == 1

    @pytest.mark.asyncio
    async def test_get_incidents_by_interface(self, tmp_path) -> None:
        """Test filtering incidents by interface."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Lost RF",
            interface_id="BidCos-RF",
        )
        await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Lost IP",
            interface_id="HmIP-RF",
        )
        await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Lost RF again",
            interface_id="BidCos-RF",
        )

        rf_incidents = await store.get_incidents_by_interface(interface_id="BidCos-RF")
        assert len(rf_incidents) == 2

        ip_incidents = await store.get_incidents_by_interface(interface_id="HmIP-RF")
        assert len(ip_incidents) == 1

    @pytest.mark.asyncio
    async def test_get_incidents_by_type(self, tmp_path) -> None:
        """Test filtering incidents by type."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Lost 1",
        )
        await store.record_incident(
            incident_type=IncidentType.RPC_ERROR,
            severity=IncidentSeverity.WARNING,
            message="RPC 1",
        )
        await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Lost 2",
        )

        conn_lost = await store.get_incidents_by_type(incident_type=IncidentType.CONNECTION_LOST)
        assert len(conn_lost) == 2

        rpc_errors = await store.get_incidents_by_type(incident_type=IncidentType.RPC_ERROR)
        assert len(rpc_errors) == 1

    @pytest.mark.asyncio
    async def test_incident_size_limit(self, tmp_path) -> None:
        """Test that incidents are evicted when max is exceeded."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
            max_incidents=5,
        )

        # Record more than max
        for i in range(8):
            await store.record_incident(
                incident_type=IncidentType.RPC_ERROR,
                severity=IncidentSeverity.WARNING,
                message=f"Error {i}",
            )

        # Should be capped at max
        assert store.incident_count == 5

        # Oldest should be evicted, newest should remain
        messages = [inc.message for inc in store.incidents]
        assert "Error 0" not in messages
        assert "Error 1" not in messages
        assert "Error 2" not in messages
        assert "Error 7" in messages

    @pytest.mark.asyncio
    async def test_load_with_invalid_data(self, tmp_path) -> None:
        """Test that invalid incidents are skipped during load."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))

        # Create store and record valid incident
        store1 = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )
        await store1.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Valid incident",
        )

        # Manually corrupt the content by adding invalid entry
        store1._content["incidents"].append({"invalid": "data"})
        await store1.save()

        # Create new store and load
        store2 = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )
        await store2.load()

        # Only valid incident should be loaded
        assert store2.incident_count == 1

    @pytest.mark.asyncio
    async def test_no_save_when_caches_disabled(self, tmp_path) -> None:
        """Test that save is skipped when caches are disabled."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path), use_caches=False)
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Test",
        )

        result = await store.save()
        assert result == DataOperationResult.NO_SAVE

    @pytest.mark.asyncio
    async def test_record_incident_basic(self, tmp_path) -> None:
        """Test recording a basic incident."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        incident = await store.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Connection lost",
            interface_id="BidCos-RF",
        )

        assert incident.incident_type == IncidentType.CONNECTION_LOST
        assert incident.severity == IncidentSeverity.ERROR
        assert incident.message == "Connection lost"
        assert incident.interface_id == "BidCos-RF"
        assert store.incident_count == 1

    @pytest.mark.asyncio
    async def test_record_incident_with_context(self, tmp_path) -> None:
        """Test recording incident with additional context."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        incident = await store.record_incident(
            incident_type=IncidentType.RPC_ERROR,
            severity=IncidentSeverity.ERROR,
            message="RPC call failed",
            interface_id="BidCos-RF",
            context={
                "method": "setValue",
                "address": "ABC123:1",
                "error": "Connection refused",
            },
        )

        assert incident.context["method"] == "setValue"
        assert incident.context["address"] == "ABC123:1"
        assert incident.context["error"] == "Connection refused"

    @pytest.mark.asyncio
    async def test_record_incident_with_journal_excerpt(self, tmp_path) -> None:
        """Test recording incident with journal excerpt."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))
        store = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        # Create a journal with some events
        journal = PingPongJournal()
        journal.record_ping_sent(token="ping-1")
        journal.record_pong_received(token="ping-1", rtt_ms=15.5)
        journal.record_ping_sent(token="ping-2")
        journal.record_pong_unknown(token="orphan")

        incident = await store.record_incident(
            incident_type=IncidentType.PING_PONG_UNKNOWN_HIGH,
            severity=IncidentSeverity.WARNING,
            message="Unknown PONG count high",
            interface_id="HmIP-RF",
            journal=journal,
        )

        assert len(incident.journal_excerpt) == 4
        assert incident.journal_excerpt[0]["type"] == "PING_SENT"

    @pytest.mark.asyncio
    async def test_save_and_load(self, tmp_path) -> None:
        """Test saving and loading incidents from storage."""
        central = _CentralStub(name="test-ccu", storage_directory=str(tmp_path))

        # Create store and record incidents
        store1 = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        await store1.record_incident(
            incident_type=IncidentType.PING_PONG_MISMATCH_HIGH,
            severity=IncidentSeverity.ERROR,
            message="PingPong mismatch",
            interface_id="BidCos-RF",
            context={"pending_count": 15},
        )
        await store1.record_incident(
            incident_type=IncidentType.CONNECTION_LOST,
            severity=IncidentSeverity.ERROR,
            message="Connection lost",
            interface_id="HmIP-RF",
        )

        # Save
        result = await store1.save()
        assert result == DataOperationResult.SAVE_SUCCESS

        # Create new store and load
        store2 = IncidentStore(
            storage=central.create_incident_storage(),
            config_provider=central,
        )

        result = await store2.load()
        assert result == DataOperationResult.LOAD_SUCCESS

        # Verify loaded data
        assert store2.incident_count == 2
        incidents = store2.incidents
        assert incidents[0].incident_type == IncidentType.PING_PONG_MISMATCH_HIGH
        assert incidents[0].context["pending_count"] == 15
        assert incidents[1].incident_type == IncidentType.CONNECTION_LOST
