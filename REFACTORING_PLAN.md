# Refactoring-Plan: Variablenbenennung Konsistenz

## Executive Summary

Vollständiges Refactoring aller inkonsistenten Variablenbenennungen in der aiohomematic Codebase für verbesserte Code-Verständlichkeit und Vermeidung von Namenskollisionen.

### Entscheidungen
- ✅ **Protocol-Interfaces MIT "-Protocol" Suffix** (ALLE!)
- ✅ **Parameter/Variablen OHNE "-Protocol" Suffix**
- ✅ **"Provider" bleibt in Variablennamen** (semantisches Konzept!)
- ✅ Cache-Klassen behalten "Cache" Suffix
- ✅ Scope: Vollständiges Refactoring

### Hauptänderungen

| Kategorie | Beispiel | Anzahl Dateien |
|-----------|----------|----------------|
| **Protocol-Suffix HINZUFÜGEN** | `ClientProvider` → `ClientProviderProtocol` | **~100+** |
| ClientDependencies | `central` → `client_deps` | 10+ |
| Handler-Naming | `LinkManagementHandler` → `LinkHandler` | 6-8 |
| Cache-Suffixe | `_device_details` → `_device_details_cache` | 10-15 |
| Model-Layer | `_description` → `_device_description` | 10-15 |

### Aufwand
- **Entwicklung:** 16-20 Stunden
- **Testing:** 3-4 Stunden
- **Review:** 2 Stunden
- **Gesamt:** 21-26 Stunden

### Risiko
**HIGH** - Phase 1 (Protocol-Suffix) betrifft ~100+ Dateien über ALLE Layers. Dies ist die größte Änderung!

---

## Kritische Erkenntnis: Namenskollisionen

### Problem

Ohne `-Protocol` Suffix entstehen **Namenskollisionen** zwischen Protocol und Implementierung:

```python
# ❌ KOLLISION ohne Suffix:
class CentralStateMachine(Protocol):  # Protocol
    ...

class CentralStateMachine:  # Implementierung - FEHLER!
    ...
```

### Konkrete Kollisionen im Projekt

```python
# 1. CentralStateMachineProtocol → CentralStateMachine = KOLLISION!
#    aiohomematic/interfaces/central.py:488
class CentralStateMachineProtocol(Protocol): ...
#    aiohomematic/central/state_machine.py:126
class CentralStateMachine(CentralStateMachineProtocol): ...

# 2. DeviceProtocol → Device = KOLLISION!
#    aiohomematic/interfaces/model.py
class DeviceProtocol(Protocol): ...
#    aiohomematic/model/device.py:157
class Device(DeviceProtocol): ...

# 3. ChannelProtocol → Channel = KOLLISION!
#    aiohomematic/interfaces/model.py
class ChannelProtocol(Protocol): ...
#    aiohomematic/model/device.py:1018
class Channel(ChannelProtocol): ...

# 4. ClientProtocol → Client = KOLLISION!
#    aiohomematic/interfaces/client.py
class ClientProtocol(Protocol): ...
#    aiohomematic/client/__init__.py (mehrere Client-Klassen)
class ClientCCU(ClientProtocol): ...
class ClientJsonCCU(ClientCCU): ...
```

### Lösung

**ALLE Protocols behalten/bekommen `-Protocol` Suffix:**

```python
# Protocol Definition (MIT Suffix)
@runtime_checkable
class ClientProviderProtocol(Protocol):
    """Protocol for accessing clients."""
    def get_client(self, interface_id: str) -> ClientProtocol: ...

@runtime_checkable
class ConfigProviderProtocol(Protocol):
    """Protocol for accessing configuration."""
    @property
    def config(self) -> CentralConfig: ...

# Verwendung (Parameter/Variablen MIT "provider")
class ClientCoordinator:
    def __init__(
        self,
        *,
        client_provider: ClientProviderProtocol,  # Type hint MIT Protocol-Suffix
        config_provider: ConfigProviderProtocol,  # "provider" bleibt!
    ):
        self._client_provider = client_provider   # Variable MIT provider
        self._config_provider = config_provider   # Variable MIT provider
```

**Wichtig: "Provider" ist semantisches Konzept!**

```python
# ✅ RICHTIG - Provider-Semantik bleibt erhalten:
client_provider: ClientProviderProtocol
client = client_provider.get_client()  # Klar: Provider liefert Client!

# ❌ FALSCH - Verliert Provider-Semantik:
clients: ClientProviderProtocol
client = clients.get_client()  # Klingt nach Collection-Abfrage!
```

**Vorteile:**
- ✅ Keine Namenskollisionen möglich
- ✅ Sofortige Erkennbarkeit: "Das ist ein Protocol"
- ✅ Provider-Semantik bleibt erhalten
- ✅ Standard-Pattern in vielen Python-Projekten

---

## Detaillierte Analyse

### Gefundene Inkonsistenzen

**4 Hauptbereiche:**
1. **Protocol-Namen** - 73 OHNE `-Protocol` Suffix, 9 MIT Suffix (inkonsistent!)
2. **ClientDependencies** - `central` statt `client_deps` (missverständlich)
3. **Cache-Variablen** - Inkonsistente Verwendung von `_cache` Suffix
4. **Handler-Klassen** - `LinkManagementHandler`, `DeviceOperationsHandler` zu lang

