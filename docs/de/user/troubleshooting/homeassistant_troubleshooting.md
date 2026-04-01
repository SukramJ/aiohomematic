---
translation_source: docs/user/troubleshooting/homeassistant_troubleshooting.md
translation_date: 2026-04-01
translation_source_hash: 8e9eba4a4876
---

# Haeufige Probleme und Fehlerbehebung (Home Assistant)

Dieses Dokument hilft bei der schnellen Analyse und Behebung typischer Probleme bei der Verwendung von aiohomematic mit Home Assistant (Integration: Homematic(IP) Local). Die Hinweise gelten fuer CCU (CCU2/3, OpenCCU, piVCCU/Debmatic) und Homegear, sofern nicht anders angegeben.

!!! note
Falls Begriffe wie Integration, App, Backend, Interface oder Channel unbekannt sind, bitte zuerst das [Glossar](../../reference/glossary.md) lesen.

Inhalt:

- Schnelle Symptomzuordnung (auf einen Blick)
- Schritt-fuer-Schritt-Diagnose
- Haeufige Probleme mit Ursachen und Loesungen
- Netzwerk/Ports/Container-Besonderheiten
- Logs und Debug-Informationen erfassen
- Wann ein Issue geoeffnet werden sollte - erforderliche Informationen

---

## 1) Schnelle Symptomzuordnung

Dieser Abschnitt bietet eine schnelle Uebersicht ueber haeufige Symptome und deren wahrscheinlichste Ursachen. Er dient dazu, den Problembereich schnell einzugrenzen, bevor die detaillierten Diagnosen weiter unten durchgegangen werden.

