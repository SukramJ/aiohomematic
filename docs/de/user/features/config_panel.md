---
translation_source: docs/user/features/config_panel.md
translation_date: 2026-04-01
translation_source_hash: dd3410609095
---

# Konfigurationspanel fuer Geraete

Das Homematic-Konfigurationspanel fuer Geraete ist ein Seitenleistenpanel in Home Assistant zum Bearbeiten von Geraeteparametern, Verwalten von Direktverknuepfungen zwischen Geraeten und Konfigurieren von Zeitprogrammen -- direkt ueber die Home Assistant-Oberflaeche.

!!! note "Nur fuer Administratoren"
Das Konfigurationspanel ist nur fuer Administratoren sichtbar.

---

## Panel aktivieren

1. Zu **Einstellungen** --> **Geraete & Dienste** navigieren
2. **Homematic(IP) Local for OpenCCU** suchen und auf **Konfigurieren** klicken
3. **Erweiterte Optionen** auswaehlen
4. **Konfigurationspanel fuer Geraete** aktivieren
5. Auf **Absenden** klicken

Das Panel erscheint in der Home Assistant-Seitenleiste als **HM Geraetekonfiguration** (bzw. **HM Device Configuration** im Englischen).

---

## Aufbau des Panels {#panel-structure}

Das Panel ist in drei Hauptregisterkarten unterteilt:

| Registerkarte   | Zweck                                                          |
| --------------- | -------------------------------------------------------------- |
| **Geraete**     | Homematic-Geraete durchsuchen, konfigurieren und verwalten     |
| **Integration** | Zustand, Leistung und Vorkommnisse der Integration ueberwachen |
| **OpenCCU**     | CCU-Hardware, Funkschnittstellen und Firmware verwalten        |

---

## Registerkarte Geraete {#devices}

### Geraételiste {#device-list}

Die Geraételiste zeigt alle konfigurierbaren Geraete, gruppiert nach Funkschnittstelle (HmIP-RF, BidCos-RF, BidCos-Wired). Die Suchleiste ermoeglicht das Filtern nach Name, Adresse oder Modell.

Jeder Geraeteeintrag zeigt:

| Information     | Beschreibung                                |
| --------------- | ------------------------------------------- |
| **Geraetename** | Name wie auf der CCU konfiguriert           |
| **Modell**      | Modellnummer des Geraets (z.B. HmIP-eTRV-2) |
| **Adresse**     | Eindeutige Hardware-Kennung des Geraets     |
| **Kanaele**     | Anzahl der funktionalen Einheiten am Geraet |

**Statussymbole** zeigen den aktuellen Zustand des Geraets an:

| Symbol                              | Bedeutung                   |
| ----------------------------------- | --------------------------- |
| :material-check-circle:{ .green }   | Geraet ist erreichbar       |
| :material-close-circle:{ .red }     | Geraet ist nicht erreichbar |
| :material-battery-alert:{ .orange } | Batterie schwach            |
| :material-clock-alert:{ .orange }   | Konfiguration ausstehend    |

!!! tip "Was ist eine Schnittstelle?"
Eine Schnittstelle ist das Funkprotokoll, das vom Geraet verwendet wird. **HmIP-RF** wird von modernen HomematicIP-Geraeten verwendet, **BidCos-RF** von klassischen Homematic-Geraeten und **BidCos-Wired** von drahtgebundenen Geraeten. Die Schnittstelle bestimmt, wie die CCU mit dem Geraet kommuniziert.

