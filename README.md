# 3i Smart Device (3i 猫砂盆) - Home Assistant 集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

> 基于对 3i 官方 Android App 的抓包分析重构的 Home Assistant 集成。
> 本集成**仅依赖 HTTP API**（不需要 MQTT），并支持用户名+密码登录。

将你的 **3i 智能猫砂盆**（3irobotix / PiceaCorp 出品）接入 Home Assistant。

## ✨ 特性

### 传感器 (Sensor)
- 电池电量
- 工作模式
- 清洁状态
- 除臭档位
- 固件版本 / MCU 版本
- 猫体重（部分型号）
- 上次清洁面积、时长、时间
- 总清洁次数
- 上次制水时间、容量
- 各种耗材寿命（猫砂、除臭剂、垃圾袋、滤芯等）

### 二进制传感器 (Binary Sensor)
- 在线状态
- 充电中
- 集便箱满
- 水量不足
- 故障状态

### 开关 (Switch)
- 自动清洁
- 童锁
- 设备灯
- 节能模式
- 除臭开关

### 选择器 (Select)
- 工作模式（手动/自动/智能/回充/强力）
- 除臭档位（关/低/中/高/自动）

### 按钮 (Button)
- 开始清洁
- 停止清洁
- 返回充电桩
- 刷新数据
- 检查固件升级

### 服务 (Service)
- `threei_cat.refresh_all` - 立即刷新所有设备

## 📋 前置要求

- Home Assistant 2024.1.0 或更高版本
- 你的 3i App 账号（用户名/邮箱 + 密码）
- 设备已通过 3i App 绑定到该账号

## 🚀 安装

### 通过 HACS（推荐）

1. 打开 HACS → Integrations
2. 点击右上角菜单 → Custom repositories
3. 添加本仓库 URL（类别选 Integration）
4. 安装 "3i Smart Device"
5. 重启 Home Assistant

### 手动安装

1. 将 `custom_components/threei_cat/` 文件夹复制到你的 HA 配置目录的 `custom_components/` 下
2. 重启 Home Assistant

## ⚙️ 配置

1. 进入 设置 → 设备与服务
2. 点击 "添加集成"
3. 搜索 "3i Smart Device"
4. 选择登录方式：
   - **用户名 + 密码**（推荐）
   - **手动输入令牌**（高级，从抓包获取）

### 方式一：用户名 + 密码

输入你在 3i App 中使用的用户名（邮箱或手机号）和密码。

> 注意：抓包发现 3i App 实际使用的是**用户名+密码登录**，而不是手机号+验证码。

### 方式二：手动输入令牌（高级）

如果你不想直接输入密码，可以从抓包（如 mitmproxy、Charles）中提取以下信息：

- `username` - 用户名
- `userId` / `openId` - 用户 ID
- `sid` - 会话 ID
- `refreshToken` - 刷新令牌

这些信息可以从抓包中请求 `living-account.cn-shanghai.aliyuncs.com/api/prd/loginbyoauth.json` 的响应中找到。

## 🏗️ 架构

```
Home Assistant                        3i Cloud API                      Device
     │                                      │                              │
     │  HTTP (HTTPS 443)                    │                              │
     ├─────────────────────────────────────►│                              │
     │  GET /device-service/app/            │                              │
     │      device/shadow                   │                              │
     │                                      │  (设备状态轮询 30s)          │
     │◄─────────────────────────────────────┤                              │
     │                                      │                              │
     │  POST /infrastructure-third/         │                              │
     │       app/record/page                │                              │
     │                                      │  (清洁/制水记录 5min)        │
     │◄─────────────────────────────────────┤                              │
```

### 服务器架构（中国区）

| 服务 | 地址 |
|------|------|
| 阿里云 OpenAccount | `living-account.cn-shanghai.aliyuncs.com` |
| 3i 主 CDN API | `cn-cdnappaiot.3itech.com` |
| 3i Open OAuth | `cn-api-aiot.3irobotix.net` |
| 3i App API | `cn-appaiot.3irobotix.net` |
| 3i MQTT Broker | `cn-mqttaiot.3irobotix.net:8883` |
| 大数据/埋点 | `bigdata-aiot.piceaiot.com` |

### 关键参数

| 参数 | 值 |
|------|------|
| appId | `1560565274212143104` |
| appKey | `6da7aec718724ed3` |
| tenantId | `1528911334443982848` (3irobotix) |
| regionId | 15 (中国) |

## ⚠️ 已知限制

### 控制功能（开关、模式选择）

由于抓包发现该设备的 `iotId` 通常为 `null`（设备未通过云端授权），
**通过云端直接控制设备的能力受限**。本集成在这种情况下：
- 读取状态：✅ 正常工作
- 写入命令：⚠️ 命令可能无法到达设备，但会被记录用于后续扩展

如果你已通过 3i App 完成了设备的云端授权（iotId 非空），
控制命令应该可以正常工作。

### MQTT 协议

抓包发现 3i App 实际上使用 MQTT (端口 8883) 与设备通信，但 **App 起到中继作用**。
设备并不直接连接到 MQTT Broker，而是通过 App 进行控制。
因此本集成**不使用 MQTT**，仅使用 HTTP API 进行状态轮询。

## 🐛 故障排查

### 登录失败

- 确认用户名和密码正确（可在 3i App 中登录验证）
- 确认网络可访问 `living-account.cn-shanghai.aliyuncs.com` 和 `cn-cdnappaiot.3itech.com`
- 启用调试日志：
  ```yaml
  logger:
    logs:
      custom_components.threei_cat: debug
  ```

### 设备不显示数据

- 检查 coordinator 日志，确认 API 调用是否成功
- 设备可能离线（检查 online 传感器）
- token 可能已过期 - 系统会自动刷新，但首次配置后需要等待

### 重新认证

如果 token 完全失效（无法自动刷新），可以：
1. 删除现有集成
2. 重新添加并登录
3. 或使用 reauth flow（HA 会自动提示）

## 📝 开发说明

### 主要抓包发现

1. **登录方式**：3i App 使用用户名+密码登录，不是手机号+验证码
2. **服务器**：3i 自有服务器 (`cn-cdnappaiot.3itech.com`)，不是阿里云 IoT
3. **设备控制**：走 HTTP API 而非 MQTT
4. **设备 iotId**：通常是 null（未通过云端授权）

### 主要 API 端点

- `POST living-account.cn-shanghai.aliyuncs.com/api/prd/loginbyoauth.json` - 登录
- `POST cn-cdnappaiot.3itech.com/device-service/app/bind/listByUserId` - 设备列表
- `POST cn-cdnappaiot.3itech.com/device-service/app/device/shadow` - 设备状态
- `POST cn-cdnappaiot.3itech.com/infrastructure-third/app/record/page` - 清洁记录
- `GET  cn-cdnappaiot.3itech.com/data-statistics-service/app/data/flow/eventStatistics/page` - 制水事件
- `POST cn-cdnappaiot.3itech.com/product-service/outer/app/productInfo/getConsumablesByProductIds` - 耗材

## 📜 许可证

MIT

## 🙏 致谢

- 基于对 3i 官方 App 的抓包分析
- 仅供个人学习研究使用
