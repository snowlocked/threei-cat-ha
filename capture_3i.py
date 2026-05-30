#!/usr/bin/env python3
"""
3i 猫砂盆 MQTT 凭证自动捕获脚本
用法: mitmdump --listen-port 8080 -s capture_3i.py
"""
import json
import time
from mitmproxy import http

# 目标域名
TARGETS = [
    "3irobotix.net",
    "piceaiot.com",
    "3itech.com",
    "aliyuncs.com",
    "aliyun.com",
    "sd-rtn.com",
    "xiaomi.com",
    "iot.com",
]

# 凭证关键词
KEYS = [
    "productKey", "product_key",
    "deviceName", "device_name",
    "deviceSecret", "device_secret",
    "iotId", "iot_id",
    "mqttHost", "mqtt_host",
    "mqttPort", "mqtt_port",
    "accessKey", "access_key",
    "accessToken", "access_token",
    "refreshToken", "refresh_token",
    "userId", "user_id",
    "iotToken", "iot_token",
]

found = {}
all_requests = []

def response(flow: http.HTTPFlow):
    host = flow.request.pretty_host
    
    # Log ALL traffic for debugging
    ts = time.strftime("%H:%M:%S")
    
    if any(t in host for t in TARGETS):
        print(f"\n{'='*80}")
        print(f"[{ts}] 🎯 [{host}] {flow.request.method} {flow.request.pretty_url}")
        
        # Print auth headers
        for k, v in flow.request.headers.items():
            if any(kw in k.lower() for kw in ["auth", "token", "sign", "cookie"]):
                print(f"  Header: {k} = {v[:200]}")
        
        # Print request body
        if flow.request.content:
            try:
                req = json.loads(flow.request.content)
                req_str = json.dumps(req, indent=2, ensure_ascii=False)
                print(f"  📤 Request:\n{req_str[:2000]}")
                search_keys(req)
            except:
                ct = flow.request.headers.get("content-type", "")
                if "json" not in ct:
                    print(f"  📤 Request ({ct}): {flow.request.content[:500]}")
        
        # Print response
        if flow.response and flow.response.content:
            try:
                resp = json.loads(flow.response.content)
                resp_str = json.dumps(resp, indent=2, ensure_ascii=False)
                print(f"  📥 Response:\n{resp_str[:3000]}")
                search_keys(resp)
                
                # Save full response for analysis
                entry = {
                    "time": ts,
                    "host": host,
                    "url": flow.request.pretty_url,
                    "method": flow.request.method,
                    "response": resp,
                }
                all_requests.append(entry)
                with open("/tmp/3i_all_requests.json", "w") as f:
                    json.dump(all_requests, f, indent=2, ensure_ascii=False)
                    
            except:
                pass
        
        print(f"{'='*80}")
    else:
        # Log non-target traffic briefly
        if flow.response:
            print(f"[{ts}] {host} {flow.request.method} {flow.response.status_code}")


def search_keys(obj, path=""):
    """Recursively search for credential keys."""
    global found
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if any(kw.lower() in k.lower() for kw in KEYS):
                if v and str(v).strip():
                    print(f"  🔑 FOUND: {p} = {v}")
                    found[k] = str(v)
                    with open("/tmp/3i_credentials.json", "w") as f:
                        json.dump(found, f, indent=2, ensure_ascii=False)
            search_keys(v, p)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            search_keys(item, f"{path}[{i}]")


def request(flow: http.HTTPFlow):
    """Capture request-side data too."""
    host = flow.request.pretty_host
    
    if not any(t in host for t in TARGETS):
        return
    
    if flow.request.content:
        try:
            req = json.loads(flow.request.content)
            search_keys(req)
        except:
            pass
