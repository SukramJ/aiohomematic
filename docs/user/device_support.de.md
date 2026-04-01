---
translation_source: docs/user/device_support.md
translation_date: 2026-04-01
translation_source_hash: e2126f6f5db7
---

# Geräteunterstützung

Diese Anleitung erklärt, wie aiohomematic Homematic-Geräte unterstützt und was zu tun ist, wenn ein Gerät nicht wie erwartet funktioniert.

## Generischer Ansatz

aiohomematic verwendet einen **generischen Ansatz** zur Geräteunterstützung:

1. **Alle Geräte werden unterstützt** - Jedes Homematic-Gerät erzeugt automatisch Entities basierend auf seinen Parametern
2. **Keine Geräteliste erforderlich** - Neue Geräte funktionieren sofort ohne Bibliotheks-Updates
3. **Benutzerdefinierte Zuordnungen erweitern** - Komplexe Geräte erhalten zusätzliche Funktionen durch benutzerdefinierte Zuordnungen

### So funktioniert es

```
CCU Device → Parameter Discovery → Entity Creation
     ↓              ↓                    ↓
  HmIP-eTRV    ACTUAL_TEMPERATURE    sensor.temperature
               SET_POINT_TEMPERATURE  climate entity
               VALVE_STATE           sensor.valve
               BATTERY_STATE         sensor.battery
```

Wenn ein Gerät zur CCU hinzugefügt wird:

1. Die Integration liest die **Parameterbeschreibungen** des Geräts von der CCU
2. Jeder Parameter wird zu einer Entity (Sensor, Schalter, Nummer usw.)
3. Parameter werden basierend auf ihren Eigenschaften den passenden Entity-Typen zugeordnet

## Entity-Typen

Parameter werden automatisch Home Assistant Entity-Typen zugeordnet:

| Parametertyp               | Entity-Typ    | Beispiel             |
| -------------------------- | ------------- | -------------------- |
| Boolean (nur lesbar)       | Binary Sensor | `WINDOW_STATE`       |
| Boolean (schreibbar)       | Switch        | `STATE`              |
| Float/Integer (nur lesbar) | Sensor        | `ACTUAL_TEMPERATURE` |
| Float/Integer (schreibbar) | Number        | `LEVEL`              |
| Enum (nur lesbar)          | Sensor        | `ERROR_CODE`         |
| Enum (schreibbar)          | Select        | `OPERATING_MODE`     |
| Action                     | Button        | `PRESS_SHORT`        |

## Benutzerdefinierte Zuordnungen

Einige Geräte profitieren von **benutzerdefinierten Zuordnungen**, die mehrere Parameter zu einer einzigen, umfassenderen Entity kombinieren:

| Gerätetyp  | Benutzerdefinierte Entity | Kombinierte Parameter                                       |
| ---------- | ------------------------- | ----------------------------------------------------------- |
| Thermostat | Climate                   | SET_POINT_TEMPERATURE, ACTUAL_TEMPERATURE, VALVE_STATE usw. |
| Dimmer     | Light                     | LEVEL, ON_TIME, RAMP_TIME                                   |
| Jalousie   | Cover                     | LEVEL, STOP, WORKING                                        |
| Schloss    | Lock                      | LOCK_STATE, LOCK_TARGET_LEVEL, ERROR                        |

### Vorteile benutzerdefinierter Zuordnungen

- **Bessere Benutzererfahrung** - Eine einzelne Climate-Karte statt mehrerer Sensoren
- **Passende Aktionen** - `climate.set_temperature` statt direkter Parameterschreibvorgänge
- **Statuszusammenfassung** - Kombinierte Verfügbarkeit und Fehlerbehandlung

## Details zu Cover-Geräten

Cover-Geräte werden der Home Assistant `cover`-Plattform zugeordnet. Verschiedene Gerätetypen bieten unterschiedliche Fähigkeiten, die über `CoverCapabilities` gemeldet werden:

### Cover-Typen und Fähigkeiten