**Zusätzliche Fälle:**
- `_description` zu generisch (sollte `_device_description` sein)
- `_dp_xxx` Abkürzungen statt `_data_point_xxx`
- Collection-Namen nicht spiegelbildlich (`_channel_group` vs `_group_channels`)

---

## Phase 1: Protocol-Suffix HINZUFÜGEN (CRITICAL - HIGHEST PRIORITY)

### 1.1 Aktueller Stand

**Protocols MIT `-Protocol` Suffix (9):**
- `HealthTrackerProtocol`
- `CentralStateMachineProtocol`
- `CentralHealthProtocol`
- `CallbackDataPointProtocol`
- `BaseDataPointProtocol`
- `BaseParameterDataPointProtocol`
- `GenericDataPointProtocol`
- `CustomDataPointProtocol`
- `CalculatedDataPointProtocol`

**Protocols OHNE `-Protocol` Suffix (~73) - MÜSSEN umbenannt werden:**

**Central Protocols (aiohomematic/interfaces/central.py):**
- `CentralInfo` → `CentralInfoProtocol`
- `CentralUnitStateProvider` → `CentralUnitStateProviderProtocol`
- `ConfigProvider` → `ConfigProviderProtocol`
- `SystemInfoProvider` → `SystemInfoProviderProtocol`
- `BackupProvider` → `BackupProviderProtocol`
- `DeviceManagement` → `DeviceManagementProtocol`
- `EventBusProvider` → `EventBusProviderProtocol`
- `EventPublisher` → `EventPublisherProtocol`
- `DataPointProvider` → `DataPointProviderProtocol`
- `DeviceProvider` → `DeviceProviderProtocol`
- `ChannelLookup` → `ChannelLookupProtocol`
- `FileOperations` → `FileOperationsProtocol`
- `FirmwareDataRefresher` → `FirmwareDataRefresherProtocol`
- `DeviceDataRefresher` → `DeviceDataRefresherProtocol`
- `DataCacheProvider` → `DataCacheProviderProtocol`
- `HubFetchOperations` → `HubFetchOperationsProtocol`
- `HubDataFetcher` → `HubDataFetcherProtocol`
- `HubDataPointManager` → `HubDataPointManagerProtocol`
- `EventSubscriptionManager` → `EventSubscriptionManagerProtocol`
- `RpcServerCentralProtocol` → `RpcServerCentralProtocol` (hat bereits Suffix!)
- `RpcServerTaskScheduler` → `RpcServerTaskSchedulerProtocol`
- `CentralStateMachineProvider` → `CentralStateMachineProviderProtocol`
- `ConnectionHealthProtocol` → `ConnectionHealthProtocol` (hat bereits Suffix!)
- `HealthProvider` → `HealthProviderProtocol`

**Client Protocols (aiohomematic/interfaces/client.py):**
- `ClientProtocol` → `ClientProtocol` (hat bereits Suffix!)
- `DeviceDiscoveryOperations` → `DeviceDiscoveryOperationsProtocol`
- `ParamsetOperations` → `ParamsetOperationsProtocol`
- `ValueOperations` → `ValueOperationsProtocol`
- `LinkOperations` → `LinkOperationsProtocol`
- `FirmwareOperations` → `FirmwareOperationsProtocol`
- `SystemVariableOperations` → `SystemVariableOperationsProtocol`
- `ProgramOperations` → `ProgramOperationsProtocol`
- `BackupOperations` → `BackupOperationsProtocol`
- `MetadataOperations` → `MetadataOperationsProtocol`
- `ClientProvider` → `ClientProviderProtocol`
- `PrimaryClientProvider` → `PrimaryClientProviderProtocol`
- `ConnectionStateProvider` → `ConnectionStateProviderProtocol`
- `SessionRecorderProvider` → `SessionRecorderProviderProtocol`
- `JsonRpcClientProvider` → `JsonRpcClientProviderProtocol`
- `CallbackAddressProvider` → `CallbackAddressProviderProtocol`
- (+ weitere Client-bezogene Protocols)

**Operations Protocols (aiohomematic/interfaces/operations.py):**
- `TaskScheduler` → `TaskSchedulerProtocol`
- `ParameterVisibilityProvider` → `ParameterVisibilityProviderProtocol`
- `DeviceDetailsProvider` → `DeviceDetailsProviderProtocol`
- `DeviceDescriptionProvider` → `DeviceDescriptionProviderProtocol`
- `ParamsetDescriptionProvider` → `ParamsetDescriptionProviderProtocol`

**Coordinator Protocols (aiohomematic/interfaces/coordinators.py):**
- `CoordinatorProvider` → `CoordinatorProviderProtocol`

