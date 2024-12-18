# unignore

_Hahomematic_ maintains [multiple lists](https://github.com/SukramJ/hahomematic/blob/devel/hahomematic/caches/visibility.py#L86) of parameters that should be ignored when entities are created for _Home-Assistant_.
These parameters are filtered out to provide a better user experience for the majority of the users.

But there is also a group of users that wants to do more... _things_.

These advanced users can use the _unignore mechanism_ provided by _hahomematic_.

You must accept the following before using the _unignore mechanism_:

- Use at your own risk!
- Customization to entities must be done with HA customisations
- Excessive writing of parameters from `MASTER` paramset can cause damage of the device

### Using the UI

The _unignore mechanism_ can be configured with the UI of the custom component starting with version 1.65.0.

- goto to the integrations page
- press configure
- go to the second page (interface)
- enable _advanced configuration_ and go to the next page
- the integration will automatically be reloaded after finishing the options flow.

Various patterns mentioned below can be found and selected in the drop down list.

### Using the unignore file:

This should no longer be used, and will be removed in later (1.65.0) releases:
To use the _unignore mechanism_ create a file named `unignore`(no prefix!) in the `{ha config dir}/homematicip_local` and put the parameters in there.
When adding parameters from `MASTER` paramset the [cache must be cleared](https://github.com/danielperna84/custom_homematic?tab=readme-ov-file#homematicip_localclear_cache) before restart.

Be aware of:

- Only one parameter per line
- Parameters are case sensitive
- Changes require a restart

## Examples:

### parameter only (only valid for paramset VALUES):

```
LEVEL
FROST_PROTECTION
```

### parameter with limitation to a device type, channel and paramset type (> 1.55.0):

```
GLOBAL_BUTTON_LOCK:MASTER@HmIP-eTRV-2:0
LEVEL:VALUES@HmIP-BROLL:3
GLOBAL_BUTTON_LOCK:MASTER@HM-TC-IT-WM-W-EU: (channel is empty!)
```

Wildcards can be used for device_type and channel for parameters from VALUES the paramaset:

```
LEVEL:VALUES@HmIP-BROLL:all  # (LEVEL on all channels for HmIP-BROLL)
```

# Known limitations

Parameters from `MASTER` paramset of HM-Classic (BidCos) devices can be changed, but need a manual refresh, by calling the service `homeassistant.update_entity`.

# ignore

There is also an option to ignore the automatic creation of a custom entities for a specific device type:
The line must start with `ignore_` to enable this mechanism.

```
ignore_HmIP-BROLL
```

This is useful, if you want to create your own entities based on HA templates. Ignoring a device_type gives you access to the raw data of this device.
