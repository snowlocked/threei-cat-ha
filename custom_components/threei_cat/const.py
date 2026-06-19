"""Constants for the 3i Smart Device (3i 猫砂盆) integration.

Based on packet capture analysis of the official 3i Android app.
3i 设备集成常量 - 基于对官方 3i Android App 的抓包分析。
"""
from __future__ import annotations

# 集成域名
DOMAIN = "threei_cat"
MANUFACTURER = "3irobotix"

# ========================================================================
# 默认服务器（中国区，基于抓包结果）
# ========================================================================

# 阿里云 OpenAccount 登录服务（中国上海）
DEFAULT_OPEN_ACCOUNT_BASE = "living-account.cn-shanghai.aliyuncs.com"

# 3i 主 CDN API（中国区主用）
DEFAULT_API_BASE_URL = "cn-cdnappaiot.3itech.com"
DEFAULT_CDN_URL = "cn-cdnappaiot.3itech.com"

# 3i App API（备用）
DEFAULT_APP_API_URL = "cn-appaiot.3irobotix.net"

# 3i Open OAuth API（获取 clientToken）
DEFAULT_OPEN_API_URL = "cn-api-aiot.3irobotix.net"

# MQTT Broker（App 与设备通信的代理中继，自签名证书）
DEFAULT_MQTT_ENDPOINT = "cn-mqttaiot.3irobotix.net"
DEFAULT_MQTT_PORT = 8883

# 埋点/数据分析服务器
DEFAULT_BIGDATA_URL = "bigdata-aiot.piceaiot.com"

# ========================================================================
# 应用凭证（来自抓包）
# ========================================================================

DEFAULT_TENANT_ID = "1528911334443982848"  # 3irobotix 租户
DEFAULT_APP_ID = "1560565274212143104"
DEFAULT_APP_KEY = "6da7aec718724ed3"
DEFAULT_REGION_ID = 15  # 中国

# 阿里云 OpenAccount 客户端参数
OA_APP_VERSION = "1.4.1"
OA_APP_NAME = "3i"
OA_CLIENT_TYPE = "PHONE"
OA_AREA_ID = "cn"
OA_PHONE_REGION_CODE = "86"
OA_APP_CODE = "6"

# ========================================================================
# HTTP 请求相关
# ========================================================================

DEFAULT_TIMEOUT = 15  # 秒
DEFAULT_LANGUAGE = "zh"
DEFAULT_USER_AGENT = "3i/1.4.1 (Android; okhttp)"

# 轮询间隔
DEFAULT_SCAN_INTERVAL = 30  # 秒 - 设备状态轮询间隔
DEFAULT_RECORDS_SCAN_INTERVAL = 300  # 秒 - 清洁/制水记录刷新间隔

# ========================================================================
# API 路径（不带域名）
# ========================================================================

# OpenAccount 登录 API
API_OA_CONNECT = "/api/prd/connect.json"
API_OA_LOGIN_BY_OAUTH = "/api/prd/loginbyoauth.json"
API_OA_REFRESH = "/api/prd/refresh.json"

# 3i 开放 API
API_OAUTH_CLIENT_TOKEN = "/open-auth-service/oauth/clientToken"
API_OAUTH_USER_AUTH_CODE = "/open-auth-service/user/auth/code"

# 设备服务
API_DEVICE_BIND_LIST = "/device-service/app/bind/listByUserId"
API_DEVICE_SHADOW = "/device-service/app/device/shadow"
API_DEVICE_CONTROL = "/device-service/app/control"
API_DEVICE_GET = "/device-service/app/device/get"
API_DEVICE_PROPERTY_GET = "/device-service/app/device/property/get"
API_DEVICE_PROPERTY_SET = "/device-service/app/device/property/set"
API_DEVICE_SHARE_LIST = "/device-service/app/device/share/list"

# 用户中心
API_USER_PROFILE = "/user-center/app/user/profile"

# 产品信息
API_PRODUCT_INFO = "/product-service/outer/app/productInfo"
API_PRODUCT_CONSUMABLES = "/product-service/outer/app/productInfo/getConsumablesByProductIds"

# 基础设施
API_CLEAN_RECORD_PAGE = "/infrastructure-third/app/record/page"
API_SHARE_RECORD_PAGE = "/infrastructure-third/app/share/record/page"

# 数据统计
API_EVENT_STATISTICS_PAGE = "/data-statistics-service/app/data/flow/eventStatistics/page"

# OSS 存储
API_OSS_GET_ACCESS_URL = "/storage-management/storage/oss/getAccessUrl"

# 固件升级
API_UPGRADE_TRY = "/upgrade-service/app/tryUpgrade"

