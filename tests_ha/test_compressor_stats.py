"""Compressor statistics inside Home Assistant."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import State
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from .test_config_flow import DOMAIN, RTU

STARTS = "sensor.lg_therma_v_r290_compressor_starts"
RUN_TIME = "sensor.lg_therma_v_r290_compressor_run_time"
SPEED = "sensor.lg_therma_v_r290_compressor_average_speed"
DEFROSTS = "sensor.lg_therma_v_r290_defrosts"
DEFROST_TIME = "sensor.lg_therma_v_r290_defrost_time"


class Compressor:
    """Discrete inputs 3 (compressor) and 4 (defrost), input 24 (speed / 60)."""

    def __init__(self, unit) -> None:
        self.on = False
        self.rpm = 0
        self.defrost = False
        read_di, read_in = unit.read_discrete_inputs, unit.read_input_registers

        async def discrete(address, count):
            values = await read_di(address, count)
            if address == 0:
                values[3] = self.on
                values[4] = self.defrost
            return values

        async def inputs(address, count):
            values = await read_in(address, count)
            if address == 16:
                values[8] = self.rpm // 60
            return values

        unit.read_discrete_inputs = discrete
        unit.read_input_registers = inputs


async def _set_up(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"connection_type": "rtu", **RTU},
        options={"compressor_statistics": True},
        version=1,
        minor_version=4,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_counts_from_polls(hass, unit) -> None:
    compressor = Compressor(unit)
    clock = iter(float(t) for t in range(0, 10_000, 60))
    with patch(
        "custom_components.lg_therma_v_r290.coordinator._monotonic",
        side_effect=lambda: next(clock),
    ):
        entry = await _set_up(hass)  # poll at t=0: off
        coordinator = entry.runtime_data
        for on, rpm in (
            (True, 1800),
            (True, 2400),
            (False, 0),
            (True, 3000),
            (False, 0),
        ):
            compressor.on, compressor.rpm = on, rpm
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert hass.states.get(STARTS).state == "2"
    assert hass.states.get(STARTS).attributes["today"] == 2
    assert hass.states.get(STARTS).attributes["last_run_minutes"] == 1.0
    assert hass.states.get(RUN_TIME).attributes["today"] == 0.05
    assert float(hass.states.get(RUN_TIME).state) == round(180 / 3600, 3)
    assert hass.states.get(RUN_TIME).attributes["unit_of_measurement"] == "h"
    # (60 × 1800 + 60 × 2400 + 60 × 3000) / 180 = 2400
    assert hass.states.get(SPEED).state == "2400"


async def test_defrosts_from_polls(hass, unit) -> None:
    compressor = Compressor(unit)
    clock = iter(float(t) for t in range(0, 10_000, 60))
    with patch(
        "custom_components.lg_therma_v_r290.coordinator._monotonic",
        side_effect=lambda: next(clock),
    ):
        entry = await _set_up(hass)  # poll at t=0: no defrost
        coordinator = entry.runtime_data
        for defrost in (True, True, True, False, True, False):
            compressor.defrost = defrost
            await coordinator.async_refresh()
        await hass.async_block_till_done()

    defrosts = hass.states.get(DEFROSTS)
    assert defrosts.state == "2"
    assert defrosts.attributes["today"] == 2
    assert defrosts.attributes["last_defrost_minutes"] == 1.0
    assert defrosts.attributes["state_class"] == "total_increasing"
    defrost_time = hass.states.get(DEFROST_TIME)
    assert float(defrost_time.state) == 4.0  # 3 + 1 minutes
    assert defrost_time.attributes["unit_of_measurement"] == "min"
    assert defrost_time.attributes["today"] == 4.0


async def test_restart_continues(hass, unit) -> None:
    Compressor(unit)
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(STARTS, "41"),
                {
                    "starts": 41,
                    "run_s": 36000.0,
                    "day": None,
                    "day_run_s": 0.0,
                    "day_rpm_s": 0.0,
                    "last_run_s": 900.0,
                },
            )
        ],
    )
    await _set_up(hass)
    assert hass.states.get(STARTS).state == "41"
    assert float(hass.states.get(RUN_TIME).state) == 10.0
    assert hass.states.get(STARTS).attributes["last_run_minutes"] == 15.0
    # Stored by 2.2.8, without defrosts: they start at 0.
    assert hass.states.get(DEFROSTS).state == "0"
    assert float(hass.states.get(DEFROST_TIME).state) == 0.0


async def test_restart_keeps_defrosts(hass, unit) -> None:
    Compressor(unit)
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(STARTS, "41"),
                {
                    "starts": 41,
                    "run_s": 36000.0,
                    "day": None,
                    "day_run_s": 0.0,
                    "day_rpm_s": 0.0,
                    "last_run_s": 900.0,
                    "defrosts": 7,
                    "defrost_s": 2520.0,
                    "day_starts": 0,
                    "day_defrosts": 0,
                    "day_defrost_s": 0.0,
                    "last_defrost_s": 360.0,
                },
            )
        ],
    )
    await _set_up(hass)
    assert hass.states.get(DEFROSTS).state == "7"
    assert float(hass.states.get(DEFROST_TIME).state) == 42.0
    assert hass.states.get(DEFROSTS).attributes["last_defrost_minutes"] == 6.0


async def test_not_created_without_the_option(hass, unit) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"connection_type": "rtu", **RTU},
        version=1,
        minor_version=4,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(STARTS) is None
    assert hass.states.get(DEFROSTS) is None
    assert entry.runtime_data.compressor_stats is None
