# 3i 猫砂盆 MQTT 抓包指南（Android 模拟器方案）

## 📋 前提条件

- 电脑已安装 **Android Studio** 或 **Genymotion** 模拟器
- 已安装 **Python 3** 和 **mitmproxy**
- 已下载 3i App APK（原版即可，不需要修改）

---

## 🚀 步骤概览

1. 启动 Android 模拟器
2. 安装 mitmproxy CA 证书为系统证书
3. 设置模拟器代理指向 mitmproxy
4. 安装并打开 3i App
5. 自动捕获 MQTT 凭证

---

## 1️⃣ 安装 mitmproxy

```bash
# 安装 mitmproxy
pip install mitmproxy

# 或者下载预编译版本
# https://github.com/mitmproxy/mitmproxy/releases
```

---

## 2️⃣ 启动 mitmproxy

```bash
# 先启动一次 mitmproxy 生成证书
mitmdump --listen-port 8080 &
sleep 2
kill %1

# 证书位置
ls ~/.mitmproxy/
# mitmproxy-ca-cert.pem  ← 这个是我们需要的
```

---

## 3️⃣ 启动 Android 模拟器

### 方案 A：Android Studio (AVD)

```bash
# 启动 AVD Manager
# 选择一个系统镜像（推荐 API 30 或 31，兼容性好）
# 启动模拟器
emulator -avd <your_avd_name> &
```

### 方案 B：Genymotion

```bash
# 启动 Genymotion 并创建一个虚拟设备
# 推荐：Google Pixel 3a, API 30
```

---

## 4️⃣ 安装 CA 证书为系统证书（关键步骤）

模拟器自带 root 权限，可以直接把用户证书升级为系统证书：

```bash
# 等待模拟器启动完成
adb wait-for-device

# 获取 root 权限
adb root
sleep 2

# 重挂载 /system 为可写
adb remount
sleep 2

# 计算证书文件名（OpenSSL hash）
CERT_HASH=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
echo "证书 hash: $CERT_HASH"

# 转换证书为 Android 系统证书格式
openssl x509 -inform PEM -text -in ~/.mitmproxy/mitmproxy-ca-cert.pem -out /tmp/${CERT_HASH}.0

# 推送到系统证书目录
adb push /tmp/${CERT_HASH}.0 /system/etc/security/cacerts/
adb shell chmod 644 /system/etc/security/cacerts/${CERT_HASH}.0

# 验证证书已安装
adb shell ls -la /system/etc/security/cacerts/${CERT_HASH}.0

echo "✅ CA 证书已安装为系统证书！"
```

### 一键脚本

创建文件 `install_cert.sh`：

```bash
#!/bin/bash
set -e

CERT_FILE="$HOME/.mitmproxy/mitmproxy-ca-cert.pem"

if [ ! -f "$CERT_FILE" ]; then
    echo "❌ 未找到 mitmproxy 证书，请先启动一次 mitmproxy"
    echo "   运行: mitmdump --listen-port 8080 &"
    exit 1
fi

echo "📱 获取模拟器 root 权限..."
adb root
sleep 2

echo "📂 挂载 /system 为可写..."
adb remount
sleep 2

echo "🔐 计算证书 hash..."
CERT_HASH=$(openssl x509 -inform PEM -subject_hash_old -in "$CERT_FILE" | head -1)
echo "   Hash: $CERT_HASH"

echo "📝 转换证书格式..."
openssl x509 -inform PEM -text -in "$CERT_FILE" -out "/tmp/${CERT_HASH}.0"

echo "📲 推送证书到系统目录..."
adb push "/tmp/${CERT_HASH}.0" /system/etc/security/cacerts/
adb shell chmod 644 /system/etc/security/cacerts/${CERT_HASH}.0

echo "✅ 证书安装完成！"
echo "   位置: /system/etc/security/cacerts/${CERT_HASH}.0"
```

运行：
```bash
chmod +x install_cert.sh
./install_cert.sh
```

---

## 5️⃣ 设置模拟器代理

### 方法 A：通过 ADB 命令（推荐）

```bash
# 获取电脑本机 IP
LOCAL_IP=$(ip addr show | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | cut -d/ -f1 | head -1)
echo "本机 IP: $LOCAL_IP"

# 设置模拟器代理
adb shell settings put global http_proxy ${LOCAL_IP}:8080

# 验证代理设置
adb shell settings get global http_proxy
```

### 方法 B：通过模拟器 WiFi 设置

1. 打开模拟器 设置 → WLAN
2. 长按当前网络 → 修改网络
3. 代理 → 手动
4. 主机名：`<电脑IP>`，端口：`8080`

---

## 6️⃣ 安装 3i App

```bash
# 从手机导出 APK，或者从应用商店下载
# 如果已有 APK 文件：
adb install /path/to/3i-app.apk
```

---

## 7️⃣ 启动抓包

### 创建抓包脚本 `capture_3i.py`

