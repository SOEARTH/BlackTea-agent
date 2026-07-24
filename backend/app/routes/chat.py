"""SSE 流式对话端点。

两个端点：
- POST /api/chat        — 发起新对话或继续对话（用户输入消息）
- POST /api/chat/resume — interrupt 恢复（用户补充信息后继续）

SSE 事件类型：
- agent     — 某 agent 节点执行完成，含 node 名称 + AIMessage 内容
- interrupt — clarify 触发 interrupt，含反问消息 + thread_id
- report    — reflect 通过，含完整 DecisionReport JSON
- error     — 异常，含错误消息
- done      — 流结束，含 thread_id
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


# ---- 请求模型 ----

class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None  # None = 新建线程


class ResumeRequest(BaseModel):
    answer: str
    thread_id: str  # 必填，恢复已有线程


# ---- JSON 序列化辅助 ----

def _json_default(obj: Any) -> Any:
    """处理 Decimal / datetime / Pydantic model 等 JSON 不兼容类型。"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=_json_default)


# ---- SSE 事件提取 ----

def extract_event_from_update(node_name: str, state_delta: dict) -> dict:
    """从节点 state delta 中提取可发给前端的事件数据。"""
    event: dict[str, Any] = {"node": node_name}

    # 提取最后一条 AIMessage 的内容作为 agent 消息
    messages = state_delta.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            event["message"] = msg.content
            break

    # 商品数量
    if "products" in state_delta:
        products = state_delta["products"]
        event["products_count"] = len(products) if products else 0

    # 打分结果数量
    if "scored_products" in state_delta:
        scored = state_delta["scored_products"]
        event["scored_count"] = len(scored) if scored else 0

    return event


def extract_report(state_delta: dict) -> dict | None:
    """如果 state delta 包含决策报告，提取其 JSON。"""
    report = state_delta.get("report")
    if report is not None:
        return report.model_dump(mode="json")
    return None


# ---- 核心流式生成器 ----

async def stream_graph_events(
    graph,
    input_data,
    config: dict,
    *,
    is_resume: bool = False,
) -> AsyncGenerator[dict, None]:
    """流式执行 graph，yield SSE 事件 dict。

    Args:
        graph: 已编译的 LangGraph（需带 checkpointer 才能检测 interrupt）。
        input_data: 首次调用为 initial state dict；resume 时为 Command(resume=...)。
        config: {"configurable": {"thread_id": ...}}。
        is_resume: True 时跳过初始 message 注入逻辑。
    """
    thread_id = config["configurable"]["thread_id"]

    try:
        # 流式执行
        async for chunk in graph.astream(input_data, config, stream_mode="updates"):
            for node_name, state_delta in chunk.items():
                if node_name.startswith("__"):
                    continue

                # agent 事件
                event_data = extract_event_from_update(node_name, state_delta)
                yield {"event": "agent", "data": _dumps(event_data)}

                # 如果 reflect 节点返回了报告，单独发一个 report 事件
                report_json = extract_report(state_delta)
                if report_json is not None:
                    yield {"event": "report", "data": _dumps(report_json)}

        # 流结束 — 检查是否因 interrupt 暂停
        try:
            state = await graph.aget_state(config)
            if state.next:
                # 图被 interrupt 暂停
                interrupts = state.interrupts or ()
                if interrupts:
                    interrupt_msg = interrupts[0].value
                else:
                    interrupt_msg = "需要补充更多信息"

                yield {
                    "event": "interrupt",
                    "data": _dumps({
                        "message": str(interrupt_msg),
                        "thread_id": thread_id,
                    }),
                }
        except Exception as e:
            # 无 checkpointer 或状态不可用（不应发生在线上）
            logger.warning("无法获取 graph 状态: %s", e)

        # done 事件
        yield {"event": "done", "data": _dumps({"thread_id": thread_id})}

    except Exception as e:
        logger.exception("SSE 流式执行异常")
        yield {
            "event": "error",
            "data": _dumps({"message": f"{type(e).__name__}: {e}"}),
        }


# ---- 端点 ----

@router.post("/chat")
async def chat(request: ChatRequest, req: Request):
    """发起或继续对话。"""
    graph = req.app.state.graph if hasattr(req.app.state, "graph") else None
    if not graph:
        raise HTTPException(status_code=503, detail="Graph 未就绪")

    thread_id = request.thread_id or str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [HumanMessage(content=request.message)],
    }

    async def event_source():
        async for event in stream_graph_events(graph, initial_state, config):
            yield event

    return EventSourceResponse(event_source())


@router.post("/chat/resume")
async def chat_resume(request: ResumeRequest, req: Request):
    """interrupt 恢复：用户补充信息后继续执行。"""
    graph = req.app.state.graph if hasattr(req.app.state, "graph") else None
    if not graph:
        raise HTTPException(status_code=503, detail="Graph 未就绪")

    config = {"configurable": {"thread_id": request.thread_id}}
    input_data = Command(resume=request.answer)

    async def event_source():
        async for event in stream_graph_events(
            graph, input_data, config, is_resume=True
        ):
            yield event

    return EventSourceResponse(event_source())
