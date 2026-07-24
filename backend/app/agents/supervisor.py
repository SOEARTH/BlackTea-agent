"""Supervisor 路由节点：根据 next_agent 决定下一个执行节点。"""
from __future__ import annotations

from app.agents.state import GraphState


def supervisor_node(state: GraphState) -> GraphState:
    """Supervisor 节点：读取 next_agent 字段，决定路由方向。

    本身不做数据处理，只是路由控制点。LangGraph 的条件边会读取 next_agent 值。
    """
    _ = state  # supervisor 不修改 state，只做路由
    return state
