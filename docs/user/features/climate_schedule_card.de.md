---
translation_source: docs/user/features/climate_schedule_card.md
translation_date: 2026-04-01
translation_source_hash: 5cf78b313f3d
---

# Climate Schedule Card

Die **HomematicIP Local Climate Schedule Card** ist eine benutzerdefinierte Lovelace-Karte zum Anzeigen und Bearbeiten von Thermostat-Zeitplänen direkt im Home Assistant Dashboard.

---

## Funktionen

- **Visueller Wochenplan**: Die gesamte Woche auf einen Blick mit farbcodierten Temperaturblöcken
- **Interaktive Bearbeitung**: Klick auf einen Tag öffnet den Editor mit Zeit- und Temperatursteuerung
- **Profilwechsel**: Umschalten zwischen Zeitplanprofilen (P1-P6) über Dropdown
- **Aktives Profil anzeigen**: Das aktuell aktive Profil auf dem Gerät wird mit einem Sternchen (\*) markiert
- **Multi-Entity-Unterstützung**: Umschalten zwischen mehreren Thermostaten in einer einzigen Karte
- **Benutzerdefinierte Profilnamen**: Aussagekräftige Namen für Profile vergeben (z.B. "Komfort", "Eco", "Abwesend")
- **Responsives Design**: Funktioniert auf Desktop und Mobilgeräten
- **Visuelle Konfiguration**: Konfiguration über den UI-Editor - kein YAML erforderlich
- **Zweisprachig**: Englisch und Deutsch

---

## Installation

Die Karte ist automatisch verfügbar, sobald die HomematicIP Local Integration geladen ist — keine manuelle Installation erforderlich. Sie erscheint im Lovelace-Karten-Picker unter **HomematicIP Local Climate Schedule Card**.

!!! note "Migration von HACS"
Falls diese Karte zuvor über HACS installiert wurde, erkennt die integrationsgebundene Version dies und überspringt die doppelte Registrierung. Die HACS-Kartenressource kann nach Belieben entfernt werden: **HACS** → **Frontend** → Climate Schedule Card entfernen. Beide Versionen koexistieren während der Übergangsphase ohne Konflikte.

---

## Geräteunterstützung

Diese Karte funktioniert mit allen Homematic-Geräten, die Wochenprofil-Unterstützung und mehrere Profile haben:

- HomematicIP Thermostate (z.B. HmIP-eTRV, HmIP-eTRV-2, HmIP-BWTH, HmIP-WTH)
- Homematic Thermostate über Thermostatgruppen (HM-CC-RT-DN nur über Gruppe)

---

## Konfiguration

### Einfach

```yaml
type: custom:homematicip-local-climate-schedule-card
entity: climate.wohnzimmer_thermostat
```

### Mehrere Entities

```yaml
type: custom:homematicip-local-climate-schedule-card
entities:
  - climate.wohnzimmer
  - climate.schlafzimmer
  - climate.buero
```

Wenn mehrere Entities definiert sind, erscheint ein Dropdown im Kartenkopf zum Umschalten.

### Benutzerdefinierte Namen und Profilnamen

```yaml
type: custom:homematicip-local-climate-schedule-card
entities:
  - entity: climate.wohnzimmer
    name: "Wohnzimmer"
    profile_names:
      P1: "Komfort"
      P2: "Eco"
      P3: "Nacht"
  - entity: climate.schlafzimmer
    name: "Schlafzimmer"
    profile_names:
      P1: "Normal"
      P2: "Abwesend"
  - climate.buero # Verwendet friendly_name aus HA
```

### Alle Optionen

| Option                  | Typ               | Standard       | Beschreibung                               |
| ----------------------- | ----------------- | -------------- | ------------------------------------------ |
| `entity`                | string            | -              | Einzelne Climate Entity                    |
| `entities`              | string[] or array | -              | Liste von Climate Entities                 |
| `name`                  | string            | Entity-Name    | Benutzerdefinierter Kartenkopf-Name        |
| `profile`               | string            | Aktives Profil | Anzeige eines bestimmten Profils erzwingen |
| `show_profile_selector` | boolean           | `true`         | Profil-Dropdown anzeigen/ausblenden        |
| `editable`              | boolean           | `true`         | Bearbeitung aktivieren/deaktivieren        |
| `show_temperature`      | boolean           | `true`         | Temperaturwerte auf Blöcken anzeigen       |
| `show_gradient`         | boolean           | `false`        | Farbverlauf zwischen Temperaturen anzeigen |
| `temperature_unit`      | string            | `°C`           | Temperatureinheit-Anzeige                  |
| `hour_format`           | string            | `24`           | Zeitformat: `12` oder `24` Stunden         |
| `language`              | string            | Auto-Erkennung | Sprache erzwingen: `en` oder `de`          |

#### Entity-Optionen

Jede Entity im `entities`-Array kann ein String oder ein Objekt sein:

