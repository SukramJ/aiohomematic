"""Tests for combined data points (CombinedDpTimerAction, CombinedDpHsColor, CombinedDataPoint)."""

from datetime import datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiohomematic.const import (
    INIT_DATETIME,
    CallSource,
    DataPointCategory,
    DataPointUsage,
    Field,
    ParameterType,
    ParamsetKey,
)
from aiohomematic.interfaces import ChannelProtocol, GenericDataPointProtocolAny
from aiohomematic.model.combined.hs_color import CombinedDpHsColor
from aiohomematic.model.combined.timer import CombinedDpTimerAction
from aiohomematic.model.generic import DpDummy


def _create_mock_channel() -> ChannelProtocol:
    """Create a minimal mock channel satisfying CombinedDataPoint init."""
    channel = MagicMock(spec_set=["address", "no", "type_name", "device"])
    channel.address = "VCU0000001:1"
    channel.no = 1
    channel.type_name = "DIMMER"

    device = MagicMock()
    device.address = "VCU0000001"
    device.name = "Test Device"
    device.model = "HmIP-BSM"
    device.interface_id = "test-interface"

    # Config provider
    device.config_provider.config.central_id = "test-central"
    device.config_provider.config.locale = "en"

    # Central info
    device.central_info.name = "test-ccu"

    # Paramset description provider
    device.paramset_description_provider.is_in_multiple_channels.return_value = False

    # Parameter visibility provider
    device.parameter_visibility_provider.parameter_is_un_ignored.return_value = True

    # Event bus provider
    device.event_bus_provider.event_bus.subscribe.return_value = lambda: None

    # Event publisher
    device.event_publisher = MagicMock()

    # Task scheduler
    device.task_scheduler = MagicMock()

    # Client
    device.client.interface = MagicMock()

    channel.device = device
    return cast(ChannelProtocol, channel)


def _create_mock_dp(
    *,
    value: float | None = None,
    default: float | None = None,
    max_value: float | None = 100.0,
    min_value: float | None = 0.0,
    is_readable: bool = True,
    is_refreshed: bool = False,
    is_status_valid: bool = True,
    state_uncertain: bool = False,
    modified_at: datetime = INIT_DATETIME,
    refreshed_at: datetime = INIT_DATETIME,
) -> GenericDataPointProtocolAny:
    """Create a mock data point for use in combined DPs."""
    dp = MagicMock()
    dp.value = value
    dp.default = default
    dp.max = max_value
    dp.min = min_value
    dp.is_readable = is_readable
    dp.is_refreshed = is_refreshed
    dp.is_status_valid = is_status_valid
    dp.is_writable = True
    dp.state_uncertain = state_uncertain
    dp.modified_at = modified_at
    dp.refreshed_at = refreshed_at
    dp.published_event_recently = False
    dp.send_value = AsyncMock(return_value=set())
    dp.load_data_point_value = AsyncMock()
    dp.unique_id = f"mock_dp_{id(dp)}"
    return cast(GenericDataPointProtocolAny, dp)


# ============================================================================
# CombinedDpTimerAction Tests
# ============================================================================


