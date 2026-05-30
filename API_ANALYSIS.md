# 3i F1 Pro 逆向分析 - 高级功能 API

## 1. 耗材 (Consumables)

### REST API
```
POST /outer/app/productInfo/getConsumablesByProductIds
POST /app/user/getConsumablesInfoByUserId
```

### MQTT 服务
```
service.reset_consumable  (重置耗材计数)
```

### 耗材类型
- `consumable_catSand` / `consumable_catSandRemain` - 猫砂
- `consumable_package` / `consumable_package_remain` (level1/2/3) - 滤芯
- `consumable_shitBox` / `consumable_shitBox_remain` - 便盒
- `consumable_material` - 通用耗材

### 页面
- `device_consumables_page` - 耗材列表
- `device_consumables_detail_page` - 耗材详情

---

## 2. 清洁记录/报告 (Cleaning History)

### REST API
```
POST /device-shadow-service/app/data/flow/clean-record-timeline
POST /infrastructure-third/app/record/page
POST /infrastructure-third/app/share/record/page
POST /data-statistics-service/app/data/flow/eventStatistics/page
POST /app/report/runtime
```

### 记录字段
- `area` - 清洁面积
- `duration` - 清洁时长
- `cleanFinish` / `manualFinish` / `errorFinish` / `DNDFinish` - 结束方式
- `startMethod` - 启动方式 (App/Device/Order)
- `cleanMode` - 清洁模式
- `pathDensity` - 路径密度
- `taskCompletion` - 任务完成度
- `makeWaterEfficiency` / `makeWaterTotal` - 制水信息

### 本地数据库
- `device_records_db_dao` - 本地记录存储

---

## 3. 定时任务 (Schedule/Timer)

### 本地存储 + MQTT 同步
```
MQTT Topic: shortcut_instruction_task_change/post
```

### 功能
- 定时清洁列表
- 添加/编辑定时任务
- 重复规则 (每天/工作日/周末/自定义)
- 清洁模式选择 (全屋/房间/区域/快捷指令)

### 快捷指令
- `shortcut_list_manage` - 快捷指令管理
- `shortcut_ai_status_manager` - AI 清洁状态
- `get_shortcut_task_by_mapid` - 按地图获取任务
- `get_regular_clean` - 获取定时清洁

---

## 4. 地图 (Map)

### 数据格式
- **Protobuf**: `sweeper_map_protocol.pb.dart` (通过 MQTT 传输)
- **本地存储**: `device_maps_db_dao` (SQLite)

### 渲染组件 (lib_sweeper_map_plus)
- `map_controller` - 地图控制器
- `map_edit_manager` - 地图编辑管理
- `native_map_manager` - 原生地图渲染
- 20+ 渲染服务: area, carpet, charge, clean_path, furniture, wall, room 等

### 家具/物体类型
- bed, cabinet, carpet, dining_table, sofa, toilet, pet_supply
- bar_chair, shoes, socks, weight_scale, wire
- 脏污标记: liquid, shit, solid

### 地图事件
```
event/build_map_record/post
event/map_change/post
event/new_to_build_map/post
event/back_start_pose_success/post
event/new_environment/post
```

---

## 5. 服务器配置

### REST API 基础 URL
```
cn-csh5-aiot.3irobotix.net  (主服务器)
api.link.aliyun.com          (阿里云 API)
living-account.cn-shanghai.aliyuncs.com  (账号服务)
iot.piceaiot.com             (数据采集)
```

### 网络架构
- `module_common/src/config/server_config.dart` - 服务器配置
- `module_common/src/network_services/http_servers.dart` - HTTP 服务
- `module_common/src/network_services/net_mqtt_service.dart` - MQTT 服务
- `module_common/src/network_services/device_mqtt_config.dart` - MQTT 配置
