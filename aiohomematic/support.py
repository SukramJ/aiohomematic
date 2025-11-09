# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2025
"""
Helper functions used within aiohomematic.

Public API of this module is defined by __all__.
"""

from __future__ import annotations

import base64
from collections import defaultdict
from collections.abc import Collection, Mapping
import contextlib
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import glob
import hashlib
import inspect
from ipaddress import IPv4Address
import logging
import os
import random
import re
import socket
import ssl
import sys
from typing import Any, Final

import orjson

from aiohomematic import i18n
from aiohomematic.const import (
    ADDRESS_SEPARATOR,
    ALLOWED_HOSTNAME_PATTERN,
    CCU_PASSWORD_PATTERN,
    CHANNEL_ADDRESS_PATTERN,
    DEVICE_ADDRESS_PATTERN,
    HTMLTAG_PATTERN,
    INIT_DATETIME,
    ISO_8859_1,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    TIMEOUT,
    UTF_8,
    CommandRxMode,
    DeviceDescription,
    ParamsetKey,
    RxMode,
    SysvarType,
)
from aiohomematic.exceptions import AioHomematicException, BaseHomematicException
from aiohomematic.property_decorators import Kind, get_hm_property_by_kind, get_hm_property_by_log_context, hm_property

_LOGGER: Final = logging.getLogger(__name__)


def extract_exc_args(*, exc: Exception) -> tuple[Any, ...] | Any:
    """Return the first arg, if there is only one arg."""
    if exc.args:
        return exc.args[0] if len(exc.args) == 1 else exc.args
    return exc


def build_xml_rpc_uri(
    *,
    host: str,
    port: int | None,
    path: str | None,
    tls: bool = False,
) -> str:
    """Build XML-RPC API URL from components."""
    scheme = "http"
    s_port = f":{port}" if port else ""
    if not path:
        path = ""
    if path and not path.startswith("/"):
        path = f"/{path}"
    if tls:
        scheme += "s"
    return f"{scheme}://{host}{s_port}{path}"


def build_xml_rpc_headers(
    *,
    username: str,
    password: str,
) -> list[tuple[str, str]]:
    """Build XML-RPC API header."""
    cred_bytes = f"{username}:{password}".encode()
    base64_message = base64.b64encode(cred_bytes).decode(ISO_8859_1)
    return [("Authorization", f"Basic {base64_message}")]


def delete_file(directory: str, file_name: str) -> None:  # kwonly: disable
    """Delete the file. File can contain a wildcard."""
    if os.path.exists(directory):
        for file_path in glob.glob(os.path.join(directory, file_name)):
            if os.path.isfile(file_path):
                os.remove(file_path)


def check_or_create_directory(*, directory: str) -> bool:
    """Check / create directory."""
    if not directory:
        return False
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as oserr:
            raise AioHomematicException(
                i18n.tr(
                    "exception.support.check_or_create_directory.failed",
                    directory=directory,
                    reason=oserr.strerror,
                )
            ) from oserr
    return True


def extract_device_addresses_from_device_descriptions(
    *, device_descriptions: tuple[DeviceDescription, ...]
) -> tuple[str, ...]:
    """Extract addresses from device descriptions."""
    return tuple(
        {
            parent_address
            for dev_desc in device_descriptions
            if (parent_address := dev_desc.get("PARENT")) and (is_device_address(address=parent_address))
        }
    )


def parse_sys_var(*, data_type: SysvarType | None, raw_value: Any) -> Any:
    """Parse system variables to fix type."""
    if not data_type:
        return raw_value
    if data_type in (SysvarType.ALARM, SysvarType.LOGIC):
        return to_bool(value=raw_value)
    if data_type == SysvarType.FLOAT:
        return float(raw_value)
    if data_type in (SysvarType.INTEGER, SysvarType.LIST):
        return int(raw_value)
    return raw_value


