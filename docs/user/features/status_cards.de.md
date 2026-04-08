---
translation_source: docs/user/features/status_cards.md
translation_date: 2026-04-08
---

# Status-Karten

Die **HomematicIP Local Status-Karten** sind drei Lovelace-Karten zur Überwachung des Systemzustands, Gerätestatus und der Meldungen des Homematic-Systems direkt auf dem Home Assistant Dashboard.

---

## Installation

Die Karten sind automatisch verfügbar, sobald die HomematicIP Local Integration geladen ist — keine manuelle Installation erforderlich. Sie erscheinen im Lovelace-Karten-Picker.

---

## Kartenübersicht

| Karte                               | Element-Name                        | Zweck                                                |
| ----------------------------------- | ----------------------------------- | ---------------------------------------------------- |
| **Systemstatus**                    | `homematicip-system-health-card`    | Integrationszustand, Gerätestatistiken, DC/CS-Werte  |
| **Gerätestatus**                    | `homematicip-device-status-card`    | Geräte-Problemübersicht mit Filterung                |
| **Meldungen**                       | `homematicip-messages-card`         | Servicemeldungen und Alarme mit Quittierung           |

Alle Karten benötigen eine `entry_id`, die den HomematicIP Local Konfigurationseintrag identifiziert. Die Karten-Editoren bieten ein Dropdown zur Auswahl.

---

## Systemstatus-Karte {#system-health}

Zeigt den Gesamtzustand des Homematic-Systems auf einen Blick.

### Angezeigte Informationen

- **Zustandswert**: Prozentwert (0–100%), der den Integrationszustand anzeigt. 100% = alle Schnittstellen verbunden.
- **Gerätestatistiken**: Gesamtzahl der Geräte, nicht erreichbare Geräte (rot wenn > 0), Geräte mit Firmware-Update (orange wenn > 0).
- **Duty Cycle / Carrier Sense**: Pro Funkmodul, HAP oder LAN-Gateway. Diese Werte stammen von den Sensor-Entities `DUTY_CYCLE_LEVEL` und `CARRIER_SENSE_LEVEL`.
- **Vorfälle** (optional): Letzte Kommunikationsereignisse zwischen Integration und CCU.

### Duty Cycle und Carrier Sense

**Duty Cycle (DC)** gibt an, wie viel der verfügbaren Funk-Sendezeit verbraucht wurde. Regulatorische Grenzwerte beschränken jedes Gerät auf 1% Sendezeit pro Stunde.

| DC-Wert | Farbe  | Bedeutung                                       |
| ------- | ------ | ----------------------------------------------- |
| < 60%   | Normal | Ausreichend Sendekapazität vorhanden            |
| 60–79%  | Orange | Nähert sich dem Limit                           |
| ≥ 80%   | Rot    | Nahe der Kapazitätsgrenze — Funkverkehr senken  |

**Carrier Sense (CS)** misst, wie viel Funkaktivität auf dem Frequenzband erkannt wird — einschließlich Störungen durch andere Geräte (Nachbarn, WLAN usw.).

| CS-Wert | Farbe  | Bedeutung                                              |
| ------- | ------ | ------------------------------------------------------ |
| < 10%   | Normal | Saubere Funkumgebung                                   |
| ≥ 10%   | Rot    | Erhebliche Störungen — kann Zuverlässigkeit beeinträchtigen |

!!! tip
    Hohe Carrier-Sense-Werte weisen auf externe Funkstörungen hin. Das Funkmodul oder den HAP von Störquellen entfernen (WLAN-Router, USB-3.0-Geräte, Mikrowellen).

### Konfiguration

```yaml
type: custom:homematicip-system-health-card
entry_id: <config-entry-id>
```

| Option           | Typ     | Standard        | Beschreibung                            |
| ---------------- | ------- | --------------- | --------------------------------------- |
| `entry_id`       | string  | — (erforderlich) | HomematicIP Local Konfigurationseintrags-ID |
| `title`          | string  | "Systemstatus"  | Benutzerdefinierter Kartentitel         |
| `show_incidents` | boolean | `false`         | Vorfallsliste anzeigen                  |
| `max_incidents`  | number  | `5`             | Maximale Anzahl angezeigter Vorfälle    |
| `poll_interval`  | number  | `30`            | Abfrageintervall in Sekunden            |

Das Abfrageintervall ist adaptiv: 5 Sekunden wenn das System nicht stabil ist, das konfigurierte Intervall (mindestens 30s) im Normalbetrieb.

---

## Gerätestatus-Karte {#device-status}

Zeigt, welche Geräte Probleme haben — nicht erreichbar, Batterie schwach oder Konfiguration ausstehend.

### Angezeigte Informationen

- **Problem-Badge**: Rotes Badge mit Anzahl der Geräte mit Problemen (oder grünes "OK" wenn keine).
- **Geräteliste**: Jedes Problemgerät mit Symbol, Name, Modell und Problembeschreibung.
- **Zusammenfassung**: Anzahl der verbleibenden OK-Geräte (bei Problemfilterung).

### Filtermodi

