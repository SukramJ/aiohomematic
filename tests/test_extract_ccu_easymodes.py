"""Tests for the CCU easymode extraction script."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "script" / "extract_ccu_easymodes.py"
_SPEC = importlib.util.spec_from_file_location("extract_ccu_easymodes", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
_EXTRACT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EXTRACT)


class TestMergeUnlabeledGroups:
    """Guard: groups without a label ref must not leak as standalone sections."""

    def test_all_labeled_pass_through(self) -> None:
        groups = [(["A"], "lblA"), (["B"], "lblB")]
        assert _EXTRACT._merge_unlabeled_groups(groups) == [(["A"], "lblA"), (["B"], "lblB")]

    def test_all_unlabeled_returned_unchanged(self) -> None:
        # Defensive: if nothing has a label we don't pick a winner.
        groups = [(["A"], ""), (["B"], "")]
        assert _EXTRACT._merge_unlabeled_groups(groups) == [(["A"], ""), (["B"], "")]

    def test_does_not_reorder_within_groups(self) -> None:
        groups = [(["LONGITUDE", "EXTRA"], ""), (["LATITUDE"], "lblLocation")]
        merged = _EXTRACT._merge_unlabeled_groups(groups)
        assert merged == [(["LONGITUDE", "EXTRA", "LATITUDE"], "lblLocation")]

    def test_empty_input(self) -> None:
        assert _EXTRACT._merge_unlabeled_groups([]) == []

    def test_interleaved(self) -> None:
        groups = [
            (["A"], "lblA"),
            (["B"], ""),
            (["C"], "lblC"),
            (["D"], ""),
            (["E"], "lblE"),
        ]
        assert _EXTRACT._merge_unlabeled_groups(groups) == [
            (["A"], "lblA"),
            (["B", "C"], "lblC"),
            (["D", "E"], "lblE"),
        ]

    def test_multiple_unlabeled_before_labeled(self) -> None:
        groups = [(["A"], ""), (["B"], ""), (["C"], "lblC")]
        assert _EXTRACT._merge_unlabeled_groups(groups) == [(["A", "B", "C"], "lblC")]

    def test_trailing_unlabeled_attached_to_last_labeled(self) -> None:
        groups = [(["A"], "lblA"), (["B"], "")]
        assert _EXTRACT._merge_unlabeled_groups(groups) == [(["A", "B"], "lblA")]

    def test_unlabeled_group_merged_into_next_labeled(self) -> None:
        # Reproduces HmIP-PSM-CO MAINTENANCE case: LONGITUDE(no label) + LATITUDE(lblLocation)
        groups = [(["LONGITUDE"], ""), (["LATITUDE"], "lblLocation")]
        merged = _EXTRACT._merge_unlabeled_groups(groups)
        assert merged == [(["LONGITUDE", "LATITUDE"], "lblLocation")]
