---
translation_source: docs/user/troubleshooting/troubleshooting_flowchart.md
translation_date: 2026-04-01
translation_source_hash: 7f9005cf352d
---

# Fehlerbehebungs-Ablaufdiagramm

Diese visuelle Anleitung hilft bei der Diagnose und Behebung haeufiger Probleme mit der Homematic(IP) Local-Integration.

## Schnelldiagnose

```mermaid
flowchart TD
    START([Problem erkannt]) --> Q1{Integration<br/>laedt?}

    Q1 -->|Nein| AUTH[Authentifizierung pruefen]
    Q1 -->|Ja| Q2{Geraete<br/>sichtbar?}

    AUTH --> A1[CCU-Zugangsdaten ueberpruefen]
    AUTH --> A2[CCU-Firewall pruefen]
    AUTH --> A3[Netzwerkverbindung testen]

    Q2 -->|Nein| DISC[Erkennung pruefen]
    Q2 -->|Ja| Q3{Entities<br/>aktualisieren sich?}

    DISC --> D1[Integration neu laden]
    DISC --> D2[CCU-Geraetliste pruefen]
    DISC --> D3[Schnittstellenkonfiguration ueberpruefen]

    Q3 -->|Nein| EVENTS[Ereignisse pruefen]
    Q3 -->|Ja| Q4{Actions<br/>funktionieren?}

    EVENTS --> E1[Debug-Logging aktivieren]
    EVENTS --> E2[Callback-Server pruefen]
    EVENTS --> E3[XML-RPC-Ports ueberpruefen]

    Q4 -->|Nein| ACTIONS[Actions pruefen]
    Q4 -->|Ja| DONE([System OK])

    ACTIONS --> C1[Entity-Zustand pruefen]
    ACTIONS --> C2[Geraet-Erreichbarkeit ueberpruefen]
    ACTIONS --> C3[CCU-Programme pruefen]
```

## Verbindungsprobleme

```mermaid
flowchart TD
    CONN([Verbindungsproblem]) --> Q1{CCU-IP<br/>pingbar?}

    Q1 -->|Nein| NET[Netzwerkproblem]
    Q1 -->|Ja| Q2{CCU-Weboberflaeche<br/>erreichbar?}

    NET --> N1[IP-Adresse pruefen]
    NET --> N2[Netzwerk/VLAN pruefen]
    NET --> N3[Firewall-Regeln pruefen]

    Q2 -->|Nein| CCU[CCU-Problem]
    Q2 -->|Ja| Q3{Integration<br/>verbindet?}

    CCU --> C1[CCU neu starten]
    CCU --> C2[CCU-Dienste pruefen]
    CCU --> C3[CCU-Logs pruefen]

    Q3 -->|Nein| PORTS[Port-Problem]
    Q3 -->|Ja| DONE([Verbindung OK])

    PORTS --> P1[Ports 2001/2010 pruefen]
    PORTS --> P2[HA-Firewall pruefen]
    PORTS --> P3[Andere Schnittstelle versuchen]
```

## Probleme bei Entity-Aktualisierungen

```mermaid
flowchart TD
    UPDATE([Entities aktualisieren sich nicht]) --> Q1{Welche<br/>Schnittstelle?}

    Q1 -->|HmIP-RF/BidCos| XML[XML-RPC-Pruefung]
    Q1 -->|CUxD/CCU-Jack| JSON[JSON-RPC-Pruefung]

    XML --> X1{Callback-<br/>Server OK?}
    X1 -->|Nein| X2[HA-Netzwerkkonfiguration pruefen]
    X1 -->|Ja| X3{Ereignisse<br/>in Logs?}
    X3 -->|Nein| X4[CCU-Callback-Registrierung pruefen]
    X3 -->|Ja| X5[Entity-Abonnement pruefen]

    JSON --> J1{Polling<br/>aktiv?}
    J1 -->|Nein| J2[Integrationskonfiguration pruefen]
    J1 -->|Ja| J3{MQTT<br/>aktiviert?}
    J3 -->|Nein| J4[Aktualisierungen koennen verzoegert sein - normal]
    J3 -->|Ja| J5[MQTT-Broker pruefen]
```

## Geraetespezifische Probleme

```mermaid
flowchart TD
    DEVICE([Geraeteproblem]) --> Q1{Geraet in<br/>CCU-Weboberflaeche?}

    Q1 -->|Nein| PAIR[Kopplungsproblem]
    Q1 -->|Ja| Q2{Geraet in<br/>Home Assistant?}

    PAIR --> PA1[Geraet erneut mit CCU koppeln]
    PAIR --> PA2[CCU-Posteingang pruefen]
    PAIR --> PA3[Geraet auf Werkseinstellungen zuruecksetzen]

    Q2 -->|Nein| DISC[Erkennungsproblem]
    Q2 -->|Ja| Q3{Korrekter<br/>Entity-Typ?}

    DISC --> DI1[Integration neu laden]
    DISC --> DI2[Geraeteausschluesse pruefen]
    DISC --> DI3[Geraetedefinition exportieren]

    Q3 -->|Nein| TYPE[Entity-Typ-Problem]
    Q3 -->|Ja| Q4{Werte<br/>korrekt?}

    TYPE --> T1[Benutzerdefinierte Zuordnung pruefen]
    TYPE --> T2[Auf GitHub melden]

    Q4 -->|Nein| VALUE[Werteproblem]
    Q4 -->|Ja| DONE([Geraet OK])

    VALUE --> V1[Parametersichtbarkeit pruefen]
    VALUE --> V2[Mit CCU-Weboberflaeche vergleichen]
```

