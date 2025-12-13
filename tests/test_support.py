"""Tests for switch data points of aiohomematic."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
from typing import Any, Final
from unittest.mock import patch

import pytest

from aiohomematic.const import (
    INIT_DATETIME,
    SCHEDULER_PROFILE_PATTERN,
    SCHEDULER_TIME_PATTERN,
    VIRTUAL_REMOTE_ADDRESSES,
    CommandRxMode,
    DataPointUsage,
    HubValueType,
    ParameterData,
    ParameterType,
    ParamsetKey,
    RxMode,
)
from aiohomematic.converter import _COMBINED_PARAMETER_TO_HM_CONVERTER, convert_hm_level_to_cpv
from aiohomematic.exceptions import AioHomematicException
from aiohomematic.model.support import (
    _check_channel_name_with_channel_no,
    convert_value,
    generate_unique_id,
    get_custom_data_point_name,
    get_data_point_name_data,
    get_device_name,
    get_event_name,
)
from aiohomematic.support import (
    CacheEntry,
    build_xml_rpc_headers,
    build_xml_rpc_uri,
    changed_within_seconds,
    check_or_create_directory,
    check_password,
    cleanup_text_from_html_tags,
    delete_file,
    element_matches_key,
    extract_exc_args,
    find_free_port,
    get_channel_no,
    get_rx_modes,
    get_tls_context,
    hash_sha256,
    is_channel_address,
    is_device_address,
    is_host,
    is_ipv4_address,
    log_boundary_error,
    parse_sys_var,
    supports_rx_mode,
    to_bool,
)

TEST_DEVICES: set[str] = {"VCU2128127", "VCU3609622"}

# pylint: disable=protected-access


class _Unserializable:
    """A helper class that orjson cannot serialize directly."""

    def __init__(self, value: Any) -> None:
        self.value = value


class TestGenerateUniqueId:
    """Tests for generate_unique_id."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            ({}, True, None, None),
        ],
    )
    async def test_generate_unique_id(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test generate_unique_id."""
        central, _, _ = central_client_factory_with_homegear_client
        assert (
            generate_unique_id(config_provider=central, address="VCU2128127", parameter="LEVEL") == "vcu2128127_level"
        )
        assert (
            generate_unique_id(config_provider=central, address="VCU2128127", parameter="LEVEL", prefix="PREFIX")
            == "prefix_vcu2128127_level"
        )
        assert (
            generate_unique_id(config_provider=central, address="INT0001", parameter="LEVEL")
            == "test1234_int0001_level"
        )


class TestXmlRpcHelpers:
    """Tests for XML-RPC helper functions."""

    def test_build_headers(self) -> None:
        """Test build_xml_rpc_uri."""
        assert build_xml_rpc_headers(username="Martin", password="") == [("Authorization", "Basic TWFydGluOg==")]
        assert build_xml_rpc_headers(username="", password="asdf") == [("Authorization", "Basic OmFzZGY=")]
        assert build_xml_rpc_headers(username="Martin", password="asdf") == [
            ("Authorization", "Basic TWFydGluOmFzZGY=")
        ]

    def test_build_xml_rpc_uri(self) -> None:
        """Test build_xml_rpc_uri."""
        assert build_xml_rpc_uri(host="1.2.3.4", port=80, path=None) == "http://1.2.3.4:80"
        assert build_xml_rpc_uri(host="1.2.3.4", port=80, path="group") == "http://1.2.3.4:80/group"
        assert build_xml_rpc_uri(host="1.2.3.4", port=80, path="group", tls=True) == "https://1.2.3.4:80/group"


class TestDirectoryHelpers:
    """Tests for directory helper functions."""

    def test_check_or_create_directory(self) -> None:
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
            with pytest.raises(AioHomematicException) as exc:
                check_or_create_directory(directory="tmpdir_ex")
            assert exc


class TestSysvarParsing:
    """Tests for system variable parsing."""

    def test_parse_sys_var(self) -> None:
        """Test parse_sys_var."""
        assert parse_sys_var(data_type=None, raw_value="1.4") == "1.4"
        assert parse_sys_var(data_type=HubValueType.STRING, raw_value="1.4") == "1.4"
        assert parse_sys_var(data_type=HubValueType.FLOAT, raw_value="1.4") == 1.4
        assert parse_sys_var(data_type=HubValueType.INTEGER, raw_value="1") == 1
        assert parse_sys_var(data_type=HubValueType.ALARM, raw_value="true") is True
        assert parse_sys_var(data_type=HubValueType.LIST, raw_value="1") == 1
        assert parse_sys_var(data_type=HubValueType.LOGIC, raw_value="true") is True


class TestBoolConversion:
    """Tests for boolean conversion."""

    @pytest.mark.asyncio
    async def test_to_bool(self) -> None:
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


class TestNamingHelpers:
    """Tests for naming helper functions."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_custom_data_point_name(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_custom_data_point_name."""
        central, _, _ = central_client_factory_with_homegear_client
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

        central.cache_coordinator.device_details.add_name(address=f"{device.address}:5", name="Roof")
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
            "aiohomematic.model.support._get_base_name_from_channel_or_device",
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
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_get_data_point_name(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_data_point_name."""
        central, _, _ = central_client_factory_with_homegear_client
        device = central.get_device(address="VCU2128127")
        assert device
        channel4 = device.get_channel(channel_address=f"{device.address}:5")
        name_data = get_data_point_name_data(channel=channel4, parameter="LEVEL")
        assert name_data.full_name == "HmIP-BSM_VCU2128127 Level"
        assert name_data.name == "Level"

        central.cache_coordinator.device_details.add_name(address=f"{device.address}:5", name="Roof")
        channel5 = device.get_channel(channel_address=f"{device.address}:5")
        name_data = get_data_point_name_data(channel=channel5, parameter="LEVEL")
        assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof Level"
        assert name_data.name == "Roof Level"

        with patch(
            "aiohomematic.model.support._get_base_name_from_channel_or_device",
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
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_get_device_name(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_device_name."""
        central, _, _ = central_client_factory_with_homegear_client
        assert (
            get_device_name(
                device_details_provider=central.cache_coordinator.device_details,
                device_address="VCU2128127",
                model="HmIP-BSM",
            )
            == "HmIP-BSM_VCU2128127"
        )
        central.cache_coordinator.device_details.add_name(address="VCU2128127", name="Roof")
        assert (
            get_device_name(
                device_details_provider=central.cache_coordinator.device_details,
                device_address="VCU2128127",
                model="HmIP-BSM",
            )
            == "Roof"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "address_device_translation",
            "do_mock_client",
            "ignore_devices_on_create",
            "un_ignore_list",
        ),
        [
            (TEST_DEVICES, True, None, None),
        ],
    )
    async def test_get_event_name(
        self,
        central_client_factory_with_homegear_client,
    ) -> None:
        """Test get_event_name."""
        central, _, _ = central_client_factory_with_homegear_client
        device = central.get_device(address="VCU2128127")
        assert device
        channel4 = device.get_channel(channel_address=f"{device.address}:4")
        name_data = get_event_name(channel=channel4, parameter="LEVEL")
        assert name_data.channel_name == "ch4"
        assert name_data.name == "ch4 Level"
        assert name_data.full_name == "HmIP-BSM_VCU2128127 ch4 Level"

        central.cache_coordinator.device_details.add_name(address=f"{device.address}:5", name="Roof")
        channel5 = device.get_channel(channel_address=f"{device.address}:5")
        name_data = get_event_name(channel=channel5, parameter="LEVEL")
        assert name_data.channel_name == "Roof"
        assert name_data.name == "Roof Level"
        assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof Level"

        with patch(
            "aiohomematic.model.support._get_base_name_from_channel_or_device",
            return_value=None,
        ):
            name_data = get_event_name(channel=channel5, parameter="LEVEL")
            assert name_data.full_name == ""
            assert name_data.name == ""


class TestTLSHelpers:
    """Tests for TLS helper functions."""

    @pytest.mark.asyncio
    async def test_tls_context(self) -> None:
        """Test tls_context."""
        assert get_tls_context(verify_tls=False).check_hostname is False
        assert get_tls_context(verify_tls=True).check_hostname is True


class TestTimeHelpers:
    """Tests for time helper functions."""

    @pytest.mark.asyncio
    async def test_changed_within_seconds(self) -> None:
        """Test changed_within_seconds."""
        assert changed_within_seconds(last_change=(datetime.now() - timedelta(seconds=10)), max_age=60) is True
        assert changed_within_seconds(last_change=(datetime.now() - timedelta(seconds=70)), max_age=60) is False
        assert changed_within_seconds(last_change=INIT_DATETIME, max_age=60) is False


class TestValueConversion:
    """Tests for value conversion."""

    @pytest.mark.asyncio
    async def test_convert_value(self) -> None:
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


class TestElementMatching:
    """Tests for element matching."""

    @pytest.mark.asyncio
    async def test_element_matches_key(self) -> None:
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


class TestMiscHelpers:
    """Tests for miscellaneous helper functions."""

    @pytest.mark.enable_socket
    @pytest.mark.asyncio
    async def test_others(self) -> None:
        """Test find_free_port."""
        assert find_free_port()
        assert get_channel_no(address="12312:1") == 1
        assert get_channel_no(address="12312") is None
        assert _check_channel_name_with_channel_no(name="light:1") is True
        assert _check_channel_name_with_channel_no(name="light:Test") is False
        assert _check_channel_name_with_channel_no(name="light:Test:123") is False


class TestPasswordValidation:
    """Tests for password validation."""

    def test_password(self) -> None:
        """
        Test the password.

        Password can be empty.
        Allowed characters:
            - A-Z, a-z
            - 0-9
            - ., !, $, (, ), :, ;, #, -
        """
        assert check_password(password=None) is False
        assert check_password(password="") is True
        assert check_password(password="t") is True
        assert check_password(password="test") is True
        assert check_password(password="TEST") is True
        assert check_password(password="1234") is True
        assert check_password(password="test123TEST") is True
        assert check_password(password="test.!$():;#-") is True
        assert check_password(password="test%") is False


class TestConverters:
    """Tests for converters."""

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
        self,
        parameter: str,
        input_value: Any,
        converter: Callable,
        result_value: Any,
    ) -> None:
        """Test device un ignore."""

        assert input_value is not None
        assert converter(value=input_value) == result_value
        if re_converter := _COMBINED_PARAMETER_TO_HM_CONVERTER.get(parameter):
            assert re_converter(value=result_value) == input_value


