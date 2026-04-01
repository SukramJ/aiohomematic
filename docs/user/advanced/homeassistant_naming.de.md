---
translation_source: docs/user/advanced/homeassistant_naming.md
translation_date: 2026-04-01
translation_source_hash: 6b9c1c39f516
---

# Namenskonventionen

Dieses Dokument erklärt, wie Homematic(IP) Local für OpenCCU Geräte und Entities in Home Assistant benennt.

## Begriffe

| Begriff        | Beschreibung                                                                                                    |
| -------------- | --------------------------------------------------------------------------------------------------------------- |
| **Device**     | Physisches Gerät, das auf der CCU registriert ist (oder Hub-Level-Pseudogerät). Wird zu einem HA-Geräteeintrag. |
| **Channel**    | Funktionale Untereinheit eines Geräts. Ein Gerät kann mehrere Kanäle haben.                                     |
| **Data Point** | Parameter, der von einem Gerät/Kanal bereitgestellt wird (z.B. LEVEL, STATE).                                   |
| **Entity**     | Home Assistant Entity, die aus einem oder mehreren Data Points erstellt wird.                                   |

## Namensquellen

Namen werden aus folgenden Quellen bezogen, in absteigender Priorität:

1. **Benutzerdefinierte Namen aus der CCU** (Räume, Gerätenamen, Kanalnamen)
2. **Logische Homematic-Namen** (Gerätetyp, Kanalnummer) als Fallback
3. **Home Assistant Übersetzungen** für Parameter-/Entity-Typ (lokalisierte Namen)

## Gerätenamen

Der HA-Gerätename ist primär der **CCU-Gerätename**.

### Sub-Device-Benennung

Wenn "Sub-Devices" aktiviert sind und ein Gerät gruppierte Kanäle hat:

| Bedingung                                              | Gerätename                     |
| ------------------------------------------------------ | ------------------------------ |
| Master-Kanal hat nicht-leeren, nicht-numerischen Namen | Name des Master-Kanals         |
| Name des Master-Kanals ist numerisch                   | `{Gerätename}-{Master-Name}`   |
| Master-Kanal hat keinen Namen                          | `{Gerätename}-{Gruppennummer}` |

Wenn Sub-Devices deaktiviert sind, wird der einfache CCU-Gerätename verwendet.

## Entity-Namen

Entity-Namen kombinieren:

- Den Benutzer-/Geräte-/Kanalanteil aus der CCU
- Einen übersetzten Parameter-/Entity-Typ-Namen aus den HA-Übersetzungen

### Benennungsregeln

**Generische/Berechnete Entities:**

1. Ausgangspunkt ist der Name des Data Points (basierend auf Geräte-/Kanalnamen und Parameternamen)
2. Wenn Sub-Devices aktiviert und Sub-Devices vorhanden sind, wird nur der Parameter-Anteil verwendet
3. Der Roh-Parametername wird durch die HA-Übersetzung ersetzt (z.B. "Level" -> "Helligkeit" bei Lichtern)

**Custom Entities:**

1. Wenn der Entity-Name mit dem Gerätenamen beginnt, wird der Gerätename entfernt, um Doppelungen zu vermeiden
2. Der Roh-Parametername wird durch die HA-Übersetzung ersetzt

**Sonderfälle:**

- Wenn der Entity-Name gleich dem Gerätenamen ist -> Entity-Name wird leer gesetzt (HA zeigt nur den Gerätenamen an)
- Wenn der Entity-Name leer ist -> HA leitet den Namen aus Gerät und Plattform ab

### Übersetzungsentfernung

Wenn die HA-Übersetzung für einen bestimmten Entity-Namensschlüssel ein **leerer String** ist, wird der übersetzte Teil vollständig weggelassen.

## Eigenschaft "Gerätename verwenden"

Entities ohne eigenen eindeutigen Namen "verwenden den Gerätenamen" in HA. Dies wird über die Eigenschaft `use_device_name` bereitgestellt.

## Beispiele

### Dimmer-Kanal

- Gerät: "Wohnzimmer Licht"
- Parameter: LEVEL
- **Ergebnis:** Entity-Name "Helligkeit" (übersetzt von LEVEL)

### Schalter-Kanal

- Gerät: "Gartenpumpe"
- Parameter: STATE
- Custom Entity-Mapping: switch
- **Ergebnis:** Entity-Name "Schalter" oder leer (abhängig von Übersetzungen)

### Multi-Gruppen-Gerät

- Basisgerät: "RGB Controller"
- Master-Kanal: "Regal"
- **Ergebnis:**
  - Gerät: "Regal" (verwendet Master-Kanal-Name)
  - Entities: "Helligkeit", "Farbtemperatur" (Parameter-Anteile übersetzt, Gerätename entfernt)

## Tipps

1. **Zuerst in der CCU benennen** - Die Integration übernimmt CCU-Namen automatisch
2. **HA-Übersetzungen prüfen** - Einige Namen sind absichtlich leer, damit die UI sich auf den Gerätenamen konzentriert
3. **Aussagekräftige Namen verwenden** - Saubere Entity-IDs entstehen durch saubere Gerätenamen

## Siehe auch

- [aiohomematic Namenskonventionen](../../contributor/coding/naming.md)
- [Integrations-Anleitung](../homeassistant_integration.md)
