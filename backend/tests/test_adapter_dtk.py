"""适配器单测，纯函数，无网络。"""
from app.adapters.dtk import TaobaoDtkAdapter

adapter = TaobaoDtkAdapter()


def test_parse_search_basic():
    """验证基本商品能被正确归一化为 NormalizedProduct。"""
    raw = {
        "data": [{
            "goodsId": "589284195570",
            "title": "测试商品标题",
            "originalPrice": 38.5,
            "actualPrice": 28.5,
            "couponPrice": 10,
            "monthSales": 1050,
            "mainPic": "//img.alicdn.com/test.jpg",
            "shopType": 1,
            "shopName": "测试旗舰店",
            "brandName": "测试品牌",
            "itemLink": "https://detail.tmall.com/item.htm?id=589284195570",
        }]
    }
    products = adapter.parse_search(raw)
    assert len(products) == 1
    p = products[0]
    assert p.goods_id == "589284195570"
    assert p.price == 28.5  # actualPrice -> price
    assert p.original_price == 38.5
    assert p.coupon_amount == 10
    assert p.sales == 1050
    assert p.main_image == "https://img.alicdn.com/test.jpg"
    assert p.shop_type == "tmall"
    assert p.brand == "测试品牌"


def test_parse_search_empty():
    products = adapter.parse_search({"data": []})
    assert products == []


def test_parse_price_trend():
    raw = {
        "data": {
            "historicalPrice": [
                {"date": "2024-01-01", "actualPrice": 29.9},
                {"date": "2024-01-15", "actualPrice": 25.5},
            ]
        }
    }
    trend = adapter.parse_price_trend(raw)
    assert len(trend) == 2
    assert trend[0]["date"] == "2024-01-01"
    assert trend[1]["price"] == "25.5"


def test_parse_convert_link():
    raw = {"data": {"shortUrl": "https://s.click.taobao.com/test", "tpwd": "test_tpwd"}}
    result = adapter.parse_convert_link(raw)
    assert result["short_url"] == "https://s.click.taobao.com/test"
    assert result["tpwd"] == "test_tpwd"
