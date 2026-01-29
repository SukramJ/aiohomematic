#!/usr/bin/env python3
"""
Issue analyzer script for AioHomematic and Homematic(IP) Local.

This script uses Claude AI to analyze newly created issues and provide helpful feedback.
It includes deep analysis of attached diagnostic files and log files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
import sys
from typing import Any, Final, cast

from anthropic import Anthropic
from github import Auth, Github, GithubException, Repository
import requests

# Valid major version range for Homematic(IP) Local
# Version 1.x.x was the original, 2.x.x is current, 3.x.x reserved for future
VALID_MAJOR_VERSIONS = (1, 2, 3)

# Integration repository for version lookups
INTEGRATION_REPO = "SukramJ/homematicip_local"

# Cached version info (populated on first use)
_cached_versions: dict[str, str | None] = {}

# Maximum file size to download (5 MB)
MAX_ATTACHMENT_SIZE: Final = 5 * 1024 * 1024

# Log analysis patterns with priorities (lower = higher priority)
# These patterns help identify the root cause of issues
LOG_PATTERNS: Final[dict[str, dict[str, Any]]] = {
    "no_subscribers": {
        "pattern": r"No subscribers for (?:Rpc)?ParameterReceivedEvent.*?\[([A-Za-z0-9]+:\d+)\]",
        "description_de": "Gerät sendet Events, aber keine HA-Entität ist registriert",
        "description_en": "Device sends events but no HA entity is registered",
        "priority": 1,
        "category": "device_not_registered",
        "severity": "error",
        "supersedes": ["sticky_unreach", "unreach"],
    },
    "unreach_true": {
        "pattern": r"parameter = UNREACH, value = True",
        "description_de": "Gerät ist aktuell nicht erreichbar (Funkproblem)",
        "description_en": "Device is currently unreachable (radio issue)",
        "priority": 2,
        "category": "device_issue",
        "severity": "warning",
        "supersedes": [],
    },
    "sticky_unreach": {
        "pattern": r"STICKY_UN_REACH.*?(?:true|True)",
        "description_de": "Vergangene Kommunikationsprobleme (Reset in CCU erforderlich)",
        "description_en": "Past communication problems (reset required in CCU)",
        "priority": 3,
        "category": "device_issue",
        "severity": "info",
        "supersedes": [],
    },
    "xmlrpc_fault": {
        "pattern": r"XMLRPCFault|XmlRpcException|XMLRPC Fault",
        "description_de": "XML-RPC Kommunikationsfehler mit CCU",
        "description_en": "XML-RPC communication error with CCU",
        "priority": 2,
        "category": "connection",
        "severity": "error",
        "supersedes": [],
    },
    "connection_refused": {
        "pattern": r"Connection refused|ConnectionRefusedError|connect ECONNREFUSED",
        "description_de": "Verbindung zur CCU wurde verweigert",
        "description_en": "Connection to CCU was refused",
        "priority": 1,
        "category": "connection",
        "severity": "error",
        "supersedes": [],
    },
    "timeout": {
        "pattern": r"TimeoutError|asyncio\.TimeoutError|timed out|timeout",
        "description_de": "Zeitüberschreitung bei der Kommunikation",
        "description_en": "Communication timeout",
        "priority": 2,
        "category": "connection",
        "severity": "warning",
        "supersedes": [],
    },
    "config_pending": {
        "pattern": r"CONFIG_PENDING.*?(?:true|True)",
        "description_de": "Gerätekonfiguration wird übertragen",
        "description_en": "Device configuration is being transferred",
        "priority": 4,
        "category": "device_issue",
        "severity": "info",
        "supersedes": [],
    },
    "callback_failed": {
        "pattern": r"callback.*?(?:failed|error|exception)|init.*?failed",
        "description_de": "XML-RPC Callback-Registrierung fehlgeschlagen",
        "description_en": "XML-RPC callback registration failed",
        "priority": 1,
        "category": "interface",
        "severity": "error",
        "supersedes": [],
    },
    "ping_pong_missing": {
        "pattern": r"(?:PING|PONG).*?(?:missing|failed|timeout)|pending PING count",
        "description_de": "Ping/Pong-Überwachung zeigt Verbindungsprobleme",
        "description_en": "Ping/Pong monitoring shows connection issues",
        "priority": 2,
        "category": "connection",
        "severity": "warning",
        "supersedes": [],
    },
}


@dataclass
class AttachmentAnalysis:
    """Structured analysis results from attached files."""

    # From diagnostics JSON
    registered_models: list[str] = field(default_factory=list)
    registered_device_addresses: set[str] = field(default_factory=set)
    interface_health: dict[str, Any] = field(default_factory=dict)
    system_health: dict[str, Any] = field(default_factory=dict)
    incident_store: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    # From log analysis
    no_subscriber_addresses: set[str] = field(default_factory=set)
    event_sending_addresses: set[str] = field(default_factory=set)
    log_pattern_matches: dict[str, list[str]] = field(default_factory=dict)

    # Cross-reference results
    unregistered_devices: set[str] = field(default_factory=set)
    orphan_events: list[str] = field(default_factory=list)

    # Prioritized findings
    findings: list[dict[str, Any]] = field(default_factory=list)

    # Raw data availability
    has_diagnostics: bool = False
    has_logs: bool = False
    diagnostics_url: str = ""
    log_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "registered_models": self.registered_models,
            "registered_device_count": len(self.registered_device_addresses),
            "interface_health": self.interface_health,
            "system_health_summary": {
                "central_state": self.system_health.get("central_state", "unknown"),
                "all_clients_healthy": self.system_health.get("all_clients_healthy", False),
                "overall_health_score": self.system_health.get("overall_health_score", 0),
            },
            "incidents_count": self.incident_store.get("total_incidents", 0),
            "no_subscriber_count": len(self.no_subscriber_addresses),
            "unregistered_devices": list(self.unregistered_devices),
            "orphan_events_sample": self.orphan_events[:5],
            "log_pattern_summary": {k: len(v) for k, v in self.log_pattern_matches.items()},
            "prioritized_findings": self.findings,
            "has_diagnostics": self.has_diagnostics,
            "has_logs": self.has_logs,
        }


def fetch_latest_versions(gh: Github) -> tuple[str | None, str | None]:
    """
    Fetch the latest stable and pre-release versions from GitHub Releases.

    Returns tuple of (stable_version, prerelease_version).
    Uses caching to avoid repeated API calls.
    """
    if "stable" in _cached_versions:
        return _cached_versions.get("stable"), _cached_versions.get("prerelease")

    try:
        repo = gh.get_repo(INTEGRATION_REPO)
        releases = repo.get_releases()

        stable_version: str | None = None
        prerelease_version: str | None = None

        for release in releases:
            if release.draft:
                continue

            tag = release.tag_name.lstrip("v")  # Remove 'v' prefix if present

            if release.prerelease:
                if prerelease_version is None:
                    prerelease_version = tag
            elif stable_version is None:
                stable_version = tag
                # If we have both, we're done
                if prerelease_version is not None:
                    break

            # Stop after checking first 20 releases
            if stable_version is not None:
                break

        _cached_versions["stable"] = stable_version
        _cached_versions["prerelease"] = prerelease_version

    except GithubException as e:
        print(f"Warning: Could not fetch versions from GitHub: {e}")  # noqa: T201
        # Fallback to None - validation will still work but without version comparison
        _cached_versions["stable"] = None
        _cached_versions["prerelease"] = None

    return _cached_versions.get("stable"), _cached_versions.get("prerelease")


def parse_version(version_str: str) -> tuple[int, int, int, str] | None:
    """
    Parse a version string into components.

    Returns tuple of (major, minor, patch, prerelease) or None if invalid.
    """
    if not version_str:
        return None

    # Match patterns like "1.90.2", "1.91.0b32"
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(b\d+)?$", version_str.strip())
    if not match:
        return None

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    prerelease = match.group(4) or ""

    return (major, minor, patch, prerelease)


def validate_integration_version(
    version_str: str,
    *,
    current_stable: str | None,
    current_prerelease: str | None,
) -> dict[str, Any]:
    """
    Validate if the reported version is a valid Homematic(IP) Local version.

    Args:
        version_str: The version string to validate.
        current_stable: Current stable version from GitHub Releases.
        current_prerelease: Current pre-release version from GitHub Releases.

    Returns a dict with validation results.

    """
    result: dict[str, Any] = {
        "reported_version": version_str,
        "is_valid_format": False,
        "is_valid_homematicip_local": False,
        "is_prerelease": False,
        "needs_update": False,
        "current_stable": current_stable or "unknown",
        "current_prerelease": current_prerelease or "none",
        "issue": None,
        "issue_description": None,
    }

    parsed = parse_version(version_str)
    if not parsed:
        result["issue"] = "invalid_format"
        result["issue_description"] = f"Version '{version_str}' does not match expected format (e.g., 2.0.3 or 2.1.0b1)"
        return result

    major, minor, patch, prerelease = parsed
    result["is_valid_format"] = True
    result["is_prerelease"] = bool(prerelease)

    # Check for valid major version (1.x.x, 2.x.x, or 3.x.x)
    if major not in VALID_MAJOR_VERSIONS:
        result["issue"] = "invalid_major_version"
        result["issue_description"] = (
            f"Version '{version_str}' is not a valid Homematic(IP) Local version. "
            f"Valid versions use major versions 1, 2, or 3. "
            f"You may have reported the CCU firmware version instead of the integration version, "
            f"or you are using an old/different integration."
        )
        return result

    result["is_valid_homematicip_local"] = True

    # Compare with current stable version (only if we have version info)
    if current_stable:
        current_parsed = parse_version(current_stable)
        if current_parsed:
            current_major, current_minor, current_patch, _ = current_parsed
            reported_tuple = (major, minor, patch)
            current_tuple = (current_major, current_minor, current_patch)

            if reported_tuple < current_tuple:
                result["needs_update"] = True
                result["issue"] = "outdated_version"
                result["issue_description"] = (
                    f"Version '{version_str}' is outdated. "
                    f"Current stable version is {current_stable}. "
                    f"Please update to the latest version before reporting issues."
                )

    return result


def extract_version_from_issue(issue_body: str) -> str | None:
    """Extract the reported version from issue body."""
    # Look for version pattern in issue body (from template field)
    # The template asks for version in format like "1.8x.x"
    patterns = [
        r"(?:version|Version)[:\s]*(\d+\.\d+\.\d+(?:b\d+)?)",
        r"(\d+\.\d+\.\d+(?:b\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, issue_body)
        if match:
            return match.group(1)

    return None


# =============================================================================
# Attachment Analysis Functions
# =============================================================================


def extract_attachment_urls(issue_body: str) -> tuple[list[str], list[str]]:
    """
    Extract URLs to attached diagnostic and log files from issue body.

    Returns tuple of (json_urls, log_urls).
    """
    # GitHub user-attachments pattern for uploaded files
    attachment_pattern = r"https://github\.com/user-attachments/files/\d+/[^\s\)\]\"']+"

    # Also match direct links to .json and .log files
    json_pattern = r"https://[^\s\)\]\"']+\.json(?:\?[^\s\)\]\"']*)?"
    log_pattern = r"https://[^\s\)\]\"']+\.log(?:\?[^\s\)\]\"']*)?"

    all_attachments = re.findall(attachment_pattern, issue_body)
    json_direct = re.findall(json_pattern, issue_body)
    log_direct = re.findall(log_pattern, issue_body)

    json_urls: list[str] = []
    log_urls: list[str] = []

    # Categorize attachments by extension or content type hint
    for url in all_attachments:
        url_lower = url.lower()
        if "config" in url_lower or "diagnostic" in url_lower or url_lower.endswith(".json"):
            json_urls.append(url)
        elif "log" in url_lower or "home-assistant" in url_lower or url_lower.endswith(".log"):
            log_urls.append(url)
        elif ".json" in url_lower:
            json_urls.append(url)
        elif ".log" in url_lower or ".txt" in url_lower:
            log_urls.append(url)

    # Add direct matches
    json_urls.extend(json_direct)
    log_urls.extend(log_direct)

    # Remove duplicates while preserving order
    json_urls = list(dict.fromkeys(json_urls))
    log_urls = list(dict.fromkeys(log_urls))

    return json_urls, log_urls


def download_attachment(url: str, *, max_size: int = MAX_ATTACHMENT_SIZE) -> str | None:
    """
    Download an attachment from GitHub.

    Returns the content as string, or None if download fails.
    """
    try:
        # Use streaming to check size before downloading
        with requests.get(url, stream=True, timeout=30, allow_redirects=True) as response:
            response.raise_for_status()

            # Check content length if available
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_size:
                print(f"Attachment too large: {content_length} bytes")  # noqa: T201
                return None

            # Download with size limit
            content_chunks: list[bytes] = []
            total_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                total_size += len(chunk)
                if total_size > max_size:
                    print("Attachment exceeded size limit during download")  # noqa: T201
                    return None
                content_chunks.append(chunk)

            content = b"".join(content_chunks)

            # Try to decode as UTF-8
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return content.decode("latin-1")

    except requests.RequestException as e:
        print(f"Failed to download attachment from {url}: {e}")  # noqa: T201
        return None


def analyze_diagnostics_json(content: str) -> dict[str, Any]:
    """
    Parse and extract structured data from diagnostics JSON file.

    Returns extracted data as a dictionary.
    """
    result: dict[str, Any] = {
        "models": [],
        "device_addresses": set(),
        "system_health": {},
        "client_health": {},
        "incident_store": {},
        "metrics": {},
        "interfaces": [],
    }

    try:
        data = json.loads(content)

        # Handle nested structure: data -> data -> ...
        inner_data = data.get("data", data)

        # Extract models list
        result["models"] = inner_data.get("models", [])

        # Extract system health
        result["system_health"] = inner_data.get("system_health", {})

        # Extract client health per interface
        if "system_health" in inner_data:
            result["client_health"] = inner_data["system_health"].get("client_health", {})

        # Extract incident store
        result["incident_store"] = inner_data.get("incident_store", {})

        # Extract metrics
        result["metrics"] = inner_data.get("metrics", {})

        # Extract interfaces from config
        config = inner_data.get("config", {})
        if isinstance(config, dict):
            config_data = config.get("data", config)
            interfaces = config_data.get("interface", {})
            result["interfaces"] = list(interfaces.keys()) if isinstance(interfaces, dict) else []

        # Try to extract device addresses from various sources
        # This might be in device descriptions or other places
        if "device_descriptions" in inner_data:
            for addr in inner_data["device_descriptions"]:
                if isinstance(addr, str) and ":" not in addr:
                    result["device_addresses"].add(addr)

    except json.JSONDecodeError as e:
        print(f"Failed to parse diagnostics JSON: {e}")  # noqa: T201

    return result


def analyze_log_file(content: str, *, max_lines: int = 50000) -> dict[str, Any]:
    """
    Analyze log file content for known patterns.

    Returns analysis results including pattern matches and extracted addresses.
    """
    result: dict[str, Any] = {
        "pattern_matches": {},
        "no_subscriber_addresses": set(),
        "event_addresses": set(),
        "unreach_addresses": set(),
        "sample_matches": {},
    }

    # Limit lines to prevent excessive processing
    lines = content.split("\n")[:max_lines]
    content_limited = "\n".join(lines)

    for pattern_name, pattern_info in LOG_PATTERNS.items():
        pattern = pattern_info["pattern"]
        matches = re.findall(pattern, content_limited, re.IGNORECASE)

        if matches:
            result["pattern_matches"][pattern_name] = len(matches) if isinstance(matches[0], str) else len(matches)

            # Store sample matches (up to 5)
            if isinstance(matches[0], str):
                result["sample_matches"][pattern_name] = matches[:5]
            else:
                result["sample_matches"][pattern_name] = [m[0] if isinstance(m, tuple) else m for m in matches[:5]]

    # Extract specific addresses from "No subscribers" events
    no_sub_pattern = r"No subscribers for (?:Rpc)?ParameterReceivedEvent.*?\[([A-Za-z0-9]+:\d+)\]"
    no_sub_matches = re.findall(no_sub_pattern, content_limited)
    for match in no_sub_matches:
        # Extract device address (before the colon)
        device_addr = match.split(":")[0] if ":" in match else match
        result["no_subscriber_addresses"].add(device_addr)

    # Extract addresses from EVENT lines
    event_pattern = r"EVENT.*?channel_address\s*=\s*([A-Za-z0-9]+:\d+)"
    event_matches = re.findall(event_pattern, content_limited)
    for match in event_matches:
        device_addr = match.split(":")[0] if ":" in match else match
        result["event_addresses"].add(device_addr)

    # Extract addresses from UNREACH events
    unreach_pattern = r"channel_address\s*=\s*([A-Za-z0-9]+:\d+).*?UNREACH.*?True"
    unreach_matches = re.findall(unreach_pattern, content_limited)
    for match in unreach_matches:
        device_addr = match.split(":")[0] if ":" in match else match
        result["unreach_addresses"].add(device_addr)

    return result


def cross_reference_devices(
    *,
    registered_models: list[str],
    no_subscriber_addresses: set[str],
    event_addresses: set[str],
) -> dict[str, Any]:
    """
    Cross-reference registered devices with event-sending devices.

    Identifies devices that send events but are not registered in HA.
    """
    result: dict[str, Any] = {
        "unregistered_sending_events": [],
        "orphan_event_count": 0,
        "analysis_notes": [],
    }

    # If we have no-subscriber events, these devices are definitely not registered
    if no_subscriber_addresses:
        result["unregistered_sending_events"] = list(no_subscriber_addresses)
        result["orphan_event_count"] = len(no_subscriber_addresses)
        result["analysis_notes"].append(
            f"Found {len(no_subscriber_addresses)} device(s) sending events without registered entities"
        )

    # Check if event-sending devices match known model patterns
    # Classic HM devices typically start with specific prefixes (JEQ, LEQ, etc.)
    classic_hm_addresses = {
        addr for addr in event_addresses if addr.startswith(("JEQ", "LEQ", "MEQ", "NEQ", "OEQ", "SEQ"))
    }

    if classic_hm_addresses and "BidCos-RF" not in str(registered_models):
        result["analysis_notes"].append(
            f"Classic HM devices detected ({len(classic_hm_addresses)}) but BidCos-RF interface may not be active"
        )

    return result


def prioritize_findings(
    *,
    log_analysis: dict[str, Any],
    cross_ref: dict[str, Any],
    diagnostics: dict[str, Any],
    is_german: bool,
) -> list[dict[str, Any]]:
    """
    Prioritize and deduplicate findings based on root cause analysis.

    Higher priority findings supersede lower priority ones for the same issue.
    """
    findings: list[dict[str, Any]] = []
    suppressed_patterns: set[str] = set()

    # Sort patterns by priority
    sorted_patterns = sorted(LOG_PATTERNS.items(), key=lambda x: x[1]["priority"])

    for pattern_name, pattern_info in sorted_patterns:
        if pattern_name in suppressed_patterns:
            continue

        match_count = log_analysis.get("pattern_matches", {}).get(pattern_name, 0)
        if match_count == 0:
            continue

        # This pattern matched - suppress lower priority patterns it supersedes
        for superseded in pattern_info.get("supersedes", []):
            suppressed_patterns.add(superseded)

        description = pattern_info["description_de"] if is_german else pattern_info["description_en"]

        finding: dict[str, Any] = {
            "category": pattern_info["category"],
            "severity": pattern_info["severity"],
            "priority": pattern_info["priority"],
            "pattern": pattern_name,
            "count": match_count,
            "description": description,
        }

        # Add specific details for certain patterns
        if pattern_name == "no_subscribers":
            addresses = list(log_analysis.get("no_subscriber_addresses", set()))[:5]
            if addresses:
                if is_german:
                    finding["description"] += f". Betroffene Geräte: {', '.join(addresses)}"
                    finding["recommendation"] = (
                        "Diese Geräte sind nicht in Home Assistant registriert. "
                        "Prüfen Sie, ob die Geräte in HA deaktiviert oder nie hinzugefügt wurden."
                    )
                else:
                    finding["description"] += f". Affected devices: {', '.join(addresses)}"
                    finding["recommendation"] = (
                        "These devices are not registered in Home Assistant. "
                        "Check if devices are disabled in HA or were never added."
                    )

        findings.append(finding)

    # Add cross-reference findings
    if cross_ref.get("unregistered_sending_events"):
        # Check if we already have a no_subscribers finding
        has_no_sub = any(f["pattern"] == "no_subscribers" for f in findings)
        if not has_no_sub:
            devices = cross_ref["unregistered_sending_events"][:5]
            if is_german:
                findings.insert(
                    0,
                    {
                        "category": "device_not_registered",
                        "severity": "error",
                        "priority": 1,
                        "pattern": "cross_reference",
                        "count": len(cross_ref["unregistered_sending_events"]),
                        "description": f"Geräte senden Events aber sind nicht in HA registriert: {', '.join(devices)}",
                        "recommendation": "Prüfen Sie, ob diese Geräte in Home Assistant deaktiviert oder nie hinzugefügt wurden.",
                    },
                )
            else:
                findings.insert(
                    0,
                    {
                        "category": "device_not_registered",
                        "severity": "error",
                        "priority": 1,
                        "pattern": "cross_reference",
                        "count": len(cross_ref["unregistered_sending_events"]),
                        "description": f"Devices send events but are not registered in HA: {', '.join(devices)}",
                        "recommendation": "Check if these devices are disabled in Home Assistant or were never added.",
                    },
                )

    # Add incident store findings
    incidents = diagnostics.get("incident_store", {})
    if incidents.get("total_incidents", 0) > 0:
        recent = incidents.get("recent_incidents", [])
        if recent:
            last_incident = recent[0]
            if is_german:
                findings.append(
                    {
                        "category": "connection",
                        "severity": "warning",
                        "priority": 3,
                        "pattern": "incident_store",
                        "count": incidents["total_incidents"],
                        "description": f"Aufgezeichnete Vorfälle: {last_incident.get('message', 'Unbekannt')}",
                    }
                )
            else:
                findings.append(
                    {
                        "category": "connection",
                        "severity": "warning",
                        "priority": 3,
                        "pattern": "incident_store",
                        "count": incidents["total_incidents"],
                        "description": f"Recorded incidents: {last_incident.get('message', 'Unknown')}",
                    }
                )

    # Sort findings by priority (lower number = higher priority)
    findings.sort(key=lambda x: (x.get("priority", 99), -x.get("count", 0)))

    return findings


def perform_deep_analysis(issue_body: str) -> AttachmentAnalysis:
    """
    Perform deep analysis of attached files.

    Downloads and analyzes diagnostic JSON and log files.
    """
    analysis = AttachmentAnalysis()

    # Extract attachment URLs
    json_urls, log_urls = extract_attachment_urls(issue_body)

    print(f"Found {len(json_urls)} JSON URLs and {len(log_urls)} log URLs")  # noqa: T201

    # Analyze diagnostics JSON
    if json_urls:
        analysis.diagnostics_url = json_urls[0]
        content = download_attachment(json_urls[0])
        if content:
            analysis.has_diagnostics = True
            diag_data = analyze_diagnostics_json(content)
            analysis.registered_models = diag_data.get("models", [])
            analysis.registered_device_addresses = diag_data.get("device_addresses", set())
            analysis.system_health = diag_data.get("system_health", {})
            analysis.interface_health = diag_data.get("client_health", {})
            analysis.incident_store = diag_data.get("incident_store", {})
            analysis.metrics = diag_data.get("metrics", {})
            print(f"Parsed diagnostics: {len(analysis.registered_models)} models")  # noqa: T201

    # Analyze log file
    if log_urls:
        analysis.log_url = log_urls[0]
        content = download_attachment(log_urls[0])
        if content:
            analysis.has_logs = True
            log_data = analyze_log_file(content)
            analysis.no_subscriber_addresses = log_data.get("no_subscriber_addresses", set())
            analysis.event_sending_addresses = log_data.get("event_addresses", set())
            analysis.log_pattern_matches = {
                k: log_data.get("sample_matches", {}).get(k, []) for k in log_data.get("pattern_matches", {})
            }
            print(f"Analyzed log: {len(analysis.no_subscriber_addresses)} no-subscriber addresses")  # noqa: T201

    # Cross-reference devices
    cross_ref = cross_reference_devices(
        registered_models=analysis.registered_models,
        no_subscriber_addresses=analysis.no_subscriber_addresses,
        event_addresses=analysis.event_sending_addresses,
    )
    analysis.unregistered_devices = set(cross_ref.get("unregistered_sending_events", []))
    analysis.orphan_events = cross_ref.get("unregistered_sending_events", [])

    return analysis


# Documentation links
DOCS_LINKS = {
    "main_readme": "https://sukramj.github.io/aiohomematic/",
    "homematicip_local_readme": "https://github.com/sukramj/homematicip_local#homematicip_local",
    "troubleshooting": "https://sukramj.github.io/aiohomematic/user/troubleshooting/homeassistant_troubleshooting/",
    "faqs": "https://github.com/sukramj/homematicip_local#frequently-asked-questions",
    "releases": "https://github.com/sukramj/homematicip_local/releases",
    "architecture": "https://sukramj.github.io/aiohomematic/architecture/",
    "naming": "https://sukramj.github.io/aiohomematic/contributor/coding/naming/",
    "unignore": "https://sukramj.github.io/aiohomematic/user/advanced/unignore/",
    "lifecycle": "https://sukramj.github.io/aiohomematic/developer/homeassistant_lifecycle/",
    "glossary": "https://sukramj.github.io/aiohomematic/reference/glossary/",
    "discussions": "https://github.com/sukramj/aiohomematic/discussions",
}

# Required information fields from issue template
REQUIRED_FIELDS = [
    "version",
    "installation_type",
    "backend_type",
    "problem_description",
]

# German template markers - if any of these are found, the issue uses the German template
GERMAN_TEMPLATE_MARKERS = [
    "Ich stimme dem Folgenden zu",
    "Das Problem",
    "Bei welcher Version",
    "Welche Art von Installation",
    "Dieses Formular dient ausschließlich",
    "Diagnoseinformationen (keine Protokolle hier!)",
    "Protokolldatei (am besten DEBUG-Log)",
    "Welche Schnittstellen werden verwendet?",
]


def detect_template_language(issue_body: str) -> str:
    """
    Detect which template language was used based on template-specific markers.

    Returns "de" if German template markers are found, "en" otherwise.
    """
    if not issue_body:
        return "en"

    # Check for German template markers
    for marker in GERMAN_TEMPLATE_MARKERS:
        if marker in issue_body:
            return "de"

    return "en"

CLAUDE_ANALYSIS_PROMPT = """You are an AI assistant helping to analyze GitHub issues for the AioHomematic and Homematic(IP) Local projects.

