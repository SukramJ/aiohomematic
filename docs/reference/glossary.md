# Glossary

This glossary defines key terms used in the Homematic(IP) Local integration for Home Assistant. Understanding these terms helps in troubleshooting and communication.

---

## Home Assistant Ecosystem

### Integration

An integration is a component that connects Home Assistant to external services, devices, or platforms. Homematic(IP) Local is an **integration** that connects Home Assistant to Homematic devices via a CCU backend. Integrations are configured in Settings → Devices & Services.

### App (formerly Add-on)

An app is a self-contained application that runs alongside Home Assistant OS or Supervised installations. Apps are managed through Settings → Apps. Examples: OpenCCU App (runs the CCU software), File Editor, Terminal. **Apps are NOT the same as integrations** – OpenCCU App provides the backend, while Homematic(IP) Local is the integration that connects to it. (Note: "Add-on" was renamed to "App" in [Home Assistant 2026.2](https://www.home-assistant.io/blog/2026/02/04/release-20262/#add-ons-are-now-called-apps).)

### Plugin ⚠️

"Plugin" is **not an official Home Assistant term**. Please use "Integration" or "App" depending on what you mean. Using "Plugin" in bug reports causes confusion.

### HACS (Home Assistant Community Store)

HACS is a community-maintained store for custom integrations, themes, and frontend components. Homematic(IP) Local can be installed via HACS. **Important:** Updates installed via HACS must also be updated via HACS.

---

## Homematic Terms

### Backend

The central control unit that manages Homematic devices. This can be a CCU3, CCU2, OpenCCU, Debmatic, or Homegear installation. The backend communicates with devices via radio protocols and provides interfaces (XML-RPC, JSON-RPC) that the integration uses.

### CCU (Central Control Unit)

The official Homematic central unit hardware/software. CCU3 is the current model, CCU2 is the predecessor. OpenCCU, piVCCU/Debmatic are open-source alternatives running the same software.

### OpenCCU

Open-source implementation of the CCU software, typically run on Raspberry Pi or as a virtual machine. Can also run as a Home Assistant App.

### piVCCU / Debmatic

Open-source CCU implementations for Debian-based systems. piVCCU runs as a virtualized CCU, Debmatic runs natively on Debian/Ubuntu. Both use the official CCU firmware.

### Interface

A communication channel to a specific type of Homematic device. Common interfaces:

- **HmIP-RF:** Homematic IP devices (wireless)
- **BidCos-RF:** Classic Homematic devices (wireless)
- **HmIP-Wired / BidCos-Wired:** Wired Homematic devices
- **VirtualDevices / CUxD:** Virtual devices and USB device extensions
- **Groups:** Heating groups configured in the CCU

### Device

A physical or virtual Homematic device (e.g., thermostat, switch, sensor). Each device has a unique address and contains one or more channels.

### Channel

A logical unit within a device that groups related functionality. For example, a 2-gang switch has two switch channels. Channel 0 is typically the maintenance channel containing device-level information.

### Parameter

A named value on a channel that can be read, written, or both. Parameters are organized in paramsets (VALUES for runtime values, MASTER for configuration).

### Data Point (Entity)

The representation of a parameter in Home Assistant. Each parameter becomes an entity (sensor, switch, climate, etc.) that can be used in automations and dashboards.

### System Variable (Sysvar)

A variable stored on the CCU that can be used in CCU programs and accessed from Home Assistant. System variables appear as entities in the integration.

### Program

A script or automation stored on the CCU. Programs can be triggered from Home Assistant using the integration's services.

---

## Technical Terms

### XML-RPC / JSON-RPC

Communication protocols used to exchange data between Home Assistant and the CCU backend. XML-RPC is the traditional protocol, JSON-RPC is used for some operations like fetching system variables.

### Callback

A mechanism where the CCU sends events (value changes, alarms) back to Home Assistant. Requires proper network configuration so the CCU can reach Home Assistant.

### TLS (Transport Layer Security)

Encryption for communication between Home Assistant and the CCU. Can be enabled in the integration configuration for secure connections.

---

## Troubleshooting Terms

### Diagnostics

A downloadable file containing configuration and state information about the integration. Essential for bug reports. Download via Settings → Devices & Services → Homematic(IP) Local → 3 dots → Download Diagnostics.

### Protocol / Log

The Home Assistant log file containing messages from the integration. Found at Settings → System → Logs. **Important:** Only enable DEBUG logging when requested by developers.

---

## Quick Reference

| Term        | Correct Usage                       |
| ----------- | ----------------------------------- |
| ~~Plugin~~  | ❌ Don't use                        |
| Integration | ✅ Homematic(IP) Local integration  |
| App         | ✅ OpenCCU App                      |
| Backend     | ✅ CCU3, OpenCCU, etc.              |
| Entity      | ✅ Sensor, Switch in Home Assistant |
| Device      | ✅ Physical Homematic device        |