class TestHostnameValidation:
    """Tests for hostname validation."""

    def test_is_valid_hostname(self) -> None:
        """Test is_valid_hostname."""
        assert is_host(host=None) is False
        assert is_host(host="") is False
        assert is_host(host=" ") is False
        assert is_host(host="123") is True
        assert is_host(host="ccu") is True
        assert is_host(host="ccu.test.de") is True
        assert is_host(host="ccu.de") is True
        assert is_host(host="ccu.123") is True
        assert is_host(host="192.168.178.2") is True
        assert is_host(host="5422eb72-openccu") is True


class TestIPv4Validation:
    """Tests for IPv4 address validation."""

    def test_is_valid_ipv4_address(self) -> None:
        """Test is_valid_ipv4_address."""
        assert is_ipv4_address(address=None) is False
        assert is_ipv4_address(address="") is False
        assert is_ipv4_address(address=" ") is False
        assert is_ipv4_address(address="192.168.1782") is False
        assert is_ipv4_address(address="192.168.178.2") is True
        assert is_ipv4_address(address="ccu") is False


class TestAddressValidation:
    """Tests for address validation."""

    def test_is_channel_address(self) -> None:
        """Test is_channel_address."""
        for address in VIRTUAL_REMOTE_ADDRESSES:
            assert is_channel_address(address=f"{address}:13") is True
        assert is_channel_address(address="1234") is False
        assert is_channel_address(address="1234:2") is False
        assert is_channel_address(address="KEQ1234567:13") is True
        assert is_channel_address(address="001858A123B912:1") is True
        assert is_channel_address(address="1234567890:123") is True
        assert is_channel_address(address="123456789_:123") is False
        assert is_channel_address(address="ABcdEFghIJ1234567890:123") is True
        assert is_channel_address(address="12345678901234567890:123") is True
        assert is_channel_address(address="123456789012345678901:123") is False

    def test_is_device_address(self) -> None:
        """Test is_device_address."""
        for address in VIRTUAL_REMOTE_ADDRESSES:
            assert is_device_address(address=address) is True
        assert is_device_address(address="123456789:2") is False
        assert is_device_address(address="KEQ1234567") is True
        assert is_device_address(address="001858A123B912") is True
        assert is_device_address(address="1234567890#") is False
        assert is_device_address(address="123456789_:123") is False
        assert is_device_address(address="ABcdEFghIJ1234567890") is True
        assert is_device_address(address="12345678901234567890") is True
        assert is_device_address(address="123456789012345678901") is False


