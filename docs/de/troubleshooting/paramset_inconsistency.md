---
translation_source: docs/troubleshooting/paramset_inconsistency.md
translation_date: 2026-04-01
translation_source_hash: 3cfa3206033b
---

# Paramset-Inkonsistenz (Fehlende Geräteparameter nach Firmware-Update)

## Was ist dieses Problem?

Nach einem Firmware-Update auf HmIP-(HomematicIP-)Geräten können bestimmte Geräteparameter für Home Assistant und andere Integrationen unsichtbar werden. Das Gerät funktioniert, aber einige Konfigurationsoptionen, die nach dem Firmware-Update verfügbar sein sollten, fehlen.

**Beispiel:** Ein HmIP-FSM16 (Schaltaktor mit Leistungsmessung) mit Firmware 1.22.8 sollte das Umschalten zwischen Verbrauchs- und Einspeisemodus über den Parameter `CHANNEL_OPERATION_MODE` auf Channel 5 ermöglichen. Nach einem Firmware-Update erscheint diese Option möglicherweise nicht, obwohl die Geräte-Firmware sie unterstützt.

## Wie kommt es dazu?

Dies ist ein bekannter Fehler in der HmIPServer-(crRFD-)Komponente der CCU / RaspberryMatic:

1. Wenn ein Gerät ein **Firmware-Update** erhält, aktualisiert der HmIPServer sein internes Parameterschema (die „Beschreibung" der vom Gerät unterstützten Parameter).
2. Der HmIPServer **versäumt es jedoch manchmal, seine gespeicherten Parameterwerte zu aktualisieren** (die `.dev`-Dateien in `/etc/config/crRFD/data/`).
3. Dies erzeugt eine **Diskrepanz**: Das Schema sagt, der Parameter existiert, aber die gespeicherten Daten enthalten ihn nicht.
4. Integrationen wie Home Assistant stützen sich auf die gespeicherten Daten, um Parameter anzuzeigen und zu steuern, sodass die fehlenden Parameter unsichtbar werden.

Dieses Problem wird **nicht durch Home Assistant oder aiohomematic verursacht**. Es handelt sich um einen serverseitigen Fehler im HmIPServer von eQ-3.

## Welche Geräte sind betroffen?

Jedes HmIP- oder HmIPW-Gerät kann nach einem Firmware-Update potenziell betroffen sein. Bestätigt betroffene Geräte:

| Gerät      | Fehlende Parameter                                                          |
| ---------- | --------------------------------------------------------------------------- |
| HmIP-FSM16 | `CHANNEL_OPERATION_MODE`                                                    |
| HmIP-SPI   | `DISABLE_MSG_TO_AC`                                                         |
| HmIP-SMO   | `DISABLE_MSG_TO_AC`                                                         |
| HmIPW-WTH  | `CLIMATE_FUNCTION`, `HUMIDITY_LIMIT_VALUE`, `TWO_POINT_HYSTERESIS_HUMIDITY` |
| HMIP-SWDO  | `SAMPLE_INTERVAL`                                                           |

**Hinweis:** Diese Liste ist nicht vollständig. Jedes HmIP-Gerät, das ein Firmware-Update erhalten hat, könnte betroffen sein.

## Wie erkennt aiohomematic dieses Problem?

Ab Version 2026.2.8 prüft aiohomematic automatisch auf Paramset-Inkonsistenzen nach der Geräteerstellung. Die Prüfung vergleicht:

- **Parameterbeschreibungen** (`getParamsetDescription`): Welche Parameter die Geräte-Firmware unterstützt.
- **Tatsächliche Parameterwerte** (`getParamset`): Welche Parameter der HmIPServer tatsächlich speichert.

Wenn Parameter in der Beschreibung vorhanden sind, aber in den tatsächlich gespeicherten Daten fehlen, wird eine **Warnung** erzeugt.

### Wo die Warnung angezeigt wird

1. **Home Assistant Repairs**: Zu **Settings > System > Repairs** navigieren. Wenn betroffene Geräte erkannt werden, erscheint ein Reparatureintrag mit dem Titel „Paramset Inconsistency", der die betroffenen Geräte und Parameter auflistet.

2. **Home Assistant-Protokolle**: Nach Protokollmeldungen suchen, die mit `PARAMSET_CONSISTENCY` beginnen:

   ```
   PARAMSET_CONSISTENCY: Device VCU0000001 on interface ccu-HmIP-RF has 1 parameter(s)
   in description but not in MASTER paramset: VCU0000001:5:CHANNEL_OPERATION_MODE.
   A factory reset on the device may resolve this issue.
   ```

3. **Diagnosedaten**: Der Vorfall wird in den aiohomematic-Diagnosedaten aufgezeichnet, herunterladbar über **Settings > Devices & Services > Homematic(IP) Local > Download Diagnostics**.

## Betroffene Geräte reparieren

Die einzige zuverlässige Lösung ist ein **Werksreset** des betroffenen Geräts auf der CCU. Dies zwingt den HmIPServer, alle Parameter erneut von der Geräte-Firmware zu lesen.

### Schritt-für-Schritt-Anleitung

1. Das **CCU-WebUI** im Browser öffnen (z. B. `http://ihre-ccu-ip`).

2. Zu **Einstellungen > Geräte** navigieren.

3. Das betroffene Gerät in der Liste finden.

4. Auf das Gerät klicken, um seine Einstellungen zu öffnen.

5. Die Schaltfläche **Reset** (Werksreset / Factory Reset) anklicken.

   > **Wichtig:** Dies ist ein _Werksreset nur auf der CCU-Seite_. Es setzt die auf der CCU gespeicherten Parameter für dieses Gerät zurück, NICHT das Gerät selbst. Das Gerät verliert weder seine Kopplung noch seine Konfiguration.

6. Warten, bis die CCU die Geräteparameter erneut eingelesen hat. Dies dauert in der Regel einige Sekunden.

7. Die **Homematic(IP) Local-Integration** in Home Assistant **neu laden**:

   - Zu **Settings > Devices & Services** navigieren
   - Die Homematic(IP) Local-Integration finden
   - Auf das Drei-Punkte-Menü > **Reload** klicken

8. Die zuvor fehlenden Parameter sollten nun als Entities in Home Assistant erscheinen.

### Was bewirkt der Werksreset?

- Er weist den HmIPServer an, seine gespeicherten Parameterdaten für dieses Gerät **zu verwerfen**.
- Der HmIPServer **liest dann alle Parameter erneut** direkt von der Geräte-Firmware.
- Dies behebt die Diskrepanz zwischen Beschreibung und tatsächlichen Werten.
- Das Gerät selbst ist **NICHT** betroffen: Es behält seine Kopplung, Konfiguration und Firmware-Version.

### Alternative: CCU-Neustart

In einigen Fällen kann auch ein **vollständiger CCU-Neustart** das Problem beheben, aber ein Werksreset auf Geräteebene ist gezielter und zuverlässiger.

## Häufig gestellte Fragen

### Tritt dieses Problem erneut auf?

Es kann nach zukünftigen Firmware-Updates erneut auftreten, wenn der HmIPServer seine gespeicherten Daten wieder nicht aktualisiert. Die Lösung (Werksreset) kann bei Bedarf wiederholt werden.

### Beeinflusst der Werksreset meine Geräteeinstellungen?

Nein. Der Werksreset setzt nur den _internen Cache_ der CCU für die Geräteparameter zurück. Das Gerät selbst behält seine Kopplung, Konfiguration und Firmware. Je nach CCU-Version müssen möglicherweise einige CCU-seitige Konfigurationseinstellungen (wie Gerätenamen oder Raumzuordnungen) erneut vorgenommen werden.

### Kann aiohomematic dies automatisch beheben?

Nein. Die Ursache liegt in der HmIPServer-(crRFD-)Komponente auf der CCU, die von eQ-3 gewartet wird. aiohomematic kann das Problem nur **erkennen** und **warnen**. Nur eQ-3 kann das serverseitige Verhalten beheben, das diese Inkonsistenz verursacht.

### Warum sind nur HmIP-Geräte betroffen?

Der HmIPServer (crRFD) ist ein separater Prozess, der nur HmIP- und HmIPW-Geräte verwaltet. Klassische Homematic-(BidCos-RF-)Geräte werden von einem anderen Prozess (rfd) verwaltet, der diesen Fehler nicht aufweist.

### Der Reparatureintrag wird in Home Assistant nicht angezeigt

Die Prüfung wird nur einmal nach der Geräteerstellung oder nach einem CONFIG_PENDING-Ereignis ausgeführt (das nach Konfigurationsänderungen oder Firmware-Updates auftritt). Um die Prüfung erneut auszulösen, die Integration neu laden.

## Referenzen

- [Originale Forumsdiskussion (deutsch)](https://homematic-forum.de/forum/viewtopic.php?t=77531) von jmaus (RaspberryMatic-Entwickler)
- [HmIP XML-RPC API Addendum](https://www.eq-3.de/downloads/download/homematic/hm_web_ui_doku/HMIP_XmlRpc_API_Addendum.pdf) von eQ-3
