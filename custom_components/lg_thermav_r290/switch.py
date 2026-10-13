"""Switch platform for LG ThermaV R290 — state coil registers.

Only coils that hold a state belong here. The momentary trigger coils
("0: hold status / 1: start operation") are buttons instead — see button.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_POWER_LIMIT, DOMAIN
from .coordinator import LGThermaVCoordinator
from .power_limit import (
    DATA_KEY_ACTIVE,
    DATA_KEY_RAW,
    POWER_LIMIT_COIL,
    SWITCH_UNIQUE_ID_SUFFIX,
)


@dataclass(frozen=True, kw_only=True)
class LGSwitchDescription(SwitchEntityDescription):
    data_key: str = ""
    coil_address: int = 0


_SWITCHES: tuple[LGSwitchDescription, ...] = (
    LGSwitchDescription(
        key="hauptschalter",
        data_key="coil_hauptschalter",
        coil_address=0,
        name="Heat Pump",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:heat-pump",
    ),
    LGSwitchDescription(
        key="dhw",
        data_key="coil_dhw",
        coil_address=1,
        name="DHW",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:water-boiler",
    ),
    LGSwitchDescription(
        key="silent_mode",
        data_key="coil_silent_mode",
        coil_address=2,
        name="Silent Mode",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:volume-off",
    ),
    LGSwitchDescription(
        key="emergency_stop",
        data_key="coil_emergency_stop",
        coil_address=4,
        name="Emergency Stop",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:stop-circle",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: LGThermaVCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = [
        LGSwitch(coordinator, entry, desc) for desc in _SWITCHES
    ]
    if entry.options.get(CONF_POWER_LIMIT, False):
        entities.append(LGPowerLimitSwitch(coordinator, entry))
    else:
        registry = er.async_get(hass)
        entity_id = registry.async_get_entity_id(
            "switch", DOMAIN, f"{entry.entry_id}_{SWITCH_UNIQUE_ID_SUFFIX}"
        )
        if entity_id is not None:
            registry.async_remove(entity_id)
    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="LG ThermaV R290",
        manufacturer="LG",
        model="ThermaV R290",
    )


class LGSwitch(CoordinatorEntity[LGThermaVCoordinator], SwitchEntity):
    """A switch that controls a Modbus coil register."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LGThermaVCoordinator,
        entry: ConfigEntry,
        description: LGSwitchDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._data_key = description.data_key
        self._coil_address = description.coil_address
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._data_key)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_coil(self._coil_address, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_coil(self._coil_address, False)
        await self.coordinator.async_request_refresh()


class LGPowerLimitSwitch(CoordinatorEntity[LGThermaVCoordinator], SwitchEntity):
    """Switches the active power limitation, coil 6. UNVERIFIED (power_limit.py).

    Only created when the power limit option is on; the coordinator accepts a
    write to coil 6 only then. The state comes from reading the coil back
    after every write, not from what was sent.
    """

    _attr_has_entity_name = True
    _attr_name = "Power Limitation"
    _attr_icon = "mdi:flash-alert"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator: LGThermaVCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{SWITCH_UNIQUE_ID_SUFFIX}"
        self._attr_device_info = _device_info(entry)

    @property
    def available(self) -> bool:
        # Both reads of the pair succeeded in the current data.
        return (
            super().available
            and self.coordinator.data is not None
            and DATA_KEY_RAW in self.coordinator.data
        )

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(DATA_KEY_ACTIVE)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_coil(POWER_LIMIT_COIL, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_coil(POWER_LIMIT_COIL, False)
        await self.coordinator.async_request_refresh()
