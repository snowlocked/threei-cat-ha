"""Constants for the 3i Smart Device integration."""

DOMAIN = "threei_cat"

# Cloud REST API defaults
DEFAULT_API_BASE_URL = "cn-csh5-aiot.3irobotix.net"
CONF_API_BASE_URL = "api_base_url"
CONF_JWT_TOKEN = "jwt_token"
CONF_TENANT_ID = "tenant_id"

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
TOPIC_SCHEDULE_POST = "shortcut_instruction_task_change/post"

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
API_CONSUMABLES_URL = "https://{base_url}/outer/app/productInfo/getConsumablesByProductIds"
API_CLEAN_RECORDS_URL = "https://{base_url}/device-shadow-service/app/data/flow/clean-record-timeline"

# Device info
DEVICE_MANUFACTURER = "3irobotix"
DEVICE_MODEL = "F1 Pro"

# Consumable types
CONSUMABLE_SIDE_BRUSH = "consumable_sideBrush"
CONSUMABLE_MAIN_BRUSH = "consumable_mainBrush"
CONSUMABLE_FILTER = "consumable_filter"
CONSUMABLE_MOP = "consumable_mop"
CONSUMABLE_CAT_SAND = "consumable_catSand"
CONSUMABLE_PACKAGE_L1 = "consumable_package_level1"
CONSUMABLE_PACKAGE_L2 = "consumable_package_level2"
CONSUMABLE_PACKAGE_L3 = "consumable_package_level3"
CONSUMABLE_SHIT_BOX = "consumable_shitBox"
CONSUMABLE_MATERIAL = "consumable_material"

# Consumable display names
CONSUMABLE_NAMES = {
    CONSUMABLE_SIDE_BRUSH: "Side Brush",
    CONSUMABLE_MAIN_BRUSH: "Main Brush",
    CONSUMABLE_FILTER: "Filter",
    CONSUMABLE_MOP: "Mop",
    CONSUMABLE_CAT_SAND: "Cat Sand",
    CONSUMABLE_PACKAGE_L1: "Package Level 1",
    CONSUMABLE_PACKAGE_L2: "Package Level 2",
    CONSUMABLE_PACKAGE_L3: "Package Level 3",
    CONSUMABLE_SHIT_BOX: "Shit Box",
    CONSUMABLE_MATERIAL: "Material",
}

# Default consumable lifespans (hours)
CONSUMABLE_LIFESPANS = {
    CONSUMABLE_SIDE_BRUSH: 360,
    CONSUMABLE_MAIN_BRUSH: 500,
    CONSUMABLE_FILTER: 300,
    CONSUMABLE_MOP: 180,
    CONSUMABLE_CAT_SAND: 720,
    CONSUMABLE_SHIT_BOX: 1440,
    CONSUMABLE_MATERIAL: 720,
}

# Cleaning record fields
CLEAN_RECORD_AREA = "area"
CLEAN_RECORD_DURATION = "duration"
CLEAN_RECORD_FINISH = "cleanFinish"
CLEAN_RECORD_MANUAL_FINISH = "manualFinish"
CLEAN_RECORD_ERROR_FINISH = "errorFinish"
CLEAN_RECORD_START_METHOD = "startMethod"
CLEAN_RECORD_CLEAN_MODE = "cleanMode"
CLEAN_RECORD_COMPLETION = "taskCompletion"

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
