# CCU Backup

The Homematic(IP) Local integration provides two backup mechanisms: a **Backup Agent** that integrates with the Home Assistant backup system, and a **manual backup button** for on-demand CCU system backups.

---

## Backup Agent

The integration registers a **LocalBackupAgent** that appears as a backup storage location in the Home Assistant backup UI (**Settings** → **System** → **Backups**). One agent is registered per CCU config entry, so multi-CCU setups get separate agents.

### How it works

When you create a Home Assistant backup and select the CCU as a storage location:

1. The agent first creates a **CCU system backup** (`.sbk` file) by requesting a full backup from the CCU via ReGa script
2. The CCU backup is downloaded and saved to the configured backup directory
3. The **HA backup** (`.tar` file) is stored in the same directory
4. A **metadata file** (`*_meta.json`) links the HA backup to the associated CCU backup

This means every HA backup stored on the CCU is accompanied by a matching CCU system backup, giving you a complete restore point for both systems.

### Resilience

- **CCU unavailable**: If the CCU is not reachable when the HA backup runs, the HA backup is saved without a CCU backup (a warning is logged)
- **CCU backup failure**: If the CCU backup fails for any reason, the HA backup proceeds normally — CCU backup failures never block HA backups
- **Metadata consistency**: If metadata cannot be saved, any already-created CCU backup is automatically cleaned up
- **Orphan cleanup**: When listing backups, metadata files without a matching `.tar` file are automatically removed

### Managing backups

All backup management is done through the standard Home Assistant backup UI:

| Action       | Behavior                                                                  |
| ------------ | ------------------------------------------------------------------------- |
| **List**     | Shows all HA backups stored in the CCU backup directory                   |
| **Download** | Downloads the HA backup `.tar` file                                       |
| **Delete**   | Removes the HA backup, its metadata, and the associated CCU `.sbk` backup |

---

## Backup Button

The integration creates a **"Create Backup"** button entity on the CCU device. Pressing it creates a standalone CCU system backup (`.sbk` file) on demand — independent of the HA backup system.

The button is available as long as the CCU is reachable. The resulting backup file is saved to the configured backup directory.

---

## Backup Directory

Both the Backup Agent and the Backup Button store files in:

```
<ha-config>/homematicip_local/backup/
```

This directory is created automatically when the first backup is made. It contains:

| File type     | Description                                         |
| ------------- | --------------------------------------------------- |
| `*.tar`       | Home Assistant backup archives (created by HA core) |
| `*_meta.json` | Metadata linking HA backups to CCU backups          |
| `*.sbk`       | CCU system backups                                  |

---

## CCU Backup Service

The integration also provides a `homematicip_local.create_ccu_backup` service for use in automations:

```yaml
service: homematicip_local.create_ccu_backup
data:
  entry_id: "your_config_entry_id"
```

This creates and downloads a CCU system backup, identical to pressing the backup button.

---

## Restore

### When to restore

A CCU restore is needed when:

- The CCU hardware was replaced or factory-reset
- A firmware update caused device or configuration issues
- Device pairings, programs, or system variables were lost
- You are migrating to a new CCU

### Restore via Home Assistant

Home Assistant backups stored on the CCU include both the HA backup (`.tar`) and the CCU system backup (`.sbk`). To restore:

1. Go to **Settings** -> **System** -> **Backups**
2. Select the backup you want to restore
3. Follow the Home Assistant restore wizard to restore the HA backup
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