def to_bool(*, value: Any) -> bool:
    """Convert defined string values to bool."""
    if isinstance(value, bool):
        return value

    if not isinstance(value, str):
        raise TypeError(i18n.tr("exception.support.boolean.invalid_type"))

    return value.lower() in ["y", "yes", "t", "true", "on", "1"]


def check_password(*, password: str | None) -> bool:
    """Check password."""
    if password is None:
        return False
    if CCU_PASSWORD_PATTERN.fullmatch(password) is None:
        _LOGGER.error(
            i18n.tr(
                "log.support.check_password.invalid_chars",
                pattern=CCU_PASSWORD_PATTERN.pattern,
            )
        )
        return False
    return True


def regular_to_default_dict_hook(origin: dict[str, Any], /) -> defaultdict[Any, Any]:
    """Use defaultdict in json.loads object_hook."""

    def new_dict() -> defaultdict[Any, Any]:
        return defaultdict(new_dict)

    new_instance: defaultdict[Any, Any] = new_dict()
    new_instance.update(origin)
    return new_instance


def _create_tls_context(*, verify_tls: bool) -> ssl.SSLContext:
    """Create tls verified/unverified context."""
    sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if not verify_tls:
        sslcontext.check_hostname = False
        sslcontext.verify_mode = ssl.CERT_NONE
    with contextlib.suppress(AttributeError):
        # This only works for OpenSSL >= 1.0.0
        sslcontext.options |= ssl.OP_NO_COMPRESSION
    sslcontext.set_default_verify_paths()
    return sslcontext


_DEFAULT_NO_VERIFY_SSL_CONTEXT = _create_tls_context(verify_tls=False)
_DEFAULT_SSL_CONTEXT = _create_tls_context(verify_tls=True)


def get_tls_context(*, verify_tls: bool) -> ssl.SSLContext:
    """Return tls verified/unverified context."""
    return _DEFAULT_SSL_CONTEXT if verify_tls else _DEFAULT_NO_VERIFY_SSL_CONTEXT


def get_channel_address(*, device_address: str, channel_no: int | None) -> str:
    """Return the channel address."""
    return device_address if channel_no is None else f"{device_address}:{channel_no}"


def get_device_address(*, address: str) -> str:
    """Return the device part of an address."""
    return get_split_channel_address(channel_address=address)[0]


def get_channel_no(*, address: str) -> int | None:
    """Return the channel part of an address."""
    return get_split_channel_address(channel_address=address)[1]


def is_address(*, address: str) -> bool:
    """Check if it is a address."""
    return is_device_address(address=address) or is_channel_address(address=address)


def is_channel_address(*, address: str) -> bool:
    """Check if it is a channel address."""
    return CHANNEL_ADDRESS_PATTERN.match(address) is not None


def is_device_address(*, address: str) -> bool:
    """Check if it is a device address."""
    return DEVICE_ADDRESS_PATTERN.match(address) is not None


def is_paramset_key(*, paramset_key: ParamsetKey | str) -> bool:
    """Check if it is a paramset key."""
    return isinstance(paramset_key, ParamsetKey) or (isinstance(paramset_key, str) and paramset_key in ParamsetKey)


@lru_cache(maxsize=4096)
def get_split_channel_address(*, channel_address: str) -> tuple[str, int | None]:
    """
    Return the device part of an address.

    Cached to avoid redundant parsing across layers when repeatedly handling
    the same channel addresses.
    """
    if ADDRESS_SEPARATOR in channel_address:
        device_address, channel_no = channel_address.split(ADDRESS_SEPARATOR)
        if channel_no in (None, "None"):
            return device_address, None
        return device_address, int(channel_no)
    return channel_address, None


def changed_within_seconds(*, last_change: datetime, max_age: int = MAX_CACHE_AGE) -> bool:
    """DataPoint has been modified within X minutes."""
    if last_change == INIT_DATETIME:
        return False
    delta = datetime.now() - last_change
    return delta.seconds < max_age