| Gerätetyp                                      | Klasse                | Position | Neigung | Stopp | Lüftung | HA device_class |
| ---------------------------------------------- | --------------------- | -------- | ------- | ----- | ------- | --------------- |
| RF-Rollläden (HM-LC-Bl1-\*)                    | `CustomDpCover`       | ja       | nein    | ja    | nein    | `shutter`       |
| IP-Rollläden (HmIP-BROLL, HmIP-FROLL)          | `CustomDpCover`       | ja       | nein    | ja    | nein    | `shutter`       |
| RF-Jalousien (HM-LC-Ja1PBU-FM)                 | `CustomDpBlind`       | ja       | ja      | ja    | nein    | `blind`         |
| IP-Jalousien (HmIP-BBL, HmIP-FBL, HmIP-DRBLI4) | `CustomDpIpBlind`     | ja       | ja      | ja    | nein    | `blind`         |
| Fensterantrieb (HM-Sec-Win)                    | `CustomDpWindowDrive` | ja       | nein    | ja    | nein    | `window`        |
| Garagentor (HmIP-MOD-HO, HmIP-MOD-TM)          | `CustomDpGarage`      | ja       | nein    | ja    | ja      | `garage`        |

### Fähigkeiten prüfen

Integrationen sollten `capabilities` anstelle von `isinstance()`-Prüfungen verwenden:

```python
cover = get_custom_data_point(device, channel_no)

if cover.capabilities.tilt:
    # Jalousie mit Neigungsunterstützung
    await cover.open_tilt()

if cover.capabilities.vent:
    # Garagentor mit Lueftungsposition
    await cover.vent()
```

### Besonderheiten bei Garagentoren

Garagentore (HmIP-MOD-HO, HmIP-MOD-TM) unterscheiden sich grundlegend von anderen Cover-Typen:

**Diskrete Zustände statt kontinuierlicher Position.** Während Rollläden und Jalousien einen kontinuierlichen Positionsbereich (0-100%) haben, besitzen Garagentore nur drei diskrete Zustände:

| Zustand              | Zugeordnete Position | Beschreibung                    |
| -------------------- | -------------------- | ------------------------------- |
| CLOSED               | 0                    | Tor vollständig geschlossen     |
| VENTILATION_POSITION | 10                   | Tor leicht geöffnet zur Lüftung |
| OPEN                 | 100                  | Tor vollständig geöffnet        |

**Asymmetrische Lese-/Schreibparameter.** Der Gerätezustand wird aus `DOOR_STATE` und `SECTION` gelesen, während Befehle an `DOOR_COMMAND` gesendet werden. Die verfügbaren Befehle sind:

| Befehl       | Beschreibung               |
| ------------ | -------------------------- |
| OPEN         | Tor öffnen                 |
| CLOSE        | Tor schließen              |
| PARTIAL_OPEN | In Lüftungsposition fahren |
| STOP         | Bewegung stoppen           |
| NOP          | Keine Operation            |

**Verhalten des Positionsreglers.** Da die Home Assistant Cover-Plattform kein natives Konzept für eine Lüftungsposition hat, ordnet das Garagentor seine drei Zustände diskreten Positionswerten (0/10/100) zu. Der Positionsregler in der Oberfläche hat daher drei effektive Bereiche:

- 0-10: Schließt das Tor
- 11-50: Fährt in Lüftungsposition
- 51-100: Öffnet das Tor

**Keine kontinuierliche Positionierung.** Das Setzen eines Positionswerts wie 75 bewegt das Tor nicht auf 75% geöffnet. Es wird dem nächsten diskreten Befehl zugeordnet (in diesem Fall OPEN).

## Parameterfilterung

**Nicht alle Parameter werden zu Entities.** Die Integration filtert Parameter, um einen übersichtlichen, nützlichen Satz von Entities bereitzustellen:

| Kategorie                     | Verhalten                                          |
| ----------------------------- | -------------------------------------------------- |
| **Allgemeine Parameter**      | Als Entities erstellt (aktiviert oder deaktiviert) |
| **Interne/Service-Parameter** | Standardmäßig nicht erstellt                       |
| **Wartungsparameter**         | Erstellt, aber standardmäßig deaktiviert           |

Diese Filterung verhindert, dass Hunderte technischer Parameter die Home Assistant-Instanz überladen.

### Deaktivierte Entities

Viele Entities werden **standardmäßig deaktiviert** erstellt, um das Dashboard nicht zu überladen:

- Signalstärke-Werte (RSSI_DEVICE, RSSI_PEER)
- Duty-Cycle-Informationen (DUTY_CYCLE)
- Gerätespezifische Diagnoseparameter

**Zum Aktivieren:**

