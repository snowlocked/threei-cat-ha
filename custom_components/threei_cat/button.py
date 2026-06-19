"""Button platform for 3i Smart Device (猫砂盆按钮)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ThreeiDataUpdateCoordinator, ThreeiDeviceData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置 3i 按钮实体。"""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ButtonEntity] = []
    for device_id in coordinator.devices:
        entities.extend([
            ThreeiStartCleanButton(coordinator, device_id),
            ThreeiStopCleanButton(coordinator, device_id),
            ThreeiReturnToDockButton(coordinator, device_id),
            ThreeiRefreshDataButton(coordinator, device_id),
            ThreeiCheckUpgradeButton(coordinator, device_id),
        ])

    async_add_entities(entities)


class ThreeiBaseButton(CoordinatorEntity, ButtonEntity):
    """3i 按钮基类。"""

    _attr_has_entity_name = True
    coordinator: ThreeiDataUpdateCoordinator

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        device_id: str,
        key: str,
        name: str,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = str(device_id)
        self._key = key
        self._attr_name = name
        if icon:
            self._attr_icon = icon
        self._attr_unique_id = f"{self._device_id}_button_{key}"

    def _get_device(self) -> ThreeiDeviceData | None:
        return self.coordinator.get_device(self._device_id)

    @property
    def device_info(self) -> dict[str, Any]:
        dev = self._get_device()
        if dev:
            return {
                "identifiers": {(DOMAIN, self._device_id)},
                "name": dev.name,
                "manufacturer": MANUFACTURER,
                "model": dev.product_mode_code or "3i Device",
                "sw_version": dev.firmware_version,
                "hw_version": dev.mcu_version,
                "serial_number": dev.sn,
            }
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": "3i Device",
            "manufacturer": MANUFACTURER,
            "model": "3i Device",
        }

    @property
    def available(self) -> bool:
        dev = self._get_device()
        return dev is not None and dev.is_available


class ThreeiStartCleanButton(ThreeiBaseButton):
    """开始清洁按钮。"""

    _attr_icon = "mdi:play"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "start_clean", "Start Clean", "mdi:play")

    async def async_press(self) -> None:
        """按下按钮：开始清洁。"""
        _LOGGER.info("Start clean for device %s", self._device_id)
        await self.coordinator.async_control_device(
            self._device_id,
            {"workMode": 1, "cleanStatus": 1},
        )


class ThreeiStopCleanButton(ThreeiBaseButton):
    """停止清洁按钮。"""

    _attr_icon = "mdi:stop"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "stop_clean", "Stop Clean", "mdi:stop")

    async def async_press(self) -> None:
        await self.coordinator.async_control_device(
            self._device_id,
            {"cleanStatus": 0},
        )


class ThreeiReturnToDockButton(ThreeiBaseButton):
    """返回充电桩按钮。"""

    _attr_icon = "mdi:home"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "return_to_dock", "Return to Dock", "mdi:home")

    async def async_press(self) -> None:
        await self.coordinator.async_control_device(
            self._device_id,
            {"workMode": 3, "cleanStatus": 5},
        )


class ThreeiRefreshDataButton(ThreeiBaseButton):
    """立即刷新数据按钮。"""

    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "refresh", "Refresh Data", "mdi:refresh")

    async def async_press(self) -> None:
        """立即刷新数据。"""
        _LOGGER.info("Manual refresh for device %s", self._device_id)
        await self.coordinator.async_request_refresh()


class ThreeiCheckUpgradeButton(ThreeiBaseButton):
    """检查固件升级按钮。"""

    _attr_icon = "mdi:update"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "check_upgrade", "Check Firmware Update", "mdi:update")

    async def async_press(self) -> None:
        """检查固件升级。"""
        if not self.coordinator.api_client:
            return
        try:
            await self.coordinator.api_client.check_upgrade(self._device_id)
            _LOGGER.info("Checked upgrade for device %s", self._device_id)
        except Exception:
            _LOGGER.exception("Check upgrade failed")
