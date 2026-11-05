#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
"""
Compare the "Homematic IP Devices - Technical Documentation" PDF with the device definitions.

The PDF lists every firmware range of a model in its own section. Only the current one is
evaluated: the section whose range has no end ("from version X", without "to version Y").

The report is a list of candidates, not of defects. A missing parameter is often intended,
because profiles are shared between models and absent fields are skipped at runtime
(``CustomDataPoint._add_channel_data_points``). Every candidate has to be judged by reading the
documentation section the report cites.

Exit codes: ``0`` report written, ``2`` the PDF could not be parsed completely. The latter is
checked against raw counts of the extracted text, so a changed PDF layout fails loudly instead
of producing an incomplete report.

Requires ``pdftotext`` (poppler). The PDF is not part of the repository.

Run manually::

    python script/check_hmip_device_doc.py tmp/hmip_device_documentation.pdf
    python script/check_hmip_device_doc.py tmp/hmip_device_documentation.pdf --output tmp/hmip_device_doc_report.md
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Final

_REPO_ROOT: Final = Path(__file__).resolve().parent.parent
# "python script/x.py" puts script/ on sys.path, so another installed aiohomematic would win.
sys.path.insert(0, str(_REPO_ROOT))

from aiohomematic import __file__ as _AIOHOMEMATIC_FILE  # noqa: E402
from aiohomematic.const import VERSION, Field  # noqa: E402
from aiohomematic.model.calculated.operating_voltage_level import (  # noqa: E402
    _BATTERY_DATA,
    _IGNORE_OPERATING_VOLTAGE_LEVEL_MODELS,
    _OPERATING_VOLTAGE_LEVEL_MODELS,
)
from aiohomematic.model.custom import DeviceProfileRegistry  # noqa: E402
from aiohomematic.model.custom.definition import _get_relevant_channels  # noqa: E402
from aiohomematic.model.custom.profile import FieldValue, get_profile_config, rebase_channel_group, resolve_field_value  # noqa: E402
from aiohomematic.store.visibility.rules import (  # noqa: E402
    IGNORE_PARAMETERS_BY_DEVICE,
    IGNORE_PARAMETERS_BY_DEVICE_LOWER,
    UN_IGNORE_PARAMETERS_BY_DEVICE,
)
from aiohomematic.support import element_matches_key  # noqa: E402

_DEVICE_HEADER: Final = re.compile(r"^\s*(\d+)\. Device (\S+) \((.*)$")
_DEVICE_HEADER_RAW: Final = re.compile(r"^\f?\s*\d+\. Device ", re.MULTILINE)
_SUPPORTED_TYPE: Final = re.compile(r"^\s*•\s*(\S+) \(ID: (\d+), from version ([\d.]+)(?: to version ([\d.]+))?\)")
_SUPPORTED_TYPE_RAW: Final = re.compile(r"•\s*\S+ \(ID: \d+")
_CHANNEL_ROW: Final = re.compile(r"^\s*(\d+)\s{3,}(\S+)\s*$")
_PARAMETER: Final = re.compile(r"^\s*[\d.]+\. Parameter (\S+)")
_PARAMETER_ROW: Final = re.compile(r"^\s*(BOOLEAN|INTEGER|LONG|FLOAT|ENUM|STRING|ACTION)\s+\S+\s+(read|write|event)\b")
_ACCESS: Final = re.compile(r"^\s*(read|write|event)\b")
_NEXT_HEADING: Final = re.compile(r"^\s*[\d.]+\. ")
_PARAMETER_LOOKAHEAD: Final = 14
_SECTION_KINDS: Final[Mapping[str, str]] = {"1": "state", "2": "config", "3": "roles", "4": "link"}
_REGISTERED_PREFIXES: Final = ("hmip", "elv")


@dataclass(slots=True)
class _Section:
    """One device section of the documentation."""

    number: int
    name: str
    description: str
    page: int
    models: list[tuple[str, int, str, str | None]] = field(default_factory=list)
    channels: dict[int, str] = field(default_factory=dict)
    state_parameters: dict[int, dict[str, tuple[str, ...]]] = field(default_factory=dict)
    config_parameters: dict[int, dict[str, tuple[str, ...]]] = field(default_factory=dict)
    channel_sections: set[int] = field(default_factory=set)

    @property
    def reference(self) -> str:
        """Return the citation of this section."""
        return f"§{self.number} {self.name}, p. {self.page}"

    def has_parameter(self, *, channel_no: int | None, parameter: str) -> bool:
        """Return if the parameter is documented on the channel, as state or as configuration parameter."""
        if channel_no is None:
            return False
        return parameter in self.state_parameters.get(channel_no, {}) or parameter in self.config_parameters.get(
            channel_no, {}
        )


def _extract_text(*, pdf: Path) -> str:
    """Return the text of the PDF, with pages separated by form feeds."""
    if (pdftotext := shutil.which("pdftotext")) is None:
        sys.exit("pdftotext not found, install poppler")
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "doc.txt"
        subprocess.run([pdftotext, "-layout", str(pdf), str(target)], check=True)
        return target.read_text(errors="replace")


def _read_parameter(*, lines: list[str], start: int) -> tuple[str, ...] | None:
    """Return the access flags of the parameter whose table row follows the heading at start."""
    access: list[str] = []
    for line in lines[start + 1 : start + _PARAMETER_LOOKAHEAD]:
        if _NEXT_HEADING.match(line):
            break
        if not access:
            if match := _PARAMETER_ROW.match(line):
                access.append(match[2])
        elif match := _ACCESS.match(line):
            access.append(match[1])
    return tuple(access) or None


def _parse(*, text: str) -> tuple[list[_Section], list[str]]:
    """Parse the extracted text and return the sections and the parse errors."""
    numbered = [(no, line) for no, page in enumerate(text.split("\f"), 1) for line in page.splitlines()]
    lines = [line for _, line in numbered]
    sections: list[_Section] = []
    errors: list[str] = []
    current: _Section | None = None
    block: str | None = None
    channel: int | None = None
    kind: str | None = None
    unread = 0

    for index, (page, line) in enumerate(numbered):
        if match := _DEVICE_HEADER.match(line):
            current = _Section(number=int(match[1]), name=match[2], description=match[3].rstrip(" )"), page=page)
            sections.append(current)
            block, channel, kind = None, None, None
            continue
        if current is None:
            continue
        number = current.number
        if re.match(rf"^\s*{number}\.1\. Supported device types", line):
            block = "types"
        elif re.match(rf"^\s*{number}\.2\. Channel types", line):
            block = "table"
        elif re.match(rf"^\s*{number}\.3\. Channels", line):
            block = "channels"
        elif block == "types":
            if match := _SUPPORTED_TYPE.match(line):
                current.models.append((match[1], int(match[2]), match[3], match[4]))
        elif block == "table":
            if match := _CHANNEL_ROW.match(line):
                current.channels[int(match[1])] = match[2]
        elif block == "channels":
            if match := re.match(rf"^\s*{number}\.3\.\d+\. Channel (\d+) - (\S+)", line):
                channel, kind = int(match[1]), None
                current.channel_sections.add(channel)
            elif match := re.match(rf"^\s*{number}\.3\.\d+\.(\d)\. ", line):
                kind = _SECTION_KINDS.get(match[1])
            elif kind in ("state", "config") and channel is not None and (match := _PARAMETER.match(line)):
                if (access := _read_parameter(lines=lines, start=index)) is None:
                    unread += 1
                target = current.state_parameters if kind == "state" else current.config_parameters
                target.setdefault(channel, {})[match[1]] = access or ()

    if (raw := len(_DEVICE_HEADER_RAW.findall(text))) != len(sections):
        errors.append(f"device headers: {raw} in text, {len(sections)} parsed")
    parsed_models = sum(len(section.models) for section in sections)
    if (raw := len(_SUPPORTED_TYPE_RAW.findall(text))) != parsed_models:
        errors.append(f"supported types: {raw} in text, {parsed_models} parsed")
    for section in sections:
        if not section.models or not section.channels:
            errors.append(f"{section.reference}: no models or no channel table")
        if set(section.channels) != section.channel_sections:
            errors.append(f"{section.reference}: channel table differs from channel sections")
    if unread:
        errors.append(f"{unread} parameters without a readable table row")
    return sections, errors


def _latest_sections(*, sections: Iterable[_Section]) -> tuple[dict[str, _Section], list[str]]:
    """Return the section of the open-ended firmware range per model, and models without one."""
    all_models: set[str] = set()
    latest: dict[str, _Section] = {}
    for section in sections:
        for model, _, _, until in section.models:
            all_models.add(model)
            if until is None:
                latest.setdefault(model, section)
    return latest, sorted(all_models - set(latest))


def _matches(*, model: str) -> list[tuple[str, str]]:
    """Return (category, registered key) of the prefix matches of a model without an exact entry."""
    normalized = model.lower().replace("hb-", "hm-")
    result: list[tuple[str, str]] = []
    for category, entries in DeviceProfileRegistry._configs.items():
        if normalized in entries:
            continue
        for key in entries:
            if normalized.startswith(key):
                result.append((category.value, key))
                break
    return result


def _write_table(*, out: list[str], header: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> None:
    """Append a markdown table."""
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + " --- |" * len(header))
    out.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    out.append("")


def _compare(*, latest: Mapping[str, _Section], sections: Iterable[_Section]) -> list[str]:
    """Return the report lines."""
    out: list[str] = []
    missing_channels: list[tuple[str, str, str, int]] = []
    field_results: dict[tuple[str, str, str, str], list[tuple[str, int | None, bool]]] = defaultdict(list)
    type_combinations: dict[str, dict[tuple[str | None, str | None], list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    uncovered: list[tuple[str, str, str, str]] = []
    no_config: list[tuple[str, str, str, str]] = []
    prefix_rows: list[tuple[str, str, str, str]] = []

    for model, section in sorted(latest.items()):
        configs = DeviceProfileRegistry.get_configs(model=model)
        if not configs:
            types = Counter(
                type_name
                for type_name in section.channels.values()
                if type_name != "KEY_TRANSCEIVER" and not type_name.startswith("MAINTENANCE")
            )
            no_config.append(
                (model, section.description, ", ".join(f"{k}×{v}" for k, v in sorted(types.items())), section.reference)
            )
            continue
        if matches := _matches(model=model):
            channels = sorted({str(config.channels) for config in configs})
            prefix_rows.append(
                (model, ", ".join(f"{c}: {k}" for c, k in matches), " ".join(channels), section.reference)
            )

        covered: set[int] = set()
        for config in configs:
            profile = config.profile_type.value
            profile_config = get_profile_config(profile_type=config.profile_type)
            relevant = _get_relevant_channels(profile_config=profile_config, device_config=config)
            base = profile_config.channel_group.primary_channel
            for conf in config.channels:
                # Same group number as _add_channel_groups_to_device.
                group_no = conf + base if conf is not None and base is not None else None
                group = rebase_channel_group(profile_config=profile_config, group_no=group_no)
                primary = group_no if group_no is not None else group.primary_channel
                type_combinations[profile][
                    (
                        section.channels.get(primary) if primary is not None else None,
                        section.channels.get(group.state_channel) if group.state_channel is not None else None,
                    )
                ].append(model)
                roles: list[tuple[str, int | None]] = [("primary", primary), ("state", group.state_channel)]
                roles.extend(("secondary", secondary) for secondary in group.secondary_channels)
                for role, channel_no in roles:
                    if channel_no is None:
                        continue
                    covered.add(channel_no)
                    if channel_no not in section.channels:
                        missing_channels.append((model, profile, role, channel_no))

                resolved: list[tuple[str, int | None, Mapping[Field, FieldValue]]] = [("fields", primary, group.fields)]
                resolved.extend(
                    ("channel_fields", channel_no if channel_no is not None else primary, mapping)
                    for channel_no, mapping in group.channel_fields.items()
                )
                resolved.extend(
                    ("fixed_channel_fields", channel_no, mapping)
                    for channel_no, mapping in group.fixed_channel_fields.items()
                )
                if config.extended and config.extended.fixed_channel_fields:
                    resolved.extend(
                        ("extended.fixed_channel_fields", channel_no, mapping)
                        for channel_no, mapping in config.extended.fixed_channel_fields.items()
                    )
                for role, channel_no, mapping in resolved:
                    for field_name, value in mapping.items():
                        parameter, _ = resolve_field_value(field_value=value)
                        field_results[(profile, role, str(field_name), parameter.value)].append(
                            (model, channel_no, section.has_parameter(channel_no=channel_no, parameter=parameter.value))
                        )
            covered.update(channel_no for channel_no in relevant if channel_no is not None)

        if receivers := {
            no: name for no, name in section.channels.items() if "VIRTUAL_RECEIVER" in name and no not in covered
        }:
            uncovered.append(
                (
                    model,
                    ", ".join(sorted({config.profile_type.value for config in configs})),
                    ", ".join(f"{no}: {name}" for no, name in sorted(receivers.items())),
                    section.reference,
                )
            )

    out += ["## 1. Coverage", ""]
    out += [
        f"- Models with a current section: {len(latest)}",
        f"- With a configuration: {len(latest) - len(no_config)}",
    ]
    out += [f"- Without a configuration: {len(no_config)}", ""]

    out += ["## 2. Configured channel does not exist on the model", ""]
    _write_table(out=out, header=("Model", "Profile", "Role", "Channel"), rows=sorted(missing_channels))

    out += ["## 3. Channel types per profile (primary, state)", "", "Rare combinations are worth reading.", ""]
    rows: list[tuple[object, ...]] = []
    for profile, combinations in sorted(type_combinations.items()):
        rows.extend(
            (profile, primary_type, state_type, len(models), ", ".join(sorted(set(models))))
            for (primary_type, state_type), models in sorted(
                combinations.items(), key=lambda item: (-len(item[1]), str(item[0]))
            )
        )
    _write_table(out=out, header=("Profile", "Primary type", "State type", "Groups", "Models"), rows=rows)

    out += ["## 4. Profile field whose parameter is not documented on the resolved channel", ""]
    out += ["`found` counts the channel groups where it exists. Low values usually mean an optional field.", ""]
    rows = []
    for (profile, role, field_name, parameter), results in sorted(field_results.items()):
        if failing := [result for result in results if not result[2]]:
            rows.append(
                (
                    profile,
                    role,
                    field_name,
                    parameter,
                    f"{len(results) - len(failing)}/{len(results)}",
                    ", ".join(sorted({f"{model}:{channel_no}" for model, channel_no, _ in failing})),
                )
            )
    _write_table(out=out, header=("Profile", "Role", "Field", "Parameter", "found", "Missing on"), rows=rows)

    out += ["## 5. VIRTUAL_RECEIVER channels outside every channel group", ""]
    _write_table(out=out, header=("Model", "Profiles", "Channels", "Source"), rows=uncovered)

    out += ["## 6. Models without a configuration", "", "These get generic data points only.", ""]
    _write_table(out=out, header=("Model", "Description", "Channel types", "Source"), rows=no_config)

    out += ["## 7. Models resolved by prefix", "", "Check these against section 3 and 4.", ""]
    _write_table(out=out, header=("Model", "Matched key", "Channels", "Source"), rows=prefix_rows)

    documented = {model.lower() for section in sections for model, _, _, _ in section.models}

    def undocumented(models: Iterable[str]) -> list[str]:
        return sorted(
            {
                model
                for model in models
                if model.lower().startswith(_REGISTERED_PREFIXES)
                and not any(doc == model.lower() or doc.startswith(model.lower()) for doc in documented)
            }
        )

    out += ["## 8. Known models without any documented model", "", f"Limited to prefixes {_REGISTERED_PREFIXES}.", ""]
    registered = [key for entries in DeviceProfileRegistry._configs.values() for key in entries]
    rule_models = {model for models in IGNORE_PARAMETERS_BY_DEVICE.values() for model in models}
    rule_models.update(UN_IGNORE_PARAMETERS_BY_DEVICE)
    _write_table(
        out=out,
        header=("Source", "Models"),
        rows=[
            ("DeviceProfileRegistry", ", ".join(undocumented(registered))),
            ("store/visibility/rules.py", ", ".join(undocumented(rule_models))),
            ("operating_voltage_level.py", ", ".join(undocumented(battery.model for battery in _BATTERY_DATA))),
        ],
    )

    voltage_models = (*_OPERATING_VOLTAGE_LEVEL_MODELS, *_IGNORE_OPERATING_VOLTAGE_LEVEL_MODELS)
    ignored = IGNORE_PARAMETERS_BY_DEVICE_LOWER.get("OPERATING_VOLTAGE", [])
    without_battery: list[tuple[str, str, str]] = []
    visible_voltage: list[tuple[str, str, str]] = []
    for model, section in sorted(latest.items()):
        maintenance = section.channels.get(0, "")
        if not section.has_parameter(channel_no=0, parameter="OPERATING_VOLTAGE"):
            continue
        if maintenance.startswith("MAINTENANCE_BAT"):
            if not element_matches_key(search_elements=voltage_models, compare_with=model):
                without_battery.append((model, maintenance, section.reference))
        elif not element_matches_key(search_elements=ignored, compare_with=model.lower()):
            visible_voltage.append((model, maintenance, section.reference))

    out += [
        "## 9. OPERATING_VOLTAGE",
        "",
        "That `MAINTENANCE_BAT*` means battery powered is read from the type name only.",
        "",
    ]
    out += ["### Channel 0 is `MAINTENANCE_BAT*`, no entry in `_BATTERY_DATA`", ""]
    _write_table(out=out, header=("Model", "Channel 0", "Source"), rows=without_battery)
    out += ["### Channel 0 is not `MAINTENANCE_BAT*`, parameter not ignored by `rules.py`", ""]
    _write_table(out=out, header=("Model", "Channel 0", "Source"), rows=visible_voltage)
    return out


def main() -> int:
    """Run the comparison."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path, help="Path of the documentation PDF.")
    parser.add_argument("--output", type=Path, help="Write the report to this file instead of stdout.")
    args = parser.parse_args()

    if not Path(_AIOHOMEMATIC_FILE).resolve().is_relative_to(_REPO_ROOT / "aiohomematic"):
        sys.exit(f"Imported {_AIOHOMEMATIC_FILE} instead of the repository")

    text = _extract_text(pdf=args.pdf)
    sections, errors = _parse(text=text)
    latest, without_current = _latest_sections(sections=sections)
    errors.extend(f"{model}: no open-ended firmware range" for model in without_current)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2

    title = re.search(r"based on crRFD version: (\S+)", text)
    created = re.search(r"Documentation creation date: (\S+)", text)
    report = [
        "# HmIP device documentation vs. device definitions",
        "",
        f"- PDF: crRFD {title[1] if title else 'unknown'}, created {created[1] if created else 'unknown'}",
        f"- aiohomematic: {VERSION}",
        f"- Parsed: {len(sections)} sections, {len(latest)} models",
        "",
        *_compare(latest=latest, sections=sections),
    ]
    content = "\n".join(report)
    if args.output:
        args.output.write_text(content + "\n")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
