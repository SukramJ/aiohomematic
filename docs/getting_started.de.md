---
translation_source: docs/getting_started.md
translation_date: 2026-07-10
translation_source_hash: b394c6091930
---

# Erste Schritte mit aiohomematic

Diese Anleitung bietet alles, was Sie benötigen, um aiohomematic als eigenständige Python-Bibliothek zur Steuerung von Homematic- und HomematicIP-Geräten zu verwenden. Sie behandelt `CentralConfig` und `CentralUnit`, die manuelle Lifecycle-Verwaltung und die explizite Interface-Konfiguration.

> **Tipp:** Definitionen von Begriffen wie Backend, Interface, Device, Channel und Parameter finden Sie im [Glossar](reference/glossary.md).

## Installation

```bash
pip install aiohomematic
```

## Schnellstart

### Verwendung des Async-Kontextmanagers (empfohlen)

`CentralUnit` unterstützt das Async-Kontextmanager-Protokoll direkt -- `async with central:` ruft beim Betreten `start()` und beim Verlassen `stop()` auf und garantiert so das Aufräumen selbst dann, wenn eine Exception auftritt:

```python
import asyncio
from aiohomematic.central import CentralConfig
from aiohomematic.const import ParamsetKey

async def main():
    config = CentralConfig.for_ccu(
        host="192.168.1.100",
        username="Admin",
        password="ihr-passwort",
    )
    central = await config.create_central()

    async with central:
        # Alle Geräte auflisten
        for device in central.devices:
            print(f"{device.address}: {device.name} ({device.model})")

        # Einen Wert lesen
        device = central.device_coordinator.get_device(address="VCU0000001")
        client = central.client_coordinator.get_client(interface_id=device.interface_id)
        state = await client.get_value(
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
        )
        print(f"Aktueller Status: {state}")

        # Einen Wert schreiben
        await client.set_value(
            channel_address="VCU0000001:1",
            paramset_key=ParamsetKey.VALUES,
            parameter="STATE",
            value=True,
        )

    # Verbindung wird beim Verlassen des Kontexts automatisch geschlossen

asyncio.run(main())
```

#### Verbindungsoptionen

`CentralConfig.for_ccu()` und `CentralConfig.for_homegear()` unterstützen verschiedene Optionen:

```python
# CCU mit TLS
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
    tls=True,
    verify_tls=False,  # In Produktion auf True setzen
)

# Homegear Backend
config = CentralConfig.for_homegear(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
)

# Benutzerdefinierte Central ID
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
    central_id="mein-wohnzimmer-ccu",
)
```

### Manuelle Lifecycle-Verwaltung

Für mehr Kontrolle über den Lifecycle können Sie Start/Stop anstelle des Kontextmanagers manuell verwalten:

```python
import asyncio
from aiohomematic.central import CentralConfig

async def main():
    config = CentralConfig.for_ccu(
        name="meine-ccu",
        host="192.168.1.100",
        username="Admin",
        password="ihr-passwort",
        central_id="meine-ccu",
    )

    central = await config.create_central()
    await central.start()

    try:
        for device in central.devices:
            print(f"{device.address}: {device.name}")
    finally:
        await central.stop()

asyncio.run(main())
```

### CentralUnit mit expliziter Interface-Konfiguration

Für volle Kontrolle darüber, welche Interfaces aktiviert sind und auf welchen Ports sie laufen, konfigurieren Sie `interface_configs` explizit, statt die Presets `for_ccu()`/`for_homegear()` zu verwenden:

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
    central = await config.create_central()
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

