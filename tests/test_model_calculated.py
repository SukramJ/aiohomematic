"""Tests for aiohomematic.model.calculated."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any

import pytest

from aiohomematic.const import INIT_DATETIME, Parameter, ParamsetKey
from aiohomematic.model.calculated import (
    ApparentTemperature,
    DewPoint,
    DewPointSpread,
    Enthalpy,
    FrostPoint,
    VaporConcentration,
)
from aiohomematic.model.calculated.climate import _is_relevant_for_model_temperature_and_humidity
from aiohomematic.model.calculated.data_point import CalculatedDataPoint
from aiohomematic.model.calculated.operating_voltage_level import OperatingVoltageLevel
from aiohomematic.model.calculated.support import (
    calculate_apparent_temperature,
    calculate_dew_point,
    calculate_dew_point_spread,
    calculate_enthalpy,
    calculate_frost_point,
    calculate_operating_voltage_level,
    calculate_vapor_concentration,
)

# Shared fake helpers ---------------------------------------------------------


class _FakeCentral:
    def __init__(self) -> None:
        self.name = "CentralTest"
        self.config = type("Cfg", (), {"central_id": "CentralTest"})()
        # Minimal helpers used by name generation (not used here)
        self.paramset_descriptions = type("PS", (), {"is_in_multiple_channels": lambda *_args, **_kw: False})()
        self.device_details = type("DD", (), {"get_name": lambda *_args, **_kw: None})()

        # Provide minimal parameter_visibility used by GenericDataPoint init
        class _PV:
            def parameter_is_hidden(self, *, channel, paramset_key, parameter) -> bool:  # noqa: D401, ANN001
                """In tests, nothing is hidden by default."""
                return False

            def parameter_is_un_ignored(self, *, channel, paramset_key, parameter, custom_only: bool) -> bool:  # noqa: D401, ANN001
                """In tests, default to False (not un-ignored)."""
                return False

        self.parameter_visibility = _PV()


class _FakeDevice:
    def __init__(self, model: str = "HmIP-XYZ", address: str = "ADDR1") -> None:
        self.interface_id = "ifid"
        self.address = address
        self.central = _FakeCentral()
        self.model = model
        self.name = "DeviceName"
        self.client = type("Client", (), {"interface": None})()
        self._store: dict[tuple[str, ParamsetKey | None], _FakeGenericDP] = {}

    def add_dp(self, dp: _FakeGenericDP) -> None:
        self._store[(dp.parameter, dp.paramset_key)] = dp

    def get_generic_data_point(
        self, *, channel_address: str, parameter: str, paramset_key: ParamsetKey | None
    ) -> _FakeGenericDP | None:
        return self._store.get((parameter, paramset_key))


class _FakeGenericDP:
    def __init__(
        self,
        *,
        parameter: str,
        paramset_key: ParamsetKey,
        value: Any = None,
        default: Any = None,
        readable: bool = True,
    ) -> None:
        self.parameter = parameter
        self.paramset_key = paramset_key
        self.value = value
        self.default = default
        self._readable = readable
        self._modified_at = INIT_DATETIME
        self._refreshed_at = INIT_DATETIME
        self.is_valid = True
        self.state_uncertain = False
        self.emitted_event_recently = True
        self._unregistered: list[bool] = []

    @property
    def is_readable(self) -> bool:
        return self._readable

    @property
    def modified_at(self) -> datetime:
        return self._modified_at

    @property
    def refreshed_at(self) -> datetime:
        return self._refreshed_at

    def register_internal_data_point_updated_callback(self, *, cb: Callable) -> Callable[[], None]:
        self.emitted_event_recently = False  # simulate change later

        def _unregister() -> None:
            self._unregistered.append(True)

        return _unregister

    def set_times(self, *, modified_delta: int, refreshed_delta: int) -> None:
        base = datetime.now()
        self._modified_at = base + timedelta(seconds=modified_delta)
        self._refreshed_at = base + timedelta(seconds=refreshed_delta)


class _FakeChannel:
    def __init__(self, model: str = "HmIP-XYZ", address: str = "ADDR1:1") -> None:
        self.central = _FakeCentral()
        self.device = _FakeDevice(model=model, address=address.split(":")[0])
        self.address = address
        self.no = int(address.split(":")[-1]) if ":" in address else 1
        self._store: dict[tuple[str, ParamsetKey | None], _FakeGenericDP] = {}

    def add_fake(self, dp: _FakeGenericDP) -> None:
        self._store[(dp.parameter, dp.paramset_key)] = dp

    # Channel-level DP getter used by calculated DPs
    def get_generic_data_point(self, *, parameter: str, paramset_key: ParamsetKey | None) -> _FakeGenericDP | None:
        return self._store.get((parameter, paramset_key))


# Tests from test_model_calculated_datapoint.py ------------------------------


class _MyCalc(CalculatedDataPoint[float | None]):
    """Concrete CalculatedDataPoint for testing with a custom parameter name."""

    _calculated_parameter = "TEST_CALC"

    def __init__(self, *, channel: _FakeChannel) -> None:  # type: ignore[override]
        super().__init__(channel=channel)  # type: ignore[arg-type]

    # Make two VALUES data points relevant so _should_emit_data_point_updated_callback checks the branch
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

    # _should_emit_data_point_updated_callback with >1 VALUES DPs requires all emitted_event_recently True
    # We set them via registration to False, so result should be False until we flip them
    assert calc._should_emit_data_point_updated_callback is False
    dp1.emitted_event_recently = True
    dp2.emitted_event_recently = True
    assert calc._should_emit_data_point_updated_callback is True

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


def test_calculated_datapoint_add_missing_returns_placeholder() -> None:
    """When a requested source DP is missing, a placeholder (DpDummy) is returned and stored."""
    ch = _FakeChannel()
    calc = _MyCalc(channel=ch)
    none_dp = calc._add_data_point(parameter="MISSING", paramset_key=ParamsetKey.VALUES, data_point_type=_FakeGenericDP)  # type: ignore[arg-type]
    # DpDummy is a GenericDataPoint-like placeholder; it exposes generic attributes safely
    assert hasattr(none_dp, "is_readable")
    # And the overall calc still exposes expected operation flags
    assert calc.is_readable is True
    assert calc.supports_events is True
    assert calc.is_writeable is False


def test_calculated_datapoint_misc_properties_and_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover misc getters, is_relevant_for_model default, load path, state_uncertain branch, and unregister None branch."""
    ch = _FakeChannel()
    # Prepare a readable VALUES dp with async load method
    dp = _FakeGenericDP(parameter="A", paramset_key=ParamsetKey.VALUES)

    async def _load_data_point_value(*_a, **_k) -> None:  # noqa: D401
        """Async stub to satisfy load_data_point_value loop."""
        return

    # Attach method dynamically
    setattr(dp, "load_data_point_value", _load_data_point_value)
    ch.add_fake(dp)

    calc = _MyCalc(channel=ch)
    calc._add_data_point(parameter="A", paramset_key=ParamsetKey.VALUES, data_point_type=_FakeGenericDP)  # type: ignore[arg-type]

    # Access simple properties to hit return lines
    _ = calc.default
    _ = calc.max
    _ = calc.min
    _ = calc.unit
    _ = calc.values
    _ = calc.visible
    _ = calc.hmtype
    _ = calc.data_point_name_postfix

    # is_relevant_for_model default on base class returns False
    assert CalculatedDataPoint.is_relevant_for_model(channel=ch) is False  # type: ignore[arg-type]

    # state_uncertain branch should return True when any relevant dp is uncertain
    dp.state_uncertain = True
    assert calc.is_state_change() is True

    # load_data_point_value should iterate and call emit callback safely
    def _noop(**_kwargs: Any) -> None:  # noqa: D401, ANN001
        """Do nothing. Synchronous no-op callback to satisfy the call inside load."""
        return

    monkeypatch.setattr(calc, "emit_data_point_updated_event", _noop)
    import asyncio

    asyncio.run(
        calc.load_data_point_value(call_source=None, direct_call=False)  # type: ignore[arg-type]
    )

    # Add a None into unregister callbacks list to hit the branch not calling it
    calc._unregister_callbacks.append(None)  # type: ignore[arg-type]

    # And then call unregister to iterate over both a callable and a None
    def dummy_cb2(**kwargs: Any) -> None:  # noqa: D401
        """Execute dummy callback for unregister path (None branch)."""

    calc._unregister_data_point_updated_callback(cb=dummy_cb2, custom_id="y")


