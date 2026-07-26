"""大淘客 MCP 工具函数：每个函数对应一个 agent 可调用的工具。"""
from __future__ import annotations

from app.adapters.dtk import TaobaoDtkAdapter
from app.models.product import NormalizedProduct

from .client import dtk_client

_adapter = TaobaoDtkAdapter()


async def search_goods(
    keywords: str,
    page_size: int = 20,
    page_id: str = "1",
    price_min: float | None = None,
    price_max: float | None = None,
    has_coupon: bool = True,
    sort: str = "0",
) -> list[NormalizedProduct]:
    """按关键词搜索淘宝商品，返回归一化商品列表。

    Args:
        keywords: 搜索关键词，如"蓝牙耳机"
        page_size: 每页条数 (10/50/100)
        page_id: 分页 id，首次传 1
        price_min: 券后价下限
        price_max: 券后价上限
        has_coupon: 是否只返回有券商品
        sort: 排序，0-综合，2-热销，5-价格降序，6-价格升序
    """
    biz: dict[str, str] = {
        "keyWords": keywords,
        "pageSize": str(page_size),
        "pageId": page_id,
        "sort": sort,
    }
    if price_min is not None:
        biz["priceLowerLimit"] = str(price_min)
    if price_max is not None:
        biz["priceUpperLimit"] = str(price_max)
    if has_coupon:
        biz["hasCoupon"] = "1"
    raw = await dtk_client.request("search", biz)
    return _adapter.parse_search(raw)


async def get_goods_list(
    page_size: int = 20,
    page_id: str = "1",
    sort: str = "0",
    cids: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    has_coupon: bool = True,
) -> list[NormalizedProduct]:
    """按类目拉取精选商品流，返回归一化商品列表。

    Args:
        page_size: 每页条数 (10/50/100)
        page_id: 分页 id，首次传 1
        sort: 排序，0-综合，2-热销，4-佣金，5-价格降序，6-价格升序
        cids: 一级分类 id，多个用英文逗号分隔（1-女装，2-母婴，3-美妆...）
        price_min: 券后价下限
        price_max: 券后价上限
        has_coupon: 是否只返回有券商品
    """
    biz: dict[str, str] = {"pageSize": str(page_size), "pageId": page_id, "sort": sort}
    if cids:
        biz["cids"] = cids
    if price_min is not None:
        biz["priceLowerLimit"] = str(price_min)
    if price_max is not None:
        biz["priceUpperLimit"] = str(price_max)
    if has_coupon:
        biz["hasCoupon"] = "1"
    raw = await dtk_client.request("list", biz)
    return _adapter.parse_search(raw)


async def get_price_trend(
    goods_id: str,
) -> list[dict]:
    """查询商品历史券后价趋势，返回日期-价格列表。

    用于比价 agent 判断"现在是否好价"：当前价在历史分位的位置。

    Args:
        goods_id: 大淘客数字商品 id（搜索响应里的 id 字段，即 extra.dtk_id）；
            注意不是 goodsId（加密在线 id），传错会返回 10006 无数据
    """
    raw = await dtk_client.request("price_trend", {"id": goods_id})
    return _adapter.parse_price_trend(raw)


async def convert_link(
    goods_id: str,
    coupon_id: str | None = None,
) -> dict:
    """高效转链，生成可跳转短链和淘口令。

    PID 不传走应用默认；项目不变现，佣金归默认方。

    Args:
        goods_id: 淘宝商品 id
        coupon_id: 优惠券 ID，指定使用某张优惠券
    """
    biz: dict[str, str] = {"goodsId": goods_id}
    if coupon_id:
        biz["couponId"] = coupon_id
    raw = await dtk_client.request("convert_link", biz)
    return _adapter.parse_convert_link(raw)


async def parse_content(
    content: str,
) -> dict:
    """万能解析转链，解析淘口令或商品链接。

    输入包含淘口令或链接的文本，优先解析淘口令，再按序解析每个链接。
    PID 不传走应用默认。

    Args:
        content: 包含淘口令、链接的文本
    """
    raw = await dtk_client.request("parse_content", {"content": content})
    data = raw.get("data", raw)
    return {
        "goods_id": data.get("itemId", ""),
        "item_name": data.get("itemName", ""),
        "main_pic": data.get("mainPic", ""),
        "data_type": data.get("dataType", ""),
        "item_link": data.get("itemLink", ""),
        "coupon_link": data.get("couponLink", ""),
        "origin_url": data.get("originUrl", ""),
        "origin_type": data.get("originType", ""),
        "cps_short_url": data.get("shortUrl", ""),
        "cps_short_tpwd": data.get("shortTpwd", ""),
    }
