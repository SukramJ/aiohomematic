# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Custom light data points for dimmers and colored lighting.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
import math
from typing import Any, Final, TypedDict, Unpack

from aiohomematic.const import DataPointCategory, DataPointUsage, DeviceProfile, Field, Parameter
from aiohomematic.model.custom.data_point import CustomDataPoint
from aiohomematic.model.custom.mixins import BrightnessMixin, StateChangeTimerMixin, TimerUnitMixin
from aiohomematic.model.custom.registry import DeviceConfig, DeviceProfileRegistry, ExtendedDeviceConfig
from aiohomematic.model.data_point import CallParameterCollector, bind_collector
from aiohomematic.model.generic import DpAction, DpFloat, DpInteger, DpSelect, DpSensor, GenericDataPointAny
from aiohomematic.property_decorators import state_property

_DIMMER_OFF: Final = 0.0
_EFFECT_OFF: Final = "Off"
_LEVEL_TO_BRIGHTNESS_MULTIPLIER: Final = 100
_MAX_BRIGHTNESS: Final = 255.0
_MAX_KELVIN: Final = 1000000
_MAX_MIREDS: Final = 500
_MAX_SATURATION: Final = 100.0
_MIN_BRIGHTNESS: Final = 0.0
_MIN_HUE: Final = 0.0
_MIN_MIREDS: Final = 153
_MIN_SATURATION: Final = 0.0
_NOT_USED: Final = 111600
_SATURATION_MULTIPLIER: Final = 100


class _DeviceOperationMode(StrEnum):
    """Enum with device operation modes."""

    PWM = "4_PWM"
    RGB = "RGB"
    RGBW = "RGBW"
    TUNABLE_WHITE = "2_TUNABLE_WHITE"


class _ColorBehaviour(StrEnum):
    """Enum with color behaviours."""

    DO_NOT_CARE = "DO_NOT_CARE"
    OFF = "OFF"
    OLD_VALUE = "OLD_VALUE"
    ON = "ON"


class _FixedColor(StrEnum):
    """Enum with colors."""

    BLACK = "BLACK"
    BLUE = "BLUE"
    DO_NOT_CARE = "DO_NOT_CARE"
    GREEN = "GREEN"
    OLD_VALUE = "OLD_VALUE"
    PURPLE = "PURPLE"
    RED = "RED"
    TURQUOISE = "TURQUOISE"
    WHITE = "WHITE"
    YELLOW = "YELLOW"


class _StateChangeArg(StrEnum):
    """Enum with light state change arguments."""

    BRIGHTNESS = "brightness"
    COLOR_TEMP_KELVIN = "color_temp_kelvin"
    EFFECT = "effect"
    HS_COLOR = "hs_color"
    OFF = "off"
    ON = "on"
    ON_TIME = "on_time"
    RAMP_TIME = "ramp_time"


_NO_COLOR: Final = (
    _FixedColor.BLACK,
    _FixedColor.DO_NOT_CARE,
    _FixedColor.OLD_VALUE,
)

_EXCLUDE_FROM_COLOR_BEHAVIOUR: Final = (
    _ColorBehaviour.DO_NOT_CARE,
    _ColorBehaviour.OFF,
    _ColorBehaviour.OLD_VALUE,
)

_OFF_COLOR_BEHAVIOUR: Final = (
    _ColorBehaviour.DO_NOT_CARE,
    _ColorBehaviour.OFF,
    _ColorBehaviour.OLD_VALUE,
)

_FIXED_COLOR_SWITCHER: Mapping[str, tuple[float, float]] = {
    _FixedColor.WHITE: (_MIN_HUE, _MIN_SATURATION),
    _FixedColor.RED: (_MIN_HUE, _MAX_SATURATION),
    _FixedColor.YELLOW: (60.0, _MAX_SATURATION),
    _FixedColor.GREEN: (120.0, _MAX_SATURATION),
    _FixedColor.TURQUOISE: (180.0, _MAX_SATURATION),
    _FixedColor.BLUE: (240.0, _MAX_SATURATION),
    _FixedColor.PURPLE: (300.0, _MAX_SATURATION),
}


