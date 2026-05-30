"""Aliyun IoT MQTT client for 3i Cat Litter Box."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import ssl
import time
from typing import Any, Callable

import paho.mqtt.client as mqtt

from .const import (
    MQTT_BROKER_TEMPLATE,
    MQTT_PORT_TLS,
    TOPIC_APP_DOWN_EVENTS,
    TOPIC_APP_DOWN_PROPERTIES,
    TOPIC_APP_DOWN_STATUS,
    TOPIC_PROPERTY_GET,
    TOPIC_PROPERTY_POST,
    TOPIC_PROPERTY_SET,
    TOPIC_SERVICE_INVOKE,
)

_LOGGER = logging.getLogger(__name__)


class AliyunIoTMqttClient:
    """MQTT client for Aliyun IoT Thing Model."""

    def __init__(
        self,
        product_key: str,
        device_name: str,
        device_secret: str,
        on_message_callback: Callable[[str, dict], None] | None = None,
    ) -> None:
        """Initialize the MQTT client."""
        self._product_key = product_key
        self._device_name = device_name
        self._device_secret = device_secret
        self._on_message_callback = on_message_callback
        self._client: mqtt.Client | None = None
        self._connected = False
        self._msg_id = 0

    def _generate_client_id(self) -> str:
        """Generate Aliyun IoT MQTT client ID."""
        return (
            f"{self._device_name}&{self._product_key}"
            f"|securemode=2,_v=ha-1.0,lan=python,"
            f"signmethod=hmacsha1,ext=1|"
        )

    def _generate_username(self) -> str:
        """Generate MQTT username."""
        return f"{self._device_name}&{self._product_key}"

    def _generate_password(self) -> str:
        """Generate HMAC-SHA1 signed password.

        Password = HMAC-SHA1(deviceSecret, sorted_concat)
        sorted_concat = "clientId{clientId}deviceName{deviceName}
                         deviceSecret{deviceSecret}productKey{productKey}"
        """
        client_id = f"{self._device_name}&{self._product_key}"
        content = (
            f"clientId{client_id}"
            f"deviceName{self._device_name}"
            f"deviceSecret{self._device_secret}"
            f"productKey{self._product_key}"
        )
        # Aliyun uses sorted key concatenation
        # Keys sorted: clientId, deviceName, deviceSecret, productKey
        # Already in correct order above
        password = hmac.new(
            self._device_secret.encode("utf-8"),
            content.encode("utf-8"),
            hashlib.sha1,
        ).hexdigest()
        return password

    def _get_broker(self) -> str:
        """Get MQTT broker hostname."""
        return MQTT_BROKER_TEMPLATE.format(product_key=self._product_key)

    def _topic(self, template: str, **kwargs) -> str:
        """Format a topic template with product_key and device_name."""
        return template.format(
            product_key=self._product_key,
            device_name=self._device_name,
            **kwargs,
        )

    def _next_msg_id(self) -> str:
        """Get next message ID."""
        self._msg_id += 1
        return str(self._msg_id)

    def connect(self) -> None:
        """Connect to the Aliyun IoT MQTT broker."""
        client_id = self._generate_client_id()
        username = self._generate_username()
        password = self._generate_password()
        broker = self._get_broker()

        _LOGGER.info("Connecting to MQTT broker: %s:%d", broker, MQTT_PORT_TLS)

        self._client = mqtt.Client(
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
        self._client.username_pw_set(username, password)

        # TLS configuration
        self._client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # Keepalive 65s (matching APK analysis)
        self._client.connect(broker, MQTT_PORT_TLS, keepalive=65)
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
            _LOGGER.info("Connected to Aliyun IoT MQTT broker")
            self._connected = True
            self._subscribe_topics()
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
            _LOGGER.debug("Received message on %s: %s", topic, payload)

            if self._on_message_callback:
                self._on_message_callback(topic, payload)
        except json.JSONDecodeError:
            _LOGGER.warning("Failed to decode MQTT message payload")
        except Exception:
            _LOGGER.exception("Error handling MQTT message")

    def _subscribe_topics(self) -> None:
        """Subscribe to device topics."""
        topics = [
            self._topic(TOPIC_PROPERTY_POST_REPLY),
            self._topic(TOPIC_APP_DOWN_PROPERTIES),
            self._topic(TOPIC_APP_DOWN_EVENTS),
            self._topic(TOPIC_APP_DOWN_STATUS),
            # Wildcard for all service responses
            self._topic(
                "/sys/{product_key}/{device_name}/thing/service/+"
            ),
        ]
        for topic in topics:
            self._client.subscribe(topic, qos=1)
            _LOGGER.debug("Subscribed to: %s", topic)

    def publish_property_set(self, properties: dict[str, Any]) -> bool:
        """Set device properties via MQTT.

        Args:
            properties: Dict of property_key -> value

        Returns:
            True if published successfully.
        """
        topic = self._topic(TOPIC_PROPERTY_SET)
        payload = {
            "id": self._next_msg_id(),
            "version": "1.0",
            "method": "thing.service.property.set",
            "params": properties,
        }
        return self._publish(topic, payload)

    def publish_property_get(self, property_keys: list[str]) -> bool:
        """Get device properties via MQTT.

        Args:
            property_keys: List of property keys to query.

        Returns:
            True if published successfully.
        """
        topic = self._topic(TOPIC_PROPERTY_GET)
        payload = {
            "id": self._next_msg_id(),
            "version": "1.0",
            "method": "thing.service.property.get",
            "params": property_keys,
        }
        return self._publish(topic, payload)

    def publish_service_invoke(
        self, identifier: str, params: dict[str, Any] | None = None
    ) -> bool:
        """Invoke a device service via MQTT.

        Args:
            identifier: Service identifier (e.g., 'ota_upgrade').
            params: Optional service parameters.

        Returns:
            True if published successfully.
        """
        topic = self._topic(
            TOPIC_SERVICE_INVOKE, identifier=identifier
        )
        payload = {
            "id": self._next_msg_id(),
            "version": "1.0",
            "method": f"thing.service.{identifier}",
            "params": params or {},
        }
        return self._publish(topic, payload)

    def publish_ota_upgrade(self) -> bool:
        """Trigger OTA firmware upgrade."""
        return self.publish_service_invoke("ota_upgrade")

    def publish_ota_install_now(self) -> bool:
        """Trigger immediate OTA installation."""
        return self.publish_service_invoke("ota_install_now")

    def _publish(self, topic: str, payload: dict) -> bool:
        """Publish a JSON message to a topic."""
        if not self._client or not self._connected:
            _LOGGER.error("Cannot publish: MQTT not connected")
            return False

        message = json.dumps(payload)
        result = self._client.publish(topic, message, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.debug("Published to %s: %s", topic, message)
            return True
        else:
            _LOGGER.error("Failed to publish to %s: %s", topic, result.rc)
            return False
