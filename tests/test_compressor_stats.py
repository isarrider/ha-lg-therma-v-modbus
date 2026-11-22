"""Compressor starts, run time and average speed (compressor_stats.py).

compressor_stats.py imports nothing from Home Assistant, so none of this needs
an install.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

COMPONENT = (
    Path(__file__).resolve().parent.parent / "custom_components" / "lg_therma_v_r290"
)


def _load(module_name: str):
    package = "lg_therma_v_r290_under_test"
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


cs = _load("compressor_stats")
DAY = "2026-10-13"


def _run(stats, samples, day=DAY):
    for on, rpm, time_s in samples:
        stats.add(on, rpm, time_s, day)


def test_starts_run_time_and_average_speed() -> None:
    stats = cs.CompressorStats()
    _run(
        stats,
        [
            (False, 0, 0),
            (True, 1800, 10),  # start 1
            (True, 2400, 70),  # 60 s at 1800
            (False, 0, 130),  # 60 s at 2400, stop
            (False, 0, 190),
            (True, 3000, 250),  # start 2
            (False, 0, 280),  # 30 s at 3000
        ],
    )
    assert stats.starts == 2
    assert stats.run_s == 150
    # (60 × 1800 + 60 × 2400 + 30 × 3000) / 150 = 2280
    assert stats.average_rpm_today == 2280
    assert stats.last_run_s == 30


def test_a_restart_or_first_poll_is_no_start() -> None:
    stats = cs.CompressorStats()
    _run(stats, [(True, 2000, 0), (True, 2000, 10)])
    assert stats.starts == 0
    assert stats.run_s == 10


def test_unknown_and_gaps_are_not_counted() -> None:
    stats = cs.CompressorStats()
    _run(
        stats,
        [
            (False, 0, 0),
            (None, None, 10),  # unit did not answer
            (True, 2000, 20),  # off -> unknown -> on: not a counted start
            (True, 2000, 20 + cs.MAX_GAP_S + 1),  # Home Assistant was down
        ],
    )
    assert stats.starts == 0
    assert stats.run_s == 0


def test_average_speed_resets_at_midnight() -> None:
    stats = cs.CompressorStats()
    _run(stats, [(True, 2000, 0), (True, 2000, 60)], day="2026-10-12")
    assert stats.average_rpm_today == 2000
    # The first poll of the new day closes the interval across midnight,
    # which counts to the new day: 60 s at the 2000 rpm seen before.
    stats.add(True, 3000, 120, "2026-10-13")
    assert stats.average_rpm_today == 2000
    assert stats.run_s == 120  # run time keeps counting
    stats.add(True, 3000, 180, "2026-10-13")
    assert stats.average_rpm_today == 2500  # (60 × 2000 + 60 × 3000) / 120


def test_restore_continues_and_keeps_only_todays_average() -> None:
    old = cs.CompressorStats()
    _run(old, [(False, 0, 0), (True, 2000, 10), (False, 0, 70)])
    saved = old.state()

    same_day = cs.CompressorStats()
    same_day.add(False, 0, 0, DAY)
    same_day.restore(saved)
    assert same_day.starts == 1
    assert same_day.run_s == 60
    assert same_day.average_rpm_today == 2000

    next_day = cs.CompressorStats()
    next_day.add(False, 0, 0, "2026-10-14")
    next_day.restore(saved)
    assert next_day.starts == 1
    assert next_day.average_rpm_today is None  # yesterday's average is gone


def _defrosts(stats, samples, day=DAY):
    """(defrost, time) with the compressor off throughout."""
    for defrost, time_s in samples:
        stats.add(False, 0, time_s, day, defrost)


def test_defrosts_and_defrost_time() -> None:
    stats = cs.CompressorStats()
    _defrosts(
        stats,
        [
            (False, 0),
            (True, 30),  # defrost 1
            (True, 90),  # 60 s
            (False, 150),  # 60 s, over: 120 s
            (True, 400),  # defrost 2
            (False, 430),  # 30 s
        ],
    )
    assert stats.defrosts == 2
    assert stats.defrost_s == 150
    assert stats.defrost_minutes == 2.5
    assert stats.last_defrost_s == 30
    assert (stats.day_defrosts, stats.day_defrost_s) == (2, 150)


def test_a_defrost_at_the_first_poll_or_after_unknown_is_not_counted() -> None:
    stats = cs.CompressorStats()
    _defrosts(stats, [(True, 0), (True, 30), (None, 60), (True, 90)])
    assert stats.defrosts == 0
    # Each interval counts with the state of the poll before it: 0-30 s and
    # 30-60 s were defrosting; 60-90 s follows an unknown poll and is left out.
    assert stats.defrost_s == 60


def test_today_counts_reset_at_midnight_and_totals_keep_going() -> None:
    stats = cs.CompressorStats()
    for on, defrost, time_s in (
        (False, False, 0),
        (True, True, 30),
        (False, False, 90),
    ):
        stats.add(on, 2000 if on else 0, time_s, "2026-10-12", defrost)
    assert (stats.day_starts, stats.day_defrosts) == (1, 1)
    stats.add(True, 2000, 150, "2026-10-13", True)
    assert (stats.starts, stats.defrosts) == (2, 2)
    assert (stats.day_starts, stats.day_defrosts) == (1, 1)  # today's only


def test_restore_keeps_defrosts_and_todays_counts() -> None:
    old = cs.CompressorStats()
    for on, defrost, time_s in (
        (False, False, 0),
        (True, True, 30),
        (False, False, 90),
    ):
        old.add(on, 2000 if on else 0, time_s, DAY, defrost)
    saved = old.state()

    same_day = cs.CompressorStats()
    same_day.add(False, 0, 0, DAY, False)
    same_day.restore(saved)
    assert (same_day.defrosts, same_day.defrost_s) == (1, 60)
    assert (same_day.day_starts, same_day.day_defrosts) == (1, 1)
    assert same_day.last_defrost_s == 60

    next_day = cs.CompressorStats()
    next_day.add(False, 0, 0, "2026-10-14", False)
    next_day.restore(saved)
    assert next_day.defrosts == 1
    assert (next_day.day_starts, next_day.day_defrosts) == (0, 0)


def test_restore_from_before_defrosts_were_counted() -> None:
    """Restore data of 2.2.8 has no defrost or per-day counts: they start at 0."""
    stats = cs.CompressorStats()
    stats.add(False, 0, 0, DAY, False)
    stats.restore(
        {
            "starts": 41,
            "run_s": 36000.0,
            "day": DAY,
            "day_run_s": 600.0,
            "day_rpm_s": 1_200_000.0,
            "last_run_s": 900.0,
        }
    )
    assert stats.starts == 41
    assert (stats.defrosts, stats.defrost_s, stats.day_starts) == (0, 0.0, 0)
    assert stats.last_defrost_s is None
