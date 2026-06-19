"""3i Smart Device 集成配置流程。

基于抓包结果重写：
  - 第一步：输入用户名+密码（3i App 实际登录方式）
  - 第二步：选择要添加的设备
  - 备选：手动输入已有令牌
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api_client import ThreeiApiClient
from .auth_flow import login_with_password
from .const import (
    CONF_API_BASE_URL,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_AUTHORIZATION,
    CONF_CDN_URL,
    CONF_CLIENT_TOKEN,
    CONF_DEVICE_ID,
    CONF_DEVICE_SN,
    CONF_JWT_TOKEN,
    CONF_OPEN_ID,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SELECTED_DEVICES,
    CONF_SID,
    CONF_TENANT_ID,
    CONF_USER_ID,
    CONF_USERNAME,
    DEFAULT_APP_ID,
    DEFAULT_APP_KEY,
    DEFAULT_CDN_URL,
    DEFAULT_TENANT_ID,
    DOMAIN,
    LOGIN_METHOD_MANUAL,
    LOGIN_METHOD_PASSWORD,
    OA_PHONE_REGION_CODE,
)

_LOGGER = logging.getLogger(__name__)


# ========================================================================
# Step 1：选择登录方式
# ========================================================================

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("method", default=LOGIN_METHOD_PASSWORD): vol.In(
            {
                LOGIN_METHOD_PASSWORD: "Username + Password",
                LOGIN_METHOD_MANUAL: "Manual Token Entry (Advanced)",
            }
        ),
    }
)


# ========================================================================
# Step 2：用户名 + 密码
# ========================================================================

STEP_PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional("region_code", default=OA_PHONE_REGION_CODE): str,
    }
)


# ========================================================================
# Step 3：选择设备
# ========================================================================

def _build_device_select_schema(devices: list[dict[str, Any]]) -> vol.Schema:
    """构建设备选择 schema。"""
    options: dict[str, str] = {}
    for d in devices:
        did = str(d.get("deviceId") or d.get("id") or "")
        if not did:
            continue
        name = d.get("name") or d.get("deviceName") or d.get("nickName") or f"Device {did[:8]}"
        sn = d.get("sn") or d.get("deviceSn") or ""
        product = d.get("productModeCode") or d.get("productCode") or ""
        label = f"{name} ({product}, SN:{sn[-6:] if sn else 'n/a'})"
        options[did] = label
    return vol.Schema(
        {vol.Required("devices"): vol.All(list, [vol.In(options)])}
    )


# ========================================================================
# 手动输入（备选）
# ========================================================================

STEP_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_USER_ID): str,
        vol.Required(CONF_OPEN_ID): str,
        vol.Required(CONF_SID): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
        vol.Optional(CONF_AUTHORIZATION, default=""): str,
        vol.Optional(CONF_CLIENT_TOKEN, default=""): str,
        vol.Optional(CONF_TENANT_ID, default=DEFAULT_TENANT_ID): str,
        vol.Optional(CONF_APP_ID, default=DEFAULT_APP_ID): str,
        vol.Optional(CONF_APP_KEY, default=DEFAULT_APP_KEY): str,
        vol.Optional(CONF_CDN_URL, default=DEFAULT_CDN_URL): str,
    }
)


class ThreeiConfigFlow(ConfigFlow, domain=DOMAIN):
    """3i 设备配置流。"""

    VERSION = 2

    def __init__(self) -> None:
        """初始化。"""
        self._username: str = ""
        self._password: str = ""
        self._region_code: str = OA_PHONE_REGION_CODE
        self._login_result: dict[str, Any] | None = None
        self._devices: list[dict[str, Any]] = []
        self._error: str = ""

    # ------------------------------------------------------------------
    # Step 1：选择登录方式
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """选择登录方式。"""
        if user_input is not None:
            method = user_input.get("method", LOGIN_METHOD_PASSWORD)
            if method == LOGIN_METHOD_MANUAL:
                return await self.async_step_manual()
            return await self.async_step_password()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
        )

    # ------------------------------------------------------------------
    # Step 2：输入用户名+密码
    # ------------------------------------------------------------------

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """输入用户名+密码登录。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._region_code = user_input.get("region_code", OA_PHONE_REGION_CODE)

            # 设置唯一 ID（基于用户名）
            await self.async_set_unique_id(self._username.lower())
            self._abort_if_unique_id_configured()

            # 尝试登录
            result = await login_with_password(
                self._username, self._password, region_code=self._region_code
            )

            if result.get("success"):
                self._login_result = result
                # 获取设备列表
                await self._fetch_devices()
                return await self.async_step_devices()
            else:
                self._error = result.get("error", "未知错误")
                errors["base"] = "login_failed"
                _LOGGER.error("Login failed: %s", self._error)

        return self.async_show_form(
            step_id="password",
            data_schema=STEP_PASSWORD_SCHEMA,
            errors=errors,
            description_placeholders={"error": self._error} if self._error else None,
        )

    async def _fetch_devices(self) -> None:
        """登录后获取设备列表。"""
        if not self._login_result:
            return
        try:
            async with ThreeiApiClient(username=self._username) as client:
                # 恢复登录态
                client.load_from_dict(self._login_result)
                client._authorization = self._login_result.get("sid", "")
                client._token_acquired_at = 0  # 强制下次刷新 token
                self._devices = await client.get_devices()
                _LOGGER.info("Found %d 3i devices", len(self._devices))
        except Exception:
            _LOGGER.exception("Failed to fetch devices")
            self._devices = []

    # ------------------------------------------------------------------
    # Step 3：选择要添加的设备
    # ------------------------------------------------------------------

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """选择要添加到 HA 的设备。"""
        errors: dict[str, str] = {}

        if not self._devices:
            return self.async_abort(reason="no_devices")

        if user_input is not None:
            selected = user_input.get("devices", [])
            if not selected:
                errors["base"] = "no_device_selected"
            else:
                return self._create_entry(selected)

        # 构建设备选择 schema
        schema = _build_device_select_schema(self._devices)
        return self.async_show_form(
            step_id="devices",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "count": str(len(self._devices)),
                "username": self._username,
            },
        )

    def _create_entry(self, selected_device_ids: list[str]) -> FlowResult:
        """创建 config entry。"""
        assert self._login_result is not None

        title = f"3i ({self._username})"
        if len(selected_device_ids) == 1:
            # 显示设备名
            for d in self._devices:
                if str(d.get("deviceId") or d.get("id")) == selected_device_ids[0]:
                    name = d.get("name") or d.get("deviceName")
                    if name:
                        title = f"3i {name}"
                    break

        data = {
            # 用户凭据
            CONF_USERNAME: self._username,
            "password": self._password,  # 保留以便 token 失效时自动重登
            CONF_USER_ID: self._login_result.get("user_id", ""),
            CONF_OPEN_ID: self._login_result.get("open_id", ""),
            CONF_SID: self._login_result.get("sid", ""),
            CONF_REFRESH_TOKEN: self._login_result.get("refresh_token", ""),
            CONF_AUTHORIZATION: self._login_result.get("authorization", ""),
            CONF_CLIENT_TOKEN: self._login_result.get("client_token", ""),
            CONF_DEVICE_ID: self._login_result.get("device_id", ""),
            # 服务器配置
            CONF_TENANT_ID: DEFAULT_TENANT_ID,
            CONF_APP_ID: DEFAULT_APP_ID,
            CONF_APP_KEY: DEFAULT_APP_KEY,
            CONF_CDN_URL: DEFAULT_CDN_URL,
            CONF_API_BASE_URL: DEFAULT_CDN_URL,
            # 设备选择
            CONF_SELECTED_DEVICES: selected_device_ids,
        }

        return self.async_create_entry(title=title, data=data)

    # ------------------------------------------------------------------
    # 手动输入（高级）
    # ------------------------------------------------------------------

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """手动输入令牌（来自抓包）。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            # 校验令牌至少要有 sid 和 refresh_token
            if not user_input.get(CONF_SID) or not user_input.get(CONF_REFRESH_TOKEN):
                errors["base"] = "missing_token"
            else:
                # 直接创建 entry，不去验证 token
                # 用户承担风险
                title = f"3i ({username}) [manual]"
                data = {
                    CONF_USERNAME: username,
                    CONF_USER_ID: user_input.get(CONF_USER_ID, ""),
                    CONF_OPEN_ID: user_input.get(CONF_OPEN_ID, ""),
                    CONF_SID: user_input.get(CONF_SID, ""),
                    CONF_REFRESH_TOKEN: user_input.get(CONF_REFRESH_TOKEN, ""),
                    CONF_AUTHORIZATION: user_input.get(
                        CONF_AUTHORIZATION, user_input.get(CONF_SID, "")
                    ),
                    CONF_CLIENT_TOKEN: user_input.get(CONF_CLIENT_TOKEN, ""),
                    CONF_TENANT_ID: user_input.get(CONF_TENANT_ID, DEFAULT_TENANT_ID),
                    CONF_APP_ID: user_input.get(CONF_APP_ID, DEFAULT_APP_ID),
                    CONF_APP_KEY: user_input.get(CONF_APP_KEY, DEFAULT_APP_KEY),
                    CONF_CDN_URL: user_input.get(CONF_CDN_URL, DEFAULT_CDN_URL),
                    CONF_API_BASE_URL: user_input.get(CONF_CDN_URL, DEFAULT_CDN_URL),
                    CONF_SELECTED_DEVICES: [],
                }
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_SCHEMA,
            errors=errors,
            description_placeholders={"info": "请输入从抓包中获得的 3i App 令牌"},
        )

    # ------------------------------------------------------------------
    # 重新认证流程（用于修复失效的 config entry）
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """处理重新认证。"""
        self._username = entry_data.get(CONF_USERNAME, "")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """确认并输入新密码。"""
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            result = await login_with_password(self._username, password)
            if result.get("success"):
                # 更新现有 entry 的数据
                entry = await self.async_set_unique_id(self._username.lower())
                if entry:
                    new_data = {**self.hass.config_entries.async_get_entry(entry.entry_id).data}
                    new_data["password"] = password
                    new_data[CONF_USER_ID] = result.get("user_id", "")
                    new_data[CONF_OPEN_ID] = result.get("open_id", "")
                    new_data[CONF_SID] = result.get("sid", "")
                    new_data[CONF_REFRESH_TOKEN] = result.get("refresh_token", "")
                    new_data[CONF_AUTHORIZATION] = result.get("authorization", "")
                    new_data[CONF_CLIENT_TOKEN] = result.get("client_token", "")
                    self.hass.config_entries.async_update_entry(entry, data=new_data)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
            else:
                errors["base"] = "login_failed"
                self._error = result.get("error", "")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                "username": self._username,
                "error": self._error,
            },
        )


# ========================================================================
# 选项流（用于调整设置）
# ========================================================================

class ThreeiOptionsFlow(config_entries.OptionsFlow):
    """3i 设备选项流。"""

    def __init__(self, entry: ConfigEntry) -> None:
        """初始化。"""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """管理选项。"""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    "scan_interval",
                    default=self.entry.options.get("scan_interval", 30),
                ): vol.All(int, vol.Range(min=10, max=600)),
                vol.Optional(
                    "show_inactive_devices",
                    default=self.entry.options.get("show_inactive_devices", True),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
