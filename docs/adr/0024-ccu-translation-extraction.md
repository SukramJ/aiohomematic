# ADR-0024: CCU Translation Extraction

## Status

Implemented

## Date

2026-02-11

## Context

### The Label Problem

Homematic devices, channels, and parameters are identified by technical IDs:

- **Device models**: `HmIP-eTRV-2`, `HM-CC-RT-DN`, `HmIP-FSM16`
- **Channel types**: `HEATING_CLIMATECONTROL_TRANSCEIVER`, `BLIND_VIRTUAL_RECEIVER`
- **Parameters**: `TEMPERATURE_OFFSET`, `BOOST_TIME`, `ACTIVE_PROFILE`
- **Parameter values**: `CHANNEL_OPERATION_MODE=OFF`, `STATE=TRUE`

These IDs are meaningful to developers but not to end users. A configuration UI
(such as the planned Homematic(IP) Local panel or aiohomematic-config) needs
human-readable labels in the user's language.

### Where Labels Already Exist

The CCU WebUI has a complete set of translations for all devices, channels, parameters,
and enum values. These translations are maintained by eQ-3 and the RaspberryMatic project
and ship with every CCU firmware update. They are stored as JavaScript files under
`/webui/js/lang/{locale}/` and are available both locally (via the OCCU repository) and
remotely (via HTTP from any running CCU).

### Translation Architecture in the CCU WebUI

The CCU uses a two-level indirection for parameter labels:

```
Level 1: stringtable_de.txt (mapping file)
  TEMPERATURE_OFFSET    ${stringTableTemperatureOffset}

Level 2: translate.lang.stringtable.js (translation file)
  "stringTableTemperatureOffset" : "Temperatur-Offset"

Result: TEMPERATURE_OFFSET -> "Temperatur-Offset"
```

The mapping file (`config/stringtable_de.txt`) bridges UPPER_SNAKE_CASE parameter IDs to
camelCase translation keys. Template variables may reference any of four JS translation
files (`stringtable`, `label`, `option`, `notTranslated`), and composite templates can
contain multiple variable references:

```
ACTUAL_TEMPERATURE_STATUS=NORMAL    ${lblValue} ${stringTableActualTemp}: ${lblNormal}
```

Channel type and device model descriptions use simpler direct key-value mappings in
dedicated JS files.

### Data Characteristics

- **Encoding**: Values use URL-encoded Latin-1 characters (`%FC`=u, `%F6`=o, `%E4`=a)
- **HTML**: Values may contain `<br/>`, `&nbsp;`, `&auml;` for WebUI rendering
- **File encoding**: Most files are ASCII/UTF-8; some use ISO-8859-1
- **JS variables**: Some values concatenate JavaScript variables (e.g., `HMIdentifier.de.CCUShortName`)
- **Sentinel entries**: Files end with `"theEnd": ""` or `"dummy": ""`
- **Languages**: `de` and `en` directories with largely identical key sets

### Why Not Query at Runtime?

Querying the CCU's translation files at runtime would add latency, require network access,
and complicate error handling. The translations change infrequently (only with firmware
updates), making a pre-extraction approach with checked-in JSON files the right trade-off.

## Decision

Extract CCU WebUI translations via a standalone script into static JSON files that are
checked into the repository. Provide a typed loader module for runtime access.

### Extraction Script

A standalone script (`script/extract_ccu_translations.py`) handles the full pipeline:

1. **Load** JS files from local OCCU checkout (`OCCU_PATH`) or remote CCU (`CCU_URL`)
2. **Parse** `jQuery.extend(true, langJSON, {...})` structures into Python dicts
3. **Clean** values: URL-decode, strip HTML, decode HTML entities, normalize whitespace
4. **Resolve** the two-level stringtable indirection by merging four translation sources
5. **Output** sorted JSON files per locale and category

The script is synchronous for the local path and uses `urllib.request` for the remote
path (no async dependencies needed for a development tool).

### Output Structure

```
aiohomematic/ccu_data/
  translation_extract.json.gz   # Auto-generated gzip archive (script output)
                                # Contains all categories as top-level keys:
                                # channel_types_de, channel_types_en,
                                # device_models_de, device_models_en,
                                # parameters_de, parameters_en,
                                # parameter_values_de, parameter_values_en,
                                # parameter_help_de, parameter_help_en,
                                # device_icons

  translation_custom/           # Hand-maintained overrides (editable JSON files)
    channel_types_de.json       # {} by default
    channel_types_en.json
    device_models_de.json
    device_models_en.json
    parameters_de.json
    parameters_en.json
    parameter_values_de.json
    parameter_values_en.json
    parameter_help_de.json
    parameter_help_en.json
    device_icons.json
```

All translation data uses flat `{key: label}` dictionaries sorted by key. The
`translation_extract.json.gz` archive is a generated artifact checked into git and
regenerated periodically when OCCU updates its translations. The `translation_custom/`
files allow overriding or supplementing individual translations without editing the
generated archive — custom keys survive re-extraction. At load time,
`translation_custom/` is merged on top of the extracted archive.