**CRITICAL - Response Language:**
The issue template language has been detected as: **{template_language}**
- If "de" (German): You MUST respond in German. All text fields in your JSON response (summary, descriptions, explanations, recommendations) MUST be in German.
- If "en" (English): You MUST respond in English. All text fields in your JSON response MUST be in English.
This is mandatory and overrides any other language detection based on content.

Context:
- This repository (aiohomematic) is a Python library for controlling Homematic and HomematicIP devices
- Issues may relate to either the library itself or the Home Assistant integration "Homematic(IP) Local"
- Issues should follow a specific template with required information

CRITICAL - Required Information for Support:
- **Meaningful support is ONLY possible if all required information is provided!**
- The two MOST IMPORTANT pieces of information are:
  1. **Integration diagnostics (.json file)** - Downloaded via Settings -> Devices -> Select integration -> Download diagnostics
  2. **Log file** - The complete Home Assistant log file (not just excerpts)
- Without these, the issue should be flagged as incomplete
- Exception: For initial setup/installation issues, diagnostics may not be available yet

CRITICAL - Version Validation:
- Valid Homematic(IP) Local versions: 1.x.x (current) or 2.x.x (future major version)
- Current stable version: {current_stable}
- Current pre-release version: {current_prerelease} (pre-releases contain 'b', e.g., 1.91.0b32)
- If a user reports a version that does NOT start with 1.x.x or 2.x.x (e.g., 3.69.7), this is INVALID:
  - They may have confused the integration version with the CCU firmware version (CCU3 uses 3.x.x)
  - They may be using an old/different integration not based on aiohomematic
  - This MUST be flagged as a critical issue requiring clarification