# Tests from test_model_operating_voltage_level.py ---------------------------


@dataclass
class _FakeParameterData:
    default: Any = None


def test_is_relevant_true_with_operating_voltage_and_master_limit() -> None:
    """is_relevant_for_model should be true when model is supported and both DPs exist at channel level."""
    device = _FakeDevice(model="HmIP-SWDO")
    ch = _FakeChannel(model=device.model)
    ch.add_fake(_FakeGenericDP(parameter=Parameter.OPERATING_VOLTAGE, paramset_key=ParamsetKey.VALUES, value=2.6))
    ch.add_fake(
        _FakeGenericDP(parameter=Parameter.LOW_BAT_LIMIT, paramset_key=ParamsetKey.MASTER, value=2.0, default=2.0)
    )

    assert OperatingVoltageLevel.is_relevant_for_model(channel=ch) is True


def test_is_relevant_true_with_battery_state_and_device_master_limit() -> None:
    """is_relevant_for_model should be true when BATTERY_STATE exists and device-level LOW_BAT_LIMIT is present."""
    ch = _FakeChannel(model="HmIP-SWDO")
    ch.add_fake(_FakeGenericDP(parameter=Parameter.BATTERY_STATE, paramset_key=ParamsetKey.VALUES, value=2.5))
    # Provide LOW_BAT_LIMIT at device-level MASTER via the channel's device
    ch.device.add_dp(
        _FakeGenericDP(parameter=Parameter.LOW_BAT_LIMIT, paramset_key=ParamsetKey.MASTER, value=2.0, default=2.0)
    )

    assert OperatingVoltageLevel.is_relevant_for_model(channel=ch) is True


