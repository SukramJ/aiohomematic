# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for paramset consistency checker."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.coordinators import DeviceCoordinator
from aiohomematic.central.events import IntegrationIssue, SystemStatusChangedEvent
from aiohomematic.const import IntegrationIssueSeverity, IntegrationIssueType, ParamsetKey, ProductGroup
from aiohomematic.store import IncidentSeverity, IncidentType


def _make_fake_channel(*, address: str) -> Any:
    """Create a minimal fake channel."""
    return SimpleNamespace(address=address)


def _make_fake_device(
    *,
    address: str,
    product_group: ProductGroup,
    channels: dict[str, Any] | None = None,
) -> Any:
    """Create a minimal fake device."""
    return SimpleNamespace(
        address=address,
        product_group=product_group,
        channels=channels or {},
    )


def _make_paramset_description(
    *,
    parameters: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Create a minimal paramset description mapping."""
    return parameters


class _FakeDeviceRegistry:
    """Minimal fake DeviceRegistry for testing."""

    def __init__(self, *, devices: dict[str, Any] | None = None) -> None:
        self._devices = devices or {}

    @property
    def devices(self) -> tuple[Any, ...]:
        """Return all devices."""
        return tuple(self._devices.values())

    def get_device(self, *, address: str) -> Any:
        """Return a device by address."""
        return self._devices.get(address)

    def get_device_addresses(self) -> set[str]:
        """Return all device addresses."""
        return set(self._devices.keys())

    def has_device(self, *, address: str) -> bool:
        """Return whether device exists."""
        return address in self._devices


def _create_device_coordinator(
    *,
    device_registry: _FakeDeviceRegistry,
    paramset_descriptions: dict[str, dict[str, dict[ParamsetKey, dict[str, Any]]]] | None = None,
    client_get_paramset_side_effect: Any = None,
    incident_recorder: Any | None = None,
) -> tuple[DeviceCoordinator, AsyncMock]:
    """Create a DeviceCoordinator with mocked dependencies for testing."""
    event_bus = MagicMock()
    event_bus.publish = AsyncMock()

    # Build paramset cache mock
    paramset_cache = MagicMock()

    def _get_paramset_descriptions(
        *,
        interface_id: str,
        channel_address: str,
        paramset_key: ParamsetKey,
    ) -> dict[str, Any]:
        if paramset_descriptions is None:
            return {}
        return paramset_descriptions.get(interface_id, {}).get(channel_address, {}).get(paramset_key, {})

    paramset_cache.get_paramset_descriptions = _get_paramset_descriptions

    cache_coordinator = MagicMock()
    cache_coordinator.paramset_descriptions = paramset_cache

    client_mock = MagicMock()
    client_mock.get_paramset = AsyncMock(side_effect=client_get_paramset_side_effect)

    client_coordinator = MagicMock()
    client_coordinator.has_client.return_value = True
    client_coordinator.get_client.return_value = client_mock

    coordinator_provider = MagicMock()
    coordinator_provider.cache_coordinator = cache_coordinator
    coordinator_provider.client_coordinator = client_coordinator
    coordinator_provider.device_registry = device_registry

    central_info = MagicMock()
    central_info.name = "test-central"

    task_scheduler = MagicMock()

    coordinator = DeviceCoordinator(
        central_info=central_info,
        client_provider=client_coordinator,
        config_provider=MagicMock(),
        coordinator_provider=coordinator_provider,
        data_cache_provider=MagicMock(),
        data_point_provider=MagicMock(),
        device_description_provider=MagicMock(),
        device_details_provider=MagicMock(),
        event_bus_provider=SimpleNamespace(event_bus=event_bus),
        event_publisher=MagicMock(),
        event_subscription_manager=MagicMock(),
        file_operations=MagicMock(),
        incident_recorder=incident_recorder,
        parameter_visibility_provider=MagicMock(),
        paramset_description_provider=paramset_cache,
        task_scheduler=task_scheduler,
    )

    return coordinator, event_bus.publish


class TestParamsetConsistencyCheck:
    """Tests for _check_paramset_consistency()."""

    @pytest.mark.asyncio
    async def test_device_unavailable_gracefully_handled(self) -> None:
        """Test that get_paramset failure doesn't crash the check."""
        device = _make_fake_device(
            address="VCU0000001",
            product_group=ProductGroup.HMIP,
            channels={
                "VCU0000001:1": _make_fake_channel(address="VCU0000001:1"),
            },
        )
        registry = _FakeDeviceRegistry(devices={"VCU0000001": device})

        paramset_descs = {
            "test-HmIP-RF": {
                "VCU0000001:1": {
                    ParamsetKey.MASTER: {
                        "PARAM_A": {"OPERATIONS": 3, "TYPE": "FLOAT"},
                    },
                },
            },
        }

        # Simulate device being unavailable
        async def _get_paramset(*, channel_address: str, **_kwargs: Any) -> dict[str, Any]:
            raise ConnectionError("Device unavailable")

        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
            paramset_descriptions=paramset_descs,
            client_get_paramset_side_effect=_get_paramset,
        )

        # Should not raise any exception
        await coordinator._check_paramset_consistency(
            interface_id="test-HmIP-RF",
            device_addresses={"VCU0000001"},
        )

        # No event should be published (device was skipped)
        publish_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_hmipw_devices_checked(self) -> None:
        """Test that HmIPW (wired) devices are also checked."""
        device = _make_fake_device(
            address="VCU0000001",
            product_group=ProductGroup.HMIPW,
            channels={
                "VCU0000001:1": _make_fake_channel(address="VCU0000001:1"),
            },
        )
        registry = _FakeDeviceRegistry(devices={"VCU0000001": device})

        paramset_descs = {
            "test-HmIPW": {
                "VCU0000001:1": {
                    ParamsetKey.MASTER: {
                        "CLIMATE_FUNCTION": {"OPERATIONS": 3, "TYPE": "INTEGER"},
                    },
                },
            },
        }

        async def _get_paramset(*, channel_address: str, **_kwargs: Any) -> dict[str, Any]:
            return {}  # CLIMATE_FUNCTION missing

        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
            paramset_descriptions=paramset_descs,
            client_get_paramset_side_effect=_get_paramset,
        )

        await coordinator._check_paramset_consistency(
            interface_id="test-HmIPW",
            device_addresses={"VCU0000001"},
        )

        # HmIPW device should be checked and issue published
        publish_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_inconsistency_detected_for_hmip(self) -> None:
        """Test inconsistency detection for HmIP device with missing parameters."""
        device = _make_fake_device(
            address="VCU0000001",
            product_group=ProductGroup.HMIP,
            channels={
                "VCU0000001:5": _make_fake_channel(address="VCU0000001:5"),
            },
        )
        registry = _FakeDeviceRegistry(devices={"VCU0000001": device})

        # Description lists CHANNEL_OPERATION_MODE, but actual paramset doesn't have it
        paramset_descs = {
            "test-HmIP-RF": {
                "VCU0000001:5": {
                    ParamsetKey.MASTER: {
                        "PARAM_A": {"OPERATIONS": 3, "TYPE": "FLOAT"},
                        "CHANNEL_OPERATION_MODE": {"OPERATIONS": 3, "TYPE": "INTEGER"},
                    },
                },
            },
        }

        async def _get_paramset(*, channel_address: str, **_kwargs: Any) -> dict[str, Any]:
            return {"PARAM_A": 1.0}  # CHANNEL_OPERATION_MODE missing

        incident_recorder = MagicMock()
        incident_recorder.record_incident = AsyncMock()

        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
            paramset_descriptions=paramset_descs,
            client_get_paramset_side_effect=_get_paramset,
            incident_recorder=incident_recorder,
        )

        await coordinator._check_paramset_consistency(
            interface_id="test-HmIP-RF",
            device_addresses={"VCU0000001"},
        )

        # Verify incident was recorded
        incident_recorder.record_incident.assert_awaited_once()
        call_kwargs = incident_recorder.record_incident.await_args.kwargs
        assert call_kwargs["incident_type"] == IncidentType.PARAMSET_INCONSISTENCY
        assert call_kwargs["severity"] == IncidentSeverity.WARNING
        assert "VCU0000001" in call_kwargs["message"]
        assert "VCU0000001:5:CHANNEL_OPERATION_MODE" in call_kwargs["context"]["missing_parameters"]

        # Verify integration issue was published
        publish_mock.assert_awaited_once()
        event = publish_mock.await_args.kwargs["event"]
        assert isinstance(event, SystemStatusChangedEvent)
        assert len(event.issues) == 1
        issue = event.issues[0]
        assert issue.issue_type == IntegrationIssueType.PARAMSET_INCONSISTENCY
        assert issue.severity == IntegrationIssueSeverity.WARNING
        assert "VCU0000001" in issue.device_addresses
        assert "VCU0000001:5:CHANNEL_OPERATION_MODE" in issue.missing_parameters

    @pytest.mark.asyncio
    async def test_multiple_channels_aggregated(self) -> None:
        """Test that inconsistencies from multiple channels are aggregated per device."""
        device = _make_fake_device(
            address="VCU0000001",
            product_group=ProductGroup.HMIP,
            channels={
                "VCU0000001:1": _make_fake_channel(address="VCU0000001:1"),
                "VCU0000001:5": _make_fake_channel(address="VCU0000001:5"),
            },
        )
        registry = _FakeDeviceRegistry(devices={"VCU0000001": device})

        paramset_descs = {
            "test-HmIP-RF": {
                "VCU0000001:1": {
                    ParamsetKey.MASTER: {
                        "DISABLE_MSG_TO_AC": {"OPERATIONS": 3, "TYPE": "BOOL"},
                    },
                },
                "VCU0000001:5": {
                    ParamsetKey.MASTER: {
                        "CHANNEL_OPERATION_MODE": {"OPERATIONS": 3, "TYPE": "INTEGER"},
                    },
                },
            },
        }

        # Both channels have missing parameters
        async def _get_paramset(*, channel_address: str, **_kwargs: Any) -> dict[str, Any]:
            return {}  # All params missing

        incident_recorder = MagicMock()
        incident_recorder.record_incident = AsyncMock()

        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
            paramset_descriptions=paramset_descs,
            client_get_paramset_side_effect=_get_paramset,
            incident_recorder=incident_recorder,
        )

        await coordinator._check_paramset_consistency(
            interface_id="test-HmIP-RF",
            device_addresses={"VCU0000001"},
        )

        # Single incident per device, aggregating all missing params
        incident_recorder.record_incident.assert_awaited_once()
        call_kwargs = incident_recorder.record_incident.await_args.kwargs
        missing = call_kwargs["context"]["missing_parameters"]
        assert "VCU0000001:1:DISABLE_MSG_TO_AC" in missing
        assert "VCU0000001:5:CHANNEL_OPERATION_MODE" in missing

        # Single integration issue with all missing parameters
        publish_mock.assert_awaited_once()
        event = publish_mock.await_args.kwargs["event"]
        issue = event.issues[0]
        assert len(issue.missing_parameters) == 2

    @pytest.mark.asyncio
    async def test_no_incident_recorder_graceful(self) -> None:
        """Test that check works without incident recorder (recorder is optional)."""
        device = _make_fake_device(
            address="VCU0000001",
            product_group=ProductGroup.HMIP,
            channels={
                "VCU0000001:1": _make_fake_channel(address="VCU0000001:1"),
            },
        )
        registry = _FakeDeviceRegistry(devices={"VCU0000001": device})

        paramset_descs = {
            "test-HmIP-RF": {
                "VCU0000001:1": {
                    ParamsetKey.MASTER: {
                        "MISSING_PARAM": {"OPERATIONS": 3, "TYPE": "BOOL"},
                    },
                },
            },
        }

        async def _get_paramset(*, channel_address: str, **_kwargs: Any) -> dict[str, Any]:
            return {}

        # No incident_recorder provided
        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
            paramset_descriptions=paramset_descs,
            client_get_paramset_side_effect=_get_paramset,
            incident_recorder=None,
        )

        # Should not crash, integration issue should still be published
        await coordinator._check_paramset_consistency(
            interface_id="test-HmIP-RF",
            device_addresses={"VCU0000001"},
        )

        # Integration issue still published even without incident recorder
        publish_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_inconsistency_detected(self) -> None:
        """Test no incidents when paramset matches description."""
        device = _make_fake_device(
            address="VCU0000001",
            product_group=ProductGroup.HMIP,
            channels={
                "VCU0000001:1": _make_fake_channel(address="VCU0000001:1"),
            },
        )
        registry = _FakeDeviceRegistry(devices={"VCU0000001": device})

        paramset_descs = {
            "test-HmIP-RF": {
                "VCU0000001:1": {
                    ParamsetKey.MASTER: {
                        "PARAM_A": {"OPERATIONS": 3, "TYPE": "FLOAT"},
                        "PARAM_B": {"OPERATIONS": 3, "TYPE": "BOOL"},
                    },
                },
            },
        }

        # Actual paramset contains all expected parameters
        async def _get_paramset(*, channel_address: str, **_kwargs: Any) -> dict[str, Any]:
            return {"PARAM_A": 1.0, "PARAM_B": True}

        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
            paramset_descriptions=paramset_descs,
            client_get_paramset_side_effect=_get_paramset,
        )

        await coordinator._check_paramset_consistency(
            interface_id="test-HmIP-RF",
            device_addresses={"VCU0000001"},
        )

        # No event should be published
        publish_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_hmip_devices_skipped(self) -> None:
        """Test that BidCos-RF devices are not checked."""
        device = _make_fake_device(
            address="MEQ0000001",
            product_group=ProductGroup.HM,  # BidCos-RF
            channels={
                "MEQ0000001:1": _make_fake_channel(address="MEQ0000001:1"),
            },
        )
        registry = _FakeDeviceRegistry(devices={"MEQ0000001": device})

        paramset_descs = {
            "test-BidCos-RF": {
                "MEQ0000001:1": {
                    ParamsetKey.MASTER: {
                        "MISSING_PARAM": {"OPERATIONS": 3, "TYPE": "BOOL"},
                    },
                },
            },
        }

        # This should never be called since the device is BidCos-RF
        async def _get_paramset(*, channel_address: str, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("get_paramset should not be called for BidCos-RF devices")

        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
            paramset_descriptions=paramset_descs,
            client_get_paramset_side_effect=_get_paramset,
        )

        await coordinator._check_paramset_consistency(
            interface_id="test-BidCos-RF",
            device_addresses={"MEQ0000001"},
        )

        # No event should be published
        publish_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_operations_zero_params_excluded(self) -> None:
        """Test that parameters with OPERATIONS=0 are not flagged as missing."""
        device = _make_fake_device(
            address="VCU0000001",
            product_group=ProductGroup.HMIP,
            channels={
                "VCU0000001:1": _make_fake_channel(address="VCU0000001:1"),
            },
        )
        registry = _FakeDeviceRegistry(devices={"VCU0000001": device})

        paramset_descs = {
            "test-HmIP-RF": {
                "VCU0000001:1": {
                    ParamsetKey.MASTER: {
                        "VISIBLE_PARAM": {"OPERATIONS": 3, "TYPE": "FLOAT"},
                        "INTERNAL_PARAM": {"OPERATIONS": 0, "TYPE": "BOOL"},  # Internal
                    },
                },
            },
        }

        # Only VISIBLE_PARAM is in the actual paramset, INTERNAL_PARAM is missing
        # but should not be flagged because OPERATIONS=0
        async def _get_paramset(*, channel_address: str, **_kwargs: Any) -> dict[str, Any]:
            return {"VISIBLE_PARAM": 1.0}

        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
            paramset_descriptions=paramset_descs,
            client_get_paramset_side_effect=_get_paramset,
        )

        await coordinator._check_paramset_consistency(
            interface_id="test-HmIP-RF",
            device_addresses={"VCU0000001"},
        )

        # No event should be published (INTERNAL_PARAM is OPERATIONS=0)
        publish_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_device_address_skipped(self) -> None:
        """Test that unknown device addresses are silently skipped."""
        registry = _FakeDeviceRegistry(devices={})

        coordinator, publish_mock = _create_device_coordinator(
            device_registry=registry,
        )

        await coordinator._check_paramset_consistency(
            interface_id="test-HmIP-RF",
            device_addresses={"NONEXISTENT"},
        )

        publish_mock.assert_not_awaited()


