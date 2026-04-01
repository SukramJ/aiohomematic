---
translation_source: docs/user/features/homeassistant_actions.md
translation_date: 2026-04-01
translation_source_hash: 4e8e07accf4c
---

# Actions-Referenz

Diese Seite dokumentiert alle benutzerdefinierten Actions, die von der Homematic(IP) Local for OpenCCU-Integration bereitgestellt werden.

---

## Geraetwert-Operationen

### homematicip_local.get_device_value

Einen Geraeteparameter ueber die XML-RPC-Schnittstelle abrufen.

### homematicip_local.set_device_value

Einen Geraeteparameter ueber die XML-RPC-Schnittstelle setzen.

!!! warning "Speicher-Warnung"
Zu haeufiges Schreiben in das MASTER-Paramset des Geraets kann den Speicher des Geraets beschaedigen.

**Beispiel - Einen Schalter einschalten:**

```yaml
action: homematicip_local.set_device_value
data:
  device_id: abcdefg...
  channel: 1
  parameter: STATE
  value: "true"
  value_type: boolean
```

**Beispiel - Thermostat-Temperatur setzen:**

```yaml
action: homematicip_local.set_device_value
data:
  device_id: abcdefg...
  channel: 4
  parameter: SET_TEMPERATURE
  value: "23.0"
  value_type: double
```

---

## Paramset-Operationen

### homematicip_local.get_paramset

`getParamset` auf der XML-RPC-Schnittstelle aufrufen. Gibt ein Paramset zurueck.

### homematicip_local.put_paramset

`putParamset` auf der XML-RPC-Schnittstelle aufrufen.

!!! warning "Speicher-Warnung"
Zu haeufiges Schreiben in das MASTER-Paramset des Geraets kann den Speicher des Geraets beschaedigen.

**Beispiel - Wochenprogramm setzen:**

```yaml
action: homematicip_local.put_paramset
data:
  device_id: abcdefg...
  paramset_key: MASTER
  paramset:
    WEEK_PROGRAM_POINTER: 1
```

**Beispiel mit rx_mode (nur BidCos-RF):**

```yaml
action: homematicip_local.put_paramset
data:
  device_id: abcdefg...
  paramset_key: MASTER
  rx_mode: WAKEUP
  paramset:
    WEEK_PROGRAM_POINTER: 1
```

!!! note "rx_mode-Optionen" - `BURST` (Standard): Weckt alle Geraete sofort auf (verbraucht Batterie) - `WAKEUP`: Sendet Daten nach Geraete-Rueckmeldung (schont Batterie, ca. 3 Min. Verzoegerung)

### homematicip_local.get_link_paramset

`getParamset` fuer Direktverknuepfungen auf der XML-RPC-Schnittstelle aufrufen.

### homematicip_local.put_link_paramset

`putParamset` fuer Direktverknuepfungen auf der XML-RPC-Schnittstelle aufrufen.

---

## Verknuepfungs-Operationen

### homematicip_local.add_link

`addLink` auf der XML-RPC-Schnittstelle aufrufen. Erstellt eine Direktverknuepfung.

### homematicip_local.remove_link

`removeLink` auf der XML-RPC-Schnittstelle aufrufen. Entfernt eine Direktverknuepfung.

### homematicip_local.get_link_peers

`getLinkPeers` auf der XML-RPC-Schnittstelle aufrufen. Gibt ein Dictionary der Direktverknuepfungs-Partner zurueck.

### homematicip_local.create_central_links

Erstellt eine zentrale Verknuepfung von einem Geraet zum Backend. Erforderlich fuer RF-Geraete, um Tastendruck-Ereignisse zu aktivieren.

### homematicip_local.remove_central_links

Entfernt eine zentrale Verknuepfung vom Backend. Deaktiviert Tastendruck-Ereignisse.

---

## Zeitplan-Operationen

Alle Zeitplan-Services sind **geraetebasiert** -- sie sprechen ein Geraet ueber `device_id` oder `device_address` an statt ueber eine Entity. Dieser einheitliche Ansatz funktioniert fuer alle Geraetetypen (Klima, Schalter, Licht, Abdeckung, Ventil).