# 内容服务
API_POLICY = "/content-service/app/policy"

# ========================================================================
# 数据统计事件标识符（用于 eventStatistics API）
# ========================================================================

EVENT_IDENTIFIER_CLEAN_RECORD = "clean_record"
EVENT_IDENTIFIER_WATER_MAKE = "water_make"
EVENT_IDENTIFIER_DEODORIZE = "deodorize"

# ========================================================================
# 配置项键名
# ========================================================================

# 用户凭据
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PHONE_REGION = "phone_region"

# 令牌相关
CONF_JWT_TOKEN = "jwt_token"
CONF_AUTHORIZATION = "authorization"  # 3i App API 使用的 JWT
CONF_REFRESH_TOKEN = "refresh_token"
CONF_OPEN_ID = "open_id"
CONF_SID = "sid"
CONF_USER_ID = "user_id"
CONF_CLIENT_TOKEN = "client_token"
CONF_IDENTITY_ID = "identity_id"
CONF_IOT_TOKEN = "iot_token"

# 设备选择
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_SN = "device_sn"
CONF_SELECTED_DEVICES = "selected_devices"

# 服务器配置
CONF_TENANT_ID = "tenant_id"
CONF_APP_ID = "app_id"
CONF_APP_KEY = "app_key"
CONF_API_BASE_URL = "api_base_url"
CONF_CDN_URL = "cdn_url"
CONF_OPEN_API_URL = "open_api_url"
CONF_MQTT_ENDPOINT = "mqtt_endpoint"
CONF_MQTT_PORT = "mqtt_port"
CONF_REGION_ID = "region_id"

# 手动配置（备选）
CONF_MANUAL_MODE = "manual_mode"

# 登录方法
LOGIN_METHOD_PASSWORD = "password"
LOGIN_METHOD_MANUAL = "manual"

# ========================================================================
# 设备状态属性键名（设备属性名在不同型号/固件下可能略有差异）
# ========================================================================

# 电源/电池
PROP_BATTERY = "battery"
PROP_BATTERY_LEVEL = "batteryLevel"
PROP_CHARGING = "charging"
PROP_CHARGE_STATUS = "chargeStatus"
PROP_POWER = "power"

# 设备状态
PROP_ONLINE = "online"
PROP_ONLINE_STATUS = "onlineStatus"
PROP_WORK_STATUS = "workStatus"
PROP_WORK_MODE = "workMode"
PROP_WORK_MODE_LEGACY = "work_mode"

# 清洁相关
PROP_CLEAN_STATUS = "cleanStatus"
PROP_CLEAN_STATUS_LEGACY = "clean_status"
PROP_CLEAN_MODE = "cleanMode"
PROP_AUTO_CLEAN = "autoClean"
PROP_AUTO_CLEAN_LEGACY = "auto_clean"
PROP_DEODORIZE = "deodorize"
PROP_DEODORIZE_LEVEL = "deodorizeLevel"

# 集便箱/垃圾
PROP_BIN_FULL = "binFull"
PROP_BIN_FULL_LEGACY = "bin_full"
PROP_BAG_FULL = "bagFull"
PROP_DEODORIZE_STATUS = "deodorizeStatus"

# 猫相关
PROP_CAT_WEIGHT = "catWeight"
PROP_LAST_CAT_WEIGHT = "lastCatWeight"
PROP_CAT_IN_BOX = "catInBox"

# 固件
PROP_FIRMWARE_CODE = "firmwareCode"
PROP_FIRMWARE_VERSION = "firmwareVersion"
PROP_MCU_VERSION = "mcuVersion"
PROP_MCU_VERSION_CODE = "mcuVersionCode"
PROP_MCU_VERSION_CODE_LEGACY = "mcu_version_code"
PROP_SOFTWARE_VERSION = "softwareVersion"
PROP_HARDWARE_VERSION = "hardwareVersion"

# 设备开关
PROP_CHILD_LOCK = "childLock"
PROP_DEVICE_LIGHT = "deviceLight"
PROP_NIGHT_LIGHT = "nightLight"
PROP_POWER_SAVING = "powerSaving"
PROP_AUTO_POWER_OFF = "autoPowerOff"

# 水相关（F1 Pro 制水功能）
PROP_WATER_LEVEL = "waterLevel"
PROP_WATER_LOW = "waterLow"
PROP_WATER_EMPTY = "waterEmpty"
PROP_WATER_MAKE_STATUS = "waterMakeStatus"

# 错误/警告
PROP_ERROR_CODE = "errorCode"
PROP_ERROR_MSG = "errorMsg"
PROP_WARNING = "warning"

# ========================================================================
# 设备工作模式
# ========================================================================

