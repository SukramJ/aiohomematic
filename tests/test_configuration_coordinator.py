# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""Test the ConfigurationCoordinator facade."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.central.coordinators import (
    ConfigurableDevice,
    ConfigurableDeviceChannel,
    ConfigurationCoordinator,
    CopyParamsetResult,
    MaintenanceData,
)
from aiohomematic.central.coordinators.configuration import ConfigurableChannel, PutParamsetResult
from aiohomematic.const import CallSource, Flag, Interface, Operations, ParameterData, ParameterType, ParamsetKey
from aiohomematic.exceptions import BaseHomematicException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pd(**overrides: object) -> ParameterData:
    """Build a ParameterData dict with overrides."""
    pd: dict[str, object] = {}
    pd.update(overrides)
    return pd  # type: ignore[return-value]


def _make_coordinator(
    *,
    channel_paramset_descriptions: dict[ParamsetKey, dict[str, ParameterData]] | None = None,
    device_with_channels: dict[str, dict[str, Any]] | None = None,
    parameter_data: ParameterData | None = None,
    get_paramset_return: dict[str, Any] | None = None,
    devices: tuple[Any, ...] = (),
) -> tuple[ConfigurationCoordinator, MagicMock, MagicMock, MagicMock]:
    """Build a ConfigurationCoordinator with mocked providers."""
    client_provider = MagicMock()
    device_description_provider = MagicMock()
    paramset_description_provider = MagicMock()
    device_registry = MagicMock()

    # Configure paramset description provider
    paramset_description_provider.get_channel_paramset_descriptions.return_value = channel_paramset_descriptions or {}
    paramset_description_provider.get_parameter_data.return_value = parameter_data

    # Configure device description provider
    device_description_provider.get_device_with_channels.return_value = device_with_channels or {}

    # Configure client provider
    mock_client = AsyncMock()
    mock_client.get_paramset.return_value = get_paramset_return or {}
    mock_client.put_paramset.return_value = None
    client_provider.get_client.return_value = mock_client

    # Configure device registry
    device_registry.devices = devices

    coordinator = ConfigurationCoordinator(
        client_provider=client_provider,
        device_description_provider=device_description_provider,
        device_registry=device_registry,
        paramset_description_provider=paramset_description_provider,
    )
    return coordinator, client_provider, device_description_provider, paramset_description_provider


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestConfigurableChannel:
    """Test ConfigurableChannel dataclass."""

    def test_creation(self) -> None:
        """Test ConfigurableChannel can be created."""
        channel = ConfigurableChannel(
            address="VCU0000001:1",
            channel_type="CLIMATECONTROL_RT_TRANSCEIVER",
            paramset_keys=(ParamsetKey.MASTER, ParamsetKey.VALUES),
        )
        assert channel.address == "VCU0000001:1"
        assert channel.channel_type == "CLIMATECONTROL_RT_TRANSCEIVER"
        assert channel.paramset_keys == (ParamsetKey.MASTER, ParamsetKey.VALUES)

    def test_frozen(self) -> None:
        """Test ConfigurableChannel is frozen."""
        channel = ConfigurableChannel(
            address="VCU0000001:1",
            channel_type="SWITCH",
            paramset_keys=(ParamsetKey.VALUES,),
        )
        with pytest.raises(AttributeError):
            channel.address = "other"  # type: ignore[misc]


class TestPutParamsetResult:
    """Test PutParamsetResult dataclass."""

    def test_failure_with_errors(self) -> None:
        """Test failure result with validation errors."""
        result = PutParamsetResult(
            success=False,
            validated=True,
            validation_errors={"TEMP": "Value 99 is above maximum 30.5."},
        )
        assert result.success is False
        assert "TEMP" in result.validation_errors

    def test_frozen(self) -> None:
        """Test PutParamsetResult is frozen."""
        result = PutParamsetResult(success=True, validated=True, validation_errors={})
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_success(self) -> None:
        """Test successful result."""
        result = PutParamsetResult(success=True, validated=True, validation_errors={})
        assert result.success is True
        assert result.validated is True
        assert result.validation_errors == {}


# ---------------------------------------------------------------------------
# get_paramset_description
# ---------------------------------------------------------------------------