class TestScheduleParamsetConsistencyCheck:
    """Tests for _schedule_paramset_consistency_check()."""

    def test_schedule_creates_task(self) -> None:
        """Test that scheduling creates a background task."""
        registry = _FakeDeviceRegistry()
        coordinator, _ = _create_device_coordinator(device_registry=registry)

        coordinator._schedule_paramset_consistency_check(
            interface_id="test-HmIP-RF",
            new_device_addresses={"test-HmIP-RF": {"VCU0000001"}},
        )

        coordinator._task_scheduler.create_task.assert_called_once()  # type: ignore[union-attr]
        call_kwargs = coordinator._task_scheduler.create_task.call_args.kwargs  # type: ignore[union-attr]
        assert "paramset_consistency_check" in call_kwargs["name"]
        # Close the unawaited coroutine to prevent RuntimeWarning
        call_kwargs["target"].close()

    def test_schedule_skips_unrelated_interface(self) -> None:
        """Test that scheduling is skipped for interfaces not in new_device_addresses."""
        registry = _FakeDeviceRegistry()
        coordinator, _ = _create_device_coordinator(device_registry=registry)

        coordinator._schedule_paramset_consistency_check(
            interface_id="test-HmIP-RF",
            new_device_addresses={"other-interface": {"VCU0000001"}},
        )

        coordinator._task_scheduler.create_task.assert_not_called()  # type: ignore[union-attr]


