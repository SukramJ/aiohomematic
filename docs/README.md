# aiohomematic Documentation

This directory contains the Sphinx documentation for aiohomematic.

## Building the Documentation

### Install Dependencies

```bash
pip install -r requirements_docs.txt
```

### Build HTML Documentation

```bash
cd docs
make html
```

The built documentation will be in `_build/html/`. Open `_build/html/index.html` in your browser.

### Build Other Formats

```bash
make latexpdf  # PDF documentation
make epub      # EPUB documentation
make help      # See all available formats
```

### Clean Build Artifacts

```bash
make clean
```

## Documentation Structure

- `api/` - Auto-generated API reference documentation
- `user/` - User guides (installation, quickstart, configuration, examples)
- `dev/` - Developer documentation
- Markdown files - Architecture and integration guides

## Contributing to Documentation

When adding new modules or classes:

1. Add appropriate docstrings to your code (Google style)
2. Update the relevant `.rst` files in `api/`
3. Rebuild the documentation to verify

For narrative documentation:

1. Create/edit `.rst` or `.md` files
2. Update `index.rst` if adding new pages
3. Rebuild to verify formatting

## Docstring Style

This project uses Google-style docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """
    Brief description of the function.

    Longer description with more details about what the function does,
    its behavior, and any important notes.

    Args:
    ----
        param1: Description of param1
        param2: Description of param2

    Returns:
    -------
        Description of return value

    Raises:
    ------
        ValueError: When param2 is negative

    Example:
    -------
        >>> example_function("test", 42)
        True

    """
    return True
```

## Online Documentation

The documentation is automatically built and published at:

- https://aiohomematic.readthedocs.io (if configured)

## Troubleshooting

### Import Errors

If you get import errors when building:

1. Ensure all dependencies are installed
2. Check that Python 3.13+ is being used
3. Verify the package can be imported: `python -c "import aiohomematic"`

### Missing Modules

If autodoc can't find modules:

1. Check `sys.path` configuration in `conf.py`
2. Ensure the package is installed or the path is correct
3. Verify module names in `.rst` files

### Theme Issues

If the RTD theme doesn't work:

```bash
pip install --upgrade sphinx-rtd-theme
```
