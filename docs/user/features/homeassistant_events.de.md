---
translation_source: docs/user/features/homeassistant_events.md
translation_date: 2026-08-02
translation_source_hash: d144149088e1
---

# Ereignis-Referenz

Diese Seite dokumentiert alle Ereignisse, die die Integration Homematic(IP) Local für OpenCCU
auf dem Home Assistant-Event-Bus auslöst, einschließlich der jeweiligen Nutzdaten.

Über **Entwicklerwerkzeuge → Ereignisse** in Home Assistant lassen sich alle Ereignistypen live
mitlesen.

!!! info "Auf der Suche nach dem Bibliotheks-Event-Bus?"
Diese Seite beschreibt die Ereignisse, auf die eine Automation triggern kann. Der interne
aiohomematic-EventBus für Entwickler ist unter [Event Reference](../../architecture/events/event_reference.md)
dokumentiert.

---

## Überblick

| Ereignistyp                                      | Wird ausgelöst, wenn                                  |
| ------------------------------------------------ | ----------------------------------------------------- |
| `homematic.keypress`                             | eine Taste an einem Gerät gedrückt wird               |
| `homematic.impulse`                              | ein Gerät einen Impuls meldet                         |
| `homematic.device_error`                         | sich ein `ERROR*`- / `SENSOR_ERROR*`-Parameter ändert |
| `homematic.device_availability`                  | ein Gerät erreichbar oder unerreichbar wird           |
| `homematicip_local.optimistic_rollback`          | ein optimistisch gesetzter Wert zurückgenommen wurde  |
| `homematicip_local.central_state_changed`        | die Zentrale ihren Zustand ändert                     |
| `homematicip_local.interface_connection_changed` | sich eine Schnittstelle verbindet oder trennt         |

