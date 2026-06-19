"""3i Smart Device 登录认证流程模块。

基于抓包结果重写 - 使用用户名+密码登录，而不是手机号+验证码。
登录流程:
  1. POST living-account.cn-shanghai.aliyuncs.com/api/prd/connect.json
     -> 获取 deviceId (用于 OpenAccount 登录)
  2. POST living-account.cn-shanghai.aliyuncs.com/api/prd/loginbyoauth.json
     -> 获取 refreshToken, sid, openId (OpenAccount 凭据)
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import time
import uuid
from typing import Any

import aiohttp

from .const import (
    API_OAUTH_CLIENT_TOKEN,
    DEFAULT_APP_ID,
    DEFAULT_APP_KEY,
    DEFAULT_OPEN_ACCOUNT_BASE,
    DEFAULT_OPEN_API_URL,
    DEFAULT_REGION_ID,
    DEFAULT_TENANT_ID,
    OA_APP_CODE,
    OA_APP_NAME,
    OA_APP_VERSION,
    OA_AREA_ID,
    OA_CLIENT_TYPE,
    OA_PHONE_REGION_CODE,
)

_LOGGER = logging.getLogger(__name__)


def _generate_uuid() -> str:
    """生成 UUID v4 字符串。"""
    return str(uuid.uuid4())


def _b64encode(text: str) -> str:
    """Base64 编码用户名（抓包发现 username header 使用 base64）。"""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _generate_trace_id() -> str:
    """生成跟踪 ID。"""
    return _generate_uuid().replace("-", "")


def _generate_nonce(length: int = 32) -> str:
    """生成随机 nonce。"""
    return secrets.token_hex(length // 2)


async def init_device(
    session: aiohttp.ClientSession,
    username: str | None = None,
    phone: str | None = None,
    region_code: str = OA_PHONE_REGION_CODE,
) -> dict[str, Any]:
    """第一步：调用 connect.json 初始化设备登录会话。

    Args:
        session: aiohttp 客户端会话
        username: 用户名/邮箱（3i App 实际用此参数）
        phone: 手机号（兼容字段，目前 3i App 主要使用邮箱登录）
        region_code: 国家代码，默认 86

    Returns:
        包含 device_id 的字典
        {"success": True, "device_id": "xxx"}
        或 {"success": False, "error": "..."}
    """
    url = f"https://{DEFAULT_OPEN_ACCOUNT_BASE}/api/prd/connect.json"
    device_id = _generate_uuid()

    # 兼容：优先使用用户名作为 loginId，抓包显示 3i 也支持 username
    login_id = username or phone or ""
    if not login_id:
        return {"success": False, "error": "用户名或手机号不能为空"}

    payload = {
        "phone": login_id,  # 兼容字段
        "phoneRegionCode": region_code,
        "areaId": OA_AREA_ID,
        "app": OA_APP_CODE,
        "deviceId": device_id,
        "appName": OA_APP_NAME,
        "appVersion": OA_APP_VERSION,
    }

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "User-Agent": "3i/1.4.1 (Android; okhttp)",
    }

    try:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            text = await resp.text()
            _LOGGER.debug("Connect response: status=%s, body=%s", resp.status, text[:500])
            try:
                data = await resp.json(content_type=None) if text else {}
            except Exception:
                # 兜底：尝试用 resp.json() 再读一次
                data = {}

            # 返回结构: {"data": {"device": {"data": {"deviceId": "..."}}}}
            actual_device_id = (
                data.get("data", {})
                .get("device", {})
                .get("data", {})
                .get("deviceId", device_id)
            )

            # 即使返回错误，仍然使用我们生成的 deviceId，
            # 因为后续 loginbyoauth.json 是无状态的
            return {
                "success": True,
                "device_id": actual_device_id or device_id,
                "raw": data,
            }
    except asyncio.TimeoutError:
        return {"success": False, "error": "连接超时"}
    except aiohttp.ClientError as e:
        _LOGGER.error("Network error in init_device: %s", e)
        return {"success": False, "error": f"网络错误: {e}"}
    except Exception as e:
        _LOGGER.exception("Unexpected error in init_device")
        return {"success": False, "error": str(e)}


async def login_with_password(
    username: str,
    password: str,
    *,
    region_code: str = OA_PHONE_REGION_CODE,
) -> dict[str, Any]:
    """使用用户名+密码登录 3i App。

    这是 3i App 实际使用的登录方式（不是手机号+验证码）。
    底层仍然走阿里云 OpenAccount 的 loginbyoauth.json 接口。

    Args:
        username: 用户名/邮箱/手机号（3i App 接受任意一种）
        password: 密码（明文）
        region_code: 国家代码，默认 86

    Returns:
        成功: {"success": True, "user_id", "refresh_token", "sid", "open_id",
               "authorization", "device_id", "username"}
        失败: {"success": False, "error": "..."}
    """
    try:
        async with aiohttp.ClientSession() as session:
            # 第一步：初始化设备，获取 deviceId
            init_result = await init_device(session, username=username, region_code=region_code)
            if not init_result.get("success"):
                return init_result

            device_id = init_result["device_id"]

            # 第二步：调用 loginbyoauth.json 用密码登录
            url = f"https://{DEFAULT_OPEN_ACCOUNT_BASE}/api/prd/loginbyoauth.json"
            payload = {
                "loginId": username,
                "mobileLocationCode": region_code,
                "password": password,
                "deviceId": device_id,
                "clientType": OA_CLIENT_TYPE,
                "appName": OA_APP_NAME,
                "appVersion": OA_APP_VERSION,
            }

            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": "3i/1.4.1 (Android; okhttp)",
            }

            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                text = await resp.text()
                _LOGGER.debug("Login response: status=%s, body=%s", resp.status, text[:500])
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return {"success": False, "error": f"响应解析失败: {text[:200]}"}

                # 检查顶层 code
                top_code = data.get("code")
                if top_code not in (200, None, "200", "0", 0):
                    msg = data.get("message") or data.get("msg") or "登录失败"
                    return {"success": False, "error": msg, "details": data}

                # 解析登录结果
                # 结构: {"data": {"data": {"loginSuccessResult": {...}}}}
                outer = data.get("data", {})
                if isinstance(outer, dict) and "data" in outer:
                    inner = outer.get("data", {})
                else:
                    inner = outer

                login_result = inner.get("loginSuccessResult", {}) if isinstance(inner, dict) else {}

                if not login_result and not inner.get("refreshToken"):
                    # 尝试从其它路径找
                    login_result = inner if isinstance(inner, dict) else {}

                refresh_token = login_result.get("refreshToken") or inner.get("refreshToken", "")
                sid = login_result.get("sid") or inner.get("sid", "")
                open_account = login_result.get("openAccount", {})
                open_id = (
                    open_account.get("openId")
                    or inner.get("openId")
                    or login_result.get("openId", "")
                )
                user_id = str(open_id) if open_id else ""

                # 错误检查
                if not refresh_token or not sid:
                    # 提取错误信息
                    err_msg = (
                        inner.get("message")
                        or login_result.get("message")
                        or data.get("message")
                        or "用户名或密码错误"
                    )
                    return {"success": False, "error": err_msg, "details": data}

                _LOGGER.info(
                    "Login successful: user_id=%s, open_id=%s",
                    user_id[:16] + "..." if user_id else "<empty>",
                    open_id[:16] + "..." if open_id else "<empty>",
                )

                return {
                    "success": True,
                    "user_id": user_id,
                    "open_id": open_id,
                    "refresh_token": refresh_token,
                    "sid": sid,
                    "device_id": device_id,
                    "username": username,
                    "raw": data,
                }
    except asyncio.TimeoutError:
        return {"success": False, "error": "登录超时，请检查网络"}
    except aiohttp.ClientError as e:
        _LOGGER.error("Network error during login: %s", e)
        return {"success": False, "error": f"网络错误: {e}"}
    except Exception as e:
        _LOGGER.exception("Unexpected error in login_with_password")
        return {"success": False, "error": str(e)}


async def refresh_user_token(refresh_token: str) -> dict[str, Any]:
    """使用 refresh_token 刷新用户令牌。

    POST https://living-account.cn-shanghai.aliyuncs.com/api/prd/refresh.json

    Args:
        refresh_token: 上次登录获得的 refresh_token

    Returns:
        {"success": True, "refresh_token", "sid", ...}
        或 {"success": False, "error": "..."}
    """
    if not refresh_token:
        return {"success": False, "error": "refresh_token 为空"}

    url = f"https://{DEFAULT_OPEN_ACCOUNT_BASE}/api/prd/refresh.json"
    payload = {"refreshToken": refresh_token}

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "User-Agent": "3i/1.4.1 (Android; okhttp)",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                text = await resp.text()
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return {"success": False, "error": f"响应解析失败: {text[:200]}"}

                # 解析结构
                outer = data.get("data", {})
                if isinstance(outer, dict) and "data" in outer:
                    inner = outer.get("data", {})
                else:
                    inner = outer

                new_refresh = inner.get("refreshToken", "")
                new_sid = inner.get("sid", "")
                new_open_id = inner.get("openId") or (
                    inner.get("openAccount", {}).get("openId") if isinstance(inner, dict) else ""
                )

                if not new_refresh:
                    return {"success": False, "error": "刷新失败：响应无 refreshToken", "details": data}

                return {
                    "success": True,
                    "refresh_token": new_refresh,
                    "sid": new_sid,
                    "open_id": str(new_open_id) if new_open_id else "",
                    "raw": data,
                }
    except Exception as e:
        _LOGGER.exception("refresh_user_token failed")
        return {"success": False, "error": str(e)}


async def get_client_token(app_id: str = DEFAULT_APP_ID, app_key: str = DEFAULT_APP_KEY) -> dict[str, Any]:
    """获取 3i App 的 clientToken（OAuth 客户端令牌）。

    POST https://cn-api-aiot.3irobotix.net/open-auth-service/oauth/clientToken
    Body: {"appId": ..., "appKey": ...}

    Returns:
        {"success": True, "client_token": "..."}
        或 {"success": False, "error": "..."}
    """
    url = f"https://{DEFAULT_OPEN_API_URL}{API_OAUTH_CLIENT_TOKEN}"
    payload = {"appId": app_id, "appKey": app_key}

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "3i/1.4.1 (Android; okhttp)",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                text = await resp.text()
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return {"success": False, "error": f"响应解析失败: {text[:200]}"}

                # 解析结构（不同 API 字段名不同）
                client_token = (
                    data.get("data", {}).get("clientToken")
                    or data.get("data", {}).get("accessToken")
                    or data.get("clientToken")
                    or data.get("accessToken")
                    or ""
                )

                if not client_token:
                    return {"success": False, "error": "未获取到 clientToken", "details": data}

                return {"success": True, "client_token": client_token, "raw": data}
    except Exception as e:
        _LOGGER.exception("get_client_token failed")
        return {"success": False, "error": str(e)}


# ========================================================================
# 兼容旧接口（保留旧函数名以防有引用）
# ========================================================================

async def get_user_token(username: str, password: str) -> dict[str, Any]:
    """兼容旧版接口 - 调用 login_with_password。

    返回结果包含 iotToken 字段以便向后兼容。
    """
    result = await login_with_password(username, password)
    if result.get("success"):
        # 旧的 iot_token 字段其实是 OpenAccount 的 refresh_token/sid 组合
        result["iot_token"] = result.get("sid", "")
        result["identity_id"] = result.get("user_id", "")
        result["jwt_token"] = result.get("refresh_token", "")
    return result


async def send_verify_code(phone: str, region_code: str = "86") -> dict[str, Any]:
    """兼容旧接口 - 实际上 3i App 不需要验证码登录。

    此函数仅生成 deviceId 而不发送验证码。
    """
    async with aiohttp.ClientSession() as session:
        return await init_device(session, phone=phone, region_code=region_code)


async def login_with_code(
    phone: str,
    code: str,
    device_id: str,
    region_code: str = "86",
) -> dict[str, Any]:
    """兼容旧接口 - 实际不再支持。

    3i App 使用密码登录，不需要验证码。
    """
    return {
        "success": False,
        "error": "3i App 不再支持验证码登录，请使用用户名+密码登录",
    }
