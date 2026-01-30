# Development Environment

This guide covers setting up a development environment for contributing to aiohomematic.

## Prerequisites

- **Python**: 3.13 or higher
- **Git**: For version control
- **Package Manager**: pip or uv (recommended)

## Initial Setup

### Clone and Create Virtual Environment

```bash
# Clone the repository
git clone https://github.com/sukramj/aiohomematic.git
cd aiohomematic

# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements_test.txt

# Install pre-commit hooks
pre-commit install
```

### Verify Setup

```bash
# Run tests
pytest tests/

# Run linters
pre-commit run --all-files

# Type check
mypy
```

## Project Structure

```
aiohomematic/
├── aiohomematic/           # Main package (~26.8K LOC)
│   ├── central/            # Central orchestration
│   ├── client/             # Protocol adapters
│   ├── model/              # Device, Channel, DataPoint
│   ├── interfaces/         # Protocol interfaces for DI
│   ├── store/              # Caching and persistence
│   └── const.py            # Constants and enums
├── tests/                  # Test suite
├── docs/                   # Documentation (MkDocs)
├── script/                 # Development scripts
└── aiohomematic_test_support/  # Test infrastructure
```

## Core Dependencies

| Package                 | Purpose                 |
| ----------------------- | ----------------------- |
| `aiohttp>=3.12.0`       | Async HTTP client       |
| `orjson>=3.11.0`        | Fast JSON serialization |
| `pydantic>=2.10.0`      | Data validation         |
| `python-slugify>=8.0.0` | URL-safe strings        |

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=aiohomematic tests/

# Run specific test file
pytest tests/test_central.py

# Run with verbose output
pytest -v tests/

# Run specific test markers
pytest -m "not slow" tests/
```

## Running Linters

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Individual tools
ruff check --fix        # Lint and auto-fix
ruff format             # Format code
mypy                    # Type check
pylint -j 0 aiohomematic  # Full linting
bandit --quiet          # Security check
codespell               # Spell check
```

## Development Scripts

| Script                           | Purpose                        |
| -------------------------------- | ------------------------------ |
| `script/sort_class_members.py`   | Organize class members         |
| `script/check_i18n.py`           | Validate translation usage     |
| `script/check_i18n_catalogs.py`  | Check translation completeness |
| `script/lint_kwonly.py`          | Enforce keyword-only arguments |
| `script/lint_package_imports.py` | Enforce import conventions     |
| `script/lint_all_exports.py`     | Validate `__all__` exports     |

## Pre-commit Hooks

The following hooks run automatically on commit:

1. **sort-class-members** - Organize class members
2. **check-i18n** - Validate translations
3. **lint-package-imports** - Enforce package imports
4. **lint-all-exports** - Validate exports
5. **ruff** - Lint and format
6. **mypy** - Type check
7. **pylint** - Additional linting
8. **codespell** - Spell check
9. **bandit** - Security check
10. **yamllint** - YAML validation

To bypass hooks (not recommended):

```bash
git commit --no-verify -m "message"
```

## IDE Configuration

### VS Code

Recommended extensions:

- Python
- Pylance
- Ruff
- mypy

Settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.analysis.typeCheckingMode": "strict",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

### PyCharm

1. Set Python interpreter to `./venv/bin/python`
2. Enable mypy plugin with strict mode
3. Configure ruff as external tool

## Debugging Tips

### Enable Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

### Use Session Recorder

```python
from aiohomematic.const import OptionalSettings

config = CentralConfig(
    ...,
    optional_settings=(OptionalSettings.SESSION_RECORDER,),
)
```

### Performance Metrics

```python
config = CentralConfig(
    ...,
    optional_settings=(OptionalSettings.PERFORMANCE_METRICS,),
)
```

## Next Steps

- [Coding Standards](coding/naming.md) - Naming conventions and style
- [Testing Guidelines](testing/coverage.md) - How to write tests
- [Git Workflow](git-workflow.md) - Branch and commit conventions
- [Contributing](contributing.md) - How to submit changes
