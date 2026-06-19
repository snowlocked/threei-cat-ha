"""3i Smart Device App HTTP API 客户端。

基于抓包结果实现 3i App 与 cn-cdnappaiot.3itech.com 之间的所有 API。
支持以下功能：
  - 用户认证（JWT）
  - 设备列表查询
  - 设备状态查询
  - 清洁记录查询
  - 制水记录查询
  - 耗材列表
  - 用户配置
  - 固件升级

注意：所有 API 调用都使用 HTTP 轮询方式，不使用 MQTT。
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import secrets
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .auth_flow import _generate_uuid, login_with_password, refresh_user_token
from .const import (
    API_CLEAN_RECORD_PAGE,
    API_DEVICE_BIND_LIST,
    API_DEVICE_SHADOW,
    API_EVENT_STATISTICS_PAGE,
    API_OSS_GET_ACCESS_URL,
    API_PRODUCT_CONSUMABLES,
    API_PRODUCT_INFO,
    API_SHARE_RECORD_PAGE,
    API_UPGRADE_TRY,
    API_USER_PROFILE,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_AUTHORIZATION,
    CONF_CLIENT_TOKEN,
    CONF_DEVICE_ID,
    CONF_DEVICE_SN,
    CONF_JWT_TOKEN,
    CONF_OPEN_ID,
    CONF_REFRESH_TOKEN,
    CONF_SELECTED_DEVICES,
    CONF_SID,
    CONF_TENANT_ID,
    CONF_USER_ID,
    CONF_USERNAME,
    DEFAULT_APP_ID,
    DEFAULT_APP_KEY,
    DEFAULT_BIGDATA_URL,
    DEFAULT_CDN_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_REGION_ID,
    DEFAULT_TENANT_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    EVENT_IDENTIFIER_CLEAN_RECORD,
    EVENT_IDENTIFIER_WATER_MAKE,
    TOKEN_REFRESH_MARGIN,
)

_LOGGER = logging.getLogger(__name__)


# ========================================================================
# 工具函数：生成抓包中观察到的请求头
# ========================================================================

def _generate_nonce(length: int = 16) -> str:
    """生成随机 nonce（抓包中观察到的字段）。"""
    return secrets.token_hex(length // 2)


def _generate_trace_id() -> str:
    """生成 trace ID。"""
    return _generate_uuid().replace("-", "")


def _b64_username(username: str) -> str:
    """Base64 编码用户名（抓包发现 authorization 使用 base64(username)）。"""
    try:
        return base64.b64encode(username.encode("utf-8")).decode("ascii")
    except Exception:
        return ""


def _build_sign(
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    secret_key: str = DEFAULT_APP_KEY,
) -> str:
    """生成 3i API 请求签名 (MD5)。

    抓包发现签名算法:
      sign = MD5( sorted(query_params) + sorted(body_params) + secret_key )

    Returns:
        MD5 hex string
    """
    parts: list[str] = []

    if query:
        for key in sorted(query.keys()):
            value = query[key]
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True, separators=(",", ":"))
            parts.append(f"{key}={value}")

    if body:
        for key in sorted(body.keys()):
            value = body[key]
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True, separators=(",", ":"))
            parts.append(f"{key}={value}")

    parts.append(secret_key)
    raw = "&".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ========================================================================
# 3i App API 客户端
# ========================================================================

class ThreeiApiClient:
    """3i App API HTTP 客户端。

    封装所有抓包观察到的 API 调用。线程安全（asyncio 锁）。
    """

    def __init__(
        self,
        username: str,
        *,
        app_id: str = DEFAULT_APP_ID,
        app_key: str = DEFAULT_APP_KEY,
        tenant_id: str = DEFAULT_TENANT_ID,
        region_id: int = DEFAULT_REGION_ID,
        cdn_url: str = DEFAULT_CDN_URL,
        bigdata_url: str = DEFAULT_BIGDATA_URL,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """初始化 API 客户端。

        Args:
            username: 用户名（用于 JWT 中的 user 字段）
            app_id: 应用 ID
            app_key: 应用密钥（用于签名）
            tenant_id: 租户 ID
            region_id: 区域 ID
            cdn_url: CDN 基础 URL
            bigdata_url: 大数据服务 URL
            session: 可选的 aiohttp 会话
        """
        self._username = username
        self._app_id = app_id
        self._app_key = app_key
        self._tenant_id = tenant_id
        self._region_id = region_id
        self._cdn_url = cdn_url
        self._bigdata_url = bigdata_url

        # 令牌状态
        self._user_id: str = ""
        self._open_id: str = ""
        self._sid: str = ""
        self._refresh_token: str = ""
        self._client_token: str = ""
        self._authorization: str = ""  # JWT
        self._token_acquired_at: float = 0.0

        self._session: aiohttp.ClientSession | None = session
        self._owns_session = session is None
        self._lock = asyncio.Lock()

    # --------------------------------------------------------------------
    # 会话管理
    # --------------------------------------------------------------------

    async def __aenter__(self) -> "ThreeiApiClient":
        """异步上下文管理器入口。"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """异步上下文管理器出口。"""
        await self.close()

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

    async def close(self) -> None:
        """关闭客户端会话。"""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    # --------------------------------------------------------------------
    # 认证
    # --------------------------------------------------------------------

    async def async_login(self, password: str) -> dict[str, Any]:
        """使用密码登录获取令牌。

        Returns:
            {"success": True, "user_id": ..., "authorization": "..."}
        """
        async with self._lock:
            result = await login_with_password(self._username, password)
            if not result.get("success"):
                return result

            self._user_id = result.get("user_id", "")
            self._open_id = result.get("open_id", "")
            self._sid = result.get("sid", "")
            self._refresh_token = result.get("refresh_token", "")
            self._device_id = result.get("device_id", "")
            self._token_acquired_at = time.time()

            # 生成 authorization 字段（实际是 JWT-like token）
            # 抓包发现 authorization 字段值与 sid 关联
            # 这里我们使用 sid 作为 JWT
            self._authorization = self._sid

            return {
                "success": True,
                "user_id": self._user_id,
                "open_id": self._open_id,
                "sid": self._sid,
                "refresh_token": self._refresh_token,
                "authorization": self._authorization,
                "device_id": self._device_id,
            }

    async def async_refresh_token(self) -> bool:
        """刷新用户令牌。

        Returns:
            True 成功，False 失败
        """
        if not self._refresh_token:
            return False

        async with self._lock:
            result = await refresh_user_token(self._refresh_token)
            if not result.get("success"):
                _LOGGER.error("Token refresh failed: %s", result.get("error"))
                return False

            self._refresh_token = result.get("refresh_token", self._refresh_token)
            new_sid = result.get("sid", self._sid)
            self._sid = new_sid
            self._authorization = new_sid
            self._token_acquired_at = time.time()

            _LOGGER.info("Token refreshed successfully")
            return True

    def set_authorization_token(self, token: str, user_id: str = "") -> None:
        """直接设置 authorization token（用于手动输入模式）。

        Args:
            token: JWT authorization token
            user_id: 用户 ID（可选，可从 JWT 中提取）
        """
        self._authorization = token
        if user_id:
            self._user_id = user_id
        self._token_acquired_at = time.time()
        _LOGGER.info("Authorization token set directly (len=%d)", len(token))

    def get_token_age(self) -> float:
        """获取令牌已使用时间（秒）。"""
        if self._token_acquired_at == 0:
            return float("inf")
        return time.time() - self._token_acquired_at

    def is_token_expired(self, max_age: float = 7200) -> bool:
        """检查令牌是否过期（默认 2 小时）。"""
        return self.get_token_age() > max_age - TOKEN_REFRESH_MARGIN

    # --------------------------------------------------------------------
    # 序列化/反序列化（用于持久化）
    # --------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """导出当前状态为字典（用于持久化）。"""
        return {
            CONF_USERNAME: self._username,
            CONF_USER_ID: self._user_id,
            CONF_OPEN_ID: self._open_id,
            CONF_SID: self._sid,
            CONF_REFRESH_TOKEN: self._refresh_token,
            CONF_AUTHORIZATION: self._authorization,
            CONF_CLIENT_TOKEN: self._client_token,
            CONF_APP_ID: self._app_id,
            CONF_APP_KEY: self._app_key,
            CONF_TENANT_ID: self._tenant_id,
        }

    def load_from_dict(self, data: dict[str, Any]) -> None:
        """从字典恢复状态。"""
        self._username = data.get(CONF_USERNAME, self._username)
        self._user_id = data.get(CONF_USER_ID, "")
        self._open_id = data.get(CONF_OPEN_ID, "")
        self._sid = data.get(CONF_SID, "")
        self._refresh_token = data.get(CONF_REFRESH_TOKEN, "")
        self._authorization = data.get(CONF_AUTHORIZATION, self._sid)
        self._client_token = data.get(CONF_CLIENT_TOKEN, "")
        self._app_id = data.get(CONF_APP_ID, DEFAULT_APP_ID)
        self._app_key = data.get(CONF_APP_KEY, DEFAULT_APP_KEY)
        self._tenant_id = data.get(CONF_TENANT_ID, DEFAULT_TENANT_ID)
        self._token_acquired_at = time.time()

    # --------------------------------------------------------------------
    # HTTP 请求辅助
    # --------------------------------------------------------------------

    def _build_headers(
        self,
        method: str = "GET",
        url_path: str = "",
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """构建请求头（包含认证、签名、跟踪 ID 等）。

        抓包发现的关键头：
          - authorization: JWT
          - sign: MD5 签名
          - tenantid: 租户 ID
          - id: 用户 ID
          - username: base64(用户名)
          - nonce: 随机数
          - ts: 时间戳
          - traceid: 跟踪 ID
        """
        ts = str(int(time.time() * 1000))
        nonce = _generate_nonce(16)
        trace_id = _generate_trace_id()

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
            "tenantid": self._tenant_id,
            "id": self._user_id,
            "username": _b64_username(self._username),
            "nonce": nonce,
            "ts": ts,
            "traceid": trace_id,
            "lang": DEFAULT_LANGUAGE,
        }

        if self._authorization:
            headers["authorization"] = self._authorization

        # 计算签名
        try:
            sign = _build_sign(query=query, body=body, secret_key=self._app_key)
            headers["sign"] = sign
        except Exception as e:
            _LOGGER.debug("Sign generation failed: %s", e)

        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        base_url: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict[str, Any] | None:
        """统一的 HTTP 请求方法。

        Args:
            method: GET / POST
            path: API 路径（以 / 开头）
            query: URL 查询参数
            body: 请求体
            base_url: 覆盖默认 base URL
            timeout: 超时秒数

        Returns:
            响应的 JSON dict，或 None 表示失败
        """
        await self._ensure_session()
        base = base_url or f"https://{self._cdn_url}"
        url = f"{base}{path}"

        if query:
            url = f"{url}?{urlencode(query)}"

        headers = self._build_headers(method, path, query, body)

        try:
            if method.upper() == "GET":
                async with self._session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    text = await resp.text()
                    _LOGGER.debug(
                        "GET %s -> %d: %s", url, resp.status, text[:300]
                    )
                    if resp.status != 200:
                        return {"code": resp.status, "message": text[:200]}
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"code": resp.status, "message": text[:200]}
            else:
                async with self._session.post(
                    url,
                    json=body or {},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    text = await resp.text()
                    _LOGGER.debug(
                        "POST %s -> %d: %s", url, resp.status, text[:300]
                    )
                    if resp.status != 200:
                        return {"code": resp.status, "message": text[:200]}
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"code": resp.status, "message": text[:200]}
        except asyncio.TimeoutError:
            _LOGGER.warning("Request timeout: %s %s", method, url)
            return None
        except aiohttp.ClientError as e:
            _LOGGER.warning("Request error: %s %s -> %s", method, url, e)
            return None
        except Exception as e:
            _LOGGER.exception("Unexpected error in _request")
            return None

    @staticmethod
    def _extract_data(resp: dict[str, Any] | None) -> Any:
        """从响应中提取 data 字段（兼容多种响应结构）。"""
        if not isinstance(resp, dict):
            return None
        # 尝试多种可能
        if "data" in resp:
            data = resp["data"]
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return data
        return resp

    @staticmethod
    def _is_success(resp: dict[str, Any] | None) -> bool:
        """判断响应是否成功。"""
        if not isinstance(resp, dict):
            return False
        code = resp.get("code")
        if code in (200, 0, "200", "0"):
            return True
        if code is None and "data" in resp:
            return True
        return False

    # --------------------------------------------------------------------
    # 用户相关 API
    # --------------------------------------------------------------------

    async def get_user_profile(self) -> dict[str, Any] | None:
        """获取当前用户的个人信息。

        GET /user-center/app/user/profile?factoryId={tenant_id}&id={user_id}
        """
        if not self._user_id:
            return None
        query = {"factoryId": self._tenant_id, "id": self._user_id}
        resp = await self._request("GET", API_USER_PROFILE, query=query)
        return self._extract_data(resp)

    # --------------------------------------------------------------------
    # 设备相关 API
    # --------------------------------------------------------------------

    async def get_devices(self) -> list[dict[str, Any]]:
        """获取用户绑定的设备列表。

        POST /device-service/app/bind/listByUserId
        Body: {"userId": "...", "tenantId": "...", ...}
        """
        body = {
            "userId": self._user_id,
            "tenantId": self._tenant_id,
            "appId": self._app_id,
            "regionId": str(self._region_id),
        }
        resp = await self._request("POST", API_DEVICE_BIND_LIST, body=body)
        data = self._extract_data(resp)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list", data.get("records", data.get("devices", [])))
        return []

    async def get_device_shadow(self, device_id: str | int) -> dict[str, Any] | None:
        """获取设备当前状态/影子数据。

        POST /device-service/app/device/shadow
        Body: {"deviceId": "..."}
        """
        body = {"deviceId": str(device_id)}
        resp = await self._request("POST", API_DEVICE_SHADOW, body=body)
        return self._extract_data(resp)

    async def get_product_info(self, product_id: str | int) -> dict[str, Any] | None:
        """获取产品信息。

        GET /product-service/outer/app/productInfo?appId=...&lang=zh&regionId=15
        """
        query = {
            "appId": self._app_id,
            "lang": DEFAULT_LANGUAGE,
            "regionId": str(self._region_id),
        }
        resp = await self._request("GET", API_PRODUCT_INFO, query=query)
        data = self._extract_data(resp)
        if isinstance(data, list):
            for p in data:
                if isinstance(p, dict) and str(p.get("productId", "")) == str(product_id):
                    return p
            return data[0] if data else None
        if isinstance(data, dict):
            return data
        return None

    # --------------------------------------------------------------------
    # 耗材相关 API
    # --------------------------------------------------------------------

    async def get_consumables(self, product_ids: list[str | int]) -> list[dict[str, Any]]:
        """获取设备耗材信息。

        POST /product-service/outer/app/productInfo/getConsumablesByProductIds
        Body: {"productIds": ["..."]}
        """
        if not product_ids:
            return []
        body = {"productIds": [str(p) for p in product_ids]}
        resp = await self._request("POST", API_PRODUCT_CONSUMABLES, body=body)
        data = self._extract_data(resp)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list", data.get("records", []))
        return []

    # --------------------------------------------------------------------
    # 记录相关 API（清洁记录、制水记录等）
    # --------------------------------------------------------------------

    async def get_clean_records(
        self,
        device_id: str | int,
        sn: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """获取清洁记录。

        POST /infrastructure-third/app/record/page
        Body: {"deviceId": "...", "sn": "...", "current": 1, "size": 20, ...}
        """
        body = {
            "deviceId": str(device_id),
            "current": page,
            "size": page_size,
        }
        if sn:
            body["sn"] = sn

        resp = await self._request("POST", API_CLEAN_RECORD_PAGE, body=body)
        data = self._extract_data(resp)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list", data.get("records", data.get("data", [])))
        return []

    async def get_event_statistics(
        self,
        sn: str,
        identifier: str,
        begin_time_ms: int | None = None,
        end_time_ms: int | None = None,
        page: int = 1,
        page_size: int = 200,
    ) -> list[dict[str, Any]]:
        """获取事件统计数据（清洁/制水等）。

        GET /data-statistics-service/app/data/flow/eventStatistics/page
            ?identifier=clean_record&sn=xxx&beginTime=...&endTime=...
            &current=1&size=200
        """
        now_ms = int(time.time() * 1000)
        if end_time_ms is None:
            end_time_ms = now_ms
        if begin_time_ms is None:
            begin_time_ms = now_ms - 7 * 24 * 3600 * 1000  # 默认过去 7 天

        query = {
            "identifier": identifier,
            "sn": sn,
            "beginTime": str(begin_time_ms),
            "endTime": str(end_time_ms),
            "current": str(page),
            "size": str(page_size),
        }

        resp = await self._request("GET", API_EVENT_STATISTICS_PAGE, query=query)
        data = self._extract_data(resp)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list", data.get("records", data.get("data", [])))
        return []

    async def get_share_records(
        self,
        sn: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """获取分享记录。

        POST /infrastructure-third/app/share/record/page
        """
        body = {
            "sn": sn,
            "current": page,
            "size": page_size,
        }
        resp = await self._request("POST", API_SHARE_RECORD_PAGE, body=body)
        data = self._extract_data(resp)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("list", data.get("records", []))
        return []

    # --------------------------------------------------------------------
    # OSS / 文件
    # --------------------------------------------------------------------

    async def get_oss_access_url(self, object_key: str) -> str | None:
        """获取 OSS 文件的访问 URL。

        POST /storage-management/storage/oss/getAccessUrl
        Body: {"objectKey": "..."}
        """
        body = {"objectKey": object_key}
        resp = await self._request("POST", API_OSS_GET_ACCESS_URL, body=body)
        data = self._extract_data(resp)
        if isinstance(data, dict):
            return data.get("url") or data.get("accessUrl")
        if isinstance(data, str):
            return data
        return None

    # --------------------------------------------------------------------
    # 固件升级
    # --------------------------------------------------------------------

    async def check_upgrade(self, device_id: str | int) -> dict[str, Any] | None:
        """检查设备固件升级。

        POST /upgrade-service/app/tryUpgrade
        Body: {"deviceId": "..."}
        """
        body = {"deviceId": str(device_id)}
        resp = await self._request("POST", API_UPGRADE_TRY, body=body)
        return self._extract_data(resp)

    # --------------------------------------------------------------------
    # 综合数据获取（用于 coordinator）
    # --------------------------------------------------------------------

    async def fetch_device_full_data(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any]:
        """获取设备的完整数据（用于 coordinator 单次更新）。

        包括：
          - 设备影子（实时状态）
          - 清洁记录
          - 制水记录（最近 7 天）
          - 耗材信息

        Args:
            device: 设备字典（来自 get_devices）

        Returns:
            包含所有数据的字典
        """
        device_id = str(device.get("deviceId") or device.get("id") or "")
        sn = device.get("sn") or device.get("deviceSn") or device_id
        product_id = device.get("productId") or device.get("productCode")

        result: dict[str, Any] = {
            "device_info": device,
            "shadow": None,
            "clean_records": [],
            "water_records": [],
            "consumables": [],
        }

        # 并发获取
        tasks = []
        tasks.append(("shadow", self.get_device_shadow(device_id)))
        tasks.append(("clean_records", self.get_clean_records(device_id, sn=sn)))
        tasks.append(("water_records", self.get_event_statistics(
            sn=sn, identifier=EVENT_IDENTIFIER_WATER_MAKE
        )))
        if product_id:
            tasks.append(("consumables", self.get_consumables([product_id])))

        results = await asyncio.gather(
            *[t[1] for t in tasks], return_exceptions=True
        )

        for (key, _), value in zip(tasks, results):
            if isinstance(value, Exception):
                _LOGGER.debug("Fetch %s failed: %s", key, value)
                continue
            result[key] = value

        return result

    # --------------------------------------------------------------------
    # 便捷属性
    # --------------------------------------------------------------------

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def open_id(self) -> str:
        return self._open_id

    @property
    def sid(self) -> str:
        return self._sid

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @property
    def authorization(self) -> str:
        return self._authorization

    @property
    def username(self) -> str:
        return self._username

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    @property
    def cdn_url(self) -> str:
        return self._cdn_url
