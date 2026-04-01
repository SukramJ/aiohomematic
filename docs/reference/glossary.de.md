---
translation_source: docs/reference/glossary.md
translation_date: 2026-04-01
---

# Glossar

Dieses Glossar definiert wichtige Begriffe, die in der Homematic(IP) Local Integration für Home Assistant verwendet werden. Das Verständnis dieser Begriffe hilft bei der Fehlerbehebung und Kommunikation.

---

## Home Assistant Ökosystem

### Integration

Eine Integration ist eine Komponente, die Home Assistant mit externen Diensten, Geräten oder Plattformen verbindet. Homematic(IP) Local ist eine **Integration**, die Home Assistant über ein CCU-Backend mit Homematic-Geräten verbindet. Integrationen werden unter Einstellungen → Geräte & Dienste konfiguriert.

### App (ehemals Add-on)

Eine App ist eine eigenständige Anwendung, die neben Home Assistant OS oder Supervised-Installationen läuft. Apps werden über Einstellungen → Apps verwaltet. Beispiele: OpenCCU App (führt die CCU-Software aus), Datei-Editor, Terminal. **Apps sind NICHT dasselbe wie Integrationen** – die OpenCCU App stellt das Backend bereit, während Homematic(IP) Local die Integration ist, die sich damit verbindet. (Hinweis: „Add-on" wurde in [Home Assistant 2026.2](https://www.home-assistant.io/blog/2026/02/04/release-20262/#add-ons-are-now-called-apps) in „App" umbenannt.)

### Plugin ⚠️

„Plugin" ist **kein offizieller Home Assistant Begriff**. Bitte verwende „Integration" oder „App" je nach Bedeutung. Die Verwendung von „Plugin" in Fehlerberichten führt zu Verwirrung.

### HACS (Home Assistant Community Store)

HACS ist ein von der Community gepflegter Store für benutzerdefinierte Integrationen, Themes und Frontend-Komponenten. Homematic(IP) Local kann über HACS installiert werden. **Wichtig:** Über HACS installierte Updates müssen auch über HACS aktualisiert werden.

---

## Homematic Begriffe

### Backend

Die zentrale Steuereinheit, die Homematic-Geräte verwaltet. Dies kann eine CCU3, CCU2, OpenCCU, Debmatic oder Homegear-Installation sein. Das Backend kommuniziert über Funkprotokolle mit Geräten und stellt Schnittstellen (XML-RPC, JSON-RPC) bereit, die die Integration nutzt.

### CCU (Central Control Unit)

Die offizielle Homematic Zentraleinheit (Hardware/Software). CCU3 ist das aktuelle Modell, CCU2 der Vorgänger. OpenCCU, piVCCU/Debmatic sind Open-Source-Alternativen, die dieselbe Software ausführen.

### OpenCCU

Open-Source-Implementierung der CCU-Software, die typischerweise auf Raspberry Pi oder als virtuelle Maschine läuft. Kann auch als Home Assistant App ausgeführt werden.

### piVCCU / Debmatic

Open-Source CCU-Implementierungen für Debian-basierte Systeme. piVCCU läuft als virtualisierte CCU, Debmatic läuft nativ auf Debian/Ubuntu. Beide verwenden die offizielle CCU-Firmware.

### Schnittstelle (Interface)

Ein Kommunikationskanal zu einem bestimmten Typ von Homematic-Geräten. Gängige Schnittstellen:

- **HmIP-RF:** Homematic IP Geräte (Funk)
- **BidCos-RF:** Klassische Homematic Geräte (Funk)
- **HmIP-Wired / BidCos-Wired:** Kabelgebundene Homematic Geräte
- **VirtualDevices / CUxD:** Virtuelle Geräte und USB-Geräteerweiterungen
- **Groups:** In der CCU konfigurierte Heizungsgruppen

### Gerät (Device)

Ein physisches oder virtuelles Homematic-Gerät (z.B. Thermostat, Schalter, Sensor). Jedes Gerät hat eine eindeutige Adresse und enthält einen oder mehrere Kanäle.

### Kanal (Channel)

Eine logische Einheit innerhalb eines Geräts, die zusammengehörige Funktionen gruppiert. Beispielsweise hat ein 2-fach-Schalter zwei Schaltkanäle. Kanal 0 ist typischerweise der Wartungskanal mit gerätebezogenen Informationen.

### Parameter

Ein benannter Wert auf einem Kanal, der gelesen, geschrieben oder beides werden kann. Parameter sind in Parametersets organisiert (VALUES für Laufzeitwerte, MASTER für Konfiguration).

### Datenpunkt (Data Point / Entität)

Die Darstellung eines Parameters in Home Assistant. Jeder Parameter wird zu einer Entität (Sensor, Schalter, Klima, etc.), die in Automatisierungen und Dashboards verwendet werden kann.

### Systemvariable (Sysvar)

Eine Variable, die auf der CCU gespeichert ist und in CCU-Programmen verwendet sowie von Home Assistant aus zugegriffen werden kann. Systemvariablen erscheinen als Entitäten in der Integration.

### Programm

Ein Skript oder eine Automatisierung, die auf der CCU gespeichert ist. Programme können von Home Assistant aus über die Dienste der Integration ausgelöst werden.

---

## Technische Begriffe

### XML-RPC / JSON-RPC

Kommunikationsprotokolle zum Datenaustausch zwischen Home Assistant und dem CCU-Backend. XML-RPC ist das traditionelle Protokoll, JSON-RPC wird für einige Operationen wie das Abrufen von Systemvariablen verwendet.

### Callback

Ein Mechanismus, bei dem die CCU Ereignisse (Wertänderungen, Alarme) an Home Assistant zurücksendet. Erfordert eine korrekte Netzwerkkonfiguration, damit die CCU Home Assistant erreichen kann.

### TLS (Transport Layer Security)

Verschlüsselung für die Kommunikation zwischen Home Assistant und der CCU. Kann in der Integrationskonfiguration für sichere Verbindungen aktiviert werden.

---

## Fehlerbehebung

### Diagnose (Diagnostics)

Eine herunterladbare Datei mit Konfigurations- und Statusinformationen über die Integration. Unverzichtbar für Fehlerberichte. Download über Einstellungen → Geräte & Dienste → Homematic(IP) Local → 3 Punkte → Diagnose herunterladen.

### Protokoll (Log)

Die Home Assistant Protokolldatei mit Nachrichten der Integration. Zu finden unter Einstellungen → System → Protokolle. **Wichtig:** DEBUG-Protokollierung nur aktivieren, wenn von Entwicklern angefordert.

---

## Kurzreferenz

| Begriff     | Korrekte Verwendung                   |
| ----------- | ------------------------------------- |
| ~~Plugin~~  | ❌ Nicht verwenden                    |
| Integration | ✅ Homematic(IP) Local Integration    |
| App         | ✅ OpenCCU App                        |
| Backend     | ✅ CCU3, OpenCCU, etc.                |
| Entität     | ✅ Sensor, Schalter in Home Assistant |
| Gerät       | ✅ Physisches Homematic-Gerät         |
