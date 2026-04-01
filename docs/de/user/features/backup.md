---
translation_source: docs/user/features/backup.md
translation_date: 2026-04-01
translation_source_hash: e800ef3de188
---

# CCU-Sicherung

Die Homematic(IP) Local-Integration bietet zwei Sicherungsmechanismen: einen **Backup Agent**, der in das Home Assistant-Sicherungssystem integriert ist, und eine **manuelle Sicherungsschaltfläche** für CCU-Systemsicherungen bei Bedarf.

---

## Backup Agent

Die Integration registriert einen **LocalBackupAgent**, der als Sicherungsspeicherort in der Home Assistant-Sicherungsoberfläche erscheint (**Settings** → **System** → **Backups**). Pro CCU-Konfigurationseintrag wird ein Agent registriert, sodass Multi-CCU-Setups separate Agents erhalten.

### Funktionsweise

Wenn eine Home Assistant-Sicherung erstellt und die CCU als Speicherort ausgewählt wird:

1. Der Agent erstellt zunächst eine **CCU-Systemsicherung** (`.sbk`-Datei), indem er über ein ReGa-Skript eine vollständige Sicherung von der CCU anfordert
2. Die CCU-Sicherung wird heruntergeladen und im konfigurierten Sicherungsverzeichnis gespeichert
3. Die **HA-Sicherung** (`.tar`-Datei) wird im selben Verzeichnis abgelegt
4. Eine **Metadaten-Datei** (`*_meta.json`) verknüpft die HA-Sicherung mit der zugehörigen CCU-Sicherung

Das bedeutet, dass jede auf der CCU gespeicherte HA-Sicherung von einer passenden CCU-Systemsicherung begleitet wird, was einen vollständigen Wiederherstellungspunkt für beide Systeme ergibt.

### Ausfallsicherheit

- **CCU nicht erreichbar**: Ist die CCU beim Ausführen der HA-Sicherung nicht erreichbar, wird die HA-Sicherung ohne CCU-Sicherung gespeichert (eine Warnung wird protokolliert)
- **CCU-Sicherung fehlgeschlagen**: Schlägt die CCU-Sicherung aus irgendeinem Grund fehl, wird die HA-Sicherung normal fortgesetzt — Fehler bei der CCU-Sicherung blockieren niemals HA-Sicherungen
- **Metadaten-Konsistenz**: Können Metadaten nicht gespeichert werden, wird eine bereits erstellte CCU-Sicherung automatisch bereinigt
- **Bereinigung verwaister Dateien**: Beim Auflisten von Sicherungen werden Metadaten-Dateien ohne zugehörige `.tar`-Datei automatisch entfernt

### Sicherungen verwalten

Die gesamte Sicherungsverwaltung erfolgt über die Standard-Sicherungsoberfläche von Home Assistant:

| Aktion            | Verhalten                                                                         |
| ----------------- | --------------------------------------------------------------------------------- |
| **Auflisten**     | Zeigt alle im CCU-Sicherungsverzeichnis gespeicherten HA-Sicherungen an           |
| **Herunterladen** | Lädt die HA-Sicherungs-`.tar`-Datei herunter                                      |
| **Löschen**       | Entfernt die HA-Sicherung, ihre Metadaten und die zugehörige CCU-`.sbk`-Sicherung |

---

## Sicherungsschaltfläche

Die Integration erstellt eine **"Sicherung erstellen"**-Taste auf dem CCU-Gerät. Durch Betätigung wird eine eigenständige CCU-Systemsicherung (`.sbk`-Datei) bei Bedarf erstellt — unabhängig vom HA-Sicherungssystem.

Die Taste ist verfügbar, solange die CCU erreichbar ist. Die resultierende Sicherungsdatei wird im konfigurierten Sicherungsverzeichnis gespeichert.

---

## Sicherungsverzeichnis

Sowohl der Backup Agent als auch die Sicherungsschaltfläche speichern Dateien in:

```
<ha-config>/homematicip_local/backup/
```

Dieses Verzeichnis wird automatisch erstellt, wenn die erste Sicherung durchgeführt wird. Es enthält:

