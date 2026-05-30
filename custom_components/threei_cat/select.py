"""Select platform for 3i Smart Device."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SUCTION_LEVELS,
    WATER_LEVELS,
    WORK_MODES,
)
from .coordinator import ThreeiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 3i select entities."""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ThreeiWorkModeSelect(coordinator),
            ThreeiWaterLevelSelect(coordinator),
            ThreeiSuctionLevelSelect(coordinator),
        ]
    )


class ThreeiBaseSelect(CoordinatorEntity, SelectEntity):
    """Base class for 3i selects."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        key: str,
        name: str,
        options_map: dict,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self._key = key
        self._options_map = options_map
        self._reverse_map = {v: k for k, v in options_map.items()}
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_info = coordinator.device_info
        self._attr_options = list(options_map.values())

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        val = self.coordinator.device_state.get(self._key)
        if val is not None:
            return self._options_map.get(val, f"Unknown ({val})")
        return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        val = self._reverse_map.get(option)
        if val is not None:
            self._set_value(val)


class ThreeiWorkModeSelect(ThreeiBaseSelect):
    """Select entity for work mode."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "work_mode", "Work Mode", WORK_MODES)

    def _set_value(self, val: int) -> None:
        """Set the work mode."""
        self.coordinator.set_work_mode(val)


class ThreeiWaterLevelSelect(ThreeiBaseSelect):
    """Select entity for water level."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "water_level", "Water Level", WATER_LEVELS)

    def _set_value(self, val: int) -> None:
        """Set the water level."""
        self.coordinator.set_water_level(val)


class ThreeiSuctionLevelSelect(ThreeiBaseSelect):
    """Select entity for suction level."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "suction_level", "Suction Level", SUCTION_LEVELS)

    def _set_value(self, val: int) -> None:
        """Set the suction level."""
        self.coordinator.set_suction_level(val)
