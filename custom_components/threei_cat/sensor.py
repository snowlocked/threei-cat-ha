"""Sensor platform for 3i Smart Device (猫砂盆传感器平台)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

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
    CLEAN_RECORD_AREA,
    CLEAN_RECORD_DURATION,
    CLEAN_RECORD_FINISH_TIME,
    CLEAN_RECORD_START_TIME,
    CLEAN_RECORD_STATUS,
    CLEAN_STATUS,
    CONSUMABLE_NAMES,
    CONSUMABLE_NAMES_CN,
    DEFAULT_CONSUMABLE_LIFESPANS,
    DEODORIZE_LEVELS,
    DOMAIN,
    EVENT_IDENTIFIER_WATER_MAKE,
    MANUFACTURER,
    PROP_BATTERY,
    WORK_MODES,
)
from .coordinator import ThreeiDataUpdateCoordinator, ThreeiDeviceData

_LOGGER = logging.getLogger(__name__)


# ========================================================================
# Setup
# ========================================================================

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置 3i 传感器实体。

    根据 coordinator.devices 中实际发现的设备动态添加实体。
    """
    coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    for device_id, dev_data in coordinator.devices.items():
        # 基础状态传感器
        entities.extend([
            ThreeiBatterySensor(coordinator, device_id),
            ThreeiWorkModeSensor(coordinator, device_id),
            ThreeiCleanStatusSensor(coordinator, device_id),
            ThreeiDeodorizeLevelSensor(coordinator, device_id),
            ThreeiFirmwareSensor(coordinator, device_id),
            ThreeiMcuVersionSensor(coordinator, device_id),
            ThreeiCatWeightSensor(coordinator, device_id),
            # 清洁记录相关
            ThreeiLastCleanAreaSensor(coordinator, device_id),
            ThreeiLastCleanDurationSensor(coordinator, device_id),
            ThreeiLastCleanTimeSensor(coordinator, device_id),
            ThreeiTotalCleanCountSensor(coordinator, device_id),
            # 制水记录
            ThreeiLastWaterMakeTimeSensor(coordinator, device_id),
            ThreeiLastWaterMakeVolumeSensor(coordinator, device_id),
        ])

        # 耗材寿命传感器（动态）
        for consumable in dev_data.consumables or []:
            ctype = consumable.get("consumableType") or consumable.get("type")
            if ctype:
                entities.append(
                    ThreeiConsumableLifeSensor(coordinator, device_id, ctype)
                )

    async_add_entities(entities)


# ========================================================================
# 基础类
# ========================================================================

class ThreeiBaseSensor(CoordinatorEntity, SensorEntity):
    """3i 传感器基类。"""

    _attr_has_entity_name = True
    coordinator: ThreeiDataUpdateCoordinator

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        device_id: str,
        key: str,
        name: str,
    ) -> None:
        """初始化。"""
        super().__init__(coordinator)
        self._device_id = str(device_id)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{self._device_id}_{key}"
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> dict[str, Any]:
        """构建 device_info。"""
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
        return dev is not None and dev.is_available


# ========================================================================
# 电池
# ========================================================================

class ThreeiBatterySensor(ThreeiBaseSensor):
    """电池电量传感器。"""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "battery", "Battery")

    @property
    def native_value(self) -> int | None:
        dev = self._get_device()
        return dev.battery if dev else None


# ========================================================================
# 工作模式
# ========================================================================

class ThreeiWorkModeSensor(ThreeiBaseSensor):
    """工作模式传感器。"""

    _attr_icon = "mdi:robot-vacuum"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "work_mode", "Work Mode")

    @property
    def native_value(self) -> str | None:
        dev = self._get_device()
        if dev and dev.work_mode is not None:
            return WORK_MODES.get(dev.work_mode, f"Unknown ({dev.work_mode})")
        return None


# ========================================================================
# 清洁状态
# ========================================================================

class ThreeiCleanStatusSensor(ThreeiBaseSensor):
    """清洁状态传感器。"""

    _attr_icon = "mdi:broom"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "clean_status", "Clean Status")

    @property
    def native_value(self) -> str | None:
        dev = self._get_device()
        if dev and dev.clean_status is not None:
            return CLEAN_STATUS.get(dev.clean_status, f"Unknown ({dev.clean_status})")
        return None