class LightOnArgs(TypedDict, total=False):
    """Matcher for the light turn on arguments."""

    brightness: int
    color_temp_kelvin: int
    effect: str
    hs_color: tuple[float, float]
    on_time: float
    ramp_time: float


class LightOffArgs(TypedDict, total=False):
    """Matcher for the light turn off arguments."""

    on_time: float
    ramp_time: float


class CustomDpDimmer(StateChangeTimerMixin, BrightnessMixin, CustomDataPoint):
    """Base class for Homematic light data point."""

    __slots__ = (
        "_dp_group_level",
        "_dp_level",
        "_dp_on_time_value",
        "_dp_ramp_time_value",
    )
    _category = DataPointCategory.LIGHT

    @property
    def brightness_pct(self) -> int | None:
        """Return the brightness in percent of this light."""
        return self.level_to_brightness_pct(self._dp_level.value or _MIN_BRIGHTNESS)

    @property
    def group_brightness(self) -> int | None:
        """Return the group brightness of this light between min/max brightness."""
        if self._dp_group_level.value is not None:
            return self.level_to_brightness(self._dp_group_level.value)
        return None

    @property
    def group_brightness_pct(self) -> int | None:
        """Return the group brightness in percent of this light."""
        if self._dp_group_level.value is not None:
            return self.level_to_brightness_pct(self._dp_group_level.value)
        return None

    @property
    def supports_brightness(self) -> bool:
        """Flag if light supports brightness."""
        return isinstance(self._dp_level, DpFloat)

    @property
    def supports_color_temperature(self) -> bool:
        """Flag if light supports color temperature."""
        return self.color_temp_kelvin is not None

    @property
    def supports_effects(self) -> bool:
        """Flag if light supports effects."""
        return self.effects is not None and len(self.effects) > 0

    @property
    def supports_hs_color(self) -> bool:
        """Flag if light supports color."""
        return self.hs_color is not None

    @property
    def supports_transition(self) -> bool:
        """Flag if light supports transition."""
        return isinstance(self._dp_ramp_time_value, DpAction)

    @state_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between min/max brightness."""
        return self.level_to_brightness(self._dp_level.value or _MIN_BRIGHTNESS)

    @state_property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        return None

    @state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        return None

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return None

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return None

    @state_property
    def is_on(self) -> bool | None:
        """Return true if dimmer is on."""
        return self._dp_level.value is not None and self._dp_level.value > _DIMMER_OFF

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if self.is_timer_state_change():
            return True
        if kwargs.get(_StateChangeArg.ON_TIME) is not None:
            return True
        if kwargs.get(_StateChangeArg.RAMP_TIME) is not None:
            return True
        if kwargs.get(_StateChangeArg.ON) is not None and self.is_on is not True and len(kwargs) == 1:
            return True
        if kwargs.get(_StateChangeArg.OFF) is not None and self.is_on is not False and len(kwargs) == 1:
            return True
        if (brightness := kwargs.get(_StateChangeArg.BRIGHTNESS)) is not None and brightness != self.brightness:
            return True
        if (hs_color := kwargs.get(_StateChangeArg.HS_COLOR)) is not None and hs_color != self.hs_color:
            return True
        if (
            color_temp_kelvin := kwargs.get(_StateChangeArg.COLOR_TEMP_KELVIN)
        ) is not None and color_temp_kelvin != self.color_temp_kelvin:
            return True
        if (effect := kwargs.get(_StateChangeArg.EFFECT)) is not None and effect != self.effect:
            return True
        return super().is_state_change(**kwargs)

    @bind_collector
    async def turn_off(
        self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOffArgs]
    ) -> None:
        """Turn the light off."""
        self.reset_timer_on_time()
        if not self.is_state_change(off=True, **kwargs):
            return
        if ramp_time := kwargs.get("ramp_time"):
            await self._set_ramp_time_off_value(ramp_time=ramp_time, collector=collector)
        await self._dp_level.send_value(value=_DIMMER_OFF, collector=collector)

    @bind_collector
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if (on_time := kwargs.get("on_time")) is not None:
            self.set_timer_on_time(on_time=on_time)
        if not self.is_state_change(on=True, **kwargs):
            return

        if (timer := self.get_and_start_timer()) is not None:
            await self._set_on_time_value(on_time=timer, collector=collector)
        if ramp_time := kwargs.get("ramp_time"):
            await self._set_ramp_time_on_value(ramp_time=ramp_time, collector=collector)
        if not (brightness := kwargs.get("brightness", self.brightness)):
            brightness = int(_MAX_BRIGHTNESS)
        level = self.brightness_to_level(brightness)
        await self._dp_level.send_value(value=level, collector=collector)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_level: DpFloat = self._get_data_point(field=Field.LEVEL, data_point_type=DpFloat)
        self._dp_group_level: DpSensor[float | None] = self._get_data_point(
            field=Field.GROUP_LEVEL, data_point_type=DpSensor[float | None]
        )
        self._dp_on_time_value: DpAction = self._get_data_point(field=Field.ON_TIME_VALUE, data_point_type=DpAction)
        self._dp_ramp_time_value: DpAction = self._get_data_point(field=Field.RAMP_TIME_VALUE, data_point_type=DpAction)

    @bind_collector
    async def _set_on_time_value(self, *, on_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the on time value in seconds."""
        await self._dp_on_time_value.send_value(value=on_time, collector=collector, do_validate=False)

    async def _set_ramp_time_off_value(
        self, *, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        await self._set_ramp_time_on_value(ramp_time=ramp_time, collector=collector)

    async def _set_ramp_time_on_value(
        self, *, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        await self._dp_ramp_time_value.send_value(value=ramp_time, collector=collector)


class CustomDpColorDimmer(CustomDpDimmer):
    """Class for Homematic dimmer with color data point."""

    __slots__ = ("_dp_color",)

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if (color := self._dp_color.value) is not None:
            if color >= 200:
                # 200 is a special case (white), so we have a saturation of 0.
                # Larger values are undefined.
                # For the sake of robustness we return "white" anyway.
                return _MIN_HUE, _MIN_SATURATION

            # For all other colors we assume saturation of 1
            return color / 200 * 360, _MAX_SATURATION
        return _MIN_HUE, _MIN_SATURATION

    @bind_collector
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            khue, ksaturation = hs_color
            hue = khue / 360
            saturation = ksaturation / _SATURATION_MULTIPLIER
            color = 200 if saturation < 0.1 else int(round(max(min(hue, 1), 0) * 199))
            await self._dp_color.send_value(value=color, collector=collector)
        await super().turn_on(collector=collector, **kwargs)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_color: DpInteger = self._get_data_point(field=Field.COLOR, data_point_type=DpInteger)


class CustomDpColorDimmerEffect(CustomDpColorDimmer):
    """Class for Homematic dimmer with color data point."""

    __slots__ = ("_dp_effect",)

    _effects: tuple[str, ...] = (
        _EFFECT_OFF,
        "Slow color change",
        "Medium color change",
        "Fast color change",
        "Campemit",
        "Waterfall",
        "TV simulation",
    )

    @state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        if self._dp_effect.value is not None:
            return self._effects[int(self._dp_effect.value)]
        return None

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._effects

    @bind_collector
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return

        if "effect" not in kwargs and self.supports_effects and self.effect != _EFFECT_OFF:
            await self._dp_effect.send_value(value=0, collector=collector, collector_order=5)

        if (
            self.supports_effects
            and (effect := kwargs.get("effect")) is not None
            and (effect_idx := self._effects.index(effect)) is not None
        ):
            await self._dp_effect.send_value(value=effect_idx, collector=collector, collector_order=95)

        await super().turn_on(collector=collector, **kwargs)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_effect: DpInteger = self._get_data_point(field=Field.PROGRAM, data_point_type=DpInteger)


class CustomDpColorTempDimmer(CustomDpDimmer):
    """Class for Homematic dimmer with color temperature."""

    __slots__ = ("_dp_color_level",)

    @state_property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        return math.floor(
            _MAX_KELVIN / int(_MAX_MIREDS - (_MAX_MIREDS - _MIN_MIREDS) * (self._dp_color_level.value or _DIMMER_OFF))
        )

    @bind_collector
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (color_temp_kelvin := kwargs.get("color_temp_kelvin")) is not None:
            color_level = (_MAX_MIREDS - math.floor(_MAX_KELVIN / color_temp_kelvin)) / (_MAX_MIREDS - _MIN_MIREDS)
            await self._dp_color_level.send_value(value=color_level, collector=collector)

        await super().turn_on(collector=collector, **kwargs)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_color_level: DpFloat = self._get_data_point(field=Field.COLOR_LEVEL, data_point_type=DpFloat)


class CustomDpIpRGBWLight(TimerUnitMixin, CustomDpDimmer):
    """Class for HomematicIP HmIP-RGBW light data point."""

    __slots__ = (
        "_dp_activity_state",
        "_dp_color_temperature_kelvin",
        "_dp_device_operation_mode",
        "_dp_effect",
        "_dp_hue",
        "_dp_on_time_unit",
        "_dp_ramp_time_to_off_unit",
        "_dp_ramp_time_to_off_value",
        "_dp_ramp_time_unit",
        "_dp_saturation",
    )

    @property
    def _device_operation_mode(self) -> _DeviceOperationMode:
        """Return the device operation mode."""
        try:
            return _DeviceOperationMode(str(self._dp_device_operation_mode.value))
        except Exception:
            # Fallback to a sensible default if the value is not set or unexpected
            return _DeviceOperationMode.RGBW

    @property
    def _relevant_data_points(self) -> tuple[GenericDataPointAny, ...]:
        """Returns the list of relevant data points. To be overridden by subclasses."""
        if self._device_operation_mode == _DeviceOperationMode.RGBW:
            return (
                self._dp_hue,
                self._dp_level,
                self._dp_saturation,
                self._dp_color_temperature_kelvin,
            )
        if self._device_operation_mode == _DeviceOperationMode.RGB:
            return self._dp_hue, self._dp_level, self._dp_saturation
        if self._device_operation_mode == _DeviceOperationMode.TUNABLE_WHITE:
            return self._dp_level, self._dp_color_temperature_kelvin
        return (self._dp_level,)

    @property
    def supports_color_temperature(self) -> bool:
        """Flag if light supports color temperature."""
        return self._device_operation_mode == _DeviceOperationMode.TUNABLE_WHITE

    @property
    def supports_effects(self) -> bool:
        """Flag if light supports effects."""
        return (
            self._device_operation_mode != _DeviceOperationMode.PWM
            and self.effects is not None
            and len(self.effects) > 0
        )

    @property
    def supports_hs_color(self) -> bool:
        """Flag if light supports color."""
        return self._device_operation_mode in (
            _DeviceOperationMode.RGBW,
            _DeviceOperationMode.RGB,
        )

    @property
    def usage(self) -> DataPointUsage:
        """
        Return the data_point usage.

        Avoid creating data points that are not usable in selected device operation mode.
        """
        if (
            self._device_operation_mode in (_DeviceOperationMode.RGB, _DeviceOperationMode.RGBW)
            and self._channel.no in (2, 3, 4)
        ) or (self._device_operation_mode == _DeviceOperationMode.TUNABLE_WHITE and self._channel.no in (3, 4)):
            return DataPointUsage.NO_CREATE
        return self._get_data_point_usage()

    @state_property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        if not self._dp_color_temperature_kelvin.value:
            return None
        return self._dp_color_temperature_kelvin.value

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._dp_effect.values or ()

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._dp_hue.value is not None and self._dp_saturation.value is not None:
            return self._dp_hue.value, self._dp_saturation.value * _SATURATION_MULTIPLIER
        return None

    @bind_collector
    async def turn_off(
        self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOffArgs]
    ) -> None:
        """Turn the light off."""
        if kwargs.get("on_time") is None and kwargs.get("ramp_time"):
            await self._set_on_time_value(on_time=_NOT_USED, collector=collector)
        await super().turn_off(collector=collector, **kwargs)

    @bind_collector
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if on_time := (kwargs.get("on_time") or self.get_and_start_timer()):
            kwargs["on_time"] = on_time
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            hue, ksaturation = hs_color
            saturation = ksaturation / _SATURATION_MULTIPLIER
            await self._dp_hue.send_value(value=int(hue), collector=collector)
            await self._dp_saturation.send_value(value=saturation, collector=collector)
        if color_temp_kelvin := kwargs.get("color_temp_kelvin"):
            await self._dp_color_temperature_kelvin.send_value(value=color_temp_kelvin, collector=collector)
        if on_time is None and kwargs.get("ramp_time"):
            await self._set_on_time_value(on_time=_NOT_USED, collector=collector)
        if self.supports_effects and (effect := kwargs.get("effect")) is not None:
            await self._dp_effect.send_value(value=effect, collector=collector)

        await super().turn_on(collector=collector, **kwargs)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_activity_state: DpSensor[str | None] = self._get_data_point(
            field=Field.DIRECTION, data_point_type=DpSensor[str | None]
        )
        self._dp_color_temperature_kelvin: DpInteger = self._get_data_point(
            field=Field.COLOR_TEMPERATURE, data_point_type=DpInteger
        )
        self._dp_device_operation_mode: DpSelect = self._get_data_point(
            field=Field.DEVICE_OPERATION_MODE, data_point_type=DpSelect
        )
        self._dp_on_time_unit: DpAction = self._get_data_point(field=Field.ON_TIME_UNIT, data_point_type=DpAction)
        self._dp_effect: DpAction = self._get_data_point(field=Field.EFFECT, data_point_type=DpAction)
        self._dp_hue: DpInteger = self._get_data_point(field=Field.HUE, data_point_type=DpInteger)
        self._dp_ramp_time_to_off_unit: DpAction = self._get_data_point(
            field=Field.RAMP_TIME_TO_OFF_UNIT, data_point_type=DpAction
        )
        self._dp_ramp_time_to_off_value: DpAction = self._get_data_point(
            field=Field.RAMP_TIME_TO_OFF_VALUE, data_point_type=DpAction
        )
        self._dp_ramp_time_unit: DpAction = self._get_data_point(field=Field.RAMP_TIME_UNIT, data_point_type=DpAction)
        self._dp_saturation: DpFloat = self._get_data_point(field=Field.SATURATION, data_point_type=DpFloat)

    @bind_collector
    async def _set_on_time_value(self, *, on_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the on time value with automatic unit conversion."""
        on_time, on_time_unit = self._recalc_unit_timer(time=on_time)
        if on_time_unit is not None:
            await self._dp_on_time_unit.send_value(value=on_time_unit, collector=collector)
        await self._dp_on_time_value.send_value(value=float(on_time), collector=collector)

    async def _set_ramp_time_off_value(
        self, *, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time off value with automatic unit conversion."""
        ramp_time, ramp_time_unit = self._recalc_unit_timer(time=ramp_time)
        if ramp_time_unit is not None:
            await self._dp_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._dp_ramp_time_value.send_value(value=float(ramp_time), collector=collector)

    async def _set_ramp_time_on_value(
        self, *, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time on value with automatic unit conversion."""
        ramp_time, ramp_time_unit = self._recalc_unit_timer(time=ramp_time)
        if ramp_time_unit is not None:
            await self._dp_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._dp_ramp_time_value.send_value(value=float(ramp_time), collector=collector)


class CustomDpIpDrgDaliLight(TimerUnitMixin, CustomDpDimmer):
    """Class for HomematicIP HmIP-DRG-DALI light data point."""

    __slots__ = (
        "_dp_color_temperature_kelvin",
        "_dp_effect",
        "_dp_hue",
        "_dp_on_time_unit",
        "_dp_ramp_time_to_off_unit",
        "_dp_ramp_time_to_off_value",
        "_dp_ramp_time_unit",
        "_dp_saturation",
    )

    @property
    def _relevant_data_points(self) -> tuple[GenericDataPointAny, ...]:
        """Returns the list of relevant data points. To be overridden by subclasses."""
        return (self._dp_level,)

    @state_property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        if not self._dp_color_temperature_kelvin.value:
            return None
        return self._dp_color_temperature_kelvin.value

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._dp_effect.values or ()

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._dp_hue.value is not None and self._dp_saturation.value is not None:
            return self._dp_hue.value, self._dp_saturation.value * _SATURATION_MULTIPLIER
        return None

    @bind_collector
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            hue, ksaturation = hs_color
            saturation = ksaturation / _SATURATION_MULTIPLIER
            await self._dp_hue.send_value(value=int(hue), collector=collector)
            await self._dp_saturation.send_value(value=saturation, collector=collector)
        if color_temp_kelvin := kwargs.get("color_temp_kelvin"):
            await self._dp_color_temperature_kelvin.send_value(value=color_temp_kelvin, collector=collector)
        if kwargs.get("on_time") is None and kwargs.get("ramp_time"):
            await self._set_on_time_value(on_time=_NOT_USED, collector=collector)
        if self.supports_effects and (effect := kwargs.get("effect")) is not None:
            await self._dp_effect.send_value(value=effect, collector=collector)

        await super().turn_on(collector=collector, **kwargs)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_color_temperature_kelvin: DpInteger = self._get_data_point(
            field=Field.COLOR_TEMPERATURE, data_point_type=DpInteger
        )
        self._dp_on_time_unit: DpAction = self._get_data_point(field=Field.ON_TIME_UNIT, data_point_type=DpAction)
        self._dp_effect: DpAction = self._get_data_point(field=Field.EFFECT, data_point_type=DpAction)
        self._dp_hue: DpInteger = self._get_data_point(field=Field.HUE, data_point_type=DpInteger)
        self._dp_ramp_time_to_off_unit: DpAction = self._get_data_point(
            field=Field.RAMP_TIME_TO_OFF_UNIT, data_point_type=DpAction
        )
        self._dp_ramp_time_to_off_value: DpAction = self._get_data_point(
            field=Field.RAMP_TIME_TO_OFF_VALUE, data_point_type=DpAction
        )
        self._dp_ramp_time_unit: DpAction = self._get_data_point(field=Field.RAMP_TIME_UNIT, data_point_type=DpAction)
        self._dp_saturation: DpFloat = self._get_data_point(field=Field.SATURATION, data_point_type=DpFloat)


class CustomDpIpFixedColorLight(TimerUnitMixin, CustomDpDimmer):
    """Class for HomematicIP HmIP-BSL light data point."""

    __slots__ = (
        "_dp_channel_color",
        "_dp_color",
        "_dp_effect",
        "_dp_on_time_unit",
        "_dp_ramp_time_unit",
        "_effect_list",
    )

    @property
    def channel_color_name(self) -> str | None:
        """Return the name of the channel color."""
        return self._dp_channel_color.value

    @property
    def channel_hs_color(self) -> tuple[float, float] | None:
        """Return the channel hue and saturation color value [float, float]."""
        if self._dp_channel_color.value is not None:
            return _FIXED_COLOR_SWITCHER.get(self._dp_channel_color.value, (_MIN_HUE, _MIN_SATURATION))
        return None

    @state_property
    def color_name(self) -> str | None:
        """Return the name of the color."""
        val = self._dp_color.value
        return val if isinstance(val, str) else None

    @state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        if (effect := self._dp_effect.value) is not None and effect in self._effect_list:
            return effect if isinstance(effect, str) else None
        return None

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._effect_list

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if (
            self._dp_color.value is not None
            and isinstance(self._dp_color.value, str)
            and (hs_color := _FIXED_COLOR_SWITCHER.get(self._dp_color.value)) is not None
        ):
            return hs_color
        return _MIN_HUE, _MIN_SATURATION

    @bind_collector
    async def turn_on(self, *, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            simple_rgb_color = _convert_color(color=hs_color)
            await self._dp_color.send_value(value=simple_rgb_color, collector=collector)
        elif self.color_name in _NO_COLOR:
            await self._dp_color.send_value(value=_FixedColor.WHITE, collector=collector)
        if (effect := kwargs.get("effect")) is not None and effect in self._effect_list:
            await self._dp_effect.send_value(value=effect, collector=collector)
        elif self._dp_effect.value not in self._effect_list:
            await self._dp_effect.send_value(value=_ColorBehaviour.ON, collector=collector)
        elif (color_behaviour := self._dp_effect.value) is not None:
            await self._dp_effect.send_value(value=color_behaviour, collector=collector)

        await super().turn_on(collector=collector, **kwargs)

    def _init_data_point_fields(self) -> None:
        """Initialize the data_point fields."""
        super()._init_data_point_fields()

        self._dp_color: DpSelect = self._get_data_point(field=Field.COLOR, data_point_type=DpSelect)
        self._dp_channel_color: DpSensor[str | None] = self._get_data_point(
            field=Field.CHANNEL_COLOR, data_point_type=DpSensor[str | None]
        )
        self._dp_on_time_unit: DpAction = self._get_data_point(field=Field.ON_TIME_UNIT, data_point_type=DpAction)
        self._dp_ramp_time_unit: DpAction = self._get_data_point(field=Field.RAMP_TIME_UNIT, data_point_type=DpAction)
        self._dp_effect: DpSelect = self._get_data_point(field=Field.COLOR_BEHAVIOUR, data_point_type=DpSelect)
        self._effect_list = (
            tuple(str(item) for item in self._dp_effect.values if item not in _EXCLUDE_FROM_COLOR_BEHAVIOUR)
            if (self._dp_effect and self._dp_effect.values)
            else ()
        )


def _convert_color(*, color: tuple[float, float]) -> str:
    """
    Convert the given color to the reduced color of the device.

    Device contains only 8 colors including white and black,
    so a conversion is required.
    """
    hue: int = int(color[0])
    if int(color[1]) < 5:
        return _FixedColor.WHITE
    if 30 < hue <= 90:
        return _FixedColor.YELLOW
    if 90 < hue <= 150:
        return _FixedColor.GREEN
    if 150 < hue <= 210:
        return _FixedColor.TURQUOISE
    if 210 < hue <= 270:
        return _FixedColor.BLUE
    if 270 < hue <= 330:
        return _FixedColor.PURPLE
    return _FixedColor.RED


# =============================================================================
# DeviceProfileRegistry Registration
# =============================================================================

# RF Dimmer (simple)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models=("263 132", "263 134", "HSS-DX"),
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
)

# RF Dimmer with virtual channels
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models=(
        "263 133",
        "HM-LC-AO-SM",
        "HM-LC-Dim1L-CV",
        "HM-LC-Dim1L-CV-2",
        "HM-LC-Dim1L-Pl",
        "HM-LC-Dim1L-Pl-3",
        "HM-LC-Dim1PWM-CV",
        "HM-LC-Dim1PWM-CV-2",
        "HM-LC-Dim1T-CV",
        "HM-LC-Dim1T-CV-2",
        "HM-LC-Dim1T-FM",
        "HM-LC-Dim1T-FM-2",
        "HM-LC-Dim1T-Pl",
        "HM-LC-Dim1T-Pl-3",
        "HM-LC-Dim1TPBU-FM",
        "HM-LC-Dim1TPBU-FM-2",
    ),
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER_WITH_VIRT_CHANNEL,
)

# RF Dimmer (specific channels)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HM-DW-WM",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
    channels=(1, 2, 3, 4),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HM-LC-Dim1T-DR",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
    channels=(1, 2, 3),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HM-LC-Dim1T-FM-LF",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models=("HM-LC-Dim1L-Pl-2", "HM-LC-Dim1T-Pl-2"),
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models=("HM-LC-Dim2L-CV", "HM-LC-Dim2L-SM", "HM-LC-Dim2T-SM"),
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
    channels=(1, 2),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models=("HM-LC-Dim2L-SM-2", "HM-LC-Dim2T-SM-2"),
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
    channels=(1, 2, 3, 4, 5, 6),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HMW-LC-Dim1L-DR",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
    channels=(3,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="OLIGO.smart.iq.HM",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
    channels=(1, 2, 3, 4, 5, 6),
)

# RF Dimmer with color temperature
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HM-LC-DW-WM",
    data_point_class=CustomDpColorTempDimmer,
    profile_type=DeviceProfile.RF_DIMMER_COLOR_TEMP,
    channels=(1, 3, 5),
)

# RF Dimmer with color and effect
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HM-LC-RGBW-WM",
    data_point_class=CustomDpColorDimmerEffect,
    profile_type=DeviceProfile.RF_DIMMER_COLOR,
)

# IP Dimmer
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIP-BDT",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.IP_DIMMER,
    channels=(4,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIP-DRDI3",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.IP_DIMMER,
    channels=(5, 9, 13),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIP-FDT",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.IP_DIMMER,
    channels=(2,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIP-PDT",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.IP_DIMMER,
    channels=(3,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIP-WGT",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.IP_DIMMER,
    channels=(2,),
)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIPW-DRD3",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.IP_DIMMER,
    channels=(2, 6, 10),
)

# IP Fixed Color Light
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIP-BSL",
    data_point_class=CustomDpIpFixedColorLight,
    profile_type=DeviceProfile.IP_FIXED_COLOR_LIGHT,
    channels=(8, 12),
)

# IP Simple Fixed Color Light (Wired)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIPW-WRC6",
    data_point_class=CustomDpIpFixedColorLight,
    profile_type=DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED,
    channels=(7, 8, 9, 10, 11, 12, 13),
)

# IP RGBW Light
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models=("HmIP-RGBW", "HmIP-LSC"),
    data_point_class=CustomDpIpRGBWLight,
    profile_type=DeviceProfile.IP_RGBW_LIGHT,
)

# IP DRG DALI Light
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIP-DRG-DALI",
    data_point_class=CustomDpIpDrgDaliLight,
    profile_type=DeviceProfile.IP_DRG_DALI,
    channels=tuple(range(1, 49)),
)

# HmIP-SCTH230 (Dimmer with additional sensors)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HmIP-SCTH230",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.IP_DIMMER,
    channels=(12,),
    extended=ExtendedDeviceConfig(
        additional_data_points={
            1: (Parameter.CONCENTRATION,),
            4: (Parameter.HUMIDITY, Parameter.ACTUAL_TEMPERATURE),
        }
    ),
)

# HBW-LC4-IN4-DR (Dimmer with additional inputs)
DeviceProfileRegistry.register(
    category=DataPointCategory.LIGHT,
    models="HBW-LC4-IN4-DR",
    data_point_class=CustomDpDimmer,
    profile_type=DeviceProfile.RF_DIMMER,
    channels=(5, 6, 7, 8),
    extended=ExtendedDeviceConfig(
        additional_data_points={
            1: (Parameter.PRESS_LONG, Parameter.PRESS_SHORT, Parameter.SENSOR),
            2: (Parameter.PRESS_LONG, Parameter.PRESS_SHORT, Parameter.SENSOR),
            3: (Parameter.PRESS_LONG, Parameter.PRESS_SHORT, Parameter.SENSOR),
            4: (Parameter.PRESS_LONG, Parameter.PRESS_SHORT, Parameter.SENSOR),
        }
    ),
)

# HBW-LC-RGBWW-IN6-DR (Complex device with multiple configs)
DeviceProfileRegistry.register_multiple(
    category=DataPointCategory.LIGHT,
    models="HBW-LC-RGBWW-IN6-DR",
    configs=(
        DeviceConfig(
            data_point_class=CustomDpDimmer,
            profile_type=DeviceProfile.RF_DIMMER,
            channels=(7, 8, 9, 10, 11, 12),
            extended=ExtendedDeviceConfig(
                additional_data_points={
                    (1, 2, 3, 4, 5, 6): (
                        Parameter.PRESS_LONG,
                        Parameter.PRESS_SHORT,
                        Parameter.SENSOR,
                    )
                },
            ),
        ),
        DeviceConfig(
            data_point_class=CustomDpColorDimmer,
            profile_type=DeviceProfile.RF_DIMMER_COLOR_FIXED,
            channels=(13,),
            extended=ExtendedDeviceConfig(fixed_channel_fields={15: {Field.COLOR: Parameter.COLOR}}),
        ),
        DeviceConfig(
            data_point_class=CustomDpColorDimmer,
            profile_type=DeviceProfile.RF_DIMMER_COLOR_FIXED,
            channels=(14,),
            extended=ExtendedDeviceConfig(fixed_channel_fields={16: {Field.COLOR: Parameter.COLOR}}),
        ),
    ),
)
