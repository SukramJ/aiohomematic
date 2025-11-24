# Test Coverage Guide

This guide explains how to measure and improve test coverage in aiohomematic.

## Running Coverage

### Basic Coverage

Run tests with coverage:

```bash
pytest --cov=aiohomematic tests/
```

### HTML Coverage Report

Generate an interactive HTML report:

```bash
pytest --cov=aiohomematic --cov-report=html tests/
```

View the report:

```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Terminal Coverage Report

Show missing lines in terminal:

```bash
pytest --cov=aiohomematic --cov-report=term-missing tests/
```

### XML Coverage Report

Generate XML report for CI/codecov:

```bash
pytest --cov=aiohomematic --cov-report=xml tests/
```

### JSON Coverage Report

Generate JSON report:

```bash
pytest --cov=aiohomematic --cov-report=json tests/
```

## Coverage Configuration

### Current Targets

- **Minimum Coverage**: 85%
- **Branch Coverage**: Enabled
- **Missing Lines**: Shown in reports

### Excluded Files

The following files are excluded from coverage:

- `aiohomematic/validator.py` - CLI validator
- `aiohomematic/exceptions.py` - Exception definitions
- `aiohomematic/central/rpc_server.py` - XML-RPC server (hard to test)
- `aiohomematic/__main__.py` - Entry point
- `aiohomematic/hmcli.py` - CLI tool

### Excluded Lines

Certain patterns are excluded from coverage:

- `pragma: no cover` - Manual exclusion
- `def __repr__` - Debug representations
- `raise AssertionError` - Defensive code
- `raise NotImplementedError` - Abstract methods
- `if TYPE_CHECKING:` - Type checking blocks
- `@overload` - Type overloads
- `@abstractmethod` - Abstract methods
- `...` - Protocol method stubs
- `if __name__ == "__main__":` - Entry points

## Component Coverage

Codecov tracks coverage by component:

### Central Module

```bash
pytest --cov=aiohomematic/central --cov-report=term-missing tests/test_central*.py
```

### Client Module

```bash
pytest --cov=aiohomematic/client --cov-report=term-missing tests/test_client*.py
```

### Model Module

```bash
pytest --cov=aiohomematic/model --cov-report=term-missing tests/test_model*.py
```

### Store Module

```bash
pytest --cov=aiohomematic/store --cov-report=term-missing tests/test_store*.py
```

## Improving Coverage

### Finding Uncovered Code

1. **Generate HTML report** to see highlighted code:

   ```bash
   pytest --cov=aiohomematic --cov-report=html tests/
   ```

2. **Open the report** and look for red-highlighted lines

3. **Sort by coverage** to find modules with low coverage

### Writing Coverage Tests

Focus on:

1. **Edge cases** - Test boundary conditions
2. **Error paths** - Test exception handling
3. **Branch coverage** - Test all conditional branches
4. **Integration paths** - Test component interactions

Example:

```python
def test_device_not_found():
    """Test handling of missing device."""
    device = central.get_device(address="NONEXISTENT")
    assert device is None

def test_device_found():
    """Test successful device lookup."""
    device = central.get_device(address="VCU0000001")
    assert device is not None
    assert device.address == "VCU0000001"
```

### Coverage Tips

1. **Start with critical paths** - Cover main functionality first
2. **Use fixtures** - Reuse test setup
3. **Test one thing** - Keep tests focused
4. **Mock external dependencies** - Isolate units under test
5. **Check branch coverage** - Ensure all conditions are tested

## Continuous Integration

### GitHub Actions

Coverage is automatically checked on:

- Pull requests
- Pushes to `master` and `devel`

Codecov comments on PRs with:

- Coverage change
- Component coverage
- Uncovered lines

### Coverage Requirements

- **Project coverage** must not decrease by more than 9%
- **Patch coverage** for new code must be at least 95%
- **Changes** must not reduce coverage

## Codecov Dashboard

View detailed coverage at:

- https://codecov.io/gh/SukramJ/aiohomematic

Features:

- **Sunburst chart** - Visual coverage by component
- **File browser** - Line-by-line coverage
- **Comparison** - Compare branches and PRs
- **Trends** - Coverage over time

## Coverage Configuration Files

### pyproject.toml

Coverage settings in `[tool.coverage]`:

```toml
[tool.coverage.run]
branch = true
source = ["aiohomematic"]
omit = [...]

[tool.coverage.report]
show_missing = true
fail_under = 85.0
sort = "cover"
```

### codecov.yml

Codecov configuration:

```yaml
coverage:
  status:
    project:
      default:
        target: auto
        threshold: 0.09
```

## Troubleshooting

### No Coverage Data

If no coverage is collected:

1. Ensure pytest-cov is installed:

   ```bash
   pip install pytest-cov
   ```

2. Check source path is correct:
   ```bash
   pytest --cov=aiohomematic --cov-report=term tests/
   ```

### Coverage Too Low

If coverage fails CI:

1. **Check the diff** - See what code isn't covered
2. **Add tests** for uncovered lines
3. **Use `pragma: no cover`** sparingly for truly untestable code

### Parallel Coverage

For parallel test execution:

```bash
pytest -n auto --cov=aiohomematic --cov-report=html tests/
```

Coverage data is automatically combined.

## Best Practices

1. **Run coverage locally** before pushing
2. **Review HTML report** to understand gaps
3. **Focus on business logic** - High-value code first
4. **Don't chase 100%** - 85% with good tests is better than 100% with poor tests
5. **Test behavior, not implementation** - Coverage is a metric, not the goal

## See Also

- [Testing Guide](testing.rst) - How to write tests
- [Contributing](contributing.rst) - Contribution guidelines
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Codecov documentation](https://docs.codecov.com/)
