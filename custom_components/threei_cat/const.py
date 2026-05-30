"""Constants for the 3i Smart Device integration."""

DOMAIN = "threei_cat"

# MQTT defaults
DEFAULT_MQTT_ENDPOINT = "public.iot-as-mqtt.cn-shanghai.aliyuncs.com"
DEFAULT_MQTT_PORT = 1883
KEEPALIVE = 65

# MQTT Topics
TOPIC_DOWN_PROPERTIES = "/app/down/thing/properties"
TOPIC_DOWN_EVENTS = "/app/down/thing/events"
TOPIC_DOWN_STATUS = "/app/down/thing/status"
TOPIC_UP_SET = "thing/service/property/set"
TOPIC_UP_GET = "thing/service/property/get"

# Token refresh constants
IOT_TOKEN_LIFETIME = 72000  # 20 hours
REFRESH_TOKEN_LIFETIME = 720000  # ~8.3 days for IoT
REFRESH_MARGIN = 300  # Refresh 5 minutes before expiry

# Config flow keys
CONF_IOT_TOKEN = "iot_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_IDENTITY_ID = "identity_id"
CONF_MQTT_ENDPOINT = "mqtt_endpoint"
CONF_MQTT_PORT = "mqtt_port"

# API endpoints
API_REFRESH_TOKEN_URL = "https://api.link.aliyun.com/account/refreshByRefreshToken"

# Device info
DEVICE_MANUFACTURER = "3irobotix"
DEVICE_MODEL = "F1 Pro"

# Property names
PROP_BATTERY = "battery"
PROP_CHARGING = "charging"
PROP_WORK_MODE = "work_mode"
PROP_CLEAN_STATUS = "clean_status"
PROP_CLEAN_FINISH = "cleanFinish"
PROP_WATER_LEVEL = "water_level"
PROP_SUCTION_LEVEL = "suction_level"
PROP_BIN_FULL = "bin_full"
PROP_BIN_FULL_ALT = "binFull"
PROP_DEVICE_LIGHT = "deviceLight"
PROP_CHILD_LOCK = "childLock"
PROP_FIRMWARE_CODE = "firmwareCode"
PROP_MCU_VERSION = "mcu_version_code"
PROP_AUTO_CLEAN = "autoClean"

# Work mode values
WORK_MODES = {
    0: "Quiet",
    1: "Standard",
    2: "Strong",
    3: "Custom",
    4: "Max",
}

# Water level values
WATER_LEVELS = {
    0: "Off",
    1: "Low",
    2: "Medium",
    3: "High",
}

# Suction level values
SUCTION_LEVELS = {
    0: "Off",
    1: "Low",
    2: "Medium",
    3: "High",
}

# Clean status values
CLEAN_STATUS = {
    0: "Idle",
    1: "Cleaning",
    2: "Paused",
    3: "Error",
    4: "Completed",
    5: "Returning",
    6: "Charging",
}
