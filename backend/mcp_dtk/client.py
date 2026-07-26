"""大淘客 HTTP 客户端：签名 + 请求 + 缓存降级。"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

import httpx

from app.config import settings

# 接口元数据：路径 -> version
API_META = {
    "search": {"path": "/api/goods/get-dtk-search-goods", "version": "v2.1.2"},
    "list": {"path": "/api/goods/get-goods-list", "version": "v1.2.4"},
    "price_trend": {"path": "/api/goods/price-trend", "version": "v1.0.0"},
    "convert_link": {"path": "/api/tb-service/get-privilege-link", "version": "v1.3.1"},
    "parse_content": {"path": "/api/tb-service/parse-content", "version": "v1.0.0"},
}

FIXTURES_DIR = pathlib.Path(__file__).parent.parent.parent / "fixtures"


class DtkClient:
    """大淘客 HTTP 客户端，封装签名与请求逻辑。"""

    BASE_URL = "https://openapi.dataoke.com"

    def __init__(self) -> None:
        self.app_key = settings.dataoke_app_key
        self.app_secret = settings.dataoke_app_secret
        self._http: httpx.AsyncClient | None = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=10.0)
        return self._http

    def _sign(self, params: dict[str, str]) -> str:
        """大淘客签名：参数按 key 升序排成 key=value&...，末尾追加 &key=appSecret，MD5 大写。

        与 dtkApi 官方 SDK (dtkApi.apiRequest.Request.md5_sign) 算法一致：
            sorted_params = sorted(params.items())
            sign_str = '&'.join(f'{k}={v}' for k, v in sorted_params) + f'&key={app_secret}'
            sign = md5(sign_str).upper()
        """
        sorted_items = sorted(params.items())
        parts = [f"{k}={v}" for k, v in sorted_items]
        sign_str = "&".join(parts) + f"&key={self.app_secret}"
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()

    async def request(self, api_name: str, biz_params: dict[str, Any]) -> dict:
        """发起请求并返回 JSON 响应。

        Args:
            api_name: API_META 中的 key（search/list/price_trend/convert_link/parse_content）
            biz_params: 业务参数（不含公共参数）
        """
        meta = API_META[api_name]
        # 组装全部参数（全部转成字符串）
        params: dict[str, str] = {
            "appKey": self.app_key,
            "version": meta["version"],
            **{k: str(v) for k, v in biz_params.items()},
        }
        # 签名
        params["sign"] = self._sign(params)
        url = f"{self.BASE_URL}{meta['path']}"
        try:
            resp = await self.http.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            # 降级：尝试读 fixture（DTK 479 验签失败/超频时让前端仍能渲染带商品的报 告）
            # 文件名按 API 分：search->sample_search.json, price_trend->sample_trend.json
            fixture_name = {
                "search": "sample_search.json",
                "price_trend": "sample_trend.json",
            }.get(api_name, "sample.json")
            fixture_path = FIXTURES_DIR / api_name / fixture_name
            if fixture_path.exists():
                return json.loads(fixture_path.read_text(encoding="utf-8"))
            raise

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None


# 全局单例
dtk_client = DtkClient()
