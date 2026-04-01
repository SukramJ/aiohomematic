---
translation_source: docs/user/advanced/unignore.md
translation_date: 2026-04-01
translation_source_hash: c03ecfa1bb90
---

# Parameter sichtbar machen (Unignore)

Die Integration fuehrt Listen von Parametern, die bei der Erstellung von Entitaeten herausgefiltert werden. Diese Filterung sorgt fuer eine uebersichtlichere Benutzererfahrung, indem technische oder selten genutzte Parameter ausgeblendet werden.

Fuer fortgeschrittene Benutzer, die Zugriff auf diese verborgenen Parameter benoetigen, ermoeglicht der **Unignore-Mechanismus** das gezielte Sichtbarmachen bestimmter Parameter als Entitaeten.

!!! note
Fuer Definitionen von Begriffen wie Parameter, Channel und Paramset (VALUES, MASTER) siehe das [Glossar](../../reference/glossary.md).

## Bevor es losgeht

**Bitte Folgendes beachten:**

- Verwendung auf eigene Gefahr
- Uebermaeassiges Schreiben von `MASTER`-Paramset-Parametern kann Geraete beschaedigen
- Entitaetsanpassungen (Namen, Symbole) muessen ueber Home Assistant vorgenommen werden

## Konfiguration ueber die UI

1. **Einstellungen** -> **Geraete & Dienste** oeffnen
2. Auf **Homematic(IP) Local** -> **Konfigurieren** klicken
3. Zur Seite **Schnittstelle** navigieren
4. **Erweiterte Konfiguration** aktivieren und fortfahren
5. Parameter zur **un_ignore**-Liste hinzufuegen
6. Die Integration laedt nach dem Speichern automatisch neu

## Musterformat

```
DEVICE_TYPE:CHANNEL:PARAMETER
```

| Komponente    | Beschreibung                      | Beispiel      |
| ------------- | --------------------------------- | ------------- |
| `DEVICE_TYPE` | Geraetemodell oder `*` fuer alle  | `HmIP-eTRV-2` |
| `CHANNEL`     | Channel-Nummer oder `*` fuer alle | `0`, `1`, `*` |
| `PARAMETER`   | Parametername                     | `LOW_BAT`     |

## Beispiele

| Muster                  | Wirkung                                                 |
| ----------------------- | ------------------------------------------------------- |
| `HmIP-eTRV-2:0:LOW_BAT` | LOW_BAT auf Channel 0 von HmIP-eTRV-2-Geraeten anzeigen |
| `HmIP-SWDO:1:ERROR`     | ERROR auf Channel 1 von HmIP-SWDO-Geraeten anzeigen     |
| `*:*:RSSI_PEER`         | RSSI_PEER auf allen Channels aller Geraete anzeigen     |
| `*:0:OPERATING_VOLTAGE` | OPERATING_VOLTAGE auf Channel 0 aller Geraete anzeigen  |

## Parameternamen finden

Um herauszufinden, welche Parameter ein Geraet hat:

1. **Geraetedefinition exportieren:**

   ```yaml
   action: homematicip_local.export_device_definition
   data:
     device_id: YOUR_DEVICE_ID
   ```

2. **CCU WebUI pruefen** -> Geraeteeinstellungen -> Technische Daten anzeigen

3. **Die Action get_paramset verwenden:**

   ```yaml
   action: homematicip_local.get_paramset
   data:
     device_id: YOUR_DEVICE_ID
     channel: 0
     paramset_key: VALUES
   ```

## Siehe auch

- [Geraeteunterstuetzung](../device_support.md) - Wie Geraete unterstuetzt werden
- [Actions-Referenz](../features/homeassistant_actions.md) - Direkter Geraetezugriff
- [Glossar](../../reference/glossary.md) - Begriffsreferenz