# ========================================================================
# 除臭档位
# ========================================================================

class ThreeiDeodorizeLevelSensor(ThreeiBaseSensor):
    """除臭档位传感器。"""

    _attr_icon = "mdi:spray"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "deodorize_level", "Deodorize Level")

    @property
    def native_value(self) -> str | None:
        dev = self._get_device()
        if dev and dev.deodorize_level is not None:
            return DEODORIZE_LEVELS.get(dev.deodorize_level, f"Unknown ({dev.deodorize_level})")
        return None


# ========================================================================
# 固件 / MCU 版本
# ========================================================================

class ThreeiFirmwareSensor(ThreeiBaseSensor):
    """固件版本传感器。"""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "firmware", "Firmware Version")

    @property
    def native_value(self) -> str | None:
        dev = self._get_device()
        return dev.firmware_version if dev else None


class ThreeiMcuVersionSensor(ThreeiBaseSensor):
    """MCU 版本传感器。"""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cpu-64-bit"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "mcu_version", "MCU Version")

    @property
    def native_value(self) -> str | None:
        dev = self._get_device()
        return dev.mcu_version if dev else None


# ========================================================================
# 猫体重
# ========================================================================

class ThreeiCatWeightSensor(ThreeiBaseSensor):
    """猫体重传感器（克）。"""

    _attr_icon = "mdi:cat"
    _attr_native_unit_of_measurement = "g"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "cat_weight", "Cat Weight")

    @property
    def native_value(self) -> float | None:
        dev = self._get_device()
        if dev and dev.cat_weight is not None:
            try:
                return round(float(dev.cat_weight), 1)
            except (ValueError, TypeError):
                return None
        return None


# ========================================================================
# 清洁记录传感器
# ========================================================================

def _parse_timestamp(value: Any) -> datetime | None:
    """解析时间戳字段（支持 ms/int/ISO string）。"""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1e12:  # 毫秒
                ts = ts / 1000
            return datetime.fromtimestamp(ts)
        if isinstance(value, str):
            s = value.replace("Z", "+00:00")
            # 纯数字字符串
            if s.isdigit():
                ts = int(s)
                if ts > 1e12:
                    ts = ts / 1000
                return datetime.fromtimestamp(ts)
            return datetime.fromisoformat(s)
    except (ValueError, TypeError, OSError):
        pass
    return None


def _get_last_clean_record(dev: ThreeiDeviceData) -> dict[str, Any] | None:
    """获取最后一次清洁记录。"""
    if not dev.clean_records:
        return None
    first = dev.clean_records[0]
    return first if isinstance(first, dict) else None


class ThreeiLastCleanAreaSensor(ThreeiBaseSensor):
    """最后清洁面积（m²）。"""

    _attr_icon = "mdi:floor-plan"
    _attr_native_unit_of_measurement = "m²"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "last_clean_area", "Last Clean Area")

    @property
    def native_value(self) -> float | None:
        dev = self._get_device()
        if not dev:
            return None
        rec = _get_last_clean_record(dev)
        if rec:
            area = rec.get(CLEAN_RECORD_AREA) or rec.get("area")
            if area is not None:
                try:
                    return round(float(area), 2)
                except (ValueError, TypeError):
                    pass
        return None


class ThreeiLastCleanDurationSensor(ThreeiBaseSensor):
    """最后清洁时长（秒）。"""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "last_clean_duration", "Last Clean Duration")

    @property
    def native_value(self) -> int | None:
        dev = self._get_device()
        if not dev:
            return None
        rec = _get_last_clean_record(dev)
        if rec:
            duration = rec.get(CLEAN_RECORD_DURATION) or rec.get("duration")
            if duration is not None:
                try:
                    return int(duration)
                except (ValueError, TypeError):
                    pass
        return None


class ThreeiLastCleanTimeSensor(ThreeiBaseSensor):
    """最后清洁时间。"""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "last_clean_time", "Last Clean Time")

    @property
    def native_value(self) -> datetime | None:
        dev = self._get_device()
        if not dev:
            return None
        rec = _get_last_clean_record(dev)
        if rec:
            for k in (CLEAN_RECORD_FINISH_TIME, CLEAN_RECORD_START_TIME, "finishTime", "startTime", "cleanFinish"):
                ts = rec.get(k)
                if ts is not None:
                    parsed = _parse_timestamp(ts)
                    if parsed:
                        return parsed
        return None


