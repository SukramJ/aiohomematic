---
translation_source: docs/user/troubleshooting/troubleshooting_flowchart.md
translation_date: 2026-04-01
translation_source_hash: 7f9005cf352d
---

# Fehlerbehebungs-Ablaufdiagramm

Diese visuelle Anleitung hilft bei der Diagnose und Behebung häufiger Probleme mit der Homematic(IP) Local-Integration.

## Schnelldiagnose

```mermaid
flowchart TD
    START([Problem erkannt]) --> Q1{Integration<br/>lädt?}

    Q1 -->|Nein| AUTH[Authentifizierung prüfen]
    Q1 -->|Ja| Q2{Geräte<br/>sichtbar?}

    AUTH --> A1[CCU-Zugangsdaten überprüfen]
    AUTH --> A2[CCU-Firewall prüfen]
    AUTH --> A3[Netzwerkverbindung testen]

    Q2 -->|Nein| DISC[Erkennung prüfen]
    Q2 -->|Ja| Q3{Entities<br/>aktualisieren sich?}

    DISC --> D1[Integration neu laden]
    DISC --> D2[CCU-Geräteliste prüfen]
    DISC --> D3[Schnittstellenkonfiguration überprüfen]

    Q3 -->|Nein| EVENTS[Ereignisse prüfen]
    Q3 -->|Ja| Q4{Actions<br/>funktionieren?}

    EVENTS --> E1[Debug-Logging aktivieren]
    EVENTS --> E2[Callback-Server prüfen]
    EVENTS --> E3[XML-RPC-Ports überprüfen]

    Q4 -->|Nein| ACTIONS[Actions prüfen]
    Q4 -->|Ja| DONE([System OK])

    ACTIONS --> C1[Entity-Zustand prüfen]
    ACTIONS --> C2[Gerät-Erreichbarkeit überprüfen]
    ACTIONS --> C3[CCU-Programme prüfen]
```

## Verbindungsprobleme

```mermaid
flowchart TD
    CONN([Verbindungsproblem]) --> Q1{CCU-IP<br/>pingbar?}

    Q1 -->|Nein| NET[Netzwerkproblem]
    Q1 -->|Ja| Q2{CCU-Weboberfläche<br/>erreichbar?}

    NET --> N1[IP-Adresse prüfen]
    NET --> N2[Netzwerk/VLAN prüfen]
    NET --> N3[Firewall-Regeln prüfen]

    Q2 -->|Nein| CCU[CCU-Problem]
    Q2 -->|Ja| Q3{Integration<br/>verbindet?}

    CCU --> C1[CCU neu starten]
    CCU --> C2[CCU-Dienste prüfen]
    CCU --> C3[CCU-Logs prüfen]

    Q3 -->|Nein| PORTS[Port-Problem]
    Q3 -->|Ja| DONE([Verbindung OK])

    PORTS --> P1[Ports 2001/2010 prüfen]
    PORTS --> P2[HA-Firewall prüfen]
    PORTS --> P3[Andere Schnittstelle versuchen]
```

## Probleme bei Entity-Aktualisierungen

```mermaid
flowchart TD
    UPDATE([Entities aktualisieren sich nicht]) --> Q1{Welche<br/>Schnittstelle?}

    Q1 -->|HmIP-RF/BidCos| XML[XML-RPC-Pruefung]
    Q1 -->|CUxD/CCU-Jack| JSON[JSON-RPC-Pruefung]

    XML --> X1{Callback-<br/>Server OK?}
    X1 -->|Nein| X2[HA-Netzwerkkonfiguration prüfen]
    X1 -->|Ja| X3{Ereignisse<br/>in Logs?}
    X3 -->|Nein| X4[CCU-Callback-Registrierung prüfen]
    X3 -->|Ja| X5[Entity-Abonnement prüfen]

    JSON --> J1{Polling<br/>aktiv?}
    J1 -->|Nein| J2[Integrationskonfiguration prüfen]
    J1 -->|Ja| J3{MQTT<br/>aktiviert?}
    J3 -->|Nein| J4[Aktualisierungen können verzögert sein - normal]
    J3 -->|Ja| J5[MQTT-Broker prüfen]
```

## Gerätespezifische Probleme

