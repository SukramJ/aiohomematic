---
translation_source: docs/user/advanced/unignore.md
translation_date: 2026-04-01
translation_source_hash: c03ecfa1bb90
---

# Parameter sichtbar machen (Unignore)

Die Integration führt Listen von Parametern, die bei der Erstellung von Entitäten herausgefiltert werden. Diese Filterung sorgt für eine übersichtlichere Benutzererfahrung, indem technische oder selten genutzte Parameter ausgeblendet werden.

Für fortgeschrittene Benutzer, die Zugriff auf diese verborgenen Parameter benötigen, ermöglicht der **Unignore-Mechanismus** das gezielte Sichtbarmachen bestimmter Parameter als Entitäten.

!!! note
Für Definitionen von Begriffen wie Parameter, Channel und Paramset (VALUES, MASTER) siehe das [Glossar](../../reference/glossary.md).

## Bevor es losgeht

**Bitte Folgendes beachten:**

- Verwendung auf eigene Gefahr
- Übermäßiges Schreiben von `MASTER`-Paramset-Parametern kann Geräte beschädigen
- Entitätsanpassungen (Namen, Symbole) müssen über Home Assistant vorgenommen werden

## Konfiguration über die UI

1. **Einstellungen** -> **Geräte & Dienste** öffnen
2. Auf **Homematic(IP) Local** -> **Konfigurieren** klicken
3. Zur Seite **Schnittstelle** navigieren
4. **Erweiterte Konfiguration** aktivieren und fortfahren
5. Parameter zur **un_ignore**-Liste hinzufügen
6. Die Integration lädt nach dem Speichern automatisch neu

## Musterformat

```
DEVICE_TYPE:CHANNEL:PARAMETER
```

| Komponente    | Beschreibung                     | Beispiel      |
| ------------- | -------------------------------- | ------------- |
| `DEVICE_TYPE` | Gerätemodell oder `*` für alle   | `HmIP-eTRV-2` |
| `CHANNEL`     | Channel-Nummer oder `*` für alle | `0`, `1`, `*` |
| `PARAMETER`   | Parametername                    | `LOW_BAT`     |

## Beispiele

| Muster                  | Wirkung                                                |
| ----------------------- | ------------------------------------------------------ |
| `HmIP-eTRV-2:0:LOW_BAT` | LOW_BAT auf Channel 0 von HmIP-eTRV-2-Geräten anzeigen |
| `HmIP-SWDO:1:ERROR`     | ERROR auf Channel 1 von HmIP-SWDO-Geräten anzeigen     |
| `*:*:RSSI_PEER`         | RSSI_PEER auf allen Channels aller Geräte anzeigen     |
| `*:0:OPERATING_VOLTAGE` | OPERATING_VOLTAGE auf Channel 0 aller Geräte anzeigen  |

## Parameternamen finden

Um herauszufinden, welche Parameter ein Gerät hat:

1. **Gerätedefinition exportieren:**

   ```yaml
   action: homematicip_local.export_device_definition
   data:
     device_id: YOUR_DEVICE_ID
   ```

2. **CCU WebUI prüfen** -> Geräteeinstellungen -> Technische Daten anzeigen

3. **Die Action get_paramset verwenden:**

   ```yaml
   action: homematicip_local.get_paramset
   data:
     device_id: YOUR_DEVICE_ID
     channel: 0
     paramset_key: VALUES
   ```

## Siehe auch

- [Geräteunterstützung](../device_support.md) - Wie Geräte unterstützt werden
- [Actions-Referenz](../features/homeassistant_actions.md) - Direkter Gerätezugriff
- [Glossar](../../reference/glossary.md) - Begriffsreferenz
