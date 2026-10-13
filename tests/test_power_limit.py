"""Encoding and write rules of the unverified power limit (holding 24, coil 6).

power_limit.py imports nothing from Home Assistant, so no install is needed.
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


power_limit = _load("power_limit")
const = _load("const")
experimental = _load("experimental")


def test_addresses() -> None:
    assert power_limit.POWER_LIMIT_REGISTER == 24
    assert power_limit.POWER_LIMIT_COIL == 6


def test_encode_is_tenths_of_a_kw() -> None:
    assert power_limit.encode(0.1) == 1
    assert power_limit.encode(3.5) == 35
    assert power_limit.encode(25.0) == 250


def test_encode_clamps_to_the_slider_range() -> None:
    assert power_limit.encode(0) == 1  # never writes 0 by accident
    assert power_limit.encode(-2) == 1
    assert power_limit.encode(25.1) == 250
    assert power_limit.encode(1000) == 250


def test_decode_keeps_zero_apart() -> None:
    data = power_limit.decode(0, False)
    assert data[power_limit.DATA_KEY_KW] is None
    assert data[power_limit.DATA_KEY_RAW] == 0
    assert data[power_limit.DATA_KEY_ACTIVE] is False


def test_decode_reports_the_limit_and_the_coil() -> None:
    data = power_limit.decode(35, True)
    assert data[power_limit.DATA_KEY_KW] == 3.5
    assert data[power_limit.DATA_KEY_ACTIVE] is True
    # Unexpected values are shown, not hidden by clamping.
    assert power_limit.decode(400, False)[power_limit.DATA_KEY_KW] == 40.0


def test_not_writable_unless_the_option_adds_them() -> None:
    assert power_limit.POWER_LIMIT_REGISTER not in const.WRITABLE_HOLDING_REGISTERS
    assert power_limit.POWER_LIMIT_COIL not in const.WRITABLE_COILS
    assert {
        power_limit.POWER_LIMIT_REGISTER
    } == const.POWER_LIMIT_WRITABLE_HOLDING_REGISTERS
    assert {power_limit.POWER_LIMIT_COIL} == const.POWER_LIMIT_WRITABLE_COILS


def test_separate_from_the_modulation_limit_option() -> None:
    """Switching one option on must not make the other's address writable."""
    assert not (
        const.POWER_LIMIT_WRITABLE_HOLDING_REGISTERS
        & const.OPTIONAL_WRITABLE_HOLDING_REGISTERS
    )


def test_coil_5_stays_unwritable() -> None:
    """Coil 5 triggers emergency operation; this option must not reach it."""
    assert 5 not in const.POWER_LIMIT_WRITABLE_COILS


def test_not_an_experimental_register() -> None:
    for kind, start, count in experimental.EXPERIMENTAL_BLOCKS:
        if kind == "holding":
            assert not start <= power_limit.POWER_LIMIT_REGISTER < start + count