Die folgenden Beispiele setzen eine laufende `central: CentralUnit` voraus (siehe [Schnellstart](#schnellstart) oben). Um rohe Parameterwerte zu lesen oder zu schreiben, muss zunächst der für das Interface des Geräts zuständige Client ermittelt werden:

```python
from aiohomematic.const import ParamsetKey

def get_client_for(*, address: str):
    """Den für eine Geräteadresse zuständigen Client ermitteln."""
    device = central.device_coordinator.get_device(address=address)
    client = central.client_coordinator.get_client(interface_id=device.interface_id)
    return client
```

### Geräteerkennung

```python
# Alle Geräte auflisten
for device in central.devices:
    print(f"Gerät: {device.address}")
    print(f"  Name: {device.name}")
    print(f"  Modell: {device.model}")
    print(f"  Kanäle: {len(device.channels)}")

    # Kanäle durchlaufen (device.channels ist Mapping[str, ChannelProtocol], geschlüsselt nach Kanaladresse)
    for channel in device.channels.values():
        print(f"  Kanal {channel.no}: {channel.address}")
        # Generische Data Points liefern die Werte pro Parameter
        for dp in channel.generic_data_points:
            print(f"    - {dp.parameter}: {dp.value}")
```

### Werte lesen

```python
# Von einem bestimmten Kanal und Parameter lesen
client = get_client_for(address="VCU0000001")
value = await client.get_value(
    channel_address="VCU0000001:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="STATE",
)

# Direkt über den Kanal eines Geräts lesen
device = central.device_coordinator.get_device(address="VCU0000001")
if device:
    # device.channels ist nach Kanaladresse geschlüsselt (z.B. "VCU0000001:1"), nicht nach Integer-Nummer
    channel = device.channels.get("VCU0000001:1")
    if channel:
        # Generischen Data Point anhand des Parameternamens suchen
        state_dp = next(
            (dp for dp in channel.generic_data_points if dp.parameter == "STATE"),
            None,
        )
        if state_dp:
            print(f"Status: {state_dp.value}")
```

### Werte schreiben

```python
# Schalter einschalten
client = get_client_for(address="VCU0000001")
await client.set_value(
    channel_address="VCU0000001:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="STATE",
    value=True,
)

# Dimmer-Level setzen (0.0 bis 1.0)
client = get_client_for(address="VCU0000002")
await client.set_value(
    channel_address="VCU0000002:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="LEVEL",
    value=0.5,
)

# Thermostat-Temperatur setzen
client = get_client_for(address="VCU0000003")
await client.set_value(
    channel_address="VCU0000003:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="SET_POINT_TEMPERATURE",
    value=21.5,
)
```

### Events abonnieren

```python
from aiohomematic.central.events import DataPointValueReceivedEvent

async def on_value_changed(*, event: DataPointValueReceivedEvent) -> None:
    print(f"Aktualisierung: {event.dpk.channel_address}.{event.dpk.parameter} = {event.value}")

# Alle Data Point Updates abonnieren
unsubscribe = central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_value_changed,
)

# ... Ihre Anwendungslogik ...

# Abonnement beenden
unsubscribe()
```

### EventBus für Geräte-Events verwenden

Der `EventBus` ist der einzige Mechanismus für die Zustellung aller Ereignisse -- Data-Point-Updates und Geräte-Lifecycle-Änderungen sind lediglich unterschiedliche Event-Typen auf demselben Bus:

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
    client = get_client_for(address="VCU0000001")
    await client.set_value(
        channel_address="VCU0000001:1",
        paramset_key=ParamsetKey.VALUES,
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
if central.client_coordinator.has_clients and not central.connection_state.is_any_issue:
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
client = get_client_for(address="VCU0000001")
state = await client.get_value(
    channel_address="VCU0000001:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="STATE",
)

# Schalter umschalten
await client.set_value(
    channel_address="VCU0000001:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="STATE",
    value=not state,
)
```

### Dimmer

```python
# Aktuellen Level abrufen (0.0-1.0)
client = get_client_for(address="VCU0000002")
level = await client.get_value(
    channel_address="VCU0000002:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="LEVEL",
)

# Auf 75% setzen
await client.set_value(
    channel_address="VCU0000002:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="LEVEL",
    value=0.75,
)
```

### Thermostate

```python
client = get_client_for(address="VCU0000003")

# Aktuelle Temperatur lesen
current_temp = await client.get_value(
    channel_address="VCU0000003:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="ACTUAL_TEMPERATURE",
)

# Sollwert lesen
set_point = await client.get_value(
    channel_address="VCU0000003:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="SET_POINT_TEMPERATURE",
)

# Neue Temperatur setzen
await client.set_value(
    channel_address="VCU0000003:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="SET_POINT_TEMPERATURE",
    value=22.0,
)
```

### Jalousien/Abdeckungen

```python
client = get_client_for(address="VCU0000004")

# Aktuelle Position abrufen (0.0=geschlossen, 1.0=offen)
position = await client.get_value(
    channel_address="VCU0000004:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="LEVEL",
)

# Jalousie vollständig öffnen
await client.set_value(
    channel_address="VCU0000004:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="LEVEL",
    value=1.0,
)

# Bewegung stoppen
await client.set_value(
    channel_address="VCU0000004:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="STOP",
    value=True,
)
```

## Programme und Systemvariablen

CCU-Programme und Systemvariablen werden als **Hub-Data-Points** bereitgestellt, die vom
`HubCoordinator` erzeugt werden. Sie verhalten sich wie reguläre Data Points (Wert, Abonnement,
Setzen), statt in einer eigenen `Hub.programs`- / `Hub.sysvars`-Sammlung zu leben.

Die unterstützten Zugriffsmuster finden Sie im Consumer-API-Guide:
[developer/consumer_api.md](developer/consumer_api.md), Abschnitt "Hub data points". Für die
Design-Begründung und den Lifecycle siehe [architecture.md](architecture.md) und
[ADR 0022 — Unified Schedule Access](adr/0022-week-profile-data-point.md).

## Best Practices

1. **Immer async Kontext verwenden**: Alle Netzwerkoperationen sind asynchron.

2. **Ordnungsgemäß aufräumen**: Immer `stop()` aufrufen, um Ressourcen freizugeben (oder `async with central:` verwenden).

3. **Verbindungsabbrüche behandeln**: Die Bibliothek verbindet sich automatisch neu, aber Ihr Code sollte vorübergehende Verbindungsabbrüche ordnungsgemäß behandeln.

4. **Keyword-Argumente verwenden**: Alle API-Methoden verwenden Keyword-Only-Parameter für Klarheit.

5. **Vor dem Schreiben validieren**: Parameter-Constraints prüfen, bevor Werte geschrieben werden, um Validierungsfehler zu vermeiden.

6. **Events abonnieren**: Event-Abonnements statt Polling für Echtzeit-Updates verwenden.

## Nächste Schritte

- Siehe [Gängige Operationen](reference/common_operations.md) für detailliertere Beispiele
- Lesen Sie die [Architektur](architecture.md)-Dokumentation für fortgeschrittene Nutzung
- Sehen Sie sich die [Consumer API](developer/consumer_api.md) für Integrationsmuster an