**Model Protocols (aiohomematic/interfaces/model.py):**
- `GenericHubDataPointProtocol` → `GenericHubDataPointProtocol` (hat bereits Suffix!)
- `GenericSysvarDataPointProtocol` → `GenericSysvarDataPointProtocol` (hat bereits Suffix!)
- `GenericProgramDataPointProtocol` → `GenericProgramDataPointProtocol` (hat bereits Suffix!)
- `HubSensorDataPointProtocol` → `HubSensorDataPointProtocol` (hat bereits Suffix!)
- `GenericInstallModeDataPointProtocol` → `GenericInstallModeDataPointProtocol` (hat bereits Suffix!)
- `GenericEventProtocol` → `GenericEventProtocol` (hat bereits Suffix!)
- `ChannelIdentity` → `ChannelIdentityProtocol`
- `ChannelDataPointAccess` → `ChannelDataPointAccessProtocol`
- `ChannelGrouping` → `ChannelGroupingProtocol`
- `ChannelMetadata` → `ChannelMetadataProtocol`
- `ChannelLinkManagement` → `ChannelLinkManagementProtocol`
- `ChannelLifecycle` → `ChannelLifecycleProtocol`
- `ChannelProtocol` → `ChannelProtocol` (hat bereits Suffix!)
- `DeviceIdentity` → `DeviceIdentityProtocol`
- `DeviceChannelAccess` → `DeviceChannelAccessProtocol`
- `DeviceAvailability` → `DeviceAvailabilityProtocol`
- `DeviceFirmware` → `DeviceFirmwareProtocol`
- `DeviceLinkManagement` → `DeviceLinkManagementProtocol`
- `DeviceGroupManagement` → `DeviceGroupManagementProtocol`
- `DeviceConfiguration` → `DeviceConfigurationProtocol`
- `DeviceWeekProfile` → `DeviceWeekProfileProtocol`
- `DeviceProviders` → `DeviceProvidersProtocol`
- `DeviceLifecycle` → `DeviceLifecycleProtocol`
- `DeviceProtocol` → `DeviceProtocol` (hat bereits Suffix!)
- `WeekProfileProtocol` → `WeekProfileProtocol` (hat bereits Suffix!)
- `HubProtocol` → `HubProtocol` (hat bereits Suffix!)

### 1.2 Strategie

**Schritt 1: Protocol-Definitionen umbenennen**

Alle ~73 Protocols OHNE Suffix bekommen das `-Protocol` Suffix.

**Schritt 2: Type Hints aktualisieren**

Alle Type Hints müssen auf neue Namen aktualisiert werden:

```python
# Vorher:
def __init__(self, *, config_provider: ConfigProvider): ...

# Nachher:
def __init__(self, *, config_provider: ConfigProviderProtocol): ...
```

**Wichtig:** Variablennamen bleiben UNVERÄNDERT (inkl. "provider")!

```python
# ✅ RICHTIG:
client_provider: ClientProviderProtocol  # "provider" bleibt im Namen!
config_provider: ConfigProviderProtocol  # "provider" bleibt im Namen!

# ❌ FALSCH:
clients: ClientProviderProtocol  # Verliert Provider-Semantik!
config: ConfigProviderProtocol   # Verliert Provider-Semantik!
```

**Schritt 3: TYPE_CHECKING Imports aktualisieren**

```python
# Vorher:
if TYPE_CHECKING:
    from aiohomematic.interfaces.central import ConfigProvider, EventBusProvider

# Nachher:
if TYPE_CHECKING:
    from aiohomematic.interfaces.central import ConfigProviderProtocol, EventBusProviderProtocol
```

**Schritt 4: isinstance/issubclass Checks aktualisieren**

```python
# Vorher:
if isinstance(obj, ConfigProvider): ...

# Nachher:
if isinstance(obj, ConfigProviderProtocol): ...
```

### 1.3 Betroffene Bereiche

**Alle Protocol-Definitionen:**
- `aiohomematic/interfaces/central.py` - ~26 Protocols
- `aiohomematic/interfaces/client.py` - ~34 Protocols
- `aiohomematic/interfaces/operations.py` - ~5 Protocols
- `aiohomematic/interfaces/coordinators.py` - ~1 Protocol
- `aiohomematic/interfaces/model.py` - ~20 Protocols (viele haben bereits Suffix)

**Alle Verwendungen:**
- `aiohomematic/central/*.py` - Alle Coordinators
- `aiohomematic/client/*.py` - Client-Implementierungen
- `aiohomematic/model/*.py` - Device, Channel, DataPoint
- `aiohomematic/model/custom/*.py` - Custom DataPoints
- `aiohomematic/model/generic/*.py` - Generic DataPoints
- `aiohomematic/model/calculated/*.py` - Calculated DataPoints
- `aiohomematic/model/hub/*.py` - Hub entities
- `aiohomematic/store/*.py` - Cache/Store Klassen

**Impact:** ~100+ Dateien (ALLE Layers!)

### 1.4 Spezialfälle

**Provider bleibt Provider:**

```python
# Protocol Interface
@runtime_checkable
class ConfigProviderProtocol(Protocol):
    """Protocol for accessing configuration."""
    @property
    def config(self) -> CentralConfig: ...

# Variable/Parameter (MIT "provider")
class Device:
    def __init__(self, *, config_provider: ConfigProviderProtocol):
        self._config_provider = config_provider  # Variable: config_provider

    @property
    def config_provider(self) -> ConfigProviderProtocol:
        """Return config provider."""
        return self._config_provider
```

**Wichtig:**
- Type Hints: `ConfigProviderProtocol` (MIT -Protocol Suffix)
- Variablen: `config_provider` (MIT provider, OHNE Protocol)
- Properties: `config_provider` (descriptiv)

---

## Phase 2: ClientDependencies Umbenennung (CRITICAL)

### 2.1 central (ClientDependencies) → client_deps

