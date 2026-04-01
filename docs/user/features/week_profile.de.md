---
translation_source: docs/user/features/week_profile.md
translation_date: 2026-04-01
translation_source_hash: 48147676f86a
---

# Wochenprofil / Zeitplanverwaltung

Diese Anleitung beschreibt die Verwaltung von Heizungszeitplänen (Wochenprofilen) und Gerätezeitplänen in Home Assistant mit der Homematic(IP) Local-Integration.

## Übersicht

Homematic-Geräte mit Wochenprofil-Unterstützung stellen eine **Wochenprofil-Sensor**-Entity bereit, die die Anzahl der aktiven Zeitplaneinträge anzeigt und Zeitplan-Metadaten als Attribute bereitstellt.

Alle Zeitplan-Services sind **gerätebasiert** - sie adressieren ein Gerät über `device_id` oder `device_address`, nicht über eine Entity.

### Klimageräte

Homematic-Thermostate unterstützen bis zu **6 Zeitplanprofile** (P1-P6), die jeweils einen Wochenplan mit individuellen Einstellungen für jeden Tag enthalten.

| Merkmal     | Beschreibung                                                   |
| ----------- | -------------------------------------------------------------- |
| **Profile** | P1 bis P6 (6 unabhängige Zeitpläne)                            |
| **Tage**    | MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY |
| **Format**  | Einfaches Format mit Basistemperatur und Heizperioden          |

### Nicht-Klimageräte (Schalter, Licht, Abdeckung, Ventil)

Geräte mit Wochenprofil-Fähigkeit unterstützen einen einzelnen Zeitplan mit bis zu 24 Einträgen.

| Merkmal      | Beschreibung                                         |
| ------------ | ---------------------------------------------------- |
| **Einträge** | Bis zu 24 Zeitplaneinträge                           |
| **Format**   | Generisches schedule_data-Dict mit time/level/target |

### Wert des Wochenprofil-Sensors

Die **Wochenprofil-Sensor**-Entity stellt einen numerischen `value` (Ganzzahl) bereit, der die **Gesamtzahl der aktiven Zeitplaneinträge** auf dem Gerät repräsentiert. Dies gibt einen schnellen Hinweis darauf, ob ein Zeitplan konfiguriert ist und wie umfassend er ist.

Wie der Wert berechnet wird, hängt vom Gerätetyp ab:

| Gerätetyp       | Zähllogik                                                                                                  |
| --------------- | ---------------------------------------------------------------------------------------------------------- |
| **Klima**       | Summe aller Temperaturperioden über alle Profile und Wochentage (z.B. 2 Perioden x 7 Tage x 1 Profil = 14) |
| **Nicht-Klima** | Anzahl der Zeitplaneinträge, die mindestens einen Zielkanal zugewiesen haben                               |

**Beispiele:**

- Ein Thermostat mit **1 aktivem Profil** und **2 Heizperioden pro Tag** -> Wert = **14** (2 x 7 Tage)
- Ein Thermostat **ohne konfigurierten Zeitplan** -> Wert = **0**
- Ein Schalter mit **3 Zeitplaneinträgen** (jeweils auf einen Kanal zielend) -> Wert = **3**

Dieser Wert ist nützlich für:

- **Schnelle Statusprüfung**: Wert `0` bedeutet, dass kein Zeitplan konfiguriert ist.
- **Automationen**: Aktionen auslösen, basierend darauf, ob ein Zeitplan existiert (Wert > 0) oder sich geändert hat.

---

## Geräteidentifikation

Alle Zeitplan-Services akzeptieren entweder `device_id` oder `device_address` zur Identifikation des Geräts:

```yaml
# Option 1: Per device_id (aus der HA-Geräteregistrierung)
data:
  device_id: abcdefg...

# Option 2: Per device_address (Homematic-Adresse)
data:
  device_address: "001F58A9876543"
```

---

## Klimazeitplan-Format

Das einfache Format ist für eine unkomplizierte Zeitplanverwaltung konzipiert. Statt jeden Zeitslot zu definieren, werden angegeben:

1. **Basistemperatur** - Die Standardtemperatur, wenn keine Heizperiode aktiv ist
2. **Perioden** - Nur die Zeiten, in denen eine _andere_ Temperatur gewünscht ist

### Struktur

```yaml
base_temperature: 17.0
periods:
  - starttime: "06:00"
    endtime: "08:00"
    temperature: 21.0
  - starttime: "17:00"
    endtime: "22:00"
    temperature: 21.0
```

### Funktionsweise

Das System füllt Lücken automatisch mit der Basistemperatur:

| Zeit          | Temperatur | Quelle                           |
| ------------- | ---------- | -------------------------------- |
| 00:00 - 06:00 | 17,0°C     | base_temperature                 |
| 06:00 - 08:00 | 21,0°C     | Periode 1                        |
| 08:00 - 17:00 | 17,0°C     | base_temperature (Lücke gefüllt) |
| 17:00 - 22:00 | 21,0°C     | Periode 2                        |
| 22:00 - 24:00 | 17,0°C     | base_temperature                 |

---

## Klimazeitplan-Actions

### Komplettes Profil setzen

Den Zeitplan für alle Wochentage eines Profils setzen:

```yaml
action: homematicip_local.set_schedule_profile
data:
  device_id: abcdefg...
  profile: P1
  simple_profile_data:
    MONDAY:
      base_temperature: 17.0
      periods:
        - starttime: "06:00"
          endtime: "08:00"
          temperature: 21.0
        - starttime: "17:00"
          endtime: "22:00"
          temperature: 21.0
    TUESDAY:
      base_temperature: 17.0
      periods:
        - starttime: "06:00"
          endtime: "08:00"
          temperature: 21.0
        - starttime: "17:00"
          endtime: "22:00"
          temperature: 21.0
    # ... weitere Wochentage hinzufuegen
```

### Einzelnen Wochentag setzen

Den Zeitplan für einen bestimmten Tag setzen:

```yaml
action: homematicip_local.set_schedule_weekday
data:
  device_id: abcdefg...
  profile: P1
  weekday: MONDAY
  base_temperature: 17.0
  simple_weekday_list:
    - starttime: "06:00"
      endtime: "08:00"
      temperature: 21.0
    - starttime: "17:00"
      endtime: "22:00"
      temperature: 21.0
```

### Zeitplan lesen

Den aktuellen Zeitplan abrufen:

```yaml
# Kompletten Zeitplan abrufen (alle Profile)
action: homematicip_local.get_schedule
data:
  device_id: abcdefg...

# Einzelnes Profil abrufen
action: homematicip_local.get_schedule_profile
data:
  device_id: abcdefg...
  profile: P1

# Einzelnen Wochentag abrufen
action: homematicip_local.get_schedule_weekday
data:
  device_id: abcdefg...
  profile: P1
  weekday: MONDAY
```

### Zeitpläne kopieren

Zeitpläne zwischen Geräten oder Profilen kopieren:

```yaml
# Kompletten Zeitplan (alle Profile) vom Quell- zum Zielgerät kopieren
action: homematicip_local.copy_schedule
data:
  device_id: abcdefg...
  target_device_id: hijklmn...

# Einzelnes Profil kopieren (innerhalb desselben Geräts oder zu einem anderen)
action: homematicip_local.copy_schedule_profile
data:
  device_id: abcdefg...
  source_profile: P1
  target_profile: P2
  target_device_id: hijklmn...  # Optional: weglassen, wenn innerhalb desselben Geräts kopiert wird
```

---

## Nicht-Klima-Zeitplan-Actions { #non-climate-schedule-actions }

Nicht-Klimageräte (Schalter, Licht, Abdeckung, Ventil) verwenden die einheitlichen `get_schedule`- und `set_schedule`-Services.

### Zeitplan setzen

Einen Wochenzeitplan für Geräte mit Zeitplanunterstützung setzen:

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Eintrag 1
      weekdays:
        - SUNDAY
        - MONDAY
        - TUESDAY
        - WEDNESDAY
        - THURSDAY
        - FRIDAY
      time: "06:00"
      condition: fixed_time
      target_channels:
        - "1_1"
      level: 0.5 # 50% Helligkeit
      duration: 1min
      ramp_time: 10s
    "2": # Eintrag 2
      weekdays:
        - SATURDAY
      time: "08:00"
      condition: fixed_time
      target_channels:
        - "1_1"
      level: 0.3 # 30% Helligkeit
      duration: 1min
      ramp_time: 10s