def test_is_relevant_false_for_unknown_model() -> None:
    """is_relevant_for_model should be false when the model is not in the supported list."""
    device = _FakeDevice(model="Unknown-Model-XYZ")
    ch = _FakeChannel(model=device.model)
    assert OperatingVoltageLevel.is_relevant_for_model(channel=ch) is False


def test_value_and_additional_information_and_low_bat_limit_property() -> None:
    """Value should compute percentage and additional_information should contain formatted battery data."""
    device = _FakeDevice(model="HmIP-SWDO")
    ch = _FakeChannel(model=device.model)
    # Use BATTERY_STATE path and device-level LOW_BAT_LIMIT
    ch.add_fake(_FakeGenericDP(parameter=Parameter.BATTERY_STATE, paramset_key=ParamsetKey.VALUES, value=2.5))
    # Add LOW_BAT_LIMIT to the channel's device-level store to match lookup in implementation
    ch.device.add_dp(
        _FakeGenericDP(parameter=Parameter.LOW_BAT_LIMIT, paramset_key=ParamsetKey.MASTER, value=2.0, default=2.0)
    )

    ovl = OperatingVoltageLevel(channel=ch)  # type: ignore[arg-type]

    # Verify _low_bat_limit property reads from dp
    assert ovl._low_bat_limit == 2.0

    # Calculate value using defaults derived from battery type/qty; should be a float percentage
    val = ovl.value
    assert val is None or isinstance(val, float)

    info = ovl.additional_information
    # Should contain formatted keys when battery data is known for model
    assert isinstance(info, dict)
    assert "Battery Qty" in info
    assert "Battery Type" in info
    assert "Low Battery Limit" in info
    assert "Voltage max" in info


