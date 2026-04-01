---
translation_source: docs/user/advanced/security.md
translation_date: 2026-04-01
translation_source_hash: ac73bbffae1e
---

# Bewertete Sicherheitspraktiken

Diese Anleitung behandelt Sicherheitsaspekte fuer aiohomematic und die Homematic(IP) Local Integration.

## Uebersicht

aiohomematic kommuniziert mit dem Homematic-Backend (CCU/Homegear) ueber XML-RPC- und JSON-RPC-Protokolle. Die Absicherung dieser Kommunikation schuetzt das Smart Home vor unautorisiertem Zugriff.

!!! warning "Backend-Sicherheit ist entscheidend"
CCU, OpenCCU (RaspberryMatic) und Homegear hatten in der Vergangenheit **schwerwiegende Sicherheitsluecken**, einschliesslich nicht authentifizierter Remote-Code-Ausfuehrung. **Das Backend niemals dem Internet aussetzen** und die Firmware stets aktuell halten.

## Bekannte Backend-Schwachstellen

### Kritisch: Niemals dem Internet aussetzen

Homematic-Backends (CCU2, CCU3, OpenCCU, Homegear) sind **nicht fuer den Internetzugang konzipiert**. Historische Schwachstellen umfassen:

| Jahr | Betroffen               | Problem                                                                                                                                                        | Schweregrad |
| ---- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| 2024 | RaspberryMatic <=3.73.9 | [Nicht authentifizierte RCE ueber ZipSlip](https://mogwailabs.de/en/advisories/mlsa-2024-001/)                                                                 | Kritisch    |
| 2020 | CCU2/CCU3 WebUI         | [Nicht authentifizierte RCE als Root](https://www.cvedetails.com/vulnerability-list/vendor_id-17729/product_id-58075/opec-1/Eq-3-Homematic-Ccu3-Firmware.html) | Kritisch    |
| 2019 | CCU3                    | [Local File Inclusion (CVE-2019-9726)](https://pentest-tools.com/vulnerabilities-exploits/homematic-ccu3-local-file-inclusion_2766)                            | Hoch        |
| 2019 | CCU2/CCU3 + XML-API     | Nicht authentifizierte RCE ueber exec.cgi                                                                                                                      | Kritisch    |
| 2019 | CCU2/CCU3               | Session-Fixierung, Passwort-Hash-Offenlegung                                                                                                                   | Hoch        |
| 2019 | CCU2/CCU3 + CUxD        | Admin-Operationen ohne Authentifizierung                                                                                                                       | Kritisch    |

### Erforderliche Massnahmen

1. **Firmware aktuell halten** - Sicherheitspatches sofort installieren
2. **CCU-Ports niemals per Portweiterleitung freigeben** - VPN fuer Fernzugriff verwenden
3. **In separatem VLAN isolieren** - Auswirkungsradius einer moeglichen Kompromittierung begrenzen
4. **Authentifizierung aktivieren** - Auch im internen Netzwerk
5. **Nicht verwendete Add-ons entfernen** - XML-API und CUxD hatten Schwachstellen

### Version pruefen

**CCU/OpenCCU:**

1. CCU WebUI -> Einstellungen -> Systemsteuerung -> System
2. Firmware-Version pruefen
3. Mit dem [neuesten OpenCCU-Release](https://github.com/OpenCCU/OpenCCU/releases) vergleichen

**Homegear:**

```bash
homegear -v
```

### Sicherheitshinweise

Diese Quellen auf neue Schwachstellen ueberwachen:

- [OpenCCU Security Advisories](https://github.com/OpenCCU/OpenCCU/security/advisories)
- [eQ-3 CVE-Liste](https://www.cvedetails.com/vulnerability-list/vendor_id-17729/Eq-3.html)
- [Homegear GitHub](https://github.com/Homegear/Homegear)

## Authentifizierung

### CCU-Authentifizierung

**Immer die Authentifizierung** auf der CCU aktivieren:

1. CCU WebUI -> **Einstellungen** -> **Systemsteuerung** -> **Sicherheit**
2. **Authentifizierung** aktivieren
3. Einen dedizierten Benutzer fuer Home Assistant erstellen

### Benutzeranforderungen

| Anforderung        | Details                                                                   |
| ------------------ | ------------------------------------------------------------------------- |
| **Berechtigungen** | Administratorrolle erforderlich                                           |
| **Benutzername**   | Gross-/Kleinschreibung beachten, exakt wie in der CCU angegeben verwenden |
| **Passwort**       | Siehe erlaubte Zeichen unten                                              |

### Passwortanforderungen

Nur diese Zeichen werden in Passwoertern unterstuetzt:

```
A-Z  a-z  0-9  . ! $ ( ) : ; # -
```

**Nicht unterstuetzt:**

- Umlaute: `Ae ae Oe oe Ue ue ss`
- Andere Sonderzeichen: `@ & * % ^ ~`
- Unicode-Zeichen

Diese funktionieren in der CCU WebUI, **schlagen aber** ueber XML-RPC fehl.

## TLS-Konfiguration

### TLS aktivieren

1. **TLS zuerst auf der CCU aktivieren:**

   - CCU WebUI -> Einstellungen -> Systemsteuerung -> Sicherheit
   - HTTPS aktivieren

2. **Integration konfigurieren:**
   - "TLS verwenden" in den Integrationseinstellungen aktivieren
   - "TLS verifizieren" basierend auf dem Zertifikatstyp setzen

### Zertifikatstypen

| Zertifikatstyp            | TLS-Verifizierung | Hinweise                                           |
| ------------------------- | ----------------- | -------------------------------------------------- |
| Selbstsigniert (Standard) | `false`           | CCU-Standard, keine Kettenverifizierung            |
| Let's Encrypt             | `true`            | Gueltige Kette, vollstaendige Verifizierung        |
| Benutzerdefinierte CA     | `true`            | CA muss zum System-Trust-Store hinzugefuegt werden |

### TLS-Ports

| Schnittstelle   | Unverschluesselter Port | TLS-Port |
| --------------- | ----------------------- | -------- |
| HmIP-RF         | 2010                    | 42010    |
| BidCos-RF       | 2001                    | 42001    |
| BidCos-Wired    | 2000                    | 42000    |
| Virtual Devices | 9292                    | 49292    |
| JSON-RPC        | 80                      | 443      |

## Netzwerksicherheit

### Firewall-Konfiguration

**Eingehend zur CCU** (von Home Assistant):

| Port       | Protokoll | Dienst                                    |
| ---------- | --------- | ----------------------------------------- |
| 80/443     | TCP       | JSON-RPC (Namen, Raeume, Systemvariablen) |
| 2001/42001 | TCP       | BidCos-RF                                 |
| 2010/42010 | TCP       | HmIP-RF                                   |
| 2000/42000 | TCP       | BidCos-Wired (falls verwendet)            |
| 9292/49292 | TCP       | Virtual Devices (falls verwendet)         |

**Eingehend zu Home Assistant** (von CCU):

| Port          | Protokoll | Dienst                             |
| ------------- | --------- | ---------------------------------- |
| Callback-Port | TCP       | XML-RPC Callbacks (konfigurierbar) |

### Netzwerksegmentierung

Empfohlene Netzwerkarchitektur:

```
Internet
    |
    v
+-----------------+
|  Router/FW      |  <- Kein eingehender Verkehr aus dem Internet
+--------+--------+
         |
    +----+----+
    |         |
    v         v
+-------+  +-------+
|  IoT  |  | Haupt-|
| VLAN  |  |  LAN  |
|       |  |       |
| CCU   |  |  HA   |  <- Nur CCU <-> HA erlauben
|       |  |       |
+-------+  +-------+
```

### Docker-Sicherheit

Fuer Docker-Installationen:

**Empfohlen:** `network_mode: host` verwenden

**Alternative (Bridge-Netzwerk):**

1. `callback_host` auf die Docker-Host-IP setzen
2. Nur den Callback-Port freigeben (nicht alle CCU-Ports)
3. Wo moeglich internes Docker-Netzwerk verwenden

```yaml
services:
  homeassistant:
    network_mode: host # Empfohlen fuer Callback-Unterstuetzung
    # ODER mit Bridge:
    ports:
      - "8123:8123" # HA UI
      - "43439:43439" # Nur Callback-Port
```

## Verwaltung von Zugangsdaten

### Zugangsdaten niemals committen

Von der Versionskontrolle ausschliessen:

```gitignore
# .gitignore
*.env
secrets.yaml
credentials.json
```

### Home Assistant Secrets

`secrets.yaml` verwenden:

```yaml
# secrets.yaml (nicht in der Versionskontrolle)
ccu_password: your-secure-password

# configuration.yaml
homematic:
  password: !secret ccu_password
```

### Umgebungsvariablen

Fuer die eigenstaendige Bibliotheksverwendung:

```python
import os
from aiohomematic.api import HomematicAPI

async with HomematicAPI.connect(
    host=os.environ["CCU_HOST"],
    username=os.environ["CCU_USER"],
    password=os.environ["CCU_PASSWORD"],
) as api:
    ...
```

## Zugriffskontrolle

### Prinzip der geringsten Berechtigung

- Dedizierten CCU-Benutzer fuer Home Assistant erstellen
- Nicht das Hauptadministratorkonto verwenden
- CCU-Benutzer bei Nichtverwendung deaktivieren (Wartung)

### Netzwerkzugriff

- CCU-Verwaltungsoberflaeche auf vertrauenswuerdige IPs beschraenken
- VPN fuer Fernzugriff verwenden (keine Portweiterleitung)
- CCU-Zugriffsprotokolle ueberwachen

## Sicherheitscheckliste

| Pruefpunkt                              | Status |
| --------------------------------------- | ------ |
| CCU-Authentifizierung aktiviert         | [ ]    |
| Dedizierter Benutzer fuer HA erstellt   | [ ]    |
| Passwort verwendet nur erlaubte Zeichen | [ ]    |
| TLS aktiviert (wenn moeglich)           | [ ]    |
| Firewall-Regeln konfiguriert            | [ ]    |
| Keine CCU-Ports dem Internet ausgesetzt | [ ]    |
| secrets.yaml fuer Zugangsdaten          | [ ]    |
| Regelmaessige CCU-Firmware-Updates      | [ ]    |

## Haeufige Sicherheitsprobleme

### Problem: "Authentifizierung fehlgeschlagen"

**Ursachen:**

- Falscher Benutzername/falsches Passwort
- Passwort enthaelt nicht unterstuetzte Zeichen
- Benutzer hat keine Administratorrechte

**Loesung:**

1. Zugangsdaten in der CCU WebUI ueberpruefen
2. Passwort auf Sonderzeichen pruefen
3. Sicherstellen, dass die Benutzerrolle Administrator ist

### Problem: Callbacks funktionieren nicht

**Ursachen:**

- Firewall blockiert CCU -> HA
- Falsche `callback_host`-Einstellung

**Loesung:**

1. Sicherstellen, dass die CCU Home Assistant ueber den Callback-Port erreichen kann
2. `callback_host` auf die IP von HA setzen (nicht localhost)
3. Docker-Netzwerkkonfiguration pruefen

## Sicherheitsprobleme melden

Sicherheitsluecken privat melden:

1. **Keine** oeffentlichen GitHub Issues fuer Sicherheitsfehler eroeffnen
2. Maintainer direkt ueber GitHub Security Advisories kontaktieren
3. Zeit fuer die Behebung vor der oeffentlichen Bekanntgabe einraeumen

## Verwandte Dokumentation

- [Fehlerbehebung](../../troubleshooting/index.md) - Verbindungsprobleme
- [CUxD und CCU-Jack](cuxd_ccu_jack.md) - MQTT-Sicherheit
- [Benutzerhandbuch](../homeassistant_integration.md) - Konfiguration