class TestGetParamsetDescription:
    """Test ConfigurationCoordinator.get_paramset_description."""

    def test_delegates_to_provider(self) -> None:
        """Test provider is called with correct arguments."""
        coordinator, _, _, psp = _make_coordinator()

        coordinator.get_paramset_description(
            interface_id="iface-1",
            channel_address="VCU0000001:2",
            paramset_key=ParamsetKey.MASTER,
        )
        psp.get_channel_paramset_descriptions.assert_called_once_with(
            interface_id="iface-1",
            channel_address="VCU0000001:2",
        )

    def test_returns_description(self) -> None:
        """Test return paramset description for existing key."""
        temp_pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5)
        coordinator, _, _, _ = _make_coordinator(
            channel_paramset_descriptions={
                ParamsetKey.MASTER: {"TEMP_MIN": temp_pd},
                ParamsetKey.VALUES: {"ACTUAL_TEMPERATURE": _make_pd(TYPE=ParameterType.FLOAT)},
            },
        )

        result = coordinator.get_paramset_description(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
        )
        assert "TEMP_MIN" in result
        assert result["TEMP_MIN"] == temp_pd

    def test_returns_empty_for_missing_key(self) -> None:
        """Test return empty dict for unknown paramset key."""
        coordinator, _, _, _ = _make_coordinator(
            channel_paramset_descriptions={
                ParamsetKey.MASTER: {"TEMP": _make_pd(TYPE=ParameterType.FLOAT)},
            },
        )

        result = coordinator.get_paramset_description(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
        )
        assert result == {}


# ---------------------------------------------------------------------------
# get_link_paramset_description
# ---------------------------------------------------------------------------


class TestGetLinkParamsetDescription:
    """Test ConfigurationCoordinator.get_link_paramset_description."""

    @pytest.mark.asyncio
    async def test_delegates_to_client(self) -> None:
        """Test delegation to client with LINK paramset key."""
        pd = _make_pd()
        coordinator, _, _, _ = _make_coordinator()
        mock_client = coordinator._client_provider.get_client()
        mock_client.get_paramset_description_on_demand.return_value = {"PARAM": pd}

        result = await coordinator.get_link_paramset_description(
            interface_id="IF_ID",
            channel_address="VCU0000001:1",
        )

        assert result == {"PARAM": pd}
        mock_client.get_paramset_description_on_demand.assert_called_once_with(
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.LINK,
        )

    @pytest.mark.asyncio
    async def test_returns_empty_when_unavailable(self) -> None:
        """Test empty dict returned when no LINK description available."""
        coordinator, _, _, _ = _make_coordinator()
        mock_client = coordinator._client_provider.get_client()
        mock_client.get_paramset_description_on_demand.return_value = {}

        result = await coordinator.get_link_paramset_description(
            interface_id="IF_ID",
            channel_address="VCU0000001:1",
        )

        assert result == {}


# ---------------------------------------------------------------------------
# get_all_paramset_descriptions
# ---------------------------------------------------------------------------


class TestGetAllParamsetDescriptions:
    """Test ConfigurationCoordinator.get_all_paramset_descriptions."""

    def test_returns_all_descriptions(self) -> None:
        """Test return all paramset descriptions."""
        descriptions = {
            ParamsetKey.MASTER: {"TEMP_MIN": _make_pd(TYPE=ParameterType.FLOAT)},
            ParamsetKey.VALUES: {"ACTUAL_TEMPERATURE": _make_pd(TYPE=ParameterType.FLOAT)},
        }
        coordinator, _, _, _ = _make_coordinator(channel_paramset_descriptions=descriptions)

        result = coordinator.get_all_paramset_descriptions(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
        )
        assert ParamsetKey.MASTER in result
        assert ParamsetKey.VALUES in result

    def test_returns_empty_for_unknown_channel(self) -> None:
        """Test return empty dict for channel with no descriptions."""
        coordinator, _, _, _ = _make_coordinator()

        result = coordinator.get_all_paramset_descriptions(
            interface_id="ccu-main",
            channel_address="UNKNOWN:0",
        )
        assert result == {}


# ---------------------------------------------------------------------------
# get_paramset (async)
# ---------------------------------------------------------------------------