| Filter           | Zeigt                                                            |
| ---------------- | ---------------------------------------------------------------- |
| `problems`       | Nur Geräte mit Problemen (Standard)                              |
| `all`            | Alle Geräte — Probleme zuerst, dann gesunde Geräte mit ✓        |
| `unreachable`    | Nur nicht erreichbare Geräte                                     |
| `low_battery`    | Nur Geräte mit schwacher Batterie                                |
| `config_pending` | Nur Geräte mit ausstehender Konfiguration                       |

### Konfiguration

```yaml
type: custom:homematicip-device-status-card
entry_id: <config-entry-id>
filter: problems
max_devices: 10
```

| Option             | Typ     | Standard       | Beschreibung                                   |
| ------------------ | ------- | -------------- | ---------------------------------------------- |
| `entry_id`         | string  | — (erforderlich) | HomematicIP Local Konfigurationseintrags-ID  |
| `title`            | string  | Automatisch    | Benutzerdefinierter Kartentitel                |
| `filter`           | string  | `"problems"`   | Filtermodus (siehe Tabelle oben)               |
| `show_model`       | boolean | `true`         | Gerätemodell im Sekundärtext anzeigen          |
| `max_devices`      | number  | `10`           | Maximale angezeigte Geräte (0 = unbegrenzt)    |
| `poll_interval`    | number  | `60`           | Abfrageintervall in Sekunden                   |
| `interface_filter` | string  | —              | Nur Geräte dieser Schnittstelle anzeigen       |

---

## Meldungen-Karte {#messages}

Zeigt Servicemeldungen und Alarmmeldungen der CCU mit Quittierungsmöglichkeit.

### Angezeigte Informationen

- **Alarmmeldungen** (rot): Kritische Benachrichtigungen wie Sabotageerkennung oder Sensorfehler. Zeigt Gerätename, Beschreibung, Zähler und Zeitstempel.
- **Servicemeldungen** (orange): Systembenachrichtigungen wie nicht erreichbare Geräte, schwache Batterie oder ausstehende Konfiguration. Zeigt Meldungscode und Zähler.
- **Badges**: Alarmanzahl (rot), Servicemeldungsanzahl (orange) oder "OK" (grün) wenn leer.

### Meldungen quittieren

- **Alarmmeldungen**: Haben immer einen Quittieren-Button.
- **Servicemeldungen**: Zeigen nur einen Quittieren-Button wenn die Meldung quittierbar ist (die CCU bestimmt dies).

Nach dem Quittieren wird die Meldung sofort aus der Liste entfernt. Der nächste Abfragezyklus bestätigt die Änderung.

### Konfiguration

```yaml
type: custom:homematicip-messages-card
entry_id: <config-entry-id>
```

| Option           | Typ     | Standard       | Beschreibung                               |
| ---------------- | ------- | -------------- | ------------------------------------------ |
| `entry_id`       | string  | — (erforderlich) | HomematicIP Local Konfigurationseintrags-ID |
| `title`          | string  | Automatisch    | Benutzerdefinierter Kartentitel            |
| `show_alarms`    | boolean | `true`         | Alarmmeldungen-Bereich anzeigen            |
| `show_service`   | boolean | `true`         | Servicemeldungen-Bereich anzeigen          |
| `max_messages`   | number  | `10`           | Maximale Meldungen pro Typ                 |
| `show_timestamp` | boolean | `true`         | Zeitstempel der Meldungen anzeigen         |
| `poll_interval`  | number  | `30`           | Abfrageintervall in Sekunden               |

---

## Dashboard-Beispiel

Ein typisches Monitoring-Setup verwendet alle drei Karten:

```yaml
# Systemzustand
type: custom:homematicip-system-health-card
entry_id: <entry-id>

# Problemgeräte
type: custom:homematicip-device-status-card
entry_id: <entry-id>
filter: problems
max_devices: 5

# Aktive Meldungen
type: custom:homematicip-messages-card
entry_id: <entry-id>
```

---

## Fehlerbehebung

### Karten werden nicht angezeigt

1. Browser-Cache leeren (Strg+F5)
2. Sicherstellen, dass die HomematicIP Local Integration geladen und aktiv ist
3. Home Assistant-Protokolle auf Frontend-Registrierungsfehler prüfen

### Keine Daten angezeigt

1. Überprüfen, ob die `entry_id` korrekt ist (Editor-Dropdown zur Auswahl verwenden)
2. Sicherstellen, dass die Integration vollständig gestartet ist (Central-Status sollte "RUNNING" sein)
3. Home Assistant-Protokolle auf WebSocket-Fehler prüfen

### Duty Cycle / Carrier Sense wird nicht angezeigt

1. Sicherstellen, dass das Funkmodul, der HAP oder das LAN-Gateway die Sensor-Entities `DUTY_CYCLE_LEVEL` und `CARRIER_SENSE_LEVEL` bereitstellt
2. Prüfen, ob diese Entities in Home Assistant aktiviert sind (diagnostische Entities, standardmäßig aktiviert)
3. Überprüfen, ob die Entities zum gleichen Konfigurationseintrag gehören, der in der Karte ausgewählt ist

---

## Siehe auch

- [Konfigurationspanel für Geräte](config_panel.md) — Vollständige Gerätekonfigurations-UI mit detailliertem Dashboard
- [Klima-Zeitprogramm-Karte](climate_schedule_card.md) — Thermostat-Zeitprogramm-Editor
- [Zeitprogramm-Karte](schedule_card.md) — Geräte-Zeitprogramm-Editor
