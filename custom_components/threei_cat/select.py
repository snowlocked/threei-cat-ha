"""Select platform for 3i Smart Device (猫砂盆选择器)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEODORIZE_LEVELS, DOMAIN, MANUFACTURER, WORK_MODES
from .coordinator import ThreeiDataUpdateCoordinator, ThreeiDeviceData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置 3i 选择实体。"""
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SelectEntity] = []
    for device_id in coordinator.devices:
        entities.extend([
            ThreeiWorkModeSelect(coordinator, device_id),
            ThreeiDeodorizeLevelSelect(coordinator, device_id),
        ])

    async_add_entities(entities)


class ThreeiBaseSelect(CoordinatorEntity, SelectEntity):
    """3i 选择器基类。"""

    _attr_has_entity_name = True
    coordinator: ThreeiDataUpdateCoordinator

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        device_id: str,
        key: str,
        name: str,
        options_map: dict[int, str],
    ) -> None:
        super().__init__(coordinator)
        self._device_id = str(device_id)
        self._key = key
        self._options_map = options_map
        self._reverse_map = {v: k for k, v in options_map.items()}
        self._attr_name = name
        self._attr_unique_id = f"{self._device_id}_select_{key}"
        self._attr_options = list(options_map.values())

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
    def current_option(self) -> str | None:
        dev = self._get_device()
        if not dev:
            return None
        # 检查属性值
        val = dev.properties.get(self._key)
        if val is None:
            # 兜底：尝试专门的方法
            val = self._read_dev_value(dev)
        if val is None:
            return None
        try:
            val_int = int(val)
        except (ValueError, TypeError):
            return None
        return self._options_map.get(val_int, f"Unknown ({val_int})")

    def _read_dev_value(self, dev: ThreeiDeviceData) -> Any:
        """子类可重写以从专门的属性获取值。"""
        return None

    async def async_select_option(self, option: str) -> None:
        """选择选项。"""
        val = self._reverse_map.get(option)
        if val is None:
            return
        _LOGGER.info(
            "Set %s=%s for device %s",
            self._key, val, self._device_id,
        )
        await self.coordinator.async_control_device(
            self._device_id, {self._key: val}
        )


class ThreeiWorkModeSelect(ThreeiBaseSelect):
    """工作模式选择器。"""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "workMode", "Work Mode", WORK_MODES)

    def _read_dev_value(self, dev: ThreeiDeviceData) -> Any:
        return dev.work_mode


class ThreeiDeodorizeLevelSelect(ThreeiBaseSelect):
    """除臭档位选择器。"""

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "deodorizeLevel", "Deodorize Level", DEODORIZE_LEVELS)

    def _read_dev_value(self, dev: ThreeiDeviceData) -> Any:
        return dev.deodorize_level