- If the reported version is older than the current stable version, the user should be asked to update first
- Support can only be provided for the current stable version or newer

Version check result for this issue:
{version_check_json}

Terminology (from our Glossary):
- Integration: A Home Assistant component connecting to external services. Homematic(IP) Local is an INTEGRATION.
- Add-on: A separate application running alongside Home Assistant (e.g., OpenCCU Add-on). NOT the same as Integration.
- Plugin: NOT an official Home Assistant term - users should use "Integration" or "Add-on" instead.
- Backend: The CCU hardware/software (OpenCCU, CCU3, Debmatic, Homegear) that manages Homematic devices.
- Interface: Communication channel to device types (HmIP-RF, BidCos-RF, BidCos-Wired, VirtualDevices/CUxD, Groups).
- Device: Physical or virtual Homematic device with unique address containing channels.
- Channel: Logical unit within device grouping related functionality.
- Parameter: Named value on a channel (VALUES for runtime, MASTER for config).
- Data Point / Entity: Representation of a parameter in Home Assistant.

=== DEEP ANALYSIS RESULTS (Pre-analyzed from attachments) ===
{deep_analysis_json}

CRITICAL - Root Cause Analysis Priority Rules:
When analyzing device availability issues, you MUST follow these priority rules:

1. **HIGHEST PRIORITY - "No subscribers" / "device_not_registered"**:
   - If the deep analysis shows "no_subscriber_count" > 0 or "unregistered_devices" is not empty,
     this means devices are SENDING events but NO Home Assistant entities are listening.
   - This is NOT a radio/communication issue - the CCU communication works fine!
   - The devices are simply not registered in Home Assistant (disabled or never added).
   - DO NOT suggest STICKY_UN_REACH reset - that is the WRONG diagnosis!
   - CORRECT recommendation: Check if devices are disabled in HA or need to be added.