class TestCombinedDpTimerAction:
    """Tests for CombinedDpTimerAction."""

    def test_default(self) -> None:
        """Test default property delegates to value_dp."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp(default=5.0)
        unit_dp = _create_mock_dp()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        assert timer.default == 5.0

    def test_init_max_none(self) -> None:
        """Test max when underlying value_dp has no max."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp(max_value=None)
        unit_dp = _create_mock_dp()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        assert timer.max is None

    def test_init_with_dummy_value_dp(self) -> None:
        """Test is_valid returns False when value_dp is a DpDummy."""
        channel = _create_mock_channel()
        value_dp = DpDummy(channel=channel, param_field=Field.ON_TIME_VALUE)
        unit_dp = DpDummy(channel=channel, param_field=Field.ON_TIME_UNIT)

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        assert timer.is_valid is False

    def test_init_with_unit_dp(self) -> None:
        """Test initialization with both value and unit data points."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp(max_value=10)
        unit_dp = _create_mock_dp()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        assert timer.hmtype == ParameterType.FLOAT
        assert timer.unit == "s"
        assert timer.min == 0.0
        # max = raw_max * 3600 (hours -> seconds)
        assert timer.max == 36000.0
        assert timer.value is None
        assert timer.is_valid is True
        assert timer.category == DataPointCategory.ACTION_NUMBER

    def test_init_without_unit_dp(self) -> None:
        """Test initialization with DpDummy as unit data point."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp(max_value=100)
        unit_dp = DpDummy(channel=channel, param_field=Field.ON_TIME_UNIT)

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        # Without unit DP, max is used directly
        assert timer.max == 100.0
        assert timer.is_valid is True

    @pytest.mark.asyncio
    async def test_send_default_no_defaults(self) -> None:
        """Test send_default does nothing when DPs have no defaults."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp(default=None)
        unit_dp = _create_mock_dp(default=None)

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        await timer.send_default()

        unit_dp.send_value.assert_not_awaited()
        value_dp.send_value.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_default_with_both_dps(self) -> None:
        """Test send_default sends defaults for both unit and value DPs."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp(default=10.0)
        unit_dp = _create_mock_dp(default="S")

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        await timer.send_default()

        unit_dp.send_value.assert_awaited_once_with(value="S", collector=None)
        value_dp.send_value.assert_awaited_once_with(value=10.0, collector=None)

    @pytest.mark.asyncio
    async def test_send_value_large_converts_to_minutes(self) -> None:
        """Test send_value converts large seconds to minutes."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        # > 16343 seconds -> should be converted to minutes
        await timer.send_value(value=20000.0)

        unit_dp.send_value.assert_awaited_once_with(value="M", collector=None)
        # 20000 / 60 = 333.33...
        value_dp.send_value.assert_awaited_once()
        sent_value = value_dp.send_value.call_args.kwargs["value"]
        assert abs(sent_value - 20000.0 / 60) < 0.01
        assert timer.value == 20000.0

    @pytest.mark.asyncio
    async def test_send_value_with_collector(self) -> None:
        """Test send_value passes collector through."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()
        collector = MagicMock()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        await timer.send_value(value=50.0, collector=collector)

        unit_dp.send_value.assert_awaited_once_with(value="S", collector=collector)
        value_dp.send_value.assert_awaited_once_with(value=50.0, collector=collector, do_validate=False)

    @pytest.mark.asyncio
    async def test_send_value_with_unit_conversion(self) -> None:
        """Test send_value converts seconds to value+unit via recalc_unit_timer."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        # 100 seconds is below threshold, stays as seconds
        await timer.send_value(value=100.0)

        unit_dp.send_value.assert_awaited_once_with(value="S", collector=None)
        value_dp.send_value.assert_awaited_once_with(value=100.0, collector=None, do_validate=False)
        assert timer.value == 100.0

    @pytest.mark.asyncio
    async def test_send_value_without_unit_dp(self) -> None:
        """Test send_value sends directly when unit_dp is DpDummy."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = DpDummy(channel=channel, param_field=Field.ON_TIME_UNIT)

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        await timer.send_value(value=50.0)

        # Should send directly without unit conversion
        value_dp.send_value.assert_awaited_once_with(value=50.0, collector=None, do_validate=False)
        assert timer.value == 50.0

    def test_visible_defaults_to_false(self) -> None:
        """Test that visible defaults to False."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        assert timer.visible is False
        assert timer.usage == DataPointUsage.NO_CREATE

    def test_visible_when_set(self) -> None:
        """Test that visible=True produces CDP_VISIBLE usage."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
            visible=True,
        )

        assert timer.visible is True
        assert timer.usage == DataPointUsage.CDP_VISIBLE


