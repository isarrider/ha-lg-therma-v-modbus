"""Label table of the ODU operation cycle (input 1, 30002).

const.py imports nothing from Home Assistant, so this needs no install.
The table is unverified on the R290 (see const.py); these tests pin what it
claims, so a change to it after measuring is a deliberate one.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

COMPONENT = (
    Path(__file__).resolve().parent.parent / "custom_components" / "lg_thermav_r290"
)


def _load(module_name: str):
    package = "lg_thermav_r290_under_test"
    if package not in sys.modules:
        stub = types.ModuleType(package)
        stub.__path__ = [str(COMPONENT)]
        sys.modules[package] = stub

    qualified = f"{package}.{module_name}"
    if qualified not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            qualified, COMPONENT / f"{module_name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
    return sys.modules[qualified]


const = _load("const")


def test_follows_lgs_table_for_30002() -> None:
    assert const.ODU_OPERATION_CYCLE_LABELS == {
        0: "Standby/Off",
        1: "Cooling",
        2: "Heating",
    }


def test_unlisted_values_are_left_unlabelled() -> None:
    """3 (defrost in one community setup) must stay visible as a number."""
    assert 3 not in const.ODU_OPERATION_CYCLE_LABELS


def test_labels_are_unique() -> None:
    labels = list(const.ODU_OPERATION_CYCLE_LABELS.values())
    assert len(labels) == len(set(labels))
