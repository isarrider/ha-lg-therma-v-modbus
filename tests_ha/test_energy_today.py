"""Today's growth of the unit's energy counters (attribute today_kwh)."""

from __future__ import annotations

from homeassistant.core import State
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from .test_config_flow import DOMAIN, RTU

ELECTRICAL = "sensor.lg_therma_v_r290_electrical_energy_space_heating"
ELECTRICAL_TOTAL = "sensor.lg_therma_v_r290_electrical_energy_total"
THERMAL = "sensor.lg_therma_v_r290_thermal_energy_space_heating"
POWER = "sensor.lg_therma_v_r290_electrical_power_heat_pump"

# Input registers of the 32-bit counters, high word first (energy.py).
ADDRESS = {ELECTRICAL_TOTAL: 38, ELECTRICAL: 40, THERMAL: 50}


def _set(unit, entity_id: str, wh: int) -> None:
    address = ADDRESS[entity_id]
    unit.values[("input", address)] = wh >> 16
    unit.values[("input", address + 1)] = wh & 0xFFFF


async def _set_up(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"connection_type": "rtu", **RTU},
        options={"energy_registers": True},
        version=1,
        minor_version=4,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_today_counts_from_the_first_poll_and_resets_at_midnight(
    hass, unit, freezer
) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-11-24 07:00:00+00:00")  # 08:00 in Berlin
    _set(unit, ELECTRICAL, 2_811_000)
    _set(unit, THERMAL, 7_388_000)
    entry = await _set_up(hass)
    coordinator = entry.runtime_data
    assert hass.states.get(ELECTRICAL).attributes["today_kwh"] == 0
    assert hass.states.get(ELECTRICAL).attributes["modbus_register"] == 30041

    _set(unit, ELECTRICAL, 2_815_520)
    _set(unit, THERMAL, 7_405_810)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ELECTRICAL).attributes["today_kwh"] == 4.52
    assert hass.states.get(THERMAL).attributes["today_kwh"] == 17.81
    # The state stays the unit's total counter.
    assert float(hass.states.get(ELECTRICAL).state) == pytest.approx(2815.52)

    # After midnight, today starts at the last value of the day before.
    freezer.move_to("2026-11-24 23:00:30+00:00")  # 00:00:30 on the 25th
    _set(unit, ELECTRICAL, 2_815_540)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ELECTRICAL).attributes["today_kwh"] == 0.02


async def test_power_sensors_have_no_today(hass, unit) -> None:
    await _set_up(hass)
    assert "today_kwh" not in hass.states.get(POWER).attributes


async def test_a_restart_continues_the_day(hass, unit, freezer) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-11-24 10:00:00+00:00")  # 11:00 in Berlin
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(ELECTRICAL, "2815.52"),
                {"day": "2026-11-24", "start": 2_811_000, "last": 2_815_520},
            ),
            (
                # Stored yesterday: not carried over.
                State(THERMAL, "7405.81"),
                {"day": "2026-11-23", "start": 7_388_000, "last": 7_405_810},
            ),
        ],
    )
    _set(unit, ELECTRICAL, 2_816_000)  # 0.48 kWh used while HA was down
    _set(unit, THERMAL, 7_407_000)
    await _set_up(hass)
    assert hass.states.get(ELECTRICAL).attributes["today_kwh"] == 5.0
    assert hass.states.get(THERMAL).attributes["today_kwh"] == 0
