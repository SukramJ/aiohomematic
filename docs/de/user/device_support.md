---
translation_source: docs/user/device_support.md
translation_date: 2026-04-01
translation_source_hash: e2126f6f5db7
---

# Geraeteunterstuetzung

Diese Anleitung erklaert, wie aiohomematic Homematic-Geraete unterstuetzt und was zu tun ist, wenn ein Geraet nicht wie erwartet funktioniert.

## Generischer Ansatz

aiohomematic verwendet einen **generischen Ansatz** zur Geraeteunterstuetzung:

1. **Alle Geraete werden unterstuetzt** - Jedes Homematic-Geraet erzeugt automatisch Entities basierend auf seinen Parametern
2. **Keine Geraetliste erforderlich** - Neue Geraete funktionieren sofort ohne Bibliotheks-Updates
3. **Benutzerdefinierte Zuordnungen erweitern** - Komplexe Geraete erhalten zusaetzliche Funktionen durch benutzerdefinierte Zuordnungen

### So funktioniert es

```
CCU Device → Parameter Discovery → Entity Creation
     ↓              ↓                    ↓
  HmIP-eTRV    ACTUAL_TEMPERATURE    sensor.temperature
               SET_POINT_TEMPERATURE  climate entity
               VALVE_STATE           sensor.valve
               BATTERY_STATE         sensor.battery
```

Wenn ein Geraet zur CCU hinzugefuegt wird:

1. Die Integration liest die **Parameterbeschreibungen** des Geraets von der CCU
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

Einige Geraete profitieren von **benutzerdefinierten Zuordnungen**, die mehrere Parameter zu einer einzigen, umfassenderen Entity kombinieren:

| Geraetetyp | Benutzerdefinierte Entity | Kombinierte Parameter                                       |
| ---------- | ------------------------- | ----------------------------------------------------------- |
| Thermostat | Climate                   | SET_POINT_TEMPERATURE, ACTUAL_TEMPERATURE, VALVE_STATE usw. |
| Dimmer     | Light                     | LEVEL, ON_TIME, RAMP_TIME                                   |
| Jalousie   | Cover                     | LEVEL, STOP, WORKING                                        |
| Schloss    | Lock                      | LOCK_STATE, LOCK_TARGET_LEVEL, ERROR                        |

### Vorteile benutzerdefinierter Zuordnungen

- **Bessere Benutzererfahrung** - Eine einzelne Climate-Karte statt mehrerer Sensoren
- **Passende Aktionen** - `climate.set_temperature` statt direkter Parameterschreibvorgaenge
- **Statuszusammenfassung** - Kombinierte Verfuegbarkeit und Fehlerbehandlung

## Details zu Cover-Geraeten

Cover-Geraete werden der Home Assistant `cover`-Plattform zugeordnet. Verschiedene Geraetetypen bieten unterschiedliche Faehigkeiten, die ueber `CoverCapabilities` gemeldet werden:

### Cover-Typen und Faehigkeiten

| Geraetetyp                                     | Klasse                | Position | Neigung | Stopp | Lueftung | HA device_class |
| ---------------------------------------------- | --------------------- | -------- | ------- | ----- | -------- | --------------- |
| RF-Rolllaeden (HM-LC-Bl1-\*)                   | `CustomDpCover`       | ja       | nein    | ja    | nein     | `shutter`       |
| IP-Rolllaeden (HmIP-BROLL, HmIP-FROLL)         | `CustomDpCover`       | ja       | nein    | ja    | nein     | `shutter`       |
| RF-Jalousien (HM-LC-Ja1PBU-FM)                 | `CustomDpBlind`       | ja       | ja      | ja    | nein     | `blind`         |
| IP-Jalousien (HmIP-BBL, HmIP-FBL, HmIP-DRBLI4) | `CustomDpIpBlind`     | ja       | ja      | ja    | nein     | `blind`         |
| Fensterantrieb (HM-Sec-Win)                    | `CustomDpWindowDrive` | ja       | nein    | ja    | nein     | `window`        |
| Garagentor (HmIP-MOD-HO, HmIP-MOD-TM)          | `CustomDpGarage`      | ja       | nein    | ja    | ja       | `garage`        |

### Faehigkeiten pruefen

Integrationen sollten `capabilities` anstelle von `isinstance()`-Pruefungen verwenden:

```python
cover = get_custom_data_point(device, channel_no)

if cover.capabilities.tilt:
    # Jalousie mit Neigungsunterstuetzung
    await cover.open_tilt()

if cover.capabilities.vent:
    # Garagentor mit Lueftungsposition
    await cover.vent()
```

### Besonderheiten bei Garagentoren

Garagentore (HmIP-MOD-HO, HmIP-MOD-TM) unterscheiden sich grundlegend von anderen Cover-Typen:

**Diskrete Zustaende statt kontinuierlicher Position.** Waehrend Rolllaeden und Jalousien einen kontinuierlichen Positionsbereich (0-100%) haben, besitzen Garagentore nur drei diskrete Zustaende:

| Zustand              | Zugeordnete Position | Beschreibung                      |
| -------------------- | -------------------- | --------------------------------- |
| CLOSED               | 0                    | Tor vollstaendig geschlossen      |
| VENTILATION_POSITION | 10                   | Tor leicht geoeffnet zur Lueftung |
| OPEN                 | 100                  | Tor vollstaendig geoeffnet        |

**Asymmetrische Lese-/Schreibparameter.** Der Geraetezustand wird aus `DOOR_STATE` und `SECTION` gelesen, waehrend Befehle an `DOOR_COMMAND` gesendet werden. Die verfuegbaren Befehle sind:

