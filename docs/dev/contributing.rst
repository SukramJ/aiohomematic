Contributing
============

Thank you for considering contributing to aiohomematic!

Development Setup
-----------------

1. Clone the repository:

.. code-block:: bash

    git clone https://github.com/sukramj/aiohomematic.git
    cd aiohomematic

2. Create virtual environment:

.. code-block:: bash

    python3.13 -m venv venv
    source venv/bin/activate

3. Install dependencies:

.. code-block:: bash

    pip install -r requirements.txt
    pip install -r requirements_test.txt

4. Install pre-commit hooks:

.. code-block:: bash

    pre-commit install

Code Style
----------

This project uses strict type checking and code quality tools:

- **ruff**: Linting and formatting
- **mypy**: Type checking (strict mode)
- **pylint**: Additional linting
- **bandit**: Security checks

Run all checks:

.. code-block:: bash

    pre-commit run --all-files

Type Annotations
~~~~~~~~~~~~~~~~

All code MUST be fully typed (mypy strict mode):

.. code-block:: python

    # ✅ CORRECT
    def get_device(self, *, address: str) -> Device | None:
        """Get device by address."""
        return self._devices.get(address)

    # ❌ INCORRECT
    def get_device(self, address):
        return self._devices.get(address)

Import Order
~~~~~~~~~~~~

Every file MUST start with:

.. code-block:: python

    from __future__ import annotations

Then imports in this order:

1. Standard library
2. Third-party packages
3. First-party (aiohomematic)
4. TYPE_CHECKING imports

Testing
-------

Run tests:

.. code-block:: bash

    pytest tests/

With coverage:

.. code-block:: bash

    pytest --cov=aiohomematic tests/

Write tests for new features:

.. code-block:: python

    """Test for new feature."""

    from __future__ import annotations

    import pytest

    from aiohomematic.central import CentralUnit


    @pytest.mark.asyncio
    async def test_new_feature(central_client_factory):
        """Test the new feature."""
        central, _ = await central_client_factory()
        await central.start()

        # Test your feature
        assert something is True

        await central.stop()

Pull Request Process
--------------------

1. Create a feature branch from ``devel``
2. Make changes with tests
3. Run pre-commit hooks
4. Commit with descriptive messages
5. Push and create PR to ``devel``
6. Wait for CI to pass
7. Request review

Commit Message Format
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

    <type>(<scope>): <subject>

    <body>

    <footer>

Types: ``feat``, ``fix``, ``docs``, ``style``, ``refactor``, ``test``, ``chore``

Examples:

.. code-block:: bash

    feat(model): Add support for new device type

    Implements custom entity class for XYZ device with support for
    parameter ABC and DEF.

    Closes #123

Documentation
-------------

Update documentation for:

- New public APIs
- Changed behavior
- New features

Build docs locally:

.. code-block:: bash

    cd docs
    make html
    open _build/html/index.html

Resources
---------

- GitHub: https://github.com/sukramj/aiohomematic
- Issues: https://github.com/sukramj/aiohomematic/issues
- Discussions: https://github.com/sukramj/aiohomematic/discussions
- CLAUDE.md: Comprehensive development guide
