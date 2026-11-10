# CCU Backup

The Homematic(IP) Local integration provides two backup mechanisms: a **Backup Agent** that integrates with the Home Assistant backup system, and a **manual backup button** for on-demand CCU system backups.

!!! note "OpenCCU only"
CCU system backups are only available for **OpenCCU** (formerly RaspberryMatic), including the OpenCCU Home Assistant App. On CCU2, CCU3, Debmatic, piVCCU and Homegear the backup button and the backup agent are not offered. See the [backend feature matrix](../homeassistant_integration.md#backend-feature-matrix).

---

## Backup Agent

The integration registers a backup agent that appears as the backup location **CCU <name>** in the Home Assistant backup UI (**Settings** → **System** → **Backups**). One agent is registered per CCU config entry, so multi-CCU setups get separate agents.

The agent does **not** store the Home Assistant backup itself. Selecting it as a backup location adds a CCU system backup to every Home Assistant backup; the Home Assistant backup archive (`.tar`) stays with the other selected locations (local storage, Home Assistant Cloud, NAS, …). Always select at least one of those as well.

### How it works

When you create a Home Assistant backup and select the CCU as a backup location:

1. The agent creates a **CCU system backup** (`.sbk` file) by requesting a full backup from the CCU via ReGa script
2. The CCU backup is downloaded and saved to the backup directory
3. A **metadata file** (`<backup-id>_meta.json`) records the HA backup and the name of the associated CCU backup file

This means every HA backup created with the CCU selected is accompanied by a matching CCU system backup, giving you a restore point for both systems.

### Resilience

- **CCU unavailable or CCU backup failure**: If the CCU is not reachable or the CCU backup fails, no CCU backup is stored and Home Assistant reports the backup as failed for the location **CCU <name>**. The other selected backup locations are not affected and still receive the HA backup
- **Metadata consistency**: If metadata cannot be saved, the already-created CCU backup is automatically cleaned up
- **Orphan cleanup**: When the agent loads its backups, metadata files without a matching `.sbk` file are automatically removed

### Managing backups

All backup management is done through the standard Home Assistant backup UI:

| Action       | Behavior                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------ |
| **List**     | Shows the HA backups for which a CCU system backup exists                                        |
| **Download** | Not supported — the agent holds no HA backup archive. Download it from another backup location   |
| **Delete**   | Removes the metadata and the associated CCU `.sbk` backup. Other backup locations are unaffected |

---

## Backup Button

The integration creates a **"Create Backup"** button entity on the CCU device. Pressing it creates a standalone CCU system backup (`.sbk` file) on demand — independent of the HA backup system.

The button is only created for OpenCCU backends and is available as long as the CCU is reachable. The resulting backup file is saved to the backup directory.

---

## Backup Directory

The Backup Agent, the Backup Button and the backup action store files in:

```
<ha-config>/homematicip_local/backup/
```

This directory is created automatically when the first backup is made. It contains:

| File type     | Description                                |
| ------------- | ------------------------------------------ |
| `*_meta.json` | Metadata linking HA backups to CCU backups |
| `*.sbk`       | CCU system backups                         |

Home Assistant backup archives (`.tar`) are not stored here.

---

## CCU Backup Action

The integration also provides the `homematicip_local.create_ccu_backup` action for use in automations:

```yaml
action: homematicip_local.create_ccu_backup
data:
  entry_id: "your_config_entry_id"
```

This creates and downloads a CCU system backup, identical to pressing the backup button. The action returns `success`, `path`, `filename` and `size` of the stored backup, see [Home Assistant actions](homeassistant_actions.md#homematicip_localcreate_ccu_backup).

---

## Restore

### When to restore

A CCU restore is needed when:

- The CCU hardware was replaced or factory-reset
- A firmware update caused device or configuration issues
- Device pairings, programs, or system variables were lost
- You are migrating to a new CCU

### Restore via Home Assistant

The Home Assistant backup (`.tar`) is restored from the backup location that holds it (local storage, Home Assistant Cloud, NAS, …); the CCU location only contributes the CCU system backup (`.sbk`). To restore:

1. Go to **Settings** -> **System** -> **Backups**
2. Select the backup you want to restore
3. Follow the Home Assistant restore wizard to restore the HA backup from one of its other backup locations
4. Locate the matching CCU backup (`.sbk` file) in the backup directory:
   ```
   <ha-config>/homematicip_local/backup/
   ```
5. Restore the CCU backup separately using the CCU WebUI (see below)

Home Assistant restore does **not** automatically restore the CCU. The CCU must be restored independently using its `.sbk` file.

### Restore via CCU WebUI

1. Open the CCU WebUI in your browser (e.g., `http://<ccu-ip>`)
2. Navigate to **Settings** -> **Security** -> **System Backup**
3. Click **Restore** and select the `.sbk` file from the backup directory
4. Confirm the restore and wait for the CCU to reboot
5. After reboot, restart the Homematic(IP) Local integration in Home Assistant

### Verification after restore

After restoring, verify that the system is working correctly:

- Check that all devices appear in Home Assistant and show current states
- Confirm that device pairings are intact (devices respond to commands)
- Verify that CCU programs and system variables are present in the CCU WebUI
- Check the integration log for connection errors or missing devices

### If restore fails

- **CCU does not boot after restore**: Perform a factory reset on the CCU, then try the restore again with a different `.sbk` file
- **Devices missing after restore**: Re-pair the affected devices with the CCU. Device data points will reappear in Home Assistant automatically
- **Integration cannot connect**: Restart the integration. If the CCU IP address changed, update the integration configuration under **Settings** -> **Devices & Services**
- **Backup file corrupted**: Use an older `.sbk` file from the backup directory. Regular backups (via the Backup Agent or automations) help ensure a recent working backup is always available