| Befehl       | Beschreibung                |
| ------------ | --------------------------- |
| OPEN         | Tor oeffnen                 |
| CLOSE        | Tor schliessen              |
| PARTIAL_OPEN | In Lueftungsposition fahren |
| STOP         | Bewegung stoppen            |
| NOP          | Keine Operation             |

**Verhalten des Positionsreglers.** Da die Home Assistant Cover-Plattform kein natives Konzept fuer eine Lueftungsposition hat, ordnet das Garagentor seine drei Zustaende diskreten Positionswerten (0/10/100) zu. Der Positionsregler in der Oberflaeche hat daher drei effektive Bereiche:

- 0-10: Schliesst das Tor
- 11-50: Faehrt in Lueftungsposition
- 51-100: Oeffnet das Tor

**Keine kontinuierliche Positionierung.** Das Setzen eines Positionswerts wie 75 bewegt das Tor nicht auf 75% geoeffnet. Es wird dem naechsten diskreten Befehl zugeordnet (in diesem Fall OPEN).

## Parameterfilterung

**Nicht alle Parameter werden zu Entities.** Die Integration filtert Parameter, um einen uebersichtlichen, nuetzlichen Satz von Entities bereitzustellen:

| Kategorie                     | Verhalten                                          |
| ----------------------------- | -------------------------------------------------- |
| **Allgemeine Parameter**      | Als Entities erstellt (aktiviert oder deaktiviert) |
| **Interne/Service-Parameter** | Standardmaessig nicht erstellt                     |
| **Wartungsparameter**         | Erstellt, aber standardmaessig deaktiviert         |

Diese Filterung verhindert, dass Hunderte technischer Parameter die Home Assistant-Instanz ueberladen.

### Deaktivierte Entities

Viele Entities werden **standardmaessig deaktiviert** erstellt, um das Dashboard nicht zu ueberladen:

- Signalstaerke-Werte (RSSI_DEVICE, RSSI_PEER)
- Duty-Cycle-Informationen (DUTY_CYCLE)
- Geraetespezifische Diagnoseparameter

**Zum Aktivieren:**

1. Zu **Einstellungen** -> **Geraete & Dienste** navigieren
2. Das Geraet suchen
3. Auf deaktivierte Entities klicken
4. Die gewuenschten aktivieren

### Versteckte Parameter hinzufuegen (Unignore)

Wenn ein Parameter benoetigt wird, der nicht als Entity erstellt wird, kann er ueber die Integrationskonfiguration **sichtbar gemacht** werden:

1. Zu **Einstellungen** -> **Geraete & Dienste** -> **Homematic(IP) Local** navigieren
2. Auf **Konfigurieren** klicken -> zur Seite **Schnittstelle** navigieren
3. **Erweiterte Konfiguration** aktivieren
4. Das Parametermuster zur **un_ignore**-Liste hinzufuegen (z.B. `*:*:RSSI_PEER`)

Siehe [Unignore-Parameter](advanced/unignore.md) fuer detaillierte Anweisungen und Musterbeispiele.

## Wenn Geraete nicht wie erwartet funktionieren

### Neues Geraetemodell

Bei einem brandneuen Geraetemodell:

1. **Pruefen, ob es ueberhaupt funktioniert** - Werden grundlegende Entities erstellt?
2. **CCU-Kopplung ueberpruefen** - Funktioniert das Geraet in der CCU-Weboberflaeche?
3. **Auf Updates pruefen** - aiohomematic und die Integration aktualisieren

### Fehlende benutzerdefinierte Zuordnung

Wenn ein Geraet funktioniert, aber keine passende benutzerdefinierte Entity hat (z.B. rohe Sensoren statt einer Climate-Entity):

1. **Geraetedefinition exportieren:**

   ```yaml
   action: homematicip_local.export_device_definition
   data:
     device_id: YOUR_DEVICE_ID
   ```

2. **Ein Issue eroeffnen** auf [GitHub](https://github.com/sukramj/aiohomematic/issues) mit:
   - Geraetemodell (z.B. HmIP-eTRV-2)
   - Die exportierte ZIP-Datei
   - Beschreibung des erwarteten Verhaltens

### Falscher Entity-Typ

Wenn ein Parameter dem falschen Entity-Typ zugeordnet ist:

- Dies ist normalerweise beabsichtigt, basierend auf den Eigenschaften des Parameters
- Bei Bedarf die Entity-Anpassung von Home Assistant verwenden
- Melden, wenn es sich um einen Fehler handeln koennte

## Generische Entities verwenden

Auch ohne benutzerdefinierte Zuordnungen kann jedes Geraet gesteuert werden:

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

## Geraetekategorien

### Vollstaendig unterstuetzt (benutzerdefinierte Zuordnung)

Diese Geraetetypen verfuegen ueber vollstaendige benutzerdefinierte Entity-Unterstuetzung:

- **Climate** - Thermostate, Wandthermostate, Heizungsgruppen
- **Cover** - Jalousien, Rolllaeden, Garagentore
- **Light** - Dimmer, Schalter mit Helligkeit
- **Lock** - Tuerschloesser
- **Siren** - Alarmsirenen, MP3-Player
- **Switch** - Alle Schaltertypen

### Generische Unterstuetzung (automatische Erkennung)

Alle anderen Geraete funktionieren ueber generische Entity-Erstellung:

- Wetterstationen
- Energiezaehler
- Bewegungsmelder
- Tuer-/Fensterkontakte
- Rauchmelder
- Wassersensoren
- Und alle zukuenftigen Geraete

## Siehe auch

- [Erweiterungspunkte](../developer/extension_points.md) - Fuer Entwickler, die benutzerdefinierte Zuordnungen hinzufuegen
- [Actions-Referenz](features/homeassistant_actions.md) - Direkter Geraetezugriff
- [Unignore-Parameter](advanced/unignore.md) - Zugriff auf versteckte Parameter
