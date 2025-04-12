"""Tests for switch data points of hahomematic."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Final
from unittest.mock import Mock, patch

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import (
    INIT_DATETIME,
    SCHEDULER_PROFILE_PATTERN,
    SCHEDULER_TIME_PATTERN,
    VIRTUAL_REMOTE_ADDRESSES,
    DataPointUsage,
    ParameterData,
    ParameterType,
    ParamsetKey,
    SysvarType,
)
from hahomematic.converter import _COMBINED_PARAMETER_TO_HM_CONVERTER, convert_hm_level_to_cpv
from hahomematic.exceptions import HaHomematicException
from hahomematic.model.support import (
    _check_channel_name_with_channel_no,
    convert_value,
    generate_unique_id,
    get_custom_data_point_name,
    get_data_point_name_data,
    get_device_name,
    get_event_name,
)
from hahomematic.support import (
    build_xml_rpc_headers,
    build_xml_rpc_uri,
    changed_within_seconds,
    check_or_create_directory,
    check_password,
    element_matches_key,
    find_free_port,
    get_channel_no,
    get_tls_context,
    is_channel_address,
    is_device_address,
    is_hostname,
    is_ipv4_address,
    parse_sys_var,
    to_bool,
)

from tests import helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU3609622": "HmIP-eTRV-2.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        ({}, True, False, False, None, None),
    ],
)
async def test_generate_unique_id(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test generate_unique_id."""
    central, _, _ = central_client_factory
    assert generate_unique_id(central=central, address="VCU2128127", parameter="LEVEL") == "vcu2128127_level"
    assert (
        generate_unique_id(central=central, address="VCU2128127", parameter="LEVEL", prefix="PREFIX")
        == "prefix_vcu2128127_level"
    )
    assert generate_unique_id(central=central, address="INT0001", parameter="LEVEL") == "test1234_int0001_level"


def test_build_xml_rpc_uri() -> None:
    """Test build_xml_rpc_uri."""
    assert build_xml_rpc_uri(host="1.2.3.4", port=80, path=None) == "http://1.2.3.4:80"
    assert build_xml_rpc_uri(host="1.2.3.4", port=80, path="group") == "http://1.2.3.4:80/group"
    assert build_xml_rpc_uri(host="1.2.3.4", port=80, path="group", tls=True) == "https://1.2.3.4:80/group"


def test_build_headers() -> None:
    """Test build_xml_rpc_uri."""
    assert build_xml_rpc_headers(username="Martin", password="") == [("Authorization", "Basic TWFydGluOg==")]
    assert build_xml_rpc_headers(username="", password="asdf") == [("Authorization", "Basic OmFzZGY=")]
    assert build_xml_rpc_headers(username="Martin", password="asdf") == [("Authorization", "Basic TWFydGluOmFzZGY=")]


def test_check_or_create_directory() -> None:
    """Test check_or_create_directory."""
    assert check_or_create_directory(directory="") is False
    with patch(
        "os.path.exists",
        return_value=True,
    ):
        assert check_or_create_directory(directory="tmpdir_1") is True

    with (
        patch(
            "os.path.exists",
            return_value=False,
        ),
        patch(
            "os.makedirs",
            return_value=None,
        ),
    ):
        assert check_or_create_directory(directory="tmpdir_1") is True

    with (
        patch(
            "os.path.exists",
            return_value=False,
        ),
        patch("os.makedirs", side_effect=OSError("bla bla")),
    ):
        with pytest.raises(HaHomematicException) as exc:
            check_or_create_directory(directory="tmpdir_ex")
        assert exc