**Dateien:**
- `aiohomematic/client/__init__.py:1602` - ClientConfig.__init__
- `aiohomematic/client/handlers/base.py:42,61,69-70` - BaseHandler
- Alle 7 Handler-Klassen (Device, Link, Firmware, SystemVariable, Program, Backup, Metadata)

**Änderungen:**
```python
# ClientConfig
class ClientConfig:
    def __init__(self, *, client_deps: ClientDependenciesProtocol, ...):
        self.client_deps: Final[ClientDependenciesProtocol] = client_deps

# BaseHandler
class BaseHandler:
    def __init__(self, *, client_deps: ClientDependenciesProtocol, ...):
        self._client_deps: Final = client_deps

    @property
    def client_deps(self) -> ClientDependenciesProtocol:
        return self._client_deps
```

**Wichtig:** Bei dieser Umbenennung auch `RpcServerCentralProtocol` berücksichtigen:
- `RpcServerCentralProtocol` (aiohomematic/interfaces/central.py:430) wird von `rpc_server.py` verwendet
- Prüfen ob Konsistenz mit ClientDependencies-Parameterbenennung hergestellt werden sollte
- Beide Protocols dienen der Dependency Injection für unterschiedliche Kontexte (Client vs RPC Server)

**Impact:** 10+ Dateien

---

## Phase 3: Cache/Store Variablen (MEDIUM RISK)

### 3.1 CacheCoordinator - Konsistente _cache Suffixe

**Datei:** `aiohomematic/central/cache_coordinator.py`

**Änderungen:**
```python
# Vorher:
self._device_details: Final = DeviceDetailsCache(...)
self._device_descriptions: Final = DeviceDescriptionCache(...)
self._parameter_visibility: Final = ParameterVisibilityCache(...)
self._paramset_descriptions: Final = ParamsetDescriptionCache(...)
self._recorder: Final = SessionRecorder(...)

# Nachher:
self._device_details_cache: Final = DeviceDetailsCache(...)
self._device_descriptions_cache: Final = DeviceDescriptionCache(...)
self._parameter_visibility_cache: Final = ParameterVisibilityCache(...)
self._paramset_descriptions_cache: Final = ParamsetDescriptionCache(...)
self._session_recorder: Final = SessionRecorder(...)
```

**Impact:** 5-10 Dateien (alle die auf CacheCoordinator Properties zugreifen)

### 3.2 Client._last_value_send_cache → _command_cache

**Datei:** `aiohomematic/client/__init__.py:186`

**Änderung:**
```python
# Vorher:
self._last_value_send_cache = CommandCache(...)

# Nachher:
self._command_cache = CommandCache(...)
```

**Impact:** 2-3 Dateien

### 3.3 DeviceDetailsCache interne Caches - Konsistente Suffixe

**Datei:** `aiohomematic/store/dynamic.py:303-309`

**Empfehlung:** OHNE Suffix (kürzer, da alle Members ohnehin caches sind)

### 3.4 Generische "cache" Variablen umbenennen

**Beispiele:**
- `aiohomematic/store/persistent.py:556` - `cache` → `address_param_map`
- `aiohomematic/store/dynamic.py:466` - `_value_cache` → `_parameter_values_by_interface`
- `aiohomematic/client/json_rpc.py:259` - `_script_cache` → `_rega_script_cache`

**Impact:** 5-8 Dateien

---

## Phase 4: Model Layer Naming (MEDIUM PRIORITY)

### 4.1 device._description → device._device_description

**Datei:** `aiohomematic/model/device.py:291,302,1091`

**Änderung:**
```python
# Vorher:
self._description = self._device_description_provider.get_device_description(...)

# Nachher:
self._device_description = self._device_description_provider.get_device_description(...)
```

**Impact:** 3-5 Dateien

### 4.2 channel._description → channel._channel_description

**Datei:** `aiohomematic/model/device.py:1091` (Channel class)

**Änderung:**
```python
# Vorher:
self._description: DeviceDescription = ...

# Nachher:
self._channel_description: DeviceDescription = ...
```

**Impact:** 2-3 Dateien

### 4.3 _dp_xxx Properties → _data_point_xxx

**Datei:** `aiohomematic/model/device.py:352-365`

**Änderungen:**
```python
# Vorher:
@property
def _dp_config_pending(self) -> DpBinarySensor | None: ...

@property
def _dp_sticky_un_reach(self) -> DpBinarySensor | None: ...

# Nachher:
@property
def _data_point_config_pending(self) -> DpBinarySensor | None: ...

@property
def _data_point_sticky_un_reach(self) -> DpBinarySensor | None: ...
```

**Impact:** 3-4 Dateien

### 4.4 Collection Naming - _channel_group vs _group_channels

**Datei:** `aiohomematic/model/device.py:286-287`

**Änderungen:**
```python
# Vorher:
self._channel_group: Final[dict[int | None, int]] = {}
self._group_channels: Final[dict[int, set[int | None]]] = {}

# Nachher (klarer spiegelt inverse Beziehung):
self._channel_to_group: Final[dict[int | None, int]] = {}
self._group_to_channels: Final[dict[int, set[int | None]]] = {}
```

**Impact:** 2-3 Dateien

---

## Phase 5: Coordinator Layer (LOW-MEDIUM PRIORITY)

### 5.1 BackgroundScheduler - Protocols statt konkreter Klassen

**Datei:** `aiohomematic/central/scheduler.py:136-150`

