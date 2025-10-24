"""
Tests for the base CalculatedDataPoint behaviors with lightweight fakes.

Covers adding source data points, property calculations, event-callback wiring,
state aggregation, and unregister behavior without requiring a full central.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from aiohomematic.const import INIT_DATETIME, ParamsetKey
from aiohomematic.model.calculated.data_point import CalculatedDataPoint


class _FakeCentral:
    def __init__(self) -> None:
        self.name = "CentralTest"
        self.config = type("Cfg", (), {"central_id": "CentralTest"})()
        # Minimal helpers used by name generation (not used here)
        self.paramset_descriptions = type("PS", (), {"is_in_multiple_channels": lambda *_args, **_kw: False})()
        self.device_details = type("DD", (), {"get_name": lambda *_args, **_kw: None})()


class _FakeDevice:
    def __init__(self) -> None:
        self.interface_id = "ifid"
        self.address = "ADDR1"
        self.model = "HmIP-XYZ"
        self.name = "DeviceName"
        self.client = type("Client", (), {"interface": None})()


class _FakeChannel:
    def __init__(self) -> None:
        self.central = _FakeCentral()
        self.device = _FakeDevice()
        self.address = "ADDR1:1"
        self.no = 1
        self._store: dict[tuple[str, ParamsetKey | None], _FakeGenericDP] = {}

    # API used by CalculatedDataPoint
    def get_generic_data_point(self, *, parameter: str, paramset_key: ParamsetKey | None) -> _FakeGenericDP | None:
        return self._store.get((parameter, paramset_key))

    def add_fake(self, dp: _FakeGenericDP) -> None:
        self._store[(dp.parameter, dp.paramset_key)] = dp


class _FakeGenericDP:
    def __init__(self, *, parameter: str, paramset_key: ParamsetKey, readable: bool = True) -> None:
        self.parameter = parameter
        self.paramset_key = paramset_key
        self._readable = readable
        self._modified_at = INIT_DATETIME
        self._refreshed_at = INIT_DATETIME
        self.is_valid = True
        self.state_uncertain = False
        self.fired_event_recently = True
        # Return unregister flag
        self._unregistered: list[bool] = []

    # Properties used by CalculatedDataPoint
    @property
    def is_readable(self) -> bool:  # noqa: D401
        """Whether the DP is readable."""
        return self._readable

    @property
    def modified_at(self) -> datetime:  # noqa: D401
        """Modified timestamp used for aggregation."""
        return self._modified_at

    @property
    def refreshed_at(self) -> datetime:  # noqa: D401
        """Refreshed timestamp used for aggregation."""
        return self._refreshed_at

    def set_times(self, *, modified_delta: int, refreshed_delta: int) -> None:
        base = datetime.now()
        self._modified_at = base + timedelta(seconds=modified_delta)
        self._refreshed_at = base + timedelta(seconds=refreshed_delta)

    # Callback registration used by CalculatedDataPoint
    def register_internal_data_point_updated_callback(self, *, cb: Callable) -> Callable[[], None]:
        self.fired_event_recently = False  # simulate that something changed later

        def _unregister() -> None:
            self._unregistered.append(True)

        return _unregister


class _MyCalc(CalculatedDataPoint[float | None]):
    """Concrete CalculatedDataPoint for testing with a custom parameter name."""

    _calculated_parameter = "TEST_CALC"

    def __init__(self, *, channel: _FakeChannel) -> None:  # type: ignore[override]
        super().__init__(channel=channel)  # type: ignore[arg-type]

    # Make two VALUES data points relevant so _should_fire_data_point_updated_callback checks the branch
    @property
    def _relevant_values_data_points(self) -> tuple[_FakeGenericDP, ...]:  # type: ignore[override]
        return tuple(dp for dp in self._data_points if dp.paramset_key == ParamsetKey.VALUES)  # type: ignore[attr-defined]


def test_calculated_datapoint_add_and_properties() -> None:
    """It should attach readable source DPs, compute dpk and operation flags, and aggregate timestamps."""
    ch = _FakeChannel()

    # Add two readable VALUES DPs and one MASTER DP (not relevant for values aggregation)
    dp1 = _FakeGenericDP(parameter="A", paramset_key=ParamsetKey.VALUES)
    dp2 = _FakeGenericDP(parameter="B", paramset_key=ParamsetKey.VALUES)
    dp3 = _FakeGenericDP(parameter="C", paramset_key=ParamsetKey.MASTER)
    dp1.set_times(modified_delta=1, refreshed_delta=2)
    dp2.set_times(modified_delta=3, refreshed_delta=1)
    dp3.set_times(modified_delta=0, refreshed_delta=0)
    ch.add_fake(dp1)
    ch.add_fake(dp2)
    ch.add_fake(dp3)

    calc = _MyCalc(channel=ch)
    # Use protected helpers to attach
    calc._add_data_point(parameter="A", paramset_key=ParamsetKey.VALUES, data_point_type=_FakeGenericDP)  # type: ignore[arg-type]
    calc._add_data_point(parameter="B", paramset_key=ParamsetKey.VALUES, data_point_type=_FakeGenericDP)  # type: ignore[arg-type]
    calc._add_data_point(parameter="C", paramset_key=ParamsetKey.MASTER, data_point_type=_FakeGenericDP)  # type: ignore[arg-type]

    # Ops flags from base: READ + EVENT, not WRITE
    assert calc.is_readable is True
    assert calc.is_writeable is False
    assert calc.supports_events is True

    # DPK and paramset
    dpk = calc.dpk
    assert dpk.paramset_key == ParamsetKey.CALCULATED
    assert dpk.parameter == "TEST_CALC"
    assert calc.paramset_key == ParamsetKey.CALCULATED

    # modified_at/refreshed_at aggregation picks the max from readable DPs
    assert calc.modified_at >= dp2.modified_at
    assert calc.refreshed_at >= max(dp1.refreshed_at, dp2.refreshed_at)

    # has_data_points/is_valid/state_uncertain
    assert calc.has_data_points is True
    assert calc.is_valid is True
    assert calc.state_uncertain is False

    # _should_fire_data_point_updated_callback with >1 VALUES DPs requires all fired_event_recently True
    # We set them via registration to False, so result should be False until we flip them
    assert calc._should_fire_data_point_updated_callback is False
    dp1.fired_event_recently = True
    dp2.fired_event_recently = True
    assert calc._should_fire_data_point_updated_callback is True

    # is_state_change should be False when not uncertain
    assert calc.is_state_change() is False

    # Unregister internal callbacks should invoke unregister callables
    # Use the public register to add and then remove a dummy callback
    def dummy_cb(**kwargs: Any) -> None:  # noqa: D401
        """Execute dummy callback for unregister path."""

    unregister = calc.register_internal_data_point_updated_callback(cb=dummy_cb)
    assert unregister is not None
    unregister()

    # Simulate unregister via internal method which loops over stored unregisters
    calc._unregister_data_point_updated_callback(cb=dummy_cb, custom_id="x")
    # Ensure at least one unregister was called on a source dp
    assert any(dp._unregistered for dp in (dp1, dp2, dp3))


def test_calculated_datapoint_add_missing_returns_none_type() -> None:
    """When a requested source DP is missing, a NoneTypeDataPoint is returned and stored."""
    ch = _FakeChannel()
    calc = _MyCalc(channel=ch)
    none_dp = calc._add_data_point(parameter="MISSING", paramset_key=ParamsetKey.VALUES, data_point_type=_FakeGenericDP)  # type: ignore[arg-type]
    # NoneTypeDataPoint has no attributes; ensure our call returned an object with no is_readable attribute
    assert not hasattr(none_dp, "is_readable")
    # And the overall calc still exposes expected operation flags
    assert calc.is_readable is True
    assert calc.supports_events is True
    assert calc.is_writeable is False
