---
translation_source: docs/user/homeassistant_integration.md
translation_date: 2026-04-01
translation_source_hash: d6940ae7d4e0
---

# Homematic(IP) Local for OpenCCU

Dies ist das umfassende Benutzerhandbuch fuer die **Homematic(IP) Local for OpenCCU** Home Assistant-Integration, die aiohomematic als Kernbibliothek verwendet.

## Schnellstart

- **Installation**: Ueber HACS (empfohlen) oder manuell
- **Dokumentation**: Dieses Handbuch + [aiohomematic-Dokumentation](../index.md)
- **Probleme**: [GitHub Issues](https://github.com/sukramj/aiohomematic/issues)
- **Diskussionen**: [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions)

## Auf einen Blick

- Lokale Home Assistant-Integration fuer Homematic(IP)-Zentralen (CCU2/3, OpenCCU, Debmatic, Homegear)
- Keine Cloud erforderlich - vollstaendig lokale Kommunikation
- XML-RPC fuer Steuerung und Push-Statusaktualisierungen; JSON-RPC fuer Namen und Raeume
- Automatische Erkennung fuer CCU und kompatible Zentralen unterstuetzt
- Mindestanforderungen: Home Assistant 2025.10.0+

## Verwandte Integrationen

| Integration                                                                         | Anwendungsfall                              |
| ----------------------------------------------------------------------------------- | ------------------------------------------- |
| **Homematic(IP) Local for OpenCCU**                                                 | Lokale Steuerung ueber CCU/OpenCCU/Homegear |
| [Homematic(IP) Cloud](https://www.home-assistant.io/integrations/homematicip_cloud) | Cloud-Steuerung ueber Access Point          |
| [Homematic IP Local (HCU)](https://github.com/Ediminator/hacs-homematicip-hcu)      | Lokale Steuerung ueber HmIP-HCU1            |

---

## Installation

### HACS (empfohlen)

1. In Home Assistant zu **HACS** → **Integrations** → **Explore & Download Repositories** navigieren
2. Nach "Homematic(IP) Local for OpenCCU" suchen
3. Installieren und Home Assistant bei Aufforderung neu starten

### Manuelle Installation

1. `custom_components/homematicip_local` in das Home Assistant-Verzeichnis `config/custom_components` kopieren
2. Home Assistant neu starten

!!! warning "Manuelle Installation unterstuetzt keine automatischen Updates"

---

## Voraussetzungen

### Hardware

Diese Integration funktioniert mit jeder CCU-kompatiblen Homematic-Zentrale:

- CCU2/CCU3
- OpenCCU (ehemals RaspberryMatic)
- Debmatic
- Homegear
- Home Assistant OS/Supervised mit geeigneter App + Kommunikationsgeraet

**Minimale CCU-Firmware:**

- CCU2: 2.61.x
- CCU3: 3.61.x

### Firewall und Ports

| Schnittstelle   | Zweck                       | Standard-Port | TLS-Port |
| --------------- | --------------------------- | ------------- | -------- |
| BidCos-RF       | Klassische Funkgeraete      | 2001          | 42001    |
| HomematicIP     | HmIP Funk- und Drahtgeraete | 2010          | 42010    |
| BidCos-Wired    | Klassische Drahtgeraete     | 2000          | 42000    |
| Virtual Devices | Thermostatgruppen           | 9292          | 49292    |
| JSON-RPC        | Namen und Raeume            | 80            | 443      |

!!! note "XML-RPC Callback"
Die Integration startet einen lokalen XML-RPC-Server innerhalb von Home Assistant. Die CCU muss in der Lage sein, sich fuer Statusaktualisierungen mit diesem Server zu verbinden.

    **Docker-Nutzer**: `network_mode: host` verwenden oder `callback_host` und `callback_port_xml_rpc` in den erweiterten Optionen konfigurieren.

!!! info "Wie Callbacks funktionieren"
Die CCU sendet Geraeteereignisse (Tastendruck, Temperaturwechsel usw.) per XML-RPC Callbacks an Home Assistant. Dazu muss die CCU HA auf einem bestimmten Port erreichen koennen. Wenn diese Verbindung fehlschlaegt (Firewall, Docker-Netzwerk, falsche IP), funktionieren Befehle an Geraete weiterhin, aber Statusaktualisierungen kommen nicht mehr an.

### Authentifizierung

- Die Authentifizierung wird **immer** an die Homematic-Zentrale weitergeleitet
- **Empfohlen**: Authentifizierung fuer die XML-RPC-Kommunikation auf der CCU aktivieren (Einstellungen → Systemsteuerung → Sicherheit → Authentifizierung)
- Das Konto **muss Administratorrechte** haben
- Erlaubte Passwortzeichen: `A-Z`, `a-z`, `0-9` und `.!$():;#-`

!!! warning "Sonderzeichen"
Zeichen wie `ÄäÖöÜüß` funktionieren im CCU WebUI, werden aber von XML-RPC-Servern **nicht unterstuetzt**.

---

## Konfiguration

### Integration hinzufuegen

[Integration hinzufuegen](https://my.home-assistant.io/redirect/config_flow_start?domain=homematicip_local){ .md-button .md-button--primary }

Oder manuell:

1. Zu **Einstellungen** → **Geraete & Dienste** navigieren
2. **Integration hinzufuegen** klicken
3. Nach "Homematic(IP) Local for OpenCCU" suchen

### Konfigurationsablauf

```
Schritt 1: CCU-Verbindung → Backend-Erkennung → Schritt 2: TLS & Schnittstellen → Abschluss oder Erweiterte Konfiguration
```

#### Schritt 1: CCU-Verbindung

| Einstellung      | Beschreibung                                         | Beispiel          |
| ---------------- | ---------------------------------------------------- | ----------------- |
| **Instanzname**  | Eindeutiger Bezeichner (Kleinbuchstaben, a-z, 0-9)   | `ccu3`            |
| **Host**         | CCU-Hostname oder IP-Adresse                         | `192.168.1.50`    |
| **Benutzername** | Admin-Benutzername (Gross-/Kleinschreibung beachten) | `Admin`           |
| **Passwort**     | Admin-Passwort (Gross-/Kleinschreibung beachten)     | `MySecurePass123` |

!!! warning "Instanzname"
Der Instanzname ist ein eindeutiger Bezeichner fuer die HA-Installation bei der Kommunikation mit der CCU.

    - Er hat **keinen Bezug** zum Hostnamen der CCU
    - Die **IP-Adresse der CCU** kann jederzeit geaendert werden
    - Der **Instanzname darf nach der Einrichtung nicht geaendert** werden (Entities werden neu erstellt, Verlauf geht verloren)

    **Beispiel**: Es gibt zwei Home Assistant-Instanzen (Produktion und Test), die mit derselben CCU verbunden sind. Jede benoetigt einen eindeutigen Instanznamen, damit die CCU Ereignisse an die richtige Callback-URL weiterleiten kann. Wenn beide denselben Namen verwenden, empfaengt nur eine Instanz Ereignisse -- die andere erscheint als getrennt.

#### Automatische Backend-Erkennung

Nach Eingabe der Zugangsdaten erkennt die Integration automatisch:

- Backend-Typ (CCU2, CCU3, OpenCCU, Debmatic, Homegear)
- Verfuegbare Schnittstellen (HmIP-RF, BidCos-RF, BidCos-Wired, Virtual Devices, CUxD, CCU-Jack)
- TLS-Konfiguration

#### Schritt 2: TLS & Schnittstellen

| Einstellung          | Standard     | Beschreibung                                                      |
| -------------------- | ------------ | ----------------------------------------------------------------- |
| **TLS verwenden**    | Auto-erkannt | Aktivieren, wenn die CCU HTTPS verwendet                          |
| **TLS verifizieren** | `false`      | Nur mit gueltigem (nicht selbst-signiertem) Zertifikat aktivieren |

**Schnittstellenauswahl:**

| Schnittstelle         | Aktivieren wenn...                            |
| --------------------- | --------------------------------------------- |
| HomematicIP (HmIP-RF) | HomematicIP Funk- oder Drahtgeraete vorhanden |
| Homematic (BidCos-RF) | Klassische Homematic Funkgeraete vorhanden    |
| BidCos-Wired          | Klassische Homematic Drahtgeraete vorhanden   |
| Heizungsgruppen       | Thermostatgruppen in der CCU konfiguriert     |
| CUxD                  | CUxD Add-on installiert                       |
| CCU-Jack              | CCU-Jack-Software installiert                 |

---

## Erweiterte Optionen

Zugriff ueber **Erweiterte Optionen konfigurieren** waehrend der Einrichtung oder **Konfigurieren** nach der Einrichtung.

### Callback-Einstellungen (Docker/Netzwerk)

| Einstellung                 | Zweck                                        |
| --------------------------- | -------------------------------------------- |
| **Callback Host**           | IP-Adresse, ueber die die CCU HA erreicht    |
| **Callback Port (XML-RPC)** | Port fuer Statusaktualisierungen von der CCU |

!!! tip "Docker-Nutzer"
**Empfohlen**: `network_mode: host` verwenden

    **Alternative**: Callback Host auf die IP des Docker-Hosts setzen und Portweiterleitung konfigurieren

### Systemvariablen & Programme

| Einstellung                         | Standard | Beschreibung                                |
| ----------------------------------- | -------- | ------------------------------------------- |
| **Systemvariablen-Scan aktivieren** | `true`   | Systemvariablen von der CCU abrufen         |
| **Systemvariablen-Marker**          | Alle     | Filtern, welche Variablen importiert werden |
| **Programm-Scan aktivieren**        | `true`   | Programme von der CCU abrufen               |
| **Scan-Intervall**                  | 30s      | Abfrageintervall fuer Aenderungen           |

**Marker:**

- **HAHM** - Erstellt beschreibbare Entities (Schalter, Auswahl, Nummer, Text)
- **MQTT** - Aktiviert Push-Updates ueber MQTT (erfordert CCU-Jack)
- **HX** - Benutzerdefinierter Marker fuer eigene Filterung
- **INTERNAL** - Schliesst CCU-interne Variablen/Programme ein

### MQTT-Integration

| Einstellung         | Standard | Beschreibung                                           |
| ------------------- | -------- | ------------------------------------------------------ |
| **MQTT aktivieren** | `false`  | Fuer CCU-Jack- und CUxD-Callback-Ereignisse aktivieren |
| **MQTT-Praefix**    | _(leer)_ | MQTT-Praefix fuer die CCU-Jack-Bridge                  |

### Geraeteverhalten

| Einstellung                                      | Standard | Beschreibung                                            |
| ------------------------------------------------ | -------- | ------------------------------------------------------- |
| **Sub-Geraete aktivieren**                       | `false`  | Geraete mit mehreren Kanalgruppen aufteilen             |
| **Gruppenkanal fuer Abdeckungsstatus verwenden** | `true`   | Gruppenkanal fuer Abdeckungsposition verwenden          |
| **Letzte Helligkeit wiederherstellen**           | `false`  | Leuchten schalten mit letzter Helligkeit statt 100% ein |

### Befehlsdrosselung

Steuert die minimale Verzoegerung zwischen aufeinanderfolgenden Geraetebefehlen, die ueber jede Funkschnittstelle gesendet werden. Dies gewaehrleistet einen reibungslosen Betrieb und hilft, Paketverluste zu vermeiden, insbesondere bei Massenoperationen wie Automatisierungen, die viele Geraete gleichzeitig steuern (z.B. "alle Lichter aus").

| Einstellung                      | Standard | Bereich     | Beschreibung                                                            |
| -------------------------------- | -------- | ----------- | ----------------------------------------------------------------------- |
| **Befehlsdrosselungs-Intervall** | `0.1`s   | 0.0 - 5.0 s | Minimale Pause zwischen aufeinanderfolgenden Befehlen pro Schnittstelle |

Bei einem positiven Wert werden ausgehende Befehle (`set_value`, `put_paramset`) ratenbegrenzt, sodass mindestens die konfigurierte Anzahl von Sekunden zwischen aufeinanderfolgenden Befehlen auf derselben Funkschnittstelle vergeht. Jede Schnittstelle (HmIP-RF, BidCos-RF usw.) hat eine eigene unabhaengige Drosselung. Auf `0.0` setzen, um die Drosselung vollstaendig zu deaktivieren.

!!! tip "Wann die Drosselung erhoehen"
Falls Befehle gelegentlich verloren gehen, wenn viele Geraete gleichzeitig gesteuert werden (z.B. eine "Gute Nacht"-Szene), das Drosselungsintervall erhoehen. Ein Wert von `0.5`s ist ein guter Ausgangspunkt fuer die meisten Installationen.

!!! note "Funk-Duty-Cycle"
Jede Homematic-Funkschnittstelle hat ein gesetzliches Limit fuer die nutzbare Sendezeit (Duty Cycle). Das Senden vieler Befehle in schneller Folge kann dieses Limit voruebergehend erschoepfen, sodass die CCU weitere Befehle ablehnt, bis sich der Duty Cycle erholt hat. Die Drosselung verteilt Befehle ueber die Zeit, um dieses Limit nicht zu erreichen.

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

`HAHM` zum Beschreibungsfeld der Variable in der CCU hinzufuegen:

1. In der CCU die Systemvariable bearbeiten
2. Im Feld "Beschreibung" `HAHM` (Grossbuchstaben) eintragen
3. Speichern und die Integration in HA neu laden

### Filtern mit Markern

Ohne Marker werden alle Variablen als **deaktivierte** Entities importiert. Mit in den erweiterten Optionen konfigurierten Markern werden nur markierte Variablen als **aktivierte** Entities importiert.

---

## Geraeteunterstuetzung

Geraete werden integriert, indem verfuegbare Parameter automatisch erkannt und passende Entities erstellt werden. Fuer komplexe Geraete (Thermostate, Abdeckungen) bieten benutzerdefinierte Zuordnungen eine bessere Darstellung.

### Deaktivierte Entities

Viele Entities werden anfaenglich **deaktiviert** erstellt. Bei Bedarf in den erweiterten Einstellungen der Entity aktivieren.

### Fehlende Geraeteunterstuetzung

Wenn ein neues Geraetemodell keine passenden benutzerdefinierten Entities hat:

1. Sicherstellen, dass das Geraet in der CCU funktioniert
2. Bei [aiohomematic Issues](https://github.com/sukramj/aiohomematic/issues) melden
3. Geraeteexport beifuegen (die Action `homematicip_local.export_device_definition` verwenden)

---

## Neue Geraete hinzufuegen (Pairing)

### Anlernmodus

Die Integration stellt Buttons bereit, um den Anlernmodus zu aktivieren:

- **Anlernmodus HmIP-RF aktivieren** - Fuer HomematicIP-Geraete
- **Anlernmodus BidCos-RF aktivieren** - Fuer klassische Homematic-Geraete

Dauer-Sensoren zeigen die verbleibende Anlernzeit an.

### Reparatur-Benachrichtigungsprozess

Beim Anlernen eines neuen Geraets:

1. **Geraet** mit der CCU koppeln (ueber die CCU-Oberflaeche)
2. **(Empfohlen) Geraet** in der CCU mit einem aussagekraeftigen Namen benennen
3. **HA-Reparaturen pruefen** - Einstellungen → System → Reparaturen
4. **Geraet bestaetigen oder benennen** im Reparaturdialog
5. Geraet und Entities werden mit korrekten Namen erstellt

!!! tip "Benennungsstrategie"
Geraete zuerst in der CCU benennen. Die Integration verwendet CCU-Namen, und es entstehen saubere Entity-IDs wie `sensor.wohnzimmer_thermostat_temperatur` statt `sensor.vcu1234567_temperature`.

### Posteingangs-Sensor

Der **Posteingangs**-Sensor zeigt Geraete an, die im CCU-Posteingang warten.

---

## Tastengeraete & Ereignisse

### Warum keine Tasten-Entities?

Physische Tasten haben keinen persistenten Zustand. Tastendrucke werden als **Ereignisse** behandelt, nicht als Entities.

### Tasten in Automatisierungen verwenden

1. Eine Automation erstellen
2. Ausloesertyp: **Device**
3. Das Tastengeraet auswaehlen
4. Den Ausloeser waehlen: "Taste 1 gedrueckt", "Taste 2 lang gedrueckt" usw.

### Tastenereignisse aktivieren (HomematicIP)

Fuer HomematicIP-Fernbedienungen (WRC2, WRC6, SPDR, KRC4, HM-PBI-4-FM):

**Option A - Action:**

```yaml
action: homematicip_local.create_central_links
target:
  device_id: YOUR_DEVICE_ID
```

**Option B - CCU-Oberflaeche:**

1. CCU → Einstellungen → Geraete
2. "+" neben der Fernbedienung klicken
3. Den Tastenkanal anklicken → "aktivieren"

**Zum Deaktivieren:** `homematicip_local.remove_central_links` verwenden

---

## Ereignisse

### homematic.keypress

Wird bei einem Tastendruck ausgeloest. Mit Device-Triggern oder Event-Entities verwenden.

### homematic.device_availability

Wird ausgeloest, wenn ein Geraet nicht mehr erreichbar ist oder wieder erreichbar wird. Nuetzlich mit dem Blueprint fuer persistente Benachrichtigungen.

### homematic.device_error

Wird ausgeloest, wenn sich ein Geraet in einem Fehlerzustand befindet.

---

## Actions-Referenz

Siehe [Actions](features/homeassistant_actions.md) fuer die vollstaendige Action-Referenz einschliesslich:

- Geraetewert-Operationen (`get_device_value`, `set_device_value`)
- Paramset-Operationen (`get_paramset`, `put_paramset`)
- Zeitplanverwaltung (`set_schedule`, `set_schedule_profile`, `copy_schedule`)
- Sirenensteuerung (`turn_on_siren`, `play_sound`)
- Systemvariablen (`get_variable_value`, `set_variable_value`)
- Und mehr...

---

## CUxD & CCU-Jack

### Kommunikationsmethoden

| Geraetetyp | Standard               | Mit MQTT           |
| ---------- | ---------------------- | ------------------ |
| CUxD       | JSON-RPC-Polling (15s) | MQTT-Push (sofort) |
| CCU-Jack   | JSON-RPC-Polling (15s) | MQTT-Push (sofort) |

### MQTT einrichten

**Voraussetzungen:**

1. CCU-Jack auf der CCU installiert
2. HA mit MQTT-Broker verbunden
3. MQTT-Integration in HA konfiguriert

**Konfiguration:**

1. Erweiterte Optionen → MQTT aktivieren: `true`
2. MQTT-Praefix: _(fuer direkte Verbindung leer lassen)_

!!! note "Support-Richtlinie"
Abweichungen von CUxD/CCU-Jack gegenueber dem Verhalten der Original-Hardware werden **nicht als Fehler betrachtet**. Bei Bedarf HA-Templates zur Anpassung verwenden.

---

## Fehlerbehebung

### Schnell-Checkliste

| Pruefpunkt         | Vorgehensweise                                              |
| ------------------ | ----------------------------------------------------------- |
| HA-Logs geprueft   | Einstellungen → System → Logs → Filter: `homematicip_local` |
| Ports offen        | Mit Ping testen, Telnet auf Port 2010                       |
| CCU erreichbar     | CCU-Weboberflaeche aufrufbar                                |
| Admin-Benutzer     | Benutzer hat Administratorrechte                            |
| Gueltiges Passwort | Nur erlaubte Zeichen verwendet                              |

### Docker-Probleme

| Problem                      | Loesung                                   |
| ---------------------------- | ----------------------------------------- |
| Keine Statusaktualisierungen | `callback_host` auf Docker-Host-IP setzen |
| Verbindung verweigert        | `network_mode: host` verwenden            |
| Konflikt mehrerer Instanzen  | Eindeutigen `instance_name` sicherstellen |

### Hilfe erhalten

1. Den [vollstaendigen Fehlerbehebungsleitfaden](troubleshooting/homeassistant_troubleshooting.md) lesen
2. [Bestehende Issues](https://github.com/sukramj/aiohomematic/issues) durchsuchen
3. In den [Diskussionen](https://github.com/sukramj/aiohomematic/discussions) fragen
4. Ein Issue eroeffnen mit: HA-Version, Integrationsversion, CCU-Typ/Firmware, Logs, Schritte zur Reproduktion

---

## Haeufige Fragen

**F: Entity zeigt "unavailable"**

Die Entity ist moeglicherweise deaktiviert. Zu Einstellungen → Entities navigieren → Entity suchen → Aktivieren.

**F: Tastendrucke loesen keine Automation aus**

HomematicIP-Tasten benoetigen Central Links. Siehe [Tastenereignisse aktivieren](#tastenereignisse-aktivieren-homematicip).

**F: Neues Geraet zur CCU hinzugefuegt, erscheint aber nicht in HA**

Unter **Einstellungen → System → Reparaturen** nach der Geraetebenachrichtigung schauen.

**F: Wie aendere ich einen Geraetenamen?**

| Ziel                    | Methode                                         |
| ----------------------- | ----------------------------------------------- |
| Nur in HA aendern       | Einstellungen → Geraete → Name bearbeiten       |
| Von CCU synchronisieren | In CCU umbenennen → Integration neu laden       |
| Entity-ID auch aendern  | Geraet loeschen → In CCU umbenennen → Neu laden |

**F: Meine CCU hat viele Systemvariablen, aber ich sehe nur wenige**

Systemvariablen werden als deaktivierte Entities importiert. In Einstellungen → Entities → Deaktivierte anzeigen aktivieren, oder Marker zur automatischen Aktivierung verwenden.

---

## Siehe auch

- [Actions-Referenz](features/homeassistant_actions.md)
- [Benennungskonventionen](advanced/homeassistant_naming.md)
- [Fehlerbehebungsleitfaden](troubleshooting/homeassistant_troubleshooting.md)
- [Berechnete Klimasensoren](features/calculated_climate_sensors.md)