class TestGetParamset:
    """Test ConfigurationCoordinator.get_paramset."""

    @pytest.mark.asyncio
    async def test_delegates_to_client(self) -> None:
        """Test client.get_paramset is called with correct arguments."""
        coordinator, cp, _, _ = _make_coordinator()

        await coordinator.get_paramset(
            interface_id="iface-1",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
        )

        mock_client = cp.get_client.return_value
        mock_client.get_paramset.assert_called_once_with(
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            call_source=CallSource.MANUAL_OR_SCHEDULED,
        )

    @pytest.mark.asyncio
    async def test_returns_values(self) -> None:
        """Test return live paramset values."""
        coordinator, _, _, _ = _make_coordinator(
            get_paramset_return={"ACTUAL_TEMPERATURE": 21.5, "SET_POINT": 22.0},
        )

        result = await coordinator.get_paramset(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
        )
        assert result == {"ACTUAL_TEMPERATURE": 21.5, "SET_POINT": 22.0}

    @pytest.mark.asyncio
    async def test_uses_correct_call_source(self) -> None:
        """Test MANUAL_OR_SCHEDULED call source is used."""
        coordinator, cp, _, _ = _make_coordinator()

        await coordinator.get_paramset(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
        )

        mock_client = cp.get_client.return_value
        call_args = mock_client.get_paramset.call_args
        assert call_args.kwargs["call_source"] == CallSource.MANUAL_OR_SCHEDULED


# ---------------------------------------------------------------------------
# put_paramset (async)
# ---------------------------------------------------------------------------


class TestPutParamset:
    """Test ConfigurationCoordinator.put_paramset."""

    @pytest.mark.asyncio
    async def test_delegates_to_client(self) -> None:
        """Test client.put_paramset is called with correct arguments."""
        coordinator, cp, _, _ = _make_coordinator(
            channel_paramset_descriptions={
                ParamsetKey.MASTER: {"TEMP": _make_pd(TYPE=ParameterType.FLOAT, MIN=0.0, MAX=30.0)},
            },
        )

        await coordinator.put_paramset(
            interface_id="iface-1",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            values={"TEMP": 20.0},
        )

        mock_client = cp.get_client.return_value
        mock_client.put_paramset.assert_called_once_with(
            channel_address="VCU0000001:1",
            paramset_key_or_link_address=ParamsetKey.MASTER,
            values={"TEMP": 20.0},
        )

    @pytest.mark.asyncio
    async def test_empty_values_succeeds(self) -> None:
        """Test writing empty values dict succeeds."""
        coordinator, _, _, _ = _make_coordinator(
            channel_paramset_descriptions={ParamsetKey.MASTER: {}},
        )

        result = await coordinator.put_paramset(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            values={},
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_skip_validation(self) -> None:
        """Test skip validation writes directly to backend."""
        coordinator, cp, _, _ = _make_coordinator()

        result = await coordinator.put_paramset(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            values={"ANYTHING": "value"},
            validate=False,
        )

        assert result.success is True
        assert result.validated is False
        mock_client = cp.get_client.return_value
        mock_client.put_paramset.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_with_validation(self) -> None:
        """Test successful write with validation enabled."""
        temp_pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5)
        coordinator, _, _, _ = _make_coordinator(
            channel_paramset_descriptions={
                ParamsetKey.MASTER: {"TEMP_MIN": temp_pd},
            },
        )

        result = await coordinator.put_paramset(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            values={"TEMP_MIN": 10.0},
            validate=True,
        )
        assert result.success is True
        assert result.validated is True
        assert result.validation_errors == {}

    @pytest.mark.asyncio
    async def test_unknown_param_fails_validation(self) -> None:
        """Test unknown parameter fails validation."""
        coordinator, cp, _, _ = _make_coordinator(
            channel_paramset_descriptions={
                ParamsetKey.MASTER: {"TEMP_MIN": _make_pd(TYPE=ParameterType.FLOAT)},
            },
        )

        result = await coordinator.put_paramset(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            values={"NONEXISTENT": 42},
            validate=True,
        )

        assert result.success is False
        assert "NONEXISTENT" in result.validation_errors
        mock_client = cp.get_client.return_value
        mock_client.put_paramset.assert_not_called()

    @pytest.mark.asyncio
    async def test_validation_failure_skips_write(self) -> None:
        """Test validation failure prevents backend write."""
        temp_pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5)
        coordinator, cp, _, _ = _make_coordinator(
            channel_paramset_descriptions={
                ParamsetKey.MASTER: {"TEMP_MIN": temp_pd},
            },
        )

        result = await coordinator.put_paramset(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            values={"TEMP_MIN": 99.0},
            validate=True,
        )

        assert result.success is False
        assert result.validated is True
        assert "TEMP_MIN" in result.validation_errors
        # Verify backend was NOT called
        mock_client = cp.get_client.return_value
        mock_client.put_paramset.assert_not_called()