**Neue Protocols definieren:**
```python
# In aiohomematic/interfaces/central.py

@runtime_checkable
class ClientOperationsProtocol(Protocol):
    @property
    def clients(self) -> tuple[ClientProtocol, ...]: ...

    @property
    def poll_clients(self) -> tuple[ClientProtocol, ...]: ...

@runtime_checkable
class EventOperationsProtocol(Protocol):
    def set_last_event_seen_for_interface(self, *, interface_id: str) -> None: ...
    # ... weitere Methoden
```

**Änderung in BackgroundScheduler:**
```python
# Vorher:
def __init__(
    self,
    *,
    client_coordinator: ClientCoordinator,
    event_coordinator: EventCoordinator,
    ...
):

# Nachher:
def __init__(
    self,
    *,
    client_operations: ClientOperationsProtocol,
    event_operations: EventOperationsProtocol,
    ...
):
```

**Impact:** 4-5 Dateien

---

## Phase 6: Dokumentation Updates

### 6.1 Veraltete Hub-Dokumentation

**Datei:** `aiohomematic/model/hub/__init__.py:67`

**Änderung:**
```python
# Alte Dokumentation entfernen oder aktualisieren:
# hub = Hub(central)  # ← VERALTET

# Neue Dokumentation:
# Hub is now initialized by HubCoordinator with protocol interfaces:
# hub = Hub(
#     central_info=central_info,
#     config_provider=config_provider,
#     ...
# )
```

### 6.2 CLAUDE.md Update

**Datei:** `CLAUDE.md`

Abschnitt über Naming Conventions aktualisieren mit:
- Protocol-Namen MIT `-Protocol` Suffix
- "Provider" bleibt in Variablennamen
- Cache-Variablen MIT `_cache` Suffix

---

## Phase 7: Handler-Klassen Naming (LOW-MEDIUM RISK)

### 7.1 LinkManagementHandler → LinkHandler

**Datei:** `aiohomematic/client/handlers/link_mgmt.py`

**Änderungen:**
```python
# Vorher:
class LinkManagementHandler(BaseHandler, LinkOperationsProtocol):
    """Handler for device linking operations."""
    ...

# Nachher:
class LinkHandler(BaseHandler, LinkOperationsProtocol):
    """Handler for device linking operations."""
    ...
```

**Impact:** 3-4 Dateien (link_mgmt.py, client/__init__.py, usages)

**Begründung:** Konsistenz mit anderen Handler-Namen (BackupHandler, FirmwareHandler, MetadataHandler, ProgramHandler)

### 7.2 DeviceOperationsHandler → DeviceHandler

**Datei:** `aiohomematic/client/handlers/device_ops.py`

**Änderungen:**
```python
# Vorher:
class DeviceOperationsHandler(
    BaseHandler,
    DeviceDiscoveryOperationsProtocol,
    ParamsetOperationsProtocol,
    ValueOperationsProtocol,
):
    """Handler for device value and paramset operations."""
    ...

# Nachher:
class DeviceHandler(
    BaseHandler,
    DeviceDiscoveryOperationsProtocol,
    ParamsetOperationsProtocol,
    ValueOperationsProtocol,
):
    """Handler for device value and paramset operations."""
    ...
```

**Impact:** 3-4 Dateien (device_ops.py, client/__init__.py, usages)

**Begründung:**
- Konsistenz mit anderen Handler-Namen
- "DeviceOperations" ist redundant, da alle Handler Operationen durchführen
- Kürzer und prägnanter

### 7.3 Handler-Übersicht nach Refactoring

**Vollständige konsistente Handler-Liste:**
```python
# aiohomematic/client/handlers/
BackupHandler           # implements BackupOperationsProtocol
DeviceHandler           # implements DeviceDiscoveryOperationsProtocol, ParamsetOperationsProtocol, ValueOperationsProtocol
FirmwareHandler         # implements FirmwareOperationsProtocol
LinkHandler             # implements LinkOperationsProtocol
MetadataHandler         # implements MetadataOperationsProtocol
ProgramHandler          # implements ProgramOperationsProtocol
SystemVariableHandler   # implements SystemVariableOperationsProtocol (Ausnahme: längerer Name für Klarheit)
```

**Naming-Pattern:**
- Handler-Klassen: `<Domain>Handler`
- Protocol-Interfaces: `<Domain>OperationsProtocol`
- Ausnahme: `SystemVariableHandler` (nicht `SysvarHandler`) für bessere Lesbarkeit

**Impact:** 6-8 Dateien total

---

## Implementierungs-Reihenfolge

**Wichtig:** Reihenfolge ist KRITISCH wegen Dependencies!

### Strategie: Bottom-Up (von innen nach außen)

1. **Phase 1** - Protocol-Suffix HINZUFÜGEN
   - **KRITISCHSTE Änderung!** ~100+ Dateien
   - ALLE Protocol-Definitionen umbenennen
   - ALLE Type Hints aktualisieren
   - ALLE Imports aktualisieren
   - **MUSS als ERSTES gemacht werden**, da alle anderen Phasen davon abhängen

2. **Phase 5.1** - Neue Coordinator Protocols
   - Additive Changes (BackgroundScheduler Protocols)
   - Keine Breaking Changes

3. **Phase 7** - Handler-Klassen Naming
   - LinkManagementHandler → LinkHandler
   - DeviceOperationsHandler → DeviceHandler
   - Isoliert auf client/handlers/
   - ~6-8 Dateien