| Symptom                                                         | Wahrscheinlichste Ursache                                                                                                                    | Siehe Abschnitt                                                            |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Keine Geraete/Entities nach der Einrichtung sichtbar            | Verbindungsdaten falsch (Host/IP, Ports, Authentifizierung), CCU nicht erreichbar oder callback nicht von der CCU aus erreichbar             | [3A](#a-keine-entities-nach-der-einrichtung)                               |
| Neue Geraete werden nicht erkannt oder unvollstaendig erkannt   | Veraltete Cache-Daten in Home Assistant                                                                                                      | [3H](#h-neue-geraete-werden-nicht-erkannt-oder-unvollstaendig-erkannt)     |
| Entities vorhanden, aber ohne Statusaenderungen                 | Event-Callbacks kommen nicht an (Firewall/NAT/Docker), XML-RPC blockiert oder ungueltige Sitzung                                             | [3B](#b-entities-haben-keine-aktualisierungen-nur-anfangswerte-oder-keine) |
| Einzelne Geraete "nicht verfuegbar" oder auf altem Wert haengen | Geraeteverfuegbarkeitsproblem (UN_REACH/STICKY_UN_REACH), Funkprobleme, batteriegespeistes Geraet im Schlafmodus oder CONFIG_PENDING aktiv   | [3C](#c-einzelne-geraete-sind-nicht-verfuegbar)                            |
| Werte schreiben funktioniert nicht                              | Berechtigungs-/Authentifizierungsproblem, ungueltiger Parameter, Validierungsfehler, falscher Channel/Parameter oder Geraet nicht verfuegbar | [3D](#d-schreiben-schlaegt-fehl-service-aufruf-schlaegt-fehl)              |
| HmIP-Geraete fehlen                                             | HmIP-Dienst auf der CCU nicht aktiv, falsche Ports oder Sitzungs-/Token-Problem                                                              | [3E](#e-hmip-geraete-fehlen-oder-werden-nicht-aktualisiert)                |
| Nach CCU/Home Assistant Neustart kommen keine Updates           | Callback nicht erneut registriert, Port blockiert oder Reverse-Proxy/SSL-Terminator blockiert interne Verbindung                             | [3F](#f-keine-ereignisse-nach-neustart)                                    |
| Ping-Pong-Diskrepanz / Events gehen an falsche Instanz          | Mehrere HA-Instanzen mit gleichem `instance_name`, Callback-Registrierungskonflikt                                                           | [3J](#j-ping-pong-diskrepanz-mehrere-home-assistant-instanzen)             |
| Auto-Discovery-Benachrichtigung erscheint immer wieder          | SSDP-Seriennummer-Diskrepanz, Integration vor der Erkennung erstellt                                                                         | [3K](#k-auto-discovery-erscheint-immer-wieder)                             |
| Warnung "Error fetching initial data"                           | CCU-REGA-Skript hat ungueltige Daten zurueckgegeben, CCU ueberlastet                                                                         | [3L](#l-error-fetching-initial-data)                                       |
| Reparaturmeldung "Incomplete device data"                       | Paramset-Beschreibungen fuer Geraete fehlen, CCU-Datenkorruption oder Kommunikationsproblem                                                  | [3M](#m-unvollstaendige-geraetedaten)                                      |
| "GET_ALL_DEVICE_DATA failed" + JSONDecodeError                  | Geraete-/Channel-Name enthaelt ungueltige Zeichen, die die JSON-Ausgabe beschaedigen                                                         | [3N](#n-get_all_device_data-fehlgeschlagen-json-parse-fehler)              |

---

## 2) Schritt-fuer-Schritt-Diagnose

Bei Problemen diese Schritte systematisch durchgehen, um die Ursache zu identifizieren:

### Schritt 1: Grundlegende Verbindungspruefungen

Bevor integrationsspezifische Probleme untersucht werden, die grundlegende Verbindung pruefen:

- **CCU/Homegear-Erreichbarkeit**: Ist die CCU-Weboberflaeche im Browser erreichbar? Falls nicht, hat moeglicherweise die CCU selbst ein Problem.
- **Uhrzeit und Datum**: Ist die Uhrzeit/das Datum auf der CCU korrekt? Eine falsche Uhrzeit kann Authentifizierungsprobleme verursachen.
- **Ressourcen**: Hat die CCU genuegend CPU/RAM? Die Systemdiagnose der CCU pruefen.
- **Netzwerkverbindung**: Kann Home Assistant die CCU erreichen? Versuchen, die CCU-IP vom Home Assistant Host aus anzupingen:
  ```bash
  # From Home Assistant terminal or SSH
  ping <CCU-IP-Adresse>
  ```
- **Port-Erreichbarkeit**: Sind die erforderlichen Ports geoeffnet? Details im Abschnitt [Netzwerk und Ports](#4-netzwerk-ports-und-container).

### Schritt 2: Integrationskonfiguration ueberpruefen

Die Home Assistant Integrationseinstellungen pruefen:

- **Host/IP-Adresse**: Eine IP-Adresse statt eines Hostnamens verwenden, um DNS/mDNS-Aufloesungsprobleme zu vermeiden.
- **Protokollauswahl**: Sicherstellen, dass das richtige Protokoll fuer die Geraete ausgewaehlt ist:
  - BidCos-RF fuer klassische Homematic-Funkgeraete
  - BidCos-Wired fuer kabelgebundene Homematic-Geraete
  - HmIP-RF fuer HomematicIP-Geraete
- **Zugangsdaten**: Benutzername und Passwort ueberpruefen (falls die Authentifizierung auf der CCU aktiviert ist).

### Schritt 3: Callback-Erreichbarkeit ueberpruefen

Dies ist entscheidend: Die CCU muss den callback-Port von Home Assistant erreichen koennen. Die Kommunikation ist bidirektional:

```
Home Assistant → CCU:  Befehle, Abfragen (werden von HA initiiert)
CCU → Home Assistant:  Events, Statusaenderungen (von der CCU ueber callback initiiert)
```

Zum Testen der callback-Erreichbarkeit:

1. Den callback-Port aus der Integrationsdiagnose notieren (Standard: dynamisch zugewiesen)
2. Von der CCU (bei SSH-Zugang) oder einem anderen Geraet im Netzwerk der CCU die Verbindung testen:
   ```bash
   nc -zv <Home-Assistant-IP> <callback-port>
   ```
3. Falls dies fehlschlaegt, die Firewall-Regeln und Docker/Container-Netzwerkkonfiguration pruefen (siehe [Netzwerk-Abschnitt](#4-netzwerk-ports-und-container)).

### Schritt 4: Debug-Logging aktivieren

Detailliertes Logging aktivieren, um zu sehen, was passiert:

**Einfachste Methode** - Ueber die Home Assistant Oberflaeche aktivieren:

1. Zu **Settings** → **Devices & Services** → **Homematic(IP) Local** navigieren
2. Auf **Configure** → **Enable debug logging** klicken
3. Das Problem reproduzieren
4. Auf **Disable debug logging** klicken - das Debug-Log wird als Datei zum Download angeboten

**Alternative** - Ueber YAML-Konfiguration:

1. Folgendes zur `configuration.yaml` hinzufuegen:
   ```yaml
   logger:
     default: info
     logs:
       aiohomematic: debug
       custom_components.homematicip_local: debug
   ```
2. Home Assistant neu starten
3. Das Problem reproduzieren
4. Die Logs unter **Settings** → **System** → **Logs** pruefen

Details zur Interpretation von Log-Nachrichten im [Logging-Abschnitt](#5-logging-und-debug).

### Schritt 5: Geraetestatus auf der CCU pruefen

In der CCU-Weboberflaeche den Status problematischer Geraete ueberpruefen:

- **Geraet erreichbar?**: Pruefen, ob das Geraet in der CCU als erreichbar angezeigt wird
- **UN_REACH/STICKY_UN_REACH**: Diese Parameter im MAINTENANCE-Channel des Geraets pruefen
- **CONFIG_PENDING**: Ist dieser Parameter `true`? Falls ja, ist die Geraetekonfiguration unvollstaendig

### Schritt 6: Cache und Neustart

Nach Aenderungen:

1. Falls Geraeteinformationen veraltet erscheinen, den Service `homematicip_local.clear_cache` verwenden
2. Home Assistant neu starten
3. In manchen Faellen auch die CCU neu starten (besonders nach Firmware-Updates oder umfangreichen Konfigurationsaenderungen)

---

## 3) Haeufige Probleme, Ursachen und Loesungen

### A) Keine Entities nach der Einrichtung

**Symptome:**

- Nach der Einrichtung der Integration erscheinen keine Geraete oder Entities in Home Assistant
- Die Integration wird als "geladen" angezeigt, aber die Geraeteanzahl ist null

**Moegliche Ursachen:**

1. Falsche Host/IP-Adresse oder CCU-Port-Konfiguration
2. Authentifizierung fehlgeschlagen (falscher Benutzername/Passwort)
3. Erforderliche CCU-Dienste nicht gestartet
4. RPC-Methoden auf der CCU nicht verfuegbar

**Diagnoseschritte:**

1. Die Home Assistant Logs auf Fehlermeldungen pruefen (nach "connection refused", "timeout", "401", "403", "404" suchen)
2. Ueberpruefen, ob die CCU-Weboberflaeche unter der gleichen IP-Adresse erreichbar ist
3. Den XML-RPC-Port der CCU direkt testen: `http://<CCU-IP>:2001/` sollte eine XML-RPC-Antwort zeigen

**Loesungen:**

- Ueberpruefen, ob die Host/IP-Adresse korrekt und erreichbar ist
- Zugangsdaten nochmals pruefen (oder ohne Authentifizierung versuchen, falls diese auf der CCU deaktiviert ist)
- Die CCU neu starten, um sicherzustellen, dass alle Dienste laufen
- Die Integration in Home Assistant entfernen und neu hinzufuegen

### B) Entities haben keine Aktualisierungen (nur Anfangswerte oder keine)

**Symptome:**

- Geraete erscheinen in Home Assistant, aber ihre Zustaende aendern sich nie
- Sensorwerte bleiben auf dem Anfangswert stehen
- Tastendruecke oder Schalterbetaetigungen an physischen Geraeten aktualisieren Home Assistant nicht

**Moegliche Ursachen:**

1. Event-Callback von der CCU zu Home Assistant ist blockiert
2. Firewall blockiert eingehende Verbindungen zu Home Assistant
3. NAT/Docker-Netzwerkkonfiguration verhindert, dass die CCU den callback-Port erreicht
4. Callback-IP-Adresse ist falsch (z.B. interne Docker-IP statt Host-IP)

**Warum das passiert:**

Die CCU sendet Statusaenderungen als "Events" an Home Assistant ueber eine callback-Verbindung. Wenn dieser callback blockiert ist, kann Home Assistant die CCU zwar noch abfragen (daher funktionieren Anfangswerte), erhaelt aber keine Aktualisierungen.

**Diagnoseschritte:**

1. Logs auf "Registering callback"- oder "Subscribed"-Meldungen pruefen
2. Vom Netzwerk der CCU aus ueberpruefen, ob der callback-Port erreichbar ist (siehe Schritt 3 der Diagnose)
3. Firewall-Regeln pruefen (ufw, iptables, Windows Firewall)

**Loesungen:**

- **Docker-Nutzer**: Host-Netzwerkmodus verwenden (`network_mode: host`) oder den callback-Port korrekt veroeffentlichen
- **Firewall**: Eingehende Verbindungen auf dem callback-Port von der IP der CCU erlauben
- **Callback-IP pruefen**: In der Integrationskonfiguration sicherstellen, dass die callback-IP eine ist, die die CCU tatsaechlich erreichen kann
- **IP-Aenderungen vermeiden**: Statische IPs oder DHCP-Reservierungen fuer Home Assistant und CCU verwenden

### C) Einzelne Geraete sind "nicht verfuegbar"

**Symptome:**

- Ein oder mehrere Geraete werden in Home Assistant als "nicht verfuegbar" angezeigt
- Das Geraet hat zuvor funktioniert, wurde aber ploetzlich nicht verfuegbar
- Die CCU-Weboberflaeche zeigt das Geraet moeglicherweise als "erreichbar" an, aber Home Assistant zeigt es als nicht verfuegbar

**Geraeteverfuegbarkeit verstehen:**

Die Integration markiert Geraete basierend auf **UNREACH-Events** von der CCU als nicht verfuegbar. Dies ist wichtig zu verstehen:

1. **Funktionsweise**: Wenn ein Geraet nicht auf die Kommunikationsversuche der CCU antwortet, setzt die CCU den Parameter `UN_REACH` auf `true` und sendet diese Information ueber ein Event an Home Assistant
2. **Die Integration reagiert auf dieses Event**, indem sie alle Entities dieses Geraets in Home Assistant als "nicht verfuegbar" markiert
3. **Dies ist beabsichtigtes Verhalten**: Es stellt sicher, dass Home Assistant Kommunikationsprobleme zwischen der CCU und dem Geraet korrekt widerspiegelt

**Warum die CCU-Weboberflaeche einen anderen Status anzeigen kann:**

Die CCU-Weboberflaeche kann den Geraetestatus anders darstellen als Home Assistant. Die **Integration reagiert jedoch ausschliesslich auf die UNREACH-Events**, die sie von der CCU erhaelt. Sie versucht nicht, das Verhalten der CCU zu interpretieren oder zu hinterfragen. Wenn die CCU ein UNREACH-Event sendet, markiert die Integration das Geraet als nicht verfuegbar.

**Moegliche Ursachen:**

1. **Funk-/Drahtlosprobleme**: Geraet ausserhalb der Reichweite, Stoerungen oder schwaches Signal
2. **Batteriebetriebene Geraete**: Geraet befindet sich im Schlafmodus und hat die Abfrage der CCU verpasst
3. **Geraet physisch nicht erreichbar**: Stromausfall, Geraetedefekt oder Geraet entfernt
4. **STICKY_UNREACH**: Ein frueherer Kommunikationsfehler, der nicht zurueckgesetzt wurde
5. **CONFIG_PENDING**: Geraetekonfiguration ist unvollstaendig

**Diagnoseschritte:**

1. In der CCU-Weboberflaeche den MAINTENANCE-Channel des Geraets pruefen:
   - `UNREACH`: Derzeit nicht erreichbar
   - `STICKY_UNREACH`: War irgendwann nicht erreichbar (manuelles Zuruecksetzen erforderlich)
   - `CONFIG_PENDING`: Konfiguration noch nicht angewendet
2. Das physische Geraet pruefen (Batterien, Stromversorgung, Standort)
3. Versuchen, das Geraet manuell auszuloesen (Taste druecken), um die Kommunikation zu erzwingen

**Loesungen:**

- **Funkreichweite verbessern**: Geraet naeher platzieren oder einen Repeater hinzufuegen (jedes netzbetriebene Homematic-Geraet fungiert als Repeater)
- **Batterien ersetzen**: Auch wenn das Geraet noch funktioniert, koennen schwache Batterien intermittierende Kommunikationsprobleme verursachen
- **STICKY_UNREACH zuruecksetzen**: In der CCU-Weboberflaeche `STICKY_UNREACH` fuer das Geraet auf `false` setzen
- **Auf CONFIG_PENDING warten**: Nach dem Pairing oder Konfigurationsaenderungen warten, bis `CONFIG_PENDING` `false` wird
- **Geraet neu pairen**: Als letzten Ausweg das Geraet von der CCU entfernen und erneut pairen

**Alternatives Verhalten (Verfuegbarkeit erzwingen):**

Wenn Geraete trotz UNREACH-Events in Home Assistant als verfuegbar angezeigt werden sollen (aehnlich wie manche das Verhalten der CCU-Weboberflaeche interpretieren), gibt es zwei Moeglichkeiten:

1. **Service-Aufruf**: Den Service `homematicip_local.force_device_availability` verwenden, um ein Geraet manuell als verfuegbar zu markieren. Details in der [Actions-Referenz](../features/homeassistant_actions.md#homematicip_localforce_device_availability).

2. **Automation mit Blueprint**: Die "Reactivate"-Blueprints verwenden, um die Geraeteverfuegbarkeit nach UNREACH-Events automatisch wiederherzustellen. Diese Blueprints ueberwachen UNREACH-Events und rufen automatisch den Service zur Erzwingung der Verfuegbarkeit auf. Siehe die [Blueprints](https://github.com/SukramJ/homematicip_local#blueprints) im Integrations-Repository.

**Hinweis:** Die Verwendung dieser Optionen bedeutet, dass Home Assistant das Geraet als verfuegbar anzeigt, auch wenn die Kommunikation mit der CCU beeintraechtigt ist. Mit Vorsicht verwenden, da dadurch tatsaechliche Geraeteprobleme verborgen werden koennen.

### D) Schreiben schlaegt fehl (Service-Aufruf schlaegt fehl)

**Symptome:**

- Service-Aufrufe zur Geraetesteuerung schlagen mit einem Fehler fehl
- Schalter schalten nicht, Lichter gehen nicht an, Thermostate aendern die Temperatur nicht
- Fehlermeldungen erscheinen im Home Assistant Log

**Moegliche Ursachen:**

1. **Validierungsfehler**: Falscher Parametername, -typ oder -wertebereich
2. **Geraet nicht verfuegbar**: Das Geraet ist als nicht verfuegbar markiert (siehe Abschnitt C)
3. **Falscher Channel**: Der Parameter existiert auf einem anderen Channel als erwartet
4. **Berechtigungsproblem**: CCU-Benutzer hat keine Schreibrechte
5. **Geraet beschaeftigt**: Das Geraet verarbeitet einen anderen Befehl

**Diagnoseschritte:**

1. Die Home Assistant Logs auf die spezifische Fehlermeldung pruefen
2. Ueberpruefen, ob das Geraet verfuegbar ist (nicht als nicht verfuegbar angezeigt)
3. In der CCU-Weboberflaeche die Paramset-Beschreibung auf gueltige Werte pruefen

**Haeufige Validierungsfehler und Loesungen:**

| Fehler               | Ursache                 | Loesung                                                             |
| -------------------- | ----------------------- | ------------------------------------------------------------------- |
| "Value out of range" | Zahl zu hoch/zu niedrig | Die MIN/MAX-Werte des Parameters pruefen                            |
| "Invalid parameter"  | Falscher Parametername  | Den genauen Parameternamen in der CCU ueberpruefen                  |
| "Invalid channel"    | Falsche Channel-Nummer  | Den richtigen Channel fuer diesen Parameter finden                  |
| "Invalid type"       | Falscher Datentyp       | Korrekten Typ verwenden (Zahl vs. Zeichenkette vs. Boolescher Wert) |

**Loesungen:**

- Die Entity-Attribute in Home Assistant pruefen, um gueltige Wertebereiche zu sehen
- Die CCU-Weboberflaeche verwenden, um zu testen, ob der Parameter dort gesetzt werden kann
- Ueberpruefen, ob der in der Integration konfigurierte Benutzer Schreibrechte hat
- Sicherstellen, dass das Geraet verfuegbar ist, bevor Befehle gesendet werden

### E) HmIP-Geraete fehlen oder werden nicht aktualisiert

**Symptome:**

- HomematicIP (HmIP)-Geraete erscheinen nicht in Home Assistant
- HmIP-Geraete erscheinen, werden aber nicht aktualisiert oder reagieren nicht auf Befehle
- Klassische Homematic-Geraete funktionieren einwandfrei, aber HmIP-Geraete nicht

**Moegliche Ursachen:**

1. HmIP-Dienst auf der CCU laeuft nicht oder ist nicht korrekt gekoppelt
2. Falsche Port-Konfiguration (HmIP verwendet andere Ports als klassisches Homematic)
3. JSON-RPC-Sitzung/Token abgelaufen oder ungueltig
4. HmIP-Funkmodul der CCU funktioniert nicht

**Diagnoseschritte:**

1. In der CCU-Weboberflaeche unter **Settings** → **System Control** pruefen, ob der HmIP-Dienst laeuft
2. Pruefen, ob HmIP-Geraete in der CCU-Weboberflaeche selbst funktionieren
3. In den Home Assistant Logs nach JSON-RPC-bezogenen Fehlern suchen
4. Ueberpruefen, ob Port 2010 (oder 42010 fuer TLS) erreichbar ist

**Loesungen:**

- Die CCU neu starten, um alle Dienste einschliesslich HmIP neu zu starten
- Die Systemdiagnose der CCU auf den Status des HmIP-Funkmoduls pruefen
- Die Home Assistant Integration neu starten (oder Home Assistant komplett neu starten)
- Falls die Probleme bestehen bleiben, die HmIP-Geraete in der CCU neu pairen

### F) Keine Ereignisse nach Neustart

**Symptome:**

- Nach dem Neustart von Home Assistant oder der CCU zeigen Geraete Anfangswerte, werden aber nicht aktualisiert
- Vor dem Neustart hat alles funktioniert
- Logs zeigen, dass die Integration erfolgreich gestartet wurde

**Moegliche Ursachen:**

1. Callback-Registrierung nach dem Neuverbinden fehlgeschlagen
2. Der callback-Port ist jetzt blockiert oder wird von einem anderen Prozess verwendet
3. Ein Reverse-Proxy oder SSL-Terminator stoert die callback-Verbindung
4. Die CCU hat das callback-Abonnement nicht erneut hergestellt

**Diagnoseschritte:**

1. Logs nach "Registering callback"-Meldungen nach dem Neustart pruefen
2. Ueberpruefen, ob der callback-Port noch verfuegbar ist und nicht von einem anderen Dienst verwendet wird
3. Falls ein Reverse-Proxy verwendet wird, pruefen, ob dieser die callback-Verbindung zulaesst

**Loesungen:**

- Die Integration ueber **Settings** → **Devices & Services** → Homematic(IP) Local → **Reload** neu starten
- Bei Verwendung von Docker mit Bridge-Netzwerk sicherstellen, dass die Port-Zuordnungen noch korrekt sind
- Bei anhaltenden Problemen den Host-Netzwerkmodus in Docker versuchen
- Pruefen, ob kuerzliche Netzwerkaenderungen die Verbindung beeintraechtigt haben koennten

### G) CONFIG_PENDING bleibt True

**Symptome:**

- Der Parameter `CONFIG_PENDING` eines Geraets bleibt dauerhaft `true`
- Das Geraet funktioniert moeglicherweise teilweise, erscheint aber unvollstaendig
- Einige Funktionen oder Parameter fehlen

**CONFIG_PENDING verstehen:**

`CONFIG_PENDING` zeigt an, dass das Geraet eine Konfiguration hat, die uebertragen werden muss, aber noch nicht vollstaendig angewendet wurde. Dies ist haeufig:

- Nach dem erstmaligen Pairing
- Nach dem Aendern von Geraeteeinstellungen in der CCU
- Bei batteriebetriebenen Geraeten, die aufwachen muessen, um die Konfiguration zu empfangen

**Moegliche Ursachen:**

1. Batteriebetriebenes Geraet schlaeft und ist nicht aufgewacht, um die Konfiguration zu empfangen
2. Geraet ausserhalb der Funkreichweite
3. Konfigurationsprozess wurde unterbrochen
4. Geraet hat ein Problem, das den Abschluss der Konfiguration verhindert

**Loesungen:**

- **Batteriegeraete**: Eine Taste am Geraet druecken, um es aufzuwecken und die Konfigurationsuebertragung auszuloesen
- **Warten**: Einige Geraete koennen mehrere Stunden benoetigen, um die Konfiguration abzuschliessen (besonders batteriebetriebene)
- **Reichweite pruefen**: Sicherstellen, dass das Geraet in Funkreichweite der CCU oder eines Repeaters ist
- **Neu pairen**: Falls nichts anderes hilft, das Geraet von der CCU entfernen und erneut pairen
- **Hinweis**: aiohomematic aktualisiert automatisch die MASTER-Parameter, sobald `CONFIG_PENDING` `false` wird

### H) Neue Geraete werden nicht erkannt oder unvollstaendig erkannt

**Symptome:**

- Ein neues Geraet wurde zur CCU hinzugefuegt, erscheint aber nicht in Home Assistant
- Ein Geraet erscheint, aber Channels oder Entities fehlen
- Geraet hat zuvor funktioniert, ist aber nach einem CCU-Update unvollstaendig

**Moegliche Ursachen:**

1. Der Cache von Home Assistant enthaelt veraltete Geraeteinformationen
2. Das Geraet war beim letzten Cache-Aufbau nicht vollstaendig gepairt
3. Die CCU hat neue Geraeteinformationen, aber Home Assistant hat diese nicht abgerufen
4. Geraetekonfiguration hat sich geaendert, aber der Cache wurde nicht invalidiert

**Den Cache verstehen:**

aiohomematic cached Geraetebeschreibungen und Parameterinformationen fuer einen schnelleren Start. Dieser Cache wird normalerweise automatisch aktualisiert, kann aber in manchen Situationen veraltet sein.

**Loesungen:**

1. **Cache leeren**: Den Service `homematicip_local.clear_cache` verwenden:
   - Zu **Developer Tools** → **Actions** in Home Assistant navigieren
   - Nach `homematicip_local.clear_cache` suchen
   - Die Integrationsinstanz auswaehlen
   - Auf **Call Service** klicken
2. **Home Assistant neu starten** nach dem Leeren des Cache
3. Dies erzwingt eine erneute Erkennung aller Geraete und ihrer Parameter

Weitere Details zum clear_cache-Service in der [Actions-Referenz](../features/homeassistant_actions.md#homematicip_localclear_cache).

### I) Unifi-Firewall-Alarme: "ET EXPLOIT HTTP POST with Common Ruby RCE Technique in Body"

**Symptome:**

- Unifi-Firewall zeigt Sicherheitswarnungen fuer den Datenverkehr zwischen Home Assistant und CCU
- Alarmmeldung erwaehnt "Ruby RCE" oder aehnliche Exploit-Erkennung
- Homematic-Kommunikation wird moeglicherweise blockiert oder ist intermittierend

**Diesen Alarm verstehen:**

Dies ist ein **Fehlalarm (False Positive)**. Die Unifi-Firewall verwendet Suricata IDS (Intrusion Detection System), das XML-RPC-Kommunikation faelschlicherweise als potenziellen Exploit identifiziert. Der Grund:

- XML-RPC verwendet Tags wie `<methodCall>`, `<methodName>` und `<params>`
- Diese Tags aehneln Mustern, die in Ruby-Marshal-Daten vorkommen
- Suricata-Regel SID 2019401 wird durch diese Muster ausgeloest, da sie als Ruby-Code-Injection-Versuch interpretiert werden
- **Der Datenverkehr ist vollstaendig legitime** Homematic-Kommunikation

**Loesungen:**

1. **IDS-Unterdrueckungsregel erstellen** (empfohlen):

   - In der Unifi Network Console zu **Settings** → **Security** → **Threat Management** navigieren
   - Unter **Suppression** eine Ausnahme hinzufuegen:
     - Quell-IP: Die IP von Home Assistant
     - Ziel-IP: Die IP der CCU
     - Oder die Signatur-ID `2019401` fuer den Datenverkehr zwischen diesen Hosts unterdruecken

2. **TLS-verschluesselte Ports verwenden** (Alternative):
   - Die Integration auf verschluesselte Ports konfigurieren (z.B. 42001 statt 2001)
   - Dies verhindert, dass das IDS den Payload-Inhalt inspiziert

**Hinweis:** Dieser Alarm ist harmlos fuer legitime CCU-Kommunikation und kann sicher unterdrueckt werden.

### J) Ping-Pong-Diskrepanz (mehrere Home Assistant Instanzen)

**Symptome:**

- Reparaturbenachrichtigung: "Pending Pong mismatch" oder "Ping-pong mismatch"
- Geraete werden nicht mehr aktualisiert oder aktualisieren intermittierend
- Einige Events scheinen "verloren" zu gehen

**Den Ping-Pong-Mechanismus verstehen:**

Die Integration verwendet einen Heartbeat-Mechanismus zur Ueberpruefung der Kommunikation:

1. Home Assistant sendet alle 15 Sekunden einen PING an die CCU
2. Die CCU antwortet mit einem PONG zurueck an Home Assistant
3. Wenn die Anzahl von PINGs und PONGs nicht uebereinstimmt, liegt ein Kommunikationsproblem vor

**Szenario 1: Weniger PONGs empfangen als PINGs gesendet**

- **Ursache:** Eine andere Home Assistant Instanz mit dem **gleichen `instance_name`** wurde nach dieser gestartet
- **Auswirkung:** Die neuere Instanz hat die callback-Registrierung "uebernommen" - sie empfaengt nun alle Events
- **Alternative Ursache:** Netzwerkproblem oder CCU-Kommunikationsproblem

**Szenario 2: Mehr PONGs empfangen als PINGs gesendet**

- **Ursache:** Eine andere Home Assistant Instanz mit dem **gleichen `instance_name`** wurde vor dieser gestartet
- **Auswirkung:** Diese Instanz empfaengt PONGs von beiden Registrierungen

**Loesungen:**

1. **Eindeutige Instanznamen sicherstellen**: Jede Home Assistant Installation, die sich mit derselben CCU verbindet, muss einen eindeutigen `instance_name` haben
2. **Auf doppelte Integrationen pruefen**: Doppelte Integrationseintraege entfernen
3. **Betroffene Instanz neu starten**: Dies registriert den callback korrekt neu
4. **Netzwerkprobleme**: Falls nur eine HA-Instanz existiert, Firewall und Netzwerkverbindung pruefen

**Wichtig:** Der `instance_name` wird bei der Ersteinrichtung festgelegt und sollte danach nie geaendert werden (Entities wuerden neu erstellt). Von Anfang an eindeutige Namen waehlen.

### K) Auto-Discovery erscheint immer wieder

**Symptome:**

- SSDP-Discovery-Benachrichtigung erscheint immer wieder, obwohl die CCU bereits konfiguriert ist
- Nach dem Klicken auf "Ignore" erscheint die Erkennung nach einem Home Assistant Neustart erneut
- Mehrere Erkennungseintraege fuer dieselbe CCU

**Moegliche Ursachen:**

1. Die Seriennummer der CCU im SSDP stimmt nicht mit dem konfigurierten Eintrag ueberein
2. Der Integrationseintrag wurde vor der Erkennung manuell erstellt
3. Die SSDP-Antwort enthaelt andere Identifikatoren als erwartet

**Loesungen:**

1. Auf **"Ignore"** bei der Erkennungsbenachrichtigung klicken
2. **Oder den vorhandenen Integrationseintrag neu konfigurieren**, um ihn mit der Erkennung zu verknuepfen
3. **Home Assistant neu starten** nach dem Ignorieren
4. Falls das Problem weiterhin besteht, pruefen, ob sich die Netzwerkkonfiguration der CCU geaendert hat (IP, Hostname)

**Hinweis:** Dies ist ein kosmetisches Problem - die vorhandene Integration funktioniert weiterhin normal.

### L) Error fetching initial data

**Symptome:**

- Warnung in den Logs: "Error fetching initial data" oder "GET_ALL_DEVICE_DATA failed"
- Integration wird geladen, aber der Start ist langsamer
- Hoehere CCU-Last waehrend des Starts

**Dieses Problem verstehen:**

Die Integration verwendet optimierte REGA-Skripte, um Geraetedaten gebuendelt abzurufen. Falls dies fehlschlaegt, wird auf einzelne Anfragen zurueckgegriffen (langsamer, aber funktional).

**Dies ist typischerweise KEIN Integrations-Bug** - es handelt sich normalerweise um ein CCU-Datenproblem.

**Moegliche Ursachen:**

1. Das REGA-Skript der CCU hat ungueltige oder fehlerhafte Daten zurueckgegeben
2. Ein bestimmtes Geraet hat beschaedigte Daten in der CCU
3. CCU ist ueberlastet oder die REGA-Engine ist blockiert
4. Sehr grosse Geraeteanzahl verursacht einen Timeout

**Diagnoseschritte:**

1. Das [REGA-Skript](https://github.com/sukramj/aiohomematic/blob/devel/aiohomematic/rega_scripts/fetch_all_device_data.fn) herunterladen
2. `##interface##` (Zeile 17) durch die Schnittstelle aus der Fehlermeldung ersetzen (z.B. `HmIP-RF`)
3. Das Skript in der CCU-Weboberflaeche ausfuehren: **Settings** → **Control panel** → **Execute script**
4. Pruefen, ob die Ausgabe gueltiges JSON ist
5. Nach fehlerhaften Eintraegen oder unerwarteten Zeichen suchen

**Loesungen:**

- **CCU neu starten**, um blockierte REGA-Prozesse zu beenden
- **Auf problematische Geraete pruefen** in der Skriptausgabe
- **In den [Diskussionen](https://github.com/sukramj/aiohomematic/discussions) posten** mit der Skriptausgabe fuer Hilfe

### M) Unvollstaendige Geraetedaten

**Symptome:**

- Home Assistant zeigt eine Reparaturmeldung: "Incomplete device data"
- Neue Geraete, die mit der CCU gepairt wurden, erscheinen nicht in Home Assistant
- Einigen Geraeten fehlen Entities oder sie zeigen unvollstaendige Funktionalitaet
- Log-Meldungen erwaehnen "devices still missing paramsets after fetch"

**Dieses Problem verstehen:**

Wenn neue Geraete erkannt werden, ruft aiohomematic deren Paramset-Beschreibungen von der CCU ab. Diese Beschreibungen definieren die Parameter, Channels und Faehigkeiten des Geraets. Ohne sie koennen Geraete nicht in Home Assistant erstellt werden.

Dieses Problem tritt auf, wenn:

1. Die CCU neue Geraete meldet, aber
2. Die Paramset-Beschreibungen fuer diese Geraete nicht abgerufen werden koennen, auch nicht nach mehreren Versuchen

**Moegliche Ursachen:**

1. **CCU-Datenkorruption**: Die Geraetedaten in der internen Datenbank der CCU sind beschaedigt
2. **Kommunikationsprobleme**: Intermittierende Netzwerkprobleme zwischen Home Assistant und CCU
3. **CCU-Ueberlastung**: Die CCU ist ueberlastet und kann nicht auf Paramset-Anfragen antworten
4. **Unvollstaendiges Pairing**: Der Pairing-Prozess des Geraets wurde nicht korrekt abgeschlossen
5. **CUxD/Add-on-Probleme**: Bei virtuellen Geraeten (CUxD) kann das Add-on Konfigurationsprobleme haben

**Diagnoseschritte:**

1. **Details der Reparaturmeldung pruefen**: Die Reparaturbenachrichtigung enthaelt die betroffenen Geraeteadressen (z.B. `NEQ1234567`, `CUX2800001`)
2. **Geraete in der CCU-Weboberflaeche ueberpruefen**: Pruefen, ob die betroffenen Geraete korrekt in der Geraetliste der CCU erscheinen
3. **CCU-Systemdiagnose pruefen**: Auf hohe CPU-/Speicherauslastung oder Dienstfehler achten
4. **Home Assistant Logs pruefen**: Debug-Logging aktivieren und nach Fehlern im Zusammenhang mit `fetch_paramsets` oder den spezifischen Geraeteadressen suchen

**Loesungen:**

1. **CCU neu starten**: Dies loest haeufig temporaere Kommunikations- oder Dienstprobleme

   - Die CCU ueber ihre Weboberflaeche oder physisch neu starten
   - Warten, bis alle Dienste vollstaendig gestartet sind (kann mehrere Minuten dauern)
   - Die Home Assistant Integration neu starten

2. **Betroffene Geraete neu pairen**:

   - Das Geraet von der CCU entfernen
   - Das Geraet auf Werkseinstellungen zuruecksetzen (siehe Geraetehandbuch)
   - Das Geraet erneut mit der CCU pairen
   - Warten, bis `CONFIG_PENDING` `false` wird
   - Den Cache in Home Assistant leeren und neu starten

3. **Den Integrations-Cache leeren**:

   - Den Service `homematicip_local.clear_cache` verwenden
   - Home Assistant neu starten
   - Dies erzwingt ein vollstaendiges erneutes Abrufen aller Geraetedaten

4. **Fuer CUxD/virtuelle Geraete**:

   - Den Status des CUxD-Add-ons in der CCU pruefen
   - Das CUxD-Add-on neu starten
   - Ueberpruefen, ob die Konfiguration des virtuellen Geraets vollstaendig ist

5. **Auf CCU-Firmware-Probleme pruefen**:
   - Sicherstellen, dass die CCU-Firmware aktuell ist
   - Einige Firmware-Versionen haben bekannte Probleme mit Paramset-Abfragen
   - Ein Update oder Rollback in Betracht ziehen, falls die Probleme nach einem Firmware-Update aufgetreten sind

**Falls das Problem weiterhin besteht:**

- Die Diagnose aus der Integration herunterladen und auf Fehlermuster pruefen
- In den [Diskussionen](https://github.com/sukramj/aiohomematic/discussions) posten mit:
  - Den betroffenen Geraeteadressen aus der Reparaturmeldung
  - Geraetetypen (Modellnummern)
  - CCU-Typ und Firmware-Version
  - Debug-Logs, die die Abrufversuche zeigen

### N) GET_ALL_DEVICE_DATA fehlgeschlagen (JSON-Parse-Fehler)

**Symptome:**

- Fehler in den Logs: `GET_ALL_DEVICE_DATA failed: Unable to fetch device data for interface X`
- Traceback zeigt `orjson.JSONDecodeError: unexpected character: line X column Y`
- Integration startet nicht oder wird ohne Geraetedaten geladen

**Dieses Problem verstehen:**

Die Integration ruft alle Geraetedaten ueber JSON-RPC ab, indem ein ReGa-Skript auf der CCU ausgefuehrt wird. Das Skript gibt Geraetewerte als JSON zurueck. Wenn ein Geraetename, Channel-Name oder Wert Sonderzeichen enthaelt, die die JSON-Syntax beschaedigen, schlaegt das Parsen fehl.

**Haeufige Ursachen:**

1. Geraete- oder Channel-Name enthaelt nicht-escapte Anfuehrungszeichen (`"`) oder Backslashes (`\`)
2. Geraetename enthaelt Steuerzeichen oder ungewoehnliches Unicode
3. Ein numerischer Wert ist ungueltig (z.B. `NaN`, `Infinity` oder fehlerhafte Zahl)
4. Kopierter Text mit unsichtbaren Zeichen in Geraetenamen

**Diagnoseschritte:**

Anders als bei anderen Problemen erfordert dies direktes JSON-RPC-Debugging, da das ReGa-Skript nicht einfach manuell ausgefuehrt werden kann.

1. **Bei der CCU ueber JSON-RPC anmelden** (Sitzungs-ID erhalten):

   ```bash
   curl -s -X POST "http://<CCU-IP>/api/homematic.cgi" \
     -H "Content-Type: application/json" \
     -d '{"method":"Session.login","params":{"username":"<USER>","password":"<PASSWORD>"}}'
   ```

   Antwort: `{"result":"<SESSION_ID>","error":null}`

2. **Das Geraetedaten-Skript ausfuehren** (`<SESSION_ID>` und `<INTERFACE>` ersetzen):

   Gueltige Schnittstellen: `BidCos-RF`, `BidCos-Wired`, `HmIP-RF`, `VirtualDevices`

   ```bash
   curl -s -X POST "http://<CCU-IP>/api/homematic.cgi" \
     -H "Content-Type: application/json" \
     -d '{
       "method": "ReGa.runScript",
       "params": {
         "_session_id_": "<SESSION_ID>",
         "script": "string sUse_Interface = \"<INTERFACE>\"; string sDevId; string sChnId; string sDPId; var vDPValue; boolean bDPFirst = true; object oInterface = interfaces.Get(sUse_Interface); Write(\"{\"); if (oInterface) { integer iInterface_ID = interfaces.Get(sUse_Interface).ID(); string sAllDevices = dom.GetObject(ID_DEVICES).EnumUsedIDs(); foreach (sDevId, sAllDevices) { object oDevice = dom.GetObject(sDevId); if ((oDevice) && (oDevice.ReadyConfig()) && (oDevice.Interface() == iInterface_ID)) { foreach (sChnId, oDevice.Channels()) { object oChannel = dom.GetObject(sChnId); if (oChannel) { var oDPs = oChannel.DPs(); if (oDPs) { foreach(sDPId, oDPs.EnumUsedIDs()) { object oDP = dom.GetObject(sDPId); if (oDP && oDP.Timestamp()) { if (oDP.TypeName() != \"VARDP\") { integer sValueType = oDP.ValueType(); boolean bHasValue = false; string sValue; string sID = oDP.Name().UriEncode(); if (sValueType == 20) { sValue = oDP.Value().UriEncode(); bHasValue = true; } else { vDPValue = oDP.Value(); if (sValueType == 2) { if (vDPValue) { sValue = \"true\"; } else { sValue = \"false\"; } bHasValue = true; } else { if (vDPValue == \"\") { sValue = \"0\"; } else { sValue = vDPValue; } bHasValue = true; } } if (bHasValue) { if (bDPFirst) { bDPFirst = false; } else { WriteLine(\",\"); } Write(\"\\\"\"); Write(sID); Write(\"\\\":\"); if (sValueType == 20) { Write(\"\\\"\"); Write(sValue); Write(\"\\\"\"); } else { Write(sValue); } } } } } } } } } } } Write(\"}\");"
       }
     }' | jq -r '.result' > device_data.json
   ```

3. **Die problematische Zeile finden** (die Fehlermeldung zeigt Zeile und Spalte):

   ```bash
   # Wenn der Fehler "line 94 column 50" anzeigt
   head -n 94 device_data.json | tail -n 1
   ```

4. **Das JSON validieren**, um alle Fehler zu sehen:

   ```bash
   cat device_data.json | python3 -m json.tool
   ```

5. **Abmelden** (Sitzung bereinigen):

   ```bash
   curl -s -X POST "http://<CCU-IP>/api/homematic.cgi" \
     -H "Content-Type: application/json" \
     -d '{"method":"Session.logout","params":{"_session_id_":"<SESSION_ID>"}}'
   ```

**Loesungen:**

1. **Das problematische Geraet identifizieren** anhand der Zeile/Spalte in der Fehlermeldung
2. **Das Geraet/den Channel in der CCU-Weboberflaeche umbenennen**, um Sonderzeichen zu entfernen:
   - Anfuehrungszeichen entfernen: `"`, `'`
   - Backslashes entfernen: `\`
   - Steuerzeichen entfernen (den Namen neu eintippen statt kopieren/einfuegen)
3. **Die Integration neu starten** nach der Korrektur des Namens

**Beispiele fuer problematische Namen:**

| Problematischer Name | Problem                           | Korrigierter Name  |
| -------------------- | --------------------------------- | ------------------ |
| `Wohnzimmer "Lampe"` | Enthaelt Anfuehrungszeichen       | `Wohnzimmer Lampe` |
| `Sensor\Fenster`     | Enthaelt Backslash                | `Sensor Fenster`   |
| `Tuer­sensor`        | Versteckter bedingter Trennstrich | `Tuersensor`       |

**Hinweis:** Dies ist ein Datenproblem auf der CCU, kein Integrations-Bug. Die Integration kann kein ungueltiges JSON verarbeiten, das von der REGA-Engine der CCU zurueckgegeben wird.

---

## 4) Netzwerk, Ports und Container

### Erforderliche Ports

| Protokoll    | Standard-Port | TLS-Port | Beschreibung                            |
| ------------ | ------------- | -------- | --------------------------------------- |
| BidCos-RF    | 2001          | 42001    | Klassisches Homematic-Funksystem        |
| BidCos-Wired | 2000          | 42000    | Klassisches Homematic kabelgebunden     |
| HmIP-RF      | 2010          | 42010    | HomematicIP                             |
| Groups       | 9292          | 49292    | Heizungsgruppen (virtueller Thermostat) |
| JSON-RPC     | 80/443        | -        | CCU-WebUI-API (verwendet fuer HmIP)     |

### Callback-Verbindung

Der callback ist die **umgekehrte Verbindung** von der CCU zu Home Assistant:

```
┌─────────────────┐                      ┌─────────────────┐
│  Home Assistant │ ◄──── Callback ───── │       CCU       │
│   (Port XXXXX)  │                      │                 │
└─────────────────┘                      └─────────────────┘
```

- Home Assistant oeffnet einen Port und teilt der CCU mit: "Sende Events an diese IP und diesen Port"
- Die CCU verbindet sich dann mit Home Assistant, wenn Ereignisse auftreten
- **Dieser Port muss vom Netzwerk der CCU aus erreichbar sein**

### Docker und Container-Netzwerke

**Host-Netzwerk (empfohlen fuer einfache Einrichtung):**

```yaml
# docker-compose.yml
services:
  homeassistant:
    network_mode: host
    # Keine Port-Zuordnungen noetig - Container nutzt das Netzwerk des Hosts direkt
```

- Die CCU kann Home Assistant ueber die IP des Hosts erreichen
- Keine Komplikationen bei Port-Zuordnungen
- Callback funktioniert automatisch

**Bridge-Netzwerk (erfordert sorgfaeltige Konfiguration):**

```yaml
# docker-compose.yml
services:
  homeassistant:
    ports:
      - "8123:8123" # Home Assistant Weboberflaeche
      # Callback-Port wird dynamisch zugewiesen - moeglicherweise muss ein statischer Port konfiguriert werden
```

- Sicherstellen, dass der callback-Port veroeffentlicht wird
- Die callback-IP muss die IP des Docker-Hosts sein, nicht die interne IP des Containers
- Die Verwendung eines statischen callback-Ports in der Integrationskonfiguration in Betracht ziehen

### Firewall-Hinweise

Haeufige Firewalls, die den callback blockieren koennen:

| Firewall                | Pruefbefehl                    | Konfigurationsort                |
| ----------------------- | ------------------------------ | -------------------------------- |
| ufw (Ubuntu)            | `sudo ufw status`              | `/etc/ufw/user.rules`            |
| firewalld (Fedora/RHEL) | `sudo firewall-cmd --list-all` | `firewall-cmd`-Befehle           |
| iptables                | `sudo iptables -L`             | `/etc/iptables/rules.v4`         |
| Windows Firewall        | `Get-NetFirewallRule`          | Windows-Sicherheitseinstellungen |
| NAS-Firewalls           | Variiert                       | NAS-Administrationsoberflaeche   |

**Beispiel: Callback-Port mit ufw erlauben:**

```bash
sudo ufw allow from <CCU-IP> to any port <callback-port> proto tcp
```

---

## 5) Logging und Debug

### Debug-Logging aktivieren

**Einfachste Methode** - Ueber die Home Assistant Oberflaeche aktivieren:

1. Zu **Settings** → **Devices & Services** → **Homematic(IP) Local** navigieren
2. Auf **Configure** → **Enable debug logging** klicken
3. Das Problem reproduzieren
4. Auf **Disable debug logging** klicken - das Debug-Log wird als Datei zum Download angeboten

**Alternative** - Ueber YAML-Konfiguration:

Folgendes zur `configuration.yaml` hinzufuegen:

```yaml
logger:
  default: info
  logs:
    # Haupt-Integrations-Logging
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

Fuer gezieltes Logging koennen spezifische Module aktiviert werden:

```yaml
logger:
  default: info
  logs:
    # Spezifische Module fuer gezieltes Debugging
    aiohomematic.caches: debug # Cache-Operationen
    aiohomematic.central: debug # Zentralen-Operationen
    aiohomematic.central_events: debug # Event-Verarbeitung
    aiohomematic.client: debug # Client-Kommunikation
    aiohomematic.model: debug # Geraete-/Entity-Modell
```

Nach Aenderungen an der Logging-Konfiguration Home Assistant neu starten.

### Haeufige Log-Meldungen interpretieren

| Log-Meldung             | Bedeutung                                   | Massnahme                             |
| ----------------------- | ------------------------------------------- | ------------------------------------- |
| "Registering callback…" | Integration richtet Event-Abonnement ein    | Normal - gutes Zeichen                |
| "Subscribed…"           | Callback-Registrierung erfolgreich          | Normal - Events sollten funktionieren |
| "Connection refused"    | Verbindung zur CCU nicht moeglich           | CCU-IP/Port/Firewall pruefen          |
| "Connection timeout"    | CCU antwortet nicht                         | CCU-Status und Netzwerk pruefen       |
| "401 Unauthorized"      | Falscher Benutzername/Passwort              | Zugangsdaten ueberpruefen             |
| "403 Forbidden"         | Benutzer hat nicht genuegend Berechtigungen | CCU-Benutzerberechtigungen pruefen    |
| "404 Not Found"         | Falscher Endpunkt/Port                      | Port-Konfiguration ueberpruefen       |
| "Validation error"      | Ungueltiger Parameterwert                   | Parametername/-typ/-bereich pruefen   |

### Diagnose herunterladen

Die Integration bietet eine Funktion zum Herunterladen der Diagnose:

1. Zu **Settings** → **Devices & Services** navigieren
2. Die Homematic(IP) Local Integration finden
3. Auf das Drei-Punkte-Menue klicken
4. **Download diagnostics** auswaehlen

Diese Datei enthaelt nuetzliche Verbindungs- und Konfigurationsdaten fuer die Fehlerbehebung.

---

## 6) Beim Oeffnen eines Issues bitte folgende Informationen bereitstellen

Beim Melden von Problemen auf GitHub die folgenden Informationen fuer eine bessere Diagnose angeben:

### Umgebungsinformationen

- **CCU-Typ und Firmware-Version**: CCU3 Firmware 3.x.x, OpenCCU-Version, piVCCU/Debmatic-Version, Homegear-Version usw.
- **Home Assistant Version**: Core-Version (z.B. 2024.1.0)
- **Integrationsversion**: Homematic(IP) Local Version
- **Python-Version** (falls relevant): Entspricht normalerweise der Python-Version von Home Assistant

### Netzwerk-Setup

- **Installationstyp**: Docker, Home Assistant OS, Supervised usw.
- **Netzwerkmodus**: Host-Netzwerk, Bridge-Netzwerk, spezifische Port-Zuordnungen
- **Proxy/VPN**: Reverse-Proxy, VPN oder spezielle Netzwerkkonfiguration
- **VLANs/Subnetze**: Befinden sich Home Assistant und CCU im selben Netzwerksegment?

### Problembeschreibung

- **Genaue Symptome**: Was funktioniert genau nicht?
- **Was funktioniert**: Was funktioniert noch korrekt?
- **Wann hat es begonnen**: Nach einem Update? Nach einer Konfigurationsaenderung? Zufaellig?
- **Schritte zur Reproduktion**: Wie kann das Problem ausgeloest werden?

### Logs und Diagnose

**[Warum sind Diagnosen und Logs so wichtig?](../../contributor/testing/debug_data_importance.md)** - Verstehen, welche Daten benoetigt werden und warum vollstaendige Daten wichtig sind.

- **Debug-Logs**: Vom Home Assistant Start bis zum ersten Fehler (auf Debug-Level)
- **Diagnosedatei**: Aus der Integration herunterladen
- **Betroffene Geraete**: Liste der betroffenen Geraetetypen und -adressen
- **Geraetetypen**: Welche sind HmIP vs. klassisches Homematic?

---

## 7) Referenzen

- [Warum Diagnosen und Logs wichtig sind](../../contributor/testing/debug_data_importance.md) - Welche Daten fuer die Problemanalyse benoetigt werden und warum
- [Lifecycle-Dokumentation](../../developer/homeassistant_lifecycle.md) - Verstehen, wie Geraete und DataPoints verwaltet werden
- [aiohomematic auf GitHub](https://github.com/sukramj/aiohomematic) - Bibliotheks-Repository
- [Integrations-Repository](https://github.com/SukramJ/homematicip_local) - Homematic(IP) Local Integration fuer Home Assistant
- [Actions-Referenz](../features/homeassistant_actions.md) - Verfuegbare Actions und deren Verwendung
- [Blueprints](https://github.com/SukramJ/homematicip_local#blueprints) - Automation-Blueprints einschliesslich Reactivate
