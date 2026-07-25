"""口碑分析 Agent（M3）：方面级 RAG 聚合口碑分。

从 Milvus review_corpus 检索与商品品类相关的口碑语料，
按"续航/做工/售后/性价比"等维度做 aspect-based 聚合，产出结构化口碑分。

RAG 不可用时降级为 M1/M2 的 DSR 店铺评分代理，不中断流程。

并行节点：与 price_node 同时执行，仅写 reputation_scores。
"""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from app.agents.state import GraphState
from app.db.milvus.rag import get_reputation_for_product

logger = logging.getLogger(__name__)


async def reputation_node(state: GraphState) -> GraphState:
    """口碑分析节点（M3 RAG，DSR 降级兜底）。"""
    products = state.get("products", [])
    requirement = state.get("requirement")
    category = requirement.category if requirement else None

    reputation_scores: dict[str, float] = {}
    rag_hit_count = 0

    for p in products[:10]:  # M3 配额限制，只查前 10 个
        try:
            rep_result = await get_reputation_for_product(
                product_title=p.title or p.dtitle or "",
                category=category,
            )

            if rep_result["source"] == "rag" and rep_result["overall"] > 0:
                reputation_scores[p.goods_id] = rep_result["overall"]
                rag_hit_count += 1
            else:
                # RAG 无命中，降级用 DSR 店铺评分
                reputation_scores[p.goods_id] = _dsr_fallback(p)
        except Exception as e:
            logger.warning("口碑 RAG 查询失败 goods_id=%s: %s", p.goods_id, e)
            reputation_scores[p.goods_id] = _dsr_fallback(p)

    source_label = f"RAG命中{rag_hit_count}个" if rag_hit_count > 0 else "DSR兜底"
    return {
        "reputation_scores": reputation_scores,
        "messages": [AIMessage(
            content=f"口碑分析完成（{source_label}），正在打分排序..."
        )],
    }


def _dsr_fallback(p) -> float:
    """DSR 店铺评分兜底：5 分制 → 10 分制。"""
    scores = [s for s in [p.dsr_score, p.ship_score, p.service_score] if s is not None]
    if scores:
        avg = sum(scores) / len(scores)
        return round(avg * 2, 1)
    return 6.0
