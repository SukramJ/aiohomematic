# Contributing to aiohomematic

Thank you for your interest in contributing to aiohomematic! This document provides guidelines and instructions for contributing.

## Getting Started

### Prerequisites

- Python 3.13 or higher
- Git

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/aiohomematic.git
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

## Code Standards

This project enforces strict code quality standards. All contributions must adhere to the following:

### Type Annotations

All code must be fully typed. The project uses mypy in strict mode.

```python
# Required at the top of every Python file
from __future__ import annotations

# All functions must have complete type annotations
def get_device(self, address: str) -> Device | None:
    """Return device by address."""
    return self._devices.get(address)
```

### Docstrings

- All public classes and methods require docstrings
- Use imperative mood ("Return the value", not "Returns the value")
- End all docstrings with a period

```python
def fetch_data(self) -> dict[str, Any]:
    """Fetch data from the backend."""
    ...
```

### Code Style

- Line length: 120 characters maximum
- Use keyword-only arguments for functions with multiple parameters
- Follow the import order: stdlib → third-party → first-party → TYPE_CHECKING

## Pull Request Process

### Branch Strategy

1. Create your feature branch from `devel`:
   ```bash
   git checkout devel
   git pull origin devel
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Submit your PR against the `devel` branch (not `master`)

### Quality Checks

Before submitting, ensure all checks pass:

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run tests
pytest tests/

# Run tests with coverage
pytest --cov=aiohomematic tests/
```

### PR Requirements

- All tests must pass
- No mypy errors
- No ruff/pylint errors
- Code must be formatted with ruff
- Meaningful commit messages

### Commit Messages

Use conventional commit format:

```
<type>(<scope>): <subject>

<body>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(model): Add support for HmIP-NEW-DEVICE
fix(client): Handle connection timeout gracefully
docs(readme): Update installation instructions
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_central.py

# Run with verbose output
pytest -v tests/

# Run with coverage report
pytest --cov=aiohomematic --cov-report=html tests/
```

### Writing Tests

- Place tests in the `tests/` directory
- Use pytest fixtures from `conftest.py`
- Follow existing test patterns in the codebase

## What to Contribute

### Good First Issues

Look for issues labeled `good first issue` for beginner-friendly tasks.

### Feature Requests

If you want to add a new feature:

1. Check existing issues to avoid duplicates
2. Open an issue describing the feature
3. Wait for maintainer feedback before starting work

### Bug Fixes

1. Check if the bug is already reported
2. Create an issue if it doesn't exist
3. Reference the issue in your PR

## Questions?

- Open an issue for questions about the codebase
- Check the [documentation](../docs/) for architecture details
- See [CLAUDE.md](../CLAUDE.md) for comprehensive development guidelines

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
