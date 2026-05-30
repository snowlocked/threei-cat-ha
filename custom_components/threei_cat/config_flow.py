"""Config flow for 3i Smart Device integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_API_BASE_URL,
    CONF_IDENTITY_ID,
    CONF_IOT_TOKEN,
    CONF_JWT_TOKEN,
    CONF_MQTT_ENDPOINT,
    CONF_MQTT_PORT,
    CONF_REFRESH_TOKEN,
    CONF_TENANT_ID,
    DEFAULT_API_BASE_URL,
    DEFAULT_MQTT_ENDPOINT,
    DEFAULT_MQTT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IOT_TOKEN): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
        vol.Required(CONF_IDENTITY_ID): str,
        vol.Optional(
            CONF_MQTT_ENDPOINT, default=DEFAULT_MQTT_ENDPOINT
        ): str,
        vol.Optional(
            CONF_MQTT_PORT, default=DEFAULT_MQTT_PORT
        ): int,
        vol.Optional(
            CONF_API_BASE_URL, default=DEFAULT_API_BASE_URL
        ): str,
        vol.Optional(CONF_JWT_TOKEN, default=""): str,
        vol.Optional(CONF_TENANT_ID, default=""): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # Validate identity_id format
    if not data[CONF_IDENTITY_ID].strip():
        raise ValueError("Identity ID cannot be empty")
    if not data[CONF_IOT_TOKEN].strip():
        raise ValueError("IoT Token cannot be empty")
    if not data[CONF_REFRESH_TOKEN].strip():
        raise ValueError("Refresh Token cannot be empty")

    return {
        "title": f"3i F1 Pro ({data[CONF_IDENTITY_ID][:8]}...)",
    }


class ThreeiCatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 3i Smart Device."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ValueError as err:
                _LOGGER.error("Validation error: %s", err)
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check for existing entry with same identity_id
                await self.async_set_unique_id(user_input[CONF_IDENTITY_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
