# Contributing to aiohomematic

Thank you for your interest in contributing to aiohomematic! This guide will help you get started.

## Ways to Contribute

| Type                 | Description                          |
| -------------------- | ------------------------------------ |
| **Bug Reports**      | Report issues you encounter          |
| **Feature Requests** | Suggest new features or improvements |
| **Documentation**    | Improve or translate documentation   |
| **Code**             | Fix bugs or implement features       |
| **Device Support**   | Add support for new device models    |
| **Testing**          | Test PRs and provide feedback        |

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/aiohomematic.git
cd aiohomematic
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python3.13 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements_test.txt

# Install pre-commit hooks
pre-commit install
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## Code Quality

### Pre-commit Hooks

All commits are checked by pre-commit hooks:

```bash
# Run all hooks manually
pre-commit run --all-files

# Run specific tools
ruff check --fix          # Lint
ruff format               # Format
mypy                      # Type check
pytest tests/             # Tests
```

### Type Annotations

This project uses **strict mypy**. All code must be fully typed:

```python
# Required
def get_device(self, address: str) -> Device | None:
    return self._devices.get(address)

# Not allowed
def get_device(self, address):
    return self._devices.get(address)
```

### Code Style

- **Line length**: 120 characters
- **Imports**: Use `from __future__ import annotations` in every file
- **Arguments**: Use keyword-only arguments for functions with > 2 parameters
- **Docstrings**: Follow [Docstring Standards](docstring_standards.md)

## Pull Request Process

### 1. Before Creating a PR

- [ ] All tests pass: `pytest tests/`
- [ ] Pre-commit hooks pass: `pre-commit run --all-files`
- [ ] No mypy errors
- [ ] Documentation updated (if applicable)
- [ ] Changelog updated (if applicable)

### 2. PR Title Format

Use conventional commit format:

```
feat(model): Add support for HmIP-NEW-DEVICE
fix(client): Handle connection timeout gracefully
docs: Update troubleshooting guide
refactor(central): Simplify device discovery
test: Add tests for week profile
```

### 3. PR Description

Include:

- **What** - What does this PR do?
- **Why** - Why is this change needed?
- **How** - How does it work? (for complex changes)
- **Testing** - How was it tested?

### 4. Review Process

1. Automated checks must pass
2. At least one maintainer review
3. Address review feedback
4. Maintainer merges when ready

## Adding Device Support

### Check If Needed

Most devices work automatically. Custom mappings are only needed for:

- Devices with multiple related parameters (climate, cover, lock)
- Complex state aggregation
- Special actions or behaviors

### Steps

1. **Export device definition** from a real device
2. **Add to pydevccu** repository for testing
3. **Register device** in appropriate module:

```python
# In aiohomematic/model/custom/climate.py (or appropriate module)
from aiohomematic.model.custom.registry import DeviceProfileRegistry

DeviceProfileRegistry.register(
    category=DataPointCategory.CLIMATE,
    models="HmIP-NEW-DEVICE",
    data_point_class=CustomDpIpThermostat,
    profile_type=DeviceProfile.IP_THERMOSTAT,
    channels=(1,),
)
```

4. **Add tests** in `tests/test_model_*.py`
5. **Update changelog**

See [Extension Points](extension_points.md) for detailed instructions.

## Bug Reports

### Required Information

1. **aiohomematic version** and **integration version**
2. **Home Assistant version**
3. **CCU type and firmware** (CCU3, RaspberryMatic, etc.)
4. **Steps to reproduce**
5. **Expected vs actual behavior**
6. **Relevant logs** (with `aiohomematic: debug` enabled)

### Getting Diagnostics

Download diagnostics from:
**Settings** → **Devices & Services** → **Homematic(IP) Local** → **⋮** → **Download Diagnostics**

## Feature Requests

Before requesting:

1. **Search existing issues** - It may already be requested
2. **Check documentation** - The feature may already exist
3. **Consider scope** - Is it specific to aiohomematic or the HA integration?

Include:

- **Use case** - What problem does it solve?
- **Proposed solution** - How should it work?
- **Alternatives** - Other ways to achieve the goal?

## Documentation

Documentation uses MkDocs with Material theme.

### Local Preview

```bash
pip install -r requirements_docs.txt
mkdocs serve
# Open http://127.0.0.1:8000
```

### Guidelines

- Write in English
- Keep it concise
- Include code examples
- Test all code examples
- Update navigation in `mkdocs.yml`

## Testing

### Running Tests

```bash
# All tests
pytest tests/

# With coverage
pytest --cov=aiohomematic tests/

# Specific test file
pytest tests/test_central.py

# Specific test
pytest tests/test_central.py::test_device_discovery
```

### Writing Tests

- Use pytest fixtures from `conftest.py`
- Mock external dependencies
- Test edge cases and error conditions
- Aim for > 85% coverage on new code

## Communication

- **Questions**: Use [GitHub Discussions](https://github.com/sukramj/aiohomematic/discussions)
- **Bugs/Features**: Use [GitHub Issues](https://github.com/sukramj/aiohomematic/issues)
- **Security Issues**: Contact maintainers directly (do not open public issues)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Every contribution, no matter how small, helps make aiohomematic better for everyone.