class ThreeiTotalCleanCountSensor(ThreeiBaseSensor):
    """总清洁次数。"""

    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "total_clean_count", "Total Clean Count")

    @property
    def native_value(self) -> int:
        dev = self._get_device()
        if not dev or not dev.clean_records:
            return 0
        return len(dev.clean_records)


# ========================================================================
# 制水记录传感器
# ========================================================================

def _get_last_water_record(dev: ThreeiDeviceData) -> dict[str, Any] | None:
    """获取最后一次制水记录。"""
    if not dev.water_records:
        return None
    first = dev.water_records[0]
    return first if isinstance(first, dict) else None


class ThreeiLastWaterMakeTimeSensor(ThreeiBaseSensor):
    """最后制水时间。"""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:water-clock"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "last_water_make_time", "Last Water Make Time")

    @property
    def native_value(self) -> datetime | None:
        dev = self._get_device()
        if not dev:
            return None
        rec = _get_last_water_record(dev)
        if rec:
            for k in ("time", "createTime", "finishTime", "endTime"):
                ts = rec.get(k)
                if ts is not None:
                    parsed = _parse_timestamp(ts)
                    if parsed:
                        return parsed
        return None


class ThreeiLastWaterMakeVolumeSensor(ThreeiBaseSensor):
    """最后制水量 (ml)。"""

    _attr_icon = "mdi:water"
    _attr_native_unit_of_measurement = "ml"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id, "last_water_make_volume", "Last Water Make Volume")

    @property
    def native_value(self) -> float | None:
        dev = self._get_device()
        if not dev:
            return None
        rec = _get_last_water_record(dev)
        if rec:
            for k in ("volume", "waterVolume", "amount", "value"):
                v = rec.get(k)
                if v is not None:
                    try:
                        return round(float(v), 1)
                    except (ValueError, TypeError):
                        pass
        return None


# ========================================================================
# 耗材寿命传感器
# ========================================================================

class ThreeiConsumableLifeSensor(ThreeiBaseSensor):
    """耗材剩余寿命（百分比）。"""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        device_id: str,
        consumable_type: str,
    ) -> None:
        """初始化。"""
        self._consumable_type = consumable_type
        name = CONSUMABLE_NAMES.get(consumable_type, consumable_type)
        super().__init__(
            coordinator,
            device_id,
            f"consumable_{consumable_type}",
            f"{name} Life",
        )

    @property
    def native_value(self) -> int | None:
        dev = self._get_device()
        if not dev or not dev.consumables:
            return None

        item = None
        for entry in dev.consumables:
            if not isinstance(entry, dict):
                continue
            ctype = entry.get("consumableType") or entry.get("type")
            if ctype == self._consumable_type:
                item = entry
                break

        if item is None:
            return None

        # 优先用百分比字段
        for pct_key in ("life", "lifePercent", "percent", "remaining", "percentage"):
            if pct_key in item:
                try:
                    return int(item[pct_key])
                except (ValueError, TypeError):
                    pass

        # 用 used/total 计算
        used = item.get("usedHours") or item.get("usedTime") or item.get("useTime")
        total = item.get("totalHours") or item.get("totalTime") or item.get("lifeTime")
        if used is not None and total is not None:
            try:
                pct = max(0.0, min(100.0, (1 - float(used) / float(total)) * 100))
                return int(pct)
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        # 兜底：用默认寿命
        lifespan = DEFAULT_CONSUMABLE_LIFESPANS.get(self._consumable_type)
        if lifespan and "usedHours" in item:
            try:
                pct = max(0.0, min(100.0, (1 - float(item["usedHours"]) / lifespan) * 100))
                return int(pct)
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """额外属性。"""
        dev = self._get_device()
        if not dev or not dev.consumables:
            return {}

        item = None
        for e in dev.consumables:
            if isinstance(e, dict):
                ctype = e.get("consumableType") or e.get("type")
                if ctype == self._consumable_type:
                    item = e
                    break

        if not item:
            return {}

        return {
            "consumable_type": self._consumable_type,
            "name_cn": CONSUMABLE_NAMES_CN.get(self._consumable_type, ""),
            "raw": {k: v for k, v in item.items()
                    if not isinstance(v, (dict, list))},
        }
