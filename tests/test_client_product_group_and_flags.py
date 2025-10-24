"""
Additional unit tests to improve coverage for aiohomematic.client.__init__.

This suite focuses on simple, low-dependency helpers and properties:
- Client.get_product_group branching based on model prefixes and interface fallbacks.
- Client.supports_ping_pong/supports_push_updates/supports_firmware_updates properties
  which are derived from the underlying config.

All tests include docstrings as required.
"""

from __future__ import annotations

from types import SimpleNamespace

from aiohomematic.client import Client
from aiohomematic.const import Interface, ProductGroup


class _TestClient(Client):
    """Minimal concrete Client for testing property/helper behavior without I/O."""

    @property
    def model(self) -> str:  # pragma: no cover - not relevant to tested logic
        return "test"

    # Implement required abstract methods with simple dummies so ABC allows instantiation
    async def fetch_all_device_data(self) -> None:  # pragma: no cover - not used in tests
        return None

    async def fetch_device_details(self) -> None:  # pragma: no cover - not used in tests
        return None

    async def check_connection_availability(self, *, handle_ping_pong: bool) -> bool:  # pragma: no cover
        return True

    async def set_system_variable(self, *, legacy_name: str, value):  # pragma: no cover - not used
        return None

    async def delete_system_variable(self, *, name: str):  # pragma: no cover - not used
        return None

    async def get_system_variable(self, *, name: str):  # pragma: no cover - not used
        return None

    async def get_all_system_variables(self, *, markers):  # pragma: no cover - not used
        return ()

    async def _get_system_information(self):  # pragma: no cover - not used
        from aiohomematic.const import DUMMY_SERIAL, Interface, SystemInformation

        return SystemInformation(available_interfaces=(Interface.BIDCOS_RF,), serial=f"{self.interface}_{DUMMY_SERIAL}")


def _make_client_with_interface(iface: Interface, *, push: bool = True, fw: bool = False) -> _TestClient:
    """
    Create an uninitialized Client instance with a fake _config for given interface.

    We bypass the real Client.__init__ to avoid network/config dependencies and only
    provide the attributes used by the tested properties/methods.
    """
    c = object.__new__(_TestClient)
    fake_cfg = SimpleNamespace(
        interface=iface,
        supports_push_updates=push,
        supports_firmware_updates=fw,
        supports_rpc_callback=(iface in {Interface.HMIP_RF, Interface.BIDCOS_RF, Interface.BIDCOS_WIRED}),
        version="0",
    )
    # Attach minimal config needed by Client properties
    c._config = fake_cfg  # type: ignore[attr-defined]
    return c


def test_get_product_group_by_model_prefixes() -> None:
    """get_product_group should classify by known model prefixes (case-insensitive)."""
    c = _make_client_with_interface(Interface.BIDCOS_RF)

    assert c.get_product_group(model="HMIPW-ABC123") is ProductGroup.HMIPW
    assert c.get_product_group(model="hmip-device") is ProductGroup.HMIP
    assert c.get_product_group(model="HMW-foo") is ProductGroup.HMW
    assert c.get_product_group(model="hm-bar") is ProductGroup.HM


def test_get_product_group_by_interface_fallbacks() -> None:
    """When no known prefix is found, the interface determines the product group."""
    assert _make_client_with_interface(Interface.HMIP_RF).get_product_group(model="X") is ProductGroup.HMIP
    assert _make_client_with_interface(Interface.BIDCOS_WIRED).get_product_group(model="X") is ProductGroup.HMW
    assert _make_client_with_interface(Interface.BIDCOS_RF).get_product_group(model="X") is ProductGroup.HM
    assert _make_client_with_interface(Interface.VIRTUAL_DEVICES).get_product_group(model="X") is ProductGroup.VIRTUAL
    assert _make_client_with_interface(Interface.CUXD).get_product_group(model="X") is ProductGroup.UNKNOWN


def test_support_flags_from_config() -> None:
    """supports_ping_pong/push/firmware reflect the derived values from config."""
    c1 = _make_client_with_interface(Interface.BIDCOS_RF, push=True, fw=True)
    assert c1.supports_ping_pong is True
    assert c1.supports_push_updates is True
    assert c1.supports_firmware_updates is True

    c2 = _make_client_with_interface(Interface.CUXD, push=False, fw=False)
    assert c2.supports_ping_pong is False
    assert c2.supports_push_updates is False
    assert c2.supports_firmware_updates is False
