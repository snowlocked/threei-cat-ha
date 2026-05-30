"""Config flow for 3i Smart Device integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .auth_flow import login_with_code, send_verify_code
from .const import (
    CONF_API_BASE_URL,
    CONF_IDENTITY_ID,
    CONF_IOT_TOKEN,
    CONF_JWT_TOKEN,
    CONF_MQTT_ENDPOINT,
    CONF_MQTT_PORT,
    CONF_PHONE,
    CONF_PHONE_REGION,
    CONF_REFRESH_TOKEN,
    CONF_TENANT_ID,
    CONF_VERIFY_CODE,
    DEFAULT_API_BASE_URL,
    DEFAULT_MQTT_ENDPOINT,
    DEFAULT_MQTT_PORT,
    DEFAULT_TENANT_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for 3i Smart Device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._phone = ""
        self._phone_region = "86"
        self._device_id = ""
        self._error_msg = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose login method."""
        if user_input is not None:
            method = user_input.get("method", "phone")
            if method == "phone":
                return await self.async_step_login()
            else:
                return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("method", default="phone"): vol.In(
                        {"phone": "Phone + Verification Code", "manual": "Manual Token Entry"}
                    )
                }
            ),
        )

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Enter phone number."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._phone = user_input[CONF_PHONE]
            self._phone_region = user_input.get(CONF_PHONE_REGION, "86")

            result = await send_verify_code(self._phone, self._phone_region)
            if result.get("success"):
                self._device_id = result.get("device_id", "")
                return await self.async_step_code()
            else:
                self._error_msg = result.get("error", "Unknown error")
                errors["base"] = "send_code_failed"
                _LOGGER.error("Failed to initialize: %s", result)

        schema = vol.Schema(
            {
                vol.Required(CONF_PHONE, default=self._phone): str,
                vol.Optional(CONF_PHONE_REGION, default=self._phone_region): str,
            }
        )

        return self.async_show_form(
            step_id="login",
            data_schema=schema,
            errors=errors,
            description_placeholders={"error": self._error_msg},
        )

    async def async_step_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Enter verification code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input[CONF_VERIFY_CODE]

            result = await login_with_code(
                self._phone, code, self._device_id, self._phone_region
            )

            if result.get("success"):
                identity_id = result.get("identity_id", "")
                await self.async_set_unique_id(identity_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"3i Device ({self._phone})",
                    data={
                        CONF_IOT_TOKEN: result["iot_token"],
                        CONF_REFRESH_TOKEN: result["refresh_token"],
                        CONF_IDENTITY_ID: result["identity_id"],
                        CONF_JWT_TOKEN: result.get("jwt_token", ""),
                        CONF_TENANT_ID: result.get("tenant_id", DEFAULT_TENANT_ID),
                        CONF_MQTT_ENDPOINT: result.get("mqtt_endpoint", DEFAULT_MQTT_ENDPOINT),
                        CONF_MQTT_PORT: result.get("mqtt_port", DEFAULT_MQTT_PORT),
                        CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
                    },
                )
            else:
                self._error_msg = result.get("error", "Login failed")
                errors["base"] = "login_failed"
                _LOGGER.error("Login failed: %s", result)

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema(
                {vol.Required(CONF_VERIFY_CODE): str}
            ),
            errors=errors,
            description_placeholders={"error": self._error_msg},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manual token entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            identity_id = user_input[CONF_IDENTITY_ID]
            await self.async_set_unique_id(identity_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"3i Device ({identity_id[:16]}...)",
                data={
                    CONF_IOT_TOKEN: user_input[CONF_IOT_TOKEN],
                    CONF_REFRESH_TOKEN: user_input[CONF_REFRESH_TOKEN],
                    CONF_IDENTITY_ID: identity_id,
                    CONF_JWT_TOKEN: user_input.get(CONF_JWT_TOKEN, ""),
                    CONF_TENANT_ID: user_input.get(CONF_TENANT_ID, DEFAULT_TENANT_ID),
                    CONF_MQTT_ENDPOINT: user_input.get(CONF_MQTT_ENDPOINT, DEFAULT_MQTT_ENDPOINT),
                    CONF_MQTT_PORT: user_input.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT),
                    CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
                },
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IOT_TOKEN): str,
                    vol.Required(CONF_REFRESH_TOKEN): str,
                    vol.Required(CONF_IDENTITY_ID): str,
                    vol.Optional(CONF_JWT_TOKEN, default=""): str,
                    vol.Optional(CONF_TENANT_ID, default=DEFAULT_TENANT_ID): str,
                    vol.Optional(CONF_MQTT_ENDPOINT, default=DEFAULT_MQTT_ENDPOINT): str,
                    vol.Optional(CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT): int,
                }
            ),
            errors=errors,
        )