1. Zu **Einstellungen** -> **Geräte & Dienste** navigieren
2. Das Gerät suchen
3. Auf deaktivierte Entities klicken
4. Die gewünschten aktivieren

### Versteckte Parameter hinzufügen (Unignore)

Wenn ein Parameter benötigt wird, der nicht als Entity erstellt wird, kann er über die Integrationskonfiguration **sichtbar gemacht** werden:

1. Zu **Einstellungen** -> **Geräte & Dienste** -> **Homematic(IP) Local** navigieren
2. Auf **Konfigurieren** klicken -> zur Seite **Schnittstelle** navigieren
3. **Erweiterte Konfiguration** aktivieren
4. Das Parametermuster zur **un_ignore**-Liste hinzufügen (z.B. `*:*:RSSI_PEER`)

Siehe [Unignore-Parameter](advanced/unignore.md) für detaillierte Anweisungen und Musterbeispiele.

## Wenn Geräte nicht wie erwartet funktionieren

### Neues Gerätemodell

Bei einem brandneuen Gerätemodell:

1. **Prüfen, ob es überhaupt funktioniert** - Werden grundlegende Entities erstellt?
2. **CCU-Kopplung überprüfen** - Funktioniert das Gerät in der CCU-Weboberfläche?
3. **Auf Updates prüfen** - aiohomematic und die Integration aktualisieren

### Fehlende benutzerdefinierte Zuordnung

Wenn ein Gerät funktioniert, aber keine passende benutzerdefinierte Entity hat (z.B. rohe Sensoren statt einer Climate-Entity):

1. **Gerätedefinition exportieren:**

   ```yaml
   action: homematicip_local.export_device_definition
   data:
     device_id: YOUR_DEVICE_ID
   ```

2. **Ein Issue eröffnen** auf [GitHub](https://github.com/sukramj/aiohomematic/issues) mit:
   - Gerätemodell (z.B. HmIP-eTRV-2)
   - Die exportierte ZIP-Datei
   - Beschreibung des erwarteten Verhaltens

### Falscher Entity-Typ

Wenn ein Parameter dem falschen Entity-Typ zugeordnet ist:

- Dies ist normalerweise beabsichtigt, basierend auf den Eigenschaften des Parameters
- Bei Bedarf die Entity-Anpassung von Home Assistant verwenden
- Melden, wenn es sich um einen Fehler handeln könnte

## Generische Entities verwenden

Auch ohne benutzerdefinierte Zuordnungen kann jedes Gerät gesteuert werden:

### Werte lesen

```yaml
# Read any parameter
action: homematicip_local.get_device_value
data:
  device_id: YOUR_DEVICE_ID
  channel: 1
  parameter: ACTUAL_TEMPERATURE
```

### Werte schreiben

```yaml
# Write any parameter
action: homematicip_local.set_device_value
data:
  device_id: YOUR_DEVICE_ID
  channel: 1
  parameter: SET_POINT_TEMPERATURE
  value: "21.0"
  value_type: double
```

### Paramsets

```yaml
# Read complete paramset
action: homematicip_local.get_paramset
data:
  device_id: YOUR_DEVICE_ID
  channel: 1
  paramset_key: VALUES
```

## Gerätekategorien

### Vollständig unterstützt (benutzerdefinierte Zuordnung)

Diese Gerätetypen verfügen über vollständige benutzerdefinierte Entity-Unterstützung:

- **Climate** - Thermostate, Wandthermostate, Heizungsgruppen
- **Cover** - Jalousien, Rollläden, Garagentore
- **Light** - Dimmer, Schalter mit Helligkeit
- **Lock** - Türschlösser
- **Siren** - Alarmsirenen, MP3-Player
- **Switch** - Alle Schaltertypen

### Generische Unterstützung (automatische Erkennung)

Alle anderen Geräte funktionieren über generische Entity-Erstellung:

- Wetterstationen
- Energiezähler
- Bewegungsmelder
- Tür-/Fensterkontakte
- Rauchmelder
- Wassersensoren
- Und alle zukünftigen Geräte

## Siehe auch

- [Erweiterungspunkte](../developer/extension_points.md) - Für Entwickler, die benutzerdefinierte Zuordnungen hinzufügen
- [Actions-Referenz](features/homeassistant_actions.md) - Direkter Gerätezugriff
- [Unignore-Parameter](advanced/unignore.md) - Zugriff auf versteckte Parameter
