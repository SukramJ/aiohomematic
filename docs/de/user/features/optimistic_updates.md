---
translation_source: docs/user/features/optimistic_updates.md
translation_date: 2026-04-01
translation_source_hash: f4e4052cce49
---

# Optimistische Aktualisierungen & Rollback

Wenn ein Homematic-Gerät in Home Assistant geschaltet wird, aktualisiert sich die Benutzeroberfläche **sofort** — ohne auf eine Bestätigung der CCU zu warten. Dies wird als **optimistische Aktualisierung** bezeichnet. Dadurch fühlt sich die Oberfläche schnell und reaktionsfreudig an.

Im Hintergrund startet ein Sicherheitstimer. Wenn die CCU den Befehl nicht innerhalb von **30 Sekunden** bestätigt, geht Home Assistant davon aus, dass der Befehl nicht erfolgreich war, und setzt die Benutzeroberfläche auf den vorherigen Zustand zurück. Dies wird als **optimistischer Rollback** bezeichnet.

---

## Funktionsweise

```
Taste "Ein" gedrückt
    │
    ▼
Oberfläche zeigt sofort "Ein"       ← optimistische Aktualisierung
    │
    ├── CCU bestätigt innerhalb 30s  → Zustand bleibt "Ein" ✅
    │
    └── Keine Bestätigung nach 30s  → Oberfläche springt auf "Aus" zurück ⚠️  (Rollback)
```

1. Ein Gerät wird geschaltet (z. B. ein Licht eingeschaltet)
2. Home Assistant zeigt den neuen Zustand sofort an — sofortige Rückmeldung
3. Der Befehl wird über RPC an die CCU gesendet
4. Ein 30-Sekunden-Timer startet
5. **Wenn die CCU bestätigt**: Der Timer wird abgebrochen, der Zustand ist bestätigt — alles in Ordnung
6. **Wenn keine Bestätigung eintrifft**: Der Zustand wird auf den vorherigen Wert zurückgesetzt und eine Warnung wird protokolliert

---

## Rollback-Gründe

Wenn ein Rollback auftritt, erscheint eine Warnmeldung im Home Assistant-Protokoll. Die Meldung enthält den **Grund** für den Rollback:

| Grund          | Bedeutung                                                                             |
| -------------- | ------------------------------------------------------------------------------------- |
| **timeout**    | Die CCU hat den Befehl nicht innerhalb von 30 Sekunden bestätigt                      |
| **send_error** | Der Befehl konnte nicht an die CCU gesendet werden (z. B. Verbindung verloren)        |
| **mismatch**   | Die CCU hat einen anderen Wert bestätigt als gesendet wurde (als Debug protokolliert) |

### Beispiel-Protokollmeldung

```
Optimistic rollback for Power Galerie/STATE: False -> True (reason=timeout, age=30.0s)
```

Das bedeutet:

- Das Gerät **Power Galerie** wurde auf **Ein** (`True`) geschaltet
- Die CCU hat nicht innerhalb von 30 Sekunden bestätigt
- Die Oberfläche ist auf **Aus** (`False`) zurückgesprungen

---

## Häufige Ursachen für Timeout-Rollbacks

Ein **Timeout**-Rollback bedeutet, dass der Befehl gesendet wurde, aber die CCU nicht geantwortet hat. Typische Ursachen:

### Kommunikationsprobleme

- **Netzwerkprobleme** zwischen Home Assistant und der CCU (z. B. nach SSL-Zertifikatsänderungen, Firewall-Regeln oder Netzwerk-Umkonfiguration)
- **CCU überlastet** — die CCU ist beschäftigt und kann Befehle nicht rechtzeitig verarbeiten

### Funkprobleme (RF)

- **Duty Cycle erschöpft** — BidCos-RF hat ein Duty-Cycle-Limit von 1 %. Wenn viele Geräte gleichzeitig geschaltet werden, kann das Sendebudget der CCU aufgebraucht sein
- **Schwaches Signal** — das Gerät ist zu weit von der CCU oder einem Repeater entfernt
- **Interferenzen** — andere 868-MHz-Geräte verursachen Funkkollisionen

