---
translation_source: docs/user/features/calculated_climate_sensors.md
translation_date: 2026-04-01
translation_source_hash: 5cb55feb4879
---

# Kurzbeschreibung der berechneten Sensoren

## Betriebsspannungsniveau

Voraussetzung: Betriebsspannung, maximale Spannung (Batteriespannung \* Anzahl), minimale Spannung (Standard-Low-Bat-Grenzwert)

Berechneter Sensor zur Bestimmung der verbleibenden Kapazität innerhalb des nutzbaren Spannungsbereichs.

## Klimasensoren

### Gefühlte Temperatur (Apparent Temperature)

Voraussetzung: Temperatur, Luftfeuchtigkeit, Windgeschwindigkeit

Berechneter Sensor, der eine gefühlte Temperatur unter Verwendung von Temperatur, Luftfeuchtigkeit und Windgeschwindigkeit anzeigt.

### Taupunkt

Voraussetzung: Temperatur, Luftfeuchtigkeit

Die Temperatur, auf die Luft bei konstantem Druck und Wasserdampfgehalt abgekühlt werden muss, damit Sättigung eintritt.

### Taupunktdifferenz (Spread)

Voraussetzung: Temperatur, Luftfeuchtigkeit

Die Differenz zwischen aktueller Lufttemperatur und Taupunkt. Gibt den Sicherheitsabstand gegen Kondensation an (K).

- Spread < 2K -> kritisch (Kondensationsgefahr)
- Spread 2-4K -> Vorsicht, hohe Luftfeuchtigkeit
- Spread > 5K -> sicherer Bereich

### Enthalpie

Voraussetzung: Temperatur, Luftfeuchtigkeit, Luftdruck (Standard ist 1013,25 hPa)

Die spezifische Enthalpie feuchter Luft in kJ/kg (bezogen auf trockene Luft). Relevant für die Berechnung von z.B. Wärmerückgewinnung oder Lüftungseffizienz.

### Frostpunkt

Voraussetzung: Temperatur, Luftfeuchtigkeit

Die Temperatur, auf die eine Luftprobe bei konstantem Druck und Feuchtigkeitsgehalt abgekühlt werden muss, um Sättigung in Bezug auf Eis zu erreichen.

### Dampfkonzentration (Absolute Luftfeuchtigkeit)

Voraussetzung: Temperatur, Luftfeuchtigkeit

Die Dampfkonzentration oder absolute Luftfeuchtigkeit eines Gemisches aus Wasserdampf und trockener Luft ist definiert als das Verhältnis der Masse des Wasserdampfes Mw zum Volumen V, das das Gemisch einnimmt.

Dv = Mw / V ausgedrückt in g/m3
