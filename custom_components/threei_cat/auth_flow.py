"""Aliyun OpenAccount login flow for 3i Smart Device."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# API Endpoints
API_CONNECT = "https://sdk.openaccount.aliyun.com/api/prd/connect.json"
API_LOGIN = "https://living-account.cn-shanghai.aliyuncs.com/api/prd/loginbyoauth.json"
API_REGION_GET = "https://api.link.aliyun.com/living/account/region/get"
API_CREATE_SESSION = "https://api.link.aliyun.com/account/createSessionByAuthCode"

DEFAULT_TENANT_ID = "1528911334443982848"


async def send_verify_code(phone: str, region_code: str = "86") -> dict[str, Any]:
    """Initialize device connection (no verification code sent here).

    The actual verification code is sent by the Aliyun OpenAccount SDK
    which uses a different flow (phone number auth service).
    We just need to get a deviceId here.

    Returns dict with deviceId on success.
    """
    device_id = str(uuid.uuid4())

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                API_CONNECT,
                json={
                    "phone": phone,
                    "phoneRegionCode": region_code,
                    "areaId": "cn",
                    "app": "6",
                    "deviceId": device_id,
                },
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                _LOGGER.debug("Connect response: %s", data)

                actual_device_id = (
                    data.get("data", {})
                    .get("device", {})
                    .get("data", {})
                    .get("deviceId", "")
                )

                if actual_device_id:
                    return {
                        "success": True,
                        "device_id": actual_device_id,
                    }

                # Check if there's an error message
                error_msg = (
                    data.get("data", {})
                    .get("device", {})
                    .get("message", "Unknown error")
                )
                return {"success": False, "error": error_msg, "details": data}

    except aiohttp.ClientError as e:
        _LOGGER.error("Network error: %s", e)
        return {"success": False, "error": f"Network error: {e}"}
    except Exception as e:
        _LOGGER.exception("Unexpected error in send_verify_code")
        return {"success": False, "error": str(e)}


async def login_with_code(
    phone: str,
    code: str,
    device_id: str,
    region_code: str = "86",
) -> dict[str, Any]:
    """Login with verification code.

    Returns dict with tokens on success.
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Login with code
            async with session.post(
                API_LOGIN,
                json={
                    "loginId": phone,
                    "mobileLocationCode": region_code,
                    "verifyCode": code,
                    "deviceId": device_id,
                    "clientType": "PHONE",
                },
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                login_data = await resp.json()
                _LOGGER.debug("Login response: %s", login_data)

                login_result = (
                    login_data.get("data", {})
                    .get("data", {})
                    .get("loginSuccessResult", {})
                )
                if not login_result:
                    error_msg = (
                        login_data.get("data", {})
                        .get("data", {})
                        .get("message", "Login failed")
                    )
                    return {"success": False, "error": error_msg, "details": login_data}

                open_account = login_result.get("openAccount", {})
                refresh_token = login_result.get("refreshToken", "")
                sid = login_result.get("sid", "")
                user_id = open_account.get("openId", "")

            # Step 2: Get region info
            async with session.post(
                API_REGION_GET,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                region_data = await resp.json()
                region_info = region_data.get("data", {})
                mqtt_endpoint = region_info.get(
                    "mqttEndpoint",
                    "public.iot-as-mqtt.cn-shanghai.aliyuncs.com:1883",
                )

            # Step 3: Create session
            async with session.post(
                API_CREATE_SESSION,
                json={"authCode": sid, "identityId": ""},
                headers={
                    "Content-Type": "application/json",
                    "x-ca-request-id": str(uuid.uuid4()),
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                session_data = await resp.json()
                session_info = session_data.get("data", {})
                identity_id = session_info.get("identityId", "")
                iot_token = session_info.get("iotToken", "")
                iot_refresh_token = session_info.get("refreshToken", "")

                if not iot_token:
                    return {
                        "success": False,
                        "error": "Failed to get IoT token",
                        "details": session_data,
                    }

            # Parse MQTT endpoint
            if ":" in mqtt_endpoint:
                host, port = mqtt_endpoint.rsplit(":", 1)
                port = int(port)
            else:
                host = mqtt_endpoint
                port = 1883

            return {
                "success": True,
                "iot_token": iot_token,
                "refresh_token": iot_refresh_token,
                "identity_id": identity_id,
                "jwt_token": refresh_token,
                "tenant_id": DEFAULT_TENANT_ID,
                "mqtt_endpoint": host,
                "mqtt_port": port,
                "user_id": user_id,
            }

    except aiohttp.ClientError as e:
        _LOGGER.error("Network error during login: %s", e)
        return {"success": False, "error": f"Network error: {e}"}
    except Exception as e:
        _LOGGER.exception("Unexpected error in login_with_code")
        return {"success": False, "error": str(e)}
