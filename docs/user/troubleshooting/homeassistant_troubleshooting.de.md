---
translation_source: docs/user/troubleshooting/homeassistant_troubleshooting.md
translation_date: 2026-04-01
translation_source_hash: 8e9eba4a4876
---

# Häufige Probleme und Fehlerbehebung (Home Assistant)

Dieses Dokument hilft bei der schnellen Analyse und Behebung typischer Probleme bei der Verwendung von aiohomematic mit Home Assistant (Integration: Homematic(IP) Local). Die Hinweise gelten für CCU (CCU2/3, OpenCCU, piVCCU/Debmatic) und Homegear, sofern nicht anders angegeben.

!!! note
Falls Begriffe wie Integration, App, Backend, Interface oder Channel unbekannt sind, bitte zuerst das [Glossar](../../reference/glossary.md) lesen.

Inhalt:

- Schnelle Symptomzuordnung (auf einen Blick)
- Schritt-für-Schritt-Diagnose
- Häufige Probleme mit Ursachen und Lösungen
- Netzwerk/Ports/Container-Besonderheiten
- Logs und Debug-Informationen erfassen
- Wann ein Issue geöffnet werden sollte - erforderliche Informationen

---

## 1) Schnelle Symptomzuordnung

Dieser Abschnitt bietet eine schnelle Übersicht über häufige Symptome und deren wahrscheinlichste Ursachen. Er dient dazu, den Problembereich schnell einzugrenzen, bevor die detaillierten Diagnosen weiter unten durchgegangen werden.

