"""Binary sensor platform for 3i Smart Device."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ThreeiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 3i binary sensor entities."""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ThreeiChargingSensor(coordinator),
            ThreeiBinFullSensor(coordinator),
        ]
    )


class ThreeiBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for 3i binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        key: str,
        name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_info = coordinator.device_info


class ThreeiChargingSensor(ThreeiBaseBinarySensor):
    """Charging status binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "charging", "Charging")

    @property
    def is_on(self) -> bool | None:
        """Return true if charging."""
        val = self.coordinator.device_state.get("charging")
        if val is not None:
            return bool(val)
        return None


class ThreeiBinFullSensor(ThreeiBaseBinarySensor):
    """Bin full warning binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "bin_full", "Bin Full")

    @property
    def is_on(self) -> bool | None:
        """Return true if bin is full."""
        val = self.coordinator.device_state.get(
            "bin_full"
        ) or self.coordinator.device_state.get("binFull")
        if val is not None:
            return bool(val)
        return None