| Dateityp      | Beschreibung                                                 |
| ------------- | ------------------------------------------------------------ |
| `*.tar`       | Home Assistant-Sicherungsarchive (erstellt durch HA Core)    |
| `*_meta.json` | Metadaten, die HA-Sicherungen mit CCU-Sicherungen verknüpfen |
| `*.sbk`       | CCU-Systemsicherungen                                        |

---

## CCU-Sicherungs-Service

Die Integration stellt außerdem einen `homematicip_local.create_ccu_backup`-Service zur Verwendung in Automationen bereit:

```yaml
service: homematicip_local.create_ccu_backup
data:
  entry_id: "your_config_entry_id"
```

Dieser erstellt und lädt eine CCU-Systemsicherung herunter, identisch zum Betätigen der Sicherungsschaltfläche.

---

## Wiederherstellung

### Wann eine Wiederherstellung erforderlich ist

Eine CCU-Wiederherstellung ist erforderlich, wenn:

- Die CCU-Hardware ausgetauscht oder auf Werkseinstellungen zurückgesetzt wurde
- Ein Firmware-Update Geräte- oder Konfigurationsprobleme verursacht hat
- Gerätekopplungen, Programme oder Systemvariablen verloren gegangen sind
- Eine Migration auf eine neue CCU durchgeführt wird

### Wiederherstellung über Home Assistant

Auf der CCU gespeicherte Home Assistant-Sicherungen enthalten sowohl die HA-Sicherung (`.tar`) als auch die CCU-Systemsicherung (`.sbk`). Zur Wiederherstellung:

1. Zu **Settings** -> **System** -> **Backups** navigieren
2. Die gewünschte Sicherung auswählen
3. Dem Home Assistant-Wiederherstellungsassistenten folgen, um die HA-Sicherung wiederherzustellen
4. Die zugehörige CCU-Sicherung (`.sbk`-Datei) im Sicherungsverzeichnis suchen:
   ```
   <ha-config>/homematicip_local/backup/
   ```
5. Die CCU-Sicherung separat über das CCU-WebUI wiederherstellen (siehe unten)

Die Home Assistant-Wiederherstellung stellt die CCU **nicht** automatisch wieder her. Die CCU muss unabhängig über ihre `.sbk`-Datei wiederhergestellt werden.

### Wiederherstellung über das CCU-WebUI

1. Das CCU-WebUI im Browser öffnen (z. B. `http://<ccu-ip>`)
2. Zu **Einstellungen** -> **Sicherheit** -> **Systemsicherung** navigieren
3. Auf **Wiederherstellen** klicken und die `.sbk`-Datei aus dem Sicherungsverzeichnis auswählen
4. Die Wiederherstellung bestätigen und warten, bis die CCU neu gestartet ist
5. Nach dem Neustart die Homematic(IP) Local-Integration in Home Assistant neu starten

### Überprüfung nach der Wiederherstellung

Nach der Wiederherstellung überprüfen, ob das System korrekt funktioniert:

- Sicherstellen, dass alle Geräte in Home Assistant angezeigt werden und aktuelle Zustände aufweisen
- Bestätigen, dass Gerätekopplungen intakt sind (Geräte reagieren auf Befehle)
- Überprüfen, ob CCU-Programme und Systemvariablen im CCU-WebUI vorhanden sind
- Das Integrationsprotokoll auf Verbindungsfehler oder fehlende Geräte prüfen

### Wenn die Wiederherstellung fehlschlägt

- **CCU startet nach der Wiederherstellung nicht**: Einen Werksreset auf der CCU durchführen und dann die Wiederherstellung mit einer anderen `.sbk`-Datei erneut versuchen
- **Geräte fehlen nach der Wiederherstellung**: Die betroffenen Geräte erneut mit der CCU koppeln. Geräte-DataPoints erscheinen automatisch wieder in Home Assistant
- **Integration kann keine Verbindung herstellen**: Die Integration neu starten. Falls sich die CCU-IP-Adresse geändert hat, die Integrationskonfiguration unter **Settings** -> **Devices & Services** aktualisieren
- **Sicherungsdatei beschädigt**: Eine ältere `.sbk`-Datei aus dem Sicherungsverzeichnis verwenden. Regelmäßige Sicherungen (über den Backup Agent oder Automationen) stellen sicher, dass immer eine aktuelle, funktionierende Sicherung verfügbar ist