def test_value_exception_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the helper raises, value should catch and return None without raising to caller."""
    device = _FakeDevice(model="HmIP-SWDO")
    ch = _FakeChannel(model=device.model)
    ch.add_fake(_FakeGenericDP(parameter=Parameter.OPERATING_VOLTAGE, paramset_key=ParamsetKey.VALUES, value=2.6))
    ch.add_fake(
        _FakeGenericDP(parameter=Parameter.LOW_BAT_LIMIT, paramset_key=ParamsetKey.MASTER, value=2.0, default=2.0)
    )

    ovl = OperatingVoltageLevel(channel=ch)  # type: ignore[arg-type]

    # Monkeypatch the helper used in value() to raise
    from aiohomematic.model.calculated import support as support_mod

    def raise_exc(*_a: object, **_k: object) -> None:
        raise RuntimeError("forced")

    monkeypatch.setattr(support_mod, "calculate_operating_voltage_level", raise_exc, raising=True)

    assert ovl.value is None


# Tests from test_model_calculated_support.py and _more.py --------------------


def test_calculate_vapor_concentration_basic() -> None:
    """Test calculating vapor concentration."""
    # 0% humidity should yield 0.0 regardless of temperature
    assert calculate_vapor_concentration(temperature=0.0, humidity=0) == 0.0
    # Typical indoor conditions should be a positive, reasonable value
    vc = calculate_vapor_concentration(temperature=25.0, humidity=50)
    assert vc is not None
    assert isinstance(vc, float)
    # Rough sanity bounds (absolute humidity at 25C/50% is ~10-13 g/m³)
    assert 8.0 <= vc <= 15.0


def test_calculate_dew_point_basic_and_zero_edge() -> None:
    """Test calculating dew point."""
    # Realistic mid-range input: dew point should be around 8-12C
    dp = calculate_dew_point(temperature=20.0, humidity=50)
    assert dp is not None
    assert 5.0 <= dp <= 15.0
    # Special error-handling branch returns 0.0 for (0,0)
    # This path occurs via math domain error during log(0), caught by except
    dp_zero = calculate_dew_point(temperature=0.0, humidity=0)
    assert dp_zero == 0.0


def test_calculate_dew_point_invalid_humidity() -> None:
    """Test calculating dew point."""
    # Negative humidity triggers ValueError in log due to negative vp
    dp = calculate_dew_point(temperature=20.0, humidity=-10)
    assert dp is None


def test_calculate_apparent_temperature_wind_chill_heat_index_and_normal() -> None:
    """Test calculating apparent temperature wind chill heat and normal."""
    # Wind chill case (temp <= 10 and wind_speed > 4.8) -> less than ambient
    at_wind = calculate_apparent_temperature(temperature=5.0, humidity=50, wind_speed=10.0)
    assert at_wind is not None
    assert at_wind < 5.0

    # Heat index case (temp >= 26.7) -> greater than ambient in humid conditions
    at_heat = calculate_apparent_temperature(temperature=30.0, humidity=70, wind_speed=2.0)
    assert at_heat is not None
    assert at_heat > 30.0

    # Normal case -> equals temperature (rounded)
    at_norm = calculate_apparent_temperature(temperature=20.0, humidity=50, wind_speed=1.0)
    assert at_norm == 20.0


def test_calculate_apparent_temperature_zero_edge() -> None:
    """Test calculating apparent temperature edge."""
    # For 0C and 0% humidity with low wind, function should return 0.0 (no exception branch needed here)
    assert calculate_apparent_temperature(temperature=0.0, humidity=0, wind_speed=1.0) == 0.0


def test_calculate_frost_point_normal_and_none_branch() -> None:
    """Test calculating frost point."""
    # Normal humid cold air -> frost point should be <= temperature and usually <= 0
    fp = calculate_frost_point(temperature=0.0, humidity=80)
    assert fp is not None
    assert fp <= 0.0
    assert fp <= 0.0 <= 0.1  # ensure it's not a positive number

    # If dew point cannot be computed -> frost point None
    fp_none = calculate_frost_point(temperature=20.0, humidity=-10)
    assert fp_none is None


def test_calculate_frost_point_zero_zero() -> None:
    """Test calculating frost point."""
    # For (0,0), dew point returns 0.0 and frost point can be computed without error
    fp = calculate_frost_point(temperature=0.0, humidity=0)
    assert fp is not None
    # Should be a finite float
    assert isinstance(fp, float)
    assert math.isfinite(fp)


def test_calculate_dew_point_zero_zero_returns_zero_point_zero() -> None:
    """Test calculating frost point."""
    # Edge case handled in implementation: temperature == 0.0 and humidity == 0 returns 0.0
    assert calculate_dew_point(temperature=0.0, humidity=0) == 0.0


@pytest.mark.parametrize(
    ("temperature", "humidity", "wind_speed", "expected"),
    [
        # Wind speed at boundary 4.8 should NOT apply wind chill; returns ambient temp rounded
        (10.0, 50, 4.8, 10.0),
        # Below threshold wind with low temp should also return ambient temp
        (5.0, 50, 4.0, 5.0),
    ],
)
def test_apparent_temperature_wind_chill_boundary(temperature, humidity, wind_speed, expected) -> None:
    """Test apparent temperature wind chill boundary."""
    assert calculate_apparent_temperature(temperature=temperature, humidity=humidity, wind_speed=wind_speed) == expected


def test_apparent_temperature_heat_index_boundary() -> None:
    """Test apparent temperature heat index boundary."""
    # Exactly at 26.7C must trigger heat index calculation
    at = calculate_apparent_temperature(temperature=26.7, humidity=60, wind_speed=0.0)
    assert at is not None
    # Should be greater or equal to the ambient temperature due to humidity
    assert at >= 26.7


def test_dew_point_mid_range_precision() -> None:
    """Test dew point mid-range precision."""
    # Verify dew point is a finite float with typical conditions
    dp = calculate_dew_point(temperature=22.0, humidity=55)
    assert isinstance(dp, float)
    assert math.isfinite(dp)
    assert 8.0 <= dp <= 16.0


@pytest.mark.parametrize(
    ("operating_voltage", "low_bat_limit", "voltage_max"),
    [
        (None, 2.0, 3.0),
        (2.5, None, 3.0),
        (2.5, 2.0, None),
    ],
)
def test_calculate_operating_voltage_level_none_inputs(operating_voltage, low_bat_limit, voltage_max) -> None:
    """If any input is None, the result should be None."""
    assert (
        calculate_operating_voltage_level(
            operating_voltage=operating_voltage, low_bat_limit=low_bat_limit, voltage_max=voltage_max
        )
        is None
    )


def test_calculate_operating_voltage_level_normal() -> None:
    """Typical calculation with rounding to one decimal."""
    # ((2.5 - 2.0) / (3.0 - 2.0)) * 100 = 50.0
    assert calculate_operating_voltage_level(operating_voltage=2.5, low_bat_limit=2.0, voltage_max=3.0) == 50.0

    """Validate rounding to one decimal place."""
    # ((2.26 - 2.0) / 1.0) * 100 = 26.0 -> 26.0
    assert calculate_operating_voltage_level(operating_voltage=2.26, low_bat_limit=2.0, voltage_max=3.0) == 26.0
    # ((2.255 - 2.0) / 1.0) * 100 = 25.5 -> 25.5 exact boundary
    assert calculate_operating_voltage_level(operating_voltage=2.255, low_bat_limit=2.0, voltage_max=3.0) == 25.5

    """Values below or equal to low_bat_limit clamp to 0."""
    assert calculate_operating_voltage_level(operating_voltage=1.9, low_bat_limit=2.0, voltage_max=3.0) == 0.0
    assert calculate_operating_voltage_level(operating_voltage=2.0, low_bat_limit=2.0, voltage_max=3.0) == 0.0

    """Values above or equal to voltage_max clamp to 100."""
    assert calculate_operating_voltage_level(operating_voltage=3.5, low_bat_limit=2.0, voltage_max=3.0) == 100.0
    assert calculate_operating_voltage_level(operating_voltage=3.0, low_bat_limit=2.0, voltage_max=3.0) == 100.0


def test_calculate_dew_point_spread_basic() -> None:
    """Test dew point spread uses dew point calculation and rounds to two decimals."""
    # With T=20, H=50 -> dew point around 9.3, spread 10.7
    assert calculate_dew_point_spread(temperature=20.0, humidity=50) == 10.7


def test_calculate_enthalpy_basic_rounding() -> None:
    """Test enthalpy returns a rounded float for typical indoor conditions."""
    h = calculate_enthalpy(temperature=22.0, humidity=45)
    assert isinstance(h, float)
    # Ensure value is rounded to two decimals according to implementation
    assert round(h, 2) == h


# Tests from test_model_calculated_support_more.py exceptional branches -------


def test_dew_point_spread_returns_none_when_dew_point_none() -> None:
    """dew_point_spread should return None when dew point calculation fails (e.g. invalid humidity)."""
    # Invalid humidity (<0) causes calculate_dew_point to return None
    assert calculate_dew_point_spread(temperature=20.0, humidity=-5) is None


def test__calculate_heat_index_else_branch() -> None:
    """Directly exercise the lower branch of _calculate_heat_index where the 80°F average condition is not met."""
    from aiohomematic.model.calculated import support as support_mod

    # Choose temperature/humidity such that ((HI_F + T_F)/2) < 80 to hit the else branch
    # temp=27C, humidity=0% -> satisfies the else-branch condition in the helper
    hi = support_mod._calculate_heat_index(temperature=27.0, humidity=0)
    # Should be a float in Celsius converted from the simple formula path
    assert isinstance(hi, float)


def test__calculate_wind_chill_invalid_returns_none() -> None:
    """_calculate_wind_chill should return None when outside its definition domain (temp > 10C or wind <= 4.8)."""
    from aiohomematic.model.calculated import support as support_mod

    assert support_mod._calculate_wind_chill(temperature=11.0, wind_speed=10.0) is None
    assert support_mod._calculate_wind_chill(temperature=0.0, wind_speed=4.8) is None


def test_calculate_vapor_concentration_value_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force a ValueError in vapor concentration to exercise the exception logging path and None return."""
    from aiohomematic.model.calculated import support as support_mod

    def raise_value_error(x: float) -> float:  # noqa: ANN001
        raise ValueError("forced")

    # Patch math.exp used inside the module
    monkeypatch.setattr(support_mod.math, "exp", raise_value_error, raising=True)
    assert calculate_vapor_concentration(temperature=20.0, humidity=50) is None