def find_free_port() -> int:
    """Find a free port for XmlRpc server default port."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def get_ip_addr(host: str, port: int, /) -> str | None:
    """Get local_ip from socket."""
    try:
        socket.gethostbyname(host)
    except Exception as exc:
        raise AioHomematicException(
            i18n.tr(
                "exception.support.get_local_ip.resolve_failed",
                host=host,
                port=port,
                reason=extract_exc_args(exc=exc),
            )
        ) from exc
    tmp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tmp_socket.settimeout(TIMEOUT)
    tmp_socket.connect((host, port))
    local_ip = str(tmp_socket.getsockname()[0])
    tmp_socket.close()
    _LOGGER.debug("GET_LOCAL_IP: Got local ip: %s", local_ip)
    return local_ip


def is_hostname(*, hostname: str | None) -> bool:
    """Return True if hostname is valid."""
    if not hostname:
        return False
    if hostname[-1] == ".":
        # strip exactly one dot from the right, if present
        hostname = hostname[:-1]
    if len(hostname) > 253 or len(hostname) < 1:
        return False

    labels = hostname.split(".")

    # the TLD must be not all-numeric
    if re.match(r"[0-9]+$", labels[-1]):
        return False

    return all(ALLOWED_HOSTNAME_PATTERN.match(label) for label in labels)


def is_ipv4_address(*, address: str | None) -> bool:
    """Return True if ipv4_address is valid."""
    if not address:
        return False
    try:
        IPv4Address(address=address)
    except ValueError:
        return False
    return True


def is_port(*, port: int) -> bool:
    """Return True if port is valid."""
    return 0 <= port <= 65535


@lru_cache(maxsize=2048)
def _element_matches_key_cached(
    *,
    search_elements: tuple[str, ...] | str,
    compare_with: str,
    ignore_case: bool,
    do_left_wildcard_search: bool,
    do_right_wildcard_search: bool,
) -> bool:
    """Cache element matching for hashable inputs."""
    compare_with_processed = compare_with.lower() if ignore_case else compare_with

    if isinstance(search_elements, str):
        element = search_elements.lower() if ignore_case else search_elements
        if do_left_wildcard_search is True and do_right_wildcard_search is True:
            return element in compare_with_processed
        if do_left_wildcard_search:
            return compare_with_processed.endswith(element)
        if do_right_wildcard_search:
            return compare_with_processed.startswith(element)
        return compare_with_processed == element

    # search_elements is a tuple
    for item in search_elements:
        element = item.lower() if ignore_case else item
        if do_left_wildcard_search is True and do_right_wildcard_search is True:
            if element in compare_with_processed:
                return True
        elif do_left_wildcard_search:
            if compare_with_processed.endswith(element):
                return True
        elif do_right_wildcard_search:
            if compare_with_processed.startswith(element):
                return True
        elif compare_with_processed == element:
            return True
    return False


def element_matches_key(
    *,
    search_elements: str | Collection[str],
    compare_with: str | None,
    search_key: str | None = None,
    ignore_case: bool = True,
    do_left_wildcard_search: bool = False,
    do_right_wildcard_search: bool = True,
) -> bool:
    """
    Return if collection element is key.

    Default search uses a right wildcard.
    A set search_key assumes that search_elements is initially a dict,
    and it tries to identify a matching key (wildcard) in the dict keys to use it on the dict.
    """
    if compare_with is None or not search_elements:
        return False

    # Handle dict case with search_key
    if isinstance(search_elements, dict) and search_key:
        if match_key := _get_search_key(search_elements=search_elements, search_key=search_key):
            if (elements := search_elements.get(match_key)) is None:
                return False
            search_elements = elements
        else:
            return False

    search_elements_hashable: str | Collection[str]
    # Convert to hashable types for caching
    if isinstance(search_elements, str):
        search_elements_hashable = search_elements
    elif isinstance(search_elements, (list, set)):
        search_elements_hashable = tuple(search_elements)
    elif isinstance(search_elements, tuple):
        search_elements_hashable = search_elements
    else:
        # Fall back to non-cached version for other collection types
        compare_with_processed = compare_with.lower() if ignore_case else compare_with
        for item in search_elements:
            element = item.lower() if ignore_case else item
            if do_left_wildcard_search is True and do_right_wildcard_search is True:
                if element in compare_with_processed:
                    return True
            elif do_left_wildcard_search:
                if compare_with_processed.endswith(element):
                    return True
            elif do_right_wildcard_search:
                if compare_with_processed.startswith(element):
                    return True
            elif compare_with_processed == element:
                return True
        return False

    return _element_matches_key_cached(
        search_elements=search_elements_hashable,
        compare_with=compare_with,
        ignore_case=ignore_case,
        do_left_wildcard_search=do_left_wildcard_search,
        do_right_wildcard_search=do_right_wildcard_search,
    )


def _get_search_key(*, search_elements: Collection[str], search_key: str) -> str | None:
    """Search for a matching key in a collection."""
    for element in search_elements:
        if search_key.startswith(element):
            return element
    return None


@dataclass(frozen=True, kw_only=True, slots=True)
class CacheEntry:
    """An entry for the value cache."""

    value: Any
    refresh_at: datetime

    @staticmethod
    def empty() -> CacheEntry:
        """Return empty cache entry."""
        return CacheEntry(value=NO_CACHE_ENTRY, refresh_at=datetime.min)

    @property
    def is_valid(self) -> bool:
        """Return if entry is valid."""
        if self.value == NO_CACHE_ENTRY:
            return False
        return changed_within_seconds(last_change=self.refresh_at)


def debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    try:
        if sys.gettrace() is not None:
            return True
    except AttributeError:
        pass

    try:
        if sys.monitoring.get_tool(sys.monitoring.DEBUGGER_ID) is not None:
            return True
    except AttributeError:
        pass

    return False


def hash_sha256(*, value: Any) -> str:
    """
    Hash a value with sha256.

    Uses orjson to serialize the value with sorted keys for a fast and stable
    representation. Falls back to the repr-based approach if
    serialization fails (e.g., unsupported types).
    """
    hasher = hashlib.sha256()
    try:
        data = orjson.dumps(value, option=orjson.OPT_SORT_KEYS | orjson.OPT_NON_STR_KEYS)
    except Exception:
        # Fallback: convert to a hashable representation and use repr()
        data = repr(_make_value_hashable(value=value)).encode(encoding=UTF_8)
    hasher.update(data)
    return base64.b64encode(hasher.digest()).decode(encoding=UTF_8)


def _make_value_hashable(*, value: Any) -> Any:
    """Make a hashable object."""
    if isinstance(value, tuple | list):
        return tuple(_make_value_hashable(value=e) for e in value)

    if isinstance(value, dict):
        return tuple(sorted((k, _make_value_hashable(value=v)) for k, v in value.items()))

    if isinstance(value, set | frozenset):
        return tuple(sorted(_make_value_hashable(value=e) for e in value))

    return value


def get_rx_modes(*, mode: int | None) -> tuple[RxMode, ...]:
    """Convert int to rx modes."""
    if mode is None:
        return ()
    rx_modes: set[RxMode] = set()
    if mode & RxMode.LAZY_CONFIG:
        mode -= RxMode.LAZY_CONFIG
        rx_modes.add(RxMode.LAZY_CONFIG)
    if mode & RxMode.WAKEUP:
        mode -= RxMode.WAKEUP
        rx_modes.add(RxMode.WAKEUP)
    if mode & RxMode.CONFIG:
        mode -= RxMode.CONFIG
        rx_modes.add(RxMode.CONFIG)
    if mode & RxMode.BURST:
        mode -= RxMode.BURST
        rx_modes.add(RxMode.BURST)
    if mode & RxMode.ALWAYS:
        rx_modes.add(RxMode.ALWAYS)
    return tuple(rx_modes)


def supports_rx_mode(*, command_rx_mode: CommandRxMode, rx_modes: tuple[RxMode, ...]) -> bool:
    """Check if rx mode is supported."""
    return (command_rx_mode == CommandRxMode.BURST and RxMode.BURST in rx_modes) or (
        command_rx_mode == CommandRxMode.WAKEUP and RxMode.WAKEUP in rx_modes
    )


def cleanup_text_from_html_tags(*, text: str) -> str:
    """Cleanup text from html tags."""
    return re.sub(HTMLTAG_PATTERN, "", text)


def create_random_device_addresses(*, addresses: list[str]) -> dict[str, str]:
    """Create a random device address."""
    return {adr: f"VCU{int(random.randint(1000000, 9999999))}" for adr in addresses}


def shrink_json_file(file_name: str) -> None:
    """Shrink a json file."""
    with open(file_name, "rb") as f:
        data = orjson.loads(f.read())

    with open(file_name, "wb") as f:
        f.write(orjson.dumps(data))


# --- Structured error boundary logging helpers ---

_BOUNDARY_MSG = "error_boundary"


def _safe_log_context(*, context: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract safe context from a mapping."""
    ctx: dict[str, Any] = {}
    if not context:
        return ctx
    # Avoid logging potentially sensitive values by redacting common keys
    redact_keys = {"password", "passwd", "pwd", "token", "authorization", "auth"}
    for k, v in context.items():
        if k.lower() in redact_keys:
            ctx[k] = "***"
        else:
            # Ensure value is serializable / printable
            try:
                str(v)
                ctx[k] = v
            except Exception:
                ctx[k] = repr(v)
    return ctx


