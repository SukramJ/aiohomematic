"""Module for data points implemented using the light category."""

from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum, StrEnum
import math
from typing import Any, Final, TypedDict, Unpack

from hahomematic.const import DataPointCategory, DataPointUsage, Parameter
from hahomematic.model import device as hmd
from hahomematic.model.custom import definition as hmed
from hahomematic.model.custom.const import DeviceProfile, Field
from hahomematic.model.custom.data_point import CustomDataPoint
from hahomematic.model.custom.support import CustomConfig, ExtendedConfig
from hahomematic.model.data_point import CallParameterCollector, bind_collector
from hahomematic.model.decorators import state_property
from hahomematic.model.generic import DpAction, DpFloat, DpInteger, DpSelect, DpSensor, GenericDataPoint
from hahomematic.model.support import TimerMixin

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
_OLD_LEVEL: Final = 1.005
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


class _TimeUnit(IntEnum):
    """Enum with time units."""

    SECONDS = 0
    MINUTES = 1
    HOURS = 2


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


class CustomDpDimmer(CustomDataPoint, TimerMixin):
    """Base class for HomeMatic light data point."""

    _category = DataPointCategory.LIGHT

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        TimerMixin.__init__(self)
        super()._init_data_point_fields()
        self._dp_level: DpFloat = self._get_data_point(field=Field.LEVEL, data_point_type=DpFloat)
        self._dp_channel_level: DpSensor[float | None] = self._get_data_point(
            field=Field.CHANNEL_LEVEL, data_point_type=DpSensor[float | None]
        )
        self._dp_on_time_value: DpAction = self._get_data_point(field=Field.ON_TIME_VALUE, data_point_type=DpAction)
        self._dp_ramp_time_value: DpAction = self._get_data_point(field=Field.RAMP_TIME_VALUE, data_point_type=DpAction)

    @state_property
    def is_on(self) -> bool | None:
        """Return true if dimmer is on."""
        return self._dp_level.value is not None and self._dp_level.value > _DIMMER_OFF

    @state_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between min/max brightness."""
        return int((self._dp_level.value or _MIN_BRIGHTNESS) * _MAX_BRIGHTNESS)

    @property
    def brightness_pct(self) -> int | None:
        """Return the brightness in percent of this light."""
        return int((self._dp_level.value or _MIN_BRIGHTNESS) * _LEVEL_TO_BRIGHTNESS_MULTIPLIER)

    @property
    def channel_brightness(self) -> int | None:
        """Return the channel_brightness of this light between min/max brightness."""
        if self._dp_channel_level.value is not None:
            return int(self._dp_channel_level.value * _MAX_BRIGHTNESS)
        return None

    @property
    def channel_brightness_pct(self) -> int | None:
        """Return the channel_brightness in percent of this light."""
        if self._dp_channel_level.value is not None:
            return int(self._dp_channel_level.value * _LEVEL_TO_BRIGHTNESS_MULTIPLIER)
        return None

    @state_property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        return None

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
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
    def effect(self) -> str | None:
        """Return the current effect."""
        return None

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return None

    @bind_collector()
    async def turn_on(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
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
        level = brightness / _MAX_BRIGHTNESS
        await self._dp_level.send_value(value=level, collector=collector)

    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOffArgs]) -> None:
        """Turn the light off."""
        self.reset_timer_on_time()
        if not self.is_state_change(off=True, **kwargs):
            return
        if ramp_time := kwargs.get("ramp_time"):
            await self._set_ramp_time_off_value(ramp_time=ramp_time, collector=collector)
        await self._dp_level.send_value(value=_DIMMER_OFF, collector=collector)

    @bind_collector()
    async def _set_on_time_value(self, on_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the on time value in seconds."""
        await self._dp_on_time_value.send_value(value=on_time, collector=collector, do_validate=False)

    async def _set_ramp_time_on_value(self, ramp_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the ramp time value in seconds."""
        await self._dp_ramp_time_value.send_value(value=ramp_time, collector=collector)

    async def _set_ramp_time_off_value(self, ramp_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the ramp time value in seconds."""
        await self._set_ramp_time_on_value(ramp_time=ramp_time, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (on_time_running := self.timer_on_time_running) is not None and on_time_running is True:
            return True
        if self.timer_on_time is not None:
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


class CustomDpColorDimmer(CustomDpDimmer):
    """Class for HomeMatic dimmer with color data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_color: DpInteger = self._get_data_point(field=Field.COLOR, data_point_type=DpInteger)

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

    @bind_collector()
    async def turn_on(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
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


class CustomDpColorDimmerEffect(CustomDpColorDimmer):
    """Class for HomeMatic dimmer with color data point."""

    _effects: tuple[str, ...] = (
        _EFFECT_OFF,
        "Slow color change",
        "Medium color change",
        "Fast color change",
        "Campfire",
        "Waterfall",
        "TV simulation",
    )

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_effect: DpInteger = self._get_data_point(field=Field.PROGRAM, data_point_type=DpInteger)

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

    @bind_collector()
    async def turn_on(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
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


class CustomDpColorTempDimmer(CustomDpDimmer):
    """Class for HomeMatic dimmer with color temperature."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
        super()._init_data_point_fields()
        self._dp_color_level: DpFloat = self._get_data_point(field=Field.COLOR_LEVEL, data_point_type=DpFloat)

    @state_property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        return math.floor(
            _MAX_KELVIN / int(_MAX_MIREDS - (_MAX_MIREDS - _MIN_MIREDS) * (self._dp_color_level.value or _DIMMER_OFF))
        )

    @bind_collector()
    async def turn_on(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (color_temp_kelvin := kwargs.get("color_temp_kelvin")) is not None:
            color_level = (_MAX_MIREDS - math.floor(_MAX_KELVIN / color_temp_kelvin)) / (_MAX_MIREDS - _MIN_MIREDS)
            await self._dp_color_level.send_value(value=color_level, collector=collector)

        await super().turn_on(collector=collector, **kwargs)


class CustomDpIpRGBWLight(CustomDpDimmer):
    """Class for HomematicIP HmIP-RGBW light data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
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

    @state_property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        if not self._dp_color_temperature_kelvin.value:
            return None
        return self._dp_color_temperature_kelvin.value

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._dp_hue.value is not None and self._dp_saturation.value is not None:
            return self._dp_hue.value, self._dp_saturation.value * _SATURATION_MULTIPLIER
        return None

    @property
    def _relevant_data_points(self) -> tuple[GenericDataPoint, ...]:
        """Returns the list of relevant data points. To be overridden by subclasses."""
        if self._dp_device_operation_mode.value == _DeviceOperationMode.RGBW:
            return (
                self._dp_hue,
                self._dp_level,
                self._dp_saturation,
                self._dp_color_temperature_kelvin,
            )
        if self._dp_device_operation_mode.value == _DeviceOperationMode.RGB:
            return self._dp_hue, self._dp_level, self._dp_saturation
        if self._dp_device_operation_mode.value == _DeviceOperationMode.TUNABLE_WHITE:
            return self._dp_level, self._dp_color_temperature_kelvin
        return (self._dp_level,)

    @property
    def supports_color_temperature(self) -> bool:
        """Flag if light supports color temperature."""
        return self._dp_device_operation_mode.value == _DeviceOperationMode.TUNABLE_WHITE

    @property
    def supports_effects(self) -> bool:
        """Flag if light supports effects."""
        return (
            self._dp_device_operation_mode.value != _DeviceOperationMode.PWM
            and self.effects is not None
            and len(self.effects) > 0
        )

    @property
    def supports_hs_color(self) -> bool:
        """Flag if light supports color."""
        return self._dp_device_operation_mode.value in (
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
            self._dp_device_operation_mode.value in (_DeviceOperationMode.RGB, _DeviceOperationMode.RGBW)
            and self._channel.no in (2, 3, 4)
        ) or (
            self._dp_device_operation_mode.value == _DeviceOperationMode.TUNABLE_WHITE and self._channel.no in (3, 4)
        ):
            return DataPointUsage.NO_CREATE
        return self._get_data_point_usage()

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._dp_effect.values or ()

    @bind_collector()
    async def turn_on(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
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

    @bind_collector()
    async def turn_off(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOffArgs]) -> None:
        """Turn the light off."""
        if kwargs.get("on_time") is None and kwargs.get("ramp_time"):
            await self._set_on_time_value(on_time=_NOT_USED, collector=collector)
        await super().turn_off(collector=collector, **kwargs)

    @bind_collector()
    async def _set_on_time_value(self, on_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the on time value in seconds."""
        on_time, on_time_unit = _recalc_unit_timer(time=on_time)
        if on_time_unit is not None:
            await self._dp_on_time_unit.send_value(value=on_time_unit, collector=collector)
        await self._dp_on_time_value.send_value(value=float(on_time), collector=collector)

    async def _set_ramp_time_on_value(self, ramp_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit is not None:
            await self._dp_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._dp_ramp_time_value.send_value(value=float(ramp_time), collector=collector)

    async def _set_ramp_time_off_value(self, ramp_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit is not None:
            await self._dp_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._dp_ramp_time_value.send_value(value=float(ramp_time), collector=collector)


class CustomDpIpDrgDaliLight(CustomDpDimmer):
    """Class for HomematicIP HmIP-DRG-DALI light data point."""

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
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

    @state_property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        if not self._dp_color_temperature_kelvin.value:
            return None
        return self._dp_color_temperature_kelvin.value

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._dp_hue.value is not None and self._dp_saturation.value is not None:
            return self._dp_hue.value, self._dp_saturation.value * _SATURATION_MULTIPLIER
        return None

    @property
    def _relevant_data_points(self) -> tuple[GenericDataPoint, ...]:
        """Returns the list of relevant data points. To be overridden by subclasses."""
        return (self._dp_level,)

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._dp_effect.values or ()

    @bind_collector()
    async def turn_on(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
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

    @bind_collector()
    async def _set_on_time_value(self, on_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the on time value in seconds."""
        on_time, on_time_unit = _recalc_unit_timer(time=on_time)
        if on_time_unit:
            await self._dp_on_time_unit.send_value(value=on_time_unit, collector=collector)
        await self._dp_on_time_value.send_value(value=float(on_time), collector=collector)

    async def _set_ramp_time_on_value(self, ramp_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit:
            await self._dp_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._dp_ramp_time_value.send_value(value=float(ramp_time), collector=collector)

    async def _set_ramp_time_off_value(self, ramp_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit:
            await self._dp_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._dp_ramp_time_value.send_value(value=float(ramp_time), collector=collector)


class CustomDpIpFixedColorLight(CustomDpDimmer):
    """Class for HomematicIP HmIP-BSL light data point."""

    @state_property
    def color_name(self) -> str | None:
        """Return the name of the color."""
        return self._dp_color.value

    @property
    def channel_color_name(self) -> str | None:
        """Return the name of the channel color."""
        return self._dp_channel_color.value

    def _init_data_point_fields(self) -> None:
        """Init the data_point fields."""
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

    @state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        if (effect := self._dp_effect.value) is not None and effect in self._effect_list:
            return effect
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
            and (hs_color := _FIXED_COLOR_SWITCHER.get(self._dp_color.value)) is not None
        ):
            return hs_color
        return _MIN_HUE, _MIN_SATURATION

    @property
    def channel_hs_color(self) -> tuple[float, float] | None:
        """Return the channel hue and saturation color value [float, float]."""
        if self._dp_channel_color.value is not None:
            return _FIXED_COLOR_SWITCHER.get(self._dp_channel_color.value, (_MIN_HUE, _MIN_SATURATION))
        return None

    @bind_collector()
    async def turn_on(self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            simple_rgb_color = _convert_color(hs_color)
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

    @bind_collector()
    async def _set_on_time_value(self, on_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the on time value in seconds."""
        on_time, on_time_unit = _recalc_unit_timer(time=on_time)
        if on_time_unit:
            await self._dp_on_time_unit.send_value(value=on_time_unit, collector=collector)
        await self._dp_on_time_value.send_value(value=float(on_time), collector=collector)

    async def _set_ramp_time_on_value(self, ramp_time: float, collector: CallParameterCollector | None = None) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit:
            await self._dp_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._dp_ramp_time_value.send_value(value=float(ramp_time), collector=collector)


def _recalc_unit_timer(time: float) -> tuple[float, int | None]:
    """Recalculate unit and value of timer."""
    ramp_time_unit = _TimeUnit.SECONDS
    if time == _NOT_USED:
        return time, None
    if time > 16343:
        time /= 60
        ramp_time_unit = _TimeUnit.MINUTES
    if time > 16343:
        time /= 60
        ramp_time_unit = _TimeUnit.HOURS
    return time, ramp_time_unit


def _convert_color(color: tuple[float, float]) -> str:
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


def make_ip_dimmer(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP dimmer data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpDimmer,
        device_profile=DeviceProfile.IP_DIMMER,
        custom_config=custom_config,
    )


def make_rf_dimmer(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpDimmer,
        device_profile=DeviceProfile.RF_DIMMER,
        custom_config=custom_config,
    )


def make_rf_dimmer_color(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer with color data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpColorDimmer,
        device_profile=DeviceProfile.RF_DIMMER_COLOR,
        custom_config=custom_config,
    )


def make_rf_dimmer_color_fixed(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer with fixed color data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpColorDimmer,
        device_profile=DeviceProfile.RF_DIMMER_COLOR_FIXED,
        custom_config=custom_config,
    )


def make_rf_dimmer_color_effect(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer and effect with color data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpColorDimmerEffect,
        device_profile=DeviceProfile.RF_DIMMER_COLOR,
        custom_config=custom_config,
    )


def make_rf_dimmer_color_temp(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer with color temperature data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpColorTempDimmer,
        device_profile=DeviceProfile.RF_DIMMER_COLOR_TEMP,
        custom_config=custom_config,
    )


def make_rf_dimmer_with_virt_channel(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer data point."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpDimmer,
        device_profile=DeviceProfile.RF_DIMMER_WITH_VIRT_CHANNEL,
        custom_config=custom_config,
    )


def make_ip_fixed_color_light(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create fixed color light data points like HmIP-BSL."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpFixedColorLight,
        device_profile=DeviceProfile.IP_FIXED_COLOR_LIGHT,
        custom_config=custom_config,
    )


def make_ip_simple_fixed_color_light_wired(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create simple fixed color light data points like HmIPW-WRC6."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpFixedColorLight,
        device_profile=DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED,
        custom_config=custom_config,
    )


def make_ip_rgbw_light(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create simple fixed color light data points like HmIP-RGBW."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpRGBWLight,
        device_profile=DeviceProfile.IP_RGBW_LIGHT,
        custom_config=custom_config,
    )


def make_ip_drg_dali_light(
    channel: hmd.Channel,
    custom_config: CustomConfig,
) -> None:
    """Create color light data points like HmIP-DRG-DALI."""
    hmed.make_custom_data_point(
        channel=channel,
        data_point_class=CustomDpIpDrgDaliLight,
        device_profile=DeviceProfile.IP_DRG_DALI,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "263 132": CustomConfig(make_ce_func=make_rf_dimmer),
    "263 133": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "263 134": CustomConfig(make_ce_func=make_rf_dimmer),
    "HBW-LC4-IN4-DR": CustomConfig(
        make_ce_func=make_rf_dimmer,
        channels=(
            5,
            6,
            7,
            8,
        ),
        extended=ExtendedConfig(
            additional_data_points={
                1: (
                    Parameter.PRESS_LONG,
                    Parameter.PRESS_SHORT,
                    Parameter.SENSOR,
                ),
                2: (
                    Parameter.PRESS_LONG,
                    Parameter.PRESS_SHORT,
                    Parameter.SENSOR,
                ),
                3: (
                    Parameter.PRESS_LONG,
                    Parameter.PRESS_SHORT,
                    Parameter.SENSOR,
                ),
                4: (
                    Parameter.PRESS_LONG,
                    Parameter.PRESS_SHORT,
                    Parameter.SENSOR,
                ),
            }
        ),
    ),
    "HBW-LC-RGBWW-IN6-DR": (
        CustomConfig(
            make_ce_func=make_rf_dimmer,
            channels=(7, 8, 9, 10, 11, 12),
            extended=ExtendedConfig(
                additional_data_points={
                    (
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                    ): (
                        Parameter.PRESS_LONG,
                        Parameter.PRESS_SHORT,
                        Parameter.SENSOR,
                    )
                },
            ),
        ),
        CustomConfig(
            make_ce_func=make_rf_dimmer_color_fixed,
            channels=(13,),
            extended=ExtendedConfig(fixed_channels={15: {Field.COLOR: Parameter.COLOR}}),
        ),
        CustomConfig(
            make_ce_func=make_rf_dimmer_color_fixed,
            channels=(14,),
            extended=ExtendedConfig(fixed_channels={16: {Field.COLOR: Parameter.COLOR}}),
        ),
    ),
    "HM-DW-WM": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3, 4)),
    "HM-LC-AO-SM": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-DW-WM": CustomConfig(make_ce_func=make_rf_dimmer_color_temp, channels=(1, 3, 5)),
    "HM-LC-Dim1L-CV": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1L-CV-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1L-Pl": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1L-Pl-2": CustomConfig(make_ce_func=make_rf_dimmer),
    "HM-LC-Dim1L-Pl-3": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1PWM-CV": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1PWM-CV-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-CV": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-CV-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-DR": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3)),
    "HM-LC-Dim1T-FM": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-FM-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-FM-LF": CustomConfig(make_ce_func=make_rf_dimmer),
    "HM-LC-Dim1T-Pl": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-Pl-2": CustomConfig(make_ce_func=make_rf_dimmer),
    "HM-LC-Dim1T-Pl-3": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1TPBU-FM": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1TPBU-FM-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim2L-CV": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2)),
    "HM-LC-Dim2L-SM": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2)),
    "HM-LC-Dim2L-SM-2": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3, 4, 5, 6)),
    "HM-LC-Dim2T-SM": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2)),
    "HM-LC-Dim2T-SM-2": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3, 4, 5, 6)),
    "HM-LC-RGBW-WM": CustomConfig(make_ce_func=make_rf_dimmer_color_effect),
    "HMW-LC-Dim1L-DR": CustomConfig(make_ce_func=make_rf_dimmer, channels=(3,)),
    "HSS-DX": CustomConfig(make_ce_func=make_rf_dimmer),
    "HmIP-DRG-DALI": CustomConfig(make_ce_func=make_ip_drg_dali_light, channels=tuple(range(1, 49))),
    "HmIP-BDT": CustomConfig(make_ce_func=make_ip_dimmer, channels=(4,)),
    "HmIP-BSL": CustomConfig(make_ce_func=make_ip_fixed_color_light, channels=(8, 12)),
    "HmIP-DRDI3": CustomConfig(
        make_ce_func=make_ip_dimmer,
        channels=(5, 9, 13),
    ),
    "HmIP-FDT": CustomConfig(make_ce_func=make_ip_dimmer, channels=(2,)),
    "HmIP-PDT": CustomConfig(make_ce_func=make_ip_dimmer, channels=(3,)),
    "HmIP-RGBW": CustomConfig(make_ce_func=make_ip_rgbw_light),
    "HmIP-SCTH230": CustomConfig(
        make_ce_func=make_ip_dimmer,
        channels=(12,),
        extended=ExtendedConfig(
            additional_data_points={
                1: (Parameter.CONCENTRATION,),
                4: (
                    Parameter.HUMIDITY,
                    Parameter.ACTUAL_TEMPERATURE,
                ),
            }
        ),
    ),
    "HmIPW-DRD3": CustomConfig(
        make_ce_func=make_ip_dimmer,
        channels=(2, 6, 10),
    ),
    "HmIPW-WRC6": CustomConfig(make_ce_func=make_ip_simple_fixed_color_light_wired, channels=(7, 8, 9, 10, 11, 12, 13)),
    "OLIGO.smart.iq.HM": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3, 4, 5, 6)),
}
hmed.ALL_DEVICES[DataPointCategory.LIGHT] = DEVICES
