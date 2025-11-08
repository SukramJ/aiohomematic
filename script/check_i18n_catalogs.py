# SPDX-License-Identifier: MIT
"""
Pre-commit hook to validate i18n catalogs and usage.

Checks performed:
1) Ensure that every translation key used in code via i18n.tr("key")/tr("key")
   exists in the base catalog `translations/strings.json`.
2) Ensure `translations/en.json` is always an exact copy of `strings.json`.
   With --fix, overwrite `en.json` accordingly.
3) For `translations/de.json`, report which entries are missing (compared to
   `strings.json`) and which are extra. Do not auto-remove/auto-add.
4) Ensure the json files (`strings.json`, `en.json`, `de.json`) are sorted by key
   and pretty formatted. With --fix, rewrite sorted files.

Exit code:
- 0: All checks passed and no modifications were necessary.
- 1: Any problems were found or files were modified (when --fix is used).

Usage in pre-commit: run with `--fix` to allow auto-fixes (en.json sync + sorting).
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
import json
from pathlib import Path

# Project paths
ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS_DIR = ROOT / "aiohomematic" / "translations"
STRINGS_JSON = TRANSLATIONS_DIR / "strings.json"
EN_JSON = TRANSLATIONS_DIR / "en.json"
DE_JSON = TRANSLATIONS_DIR / "de.json"

CODE_DIRS = [ROOT / "aiohomematic"]  # scan code here for i18n.tr usage


@dataclass
class Findings:
    """Container for problems detected across catalogs and usage."""

    missing_in_strings: set[str]
    de_missing: set[str]
    de_extra: set[str]

    def has_problems(self) -> bool:
        """Return True if any issue has been detected."""
        return bool(self.missing_in_strings or self.de_missing or self.de_extra)


def _iter_py_files() -> Iterable[Path]:
    """Yield all Python files from the code directories."""
    for base in CODE_DIRS:
        if not base.exists():
            continue
        yield from base.rglob("*.py")


def _collect_used_keys() -> set[str]:
    """Parse Python files and collect keys used in i18n.tr("...") or tr("...")."""
    keys: set[str] = set()

    def is_tr_call(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        # i18n.tr("...")
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.attr == "tr"
            and func.value.id == "i18n"
        ):
            return True
        # tr("...") imported into scope
        return isinstance(func, ast.Name) and func.id == "tr"

    def extract_literal_key(arg: ast.AST) -> str | None:
        # accept string literal only (Constant with str)
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
        # Do not attempt to evaluate f-strings or variables; only literal keys matter.
        return None

    for path in _iter_py_files():
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not is_tr_call(node):
                continue
            if not node.args:
                continue
            key = extract_literal_key(node.args[0])
            if key:
                keys.add(key)
    return keys


def _load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    # normalize to str->str mapping
    return {str(k): str(v) for k, v in data.items()}


def _dump_sorted_json(path: Path, data: dict[str, str]) -> None:
    # Ensure deterministic order and formatting
    sorted_items = dict(sorted(data.items(), key=lambda kv: kv[0]))
    text = json.dumps(sorted_items, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def run(fix: bool) -> int:
    """
    Run the i18n catalogs check and return an appropriate exit code.

    When `fix` is True, the function will synchronize `en.json` to `strings.json`
    and sort/pretty-print the catalogs, asking pre-commit to re-run by returning 1.
    """
    problems: list[str] = []
    modified = False

    used_keys = _collect_used_keys()

    strings = _load_json(STRINGS_JSON)
    en = _load_json(EN_JSON)
    de = _load_json(DE_JSON)

    # 1) used keys must be in strings.json
    missing_in_strings = {k for k in used_keys if k not in strings}
    if missing_in_strings:
        problems.extend(f"Missing key in strings.json: {k}" for k in sorted(missing_in_strings))

    # 2) en.json must equal strings.json
    if en != strings:
        if fix:
            # Overwrite en.json to match strings.json, sorted
            _dump_sorted_json(EN_JSON, strings)
            modified = True
        else:
            problems.append("en.json differs from strings.json (run with --fix to sync)")

    # 3) de.json differences
    strings_keys = set(strings.keys())
    de_keys = set(de.keys())
    de_missing = strings_keys - de_keys
    de_extra = de_keys - strings_keys
    problems.extend(f"de.json missing key: {k}" for k in sorted(de_missing))
    problems.extend(f"de.json has extra key not in strings.json: {k}" for k in sorted(de_extra))

    # 4) ensure sorted JSON files
    def ensure_sorted(path: Path, current: dict[str, str]) -> None:
        nonlocal modified
        # Compare to sorted dump
        sorted_items = dict(sorted(current.items(), key=lambda kv: kv[0]))
        expected_text = json.dumps(sorted_items, ensure_ascii=False, indent=2) + "\n"
        try:
            existing_text = path.read_text(encoding="utf-8")
        except Exception:
            existing_text = ""
        if existing_text != expected_text:
            if fix:
                _dump_sorted_json(path, current)
                modified = True
            else:
                problems.append(f"File not sorted/formatted: {path.relative_to(ROOT)} (run with --fix)")

    ensure_sorted(STRINGS_JSON, strings)
    ensure_sorted(EN_JSON, _load_json(EN_JSON))  # re-load in case it was missing
    ensure_sorted(DE_JSON, de)

    # Print problems
    for msg in problems:
        print(msg)

    # If anything modified, ask pre-commit to re-run (exit non-zero)
    if modified:
        return 1

    # Fail if problems were found
    if problems:
        return 1

    return 0


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point for running the catalogs check."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="Apply automatic fixes (sync en.json, sort files)")
    args = parser.parse_args(list(argv) if argv is not None else None)
    return run(fix=args.fix)


if __name__ == "__main__":
    raise SystemExit(main())