# ============================================================================
# CombinedDpHsColor Tests
# ============================================================================


class TestCombinedDpHsColor:
    """Tests for CombinedDpHsColor."""

    def test_init(self) -> None:
        """Test initialization."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp()
        sat_dp = _create_mock_dp()

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.hmtype == ParameterType.FLOAT
        assert hs.is_writable is True
        assert hs.is_readable is True
        assert hs.has_events is True
        assert hs.default is None
        assert hs.category == DataPointCategory.SENSOR

    def test_is_valid_with_dummy_hue(self) -> None:
        """Test is_valid returns False when hue DP is dummy."""
        channel = _create_mock_channel()
        hue_dp = DpDummy(channel=channel, param_field=Field.HUE)
        sat_dp = _create_mock_dp()

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.is_valid is False

    def test_is_valid_with_dummy_saturation(self) -> None:
        """Test is_valid returns False when saturation DP is dummy."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp()
        sat_dp = DpDummy(channel=channel, param_field=Field.SATURATION)

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.is_valid is False

    def test_is_valid_with_real_dps(self) -> None:
        """Test is_valid returns True when both DPs are real."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp()
        sat_dp = _create_mock_dp()

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.is_valid is True

    def test_operations(self) -> None:
        """Test operations include READ, WRITE, EVENT."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp()
        sat_dp = _create_mock_dp()

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.is_readable is True
        assert hs.is_writable is True
        assert hs.has_events is True

    @pytest.mark.asyncio
    async def test_send_default_no_defaults(self) -> None:
        """Test send_default skips when no defaults set."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp(default=None)
        sat_dp = _create_mock_dp(default=None)

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        await hs.send_default()

        hue_dp.send_value.assert_not_awaited()
        sat_dp.send_value.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_default_with_defaults(self) -> None:
        """Test send_default sends default values."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp(default=0.0)
        sat_dp = _create_mock_dp(default=1.0)

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        await hs.send_default()

        hue_dp.send_value.assert_awaited_once_with(value=0.0, collector=None)
        sat_dp.send_value.assert_awaited_once_with(value=1.0, collector=None)

    @pytest.mark.asyncio
    async def test_send_value(self) -> None:
        """Test send_value sends hue as int and saturation divided by 100."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp()
        sat_dp = _create_mock_dp()

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        await hs.send_value(value=(120.0, 50.0))

        hue_dp.send_value.assert_awaited_once_with(value=120, collector=None)
        sat_dp.send_value.assert_awaited_once_with(value=0.5, collector=None)

    @pytest.mark.asyncio
    async def test_send_value_with_collector(self) -> None:
        """Test send_value passes collector through."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp()
        sat_dp = _create_mock_dp()
        collector = MagicMock()

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        await hs.send_value(value=(300.0, 75.0), collector=collector)

        hue_dp.send_value.assert_awaited_once_with(value=300, collector=collector)
        sat_dp.send_value.assert_awaited_once_with(value=0.75, collector=collector)

    @pytest.mark.asyncio
    async def test_send_value_zero_saturation(self) -> None:
        """Test send_value with zero saturation."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp()
        sat_dp = _create_mock_dp()

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        await hs.send_value(value=(0.0, 0.0))

        hue_dp.send_value.assert_awaited_once_with(value=0, collector=None)
        sat_dp.send_value.assert_awaited_once_with(value=0.0, collector=None)

    def test_value_none_when_hue_none(self) -> None:
        """Test value returns None when hue has no value."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp(value=None)
        sat_dp = _create_mock_dp(value=0.5)

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.value is None

    def test_value_none_when_saturation_none(self) -> None:
        """Test value returns None when saturation has no value."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp(value=120.0)
        sat_dp = _create_mock_dp(value=None)

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.value is None

    def test_value_with_both_values(self) -> None:
        """Test value returns (hue, saturation*100) when both have values."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp(value=120.0)
        sat_dp = _create_mock_dp(value=0.5)

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.value == (120.0, 50.0)

    def test_value_with_full_saturation(self) -> None:
        """Test value with saturation = 1.0 returns 100.0."""
        channel = _create_mock_channel()
        hue_dp = _create_mock_dp(value=240.0)
        sat_dp = _create_mock_dp(value=1.0)

        hs = CombinedDpHsColor(
            channel=channel,
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
            hue_dp=hue_dp,
            saturation_dp=sat_dp,
        )

        assert hs.value == (240.0, 100.0)