## Schritt-fuer-Schritt-Diagnose

### Schritt 1: Grundlegende Konnektivitaet ueberpruefen

1. **CCU anpingen**:

   ```bash
   ping YOUR_CCU_IP
   ```

2. **CCU-Weboberflaeche aufrufen**: `http://YOUR_CCU_IP` im Browser oeffnen

3. **HA-Logs auf Verbindungsfehler pruefen**:
   ```yaml
   logger:
     logs:
       aiohomematic: debug
   ```

### Schritt 2: Schnittstellenstatus pruefen

In Home Assistant:

1. Zu **Einstellungen** -> **Geraete & Dienste** navigieren
2. Auf **Homematic(IP) Local** -> **Konfigurieren** klicken
3. Schnittstellenstatus pruefen (verbunden/getrennt)

### Schritt 3: Ereignisfluss ueberpruefen

Debug-Logging aktivieren und nach Folgendem suchen:

```
# Gut - Ereignisse kommen an
Received event: interface=HmIP-RF channel=XXXX:1 parameter=STATE value=True

# Schlecht - Keine Ereignisse
No events received for 180 seconds
```

### Schritt 4: Actions testen

Eine einfache Action in Entwicklerwerkzeuge -> Dienste ausprobieren:

```yaml
action: homematicip_local.set_device_value
data:
  device_id: YOUR_DEVICE_ID
  channel: 1
  parameter: STATE
  value: "true"
  value_type: boolean
```

## Kurzreferenz haeufiger Probleme

| Symptom                       | Wahrscheinliche Ursache               | Loesung                             |
| ----------------------------- | ------------------------------------- | ----------------------------------- |
| "Connection refused"          | CCU nicht erreichbar                  | Netzwerk und Firewall pruefen       |
| "Authentication failed"       | Falsche Zugangsdaten                  | Benutzername/Passwort ueberpruefen  |
| Entities zeigen "unavailable" | Verbindung unterbrochen               | CCU pruefen, Integration neu laden  |
| Keine Entity-Aktualisierungen | Callback funktioniert nicht           | HA-Netzwerkkonfiguration pruefen    |
| Falscher Entity-Typ           | Fehlende benutzerdefinierte Zuordnung | Auf GitHub melden                   |
| CUxD-Geraete langsam          | Normal bei Polling                    | MQTT-Einrichtung in Betracht ziehen |

## Debug-Log-Stufen

| Stufe     | Angezeigte Informationen                      | Verwendungszweck        |
| --------- | --------------------------------------------- | ----------------------- |
| `warning` | Fehler und Warnungen                          | Normalbetrieb           |
| `info`    | Verbindungsstatus, Ereignisse                 | Einfache Fehlerbehebung |
| `debug`   | Alle RPC-Aufrufe, vollstaendige Ereignisdaten | Detaillierte Diagnose   |

### Debug-Logging aktivieren

**Einfachste Methode** - Ueber die Home Assistant-Oberflaeche aktivieren:

1. Zu **Einstellungen** -> **Geraete & Dienste** -> **Homematic(IP) Local** navigieren
2. Auf **Konfigurieren** -> **Debug-Logging aktivieren** klicken
3. Das Problem reproduzieren
4. Auf **Debug-Logging deaktivieren** klicken - das Debug-Log wird als Datei zum Download angeboten

**Alternative** - Ueber YAML-Konfiguration:

```yaml
logger:
  default: warning
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

## Wann ein Issue eroeffnet werden sollte

Ein GitHub-Issue eroeffnen, wenn:

1. **Fehler**: Unerwartetes Verhalten nach Durchfuehrung der Fehlerbehebungsschritte
2. **Fehlende Geraeteunterstuetzung**: Geraet funktioniert in der CCU, aber nicht in HA
3. **Falscher Entity-Typ**: Geraet erzeugt falsche Entity (Sensor statt Schalter)

**Im Issue angeben**:

- [ ] Home Assistant-Version
- [ ] aiohomematic-Version
- [ ] CCU-Typ und Firmware
- [ ] Debug-Logs (sensible Informationen entfernen)
- [ ] Geraetedefinitions-Export (bei Geraeteproblemen)

### Geraetedefinition exportieren

```yaml
action: homematicip_local.export_device_definition
data:
  device_id: YOUR_DEVICE_ID
```

## Siehe auch

- [Fehlerbehebungsanleitung](homeassistant_troubleshooting.md) - Detaillierte Fehlerbehebung
- [CUxD und CCU-Jack](../advanced/cuxd_ccu_jack.md) - Spezielle Schnittstellenbehandlung
- [Geraeteunterstuetzung](../device_support.md) - Wie Geraete unterstuetzt werden