### Key Design Decisions

**Single gzip-compressed archive** for extracted translations, because:

- Reduces package size from ~636 KB to ~125 KB (80% reduction)
- All categories are loaded eagerly at import time anyway
- Single I/O operation instead of 11 separate file reads
- Hand-maintained overrides remain as individual editable JSON files in
  `translation_custom/`

**Parameter keys include channel-type scope** using the pipe separator:

- `TEMPERATURE_OFFSET` - global parameter label
- `HEATING_CLIMATECONTROL_TRANSCEIVER|ACTIVE_PROFILE` - channel-specific label
- `ACCELERATION_TRANSCEIVER|STATE=CLOSED` - channel-specific enum value

This mirrors the stringtable_de.txt format and allows the loader to implement
channel-specific fallback logic.

**Device model lookup with sub_model fallback**: The CCU WebUI uses abbreviated keys
for many HmIP devices (e.g., `PS` instead of `HmIP-PS`, `SMO` instead of `HmIP-SMO230`).
These abbreviated keys correspond to the `SUBTYPE` field in the device description,
exposed as `device.sub_model` in the aiohomematic model. The loader tries the full
model ID first, then falls back to sub_model.

### Loader Module

`aiohomematic/ccu_translations.py` provides four typed lookup functions:

| Function                            | Lookup Key                         | Fallback |
| ----------------------------------- | ---------------------------------- | -------- |
| `get_channel_type_translation()`    | channel_type                       | None     |
| `get_device_model_description()`    | model, then sub_model              | None     |
| `get_parameter_translation()`       | CHANNEL\|PARAM, then PARAM         | None     |
| `get_parameter_value_translation()` | CHANNEL\|PARAM=VAL, then PARAM=VAL | None     |

All functions use keyword-only arguments and accept a `locale` parameter (default: `en`).
JSON files are loaded lazily on first access and served from memory afterwards.

### JavaScript Parsing Strategy

The JS files are not valid JSON but follow a predictable `jQuery.extend()` pattern.
The parser applies these transformations in order:

1. Extract inner JSON object via regex
2. Remove trailing commas (`{..., }` -> `{...}`)
3. Remove single-line comments (`// ...`)
4. Strip JS variable concatenation (`"str" + HMIdentifier.de.Name` -> `"str"`)
5. Merge string concatenation (`"a" + "b"` -> `"ab"`)
6. Parse as JSON
7. Filter sentinel keys

### Encoding Handling

Files may use either UTF-8 or ISO-8859-1 encoding (varies between files and between
local checkout vs. HTTP fetch). Both the local reader and HTTP fetcher try UTF-8 first
and fall back to ISO-8859-1 on decode error.

## Architecture

### Data Flow

```
                           OCCU Checkout / Live CCU
                           ========================
                     ┌─────────────────────────────────────┐
                     │  webui/js/lang/{de,en}/              │
                     │    translate.lang.stringtable.js      │
                     │    translate.lang.label.js             │
                     │    translate.lang.option.js            │
                     │    translate.lang.notTranslated.js     │
                     │    translate.lang.channelDescription.js│
                     │    translate.lang.deviceDescription.js │
                     │  config/stringtable_de.txt             │
                     └──────────────┬──────────────────────-─┘
                                    │
                     script/extract_ccu_translations.py
                                    │
           ┌────────────────────────┼────────────────────────┐
           │ parse JS    resolve stringtable     clean values │
           │ files       template vars           URL-decode   │
           │             (2-level indirection)    strip HTML   │
           └────────────────────────┼────────────────────────┘
                                    │
                                    ▼
                     aiohomematic/ccu_data/
                     ┌──────────────────────────────────┐
                     │  translation_extract.json.gz      │
                     │  (all categories in one archive)  │
                     │  + translation_custom/*.json       │
                     │  (hand-maintained overrides)       │
                     └──────────────┬───────────────────┘
                                    │
                     aiohomematic/ccu_translations.py
                     (eagerly loaded, typed lookup API)
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
       Device.__init__       Channel.__init__     BaseParameterDataPoint
       ._model_description   ._type_translation    .__init__
       = get_device_model_   = get_channel_type_   ._translation = get_
       description()         translation()         parameter_translation()
              │                     │                     │
              ▼                     ▼                     ▼
       device.model_         channel.type_         data_point.translation
       description           translation           (DelegatedProperty)
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                     ┌──────────────┴──────────────┐
                     │                             │
                     ▼                             ▼
              aiohomematic-config           Home Assistant
              LabelResolver                 integration / UI
              form label generation         entity labels
```

### Model Integration

Device, Channel, and BaseParameterDataPoint each expose a translation property that
resolves a human-readable name from the CCU translations at init time:

