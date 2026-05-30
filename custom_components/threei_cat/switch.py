"""Switch platform for 3i Cat Litter Box."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    PROPERTY_AUTO_CLEAN,
    PROPERTY_CHILD_LOCK,
    PROPERTY_DEVICE_LIGHT,
    PROPERTY_AUTO_POWER_OFF,
)
from .coordinator import ThreeiDataUpdateCoordinator


SWITCH_CONFIGS: list[tuple[str, str, str]] = [
    (PROPERTY_AUTO_CLEAN, "Auto Clean", "mdi:robot-vacuum"),
    (PROPERTY_CHILD_LOCK, "Child Lock", "mdi:lock"),
    (PROPERTY_DEVICE_LIGHT, "Device Light", "mdi:lightbulb"),
    (PROPERTY_AUTO_POWER_OFF, "Auto Power Off", "mdi:power"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 3i switches from a config entry."""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ThreeiSwitchEntity(coordinator, key, name, icon)
        for key, name, icon in SWITCH_CONFIGS
    )


class ThreeiSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Representation of a 3i switch."""

    coordinator: ThreeiDataUpdateCoordinator

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        value = self.coordinator.device_data.get(self._key)
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            return value.lower() in ("true", "1", "on", "yes")
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(
            self.coordinator.set_property, self._key, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(
            self.coordinator.set_property, self._key, False
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.config_entry.entry_id)},
            "name": "3i Cat Litter Box",
            "manufacturer": "3irobotix",
            "model": "Smart Cat Litter Box",
        }
