Installation
============

Requirements
------------

- Python 3.13 or higher
- pip or uv package manager

Dependencies
------------

aiohomematic requires the following packages:

- ``aiohttp>=3.12.0`` - Async HTTP client
- ``orjson>=3.11.0`` - Fast JSON serialization
- ``python-slugify>=8.0.0`` - URL-safe string conversion
- ``voluptuous>=0.15.0`` - Configuration/schema validation

Installing from PyPI
--------------------

Install the latest stable version from PyPI:

.. code-block:: bash

    pip install aiohomematic

Using uv (recommended for development):

.. code-block:: bash

    uv pip install aiohomematic

Installing from Source
----------------------

Clone the repository and install in development mode:

.. code-block:: bash

    git clone https://github.com/sukramj/aiohomematic.git
    cd aiohomematic
    pip install -e .

Verifying Installation
----------------------

Verify the installation by importing the package:

.. code-block:: python

    import aiohomematic
    print(aiohomematic.__version__)

Development Installation
------------------------

For development, install with test dependencies:

.. code-block:: bash

    pip install -r requirements.txt
    pip install -r requirements_test.txt

Install pre-commit hooks:

.. code-block:: bash

    pre-commit install
