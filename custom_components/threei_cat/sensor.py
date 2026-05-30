"""Sensor platform for 3i Smart Device."""
from __future__ import annotations

from datetime import datetime

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
    CONSUMABLE_FILTER,
    CONSUMABLE_LIFESPANS,
    CONSUMABLE_MAIN_BRUSH,
    CONSUMABLE_MOP,
    CONSUMABLE_NAMES,
    CONSUMABLE_SIDE_BRUSH,
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
    entities = [
        ThreeiBatterySensor(coordinator),
        ThreeiCleanStatusSensor(coordinator),
        ThreeiWorkModeSensor(coordinator),
        ThreeiFirmwareSensor(coordinator),
        ThreeiMcuVersionSensor(coordinator),
        ThreeiLastCleanAreaSensor(coordinator),
        ThreeiLastCleanDurationSensor(coordinator),
        ThreeiLastCleanTimeSensor(coordinator),
        ThreeiLastCleanStatusSensor(coordinator),
    ]

    # Add consumable life sensors for the 4 main consumables
    for consumable_key in [
        CONSUMABLE_SIDE_BRUSH,
        CONSUMABLE_MAIN_BRUSH,
        CONSUMABLE_FILTER,
        CONSUMABLE_MOP,
    ]:
        entities.append(ThreeiConsumableLifeSensor(coordinator, consumable_key))

    async_add_entities(entities)


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


class ThreeiConsumableLifeSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing consumable remaining life as a percentage."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = None
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: ThreeiDataUpdateCoordinator,
        consumable_key: str,
    ) -> None:
        """Initialize the consumable life sensor."""
        super().__init__(coordinator)
        self._consumable_key = consumable_key
        self._attr_name = f"{CONSUMABLE_NAMES.get(consumable_key, consumable_key)} Life"
        self._attr_unique_id = f"{coordinator.device_id}_consumable_{consumable_key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | None:
        """Return the remaining life percentage of the consumable."""
        consumables = self.coordinator.consumables_data
        if not consumables:
            return None

        # Try to find the consumable data by key
        # The API may return data in various formats; try common patterns
        item = None
        if isinstance(consumables, dict):
            # Direct key lookup
            item = consumables.get(self._consumable_key)
            # Or nested in a list
            if item is None and "list" in consumables:
                for entry in consumables["list"]:
                    if isinstance(entry, dict):
                        if entry.get("consumableType") == self._consumable_key:
                            item = entry
                            break
                        if entry.get("type") == self._consumable_key:
                            item = entry
                            break
        elif isinstance(consumables, list):
            for entry in consumables:
                if isinstance(entry, dict):
                    if entry.get("consumableType") == self._consumable_key:
                        item = entry
                        break
                    if entry.get("type") == self._consumable_key:
                        item = entry
                        break

        if item is None:
            return None

        # Try to extract percentage directly
        if isinstance(item, (int, float)):
            return int(item)

        if isinstance(item, dict):
            # Direct percentage field
            for pct_key in ("life", "lifePercent", "percent", "remaining", "percentage"):
                if pct_key in item:
                    return int(item[pct_key])

            # Calculate from used/total hours
            used_hours = item.get("usedHours") or item.get("usedTime") or item.get("useTime")
            total_hours = item.get("totalHours") or item.get("totalTime") or item.get("lifeTime")
            if used_hours is not None and total_hours is not None:
                try:
                    remaining = max(0, (1 - float(used_hours) / float(total_hours)) * 100)
                    return int(remaining)
                except (ValueError, ZeroDivisionError):
                    pass

            # Fallback: use defaults
            lifespan = CONSUMABLE_LIFESPANS.get(self._consumable_key)
            if lifespan and "usedHours" in item:
                try:
                    remaining = max(0, (1 - float(item["usedHours"]) / lifespan) * 100)
                    return int(remaining)
                except (ValueError, ZeroDivisionError):
                    pass

        return None


class ThreeiLastCleanAreaSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the last clean area in square meters."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "m\u00b2"
    _attr_icon = "mdi:floor-plan"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = "Last Clean Area"
        self._attr_unique_id = f"{coordinator.device_id}_last_clean_area"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the last clean area."""
        records = self.coordinator.clean_records
        if not records:
            return None
        last = records[0] if isinstance(records, list) and records else None
        if not last or not isinstance(last, dict):
            return None
        area = last.get("area")
        if area is not None:
            try:
                return float(area)
            except (ValueError, TypeError):
                pass
        return None


class ThreeiLastCleanDurationSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the last clean duration in minutes."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "min"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = "Last Clean Duration"
        self._attr_unique_id = f"{coordinator.device_id}_last_clean_duration"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int | None:
        """Return the last clean duration in minutes."""
        records = self.coordinator.clean_records
        if not records:
            return None
        last = records[0] if isinstance(records, list) and records else None
        if not last or not isinstance(last, dict):
            return None
        duration = last.get("duration")
        if duration is not None:
            try:
                # Duration may be in seconds; convert to minutes
                val = int(duration)
                if val > 300:  # likely seconds
                    return val // 60
                return val  # already minutes
            except (ValueError, TypeError):
                pass
        return None


class ThreeiLastCleanTimeSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing when the last clean occurred."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = "Last Clean Time"
        self._attr_unique_id = f"{coordinator.device_id}_last_clean_time"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the last clean."""
        records = self.coordinator.clean_records
        if not records:
            return None
        last = records[0] if isinstance(records, list) and records else None
        if not last or not isinstance(last, dict):
            return None
        # Try common timestamp fields
        for ts_key in ("cleanFinish", "finishTime", "endTime", "createTime", "timestamp"):
            ts = last.get(ts_key)
            if ts is not None:
                try:
                    if isinstance(ts, (int, float)):
                        if ts > 1e12:  # milliseconds
                            ts = ts / 1000
                        return datetime.fromtimestamp(ts)
                    if isinstance(ts, str):
                        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, TypeError, OSError):
                    continue
        return None


class ThreeiLastCleanStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the last clean result status."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator: ThreeiDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_name = "Last Clean Result"
        self._attr_unique_id = f"{coordinator.device_id}_last_clean_result"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str | None:
        """Return the last clean result."""
        records = self.coordinator.clean_records
        if not records:
            return None
        last = records[0] if isinstance(records, list) and records else None
        if not last or not isinstance(last, dict):
            return None
        if last.get("errorFinish"):
            return "Error"
        if last.get("manualFinish"):
            return "Manually Stopped"
        if last.get("cleanFinish") or last.get("taskCompletion"):
            return "Completed"
        return last.get("status", "Unknown")