| Symptom                                                      | Wahrscheinlichste Ursache                                                                                                                 | Siehe Abschnitt                                                            |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Keine Geräte/Entities nach der Einrichtung sichtbar          | Verbindungsdaten falsch (Host/IP, Ports, Authentifizierung), CCU nicht erreichbar oder callback nicht von der CCU aus erreichbar          | [3A](#a-keine-entities-nach-der-einrichtung)                               |
| Neue Geräte werden nicht erkannt oder unvollständig erkannt  | Veraltete Cache-Daten in Home Assistant                                                                                                   | [3H](#h-neue-gerate-werden-nicht-erkannt-oder-unvollstandig-erkannt)       |
| Entities vorhanden, aber ohne Statusänderungen               | Event-Callbacks kommen nicht an (Firewall/NAT/Docker), XML-RPC blockiert oder ungültige Sitzung                                           | [3B](#b-entities-haben-keine-aktualisierungen-nur-anfangswerte-oder-keine) |
| Einzelne Geräte "nicht verfügbar" oder auf altem Wert hängen | Geräteverfügbarkeitsproblem (UN_REACH/STICKY_UN_REACH), Funkprobleme, batteriegespeistes Gerät im Schlafmodus oder CONFIG_PENDING aktiv   | [3C](#c-einzelne-gerate-sind-nicht-verfugbar)                              |
| Werte schreiben funktioniert nicht                           | Berechtigungs-/Authentifizierungsproblem, ungültiger Parameter, Validierungsfehler, falscher Channel/Parameter oder Gerät nicht verfügbar | [3D](#d-schreiben-schlagt-fehl-service-aufruf-schlagt-fehl)                |
| HmIP-Geräte fehlen                                           | HmIP-Dienst auf der CCU nicht aktiv, falsche Ports oder Sitzungs-/Token-Problem                                                           | [3E](#e-hmip-gerate-fehlen-oder-werden-nicht-aktualisiert)                 |
| Nach CCU/Home Assistant Neustart kommen keine Updates        | Callback nicht erneut registriert, Port blockiert oder Reverse-Proxy/SSL-Terminator blockiert interne Verbindung                          | [3F](#f-keine-ereignisse-nach-neustart)                                    |
| Ping-Pong-Diskrepanz / Events gehen an falsche Instanz       | Mehrere HA-Instanzen mit gleichem `instance_name`, Callback-Registrierungskonflikt                                                        | [3J](#j-ping-pong-diskrepanz-mehrere-home-assistant-instanzen)             |
| Auto-Discovery-Benachrichtigung erscheint immer wieder       | SSDP-Seriennummer-Diskrepanz, Integration vor der Erkennung erstellt                                                                      | [3K](#k-auto-discovery-erscheint-immer-wieder)                             |
| Warnung "Error fetching initial data"                        | CCU-REGA-Skript hat ungültige Daten zurückgegeben, CCU überlastet                                                                         | [3L](#l-error-fetching-initial-data)                                       |
| Reparaturmeldung "Incomplete device data"                    | Paramset-Beschreibungen für Geräte fehlen, CCU-Datenkorruption oder Kommunikationsproblem                                                 | [3M](#m-unvollstandige-geratedaten)                                        |
| "GET_ALL_DEVICE_DATA failed" + JSONDecodeError               | Geräte-/Channel-Name enthält ungültige Zeichen, die die JSON-Ausgabe beschädigen                                                          | [3N](#n-get_all_device_data-fehlgeschlagen-json-parse-fehler)              |

---

## 2) Schritt-für-Schritt-Diagnose

Bei Problemen diese Schritte systematisch durchgehen, um die Ursache zu identifizieren:

### Schritt 1: Grundlegende Verbindungsprüfungen

Bevor integrationsspezifische Probleme untersucht werden, die grundlegende Verbindung prüfen:

- **CCU/Homegear-Erreichbarkeit**: Ist die CCU-Weboberfläche im Browser erreichbar? Falls nicht, hat möglicherweise die CCU selbst ein Problem.
- **Uhrzeit und Datum**: Ist die Uhrzeit/das Datum auf der CCU korrekt? Eine falsche Uhrzeit kann Authentifizierungsprobleme verursachen.
- **Ressourcen**: Hat die CCU genügend CPU/RAM? Die Systemdiagnose der CCU prüfen.
- **Netzwerkverbindung**: Kann Home Assistant die CCU erreichen? Versuchen, die CCU-IP vom Home Assistant Host aus anzupingen:
  ```bash
  # From Home Assistant terminal or SSH
  ping <CCU-IP-Adresse>
  ```
- **Port-Erreichbarkeit**: Sind die erforderlichen Ports geöffnet? Details im Abschnitt [Netzwerk und Ports](#4-netzwerk-ports-und-container).

### Schritt 2: Integrationskonfiguration überprüfen

Die Home Assistant Integrationseinstellungen prüfen:

- **Host/IP-Adresse**: Eine IP-Adresse statt eines Hostnamens verwenden, um DNS/mDNS-Auflösungsprobleme zu vermeiden.
- **Protokollauswahl**: Sicherstellen, dass das richtige Protokoll für die Geräte ausgewählt ist:
  - BidCos-RF für klassische Homematic-Funkgeräte
  - BidCos-Wired für kabelgebundene Homematic-Geräte
  - HmIP-RF für HomematicIP-Geräte
- **Zugangsdaten**: Benutzername und Passwort überprüfen (falls die Authentifizierung auf der CCU aktiviert ist).

### Schritt 3: Callback-Erreichbarkeit überprüfen

Dies ist entscheidend: Die CCU muss den callback-Port von Home Assistant erreichen können. Die Kommunikation ist bidirektional:

```
Home Assistant → CCU:  Befehle, Abfragen (werden von HA initiiert)
CCU → Home Assistant:  Events, Statusaenderungen (von der CCU ueber callback initiiert)
```

Zum Testen der callback-Erreichbarkeit:

1. Den callback-Port aus der Integrationsdiagnose notieren (Standard: dynamisch zugewiesen)
2. Von der CCU (bei SSH-Zugang) oder einem anderen Gerät im Netzwerk der CCU die Verbindung testen:
   ```bash
   nc -zv <Home-Assistant-IP> <callback-port>
   ```
3. Falls dies fehlschlägt, die Firewall-Regeln und Docker/Container-Netzwerkkonfiguration prüfen (siehe [Netzwerk-Abschnitt](#4-netzwerk-ports-und-container)).

### Schritt 4: Debug-Logging aktivieren

Detailliertes Logging aktivieren, um zu sehen, was passiert:

**Einfachste Methode** - Über die Home Assistant Oberfläche aktivieren:

1. Zu **Settings** → **Devices & Services** → **Homematic(IP) Local** navigieren
2. Auf **Configure** → **Enable debug logging** klicken
3. Das Problem reproduzieren
4. Auf **Disable debug logging** klicken - das Debug-Log wird als Datei zum Download angeboten

**Alternative** - Über YAML-Konfiguration:

1. Folgendes zur `configuration.yaml` hinzufügen:
   ```yaml
   logger:
     default: info
     logs:
       aiohomematic: debug
       custom_components.homematicip_local: debug
   ```
2. Home Assistant neu starten
3. Das Problem reproduzieren
4. Die Logs unter **Settings** → **System** → **Logs** prüfen

Details zur Interpretation von Log-Nachrichten im [Logging-Abschnitt](#5-logging-und-debug).

### Schritt 5: Gerätestatus auf der CCU prüfen

In der CCU-Weboberfläche den Status problematischer Geräte überprüfen:

- **Gerät erreichbar?**: Prüfen, ob das Gerät in der CCU als erreichbar angezeigt wird
- **UN_REACH/STICKY_UN_REACH**: Diese Parameter im MAINTENANCE-Channel des Geräts prüfen
- **CONFIG_PENDING**: Ist dieser Parameter `true`? Falls ja, ist die Gerätekonfiguration unvollständig

### Schritt 6: Cache und Neustart

Nach Änderungen:

1. Falls Geräteinformationen veraltet erscheinen, den Service `homematicip_local.clear_cache` verwenden
2. Home Assistant neu starten
3. In manchen Fällen auch die CCU neu starten (besonders nach Firmware-Updates oder umfangreichen Konfigurationsänderungen)

---

## 3) Häufige Probleme, Ursachen und Lösungen

### A) Keine Entities nach der Einrichtung

**Symptome:**

- Nach der Einrichtung der Integration erscheinen keine Geräte oder Entities in Home Assistant
- Die Integration wird als "geladen" angezeigt, aber die Geräteanzahl ist null

**Mögliche Ursachen:**

1. Falsche Host/IP-Adresse oder CCU-Port-Konfiguration
2. Authentifizierung fehlgeschlagen (falscher Benutzername/Passwort)
3. Erforderliche CCU-Dienste nicht gestartet
4. RPC-Methoden auf der CCU nicht verfügbar

**Diagnoseschritte:**

1. Die Home Assistant Logs auf Fehlermeldungen prüfen (nach "connection refused", "timeout", "401", "403", "404" suchen)
2. Überprüfen, ob die CCU-Weboberfläche unter der gleichen IP-Adresse erreichbar ist
3. Den XML-RPC-Port der CCU direkt testen: `http://<CCU-IP>:2001/` sollte eine XML-RPC-Antwort zeigen

**Lösungen:**

- Überprüfen, ob die Host/IP-Adresse korrekt und erreichbar ist
- Zugangsdaten nochmals prüfen (oder ohne Authentifizierung versuchen, falls diese auf der CCU deaktiviert ist)
- Die CCU neu starten, um sicherzustellen, dass alle Dienste laufen
- Die Integration in Home Assistant entfernen und neu hinzufügen

### B) Entities haben keine Aktualisierungen (nur Anfangswerte oder keine)

**Symptome:**

- Geräte erscheinen in Home Assistant, aber ihre Zustände ändern sich nie
- Sensorwerte bleiben auf dem Anfangswert stehen
- Tastendrücke oder Schalterbetätigungen an physischen Geräten aktualisieren Home Assistant nicht

**Mögliche Ursachen:**

1. Event-Callback von der CCU zu Home Assistant ist blockiert
2. Firewall blockiert eingehende Verbindungen zu Home Assistant
3. NAT/Docker-Netzwerkkonfiguration verhindert, dass die CCU den callback-Port erreicht
4. Callback-IP-Adresse ist falsch (z.B. interne Docker-IP statt Host-IP)

**Warum das passiert:**

Die CCU sendet Statusänderungen als "Events" an Home Assistant über eine callback-Verbindung. Wenn dieser callback blockiert ist, kann Home Assistant die CCU zwar noch abfragen (daher funktionieren Anfangswerte), erhält aber keine Aktualisierungen.

**Diagnoseschritte:**

1. Logs auf "Registering callback"- oder "Subscribed"-Meldungen prüfen
2. Vom Netzwerk der CCU aus überprüfen, ob der callback-Port erreichbar ist (siehe Schritt 3 der Diagnose)
3. Firewall-Regeln prüfen (ufw, iptables, Windows Firewall)

**Lösungen:**

- **Docker-Nutzer**: Host-Netzwerkmodus verwenden (`network_mode: host`) oder den callback-Port korrekt veröffentlichen
- **Firewall**: Eingehende Verbindungen auf dem callback-Port von der IP der CCU erlauben
- **Callback-IP prüfen**: In der Integrationskonfiguration sicherstellen, dass die callback-IP eine ist, die die CCU tatsächlich erreichen kann
- **IP-Änderungen vermeiden**: Statische IPs oder DHCP-Reservierungen für Home Assistant und CCU verwenden

### C) Einzelne Geräte sind "nicht verfügbar"

**Symptome:**

- Ein oder mehrere Geräte werden in Home Assistant als "nicht verfügbar" angezeigt
- Das Gerät hat zuvor funktioniert, wurde aber plötzlich nicht verfügbar
- Die CCU-Weboberfläche zeigt das Gerät möglicherweise als "erreichbar" an, aber Home Assistant zeigt es als nicht verfügbar

**Geräteverfügbarkeit verstehen:**

Die Integration markiert Geräte basierend auf **UNREACH-Events** von der CCU als nicht verfügbar. Dies ist wichtig zu verstehen:

1. **Funktionsweise**: Wenn ein Gerät nicht auf die Kommunikationsversuche der CCU antwortet, setzt die CCU den Parameter `UN_REACH` auf `true` und sendet diese Information über ein Event an Home Assistant
2. **Die Integration reagiert auf dieses Event**, indem sie alle Entities dieses Geräts in Home Assistant als "nicht verfügbar" markiert
3. **Dies ist beabsichtigtes Verhalten**: Es stellt sicher, dass Home Assistant Kommunikationsprobleme zwischen der CCU und dem Gerät korrekt widerspiegelt

**Warum die CCU-Weboberfläche einen anderen Status anzeigen kann:**

Die CCU-Weboberfläche kann den Gerätestatus anders darstellen als Home Assistant. Die **Integration reagiert jedoch ausschließlich auf die UNREACH-Events**, die sie von der CCU erhält. Sie versucht nicht, das Verhalten der CCU zu interpretieren oder zu hinterfragen. Wenn die CCU ein UNREACH-Event sendet, markiert die Integration das Gerät als nicht verfügbar.

**Mögliche Ursachen:**

1. **Funk-/Drahtlosprobleme**: Gerät außerhalb der Reichweite, Störungen oder schwaches Signal
2. **Batteriebetriebene Geräte**: Gerät befindet sich im Schlafmodus und hat die Abfrage der CCU verpasst
3. **Gerät physisch nicht erreichbar**: Stromausfall, Gerätedefekt oder Gerät entfernt
4. **STICKY_UNREACH**: Ein früherer Kommunikationsfehler, der nicht zurückgesetzt wurde
5. **CONFIG_PENDING**: Gerätekonfiguration ist unvollständig

**Diagnoseschritte:**

1. In der CCU-Weboberfläche den MAINTENANCE-Channel des Geräts prüfen:
   - `UNREACH`: Derzeit nicht erreichbar
   - `STICKY_UNREACH`: War irgendwann nicht erreichbar (manuelles Zurücksetzen erforderlich)
   - `CONFIG_PENDING`: Konfiguration noch nicht angewendet
2. Das physische Gerät prüfen (Batterien, Stromversorgung, Standort)
3. Versuchen, das Gerät manuell auszulösen (Taste drücken), um die Kommunikation zu erzwingen

**Lösungen:**

- **Funkreichweite verbessern**: Gerät näher platzieren oder einen Repeater hinzufügen (jedes netzbetriebene Homematic-Gerät fungiert als Repeater)
- **Batterien ersetzen**: Auch wenn das Gerät noch funktioniert, können schwache Batterien intermittierende Kommunikationsprobleme verursachen
- **STICKY_UNREACH zurücksetzen**: In der CCU-Weboberfläche `STICKY_UNREACH` für das Gerät auf `false` setzen
- **Auf CONFIG_PENDING warten**: Nach dem Pairing oder Konfigurationsänderungen warten, bis `CONFIG_PENDING` `false` wird
- **Gerät neu pairen**: Als letzten Ausweg das Gerät von der CCU entfernen und erneut pairen

**Alternatives Verhalten (Verfügbarkeit erzwingen):**

Wenn Geräte trotz UNREACH-Events in Home Assistant als verfügbar angezeigt werden sollen (ähnlich wie manche das Verhalten der CCU-Weboberfläche interpretieren), gibt es zwei Möglichkeiten:

1. **Service-Aufruf**: Den Service `homematicip_local.force_device_availability` verwenden, um ein Gerät manuell als verfügbar zu markieren. Details in der [Actions-Referenz](../features/homeassistant_actions.md#homematicip_localforce_device_availability).

2. **Automation mit Blueprint**: Die "Reactivate"-Blueprints verwenden, um die Geräteverfügbarkeit nach UNREACH-Events automatisch wiederherzustellen. Diese Blueprints überwachen UNREACH-Events und rufen automatisch den Service zur Erzwingung der Verfügbarkeit auf. Siehe die [Blueprints](https://github.com/SukramJ/homematicip_local#blueprints) im Integrations-Repository.

**Hinweis:** Die Verwendung dieser Optionen bedeutet, dass Home Assistant das Gerät als verfügbar anzeigt, auch wenn die Kommunikation mit der CCU beeinträchtigt ist. Mit Vorsicht verwenden, da dadurch tatsächliche Geräteprobleme verborgen werden können.

### D) Schreiben schlägt fehl (Service-Aufruf schlägt fehl)

**Symptome:**

- Service-Aufrufe zur Gerätesteuerung schlagen mit einem Fehler fehl
- Schalter schalten nicht, Lichter gehen nicht an, Thermostate ändern die Temperatur nicht
- Fehlermeldungen erscheinen im Home Assistant Log

**Mögliche Ursachen:**

1. **Validierungsfehler**: Falscher Parametername, -typ oder -wertebereich
2. **Gerät nicht verfügbar**: Das Gerät ist als nicht verfügbar markiert (siehe Abschnitt C)
3. **Falscher Channel**: Der Parameter existiert auf einem anderen Channel als erwartet
4. **Berechtigungsproblem**: CCU-Benutzer hat keine Schreibrechte
5. **Gerät beschäftigt**: Das Gerät verarbeitet einen anderen Befehl

**Diagnoseschritte:**

1. Die Home Assistant Logs auf die spezifische Fehlermeldung prüfen
2. Überprüfen, ob das Gerät verfügbar ist (nicht als nicht verfügbar angezeigt)
3. In der CCU-Weboberfläche die Paramset-Beschreibung auf gültige Werte prüfen

**Häufige Validierungsfehler und Lösungen:**

| Fehler               | Ursache                 | Lösung                                                              |
| -------------------- | ----------------------- | ------------------------------------------------------------------- |
| "Value out of range" | Zahl zu hoch/zu niedrig | Die MIN/MAX-Werte des Parameters prüfen                             |
| "Invalid parameter"  | Falscher Parametername  | Den genauen Parameternamen in der CCU überprüfen                    |
| "Invalid channel"    | Falsche Channel-Nummer  | Den richtigen Channel für diesen Parameter finden                   |
| "Invalid type"       | Falscher Datentyp       | Korrekten Typ verwenden (Zahl vs. Zeichenkette vs. Boolescher Wert) |

**Lösungen:**

- Die Entity-Attribute in Home Assistant prüfen, um gültige Wertebereiche zu sehen
- Die CCU-Weboberfläche verwenden, um zu testen, ob der Parameter dort gesetzt werden kann
- Überprüfen, ob der in der Integration konfigurierte Benutzer Schreibrechte hat
- Sicherstellen, dass das Gerät verfügbar ist, bevor Befehle gesendet werden

### E) HmIP-Geräte fehlen oder werden nicht aktualisiert

**Symptome:**

- HomematicIP (HmIP)-Geräte erscheinen nicht in Home Assistant
- HmIP-Geräte erscheinen, werden aber nicht aktualisiert oder reagieren nicht auf Befehle
- Klassische Homematic-Geräte funktionieren einwandfrei, aber HmIP-Geräte nicht

**Mögliche Ursachen:**

1. HmIP-Dienst auf der CCU läuft nicht oder ist nicht korrekt gekoppelt
2. Falsche Port-Konfiguration (HmIP verwendet andere Ports als klassisches Homematic)
3. JSON-RPC-Sitzung/Token abgelaufen oder ungültig
4. HmIP-Funkmodul der CCU funktioniert nicht

**Diagnoseschritte:**

1. In der CCU-Weboberfläche unter **Settings** → **System Control** prüfen, ob der HmIP-Dienst läuft
2. Prüfen, ob HmIP-Geräte in der CCU-Weboberfläche selbst funktionieren
3. In den Home Assistant Logs nach JSON-RPC-bezogenen Fehlern suchen
4. Überprüfen, ob Port 2010 (oder 42010 für TLS) erreichbar ist

**Lösungen:**

- Die CCU neu starten, um alle Dienste einschließlich HmIP neu zu starten
- Die Systemdiagnose der CCU auf den Status des HmIP-Funkmoduls prüfen
- Die Home Assistant Integration neu starten (oder Home Assistant komplett neu starten)
- Falls die Probleme bestehen bleiben, die HmIP-Geräte in der CCU neu pairen

### F) Keine Ereignisse nach Neustart

**Symptome:**

- Nach dem Neustart von Home Assistant oder der CCU zeigen Geräte Anfangswerte, werden aber nicht aktualisiert
- Vor dem Neustart hat alles funktioniert
- Logs zeigen, dass die Integration erfolgreich gestartet wurde

**Mögliche Ursachen:**

1. Callback-Registrierung nach dem Neuverbinden fehlgeschlagen
2. Der callback-Port ist jetzt blockiert oder wird von einem anderen Prozess verwendet
3. Ein Reverse-Proxy oder SSL-Terminator stört die callback-Verbindung
4. Die CCU hat das callback-Abonnement nicht erneut hergestellt

**Diagnoseschritte:**

1. Logs nach "Registering callback"-Meldungen nach dem Neustart prüfen
2. Überprüfen, ob der callback-Port noch verfügbar ist und nicht von einem anderen Dienst verwendet wird
3. Falls ein Reverse-Proxy verwendet wird, prüfen, ob dieser die callback-Verbindung zulässt

**Lösungen:**

- Die Integration über **Settings** → **Devices & Services** → Homematic(IP) Local → **Reload** neu starten
- Bei Verwendung von Docker mit Bridge-Netzwerk sicherstellen, dass die Port-Zuordnungen noch korrekt sind
- Bei anhaltenden Problemen den Host-Netzwerkmodus in Docker versuchen
- Prüfen, ob kürzliche Netzwerkänderungen die Verbindung beeinträchtigt haben könnten

### G) CONFIG_PENDING bleibt True

**Symptome:**

- Der Parameter `CONFIG_PENDING` eines Geräts bleibt dauerhaft `true`
- Das Gerät funktioniert möglicherweise teilweise, erscheint aber unvollständig
- Einige Funktionen oder Parameter fehlen

**CONFIG_PENDING verstehen:**

`CONFIG_PENDING` zeigt an, dass das Gerät eine Konfiguration hat, die übertragen werden muss, aber noch nicht vollständig angewendet wurde. Dies ist häufig:

- Nach dem erstmaligen Pairing
- Nach dem Ändern von Geräteeinstellungen in der CCU
- Bei batteriebetriebenen Geräten, die aufwachen müssen, um die Konfiguration zu empfangen

**Mögliche Ursachen:**

1. Batteriebetriebenes Gerät schläft und ist nicht aufgewacht, um die Konfiguration zu empfangen
2. Gerät außerhalb der Funkreichweite
3. Konfigurationsprozess wurde unterbrochen
4. Gerät hat ein Problem, das den Abschluss der Konfiguration verhindert

**Lösungen:**

- **Batteriegeräte**: Eine Taste am Gerät drücken, um es aufzuwecken und die Konfigurationsübertragung auszulösen
- **Warten**: Einige Geräte können mehrere Stunden benötigen, um die Konfiguration abzuschließen (besonders batteriebetriebene)
- **Reichweite prüfen**: Sicherstellen, dass das Gerät in Funkreichweite der CCU oder eines Repeaters ist
- **Neu pairen**: Falls nichts anderes hilft, das Gerät von der CCU entfernen und erneut pairen
- **Hinweis**: aiohomematic aktualisiert automatisch die MASTER-Parameter, sobald `CONFIG_PENDING` `false` wird

### H) Neue Geräte werden nicht erkannt oder unvollständig erkannt

**Symptome:**

- Ein neues Gerät wurde zur CCU hinzugefügt, erscheint aber nicht in Home Assistant
- Ein Gerät erscheint, aber Channels oder Entities fehlen
- Gerät hat zuvor funktioniert, ist aber nach einem CCU-Update unvollständig

**Mögliche Ursachen:**

1. Der Cache von Home Assistant enthält veraltete Geräteinformationen
2. Das Gerät war beim letzten Cache-Aufbau nicht vollständig gepairt
3. Die CCU hat neue Geräteinformationen, aber Home Assistant hat diese nicht abgerufen
4. Gerätekonfiguration hat sich geändert, aber der Cache wurde nicht invalidiert

**Den Cache verstehen:**

aiohomematic cached Gerätebeschreibungen und Parameterinformationen für einen schnelleren Start. Dieser Cache wird normalerweise automatisch aktualisiert, kann aber in manchen Situationen veraltet sein.

**Lösungen:**

1. **Cache leeren**: Den Service `homematicip_local.clear_cache` verwenden:
   - Zu **Developer Tools** → **Actions** in Home Assistant navigieren
   - Nach `homematicip_local.clear_cache` suchen
   - Die Integrationsinstanz auswählen
   - Auf **Call Service** klicken
2. **Home Assistant neu starten** nach dem Leeren des Cache
3. Dies erzwingt eine erneute Erkennung aller Geräte und ihrer Parameter

Weitere Details zum clear_cache-Service in der [Actions-Referenz](../features/homeassistant_actions.md#homematicip_localclear_cache).

### I) Unifi-Firewall-Alarme: "ET EXPLOIT HTTP POST with Common Ruby RCE Technique in Body"

**Symptome:**

- Unifi-Firewall zeigt Sicherheitswarnungen für den Datenverkehr zwischen Home Assistant und CCU
- Alarmmeldung erwähnt "Ruby RCE" oder ähnliche Exploit-Erkennung
- Homematic-Kommunikation wird möglicherweise blockiert oder ist intermittierend

**Diesen Alarm verstehen:**

Dies ist ein **Fehlalarm (False Positive)**. Die Unifi-Firewall verwendet Suricata IDS (Intrusion Detection System), das XML-RPC-Kommunikation fälschlicherweise als potenziellen Exploit identifiziert. Der Grund:

- XML-RPC verwendet Tags wie `<methodCall>`, `<methodName>` und `<params>`
- Diese Tags ähneln Mustern, die in Ruby-Marshal-Daten vorkommen
- Suricata-Regel SID 2019401 wird durch diese Muster ausgelöst, da sie als Ruby-Code-Injection-Versuch interpretiert werden
- **Der Datenverkehr ist vollständig legitime** Homematic-Kommunikation

**Lösungen:**

1. **IDS-Unterdrückungsregel erstellen** (empfohlen):

   - In der Unifi Network Console zu **Settings** → **Security** → **Threat Management** navigieren
   - Unter **Suppression** eine Ausnahme hinzufügen:
     - Quell-IP: Die IP von Home Assistant
     - Ziel-IP: Die IP der CCU
     - Oder die Signatur-ID `2019401` für den Datenverkehr zwischen diesen Hosts unterdrücken

2. **TLS-verschlüsselte Ports verwenden** (Alternative):
   - Die Integration auf verschlüsselte Ports konfigurieren (z.B. 42001 statt 2001)
   - Dies verhindert, dass das IDS den Payload-Inhalt inspiziert

**Hinweis:** Dieser Alarm ist harmlos für legitime CCU-Kommunikation und kann sicher unterdrückt werden.

### J) Ping-Pong-Diskrepanz (mehrere Home Assistant Instanzen)

**Symptome:**

- Reparaturbenachrichtigung: "Pending Pong mismatch" oder "Ping-pong mismatch"
- Geräte werden nicht mehr aktualisiert oder aktualisieren intermittierend
- Einige Events scheinen "verloren" zu gehen

**Den Ping-Pong-Mechanismus verstehen:**

Die Integration verwendet einen Heartbeat-Mechanismus zur Überprüfung der Kommunikation:

1. Home Assistant sendet alle 15 Sekunden einen PING an die CCU
2. Die CCU antwortet mit einem PONG zurück an Home Assistant
3. Wenn die Anzahl von PINGs und PONGs nicht übereinstimmt, liegt ein Kommunikationsproblem vor

**Szenario 1: Weniger PONGs empfangen als PINGs gesendet**

- **Ursache:** Eine andere Home Assistant Instanz mit dem **gleichen `instance_name`** wurde nach dieser gestartet
- **Auswirkung:** Die neuere Instanz hat die callback-Registrierung "übernommen" - sie empfängt nun alle Events
- **Alternative Ursache:** Netzwerkproblem oder CCU-Kommunikationsproblem

**Szenario 2: Mehr PONGs empfangen als PINGs gesendet**

- **Ursache:** Eine andere Home Assistant Instanz mit dem **gleichen `instance_name`** wurde vor dieser gestartet
- **Auswirkung:** Diese Instanz empfängt PONGs von beiden Registrierungen

**Lösungen:**

1. **Eindeutige Instanznamen sicherstellen**: Jede Home Assistant Installation, die sich mit derselben CCU verbindet, muss einen eindeutigen `instance_name` haben
2. **Auf doppelte Integrationen prüfen**: Doppelte Integrationseinträge entfernen
3. **Betroffene Instanz neu starten**: Dies registriert den callback korrekt neu
4. **Netzwerkprobleme**: Falls nur eine HA-Instanz existiert, Firewall und Netzwerkverbindung prüfen

**Wichtig:** Der `instance_name` wird bei der Ersteinrichtung festgelegt und sollte danach nie geändert werden (Entities würden neu erstellt). Von Anfang an eindeutige Namen wählen.

### K) Auto-Discovery erscheint immer wieder

**Symptome:**

- SSDP-Discovery-Benachrichtigung erscheint immer wieder, obwohl die CCU bereits konfiguriert ist
- Nach dem Klicken auf "Ignore" erscheint die Erkennung nach einem Home Assistant Neustart erneut
- Mehrere Erkennungseinträge für dieselbe CCU

**Mögliche Ursachen:**

1. Die Seriennummer der CCU im SSDP stimmt nicht mit dem konfigurierten Eintrag überein
2. Der Integrationseintrag wurde vor der Erkennung manuell erstellt
3. Die SSDP-Antwort enthält andere Identifikatoren als erwartet

**Lösungen:**

1. Auf **"Ignore"** bei der Erkennungsbenachrichtigung klicken
2. **Oder den vorhandenen Integrationseintrag neu konfigurieren**, um ihn mit der Erkennung zu verknüpfen
3. **Home Assistant neu starten** nach dem Ignorieren
4. Falls das Problem weiterhin besteht, prüfen, ob sich die Netzwerkkonfiguration der CCU geändert hat (IP, Hostname)

**Hinweis:** Dies ist ein kosmetisches Problem - die vorhandene Integration funktioniert weiterhin normal.

### L) Error fetching initial data

**Symptome:**

- Warnung in den Logs: "Error fetching initial data" oder "GET_ALL_DEVICE_DATA failed"
- Integration wird geladen, aber der Start ist langsamer
- Höhere CCU-Last während des Starts

**Dieses Problem verstehen:**

Die Integration verwendet optimierte REGA-Skripte, um Gerätedaten gebündelt abzurufen. Falls dies fehlschlägt, wird auf einzelne Anfragen zurückgegriffen (langsamer, aber funktional).

**Dies ist typischerweise KEIN Integrations-Bug** - es handelt sich normalerweise um ein CCU-Datenproblem.

**Mögliche Ursachen:**

1. Das REGA-Skript der CCU hat ungültige oder fehlerhafte Daten zurückgegeben
2. Ein bestimmtes Gerät hat beschädigte Daten in der CCU
3. CCU ist überlastet oder die REGA-Engine ist blockiert
4. Sehr große Geräteanzahl verursacht einen Timeout

**Diagnoseschritte:**

1. Das [REGA-Skript](https://github.com/sukramj/aiohomematic/blob/devel/aiohomematic/rega_scripts/fetch_all_device_data.fn) herunterladen
2. `##interface##` (Zeile 17) durch die Schnittstelle aus der Fehlermeldung ersetzen (z.B. `HmIP-RF`)
3. Das Skript in der CCU-Weboberfläche ausführen: **Settings** → **Control panel** → **Execute script**
4. Prüfen, ob die Ausgabe gültiges JSON ist
5. Nach fehlerhaften Einträgen oder unerwarteten Zeichen suchen

**Lösungen:**

- **CCU neu starten**, um blockierte REGA-Prozesse zu beenden
- **Auf problematische Geräte prüfen** in der Skriptausgabe
- **In den [Diskussionen](https://github.com/sukramj/aiohomematic/discussions) posten** mit der Skriptausgabe für Hilfe

### M) Unvollständige Gerätedaten

**Symptome:**

- Home Assistant zeigt eine Reparaturmeldung: "Incomplete device data"
- Neue Geräte, die mit der CCU gepairt wurden, erscheinen nicht in Home Assistant
- Einigen Geräten fehlen Entities oder sie zeigen unvollständige Funktionalität
- Log-Meldungen erwähnen "devices still missing paramsets after fetch"

**Dieses Problem verstehen:**

Wenn neue Geräte erkannt werden, ruft aiohomematic deren Paramset-Beschreibungen von der CCU ab. Diese Beschreibungen definieren die Parameter, Channels und Fähigkeiten des Geräts. Ohne sie können Geräte nicht in Home Assistant erstellt werden.

Dieses Problem tritt auf, wenn:

1. Die CCU neue Geräte meldet, aber
2. Die Paramset-Beschreibungen für diese Geräte nicht abgerufen werden können, auch nicht nach mehreren Versuchen

**Mögliche Ursachen:**

1. **CCU-Datenkorruption**: Die Gerätedaten in der internen Datenbank der CCU sind beschädigt
2. **Kommunikationsprobleme**: Intermittierende Netzwerkprobleme zwischen Home Assistant und CCU
3. **CCU-Überlastung**: Die CCU ist überlastet und kann nicht auf Paramset-Anfragen antworten
4. **Unvollständiges Pairing**: Der Pairing-Prozess des Geräts wurde nicht korrekt abgeschlossen
5. **CUxD/Add-on-Probleme**: Bei virtuellen Geräten (CUxD) kann das Add-on Konfigurationsprobleme haben

**Diagnoseschritte:**

1. **Details der Reparaturmeldung prüfen**: Die Reparaturbenachrichtigung enthält die betroffenen Geräteadressen (z.B. `NEQ1234567`, `CUX2800001`)
2. **Geräte in der CCU-Weboberfläche überprüfen**: Prüfen, ob die betroffenen Geräte korrekt in der Geräteliste der CCU erscheinen
3. **CCU-Systemdiagnose prüfen**: Auf hohe CPU-/Speicherauslastung oder Dienstfehler achten
4. **Home Assistant Logs prüfen**: Debug-Logging aktivieren und nach Fehlern im Zusammenhang mit `fetch_paramsets` oder den spezifischen Geräteadressen suchen

**Lösungen:**

1. **CCU neu starten**: Dies löst häufig temporäre Kommunikations- oder Dienstprobleme

   - Die CCU über ihre Weboberfläche oder physisch neu starten
   - Warten, bis alle Dienste vollständig gestartet sind (kann mehrere Minuten dauern)
   - Die Home Assistant Integration neu starten

2. **Betroffene Geräte neu pairen**:

   - Das Gerät von der CCU entfernen
   - Das Gerät auf Werkseinstellungen zurücksetzen (siehe Gerätehandbuch)
   - Das Gerät erneut mit der CCU pairen
   - Warten, bis `CONFIG_PENDING` `false` wird
   - Den Cache in Home Assistant leeren und neu starten

3. **Den Integrations-Cache leeren**:

   - Den Service `homematicip_local.clear_cache` verwenden
   - Home Assistant neu starten
   - Dies erzwingt ein vollständiges erneutes Abrufen aller Gerätedaten

4. **Für CUxD/virtuelle Geräte**:

   - Den Status des CUxD-Add-ons in der CCU prüfen
   - Das CUxD-Add-on neu starten
   - Überprüfen, ob die Konfiguration des virtuellen Geräts vollständig ist

5. **Auf CCU-Firmware-Probleme prüfen**:
   - Sicherstellen, dass die CCU-Firmware aktuell ist
   - Einige Firmware-Versionen haben bekannte Probleme mit Paramset-Abfragen
   - Ein Update oder Rollback in Betracht ziehen, falls die Probleme nach einem Firmware-Update aufgetreten sind

**Falls das Problem weiterhin besteht:**

- Die Diagnose aus der Integration herunterladen und auf Fehlermuster prüfen
- In den [Diskussionen](https://github.com/sukramj/aiohomematic/discussions) posten mit:
  - Den betroffenen Geräteadressen aus der Reparaturmeldung
  - Gerätetypen (Modellnummern)
  - CCU-Typ und Firmware-Version
  - Debug-Logs, die die Abrufversuche zeigen

### N) GET_ALL_DEVICE_DATA fehlgeschlagen (JSON-Parse-Fehler)

**Symptome:**

- Fehler in den Logs: `GET_ALL_DEVICE_DATA failed: Unable to fetch device data for interface X`
- Traceback zeigt `orjson.JSONDecodeError: unexpected character: line X column Y`
- Integration startet nicht oder wird ohne Gerätedaten geladen

**Dieses Problem verstehen:**

Die Integration ruft alle Gerätedaten über JSON-RPC ab, indem ein ReGa-Skript auf der CCU ausgeführt wird. Das Skript gibt Gerätewerte als JSON zurück. Wenn ein Gerätename, Channel-Name oder Wert Sonderzeichen enthält, die die JSON-Syntax beschädigen, schlägt das Parsen fehl.

**Häufige Ursachen:**

1. Geräte- oder Channel-Name enthält nicht-escapte Anführungszeichen (`"`) oder Backslashes (`\`)
2. Gerätename enthält Steuerzeichen oder ungewöhnliches Unicode
3. Ein numerischer Wert ist ungültig (z.B. `NaN`, `Infinity` oder fehlerhafte Zahl)
4. Kopierter Text mit unsichtbaren Zeichen in Gerätenamen

**Diagnoseschritte:**

Anders als bei anderen Problemen erfordert dies direktes JSON-RPC-Debugging, da das ReGa-Skript nicht einfach manuell ausgeführt werden kann.

1. **Bei der CCU über JSON-RPC anmelden** (Sitzungs-ID erhalten):

   ```bash
   curl -s -X POST "http://<CCU-IP>/api/homematic.cgi" \
     -H "Content-Type: application/json" \
     -d '{"method":"Session.login","params":{"username":"<USER>","password":"<PASSWORD>"}}'
   ```

   Antwort: `{"result":"<SESSION_ID>","error":null}`

2. **Das Gerätedaten-Skript ausführen** (`<SESSION_ID>` und `<INTERFACE>` ersetzen):

   Gültige Schnittstellen: `BidCos-RF`, `BidCos-Wired`, `HmIP-RF`, `VirtualDevices`

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

**Lösungen:**

1. **Das problematische Gerät identifizieren** anhand der Zeile/Spalte in der Fehlermeldung
2. **Das Gerät/den Channel in der CCU-Weboberfläche umbenennen**, um Sonderzeichen zu entfernen:
   - Anführungszeichen entfernen: `"`, `'`
   - Backslashes entfernen: `\`
   - Steuerzeichen entfernen (den Namen neu eintippen statt kopieren/einfügen)
3. **Die Integration neu starten** nach der Korrektur des Namens

**Beispiele für problematische Namen:**

| Problematischer Name | Problem                           | Korrigierter Name  |
| -------------------- | --------------------------------- | ------------------ |
| `Wohnzimmer "Lampe"` | Enthält Anführungszeichen         | `Wohnzimmer Lampe` |
| `Sensor\Fenster`     | Enthält Backslash                 | `Sensor Fenster`   |
| `Tuer­sensor`        | Versteckter bedingter Trennstrich | `Tuersensor`       |

**Hinweis:** Dies ist ein Datenproblem auf der CCU, kein Integrations-Bug. Die Integration kann kein ungültiges JSON verarbeiten, das von der REGA-Engine der CCU zurückgegeben wird.

---

## 4) Netzwerk, Ports und Container

### Erforderliche Ports

| Protokoll    | Standard-Port | TLS-Port | Beschreibung                            |
| ------------ | ------------- | -------- | --------------------------------------- |
| BidCos-RF    | 2001          | 42001    | Klassisches Homematic-Funksystem        |
| BidCos-Wired | 2000          | 42000    | Klassisches Homematic kabelgebunden     |
| HmIP-RF      | 2010          | 42010    | HomematicIP                             |
| Groups       | 9292          | 49292    | Heizungsgruppen (virtueller Thermostat) |
| JSON-RPC     | 80/443        | -        | CCU-WebUI-API (verwendet für HmIP)      |

### Callback-Verbindung

Der callback ist die **umgekehrte Verbindung** von der CCU zu Home Assistant:

```
┌─────────────────┐                      ┌─────────────────┐
│  Home Assistant │ ◄──── Callback ───── │       CCU       │
│   (Port XXXXX)  │                      │                 │
└─────────────────┘                      └─────────────────┘
```

- Home Assistant öffnet einen Port und teilt der CCU mit: "Sende Events an diese IP und diesen Port"
- Die CCU verbindet sich dann mit Home Assistant, wenn Ereignisse auftreten
- **Dieser Port muss vom Netzwerk der CCU aus erreichbar sein**

### Docker und Container-Netzwerke

**Host-Netzwerk (empfohlen für einfache Einrichtung):**

```yaml
# docker-compose.yml
services:
  homeassistant:
    network_mode: host
    # Keine Port-Zuordnungen noetig - Container nutzt das Netzwerk des Hosts direkt
```

- Die CCU kann Home Assistant über die IP des Hosts erreichen
- Keine Komplikationen bei Port-Zuordnungen
- Callback funktioniert automatisch

**Bridge-Netzwerk (erfordert sorgfältige Konfiguration):**

```yaml
# docker-compose.yml
services:
  homeassistant:
    ports:
      - "8123:8123" # Home Assistant Weboberfläche
      # Callback-Port wird dynamisch zugewiesen - möglicherweise muss ein statischer Port konfiguriert werden
```

- Sicherstellen, dass der callback-Port veröffentlicht wird
- Die callback-IP muss die IP des Docker-Hosts sein, nicht die interne IP des Containers
- Die Verwendung eines statischen callback-Ports in der Integrationskonfiguration in Betracht ziehen

### Firewall-Hinweise

Häufige Firewalls, die den callback blockieren können:

| Firewall                | Prüfbefehl                     | Konfigurationsort                |
| ----------------------- | ------------------------------ | -------------------------------- |
| ufw (Ubuntu)            | `sudo ufw status`              | `/etc/ufw/user.rules`            |
| firewalld (Fedora/RHEL) | `sudo firewall-cmd --list-all` | `firewall-cmd`-Befehle           |
| iptables                | `sudo iptables -L`             | `/etc/iptables/rules.v4`         |
| Windows Firewall        | `Get-NetFirewallRule`          | Windows-Sicherheitseinstellungen |
| NAS-Firewalls           | Variiert                       | NAS-Administrationsoberfläche    |

**Beispiel: Callback-Port mit ufw erlauben:**

```bash
sudo ufw allow from <CCU-IP> to any port <callback-port> proto tcp
```

---

## 5) Logging und Debug

### Debug-Logging aktivieren

**Einfachste Methode** - Über die Home Assistant Oberfläche aktivieren:

1. Zu **Settings** → **Devices & Services** → **Homematic(IP) Local** navigieren
2. Auf **Configure** → **Enable debug logging** klicken
3. Das Problem reproduzieren
4. Auf **Disable debug logging** klicken - das Debug-Log wird als Datei zum Download angeboten

**Alternative** - Über YAML-Konfiguration:

Folgendes zur `configuration.yaml` hinzufügen:

```yaml
logger:
  default: info
  logs:
    # Haupt-Integrations-Logging
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

Für gezieltes Logging können spezifische Module aktiviert werden:

```yaml
logger:
  default: info
  logs:
    # Spezifische Module fuer gezieltes Debugging
    aiohomematic.caches: debug # Cache-Operationen
    aiohomematic.central: debug # Zentralen-Operationen
    aiohomematic.central_events: debug # Event-Verarbeitung
    aiohomematic.client: debug # Client-Kommunikation
    aiohomematic.model: debug # Geräte-/Entity-Modell
```

Nach Änderungen an der Logging-Konfiguration Home Assistant neu starten.

### Häufige Log-Meldungen interpretieren

| Log-Meldung             | Bedeutung                                  | Maßnahme                              |
| ----------------------- | ------------------------------------------ | ------------------------------------- |
| "Registering callback…" | Integration richtet Event-Abonnement ein   | Normal - gutes Zeichen                |
| "Subscribed…"           | Callback-Registrierung erfolgreich         | Normal - Events sollten funktionieren |
| "Connection refused"    | Verbindung zur CCU nicht möglich           | CCU-IP/Port/Firewall prüfen           |
| "Connection timeout"    | CCU antwortet nicht                        | CCU-Status und Netzwerk prüfen        |
| "401 Unauthorized"      | Falscher Benutzername/Passwort             | Zugangsdaten überprüfen               |
| "403 Forbidden"         | Benutzer hat nicht genügend Berechtigungen | CCU-Benutzerberechtigungen prüfen     |
| "404 Not Found"         | Falscher Endpunkt/Port                     | Port-Konfiguration überprüfen         |
| "Validation error"      | Ungültiger Parameterwert                   | Parametername/-typ/-bereich prüfen    |

### Diagnose herunterladen

Die Integration bietet eine Funktion zum Herunterladen der Diagnose:

1. Zu **Settings** → **Devices & Services** navigieren
2. Die Homematic(IP) Local Integration finden
3. Auf das Drei-Punkte-Menü klicken
4. **Download diagnostics** auswählen

Diese Datei enthält nützliche Verbindungs- und Konfigurationsdaten für die Fehlerbehebung.

---

## 6) Beim Öffnen eines Issues bitte folgende Informationen bereitstellen

Beim Melden von Problemen auf GitHub die folgenden Informationen für eine bessere Diagnose angeben:

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
- **Wann hat es begonnen**: Nach einem Update? Nach einer Konfigurationsänderung? Zufällig?
- **Schritte zur Reproduktion**: Wie kann das Problem ausgelöst werden?

### Logs und Diagnose

**[Warum sind Diagnosen und Logs so wichtig?](../../contributor/testing/debug_data_importance.md)** - Verstehen, welche Daten benötigt werden und warum vollständige Daten wichtig sind.

- **Debug-Logs**: Vom Home Assistant Start bis zum ersten Fehler (auf Debug-Level)
- **Diagnosedatei**: Aus der Integration herunterladen
- **Betroffene Geräte**: Liste der betroffenen Gerätetypen und -adressen
- **Gerätetypen**: Welche sind HmIP vs. klassisches Homematic?

---

## 7) Referenzen

- [Warum Diagnosen und Logs wichtig sind](../../contributor/testing/debug_data_importance.md) - Welche Daten für die Problemanalyse benötigt werden und warum
- [Lifecycle-Dokumentation](../../developer/homeassistant_lifecycle.md) - Verstehen, wie Geräte und DataPoints verwaltet werden
- [aiohomematic auf GitHub](https://github.com/sukramj/aiohomematic) - Bibliotheks-Repository
- [Integrations-Repository](https://github.com/SukramJ/homematicip_local) - Homematic(IP) Local Integration für Home Assistant
- [Actions-Referenz](../features/homeassistant_actions.md) - Verfügbare Actions und deren Verwendung
- [Blueprints](https://github.com/SukramJ/homematicip_local#blueprints) - Automation-Blueprints einschließlich Reactivate
