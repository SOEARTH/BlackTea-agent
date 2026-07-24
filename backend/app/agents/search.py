"""选品检索 Agent：调用 MCP 工具搜索商品，输出候选列表。

容错：MCP 调用失败时返回空候选列表并记录错误消息，
由下游 reflect 判断是否打回重试或告知用户，而非整个图崩溃。
"""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from app.agents.state import GraphState
from app.models.product import NormalizedProduct

logger = logging.getLogger(__name__)


async def search_node(state: GraphState) -> GraphState:
    """选品检索节点：根据需求调用 mcp_dtk 搜索工具。

    检索完成后扇出为 price / reputation 两条并行分支。
    MCP 调用异常时降级为空候选列表，不中断图执行。
    """
    from mcp_dtk.tools import search_goods

    requirement = state.get("requirement")
    if not requirement:
        return {**state, "next_agent": "scoring", "products": [], "messages": []}

    keywords = requirement.category
    if requirement.scenario:
        keywords += f" {requirement.scenario}"

    price_min = None
    price_max = None
    if requirement.budget_min:
        price_min = float(requirement.budget_min)
    if requirement.budget_max:
        price_max = float(requirement.budget_max)

    products: list[NormalizedProduct] = []
    error_msg = ""
    try:
        products = await search_goods(
            keywords=keywords,
            page_size=20,
            price_min=price_min,
            price_max=price_max,
            has_coupon=True,
            sort="0",
        )
    except Exception as e:
        logger.error("search_goods MCP 调用失败: %s", e)
        error_msg = f"（检索异常：{type(e).__name__}，将重试）"

    # 按预算硬过滤
    if price_max:
        products = [p for p in products if p.price <= _to_decimal(price_max)]

    return {
        **state,
        "products": products,
        "next_agent": "scoring",
        "messages": [AIMessage(
            content=f"检索到 {len(products)} 个候选商品{error_msg}，正在并行分析价格与口碑..."
        )],
    }


def _to_decimal(val):
    from decimal import Decimal
    return Decimal(str(val))