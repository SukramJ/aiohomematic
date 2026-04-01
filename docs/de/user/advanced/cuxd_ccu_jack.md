---
translation_source: docs/user/advanced/cuxd_ccu_jack.md
translation_date: 2026-04-01
translation_source_hash: 753ba50627ff
---

# CUxD und CCU-Jack Einrichtungsanleitung

Diese Anleitung beschreibt die Einrichtung und Fehlerbehebung von CUxD- und CCU-Jack-Schnittstellen mit der Homematic(IP) Local Integration.

## Was sind CUxD und CCU-Jack?

**CUxD** (CUx Daemon) und **CCU-Jack** sind Zusatzschnittstellen fuer die Homematic CCU, die erweiterte Funktionen bereitstellen:

- **CUxD**: Ermoeglicht die Integration von Nicht-Homematic-Geraeten (FS20, EnOcean usw.)
- **CCU-Jack**: Bietet eine alternative HTTP-API fuer den CCU-Zugriff

Beide verwenden ein grundlegend anderes Kommunikationsprotokoll als Standard-Homematic-Schnittstellen.

## Wesentliche Unterschiede zu Standardschnittstellen

| Aspekt         | Standard (HmIP-RF, BidCos-RF) | CUxD / CCU-Jack            |
| -------------- | ----------------------------- | -------------------------- |
| **Protokoll**  | XML-RPC                       | JSON-RPC                   |
| **Ports**      | 2001, 2010 usw.               | 80 (HTTP) oder 443 (HTTPS) |
| **Ereignisse** | Push (CCU sendet an HA)       | Polling oder MQTT          |
| **Keep-Alive** | Ping/Pong-Mechanismus         | Nicht unterstuetzt         |

**Wichtig**: CUxD- und CCU-Jack-Geraete aktualisieren sich moeglicherweise weniger haeufig als Standardgeraete, da sie auf Polling statt auf Push-Benachrichtigungen angewiesen sind.

## Einrichtung in Home Assistant

### Voraussetzungen

1. CUxD- oder CCU-Jack-Add-on auf der CCU installiert und gestartet
2. Homematic(IP) Local Integration in Home Assistant konfiguriert

### Konfiguration

CUxD und CCU-Jack muessen in der Integrationskonfiguration **manuell aktiviert** werden:

1. **Einstellungen** -> **Geraete & Dienste** oeffnen
2. Auf **Integration hinzufuegen** -> **Homematic(IP) Local** klicken
3. IP-Adresse und Zugangsdaten der CCU eingeben
4. In der Schnittstellenkonfiguration das Kontrollkaestchen **CUxD oder CCU-Jack aktivieren** setzen

**Hinweis**: Nur Standardschnittstellen (HmIP-RF, BidCos-RF usw.) werden automatisch erkannt. CUxD und CCU-Jack erfordern eine explizite Konfiguration.

**Es ist keine spezielle Portkonfiguration erforderlich** - diese Schnittstellen verwenden Standard-HTTP-Ports (80/443).

### Einrichtung ueberpruefen

Nach der Konfiguration Folgendes pruefen:

1. **Geraete & Dienste** -> **Homematic(IP) Local** -> **Konfigurieren**
2. CUxD/CCU-Jack sollte unter den Schnittstellen aufgefuehrt sein
3. Geraete sollten mit ihren Entitaeten angezeigt werden

## Ereignisaktualisierungen

### Standardverhalten (Polling)

Standardmaessig werden CUxD- und CCU-Jack-Geraete periodisch nach Aktualisierungen abgefragt. Das bedeutet:

- Geraetezustaende aktualisieren sich moeglicherweise langsamer (Polling-Intervall)
- Keine sofortigen Push-Benachrichtigungen von diesen Geraeten
- Die Verbindungsgesundheit wird ueber periodische Pruefungen ueberwacht

### Optional: MQTT-Integration

Fuer schnellere Aktualisierungen kann die MQTT-Bridge von CCU-Jack eingerichtet werden, um Ereignisse an Home Assistant weiterzuleiten:

**Hinweis**: CCU-Jack enthaelt einen eigenen MQTT-Broker. Fuer die Integration mit Home Assistant wird eine Bridge konfiguriert, um Ereignisse weiterzuleiten.

