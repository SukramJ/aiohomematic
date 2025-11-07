# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Dummy generic data point (backend-detached placeholder).

This class derives from `GenericDataPoint` but overrides all methods that would
normally interact with the backend so it behaves like an inert data point that
uses safe default values only.
The DpDummy class is intended to be used as a placeholder for custom data
points that are not implemented in the backend.

Key properties:
- It never triggers backend I/O (no reads, no writes, no subscriptions).
- It always reports `usage = DataPointUsage.NO_CREATE` so it is not created as a
  real entity.
- It is not readable or writable and does not require polling nor support
  events.
- It exposes safe, static defaults for metadata and state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from aiohomematic.const import (
    DP_KEY_VALUE,
    INIT_DATETIME,
    CallSource,
    DataPointKey,
    DataPointUsage,
    Field,
    ParameterData,
    ParameterType,
    ParamsetKey,
)
from aiohomematic.model import device as hmd
from aiohomematic.model.data_point import CallParameterCollector
from aiohomematic.model.generic import GenericDataPointAny
from aiohomematic.model.support import DataPointNameData


class DpDummy(GenericDataPointAny):
    """
    Backend-detached `GenericDataPoint` using only default values.

    All backend-touching operations are overridden to be no-ops.
    """

    __slots__ = ()

    is_hmtype = False

    def __init__(self, *, channel: hmd.Channel, param_field: str | Field) -> None:
        """
        Initialize the dummy data point.

        We still call `super().__init__` to get a valid object layout, but all
        runtime behavior that would contact the backend is disabled via
        overrides below.
        """

        super().__init__(
            channel=channel,
            paramset_key=ParamsetKey.DUMMY,
            parameter=f"DUMMY-{str(param_field)}",
            parameter_data=ParameterData(
                DEFAULT=None,
                FLAGS=0,
                ID="0",
                MAX=None,
                MIN=None,
                OPERATIONS=0,
                SPECIAL={},
                TYPE=ParameterType.DUMMY,
                UNIT="",
                VALUE_LIST=(),
            ),
        )

    @property
    def dpk(self) -> DataPointKey:
        """Return a stable placeholder data point key."""
        # Return a stable placeholder key so equality/set operations are safe.
        return cast(DataPointKey, ("", "", ""))

    @property
    def modified_at(self) -> datetime:
        """Never report modification timestamp for this data point."""
        return INIT_DATETIME

    @property
    def refreshed_at(self) -> datetime:
        """Never report refresh timestamp for this data point."""
        return INIT_DATETIME

    @property
    def requires_polling(self) -> bool:
        """Never poll from this data point."""
        return False

    @property
    def state_uncertain(self) -> bool:
        """Never report state uncertainty for this data point."""
        return True

    @property
    def usage(self) -> DataPointUsage:
        """Never create/ expose this data point as a real entity."""
        return DataPointUsage.NO_CREATE

    @property
    def value(self) -> Any:
        """Return the value of the data_point."""
        return None

    async def event(self, *, value: Any, received_at: datetime) -> None:
        """Ignore backend events entirely."""
        return

    async def load_data_point_value(self, *, call_source: CallSource, direct_call: bool = False) -> None:
        """Do not read from backend; keep defaults as-is."""
        return

    async def send_value(
        self,
        *,
        value: Any,
        collector: CallParameterCollector | None = None,
        collector_order: int = 50,
        do_validate: bool = True,
    ) -> set[DP_KEY_VALUE]:
        """Do not write to backend; accept but perform no operation."""
        return set()

    def _get_data_point_name(self) -> DataPointNameData:
        """Return a stable, recognizable name to aid debugging."""
        name = super()._get_data_point_name()
        # Replace parameter part with a dummy marker without touching address
        return DataPointNameData(
            device_name=f"DUMMY_{name.name}",
            channel_name=f"DUMMY_{name.full_name}",
            parameter_name=f"DUMMY_{name.parameter_name}",
        )