| Option          | Typ              | Beschreibung                                          |
| --------------- | ---------------- | ----------------------------------------------------- |
| `entity`        | string           | Climate Entity ID (erforderlich)                      |
| `name`          | string           | Benutzerdefinierter Anzeigename für das Dropdown      |
| `profile_names` | Record\<string\> | Benutzerdefinierte Profilnamen (z.B. `P1: "Komfort"`) |

---

## Verwendung

### Zeitpläne anzeigen

Die Karte zeigt den Wochenzeitplan als farbcodierte Temperaturblöcke an:

| Farbbereich  | Temperatur | Beschreibung    |
| ------------ | ---------- | --------------- |
| Blau         | < 10°C     | Kalt            |
| Hellblau     | 10-14°C    | Kühl            |
| Cyan         | 14-17°C    | Mild kühl       |
| Grün         | 17-19°C    | Komfort niedrig |
| Hellgrün     | 19-21°C    | Komfort         |
| Hellorange   | 21-23°C    | Warm            |
| Orange       | 23-25°C    | Wärmer          |
| Dunkelorange | >= 25°C    | Heiß            |

Fahren Sie mit der Maus über einen Block, um den genauen Zeitraum und die Temperatur zu sehen.

### Zeitpläne bearbeiten

1. Auf eine beliebige **Tageszeile** in der Wochenansicht klicken
2. Der Editor öffnet sich mit allen Zeitslots für diesen Tag
3. Die **Basistemperatur** oben im Editor anpassen (Hintergrundtemperatur für nicht abgedeckte Zeiten)
4. **Endzeiten** und **Temperaturen** für jeden Block ändern
5. **+ Zeitblock hinzufügen** klicken, um eine Heizperiode hinzuzufügen
6. Das **Papierkorb-Symbol** klicken, um einen Block zu entfernen
7. **Speichern** klicken, um Änderungen an den Thermostat zu übertragen

!!! info "Automatisches Block-Zusammenfügen"
Aufeinanderfolgende Zeitblöcke mit derselben Temperatur werden beim Speichern automatisch zusammengefügt. Beispiel: 06:00-08:00 bei 22°C gefolgt von 08:00-10:00 bei 22°C wird zu einem einzelnen Block 06:00-10:00 bei 22°C.

### Profilwechsel

Verwenden Sie das Profil-Dropdown, um zwischen P1-P6 umzuschalten. Das aktuell aktive Profil auf dem Gerät wird mit einem Sternchen (\*) markiert.

!!! note "Anzeigen vs. Aktivieren"
Das Profil-Dropdown in der Karte dient zum **Anzeigen und Bearbeiten** verschiedener Profile. Um das aktive Profil auf dem Gerät zu ändern, verwenden Sie das [Gerätekonfigurations-Panel](config_panel.md).

### Zeitplanformat

Die Karte verwendet das **Einfache Format**: eine Basistemperatur plus explizite Heizperioden. Nur Perioden, die von der Basistemperatur abweichen, werden gespeichert.

**Beispiel**: Basis 17°C mit einer Heizperiode:

| Zeit          | Temperatur | Quelle          |
| ------------- | ---------- | --------------- |
| 00:00 - 06:00 | 17,0°C     | Basistemperatur |
| 06:00 - 22:00 | 21,0°C     | Heizperiode     |
| 22:00 - 24:00 | 17,0°C     | Basistemperatur |

Siehe [Wochenprofile](week_profile.md) für das vollständige Zeitplan-Datenformat und alle verfügbaren Aktionen.

---

## Berechtigungen

Standardmäßig können nur Administratoren Zeitpläne bearbeiten. Um Nicht-Admin-Haushaltsmitgliedern die Zeitplan-Bearbeitung zu erlauben, aktiviere dies in den Integrationsoptionen unter **Zeitplan-Bearbeitung**. Siehe [Zeitplan-Bearbeitung für Nicht-Admins](config_panel.md#non-admin-schedules) für Details.

---

## Fehlerbehebung

### Karte wird nicht angezeigt

1. Browser-Cache leeren (Strg+F5)
2. Sicherstellen, dass die HomematicIP Local Integration geladen und aktiv ist
3. Home Assistant-Protokolle auf Frontend-Registrierungsfehler prüfen

### Entity nicht gefunden

1. Überprüfen, ob die Climate Entity ID korrekt ist
2. Sicherstellen, dass die Entity Zeitplan-Attribute der HomematicIP Local Integration hat
3. Home Assistant Logs auf Fehler prüfen

### Änderungen werden nicht gespeichert

1. Home Assistant-Protokolle auf WebSocket-Fehler prüfen
2. Sicherstellen, dass CCU und Thermostat erreichbar sind
3. Warten, bis CONFIG_PENDING auf dem Gerät zurückgesetzt wird

---

## Siehe auch

- [Wochenprofile](week_profile.md) - Zeitplan-Datenformat, Aktionen und Beispiele
- [Schedule Card](schedule_card.md) - Zeitplan-Karte für Schalter, Lichter, Abdeckungen und Ventile
- [Status-Karten](status_cards.md) - Systemstatus, Gerätestatus und Meldungen
- [Gerätekonfigurations-Panel](config_panel.md) - Vollständige Gerätekonfigurations-UI
