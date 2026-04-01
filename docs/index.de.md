---
translation_source: docs/index.md
translation_date: 2026-04-01
translation_source_hash: f3d60a848470
---

# aiohomematic

[![PyPI version](https://badge.fury.io/py/aiohomematic.svg)](https://badge.fury.io/py/aiohomematic)
[![Python versions](https://img.shields.io/pypi/pyversions/aiohomematic.svg)](https://pypi.org/project/aiohomematic/)
[![License](https://img.shields.io/github/license/sukramj/aiohomematic)](https://github.com/sukramj/aiohomematic/blob/master/LICENSE)

**Moderne async Python-Bibliothek für Homematic- und HomematicIP-Geräte.**

aiohomematic bildet die Grundlage der [Homematic(IP) Local](https://github.com/sukramj/homematicip_local)-Integration für Home Assistant und ermöglicht die lokale Steuerung von Homematic-Geräten ohne Cloud-Abhängigkeit.

---

## Funktionen

- **Async-first**: Basiert auf `asyncio` für nicht-blockierende I/O-Operationen
- **Typsicher**: Vollständig typisiert mit strikter `mypy`-Durchsetzung
- **Automatische Erkennung**: Automatische Entity-Erstellung aus Geräte-Parametern
- **Erweiterbar**: Benutzerdefinierte Entity-Klassen für gerätespezifische Funktionen
- **Schneller Start**: Paramset-Caching für schnelle Initialisierung
- **Multi-Backend**: Unterstützt CCU3, CCU2, Homegear und RaspberryMatic

## Schnellstart

### Installation

```bash
pip install aiohomematic
```

### Grundlegende Verwendung

```python
import asyncio
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import Interface

async def main():
    # Configure the central unit
    config = CentralConfig(
        name="my-ccu",
        host="192.168.1.100",
        username="Admin",
        password="your-password",
        central_id="my-central",
        interface_configs={
            InterfaceConfig(
                central_name="my-ccu",
                interface=Interface.HMIP_RF,
                port=2010,
            ),
        },
    )

    # Create and start the central
    central = config.create_central()
    await central.start()

    # Access devices
    for address, device in central.devices.items():
        print(f"Device: {device.name} ({address})")

    # Stop the central
    await central.stop()

asyncio.run(main())
```

## Dokumentationsübersicht

### Für Benutzer (Home Assistant)

- [Benutzerhandbuch](user/homeassistant_integration.md) - Vollständige Integrationsanleitung
- **Funktionen**:
  - [Action-Referenz](user/features/homeassistant_actions.md) - Verfügbare Home Assistant Actions
  - [CCU-Sicherung](user/features/backup.md) - Sicherungsagent und manuelle Sicherung
  - [Berechnete Klima-Sensoren](user/features/calculated_climate_sensors.md) - Abgeleitete Klimamesswerte
  - [Klimaplan-Karte](user/features/climate_schedule_card.md) - Klimaplan-UI-Karte
  - [Gerätekonfigurations-Panel](user/features/config_panel.md) - Gerätekonfiguration in HA
  - [Optimistische Aktualisierungen](user/features/optimistic_updates.md) - Sofortiges UI-Feedback und Rollback
  - [Zeitplan-Karte](user/features/schedule_card.md) - Zeitplan-Verwaltungs-UI-Karte
  - [Wochenprofil](user/features/week_profile.md) - Wochenplan-Verwaltung
- [Fehlerbehebung](troubleshooting/index.md) - Häufige Probleme und Lösungen
- [Häufige Fragen](faq.md) - Häufig gestellte Fragen
- [Glossar](reference/glossary.md) - Begriffsübersicht

### Für Entwickler (Bibliotheksnutzung)

- [Schnellstart](quickstart.md) - In 5 Minuten einsatzbereit
- [Erste Schritte](getting_started.md) - Detaillierte Einrichtungsanleitung
- [Consumer API](developer/consumer_api.md) - API-Muster für Integrationen
- [API-Referenz](reference/api/index.md) - Automatisch generierte API-Dokumentation
- [Architektur](architecture.md) - Übersicht über das Systemdesign
- [Protokoll-Auswahlleitfaden](architecture/protocol_selection_guide.md) - Auswahl der richtigen Protokoll-Schnittstelle

### Für Mitwirkende

- [Mitwirken](contributor/contributing.md) - So kann man beitragen
- [Coding-Standards](contributor/coding/naming.md) - Namens- und Stilkonventionen
- [ADRs](adr/index.md) - Architecture Decision Records
- [Änderungsprotokoll](changelog.md) - Versionshistorie

## Unterstützte Geräte

aiohomematic unterstützt eine breite Palette von Homematic- und HomematicIP-Geräten:

| Kategorie     | Beispiele                         |
| ------------- | --------------------------------- |
| **Klima**     | HmIP-eTRV, HmIP-BWTH, HM-CC-RT-DN |
| **Abdeckung** | HmIP-BROLL, HmIP-FBL, HM-LC-Bl1   |
| **Licht**     | HmIP-BDT, HmIP-BSL, HM-LC-Dim1T   |
| **Schloss**   | HmIP-DLD, HM-Sec-Key              |
| **Schalter**  | HmIP-PS, HmIP-BSM, HM-LC-Sw1      |
| **Sensor**    | HmIP-SRH, HmIP-SWSD, HmIP-SMI     |
| **Sirene**    | HmIP-ASIR, HmIP-MP3P              |

Eine vollständige Liste ist in der Dokumentation der [Erweiterungspunkte](developer/extension_points.md) zu finden.

## Zwei Projekte, ein Ökosystem

Diese Dokumentation umfasst **zwei verwandte, aber separate Projekte**:

| Projekt                 | Typ               | Zweck                                  | Repository                                                        |
| ----------------------- | ----------------- | -------------------------------------- | ----------------------------------------------------------------- |
| **aiohomematic**        | Python-Bibliothek | Protokollimplementierung, Gerätemodell | [aiohomematic](https://github.com/sukramj/aiohomematic)           |
| **Homematic(IP) Local** | HA-Integration    | Home Assistant Entities, UI, Services  | [homematicip_local](https://github.com/sukramj/homematicip_local) |

### Welche Dokumentation wird benötigt?

- **Home Assistant-Benutzer?** → Mit dem [Benutzerhandbuch](user/homeassistant_integration.md) beginnen
- **Eine Python-Anwendung erstellen?** → Siehe [Schnellstart](quickstart.md) und [Consumer API](developer/consumer_api.md)
- **Code beitragen?** → Den [Leitfaden für Mitwirkende](contributor/contributing.md) lesen

### Architekturübersicht

```
Home Assistant
     │
     ▼
Homematic(IP) Local Integration    ← HA-spezifisch: Entities, Services, UI
     │
     ▼
aiohomematic-Bibliothek            ← Eigenständig: Protokoll, Geräte, Ereignisse
     │
     ▼
CCU3 / OpenCCU / Homegear          ← Backend-Hardware/-Software
     │
     ▼
Homematic-Geräte                  ← Physische Geräte
```

Siehe [Home Assistant Lebenszyklus](developer/homeassistant_lifecycle.md) für den detaillierten Integrationsablauf.

## Links

- **GitHub**: [sukramj/aiohomematic](https://github.com/sukramj/aiohomematic)
- **PyPI**: [aiohomematic](https://pypi.org/project/aiohomematic/)
- **Fehler melden**: [Einen Fehler melden](https://github.com/sukramj/aiohomematic/issues)
- **Diskussionen**: [Fragen stellen](https://github.com/sukramj/aiohomematic/discussions)
- **HA-Integration**: [homematicip_local](https://github.com/sukramj/homematicip_local)

## Lizenz

MIT-Lizenz - siehe [LICENSE](https://github.com/sukramj/aiohomematic/blob/master/LICENSE) für Details.
