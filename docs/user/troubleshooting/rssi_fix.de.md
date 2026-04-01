---
translation_source: docs/user/troubleshooting/rssi_fix.md
translation_date: 2026-04-01
translation_source_hash: d0cc2effe568
---

# Über RSSI-Werte

Wenn Sie die generierten RSSI-Entities verwenden, könnten Sie feststellen, dass die Werte nicht immer mit denen übereinstimmen, die Sie in der CCU WebUI sehen.
Kurz gesagt liegt das daran, dass die in der WebUI angezeigten Werte (und die von der Homematic API zurückgegebenen) falsch sind.
Diese Integration wendet Strategien an, um die gemeldeten Werte so gut wie möglich zu korrigieren, damit Sie sie ohne Sorge um die technischen Details verwenden können.

Wenn Sie an einer weiteren Erklärung interessiert sind, lesen Sie weiter.

## Technische Details

Der RSSI-Wert ([Received Signal Strength Indicator](https://en.wikipedia.org/wiki/Received_signal_strength_indication)) gibt an, wie gut die Kommunikation zwischen zwei Funkgeräten ist (z.B. CCU und eines Ihrer Homematic-Geräte).
Er kann in verschiedenen Einheiten gemessen werden, Homematic verwendet dBm ([Dezibel-Milliwatt](https://en.wikipedia.org/wiki/DBm)).
Der gültige Bereich wird durch den verwendeten Chipsatz bestimmt.
Für Homematic liegt er bei -127 bis 0 dBm.
Je näher der Wert an 0 liegt, desto staerker ist das Signal.

Leider führen einige Implementierungsdetails in Homematic dazu, dass Werte außerhalb dieses Bereichs gemeldet werden.
Dies liegt wahrscheinlich an falschen Datentypen bei der Konvertierung und internen Konventionen. Es resultiert in folgenden gemeldeten Bereichen:

- 0, 1, -256, 256, 128, -128, 65536, -65536: Alle werden an verschiedenen Stellen verwendet, um "unbekannt" anzuzeigen
- 1 bis 127: Eine fehlende Invertierung des Werts, wird durch Multiplikation mit -1 korrigiert
- 129 bis 256: Ein falsch verwendeter Datentyp, wird durch Subtraktion von 256 korrigiert
- -129 bis -256: Ein falsch verwendeter Datentyp, wird durch Subtraktion von 256 vom invertierten Wert korrigiert

Dies sind die exakten Konvertierungen, die in Home Assistant angewandt werden:

| Bereich             | Konvertierter Wert | Grund                                    |
| ------------------- | ------------------ | ---------------------------------------- |
| <= -256             | None/unbekannt     | Ungültig                                 |
| > -256 und < -129   | (Wert \* -1) - 256 | Übersetzt zu > -127 und < 0              |
| >= -129 und <= -127 | None/unbekannt     | Ungültig                                 |
| > -127 und < 0      | Wert               | Der reale Bereich, wird direkt verwendet |
| >= 0 und <= 1       | None/unbekannt     | Übersetzt zu None/unbekannt              |
| > 1 und < 127       | Wert \* -1         | Übersetzt zu > -127 und < -1             |
| >= 127 und <= 129   | None/unbekannt     | Ungültig                                 |
| > 129 und < 256     | Wert - 256         | Übersetzt zu > -127 und < 0              |
| >= 256              | None/unbekannt     | Ungültig                                 |
