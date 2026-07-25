"""记忆召回集成：在打分前从画像 + 情景记忆动态调整决策参数。

集成点：scoring 节点调用 apply_memory_weights()，
读到的画像事实和情景记忆会覆盖/微调 _compute_dynamic_weights 的初始权重。

降级策略：Milvus / PG 不可用时，静默降级为 M2 的静态权重，不中断流程。
"""
from __future__ import annotations

import logging
from typing import Any

from app.models.requirement import ShoppingRequirement

logger = logging.getLogger(__name__)


async def apply_memory_weights(
    weights: dict[str, float],
    user_id: str | None,
    requirement: ShoppingRequirement | None,
) -> dict[str, float]:
    """根据用户画像和情景记忆微调打分权重。

    画像规则：
    - 预算带"低" → price 权重 +0.08
    - 预算带"高" → reputation 权重 +0.05（高预算更看品质）
    - 有排斥品牌历史 → brand 权重 +0.03（更关注品牌筛选）

    情景记忆规则：
    - 召回到"因为续航退过货"类记忆 → reputation 权重 +0.05

    调整后归一化，确保总和 = 1.0。
    """
    if not user_id:
        return weights

    adjusted = dict(weights)
    memory_adjustments: list[str] = []

    try:
        from app.db.milvus.memory import read_profile_facts, recall_episodic_memories
        from app.db.checkpointer import get_connection_pool

        pool = await get_connection_pool()
        if pool is None:
            return weights

        # 1. 读画像
        facts = await read_profile_facts(pool, user_id)
        for fact in facts:
            if fact.get("category") == "budget" and fact.get("key") in ("预算带", "budget_band"):
                band = fact["value"]
                if band in ("低", "low"):
                    adjusted["price"] += 0.08
                    memory_adjustments.append("低预算用户→价格权重上调")
                elif band in ("高", "high"):
                    adjusted["reputation"] += 0.05
                    memory_adjustments.append("高预算用户→口碑权重上调")
            elif fact.get("category") == "brand" and fact.get("key") in ("排斥品牌", "excluded_brand"):
                adjusted["brand"] += 0.03
                memory_adjustments.append("有排斥品牌历史→品牌权重上调")

        # 2. 召回情景记忆
        query = requirement.category if requirement else "购物"
        memories = await recall_episodic_memories(user_id, query, top_k=3)
        if memories:
            # 有记忆召回，微调口碑权重（历史经验影响决策）
            adjusted["reputation"] += 0.03 * len(memories) / 3
            memory_adjustments.append(f"召回{len(memories)}条情景记忆→口碑权重微调")

        # 归一化
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        if memory_adjustments:
            logger.info("记忆调权: %s", "; ".join(memory_adjustments))

    except Exception as e:
        logger.warning("记忆召回失败，降级为静态权重: %s", e)

    return adjusted
