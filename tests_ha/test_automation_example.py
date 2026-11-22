"""The example automations in docs/automations.md are valid and use real entities.

Each automation is its own file in docs/, linked from docs/automations.md.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import re

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)
import yaml

from custom_components.lg_therma_v_r290.const import CONTROL_METHOD_OPTIONS

from .test_config_flow import DOMAIN, RTU

DOCS = Path(__file__).resolve().parent.parent / "docs"
AUTOMATIONS = DOCS / "automations.md"
FILES = [
    DOCS / "therma-v-start.yaml",
    DOCS / "autotemp-heat-circuit-1.yaml",
    DOCS / "therma-v-stop.yaml",
]
STATUS_CARD = DOCS / "autotemp-status-card.yaml"
STATUS_TEMPLATE = DOCS / "autotemp-status-template.jinja"


def test_automations_md_links_every_file() -> None:
    text = AUTOMATIONS.read_text()
    missing = [
        f.name
        for f in [*FILES, STATUS_CARD, STATUS_TEMPLATE]
        if f"]({f.name})" not in text
    ]
    assert missing == []


def _configs() -> list[dict]:
    return [yaml.safe_load(f.read_text()) for f in FILES]


def _texts() -> str:
    files = [*FILES, STATUS_CARD, STATUS_TEMPLATE]
    return AUTOMATIONS.read_text() + "".join(f.read_text() for f in files)


def test_control_method_options_exist() -> None:
    used = set(re.findall(r"(\w+ Water Temp Control|Room Air Control)", _texts()))
    assert used
    assert used <= set(CONTROL_METHOD_OPTIONS)


async def test_every_automation_entity_exists(hass, unit) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"connection_type": "rtu", **RTU},
        options={"compressor_modulation_limit": True},
        version=1,
        minor_version=4,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    ids = set(re.findall(r"\b\w+\.lg_therma_v_r290_\w+", _texts()))
    assert len(ids) > 5
    missing = sorted(i for i in ids if registry.async_get(i) is None)
    assert missing == []


# The time and time_pattern triggers schedule timers that outlive the test.
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_automations_load(hass) -> None:
    configs = _configs()
    for i, config in enumerate(configs):
        config["id"] = f"example_{i}"
    assert await async_setup_component(hass, "automation", {"automation": configs})
    await hass.async_block_till_done()

    states = hass.states.async_all("automation")
    assert len(states) == len(configs)
    # An automation Home Assistant rejects is created unavailable.
    assert sorted(s.state for s in states) == ["on"] * len(configs)


AUTOTEMP = "automation.autotemp_heat_circuit_1"
SETPOINT = "number.lg_therma_v_r290_target_temperature_circuit_1_radiators"


async def _set_up_with_automations(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"connection_type": "rtu", **RTU},
        options={"compressor_modulation_limit": True},
        version=1,
        minor_version=4,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    configs = _configs()
    for i, config in enumerate(configs):
        config["id"] = f"example_{i}"
    assert await async_setup_component(hass, "automation", {"automation": configs})
    await hass.async_block_till_done()


def _raise_situation(unit) -> None:
    """Inlet control, setpoint 30 °C, inlet 34 °C, coil 5 °C, compressor on."""
    unit.values = {
        ("holding", 1): 1,
        ("holding", 2): 300,
        ("input", 2): 340,
        ("input", 20): 50,
        ("discrete", 3): 1,
    }


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_the_automations_explain_each_change_in_the_logbook(hass, unit) -> None:
    logbook = async_mock_service(hass, "logbook", "log")
    _raise_situation(unit)
    await _set_up_with_automations(hass)

    await hass.services.async_call(
        "automation", "trigger", {"entity_id": AUTOTEMP}, blocking=True
    )
    await hass.async_block_till_done()
    assert ("holding", 2, 310) in unit.writes
    assert [call.data for call in logbook] == [
        {
            "name": "AutoTemp",
            "entity_id": SETPOINT,
            "message": "raised to 31 °C: inlet 34.0 °C, 4.0 K above, close to thermo off",
        }
    ]

    await hass.services.async_call(
        "automation",
        "trigger",
        {"entity_id": "automation.therma_v_stop"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert logbook[-1].data["name"] == "Therma V stop"
    assert logbook[-1].data["message"].startswith("setpoint 20 °C")
    assert logbook[-1].data["entity_id"] == SETPOINT


def _card(hass) -> str:
    content = yaml.safe_load(STATUS_CARD.read_text())["content"]
    return " ".join(Template(content, hass).async_render().split())


async def test_the_status_card(hass, freezer) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-11-16 09:00:00+00:00")  # 10:00 in Berlin
    for entity_id, state in {
        AUTOTEMP: "on",
        SETPOINT: "35",
        "sensor.lg_therma_v_r290_inlet_temperature": "34.1",
        "sensor.lg_therma_v_r290_outlet_temperature": "36.0",
        "sensor.lg_therma_v_r290_temperature_before_evaporator": "4.2",
        "binary_sensor.lg_therma_v_r290_defrost": "off",
        "binary_sensor.lg_therma_v_r290_compressor": "on",
        "select.lg_therma_v_r290_control_method": "Inlet Water Temp Control",
    }.items():
        hass.states.async_set(entity_id, state)

    # The defrost ended just now: AutoTemp waits 5 minutes.
    assert _card(hass).endswith("AutoTemp: paused (defrost)")

    freezer.tick(timedelta(minutes=6))
    assert _card(hass).endswith(
        "AutoTemp: active<br> setpoint 35 °C, inlet 34.1 °C · "
        "raises from 37.8 °C, lowers from 34 °C"
    )

    hass.states.async_set(
        "sensor.lg_therma_v_r290_temperature_before_evaporator", "0.6"
    )
    assert _card(hass).endswith("frost protection (coil 0.6 °C): lowering")

    hass.states.async_set(
        "select.lg_therma_v_r290_control_method", "Outlet Water Temp Control"
    )
    assert _card(hass).endswith(
        "AutoTemp: cold start<br> setpoint 35 °C, outlet 36.0 °C, inlet 34.1 °C · "
        "inlet control from 22 °C"
    )

    hass.states.async_set("binary_sensor.lg_therma_v_r290_compressor", "off")
    assert _card(hass).endswith("AutoTemp: waiting for the compressor")

    hass.states.async_set(SETPOINT, "20")
    assert _card(hass).endswith("AutoTemp: off (setpoint 20 °C)")

    hass.states.async_set(AUTOTEMP, "off")
    assert _card(hass).endswith("AutoTemp: disabled")

    hass.states.async_set(AUTOTEMP, "on")
    hass.states.async_set(SETPOINT, "35")
    freezer.move_to("2026-11-16 16:30:00+00:00")  # 17:30 in Berlin
    assert _card(hass).endswith("AutoTemp: done for today (after 17:00)")


def _timeline(hass) -> str:
    return Template(STATUS_TEMPLATE.read_text(), hass).async_render()


async def test_the_timeline_template(hass, freezer) -> None:
    """The template sensor's states, in the order of AutoTemp's conditions."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-11-16 09:00:00+00:00")  # 10:00 in Berlin
    for entity_id, state in {
        AUTOTEMP: "on",
        SETPOINT: "35",
        "sensor.lg_therma_v_r290_temperature_before_evaporator": "4.2",
        "binary_sensor.lg_therma_v_r290_defrost": "off",
        "binary_sensor.lg_therma_v_r290_compressor": "on",
        "select.lg_therma_v_r290_control_method": "Inlet Water Temp Control",
    }.items():
        hass.states.async_set(entity_id, state)
    assert _timeline(hass) == "paused (defrost)"  # the defrost ended just now

    freezer.tick(timedelta(minutes=6))
    assert _timeline(hass) == "active"
    hass.states.async_set(
        "sensor.lg_therma_v_r290_temperature_before_evaporator", "0.6"
    )
    assert _timeline(hass) == "frost protection"
    hass.states.async_set(
        "select.lg_therma_v_r290_control_method", "Outlet Water Temp Control"
    )
    assert _timeline(hass) == "cold start"
    hass.states.async_set("binary_sensor.lg_therma_v_r290_compressor", "off")
    assert _timeline(hass) == "waiting for the compressor"
    hass.states.async_set(SETPOINT, "20")
    assert _timeline(hass) == "off"
    hass.states.async_set(AUTOTEMP, "off")
    assert _timeline(hass) == "disabled"
    hass.states.async_set(AUTOTEMP, "on")
    hass.states.async_set(SETPOINT, "35")
    freezer.move_to("2026-11-16 16:30:00+00:00")  # 17:30 in Berlin
    assert _timeline(hass) == "done for today"
