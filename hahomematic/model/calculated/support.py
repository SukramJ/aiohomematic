"""
A number of functions used to calculate values based on existing data.

Climate related formula are based on:
 - thermal comfort (https://github.com/dolezsa/thermal_comfort) ground works.
 - https://gist.github.com/E3V3A/8f9f0aa18380d4ab2546cd50b725a219
"""

from __future__ import annotations

import logging
import math
from typing import Final

from hahomematic.support import reduce_args

_LOGGER: Final = logging.getLogger(__name__)


def _calculate_heat_index(temperature: float, humidity: int) -> float:
    """
    Calculate the Heat Index (feels like temperature) based on the NOAA equation.

    References:
    [1] https://en.wikipedia.org/wiki/Heat_index
    [2] http://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
    [3] https://github.com/geanders/weathermetrics/blob/master/R/heat_index.R
    [4] https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3801457/

    """

    # SI units (Celsius)
    c1 = -8.78469475556
    c2 = 1.61139411
    c3 = 2.33854883889
    c4 = -0.14611605
    c5 = -0.012308094
    c6 = -0.0164248277778
    c7 = 0.002211732
    c8 = 0.00072546
    c9 = -0.000003582

    temperature_fahrenheit = (temperature * 9 / 5) + 32
    heat_index_fahrenheit = 0.5 * (
        temperature_fahrenheit + 61.0 + (temperature_fahrenheit - 68.0) * 1.2 + humidity * 0.094
    )

    if ((heat_index_fahrenheit + temperature_fahrenheit) / 2) >= 80:  # [°F]
        # temperature > 27C and humidity > 40 %
        heat_index_celsius = math.fsum(
            [
                c1,
                c2 * temperature,
                c3 * humidity,
                c4 * temperature * humidity,
                c5 * temperature**2,
                c6 * humidity**2,
                c7 * temperature**2 * humidity,
                c8 * temperature * humidity**2,
                c9 * temperature**2 * humidity**2,
            ]
        )
    else:
        heat_index_celsius = (heat_index_fahrenheit - 32) * 5 / 9

    return heat_index_celsius


def _calculate_wind_chill(temperature: float, wind_speed: float) -> float | None:
    """
    Calculate the Wind Chill (feels like temperature) based on NOAA.

    References:
    [1] https://en.wikipedia.org/wiki/Wind_chill
    [2] https://www.wpc.ncep.noaa.gov/html/windchill.shtml

    """
    # Wind Chill Temperature is only defined for temperatures at or below 10°C and wind speeds above 4.8 Km/h.
    if temperature > 10 or wind_speed <= 4.8:  # if temperature > 50 or wind_speed <= 3:    # (°F, Mph)
        return None

    return float(13.12 + (0.6215 * temperature) - 11.37 * wind_speed**0.16 + 0.3965 * temperature * wind_speed**0.16)


def calculate_vapor_concentration(temperature: float, humidity: int) -> float | None:
    """Calculate the vapor concentration."""
    try:
        abs_temperature = temperature + 273.15
        vapor_concentration = 6.112
        vapor_concentration *= math.exp((17.67 * temperature) / (243.5 + temperature))
        vapor_concentration *= humidity
        vapor_concentration *= 2.1674
        vapor_concentration /= abs_temperature

        return round(vapor_concentration, 2)
    except ValueError as ve:
        _LOGGER.debug(
            "Unable to calculate 'vapor concentration' with temperature: %s, humidity: %s (%s)",
            temperature,
            humidity,
            reduce_args(args=ve.args),
        )
    return None


def calculate_apparent_temperature(temperature: float, humidity: int, wind_speed: float) -> float | None:
    """Calculate the apparent temperature based on NOAA."""
    try:
        if temperature <= 10 and wind_speed > 4.8:
            # Wind Chill for low temp cases (and wind)
            apparent_temperature = _calculate_wind_chill(temperature=temperature, wind_speed=wind_speed)
        elif temperature >= 26.7:
            # Heat Index for High temp cases
            apparent_temperature = _calculate_heat_index(temperature=temperature, humidity=humidity)
        else:
            apparent_temperature = temperature

        return round(apparent_temperature, 1)  # type: ignore[arg-type]
    except ValueError as ve:
        if temperature == 0.0 and humidity == 0:
            return 0.0
        _LOGGER.debug(
            "Unable to calculate 'apparent temperature' with temperature: %s, humidity: %s (%s)",
            temperature,
            humidity,
            reduce_args(args=ve.args),
        )
    return None


def calculate_dew_point(temperature: float, humidity: int) -> float | None:
    """Calculate the dew point."""
    try:
        a0 = 373.15 / (273.15 + temperature)
        s = -7.90298 * (a0 - 1)
        s += 5.02808 * math.log(a0, 10)
        s += -1.3816e-7 * (pow(10, (11.344 * (1 - 1 / a0))) - 1)
        s += 8.1328e-3 * (pow(10, (-3.49149 * (a0 - 1))) - 1)
        s += math.log(1013.246, 10)
        vp = pow(10, s - 3) * humidity
        td = math.log(vp / 0.61078)

        return round((241.88 * td) / (17.558 - td), 1)
    except ValueError as ve:
        if temperature == 0.0 and humidity == 0:
            return 0.0
        _LOGGER.debug(
            "Unable to calculate 'dew point' with temperature: %s, humidity: %s (%s)",
            temperature,
            humidity,
            reduce_args(args=ve.args),
        )
    return None


def calculate_frost_point(temperature: float, humidity: int) -> float | None:
    """Calculate the frost point."""
    try:
        if (dewpoint := calculate_dew_point(temperature=temperature, humidity=humidity)) is None:
            return None
        t = temperature + 273.15
        td = dewpoint + 273.15

        return round((td + (2671.02 / ((2954.61 / t) + 2.193665 * math.log(t) - 13.3448)) - t) - 273.15, 1)
    except ValueError as ve:
        if temperature == 0.0 and humidity == 0:
            return 0.0
        _LOGGER.debug(
            "Unable to calculate 'frost point' with temperature: %s, humidity: %s (%s)",
            temperature,
            humidity,
            reduce_args(args=ve.args),
        )
    return None