4. **Phase 3** - Cache Variablen
   - Isoliert auf store/ und cache_coordinator
   - Mittlerer Impact (10-15 Dateien)

5. **Phase 2** - ClientDependencies → client_deps
   - Kritisch, aber isoliert auf client/ und handlers/
   - ~10 Dateien
   - Sollte NACH Phase 7 kommen (da Handler-Klassen betroffen)

6. **Phase 4** - Model Layer Details
   - Device._description, Channel._description, _dp_ Properties
   - Isoliert auf model/
   - ~10-15 Dateien

7. **Phase 6** - Dokumentation
   - Keine Code-Änderungen

**Empfehlung:**
- **Phase 1 in Sub-Phasen aufteilen:**
  1. Phase 1a: interfaces/ - Protocol-Definitionen
  2. Phase 1b: central/ - Coordinator-Layer
  3. Phase 1c: model/ - Model-Layer
  4. Phase 1d: client/ - Client-Layer
  5. Phase 1e: store/ - Store-Layer
- Jede Sub-Phase in separatem Commit
- Nach jedem Commit: Tests + mypy laufen lassen

---

## Test-Strategie

Nach jeder Phase:
1. `ruff format` - Auto-Format
2. `ruff check --fix` - Linting
3. `mypy` - Type-Check (CRITICAL!)
4. `pytest tests/` - Alle Tests
5. Manual check für übersehene Usages

**Wichtig:** Type-Checker wird viele Probleme aufdecken!

**Spezial-Check für Phase 1:**
```bash
# Alle Protocol-Definitionen finden
grep -r "class.*Protocol):" aiohomematic/interfaces/

# Alle Protocol-Verwendungen finden
grep -r ": \w\+Protocol" aiohomematic/

# Sicherstellen, dass keine Protokolle OHNE Suffix existieren
grep -r "class \w\+(Protocol):" aiohomematic/interfaces/ | grep -v "Protocol("
```

---

## Risiko-Bewertung

| Phase | Risiko | Dateien | Grund |
|-------|--------|---------|-------|
| 1 | **CRITICAL** | **~100+** | **Betrifft ALLE Layers, größte Änderung!** |
| 2 | MEDIUM | 10+ | Isoliert auf client/, aber kritisch |
| 3 | MEDIUM | 10-15 | Isoliert auf store/ |
| 4 | LOW | 10-15 | Isoliert auf model/ |
| 5 | LOW | 4-5 | Neue Protocols, keine Breaking Changes |
| 6 | NONE | 2 | Nur Doku |
| 7 | LOW | 6-8 | Handler-Naming, isoliert auf client/handlers/ |

**Gesamt-Risiko:** **CRITICAL** (wegen Phase 1 Protocol-Suffix Hinzufügung)

---

## Kritische Dateien

**Am meisten betroffen:**
- `aiohomematic/interfaces/central.py` - ~26 Protocol-Umbenennungen
- `aiohomematic/interfaces/client.py` - ~34 Protocol-Umbenennungen
- `aiohomematic/interfaces/model.py` - ~20 Protocol-Umbenennungen
- `aiohomematic/interfaces/operations.py` - ~5 Protocol-Umbenennungen
- `aiohomematic/model/device.py` - ~40 Type Hint Updates
- `aiohomematic/model/data_point.py` - ~30 Type Hint Updates
- `aiohomematic/central/device_coordinator.py` - ~25 Type Hint Updates
- `aiohomematic/central/cache_coordinator.py` - ~20 Type Hint Updates
- `aiohomematic/client/__init__.py` - ~20 Type Hint Updates

**Alle Custom DataPoint Klassen:**
- `aiohomematic/model/custom/*.py` - ~50 Dateien
- `aiohomematic/model/generic/*.py` - ~10 Dateien

**Alle Coordinator Klassen:**
- `aiohomematic/central/*.py` - ~11 Dateien

---

## Success Criteria

✅ Alle Tests passing
✅ Mypy strict mode ohne Fehler
✅ Ruff/Pylint ohne neue Warnings
✅ Konsistente Benennung project-wide:
  - **Protocols MIT "-Protocol" Suffix**
  - **"Provider" bleibt in Variablennamen**
  - Cache-Variablen MIT "_cache" Suffix
  - Handler-Klassen: `<Domain>Handler`
✅ Dokumentation aktualisiert
✅ **Keine Namenskollisionen** zwischen Protocols und Implementierungen

---

## Geschätzter Aufwand

- **Phase 1 (Protocol-Suffix):** 12-15 Stunden (MASSIV!)
  - Phase 1a (interfaces/): 3 Stunden
  - Phase 1b (central/): 3 Stunden
  - Phase 1c (model/): 3 Stunden
  - Phase 1d (client/): 2 Stunden
  - Phase 1e (store/): 1 Stunde
- **Phase 5.1 (Coordinator Protocols):** 30 Minuten
- **Phase 7 (Handler-Naming):** 30 Minuten
- **Phase 3 (Cache):** 45 Minuten
- **Phase 2 (ClientDependencies):** 30 Minuten
- **Phase 4 (Model Layer):** 1 Stunde
- **Phase 6 (Doku):** 1 Stunde
- **Testing nach jeder Phase:** 3-4 Stunden total
- **Gesamt:** 20-24 Stunden

