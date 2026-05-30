"""Aliyun OpenAccount login flow for 3i Smart Device."""
from __future__ import annotations

import logging
import uuid
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# API Endpoints
API_CONNECT = "https://sdk.openaccount.aliyun.com/api/prd/connect.json"
API_SEND_CODE = "https://sdk.openaccount.aliyun.com/api/prd/sendVerifyCode.json"
API_LOGIN = "https://living-account.cn-shanghai.aliyuncs.com/api/prd/loginbyoauth.json"
API_REGION_GET = "https://api.link.aliyun.com/living/account/region/get"
API_CREATE_SESSION = "https://api.link.aliyun.com/account/createSessionByAuthCode"

DEFAULT_TENANT_ID = "1528911334443982848"


async def send_verify_code(phone: str, region_code: str = "86") -> dict[str, Any]:
    """Send verification code to phone number.

    Returns dict with deviceId and sid on success.
    """
    device_id = str(uuid.uuid4())

    # Step 1: Get device ID
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

            if not data.get("data", {}).get("device", {}).get("data", {}).get("deviceId"):
                _LOGGER.error("Failed to get deviceId: %s", data)
                return {"error": "Failed to initialize device", "details": data}

            actual_device_id = data["data"]["device"]["data"]["deviceId"]

    # Step 2: Send verification code
    async with aiohttp.ClientSession() as session:
        async with session.post(
            API_SEND_CODE,
            json={
                "phone": phone,
                "phoneRegionCode": region_code,
                "deviceId": actual_device_id,
                "app": "6",
            },
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()
            _LOGGER.debug("Send code response: %s", data)

            # Check if code was sent successfully
            success = data.get("data", {}).get("successful", "false") == "true"
            if not success:
                # Try alternative response format
                success = data.get("data", {}).get("code") == 1

            return {
                "success": success,
                "device_id": actual_device_id,
                "response": data,
            }


async def login_with_code(
    phone: str,
    code: str,
    device_id: str,
    region_code: str = "86",
) -> dict[str, Any]:
    """Login with verification code.

    Returns dict with tokens on success.
    """
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

            login_result = login_data.get("data", {}).get("data", {}).get("loginSuccessResult", {})
            if not login_result:
                _LOGGER.error("Login failed: %s", login_data)
                return {"error": "Login failed", "details": login_data}

            open_account = login_result.get("openAccount", {})
            refresh_token = login_result.get("refreshToken", "")
            sid = login_result.get("sid", "")
            user_id = open_account.get("openId", "")
            oa_id = open_account.get("id", "")

        # Step 2: Get region info
        async with session.post(
            API_REGION_GET,
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            region_data = await resp.json()
            _LOGGER.debug("Region response: %s", region_data)

            region_info = region_data.get("data", {})
            mqtt_endpoint = region_info.get("mqttEndpoint", "public.iot-as-mqtt.cn-shanghai.aliyuncs.com:1883")
            region_id = region_info.get("regionId", "cn-shanghai")

        # Step 3: Create session to get iotToken
        async with session.post(
            API_CREATE_SESSION,
            json={
                "authCode": sid,
                "identityId": "",
            },
            headers={
                "Content-Type": "application/json",
                "x-ca-request-id": str(uuid.uuid4()),
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            session_data = await resp.json()
            _LOGGER.debug("Session response: %s", session_data)

            session_info = session_data.get("data", {})
            identity_id = session_info.get("identityId", "")
            iot_token = session_info.get("iotToken", "")
            iot_refresh_token = session_info.get("refreshToken", "")

            if not iot_token:
                _LOGGER.error("Failed to get iotToken: %s", session_data)
                return {"error": "Failed to get IoT token", "details": session_data}

        # Build JWT token (simplified - the real JWT is constructed by the app)
        # For REST API calls, we use the OpenAccount refresh token as the auth token
        jwt_token = refresh_token

        return {
            "success": True,
            "iot_token": iot_token,
            "refresh_token": iot_refresh_token,
            "identity_id": identity_id,
            "jwt_token": jwt_token,
            "tenant_id": DEFAULT_TENANT_ID,
            "mqtt_endpoint": mqtt_endpoint.split(":")[0] if ":" in mqtt_endpoint else mqtt_endpoint,
            "mqtt_port": int(mqtt_endpoint.split(":")[1]) if ":" in mqtt_endpoint else 1883,
            "user_id": user_id,
            "open_account_id": oa_id,
            "sid": sid,
        }