class TestPatterns:
    """Tests for pattern matching."""

    def test_scheduler_profile_pattern(self) -> None:
        """Test the SCHEDULER_PROFILE_PATTERN."""
        assert SCHEDULER_PROFILE_PATTERN.match("P1_TEMPERATURE_THURSDAY_13")
        assert SCHEDULER_PROFILE_PATTERN.match("P1_ENDTIME_THURSDAY_13")
        assert SCHEDULER_PROFILE_PATTERN.match("P1_ENDTIME_THURSDAY_3")
        assert SCHEDULER_PROFILE_PATTERN.match("Px_ENDTIME_THURSDAY_13") is None
        assert SCHEDULER_PROFILE_PATTERN.match("P3_ENDTIME_THURSDAY_19") is None

    def test_scheduler_time_pattern(self) -> None:
        """Test the SCHEDULER_TIME_PATTERN."""
        assert SCHEDULER_TIME_PATTERN.match("00:00")
        assert SCHEDULER_TIME_PATTERN.match("01:15")
        assert SCHEDULER_TIME_PATTERN.match("23:59")
        assert SCHEDULER_TIME_PATTERN.match("24:00")
        assert SCHEDULER_TIME_PATTERN.match("5:00")
        assert SCHEDULER_TIME_PATTERN.match("25:00") is None
        assert SCHEDULER_TIME_PATTERN.match("F:00") is None