Geräteparameter außerhalb dieser Liste lösen niemals ein Ereignis aus. Insbesondere sind
CCU-Servicemeldungen wie `CONFIG_PENDING`, `UPDATE_PENDING`, `STICKY_UNREACH`, `LOW_BAT` und
`SABOTAGE` **keine** Ereignisse — siehe [Servicemeldungen sind keine Ereignisse](#servicemeldungen-sind-keine-ereignisse).

---

## homematic.keypress

Wird ausgelöst, wenn ein Gerät einen Tastendruck meldet. Dieses Ereignis liegt den
Fernbedienungs-Blueprints und den Geräte-Triggern in der Automations-Oberfläche zugrunde.

**Auslösende Parameter:** `PRESS`, `PRESS_CONT`, `PRESS_LOCK`, `PRESS_LONG`,
`PRESS_LONG_RELEASE`, `PRESS_LONG_START`, `PRESS_SHORT`, `PRESS_UNLOCK`

| Feld           | Typ   | Beschreibung                                                  |
| -------------- | ----- | ------------------------------------------------------------- |
| `device_id`    | `str` | ID im Geräteregister von Home Assistant                       |
| `name`         | `str` | Gerätename (ein selbst vergebener Name hat Vorrang)           |
| `address`      | `str` | Geräteadresse, z. B. `0001D8A9B12C34`                         |
| `model`        | `str` | Gerätemodell, z. B. `HmIP-WRC2`                               |
| `interface_id` | `str` | Schnittstelle, z. B. `openccu-HmIP-RF`                        |
| `type`         | `str` | auslösender Parameter in Kleinschreibung, z. B. `press_short` |
| `subtype`      | `int` | Kanalnummer, von der der Tastendruck stammt                   |

!!! note
Der Parametername wird als `type` geliefert, der Kanal als `subtype`. Dieses Ereignis hat keine
separaten Felder `parameter`, `channel_no` oder `value`.

---

## homematic.impulse

Wird ausgelöst, wenn ein Gerät einen Impuls meldet. Einziger auslösender Parameter ist
`SEQUENCE_OK`.

Die Nutzdaten entsprechen [homematic.keypress](#homematickeypress), wobei `type` den Wert
`sequence_ok` hat.

---

## homematic.device_error

Wird ausgelöst, wenn ein Gerät einen Fehlerzustand meldet.

**Auslösende Parameter:** alle Parameter, deren Name mit `ERROR` oder `SENSOR_ERROR`
**beginnt** — zum Beispiel `ERROR_OVERHEAT`, `ERROR_OVERLOAD`, `ERROR_JAMMED`,
`ERROR_NON_FLAT_POSITIONING`, `ERROR_SABOTAGE` oder `SENSOR_ERROR`.

`ERROR_CODE` ist bewusst ausgenommen: Es handelt sich um einen rohen Zahlencode, dessen
Bedeutung je Gerät unterschiedlich ist und der in einer Benachrichtigung keinen verwertbaren
Inhalt hat.

Das Ereignis wird bei jeder Änderung des Fehlerzustands ausgelöst, also sowohl beim Auftreten
als auch beim Verschwinden eines Fehlers. Bei booleschen Parametern wird zusätzlich beim
Übergang von unbekannt auf `true` ausgelöst, bei numerischen Parametern beim Übergang von
unbekannt auf einen Wert größer null.

| Feld           | Typ           | Beschreibung                                                         |
| -------------- | ------------- | -------------------------------------------------------------------- |
| `device_id`    | `str`         | ID im Geräteregister von Home Assistant                              |
| `name`         | `str`         | Gerätename (ein selbst vergebener Name hat Vorrang)                  |
| `address`      | `str`         | Geräteadresse                                                        |
| `channel_no`   | `int`         | Kanalnummer, die den Fehler meldet                                   |
| `model`        | `str`         | Gerätemodell                                                         |
| `interface_id` | `str`         | Schnittstelle                                                        |
| `parameter`    | `str`         | Name des Fehlerparameters, z. B. `ERROR_OVERHEAT`                    |
| `value`        | `bool \| int` | Rohwert des Parameters                                               |
| `error_value`  | `bool \| int` | identisch mit `value`                                                |
| `error`        | `bool`        | `true`, solange der Fehler aktiv ist, `false` beim Abklingen         |
| `identifier`   | `str`         | stabile ID `<adresse>_<parameter>`, als Benachrichtigungs-ID nutzbar |
| `title`        | `str`         | fertiger Benachrichtigungstitel                                      |
| `message`      | `str`         | fertiger Benachrichtigungstext                                       |

Über `error` wird entschieden, ob eine Benachrichtigung erzeugt oder geschlossen wird, über
`identifier` wird in beiden Fällen dieselbe Benachrichtigung adressiert. Genau so arbeitet der
Blueprint `Show device error`.

---

## homematic.device_availability

Wird ausgelöst, wenn ein Gerät zwischen erreichbar und unerreichbar wechselt.

Die Erreichbarkeit wird aus dem Parameter `UN_REACH` auf Kanal `0` abgeleitet. Nur wenn ein
Gerät überhaupt keinen `UN_REACH`-Parameter besitzt, dient `STICKY_UNREACH` als Rückfallebene.
Da HmIP- und BidCos-Geräte beide Parameter bereitstellen, entscheidet praktisch immer
`UN_REACH`; `STICKY_UNREACH` beeinflusst die Verfügbarkeit nicht. Die Action
`force_device_availability` überschreibt das Ergebnis und löst dieses Ereignis ebenfalls aus.

| Feld           | Typ    | Beschreibung                                            |
| -------------- | ------ | ------------------------------------------------------- |
| `device_id`    | `str`  | ID im Geräteregister von Home Assistant                 |
| `name`         | `str`  | Gerätename (ein selbst vergebener Name hat Vorrang)     |
| `address`      | `str`  | Geräteadresse                                           |
| `channel_no`   | `int`  | immer `0` — Verfügbarkeit gilt je Gerät, nicht je Kanal |
| `model`        | `str`  | Gerätemodell                                            |
| `interface_id` | `str`  | Schnittstelle                                           |
| `parameter`    | `str`  | immer die Zeichenkette `AVAILABILITY`                   |
| `unavailable`  | `bool` | `true`, wenn das Gerät unerreichbar wurde               |
| `identifier`   | `str`  | stabile ID `<adresse>_availability`                     |
| `title`        | `str`  | fertiger Benachrichtigungstitel                         |
| `message`      | `str`  | fertiger Benachrichtigungstext                          |

!!! note
`parameter` ist ein von der Integration gesetzter fester Platzhalter, kein CCU-Parameter —
Geräte haben keinen Parameter `AVAILABILITY`.

---

## homematicip_local.optimistic_rollback

Wird ausgelöst, wenn ein in Home Assistant optimistisch übernommener Wert zurückgenommen werden
musste, weil die CCU ihn nicht bestätigt hat. Setzt voraus, dass **Systembenachrichtigungen** in
den erweiterten Optionen der Integration aktiviert sind. Hintergründe unter
[Optimistische Aktualisierungen](optimistic_updates.md).

| Feld                | Typ     | Beschreibung                                                        |
| ------------------- | ------- | ------------------------------------------------------------------- |
| `device_id`         | `str`   | ID im Geräteregister von Home Assistant (entfällt, wenn unbekannt)  |
| `name`              | `str`   | Gerätename (entfällt, wenn unbekannt)                               |
| `address`           | `str`   | Geräteadresse                                                       |
| `interface_id`      | `str`   | Schnittstelle                                                       |
| `parameter`         | `str`   | betroffener Parameter                                               |
| `reason`            | `str`   | `timeout`, `send_error` oder `mismatch`                             |
| `rolled_back_value` | `Any`   | der fehlgeschlagene optimistische Wert                              |
| `restored_value`    | `Any`   | der zuvor bestätigte, wiederhergestellte Wert                       |
| `age_seconds`       | `float` | wie lange der optimistische Wert gehalten wurde                     |
| `error`             | `str`   | Fehlermeldung, nur vorhanden, wenn `reason` gleich `send_error` ist |

Die drei Gründe bedeuten: Die CCU hat nicht innerhalb des Zeitlimits für optimistische
Aktualisierungen geantwortet (`timeout`), beim Senden ist eine Ausnahme aufgetreten
(`send_error`), oder die CCU hat einen anderen als den gesendeten Wert bestätigt (`mismatch`).

---

## homematicip_local.central_state_changed

Wird ausgelöst, wenn die Zentrale ihren Gesamtzustand ändert.

| Feld            | Typ   | Beschreibung                                      |
| --------------- | ----- | ------------------------------------------------- |
| `instance_name` | `str` | Name der Zentralen-Instanz                        |
| `new_state`     | `str` | `degraded`, `failed`, `recovering` oder `running` |

`degraded` bedeutet, dass mindestens eine Schnittstelle nicht verbunden ist, `failed`, dass ein
manueller Eingriff nötig ist, `recovering`, dass ein Verbindungsaufbau läuft, und `running`, dass
alle Schnittstellen verbunden sind. Beruht ein Zustand `degraded` oder `failed` auf einem
Authentifizierungsproblem, wird statt dieses Ereignisses eine erneute Anmeldung angestoßen.

---

## homematicip_local.interface_connection_changed

Wird ausgelöst, wenn sich eine einzelne Schnittstelle verbindet oder trennt.

| Feld            | Typ    | Beschreibung                                          |
| --------------- | ------ | ----------------------------------------------------- |
| `instance_name` | `str`  | Name der Zentralen-Instanz                            |
| `interface_id`  | `str`  | betroffene Schnittstelle, z. B. `openccu-HmIP-RF`     |
| `connected`     | `bool` | `true`, wenn die Schnittstelle (wieder) verbunden ist |

---

## Servicemeldungen sind keine Ereignisse

Die CCU führt eine eigene Liste von Servicemeldungen — die Einträge, die in der OpenCCU-Weboberfläche
sichtbar sind. Diese werden **nicht** als Ereignisse ausgeliefert, und die dahinterliegenden
Parameter (`CONFIG_PENDING`, `UPDATE_PENDING`, `STICKY_UNREACH`, `UN_REACH`) erzeugen auch keine
Entities in Home Assistant.

Stattdessen stellt die Integration die vollständige Liste über den Hub-Sensor
`sensor.<instanz>_hub_service_messages` bereit:

- **Zustand**: die Anzahl der aktuell aktiven Servicemeldungen
- **Attribute**: `message_1`, `message_2`, … — je Meldung ein Attribut mit Gerätename und
  Meldungstext

Der Sensor ist standardmäßig aktiviert und wird im Abfrageintervall für Systemvariablen
aktualisiert (standardmäßig 30 Sekunden). Automationen sollten daher einen **Zustands-Trigger**
auf diesen Sensor verwenden statt eines Ereignis-Triggers.

**Beispiel — benachrichtigen, sobald eine Servicemeldung auftritt:**

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.openccu_hub_service_messages
    above: 0
actions:
  - action: persistent_notification.create
    data:
      title: CCU-Servicemeldungen
      message: >
        {{ state_attr('sensor.openccu_hub_service_messages', 'message_1') }}
```

Ein entsprechender Sensor `sensor.<instanz>_hub_alarm_messages` stellt die Alarmmeldungen der CCU
auf dieselbe Weise bereit.

!!! note "LOW_BAT und SABOTAGE"
Diese beiden sind ein Sonderfall: Sie sind reguläre Binärsensoren am Gerät und sollten als
Entities verwendet werden, statt sie unter den Ereignissen zu suchen.

---

## Siehe auch

- [Actions-Referenz](homeassistant_actions.md) — alle Actions der Integration
- [Optimistische Aktualisierungen](optimistic_updates.md) — Hintergründe zu optimistischen Werten und Rollbacks
- [Event Reference](../../architecture/events/event_reference.md) — interner aiohomematic-EventBus (Entwickler)