```python
#!/usr/bin/env python3
"""
3i 猫砂盆 MQTT 凭证自动捕获脚本
用法: mitmdump -s capture_3i.py
"""
import json
from mitmproxy import http

# 目标域名
TARGETS = [
    "3irobotix.net",
    "piceaiot.com", 
    "3itech.com",
    "sd-rtn.com",
]

# 凭证关键词
KEYS = [
    "productKey", "product_key",
    "deviceName", "device_name",
    "deviceSecret", "device_secret",
    "iotId", "iot_id",
]

found = {}

def response(flow: http.HTTPFlow):
    host = flow.request.pretty_host
    
    if not any(t in host for t in TARGETS):
        return
    
    if not flow.response or not flow.response.content:
        return
    
    print(f"\n{'='*60}")
    print(f"[{host}] {flow.request.method} {flow.request.pretty_url}")
    
    # 打印请求头
    for k, v in flow.request.headers.items():
        if any(kw in k.lower() for kw in ["auth", "token", "sign"]):
            print(f"  Header: {k} = {v[:100]}")
    
    # 打印请求体
    if flow.request.content:
        try:
            req = json.loads(flow.request.content)
            print(f"  Request: {json.dumps(req, indent=2, ensure_ascii=False)[:500]}")
            search(req)
        except:
            pass
    
    # 打印响应体
    try:
        resp = json.loads(flow.response.content)
        print(f"  Response: {json.dumps(resp, indent=2, ensure_ascii=False)[:1000]}")
        search(resp)
    except:
        pass
    
    print(f"{'='*60}")


def search(obj, path=""):
    global found
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if any(kw.lower() in k.lower() for kw in KEYS):
                print(f"  🔑 FOUND: {p} = {v}")
                found[k] = str(v)
                with open("/tmp/3i_credentials.json", "w") as f:
                    json.dump(found, f, indent=2)
            search(v, p)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            search(item, f"{path}[{i}]")


def request(flow: http.HTTPFlow):
    """也捕获 MQTT CONNECT 包（如果走 HTTP）"""
    host = flow.request.pretty_host
    
    if not any(t in host for t in TARGETS):
        return
    
    if flow.request.content:
        try:
            req = json.loads(flow.request.content)
            print(f"\n[REQUEST] {host}: {json.dumps(req, indent=2)[:500]}")
            search(req)
        except:
            pass
```

### 启动抓包

```bash
# 启动 mitmproxy 并加载抓包脚本
mitmdump --listen-port 8080 -s capture_3i.py

# 输出会显示捕获的 HTTP/HTTPS 流量
# 凭证会自动保存到 /tmp/3i_credentials.json
```

---

## 8️⃣ 操作 3i App

1. 打开 3i App
2. 登录账号
3. 进入猫砂盆控制页面
4. 切换设置、查看状态
5. 观察 mitmproxy 输出

---

## 9️⃣ 提取凭证

抓包完成后，凭证会保存在 `/tmp/3i_credentials.json`：

```bash
cat /tmp/3i_credentials.json
```

期望输出：
```json
{
  "productKey": "xxxxxxxx",
  "deviceName": "xxxxxxxx", 
  "deviceSecret": "xxxxxxxxxxxxxxxxxxxxxxxx"
}
```

---

## 🔟 使用凭证配置 HACS 集成

拿到三元组后：

1. 把 `custom_components/threei_cat/` 复制到 HA
2. 安装依赖：`pip install paho-mqtt>=1.6.1`
3. 重启 HA
4. 添加集成，输入三元组
5. 观察 HA 日志验证连接

---

## ⚠️ 常见问题

### Q: 模拟器无法安装 3i App？
A: 检查模拟器 ABI 架构（arm64 vs x86_64）。某些 App 不支持 x86。尝试使用 ARM 翻译层或不同模拟器。

### Q: 证书安装后 HTTPS 仍然不解密？
A: 检查证书是否正确安装：
```bash
adb shell ls /system/etc/security/cacerts/ | grep mitmproxy
```

### Q: 3i App 检测到模拟器无法运行？
A: 尝试：
- 使用 Genymotion（更真实的设备模拟）
- 安装 MagiskHide 模块
- 修改模拟器 build.prop

### Q: 捕获不到 3irobotix 的流量？
A: 
- 确认代理设置生效
- 检查 App 是否走了其他网络通道
- 尝试在 App 中强制刷新

---

## 📁 文件清单

- `install_cert.sh` - 一键安装证书脚本
- `capture_3i.py` - 自动捕获凭证脚本
- `~/.mitmproxy/mitmproxy-ca-cert.pem` - mitmproxy CA 证书
- `/tmp/3i_credentials.json` - 捕获到的凭证（自动生成）

---

## 🎯 快速开始（一键流程）

```bash
# 1. 启动 mitmproxy 生成证书
mitmdump --listen-port 8080 &
sleep 3
kill %1

# 2. 安装证书到模拟器
./install_cert.sh

# 3. 设置模拟器代理
LOCAL_IP=$(ip addr show | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | cut -d/ -f1 | head -1)
adb shell settings put global http_proxy ${LOCAL_IP}:8080

# 4. 安装 3i App
adb install 3i-app.apk

# 5. 启动抓包
mitmdump --listen-port 8080 -s capture_3i.py

# 6. 操作 App，等待凭证自动捕获
# 7. 查看结果
cat /tmp/3i_credentials.json
```
