# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Tests for service messages and alarm messages hub sensors and parsing."""

from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from aiohomematic.client.json_rpc import _parse_tab_separated
from aiohomematic.const import AlarmMessageData, DataPointCategory, HubValueType, ServiceMessageData
from aiohomematic.model.hub import HmAlarmMessagesSensor, HmServiceMessagesSensor, Hub

# =============================================================================
# Helper: _parse_tab_separated
# =============================================================================


class TestParseTabSeparated:
    """Tests for _parse_tab_separated helper."""

    def test_empty_string(self) -> None:
        """Return empty tuple for empty string."""
        assert _parse_tab_separated(value="") == ()

    def test_multiple_values(self) -> None:
        """Return tuple with all tab-separated values."""
        result = _parse_tab_separated(value="Kitchen\tLiving%20Room\tBedroom")
        assert result == ("Kitchen", "Living Room", "Bedroom")

    def test_single_value(self) -> None:
        """Return single-element tuple for value without tabs."""
        assert _parse_tab_separated(value="Kitchen") == ("Kitchen",)

    def test_trailing_empty_ignored(self) -> None:
        """Ignore empty segments from trailing tabs."""
        result = _parse_tab_separated(value="Room1\t\tRoom2")
        assert result == ("Room1", "Room2")

    def test_uri_encoded_values(self) -> None:
        """Decode URI-encoded values correctly (ISO-8859-1 encoding from ReGa)."""
        result = _parse_tab_separated(value="K%FCche\tWohnzimmer")
        assert result == ("Küche", "Wohnzimmer")


# =============================================================================
# Dataclass construction
# =============================================================================


class TestServiceMessageData:
    """Tests for ServiceMessageData dataclass."""

    def test_full_construction(self) -> None:
        """Create with all fields."""
        msg = ServiceMessageData(
            msg_id="42",
            name="STICKY_UNREACH",
            timestamp="2026-03-25 10:00:00",
            msg_type=1,
            address="MEQ0123456",
            device_name="Thermostat",
            last_timestamp="2026-03-25 12:00:00",
            counter=3,
            rooms=("Kitchen", "Living Room"),
            functions=("Heating",),
            quittable=True,
        )
        assert msg.counter == 3
        assert msg.rooms == ("Kitchen", "Living Room")
        assert msg.functions == ("Heating",)
        assert msg.quittable is True

    def test_minimal_construction(self) -> None:
        """Create with required fields only."""
        msg = ServiceMessageData(msg_id="1", name="test", timestamp="2026-01-01", msg_type=0)
        assert msg.msg_id == "1"
        assert msg.rooms == ()
        assert msg.functions == ()
        assert msg.quittable is False
        assert msg.counter == 0
        assert msg.last_timestamp == ""


class TestAlarmMessageData:
    """Tests for AlarmMessageData dataclass."""

    def test_full_construction(self) -> None:
        """Create with all fields."""
        alarm = AlarmMessageData(
            alarm_id="99",
            name="Smoke Detector",
            description="Smoke detected in kitchen",
            timestamp="2026-03-25 10:00:00",
            last_timestamp="2026-03-25 12:00:00",
            counter=5,
            last_trigger="Trigger at 12:00",
            rooms=("Kitchen",),
        )
        assert alarm.counter == 5
        assert alarm.rooms == ("Kitchen",)
        assert alarm.last_trigger == "Trigger at 12:00"

    def test_minimal_construction(self) -> None:
        """Create with required fields only."""
        alarm = AlarmMessageData(alarm_id="1", name="Fire Alarm")
        assert alarm.alarm_id == "1"
        assert alarm.description == ""
        assert alarm.rooms == ()
        assert alarm.counter == 0
        assert alarm.last_trigger == ""


# =============================================================================
# Hub sensor helpers
# =============================================================================


def _make_fake_protocols() -> dict[str, Any]:
    """Create minimal fake protocol implementations for hub sensor construction."""
    config_provider = SimpleNamespace(config=SimpleNamespace(central_id="test-central"))
    central_info = SimpleNamespace(name="test-central", available=True)
    event_bus_provider = SimpleNamespace(event_bus=SimpleNamespace())
    event_publisher = SimpleNamespace(
        publish_system_event=lambda **kwargs: None,
    )
    task_scheduler = SimpleNamespace(create_task=lambda **kwargs: None)
    paramset_description_provider = SimpleNamespace(
        is_in_multiple_channels=lambda **kwargs: False,
    )
    parameter_visibility_provider = SimpleNamespace()

    return {
        "config_provider": config_provider,
        "central_info": central_info,
        "event_bus_provider": event_bus_provider,
        "event_publisher": event_publisher,
        "task_scheduler": task_scheduler,
        "paramset_description_provider": paramset_description_provider,
        "parameter_visibility_provider": parameter_visibility_provider,
    }


