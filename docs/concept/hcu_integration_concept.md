# Konzept: Gemeinsame Fassade für CCU und HCU

**Status**: Entwurf
**Datum**: 2026-02-19
**Autor**: Claude (im Auftrag von Markus)

---

## Inhaltsverzeichnis

1. [Ausgangslage](#1-ausgangslage)
2. [Analyse der beiden Systeme](#2-analyse-der-beiden-systeme)
3. [Kernproblem: Inkompatible Gerätemodelle](#3-kernproblem-inkompatible-gerätemodelle)
4. [Architekturoptionen](#4-architekturoptionen)
5. [Empfohlene Architektur: Shared-Facade mit dualen Backends](#5-empfohlene-architektur-shared-facade-mit-dualen-backends)
6. [Detailentwurf der Fassade](#6-detailentwurf-der-fassade)
7. [Mapping der Gerätemodelle](#7-mapping-der-gerätemodelle)
8. [Event-System-Vereinheitlichung](#8-event-system-vereinheitlichung)
9. [Lifecycle-Management](#9-lifecycle-management)
10. [Home-Assistant-Integration](#10-home-assistant-integration)
11. [Migrationsstrategie](#11-migrationsstrategie)
12. [Risiken und offene Punkte](#12-risiken-und-offene-punkte)
13. [Zusammenfassung](#13-zusammenfassung)

---

## 1. Ausgangslage

### Ist-Zustand

Die Home-Assistant-Integration **Homematic(IP) Local** nutzt die Bibliothek
**aiohomematic**, um CCU3, OpenCCU und Homegear anzubinden. Die Bibliothek
kommuniziert per XML-RPC und JSON-RPC mit dem Backend und stellt Geräte,
Kanäle und Datenpunkte als typisierte Python-Objekte bereit.

### Neues Produkt: HCU (Home Control Unit)

Die HCU bietet eine **Connect API** (Version 1.0.1), die ein
Plugin-Erweiterungssystem bereitstellt. Plugins kommunizieren per **WebSocket
(WSS)** mit der HCU und tauschen JSON-Nachrichten aus. Die API ist
feature-basiert statt paramset-basiert.

### Ziel

Eine einzige Home-Assistant-Integration, die sowohl CCU/Homegear als auch die
HCU anbinden kann. Darunter arbeiten zwei spezialisierte Backend-Bibliotheken,
die durch eine **gemeinsame Fassade** vereinheitlicht werden.

---

## 2. Analyse der beiden Systeme

### 2.1 Vergleichsmatrix

| Aspekt | CCU/Homegear (aiohomematic) | HCU (Connect API) |
|--------|----------------------------|-------------------|
| **Transport** | XML-RPC + JSON-RPC über HTTP | WebSocket (WSS) auf Port 9001 |
| **Nachrichtenformat** | XML (RPC) + JSON (RPC) | JSON (WebSocket-Frames) |
| **Authentifizierung** | IP-basiert, Benutzername/Passwort | Bearer-Token (Auth-Token-Flow) |
| **Gerätemodell** | Paramset-basiert (MASTER, VALUES, LINK) | Feature-basiert (46 Feature-Typen) |
| **Geräteerkennung** | `listDevices()` via XML-RPC | `DISCOVER_REQUEST` → `DISCOVER_RESPONSE` |
| **Geräteaufnahme** | Install-Mode + automatische Erkennung | Discovery → Inclusion-Flow |
| **Events (Push)** | XML-RPC-Callback-Server (oder MQTT für CUxD) | WebSocket bidirektional (`STATUS_EVENT`) |
| **Konfiguration** | Paramset-Descriptions (statisch) | Config-Templates (dynamisches Schema) |
| **Gerätesteuerung** | `setValue()`, `putParamset()` | `CONTROL_REQUEST` mit Feature-Werten |
| **Systemsteuerung** | JSON-RPC (Programme, Sysvars) | `HMIP_SYSTEM_REQUEST` (REST-artige Endpunkte) |
| **Gerätemetadaten** | DeviceDescription (TypedDict) | Device-Objekt mit Channels und Features |
| **Verbindungsprüfung** | Ping/Pong über XML-RPC | WebSocket-Heartbeat (Ping/Pong-Frames) |
| **Deployment** | Externe Bibliothek | Plugin als Docker-Container oder Remote |

### 2.2 Gemeinsamkeiten

Trotz der Unterschiede teilen beide Systeme grundlegende Konzepte:

1. **Geräte** mit einer eindeutigen Adresse/ID
2. **Kanäle** als funktionale Untereinheiten eines Gerätes
3. **Datenpunkte/Features** mit Werten, die gelesen, geschrieben und
   abonniert werden können
4. **Events** bei Wertänderungen (Push-Benachrichtigungen)
5. **Lifecycle**: Verbindung herstellen → Geräte entdecken → Laufzeit →
   Trennung
6. **Zustandsmaschine**: Verbindungsstatus (Verbunden, Degradiert, Getrennt)

### 2.3 Fundamentale Unterschiede

Diese Unterschiede verhindern eine einfache Integration der HCU als weiteres
Backend in aiohomematic:

#### a) Gerätemodell

**CCU**: Geräte werden durch `DeviceDescription` + `ParamsetDescription`
beschrieben. Jeder Parameter (z. B. `STATE`, `LEVEL`, `SET_POINT_TEMPERATURE`)
hat Metadaten (Typ, Min/Max, Operationen). Datenpunkttypen werden zur Laufzeit
aus diesen Metadaten **inferiert**.

**HCU**: Geräte deklarieren explizit ihre **Features** (z. B.
`switchState`, `dimming`, `actualTemperature`). Jedes Feature hat einen
definierten Typ und Wertebereich. Es gibt keine Paramsets.

#### b) Kommunikationsrolle

**CCU**: aiohomematic ist ein **Client**, der die CCU abfragt und einen
Callback-Server betreibt.

**HCU**: Das Plugin ist ein **Server/Provider**, der auf Anfragen der HCU
reagiert (`DISCOVER_REQUEST`, `CONTROL_REQUEST`, `STATUS_REQUEST`) und
proaktiv Events sendet (`STATUS_EVENT`).

> **Hinweis**: Für die Home-Assistant-Integration kehrt sich die Rolle
> allerdings um — die Integration will die HCU als Datenquelle nutzen,
> nicht als Plugin-Host. Das bedeutet, die Integration müsste die
> Connect API *konsumieren*, nicht *implementieren*. Die HCU-Seite der
> Kommunikation (WebSocket-Client, der Events empfängt und Befehle
> sendet) ähnelt dann wieder dem Client-Muster von aiohomematic.

#### c) Gerätesteuerung

**CCU**: Universelle Methoden (`setValue`, `putParamset`) mit Adresse +
Parametername + Wert.

**HCU**: Typisierte REST-artige Endpunkte pro Gerätetyp
(`/hmip/device/control/setSwitchState`,
`/hmip/device/control/setShutterLevel`) über `HMIP_SYSTEM_REQUEST`.

#### d) Konfiguration

**CCU**: Statische Paramset-Descriptions (MASTER-Paramset) mit festen
Feldern.

**HCU**: Dynamische Config-Templates (JSON-Schema) mit Validierung und
Gruppen.

---

## 3. Kernproblem: Inkompatible Gerätemodelle

Das zentrale Problem ist die Inkompatibilität der Gerätemodelle:

```
CCU-Modell:                          HCU-Modell:
┌─────────────┐                      ┌─────────────────┐
│ Device      │                      │ Device          │
│ ADDRESS     │                      │ deviceId        │
│ MODEL       │                      │ deviceType      │
│ FIRMWARE    │                      │ label{en,de}    │
├─────────────┤                      ├─────────────────┤
│ Channel :0  │                      │ Channel         │
│  PARAMSETS: │                      │  channelId      │
│   MASTER    │                      │  type           │
│   VALUES    │                      │  features: [    │
│   LINK      │                      │    {featureType,│
│  Parameter: │                      │     value,      │
│   STATE     │◄───── kein 1:1 ─────►│     constraints}│
│   LEVEL     │      Mapping         │  ]              │
│   ERROR     │                      │                 │
└─────────────┘                      └─────────────────┘
```

**Warum kein 1:1-Mapping möglich ist**:

1. CCU-Parameter sind **flach** (ein Name = ein Wert), HCU-Features sind
   **strukturiert** (ein Feature kann mehrere Werte haben, z. B.
   `color` mit Hue + Saturation + Brightness).

2. CCU-Parametertypen (`BOOL`, `FLOAT`, `INTEGER`, `ENUM`, `ACTION`, `STRING`)
   decken nicht alle HCU-Feature-Typen ab (z. B. `climateOperationMode`,
   `presenceMode`).

3. CCU-Datenpunkttypen werden durch **Inferenz** bestimmt (aus
   ParameterData), HCU-Feature-Typen sind **explizit deklariert**.

4. Die CCU kennt **keinen Discovery/Inclusion-Flow**. Geräte erscheinen
   nach dem Pairing automatisch in `listDevices()`.

---

## 4. Architekturoptionen

### Option A: HCU als weiteres Backend in aiohomematic

```
Home Assistant Integration
         │
    aiohomematic
    ┌────┴────────────────────┐
    │ CentralUnit             │
    │  ├─ CcuBackend          │
    │  ├─ HomegearBackend     │
    │  ├─ JsonCcuBackend      │
    │  └─ HcuBackend (NEU)    │
    └─────────────────────────┘
```

**Vorteile**: Kein neues Paket, maximale Wiederverwendung.

**Nachteile**:

- Das gesamte Modell (Device, Channel, DataPoint) ist paramset-basiert. Ein
  HCU-Backend müsste Feature-Daten in synthetische Paramset-Descriptions
  umwandeln — ein fragiler Adapter mit Informationsverlust.
- Die `InterfaceClient`-Klasse setzt `BackendOperationsProtocol` voraus, das
  ~50 Methoden definiert (viele davon CCU-spezifisch: `execute_program`,
  `get_system_variable`, `get_all_rooms`, etc.).
- Die HCU-Connect-API hat eine **umgekehrte Kommunikationsrolle** (Plugin
  reagiert auf Anfragen), was grundlegend anders ist als der Client-Ansatz.
- Hohe Kopplung: Änderungen am HCU-Protokoll erfordern Änderungen in
  aiohomematic-Kerncode.

**Bewertung**: **Nicht empfohlen.** Zu viel Impedance Mismatch.

---

### Option B: Separate Bibliothek mit gemeinsamer Fassade

```
Home Assistant Integration
         │
    homematic-facade (NEU)
    ┌────┴────────────────────────────┐
    │ UnifiedCentral                  │
    │  ├─ UnifiedDevice               │
    │  ├─ UnifiedChannel              │
    │  └─ UnifiedDataPoint            │
    ├─────────────────┬───────────────┤
    │ aiohomematic    │ aiohcu (NEU)  │
    │ (CCU/Homegear)  │ (HCU)        │
    └─────────────────┴───────────────┘
```

**Vorteile**:

- Klare Trennung: Jede Bibliothek ist für ihr Protokoll zuständig.
- Die Fassade definiert ein einheitliches Modell, das beide bedienen.
- Home Assistant braucht nur die Fassade zu kennen.
- Unabhängige Entwicklung und Versionierung der Bibliotheken.

**Nachteile**:

- Drei Pakete statt einem.
- Die Fassade muss die Komplexität beider Systeme abstrahieren.
- Doppelte Wartung für gemeinsame Konzepte (Events, State-Machine, etc.).

**Bewertung**: **Möglich, aber hoher Aufwand.**

---

### Option C: Dünne Adapter-Schicht in der Integration

```
Home Assistant Integration
    ┌─────────────────────────────────┐
    │ homematicip_local               │
    │  ├─ CcuAdapter (aiohomematic)   │
    │  └─ HcuAdapter (aiohcu)         │
    │  ┌──────────────────────────┐   │
    │  │ Unified Entity Layer     │   │
    │  │ (HA-Entities mit Switch) │   │
    │  └──────────────────────────┘   │
    └─────────────────────────────────┘
         │                   │
    aiohomematic          aiohcu (NEU)
```

**Vorteile**:

- Kein neues Fassaden-Paket nötig.
- Die Integration selbst enthält die Adapter-Logik.
- Maximale Flexibilität bei der Entity-Erstellung.

**Nachteile**:

- Geschäftslogik wandert in die Integration (statt in Bibliotheken).
- Schwer testbar ohne Home Assistant.
- Duplizierung von Konzepten (State-Machine, Events, Health-Checks).

**Bewertung**: **Nicht empfohlen.** Zu viel Logik in der Integration.

---

### Option D (Empfohlen): Shared-Facade als Protocol-Schicht in aiohomematic

```
Home Assistant Integration (homematicip_local)
         │
         │  nutzt nur Facade-Protocols
         ▼
    ┌─────────────────────────────────────────┐
    │ aiohomematic (erweitert)                │
    │                                         │
    │  ┌───────────────────────────────────┐  │
    │  │ Facade-Protocols (NEU)            │  │
    │  │  UnifiedCentralProtocol           │  │
    │  │  UnifiedDeviceProtocol            │  │
    │  │  UnifiedDataPointProtocol         │  │
    │  │  UnifiedEventBusProtocol          │  │
    │  └───────────────┬───────────────────┘  │
    │                  │                      │
    │       ┌──────────┴──────────┐           │
    │       │                     │           │
    │  CentralUnit            HcuCentral      │
    │  (CCU/Homegear)         (HCU/NEU)       │
    │  implementiert          implementiert    │
    │  Facade-Protocols       Facade-Protocols │
    │       │                     │           │
    │  CcuBackend             HcuClient       │
    │  HomegearBackend        (WebSocket)      │
    │  JsonCcuBackend                         │
    └─────────────────────────────────────────┘
```

**Vorteile**:

- **Ein Paket**: Alles bleibt in aiohomematic (oder einem Mono-Repo).
- **Protocol-basiert**: Die Fassade ist eine Menge von Protocol-Interfaces,
  die beide Implementierungen erfüllen.
- **Bestehende Architektur wird genutzt**: aiohomematic hat bereits eine
  ausgeprägte Protocol-basierte DI-Architektur mit 30+ Protocols.
- **Schrittweise Migration**: Die bestehenden Protocols können graduell zu
  Facade-Protocols angehoben werden.
- **Testbarkeit**: Protocols können unabhängig gemockt werden.
- **Ein HA-Integration**: homematicip_local programmiert gegen die
  Facade-Protocols und behandelt CCU und HCU gleich.

**Nachteile**:

- aiohomematic wird größer (aber modular durch Packages).
- Die HCU-Implementierung muss das gleiche Modell bedienen, obwohl
  das darunterliegende Protokoll anders ist.

**Bewertung**: **Empfohlen.** Beste Balance aus Wiederverwendung,
Modularität und Wartbarkeit.

---

## 5. Empfohlene Architektur: Shared-Facade mit dualen Backends

### 5.1 Paketstruktur

```
aiohomematic/
├── facade/                          # NEU: Gemeinsame Fassade
│   ├── __init__.py
│   ├── protocols.py                 # Unified Protocols
│   ├── types.py                     # Gemeinsame Datentypen
│   ├── event_types.py               # Gemeinsame Event-Typen
│   └── factory.py                   # Factory für CCU oder HCU
│
├── central/                         # BESTAND: CCU/Homegear-Implementierung
│   ├── central_unit.py              # Implementiert UnifiedCentralProtocol
│   ├── coordinators/
│   │   └── ...
│   └── ...
│
├── hcu/                             # NEU: HCU-Implementierung
│   ├── __init__.py
│   ├── hcu_central.py               # Implementiert UnifiedCentralProtocol
│   ├── hcu_client.py                # WebSocket-Client
│   ├── hcu_auth.py                  # Token-basierte Authentifizierung
│   ├── hcu_config.py                # HCU-Konfiguration
│   ├── hcu_device.py                # HCU-Geräte → UnifiedDeviceProtocol
│   ├── hcu_event_bridge.py          # WebSocket-Events → EventBus
│   ├── feature_mapping.py           # Feature → DataPoint-Mapping
│   └── message_types.py             # WebSocket-Nachrichtentypen
│
├── client/                          # BESTAND (unverändert)
│   ├── backends/
│   └── ...
│
├── model/                           # BESTAND (teilweise erweitert)
│   ├── device.py                    # Device implementiert UnifiedDeviceProtocol
│   └── ...
│
└── interfaces/                      # BESTAND (erweitert um Facade-Protocols)
    ├── facade.py                    # NEU: Re-Export der Facade-Protocols
    └── ...
```

### 5.2 Schichtenarchitektur

```
┌──────────────────────────────────────────────────────┐
│                Home Assistant Integration             │
│              (homematicip_local)                      │
│                                                      │
│  Programmiert ausschließlich gegen Facade-Protocols   │
└──────────────────────┬───────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌─────────────────┐        ┌─────────────────┐
│  Facade-Layer   │        │  Facade-Layer   │
│  (Protocols)    │        │  (Protocols)    │
├─────────────────┤        ├─────────────────┤
│  CentralUnit    │        │  HcuCentral     │
│  (CCU/Homegear) │        │  (HCU)          │
├─────────────────┤        ├─────────────────┤
│  Device/Channel │        │  HcuDevice      │
│  /DataPoint     │        │  /HcuChannel    │
├─────────────────┤        ├─────────────────┤
│  InterfaceClient│        │  HcuClient      │
│  + Backends     │        │  (WebSocket)    │
├─────────────────┤        ├─────────────────┤
│  XML-RPC /      │        │  WSS + JSON     │
│  JSON-RPC       │        │  Port 9001      │
└─────────────────┘        └─────────────────┘
         │                           │
         ▼                           ▼
    CCU3/OpenCCU/                  HCU
    Homegear
```

---

## 6. Detailentwurf der Fassade

### 6.1 UnifiedCentralProtocol

Das Haupt-Protocol, das die Integration nutzt:

```python
@runtime_checkable
class UnifiedCentralProtocol(Protocol):
    """Einheitliches Protocol für CCU und HCU."""

    # --- Identifikation ---
    @property
    def name(self) -> str:
        """Eindeutiger Name der Zentrale."""
        ...

    @property
    def host(self) -> str:
        """Hostname oder IP-Adresse."""
        ...

    @property
    def model(self) -> str:
        """Modell (z.B. 'CCU3', 'HCU')."""
        ...

    @property
    def backend_type(self) -> BackendType:
        """Typ des Backends (CCU, HOMEGEAR, HCU)."""
        ...

    # --- Zustand ---
    @property
    def state(self) -> CentralState:
        """Aktueller Betriebszustand."""
        ...

    @property
    def is_connected(self) -> bool:
        """Ob die Verbindung steht."""
        ...

    # --- Lifecycle ---
    async def start(self) -> None:
        """Zentrale starten (Verbindung, Geräteerkennung, Events)."""
        ...

    async def stop(self) -> None:
        """Zentrale herunterfahren."""
        ...

    # --- Geräte ---
    @property
    def devices(self) -> tuple[UnifiedDeviceProtocol, ...]:
        """Alle bekannten Geräte."""
        ...

    def get_device(self, *, address: str) -> UnifiedDeviceProtocol | None:
        """Gerät anhand der Adresse/ID suchen."""
        ...

    # --- Events ---
    @property
    def event_bus(self) -> UnifiedEventBusProtocol:
        """Zentraler Event-Bus."""
        ...

    # --- Fähigkeiten ---
    @property
    def capabilities(self) -> CentralCapabilities:
        """Welche Operationen diese Zentrale unterstützt."""
        ...
```

### 6.2 UnifiedDeviceProtocol

```python
@runtime_checkable
class UnifiedDeviceProtocol(Protocol):
    """Einheitliches Geräte-Protocol."""

    # --- Identifikation ---
    @property
    def address(self) -> str:
        """Eindeutige Geräteadresse (CCU) oder deviceId (HCU)."""
        ...

    @property
    def name(self) -> str:
        """Anzeigename."""
        ...

    @property
    def model(self) -> str:
        """Gerätemodell."""
        ...

    @property
    def device_type(self) -> str:
        """Gerätetyp (z.B. 'SWITCH', 'LIGHT', 'THERMOSTAT')."""
        ...

    @property
    def firmware(self) -> str:
        """Firmware-Version."""
        ...

    # --- Verfügbarkeit ---
    @property
    def is_available(self) -> bool:
        """Ob das Gerät erreichbar ist."""
        ...

    # --- Struktur ---
    @property
    def channels(self) -> Mapping[str, UnifiedChannelProtocol]:
        """Kanäle des Gerätes."""
        ...

    # --- Datenpunkte (Schnellzugriff) ---
    @property
    def data_points(self) -> tuple[UnifiedDataPointProtocol, ...]:
        """Alle Datenpunkte über alle Kanäle."""
        ...

    # --- Events ---
    def subscribe_to_device_updated(
        self, *, handler: Callable[[], None]
    ) -> Callable[[], None]:
        """Änderungen am Gerät abonnieren. Gibt Unsubscribe-Callable zurück."""
        ...
```

### 6.3 UnifiedDataPointProtocol

```python
@runtime_checkable
class UnifiedDataPointProtocol(Protocol):
    """Einheitliches Datenpunkt-Protocol (Parameter oder Feature)."""

    # --- Identifikation ---
    @property
    def unique_id(self) -> str:
        """Global eindeutige ID für Home Assistant Entity."""
        ...

    @property
    def parameter(self) -> str:
        """Parametername (CCU) oder Feature-ID (HCU)."""
        ...

    @property
    def category(self) -> DataPointCategory:
        """Kategorie (SWITCH, SENSOR, CLIMATE, COVER, etc.)."""
        ...

    # --- Wert ---
    @property
    def value(self) -> Any:
        """Aktueller gecachter Wert."""
        ...

    @property
    def is_readable(self) -> bool:
        """Ob der Wert gelesen werden kann."""
        ...

    @property
    def is_writable(self) -> bool:
        """Ob der Wert geschrieben werden kann."""
        ...

    # --- Metadaten ---
    @property
    def unit(self) -> str | None:
        """Einheit (°C, %, W, etc.)."""
        ...

    @property
    def min_value(self) -> float | None:
        """Minimalwert."""
        ...

    @property
    def max_value(self) -> float | None:
        """Maximalwert."""
        ...

    @property
    def value_list(self) -> tuple[str, ...] | None:
        """Mögliche Werte bei Enum-Typen."""
        ...

    # --- Operationen ---
    async def send_value(self, *, value: Any) -> None:
        """Wert an das Backend senden."""
        ...

    async def get_value(self) -> Any:
        """Aktuellen Wert vom Backend lesen."""
        ...

    # --- Events ---
    def subscribe_to_data_point_updated(
        self,
        *,
        handler: Callable[..., None],
        custom_id: str,
    ) -> Callable[[], None]:
        """Wertänderungen abonnieren."""
        ...
```

### 6.4 CentralCapabilities

Ein Datenmodell, das beschreibt, welche Operationen eine Zentrale unterstützt.
Die Integration prüft Capabilities, bevor sie Features anbietet:

```python
@dataclass(frozen=True, slots=True)
class CentralCapabilities:
    """Fähigkeiten einer Zentrale."""

    # Geräteverwaltung
    device_pairing: bool = False        # Install-Mode / Discovery
    device_firmware_update: bool = False
    device_rename: bool = False
    device_linking: bool = False

    # Systemfunktionen
    programs: bool = False              # CCU-Programme
    system_variables: bool = False      # CCU-Systemvariablen
    rooms: bool = False                 # Raum-Zuordnungen
    functions: bool = False             # Funktions-Gruppen
    backup: bool = False                # System-Backup

    # Konfiguration
    paramset_configuration: bool = False  # MASTER-Paramset lesen/schreiben
    plugin_configuration: bool = False    # Plugin-Config-Templates (HCU)

    # Benachrichtigungen
    user_messages: bool = False           # In-App-Nachrichten (HCU)
    service_messages: bool = False        # Service-Meldungen (CCU)
```

**CCU-Zentrale** hat z. B.:

```python
CentralCapabilities(
    device_pairing=True,
    device_firmware_update=True,
    device_rename=True,
    device_linking=True,
    programs=True,
    system_variables=True,
    rooms=True,
    functions=True,
    backup=True,
    paramset_configuration=True,
    service_messages=True,
)
```

**HCU-Zentrale** hat z. B.:

```python
CentralCapabilities(
    device_pairing=True,       # via Discovery/Inclusion
    device_rename=False,       # nicht in Connect API vorgesehen
    plugin_configuration=True, # Config-Templates
    user_messages=True,        # In-App-Nachrichten
)
```

---

## 7. Mapping der Gerätemodelle

> **Hinweis (nach Analyse der Referenzimplementierung)**: Die HCU liefert
> für native HmIP-Geräte **nicht** das Feature-Modell der Connect API,
> sondern das **HmIP-Cloud-API-Format** mit `functionalChannels`. Das
> untenstehende Feature-Mapping gilt daher primär für Plugin-Geräte
> (Drittanbieter). Für native HmIP-Geräte ist das Kanaltyp-Mapping
> (Abschnitt 7.4) maßgeblich.

### 7.1 HCU-Feature → Unified DataPoint (Plugin-Geräte)

Die zentrale Herausforderung ist die Abbildung von HCU-Features auf
einheitliche Datenpunkte. Hier ein Mapping der wichtigsten Feature-Typen:

| HCU Feature-Typ | DataPointCategory | Werttyp | Hinweise |
|-----------------|-------------------|---------|----------|
| `switchState` | `SWITCH` | `bool` | An/Aus |
| `dimming` | `NUMBER` | `float` (0.0-1.0) | Helligkeit |
| `color` | (Custom) | `dict` (HSV) | Zusammengesetztes Feature |
| `colorTemperature` | `NUMBER` | `int` (Kelvin) | Farbtemperatur |
| `shutterLevel` | `COVER` | `float` (0.0-1.0) | Rollladenposition |
| `slatsLevel` | `COVER` | `float` (0.0-1.0) | Lamellenposition |
| `actualTemperature` | `SENSOR` | `float` (°C) | Ist-Temperatur |
| `setPointTemperature` | `CLIMATE` | `float` (°C) | Soll-Temperatur |
| `humidity` | `SENSOR` | `float` (%) | Luftfeuchtigkeit |
| `contactSensorState` | `BINARY_SENSOR` | `bool` | Tür/Fenster |
| `presenceDetected` | `BINARY_SENSOR` | `bool` | Anwesenheit |
| `batteryState` | `SENSOR` | `float` (%) | Batteriestand |
| `maintenance` | `BINARY_SENSOR` | `bool` | Wartung nötig |
| `smokeAlarm` | `BINARY_SENSOR` | `bool` | Rauchalarm |
| `currentPower` | `SENSOR` | `float` (W) | Aktuelle Leistung |
| `energyCounter` | `SENSOR` | `float` (kWh) | Energiezähler |
| `climateOperationMode` | `SELECT` | `str` (Enum) | Betriebsmodus |
| `windSpeed` | `SENSOR` | `float` (km/h) | Windgeschwindigkeit |
| `illumination` | `SENSOR` | `float` (lux) | Beleuchtungsstärke |
| `co2` | `SENSOR` | `float` (ppm) | CO2-Konzentration |

### 7.2 Zusammengesetzte Features

Einige HCU-Features sind strukturiert und müssen in mehrere Datenpunkte
aufgelöst werden:

```
HCU Feature "color":
  ├─ hue: float (0-360)         → DataPoint "color_hue" (NUMBER)
  ├─ saturation: float (0-1)    → DataPoint "color_saturation" (NUMBER)
  └─ brightness: float (0-1)    → DataPoint "color_brightness" (NUMBER)

HCU Feature "climateOperationMode":
  └─ mode: enum                 → DataPoint "climate_mode" (SELECT)
       Werte: ["AUTO", "MANUAL", "ECO", "BOOST"]
```

### 7.3 Mapping-Registry

```python
@dataclass(frozen=True, slots=True)
class FeatureMapping:
    """Abbildung eines HCU-Features auf einen oder mehrere Datenpunkte."""

    feature_type: str
    category: DataPointCategory
    value_type: type
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    sub_features: tuple[FeatureMapping, ...] = ()


# Registry: feature_type → FeatureMapping
FEATURE_MAPPINGS: Final[dict[str, FeatureMapping]] = {
    "switchState": FeatureMapping(
        feature_type="switchState",
        category=DataPointCategory.SWITCH,
        value_type=bool,
    ),
    "actualTemperature": FeatureMapping(
        feature_type="actualTemperature",
        category=DataPointCategory.SENSOR,
        value_type=float,
        unit="°C",
        min_value=-40.0,
        max_value=80.0,
    ),
    "dimming": FeatureMapping(
        feature_type="dimming",
        category=DataPointCategory.NUMBER,
        value_type=float,
        unit="%",
        min_value=0.0,
        max_value=1.0,
    ),
    # ... weitere Mappings
}
```

### 7.4 functionalChannelType → Entity (native HmIP-Geräte)

Für native HmIP-Geräte auf der HCU ist dieses Mapping maßgeblich.
Es basiert auf der Analyse der Referenzimplementierung:

| functionalChannelType | HA Platform | Kanal-Properties | Steuerungs-API |
|----------------------|-------------|-----------------|----------------|
| `SWITCH_CHANNEL` | `switch` | `on` | `setSwitchState` |
| `SWITCH_MEASURING_CHANNEL` | `switch` + `sensor` | `on`, `energyCounter`, `currentPowerConsumption` | `setSwitchState` |
| `WATERING_CHANNEL` | `switch` | `wateringActive` | `setWateringState` |
| `DIMMER_CHANNEL` | `light` | `dimLevel`, `on` | `setDimLevel` |
| `DIMMER_WITH_COLOR_TEMP` | `light` | `dimLevel`, `colorTemperature`, `on` | `setColorTemperatureDimLevel` |
| `DIMMER_WITH_HS_COLOR` | `light` | `dimLevel`, `hue`, `saturation`, `on` | `setHueSaturationDimLevel` |
| `NOTIFICATION_LIGHT_CHANNEL` | `light` | `dimLevel`, `simpleRGBColorState` | `setSimpleRGBColorState` |
| `SHUTTER_CHANNEL` | `cover` | `shutterLevel` (0.0=offen, 1.0=zu) | `setShutterLevel` |
| `BLIND_CHANNEL` | `cover` | `primaryShadingLevel`, `slatsLevel` | `setPrimaryShadingLevel`, `setSlatsLevel` |
| `DOOR_CHANNEL` | `cover` | `doorState`, `doorMotion` | `sendDoorCommand` |
| `DOOR_LOCK_CHANNEL` | `lock` | `lockState`, `motorState` | `setLockState` |
| `DEVICE_BASE` | `binary_sensor` | `unreach`, `lowBat`, `configPending` | — (read-only) |
| `SMOKE_DETECTOR_CHANNEL` | `binary_sensor` | `alarmState` | — (read-only) |
| `CONTACT_INTERFACE_CHANNEL` | `binary_sensor` | `windowState` | — (read-only) |
| `MOTION_DETECTION_CHANNEL` | `binary_sensor` | `presenceDetected`, `illumination` | — (read-only) |

**Gruppen-basierte Entities** (kein Gerätekanal, sondern HCU-Gruppen):

| Gruppen-Typ | HA Platform | Properties | Steuerungs-API |
|-------------|-------------|------------|----------------|
| `HEATING` | `climate` | `actualTemperature`, `setPointTemperature`, `controlMode`, `boostMode`, `humidity`, `valvePosition` | `setSetPointTemperature`, `setControlMode`, `setBoost` |
| `SWITCHING` | `switch` | `on` | `setState` |
| `ALARM_SWITCHING` | `siren` | `on` | `setState` |
| `SECURITY_AND_ALARM` (Home) | `alarm_control_panel` | `securityZones`, `intrusionAlarmActive` | `setExtendedZonesActivation` |

---

## 8. Event-System-Vereinheitlichung

### 8.1 Event-Quellen

```
CCU-Events:                          HCU-Events:
┌────────────────────┐               ┌────────────────────┐
│ XML-RPC Callback   │               │ WebSocket Frame    │
│ event(interface_id,│               │ TYPE: STATUS_EVENT │
│   channel_address, │               │ BODY: {devices:[  │
│   parameter,       │               │   {deviceId,      │
│   value)           │               │    channels:[     │
└────────┬───────────┘               │     {features:[   │
         │                           │      {value}]}]}  │
         ▼                           └────────┬───────────┘
┌────────────────────┐                        │
│ EventCoordinator   │                        ▼
│ .event()           │               ┌────────────────────┐
└────────┬───────────┘               │ HcuEventBridge     │
         │                           │ .on_status_event() │
         ▼                           └────────┬───────────┘
┌────────────────────┐                        │
│ EventBus           │◄───────────────────────┘
│ .publish()         │
└────────────────────┘
         │
         ▼
┌────────────────────┐
│ Home Assistant     │
│ Entity Updates     │
└────────────────────┘
```

### 8.2 Gemeinsame Event-Typen

Beide Systeme produzieren letztlich die gleichen Event-Typen:

```python
# Gemeinsam nutzbar (bereits in aiohomematic vorhanden):

@dataclass(frozen=True, slots=True)
class DataPointValueChangedEvent:
    """Ein Datenpunktwert hat sich geändert."""
    unique_id: str
    parameter: str
    old_value: Any
    new_value: Any

@dataclass(frozen=True, slots=True)
class DeviceAvailabilityChangedEvent:
    """Geräteverfügbarkeit hat sich geändert."""
    device_address: str
    is_available: bool

@dataclass(frozen=True, slots=True)
class SystemStateChangedEvent:
    """Zentralen-Zustand hat sich geändert."""
    old_state: CentralState
    new_state: CentralState
```

### 8.3 HCU-Event-Bridge

Die `HcuEventBridge` übersetzt WebSocket-Nachrichten in EventBus-Events:

```python
class HcuEventBridge:
    """Übersetzt HCU-WebSocket-Events in EventBus-Events."""

    def __init__(self, *, event_bus: EventBus, device_registry: ...) -> None:
        self._event_bus = event_bus
        self._device_registry = device_registry

    def on_status_event(self, message: dict[str, Any]) -> None:
        """Verarbeitet STATUS_EVENT von der HCU."""
        for device_data in message.get("devices", []):
            device_id = device_data["deviceId"]
            for channel_data in device_data.get("channels", []):
                for feature_data in channel_data.get("features", []):
                    # Feature-Wert auf Datenpunkt abbilden
                    dp = self._resolve_data_point(
                        device_id=device_id,
                        channel_id=channel_data["channelId"],
                        feature_type=feature_data["featureType"],
                    )
                    if dp is not None:
                        old_value = dp.value
                        dp.update_value(feature_data["value"])
                        self._event_bus.publish(
                            DataPointValueChangedEvent(
                                unique_id=dp.unique_id,
                                parameter=dp.parameter,
                                old_value=old_value,
                                new_value=feature_data["value"],
                            )
                        )

    def on_system_event(self, message: dict[str, Any]) -> None:
        """Verarbeitet HMIP_SYSTEM_EVENT von der HCU."""
        event_type = message.get("type")
        if event_type == "DEVICE_ADDED":
            # Neues Gerät entdeckt → Geräteerstellung auslösen
            ...
        elif event_type == "DEVICE_REMOVED":
            # Gerät entfernt → Aufräumen
            ...
```

---

## 9. Lifecycle-Management

### 9.1 Startup-Vergleich

```
CCU-Startup:                           HCU-Startup:
1. CentralConfig erstellen             1. HcuConfig erstellen
2. CentralUnit erstellen               2. HcuCentral erstellen
3. central.start()                     3. hcu.start()
   ├─ IP erkennen                         ├─ Auth-Token anfordern
   ├─ XML-RPC-Server starten              ├─ WebSocket verbinden
   ├─ Clients starten                     ├─ Auth-Token bestätigen
   ├─ listDevices()                       ├─ STATUS_REQUEST senden
   ├─ Paramset-Descriptions laden         ├─ Geräte aus Response erstellen
   ├─ Devices/Channels/DPs erstellen      ├─ Feature-Mappings anwenden
   └─ Scheduler starten                   └─ Event-Listener starten
```

### 9.2 Vereinheitlichter Lifecycle

```python
# Die Integration erstellt die passende Zentrale:

async def async_setup_entry(hass, entry) -> bool:
    """Integration-Setup."""
    backend_type = entry.data["backend_type"]  # "ccu" oder "hcu"

    if backend_type == "ccu":
        config = CentralConfig(
            host=entry.data["host"],
            username=entry.data["username"],
            password=entry.data["password"],
            ...
        )
        central: UnifiedCentralProtocol = config.create_central()
    elif backend_type == "hcu":
        config = HcuConfig(
            host=entry.data["host"],
            plugin_id=entry.data["plugin_id"],
            ...
        )
        central: UnifiedCentralProtocol = config.create_central()

    # Ab hier: Einheitlicher Code für beide Backends
    await central.start()

    # Geräte registrieren
    for device in central.devices:
        for dp in device.data_points:
            if dp.category == DataPointCategory.SWITCH:
                # HA Switch-Entity erstellen
                ...
            elif dp.category == DataPointCategory.SENSOR:
                # HA Sensor-Entity erstellen
                ...

    # Events abonnieren
    central.event_bus.subscribe(
        event_type=DataPointValueChangedEvent,
        handler=on_state_changed,
    )
```

### 9.3 HCU-spezifischer Auth-Flow

```
┌──────────┐     POST /requestConnectApiAuthToken     ┌──────┐
│ aiohm    │ ─────────────────────────────────────────→│ HCU  │
│ (Plugin) │ ←─────────────────────────────────────────│      │
│          │     { authToken: "abc123" }                │      │
│          │                                           │      │
│          │  [Nutzer bestätigt in App]                │      │
│          │                                           │      │
│          │     POST /confirmConnectApiAuthToken       │      │
│          │ ─────────────────────────────────────────→│      │
│          │ ←─────────────────────────────────────────│      │
│          │     { confirmed: true }                    │      │
│          │                                           │      │
│          │     WSS :9001  Authorization: Bearer abc   │      │
│          │ ═════════════════════════════════════════→│      │
│          │ ←════════════════════════════════════════=│      │
│          │     WebSocket-Verbindung steht             │      │
└──────────┘                                           └──────┘
```

---

## 10. Home-Assistant-Integration

### 10.1 Config-Flow-Erweiterung

Der Config-Flow von homematicip_local muss um die HCU erweitert werden:

```
Schritt 1: Backend-Typ wählen
  ┌─────────────────────────────────┐
  │ Welches System möchten Sie      │
  │ verbinden?                      │
  │                                 │
  │ ○ CCU3 / OpenCCU / RaspMatic   │
  │ ○ Homegear                     │
  │ ○ HCU (Home Control Unit)      │
  └─────────────────────────────────┘

Schritt 2a (CCU): Host, Benutzername, Passwort, Interfaces
Schritt 2b (HCU): Host, Plugin-ID, Auth-Token-Flow
```

### 10.2 Entity-Erstellung

Die Integration erstellt Entities basierend auf `DataPointCategory` — das
funktioniert für beide Backends identisch:

```python
# Platform-Mapping (identisch für CCU und HCU)
CATEGORY_TO_PLATFORM: dict[DataPointCategory, str] = {
    DataPointCategory.SWITCH: "switch",
    DataPointCategory.SENSOR: "sensor",
    DataPointCategory.BINARY_SENSOR: "binary_sensor",
    DataPointCategory.CLIMATE: "climate",
    DataPointCategory.COVER: "cover",
    DataPointCategory.LIGHT: "light",
    DataPointCategory.LOCK: "lock",
    DataPointCategory.NUMBER: "number",
    DataPointCategory.SELECT: "select",
    DataPointCategory.BUTTON: "button",
    DataPointCategory.TEXT: "text",
}
```

### 10.3 Backend-spezifische Features

Einige Features sind nur für bestimmte Backends verfügbar:

```python
# In der Integration:
if central.capabilities.programs:
    # CCU-Programme als Buttons/Switches registrieren
    await setup_program_entities(central)

if central.capabilities.system_variables:
    # CCU-Systemvariablen als Entities registrieren
    await setup_sysvar_entities(central)

if central.capabilities.user_messages:
    # HCU-Nachrichten-Service registrieren
    await setup_user_message_service(central)

if central.capabilities.plugin_configuration:
    # HCU-Plugin-Konfiguration als Options-Flow anbieten
    ...
```

---

## 11. Migrationsstrategie

### Phase 1: Facade-Protocols definieren (ohne HCU)

1. `UnifiedCentralProtocol`, `UnifiedDeviceProtocol`,
   `UnifiedDataPointProtocol` in `aiohomematic/facade/` definieren.
2. `CentralUnit` implementiert `UnifiedCentralProtocol` (zusätzlich zu
   allen bestehenden Protocols).
3. `Device` implementiert `UnifiedDeviceProtocol`.
4. Bestehende DataPoints implementieren `UnifiedDataPointProtocol`.
5. **Kein Breaking Change** — alles additiv.

### Phase 2: homematicip_local auf Facade-Protocols umstellen

1. Integration programmiert gegen `UnifiedCentralProtocol` statt
   direkt gegen `CentralUnit`.
2. Backend-spezifische Features über `capabilities` gesteuert.
3. **Rückwärtskompatibel** — CCU funktioniert wie bisher.

### Phase 3: HCU-Backend implementieren

1. `HcuCentral` in `aiohomematic/hcu/` erstellen.
2. WebSocket-Client implementieren.
3. Feature-Mapping-Registry aufbauen.
4. Event-Bridge implementieren.
5. `HcuCentral` implementiert `UnifiedCentralProtocol`.

### Phase 4: Integration erweitert Config-Flow

1. Backend-Typ-Auswahl im Config-Flow.
2. HCU-spezifischer Auth-Flow.
3. Tests mit realer HCU-Hardware.

### Zeitschätzung

| Phase | Aufwand | Abhängigkeiten |
|-------|---------|----------------|
| Phase 1 | Moderat | Keine |
| Phase 2 | Moderat | Phase 1 |
| Phase 3 | Hoch | Phase 1, HCU-Hardware zum Testen |
| Phase 4 | Moderat | Phase 2 + 3 |

---

## 12. Erkenntnisse aus der Referenzimplementierung

### 12.1 Analyse: hacs-homematicip-hcu

Die existierende HACS-Integration
[hacs-homematicip-hcu](https://github.com/Ediminator/hacs-homematicip-hcu)
wurde analysiert. Sie liefert kritische Antworten auf die offenen Fragen
und korrigiert einige Annahmen aus der API-Dokumentation.

### 12.2 Beantwortete Fragen

#### Frage 1: Wie läuft die Gerätesteuerung konkret ab?

**Antwort**: Über `HMIP_SYSTEM_REQUEST` mit REST-artigen Pfaden.

Die Integration sendet **alle Befehle** als `HMIP_SYSTEM_REQUEST`-Nachrichten
über den WebSocket. Der `body` enthält einen `path` und optional einen
`body`-Payload:

```python
# Beispiel: Switch einschalten
message = {
    "type": "HMIP_SYSTEM_REQUEST",
    "pluginId": "de.homeassistant.hcu.integration",
    "id": "<uuid>",
    "body": {
        "path": "/hmip/device/control/setSwitchState",
        "body": {
            "deviceId": "3014F711A000...",
            "channelIndex": 1,
            "on": True
        }
    }
}
```

**~30 Steuerungsendpunkte** stehen zur Verfügung, u. a.:
- `/hmip/device/control/setSwitchState` (+WithTime)
- `/hmip/device/control/setDimLevel` (+WithTime)
- `/hmip/device/control/setShutterLevel`
- `/hmip/device/control/setSlatsLevel`
- `/hmip/device/control/setLockState`
- `/hmip/device/control/setColorTemperatureDimLevel`
- `/hmip/device/control/setHueSaturationDimLevel`
- `/hmip/device/control/stop` (Cover)
- `/hmip/group/heating/setSetPointTemperature`
- `/hmip/group/heating/setControlMode`
- `/hmip/group/heating/setBoost`
- `/hmip/group/switching/setState`
- `/hmip/home/security/setExtendedZonesActivation`

**Erkenntnis**: Die Steuerung funktioniert vollständig über
`HMIP_SYSTEM_REQUEST`. Das Plugin muss **keine** `CONTROL_REQUEST`-Nachrichten
verarbeiten — diese sind nur für Plugin-eigene (Drittanbieter-) Geräte
relevant, nicht für native HmIP-Geräte.

#### Frage 2: Ist eine reine Client-Nutzung möglich?

**Antwort**: Ja, mit minimalem Plugin-Boilerplate.

Die Integration registriert sich als Plugin und beantwortet die
Plugin-Lifecycle-Anfragen mit Minimal-Antworten:

```python
# Auf PLUGIN_STATE_REQUEST:
→ {"pluginReadinessStatus": "READY"}

# Auf DISCOVER_REQUEST:
→ {"success": "true", "devices": []}  # Keine eigenen Geräte

# Auf CONFIG_TEMPLATE_REQUEST:
→ {"properties": {}}  # Keine Konfiguration

# Auf CONFIG_UPDATE_REQUEST:
→ {"status": "APPLIED"}
```

Das Plugin stellt **keine eigenen Geräte bereit** — es nutzt die
Connect API ausschließlich als **Event-Consumer und Befehls-Sender**
für native HmIP-Geräte. Die Plugin-Registrierung ist nur der
Authentifizierungs-Mechanismus, nicht die primäre Funktion.

#### Frage 3: Wie funktioniert die Geräteidentifikation?

**Antwort**: Geräte werden per SGTIN identifiziert (stabile IDs).

Die HCU liefert Geräte mit einer `id`-Eigenschaft, die dem SGTIN
(Serialized Global Trade Item Number) entspricht — z. B.
`3014F711A0000E98B9ACEF70`. Diese IDs sind:

- **Stabil über Neustarts hinweg** (hardware-gebunden)
- **Eindeutig** (globale Seriennummer)
- **Nicht mit CCU-Adressen kompatibel** (kein `VCU`/`MEQ`-Prefix)

#### Frage 4: Paramset-Äquivalente auf der HCU?

**Antwort**: Nein — die HCU nutzt `functionalChannels` statt Paramsets.

> **Kritische Erkenntnis**: Die HCU-Systemstate-API (`/hmip/home/getSystemState`)
> liefert **nicht** das Feature-Modell der Connect API, sondern das
> **HmIP-Cloud-API-Format** mit `functionalChannels`:

```json
{
  "devices": {
    "3014F711A000...": {
      "id": "3014F711A000...",
      "label": "Wohnzimmer Schalter",
      "type": "FULL_FLUSH_SWITCH_MEASURING",
      "modelType": "HmIP-FSM",
      "functionalChannels": {
        "0": {
          "functionalChannelType": "DEVICE_BASE",
          "unreach": false,
          "lowBat": false,
          "configPending": false
        },
        "1": {
          "functionalChannelType": "SWITCH_MEASURING_CHANNEL",
          "on": true,
          "energyCounter": 1234.5,
          "currentPowerConsumption": 42.0
        }
      }
    }
  },
  "groups": {
    "group-uuid": {
      "type": "HEATING",
      "actualTemperature": 21.5,
      "setPointTemperature": 22.0,
      "controlMode": "AUTOMATIC"
    }
  }
}
```

**Konsequenz**: Das Gerätemodell der HCU ist kanaltyp-basiert
(`functionalChannelType`), nicht feature-basiert und nicht paramset-basiert.
Jeder Kanaltyp hat seine eigenen typisierten Properties.

**Kein Äquivalent zu MASTER-Paramsets** — es gibt keine generische
Gerätekonfigurationsschnittstelle. Konfiguration läuft über die
HmIP-App oder über `CONFIG_TEMPLATE`/`CONFIG_UPDATE` für Plugin-eigene
Settings.

#### Frage 5: Welche Gerätetypen sind relevant?

**Antwort**: Die Referenzimplementierung unterstützt folgende Kanaltypen:

| HA Platform | HCU functionalChannelType |
|-------------|--------------------------|
| `switch` | SWITCH_CHANNEL, WATERING_CHANNEL |
| `light` | DIMMER_CHANNEL, NOTIFICATION_LIGHT, RGBW |
| `cover` | SHUTTER_CHANNEL, BLIND_CHANNEL, GARAGE_DOOR |
| `climate` | HEATING_GROUP (über Gruppen, nicht Gerätekanäle!) |
| `sensor` | Temperature, Humidity, Energy, Valve, Window-State |
| `binary_sensor` | Window, Door, Motion, Smoke, Battery, Connectivity |
| `lock` | DOOR_LOCK_CHANNEL |
| `siren` | via ALARM_SWITCHING_GROUP |
| `alarm_control_panel` | SECURITY_AND_ALARM (functionalHome) |
| `button` | Energy-Reset, Door-Opener, Identify |
| `event` | Button-Press, Doorbell |
| `update` | Firmware-Version (read-only) |

**Wichtige Erkenntnis**: Klima wird über **Gruppen** gesteuert, nicht
über einzelne Gerätekanäle. Dies ist ein fundamentaler Unterschied zur
CCU, bei der Thermostate direkt über ihre Kanäle gesteuert werden.

#### Frage 6: Koexistenz mit CCU?

**Antwort**: Noch nicht abschließend geklärt. Die HCU und CCU nutzen
unterschiedliche Adressformate (SGTIN vs. VCU) und verschiedene
Funkprotokolle für das Pairing. Eine Koexistenz im selben Netzwerk
ist technisch möglich, aber Geräte können nicht gleichzeitig an beide
Zentralen gebunden sein.

### 12.3 Revidierte Risikoeinschätzung

| Risiko | Ursprünglich | Revidiert | Begründung |
|--------|-------------|-----------|------------|
| Plugin-Rollenumkehr | Hoch | **Niedrig** | Gelöst: Minimales Plugin-Boilerplate, aktive Steuerung über `HMIP_SYSTEM_REQUEST` |
| Feature-Mapping | Mittel | **Mittel (verschoben)** | Das Modell ist kanaltyp-basiert, nicht feature-basiert. Mapping von `functionalChannelType` → Entities statt Features → DataPoints |
| WebSocket-Stabilität | Mittel | **Niedrig** | Referenzimplementierung zeigt: Exponential-Backoff (5s→60s) mit Jitter funktioniert zuverlässig |
| Selbstsignierte Zertifikate | Niedrig | **Niedrig** | Bestätigt: aiohttp mit `ssl=False` / custom SSL-Context |

### 12.4 Neue Erkenntnisse und Implikationen

#### a) Das Datenmodell ist NICHT feature-basiert

Die Connect-API-Dokumentation beschreibt ein Feature-Modell für
**Plugin-Geräte** (Drittanbieter). Für native HmIP-Geräte liefert
die HCU jedoch das **HmIP-Cloud-API-Format** mit `functionalChannels`.

**Implikation für die Architektur**: Das Mapping ist nicht
`Feature → DataPoint`, sondern `functionalChannelType + Properties →
Entity`. Das ist konzeptionell näher an CCU-Paramsets als ursprünglich
angenommen.

#### b) Gruppen sind ein eigenes Konzept

Die HCU arbeitet stark mit **Gruppen** (Heating, Switching, Alarm).
Gruppen aggregieren mehrere Geräte und bieten gruppierte Steuerung.
Die CCU kennt dieses Konzept nicht in dieser Form.

**Implikation**: Das Facade-Protocol muss ein Gruppen-Konzept
unterstützen oder Gruppen als virtuelle Geräte abbilden.

#### c) Events kommen als Transaktionen

HCU-Events enthalten `eventTransaction`-Objekte mit mehreren
Einzelereignissen. Ein einziger WebSocket-Frame kann Änderungen an
mehreren Geräten, Gruppen und dem Home-Objekt enthalten.

**Implikation**: Die Event-Bridge muss Transaktionen auflösen und
einzelne DataPoint-Events generieren.

#### d) Optimistic Updates sind Standard

Die Referenzimplementierung nutzt **optimistische Zustandsaktualisierungen**:
Entity setzt den erwarteten Wert sofort und revertiert bei Fehler.

**Implikation**: Das passt zum aiohomematic-Pattern bei `send_value()`,
wo der Cache vor der Bestätigung aktualisiert werden kann.

#### e) Request-Response-Korrelation per UUID

Jede Anfrage erhält eine UUID. Die Antwort wird über ein
`asyncio.Future` korreliert mit bis zu 3 Wiederholungsversuchen
(1s, 2s, 4s Backoff).

**Implikation**: Ähnlich zum Circuit-Breaker-Pattern in aiohomematic,
aber auf Nachrichtenebene statt auf Transportebene.

### 12.5 Geklärte Design-Entscheidungen

Die folgenden Punkte wurden geklärt und fließen in die Architektur ein:

1. **Gruppen-Modellierung** → **Virtuelle Geräte**

   HCU-Gruppen (Heating, Switching, Alarm) werden als **virtuelle Geräte**
   mit eigenen Kanälen und DataPoints dargestellt. Das passt nahtlos in die
   bestehende Device-zentrierte Architektur von aiohomematic. Eine
   HEATING_GROUP wird z. B. als virtuelles Gerät mit Kanälen für
   `setPointTemperature`, `actualTemperature`, `controlMode` etc. abgebildet.

   **Begründung**: Konsistent mit der bestehenden Architektur, keine
   Protocol-Erweiterungen nötig, HA-Integration kann Standard-Plattformen
   (climate, switch) nutzen.

2. **Firmware-Updates** → **Read-Only-Sensor**

   Firmware-Versionen werden als **Sensor-Entity** exponiert (read-only).
   Kein Update-Mechanismus — Firmware-Updates werden über die HmIP-App
   oder die HCU-Web-Oberfläche durchgeführt.

   **Begründung**: Die Connect API bietet keinen dokumentierten
   Update-Endpunkt. Die Referenzimplementierung bestätigt dies.

3. **Alarm-Panel** → **Virtuelles Gerät**

   Das Alarm-System (`SECURITY_AND_ALARM`) wird ebenfalls als
   **virtuelles Gerät** abgebildet, konsistent mit der Gruppen-Entscheidung.
   Sicherheitszonen werden als Kanäle dargestellt, Aktivierung/Deaktivierung
   als DataPoints.

   **Begründung**: Einheitliches Modell für alle HCU-Konzepte
   (Gruppen, Alarm, Home-Features) über virtuelle Geräte. Die
   HA-Integration nutzt die Standard `alarm_control_panel`-Plattform.

4. **Automatisierungsregeln** → **Als Entities exponieren**

   HCU-Regeln werden als **Switch-Entities** exponiert (aktivieren/
   deaktivieren), analog zu CCU-Programmen in aiohomematic. Der Endpunkt
   `/hmip/rule/enableSimpleRule` wird über `HMIP_SYSTEM_REQUEST` angesprochen.

   **Begründung**: Gibt dem Nutzer volle Kontrolle über HCU-Automatisierungen
   aus Home Assistant heraus. Konsistent mit dem bestehenden Programm-Modell
   der CCU.

5. **Performance** → **Vollständiger Ladevorgang + lokaler Cache**

   Beim Start wird der **gesamte Systemzustand** geladen und lokal gecacht
   (analog zum `DeviceDescriptionRegistry` in aiohomematic). Nachfolgende
   Starts nutzen den Cache und aktualisieren inkrementell über Events.

   **Begründung**: Einfache, bewährte Strategie. Der Cache beschleunigt
   Restarts erheblich. Die Event-Bridge hält den Cache nach dem initialen
   Laden aktuell.

---

## 13. Zusammenfassung

### Empfohlene Architektur

**Option D: Shared-Facade als Protocol-Schicht in aiohomematic.**

Die bestehende Protocol-basierte DI-Architektur von aiohomematic bietet eine
ideale Grundlage. Durch Definition von Unified-Protocols auf Facade-Ebene
können beide Backends (CCU und HCU) eine gemeinsame Schnittstelle bedienen,
ohne dass die bestehende CCU-Implementierung verändert werden muss.

### Revidierte Kernprinzipien (nach Analyse der Referenzimplementierung)

1. **Protocol-First**: Die Fassade besteht ausschließlich aus
   Protocol-Interfaces — keine Basisklassen, keine Vererbung.
2. **Capability-Driven**: Backend-spezifische Features werden über
   `CentralCapabilities` gesteuert, nicht über Typ-Prüfungen.
3. **Additiv**: Alle Änderungen an aiohomematic sind additiv — kein
   Breaking Change für bestehende CCU-Nutzer.
4. **Kanaltyp-Mapping statt Feature-Mapping**: HCU-Geräte nutzen
   `functionalChannelType` (HmIP-Cloud-Format), nicht das Feature-Modell
   der Connect API. Das Mapping ist konzeptionell näher an CCU-Paramsets.
5. **Gemeinsamer EventBus**: Beide Backends publizieren Events über
   den gleichen EventBus mit gemeinsamen Event-Typen.
6. **Gruppen als virtuelle Geräte**: HCU-Gruppen (Heating, Switching,
   Alarm) sowie Home-Level-Features (Alarm-Panel) werden als virtuelle
   Geräte mit Kanälen und DataPoints abgebildet. Kein eigenes
   Protocol — konsistent mit der Device-zentrierten Architektur.
7. **Plugin-Boilerplate minimal**: Die Connect API wird als
   Transportschicht genutzt. Das Plugin registriert sich, stellt aber
   keine eigenen Geräte bereit — es ist ein „passiver Plugin, aktiver
   Client".
8. **Regeln wie Programme**: HCU-Automatisierungsregeln werden als
   Switch-Entities exponiert, analog zu CCU-Programmen.

### Wichtigste Erkenntnisse

1. Das HCU-Datenmodell ist **kanaltyp-basiert** (`functionalChannelType`
   mit typisierten Properties), nicht feature-basiert wie in der Connect
   API-Dokumentation beschrieben. Das vereinfacht die Integration erheblich,
   da das Konzept konzeptionell näher an den CCU-Paramsets liegt als
   ursprünglich angenommen.

2. Die HCU-API und die HomematicIP-Cloud-API teilen **zu 95%+ dasselbe
   Datenmodell** (76 Kanaltypen, 27 Gruppentypen, identische Geräte-IDs).
   Die existierende homematicip-rest-api-Bibliothek dokumentiert **131
   Gerätetypen** und **78 Kanaltyp-Klassen** mit allen Properties. Diese
   kann als umfassende Referenz dienen, muss aber aufgrund der GPL-3.0-
   Lizenz und fehlender Typsicherheit **nicht als Dependency**, sondern
   als **Architektur- und Daten-Referenz** genutzt werden.

### Erkenntnisse aus homematicip-rest-api (Cloud-API-Bibliothek)

Die Analyse der Bibliothek [homematicip-rest-api](https://github.com/hahn-th/homematicip-rest-api)
liefert tiefgreifende zusätzliche Erkenntnisse, da die Cloud-API und die
HCU-API nahezu identische Datenmodelle verwenden.

#### Erkenntnis 1: Cloud-API und HCU-API teilen dasselbe Datenmodell

Die `home.json`-Testdaten (18.821 Zeilen, 141 Geräte, 43 Gruppen) verwenden
exakt dasselbe Format wie die HCU-Systemzustands-API. Die Datenstruktur ist:

```json
{
  "devices": { "<sgtin>": { "type": "...", "functionalChannels": {...} } },
  "groups": { "<uuid>": { "type": "...", "channels": [...] } },
  "clients": { "<uuid>": { "label": "...", "clientType": "APP" } },
  "home": { "weather": {...}, "location": {...}, "functionalHomes": {...} }
}
```

**Konsequenz**: Die homematicip-rest-api-Bibliothek kann als **Referenz-
Deserialisierung** für HCU-Daten dienen. Das spart erheblichen
Entwicklungsaufwand bei der Implementierung des HCU-Backends.

#### Erkenntnis 2: 76 functionalChannelType-Werte sind dokumentiert

Die Testdaten enthalten **76 einzigartige Kanaltypen** in 7 Kategorien:

| Kategorie | Anzahl | Beispiele |
|-----------|--------|-----------|
| Device-Base-Kanäle | 10 | `DEVICE_BASE`, `DEVICE_OPERATIONLOCK`, `DEVICE_SABOTAGE` |
| Aktor-Kanäle | 21 | `SWITCH_CHANNEL`, `DIMMER_CHANNEL`, `BLIND_CHANNEL`, `DOOR_LOCK_CHANNEL` |
| Klima/Thermostat | 6 | `HEATING_THERMOSTAT_CHANNEL`, `WALL_MOUNTED_THERMOSTAT_PRO_CHANNEL` |
| Fußbodenheizung | 5 | `FLOOR_TERMINAL_BLOCK_CHANNEL`, `HEAT_DEMAND_CHANNEL` |
| Sensor-Kanäle | 16 | `SHUTTER_CONTACT_CHANNEL`, `SMOKE_DETECTOR_CHANNEL`, `WEATHER_SENSOR_PRO_CHANNEL` |
| Input/Button-Kanäle | 8 | `SINGLE_KEY_CHANNEL`, `MULTI_MODE_INPUT_CHANNEL` |
| Zugangs-Kanäle | 4 | `ACCESS_AUTHORIZATION_CHANNEL`, `DOOR_LOCK_SENSOR_CHANNEL` |

Jeder Kanaltyp hat **typisierte Properties** mit festen Schlüsseln — das
ermöglicht statisch typisierte Python-Klassen statt generischem Dict-Zugriff.

#### Erkenntnis 3: 27 Gruppentypen mit komplexer Hierarchie

Die API kennt **27 verschiedene Gruppentypen**. Für die Fassade sind die
wichtigsten:

| Gruppentyp | Relevanz | Schlüssel-Properties |
|------------|----------|---------------------|
| `HEATING` | **Hoch** — Klimasteuerung | `actualTemperature`, `setPointTemperature`, `humidity`, `controlMode`, `boostMode`, `profiles`, `valvePosition` |
| `SECURITY_ZONE` | **Hoch** — Alarm-Panel | `active`, `silent`, `windowState`, `sabotage` |
| `ALARM_SWITCHING` | **Hoch** — Sirenen | `on`, `signalAcoustic`, `signalOptical` |
| `SWITCHING` | Mittel — Schaltgruppen | `on`, `dimLevel` |
| `META` | Mittel — Raumzuordnung | `groups` (Kind-Gruppen) |
| `ENVIRONMENT` | Mittel — Außensensoren | `actualTemperature`, `humidity`, `windSpeed` |
| `HOT_WATER` | Mittel — Warmwasser | `on`, `profileMode` |
| `SHUTTER_PROFILE` | Niedrig — Automatik | `shutterLevel`, `profileMode` |

Die **HeatingGroup** ist mit Abstand der komplexeste Gruppentyp (25+ Properties
inkl. Profilen, Boost-Modus, Fenster-Offen-Erkennung, Kühlmodus).

#### Erkenntnis 4: FunctionalHomes als Domain-Aggregatoren

Das `home`-Objekt enthält 6 **FunctionalHomes**, die als logische Subsysteme
fungieren:

| FunctionalHome | Funktion | Relevante Gruppen |
|---------------|----------|-------------------|
| `INDOOR_CLIMATE` | Heizung, Abwesenheit, Eco | Heating-Gruppen, Fußbodenheizung |
| `SECURITY_AND_ALARM` | Zonen, Alarme, Sirenen | Security-Zones, Alarm-Switching |
| `LIGHT_AND_SHADOW` | Licht/Rollladen-Automatik | Linked-Switching, Shutter-Profile |
| `ACCESS_CONTROL` | Schlösser, Garagen | Lock-Profile, Garage-Door |
| `WEATHER_AND_ENVIRONMENT` | Außensensoren | Environment-Gruppen |
| `ENERGY` | Energieüberwachung | Energy-Gruppen |

**Konsequenz für die Fassade**: FunctionalHomes bieten eine natürliche
Zuordnung zu `CentralCapabilities`. Ob ein Backend `INDOOR_CLIMATE` unterstützt,
bestimmt, ob Heizungs-Features angezeigt werden.

#### Erkenntnis 5: supportedOptionalFeatures als Laufzeit-Capability-System

Jedes Gerät meldet auf Kanal 0 über `supportedOptionalFeatures` (dict von
`IFeature*`-Flags → Boolean), welche optionalen Hardware-Fähigkeiten es hat:

```json
"supportedOptionalFeatures": {
  "IFeatureDeviceOverheated": false,
  "IFeatureRssiValue": true,
  "IOptionalFeatureDutyCycle": true,
  "IOptionalFeatureLowBat": true,
  "IOptionalFeatureMountingOrientation": false
}
```

Das einfachste Gerät hat 0 Flags, der RGBW-Dimmer hat 40+.

**Konsequenz**: Das HCU-Backend kann diesen Mechanismus nutzen, um pro Gerät
dynamisch zu entscheiden, welche DataPoints erstellt werden — analog zum
`ParameterVisibilityRegistry` in aiohomematic.

#### Erkenntnis 6: Die API-Endpunkte sind identisch

Die REST-API-Endpunkte der Cloud-API stimmen mit den `HMIP_SYSTEM_REQUEST`-
Pfaden der HCU überein:

| Cloud-API REST-Endpunkt | HCU `HMIP_SYSTEM_REQUEST` path |
|------------------------|-------------------------------|
| `device/control/setSwitchState` | `/hmip/device/control/setSwitchState` |
| `device/control/setDimLevel` | `/hmip/device/control/setDimLevel` |
| `device/control/setShutterLevel` | `/hmip/device/control/setShutterLevel` |
| `device/control/setSlatsLevel` | `/hmip/device/control/setSlatsLevel` |
| `device/control/setLockState` | `/hmip/device/control/setLockState` |
| `home/security/setZonesActivation` | `/hmip/home/security/setExtendedZonesActivation` |
| `home/heating/setSetPointTemperature` | `/hmip/group/heating/setSetPointTemperature` |
| `device/authorizeUpdate` | (noch zu prüfen) |

**Konsequenz**: Der HCU-Command-Layer kann die gleiche Endpunkt-Struktur
verwenden wie die Cloud-API — nur der Transportmechanismus unterscheidet
sich (WebSocket statt HTTPS-POST).

#### Erkenntnis 7: Vollständige Geräte-Typ-Registry vorhanden

Die homematicip-rest-api enthält eine **vollständige Registry** mit:
- **131 DeviceType → Klassen-Mappings** (TYPE_CLASS_MAP)
- **32 GroupType → Klassen-Mappings** (TYPE_GROUP_MAP)
- **78 FunctionalChannelType → Klassen-Mappings** (TYPE_FUNCTIONALCHANNEL_MAP)

Diese Registries können als **Referenz-Mapping** für das HCU-Backend dienen.
Die Kanaltyp-zu-Entity-Zuordnung muss nicht von Grund auf entwickelt werden.

#### Erkenntnis 8: Event-Modell mit vollständiger State-Ersetzung

Events kommen über WebSocket und enthalten den **vollständigen Objektzustand**
(nicht nur Deltas):

```python
# Event-Typen (10):
DEVICE_CHANGED    # Gerät aktualisiert (vollständiger State)
DEVICE_ADDED      # Neues Gerät
DEVICE_REMOVED    # Gerät entfernt
GROUP_CHANGED     # Gruppe aktualisiert
GROUP_ADDED       # Neue Gruppe
GROUP_REMOVED     # Gruppe entfernt
HOME_CHANGED      # Home-Objekt aktualisiert
CLIENT_ADDED/CHANGED/REMOVED  # Client-Änderungen
DEVICE_CHANNEL_EVENT           # Button-Press, Doorbell etc.
```

**Konsequenz**: Die Event-Bridge im HCU-Backend muss:
1. Den neuen vollständigen State mit dem gecachten vergleichen
2. Nur für tatsächlich geänderte Properties DataPoint-Events generieren
3. `DEVICE_CHANNEL_EVENT` auf aiohomematic-Events abbilden

#### Erkenntnis 9: Möglichkeit zur Wiederverwendung der Bibliothek

Die homematicip-rest-api ist ein **existierendes, stabiles Projekt** (GPL-3.0)
das aktiv gepflegt wird. Es gibt zwei strategische Optionen:

**Option A: Als Abhängigkeit nutzen**
- homematicip-rest-api als Dependency des HCU-Backends
- Vorteil: Sofort 131+ Gerätetypen, Deserialisierung, WebSocket-Handling
- Nachteil: GPL-3.0-Lizenz (aiohomematic ist MIT), keine Typsicherheit,
  Legacy-Code-Stil

**Option B: Als Referenz nutzen (empfohlen)**
- Die Registries, Kanaltyp-Definitionen und Testdaten als Referenz
- Eigene typsichere Implementierung in aiohomematic-Qualität
- Die `home.json` als Basis für HCU-Backend-Tests nutzen
- Vorteil: MIT-kompatibel, strikt typisiert, konsistent mit aiohomematic

#### Erkenntnis 10: Architektonische Unterschiede Cloud vs. HCU

| Aspekt | Cloud-API | HCU Connect API |
|--------|-----------|-----------------|
| Transport | HTTPS REST + WebSocket | WebSocket only |
| Authentifizierung | SGTIN + SHA512-Token + Button-Press | Bearer-Token via Plugin-Registrierung |
| URL-Discovery | `lookup.homematic.com:48335` | Direkt `wss://hcu-ip:9001` |
| Rate-Limiting | Token-Bucket (10 req / 8s fill) | Nicht dokumentiert |
| State-Abruf | `POST home/getCurrentState` | `HMIP_SYSTEM_REQUEST` mit path |
| Geräte-IDs | SGTIN (identisch) | SGTIN (identisch) |
| Datenformat | Identisch | Identisch |
| Event-Format | WebSocket push (identisch) | WebSocket push (via `eventTransaction`) |

**Wichtigste Erkenntnis**: Der Transportmechanismus unterscheidet sich, aber
das Datenmodell ist **zu 95%+ identisch**. Das bedeutet, dass Deserialisierung,
Kanaltyp-Mapping und Entity-Erstellung für Cloud-API und HCU-API gemeinsam
genutzt werden können.

### Alle Design-Entscheidungen getroffen

Alle offenen Architektur-Fragen sind geklärt:

| Aspekt | Entscheidung |
|--------|-------------|
| Gruppen | Virtuelle Geräte mit Kanälen/DataPoints |
| Alarm-Panel | Virtuelles Gerät (konsistent mit Gruppen) |
| Firmware | Read-Only-Sensor |
| Regeln | Switch-Entities (analog CCU-Programme) |
| Performance | Vollständiger Ladevorgang + lokaler Cache |

### Nächste Schritte

1. **Phase 1 starten**: Facade-Protocols definieren und bestehende
   Klassen erweitern (CentralUnit → UnifiedCentralProtocol)
2. **Kanaltyp-Registry aufbauen**: Mapping von
   `functionalChannelType` → Entity-Erstellungslogik, inkl.
   Gruppen → virtuelle Geräte. Die 78 Kanaltyp-Mappings aus
   homematicip-rest-api als Referenz nutzen.
3. **Testdaten übernehmen**: Die `home.json` (18.821 Zeilen, 141
   Geräte) aus homematicip-rest-api als Basis für HCU-Backend-Tests
   adaptieren (Lizenz beachten: GPL-3.0 → eigene Testdaten ableiten).
4. **Proof of Concept**: Minimale HCU-Anbindung mit Switch + Sensor +
   Heating-Group zum Validieren der Architektur
5. **Regeln-Support**: `/hmip/rule/enableSimpleRule` als Switch-Entities
   anbinden (analog CCU-Programm-Modell)

### Referenz-Materialien

| Quelle | Nutzen | Lizenz |
|--------|--------|--------|
| [homematicip-rest-api](https://github.com/hahn-th/homematicip-rest-api) | 131 DeviceType-Mappings, 78 Kanaltyp-Klassen, home.json Testdaten, Event-Verarbeitung | GPL-3.0 |
| [hacs-homematicip-hcu](https://github.com/Ediminator/hacs-homematicip-hcu) | HCU-Connect-API-Nutzung, WebSocket-Client, Plugin-Lifecycle | ? |
| HCU Connect API Spec v1.0.1 | Offizielle API-Dokumentation, Plugin-Konzept, Nachrichtentypen | eQ-3 |