Auf ein Geraet klicken, um die [Geraetedetailansicht](#device-detail) zu oeffnen.

---

### Geraetedetails {#device-detail}

Die Geraetedetailansicht zeigt alle Informationen zu einem einzelnen Geraet und bietet Zugriff auf dessen Kanaele.

**Geraeteinformationen:**

| Feld         | Beschreibung                                |
| ------------ | ------------------------------------------- |
| **Modell**   | Geraetetyp (z.B. HmIP-eTRV-2)               |
| **Firmware** | Auf dem Geraet installierte Softwareversion |
| **Adresse**  | Hardware-Kennung (z.B. `001FD9499D7856`)    |

**Verfuegbare Aktionen:**

- **Direktverknuepfungen** -- Peer-to-Peer-Verbindungen zu anderen Geraeten verwalten ([mehr Infos](#direct-links))
- **Zeitprogramme** -- Zeitbasierte Automatisierungsprogramme bearbeiten ([mehr Infos](#schedules))
- **Aenderungsverlauf** -- Protokoll vergangener Konfigurationsaenderungen einsehen ([mehr Infos](#change-history))

#### Kanaele {#channels}

Ein Geraet besteht aus einem oder mehreren **Kanaelen**. Jeder Kanal repraesentiert eine eigene Funktion des Geraets -- beispielsweise hat ein Zweitastenschalter separate Kanaele fuer jede Taste.

| Kanal                    | Zweck                                                                      |
| ------------------------ | -------------------------------------------------------------------------- |
| **Geraetekonfiguration** | Geraeuebergreifende Einstellungen (z.B. Display-Beleuchtung, Tastensperre) |
| **Kanal 0 (Wartung)**    | Zustandsdaten: Signalstaerke (RSSI), Batterie, Erreichbarkeit, Duty Cycle  |
| **Kanal 1, 2, ...**      | Funktionale Kanaele (z.B. Relais, Dimmer, Sensor, Thermostat)              |

Jeder Kanal zeigt seinen **Typ** (z.B. SWITCH, DIMMER, CLIMATECONTROL_REGULATOR) und bietet die Schaltflaechen **Konfigurieren**, **Exportieren** und **Importieren**.

##### Wartungskanal {#maintenance}

Kanal 0 ist ein spezieller Wartungskanal, der auf jedem Geraet vorhanden ist. Er zeigt:

| Feld                   | Bedeutung                                                                                                                                                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **RSSI Geraet**        | Signalstaerke von der CCU zum Geraet (in dBm). Werte naeher an 0 sind besser. Typischer Bereich: -40 (ausgezeichnet) bis -100 (schlecht).                                                                                     |
| **RSSI Peer**          | Signalstaerke vom Geraet zu seinem Kommunikationspartner. Zeigt "---" an, wenn keine Direktverknuepfungen existieren.                                                                                                         |
| **DC-Limit**           | Ob das Geraet sein [Duty-Cycle](https://de.wikipedia.org/wiki/Duty_Cycle)-Limit erreicht hat. Bei "Ja" kann das Geraet voruebergehend keine Funkbefehle senden (regulatorische Begrenzung zur Vermeidung von Funkstoerungen). |
| **Batterie schwach**   | Ob die Batterie ausgetauscht werden muss.                                                                                                                                                                                     |
| **Erreichbar**         | Ob die CCU mit dem Geraet kommunizieren kann.                                                                                                                                                                                 |
| **Konfig. ausstehend** | Ob eine Konfigurationsaenderung darauf wartet, auf das Geraet uebertragen zu werden (das Geraet befindet sich moeglicherweise im Schlafmodus).                                                                                |

---

### Parameter bearbeiten {#editing-parameters}

Der Parametereditor bietet eine formularbasierte Oberflaeche zum Bearbeiten von Geraetekonfigurationswerten (MASTER Paramset).

#### Arbeitsablauf

1. Ein Geraet aus der Geraételiste auswaehlen
2. Einen Kanal zum Konfigurieren auswaehlen
3. Das Panel generiert automatisch ein Formular mit passenden Steuerelementen:
   - **Schieberegler** fuer numerische Parameter (z.B. Temperaturoffset)
   - **Umschalter** fuer boolesche Parameter (z.B. Tastensperre)
   - **Auswahlfelder** fuer Aufzaehlungsparameter (z.B. Anzeigemodus)
   - **Voreinstellungen** fuer gaengige Wertekombinationen (z.B. Zeitintervalle)
4. Werte nach Bedarf anpassen
5. Auf **Speichern** klicken, um die Aenderungen ueber die CCU auf das Geraet zu schreiben

!!! warning "Geraetespeicher"
Das Schreiben von MASTER-Parametern verwendet den internen Speicher des Geraets. Uebermaeßig haeufiges Schreiben kann das EEPROM des Geraets beeintraechtigen. Das Panel ist fuer Konfigurationsaenderungen konzipiert, nicht fuer haeufige Statusaktualisierungen.

#### Was ist ein Paramset? {#paramset}

Ein **Paramset** ist eine Sammlung von Konfigurationsparametern, die auf dem Geraet gespeichert sind. Das **MASTER**-Paramset enthaelt Geraeteeinstellungen, die ueber Neustarts hinweg erhalten bleiben -- beispielsweise den Temperaturoffset eines Thermostats oder die LED-Helligkeit eines Schalters. Dies sind keine Laufzeitwerte (wie die aktuelle Temperatur), sondern Konfigurationswerte, die das Verhalten des Geraets aendern.

#### Sitzungsverwaltung {#session}

Aenderungen werden in einer In-Memory-Sitzung mit Rueckgaengig/Wiederherstellen-Unterstuetzung verfolgt:

- **Rueckgaengig**: Die letzte Parameteraenderung zuruecknehmen
- **Wiederherstellen**: Eine zurueckgenommene Aenderung erneut anwenden
- **Auf Standardwerte zuruecksetzen**: Werkseitige Standardwerte fuer alle Parameter wiederherstellen
- **Verwerfen**: Alle ausstehenden Aenderungen verwerfen, ohne zu schreiben
- **Speichern**: Oeffnet einen Bestaetigungsdialog, der alle Aenderungen (alter --> neuer Wert) vor dem Anwenden anzeigt

#### Easymode {#easymode}

Das Panel verwendet **Easymode**, um den Parametereditor zu vereinfachen:

- **Bedingte Sichtbarkeit**: Einige Parameter werden nur angezeigt, wenn sie relevant sind (z.B. ein Schwellwertparameter erscheint nur, wenn die zugehoerige Funktion aktiviert ist)
- **Voreinstellungs-Auswahlfelder**: Gaengige Wertekombinationen werden als Auswahlfeld angeboten (z.B. die Auswahl von "Treppenlicht" wendet mehrere Parameter gleichzeitig an)
- **Gruppierte Parameter**: Zusammengehoerige Parameter werden in einem einzigen Steuerelement kombiniert

Diese Vereinfachungen entsprechen dem Verhalten der CCU WebUI -- es werden nur Parameter mit lesbaren Namen angezeigt.

#### Parametervalidierung {#validation}

Das Panel validiert Aenderungen in Echtzeit:

- **Bereichspruefungen**: Werte muessen innerhalb des erlaubten Min/Max-Bereichs liegen
- **Kreuzvalidierung**: Zusammengehoerige Parameter werden gemeinsam geprueft (z.B. Maximum muss groesser als Minimum sein)
- Ungueltige Felder werden mit einer Fehlermeldung hervorgehoben

---

### Export / Import {#export-import}

#### Export

Die aktuelle Paramset-Konfiguration eines Kanals als JSON-Datei exportieren. Dies dient als Sicherung oder als Vorlage fuer andere Geraete desselben Modells.

#### Import

Eine zuvor exportierte JSON-Konfiguration in einen Kanal **desselben Geraetemodells** importieren. Es werden nur beschreibbare Parameter angewendet, die auf dem Zielkanal vorhanden sind.

---

### Direktverknuepfungen {#direct-links}

Direktverknuepfungen (auch **Peerings** genannt) verbinden zwei Geraetekanaele fuer direkte Peer-to-Peer-Kommunikation -- ohne die CCU als Vermittler.

!!! example "Typischer Anwendungsfall"
Ein Wandschalter steuert direkt einen Lichtaktor. Beim Druecken des Schalters geht der Befehl direkt per Funk an das Licht -- auch wenn die CCU offline ist.

#### Vorteile von Direktverknuepfungen

- **Schnelle Reaktion**: Kein Umweg ueber die CCU
- **Zuverlaessig**: Funktioniert auch, wenn die CCU voruebergehend nicht verfuegbar ist
- **Konfigurierbar**: Unterschiedliches Verhalten fuer kurze und lange Tastendruecke

#### Verknuepfungen durchsuchen

Ein Geraet auswaehlen, um alle vorhandenen Direktverknuepfungen nach Kanal gruppiert anzuzeigen. Jede Verknuepfung zeigt:

- **Richtung**: Ob das Geraet Sender oder Empfaenger ist
- **Partner**: Das verknuepfte Geraet, Modell und Kanal
- **Verknuepfungsname**: Optionale benutzerdefinierte Bezeichnung

#### Verknuepfungen erstellen

1. Auf **Verknuepfung hinzufuegen** bei einem Geraet klicken
2. Den Kanal am eigenen Geraet auswaehlen
3. Festlegen, ob dieses Geraet der **Sender** oder **Empfaenger** ist
4. Das Partnergeraet und den Kanal suchen und auswaehlen (nur kompatible Kanaele werden angezeigt)
5. Optional einen Verknuepfungsnamen eingeben
6. Zum Erstellen der Verknuepfung bestaetigen

#### Verknuepfungen konfigurieren {#link-config}

Auf eine vorhandene Verknuepfung klicken, um deren Parameter zu bearbeiten:

- **Profilauswahl**: Aus vordefinierten Easymode-Profilen waehlen (z.B. "Dimmer ein/aus", "Treppenlicht", "Umschalten") -- jedes Profil konfiguriert Parameter fuer einen gaengigen Anwendungsfall vor
- **Registerkarten kurzer/langer Tastendruck**: Unterschiedliches Verhalten fuer kurze und lange Tastendruecke konfigurieren
- **Zeitparameter**: Kombinierte Zeitauswahlfelder fuer Verzoegerungen und Dauer
- **Pegelparameter**: Prozent-Schieberegler mit "Letzter Wert"-Unterstuetzung (den zuletzt gesetzten Wert verwenden)

#### Verknuepfungen entfernen

Eine Verknuepfung auswaehlen und auf **Loeschen** klicken, um die Direktverknuepfung von der CCU zu entfernen.

---

### Zeitprogramme {#schedules}

Das Panel integriert die Verwaltung von Zeitprogrammen fuer Geraete mit Wochenprofilunterstuetzung.

#### Klima-Zeitprogramme {#climate-schedules}

Fuer Thermostatgeraete (z.B. HmIP-eTRV, HmIP-WTH):

- **Visuelles Wochenraster**: Farbcodierte Temperaturblöcke fuer jeden Wochentag
- **Profilauswahl**: Zwischen bis zu 6 Zeitprogrammprofilen (P1--P6) wechseln
- **Aktives Profil**: Festlegen, welchem Profil der Thermostat tatsaechlich folgt
- **Tagesweise Bearbeitung**: Auf einen Tag klicken, um Temperaturblöcke hinzuzufuegen, zu verschieben oder zu loeschen
- **Kopieren/Einfuegen**: Das Zeitprogramm eines Tages auf andere Tage kopieren
- **Rueckgaengig/Wiederherstellen**: Aenderungen zuruecknehmen oder erneut anwenden
- **Import/Export**: Zeitprogramme als JSON speichern und wiederherstellen

!!! info "Profile"
Ein **Profil** ist ein vollstaendiges Wochenprogramm. Die meisten Thermostate unterstuetzen mehrere Profile (z.B. "Normal", "Energiesparen", "Urlaub"). Das **aktive Profil** ist dasjenige, dem das Geraet aktuell folgt. Die Auswahl eines anderen Profils im Auswahlfeld laedt dessen Daten zur Anzeige/Bearbeitung und aktiviert es auf dem Geraet.

#### Geraete-Zeitprogramme {#device-schedules}

Fuer Nicht-Klima-Geraete (Schalter, Leuchten, Abdeckungen, Ventile):

- **Ereignisliste**: Zeigt alle geplanten Ereignisse nach Wochentag gruppiert
- **Ereigniseditor**: Jedes Ereignis konfigurieren mit:
  - **Uhrzeit**: Feste Uhrzeit (z.B. 06:00) oder astronomisch (relativ zum Sonnenauf-/Sonnenuntergang)
  - **Wochentage**: An welchen Tagen das Ereignis gilt
  - **Pegel**: Zielzustand (Ein/Aus fuer Schalter, 0--100% fuer Dimmer/Abdeckungen)
  - **Dauer**: Wie lange die Aktion dauert (optional)
  - **Rampenzeit**: Graduelle Uebergangszeit fuer Leuchten (optional)
  - **Zielkanaele**: Welche Kanaele gesteuert werden (bei Mehrkanal-Geraeten)

!!! tip "Zeitprogramm-Karten"
Fuer eine visuellere Bearbeitung von Zeitprogrammen die dedizierten Lovelace-Karten verwenden:

    - [Klima-Zeitprogramm-Karte](climate_schedule_card.md) fuer Thermostate
    - [Zeitprogramm-Karte](schedule_card.md) fuer Schalter, Leuchten, Abdeckungen und Ventile

---

### Aenderungsverlauf {#change-history}

Der Aenderungsverlauf fuehrt ein dauerhaftes Protokoll aller ueber das Panel vorgenommenen Parameteraenderungen.

Jeder Eintrag zeigt:

| Feld            | Beschreibung                                  |
| --------------- | --------------------------------------------- |
| **Zeitstempel** | Wann die Aenderung vorgenommen wurde          |
| **Geraet**      | Geraetename und Modell                        |
| **Kanal**       | Kanaladresse, die geaendert wurde             |
| **Parameter**   | Anzahl der geaenderten Parameter              |
| **Quelle**      | Art der Aenderung: Manuell, Import oder Kopie |

Auf einen Eintrag klicken, um die Details aufzuklappen und den alten und neuen Wert jedes Parameters einzusehen.

!!! info "Speicherung"
Der Verlauf wird ueber das Speichersystem von Home Assistant mit einem Limit von 500 Eintraegen pro Konfigurationseintrag gespeichert. Wenn das Limit erreicht ist, werden die aeltesten Eintraege automatisch entfernt.

Die Schaltflaeche **Verlauf loeschen** entfernt dauerhaft alle Eintraege (mit Bestaetigung).

---

## Registerkarte Integration {#integration}

Das Integration-Dashboard ueberwacht den Zustand und die Leistung der Homematic(IP) Local-Integration.

### Systemzustand {#system-health}

Zeigt den aktuellen Zustand der Integration:

| Feld               | Beschreibung                                                                                                                                                                                                                                           |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Central-Status** | Verbindungsstatus der Integration. "RUNNING" bedeutet, dass alles betriebsbereit ist. Andere Zustaende wie "STARTUP" oder "RECONNECT" zeigen an, dass die Integration initialisiert oder wiederhergestellt wird.                                       |
| **Zustandswert**   | Ein Prozentwert (0--100%), der die allgemeine Kommunikationsqualitaet der Geraete anzeigt. 100% bedeutet, dass alle Geraete erreichbar sind und normal kommunizieren. Ein niedrigerer Wert bedeutet, dass einige Geraete Kommunikationsprobleme haben. |

### Geraetestatistiken {#device-statistics}

Ein schneller Ueberblick ueber die Geraeteflotte:

| Feld                        | Beschreibung                                                       |
| --------------------------- | ------------------------------------------------------------------ |
| **Geraete gesamt**          | Anzahl der von dieser Integration verwalteten Geraete              |
| **Nicht erreichbar**        | Derzeit nicht reagierende Geraete (als Warnung angezeigt wenn > 0) |
| **Firmware aktualisierbar** | Geraete mit verfuegbaren Firmware-Updates                          |

### Befehlsdrosselung {#command-throttle}

Die **Befehlsdrosselung** ist ein Schutzmechanismus, der begrenzt, wie schnell Befehle an die CCU gesendet werden.

!!! question "Warum ist das noetig?"
Homematic-Geraete kommunizieren per Funk. Wenn zu viele Befehle in schneller Folge gesendet werden, koennen sie sich gegenseitig stoeren -- was zu verlorenen Befehlen oder verzoegerten Antworten fuehrt. Die Drosselung stellt sicher, dass Befehle zeitlich verteilt werden, insbesondere bei Automatisierungen oder Szenen, die viele Geraete gleichzeitig steuern.

| Feld                      | Beschreibung                                                                                    |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| **Aktiviert**             | Ob die Drosselung aktiv ist                                                                     |
| **Intervall**             | Mindestzeit zwischen Befehlen (in Sekunden)                                                     |
| **Warteschlangengroesse** | Anzahl der Befehle, die derzeit auf das Senden warten                                           |
| **Gedrosselt**            | Ob Befehle derzeit verzoegert werden                                                            |
| **Burst-Anzahl**          | Anzahl der Befehle, die in schneller Folge gesendet werden koennen, bevor die Drosselung greift |

Im Normalbetrieb ist die Warteschlange leer und "Gedrosselt" zeigt "Nein". Wenn die Warteschlange waechst oder die Drosselung aktiv ist, bedeutet dies, dass viele Befehle verarbeitet werden -- dies ist bei Szenen oder umfangreichen Automatisierungen zu erwarten.

### Vorkommnisse {#incidents}

**Vorkommnisse** sind protokollierte Kommunikationsereignisse, die zwischen der Integration und der CCU oder Geraeten aufgetreten sind. Dies sind **keine Fehler** und erfordern in der Regel **keine Massnahmen**.

!!! warning "Vorkommnisse sind keine Fehler"
Ein Vorkommnis bedeutet **nicht**, dass etwas kaputt ist. Es ist ein normaler Diagnoseeintrag -- aehnlich einem Flugschreiber. Haeufige Vorkommnisse umfassen:

    - Ein Geraet reagiert voruebergehend nicht (z.B. batteriebetriebenes Geraet im Schlafmodus)
    - Eine kurze Kommunikationsunterbrechung bei starkem Funkverkehr
    - Ein Geraet verbindet sich nach einem Stromausfall neu

    Diese Ereignisse werden automatisch behoben und nur zu Informationszwecken protokolliert. **Kein GitHub-Issue eroeffnen** wegen Vorkommnissen -- sie sind erwartetes Verhalten in einer drahtlosen Umgebung.

Wenn die Vorkommnisliste leer ist, ist das ideal -- es bedeutet, dass keine Kommunikationsunregelmaessigkeiten aufgezeichnet wurden.

Die Schaltflaeche **Vorkommnisse loeschen** entfernt alle protokollierten Vorkommnisse.

### Cache-Verwaltung {#cache}

Die Integration speichert Geraetemetadaten (Parameterbeschreibungen, Kanalinformationen) im Cache, um den Start zu beschleunigen. Bei Verdacht auf veralteten Cache (z.B. nach einem CCU-Firmware-Update) kann dieser geleert werden:

- **Cache leeren**: Loescht alle zwischengespeicherten Geraetedaten. Die Integration ruft beim naechsten Neustart alles erneut von der CCU ab.

!!! note
Das Leeren des Caches hat keinen Einfluss auf Geraetekonfigurationen oder Automatisierungen. Es erzwingt lediglich, dass die Integration die Geraetemetadaten erneut von der CCU einliest.

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

- **Sicherung erstellen**: Laedt eine CCU-Konfigurationssicherungsdatei herunter. Zeigt den Fortschritt an und meldet Dateinamen und Groesse nach Abschluss.

### Nachrichten {#messages}

Die Unterregisterkarte Nachrichten zeigt drei Kategorien von Systembenachrichtigungen. Ein Badge auf der Registerkarte zeigt die Gesamtzahl der aktiven Nachrichten.

#### Posteingang {#inbox}

Neue Geraete, die erkannt, aber noch nicht in das System uebernommen wurden. Auf **Akzeptieren** klicken, um ein Geraet hinzuzufuegen -- dabei wird zur Bestaetigung und optional zur Namenseingabe aufgefordert.

#### Servicemeldungen {#service-messages}

Servicemeldungen sind Systembenachrichtigungen der CCU ueber Geraetezustaende, die moeglicherweise Aufmerksamkeit erfordern:

| Typ                    | Bedeutung                                                            |
| ---------------------- | -------------------------------------------------------------------- |
| **Generisch**          | Allgemeine Benachrichtigung                                          |
| **Persistent**         | Dauerhafte Benachrichtigung, die bis zur Quittierung bestehen bleibt |
| **Konfig. ausstehend** | Ein Geraet wartet auf die Uebernahme einer Konfiguration             |
| **Alarm**              | Eine Warnbedingung (z.B. Batterie schwach, Sabotage)                 |
| **Update ausstehend**  | Ein Firmware-Update ist verfuegbar                                   |
| **Kommunikation**      | Ein Kommunikationsproblem wurde erkannt                              |

Jede Meldung zeigt Geraetename, Adresse, Meldungstyp, Beschreibung, Zeitstempel und einen Zaehler (wie oft sie aufgetreten ist). **Quittierbare** Meldungen koennen mit der Schaltflaeche **Quittieren** bestaetigt werden.

!!! tip
Die meisten Servicemeldungen loesen sich von selbst (z.B. ein batteriebetriebenes Geraet verbindet sich nach dem Aufwachen wieder). Die Meldungen dienen der Information -- sie erfordern nicht unbedingt sofortiges Handeln.

#### Alarmmeldungen {#alarm-messages}

Alarmmeldungen sind kritische Benachrichtigungen, die auf einen Zustand hinweisen, der Aufmerksamkeit erfordert (z.B. Sabotageerkennung, Sensorfehler). Jeder Alarm zeigt:

- Geraetename und Beschreibung
- Letzter Ausloesezeitpunkt
- Vorkommniszaehler
- Schaltflaeche **Quittieren** zum Loeschen des Alarms

### Signalqualitaet {#signal-quality}

Eine sortier- und filterbare Tabelle, die die Funksignalqualitaet aller Geraete zeigt:

| Spalte            | Beschreibung                                |
| ----------------- | ------------------------------------------- |
| **Geraet**        | Geraetename                                 |
| **Modell**        | Geraetemodell                               |
| **Schnittstelle** | Funkprotokoll (HmIP-RF, BidCos-RF)          |
| **Erreichbar**    | Ob das Geraet derzeit antwortet             |
| **RSSI**          | Signalstaerke in dBm (naeher an 0 = besser) |
| **Batterie**      | Batteriestatus (OK oder Schwach)            |

Die Filterleiste (angezeigt bei mehr als 10 Geraeten) ermoeglicht die Suche nach Name/Modell oder das Filtern nach Schnittstelle, Erreichbarkeit oder Batteriestatus.

!!! info "RSSI-Werte verstehen"
| Bereich | Qualitaet |
| ----- | ------- |
| -40 bis 0 dBm | Ausgezeichnet |
| -60 bis -40 dBm | Gut |
| -80 bis -60 dBm | Akzeptabel |
| -100 bis -80 dBm | Schlecht -- Geraet naeher platzieren oder einen Repeater hinzufuegen |
| Unter -100 dBm | Sehr schlecht -- Kommunikationsprobleme wahrscheinlich |

    Weitere Details unter [Ueber RSSI-Werte](../troubleshooting/rssi_fix.md).

### Firmware {#firmware}

Eine sortier- und filterbare Tabelle, die den Firmware-Status aller Geraete zeigt:

| Spalte             | Beschreibung                                 |
| ------------------ | -------------------------------------------- |
| **Geraet**         | Geraetename und Modell                       |
| **Aktuelle FW**    | Installierte Firmware-Version                |
| **Verfuegbare FW** | Neueste verfuegbare Firmware-Version         |
| **Status**         | Update-Status (aktuell, aktualisierbar usw.) |

Auf **Firmware-Daten aktualisieren** klicken, um die neuesten Firmware-Informationen von der CCU abzurufen.

!!! note
Firmware-Updates werden von der CCU verwaltet, nicht von dieser Integration. Das Panel zeigt den Status zu Informationszwecken an. Fuer Updates die CCU WebUI oder den geraeeteigenen Aktualisierungsmechanismus verwenden.

### Anlernmodus {#install-mode}

Der Anlernmodus versetzt die CCU in den **Kopplungsmodus**, damit neue Geraete dem Netzwerk beitreten koennen.

- Auf **Aktivieren** neben der gewuenschten Schnittstelle (HmIP-RF oder BidCos-RF) klicken
- Die CCU geht fuer 60 Sekunden in den Kopplungsmodus (ein Countdown wird angezeigt)
- Das neue Geraet waehrend dieser Zeit in den Kopplungsmodus versetzen (siehe Geraetehandbuch)
- Nach der Kopplung erscheint das Geraet im [Posteingang](#inbox)

!!! tip
Es werden nur Schnittstellen angezeigt, die tatsaechlich in der Integration konfiguriert sind. Falls eine Schnittstelle nicht sichtbar ist, die Integrationskonfiguration pruefen.

---

## Deep-Linking {#deep-linking}

Ueber URL-Hash-Parameter direkt zu einem bestimmten Geraet, Kanal oder einer Verknuepfungsansicht navigieren. Das Panel unterstuetzt die Browser-Vor-/Zurueck-Navigation fuer nahtloses Durchsuchen.

---

## Fehlerbehebung {#troubleshooting}

### Panel ist in der Seitenleiste nicht sichtbar

1. Sicherstellen, dass das Panel in den erweiterten Optionen aktiviert ist
2. Bestaetigen, dass die Anmeldung als Administrator erfolgt ist
3. Den Browser neu laden (Strg+F5)

### Parameter werden nicht gespeichert

1. Pruefen, ob das Geraet erreichbar ist (kein UNREACH)
2. Home Assistant-Protokolle auf XML-RPC-Fehler pruefen
3. Warten, bis CONFIG_PENDING auf dem Geraet aufgeloest ist

### Leere Parameterliste fuer einen Kanal

- Der Kanal hat moeglicherweise keine sichtbaren MASTER-Parameter
- Parameter ohne CCU-Uebersetzungen werden herausgefiltert (entspricht dem Verhalten der CCU WebUI)

---

## Siehe auch {#see-also}

- [Wochenprofile](week_profile.md) -- Zeitprogramm-Datenformat und Aktionen
- [Klima-Zeitprogramm-Karte](climate_schedule_card.md) -- Visueller Thermostat-Zeitprogrammeditor
- [Zeitprogramm-Karte](schedule_card.md) -- Visueller Geraete-Zeitprogrammeditor
- [Aktionsreferenz](homeassistant_actions.md) -- Alle verfuegbaren Service-Aktionen
- [Ueber RSSI-Werte](../troubleshooting/rssi_fix.md) -- Signalstaerke verstehen