class TestIntegrationIssueParamsetFields:
    """Tests for IntegrationIssue paramset-related fields."""

    def test_issue_id_format(self) -> None:
        """Test issue_id format for paramset inconsistency."""
        issue = IntegrationIssue(
            issue_type=IntegrationIssueType.PARAMSET_INCONSISTENCY,
            severity=IntegrationIssueSeverity.WARNING,
            interface_id="ccu-HmIP-RF",
        )

        assert issue.issue_id == "paramset_inconsistency_ccu-HmIP-RF"
        assert issue.translation_key == "paramset_inconsistency"

    def test_missing_parameters_in_translation_placeholders(self) -> None:
        """Test that missing_parameters is included in translation placeholders."""
        issue = IntegrationIssue(
            issue_type=IntegrationIssueType.PARAMSET_INCONSISTENCY,
            severity=IntegrationIssueSeverity.WARNING,
            interface_id="test-HmIP-RF",
            device_addresses=("VCU0000001",),
            missing_parameters=("VCU0000001:5:CHANNEL_OPERATION_MODE", "VCU0000001:1:DISABLE_MSG_TO_AC"),
        )

        placeholders = issue.translation_placeholders
        assert placeholders["parameter_count"] == "2"
        assert "CHANNEL_OPERATION_MODE" in placeholders["missing_parameters"]
        assert "DISABLE_MSG_TO_AC" in placeholders["missing_parameters"]
        assert placeholders["device_count"] == "1"
        assert placeholders["device_addresses"] == "VCU0000001"