# =============================================================================
# HmServiceMessagesSensor
# =============================================================================


class TestHmServiceMessagesSensor:
    """Tests for HmServiceMessagesSensor."""

    def test_empty_update(self) -> None:
        """Updating with empty tuple should set value to 0."""
        sensor = HmServiceMessagesSensor(**_make_fake_protocols())
        messages = (ServiceMessageData(msg_id="1", name="UNREACH", timestamp="2026-01-01", msg_type=0),)

        sensor.update_data(messages=messages, write_at=datetime.now())
        assert sensor.value == 1

        sensor.update_data(messages=(), write_at=datetime.now())
        assert sensor.value == 0

    def test_initial_state(self) -> None:
        """Sensor should start with zero count and state_uncertain."""
        sensor = HmServiceMessagesSensor(**_make_fake_protocols())

        assert sensor.value == 0
        assert sensor.messages == ()
        assert sensor.state_uncertain is True
        assert sensor.data_type == HubValueType.INTEGER
        assert sensor.translation_key == "service_messages"
        assert sensor._category == DataPointCategory.HUB_SENSOR

    def test_update_data_changed(self) -> None:
        """Updating with different data should update modified_at."""
        sensor = HmServiceMessagesSensor(**_make_fake_protocols())
        msg1 = (ServiceMessageData(msg_id="1", name="UNREACH", timestamp="2026-01-01", msg_type=0),)
        msg2 = (
            ServiceMessageData(msg_id="1", name="UNREACH", timestamp="2026-01-01", msg_type=0),
            ServiceMessageData(msg_id="2", name="LOW_BAT", timestamp="2026-01-01", msg_type=0),
        )

        t1 = datetime(2026, 3, 25, 10, 0, 0)
        t2 = datetime(2026, 3, 25, 10, 5, 0)

        sensor.update_data(messages=msg1, write_at=t1)
        sensor.update_data(messages=msg2, write_at=t2)

        assert sensor.value == 2
        assert sensor.modified_at == t2

    def test_update_data_sets_messages(self) -> None:
        """Updating data should set messages and clear state_uncertain."""
        sensor = HmServiceMessagesSensor(**_make_fake_protocols())
        messages = (
            ServiceMessageData(msg_id="1", name="UNREACH", timestamp="2026-01-01", msg_type=0),
            ServiceMessageData(msg_id="2", name="LOW_BAT", timestamp="2026-01-01", msg_type=0),
        )

        sensor.update_data(messages=messages, write_at=datetime.now())

        assert sensor.value == 2
        assert sensor.messages == messages
        assert sensor.state_uncertain is False

    def test_update_data_unchanged(self) -> None:
        """Re-updating with same data should not change modified_at."""
        sensor = HmServiceMessagesSensor(**_make_fake_protocols())
        messages = (ServiceMessageData(msg_id="1", name="UNREACH", timestamp="2026-01-01", msg_type=0),)

        t1 = datetime(2026, 3, 25, 10, 0, 0)
        t2 = datetime(2026, 3, 25, 10, 5, 0)

        sensor.update_data(messages=messages, write_at=t1)
        modified_after_first = sensor.modified_at

        sensor.update_data(messages=messages, write_at=t2)
        modified_after_second = sensor.modified_at

        assert modified_after_first == modified_after_second


# =============================================================================
# HmAlarmMessagesSensor
# =============================================================================


