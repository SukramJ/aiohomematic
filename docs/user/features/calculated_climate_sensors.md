# Short description of calculated sensors

## Operating Voltage Level

requires: operating voltage, max voltage(battery voltage\*qty), min voltage (low bat limit default)

Calculated sensor to define the left over capacity within the usable voltage range.

## Climate sensors

### Apparent Temperature (Feels like)

requires: temperature, humidity, wind speed

Calculated sensor that displays a perceived temperature using temperature, humidity and wind speed.

### Dew Point

requires: temperature, humidity

The temperature, with constant pressure and water-vapour content, to which air must be cooled for saturation to occur.

### Dew Point Spread

requires: temperature, humidity

The difference between current air temperature and dew point. Specifies the safety margin against condensation(K).

• Spread < 2K → critical (condenser danger)
• Spread 2–4K → caution, high humidity
• Spread > 5 K → safe area

### Enthalphy

requires: temperature, humidity, air pressure (used default is 1013.25 hPa)

The specific enthalpy of humid air in kJ/kg (relative to dry air). Relevant
It is important when calculating, for example, heat recovery or ventilation efficiency.

### Frost Point

requires: temperature, humidity

The temperature to which a sample of air must be cooled, at constant pressure and humidity, to reach saturation with respect to ice.

### Vapor Concentration (Absolute Humidity)

requires: temperature, humidity

The vapor concentration or absolute humidity of a mixture of water vapor and dry air is defined as the ratio of the mass of water vapor Mw to the volume V occupied by the mixture.

Dv = Mw / V expressed in g/m3
