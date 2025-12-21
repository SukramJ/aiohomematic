# unignore

_AioHomematic_ maintains [multiple lists](https://github.com/sukramj/aiohomematic/blob/devel/aiohomematic/store/visibility.py#L284) of parameters that should be ignored when entities are created.
These parameters are filtered out to provide a better user experience for the majority of the users.

But there is also a group of users that wants to do more... _things_.

These advanced users can use the _unignore mechanism_ provided by _aiohomematic_.

> **Note:** For definitions of terms like Parameter, Channel, and Paramset (VALUES, MASTER), see the [Glossary](glossary.md).

You must accept the following before using the _unignore mechanism_:

- Use at your own risk!
- Customization to entities must be done with HA customisations
- Excessive writing of parameters from `MASTER` paramset can cause damage of the device

---

### Using the UI

The _unignore mechanism_ can be configured with the UI of the custom component starting with version 1.65.0.

- goto to the integrations page
- press configure
- go to the second page (interface)
- enable _advanced configuration_ and go to the next page
- the integration will automatically be reloaded after finishing the options flow.

Various patterns mentioned below can be found and selected in the drop down list.
