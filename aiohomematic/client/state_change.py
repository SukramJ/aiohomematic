# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
State change tracking utilities.

Provides utilities for waiting on device state changes after sending commands.

Public API
----------
- wait_for_state_change_or_timeout: Wait for data point callbacks after set_value/put_paramset
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Final

from aiohomematic.const import DP_KEY_VALUE, InternalCustomID, ParamsetKey
from aiohomematic.decorators import measure_execution_time

if TYPE_CHECKING:
    from aiohomematic.interfaces.model import DeviceProtocol

__all__ = [
    "wait_for_state_change_or_timeout",
    # Private but exported for testing
    "_isclose",
    "_track_single_data_point_state_change_or_timeout",
]

_LOGGER: Final = logging.getLogger(__name__)


@measure_execution_time
async def wait_for_state_change_or_timeout(
    *,
    device: DeviceProtocol,
    dpk_values: set[DP_KEY_VALUE],
    wait_for_callback: int,
) -> None:
    """Wait for all affected data points to receive confirmation callbacks in parallel."""
    waits = [
        _track_single_data_point_state_change_or_timeout(
            device=device,
            dpk_value=dpk_value,
            wait_for_callback=wait_for_callback,
        )
        for dpk_value in dpk_values
    ]
    await asyncio.gather(*waits)


@measure_execution_time
async def _track_single_data_point_state_change_or_timeout(
    *, device: DeviceProtocol, dpk_value: DP_KEY_VALUE, wait_for_callback: int
) -> None:
    """
    Wait for a single data point to receive its confirmation callback.

    Subscribes to the data point's update events and waits until the received
    value matches the sent value (using fuzzy float comparison) or times out.
    """
    ev = asyncio.Event()
    dpk, value = dpk_value

    def _async_event_changed(*args: Any, **kwargs: Any) -> None:
        if dp:
            _LOGGER.debug(
                "TRACK_SINGLE_DATA_POINT_STATE_CHANGE_OR_TIMEOUT: Received event %s with value %s",
                dpk,
                dp.value,
            )
            if _isclose(value1=value, value2=dp.value):
                _LOGGER.debug(
                    "TRACK_SINGLE_DATA_POINT_STATE_CHANGE_OR_TIMEOUT: Finished event %s with value %s",
                    dpk,
                    dp.value,
                )
                ev.set()

    if dp := device.get_generic_data_point(
        channel_address=dpk.channel_address,
        parameter=dpk.parameter,
        paramset_key=ParamsetKey(dpk.paramset_key),
    ):
        if not dp.has_events:
            _LOGGER.debug(
                "TRACK_SINGLE_DATA_POINT_STATE_CHANGE_OR_TIMEOUT: DataPoint supports no events %s",
                dpk,
            )
            return
        unreg = dp.subscribe_to_data_point_updated(handler=_async_event_changed, custom_id=InternalCustomID.DEFAULT)

        try:
            async with asyncio.timeout(wait_for_callback):
                await ev.wait()
        except TimeoutError:
            _LOGGER.debug(
                "TRACK_SINGLE_DATA_POINT_STATE_CHANGE_OR_TIMEOUT: Timeout waiting for event %s with value %s",
                dpk,
                dp.value,
            )
        finally:
            unreg()


def _isclose(*, value1: Any, value2: Any) -> bool:
    """Compare values with fuzzy float matching (2 decimal places) for confirmation."""
    if isinstance(value1, float):
        return bool(round(value1, 2) == round(value2, 2))
    return bool(value1 == value2)