2. **LOWER PRIORITY - STICKY_UN_REACH**:
   - Only relevant if devices ARE registered but had past communication issues.
   - If "no_subscribers" findings exist, STICKY_UN_REACH is NOT the root cause.
   - STICKY_UN_REACH means "past radio issues" - but if events are arriving, radio works!

3. **Priority Hierarchy**:
   - device_not_registered (priority 1) SUPERSEDES sticky_unreach (priority 3)
   - connection_refused (priority 1) indicates backend not reachable
   - xmlrpc_fault (priority 2) indicates communication errors
   - If a higher priority issue exists, do NOT mention lower priority issues as the cause.

Your task:
1. Analyze the issue content and determine if it's complete and well-formed
2. Check for terminology misuse (e.g., "Plugin" instead of "Integration", confusion between Integration and Add-on)
3. Identify any missing required information
4. USE THE DEEP ANALYSIS RESULTS above - this is VERIFIED data from the actual files!
   - The "prioritized_findings" list is already sorted by priority
   - Trust this data over symptom-based guessing
5. Suggest relevant documentation links from the available docs
6. Identify key terms for searching similar issues

Issue Title: {title}

Issue Body:
{body}

Available documentation:
{docs}

Please respond in JSON format with the following structure:
{{
  "is_complete": boolean,
  "version_issue": {{
    "has_issue": boolean,
    "severity": "critical|warning|info|none",
    "message": "explanation of the version issue in detected language (or null if no issue)"
  }},
  "missing_information": [
    {{
      "field": "field name",
      "description": "what information is missing",
      "language": "de" or "en" (detected from issue)
    }}
  ],
  "terminology_issues": [
    {{
      "term_used": "incorrect term used",
      "correct_term": "what they should use instead",
      "explanation": "brief explanation in detected language"
    }}
  ],
  "attachment_analysis": {{
    "has_diagnostics": boolean,
    "has_logs": boolean,
    "findings": [
      {{
        "category": "device_not_registered|device_issue|connection|interface|config|other",
        "description": "what was found",
        "severity": "info|warning|error",
        "recommendation": "optional - specific action to take"
      }}
    ]
  }},
  "suggested_docs": [
    {{
      "doc_key": "key from available docs",
      "reason": "why this doc is relevant"
    }}
  ],
  "search_terms": ["term1", "term2", ...],
  "language": "de" or "en",
  "is_bug_report": boolean,
  "is_device_related": boolean,
  "has_screenshots": boolean,
  "summary": "brief summary of the issue in the detected language"
}}