| Class                    | Lookup function                  | Fallback          |
| ------------------------ | -------------------------------- | ----------------- |
| `Device`                 | `get_device_model_description()` | `device.name`     |
| `Channel`                | `get_channel_type_translation()` | `channel.name`    |
| `BaseParameterDataPoint` | `get_parameter_translation()`    | `parameter` (raw) |

Translations are resolved once during `__init__` and stored as `Final` attributes, since
the locale is immutable after the first `set_locale()` call (see Locale Immutability
below). Protocol interfaces (`DeviceIdentityProtocol`, `ChannelIdentityProtocol`,
`BaseParameterDataPointProtocol`) declare the translation property so consumers can depend
on it via narrow protocols.

### Locale Immutability

The locale is set once during `CentralUnit` initialization and never changes afterwards.
To enforce this invariant, `i18n.set_locale()` raises `RuntimeError` on any subsequent
call. This guarantees that translations resolved at init time remain correct for the entire
process lifetime.

A `_reset_locale_for_testing()` internal function allows tests to bypass the lock.

### Integration Points

- **Device/Channel/DataPoint translation properties**: Consumers (e.g., Home Assistant
  integration, configuration UIs) access `device.model_description`, `channel.type_translation`, or
  `data_point.translation` for human-readable names without calling translation functions
  directly.
- **aiohomematic-config**: The `LabelResolver` uses `get_parameter_translation()` and
  `get_parameter_value_translation()` to generate form labels for the configuration UI.
- **ConfigurationCoordinator**: `ConfigurableChannel` can be enriched with labels
  via `get_channel_type_translation()`.
- **Diagnostic logging**: Device and channel descriptions can use translated names
  for more readable log output.

## Risks and Mitigations

| Risk                    | Likelihood | Impact | Mitigation                                                  |
| ----------------------- | ---------- | ------ | ----------------------------------------------------------- |
| OCCU format changes     | Low        | Medium | Regex-based parser is tolerant; CI can detect regressions   |
| Missing translations    | Medium     | Low    | 248 unresolved refs from newer devices; fallback to raw IDs |
| Stale checked-in files  | Medium     | Low    | Re-run script periodically; CI can diff against OCCU        |
| Encoding surprises      | Low        | Low    | UTF-8 -> ISO-8859-1 fallback covers known variants          |
| Large file size in repo | Low        | Low    | ~125KB gzip archive + ~244KB custom overrides; static data  |

## Deferred Work

### Automatic Regeneration in CI

A CI step could compare the checked-in JSON files against the current OCCU submodule
and fail if they diverge. This would ensure translations stay up-to-date without
manual intervention. Deferred because the initial use case is manual regeneration
when adding support for new device types.

### Additional Languages

The OCCU repository currently provides `de` and `en` translations. Additional languages
(if available in future OCCU releases) can be added by extending the `_LOCALES` tuple
in both the script and loader.

### Unresolved Template References

Approximately 248 template references remain unresolved because they point to translation
keys defined in JS files outside the six core files parsed by the script (e.g.,
`translate.lang.extension.js`, `translate.lang.js`). These are predominantly for
advanced features (rules, programs, system settings) that are not relevant for device
configuration. Coverage can be extended by adding more source files if needed.

## Alternatives Considered

### 1. Runtime HTTP Fetch from CCU

Query the CCU's JS files at runtime during central initialization. Rejected because:

- Adds startup latency (12+ HTTP requests per locale)
- Requires network access and error handling
- Translations rarely change (only with firmware updates)
- Does not work when CCU is offline during development

### 2. Hardcoded Translation Tables

Maintain translation tables manually in Python source. Rejected because:

- 2500+ entries across all categories - impractical to maintain
- Diverges from upstream translations over time
- No automated way to detect new devices or parameters

### 3. Ship Complete JS Files as Package Data

Include the original OCCU JS files and parse them at runtime. Rejected because:

- Licensing concerns (OCCU files are not MIT-licensed)
- Runtime parsing overhead on every startup
- Larger package size than pre-processed JSON

### 4. Individual JSON Files Per Category (Original Approach, Superseded)

Individual JSON files per category and locale (e.g., `channel_types_de.json`,
`parameters_en.json`). This was the original implementation but was replaced by
gzip-compressed archives in version 2026.3.15 because:

- 11 separate files added ~636 KB to the package (vs. 125 KB gzip archive)
- All categories were loaded eagerly at import time anyway, so lazy per-file
  loading provided no practical benefit
- A single archive simplifies the extraction script output

## References

- [Concept document](../concepts/ccu_translation_extraction.md) - detailed analysis of
  CCU WebUI translation files and extraction strategy
- [OCCU repository](https://github.com/jens-maus/occu) - source of translation files
- `script/extract_ccu_translations.py` - extraction script
- `aiohomematic/ccu_translations.py` - loader module
- `aiohomematic/model/device.py` - Device and Channel `label` properties
- `aiohomematic/model/data_point.py` - BaseParameterDataPoint `label` property
- `aiohomematic/i18n.py` - locale immutability guard (`set_locale`, `_reset_locale_for_testing`)
