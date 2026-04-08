---
translation_source: docs/user/features/schedule_card.md
translation_date: 2026-04-01
translation_source_hash: 413105916eb9
---

# Schedule Card

Die **HomematicIP Local Schedule Card** ist eine benutzerdefinierte Lovelace-Karte zum Anzeigen und Bearbeiten von ereignisbasierten Zeitplänen für Homematic-Schalter, -Lichter, -Abdeckungen und -Ventile.

---

## Funktionen

- **Ereignisbasierte Zeitplanung**: Verwaltung einzelner Zeitplan-Ereignisse mit präziser Steuerung
- **Multi-Geräte-Unterstützung**: Funktioniert mit Schaltern, Lichtern, Abdeckungen und Ventilen
- **Flexible Zeitsteuerung**: Feste Uhrzeit oder astronomische Ereignisse (Sonnenauf-/untergang) mit Offset
- **8 Bedingungstypen**: Feste Zeit, Astro, Frühestens/Spätestens-Kombinationen
- **Kategoriespezifische UI**: Angepasste Steuerung pro Gerätetyp (Dimmen, Lamellenposition, Dauer usw.)
- **Visuelle Konfiguration**: Konfiguration über den UI-Editor - kein YAML erforderlich
- **Zweisprachig**: Englisch und Deutsch

---

## Unterstützte Gerätetypen

| Domain   | Beschreibung                                 | Spezialfelder              |
| -------- | -------------------------------------------- | -------------------------- |
| `switch` | Ein/Aus-Geräte                               | Level: nur 0.0 oder 1.0    |
| `light`  | Lichter mit Dimmunterstützung                | Level + Rampenzeit         |
| `cover`  | Jalousien/Rollläden mit Position und Lamelle | Level + level_2 (Lamellen) |
| `valve`  | Heizungsventile                              | Level + Dauer              |

---

## Installation

Die Karte ist automatisch verfügbar, sobald die HomematicIP Local Integration geladen ist — keine manuelle Installation erforderlich. Sie erscheint im Lovelace-Karten-Picker unter **HomematicIP Local Scheduler Card**.

!!! note "Migration von HACS"
    Falls diese Karte zuvor über HACS installiert wurde, erkennt die integrationsgebundene Version dies und überspringt die doppelte Registrierung. Die HACS-Kartenressource kann nach Belieben entfernt werden: **HACS** → **Frontend** → Schedule Card entfernen. Beide Versionen koexistieren während der Übergangsphase ohne Konflikte.

---

## Konfiguration

### Einfach

```yaml
type: custom:homematicip-local-schedule-card
entity: switch.gartenbeleuchtung
```

### Mehrere Entities

```yaml
type: custom:homematicip-local-schedule-card
entities:
  - switch.gartenbeleuchtung
  - light.flur_dimmer
  - cover.wohnzimmer_jalousie
```

Wenn mehrere Entities definiert sind, erscheint ein Dropdown zum Umschalten.

### Alle Optionen

| Option              | Typ      | Standard       | Beschreibung                        |
| ------------------- | -------- | -------------- | ----------------------------------- |
| `entity`            | string   | -              | Einzelne Entity ID                  |
| `entities`          | string[] | -              | Liste von Entity IDs                |
| `name`              | string   | Entity-Name    | Benutzerdefinierter Kartenkopf-Name |
| `editable`          | boolean  | `true`         | Bearbeitung aktivieren/deaktivieren |
| `hour_format`       | string   | `24`           | Zeitformat: `12` oder `24` Stunden  |
| `language`          | string   | Auto-Erkennung | Sprache erzwingen: `en` oder `de`   |
| `time_step_minutes` | number   | `15`           | Zeitauswahl-Schrittweite in Minuten |

---

## Verwendung

### Zeitplan-Ereignisse

Jedes Zeitplan-Ereignis definiert, wann und wie ein Gerät gesteuert werden soll. Ein Gerät unterstützt bis zu **24 Zeitplan-Ereignisse**.

Ein Ereignis besteht aus:

- **Wochentage**: An welchen Tagen das Ereignis aktiv ist
- **Uhrzeit**: Wann das Ereignis ausgelöst wird (fest oder astronomisch)
- **Zielkanäle**: Welche Gerätekanäle gesteuert werden
- **Level**: Ausgangslevel (0.0-1.0)
- **Dauer**: Wie lange der Ausgang aktiv bleibt (optional)
- **Rampenzeit**: Übergangszeit für Dimmer (optional, nur Lichter)

### Bedingungstypen

Ereignisse können verschiedene Zeitbedingungen verwenden:

