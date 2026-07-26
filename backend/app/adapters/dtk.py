"""大淘客原始响应 -> NormalizedProduct 适配器。"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.models.product import NormalizedProduct

_SHOP_TYPE_MAP = {1: "tmall", 0: "taobao"}
_ACTIVITY_MAP = {1: "无活动", 2: "淘抢购", 3: "聚划算"}


def _ensure_https(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return "https:" + url
    return url


def _to_decimal(val, default="0") -> Decimal:
    if val is None or val == "" or val == "-":
        return Decimal(default)
    return Decimal(str(val)).quantize(Decimal("0.01"))


def _parse_goods_item(item: dict) -> NormalizedProduct:
    """将大淘客搜索/列表/详情的单个商品 dict 转为 NormalizedProduct。"""
    coupon_price = item.get("couponPrice") or 0
    return NormalizedProduct(
        goods_id=str(item.get("goodsId", "")),
        goods_sign=item.get("goodsSign"),
        title=item.get("title", ""),
        dtitle=item.get("dtitle"),
        brand=item.get("brandName"),
        shop_name=item.get("shopName"),
        shop_type=_SHOP_TYPE_MAP.get(int(item.get("shopType", 0))),
        price=_to_decimal(item.get("actualPrice")),
        original_price=_to_decimal(item.get("originalPrice")) or None,
        coupon_amount=_to_decimal(coupon_price),
        coupon_conditions=item.get("couponConditions"),
        sales=int(item["monthSales"]) if item.get("monthSales") is not None else None,
        daily_sales=int(item["dailySales"]) if item.get("dailySales") is not None else None,
        commission_rate=float(item["commissionRate"]) if item.get("commissionRate") is not None else None,
        discounts=float(item["discounts"]) if item.get("discounts") is not None else None,
        dsr_score=float(item["dsrScore"]) if item.get("dsrScore") is not None else None,
        ship_score=float(item["shipScore"]) if item.get("shipScore") is not None else None,
        service_score=float(item["serviceScore"]) if item.get("serviceScore") is not None else None,
        main_image=_ensure_https(item.get("mainPic", "")) or "",
        marketing_image=_ensure_https(item.get("marketingMainPic")),
        detail_url=item.get("itemLink", ""),
        coupon_link=_ensure_https(item.get("couponLink")),
        selling_points=item.get("desc"),
        special_texts=item.get("specialText") or [],
        activity_type=_ACTIVITY_MAP.get(int(item.get("activityType", 1)), "无活动"),
        has_coupon=bool(coupon_price and float(coupon_price) > 0),
        free_ship=bool(item.get("freeshipRemoteDistrict") == 1),
        fetched_at=datetime.now(timezone.utc),
        extra={
            "raw": item,
            # 大淘客数字商品 id：历史券后价等接口的入参要它，
            # goodsId 是加密在线 id，price-trend 用它会查不到数据
            "dtk_id": str(item.get("id") or ""),
            "sales_caption": "30天热销",
            "cid": item.get("cid"),
            "subcid": item.get("subcid"),
            "tbcid": item.get("tbcid"),
            "ai_score": item.get("aiSummarizeScore"),
        },
    )


class TaobaoDtkAdapter:
    """大淘客适配器：纯函数风格，无网络依赖，单测直接喂 fixture。"""

    def parse_search(self, raw: dict) -> list[NormalizedProduct]:
        # DTK 真实搜索响应：data 是 dict {"list":[...],"totalNum":N,...}
        # 旧 fixture 样例：data 直接是 list。兼容两种结构。
        data = raw.get("data", [])
        if isinstance(data, dict):
            items = data.get("list", [])
        else:
            items = data
        return [_parse_goods_item(i) for i in items]

    def parse_detail(self, raw: dict) -> NormalizedProduct:
        item = raw.get("data", raw)
        return _parse_goods_item(item)

    def parse_price_trend(self, raw: dict) -> list[dict]:
        # 业务错误（如无历史数据 code=10006）时 data 是 JSON null
        hist = (raw.get("data") or {}).get("historicalPrice", [])
        return [{"date": h.get("date"), "price": str(h.get("actualPrice"))} for h in hist]

    def parse_convert_link(self, raw: dict) -> dict:
        """高效转链(7)返回的链接信息。"""
        data = raw.get("data", raw)
        return {
            "short_url": data.get("shortUrl", ""),
            "item_url": data.get("itemUrl", ""),
            "tpwd": data.get("tpwd", ""),
            "long_tpwd": data.get("longTpwd", ""),
            "max_commission_rate": data.get("maxCommissionRate", ""),
        }
