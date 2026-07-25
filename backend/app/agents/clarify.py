"""需求澄清 Agent：把用户模糊输入结构化为 ShoppingRequirement。

如果关键信息缺失（预算、品类），通过 interrupt 反问用户（human-in-the-loop）。
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.state import GraphState
from app.agents.utils import get_llm, parse_json_response
from app.models.requirement import ShoppingRequirement

CLARIFY_PROMPT = """你是一个购物需求澄清专家。分析用户的购物需求，提取以下结构化信息。

用户消息：{user_message}

请提取以下字段（JSON 格式，没有的填 null 或空列表）：
- category: 商品品类，如"蓝牙耳机"、"露营装备"、"笔记本电脑"
- scenario: 使用场景，如"通勤降噪"、"周末双人露营"，没有则 null
- budget_min: 预算下限（元），没有则 null
- budget_max: 预算上限（元），没有则 null
- must_have: 硬约束列表，如["续航>20h", "IPX5防水"]
- nice_to_have: 软偏好列表，如["白色优先"]
- excluded: 排除项列表，如["不要某品牌"]
- combo: 是否组合采购（多件商品组合），true/false
- slots: 组合采购的品类槽位，如["帐篷","睡袋","炉具"]

只输出 JSON，不要输出其他内容。"""

NEED_CLARIFY_PROMPT = """根据用户已提供的信息，判断还缺哪些关键信息。

当前已提取的需求：{requirement}

必须有的关键信息：
1. category（品类）—— 必须
2. budget_max（预算上限）—— 没有 budget_max 时，budget_min 也可以接受

如果缺少以上任一关键信息，请生成一句简短的反问（向用户索要缺失信息）。
如果信息充足，回复 COMPLETE。

只输出反问文本或 COMPLETE，不要输出其他内容。"""


def clarify_node(state: GraphState) -> GraphState:
    """需求澄清节点。

    流程：
    1. 用 LLM 提取结构化需求
    2. 检查是否缺关键信息
    3. 缺则 interrupt 反问用户；不缺则写入 state
    """
    llm = get_llm()

    # 获取最后一条用户消息
    user_msg = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            user_msg = msg.content
            break

    # 第一步：LLM 提取结构化需求
    extract_prompt = CLARIFY_PROMPT.format(user_message=user_msg)
    response = llm.invoke([SystemMessage(content=extract_prompt)])
    parsed = parse_json_response(response.content)

    # 构建 ShoppingRequirement（budget 字段安全转为 Decimal）
    from decimal import Decimal

    def _to_decimal(val):
        if val is None:
            return None
        return Decimal(str(val))

    requirement = ShoppingRequirement(
        category=parsed.get("category", "") or "",
        scenario=parsed.get("scenario"),
        budget_min=_to_decimal(parsed.get("budget_min")),
        budget_max=_to_decimal(parsed.get("budget_max")),
        must_have=parsed.get("must_have", []),
        nice_to_have=parsed.get("nice_to_have", []),
        excluded=parsed.get("excluded", []),
        combo=bool(parsed.get("combo", False)),
        slots=parsed.get("slots", []),
    )

    # 第二步：检查是否缺关键信息
    check_prompt = NEED_CLARIFY_PROMPT.format(
        requirement=requirement.model_dump_json()
    )
    check_response = llm.invoke([SystemMessage(content=check_prompt)])
    check_text = check_response.content.strip()

    if check_text == "COMPLETE" or check_text.startswith("COMPLETE"):
        # M3: skill
        from app.skills.loader import enrich_requirement_prompt
        skill_hint = enrich_requirement_prompt(requirement.category)
        msg = f"需求已明确：{requirement.category}，预算 "
        msg += f"{requirement.budget_max or '不限'} 元。正在为你检索商品..."
        if skill_hint:
            msg += f"（已加载{requirement.category}选购方法论）"
        return {
            **state,
            "requirement": requirement,
            "next_agent": "search",
            "messages": [AIMessage(content=msg)],
        }
    else:
        # 信息不足，interrupt 反问用户
        from langgraph.types import interrupt
        clarify_msg = check_text
        answer = interrupt(clarify_msg)
        # interrupt 恢复后，answer 是用户的新输入
        return {
            **state,
            "messages": [HumanMessage(content=answer)],
            "next_agent": "clarify",  # 重新进入澄清
        }
