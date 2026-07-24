# 大淘客 FastMCP Server 搭建指南

> 本文档解释如何从零搭建一个封装大淘客开放平台 API 的 FastMCP server，让 LangGraph agent 通过 MCP 协议按需调用商品搜索、详情、历史券后价、转链等工具。

## 1. 为什么用 FastMCP

MCP (Model Context Protocol) 是 Anthropic 开源的工具协议标准，核心思路是：**把外部 API 封装成工具，agent 按需发现和调用**。

我们的架构里，每个外部数据源是一个独立的 MCP server：

```
LangGraph Agent
  ↓ langchain-mcp-adapters
  ↓ MCP 协议 (stdio / SSE)
FastMCP Server (mcp-dtk)
  ↓ httpx
大淘客 openapi.dataoke.com
```

好处：

- **解耦**：agent 代码不直接 import 大淘客 SDK，而是通过 MCP 协议发现工具；换数据源只需换 server，agent 不改
- **可插拔**：多个 MCP server 可并存（未来加和风天气 server 不影响大淘客 server）
- **前端可视化**：MCP 协议天然支持工具列表查询，前端可展示"当前挂载了哪些工具"
- **面试加分**：MCP 是 2025 年最新工具协议标准，写在简历上是技术敏感度信号

## 2. 大淘客 API 签名机制

大淘客所有接口都需要签名验证，流程如下：

```
1. 组装参数：业务参数 + 公共参数（appKey, version, type）
2. 按参数名升序排序
3. 拼接：appSecret + key1value1 + key2value2 + ... + appSecret
4. MD5 取大写
5. 把 sign 加入请求参数，发 GET 请求
```

具体来说：

| 公共参数 | 说明 |
|---|---|
| appKey | 应用 key（.env 中 DATAOKE_APP_KEY） |
| version | 接口版本，固定 `v1.1.0`（具体看接口文档） |
| type | 接口名，如 `get_dtk_search_goods` |
| sign | 签名，MD5(appSecret + sorted_kv + appSecret).upper() |

示例（搜索接口）：

```python
params = {
    "appKey": "your_app_key",
    "version": "v1.1.0",
    "type": "get_dtk_search_goods",
    "keyWords": "蓝牙耳机",
    "pageId": "1",
    "pageSize": "20",
    "sort": "0",
}
# 签名
sign_str = app_secret + "".join(f"{k}{v}" for k, v in sorted(params.items())) + app_secret
sign = hashlib.md5(sign_str.encode()).hexdigest().upper()
params["sign"] = sign
# 请求
response = httpx.get("https://openapi.dataoke.com/api/goods/get-dtk-search-goods", params=params)
```

注意：`sign` 参数不参与签名本身的计算；`version` 值以接口文档为准（部分接口是 `v1.1.0`，部分是 `v2.0.0`）。

## 3. FastMCP Server 代码结构

```
backend/mcp_dtk/
  __init__.py
  server.py          # FastMCP 入口 + 工具注册
  client.py           # 大淘客 HTTP 客户端（签名 + 请求 + 缓存降级）
  tools.py            # 工具函数（搜索/详情/历史价/转链）
```

每个文件职责：

- `client.py`：封装签名逻辑和 HTTP 调用，是唯一与大淘客通信的地方；内置 Redis 缓存与 fixture 降级
- `tools.py`：把 client 方法包装成 MCP 工具函数，输入/输出用 Pydantic 类型标注
- `server.py`：创建 FastMCP 实例，用 `@server.tool()` 注册工具，启动 stdio 或 SSE 传输

## 4. 核心代码讲解

### 4.1 client.py — 大淘客 HTTP 客户端

```python
"""大淘客 HTTP 客户端：签名 + 请求 + 缓存降级。"""
import hashlib
import httpx
from app.config import settings

class DtkClient:
    BASE_URL = "https://openapi.dataoke.com"

    def __init__(self):
        self.app_key = settings.dataoke_app_key
        self.app_secret = settings.dataoke_app_secret
        self.http = httpx.AsyncClient(timeout=10)

    def _sign(self, params: dict) -> str:
        """大淘客签名：appSecret + 升序拼接 kv + appSecret，MD5 大写。"""
        sign_str = self.app_secret
        for k in sorted(params):
            sign_str += f"{k}{params[k]}"
        sign_str += self.app_secret
        return hashlib.md5(sign_str.encode()).hexdigest().upper()

    async def request(self, path: str, biz_params: dict, version: str = "v1.1.0") -> dict:
        """发请求并返回 JSON。"""
        all_params = {
            "appKey": self.app_key,
            "version": version,
            "type": path.rsplit("/", 1)[-1],  # 接口名
            **biz_params,
        }
        all_params["sign"] = self._sign(all_params)
        resp = await self.http.get(f"{self.BASE_URL}{path}", params=all_params)
        return resp.json()
```

关键点：
- 签名时 `sign` 本身不参与；`sorted(params)` 保证升序
- `type` 参数取 URL 末段（如 `get-dtk-search-goods`），用接口文档的 `type` 值
- 用 `httpx.AsyncClient` 异步，和 LangGraph agent 同一个事件循环

### 4.2 tools.py — MCP 工具函数

