---
translation_source: docs/user/advanced/optional_settings.md
translation_date: 2026-04-01
translation_source_hash: bd81bbe4ebfa
---

# Optionale Einstellungen (Experimentelle Funktionen)

## Uebersicht

Optionale Einstellungen sind Feature-Flags, mit denen neue, experimentelle Implementierungen in der Homematic(IP) Local Integration getestet werden koennen. Diese Einstellungen werden ueber die Home Assistant Integrationsoptionen konfiguriert.

**Wichtig**: Dies sind experimentelle Funktionen. Sie sind standardmaessig nicht aktiviert und sollten nur eingeschaltet werden, wenn die Bereitschaft besteht, Feedback zu geben und moegliche Instabilitaet in Kauf zu nehmen.

**Aktueller Status**: Alle experimentellen Funktionen haben umfassende Unit- und Integrationstests bestanden. Sie wurden zudem von Entwicklern mit realer Hardware (CCU3, OpenCCU) getestet. Der naechste Schritt sind Feldtests durch Benutzer mit unterschiedlichen Setups, um die Kompatibilitaet ueber alle Umgebungen hinweg vor der allgemeinen Veroeffentlichung sicherzustellen.

---

## Warum gibt es diese Einstellungen?

### Die Herausforderung

Die Homematic(IP) Local Integration unterstuetzt eine Vielzahl von Backend-Systemen:

- **CCU3/CCU2** - Originale eQ-3 Homematic-Zentralen
- **OpenCCU** - Community-basierte CCU fuer Raspberry Pi und andere Plattformen
- **Homegear** - Open-Source Homematic-Backend
- **CCU-Jack** - JSON-RPC-Bridge fuer CCU
- **debmatic** - Homematic auf Debian-basierten Systemen

Jedes dieser Systeme weist subtile Verhaltensunterschiede auf. Wenn neue, verbesserte Implementierungen von Kernkomponenten entwickelt werden, kann der bestehende Code nicht einfach ueber Nacht ersetzt werden - dies wuerde riskieren, Systeme fuer Tausende von Benutzern zu beeintraechtigen.

### Die Loesung: Opt-In-Tests

Anstatt neuen Code fuer alle zu erzwingen, werden Feature-Flags verwendet:

1. **Eigene Entscheidung**, ob die neue Implementierung ausprobiert wird
2. **Alter und neuer Code existieren** nebeneinander
3. **Einfaches Zuruecksetzen** - die Einstellung einfach deaktivieren, wenn etwas schiefgeht
4. **Das Feedback** hilft, Probleme vor der allgemeinen Veroeffentlichung zu identifizieren

Dieser Ansatz ermoeglicht es, neue Architekturen gruendlich in realen Umgebungen zu testen, bevor sie fuer alle zum Standard werden.

---

## Zugriff auf optionale Einstellungen

Um experimentelle Funktionen zu aktivieren oder zu deaktivieren:

1. **Einstellungen** -> **Geraete & Dienste** oeffnen
2. **Homematic(IP) Local** suchen und anklicken
3. Auf **Konfigurieren** klicken
4. Zur Konfigurationsseite **Erweitert** navigieren
5. Den Abschnitt **Optionale Einstellungen** suchen
6. Die gewuenschten Einstellungen aktivieren
7. Home Assistant neu starten, damit die Aenderungen wirksam werden

---

## Verfuegbare Einstellungen

### Entwickler-/Debugging-Einstellungen

Die folgenden Einstellungen sind **nicht fuer normale Benutzer gedacht**. Sie dienen ausschliesslich zu Debugging-Zwecken und sollten nur aktiviert werden, wenn ein Entwickler dies zur Diagnose eines Problems ausdruecklich anfordert.

| Einstellung                     | Zweck                                                                     |
| ------------------------------- | ------------------------------------------------------------------------- |
| **SR_RECORD_SYSTEM_INIT**       | Zeichnet die gesamte Kommunikation waehrend des Starts fuer Debugging auf |
| **SR_DISABLE_RANDOMIZE_OUTPUT** | Macht aufgezeichnete Daten deterministisch fuer die Testerstellung        |

**Diese Einstellungen nicht aktivieren, es sei denn, ein Entwickler fordert dazu auf.** Sie erzeugen zusaetzliche Daten, koennen die Leistung beeintraechtigen und bieten im Normalbetrieb keinen Vorteil.

---

## Wer sollte diese Einstellungen verwenden?

