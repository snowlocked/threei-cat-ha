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
    PROP_AUTO_CLEAN,
    PROP_CHILD_LOCK,
    PROP_DEVICE_LIGHT,
)
from .coordinator import ThreeiDataUpdateCoordinator


SWITCH_CONFIGS: list[tuple[str, str, str]] = [
    (PROP_AUTO_CLEAN, "Auto Clean", "mdi:robot-vacuum"),
    (PROP_CHILD_LOCK, "Child Lock", "mdi:lock"),
    (PROP_DEVICE_LIGHT, "Device Light", "mdi:lightbulb"),
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
        value = self.coordinator.device_state.get(self._key)
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
        self.coordinator._client.publish_property_set({self._key: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.coordinator._client.publish_property_set({self._key: False})

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self.coordinator.device_info
