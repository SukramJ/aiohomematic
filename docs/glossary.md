# Glossary / Glossar

This glossary defines key terms used in the Homematic(IP) Local integration for Home Assistant. Understanding these terms helps in troubleshooting and communication.

Dieses Glossar definiert wichtige Begriffe, die in der Homematic(IP) Local Integration für Home Assistant verwendet werden. Das Verständnis dieser Begriffe hilft bei der Fehlerbehebung und Kommunikation.

---

## Home Assistant Ecosystem Terms / Home Assistant Ökosystem Begriffe

### Integration

**EN:** An integration is a component that connects Home Assistant to external services, devices, or platforms. Homematic(IP) Local is an **integration** that connects Home Assistant to Homematic devices via a CCU backend. Integrations are configured in Settings → Devices & Services.

**DE:** Eine Integration ist eine Komponente, die Home Assistant mit externen Diensten, Geräten oder Plattformen verbindet. Homematic(IP) Local ist eine **Integration**, die Home Assistant über ein CCU-Backend mit Homematic-Geräten verbindet. Integrationen werden unter Einstellungen → Geräte & Dienste konfiguriert.

### Add-on

**EN:** An add-on is a self-contained application that runs alongside Home Assistant OS or Supervised installations. Add-ons are managed through Settings → Add-ons. Examples: OpenCCU Add-on (runs the CCU software), File Editor, Terminal. **Add-ons are NOT the same as integrations** – OpenCCU Add-on provides the backend, while Homematic(IP) Local is the integration that connects to it.

**DE:** Ein Add-on ist eine eigenständige Anwendung, die neben Home Assistant OS oder Supervised-Installationen läuft. Add-ons werden über Einstellungen → Add-ons verwaltet. Beispiele: OpenCCU Add-on (führt die CCU-Software aus), Datei-Editor, Terminal. **Add-ons sind NICHT dasselbe wie Integrationen** – das OpenCCU Add-on stellt das Backend bereit, während Homematic(IP) Local die Integration ist, die sich damit verbindet.

### Plugin ⚠️

**EN:** "Plugin" is **not an official Home Assistant term**. Please use "Integration" or "Add-on" depending on what you mean. Using "Plugin" in bug reports causes confusion.

**DE:** "Plugin" ist **kein offizieller Home Assistant Begriff**. Bitte verwende "Integration" oder "Add-on" je nach Bedeutung. Die Verwendung von "Plugin" in Fehlerberichten führt zu Verwirrung.

### HACS (Home Assistant Community Store)

**EN:** HACS is a community-maintained store for custom integrations, themes, and frontend components. Homematic(IP) Local can be installed via HACS. **Important:** Updates installed via HACS must also be updated via HACS.

**DE:** HACS ist ein von der Community gepflegter Store für benutzerdefinierte Integrationen, Themes und Frontend-Komponenten. Homematic(IP) Local kann über HACS installiert werden. **Wichtig:** Über HACS installierte Updates müssen auch über HACS aktualisiert werden.

---

## Homematic Terms / Homematic Begriffe

### Backend

**EN:** The central control unit that manages Homematic devices. This can be a CCU3, CCU2, OpenCCU, Debmatic, or Homegear installation. The backend communicates with devices via radio protocols and provides interfaces (XML-RPC, JSON-RPC) that the integration uses.

**DE:** Die zentrale Steuereinheit, die Homematic-Geräte verwaltet. Dies kann eine CCU3, CCU2, OpenCCU, Debmatic oder Homegear-Installation sein. Das Backend kommuniziert über Funkprotokolle mit Geräten und stellt Schnittstellen (XML-RPC, JSON-RPC) bereit, die die Integration nutzt.

### CCU (Central Control Unit)

**EN:** The official Homematic central unit hardware/software. CCU3 is the current model, CCU2 is the predecessor. OpenCCU, piVCCU/Debmatic are open-source alternatives running the same software.

**DE:** Die offizielle Homematic Zentraleinheit (Hardware/Software). CCU3 ist das aktuelle Modell, CCU2 der Vorgänger. OpenCCU, piVCCU/Debmatic sind Open-Source-Alternativen, die dieselbe Software ausführen.

### OpenCCU

**EN:** Open-source implementation of the CCU software, typically run on Raspberry Pi or as a virtual machine. Can also run as a Home Assistant Add-on.

**DE:** Open-Source-Implementierung der CCU-Software, die typischerweise auf Raspberry Pi oder als virtuelle Maschine läuft. Kann auch als Home Assistant Add-on ausgeführt werden.

### piVCCU / Debmatic

**EN:** Open-source CCU implementations for Debian-based systems. piVCCU runs as a virtualized CCU, Debmatic runs natively on Debian/Ubuntu. Both use the official CCU firmware.

**DE:** Open-Source CCU-Implementierungen für Debian-basierte Systeme. piVCCU läuft als virtualisierte CCU, Debmatic läuft nativ auf Debian/Ubuntu. Beide verwenden die offizielle CCU-Firmware.

### Interface

**EN:** A communication channel to a specific type of Homematic device. Common interfaces:

- **HmIP-RF:** Homematic IP devices (wireless)
- **BidCos-RF:** Classic Homematic devices (wireless)
- **HmIP-Wired / BidCos-Wired:** Wired Homematic devices
- **VirtualDevices / CUxD:** Virtual devices and USB device extensions
- **Groups:** Heating groups configured in the CCU

**DE:** Ein Kommunikationskanal zu einem bestimmten Typ von Homematic-Geräten. Gängige Schnittstellen:

