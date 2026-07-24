"""大淘客 FastMCP Server 入口。

启动方式：
    conda run -n BlackTea python -m mcp_dtk.server

调试：
    npx @modelcontextprotocol/inspector python -m mcp_dtk.server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import (
    convert_link,
    get_goods_list,
    get_price_trend,
    parse_content,
    search_goods,
)

server = FastMCP(
    "mcp-dtk",
    instructions="大淘客商品数据工具：搜索/精选列表/历史价/转链/解析。商品数据来自大淘客开放平台。",
)

# 注册工具——@server.tool() 会自动提取函数名、docstring、类型标注作为 MCP 工具 schema
server.tool(description="按关键词搜索淘宝商品，返回归一化商品列表")(search_goods)
server.tool(description="按类目拉取精选商品流，返回归一化商品列表")(get_goods_list)
server.tool(description="查询商品历史券后价趋势，判断入手时机")(get_price_trend)
server.tool(description="高效转链，生成可跳转短链和淘口令")(convert_link)
server.tool(description="万能解析转链，解析淘口令或商品链接")(parse_content)


if __name__ == "__main__":
    server.run(transport="stdio")