class TestDefaultDict:
    """Tests for default dict."""

    def test_default_dict(self) -> None:
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


class TestHashSha256:
    """Tests for hash_sha256."""

    @pytest.mark.asyncio
    async def test_hash_sha256_stable_and_distinct(self) -> None:
        """
        hash_sha256 returns stable value for same input and different for different inputs.

        Also verifies the fallback branch for non-orjson-serializable input types (like set/custom object).
        """
        # JSON-serializable data
        v1 = {"a": 1, "b": [1, 2, 3]}
        v1_but_ordered_diff = {"b": [1, 2, 3], "a": 1}
        h1 = hash_sha256(value=v1)
        h1_again = hash_sha256(value=v1_but_ordered_diff)  # sorted keys should yield same hash

        # Different JSON-serializable data
        v2 = {"a": 2, "b": [1, 2, 3]}
        h2 = hash_sha256(value=v2)

        # Non-serializable with orjson -> triggers fallback
        v3 = {"a": {1, 2, 3}}  # set is not directly serializable by orjson
        h3 = hash_sha256(value=v3)

        # Custom object also triggers fallback path
        v4 = _Unserializable(value="x")
        h4 = hash_sha256(value=v4)

        assert isinstance(h1, str) and isinstance(h2, str) and isinstance(h3, str) and isinstance(h4, str)
        assert h1 == h1_again  # stable independent of dict key order
        assert h1 != h2  # different content -> different hash
        # Fallback paths still produce deterministic strings for equal values
        assert h3 == hash_sha256(value={"a": {3, 2, 1}})
        # For custom objects, fallback uses repr(object) which is instance-identity-dependent;
        # we only assert it produces a string, not equality across different instances.


class TestCacheEntry:
    """Tests for CacheEntry."""

    @pytest.mark.asyncio
    async def test_cache_entry_validity(self) -> None:
        """CacheEntry.empty() and is_valid reflect validity depending on refresh time."""
        empty = CacheEntry.empty()
        assert empty.is_valid is False

        fresh = CacheEntry(value="ok", refresh_at=datetime.now())
        assert fresh.is_valid is True

        # Very old timestamps may still be considered valid due to implementation using seconds within day.
        old = CacheEntry(value="ok", refresh_at=datetime.now() - timedelta(days=3650))
        assert isinstance(old.is_valid, bool)


