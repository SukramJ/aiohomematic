---
translation_source: docs/user/features/config_panel.md
translation_date: 2026-04-01
translation_source_hash: dd3410609095
---

# Konfigurationspanel für Geräte

Das Homematic-Konfigurationspanel für Geräte ist ein Seitenleistenpanel in Home Assistant zum Bearbeiten von Geräteparametern, Verwalten von Direktverknüpfungen zwischen Geräten und Konfigurieren von Zeitprogrammen -- direkt über die Home Assistant-Oberfläche.

!!! note "Nur für Administratoren"
Das Konfigurationspanel ist nur für Home Assistant-Administratoren sichtbar. Nicht-Admin-Benutzer können Gerätezeitpläne über die [Klima-Zeitprogramm-Karte](climate_schedule_card.md) und [Zeitprogramm-Karte](schedule_card.md) bearbeiten, wenn dies in den Integrationsoptionen aktiviert ist (siehe [Zeitplan-Bearbeitung für Nicht-Admins](#non-admin-schedules)).

---

## Panel aktivieren

1. Zu **Einstellungen** --> **Geräte & Dienste** navigieren
2. **Homematic(IP) Local for OpenCCU** suchen und auf **Konfigurieren** klicken
3. **Erweiterte Optionen** auswählen
4. **Konfigurationspanel für Geräte** aktivieren
5. Auf **Absenden** klicken

Das Panel erscheint in der Home Assistant-Seitenleiste als **HM Gerätekonfiguration** (bzw. **HM Device Configuration** im Englischen).

---

## Aufbau des Panels {#panel-structure}

Das Panel ist in drei Hauptregisterkarten unterteilt:

| Registerkarte   | Zweck                                                         |
| --------------- | ------------------------------------------------------------- |
| **Geräte**      | Homematic-Geräte durchsuchen, konfigurieren und verwalten     |
| **Integration** | Zustand, Leistung und Vorkommnisse der Integration überwachen |
| **OpenCCU**     | CCU-Hardware, Funkschnittstellen und Firmware verwalten       |

---

## Registerkarte Geräte {#devices}

### Geraételiste {#device-list}

Die Geraételiste zeigt alle konfigurierbaren Geräte, gruppiert nach Funkschnittstelle (HmIP-RF, BidCos-RF, BidCos-Wired). Die Suchleiste ermöglicht das Filtern nach Name, Adresse oder Modell.

Jeder Geräteeintrag zeigt:

| Information    | Beschreibung                               |
| -------------- | ------------------------------------------ |
| **Gerätename** | Name wie auf der CCU konfiguriert          |
| **Modell**     | Modellnummer des Geräts (z.B. HmIP-eTRV-2) |
| **Adresse**    | Eindeutige Hardware-Kennung des Geräts     |
| **Kanäle**     | Anzahl der funktionalen Einheiten am Gerät |

**Statussymbole** zeigen den aktuellen Zustand des Geräts an:

| Symbol                              | Bedeutung                  |
| ----------------------------------- | -------------------------- |
| :material-check-circle:{ .green }   | Gerät ist erreichbar       |
| :material-close-circle:{ .red }     | Gerät ist nicht erreichbar |
| :material-battery-alert:{ .orange } | Batterie schwach           |
| :material-clock-alert:{ .orange }   | Konfiguration ausstehend   |

!!! tip "Was ist eine Schnittstelle?"
Eine Schnittstelle ist das Funkprotokoll, das vom Gerät verwendet wird. **HmIP-RF** wird von modernen HomematicIP-Geräten verwendet, **BidCos-RF** von klassischen Homematic-Geräten und **BidCos-Wired** von drahtgebundenen Geräten. Die Schnittstelle bestimmt, wie die CCU mit dem Gerät kommuniziert.

Auf ein Gerät klicken, um die [Gerätedetailansicht](#device-detail) zu öffnen.

---

### Gerätedetails {#device-detail}

Die Gerätedetailansicht zeigt alle Informationen zu einem einzelnen Gerät und bietet Zugriff auf dessen Kanäle.

**Geräteinformationen:**

| Feld         | Beschreibung                               |
| ------------ | ------------------------------------------ |
| **Modell**   | Gerätetyp (z.B. HmIP-eTRV-2)               |
| **Firmware** | Auf dem Gerät installierte Softwareversion |
| **Adresse**  | Hardware-Kennung (z.B. `001FD9499D7856`)   |

**Verfügbare Aktionen:**

- **Direktverknüpfungen** -- Peer-to-Peer-Verbindungen zu anderen Geräten verwalten ([mehr Infos](#direct-links))
- **Zeitprogramme** -- Zeitbasierte Automatisierungsprogramme bearbeiten ([mehr Infos](#schedules))
- **Änderungsverlauf** -- Protokoll vergangener Konfigurationsänderungen einsehen ([mehr Infos](#change-history))

#### Kanäle {#channels}

Ein Gerät besteht aus einem oder mehreren **Kanälen**. Jeder Kanal repräsentiert eine eigene Funktion des Geräts -- beispielsweise hat ein Zweitastenschalter separate Kanäle für jede Taste.

| Kanal                   | Zweck                                                                      |
| ----------------------- | -------------------------------------------------------------------------- |
| **Gerätekonfiguration** | Geräteübergreifende Einstellungen (z.B. Display-Beleuchtung, Tastensperre) |
| **Kanal 0 (Wartung)**   | Zustandsdaten: Signalstärke (RSSI), Batterie, Erreichbarkeit, Duty Cycle   |
| **Kanal 1, 2, ...**     | Funktionale Kanäle (z.B. Relais, Dimmer, Sensor, Thermostat)               |

Jeder Kanal zeigt seinen **Typ** (z.B. SWITCH, DIMMER, CLIMATECONTROL_REGULATOR) und bietet die Schaltflächen **Konfigurieren**, **Exportieren** und **Importieren**.

##### Wartungskanal {#maintenance}

Kanal 0 ist ein spezieller Wartungskanal, der auf jedem Gerät vorhanden ist. Er zeigt:

| Feld                   | Bedeutung                                                                                                                                                                                                                  |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **RSSI Gerät**         | Signalstärke von der CCU zum Gerät (in dBm). Werte näher an 0 sind besser. Typischer Bereich: -40 (ausgezeichnet) bis -100 (schlecht).                                                                                     |
| **RSSI Peer**          | Signalstärke vom Gerät zu seinem Kommunikationspartner. Zeigt "---" an, wenn keine Direktverknüpfungen existieren.                                                                                                         |
| **DC-Limit**           | Ob das Gerät sein [Duty-Cycle](https://de.wikipedia.org/wiki/Duty_Cycle)-Limit erreicht hat. Bei "Ja" kann das Gerät vorübergehend keine Funkbefehle senden (regulatorische Begrenzung zur Vermeidung von Funkstoerungen). |
| **Batterie schwach**   | Ob die Batterie ausgetauscht werden muss.                                                                                                                                                                                  |
| **Erreichbar**         | Ob die CCU mit dem Gerät kommunizieren kann.                                                                                                                                                                               |
| **Konfig. ausstehend** | Ob eine Konfigurationsänderung darauf wartet, auf das Gerät übertragen zu werden (das Gerät befindet sich möglicherweise im Schlafmodus).                                                                                  |

---

### Parameter bearbeiten {#editing-parameters}

Der Parametereditor bietet eine formularbasierte Oberfläche zum Bearbeiten von Gerätekonfigurationswerten (MASTER Paramset).

#### Arbeitsablauf

1. Ein Gerät aus der Geraételiste auswählen
2. Einen Kanal zum Konfigurieren auswählen
3. Das Panel generiert automatisch ein Formular mit passenden Steuerelementen:
   - **Schieberegler** für numerische Parameter (z.B. Temperaturoffset)
   - **Umschalter** für boolesche Parameter (z.B. Tastensperre)
   - **Auswahlfelder** für Aufzählungsparameter (z.B. Anzeigemodus)
   - **Voreinstellungen** für gängige Wertekombinationen (z.B. Zeitintervalle)
4. Werte nach Bedarf anpassen
5. Auf **Speichern** klicken, um die Änderungen über die CCU auf das Gerät zu schreiben

!!! warning "Gerätespeicher"
Das Schreiben von MASTER-Parametern verwendet den internen Speicher des Geräts. Übermäßig häufiges Schreiben kann das EEPROM des Geräts beeinträchtigen. Das Panel ist für Konfigurationsänderungen konzipiert, nicht für häufige Statusaktualisierungen.

#### Was ist ein Paramset? {#paramset}

Ein **Paramset** ist eine Sammlung von Konfigurationsparametern, die auf dem Gerät gespeichert sind. Das **MASTER**-Paramset enthält Geräteeinstellungen, die über Neustarts hinweg erhalten bleiben -- beispielsweise den Temperaturoffset eines Thermostats oder die LED-Helligkeit eines Schalters. Dies sind keine Laufzeitwerte (wie die aktuelle Temperatur), sondern Konfigurationswerte, die das Verhalten des Geräts ändern.

#### Sitzungsverwaltung {#session}

Änderungen werden in einer In-Memory-Sitzung mit Rückgängig/Wiederherstellen-Unterstützung verfolgt:

- **Rückgängig**: Die letzte Parameteränderung zurücknehmen
- **Wiederherstellen**: Eine zurückgenommene Änderung erneut anwenden
- **Auf Standardwerte zurücksetzen**: Werkseitige Standardwerte für alle Parameter wiederherstellen
- **Verwerfen**: Alle ausstehenden Änderungen verwerfen, ohne zu schreiben
- **Speichern**: Öffnet einen Bestätigungsdialog, der alle Änderungen (alter --> neuer Wert) vor dem Anwenden anzeigt

#### Easymode {#easymode}

Das Panel verwendet **Easymode**, um den Parametereditor zu vereinfachen:

- **Bedingte Sichtbarkeit**: Einige Parameter werden nur angezeigt, wenn sie relevant sind (z.B. ein Schwellwertparameter erscheint nur, wenn die zugehörige Funktion aktiviert ist)
- **Voreinstellungs-Auswahlfelder**: Gängige Wertekombinationen werden als Auswahlfeld angeboten (z.B. die Auswahl von "Treppenlicht" wendet mehrere Parameter gleichzeitig an)
- **Gruppierte Parameter**: Zusammengehörige Parameter werden in einem einzigen Steuerelement kombiniert

Diese Vereinfachungen entsprechen dem Verhalten der CCU WebUI -- es werden nur Parameter mit lesbaren Namen angezeigt.

#### Parametervalidierung {#validation}

Das Panel validiert Änderungen in Echtzeit:

- **Bereichsprüfungen**: Werte müssen innerhalb des erlaubten Min/Max-Bereichs liegen
- **Kreuzvalidierung**: Zusammengehörige Parameter werden gemeinsam geprüft (z.B. Maximum muss größer als Minimum sein)
- Ungültige Felder werden mit einer Fehlermeldung hervorgehoben

---

### Export / Import {#export-import}

#### Export

Die aktuelle Paramset-Konfiguration eines Kanals als JSON-Datei exportieren. Dies dient als Sicherung oder als Vorlage für andere Geräte desselben Modells.

#### Import

Eine zuvor exportierte JSON-Konfiguration in einen Kanal **desselben Gerätemodells** importieren. Es werden nur beschreibbare Parameter angewendet, die auf dem Zielkanal vorhanden sind.

---

### Direktverknüpfungen {#direct-links}

Direktverknüpfungen (auch **Peerings** genannt) verbinden zwei Gerätekanäle für direkte Peer-to-Peer-Kommunikation -- ohne die CCU als Vermittler.

!!! example "Typischer Anwendungsfall"
Ein Wandschalter steuert direkt einen Lichtaktor. Beim Drücken des Schalters geht der Befehl direkt per Funk an das Licht -- auch wenn die CCU offline ist.

#### Vorteile von Direktverknüpfungen

- **Schnelle Reaktion**: Kein Umweg über die CCU
- **Zuverlässig**: Funktioniert auch, wenn die CCU vorübergehend nicht verfügbar ist
- **Konfigurierbar**: Unterschiedliches Verhalten für kurze und lange Tastendrücke

#### Verknüpfungen durchsuchen

Ein Gerät auswählen, um alle vorhandenen Direktverknüpfungen nach Kanal gruppiert anzuzeigen. Jede Verknüpfung zeigt:

- **Richtung**: Ob das Gerät Sender oder Empfänger ist
- **Partner**: Das verknüpfte Gerät, Modell und Kanal
- **Verknüpfungsname**: Optionale benutzerdefinierte Bezeichnung

#### Verknüpfungen erstellen

1. Auf **Verknüpfung hinzufügen** bei einem Gerät klicken
2. Den Kanal am eigenen Gerät auswählen
3. Festlegen, ob dieses Gerät der **Sender** oder **Empfänger** ist
4. Das Partnergerät und den Kanal suchen und auswählen (nur kompatible Kanäle werden angezeigt)
5. Optional einen Verknüpfungsnamen eingeben
6. Zum Erstellen der Verknüpfung bestätigen

#### Verknüpfungen konfigurieren {#link-config}

Auf eine vorhandene Verknüpfung klicken, um deren Parameter zu bearbeiten:

- **Profilauswahl**: Aus vordefinierten Easymode-Profilen wählen (z.B. "Dimmer ein/aus", "Treppenlicht", "Umschalten") -- jedes Profil konfiguriert Parameter für einen gängigen Anwendungsfall vor
- **Registerkarten kurzer/langer Tastendruck**: Unterschiedliches Verhalten für kurze und lange Tastendrücke konfigurieren
- **Zeitparameter**: Kombinierte Zeitauswahlfelder für Verzögerungen und Dauer
- **Pegelparameter**: Prozent-Schieberegler mit "Letzter Wert"-Unterstützung (den zuletzt gesetzten Wert verwenden)

#### Verknüpfungen entfernen

Eine Verknüpfung auswählen und auf **Löschen** klicken, um die Direktverknüpfung von der CCU zu entfernen.

---

### Zeitprogramme {#schedules}

Das Panel integriert die Verwaltung von Zeitprogrammen für Geräte mit Wochenprofilunterstützung.

#### Klima-Zeitprogramme {#climate-schedules}

Für Thermostatgeräte (z.B. HmIP-eTRV, HmIP-WTH):

- **Visuelles Wochenraster**: Farbcodierte Temperaturblöcke für jeden Wochentag
- **Profilauswahl**: Zwischen bis zu 6 Zeitprogrammprofilen (P1--P6) wechseln
- **Aktives Profil**: Festlegen, welchem Profil der Thermostat tatsächlich folgt
- **Tagesweise Bearbeitung**: Auf einen Tag klicken, um Temperaturblöcke hinzuzufügen, zu verschieben oder zu löschen
- **Kopieren/Einfügen**: Das Zeitprogramm eines Tages auf andere Tage kopieren
- **Rückgängig/Wiederherstellen**: Änderungen zurücknehmen oder erneut anwenden
- **Import/Export**: Zeitprogramme als JSON speichern und wiederherstellen

!!! info "Profile"
Ein **Profil** ist ein vollständiges Wochenprogramm. Die meisten Thermostate unterstützen mehrere Profile (z.B. "Normal", "Energiesparen", "Urlaub"). Das **aktive Profil** ist dasjenige, dem das Gerät aktuell folgt. Die Auswahl eines anderen Profils im Auswahlfeld lädt dessen Daten zur Anzeige/Bearbeitung und aktiviert es auf dem Gerät.

#### Geräte-Zeitprogramme {#device-schedules}

Für Nicht-Klima-Geräte (Schalter, Leuchten, Abdeckungen, Ventile):

- **Ereignisliste**: Zeigt alle geplanten Ereignisse nach Wochentag gruppiert
- **Ereigniseditor**: Jedes Ereignis konfigurieren mit:
  - **Uhrzeit**: Feste Uhrzeit (z.B. 06:00) oder astronomisch (relativ zum Sonnenauf-/Sonnenuntergang)
  - **Wochentage**: An welchen Tagen das Ereignis gilt
  - **Pegel**: Zielzustand (Ein/Aus für Schalter, 0--100% für Dimmer/Abdeckungen)
  - **Dauer**: Wie lange die Aktion dauert (optional)
  - **Rampenzeit**: Graduelle Übergangszeit für Leuchten (optional)
  - **Zielkanäle**: Welche Kanäle gesteuert werden (bei Mehrkanal-Geräten)

!!! tip "Zeitprogramm-Karten"
Für eine visuellere Bearbeitung von Zeitprogrammen die dedizierten Lovelace-Karten verwenden:

    - [Klima-Zeitprogramm-Karte](climate_schedule_card.md) für Thermostate
    - [Zeitprogramm-Karte](schedule_card.md) für Schalter, Leuchten, Abdeckungen und Ventile

---

### Änderungsverlauf {#change-history}

Der Änderungsverlauf führt ein dauerhaftes Protokoll aller über das Panel vorgenommenen Parameteränderungen.

Jeder Eintrag zeigt:

| Feld            | Beschreibung                                 |
| --------------- | -------------------------------------------- |
| **Zeitstempel** | Wann die Änderung vorgenommen wurde          |
| **Gerät**       | Gerätename und Modell                        |
| **Kanal**       | Kanaladresse, die geändert wurde             |
| **Parameter**   | Anzahl der geänderten Parameter              |
| **Quelle**      | Art der Änderung: Manuell, Import oder Kopie |

Auf einen Eintrag klicken, um die Details aufzuklappen und den alten und neuen Wert jedes Parameters einzusehen.

!!! info "Speicherung"
Der Verlauf wird über das Speichersystem von Home Assistant mit einem Limit von 500 Einträgen pro Konfigurationseintrag gespeichert. Wenn das Limit erreicht ist, werden die ältesten Einträge automatisch entfernt.

Die Schaltfläche **Verlauf löschen** entfernt dauerhaft alle Einträge (mit Bestätigung).

---

## Registerkarte Integration {#integration}

Das Integration-Dashboard überwacht den Zustand und die Leistung der Homematic(IP) Local-Integration.

### Systemzustand {#system-health}

Zeigt den aktuellen Zustand der Integration:

| Feld               | Beschreibung                                                                                                                                                                                                                                       |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Central-Status** | Verbindungsstatus der Integration. "RUNNING" bedeutet, dass alles betriebsbereit ist. Andere Zustände wie "STARTUP" oder "RECONNECT" zeigen an, dass die Integration initialisiert oder wiederhergestellt wird.                                    |
| **Zustandswert**   | Ein Prozentwert (0--100%), der die allgemeine Kommunikationsqualität der Geräte anzeigt. 100% bedeutet, dass alle Geräte erreichbar sind und normal kommunizieren. Ein niedrigerer Wert bedeutet, dass einige Geräte Kommunikationsprobleme haben. |

### Gerätestatistiken {#device-statistics}

Ein schneller Überblick über die Geräteflotte:

| Feld                        | Beschreibung                                                      |
| --------------------------- | ----------------------------------------------------------------- |
| **Geräte gesamt**           | Anzahl der von dieser Integration verwalteten Geräte              |
| **Nicht erreichbar**        | Derzeit nicht reagierende Geräte (als Warnung angezeigt wenn > 0) |
| **Firmware aktualisierbar** | Geräte mit verfügbaren Firmware-Updates                           |

### Befehlsdrosselung {#command-throttle}

Die **Befehlsdrosselung** ist ein Schutzmechanismus, der begrenzt, wie schnell Befehle an die CCU gesendet werden.

!!! question "Warum ist das nötig?"
Homematic-Geräte kommunizieren per Funk. Wenn zu viele Befehle in schneller Folge gesendet werden, können sie sich gegenseitig stören -- was zu verlorenen Befehlen oder verzögerten Antworten führt. Die Drosselung stellt sicher, dass Befehle zeitlich verteilt werden, insbesondere bei Automatisierungen oder Szenen, die viele Geräte gleichzeitig steuern.

| Feld                    | Beschreibung                                                                                   |
| ----------------------- | ---------------------------------------------------------------------------------------------- |
| **Aktiviert**           | Ob die Drosselung aktiv ist                                                                    |
| **Intervall**           | Mindestzeit zwischen Befehlen (in Sekunden)                                                    |
| **Warteschlangengröße** | Anzahl der Befehle, die derzeit auf das Senden warten                                          |
| **Gedrosselt**          | Ob Befehle derzeit verzögert werden                                                            |
| **Burst-Anzahl**        | Anzahl der Befehle, die in schneller Folge gesendet werden können, bevor die Drosselung greift |

Im Normalbetrieb ist die Warteschlange leer und "Gedrosselt" zeigt "Nein". Wenn die Warteschlange wächst oder die Drosselung aktiv ist, bedeutet dies, dass viele Befehle verarbeitet werden -- dies ist bei Szenen oder umfangreichen Automatisierungen zu erwarten.

### Vorkommnisse {#incidents}

**Vorkommnisse** sind protokollierte Kommunikationsereignisse, die zwischen der Integration und der CCU oder Geräten aufgetreten sind. Dies sind **keine Fehler** und erfordern in der Regel **keine Maßnahmen**.

!!! warning "Vorkommnisse sind keine Fehler"
Ein Vorkommnis bedeutet **nicht**, dass etwas kaputt ist. Es ist ein normaler Diagnoseeintrag -- ähnlich einem Flugschreiber. Häufige Vorkommnisse umfassen:

    - Ein Gerät reagiert vorübergehend nicht (z.B. batteriebetriebenes Gerät im Schlafmodus)
    - Eine kurze Kommunikationsunterbrechung bei starkem Funkverkehr
    - Ein Gerät verbindet sich nach einem Stromausfall neu

    Diese Ereignisse werden automatisch behoben und nur zu Informationszwecken protokolliert. **Kein GitHub-Issue eröffnen** wegen Vorkommnissen -- sie sind erwartetes Verhalten in einer drahtlosen Umgebung.

Wenn die Vorkommnisliste leer ist, ist das ideal -- es bedeutet, dass keine Kommunikationsunregelmäßigkeiten aufgezeichnet wurden.

Die Schaltfläche **Vorkommnisse löschen** entfernt alle protokollierten Vorkommnisse.

### Cache-Verwaltung {#cache}

Die Integration speichert Gerätemetadaten (Parameterbeschreibungen, Kanalinformationen) im Cache, um den Start zu beschleunigen. Bei Verdacht auf veralteten Cache (z.B. nach einem CCU-Firmware-Update) kann dieser geleert werden:

- **Cache leeren**: Löscht alle zwischengespeicherten Gerätedaten. Die Integration ruft beim nächsten Neustart alles erneut von der CCU ab.

!!! note
Das Leeren des Caches hat keinen Einfluss auf Gerätekonfigurationen oder Automatisierungen. Es erzwingt lediglich, dass die Integration die Gerätemetadaten erneut von der CCU einliest.

---

## Registerkarte OpenCCU {#openccu}

Das OpenCCU-Dashboard bietet direkten Zugriff auf CCU-Systemverwaltungsfunktionen. Es ist in Unterregisterkarten gegliedert.

### Systeminformationen {#system-info}

Zeigt Details zur verbundenen CCU-Hardware:

| Feld                | Beschreibung                               |
| ------------------- | ------------------------------------------ |
| **Name**            | CCU-Systemname                             |
| **Modell**          | Hardwaremodell (z.B. CCU3, RaspberryMatic) |
| **Version**         | CCU-Firmware-Version                       |
| **Seriennummer**    | Hardware-Seriennummer                      |
| **Hostname**        | Netzwerk-Hostname                          |
| **Schnittstellen**  | Konfigurierte Funkschnittstellen           |
| **Auth. aktiviert** | Ob die CCU-Authentifizierung aktiv ist     |

**Aktionen:**

- **Sicherung erstellen**: Lädt eine CCU-Konfigurationssicherungsdatei herunter. Zeigt den Fortschritt an und meldet Dateinamen und Größe nach Abschluss.

### Nachrichten {#messages}

Die Unterregisterkarte Nachrichten zeigt drei Kategorien von Systembenachrichtigungen. Ein Badge auf der Registerkarte zeigt die Gesamtzahl der aktiven Nachrichten.

#### Posteingang {#inbox}

Neue Geräte, die erkannt, aber noch nicht in das System übernommen wurden. Auf **Akzeptieren** klicken, um ein Gerät hinzuzufügen -- dabei wird zur Bestätigung und optional zur Namenseingabe aufgefordert.

#### Servicemeldungen {#service-messages}

Servicemeldungen sind Systembenachrichtigungen der CCU über Gerätezustände, die möglicherweise Aufmerksamkeit erfordern:

| Typ                    | Bedeutung                                                            |
| ---------------------- | -------------------------------------------------------------------- |
| **Generisch**          | Allgemeine Benachrichtigung                                          |
| **Persistent**         | Dauerhafte Benachrichtigung, die bis zur Quittierung bestehen bleibt |
| **Konfig. ausstehend** | Ein Gerät wartet auf die Übernahme einer Konfiguration               |
| **Alarm**              | Eine Warnbedingung (z.B. Batterie schwach, Sabotage)                 |
| **Update ausstehend**  | Ein Firmware-Update ist verfügbar                                    |
| **Kommunikation**      | Ein Kommunikationsproblem wurde erkannt                              |

Jede Meldung zeigt Gerätename, Adresse, Meldungstyp, Beschreibung, Zeitstempel und einen Zähler (wie oft sie aufgetreten ist). **Quittierbare** Meldungen können mit der Schaltfläche **Quittieren** bestätigt werden.

!!! tip
Die meisten Servicemeldungen lösen sich von selbst (z.B. ein batteriebetriebenes Gerät verbindet sich nach dem Aufwachen wieder). Die Meldungen dienen der Information -- sie erfordern nicht unbedingt sofortiges Handeln.

#### Alarmmeldungen {#alarm-messages}

Alarmmeldungen sind kritische Benachrichtigungen, die auf einen Zustand hinweisen, der Aufmerksamkeit erfordert (z.B. Sabotageerkennung, Sensorfehler). Jeder Alarm zeigt:

- Gerätename und Beschreibung
- Letzter Auslösezeitpunkt
- Vorkommniszähler
- Schaltfläche **Quittieren** zum Löschen des Alarms

### Signalqualität {#signal-quality}

Eine sortier- und filterbare Tabelle, die die Funksignalqualität aller Geräte zeigt:

| Spalte            | Beschreibung                              |
| ----------------- | ----------------------------------------- |
| **Gerät**         | Gerätename                                |
| **Modell**        | Gerätemodell                              |
| **Schnittstelle** | Funkprotokoll (HmIP-RF, BidCos-RF)        |
| **Erreichbar**    | Ob das Gerät derzeit antwortet            |
| **RSSI**          | Signalstärke in dBm (näher an 0 = besser) |
| **Batterie**      | Batteriestatus (OK oder Schwach)          |

Die Filterleiste (angezeigt bei mehr als 10 Geräten) ermöglicht die Suche nach Name/Modell oder das Filtern nach Schnittstelle, Erreichbarkeit oder Batteriestatus.

!!! info "RSSI-Werte verstehen"
| Bereich | Qualität |
| ----- | ------- |
| -40 bis 0 dBm | Ausgezeichnet |
| -60 bis -40 dBm | Gut |
| -80 bis -60 dBm | Akzeptabel |
| -100 bis -80 dBm | Schlecht -- Gerät näher platzieren oder einen Repeater hinzufügen |
| Unter -100 dBm | Sehr schlecht -- Kommunikationsprobleme wahrscheinlich |

    Weitere Details unter [Über RSSI-Werte](../troubleshooting/rssi_fix.md).

### Firmware {#firmware}

Eine sortier- und filterbare Tabelle, die den Firmware-Status aller Geräte zeigt:

| Spalte            | Beschreibung                                 |
| ----------------- | -------------------------------------------- |
| **Gerät**         | Gerätename und Modell                        |
| **Aktuelle FW**   | Installierte Firmware-Version                |
| **Verfügbare FW** | Neueste verfügbare Firmware-Version          |
| **Status**        | Update-Status (aktuell, aktualisierbar usw.) |

Auf **Firmware-Daten aktualisieren** klicken, um die neuesten Firmware-Informationen von der CCU abzurufen.

!!! note
Firmware-Updates werden von der CCU verwaltet, nicht von dieser Integration. Das Panel zeigt den Status zu Informationszwecken an. Für Updates die CCU WebUI oder den geräteeigenen Aktualisierungsmechanismus verwenden.

### Anlernmodus {#install-mode}

Der Anlernmodus versetzt die CCU in den **Kopplungsmodus**, damit neue Geräte dem Netzwerk beitreten können.

- Auf **Aktivieren** neben der gewünschten Schnittstelle (HmIP-RF oder BidCos-RF) klicken
- Die CCU geht für 60 Sekunden in den Kopplungsmodus (ein Countdown wird angezeigt)
- Das neue Gerät während dieser Zeit in den Kopplungsmodus versetzen (siehe Gerätehandbuch)
- Nach der Kopplung erscheint das Gerät im [Posteingang](#inbox)

!!! tip
Es werden nur Schnittstellen angezeigt, die tatsächlich in der Integration konfiguriert sind. Falls eine Schnittstelle nicht sichtbar ist, die Integrationskonfiguration prüfen.

---

## Zeitplan-Bearbeitung für Nicht-Admins {#non-admin-schedules}

Standardmäßig können nur Administratoren Gerätezeitpläne bearbeiten. Nicht-Admin-Haushaltsmitgliedern kann die Zeitplan-Bearbeitung über die Zeitplan-Karten ([Klima-Zeitprogramm-Karte](climate_schedule_card.md) und [Zeitprogramm-Karte](schedule_card.md)) erlaubt werden.

### Aktivierung

1. Zu **Einstellungen** --> **Geräte & Dienste** navigieren
2. **Homematic(IP) Local for OpenCCU** suchen und auf **Konfigurieren** klicken
3. **Zeitplan-Bearbeitung** auswählen
4. **Nicht-Admin-Benutzern erlauben, Zeitpläne zu bearbeiten** aktivieren
5. Auf **Absenden** klicken

### Funktionsweise

- Nicht-Admin-Benutzer können Zeitpläne über die Lovelace-Zeitplan-Karten bearbeiten
- Das Backend erzwingt die Berechtigungen -- wenn ein Nicht-Admin-Benutzer versucht, einen Zeitplan ohne diese Option zu bearbeiten, zeigt die Karte eine Fehlermeldung "Keine Berechtigung"
- Alle anderen Operationen (Gerätekonfiguration, Direktverknüpfungen, Systemverwaltung) bleiben nur für Administratoren
- Leseoperationen (Zeitpläne anzeigen, Geräteparameter einsehen) sind immer für alle authentifizierten Benutzer verfügbar

!!! note
Das Konfigurationspanel selbst bleibt nur für Administratoren zugänglich. Diese Einstellung betrifft nur die Zeitplan-Karten auf Dashboards.

---

## Deep-Linking {#deep-linking}

Über URL-Hash-Parameter direkt zu einem bestimmten Gerät, Kanal oder einer Verknüpfungsansicht navigieren. Das Panel unterstützt die Browser-Vor-/Zurück-Navigation für nahtloses Durchsuchen.

---

## Fehlerbehebung {#troubleshooting}

### Panel ist in der Seitenleiste nicht sichtbar

1. Sicherstellen, dass das Panel in den erweiterten Optionen aktiviert ist
2. Bestätigen, dass die Anmeldung als Administrator erfolgt ist
3. Den Browser neu laden (Strg+F5)

### Parameter werden nicht gespeichert

1. Prüfen, ob das Gerät erreichbar ist (kein UNREACH)
2. Home Assistant-Protokolle auf XML-RPC-Fehler prüfen
3. Warten, bis CONFIG_PENDING auf dem Gerät aufgelöst ist

### Leere Parameterliste für einen Kanal

- Der Kanal hat möglicherweise keine sichtbaren MASTER-Parameter
- Parameter ohne CCU-Übersetzungen werden herausgefiltert (entspricht dem Verhalten der CCU WebUI)

---

## Siehe auch {#see-also}

- [Wochenprofile](week_profile.md) -- Zeitprogramm-Datenformat und Aktionen
- [Klima-Zeitprogramm-Karte](climate_schedule_card.md) -- Visueller Thermostat-Zeitprogrammeditor
- [Zeitprogramm-Karte](schedule_card.md) -- Visueller Geräte-Zeitprogrammeditor
- [Status-Karten](status_cards.md) -- Systemstatus, Gerätestatus und Meldungen
- [Aktionsreferenz](homeassistant_actions.md) -- Alle verfügbaren Service-Aktionen
- [Über RSSI-Werte](../troubleshooting/rssi_fix.md) -- Signalstärke verstehen