| Bedingung               | Beschreibung                                                     |
| ----------------------- | ---------------------------------------------------------------- |
| `fixed_time`            | Auslösung zur angegebenen Uhrzeit                                |
| `astro`                 | Auslösung bei Sonnenauf- oder -untergang (mit optionalem Offset) |
| `fixed_if_before_astro` | Feste Zeit verwenden, wenn sie vor dem Astro-Ereignis liegt      |
| `astro_if_before_fixed` | Astro-Ereignis verwenden, wenn es vor der festen Zeit liegt      |
| `fixed_if_after_astro`  | Feste Zeit verwenden, wenn sie nach dem Astro-Ereignis liegt     |
| `astro_if_after_fixed`  | Astro-Ereignis verwenden, wenn es nach der festen Zeit liegt     |
| `earliest`              | Den früheren Zeitpunkt verwenden (feste Zeit oder Astro)         |
| `latest`                | Den späteren Zeitpunkt verwenden (feste Zeit oder Astro)         |

Astronomische Ereignisse unterstützen einen Offset von bis zu +/- 720 Minuten (12 Stunden) ab Sonnenauf- oder -untergang.

### Bearbeitung

1. **Ereignis hinzufügen** klicken, um ein neues Zeitplan-Ereignis zu erstellen
2. Die **Wochentage** für das Ereignis auswählen
3. Einen **Bedingungstyp** wählen und die Auslöse-Uhrzeit festlegen
4. **Zielkanäle** für das Gerät auswählen
5. Den **Level** und optionale Parameter (Dauer, Rampenzeit) festlegen
6. **Speichern** klicken, um den Zeitplan auf das Gerät zu schreiben

### Gerätetypspezifische Steuerung

Die Karte passt ihre UI je nach Gerätetyp an:

- **Schalter**: Einfacher Ein/Aus-Umschalter (Level 0.0 oder 1.0)
- **Licht**: Helligkeitsregler (0-100%) mit optionaler Rampenzeit für sanftes Dimmen
- **Abdeckung**: Positionsregler (0-100%) mit optionaler Lamellenposition (level_2)
- **Ventil**: Öffnungsregler (0-100%) mit optionaler Dauer

---

## Zeitplan-Datenformat

Das Zeitplan-Datenformat folgt dem gleichen Format wie die Aktion `homematicip_local.set_schedule`. Siehe [Wochenprofile - Nicht-Klima-Zeitplan-Aktionen](week_profile.md#non-climate-schedule-actions) für die vollständige Feldreferenz und Beispiele.

### Kurzbeispiel

```yaml
schedule_data:
  "1":
    weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
    time: "06:30"
    condition: fixed_time
    target_channels: ["1_1"]
    level: 0.8
    duration: 1min
  "2":
    weekdays: [SATURDAY, SUNDAY]
    time: "08:00"
    condition: astro
    astro_type: sunrise
    astro_offset_minutes: 30
    target_channels: ["1_1"]
    level: 0.5
    duration: 30min
```

---

## Berechtigungen

Standardmäßig können nur Administratoren Zeitpläne bearbeiten. Um Nicht-Admin-Haushaltsmitgliedern die Zeitplan-Bearbeitung zu erlauben, aktiviere dies in den Integrationsoptionen unter **Zeitplan-Bearbeitung**. Siehe [Zeitplan-Bearbeitung für Nicht-Admins](config_panel.md#non-admin-schedules) für Details.

---

## Fehlerbehebung

### Karte wird nicht angezeigt

1. Browser-Cache leeren (Strg+F5)
2. Sicherstellen, dass die HomematicIP Local Integration geladen und aktiv ist
3. Home Assistant-Protokolle auf Frontend-Registrierungsfehler prüfen

### Entity nicht aufgelistet

1. Überprüfen, ob die Entity Zeitplan-Unterstützung hat (prüfen Sie, ob eine Wochenprofil-Sensor-Entity am Gerät vorhanden ist)
2. Sicherstellen, dass die Entity-Domain unterstützt wird (switch, light, cover oder valve)

### Änderungen werden nicht gespeichert

1. Home Assistant-Protokolle auf WebSocket-Fehler prüfen
2. Sicherstellen, dass CCU und Gerät erreichbar sind
3. Warten, bis CONFIG_PENDING auf dem Gerät zurückgesetzt wird

---

## Siehe auch

- [Wochenprofile](week_profile.md) - Zeitplan-Datenformat, Aktionen und Beispiele
- [Climate Schedule Card](climate_schedule_card.md) - Zeitplan-Karte für Thermostate
- [Status-Karten](status_cards.md) - Systemstatus, Gerätestatus und Meldungen
- [Gerätekonfigurations-Panel](config_panel.md) - Vollständige Gerätekonfigurations-UI
