"""3i Smart Device (3i 猫砂盆) Home Assistant 集成.

基于对 3i 官方 App 的抓包分析重写。
使用 HTTP API 轮询获取设备状态，支持用户名+密码登录。

主要功能:
  - 设备状态（电池、清洁状态、水量、除臭档位）
  - 清洁记录
  - 制水记录
  - 耗材寿命
  - 多设备支持
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import ThreeiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# 支持的平台
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """设置集成（由 YAML 配置触发时调用）。"""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """从 config entry 设置 3i 集成。

    创建协调器，加载所有平台。
    """
    coordinator = ThreeiDataUpdateCoordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        # 如果首次刷新失败，标记 entry 为不可用状态
        _LOGGER.error("Failed to set up 3i device: %s", err)
        raise ConfigEntryNotReady(f"无法连接到 3i 云服务: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 注册服务（每个 entry 一次）
    await _register_services(hass)

    # 加载所有平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 注册更新监听器（用于 options flow）
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载 config entry。"""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ThreeiDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    else:
        _LOGGER.warning("Failed to unload platforms for entry %s", entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """监听 entry 更新（如 options 变化）。"""
    await hass.config_entries.async_reload(entry.entry_id)


async def _register_services(hass: HomeAssistant) -> None:
    """注册集成级服务。"""
    # 仅在第一次时注册
    if hass.data[DOMAIN].get("_services_registered"):
        return
    hass.data[DOMAIN]["_services_registered"] = True

    async def refresh_all(call) -> None:
        """刷新所有 3i 设备数据。"""
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if entry_id == "_services_registered":
                continue
            if isinstance(coordinator, ThreeiDataUpdateCoordinator):
                await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, "refresh_all", refresh_all,
    )