**Hinweis:**
- Search-Replace + mypy kann viele Fehler finden
- Aber manuelles Review ist KRITISCH, besonders bei Phase 1
- Tests müssen nach jeder Sub-Phase passing sein
- Phase 1 ist die zeitaufwändigste - nimm dir Zeit!

---

## Automatisierungs-Tipps

### Phase 1: Protocol-Suffix HINZUFÜGEN

**WICHTIG:** Manuelle Überprüfung für jedes Protocol notwendig!

```bash
# Schritt 1: Protocol-Definitionen umbenennen (VORSICHTIG!)
# Beispiel für ein einzelnes Protocol:
sed -i 's/class ClientProvider(Protocol)/class ClientProviderProtocol(Protocol)/g' aiohomematic/interfaces/client.py

# Schritt 2: Type Hints in allen Dateien aktualisieren
find aiohomematic -name "*.py" -exec sed -i 's/: ClientProvider/: ClientProviderProtocol/g' {} \;
find aiohomematic -name "*.py" -exec sed -i 's/\[ClientProvider\]/[ClientProviderProtocol]/g' {} \;

# Schritt 3: Imports aktualisieren
find aiohomematic -name "*.py" -exec sed -i 's/from .* import ClientProvider/from .* import ClientProviderProtocol/g' {} \;

# WICHTIG: Variablennamen bleiben UNVERÄNDERT!
# "client_provider" bleibt "client_provider"
# "config_provider" bleibt "config_provider"

# Danach IMMER:
mypy aiohomematic/
pytest tests/
```

**Empfohlene Reihenfolge für Phase 1:**

1. Ein Protocol nach dem anderen umbenennen
2. Nach jedem Protocol: `mypy` laufen lassen
3. Fehler beheben
4. Commit
5. Nächstes Protocol

**Script-Vorlage für ein Protocol:**

```bash
#!/bin/bash
# rename_protocol.sh <OldName> <NewName>

OLD=$1
NEW=$2

echo "Renaming Protocol: $OLD → $NEW"

# 1. Protocol Definition
find aiohomematic/interfaces -name "*.py" -exec sed -i "s/class $OLD(Protocol)/class $NEW(Protocol)/g" {} \;

# 2. Type Hints (nur Type-Annotationen, NICHT Variablennamen!)
find aiohomematic -name "*.py" -exec sed -i "s/: $OLD/: $NEW/g" {} \;
find aiohomematic -name "*.py" -exec sed -i "s/\[$OLD\]/[$NEW]/g" {} \;
find aiohomematic -name "*.py" -exec sed -i "s/\[$OLD,/[$NEW,/g" {} \;

# 3. Imports
find aiohomematic -name "*.py" -exec sed -i "s/import $OLD/import $NEW/g" {} \;
find aiohomematic -name "*.py" -exec sed -i "s/from \(.*\) import \(.*\)$OLD\(.*\)/from \1 import \2$NEW\3/g" {} \;

# 4. isinstance/issubclass
find aiohomematic -name "*.py" -exec sed -i "s/isinstance(\(.*\), $OLD)/isinstance(\1, $NEW)/g" {} \;

echo "Running mypy..."
mypy aiohomematic/

echo "Running tests..."
pytest tests/ -x
```

**WICHTIG:** Nach jedem automatischen Replace:
1. Git diff überprüfen
2. Mypy laufen lassen (zeigt Type-Errors)
3. Alle Tests laufen lassen
4. Manuell durch betroffene Dateien gehen

---

## Migration Guide für Downstream-Projekte (z.B. Home Assistant)

### Wichtigste Breaking Changes

1. **ALLE Protocol-Namen haben jetzt `-Protocol` Suffix:**

```python
# Alt:
from aiohomematic.interfaces.central import ConfigProvider, EventBusProvider
from aiohomematic.interfaces.client import ClientProvider

def some_function(config_provider: ConfigProvider) -> None:
    ...

# Neu:
from aiohomematic.interfaces.central import ConfigProviderProtocol, EventBusProviderProtocol
from aiohomematic.interfaces.client import ClientProviderProtocol

def some_function(config_provider: ConfigProviderProtocol) -> None:
    ...
```

**WICHTIG:** Variablennamen bleiben UNVERÄNDERT!
```python
# ✅ RICHTIG - Variablenname bleibt gleich:
config_provider: ConfigProviderProtocol  # Nur Type-Hint ändert sich

# ❌ FALSCH - Variablenname ändern:
config: ConfigProviderProtocol  # NICHT machen!
```

2. **Handler-Klassen umbenannt:**

```python
# Alt:
from aiohomematic.client.handlers.link_mgmt import LinkManagementHandler
from aiohomematic.client.handlers.device_ops import DeviceOperationsHandler

# Neu:
from aiohomematic.client.handlers.link_mgmt import LinkHandler
from aiohomematic.client.handlers.device_ops import DeviceHandler
```

### Search & Replace Patterns

