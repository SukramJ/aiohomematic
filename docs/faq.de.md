---
translation_source: docs/faq.md
translation_date: 2026-04-01
translation_source_hash: c3cb478f6702
---

# Häufige Fragen

Diese Seite beantwortet häufig gestellte Fragen zu aiohomematic und der Homematic(IP) Local Integration für Home Assistant.

---

## Allgemeine Fragen

### Was ist aiohomematic?

aiohomematic ist eine moderne, async Python-Bibliothek zur Steuerung von Homematic- und HomematicIP-Geräten. Sie übernimmt die Low-Level-Kommunikation mit CCU/Homegear-Backends über XML-RPC- und JSON-RPC-Protokolle.

### Was ist der Unterschied zwischen aiohomematic und Homematic(IP) Local?

| Aspekt                      | aiohomematic                                            | Homematic(IP) Local                                               |
| --------------------------- | ------------------------------------------------------- | ----------------------------------------------------------------- |
| **Typ**                     | Python-Bibliothek                                       | Home Assistant Integration                                        |
| **Zweck**                   | Protokollimplementierung                                | HA Entity-Zuordnung                                               |
| **Eigenständig verwendbar** | Ja                                                      | Nein (erfordert HA)                                               |
| **Repository**              | [aiohomematic](https://github.com/sukramj/aiohomematic) | [homematicip_local](https://github.com/sukramj/homematicip_local) |

### Welche Backends werden unterstützt?

- CCU3 / CCU2
- OpenCCU (ehemals RaspberryMatic)
- piVCCU / Debmatic
- Homegear

### Was sind die Mindestanforderungen?

- **Python**: 3.14+ (für eigenständige Bibliotheksnutzung)
- **Home Assistant**: 2025.10.0+ (für die Integration)
- **CCU Firmware**: CCU2 ≥2.53.27, CCU3 ≥3.53.26 (für HomematicIP-Geräte)

---

## Installation & Konfiguration

### Wie installiere ich die Integration?

**Über HACS (empfohlen):**

1. HACS in Home Assistant öffnen
2. Nach "Homematic(IP) Local for OpenCCU" suchen
3. Installieren und Home Assistant neu starten
4. Integration hinzufügen über Einstellungen → Geräte & Dienste

**Manuell:**

1. `custom_components/homematicip_local` in das HA-Konfigurationsverzeichnis kopieren
2. Home Assistant neu starten

### Kann ich diese Integration neben der offiziellen Homematic-Integration verwenden?

Es gibt mehrere Homematic-bezogene Integrationen:

| Integration                                                                            | Typ         | Backend              | Status            |
| -------------------------------------------------------------------------------------- | ----------- | -------------------- | ----------------- |
| **[Homematic](https://www.home-assistant.io/integrations/homematic/)**                 | HA Core     | CCU (lokal)          | ⚠️ Nicht gepflegt |
| **[HomematicIP Cloud](https://www.home-assistant.io/integrations/homematicip_cloud/)** | HA Core     | Access Point (Cloud) | Aktiv             |
| **Homematic(IP) Local**                                                                | HACS Custom | CCU (lokal)          | ✅ Aktiv          |

**Warum wird die Homematic-Core-Integration nicht mehr gepflegt?**

Die offizielle Homematic-Integration basiert auf [pyhomematic](https://github.com/danielperna84/pyhomematic), das nicht mehr weiterentwickelt wird. aiohomematic ist der moderne Nachfolger von pyhomematic und bietet async-Unterstützung, bessere Typisierung und aktive Entwicklung. Da pyhomematic nicht mehr weiterentwickelt wird, gilt das auch für die Homematic-Core-Integration.

**Sollte ich Homematic oder Homematic(IP) Local verwenden?**

**Homematic(IP) Local** verwenden. Es bietet mehr Funktionen, unterstützt neuere Geräte und erhält regelmäßige Updates. Die gleichen Geräte sollten **nicht** gleichzeitig in beiden Integrationen konfiguriert werden.

### Warum benötigt die Integration Admin-Zugangsdaten?

Die CCU erfordert Administratorrechte für:

- Abrufen von Gerätekonfigurationen
- Lesen und Schreiben von Parametern
- Ausführen von Programmen
- Verwalten von Systemvariablen

### Welche Passwortzeichen sind erlaubt?

Nur diese Zeichen werden unterstützt: `A-Z`, `a-z`, `0-9`, `.!$():;#-`

Sonderzeichen wie `ÄäÖöÜüß` funktionieren in der CCU-Weboberfläche, aber **nicht** über XML-RPC.

---

## Geräte & Entities

### Warum sind einige Entities standardmäßig deaktiviert?

Viele Parameter existieren auf Geräten, werden aber selten benötigt (Diagnosewerte, interne Zähler usw.). Um die Oberfläche übersichtlich zu halten, werden diese als deaktivierte Entities angelegt. Aktivierung über:

1. Einstellungen → Entities
2. Deaktivierte Entities anzeigen
3. Die gewünschte Entity finden und aktivieren

### Entity zeigt "nicht verfügbar" - was nun?

Häufige Ursachen:

1. **Entity ist deaktiviert** → In den Entity-Einstellungen aktivieren
2. **Gerät offline** → Batterie/Stromversorgung und Funkreichweite des Geräts prüfen
3. **Schnittstelle nicht aktiviert** → Prüfen, ob die richtige Schnittstelle (HmIP-RF, BidCos-RF) aktiviert ist
4. **Verbindung unterbrochen** → Integrationsstatus und Logs prüfen

### Neues Gerät erscheint nicht in Home Assistant?

1. Sicherstellen, dass das Gerät in der CCU-Weboberfläche erfolgreich angelernt ist
2. **Einstellungen → System → Reparaturen** auf Gerätebenachrichtigungen prüfen
3. Die Integration neu laden
4. Logs auf Fehler prüfen

### Wie benenne ich ein Gerät um?

| Ziel                         | Methode                                             |
| ---------------------------- | --------------------------------------------------- |
| Name nur in HA ändern        | Einstellungen → Geräte → Name bearbeiten            |
| Name von CCU synchronisieren | In CCU umbenennen → Integration neu laden           |
| Auch Entity-ID ändern        | Gerät in HA löschen → In CCU umbenennen → Neu laden |

### Warum lösen Tastendrücke keine Automations aus?

**Für HomematicIP-Fernbedienungen (WRC2, WRC6, usw.):**

Zuerst müssen zentrale Verknüpfungen erstellt werden:

```yaml
action: homematicip_local.create_central_links
target:
  device_id: YOUR_DEVICE_ID
```

**Für klassische Homematic-Tasten:**

Sollte automatisch funktionieren. Falls nicht, prüfen, ob das Gerät korrekt angelernt ist.

---

## Systemvariablen & Programme

### Warum sehe ich nur wenige Systemvariablen?

Systemvariablen werden standardmäßig als **deaktivierte** Entities importiert. Um alle zu sehen:

1. Einstellungen → Entities
2. "Deaktivierte Entities anzeigen" aktivieren
3. Die gewünschten Variablen aktivieren

Oder Markierungen verwenden (`HAHM` zur Variablenbeschreibung in der CCU hinzufügen), um sie automatisch zu aktivieren.

### Wie mache ich eine Systemvariable beschreibbar?

`HAHM` zum Beschreibungsfeld der Variable in der CCU hinzufügen:

1. In der CCU die Systemvariable bearbeiten
2. Im Feld "Beschreibung" `HAHM` (Großbuchstaben) eintragen
3. Speichern und die Integration neu laden

Der Entity-Typ ändert sich von `sensor` (schreibgeschützt) zu editierbar (`number`, `select`, `text` oder `switch`).

### Wie starte ich ein CCU-Programm aus Home Assistant?

Programme erscheinen als Button-Entities. Die Taste drücken oder in einer Automation verwenden:

```yaml
action: button.press
target:
  entity_id: button.my_program
```

---

## Verbindung & Netzwerk

### Welche Ports müssen geöffnet sein?

| Schnittstelle   | Port | TLS-Port |
| --------------- | ---- | -------- |
| HmIP-RF         | 2010 | 42010    |
| BidCos-RF       | 2001 | 42001    |
| BidCos-Wired    | 2000 | 42000    |
| Virtual Devices | 9292 | 49292    |
| JSON-RPC        | 80   | 443      |

Zusätzlich: Die CCU muss Home Assistant auf dem Callback-Port erreichen können.

### Docker: Ereignisse werden nicht empfangen?

Die CCU muss Home Assistant auf dem Callback-Port erreichen können. In Docker ist die interne IP des Containers standardmäßig nicht von der CCU erreichbar.

**Option A: Host-Netzwerk (einfachste Lösung)**

`network_mode: host` in der Docker-Compose-Datei setzen. Dadurch teilt sich der Container den Netzwerk-Stack des Hosts, sodass die CCU den Callback-Port direkt erreichen kann.

```yaml
services:
  homeassistant:
    # ...
    network_mode: host
```

**Option B: callback_host manuell konfigurieren**

Falls Host-Netzwerk nicht möglich ist, `callback_host` auf die IP des Docker-Hosts (nicht die Container-IP) in den erweiterten Optionen der Integration setzen und sicherstellen, dass der Callback-Port vom Host zum Container weitergeleitet wird.

1. Docker-Host-IP ermitteln:

   ```bash
   ip route | grep default
   ```

   Die angezeigte Gateway-Adresse ist typischerweise die IP des Hosts im lokalen Netzwerk.

2. In Home Assistant zu Einstellungen → Geräte & Dienste → Homematic(IP) Local → Konfigurieren gehen
3. **Callback Host** auf die Docker-Host-IP setzen (z.B. `192.168.1.10`)
4. **Callback Port (XML-RPC)** setzen, falls der Standard nicht weitergeleitet wird
5. Sicherstellen, dass der Callback-Port in Docker Compose weitergeleitet wird:

   ```yaml
   ports:
     - "2010:2010" # Beispiel für HmIP-RF Callback
   ```

### Wie aktiviere ich TLS?

1. Zuerst TLS auf der CCU aktivieren
2. In der Integrationskonfiguration "TLS verwenden" aktivieren
3. "TLS verifizieren" auf `false` setzen für selbstsignierte Zertifikate

---

## CUxD & CCU-Jack

### Wie erhalten CUxD/CCU-Jack-Geräte Updates?

Standardmäßig: JSON-RPC-Polling alle 15 Sekunden.

Für sofortige Updates: MQTT in den erweiterten Optionen aktivieren (erfordert CCU-Jack mit konfigurierter MQTT-Bridge).

### Warum verhält sich mein CUxD-Gerät anders?

CUxD- und CCU-Jack-Geräte können sich geringfügig anders verhalten als originale Homematic-Hardware. Dies wird **nicht als Fehler** in der Integration betrachtet. Bei Bedarf Home Assistant Templates zur Anpassung verwenden.

---

## Bibliotheksnutzung (Entwickler)

### Wie verwende ich aiohomematic eigenständig?

```python
from aiohomematic.api import HomematicAPI

async with HomematicAPI.connect(
    host="192.168.1.100",
    username="Admin",
    password="secret",
) as api:
    for device in api.list_devices():
        print(f"{device.name}: {device.model}")
```

### Wie abonniere ich Ereignisse?

```python
from aiohomematic.central.events import DataPointValueReceivedEvent

async def on_update(*, event: DataPointValueReceivedEvent) -> None:
    print(f"{event.dpk}: {event.value}")

unsubscribe = central.event_bus.subscribe(
    event_type=DataPointValueReceivedEvent,
    event_key=None,
    handler=on_update,
)

# Später: unsubscribe()
```

### Wie füge ich Unterstützung für ein neues Gerät hinzu?

Siehe die Dokumentation zu den [Erweiterungspunkten](developer/extension_points.md) für detaillierte Anweisungen zur Registrierung von Geräteprofilen.

---

## Fehlerbehebung

### Wo finde ich Logs?

**Home Assistant:**

Einstellungen → System → Logs → Nach `homematicip_local` oder `aiohomematic` filtern

**Debug-Logging aktivieren:**

```yaml
# configuration.yaml
logger:
  logs:
    aiohomematic: debug
    custom_components.homematicip_local: debug
```

### Wie lade ich Diagnosedaten herunter?

1. Einstellungen → Geräte & Dienste
2. Homematic(IP) Local finden
3. Drei Punkte anklicken → Diagnose herunterladen

Diagnosedaten immer anhängen, wenn Probleme gemeldet werden.

### Wo melde ich Fehler?

- **Bibliotheksprobleme (aiohomematic):** [aiohomematic Issues](https://github.com/sukramj/aiohomematic/issues)
- **Integrationsprobleme (Homematic(IP) Local):** Gleiches Repository
- **Diskussionen/Fragen:** [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions)

---

## Siehe auch

- [Fehlerbehebung](troubleshooting/index.md)
- [Erste Schritte](getting_started.md)
- [Benutzerhandbuch](user/homeassistant_integration.md)
- [Glossar](reference/glossary.md)
