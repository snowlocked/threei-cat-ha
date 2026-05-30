"""DataUpdateCoordinator for 3i Smart Device."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .ali_iot_client import AliIoTClient
from .const import (
    CONF_IDENTITY_ID,
    CONF_IOT_TOKEN,
    CONF_MQTT_ENDPOINT,
    CONF_MQTT_PORT,
    CONF_REFRESH_TOKEN,
    DEFAULT_MQTT_ENDPOINT,
    DEFAULT_MQTT_PORT,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
    PROP_AUTO_CLEAN,
    PROP_BATTERY,
    PROP_BIN_FULL,
    PROP_BIN_FULL_ALT,
    PROP_CHARGING,
    PROP_CHILD_LOCK,
    PROP_CLEAN_FINISH,
    PROP_CLEAN_STATUS,
    PROP_DEVICE_LIGHT,
    PROP_FIRMWARE_CODE,
    PROP_MCU_VERSION,
    PROP_SUCTION_LEVEL,
    PROP_WATER_LEVEL,
    PROP_WORK_MODE,
    REFRESH_MARGIN,
    REFRESH_TOKEN_LIFETIME,
    TOPIC_DOWN_PROPERTIES,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


class ThreeiDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for 3i Smart Device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        self._client: AliIoTClient | None = None
        self._token_refresh_task: asyncio.Task | None = None
        self.device_state: dict = {}

        # Device info
        self.identity_id: str = entry.data[CONF_IDENTITY_ID]
        self.device_id: str = entry.data[CONF_IDENTITY_ID]

    @callback
    def _on_message(self, topic: str, payload: dict) -> None:
        """Handle incoming MQTT message."""
        _LOGGER.debug("Processing message on %s: %s", topic, payload)
        if topic == TOPIC_DOWN_PROPERTIES:
            self._handle_properties(payload)
        else:
            _LOGGER.debug("Ignoring message on topic %s", topic)

    def _handle_properties(self, payload: dict) -> None:
        """Handle property change notification."""
        params = payload.get("params", payload)
        if isinstance(params, dict):
            self.device_state.update(params)
            _LOGGER.debug("Updated device state: %s", self.device_state)
            self.async_set_updated_data(self.device_state)

    def _on_token_refresh(self, iot_token: str, refresh_token: str) -> None:
        """Handle token refresh."""
        _LOGGER.info("Tokens refreshed, updating config entry")
        new_data = {**self.entry.data, CONF_IOT_TOKEN: iot_token}
        if refresh_token:
            new_data[CONF_REFRESH_TOKEN] = refresh_token
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    async def _async_refresh_loop(self) -> None:
        """Background task to refresh tokens before expiry."""
        while True:
            if not self._client:
                await asyncio.sleep(60)
                continue
            wait_seconds = self._client.get_seconds_until_refresh()
            if wait_seconds <= 0:
                _LOGGER.info("IoT token needs refresh")
                success = await self._client.refresh_token()
                if success:
                    _LOGGER.info("Token refreshed successfully")
                else:
                    _LOGGER.error("Token refresh failed, retrying in 60s")
                    await asyncio.sleep(60)
                    continue
            else:
                _LOGGER.debug(
                    "Token refresh in %.0f seconds", wait_seconds
                )
                await asyncio.sleep(min(wait_seconds, 3600))

    async def _async_update_data(self) -> dict:
        """Fetch data from the device."""
        if self._client and self._client.connected:
            self._client.publish_property_get()
        return self.device_state

    async def async_config_entry_first_refresh(self) -> None:
        """Set up the MQTT client and do first refresh."""
        mqtt_endpoint = self.entry.data.get(
            CONF_MQTT_ENDPOINT, DEFAULT_MQTT_ENDPOINT
        )
        mqtt_port = self.entry.data.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)

        self._client = AliIoTClient(
            identity_id=self.entry.data[CONF_IDENTITY_ID],
            iot_token=self.entry.data[CONF_IOT_TOKEN],
            refresh_token=self.entry.data[CONF_REFRESH_TOKEN],
            mqtt_endpoint=mqtt_endpoint,
            mqtt_port=int(mqtt_port),
            on_message=self._on_message,
            on_token_refresh=self._on_token_refresh,
        )
        await self._client.async_connect()

        # Start token refresh background task
        self._token_refresh_task = asyncio.create_task(
            self._async_refresh_loop()
        )

        # Wait briefly for connection
        for _ in range(20):
            if self._client.connected:
                break
            await asyncio.sleep(0.5)

        if self._client.connected:
            self._client.publish_property_get()

        # Do initial data update
        self.async_set_updated_data(self.device_state)

    async def async_shutdown(self) -> None:
        """Shut down the coordinator."""
        if self._token_refresh_task:
            self._token_refresh_task.cancel()
            try:
                await self._token_refresh_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.async_disconnect()
            self._client = None

    # Service methods
    def start_clean(self) -> None:
        """Start cleaning."""
        if self._client:
            self._client.publish_property_set({"work_mode": 1, "clean_status": 1})

    def stop_clean(self) -> None:
        """Stop cleaning."""
        if self._client:
            self._client.publish_property_set({"clean_status": 0})

    def start_recharge(self) -> None:
        """Return to dock."""
        if self._client:
            self._client.publish_property_set({"work_mode": 3, "clean_status": 5})

    def stop_recharge(self) -> None:
        """Stop returning to dock."""
        if self._client:
            self._client.publish_property_set({"clean_status": 0})

    def set_work_mode(self, mode: int) -> None:
        """Set work mode."""
        if self._client:
            self._client.publish_property_set({"work_mode": mode})

    def set_water_level(self, level: int) -> None:
        """Set water level."""
        if self._client:
            self._client.publish_property_set({"water_level": level})

    def set_suction_level(self, level: int) -> None:
        """Set suction level."""
        if self._client:
            self._client.publish_property_set({"suction_level": level})

    @property
    def device_info(self) -> dict:
        """Return device info for entity registration."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": "3i F1 Pro",
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
        }

    @property
    def battery_level(self) -> int | None:
        """Return battery level."""
        return self.device_state.get(PROP_BATTERY)

    @property
    def is_charging(self) -> bool | None:
        """Return charging status."""
        val = self.device_state.get(PROP_CHARGING)
        if val is not None:
            return bool(val)
        return None

    @property
    def work_mode(self) -> int | None:
        """Return work mode."""
        return self.device_state.get(PROP_WORK_MODE)

    @property
    def clean_status(self) -> int | None:
        """Return clean status."""
        return self.device_state.get(PROP_CLEAN_STATUS)

    @property
    def water_level(self) -> int | None:
        """Return water level."""
        return self.device_state.get(PROP_WATER_LEVEL)

    @property
    def suction_level(self) -> int | None:
        """Return suction level."""
        return self.device_state.get(PROP_SUCTION_LEVEL)

    @property
    def bin_full(self) -> bool | None:
        """Return bin full status."""
        val = self.device_state.get(PROP_BIN_FULL) or self.device_state.get(
            PROP_BIN_FULL_ALT
        )
        if val is not None:
            return bool(val)
        return None

    @property
    def firmware_version(self) -> str | None:
        """Return firmware version."""
        return self.device_state.get(PROP_FIRMWARE_CODE)

    @property
    def mcu_version(self) -> str | None:
        """Return MCU version."""
        return self.device_state.get(PROP_MCU_VERSION)