| Wenn man...                                                             | Empfehlung                                     |
| ----------------------------------------------------------------------- | ---------------------------------------------- |
| Ein normaler Benutzer ist, der einfach moechte, dass alles funktioniert | Alle Einstellungen auf Standard belassen       |
| Neugierig auf neue Funktionen ist, aber Stabilitaet benoetigt           | Auf die allgemeine Veroeffentlichung warten    |
| Bereit ist zu testen und Probleme zu melden                             | Eine Einstellung nach der anderen ausprobieren |
| Ein spezifisches Problem hat, das ein Entwickler debuggen moechte       | Nur die angeforderte Einstellung aktivieren    |

---

## Feedback geben

Beim Testen einer experimentellen Funktion ist das Feedback unschaetzbar wertvoll. Folgende Informationen sind am hilfreichsten:

**[Warum sind Diagnosen und Protokolle so wichtig?](../../contributor/testing/debug_data_importance.md)** - Detaillierte Erklaerung, welche Daten benoetigt werden und warum.

### Was funktioniert hat

- "Interface Client funktioniert einwandfrei mit OpenCCU 3.x"

### Was nicht funktioniert hat

Bitte Folgendes angeben:

1. **Welche Einstellung** aktiviert wurde
2. **Der Backend-Typ** (CCU3, OpenCCU, Homegear usw.)
3. **Was passiert ist** (Fehlermeldungen, unerwartetes Verhalten)
4. **Home Assistant-Protokolle** mit aktivierter Debug-Protokollierung (siehe unten)

### Debug-Protokollierung aktivieren

**Option 1: Ueber die Home Assistant UI**

1. **Einstellungen** -> **Geraete & Dienste** oeffnen
2. **Homematic(IP) Local** suchen und anklicken
3. Auf **Debug-Protokollierung aktivieren** klicken
4. Das Problem reproduzieren
5. Auf **Debug-Protokollierung deaktivieren** klicken - die Protokolldatei wird automatisch heruntergeladen

**Option 2: Ueber configuration.yaml**

```yaml
logger:
  logs:
    aiohomematic: debug
```

Nach dem Hinzufuegen Home Assistant neu starten und die Protokolle unter **Einstellungen** -> **System** -> **Protokolle** pruefen.

### Wo melden

- **GitHub Issues**: https://github.com/sukramj/aiohomematic/issues
- Beim Melden den Tag `experimental-feature` verwenden

---

## Risiken und Empfehlungen

### Vor dem Aktivieren einer experimentellen Einstellung

1. **Eine Sicherung** der CCU erstellen
2. **Die aktuelle Konfiguration notieren**, fuer den Fall einer notwendigen Ruecksetzung
3. **Debug-Protokollierung aktivieren**, damit Daten verfuegbar sind, falls etwas schiefgeht

### Nach dem Aktivieren

1. **Home Assistant neu starten**, damit die Einstellung wirksam wird
2. **Die Geraete testen** - pruefen, ob Schalter, Sensoren, Thermostate korrekt reagieren
3. **24-48 Stunden ueberwachen**, bevor die Einstellung als stabil betrachtet wird

### Wenn etwas schiefgeht

1. **Die experimentelle Einstellung deaktivieren** in den Integrationsoptionen
2. **Home Assistant neu starten**
3. **Das Problem melden** mit den Protokollen

Der Vorteil von Feature-Flags ist, dass das Zuruecksetzen immer nur einen Klick entfernt ist.

---

## Fahrplan

| Einstellung                      | Aktueller Status    | Zukunft                                                 |
| -------------------------------- | ------------------- | ------------------------------------------------------- |
| Interface Client                 | Test                | Wird zum Standard, wenn die Tests erfolgreich verlaufen |
| Debugging-Einstellungen (SR\_\*) | Entwicklerwerkzeuge | Bleiben dauerhaft Opt-in                                |

Sobald eine experimentelle Funktion ueber verschiedene Backend-Typen hinweg gruendlich getestet wurde und positives Feedback erhaelt, wird sie zur Standardimplementierung befoeordert. Zu diesem Zeitpunkt wird die alte Implementierung als veraltet markiert und schliesslich entfernt.

---

## Zusammenfassung

- **Experimentelle Einstellungen** ermoeglichen eine Vorschau auf kommende Verbesserungen
- **Das Feedback** beeinflusst direkt, ob Funktionen veroeffentlicht werden
- **Einfaches Zuruecksetzen**, wenn etwas schiefgeht
- **Nicht fuer jeden** - nur aktivieren, wenn die Bereitschaft besteht, Probleme zu melden
- **Debugging-Einstellungen** sind Entwicklerwerkzeuge, keine Benutzerfunktionen

Vielen Dank fuer die Mithilfe bei der Verbesserung von Homematic(IP) Local!
