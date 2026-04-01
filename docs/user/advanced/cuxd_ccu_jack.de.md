---
translation_source: docs/user/advanced/cuxd_ccu_jack.md
translation_date: 2026-04-01
translation_source_hash: 753ba50627ff
---

# CUxD und CCU-Jack Einrichtungsanleitung

Diese Anleitung beschreibt die Einrichtung und Fehlerbehebung von CUxD- und CCU-Jack-Schnittstellen mit der Homematic(IP) Local Integration.

## Was sind CUxD und CCU-Jack?

**CUxD** (CUx Daemon) und **CCU-Jack** sind Zusatzschnittstellen für die Homematic CCU, die erweiterte Funktionen bereitstellen:

- **CUxD**: Ermöglicht die Integration von Nicht-Homematic-Geräten (FS20, EnOcean usw.)
- **CCU-Jack**: Bietet eine alternative HTTP-API für den CCU-Zugriff

Beide verwenden ein grundlegend anderes Kommunikationsprotokoll als Standard-Homematic-Schnittstellen.

## Wesentliche Unterschiede zu Standardschnittstellen

| Aspekt         | Standard (HmIP-RF, BidCos-RF) | CUxD / CCU-Jack            |
| -------------- | ----------------------------- | -------------------------- |
| **Protokoll**  | XML-RPC                       | JSON-RPC                   |
| **Ports**      | 2001, 2010 usw.               | 80 (HTTP) oder 443 (HTTPS) |
| **Ereignisse** | Push (CCU sendet an HA)       | Polling oder MQTT          |
| **Keep-Alive** | Ping/Pong-Mechanismus         | Nicht unterstützt          |

**Wichtig**: CUxD- und CCU-Jack-Geräte aktualisieren sich möglicherweise weniger häufig als Standardgeräte, da sie auf Polling statt auf Push-Benachrichtigungen angewiesen sind.

## Einrichtung in Home Assistant

### Voraussetzungen

1. CUxD- oder CCU-Jack-Add-on auf der CCU installiert und gestartet
2. Homematic(IP) Local Integration in Home Assistant konfiguriert

### Konfiguration

CUxD und CCU-Jack müssen in der Integrationskonfiguration **manuell aktiviert** werden:

1. **Einstellungen** -> **Geräte & Dienste** öffnen
2. Auf **Integration hinzufügen** -> **Homematic(IP) Local** klicken
3. IP-Adresse und Zugangsdaten der CCU eingeben
4. In der Schnittstellenkonfiguration das Kontrollkästchen **CUxD oder CCU-Jack aktivieren** setzen

**Hinweis**: Nur Standardschnittstellen (HmIP-RF, BidCos-RF usw.) werden automatisch erkannt. CUxD und CCU-Jack erfordern eine explizite Konfiguration.

**Es ist keine spezielle Portkonfiguration erforderlich** - diese Schnittstellen verwenden Standard-HTTP-Ports (80/443).

### Einrichtung überprüfen

Nach der Konfiguration Folgendes prüfen:

1. **Geräte & Dienste** -> **Homematic(IP) Local** -> **Konfigurieren**
2. CUxD/CCU-Jack sollte unter den Schnittstellen aufgeführt sein
3. Geräte sollten mit ihren Entitäten angezeigt werden

## Ereignisaktualisierungen

### Standardverhalten (Polling)

Standardmäßig werden CUxD- und CCU-Jack-Geräte periodisch nach Aktualisierungen abgefragt. Das bedeutet:

- Gerätezustände aktualisieren sich möglicherweise langsamer (Polling-Intervall)
- Keine sofortigen Push-Benachrichtigungen von diesen Geräten
- Die Verbindungsgesundheit wird über periodische Prüfungen überwacht

### Optional: MQTT-Integration

Für schnellere Aktualisierungen kann die MQTT-Bridge von CCU-Jack eingerichtet werden, um Ereignisse an Home Assistant weiterzuleiten:

**Hinweis**: CCU-Jack enthält einen eigenen MQTT-Broker. Für die Integration mit Home Assistant wird eine Bridge konfiguriert, um Ereignisse weiterzuleiten.