# ============================================================================
# CombinedDataPoint Base Tests
# ============================================================================


class TestCombinedDataPointBase:
    """Tests for CombinedDataPoint base class behavior."""

    def test_data_point_name_postfix(self) -> None:
        """Test data_point_name_postfix returns empty string."""
        timer = self._create_timer()
        assert timer.data_point_name_postfix == ""

    def test_dpk(self) -> None:
        """Test dpk returns correct DataPointKey."""
        timer = self._create_timer()

        dpk = timer.dpk
        assert dpk.paramset_key == ParamsetKey.COMBINED
        assert dpk.parameter == Field.ON_TIME_VALUE.value

    def test_has_data_points(self) -> None:
        """Test has_data_points returns True when data points exist."""
        timer = self._create_timer()
        assert timer.has_data_points is True

    def test_is_refreshed_all_refreshed(self) -> None:
        """Test is_refreshed returns True when all readable DPs are refreshed."""
        value_dp = _create_mock_dp(is_refreshed=True)
        unit_dp = _create_mock_dp(is_refreshed=True)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.is_refreshed is True

    def test_is_refreshed_not_all_refreshed(self) -> None:
        """Test is_refreshed returns False when any readable DP is not refreshed."""
        value_dp = _create_mock_dp(is_refreshed=True)
        unit_dp = _create_mock_dp(is_refreshed=False)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.is_refreshed is False

    def test_is_refreshed_with_non_readable_dp(self) -> None:
        """Test is_refreshed ignores non-readable DPs."""
        value_dp = _create_mock_dp(is_refreshed=True, is_readable=True)
        unit_dp = _create_mock_dp(is_refreshed=False, is_readable=False)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        # unit_dp is not readable so it's not in _relevant_data_points
        assert timer.is_refreshed is True

    def test_is_state_change_when_certain(self) -> None:
        """Test is_state_change returns False when state is certain."""
        value_dp = _create_mock_dp(state_uncertain=False)
        unit_dp = _create_mock_dp(state_uncertain=False)
        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.is_state_change() is False

    def test_is_state_change_when_uncertain(self) -> None:
        """Test is_state_change returns True when state is uncertain."""
        value_dp = _create_mock_dp(state_uncertain=True)
        timer = self._create_timer(value_dp=value_dp)

        assert timer.is_state_change() is True

    def test_is_status_valid_all_valid(self) -> None:
        """Test is_status_valid returns True when all readable DPs have valid status."""
        value_dp = _create_mock_dp(is_status_valid=True)
        unit_dp = _create_mock_dp(is_status_valid=True)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.is_status_valid is True

    def test_is_status_valid_one_invalid(self) -> None:
        """Test is_status_valid returns False when any readable DP has invalid status."""
        value_dp = _create_mock_dp(is_status_valid=False)
        unit_dp = _create_mock_dp(is_status_valid=True)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.is_status_valid is False

    @pytest.mark.asyncio
    async def test_load_data_point_value(self) -> None:
        """Test load_data_point_value loads all readable DPs."""
        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        await timer.load_data_point_value(call_source=CallSource.HM_INIT)

        value_dp.load_data_point_value.assert_awaited_once_with(call_source=CallSource.HM_INIT, direct_call=False)
        unit_dp.load_data_point_value.assert_awaited_once_with(call_source=CallSource.HM_INIT, direct_call=False)

    @pytest.mark.asyncio
    async def test_load_data_point_value_skips_non_readable(self) -> None:
        """Test load_data_point_value skips non-readable DPs."""
        value_dp = _create_mock_dp(is_readable=True)
        unit_dp = _create_mock_dp(is_readable=False)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        await timer.load_data_point_value(call_source=CallSource.HM_INIT)

        value_dp.load_data_point_value.assert_awaited_once()
        unit_dp.load_data_point_value.assert_not_awaited()

    def test_modified_at_init_when_no_modifications(self) -> None:
        """Test modified_at returns INIT_DATETIME when no DP has been modified."""
        value_dp = _create_mock_dp(modified_at=INIT_DATETIME)
        unit_dp = _create_mock_dp(modified_at=INIT_DATETIME)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.modified_at == INIT_DATETIME

    def test_modified_at_returns_latest(self) -> None:
        """Test modified_at returns the latest timestamp from readable DPs."""
        t1 = datetime(2025, 1, 1, 12, 0, 0)
        t2 = datetime(2025, 1, 1, 13, 0, 0)
        value_dp = _create_mock_dp(modified_at=t1)
        unit_dp = _create_mock_dp(modified_at=t2)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.modified_at == t2

    def test_multiplier(self) -> None:
        """Test multiplier is always 1.0."""
        timer = self._create_timer()
        assert timer.multiplier == 1.0

    def test_paramset_key(self) -> None:
        """Test paramset_key is COMBINED."""
        timer = self._create_timer()
        assert timer.paramset_key == ParamsetKey.COMBINED

    def test_refreshed_at_returns_latest(self) -> None:
        """Test refreshed_at returns the latest timestamp from readable DPs."""
        t1 = datetime(2025, 1, 1, 12, 0, 0)
        t2 = datetime(2025, 1, 1, 14, 0, 0)
        value_dp = _create_mock_dp(refreshed_at=t1)
        unit_dp = _create_mock_dp(refreshed_at=t2)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.refreshed_at == t2

    def test_service_default(self) -> None:
        """Test service defaults to False."""
        timer = self._create_timer()
        assert timer.service is False

    def test_state_uncertain_none(self) -> None:
        """Test state_uncertain returns False when no DP is uncertain."""
        value_dp = _create_mock_dp(state_uncertain=False)
        unit_dp = _create_mock_dp(state_uncertain=False)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.state_uncertain is False

    def test_state_uncertain_one(self) -> None:
        """Test state_uncertain returns True when any DP is uncertain."""
        value_dp = _create_mock_dp(state_uncertain=True)
        unit_dp = _create_mock_dp(state_uncertain=False)

        timer = self._create_timer(value_dp=value_dp, unit_dp=unit_dp)

        assert timer.state_uncertain is True

    def test_subscription_skips_dummy_dps(self) -> None:
        """Test that combined DP does not subscribe to DpDummy instances."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = DpDummy(channel=channel, param_field=Field.ON_TIME_UNIT)

        _timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        # EventBus subscribe is called once for value_dp (not for DpDummy)
        channel.device.event_bus_provider.event_bus.subscribe.assert_called_once()

    def test_subscription_to_underlying_dps(self) -> None:
        """Test that combined DP subscribes to underlying data point updates via EventBus."""
        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()

        _timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        # EventBus subscribe is called twice (once per non-dummy DP)
        assert channel.device.event_bus_provider.event_bus.subscribe.call_count == 2

    def test_unsubscribe_from_data_point_updated(self) -> None:
        """Test unsubscribe clears all subscriptions."""
        channel = _create_mock_channel()
        unsub_mock = MagicMock()
        channel.device.event_bus_provider.event_bus.subscribe.return_value = unsub_mock

        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()

        timer = CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )

        timer.unsubscribe_from_data_point_updated()

        # unsub_mock was returned twice, so it should be called twice
        assert unsub_mock.call_count == 2

    def _create_timer(
        self,
        *,
        value_dp: GenericDataPointProtocolAny | None = None,
        unit_dp: GenericDataPointProtocolAny | None = None,
        channel: ChannelProtocol | None = None,
    ) -> CombinedDpTimerAction:
        """Create a CombinedDpTimerAction for base class testing."""
        if channel is None:
            channel = _create_mock_channel()
        if value_dp is None:
            value_dp = _create_mock_dp()
        if unit_dp is None:
            unit_dp = _create_mock_dp()
        return CombinedDpTimerAction(
            channel=channel,
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
            value_dp=value_dp,
            unit_dp=unit_dp,
        )


# ============================================================================
# CombinedTimerField Descriptor Tests
# ============================================================================


class TestCombinedTimerField:
    """Tests for CombinedTimerField descriptor."""

    def test_create_combined_dp_with_missing_dps(self) -> None:
        """Test create_combined_dp creates DpDummy for missing DPs."""
        from aiohomematic.model.combined.field import CombinedTimerField

        channel = _create_mock_channel()
        data_points: dict[Field, GenericDataPointProtocolAny] = {}

        field = CombinedTimerField(
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
        )

        result = field.create_combined_dp(channel=channel, data_points=data_points)

        assert isinstance(result, CombinedDpTimerAction)
        assert result.is_valid is False  # value_dp is DpDummy

    def test_create_combined_dp_with_real_dps(self) -> None:
        """Test create_combined_dp creates timer with resolved DPs."""
        from aiohomematic.model.combined.field import CombinedTimerField

        channel = _create_mock_channel()
        value_dp = _create_mock_dp()
        unit_dp = _create_mock_dp()
        data_points = {
            Field.ON_TIME_VALUE: value_dp,
            Field.ON_TIME_UNIT: unit_dp,
        }

        field = CombinedTimerField(
            value_field=Field.ON_TIME_VALUE,
            unit_field=Field.ON_TIME_UNIT,
        )

        result = field.create_combined_dp(channel=channel, data_points=data_points)

        assert isinstance(result, CombinedDpTimerAction)
        assert result.is_valid is True


# ============================================================================
# CombinedHsColorField Descriptor Tests
# ============================================================================


class TestCombinedHsColorField:
    """Tests for CombinedHsColorField descriptor."""

    def test_create_combined_dp_with_missing_dps(self) -> None:
        """Test create_combined_dp creates DpDummy for missing DPs."""
        from aiohomematic.model.combined.field import CombinedHsColorField

        channel = _create_mock_channel()
        data_points: dict[Field, GenericDataPointProtocolAny] = {}

        field = CombinedHsColorField(
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
        )

        result = field.create_combined_dp(channel=channel, data_points=data_points)

        assert isinstance(result, CombinedDpHsColor)
        assert result.is_valid is False

    def test_create_combined_dp_with_real_dps(self) -> None:
        """Test create_combined_dp creates hs_color with resolved DPs."""
        from aiohomematic.model.combined.field import CombinedHsColorField

        channel = _create_mock_channel()
        hue_dp = _create_mock_dp()
        sat_dp = _create_mock_dp()
        data_points = {
            Field.HUE: hue_dp,
            Field.SATURATION: sat_dp,
        }

        field = CombinedHsColorField(
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
        )

        result = field.create_combined_dp(channel=channel, data_points=data_points)

        assert isinstance(result, CombinedDpHsColor)
        assert result.is_valid is True

    def test_value_field_returns_hue_field(self) -> None:
        """Test value_field property returns the hue field."""
        from aiohomematic.model.combined.field import CombinedHsColorField

        field = CombinedHsColorField(
            hue_field=Field.HUE,
            saturation_field=Field.SATURATION,
        )

        assert field.value_field == Field.HUE
