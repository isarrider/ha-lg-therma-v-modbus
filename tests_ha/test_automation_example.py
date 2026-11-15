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
from pytest_homeassistant_custom_component.common import MockConfigEntry
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


def test_automations_md_links_every_file() -> None:
    text = AUTOMATIONS.read_text()
    missing = [f.name for f in [*FILES, STATUS_CARD] if f"]({f.name})" not in text]
    assert missing == []


def _configs() -> list[dict]:
    return [yaml.safe_load(f.read_text()) for f in FILES]


def _texts() -> str:
    files = [*FILES, STATUS_CARD]
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
STATUS = "input_text.autotemp_status"


async def _set_up_with_automations(hass, *, helper: bool) -> None:
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
    if helper:
        assert await async_setup_component(
            hass,
            "input_text",
            {
                "input_text": {
                    "autotemp_status": {"name": "AutoTemp status", "max": 255}
                }
            },
        )
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
async def test_autotemp_describes_what_it_does(hass, unit) -> None:
    _raise_situation(unit)
    await _set_up_with_automations(hass, helper=True)

    await hass.services.async_call(
        "automation", "trigger", {"entity_id": AUTOTEMP}, blocking=True
    )
    await hass.async_block_till_done()
    assert ("holding", 2, 310) in unit.writes
    assert (
        hass.states.get(STATUS).state
        == "Raised to 31 °C: inlet 34.0 °C, 4.0 K above (emergency)"
    )

    await hass.services.async_call(
        "automation",
        "trigger",
        {"entity_id": "automation.therma_v_stop"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(STATUS).state.startswith("Stop: 20 °C")


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_autotemp_works_without_the_helper(hass, unit) -> None:
    _raise_situation(unit)
    await _set_up_with_automations(hass, helper=False)

    await hass.services.async_call(
        "automation", "trigger", {"entity_id": AUTOTEMP}, blocking=True
    )
    await hass.async_block_till_done()
    assert ("holding", 2, 310) in unit.writes
    assert hass.states.get(AUTOTEMP).state == "on"


def _card(hass) -> str:
    content = yaml.safe_load(STATUS_CARD.read_text())["content"]
    return " ".join(Template(content, hass).async_render().split())


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_the_status_card(hass, unit, freezer) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-11-16 09:00:00+00:00")  # 10:00 in Berlin
    _raise_situation(unit)
    await _set_up_with_automations(hass, helper=True)

    # The defrost sensor changed state just now (setup): 5 minutes of pause.
    assert "AutoTemp: paused (defrost)" in _card(hass)

    freezer.tick(timedelta(minutes=6))
    await hass.services.async_call(
        "automation", "trigger", {"entity_id": AUTOTEMP}, blocking=True
    )
    await hass.async_block_till_done()
    card = _card(hass)
    assert "AutoTemp: active" in card
    assert "Raised to 31 °C: inlet 34.0 °C, 4.0 K above (emergency) ·" in card

    entity = "number.lg_therma_v_r290_target_temperature_circuit_1_radiators"
    hass.states.async_set(entity, "20")
    assert "AutoTemp: off (setpoint 20 °C)" in _card(hass)

    hass.states.async_set(entity, "31")
    hass.states.async_set("binary_sensor.lg_therma_v_r290_compressor", "off")
    assert "AutoTemp: waiting for the compressor" in _card(hass)

    hass.states.async_set(AUTOTEMP, "off")
    assert "AutoTemp: disabled" in _card(hass)

    freezer.move_to("2026-11-16 16:30:00+00:00")  # 17:30 in Berlin
    hass.states.async_set(AUTOTEMP, "on")
    assert "AutoTemp: done for today" in _card(hass)
