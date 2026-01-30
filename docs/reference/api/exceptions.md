# Exceptions

aiohomematic defines a hierarchy of exceptions for error handling.

## Exception Hierarchy

```
AioHomematicException (Base)
├── ClientException (Communication errors)
│   ├── NoConnectionException (Connection lost)
│   └── AuthFailure (Authentication failed)
├── ValidationException (Value validation failed)
└── UnsupportedException (Operation not supported)
```

## Usage Example

```python
from aiohomematic.exceptions import (
    AioHomematicException,
    ClientException,
    NoConnectionException,
    AuthFailure,
    ValidationException,
)

try:
    await api.write_value(
        channel_address="VCU0000001:1",
        parameter="LEVEL",
        value=1.5,  # Invalid: must be 0.0-1.0
    )
except ValidationException as e:
    print(f"Invalid value: {e}")
except NoConnectionException:
    print("Lost connection to backend")
except AuthFailure:
    print("Authentication failed - check credentials")
except ClientException as e:
    print(f"Communication error: {e}")
except AioHomematicException as e:
    print(f"General error: {e}")
```

## Class Reference

::: aiohomematic.exceptions.AioHomematicException
options:
show_root_heading: true
show_source: false

::: aiohomematic.exceptions.ClientException
options:
show_root_heading: true
show_source: false

::: aiohomematic.exceptions.NoConnectionException
options:
show_root_heading: true
show_source: false

::: aiohomematic.exceptions.AuthFailure
options:
show_root_heading: true
show_source: false

::: aiohomematic.exceptions.ValidationException
options:
show_root_heading: true
show_source: false