```mermaid
flowchart TD
    DEVICE([Geräteproblem]) --> Q1{Gerät in<br/>CCU-Weboberfläche?}

    Q1 -->|Nein| PAIR[Kopplungsproblem]
    Q1 -->|Ja| Q2{Gerät in<br/>Home Assistant?}

    PAIR --> PA1[Gerät erneut mit CCU koppeln]
    PAIR --> PA2[CCU-Posteingang prüfen]
    PAIR --> PA3[Gerät auf Werkseinstellungen zurücksetzen]

    Q2 -->|Nein| DISC[Erkennungsproblem]
    Q2 -->|Ja| Q3{Korrekter<br/>Entity-Typ?}

    DISC --> DI1[Integration neu laden]
    DISC --> DI2[Geräteausschlüsse prüfen]
    DISC --> DI3[Gerätedefinition exportieren]

    Q3 -->|Nein| TYPE[Entity-Typ-Problem]
    Q3 -->|Ja| Q4{Werte<br/>korrekt?}

    TYPE --> T1[Benutzerdefinierte Zuordnung prüfen]
    TYPE --> T2[Auf GitHub melden]

    Q4 -->|Nein| VALUE[Werteproblem]
    Q4 -->|Ja| DONE([Gerät OK])

    VALUE --> V1[Parametersichtbarkeit prüfen]
    VALUE --> V2[Mit CCU-Weboberfläche vergleichen]
```

## Schritt-für-Schritt-Diagnose

### Schritt 1: Grundlegende Konnektivität überprüfen

1. **CCU anpingen**:

   ```bash
   ping YOUR_CCU_IP
   ```

2. **CCU-Weboberfläche aufrufen**: `http://YOUR_CCU_IP` im Browser öffnen

3. **HA-Logs auf Verbindungsfehler prüfen**:
   ```yaml
   logger:
     logs:
       aiohomematic: debug
   ```

### Schritt 2: Schnittstellenstatus prüfen

In Home Assistant:

1. Zu **Einstellungen** -> **Geräte & Dienste** navigieren
2. Auf **Homematic(IP) Local** -> **Konfigurieren** klicken
3. Schnittstellenstatus prüfen (verbunden/getrennt)

### Schritt 3: Ereignisfluss überprüfen

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

## Kurzreferenz häufiger Probleme

| Symptom                       | Wahrscheinliche Ursache               | Lösung                              |
| ----------------------------- | ------------------------------------- | ----------------------------------- |
| "Connection refused"          | CCU nicht erreichbar                  | Netzwerk und Firewall prüfen        |
| "Authentication failed"       | Falsche Zugangsdaten                  | Benutzername/Passwort überprüfen    |
| Entities zeigen "unavailable" | Verbindung unterbrochen               | CCU prüfen, Integration neu laden   |
| Keine Entity-Aktualisierungen | Callback funktioniert nicht           | HA-Netzwerkkonfiguration prüfen     |
| Falscher Entity-Typ           | Fehlende benutzerdefinierte Zuordnung | Auf GitHub melden                   |
| CUxD-Geräte langsam           | Normal bei Polling                    | MQTT-Einrichtung in Betracht ziehen |

## Debug-Log-Stufen

| Stufe     | Angezeigte Informationen                     | Verwendungszweck        |
| --------- | -------------------------------------------- | ----------------------- |
| `warning` | Fehler und Warnungen                         | Normalbetrieb           |
| `info`    | Verbindungsstatus, Ereignisse                | Einfache Fehlerbehebung |
| `debug`   | Alle RPC-Aufrufe, vollständige Ereignisdaten | Detaillierte Diagnose   |

### Debug-Logging aktivieren

**Einfachste Methode** - Über die Home Assistant-Oberfläche aktivieren:

1. Zu **Einstellungen** -> **Geräte & Dienste** -> **Homematic(IP) Local** navigieren
2. Auf **Konfigurieren** -> **Debug-Logging aktivieren** klicken
3. Das Problem reproduzieren
4. Auf **Debug-Logging deaktivieren** klicken - das Debug-Log wird als Datei zum Download angeboten

**Alternative** - Über YAML-Konfiguration:

```yaml
logger:
  default: warning
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

## Wann ein Issue eröffnet werden sollte

Ein GitHub-Issue eröffnen, wenn:

1. **Fehler**: Unerwartetes Verhalten nach Durchführung der Fehlerbehebungsschritte
2. **Fehlende Geräteunterstützung**: Gerät funktioniert in der CCU, aber nicht in HA
3. **Falscher Entity-Typ**: Gerät erzeugt falsche Entity (Sensor statt Schalter)

**Im Issue angeben**:

- [ ] Home Assistant-Version
- [ ] aiohomematic-Version
- [ ] CCU-Typ und Firmware
- [ ] Debug-Logs (sensible Informationen entfernen)
- [ ] Gerätedefinitions-Export (bei Geräteproblemen)

### Gerätedefinition exportieren

```yaml
action: homematicip_local.export_device_definition
data:
  device_id: YOUR_DEVICE_ID
```

## Siehe auch

- [Fehlerbehebungsanleitung](homeassistant_troubleshooting.md) - Detaillierte Fehlerbehebung
- [CUxD und CCU-Jack](../advanced/cuxd_ccu_jack.md) - Spezielle Schnittstellenbehandlung
- [Geräteunterstützung](../device_support.md) - Wie Geräte unterstützt werden
