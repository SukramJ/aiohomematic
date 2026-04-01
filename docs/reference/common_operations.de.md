---
translation_source: docs/reference/common_operations.md
translation_date: 2026-04-01
translation_source_hash: f36b25dfb759
---

# Referenz: Gängige Operationen

Dieses Dokument beschreibt die am häufigsten verwendeten Operationen in aiohomematic mit ausführlichen Beispielen und Best Practices.

> **Tipp:** Definitionen von Begriffen wie Device, Channel, Parameter und Systemvariable finden Sie im [Glossar](../reference/glossary.md).

## Inhaltsverzeichnis

1. [Verbindungsverwaltung](#verbindungsverwaltung)
2. [Geräteoperationen](#gerateoperationen)
3. [Wertoperationen](#wertoperationen)
4. [Ereignisbehandlung](#ereignisbehandlung)
5. [Programme und Systemvariablen](#programme-und-systemvariablen)
6. [Cache-Verwaltung](#cache-verwaltung)

---

## Verbindungsverwaltung

### Starten und Stoppen

```python
from aiohomematic.api import HomematicAPI
from aiohomematic.central import CentralConfig

async def main():
    config = CentralConfig.for_ccu(
        host="192.168.1.100",
        username="Admin",
        password="geheim",
    )

    api = HomematicAPI(config=config)

    # Verbindung starten
    await api.start()

    # Ihre Anwendungslogik hier...

    # Sauberes Herunterfahren
    await api.stop()
```

### Verbindungsstatus überwachen

```python
# Mit HomematicAPI
if api.is_connected:
    print("Verbunden")

# Mit CentralUnit für detaillierten Status
from aiohomematic.central import CentralUnit
from aiohomematic.const import CentralState

central: CentralUnit = api.central

# Gesamten Systemstatus prüfen
print(f"Central Status: {central.state}")

# Verschiedene Zustände zeigen unterschiedliche Systemgesundheit:
if central.state == CentralState.RUNNING:
    print("Alle Interfaces verbunden")
elif central.state == CentralState.DEGRADED:
    print("Einige Interfaces getrennt")
elif central.state == CentralState.FAILED:
    print("System fehlgeschlagen - maximale Wiederholungen erreicht")

# Verbindungsgesundheit pro Interface prüfen
if central.connection_state.is_any_issue:
    print(f"Verbindungsprobleme: {central.connection_state.issue_count}")

# Gerätestatus-Änderungen abonnieren
from aiohomematic.central.events import DeviceStateChangedEvent


async def on_device_updated(*, event: DeviceStateChangedEvent) -> None:
    """Gerätestatus-Änderungen behandeln."""
    print(f"Gerät aktualisiert: {event.device_address}")


unsubscribe_device = central.event_bus.subscribe(
    event_type=DeviceStateChangedEvent,
    event_key=None,
    handler=on_device_updated,
)

# Später: Benachrichtigungen beenden
unsubscribe_device()
```

### Wiederverbindung

Die Bibliothek behandelt die Wiederverbindung automatisch. Zum manuellen Auslösen:

```python
# Alle Clients neu starten
await central.client_coordinator.restart_clients()

# Oder Daten nach Wiederverbindung aktualisieren
await api.refresh_data()
```

---

## Geräteoperationen

### Alle Geräte auflisten

```python
# Einfache Auflistung
for device in api.list_devices():
    print(f"{device.address}: {device.name}")

# Mit Details
for device in api.list_devices():
    print(f"\nGerät: {device.address}")
    print(f"  Name: {device.name}")
    print(f"  Modell: {device.model}")
    print(f"  Typ: {device.device_type}")
    print(f"  Interface: {device.interface}")
    print(f"  Firmware: {device.firmware}")
    print(f"  Verfügbar: {device.available}")
```

### Geräte finden

```python
# Nach Adresse
device = api.get_device(address="VCU0000001")

# Nach Name (durch Liste filtern)
device = next(
    (d for d in api.list_devices() if d.name == "Wohnzimmer Schalter"),
    None,
)

# Nach Modell filtern
hmip_schalter = [
    d for d in api.list_devices()
    if d.model.startswith("HmIP-PS")
]

# Nach Interface filtern
from aiohomematic.const import Interface

hmip_geräte = [
    d for d in api.list_devices()
    if d.interface == Interface.HMIP_RF
]
```

### Auf Kanäle zugreifen

```python
device = api.get_device(address="VCU0000001")
if device:
    # Alle Kanäle abrufen
    for channel_no, channel in device.channels.items():
        print(f"Kanal {channel_no}: {channel.channel_address}")

    # Bestimmten Kanal abrufen
    channel = device.channels.get(1)
    if channel:
        print(f"Kanaladresse: {channel.channel_address}")
```

### Auf Data Points zugreifen

```python
device = api.get_device(address="VCU0000001")
if device:
    channel = device.channels.get(1)
    if channel:
        # Alle Data Points auflisten
        for param_name, dp in channel.data_points.items():
            print(f"{param_name}: {dp.value} ({dp.unit})")

        # Bestimmten Data Point abrufen
        state_dp = channel.data_points.get("STATE")
        if state_dp:
            print(f"Status-Wert: {state_dp.value}")
            print(f"Status-Einheit: {state_dp.unit}")
            print(f"Schreibbar: {state_dp.is_writable}")
```

---

## Wertoperationen

### Werte lesen

```python
# Mit HomematicAPI
value = await api.read_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
)

# Aus verschiedenen Paramsets lesen
from aiohomematic.const import ParamsetKey

# VALUES Paramset (Laufzeitwerte) - Standard
state = await api.read_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
    paramset_key=ParamsetKey.VALUES,
)

# MASTER Paramset (Konfiguration)
config_value = await api.read_value(
    channel_address="VCU0000001:0",
    parameter="CYCLIC_INFO_MSG",
    paramset_key=ParamsetKey.MASTER,
)
```

### Werte schreiben

```python
# Mit HomematicAPI
await api.write_value(
    channel_address="VCU0000001:1",
    parameter="STATE",
    value=True,
)

# Mit ConfigurationCoordinator für mehr Kontrolle
await central.configuration.put_paramset(
    channel_address="VCU0000001:1",
    paramset_key_or_link_address=ParamsetKey.VALUES,
    values={
        "STATE": True,
        "ON_TIME": 300,  # 5 Minuten
    },
)
```

### Werttypen und Einschränkungen

```python
# Parameter-Einschränkungen vor dem Schreiben prüfen
device = api.get_device(address="VCU0000001")
channel = device.channels.get(1)
level_dp = channel.data_points.get("LEVEL")

if level_dp:
    print(f"Min: {level_dp.min}")      # z.B. 0.0
    print(f"Max: {level_dp.max}")      # z.B. 1.0
    print(f"Standard: {level_dp.default}")
    print(f"Typ: {level_dp.type}")     # z.B. FLOAT

    # Sicheres Schreiben mit Validierung
    new_value = 0.5
    if level_dp.min <= new_value <= level_dp.max:
        await api.write_value(
            channel_address=channel.channel_address,
            parameter="LEVEL",
            value=new_value,
        )
```

---

## Ereignisbehandlung

### Einfaches Event-Abonnement

```python
from typing import Any

def on_update(address: str, parameter: str, value: Any) -> None:
    print(f"{address}.{parameter} = {value}")

# Abonnieren
unsubscribe = api.subscribe_to_updates(callback=on_update)

# ... Anwendung läuft ...

# Abonnement beenden
unsubscribe()
```

### Typisierte Ereignisbehandlung mit EventBus

```python
from aiohomematic.central.events import (
    DataPointValueReceivedEvent,
    DeviceStateChangedEvent,
    FirmwareStateChangedEvent,
)

# Data Point Updates
async def on_datapoint_update(*, event: DataPointValueReceivedEvent) -> None:
    print(f"DataPointKey: {event.dpk}")
    print(f"Wert: {event.value}")

central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_datapoint_update,
)

# Geräte-Events
async def on_device_event(*, event: DeviceStateChangedEvent) -> None:
    print(f"Gerät aktualisiert: {event.device_address}")

central.event_bus.subscribe(
    event_type=DeviceStateChangedEvent,
    event_key=None,
    handler=on_device_event,
)
```

### Events filtern

```python
from aiohomematic.const import DataPointKey, ParamsetKey

# Auf bestimmtes Gerät abonnieren durch Filtern im Handler
async def on_specific_device(*, event: DataPointValueReceivedEvent) -> None:
    if event.dpk.channel_address.startswith("VCU0000001"):
        print(f"Mein Gerät: {event.dpk.parameter} = {event.value}")

central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_specific_device,
)

# Mit spezifischem DataPointKey-Filter abonnieren
specific_dpk = DataPointKey(
    interface_id="BidCos-RF",
    channel_address="VCU0000001:1",
    paramset_key=ParamsetKey.VALUES,
    parameter="STATE",
)
central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=specific_dpk,
    handler=on_datapoint_update,
)
```

---

## Programme und Systemvariablen

### Programme auflisten

```python
# Über HubCoordinator
for program in central.hub_coordinator.program_data_points:
    print(f"Programm: {program.name}")
    print(f"  ID: {program.unique_id}")
    print(f"  Aktiv: {program.is_active}")
    print(f"  Intern: {program.is_internal}")
```

### Programme ausführen

```python
# Nach Name suchen (durch Liste filtern)
program = next(
    (p for p in central.hub_coordinator.program_data_points if p.name == "Aufwachlicht"),
    None,
)
if program:
    await program.press()

# Oder nach PID
program = central.hub_coordinator.get_program_data_point(pid="12345")
if program:
    await program.press()
```

### Systemvariablen lesen

```python
# Alle auflisten
for sysvar in central.hub_coordinator.sysvar_data_points:
    print(f"{sysvar.name}: {sysvar.value}")

# Bestimmte Variable abrufen (durch Liste filtern)
sysvar = next(
    (sv for sv in central.hub_coordinator.sysvar_data_points if sv.name == "Anwesenheit"),
    None,
)
if sysvar:
    print(f"Wert: {sysvar.value}")
```

### Systemvariablen schreiben

```python
sysvar = next(
    (sv for sv in central.hub_coordinator.sysvar_data_points if sv.name == "AlarmAktiv"),
    None,
)
if sysvar:
    # Boolean-Variable
    await sysvar.send_variable(value=True)

# Zahlenvariable
sysvar = next(
    (sv for sv in central.hub_coordinator.sysvar_data_points if sv.name == "Zieltemperatur"),
    None,
)
if sysvar:
    await sysvar.send_variable(value=21.5)

# String-Variable
sysvar = next(
    (sv for sv in central.hub_coordinator.sysvar_data_points if sv.name == "Statusmeldung"),
    None,
)
if sysvar:
    await sysvar.send_variable(value="Alle Systeme normal")
```

---

## Cache-Verwaltung

### Caches verstehen

aiohomematic verwendet mehrere Caches:

- **Device Description Cache**: Speichert Geräte-Metadaten
- **Paramset Description Cache**: Speichert Parameterdefinitionen
- **Data Cache**: Speichert aktuelle Laufzeitwerte

### Daten aktualisieren

```python
# Alle Gerätedaten aktualisieren
await api.refresh_data()

# Bestimmtes Gerät aktualisieren
device = api.get_device(address="VCU0000001")
if device:
    await device.refresh_data()

# Hub-Daten aktualisieren (Programme, Systemvariablen)
await central.hub_coordinator.fetch_program_data()
await central.hub_coordinator.fetch_sysvar_data()
```

### Cache-Speicherort

Caches werden im konfigurierten Speicherverzeichnis abgelegt:

```python
config = CentralConfig.for_ccu(
    host="192.168.1.100",
    username="Admin",
    password="geheim",
    storage_directory="/pfad/zum/cache",  # Standard: aktuelles Verzeichnis
)
```

### Caches leeren

Die Cache-Verwaltung wird intern von aiohomematic behandelt. Caches werden beim Start und bei der Wiederverbindung automatisch aktualisiert. Um ein erneutes Abrufen der Gerätedaten zu erzwingen, stoppen und starten Sie die CentralUnit neu.

---

## Erweiterte Operationen

### Direkte RPC-Aufrufe

Für fortgeschrittene Anwendungsfälle können Sie direkt auf die Clients zugreifen:

```python
# Client für bestimmtes Interface abrufen
from aiohomematic.const import Interface

client = central.client_coordinator.get_client(interface=Interface.HMIP_RF)
if client:
    # Low-Level RPC-Aufruf
    result = await client.get_value(
        channel_address="VCU0000001:1",
        paramset_key="VALUES",
        parameter="STATE",
    )
```

### Geräte-Firmware-Updates

```python
# Firmware-Status prüfen
for device in api.list_devices():
    if device.firmware_update_state:
        print(f"{device.name}: {device.firmware_update_state}")

# Firmware-Update auslösen (über Client)
client = central.client_coordinator.get_client(interface=Interface.HMIP_RF)
await client.update_device_firmware(device_address="VCU0000001")
```

### Link Peers (Direkte Gerätekommunikation)

```python
# Link Peers für ein Gerät abrufen (über Client)
client = central.client_coordinator.get_client(interface=Interface.HMIP_RF)
peers = await client.get_link_peers(channel_address="VCU0000001:1")
for peer in peers:
    print(f"Verknüpft mit: {peer}")

# Verknüpfung erstellen (über LinkCoordinator)
await central.link.add_link(
    sender_channel_address="VCU0000001:1",
    receiver_channel_address="VCU0000002:1",
    name="Meine Verknüpfung",
    description="Taster steuert Licht",
)

# Verknüpfung entfernen
await central.link.remove_link(
    sender_channel_address="VCU0000001:1",
    receiver_channel_address="VCU0000002:1",
)
```

---

## Fehlerreferenz

| Exception               | Beschreibung                     | Häufige Ursachen                  |
| ----------------------- | -------------------------------- | --------------------------------- |
| `NoConnectionException` | Keine Verbindung zum Backend     | Netzwerkprobleme, CCU offline     |
| `AuthFailure`           | Authentifizierung fehlgeschlagen | Falsche Anmeldedaten              |
| `ValidationException`   | Wertvalidierung fehlgeschlagen   | Wert außerhalb des Bereichs       |
| `ClientException`       | Allgemeiner Client-Fehler        | RPC-Aufruf fehlgeschlagen         |
| `UnsupportedException`  | Operation nicht unterstützt      | Backend unterstützt Methode nicht |

```python
from aiohomematic.exceptions import (
    NoConnectionException,
    AuthFailure,
    ValidationException,
    ClientException,
)

try:
    await api.write_value(
        channel_address="VCU0000001:1",
        parameter="LEVEL",
        value=1.5,
    )
except ValidationException as e:
    print(f"Ungültiger Wert: {e}")
except NoConnectionException:
    print("Verbindung verloren, wird wiederholt...")
except AuthFailure:
    print("Prüfen Sie Ihre Anmeldedaten")
except ClientException as e:
    print(f"RPC-Fehler: {e}")
```