1. **CCU-Jack** auf der CCU installieren (falls noch nicht geschehen)
2. **MQTT-Broker** in Home Assistant einrichten (z. B. Mosquitto-App)
3. **CCU-Jack MQTT-Bridge** zum Weiterleiten von Ereignissen konfigurieren:
   - In `ccu-jack.cfg` den Wert `"MQTT.Bridge.Enable": true` setzen
   - Die Adresse des entfernten Brokers konfigurieren (der HA-Mosquitto)
   - Ausgehende Topics zum Weiterleiten von CCU-Datenpunkten definieren
   - Details in der [CCU-Jack MQTT-Bridge-Dokumentation](https://github.com/mdzio/ccu-jack/wiki/MQTT-Bridge)
4. **MQTT** in den Einstellungen der Homematic(IP) Local Integration aktivieren

Mit konfigurierter MQTT-Bridge werden Ereignisse von CCU-Jack-Geraeten an Home Assistant weitergeleitet, was nahezu sofortige Aktualisierungen statt Polling ermoeglicht.

## Fehlerbehebung

### Geraete werden nicht gefunden

| Symptom                     | Moegliche Ursache              | Loesung                                                        |
| --------------------------- | ------------------------------ | -------------------------------------------------------------- |
| Keine CUxD-Geraete sichtbar | CUxD-Add-on laeuft nicht       | CCU WebUI -> System -> Add-ons pruefen                         |
| "Verbindung abgelehnt"      | Schnittstelle nicht erreichbar | Pruefen, ob CUxD/CCU-Jack auf der CCU gestartet ist            |
| Authentifizierungsfehler    | Falsche Zugangsdaten           | Benutzername/Passwort in der Integrationskonfiguration pruefen |

### Geraete aktualisieren nie

| Symptom                          | Moegliche Ursache             | Loesung                                          |
| -------------------------------- | ----------------------------- | ------------------------------------------------ |
| Zustand aendert sich nie         | Polling erreicht Geraet nicht | CCU-Protokolle auf Fehler pruefen                |
| Aktualisierungen sehr verzoegert | Normal fuer CUxD              | MQTT fuer schnellere Aktualisierungen aktivieren |

### Debug-Protokollierung

**Einfachste Methode** - Ueber die Home Assistant UI aktivieren:

1. **Einstellungen** -> **Geraete & Dienste** -> **Homematic(IP) Local** oeffnen
2. Auf **Konfigurieren** -> **Debug-Protokollierung aktivieren** klicken
3. Das Problem reproduzieren
4. Auf **Debug-Protokollierung deaktivieren** klicken - das Debug-Protokoll wird als Dateidownload angeboten

**Alternative** - Ueber YAML-Konfiguration:

```yaml
logger:
  default: info
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

In den Protokollen auf Folgendes achten:

- Verbindungsstatus der Schnittstelle
- Geraeteerkennungsmeldungen
- Ereignisverarbeitung

### Konnektivitaet testen

Vom Home Assistant Host aus die HTTP-Konnektivitaet testen:

```bash
# Grundlegende HTTP-Konnektivitaet zur CCU testen
curl -v http://YOUR_CCU_IP/

# Sollte die CCU-Weboberflaeche zurueckgeben, nicht "Connection refused"
```

## Einschraenkungen

CUxD und CCU-Jack haben im Vergleich zu Standardschnittstellen einige Einschraenkungen:

| Funktion             | Unterstuetzt       |
| -------------------- | ------------------ |
| Geraetesteuerung     | Ja                 |
| Zustandsabfrage      | Ja                 |
| Push-Ereignisse      | Nein (nur Polling) |
| Ping/Pong-Keep-Alive | Nein               |
| Firmware-Updates     | Nein               |
| Geraeteverknuepfung  | Nein               |
| Systemvariablen      | Nein               |

## Empfohlene Vorgehensweisen

1. **Keine sofortigen Aktualisierungen erwarten** - CUxD-Geraete aktualisieren ueber Polling
2. **Automations-Timer verwenden** - Verzoegerungen fuer die Zustandsverifizierung einbauen
3. **MQTT aktivieren, wenn verfuegbar** - Bietet schnellere Ereigniszustellung
4. **Protokolle ueberwachen** - In den Debug-Protokollen auf Verbindungsprobleme achten

## Haeufige Missverstaendnisse

- **Falsch**: "Ich muss einen speziellen Port fuer CUxD konfigurieren"

  - **Richtig**: CUxD verwendet HTTP-Port 80/443, keine spezielle Konfiguration erforderlich

- **Falsch**: "CUxD sollte sofortige Updates wie HmIP-RF senden"

  - **Richtig**: CUxD verwendet standardmaessig Polling, Aktualisierungen koennen verzoegert sein

- **Falsch**: "Verbindungs-Timeout-Warnungen bedeuten, dass CUxD defekt ist"
  - **Richtig**: CUxD hat kein Ping/Pong; die Integration behandelt dies korrekt

## Siehe auch

- [Fehlerbehebungsanleitung](../troubleshooting/homeassistant_troubleshooting.md)
- [Actions-Referenz](../features/homeassistant_actions.md) - Fuer manuelle Geraetesteuerung
