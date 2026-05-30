"""Button platform for 3i Smart Device."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
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
    """Set up 3i button entities."""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ThreeiStartCleanButton(coordinator),
            ThreeiStopCleanButton(coordinator),
            ThreeiReturnToDockButton(coordinator),
            ThreeiStopRechargeButton(coordinator),
        ]
    )


class ThreeiBaseButton(CoordinatorEntity, ButtonEntity):
    """Base class for 3i buttons."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        key: str,
        name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_device_info = coordinator.device_info


class ThreeiStartCleanButton(ThreeiBaseButton):
    """Button to start cleaning."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "start_clean", "Start Clean")

    async def async_press(self) -> None:
        """Handle button press."""
        self.coordinator.start_clean()


class ThreeiStopCleanButton(ThreeiBaseButton):
    """Button to stop cleaning."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "stop_clean", "Stop Clean")

    async def async_press(self) -> None:
        """Handle button press."""
        self.coordinator.stop_clean()


class ThreeiReturnToDockButton(ThreeiBaseButton):
    """Button to return to dock."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "return_to_dock", "Return to Dock")

    async def async_press(self) -> None:
        """Handle button press."""
        self.coordinator.start_recharge()


class ThreeiStopRechargeButton(ThreeiBaseButton):
    """Button to stop recharge/return."""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "stop_recharge", "Stop Recharge")

    async def async_press(self) -> None:
        """Handle button press."""
        self.coordinator.stop_recharge()
