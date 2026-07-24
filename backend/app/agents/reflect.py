"""反思校验 Agent：预算合规 + LLM 校验硬约束 + 好价占比，决定通过或打回。

M2 升级：
- must_have 硬约束用 LLM 校验（对比商品标题/selling_points 与约束描述）
- 好价占比检查保持不变
- combo 场景的报告携带组合方案
- 综合打分摘要展示各维度分数依据
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, SystemMessage

from app.agents.state import GraphState
from app.agents.utils import get_llm, parse_json_response
from app.models.decision import DecisionReport

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3  # 最大反思循环次数


async def reflect_node(state: GraphState) -> GraphState:
    """反思校验节点（async：LLM 调用需要 async）。"""
    requirement = state.get("requirement")
    scored = state.get("scored_products", [])
    price_analysis = state.get("price_analysis", {})
    iteration = state.get("iteration", 0)
    notes = list(state.get("reflection_notes", []))

    issues: list[str] = []

    # 1. 预算检查（硬规则，不依赖 LLM）
    if requirement and requirement.budget_max:
        budget = float(requirement.budget_max)
        over_budget = [s for s in scored if float(s.product.price) > budget]
        if over_budget:
            issues.append(f"有 {len(over_budget)} 个商品超过预算 {budget} 元")
            scored = [s for s in scored if float(s.product.price) <= budget]

    # 2. LLM 校验硬约束（must_have）
    if requirement and requirement.must_have and scored:
        violations = await _llm_check_constraints(scored[:5], requirement.must_have)
        if violations:
            issues.append(f"LLM 检出硬约束不满足：{violations}")

    # 3. 好价占比检查
    if price_analysis and scored:
        good_ratio = sum(
            1 for s in scored[:5]
            if price_analysis.get(s.product.goods_id, {}).get("is_good_price", True)
        ) / min(5, len(scored))
        if good_ratio < 0.4:
            issues.append(f"好价占比仅 {good_ratio:.0%}，建议重新检索调整筛选条件")

    # 4. 是否有结果 + 最低质量门槛
    if not scored:
        issues.append("候选商品为空，需要调整搜索条件或放宽预算")
    elif scored[0].total < 4.0:
        issues.append(f"最高分仅 {scored[0].total}，整体质量低，建议调整搜索策略")

    # 5. 防死循环
    if iteration >= MAX_ITERATIONS:
        notes.append(f"已达最大反思次数 {MAX_ITERATIONS}，强制通过（剩余检查跳过）")
        issues = []

    if issues:
        notes.append(f"第 {iteration + 1} 轮反思：{'; '.join(issues)}")
        return {
            **state,
            "scored_products": scored,
            "reflection_notes": notes,
            "iteration": iteration + 1,
            "next_agent": "search",  # 打回重新检索
        }
    else:
        # 通过，生成决策报告
        combos = state.get("combos", [])
        if not combos and requirement and requirement.combo and requirement.slots:
            from app.agents.optimizer import generate_combo_summary, knapsack_combo
            combos = knapsack_combo(scored, requirement)
            if combos:
                combo_summary = generate_combo_summary(combos, requirement)
                notes.append(f"组合方案：{combo_summary}")

        report = DecisionReport(
            requirement=requirement,
            recommendations=scored[:10],
            combos=combos,
            summary=_generate_summary(scored, requirement, price_analysis, combos),
            reflection_notes=notes,
            created_at=datetime.now(timezone.utc),
        )
        return {
            **state,
            "report": report,
            "reflection_notes": notes,
            "next_agent": "END",
            "messages": [AIMessage(
                content=f"反思通过，决策报告已生成。推荐第 1 名："
                    f"{scored[0].product.title if scored else '无'}"
                    f"（综合得分 {scored[0].total if scored else 'N/A'}）"
                    + (f"\n另生成 {len(combos)} 套组合方案" if combos else "")
            )],
        }


async def _llm_check_constraints(scored_products: list, must_have: list[str]) -> str:
    """用 LLM 校验 top-N 商品是否满足 must_have 硬约束。

    Returns:
        空字符串表示全部通过，否则返回不满足描述。
    """
    llm = get_llm()

    items_text = "\n".join(
        f"商品{i + 1}: {sp.product.title or sp.product.dtitle} | "
        f"卖点: {sp.product.selling_points or '无'} | "
        f"特色: {', '.join(sp.product.special_texts) if sp.product.special_texts else '无'}"
        for i, sp in enumerate(scored_products)
    )
    constraints_text = "\n".join(f"- {c}" for c in must_have)

    prompt = f"""你是购物决策质检员。检查以下商品是否满足用户的硬约束。

硬约束列表：
{constraints_text}

候选商品：
{items_text}

逐个判断每个商品是否满足所有硬约束。只输出 JSON：
{{
  "results": [
    {{"index": 1, "satisfied": true/false, "reason": "简短说明"}}
  ]
}}

如果所有商品都满足，results 里全部 satisfied=true。
如果有任何不满足，给出原因。只输出 JSON，不要其他内容。"""

    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        parsed = parse_json_response(response.content)
        results = parsed.get("results", [])
        violations = [
            f"商品{r.get('index')}：{r.get('reason')}"
            for r in results if not r.get("satisfied", True)
        ]
        return "; ".join(violations)
    except Exception as e:
        logger.warning("LLM 硬约束校验失败，跳过: %s", e)
        return ""  # LLM 失败不阻塞流程


def _generate_summary(scored, requirement, price_analysis, combos) -> str:
    """生成决策报告摘要（含组合方案概览）。"""
    if not scored:
        return "未找到符合条件的商品。"
    top = scored[0]
    lines = [
        f"需求：{requirement.category if requirement else '未指定'}",
        f"推荐第 1 名：{top.product.title}（综合得分 {top.total}）",
        f"价格：{top.product.price} 元（券后）",
    ]
    # 打分明细概览
    if top.aspects:
        aspect_desc = "、".join(f"{a.aspect}{a.score}" for a in top.aspects)
        lines.append(f"明分：{aspect_desc}")
    if price_analysis.get(top.product.goods_id):
        pa = price_analysis[top.product.goods_id]
        lines.append(f"价格趋势：{'好价区间' if pa.get('is_good_price') else '偏高'}"
                     f"（历史分位 {pa.get('current_percentile', 'N/A')}）")
    if combos:
        lines.append(f"组合方案 {len(combos)} 套（详见下方对比）")
    return "；".join(lines)