!!! warning "Speicher-Warnung"
Zu haeufiges Schreiben auf das Geraet kann den Speicher des Geraets beschaedigen.

### homematicip_local.get_schedule

Gibt den vollstaendigen Zeitplan eines Geraets zurueck. Funktioniert sowohl fuer Klima- als auch fuer Nicht-Klima-Geraete.

```yaml
action: homematicip_local.get_schedule
data:
  device_id: abcdefg...
```

### homematicip_local.set_schedule

Setzt den vollstaendigen Zeitplan auf einem Geraet. Fuer Nicht-Klima-Geraete `schedule_data` mit Entry-Dict-Format verwenden.

```yaml
action: homematicip_local.set_schedule
data:
  device_id: abcdefg...
  schedule_data:
    "1":
      weekdays: [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]
      time: "18:00"
      condition: fixed_time
      target_channels: ["1_1"]
      level: 1.0
      duration: 4h
```

### homematicip_local.get_schedule_profile

Gibt ein einzelnes Klima-Zeitplanprofil in vereinfachtem Format zurueck. Nur fuer Klimageraete.

Der Service analysiert den Zeitplan und bestimmt `base_temperature` als die am haeufigsten verwendete Temperatur. Nur abweichende Zeitraeume werden zurueckgegeben.

```yaml
action: homematicip_local.get_schedule_profile
data:
  device_id: abcdefg...
  profile: P1
```

### homematicip_local.get_schedule_weekday

Gibt den Zeitplan fuer einen bestimmten Wochentag eines Klimaprofils in vereinfachtem Format zurueck.

```yaml
action: homematicip_local.get_schedule_weekday
data:
  device_id: abcdefg...
  profile: P1
  weekday: MONDAY
```

### homematicip_local.set_schedule_profile

Sendet einen vollstaendigen Zeitplan fuer ein Klimaprofil im **vereinfachten Format**. Nur fuer Klimageraete.

**Funktionsweise:**

- Jeder Wochentag hat eine `base_temperature` und eine Liste von `periods`
- Nur aktive Heizperioden mit `starttime`, `endtime` und `temperature` angeben
- Luecken werden automatisch mit `base_temperature` gefuellt
- Das System konvertiert in das erforderliche 13-Slot-Format

**Beispiel:**

```yaml
action: homematicip_local.set_schedule_profile
data:
  device_id: abcdefg...
  profile: P1
  simple_profile_data:
    MONDAY:
      base_temperature: 16.0
      periods:
        - starttime: "05:00"
          endtime: "06:00"
          temperature: 17.0
        - starttime: "09:00"
          endtime: "15:00"
          temperature: 17.0
        - starttime: "19:00"
          endtime: "22:00"
          temperature: 22.0
    TUESDAY:
      base_temperature: 16.0
      periods:
        - starttime: "05:00"
          endtime: "06:00"
          temperature: 17.0
        - starttime: "19:00"
          endtime: "22:00"
          temperature: 22.0
    # Weitere Wochentage nach Bedarf hinzufuegen
```

### homematicip_local.set_schedule_weekday

Sendet den Zeitplan fuer einen einzelnen Wochentag im vereinfachten Format. Nur fuer Klimageraete.

**Beispiel:**

```yaml
action: homematicip_local.set_schedule_weekday
data:
  device_id: abcdefg...
  profile: P3
  weekday: MONDAY
  base_temperature: 16
  simple_weekday_list:
    - starttime: "05:00"
      endtime: "06:00"
      temperature: 17.0
    - starttime: "09:00"
      endtime: "15:00"
      temperature: 17.0
    - starttime: "19:00"
      endtime: "22:00"
      temperature: 22.0
```

**Ergebnis:**