IMPORTANT:
- Use the prioritized_findings from deep analysis as the PRIMARY source for attachment_analysis.findings
- If "device_not_registered" findings exist, this is the root cause - not STICKY_UN_REACH
- Be helpful and constructive
- Only flag missing information if it's genuinely required
- If terminology is misused, gently suggest correct terms and link to glossary
- For device-related issues (missing entities, wrong values, strange behavior): Check if the issue contains screenshots. If not, flag this as missing information - screenshots are much more helpful than long text descriptions for device issues!
- Detect screenshots by looking for image URLs (e.g., user-attachments/assets, imgur, png, jpg, gif extensions)"""


def get_claude_analysis(
    title: str,
    body: str,
    api_key: str,
    *,
    gh: Github,
    deep_analysis: AttachmentAnalysis | None = None,
) -> dict[str, Any]:
    """Use Claude to analyze the issue with deep analysis results."""
    client = Anthropic(api_key=api_key)

    docs_str = "\n".join([f"- {key}: {url}" for key, url in DOCS_LINKS.items()])

    # Detect template language from issue body
    template_language = detect_template_language(body or "")
    print(f"Detected template language: {template_language}")  # noqa: T201

    # Fetch current versions from GitHub Releases
    current_stable, current_prerelease = fetch_latest_versions(gh)

    # Extract and validate version from issue body
    extracted_version = extract_version_from_issue(body or "")
    if extracted_version:
        version_check = validate_integration_version(
            extracted_version,
            current_stable=current_stable,
            current_prerelease=current_prerelease,
        )
    else:
        version_check = {
            "reported_version": None,
            "is_valid_format": False,
            "is_valid_homematicip_local": False,
            "issue": "no_version_found",
            "issue_description": "No version number found in issue body",
            "current_stable": current_stable or "unknown",
            "current_prerelease": current_prerelease or "none",
        }

    # Prepare deep analysis JSON
    if deep_analysis:
        deep_analysis_dict = deep_analysis.to_dict()
    else:
        deep_analysis_dict = {
            "has_diagnostics": False,
            "has_logs": False,
            "note": "No attachments could be downloaded or analyzed",
        }

    prompt = CLAUDE_ANALYSIS_PROMPT.format(
        title=title,
        body=body or "(empty)",
        docs=docs_str,
        current_stable=current_stable or "unknown",
        current_prerelease=current_prerelease or "none",
        version_check_json=json.dumps(version_check, indent=2),
        deep_analysis_json=json.dumps(deep_analysis_dict, indent=2),
        template_language="de (German)" if template_language == "de" else "en (English)",
    )

    message = client.messages.create(
        model="claude-sonnet-4-5", max_tokens=2000, messages=[{"role": "user", "content": prompt}]
    )

    # Parse the JSON response
    response_text = message.content[0].text
    # Extract JSON from potential markdown code blocks
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    analysis = cast(dict[str, Any], json.loads(response_text))

    # Override language with detected template language (template language takes precedence)
    analysis["language"] = template_language

    # Merge deep analysis findings if Claude didn't include them
    if deep_analysis and deep_analysis.findings:
        attachment_analysis = analysis.get("attachment_analysis", {})
        claude_findings = attachment_analysis.get("findings", [])

        # If Claude returned fewer findings than our deep analysis, use ours
        if len(claude_findings) < len(deep_analysis.findings):
            # Use template language for findings
            is_german = template_language == "de"

            # Prioritize findings
            prioritized = prioritize_findings(
                log_analysis={
                    "pattern_matches": {k: len(v) for k, v in deep_analysis.log_pattern_matches.items()},
                    "no_subscriber_addresses": deep_analysis.no_subscriber_addresses,
                },
                cross_ref={
                    "unregistered_sending_events": list(deep_analysis.unregistered_devices),
                },
                diagnostics={
                    "incident_store": deep_analysis.incident_store,
                },
                is_german=is_german,
            )

            # Convert to Claude's format
            attachment_analysis["findings"] = [
                {
                    "category": f["category"],
                    "description": f["description"],
                    "severity": f["severity"],
                    "recommendation": f.get("recommendation", ""),
                }
                for f in prioritized
            ]
            attachment_analysis["has_diagnostics"] = deep_analysis.has_diagnostics
            attachment_analysis["has_logs"] = deep_analysis.has_logs
            analysis["attachment_analysis"] = attachment_analysis

    return analysis


def search_similar_issues(
    repo: Repository.Repository, search_terms: list[str], current_issue_number: int
) -> list[dict[str, Any]]:
    """Search for similar issues and discussions."""
    similar_items: list[dict[str, Any]] = []

    # Limit search terms to top 3 most relevant
    search_terms = search_terms[:3]

    for term in search_terms:
        if not term or len(term) < 3:
            continue

        # Search in issues
        try:
            issues = repo.get_issues(state="all", sort="updated", direction="desc")
            similar_items.extend(
                {
                    "type": "issue",
                    "number": issue.number,
                    "title": issue.title,
                    "url": issue.html_url,
                    "state": issue.state,
                    "search_term": term,
                }
                for issue in issues[:5]  # Limit to 5 results per term
                if issue.number != current_issue_number
            )
        except GithubException:
            pass

    # Remove duplicates
    seen = set()
    unique_items = []
    for item in similar_items:
        key = (item["type"], item["number"])
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

    return unique_items[:5]  # Return top 5 overall


def has_bot_comment(issue: Any) -> bool:
    """Check if the bot has already commented on this issue."""
    for comment in issue.get_comments():
        if comment.user.type == "Bot" and "Automatische Issue-Analyse" in comment.body:
            return True
        if comment.user.type == "Bot" and "Automatic Issue Analysis" in comment.body:
            return True
    return False


def _format_version_issue(
    analysis: dict[str, Any],
    is_german: bool,
    *,
    current_stable: str,
    current_prerelease: str,
) -> str:
    """Format version issue section of the comment."""
    # If we couldn't determine current versions, don't comment on version issues
    if current_stable == "unknown":
        return ""

    version_issue = analysis.get("version_issue", {})
    if not version_issue.get("has_issue"):
        return ""
    if version_issue.get("severity") not in ("critical", "warning"):
        return ""

    severity = version_issue.get("severity", "warning")
    message = version_issue.get("message", "")

    is_critical = severity == "critical"
    emoji = "🚨" if is_critical else "⚠️"
    header = (
        ("KRITISCH: Versionsproblem" if is_german else "CRITICAL: Version Issue")
        if is_critical
        else ("Versionshinweis" if is_german else "Version Notice")
    )

    result = f"### {emoji} {header}\n\n{message}\n\n"

    if is_german:
        result += (
            f"**Aktuelle stabile Version:** {current_stable}\n"
            f"**Aktuelle Pre-Release:** {current_prerelease}\n\n"
            f"Bitte stelle sicher, dass du die [aktuelle Version]({DOCS_LINKS['releases']}) verwendest, "
            f"bevor du ein Problem meldest. Support kann nur für die aktuelle Version geleistet werden.\n\n"
        )
    else:
        result += (
            f"**Current stable version:** {current_stable}\n"
            f"**Current pre-release:** {current_prerelease}\n\n"
            f"Please ensure you are using the [latest version]({DOCS_LINKS['releases']}) "
            f"before reporting issues. Support can only be provided for the current version.\n\n"
        )

    return result


def _format_missing_required_info(
    has_diagnostics: bool,
    has_logs: bool,
    is_german: bool,
) -> str:
    """Format missing required information section."""
    if has_diagnostics and has_logs:
        return ""

    if is_german:
        result = "### ⚠️ Fehlende Pflichtinformationen\n\n"
        result += (
            "**Sinnvoller Support ist nur möglich, wenn alle erforderlichen Informationen bereitgestellt werden!**\n\n"
            "Es fehlen:\n\n"
        )
        if not has_diagnostics:
            result += "- ❌ **Integrationsdiagnose (.json-Datei)** - Herunterladen via: Einstellungen → Geräte → Integration auswählen → Diagnose herunterladen\n"
        if not has_logs:
            result += "- ❌ **Protokolldatei** - Am besten ein DEBUG-Log hochladen. Aktivieren via: Einstellungen → Geräte → Integration auswählen → Debug-Protokollierung aktivieren. Danach Problem reproduzieren und Log herunterladen (Einstellungen → System → Protokolle → Unveränderte Protokolle laden)\n"
        result += (
            "\n⚠️ **Issues ohne diese Informationen können nicht bearbeitet werden und werden ggf. geschlossen.**\n\n"
        )
        result += "_Ausnahme: Bei Problemen mit der Erstinstallation sind Diagnosedaten möglicherweise noch nicht verfügbar._\n\n"
    else:
        result = "### ⚠️ Missing Required Information\n\n"
        result += "**Meaningful support is only possible if all required information is provided!**\n\nMissing:\n\n"
        if not has_diagnostics:
            result += "- ❌ **Integration diagnostics (.json file)** - Download via: Settings → Devices → Select integration → Download diagnostics\n"
        if not has_logs:
            result += "- ❌ **Log file** - Preferably a DEBUG log. Enable via: Settings → Devices → Select integration → Enable debug logging. Then reproduce the issue and download log (Settings → System → Logs → Load unchanged logs)\n"
        result += "\n⚠️ **Issues without this information cannot be processed and may be closed.**\n\n"
        result += "_Exception: For initial setup issues, diagnostics may not be available yet._\n\n"

    return result


def _format_screenshot_hint(
    is_device_related: bool,
    has_screenshots: bool,
    is_german: bool,
) -> str:
    """Format screenshot hint for device-related issues."""
    if not is_device_related or has_screenshots:
        return ""

    if is_german:
        return (
            "### 📸 Screenshots empfohlen\n\n"
            "Bei Geräteproblemen (fehlende Entitäten, falsche Werte, seltsames Verhalten) "
            "sind **Screenshots viel hilfreicher als lange Textbeschreibungen**!\n\n"
            "Bitte zeige uns, was Du siehst:\n"
            "- Screenshot der betroffenen Entität in Home Assistant\n"
            "- Screenshot des Geräts/Kanals in der CCU-Oberfläche\n\n"
        )
    return (
        "### 📸 Screenshots Recommended\n\n"
        "For device-related issues (missing entities, wrong values, strange behavior), "
        "**screenshots are much more helpful than long text descriptions**!\n\n"
        "Please show us what you see:\n"
        "- Screenshot of the affected entity in Home Assistant\n"
        "- Screenshot of the device/channel in the CCU interface\n\n"
    )


def format_comment(
    analysis: dict[str, Any],
    similar_items: list[dict[str, Any]],
    *,
    current_stable: str,
    current_prerelease: str,
) -> str:
    """Format the comment to post on the issue."""
    lang = analysis.get("language", "en")
    is_german = lang == "de"

    # Header
    if is_german:
        comment = "## Automatische Issue-Analyse\n\n"
        comment += f"**Zusammenfassung:** {analysis.get('summary', 'Issue wurde erkannt')}\n\n"
    else:
        comment = "## Automatic Issue Analysis\n\n"
        comment += f"**Summary:** {analysis.get('summary', 'Issue detected')}\n\n"

    # Version issue (highest priority - show first if critical)
    comment += _format_version_issue(
        analysis,
        is_german,
        current_stable=current_stable,
        current_prerelease=current_prerelease,
    )

    # Terminology issues
    terminology_issues = analysis.get("terminology_issues", [])
    if terminology_issues:
        if is_german:
            comment += "### Hinweise zur Terminologie\n\n"
            comment += (
                "Um Verwirrung zu vermeiden, beachte bitte die korrekte "
                f"[Terminologie (Glossar)]({DOCS_LINKS['glossary']}):\n\n"
            )
        else:
            comment += "### Terminology Notes\n\n"
            comment += (
                f"To avoid confusion, please note the correct [terminology (Glossary)]({DOCS_LINKS['glossary']}):\n\n"
            )

        for item in terminology_issues:
            comment += f"- **{item['term_used']}** → **{item['correct_term']}**: {item['explanation']}\n"
        comment += "\n"

    # Check for missing diagnostics/logs (critical for support)
    attachment_analysis = analysis.get("attachment_analysis", {})
    has_diagnostics = attachment_analysis.get("has_diagnostics", False)
    has_logs = attachment_analysis.get("has_logs", False)
    comment += _format_missing_required_info(has_diagnostics, has_logs, is_german)

    # Screenshot hint for device-related issues
    is_device_related = analysis.get("is_device_related", False)
    has_screenshots = analysis.get("has_screenshots", False)
    comment += _format_screenshot_hint(is_device_related, has_screenshots, is_german)

    # Other missing information
    missing = analysis.get("missing_information", [])
    # Filter out diagnostics/logs from missing list since we handle them separately
    missing = [
        m
        for m in missing
        if m.get("field", "").lower() not in ("diagnostics", "logs", "log", "diagnostik", "protokoll")
    ]
    if missing:
        if is_german:
            comment += "### Weitere fehlende Informationen\n\n"
        else:
            comment += "### Additional Missing Information\n\n"

        for item in missing:
            comment += f"- **{item['field']}**: {item['description']}\n"
        comment += "\n"

    # Attachment analysis findings
    findings = attachment_analysis.get("findings", [])
    if findings:
        if is_german:
            comment += "### Analyse der angehängten Daten\n\n"
            if attachment_analysis.get("has_diagnostics"):
                comment += "✅ Diagnostik-Daten analysiert. "
            if attachment_analysis.get("has_logs"):
                comment += "✅ Protokoll-Daten analysiert. "
            comment += "\n\n**Erkenntnisse:**\n\n"
        else:
            comment += "### Attachment Analysis\n\n"
            if attachment_analysis.get("has_diagnostics"):
                comment += "✅ Diagnostics data analyzed. "
            if attachment_analysis.get("has_logs"):
                comment += "✅ Log data analyzed. "
            comment += "\n\n**Findings:**\n\n"

        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}
        category_labels = {
            "device_not_registered": "Gerät nicht registriert" if is_german else "Device Not Registered",
            "device_issue": "Geräteproblem" if is_german else "Device Issue",
            "connection": "Verbindung" if is_german else "Connection",
            "interface": "Schnittstelle" if is_german else "Interface",
            "config": "Konfiguration" if is_german else "Configuration",
            "other": "Sonstiges" if is_german else "Other",
        }

        for finding in findings:
            emoji = severity_emoji.get(finding.get("severity", "info"), "ℹ️")
            category = finding.get("category", "other")
            category_label = category_labels.get(category, category)
            description = finding.get("description", "")
            recommendation = finding.get("recommendation", "")

            comment += f"- {emoji} **[{category_label}]** {description}\n"

            # Add recommendation if present
            if recommendation:
                if is_german:
                    comment += f"  - 💡 **Empfehlung:** {recommendation}\n"
                else:
                    comment += f"  - 💡 **Recommendation:** {recommendation}\n"

        comment += "\n"

    # Suggested documentation
    suggested_docs = analysis.get("suggested_docs", [])
    if suggested_docs:
        if is_german:
            comment += "### Hilfreiche Dokumentation\n\n"
            comment += "Die folgenden Dokumentationsseiten könnten hilfreich sein:\n\n"
        else:
            comment += "### Helpful Documentation\n\n"
            comment += "The following documentation pages might be helpful:\n\n"

        for doc in suggested_docs:
            doc_key = doc["doc_key"]
            if doc_key in DOCS_LINKS:
                url = DOCS_LINKS[doc_key]
                reason = doc["reason"]
                comment += f"- [{doc_key}]({url})\n  _{reason}_\n"
        comment += "\n"

    # Similar issues
    if similar_items:
        if is_german:
            comment += "### Ähnliche Issues und Diskussionen\n\n"
            comment += "Die folgenden Issues oder Diskussionen könnten relevant sein:\n\n"
        else:
            comment += "### Similar Issues and Discussions\n\n"
            comment += "The following issues or discussions might be relevant:\n\n"

        for item in similar_items:
            state_emoji = "✅" if item["state"] == "closed" else "🔄"
            comment += f"- {state_emoji} #{item['number']}: [{item['title']}]({item['url']})\n"
        comment += "\n"

    # Footer
    if is_german:
        comment += "---\n"
        comment += "_Diese Analyse wurde automatisch erstellt. "
        comment += "Bei Fragen oder Problemen, bitte die [Diskussionen]({}) nutzen._\n".format(
            DOCS_LINKS["discussions"]
        )
    else:
        comment += "---\n"
        comment += "_This analysis was generated automatically. "
        comment += "For questions or support, please use the [discussions]({})._\n".format(DOCS_LINKS["discussions"])

    return comment


def main() -> None:
    """Analyze issue and post comment."""
    # Get environment variables
    github_token = os.getenv("GITHUB_TOKEN") or ""
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or ""
    issue_number = int(os.getenv("ISSUE_NUMBER", "0"))
    repo_name = os.getenv("REPO_NAME", "")

    if not all([github_token, anthropic_api_key, issue_number, repo_name]):
        print("Error: Missing required environment variables")  # noqa: T201
        sys.exit(1)

    # Initialize GitHub client
    gh = Github(auth=Auth.Token(github_token))
    repo = gh.get_repo(repo_name)
    issue = repo.get_issue(issue_number)

    # Get issue details (either from env or from GitHub API)
    issue_title = os.getenv("ISSUE_TITLE") or issue.title
    issue_body = os.getenv("ISSUE_BODY") or issue.body or ""

    print(f"Analyzing issue #{issue_number}: {issue_title}")  # noqa: T201

    # Fetch latest versions from GitHub Releases
    current_stable, current_prerelease = fetch_latest_versions(gh)
    print(f"Current versions - stable: {current_stable}, prerelease: {current_prerelease}")  # noqa: T201

    # Perform deep analysis of attachments BEFORE Claude analysis
    deep_analysis: AttachmentAnalysis | None = None
    try:
        print("Performing deep analysis of attachments...")  # noqa: T201
        deep_analysis = perform_deep_analysis(issue_body)
        print(f"Deep analysis complete: diagnostics={deep_analysis.has_diagnostics}, logs={deep_analysis.has_logs}")  # noqa: T201
        if deep_analysis.no_subscriber_addresses:
            print(f"Found {len(deep_analysis.no_subscriber_addresses)} devices with no subscribers")  # noqa: T201
        if deep_analysis.unregistered_devices:
            print(f"Found {len(deep_analysis.unregistered_devices)} unregistered devices sending events")  # noqa: T201
    except Exception as e:
        print(f"Warning: Deep analysis failed (continuing with basic analysis): {e}")  # noqa: T201
        deep_analysis = None

    # Get Claude's analysis with deep analysis results
    try:
        analysis = get_claude_analysis(
            issue_title,
            issue_body,
            anthropic_api_key,
            gh=gh,
            deep_analysis=deep_analysis,
        )
        print(f"Analysis complete: {json.dumps(analysis, indent=2)}")  # noqa: T201
    except Exception as e:
        print(f"Error getting Claude analysis: {e}")  # noqa: T201
        sys.exit(1)

    # Search for similar issues
    search_terms = analysis.get("search_terms", [])
    similar_items = []
    if search_terms:
        try:
            similar_items = search_similar_issues(repo, search_terms, issue_number)
            print(f"Found {len(similar_items)} similar items")  # noqa: T201
        except Exception as e:
            print(f"Error searching for similar issues: {e}")  # noqa: T201

    # Check if bot has already commented (to avoid duplicates on edit)
    is_manual_trigger = not os.getenv("ISSUE_TITLE")  # Manual trigger doesn't have ISSUE_TITLE in env
    already_commented = has_bot_comment(issue)

    if already_commented and not is_manual_trigger:
        print("Bot has already commented on this issue, skipping to avoid duplicates")  # noqa: T201
        return

    # Format and post comment
    comment_body = format_comment(
        analysis,
        similar_items,
        current_stable=current_stable or "unknown",
        current_prerelease=current_prerelease or "none",
    )

    # Only post if there's something useful to say
    version_issue = analysis.get("version_issue", {})
    has_version_issue = version_issue.get("has_issue") and version_issue.get("severity") in (
        "critical",
        "warning",
    )
    attachment_info = analysis.get("attachment_analysis", {})
    missing_required_info = not attachment_info.get("has_diagnostics") or not attachment_info.get("has_logs")
    has_useful_feedback = (
        has_version_issue
        or missing_required_info
        or analysis.get("missing_information")
        or analysis.get("terminology_issues")
        or attachment_info.get("findings")
        or analysis.get("suggested_docs")
        or similar_items
    )

    if has_useful_feedback:
        try:
            issue.create_comment(comment_body)
            print("Comment posted successfully")  # noqa: T201
        except Exception as e:
            print(f"Error posting comment: {e}")  # noqa: T201
            sys.exit(1)
    else:
        print("No actionable feedback to provide, skipping comment")  # noqa: T201


if __name__ == "__main__":
    main()
