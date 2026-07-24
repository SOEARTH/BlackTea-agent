"""口碑分析 Agent（M3）：方面级 RAG 聚合口碑分。

M1/M2 阶段为 stub，返回默认评分；M3 接 Milvus review_corpus 做 aspect-based 聚合。

并行节点：与 price_node 同时执行，仅写自己的 state 字段（reputation_scores），
不返回 **state 全量、不设 next_agent，避免并行分支写冲突。
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from app.agents.state import GraphState


async def reputation_node(state: GraphState) -> GraphState:
    """口碑分析节点。

    M3 实现：从 Milvus review_corpus 检索与商品品类相关的口碑语料，
    按"续航/做工/售后/性价比"等维度做 aspect-based 聚合，产出结构化口碑分。

    M1/M2 stub：用店铺评分（dsr_score/ship_score/service_score）做简易口碑代理。
    """
    products = state.get("products", [])
    reputation_scores: dict[str, float] = {}

    for p in products:
        # M1/M2: 用大淘客店铺评分做简易口碑代理（满分 5 -> 映射到 0-10）
        scores = [s for s in [p.dsr_score, p.ship_score, p.service_score] if s is not None]
        if scores:
            avg = sum(scores) / len(scores)
            reputation_scores[p.goods_id] = round(avg * 2, 1)  # 5分制 -> 10分制
        else:
            reputation_scores[p.goods_id] = 6.0  # 无评分默认中等

    return {
        "reputation_scores": reputation_scores,
        "messages": [AIMessage(content="口碑分析完成，正在打分排序...")],
    }