```python
"""大淘客 MCP 工具：每个函数对应一个 agent 可调用的工具。"""
from app.models.product import NormalizedProduct
from app.adapters.dtk import TaobaoDtkAdapter

from .client import DtkClient

_client = DtkClient()
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
    """按关键词搜索商品，返回归一化商品列表。

    Args:
        keywords: 搜索关键词，如"蓝牙耳机"
        page_size: 每页条数 (10/50/100)
        page_id: 分页 id，首次传 1
        price_min: 券后价下限
        price_max: 券后价上限
        has_coupon: 是否只返回有券商品
        sort: 排序，0-综合，2-热销，5-价格降序，6-价格升序
    """
    biz = {"keyWords": keywords, "pageSize": str(page_size), "pageId": page_id, "sort": sort}
    if price_min is not None:
        biz["priceLowerLimit"] = str(price_min)
    if price_max is not None:
        biz["priceUpperLimit"] = str(price_max)
    if has_coupon:
        biz["hasCoupon"] = "1"
    raw = await _client.request("/api/goods/get-dtk-search-goods", biz)
    return _adapter.parse_search(raw)
```

关键点：
- 工具函数的 **docstring 和类型标注就是 MCP 协议暴露给 agent 的工具描述**——agent 靠这些信息决定何时调用
- 返回 `NormalizedProduct` 而非原始 dict，适配器在工具层完成归一化
- `structured_output=True` 让 MCP 协议携带 Pydantic schema，agent 端能自动解析

### 4.3 server.py — FastMCP 入口

```python
"""大淘客 FastMCP Server 入口。"""
from mcp.server.fastmcp import FastMCP

from .tools import search_goods, get_goods_detail, get_price_trend, convert_link, parse_content

server = FastMCP("mcp-dtk", instructions="大淘客商品数据工具：搜索/详情/历史价/转链")

# 注册工具——@server.tool() 会自动提取函数名、docstring、类型标注
server.tool(description="按关键词搜索淘宝商品，返回归一化商品列表")(search_goods)
server.tool(description="获取商品详情")(get_goods_detail)
server.tool(description="查询商品历史券后价趋势")(get_price_trend)
server.tool(description="高效转链，生成可跳转短链和淘口令")(convert_link)
server.tool(description="万能解析转链，解析淘口令或商品链接")(parse_content)

if __name__ == "__main__":
    server.run(transport="stdio")
```

关键点：
- `FastMCP("mcp-dtk")` 第一个参数是 server 名称，agent 端通过它识别工具来源
- `server.tool()` 是装饰器，也可以写成 `@server.tool()` 放在 tools.py 的函数上
- `transport="stdio"` 适合本地开发（agent 同进程调用）；`transport="sse"` 适合远程部署

## 5. Agent 端如何接入

LangGraph agent 通过 `langchain-mcp-adapters` 连接 MCP server：

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "mcp-dtk": {
        "command": "python",
        "args": ["-m", "mcp_dtk.server"],
        "transport": "stdio",
    }
})
tools = await client.get_tools()
# tools 是 list[BaseTool]，直接传给 LangGraph agent
```

agent 会看到 5 个工具：`search_goods`、`get_goods_detail`、`get_price_trend`、`convert_link`、`parse_content`。
每个工具的 name/description/args_schema 都来自 tools.py 里的函数定义。

## 6. 缓存与降级

client.py 在请求前查 Redis 缓存，请求后写缓存；配额超限时降级：

```
正常：查缓存 → miss → 调 API → 写缓存(带 TTL) → 返回
降级：查缓存 → miss → 调 API 失败 → 读缓存(无视 TTL) → 读 fixture → 报错
```

```python
async def search_with_cache(keywords, **kwargs):
    cache_key = f"goods:search:{md5(json.dumps({'kw': keywords, **kwargs}, sort_keys=True))}"
    cached = await cache_get_raw(cache_key)
    if cached:
        return cached
    try:
        raw = await _client.request(...)
        await cache_set(cache_key, raw, ttl=21600)  # 6h
        return raw
    except Exception:
        fallback = await cache_fallback(cache_key)  # 无视 TTL
        if fallback:
            return fallback
        fixture = load_fixture("search", "sample_search.json")
        return fixture  # 兜底
```

## 7. 启动与调试

```bash
# 1. 确保 .env 中 DATAOKE_APP_KEY 和 DATAOKE_APP_SECRET 已填
# 2. 直接运行 MCP server（stdio 模式，agent 同进程调用）
conda run -n BlackTea python -m mcp_dtk.server

# 3. 用 MCP inspector 调试（可视化工具列表与调用）
npx @modelcontextprotocol/inspector python -m mcp_dtk.server

# 4. 单测（mock client.request，不走网络）
conda run -n BlackTea python -m pytest backend/tests/test_mcp_tools.py -v
```

## 8. 需要实现的 5 个工具

| 工具函数 | 大淘客接口 | 文档 id | 用途 |
|---|---|---|---|
| `search_goods` | /api/goods/get-dtk-search-goods | 9 | 关键词搜索，候选集主接口 |
| `get_goods_list` | /api/goods/get-goods-list | 5 | 精选商品流，按类目/排序拉取 |
| `get_goods_detail` | /api/goods/get-goods-details | — | 打分字段补全 |
| `get_price_trend` | /api/goods/price-trend | 36 | 历史券后价，比价 agent 判断入手时机 |
| `convert_link` | /api/goods/get-privilege-link | 7 | 高效转链生成短链/淘口令 |
| `parse_content` | /api/goods/parse-link | 33 | 万能解析淘口令/链接 |

M1 阶段先实现 `search_goods` 和 `get_price_trend` 两个（搜索 + 历史价是一轮对话里最高频的联动）。