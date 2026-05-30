# 3i 智能猫砂盆 MQTT 协议分析

> 基于 com.sc.iot.device APK 反编译分析
> 公司: 3irobotix / PiceaCorp
> 平台: 阿里云 IoT (Aliyun IoT Thing Model)

---

## 1. MQTT 连接参数

### Broker 地址
```
生产环境: ssl://{productKey}.iot-as-mqtt.cn-shanghai.aliyuncs.com:443
TCP 环境: tcp://{productKey}.iot-as-mqtt.cn-shanghai.aliyuncs.com:1883
ITLS 环境: tcp://{productKey}.itls.cn-shanghai.aliyuncs.com:1883
```

### 连接认证
```
协议:       MQTT v3.1.1 (Eclipse Paho)
TLS:        默认启用 (secureMode=2)
KeepAlive:  65 秒
CleanSession: true
自动重连:   true

ClientID: {deviceName}&{productKey}|securemode=2,_v={SDK_VERSION},lan=Android,os={ANDROID_VER},signmethod=hmacsha1,ext=1|

Username:   {deviceName}&{productKey}

Password:   HMAC-SHA1({deviceSecret}, 
            "clientId{clientId}deviceName{deviceName}deviceSecret{deviceSecret}productKey{productKey}")
            (按字母排序拼接后做 HMAC-SHA1，结果为 hex 编码)
```

### 凭证获取流程
```
1. 用户通过阿里云 OpenAccount SDK 登录
2. 通过 3irobotix 云 API 绑定设备 (cn-appaiot.3irobotix.net)
3. 云端返回设备三元组: productKey, deviceName, deviceSecret
4. SDK 用三元组构造 MQTT 连接参数
5. 连接阿里云 IoT Broker
```

---

## 2. Thing Model (物模型) Topic 结构

### 设备端 Topic (device -> cloud)

| Topic | 用途 |
|-------|------|
| `/sys/{productKey}/{deviceName}/thing/event/property/post` | 上报属性 |
| `/sys/{productKey}/{deviceName}/thing/event/{identifier}/post` | 上报事件 |
| `/sys/{productKey}/{deviceName}/thing/model/up_raw` | 透传上行 |
| `/sys/{productKey}/{deviceName}/thing/deviceinfo/update` | 更新设备信息 |
| `/ota/device/inform/{productKey}/{deviceName}` | OTA 通知 |

### 云端 Topic (cloud -> device)

| Topic | 用途 |
|-------|------|
| `/sys/{productKey}/{deviceName}/thing/service/property/set` | 设置属性 |
| `/sys/{productKey}/{deviceName}/thing/service/property/get` | 查询属性 |
| `/sys/{productKey}/{deviceName}/thing/service/{identifier}` | 调用服务 |
| `/sys/{productKey}/{deviceName}/thing/event/property/post_reply` | 属性上报回复 |
| `/sys/{productKey}/{deviceName}/thing/model/down_raw` | 透传下行 |

### App 下行 Topic (app push)

| Topic | 用途 |
|-------|------|
| `/app/down/thing/properties` | 属性变更通知 |
| `/app/down/thing/events` | 事件通知 |
| `/app/down/thing/status` | 状态通知 |
| `/app/down/_thing/event/notify` | 事件推送 |

---

## 3. 消息格式 (Aliyun Thing Model JSON)

### 属性上报 (property/post)
```json
{
  "id": "123",
  "version": "1.0",
  "method": "thing.event.property.post",
  "params": {
    "property_key_1": "value1",
    "property_key_2": 42
  }
}
```

### 属性设置 (service/property/set)
```json
{
  "id": "456",
  "version": "1.0",
  "method": "thing.service.property.set",
  "params": {
    "property_key": "new_value"
  }
}
```

### 服务调用 (service/{identifier})
```json
{
  "id": "789",
  "version": "1.0",
  "method": "thing.service.{identifier}",
  "params": {
    "input_param1": "value1"
  }
}
```

---

## 4. 设备属性 (Thing Model Properties)

### 从 libapp.so 提取的设备功能

