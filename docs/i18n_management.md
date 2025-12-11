# i18n Translation Management

This document describes how translation keys are managed in the aiohomematic project.

## Overview

The project uses a custom i18n system with the following catalog files:

- `aiohomematic/strings.json` - Base catalog with English translations (source of truth)
- `aiohomematic/translations/en.json` - English catalog (mirrors strings.json)
- `aiohomematic/translations/de.json` - German catalog

## Linting Tools

### check_i18n.py

Ensures that all exceptions and INFO+ level log messages use `i18n.tr()` for translation.

**Rules:**

- All `raise` statements with string literals must use `i18n.tr()`
- All INFO, WARNING, ERROR, EXCEPTION, CRITICAL log messages must use `i18n.tr()`
- DEBUG log messages are exempt (can use plain strings)

**Skip checks:**

```python
# Inline skip for exceptions
raise ValueError("message")  # i18n-exc: ignore

# Inline skip for logs
_LOGGER.info("message")  # i18n-log: ignore

# Skip next line
# i18n-exc: ignore-next
raise ValueError("message")
```

### check_i18n_catalogs.py

Validates translation catalogs and ensures consistency between code and catalog files.

**Checks performed:**

1. **Missing keys** - Every key used in code via `i18n.tr("key")` must exist in `strings.json`
2. **Unused keys** - Every key in `strings.json` should be used in the codebase
3. **Catalog sync** - `en.json` must be identical to `strings.json`
4. **German catalog** - Reports missing/extra keys in `de.json`
5. **Formatting** - All JSON files must be sorted by key and properly formatted

**Usage:**

```bash
# Check for issues
python script/check_i18n_catalogs.py

# Auto-fix sync and formatting issues
python script/check_i18n_catalogs.py --fix

# Remove unused translation keys
python script/check_i18n_catalogs.py --remove-unused

# Combine both
python script/check_i18n_catalogs.py --fix --remove-unused
```

**Example output:**

```
Warnings:
  Unused key in strings.json: exception.validator.custom_definition.invalid (run with --remove-unused to remove)
  Unused key in strings.json: log.client.json_rpc.rename_channel.failed (run with --remove-unused to remove)

Errors:
  de.json missing key: exception.new.error
  File not sorted/formatted: aiohomematic/strings.json (run with --fix)
```

## Adding New Translation Keys

1. **Add the key to `strings.json`:**

   ```json
   {
     "exception.my_module.my_error": "My error message with {placeholder}"
   }
   ```

2. **Use it in code:**

   ```python
   raise MyException(
       i18n.tr("exception.my_module.my_error", placeholder="value")
   )
   ```

3. **Run the catalog checker:**

   ```bash
   python script/check_i18n_catalogs.py --fix
   ```

   This will automatically sync `en.json` and sort all files.

4. **Add German translation:**
   Edit `translations/de.json` and add the corresponding German text:
   ```json
   {
     "exception.my_module.my_error": "Meine Fehlermeldung mit {placeholder}"
   }
   ```

## Key Naming Conventions

Translation keys follow a hierarchical naming scheme:

### Exceptions

```
exception.<module>.<function>.<error_type>
```

Examples:

- `exception.central.create_devices.no_clients`
- `exception.client.get_value.failed`
- `exception.model.device.export_device_definition.failed`

### Log Messages

```
log.<module>.<function>.<event>
```

Examples:

- `log.client.reconnect.reconnected`
- `log.client.circuit_breaker.state_transition`
- `log.central.restart_clients.restarted`

## Pre-commit Hooks

The i18n checks are automatically run as pre-commit hooks:

```yaml
- id: check-i18n
  name: Check i18n translations
  entry: script/run-in-env.sh python script/check_i18n.py

- id: check-i18n-catalogs
  name: Check i18n catalogs
  entry: script/run-in-env.sh python script/check_i18n_catalogs.py --fix
```

## Statistics

Current catalog statistics:

- **Total keys:** 185 (as of 2025-12-11)
- **Used keys:** 181
- **Unused keys:** 4
- **Key categories:**
  - Exceptions: 111 keys
  - Log messages: 74 keys

## Maintenance

### Finding Unused Keys

```bash
# Show unused keys
python script/check_i18n_catalogs.py

# Remove unused keys from all catalogs
python script/check_i18n_catalogs.py --remove-unused
```

### Verifying Coverage

```bash
# Ensure all code uses i18n.tr() properly
python script/check_i18n.py aiohomematic/**/*.py
```

### Syncing Catalogs

```bash
# Auto-sync en.json to match strings.json and sort all files
python script/check_i18n_catalogs.py --fix
```

## Best Practices

1. **Always use `i18n.tr()`** for user-facing messages (exceptions, INFO+ logs)
2. **Use English in base catalog** - `strings.json` should always be in English
3. **Keep keys organized** - Follow the naming conventions for consistency
4. **Remove unused keys** - Run `--remove-unused` periodically to keep catalogs clean
5. **Test translations** - Verify both English and German locales work correctly
6. **DEBUG logs exempt** - Low-level debug messages can use plain strings for performance

## Troubleshooting

### "Missing key in strings.json"

Add the missing key to `strings.json` or remove the `i18n.tr()` call if it's not needed.

### "en.json differs from strings.json"

Run `python script/check_i18n_catalogs.py --fix` to auto-sync.

### "de.json missing key"

Add the German translation to `translations/de.json`.

### "Unused key in strings.json"

Either:

- Start using the key in code, or
- Remove it with `python script/check_i18n_catalogs.py --remove-unused`