class TestHmAlarmMessagesSensor:
    """Tests for HmAlarmMessagesSensor."""

    def test_empty_update(self) -> None:
        """Updating with empty tuple should set value to 0."""
        sensor = HmAlarmMessagesSensor(**_make_fake_protocols())
        alarms = (AlarmMessageData(alarm_id="1", name="Fire"),)

        sensor.update_data(alarms=alarms, write_at=datetime.now())
        assert sensor.value == 1

        sensor.update_data(alarms=(), write_at=datetime.now())
        assert sensor.value == 0

    def test_initial_state(self) -> None:
        """Sensor should start with zero count and state_uncertain."""
        sensor = HmAlarmMessagesSensor(**_make_fake_protocols())

        assert sensor.value == 0
        assert sensor.alarms == ()
        assert sensor.state_uncertain is True
        assert sensor.data_type == HubValueType.INTEGER
        assert sensor.translation_key == "alarm_messages"
        assert sensor._category == DataPointCategory.HUB_SENSOR

    def test_update_data_changed(self) -> None:
        """Updating with different data should update modified_at."""
        sensor = HmAlarmMessagesSensor(**_make_fake_protocols())
        alarms1 = (AlarmMessageData(alarm_id="1", name="Fire"),)
        alarms2 = (
            AlarmMessageData(alarm_id="1", name="Fire"),
            AlarmMessageData(alarm_id="2", name="Water"),
        )

        t1 = datetime(2026, 3, 25, 10, 0, 0)
        t2 = datetime(2026, 3, 25, 10, 5, 0)

        sensor.update_data(alarms=alarms1, write_at=t1)
        sensor.update_data(alarms=alarms2, write_at=t2)

        assert sensor.value == 2
        assert sensor.modified_at == t2

    def test_update_data_sets_alarms(self) -> None:
        """Updating data should set alarms and clear state_uncertain."""
        sensor = HmAlarmMessagesSensor(**_make_fake_protocols())
        alarms = (
            AlarmMessageData(alarm_id="1", name="Fire Alarm"),
            AlarmMessageData(alarm_id="2", name="Water Alarm"),
        )

        sensor.update_data(alarms=alarms, write_at=datetime.now())

        assert sensor.value == 2
        assert sensor.alarms == alarms
        assert sensor.state_uncertain is False

    def test_update_data_unchanged(self) -> None:
        """Re-updating with same data should not change modified_at."""
        sensor = HmAlarmMessagesSensor(**_make_fake_protocols())
        alarms = (AlarmMessageData(alarm_id="1", name="Fire Alarm"),)

        t1 = datetime(2026, 3, 25, 10, 0, 0)
        t2 = datetime(2026, 3, 25, 10, 5, 0)

        sensor.update_data(alarms=alarms, write_at=t1)
        modified_after_first = sensor.modified_at

        sensor.update_data(alarms=alarms, write_at=t2)
        modified_after_second = sensor.modified_at

        assert modified_after_first == modified_after_second


# =============================================================================
# Hub integration: fetch methods create and update sensors
# =============================================================================


class TestHubFetchServiceMessages:
    """Tests for Hub.fetch_service_messages_data integration."""

    @pytest.mark.asyncio
    async def test_fetch_creates_sensor_and_publishes_event(self) -> None:
        """First fetch should create the sensor and publish HUB_REFRESHED."""

        protocols = _make_fake_protocols()
        published_events: list[Any] = []
        protocols["event_publisher"] = SimpleNamespace(
            publish_system_event=lambda **kwargs: published_events.append(kwargs),
        )
        fake_client = SimpleNamespace(
            get_service_messages=AsyncMock(
                return_value=(ServiceMessageData(msg_id="1", name="UNREACH", timestamp="2026-01-01", msg_type=0),)
            ),
        )
        hub = Hub(
            config_provider=protocols["config_provider"],
            central_info=SimpleNamespace(name="test", available=True, model="CCU"),
            client_provider=SimpleNamespace(),
            hub_data_point_manager=SimpleNamespace(),
            primary_client_provider=SimpleNamespace(primary_client=fake_client),
            event_publisher=protocols["event_publisher"],
            event_bus_provider=protocols["event_bus_provider"],
            task_scheduler=protocols["task_scheduler"],
            paramset_description_provider=protocols["paramset_description_provider"],
            parameter_visibility_provider=protocols["parameter_visibility_provider"],
            channel_lookup=SimpleNamespace(),
            hub_data_fetcher=SimpleNamespace(),
            metrics_provider=SimpleNamespace(),
            health_tracker=SimpleNamespace(),
        )  # type: ignore[arg-type]

        await hub._update_service_messages_data_point()

        assert hub.service_messages_dp is not None
        assert hub.service_messages_dp.value == 1
        assert len(published_events) == 1
        assert published_events[0]["system_event"].value == "hubDataPointRefreshed"

    @pytest.mark.asyncio
    async def test_second_fetch_updates_without_new_event(self) -> None:
        """Second fetch should update existing sensor without publishing HUB_REFRESHED."""

        protocols = _make_fake_protocols()
        published_events: list[Any] = []
        protocols["event_publisher"] = SimpleNamespace(
            publish_system_event=lambda **kwargs: published_events.append(kwargs),
        )
        msg1 = (ServiceMessageData(msg_id="1", name="UNREACH", timestamp="2026-01-01", msg_type=0),)
        msg2 = (
            ServiceMessageData(msg_id="1", name="UNREACH", timestamp="2026-01-01", msg_type=0),
            ServiceMessageData(msg_id="2", name="LOW_BAT", timestamp="2026-01-01", msg_type=0),
        )
        call_count = 0

        async def _get_messages(**kwargs: Any) -> tuple[ServiceMessageData, ...]:
            nonlocal call_count
            call_count += 1
            return msg1 if call_count == 1 else msg2

        fake_client = SimpleNamespace(get_service_messages=_get_messages)
        hub = Hub(
            config_provider=protocols["config_provider"],
            central_info=SimpleNamespace(name="test", available=True, model="CCU"),
            client_provider=SimpleNamespace(),
            hub_data_point_manager=SimpleNamespace(),
            primary_client_provider=SimpleNamespace(primary_client=fake_client),
            event_publisher=protocols["event_publisher"],
            event_bus_provider=protocols["event_bus_provider"],
            task_scheduler=protocols["task_scheduler"],
            paramset_description_provider=protocols["paramset_description_provider"],
            parameter_visibility_provider=protocols["parameter_visibility_provider"],
            channel_lookup=SimpleNamespace(),
            hub_data_fetcher=SimpleNamespace(),
            metrics_provider=SimpleNamespace(),
            health_tracker=SimpleNamespace(),
        )  # type: ignore[arg-type]

        await hub._update_service_messages_data_point()
        await hub._update_service_messages_data_point()

        assert hub.service_messages_dp is not None
        assert hub.service_messages_dp.value == 2
        # Only one HUB_REFRESHED event (from the first call)
        assert len(published_events) == 1


