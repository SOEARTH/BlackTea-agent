"""反思校验 Agent：检查预算合规/硬约束/好价，决定通过或打回。"""
from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from app.agents.state import GraphState
from app.models.decision import DecisionReport


MAX_ITERATIONS = 3  # 最大反思循环次数


def reflect_node(state: GraphState) -> GraphState:
    """反思校验节点。

    检查项：
    1. 是否超预算（budget_max）
    2. 是否漏硬约束（must_have）—— M2 改为 LLM 校验
    3. 好价占比是否达标

    通过则生成 DecisionReport；不通过则增加 iteration 并打回到 scoring。
    """
    requirement = state.get("requirement")
    scored = state.get("scored_products", [])
    price_analysis = state.get("price_analysis", {})
    iteration = state.get("iteration", 0)
    notes = list(state.get("reflection_notes", []))

    issues: list[str] = []

    # 1. 预算检查
    if requirement and requirement.budget_max:
        budget = float(requirement.budget_max)
        over_budget = [s for s in scored if float(s.product.price) > budget]
        if over_budget:
            issues.append(f"有 {len(over_budget)} 个商品超过预算 {budget} 元")
            # 过滤超预算商品
            scored = [s for s in scored if float(s.product.price) <= budget]

    # 2. 好价占比检查
    if price_analysis and scored:
        good_ratio = sum(
            1 for s in scored[:5]
            if price_analysis.get(s.product.goods_id, {}).get("is_good_price", True)
        ) / min(5, len(scored))
        if good_ratio < 0.4:
            issues.append(f"好价占比仅 {good_ratio:.0%}，建议重新检索调整筛选条件")

    # 3. 是否有结果
    if not scored:
        issues.append("候选商品为空，需要调整搜索条件或放宽预算")
    elif scored[0].total < 5.0:
        issues.append(f"最高分仅 {scored[0].total}，整体质量低，建议调整搜索策略")

    # 4. 防死循环
    if iteration >= MAX_ITERATIONS:
        notes.append(f"已达最大反思次数 {MAX_ITERATIONS}，强制通过")
        issues = []  # 放弃检查

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
        report = DecisionReport(
            requirement=requirement,
            recommendations=scored[:10],
            combos=[],  # M2 组合场景
            summary=_generate_summary(scored, requirement, price_analysis),
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
            )],
        }


def _generate_summary(scored, requirement, price_analysis) -> str:
    """生成决策报告摘要。"""
    if not scored:
        return "未找到符合条件的商品。"
    top = scored[0]
    lines = [
        f"需求：{requirement.category if requirement else '未指定' }",
        f"推荐第 1 名：{top.product.title}（综合得分 {top.total}）",
        f"价格：{top.product.price} 元（券后）",
    ]
    if price_analysis.get(top.product.goods_id):
        pa = price_analysis[top.product.goods_id]
        lines.append(f"价格趋势：{'好价区间' if pa.get('is_good_price') else '偏高'}"
                     f"（历史分位 {pa.get('current_percentile', 'N/A')}）")
    return "；".join(lines)
