---
translation_source: docs/getting_started.md
translation_date: 2026-04-01
translation_source_hash: b394c6091930
---

# Erste Schritte mit aiohomematic

Diese Anleitung bietet alles, was Sie benötigen, um aiohomematic als eigenständige Python-Bibliothek zur Steuerung von Homematic- und HomematicIP-Geräten zu verwenden.

> **Tipp:** Definitionen von Begriffen wie Backend, Interface, Device, Channel und Parameter finden Sie im [Glossar](reference/glossary.md).

## Installation

```bash
pip install aiohomematic
```

## Schnellstart

### Verwendung der vereinfachten API (empfohlen)

Der einfachste Einstieg ist mit der `HomematicAPI`-Fassade über den async Context Manager:

```python
import asyncio
from aiohomematic.api import HomematicAPI

async def main():
    # Verbinden über den async Context Manager (empfohlen)
    async with HomematicAPI.connect(
        host="192.168.1.100",
        username="Admin",
        password="ihr-passwort",
    ) as api:
        # Alle Geräte auflisten
        for device in api.list_devices():
            print(f"{device.address}: {device.name} ({device.model})")

        # Einen Wert lesen
        state = await api.read_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
        )
        print(f"Aktueller Status: {state}")

        # Einen Wert schreiben
        await api.write_value(
            channel_address="VCU0000001:1",
            parameter="STATE",
            value=True,
        )

    # Verbindung wird beim Verlassen des Kontexts automatisch geschlossen

asyncio.run(main())
```

#### Verbindungsoptionen

Die `connect()`-Methode unterstützt verschiedene Optionen:

```python
# CCU mit TLS
async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
    tls=True,
    verify_tls=False,  # In Produktion auf True setzen
) as api:
    ...

# Homegear Backend
async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
    backend="homegear",
) as api:
    ...

# Benutzerdefinierte Central ID
async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
    central_id="mein-wohnzimmer-ccu",
) as api:
    ...
```

### Manuelle Lifecycle-Verwaltung

Für mehr Kontrolle über den Lifecycle können Sie Start/Stop manuell verwalten:

```python
import asyncio
from aiohomematic.api import HomematicAPI
from aiohomematic.central import CentralConfig

async def main():
    config = CentralConfig.for_ccu(
        name="meine-ccu",
        host="192.168.1.100",
        username="Admin",
        password="ihr-passwort",
        central_id="meine-ccu",
    )

    api = HomematicAPI(config=config)
    await api.start()

    try:
        for device in api.list_devices():
            print(f"{device.address}: {device.name}")
    finally:
        await api.stop()

asyncio.run(main())
```

### CentralUnit direkt verwenden

Für mehr Kontrolle verwenden Sie `CentralUnit` direkt:

```python
import asyncio
from aiohomematic.central import CentralConfig
from aiohomematic.client import InterfaceConfig
from aiohomematic.const import Interface

async def main():
    # Interfaces manuell definieren
    interface_configs = {
        InterfaceConfig(
            central_name="meine-ccu",
            interface=Interface.HMIP_RF,
            port=2010,
        ),
        InterfaceConfig(
            central_name="meine-ccu",
            interface=Interface.BIDCOS_RF,
            port=2001,
        ),
    }

    # Konfiguration erstellen
    config = CentralConfig(
        name="meine-ccu",
        host="192.168.1.100",
        username="Admin",
        password="ihr-passwort",
        central_id="eindeutige-id",
        interface_configs=interface_configs,
    )

    # CentralUnit erstellen und starten
    central = config.create_central()
    await central.start()

    try:
        # Auf Geräte zugreifen
        for device in central.devices:
            print(f"{device.address}: {device.name}")

    finally:
        await central.stop()

asyncio.run(main())
```

## Konfigurations-Presets

aiohomematic bietet komfortable Factory-Methoden für gängige Backend-Typen:

### CCU3/CCU2