```bash
# 1. Protocol-Namen in Type-Hints aktualisieren
s/: ClientProvider/: ClientProviderProtocol/g
s/: ConfigProvider/: ConfigProviderProtocol/g
s/: EventBusProvider/: EventBusProviderProtocol/g
s/: DeviceProvider/: DeviceProviderProtocol/g
# ... (für alle ~73 Protocols)

# 2. Handler-Namen aktualisieren
s/LinkManagementHandler/LinkHandler/g
s/DeviceOperationsHandler/DeviceHandler/g

# 3. Import-Statements aktualisieren
s/import ClientProvider/import ClientProviderProtocol/g
s/import ConfigProvider/import ConfigProviderProtocol/g
# ... etc

# WICHTIG: NICHT Variablennamen ändern!
# "client_provider" bleibt "client_provider"
# "config_provider" bleibt "config_provider"
```

---

## Anhang: Vollständige Protocol-Liste für Umbenennung

### Zentrale Protocols (aiohomematic/interfaces/central.py)

| Alt | Neu |
|-----|-----|
| CentralInfo | CentralInfoProtocol |
| CentralUnitStateProvider | CentralUnitStateProviderProtocol |
| ConfigProvider | ConfigProviderProtocol |
| SystemInfoProvider | SystemInfoProviderProtocol |
| BackupProvider | BackupProviderProtocol |
| DeviceManagement | DeviceManagementProtocol |
| EventBusProvider | EventBusProviderProtocol |
| EventPublisher | EventPublisherProtocol |
| DataPointProvider | DataPointProviderProtocol |
| DeviceProvider | DeviceProviderProtocol |
| ChannelLookup | ChannelLookupProtocol |
| FileOperations | FileOperationsProtocol |
| FirmwareDataRefresher | FirmwareDataRefresherProtocol |
| DeviceDataRefresher | DeviceDataRefresherProtocol |
| DataCacheProvider | DataCacheProviderProtocol |
| HubFetchOperations | HubFetchOperationsProtocol |
| HubDataFetcher | HubDataFetcherProtocol |
| HubDataPointManager | HubDataPointManagerProtocol |
| EventSubscriptionManager | EventSubscriptionManagerProtocol |
| RpcServerTaskScheduler | RpcServerTaskSchedulerProtocol |
| CentralStateMachineProvider | CentralStateMachineProviderProtocol |
| HealthProvider | HealthProviderProtocol |

*(Hinweis: RpcServerCentralProtocol, ConnectionHealthProtocol, CentralHealthProtocol, CentralStateMachineProtocol haben bereits das Suffix)*

### Client Protocols (aiohomematic/interfaces/client.py)

| Alt | Neu |
|-----|-----|
| DeviceDiscoveryOperations | DeviceDiscoveryOperationsProtocol |
| ParamsetOperations | ParamsetOperationsProtocol |
| ValueOperations | ValueOperationsProtocol |
| LinkOperations | LinkOperationsProtocol |
| FirmwareOperations | FirmwareOperationsProtocol |
| SystemVariableOperations | SystemVariableOperationsProtocol |
| ProgramOperations | ProgramOperationsProtocol |
| BackupOperations | BackupOperationsProtocol |
| MetadataOperations | MetadataOperationsProtocol |
| ClientProvider | ClientProviderProtocol |
| PrimaryClientProvider | PrimaryClientProviderProtocol |
| ConnectionStateProvider | ConnectionStateProviderProtocol |
| SessionRecorderProvider | SessionRecorderProviderProtocol |
| JsonRpcClientProvider | JsonRpcClientProviderProtocol |
| CallbackAddressProvider | CallbackAddressProviderProtocol |

*(Hinweis: ClientProtocol hat bereits das Suffix)*

### Operations Protocols (aiohomematic/interfaces/operations.py)

| Alt | Neu |
|-----|-----|
| TaskScheduler | TaskSchedulerProtocol |
| ParameterVisibilityProvider | ParameterVisibilityProviderProtocol |
| DeviceDetailsProvider | DeviceDetailsProviderProtocol |
| DeviceDescriptionProvider | DeviceDescriptionProviderProtocol |
| ParamsetDescriptionProvider | ParamsetDescriptionProviderProtocol |

### Model Protocols (aiohomematic/interfaces/model.py)

| Alt | Neu |
|-----|-----|
| ChannelIdentity | ChannelIdentityProtocol |
| ChannelDataPointAccess | ChannelDataPointAccessProtocol |
| ChannelGrouping | ChannelGroupingProtocol |
| ChannelMetadata | ChannelMetadataProtocol |
| ChannelLinkManagement | ChannelLinkManagementProtocol |
| ChannelLifecycle | ChannelLifecycleProtocol |
| DeviceIdentity | DeviceIdentityProtocol |
| DeviceChannelAccess | DeviceChannelAccessProtocol |
| DeviceAvailability | DeviceAvailabilityProtocol |
| DeviceFirmware | DeviceFirmwareProtocol |
| DeviceLinkManagement | DeviceLinkManagementProtocol |
| DeviceGroupManagement | DeviceGroupManagementProtocol |
| DeviceConfiguration | DeviceConfigurationProtocol |
| DeviceWeekProfile | DeviceWeekProfileProtocol |
| DeviceProviders | DeviceProvidersProtocol |
| DeviceLifecycle | DeviceLifecycleProtocol |

*(Hinweis: Viele DataPoint-, Channel-, Device-, Hub-, WeekProfile-Protocols haben bereits das Suffix)*

### Coordinator Protocols (aiohomematic/interfaces/coordinators.py)

| Alt | Neu |
|-----|-----|
| CoordinatorProvider | CoordinatorProviderProtocol |

---

**Ende des Refactoring-Plans**
