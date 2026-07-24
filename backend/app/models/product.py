"""归一化商品模型与适配器协议。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel


class NormalizedProduct(BaseModel):
    """大淘客商品归一化后的统一结构。"""

    # 标识
    platform: Literal["taobao"] = "taobao"
    goods_id: str
    goods_sign: str | None = None
    # 基础信息
    title: str
    dtitle: str | None = None
    brand: str | None = None
    category_path: list[str] = []
    shop_name: str | None = None
    shop_type: str | None = None  # tmall / taobao
    # 价格 (元, Decimal)
    price: Decimal
    original_price: Decimal | None = None
    coupon_amount: Decimal = Decimal(0)
    coupon_conditions: str | None = None
    # 市场信号
    sales: int | None = None
    daily_sales: int | None = None
    commission_rate: float | None = None
    discounts: float | None = None
    # 店铺评分
    dsr_score: float | None = None
    ship_score: float | None = None
    service_score: float | None = None
    # 内容与链接
    main_image: str
    marketing_image: str | None = None
    images: list[str] = []
    detail_url: str
    coupon_link: str | None = None
    selling_points: str | None = None
    special_texts: list[str] = []
    # 历史价格 (M2)
    price_history: list[dict] | None = None
    # 活动信息
    activity_type: str | None = None
    has_coupon: bool = True
    free_ship: bool = False
    # 溯源
    fetched_at: datetime
    extra: dict = {}


class DtkAdapter(Protocol):
    """大淘客原始响应 -> NormalizedProduct 的适配器协议。"""

    def parse_search(self, raw: dict) -> list[NormalizedProduct]: ...
    def parse_detail(self, raw: dict) -> NormalizedProduct: ...
    def parse_price_trend(self, raw: dict) -> list[dict]: ...
    def parse_convert_link(self, raw: dict) -> dict: ...