def log_boundary_error(
    logger: logging.Logger,
    *,
    boundary: str,
    action: str,
    err: Exception,
    level: int | None = None,
    log_context: Mapping[str, Any] | None = None,
    message: str | None = None,
) -> None:
    """
    Log a boundary error with the provided logger.

    This function differentiates
    between recoverable and non-recoverable domain errors to select an appropriate
    logging level if not explicitly provided. Additionally, it enriches the log
    record with extra context about the error and action boundaries.

    """
    err_name = err.__class__.__name__
    log_message = f"[boundary={boundary} action={action} err={err_name}"

    if (err_args := extract_exc_args(exc=err)) and err_args != err_name:
        log_message += f": {err_args}"
    log_message += "]"

    if message:
        log_message += f" {message}"

    if log_context:
        log_message += f" ctx={orjson.dumps(_safe_log_context(context=log_context), option=orjson.OPT_SORT_KEYS).decode(encoding=UTF_8)}"

    # Choose level if not provided:
    if (chosen_level := level) is None:
        # Use WARNING for expected/recoverable domain errors, ERROR otherwise.
        chosen_level = logging.WARNING if isinstance(err, BaseHomematicException) else logging.ERROR

    logger.log(chosen_level, log_message)


class LogContextMixin:
    """Mixin to add log context methods to class."""

    __slots__ = ("_cached_log_context",)

    @hm_property(cached=True)
    def log_context(self) -> Mapping[str, Any]:
        """Return the log context for this object."""
        return {
            key: value for key, value in get_hm_property_by_log_context(data_object=self).items() if value is not None
        }


class PayloadMixin:
    """Mixin to add payload methods to class."""

    __slots__ = ()

    @property
    def config_payload(self) -> Mapping[str, Any]:
        """Return the config payload."""
        return {
            key: value
            for key, value in get_hm_property_by_kind(data_object=self, kind=Kind.CONFIG).items()
            if value is not None
        }

    @property
    def info_payload(self) -> Mapping[str, Any]:
        """Return the info payload."""
        return {
            key: value
            for key, value in get_hm_property_by_kind(data_object=self, kind=Kind.INFO).items()
            if value is not None
        }

    @property
    def state_payload(self) -> Mapping[str, Any]:
        """Return the state payload."""
        return {
            key: value
            for key, value in get_hm_property_by_kind(data_object=self, kind=Kind.STATE).items()
            if value is not None
        }


# Define public API for this module
__all__ = tuple(
    sorted(
        name
        for name, obj in globals().items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.isclass(obj))
        and getattr(obj, "__module__", __name__) == __name__
    )
)
