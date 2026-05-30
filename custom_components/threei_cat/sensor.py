"""Sensor platform for 3i Smart Device."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CLEAN_STATUS,
    DOMAIN,
    WORK_MODES,
)
from .coordinator import ThreeiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up 3i sensor entities."""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ThreeiBatterySensor(coordinator),
            ThreeiCleanStatusSensor(coordinator),
            ThreeiWorkModeSensor(coordinator),
            ThreeiFirmwareSensor(coordinator),
            ThreeiMcuVersionSensor(coordinator),
        ]
    )


class ThreeiBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for 3i sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        key: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        return self.coordinator.device_state.get(self._key)


class ThreeiBatterySensor(ThreeiBaseSensor):
    """Battery level sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "battery", "Battery")


class ThreeiCleanStatusSensor(ThreeiBaseSensor):
    """Clean status sensor."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "clean_status", "Clean Status")

    @property
    def native_value(self) -> str | None:
        """Return clean status as text."""
        val = self.coordinator.device_state.get(self._key)
        if val is not None:
            return CLEAN_STATUS.get(val, f"Unknown ({val})")
        return None


class ThreeiWorkModeSensor(ThreeiBaseSensor):
    """Work mode sensor."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "work_mode", "Work Mode")

    @property
    def native_value(self) -> str | None:
        """Return work mode as text."""
        val = self.coordinator.device_state.get(self._key)
        if val is not None:
            return WORK_MODES.get(val, f"Unknown ({val})")
        return None


class ThreeiFirmwareSensor(ThreeiBaseSensor):
    """Firmware version sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "firmwareCode", "Firmware Version")


class ThreeiMcuVersionSensor(ThreeiBaseSensor):
    """MCU version sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "mcu_version_code", "MCU Version")