- 00:00-05:00: 16°C (base_temperature)
- 05:00-06:00: 17°C (Zeitraum 1)
- 06:00-09:00: 16°C (Basistemperatur fuellt Luecke)
- 09:00-15:00: 17°C (Zeitraum 2)
- 15:00-19:00: 16°C (Basistemperatur fuellt Luecke)
- 19:00-22:00: 22°C (Zeitraum 3)
- 22:00-24:00: 16°C (base_temperature)

### homematicip_local.copy_schedule

Kopiert den vollstaendigen Zeitplan (alle Profile P1-P6, alle Wochentage) von einem Klimageraet auf ein anderes.

**Voraussetzungen:**

- Beide Geraete muessen Klima-Zeitplaene unterstuetzen
- Beide Geraete muessen die gleiche Anzahl an Profilen unterstuetzen

```yaml
action: homematicip_local.copy_schedule
data:
  device_id: abcdefg...
  target_device_id: hijklmn...
```

### homematicip_local.copy_schedule_profile

Kopiert ein einzelnes Zeitplanprofil von einem Geraet auf ein anderes (oder auf ein anderes Profil desselben Geraets).

**Anwendungsfaelle:**

- P1 von Geraet A nach P2 auf Geraet A kopieren
- P1 von Geraet A nach P1 auf Geraet B kopieren
- P3 von Geraet A nach P1 auf Geraet B kopieren

```yaml
action: homematicip_local.copy_schedule_profile
data:
  device_id: abcdefg...
  source_profile: P1
  target_profile: P2
  target_device_id: hijklmn... # Optional: weglassen beim Kopieren innerhalb desselben Geraets
```

---

## Klima-Abwesenheitsmodus

### homematicip_local.enable_away_mode_by_calendar

Abwesenheitsmodus durch Angabe von Start- und Enddatum/-uhrzeit aktivieren.

!!! note "Nur HomematicIP"

### homematicip_local.enable_away_mode_by_duration

Abwesenheitsmodus sofort mit Dauer in Stunden aktivieren.

!!! note "Nur HomematicIP"

### homematicip_local.disable_away_mode

Abwesenheitsmodus fuer Klimageraete deaktivieren.

!!! note "Nur HomematicIP"

---

## Systemvariablen

### homematicip_local.get_variable_value

Den Wert einer Variablen vom Homematic-Hub abrufen.

### homematicip_local.set_variable_value

Den Wert einer Variablen auf dem Homematic-Hub setzen.

**Wertelisten:** Akzeptieren 0-basierte Position oder den Wert als Eingabe.

**Boolesche Werte:**

- `true`, `on`, `1`, 1 → True
- `false`, `off`, `0`, 0 → False

**Beispiel:**

```yaml
action: homematicip_local.set_variable_value
data:
  entity_id: sensor.ccu2
  name: Variable name
  value: true
```

### homematicip_local.fetch_system_variables

Systemvariablen auf Abruf laden, unabhaengig vom standardmaessigen 30-Sekunden-Intervall.

!!! warning "Sparsam verwenden - haeufige Aufrufe koennen die CCU-Stabilitaet beeintraechtigen"

---

## Sirenen- und Sound-Operationen

### homematicip_local.turn_on_siren

Sirene einschalten. Kann mit `siren.turn_off` deaktiviert werden.

!!! note "Automatische Select-Entities"
Seit Version 2.0.0 erstellt die Integration automatisch **Select-Entities** fuer die Auswahl von Sirenenton und Lichtmuster:

    - **Sirenenton** (`select.<device>_acoustic_alarm_selection`)
    - **Sirenen-Lichtmuster** (`select.<device>_optical_alarm_selection`)

    Diese Auswahl bleibt ueber Neustarts erhalten und wird automatisch beim Aufruf von Sirenen-Services verwendet.

### homematicip_local.play_sound

Einen Sound auf HmIP-MP3P-Soundplayer-Geraeten abspielen.

