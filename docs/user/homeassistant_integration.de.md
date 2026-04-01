---
translation_source: docs/user/homeassistant_integration.md
translation_date: 2026-04-01
translation_source_hash: d6940ae7d4e0
---

# Homematic(IP) Local for OpenCCU

Dies ist das umfassende Benutzerhandbuch für die **Homematic(IP) Local for OpenCCU** Home Assistant-Integration, die aiohomematic als Kernbibliothek verwendet.

## Schnellstart

- **Installation**: Über HACS (empfohlen) oder manuell
- **Dokumentation**: Dieses Handbuch + [aiohomematic-Dokumentation](../index.md)
- **Probleme**: [GitHub Issues](https://github.com/sukramj/aiohomematic/issues)
- **Diskussionen**: [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions)

## Auf einen Blick

- Lokale Home Assistant-Integration für Homematic(IP)-Zentralen (CCU2/3, OpenCCU, Debmatic, Homegear)
- Keine Cloud erforderlich - vollständig lokale Kommunikation
- XML-RPC für Steuerung und Push-Statusaktualisierungen; JSON-RPC für Namen und Räume
- Automatische Erkennung für CCU und kompatible Zentralen unterstützt
- Mindestanforderungen: Home Assistant 2025.10.0+

## Verwandte Integrationen

| Integration                                                                         | Anwendungsfall                             |
| ----------------------------------------------------------------------------------- | ------------------------------------------ |
| **Homematic(IP) Local for OpenCCU**                                                 | Lokale Steuerung über CCU/OpenCCU/Homegear |
| [Homematic(IP) Cloud](https://www.home-assistant.io/integrations/homematicip_cloud) | Cloud-Steuerung über Access Point          |
| [Homematic IP Local (HCU)](https://github.com/Ediminator/hacs-homematicip-hcu)      | Lokale Steuerung über HmIP-HCU1            |

---

## Installation

### HACS (empfohlen)

1. In Home Assistant zu **HACS** → **Integrations** → **Explore & Download Repositories** navigieren
2. Nach "Homematic(IP) Local for OpenCCU" suchen
3. Installieren und Home Assistant bei Aufforderung neu starten

### Manuelle Installation

1. `custom_components/homematicip_local` in das Home Assistant-Verzeichnis `config/custom_components` kopieren
2. Home Assistant neu starten

!!! warning "Manuelle Installation unterstützt keine automatischen Updates"

---

## Voraussetzungen

### Hardware

Diese Integration funktioniert mit jeder CCU-kompatiblen Homematic-Zentrale:

- CCU2/CCU3
- OpenCCU (ehemals RaspberryMatic)
- Debmatic
- Homegear
- Home Assistant OS/Supervised mit geeigneter App + Kommunikationsgerät

**Minimale CCU-Firmware:**

- CCU2: 2.61.x
- CCU3: 3.61.x

### Firewall und Ports

| Schnittstelle   | Zweck                      | Standard-Port | TLS-Port |
| --------------- | -------------------------- | ------------- | -------- |
| BidCos-RF       | Klassische Funkgeräte      | 2001          | 42001    |
| HomematicIP     | HmIP Funk- und Drahtgeräte | 2010          | 42010    |
| BidCos-Wired    | Klassische Drahtgeräte     | 2000          | 42000    |
| Virtual Devices | Thermostatgruppen          | 9292          | 49292    |
| JSON-RPC        | Namen und Räume            | 80            | 443      |

!!! note "XML-RPC Callback"
Die Integration startet einen lokalen XML-RPC-Server innerhalb von Home Assistant. Die CCU muss in der Lage sein, sich für Statusaktualisierungen mit diesem Server zu verbinden.

    **Docker-Nutzer**: `network_mode: host` verwenden oder `callback_host` und `callback_port_xml_rpc` in den erweiterten Optionen konfigurieren.

!!! info "Wie Callbacks funktionieren"
Die CCU sendet Geräteereignisse (Tastendruck, Temperaturwechsel usw.) per XML-RPC Callbacks an Home Assistant. Dazu muss die CCU HA auf einem bestimmten Port erreichen können. Wenn diese Verbindung fehlschlägt (Firewall, Docker-Netzwerk, falsche IP), funktionieren Befehle an Geräte weiterhin, aber Statusaktualisierungen kommen nicht mehr an.

### Authentifizierung

- Die Authentifizierung wird **immer** an die Homematic-Zentrale weitergeleitet
- **Empfohlen**: Authentifizierung für die XML-RPC-Kommunikation auf der CCU aktivieren (Einstellungen → Systemsteuerung → Sicherheit → Authentifizierung)
- Das Konto **muss Administratorrechte** haben
- Erlaubte Passwortzeichen: `A-Z`, `a-z`, `0-9` und `.!$():;#-`

!!! warning "Sonderzeichen"
Zeichen wie `ÄäÖöÜüß` funktionieren im CCU WebUI, werden aber von XML-RPC-Servern **nicht unterstützt**.

---

## Konfiguration

### Integration hinzufügen

[Integration hinzufügen](https://my.home-assistant.io/redirect/config_flow_start?domain=homematicip_local){ .md-button .md-button--primary }

Oder manuell:

1. Zu **Einstellungen** → **Geräte & Dienste** navigieren
2. **Integration hinzufügen** klicken
3. Nach "Homematic(IP) Local for OpenCCU" suchen

### Konfigurationsablauf

```
Schritt 1: CCU-Verbindung → Backend-Erkennung → Schritt 2: TLS & Schnittstellen → Abschluss oder Erweiterte Konfiguration
```

#### Schritt 1: CCU-Verbindung

| Einstellung      | Beschreibung                                        | Beispiel          |
| ---------------- | --------------------------------------------------- | ----------------- |
| **Instanzname**  | Eindeutiger Bezeichner (Kleinbuchstaben, a-z, 0-9)  | `ccu3`            |
| **Host**         | CCU-Hostname oder IP-Adresse                        | `192.168.1.50`    |
| **Benutzername** | Admin-Benutzername (Groß-/Kleinschreibung beachten) | `Admin`           |
| **Passwort**     | Admin-Passwort (Groß-/Kleinschreibung beachten)     | `MySecurePass123` |

!!! warning "Instanzname"
Der Instanzname ist ein eindeutiger Bezeichner für die HA-Installation bei der Kommunikation mit der CCU.

    - Er hat **keinen Bezug** zum Hostnamen der CCU
    - Die **IP-Adresse der CCU** kann jederzeit geändert werden
    - Der **Instanzname darf nach der Einrichtung nicht geändert** werden (Entities werden neu erstellt, Verlauf geht verloren)

    **Beispiel**: Es gibt zwei Home Assistant-Instanzen (Produktion und Test), die mit derselben CCU verbunden sind. Jede benötigt einen eindeutigen Instanznamen, damit die CCU Ereignisse an die richtige Callback-URL weiterleiten kann. Wenn beide denselben Namen verwenden, empfängt nur eine Instanz Ereignisse -- die andere erscheint als getrennt.

#### Automatische Backend-Erkennung

Nach Eingabe der Zugangsdaten erkennt die Integration automatisch:

- Backend-Typ (CCU2, CCU3, OpenCCU, Debmatic, Homegear)
- Verfügbare Schnittstellen (HmIP-RF, BidCos-RF, BidCos-Wired, Virtual Devices, CUxD, CCU-Jack)
- TLS-Konfiguration

#### Schritt 2: TLS & Schnittstellen

| Einstellung          | Standard     | Beschreibung                                                     |
| -------------------- | ------------ | ---------------------------------------------------------------- |
| **TLS verwenden**    | Auto-erkannt | Aktivieren, wenn die CCU HTTPS verwendet                         |
| **TLS verifizieren** | `false`      | Nur mit gültigem (nicht selbst-signiertem) Zertifikat aktivieren |

**Schnittstellenauswahl:**

| Schnittstelle         | Aktivieren wenn...                           |
| --------------------- | -------------------------------------------- |
| HomematicIP (HmIP-RF) | HomematicIP Funk- oder Drahtgeräte vorhanden |
| Homematic (BidCos-RF) | Klassische Homematic Funkgeräte vorhanden    |
| BidCos-Wired          | Klassische Homematic Drahtgeräte vorhanden   |
| Heizungsgruppen       | Thermostatgruppen in der CCU konfiguriert    |
| CUxD                  | CUxD Add-on installiert                      |
| CCU-Jack              | CCU-Jack-Software installiert                |

---

## Erweiterte Optionen

Zugriff über **Erweiterte Optionen konfigurieren** während der Einrichtung oder **Konfigurieren** nach der Einrichtung.

### Callback-Einstellungen (Docker/Netzwerk)

| Einstellung                 | Zweck                                       |
| --------------------------- | ------------------------------------------- |
| **Callback Host**           | IP-Adresse, über die die CCU HA erreicht    |
| **Callback Port (XML-RPC)** | Port für Statusaktualisierungen von der CCU |

!!! tip "Docker-Nutzer"
**Empfohlen**: `network_mode: host` verwenden

    **Alternative**: Callback Host auf die IP des Docker-Hosts setzen und Portweiterleitung konfigurieren

### Systemvariablen & Programme

| Einstellung                         | Standard | Beschreibung                                |
| ----------------------------------- | -------- | ------------------------------------------- |
| **Systemvariablen-Scan aktivieren** | `true`   | Systemvariablen von der CCU abrufen         |
| **Systemvariablen-Marker**          | Alle     | Filtern, welche Variablen importiert werden |
| **Programm-Scan aktivieren**        | `true`   | Programme von der CCU abrufen               |
| **Scan-Intervall**                  | 30s      | Abfrageintervall für Änderungen             |

**Marker:**

- **HAHM** - Erstellt beschreibbare Entities (Schalter, Auswahl, Nummer, Text)
- **MQTT** - Aktiviert Push-Updates über MQTT (erfordert CCU-Jack)
- **HX** - Benutzerdefinierter Marker für eigene Filterung
- **INTERNAL** - Schließt CCU-interne Variablen/Programme ein

### MQTT-Integration

| Einstellung         | Standard | Beschreibung                                          |
| ------------------- | -------- | ----------------------------------------------------- |
| **MQTT aktivieren** | `false`  | Für CCU-Jack- und CUxD-Callback-Ereignisse aktivieren |
| **MQTT-Präfix**     | _(leer)_ | MQTT-Präfix für die CCU-Jack-Bridge                   |

### Geräteverhalten

| Einstellung                                     | Standard | Beschreibung                                            |
| ----------------------------------------------- | -------- | ------------------------------------------------------- |
| **Sub-Geräte aktivieren**                       | `false`  | Geräte mit mehreren Kanalgruppen aufteilen              |
| **Gruppenkanal für Abdeckungsstatus verwenden** | `true`   | Gruppenkanal für Abdeckungsposition verwenden           |
| **Letzte Helligkeit wiederherstellen**          | `false`  | Leuchten schalten mit letzter Helligkeit statt 100% ein |

### Befehlsdrosselung

Steuert die minimale Verzögerung zwischen aufeinanderfolgenden Gerätebefehlen, die über jede Funkschnittstelle gesendet werden. Dies gewährleistet einen reibungslosen Betrieb und hilft, Paketverluste zu vermeiden, insbesondere bei Massenoperationen wie Automatisierungen, die viele Geräte gleichzeitig steuern (z.B. "alle Lichter aus").

| Einstellung                      | Standard | Bereich     | Beschreibung                                                            |
| -------------------------------- | -------- | ----------- | ----------------------------------------------------------------------- |
| **Befehlsdrosselungs-Intervall** | `0.1`s   | 0.0 - 5.0 s | Minimale Pause zwischen aufeinanderfolgenden Befehlen pro Schnittstelle |

Bei einem positiven Wert werden ausgehende Befehle (`set_value`, `put_paramset`) ratenbegrenzt, sodass mindestens die konfigurierte Anzahl von Sekunden zwischen aufeinanderfolgenden Befehlen auf derselben Funkschnittstelle vergeht. Jede Schnittstelle (HmIP-RF, BidCos-RF usw.) hat eine eigene unabhängige Drosselung. Auf `0.0` setzen, um die Drosselung vollständig zu deaktivieren.

!!! tip "Wann die Drosselung erhöhen"
Falls Befehle gelegentlich verloren gehen, wenn viele Geräte gleichzeitig gesteuert werden (z.B. eine "Gute Nacht"-Szene), das Drosselungsintervall erhöhen. Ein Wert von `0.5`s ist ein guter Ausgangspunkt für die meisten Installationen.

!!! note "Funk-Duty-Cycle"
Jede Homematic-Funkschnittstelle hat ein gesetzliches Limit für die nutzbare Sendezeit (Duty Cycle). Das Senden vieler Befehle in schneller Folge kann dieses Limit vorübergehend erschöpfen, sodass die CCU weitere Befehle ablehnt, bis sich der Duty Cycle erholt hat. Die Drosselung verteilt Befehle über die Zeit, um dieses Limit nicht zu erreichen.

---

## Systemvariablen & Programme

### Entity-Typen nach Variablentyp

| CCU-Typ      | Standard-Entity      | Mit HAHM-Marker          |
| ------------ | -------------------- | ------------------------ |
| Zeichenkette | `sensor` (nur lesen) | `text` (bearbeitbar)     |
| Werteliste   | `sensor` (nur lesen) | `select` (Dropdown)      |
| Zahl         | `sensor` (nur lesen) | `number` (Schieberegler) |
| Logikwert    | `binary_sensor`      | `switch` (umschaltbar)   |
| Alarm        | `binary_sensor`      | `switch` (umschaltbar)   |

### Variablen beschreibbar machen

`HAHM` zum Beschreibungsfeld der Variable in der CCU hinzufügen:

1. In der CCU die Systemvariable bearbeiten
2. Im Feld "Beschreibung" `HAHM` (Großbuchstaben) eintragen
3. Speichern und die Integration in HA neu laden

### Filtern mit Markern

Ohne Marker werden alle Variablen als **deaktivierte** Entities importiert. Mit in den erweiterten Optionen konfigurierten Markern werden nur markierte Variablen als **aktivierte** Entities importiert.

---

## Geräteunterstützung

Geräte werden integriert, indem verfügbare Parameter automatisch erkannt und passende Entities erstellt werden. Für komplexe Geräte (Thermostate, Abdeckungen) bieten benutzerdefinierte Zuordnungen eine bessere Darstellung.

### Deaktivierte Entities

Viele Entities werden anfänglich **deaktiviert** erstellt. Bei Bedarf in den erweiterten Einstellungen der Entity aktivieren.

### Fehlende Geräteunterstützung

Wenn ein neues Gerätemodell keine passenden benutzerdefinierten Entities hat:

1. Sicherstellen, dass das Gerät in der CCU funktioniert
2. Bei [aiohomematic Issues](https://github.com/sukramj/aiohomematic/issues) melden
3. Geräteexport beifügen (die Action `homematicip_local.export_device_definition` verwenden)

---

## Neue Geräte hinzufügen (Pairing)

### Anlernmodus

Die Integration stellt Buttons bereit, um den Anlernmodus zu aktivieren:

- **Anlernmodus HmIP-RF aktivieren** - Für HomematicIP-Geräte
- **Anlernmodus BidCos-RF aktivieren** - Für klassische Homematic-Geräte

Dauer-Sensoren zeigen die verbleibende Anlernzeit an.

### Reparatur-Benachrichtigungsprozess

Beim Anlernen eines neuen Geräts:

1. **Gerät** mit der CCU koppeln (über die CCU-Oberfläche)
2. **(Empfohlen) Gerät** in der CCU mit einem aussagekräftigen Namen benennen
3. **HA-Reparaturen prüfen** - Einstellungen → System → Reparaturen
4. **Gerät bestätigen oder benennen** im Reparaturdialog
5. Gerät und Entities werden mit korrekten Namen erstellt

!!! tip "Benennungsstrategie"
Geräte zuerst in der CCU benennen. Die Integration verwendet CCU-Namen, und es entstehen saubere Entity-IDs wie `sensor.wohnzimmer_thermostat_temperatur` statt `sensor.vcu1234567_temperature`.

### Posteingangs-Sensor

Der **Posteingangs**-Sensor zeigt Geräte an, die im CCU-Posteingang warten.

---

## Tastengeräte & Ereignisse

### Warum keine Tasten-Entities?

Physische Tasten haben keinen persistenten Zustand. Tastendrucke werden als **Ereignisse** behandelt, nicht als Entities.

### Tasten in Automatisierungen verwenden

1. Eine Automation erstellen
2. Auslösertyp: **Device**
3. Das Tastengerät auswählen
4. Den Auslöser wählen: "Taste 1 gedrückt", "Taste 2 lang gedrückt" usw.

### Tastenereignisse aktivieren (HomematicIP)

Für HomematicIP-Fernbedienungen (WRC2, WRC6, SPDR, KRC4, HM-PBI-4-FM):

**Option A - Action:**

```yaml
action: homematicip_local.create_central_links
target:
  device_id: YOUR_DEVICE_ID
```

**Option B - CCU-Oberfläche:**

1. CCU → Einstellungen → Geräte
2. "+" neben der Fernbedienung klicken
3. Den Tastenkanal anklicken → "aktivieren"

**Zum Deaktivieren:** `homematicip_local.remove_central_links` verwenden

---

## Ereignisse

### homematic.keypress

Wird bei einem Tastendruck ausgelöst. Mit Device-Triggern oder Event-Entities verwenden.

### homematic.device_availability

Wird ausgelöst, wenn ein Gerät nicht mehr erreichbar ist oder wieder erreichbar wird. Nützlich mit dem Blueprint für persistente Benachrichtigungen.

### homematic.device_error

Wird ausgelöst, wenn sich ein Gerät in einem Fehlerzustand befindet.

---

## Actions-Referenz

Siehe [Actions](features/homeassistant_actions.md) für die vollständige Action-Referenz einschließlich:

- Gerätewert-Operationen (`get_device_value`, `set_device_value`)
- Paramset-Operationen (`get_paramset`, `put_paramset`)
- Zeitplanverwaltung (`set_schedule`, `set_schedule_profile`, `copy_schedule`)
- Sirenensteuerung (`turn_on_siren`, `play_sound`)
- Systemvariablen (`get_variable_value`, `set_variable_value`)
- Und mehr...

---

## CUxD & CCU-Jack

### Kommunikationsmethoden

| Gerätetyp | Standard               | Mit MQTT           |
| --------- | ---------------------- | ------------------ |
| CUxD      | JSON-RPC-Polling (15s) | MQTT-Push (sofort) |
| CCU-Jack  | JSON-RPC-Polling (15s) | MQTT-Push (sofort) |

### MQTT einrichten

**Voraussetzungen:**

1. CCU-Jack auf der CCU installiert
2. HA mit MQTT-Broker verbunden
3. MQTT-Integration in HA konfiguriert

**Konfiguration:**

1. Erweiterte Optionen → MQTT aktivieren: `true`
2. MQTT-Präfix: _(für direkte Verbindung leer lassen)_

!!! note "Support-Richtlinie"
Abweichungen von CUxD/CCU-Jack gegenüber dem Verhalten der Original-Hardware werden **nicht als Fehler betrachtet**. Bei Bedarf HA-Templates zur Anpassung verwenden.

---

## Fehlerbehebung

### Schnell-Checkliste

| Prüfpunkt         | Vorgehensweise                                              |
| ----------------- | ----------------------------------------------------------- |
| HA-Logs geprüft   | Einstellungen → System → Logs → Filter: `homematicip_local` |
| Ports offen       | Mit Ping testen, Telnet auf Port 2010                       |
| CCU erreichbar    | CCU-Weboberfläche aufrufbar                                 |
| Admin-Benutzer    | Benutzer hat Administratorrechte                            |
| Gültiges Passwort | Nur erlaubte Zeichen verwendet                              |

### Docker-Probleme

| Problem                      | Lösung                                    |
| ---------------------------- | ----------------------------------------- |
| Keine Statusaktualisierungen | `callback_host` auf Docker-Host-IP setzen |
| Verbindung verweigert        | `network_mode: host` verwenden            |
| Konflikt mehrerer Instanzen  | Eindeutigen `instance_name` sicherstellen |

### Hilfe erhalten

1. Den [vollständigen Fehlerbehebungsleitfaden](troubleshooting/homeassistant_troubleshooting.md) lesen
2. [Bestehende Issues](https://github.com/sukramj/aiohomematic/issues) durchsuchen
3. In den [Diskussionen](https://github.com/sukramj/aiohomematic/discussions) fragen
4. Ein Issue eröffnen mit: HA-Version, Integrationsversion, CCU-Typ/Firmware, Logs, Schritte zur Reproduktion

---

## Häufige Fragen

**F: Entity zeigt "unavailable"**

Die Entity ist möglicherweise deaktiviert. Zu Einstellungen → Entities navigieren → Entity suchen → Aktivieren.

**F: Tastendrucke lösen keine Automation aus**

HomematicIP-Tasten benötigen Central Links. Siehe [Tastenereignisse aktivieren](#tastenereignisse-aktivieren-homematicip).

**F: Neues Gerät zur CCU hinzugefügt, erscheint aber nicht in HA**

Unter **Einstellungen → System → Reparaturen** nach der Gerätebenachrichtigung schauen.

**F: Wie ändere ich einen Gerätenamen?**

| Ziel                    | Methode                                       |
| ----------------------- | --------------------------------------------- |
| Nur in HA ändern        | Einstellungen → Geräte → Name bearbeiten      |
| Von CCU synchronisieren | In CCU umbenennen → Integration neu laden     |
| Entity-ID auch ändern   | Gerät löschen → In CCU umbenennen → Neu laden |

**F: Meine CCU hat viele Systemvariablen, aber ich sehe nur wenige**

Systemvariablen werden als deaktivierte Entities importiert. In Einstellungen → Entities → Deaktivierte anzeigen aktivieren, oder Marker zur automatischen Aktivierung verwenden.

---

## Siehe auch

- [Actions-Referenz](features/homeassistant_actions.md)
- [Benennungskonventionen](advanced/homeassistant_naming.md)
- [Fehlerbehebungsleitfaden](troubleshooting/homeassistant_troubleshooting.md)
- [Berechnete Klimasensoren](features/calculated_climate_sensors.md)