#### 清洁控制
- `cleanFinish` / `cleanFinished` - 清洁完成状态
- `autoClean` / `aiAutoClean` - 自动清洁模式
- `_autoEdgeClean` - 边缘清洁
- `_aiSceneClean` - AI 场景清洁
- `_allHouseClean` - 全屋清洁
- `_areaClean` - 区域清洁
- `_chooseRoomClean` - 指定房间清洁
- `_launchQuickCLean` - 快速清洁

#### 设备状态
- `binFull` - 集尘盒满
- `deodorize_level` - 除臭等级
- `cycle_deodorize` - 循环除臭
- `catweight` / `catWeight` - 猫咪体重
- `firmwareCode` - 固件版本
- `mcu_version_code` - MCU 版本

#### 猫咪管理
- `catData_toilet_catWeight` - 如厕体重数据
- `catBind` - 猫咪绑定
- `catKind` - 猫咪品种

#### 设备设置
- `_childLockAndDeviceLight` - 童锁 + LED
- `_autoPowerOffRobot` - 自动关机
- `cleanRecordStartMethod` - 清洁启动方式

#### 清洁记录
- `cleanFinishInSeconds` - 清洁完成时间
- `deviceSetting_cleanRecord_area` - 清洁面积
- `deviceSetting_cleanRecord_duration` - 清洁时长
- `deviceSetting_cleanRecord_manualFinish` - 手动结束
- `deviceSetting_cleanRecord_errorFinish` - 错误结束
- `deviceSetting_cleanRecord_DNDFinish` - 免打扰结束
- `deviceSetting_cleanRecord_multiMode` - 多模式清洁

#### OTA 升级
- `FirmwareUpgradeEvent` - 固件升级事件
- `FirmwareUpgradeMessage` - 升级消息
- `DRDeviceOtaStatusModel` - OTA 状态

---

## 5. App MQTT 消息流程

```
初始化:
  MqttManager -> initMqttConnection -> connectMqtt
  DeviceMqttSubManager -> _subscribe -> 各 Topic

属性上报流程:
  Device -> /thing/event/property/post -> Cloud
  Cloud -> /thing/event/property/post_reply -> Device
  App 收到 /app/down/thing/properties -> _handleDevicePropertyChange

设备控制流程:
  App -> /thing/service/property/set -> Cloud -> Device
  或 App -> publishTopicStartRecharge / publishTopicStopRecharge

OTA 流程:
  App -> publishMqttOtaUpgrade -> /thing/service/ota/upgrade
  Device -> /thing/event/ota/progress -> Cloud
  App -> subscribeDeviceOtaProgress -> 监听进度
  App -> publishMqttOtaUpgradeInstallNow -> 立即安装
```

---

## 6. 3irobotix 云 API

### 服务端点
```
生产: cn-appaiot.3irobotix.net
测试: test-csh5-aiot.3irobotix.net
欧盟: eu-csh5-aiot.3irobotix.net
大数据: bigdata-aiot.piceaiot.com
```

### 关键 API
```
/device-service/app/upload/iotId        - 上传设备 IoT ID
/device-shadow-service/app/data/flow/   - 设备影子数据
/user-center/auth/aliyun/platform/phone/login - 手机号登录
```

---

## 7. HACS 集成方案

### 方案选择
由于 MQTT 凭证需要阿里云三元组 (productKey, deviceName, deviceSecret)，
而这些凭证由 3irobotix 云端管理，有两种集成方式:

**方案 A: 通过 3irobotix 云 API 获取凭证后直连 MQTT**
- 优点: 实时性好，延迟低
- 缺点: 需要逆向登录 API，凭证可能过期

**方案 B: 使用阿里云 IoT 云账号代理**
- 优点: 标准方案，稳定性好
- 缺点: 需要用户在阿里云 IoT 平台配置

**方案 C: 抓包获取 MQTT 消息格式后，用现有 MQTT broker 中转**
- 优点: 最灵活
- 缺点: 需要额外中间件

推荐方案 A，详见 hacs_integration/ 代码。