class TestHubFetchAlarmMessages:
    """Tests for Hub.fetch_alarm_messages_data integration."""

    @pytest.mark.asyncio
    async def test_fetch_creates_sensor_and_publishes_event(self) -> None:
        """First fetch should create the sensor and publish HUB_REFRESHED."""

        protocols = _make_fake_protocols()
        published_events: list[Any] = []
        protocols["event_publisher"] = SimpleNamespace(
            publish_system_event=lambda **kwargs: published_events.append(kwargs),
        )
        fake_client = SimpleNamespace(
            get_alarm_messages=AsyncMock(return_value=(AlarmMessageData(alarm_id="1", name="Fire Alarm"),)),
        )
        hub = Hub(
            config_provider=protocols["config_provider"],
            central_info=SimpleNamespace(name="test", available=True, model="CCU"),
            client_provider=SimpleNamespace(),
            hub_data_point_manager=SimpleNamespace(),
            primary_client_provider=SimpleNamespace(primary_client=fake_client),
            event_publisher=protocols["event_publisher"],
            event_bus_provider=protocols["event_bus_provider"],
            task_scheduler=protocols["task_scheduler"],
            paramset_description_provider=protocols["paramset_description_provider"],
            parameter_visibility_provider=protocols["parameter_visibility_provider"],
            channel_lookup=SimpleNamespace(),
            hub_data_fetcher=SimpleNamespace(),
            metrics_provider=SimpleNamespace(),
            health_tracker=SimpleNamespace(),
        )  # type: ignore[arg-type]

        await hub._update_alarm_messages_data_point()

        assert hub.alarm_messages_dp is not None
        assert hub.alarm_messages_dp.value == 1
        assert len(published_events) == 1

    @pytest.mark.asyncio
    async def test_no_client_returns_early(self) -> None:
        """If no primary client, the method should return without error."""

        protocols = _make_fake_protocols()
        hub = Hub(
            config_provider=protocols["config_provider"],
            central_info=SimpleNamespace(name="test", available=True, model="CCU"),
            client_provider=SimpleNamespace(),
            hub_data_point_manager=SimpleNamespace(),
            primary_client_provider=SimpleNamespace(primary_client=None),
            event_publisher=protocols["event_publisher"],
            event_bus_provider=protocols["event_bus_provider"],
            task_scheduler=protocols["task_scheduler"],
            paramset_description_provider=protocols["paramset_description_provider"],
            parameter_visibility_provider=protocols["parameter_visibility_provider"],
            channel_lookup=SimpleNamespace(),
            hub_data_fetcher=SimpleNamespace(),
            metrics_provider=SimpleNamespace(),
            health_tracker=SimpleNamespace(),
        )  # type: ignore[arg-type]

        await hub._update_alarm_messages_data_point()

        assert hub.alarm_messages_dp is None