def test_parse_sys_var() -> None:
    """Test parse_sys_var."""
    assert parse_sys_var(data_type=None, raw_value="1.4") == "1.4"
    assert parse_sys_var(data_type=SysvarType.STRING, raw_value="1.4") == "1.4"
    assert parse_sys_var(data_type=SysvarType.FLOAT, raw_value="1.4") == 1.4
    assert parse_sys_var(data_type=SysvarType.INTEGER, raw_value="1") == 1
    assert parse_sys_var(data_type=SysvarType.ALARM, raw_value="true") is True
    assert parse_sys_var(data_type=SysvarType.LIST, raw_value="1") == 1
    assert parse_sys_var(data_type=SysvarType.LOGIC, raw_value="true") is True


@pytest.mark.asyncio
async def test_to_bool() -> None:
    """Test to_bool."""
    assert to_bool(value=True) is True
    assert to_bool(value="y") is True
    assert to_bool(value="yes") is True
    assert to_bool(value="t") is True
    assert to_bool(value="true") is True
    assert to_bool(value="on") is True
    assert to_bool(value="1") is True
    assert to_bool(value="") is False
    assert to_bool(value="n") is False
    assert to_bool(value="no") is False
    assert to_bool(value="f") is False
    assert to_bool(value="false") is False
    assert to_bool(value="off") is False
    assert to_bool(value="0") is False
    assert to_bool(value="blabla") is False
    assert to_bool(value="2") is False
    with pytest.raises(TypeError):
        to_bool(value=2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_get_data_point_name(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test get_data_point_name."""
    central, _, _ = central_client_factory
    device = central.get_device(address="VCU2128127")
    assert device
    channel4 = device.get_channel(channel_address=f"{device.address}:5")
    name_data = get_data_point_name_data(channel=channel4, parameter="LEVEL")
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Level"
    assert name_data.name == "Level"

    central.device_details.add_name(address=f"{device.address}:5", name="Roof")
    channel5 = device.get_channel(channel_address=f"{device.address}:5")
    name_data = get_data_point_name_data(channel=channel5, parameter="LEVEL")
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof Level"
    assert name_data.name == "Roof Level"

    with patch(
        "hahomematic.model.support._get_base_name_from_channel_or_device",
        return_value=None,
    ):
        name_data = get_data_point_name_data(channel=channel5, parameter="LEVEL")
        assert name_data.full_name == ""
        assert name_data.name == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_get_event_name(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test get_event_name."""
    central, _, _ = central_client_factory
    device = central.get_device(address="VCU2128127")
    assert device
    channel4 = device.get_channel(channel_address=f"{device.address}:4")
    name_data = get_event_name(channel=channel4, parameter="LEVEL")
    assert name_data.channel_name == "ch4"
    assert name_data.name == "ch4 Level"
    assert name_data.full_name == "HmIP-BSM_VCU2128127 ch4 Level"

    central.device_details.add_name(address=f"{device.address}:5", name="Roof")
    channel5 = device.get_channel(channel_address=f"{device.address}:5")
    name_data = get_event_name(channel=channel5, parameter="LEVEL")
    assert name_data.channel_name == "Roof"
    assert name_data.name == "Roof Level"
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof Level"

    with patch(
        "hahomematic.model.support._get_base_name_from_channel_or_device",
        return_value=None,
    ):
        name_data = get_event_name(channel=channel5, parameter="LEVEL")
        assert name_data.full_name == ""
        assert name_data.name == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_custom_data_point_name(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test get_custom_data_point_name."""
    central, _, _ = central_client_factory
    device = central.get_device(address="VCU2128127")
    assert device
    channel4 = device.get_channel(channel_address=f"{device.address}:4")
    name_data = get_custom_data_point_name(
        channel=channel4,
        is_only_primary_channel=True,
        ignore_multiple_channels_for_name=False,
        usage=DataPointUsage.CDP_PRIMARY,
    )
    assert name_data.full_name == "HmIP-BSM_VCU2128127"
    assert name_data.name == ""

    name_data = get_custom_data_point_name(
        channel=channel4,
        is_only_primary_channel=False,
        ignore_multiple_channels_for_name=False,
        usage=DataPointUsage.CDP_SECONDARY,
    )
    assert name_data.full_name == "HmIP-BSM_VCU2128127 vch4"
    assert name_data.name == "vch4"

    central.device_details.add_name(address=f"{device.address}:5", name="Roof")
    channel5 = device.get_channel(channel_address=f"{device.address}:5")
    name_data = get_custom_data_point_name(
        channel=channel5,
        is_only_primary_channel=True,
        ignore_multiple_channels_for_name=False,
        usage=DataPointUsage.CDP_PRIMARY,
    )
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof"
    assert name_data.name == "Roof"

    name_data = get_custom_data_point_name(
        channel=channel5,
        is_only_primary_channel=False,
        ignore_multiple_channels_for_name=False,
        usage=DataPointUsage.CDP_SECONDARY,
    )
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof"
    assert name_data.name == "Roof"

    with patch(
        "hahomematic.model.support._get_base_name_from_channel_or_device",
        return_value=None,
    ):
        name_data = get_custom_data_point_name(
            channel=channel5,
            is_only_primary_channel=False,
            ignore_multiple_channels_for_name=False,
            usage=DataPointUsage.CDP_SECONDARY,
        )
        assert name_data.full_name == ""
        assert name_data.name == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_get_device_name(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test get_device_name."""
    central, _, _ = central_client_factory
    assert get_device_name(central=central, device_address="VCU2128127", model="HmIP-BSM") == "HmIP-BSM_VCU2128127"
    central.device_details.add_name(address="VCU2128127", name="Roof")
    assert get_device_name(central=central, device_address="VCU2128127", model="HmIP-BSM") == "Roof"


@pytest.mark.asyncio
async def test_tls_context() -> None:
    """Test tls_context."""
    assert get_tls_context(verify_tls=False).check_hostname is False
    assert get_tls_context(verify_tls=True).check_hostname is True


@pytest.mark.asyncio
async def test_changed_within_seconds() -> None:
    """Test changed_within_seconds."""
    assert changed_within_seconds(last_change=(datetime.now() - timedelta(seconds=10)), max_age=60) is True
    assert changed_within_seconds(last_change=(datetime.now() - timedelta(seconds=70)), max_age=60) is False
    assert changed_within_seconds(last_change=INIT_DATETIME, max_age=60) is False


@pytest.mark.asyncio
async def test_convert_value() -> None:
    """Test convert_value."""
    assert convert_value(value=None, target_type=ParameterType.BOOL, value_list=None) is None
    assert convert_value(value=True, target_type=ParameterType.BOOL, value_list=None) is True
    assert convert_value(value="true", target_type=ParameterType.BOOL, value_list=None) is True
    assert convert_value(value=1, target_type=ParameterType.BOOL, value_list=("CLOSED", "OPEN")) is True
    assert convert_value(value=0, target_type=ParameterType.BOOL, value_list=("CLOSED", "OPEN")) is False
    assert convert_value(value=2, target_type=ParameterType.BOOL, value_list=("CLOSED", "OPEN")) is False
    assert convert_value(value="0.1", target_type=ParameterType.FLOAT, value_list=None) == 0.1
    assert convert_value(value="1", target_type=ParameterType.INTEGER, value_list=None) == 1
    assert convert_value(value="test", target_type=ParameterType.STRING, value_list=None) == "test"
    assert convert_value(value="1", target_type=ParameterType.STRING, value_list=None) == "1"
    assert convert_value(value=True, target_type=ParameterType.ACTION, value_list=None) is True


@pytest.mark.asyncio
async def test_element_matches_key() -> None:
    """Test element_matches_key."""
    assert element_matches_key(search_elements="HmIP-eTRV", compare_with=None) is False
    assert element_matches_key(search_elements="HmIP-eTRV", compare_with="HmIP-eTRV-2") is True
    assert (
        element_matches_key(
            search_elements="HmIP-eTRV",
            compare_with="HmIP-eTRV-2",
            do_right_wildcard_search=False,
        )
        is False
    )
    assert element_matches_key(search_elements=["HmIP-eTRV", "HmIP-BWTH"], compare_with="HmIP-eTRV-2") is True
    assert (
        element_matches_key(
            search_elements=["HmIP-eTRV", "HmIP-BWTH"],
            compare_with="HmIP-eTRV-2",
            do_right_wildcard_search=False,
        )
        is False
    )
    assert (
        element_matches_key(
            search_elements=["HmIP-eTRV", "HmIP-BWTH"],
            compare_with="HmIP-eTRV",
            do_right_wildcard_search=False,
        )
        is True
    )
    assert (
        element_matches_key(
            search_elements=["eTRV", "HmIP-BWTH"],
            compare_with="HmIP-eTRV",
            do_left_wildcard_search=True,
            do_right_wildcard_search=False,
        )
        is True
    )
    assert (
        element_matches_key(
            search_elements=["IP-eTR", "HmIP-BWTH"],
            compare_with="HmIP-eTRV",
            do_left_wildcard_search=True,
            do_right_wildcard_search=True,
        )
        is True
    )
    assert (
        element_matches_key(
            search_elements=["HmIP-eTRV", "HmIP-BWTH"],
            compare_with="HmIP-eTRV",
            do_left_wildcard_search=True,
            do_right_wildcard_search=True,
        )
        is True
    )
    assert (
        element_matches_key(
            search_elements=["INTERNAL", "HA", "hahm"],
            compare_with="Long description with hahm in text",
            do_left_wildcard_search=True,
            do_right_wildcard_search=True,
        )
        is True
    )


@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_others() -> None:
    """Test find_free_port."""
    assert find_free_port()
    assert get_channel_no(address="12312:1") == 1
    assert get_channel_no(address="12312") is None
    assert _check_channel_name_with_channel_no(name="light:1") is True
    assert _check_channel_name_with_channel_no(name="light:Test") is False
    assert _check_channel_name_with_channel_no(name="light:Test:123") is False


def test_password() -> None:
    """
    Test the password.

    Password can be empty.
    Allowed characters:
        - A-Z, a-z
        - 0-9
        - ., !, $, (, ), :, ;, #, -
    """
    assert check_password(None) is False
    assert check_password("") is True
    assert check_password("t") is True
    assert check_password("test") is True
    assert check_password("TEST") is True
    assert check_password("1234") is True
    assert check_password("test123TEST") is True
    assert check_password("test.!$():;#-") is True
    assert check_password("test%") is False


@pytest.mark.parametrize(
    ("parameter", "input_value", "converter", "result_value"),
    [
        (
            "LEVEL_COMBINED",
            0,
            convert_hm_level_to_cpv,
            "0x00",
        ),
        (
            "LEVEL_COMBINED",
            0.17,
            convert_hm_level_to_cpv,
            "0x22",
        ),
        (
            "LEVEL_COMBINED",
            0.81,
            convert_hm_level_to_cpv,
            "0xa2",
        ),
        (
            "LEVEL_COMBINED",
            1,
            convert_hm_level_to_cpv,
            "0xc8",
        ),
    ],
)
def test_converter(
    parameter: str,
    input_value: Any,
    converter: Callable,
    result_value: Any,
) -> None:
    """Test device un ignore."""

    assert input_value is not None
    assert converter(input_value) == result_value
    if re_converter := _COMBINED_PARAMETER_TO_HM_CONVERTER.get(parameter):
        assert re_converter(result_value) == input_value


def test_is_valid_hostname() -> None:
    """Test is_valid_hostname."""
    assert is_hostname(None) is False
    assert is_hostname("") is False
    assert is_hostname(" ") is False
    assert is_hostname("123") is False
    assert is_hostname("ccu") is True
    assert is_hostname("ccu.test.de") is True
    assert is_hostname("ccu.de") is True
    assert is_hostname("ccu.123") is False
    assert is_hostname("192.168.178.2") is False
    assert is_hostname("5422eb72-raspberrymatic") is True


def test_is_valid_ipv4_address() -> None:
    """Test is_valid_ipv4_address."""
    assert is_ipv4_address(None) is False
    assert is_ipv4_address("") is False
    assert is_ipv4_address(" ") is False
    assert is_ipv4_address("192.168.1782") is False
    assert is_ipv4_address("192.168.178.2") is True
    assert is_ipv4_address("ccu") is False


def test_is_device_address() -> None:
    """Test is_device_address."""
    for address in VIRTUAL_REMOTE_ADDRESSES:
        assert is_device_address(address) is True
    assert is_device_address("123456789:2") is False
    assert is_device_address("KEQ1234567") is True
    assert is_device_address("001858A123B912") is True
    assert is_device_address("1234567890#") is False
    assert is_device_address("123456789_:123") is False
    assert is_device_address("ABcdEFghIJ1234567890") is True
    assert is_device_address("12345678901234567890") is True
    assert is_device_address("123456789012345678901") is False


def test_is_channel_address() -> None:
    """Test is_channel_address."""
    for address in VIRTUAL_REMOTE_ADDRESSES:
        assert is_channel_address(f"{address}:13") is True
    assert is_channel_address("1234") is False
    assert is_channel_address("1234:2") is False
    assert is_channel_address("KEQ1234567:13") is True
    assert is_channel_address("001858A123B912:1") is True
    assert is_channel_address("1234567890:123") is True
    assert is_channel_address("123456789_:123") is False
    assert is_channel_address("ABcdEFghIJ1234567890:123") is True
    assert is_channel_address("12345678901234567890:123") is True
    assert is_channel_address("123456789012345678901:123") is False


def test_scheduler_profile_pattern() -> None:
    """Test the SCHEDULER_PROFILE_PATTERN."""
    assert SCHEDULER_PROFILE_PATTERN.match("P1_TEMPERATURE_THURSDAY_13")
    assert SCHEDULER_PROFILE_PATTERN.match("P1_ENDTIME_THURSDAY_13")
    assert SCHEDULER_PROFILE_PATTERN.match("P1_ENDTIME_THURSDAY_3")
    assert SCHEDULER_PROFILE_PATTERN.match("Px_ENDTIME_THURSDAY_13") is None
    assert SCHEDULER_PROFILE_PATTERN.match("P3_ENDTIME_THURSDAY_19") is None


def test_scheduler_time_pattern() -> None:
    """Test the SCHEDULER_TIME_PATTERN."""
    assert SCHEDULER_TIME_PATTERN.match("00:00")
    assert SCHEDULER_TIME_PATTERN.match("01:15")
    assert SCHEDULER_TIME_PATTERN.match("23:59")
    assert SCHEDULER_TIME_PATTERN.match("24:00")
    assert SCHEDULER_TIME_PATTERN.match("5:00")
    assert SCHEDULER_TIME_PATTERN.match("25:00") is None
    assert SCHEDULER_TIME_PATTERN.match("F:00") is None


def test_default_dict() -> None:
    """Test the default dict."""
    def_dict: Final[dict[str, dict[str, dict[ParamsetKey, dict[str, ParameterData]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )

    assert def_dict == {}
    assert def_dict["k1"] == {}
    assert def_dict["k1"]["k2"] == {}
    assert def_dict["k1"]["k2"][ParamsetKey.VALUES] == {}
    # assert def_dict["k1"]["k2"][ParamsetKey.VALUES]["k4"] == {}
    def_dict["k1"]["k2"][ParamsetKey.VALUES]["k4"] = ParameterData(ID="13")
    assert def_dict["k1"]["k2"][ParamsetKey.VALUES] == {"k4": ParameterData(ID="13")}
    def_dict["k1"]["k2"][ParamsetKey.VALUES] = {"k4.1": ParameterData(ID="14")}
    assert def_dict["k1"]["k2"][ParamsetKey.VALUES]["k4.1"] == ParameterData(ID="14")