### Geräteprobleme

- **Gerät nicht erreichbar** — das Gerät ist ausgeschaltet, defekt oder außer Reichweite
- **Batterie leer** — batteriebetriebene Geräte reagieren möglicherweise nicht, wenn die Batterie schwach ist

---

## Fehlerbehebung

### Schritt 1: Gerät über die CCU überprüfen

1. Das CCU-Webinterface im Browser öffnen (z. B. `http://<CCU-IP>`)
2. Zu **Status und Bedienung → Geräte** navigieren
3. Das betroffene Gerät finden und manuell schalten

Wenn das Gerät auch über die CCU **nicht** schaltet, liegt das Problem auf der CCU-/Funk-Seite (nicht bei Home Assistant).

### Schritt 2: CCU-Duty-Cycle prüfen

1. Das CCU-Webinterface öffnen
2. Zu **Einstellungen → Systemsteuerung → Funk-Schnittstellen** navigieren
3. Den **Duty Cycle**-Prozentwert für BidCos-RF prüfen

Liegt der Duty Cycle über 90 %, kann die CCU keine weiteren Befehle senden. Warten, bis er zurückgesetzt wird (wird jede Stunde zurückgesetzt) oder die Anzahl gleichzeitiger Befehle reduzieren.

### Schritt 3: Debug-Protokollierung aktivieren

1. In Home Assistant zu **Settings → Devices & Services** navigieren
2. Die **Homematic(IP) Local**-Integration finden und anklicken
3. **"Enable debug logging"** anklicken (das Käfer-Symbol oben)
4. Die Automation auslösen, die den Rollback verursacht
5. 30 Sekunden warten, bis der Rollback erscheint
6. Zu **Settings → System → Logs** navigieren
7. **"Download full log"** anklicken (oben rechts)
8. Debug-Protokollierung wieder deaktivieren (gleicher Pfad wie Schritt 2–3)

Im Debug-Protokoll nach Folgendem suchen:

- `set_value`-Einträge für die betroffenen Geräte — bestätigen, dass der Befehl gesendet wurde
- `event`-Einträge für dieselben Geräte — zeigen, ob die CCU eine Bestätigung gesendet hat
- Fehlermeldungen im Zusammenhang mit der betroffenen Schnittstelle

### Schritt 4: Auf kürzliche Änderungen prüfen

Rollbacks, die plötzlich nach einer Konfigurationsänderung auftreten, deuten oft auf Folgendes hin:

- **SSL/TLS-Änderungen** — das Hinzufügen von HTTPS zu Home Assistant kann die XML-RPC-Callback-Verbindung beeinträchtigen, wenn die CCU den neuen Endpunkt nicht erreichen kann
- **Netzwerkänderungen** — neuer Router, Firewall, VLAN oder IP-Adressänderungen
- **CCU-Firmware-Updates** — können Standardeinstellungen ändern oder Schnittstellenkonfigurationen zurücksetzen

---

## Konfiguration

Das Rollback-Timeout wird über `TimeoutConfig.optimistic_update_timeout` konfiguriert (Standard: **30 Sekunden**). Dies ist nicht über die Home Assistant-Oberfläche konfigurierbar — es handelt sich um eine Einstellung auf Bibliotheksebene, die für alle Geräte gilt.

Der 30-Sekunden-Standardwert wurde so gewählt, um Folgendes auszubalancieren:

- **Schnelle Rückmeldung** — Benutzer werden innerhalb von 30 Sekunden benachrichtigt, wenn ein Befehl fehlgeschlagen ist
- **Toleranz für langsame Geräte** — batteriebetriebene Geräte und ausgelastete Netzwerke benötigen möglicherweise mehrere Sekunden für eine Antwort
