"""Every entity of the integration in the example dashboards exists, with all options on.

The compact view is inline in docs/dashboard.md, the full view is its own file,
docs/dashboard-full.yaml.
"""

from __future__ import annotations

from pathlib import Path
import re

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
import yaml

from .test_config_flow import DOMAIN, RTU

DOCS = Path(__file__).resolve().parent.parent / "docs"
DASHBOARD = DOCS / "dashboard.md"
FULL_VIEW = DOCS / "dashboard-full.yaml"


def _entity_ids() -> set[str]:
    text = DASHBOARD.read_text()
    found: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "entity":
                    found.add(value)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    blocks = re.findall(r"```yaml\n(.*?)```", text, re.S)
    assert blocks, "the compact view is no longer inline in dashboard.md"
    blocks.append(FULL_VIEW.read_text())
    assert "dashboard-full.yaml" in text, "dashboard.md does not link the full view"
    for block in blocks:
        walk(yaml.safe_load(block))
    # Only the integration's own entities; e.g. the weather card is the user's.
    return {i for i in found if ".lg_therma_v_r290_" in i}


async def test_every_dashboard_entity_exists(hass, unit) -> None:
    hass.states.async_set("sensor.meter_power", "1", {"unit_of_measurement": "kW"})
    hass.states.async_set("sensor.meter_energy", "1", {"unit_of_measurement": "kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"connection_type": "rtu", **RTU},
        options={
            "energy_registers": True,
            "compressor_modulation_limit": True,
            "power_limit": True,
            "emergency_operation_button": True,
            "experimental_registers": True,
            "compressor_statistics": True,
            "poll_statistics": True,
            "external_power_sensor": "sensor.meter_power",
            "external_energy_sensor": "sensor.meter_energy",
        },
        version=1,
        minor_version=4,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    ids = _entity_ids()
    assert len(ids) > 20
    missing = sorted(i for i in ids if registry.async_get(i) is None)
    assert missing == []


def _counts_table() -> str:
    """The markdown card with starts and defrosts, today and total."""
    view = yaml.safe_load(FULL_VIEW.read_text())["views"][0]
    for section in view["sections"]:
        for card in section["cards"]:
            if (
                card["type"] == "markdown"
                and "compressor_starts" in card["content"]
                and "<table" in card["content"]
            ):
                return card["content"]
    raise AssertionError("the starts and defrosts table is gone")


async def test_the_starts_and_defrosts_table(hass, unit) -> None:
    from homeassistant.helpers.template import Template

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
    stats = entry.runtime_data.compressor_stats
    stats.starts, stats.day_starts, stats.run_s = 31, 3, 240.4 * 3600
    stats.day_run_s = 3.2 * 3600
    stats.defrosts, stats.day_defrosts = 7, 2
    stats.defrost_s, stats.day_defrost_s = 42 * 60, 14 * 60
    stats.last_run_s, stats.last_defrost_s = 23 * 60, 6 * 60
    stats.defrost_ws, stats.day_defrost_ws = 1.84 * 3_600_000, 0.42 * 3_600_000
    entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    text = Template(_counts_table(), hass).async_render()
    rows = [
        [
            re.sub(r"<[^>]+>", "", cell).strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row)
        ]
        for row in re.findall(r"<tr>(.*?)</tr>", text)
    ]
    assert rows == [
        ["", "Today", "Total"],
        ["Starts", "3", "31"],
        ["Run time", "3.2 h", "240 h"],
        ["Defrosts", "2", "7"],
        ["Defrost time", "14 min", "42 min"],
        ["Defrost energy", "0.42 kWh", "1.8 kWh"],
        # below: when the last run and defrost were, and how long they lasted
        ["", "When", "Lasted"],
        rows[7][:2] + ["23 min"],
        rows[8][:2] + ["6 min"],
    ]
    assert rows[7][0] == "Last run" and rows[8][0] == "Last defrost"