def test_calculate_apparent_temperature_value_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force a ValueError in the heat index helper to trigger logging and a None return."""
    from aiohomematic.model.calculated import support as support_mod

    def raise_value_error(*_args: object, **_kwargs: object) -> float:
        raise ValueError("forced")

    monkeypatch.setattr(support_mod, "_calculate_heat_index", raise_value_error, raising=True)
    # Use parameters that would otherwise take the heat index branch
    assert calculate_apparent_temperature(temperature=30.0, humidity=60, wind_speed=0.0) is None


def test_calculate_frost_point_value_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force a ValueError in frost point math to exercise exception handling and None return."""
    from aiohomematic.model.calculated import support as support_mod

    # Ensure dew point can be computed first, then break math.log used in frost computation
    def raise_value_error(*_args: object, **_kwargs: object) -> float:
        raise ValueError("forced")

    monkeypatch.setattr(support_mod.math, "log", raise_value_error, raising=True)
    assert calculate_frost_point(temperature=5.0, humidity=50) is None


# Climate-related calculated tests formerly in test_model_climate.py ----------


@pytest.mark.asyncio
async def test_apparent_temperature_relevance_and_value_paths() -> None:
    """ApparentTemperature should check model + required DPs and compute value or None accordingly."""
    # Relevant model and all required DPs present
    ch_ok = _FakeChannel(model="HmIP-SWO")
    ch_ok.add_fake(_FakeGenericDP(parameter="ACTUAL_TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=22.0))
    ch_ok.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=55.0))
    ch_ok.add_fake(_FakeGenericDP(parameter="WIND_SPEED", paramset_key=ParamsetKey.VALUES, value=3.0))

    assert ApparentTemperature.is_relevant_for_model(channel=ch_ok) is True
    at = ApparentTemperature(channel=ch_ok)
    # Value present: compare to support function for robustness
    assert at.value == pytest.approx(calculate_apparent_temperature(temperature=22.0, humidity=55.0, wind_speed=3.0))

    # If one value is None, the calculated DP should return None
    ch_none = _FakeChannel(model="HmIP-SWO")
    ch_none.add_fake(_FakeGenericDP(parameter="ACTUAL_TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=None))
    ch_none.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=55.0))
    ch_none.add_fake(_FakeGenericDP(parameter="WIND_SPEED", paramset_key=ParamsetKey.VALUES, value=3.0))
    at_none = ApparentTemperature(channel=ch_none)
    assert at_none.value is None

    # Not relevant model -> relevance false
    ch_bad_model = _FakeChannel(model="HmIP-OTHER")
    ch_bad_model.add_fake(_FakeGenericDP(parameter="ACTUAL_TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=22.0))
    ch_bad_model.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=55.0))
    ch_bad_model.add_fake(_FakeGenericDP(parameter="WIND_SPEED", paramset_key=ParamsetKey.VALUES, value=3.0))
    assert ApparentTemperature.is_relevant_for_model(channel=ch_bad_model) is False