| Feld          | Erforderlich | Beschreibung                                            |
| ------------- | ------------ | ------------------------------------------------------- |
| `soundfile`   | Nein         | Sounddatei (z.B. `SOUNDFILE_001`, `INTERNAL_SOUNDFILE`) |
| `volume`      | Nein         | Lautstaerke (0.0 bis 1.0)                               |
| `on_time`     | Nein         | Dauer in Sekunden                                       |
| `ramp_time`   | Nein         | Lautstaerke-Einblendzeit in Sekunden                    |
| `repetitions` | Nein         | Wiederholungen (0=keine, 1-18=Anzahl, -1=endlos)        |

### homematicip_local.stop_sound

Soundwiedergabe auf HmIP-MP3P-Geraeten stoppen.

### homematicip_local.set_sound_led

LED-Farbe und -Helligkeit auf HmIP-MP3P-Geraeten setzen.

| Feld          | Erforderlich | Beschreibung                                                                         |
| ------------- | ------------ | ------------------------------------------------------------------------------------ |
| `color`       | Nein         | LED-Farbe: `black`, `blue`, `green`, `turquoise`, `red`, `purple`, `yellow`, `white` |
| `brightness`  | Nein         | Helligkeit (0 bis 255)                                                               |
| `on_time`     | Nein         | Dauer in Sekunden                                                                    |
| `ramp_time`   | Nein         | Einblendzeit in Sekunden                                                             |
| `repetitions` | Nein         | Wiederholungen                                                                       |
| `flash_time`  | Nein         | Blitzdauer in ms (0 bis 5000)                                                        |

---

## Abdeckungs-Operationen

### homematicip_local.set_cover_combined_position

Eine Jalousie gleichzeitig auf eine bestimmte Position und Neigungsposition fahren.

---

## Licht- und Schalter-Einschaltzeit

### homematicip_local.light_set_on_time

Einschaltzeit fuer eine Licht-Entity setzen. Muss von `light.turn_on` gefolgt werden. 0 verwenden zum Zuruecksetzen.

### homematicip_local.switch_set_on_time

Einschaltzeit fuer eine Schalter-Entity setzen. Muss von `switch.turn_on` gefolgt werden. 0 verwenden zum Zuruecksetzen.

### homematicip_local.valve_set_on_time

Einschaltzeit fuer eine Ventil-Entity setzen. Muss von `valve.open` gefolgt werden. 0 verwenden zum Zuruecksetzen.

---

## Textanzeige

### homematicip_local.send_text_display

Text an eine Notify-Entity senden (Textanzeigegeraete wie HmIP-WRCD).

| Feld               | Erforderlich | Beschreibung                                                                                                                                       |
| ------------------ | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_id`        | Ja           | Notify-Entity-ID (Domain: `notify`)                                                                                                                |
| `text`             | Ja           | Anzuzeigender Text                                                                                                                                 |
| `icon`             | Nein         | Anzeigesymbol (siehe Optionen unten)                                                                                                               |
| `background_color` | Nein         | Hintergrundfarbe: `white`, `black`                                                                                                                 |
| `text_color`       | Nein         | Textfarbe: `white`, `black`                                                                                                                        |
| `alignment`        | Nein         | Textausrichtung: `left`, `center`, `right`                                                                                                         |
| `display_id`       | Nein         | Display-ID (1-5) fuer Geraete mit mehreren Anzeigen                                                                                                |
| `sound`            | Nein         | Sound: `disarmed`, `externally_armed`, `internally_armed`, `delayed_externally_armed`, `delayed_internally_armed`, `event`, `error`, `low_battery` |
| `repeat`           | Nein         | Wiederholungsanzahl (0-15)                                                                                                                         |

**Verfuegbare Symbole:**

`no_icon`, `sun`, `moon`, `cloud`, `cloud_and_sun`, `cloud_and_mooon`, `cloud_sun_and_rain`, `rain`, `raindrop`, `drizzle`, `snow`, `snowflake`, `wind`, `thunderstorm`, `bell`, `clock`, `eco`, `flame`, `lamp_on`, `lamp_off`, `padlock_open`, `padlock_closed`, `error`, `everything_okay`, `information`, `new_message`, `service_message`, `shutters`, `window_open`, `external_protection`, `internal_protection`, `protection_deactivated`

**Beispiel:**

```yaml
action: homematicip_local.send_text_display
target:
  entity_id: notify.display_living_room