WORK_MODES = {
    0: "Manual",
    1: "Auto",
    2: "Smart",
    3: "Recharge",
    4: "Max",
}

# 反向映射
WORK_MODE_TO_INT = {v: k for k, v in WORK_MODES.items()}

# ========================================================================
# 清洁状态
# ========================================================================

CLEAN_STATUS = {
    0: "Idle",
    1: "Running",
    2: "Paused",
    3: "Error",
    4: "Completed",
    5: "Returning",
    6: "Charging",
    7: "Sleeping",
    8: "Cleaning",
}

# ========================================================================
# 除臭档位
# ========================================================================

DEODORIZE_LEVELS = {
    0: "Off",
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Auto",
}

DEODORIZE_LEVEL_TO_INT = {v: k for k, v in DEODORIZE_LEVELS.items()}

# ========================================================================
# 耗材类型与显示名
# ========================================================================

# 猫砂盆专用耗材
CONSUMABLE_CAT_SAND = "consumable_catSand"
CONSUMABLE_DEODORIZE = "consumable_deodorize"
CONSUMABLE_BAG = "consumable_bag"
CONSUMABLE_FILTER = "consumable_filter"
CONSUMABLE_MATERIAL = "consumable_material"
CONSUMABLE_SHIT_BOX = "consumable_shitBox"
CONSUMABLE_WATER_FILTER = "consumable_waterFilter"
CONSUMABLE_WATER_MATERIAL = "consumable_waterMaterial"
CONSUMABLE_UV_LAMP = "consumable_uvLamp"

CONSUMABLE_NAMES = {
    CONSUMABLE_CAT_SAND: "Cat Sand",
    CONSUMABLE_DEODORIZE: "Deodorize Cartridge",
    CONSUMABLE_BAG: "Waste Bag",
    CONSUMABLE_FILTER: "Filter",
    CONSUMABLE_MATERIAL: "Material",
    CONSUMABLE_SHIT_BOX: "Shit Box",
    CONSUMABLE_WATER_FILTER: "Water Filter",
    CONSUMABLE_WATER_MATERIAL: "Water Material",
    CONSUMABLE_UV_LAMP: "UV Lamp",
}

CONSUMABLE_NAMES_CN = {
    CONSUMABLE_CAT_SAND: "猫砂",
    CONSUMABLE_DEODORIZE: "除臭剂",
    CONSUMABLE_BAG: "垃圾袋",
    CONSUMABLE_FILTER: "滤芯",
    CONSUMABLE_MATERIAL: "耗材包",
    CONSUMABLE_SHIT_BOX: "集便箱",
    CONSUMABLE_WATER_FILTER: "水滤芯",
    CONSUMABLE_WATER_MATERIAL: "制水耗材",
    CONSUMABLE_UV_LAMP: "UV 灯",
}

# 默认耗材寿命（小时）
DEFAULT_CONSUMABLE_LIFESPANS = {
    CONSUMABLE_CAT_SAND: 720,
    CONSUMABLE_DEODORIZE: 360,
    CONSUMABLE_BAG: 240,
    CONSUMABLE_FILTER: 720,
    CONSUMABLE_MATERIAL: 720,
    CONSUMABLE_SHIT_BOX: 1440,
    CONSUMABLE_WATER_FILTER: 720,
    CONSUMABLE_WATER_MATERIAL: 720,
    CONSUMABLE_UV_LAMP: 8760,
}

# ========================================================================
# 设备型号（基于抓包获得）
# ========================================================================

DEVICE_MODEL_F1_PRO = "3irobotix.F1Pro"
DEVICE_MODEL_DEFAULT = "F1 Pro"

# ========================================================================
# 默认扫描间隔
# ========================================================================

SCAN_INTERVAL_SECONDS = 30
TOKEN_REFRESH_MARGIN = 300  # 提前 5 分钟刷新令牌

# ========================================================================
# 清洁记录字段
# ========================================================================

CLEAN_RECORD_AREA = "area"
CLEAN_RECORD_DURATION = "duration"
CLEAN_RECORD_FINISH_TIME = "finishTime"
CLEAN_RECORD_START_TIME = "startTime"
CLEAN_RECORD_CLEAN_FINISH = "cleanFinish"
CLEAN_RECORD_ERROR_FINISH = "errorFinish"
CLEAN_RECORD_MANUAL_FINISH = "manualFinish"
CLEAN_RECORD_STATUS = "status"
CLEAN_RECORD_MODE = "mode"

# 制水记录字段
WATER_RECORD_VOLUME = "volume"
WATER_RECORD_DURATION = "duration"
WATER_RECORD_TIME = "time"
WATER_RECORD_TDS = "tds"