def test_dew_point_relevance_with_fallbacks_and_value() -> None:
    """DewPoint relevance uses TEMPERATURE or ACTUAL_TEMPERATURE and HUMIDITY or ACTUAL_HUMIDITY."""
    # Case 1: Use standard TEMPERATURE and HUMIDITY
    ch_std = _FakeChannel(model="Any")
    ch_std.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=20.0))
    ch_std.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=40.0))
    assert DewPoint.is_relevant_for_model(channel=ch_std) is True
    dp1 = DewPoint(channel=ch_std)
    assert dp1.value == pytest.approx(calculate_dew_point(temperature=20.0, humidity=40.0))

    # Case 2: Fallback to ACTUAL_TEMPERATURE and ACTUAL_HUMIDITY
    ch_fb = _FakeChannel(model="Any")
    ch_fb.add_fake(_FakeGenericDP(parameter="ACTUAL_TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=21.5))
    ch_fb.add_fake(_FakeGenericDP(parameter="ACTUAL_HUMIDITY", paramset_key=ParamsetKey.VALUES, value=35.0))
    assert DewPoint.is_relevant_for_model(channel=ch_fb) is True
    dp2 = DewPoint(channel=ch_fb)
    assert dp2.value == pytest.approx(calculate_dew_point(temperature=21.5, humidity=35.0))

    # Missing one DP -> relevance false and value None
    ch_missing = _FakeChannel(model="Any")
    ch_missing.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=20.0))
    assert DewPoint.is_relevant_for_model(channel=ch_missing) is False
    dp_missing = DewPoint(channel=ch_missing)
    assert dp_missing.value is None