data:
  text: "Hello World"
  icon: sun
  background_color: white
  text_color: black
  alignment: center
  sound: event
```

### homematicip_local.clear_text_display

Text auf einer Notify-Entity (Textanzeige) loeschen.

---

## Geraeteverwaltung

### homematicip_local.export_device_definition

Exportiert eine Geraetedefinition als ZIP-Datei nach:
`{HA_config}/homematicip_local/{device_model}.zip`

Die ZIP-Datei enthaelt:

- `device_descriptions/{device_model}.json`
- `paramset_descriptions/{device_model}.json`

Auf [pydevccu](https://github.com/sukramj/pydevccu) hochladen, um die Entwicklung neuer Geraete zu unterstuetzen.

### homematicip_local.reload_device_config

Geraetekonfiguration von der CCU neu laden. Aktualisiert Paramset-Beschreibungen und Werte.

### homematicip_local.reload_channel_config

Konfiguration fuer einen bestimmten Channel von der CCU neu laden.

### homematicip_local.force_device_availability

Ein Geraet in HA reaktivieren, das durch ein UNREACH-Ereignis als nicht verfuegbar markiert wurde.

!!! warning "Keine Loesung fuer Kommunikationsprobleme"
Dies ueberschreibt lediglich den Verfuegbarkeitsstatus in HA. Es findet keine Kommunikation mit dem Backend statt.

### homematicip_local.confirm_all_delayed_devices

Bestaetigt alle verzoegerten Geraete (CCU-Posteingang) auf einmal und fuegt sie ohne benutzerdefinierte Namen zu Home Assistant hinzu.

---

## Systemoperationen

### homematicip_local.clear_cache

Loescht den Cache einer Zentraleinheit aus Home Assistant. Erfordert einen Neustart.

### homematicip_local.record_session

Zeichnet eine Sitzung zur Fehlersuche auf (maximal 10 Minuten). Ausgabe gespeichert unter:
`{HA_config}/homematicip_local/session/`

### homematicip_local.create_ccu_backup

Eine Systemsicherung von der CCU erstellen und herunterladen.

!!! note "Nur OpenCCU"
Diese Funktion ist nur fuer OpenCCU (ehemals RaspberryMatic) verfuegbar. Nicht unterstuetzt auf CCU2, CCU3, Debmatic oder piVCCU.

Sicherung gespeichert unter: `{HA_storage}/homematicip_local/backup/`

**Rueckgabe:**

```yaml
success: true
path: "/config/.storage/homematicip_local/backup/ccu_backup_raspberrymatic_20251203_143022.sbk"
filename: "ccu_backup_raspberrymatic_20251203_143022.sbk"
size: 12345678
```

**Automation-Beispiel - Woechentliche Sicherung:**

```yaml
automation:
  - alias: "Weekly OpenCCU Backup"
    trigger:
      - platform: time
        at: "03:00:00"
    condition:
      - condition: time
        weekday:
          - sun
    action:
      - action: homematicip_local.create_ccu_backup
        data:
          entry_id: YOUR_ENTRY_ID
```

---

## Integrierte Home Assistant Actions

### homeassistant.update_entity

Entity-Wert aktualisieren (begrenzt auf einmal pro 60 Sekunden).

!!! note "Sparsam verwenden"
99,9 % der Entities aktualisieren sich automatisch. Nur fuer Ausnahmefaelle verwenden (z.B. RSSI-Werte einiger HM-Geraete).

    - Batteriegeraete: Werte aus dem Backend-Cache
    - Nicht-Batteriegeraete: Werte vom Geraet (beeinflusst den Duty Cycle)

### homematicip_local.update_device_firmware_data

Firmware-Daten fuer alle Geraete aktualisieren.

---

## Siehe auch

- [Integrationsanleitung](../homeassistant_integration.md)
- [Fehlerbehebung](../troubleshooting/homeassistant_troubleshooting.md)