- **HmIP-RF:** Homematic IP Geräte (Funk)
- **BidCos-RF:** Klassische Homematic Geräte (Funk)
- **HmIP-Wired / BidCos-Wired:** Kabelgebundene Homematic Geräte
- **VirtualDevices / CUxD:** Virtuelle Geräte und USB-Geräteerweiterungen
- **Groups:** In der CCU konfigurierte Heizungsgruppen

### Device

**EN:** A physical or virtual Homematic device (e.g., thermostat, switch, sensor). Each device has a unique address and contains one or more channels.

**DE:** Ein physisches oder virtuelles Homematic-Gerät (z.B. Thermostat, Schalter, Sensor). Jedes Gerät hat eine eindeutige Adresse und enthält einen oder mehrere Kanäle.

### Channel

**EN:** A logical unit within a device that groups related functionality. For example, a 2-gang switch has two switch channels. Channel 0 is typically the maintenance channel containing device-level information.

**DE:** Eine logische Einheit innerhalb eines Geräts, die zusammengehörige Funktionen gruppiert. Beispielsweise hat ein 2-fach-Schalter zwei Schaltkanäle. Kanal 0 ist typischerweise der Wartungskanal mit gerätebezogenen Informationen.

### Parameter

**EN:** A named value on a channel that can be read, written, or both. Parameters are organized in paramsets (VALUES for runtime values, MASTER for configuration).

**DE:** Ein benannter Wert auf einem Kanal, der gelesen, geschrieben oder beides werden kann. Parameter sind in Parametersets organisiert (VALUES für Laufzeitwerte, MASTER für Konfiguration).

### Data Point (Entity)

**EN:** The representation of a parameter in Home Assistant. Each parameter becomes an entity (sensor, switch, climate, etc.) that can be used in automations and dashboards.

**DE:** Die Darstellung eines Parameters in Home Assistant. Jeder Parameter wird zu einer Entität (Sensor, Schalter, Klima, etc.), die in Automatisierungen und Dashboards verwendet werden kann.

### System Variable (Sysvar)

**EN:** A variable stored on the CCU that can be used in CCU programs and accessed from Home Assistant. System variables appear as entities in the integration.

**DE:** Eine Variable, die auf der CCU gespeichert ist und in CCU-Programmen verwendet sowie von Home Assistant aus zugegriffen werden kann. Systemvariablen erscheinen als Entitäten in der Integration.

### Program

**EN:** A script or automation stored on the CCU. Programs can be triggered from Home Assistant using the integration's services.

**DE:** Ein Skript oder eine Automatisierung, die auf der CCU gespeichert ist. Programme können von Home Assistant aus über die Dienste der Integration ausgelöst werden.

---

## Technical Terms / Technische Begriffe

### XML-RPC / JSON-RPC

**EN:** Communication protocols used to exchange data between Home Assistant and the CCU backend. XML-RPC is the traditional protocol, JSON-RPC is used for some operations like fetching system variables.

**DE:** Kommunikationsprotokolle zum Datenaustausch zwischen Home Assistant und dem CCU-Backend. XML-RPC ist das traditionelle Protokoll, JSON-RPC wird für einige Operationen wie das Abrufen von Systemvariablen verwendet.

### Callback

**EN:** A mechanism where the CCU sends events (value changes, alarms) back to Home Assistant. Requires proper network configuration so the CCU can reach Home Assistant.

**DE:** Ein Mechanismus, bei dem die CCU Ereignisse (Wertänderungen, Alarme) an Home Assistant zurücksendet. Erfordert eine korrekte Netzwerkkonfiguration, damit die CCU Home Assistant erreichen kann.

### TLS (Transport Layer Security)

**EN:** Encryption for communication between Home Assistant and the CCU. Can be enabled in the integration configuration for secure connections.

**DE:** Verschlüsselung für die Kommunikation zwischen Home Assistant und der CCU. Kann in der Integrationskonfiguration für sichere Verbindungen aktiviert werden.

---

## Troubleshooting Terms / Fehlerbehebungs-Begriffe

### Diagnostics

**EN:** A downloadable file containing configuration and state information about the integration. Essential for bug reports. Download via Settings → Devices & Services → Homematic(IP) Local → 3 dots → Download Diagnostics.

**DE:** Eine herunterladbare Datei mit Konfigurations- und Statusinformationen über die Integration. Unverzichtbar für Fehlerberichte. Download über Einstellungen → Geräte & Dienste → Homematic(IP) Local → 3 Punkte → Diagnose herunterladen.

### Protocol / Log

**EN:** The Home Assistant log file containing messages from the integration. Found at Settings → System → Logs. **Important:** Only enable DEBUG logging when requested by developers.

**DE:** Die Home Assistant Protokolldatei mit Nachrichten der Integration. Zu finden unter Einstellungen → System → Protokolle. **Wichtig:** DEBUG-Protokollierung nur aktivieren, wenn von Entwicklern angefordert.

---

## Quick Reference / Kurzreferenz

| Term / Begriff | Correct Usage / Korrekte Verwendung |
| -------------- | ----------------------------------- |
| ~~Plugin~~     | ❌ Don't use / Nicht verwenden      |
| Integration    | ✅ Homematic(IP) Local integration  |
| Add-on         | ✅ OpenCCU Add-on                   |
| Backend        | ✅ CCU3, OpenCCU, etc.              |
| Entity         | ✅ Sensor, Switch in Home Assistant |
| Device         | ✅ Physical Homematic device        |