# ---------------------------------------------------------------------------
# get_configurable_channels
# ---------------------------------------------------------------------------


class TestGetConfigurableChannels:
    """Test ConfigurationCoordinator.get_configurable_channels."""

    def test_delegates_to_provider(self) -> None:
        """Test device_description_provider is called with correct arguments."""
        coordinator, _, ddp, _ = _make_coordinator()

        coordinator.get_configurable_channels(
            interface_id="iface-1",
            device_address="VCU1234567",
        )
        ddp.get_device_with_channels.assert_called_once_with(
            interface_id="iface-1",
            device_address="VCU1234567",
        )

    def test_empty_device(self) -> None:
        """Test device with no channels returns empty tuple."""
        coordinator, _, _, _ = _make_coordinator(device_with_channels={})

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert channels == ()

    def test_filters_invalid_paramset_keys(self) -> None:
        """Test invalid paramset key strings are filtered out."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER", "INVALID_KEY"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 1
        assert channels[0].paramset_keys == (ParamsetKey.MASTER,)

    def test_includes_device_level_entry_with_master(self) -> None:
        """Test device-level entry (no colon) is included when it has MASTER."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001": {"TYPE": "DEVICE", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["VALUES"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 2
        assert channels[0].address == "VCU0000001"
        assert channels[0].channel_type == "DEVICE"
        assert channels[0].paramset_keys == (ParamsetKey.MASTER,)
        assert channels[1].address == "VCU0000001:1"

    def test_includes_hidden_channels_with_master(self) -> None:
        """Test channels without FLAGS are included if they have MASTER."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:0": {"TYPE": "MAINTENANCE", "PARAMSETS": ["MASTER"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 2
        assert channels[0].address == "VCU0000001:0"
        assert channels[0].paramset_keys == (ParamsetKey.MASTER,)
        assert channels[1].address == "VCU0000001:1"

    def test_includes_internal_channels_with_master(self) -> None:
        """Test channels with INTERNAL flag are included when they have MASTER."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:0": {"TYPE": "MAINTENANCE", "FLAGS": 3, "PARAMSETS": ["MASTER"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 2
        assert channels[0].address == "VCU0000001:0"
        assert channels[0].paramset_keys == (ParamsetKey.MASTER,)
        assert channels[1].address == "VCU0000001:1"

    def test_includes_invisible_channels_with_master(self) -> None:
        """Test channels without VISIBLE flag are included when they have MASTER."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:0": {"TYPE": "MAINTENANCE", "FLAGS": 0, "PARAMSETS": ["MASTER"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 2
        assert channels[0].address == "VCU0000001:0"
        assert channels[0].paramset_keys == (ParamsetKey.MASTER,)
        assert channels[1].address == "VCU0000001:1"

    def test_missing_type_defaults_to_empty(self) -> None:
        """Test channel without TYPE gets empty string."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:1": {"FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 1
        assert channels[0].channel_type == ""

    def test_returns_channels(self) -> None:
        """Test return channels with paramset keys."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001": {"TYPE": "DEVICE", "PARAMSETS": []},
                "VCU0000001:0": {"TYPE": "MAINTENANCE", "FLAGS": 1, "PARAMSETS": ["MASTER", "VALUES"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER", "VALUES"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 2
        assert channels[0].address == "VCU0000001:0"
        assert channels[0].channel_type == "MAINTENANCE"
        assert channels[0].paramset_keys == (ParamsetKey.MASTER, ParamsetKey.VALUES)
        assert channels[1].address == "VCU0000001:1"

    def test_skips_channels_without_paramsets(self) -> None:
        """Test channels without paramset keys are skipped."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001": {"TYPE": "DEVICE", "PARAMSETS": []},
                "VCU0000001:0": {"TYPE": "MAINTENANCE", "FLAGS": 1, "PARAMSETS": []},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 1
        assert channels[0].address == "VCU0000001:1"

    def test_skips_device_level_entry_without_master(self) -> None:
        """Test device-level entry (no colon) is skipped when it has no MASTER."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001": {"TYPE": "DEVICE", "FLAGS": 1, "PARAMSETS": ["VALUES"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 1
        assert channels[0].address == "VCU0000001:1"

    def test_skips_hidden_channels_without_master(self) -> None:
        """Test channels without FLAGS are skipped if they have no MASTER."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:0": {"TYPE": "MAINTENANCE", "PARAMSETS": ["VALUES"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 1
        assert channels[0].address == "VCU0000001:1"

    def test_skips_internal_channels_without_master(self) -> None:
        """Test channels with INTERNAL flag are skipped when they have no MASTER."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:0": {"TYPE": "MAINTENANCE", "FLAGS": 3, "PARAMSETS": ["VALUES"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 1
        assert channels[0].address == "VCU0000001:1"

    def test_skips_invisible_channels_without_master(self) -> None:
        """Test channels without VISIBLE flag are skipped when they have no MASTER."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:0": {"TYPE": "MAINTENANCE", "FLAGS": 0, "PARAMSETS": ["VALUES"]},
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 1
        assert channels[0].address == "VCU0000001:1"

    def test_skips_week_program_channels(self) -> None:
        """Test WEEK_PROGRAM channels are excluded."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:1": {"TYPE": "SWITCH", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
                "VCU0000001:2": {"TYPE": "WEEK_PROGRAM", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert len(channels) == 1
        assert channels[0].address == "VCU0000001:1"

    def test_sorted_by_address(self) -> None:
        """Test channels are sorted by address."""
        coordinator, _, _, _ = _make_coordinator(
            device_with_channels={
                "VCU0000001:3": {"TYPE": "C", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
                "VCU0000001:1": {"TYPE": "A", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
                "VCU0000001:2": {"TYPE": "B", "FLAGS": 1, "PARAMSETS": ["MASTER"]},
            },
        )

        channels = coordinator.get_configurable_channels(
            interface_id="ccu-main",
            device_address="VCU0000001",
        )
        assert [ch.address for ch in channels] == [
            "VCU0000001:1",
            "VCU0000001:2",
            "VCU0000001:3",
        ]


# ---------------------------------------------------------------------------
# get_parameter_data
# ---------------------------------------------------------------------------


class TestGetParameterData:
    """Test ConfigurationCoordinator.get_parameter_data."""

    def test_delegates_to_provider(self) -> None:
        """Test provider is called with correct arguments."""
        coordinator, _, _, psp = _make_coordinator()

        coordinator.get_parameter_data(
            interface_id="iface-1",
            channel_address="VCU0000001:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        psp.get_parameter_data.assert_called_once_with(
            interface_id="iface-1",
            channel_address="VCU0000001:2",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )

    def test_returns_none_for_unknown(self) -> None:
        """Test return None for unknown parameter."""
        coordinator, _, _, _ = _make_coordinator(parameter_data=None)

        result = coordinator.get_parameter_data(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            parameter="NONEXISTENT",
        )
        assert result is None

    def test_returns_parameter_data(self) -> None:
        """Test return parameter data for existing parameter."""
        temp_pd = _make_pd(TYPE=ParameterType.FLOAT, MIN=4.5, MAX=30.5)
        coordinator, _, _, _ = _make_coordinator(parameter_data=temp_pd)

        result = coordinator.get_parameter_data(
            interface_id="ccu-main",
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.MASTER,
            parameter="TEMP_MIN",
        )
        assert result == temp_pd


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Test ConfigurationCoordinator satisfies ConfigurationFacadeProtocol."""

    def test_is_instance_of_protocol(self) -> None:
        """Test ConfigurationCoordinator is a ConfigurationFacadeProtocol instance."""
        from aiohomematic.interfaces import ConfigurationFacadeProtocol

        coordinator, _, _, _ = _make_coordinator()
        assert isinstance(coordinator, ConfigurationFacadeProtocol)


# ---------------------------------------------------------------------------
# New dataclass tests
# ---------------------------------------------------------------------------


class TestCopyParamsetResult:
    """Test CopyParamsetResult dataclass."""

    def test_creation(self) -> None:
        """Test CopyParamsetResult can be created."""
        result = CopyParamsetResult(
            success=True,
            validated=True,
            validation_errors={},
            parameters_copied=3,
            parameters_skipped=1,
        )
        assert result.success is True
        assert result.parameters_copied == 3
        assert result.parameters_skipped == 1

    def test_frozen(self) -> None:
        """Test CopyParamsetResult is frozen."""
        result = CopyParamsetResult(
            success=True,
            validated=True,
            validation_errors={},
            parameters_copied=0,
            parameters_skipped=0,
        )
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]


class TestConfigurableDeviceChannel:
    """Test ConfigurableDeviceChannel dataclass."""

    def test_creation(self) -> None:
        """Test ConfigurableDeviceChannel can be created."""
        ch = ConfigurableDeviceChannel(
            address="VCU:1",
            channel_type="SWITCH",
            channel_type_label="Switch",
            channel_name="Licht Küche",
            paramset_keys=("MASTER", "VALUES"),
        )
        assert ch.address == "VCU:1"
        assert ch.channel_type_label == "Switch"
        assert ch.channel_name == "Licht Küche"
        assert ch.paramset_keys == ("MASTER", "VALUES")

    def test_frozen(self) -> None:
        """Test ConfigurableDeviceChannel is frozen."""
        ch = ConfigurableDeviceChannel(
            address="VCU:1",
            channel_type="SWITCH",
            channel_type_label="Switch",
            channel_name="",
            paramset_keys=("MASTER",),
        )
        with pytest.raises(AttributeError):
            ch.address = "other"  # type: ignore[misc]


class TestMaintenanceData:
    """Test MaintenanceData dataclass."""

    def test_creation_with_values(self) -> None:
        """Test MaintenanceData can be created with values."""
        md = MaintenanceData(unreach=False, low_bat=True, rssi_device=-65)
        assert md.unreach is False
        assert md.low_bat is True
        assert md.rssi_device == -65

    def test_defaults_are_none(self) -> None:
        """Test MaintenanceData fields default to None."""
        md = MaintenanceData()
        assert md.unreach is None
        assert md.low_bat is None
        assert md.rssi_device is None
        assert md.rssi_peer is None
        assert md.dutycycle is None
        assert md.config_pending is None

    def test_frozen(self) -> None:
        """Test MaintenanceData is frozen."""
        md = MaintenanceData()
        with pytest.raises(AttributeError):
            md.unreach = True  # type: ignore[misc]


class TestConfigurableDevice:
    """Test ConfigurableDevice dataclass."""

    def test_creation(self) -> None:
        """Test ConfigurableDevice can be created."""
        device = ConfigurableDevice(
            address="VCU0000001",
            interface="HmIP-RF",
            interface_id="iface-VCU",
            model="HmIP-BSM",
            model_description="Switch Actuator",
            name="Test Switch",
            firmware="1.0.0",
            channels=(),
            maintenance=MaintenanceData(),
        )
        assert device.address == "VCU0000001"
        assert device.model == "HmIP-BSM"

    def test_frozen(self) -> None:
        """Test ConfigurableDevice is frozen."""
        device = ConfigurableDevice(
            address="VCU0000001",
            interface="HmIP-RF",
            interface_id="iface-VCU",
            model="HmIP-BSM",
            model_description="",
            name="Test",
            firmware="1.0.0",
            channels=(),
            maintenance=MaintenanceData(),
        )
        with pytest.raises(AttributeError):
            device.address = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# get_configurable_devices tests
# ---------------------------------------------------------------------------


def _make_mock_device(
    *,
    address: str = "VCU0000001",
    interface_id: str = "iface-VCU",
    interface: Interface = Interface.HMIP_RF,
    model: str = "HmIP-BSM",
    model_description: str = "",
    name: str = "Test Switch",
    firmware: str = "1.0.0",
    generic_data_points: tuple[Any, ...] = (),
) -> MagicMock:
    """Build a mock device for testing."""
    device = MagicMock()
    device.address = address
    device.interface_id = interface_id
    device.interface = interface
    device.model = model
    device.model_description = model_description
    device.name = name
    device.firmware = firmware
    device.generic_data_points = generic_data_points
    return device


def _make_mock_data_point(*, channel_address: str, parameter: str, value: Any) -> MagicMock:
    """Build a mock data point for testing."""
    dp = MagicMock()
    dp.parameter = parameter
    dp.value = value
    dp.channel = MagicMock()
    dp.channel.address = channel_address
    return dp


class TestGetConfigurableDevices:
    """Test get_configurable_devices method."""

    def test_device_with_channels(self) -> None:
        """Test device with configurable channels is returned."""
        device = _make_mock_device()
        coordinator, _, device_desc_prov, paramset_desc_prov = _make_coordinator(
            devices=(device,),
            device_with_channels={
                "VCU0000001": {"TYPE": "DEVICE"},
                "VCU0000001:1": {
                    "TYPE": "SWITCH",
                    "FLAGS": Flag.VISIBLE,
                    "PARAMSETS": ["VALUES"],
                },
            },
        )

        result = coordinator.get_configurable_devices()
        assert len(result) == 1
        assert result[0].address == "VCU0000001"
        assert result[0].model == "HmIP-BSM"
        assert result[0].name == "Test Switch"
        assert len(result[0].channels) == 1
        assert result[0].channels[0].address == "VCU0000001:1"

    def test_device_without_configurable_channels_skipped(self) -> None:
        """Test device with no configurable channels is skipped."""
        device = _make_mock_device()
        coordinator, _, device_desc_prov, _ = _make_coordinator(devices=(device,))
        # Return no channels
        device_desc_prov.get_device_with_channels.return_value = {}

        result = coordinator.get_configurable_devices()
        assert result == ()

    def test_empty_device_list(self) -> None:
        """Test with no devices."""
        coordinator, _, _, _ = _make_coordinator(devices=())
        result = coordinator.get_configurable_devices()
        assert result == ()

    def test_exception_in_get_configurable_channels_skips_device(self) -> None:
        """Test device skipped when get_configurable_channels raises."""
        device = _make_mock_device()
        coordinator, _, device_desc_prov, _ = _make_coordinator(devices=(device,))
        device_desc_prov.get_device_with_channels.side_effect = BaseHomematicException("fail")

        result = coordinator.get_configurable_devices()
        assert result == ()

    def test_maintenance_data_collected(self) -> None:
        """Test maintenance data from channel 0 data points."""
        dp_unreach = _make_mock_data_point(channel_address="VCU:0", parameter="UNREACH", value=False)
        dp_low_bat = _make_mock_data_point(channel_address="VCU:0", parameter="LOW_BAT", value=True)
        dp_state = _make_mock_data_point(channel_address="VCU:1", parameter="STATE", value=True)
        device = _make_mock_device(
            address="VCU",
            generic_data_points=(dp_unreach, dp_low_bat, dp_state),
        )
        coordinator, _, device_desc_prov, _ = _make_coordinator(
            devices=(device,),
            device_with_channels={
                "VCU": {"TYPE": "DEVICE"},
                "VCU:1": {
                    "TYPE": "SWITCH",
                    "FLAGS": Flag.VISIBLE,
                    "PARAMSETS": ["VALUES"],
                },
            },
        )

        result = coordinator.get_configurable_devices()
        assert len(result) == 1
        maint = result[0].maintenance
        assert maint.unreach is False
        assert maint.low_bat is True
        # STATE from channel :1 should NOT be in maintenance
        assert maint.rssi_device is None

    def test_master_with_readonly_visible_params_included(self) -> None:
        """Test MASTER paramset included when it has visible (even read-only) params."""
        device = _make_mock_device()
        coordinator, _, _, paramset_desc_prov = _make_coordinator(
            devices=(device,),
            device_with_channels={
                "VCU0000001": {"TYPE": "DEVICE"},
                "VCU0000001:1": {
                    "TYPE": "SWITCH",
                    "FLAGS": Flag.VISIBLE,
                    "PARAMSETS": ["MASTER", "VALUES"],
                },
            },
        )
        # MASTER descriptions: only a read-only parameter
        paramset_desc_prov.get_channel_paramset_descriptions.return_value = {
            ParamsetKey.MASTER: {
                "READONLY": _make_pd(FLAGS=Flag.VISIBLE, OPERATIONS=Operations.READ),
            },
            ParamsetKey.VALUES: {},
        }

        result = coordinator.get_configurable_devices()
        assert len(result) == 1
        ch = result[0].channels[0]
        # MASTER should be included (visible params exist, even if read-only)
        assert "MASTER" in ch.paramset_keys
        assert "VALUES" in ch.paramset_keys

    def test_master_without_visible_params_excluded(self) -> None:
        """Test MASTER paramset excluded when no visible params at all."""
        device = _make_mock_device()
        coordinator, _, _, paramset_desc_prov = _make_coordinator(
            devices=(device,),
            device_with_channels={
                "VCU0000001": {"TYPE": "DEVICE"},
                "VCU0000001:1": {
                    "TYPE": "SWITCH",
                    "FLAGS": Flag.VISIBLE,
                    "PARAMSETS": ["MASTER", "VALUES"],
                },
            },
        )
        # MASTER descriptions: only an internal parameter
        paramset_desc_prov.get_channel_paramset_descriptions.return_value = {
            ParamsetKey.MASTER: {
                "INTERNAL_PARAM": _make_pd(FLAGS=Flag.INTERNAL, OPERATIONS=Operations.READ),
            },
            ParamsetKey.VALUES: {},
        }

        result = coordinator.get_configurable_devices()
        assert len(result) == 1
        ch = result[0].channels[0]
        # MASTER should be excluded, only VALUES remains
        assert "MASTER" not in ch.paramset_keys
        assert "VALUES" in ch.paramset_keys


# ---------------------------------------------------------------------------
# copy_paramset tests
# ---------------------------------------------------------------------------


class TestCopyParamset:
    """Test copy_paramset method."""

    @pytest.mark.asyncio
    async def test_empty_source(self) -> None:
        """Test copy with empty source values."""
        coordinator, client_prov, _, paramset_desc_prov = _make_coordinator()
        mock_client = client_prov.get_client.return_value
        mock_client.get_paramset.return_value = {}
        paramset_desc_prov.get_channel_paramset_descriptions.return_value = {ParamsetKey.MASTER: {}}

        result, old_vals, copied_vals = await coordinator.copy_paramset(
            source_interface_id="iface",
            source_channel_address="VCU:1",
            target_interface_id="iface",
            target_channel_address="VCU:2",
            paramset_key=ParamsetKey.MASTER,
        )
        assert result.success is True
        assert result.parameters_copied == 0
        assert result.parameters_skipped == 0
        assert old_vals == {}
        assert copied_vals == {}

    @pytest.mark.asyncio
    async def test_filters_missing_params(self) -> None:
        """Test that parameters not in target description are filtered out."""
        coordinator, client_prov, _, paramset_desc_prov = _make_coordinator()
        mock_client = client_prov.get_client.return_value
        mock_client.get_paramset.return_value = {"PARAM_A": 1, "PARAM_B": 2}
        paramset_desc_prov.get_channel_paramset_descriptions.return_value = {
            ParamsetKey.MASTER: {
                "PARAM_A": _make_pd(OPERATIONS=Operations.READ | Operations.WRITE),
                # PARAM_B not in target
            },
        }

        result, _, _ = await coordinator.copy_paramset(
            source_interface_id="iface",
            source_channel_address="VCU:1",
            target_interface_id="iface",
            target_channel_address="VCU:2",
            paramset_key=ParamsetKey.MASTER,
        )
        assert result.parameters_copied == 1
        assert result.parameters_skipped == 1

    @pytest.mark.asyncio
    async def test_filters_non_writable(self) -> None:
        """Test that non-writable parameters are filtered out."""
        coordinator, client_prov, _, paramset_desc_prov = _make_coordinator()
        mock_client = client_prov.get_client.return_value
        mock_client.get_paramset.return_value = {"WRITABLE": 10, "READONLY": 20}
        paramset_desc_prov.get_channel_paramset_descriptions.return_value = {
            ParamsetKey.MASTER: {
                "WRITABLE": _make_pd(OPERATIONS=Operations.READ | Operations.WRITE),
                "READONLY": _make_pd(OPERATIONS=Operations.READ),
            },
        }

        result, _, copied_vals = await coordinator.copy_paramset(
            source_interface_id="iface",
            source_channel_address="VCU:1",
            target_interface_id="iface",
            target_channel_address="VCU:2",
            paramset_key=ParamsetKey.MASTER,
        )
        assert result.success is True
        assert result.parameters_copied == 1
        assert result.parameters_skipped == 1
        assert "WRITABLE" in copied_vals
        assert "READONLY" not in copied_vals

    @pytest.mark.asyncio
    async def test_successful_copy_returns_old_and_new(self) -> None:
        """Test successful copy returns old values and copied values."""
        coordinator, client_prov, _, paramset_desc_prov = _make_coordinator()
        mock_client = client_prov.get_client.return_value
        # First call: source values; second call: old target values;
        # third call: current values for cross-parameter validation in put_paramset
        mock_client.get_paramset.side_effect = [
            {"PARAM": 99},
            {"PARAM": 0},
            {"PARAM": 0},
        ]
        paramset_desc_prov.get_channel_paramset_descriptions.return_value = {
            ParamsetKey.MASTER: {
                "PARAM": _make_pd(OPERATIONS=Operations.READ | Operations.WRITE),
            },
        }

        result, old_vals, copied_vals = await coordinator.copy_paramset(
            source_interface_id="iface",
            source_channel_address="VCU:1",
            target_interface_id="iface",
            target_channel_address="VCU:2",
            paramset_key=ParamsetKey.MASTER,
        )
        assert result.success is True
        assert old_vals == {"PARAM": 0}
        assert copied_vals == {"PARAM": 99}
