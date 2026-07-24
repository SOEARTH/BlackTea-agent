"""比价 Agent：查询历史券后价趋势，判断当前是否好价。

并行节点：与 reputation_node 同时执行，仅写自己的 state 字段（price_analysis），
不返回 **state 全量、不设 next_agent，避免并行分支写冲突。
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from app.agents.state import GraphState


async def price_node(state: GraphState) -> GraphState:
    """比价节点：对候选商品查询历史券后价，计算当前价在历史分位的位置。"""
    from mcp_dtk.tools import get_price_trend

    products = state.get("products", [])
    price_analysis: dict[str, dict] = {}

    for p in products[:10]:  # 只查前 10 个，控配额
        try:
            trend = await get_price_trend(p.goods_id)
            if not trend:
                continue
            prices = [float(t["price"]) for t in trend if t.get("price")]
            current = float(p.price)
            if prices:
                below = sum(1 for hp in prices if hp >= current)
                percentile = below / len(prices)  # 0=最贵, 1=最便宜
                is_good_price = percentile >= 0.6  # 当前价在历史 60 分位以下算好价
            else:
                percentile = None
                is_good_price = True  # 无历史数据，不否决
            price_analysis[p.goods_id] = {
                "trend": trend,
                "current_percentile": percentile,
                "is_good_price": is_good_price,
            }
        except Exception:
            continue  # 单品查询失败不影响整体

    good_count = sum(1 for v in price_analysis.values() if v["is_good_price"])
    return {
        "price_analysis": price_analysis,
        "messages": [AIMessage(
            content=f"完成 {len(price_analysis)} 个商品的价格趋势分析，"
                    f"其中 {good_count} 个当前价格位于好价区间。"
        )],
    }