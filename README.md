# 3i Smart Cat Litter Box - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Control your **3i Smart Cat Litter Box** (by 3irobotix / PiceaCorp) in Home Assistant via the Aliyun IoT MQTT protocol.

> This integration is based on reverse engineering the official `com.sc.iot.device` Android app.

## Features

- **Sensor**: Cat weight, deodorize level, firmware version, clean status
- **Binary Sensor**: Bin full warning, auto clean active
- **Switch**: Auto clean, child lock, device light, auto power off
- **Select**: Deodorize level (off/low/medium/high)
- **Button**: Start/stop clean, return to dock, OTA upgrade

## Prerequisites

You need the **Aliyun IoT device triple** (productKey, deviceName, deviceSecret).

### How to get credentials

**Option 1: Packet capture (recommended)**
1. Install the 3i app on your phone
2. Set up MITM proxy (e.g., mitmproxy, Charles)
3. Connect the device and observe MQTT traffic
4. Extract the device credentials from the MQTT CONNECT packet

**Option 2: Frida hook**
1. Root your phone or use an emulator
2. Run Frida with a hook on `MqttConfigure` class
3. Dump `productKey`, `deviceName`, `deviceSecret` at runtime

**Option 3: Aliyun IoT Platform**
1. If you have access to the Aliyun IoT console
2. Find your device under the product
3. Copy the device triple from the device detail page

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots menu → "Custom repositories"
4. Add this repository URL
5. Install "3i Smart Cat Litter Box"
6. Restart Home Assistant

### Manual

1. Copy the `custom_components/threei_cat/` folder to your HA `config/custom_components/` directory
2. Install the `paho-mqtt` Python package: `pip install paho-mqtt>=1.6.1`
3. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "3i Smart Cat Litter Box"
4. Enter your device credentials:
   - **Product Key**: Your Aliyun IoT product key
   - **Device Name**: Your device identifier
   - **Device Secret**: Your HMAC signing secret

## Architecture

```
Home Assistant                    Aliyun IoT Cloud                 Device
     │                                  │                            │
     │  MQTT (TLS 443)                  │                            │
     ├─────────────────────────────────►│                            │
     │  topic: /thing/service/          │                            │
     │         property/set             │  MQTT                      │
     │                                  ├───────────────────────────►│
     │                                  │                            │
     │                                  │  MQTT                      │
     │                                  │◄───────────────────────────┤
     │  topic: /app/down/               │  topic: /thing/event/      │
     │         thing/properties         │         property/post      │
     │◄─────────────────────────────────┤                            │
     │                                  │                            │
```

### MQTT Connection

- **Broker**: `{productKey}.iot-as-mqtt.cn-shanghai.aliyuncs.com`
- **Port**: 443 (TLS)
- **Auth**: HMAC-SHA1 signed credentials
- **Protocol**: Aliyun IoT Thing Model

### Message Format

```json
{
  "id": "123",
  "version": "1.0",
  "method": "thing.service.property.set",
  "params": {
    "property_key": "value"
  }
}
```

## Known Limitations

1. **Property names may vary** between device models/firmware versions
2. **Some properties are read-only** (e.g., cat weight, firmware version)
3. **The device triple is obtained at runtime** by the app — you need to extract it yourself
4. **No auto-discovery** — manual configuration required
5. **Cloud dependency** — requires Aliyun IoT cloud to be reachable

## Troubleshooting

### Cannot connect to MQTT broker
- Verify your device credentials are correct
- Check that your HA instance can reach `*.iot-as-mqtt.cn-shanghai.aliyuncs.com:443`
- Ensure `paho-mqtt` is installed

### Entities show "unavailable"
- The device may be offline
- Check the MQTT connection in HA logs (enable debug logging for `custom_components.threei_cat`)

### Enable debug logging
```yaml
logger:
  logs:
    custom_components.threei_cat: debug
```

## Credits

- Protocol analysis based on reverse engineering the `com.sc.iot.device` APK
- Uses Aliyun IoT Thing Model protocol
- Built with Eclipse Paho MQTT client
