"""
Unit tests to improve coverage for aiohomematic.client helpers and config.

All tests include docstrings as required.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aiohomematic.client import InterfaceConfig, _isclose, get_client
from aiohomematic.const import DataPointKey, Interface, ParamsetKey
from aiohomematic.exceptions import ClientException


def test_isclose_float_rounding() -> None:
    """_isclose should consider floats equal when equal at 2 decimal places."""
    assert _isclose(value1=0.123, value2=0.124) is True
    assert _isclose(value1=1.005, value2=1.0049) is True
    assert _isclose(value1=1.00, value2=1.01) is False


def test_isclose_non_float_equality() -> None:
    """_isclose should use simple equality for non-floats."""
    assert _isclose(value1=5, value2=5) is True
    assert _isclose(value1="abc", value2="abc") is True
    assert _isclose(value1={"a": 1}, value2={"a": 1}) is True
    assert _isclose(value1=(1, 2), value2=(1, 3)) is False


def test_interface_config_validation_requires_port_for_callback_interfaces() -> None:
    """InterfaceConfig must raise when port is falsy for callback-capable interfaces."""
    with pytest.raises(ClientException):
        InterfaceConfig(central_name="test", interface=Interface.HMIP_RF, port=0)


def test_interface_config_enabled_and_disable() -> None:
    """InterfaceConfig.enabled is True by default and becomes False after disable()."""
    ic = InterfaceConfig(central_name="test", interface=Interface.CUXD, port=0)
    assert ic.enabled is True
    ic.disable()
    assert ic.enabled is False


def test_get_client_returns_none_when_not_found() -> None:
    """get_client should return None when no central contains the interface id."""
    assert get_client("non-existent-interface-id") is None


@pytest.mark.asyncio
async def test_track_single_data_point_returns_when_dp_missing() -> None:
    """_track_single_data_point_state_change_or_timeout returns immediately if DP is missing."""
    from aiohomematic.client import _track_single_data_point_state_change_or_timeout

    # Prepare a fake device without the requested data point
    device = MagicMock()
    device.get_generic_data_point.return_value = None

    dpk = DataPointKey(
        interface_id="test-iface", channel_address="addr:1", paramset_key=ParamsetKey.VALUES, parameter="STATE"
    )

    await _track_single_data_point_state_change_or_timeout(device=device, dpk_value=(dpk, True), wait_for_callback=1)


@pytest.mark.asyncio
async def test_track_single_data_point_returns_when_no_events_supported() -> None:
    """Function should return early when the data point does not support events."""
    from aiohomematic.client import _track_single_data_point_state_change_or_timeout

    # Mock a data point that does not support events
    dp = MagicMock()
    dp.supports_events = False

    # Device returns our mocked dp
    device = MagicMock()
    device.get_generic_data_point.return_value = dp

    dpk = DataPointKey(
        interface_id="test-iface", channel_address="addr:1", paramset_key=ParamsetKey.VALUES, parameter="STATE"
    )

    await _track_single_data_point_state_change_or_timeout(device=device, dpk_value=(dpk, True), wait_for_callback=1)