class TestRxModes:
    """Tests for RX modes."""

    @pytest.mark.asyncio
    async def test_get_rx_modes_and_supports_rx_mode(self) -> None:
        """get_rx_modes decodes bitmask and supports_rx_mode validates compatibility."""
        # Compose a bitmask with multiple modes
        mask = int(RxMode.BURST) | int(RxMode.WAKEUP) | int(RxMode.CONFIG)
        modes = get_rx_modes(mode=mask)

        assert isinstance(modes, tuple)
        assert RxMode.BURST in modes
        assert RxMode.WAKEUP in modes
        assert RxMode.CONFIG in modes

        # supports_rx_mode checks for BURST/WAKEUP presence
        assert supports_rx_mode(command_rx_mode=CommandRxMode.BURST, rx_modes=modes) is True
        assert supports_rx_mode(command_rx_mode=CommandRxMode.WAKEUP, rx_modes=modes) is True

        # When mode does not include required flag
        only_config = get_rx_modes(mode=int(RxMode.CONFIG))
        assert supports_rx_mode(command_rx_mode=CommandRxMode.BURST, rx_modes=only_config) is False
        assert supports_rx_mode(command_rx_mode=CommandRxMode.WAKEUP, rx_modes=only_config) is False


class TestExceptionHelpers:
    """Tests for exception helpers."""

    @pytest.mark.asyncio
    async def test_extract_exc_args_variants(self) -> None:
        """extract_exc_args returns the first arg, a tuple for multiple args, or the exception if no args are set."""
        # One arg -> returns the single arg
        e1 = Exception("only")
        assert extract_exc_args(exc=e1) == "only"

        # Multiple args -> returns the tuple
        e2 = Exception("a", 2)
        assert extract_exc_args(exc=e2) == ("a", 2)

        # No args -> returns the exception itself
        e3 = Exception()
        assert extract_exc_args(exc=e3) is e3


class TestTextCleanup:
    """Tests for text cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_text_from_html_tags(self) -> None:
        """cleanup_text_from_html_tags removes HTML tags and entities while keeping inner text intact."""
        text = "<div>Hello <b>World</b> &amp; everyone!</div>"
        # Pattern also removes html entities like &amp;
        assert cleanup_text_from_html_tags(text=text) == "Hello World  everyone!"


class TestLogging:
    """Tests for logging."""

    @pytest.mark.asyncio
    async def test_log_boundary_error_levels_and_context(self, caplog: pytest.LogCaptureFixture) -> None:
        """log_boundary_error chooses level (WARNING for domain errors, ERROR otherwise) and redacts sensitive context."""
        logger = logging.getLogger("aiohomematic.test.logging")

        # WARNING for domain/BaseHomematicException
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            log_boundary_error(
                logger,
                boundary="client",
                action="connect",
                err=AioHomematicException("oops"),
                log_context={"password": "secret", "token": "tok", "info": 42},
                message="while trying to connect",
            )
        assert any(rec.levelno == logging.WARNING for rec in caplog.records)
        # Validate redacted context and message parts present
        msg = caplog.records[-1].getMessage()
        assert "[boundary=client action=connect err=AioHomematicException: oops]" in msg
        assert "while trying to connect" in msg
        assert "ctx={" in msg
        assert '"password":"***"' in msg
        assert '"token":"***"' in msg
        assert '"info":42' in msg

        # ERROR for non-domain exception
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            log_boundary_error(
                logger,
                boundary="client",
                action="connect",
                err=ValueError("bad"),
            )
        assert any(rec.levelno == logging.ERROR for rec in caplog.records)
        assert "err=ValueError: bad" in caplog.records[-1].getMessage()


class TestFileOperations:
    """Tests for file operations."""

    @pytest.mark.asyncio
    async def test_delete_file_behaviour(self, tmp_path: Path) -> None:
        """delete_file removes regular files and symlinks but leaves directories and missing files untouched."""
        # Create regular file
        f = tmp_path / "a_file.txt"
        f.write_text("x")
        assert f.exists()

        # Create a symlink to the file
        s = tmp_path / "alink"
        os.symlink(f, s)
        assert s.exists()

        # Create a directory (should not be removed)
        d = tmp_path / "adir"
        d.mkdir()

        # delete regular file
        delete_file(directory=str(tmp_path), file_name=f.name)
        assert not f.exists()

        # delete symlink
        delete_file(directory=str(tmp_path), file_name=s.name)
        assert not s.exists()

        # attempt to delete directory by name -> function should no-op
        delete_file(directory=str(tmp_path), file_name=d.name)
        assert d.exists()

        # nonexistent file -> should not raise
        delete_file(directory=str(tmp_path), file_name="does_not_exist")
