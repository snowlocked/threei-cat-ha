"""3i Smart Device 数据更新协调器（HTTP polling 版本）。

基于抓包结果：设备控制走 HTTP API，不使用 MQTT。
本协调器定时轮询设备状态、清洁记录、耗材等信息。

架构：
  - 每个 coordinator 实例对应一个 config entry
  - 每个 config entry 可关联多个设备（多设备支持）
  - 定时刷新：设备状态 30s，记录/耗材 5min
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client import ThreeiApiClient
from .const import (
    CONF_API_BASE_URL,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_AUTHORIZATION,
    CONF_CLIENT_TOKEN,
    CONF_CDN_URL,
    CONF_DEVICE_ID,
    CONF_DEVICE_SN,
    CONF_JWT_TOKEN,
    CONF_OPEN_ID,
    CONF_REFRESH_TOKEN,
    CONF_SELECTED_DEVICES,
    CONF_SID,
    CONF_TENANT_ID,
    CONF_USER_ID,
    CONF_USERNAME,
    DEFAULT_CDN_URL,
    DEFAULT_RECORDS_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_MODEL_DEFAULT,
    DOMAIN,
    MANUFACTURER,
    PROP_BATTERY,
    PROP_BATTERY_LEVEL,
    PROP_BIN_FULL,
    PROP_BIN_FULL_LEGACY,
    PROP_CAT_WEIGHT,
    PROP_CHARGING,
    PROP_CHARGE_STATUS,
    PROP_CLEAN_STATUS,
    PROP_CLEAN_STATUS_LEGACY,
    PROP_DEODORIZE,
    PROP_DEODORIZE_LEVEL,
    PROP_ERROR_CODE,
    PROP_ERROR_MSG,
    PROP_FIRMWARE_CODE,
    PROP_FIRMWARE_VERSION,
    PROP_HARDWARE_VERSION,
    PROP_LAST_CAT_WEIGHT,
    PROP_MCU_VERSION,
    PROP_MCU_VERSION_CODE,
    PROP_MCU_VERSION_CODE_LEGACY,
    PROP_ONLINE,
    PROP_ONLINE_STATUS,
    PROP_POWER,
    PROP_SOFTWARE_VERSION,
    PROP_WATER_EMPTY,
    PROP_WATER_LEVEL,
    PROP_WATER_LOW,
    PROP_WORK_MODE,
    PROP_WORK_MODE_LEGACY,
    PROP_WORK_STATUS,
    SCAN_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


# ========================================================================
# 设备数据模型
# ========================================================================

class ThreeiDeviceData:
    """单个设备的所有数据缓存。"""

    def __init__(self, device_info: dict[str, Any]) -> None:
        self.device_info = device_info
        self.device_id = str(
            device_info.get("deviceId")
            or device_info.get("id")
            or device_info.get("iotId")
            or ""
        )
        self.sn = str(device_info.get("sn") or device_info.get("deviceSn") or self.device_id)
        self.product_id = str(
            device_info.get("productId") or device_info.get("productCode") or ""
        )
        self.product_mode_code = device_info.get("productModeCode") or ""
        self.name = device_info.get("name") or device_info.get("deviceName") or "3i Device"
        self.mac = device_info.get("mac") or ""

        # 实时数据
        self.shadow: dict[str, Any] = {}
        self.properties: dict[str, Any] = {}

        # 历史数据
        self.clean_records: list[dict[str, Any]] = []
        self.water_records: list[dict[str, Any]] = []
        self.consumables: list[dict[str, Any]] = []

        # 上次更新时间
        self.last_update: float = 0.0
        self.last_records_update: float = 0.0

    # ----------------------------------------------------------------
    # 设备状态属性便捷访问
    # ----------------------------------------------------------------

    def get_prop(self, *keys: str, default: Any = None) -> Any:
        """按顺序尝试多个属性键，返回第一个找到的值。"""
        for k in keys:
            if k in self.properties:
                return self.properties[k]
        return default

    @property
    def battery(self) -> int | None:
        v = self.get_prop(PROP_BATTERY, PROP_BATTERY_LEVEL)
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @property
    def charging(self) -> bool | None:
        v = self.get_prop(PROP_CHARGING, PROP_CHARGE_STATUS)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        return int(v) > 0 if isinstance(v, (int, float)) else False

    @property
    def online(self) -> bool | None:
        v = self.get_prop(PROP_ONLINE, PROP_ONLINE_STATUS)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        return int(v) > 0

    @property
    def work_mode(self) -> int | None:
        v = self.get_prop(PROP_WORK_MODE, PROP_WORK_MODE_LEGACY)
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @property
    def clean_status(self) -> int | None:
        v = self.get_prop(PROP_CLEAN_STATUS, PROP_CLEAN_STATUS_LEGACY, PROP_WORK_STATUS)
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @property
    def water_level(self) -> int | None:
        v = self.get_prop(PROP_WATER_LEVEL)
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @property
    def water_low(self) -> bool | None:
        v = self.get_prop(PROP_WATER_LOW, PROP_WATER_EMPTY)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        return int(v) > 0

    @property
    def bin_full(self) -> bool | None:
        v = self.get_prop(PROP_BIN_FULL, PROP_BIN_FULL_LEGACY)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        return int(v) > 0

    @property
    def cat_weight(self) -> float | None:
        v = self.get_prop(PROP_CAT_WEIGHT, PROP_LAST_CAT_WEIGHT)
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    @property
    def deodorize_level(self) -> int | None:
        v = self.get_prop(PROP_DEODORIZE_LEVEL, PROP_DEODORIZE)
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @property
    def firmware_version(self) -> str | None:
        v = self.get_prop(PROP_FIRMWARE_CODE, PROP_FIRMWARE_VERSION, PROP_SOFTWARE_VERSION)
        return str(v) if v is not None else None

    @property
    def mcu_version(self) -> str | None:
        v = self.get_prop(
            PROP_MCU_VERSION_CODE,
            PROP_MCU_VERSION,
            PROP_MCU_VERSION_CODE_LEGACY,
            PROP_HARDWARE_VERSION,
        )
        return str(v) if v is not None else None

    @property
    def error_code(self) -> str | None:
        v = self.get_prop(PROP_ERROR_CODE, PROP_ERROR_MSG)
        return str(v) if v is not None else None

    @property
    def power(self) -> bool | None:
        v = self.get_prop(PROP_POWER)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        return int(v) > 0

    @property
    def is_available(self) -> bool:
        """设备是否在线/可用。"""
        if self.online is not None:
            return self.online
        # 兜底：如果 properties 非空，认为可用
        return bool(self.properties)


# ========================================================================
# 协调器
# ========================================================================

class ThreeiDataUpdateCoordinator(DataUpdateCoordinator):
    """3i 设备数据更新协调器。

    使用 HTTP polling 方式，定时查询设备状态。
    支持多设备。
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """初始化协调器。"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.config_entry = entry
        self.api_client: ThreeiApiClient | None = None

        # 设备数据缓存（按 device_id 索引）
        self.devices: dict[str, ThreeiDeviceData] = {}

        # 第一次刷新时的设备列表
        self._initial_device_ids: list[str] = entry.data.get(CONF_SELECTED_DEVICES, [])

        # 元数据
        self.user_id: str = entry.data.get(CONF_USER_ID, "")
        self.username: str = entry.data.get(CONF_USERNAME, "")
        self.tenant_id: str = entry.data.get(CONF_TENANT_ID, "")

        # 记录刷新节流：避免每次轮询都拉记录
        self._last_records_refresh: float = 0.0
        self._records_refresh_interval: float = DEFAULT_RECORDS_SCAN_INTERVAL

        # token 刷新任务
        self._token_refresh_task: asyncio.Task | None = None

    # ----------------------------------------------------------------
    # 初始化
    # ----------------------------------------------------------------

    async def async_config_entry_first_refresh(self) -> None:
        """首次刷新：建立 API 客户端并获取设备列表。"""
        await self._setup_api_client()
        await self._discover_devices()

        # 首次数据刷新
        await self.async_refresh()

        # 启动后台 token 刷新任务
        self._token_refresh_task = self.hass.async_create_task(
            self._token_refresh_loop()
        )

    async def _setup_api_client(self) -> None:
        """根据 entry 数据创建 API 客户端。"""
        data = self.config_entry.data

        username = data.get(CONF_USERNAME, "")
        if not username:
            raise UpdateFailed("配置缺少用户名")

        self.api_client = ThreeiApiClient(
            username=username,
            app_id=data.get(CONF_APP_ID, ""),
            app_key=data.get(CONF_APP_KEY, ""),
            tenant_id=data.get(CONF_TENANT_ID, ""),
            cdn_url=data.get(CONF_CDN_URL, DEFAULT_CDN_URL),
        )

        # 从 entry 恢复会话状态
        load_data = {
            CONF_USERNAME: data.get(CONF_USERNAME, ""),
            CONF_USER_ID: data.get(CONF_USER_ID, ""),
            CONF_OPEN_ID: data.get(CONF_OPEN_ID, ""),
            CONF_SID: data.get(CONF_SID, ""),
            CONF_REFRESH_TOKEN: data.get(CONF_REFRESH_TOKEN, ""),
            CONF_AUTHORIZATION: data.get(CONF_AUTHORIZATION, ""),
            CONF_CLIENT_TOKEN: data.get(CONF_CLIENT_TOKEN, ""),
            CONF_APP_ID: data.get(CONF_APP_ID, ""),
            CONF_APP_KEY: data.get(CONF_APP_KEY, ""),
            CONF_TENANT_ID: data.get(CONF_TENANT_ID, ""),
        }
        self.api_client.load_from_dict(load_data)

        # 如果没有 sid（首次登录失败），尝试重新登录
        # 但如果已有 authorization token，跳过重新登录
        if not self.api_client.sid or not self.api_client.refresh_token:
            # 检查是否有直接提供的 authorization token
            if self.api_client.authorization:
                _LOGGER.info("Using directly provided authorization token")
            else:
                password = data.get("password", "")
                if password:
                    _LOGGER.info("No stored tokens, re-login with stored password")
                    login_result = await self.api_client.async_login(password)
                    if login_result.get("success"):
                        # 保存到 entry
                        self._persist_tokens(login_result)
                    else:
                        _LOGGER.warning(
                            "Stored password login failed: %s", login_result.get("error")
                        )

    async def _discover_devices(self) -> None:
        """发现用户绑定的设备。"""
        if not self.api_client:
            return
        try:
            devices = await self.api_client.get_devices()
            _LOGGER.info("Discovered %d 3i devices", len(devices))

            # 如果指定了设备列表，则只使用指定的
            if self._initial_device_ids:
                devices = [
                    d for d in devices
                    if str(d.get("deviceId") or d.get("id")) in self._initial_device_ids
                ]

            for dev in devices:
                did = str(dev.get("deviceId") or dev.get("id") or "")
                if not did:
                    continue
                if did not in self.devices:
                    self.devices[did] = ThreeiDeviceData(dev)
                else:
                    self.devices[did].device_info.update(dev)
        except Exception:
            _LOGGER.exception("Failed to discover devices")

    def _persist_tokens(self, login_result: dict[str, Any]) -> None:
        """将登录结果持久化到 config entry。"""
        new_data = {**self.config_entry.data}
        for k in (
            CONF_USER_ID,
            CONF_OPEN_ID,
            CONF_SID,
            CONF_REFRESH_TOKEN,
            CONF_AUTHORIZATION,
            CONF_CLIENT_TOKEN,
        ):
            if k in login_result and login_result[k]:
                new_data[k] = login_result[k]
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

    # ----------------------------------------------------------------
    # 主数据更新
    # ----------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """主轮询回调：刷新所有设备的影子数据。

        Returns:
            dict: {device_id: device_properties}
        """
        if not self.api_client:
            raise UpdateFailed("API 客户端未初始化")

        # 检查 token 是否需要刷新
        if self.api_client.is_token_expired():
            _LOGGER.info("Token expired, refreshing...")
            if await self.api_client.async_refresh_token():
                self._persist_tokens(self.api_client.to_dict())

        now = time.time()
        should_refresh_records = (
            now - self._last_records_refresh > self._records_refresh_interval
        )

        results: dict[str, Any] = {}

        for did, dev_data in list(self.devices.items()):
            try:
                await self._update_one_device(dev_data, with_records=should_refresh_records)
                results[did] = {
                    "device_info": dev_data.device_info,
                    "properties": dict(dev_data.properties),
                    "clean_records": list(dev_data.clean_records),
                    "water_records": list(dev_data.water_records),
                    "consumables": list(dev_data.consumables),
                }
            except Exception as e:
                _LOGGER.warning("Update device %s failed: %s", did, e)
                # 保留旧数据，但标记
                results[did] = None

        if should_refresh_records:
            self._last_records_refresh = now

        return results

    async def _update_one_device(
        self,
        dev: ThreeiDeviceData,
        with_records: bool = True,
    ) -> None:
        """刷新单个设备的数据。"""
        assert self.api_client is not None

        # 设备影子（实时状态）
        shadow = await self.api_client.get_device_shadow(dev.device_id)
        if shadow:
            dev.shadow = shadow if isinstance(shadow, dict) else {}

            # 提取 properties（兼容多种结构）
            props = {}
            if isinstance(dev.shadow, dict):
                # 直接的属性字典
                if "properties" in dev.shadow and isinstance(dev.shadow["properties"], dict):
                    props = dict(dev.shadow["properties"])
                # 或者 properties 在 nested data 里
                elif "data" in dev.shadow:
                    data = dev.shadow["data"]
                    if isinstance(data, dict):
                        if "properties" in data and isinstance(data["properties"], dict):
                            props = dict(data["properties"])
                        else:
                            props = {k: v for k, v in data.items()
                                     if not isinstance(v, (dict, list))}
                else:
                    # shadow 本身就是 properties
                    props = {k: v for k, v in dev.shadow.items()
                             if not isinstance(v, (dict, list))}
            dev.properties = props

        dev.last_update = time.time()

        # 周期性刷新记录和耗材
        if with_records:
            try:
                records = await self.api_client.get_clean_records(
                    dev.device_id, sn=dev.sn, page=1, page_size=20
                )
                if isinstance(records, list):
                    dev.clean_records = records
            except Exception:
                _LOGGER.debug("Fetch clean records failed for %s", dev.device_id)

            try:
                water = await self.api_client.get_event_statistics(
                    sn=dev.sn,
                    identifier="water_make",
                    page=1,
                    page_size=50,
                )
                if isinstance(water, list):
                    dev.water_records = water
            except Exception:
                _LOGGER.debug("Fetch water records failed for %s", dev.device_id)

            if dev.product_id:
                try:
                    consumables = await self.api_client.get_consumables([dev.product_id])
                    if isinstance(consumables, list):
                        dev.consumables = consumables
                except Exception:
                    _LOGGER.debug("Fetch consumables failed for %s", dev.device_id)

            dev.last_records_update = time.time()

    # ----------------------------------------------------------------
    # Token 刷新后台任务
    # ----------------------------------------------------------------

    async def _token_refresh_loop(self) -> None:
        """后台定时刷新 token。"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时检查一次
                if self.api_client and self.api_client.is_token_expired(max_age=7200):
                    _LOGGER.info("Background token refresh")
                    if await self.api_client.async_refresh_token():
                        self._persist_tokens(self.api_client.to_dict())
            except asyncio.CancelledError:
                break
            except Exception:
                _LOGGER.exception("Background token refresh error")

    # ----------------------------------------------------------------
    # 关闭
    # ----------------------------------------------------------------

    async def async_shutdown(self) -> None:
        """关闭协调器，清理资源。"""
        if self._token_refresh_task and not self._token_refresh_task.done():
            self._token_refresh_task.cancel()
            try:
                await self._token_refresh_task
            except asyncio.CancelledError:
                pass
            self._token_refresh_task = None

        if self.api_client:
            await self.api_client.close()
            self.api_client = None

    # ----------------------------------------------------------------
    # 设备查找
    # ----------------------------------------------------------------

    def get_device(self, device_id: str) -> ThreeiDeviceData | None:
        """根据 device_id 获取设备数据。"""
        return self.devices.get(str(device_id))

    @property
    def primary_device(self) -> ThreeiDeviceData | None:
        """获取主设备（第一个）。"""
        if not self.devices:
            return None
        return next(iter(self.devices.values()))

    # ----------------------------------------------------------------
    # 设备控制（HTTP API 调用，目前为占位实现）
    # ----------------------------------------------------------------

    async def async_control_device(
        self,
        device_id: str,
        properties: dict[str, Any],
    ) -> bool:
        """控制设备属性。

        由于设备 iotId 是 null（未通过云端授权），实际控制走 HTTP API。
        目前该集成主要专注于状态读取，控制命令可通过 service 调用。

        Args:
            device_id: 目标设备 ID
            properties: 要设置的属性字典

        Returns:
            True 如果命令已发送
        """
        _LOGGER.warning(
            "Device control attempted for %s: %s "
            "(not fully supported - device may not be cloud-authorized)",
            device_id, properties,
        )
        # 实际控制需要设备已通过云端授权（iotId 非空）
        # 当前实现仅记录日志，后续刷新会从服务器拉取最新状态
        return False

    # ----------------------------------------------------------------
    # 服务方法（兼容旧版 API）
    # ----------------------------------------------------------------

    def start_clean(self) -> None:
        """开始清洁。"""
        if self.primary_device:
            self.hass.async_create_task(
                self.async_control_device(
                    self.primary_device.device_id,
                    {PROP_WORK_MODE: 1, PROP_CLEAN_STATUS: 1},
                )
            )

    def stop_clean(self) -> None:
        """停止清洁。"""
        if self.primary_device:
            self.hass.async_create_task(
                self.async_control_device(
                    self.primary_device.device_id,
                    {PROP_CLEAN_STATUS: 0},
                )
            )

    def return_to_dock(self) -> None:
        """返回充电桩。"""
        if self.primary_device:
            self.hass.async_create_task(
                self.async_control_device(
                    self.primary_device.device_id,
                    {PROP_WORK_MODE: 3, PROP_CLEAN_STATUS: 5},
                )
            )

    # ----------------------------------------------------------------
    # HA 集成属性
    # ----------------------------------------------------------------

    @property
    def device_info(self) -> dict[str, Any]:
        """主设备的 device_info（兼容旧版 API）。"""
        dev = self.primary_device
        if dev:
            return {
                "identifiers": {(DOMAIN, dev.device_id)},
                "name": dev.name,
                "manufacturer": MANUFACTURER,
                "model": dev.product_mode_code or DEVICE_MODEL_DEFAULT,
                "sw_version": dev.firmware_version,
                "hw_version": dev.mcu_version,
                "serial_number": dev.sn,
            }
        # 兜底
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "3i Device",
            "manufacturer": MANUFACTURER,
            "model": DEVICE_MODEL_DEFAULT,
        }
