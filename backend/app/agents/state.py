"""LangGraph 共享状态定义。

所有 agent 节点通过 GraphState 传递数据，Supervisor 根据状态决定下一个节点。
"""
from __future__ import annotations

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.models.decision import DecisionReport, ScoredProduct
from app.models.product import NormalizedProduct
from app.models.requirement import ShoppingRequirement


class GraphState(TypedDict, total=False):
    """LangGraph 图状态，所有 agent 节点的共享数据载体。"""

    # 对话消息（LangGraph 自动合并）
    messages: Annotated[list[AnyMessage], add_messages]

    # 需求结构（澄清 agent 输出）
    requirement: ShoppingRequirement | None

    # 候选商品（检索 agent 输出）
    products: list[NormalizedProduct]

    # 打分结果（打分 agent 输出）
    scored_products: list[ScoredProduct]

    # 决策报告（反思 agent 通过后输出）
    report: DecisionReport | None

    # 反思记录
    reflection_notes: list[str]

    # 控制流
    next_agent: str       # supervisor 决定下一个节点
    iteration: int        # 反思循环计数，防死循环

    # 口碑分析（M3，RAG agent 输出）
    reputation_scores: dict[str, float]  # goods_id -> 口碑分

    # 比价分析
    price_analysis: dict[str, dict]     # goods_id -> {trend, current_percentile, is_good_price}
