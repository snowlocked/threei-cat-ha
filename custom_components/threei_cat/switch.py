"""Switch platform for 3i Smart Device (猫砂盆开关)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """设置 3i 开关实体。"""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []
    for device_id in coordinator.devices:
        entities.extend([
            ThreeiSwitchEntity(coordinator, device_id, "autoClean", "Auto Clean", "mdi:robot-vacuum"),
            ThreeiSwitchEntity(coordinator, device_id, "childLock", "Child Lock", "mdi:lock"),
            ThreeiSwitchEntity(coordinator, device_id, "deviceLight", "Device Light", "mdi:lightbulb"),
            ThreeiSwitchEntity(coordinator, device_id, "powerSaving", "Power Saving", "mdi:leaf"),
            ThreeiSwitchEntity(coordinator, device_id, "deodorize", "Deodorize", "mdi:spray"),
        ])

    async_add_entities(entities)


class ThreeiSwitchEntity(CoordinatorEntity, SwitchEntity):
    """3i 开关实体。"""

    _attr_has_entity_name = True
    coordinator: ThreeiDataUpdateCoordinator

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        device_id: str,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = str(device_id)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._device_id}_switch_{key}"

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

    @property
    def is_on(self) -> bool | None:
        dev = self._get_device()
        if not dev:
            return None
        v = dev.properties.get(self._key)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v > 0
        if isinstance(v, str):
            return v.lower() in ("true", "1", "on", "yes")
        return bool(v)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """打开开关 - 通过 HTTP API 控制。

        由于设备 iotId 通常为 null，实际控制命令可能无法到达设备。
        这只是占位实现，控制状态会在下次轮询时被云端状态覆盖。
        """
        _LOGGER.info(
            "Turn on %s for device %s (may not work if device not cloud-authorized)",
            self._key, self._device_id,
        )
        await self.coordinator.async_control_device(
            self._device_id, {self._key: True}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关闭开关。"""
        _LOGGER.info(
            "Turn off %s for device %s",
            self._key, self._device_id,
        )
        await self.coordinator.async_control_device(
            self._device_id, {self._key: False}
        )
