"""LangGraph 图构建：把所有 agent 节点用边连接起来。

拓扑：
    START -> clarify ──(信息不足)──> clarify  (interrupt 自环, human-in-the-loop)
                  └──(信息充足)──> search
                              -> [ price || reputation ] -> scoring -> reflect
                     ^                                                    |
                     |____________________打回重检_________________________|
                                                       |
                                                     通过 -> supervisor -> END

容错机制：
- clarify 条件边：interrupt 恢复后 next_agent="clarify" 自环重新提取需求
- search 异常降级：MCP 调用失败时返回空候选，由 reflect 打回或告知用户
- price 异常降级：单商品趋势查询失败跳过，不影响其他商品
- reflect 死循环保护：MAX_ITERATIONS=3 强制通过

checkpointer 传入 PostgresSaver 后，graph 具备持久化能力：
- interrupt 恢复（用户回复后用 Command(resume=...) 继续）
- 线程历史回放（thread_id 跨请求恢复上下文）
- 短期记忆（线程内 state 持久化到 PG）
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.clarify import clarify_node
from app.agents.price import price_node
from app.agents.reflect import reflect_node
from app.agents.reputation import reputation_node
from app.agents.scoring import scoring_node
from app.agents.search import search_node
from app.agents.state import GraphState
from app.agents.supervisor import supervisor_node


def route_from_clarify(state: GraphState) -> str:
    """clarify 条件边：信息不足时自环重新澄清，信息充足时推进到 search。"""
    return state.get("next_agent", "clarify")


def build_graph(checkpointer=None):
    """构建并编译 LangGraph 图。

    Args:
        checkpointer: 可选，传入 AsyncPostgresSaver 实例启用持久化。
                      不传（默认 None）时编译为无 checkpointer 的图，
                      纯内存执行，用于单测和离线调试。

    clarify 用条件边实现 interrupt 自环：信息不足时 interrupt 暂停图，
    用户回复后 Command(resume=...) 恢复执行，next_agent="clarify" 触发自环，
    重新提取需求；信息充足后 next_agent="search" 推进到检索。

    clarify -> search 之后扇出为两条并行分支（price / reputation），
    两者完成后汇聚到 scoring，再进入 reflect 做反思校验。
    """
    graph = StateGraph(GraphState)

    # 注册节点
    graph.add_node("clarify", clarify_node)
    graph.add_node("search", search_node)
    graph.add_node("price", price_node)
    graph.add_node("reputation", reputation_node)
    graph.add_node("scoring", scoring_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("supervisor", supervisor_node)

    # 入口边
    graph.add_edge(START, "clarify")

    # clarify 条件边：interrupt 自环（信息不足）或推进到 search（信息充足）
    graph.add_conditional_edges(
        "clarify",
        route_from_clarify,
        {
            "clarify": "clarify",   # interrupt 恢复，重新提取需求
            "search": "search",     # 信息充足，进入检索
        },
    )

    # 并行扇出：search -> price || reputation
    graph.add_edge("search", "price")
    graph.add_edge("search", "reputation")

    # 并行汇聚：price & reputation -> scoring
    graph.add_edge("price", "scoring")
    graph.add_edge("reputation", "scoring")

    # 打分 -> 反思
    graph.add_edge("scoring", "reflect")

    # 反思决策路由：通过 -> supervisor -> END，打回 -> search
    graph.add_conditional_edges(
        "reflect",
        lambda state: state.get("next_agent", "search"),
        {
            "search": "search",
            "END": "supervisor",
        },
    )

    # supervisor -> END
    graph.add_edge("supervisor", END)

    return graph.compile(checkpointer=checkpointer)