def test_dew_point_spread_and_enthalpy_and_vapor_concentration() -> None:
    """Value computations for other climate sensors and None branch when inputs missing."""
    # DewPointSpread
    ch1 = _FakeChannel(model="Any")
    ch1.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=24.0))
    ch1.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=50.0))
    dps = DewPointSpread(channel=ch1)
    assert dps.value == pytest.approx(calculate_dew_point_spread(temperature=24.0, humidity=50.0))

    # Enthalpy
    ch2 = _FakeChannel(model="Any")
    ch2.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=18.0))
    ch2.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=60.0))
    enth = Enthalpy(channel=ch2)
    assert enth.value == pytest.approx(calculate_enthalpy(temperature=18.0, humidity=60.0))

    # VaporConcentration
    ch3 = _FakeChannel(model="Any")
    ch3.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=23.0))
    ch3.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=45.0))
    vap = VaporConcentration(channel=ch3)
    assert vap.value == pytest.approx(calculate_vapor_concentration(temperature=23.0, humidity=45.0))

    # Missing value path returns None
    ch4 = _FakeChannel(model="Any")
    ch4.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=None))
    ch4.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=45.0))
    assert Enthalpy(channel=ch4).value is None
    assert VaporConcentration(channel=ch4).value is None


def test_frost_point_relevance_filter_and_value() -> None:
    """FrostPoint should honor relevant model filter and DP presence."""
    # Relevant models include HmIP-SWO and HmIP-STHO
    ch_rel = _FakeChannel(model="HmIP-STHO")
    ch_rel.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=0.0))
    ch_rel.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=80.0))
    assert FrostPoint.is_relevant_for_model(channel=ch_rel) is True
    fr = FrostPoint(channel=ch_rel)
    assert fr.value == pytest.approx(calculate_frost_point(temperature=0.0, humidity=80.0))

    # Non-relevant model should result in relevance False even if DPs exist
    ch_irrel = _FakeChannel(model="HmIP-ABC")
    ch_irrel.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=-5.0))
    ch_irrel.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=70.0))
    assert FrostPoint.is_relevant_for_model(channel=ch_irrel) is False


