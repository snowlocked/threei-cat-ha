"""Aliyun IoT MQTT client for 3i Smart Device."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable

import aiohttp
import paho.mqtt.client as mqtt

from .const import (
    API_CLEAN_RECORDS_URL,
    API_CONSUMABLES_URL,
    API_REFRESH_TOKEN_URL,
    DEFAULT_API_BASE_URL,
    DEFAULT_MQTT_ENDPOINT,
    DEFAULT_MQTT_PORT,
    KEEPALIVE,
    REFRESH_MARGIN,
    REFRESH_TOKEN_LIFETIME,
    TOPIC_DOWN_EVENTS,
    TOPIC_DOWN_PROPERTIES,
    TOPIC_DOWN_STATUS,
    TOPIC_UP_GET,
    TOPIC_UP_SET,
)

_LOGGER = logging.getLogger(__name__)


class AliIoTClient:
    """MQTT client for Aliyun IoT."""

    def __init__(
        self,
        identity_id: str,
        iot_token: str,
        refresh_token: str,
        api_base_url: str = DEFAULT_API_BASE_URL,
        jwt_token: str = "",
        tenant_id: str = "",
        mqtt_endpoint: str = DEFAULT_MQTT_ENDPOINT,
        mqtt_port: int = DEFAULT_MQTT_PORT,
        on_message: Callable[[str, dict], None] | None = None,
        on_token_refresh: Callable[[str, str], None] | None = None,
    ) -> None:
        """Initialize the client."""
        self._identity_id = identity_id
        self._iot_token = iot_token
        self._refresh_token = refresh_token
        self._api_base_url = api_base_url
        self._jwt_token = jwt_token
        self._tenant_id = tenant_id
        self._mqtt_endpoint = mqtt_endpoint
        self._mqtt_port = mqtt_port
        self._on_message = on_message
        self._on_token_refresh = on_token_refresh
        self._client: mqtt.Client | None = None
        self._connected = False
        self._token_acquired_at = time.time()
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def connected(self) -> bool:
        """Return if connected."""
        return self._connected

    def _build_client(self) -> mqtt.Client:
        """Build the MQTT client."""
        client_id = f"{self._identity_id}|securemode=2,signmethod=hmacsha1|"
        client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
        client.username_pw_set(self._identity_id, self._iot_token)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_mqtt_message
        client.reconnect_delay_set(min_delay=1, max_delay=120)
        return client

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: dict,
        rc: int,
    ) -> None:
        """Handle connection."""
        if rc == 0:
            _LOGGER.info("Connected to Aliyun IoT MQTT broker")
            self._connected = True
            client.subscribe(TOPIC_DOWN_PROPERTIES)
            client.subscribe(TOPIC_DOWN_EVENTS)
            client.subscribe(TOPIC_DOWN_STATUS)
            _LOGGER.info("Subscribed to device topics")
        else:
            _LOGGER.error("MQTT connection failed with code %d", rc)
            self._connected = False

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        rc: int,
    ) -> None:
        """Handle disconnection."""
        self._connected = False
        if rc != 0:
            _LOGGER.warning("MQTT disconnected (rc=%d), will reconnect", rc)

    def _on_mqtt_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        """Handle incoming MQTT message."""
        try:
            payload = json.loads(msg.payload.decode())
            _LOGGER.debug("Received on %s: %s", msg.topic, payload)
            if self._on_message:
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(
                        self._on_message, msg.topic, payload
                    )
                else:
                    self._on_message(msg.topic, payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Failed to decode MQTT message on %s", msg.topic)
        except Exception:
            _LOGGER.exception("Error handling MQTT message on %s", msg.topic)

    async def async_connect(self) -> None:
        """Connect to MQTT broker."""
        self._loop = asyncio.get_event_loop()
        self._client = self._build_client()
        try:
            self._client.connect_async(
                self._mqtt_endpoint, self._mqtt_port, keepalive=KEEPALIVE
            )
            self._client.loop_start()
            _LOGGER.info(
                "Connecting to %s:%d", self._mqtt_endpoint, self._mqtt_port
            )
        except Exception:
            _LOGGER.exception("Failed to start MQTT connection")
            raise

    async def async_disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self._connected = False
        _LOGGER.info("MQTT client disconnected")

    def publish_property_set(self, params: dict[str, Any]) -> None:
        """Publish a property set command."""
        if not self._client or not self._connected:
            _LOGGER.warning("Cannot publish: not connected")
            return
        message = {
            "id": str(int(time.time() * 1000)),
            "version": "1.0",
            "method": "thing.service.property.set",
            "params": params,
        }
        payload = json.dumps(message)
        _LOGGER.debug("Publishing to %s: %s", TOPIC_UP_SET, payload)
        self._client.publish(TOPIC_UP_SET, payload, qos=1)

    def publish_property_get(self, params: dict[str, Any] | None = None) -> None:
        """Publish a property get command."""
        if not self._client or not self._connected:
            _LOGGER.warning("Cannot publish: not connected")
            return
        message = {
            "id": str(int(time.time() * 1000)),
            "version": "1.0",
            "method": "thing.service.property.get",
            "params": params or {},
        }
        payload = json.dumps(message)
        _LOGGER.debug("Publishing to %s: %s", TOPIC_UP_GET, payload)
        self._client.publish(TOPIC_UP_GET, payload, qos=1)

    async def refresh_token(self) -> bool:
        """Refresh the IoT token."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    API_REFRESH_TOKEN_URL,
                    json={"refreshToken": self._refresh_token},
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.error("Token refresh failed: %d", resp.status)
                        return False
                    data = await resp.json()
                    new_iot_token = data.get("data", {}).get("iotToken")
                    new_refresh_token = data.get("data", {}).get("refreshToken")
                    if not new_iot_token:
                        _LOGGER.error("No iotToken in refresh response")
                        return False
                    self._iot_token = new_iot_token
                    if new_refresh_token:
                        self._refresh_token = new_refresh_token
                    self._token_acquired_at = time.time()
                    _LOGGER.info("IoT token refreshed")
                    if self._on_token_refresh:
                        self._on_token_refresh(self._iot_token, self._refresh_token)
                    await self._reconnect_with_new_token()
                    return True
        except Exception:
            _LOGGER.exception("Token refresh failed")
            return False

    async def _reconnect_with_new_token(self) -> None:
        """Reconnect to MQTT with new token."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self._connected = False
        self._client = self._build_client()
        try:
            self._client.connect_async(
                self._mqtt_endpoint, self._mqtt_port, keepalive=KEEPALIVE
            )
            self._client.loop_start()
            _LOGGER.info("Reconnected MQTT with new token")
        except Exception:
            _LOGGER.exception("Failed to reconnect")

    def get_seconds_until_refresh(self) -> float:
        """Get seconds until token needs refresh."""
        elapsed = time.time() - self._token_acquired_at
        remaining = REFRESH_TOKEN_LIFETIME - elapsed - REFRESH_MARGIN
        return max(0, remaining)

    def _build_rest_cookies(self) -> dict[str, str]:
        """Build cookie dict for REST API calls to 3irobotix servers."""
        cookies = {"iotToken": self._iot_token}
        if self._jwt_token:
            cookies["auth"] = self._jwt_token
        cookies["country"] = "15"
        cookies["language"] = "en"
        return cookies

    def _build_rest_headers(self) -> dict[str, str]:
        """Build headers for REST API calls."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._tenant_id:
            headers["tenant_id"] = self._tenant_id
        return headers

    async def get_consumables(self) -> dict | None:
        """Fetch consumable information from the cloud API.

        Note: This requires a valid JWT token from the 3i app.
        If the token is missing or expired, this will return None.
        The MQTT-based device properties still work without this.
        """
        if not self._jwt_token or self._jwt_token.startswith("OA-"):
            _LOGGER.debug("Skipping consumables API - no valid JWT token")
            return None

        cookies = self._build_rest_cookies()
        headers = self._build_rest_headers()

        endpoints = [
            f"https://{self._api_base_url}/outer/app/productInfo/getConsumablesByProductIds",
            f"https://{self._api_base_url}/app/user/getConsumablesInfoByUserId",
        ]

        async with aiohttp.ClientSession() as session:
            for url in endpoints:
                for method in ["POST", "GET"]:
                    try:
                        if method == "GET":
                            resp_ctx = session.get(
                                url, headers=headers, cookies=cookies,
                                timeout=aiohttp.ClientTimeout(total=10),
                            )
                        else:
                            resp_ctx = session.post(
                                url, json={}, headers=headers, cookies=cookies,
                                timeout=aiohttp.ClientTimeout(total=10),
                            )
                        async with resp_ctx as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                _LOGGER.debug("Consumables OK: %s %s", method, url)
                                return data.get("data", data)
                            else:
                                _LOGGER.debug(
                                    "Consumables %s %s -> %d",
                                    method, url, resp.status,
                                )
                    except Exception as e:
                        _LOGGER.debug("Consumables %s %s error: %s", method, url, e)

        return None

    async def get_clean_records(
        self, page: int = 1, page_size: int = 20
    ) -> list | None:
        """Fetch cleaning history records.

        Note: This requires a valid JWT token from the 3i app.
        """
        if not self._jwt_token or self._jwt_token.startswith("OA-"):
            _LOGGER.debug("Skipping clean records API - no valid JWT token")
            return None

        url = f"https://{self._api_base_url}/device-shadow-service/app/data/flow/clean-record-timeline"
        cookies = self._build_rest_cookies()
        headers = self._build_rest_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"page": page, "pageSize": page_size},
                    headers=headers,
                    cookies=cookies,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.debug("Clean records API returned %d", resp.status)
                        return None
                    data = await resp.json()
                    _LOGGER.debug("Clean records: %s", data)
                    result = data.get("data", data)
                    if isinstance(result, dict):
                        return result.get("list", result.get("records", []))
                    return result if isinstance(result, list) else []
        except Exception:
            _LOGGER.debug("Failed to fetch clean records", exc_info=True)
            return None
