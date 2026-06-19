"""Binary sensor platform for 3i Smart Device (猫砂盆二进制传感器)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """设置 3i 二进制传感器。"""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = []
    for device_id in coordinator.devices:
        entities.extend([
            ThreeiOnlineSensor(coordinator, device_id),
            ThreeiChargingSensor(coordinator, device_id),
            ThreeiBinFullSensor(coordinator, device_id),
            ThreeiWaterLowSensor(coordinator, device_id),
            ThreeiErrorSensor(coordinator, device_id),
        ])

    async_add_entities(entities)


class ThreeiBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """3i 二进制传感器基类。"""

    _attr_has_entity_name = True
    coordinator: ThreeiDataUpdateCoordinator

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        device_id: str,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = str(device_id)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{self._device_id}_{key}"
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> dict[str, Any]:
        dev = self.coordinator.get_device(self._device_id)
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

    def _get_device(self) -> ThreeiDeviceData | None:
        return self.coordinator.get_device(self._device_id)

    @property
    def available(self) -> bool:
        dev = self._get_device()
        return dev is not None


class ThreeiOnlineSensor(ThreeiBaseBinarySensor):
    """在线状态传感器。"""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "online", "Online")

    @property
    def is_on(self) -> bool | None:
        dev = self._get_device()
        return dev.online if dev else None


class ThreeiChargingSensor(ThreeiBaseBinarySensor):
    """充电状态传感器。"""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "charging", "Charging")

    @property
    def is_on(self) -> bool | None:
        dev = self._get_device()
        return dev.charging if dev else None


class ThreeiBinFullSensor(ThreeiBaseBinarySensor):
    """集便箱满警告。"""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:delete-alert"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "bin_full", "Bin Full")

    @property
    def is_on(self) -> bool | None:
        dev = self._get_device()
        return dev.bin_full if dev else None


class ThreeiWaterLowSensor(ThreeiBaseBinarySensor):
    """水量不足警告。"""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:water-alert"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "water_low", "Water Low")

    @property
    def is_on(self) -> bool | None:
        dev = self._get_device()
        return dev.water_low if dev else None


class ThreeiErrorSensor(ThreeiBaseBinarySensor):
    """错误状态传感器。"""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "error", "Error")

    @property
    def is_on(self) -> bool | None:
        dev = self._get_device()
        if not dev:
            return None
        # 如果有错误码，认为出错
        return dev.error_code is not None and dev.error_code not in ("", "0", 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dev = self._get_device()
        return {"error_code": dev.error_code if dev else None}