```

### Zeitplan abrufen

Den aktuellen Wochenzeitplan eines Geräts abrufen:

```yaml
action: homematicip_local.get_schedule
data:
  device_id: abcdefg...
response_variable: current_schedule
```

Der Service gibt die Zeitplandaten im selben Format zurück, das vom set_schedule-Service verwendet wird:

```yaml
# Antwortbeispiel gespeichert in current_schedule
{
  "1":
    {
      "weekdays":
        ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
      "time": "06:00",
      "condition": "fixed_time",
      "astro_type": null,
      "astro_offset_minutes": 0,
      "target_channels": ["1_1"],
      "level": 0.5,
      "level_2": null,
      "duration": "1min",
      "ramp_time": "10s",
    },
  "2":
    {
      "weekdays": ["SATURDAY"],
      "time": "08:00",
      "condition": "fixed_time",
      "astro_type": null,
      "astro_offset_minutes": 0,
      "target_channels": ["1_1"],
      "level": 0.3,
      "level_2": null,
      "duration": "1min",
      "ramp_time": "10s",
    },
}
```

### Unterstützte Domänen und Feldeinschränkungen

Jede Domäne unterstützt unterschiedliche Felder. Die Verwendung nicht unterstützter Felder führt zu einem Validierungsfehler.

| Feld        |       Schalter        |    Licht     |       Abdeckung       |    Ventil    |
| ----------- | :-------------------: | :----------: | :-------------------: | :----------: |
| `level`     | ✅ (nur 0.0 oder 1.0) | ✅ (0.0-1.0) |     ✅ (0.0-1.0)      | ✅ (0.0-1.0) |
| `level_2`   |          ❌           |      ❌      | ✅ (Lamellenposition) |      ❌      |
| `duration`  |          ✅           |      ✅      |          ❌           |      ✅      |
| `ramp_time` |          ❌           |      ✅      |          ❌           |      ❌      |

**Wichtige Einschränkungen:**

- **Schalter**: Das Feld `level` akzeptiert nur `0.0` (aus) oder `1.0` (ein). Zwischenwerte wie `0.5` sind nicht erlaubt.
- **Licht**: Unterstützt `ramp_time` für sanfte Dimmübergänge. Unterstützt kein `level_2`.
- **Abdeckung**: Unterstützt `level_2` für die Lamellen-/Jalousieposition. Unterstützt weder `duration` noch `ramp_time`.
- **Ventil**: Unterstützt weder `level_2` noch `ramp_time`.

### Zeitplandatenformat

Die `schedule_data` sind ein Dictionary, bei dem:

- **Schlüssel**: String mit der Eintragsnummer ("1" bis "24")
- **Wert**: Dictionary mit Details des Zeitplaneintrags (`SimpleScheduleEntry`-Felder)

Jeder Eintrag wird durch das `SimpleScheduleEntry`-Pydantic-Modell validiert und enthält die folgenden Felder:

#### Pflichtfelder

##### weekdays

- **Typ**: Liste von Strings
- **Beschreibung**: Tage, an denen dieser Zeitplan ausgelöst wird
- **Gültige Werte**: `"MONDAY"`, `"TUESDAY"`, `"WEDNESDAY"`, `"THURSDAY"`, `"FRIDAY"`, `"SATURDAY"`, `"SUNDAY"`
- **Einschränkung**: Mindestens ein Wochentag erforderlich
- **Beispiel**: `["MONDAY", "FRIDAY"]` oder `["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]`

##### time

- **Typ**: String
- **Beschreibung**: Auslösezeitpunkt im 24-Stunden-Format
- **Format**: `"HH:MM"` (Stunden: 00-23, Minuten: 00-59)
- **Beispiel**: `"07:30"`, `"22:00"`, `"00:00"`

##### target_channels

- **Typ**: Liste von Strings
- **Beschreibung**: Ziel-Aktorenkanäle zur Steuerung
- **Format**: Jeder Kanal als `"X_Y"`, wobei X=1-8 (Gerätekanal), Y=1-3 (Aktorkanal)
- **Einschränkung**: Mindestens ein Kanal erforderlich
- **Beispiel**: `["1_1"]`, `["1_1", "2_1"]`

##### level

- **Typ**: Float
- **Beschreibung**: Ausgangspegel für das Zielgerät
- **Bereich**: 0.0 bis 1.0
- **Bedeutung nach Gerätetyp**:
  - **Schalter**: `0.0` = aus, `1.0` = ein
  - **Licht (dimmbar)**: `0.0` = aus, `1.0` = 100% Helligkeit, `0.5` = 50% Helligkeit
  - **Abdeckung**: `0.0` = geschlossen, `1.0` = offen
  - **Ventil**: `0.0` = geschlossen, `1.0` = offen
- **Beispiel**: `0.0`, `0.5`, `1.0`

#### Optionale Felder

##### condition

- **Typ**: String
- **Beschreibung**: Auslösebedingungstyp
- **Gültige Werte**:
  - `"fixed_time"` (Standard) - Auslösung zur angegebenen Zeit
  - `"astro"` - Auslösung bei Astro-Ereignis (Sonnenaufgang/Sonnenuntergang)
  - `"fixed_if_before_astro"` - Auslösung zur Zeit, wenn vor dem Astro-Ereignis, sonst beim Astro-Ereignis
  - `"fixed_if_after_astro"` - Auslösung zur Zeit, wenn nach dem Astro-Ereignis, sonst beim Astro-Ereignis
- **Standard**: `"fixed_time"`
- **Hinweis**: Bei Verwendung von Astro-Bedingungen muss `astro_type` gesetzt sein

##### astro_type

- **Typ**: String oder null
- **Beschreibung**: Astronomischer Ereignistyp für astrobasierte Bedingungen
- **Gültige Werte**: `"sunrise"`, `"sunset"`, `null`
- **Standard**: `null`
- **Erforderlich wenn**: `condition` nicht `"fixed_time"` ist

##### astro_offset_minutes

- **Typ**: Ganzzahl
- **Beschreibung**: Versatz in Minuten vom astronomischen Ereignis
- **Bereich**: -720 bis 720 (-12 Stunden bis +12 Stunden)
- **Standard**: `0`
- **Beispiel**: `30` (30 Minuten danach), `-60` (60 Minuten davor)

##### level_2

- **Typ**: Float oder null
- **Beschreibung**: Sekundärer Pegel für Geräte mit doppeltem Ausgang (z.B. Abdeckung-Lamellenposition)
- **Bereich**: 0.0 bis 1.0
- **Standard**: `null`
- **Verwendet von**: Abdeckungsgeräte (für Lamellen-/Jalousieposition)

##### duration

- **Typ**: String oder null
- **Beschreibung**: Wie lange der Ausgang aktiv gehalten wird
- **Format**: Zahl gefolgt von Einheit: `"Xs"` (Sekunden), `"Xmin"` (Minuten), `"Xh"` (Stunden)
- **Standard**: `null` (dauerhaft/bis zum nächsten Zeitplan)
- **Beispiele**: `"10s"`, `"5min"`, `"1h"`, `"30min"`

##### ramp_time

- **Typ**: String oder null
- **Beschreibung**: Übergangs-/Rampenzeit für Dimmergeräte
- **Format**: Zahl gefolgt von Einheit: `"Xms"` (Millisekunden), `"Xs"` (Sekunden)
- **Standard**: `null` (sofortige Änderung)
- **Beispiele**: `"500ms"`, `"2s"`, `"10s"`
- **Verwendet von**: Dimmbare Leuchten

#### Feldübersichtstabelle

| Feld                 | Typ         | Pflicht | Bereich/Format         | Standard     |
| -------------------- | ----------- | ------- | ---------------------- | ------------ |
| weekdays             | list[str]   | ✅      | MONDAY-SUNDAY          | -            |
| time                 | str         | ✅      | HH:MM (00:00-23:59)    | -            |
| target_channels      | list[str]   | ✅      | ["X_Y"]                | -            |
| level                | float       | ✅      | 0.0-1.0                | -            |
| condition            | str         | ❌      | fixed_time, astro, ... | "fixed_time" |
| astro_type           | str \| null | ❌      | sunrise, sunset, null  | null         |
| astro_offset_minutes | int         | ❌      | -720 bis 720           | 0            |
| level_2              | float\|null | ❌      | 0.0-1.0 oder null      | null         |
| duration             | str \| null | ❌      | "10s", "5min", "1h"    | null         |
| ramp_time            | str \| null | ❌      | "500ms", "2s"          | null         |

#### Vollständiges Beispiel

```yaml
schedule_data:
  "1": # Werktag morgens (feste Zeit)
    weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
    time: "06:30"
    condition: fixed_time
    target_channels: ["1_1"]
    level: 0.8 # 80% Helligkeit
    duration: 1min
    ramp_time: 10s
    astro_type: null
    astro_offset_minutes: 0
    level_2: null
  "2": # Wochenende morgens (sonnenaufgangsbasiert)
    weekdays: [SATURDAY, SUNDAY]
    time: "08:00" # Rueckfallzeit
    condition: fixed_if_after_astro # 08:00 verwenden, wenn nach Sonnenaufgang, sonst Sonnenaufgang
    astro_type: sunrise
    astro_offset_minutes: 30 # 30 Minuten nach Sonnenaufgang
    target_channels: ["1_1"]
    level: 0.5 # 50% Helligkeit
    duration: 30min
    ramp_time: 5s
    level_2: null
```

---

## Gängige Klimazeitpläne

### Werktagszeitplan

```yaml
base_temperature: 17.0
periods:
  - starttime: "06:00"
    endtime: "07:30"
    temperature: 21.0
  - starttime: "17:00"
    endtime: "22:00"
    temperature: 21.0
```

### Wochenendzeitplan

```yaml
base_temperature: 17.0
periods:
  - starttime: "08:00"
    endtime: "23:00"
    temperature: 21.0
```

### Homeoffice-Zeitplan

```yaml
base_temperature: 17.0
periods:
  - starttime: "07:00"
    endtime: "22:00"
    temperature: 21.0
```

### Nur Nachtabsenkung

```yaml
base_temperature: 21.0
periods:
  - starttime: "23:00"
    endtime: "06:00"
    temperature: 17.0
```

## Tipps

### Auswahl der Basistemperatur

Die `base_temperature` sollte:

- Die Temperatur sein, die die meiste Zeit gewünscht ist
- Üblicherweise die "Absenktemperatur" oder "Spartemperatur"
- Typischerweise 16-18°C für Energieeinsparungen

### Periodengestaltung

- **Perioden einfach halten** - 2-4 Perioden pro Tag sind in der Regel ausreichend
- **Kleine Lücken vermeiden** - Wenn zwei Perioden nah beieinander liegen, zusammenführen
- **Zeiten runden** - 15- oder 30-Minuten-Schritte für einfachere Verwaltung verwenden

### Best Practices beim Kopieren

1. **Vorlagegerät erstellen** - Einen Thermostat perfekt einrichten, dann auf andere kopieren
2. **Profile kopieren, nicht Geräte** - `copy_schedule_profile` für mehr Kontrolle verwenden
3. **Nach dem Kopieren prüfen** - `get_schedule_profile` zur Bestätigung verwenden

---

## Automationsbeispiele

### Klimaprofil am Freitagabend umschalten

```yaml
automation:
  - alias: "Auf Wochenendzeitplan umschalten"
    trigger:
      - platform: time
        at: "18:00"
    condition:
      - condition: time
        weekday:
          - fri
    action:
      - action: homematicip_local.set_schedule_weekday
        data:
          device_id: abcdefg...
          profile: P1
          weekday: SATURDAY
          base_temperature: 17.0
          simple_weekday_list:
            - starttime: "08:00"
              endtime: "23:00"
              temperature: 21.0
```

### Beispiel: Schalterzeitplan

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Werktag abends
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "18:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Ein (nur 0.0 oder 1.0 erlaubt!)
      duration: 4h
    "2": # Wochenende abends
      weekdays: [SATURDAY, SUNDAY]
      time: "17:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Ein
      duration: 6h
```

### Beispiel: Gartenbewässerungsventil

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Morgenbewaesserung an Werktagen
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "06:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Voll geöffnet
      duration: 30min
    "2": # Abendbewaesserung an Werktagen
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "18:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Voll geöffnet
      duration: 30min
    "3": # Wochenendbewaesserung
      weekdays: [SATURDAY, SUNDAY]
      time: "07:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Voll geöffnet
      duration: 45min
```

### Beispiel: Lichtdimmer-Zeitplan

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Werktag morgens
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "06:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.3 # 30% Helligkeit
      duration: 2h
      ramp_time: 10s # Sanfter Übergang (nur für Lichter!)
    "2": # Werktag abends
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "17:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.6 # 60% Helligkeit
      duration: 5h
      ramp_time: 10s
    "3": # Spaetabends
      weekdays: [SUNDAY, MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY]
      time: "22:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.2 # 20% Helligkeit
      duration: 1h
      ramp_time: 10s
```

### Beispiel: Abdeckungs-/Jalousiezeitplan

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1": # Morgens - Jalousien öffnen
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
      time: "07:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0 # Voll geöffnet
      level_2: 0.5 # Lamellen auf 50% (nur für Abdeckungen!)
    "2": # Mittags - Teilbeschattung
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
      time: "12:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.7 # 70% geöffnet
      level_2: 0.3 # Lamellen auf 30%
    "3": # Abends - Jalousien schließen
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY]
      time: "21:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 0.0 # Geschlossen
      level_2: 0.0 # Lamellen geschlossen
```

---

## Unterschiede: Klima vs. Nicht-Klima

| Merkmal      | Klima-Services                              | Nicht-Klima-Services               |
| ------------ | ------------------------------------------- | ---------------------------------- |
| **Geräte**   | Nur Thermostate                             | Schalter, Licht, Abdeckung, Ventil |
| **Format**   | Einfaches Format mit base_temperature       | Generisches schedule_data-Dict     |
| **Profile**  | P1-P6 Profile                               | Einzelner Zeitplan (Geräteebene)   |
| **Services** | set_schedule_profile / set_schedule_weekday | set_schedule                       |

---

## Fehlerbehebung

### Zeitplan wird nicht angewendet

1. **CONFIG_PENDING prüfen** - Auf die Bestätigung der Änderung durch das Gerät warten
2. **Profilauswahl überprüfen** - Sicherstellen, dass das richtige Profil (P1-P6) auf dem Gerät aktiv ist (nur Klima)
3. **Zeitformat prüfen** - Das Format `"HH:MM"` verwenden (24-Stunden, mit Anführungszeichen in YAML)
4. **Geräteunterstützung** - Überprüfen, ob das Gerät Zeitpläne unterstützt (Wochenprofil-Sensor-Entity prüfen)

### Lesevorgang gibt leeres Ergebnis zurück

- Das Gerät unterstützt möglicherweise keine Zeitpläne
- Die Gerätekonfiguration neu laden
- Prüfen, ob ein Wochenprofil auf dem Gerät konfiguriert ist

### Kopieren schlägt fehl

- Beide Geräte müssen Zeitpläne unterstützen
- Beide Geräte müssen die gleiche Anzahl an Profilen haben (nur Klima)
- Prüfen, ob die Geräte erreichbar sind

### Validierungsfehler: Nicht unterstütztes Feld

Bei einer Fehlermeldung wie "level_2 not supported for switch" oder "ramp_time not supported for cover":

- Die [Feldeinschränkungstabelle](#unterstutzte-domanen-und-feldeinschrankungen) für die jeweilige Domäne prüfen
- Nicht unterstützte Felder aus den Zeitplandaten entfernen
- Bei Schaltern sicherstellen, dass `level` exakt `0.0` oder `1.0` ist (keine Zwischenwerte)

## Siehe auch

- [Actions-Referenz](homeassistant_actions.md#zeitplan-operationen)
- [Klima-Entities](../homeassistant_integration.md)
