---
translation_source: docs/index.md
translation_date: 2026-04-01
translation_source_hash: f3d60a848470
---

# aiohomematic

[![PyPI version](https://badge.fury.io/py/aiohomematic.svg)](https://badge.fury.io/py/aiohomematic)
[![Python versions](https://img.shields.io/pypi/pyversions/aiohomematic.svg)](https://pypi.org/project/aiohomematic/)
[![License](https://img.shields.io/github/license/sukramj/aiohomematic)](https://github.com/sukramj/aiohomematic/blob/master/LICENSE)

**Moderne async Python-Bibliothek fuer Homematic- und HomematicIP-Geraete.**

aiohomematic bildet die Grundlage der [Homematic(IP) Local](https://github.com/sukramj/homematicip_local)-Integration fuer Home Assistant und ermoeglicht die lokale Steuerung von Homematic-Geraeten ohne Cloud-Abhaengigkeit.

---

## Funktionen

- **Async-first**: Basiert auf `asyncio` fuer nicht-blockierende I/O-Operationen
- **Typsicher**: Vollstaendig typisiert mit strikter `mypy`-Durchsetzung
- **Automatische Erkennung**: Automatische Entity-Erstellung aus Geraete-Parametern
- **Erweiterbar**: Benutzerdefinierte Entity-Klassen fuer geraetespezifische Funktionen
- **Schneller Start**: Paramset-Caching fuer schnelle Initialisierung
- **Multi-Backend**: Unterstuetzt CCU3, CCU2, Homegear und RaspberryMatic

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

## Dokumentationsuebersicht

### Fuer Benutzer (Home Assistant)

- [Benutzerhandbuch](user/homeassistant_integration.md) - Vollstaendige Integrationsanleitung
- **Funktionen**:
  - [Action-Referenz](user/features/homeassistant_actions.md) - Verfuegbare Home Assistant Actions
  - [CCU-Sicherung](user/features/backup.md) - Sicherungsagent und manuelle Sicherung
  - [Berechnete Klima-Sensoren](user/features/calculated_climate_sensors.md) - Abgeleitete Klimamesswerte
  - [Klimaplan-Karte](user/features/climate_schedule_card.md) - Klimaplan-UI-Karte
  - [Geraetekonfigurations-Panel](user/features/config_panel.md) - Geraetekonfiguration in HA
  - [Optimistische Aktualisierungen](user/features/optimistic_updates.md) - Sofortiges UI-Feedback und Rollback
  - [Zeitplan-Karte](user/features/schedule_card.md) - Zeitplan-Verwaltungs-UI-Karte
  - [Wochenprofil](user/features/week_profile.md) - Wochenplan-Verwaltung
- [Fehlerbehebung](troubleshooting/index.md) - Haeufige Probleme und Loesungen
- [Haeufige Fragen](faq.md) - Haeufig gestellte Fragen
- [Glossar](reference/glossary.md) - Begriffsuebersicht

### Fuer Entwickler (Bibliotheksnutzung)

- [Schnellstart](quickstart.md) - In 5 Minuten einsatzbereit
- [Erste Schritte](getting_started.md) - Detaillierte Einrichtungsanleitung
- [Consumer API](developer/consumer_api.md) - API-Muster fuer Integrationen
- [API-Referenz](reference/api/index.md) - Automatisch generierte API-Dokumentation
- [Architektur](architecture.md) - Uebersicht ueber das Systemdesign
- [Protokoll-Auswahlleitfaden](architecture/protocol_selection_guide.md) - Auswahl der richtigen Protokoll-Schnittstelle

### Fuer Mitwirkende

- [Mitwirken](contributor/contributing.md) - So kann man beitragen
- [Coding-Standards](contributor/coding/naming.md) - Namens- und Stilkonventionen
- [ADRs](adr/index.md) - Architecture Decision Records
- [Aenderungsprotokoll](changelog.md) - Versionshistorie

## Unterstuetzte Geraete

aiohomematic unterstuetzt eine breite Palette von Homematic- und HomematicIP-Geraeten:

| Kategorie     | Beispiele                         |
| ------------- | --------------------------------- |
| **Klima**     | HmIP-eTRV, HmIP-BWTH, HM-CC-RT-DN |
| **Abdeckung** | HmIP-BROLL, HmIP-FBL, HM-LC-Bl1   |
| **Licht**     | HmIP-BDT, HmIP-BSL, HM-LC-Dim1T   |
| **Schloss**   | HmIP-DLD, HM-Sec-Key              |
| **Schalter**  | HmIP-PS, HmIP-BSM, HM-LC-Sw1      |
| **Sensor**    | HmIP-SRH, HmIP-SWSD, HmIP-SMI     |
| **Sirene**    | HmIP-ASIR, HmIP-MP3P              |

Eine vollstaendige Liste ist in der Dokumentation der [Erweiterungspunkte](developer/extension_points.md) zu finden.

## Zwei Projekte, ein Oekosystem

Diese Dokumentation umfasst **zwei verwandte, aber separate Projekte**:

| Projekt                 | Typ               | Zweck                                   | Repository                                                        |
| ----------------------- | ----------------- | --------------------------------------- | ----------------------------------------------------------------- |
| **aiohomematic**        | Python-Bibliothek | Protokollimplementierung, Geraetemodell | [aiohomematic](https://github.com/sukramj/aiohomematic)           |
| **Homematic(IP) Local** | HA-Integration    | Home Assistant Entities, UI, Services   | [homematicip_local](https://github.com/sukramj/homematicip_local) |

### Welche Dokumentation wird benoetigt?

- **Home Assistant-Benutzer?** → Mit dem [Benutzerhandbuch](user/homeassistant_integration.md) beginnen
- **Eine Python-Anwendung erstellen?** → Siehe [Schnellstart](quickstart.md) und [Consumer API](developer/consumer_api.md)
- **Code beitragen?** → Den [Leitfaden fuer Mitwirkende](contributor/contributing.md) lesen

### Architekturuebersicht

```
Home Assistant
     │
     ▼
Homematic(IP) Local Integration    ← HA-spezifisch: Entities, Services, UI
     │
     ▼
aiohomematic-Bibliothek            ← Eigenstaendig: Protokoll, Geraete, Ereignisse
     │
     ▼
CCU3 / OpenCCU / Homegear          ← Backend-Hardware/-Software
     │
     ▼
Homematic-Geraete                  ← Physische Geraete
```

Siehe [Home Assistant Lebenszyklus](developer/homeassistant_lifecycle.md) fuer den detaillierten Integrationsablauf.

## Links

- **GitHub**: [sukramj/aiohomematic](https://github.com/sukramj/aiohomematic)
- **PyPI**: [aiohomematic](https://pypi.org/project/aiohomematic/)
- **Fehler melden**: [Einen Fehler melden](https://github.com/sukramj/aiohomematic/issues)
- **Diskussionen**: [Fragen stellen](https://github.com/sukramj/aiohomematic/discussions)
- **HA-Integration**: [homematicip_local](https://github.com/sukramj/homematicip_local)

## Lizenz

MIT-Lizenz - siehe [LICENSE](https://github.com/sukramj/aiohomematic/blob/master/LICENSE) fuer Details.
