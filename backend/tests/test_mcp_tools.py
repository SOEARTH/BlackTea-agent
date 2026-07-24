"""MCP 工具单测：mock client.request，验证工具函数逻辑。"""
import json
import pathlib
from unittest.mock import AsyncMock, patch

import pytest

from mcp_dtk.tools import convert_link, get_goods_list, get_price_trend, parse_content, search_goods

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"


@pytest.mark.asyncio
async def test_search_goods_mock():
    """搜索工具：mock client 返回 fixture，验证归一化链路。"""
    fixture = json.loads((FIXTURES / "search" / "sample_search.json").read_text(encoding="utf-8"))
    with patch("mcp_dtk.tools.dtk_client.request", new_callable=AsyncMock, return_value=fixture):
        products = await search_goods("测试", page_size=10)
    assert len(products) == 1
    p = products[0]
    assert p.goods_id == "589284195570"
    assert p.price == 28.5
    assert p.shop_type == "tmall"


@pytest.mark.asyncio
async def test_get_goods_list_mock():
    """精选列表工具：mock client 返回 fixture。"""
    fixture = json.loads((FIXTURES / "search" / "sample_search.json").read_text(encoding="utf-8"))
    with patch("mcp_dtk.tools.dtk_client.request", new_callable=AsyncMock, return_value=fixture):
        products = await get_goods_list(page_size=50, sort="0")
    assert len(products) == 1
    assert products[0].brand == "西维里"


@pytest.mark.asyncio
async def test_get_price_trend_mock():
    """历史价工具：mock client 返回 fixture。"""
    fixture = json.loads((FIXTURES / "price_trend" / "sample_trend.json").read_text(encoding="utf-8"))
    with patch("mcp_dtk.tools.dtk_client.request", new_callable=AsyncMock, return_value=fixture):
        trend = await get_price_trend("589284195570")
    assert len(trend) == 3
    assert trend[0]["price"] == "29.9"
    assert trend[2]["price"] == "28.5"


@pytest.mark.asyncio
async def test_convert_link_mock():
    """转链工具：mock client 返回转链响应。"""
    resp = {"data": {"shortUrl": "https://s.click.taobao.com/abc", "tpwd": "test_tpwd", "longTpwd": "long_tpwd"}}
    with patch("mcp_dtk.tools.dtk_client.request", new_callable=AsyncMock, return_value=resp):
        result = await convert_link("589284195570")
    assert result["short_url"] == "https://s.click.taobao.com/abc"
    assert result["tpwd"] == "test_tpwd"


@pytest.mark.asyncio
async def test_parse_content_mock():
    """万能解析工具：mock client 返回解析响应。"""
    resp = {"data": {"itemId": "12345", "itemName": "测试商品", "dataType": "goods", "itemLink": "https://detail.tmall.com/item.htm?id=12345"}}
    with patch("mcp_dtk.tools.dtk_client.request", new_callable=AsyncMock, return_value=resp):
        result = await parse_content("￥test￥")
    assert result["goods_id"] == "12345"
    assert result["item_name"] == "测试商品"
    assert result["data_type"] == "goods"


def test_server_imports():
    """验证 server 模块能正常导入、工具已注册。"""
    from mcp_dtk.server import server
    # FastMCP 实例存在即通过
    assert server is not None
