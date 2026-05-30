"""Aliyun IoT Living Link MQTT client for 3i devices."""
from __future__ import annotations

import json
import logging
import ssl
import time
from typing import Any, Callable

import paho.mqtt.client as mqtt
import requests

_LOGGER = logging.getLogger(__name__)

# Aliyun IoT Living Link API
API_REGION_GET = "https://api.link.aliyun.com/living/account/region/get"
API_LOGIN = "https://living-account.{region}.aliyuncs.com/api/prd/loginbyoauth.json"
API_SESSION = "https://api.link.aliyun.com/account/createSessionByAuthCode"
API_REFRESH = "https://api.link.aliyun.com/account/refreshByRefreshToken"

# Default MQTT endpoint
DEFAULT_MQTT_ENDPOINT = "public.iot-as-mqtt.cn-shanghai.aliyuncs.com"
DEFAULT_MQTT_PORT = 1883


class AliyunLivingLinkClient:
    """MQTT client using Aliyun IoT Living Link (iotToken auth)."""

    def __init__(
        self,
        iot_token: str,
        identity_id: str,
        region: str = "cn-shanghai",
        mqtt_endpoint: str = DEFAULT_MQTT_ENDPOINT,
        mqtt_port: int = DEFAULT_MQTT_PORT,
        on_message_callback: Callable[[str, dict], None] | None = None,
    ) -> None:
        """Initialize the Living Link MQTT client."""
        self._iot_token = iot_token
        self._identity_id = identity_id
        self._region = region
        self._mqtt_endpoint = mqtt_endpoint
        self._mqtt_port = mqtt_port
        self._on_message_callback = on_message_callback
        self._client: mqtt.Client | None = None
        self._connected = False
        self._msg_id = 0
        self._subscribed_topics: list[str] = []

    def _generate_client_id(self) -> str:
        """Generate MQTT client ID for Living Link mode."""
        return f"{self._identity_id}|securemode=2,signmethod=hmacsha1|"

    def _generate_username(self) -> str:
        """Generate MQTT username."""
        return self._identity_id

    def _generate_password(self) -> str:
        """Generate MQTT password (iotToken)."""
        return self._iot_token

    def connect(self) -> None:
        """Connect to the Aliyun IoT MQTT broker."""
        client_id = self._generate_client_id()
        username = self._generate_username()
        password = self._generate_password()

        _LOGGER.info(
            "Connecting to MQTT broker: %s:%d (identity: %s)",
            self._mqtt_endpoint,
            self._mqtt_port,
            self._identity_id[:20] + "...",
        )

        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        self._client.username_pw_set(username, password)

        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # Keepalive 65s (matching APK analysis)
        self._client.connect(self._mqtt_endpoint, self._mqtt_port, keepalive=65)
        self._client.loop_start()

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: dict,
        rc: int,
    ) -> None:
        """Handle connection callback."""
        if rc == 0:
            _LOGGER.info("Connected to Aliyun IoT MQTT broker (Living Link)")
            self._connected = True
            # Re-subscribe to topics after reconnect
            for topic in self._subscribed_topics:
                self._client.subscribe(topic, qos=1)
        else:
            _LOGGER.error("MQTT connection failed with code: %d", rc)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        rc: int,
    ) -> None:
        """Handle disconnection callback."""
        _LOGGER.warning("MQTT disconnected with code: %d", rc)
        self._connected = False

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        """Handle incoming MQTT message."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))
            _LOGGER.debug("Received on %s: %s", topic, json.dumps(payload)[:500])
            if self._on_message_callback:
                self._on_message_callback(topic, payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Failed to decode MQTT message on %s", msg.topic)
        except Exception:
            _LOGGER.exception("Error handling MQTT message")

    def subscribe(self, topic: str, qos: int = 1) -> None:
        """Subscribe to a topic."""
        if topic not in self._subscribed_topics:
            self._subscribed_topics.append(topic)
        if self._client and self._connected:
            self._client.subscribe(topic, qos=qos)
            _LOGGER.debug("Subscribed to: %s", topic)

    def publish(self, topic: str, payload: dict, qos: int = 1) -> bool:
        """Publish a JSON message to a topic."""
        if not self._client or not self._connected:
            _LOGGER.error("Cannot publish: MQTT not connected")
            return False

        self._msg_id += 1
        payload["id"] = str(self._msg_id)
        payload.setdefault("version", "1.0")

        message = json.dumps(payload)
        result = self._client.publish(topic, message, qos=qos)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.debug("Published to %s", topic)
            return True
        else:
            _LOGGER.error("Failed to publish to %s: %s", topic, result.rc)
            return False

    def publish_property_set(self, properties: dict[str, Any]) -> bool:
        """Set device properties."""
        return self.publish(
            "thing/service/property/set",
            {"method": "thing.service.property.set", "params": properties},
        )

    def publish_property_get(self, keys: list[str]) -> bool:
        """Get device properties."""
        return self.publish(
            "thing/service/property/get",
            {"method": "thing.service.property.get", "params": keys},
        )


def refresh_iot_token(refresh_token: str) -> dict | None:
    """Refresh the iotToken using the refreshToken.

    Returns dict with new iotToken, refreshToken, identityId, etc.
    """
    try:
        resp = requests.post(
            API_REFRESH,
            json={"refreshToken": refresh_token},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 200:
            return data.get("data")
        else:
            _LOGGER.error("Token refresh failed: %s", data)
            return None
    except Exception:
        _LOGGER.exception("Failed to refresh iotToken")
        return None