def test_helper_is_relevant_temperature_and_humidity_branches() -> None:
    """Cover helper branches: with relevant_models filter and both TEMPERATURE/ACTUAL_* combos."""
    # 1) With relevant_models filter: match -> True when DPs exist
    ch_a = _FakeChannel(model="HmIP-SWO")
    ch_a.add_fake(_FakeGenericDP(parameter="ACTUAL_TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=10.0))
    ch_a.add_fake(_FakeGenericDP(parameter="ACTUAL_HUMIDITY", paramset_key=ParamsetKey.VALUES, value=30.0))
    assert _is_relevant_for_model_temperature_and_humidity(channel=ch_a, relevant_models=("HmIP-SWO",)) is True

    # 2) With relevant_models filter: no match -> False
    ch_b = _FakeChannel(model="HmIP-OTHER")
    ch_b.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=10.0))
    ch_b.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=30.0))
    assert _is_relevant_for_model_temperature_and_humidity(channel=ch_b, relevant_models=("HmIP-SWO",)) is False

    # 3) Without relevant_models: only DP presence decides; missing HUMIDITY path -> False
    ch_c = _FakeChannel(model="Any")
    ch_c.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=10.0))
    assert _is_relevant_for_model_temperature_and_humidity(channel=ch_c) is False

    # 4) Without relevant_models: presence of TEMPERATURE and HUMIDITY -> True
    ch_d = _FakeChannel(model="Any")
    ch_d.add_fake(_FakeGenericDP(parameter="TEMPERATURE", paramset_key=ParamsetKey.VALUES, value=10.0))
    ch_d.add_fake(_FakeGenericDP(parameter="HUMIDITY", paramset_key=ParamsetKey.VALUES, value=30.0))
    assert _is_relevant_for_model_temperature_and_humidity(channel=ch_d) is True