1. **CCU-Jack** auf der CCU installieren (falls noch nicht geschehen)
2. **MQTT-Broker** in Home Assistant einrichten (z. B. Mosquitto-App)
3. **CCU-Jack MQTT-Bridge** zum Weiterleiten von Ereignissen konfigurieren:
   - In `ccu-jack.cfg` den Wert `"MQTT.Bridge.Enable": true` setzen
   - Die Adresse des entfernten Brokers konfigurieren (der HA-Mosquitto)
   - Ausgehende Topics zum Weiterleiten von CCU-Datenpunkten definieren
   - Details in der [CCU-Jack MQTT-Bridge-Dokumentation](https://github.com/mdzio/ccu-jack/wiki/MQTT-Bridge)
4. **MQTT** in den Einstellungen der Homematic(IP) Local Integration aktivieren

Mit konfigurierter MQTT-Bridge werden Ereignisse von CCU-Jack-Geräten an Home Assistant weitergeleitet, was nahezu sofortige Aktualisierungen statt Polling ermöglicht.

## Fehlerbehebung

### Geräte werden nicht gefunden

| Symptom                    | Mögliche Ursache               | Lösung                                                        |
| -------------------------- | ------------------------------ | ------------------------------------------------------------- |
| Keine CUxD-Geräte sichtbar | CUxD-Add-on läuft nicht        | CCU WebUI -> System -> Add-ons prüfen                         |
| "Verbindung abgelehnt"     | Schnittstelle nicht erreichbar | Prüfen, ob CUxD/CCU-Jack auf der CCU gestartet ist            |
| Authentifizierungsfehler   | Falsche Zugangsdaten           | Benutzername/Passwort in der Integrationskonfiguration prüfen |

### Geräte aktualisieren nie

| Symptom                         | Mögliche Ursache             | Lösung                                          |
| ------------------------------- | ---------------------------- | ----------------------------------------------- |
| Zustand ändert sich nie         | Polling erreicht Gerät nicht | CCU-Protokolle auf Fehler prüfen                |
| Aktualisierungen sehr verzögert | Normal für CUxD              | MQTT für schnellere Aktualisierungen aktivieren |

### Debug-Protokollierung

**Einfachste Methode** - Über die Home Assistant UI aktivieren:

1. **Einstellungen** -> **Geräte & Dienste** -> **Homematic(IP) Local** öffnen
2. Auf **Konfigurieren** -> **Debug-Protokollierung aktivieren** klicken
3. Das Problem reproduzieren
4. Auf **Debug-Protokollierung deaktivieren** klicken - das Debug-Protokoll wird als Dateidownload angeboten

**Alternative** - Über YAML-Konfiguration:

```yaml
logger:
  default: info
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

In den Protokollen auf Folgendes achten:

- Verbindungsstatus der Schnittstelle
- Geräteerkennungsmeldungen
- Ereignisverarbeitung

### Konnektivität testen

Vom Home Assistant Host aus die HTTP-Konnektivität testen:

```bash
# Grundlegende HTTP-Konnektivität zur CCU testen
curl -v http://YOUR_CCU_IP/

# Sollte die CCU-Weboberfläche zurückgeben, nicht "Connection refused"
```

## Einschränkungen

CUxD und CCU-Jack haben im Vergleich zu Standardschnittstellen einige Einschränkungen:

| Funktion             | Unterstützt        |
| -------------------- | ------------------ |
| Gerätesteuerung      | Ja                 |
| Zustandsabfrage      | Ja                 |
| Push-Ereignisse      | Nein (nur Polling) |
| Ping/Pong-Keep-Alive | Nein               |
| Firmware-Updates     | Nein               |
| Geräteverknüpfung    | Nein               |
| Systemvariablen      | Nein               |

## Empfohlene Vorgehensweisen

1. **Keine sofortigen Aktualisierungen erwarten** - CUxD-Geräte aktualisieren über Polling
2. **Automations-Timer verwenden** - Verzögerungen für die Zustandsverifizierung einbauen
3. **MQTT aktivieren, wenn verfügbar** - Bietet schnellere Ereigniszustellung
4. **Protokolle überwachen** - In den Debug-Protokollen auf Verbindungsprobleme achten

## Häufige Missverständnisse

- **Falsch**: "Ich muss einen speziellen Port für CUxD konfigurieren"

  - **Richtig**: CUxD verwendet HTTP-Port 80/443, keine spezielle Konfiguration erforderlich

- **Falsch**: "CUxD sollte sofortige Updates wie HmIP-RF senden"

  - **Richtig**: CUxD verwendet standardmäßig Polling, Aktualisierungen können verzögert sein

- **Falsch**: "Verbindungs-Timeout-Warnungen bedeuten, dass CUxD defekt ist"
  - **Richtig**: CUxD hat kein Ping/Pong; die Integration behandelt dies korrekt

## Siehe auch

- [Fehlerbehebungsanleitung](../troubleshooting/homeassistant_troubleshooting.md)
- [Actions-Referenz](../features/homeassistant_actions.md) - Für manuelle Gerätesteuerung