```python
from aiohomematic.central import CentralConfig

# Einfache Einrichtung mit HmIP-RF und BidCos-RF
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
)

# Mit TLS und zusätzlichen Interfaces
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
    tls=True,
    enable_bidcos_wired=True,
    enable_virtual_devices=True,
)
```

### Homegear

```python
from aiohomematic.central import CentralConfig

config = CentralConfig.for_homegear(
    host="192.168.1.50",
    username="homegear",
    password="geheim",
)
```

## Gängige Muster

### Geräteerkennung

```python
# Alle Geräte auflisten
for device in api.list_devices():
    print(f"Gerät: {device.address}")
    print(f"  Name: {device.name}")
    print(f"  Modell: {device.model}")
    print(f"  Kanäle: {len(device.channels)}")

    # Kanäle und deren Data Points auflisten
    for channel in device.channels.values():
        print(f"  Kanal {channel.channel_no}:")
        for dp in channel.data_points.values():
            print(f"    - {dp.parameter}: {dp.value}")
```

### Werte lesen

```python
# Von einem bestimmten Kanal und Parameter lesen
value = await api.read_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
)

# Direkt über Data Points des Geräts lesen
device = api.get_device(address="VCU0000001")
if device:
    channel = device.channels.get(1)
    if channel:
        state_dp = channel.data_points.get("STATE")
        if state_dp:
            print(f"Status: {state_dp.value}")
```

### Werte schreiben

```python
# Schalter einschalten
await api.write_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
    value=True,
)

# Dimmer-Level setzen (0.0 bis 1.0)
await api.write_value(
    channel_address="VCU0000002:1",
    parameter="LEVEL",
    value=0.5,
)

# Thermostat-Temperatur setzen
await api.write_value(
    channel_address="VCU0000003:1",
    parameter="SET_POINT_TEMPERATURE",
    value=21.5,
)
```

### Events abonnieren

```python
from typing import Any

def on_value_changed(address: str, parameter: str, value: Any) -> None:
    print(f"Aktualisierung: {address}.{parameter} = {value}")

# Alle Data Point Updates abonnieren
unsubscribe = api.subscribe_to_updates(callback=on_value_changed)

# ... Ihre Anwendungslogik ...

# Abonnement beenden
unsubscribe()
```

### EventBus direkt verwenden

Für mehr Kontrolle über die Ereignisbehandlung:

```python
from aiohomematic.central.events import DataPointValueReceivedEvent, DeviceStateChangedEvent

async def on_datapoint_update(*, event: DataPointValueReceivedEvent) -> None:
    print(f"DataPoint {event.dpk} = {event.value}")

async def on_device_update(*, event: DeviceStateChangedEvent) -> None:
    print(f"Gerät aktualisiert: {event.device_address}")

# Bestimmte Events abonnieren
central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_datapoint_update,
)

central.event_bus.subscribe(
    event_type=DeviceStateChangedEvent,
    event_key=None,
    handler=on_device_update,
)
```

## Fehlerbehandlung

### Gängige Exceptions

```python
from aiohomematic.exceptions import (
    AioHomematicException,      # Basis-Exception
    ClientException,            # Client-/Verbindungsfehler
    NoConnectionException,      # Keine Verbindung zum Backend
    AuthFailure,                # Authentifizierung fehlgeschlagen
    ValidationException,        # Wertvalidierung fehlgeschlagen
)

try:
    await api.write_value(
        channel_address="VCU0000001:1",
        parameter="LEVEL",
        value=1.5,  # Ungültig: muss 0.0-1.0 sein
    )
except ValidationException as e:
    print(f"Validierungsfehler: {e}")
except NoConnectionException as e:
    print(f"Verbindung verloren: {e}")
except AioHomematicException as e:
    print(f"Allgemeiner Fehler: {e}")
```

### Verbindungswiederherstellung

Die Bibliothek behandelt die Verbindungswiederherstellung automatisch. Sie können den Verbindungsstatus überwachen:

```python
# Verbindungsstatus prüfen
if api.is_connected:
    print("Verbunden mit Backend")
else:
    print("Nicht verbunden")

# Geräteverfügbarkeits-Änderungen abonnieren
from aiohomematic.central.events import DeviceStateChangedEvent

async def on_device_updated(*, event: DeviceStateChangedEvent) -> None:
    print(f"Gerät {event.device_address} wurde aktualisiert")

unsubscribe = central.event_bus.subscribe(
    event_type=DeviceStateChangedEvent,
    event_key=None,
    handler=on_device_updated,
)
```

## Arbeiten mit bestimmten Gerätetypen

### Schalter

```python
# Schalterstatus abrufen
state = await api.read_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
)

# Schalter umschalten
await api.write_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
    value=not state,
)
```

### Dimmer

```python
# Aktuellen Level abrufen (0.0-1.0)
level = await api.read_value(
    channel_address="VCU0000002:1",
    parameter="LEVEL",
)

# Auf 75% setzen
await api.write_value(
    channel_address="VCU0000002:1",
    parameter="LEVEL",
    value=0.75,
)
```

### Thermostate

```python
# Aktuelle Temperatur lesen
current_temp = await api.read_value(
    channel_address="VCU0000003:1",
    parameter="ACTUAL_TEMPERATURE",
)

# Sollwert lesen
set_point = await api.read_value(
    channel_address="VCU0000003:1",
    parameter="SET_POINT_TEMPERATURE",
)

# Neue Temperatur setzen
await api.write_value(
    channel_address="VCU0000003:1",
    parameter="SET_POINT_TEMPERATURE",
    value=22.0,
)
```

### Jalousien/Abdeckungen

```python
# Aktuelle Position abrufen (0.0=geschlossen, 1.0=offen)
position = await api.read_value(
    channel_address="VCU0000004:1",
    parameter="LEVEL",
)

# Jalousie vollständig öffnen
await api.write_value(
    channel_address="VCU0000004:1",
    parameter="LEVEL",
    value=1.0,
)

# Bewegung stoppen
await api.write_value(
    channel_address="VCU0000004:1",
    parameter="STOP",
    value=True,
)
```

## Programme und Systemvariablen

### Programme ausführen

```python
# Auf Programme über den Hub zugreifen
for program in central.hub.programs:
    print(f"Programm: {program.name}")

# Ein Programm ausführen
program = central.get_program_by_name("MeinProgramm")
if program:
    await program.execute()
```

### Systemvariablen

```python
# Systemvariable lesen
for sysvar in central.hub.sysvars:
    print(f"{sysvar.name}: {sysvar.value}")

# Systemvariable aktualisieren
sysvar = central.get_sysvar_by_name("MeineSysVar")
if sysvar:
    await sysvar.set_value(42)
```

## Best Practices

1. **Immer async Kontext verwenden**: Alle Netzwerkoperationen sind asynchron.

2. **Ordnungsgemäß aufräumen**: Immer `stop()` aufrufen, um Ressourcen freizugeben.

3. **Verbindungsabbrüche behandeln**: Die Bibliothek verbindet sich automatisch neu, aber Ihr Code sollte vorübergehende Verbindungsabbrüche ordnungsgemäß behandeln.

4. **Keyword-Argumente verwenden**: Alle API-Methoden verwenden Keyword-Only-Parameter für Klarheit.

5. **Vor dem Schreiben validieren**: Parameter-Constraints prüfen, bevor Werte geschrieben werden, um Validierungsfehler zu vermeiden.

6. **Events abonnieren**: Event-Abonnements statt Polling für Echtzeit-Updates verwenden.

## Nächste Schritte

- Siehe [Gängige Operationen](reference/common_operations.md) für detailliertere Beispiele
- Lesen Sie die [Architektur](architecture.md)-Dokumentation für fortgeschrittene Nutzung
- Sehen Sie sich die [Consumer API](developer/consumer_api.md) für Integrationsmuster an
